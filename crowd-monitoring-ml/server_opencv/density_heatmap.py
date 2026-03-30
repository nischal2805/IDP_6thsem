"""
OpenCV-based Density Heatmap Generation
Creates visual heatmaps from crowd detection results
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from opencv_crowd_detector import BoundingBox, CrowdDetectionResult


@dataclass
class DensityMapConfig:
    """Configuration for density heatmap generation"""
    gaussian_sigma: float = 30.0    # Gaussian blur sigma
    colormap: int = cv2.COLORMAP_JET  # OpenCV colormap
    alpha: float = 0.5               # Overlay transparency (0-1)
    grid_size: int = 32              # Grid cell size for density calculation
    normalize: bool = True            # Normalize density to 0-255


class DensityHeatmapGenerator:
    """
    Generate density heatmaps from crowd detection results
    Uses Gaussian blur to create smooth density visualization
    """
    
    def __init__(self, config: DensityMapConfig = DensityMapConfig()):
        self.config = config
    
    def generate_heatmap(
        self,
        frame_shape: Tuple[int, int],
        detection_result: CrowdDetectionResult
    ) -> Tuple[np.ndarray, dict]:
        """
        Generate density heatmap from detection result
        
        Args:
            frame_shape: (height, width) of the frame
            detection_result: CrowdDetectionResult from detector
        
        Returns:
            (heatmap_overlay, metrics_dict)
        """
        height, width = frame_shape[:2]
        
        # Create empty density map
        density_map = np.zeros((height, width), dtype=np.float32)
        
        # Add Gaussian blob for each detected person
        for bbox in detection_result.bboxes:
            center_x, center_y = bbox.center
            
            # Create Gaussian kernel based on person size
            kernel_size = max(bbox.width, bbox.height)
            kernel_size = max(31, min(kernel_size, 101))  # Clamp to reasonable range
            if kernel_size % 2 == 0:
                kernel_size += 1  # Must be odd
            
            # Add Gaussian contribution
            y, x = np.ogrid[-center_y:height-center_y, -center_x:width-center_x]
            sigma = self.config.gaussian_sigma
            gaussian = np.exp(-(x*x + y*y) / (2.*sigma*sigma))
            
            density_map += gaussian
        
        # Apply additional Gaussian blur for smoothing
        density_map = cv2.GaussianBlur(density_map, (31, 31), self.config.gaussian_sigma / 2)
        
        # Normalize to 0-255
        if self.config.normalize and density_map.max() > 0:
            density_map = (density_map / density_map.max() * 255).astype(np.uint8)
        else:
            density_map = np.clip(density_map * 255, 0, 255).astype(np.uint8)
        
        # Apply colormap
        heatmap = cv2.applyColorMap(density_map, self.config.colormap)
        
        # Calculate metrics
        metrics = self._calculate_metrics(density_map, detection_result)
        
        return heatmap, metrics
    
    def overlay_heatmap(
        self,
        frame: np.ndarray,
        heatmap: np.ndarray,
        alpha: Optional[float] = None
    ) -> np.ndarray:
        """
        Overlay heatmap on original frame
        
        Args:
            frame: Original frame
            heatmap: Generated heatmap
            alpha: Overlay transparency (uses config if None)
        
        Returns:
            Blended frame with heatmap overlay
        """
        if alpha is None:
            alpha = self.config.alpha
        
        # Ensure same size
        if frame.shape[:2] != heatmap.shape[:2]:
            heatmap = cv2.resize(heatmap, (frame.shape[1], frame.shape[0]))
        
        # Blend
        overlay = cv2.addWeighted(frame, 1 - alpha, heatmap, alpha, 0)
        
        return overlay
    
    def generate_grid_density(
        self,
        frame_shape: Tuple[int, int],
        detection_result: CrowdDetectionResult
    ) -> Tuple[np.ndarray, List[dict]]:
        """
        Generate grid-based density map
        Divides frame into grid cells and counts people per cell
        
        Returns:
            (grid_density_map, high_density_regions)
        """
        height, width = frame_shape[:2]
        grid_size = self.config.grid_size
        
        # Calculate grid dimensions
        grid_h = (height + grid_size - 1) // grid_size
        grid_w = (width + grid_size - 1) // grid_size
        
        # Create grid
        grid_density = np.zeros((grid_h, grid_w), dtype=np.int32)
        
        # Count people in each grid cell
        for bbox in detection_result.bboxes:
            center_x, center_y = bbox.center
            grid_x = min(center_x // grid_size, grid_w - 1)
            grid_y = min(center_y // grid_size, grid_h - 1)
            grid_density[grid_y, grid_x] += 1
        
        # Resize to frame size for visualization
        grid_density_resized = cv2.resize(
            grid_density.astype(np.float32),
            (width, height),
            interpolation=cv2.INTER_NEAREST
        )
        
        # Normalize and apply colormap
        if grid_density_resized.max() > 0:
            grid_density_norm = (grid_density_resized / grid_density_resized.max() * 255).astype(np.uint8)
        else:
            grid_density_norm = grid_density_resized.astype(np.uint8)
        
        grid_heatmap = cv2.applyColorMap(grid_density_norm, self.config.colormap)
        
        # Find high-density regions (top 25%)
        threshold = np.percentile(grid_density[grid_density > 0], 75) if grid_density.max() > 0 else 0
        high_density_regions = []
        
        for i in range(grid_h):
            for j in range(grid_w):
                if grid_density[i, j] >= threshold and grid_density[i, j] > 0:
                    high_density_regions.append({
                        'x': j * grid_size,
                        'y': i * grid_size,
                        'width': grid_size,
                        'height': grid_size,
                        'count': int(grid_density[i, j])
                    })
        
        return grid_heatmap, high_density_regions
    
    def _calculate_metrics(self, density_map: np.ndarray, detection_result: CrowdDetectionResult) -> dict:
        """Calculate density metrics"""
        return {
            'peak_density': float(density_map.max()),
            'avg_density': float(density_map.mean()),
            'density_std': float(density_map.std()),
            'person_count': detection_result.person_count,
            'total_area': detection_result.total_crowd_area,
            'density_score': detection_result.density_score,
        }
    
    def draw_high_density_regions(
        self,
        frame: np.ndarray,
        high_density_regions: List[dict]
    ) -> np.ndarray:
        """Draw rectangles around high-density regions"""
        annotated = frame.copy()
        
        for region in high_density_regions:
            cv2.rectangle(
                annotated,
                (region['x'], region['y']),
                (region['x'] + region['width'], region['y'] + region['height']),
                (0, 0, 255),  # Red
                2
            )
            # Draw count
            cv2.putText(
                annotated,
                f"{region['count']}",
                (region['x'] + 5, region['y'] + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2
            )
        
        return annotated


def test_heatmap():
    """Test heatmap generation with live camera"""
    import time
    from camera_receiver import CameraReceiver, CameraConfig
    from opencv_crowd_detector import OpenCVCrowdDetector, DetectionMethod
    
    print("Testing Density Heatmap Generator")
    print("Press 'q' to quit, 'r' to reset background")
    print("Press 'g' to toggle grid view")
    print("-" * 50)
    
    # Initialize camera
    cam_config = CameraConfig(source=0, width=640, height=480, fps=30)
    camera = CameraReceiver(cam_config)
    
    # Initialize detector
    detector = OpenCVCrowdDetector(method=DetectionMethod.MOG2)
    
    # Initialize heatmap generator
    heatmap_config = DensityMapConfig(gaussian_sigma=40, alpha=0.6)
    heatmap_gen = DensityHeatmapGenerator(heatmap_config)
    
    show_grid = False
    
    try:
        while True:
            ret, frame = camera.read_frame()
            
            if not ret or frame is None:
                time.sleep(0.1)
                continue
            
            # Detect crowd
            result = detector.detect(frame)
            
            # Generate heatmap
            if show_grid:
                grid_heatmap, high_density_regions = heatmap_gen.generate_grid_density(
                    frame.shape, result
                )
                overlay = heatmap_gen.overlay_heatmap(frame, grid_heatmap)
                overlay = heatmap_gen.draw_high_density_regions(overlay, high_density_regions)
            else:
                heatmap, metrics = heatmap_gen.generate_heatmap(frame.shape, result)
                overlay = heatmap_gen.overlay_heatmap(frame, heatmap)
            
            # Draw detection boxes
            for bbox in result.bboxes:
                cv2.rectangle(
                    overlay,
                    (bbox.x, bbox.y),
                    (bbox.x + bbox.width, bbox.y + bbox.height),
                    (0, 255, 0),
                    1
                )
            
            # Add info
            mode_text = "Grid Mode" if show_grid else "Gaussian Mode"
            cv2.putText(overlay, f"{mode_text} | Count: {result.person_count}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow('Density Heatmap', overlay)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                detector.reset_background()
            elif key == ord('g'):
                show_grid = not show_grid
                print(f"Switched to {'Grid' if show_grid else 'Gaussian'} mode")
    
    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("\nTest completed")


if __name__ == "__main__":
    test_heatmap()
