"""Shared Person 1 -> Person 2 -> Person 3 risk-message contract.

All numeric risk and signal values use the inclusive 0--100 range.  A
trajectory slope is measured in risk-score points per second.  This module
intentionally has no OpenCV or MediaPipe dependency so it is usable by unit
tests and by the backend's partial-data fallback path.
"""

from __future__ import annotations

from copy import deepcopy
from numbers import Real
from time import time
from typing import Any, Final

CONTEXT_MODES: Final[frozenset[str]] = frozenset({"city", "highway", "night"})
SIGNAL_NAMES: Final[tuple[str, ...]] = ("perclos", "head_pose", "hand_zone", "yawn")
SEVERITIES: Final[frozenset[str]] = frozenset({"none", "amber", "red"})

DEFAULT_RESULT: Final[dict[str, Any]] = {
    "timestamp": 0.0,
    "risk_score": 0.0,
    "trend_slope": 0.0,
    "naive_score": 0.0,
    "signals": {name: 0.0 for name in SIGNAL_NAMES},
    "signal_quality": {
        "face_detected": False,
        "hands_detected": False,
        "lighting_ok": False,
    },
    "calibration": {
        "in_progress": False,
        "seconds_remaining": 0.0,
    },
    "alert": {
        "active": False,
        "severity": "none",
        "reason": "",
        "time_saved_seconds": 0.0,
    },
    "context_mode": "city",
}


def build_result(context_mode: str = "city", *, timestamp: float | None = None) -> dict[str, Any]:
    """Return a new schema-valid risk message with conservative defaults.

    ``context_mode`` is validated at the module boundary to prevent a value
    that cannot be represented by the frontend context selector from entering
    the WebSocket stream.
    """
    if context_mode not in CONTEXT_MODES:
        raise ValueError(
            f"Unsupported context mode {context_mode!r}; expected one of "
            f"{sorted(CONTEXT_MODES)}."
        )

    result = deepcopy(DEFAULT_RESULT)
    result["timestamp"] = float(time() if timestamp is None else timestamp)
    result["context_mode"] = context_mode
    return result


def validate_result(result: dict[str, Any]) -> None:
    """Raise ``ValueError`` when a message violates the shared contract."""
    if not isinstance(result, dict):
        raise ValueError("Risk result must be a dictionary.")

    required = set(DEFAULT_RESULT)
    missing = required - set(result)
    unexpected = set(result) - required
    if missing or unexpected:
        raise ValueError(f"Schema keys mismatch; missing={missing}, unexpected={unexpected}.")

    _require_number(result["timestamp"], "timestamp")
    _require_score(result["risk_score"], "risk_score")
    _require_number(result["trend_slope"], "trend_slope")
    _require_score(result["naive_score"], "naive_score")

    _validate_exact_mapping(result["signals"], SIGNAL_NAMES, "signals")
    for name, value in result["signals"].items():
        _require_score(value, f"signals.{name}")

    quality_names = ("face_detected", "hands_detected", "lighting_ok")
    _validate_exact_mapping(result["signal_quality"], quality_names, "signal_quality")
    for name, value in result["signal_quality"].items():
        if not isinstance(value, bool):
            raise ValueError(f"signal_quality.{name} must be a bool.")

    _validate_exact_mapping(result["calibration"], ("in_progress", "seconds_remaining"), "calibration")
    if not isinstance(result["calibration"]["in_progress"], bool):
        raise ValueError("calibration.in_progress must be a bool.")
    if _require_number(result["calibration"]["seconds_remaining"], "calibration.seconds_remaining") < 0:
        raise ValueError("calibration.seconds_remaining cannot be negative.")

    _validate_exact_mapping(result["alert"], ("active", "severity", "reason", "time_saved_seconds"), "alert")
    if not isinstance(result["alert"]["active"], bool):
        raise ValueError("alert.active must be a bool.")
    if result["alert"]["severity"] not in SEVERITIES:
        raise ValueError(f"alert.severity must be one of {sorted(SEVERITIES)}.")
    if not isinstance(result["alert"]["reason"], str):
        raise ValueError("alert.reason must be a string.")
    if _require_number(result["alert"]["time_saved_seconds"], "alert.time_saved_seconds") < 0:
        raise ValueError("alert.time_saved_seconds cannot be negative.")

    if result["context_mode"] not in CONTEXT_MODES:
        raise ValueError(f"context_mode must be one of {sorted(CONTEXT_MODES)}.")


def _validate_exact_mapping(value: Any, keys: tuple[str, ...], name: str) -> None:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{name} must contain exactly {list(keys)}.")


def _require_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number.")
    return float(value)


def _require_score(value: Any, name: str) -> None:
    numeric_value = _require_number(value, name)
    if not 0.0 <= numeric_value <= 100.0:
        raise ValueError(f"{name} must be between 0 and 100.")
