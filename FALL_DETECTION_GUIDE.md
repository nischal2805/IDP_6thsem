# Fall Detection - How It Works

## Overview
Fall detection uses **pose keypoints** from YOLO to detect when a person falls.

## Detection Logic

### 1. Aspect Ratio Check
```python
aspect_ratio = bbox_width / bbox_height
if aspect_ratio > 1.5:  # Person is wider than tall
    -> SUSPECTED FALL
```

### 2. Keypoint Analysis
Checks vertical position of key body parts:
- **Hips** (keypoints 11, 12)
- **Shoulders** (keypoints 5, 6)
- **Head** (keypoints 0)

If hips are at similar height to shoulders → person is horizontal → FALL

### 3. Temporal Confirmation
Fall must persist for **1.5 seconds** before confirmed.

### State Machine:
```
STANDING → SUSPECTED (aspect > 1.5) → CONFIRMED (1.5s) → RECOVERING
```

## How to Test Fall Detection

### Method 1: Have Someone Lie Down
1. Start the system
2. Have a person stand in camera view
3. Person lies down on ground
4. Wait 2 seconds
5. Should trigger fall alert

### Method 2: Simulate with Objects
Use a mannequin or tall object that can be tilted horizontally.

### Method 3: Inject Test Fall (Developer Mode)
While inference pipeline is running:
1. Press **'f'** key (if display is enabled)
2. This forces a test fall event

## Current Status: **DISABLED**

Alerts are currently disabled in `inference_pipeline.py` line 542-545.

To re-enable:
```python
# In inference_pipeline.py, replace line 542-545 with:
alerts = []

for event in fall_events:
    if event.confirmed and event.confidence > 0.8:
        alert = self.alert_manager.create_fall_alert(
            person_id=event.person_id,
            confidence=event.confidence,
            bbox=tuple(event.bbox) if event.bbox is not None else None,
            duration=event.duration_seconds
        )
        alerts.append(json.loads(alert.to_json()))
```

## Tuning Parameters

File: `crowd-monitoring-ml/jetson/fall_detector.py`

Key thresholds:
```python
ASPECT_RATIO_THRESHOLD = 1.5  # Lower = more sensitive
KEYPOINT_CONFIDENCE_MIN = 0.3  # Lower = less strict
FALL_CONFIRMATION_TIME = 1.5  # seconds
```

## Why Falls Were False Triggering

1. **Camera movement** - drone motion makes bboxes wide
2. **Sitting people** - chairs make aspect ratio > 1.5
3. **Occlusion** - partial views trigger false positives

**Solution:** Need to add:
- IMU stabilization (ignore during drone movement)
- Sitting vs. falling classifier
- Multi-frame optical flow confirmation

## Dashboard Visualization

Fall detection status shown in bottom-right "Drone Status" panel:
- ✅ **No falls detected** - green
- ⚠️ **Fall suspected** - yellow
- 🔴 **FALL DETECTED** - red alert

Inference timing shows fall detection overhead (~0.0ms as it's pose-based, no ML model).
