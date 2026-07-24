import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_RECONNECT_ATTEMPTS = 10
const RECONNECT_DELAY_MS = 2000

export const EMPTY_RISK = {
  timestamp: 0,
  risk_score: 0,
  trend_slope: 0,
  naive_score: 0,
  signals: { perclos: 0, head_pose: 0, hand_zone: 0, yawn: 0 },
  signal_quality: { face_detected: false, hands_detected: false, lighting_ok: false },
  calibration: { in_progress: false, seconds_remaining: 0 },
  alert: { active: false, severity: 'none', reason: '', time_saved_seconds: 0 },
  context_mode: 'city',
}

export function useRiskStream(url) {
  const [latestRisk, setLatestRisk] = useState(EMPTY_RISK)
  const [events, setEvents] = useState([])
  const [connection, setConnection] = useState({ status: 'connecting', label: 'CONNECTING', attempts: 0 })
  const reconnectTimer = useRef(null)
  const socketRef = useRef(null)

  useEffect(() => {
    let socket
    let disposed = false
    let attempts = 0

    const connect = () => {
      if (disposed) return
      setConnection({ status: attempts ? 'reconnecting' : 'connecting', label: attempts ? 'RECONNECTING' : 'CONNECTING', attempts })
      socket = new WebSocket(url)
      socketRef.current = socket

      socket.onopen = () => {
        attempts = 0
        setConnection({ status: 'connected', label: 'LIVE STREAM', attempts: 0 })
      }

      socket.onmessage = ({ data }) => {
        try {
          const message = JSON.parse(data)
          if (message?.type === 'event' && message.event) {
            setEvents((previous) => [...previous.slice(-19), message.event])
          } else if (isRiskFrame(message)) {
            setLatestRisk(message)
          }
        } catch {
          // Ignore malformed demo messages and preserve the last known state.
        }
      }

      socket.onclose = () => {
        if (socketRef.current === socket) socketRef.current = null
        if (disposed) return
        attempts += 1
        if (attempts > MAX_RECONNECT_ATTEMPTS) {
          setConnection({ status: 'lost', label: 'CONNECTION LOST', attempts: MAX_RECONNECT_ATTEMPTS })
          return
        }
        setConnection({ status: 'reconnecting', label: 'RECONNECTING', attempts })
        reconnectTimer.current = window.setTimeout(connect, RECONNECT_DELAY_MS)
      }

      socket.onerror = () => socket.close()
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(reconnectTimer.current)
      socket?.close()
    }
  }, [url])

  const sendCameraFrame = useCallback((frame) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(frame)
    }
  }, [])

  return { latestRisk, events, connection, sendCameraFrame }
}

function isRiskFrame(message) {
  return typeof message?.risk_score === 'number' && typeof message?.timestamp === 'number' && message?.signals
}
