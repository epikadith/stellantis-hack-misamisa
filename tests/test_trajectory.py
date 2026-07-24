"""Behaviour tests for the PRD's predictive-alert differentiator."""

from __future__ import annotations

import unittest

from cv.trajectory import TrajectoryAnalyzer, TrajectoryConfig


class TrajectoryAnalyzerTests(unittest.TestCase):
    def test_empty_and_single_sample_windows_are_safe(self) -> None:
        analyzer = TrajectoryAnalyzer()

        self.assertEqual(
            analyzer.snapshot(),
            {
                "trend_slope": 0.0,
                "naive_score": 0.0,
                "alert_active": False,
                "time_saved_seconds": 0.0,
            },
        )
        result = analyzer.push(10.0, 35.0)
        self.assertEqual(result["trend_slope"], 0.0)
        self.assertEqual(result["naive_score"], 35.0)
        self.assertFalse(result["alert_active"])

    def test_flat_trend_has_no_predictive_alert(self) -> None:
        analyzer = TrajectoryAnalyzer()
        result = None
        for timestamp in range(5):
            result = analyzer.push(float(timestamp), 40.0)

        assert result is not None
        self.assertAlmostEqual(result["trend_slope"], 0.0, places=9)
        self.assertFalse(result["alert_active"])
        self.assertEqual(result["time_saved_seconds"], 0.0)

    def test_rising_trend_fires_before_naive_threshold_crossing(self) -> None:
        analyzer = TrajectoryAnalyzer(TrajectoryConfig(lookahead_seconds=3.0))
        analyzer.push(0.0, 20.0)
        analyzer.push(1.0, 30.0)
        prediction = analyzer.push(2.0, 40.0)

        self.assertAlmostEqual(prediction["trend_slope"], 10.0, places=9)
        self.assertTrue(prediction["alert_active"])
        self.assertEqual(prediction["naive_score"], 40.0)
        self.assertAlmostEqual(prediction["time_saved_seconds"], 3.0, places=9)

    def test_measured_lead_time_is_retained_when_naive_score_crosses(self) -> None:
        analyzer = TrajectoryAnalyzer(TrajectoryConfig(lookahead_seconds=3.0))
        analyzer.push(0.0, 20.0)
        analyzer.push(1.0, 30.0)
        analyzer.push(2.0, 40.0)  # predictive alert; raw score remains below 70
        raw_crossing = analyzer.push(5.0, 70.0)

        self.assertTrue(raw_crossing["alert_active"])
        self.assertEqual(raw_crossing["naive_score"], 70.0)
        self.assertAlmostEqual(raw_crossing["time_saved_seconds"], 3.0, places=9)

        still_unsafe = analyzer.push(6.0, 80.0)
        self.assertAlmostEqual(still_unsafe["time_saved_seconds"], 3.0, places=9)

    def test_sudden_drop_clears_a_pending_predictive_alert(self) -> None:
        analyzer = TrajectoryAnalyzer(TrajectoryConfig(lookahead_seconds=3.0))
        analyzer.push(0.0, 20.0)
        analyzer.push(1.0, 30.0)
        self.assertTrue(analyzer.push(2.0, 40.0)["alert_active"])

        dropped = analyzer.push(3.0, 10.0)
        self.assertLess(dropped["trend_slope"], 0.0)
        self.assertFalse(dropped["alert_active"])
        self.assertEqual(dropped["time_saved_seconds"], 0.0)

    def test_raw_threshold_crossing_alerts_without_a_predictive_lead(self) -> None:
        analyzer = TrajectoryAnalyzer()
        result = analyzer.push(0.0, 70.0)

        self.assertTrue(result["alert_active"])
        self.assertEqual(result["naive_score"], 70.0)
        self.assertEqual(result["time_saved_seconds"], 0.0)

    def test_rejects_invalid_scores_and_non_monotonic_timestamps(self) -> None:
        analyzer = TrajectoryAnalyzer()
        with self.assertRaisesRegex(ValueError, "risk_score"):
            analyzer.push(0.0, 100.1)

        analyzer.push(1.0, 20.0)
        with self.assertRaisesRegex(ValueError, "strictly greater"):
            analyzer.push(1.0, 30.0)

    def test_configuration_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "threshold"):
            TrajectoryConfig(threshold=0.0)
        with self.assertRaisesRegex(ValueError, "window_size"):
            TrajectoryConfig(window_size=1)
        with self.assertRaisesRegex(ValueError, "min_points"):
            TrajectoryConfig(window_size=5, min_points=6)
        with self.assertRaisesRegex(ValueError, "lookahead_seconds"):
            TrajectoryConfig(lookahead_seconds=0.0)


if __name__ == "__main__":
    unittest.main()
