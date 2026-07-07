import sys
import os
import signal
import argparse
import atexit

# 確保專案根目錄在系統路徑中，以解決模組匯入問題 (ImportError)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from src.ui.main_window import MainWindow

PID_FILE = "/tmp/pyside6-main.pid"

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
            print(f"[ERROR] pyside6-main is already running (PID {old_pid}).", file=sys.stderr)
            sys.exit(1)
        except (OSError, ValueError):
            # Stale PID file (process died or invalid content)
            print(f"[WARN] Removing stale PID file: {PID_FILE}", file=sys.stderr)
            os.remove(PID_FILE)

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(_release_pidfile)


def _handle_signal(sig, frame):
    global _quit_flag
    _quit_flag = True
    _release_pidfile()


def _parse_args():
    p = argparse.ArgumentParser(description="pyside6-main GUI")
    p.add_argument("--dpi-scale", type=float, default=2.0,
                   help="DPI scale factor (default: 2.0)")
    return p.parse_args()


def main():
    _acquire_pidfile()

    args = _parse_args()

    # 針對高解析度螢幕進行縮放優化
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

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
    print(f"Font: {pts}pt (DPI={dpi:.0f}, scale={args.dpi_scale:.1f}x)")

    # Handle Ctrl-C / SIGTERM
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    timer = QTimer()
    timer.setInterval(200)
    timer.timeout.connect(lambda: app.quit() if _quit_flag else None)
    timer.start()

    try:
        window = MainWindow()
        # Window = 60% screen width, 80% screen height
        if screen:
            sw, sh = screen.size().width(), screen.size().height()
            window.resize(int(sw * 0.6), int(sh * 0.8))
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Startup Critical Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
