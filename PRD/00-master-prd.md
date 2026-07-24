# Predictive Driver Risk Cockpit — Master PRD

## Problem Statement

Driver drowsiness and distraction detection systems today are reactive — they only fire after a threshold is crossed, offering no predictive lead time. Existing solutions lack trajectory awareness, per-driver calibration, and explainable multi-signal fusion. At hackathon demos, systems built with single-threshold triggers appear simplistic and fail to demonstrate differentiation to judges. The team needs to build a demonstrably superior system in 3 hours that showcases predictive trajectory-based alerting as the core innovation.

## Solution

A webcam-only predictive driver risk cockpit that fuses multiple signals (PERCLOS, head pose, hand zone, yawn) into a single risk score, computes a trajectory slope to predict threshold crossings before they happen, and surfaces this via a real-time React dashboard. The system features per-driver calibration, context-aware threshold multipliers, and explainability — all designed to be demoed live to judges with clear visual differentiation from naive threshold-only detectors.

## User Stories

1. As a judge at a hackathon demo, I want to see a trajectory-based alert fire before a naive threshold-only detector would trigger, so that the predictive advantage is visually obvious.
2. As a judge, I want a toggle to overlay the naive detector's score next to the predictive score, so that I can directly compare lag between the two approaches.
3. As a judge, I want to see a counter showing how many seconds the predictive system saved vs. the naive detector, so that the time advantage is quantified.
4. As a demo presenter, I want a live risk gauge color-coded green/amber/red, so that the audience intuitively understands the driver's state at a glance.
5. As a demo presenter, I want per-signal breakdown bars showing which factor is contributing most to risk, so that explainability is built into the display.
6. As a demo presenter, I want a live trajectory chart scrolling in real time, so that trends (not just snapshots) are visible.
7. As a demo presenter, I want a calibration phase on session start that adapts thresholds to the driver's baseline, so that the system works for different individuals without manual tuning.
8. As a demo presenter, I want to switch context modes (highway/city/night) to adjust sensitivity, demonstrating environmental awareness.
9. As a demo presenter, I want the webcam feed displayed with landmark overlays, so that the audience sees exactly what the system is tracking.
10. As a demo presenter, I want confidence indicators (face detected, hands detected, lighting OK) displayed, so that signal quality issues are transparent.
11. As a demo presenter, I want event markers on the trajectory chart at alert timestamps with hoverable reason text, so that the audience sees exactly when and why alerts fired.
12. As a demo presenter, I want a one-click "explain this alert" feature that shows the plain-language reason string, demonstrating the system's transparency.
13. As the backend developer, I want a WebSocket schema that both the CV module and frontend agree on, so that parallel development is possible from minute zero.
14. As the backend developer, I want to stream fake/simulated data initially, so that the frontend developer can build against a live data feed before real CV signals are ready.
15. As the CV developer, I want to expose a simple `get_current_frame_result()` function, so that the backend can integrate my module as a library import without building a separate service.
16. As the frontend developer, I want a dark cockpit-style design with consistent green/amber/red color coding, so that the UI feels professional and demo-ready.
17. As the frontend developer, I want the WebSocket client to handle reconnection gracefully, so that the demo doesn't crash if the backend restarts.
18. As all three team members, I want clearly defined module boundaries and a shared integration contract, so that we can work in parallel without stepping on each other.

## Implementation Decisions

### Module Architecture

Three independent modules under a monorepo structure:

- **`/cv` (Person 1):** Python module using OpenCV + MediaPipe Face Mesh + Hands. Exposes `get_current_frame_result() -> dict` matching the shared schema. No web server — imported as a library by the backend.
- **`/backend` (Person 2):** FastAPI application with a `/ws/risk` WebSocket endpoint that streams risk data every ~200ms. Initially emits simulated sine-wave data, then swaps in real signals from the CV module. REST endpoints for session control.
- **`/frontend` (Person 3):** React dashboard with 5 visual zones (video, gauge, trajectory chart, signal bars, cockpit state). Connects to `/ws/risk` via WebSocket.

### Shared Integration Contract

All communication between modules uses a single WebSocket message schema (see execution plan for full JSON shape). Key fields:

- `risk_score` (0–100 fused score)
- `trend_slope` (rolling regression slope)
- `naive_score` (threshold-only score without trend anticipation — Tier S differentiator)
- `signals` (per-signal contribution: perclos, head_pose, hand_zone, yawn)
- `signal_quality` (face_detected, hands_detected, lighting_ok)
- `calibration` (in_progress, seconds_remaining)
- `alert` (active, severity, reason, time_saved_seconds)
- `context_mode` (set by frontend dropdown)

Person 1's CV module runs in the same Python process as Person 2's FastAPI (same venv, imported directly). No socket/queue layer between them.

### Deep Modules Identified

1. **Signal Fusion Engine** (Person 1) — encapsulates PERCLOS computation, head pose estimation, hand zone detection, and weighted fusion into a single `compute_risk(landmarks, context_mode) -> RiskResult` interface. Can be tested in isolation with prerecorded frame sequences.
2. **Trajectory Analyzer** (Person 1) — encapsulates rolling deque, linear regression, naive_score computation, and time_saved_seconds calculation. Takes a stream of `(timestamp, risk_score)` and outputs slope + alert predictions. Pure math — no camera dependency, testable with synthetic data.
3. **Calibration Engine** (Person 1) — encapsulates baseline averaging over the first 20–30s, per-signal threshold adjustment, and calibration state machine. Interface: `start_calibration() -> None`, `is_calibrating() -> bool`, `get_thresholds() -> dict`.
4. **WebSocket Stream Manager** (Person 2) — encapsulates the 200ms emit loop, fake data generation, and fallback logic for missing CV signals. Interface: `start_streaming(ws) -> None`, `stop_streaming() -> None`.
5. **Dashboard Layout Engine** (Person 3) — encapsulates the 5-zone responsive layout, dark theme, and consistent color system. Interface: component composition, no public API surface beyond React props.

### API Contracts

**WebSocket `/ws/risk` (Backend → Frontend):**
- Frequency: ~200ms per message
- Schema: as defined in the integration contract
- Initial data: simulated (sine-wave risk_score) until CV module is wired

**REST Endpoints (Backend):**
- `POST /session/start` — resets calibration window
- `POST /session/context` — body `{ "mode": "highway" | "city" | "night" }`
- `GET /session/events` — returns event log array

### Visualization Priorities (Frontend)

- Dark background, monospace-ish font for numeric readouts
- Green (< 40) / amber (40–70) / red (> 70) color scale on every widget
- Trajectory chart: risk_score (main line) + trend extrapolation (dashed, contrasting color) + shaded threshold band at 70
- Naive-detector toggle: overlays `naive_score` as third line
- Event markers: recharts ReferenceDot/ReferenceLine on the trajectory chart at alert timestamps

## Testing Decisions

### What Makes a Good Test

- Tests external behavior, not implementation details. For example: "given a sequence of risk scores with ascending trend, the trajectory analyzer should flag a pending alert before raw score crosses threshold" — not "the linear regression function uses deque of size N".
- Each deep module is tested in isolation with synthetic/recorded data — no camera, no network, no browser.
- Integration tests verify the schema contract end-to-end (CV output → backend → WebSocket message shape matches schema).

### Modules to Test

| Module | Test Type | Prior Art |
|--------|-----------|-----------|
| Trajectory Analyzer | Unit tests with synthetic time series | Standard pytest for math functions |
| Fusion Engine | Unit tests with mock landmark data | Standard pytest |
| Calibration Engine | Unit tests with simulated signal streams | Standard pytest |
| WebSocket Stream Manager | Integration test verifying message shape | FastAPI TestClient + pytest-asyncio |
| Frontend (dashboard) | Not tested — visual demo only | N/A for 3-hour hackathon |

### What We Are NOT Testing

- MediaPipe landmark detection accuracy (already validated by Google)
- Frontend component unit tests (time constraint)
- End-to-end tests across all three modules simultaneously

## Out of Scope

- Mobile app or native deployment — web-only demo
- Database persistence — in-memory only
- Authentication or multi-user support — single-session demo
- Real vehicle hardware integration (CAN bus, OBD-II, etc.)
- ML model training — using pre-trained MediaPipe models only
- Audio alerts or TTS — visual indicators only
- Production-grade error handling, logging, or monitoring
- iOS/Android webcam compatibility — desktop Chrome/Firefox only
- Long-running sessions beyond demo duration (~5-10 minutes)
- Legacy browser support

## Further Notes

### Differentiation Strategy for Judges

The entire originality argument rests on three features that the team must protect above all else:

1. **Trajectory-based alerting** (time_saved_seconds counter) — demonstrates predictive lead time
2. **Naive-detector toggle** — visually proves the predictive system beats threshold-only approaches
3. **Trajectory chart with trend line** — makes the predictive advantage visible in real time

Everything else (yawn signal, explain-on-click, event markers) is support — cut these first if time runs short.

### Demo Script Suggestion

1. Start session → show calibration phase counting down (20s)
2. After calibration, sit still → show low risk, flat trend
3. Simulate drowsy motion (slow head drop + eyes half-closed) → watch risk_score rise, trend slope turn positive
4. Alert fires before naive_score crosses threshold → toggle naive overlay to show the lag
5. Point to time_saved_seconds counter as the quantified advantage
6. Click "explain this alert" to show the plain-language reason
7. Switch context to "night" mode → demonstrate increased sensitivity

### Sync Cadence

All three team members sync briefly at 0:30, 1:00, 1:50, and 2:30. Hard feature freeze at 2:30 regardless of what's unfinished. Last 30 minutes = rehearsal only.
