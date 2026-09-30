import os
import sys
import unittest
import numpy as np
import cv2
import psutil

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.inference import analyze_onion_image, get_model, get_current_ram_mb
from backend.rules_engine import RulesEngine
from backend.models import LotStatistics, SizeDistribution


class TestOnionQualityAI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n[SETUP] Initializing model singleton...")
        cls.model = get_model()
        cls.engine = RulesEngine()
        cls.samples_dir = os.path.join(PROJECT_ROOT, "sample_images")

    def test_01_model_loaded_once(self):
        """Verify that model loading returns the exact same singleton instance."""
        m1 = get_model()
        m2 = get_model()
        self.assertIs(m1, m2, "Model instance must be a singleton loaded only once.")

    def test_02_ram_target_compliance(self):
        """Verify that process RAM stays well below the 500 MB threshold."""
        ram_mb = get_current_ram_mb()
        print(f"\n[RAM CHECK] Current Process RAM: {ram_mb:.2f} MB (Target: < 500 MB)")
        self.assertLess(ram_mb, 500.0, f"Process RAM {ram_mb} MB exceeds target of 500 MB.")

    def test_03_no_marker_sample_analysis(self):
        """Test inference on a normal onion lot image WITHOUT an ArUco or reference marker."""
        sample_path = os.path.join(self.samples_dir, "sample_lot_1.jpeg")
        self.assertTrue(os.path.exists(sample_path), f"Sample image missing at {sample_path}")

        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        response = analyze_onion_image(
            image_bytes=img_bytes,
            standard_id="local_market",
            conf_threshold=0.25,
            calibration_enabled=False  # No marker, Mode A
        )

        self.assertEqual(response.status, "success")
        self.assertGreater(response.total_onions, 0, "Should detect onions in sample lot 1.")
        self.assertFalse(response.calibration_used, "Should operate in uncalibrated Mode A.")
        self.assertIsNotNone(response.annotated_image, "Must return base64 annotated image.")

        # Check onion records have required explainability fields
        first_onion = response.onions[0]
        self.assertIn("onion_id", first_onion.model_dump())
        self.assertIn("approximate_size_category", first_onion.model_dump())
        self.assertIn("explanation", first_onion.model_dump())
        self.assertIn(first_onion.approximate_size_category, ["Large", "Medium", "Small"])

    def test_04_defective_lot_analysis(self):
        """Test inference on lot with rotten / defect onions."""
        sample_path = os.path.join(self.samples_dir, "sample_lot_2_rotten.jpeg")
        self.assertTrue(os.path.exists(sample_path), f"Sample image missing at {sample_path}")

        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        response = analyze_onion_image(
            image_bytes=img_bytes,
            standard_id="nhb_nasik",
            conf_threshold=0.25
        )

        self.assertEqual(response.status, "success")
        self.assertGreater(response.total_onions, 0)
        self.assertGreater(response.lot_statistics.rotten_count, 0, "Should detect rotten onions.")
        self.assertGreater(response.lot_statistics.decay_indicator_percent, 0.0)

        # Nasik standard allows max 2% decay, so this defective lot should fail
        self.assertEqual(
            response.assessment.assessment_status,
            "Does not meet evaluated criteria"
        )
        self.assertTrue(any("decay" in r.lower() or "exceeds" in r.lower() for r in response.assessment.reasons))

    def test_05_no_onions_empty_image(self):
        """Verify pipeline handles an image with zero onions cleanly without crashing."""
        # Create a blank black image
        blank = np.zeros((400, 400, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", blank)
        img_bytes = buf.tobytes()

        response = analyze_onion_image(
            image_bytes=img_bytes,
            standard_id="local_market"
        )

        self.assertEqual(response.status, "success")
        self.assertEqual(response.total_onions, 0)
        self.assertEqual(response.lot_statistics.sound_onions, 0)
        self.assertEqual(
            response.assessment.assessment_status,
            "Insufficient data for complete regulatory grading"
        )

    def test_06_very_large_image_resizing(self):
        """Test that huge images (e.g. 3500x3500) are gracefully resized without memory spike."""
        # Create a synthetic large image
        large_img = np.full((3200, 3200, 3), 200, dtype=np.uint8)
        # Draw a synthetic circle representing an onion
        cv2.circle(large_img, (1600, 1600), 400, (60, 80, 150), -1)
        _, buf = cv2.imencode(".jpg", large_img)
        img_bytes = buf.tobytes()
        del large_img

        response = analyze_onion_image(
            image_bytes=img_bytes,
            standard_id="local_market"
        )
        self.assertEqual(response.status, "success")
        self.assertTrue(response.memory_telemetry["within_target"])

    def test_07_invalid_image_handling(self):
        """Verify that corrupted or non-image bytes raise ValueError cleanly."""
        corrupted_bytes = b"This is random non-image text data"
        with self.assertRaises(ValueError):
            analyze_onion_image(image_bytes=corrupted_bytes)

    def test_08_calibrated_mode_b(self):
        """Verify optional Mode B physical size conversion when reference scale is provided."""
        sample_path = os.path.join(self.samples_dir, "sample_lot_1.jpeg")
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        # Suppose 0.35 mm per pixel
        response = analyze_onion_image(
            image_bytes=img_bytes,
            standard_id="nhb_nasik",
            calibration_enabled=True,
            mm_per_pixel=0.35
        )

        self.assertTrue(response.calibration_used)
        self.assertIsNotNone(response.onions[0].physical_diameter_mm)
        self.assertGreater(response.onions[0].physical_diameter_mm, 0.0)

    def test_09_rules_engine_standards(self):
        """Test rules engine logic for various standards."""
        # Case A: Lot with 0% defects
        clean_stats = LotStatistics(
            total_onions=10,
            sound_onions=10,
            defective_onions=0,
            rotten_count=0,
            sprout_count=0,
            double_split_count=0,
            unassigned_defects=0,
            defect_indicator_percent=0.0,
            decay_indicator_percent=0.0,
            sprout_indicator_percent=0.0,
            double_split_indicator_percent=0.0,
            size_distribution=SizeDistribution(large=4, medium=4, small=2),
            avg_approx_diameter_pixels=150.0,
            min_approx_diameter_pixels=80.0,
            max_approx_diameter_pixels=220.0
        )

        res_clean = self.engine.evaluate(clean_stats, standard_id="nhb_nasik")
        self.assertEqual(res_clean.assessment_status, "Meets evaluated criteria")

        # Case B: Lot with 5% decay (fails NHB Nasik export max 2%)
        decay_stats = LotStatistics(
            total_onions=20,
            sound_onions=19,
            defective_onions=1,
            rotten_count=1,
            sprout_count=0,
            double_split_count=0,
            unassigned_defects=0,
            defect_indicator_percent=5.0,
            decay_indicator_percent=5.0,
            sprout_indicator_percent=0.0,
            double_split_indicator_percent=0.0,
            size_distribution=SizeDistribution(large=8, medium=8, small=4),
            avg_approx_diameter_pixels=150.0,
            min_approx_diameter_pixels=80.0,
            max_approx_diameter_pixels=220.0
        )

        res_decay = self.engine.evaluate(decay_stats, standard_id="nhb_nasik")
        self.assertEqual(res_decay.assessment_status, "Does not meet evaluated criteria")


if __name__ == "__main__":
    unittest.main()
