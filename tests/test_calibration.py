"""Deterministic tests for per-driver calibration."""

from __future__ import annotations

import unittest

from cv.calibration import CalibrationEngine, CalibrationState


def _signals(value: float) -> dict[str, float]:
    return {
        "perclos": value,
        "head_pose": value + 1.0,
        "hand_zone": value + 2.0,
        "yawn": value + 3.0,
    }


class CalibrationEngineTests(unittest.TestCase):
    def test_state_machine_and_threshold_baselines(self) -> None:
        engine = CalibrationEngine(duration_seconds=10.0, threshold_multiplier=1.4)

        self.assertEqual(engine.state, CalibrationState.IDLE)
        self.assertEqual(engine.status(timestamp=0.0), {"in_progress": False, "seconds_remaining": 0.0})
        engine.start(timestamp=0.0)
        engine.push_signals(_signals(10.0), timestamp=1.0)
        engine.push_signals(_signals(20.0), timestamp=4.0)

        self.assertTrue(engine.is_calibrating(timestamp=5.0))
        self.assertEqual(engine.status(timestamp=5.0), {"in_progress": True, "seconds_remaining": 5.0})
        self.assertEqual(engine.get_thresholds(timestamp=5.0), {})

        self.assertFalse(engine.is_calibrating(timestamp=10.0))
        self.assertEqual(engine.state, CalibrationState.CALIBRATED)
        thresholds = engine.get_thresholds(timestamp=10.0)
        self.assertAlmostEqual(thresholds["perclos"], 21.0)
        self.assertAlmostEqual(thresholds["head_pose"], 22.4)
        self.assertAlmostEqual(thresholds["hand_zone"], 23.8)
        self.assertAlmostEqual(thresholds["yawn"], 25.2)

    def test_thresholds_are_capped_to_the_shared_score_range(self) -> None:
        engine = CalibrationEngine(duration_seconds=1.0)
        engine.start(timestamp=0.0)
        engine.push_signals(_signals(97.0), timestamp=0.5)

        thresholds = engine.get_thresholds(timestamp=1.0)
        self.assertEqual(thresholds, {"perclos": 100.0, "head_pose": 100.0, "hand_zone": 100.0, "yawn": 100.0})

    def test_restart_discards_previous_driver_baseline(self) -> None:
        engine = CalibrationEngine(duration_seconds=5.0)
        engine.start(timestamp=0.0)
        engine.push_signals(_signals(50.0), timestamp=1.0)
        engine.start(timestamp=2.0)
        engine.push_signals(_signals(10.0), timestamp=3.0)

        self.assertEqual(engine.get_thresholds(timestamp=7.0)["perclos"], 14.0)

    def test_invalid_signal_shapes_and_time_order_are_rejected(self) -> None:
        engine = CalibrationEngine(duration_seconds=10.0)
        engine.start(timestamp=0.0)
        with self.assertRaisesRegex(ValueError, "exactly"):
            engine.push_signals({"perclos": 0.0}, timestamp=1.0)
        with self.assertRaisesRegex(ValueError, "signals.yawn"):
            engine.push_signals({**_signals(10.0), "yawn": 101.0}, timestamp=1.0)

        engine.push_signals(_signals(10.0), timestamp=2.0)
        with self.assertRaisesRegex(ValueError, "non-decreasing"):
            engine.push_signals(_signals(10.0), timestamp=1.0)

    def test_reset_returns_to_idle(self) -> None:
        engine = CalibrationEngine(duration_seconds=10.0)
        engine.start(timestamp=0.0)
        engine.push_signals(_signals(10.0), timestamp=1.0)
        engine.reset()

        self.assertEqual(engine.state, CalibrationState.IDLE)
        self.assertEqual(engine.get_thresholds(timestamp=2.0), {})
        self.assertEqual(engine.status(timestamp=2.0), {"in_progress": False, "seconds_remaining": 0.0})


if __name__ == "__main__":
    unittest.main()
