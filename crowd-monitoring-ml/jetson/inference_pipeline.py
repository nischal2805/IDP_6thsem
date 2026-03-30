"""
Main Inference Pipeline for Jetson Orin Nano.
Orchestrates all ML modules and streams results to ground server.
"""
import numpy as np
import time
import json
import argparse
from typing import Dict, Optional
from dataclasses import asdict
import threading
import queue

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from pose_estimator import PoseEstimator
from fall_detector import MLFallDetector, FallState
from density_estimator import CrowdDensityEstimator
from optical_flow import OpticalFlowAnalyzer, AnomalyType
from gps_alert import GPSManager, AlertManager

# Network communication
try:
    import socket
    import struct
    SOCKET_AVAILABLE = True
except ImportError:
    SOCKET_AVAILABLE = False


class JetsonInferencePipeline:
    """
    Main inference pipeline running on Jetson Orin Nano.
    
    Processes video frames through:
    1. YOLOv8n-pose for person detection + keypoints
    2. Fall detection classifier
    3. Crowd density estimation
    4. Optical flow anomaly detection
    5. GPS coordinate tagging for alerts
    
    Outputs JSON results via socket to ground server.
    """
    
    def __init__(
        self,
        camera_source: int = 0,
        server_host: str = "localhost",
        server_port: int = 9000,
        target_fps: float = 15.0,
        use_tensorrt: bool = False,
        enable_display: bool = True
    ):
        """
        Initialize inference pipeline.
        
        Args:
            camera_source: Camera index or video file path
            server_host: Ground server IP address
            server_port: Ground server port
            target_fps: Target inference FPS
            use_tensorrt: Use TensorRT optimization
            enable_display: Show local visualization
        """
        self.camera_source = camera_source
        self.server_host = server_host
        self.server_port = server_port
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.enable_display = enable_display
        
        # Initialize modules
        print("Initializing ML modules...")
        
        self.pose_estimator = PoseEstimator(
            model_path="yolov8n-pose.pt",
            device="cpu",
            use_tensorrt=use_tensorrt
        )
        
        self.fall_detector = MLFallDetector(
            use_lstm=False,  # Start with rule-based
            device="cpu"
        )
        
        self.density_estimator = CrowdDensityEstimator(
            backend="auto",
            device="cpu"
        )
        
        self.flow_analyzer = OpticalFlowAnalyzer(
            magnitude_threshold=5.0,
            panic_threshold=15.0
        )
        
        self.gps_manager = GPSManager()
        self.alert_manager = AlertManager(self.gps_manager)
        
        # Video capture
        self.cap = None
        self.frame_queue = queue.Queue(maxsize=3)
        
        # Network socket
        self.socket = None
        self.connected = False
        
        # State
        self.running = False
        self.frame_count = 0
        self.start_time = 0
        
        # Results buffer
        self.latest_result: Optional[Dict] = None
    
    def start(self):
        """Start the inference pipeline."""
        print("Starting Jetson Inference Pipeline...")
        
        # Initialize camera
        if CV2_AVAILABLE:
            print(f"Opening camera {self.camera_source}...")
            
            # Use V4L2 backend explicitly for USB cameras on Jetson
            self.cap = cv2.VideoCapture(self.camera_source, cv2.CAP_V4L2)
            
            if not self.cap.isOpened():
                print(f"❌ Failed to open camera {self.camera_source}")
                print("Available devices:")
                import os
                os.system("ls -l /dev/video* 2>/dev/null || echo 'No video devices found'")
                return False
            
            # Set camera properties BEFORE first read (critical for USB cameras)
            # Start with lower resolution to ensure compatibility
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
            
            # Give camera time to initialize and adjust settings
            print("Waiting for camera to initialize...")
            time.sleep(2)
            
            # Flush initial frames (often corrupted)
            for i in range(5):
                self.cap.grab()
            
            # Test read
            ret, test_frame = self.cap.read()
            if not ret:
                print("❌ Camera opened but cannot read frames")
                print("Trying alternative settings...")
                
                # Try without MJPG
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
                time.sleep(1)
                ret, test_frame = self.cap.read()
                
                if not ret:
                    print("❌ Still failed. Camera may need manual configuration.")
                    return False
            
            print(f"✅ Camera initialized: {test_frame.shape[1]}x{test_frame.shape[0]}")
        
        # Connect GPS
        try:
            self.gps_manager.connect()
        except Exception as e:
            print(f"GPS connection failed (non-critical): {e}")
        
        # Connect to ground server
        self._connect_server()
        
        self.running = True
        self.start_time = time.time()
        
        # Main loop
        self._run_loop()
        
        return True
    
    def stop(self):
        """Stop the pipeline."""
        self.running = False
        
        if self.cap:
            self.cap.release()
        
        if self.socket:
            self.socket.close()
        
        self.gps_manager.disconnect()
        
        if CV2_AVAILABLE:
            cv2.destroyAllWindows()
        
        print("Pipeline stopped.")
    
    def _connect_server(self):
        """Connect to ground server via socket."""
        if not SOCKET_AVAILABLE or self.server_host is None:
            print("Running in local-only mode (no server connection)")
            return
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)  # 5 second timeout
            self.socket.connect((self.server_host, self.server_port))
            self.connected = True
            print(f"✅ Connected to ground server at {self.server_host}:{self.server_port}")
        except Exception as e:
            print(f"⚠️ Failed to connect to server: {e}")
            print("   Continuing in local-only mode...")
            self.connected = False
    
    def _send_result(self, result: Dict):
        """Send result to ground server."""
        if not self.connected or not self.socket:
            return
        
        try:
            data = json.dumps(result).encode('utf-8')
            # Send length prefix then data
            self.socket.sendall(struct.pack('>I', len(data)) + data)
        except Exception as e:
            print(f"Send error: {e}")
            self.connected = False
    
    def _run_loop(self):
        """Main inference loop."""
        consecutive_failures = 0
        max_failures = 10
        
        while self.running:
            loop_start = time.time()
            
            # Capture frame
            if CV2_AVAILABLE and self.cap:
                ret, frame = self.cap.read()
                if not ret:
                    consecutive_failures += 1
                    print(f"⚠️ Frame capture failed (attempt {consecutive_failures}/{max_failures})")
                    
                    if consecutive_failures >= max_failures:
                        print("❌ Too many consecutive failures, stopping...")
                        self.running = False
                        break
                    
                    time.sleep(0.5)
                    continue
                else:
                    consecutive_failures = 0  # Reset on success
            else:
                # Generate test frame
                frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
            
            # Process frame
            try:
                result = self._process_frame(frame)
                self.latest_result = result
            except Exception as e:
                print(f"❌ Frame processing error: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Send to server
            if self.connected:
                self._send_result(result)
            
            # Display
            if self.enable_display and CV2_AVAILABLE:
                self._display_frame(frame, result)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.running = False
                elif key == ord('p'):
                    # Inject test panic
                    self.flow_analyzer.magnitude_threshold = 1.0
            
            # Frame rate control
            elapsed = time.time() - loop_start
            if elapsed < self.frame_interval:
                time.sleep(self.frame_interval - elapsed)
            
            self.frame_count += 1
            
            # Print FPS every 30 frames
            if self.frame_count % 30 == 0:
                runtime = time.time() - self.start_time
                fps = self.frame_count / runtime if runtime > 0 else 0
                print(f"📊 FPS: {fps:.1f} | Frames: {self.frame_count} | Connected: {self.connected}")
    
    def _process_frame(self, frame: np.ndarray) -> Dict:
        """
        Process a single frame through all ML modules.
        
        Args:
            frame: BGR image
        
        Returns:
            Dictionary with all inference results
        """
        timestamp = time.time()
        
        # 1. Pose estimation
        pose_start = time.time()
        detections = self.pose_estimator.infer(frame)
        pose_time = (time.time() - pose_start) * 1000
        
        # 2. Fall detection
        fall_start = time.time()
        fall_events = self.fall_detector.detect(detections, timestamp)
        fall_time = (time.time() - fall_start) * 1000
        
        # 3. Density estimation
        density_start = time.time()
        density_result = self.density_estimator.estimate(frame)
        density_time = density_result.inference_time_ms
        
        # 4. Optical flow anomaly
        flow_start = time.time()
        flow_result = self.flow_analyzer.analyze(frame)
        flow_time = flow_result.inference_time_ms
        
        # 5. Generate alerts
        alerts = []
        
        for event in fall_events:
            if event.confirmed:
                alert = self.alert_manager.create_fall_alert(
                    person_id=event.person_id,
                    confidence=event.confidence,
                    bbox=tuple(event.bbox) if event.bbox is not None else None,
                    duration=event.duration_seconds
                )
                alerts.append(json.loads(alert.to_json()))
        
        if flow_result.anomaly_type in [AnomalyType.PANIC, AnomalyType.STAMPEDE]:
            alert = self.alert_manager.create_panic_alert(
                confidence=flow_result.confidence,
                estimated_count=len(detections)
            )
            alerts.append(json.loads(alert.to_json()))
        
        # Check crush risk from density
        if density_result.peak_density > 6.0:
            alert = self.alert_manager.create_crush_risk_alert(
                density=density_result.peak_density,
                location=density_result.peak_location
            )
            alerts.append(json.loads(alert.to_json()))
        
        # Get current GPS
        gps = self.gps_manager.get_current_position()
        
        # Build result
        result = {
            "timestamp": timestamp,
            "frame_id": self.frame_count,
            "fps": self.frame_count / (timestamp - self.start_time + 0.001),
            
            # Pose/Person data
            "persons": [
                {
                    "id": d.person_id,
                    "bbox": [float(x) for x in d.bbox],
                    "confidence": d.confidence,
                    "keypoints": d.keypoints.tolist()
                }
                for d in detections
            ],
            "person_count": len(detections),
            
            # Fall detection
            "falls": [
                {
                    "person_id": e.person_id,
                    "state": e.state.value,
                    "confidence": e.confidence,
                    "confirmed": e.confirmed,
                    "duration": e.duration_seconds
                }
                for e in fall_events
            ],
            
            # Density
            "density": {
                "count": density_result.count,
                "peak_density": density_result.peak_density,
                "peak_location": density_result.peak_location,
                "avg_density": density_result.avg_density,
                "high_density_regions": density_result.high_density_regions[:5]
            },
            
            # Anomaly
            "anomaly": {
                "detected": flow_result.anomaly_detected,
                "type": flow_result.anomaly_type.value,
                "confidence": flow_result.confidence,
                "magnitude": flow_result.global_magnitude,
                "divergence": flow_result.global_divergence
            },
            
            # GPS
            "gps": gps.to_dict() if gps else None,
            
            # Alerts
            "alerts": alerts,
            
            # Performance
            "timing_ms": {
                "pose": pose_time,
                "fall": fall_time,
                "density": density_time,
                "flow": flow_time,
                "total": pose_time + fall_time + density_time + flow_time
            }
        }
        
        return result
    
    def _display_frame(self, frame: np.ndarray, result: Dict):
        """Display frame with overlays."""
        if not CV2_AVAILABLE:
            return
        
        display = frame.copy()
        
        # Draw person bboxes
        for person in result.get("persons", []):
            bbox = person["bbox"]
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(display, f"P{person['id']}", (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw fall indicators
        for fall in result.get("falls", []):
            if fall["confirmed"]:
                cv2.putText(display, "FALL DETECTED!", (50, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
        
        # Draw stats
        stats = [
            f"FPS: {result['fps']:.1f}",
            f"Persons: {result['person_count']}",
            f"Density Count: {result['density']['count']:.0f}",
            f"Anomaly: {result['anomaly']['type']}",
        ]
        
        for i, stat in enumerate(stats):
            cv2.putText(display, stat, (10, 30 + i * 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Show alerts
        if result.get("alerts"):
            cv2.putText(display, f"ALERTS: {len(result['alerts'])}", (10, 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        cv2.imshow("Jetson Inference", display)


def main():
    parser = argparse.ArgumentParser(description="Jetson Crowd Monitoring Pipeline")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--server", type=str, default="localhost", help="Ground server host")
    parser.add_argument("--port", type=int, default=9000, help="Ground server port")
    parser.add_argument("--fps", type=float, default=15.0, help="Target FPS")
    parser.add_argument("--no-display", action="store_true", help="Disable local display")
    parser.add_argument("--no-tensorrt", action="store_true", help="Disable TensorRT")
    parser.add_argument("--no-gps", action="store_true", help="Disable GPS")
    parser.add_argument("--no-server", action="store_true", help="Run without server connection (local only)")
    
    args = parser.parse_args()
    
    pipeline = JetsonInferencePipeline(
        camera_source=args.camera,
        server_host=args.server if not args.no_server else None,
        server_port=args.port,
        target_fps=args.fps,
        use_tensorrt=not args.no_tensorrt,
        enable_display=not args.no_display
    )
    
    try:
        pipeline.start()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
