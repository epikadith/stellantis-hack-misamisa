"""Bridge browser camera frames into the in-process CV package."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from numbers import Real
from threading import RLock
from typing import Any, Callable

from cv.schema import CONTEXT_MODES, SEVERITIES, SIGNAL_NAMES, build_result, validate_result


class CVFrameProvider:
    """Decode JPEG frames received from the browser and process the latest one."""

    def __init__(
        self,
        *,
        module_loader: Callable[[str], Any] = import_module,
        frame_decoder: Callable[[bytes], Any] | None = None,
    ) -> None:
        self._module_loader = module_loader
        self._frame_decoder = frame_decoder or _decode_jpeg
        self._module: Any | None = None
        self._load_attempted = False
        self._latest_frame: Any | None = None
        self._lock = RLock()

    def submit_frame_bytes(self, frame_bytes: bytes) -> bool:
        """Accept a JPEG frame from the browser camera WebSocket client."""
        try:
            frame = self._frame_decoder(frame_bytes)
        except Exception:
            return False
        if frame is None:
            return False
        with self._lock:
            self._latest_frame = frame
        return True

    def get_frame_data(self, context_mode: str = "city") -> dict[str, Any]:
        fallback = build_result(context_mode)
        module = self._get_module()
        with self._lock:
            frame = self._latest_frame
        if module is None or frame is None:
            return fallback

        try:
            result = module.process_camera_frame(frame, context_mode=context_mode)
        except Exception:
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


def _decode_jpeg(frame_bytes: bytes) -> Any:
    import cv2
    import numpy as np

    encoded = np.frombuffer(frame_bytes, dtype=np.uint8)
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)


def _merge_result(candidate: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    """Use valid CV leaves and retain safe defaults for malformed output."""
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
    if isinstance(candidate, dict):
        for name in names:
            if _is_score(candidate.get(name)):
                target[name] = float(candidate[name])


def _merge_bools(candidate: Any, target: dict[str, Any]) -> None:
    if isinstance(candidate, dict):
        for name in target:
            if isinstance(candidate.get(name), bool):
                target[name] = candidate[name]


def _merge_calibration(candidate: Any, target: dict[str, Any]) -> None:
    if isinstance(candidate, dict):
        if isinstance(candidate.get("in_progress"), bool):
            target["in_progress"] = candidate["in_progress"]
        if _is_non_negative(candidate.get("seconds_remaining")):
            target["seconds_remaining"] = float(candidate["seconds_remaining"])


def _merge_alert(candidate: Any, target: dict[str, Any]) -> None:
    if isinstance(candidate, dict):
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
