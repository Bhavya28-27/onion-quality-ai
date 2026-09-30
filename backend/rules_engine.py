import json
import os
from typing import Dict, Any, List
from .models import RuleCriterionResult, AssessmentResult, LotStatistics


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STANDARDS_FILE = os.path.join(CURRENT_DIR, "standards.json")


def load_standards() -> Dict[str, Any]:
    with open(STANDARDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


class RulesEngine:
    def __init__(self, standards_path: str = STANDARDS_FILE):
        self.standards_path = standards_path
        self.standards = self._load()

    def _load(self) -> Dict[str, Any]:
        with open(self.standards_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_standards_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": k,
                "name": v.get("name", k),
                "type": v.get("type", "general"),
                "description": v.get("description", "")
            }
            for k, v in self.standards.items()
        ]

    def evaluate(
        self,
        lot_stats: LotStatistics,
        standard_id: str = "local_market",
        calibration_used: bool = False,
        min_observed_diameter_mm: float = None
    ) -> AssessmentResult:
        std = self.standards.get(standard_id, self.standards.get("local_market"))
        std_name = std.get("name", standard_id)

        if lot_stats.total_onions == 0:
            return AssessmentResult(
                standard_id=standard_id,
                standard_name=std_name,
                assessment_status="Insufficient data for complete regulatory grading",
                summary="No onions were detected in the image to perform quality grading.",
                evaluated_criteria=[],
                un_evaluated_criteria=[
                    "Visible surface defect screening",
                    "Diameter / size distribution",
                    "Weight-based defect percentage",
                    "Internal rot inspection"
                ],
                reasons=["Zero onions identified within confidence threshold."],
                recommendation="Upload a clear photograph showing the onion lot under adequate illumination.",
                regulatory_disclaimer="Regulatory grading requires valid lot samples with weight data."
            )

        evaluated_criteria: List[RuleCriterionResult] = []
        reasons: List[str] = []
        any_failed = False

        # 1. Decay / Rotten Criterion
        decay_max = std.get("decay_max_percent", 2.0)
        observed_decay = lot_stats.decay_indicator_percent
        decay_passed = observed_decay <= decay_max
        if not decay_passed:
            any_failed = True
            reasons.append(
                f"Visible decay indicator ({observed_decay:.1f}%) exceeds allowable limit of {decay_max:.1f}%."
            )
        evaluated_criteria.append(RuleCriterionResult(
            criterion="Visible Decay / Rot",
            limit=f"<= {decay_max:.1f}% by visual count",
            observed=f"{observed_decay:.1f}% ({lot_stats.rotten_count}/{lot_stats.total_onions} onions)",
            status="PASS" if decay_passed else "FAIL",
            details="Surface rot detected from RGB bounding box overlap analysis."
        ))

        # 2. Sprouting Criterion
        sprout_max = std.get("sprout_max_percent", 0.0)
        observed_sprout = lot_stats.sprout_indicator_percent
        sprout_passed = observed_sprout <= sprout_max
        if not sprout_passed:
            any_failed = True
            reasons.append(
                f"Visible sprouting indicator ({observed_sprout:.1f}%) exceeds standard limit of {sprout_max:.1f}%."
            )
        evaluated_criteria.append(RuleCriterionResult(
            criterion="Sprouting",
            limit=f"<= {sprout_max:.1f}% (free from sprouts for export)" if sprout_max == 0 else f"<= {sprout_max:.1f}%",
            observed=f"{observed_sprout:.1f}% ({lot_stats.sprout_count}/{lot_stats.total_onions} onions)",
            status="PASS" if sprout_passed else "FAIL",
            details="Emergent green sprout shoots detected within onion boundaries."
        ))

        # 3. Double-Split Criterion
        double_split_max = std.get("double_split_max_percent", 5.0)
        observed_split = lot_stats.double_split_indicator_percent
        split_passed = observed_split <= double_split_max
        if not split_passed:
            any_failed = True
            reasons.append(
                f"Double-split indicator ({observed_split:.1f}%) exceeds standard limit of {double_split_max:.1f}%."
            )
        evaluated_criteria.append(RuleCriterionResult(
            criterion="Double-Split / Malformation",
            limit=f"<= {double_split_max:.1f}%",
            observed=f"{observed_split:.1f}% ({lot_stats.double_split_count}/{lot_stats.total_onions} onions)",
            status="PASS" if split_passed else "FAIL",
            details="Twin bulb divisions or structural split contours detected."
        ))

        # 4. Total Visual Defect Indicator
        defective_limit = std.get("defective_weight_limit_percent", std.get("defective_limit_percent", 10.0))
        observed_defective = lot_stats.defect_indicator_percent
        defect_passed = observed_defective <= defective_limit
        if not defect_passed:
            any_failed = True
            reasons.append(
                f"Total visible defect indicator ({observed_defective:.1f}%) exceeds allowable threshold of {defective_limit:.1f}%."
            )
        evaluated_criteria.append(RuleCriterionResult(
            criterion="Total Visible Defect Indicator",
            limit=f"<= {defective_limit:.1f}% (Visual screening threshold)",
            observed=f"{observed_defective:.1f}% ({lot_stats.defective_onions}/{lot_stats.total_onions} onions with >= 1 defect)",
            status="PASS" if defect_passed else "FAIL",
            details="AI-derived count-based visual indicator. Official limits require weight data."
        ))

        # 5. Size Criterion
        min_dia = std.get("minimum_diameter_mm", None)
        if min_dia is not None:
            if calibration_used and min_observed_diameter_mm is not None:
                size_passed = min_observed_diameter_mm >= min_dia
                if not size_passed:
                    any_failed = True
                    reasons.append(
                        f"Minimum calibrated diameter ({min_observed_diameter_mm:.1f} mm) is below required minimum of {min_dia:.1f} mm."
                    )
                evaluated_criteria.append(RuleCriterionResult(
                    criterion="Minimum Physical Diameter",
                    limit=f">= {min_dia:.1f} mm",
                    observed=f"{min_observed_diameter_mm:.1f} mm",
                    status="PASS" if size_passed else "FAIL",
                    details="Calculated using user-provided physical calibration."
                ))
            else:
                evaluated_criteria.append(RuleCriterionResult(
                    criterion="Minimum Physical Diameter",
                    limit=f">= {min_dia:.1f} mm",
                    observed="Uncalibrated (Pixels only)",
                    status="NOT_EVALUATED",
                    details="Physical diameter in millimeters cannot be reliably calculated without camera calibration or a known reference."
                ))

        un_evaluated = [
            "Weight-based regulatory criteria (requires lot scale weight data or weighing system integration)",
            "Internal rot / heart rot / internal microbial breakdown (cannot be determined from ordinary RGB surface imagery)",
            "Neck tightness and curing dryness (requires tactile manual handling)",
            "Firmness, pungency, and moisture content (laboratory or physical testing required)"
        ]

        if any_failed:
            assessment_status = "Does not meet evaluated criteria"
            summary = (
                f"The lot does NOT satisfy one or more evaluated visual thresholds under '{std_name}'. "
                f"Defective count indicator is {lot_stats.defect_indicator_percent:.1f}%."
            )
            recommendation = (
                "Lot fails preliminary visual screening. Segregation of decayed, sprouted, "
                "or double-split bulbs is strongly recommended prior to packing or dispatch."
            )
        else:
            assessment_status = "Meets evaluated criteria"
            summary = (
                f"All evaluated visual parameters (decay, sprout, splitting) satisfy '{std_name}' preliminary thresholds. "
                "Final regulatory certification requires manual verification and weight verification."
            )
            recommendation = (
                "Proceed to manual sorting verification and weighbridge lot check. "
                "Ensure sample cuts are conducted to verify absence of internal neck/bulb rot."
            )

        regulatory_disclaimer = (
            "Assessment status: Insufficient data for complete regulatory grading without physical inspection. "
            "Weight-based regulatory criteria require lot weight data or integration with a weighing system. "
            "AI observations are advisory and must be verified where regulatory compliance is mandatory."
        )

        return AssessmentResult(
            standard_id=standard_id,
            standard_name=std_name,
            assessment_status=assessment_status,
            summary=summary,
            evaluated_criteria=evaluated_criteria,
            un_evaluated_criteria=un_evaluated,
            reasons=reasons if reasons else ["All evaluated surface defect indicators fall within allowable thresholds."],
            recommendation=recommendation,
            regulatory_disclaimer=regulatory_disclaimer
        )
