#!/usr/bin/env python3
"""Kiosk VLM GUI — entry point."""
import sys
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.ui.kiosk_window import KioskWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = KioskWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
