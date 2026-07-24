from __future__ import annotations

import math

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.simulation import SimulatedRiskProvider
from cv.schema import CONTEXT_MODES, validate_result


def test_simulated_provider_is_schema_valid_and_deterministic() -> None:
    provider = SimulatedRiskProvider(clock=lambda: 7.5)

    result = provider.get_frame_data("night")

    validate_result(result)
    assert result["timestamp"] == 7.5
    assert result["context_mode"] == "night"
    assert result["risk_score"] == 95.0
    assert result["naive_score"] == result["risk_score"]
    assert math.isclose(result["trend_slope"], 0.0, abs_tol=1e-12)


def test_websocket_sends_consecutive_schema_valid_messages() -> None:
    client = TestClient(create_app(provider=SimulatedRiskProvider()))

    with client.websocket_connect("/ws/risk") as websocket:
        messages = [websocket.receive_json() for _ in range(5)]

    for message in messages:
        validate_result(message)
        assert message["context_mode"] in CONTEXT_MODES
