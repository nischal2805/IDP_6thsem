# Critical Issues Report: Crowd Monitoring ML System
## Drone-Based Fall Detection & Crowd Monitoring

**Date**: 2026-04-02  
**Evaluated Components**: Jetson Edge Device, Ground Server, Dashboard  
**Total Issues Found**: 24  
**Critical Issues**: 5  
**High Severity**: 7  
**Medium Severity**: 9  
**Low Severity**: 3

---

## Executive Summary

This system consists of three main components:
1. **Jetson Edge Device** - Runs on-device inference for pose detection, fall detection, crowd density estimation
2. **Ground Server** - FastAPI backend that receives data from Jetson and serves dashboard
3. **Dashboard** - React web interface for real-time monitoring

**Most Critical Finding**: The primary feature of the system (automatic fall and panic alert generation) is **completely disabled** in the code despite all the detection logic being implemented. The system can only generate "fake alerts" via test buttons on the dashboard.

---

## 🚨 CRITICAL ISSUES (Must Fix Immediately)

### JETSON-001: Alerts Completely Disabled ⚠️⚠️⚠️
**File**: `jetson/inference_pipeline.py` (Lines 557-563)  
**Severity**: CRITICAL

```python
# 5. Generate alerts (DISABLED - no alerts generated)
alerts = []

# TODO: Re-enable alerts when thresholds are properly calibrated
# Fall detection: requires manual testing and threshold tuning
# Panic detection: requires optical flow calibration
# Crush risk: requires proper density per m² calculation
```

**Impact**: The entire purpose of the system (drone-based fall detection and panic alerts) is non-functional. All the ML models run correctly (pose detection, fall detection, optical flow, density estimation) but NO ALERTS are ever generated or sent. The dashboard only shows "fake alerts" when you click the test buttons.

**Fix Required**:
1. Re-enable alert generation in `_process_frame()` method
2. Add configurable thresholds to `jetson_config.toml`
3. Implement alert deduplication (don't spam same alert)
4. Add cooldown periods between alerts for same person/event

---

### SERVER-001: CORS Allows All Origins (Security Vulnerability)
**File**: `ground_server/server.py` (Lines 85-91)  
**Severity**: CRITICAL

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ DANGEROUS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Impact**: Any website on the internet can access your API, view camera feeds, trigger alerts, and manipulate system state. This is a **major security vulnerability**.

**Fix Required**:
```python
ALLOWED_ORIGINS = os.environ.get(
    "CORS_ORIGINS", 
    "http://localhost:5173,http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### DASHBOARD-001: Hardcoded WebSocket URL
**File**: `dashboard/src/App.jsx` (Line 9)  
**Severity**: CRITICAL

```javascript
const WS_URL = 'ws://localhost:8080/ws/dashboard';
```

**Impact**: Dashboard **will not work** when deployed to any server or accessed from another computer. This is a critical deployment blocker.

**Fix Required**:
```javascript
const WS_URL = `ws://${window.location.hostname}:8080/ws/dashboard`;
// Or use environment variable:
const WS_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.hostname}:8080/ws/dashboard`;
```

---

### DASHBOARD-002: Hardcoded API URL for Video Feed
**File**: `dashboard/src/components/HeatmapView.jsx` (Line 9)  
**Severity**: CRITICAL

```javascript
setFrameUrl(`http://localhost:8080/api/video_feed?t=${Date.now()}`);
```

**Impact**: Video playback (the camera feed showing crowd) will not work in production. Same issue as DASHBOARD-001.

**Fix Required**:
```javascript
const baseUrl = window.location.hostname === 'localhost' 
  ? 'http://localhost:8080' 
  : `http://${window.location.hostname}:8080`;
setFrameUrl(`${baseUrl}/api/video_feed?t=${Date.now()}`);
```

---

### DASHBOARD-003: Fake Alert Buttons in Production UI
**File**: `dashboard/src/App.jsx` (Lines 200-212)  
**Severity**: CRITICAL

```javascript
<button
  className="w-full btn-primary"
  onClick={() => fetch('/api/test/alert?alert_type=fall', { method: 'POST' })}
>
  🧪 Test Fall Alert
</button>
```

**Impact**: Users can trigger fake fall and panic alerts that get sent to **Telegram**, causing confusion and false emergencies. These buttons should not be accessible in production.

**Fix Required**:
```javascript
{import.meta.env.DEV && (
  <div className="card">
    <h3 className="font-bold mb-3">⚠️ Dev Tools</h3>
    {/* Test buttons here */}
  </div>
)}
```

---

## 🔴 HIGH SEVERITY ISSUES

### JETSON-002: Socket Timeout Too Aggressive
**File**: `jetson/inference_pipeline.py` (Line 400)

```python
self.socket.settimeout(5)  # 5 second timeout
```

**Impact**: Connection will drop during legitimate network delays, causing data loss.

**Fix**: Increase to 30 seconds or make configurable. Add exponential backoff for reconnection.

---

### JETSON-003: No Auto-Reconnection to Server
**File**: `jetson/inference_pipeline.py` (Lines 392-407)

**Impact**: If ground server restarts or network hiccups, Jetson will **never reconnect** automatically. Requires manual restart of entire edge device.

**Fix**: Implement background reconnection thread with exponential backoff:
```python
def _reconnect_loop(self):
    while self.running:
        if not self.connected:
            try:
                self._connect_server()
                if self.connected:
                    print("✅ Reconnected to server")
            except:
                time.sleep(min(self.reconnect_delay, 60))
                self.reconnect_delay *= 2
        time.sleep(5)
```

---

### SERVER-003: Alerts Stored Only in Memory
**File**: `ground_server/server.py` (Line 47)

```python
state.active_alerts = []  # Lost on restart!
```

**Impact**: All alert history is lost when server restarts. For a safety system, this is unacceptable. Need to track alert history for liability and analysis.

**Fix**: Persist to SQLite database with retention policy:
```python
# Add SQLite persistence
import sqlite3
db = sqlite3.connect("alerts.db")
db.execute("""CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    type TEXT,
    timestamp REAL,
    data JSON,
    acknowledged INTEGER DEFAULT 0
)""")
```

---

### SERVER-002: Broad Exception Catch Without Logging
**File**: `ground_server/server.py` (Lines 286-288)

```python
for client in dashboard_clients:
    try:
        await client.send_json(message)
    except:  # ⚠️ Catches everything silently
        disconnected.add(client)
```

**Impact**: Real errors (serialization issues, corrupted data) are silently ignored. Impossible to debug.

**Fix**:
```python
try:
    await client.send_json(message)
except WebSocketDisconnect:
    disconnected.add(client)
except Exception as e:
    logger.error(f"Error broadcasting to client: {e}")
    disconnected.add(client)
```

---

### DASHBOARD-004: Polling Video Feed (Performance Issue)
**File**: `dashboard/src/components/HeatmapView.jsx` (Lines 7-12)

```javascript
const interval = setInterval(() => {
  setFrameUrl(`http://localhost:8080/api/video_feed?t=${Date.now()}`);
}, 200);  // 5 requests per second!
```

**Impact**: 
- 5 HTTP requests per second per client
- 10 clients = 50 requests/second
- Wastes bandwidth and CPU
- Not scalable

**Fix**: Implement proper video streaming (MJPEG stream or WebSocket-based):
```python
# In server.py
from starlette.responses import StreamingResponse

@app.get("/api/video_stream")
async def video_stream():
    async def frame_generator():
        while True:
            if state.latest_frame:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + 
                    state.latest_frame + 
                    b'\r\n'
                )
            await asyncio.sleep(0.1)
    
    return StreamingResponse(
        frame_generator(),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )
```

---

### ARCH-001: Single Point of Failure
**Entire System Architecture**

**Impact**: If ground server crashes, entire system goes down:
- Jetson can't send data anywhere
- Dashboard can't display anything
- No alerts can be sent
- No data is logged

**Fix**: Implement:
1. Health check endpoint with automatic restart
2. Message queue (Redis/RabbitMQ) between components
3. Local logging on Jetson (fallback when server down)
4. Multi-instance server with load balancer

---

### ARCH-002: No Support for Multiple Drones
**File**: `ground_server/server.py` (Line 118)

```python
state.connected_jetson = True  # Boolean, not list!
```

**Impact**: System says "fleet monitoring" and "multiple drones" but architecture only supports ONE Jetson device at a time. Second Jetson will override the first.

**Fix**:
```python
@dataclass
class SystemState:
    connected_devices: Dict[str, DeviceInfo] = None  # device_id -> info
    
# Update protocol to include device_id in every packet
# Track per-device alerts, frames, GPS, etc.
```

---

## ⚠️ MEDIUM SEVERITY ISSUES

### JETSON-004: Silent Exception Handling in Send
Lines 455-457 - Send errors caught and logged but no recovery attempted.

### JETSON-005: Unused Frame Queue
Line 105 - `frame_queue` created but never used. Dead code.

### SERVER-004: Global State Not Thread-Safe
Race conditions possible when multiple async tasks modify `state` object.

### SERVER-005: Unbounded Memory Growth
Forecaster history grows forever. Will cause OOM after weeks of operation.

### SERVER-006: Incomplete Read Error Handling
Partial packets from network errors are completely lost.

### DASHBOARD-005: Acknowledge Doesn't Send to Server
Alert acknowledgment is local-only, not synced with server/other clients.

### DASHBOARD-006: Duplicate Alerts
Same alert appears multiple times in feed without deduplication.

### ARCH-003: No Alert Deduplication
Same alert sent every frame. Telegram will get spammed.

### ARCH-004: No Structured Logging
All components use `print()`. Can't debug production or track metrics.

---

## 🟡 LOW SEVERITY ISSUES

### JETSON-006: Hardcoded CPU Device
GPU acceleration never used despite Jetson having CUDA capability.

### SERVER-007: Video Frames Kept in Memory
High memory usage for high-resolution frames.

### DASHBOARD-007: No WebSocket Error Recovery UI
User not informed when connection fails.

---

## Summary by Component

### Jetson Edge Device
- ✅ **Working**: Pose detection, fall detection logic, density estimation, optical flow
- ❌ **Broken**: Alert generation disabled, no auto-reconnect, inefficient network protocol
- 🎯 **Priority**: Re-enable alerts, implement reconnection, fix socket timeout

### Ground Server
- ✅ **Working**: WebSocket hub, LSTM forecasting, Telegram integration (when alerts enabled)
- ❌ **Broken**: Security (CORS), data persistence, thread safety, scalability
- 🎯 **Priority**: Fix CORS, persist alerts to database, support multiple Jetson devices

### Dashboard
- ✅ **Working**: Real-time visualization, charting, alert feed UI
- ❌ **Broken**: Hardcoded URLs (won't deploy), fake alert buttons in production, polling video
- 🎯 **Priority**: Fix URLs for deployment, hide test buttons, implement streaming video

---

## Recommended Fix Order

### Phase 1: Make It Work (Critical Fixes)
1. **JETSON-001**: Re-enable alert generation ⚠️⚠️⚠️
2. **DASHBOARD-001**: Fix hardcoded WebSocket URL
3. **DASHBOARD-002**: Fix hardcoded API URL
4. **DASHBOARD-003**: Hide fake alert buttons in production

### Phase 2: Make It Secure
5. **SERVER-001**: Fix CORS vulnerability
6. **SERVER-003**: Persist alerts to database
7. **SERVER-002**: Proper error logging

### Phase 3: Make It Reliable
8. **JETSON-003**: Implement auto-reconnection
9. **JETSON-002**: Fix socket timeout
10. **DASHBOARD-004**: Implement video streaming
11. **ARCH-001**: Add health checks and restart mechanisms

### Phase 4: Make It Scalable
12. **ARCH-002**: Support multiple Jetson devices
13. **ARCH-003**: Implement alert deduplication
14. **SERVER-004**: Thread-safe state management
15. **ARCH-004**: Structured logging and metrics

---

## Testing Checklist

After fixing issues, verify:

### Jetson
- [ ] Alerts are generated when fall detected
- [ ] Alerts sent to ground server
- [ ] Auto-reconnects when server restarts
- [ ] No crashes after 1 hour of operation
- [ ] GPU acceleration working (check nvidia-smi)

### Ground Server
- [ ] CORS restricted to allowed origins
- [ ] Alerts persisted across restarts
- [ ] Multiple Jetson devices can connect
- [ ] WebSocket broadcasts to all dashboard clients
- [ ] Telegram alerts received correctly

### Dashboard
- [ ] Works when accessed from different computer
- [ ] Video feed displays correctly
- [ ] Alerts update in real-time
- [ ] Test buttons hidden in production build
- [ ] Reconnects when server restarts

---

## Conclusion

The system has **solid ML/CV foundations** with working pose detection, fall detection, and crowd analysis algorithms. However, it has **critical deployment and operational issues** that prevent it from working as a production safety system.

**Most Critical**: The alert generation is completely disabled, making this a "detection-only" system rather than an "alert system". This MUST be fixed first.

The architecture needs work to support multiple drones, persist data, and handle failures gracefully. The dashboard needs configuration for deployment.

**Estimated Fix Time**:
- Phase 1 (Critical): 4-6 hours
- Phase 2 (Security): 3-4 hours  
- Phase 3 (Reliability): 6-8 hours
- Phase 4 (Scalability): 8-12 hours

**Total**: 21-30 hours of focused development work to make this production-ready.
