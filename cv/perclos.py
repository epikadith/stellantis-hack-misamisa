"""Eye-aspect-ratio and rolling PERCLOS extraction."""

from __future__ import annotations

from collections import deque
from math import hypot
from numbers import Real
from typing import Deque, Sequence

Point2D = Sequence[float]


def eye_aspect_ratio(eye: Sequence[Point2D]) -> float:
    """Calculate EAR from six ordered eye points: p1 through p6.

    EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|).
    """
    if len(eye) != 6:
        raise ValueError("An eye must contain exactly six landmarks.")
    horizontal = _distance(eye[0], eye[3])
    if horizontal == 0.0:
        raise ValueError("Eye landmarks have zero horizontal width.")
    return (_distance(eye[1], eye[5]) + _distance(eye[2], eye[4])) / (2.0 * horizontal)


class PerclosExtractor:
    """Classify EAR samples and calculate rolling percentage eye closure."""

    def __init__(self, ear_closed_threshold: float = 0.21, window_seconds: float = 10.0) -> None:
        if ear_closed_threshold <= 0:
            raise ValueError("ear_closed_threshold must be positive.")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive.")
        self.ear_closed_threshold = float(ear_closed_threshold)
        self.window_seconds = float(window_seconds)
        self._samples: Deque[tuple[float, bool]] = deque()
        self._last_timestamp: float | None = None

    def push_ear(self, timestamp: float, ear: float) -> float:
        timestamp = _number(timestamp, "timestamp")
        ear = _number(ear, "ear")
        if ear < 0:
            raise ValueError("ear cannot be negative.")
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError("timestamps must be strictly increasing.")
        self._samples.append((timestamp, ear < self.ear_closed_threshold))
        self._last_timestamp = timestamp
        cutoff = timestamp - self.window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        return 100.0 * sum(closed for _, closed in self._samples) / len(self._samples)

    def push_landmarks(self, timestamp: float, left_eye: Sequence[Point2D], right_eye: Sequence[Point2D]) -> float:
        return self.push_ear(timestamp, (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2.0)


def _distance(first: Point2D, second: Point2D) -> float:
    if len(first) < 2 or len(second) < 2:
        raise ValueError("Landmarks must each contain x and y coordinates.")
    return hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))


def _number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number.")
    return float(value)
