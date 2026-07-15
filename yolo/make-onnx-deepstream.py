#!/usr/bin/env python3
"""
Wrapper around DeepStream-Yolo export_yoloV8.py — DeepStream-compatible ONNX export.
Adds --onnx flag for renaming output.

Usage:
  python3 make-onnx-deepstream.py --weights /model/yolov8n.pt
  python3 make-onnx-deepstream.py --weights /model/yolov8n.pt --onnx /model/yolov8n-ds.onnx --opset 12
"""
import argparse
import os
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(
        description="DeepStream-compatible YOLOv8 ONNX export")
    p.add_argument("--onnx", default=None, help="Rename output ONNX to this path")
    p.add_argument("--weights", required=True, help="Input .pt model")
    known, _ = p.parse_known_args()

    if not os.path.exists(known.weights):
        sys.exit(f"✗ weights not found: {known.weights}")

    # Forward all args except --onnx to export_yoloV8.py
    script = os.path.join(os.path.dirname(__file__),
                          "DeepStream-Yolo/utils/export_yoloV8.py")
    forward = [sys.executable, script]
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--onnx":
            i += 2  # skip --onnx VALUE
        else:
            forward.append(sys.argv[i])
            i += 1

    subprocess.run(forward, check=True)

    # Rename auto-generated ONNX if --onnx given
    if known.onnx:
        auto = os.path.splitext(known.weights)[0] + ".onnx"
        if os.path.abspath(auto) != os.path.abspath(known.onnx):
            os.rename(auto, known.onnx)
            print(f"✓ Renamed {auto} → {known.onnx}")


if __name__ == "__main__":
    main()
