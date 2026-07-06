"""
YOLO overlay: parses detection JSON from router response and draws
colored bounding boxes with class labels and confidence scores.
"""
import json
import logging
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QBuffer, QIODevice
import base64

INFER_MAX_DIM = 1280

logger = logging.getLogger(__name__)

# Distinct colors for common COCO classes
CLASS_COLORS = {
    "person": QColor(0, 255, 0),
    "car": QColor(255, 0, 0),
    "bus": QColor(0, 0, 255),
    "truck": QColor(255, 165, 0),
    "bicycle": QColor(255, 255, 0),
    "motorcycle": QColor(128, 0, 128),
    "traffic light": QColor(255, 192, 203),
    "stop sign": QColor(139, 0, 0),
}
FALLBACK_COLOR = QColor(0, 255, 255)


def draw_overlay(qimage: QImage, response_text: str) -> QImage:
    """Parse YOLO JSON and draw bounding boxes. Returns annotated QImage."""
    result = qimage.copy()

    text = response_text.strip()
    if not text or text.lower() in ("no objects detected.", "no objects detected"):
        return result

    try:
        detections = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("YOLO response is not valid JSON: %s", text[:100])
        return result

    if not detections:
        return result

    painter = QPainter(result)
    font = QFont("monospace", max(14, qimage.width() // 60))
    font.setBold(True)
    painter.setFont(font)
    fm = painter.fontMetrics()
    label_h = fm.height() + 4

    # Scale bbox from inference resolution back to display resolution
    max_dim = max(qimage.width(), qimage.height())
    if max_dim > INFER_MAX_DIM:
        scale = max_dim / INFER_MAX_DIM
    else:
        scale = 1.0

    for det in detections:
        name = det.get("name", det.get("class", "?"))
        conf = det.get("confidence", 0)
        bbox = det.get("bbox", [0, 0, 0, 0])
        x1, y1, x2, y2 = [int(v * scale) for v in bbox]

        color = CLASS_COLORS.get(name, FALLBACK_COLOR)
        pen = QPen(color, max(2, qimage.width() // 400))
        painter.setPen(pen)
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        label = f"{name} {conf:.2f}"
        tw = fm.horizontalAdvance(label) + 6
        painter.fillRect(x1, y1, tw, label_h, color)
        painter.setPen(Qt.black)
        painter.drawText(x1 + 3, y1 + fm.ascent() + 2, label)

    painter.end()
    return result


def prepare_payload(frame: QImage, prompt: str, max_tokens: int) -> str:
    """Resize, JPEG-encode, build Router API JSON payload for YOLO.
       (prompt is ignored; YOLO always uses 'Detect objects'.)"""
    max_dim = max(frame.width(), frame.height())
    if max_dim > INFER_MAX_DIM:
        scale = INFER_MAX_DIM / max_dim
        frame = frame.scaled(int(frame.width() * scale), int(frame.height() * scale))
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    frame.save(buf, "JPEG", quality=85)
    image_b64 = base64.b64encode(buf.data()).decode()
    buf.close()
    return json.dumps({
        "model": "yolo",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Detect objects"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]
        }],
        "max_tokens": max_tokens,
    })
