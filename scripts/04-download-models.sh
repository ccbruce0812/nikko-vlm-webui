#!/usr/bin/env bash
# ============================================================
# Download Reason2 + moondream2 + YOLO models (in venv)
# Reference: README.md → Model Download
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Create venv ==="
python3 -m venv /tmp/model-dl-venv
source /tmp/model-dl-venv/bin/activate
pip install -q huggingface_hub ultralytics onnx

echo ""
echo "=== Download Reason2 (IQ4_XS) ==="
mkdir -p models/reason2
cd models/reason2

echo "  → LLM (IQ4_XS, ~970MB)"
hf download mradermacher/Cosmos-Reason2-2B-heretic-GGUF \
    Cosmos-Reason2-2B-heretic.IQ4_XS.gguf --local-dir .

echo "  → mmproj (F16, ~782MB)"
hf download apolo13x/Cosmos-Reason2-2B-GGUF \
    mmproj-Cosmos-Reason2-2B-F16.gguf --local-dir .

cd "$PROJECT_ROOT"

echo ""
echo "=== Download moondream2 (q4_k) ==="
mkdir -p models/moondream2
cd models/moondream2

hf download salivosa/moondream2-gguf \
    moondream2-q4_k.gguf moondream2-mmproj-f16.gguf --local-dir .

cd "$PROJECT_ROOT"

echo ""
echo "=== Download YOLOv8n ==="
mkdir -p models/yolo
cd models/yolo

echo "  → Download YOLOv8n PyTorch model (~6.5MB)"
python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')  # downloads to current dir
print('Downloaded yolov8n.pt')
"
# TensorRT engine is generated inside Docker at first inference

cd "$PROJECT_ROOT"

echo ""
echo "=== Clean up venv ==="
deactivate
rm -rf /tmp/model-dl-venv

echo ""
echo "=== Models downloaded ==="
echo "Reason2:"
ls -lh models/reason2/
echo ""
echo "moondream2:"
ls -lh models/moondream2/
echo ""
echo "YOLO:"
ls -lh models/yolo/
