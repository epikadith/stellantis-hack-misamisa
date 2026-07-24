import './CockpitState.css';

const MODES = [
  { value: 'city', label: 'City', icon: '🏙' },
  { value: 'highway', label: 'Highway', icon: '🛣' },
  { value: 'night', label: 'Night', icon: '🌙' },
];

const QUALITY = [
  { key: 'face_detected', label: 'Face' },
  { key: 'hands_detected', label: 'Hands' },
  { key: 'lighting_ok', label: 'Light' },
];

export default function CockpitState({
  connected,
  frame,
  contextMode,
  onContextChange,
  onStartSession,
}) {
  const q = frame?.signal_quality || {};

  return (
    <header className="ck-header panel">
      {/* branding */}
      <div className="ck-brand">
        <span className="ck-diamond">◆</span>
        <h1 className="ck-title">PREDICTIVE RISK COCKPIT</h1>
        <span className={`ck-badge ${connected ? 'live' : 'off'}`}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>

      {/* signal quality */}
      <div className="ck-quality">
        {QUALITY.map(({ key, label }) => (
          <div key={key} className={`ck-qi ${q[key] ? 'ok' : ''}`}>
            <span className="qi-dot" />
            <span className="qi-label">{label}</span>
          </div>
        ))}
      </div>

      {/* controls */}
      <div className="ck-controls">
        <div className="ck-modes">
          {MODES.map(({ value, label, icon }) => (
            <button
              key={value}
              className={`ck-mode ${contextMode === value ? 'active' : ''}`}
              onClick={() => onContextChange(value)}
            >
              <span className="mode-icon">{icon}</span>
              {label}
            </button>
          ))}
        </div>
        <button className="ck-start" onClick={onStartSession}>
          ▶ New Session
        </button>
      </div>
    </header>
  );
}
