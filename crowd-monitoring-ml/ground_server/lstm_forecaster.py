"""
LSTM Crowd Density Forecaster.
Predicts future crowd density based on historical time series data.

Architecture:
- Input: Rolling window of 30 timesteps of crowd count or density features
- 2-layer LSTM, hidden_size=64, dropout=0.2
- Multi-horizon output: predictions for 10s, 30s, 60s ahead
"""
import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import json
import os

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: PyTorch not available for LSTM forecaster")


@dataclass
class ForecastResult:
    """Result from density forecasting."""
    current_count: float
    prediction_10s: float
    prediction_30s: float
    prediction_60s: float
    confidence: float
    trend: str  # "increasing", "decreasing", "stable"
    warning: Optional[str]


class DensityTimeSeriesDataset(Dataset):
    """PyTorch dataset for density time series."""
    
    def __init__(
        self,
        data: np.ndarray,
        window_size: int = 30,
        horizons: List[int] = [10, 30, 60],
        sampling_rate: float = 1.0  # samples per second
    ):
        """
        Initialize dataset.
        
        Args:
            data: 1D array of density/count values
            window_size: Number of past timesteps to use
            horizons: Future timesteps to predict (in seconds)
            sampling_rate: Data sampling rate in Hz
        """
        self.data = data
        self.window_size = window_size
        self.horizons = [int(h * sampling_rate) for h in horizons]
        self.max_horizon = max(self.horizons)
        
        # Valid indices
        self.valid_length = len(data) - window_size - self.max_horizon
    
    def __len__(self):
        return max(0, self.valid_length)
    
    def __getitem__(self, idx):
        # Input sequence
        x = self.data[idx:idx + self.window_size]
        
        # Target values at each horizon
        y = np.array([
            self.data[idx + self.window_size + h - 1]
            for h in self.horizons
        ])
        
        return torch.FloatTensor(x).unsqueeze(-1), torch.FloatTensor(y)


class LSTMForecaster(nn.Module):
    """
    LSTM-based time series forecaster for crowd density prediction.
    
    Architecture:
    - Input: (batch, seq_len, 1) - univariate time series
    - 2-layer Bidirectional LSTM with hidden_size=64
    - Attention mechanism for sequence weighting
    - Multi-head output for different horizons
    """
    
    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        num_horizons: int = 3,
        bidirectional: bool = True
    ):
        super().__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        self.num_directions = 2 if bidirectional else 1
        
        # LSTM encoder
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=bidirectional
        )
        
        # Attention layer
        self.attention = nn.Sequential(
            nn.Linear(hidden_size * self.num_directions, hidden_size),
            nn.Tanh(),
            nn.Linear(hidden_size, 1),
            nn.Softmax(dim=1)
        )
        
        # Output heads for each horizon
        self.output_heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_size * self.num_directions, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size, 1)
            )
            for _ in range(num_horizons)
        ])
        
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights using Xavier initialization."""
        for name, param in self.named_parameters():
            if 'weight_ih' in name:
                nn.init.xavier_uniform_(param.data)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param.data)
            elif 'bias' in name:
                param.data.fill_(0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor (batch, seq_len, input_size)
        
        Returns:
            Predictions (batch, num_horizons)
        """
        # LSTM encoding
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden*directions)
        
        # Attention weighting
        attention_weights = self.attention(lstm_out)  # (batch, seq_len, 1)
        context = torch.sum(attention_weights * lstm_out, dim=1)  # (batch, hidden*directions)
        
        # Multi-horizon predictions
        predictions = []
        for head in self.output_heads:
            pred = head(context)
            predictions.append(pred)
        
        return torch.cat(predictions, dim=1)  # (batch, num_horizons)
    
    def predict_single(self, sequence: np.ndarray) -> np.ndarray:
        """
        Predict from a single sequence.
        
        Args:
            sequence: 1D array of past values
        
        Returns:
            Array of predictions for each horizon
        """
        self.eval()
        with torch.no_grad():
            x = torch.FloatTensor(sequence).unsqueeze(0).unsqueeze(-1)
            pred = self.forward(x)
            return pred.squeeze().numpy()


class CrowdDensityForecaster:
    """
    High-level forecaster interface for crowd density prediction.
    Handles data preprocessing, model inference, and result interpretation.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        window_size: int = 30,
        horizons: List[int] = [10, 30, 60],  # seconds
        capacity: int = 100,  # Maximum expected crowd count
        device: str = "cuda"
    ):
        """
        Initialize forecaster.
        
        Args:
            model_path: Path to pretrained model weights
            window_size: Number of past samples to use
            horizons: Future prediction horizons in seconds
            capacity: Maximum crowd capacity for normalization
            device: 'cuda' or 'cpu'
        """
        self.window_size = window_size
        self.horizons = horizons
        self.capacity = capacity
        self.device = device if TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
        
        # Data buffer
        self.history: List[float] = []
        self.max_history = window_size * 2
        
        # Normalization stats
        self.mean = 50.0
        self.std = 25.0
        
        # Model
        if TORCH_AVAILABLE:
            self.model = LSTMForecaster(
                input_size=1,
                hidden_size=64,
                num_layers=2,
                dropout=0.2,
                num_horizons=len(horizons)
            )
            self.model.to(self.device)
            
            if model_path and os.path.exists(model_path):
                self._load_model(model_path)
            
            self.model.eval()
        else:
            self.model = None
    
    def _load_model(self, model_path: str):
        """Load pretrained model weights."""
        try:
            state_dict = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            print(f"Loaded forecaster model from {model_path}")
        except Exception as e:
            print(f"Failed to load model: {e}")
    
    def update(self, count: float):
        """
        Add new observation to history.
        
        Args:
            count: Current crowd count
        """
        self.history.append(count)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        # Update running statistics
        if len(self.history) > 10:
            self.mean = np.mean(self.history)
            self.std = max(np.std(self.history), 1.0)
    
    def predict(self) -> Optional[ForecastResult]:
        """
        Generate forecast based on current history.
        
        Returns:
            ForecastResult or None if insufficient history
        """
        if len(self.history) < self.window_size:
            return None
        
        # Get input sequence
        sequence = np.array(self.history[-self.window_size:])
        current = sequence[-1]
        
        # Normalize
        normalized = (sequence - self.mean) / self.std
        
        # Predict
        if self.model is not None:
            predictions = self.model.predict_single(normalized)
            # Denormalize
            predictions = predictions * self.std + self.mean
        else:
            # Simple linear extrapolation fallback
            trend = np.polyfit(range(len(sequence)), sequence, 1)[0]
            predictions = np.array([
                current + trend * h for h in self.horizons
            ])
        
        # Clip to valid range
        predictions = np.clip(predictions, 0, self.capacity * 1.5)
        
        # Determine trend
        recent_trend = np.mean(np.diff(sequence[-10:]))
        if recent_trend > 1:
            trend = "increasing"
        elif recent_trend < -1:
            trend = "decreasing"
        else:
            trend = "stable"
        
        # Calculate confidence
        variance = np.var(sequence[-10:])
        confidence = max(0.3, 1.0 - variance / (self.std ** 2 + 1))
        
        # Generate warnings
        warning = None
        if predictions[2] > self.capacity * 0.9:
            warning = "CRITICAL: Capacity overflow predicted in 60s"
        elif predictions[1] > self.capacity * 0.85:
            warning = "WARNING: High density predicted in 30s"
        elif predictions[0] > self.capacity * 0.8:
            warning = "CAUTION: Approaching capacity in 10s"
        
        return ForecastResult(
            current_count=float(current),
            prediction_10s=float(predictions[0]),
            prediction_30s=float(predictions[1]),
            prediction_60s=float(predictions[2]),
            confidence=float(confidence),
            trend=trend,
            warning=warning
        )
    
    def get_history(self) -> List[float]:
        """Get current history buffer."""
        return self.history.copy()
    
    def reset(self):
        """Reset history buffer."""
        self.history.clear()
    
    def to_dict(self, result: ForecastResult) -> Dict:
        """Convert ForecastResult to dictionary."""
        return {
            "current": result.current_count,
            "predictions": {
                "10s": result.prediction_10s,
                "30s": result.prediction_30s,
                "60s": result.prediction_60s
            },
            "confidence": result.confidence,
            "trend": result.trend,
            "warning": result.warning
        }


class ForecasterTrainer:
    """
    Training utilities for the LSTM forecaster.
    """
    
    def __init__(
        self,
        model: LSTMForecaster,
        device: str = "cuda",
        learning_rate: float = 0.001
    ):
        self.model = model
        self.device = device
        self.model.to(device)
        
        self.optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5
        )
        self.criterion = nn.MSELoss()
    
    def train_epoch(self, dataloader: DataLoader) -> float:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        
        for x, y in dataloader:
            x, y = x.to(self.device), y.to(self.device)
            
            self.optimizer.zero_grad()
            pred = self.model(x)
            loss = self.criterion(pred, y)
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            total_loss += loss.item()
        
        return total_loss / len(dataloader)
    
    def validate(self, dataloader: DataLoader) -> float:
        """Validate model."""
        self.model.eval()
        total_loss = 0.0
        
        with torch.no_grad():
            for x, y in dataloader:
                x, y = x.to(self.device), y.to(self.device)
                pred = self.model(x)
                loss = self.criterion(pred, y)
                total_loss += loss.item()
        
        return total_loss / len(dataloader)
    
    def train(
        self,
        train_data: np.ndarray,
        val_data: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        window_size: int = 30,
        save_path: str = "forecaster_model.pt"
    ) -> Dict:
        """
        Full training loop.
        
        Args:
            train_data: Training time series
            val_data: Validation time series
            epochs: Number of training epochs
            batch_size: Batch size
            window_size: Input sequence length
            save_path: Path to save best model
        
        Returns:
            Training history
        """
        train_dataset = DensityTimeSeriesDataset(train_data, window_size)
        val_dataset = DensityTimeSeriesDataset(val_data, window_size)
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)
        
        history = {"train_loss": [], "val_loss": []}
        best_val_loss = float('inf')
        
        for epoch in range(epochs):
            train_loss = self.train_epoch(train_loader)
            val_loss = self.validate(val_loader)
            
            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)
            
            self.scheduler.step(val_loss)
            
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(self.model.state_dict(), save_path)
            
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs} - "
                      f"Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
        
        print(f"Training complete. Best validation loss: {best_val_loss:.4f}")
        return history


def generate_synthetic_data(
    duration_seconds: int = 3600,
    sampling_rate: float = 1.0,
    base_count: float = 50,
    noise_std: float = 5
) -> np.ndarray:
    """
    Generate synthetic crowd count data for training.
    Includes realistic patterns: trends, periodicity, events.
    """
    n_samples = int(duration_seconds * sampling_rate)
    t = np.linspace(0, duration_seconds, n_samples)
    
    # Base trend
    data = np.ones(n_samples) * base_count
    
    # Add slow sinusoidal variation (crowd patterns)
    data += 20 * np.sin(2 * np.pi * t / 600)  # 10-minute cycle
    
    # Add random events (sudden increases)
    n_events = np.random.randint(3, 8)
    for _ in range(n_events):
        event_start = np.random.randint(0, n_samples - 300)
        event_duration = np.random.randint(60, 300)
        event_magnitude = np.random.uniform(10, 30)
        
        # Gaussian-shaped event
        event_x = np.arange(event_duration)
        event_profile = event_magnitude * np.exp(-((event_x - event_duration/2)**2) / (2 * (event_duration/4)**2))
        data[event_start:event_start+event_duration] += event_profile
    
    # Add noise
    data += np.random.normal(0, noise_std, n_samples)
    
    # Ensure non-negative
    data = np.clip(data, 0, 150)
    
    return data
