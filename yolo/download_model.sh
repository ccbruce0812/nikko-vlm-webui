#!/bin/bash
# Download YOLOv8n and export to TensorRT engine
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; DEST="$SCRIPT_DIR/../models/yolo"
mkdir -p "$DEST"

# Download PyTorch model
if [ ! -f "$DEST/yolov8n.pt" ]; then
    echo "=== Downloading YOLOv8n ==="
    python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
import shutil
shutil.move('yolov8n.pt', '$DEST/yolov8n.pt')
print('Downloaded yolov8n.pt')
"
fi

# Export to TensorRT (on Jetson GPU)
if [ ! -f "$DEST/yolov8n.engine" ]; then
    echo "=== Exporting to TensorRT (FP16) ==="
    python3 -c "
from ultralytics import YOLO
model = YOLO('$DEST/yolov8n.pt')
model.export(format='engine', device=0, half=True, imgsz=640)
import shutil
shutil.move('yolov8n.engine', '$DEST/yolov8n.engine')
print('TensorRT engine exported')
"
fi

echo "=== Done ==="
ls -lh "$DEST"
