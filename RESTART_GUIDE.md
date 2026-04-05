# Restart Guide - Video Feed Fix

## Problem
Dashboard shows "Jetson: Online" and person count updates, but video feed shows 404 error.

## Root Cause
**Jetson is running OLD code** from before the fixes were applied. The old code doesn't properly send video frames.

## Solution: Restart Everything

### Step 1: Restart Ground Server (on server machine)
```bash
# In terminal running server.py
# Press Ctrl+C to stop

cd D:\IDP\crowd-monitoring-ml\ground_server
python server.py
```

**Expected output:**
```
Jetson listener started on ('0.0.0.0', 9000)
Dashboard HTTP port: 8080
```

---

### Step 2: Restart Jetson (on edge device)
```bash
# In terminal running inference_pipeline.py
# Press Ctrl+C to stop

cd /path/to/crowd-monitoring-ml/jetson
python3 inference_pipeline.py --server <SERVER_IP> --port 9000
```

Replace `<SERVER_IP>` with your ground server IP address (or `localhost` if on same machine).

**Expected NEW output with updated code:**
```
🎥 CAMERA INITIALIZATION
✅ CAMERA READY
   Device: /dev/video0
✅ Connected to ground server at <SERVER_IP>:9000

📤 First frame send: JSON=2459 bytes, JPEG=45123 bytes
📊 Frame: 30 | FPS: 1.5 | Persons: 1 | Alerts: 0 | Connected: True | FrameSize: 921.6KB
📊 Frame: 60 | FPS: 1.5 | Persons: 1 | Alerts: 0 | Connected: True | FrameSize: 921.6KB
✅ Sent frame 100 with 44.1KB JPEG to server
```

**On ground server console, you should now see:**
```
✅ Jetson connected from ('192.168.1.x', 12345)
📸 First video frame received: 44.1KB JPEG
📊 Jetson data received | Frame: 30 | Persons: 1 | Density: 5 | Alerts: 0
📸 Received 100 video frames (latest: 44.1KB)
```

---

### Step 3: Check Dashboard
```bash
# Dashboard should already be running on port 3000
# If not:
cd D:\IDP\crowd-monitoring-ml\dashboard
npm run dev
```

Open: **http://localhost:3000**

**You should now see:**
- ✅ Live video feed from camera
- ✅ Person count updating (1, 2, etc.)
- ✅ Blue dots on detected persons
- ✅ Heatmap overlay
- ❌ No more old TEST alerts (server restart cleared them)

---

## Verification Checklist

After restart:

### Jetson Console:
- [ ] "📤 First frame send" message appears
- [ ] "✅ Sent frame 100" messages appear periodically
- [ ] "FrameSize: XX.XKB" shows in stats
- [ ] Person count changes when people move in/out of frame

### Ground Server Console:
- [ ] "📸 First video frame received" message appears
- [ ] "📸 Received N video frames" messages appear
- [ ] No 404 spam in logs

### Dashboard:
- [ ] Video feed displays (not "Waiting for camera feed...")
- [ ] Person count matches Jetson console
- [ ] Stats update in real-time
- [ ] No old TEST alerts

---

## If Video Still Not Working

1. **Check Jetson logs carefully** - look for:
   ```
   ⚠️ OpenCV not available, cannot encode frame
   ⚠️ Frame encoding error: ...
   ❌ Failed to send data: ...
   ```

2. **Check ground server logs** - look for:
   ```
   ⚠️ Jetson sending data without video frames (old code?)
   ```
   If you see this, Jetson is definitely running old code.

3. **Verify files are updated**:
   ```bash
   # On Jetson, check if file has new logging:
   grep "First frame send" jetson/inference_pipeline.py
   
   # Should return a match. If not, files weren't updated properly.
   ```

4. **Check network**:
   ```bash
   # On Jetson, verify connection to server:
   ping <SERVER_IP>
   telnet <SERVER_IP> 9000
   ```

---

## Quick Debug Commands

### Check if video frames are being received:
```powershell
# On server machine:
Invoke-RestMethod -Uri "http://localhost:8080/api/status"

# Should show:
# - jetson_connected: True
# - total_frames: increasing number
```

### Try to get a frame:
```powershell
Invoke-WebRequest -Uri "http://localhost:8080/api/video_feed" -OutFile "test.jpg"

# If successful: opens test.jpg (should show camera view)
# If 404: frames not being received
```

### Check alerts:
```powershell
Invoke-RestMethod -Uri "http://localhost:8080/api/alerts"

# Should be empty {} after server restart
```

---

## Summary

The Jetson is working and detecting people, but it's running the old code that doesn't send video frames properly. Simply **restart both server and Jetson** with the updated code, and the video feed will work!
