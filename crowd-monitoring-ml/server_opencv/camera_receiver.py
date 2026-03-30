"""
Camera Stream Receiver for Server-Side Processing
Supports USB cameras, RTSP streams, and video files
"""

import cv2
import time
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamType(Enum):
    """Camera stream types"""
    USB = "usb"
    RTSP = "rtsp"
    HTTP = "http"
    FILE = "file"


@dataclass
class CameraConfig:
    """Camera configuration"""
    source: str | int = 0  # Camera index or stream URL
    width: int = 1280
    height: int = 720
    fps: int = 30
    reconnect_delay: float = 2.0  # Seconds to wait before reconnecting
    max_reconnect_attempts: int = 5


class CameraReceiver:
    """
    Receives and manages camera streams from drone or USB camera
    Handles reconnection and frame buffering
    """
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None
        self.stream_type = self._detect_stream_type()
        self.frame_count = 0
        self.fps_actual = 0.0
        self.last_frame_time = time.time()
        self.reconnect_attempts = 0
        
        logger.info(f"Initializing camera receiver: {self.stream_type.value}")
        self._initialize_capture()
    
    def _detect_stream_type(self) -> StreamType:
        """Detect stream type from source"""
        if isinstance(self.config.source, int):
            return StreamType.USB
        
        source_lower = str(self.config.source).lower()
        if source_lower.startswith('rtsp://'):
            return StreamType.RTSP
        elif source_lower.startswith('http://') or source_lower.startswith('https://'):
            return StreamType.HTTP
        elif source_lower.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            return StreamType.FILE
        else:
            # Assume USB camera index
            try:
                return StreamType.USB if int(self.config.source) >= 0 else StreamType.FILE
            except ValueError:
                return StreamType.FILE
    
    def _initialize_capture(self) -> bool:
        """Initialize video capture"""
        try:
            self.cap = cv2.VideoCapture(self.config.source)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera: {self.config.source}")
                return False
            
            # Set camera properties for USB cameras
            if self.stream_type == StreamType.USB:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            
            # Verify capture
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            logger.info(f"Camera opened: {actual_width}x{actual_height} @ {actual_fps} FPS")
            logger.info(f"Stream type: {self.stream_type.value}")
            
            self.reconnect_attempts = 0
            return True
            
        except Exception as e:
            logger.error(f"Error initializing capture: {e}")
            return False
    
    def read_frame(self) -> Tuple[bool, Optional[cv2.Mat]]:
        """
        Read next frame from camera
        Returns: (success, frame)
        """
        if self.cap is None or not self.cap.isOpened():
            # Attempt reconnection
            if self.reconnect_attempts < self.config.max_reconnect_attempts:
                logger.warning(f"Camera disconnected. Reconnecting... (Attempt {self.reconnect_attempts + 1})")
                time.sleep(self.config.reconnect_delay)
                self.reconnect_attempts += 1
                if self._initialize_capture():
                    return self.read_frame()
            else:
                logger.error("Max reconnection attempts reached")
                return False, None
        
        ret, frame = self.cap.read()
        
        if ret:
            self.frame_count += 1
            
            # Calculate actual FPS
            current_time = time.time()
            time_diff = current_time - self.last_frame_time
            if time_diff > 0:
                self.fps_actual = 0.9 * self.fps_actual + 0.1 * (1.0 / time_diff)
            self.last_frame_time = current_time
            
            # Resize if needed
            if frame.shape[1] != self.config.width or frame.shape[0] != self.config.height:
                frame = cv2.resize(frame, (self.config.width, self.config.height))
            
            return True, frame
        else:
            logger.warning("Failed to read frame")
            return False, None
    
    def get_frame_properties(self) -> dict:
        """Get current frame properties"""
        return {
            'width': self.config.width,
            'height': self.config.height,
            'fps_target': self.config.fps,
            'fps_actual': round(self.fps_actual, 2),
            'frame_count': self.frame_count,
            'stream_type': self.stream_type.value
        }
    
    def release(self):
        """Release camera resources"""
        if self.cap is not None:
            self.cap.release()
            logger.info("Camera released")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def test_camera():
    """Test camera receiver with display"""
    # Try USB camera first
    config = CameraConfig(source=0, width=640, height=480, fps=30)
    
    print("Testing Camera Receiver")
    print("Press 'q' to quit")
    print("-" * 50)
    
    with CameraReceiver(config) as receiver:
        while True:
            ret, frame = receiver.read_frame()
            
            if not ret or frame is None:
                print("Failed to get frame, retrying...")
                time.sleep(0.1)
                continue
            
            # Display frame info
            props = receiver.get_frame_properties()
            info_text = f"Frame: {props['frame_count']} | FPS: {props['fps_actual']} | {props['width']}x{props['height']}"
            
            cv2.putText(frame, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow('Camera Test', frame)
            
            # Exit on 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    cv2.destroyAllWindows()
    print("\nCamera test completed")


if __name__ == "__main__":
    test_camera()
