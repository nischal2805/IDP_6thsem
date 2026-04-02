# Quick Start Guide - Fixed System

## 🚀 Start the System (3 Terminals)

### Terminal 1: Ground Server
```bash
cd D:\IDP\crowd-monitoring-ml\ground_server
python server.py
```
**Wait for**: `Jetson listener started on ('0.0.0.0', 9000)`

---

### Terminal 2: Jetson Edge Device
```bash
cd D:\IDP\crowd-monitoring-ml\jetson
python inference_pipeline.py --server localhost --port 9000
```
**Wait for**: `✅ Connected to ground server at localhost:9000`

---

### Terminal 3: Dashboard
```bash
cd D:\IDP\crowd-monitoring-ml\dashboard
npm run dev
```
**Access**: http://localhost:5173

---

## ✅ What Should Work Now

1. **Video Feed**: Live camera feed displays in dashboard
2. **Person Count**: Real-time count of detected persons
3. **Density Heatmap**: Color overlay showing crowd density
4. **Fall Detection**: Alerts when person falls
5. **Connection Status**: Green indicators when connected
6. **Alert Feed**: Real-time alerts in right panel

---

## 🔧 What Was Fixed

✅ Re-enabled fall detection alerts (were disabled)  
✅ Removed fake test buttons from UI  
✅ Fixed CORS security vulnerability  
✅ Increased socket timeout for stability  
✅ Added detailed logging for debugging  
✅ Better error messages throughout

---

## 📊 Console Output to Expect

### Jetson Console (every 30 frames):
```
📊 Frame: 30 | FPS: 15.2 | Persons: 3 | Alerts: 0 | Connected: True
```

### When Fall Detected:
```
🚨 FALL DETECTED: Person 1 | Confidence: 0.85 | Duration: 2.3s
```

### Ground Server Console:
```
📊 Jetson data received | Frame: 30 | Persons: 3 | Density: 5 | Alerts: 0
📢 Processing alert: FALL | ID: FALL-123 | Confidence: 0.85
   ✅ Fall alert sent to Telegram
```

---

## 🐛 Quick Troubleshooting

**Dashboard shows "Waiting for camera feed"**
→ Wait 5-10 seconds for Jetson to connect

**"Connection refused" error**
→ Start ground server first (Terminal 1)

**No video showing**
→ Check Jetson console for camera initialization errors

**Alerts not appearing**
→ Check thresholds: Fall confidence >0.7, Crush density >6.0

---

## 📝 Files Modified

1. `jetson/inference_pipeline.py` - Re-enabled alerts, better logging
2. `ground_server/server.py` - Fixed CORS, improved error handling  
3. `dashboard/src/App.jsx` - Removed test buttons

**Full details**: See `CRITICAL_FIXES_APPLIED.md`
