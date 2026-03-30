# Quick Start Guide - CPU Mode (Jetson Nano Orin)

## ✅ All Issues Fixed

### Changes Made:
- ✅ All modules default to **CPU mode** (no CUDA required)
- ✅ TensorRT disabled by default (enable only after testing)
- ✅ Comprehensive error handling for all modules
- ✅ Better camera initialization with timeouts
- ✅ Server connection is now optional (local-only mode)
- ✅ GPS is optional (use `--no-gps` flag)
- ✅ Telegram bot import errors fixed

---

## 🚀 Run on Jetson (After git pull)

### Step 1: Pull Latest Changes
```bash
cd ~/crowd-monitoring/IDP_6thsem/crowd-monitoring-ml
git pull
```

### Step 2: Install Missing Package
```bash
source ~/crowd-monitoring/boss/bin/activate
uv pip install pyserial
```

### Step 3: Check Available Cameras
```bash
ls -l /dev/video*
v4l2-ctl --list-devices
```

### Step 4: Run Local Test (No Server)
```bash
cd jetson
python inference_pipeline.py --camera 0 --no-server --no-gps
```

**Expected Output:**
```
Initializing ML modules...
Model loaded: yolov8n-pose.pt
Starting Jetson Inference Pipeline...
Opening camera 0...
✅ Camera initialized: 1280x720
Running in local-only mode (no server connection)
📊 FPS: 12.3 | Frames: 30 | Connected: False
```

### Step 5: Run with Server (After server is running)

**Make sure to update `configs/jetson_config.toml` first:**
```toml
[server]
host = "YOUR_PC_IP"    # e.g., "192.168.1.100" or "10.58.30.xxx"
port = 9000
```

Then run:
```bash
cd jetson
python inference_pipeline.py --camera 0 --no-gps
```

---

## 🖥️ Run Ground Server (Windows)

### Terminal 1: Ground Server
```powershell
cd D:\IDP\crowd-monitoring-ml\ground_server
python server.py
```

**Expected Output:**
```
Using mock Telegram bot (no credentials)
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8080
INFO:     Listening for Jetson data on port 9000
```

---

## 🎛️ Command Line Options

### Jetson Pipeline Flags:
```bash
--camera N           # Camera device index (default: 0)
--server IP          # Ground server IP (default: localhost)
--port N             # Ground server port (default: 9000)
--fps N              # Target FPS (default: 15.0)
--no-display         # Run headless (no OpenCV window)
--no-tensorrt        # Disable TensorRT (recommended for testing)
--no-gps             # Skip GPS/MAVLink initialization
--no-server          # Run local-only mode (no server connection)
```

### Examples:
```bash
# Local test with camera 1, no server
python inference_pipeline.py --camera 1 --no-server --no-gps

# Full pipeline with custom FPS
python inference_pipeline.py --camera 0 --fps 10 --no-gps

# Headless mode (no display)
python inference_pipeline.py --camera 0 --no-display --no-gps
```

---

## 🔍 Troubleshooting

### Issue: Camera timeout errors
```bash
# Check which cameras are available
ls -l /dev/video*

# Try different camera indices
python inference_pipeline.py --camera 1 --no-server

# Check camera permissions
sudo usermod -a -G video $USER
sudo chmod 666 /dev/video0
```

### Issue: "Module not found" errors
```bash
# Activate virtual environment
source ~/crowd-monitoring/boss/bin/activate

# Install missing packages
uv pip install pyserial opencv-python ultralytics scipy pyyaml
```

### Issue: Server connection refused
```bash
# 1. Make sure server is running on Windows
# 2. Check firewall (allow port 9000)
# 3. Verify IP address in config matches your PC's IP
ipconfig  # On Windows to get IP

# 4. Test with local-only mode first
python inference_pipeline.py --camera 0 --no-server
```

### Issue: Low FPS (< 5 FPS)
```bash
# Lower target FPS
python inference_pipeline.py --camera 0 --fps 8

# Reduce camera resolution in code or config
# Edit configs/jetson_config.toml:
[camera]
width = 640
height = 480
```

---

## 📊 Performance Expectations (CPU Mode)

| Component | CPU FPS | Notes |
|-----------|---------|-------|
| YOLOv8n-pose | 8-12 | Main bottleneck |
| Fall Detection (rule-based) | 30+ | Very fast |
| Optical Flow | 20-25 | OpenCV optimized |
| Density Estimation | 15-20 | Lightweight |
| **Total Pipeline** | **8-12 FPS** | Acceptable for testing |

---

## 🚀 Enable GPU Later (After Testing)

Once everything works, enable GPU for 2-3x speedup:

1. **Install PyTorch with CUDA** (use NVIDIA Jetson wheel)
2. **Update configs/jetson_config.toml:**
```toml
[inference]
device = "cuda"
use_tensorrt = true
```

3. **Regenerate TensorRT engine:**
```bash
python -c "from ultralytics import YOLO; m = YOLO('yolov8n-pose.pt'); m.export(format='engine', half=True)"
```

---

## ✅ Success Indicators

### Jetson Console:
```
✅ Camera initialized: 1280x720
✅ Connected to ground server at 192.168.1.100:9000
📊 FPS: 10.5 | Frames: 30 | Connected: True
```

### Ground Server Console:
```
INFO:     Jetson connected from ('192.168.1.x', 54321)
Received frame 30 with 3 persons detected
```

---

## 🎯 Next Steps

1. ✅ Get Jetson pipeline running locally (`--no-server`)
2. ✅ Start ground server on Windows
3. ✅ Update Jetson config with correct server IP
4. ✅ Run full pipeline (Jetson → Server)
5. 🔲 Set up React dashboard (optional)
6. 🔲 Enable GPU mode for better performance
7. 🔲 Add Telegram bot credentials (optional)

---

## 📞 Support

If issues persist:
1. Check all dependencies are installed
2. Verify camera works: `python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"`
3. Run with `--no-server --no-gps` first to isolate camera issues
4. Check console output for specific error messages

**All code now includes detailed error messages with ✅ ❌ ⚠️ emojis for easy debugging!**
