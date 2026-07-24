import { useMemo, useState } from 'react'
import { useRiskStream } from './hooks/useRiskStream'
import './App.css'

const SIGNAL_LABELS = {
  perclos: 'PERCLOS',
  head_pose: 'HEAD POSE',
  hand_zone: 'HAND ZONE',
  yawn: 'YAWN',
}

function App() {
  const socketUrl = useMemo(() => getSocketUrl(), [])
  const { latestRisk, connection, events } = useRiskStream(socketUrl)
  const [showNaive, setShowNaive] = useState(false)

  return (
    <main className="cockpit-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">STELLANTIS / DRIVER SAFETY SYSTEM</p>
          <h1>Predictive Driver Risk Cockpit</h1>
        </div>
        <div className={`connection connection-${connection.status}`} aria-live="polite">
          <span className="status-dot" />
          {connection.label}
        </div>
      </header>

      <section className="status-strip" aria-label="Live session summary">
        <span>CONTEXT <b>{latestRisk.context_mode.toUpperCase()}</b></span>
        <span>STREAM <b>{connection.attempts ? `RETRY ${connection.attempts}/10` : 'LIVE'}</b></span>
        <span>EVENTS <b>{events.length}</b></span>
        <span>CADENCE <b>200 MS</b></span>
      </section>

      <section className="cockpit-grid" aria-label="Driver risk dashboard">
        <section className="zone video-zone" aria-labelledby="video-heading">
          <div className="zone-heading">
            <p>01 / LIVE INPUT</p>
            <h2 id="video-heading">Driver Camera</h2>
          </div>
          <div className="video-placeholder">
            <span>CAMERA INITIALIZING</span>
          </div>
        </section>

        <section className="zone gauge-zone" aria-labelledby="gauge-heading">
          <div className="zone-heading">
            <p>02 / COMPOSITE</p>
            <h2 id="gauge-heading">Risk Gauge</h2>
          </div>
          <div className="gauge-placeholder">{Math.round(latestRisk.risk_score)}</div>
          <span className="zone-placeholder-label">RISK SCORE</span>
        </section>

        <section className="zone signals-zone" aria-labelledby="signals-heading">
          <div className="zone-heading">
            <p>03 / SIGNAL FUSION</p>
            <h2 id="signals-heading">Signal Breakdown</h2>
          </div>
          <div className="signal-placeholder-list">
            {Object.entries(SIGNAL_LABELS).map(([key, label]) => (
              <div className="signal-placeholder" key={key}>
                <span>{label}</span>
                <span>{Math.round(latestRisk.signals[key])}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="zone trajectory-zone" aria-labelledby="trajectory-heading">
          <div className="zone-heading zone-heading-row">
            <div>
              <p>04 / PREDICTIVE TRAJECTORY</p>
              <h2 id="trajectory-heading">Risk Projection</h2>
            </div>
            <label className="switch-control">
              <input checked={showNaive} onChange={(event) => setShowNaive(event.target.checked)} type="checkbox" />
              <span className="switch-track" aria-hidden="true" />
              <span>Naive detector</span>
            </label>
          </div>
          <div className="chart-placeholder">
            <span>STREAM BUFFER READY</span>
            <small>{showNaive ? 'NAIVE OVERLAY ENABLED' : 'PREDICTIVE VIEW'}</small>
          </div>
        </section>

        <section className="zone response-zone" aria-labelledby="response-heading">
          <div className="zone-heading">
            <p>05 / COCKPIT RESPONSE</p>
            <h2 id="response-heading">Safety State</h2>
          </div>
          <div className="response-placeholder">
            <span>ALERT SYSTEM STANDBY</span>
            <span>TIME SAVED {latestRisk.alert.time_saved_seconds.toFixed(1)} S</span>
          </div>
        </section>
      </section>
    </main>
  )
}

function getSocketUrl() {
  if (import.meta.env.VITE_RISK_WS_URL) {
    return import.meta.env.VITE_RISK_WS_URL
  }
  return 'ws://127.0.0.1:8003/ws/risk'
}

export default App
