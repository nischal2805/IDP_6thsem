"""
Crowd Density Estimation Module using MobileCount/LWCC.
Provides density maps and crowd count estimation for drone-based monitoring.
"""
import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
import time

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import lwcc
    LWCC_AVAILABLE = True
except ImportError:
    LWCC_AVAILABLE = False
    print("Warning: LWCC not installed. pip install lwcc for pretrained models.")


@dataclass
class DensityResult:
    """Result from density estimation."""
    count: float
    density_map: np.ndarray
    peak_density: float
    peak_location: Tuple[int, int]
    avg_density: float
    high_density_regions: List[Tuple[int, int, float]]  # [(x, y, density), ...]
    inference_time_ms: float


class MobileCountBackbone(nn.Module):
    """
    MobileNet-based encoder for crowd counting.
    Lightweight alternative to VGG-16 used in CSRNet.
    """
    
    def __init__(self, pretrained: bool = True):
        super().__init__()
        
        # MobileNetV2-style inverted residual blocks
        self.features = nn.Sequential(
            # Initial conv
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU6(inplace=True),
            
            # Inverted residual blocks
            self._make_inverted_residual(32, 16, 1, 1),
            self._make_inverted_residual(16, 24, 2, 6),
            self._make_inverted_residual(24, 24, 1, 6),
            self._make_inverted_residual(24, 32, 2, 6),
            self._make_inverted_residual(32, 32, 1, 6),
            self._make_inverted_residual(32, 32, 1, 6),
            self._make_inverted_residual(32, 64, 2, 6),
            self._make_inverted_residual(64, 64, 1, 6),
            self._make_inverted_residual(64, 64, 1, 6),
            self._make_inverted_residual(64, 64, 1, 6),
            self._make_inverted_residual(64, 96, 1, 6),
            self._make_inverted_residual(96, 96, 1, 6),
            self._make_inverted_residual(96, 96, 1, 6),
        )
        
        self.out_channels = 96
    
    def _make_inverted_residual(
        self, 
        in_channels: int, 
        out_channels: int, 
        stride: int, 
        expand_ratio: int
    ) -> nn.Sequential:
        """Create an inverted residual block."""
        hidden_dim = in_channels * expand_ratio
        
        layers = []
        if expand_ratio != 1:
            layers.extend([
                nn.Conv2d(in_channels, hidden_dim, 1, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
            ])
        
        layers.extend([
            nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU6(inplace=True),
            nn.Conv2d(hidden_dim, out_channels, 1, bias=False),
            nn.BatchNorm2d(out_channels),
        ])
        
        return nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.features(x)


class MobileCountDecoder(nn.Module):
    """
    Decoder for density map generation.
    Upsamples feature maps to produce density estimation.
    """
    
    def __init__(self, in_channels: int = 96):
        super().__init__()
        
        self.decoder = nn.Sequential(
            # Upsample stages with dilated convolutions
            nn.Conv2d(in_channels, 128, kernel_size=3, padding=2, dilation=2),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 64, kernel_size=3, padding=2, dilation=2),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 32, kernel_size=3, padding=2, dilation=2),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 1, kernel_size=1),  # Density map output
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(x)


class MobileCount(nn.Module):
    """
    MobileCount: Efficient Encoder-Decoder for Real-Time Crowd Counting.
    
    Paper: MobileCount: An Efficient Encoder-Decoder Framework 
           for Real-Time Crowd Counting (Neurocomputing, 2020)
    
    Architecture:
    - MobileNetV2-based encoder (lightweight)
    - Dilated convolution decoder
    - Outputs density map (sum = crowd count)
    """
    
    def __init__(self, pretrained: bool = True):
        super().__init__()
        
        self.encoder = MobileCountBackbone(pretrained)
        self.decoder = MobileCountDecoder(self.encoder.out_channels)
        
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize decoder weights."""
        for m in self.decoder.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input image tensor (B, 3, H, W)
        
        Returns:
            Density map tensor (B, 1, H', W')
        """
        features = self.encoder(x)
        density = self.decoder(features)
        
        # Upsample to match input size
        density = F.interpolate(
            density, 
            size=x.shape[2:], 
            mode='bilinear', 
            align_corners=False
        )
        
        return density
    
    def count(self, x: torch.Tensor) -> torch.Tensor:
        """Get crowd count from input image."""
        density = self.forward(x)
        return density.sum(dim=(1, 2, 3))


class CrowdDensityEstimator:
    """
    High-level crowd density estimation interface.
    Supports multiple backends: MobileCount, LWCC, or mock.
    """
    
    def __init__(
        self,
        backend: str = "auto",  # "mobilecount", "lwcc", "auto", "mock"
        model_path: Optional[str] = None,
        device: str = "cpu",
        input_size: Tuple[int, int] = (640, 480)
    ):
        """
        Initialize density estimator.
        
        Args:
            backend: Which model backend to use
            model_path: Path to pretrained weights (for MobileCount)
            device: 'cuda' or 'cpu'
            input_size: (width, height) for input resize
        """
        self.device = device
        self.input_size = input_size
        self.backend = self._select_backend(backend)
        
        # Initialize model based on backend
        if self.backend == "lwcc":
            self.model = None  # LWCC handles model internally
            self.lwcc_model = "DM-Count"  # Options: CSRNet, SFANet, DM-Count
        elif self.backend == "mobilecount":
            try:
                self.model = MobileCount()
                if model_path:
                    self._load_weights(model_path)
                self.model.to(device)
                self.model.eval()
            except Exception as e:
                print(f"MobileCount initialization failed: {e}, using mock backend")
                self.backend = "mock"
                self.model = None
        else:
            self.model = None
        
        # Performance tracking
        self.last_inference_time = 0
        self.frame_count = 0
    
    def _select_backend(self, backend: str) -> str:
        """Select best available backend."""
        if backend == "auto":
            if LWCC_AVAILABLE:
                return "lwcc"
            elif TORCH_AVAILABLE:
                return "mobilecount"
            else:
                return "mock"
        return backend
    
    def _load_weights(self, model_path: str):
        """Load pretrained MobileCount weights."""
        try:
            state_dict = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            print(f"Loaded MobileCount weights from {model_path}")
        except Exception as e:
            print(f"Failed to load weights: {e}")
    
    def estimate(self, frame: np.ndarray) -> DensityResult:
        """
        Estimate crowd density from frame.
        
        Args:
            frame: BGR image as numpy array (H, W, 3)
        
        Returns:
            DensityResult with count, density map, and statistics
        """
        start_time = time.time()
        
        if self.backend == "lwcc":
            result = self._estimate_lwcc(frame)
        elif self.backend == "mobilecount":
            result = self._estimate_mobilecount(frame)
        else:
            result = self._estimate_mock(frame)
        
        result.inference_time_ms = (time.time() - start_time) * 1000
        self.last_inference_time = result.inference_time_ms
        self.frame_count += 1
        
        return result
    
    def _estimate_lwcc(self, frame: np.ndarray) -> DensityResult:
        """Estimate using LWCC library."""
        # LWCC expects RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Get count and density map
        count = lwcc.LWCC.get_count(rgb_frame, model=self.lwcc_model)
        density_map = lwcc.LWCC.get_density(rgb_frame, model=self.lwcc_model)
        
        return self._build_result(count, density_map)
    
    def _estimate_mobilecount(self, frame: np.ndarray) -> DensityResult:
        """Estimate using MobileCount model."""
        # Preprocess
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, self.input_size)
        
        # Normalize to [0, 1]
        tensor = torch.FloatTensor(resized).permute(2, 0, 1).unsqueeze(0) / 255.0
        tensor = tensor.to(self.device)
        
        # Inference
        with torch.no_grad():
            density_map = self.model(tensor)
            count = density_map.sum().item()
            density_np = density_map.squeeze().cpu().numpy()
        
        # Resize density map to original frame size
        density_np = cv2.resize(density_np, (frame.shape[1], frame.shape[0]))
        
        return self._build_result(count, density_np)
    
    def _estimate_mock(self, frame: np.ndarray) -> DensityResult:
        """Generate mock density estimation."""
        h, w = frame.shape[:2]
        
        # Generate random gaussian blobs
        density_map = np.zeros((h, w), dtype=np.float32)
        num_clusters = np.random.randint(3, 8)
        
        for _ in range(num_clusters):
            cx, cy = np.random.randint(0, w), np.random.randint(0, h)
            sigma = np.random.randint(20, 50)
            intensity = np.random.uniform(0.5, 2.0)
            
            y, x = np.ogrid[:h, :w]
            gaussian = np.exp(-((x - cx)**2 + (y - cy)**2) / (2 * sigma**2))
            density_map += gaussian * intensity
        
        count = density_map.sum() * 0.1  # Scale to reasonable count
        
        return self._build_result(count, density_map)
    
    def _build_result(self, count: float, density_map: np.ndarray) -> DensityResult:
        """Build DensityResult from count and density map."""
        # Find peak
        peak_idx = np.unravel_index(np.argmax(density_map), density_map.shape)
        peak_location = (peak_idx[1], peak_idx[0])  # (x, y)
        peak_density = density_map[peak_idx]
        
        # Average density
        avg_density = density_map.mean()
        
        # Find high-density regions (above 75th percentile)
        threshold = np.percentile(density_map, 75)
        high_density_regions = []
        
        # Divide into grid and find hot spots
        grid_h, grid_w = 10, 10
        cell_h, cell_w = density_map.shape[0] // grid_h, density_map.shape[1] // grid_w
        
        for i in range(grid_h):
            for j in range(grid_w):
                cell = density_map[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
                cell_density = cell.mean()
                if cell_density > threshold:
                    cx = j * cell_w + cell_w // 2
                    cy = i * cell_h + cell_h // 2
                    high_density_regions.append((cx, cy, float(cell_density)))
        
        return DensityResult(
            count=float(count),
            density_map=density_map,
            peak_density=float(peak_density),
            peak_location=peak_location,
            avg_density=float(avg_density),
            high_density_regions=high_density_regions,
            inference_time_ms=0  # Will be set by caller
        )
    
    def get_heatmap_overlay(
        self, 
        frame: np.ndarray, 
        density_map: np.ndarray,
        alpha: float = 0.5
    ) -> np.ndarray:
        """
        Create visualization overlay of density map on frame.
        
        Args:
            frame: Original BGR frame
            density_map: Density estimation result
            alpha: Overlay transparency
        
        Returns:
            BGR frame with heatmap overlay
        """
        if not CV2_AVAILABLE:
            return frame
        
        # Normalize density map to [0, 255]
        normalized = density_map.copy()
        if normalized.max() > 0:
            normalized = (normalized / normalized.max() * 255).astype(np.uint8)
        else:
            normalized = normalized.astype(np.uint8)
        
        # Apply colormap (green to red)
        heatmap = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
        
        # Resize to match frame if needed
        if heatmap.shape[:2] != frame.shape[:2]:
            heatmap = cv2.resize(heatmap, (frame.shape[1], frame.shape[0]))
        
        # Blend
        overlay = cv2.addWeighted(frame, 1 - alpha, heatmap, alpha, 0)
        
        return overlay
    
    def get_stats(self) -> Dict:
        """Get estimation statistics."""
        return {
            "backend": self.backend,
            "last_inference_ms": self.last_inference_time,
            "frame_count": self.frame_count,
            "input_size": self.input_size
        }
