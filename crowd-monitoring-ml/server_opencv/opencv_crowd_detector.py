"""
OpenCV-Only Crowd Detection
Uses background subtraction and contour detection (no YOLO dependency)
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum


class DetectionMethod(Enum):
    """Crowd detection methods"""
    MOG2 = "mog2"  # Background subtraction (best for moving crowds)
    KNN = "knn"    # Alternative background subtraction
    BLOB = "blob"  # Simple blob detection (static crowds)


@dataclass
class BoundingBox:
    """Detected person bounding box"""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    
    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    @property
    def aspect_ratio(self) -> float:
        return self.height / self.width if self.width > 0 else 0


@dataclass
class CrowdDetectionResult:
    """Result from crowd detection"""
    person_count: int
    bboxes: List[BoundingBox]
    foreground_mask: np.ndarray
    total_crowd_area: int
    density_score: float  # 0-1 score based on coverage


class OpenCVCrowdDetector:
    """
    Crowd detection using classical OpenCV methods
    No YOLO dependency - uses background subtraction and contour detection
    """
    
    def __init__(
        self,
        method: DetectionMethod = DetectionMethod.MOG2,
        min_person_area: int = 800,      # Min pixels for person blob
        max_person_area: int = 20000,    # Max pixels for person blob
        min_aspect_ratio: float = 1.2,   # Height/width ratio (people are taller)
        max_aspect_ratio: float = 4.0,   # Max ratio
        learning_rate: float = 0.01,     # Background learning rate
        history: int = 500,              # Background history frames
        var_threshold: int = 16,         # Variance threshold for MOG2
        detect_shadows: bool = False,    # Shadow detection (slower)
    ):
        self.method = method
        self.min_person_area = min_person_area
        self.max_person_area = max_person_area
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.learning_rate = learning_rate
        
        # Initialize background subtractor
        if method == DetectionMethod.MOG2:
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=history,
                varThreshold=var_threshold,
                detectShadows=detect_shadows
            )
        elif method == DetectionMethod.KNN:
            self.bg_subtractor = cv2.createBackgroundSubtractorKNN(
                history=history,
                detectShadows=detect_shadows
            )
        else:
            self.bg_subtractor = None
        
        # Morphological kernels for cleanup
        self.kernel_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        
        self.frame_count = 0
        self.frame_shape: Optional[Tuple[int, int]] = None
    
    def detect(self, frame: np.ndarray) -> CrowdDetectionResult:
        """
        Detect people in frame
        Returns: CrowdDetectionResult with person count and bounding boxes
        """
        self.frame_count += 1
        
        if self.frame_shape is None:
            self.frame_shape = (frame.shape[0], frame.shape[1])
        
        if self.method == DetectionMethod.BLOB:
            return self._detect_blob(frame)
        else:
            return self._detect_background_subtraction(frame)
    
    def _detect_background_subtraction(self, frame: np.ndarray) -> CrowdDetectionResult:
        """Detect using background subtraction (MOG2/KNN)"""
        
        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(frame, learningRate=self.learning_rate)
        
        # Clean up mask
        fg_mask = self._clean_mask(fg_mask)
        
        # Find contours
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter and extract bounding boxes
        bboxes = []
        total_area = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area
            if area < self.min_person_area or area > self.max_person_area:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(x, y, w, h)
            
            # Filter by aspect ratio (people are usually taller than wide)
            if bbox.aspect_ratio < self.min_aspect_ratio or bbox.aspect_ratio > self.max_aspect_ratio:
                continue
            
            bboxes.append(bbox)
            total_area += area
        
        # Calculate density score (0-1)
        frame_area = self.frame_shape[0] * self.frame_shape[1]
        density_score = min(total_area / frame_area, 1.0)
        
        return CrowdDetectionResult(
            person_count=len(bboxes),
            bboxes=bboxes,
            foreground_mask=fg_mask,
            total_crowd_area=total_area,
            density_score=density_score
        )
    
    def _detect_blob(self, frame: np.ndarray) -> CrowdDetectionResult:
        """Simple blob detection for static crowds"""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Clean up
        binary = self._clean_mask(binary)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        total_area = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if area < self.min_person_area or area > self.max_person_area:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(x, y, w, h)
            
            if bbox.aspect_ratio < self.min_aspect_ratio or bbox.aspect_ratio > self.max_aspect_ratio:
                continue
            
            bboxes.append(bbox)
            total_area += area
        
        frame_area = self.frame_shape[0] * self.frame_shape[1]
        density_score = min(total_area / frame_area, 1.0)
        
        return CrowdDetectionResult(
            person_count=len(bboxes),
            bboxes=bboxes,
            foreground_mask=binary,
            total_crowd_area=total_area,
            density_score=density_score
        )
    
    def _clean_mask(self, mask: np.ndarray) -> np.ndarray:
        """Clean up foreground mask with morphological operations"""
        # Remove noise
        mask = cv2.erode(mask, self.kernel_erode, iterations=1)
        # Fill gaps
        mask = cv2.dilate(mask, self.kernel_dilate, iterations=2)
        # Smooth
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel_dilate)
        
        return mask
    
    def draw_detections(self, frame: np.ndarray, result: CrowdDetectionResult) -> np.ndarray:
        """
        Draw bounding boxes and info on frame
        Returns: annotated frame
        """
        annotated = frame.copy()
        
        # Draw bounding boxes
        for bbox in result.bboxes:
            cv2.rectangle(
                annotated,
                (bbox.x, bbox.y),
                (bbox.x + bbox.width, bbox.y + bbox.height),
                (0, 255, 0),  # Green
                2
            )
            # Draw center point
            cv2.circle(annotated, bbox.center, 3, (0, 0, 255), -1)
        
        # Draw info text
        info_lines = [
            f"Count: {result.person_count}",
            f"Density: {result.density_score:.2%}",
            f"Method: {self.method.value.upper()}"
        ]
        
        y_offset = 30
        for i, line in enumerate(info_lines):
            cv2.putText(
                annotated,
                line,
                (10, y_offset + i * 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
        
        return annotated
    
    def reset_background(self):
        """Reset background model (useful when scene changes)"""
        if self.bg_subtractor is not None:
            if self.method == DetectionMethod.MOG2:
                self.bg_subtractor = cv2.createBackgroundSubtractorMOG2()
            elif self.method == DetectionMethod.KNN:
                self.bg_subtractor = cv2.createBackgroundSubtractorKNN()


def test_detector():
    """Test crowd detector with webcam"""
    import time
    from camera_receiver import CameraReceiver, CameraConfig
    
    print("Testing OpenCV Crowd Detector")
    print("Press 'q' to quit, 'r' to reset background")
    print("-" * 50)
    
    # Initialize camera
    cam_config = CameraConfig(source=0, width=640, height=480, fps=30)
    camera = CameraReceiver(cam_config)
    
    # Initialize detector
    detector = OpenCVCrowdDetector(
        method=DetectionMethod.MOG2,
        min_person_area=800,
        learning_rate=0.01
    )
    
    try:
        while True:
            ret, frame = camera.read_frame()
            
            if not ret or frame is None:
                print("Failed to get frame")
                time.sleep(0.1)
                continue
            
            # Detect crowd
            result = detector.detect(frame)
            
            # Draw results
            annotated = detector.draw_detections(frame, result)
            
            # Show foreground mask
            fg_mask_color = cv2.cvtColor(result.foreground_mask, cv2.COLOR_GRAY2BGR)
            combined = np.hstack([annotated, fg_mask_color])
            
            cv2.imshow('Crowd Detection | Foreground Mask', combined)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                print("Resetting background model...")
                detector.reset_background()
    
    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("\nTest completed")


if __name__ == "__main__":
    test_detector()
