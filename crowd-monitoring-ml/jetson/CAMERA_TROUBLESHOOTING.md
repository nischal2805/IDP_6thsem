# Jetson Camera Troubleshooting Guide

Complete guide for diagnosing and fixing camera issues on NVIDIA Jetson devices.

---

## 🚨 Quick Diagnostic Commands

Run these **immediately** when camera issues occur:

```bash
# 1. List all video devices
ls -la /dev/video*

# 2. Check device permissions
groups $USER | grep video

# 3. List camera details
v4l2-ctl --list-devices

# 4. Test camera with GStreamer (CSI)
gst-launch-1.0 nvarguscamerasrc ! nvoverlaysink

# 5. Test camera with GStreamer (USB)
gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! xvimagesink

# 6. Check which processes are using camera
sudo lsof /dev/video0

# 7. Run our diagnostic script
python3 diagnose_camera.py
```

---

## 🔧 Common Issues & Solutions

### Issue 1: Camera Not Found (`cv2.VideoCapture returns False`)

**Symptoms:**
```python
camera = cv2.VideoCapture(0)
ret, frame = camera.read()
# ret = False, frame = None
```

**Solutions:**

**A. Wrong device index**
```bash
# Find correct device index
v4l2-ctl --list-devices

# Try all video devices
for i in {0..9}; do
    echo "Testing /dev/video$i"
    v4l2-ctl -d /dev/video$i --all 2>&1 | grep -i "pixel format"
done

# Test each device with Python
python3 -c "
import cv2
for i in range(10):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        print(f'Device {i}: {'OK' if ret else 'FAIL'}')
        cap.release()
"
```

**B. Use CSI camera instead of device index**
```python
# For CSI cameras, use GStreamer pipeline
gst_pipeline = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! "
    "nvvidconv ! video/x-raw, format=BGRx ! "
    "videoconvert ! video/x-raw, format=BGR ! appsink"
)
camera = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
```

---

### Issue 2: Permission Denied

**Symptoms:**
```
VIDEOIO ERROR: V4L2: Could not open /dev/video0
Permission denied
```

**Solution:**

```bash
# Add user to video group
sudo usermod -aG video $USER

# Apply changes (logout/login OR run)
newgrp video

# Set device permissions (temporary fix)
sudo chmod 666 /dev/video0

# Verify permissions
ls -la /dev/video0
# Should show: crw-rw-rw- or crw-rw----+ with video group

# Make permanent (create udev rule)
echo 'KERNEL=="video[0-9]*", GROUP="video", MODE="0660"' | sudo tee /etc/udev/rules.d/99-camera.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

### Issue 3: Camera Opens But No Frames

**Symptoms:**
```python
camera.isOpened() == True
ret, frame = camera.read()  # ret = False
```

**Solutions:**

**A. Wrong codec/format**
```python
# Force MJPG codec
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

ret, frame = camera.read()
```

**B. Check supported formats**
```bash
# List supported formats for device
v4l2-ctl -d /dev/video0 --list-formats-ext

# Try YUYV format in Python
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','U','Y','V'))
```

**C. Use v4l2-ctl to set format**
```bash
# Set specific format
v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=MJPG

# Then open with OpenCV
python3 -c "import cv2; cap = cv2.VideoCapture(0); print(cap.read()[0])"
```

---

### Issue 4: Multiple Video Devices (Which to Use?)

**Problem:** `/dev/video0` through `/dev/video9` exist - which is the real camera?

**Solution:**

```bash
# Method 1: Check capabilities
for i in {0..9}; do
    echo "=== /dev/video$i ==="
    v4l2-ctl -d /dev/video$i --all 2>&1 | grep -E "(Driver|Card type|Pixel Format)"
done

# Method 2: Look for "capture" capability
for i in {0..9}; do
    v4l2-ctl -d /dev/video$i --all 2>&1 | grep -q "Video Capture" && echo "video$i: CAPTURE"
done

# Method 3: Use our diagnostic script
python3 diagnose_camera.py
```

**Common patterns on Jetson:**
- `/dev/video0` - Often CSI camera or first USB camera
- `/dev/video1` - Secondary camera or CSI subdevice
- `/dev/video2-7` - CSI subdevices (metadata, controls) - **NOT for capture**

**Rule of thumb:** Test devices 0-2 first, skip higher numbers unless they show "Video Capture" capability.

---

### Issue 5: Camera In Use By Another Process

**Symptoms:**
```
VIDEOIO ERROR: V4L2: Device or resource busy
```

**Solution:**

```bash
# Find process using camera
sudo lsof /dev/video0

# Output shows PID and process name
# COMMAND   PID USER   FD   TYPE DEVICE
# python3  1234 user    3u   CHR  81,0

# Kill the process
kill 1234

# Or force kill
kill -9 1234

# If it's a system service
sudo systemctl stop nvargus-daemon
sudo systemctl restart nvargus-daemon
```

---

### Issue 6: Low FPS / Slow Capture

**Symptoms:**
- Camera FPS < 10 when expecting 30
- Laggy video feed

**Solutions:**

**A. Reduce resolution**
```python
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
camera.set(cv2.CAP_PROP_FPS, 30)
```

**B. Use hardware acceleration (CSI)**
```python
gst_pipeline = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=640, height=480, framerate=30/1 ! "
    "nvvidconv ! video/x-raw, format=BGRx ! "
    "videoconvert ! video/x-raw, format=BGR ! appsink"
)
camera = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
```

**C. Change USB buffering**
```python
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer lag
```

**D. Use MJPG instead of raw**
```python
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
```

**E. Check CPU throttling**
```bash
# Check current CPU frequency
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq

# Set max performance mode
sudo nvpmodel -m 0
sudo jetson_clocks
```

---

## 📋 Step-by-Step Testing Procedure

Follow this checklist when camera fails:

### Step 1: Verify Hardware Connection
```bash
# Check if device exists
ls -la /dev/video*
# Expected: At least /dev/video0 should exist
```
✅ **Success:** Devices found → Go to Step 2  
❌ **Failure:** No devices → Check physical connection, reboot

### Step 2: Check Permissions
```bash
groups $USER | grep video
```
✅ **Success:** "video" appears → Go to Step 3  
❌ **Failure:** Not in group → Run `sudo usermod -aG video $USER && newgrp video`

### Step 3: Test with GStreamer (CSI)
```bash
gst-launch-1.0 nvarguscamerasrc sensor-id=0 ! nvoverlaysink
```
✅ **Success:** Video appears → CSI camera works, use GStreamer pipeline  
❌ **Failure:** Error → Try Step 4 (USB)

### Step 4: Test with GStreamer (USB)
```bash
gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! xvimagesink
```
✅ **Success:** Video appears → USB camera works  
❌ **Failure:** Error → Go to Step 5

### Step 5: Check Device Capabilities
```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --all
```
✅ **Success:** Shows "Video Capture" → Device is correct  
❌ **Failure:** No capture capability → Try different device index

### Step 6: Test with OpenCV
```python
python3 diagnose_camera.py
```
✅ **Success:** Camera opens and captures frames → Problem solved  
❌ **Failure:** Still fails → Check OpenCV build (Step 7)

### Step 7: Verify OpenCV Installation
```bash
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -E "(GStreamer|V4L|FFMPEG)"
```
✅ **Success:** Shows GStreamer and V4L support → OpenCV is correct  
❌ **Failure:** Missing support → Rebuild OpenCV (see below)

---

## 📷 CSI vs USB Camera Differences

### CSI Camera (MIPI-CSI connector)

**Identification:**
- Physical: Ribbon cable connected to CSI port
- Software: Uses `nvarguscamerasrc` in GStreamer

**Opening with OpenCV:**
```python
# Method 1: GStreamer pipeline (RECOMMENDED)
gst_pipeline = (
    "nvarguscamerasrc sensor-id=0 ! "
    "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! "
    "nvvidconv ! video/x-raw, format=BGRx ! "
    "videoconvert ! video/x-raw, format=BGR ! appsink"
)
camera = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

# Method 2: Direct device (may not work)
camera = cv2.VideoCapture(0)  # Often fails with CSI
```

**Advantages:**
- Higher quality
- Hardware-accelerated encoding/decoding
- Better integration with Jetson ISP

**Disadvantages:**
- Requires GStreamer
- More complex setup
- Limited to certain resolutions/framerates

**Common Issues:**
```bash
# Error: "No cameras available"
# Solution: Check nvargus daemon
sudo systemctl status nvargus-daemon
sudo systemctl restart nvargus-daemon

# Error: "GST_ARGUS: Setup Failed"
# Solution: Verify camera is connected to correct CSI port
# Try sensor-id=1 if sensor-id=0 fails
```

---

### USB Camera (USB connector)

**Identification:**
- Physical: USB cable connected to USB port
- Software: Shows up as `/dev/video*` with v4l2

**Opening with OpenCV:**
```python
# Method 1: Device index (SIMPLE)
camera = cv2.VideoCapture(0)

# Method 2: Device path (EXPLICIT)
camera = cv2.VideoCapture("/dev/video0")

# Method 3: GStreamer (ADVANCED)
gst_pipeline = "v4l2src device=/dev/video0 ! videoconvert ! appsink"
camera = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
```

**Advantages:**
- Simpler to use
- Standard V4L2 interface
- Works with any USB camera

**Disadvantages:**
- No hardware acceleration
- USB bandwidth limitations
- May require format negotiation

**Common Issues:**
```bash
# Error: "Unable to stop the stream"
# Solution: Camera might be in wrong mode
v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=MJPG

# Error: "Select timeout"
# Solution: Reduce resolution or change format
```

---

## 🛠️ OpenCV Build Requirements for Jetson

### Check Current OpenCV Build

```bash
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -A10 "Video I/O"
```

**Required features for Jetson:**
- ✅ GStreamer: YES
- ✅ V4L/V4L2: YES
- ⚠️ FFMPEG: Optional (recommended)

### If OpenCV Missing GStreamer Support

```bash
# Install GStreamer dependencies
sudo apt-get update
sudo apt-get install -y \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools

# Install v4l2 utilities
sudo apt-get install -y v4l-utils

# Rebuild OpenCV with GStreamer (example for OpenCV 4.5.0)
git clone https://github.com/opencv/opencv.git
cd opencv
mkdir build && cd build
cmake -D CMAKE_BUILD_TYPE=RELEASE \
      -D WITH_GSTREAMER=ON \
      -D WITH_V4L=ON \
      -D WITH_LIBV4L=ON \
      -D BUILD_opencv_python3=ON \
      ..
make -j$(nproc)
sudo make install
```

### Quick Install (Use JetPack OpenCV)

```bash
# JetPack usually includes pre-built OpenCV with GStreamer
# Verify installation
dpkg -l | grep opencv
python3 -c "import cv2; print(cv2.__version__)"
```

---

## 🔗 Diagnostic Script Reference

**Location:** `crowd-monitoring-ml/jetson/diagnose_camera.py`

**Usage:**
```bash
# Run full diagnostics
python3 diagnose_camera.py

# Test specific device
python3 diagnose_camera.py --device 1

# Test CSI camera
python3 diagnose_camera.py --csi

# Verbose output
python3 diagnose_camera.py --verbose
```

**What it checks:**
1. ✅ Lists all video devices
2. ✅ Checks permissions
3. ✅ Tests each device with OpenCV
4. ✅ Captures test frame
5. ✅ Reports working devices
6. ✅ Suggests fixes for failures

**Output example:**
```
=== Camera Diagnostics ===
Found devices: /dev/video0, /dev/video1
Testing /dev/video0... OK (640x480 @ 30fps)
Testing /dev/video1... FAIL (not a capture device)

✅ Working camera: /dev/video0
Recommended: cv2.VideoCapture(0)
```

---

## 🆘 Emergency Fallback Options

When standard methods fail, try these fallbacks:

### Fallback 1: Lower Resolution
```python
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
camera.set(cv2.CAP_PROP_FPS, 15)
```

### Fallback 2: Try Different Device Index
```python
for device in [0, 1, 2]:
    camera = cv2.VideoCapture(device)
    if camera.isOpened():
        ret, frame = camera.read()
        if ret:
            print(f"Working device: {device}")
            break
```

### Fallback 3: Force MJPG Codec
```python
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
```

### Fallback 4: GStreamer Test Mode
```bash
# Test with GStreamer directly (bypass OpenCV)
gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! autovideosink
```

### Fallback 5: Use videotestsrc (Synthetic Feed)
```python
# For testing without real camera
gst_pipeline = "videotestsrc ! videoconvert ! appsink"
camera = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
```

### Fallback 6: Check for USB Camera with lsusb
```bash
lsusb | grep -i camera
# If camera appears in lsusb but not /dev/video*, driver issue

# Load UVC driver
sudo modprobe uvcvideo
```

### Fallback 7: Reset Camera Device
```bash
# Unbind and rebind USB camera
# Find device (example: 1-2:1.0)
ls /sys/bus/usb/drivers/uvcvideo/

# Unbind
echo "1-2:1.0" | sudo tee /sys/bus/usb/drivers/uvcvideo/unbind

# Rebind
echo "1-2:1.0" | sudo tee /sys/bus/usb/drivers/uvcvideo/bind
```

### Fallback 8: Reboot Jetson
```bash
# Nuclear option - often fixes transient issues
sudo reboot
```

---

## 📞 Getting Help

If all else fails:

1. **Run diagnostics and save output:**
   ```bash
   python3 diagnose_camera.py > camera_diagnostics.txt 2>&1
   v4l2-ctl --list-devices >> camera_diagnostics.txt
   dmesg | grep -i video >> camera_diagnostics.txt
   ```

2. **Check system logs:**
   ```bash
   dmesg | tail -50
   journalctl -xe | grep -i camera
   ```

3. **Verify hardware:**
   - Check physical connections
   - Try camera on another system
   - Test different USB ports

4. **Search for model-specific issues:**
   - NVIDIA Jetson Forums
   - JetsonHacks website
   - GitHub Issues for OpenCV

---

## ✅ Quick Reference Card

| Problem | Quick Fix |
|---------|-----------|
| Permission denied | `sudo usermod -aG video $USER && newgrp video` |
| Device busy | `sudo lsof /dev/video0` then `kill <PID>` |
| Wrong device | `v4l2-ctl --list-devices` and try different index |
| No frames | `camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))` |
| CSI not working | Use GStreamer pipeline with `nvarguscamerasrc` |
| Low FPS | Reduce resolution + `sudo jetson_clocks` |
| Camera not listed | Check `lsusb` and `sudo modprobe uvcvideo` |

**Most Common Fix:** Wrong device index - always run `v4l2-ctl --list-devices` first!

---

**Last Updated:** 2024  
**Maintainer:** IDP Crowd Monitoring Team  
**Related Files:** `diagnose_camera.py`, `camera_manager.py`, `data_collection.py`
