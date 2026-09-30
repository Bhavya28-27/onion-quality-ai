import os
import sys
import unittest
import numpy as np
import cv2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.inference import analyze_onion_image, get_model, get_current_ram_mb
from backend.grading_engine import GradingEngine


class TestSIHGradingEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.model = get_model()
        cls.engine = GradingEngine()
        cls.samples_dir = os.path.join(PROJECT_ROOT, "sample_images")

    def test_01_unconfigured_standard_behavior(self):
        """Verify that when standard has unconfigured Grade A/URS criteria, it does NOT fabricate numbers."""
        sample_path = os.path.join(self.samples_dir, "sample_lot_1.jpeg")
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        res = analyze_onion_image(img_bytes, standard_id="local_market")
        self.assertIsNotNone(res.grading)
        self.assertFalse(res.grading.is_configured, "local_market should NOT have Grade A/URS configured.")
        self.assertEqual(res.grading.status_message, "Grade A / URS calculation unavailable")
        self.assertIn("This grading profile does not currently contain Grade A / URS criteria.", res.grading.unavailability_reason)
        self.assertGreater(len(res.grading.missing_criteria), 0, "Must explicitly list missing criteria.")
        self.assertEqual(res.grading.grade_a_count, 0)
        self.assertEqual(res.grading.urs_count, 0)

    def test_02_sample1_good_lot_grading(self):
        """Verify Sample 1 (Good lot) under configured procurement standard."""
        sample_path = os.path.join(self.samples_dir, "sample_lot_1.jpeg")
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        res = analyze_onion_image(img_bytes, standard_id="procurement_trial")
        self.assertTrue(res.grading.is_configured)
        self.assertEqual(res.grading.status_message, "Grading completed")
        self.assertEqual(res.grading.total_onions_assessed, res.total_onions)

        # Sample 1 has 11 onions, 0 rotten, 0 sprouted
        self.assertEqual(res.grading.defective_count, 0)
        self.assertEqual(res.grading.defective_percentage, 0.0)
        self.assertGreater(res.grading.grade_a_count, 0)
        # Sum of Grade A + URS + Defective must equal total
        self.assertEqual(
            res.grading.grade_a_count + res.grading.urs_count + res.grading.defective_count,
            res.total_onions
        )
        # Check individual onion grading records
        for og in res.grading.onion_gradings:
            self.assertIn(og.grade_category, ["Grade A", "URS", "Defective / Reject", "Undersized", "Insufficient data"])
            self.assertTrue(len(og.reason) > 5)

    def test_03_sample2_rotten_lot_grading(self):
        """Verify Sample 2 (Rotten lot) under configured procurement standard."""
        sample_path = os.path.join(self.samples_dir, "sample_lot_2_rotten.jpeg")
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        res = analyze_onion_image(img_bytes, standard_id="procurement_trial")
        self.assertTrue(res.grading.is_configured)
        self.assertGreater(res.grading.defective_count, 0, "Must classify rotten bulbs as Defective / Reject.")
        self.assertEqual(res.grading.defective_count, res.lot_statistics.rotten_count)
        self.assertAlmostEqual(res.grading.defective_percentage, res.lot_statistics.decay_indicator_percent, places=1)

    def test_04_sample3_multilot_grading(self):
        """Verify Sample 3 (Multi-lot) under configured procurement standard."""
        sample_path = os.path.join(self.samples_dir, "sample_lot_3.jpg")
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        res = analyze_onion_image(img_bytes, standard_id="procurement_trial")
        self.assertTrue(res.grading.is_configured)
        self.assertGreater(res.grading.total_onions_assessed, 0)

    def test_05_custom_uploads_jpeg_png(self):
        """Verify custom synthetic JPEG and PNG uploads."""
        # JPEG
        img = np.full((400, 400, 3), 180, dtype=np.uint8)
        cv2.circle(img, (200, 200), 80, (40, 80, 160), -1)
        _, buf_jpg = cv2.imencode(".jpg", img)
        res_jpg = analyze_onion_image(buf_jpg.tobytes(), standard_id="procurement_trial")
        self.assertEqual(res_jpg.status, "success")

        # PNG
        _, buf_png = cv2.imencode(".png", img)
        res_png = analyze_onion_image(buf_png.tobytes(), standard_id="procurement_trial")
        self.assertEqual(res_png.status, "success")

    def test_06_ram_limit_maintained(self):
        """Verify process RAM is still well below 500 MB after grading calculations."""
        ram_mb = get_current_ram_mb()
        self.assertLess(ram_mb, 500.0, f"RAM {ram_mb} MB exceeds target of 500 MB.")

    def test_07_no_onions_detected_grading(self):
        """Verify 0 onions detected case under configured procurement standard."""
        blank = np.zeros((400, 400, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", blank)
        res = analyze_onion_image(buf.tobytes(), standard_id="procurement_trial")
        self.assertEqual(res.grading.status_message, "No onions detected")
        self.assertEqual(res.grading.unavailability_reason, "Try uploading a clearer image with onions clearly visible.")
        self.assertEqual(res.grading.total_onions_assessed, 0)


if __name__ == "__main__":
    unittest.main()
