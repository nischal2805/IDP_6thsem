#!/usr/bin/env python3
"""
Web Streaming Server for Jetson Inference Pipeline
Streams video with pose detection overlay to browser via MJPEG
"""

import cv2
import numpy as np
import threading
import time
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json

# Global frame buffer
output_frame = None
frame_lock = threading.Lock()
stats = {"fps": 0, "persons": 0, "falls": 0, "frame_count": 0}
stats_lock = threading.Lock()

# Try to import inference modules
try:
    from pose_estimator import PoseEstimator
    from fall_detector import FallDetector
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    print("⚠️ ML modules not available, running in camera-only mode")


class StreamingHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MJPEG streaming"""
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self._get_html().encode())
        elif self.path == '/video_feed':
            self.send_response(200)
            self.send_header('Age', '0')
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with frame_lock:
                        if output_frame is None:
                            continue
                        frame = output_frame.copy()
                    
                    ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if not ret:
                        continue
                    
                    self.wfile.write(b'--FRAME\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                    self.wfile.write(jpeg.tobytes())
                    self.wfile.write(b'\r\n')
                    time.sleep(0.033)
            except Exception as e:
                print(f"Client disconnected: {e}")
        elif self.path == '/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with stats_lock:
                self.wfile.write(json.dumps(stats).encode())
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        pass
    
    def _get_html(self):
        return '''<!DOCTYPE html>
<html>
<head>
    <title>Jetson Crowd Monitoring - Live Stream</title>
    <style>
        body { font-family: Arial, sans-serif; background: #1a1a2e; color: #fff; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; color: #00d4ff; }
        .video-container { display: flex; justify-content: center; margin: 20px 0; }
        #video { border: 3px solid #00d4ff; border-radius: 10px; max-width: 100%; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 20px; }
        .stat-card { background: rgba(255,255,255,0.1); border-radius: 10px; padding: 20px; text-align: center; }
        .stat-value { font-size: 2.5em; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #888; margin-top: 5px; }
        .status { text-align: center; padding: 10px; background: rgba(0,255,100,0.2); color: #00ff64; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Jetson Crowd Monitoring</h1>
        <div class="status">● Live Stream Active</div>
        <div class="video-container">
            <img id="video" src="/video_feed" alt="Live Stream">
        </div>
        <div class="stats-grid">
            <div class="stat-card"><div id="fps" class="stat-value">0</div><div class="stat-label">FPS</div></div>
            <div class="stat-card"><div id="persons" class="stat-value">0</div><div class="stat-label">Persons</div></div>
            <div class="stat-card"><div id="falls" class="stat-value">0</div><div class="stat-label">Falls</div></div>
            <div class="stat-card"><div id="frames" class="stat-value">0</div><div class="stat-label">Frames</div></div>
        </div>
    </div>
    <script>
        setInterval(async () => {
            try {
                const r = await fetch('/stats');
                const d = await r.json();
                document.getElementById('fps').textContent = d.fps.toFixed(1);
                document.getElementById('persons').textContent = d.persons;
                document.getElementById('falls').textContent = d.falls;
                document.getElementById('frames').textContent = d.frame_count;
            } catch (e) {}
        }, 1000);
    </script>
</body>
</html>'''


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def inference_loop(camera_source: int, use_inference: bool = True):
    """Main inference loop"""
    global output_frame, stats
    
    print(f"\n🎥 Opening camera {camera_source}...")
    
    cap = cv2.VideoCapture(camera_source, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_source)
    
    if not cap.isOpened():
        print("❌ Camera not available")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    
    time.sleep(2)
    for _ in range(5):
        cap.grab()
    
    print("✅ Camera ready")
    
    pose_estimator = None
    if use_inference and MODULES_AVAILABLE:
        try:
            print("🧠 Loading ML models...")
            pose_estimator = PoseEstimator()
            print("✅ Models loaded")
        except Exception as e:
            print(f"⚠️ Models failed: {e}")
    
    frame_count = 0
    fps_start = time.time()
    fps_frames = 0
    current_fps = 0
    persons = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue
        
        frame_count += 1
        fps_frames += 1
        
        if pose_estimator:
            try:
                results = pose_estimator.detect(frame)
                persons = len(results) if results else 0
                if results:
                    frame = pose_estimator.draw_poses(frame, results)
            except:
                pass
        
        elapsed = time.time() - fps_start
        if elapsed >= 1.0:
            current_fps = fps_frames / elapsed
            fps_frames = 0
            fps_start = time.time()
            print(f"📊 FPS: {current_fps:.1f} | Persons: {persons} | Frames: {frame_count}")
        
        cv2.rectangle(frame, (0, 0), (350, 30), (0, 0, 0), -1)
        cv2.putText(frame, f"FPS: {current_fps:.1f} | Persons: {persons}", (10, 22),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        with frame_lock:
            output_frame = frame.copy()
        
        with stats_lock:
            stats["fps"] = current_fps
            stats["persons"] = persons
            stats["frame_count"] = frame_count
    
    cap.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--no-inference', action='store_true')
    args = parser.parse_args()
    
    print("=" * 50)
    print("🌐 Jetson Web Streaming Server")
    print("=" * 50)
    
    t = threading.Thread(target=inference_loop, args=(args.camera, not args.no_inference), daemon=True)
    t.start()
    time.sleep(3)
    
    server = ThreadedHTTPServer(('0.0.0.0', args.port), StreamingHandler)
    print(f"\n✅ Server: http://0.0.0.0:{args.port}")
    print(f"📺 Open: http://10.161.127.240:{args.port}\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Stopped")
        server.shutdown()


if __name__ == '__main__':
    main()
