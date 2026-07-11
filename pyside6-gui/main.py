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
from src.modules.video_source import VideoSource
from src.modules.defaults import DEFAULTS

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
    p = argparse.ArgumentParser(
        description="Kiosk VLM GUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py                                           # interactive mode
  python main.py --play --camera-id 0 --resolution 3280x2464@21 \\
                  --model reason2 --prompt "Describe this image.""")

    # Display
    p.add_argument("--dpi-scale", type=float, default=2.0,
                   help="DPI scale factor (default: 2.0)")

    # --play auto-start mode
    p.add_argument("--play", action="store_true",
                   help="Auto-start streaming and inference (skip manual START)")
    p.add_argument("--camera-id", type=int, default=DEFAULTS["camera_id"],
                   help=f"Camera device ID (default: {DEFAULTS['camera_id']})")
    p.add_argument("--resolution", default=DEFAULTS["resolution"],
                   help="Resolution WxH[@FPS], e.g. 3280x2464@21 (default: auto-highest)")
    p.add_argument("--model", default=DEFAULTS["model"],
                   help=f"Model: reason2, moondream2, yolo, or disable (default: {DEFAULTS['model']})")
    p.add_argument("--interval", type=int, default=DEFAULTS["interval"],
                   help=f"Inference interval in ms (default: {DEFAULTS['interval']})")
    p.add_argument("--prompt", default=DEFAULTS["prompt"],
                   help=f"Prompt sent to VLM (default: {repr(DEFAULTS['prompt'])})")
    p.add_argument("--max-tokens", type=int, default=DEFAULTS["max_tokens"],
                   help=f"Max response tokens 1-2048 (default: {DEFAULTS['max_tokens']})")
    return p.parse_args()

def _play_args_clamped(args):
    """Clamp --play arguments to valid ranges."""
    args.interval = max(1, args.interval)
    args.max_tokens = max(1, min(args.max_tokens, 2048))
    return args


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

    # Apply CLI args to sidebar (always), auto-start if --play
    _play_args_clamped(args)
    if args.resolution:
        w, h, fps = VideoSource.parse_resolution(args.resolution)
    else:
        w = h = fps = 0  # auto-select from UI
    logger.info("CLI args: %s model=%s interval=%d play=%s",
                 args.resolution or "auto", args.model, args.interval, args.play)
    QTimer.singleShot(2000, lambda: window.apply_cli_args(
        args.camera_id, w, h, fps,
        args.model, args.interval, args.prompt, args.max_tokens,
        auto_start=args.play,
    ))

    # Handle Ctrl-C / SIGTERM
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    timer = QTimer()
    timer.timeout.connect(lambda: app.quit() if _quit_flag else None)
    timer.start(200)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
