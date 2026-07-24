from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.cv_provider import CVFrameProvider
from cv.schema import build_result, validate_result


def test_cv_provider_processes_browser_frame_and_merges_partial_result() -> None:
    processed: list[object] = []

    def process(frame: object, *, context_mode: str) -> dict:
        processed.append(frame)
        return {
            "risk_score": 83.0,
            "signals": {"perclos": 91.0, "head_pose": None},
            "signal_quality": {"face_detected": True},
            "calibration": {"in_progress": True, "seconds_remaining": 12.0},
            "context_mode": context_mode,
        }

    provider = CVFrameProvider(
        module_loader=lambda _: SimpleNamespace(process_camera_frame=process),
        frame_decoder=lambda frame_bytes: {"jpeg": frame_bytes},
    )

    before_frame = provider.get_frame_data("night")
    assert before_frame["signal_quality"]["face_detected"] is False
    assert provider.submit_frame_bytes(b"jpeg-frame") is True
    result = provider.get_frame_data("night")

    validate_result(result)
    assert processed == [{"jpeg": b"jpeg-frame"}]
    assert result["risk_score"] == 83.0
    assert result["signals"]["perclos"] == 91.0
    assert result["signals"]["head_pose"] == 0.0
    assert result["context_mode"] == "night"


def test_cv_provider_uses_safe_result_for_decode_or_processing_failure() -> None:
    provider = CVFrameProvider(module_loader=lambda _: SimpleNamespace(process_camera_frame=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError())))
    assert provider.submit_frame_bytes(b"bad") is False
    result = provider.get_frame_data()
    validate_result(result)
    assert result["signal_quality"]["face_detected"] is False


class FakeCVProvider:
    def __init__(self) -> None:
        self.calibration_starts = 0
        self.context_modes: list[str] = []

    def get_frame_data(self, context_mode: str = "city") -> dict:
        result = build_result(context_mode, timestamp=1.0)
        result["signal_quality"] = {"face_detected": True, "hands_detected": True, "lighting_ok": True}
        return result

    def start_calibration(self) -> bool:
        self.calibration_starts += 1
        return True

    def set_context_mode(self, context_mode: str) -> bool:
        self.context_modes.append(context_mode)
        return True


def test_session_controls_call_cv_provider_and_update_stream_context() -> None:
    provider = FakeCVProvider()
    client = TestClient(create_app(provider=provider))

    start = client.post("/session/start")
    context = client.post("/session/context", json={"mode": "night"})

    assert start.status_code == 200
    assert start.json()["calibrating"] is True
    assert start.json()["cv_calibration_started"] is True
    assert provider.calibration_starts == 1
    assert context.json() == {"context_mode": "night", "cv_context_updated": True}
    assert provider.context_modes == ["night"]

    with client.websocket_connect("/ws/risk") as websocket:
        message = websocket.receive_json()

    validate_result(message)
    assert message["context_mode"] == "night"


def test_context_endpoint_rejects_unsupported_mode() -> None:
    client = TestClient(create_app(provider=FakeCVProvider()))

    response = client.post("/session/context", json={"mode": "rain"})

    assert response.status_code == 422
