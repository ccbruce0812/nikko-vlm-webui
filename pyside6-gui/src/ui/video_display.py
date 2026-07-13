"""Video display stub — nveglglessink renders video directly (no QPainter)."""
from PySide6.QtWidgets import QLabel


class VideoDisplay(QLabel):
    """Placeholder widget — video rendered by nveglglessink via WA_NativeWindow."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: black;")
        self._res_fps = ""

    def set_res_fps(self, text):
        self._res_fps = text

    def set_frame(self, qimage):
        pass  # nveglglessink renders, no QImage display

    def set_stats(self, stats):
        pass  # nvdsosd handles OSD

    def set_overlay_text(self, text):
        pass  # nvdsosd handles caption
