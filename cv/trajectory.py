"""Camera-independent predictive risk trajectory analysis.

This module is deliberately limited to timestamped risk scores.  Keeping it
free of OpenCV, MediaPipe, and the fusion engine lets us prove the predictive
alerting behaviour with deterministic synthetic tests before wiring it to a
webcam.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from numbers import Real
from typing import Deque


@dataclass(frozen=True)
class TrajectoryConfig:
    """Configuration for trajectory-based alert prediction.

    ``lookahead_seconds`` is intentionally time-based instead of frame-count
    based.  The backend emits roughly every 200 ms, but using seconds keeps the
    prediction mathematically correct if the actual stream cadence varies.
    """

    threshold: float = 70.0
    window_size: int = 15
    min_points: int = 3
    lookahead_seconds: float = 3.0

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold <= 100.0:
            raise ValueError("threshold must be in the interval (0, 100].")
        if self.window_size < 2:
            raise ValueError("window_size must be at least 2.")
        if not 2 <= self.min_points <= self.window_size:
            raise ValueError("min_points must be between 2 and window_size.")
        if self.lookahead_seconds <= 0:
            raise ValueError("lookahead_seconds must be positive.")


class TrajectoryAnalyzer:
    """Predict risk-threshold crossings from a rolling linear regression.

    ``push`` returns values that map directly into the Person 1 output
    contract.  ``naive_score`` is simply the raw fused score: it never uses a
    trajectory projection and therefore represents a threshold-only detector.

    A predictive alert is active when the raw score is at/above the threshold,
    or when an *upward* trend projects the score across the threshold within
    the configured look-ahead horizon.  Downward trends cannot create alerts.
    """

    def __init__(self, config: TrajectoryConfig | None = None) -> None:
        self.config = config or TrajectoryConfig()
        self._samples: Deque[tuple[float, float]] = deque(maxlen=self.config.window_size)
        self._predictive_alert_started_at: float | None = None
        self._realized_time_saved: float | None = None
        self._last_timestamp: float | None = None

    def reset(self) -> None:
        """Clear rolling history and any pending predictive alert."""
        self._samples.clear()
        self._predictive_alert_started_at = None
        self._realized_time_saved = None
        self._last_timestamp = None

    def snapshot(self) -> dict[str, float | bool]:
        """Return a safe result before any sample has been received."""
        return {
            "trend_slope": self._slope(),
            "naive_score": self._samples[-1][1] if self._samples else 0.0,
            "alert_active": False,
            "time_saved_seconds": 0.0,
        }

    def push(self, timestamp: float, risk_score: float) -> dict[str, float | bool]:
        """Add one fused risk score and return current predictive state.

        Timestamps must be strictly increasing.  This protects the regression
        and produces deterministic behaviour for the WebSocket stream.
        """
        timestamp = _require_number(timestamp, "timestamp")
        risk_score = _require_number(risk_score, "risk_score")
        if not 0.0 <= risk_score <= 100.0:
            raise ValueError("risk_score must be between 0 and 100.")
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError("timestamp must be strictly greater than the previous timestamp.")

        self._samples.append((timestamp, risk_score))
        self._last_timestamp = timestamp
        slope = self._slope()
        predictive_score = risk_score + max(0.0, slope) * self.config.lookahead_seconds
        raw_threshold_crossed = risk_score >= self.config.threshold
        predictive_threshold_crossed = (
            len(self._samples) >= self.config.min_points
            and slope > 0.0
            and predictive_score >= self.config.threshold
        )
        alert_active = raw_threshold_crossed or predictive_threshold_crossed

        if predictive_threshold_crossed and not raw_threshold_crossed:
            estimated_seconds = (self.config.threshold - risk_score) / slope
            if self._predictive_alert_started_at is None:
                self._predictive_alert_started_at = timestamp
                self._realized_time_saved = None
            time_saved_seconds = estimated_seconds
        elif raw_threshold_crossed:
            if self._predictive_alert_started_at is None:
                time_saved_seconds = 0.0
            else:
                # At the actual crossing, expose the measured lead time rather
                # than an estimate.  Retain it while risk remains unsafe so the
                # dashboard can continue to explain the alert.
                if self._realized_time_saved is None:
                    self._realized_time_saved = max(
                        0.0,
                        timestamp - self._predictive_alert_started_at,
                    )
                time_saved_seconds = self._realized_time_saved
        else:
            # A declining score before raw threshold crossing cancels the
            # pending prediction; stale alerts are unsafe and misleading.
            self._predictive_alert_started_at = None
            self._realized_time_saved = None
            time_saved_seconds = 0.0

        return {
            "trend_slope": slope,
            "naive_score": risk_score,
            "alert_active": alert_active,
            "time_saved_seconds": time_saved_seconds,
        }

    def _slope(self) -> float:
        """Return ordinary-least-squares slope in risk-score points/second."""
        if len(self._samples) < self.config.min_points:
            return 0.0

        origin = self._samples[0][0]
        xs = [timestamp - origin for timestamp, _ in self._samples]
        ys = [risk_score for _, risk_score in self._samples]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denominator = sum((x - mean_x) ** 2 for x in xs)
        if denominator == 0.0:
            return 0.0
        return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def _require_number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number.")
    return float(value)
