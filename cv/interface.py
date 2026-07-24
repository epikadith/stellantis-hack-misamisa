"""Stable synchronous entry point consumed by the FastAPI stream manager."""

from __future__ import annotations

from .pipeline import RiskPipeline

_DEFAULT_PIPELINE = RiskPipeline()


def get_current_frame_result(context_mode: str = "city") -> dict:
    """Return the current risk message without requiring async or IPC.

    The pipeline lazily opens the camera only when called.  If the webcam or a
    frame is unavailable, it still returns a conservative schema-valid result
    so Person 2 can retain its simulated-data fallback without a crash.
    """
    return _DEFAULT_PIPELINE.get_current_frame_result(context_mode)


def process_camera_frame(frame_bgr: object, context_mode: str = "city") -> dict:
    """Process one browser-supplied OpenCV BGR frame through the CV pipeline."""
    _DEFAULT_PIPELINE.set_context_mode(context_mode)
    return _DEFAULT_PIPELINE.process_frame(frame_bgr)


def start_calibration() -> None:
    """Reset and start Person 1 calibration; call from POST /session/start."""
    _DEFAULT_PIPELINE.start_calibration()


def set_context_mode(context_mode: str) -> None:
    """Update the thread-safe CV context; call from POST /session/context."""
    _DEFAULT_PIPELINE.set_context_mode(context_mode)


def close_pipeline() -> None:
    """Release webcam and MediaPipe resources during backend shutdown."""
    _DEFAULT_PIPELINE.close()
