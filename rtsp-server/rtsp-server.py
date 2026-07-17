#!/usr/bin/env python3
"""GStreamer RTSP server — CSI camera source (CAM0 / IMX219) via nvarguscamerasrc."""
import argparse, logging, os, re, signal, subprocess, sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [rtsp-server] %(message)s")
logger = logging.getLogger("rtsp-server")


# ── camera helpers (mirrors pyside6-gui VideoSource) ────────

def scan_devices():
    """Return list of (name, device_id_str) for /dev/video0–9."""
    devices = []
    for i in range(10):
        path = f"/dev/video{i}"
        if os.path.exists(path):
            name = f"Camera {i}"
            try:
                out = subprocess.check_output(
                    ["v4l2-ctl", "-d", path, "--info"],
                    text=True, stderr=subprocess.DEVNULL)
                m = re.search(r"Card type\s*:\s*(.+)", out)
                if m: name = m.group(1).strip()
            except Exception: pass
            devices.append((name, str(i)))
    return devices


def probe_formats(device_id):
    """Return list of 'WxH (max_fps fps)' strings."""
    modes = {}
    try:
        out = subprocess.check_output(
            ["v4l2-ctl", "-d", f"/dev/video{device_id}", "--list-formats-ext"],
            text=True, stderr=subprocess.DEVNULL)
        cur = None
        for line in out.split("\n"):
            m = re.search(r"Size:\s+Discrete\s+(\d+x\d+)", line)
            if m: cur = m.group(1); modes.setdefault(cur, [])
            elif cur:
                m = re.search(r"\(([\d.]+)\s*fps\)", line)
                if m: modes[cur].append(float(m.group(1)))
    except Exception: pass
    if not modes:
        modes = {"3280x2464": [21], "3280x1848": [28],
                 "1920x1080": [30], "1640x1232": [30], "1280x720": [60]}
    return [f"{r} ({int(max(f))} fps)" for r, f in modes.items() if f]


def parse_resolution(text):
    """Return (width, height, fps).  FPS=0 if not specified."""
    m = re.search(r"(\d+)x(\d+)@(\d+)", text)
    if m: return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"(\d+)x(\d+).*?(\d+)\s*fps", text)
    if m: return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"(\d+)x(\d+)", text)
    if m: return int(m.group(1)), int(m.group(2)), 30  # default FPS
    return 1920, 1080, 30


# ── resolve_config ─────────────────────────────────────────

def resolve_config(args):
    """Validate and resolve camera + resolution. sys.exit(1) on failure."""

    # camera
    devices = scan_devices()
    if not devices:
        logger.error("No camera found")
        sys.exit(1)
    device_ids = {int(d[1]) for d in devices}
    cam_id = args.camera_id if args.camera_id is not None else 0
    if cam_id not in device_ids:
        cam_id = min(device_ids)
        logger.warning("Camera %d not found, using %d", args.camera_id, cam_id)

    # resolution
    formats = probe_formats(str(cam_id))
    if not formats:
        logger.error("No formats for camera %d", cam_id)
        sys.exit(1)
    req_w, req_h, req_fps = parse_resolution(args.resolution)
    found = None
    for f in formats:
        fw, fh, ff = parse_resolution(f)
        if fw == req_w and fh == req_h:
            found = f
            break
    if not found:
        found = max(formats, key=lambda f: parse_resolution(f)[0] * parse_resolution(f)[1])
        logger.warning("Resolution %s not supported, using %s", args.resolution, found)
    w, h, fps = parse_resolution(found)
    if fps <= 0:
        fps = req_fps if req_fps > 0 else 30

    # port
    if args.port < 1024 or args.port > 65535:
        logger.error("Port must be 1024–65535, got %d", args.port)
        sys.exit(1)

    # path
    path = args.path
    if not path.startswith("/"):
        path = "/" + path

    return {"camera_id": cam_id, "width": w, "height": h, "fps": fps,
            "port": args.port, "path": path}


# ── argparse ───────────────────────────────────────────────
p = argparse.ArgumentParser(
    description="CSI camera RTSP server (nvarguscamerasrc → x264enc → rtph264pay)",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="Examples:\n"
           "  python3 rtsp-server.py\n"
           "  python3 rtsp-server.py --resolution 1280x720 --port 8555\n"
           "  python3 rtsp-server.py --camera-id 0 --path /cam0 --resolution 1920x1080@30",
)
p.add_argument("--camera-id", type=int, default=0, help="CSI camera sensor ID (default: 0)")
p.add_argument("--resolution", default="1920x1080@30",
               help="WxH[@FPS] — FPS optional (default: 1920x1080@30)")
p.add_argument("--port", type=int, default=8554, help="RTSP port (default: 8554)")
p.add_argument("--path", default="/stream", help="RTSP mount path (default: /stream)")
args = p.parse_args()

cfg = resolve_config(args)

logger.info("Camera: sensor-id=%d  %dx%d @ %dfps", cfg["camera_id"], cfg["width"], cfg["height"], cfg["fps"])
logger.info("RTSP: port=%d path=%s", cfg["port"], cfg["path"])

# ── GStreamer ──────────────────────────────────────────────
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

pipeline_str = (
    f"nvarguscamerasrc sensor-id={cfg['camera_id']} ! "
    f"video/x-raw(memory:NVMM),width={cfg['width']},height={cfg['height']},framerate={cfg['fps']}/1 ! "
    f"nvvidconv ! video/x-raw,format=I420 ! "
    f"x264enc speed-preset=ultrafast tune=zerolatency bitrate=2000 ! "
    f"h264parse ! rtph264pay name=pay0 pt=96"
)

logger.info("Pipeline: nvarguscamerasrc → nvvidconv → x264enc → rtph264pay")


class RtspServer:
    def __init__(self):
        self.server = GstRtspServer.RTSPServer()
        self.server.set_service(str(cfg["port"]))
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline_str)
        factory.set_shared(True)
        mount_points = self.server.get_mount_points()
        mount_points.add_factory(cfg["path"], factory)
        self.server.attach(None)
        logger.info("RTSP server started — rtsp://<host>:%d%s", cfg["port"], cfg["path"])


server = RtspServer()
loop = GLib.MainLoop()


def shutdown(sig, frame):
    logger.info("Shutting down...")
    loop.quit()


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)
loop.run()
