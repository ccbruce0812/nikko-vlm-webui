#!/usr/bin/env python3
"""Kiosk VLM GUI — entry point."""
import sys, signal, logging, argparse, os, atexit, json, urllib.request

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from src.ui.kiosk_window import KioskWindow
from src.modules.video_source import VideoSource
from src.modules.defaults import DEFAULTS

PID_FILE = "/tmp/pyside6-gui.pid"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("gui")

_quit_flag = False


def _release_pidfile():
    try: os.remove(PID_FILE)
    except OSError: pass


def _acquire_pidfile():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            logger.error("Already running (PID %d)", old_pid)
            sys.exit(1)
        except (OSError, ValueError):
            os.remove(PID_FILE)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(_release_pidfile)


def _handle_signal(sig, frame):
    global _quit_flag
    _quit_flag = True
    _release_pidfile()


def _parse_args():
    p = argparse.ArgumentParser(description="Kiosk VLM GUI", formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dpi-scale", type=float, default=2.0, help="DPI scale (default: 2.0)")
    p.add_argument("--play", action="store_true", help="Auto-start streaming")
    p.add_argument("--camera-id", type=int, default=DEFAULTS["camera_id"])
    p.add_argument("--resolution", default=DEFAULTS["resolution"])
    p.add_argument("--reasoning-model", default=DEFAULTS["reasoning_model"])
    p.add_argument("--interval", type=int, default=DEFAULTS["interval"])
    p.add_argument("--prompt", default=DEFAULTS["prompt"])
    p.add_argument("--max-tokens", type=int, default=DEFAULTS["max_tokens"])
    p.add_argument("--router-url", default=DEFAULTS["router_url"])
    p.add_argument("--ram-threshold", type=float, default=DEFAULTS["ram_threshold"])
    return p.parse_args()


def resolve_config(args):
    """Resolve all configuration synchronously. Returns config dict or sys.exit(1)."""
    config = dict(DEFAULTS)

    # --- camera ---
    devices = VideoSource.scan_devices()
    if not devices:
        logger.error("No camera found — exiting")
        sys.exit(1)
    device_ids = {int(d[1]) for d in devices}
    cam_id = args.camera_id if args.camera_id is not None else config["camera_id"]
    if cam_id not in device_ids:
        logger.warning("Camera %d not found, using first available", cam_id)
        cam_id = min(device_ids)
    config["camera_id"] = cam_id

    # --- resolution ---
    formats = VideoSource.probe_formats(str(cam_id))
    if not formats:
        logger.error("No formats for camera %d", cam_id)
        sys.exit(1)
    res_text = args.resolution if args.resolution is not None else config["resolution"]
    w, h, fps = VideoSource.parse_resolution(res_text)
    found = None
    for f in formats:
        fw, fh, ff = VideoSource.parse_resolution(f)
        if fw == w and fh == h:
            found = f
            break
    if found:
        config["resolution_text"] = found
    else:
        found = max(formats, key=lambda f: VideoSource.parse_resolution(f)[0] * VideoSource.parse_resolution(f)[1])
        config["resolution_text"] = found
        logger.warning("Resolution %s not supported, using highest: %s", res_text, found)
    config["resolution_w"], config["resolution_h"], config["resolution_fps"] = VideoSource.parse_resolution(found)

    # --- router: fetch models ---
    router_url = args.router_url if args.router_url is not None else config["router_url"]
    config["router_url"] = router_url
    models = []
    try:
        req = urllib.request.Request(f"{router_url}/v1/models")
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        models = [(m["id"], m.get("owned_by", "")) for m in data.get("data", [])]
    except Exception:
        logger.warning("Router unreachable, models=disable only")

    # --- model classification ---
    reasoning_models = [m_id for m_id, _ in models if m_id != "yolo"]
    config["reasoning_options"] = ["disable"] + reasoning_models

    r_default = args.reasoning_model if args.reasoning_model is not None else config["reasoning_model"]
    if r_default not in config["reasoning_options"]:
        logger.warning("Reasoning model '%s' not available, using disable", r_default)
        r_default = "disable"
    config["reasoning_default"] = r_default

    # --- other params (CLI > DEFAULTS) ---
    config["interval"] = args.interval if args.interval is not None else config["interval"]
    config["prompt"] = args.prompt if args.prompt is not None else config["prompt"]
    config["max_tokens"] = args.max_tokens if args.max_tokens is not None else config["max_tokens"]
    config["ram_threshold"] = args.ram_threshold if args.ram_threshold is not None else config["ram_threshold"]
    config["auto_start"] = args.play
    config["dpi_scale"] = args.dpi_scale

    return config

def main():
    _acquire_pidfile()
    args = _parse_args()
    config = resolve_config(args)

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    qss_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path) as f:
            app.setStyleSheet(f.read())

    screen = app.primaryScreen()
    if screen:
        dpi = screen.logicalDotsPerInch()
        pts = max(10, int(12 * dpi / 96 * config["dpi_scale"]))
    else:
        pts = 10
    font = app.font()
    font.setPointSize(pts)
    font.setFamily("monospace")
    app.setFont(font)
    logger.info("Font: %dpt (DPI=%.0f, scale=%.1fx)", pts, dpi if screen else 0, config["dpi_scale"])

    logger.info("Config: %dx%d@%d reasoning=%s interval=%d play=%s (YOLO via nvinfer)",
                 config["resolution_w"], config["resolution_h"], config["resolution_fps"],
                 config["reasoning_default"],
                 config["interval"], config["auto_start"])

    window = KioskWindow(config)
    window.showFullScreen()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    timer = QTimer()
    timer.timeout.connect(lambda: app.quit() if _quit_flag else None)
    timer.start(200)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
