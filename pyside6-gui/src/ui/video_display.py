"""
Video display widget (3/5 width).
Shows live QImage frames centered with aspect ratio, plus overlay text and system monitor.
"""
from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QFont, QImage
from PySide6.QtCore import Qt


class VideoDisplay(QWidget):
    """Widget that displays a QImage frame centered with KeepAspectRatio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._frame = None
        self._overlay_text = ""
        self._img_rect = None  # last scaled image rect for caption positioning
        self._stats = {"gpu": 0, "cpu": 0, "ram": 0}
        self._res_fps = "—"

    # ---- aspect ratio ----

    def _aspect_ratio(self):
        img = self._frame
        if img and not img.isNull():
            w, h = img.width(), img.height()
            if h > 0:
                return w / h
        return 16.0 / 9.0

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return int(w / self._aspect_ratio())

    # ---- input ----

    def set_frame(self, qimage: QImage):
        self._frame = qimage
        self.updateGeometry()
        self.update()

    def set_overlay_text(self, text: str):
        self._overlay_text = text.strip() if text else ""
        self.update()

    def set_stats(self, stats: dict):
        if stats:
            self._stats.update(stats)
        else:
            self._stats.clear()
        self.update()

    def set_res_fps(self, text: str):
        self._res_fps = text

    def current_frame(self) -> QImage:
        return self._frame

    # ---- paint ----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        if self._frame and not self._frame.isNull():
            scaled = self._frame.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
            from PySide6.QtCore import QRect
            self._img_rect = QRect(x, y, scaled.width(), scaled.height())
        else:
            self._img_rect = None

        # Draw text caption at bottom
        if self._overlay_text:
            self._draw_caption(painter)

        self._draw_monitor(painter)
        painter.end()

    def _draw_caption(self, painter):
        text = self._overlay_text.strip()
        if not text or self._img_rect is None:
            return
        r = self._img_rect

        painter.setFont(self.font())
        metrics = painter.fontMetrics()
        line_h = metrics.height() + 4
        bar_h = line_h * 5
        bar_w = int(r.width() * 0.94)
        gap_y = int(r.height() * 0.02)
        text_w = bar_w - 12

        bx = r.x() + (r.width() - bar_w) // 2
        by = r.y() + r.height() - bar_h - gap_y

        # Truncate text to fit 5 lines
        elided = ""
        for ch in text:
            test = elided + ch
            rect = metrics.boundingRect(0, 0, text_w, bar_h - 4,
                                         Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, test)
            if rect.height() > bar_h - 4:
                elided = elided.rstrip() + "…"
                break
            elided = test
        if not elided:
            elided = text

        painter.fillRect(bx, by, bar_w, bar_h, QColor(0, 0, 0))
        painter.setPen(QColor("#ddd"))
        painter.drawText(bx + 6, by + 4, text_w, bar_h - 4,
                         Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, elided)

    def _draw_monitor(self, painter):
        if self._img_rect is None:
            return
        if "fps" not in self._stats:
            return  # stopped — hide OSD
        r = self._img_rect
        fps = self._stats.get("fps", 0)
        gpu = self._stats.get("gpu", 0)
        cpu = self._stats.get("cpu", 0)
        ram = self._stats.get("ram", 0)

        text = (f"FPS:{fps:.1f} | "
                f"GPU:{gpu:.0f}% CPU:{cpu:.0f}% RAM:{ram:.1f}G")

        painter.setFont(self.font())
        fm = painter.fontMetrics()
        bar_w = fm.horizontalAdvance(text) + 12
        bar_h = fm.height() + 4
        gap_x = int(r.width() * 0.02)
        gap_y = int(r.height() * 0.02)

        bx = r.x() + r.width() - bar_w - gap_x
        by = r.y() + gap_y

        painter.fillRect(bx, by, bar_w, bar_h, QColor(0, 0, 0))
        painter.setPen(Qt.white)
        painter.drawText(bx + 3, by, bar_w - 6, bar_h,
                         Qt.AlignLeft | Qt.AlignVCenter, text)
