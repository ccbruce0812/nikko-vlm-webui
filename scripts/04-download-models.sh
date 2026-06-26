#!/usr/bin/env bash
# ============================================================
# 下載 Cosmos-Reason2 + moondream2 + YOLO 模型
# 對應 README.md → 模型下載
# ============================================================
set -euo pipefail

echo "=== 下載 Cosmos-Reason2 (IQ4_XS 量化) ==="
mkdir -p ~/project/models/cosmos-reason2
cd ~/project/models/cosmos-reason2

echo "  → LLM (IQ4_XS, ~970MB)"
hf download mradermacher/Cosmos-Reason2-2B-heretic-GGUF \
    Cosmos-Reason2-2B-heretic.IQ4_XS.gguf --local-dir .

echo "  → mmproj (F16, ~782MB)"
hf download apolo13x/Cosmos-Reason2-2B-GGUF \
    mmproj-Cosmos-Reason2-2B-F16.gguf --local-dir .

echo ""
echo "=== 下載 moondream2 (q4_k 量化) ==="
mkdir -p ~/project/models/moondream2
cd ~/project/models/moondream2

hf download salivosa/moondream2-gguf \
    moondream2-q4_k.gguf moondream2-mmproj-f16.gguf --local-dir .

echo ""
echo "=== 下載 YOLOv8n + 匯出 TensorRT ==="
mkdir -p ~/project/models/yolo
cd ~/project/models/yolo

echo "  → 下載 YOLOv8n PyTorch 模型 (~6.5MB)"
python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
import shutil
shutil.move('yolov8n.pt', '.')
print('Downloaded yolov8n.pt')
"

echo "  → 匯出 TensorRT engine (FP16, 需 GPU, ~13MB)"
python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.export(format='engine', device=0, half=True, imgsz=640)
import shutil
shutil.move('yolov8n.engine', '.')
print('TensorRT engine exported')
"

echo ""
echo "=== 模型下載完成 ==="
echo "Cosmos-Reason2:"
ls -lh ~/project/models/cosmos-reason2/
echo ""
echo "moondream2:"
ls -lh ~/project/models/moondream2/
echo ""
echo "YOLO:"
ls -lh ~/project/models/yolo/
