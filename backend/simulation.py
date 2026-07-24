"""Deterministic, schema-valid risk data used before CV is wired in."""

from __future__ import annotations

import math
from time import time
from typing import Any

from cv.schema import build_result, validate_result


class SimulatedRiskProvider:
    """Produce a repeatable 30-second risk wave for frontend development."""

    def __init__(self, *, period_seconds: float = 30.0, clock: Any = time) -> None:
        if period_seconds <= 0:
            raise ValueError("period_seconds must be positive.")
        self.period_seconds = float(period_seconds)
        self._clock = clock

    def get_frame_data(self, context_mode: str = "city") -> dict[str, Any]:
        timestamp = float(self._clock())
        phase = 2.0 * math.pi * timestamp / self.period_seconds
        risk_score = _clamp(50.0 + 45.0 * math.sin(phase))
        trend_slope = 45.0 * (2.0 * math.pi / self.period_seconds) * math.cos(phase)

        result = build_result(context_mode, timestamp=timestamp)
        result["risk_score"] = risk_score
        result["trend_slope"] = trend_slope
        result["naive_score"] = risk_score
        result["signals"] = {
            "perclos": _clamp(risk_score * 1.10),
            "head_pose": _clamp(risk_score * 0.90),
            "hand_zone": _clamp(risk_score * 0.65),
            "yawn": _clamp(risk_score * 0.45),
        }
        result["signal_quality"] = {
            "face_detected": True,
            "hands_detected": True,
            "lighting_ok": True,
        }
        active = risk_score >= 70.0
        result["alert"] = {
            "active": active,
            "severity": "red" if active else "none",
            "reason": "Simulated risk exceeds the alert threshold." if active else "",
            "time_saved_seconds": 0.0,
        }
        validate_result(result)
        return result


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))
