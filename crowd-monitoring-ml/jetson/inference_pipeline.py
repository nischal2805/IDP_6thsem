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
            backend="mock",
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
    
    def _enumerate_video_devices(self):
        """Enumerate all available video devices on Linux."""
        import os
        import glob
        
        devices = []
        device_paths = sorted(glob.glob('/dev/video*'))
        
        print("\n📹 Enumerating video devices:")
        if not device_paths:
            print("   ⚠️ No /dev/video* devices found")
            return devices
        
        for dev_path in device_paths:
            try:
                # Get device info
                stat_info = os.stat(dev_path)
                permissions = oct(stat_info.st_mode)[-3:]
                
                # Check if readable
                readable = os.access(dev_path, os.R_OK)
                writable = os.access(dev_path, os.W_OK)
                
                device_info = {
                    'path': dev_path,
                    'index': int(dev_path.replace('/dev/video', '')),
                    'permissions': permissions,
                    'readable': readable,
                    'writable': writable
                }
                devices.append(device_info)
                
                status = "✅" if readable and writable else "⚠️"
                print(f"   {status} {dev_path} (perms: {permissions}, r:{readable}, w:{writable})")
                
            except Exception as e:
                print(f"   ❌ {dev_path}: {e}")
        
        return devices
    
    def _check_video_permissions(self):
        """Check if current user has proper video device permissions."""
        import os
        import subprocess
        
        print("\n🔐 Checking video permissions:")
        
        # Check if user is in video group
        try:
            result = subprocess.run(['groups'], capture_output=True, text=True, timeout=2)
            groups = result.stdout.strip()
            in_video_group = 'video' in groups.split()
            
            if in_video_group:
                print(f"   ✅ User is in 'video' group")
            else:
                print(f"   ⚠️ User NOT in 'video' group")
                print(f"   💡 Fix: sudo usermod -a -G video $USER (then logout/login)")
            
            return in_video_group
        except Exception as e:
            print(f"   ⚠️ Could not check group membership: {e}")
            return False
    
    def _try_open_camera(self, device_index: int, backend: int, backend_name: str) -> Optional[object]:
        """
        Try to open camera with specific device and backend.
        
        Args:
            device_index: Camera device index
            backend: OpenCV backend constant
            backend_name: Backend name for logging
        
        Returns:
            VideoCapture object if successful, None otherwise
        """
        try:
            print(f"   Trying device {device_index} with {backend_name} backend...")
            cap = cv2.VideoCapture(device_index, backend)
            
            if cap.isOpened():
                return cap
            else:
                cap.release()
                return None
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return None
    
    def _configure_camera(self, cap: object, codec_fourcc: str = 'MJPG') -> bool:
        """
        Configure camera properties and verify settings.
        
        Args:
            cap: OpenCV VideoCapture object
            codec_fourcc: Codec FourCC code ('MJPG', 'YUYV', etc.)
        
        Returns:
            True if configuration successful and frames readable
        """
        print(f"\n⚙️ Configuring camera with {codec_fourcc} codec...")
        
        # Set properties BEFORE first read (critical for USB cameras)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Set codec
        fourcc = cv2.VideoWriter_fourcc(*codec_fourcc)
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        
        # Give camera time to initialize
        print("   Waiting for camera to stabilize...")
        time.sleep(2)
        
        # Flush initial frames (often corrupted or black)
        print("   Flushing initial frames...")
        for i in range(5):
            cap.grab()
        
        # Test read
        print("   Testing frame capture...")
        ret, test_frame = cap.read()
        
        if not ret or test_frame is None:
            print(f"   ❌ Cannot read frames with {codec_fourcc}")
            return False
        
        # Verify actual settings
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(cap.get(cv2.CAP_PROP_FPS))
        
        print(f"   ✅ Camera configured successfully:")
        print(f"      Resolution: {actual_width}x{actual_height} (frame: {test_frame.shape[1]}x{test_frame.shape[0]})")
        print(f"      FPS: {actual_fps}")
        print(f"      Codec: {codec_fourcc}")
        
        return True
    
    def _initialize_camera_robust(self) -> bool:
        """
        Robustly initialize camera with fallback strategies.
        
        Returns:
            True if camera successfully initialized, False otherwise
        """
        if not CV2_AVAILABLE:
            print("⚠️ OpenCV not available, skipping camera initialization")
            return False
        
        print("\n" + "="*60)
        print("🎥 CAMERA INITIALIZATION")
        print("="*60)
        
        # Step 1: Enumerate devices
        available_devices = self._enumerate_video_devices()
        
        # Step 2: Check permissions
        self._check_video_permissions()
        
        if not available_devices:
            print("\n❌ No video devices found!")
            print("💡 Troubleshooting:")
            print("   1. Check if camera is physically connected")
            print("   2. Check dmesg: dmesg | grep -i video")
            print("   3. Check USB devices: lsusb")
            return False
        
        # Step 3: Determine device indices to try
        if isinstance(self.camera_source, int):
            # Try specified index first, then fallback to others
            device_indices = [self.camera_source]
            device_indices.extend([d['index'] for d in available_devices if d['index'] != self.camera_source])
        else:
            # Try all available devices
            device_indices = [d['index'] for d in available_devices]
        
        print(f"\n🔍 Will try device indices in order: {device_indices}")
        
        # Step 4: Try different backend and device combinations
        backends = [
            (cv2.CAP_V4L2, "V4L2"),
            (cv2.CAP_ANY, "ANY"),
        ]
        
        codecs = ['MJPG', 'YUYV', 'YUY2']
        
        print("\n🔄 Attempting camera initialization with fallbacks...")
        
        for device_idx in device_indices:
            for backend_const, backend_name in backends:
                cap = self._try_open_camera(device_idx, backend_const, backend_name)
                
                if cap is None:
                    continue
                
                # Camera opened, now try different codecs
                for codec in codecs:
                    if self._configure_camera(cap, codec):
                        # Success!
                        self.cap = cap
                        print(f"\n{'='*60}")
                        print(f"✅ CAMERA READY")
                        print(f"   Device: /dev/video{device_idx}")
                        print(f"   Backend: {backend_name}")
                        print(f"   Codec: {codec}")
                        print(f"{'='*60}\n")
                        return True
                
                # All codecs failed for this backend, release and try next
                cap.release()
        
        # All attempts failed
        print("\n" + "="*60)
        print("❌ CAMERA INITIALIZATION FAILED")
        print("="*60)
        print("\n💡 Troubleshooting steps:")
        print("   1. Verify camera is detected: ls -l /dev/video*")
        print("   2. Check permissions: groups (should include 'video')")
        print("   3. Test with v4l2-ctl: v4l2-ctl --list-devices")
        print("   4. Test with simple capture: ffplay /dev/video0")
        print("   5. Check if camera is in use: sudo lsof | grep video")
        print("   6. Try different USB port or cable")
        print("   7. Check kernel messages: dmesg | tail -50")
        
        return False
    
    def start(self):
        """Start the inference pipeline."""
        print("Starting Jetson Inference Pipeline...")
        
        # Initialize camera with robust error handling
        if not self._initialize_camera_robust():
            print("\n⚠️ Camera initialization failed, but continuing...")
            print("   Pipeline will run with synthetic frames for testing")
            self.cap = None
        
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
            # Convert numpy types to native Python types for JSON serialization
            import numpy as np
            def convert_types(obj):
                if isinstance(obj, dict):
                    return {k: convert_types(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [convert_types(i) for i in obj]
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, (np.integer, np.int64, np.int32)):
                    return int(obj)
                elif isinstance(obj, (np.floating, np.float64, np.float32)):
                    return float(obj)
                elif isinstance(obj, np.bool_):
                    return bool(obj)
                elif hasattr(obj, 'item'):  # other numpy scalars
                    return obj.item()
                return obj
            
            result = convert_types(result)
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
        density_result = self.density_estimator.estimate(frame, detections)
        density_time = density_result.inference_time_ms
        
        # 4. Optical flow anomaly
        flow_start = time.time()
        flow_result = self.flow_analyzer.analyze(frame)
        flow_time = flow_result.inference_time_ms
        
        # 5. Generate alerts (with higher thresholds to reduce false positives)
        alerts = []
        
        # Only alert on confirmed falls with high confidence
        for event in fall_events:
            if event.confirmed and event.confidence > 0.8:
                alert = self.alert_manager.create_fall_alert(
                    person_id=event.person_id,
                    confidence=event.confidence,
                    bbox=tuple(event.bbox) if event.bbox is not None else None,
                    duration=event.duration_seconds
                )
                alerts.append(json.loads(alert.to_json()))
        
        # Only alert on high-confidence anomalies
        if flow_result.anomaly_type in [AnomalyType.PANIC, AnomalyType.STAMPEDE] and flow_result.confidence > 0.7:
            alert = self.alert_manager.create_panic_alert(
                confidence=flow_result.confidence,
                estimated_count=len(detections)
            )
            alerts.append(json.loads(alert.to_json()))
        
        # Check crush risk from density (much higher threshold)
        if density_result.peak_density > 15.0:  # Raised from 6.0
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
