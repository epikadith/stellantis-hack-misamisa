"""End-to-end Person 1 pipeline tests with synthetic signals and frames."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from cv.calibration import CalibrationEngine
from cv.pipeline import RiskPipeline
from cv.schema import validate_result
from cv.trajectory import TrajectoryAnalyzer, TrajectoryConfig


def _signals(value: float) -> dict[str, float]:
    return {"perclos": value, "head_pose": value, "hand_zone": value, "yawn": value}


def _landmark(x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


def _mock_face_landmarks() -> list[SimpleNamespace]:
    """A MediaPipe-shaped face with open eyes and a non-yawning mouth."""
    landmarks = [_landmark(0.5, 0.5) for _ in range(400)]
    landmarks[1] = _landmark(0.5, 0.3)
    for index, point in zip(
        (33, 160, 158, 133, 153, 144),
        ((0.30, 0.40), (0.32, 0.38), (0.35, 0.38), (0.38, 0.40), (0.35, 0.42), (0.32, 0.42)),
    ):
        landmarks[index] = _landmark(*point)
    for index, point in zip(
        (362, 385, 387, 263, 373, 380),
        ((0.62, 0.40), (0.64, 0.38), (0.67, 0.38), (0.70, 0.40), (0.67, 0.42), (0.64, 0.42)),
    ):
        landmarks[index] = _landmark(*point)
    landmarks[13] = _landmark(0.5, 0.58)
    landmarks[14] = _landmark(0.5, 0.62)
    landmarks[78] = _landmark(0.4, 0.6)
    landmarks[308] = _landmark(0.6, 0.6)
    return landmarks


class _Detector:
    def __init__(self, result: object) -> None:
        self.result = result

    def process(self, _: object) -> object:
        return self.result


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

    def test_mocked_mediapipe_output_flows_to_the_exact_shared_schema(self) -> None:
        face = SimpleNamespace(multi_face_landmarks=[SimpleNamespace(landmark=_mock_face_landmarks())])
        hand_landmarks = [_landmark(0.05, 0.8) for _ in range(21)]
        hand_landmarks[8] = _landmark(0.51, 0.31)  # phone-near-face zone
        hands = SimpleNamespace(multi_hand_landmarks=[SimpleNamespace(landmark=hand_landmarks)])
        pipeline = RiskPipeline()
        pipeline._face_mesh = _Detector(face)
        pipeline._hands = _Detector(hands)
        try:
            result = pipeline.process_frame(np.full((64, 64, 3), 150, dtype=np.uint8), timestamp=1.0)

            validate_result(result)
            self.assertEqual(result["signals"]["perclos"], 0.0)
            self.assertEqual(result["signals"]["hand_zone"], 100.0)
            self.assertEqual(
                result["signal_quality"],
                {"face_detected": True, "hands_detected": True, "lighting_ok": True},
            )
        finally:
            pipeline.close()

    def test_demo_rising_risk_sequence_alerts_before_naive_crossing(self) -> None:
        pipeline = RiskPipeline(trajectory=TrajectoryAnalyzer(TrajectoryConfig(lookahead_seconds=3.0)))
        try:
            neutral = pipeline.process_signals(_signals(20.0), timestamp=0.0)
            pipeline.process_signals(_signals(40.0), timestamp=1.0)
            predictive = pipeline.process_signals(_signals(60.0), timestamp=2.0)
            naive_crossing = pipeline.process_signals(_signals(70.0), timestamp=3.0)
            pipeline.set_context_mode("night")
            night = pipeline.process_signals(_signals(60.0), timestamp=4.0)

            self.assertFalse(neutral["alert"]["active"])
            self.assertTrue(predictive["alert"]["active"])
            self.assertLess(predictive["naive_score"], 70.0)
            self.assertIn("perclos", predictive["alert"]["reason"])
            self.assertIn("head pose", predictive["alert"]["reason"])
            self.assertEqual(naive_crossing["naive_score"], 70.0)
            self.assertGreater(naive_crossing["alert"]["time_saved_seconds"], 0.0)
            self.assertEqual(night["context_mode"], "night")
            self.assertAlmostEqual(night["risk_score"], 69.0)
        finally:
            pipeline.close()


if __name__ == "__main__":
    unittest.main()
