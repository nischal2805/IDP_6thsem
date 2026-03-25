"""
Fall Detection Module - Rule-based and LSTM-based classifiers.
Implements two-stage fall detection: pose estimation -> temporal classification.
"""
import numpy as np
from typing import List, Dict, Tuple, Optional, Deque
from collections import deque
from dataclasses import dataclass
from enum import Enum
import time

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from pose_estimator import PersonDetection


class FallState(Enum):
    """Fall detection states."""
    STANDING = "standing"
    FALLING = "falling"
    FALLEN = "fallen"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


@dataclass
class FallEvent:
    """Represents a detected fall event."""
    person_id: int
    timestamp: float
    confidence: float
    state: FallState
    bbox: np.ndarray
    hip_position: Tuple[float, float]
    duration_seconds: float = 0.0
    confirmed: bool = False


class PersonTracker:
    """
    Tracks a single person across frames for fall detection.
    Maintains temporal window of detections for analysis.
    """
    
    def __init__(self, person_id: int, window_size: int = 20):
        self.person_id = person_id
        self.window_size = window_size
        
        # Temporal buffers
        self.bbox_history: Deque[np.ndarray] = deque(maxlen=window_size)
        self.aspect_ratio_history: Deque[float] = deque(maxlen=window_size)
        self.hip_y_history: Deque[float] = deque(maxlen=window_size)
        self.keypoint_history: Deque[np.ndarray] = deque(maxlen=window_size)
        self.timestamps: Deque[float] = deque(maxlen=window_size)
        
        # State tracking
        self.current_state = FallState.STANDING
        self.fall_start_time: Optional[float] = None
        self.stillness_start_time: Optional[float] = None
        self.last_update_time = time.time()
    
    def update(self, detection: PersonDetection, timestamp: float):
        """Update tracker with new detection."""
        self.bbox_history.append(detection.bbox)
        self.aspect_ratio_history.append(detection.aspect_ratio)
        self.hip_y_history.append(detection.hip_center[1])
        self.keypoint_history.append(detection.keypoints.copy())
        self.timestamps.append(timestamp)
        self.last_update_time = timestamp
    
    def get_hip_velocity(self, num_frames: int = 8) -> float:
        """Calculate average downward hip velocity over last N frames."""
        if len(self.hip_y_history) < 2:
            return 0.0
        
        n = min(num_frames, len(self.hip_y_history) - 1)
        if n < 1:
            return 0.0
        
        hip_positions = list(self.hip_y_history)[-n-1:]
        timestamps = list(self.timestamps)[-n-1:]
        
        # Calculate velocity (positive = downward in image coordinates)
        velocities = []
        for i in range(1, len(hip_positions)):
            dt = timestamps[i] - timestamps[i-1]
            if dt > 0:
                velocity = (hip_positions[i] - hip_positions[i-1]) / dt
                velocities.append(velocity)
        
        return np.mean(velocities) if velocities else 0.0
    
    def get_aspect_ratio_change(self) -> Tuple[bool, float]:
        """
        Check if aspect ratio flipped from tall to wide.
        Returns (flipped, magnitude of change).
        """
        if len(self.aspect_ratio_history) < 10:
            return False, 0.0
        
        ratios = list(self.aspect_ratio_history)
        
        # Check last 10 frames for flip
        recent = ratios[-5:]
        older = ratios[-10:-5]
        
        avg_recent = np.mean(recent)
        avg_older = np.mean(older)
        
        # Flip from tall (AR < 1) to wide (AR > 1)
        flipped = avg_older < 0.9 and avg_recent > 1.1
        magnitude = avg_recent - avg_older
        
        return flipped, magnitude
    
    def get_keypoint_sequence(self) -> np.ndarray:
        """Get flattened keypoint sequence for LSTM input."""
        if len(self.keypoint_history) < self.window_size:
            # Pad with zeros
            seq = np.zeros((self.window_size, 17, 3))
            for i, kpts in enumerate(self.keypoint_history):
                seq[i] = kpts
            return seq
        
        return np.array(list(self.keypoint_history))
    
    def is_still(self, threshold: float = 5.0, duration: float = 1.5) -> bool:
        """Check if person has been still for specified duration."""
        if len(self.hip_y_history) < 10:
            return False
        
        recent_hips = list(self.hip_y_history)[-10:]
        variance = np.var(recent_hips)
        
        if variance < threshold:
            if self.stillness_start_time is None:
                self.stillness_start_time = time.time()
            elif time.time() - self.stillness_start_time > duration:
                return True
        else:
            self.stillness_start_time = None
        
        return False


class RuleBasedFallDetector:
    """
    Rule-based fall detection using bounding box aspect ratio
    and hip keypoint velocity analysis.
    
    Detection Rules (AND-ed):
    1. Aspect ratio flip: bbox width > height AND previously height > width
    2. Hip Y velocity: average downward velocity > threshold over 8 frames
    3. Post-fall stillness: person stays in fallen aspect ratio for > 1.5 seconds
    """
    
    def __init__(
        self,
        hip_velocity_threshold: float = 150.0,  # pixels/second
        stillness_duration: float = 1.5,  # seconds
        window_size: int = 20
    ):
        self.hip_velocity_threshold = hip_velocity_threshold
        self.stillness_duration = stillness_duration
        self.window_size = window_size
        
        # Person trackers
        self.trackers: Dict[int, PersonTracker] = {}
        
        # Active fall events
        self.active_falls: Dict[int, FallEvent] = {}
        self.confirmed_falls: List[FallEvent] = []
    
    def update(self, detections: List[PersonDetection], timestamp: float) -> List[FallEvent]:
        """
        Process new detections and return any fall events.
        
        Args:
            detections: List of person detections from pose estimator
            timestamp: Current timestamp in seconds
        
        Returns:
            List of fall events (both ongoing and newly confirmed)
        """
        events = []
        
        # Update trackers
        for detection in detections:
            person_id = detection.person_id
            
            if person_id not in self.trackers:
                self.trackers[person_id] = PersonTracker(person_id, self.window_size)
            
            self.trackers[person_id].update(detection, timestamp)
            
            # Check for fall conditions
            event = self._check_fall_conditions(person_id, detection, timestamp)
            if event:
                events.append(event)
        
        # Clean up old trackers (not seen for 5 seconds)
        stale_ids = [
            pid for pid, tracker in self.trackers.items()
            if timestamp - tracker.last_update_time > 5.0
        ]
        for pid in stale_ids:
            del self.trackers[pid]
            if pid in self.active_falls:
                del self.active_falls[pid]
        
        return events
    
    def _check_fall_conditions(
        self,
        person_id: int,
        detection: PersonDetection,
        timestamp: float
    ) -> Optional[FallEvent]:
        """Check if fall conditions are met for a person."""
        tracker = self.trackers[person_id]
        
        # Need enough history
        if len(tracker.bbox_history) < 10:
            return None
        
        # Condition 1: Aspect ratio flip
        ar_flipped, ar_magnitude = tracker.get_aspect_ratio_change()
        
        # Condition 2: Hip velocity
        hip_velocity = tracker.get_hip_velocity(num_frames=8)
        high_velocity = hip_velocity > self.hip_velocity_threshold
        
        # Condition 3: Stillness after fall
        is_still = tracker.is_still(duration=self.stillness_duration)
        
        # Calculate confidence based on conditions met
        confidence = 0.0
        if ar_flipped:
            confidence += 0.35
        if high_velocity:
            confidence += 0.35
        if is_still:
            confidence += 0.30
        
        # Determine fall state
        if ar_flipped and high_velocity:
            if person_id not in self.active_falls:
                # New fall detected
                tracker.current_state = FallState.FALLING
                event = FallEvent(
                    person_id=person_id,
                    timestamp=timestamp,
                    confidence=confidence,
                    state=FallState.FALLING,
                    bbox=detection.bbox,
                    hip_position=detection.hip_center,
                    confirmed=False
                )
                self.active_falls[person_id] = event
                tracker.fall_start_time = timestamp
                return event
        
        # Check for fall confirmation
        if person_id in self.active_falls:
            event = self.active_falls[person_id]
            event.duration_seconds = timestamp - tracker.fall_start_time
            
            if is_still and ar_flipped:
                # Confirmed fall
                event.state = FallState.FALLEN
                event.confirmed = True
                event.confidence = min(confidence + 0.2, 1.0)
                self.confirmed_falls.append(event)
                return event
            elif not ar_flipped:
                # Person recovered
                tracker.current_state = FallState.RECOVERING
                del self.active_falls[person_id]
                tracker.fall_start_time = None
        
        return None
    
    def get_active_falls(self) -> List[FallEvent]:
        """Get all currently active (unconfirmed) falls."""
        return list(self.active_falls.values())
    
    def get_confirmed_falls(self) -> List[FallEvent]:
        """Get all confirmed falls."""
        return self.confirmed_falls.copy()
    
    def reset(self):
        """Reset all tracking state."""
        self.trackers.clear()
        self.active_falls.clear()
        self.confirmed_falls.clear()


class LSTMFallClassifier(nn.Module):
    """
    LSTM-based fall classifier for ambiguous poses.
    Takes sequence of keypoints and classifies fall vs non-fall.
    
    Architecture:
    - Input: (batch, seq_len=20, features=34) - 17 keypoints * 2 (x, y normalized)
    - 2-layer LSTM with hidden_size=64
    - Dropout 0.3
    - FC output layer -> 2 classes (fall, no_fall)
    """
    
    def __init__(
        self,
        input_size: int = 34,  # 17 keypoints * 2 coordinates
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
        num_classes: int = 2
    ):
        super().__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=False
        )
        
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, num_classes)
        self.softmax = nn.Softmax(dim=1)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch, seq_len, input_size)
        
        Returns:
            Class probabilities of shape (batch, num_classes)
        """
        # LSTM forward
        lstm_out, (hidden, cell) = self.lstm(x)
        
        # Use last hidden state
        last_hidden = hidden[-1]  # (batch, hidden_size)
        
        # Classification
        out = self.dropout(last_hidden)
        out = self.fc(out)
        
        return self.softmax(out)
    
    def predict(self, keypoint_sequence: np.ndarray) -> Tuple[int, float]:
        """
        Predict fall class from keypoint sequence.
        
        Args:
            keypoint_sequence: Shape (seq_len, 17, 3) - keypoints with confidence
        
        Returns:
            (class_id, confidence) - 1 for fall, 0 for no fall
        """
        self.eval()
        
        # Normalize and flatten keypoints
        seq = keypoint_sequence[:, :, :2]  # Drop confidence
        seq_flat = seq.reshape(seq.shape[0], -1)  # (seq_len, 34)
        
        # Normalize to [0, 1] assuming 1920x1080 frame
        seq_flat[:, ::2] /= 1920  # x coordinates
        seq_flat[:, 1::2] /= 1080  # y coordinates
        
        # Convert to tensor
        x = torch.FloatTensor(seq_flat).unsqueeze(0)  # (1, seq_len, 34)
        
        with torch.no_grad():
            probs = self.forward(x)
            class_id = torch.argmax(probs, dim=1).item()
            confidence = probs[0, class_id].item()
        
        return class_id, confidence


class MLFallDetector:
    """
    ML-based fall detector combining rule-based and LSTM classifiers.
    Uses rule-based for initial detection, LSTM for confirmation.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        use_lstm: bool = True,
        device: str = "cuda"
    ):
        self.rule_detector = RuleBasedFallDetector()
        self.use_lstm = use_lstm and TORCH_AVAILABLE
        self.device = device
        
        if self.use_lstm:
            self.lstm_classifier = LSTMFallClassifier()
            if model_path:
                self._load_model(model_path)
            self.lstm_classifier.to(device)
            self.lstm_classifier.eval()
    
    def _load_model(self, model_path: str):
        """Load pretrained LSTM weights."""
        try:
            state_dict = torch.load(model_path, map_location=self.device)
            self.lstm_classifier.load_state_dict(state_dict)
            print(f"Loaded LSTM model from {model_path}")
        except Exception as e:
            print(f"Failed to load model: {e}")
    
    def detect(
        self,
        detections: List[PersonDetection],
        timestamp: float
    ) -> List[FallEvent]:
        """
        Detect falls using combined approach.
        
        Args:
            detections: Person detections from pose estimator
            timestamp: Current timestamp
        
        Returns:
            List of fall events with confidence scores
        """
        # Get rule-based events
        events = self.rule_detector.update(detections, timestamp)
        
        # Enhance with LSTM if available
        if self.use_lstm and events:
            for event in events:
                if event.person_id in self.rule_detector.trackers:
                    tracker = self.rule_detector.trackers[event.person_id]
                    seq = tracker.get_keypoint_sequence()
                    
                    if seq.shape[0] >= 15:  # Need enough frames
                        class_id, lstm_conf = self.lstm_classifier.predict(seq)
                        
                        # Combine confidences
                        if class_id == 1:  # Fall predicted
                            event.confidence = 0.6 * event.confidence + 0.4 * lstm_conf
                        else:
                            event.confidence *= 0.5  # Reduce confidence if LSTM disagrees
        
        return events
    
    def get_stats(self) -> Dict:
        """Get detection statistics."""
        return {
            "active_falls": len(self.rule_detector.active_falls),
            "confirmed_falls": len(self.rule_detector.confirmed_falls),
            "tracked_persons": len(self.rule_detector.trackers),
            "using_lstm": self.use_lstm
        }
