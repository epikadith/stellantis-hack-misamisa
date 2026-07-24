import { useCallback, useEffect, useRef, useState } from 'react';

const MAX_POINTS = 150;       // ~30 s at 5 Hz
const RECONNECT_MS = 1500;

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [frame, setFrame] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [events, setEvents] = useState([]);

  const wsRef = useRef(null);
  const epochRef = useRef(null);
  const timerRef = useRef(null);

  /* ── connect / reconnect ────────────────────────── */

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return;

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws/risk`);
    wsRef.current = ws;

    ws.addEventListener('open', () => setConnected(true));

    ws.addEventListener('message', (e) => {
      const msg = JSON.parse(e.data);

      /* inline event messages */
      if (msg.type === 'event') {
        const relTime =
          epochRef.current !== null ? msg.event.timestamp - epochRef.current : 0;
        setEvents((prev) => [
          ...prev.slice(-80),
          { ...msg.event, relativeTime: relTime },
        ]);
        return;
      }

      /* regular risk frame */
      setFrame(msg);

      if (epochRef.current === null) epochRef.current = msg.timestamp;
      const t = parseFloat((msg.timestamp - epochRef.current).toFixed(2));

      setChartData((prev) => {
        const next = [
          ...prev,
          {
            time: t,
            riskScore: msg.risk_score,
            naiveScore: msg.naive_score,
            trendSlope: msg.trend_slope,
          },
        ];
        return next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next;
      });
    });

    ws.addEventListener('close', () => {
      setConnected(false);
      wsRef.current = null;
      timerRef.current = setTimeout(connect, RECONNECT_MS);
    });

    ws.addEventListener('error', () => ws.close());
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  /* ── REST helpers ───────────────────────────────── */

  const startSession = useCallback(async () => {
    try {
      const res = await fetch('/session/start', { method: 'POST' });
      epochRef.current = null;
      setChartData([]);
      setEvents([]);
      return await res.json();
    } catch {
      return null;
    }
  }, []);

  const setContextMode = useCallback(async (mode) => {
    try {
      const res = await fetch('/session/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      return await res.json();
    } catch {
      return null;
    }
  }, []);

  return { connected, frame, chartData, events, startSession, setContextMode };
}
