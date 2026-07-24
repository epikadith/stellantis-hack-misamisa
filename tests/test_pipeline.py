"""End-to-end Person 1 pipeline tests with synthetic signals and frames."""

from __future__ import annotations

import unittest

import numpy as np

from cv.calibration import CalibrationEngine
from cv.pipeline import RiskPipeline
from cv.schema import validate_result
from cv.trajectory import TrajectoryAnalyzer, TrajectoryConfig


def _signals(value: float) -> dict[str, float]:
    return {"perclos": value, "head_pose": value, "hand_zone": value, "yawn": value}


class _UnavailableCapture:
    def isOpened(self) -> bool:
        return False

    def release(self) -> None:
        pass


class PipelineTests(unittest.TestCase):
    def test_synthetic_signals_flow_through_fusion_trajectory_and_contract(self) -> None:
        pipeline = RiskPipeline(
            trajectory=TrajectoryAnalyzer(TrajectoryConfig(lookahead_seconds=3.0)),
        )
        try:
            pipeline.process_signals(_signals(20.0), timestamp=0.0)
            pipeline.process_signals(_signals(30.0), timestamp=1.0)
            result = pipeline.process_signals(_signals(40.0), timestamp=2.0)

            validate_result(result)
            self.assertEqual(result["risk_score"], 40.0)
            self.assertEqual(result["naive_score"], 40.0)
            self.assertTrue(result["alert"]["active"])
            self.assertEqual(result["alert"]["severity"], "amber")
            self.assertAlmostEqual(result["alert"]["time_saved_seconds"], 3.0)
            self.assertIn("Predictive alert", result["alert"]["reason"])
        finally:
            pipeline.close()

    def test_calibration_status_and_thresholds_are_exposed_in_live_result(self) -> None:
        pipeline = RiskPipeline(calibration=CalibrationEngine(duration_seconds=2.0))
        try:
            pipeline.start_calibration(timestamp=0.0)
            calibrating = pipeline.process_signals(_signals(10.0), timestamp=1.0)
            self.assertEqual(calibrating["calibration"], {"in_progress": True, "seconds_remaining": 1.0})

            completed = pipeline.process_signals(_signals(10.0), timestamp=2.0)
            self.assertEqual(completed["calibration"], {"in_progress": False, "seconds_remaining": 0.0})
            self.assertEqual(pipeline.calibration.get_thresholds(timestamp=2.0)["perclos"], 14.0)
            validate_result(completed)
        finally:
            pipeline.close()

    def test_context_mode_changes_result_and_is_returned_to_frontend(self) -> None:
        city = RiskPipeline()
        highway = RiskPipeline()
        night = RiskPipeline()
        try:
            city_result = city.process_signals(_signals(50.0), timestamp=0.0)
            highway.set_context_mode("highway")
            highway_result = highway.process_signals(_signals(50.0), timestamp=0.0)
            night.set_context_mode("night")
            night_result = night.process_signals(_signals(50.0), timestamp=0.0)

            self.assertEqual(city_result["context_mode"], "city")
            self.assertEqual(highway_result["context_mode"], "highway")
            self.assertEqual(night_result["context_mode"], "night")
            self.assertLess(highway_result["risk_score"], city_result["risk_score"])
            self.assertGreater(night_result["risk_score"], city_result["risk_score"])
        finally:
            city.close()
            highway.close()
            night.close()

    def test_unavailable_camera_returns_a_safe_schema_valid_result(self) -> None:
        pipeline = RiskPipeline(capture_factory=lambda _: _UnavailableCapture())
        try:
            result = pipeline.get_current_frame_result("night")
            validate_result(result)
            self.assertEqual(result["context_mode"], "night")
            self.assertFalse(result["signal_quality"]["face_detected"])
        finally:
            pipeline.close()

    def test_real_mediapipe_blank_frame_path_is_schema_valid(self) -> None:
        pipeline = RiskPipeline()
        try:
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            result = pipeline.process_frame(frame, timestamp=0.0)

            validate_result(result)
            self.assertFalse(result["signal_quality"]["face_detected"])
            self.assertFalse(result["signal_quality"]["hands_detected"])
            self.assertFalse(result["signal_quality"]["lighting_ok"])
        finally:
            pipeline.close()


if __name__ == "__main__":
    unittest.main()
