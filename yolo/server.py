#!/usr/bin/env python3
"""YOLO inference server. Reads /model (first .engine, else first .pt)."""
import argparse, base64, glob, io, json, os, time, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [yolo] %(message)s")
logger = logging.getLogger("yolo")

MODEL_DIR = "/model"


def find_model():
    engines = sorted(glob.glob(f"{MODEL_DIR}/*.engine"))
    if engines:
        return engines[0], "TensorRT"
    pts = sorted(glob.glob(f"{MODEL_DIR}/*.pt"))
    if pts:
        return pts[0], "PyTorch"
    raise FileNotFoundError(f"No .engine or .pt found in {MODEL_DIR}")


def create_app(model, engine_type, port):
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logger.info(f"{self.client_address[0]} - {fmt % args}")

        def _send_json(self, data, status=200):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                return self._send_json({"status": "ok", "engine": engine_type})
            if self.path == "/v1/models":
                return self._send_json({
                    "object": "list",
                    "data": [{"id": "yolo", "object": "model", "owned_by": "jetson", "engine": engine_type}]
                })
            self._send_json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                return self._send_json({"error": "not found"}, 404)
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
            except Exception as e:
                return self._send_json({"error": str(e)}, 400)
            try:
                start = time.time()
                image_b64 = None
                for msg in body.get("messages", []):
                    if isinstance(msg.get("content"), list):
                        for part in msg["content"]:
                            if part.get("type") == "image_url":
                                url = part["image_url"]["url"]
                                if url.startswith("data:image"):
                                    image_b64 = url.split(",", 1)[1]
                if not image_b64:
                    return self._send_json({"error": "no image in request"}, 400)
                img = __import__("PIL.Image").Image.open(io.BytesIO(base64.b64decode(image_b64)))
                results = model(img)
                elapsed = time.time() - start
                detections = []
                for r in results:
                    for box in r.boxes:
                        detections.append({
                            "class": int(box.cls[0]),
                            "name": model.names[int(box.cls[0])],
                            "confidence": round(float(box.conf[0]), 4),
                            "bbox": [round(x, 1) for x in box.xyxy[0].tolist()],
                        })
                text = json.dumps(detections, indent=2) if detections else "No objects detected."
                logger.info(f"[{engine_type}] {len(detections)} objects in {elapsed*1000:.0f}ms")
                return self._send_json({
                    "id": "yolo-" + str(int(time.time())),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": "yolo",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                    "usage": {"engine": engine_type, "latency_ms": round(elapsed * 1000, 1)},
                })
            except Exception as e:
                logger.error(f"Error: {e}")
                return self._send_json({"error": str(e)}, 500)

    return HTTPServer(("0.0.0.0", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO inference server. Reads models from /model.")
    parser.add_argument("--port", type=int, default=8003, help="listen port (default: 8003)")
    args = parser.parse_args()

    model_path, engine_type = find_model()
    from ultralytics import YOLO
    model = YOLO(model_path)
    logger.info(f"Loaded {engine_type}: {model_path}")
    logger.info(f"Starting server on :{args.port}")
    server = create_app(model, engine_type, args.port)
    server.serve_forever()
