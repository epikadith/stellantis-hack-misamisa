import { useEffect, useRef, useState } from 'react'

const CAPTURE_INTERVAL_MS = 200

export function CameraFeed({ onFrame }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [state, setState] = useState('REQUESTING CAMERA')

  useEffect(() => {
    let stream
    let captureTimer
    let cancelled = false

    async function startCamera() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setState('CAMERA API UNAVAILABLE')
        return
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 960 }, height: { ideal: 540 }, facingMode: 'user' },
          audio: false,
        })
        if (cancelled || !videoRef.current) return
        videoRef.current.srcObject = stream
        await videoRef.current.play()
        setState('CAMERA LIVE')
        captureTimer = window.setInterval(() => captureFrame(videoRef.current, canvasRef.current, onFrame), CAPTURE_INTERVAL_MS)
      } catch {
        setState('CAMERA PERMISSION REQUIRED')
      }
    }

    startCamera()
    return () => {
      cancelled = true
      window.clearInterval(captureTimer)
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [onFrame])

  return (
    <div className="camera-feed">
      <video autoPlay muted playsInline ref={videoRef} />
      <canvas ref={canvasRef} hidden />
      <div className="camera-status"><span className="status-dot" />{state}</div>
    </div>
  )
}

function captureFrame(video, canvas, onFrame) {
  if (!video || !canvas || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d', { alpha: false }).drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob((blob) => blob && onFrame(blob), 'image/jpeg', 0.75)
}
