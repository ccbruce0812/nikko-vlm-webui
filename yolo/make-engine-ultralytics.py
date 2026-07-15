#!/usr/bin/env python3
"""
Export YOLO .pt → TensorRT .engine (via ultralytics).

Usage (inside yolo docker):
  python3 make-engine-ultralytics.py /model/yolov8n.pt
  python3 make-engine-ultralytics.py /model/yolov8n.pt --onnx /model/yolov8n-ultralytics.onnx --engine /model/yolov8n-ultralytics.engine
"""
import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [engine] %(message)s")
logger = logging.getLogger("engine")


def main():
    p = argparse.ArgumentParser(
        description="Export YOLO .pt → TensorRT .engine via ultralytics")
    p.add_argument("pt", help="Input .pt model file")
    p.add_argument("--onnx", default=None, help="Output .onnx path (default: same as .pt)")
    p.add_argument("--engine", default=None, help="Output .engine path (default: same as .pt)")
    args = p.parse_args()

    if not os.path.exists(args.pt):
        sys.exit(f"✗ .pt not found: {args.pt}")

    pt_dir = os.path.dirname(args.pt) or "."
    pt_base = os.path.splitext(os.path.basename(args.pt))[0]
    onnx_path = args.onnx or os.path.join(pt_dir, pt_base + ".onnx")
    engine_path = args.engine or os.path.join(pt_dir, pt_base + ".engine")

    from ultralytics import YOLO
    logger.info("Exporting %s", args.pt)
    model = YOLO(args.pt)
    model.export(format="engine", half=True, device=0, workspace=4)

    # ultralytics auto-generates .onnx and .engine in same dir as .pt
    auto_onnx = os.path.join(pt_dir, pt_base + ".onnx")
    auto_engine = os.path.join(pt_dir, pt_base + ".engine")

    if os.path.abspath(auto_onnx) != os.path.abspath(onnx_path):
        os.rename(auto_onnx, onnx_path)
        logger.info("✓ ONNX: %s", onnx_path)

    if os.path.abspath(auto_engine) != os.path.abspath(engine_path):
        os.rename(auto_engine, engine_path)
        logger.info("✓ Engine: %s", engine_path)

    print(f"Done: {engine_path}")


if __name__ == "__main__":
    main()
