#!/usr/bin/env python3
"""Kiosk VLM GUI — entry point."""
import sys
import signal
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from src.ui.kiosk_window import KioskWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gui")

_quit_flag = False


def _handle_signal(sig, frame):
    global _quit_flag
    _quit_flag = True


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Load dark theme stylesheet
    import os
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path) as f:
            app.setStyleSheet(f.read())

    # Font scaling — base 9pt at 800px height, proportional to screen
    screen = app.primaryScreen()
    if screen:
        ref_h = screen.size().height()
        pts = max(10, int(12 * ref_h / 800))
    else:
        pts = 9
    font = app.font()
    font.setPointSize(pts)
    font.setFamily("monospace")
    app.setFont(font)

    window = KioskWindow()
    window.showFullScreen()

    # Handle Ctrl-C / SIGTERM
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Qt timer to check for signal (safe call from Qt event loop)
    timer = QTimer()
    timer.timeout.connect(lambda: app.quit() if _quit_flag else None)
    timer.start(200)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
