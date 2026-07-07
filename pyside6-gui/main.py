#!/usr/bin/env python3
"""Kiosk VLM GUI — entry point."""
import sys
import signal
import logging
import argparse
import os
import atexit

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from src.ui.kiosk_window import KioskWindow

PID_FILE = "/tmp/pyside6-gui.pid"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gui")

_quit_flag = False


def _release_pidfile():
    """Remove the PID file (idempotent)."""
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def _acquire_pidfile():
    """Ensure only one instance runs via PID file.  Stale files are cleaned."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)  # signal 0 = existence check
            logger.error("Another instance is already running (PID %d).", old_pid)
            print(f"[ERROR] pyside6-gui is already running (PID {old_pid}).", file=sys.stderr)
            sys.exit(1)
        except (OSError, ValueError):
            # Stale PID file (process died or invalid content)
            logger.warning("Removing stale PID file: %s", PID_FILE)
            os.remove(PID_FILE)

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(_release_pidfile)
    logger.info("PID file acquired: %s (PID %d)", PID_FILE, os.getpid())


def _handle_signal(sig, frame):
    global _quit_flag
    _quit_flag = True
    _release_pidfile()


def _parse_args():
    p = argparse.ArgumentParser(description="Kiosk VLM GUI")
    p.add_argument("--dpi-scale", type=float, default=2.0,
                   help="DPI scale factor (default: 2.0)")
    return p.parse_args()


def main():
    _acquire_pidfile()

    args = _parse_args()

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Load dark theme stylesheet
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path) as f:
            app.setStyleSheet(f.read())

    # Font scaling — base 12pt at 96 DPI × scale factor
    screen = app.primaryScreen()
    if screen:
        dpi = screen.logicalDotsPerInch()
        pts = max(10, int(12 * dpi / 96 * args.dpi_scale))
    else:
        pts = 10
    font = app.font()
    font.setPointSize(pts)
    font.setFamily("monospace")
    app.setFont(font)
    logger.info("Font: %dpt (DPI=%.0f, scale=%.1fx)", pts, dpi if screen else 0, args.dpi_scale)

    window = KioskWindow()
    window.showFullScreen()

    # Handle Ctrl-C / SIGTERM
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    timer = QTimer()
    timer.timeout.connect(lambda: app.quit() if _quit_flag else None)
    timer.start(200)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
