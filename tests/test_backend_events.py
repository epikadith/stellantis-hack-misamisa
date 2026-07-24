from __future__ import annotations

from collections import deque
from copy import deepcopy

from fastapi.testclient import TestClient

from backend.app import create_app
from cv.schema import build_result, validate_result


class SequenceProvider:
    def __init__(self, results: list[dict]) -> None:
        self._results = deque(results)
        self._last = results[-1]

    def get_frame_data(self, context_mode: str = "city") -> dict:
        result = deepcopy(self._results.popleft() if self._results else self._last)
        result["context_mode"] = context_mode
        return result


def _result(
    timestamp: float,
    *,
    alert_active: bool = False,
    calibration_active: bool = False,
) -> dict:
    result = build_result(timestamp=timestamp)
    result["signal_quality"] = {
        "face_detected": True,
        "hands_detected": True,
        "lighting_ok": True,
    }
    result["calibration"] = {
        "in_progress": calibration_active,
        "seconds_remaining": 4.0 if calibration_active else 0.0,
    }
    result["alert"] = {
        "active": alert_active,
        "severity": "amber" if alert_active else "none",
        "reason": "Predictive alert: rising risk." if alert_active else "",
        "time_saved_seconds": 1.5 if alert_active else 0.0,
    }
    validate_result(result)
    return result


def test_alert_event_is_logged_once_and_pushed_after_risk_message() -> None:
    provider = SequenceProvider([_result(1.0), _result(2.0, alert_active=True), _result(3.0, alert_active=True)])
    client = TestClient(create_app(provider=provider))

    with client.websocket_connect("/ws/risk") as websocket:
        first_risk = websocket.receive_json()
        alert_risk = websocket.receive_json()
        event_message = websocket.receive_json()
        repeated_alert_risk = websocket.receive_json()

    validate_result(first_risk)
    validate_result(alert_risk)
    validate_result(repeated_alert_risk)
    assert event_message == {
        "type": "event",
        "event": {
            "timestamp": 2.0,
            "type": "alert",
            "reason": "Predictive alert: rising risk.",
            "severity": "amber",
        },
    }
    assert client.get("/session/events").json() == [event_message["event"]]


def test_calibration_completion_is_logged_only_after_calibration_was_observed() -> None:
    provider = SequenceProvider([_result(10.0, calibration_active=True), _result(11.0)])
    client = TestClient(create_app(provider=provider))

    assert client.post("/session/start").status_code == 200
    with client.websocket_connect("/ws/risk") as websocket:
        calibrating_risk = websocket.receive_json()
        complete_risk = websocket.receive_json()
        event_message = websocket.receive_json()

    validate_result(calibrating_risk)
    validate_result(complete_risk)
    assert event_message["type"] == "event"
    assert event_message["event"] == {
        "timestamp": 11.0,
        "type": "calibration_complete",
        "reason": "Driver calibration completed.",
        "severity": "none",
    }
    assert client.get("/session/events").json() == [event_message["event"]]
