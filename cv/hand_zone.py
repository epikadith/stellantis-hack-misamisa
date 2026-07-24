"""Hand-zone heuristics for on-wheel, off-wheel, and phone-near-face states."""

from __future__ import annotations

from enum import StrEnum
from math import hypot
from typing import Sequence

Point2D = Sequence[float]


class HandZone(StrEnum):
    ON_WHEEL = "on_wheel"
    OFF_WHEEL = "off_wheel"
    PHONE_NEAR_FACE = "phone_near_face"
    NOT_DETECTED = "not_detected"


_ZONE_SCORES = {
    HandZone.ON_WHEEL: 0.0,
    HandZone.OFF_WHEEL: 60.0,
    HandZone.PHONE_NEAR_FACE: 100.0,
    HandZone.NOT_DETECTED: 0.0,
}


def classify_hand_zone(
    hand_landmarks: Sequence[Point2D],
    *,
    face_center: Point2D | None = None,
    wheel_center: Point2D = (0.5, 0.78),
    wheel_radius: float = 0.32,
    phone_near_face_radius: float = 0.18,
) -> HandZone:
    """Classify one normalized MediaPipe hand-landmark set.

    The wrist (index 0) approximates the wheel position.  The index-finger tip
    (index 8) near the detected face is a conservative phone-distraction cue.
    """
    if len(hand_landmarks) < 9:
        raise ValueError("A hand must contain at least wrist (0) and index tip (8) landmarks.")
    if wheel_radius <= 0 or phone_near_face_radius <= 0:
        raise ValueError("zone radii must be positive.")
    wrist = hand_landmarks[0]
    index_tip = hand_landmarks[8]
    if face_center is not None and _distance(index_tip, face_center) <= phone_near_face_radius:
        return HandZone.PHONE_NEAR_FACE
    if _distance(wrist, wheel_center) <= wheel_radius:
        return HandZone.ON_WHEEL
    return HandZone.OFF_WHEEL


def classify_hands(
    hands: Sequence[Sequence[Point2D]],
    **kwargs: object,
) -> tuple[HandZone, float]:
    """Return the highest-risk classification and signal score for all hands."""
    if not hands:
        return HandZone.NOT_DETECTED, _ZONE_SCORES[HandZone.NOT_DETECTED]
    zones = [classify_hand_zone(hand, **kwargs) for hand in hands]
    highest_risk = max(zones, key=lambda zone: _ZONE_SCORES[zone])
    return highest_risk, _ZONE_SCORES[highest_risk]


def hand_zone_score(zone: HandZone) -> float:
    return _ZONE_SCORES[zone]


def _distance(first: Point2D, second: Point2D) -> float:
    if len(first) < 2 or len(second) < 2:
        raise ValueError("Landmarks must each contain x and y coordinates.")
    return hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))
