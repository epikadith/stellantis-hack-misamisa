# Predictive Driver Risk Cockpit — Person 3: Frontend React Dashboard

## Problem Statement

The judges need to see the predictive advantage of trajectory-based alerting visually, in real time. Person 3 owns the React dashboard that renders live risk data from the backend WebSocket into a cockpit-like display. The dashboard must make the trajectory-vs-naive gap obvious at a glance, show per-signal breakdowns, confidence indicators, and calibration state — all within a polished dark-themed UI that looks demo-ready in 3 hours.

## Solution

A React dashboard with 5 visual zones (video feed, risk gauge, trajectory chart, signal breakdown bars, cockpit state) connected to the backend via WebSocket at `/ws/risk`. Uses recharts for the trajectory chart (centerpiece), a circular SVG gauge for risk score, and consistent green/amber/red color coding across all widgets. Builds against mock data initially via the real WebSocket (pointing at Person 2's fake-data stream), then seamlessly transitions to real data as signals come online.

## User Stories

1. As a judge, I want to see a live trajectory chart with risk_score as the main line and a trend line in contrasting color, so that I can see risk trending upward before an alert fires.
2. As a judge, I want a shaded threshold band on the chart (e.g., red zone above 70), so that I can see when the score enters dangerous territory.
3. As a judge, I want a toggle switch labeled "Show naive detector" that overlays `naive_score` as a third line, so that I can visually compare how the predictive system anticipates vs. a threshold-only detector lags behind.
4. As a judge, I want a counter showing "Predicted Xs before threshold crossing" when an alert fires, so that the time saved is quantified.
5. As a judge, I want small confidence status indicators ("Face: detected", "Lighting: good") that dim or warn when signal quality drops, so that I can assess data reliability.
6. As a presenter, I want a circular risk gauge (green → amber → red arc) driven by `risk_score`, so that the audience intuitively understands the driver's state.
7. As a presenter, I want the gauge replaced by a calibration progress ring showing `seconds_remaining` countdown during calibration, so that calibration state is obvious.
8. As a presenter, I want 4 horizontal bars (PERCLOS, head pose, hand zone, yawn) driven by the `signals` object, live-updating with color by contribution level, so that per-signal breakdown is visible.
9. As a presenter, I want the webcam feed displayed with landmark overlays if coordinates are available, or raw video if not, so that the audience sees what the system is tracking.
10. As a presenter, I want event markers (dots/lines) on the trajectory chart at alert timestamps with hover text showing the reason, so that I don't need a separate log table.
11. As a presenter, I want a context mode dropdown (Highway / City / Night) that calls `POST /session/context`, so that I can demonstrate environmental awareness.
12. As a presenter, I want clicking on an active alert to expand the plain-language `alert.reason` string, demonstrating explainability.
13. As a presenter, I want cockpit response icons (chime, seat vibration, "reduce speed" nudge) that light up when `alert.active` is true, so that the audience sees multi-modal alerting.
14. As a developer, I want to build against simulated data from minute zero via the real WebSocket endpoint, so that I can develop all features without waiting for real CV signals.
15. As a developer, I want the WebSocket client to handle reconnection gracefully, so that the demo doesn't crash if the backend restarts.
16. As a developer, I want a dark cockpit-style design with consistent green/amber/red color coding across all widgets, so that the UI looks professional without per-widget styling decisions.

## Implementation Decisions

### Technology Choices

- **Framework:** React with Vite (fast setup, hot reload)
- **Charts:** recharts (React-native charting, supports ReferenceDot/ReferenceLine for event markers)
- **WebSocket:** Native `WebSocket` API (no library needed)
- **Styling:** CSS modules or a lightweight approach — no heavy framework (time constraint)
- **Video:** Browser `getUserMedia` API for webcam, canvas overlay for landmarks if exposed in payload

### Dashboard Layout — 5 Zones

```
┌──────────────────────────────────────────────────┐
│  ┌──────────────┐ ┌─────────┐ ┌────────────────┐ │
│  │  Video Feed   │ │  Gauge  │ │  Signal Bars   │ │
│  │  (webcam +    │ │  (risk  │ │  PERCLOS  ████ │ │
│  │   landmarks)  │ │  0–100) │ │  HeadPose ██   │ │
│  └──────────────┘ └─────────┘ │  HandZone █    │ │
│                                │  Yawn     ████ │ │
│                                └────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │        Trajectory Chart (centerpiece)          │ │
│  │  ╱╲    risk_score ─── trend - - - naive . . .  │ │
│  │ ╱  ╲  ▓▓▓▓▓▓▓▓▓▓▓▓▓ (threshold band 70+)      │ │
│  │                ● event marker                  │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │  Cockpit Bar: time-saved | confidence | mode   │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### Color System (Consistent Across All Widgets)

- **Green:** `risk_score < 40`, low signal contribution
- **Amber:** `risk_score 40–70`, medium signal contribution
- **Red:** `risk_score > 70`, high signal contribution, `alert.active === true`
- Chart line colors: risk_score = bright cyan/blue, trend = orange/yellow dashed, naive = gray/white dotted
- Background: dark (#0a0a0f or similar)
- Font: monospace for numeric readouts

### Color constants defined once in a theme object:

```javascript
const THEME = {
  bg: '#0a0a0f',
  surface: '#14141f',
  green: '#00e676',
  amber: '#ff9100',
  red: '#ff1744',
  chartLine: '#00e5ff',
  trendLine: '#ff9100',
  naiveLine: '#9e9e9e',
  text: '#e0e0e0',
  textDim: '#666666',
}
```

### Trajectory Chart (Centerpiece — Protect This Time)

- Maintain a rolling buffer of last ~100 data points
- X-axis: time (relative seconds)
- Y-axis: risk score 0–100
- Three lines: risk_score (solid), trend line (dashed, derived from `trend_slope`), naive_score (dotted, shown only when toggle is on)
- Shaded rect covering y > 70 for threshold band
- Event markers: recharts `ReferenceDot` at alert timestamps, `Tooltip` shows `reason`

### Naive-Detector Toggle (Tier S #2)

A toggle switch above the chart:
- OFF (default): Only risk_score + trend line visible
- ON: `naive_score` line appears, visibly lagging behind the predictive system
- This is the single most important visual for judges — protect it

### WebSocket Client Hook

```javascript
function useRiskStream(url) {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onopen = () => setConnected(true);
    ws.onmessage = (e) => setData(JSON.parse(e.data));
    ws.onclose = () => {
      setConnected(false);
      // reconnect after 1s
      setTimeout(() => { /* re-initialize */ }, 1000);
    };
    return () => ws.close();
  }, [url]);

  return { data, connected };
}
```

### Reconnection Strategy

On disconnect: show a "Reconnecting..." overlay (don't hide the last data), attempt reconnect every 2s, max 10 attempts. After 10 failures, show "Connection lost" — but for demo purposes this should never happen.

### Video Overlay Decision

Two options, decide with Person 1/2:
- **Option A (simpler):** Use browser `getUserMedia` directly for the video feed. No landmark overlay unless coordinates are in the WebSocket payload (unlikely at this framerate). Pros: zero backend dependency. Cons: no landmarks.
- **Option B:** Backend forwards processed frames as base64 or MJPEG. Pros: landmarks drawn server-side. Cons: bandwidth, latency.

**Recommendation: Option A.** The video zone is a secondary visual — landmarks drawn on the feed are nice-to-have but not worth the complexity.

### Event Markers on Chart (Replace Separate Log Table)

When `alert.active` transitions from false to true, add a visible marker (ReferenceDot) on the trajectory chart at the current point. Hovering shows the `reason` string via recharts Tooltip. This avoids needing a separate scrolling log table — save screen space.

## Testing Decisions

### What Makes a Good Test

For a 3-hour hackathon demo, formal frontend testing is not a priority. "Testing" means:
- Manually verify every widget responds to WebSocket data changes
- Verify the naive-detector toggle shows/hides the third line
- Verify calibration state replaces gauge with countdown ring
- Verify color coding matches THEME consistently across all widgets
- Verify WebSocket reconnection doesn't crash the app

### What We Are NOT Testing

- Unit tests for React components
- Snapshot tests
- End-to-end tests
- Browser compatibility beyond Chrome

## Out of Scope

- Mobile responsive layout — desktop-only demo
- Production bundling or minification concerns
- State management libraries (Redux, Zustand) — React state + hook is sufficient
- CSS-in-JS libraries — plain CSS modules or inline styles
- Animations beyond simple CSS transitions on value changes
- Audio alerts or text-to-speech
- Touch interactions — mouse-only demo
- Dark/light mode toggle — dark only

## Further Notes

### Build Order

1. Phase 3.1 (0:10–0:30): App shell + WebSocket client + 5 empty zone placeholders — get the connection working first
2. Phase 3.2 (0:30–1:00): Trajectory chart with all 3 lines + threshold band + naive toggle — **protect this time block, this is the centerpiece**
3. Phase 3.3 (1:00–1:20): Gauge + calibration countdown ring
4. Phase 3.4 (1:20–1:45): Per-signal breakdown bars
5. Phase 3.5 (1:45–2:00): Video feed with getUsermedia
6. Phase 3.6 (2:00–2:15): Time-saved counter + confidence indicators
7. Phase 3.7 (2:15–2:30): Event markers on chart + cockpit response icons
8. Phase 3.8 (2:30–2:45): Context dropdown + explain-on-click
9. Phase 3.9 (2:45 onward): Visual polish — colors, transitions, smoothness

### Cut Order (if behind schedule)

1. Explain-on-click detail — per-signal bars already show contribution
2. Context dropdown — hardcode "city" mode
3. Event markers — chart is still informative without markers
4. Video landmark overlay — raw video is fine
5. Cockpit response icons — icing on the cake

### Never Cut

The trajectory chart with all 3 lines + naive-detector toggle + time-saved counter. That trio is the entire originality argument that wins the demo.

### Rehearsal

You're driving the screen during the pitch. Practice the sequence: start → calibrate → simulate drowsiness → alert fires → toggle naive → point at time saved. Know exactly where each UI element is without looking.
