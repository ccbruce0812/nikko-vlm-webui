#!/usr/bin/env python3
"""Convert first .pt model in /model to TensorRT .engine."""
import argparse, glob, logging, os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [engine] %(message)s")
logger = logging.getLogger("engine")

MODEL_DIR = "/model"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert first .pt model in /model to TensorRT .engine")
    parser.parse_args()

    pts = sorted(glob.glob(f"{MODEL_DIR}/*.pt"))
    if not pts:
        raise FileNotFoundError(f"No .pt found in {MODEL_DIR}")

    pt_path = pts[0]
    engine_path = os.path.splitext(pt_path)[0] + ".engine"

    from ultralytics import YOLO
    logger.info(f"Loading: {pt_path}")
    model = YOLO(pt_path)
    logger.info("Exporting to TensorRT... (this may take several minutes)")
    model.export(format="engine", half=True, device=0, workspace=4)
    logger.info(f"Exported: {engine_path}")
    print(f"Done: {engine_path}")
