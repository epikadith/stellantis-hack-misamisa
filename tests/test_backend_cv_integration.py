from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.cv_provider import CVFrameProvider
from backend.simulation import SimulatedRiskProvider
from cv.schema import build_result, validate_result


def test_cv_provider_merges_partial_cv_result_with_simulation() -> None:
    module = SimpleNamespace(
        get_current_frame_result=lambda *, context_mode: {
            "risk_score": 83.0,
            "signals": {"perclos": 91.0, "head_pose": None},
            "signal_quality": {"face_detected": True},
            "calibration": {"in_progress": True, "seconds_remaining": 12.0},
            "context_mode": "city",
        }
    )
    provider = CVFrameProvider(
        module_loader=lambda _: module,
        simulation=SimulatedRiskProvider(clock=lambda: 0.0),
    )

    result = provider.get_frame_data("night")

    validate_result(result)
    assert result["risk_score"] == 83.0
    assert result["signals"]["perclos"] == 91.0
    assert result["signals"]["head_pose"] == 45.0
    assert result["signal_quality"] == {
        "face_detected": True,
        "hands_detected": True,
        "lighting_ok": True,
    }
    assert result["calibration"] == {"in_progress": True, "seconds_remaining": 12.0}
    assert result["context_mode"] == "night"


def test_cv_exception_and_safe_camera_result_use_simulation() -> None:
    fallback = SimulatedRiskProvider(clock=lambda: 0.0)
    failing = SimpleNamespace(get_current_frame_result=lambda **_: (_ for _ in ()).throw(RuntimeError("camera")))
    safe = SimpleNamespace(get_current_frame_result=lambda **_: build_result())

    assert CVFrameProvider(module_loader=lambda _: failing, simulation=fallback).get_frame_data() == fallback.get_frame_data()
    assert CVFrameProvider(module_loader=lambda _: safe, simulation=fallback).get_frame_data() == fallback.get_frame_data()


class FakeCVProvider:
    def __init__(self) -> None:
        self.calibration_starts = 0
        self.context_modes: list[str] = []

    def get_frame_data(self, context_mode: str = "city") -> dict:
        return SimulatedRiskProvider(clock=lambda: 0.0).get_frame_data(context_mode)

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
