import './AlertPanel.css';

export default function AlertPanel({ alert }) {
  const active = alert?.active ?? false;
  const severity = alert?.severity ?? 'none';
  const reason = alert?.reason ?? '';
  const timeSaved = alert?.time_saved_seconds ?? 0;

  const panelClass = active ? `alert-${severity}` : 'alert-idle';

  return (
    <div className={`ap-panel panel ${panelClass}`}>
      <div className="panel-header">Alert Status</div>

      {active ? (
        <div className="ap-body">
          <div className="ap-badge-row">
            <span className={`ap-badge sev-${severity}`}>
              {severity === 'red' ? '⚠ CRITICAL' : '⚡ WARNING'}
            </span>
          </div>

          <p className="ap-reason">{reason}</p>

          {timeSaved > 0 && (
            <div className="ap-saved">
              <span className="saved-icon">⏱</span>
              <div className="saved-body">
                <span className="saved-val">{timeSaved.toFixed(1)}s</span>
                <span className="saved-label">predicted earlier than naive</span>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="ap-idle">
          <span className="ap-idle-dot" />
          <span className="ap-idle-text">All clear — no active alerts</span>
        </div>
      )}
    </div>
  );
}
