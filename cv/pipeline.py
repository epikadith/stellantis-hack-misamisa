"""In-process webcam pipeline consumed directly by the FastAPI backend."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from threading import RLock
from time import time
from typing import Any

from .calibration import CalibrationEngine
from .fusion import SignalFusionEngine
from .hand_zone import HandZone, classify_hands
from .head_pose import estimate_head_pose, head_pose_risk
from .perclos import PerclosExtractor
from .schema import CONTEXT_MODES, SIGNAL_NAMES, build_result, validate_result
from .trajectory import TrajectoryAnalyzer
from .yawn import YawnExtractor

_LEFT_EYE = (33, 160, 158, 133, 153, 144)
_RIGHT_EYE = (362, 385, 387, 263, 373, 380)


class RiskPipeline:
    """Extract, calibrate, fuse, and predict risk from one webcam frame.

    The class owns all rolling state.  Its ``process_signals`` method is a
    deterministic integration seam for tests and for future alternate camera
    providers; ``process_frame`` is the real OpenCV + MediaPipe path.
    """

    def __init__(
        self,
        *,
        camera_index: int = 0,
        calibration: CalibrationEngine | None = None,
        fusion: SignalFusionEngine | None = None,
        trajectory: TrajectoryAnalyzer | None = None,
        capture_factory: Callable[[int], Any] | None = None,
    ) -> None:
        self.camera_index = camera_index
        self.calibration = calibration or CalibrationEngine()
        self.fusion = fusion or SignalFusionEngine()
        self.trajectory = trajectory or TrajectoryAnalyzer()
        self.perclos = PerclosExtractor()
        self.yawn = YawnExtractor()
        self._capture_factory = capture_factory
        self._capture: Any | None = None
        self._face_mesh: Any | None = None
        self._hands: Any | None = None
        self._context_mode = "city"
        self._lock = RLock()

    def set_context_mode(self, context_mode: str) -> None:
        if context_mode not in CONTEXT_MODES:
            raise ValueError(f"Unsupported context mode {context_mode!r}.")
        with self._lock:
            self._context_mode = context_mode

    def start_calibration(self, timestamp: float | None = None) -> None:
        with self._lock:
            self.calibration.start(timestamp)

    def get_current_frame_result(self, context_mode: str | None = None) -> dict[str, Any]:
        """Return one schema-valid camera result, even when a camera is absent."""
        with self._lock:
            if context_mode is not None:
                self.set_context_mode(context_mode)
            try:
                capture = self._ensure_capture()
                if capture is None or not capture.isOpened():
                    return self._safe_result()
                ok, frame = capture.read()
                if not ok or frame is None:
                    return self._safe_result()
                return self.process_frame(frame)
            except Exception:
                # The backend has a simulated-data fallback, but the CV module
                # itself also guarantees a valid message on bad camera frames.
                return self._safe_result()

    def process_frame(self, frame_bgr: Any, timestamp: float | None = None) -> dict[str, Any]:
        """Process one BGR OpenCV frame through MediaPipe Face Mesh and Hands."""
        with self._lock:
            cv2, _ = _vision_dependencies()
            if frame_bgr is None or getattr(frame_bgr, "ndim", 0) != 3 or frame_bgr.shape[2] != 3:
                raise ValueError("frame_bgr must be a non-empty three-channel BGR image.")
            height, width = frame_bgr.shape[:2]
            if height <= 0 or width <= 0:
                raise ValueError("frame_bgr must have positive dimensions.")
            self._ensure_detectors()
            rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            assert self._face_mesh is not None and self._hands is not None
            face_result = self._face_mesh.process(rgb_frame)
            hand_result = self._hands.process(rgb_frame)

            face_landmarks = face_result.multi_face_landmarks[0].landmark if face_result.multi_face_landmarks else None
            hands = [hand.landmark for hand in hand_result.multi_hand_landmarks or []]
            lighting = _lighting_ok(frame_bgr, cv2)
            signals = _empty_signals()
            quality = {
                "face_detected": face_landmarks is not None,
                "hands_detected": bool(hands),
                "lighting_ok": lighting,
            }

            if face_landmarks is not None:
                signals["perclos"] = self.perclos.push_landmarks(
                    _resolve_timestamp(timestamp),
                    _points(face_landmarks, _LEFT_EYE),
                    _points(face_landmarks, _RIGHT_EYE),
                )
                try:
                    yaw, pitch = estimate_head_pose(_indexed_points(face_landmarks), width, height)
                    signals["head_pose"] = head_pose_risk(yaw, pitch)
                except (RuntimeError, ValueError, IndexError):
                    signals["head_pose"] = 0.0
                signals["yawn"] = self.yawn.push_landmarks(
                    _point(face_landmarks[13]),
                    _point(face_landmarks[14]),
                    _point(face_landmarks[78]),
                    _point(face_landmarks[308]),
                )

            if hands:
                face_center = _point(face_landmarks[1]) if face_landmarks is not None else None
                _, signals["hand_zone"] = classify_hands(
                    [[_point(landmark) for landmark in hand] for hand in hands],
                    face_center=face_center,
                )

            return self.process_signals(signals, signal_quality=quality, timestamp=timestamp)

    def process_signals(
        self,
        signals: Mapping[str, float],
        *,
        signal_quality: Mapping[str, bool] | None = None,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        """Run a synthetic or extracted signal snapshot through all deep modules."""
        with self._lock:
            now = _resolve_timestamp(timestamp)
            values = {name: float(signals[name]) for name in SIGNAL_NAMES}
            quality = _validate_quality(signal_quality)
            self.calibration.push_signals(values, now)
            thresholds = self.calibration.get_thresholds(now)
            risk_score = self.fusion.compute_from_signals(
                values,
                calibration_thresholds=thresholds if thresholds else None,
                context_mode=self._context_mode,
            )
            trajectory = self.trajectory.push(now, risk_score)
            calibration_status = self.calibration.status(now)
            result = build_result(self._context_mode, timestamp=now)
            result["risk_score"] = risk_score
            result["trend_slope"] = trajectory["trend_slope"]
            result["naive_score"] = trajectory["naive_score"]
            result["signals"] = values
            result["signal_quality"] = quality
            result["calibration"] = calibration_status
            result["alert"] = {
                "active": trajectory["alert_active"],
                "severity": _severity(risk_score, trajectory["alert_active"]),
                "reason": _alert_reason(values, trajectory["trend_slope"], trajectory["alert_active"]),
                "time_saved_seconds": trajectory["time_saved_seconds"],
            }
            validate_result(result)
            return result

    def close(self) -> None:
        """Release webcam and MediaPipe resources; safe to call repeatedly."""
        with self._lock:
            for resource in (self._capture, self._face_mesh, self._hands):
                close = getattr(resource, "close", None) or getattr(resource, "release", None)
                if close is not None:
                    close()
            self._capture = None
            self._face_mesh = None
            self._hands = None

    def _safe_result(self) -> dict[str, Any]:
        now = _resolve_timestamp(None)
        result = build_result(self._context_mode, timestamp=now)
        result["calibration"] = self.calibration.status(now)
        validate_result(result)
        return result

    def _ensure_capture(self) -> Any | None:
        if self._capture is not None:
            return self._capture
        if self._capture_factory is not None:
            self._capture = self._capture_factory(self.camera_index)
            return self._capture
        cv2, _ = _vision_dependencies()
        self._capture = cv2.VideoCapture(self.camera_index)
        return self._capture

    def _ensure_detectors(self) -> None:
        if self._face_mesh is not None and self._hands is not None:
            return
        _, mp = _vision_dependencies()
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )


def _vision_dependencies() -> tuple[Any, Any]:
    try:
        import cv2
        import mediapipe as mp
    except ImportError as error:  # pragma: no cover - project dependency failure
        raise RuntimeError("Live capture requires the project's cv dependency extra.") from error
    return cv2, mp


def _resolve_timestamp(timestamp: float | None) -> float:
    return float(time() if timestamp is None else timestamp)


def _empty_signals() -> dict[str, float]:
    return {name: 0.0 for name in SIGNAL_NAMES}


def _validate_quality(quality: Mapping[str, bool] | None) -> dict[str, bool]:
    default = {"face_detected": True, "hands_detected": True, "lighting_ok": True}
    if quality is None:
        return default
    if set(quality) != set(default) or not all(isinstance(value, bool) for value in quality.values()):
        raise ValueError("signal_quality must contain the three boolean quality flags.")
    return dict(quality)


def _severity(risk_score: float, alert_active: bool) -> str:
    if not alert_active:
        return "none"
    return "red" if risk_score >= 70.0 else "amber"


def _alert_reason(signals: Mapping[str, float], trend_slope: float, alert_active: bool) -> str:
    if not alert_active:
        return ""
    dominant = sorted(signals.items(), key=lambda item: item[1], reverse=True)[:2]
    contributors = " + ".join(f"{name.replace('_', ' ')} {value:.0f}%" for name, value in dominant if value > 0)
    trend = f"rising {trend_slope:.1f} risk points/s"
    return f"Predictive alert: {contributors or 'combined risk'}; {trend}."


def _point(landmark: Any) -> tuple[float, float]:
    return float(landmark.x), float(landmark.y)


def _points(landmarks: Sequence[Any], indices: Sequence[int]) -> list[tuple[float, float]]:
    return [_point(landmarks[index]) for index in indices]


def _indexed_points(landmarks: Sequence[Any]) -> dict[int, tuple[float, float]]:
    return {index: _point(landmarks[index]) for index in (1, 152, 33, 263, 61, 291)}


def _lighting_ok(frame_bgr: Any, cv2: Any) -> bool:
    brightness = float(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY).mean())
    return 40.0 <= brightness <= 220.0
