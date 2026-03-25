"""
YOLOv8n-pose Inference Module for Jetson Orin Nano.
Extracts 17 COCO keypoints per person for fall detection pipeline.
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import time

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: ultralytics not installed. Using mock inference.")


@dataclass
class PersonDetection:
    """Represents a single person detection with pose keypoints."""
    bbox: np.ndarray  # [x1, y1, x2, y2]
    confidence: float
    keypoints: np.ndarray  # Shape: (17, 3) - x, y, confidence for each keypoint
    person_id: Optional[int] = None
    
    @property
    def bbox_width(self) -> float:
        return self.bbox[2] - self.bbox[0]
    
    @property
    def bbox_height(self) -> float:
        return self.bbox[3] - self.bbox[1]
    
    @property
    def aspect_ratio(self) -> float:
        """Width / Height ratio. > 1 means wider than tall (potential fall)."""
        h = self.bbox_height
        return self.bbox_width / h if h > 0 else 0
    
    @property
    def center(self) -> Tuple[float, float]:
        return (
            (self.bbox[0] + self.bbox[2]) / 2,
            (self.bbox[1] + self.bbox[3]) / 2
        )
    
    def get_keypoint(self, idx: int) -> Tuple[float, float, float]:
        """Get keypoint by index. Returns (x, y, confidence)."""
        return tuple(self.keypoints[idx])
    
    @property
    def left_hip(self) -> Tuple[float, float, float]:
        return self.get_keypoint(11)
    
    @property
    def right_hip(self) -> Tuple[float, float, float]:
        return self.get_keypoint(12)
    
    @property
    def hip_center(self) -> Tuple[float, float]:
        """Average position of both hips."""
        lh = self.left_hip
        rh = self.right_hip
        return ((lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2)


# COCO Keypoint indices
KEYPOINT_NAMES = [
    'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
    'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
    'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
    'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
]


class PoseEstimator:
    """
    YOLOv8n-pose based human pose estimation.
    Optimized for Jetson Orin Nano with TensorRT FP16.
    """
    
    def __init__(
        self,
        model_path: str = "yolov8n-pose.pt",
        device: str = "cuda",
        conf_threshold: float = 0.5,
        use_tensorrt: bool = True
    ):
        """
        Initialize the pose estimator.
        
        Args:
            model_path: Path to YOLOv8 pose model (.pt or .engine)
            device: 'cuda' for GPU, 'cpu' for CPU
            conf_threshold: Minimum confidence for detections
            use_tensorrt: Whether to use TensorRT optimized model
        """
        self.device = device
        self.conf_threshold = conf_threshold
        self.model = None
        self.use_tensorrt = use_tensorrt
        
        if YOLO_AVAILABLE:
            self._load_model(model_path)
        else:
            print("Running in mock mode - no actual inference")
        
        # Performance tracking
        self.last_inference_time = 0
        self.avg_fps = 0
        self.frame_count = 0
    
    def _load_model(self, model_path: str):
        """Load YOLOv8 pose model."""
        try:
            self.model = YOLO(model_path)
            
            # Export to TensorRT if requested and not already exported
            if self.use_tensorrt and not model_path.endswith('.engine'):
                print("Exporting model to TensorRT FP16...")
                self.model.export(format='engine', half=True, device=0)
                engine_path = model_path.replace('.pt', '.engine')
                self.model = YOLO(engine_path)
            
            print(f"Model loaded: {model_path}")
        except Exception as e:
            print(f"Failed to load model: {e}")
            self.model = None
    
    def infer(self, frame: np.ndarray) -> List[PersonDetection]:
        """
        Run pose estimation on a single frame.
        
        Args:
            frame: BGR image as numpy array (H, W, 3)
        
        Returns:
            List of PersonDetection objects
        """
        start_time = time.time()
        
        if not YOLO_AVAILABLE or self.model is None:
            return self._mock_inference(frame)
        
        # Run inference
        results = self.model(
            frame,
            conf=self.conf_threshold,
            verbose=False,
            device=self.device
        )
        
        detections = []
        
        for result in results:
            if result.keypoints is None:
                continue
            
            boxes = result.boxes
            keypoints = result.keypoints
            
            for i in range(len(boxes)):
                bbox = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                kpts = keypoints.data[i].cpu().numpy()  # (17, 3)
                
                detection = PersonDetection(
                    bbox=bbox,
                    confidence=conf,
                    keypoints=kpts,
                    person_id=i
                )
                detections.append(detection)
        
        # Update performance metrics
        self.last_inference_time = time.time() - start_time
        self.frame_count += 1
        self.avg_fps = self.frame_count / (self.frame_count * self.last_inference_time + 0.001)
        
        return detections
    
    def _mock_inference(self, frame: np.ndarray) -> List[PersonDetection]:
        """Generate mock detections for testing without model."""
        h, w = frame.shape[:2]
        
        # Generate 1-3 random detections
        num_detections = np.random.randint(1, 4)
        detections = []
        
        for i in range(num_detections):
            # Random bbox
            x1 = np.random.randint(0, w // 2)
            y1 = np.random.randint(0, h // 2)
            x2 = x1 + np.random.randint(50, 150)
            y2 = y1 + np.random.randint(100, 300)
            
            # Random keypoints within bbox
            keypoints = np.zeros((17, 3))
            for j in range(17):
                keypoints[j, 0] = np.random.uniform(x1, x2)
                keypoints[j, 1] = np.random.uniform(y1, y2)
                keypoints[j, 2] = np.random.uniform(0.5, 1.0)
            
            detection = PersonDetection(
                bbox=np.array([x1, y1, x2, y2]),
                confidence=np.random.uniform(0.7, 0.99),
                keypoints=keypoints,
                person_id=i
            )
            detections.append(detection)
        
        self.last_inference_time = 0.04  # Mock ~25 FPS
        return detections
    
    def get_performance_stats(self) -> Dict:
        """Get inference performance statistics."""
        return {
            "last_inference_ms": self.last_inference_time * 1000,
            "avg_fps": self.avg_fps,
            "frame_count": self.frame_count
        }
    
    @staticmethod
    def export_tensorrt(model_path: str, output_path: str = None):
        """
        Export YOLOv8 model to TensorRT engine.
        Run this once on the Jetson to optimize inference.
        
        Command equivalent:
        yolo export model=yolov8n-pose.pt format=engine half=True device=0
        """
        if not YOLO_AVAILABLE:
            print("Ultralytics not available for export")
            return
        
        model = YOLO(model_path)
        model.export(format='engine', half=True, device=0)
        print(f"Exported TensorRT engine")
