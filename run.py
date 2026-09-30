import sys
import os
import uvicorn

# Ensure the project root is in Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if __name__ == "__main__":
    print("=" * 60)
    print("       ONION QUALITY AI — STARTING APPLICATION")
    print("=" * 60)
    print(" Low-RAM Target: < 500 MB RAM during inference")
    print(" Architecture: YOLO11n CPU + OpenCV (No SAM/SAM2)")
    print(" Standards Engine: NHB Export & Local Wholesale Mandi")
    print(" Mode: No Marker Required (Default Relative Sizing)")
    print("=" * 60)
    print(" Access Web UI at: http://127.0.0.1:8000")
    print("=" * 60)

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False  # Keep false in production to prevent subprocess memory doubling
    )
