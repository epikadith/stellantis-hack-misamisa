import { useEffect, useRef } from 'react';
import './WebcamView.css';

export default function WebcamView() {
  const videoRef = useRef(null);

  useEffect(() => {
    let stream = null;
    
    async function setupCamera() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 },
          audio: false,
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.error("Failed to get webcam stream:", err);
      }
    }
    
    setupCamera();
    
    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  return (
    <div className="webcam-panel panel">
      <div className="panel-header">Live Feed</div>
      <div className="webcam-container">
        <video 
          ref={videoRef} 
          autoPlay 
          playsInline 
          muted 
          className="webcam-video" 
        />
        {/* Adds a slight scanline/tech overlay effect to match the cockpit theme */}
        <div className="webcam-overlay"></div>
      </div>
    </div>
  );
}
