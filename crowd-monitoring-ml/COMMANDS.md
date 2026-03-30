# Quick Command Reference

## 📋 ONE FILE WITH ALL COMMANDS

### 🔧 FOR YOU TO RUN ON JETSON (SSH: 10.58.30.340)

```bash
# ============================================
# STEP 1: INITIAL SETUP ON JETSON
# ============================================

# 1. Transfer setup script from PC
# (Run on PC first)
scp D:\IDP\crowd-monitoring-ml\jetson_setup.sh <user>@10.58.30.340:/home/<user>/

# 2. SSH into Jetson
ssh <user>@10.58.30.340

# 3. Run setup script
chmod +x jetson_setup.sh
./jetson_setup.sh

# This will install:
# - PyTorch for JetPack 6.0
# - Ultralytics YOLO
# - OpenCV
# - pymavlink
# - All dependencies


# ============================================
# STEP 2: TRANSFER CODE TO JETSON
# ============================================

# From PC, after applying fixes (see COMPLETE_GUIDE.md)
scp -r D:\IDP\crowd-monitoring-ml\jetson <user>@10.58.30.340:/home/<user>/crowd-monitoring/
scp -r D:\IDP\crowd-monitoring-ml\models <user>@10.58.30.340:/home/<user>/crowd-monitoring/
scp -r D:\IDP\crowd-monitoring-ml\configs <user>@10.58.30.340:/home/<user>/crowd-monitoring/


# ============================================
# STEP 3: DOWNLOAD MODELS ON JETSON
# ============================================

# SSH to Jetson
ssh <user>@10.58.30.340
cd /home/<user>/crowd-monitoring/models

# Download YOLOv8n-pose
python3 -c "from ultralytics import YOLO; model = YOLO('yolov8n-pose.pt'); print('Model downloaded')"


# ============================================
# STEP 4: TEST CAMERA ON JETSON
# ============================================

# Test camera (try index 0, 1, or 2)
python3 -c "import cv2; cap = cv2.VideoCapture(0); ret, frame = cap.read(); print('Camera 0:', 'OK' if ret else 'FAILED', frame.shape if ret else ''); cap.release()"

python3 -c "import cv2; cap = cv2.VideoCapture(1); ret, frame = cap.read(); print('Camera 1:', 'OK' if ret else 'FAILED', frame.shape if ret else ''); cap.release()"


# ============================================
# STEP 5: RUN JETSON PIPELINE
# ============================================

cd /home/<user>/crowd-monitoring/jetson
python3 inference_pipeline.py

# Expected output:
# Initializing JetsonInferencePipeline...
# ✓ Pose Estimator initialized
# ✓ Fall Detector initialized
# ✓ Optical Flow initialized
# ✓ Density Estimator initialized
# ✓ GPS Manager initialized
# Starting inference... Press Ctrl+C to stop


# ============================================
# TROUBLESHOOTING COMMANDS
# ============================================

# Check Python version
python3 --version  # Should be 3.10+

# Check PyTorch CUDA
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"

# Check JetPack version
cat /etc/nv_tegra_release

# Check disk space
df -h

# Check GPU usage (while pipeline is running)
tegrastats

# List video devices
ls /dev/video*

# Check camera permissions
sudo chmod 666 /dev/video0

```

---

### 🖥️ FOR YOU TO RUN ON SERVER PC

```bash
# ============================================
# GROUND SERVER SETUP
# ============================================

# Navigate to ground server
cd D:\IDP\crowd-monitoring-ml\ground_server

# Install dependencies (first time only)
pip install -r requirements.txt

# Set environment variables (Windows)
set TELEGRAM_BOT_TOKEN=your_bot_token_here
set TELEGRAM_CHAT_IDS=your_chat_id_here

# Run server
python server.py

# Expected output:
# Ground server listening on 0.0.0.0:9000 (Jetson)
# Dashboard WebSocket server on 0.0.0.0:8080


# ============================================
# DASHBOARD SETUP
# ============================================

# Navigate to dashboard
cd D:\IDP\crowd-monitoring-ml\dashboard

# Install dependencies (first time only)
npm install

# Run dashboard
npm run dev

# Expected output:
# VITE v... ready in ...ms
# Local: http://localhost:3000
# Network: use --host to expose

# Open browser to: http://localhost:3000


# ============================================
# SERVER-SIDE OPENCV TESTING (NO JETSON)
# ============================================

# If you want to test without Jetson (USB camera on PC)
cd D:\IDP\crowd-monitoring-ml\server_opencv

# Install dependencies
pip install -r requirements.txt

# Test individual modules
python camera_receiver.py       # Test camera
python opencv_crowd_detector.py # Test crowd detection
python density_heatmap.py       # Test heatmap
python optical_flow_analyzer.py # Test optical flow

# Run full pipeline
python server_pipeline.py

# Controls:
# q - Quit
# r - Reset background
# f - Reset optical flow
# 1,2,3,4 - Switch views
# s - Save snapshot

```

---

### 🔍 VERIFICATION COMMANDS

```bash
# ============================================
# VERIFY JETSON → SERVER CONNECTION
# ============================================

# On Jetson (should show JSON output)
cd /home/<user>/crowd-monitoring/jetson
python3 inference_pipeline.py

# On Server (should show "Jetson connected")
cd D:\IDP\crowd-monitoring-ml\ground_server
python server.py
# Watch for: "Jetson connected from <ip>"


# ============================================
# VERIFY SERVER → DASHBOARD CONNECTION
# ============================================

# On Server
python server.py

# On Dashboard
npm run dev

# Open browser console (F12)
# Should see: "Connected to ground server"


# ============================================
# CHECK SYSTEM HEALTH
# ============================================

# Jetson FPS (while pipeline running)
# Look at terminal output, should show ~15 FPS

# Server logs
# Check for errors in server.py output

# Dashboard connection
# Check browser console (F12) for errors

# Network connectivity
ping 10.58.30.340  # From PC to Jetson

```

---

### ⚠️ COMMON FIXES

```bash
# ============================================
# FIX: Camera not found on Jetson
# ============================================

# List all video devices
ls -la /dev/video*

# Give permissions
sudo chmod 666 /dev/video0

# Try different camera index
# Edit configs/jetson_config.toml
# Change: source = 1  (instead of 0)


# ============================================
# FIX: Port already in use on Server
# ============================================

# Check what's using port 9000
netstat -ano | findstr :9000

# Kill the process
taskkill /PID <pid> /F

# Or change port in configs/server_config.toml


# ============================================
# FIX: PyTorch CUDA not available on Jetson
# ============================================

# Check CUDA
nvidia-smi  # or: tegrastats

# Reinstall PyTorch for Jetson
pip3 uninstall torch torchvision
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu124


# ============================================
# FIX: Module not found errors
# ============================================

# On Jetson
cd /home/<user>/crowd-monitoring/jetson
pip3 install -r requirements.txt

# On Server
cd D:\IDP\crowd-monitoring-ml\ground_server
pip install -r requirements.txt

```

---

### 🎯 TESTING SEQUENCE

```bash
# ============================================
# COMPLETE END-TO-END TEST
# ============================================

# Terminal 1: Start Server
cd D:\IDP\crowd-monitoring-ml\ground_server
python server.py

# Terminal 2: Start Dashboard
cd D:\IDP\crowd-monitoring-ml\dashboard
npm run dev

# Terminal 3: SSH to Jetson and run pipeline
ssh <user>@10.58.30.340
cd /home/<user>/crowd-monitoring/jetson
python3 inference_pipeline.py

# Browser: Open http://localhost:3000

# Expected flow:
# 1. Jetson shows: "Starting inference... FPS: 15.2"
# 2. Server shows: "Jetson connected from <ip>"
# 3. Dashboard shows: Live heatmap, person count, charts updating

```

---

### 📞 QUICK REFERENCE

**Jetson IP:** 10.58.30.340  
**Server Ports:** 9000 (Jetson), 8080 (Dashboard)  
**Dashboard URL:** http://localhost:3000

**Main Files:**
- Jetson: `/home/<user>/crowd-monitoring/jetson/inference_pipeline.py`
- Server: `D:\IDP\crowd-monitoring-ml\ground_server\server.py`
- Dashboard: `D:\IDP\crowd-monitoring-ml\dashboard\` (npm run dev)

**Logs Location:**
- Jetson: Terminal output
- Server: Terminal output
- Dashboard: Browser console (F12)

**Config Files:**
- Jetson: `configs/jetson_config.toml`
- Server: `configs/server_config.toml`
- Dashboard: `.env` (create from .env.example)

---

**Need more details?** → See `COMPLETE_GUIDE.md`  
**Need help?** → See `COMPLETE_GUIDE.md` → Troubleshooting section
