# Server-Side OpenCV Crowd Monitoring

**OpenCV-only implementation** for testing phase - no YOLO dependency.

## Architecture

```
Drone (Camera Only) → Stream → Server → Process Everything → Display
```

All ML processing happens on the server, not on the drone.

## Features

✅ **Camera Input**
- USB camera (`cv2.VideoCapture(0)`)
- RTSP streams from drone
- Video file playback
- Auto-reconnection on stream loss

✅ **Crowd Detection** (OpenCV-only)
- Background subtraction (MOG2/KNN)
- Contour-based person detection
- Blob filtering by size and aspect ratio
- Real-time person count

✅ **Density Heatmap**
- Gaussian-based density visualization
- Grid-based density analysis
- High-density region detection
- Colormap overlay (COLORMAP_JET)

✅ **Optical Flow Analysis**
- Farneback optical flow
- Anomaly detection:
  - Normal flow
  - Bottleneck (convergence)
  - Panic/Stampede (high magnitude)
  - Congestion
  - Counter-flow
- Grid-based region analysis
- Flow visualization with arrows

✅ **Real-Time Visualization**
- 4-panel view (detection, heatmap, grid, flow)
- Configurable display modes
- FPS and statistics overlay
- Anomaly alerts

## Quick Start

### 1. Install Dependencies

```bash
cd server_opencv
pip install -r requirements.txt
```

### 2. Test Individual Modules

**Camera Receiver:**
```bash
python camera_receiver.py
```

**Crowd Detector:**
```bash
python opencv_crowd_detector.py
```

**Density Heatmap:**
```bash
python density_heatmap.py
```

**Optical Flow:**
```bash
python optical_flow_analyzer.py
```

### 3. Run Full Pipeline

**USB Camera (default):**
```bash
python server_pipeline.py
```

**RTSP Stream from Drone:**
Edit `server_pipeline.py`, change camera_source:
```python
config = PipelineConfig(
    camera_source='rtsp://192.168.1.100:8554/stream',  # Your drone IP
    ...
)
```

Then run:
```bash
python server_pipeline.py
```

## Controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Reset background model |
| `f` | Reset optical flow |
| `1` | Detection view only |
| `2` | Heatmap view only |
| `3` | Optical flow view only |
| `4` | All views (2x2 grid) |
| `s` | Save current frame |

## Configuration

Edit `PipelineConfig` in `server_pipeline.py`:

```python
config = PipelineConfig(
    # Camera settings
    camera_source=0,              # 0 = USB cam, or 'rtsp://...'
    camera_width=1280,
    camera_height=720,
    camera_fps=30,
    
    # Detection settings
    detection_method="mog2",      # mog2, knn, blob
    min_person_area=800,          # Min pixels for person
    max_person_area=20000,        # Max pixels for person
    
    # Heatmap settings
    heatmap_alpha=0.5,            # Overlay transparency
    gaussian_sigma=30.0,          # Blur amount
    
    # Optical flow settings
    enable_optical_flow=True,
    magnitude_threshold=5.0,      # Normal vs high movement
    panic_threshold=15.0,         # Panic detection
    
    # Display settings
    display_mode="all",           # all, detection, heatmap, flow
    save_output=False,            # Save video to file
    target_fps=15                 # Processing FPS
)
```

## Modules

### 1. `camera_receiver.py`
- Camera stream management
- USB/RTSP/HTTP/File support
- Auto-reconnection
- FPS tracking

### 2. `opencv_crowd_detector.py`
- OpenCV-only crowd detection
- Background subtraction (MOG2/KNN)
- Contour filtering
- Person count estimation
- BoundingBox extraction

### 3. `density_heatmap.py`
- Gaussian density maps
- Grid-based density calculation
- Heatmap overlay
- High-density region detection

### 4. `optical_flow_analyzer.py`
- Farneback optical flow
- Anomaly classification
- Grid-based flow analysis
- Flow visualization

### 5. `server_pipeline.py`
- Main orchestration script
- Integrates all modules
- Real-time processing loop
- Multi-panel display
- JSON output for dashboard integration

## Performance

| Component | FPS | Notes |
|-----------|-----|-------|
| Camera Input | 30 | USB camera |
| Crowd Detection | 20-25 | MOG2 background subtraction |
| Density Heatmap | 25-30 | Gaussian blur + colormap |
| Optical Flow | 15-20 | Farneback flow |
| **Full Pipeline** | **15** | All components together |

CPU-only on typical laptop/desktop.

## Output Format (JSON)

Results available for dashboard integration:

```json
{
  "timestamp": 1234567890.123,
  "frame_id": 42,
  "fps": 15.2,
  "processing_time_ms": 66.5,
  
  "person_count": 12,
  "density_score": 0.23,
  "total_crowd_area": 45600,
  "bboxes": [
    {"x": 100, "y": 200, "width": 50, "height": 120, "confidence": 1.0}
  ],
  
  "density": {
    "peak_density": 245.3,
    "avg_density": 45.2,
    "density_std": 23.1
  },
  
  "high_density_regions": [
    {"x": 320, "y": 160, "width": 32, "height": 32, "count": 5}
  ],
  
  "anomaly": {
    "detected": true,
    "type": "panic",
    "confidence": 0.87,
    "magnitude": 12.4,
    "divergence": 0.34
  }
}
```

## Migration to Jetson

When ready to deploy on drone with Jetson:

1. Copy these modules to Jetson
2. Add YOLO detector (already in `jetson/` folder)
3. Change architecture: Jetson processes → sends results to server
4. Dashboard will work with same JSON format

## Troubleshooting

**"No camera found"**
- Check camera is connected: `ls /dev/video*` (Linux) or Device Manager (Windows)
- Try different indices: 0, 1, 2

**"Background subtraction not working"**
- Ensure camera is stable (not moving)
- Adjust `learning_rate` (higher = faster adaptation)
- Try KNN instead of MOG2

**"Low FPS"**
- Reduce resolution: 640x480 instead of 1280x720
- Lower `target_fps` in config
- Disable optical flow: `enable_optical_flow=False`

**"Too many false detections"**
- Increase `min_person_area` (filter small blobs)
- Adjust aspect ratio thresholds in detector
- Let background model stabilize (30+ frames)

## Next Steps

1. ✅ Test with USB camera
2. ✅ Test with video file
3. 🔲 Test with drone RTSP stream
4. 🔲 Integrate with dashboard WebSocket
5. 🔲 Add YOLO when model is trained
6. 🔲 Deploy to Jetson on drone

## Files

```
server_opencv/
├── camera_receiver.py           # Camera input handling
├── opencv_crowd_detector.py     # OpenCV-only crowd detection
├── density_heatmap.py           # Heatmap generation
├── optical_flow_analyzer.py     # Optical flow anomalies
├── server_pipeline.py           # Main pipeline (run this!)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Contact

RVCE Drone Club - IDP Project
