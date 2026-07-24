"""Mouth-aspect-ratio yawn signal extraction."""

from __future__ import annotations

from math import hypot
from typing import Sequence

Point2D = Sequence[float]


def mouth_aspect_ratio(upper_lip: Point2D, lower_lip: Point2D, left_corner: Point2D, right_corner: Point2D) -> float:
    """Return mouth opening divided by mouth width (MAR)."""
    width = _distance(left_corner, right_corner)
    if width == 0.0:
        raise ValueError("Mouth landmarks have zero width.")
    return _distance(upper_lip, lower_lip) / width


def yawn_score(mar: float, threshold: float = 0.6) -> float:
    """Map MAR to a smooth 0--100 fatigue contribution around its threshold."""
    if threshold <= 0:
        raise ValueError("threshold must be positive.")
    if mar < 0:
        raise ValueError("mar cannot be negative.")
    # Below half the configured yawn threshold is no contribution; at 1.5x
    # threshold it reaches 100.  This avoids a binary risk jump.
    return min(100.0, max(0.0, 100.0 * (mar - threshold * 0.5) / threshold))


class YawnExtractor:
    def __init__(self, threshold: float = 0.6) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be positive.")
        self.threshold = float(threshold)

    def push_mar(self, mar: float) -> float:
        return yawn_score(mar, self.threshold)

    def push_landmarks(self, upper_lip: Point2D, lower_lip: Point2D, left_corner: Point2D, right_corner: Point2D) -> float:
        return self.push_mar(mouth_aspect_ratio(upper_lip, lower_lip, left_corner, right_corner))


def _distance(first: Point2D, second: Point2D) -> float:
    if len(first) < 2 or len(second) < 2:
        raise ValueError("Landmarks must each contain x and y coordinates.")
    return hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))
