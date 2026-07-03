"""
Reason2 overlay: draws a semi-transparent black bar at the image bottom
with the inference response text as a caption.
"""
from PySide6.QtGui import QImage, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QBuffer, QIODevice
import base64

INFER_MAX_DIM = 1280


def _draw_caption(qimage: QImage, text: str) -> QImage:
    result = qimage.copy()
    if not text:
        return result

    w, h = result.width(), result.height()
    painter = QPainter(result)

    font_size = max(12, w // 60)
    font = QFont("monospace", font_size)
    painter.setFont(font)

    metrics = painter.fontMetrics()
    text_width = metrics.horizontalAdvance(text)
    lines_needed = max(1, text_width // (w - 20) + 1)
    bar_height = (metrics.height() + 4) * lines_needed + 12

    painter.fillRect(0, h - bar_height, w, bar_height, QColor(0, 0, 0, 160))
    painter.setPen(Qt.white)
    painter.drawText(10, h - bar_height, w - 20, bar_height,
                     Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, text)

    painter.end()
    return result


def draw_overlay(qimage: QImage, response_text: str) -> QImage:
    """Draw semi-transparent caption bar with Reason2 response."""
    return _draw_caption(qimage, response_text)


def prepare_payload(frame: QImage, prompt: str, max_tokens: int) -> str:
    """Resize, JPEG-encode, build Router API JSON payload for Reason2."""
    import json
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
        "model": "reason2",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]
        }],
        "max_tokens": max_tokens,
    })
