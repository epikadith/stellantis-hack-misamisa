"""Unit tests for configurable four-signal risk fusion."""

from __future__ import annotations

import unittest

from cv.fusion import FusionWeights, SignalFusionEngine, compute_risk


class FusionTests(unittest.TestCase):
    def test_default_weights_produce_expected_weighted_score(self) -> None:
        risk = compute_risk(perclos=50.0, head_pose=20.0, hand_zone=10.0, yawn=0.0)
        self.assertAlmostEqual(risk, 28.0)

    def test_equal_signal_values_preserve_that_score_across_weights(self) -> None:
        self.assertEqual(compute_risk(50.0, 50.0, 50.0, 50.0), 50.0)

    def test_context_modes_apply_prd_sensitivity(self) -> None:
        fusion = SignalFusionEngine()
        values = {"perclos": 50.0, "head_pose": 50.0, "hand_zone": 50.0, "yawn": 50.0}

        self.assertEqual(fusion.compute_from_signals(values, context_mode="city"), 50.0)
        self.assertEqual(fusion.compute_from_signals(values, context_mode="highway"), 42.5)
        self.assertAlmostEqual(fusion.compute_from_signals(values, context_mode="night"), 57.5)

    def test_calibration_threshold_normalizes_per_driver_signal_levels(self) -> None:
        fusion = SignalFusionEngine()
        values = {"perclos": 25.0, "head_pose": 25.0, "hand_zone": 25.0, "yawn": 25.0}
        thresholds = {"perclos": 25.0, "head_pose": 25.0, "hand_zone": 25.0, "yawn": 25.0}

        self.assertEqual(fusion.compute_from_signals(values, calibration_thresholds=thresholds), 100.0)

    def test_invalid_weights_and_signal_shapes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "sum"):
            FusionWeights(perclos=0.5, head_pose=0.5, hand_zone=0.5, yawn=0.5)
        with self.assertRaisesRegex(ValueError, "exactly"):
            SignalFusionEngine().compute_from_signals({"perclos": 1.0})
        with self.assertRaisesRegex(ValueError, "Unsupported context"):
            SignalFusionEngine().compute_from_signals(
                {"perclos": 0.0, "head_pose": 0.0, "hand_zone": 0.0, "yawn": 0.0},
                context_mode="rain",
            )


if __name__ == "__main__":
    unittest.main()
