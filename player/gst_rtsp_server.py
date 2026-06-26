#!/usr/bin/env python3
"""
GStreamer RTSP server for MP4 playback.
Uses decodebin for auto hardware/software decode selection.
"""

import sys, os, logging, signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [player] %(message)s")
logger = logging.getLogger("player")

VIDEO_FILE = os.environ.get("VIDEO_FILE", "/videos/demo.mp4")
RTSP_PORT = os.environ.get("RTSP_PORT", "8554")
RTSP_PATH = os.environ.get("RTSP_PATH", "/stream")

logger.info(f"Source: {VIDEO_FILE}")

if not os.path.exists(VIDEO_FILE):
    logger.error(f"Video file not found: {VIDEO_FILE}")
    sys.exit(1)

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

# Check what decoders are actually available
reg = Gst.Registry.get()
has_nvdec = reg.find_feature("nvv4l2decoder", Gst.ElementFactory) is not None
logger.info(f"nvv4l2decoder available: {has_nvdec}")

# Use decodebin which auto-selects best decoder (HW if possible, SW fallback)
pipeline_str = (
    f"filesrc location={VIDEO_FILE} ! qtdemux ! h264parse ! "
    f"decodebin ! videoconvert ! videoscale ! "
    f"video/x-raw,width=640,height=480 ! "
    f"x264enc speed-preset=ultrafast tune=zerolatency ! "
    f"h264parse ! rtph264pay name=pay0 pt=96"
)

logger.info(f"Pipeline: decodebin (auto HW/SW) → scale → x264enc")
logger.info(f"RTSP: rtsp://0.0.0.0:{RTSP_PORT}{RTSP_PATH}")

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
