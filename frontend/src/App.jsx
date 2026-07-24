import { useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import CockpitState from './components/CockpitState';
import WebcamView from './components/WebcamView';
import RiskGauge from './components/RiskGauge';
import TrajectoryChart from './components/TrajectoryChart';
import SignalBars from './components/SignalBars';
import AlertPanel from './components/AlertPanel';
import './App.css';

export default function App() {
  const { connected, frame, chartData, events, startSession, setContextMode } =
    useWebSocket();
  const [showNaive, setShowNaive] = useState(false);
  const [localMode, setLocalMode] = useState('city');

  const handleContextChange = async (mode) => {
    setLocalMode(mode);
    await setContextMode(mode);
  };

  const activeMode = frame?.context_mode ?? localMode;

  return (
    <div className="dashboard">
      <CockpitState
        connected={connected}
        frame={frame}
        contextMode={activeMode}
        onContextChange={handleContextChange}
        onStartSession={startSession}
      />

      <section className="dashboard-left">
        <WebcamView />
        <RiskGauge
          riskScore={frame?.risk_score ?? 0}
          trendSlope={frame?.trend_slope ?? 0}
          calibration={frame?.calibration}
        />
      </section>

      <section className="dashboard-center">
        <TrajectoryChart
          chartData={chartData}
          showNaive={showNaive}
          onToggleNaive={() => setShowNaive((v) => !v)}
          events={events}
        />
      </section>

      <section className="dashboard-right">
        <SignalBars signals={frame?.signals} />
        <AlertPanel alert={frame?.alert} />
      </section>

      {!connected && !frame && (
        <div className="dashboard-overlay">
          <div className="overlay-spinner" />
          <span className="overlay-text">Connecting to risk pipeline…</span>
        </div>
      )}
    </div>
  );
}
