#!/usr/bin/env bash
# ============================================================
# Install basic packages + DeepStream SDK 7.1 + pyds 1.2.0
# Reference: README.md → Prerequisites → 3. Install packages
# ============================================================
set -euo pipefail

echo "=== Verify nvidia-container-runtime ==="
sudo docker info 2>/dev/null | grep -i runtime || echo "⚠ Docker not installed or nvidia-container-runtime missing"

echo ""
echo "=== Install system packages ==="
sudo apt-get install -y python3-venv v4l-utils libxcb-cursor0 python3-pip
echo "✓ system packages installed"

# ---------- DeepStream SDK 7.1 + pyds 1.2.0 ----------
DS_TBZ=deepstream_sdk_v7.1.0_jetson.tbz2
DS_URL="https://api.ngc.nvidia.com/v2/resources/nvidia/deepstream/versions/7.1/files/${DS_TBZ}"
DS_DIR=/opt/nvidia/deepstream/deepstream-7.1
PYDS_URL="https://github.com/NVIDIA-AI-IOT/deepstream_python_apps/releases/download/v1.2.0/pyds-1.2.0-cp310-cp310-linux_aarch64.whl"

echo ""
echo "=== DeepStream dependencies ==="
sudo apt-get install -y gstreamer1.0-rtsp libyaml-cpp-dev

echo ""
echo "=== Download & install DeepStream SDK 7.1 ==="
wget --content-disposition "$DS_URL" -O /tmp/"$DS_TBZ"
sudo tar -xvf /tmp/"$DS_TBZ" -C /
rm -f /tmp/"$DS_TBZ"
cd "$DS_DIR"
sudo ./install.sh
sudo ldconfig
cd -

echo ""
echo "=== DeepStream env vars → ~/.bashrc ==="
if ! grep -q "DEEPSTREAM_DIR" ~/.bashrc; then
    cat >> ~/.bashrc << 'EOS'
# DeepStream 7.1
export DEEPSTREAM_DIR=/opt/nvidia/deepstream/deepstream-7.1
export PATH=$DEEPSTREAM_DIR/bin:$PATH
export LD_LIBRARY_PATH=$DEEPSTREAM_DIR/lib:$LD_LIBRARY_PATH
EOS
fi
export DEEPSTREAM_DIR="$DS_DIR"
export PATH="$DEEPSTREAM_DIR/bin:$PATH"
export LD_LIBRARY_PATH="$DEEPSTREAM_DIR/lib:$LD_LIBRARY_PATH"

echo ""
echo "=== Install pyds 1.2.0 ==="
python3 -m pip install "$PYDS_URL"

echo ""
echo "=== Verify ==="
echo "--- nvdsosd ---"
gst-inspect-1.0 nvdsosd 2>&1 | head -3
echo "--- pyds ---"
python3 -c "import pyds; print('pyds', pyds.__version__)"
echo ""
echo "✓ all deps installed"
