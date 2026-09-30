import os
import json
from typing import Dict, Any, List, Optional
from .models import (
    OnionRecord,
    LotStatistics,
    OnionGradingRecord,
    CategoryBreakdown,
    GradingLotSummary
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STANDARDS_FILE = os.path.join(CURRENT_DIR, "standards.json")


def load_standards() -> Dict[str, Any]:
    with open(STANDARDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


class GradingEngine:
    """
    Transparent onion-level grading layer.
    Converts visual detections (sound, rotten, sprout, double_split, size)
    into Grade A, URS, Defective, and Undersized categories.
    
    Principles:
    1. AI detection answers: 'What visible characteristics are present?'
    2. Grading engine answers: 'What category does this onion fall into under the selected criteria?'
    3. Grade A is NEVER calculated as a simple '100 - defect %' heuristic.
    4. If criteria are not configured for a standard, the engine explicitly reports
       'Grade A / URS calculation unavailable' and states the missing requirements.
    """

    def __init__(self, standards_path: str = STANDARDS_FILE):
        self.standards_path = standards_path
        self.standards = self._load()

    def _load(self) -> Dict[str, Any]:
        with open(self.standards_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def grade_lot(
        self,
        onions: List[OnionRecord],
        lot_stats: LotStatistics,
        standard_id: str = "local_market"
    ) -> GradingLotSummary:
        std = self.standards.get(standard_id, self.standards.get("local_market", {}))
        criteria_cfg = std.get("grading_criteria", {})

        assessment_basis_statement = (
            "This assessment is generated from image-based observations and the selected "
            "grading criteria. The same criteria are applied consistently to the detected "
            "onions to support transparent and repeatable assessment."
        )

        total_detected = len(onions)

        # 1. Check if Grade A / URS criteria are configured for this standard
        is_configured = criteria_cfg.get("configured", False)

        if not is_configured:
            missing = criteria_cfg.get("missing_requirements", [
                "Official procurement tender definition of Grade A vs URS for this standard",
                "Physical diameter calibration in mm (cannot be reliably verified from uncalibrated RGB pixels)",
                "Lot weight data (NAFED/APMC procurement limits are based on weight percentages, not visual image count)"
            ])
            return GradingLotSummary(
                is_configured=False,
                status_message="Grade A / URS calculation unavailable",
                unavailability_reason="This grading profile does not currently contain Grade A / URS criteria.",
                missing_criteria=missing,
                total_onions_assessed=total_detected,
                assessment_basis_statement=assessment_basis_statement
            )

        if total_detected == 0:
            return GradingLotSummary(
                is_configured=True,
                status_message="No onions detected",
                unavailability_reason="Try uploading a clearer image with onions clearly visible.",
                total_onions_assessed=0,
                assessment_basis_statement=assessment_basis_statement
            )

        # 2. Grade each onion individually
        onion_gradings: List[OnionGradingRecord] = []
        grade_a_count = 0
        urs_count = 0
        defective_count = 0
        undersized_count = 0
        insufficient_data_count = 0

        for o in onions:
            defects = list(o.defect_types)
            size_cat = o.approximate_size_category  # "Large", "Medium", "Small"

            # Check defect precedence: Active rot or sprouting is an immediate Reject / Defective
            if o.rotten:
                category = "Defective / Reject"
                reason = "Visible surface rot/decay detected within bulb boundary."
                defective_count += 1
            elif o.sprout:
                category = "Defective / Reject"
                reason = "Visible vegetative sprout emergence detected."
                defective_count += 1
            elif o.double_split:
                # Double / split bulb: classified as URS (Under Requisite Standard)
                category = "URS"
                reason = "Double/split bulb malformation detected; classified as Under Requisite Standard (URS)."
                urs_count += 1
                if size_cat == "Small":
                    undersized_count += 1
            elif size_cat == "Small":
                # Sound bulb, but undersized
                category = "URS"
                reason = "Sound bulb but falls in the Small (undersized) approximate visual size category."
                urs_count += 1
                undersized_count += 1
            elif size_cat in ("Medium", "Large"):
                # Sound single bulb in acceptable size band
                category = "Grade A"
                reason = f"Sound single bulb in {size_cat} size band with zero detected surface defects."
                grade_a_count += 1
            else:
                category = "Insufficient data"
                reason = "Bulb size and quality parameters could not be conclusively determined from visual evidence."
                insufficient_data_count += 1

            onion_gradings.append(OnionGradingRecord(
                onion_id=o.onion_id,
                size_category=size_cat,
                visible_defects=defects,
                grade_category=category,
                reason=reason
            ))

        # 3. Calculate lot percentages with total_detected as denominator
        grade_a_pct = round((grade_a_count / total_detected) * 100.0, 1)
        urs_pct = round((urs_count / total_detected) * 100.0, 1)
        defective_pct = round((defective_count / total_detected) * 100.0, 1)
        undersized_pct = round((undersized_count / total_detected) * 100.0, 1)
        insufficient_pct = round((insufficient_data_count / total_detected) * 100.0, 1)

        # 4. Formulate Category Breakdown
        categories_breakdown = {
            "Grade A": CategoryBreakdown(
                count=grade_a_count,
                percentage=grade_a_pct,
                criteria="Sound single bulb (no rot, sprout, or splitting) in Medium or Large size category.",
                observed_result=f"{grade_a_count} of {total_detected} onions ({grade_a_pct}%)"
            ),
            "URS": CategoryBreakdown(
                count=urs_count,
                percentage=urs_pct,
                criteria="Bulbs with double/split malformation or Small approximate size (free of rot/sprout).",
                observed_result=f"{urs_count} of {total_detected} onions ({urs_pct}%)"
            ),
            "Defective / Reject": CategoryBreakdown(
                count=defective_count,
                percentage=defective_pct,
                criteria="Bulbs exhibiting visible surface rot, decay, or emergent sprouting.",
                observed_result=f"{defective_count} of {total_detected} onions ({defective_pct}%)"
            ),
            "Undersized": CategoryBreakdown(
                count=undersized_count,
                percentage=undersized_pct,
                criteria="Bulbs in the Small approximate image-based size category.",
                observed_result=f"{undersized_count} of {total_detected} onions ({undersized_pct}%)"
            )
        }

        return GradingLotSummary(
            is_configured=True,
            status_message="Grading completed",
            unavailability_reason=None,
            missing_criteria=[],
            total_onions_assessed=total_detected,
            grade_a_count=grade_a_count,
            grade_a_percentage=grade_a_pct,
            urs_count=urs_count,
            urs_percentage=urs_pct,
            defective_count=defective_count,
            defective_percentage=defective_pct,
            undersized_count=undersized_count,
            undersized_percentage=undersized_pct,
            insufficient_data_count=insufficient_data_count,
            insufficient_data_percentage=insufficient_pct,
            onion_gradings=onion_gradings,
            categories_breakdown=categories_breakdown,
            assessment_basis_statement=assessment_basis_statement
        )
