import { useMemo } from 'react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
  ReferenceDot,
  ResponsiveContainer,
} from 'recharts';
import './TrajectoryChart.css';

/* ── Custom tooltip ──────────────────────────────────── */

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="ct-tooltip">
      <div className="ct-tooltip-time">
        {typeof label === 'number' ? `${label.toFixed(1)}s` : label}
      </div>
      {payload.map((p) => (
        <div key={p.dataKey} className="ct-tooltip-row">
          <span className="ct-dot" style={{ background: p.color }} />
          <span className="ct-name">{p.name}</span>
          <span className="ct-val">{Number(p.value).toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Component ───────────────────────────────────────── */

export default function TrajectoryChart({
  chartData = [],
  showNaive,
  onToggleNaive,
  events = [],
}) {
  /* merge real data + trend projection line */
  const displayData = useMemo(() => {
    if (chartData.length === 0) return [];

    const data = chartData.map((d) => ({
      time: d.time,
      riskScore: d.riskScore,
      naiveScore: d.naiveScore,
    }));

    const last = chartData[chartData.length - 1];
    if (last && last.trendSlope > 0.5) {
      data[data.length - 1].projection = last.riskScore;
      for (let i = 1; i <= 15; i++) {
        const dt = i * 0.2;
        const p = last.riskScore + last.trendSlope * dt;
        if (p > 110) break;
        data.push({
          time: parseFloat((last.time + dt).toFixed(2)),
          projection: Math.min(100, Math.max(0, p)),
        });
      }
    }
    return data;
  }, [chartData]);

  const domain = useMemo(() => {
    if (displayData.length < 2) return [0, 30];
    const times = displayData.map((d) => d.time);
    const max = Math.max(...times);
    const min = Math.max(0, max - 30);
    return [min, Math.max(max, min + 30)];
  }, [displayData]);

  /* alert event markers inside visible domain */
  const alertEvents = useMemo(
    () =>
      events
        .filter((e) => e.type === 'alert')
        .filter((e) => e.relativeTime >= domain[0] && e.relativeTime <= domain[1]),
    [events, domain],
  );

  return (
    <div className="chart-panel panel">
      <div className="chart-head">
        <span className="panel-header">Trajectory</span>

        <div className="chart-legend">
          <span className="legend-item">
            <span className="legend-line" style={{ background: '#00e5ff' }} />
            Risk
          </span>
          {showNaive && (
            <span className="legend-item">
              <span className="legend-line legend-dashed" style={{ background: 'var(--naive-color)' }} />
              Naive
            </span>
          )}
          <span className="legend-item">
            <span className="legend-line legend-dashed" style={{ background: '#00e5ff' }} />
            Projection
          </span>
        </div>

        <label className="chart-toggle">
          <input type="checkbox" checked={showNaive} onChange={onToggleNaive} />
          <span className="toggle-track"><span className="toggle-thumb" /></span>
          <span className="toggle-text">Naive Detector</span>
        </label>
      </div>

      <div className="chart-body">
        {chartData.length === 0 ? (
          <div className="chart-empty">Waiting for data…</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={displayData} margin={{ top: 8, right: 16, bottom: 4, left: 6 }}>
              <defs>
                <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00e5ff" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#00e5ff" stopOpacity={0.01} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 6" stroke="rgba(60,60,100,0.12)" vertical={false} />

              <XAxis
                dataKey="time" type="number" domain={domain}
                tickFormatter={(v) => `${v.toFixed(0)}s`}
                stroke="var(--text-muted)"
                tick={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={{ stroke: 'var(--border-subtle)' }}
              />
              <YAxis
                domain={[0, 100]} ticks={[0, 25, 50, 70, 100]}
                stroke="var(--text-muted)"
                tick={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={{ stroke: 'var(--border-subtle)' }}
                width={32}
              />

              <Tooltip content={<ChartTooltip />} />

              {/* danger zone */}
              <ReferenceArea y1={70} y2={100} fill="rgba(255,23,68,0.05)" ifOverflow="hidden" />
              <ReferenceLine
                y={70} stroke="rgba(255,23,68,0.35)" strokeDasharray="6 4"
                label={{
                  value: 'THRESHOLD', position: 'right',
                  fill: 'rgba(255,23,68,0.45)', fontSize: 9,
                  fontFamily: 'var(--font-display)',
                }}
              />

              {/* trend projection */}
              <Line
                type="monotone" dataKey="projection"
                stroke="#00e5ff" strokeWidth={2} strokeDasharray="4 4"
                dot={false} connectNulls={false} isAnimationActive={false}
                name="Projection"
              />

              {/* naive score */}
              {showNaive && (
                <Line
                  type="monotone" dataKey="naiveScore"
                  stroke="var(--naive-color)" strokeWidth={1.5} strokeDasharray="6 3"
                  dot={false} isAnimationActive={false}
                  name="Naive Score"
                />
              )}

              {/* risk score — hero line */}
              <Line
                type="monotone" dataKey="riskScore"
                stroke="#00e5ff" strokeWidth={2.5}
                dot={false} isAnimationActive={false}
                name="Risk Score"
              />

              {/* alert event markers */}
              {alertEvents.map((ev, i) => (
                <ReferenceDot
                  key={i} x={ev.relativeTime} y={70}
                  r={5} fill="var(--danger)" stroke="#fff" strokeWidth={1.5}
                  ifOverflow="extendDomain"
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
