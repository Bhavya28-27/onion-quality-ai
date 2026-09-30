import cv2
import numpy as np
import base64
import math
import gc
from typing import Tuple, List, Dict, Any, Optional

MAX_IMAGE_DIM = 1280

# Color mapping in BGR
CLASS_COLORS = {
    "onion": (46, 180, 80),          # Emerald Green
    "rotten": (30, 30, 220),         # Crimson Red
    "sprout": (0, 165, 255),         # Vibrant Orange
    "double_split": (180, 40, 180),  # Purple/Magenta
    "unassigned": (128, 128, 128)    # Grey
}


def load_and_preprocess_image(
    image_bytes: bytes,
    enhance: bool = False,
    max_dim: int = MAX_IMAGE_DIM
) -> Tuple[np.ndarray, float]:
    """
    Decodes image bytes safely, validates dimensions, and scales down if necessary
    to preserve RAM under the 500 MB limit.
    Returns: (preprocessed_bgr_image, scale_factor)
    """
    if not image_bytes or len(image_bytes) == 0:
        raise ValueError("Image data is empty.")

    # Memory efficient decode
    np_buf = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
    del np_buf

    if img is None or img.size == 0:
        raise ValueError("Unsupported or corrupted image file format.")

    h, w = img.shape[:2]
    if h <= 0 or w <= 0:
        raise ValueError(f"Invalid image dimensions: {w}x{h}.")

    # Scale down if larger than max_dim to keep memory usage minimal
    scale = 1.0
    max_side = max(h, w)
    if max_side > max_dim:
        scale = max_dim / float(max_side)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Optional mild brightness/contrast normalization (default OFF)
    if enhance:
        # Convert to LAB and apply gentle CLAHE to L channel only
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        del lab, l, a, b, cl, limg

    return img, scale


def calculate_onion_dimensions(
    bbox: List[float],
    mm_per_pixel: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculates image-based dimensions using bounding boxes without heavy segmentation models.
    """
    x1, y1, x2, y2 = bbox
    width = max(1.0, float(x2 - x1))
    height = max(1.0, float(y2 - y1))
    diameter_pixels = max(width, height)
    area_pixels = width * height
    equivalent_diameter_pixels = 2.0 * math.sqrt(area_pixels / math.pi)

    physical_diameter_mm = None
    if mm_per_pixel is not None and mm_per_pixel > 0:
        physical_diameter_mm = round(equivalent_diameter_pixels * mm_per_pixel, 1)

    return {
        "width_pixels": round(width, 1),
        "height_pixels": round(height, 1),
        "diameter_pixels": round(diameter_pixels, 1),
        "area_pixels": round(area_pixels, 1),
        "equivalent_diameter_pixels": round(equivalent_diameter_pixels, 1),
        "physical_diameter_mm": physical_diameter_mm
    }


def draw_annotated_image(
    image: np.ndarray,
    onions: List[Dict[str, Any]],
    unassigned_defects: List[Dict[str, Any]] = None
) -> str:
    """
    Generates a clean, professional annotated image with high-contrast bounding boxes,
    pills for labels, and distinct defect colors.
    Returns: base64 encoded JPEG string.
    """
    annotated = image.copy()
    h_img, w_img = annotated.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    font_thickness = 1

    # First, draw onion bounding boxes
    for onion in onions:
        box = [int(v) for v in onion["bbox"]]
        x1, y1, x2, y2 = box
        has_defects = len(onion.get("defect_types", [])) > 0
        box_color = (0, 140, 255) if has_defects else CLASS_COLORS["onion"]

        # Onion bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2)

        # Label pill
        size_cat = onion.get("approximate_size_category", "")
        onion_id = onion.get("onion_id", 0)
        conf = onion.get("confidence", 0.0)
        label_text = f"#{onion_id} {size_cat} ({conf:.2f})"

        (tw, th), baseline = cv2.getTextSize(label_text, font, font_scale, font_thickness)
        pill_y1 = max(0, y1 - th - 6)
        pill_y2 = y1
        pill_x1 = x1
        pill_x2 = min(w_img, x1 + tw + 8)

        # Pill background
        cv2.rectangle(annotated, (pill_x1, pill_y1), (pill_x2, pill_y2), box_color, -1)
        cv2.putText(
            annotated,
            label_text,
            (pill_x1 + 4, pill_y2 - 4),
            font,
            font_scale,
            (255, 255, 255),
            font_thickness,
            cv2.LINE_AA
        )

        # Draw associated defect boxes inside/on this onion
        for defect in onion.get("defects_detail", []):
            d_box = [int(v) for v in defect["bbox"]]
            dx1, dy1, dx2, dy2 = d_box
            d_type = defect["defect_type"]
            d_conf = defect["confidence"]
            d_color = CLASS_COLORS.get(d_type, (0, 0, 255))

            # Dashed or thick rectangle for defect
            cv2.rectangle(annotated, (dx1, dy1), (dx2, dy2), d_color, 2)
            
            # Defect mini pill
            d_text = f"{d_type.upper()} {d_conf:.2f}"
            (dtw, dth), _ = cv2.getTextSize(d_text, font, 0.42, 1)
            dp_y1 = max(0, dy1 - dth - 4)
            dp_y2 = dy1
            dp_x1 = dx1
            dp_x2 = min(w_img, dx1 + dtw + 6)
            cv2.rectangle(annotated, (dp_x1, dp_y1), (dp_x2, dp_y2), d_color, -1)
            cv2.putText(
                annotated,
                d_text,
                (dp_x1 + 3, dp_y2 - 3),
                font,
                0.42,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

    # Draw any unassigned defects
    if unassigned_defects:
        for u_defect in unassigned_defects:
            ux1, uy1, ux2, uy2 = [int(v) for v in u_defect["bbox"]]
            u_color = CLASS_COLORS.get(u_defect["defect_type"], CLASS_COLORS["unassigned"])
            cv2.rectangle(annotated, (ux1, uy1), (ux2, uy2), u_color, 2)
            u_text = f"? {u_defect['defect_type'].upper()}"
            cv2.putText(annotated, u_text, (ux1, max(15, uy1 - 5)), font, 0.42, u_color, 1, cv2.LINE_AA)

    # Encode to JPEG
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
    _, buffer = cv2.imencode('.jpg', annotated, encode_params)
    b64_str = base64.b64encode(buffer).decode('utf-8')

    del annotated, buffer
    gc.collect()

    return b64_str
