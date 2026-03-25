"""
Optical Flow Anomaly Detection Module.
Uses Farneback optical flow to detect crowd anomalies like panic and bottlenecks.
"""
import numpy as np
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum
import time

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: OpenCV not available for optical flow")


class AnomalyType(Enum):
    """Types of crowd anomalies."""
    NORMAL = "normal"
    BOTTLENECK = "bottleneck"
    PANIC = "panic"
    STAMPEDE = "stampede"
    CONGESTION = "congestion"
    COUNTER_FLOW = "counter_flow"


@dataclass
class FlowRegion:
    """Represents a region with flow statistics."""
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
    """Result from anomaly detection."""
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
    Farneback optical flow based crowd anomaly detector.
    
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
        magnitude_threshold: float = 5.0,  # Normal vs high magnitude
        panic_threshold: float = 15.0,  # Panic detection threshold
        divergence_threshold: float = 0.5,  # Convergence/divergence threshold
        grid_size: Tuple[int, int] = (8, 6),  # Analysis grid
        history_size: int = 30  # Frames to maintain for trend analysis
    ):
        self.magnitude_threshold = magnitude_threshold
        self.panic_threshold = panic_threshold
        self.divergence_threshold = divergence_threshold
        self.grid_size = grid_size
        self.history_size = history_size
        
        # Previous frame for flow computation
        self.prev_gray: Optional[np.ndarray] = None
        
        # History buffers
        self.magnitude_history: List[float] = []
        self.divergence_history: List[float] = []
        
        # Calibration
        self.baseline_magnitude = 2.0
        self.baseline_divergence = 0.1
        self.is_calibrated = False
    
    def reset(self):
        """Reset analyzer state."""
        self.prev_gray = None
        self.magnitude_history.clear()
        self.divergence_history.clear()
        self.is_calibrated = False
    
    def calibrate(self, frames: List[np.ndarray]):
        """
        Calibrate thresholds on normal crowd footage.
        
        Args:
            frames: List of BGR frames representing normal behavior
        """
        if len(frames) < 10:
            print("Need at least 10 frames for calibration")
            return
        
        magnitudes = []
        divergences = []
        
        for i in range(1, len(frames)):
            result = self.analyze(frames[i])
            magnitudes.append(result.global_magnitude)
            divergences.append(abs(result.global_divergence))
        
        # Set baselines as mean + 2 std
        self.baseline_magnitude = np.mean(magnitudes) + 2 * np.std(magnitudes)
        self.baseline_divergence = np.mean(divergences) + 2 * np.std(divergences)
        
        # Update thresholds
        self.magnitude_threshold = self.baseline_magnitude * 2
        self.panic_threshold = self.baseline_magnitude * 4
        self.divergence_threshold = self.baseline_divergence * 3
        
        self.is_calibrated = True
        print(f"Calibrated: mag_threshold={self.magnitude_threshold:.2f}, "
              f"panic_threshold={self.panic_threshold:.2f}")
    
    def analyze(self, frame: np.ndarray) -> AnomalyResult:
        """
        Analyze frame for crowd anomalies using optical flow.
        
        Args:
            frame: BGR image as numpy array
        
        Returns:
            AnomalyResult with detected anomalies and flow statistics
        """
        start_time = time.time()
        
        if not CV2_AVAILABLE:
            return self._mock_result()
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # First frame - no flow yet
        if self.prev_gray is None:
            self.prev_gray = gray
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
        
        # Compute optical flow
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray, gray, None,
            pyr_scale=self.PYR_SCALE,
            levels=self.LEVELS,
            winsize=self.WIN_SIZE,
            iterations=self.ITERATIONS,
            poly_n=self.POLY_N,
            poly_sigma=self.POLY_SIGMA,
            flags=0
        )
        
        # Update previous frame
        self.prev_gray = gray
        
        # Compute magnitude and angle
        magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        
        # Analyze flow field
        regions = self._analyze_regions(flow, magnitude, angle, frame.shape[:2])
        global_mag = float(np.mean(magnitude))
        global_div = self._compute_divergence(flow)
        
        # Update history
        self._update_history(global_mag, global_div)
        
        # Detect anomalies
        anomaly_type, confidence = self._classify_anomaly(
            global_mag, global_div, regions
        )
        
        inference_time = (time.time() - start_time) * 1000
        
        return AnomalyResult(
            anomaly_detected=(anomaly_type != AnomalyType.NORMAL),
            anomaly_type=anomaly_type,
            confidence=confidence,
            regions=regions,
            global_magnitude=global_mag,
            global_divergence=global_div,
            flow_field=flow,
            magnitude_map=magnitude,
            inference_time_ms=inference_time
        )
    
    def _analyze_regions(
        self,
        flow: np.ndarray,
        magnitude: np.ndarray,
        angle: np.ndarray,
        frame_shape: Tuple[int, int]
    ) -> List[FlowRegion]:
        """Analyze flow in grid regions."""
        h, w = frame_shape
        grid_h, grid_w = self.grid_size
        cell_h, cell_w = h // grid_h, w // grid_w
        
        regions = []
        
        for i in range(grid_h):
            for j in range(grid_w):
                y1, y2 = i * cell_h, (i + 1) * cell_h
                x1, x2 = j * cell_w, (j + 1) * cell_w
                
                cell_flow = flow[y1:y2, x1:x2]
                cell_mag = magnitude[y1:y2, x1:x2]
                cell_angle = angle[y1:y2, x1:x2]
                
                avg_mag = float(np.mean(cell_mag))
                avg_angle = float(np.mean(cell_angle))
                cell_div = self._compute_divergence(cell_flow)
                
                is_anomaly = avg_mag > self.magnitude_threshold
                anomaly_type = AnomalyType.NORMAL
                
                if avg_mag > self.panic_threshold:
                    anomaly_type = AnomalyType.PANIC
                elif cell_div > self.divergence_threshold:
                    anomaly_type = AnomalyType.BOTTLENECK
                elif cell_div < -self.divergence_threshold:
                    anomaly_type = AnomalyType.CONGESTION
                
                regions.append(FlowRegion(
                    x=x1,
                    y=y1,
                    width=cell_w,
                    height=cell_h,
                    magnitude=avg_mag,
                    direction=avg_angle,
                    divergence=cell_div,
                    is_anomaly=is_anomaly,
                    anomaly_type=anomaly_type
                ))
        
        return regions
    
    def _compute_divergence(self, flow: np.ndarray) -> float:
        """
        Compute divergence of flow field.
        Positive = expansion (panic outward)
        Negative = convergence (bottleneck)
        """
        if flow.shape[0] < 2 or flow.shape[1] < 2:
            return 0.0
        
        # Compute partial derivatives
        du_dx = np.gradient(flow[..., 0], axis=1)
        dv_dy = np.gradient(flow[..., 1], axis=0)
        
        # Divergence = du/dx + dv/dy
        divergence = du_dx + dv_dy
        
        return float(np.mean(divergence))
    
    def _update_history(self, magnitude: float, divergence: float):
        """Update history buffers."""
        self.magnitude_history.append(magnitude)
        self.divergence_history.append(divergence)
        
        if len(self.magnitude_history) > self.history_size:
            self.magnitude_history.pop(0)
            self.divergence_history.pop(0)
    
    def _classify_anomaly(
        self,
        global_mag: float,
        global_div: float,
        regions: List[FlowRegion]
    ) -> Tuple[AnomalyType, float]:
        """Classify overall anomaly type."""
        
        # Count anomalous regions
        anomaly_count = sum(1 for r in regions if r.is_anomaly)
        anomaly_ratio = anomaly_count / len(regions) if regions else 0
        
        # Check for sudden spike (compare to recent history)
        if len(self.magnitude_history) > 5:
            recent_avg = np.mean(self.magnitude_history[-5:])
            older_avg = np.mean(self.magnitude_history[:-5]) if len(self.magnitude_history) > 5 else recent_avg
            spike_ratio = recent_avg / (older_avg + 0.1)
        else:
            spike_ratio = 1.0
        
        # Classification logic
        confidence = 0.0
        anomaly_type = AnomalyType.NORMAL
        
        # Panic/Stampede: high magnitude + high divergence + sudden spike
        if global_mag > self.panic_threshold and global_div > self.divergence_threshold:
            anomaly_type = AnomalyType.PANIC
            confidence = min(0.5 + anomaly_ratio * 0.3 + (spike_ratio - 1) * 0.2, 1.0)
        
        # Stampede: very high magnitude with directional consistency
        elif global_mag > self.panic_threshold * 1.5:
            anomaly_type = AnomalyType.STAMPEDE
            confidence = min(0.6 + anomaly_ratio * 0.4, 1.0)
        
        # Bottleneck: high convergence (negative divergence)
        elif global_div < -self.divergence_threshold:
            anomaly_type = AnomalyType.BOTTLENECK
            confidence = min(0.4 + abs(global_div) * 0.3, 0.9)
        
        # Congestion: moderate magnitude, mixed directions
        elif global_mag > self.magnitude_threshold and anomaly_ratio > 0.3:
            anomaly_type = AnomalyType.CONGESTION
            confidence = min(0.3 + anomaly_ratio * 0.5, 0.8)
        
        # Counter-flow: check adjacent regions for opposing directions
        elif self._detect_counter_flow(regions):
            anomaly_type = AnomalyType.COUNTER_FLOW
            confidence = 0.6
        
        return anomaly_type, confidence
    
    def _detect_counter_flow(self, regions: List[FlowRegion]) -> bool:
        """Detect if adjacent regions have opposing flow directions."""
        if len(regions) < 4:
            return False
        
        # Check horizontal neighbors
        for i, r1 in enumerate(regions):
            for r2 in regions[i+1:]:
                # Check if adjacent
                if abs(r1.x - r2.x) == r1.width and r1.y == r2.y:
                    # Check if opposing directions (roughly 180 degrees apart)
                    angle_diff = abs(r1.direction - r2.direction)
                    if 2.5 < angle_diff < 3.8:  # ~143 to ~218 degrees
                        if r1.magnitude > 2 and r2.magnitude > 2:
                            return True
        
        return False
    
    def _mock_result(self) -> AnomalyResult:
        """Generate mock result when OpenCV not available."""
        return AnomalyResult(
            anomaly_detected=False,
            anomaly_type=AnomalyType.NORMAL,
            confidence=0.0,
            regions=[],
            global_magnitude=np.random.uniform(1, 5),
            global_divergence=np.random.uniform(-0.2, 0.2),
            flow_field=None,
            magnitude_map=None,
            inference_time_ms=10.0
        )
    
    def visualize_flow(
        self,
        frame: np.ndarray,
        flow: np.ndarray,
        step: int = 16,
        scale: float = 3.0
    ) -> np.ndarray:
        """
        Visualize optical flow as arrows on frame.
        
        Args:
            frame: BGR frame
            flow: Optical flow field
            step: Arrow spacing
            scale: Arrow length multiplier
        
        Returns:
            Frame with flow arrows overlaid
        """
        if not CV2_AVAILABLE or flow is None:
            return frame
        
        vis = frame.copy()
        h, w = frame.shape[:2]
        
        # Draw arrows
        for y in range(0, h, step):
            for x in range(0, w, step):
                fx, fy = flow[y, x]
                cv2.arrowedLine(
                    vis,
                    (x, y),
                    (int(x + fx * scale), int(y + fy * scale)),
                    (0, 255, 0),
                    1,
                    tipLength=0.3
                )
        
        return vis
    
    def visualize_magnitude(
        self,
        frame: np.ndarray,
        magnitude_map: np.ndarray,
        alpha: float = 0.5
    ) -> np.ndarray:
        """
        Overlay magnitude heatmap on frame.
        
        Args:
            frame: BGR frame
            magnitude_map: Flow magnitude array
            alpha: Overlay transparency
        
        Returns:
            Frame with magnitude heatmap overlay
        """
        if not CV2_AVAILABLE or magnitude_map is None:
            return frame
        
        # Normalize and colorize
        normalized = np.clip(magnitude_map / self.panic_threshold * 255, 0, 255).astype(np.uint8)
        heatmap = cv2.applyColorMap(normalized, cv2.COLORMAP_HOT)
        
        return cv2.addWeighted(frame, 1 - alpha, heatmap, alpha, 0)
    
    def get_stats(self) -> Dict:
        """Get analyzer statistics."""
        return {
            "is_calibrated": self.is_calibrated,
            "baseline_magnitude": self.baseline_magnitude,
            "baseline_divergence": self.baseline_divergence,
            "history_length": len(self.magnitude_history),
            "avg_recent_magnitude": np.mean(self.magnitude_history[-10:]) if self.magnitude_history else 0
        }
