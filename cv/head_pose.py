"""Head-pose estimation and distraction-risk normalization."""

from __future__ import annotations

from math import isfinite
from numbers import Real
from typing import Mapping, Sequence


# Standard sparse facial model aligned to MediaPipe Face Mesh indices below.
_MODEL_POINTS = (
    (0.0, 0.0, 0.0),  # nose tip (1)
    (0.0, -330.0, -65.0),  # chin (152)
    (-225.0, 170.0, -135.0),  # left eye outer corner (33)
    (225.0, 170.0, -135.0),  # right eye outer corner (263)
    (-150.0, -150.0, -125.0),  # left mouth corner (61)
    (150.0, -150.0, -125.0),  # right mouth corner (291)
)
_LANDMARK_INDICES = (1, 152, 33, 263, 61, 291)


def head_pose_risk(yaw_degrees: float, pitch_degrees: float, *, yaw_limit: float = 20.0, pitch_limit: float = 15.0) -> float:
    """Map yaw/pitch distraction to the shared 0--100 signal range."""
    yaw = _number(yaw_degrees, "yaw_degrees")
    pitch = _number(pitch_degrees, "pitch_degrees")
    if yaw_limit <= 0 or pitch_limit <= 0:
        raise ValueError("yaw_limit and pitch_limit must be positive.")
    return min(100.0, 100.0 * max(abs(yaw) / yaw_limit, abs(pitch) / pitch_limit))


def estimate_head_pose(
    face_landmarks: Mapping[int, Sequence[float]] | Sequence[Sequence[float]],
    frame_width: int,
    frame_height: int,
) -> tuple[float, float]:
    """Estimate ``(yaw, pitch)`` with OpenCV ``solvePnP``.

    ``face_landmarks`` may be a MediaPipe-indexed sequence of normalized
    coordinates or a mapping keyed by Face Mesh index.  OpenCV and NumPy are
    imported only here so unit tests and backend fallback imports stay clean
    before camera dependencies are installed.
    """
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame_width and frame_height must be positive.")
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np
    except ImportError as error:  # pragma: no cover - depends on local environment
        raise RuntimeError("Head-pose estimation requires opencv-python and numpy.") from error

    image_points = []
    for index in _LANDMARK_INDICES:
        landmark = face_landmarks[index]
        if len(landmark) < 2:
            raise ValueError(f"Face landmark {index} must contain x and y coordinates.")
        image_points.append((float(landmark[0]) * frame_width, float(landmark[1]) * frame_height))

    focal_length = float(frame_width)
    camera_matrix = np.array(
        ((focal_length, 0.0, frame_width / 2.0), (0.0, focal_length, frame_height / 2.0), (0.0, 0.0, 1.0)),
        dtype="double",
    )
    success, rotation_vector, _ = cv2.solvePnP(
        np.array(_MODEL_POINTS, dtype="double"),
        np.array(image_points, dtype="double"),
        camera_matrix,
        np.zeros((4, 1)),
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        raise RuntimeError("OpenCV solvePnP could not estimate head pose.")
    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    angles, *_ = cv2.RQDecomp3x3(rotation_matrix)
    pitch, yaw = float(angles[0]), float(angles[1])
    if not isfinite(yaw) or not isfinite(pitch):
        raise RuntimeError("Head-pose estimation produced non-finite angles.")
    return yaw, pitch


def _number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number.")
    return float(value)
