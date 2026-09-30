# Onion Quality AI (OQ-AI)

> **AI-assisted visual inspection and standards-based assessment system for onion lots.**  
> Built for wholesale mandi yards, procurement centers, and packhouse intake screening.  
> Engineered for lightweight, low-RAM edge CPU deployment (**target: < 500 MB RAM**).

---

## 1. Project Overview

**Onion Quality AI** provides automated, objective visual screening of onion lots using lightweight computer vision and a configurable agricultural standards rules engine.

### Key Capabilities
- **No Marker Required (Default Mode A):** Analyzes ordinary RGB photographs taken with standard smartphones or intake cameras without mandatory ArUco markers or calibration targets.
- **Low RAM Footprint:** Operates strictly under **500 MB RAM** during normal inference by utilizing single-model CPU YOLO object detection without heavy segmentation transformers.
- **Defect-to-Bulb Association:** Accurately maps visible defects (decay, sprouting, double splits) to specific individual onions using geometric center containment and IoU overlap.
- **Configurable Standards Engine:** Compares observed lot metrics against Indian regulatory specifications (National Horticulture Board - NHB Export & Wholesale Mandi classifications).
- **Explainable Quality Assessment:** Generates bulb-by-bulb rationales rather than black-box grades, distinguishing evaluated visual indicators from physical parameters requiring manual verification.
- **Scientific Integrity:** Explicitly highlights that RGB imagery cannot detect internal rot or measure weight without physical scales.

---

## 2. Core Architecture

```
INPUT IMAGE (RGB Photograph)
    │
    ▼
IMAGE PREPROCESSING (OpenCV)
  - Memory-efficient buffer decode
  - Aspect-ratio preserving downscale (max dim 1280px)
  - Optional mild contrast normalization (Default: OFF)
    │
    ▼
LIGHTWEIGHT YOLO OBJECT DETECTION (CPU, imgsz=416)
  - Single model instance loaded once on startup
  - Classes: onion (1), rotten (2), sprout (3), double_split (0)
    │
    ▼
SIZE & SHAPE ANALYSIS (OpenCV Geometric)
  - Bounding box dimension extraction (width, height, area)
  - Circular-equivalent diameter: d = 2 * sqrt(Area / π)
  - Relative sizing categorization (Small, Medium, Large)
    │
    ▼
DEFECT-TO-ONION ASSOCIATION
  - Defect centroid containment within onion boundary
  - Overlap IoU resolution for touching/overlapping boundaries
  - Unassigned defect handling
    │
    ▼
LOT STATISTICS CALCULATION
  - Total count, Sound count, Defect counts & indicators
  - Size distribution & average dimensions
    │
    ▼
CONFIGURABLE STANDARDS RULES ENGINE (rules_engine.py + standards.json)
  - NHB Export (Nasik / Bangalore / Krishnapuram)
  - NHB Wholesale Mandi Local Market
    │
    ▼
TRANSPARENT GRADING ENGINE (grading_engine.py)
  - SIH Procurement Trial Profile
  - Onion-by-onion Grade A / URS / Defective segregation
  - Explicit 'unavailable' reporting for unconfigured official NHB standards
    │
    ▼
DIGITAL QUALITY REPORT & ANNOTATED VISUALIZATION
  - Transparent criteria breakdown (Pass / Fail / Not Evaluated)
  - Grade A & URS percentages with plain-language reasons
  - Downloadable JSON audit report and printable certificate
```

---

## 3. Model Specifications & Validation Metrics

The system uses a compact YOLO object detection model (`model/best.pt`, ~5.2 MB) trained on agricultural onion lots.

### Model Classes
| Class ID | Class Name | Description |
|---|---|---|
| `0` | `double_split` | Malformed twin bulbs or split root structures |
| `1` | `onion` | Sound onion bulb body |
| `2` | `rotten` | Surface microbial decay, fungal lesions, or wet breakdown |
| `3` | `sprout` | Emergent green vegetative shoot growth |

### Research Validation Metrics (Not Claimed as Universal Field Accuracy)
- **Overall:** Precision: 0.704 | Recall: 0.647 | mAP50: 0.674 | mAP50-95: 0.445
- **double_split:** Precision: 0.841 | Recall: 0.642 | mAP50: 0.692
- **onion:** Precision: 0.588 | Recall: 0.648 | mAP50: 0.639
- **rotten:** Precision: 0.533 | Recall: 0.663 | mAP50: 0.596
- **sprout:** Precision: 0.853 | Recall: 0.637 | mAP50: 0.769

---

## 4. RAM Optimization Principles (< 500 MB Target)

To guarantee reliable operation on low-cost edge terminals and field laptops:
1. **No Heavy Transformers:** Explicitly avoids Segment Anything (SAM/SAM2), YOLO11-Seg, and vision transformers.
2. **Single Singleton Model:** The model is initialized once during FastAPI startup (`lifespan`) and kept in memory. Requests never reload the weights.
3. **Serialized Inference:** A threading lock ensures only one inference request executes at a time, eliminating concurrency memory spikes.
4. **Targeted Inference Resolution:** Images are scaled to a maximum dimension of 1280px for display and inferenced at `imgsz=416` in FP32 on CPU.
5. **Memory Hygiene:** Immediate array deletion and explicit garbage collection (`gc.collect()`) after prediction.
6. **Telemetry Monitoring:** Process RSS memory is measured using `psutil` and returned in both `/health` and `/analyze` responses.

---

## 5. Dual Size-Estimation Modes

### Mode A: "Relative Size" (Default)
- **No marker required.**
- Automatically computes bounding box dimensions and equivalent circular diameter:
  $$\text{Equivalent Diameter} = 2 \times \sqrt{\frac{\text{Width} \times \text{Height}}{\pi}}$$
- Categorizes onions into **Large**, **Medium**, and **Small** using the lot's percentile distribution.
- **Explicit Label:** *"Approximate image-based size. Physical diameter in millimeters cannot be reliably calculated without camera calibration or a known reference."*

### Mode B: "Calibrated Size" (Optional)
- Enabled via the Advanced Settings panel.
- Allows user to input a known reference object diameter (e.g., 25 mm coin) and its measured pixel size, or a direct mm-per-pixel ratio.
- Evaluates minimum physical diameter against export standards (e.g., 20 mm for Nasik, 15 mm for Bangalore Rose).

---

## 6. Configurable Standards & Grading Engine

Standards are isolated from detection logic in `backend/standards.json` and evaluated via `backend/rules_engine.py` and `backend/grading_engine.py`.

### Available Standards & Profiles
1. **SIH Procurement Trial (Configurable Trial Profile - `procurement_trial`):** Configurable trial profile for SIH demonstration. Classifies onions into **Grade A**, **URS** (Under Requisite Standard), and **Defective / Reject** based on visual defect segregation and relative size tiers.
2. **NHB Local Market (`local_market`):** Focuses on diameter sorting tiers (Extra Large, Large, Medium, Small) and visual soundness for wholesale mandis. Grade A / URS criteria are intentionally marked unconfigured to preserve official standard integrity.
3. **NHB Export – Nasik / Saurashtra / Bellary / Poona (`nhb_nasik`):** Min diameter 20 mm, decay $\le 2\%$, sprout $0\%$.
4. **NHB Export – Bangalore (Rose Variety) (`nhb_bangalore`):** Min diameter 15 mm, decay $\le 2\%$, sprout $0\%$.
5. **NHB Export – Krishnapuram (`nhb_krishnapuram`):** Min diameter 15 mm, decay $\le 2\%$, sprout $0\%$.

### Explainable Grading Outcomes
The system never issues a black-box grade. Instead, it provides:
- **Grade A / URS Lot Percentages:** Derived transparently onion-by-onion under the configured procurement profile.
- **Criteria Unavailability Notice:** For official standards lacking official Grade A / URS definitions, the engine explicitly reports *"Grade A / URS calculation unavailable"* rather than fabricating numbers.
- **Meets evaluated criteria (Manual verification required):** Surface indicators pass, but manual inspection is required for internal rot and weight verification.
- **Does not meet evaluated criteria:** Exceeds allowable limits for decay, sprouting, or double-splits.
- **Insufficient data for complete regulatory grading:** Returned when image conditions prevent sound evaluation.

---

## 7. Installation & Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12 (Python 3.12 recommended)
- Git (optional)

### Setup Instructions

1. **Clone or Navigate to Directory:**
   ```bash
   cd C:\Users\Bhavya\.gemini\antigravity\scratch\onion-quality-ai
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify Model File:**
   Ensure `model/best.pt` is present (approx 5.2 MB).

---

## 8. Running the Application

### Option A: Standard Launcher (Recommended)
```bash
python run.py
```

### Option B: Direct Uvicorn Command
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Once started:
- Open your browser at: **`http://127.0.0.1:8000`**
- Interactive Swagger API docs: **`http://127.0.0.1:8000/docs`**

---

## 9. API Reference

### Health & RAM Telemetry
```http
GET /health
```
**Response:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "classes": ["double_split", "onion", "rotten", "sprout"],
  "ram_usage_mb": 233.32,
  "ram_target_mb": 500.0,
  "ram_within_target": true
}
```

### Analyze Onion Lot
```http
POST /analyze
Content-Type: multipart/form-data
```
**Parameters:**
- `image`: Image file (JPEG/PNG, max 25 MB)
- `standard`: `local_market` | `nhb_nasik` | `nhb_bangalore` | `nhb_krishnapuram`
- `conf_threshold`: Detection threshold (default: `0.25`)
- `enhance_image`: Mild normalization boolean (default: `false`)
- `calibration_enabled`: Physical calibration boolean (default: `false`)
- `reference_object_diameter_mm`: Optional float
- `reference_object_pixels`: Optional float

**Example Response:**
```json
{
  "status": "success",
  "total_onions": 11,
  "visible_defects": 0,
  "defect_indicator_percent": 0.0,
  "size_distribution": {
    "large": 4,
    "medium": 4,
    "small": 3
  },
  "onions": [
    {
      "onion_id": 1,
      "width_pixels": 213.3,
      "height_pixels": 211.3,
      "diameter_pixels": 213.3,
      "equivalent_diameter_pixels": 239.5,
      "approximate_size_category": "Large",
      "rotten": false,
      "sprout": false,
      "double_split": false,
      "confidence": 0.89,
      "status": "Sound",
      "explanation": "Sound onion: No visible surface decay, sprouting, or splitting detected."
    }
  ],
  "lot_statistics": {
    "total_onions": 11,
    "sound_onions": 11,
    "defective_onions": 0,
    "rotten_count": 0,
    "sprout_count": 0,
    "double_split_count": 0,
    "defect_indicator_percent": 0.0,
    "decay_indicator_percent": 0.0
  },
  "assessment": {
    "standard_id": "nhb_nasik",
    "assessment_status": "Meets evaluated criteria",
    "regulatory_disclaimer": "Weight-based regulatory criteria require lot weight data or integration with a weighing system."
  },
  "memory_telemetry": {
    "initial_ram_mb": 233.5,
    "final_ram_mb": 383.42,
    "within_target": true
  }
}
```

---

## 10. Automated Tests & RAM Verification

Run the test suites:
```bash
python tests/test_pipeline.py
python tests/test_grading_engine.py
```

### Covered Test Cases:
**1. Pipeline & Core Vision Suite (`test_pipeline.py` - 9 tests):**
1. `test_01_model_loaded_once`: Verifies singleton instance reuse.
2. `test_02_ram_target_compliance`: Asserts process memory is strictly $< 500\text{ MB}$.
3. `test_03_no_marker_sample_analysis`: Tests inference on normal lots without markers.
4. `test_04_defective_lot_analysis`: Tests rotten bulb detection and standards failure.
5. `test_05_no_onions_empty_image`: Tests empty/black image handling.
6. `test_06_very_large_image_resizing`: Tests automatic downsampling of 3200x3200px images.
7. `test_07_invalid_image_handling`: Tests non-image and corrupted byte rejection.
8. `test_08_calibrated_mode_b`: Tests physical millimeter calibration calculation.
9. `test_09_rules_engine_standards`: Unit tests rules engine logic across standards.

**2. SIH Grading Engine Suite (`test_grading_engine.py` - 7 tests):**
1. `test_01_unconfigured_standard_behavior`: Confirms official standards report unavailable rather than fabricating Grade A/URS numbers.
2. `test_02_sample1_good_lot_grading`: Verifies Grade A classification on clean lots with sound single bulbs.
3. `test_03_sample2_rotten_lot_grading`: Verifies Defective / Reject classification on decay and sprouting.
4. `test_04_sample3_multilot_grading`: Tests mixed multi-lot grading and percentage totals.
5. `test_05_custom_uploads_jpeg_png`: Tests synthetic image buffers and format support.
6. `test_06_ram_limit_maintained`: Verifies RAM remains $< 500\text{ MB}$ after grading computations.
7. `test_07_no_onions_detected_grading`: Verifies graceful empty-image handling with prompt to upload clearer photo.

---

## 11. Important Scientific Limitations

1. **RGB Surface Information:** Ordinary RGB cameras capture surface reflections only. Internal rot, heart rot, and black mold deep within the scales cannot be detected.
2. **Approximate Sizing:** Physical diameter in millimeters requires camera calibration or a known reference marker. Without calibration, size is reported as approximate image-based pixels.
3. **Count vs. Weight:** Official regulatory grading uses defect percentages calculated by lot weight. Visual indicators represent count ratios and serve as preliminary screening.
4. **No False Claims:** This system does NOT replace government mandi inspectors or certified laboratory tests. Regulatory decisions require human verification.
5. **Dataset Scope:** Current model metrics reflect the research validation dataset (Precision 0.704, Recall 0.647) and should not be interpreted as universal 100% field accuracy under arbitrary lighting or heavy occlusion.

---

## 12. Future Extensions (Roadmap)

- **NIR & Hyperspectral Imaging:** For subsurface spectral absorption and non-destructive internal rot detection.
- **Weighbridge & Belt Scale Integration:** Pairing visual counts with load-cell weight sensors for automated weight-percentage calculation.
- **ONNX Runtime / OpenVINO / TFLite Quantization:** Further reducing CPU inference latency to $< 50\text{ ms}$ on edge Raspberry Pi / Jetson devices.
- **Conveyor Multi-Frame Video Tracking:** ByteTrack integration for continuous belt inspection at packhouse intake.
