# Predictive Driver Risk Cockpit

## Person 2 handoff

Install the locked project environment and run the full test suite with `uv`:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"  # avoids a machine-level cache collision
uv sync --extra cv --extra dev
uv run pytest -q
```

The direct backend import and initialization are synchronous; no worker,
server, or IPC setup is required:

```python
from cv import close_pipeline, get_current_frame_result, set_context_mode, start_calibration

start_calibration()                         # optional: starts the 25-second baseline window
set_context_mode("night")                   # city | highway | night
message = get_current_frame_result("night")
await websocket.send_json(message)           # send unchanged

# Call close_pipeline() during FastAPI shutdown.
```

`get_current_frame_result(context_mode: str = "city") -> dict` lazily opens
the webcam, runs MediaPipe Face Mesh and Hands, and always returns the exact
schema below. It is safe to call repeatedly from the backend stream loop. The
context is protected by a lock; `city`, `highway`, and `night` apply risk
multipliers of `1.0`, `0.85`, and `1.15` respectively. Missing cameras,
frames, or landmarks return a conservative, schema-valid payload instead of
raising.

```json
{
  "timestamp": 1721800012.4,
  "risk_score": 60.0,
  "trend_slope": 10.0,
  "naive_score": 60.0,
  "signals": {"perclos": 60.0, "head_pose": 60.0, "hand_zone": 60.0, "yawn": 60.0},
  "signal_quality": {"face_detected": true, "hands_detected": true, "lighting_ok": true},
  "calibration": {"in_progress": false, "seconds_remaining": 0.0},
  "alert": {
    "active": true,
    "severity": "amber",
    "reason": "Predictive alert: perclos 60% + head pose 60%; rising 10.0 risk points/s.",
    "time_saved_seconds": 1.0
  },
  "context_mode": "city"
}
```

Dependencies are Python 3.10+, NumPy, OpenCV, MediaPipe `0.10.21`, and
pytest for tests. They are declared in `pyproject.toml` and locked in
`uv.lock`.

## Demo rehearsal

Use the dashboard with the webcam as follows: begin neutral, then sustain eye
closure while dropping/turning the head. The predictive alert should appear
while `naive_score` is still below 70; maintain the pose until the naive score
crosses. Finally switch the context selector to `night` to show increased
sensitivity. The automated rising-risk test exercises the same order without
requiring a camera.
