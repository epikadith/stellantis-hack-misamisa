import './RiskGauge.css';

/* ── SVG arc helpers ─────────────────────────────────── */

const CX = 120;
const CY = 108;
const R = 82;
const STROKE = 10;
const START_ANGLE = -135;    // lower-left  (0° = 12 o'clock, CW positive)
const END_ANGLE = 135;       // lower-right
const SWEEP = END_ANGLE - START_ANGLE; // 270°
const ARC_LEN = (SWEEP / 360) * 2 * Math.PI * R;

const TICKS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
const LABELS = [0, 25, 50, 75, 100];

function polar(cx, cy, r, deg) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arc(cx, cy, r, a, b) {
  const s = polar(cx, cy, r, a);
  const e = polar(cx, cy, r, b);
  const large = Math.abs(b - a) > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}

function color(v) {
  if (v < 40) return 'var(--safe)';
  if (v < 70) return 'var(--warn)';
  return 'var(--danger)';
}

function label(v) {
  if (v < 40) return 'LOW';
  if (v < 70) return 'MODERATE';
  return 'HIGH';
}

/* ── Component ───────────────────────────────────────── */

export default function RiskGauge({ riskScore = 0, trendSlope = 0, calibration }) {
  const c = color(riskScore);
  const offset = ARC_LEN * (1 - riskScore / 100);

  const trendArrow =
    trendSlope > 0.5 ? '▲' : trendSlope < -0.5 ? '▼' : '●';
  const trendColor =
    trendSlope > 0.5
      ? 'var(--danger)'
      : trendSlope < -0.5
        ? 'var(--safe)'
        : 'var(--text-muted)';

  const isCalibrating = calibration?.in_progress ?? false;

  return (
    <div className="gauge-panel panel">
      <div className="panel-header">Risk Score</div>

      <svg viewBox="0 0 240 175" className="gauge-svg">
        <defs>
          <filter id="g-glow">
            <feGaussianBlur stdDeviation="3.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* decorative rings */}
        <circle cx={CX} cy={CY} r={R + STROKE / 2 + 5}
          fill="none" stroke="rgba(50,50,85,0.15)" strokeWidth={0.5} />
        <circle cx={CX} cy={CY} r={R - STROKE / 2 - 28}
          fill="none" stroke="rgba(50,50,85,0.12)" strokeWidth={0.5}
          strokeDasharray="3 5" />

        {/* background arc */}
        <path d={arc(CX, CY, R, START_ANGLE, END_ANGLE)}
          fill="none" stroke="rgba(50,50,80,0.32)" strokeWidth={STROKE}
          strokeLinecap="round" />

        {/* value arc */}
        <path d={arc(CX, CY, R, START_ANGLE, END_ANGLE)}
          fill="none" stroke={c} strokeWidth={STROKE} strokeLinecap="round"
          strokeDasharray={ARC_LEN} strokeDashoffset={offset}
          filter="url(#g-glow)"
          className="gauge-arc" />

        {/* ticks */}
        {TICKS.map((t) => {
          const a = START_ANGLE + (t / 100) * SWEEP;
          const major = LABELS.includes(t);
          const p1 = polar(CX, CY, R - STROKE / 2 - 2, a);
          const p2 = polar(CX, CY, R - STROKE / 2 - (major ? 13 : 7), a);
          return (
            <line key={t} x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
              stroke={major ? 'var(--text-secondary)' : 'var(--text-muted)'}
              strokeWidth={major ? 1.4 : 0.7} />
          );
        })}

        {/* tick labels */}
        {LABELS.map((t) => {
          const p = polar(CX, CY, R - STROKE / 2 - 22, START_ANGLE + (t / 100) * SWEEP);
          return (
            <text key={t} x={p.x} y={p.y} textAnchor="middle"
              dominantBaseline="central" className="gauge-tick-text">
              {t}
            </text>
          );
        })}

        {/* center readout */}
        <text x={CX} y={CY - 6} textAnchor="middle"
          className="gauge-number" style={{ fill: c }}>
          {Math.round(riskScore)}
        </text>
        <text x={CX} y={CY + 16} textAnchor="middle"
          className="gauge-status" style={{ fill: c }}>
          {label(riskScore)}
        </text>
      </svg>

      {/* trend */}
      <div className="gauge-trend" style={{ color: trendColor }}>
        <span className="trend-arrow">{trendArrow}</span>
        <span className="trend-val">{Math.abs(trendSlope).toFixed(1)}</span>
        <span className="trend-unit">pts/s</span>
      </div>

      {/* calibration */}
      <div className={`gauge-calib ${isCalibrating ? 'active' : ''}`}>
        {isCalibrating ? (
          <>
            <span className="calib-dot" />
            <span>Calibrating… {Math.ceil(calibration.seconds_remaining)}s</span>
          </>
        ) : (
          <span className="calib-ok">✓ Calibrated</span>
        )}
      </div>
    </div>
  );
}
