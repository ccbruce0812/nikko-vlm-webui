#!/usr/bin/env python3
"""YOLO inference server with OpenAI-compatible API. TensorRT preferred, PyTorch fallback."""
import base64, io, json, os, time, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [yolo] %(message)s")
logger = logging.getLogger("yolo")

ENGINE_PATH = "/model/yolov8n.engine"
PT_PATH = "/model/yolov8n.pt"

model = None
engine_type = "PyTorch"


def load_model():
    """Try TensorRT engine first, fall back to PyTorch."""
    global model, engine_type
    if os.path.exists(ENGINE_PATH):
        from ultralytics import YOLO
        model = YOLO(ENGINE_PATH)
        engine_type = "TensorRT"
        logger.info(f"Loaded TensorRT engine: {ENGINE_PATH}")
    else:
        from ultralytics import YOLO
        model = YOLO(PT_PATH)
        engine_type = "PyTorch"
        logger.info(f"Loaded PyTorch model: {PT_PATH} (TensorRT engine not found, build with EXPORT_ENGINE=1)")


def export_engine():
    """Export model to TensorRT and exit."""
    from ultralytics import YOLO
    logger.info(f"Loading PyTorch model for export: {PT_PATH}")
    m = YOLO(PT_PATH)
    logger.info("Exporting to TensorRT... (this may take several minutes)")
    m.export(format="engine", half=True, device=0, workspace=4)
    logger.info(f"TensorRT engine saved to {ENGINE_PATH}")
    logger.info("Export complete. Restart without EXPORT_ENGINE to use it.")


class YOLOHandler:
    """HTTP request handler for YOLO inference."""
    def __init__(self, request, client_address, server):
        from http.server import BaseHTTPRequestHandler
        # ... using function-based server instead

    def log_message(self, fmt, *args):
        logger.info(f"{self.client_address[0]} - {fmt % args}")


def create_app():
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
                return self._send_json({"status": "ok", "model": PT_PATH, "engine": engine_type})
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
                messages = body.get("messages", [])
                image_b64 = None
                for msg in messages:
                    if isinstance(msg.get("content"), list):
                        for part in msg["content"]:
                            if part.get("type") == "image_url":
                                url = part["image_url"]["url"]
                                if url.startswith("data:image"):
                                    image_b64 = url.split(",", 1)[1]

                if not image_b64:
                    return self._send_json({"error": "no image in request"}, 400)

                img_bytes = base64.b64decode(image_b64)
                img = __import__("PIL.Image").Image.open(io.BytesIO(img_bytes))

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

                result_text = json.dumps(detections, indent=2) if detections else "No objects detected."
                n = len(detections)
                logger.info(f"[{engine_type}] {n} objects in {elapsed*1000:.0f}ms")

                return self._send_json({
                    "id": "yolo-" + str(int(time.time())),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": "yolo",
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": result_text},
                        "finish_reason": "stop",
                    }],
                    "usage": {"engine": engine_type, "latency_ms": round(elapsed * 1000, 1)},
                })
            except Exception as e:
                logger.error(f"Error: {e}")
                return self._send_json({"error": str(e)}, 500)

    return HTTPServer(("0.0.0.0", 8003), Handler)


if __name__ == "__main__":
    if os.environ.get("EXPORT_ENGINE") == "1":
        export_engine()
    else:
        load_model()
        logger.info(f"Model loaded ({engine_type}). Starting server on :8003")
        server = create_app()
        server.serve_forever()
