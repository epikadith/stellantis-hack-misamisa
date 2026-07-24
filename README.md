# Predictive Driver Risk Cockpit

## CV integration contract

Person 2 imports the CV package directly:

```python
from cv import get_current_frame_result

message = get_current_frame_result(context_mode="city")
```

The returned dictionary is ready to send unchanged with FastAPI's
`WebSocket.send_json`.  It has these top-level fields: `timestamp`,
`risk_score`, `trend_slope`, `naive_score`, `signals`, `signal_quality`,
`calibration`, `alert`, and `context_mode`.

`signals` always contains `perclos`, `head_pose`, `hand_zone`, and `yawn`.
The supported context modes are `city`, `highway`, and `night`.

Install the camera runtime before running the live CV pipeline:

```powershell
python -m pip install -e ".[cv,dev]"
```

Run the Phase 0 contract tests with:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

The public import path stays free of camera imports until a live capture call,
so the backend's simulated-data fallback remains usable when a webcam is not
available.
