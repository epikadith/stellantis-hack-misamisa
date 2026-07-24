# Predictive Driver Risk Cockpit — Person 2: Backend (FastAPI + WebSocket)

## Problem Statement

The frontend needs a live data stream of risk information, and the CV module needs a host process to invoke it. Person 2 owns the FastAPI backend that bridges CV signal extraction and frontend visualization. The backend must stream data every ~200ms via WebSocket, provide REST endpoints for session control, and support a gradual integration path where simulated data is replaced by real CV signals as they become ready — without ever blocking the frontend developer.

## Solution

A FastAPI application with a `/ws/risk` WebSocket endpoint that streams JSON risk data at ~200ms intervals. Initially emits fully simulated data (sine-wave risk_score, randomized signals) to unblock Person 3 immediately. Gradually swaps in real signal values from Person 1's `get_current_frame_result()` as they become available — falling back to simulated values for any missing fields. Provides REST endpoints for session lifecycle and context control. Runs Person 1's CV module in-process within the same Python venv.

## User Stories

1. As the frontend developer, I want a WebSocket at `/ws/risk` that emits data every ~200ms from the moment of connection, so that I can build and test the dashboard immediately.
2. As the frontend developer, I want the initial data stream to be fully simulated (sine-wave risk_score, randomized signals), so that I am not blocked waiting for real CV signals.
3. As the frontend developer, I want the WebSocket message schema to match the shared integration contract exactly, so that I can parse and render data without transformation logic.
4. As the frontend developer, I want `POST /session/start` to reset the calibration window, so that the user can re-calibrate for a new driver.
5. As the frontend developer, I want `POST /session/context` to accept `{ "mode": "highway" | "city" | "night" }`, so that the frontend dropdown controls context sensitivity.
6. As the frontend developer, I want `GET /session/events` to return the event log, so that I can render past alerts and calibration milestones.
7. As the CV developer, I want the backend to import my module as a Python library in the same process, so that we avoid socket/IPC complexity.
8. As the CV developer, I want the backend to gracefully handle missing or partial CV signals with fallback to simulated data, so that partial integration works without crashes.
9. As the presenter, I want the WebSocket connection to be stable and reconnectable, so that the demo doesn't break if the backend restarts.
10. As the presenter, I want events (alert fired, calibration completed) pushed over the WebSocket, so that the frontend can react in real time without polling.

## Implementation Decisions

### Architecture

```
[CV Module] ←import→ [FastAPI Backend] ←WebSocket 200ms→ [React Frontend]
   (Person 1)          (Person 2)                       (Person 3)
```

Same Python process, same venv. The backend calls `get_current_frame_result()` in a background `asyncio` loop. If the CV module isn't ready or raises an exception, the backend falls back to its own simulation function for any missing fields.

### WebSocket Stream Manager (Deep Module)

Encapsulated in a `StreamManager` class:

```python
class StreamManager:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self._running = False
        self._cv_module = None  # imported lazily

    async def start_streaming(self):
        self._running = True
        while self._running:
            data = self._get_frame_data()
            await self.ws.send_json(data)
            await asyncio.sleep(0.2)

    def _get_frame_data(self) -> dict:
        # Try CV module first, fill gaps with simulation
        ...
    def stop(self):
        self._running = False
```

### Fallback Strategy

For each field in the schema, the backend attempts to get a real value from the CV module. If the field is missing, `None`, or the module raises, the backend substitutes a simulated value. Simulated values use a sine wave for risk_score (period ~30s, amplitude 0–100) and bounded random noise for signals. This ensures the frontend always receives valid data.

### Session State

In-memory dictionary:

```python
session = {
    "calibrating": False,
    "context_mode": "city",
    "events": [],  # list of event objects
    "stream_manager": None
}
```

### Endpoints

| Method | Path | Behavior | Request Body |
|--------|------|----------|-------------|
| WebSocket | `/ws/risk` | Streams risk data every 200ms | N/A |
| POST | `/session/start` | Resets calibration, clears events | Empty |
| POST | `/session/context` | Updates context mode | `{ "mode": "highway" \| "city" \| "night" }` |
| GET | `/session/events` | Returns event log array | N/A |

### Event Push Over WebSocket

When an alert fires or calibration completes, the backend pushes a lightweight event message in addition to the regular risk stream. Two options (discuss with Person 3):

- **Option A**: Add an `event` field to the regular payload (e.g., `"event": { "type": "alert", ... }`), null when no event
- **Option B**: Send a separate compact message type over the same WebSocket

### Event Log

In-memory list. Each entry:

```json
{ "timestamp": 1721800012.4, "type": "alert" | "calibration_complete", "reason": "...", "severity": "amber" | "red" }
```

Appended by the backend when alert fires or calibration finishes.

## Testing Decisions

### What Makes a Good Test

- Integration tests verify the WebSocket emits messages matching the schema using FastAPI's TestClient
- Tests should verify fallback behavior: when CV module returns partial data, missing fields are filled with simulation
- Tests should verify session lifecycle: start → calibrating → calibrated, context mode changes reflected in output
- No browser-based testing — pure Python async tests

### Modules to Test

| Module | Test Type | Approach |
|--------|-----------|----------|
| WebSocket endpoint | Integration (pytest + httpx) | Connect via TestClient, verify 5 consecutive messages match schema |
| Fallback logic | Unit (pytest) | Mock CV module returning partial data, verify filled output |
| Session endpoints | Integration (pytest) | POST /session/start → verify calibration reset; POST /session/context → verify mode stored |
| Event log | Unit (pytest) | Push events, verify GET /session/events returns them |

### Prior Art

FastAPI's built-in `TestClient` (from `httpx`) for WebSocket testing. Standard `pytest` fixtures for mock CV modules.

## Out of Scope

- Database persistence — in-memory only, session data lost on restart
- Authentication, CORS beyond wildcard for demo, rate limiting
- Multiple concurrent sessions — single-session demo
- HTTPS/WSS — plain HTTP/WS for localhost demo
- Containerization or deployment — run via `uvicorn` directly
- Message queuing (Redis, RabbitMQ, etc.)
- Health check endpoints

## Further Notes

### Build Order

1. Phase 2.1 (0:10–0:25): Scaffold FastAPI app with fake data stream — this is critical because it unblocks Person 3
2. Phase 2.2 (0:25–0:55): Import CV module, replace PERCLOS/head-pose with real values, keep fallback for missing fields
3. Phase 2.3 (0:55–1:50): Full real integration — all 4 signals + trajectory + naive_score flowing live
4. Phase 2.4 (1:50–2:20): Calibration + context endpoints wired live to CV module
5. Phase 2.5 (2:20–2:35): Event log persistence + push over WebSocket

### Key Integration Risks

- Person 1 might not finish all signals in time → fallback strategy handles this
- CV module might raise exceptions (no camera, bad frame) → wrap in try/except
- WebSocket might disconnect → FastAPI handles this natively; `send_json` will raise `WebSocketDisconnect` which you should catch and clean up

### Keep a Terminal Open

During the final rehearsal, watch raw WebSocket traffic (or use a quick `print()` per message) to visually confirm data is flowing. Nothing worse than discovering at demo time that the frontend is looking at stale mock data.
