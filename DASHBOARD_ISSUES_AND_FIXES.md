# Dashboard Issues & Fixes

## Issue 1: No Live Video Feed ❌

**Problem**: You expect to see actual camera video with heatmap overlay, but dashboard only shows a grid visualization.

**Why**: The dashboard was designed to show a **grid-based heatmap**, not the actual video stream.

### Fix Options:

#### Option A: Add Video Stream to Dashboard (Recommended)
1. Run the web stream server on Jetson:
   ```bash
   python3 web_stream_server.py --camera 0 --port 8081
   ```

2. Add to dashboard (`HeatmapView.jsx`):
   ```jsx
   <img src="http://10.161.127.240:8081/video_feed" 
        alt="Live Feed" 
        style={{width: '100%', height: 'auto'}} />
   ```

#### Option B: Stream with Heatmap Overlay from Jetson
Modify `inference_pipeline.py` to:
- Encode frame with heatmap drawn on it
- Send JPEG over separate HTTP stream
- Dashboard loads it as `<img>` tag

---

## Issue 2: LSTM Forecast is Wrong 🤖

**Problem**: The LSTM model is **untrained** - it's using **random weights**.

**Why**: The forecaster initializes with untrained model (lstm_forecaster.py line 231-240).

### Fix:

#### Step 1: Train the model
```bash
cd D:\IDP\crowd-monitoring-ml\ground_server

# Option A: Train on synthetic data (quick test)
python -c "
from lstm_forecaster import ForecasterTrainer, LSTMForecaster, generate_synthetic_data
import torch

model = LSTMForecaster()
trainer = ForecasterTrainer(model, device='cpu')
train_data, val_data = generate_synthetic_data(num_samples=1000, pattern='mixed')
trainer.train(train_data, val_data, epochs=50, save_path='models/forecaster_model.pt')
"

# Option B: Collect real data first, then train
# Let the system run for 30-60 minutes to collect data via /api/history
# Export that data and train on it
```

#### Step 2: Forecaster will auto-load the model
The forecaster checks for `models/forecaster_model.pt` on init (line 247-252).

### Alternative: Disable LSTM and use simple averaging
Edit `server.py` line 155-157:
```python
# Simple moving average instead of LSTM
if len(forecaster.get_history()) >= 10:
    recent = forecaster.get_history()[-10:]
    avg = sum(recent) / len(recent)
    state.forecast = {
        "current": density_count,
        "predictions": {
            "10s": avg,
            "30s": avg,
            "60s": avg
        },
        "confidence": 0.7,
        "trend": "stable",
        "warning": None
    }
```

---

## Issue 3: Graph Jumping Around 📊

**Problem**: Crowd density over time graph is erratic.

**Why**: This is **NORMAL** when:
- Low person counts (0-5 people)
- Sporadic detections (person appears/disappears)
- Fast camera movement
- Inference at 1.5 FPS (CPU mode) causes frame skipping

### What the graph shows:
- **Cyan line**: Density estimate (crowd density heatmap peak)
- **Green line**: Actual person count (YOLO detections)

### Fixes:

#### Option 1: Smooth the data (dashboard side)
Edit `DensityChart.jsx` - add moving average:
```jsx
const smoothData = (data, windowSize = 5) => {
  return data.map((point, i) => {
    const start = Math.max(0, i - windowSize + 1);
    const window = data.slice(start, i + 1);
    const avgCount = window.reduce((sum, p) => sum + p.count, 0) / window.length;
    const avgPersons = window.reduce((sum, p) => sum + p.persons, 0) / window.length;
    return { ...point, count: avgCount, persons: avgPersons };
  });
};

// In render:
const displayData = smoothData(history, 5);
```

#### Option 2: Fix GPU to get stable 15 FPS
With GPU enabled, inference is consistent → smoother graph.

---

## Issue 4: Normal/Critical/Overflow Calculation 🚨

**Current Logic** (inference_pipeline.py lines 560-566):

```python
# Crush risk alert
if density_result.peak_density > 6.0:
    alerts.append({
        "alert_id": f"CRUSH-{frame_id:06d}",
        "type": "crush_risk",
        "severity": "critical" if density_result.peak_density > 8 else "high",
        "confidence": min(density_result.peak_density / 10.0, 1.0),
        # ...
    })
```

**Thresholds**:
- **Normal**: peak_density ≤ 6.0 (no alert)
- **High**: 6.0 < peak_density ≤ 8.0 (crush risk alert, high severity)
- **Critical**: peak_density > 8.0 (crush risk alert, critical severity)

### Issues with current calculation:

1. **Density values are relative** - What does "6.0" mean?
   - It's based on gaussian kernel density estimation
   - Not calibrated to real-world people/m²

2. **No area normalization** - Should be people per square meter

3. **Single threshold** - No multi-tier overflow (yellow/orange/red zones)

### Better Calculation:

```python
# In inference_pipeline.py, replace lines 560-566:

# Define zones based on person count and area
AREA_M2 = 100  # Configure based on camera FOV
density_per_m2 = density_result.count / AREA_M2

# Multi-tier thresholds (people per m²)
CAUTION_THRESHOLD = 2.0   # Yellow
WARNING_THRESHOLD = 4.0   # Orange  
CRITICAL_THRESHOLD = 6.0  # Red
OVERFLOW_THRESHOLD = 8.0  # Emergency

if density_per_m2 > OVERFLOW_THRESHOLD:
    severity = "overflow"
    message = "EMERGENCY OVERFLOW"
elif density_per_m2 > CRITICAL_THRESHOLD:
    severity = "critical"
    message = "CRITICAL DENSITY"
elif density_per_m2 > WARNING_THRESHOLD:
    severity = "warning"
    message = "HIGH DENSITY"
elif density_per_m2 > CAUTION_THRESHOLD:
    severity = "caution"
    message = "MODERATE DENSITY"
else:
    severity = "normal"
    message = None

if severity != "normal":
    alerts.append({
        "alert_id": f"DENSITY-{frame_id:06d}",
        "type": "density_alert",
        "severity": severity,
        "confidence": 0.9,
        "timestamp": time.time(),
        "data": {
            "density_per_m2": round(density_per_m2, 2),
            "total_people": density_result.count,
            "message": message
        }
    })
```

---

## Quick Wins

### 1. Add video stream to dashboard NOW
```bash
# On Jetson (new terminal)
cd ~/crowd-monitoring/IDP_6thsem/crowd-monitoring-ml/jetson
source ~/crowd-monitoring/boss/bin/activate
python3 web_stream_server.py --camera 0 --port 8081
```

```jsx
// In dashboard/src/components/HeatmapView.jsx, add at top:
<div className="relative mb-4">
  <img 
    src="http://10.161.127.240:8081/video_feed" 
    alt="Live Camera Feed"
    className="w-full rounded-lg border border-border"
  />
  <div className="absolute top-2 left-2 bg-black/70 px-2 py-1 rounded text-xs">
    Live Feed
  </div>
</div>
```

### 2. Disable LSTM until trained
```python
# In server.py line 155-157, comment out:
# forecast_result = forecaster.predict()
# if forecast_result:
#     state.forecast = forecaster.to_dict(forecast_result)

# Add simple placeholder:
state.forecast = {
    "current": density_count,
    "predictions": {"10s": density_count, "30s": density_count, "60s": density_count},
    "confidence": 0.0,
    "trend": "stable",
    "warning": None
}
```

### 3. Smooth the graph
Add to `App.jsx` line 75:
```jsx
// Smooth new data before adding to history
const smoothed_count = history.length > 0 
  ? (history[history.length-1].count * 0.7 + newPoint.count * 0.3)
  : newPoint.count;

const newPoint = {
  time: Date.now(),
  count: smoothed_count,
  persons: message.data?.person_count || 0
};
```

---

## Summary

| Issue | Severity | Fix Time | Status |
|-------|----------|----------|--------|
| No video feed | High | 5 min | Run web_stream_server.py |
| LSTM wrong | Medium | 1 hour | Train model or disable |
| Graph jumpy | Low | 10 min | Add smoothing |
| Alert thresholds | Medium | 20 min | Recalibrate thresholds |

**Recommended order:**
1. Add video stream (instant improvement)
2. Disable/mock LSTM (stop confusing data)
3. Fix alert thresholds (meaningful alerts)
4. Train LSTM properly (after collecting real data)
