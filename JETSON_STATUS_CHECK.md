# Jetson Status Checker

## Quick Diagnosis

Run this in PowerShell to check the system:

```powershell
# 1. Check if ground server is receiving frames
Invoke-RestMethod -Uri "http://localhost:8080/api/status"

# 2. Try to get a video frame
Invoke-WebRequest -Uri "http://localhost:8080/api/video_feed" -OutFile "test_frame.jpg"
# If this fails with 404, Jetson is NOT sending video frames

# 3. Check active alerts
Invoke-RestMethod -Uri "http://localhost:8080/api/alerts"
```

## Problem Identified

Your dashboard shows:
- ✅ Server: Connected
- ✅ Jetson: Online  
- ✅ FPS: 0.0 (but frames are being processed - 2069 frames received!)
- ❌ Video feed: "Waiting for camera feed..." (404 errors)
- ⚠️ Old test alerts still showing (TEST-1775...)

## Why No Video?

The Jetson is sending **inference data** (person count, alerts, etc.) but **NOT sending video frames**.

**Possible causes:**

1. **Jetson running without camera** (test mode)
   - Check Jetson console for "Camera initialized" message
   - If it says "synthetic frames", that's the issue

2. **OpenCV not installed on Jetson**
   - Can't encode JPEG frames without cv2.imencode()
   - Jetson needs: `pip install opencv-python`

3. **Frame encoding failing silently**
   - Check Jetson console for encoding errors

## To Fix: Check Jetson Console

Look for one of these:

**✅ Good (camera working):**
```
🎥 CAMERA INITIALIZATION
✅ CAMERA READY
   Device: /dev/video0
   Backend: V4L2
✅ Connected to ground server at localhost:9000
📊 Frame: 30 | FPS: 15.2 | Persons: 3 | Alerts: 0 | Connected: True
```

**❌ Bad (no camera):**
```
⚠️ Camera initialization failed, but continuing...
   Pipeline will run with synthetic frames for testing
⚠️ OpenCV not available, cannot encode frame for transmission
```

## Solutions

### Solution 1: If running on Windows/PC (no real camera)
The Jetson code is meant to run on actual Jetson hardware with a camera. On PC:
- You won't see video feed (no camera)
- Person count will be 0
- You can test alerts manually

### Solution 2: If running on actual Jetson device
```bash
# Install OpenCV
pip install opencv-python

# Check camera
ls -l /dev/video*

# Run Jetson pipeline
python inference_pipeline.py --server <SERVER_IP> --port 9000
```

### Solution 3: Clear old test alerts
```bash
# In PowerShell
Invoke-RestMethod -Uri "http://localhost:8080/api/alerts" -Method GET

# Or restart the ground server to clear memory
```

## Expected Dashboard Behavior

**With Jetson + Camera:**
- Live video feed shows camera view
- Person count updates in real-time
- Heatmap overlay shows density
- Blue dots mark detected persons

**Without Camera (PC testing):**
- "Waiting for camera feed..." message
- Person count = 0
- Density = 0
- Can still test alert system logic

## Quick Test

Run this from the `ground_server` directory:

```python
# test_server_state.py
import requests

status = requests.get("http://localhost:8080/api/status").json()

print(f"Jetson Connected: {status['jetson_connected']}")
print(f"Total Frames: {status['total_frames']}")
print(f"Active Alerts: {status['active_alerts']}")

if status['total_frames'] > 0:
    print("✅ Jetson is sending data")
    
    try:
        frame = requests.get("http://localhost:8080/api/video_feed")
        if frame.status_code == 200:
            print("✅ Video feed working!")
        else:
            print(f"❌ Video feed not available: {frame.status_code}")
            print(f"   Reason: {frame.text}")
    except Exception as e:
        print(f"❌ Video feed error: {e}")
else:
    print("❌ No data from Jetson")
```
