"""Application factory and Phase 1 WebSocket endpoint."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .cv_provider import CVFrameProvider
from .streaming import FrameDataProvider, StreamManager


@dataclass
class SessionState:
    """Thread-safe state shared by REST control and WebSocket stream calls."""

    context_mode: str = "city"
    calibrating: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)
    _alert_active: bool = field(default=False, init=False, repr=False)
    _calibration_observed: bool = field(default=False, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def get_context_mode(self) -> str:
        with self._lock:
            return self.context_mode

    def set_context_mode(self, context_mode: str) -> None:
        with self._lock:
            self.context_mode = context_mode

    def start_calibration(self) -> None:
        with self._lock:
            self.calibrating = True
            self.events.clear()
            self._alert_active = False
            self._calibration_observed = False

    def record_events(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """Append and return events created by this one risk frame."""
        with self._lock:
            created: list[dict[str, Any]] = []
            timestamp = float(result["timestamp"])
            alert = result["alert"]
            alert_active = bool(alert["active"])
            if alert_active and not self._alert_active:
                created.append(
                    {
                        "timestamp": timestamp,
                        "type": "alert",
                        "reason": alert["reason"] or "Predictive risk alert.",
                        "severity": alert["severity"],
                    }
                )
            self._alert_active = alert_active

            calibration = result["calibration"]
            calibration_active = bool(calibration["in_progress"])
            if calibration_active:
                self._calibration_observed = True
                self.calibrating = True
            elif self._calibration_observed:
                created.append(
                    {
                        "timestamp": timestamp,
                        "type": "calibration_complete",
                        "reason": "Driver calibration completed.",
                        "severity": "none",
                    }
                )
                self._calibration_observed = False
                self.calibrating = False

            self.events.extend(created)
            return [dict(event) for event in created]

    def get_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(event) for event in self.events]


class ContextRequest(BaseModel):
    mode: Literal["highway", "city", "night"]


def create_app(
    *,
    provider: FrameDataProvider | None = None,
    interval_seconds: float = 0.2,
) -> FastAPI:
    app = FastAPI(title="Predictive Driver Risk Cockpit")
    app.state.session = SessionState()
    app.state.provider = provider or CVFrameProvider()

    @app.websocket("/ws/risk")
    async def risk_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        receive_task = asyncio.create_task(_receive_camera_frames(websocket, app.state.provider))
        manager = StreamManager(
            websocket,
            context_mode=app.state.session.get_context_mode,
            provider=app.state.provider,
            interval_seconds=interval_seconds,
            event_callback=app.state.session.record_events,
        )
        try:
            await manager.start_streaming()
        finally:
            receive_task.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect):
                await receive_task

    @app.post("/session/start")
    async def start_session() -> dict[str, bool | str]:
        app.state.session.start_calibration()
        started = await asyncio.to_thread(_call_provider, app.state.provider, "start_calibration")
        return {
            "calibrating": app.state.session.calibrating,
            "cv_calibration_started": started,
            "context_mode": app.state.session.get_context_mode(),
        }

    @app.post("/session/context")
    async def set_session_context(request: ContextRequest) -> dict[str, bool | str]:
        app.state.session.set_context_mode(request.mode)
        updated = await asyncio.to_thread(
            _call_provider,
            app.state.provider,
            "set_context_mode",
            request.mode,
        )
        return {"context_mode": request.mode, "cv_context_updated": updated}

    @app.get("/session/events")
    async def get_session_events() -> list[dict[str, Any]]:
        return app.state.session.get_events()

    return app


def _call_provider(provider: FrameDataProvider, name: str, *args: str) -> bool:
    method = getattr(provider, name, None)
    if not callable(method):
        return False
    try:
        return bool(method(*args))
    except Exception:
        return False


async def _receive_camera_frames(websocket: WebSocket, provider: FrameDataProvider) -> None:
    """Receive browser JPEG frames without blocking the outbound risk stream."""
    submit_frame = getattr(provider, "submit_frame_bytes", None)
    if not callable(submit_frame):
        return
    try:
        while True:
            message = await websocket.receive()
            frame_bytes = message.get("bytes")
            if frame_bytes:
                await asyncio.to_thread(submit_frame, frame_bytes)
    except WebSocketDisconnect:
        return


app = create_app()
