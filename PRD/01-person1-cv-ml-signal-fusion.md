# Predictive Driver Risk Cockpit — Person 1: CV / ML / Signal Fusion

## Problem Statement

The core differentiation of the demo is trajectory-based predictive alerting. Person 1 owns the signal pipeline that converts raw webcam frames into the fused risk score, trajectory slope, naive score, and explainability payload. Without this module, the backend has nothing to stream and the frontend has nothing to display. The work must produce a clean interface (`get_current_frame_result() -> dict`) that the FastAPI backend can import directly, with no web server or IPC layer.

## Solution

A Python module using OpenCV + MediaPipe Face Mesh + Hands that runs a webcam capture loop, extracts PERCLOS, head pose, hand zone, and yawn signals, fuses them into a weighted risk score, computes a trajectory slope via rolling linear regression, and outputs the naive score (same fusion without slope-based anticipation). The module also handles per-driver calibration (20–30s baseline) and context-aware threshold multipliers. All output matches the shared WebSocket schema.

## User Stories

1. As the backend developer, I want Person 1's module to expose a synchronous `get_current_frame_result() -> dict` function, so that I can call it from my FastAPI background loop without async complexity.
2. As the backend developer, I want the output dict to match the shared integration contract exactly, so that I can pass it through to the WebSocket without transformation.
3. As the presenter, I want PERCLOS computed from eye aspect ratio (EAR) over a rolling window, so that sustained eye closure (drowsiness) drives risk score upward.
4. As the presenter, I want head pose computed via solvePnP from facial landmarks, so that yaw/pitch distraction (looking away from road) contributes to risk.
5. As the presenter, I want hand zone detection that classifies hands as on-wheel / off-wheel / phone-near-face, so that distracted driving is captured.
6. As the presenter, I want a yawn signal via mouth aspect ratio (MAR), so that fatigue is detected (lowest priority — cut first).
7. As the presenter, I want the four signals fused with configurable weights (default: PERCLOS 40%, head pose 30%, hand zone 20%, yawn 10%), so that the risk score reflects multiple factors.
8. As the presenter, I want a `trend_slope` computed from rolling linear regression over the last N risk scores, so that upward trends are detected before the score crosses threshold.
9. As the presenter, I want a `naive_score` computed from the same fusion but without trend-based anticipation, so that the frontend can overlay it and visually prove the predictive advantage.
10. As the presenter, I want `time_saved_seconds` calculated as the difference between when the predictive system fires vs. when naive_score alone would have crossed threshold, so that the advantage is quantified.
11. As the presenter, I want a calibration phase (20–30s) on session start that averages baseline signal values and adjusts per-signal thresholds (e.g., threshold = baseline * 1.4), so that the system adapts to different drivers.
12. As the presenter, I want `calibration.in_progress` and `seconds_remaining` in the output, so that the frontend can show a calibration progress indicator.
13. As the presenter, I want a context mode multiplier (highway/city/night) that adjusts threshold sensitivity (e.g., night = 15% more sensitive to PERCLOS), so that environmental awareness is demonstrated.
14. As the presenter, I want `signal_quality` flags (face_detected, hands_detected, lighting_ok) in the output, so that the frontend can show confidence indicators when signals degrade.
15. As the presenter, I want an explainability payload: a plain-language reason string when an alert fires (e.g., "sustained eye closure 68% + head tilt 12° for 3.1s"), so that judges see the system is transparent.
16. As the tester, I want the trajectory analyzer and fusion engine to be testable with synthetic data (no camera), so that I can verify correctness offline.

## Implementation Decisions

### Module Interface

The module exposes a single entry point:

```
get_current_frame_result(context_mode: str = "city") -> dict
```

Called by the backend in a loop. Returns a dict matching the shared WebSocket schema. The module internally manages webcam capture, landmark detection, rolling windows, and calibration state.

### Deep Modules to Extract

1. **Signal Fusion Engine** (`fusion.py`)
   - Takes raw landmarks + per-signal values
   - Computes weighted risk_score
   - Interface: `compute_risk(perclos, head_pose, hand_zone, yawn, weights) -> float`

2. **Trajectory Analyzer** (`trajectory.py`)
   - Maintains rolling deque of `(timestamp, risk_score)`
   - Computes linear regression slope → `trend_slope`
   - Computes `naive_score` (same signals, no trend contribution)
   - Detects threshold crossing and computes `time_saved_seconds`
   - Interface: `TrajectoryAnalyzer.push(timestamp, risk_score) -> dict` containing `{trend_slope, naive_score, alert_active, time_saved_seconds}`

3. **Calibration Engine** (`calibration.py`)
   - State machine: IDLE → CALIBRATING (20–30s) → CALIBRATED
   - Averages signal values over calibration window
   - Outputs per-signal thresholds
   - Interface: `CalibrationEngine.start()`, `push_signals(signals)`, `is_calibrating() -> bool`, `get_thresholds() -> dict`

4. **Signal Extractors** — each in its own file:
   - `perclos.py`: EAR-based eye closure detection over rolling window
   - `head_pose.py`: solvePnP-based yaw/pitch estimation
   - `hand_zone.py`: hand landmark → wheel zone classification
   - `yawn.py`: MAR-based mouth openness

### Alert Logic

Alert fires when `risk_score + trend_slope * LOOKAHEAD_STEPS` crosses the threshold. The `naive_score` is the same risk_score without any trend projection — it only fires when the raw score itself crosses threshold. The frontend toggle reveals this gap.

### Calibration State Machine

```
IDLE → (POST /session/start) → CALIBRATING (countdown 20–30s) → CALIBRATED
```

During CALIBRATING, output `calibration.seconds_remaining`. During CALIBRATED, thresholds are `baseline_mean * 1.4` per signal.

### Context Mode

Set via `POST /session/context`. Stored in the module as a thread-safe string. Signal thresholds multiplied by:
- `city`: 1.0 (neutral)
- `highway`: 0.85 (less sensitive — higher speeds need fewer false positives)
- `night`: 1.15 (more sensitive — reduced visibility)

### Critical: Protect the trajectory work

Phase 1.4 (trajectory slope + naive_score + time_saved_seconds) is the highest-impact block. If behind, cut yawn/MAR first (Phase 1.6), then context multiplier, then explainability. Never cut the trajectory analyzer.

## Testing Decisions

### What Makes a Good Test

- Unit tests use synthetic/simulated data, not a live camera
- Trajectory analyzer tests: input a sequence of scores with known linear trend, verify slope matches, verify alert triggers at correct point, verify time_saved_seconds calculation
- Fusion tests: input known signal values with known weights, verify risk_score matches `sum(signal_i * weight_i)`
- Calibration tests: push known signal values, verify baseline average is correct, verify threshold = baseline * 1.4

### Modules to Test

| Module | Test Type | Approach |
|--------|-----------|----------|
| Trajectory Analyzer | Unit (pytest) | Synthetic time series with known slope |
| Fusion Engine | Unit (pytest) | Known weights + known signals |
| Calibration Engine | Unit (pytest) | Simulated signal stream |
| PERCLOS extractor | Unit (pytest) | Mock eye landmarks with known aspect ratios |
| Head pose extractor | Unit (pytest) | Mock face landmarks with known angles |

### Prior Art

Standard `pytest` for Python math modules. Fixtures for synthetic landmark data. The trajectory analyzer is the most important to test — verify its behavior edge cases: flat trend, steep upward trend, sudden drop, empty window, single data point.

## Out of Scope

- Training custom ML models — using pre-trained MediaPipe only
- Iris tracking or gaze estimation
- Emotion detection
- Running as a separate process or container — must be a library import
- GPU acceleration beyond what OpenCV's DNN module provides out of box
- macOS/Linux camera compatibility issues beyond basic OpenCV
- Audio or microphone input

## Further Notes

### Cut Order (if behind schedule)

1. Yawn/MAR signal — lowest signal value, cut first
2. Context multiplier — hardcode to "city" if out of time
3. Explainability payload string — signal bars alone provide enough explainability
4. Hand zone refinement — rough on/off-wheel heuristic is sufficient

### Never Cut

Trajectory slope + naive_score + time_saved_seconds. These three are the entire originality argument.

### Physical Demo Rehearsal

During testing, physically rehearse the drowsy + distracted motions that trigger alerts. The demo needs to reliably show the trajectory-before-naive difference on cue. Practice the exact head drop, eye closure, and hand-off-wheel movements to ensure repeatable triggering.
