"""Lazy in-process adapter for the Person 1 CV package."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from numbers import Real
from threading import RLock
from typing import Any, Callable

from cv.schema import CONTEXT_MODES, SEVERITIES, SIGNAL_NAMES, build_result, validate_result

from .simulation import SimulatedRiskProvider


class CVFrameProvider:
    """Read CV frames when available and retain a complete simulated fallback."""

    def __init__(
        self,
        *,
        module_loader: Callable[[str], Any] = import_module,
        simulation: SimulatedRiskProvider | None = None,
    ) -> None:
        self._module_loader = module_loader
        self._simulation = simulation or SimulatedRiskProvider()
        self._module: Any | None = None
        self._load_attempted = False
        self._lock = RLock()

    def get_frame_data(self, context_mode: str = "city") -> dict[str, Any]:
        fallback = self._simulation.get_frame_data(context_mode)
        module = self._get_module()
        if module is None:
            return fallback

        try:
            result = module.get_current_frame_result(context_mode=context_mode)
        except Exception:
            return fallback

        if not _has_live_signal(result):
            return fallback
        return _merge_result(result, fallback)

    def start_calibration(self) -> bool:
        return self._call_control("start_calibration")

    def set_context_mode(self, context_mode: str) -> bool:
        if context_mode not in CONTEXT_MODES:
            raise ValueError(f"Unsupported context mode {context_mode!r}.")
        return self._call_control("set_context_mode", context_mode)

    def close(self) -> bool:
        return self._call_control("close_pipeline")

    def _get_module(self) -> Any | None:
        with self._lock:
            if self._load_attempted:
                return self._module
            self._load_attempted = True
            try:
                self._module = self._module_loader("cv")
            except Exception:
                self._module = None
            return self._module

    def _call_control(self, name: str, *args: Any) -> bool:
        module = self._get_module()
        method = getattr(module, name, None) if module is not None else None
        if not callable(method):
            return False
        try:
            method(*args)
        except Exception:
            return False
        return True


def _has_live_signal(result: Any) -> bool:
    """Treat the CV package's all-false safe camera result as unavailable."""
    if not isinstance(result, dict):
        return False
    quality = result.get("signal_quality")
    return isinstance(quality, dict) and any(quality.get(name) is True for name in quality)


def _merge_result(candidate: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    """Apply only valid CV leaves, preserving simulation for every bad/missing one."""
    merged = deepcopy(fallback)
    if not isinstance(candidate, dict):
        return merged

    for name in ("timestamp", "trend_slope"):
        if _is_number(candidate.get(name)):
            merged[name] = float(candidate[name])
    for name in ("risk_score", "naive_score"):
        if _is_score(candidate.get(name)):
            merged[name] = float(candidate[name])

    _merge_scores(candidate.get("signals"), merged["signals"], SIGNAL_NAMES)
    _merge_bools(candidate.get("signal_quality"), merged["signal_quality"])
    _merge_calibration(candidate.get("calibration"), merged["calibration"])
    _merge_alert(candidate.get("alert"), merged["alert"])
    validate_result(merged)
    return merged


def _merge_scores(candidate: Any, target: dict[str, Any], names: tuple[str, ...]) -> None:
    if not isinstance(candidate, dict):
        return
    for name in names:
        if _is_score(candidate.get(name)):
            target[name] = float(candidate[name])


def _merge_bools(candidate: Any, target: dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        return
    for name in target:
        if isinstance(candidate.get(name), bool):
            target[name] = candidate[name]


def _merge_calibration(candidate: Any, target: dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        return
    if isinstance(candidate.get("in_progress"), bool):
        target["in_progress"] = candidate["in_progress"]
    if _is_non_negative(candidate.get("seconds_remaining")):
        target["seconds_remaining"] = float(candidate["seconds_remaining"])


def _merge_alert(candidate: Any, target: dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        return
    if isinstance(candidate.get("active"), bool):
        target["active"] = candidate["active"]
    if candidate.get("severity") in SEVERITIES:
        target["severity"] = candidate["severity"]
    if isinstance(candidate.get("reason"), str):
        target["reason"] = candidate["reason"]
    if _is_non_negative(candidate.get("time_saved_seconds")):
        target["time_saved_seconds"] = float(candidate["time_saved_seconds"])


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, Real)


def _is_non_negative(value: Any) -> bool:
    return _is_number(value) and float(value) >= 0.0


def _is_score(value: Any) -> bool:
    return _is_number(value) and 0.0 <= float(value) <= 100.0
