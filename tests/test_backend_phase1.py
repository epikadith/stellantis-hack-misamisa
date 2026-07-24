from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import create_app
from cv.schema import build_result, validate_result


class SafeProvider:
    def get_frame_data(self, context_mode: str = "city") -> dict:
        return build_result(context_mode, timestamp=1.0)


def test_websocket_sends_consecutive_schema_valid_messages() -> None:
    client = TestClient(create_app(provider=SafeProvider()))

    with client.websocket_connect("/ws/risk") as websocket:
        messages = [websocket.receive_json() for _ in range(5)]

    for message in messages:
        validate_result(message)
        assert message["context_mode"] == "city"
