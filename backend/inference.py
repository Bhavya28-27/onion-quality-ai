import os
import gc
import time
import math
import threading
import psutil
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from ultralytics import YOLO

from .image_processing import (
    load_and_preprocess_image,
    calculate_onion_dimensions,
    draw_annotated_image
)
from .models import (
    OnionRecord,
    DefectDetail,
    SizeDistribution,
    LotStatistics,
    AnalyzeResponse
)
from .rules_engine import RulesEngine
from .grading_engine import GradingEngine


CLASS_MAPPING = {
    0: "double_split",
    1: "onion",
    2: "rotten",
    3: "sprout"
}

# Thread lock to guarantee single-request inference and maintain < 500 MB RAM
INFERENCE_LOCK = threading.Lock()

# Global singleton model
_MODEL_INSTANCE: Optional[YOLO] = None
_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "model",
    "best.pt"
)


def get_current_ram_mb() -> float:
    """Returns current process RSS memory in Megabytes."""
    process = psutil.Process(os.getpid())
    return round(process.memory_info().rss / (1024 * 1024), 2)


def get_model(model_path: str = _MODEL_PATH) -> YOLO:
    """Loads the YOLO model once and caches the singleton instance."""
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
        _MODEL_INSTANCE = YOLO(model_path)
    return _MODEL_INSTANCE


def compute_iou(boxA: List[float], boxB: List[float]) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0.0, xB - xA)
    inter_h = max(0.0, yB - yA)
    inter_area = inter_w * inter_h

    boxA_area = max(1e-6, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxB_area = max(1e-6, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    iou = inter_area / float(boxA_area + boxB_area - inter_area)
    return max(0.0, min(1.0, iou))


def compute_containment_or_overlap(defect_box: List[float], onion_box: List[float]) -> Tuple[bool, float]:
    """
    Checks if defect center is inside the onion box, and calculates
    intersection over defect area (how much of defect lies within the onion).
    """
    cx = (defect_box[0] + defect_box[2]) / 2.0
    cy = (defect_box[1] + defect_box[3]) / 2.0

    center_inside = (
        onion_box[0] <= cx <= onion_box[2] and
        onion_box[1] <= cy <= onion_box[3]
    )

    xA = max(defect_box[0], onion_box[0])
    yA = max(defect_box[1], onion_box[1])
    xB = min(defect_box[2], onion_box[2])
    yB = min(defect_box[3], onion_box[3])

    inter_w = max(0.0, xB - xA)
    inter_h = max(0.0, yB - yA)
    inter_area = inter_w * inter_h

    defect_area = max(1e-6, (defect_box[2] - defect_box[0]) * (defect_box[3] - defect_box[1]))
    defect_overlap_fraction = inter_area / defect_area

    return center_inside, defect_overlap_fraction


def classify_sizes(onions: List[Dict[str, Any]], calibrated: bool) -> List[str]:
    """
    Categorizes onions into Large, Medium, Small.
    Mode A (Uncalibrated): Uses relative lot distribution.
    Mode B (Calibrated): Uses physical millimeter thresholds.
    """
    if not onions:
        return []

    if calibrated:
        # Standard physical sizing thresholds in mm:
        # >= 50 mm: Large
        # 35 to < 50 mm: Medium
        # < 35 mm: Small
        categories = []
        for o in onions:
            dia = o.get("physical_diameter_mm", 0.0) or 0.0
            if dia >= 50.0:
                categories.append("Large")
            elif dia >= 35.0:
                categories.append("Medium")
            else:
                categories.append("Small")
        return categories

    # Mode A: Relative size categorization based on equivalent diameter
    diameters = [o["equivalent_diameter_pixels"] for o in onions]
    min_d = min(diameters)
    max_d = max(diameters)
    span = max_d - min_d

    # If all onions are virtually identical in size (within 15% range)
    if span < 0.15 * max_d or len(onions) < 3:
        # Categorize by absolute pixel scale if single/few onions
        categories = []
        for d in diameters:
            if d > 200:
                categories.append("Large")
            elif d >= 100:
                categories.append("Medium")
            else:
                categories.append("Small")
        return categories

    # Use percentiles for robust relative distribution
    p33 = np.percentile(diameters, 33.3)
    p67 = np.percentile(diameters, 66.7)

    categories = []
    for d in diameters:
        if d >= p67:
            categories.append("Large")
        elif d >= p33:
            categories.append("Medium")
        else:
            categories.append("Small")
    return categories


def analyze_onion_image(
    image_bytes: bytes,
    standard_id: str = "local_market",
    conf_threshold: float = 0.25,
    enhance_image: bool = False,
    calibration_enabled: bool = False,
    mm_per_pixel: Optional[float] = None
) -> AnalyzeResponse:
    """
    Main inference and grading pipeline.
    Runs strictly one request at a time with low RAM usage (< 500 MB).
    """
    start_time = time.perf_counter()
    initial_ram = get_current_ram_mb()

    with INFERENCE_LOCK:
        model = get_model()

        # Step 1: Preprocessing with dimension downscaling for low RAM
        img_bgr, scale_factor = load_and_preprocess_image(
            image_bytes=image_bytes,
            enhance=enhance_image,
            max_dim=1280
        )

        ram_after_prep = get_current_ram_mb()

        # Step 2: YOLO Object Detection (CPU, lightweight, imgsz=416)
        results = model.predict(
            source=img_bgr,
            imgsz=416,
            conf=conf_threshold,
            device="cpu",
            verbose=False
        )[0]

        ram_during_inf = get_current_ram_mb()

        # Step 3: Extract Detections
        detected_onions: List[Dict[str, Any]] = []
        detected_defects: List[Dict[str, Any]] = []

        if results.boxes is not None and len(results.boxes) > 0:
            for box in results.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                xyxy = [float(v) for v in box.xyxy[0].tolist()]

                class_name = CLASS_MAPPING.get(cls_id, "unknown")

                if class_name == "onion":
                    detected_onions.append({
                        "bbox": xyxy,
                        "confidence": round(conf, 3),
                        "raw_class": class_name
                    })
                elif class_name in ("rotten", "sprout", "double_split"):
                    detected_defects.append({
                        "bbox": xyxy,
                        "confidence": round(conf, 3),
                        "defect_type": class_name
                    })

        # Step 4: Fallback for isolated defect detections without enclosing onion box
        # If a defect has no onion box near it, create an onion proxy around it
        # so heavily decayed bulbs that YOLO only marked as "rotten" are not lost.
        unassociated_defects_initial = []
        for defect in detected_defects:
            has_nearby_onion = False
            for onion in detected_onions:
                c_in, overlap = compute_containment_or_overlap(defect["bbox"], onion["bbox"])
                if c_in or overlap > 0.15:
                    has_nearby_onion = True
                    break
            if not has_nearby_onion:
                # If defect box is reasonably sized (e.g. > 30px side), treat as defective onion bulb
                dw = defect["bbox"][2] - defect["bbox"][0]
                dh = defect["bbox"][3] - defect["bbox"][1]
                if dw >= 30 and dh >= 30 and defect["defect_type"] in ("rotten", "double_split"):
                    detected_onions.append({
                        "bbox": list(defect["bbox"]),
                        "confidence": defect["confidence"],
                        "raw_class": "onion"
                    })
                else:
                    unassociated_defects_initial.append(defect)

        # Step 5: Size & Shape Analysis without segmentation
        calib_factor = mm_per_pixel if (calibration_enabled and mm_per_pixel and mm_per_pixel > 0) else None

        for o in detected_onions:
            dims = calculate_onion_dimensions(o["bbox"], mm_per_pixel=calib_factor)
            o.update(dims)
            o["defect_types"] = []
            o["defects_detail"] = []

        # Relative / Calibrated size assignment
        size_cats = classify_sizes(detected_onions, calibrated=calibration_enabled and calib_factor is not None)
        for i, o in enumerate(detected_onions):
            o["approximate_size_category"] = size_cats[i]

        # Step 6: Defect-to-Onion Association (Geometric Overlap & Center Containment)
        unassigned_defects: List[Dict[str, Any]] = []

        for defect in detected_defects:
            assigned_onion_idx = None
            best_overlap = 0.0
            best_method = ""

            # Check 1: Center Containment
            for idx, onion in enumerate(detected_onions):
                center_in, overlap = compute_containment_or_overlap(defect["bbox"], onion["bbox"])
                if center_in:
                    assigned_onion_idx = idx
                    best_overlap = overlap
                    best_method = "center_containment"
                    break

            # Check 2: If no center containment, pick highest overlap IoU
            if assigned_onion_idx is None:
                for idx, onion in enumerate(detected_onions):
                    iou = compute_iou(defect["bbox"], onion["bbox"])
                    if iou > 0.08 and iou > best_overlap:
                        best_overlap = iou
                        assigned_onion_idx = idx
                        best_method = "iou_overlap"

            if assigned_onion_idx is not None:
                target_onion = detected_onions[assigned_onion_idx]
                d_type = defect["defect_type"]
                if d_type not in target_onion["defect_types"]:
                    target_onion["defect_types"].append(d_type)

                target_onion["defects_detail"].append(DefectDetail(
                    defect_type=d_type,
                    confidence=defect["confidence"],
                    bbox=defect["bbox"],
                    association_method=best_method,
                    overlap_score=round(best_overlap, 3)
                ))
            else:
                unassigned_defects.append(defect)

        # Step 7: Build Onion Records with Explanations
        onion_records: List[OnionRecord] = []
        for i, o in enumerate(detected_onions):
            onion_id = i + 1
            has_rot = "rotten" in o["defect_types"]
            has_sprout = "sprout" in o["defect_types"]
            has_split = "double_split" in o["defect_types"]
            is_defective = len(o["defect_types"]) > 0

            # Explainability rationale
            if is_defective:
                defect_names = ", ".join([d.replace("_", " ").title() for d in o["defect_types"]])
                explanation = (
                    f"Defective: Visible {defect_names} detected within onion boundary "
                    f"with confidence {[d.confidence for d in o['defects_detail']]}."
                )
                status_str = "Defective"
            else:
                explanation = "Sound onion: No visible surface decay, sprouting, or splitting detected."
                status_str = "Sound"

            rec = OnionRecord(
                onion_id=onion_id,
                bbox=o["bbox"],
                width_pixels=o["width_pixels"],
                height_pixels=o["height_pixels"],
                diameter_pixels=o["diameter_pixels"],
                area_pixels=o["area_pixels"],
                equivalent_diameter_pixels=o["equivalent_diameter_pixels"],
                approximate_size_category=o["approximate_size_category"],
                physical_diameter_mm=o.get("physical_diameter_mm"),
                rotten=has_rot,
                sprout=has_sprout,
                double_split=has_split,
                defect_types=o["defect_types"],
                defects_detail=o["defects_detail"],
                confidence=o["confidence"],
                status=status_str,
                explanation=explanation
            )
            onion_records.append(rec)

        # Step 8: Calculate Lot Statistics
        total_onions = len(onion_records)
        defective_count = sum(1 for o in onion_records if len(o.defect_types) > 0)
        sound_count = total_onions - defective_count

        rotten_count = sum(1 for o in onion_records if o.rotten)
        sprout_count = sum(1 for o in onion_records if o.sprout)
        split_count = sum(1 for o in onion_records if o.double_split)

        defect_indicator = round((defective_count / total_onions * 100.0), 1) if total_onions > 0 else 0.0
        decay_indicator = round((rotten_count / total_onions * 100.0), 1) if total_onions > 0 else 0.0
        sprout_indicator = round((sprout_count / total_onions * 100.0), 1) if total_onions > 0 else 0.0
        split_indicator = round((split_count / total_onions * 100.0), 1) if total_onions > 0 else 0.0

        large_cnt = sum(1 for o in onion_records if o.approximate_size_category == "Large")
        medium_cnt = sum(1 for o in onion_records if o.approximate_size_category == "Medium")
        small_cnt = sum(1 for o in onion_records if o.approximate_size_category == "Small")

        size_dist = SizeDistribution(
            large=large_cnt,
            medium=medium_cnt,
            small=small_cnt,
            large_percent=round((large_cnt / total_onions * 100.0), 1) if total_onions > 0 else 0.0,
            medium_percent=round((medium_cnt / total_onions * 100.0), 1) if total_onions > 0 else 0.0,
            small_percent=round((small_cnt / total_onions * 100.0), 1) if total_onions > 0 else 0.0
        )

        eq_diameters = [o.equivalent_diameter_pixels for o in onion_records] if total_onions > 0 else [0.0]
        avg_diam = round(float(np.mean(eq_diameters)), 1)
        min_diam = round(float(np.min(eq_diameters)), 1)
        max_diam = round(float(np.max(eq_diameters)), 1)

        physical_diams = [o.physical_diameter_mm for o in onion_records if o.physical_diameter_mm is not None]
        avg_phys = round(float(np.mean(physical_diams)), 1) if physical_diams else None
        min_phys = round(float(np.min(physical_diams)), 1) if physical_diams else None

        lot_stats = LotStatistics(
            total_onions=total_onions,
            sound_onions=sound_count,
            defective_onions=defective_count,
            rotten_count=rotten_count,
            sprout_count=sprout_count,
            double_split_count=split_count,
            unassigned_defects=len(unassigned_defects),
            defect_indicator_percent=defect_indicator,
            decay_indicator_percent=decay_indicator,
            sprout_indicator_percent=sprout_indicator,
            double_split_indicator_percent=split_indicator,
            size_distribution=size_dist,
            avg_approx_diameter_pixels=avg_diam,
            min_approx_diameter_pixels=min_diam,
            max_approx_diameter_pixels=max_diam,
            avg_physical_diameter_mm=avg_phys
        )

        # Step 9: Standards Evaluation via Rules Engine
        engine = RulesEngine()
        assessment = engine.evaluate(
            lot_stats=lot_stats,
            standard_id=standard_id,
            calibration_used=calibration_enabled and calib_factor is not None,
            min_observed_diameter_mm=min_phys
        )

        # Step 9b: Transparent Onion-Level Grading Engine (Grade A / URS / Defective)
        grading_engine = GradingEngine()
        grading_summary = grading_engine.grade_lot(
            onions=onion_records,
            lot_stats=lot_stats,
            standard_id=standard_id
        )

        # Step 10: Generate Annotated Image
        annotated_b64 = draw_annotated_image(
            image=img_bgr,
            onions=[o.model_dump() for o in onion_records],
            unassigned_defects=unassigned_defects
        )

        # Cleanup prediction structures to guarantee memory safety
        del results
        del img_bgr
        gc.collect()

        final_ram = get_current_ram_mb()
        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 1)

        limitations = [
            "RGB imagery primarily provides visible surface information; internal rot cannot be detected from ordinary photographs.",
            "Physical diameter in millimeters requires camera calibration or a known reference marker. Without calibration, size is reported as approximate image-based pixels.",
            "Weight-based regulatory criteria require lot scale weight data or weighing system integration. Displayed defect percentages are count-based visual indicators.",
            "Model predictions are AI-assisted observations and require verification where regulatory or export decisions are mandatory.",
            "Current model performance reflects the validation dataset and is not a guarantee of universal real-world accuracy under varying lighting or occlusion."
        ]

        memory_telemetry = {
            "initial_ram_mb": initial_ram,
            "peak_inference_ram_mb": max(ram_after_prep, ram_during_inf, final_ram),
            "final_ram_mb": final_ram,
            "target_ram_mb": 500.0,
            "within_target": final_ram < 500.0
        }

        return AnalyzeResponse(
            status="success",
            total_onions=total_onions,
            visible_defects=defective_count,
            defect_indicator_percent=defect_indicator,
            size_distribution={
                "large": size_dist.large,
                "medium": size_dist.medium,
                "small": size_dist.small
            },
            onions=onion_records,
            lot_statistics=lot_stats,
            assessment=assessment,
            grading=grading_summary,
            annotated_image=annotated_b64,
            limitations=limitations,
            memory_telemetry=memory_telemetry,
            calibration_used=calibration_enabled and calib_factor is not None,
            inference_time_ms=elapsed_ms
        )
