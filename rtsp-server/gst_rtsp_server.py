#!/usr/bin/env python3
"""
GStreamer RTSP server — CSI camera source (CAM0 / IMX219) via nvarguscamerasrc.
Image size controlled by WIDTH/HEIGHT environment variables.
"""
import os, sys, logging, signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [rtsp-server] %(message)s")
logger = logging.getLogger("rtsp-server")

# ── env vars ──────────────────────────────────────────────
WIDTH  = os.environ.get("WIDTH",  "1280")
HEIGHT = os.environ.get("HEIGHT", "720")
FPS    = os.environ.get("FPS",    "30")
RTSP_PORT = os.environ.get("RTSP_PORT", "8554")
RTSP_PATH = os.environ.get("RTSP_PATH", "/stream")
SENSOR_ID = os.environ.get("SENSOR_ID", "0")  # CAM0

logger.info(f"CSI camera: sensor-id={SENSOR_ID}  {WIDTH}x{HEIGHT} @ {FPS}fps")

# ── GStreamer ─────────────────────────────────────────────
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

# nvarguscamerasrc → nvvidconv → x264enc → rtph264pay
pipeline_str = (
    f"nvarguscamerasrc sensor-id={SENSOR_ID} ! "
    f"video/x-raw(memory:NVMM),width={WIDTH},height={HEIGHT},framerate={FPS}/1 ! "
    f"nvvidconv ! video/x-raw,format=I420 ! "
    f"x264enc speed-preset=ultrafast tune=zerolatency bitrate=2000 ! "
    f"h264parse ! rtph264pay name=pay0 pt=96"
)

logger.info(f"Pipeline: nvarguscamerasrc → nvvidconv → x264enc")
logger.info(f"RTSP: rtsp://<host>:{RTSP_PORT}{RTSP_PATH}")

# ── RTSP server ───────────────────────────────────────────
class RtspServer:
    def __init__(self):
        self.server = GstRtspServer.RTSPServer()
        self.server.set_service(str(RTSP_PORT))
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline_str)
        factory.set_shared(True)
        mount_points = self.server.get_mount_points()
        mount_points.add_factory(RTSP_PATH, factory)
        self.server.attach(None)
        logger.info(f"RTSP server started on port {RTSP_PORT}")

server = RtspServer()
loop = GLib.MainLoop()

def shutdown(sig, frame):
    logger.info("Shutting down...")
    loop.quit()

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)
loop.run()
