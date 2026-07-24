"""Per-driver signal-baseline calibration state machine."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from numbers import Real
from time import monotonic

from .schema import SIGNAL_NAMES


class CalibrationState(StrEnum):
    IDLE = "idle"
    CALIBRATING = "calibrating"
    CALIBRATED = "calibrated"


class CalibrationEngine:
    """Learn per-signal thresholds over a bounded calibration window.

    The engine is clock-injectable so every transition can be tested without
    waiting 20--30 seconds.  Production uses ``time.monotonic`` by default.
    A completed threshold is ``baseline mean * threshold_multiplier``, capped
    at 100 because all upstream signal scores use the 0--100 contract range.
    """

    def __init__(
        self,
        duration_seconds: float = 25.0,
        threshold_multiplier: float = 1.4,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive.")
        if threshold_multiplier <= 0:
            raise ValueError("threshold_multiplier must be positive.")

        self.duration_seconds = float(duration_seconds)
        self.threshold_multiplier = float(threshold_multiplier)
        self._clock = clock
        self._state = CalibrationState.IDLE
        self._started_at: float | None = None
        self._last_sample_at: float | None = None
        self._samples: dict[str, list[float]] = {name: [] for name in SIGNAL_NAMES}
        self._thresholds: dict[str, float] = {}

    @property
    def state(self) -> CalibrationState:
        return self._state

    def start(self, timestamp: float | None = None) -> None:
        """Start a new calibration and discard all previous driver baselines."""
        now = self._resolve_timestamp(timestamp)
        self._state = CalibrationState.CALIBRATING
        self._started_at = now
        self._last_sample_at = None
        self._samples = {name: [] for name in SIGNAL_NAMES}
        self._thresholds = {}

    def reset(self) -> None:
        """Return to IDLE and clear calibration data."""
        self._state = CalibrationState.IDLE
        self._started_at = None
        self._last_sample_at = None
        self._samples = {name: [] for name in SIGNAL_NAMES}
        self._thresholds = {}

    def push_signals(self, signals: Mapping[str, float], timestamp: float | None = None) -> None:
        """Record one validated signal snapshot while calibration is active."""
        now = self._resolve_timestamp(timestamp)
        self._update_state(now)
        if self._state is not CalibrationState.CALIBRATING:
            return
        if self._last_sample_at is not None and now < self._last_sample_at:
            raise ValueError("Calibration signal timestamps must be non-decreasing.")
        _validate_signals(signals)
        for name in SIGNAL_NAMES:
            self._samples[name].append(float(signals[name]))
        self._last_sample_at = now

    def is_calibrating(self, timestamp: float | None = None) -> bool:
        self._update_state(self._resolve_timestamp(timestamp))
        return self._state is CalibrationState.CALIBRATING

    def get_thresholds(self, timestamp: float | None = None) -> dict[str, float]:
        """Return a copy of completed thresholds, or an empty mapping before."""
        self._update_state(self._resolve_timestamp(timestamp))
        return dict(self._thresholds)

    def status(self, timestamp: float | None = None) -> dict[str, bool | float]:
        """Return the exact calibration payload expected by the frontend."""
        now = self._resolve_timestamp(timestamp)
        self._update_state(now)
        seconds_remaining = 0.0
        if self._state is CalibrationState.CALIBRATING:
            assert self._started_at is not None
            seconds_remaining = max(0.0, self.duration_seconds - (now - self._started_at))
        return {
            "in_progress": self._state is CalibrationState.CALIBRATING,
            "seconds_remaining": seconds_remaining,
        }

    def _update_state(self, timestamp: float) -> None:
        if self._state is not CalibrationState.CALIBRATING:
            return
        assert self._started_at is not None
        if timestamp < self._started_at:
            raise ValueError("Calibration timestamp cannot precede start time.")
        if timestamp - self._started_at >= self.duration_seconds:
            self._complete()

    def _complete(self) -> None:
        self._thresholds = {
            name: min(100.0, _mean(self._samples[name]) * self.threshold_multiplier)
            for name in SIGNAL_NAMES
        }
        self._state = CalibrationState.CALIBRATED

    def _resolve_timestamp(self, timestamp: float | None) -> float:
        value = self._clock() if timestamp is None else timestamp
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("timestamp must be a number.")
        return float(value)


def _validate_signals(signals: Mapping[str, float]) -> None:
    if set(signals) != set(SIGNAL_NAMES):
        raise ValueError(f"signals must contain exactly {list(SIGNAL_NAMES)}.")
    for name in SIGNAL_NAMES:
        value = signals[name]
        if isinstance(value, bool) or not isinstance(value, Real) or not 0.0 <= value <= 100.0:
            raise ValueError(f"signals.{name} must be a number between 0 and 100.")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
