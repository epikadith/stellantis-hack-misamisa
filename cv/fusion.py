"""Configurable, calibration-aware fusion of the four driver-risk signals."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Mapping

from .schema import CONTEXT_MODES, SIGNAL_NAMES

# These preserve the PRD's intended behaviour: highway reduces sensitivity and
# night increases it relative to the neutral city baseline.
CONTEXT_RISK_MULTIPLIERS = {"city": 1.0, "highway": 0.85, "night": 1.15}


@dataclass(frozen=True)
class FusionWeights:
    perclos: float = 0.40
    head_pose: float = 0.30
    hand_zone: float = 0.20
    yawn: float = 0.10

    def __post_init__(self) -> None:
        values = self.as_dict()
        if any(value < 0.0 for value in values.values()):
            raise ValueError("Fusion weights cannot be negative.")
        if abs(sum(values.values()) - 1.0) > 1e-9:
            raise ValueError("Fusion weights must sum to 1.0.")

    def as_dict(self) -> dict[str, float]:
        return {
            "perclos": self.perclos,
            "head_pose": self.head_pose,
            "hand_zone": self.hand_zone,
            "yawn": self.yawn,
        }


class SignalFusionEngine:
    """Fuse normalized signal values into one 0--100 risk score."""

    def __init__(self, weights: FusionWeights | None = None) -> None:
        self.weights = weights or FusionWeights()

    def compute_risk(
        self,
        perclos: float,
        head_pose: float,
        hand_zone: float,
        yawn: float,
        *,
        calibration_thresholds: Mapping[str, float] | None = None,
        context_mode: str = "city",
    ) -> float:
        return self.compute_from_signals(
            {
                "perclos": perclos,
                "head_pose": head_pose,
                "hand_zone": hand_zone,
                "yawn": yawn,
            },
            calibration_thresholds=calibration_thresholds,
            context_mode=context_mode,
        )

    def compute_from_signals(
        self,
        signals: Mapping[str, float],
        *,
        calibration_thresholds: Mapping[str, float] | None = None,
        context_mode: str = "city",
    ) -> float:
        """Return weighted risk with optional per-driver baseline adjustment.

        During calibration (or when a signal's learned baseline is zero), the
        source 0--100 score is used directly.  Once a positive calibrated
        threshold exists, the signal reaches full contribution at that
        threshold.  This makes baseline * 1.4 the personalised trigger level.
        """
        _validate_signals(signals)
        if context_mode not in CONTEXT_MODES:
            raise ValueError(f"Unsupported context mode {context_mode!r}.")
        if calibration_thresholds is not None:
            _validate_thresholds(calibration_thresholds)

        weights = self.weights.as_dict()
        weighted_score = sum(
            _calibrated_signal_score(signals[name], _threshold_for(name, calibration_thresholds)) * weights[name]
            for name in SIGNAL_NAMES
        )
        return min(100.0, max(0.0, weighted_score * CONTEXT_RISK_MULTIPLIERS[context_mode]))


def compute_risk(
    perclos: float,
    head_pose: float,
    hand_zone: float,
    yawn: float,
    weights: FusionWeights | None = None,
) -> float:
    """PRD-compatible convenience interface for basic weighted fusion."""
    return SignalFusionEngine(weights).compute_risk(perclos, head_pose, hand_zone, yawn)


def _threshold_for(name: str, thresholds: Mapping[str, float] | None) -> float | None:
    return None if thresholds is None else float(thresholds[name])


def _calibrated_signal_score(value: float, threshold: float | None) -> float:
    if threshold is None or threshold <= 0.0:
        return value
    return min(100.0, value / threshold * 100.0)


def _validate_signals(signals: Mapping[str, float]) -> None:
    if set(signals) != set(SIGNAL_NAMES):
        raise ValueError(f"signals must contain exactly {list(SIGNAL_NAMES)}.")
    for name in SIGNAL_NAMES:
        value = signals[name]
        if isinstance(value, bool) or not isinstance(value, Real) or not 0.0 <= value <= 100.0:
            raise ValueError(f"signals.{name} must be a number between 0 and 100.")


def _validate_thresholds(thresholds: Mapping[str, float]) -> None:
    if set(thresholds) != set(SIGNAL_NAMES):
        raise ValueError(f"calibration_thresholds must contain exactly {list(SIGNAL_NAMES)}.")
    for name in SIGNAL_NAMES:
        value = thresholds[name]
        if isinstance(value, bool) or not isinstance(value, Real) or not 0.0 <= value <= 100.0:
            raise ValueError(f"calibration_thresholds.{name} must be a number between 0 and 100.")
