#!/bin/bash
# Jetson Orin Nano Setup Script
# JetPack 6.0 (R36.4.4)
# Run this on Jetson via SSH

set -e  # Exit on error

echo "======================================"
echo "JETSON ORIN NANO - SETUP SCRIPT"
echo "======================================"
echo ""

# System info
echo "=== System Information ==="
echo "Python: $(python3 --version)"
cat /etc/nv_tegra_release 2>/dev/null || echo "Tegra release info not found"
echo ""

# Update system
echo "=== Updating System ==="
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev python3-venv
sudo apt-get install -y libopenblas-base libopenmpi-dev libomp-dev
sudo apt-get install -y git wget curl
echo "✓ System updated"
echo ""

# Upgrade pip
echo "=== Upgrading pip ==="
pip3 install --upgrade pip
echo "✓ pip upgraded"
echo ""

# Install PyTorch for JetPack 6.0
echo "=== Installing PyTorch for JetPack 6.0 ==="
pip3 install numpy==1.26.0

# Try standard PyTorch first
echo "Attempting standard PyTorch installation..."
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 || {
    echo "Standard install failed, trying NVIDIA wheel..."
    # Fallback to NVIDIA pre-built wheel
    wget https://developer.download.nvidia.com/compute/redist/jp/v60/pytorch/torch-2.1.0a0+41361538.nv23.06-cp310-cp310-linux_aarch64.whl -O /tmp/torch.whl
    pip3 install /tmp/torch.whl
    rm /tmp/torch.whl
}
echo "✓ PyTorch installed"
echo ""

# Install Ultralytics YOLO
echo "=== Installing Ultralytics YOLO ==="
pip3 install ultralytics
echo "✓ Ultralytics installed"
echo ""

# Install OpenCV
echo "=== Installing OpenCV ==="
pip3 install opencv-python
echo "✓ OpenCV installed"
echo ""

# Install other dependencies
echo "=== Installing Other Dependencies ==="
pip3 install pymavlink scipy pyyaml
pip3 install websocket-client  # For server communication
echo "✓ Dependencies installed"
echo ""

# Verify installation
echo "=== Verification ==="
python3 << 'EOF'
import sys

print("Checking installations...")

try:
    import torch
    print(f"✓ PyTorch {torch.__version__}")
    print(f"  CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  CUDA device: {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"✗ PyTorch: {e}")
    sys.exit(1)

try:
    import cv2
    print(f"✓ OpenCV {cv2.__version__}")
except Exception as e:
    print(f"✗ OpenCV: {e}")
    sys.exit(1)

try:
    from ultralytics import YOLO
    print("✓ Ultralytics YOLO")
except Exception as e:
    print(f"✗ Ultralytics: {e}")
    sys.exit(1)

try:
    import pymavlink
    print("✓ pymavlink")
except Exception as e:
    print(f"✗ pymavlink: {e}")

try:
    import numpy as np
    print(f"✓ NumPy {np.__version__}")
except Exception as e:
    print(f"✗ NumPy: {e}")
    sys.exit(1)

print("\n✓ All core dependencies verified!")
EOF

echo ""
echo "======================================"
echo "✓ JETSON SETUP COMPLETE!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Transfer crowd-monitoring-ml/jetson folder to Jetson"
echo "2. Download YOLO model: python3 -c \"from ultralytics import YOLO; YOLO('yolov8n-pose.pt')\""
echo "3. Test camera: python3 -c \"import cv2; cap = cv2.VideoCapture(0); print('Camera:', cap.isOpened()); cap.release()\""
echo "4. Run pipeline: cd jetson && python3 inference_pipeline.py"
echo ""
