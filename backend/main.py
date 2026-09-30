import os
import gc
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .inference import get_model, analyze_onion_image, get_current_ram_mb, CLASS_MAPPING
from .rules_engine import RulesEngine
from .models import AnalyzeResponse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
SAMPLES_DIR = os.path.join(BASE_DIR, "sample_images")
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB max upload to prevent OOM
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load model once on startup to avoid request-time latency and duplicate memory
    print("[Onion Quality AI] Pre-loading lightweight YOLO model on startup...")
    get_model()
    ram_mb = get_current_ram_mb()
    print(f"[Onion Quality AI] Model loaded. Current RAM usage: {ram_mb:.2f} MB (Target: < 500 MB)")
    yield
    print("[Onion Quality AI] Shutting down application...")
    gc.collect()


app = FastAPI(
    title="Onion Quality AI",
    description="AI-assisted onion quality inspection and standards-based assessment system",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local cross-origin development if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint showing model status and real-time RAM usage."""
    ram = get_current_ram_mb()
    return {
        "status": "ok",
        "model_loaded": True,
        "classes": list(CLASS_MAPPING.values()),
        "ram_usage_mb": ram,
        "ram_target_mb": 500.0,
        "ram_within_target": ram < 500.0
    }


@app.get("/standards")
def list_standards():
    """Returns the list of available grading standards."""
    engine = RulesEngine()
    return engine.get_standards_list()


@app.get("/samples")
def list_sample_images():
    """Returns sample image names available for quick testing."""
    if not os.path.exists(SAMPLES_DIR):
        return []
    files = [
        f for f in os.listdir(SAMPLES_DIR)
        if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
    ]
    return files


@app.get("/samples/{filename}")
def get_sample_image(filename: str):
    """Serves a sample image file for preview or testing."""
    safe_name = os.path.basename(filename)
    file_path = os.path.join(SAMPLES_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Sample image not found.")
    return FileResponse(file_path)


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    image: UploadFile = File(..., description="Onion lot RGB image (JPEG or PNG)"),
    standard: str = Form("local_market", description="Grading standard ID"),
    conf_threshold: float = Form(0.25, description="YOLO detection confidence threshold"),
    enhance_image: bool = Form(False, description="Enable mild image normalization"),
    calibration_enabled: bool = Form(False, description="Enable physical size calibration"),
    mm_per_pixel: Optional[float] = Form(None, description="Direct mm/pixel scale factor"),
    reference_object_diameter_mm: Optional[float] = Form(None, description="Known reference object mm"),
    reference_object_pixels: Optional[float] = Form(None, description="Measured reference object pixels")
):
    """
    Main analysis endpoint. Analyzes normal onion lot photographs without mandatory markers.
    Processes one image at a time to ensure RAM stays below 500 MB.
    """
    # 1. Validate file extension
    ext = os.path.splitext(image.filename)[1].lower() if image.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Only JPEG and PNG images are allowed."
        )

    # 2. Read image bytes with size limit guard
    contents = await image.read()
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded image file is empty."
        )
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image file exceeds maximum allowable limit of {MAX_UPLOAD_SIZE // (1024*1024)} MB."
        )

    # 3. Calculate mm_per_pixel if reference object was supplied
    effective_scale = mm_per_pixel
    if calibration_enabled:
        if reference_object_diameter_mm and reference_object_pixels and reference_object_pixels > 0:
            effective_scale = reference_object_diameter_mm / reference_object_pixels

    # 4. Run pipeline
    try:
        response = analyze_onion_image(
            image_bytes=contents,
            standard_id=standard,
            conf_threshold=conf_threshold,
            enhance_image=enhance_image,
            calibration_enabled=calibration_enabled,
            mm_per_pixel=effective_scale
        )
        return response
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image processing error: {str(ve)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal inference failure: {str(e)}"
        )
    finally:
        del contents
        gc.collect()


# Serve frontend static assets
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
