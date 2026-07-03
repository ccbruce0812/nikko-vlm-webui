"""
Video display widget (5/6 width).
Shows live QImage frames with overlay support and system monitor stats.
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


class VideoDisplay(QWidget):
    """Widget that displays a QImage frame with optional overlays."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self._frame = None          # QImage
        self._overlay_frame = None  # QImage (annotated by overlay module)
        self._stats = {"gpu": 0, "cpu": 0, "ram": 0, "vram": 0}
        self._res_fps = "—"

    def set_frame(self, qimage: QImage):
        """Set the raw camera frame."""
        self._frame = qimage
        self.update()

    def set_overlay_frame(self, qimage: QImage):
        """Set the annotated frame (with YOLO boxes or VLM caption)."""
        self._overlay_frame = qimage
        self.update()

    def set_stats(self, stats: dict):
        """Update system monitor stats."""
        self._stats.update(stats)
        self.update()

    def set_res_fps(self, text: str):
        """Set resolution/FPS display string, e.g. '1920x1080@30'."""
        self._res_fps = text

    def current_frame(self) -> QImage:
        """Return the latest clean frame (for capture)."""
        return self._frame

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Fill background black
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        # Draw frame (annotated if available, else raw)
        image = self._overlay_frame if self._overlay_frame else self._frame
        if image and not image.isNull():
            scaled = image.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)

        # Draw system monitor overlay (top-right)
        self._draw_monitor(painter)

        painter.end()

    def _draw_monitor(self, painter):
        gpu = self._stats.get("gpu", 0)
        cpu = self._stats.get("cpu", 0)
        ram = self._stats.get("ram", 0)
        vram = self._stats.get("vram", 0)

        font = QFont("monospace", max(10, self.width() // 100))
        font.setBold(True)
        painter.setFont(font)

        text = f"{self._res_fps}  GPU:{gpu:.0f}% VRAM:{vram:.1f}G\nCPU:{cpu:.0f}% RAM:{ram:.1f}G"

        # Semi-transparent background
        fm = painter.fontMetrics()
        lines = text.split("\n")
        max_w = max(fm.horizontalAdvance(line) for line in lines)
        line_h = fm.height() + 2
        total_h = line_h * len(lines) + 6

        x = self.width() - max_w - 16
        y = 8
        painter.fillRect(x - 4, y, max_w + 8, total_h, QColor(0, 0, 0, 140))
        painter.setPen(Qt.white)
        painter.drawText(x, y + line_h - 4, text)
