from ultralytics import YOLO
import os
import urllib.request

os.makedirs('D:/IDP/crowd-monitoring-ml/models', exist_ok=True)
os.chdir('D:/IDP/crowd-monitoring-ml/models')

print("=" * 60)
print("Downloading ML Models for Crowd Monitoring")
print("=" * 60)

# Download YOLOv8n-pose
print("\n[1/2] Downloading YOLOv8n-pose...")
try:
    model = YOLO('yolov8n-pose.pt')
    yolo_path = os.path.abspath('yolov8n-pose.pt')
    print(f"✓ Downloaded YOLOv8n-pose to: {yolo_path}")
    print(f"  File size: {os.path.getsize(yolo_path) / (1024*1024):.2f} MB")
except Exception as e:
    print(f"✗ Failed to download YOLOv8n-pose: {e}")
    yolo_path = None

# Download crowd counting model (CSRNet pretrained on ShanghaiTech)
print("\n[2/2] Downloading crowd counting model...")
print("Note: Using CSRNet model (pretrained on ShanghaiTech dataset)")
print("MobileCount requires specific training. Using CSRNet as alternative.")

crowd_model_url = "https://github.com/leeyeehoo/CSRNet-pytorch/releases/download/v1.0/csrnet_shanghaitech_partA.pth"
crowd_model_path = os.path.abspath('csrnet_shanghaitech.pth')

try:
    print(f"  Downloading from: {crowd_model_url}")
    urllib.request.urlretrieve(crowd_model_url, crowd_model_path)
    print(f"✓ Downloaded CSRNet model to: {crowd_model_path}")
    print(f"  File size: {os.path.getsize(crowd_model_path) / (1024*1024):.2f} MB")
except Exception as e:
    print(f"✗ Failed to download CSRNet model: {e}")
    print("  You may need to train a custom model or find alternative pretrained weights")
    crowd_model_path = None

print("\n" + "=" * 60)
print("Download Summary")
print("=" * 60)

if yolo_path:
    print(f"✓ YOLOv8n-pose: {yolo_path}")
else:
    print("✗ YOLOv8n-pose: Download failed")

if crowd_model_path:
    print(f"✓ Crowd counting model: {crowd_model_path}")
else:
    print("✗ Crowd counting model: Download failed")

print("\nAll models saved to: D:\\IDP\\crowd-monitoring-ml\\models\\")
print("=" * 60)
