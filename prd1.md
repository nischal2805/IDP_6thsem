**PRD 01**

**ML Pipeline - Crowd Monitoring & Distress Detection**

| **Project** | **IDP - Drone-Based Crowd Monitoring** | **Author** | **RVCE Drone Club**                       |
| ----------- | -------------------------------------- | ---------- | ----------------------------------------- |
| Status      | Active - Software Phase                | Hardware   | Jetson Orin Nano (67 TOPS) + Pixhawk Cube |
| ---         | ---                                    | ---        | ---                                       |

# **1\. Project Overview**

The IDP aims to deploy a drone-based real-time crowd monitoring system capable of (1) detecting crowd density and predicting dangerous density buildup using a downward-facing camera, and (2) detecting individual distress events such as falls and triggering GPS-tagged alerts. All time-critical inference runs onboard the Jetson Orin Nano. Aggregated data and heavy analytics are offloaded to a ground server exposing a React dashboard with Telegram alert integration.

# **2\. System Architecture**

## **2.1 Inference Topology**

| **Component**              | **Runs On**                      | **Output**                       |
| -------------------------- | -------------------------------- | -------------------------------- |
| YOLOv8n-pose               | Jetson Orin Nano (TensorRT FP16) | Person keypoints + BBoxes        |
| ---                        | ---                              | ---                              |
| Fall Classifier (MLP/LSTM) | Jetson Orin Nano                 | Distress label + confidence      |
| ---                        | ---                              | ---                              |
| Farneback Optical Flow     | Jetson Orin Nano (OpenCV)        | Flow magnitude + divergence      |
| ---                        | ---                              | ---                              |
| MobileCount (lite)         | Jetson Orin Nano (TensorRT)      | Crowd density map + count        |
| ---                        | ---                              | ---                              |
| LSTM Density Forecaster    | Ground Server (Python)           | Next-N-second density prediction |
| ---                        | ---                              | ---                              |
| GPS Alert Logic            | Ground Server                    | Telegram alert + dashboard push  |
| ---                        | ---                              | ---                              |

## **2.2 Data Flow**

Jetson Orin Nano captures frames from USB webcam → runs all onboard inference → publishes results over MAVLink telemetry or WiFi socket to ground server → ground server runs LSTM forecasting → React dashboard renders live heatmaps, counts, and alerts.

# **3\. ML Task 1: Distress & Fall Detection**

## **3.1 Approach**

This is a two-stage pipeline: pose estimation followed by temporal fall classification. The approach is validated in published research on the Le2i and URFD datasets.

## **3.2 Stage 1 - Pose Estimation: YOLOv8n-pose**

| **Library** | Ultralytics YOLOv8 - pip install ultralytics |
| ----------- | -------------------------------------------- |

| **Model** | yolov8n-pose.pt - nano variant, TensorRT-optimized for Jetson |
| --------- | ------------------------------------------------------------- |

| **Output** | 17 COCO keypoints per person: nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles + bounding box |
| ---------- | ------------------------------------------------------------------------------------------------------------- |

| **Expected FPS** | ~20-25 FPS on Jetson Orin Nano after TensorRT FP16 export |
| ---------------- | --------------------------------------------------------- |

Export command for TensorRT:

yolo export model=yolov8n-pose.pt format=engine half=True device=0

## **3.3 Stage 2 - Fall Classifier**

A sliding window of 15-20 frames of keypoints is fed into a lightweight temporal classifier. Two options are viable:

| **Option**      | **Architecture**                                                               | **Notes**                                                     |
| --------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| A (Recommended) | Rule-based: bounding box aspect ratio + hip keypoint Y-velocity over 10 frames | No training needed. Fast to implement. 90%+ accuracy on Le2i. |
| ---             | ---                                                                            | ---                                                           |
| B (ML-based)    | 2-layer LSTM on 17\*2=34 keypoint features, window=20 frames                   | Requires training on Le2i/URFD. Better for ambiguous poses.   |
| ---             | ---                                                                            | ---                                                           |

Start with Option A and upgrade to B if false positive rate is unacceptable. Research confirms both approaches work well on the standard datasets.

## **3.4 Fall Detection Rules (Option A)**

- Aspect ratio flip: if bbox width > bbox height and previously height > width → candidate fall
- Hip keypoint Y velocity: average downward velocity of left/right hip keypoints over 8 frames exceeds threshold (e.g. >15 px/frame)
- Post-fall stillness: person stays in fallen aspect ratio for >1.5 seconds → confirmed fall
- All three conditions AND-ed to minimize false positives (lying down vs. fallen)

## **3.5 Datasets for Training (Option B LSTM)**

| **Dataset**       | **Size**                    | **Source**            | **Notes**                                                         |
| ----------------- | --------------------------- | --------------------- | ----------------------------------------------------------------- |
| Le2i FDD          | 191 videos, 75,911 frames   | Public                | 4 scenes: home, office, coffee room, lecture room. Gold standard. |
| ---               | ---                         | ---                   | ---                                                               |
| URFD              | 30 falls, 40 ADL activities | Public                | Microsoft Kinect RGB + depth. Good for pose pre-training.         |
| ---               | ---                         | ---                   | ---                                                               |
| CAUCAFall         | 50 falls, 50 normal         | Public                | RGB only. Smaller but clean.                                      |
| ---               | ---                         | ---                   | ---                                                               |
| Roboflow Universe | 474+ annotated fall images  | universe.roboflow.com | Pre-labeled YOLOv8-pose format. Use for fine-tuning detector.     |
| ---               | ---                         | ---                   | ---                                                               |

## **3.6 GPS Coordinate Extraction on Distress**

When fall is confirmed by the classifier: query Pixhawk via MAVROS for current GPS coordinates → package as JSON alert → publish to ground server → ground server triggers Telegram bot message and pushes alert to React dashboard with lat/lng pin.

# **4\. ML Task 2: Crowd Density Estimation**

## **4.1 Why Not Pure Detection**

At drone altitude with 50+ people in frame, individual person detection degrades significantly (occlusion, small object size, overlapping bboxes). Density map regression models are purpose-built for this problem and are the industry standard.

## **4.2 Model: MobileCount**

| **Paper** | MobileCount: An Efficient Encoder-Decoder Framework for Real-Time Crowd Counting (Neurocomputing, 2020) |
| --------- | ------------------------------------------------------------------------------------------------------- |

| **GitHub** | github.com/ChenyuGAO-CS/MobileCount - Official implementation, MIT-adjacent license |
| ---------- | ----------------------------------------------------------------------------------- |

| **Backbone** | MobileNet - significantly lighter than VGG-16 based CSRNet |
| ------------ | ---------------------------------------------------------- |

| **Output** | Density map (same resolution as input). Sum of map = crowd count estimate. |
| ---------- | -------------------------------------------------------------------------- |

| **Why Not CSRNet** | CSRNet uses VGG-16 backbone - too heavy for Jetson real-time. MobileCount is purpose-built for edge deployment. |
| ------------------ | --------------------------------------------------------------------------------------------------------------- |

## **4.3 Alternative: LWCC Library**

| **Library** | lwcc - pip install lwcc (github.com/tersekmatija/lwcc) |
| ----------- | ------------------------------------------------------ |

LWCC is a pip-installable Python library with several pretrained state-of-the-art crowd counting models. Use this for fastest integration - no training needed, just inference. Recommended for prototype stage.

import lwcc count = lwcc.LWCC.get_count(image, model='CSRNet') # or 'SFANet', 'DM-Count'

## **4.4 Datasets for Density Model Training/Fine-tuning**

| **Dataset**         | **Images / Count**        | **Notes**                                               |
| ------------------- | ------------------------- | ------------------------------------------------------- |
| ShanghaiTech Part A | 482 images, 241,677 heads | Dense crowds. Pretrained MobileCount weights available. |
| ---                 | ---                       | ---                                                     |
| ShanghaiTech Part B | 716 images, 88,514 heads  | Sparser crowd, more outdoor scenes.                     |
| ---                 | ---                       | ---                                                     |
| UCF-CC-50           | 50 images, 63,974 heads   | Extreme density variation. Good for robustness testing. |
| ---                 | ---                       | ---                                                     |

For IDP: use pretrained ShanghaiTech weights directly. No training needed unless drone-perspective fine-tuning is required in later phases.

# **5\. ML Task 3: Crowd Anomaly Detection (Optical Flow)**

## **5.1 Approach**

Classical Farneback optical flow computed between consecutive frames. No ML model required - compute flow vector field, derive magnitude and divergence metrics per region.

## **5.2 Anomaly Heuristics**

- Normal crowd: low flow magnitude, consistent directional vectors
- Bottleneck / compression: high inward flow convergence at a point
- Panic / stampede: sudden spike in flow magnitude + divergence from a centroid
- Threshold tuning: calibrate magnitude and divergence thresholds on normal event footage

## **5.3 Implementation**

| **Library** | OpenCV - cv2.calcOpticalFlowFarneback() - built into Jetson OpenCV |
| ----------- | ------------------------------------------------------------------ |

flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None, pyr_scale=0.5, levels=3, winsize=15, iterations=3, poly_n=5, poly_sigma=1.2, flags=0) mag, ang = cv2.cartToPolar(flow\[...,0\], flow\[...,1\])

# **6\. ML Task 4: LSTM Crowd Density Forecasting**

## **6.1 Architecture**

A sequence-to-one (or sequence-to-sequence) LSTM that takes a rolling window of crowd count scalars or density map feature vectors and predicts crowd count N seconds ahead. This runs on the ground server, not onboard.

| **Parameter** | **Value**                                                                            |
| ------------- | ------------------------------------------------------------------------------------ |
| Input         | Rolling window of 30 timesteps of crowd count (scalar) or top-N density map features |
| ---           | ---                                                                                  |
| Architecture  | 2-layer LSTM, hidden_size=64, dropout=0.2, fully-connected output layer              |
| ---           | ---                                                                                  |
| Output        | Predicted crowd count for next 10/30/60 seconds (multi-horizon)                      |
| ---           | ---                                                                                  |
| Framework     | PyTorch - torch.nn.LSTM                                                              |
| ---           | ---                                                                                  |
| Training Data | Simulated data from dual-drone simulation + any event footage available              |
| ---           | ---                                                                                  |

# **7\. Complete Library Stack**

| **Library**         | **Install**                       | **Purpose**                                              |
| ------------------- | --------------------------------- | -------------------------------------------------------- |
| Ultralytics         | pip install ultralytics           | YOLOv8n-pose inference + TensorRT export                 |
| ---                 | ---                               | ---                                                      |
| LWCC                | pip install lwcc                  | Pretrained crowd counting - fastest path to density maps |
| ---                 | ---                               | ---                                                      |
| OpenCV              | Pre-installed on Jetson           | Farneback optical flow, image preprocessing              |
| ---                 | ---                               | ---                                                      |
| PyTorch             | Jetson-specific wheel from NVIDIA | LSTM forecaster training + inference                     |
| ---                 | ---                               | ---                                                      |
| pymavlink / MAVROS  | pip install pymavlink             | GPS coordinate retrieval from Pixhawk on distress event  |
| ---                 | ---                               | ---                                                      |
| FastAPI             | pip install fastapi uvicorn       | Ground server WebSocket API for dashboard                |
| ---                 | ---                               | ---                                                      |
| python-telegram-bot | pip install python-telegram-bot   | Telegram alert dispatch                                  |
| ---                 | ---                               | ---                                                      |

# **8\. Implementation Phases**

## **Phase 1 - Onboard Baseline (2 weeks)**

- Flash Jetson with JetPack 5.x
- Install PyTorch wheel from NVIDIA JetPack repo
- Install Ultralytics, run YOLOv8n-pose on webcam feed
- Export YOLOv8n-pose to TensorRT engine
- Implement rule-based fall detection (Option A) on keypoints
- Verify MAVLink GPS query via pymavlink over UART

## **Phase 2 - Density Pipeline (1 week)**

- Install lwcc, test CSRNet/SFANet pretrained inference on sample frames
- Implement Farneback optical flow + anomaly heuristics
- Integrate density count + anomaly flag into single output JSON

## **Phase 3 - Ground Server + Dashboard (2 weeks)**

- Build FastAPI WebSocket server receiving Jetson output over WiFi
- Set up LSTM forecaster (can use simulated data initially)
- Connect React dashboard: live density heatmap, alert feed, GPS map pin
- Integrate Telegram bot for distress alerts

## **Phase 4 - LSTM Training + Tuning (1 week)**

- Collect real or simulated density time-series data (min 1000 timesteps)
- Train 2-layer LSTM forecaster, validate on held-out sequence
- Deploy forecaster to ground server, display predictions on dashboard

# **9\. Known Risks & Mitigations**

| **Risk**                                             | **Mitigation**                                                 |
| ---------------------------------------------------- | -------------------------------------------------------------- |
| Jetson thermal throttling at sustained inference     | Add heatsink + fan. Run models at FP16. Monitor jetson_clocks. |
| ---                                                  | ---                                                            |
| Fall detection false positives (lying down, sitting) | Use 3-condition AND logic. Add stillness confirmation timer.   |
| ---                                                  | ---                                                            |
| Drone altitude affecting density map accuracy        | Calibrate LWCC/MobileCount at target altitude during testing.  |
| ---                                                  | ---                                                            |
| WiFi range insufficient for frame streaming          | Stream only processed JSON outputs. No raw video to server.    |
| ---                                                  | ---                                                            |
| GPS lag on distress trigger                          | Cache last GPS fix every 500ms. Use cached value for alert.    |
| ---                                                  | ---                                                            |

_- End of PRD 01 -_