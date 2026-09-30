import os
import sys
import numpy as np
import cv2
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.main import app

def run_checks():
    client = TestClient(app)

    # 1. Test Static files
    r_index = client.get('/')
    assert r_index.status_code == 200, "Index page should load with status 200"
    assert 'ONION QUALITY AI' in r_index.text
    assert 'Upload Onion Lot Image' in r_index.text
    assert 'RAM: Measuring' not in r_index.text
    assert 'Important Scientific Limitations & Boundary Conditions' not in r_index.text
    assert 'Limitations &amp; Notes' in r_index.text or 'Limitations & Notes' in r_index.text
    print("[1/5] Index HTML verified with clean redesigned layout.")

    # 2. Test Sample 1
    sample1_path = os.path.join(PROJECT_ROOT, 'sample_images', 'sample_lot_1.jpeg')
    with open(sample1_path, 'rb') as f:
        r1 = client.post('/analyze', files={'image': ('sample_lot_1.jpeg', f, 'image/jpeg')}, data={'standard': 'local_market', 'conf_threshold': 0.25})
    assert r1.status_code == 200
    d1 = r1.json()
    print(f"[2/5] Sample 1 verified: {d1['total_onions']} onions, defect rate: {d1['defect_indicator_percent']}%, status: {d1['assessment']['assessment_status']}")

    # 3. Test Sample 2 (Rotten Lot)
    sample2_path = os.path.join(PROJECT_ROOT, 'sample_images', 'sample_lot_2_rotten.jpeg')
    with open(sample2_path, 'rb') as f:
        r2 = client.post('/analyze', files={'image': ('sample_lot_2_rotten.jpeg', f, 'image/jpeg')}, data={'standard': 'nhb_nasik', 'conf_threshold': 0.25})
    assert r2.status_code == 200
    d2 = r2.json()
    print(f"[3/5] Sample 2 verified: {d2['total_onions']} onions, {d2['lot_statistics']['rotten_count']} rotten, status: {d2['assessment']['assessment_status']}")

    # 4. Test Sample 3 (Multi-Lot)
    sample3_path = os.path.join(PROJECT_ROOT, 'sample_images', 'sample_lot_3.jpg')
    with open(sample3_path, 'rb') as f:
        r3 = client.post('/analyze', files={'image': ('sample_lot_3.jpg', f, 'image/jpeg')}, data={'standard': 'local_market', 'conf_threshold': 0.25})
    assert r3.status_code == 200
    d3 = r3.json()
    print(f"[4/5] Sample 3 verified: {d3['total_onions']} onions, status: {d3['assessment']['assessment_status']}")

    # 5. Test arbitrary user-uploaded image
    user_img = np.full((600, 600, 3), 190, dtype=np.uint8)
    cv2.circle(user_img, (300, 300), 150, (40, 90, 180), -1)
    _, buf = cv2.imencode('.png', user_img)
    r_user = client.post('/analyze', files={'image': ('custom_user_photo.png', buf.tobytes(), 'image/png')}, data={'standard': 'nhb_nasik', 'conf_threshold': 0.25})
    assert r_user.status_code == 200
    print(f"[5/5] Custom user upload verified: HTTP {r_user.status_code}, response status: {r_user.json()['status']}")

    print("\nALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_checks()
