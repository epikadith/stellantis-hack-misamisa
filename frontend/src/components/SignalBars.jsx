import './SignalBars.css';

const SIGNALS = [
  { key: 'perclos', label: 'PERCLOS', desc: 'Eye Closure' },
  { key: 'head_pose', label: 'HEAD POSE', desc: 'Distraction' },
  { key: 'hand_zone', label: 'HAND ZONE', desc: 'Wheel Status' },
  { key: 'yawn', label: 'YAWN', desc: 'Fatigue' },
];

function barColor(v) {
  if (v < 40) return 'var(--safe)';
  if (v < 70) return 'var(--warn)';
  return 'var(--danger)';
}

function glowColor(v) {
  if (v < 40) return 'var(--safe-glow)';
  if (v < 70) return 'var(--warn-glow)';
  return 'var(--danger-glow)';
}

export default function SignalBars({ signals }) {
  const vals = signals || { perclos: 0, head_pose: 0, hand_zone: 0, yawn: 0 };

  /* find dominant (highest) signal */
  const maxKey = Object.entries(vals).reduce(
    (a, b) => (b[1] > a[1] ? b : a),
    ['', -1],
  )[0];

  return (
    <div className="sig-panel panel">
      <div className="panel-header">Signal Breakdown</div>
      <div className="sig-list">
        {SIGNALS.map(({ key, label, desc }) => {
          const v = vals[key] ?? 0;
          const c = barColor(v);
          const isDominant = key === maxKey && v > 5;
          return (
            <div key={key} className={`sig-row ${isDominant ? 'dominant' : ''}`}>
              <div className="sig-meta">
                <div className="sig-names">
                  <span className="sig-label">{label}</span>
                  <span className="sig-desc">{desc}</span>
                </div>
                <span className="sig-value" style={{ color: c }}>
                  {Math.round(v)}
                </span>
              </div>
              <div className="sig-track">
                <div
                  className="sig-fill"
                  style={{
                    width: `${Math.min(100, v)}%`,
                    background: c,
                    boxShadow: `0 0 10px ${glowColor(v)}`,
                  }}
                />
                <div className="sig-threshold" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
