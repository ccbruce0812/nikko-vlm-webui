from PySide6.QtWidgets import QFrame, QVBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPainter, QColor


class VideoCanvas(QFrame):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Live Stream")
        self.setMinimumSize(800, 600)
        self.setStyleSheet("background-color: black;")
        self._image = QImage()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

    def update_image(self, qimage: QImage):
        self._image = qimage
        self.update()

    def clear(self):
        self._image = QImage()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._image.isNull():
            painter.fillRect(self.rect(), QColor("black"))
        else:
            target = self.rect()
            scaled = self._image.scaled(target.width(), target.height(),
                                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (target.width() - scaled.width()) // 2
            y = (target.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
        painter.end()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
