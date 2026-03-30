#!/usr/bin/env bash
# Jetson Orin Nano Setup Script - With Virtual Environment
# JetPack 6.0 (R36.4.4)
# Run this on Jetson via SSH

set -euo pipefail  # Exit on error, undefined vars, pipe failures

echo "======================================"
echo "JETSON ORIN NANO - SETUP SCRIPT"
echo "WITH VIRTUAL ENVIRONMENT"
echo "======================================"
echo ""

# System info
echo "=== System Information ==="
echo "Python: $(python3 --version)"
cat /etc/nv_tegra_release 2>/dev/null || echo "Tegra release info not found"
echo ""

# Update system
echo "=== Updating System ==="
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-dev python3-venv
sudo apt-get install -y libopenblas-base libopenmpi-dev libomp-dev
sudo apt-get install -y git wget curl
echo "✓ System updated"
echo ""

# Create project directory
PROJ_DIR="$HOME/crowd-monitoring"
mkdir -p "$PROJ_DIR"
cd "$PROJ_DIR"
echo "✓ Project directory: $PROJ_DIR"
echo ""

# Try to install uv (fast package manager), fallback to venv
echo "=== Setting Up Python Environment ==="
USE_UV=false

if command -v uv &> /dev/null; then
    echo "✓ uv already installed"
    USE_UV=true
elif curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null; then
    echo "✓ uv installed successfully"
    export PATH="$HOME/.cargo/bin:$PATH"
    USE_UV=true
else
    echo "⚠ uv not available, using standard venv (slower but reliable)"
    USE_UV=false
fi
echo ""

# Create virtual environment
if [ "$USE_UV" = true ]; then
    echo "=== Creating uv Virtual Environment ==="
    uv venv .venv
    source .venv/bin/activate
    echo "✓ uv venv activated at $PROJ_DIR/.venv"
else
    echo "=== Creating Python Virtual Environment ==="
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip setuptools wheel
    echo "✓ venv activated at $PROJ_DIR/.venv"
fi
echo ""

# Function to install packages
install_pkg() {
    if [ "$USE_UV" = true ]; then
        uv pip install "$@"
    else
        pip install "$@"
    fi
}

# Install numpy first (required for PyTorch)
echo "=== Installing numpy ==="
install_pkg numpy==1.26.0
echo "✓ numpy installed"
echo ""

# Install PyTorch for JetPack 6.0
echo "=== Installing PyTorch for JetPack 6.0 ==="
echo "Attempting standard PyTorch installation..."
if install_pkg torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 2>/dev/null; then
    echo "✓ Standard PyTorch installed"
else
    echo "Standard install failed, trying NVIDIA wheel..."
    wget https://developer.download.nvidia.com/compute/redist/jp/v60/pytorch/torch-2.1.0a0+41361538.nv23.06-cp310-cp310-linux_aarch64.whl -O /tmp/torch.whl
    install_pkg /tmp/torch.whl
    rm /tmp/torch.whl
    echo "✓ NVIDIA PyTorch wheel installed"
fi
echo ""

# Install Ultralytics YOLO
echo "=== Installing Ultralytics YOLO ==="
install_pkg ultralytics
echo "✓ Ultralytics installed"
echo ""

# Install OpenCV
echo "=== Installing OpenCV ==="
install_pkg opencv-python
echo "✓ OpenCV installed"
echo ""

# Install other dependencies
echo "=== Installing Other Dependencies ==="
install_pkg pymavlink scipy pyyaml websocket-client
echo "✓ Dependencies installed"
echo ""

# Create activation script
cat > activate_env.sh << 'ACTIVATE_EOF'
#!/bin/bash
# Activate the crowd-monitoring virtual environment
source "$HOME/crowd-monitoring/.venv/bin/activate"
echo "✓ Virtual environment activated"
echo "To deactivate, run: deactivate"
ACTIVATE_EOF
chmod +x activate_env.sh
echo "✓ Created activation script: $PROJ_DIR/activate_env.sh"
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
echo "📁 Installation location: $PROJ_DIR"
echo "🐍 Virtual environment: $PROJ_DIR/.venv"
echo ""
echo "⚡ To activate the environment in future sessions:"
echo "   source $PROJ_DIR/.venv/bin/activate"
echo "   # OR use the helper script:"
echo "   source $PROJ_DIR/activate_env.sh"
echo ""
echo "Next steps:"
echo "1. Transfer code: scp -r jetson/ models/ jatayu@10.58.30.240:~/crowd-monitoring/"
echo "2. Test camera: python3 -c \"import cv2; cap = cv2.VideoCapture(0); print('Camera:', cap.isOpened()); cap.release()\""
echo "3. Run pipeline: cd jetson && python3 inference_pipeline.py"
echo ""
