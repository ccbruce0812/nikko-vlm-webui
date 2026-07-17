#!/bin/bash
# ============================================================
# 09-install-pyside6-gui.sh
# Create Python venv and install PySide6 + aiohttp for the
# kiosk VLM GUI and headless validation tool.
#
# Usage:
#   bash scripts/09-install-pyside6-gui.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/pyside6-gui-venv"

# ---- DeepStream env vars + display blanking → ~/.bashrc ----
if ! grep -q "DEEPSTREAM_DIR" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'EOS'
# DeepStream 7.1
export DEEPSTREAM_DIR=/opt/nvidia/deepstream/deepstream-7.1
export PATH=$DEEPSTREAM_DIR/bin:$PATH
export LD_LIBRARY_PATH=$DEEPSTREAM_DIR/lib:$LD_LIBRARY_PATH

# Disable screen blanking for kiosk
export DISPLAY=:0
xset s off -dpms
EOS
fi
export DEEPSTREAM_DIR=/opt/nvidia/deepstream/deepstream-7.1
export PATH="$DEEPSTREAM_DIR/bin:$PATH"
export LD_LIBRARY_PATH="$DEEPSTREAM_DIR/lib:${LD_LIBRARY_PATH:-}"

# Apply immediately (in addition to .bashrc for persistence)
export DISPLAY=:0
xset s off -dpms 2>/dev/null || true

echo ""
echo "=== Remove artifacts ==="
rm -f models/yolo/*.engine
rm -f models/yolo/*.onnx
rm -f pyside6-gui/assets/*.so
echo "✓ Artifacts removed"

echo ""
echo "=== Build & install CUDA parser .so ==="
CUDA_VER=12.6 make -C yolo/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo clean
CUDA_VER=12.6 make -C yolo/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo
cp yolo/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so \
   pyside6-gui/assets/
echo "✓ CUDA parser installed"

echo ""
echo "=== Export DeepStream-compatible ONNX (via yolo docker) ==="
if sudo docker image inspect yolo >/dev/null 2>&1; then
    sudo docker run --rm --runtime nvidia \
        -v "$(readlink -f models/yolo):/model" \
        yolo python3 make-onnx-deepstream.py \
        --weights /model/yolov8n.pt --dynamic \
        --onnx /model/yolov8n.deepstream.onnx
    echo "✓ DeepStream ONNX exported"
else
    echo "⚠ yolo docker image not found — skip ONNX export"
fi

echo ""
echo "=== Build TensorRT engine (via deepstream-app) ==="
deepstream-app -c pyside6-gui/assets/app-config.txt &
DS_PID=$!
echo "  Waiting for engine file..."
until [ -f model_b1_gpu0_fp16.engine ]; do sleep 1; done
sleep 5
kill -2 $DS_PID 2>/dev/null || true
wait $DS_PID 2>/dev/null || true

echo ""
echo "=== Move engine to models/yolo/ ==="
mv model_b1_gpu0_fp16.engine models/yolo/yolov8n.deepstream.engine
echo "✓ Engine: models/yolo/yolov8n.deepstream.engine"

echo ""
echo "=== Export YOLO to TensorRT (ultralytics engine for HTTP YOLO container) ==="
if sudo docker image inspect yolo >/dev/null 2>&1; then
    sudo docker run --rm --runtime nvidia \
        -v "$(readlink -f models/yolo):/model" \
        yolo python3 make-engine-ultralytics.py \
        /model/yolov8n.pt \
        --onnx /model/yolov8n-ultralytics.onnx \
        --engine /model/yolov8n-ultralytics.engine
    echo "✓ Ultralytics engine exported"
else
    echo "⚠ yolo docker image not found — skip"
fi

echo "=== Create Python venv (--system-site-packages) ==="
rm -rf "${VENV_DIR}"
python3 -m venv --system-site-packages "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

pip install --upgrade pip setuptools wheel
pip install pyside6 aiohttp

echo ""
echo "Python: $(python3 --version)"
echo "pip:    $(pip --version)"
echo "venv:   ${VENV_DIR}"
echo ""
echo "✓ pyside6-gui venv ready"
echo "  source ${VENV_DIR}/bin/activate"
