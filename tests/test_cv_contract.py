"""Phase 0 contract tests: no camera, MediaPipe, or network required."""

from __future__ import annotations

import unittest

from cv import CONTEXT_MODES, build_result, get_current_frame_result, validate_result


class CvContractTests(unittest.TestCase):
    def test_public_entry_point_returns_the_full_websocket_contract(self) -> None:
        result = get_current_frame_result("city")

        self.assertEqual(
            set(result),
            {
                "timestamp",
                "risk_score",
                "trend_slope",
                "naive_score",
                "signals",
                "signal_quality",
                "calibration",
                "alert",
                "context_mode",
            },
        )
        self.assertEqual(set(result["signals"]), {"perclos", "head_pose", "hand_zone", "yawn"})
        self.assertEqual(
            set(result["signal_quality"]),
            {"face_detected", "hands_detected", "lighting_ok"},
        )
        self.assertEqual(set(result["calibration"]), {"in_progress", "seconds_remaining"})
        self.assertEqual(
            set(result["alert"]),
            {"active", "severity", "reason", "time_saved_seconds"},
        )
        validate_result(result)

    def test_every_frontend_context_mode_is_preserved(self) -> None:
        for context_mode in sorted(CONTEXT_MODES):
            with self.subTest(context_mode=context_mode):
                result = get_current_frame_result(context_mode)

                self.assertEqual(result["context_mode"], context_mode)
                validate_result(result)

    def test_invalid_context_mode_is_rejected_at_the_module_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported context mode"):
            get_current_frame_result("rain")

    def test_schema_validator_rejects_missing_or_out_of_range_data(self) -> None:
        missing_risk_score = build_result(timestamp=1.0)
        del missing_risk_score["risk_score"]
        with self.assertRaisesRegex(ValueError, "Schema keys mismatch"):
            validate_result(missing_risk_score)

        invalid_signal_score = build_result(timestamp=1.0)
        invalid_signal_score["signals"]["perclos"] = 100.1
        with self.assertRaisesRegex(ValueError, "signals.perclos"):
            validate_result(invalid_signal_score)


if __name__ == "__main__":
    unittest.main()
