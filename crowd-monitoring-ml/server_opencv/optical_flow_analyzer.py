"""
Server-Side Optical Flow Analyzer
Adapted from jetson/optical_flow.py for server-side processing
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time


class AnomalyType(Enum):
    """Types of crowd anomalies"""
    NORMAL = "normal"
    BOTTLENECK = "bottleneck"
    PANIC = "panic"
    STAMPEDE = "stampede"
    CONGESTION = "congestion"
    COUNTER_FLOW = "counter_flow"


@dataclass
class FlowRegion:
    """Represents a region with flow statistics"""
    x: int
    y: int
    width: int
    height: int
    magnitude: float
    direction: float  # radians
    divergence: float
    is_anomaly: bool
    anomaly_type: AnomalyType


@dataclass
class AnomalyResult:
    """Result from anomaly detection"""
    anomaly_detected: bool
    anomaly_type: AnomalyType
    confidence: float
    regions: List[FlowRegion]
    global_magnitude: float
    global_divergence: float
    flow_field: Optional[np.ndarray]
    magnitude_map: Optional[np.ndarray]
    inference_time_ms: float


class OpticalFlowAnalyzer:
    """
    Farneback optical flow based crowd anomaly detector
    
    Detects:
    - Normal flow: low magnitude, consistent direction
    - Bottleneck: high inward flow convergence at a point
    - Panic/Stampede: sudden spike in magnitude + divergence from centroid
    - Counter-flow: opposing flow directions in adjacent regions
    """
    
    # Farneback parameters
    PYR_SCALE = 0.5
    LEVELS = 3
    WIN_SIZE = 15
    ITERATIONS = 3
    POLY_N = 5
    POLY_SIGMA = 1.2
    
    def __init__(
        self,
        magnitude_threshold: float = 5.0,
        panic_threshold: float = 15.0,
        divergence_threshold: float = 0.5,
        grid_size: Tuple[int, int] = (8, 6),
        history_size: int = 30
    ):
        self.magnitude_threshold = magnitude_threshold
        self.panic_threshold = panic_threshold
        self.divergence_threshold = divergence_threshold
        self.grid_size = grid_size
        self.history_size = history_size
        
        self.prev_gray: Optional[np.ndarray] = None
        self.magnitude_history: List[float] = []
        self.divergence_history: List[float] = []
        
        self.baseline_magnitude = 2.0
        self.baseline_divergence = 0.1
        self.is_calibrated = False
    
    def reset(self):
        """Reset analyzer state"""
        self.prev_gray = None
        self.magnitude_history.clear()
        self.divergence_history.clear()
    
    def analyze(self, frame: np.ndarray) -> AnomalyResult:
        """
        Analyze frame for crowd anomalies using optical flow
        
        Args:
            frame: BGR image as numpy array
        
        Returns:
            AnomalyResult with detected anomalies
        """
        start_time = time.time()
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Need two frames for flow
        if self.prev_gray is None:
            self.prev_gray = gray
            return self._empty_result()
        
        # Calculate optical flow
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray,
            gray,
            None,
            self.PYR_SCALE,
            self.LEVELS,
            self.WIN_SIZE,
            self.ITERATIONS,
            self.POLY_N,
            self.POLY_SIGMA,
            0
        )
        
        # Calculate magnitude and angle
        magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        
        # Global statistics
        global_magnitude = float(np.mean(magnitude))
        
        # Calculate divergence (simplified)
        flow_x = flow[..., 0]
        flow_y = flow[..., 1]
        divergence = np.gradient(flow_x)[1] + np.gradient(flow_y)[0]
        global_divergence = float(np.mean(divergence))
        
        # Update history
        self.magnitude_history.append(global_magnitude)
        self.divergence_history.append(abs(global_divergence))
        if len(self.magnitude_history) > self.history_size:
            self.magnitude_history.pop(0)
            self.divergence_history.pop(0)
        
        # Grid-based analysis
        regions = self._analyze_grid(flow, magnitude, divergence, frame.shape[:2])
        
        # Detect anomaly type
        anomaly_type, confidence = self._classify_anomaly(
            global_magnitude, global_divergence, regions
        )
        
        # Update previous frame
        self.prev_gray = gray
        
        inference_time = (time.time() - start_time) * 1000
        
        return AnomalyResult(
            anomaly_detected=(anomaly_type != AnomalyType.NORMAL),
            anomaly_type=anomaly_type,
            confidence=confidence,
            regions=regions,
            global_magnitude=global_magnitude,
            global_divergence=global_divergence,
            flow_field=flow,
            magnitude_map=magnitude,
            inference_time_ms=inference_time
        )
    
    def _analyze_grid(
        self,
        flow: np.ndarray,
        magnitude: np.ndarray,
        divergence: np.ndarray,
        frame_shape: Tuple[int, int]
    ) -> List[FlowRegion]:
        """Analyze flow in grid regions"""
        height, width = frame_shape
        grid_h, grid_w = self.grid_size
        
        cell_h = height // grid_h
        cell_w = width // grid_w
        
        regions = []
        
        for i in range(grid_h):
            for j in range(grid_w):
                y1 = i * cell_h
                y2 = min((i + 1) * cell_h, height)
                x1 = j * cell_w
                x2 = min((j + 1) * cell_w, width)
                
                # Extract region
                region_flow = flow[y1:y2, x1:x2]
                region_mag = magnitude[y1:y2, x1:x2]
                region_div = divergence[y1:y2, x1:x2]
                
                # Calculate stats
                avg_magnitude = float(np.mean(region_mag))
                avg_divergence = float(np.mean(region_div))
                
                # Average flow direction
                avg_flow_x = float(np.mean(region_flow[..., 0]))
                avg_flow_y = float(np.mean(region_flow[..., 1]))
                avg_direction = float(np.arctan2(avg_flow_y, avg_flow_x))
                
                # Classify region
                is_anomaly = (
                    avg_magnitude > self.magnitude_threshold or
                    abs(avg_divergence) > self.divergence_threshold
                )
                
                if avg_magnitude > self.panic_threshold:
                    region_type = AnomalyType.PANIC
                elif abs(avg_divergence) > self.divergence_threshold * 1.5:
                    region_type = AnomalyType.BOTTLENECK if avg_divergence < 0 else AnomalyType.STAMPEDE
                else:
                    region_type = AnomalyType.NORMAL
                
                regions.append(FlowRegion(
                    x=x1,
                    y=y1,
                    width=x2 - x1,
                    height=y2 - y1,
                    magnitude=avg_magnitude,
                    direction=avg_direction,
                    divergence=avg_divergence,
                    is_anomaly=is_anomaly,
                    anomaly_type=region_type
                ))
        
        return regions
    
    def _classify_anomaly(
        self,
        global_magnitude: float,
        global_divergence: float,
        regions: List[FlowRegion]
    ) -> Tuple[AnomalyType, float]:
        """Classify overall anomaly type and confidence"""
        
        # Count anomalous regions
        anomaly_regions = [r for r in regions if r.is_anomaly]
        
        if len(anomaly_regions) == 0:
            return AnomalyType.NORMAL, 0.0
        
        # Panic: very high magnitude
        if global_magnitude > self.panic_threshold:
            confidence = min((global_magnitude / self.panic_threshold - 1.0), 1.0)
            return AnomalyType.PANIC, confidence
        
        # Bottleneck: high negative divergence (convergence)
        if global_divergence < -self.divergence_threshold:
            confidence = min(abs(global_divergence / self.divergence_threshold - 1.0), 1.0)
            return AnomalyType.BOTTLENECK, confidence
        
        # Stampede: high positive divergence
        if global_divergence > self.divergence_threshold:
            confidence = min(global_divergence / self.divergence_threshold - 1.0, 1.0)
            return AnomalyType.STAMPEDE, confidence
        
        # Congestion: moderate magnitude, mixed directions
        if global_magnitude > self.magnitude_threshold:
            confidence = min((global_magnitude / self.magnitude_threshold - 1.0), 1.0)
            return AnomalyType.CONGESTION, confidence
        
        return AnomalyType.NORMAL, 0.0
    
    def _empty_result(self) -> AnomalyResult:
        """Return empty result for first frame"""
        return AnomalyResult(
            anomaly_detected=False,
            anomaly_type=AnomalyType.NORMAL,
            confidence=0.0,
            regions=[],
            global_magnitude=0.0,
            global_divergence=0.0,
            flow_field=None,
            magnitude_map=None,
            inference_time_ms=0.0
        )
    
    def visualize_flow(
        self,
        frame: np.ndarray,
        result: AnomalyResult,
        show_arrows: bool = True,
        show_regions: bool = True
    ) -> np.ndarray:
        """
        Visualize optical flow on frame
        
        Args:
            frame: Original BGR frame
            result: AnomalyResult from analyze()
            show_arrows: Draw flow arrows
            show_regions: Highlight anomalous regions
        
        Returns:
            Annotated frame
        """
        vis = frame.copy()
        
        # Show magnitude heatmap
        if result.magnitude_map is not None:
            mag_norm = cv2.normalize(result.magnitude_map, None, 0, 255, cv2.NORM_MINMAX)
            mag_colored = cv2.applyColorMap(mag_norm.astype(np.uint8), cv2.COLORMAP_JET)
            vis = cv2.addWeighted(vis, 0.6, mag_colored, 0.4, 0)
        
        # Draw grid regions
        if show_regions:
            for region in result.regions:
                if region.is_anomaly:
                    color = (0, 0, 255) if region.anomaly_type == AnomalyType.PANIC else (0, 165, 255)
                    cv2.rectangle(
                        vis,
                        (region.x, region.y),
                        (region.x + region.width, region.y + region.height),
                        color,
                        2
                    )
        
        # Draw flow arrows
        if show_arrows and result.flow_field is not None:
            step = 20
            h, w = frame.shape[:2]
            y, x = np.mgrid[step//2:h:step, step//2:w:step].reshape(2, -1).astype(int)
            fx, fy = result.flow_field[y, x].T
            
            lines = np.vstack([x, y, x+fx, y+fy]).T.reshape(-1, 2, 2)
            lines = np.int32(lines + 0.5)
            
            for (x1, y1), (x2, y2) in lines:
                cv2.arrowedLine(vis, (x1, y1), (x2, y2), (0, 255, 0), 1, tipLength=0.3)
        
        # Draw info
        info_lines = [
            f"Anomaly: {result.anomaly_type.value.upper()}",
            f"Confidence: {result.confidence:.2%}",
            f"Magnitude: {result.global_magnitude:.2f}",
            f"Divergence: {result.global_divergence:.3f}"
        ]
        
        y_offset = 30
        for i, line in enumerate(info_lines):
            color = (0, 0, 255) if result.anomaly_detected else (0, 255, 0)
            cv2.putText(vis, line, (10, y_offset + i * 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return vis


def test_optical_flow():
    """Test optical flow analyzer with webcam"""
    import time
    from camera_receiver import CameraReceiver, CameraConfig
    
    print("Testing Optical Flow Analyzer")
    print("Press 'q' to quit, 'r' to reset")
    print("Press 'a' to toggle arrows, 'g' to toggle regions")
    print("-" * 50)
    
    # Initialize camera
    cam_config = CameraConfig(source=0, width=640, height=480, fps=30)
    camera = CameraReceiver(cam_config)
    
    # Initialize analyzer
    analyzer = OpticalFlowAnalyzer(
        magnitude_threshold=3.0,
        panic_threshold=10.0,
        divergence_threshold=0.3
    )
    
    show_arrows = True
    show_regions = True
    
    try:
        while True:
            ret, frame = camera.read_frame()
            
            if not ret or frame is None:
                time.sleep(0.1)
                continue
            
            # Analyze optical flow
            result = analyzer.analyze(frame)
            
            # Visualize
            vis = analyzer.visualize_flow(frame, result, show_arrows, show_regions)
            
            cv2.imshow('Optical Flow Analysis', vis)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                analyzer.reset()
                print("Reset analyzer")
            elif key == ord('a'):
                show_arrows = not show_arrows
                print(f"Arrows: {'ON' if show_arrows else 'OFF'}")
            elif key == ord('g'):
                show_regions = not show_regions
                print(f"Regions: {'ON' if show_regions else 'OFF'}")
    
    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("\nTest completed")


if __name__ == "__main__":
    test_optical_flow()
