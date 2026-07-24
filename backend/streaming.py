"""WebSocket streaming loop for risk messages."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from fastapi import WebSocket, WebSocketDisconnect

from cv.schema import build_result


class FrameDataProvider(Protocol):
    def get_frame_data(self, context_mode: str = "city") -> dict[str, Any]: ...


class StreamManager:
    """Send one schema-valid risk message approximately every 200 ms."""

    def __init__(
        self,
        websocket: WebSocket,
        *,
        context_mode: Callable[[], str],
        provider: FrameDataProvider | None = None,
        interval_seconds: float = 0.2,
        event_callback: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive.")
        self.websocket = websocket
        self._context_mode = context_mode
        self._provider = provider or _SafeResultProvider()
        self._interval_seconds = float(interval_seconds)
        self._event_callback = event_callback
        self._running = False

    async def start_streaming(self) -> None:
        self._running = True
        try:
            while self._running:
                data = await asyncio.to_thread(self._provider.get_frame_data, self._context_mode())
                await self.websocket.send_json(data)
                if self._event_callback is not None:
                    for event in self._event_callback(data):
                        await self.websocket.send_json({"type": "event", "event": event})
                await asyncio.sleep(self._interval_seconds)
        except WebSocketDisconnect:
            pass
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False


class _SafeResultProvider:
    def get_frame_data(self, context_mode: str = "city") -> dict[str, Any]:
        return build_result(context_mode)
