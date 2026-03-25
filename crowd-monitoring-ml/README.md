# Crowd Monitoring ML Pipeline

**IDP - Drone-Based Crowd Monitoring System**

A comprehensive ML pipeline for real-time crowd monitoring using drone-mounted cameras. The system detects crowd density, predicts dangerous density buildup, detects individual distress events (falls), and triggers GPS-tagged alerts.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         JETSON ORIN NANO                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  YOLOv8n-    │  │    Fall      │  │  MobileCount │  │  Farneback  │  │
│  │    pose      │  │  Classifier  │  │   Density    │  │   Optical   │  │
│  │  (TensorRT)  │  │ (Rule+LSTM)  │  │  Estimator   │  │    Flow     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘  │
│         │                 │                 │                 │         │
│         └─────────────────┴─────────────────┴─────────────────┘         │
│                                    │                                    │
│                          ┌─────────▼─────────┐                          │
│                          │  GPS + MAVLink    │                          │
│                          │    (Pixhawk)      │                          │
│                          └─────────┬─────────┘                          │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │ WiFi/Socket
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          GROUND SERVER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │    LSTM      │  │   FastAPI    │  │   Telegram   │                   │
│  │  Forecaster  │  │   WebSocket  │  │     Bot      │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        REACT DASHBOARD                                  │
│  • Live Density Heatmap    • LSTM Forecast Panel                        │
│  • Alert Feed              • GPS Map Integration                        │
│  • Performance Metrics     • Historical Charts                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## ML Models

### 1. YOLOv8n-pose (Pose Estimation)
- **Purpose**: Detect persons and extract 17 COCO keypoints
- **Model**: `yolov8n-pose.pt` (nano variant)
- **Optimization**: TensorRT FP16 for Jetson
- **Output**: Person bounding boxes + keypoints (nose, eyes, shoulders, hips, etc.)
- **Expected FPS**: 20-25 on Jetson Orin Nano

```python
from jetson.pose_estimator import PoseEstimator

estimator = PoseEstimator(model_path="yolov8n-pose.pt", use_tensorrt=True)
detections = estimator.infer(frame)
```

### 2. Fall Detection Classifier
Two-stage pipeline: pose estimation → temporal classification

**Option A: Rule-Based (Recommended for start)**
- Bounding box aspect ratio flip detection
- Hip keypoint Y-velocity analysis (>15 px/frame)
- Post-fall stillness confirmation (>1.5s)
- ~90% accuracy on Le2i dataset

**Option B: LSTM-Based**
- 2-layer LSTM, hidden_size=64
- Input: 20 frames of 17×2 keypoint coordinates
- Output: fall/no-fall classification
- Better for ambiguous poses

```python
from jetson.fall_detector import MLFallDetector

detector = MLFallDetector(use_lstm=False)  # Start with rule-based
events = detector.detect(detections, timestamp)
```

### 3. MobileCount (Density Estimation)
- **Paper**: "MobileCount: An Efficient Encoder-Decoder Framework for Real-Time Crowd Counting"
- **Backbone**: MobileNet (lighter than VGG-16 used in CSRNet)
- **Output**: Density map (sum = crowd count)
- **Alternative**: LWCC library (`pip install lwcc`) for fastest integration

```python
from jetson.density_estimator import CrowdDensityEstimator

estimator = CrowdDensityEstimator(backend="auto")
result = estimator.estimate(frame)
print(f"Count: {result.count}, Peak density: {result.peak_density}")
```

### 4. Optical Flow Anomaly Detection
- **Method**: Farneback optical flow (OpenCV)
- **Detects**: 
  - Normal crowd (low magnitude, consistent direction)
  - Bottleneck (high inward convergence)
  - Panic/Stampede (high magnitude + divergence spike)
  - Counter-flow (opposing directions)

```python
from jetson.optical_flow import OpticalFlowAnalyzer

analyzer = OpticalFlowAnalyzer(panic_threshold=15.0)
result = analyzer.analyze(frame)
if result.anomaly_detected:
    print(f"Anomaly: {result.anomaly_type}, confidence: {result.confidence}")
```

### 5. LSTM Density Forecaster
- **Architecture**: 2-layer Bidirectional LSTM with attention
- **Input**: Rolling window of 30 timesteps
- **Output**: Predictions at 10s, 30s, 60s horizons
- **Runs on**: Ground server (not onboard)

```python
from ground_server.lstm_forecaster import CrowdDensityForecaster

forecaster = CrowdDensityForecaster(model_path="models/forecaster_model.pt")
forecaster.update(current_count)
result = forecaster.predict()
print(f"60s forecast: {result.prediction_60s}, trend: {result.trend}")
```

## Project Structure

```
crowd-monitoring-ml/
├── jetson/                      # Onboard inference (Jetson Orin Nano)
│   ├── pose_estimator.py        # YOLOv8n-pose wrapper
│   ├── fall_detector.py         # Rule-based + LSTM fall detection
│   ├── density_estimator.py     # MobileCount/LWCC density maps
│   ├── optical_flow.py          # Farneback anomaly detection
│   ├── gps_alert.py             # MAVLink GPS + alert packaging
│   ├── inference_pipeline.py    # Main orchestration script
│   └── requirements.txt
│
├── ground_server/               # Ground station server
│   ├── server.py                # FastAPI WebSocket server
│   ├── lstm_forecaster.py       # Density prediction model
│   ├── telegram_bot.py          # Alert dispatch
│   └── requirements.txt
│
├── dashboard/                   # React frontend
│   ├── src/
│   │   ├── App.jsx              # Main dashboard
│   │   └── components/
│   │       ├── DensityChart.jsx
│   │       ├── ForecastPanel.jsx
│   │       ├── AlertFeed.jsx
│   │       ├── HeatmapView.jsx
│   │       └── DroneStatus.jsx
│   └── package.json
│
├── models/                      # Training scripts
│   ├── train_fall_classifier.py
│   └── train_forecaster.py
│
├── configs/                     # Configuration files
│   ├── jetson_config.toml
│   └── server_config.toml
│
├── data/                        # Training data (not included)
│
└── README.md
```

## Quick Start

### 1. Jetson Setup

```bash
# Flash JetPack 5.x, install PyTorch from NVIDIA
cd jetson
pip install -r requirements.txt

# Export YOLOv8 to TensorRT (run once)
python -c "from pose_estimator import PoseEstimator; PoseEstimator.export_tensorrt('yolov8n-pose.pt')"

# Run inference pipeline
python inference_pipeline.py --camera 0 --server 192.168.1.100 --port 9000
```

### 2. Ground Server Setup

```bash
cd ground_server
pip install -r requirements.txt

# Set Telegram credentials (optional)
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_IDS="123456789,987654321"

# Run server
python server.py
```

### 3. Dashboard Setup

```bash
cd dashboard
npm install
npm run dev
```

Open http://localhost:3000

## Training Models

### Train Fall Classifier

```bash
cd models
python train_fall_classifier.py \
    --epochs 50 \
    --samples 2000 \
    --output models/fall_classifier.pt
```

For real training, use Le2i FDD or URFD datasets.

### Train Density Forecaster

```bash
cd models
python train_forecaster.py \
    --epochs 100 \
    --duration 7200 \
    --output models/forecaster_model.pt
```

## Datasets

| Dataset | Size | Purpose |
|---------|------|---------|
| Le2i FDD | 191 videos, 75,911 frames | Fall detection training |
| URFD | 30 falls, 40 ADL activities | Fall detection |
| ShanghaiTech A | 482 images, 241,677 heads | Density estimation |
| ShanghaiTech B | 716 images, 88,514 heads | Density estimation |

## API Reference

### WebSocket Payload (Jetson → Server)

```json
{
  "timestamp": 1679584200.123,
  "frame_id": 1500,
  "fps": 15.2,
  "persons": [
    {"id": 0, "bbox": [100, 200, 150, 400], "confidence": 0.92, "keypoints": [...]}
  ],
  "person_count": 5,
  "falls": [
    {"person_id": 2, "state": "fallen", "confidence": 0.95, "confirmed": true}
  ],
  "density": {
    "count": 47.3,
    "peak_density": 3.2,
    "high_density_regions": [[320, 240, 4.5]]
  },
  "anomaly": {
    "detected": false,
    "type": "normal",
    "magnitude": 2.3,
    "divergence": 0.1
  },
  "gps": {
    "lat": 12.9236,
    "lng": 77.4987,
    "alt": 50.0,
    "satellites": 12
  },
  "alerts": [],
  "timing_ms": {
    "pose": 25.3,
    "fall": 2.1,
    "density": 18.7,
    "flow": 8.4,
    "total": 54.5
  }
}
```

### Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` | View bot and alert statistics |
| `/ack <alert_id>` | Acknowledge an alert |
| `/history` | View recent alerts |
| `/help` | Show help message |

## Performance Targets

| Component | Target | Hardware |
|-----------|--------|----------|
| YOLOv8n-pose | 20-25 FPS | Jetson Orin Nano (TensorRT FP16) |
| Fall Detection | <5ms | Jetson Orin Nano |
| Density Estimation | 15-20 FPS | Jetson Orin Nano |
| Optical Flow | 25-30 FPS | Jetson Orin Nano (OpenCV) |
| LSTM Forecaster | <10ms | Ground Server (GPU optional) |
| End-to-end Pipeline | 15 FPS | Combined |

## Known Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Jetson thermal throttling | Add heatsink + fan, run at FP16 |
| Fall detection false positives | Use 3-condition AND logic + stillness timer |
| Drone altitude affects density | Calibrate at target altitude |
| WiFi range insufficient | Stream JSON only, no raw video |
| GPS lag on distress trigger | Cache GPS fix every 500ms |

## License

MIT License - See LICENSE file

## Authors

RVCE Drone Club - IDP Project
