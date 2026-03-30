"""
Server-Side Crowd Monitoring Pipeline
OpenCV-only implementation (no YOLO dependency)

Receives camera stream from drone → processes everything on server →
displays results in real-time

Features:
- OpenCV crowd detection (background subtraction)
- Density heatmap generation
- Optical flow anomaly detection
- Real-time visualization
"""

import cv2
import numpy as np
import time
import json
from typing import Optional, Dict
from dataclasses import dataclass, asdict

from camera_receiver import CameraReceiver, CameraConfig
from opencv_crowd_detector import OpenCVCrowdDetector, DetectionMethod
from density_heatmap import DensityHeatmapGenerator, DensityMapConfig
from optical_flow_analyzer import OpticalFlowAnalyzer


@dataclass
class PipelineConfig:
    """Configuration for crowd monitoring pipeline"""
    # Camera settings
    camera_source: str | int = 0  # Camera index or RTSP URL
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30
    
    # Detection settings
    detection_method: str = "mog2"  # mog2, knn, blob
    min_person_area: int = 800
    max_person_area: int = 20000
    
    # Heatmap settings
    heatmap_alpha: float = 0.5
    gaussian_sigma: float = 30.0
    
    # Optical flow settings
    enable_optical_flow: bool = True
    magnitude_threshold: float = 5.0
    panic_threshold: float = 15.0
    
    # Display settings
    display_mode: str = "all"  # all, detection, heatmap, flow
    save_output: bool = False
    output_file: str = "crowd_monitoring_output.avi"
    
    # Processing settings
    target_fps: int = 15  # Process at lower FPS to save CPU
    enable_json_output: bool = True  # Output JSON for dashboard


class CrowdMonitoringPipeline:
    """
    Main pipeline for server-side crowd monitoring
    Integrates camera input, crowd detection, heatmap, and optical flow
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        
        # Initialize components
        print("Initializing Crowd Monitoring Pipeline...")
        
        # Camera
        cam_config = CameraConfig(
            source=config.camera_source,
            width=config.camera_width,
            height=config.camera_height,
            fps=config.camera_fps
        )
        self.camera = CameraReceiver(cam_config)
        
        # Crowd detector
        method_map = {
            "mog2": DetectionMethod.MOG2,
            "knn": DetectionMethod.KNN,
            "blob": DetectionMethod.BLOB
        }
        self.detector = OpenCVCrowdDetector(
            method=method_map.get(config.detection_method, DetectionMethod.MOG2),
            min_person_area=config.min_person_area,
            max_person_area=config.max_person_area
        )
        
        # Heatmap generator
        heatmap_config = DensityMapConfig(
            gaussian_sigma=config.gaussian_sigma,
            alpha=config.heatmap_alpha
        )
        self.heatmap_gen = DensityHeatmapGenerator(heatmap_config)
        
        # Optical flow analyzer
        if config.enable_optical_flow:
            self.flow_analyzer = OpticalFlowAnalyzer(
                magnitude_threshold=config.magnitude_threshold,
                panic_threshold=config.panic_threshold
            )
        else:
            self.flow_analyzer = None
        
        # Video writer for saving output
        self.video_writer: Optional[cv2.VideoWriter] = None
        if config.save_output:
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(
                config.output_file,
                fourcc,
                config.target_fps,
                (config.camera_width, config.camera_height)
            )
        
        # Statistics
        self.frame_count = 0
        self.processing_fps = 0.0
        self.last_process_time = time.time()
        
        print("✓ Pipeline initialized successfully")
    
    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Process single frame through complete pipeline
        
        Returns:
            Dictionary with all processing results
        """
        start_time = time.time()
        
        # 1. Crowd detection
        detection_result = self.detector.detect(frame)
        
        # 2. Generate heatmap
        heatmap, heatmap_metrics = self.heatmap_gen.generate_heatmap(
            frame.shape, detection_result
        )
        heatmap_overlay = self.heatmap_gen.overlay_heatmap(frame, heatmap)
        
        # 3. Grid density for high-density regions
        grid_heatmap, high_density_regions = self.heatmap_gen.generate_grid_density(
            frame.shape, detection_result
        )
        
        # 4. Optical flow analysis
        flow_result = None
        if self.flow_analyzer is not None:
            flow_result = self.flow_analyzer.analyze(frame)
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Prepare results
        results = {
            'timestamp': time.time(),
            'frame_id': self.frame_count,
            'fps': self.processing_fps,
            'processing_time_ms': processing_time,
            
            # Detection results
            'person_count': detection_result.person_count,
            'density_score': detection_result.density_score,
            'total_crowd_area': detection_result.total_crowd_area,
            'bboxes': [
                {
                    'x': bbox.x, 'y': bbox.y,
                    'width': bbox.width, 'height': bbox.height,
                    'confidence': bbox.confidence
                }
                for bbox in detection_result.bboxes
            ],
            
            # Heatmap metrics
            'density': heatmap_metrics,
            'high_density_regions': high_density_regions,
            
            # Optical flow (if enabled)
            'anomaly': None if flow_result is None else {
                'detected': flow_result.anomaly_detected,
                'type': flow_result.anomaly_type.value,
                'confidence': flow_result.confidence,
                'magnitude': flow_result.global_magnitude,
                'divergence': flow_result.global_divergence
            },
            
            # Visualization frames
            'frames': {
                'original': frame,
                'heatmap': heatmap_overlay,
                'grid': grid_heatmap,
                'flow_vis': None if flow_result is None else 
                    self.flow_analyzer.visualize_flow(frame, flow_result)
            }
        }
        
        return results
    
    def create_display_frame(self, results: Dict) -> np.ndarray:
        """Create combined display frame based on display mode"""
        frames = results['frames']
        mode = self.config.display_mode
        
        if mode == "detection":
            # Just detection boxes
            display = self.detector.draw_detections(
                frames['original'],
                self.detector.detect(frames['original'])
            )
        
        elif mode == "heatmap":
            # Heatmap overlay
            display = frames['heatmap'].copy()
            
        elif mode == "flow":
            # Optical flow visualization
            display = frames['flow_vis'] if frames['flow_vis'] is not None else frames['original']
        
        else:  # "all" - create grid layout
            original = frames['original']
            heatmap = frames['heatmap']
            flow_vis = frames['flow_vis'] if frames['flow_vis'] is not None else np.zeros_like(original)
            
            # Grid with high-density regions
            grid_overlay = self.heatmap_gen.overlay_heatmap(original, frames['grid'], alpha=0.6)
            grid_annotated = self.heatmap_gen.draw_high_density_regions(
                grid_overlay, results['high_density_regions']
            )
            
            # Create 2x2 grid
            top_row = np.hstack([original, heatmap])
            bottom_row = np.hstack([grid_annotated, flow_vis])
            display = np.vstack([top_row, bottom_row])
            
            # Resize to fit screen
            display = cv2.resize(display, (1280, 720))
        
        # Add overlay info
        info_lines = [
            f"Frame: {results['frame_id']} | FPS: {results['fps']:.1f}",
            f"Count: {results['person_count']} | Density: {results['density_score']:.2%}",
        ]
        
        if results['anomaly'] is not None and results['anomaly']['detected']:
            info_lines.append(
                f"⚠ ANOMALY: {results['anomaly']['type'].upper()} "
                f"({results['anomaly']['confidence']:.0%})"
            )
        
        y_offset = 30
        for i, line in enumerate(info_lines):
            bg_color = (0, 0, 0) if not (results['anomaly'] and results['anomaly']['detected']) else (0, 0, 139)
            text_color = (255, 255, 255)
            
            # Draw background
            (text_width, text_height), _ = cv2.getTextSize(
                line, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
            )
            cv2.rectangle(
                display,
                (5, y_offset + i * 30 - text_height - 5),
                (15 + text_width, y_offset + i * 30 + 5),
                bg_color,
                -1
            )
            
            # Draw text
            cv2.putText(
                display, line, (10, y_offset + i * 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2
            )
        
        return display
    
    def run(self):
        """
        Main processing loop
        Runs until user presses 'q'
        """
        print("\n" + "="*60)
        print("CROWD MONITORING PIPELINE - RUNNING")
        print("="*60)
        print("\nControls:")
        print("  q - Quit")
        print("  r - Reset background model")
        print("  f - Reset optical flow")
        print("  1 - Detection view")
        print("  2 - Heatmap view")
        print("  3 - Flow view")
        print("  4 - All views (grid)")
        print("  s - Save current frame")
        print("\n" + "="*60 + "\n")
        
        frame_interval = 1.0 / self.config.target_fps
        
        try:
            while True:
                loop_start = time.time()
                
                # Read frame
                ret, frame = self.camera.read_frame()
                if not ret or frame is None:
                    print("Failed to read frame, retrying...")
                    time.sleep(0.1)
                    continue
                
                # Process frame
                results = self.process_frame(frame)
                self.frame_count += 1
                
                # Update FPS
                current_time = time.time()
                time_diff = current_time - self.last_process_time
                if time_diff > 0:
                    self.processing_fps = 0.9 * self.processing_fps + 0.1 * (1.0 / time_diff)
                self.last_process_time = current_time
                
                # Create display
                display_frame = self.create_display_frame(results)
                
                # Save to video if enabled
                if self.video_writer is not None and display_frame.shape[:2] == (self.config.camera_height, self.config.camera_width):
                    self.video_writer.write(display_frame)
                
                # Save JSON output if enabled
                if self.config.enable_json_output and self.frame_count % 30 == 0:
                    # Save periodic JSON snapshots
                    json_output = {k: v for k, v in results.items() if k != 'frames'}
                    # Could send this to dashboard via WebSocket
                
                # Display
                cv2.imshow('Crowd Monitoring - Server Pipeline', display_frame)
                
                # Handle keyboard
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\nShutting down...")
                    break
                elif key == ord('r'):
                    print("Resetting background model...")
                    self.detector.reset_background()
                elif key == ord('f') and self.flow_analyzer:
                    print("Resetting optical flow...")
                    self.flow_analyzer.reset()
                elif key == ord('1'):
                    self.config.display_mode = "detection"
                    print("View: Detection only")
                elif key == ord('2'):
                    self.config.display_mode = "heatmap"
                    print("View: Heatmap only")
                elif key == ord('3'):
                    self.config.display_mode = "flow"
                    print("View: Optical flow only")
                elif key == ord('4'):
                    self.config.display_mode = "all"
                    print("View: All (grid)")
                elif key == ord('s'):
                    filename = f"snapshot_{int(time.time())}.jpg"
                    cv2.imwrite(filename, display_frame)
                    print(f"Saved: {filename}")
                
                # Throttle to target FPS
                elapsed = time.time() - loop_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        print("\nCleaning up...")
        self.camera.release()
        if self.video_writer is not None:
            self.video_writer.release()
        cv2.destroyAllWindows()
        print("✓ Pipeline stopped")


def main():
    """Main entry point"""
    
    # Default configuration
    config = PipelineConfig(
        camera_source=1,  # USB camera (change to RTSP URL for drone)
        camera_width=1280,
        camera_height=720,
        camera_fps=30,
        
        detection_method="mog2",
        min_person_area=800,
        max_person_area=20000,
        
        heatmap_alpha=0.5,
        gaussian_sigma=30.0,
        
        enable_optical_flow=True,
        magnitude_threshold=5.0,
        panic_threshold=15.0,
        
        display_mode="all",
        save_output=False,
        target_fps=15
    )
    
    # Create and run pipeline
    pipeline = CrowdMonitoringPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
