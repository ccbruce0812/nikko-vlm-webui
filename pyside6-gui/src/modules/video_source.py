"""
GStreamer video source: nvdsosd + nveglglessink display, 10fps JPEG inference.

Pipeline (tee split):
  Display:  nvarguscamerasrc → tee → nvstreammux → nvdsosd → nvegltransform → nveglglessink
  Infer:    tee → nvvidconv → videorate 10fps → nvjpegenc → appsink

nveglglessink renders via prepare-window-handle (set by kiosk_window).
nvdsosd probe is attached by kiosk_window for OSD/bbox/caption.
"""
import re, subprocess, os, logging
from PySide6.QtCore import QThread, Signal

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gst, GLib

Gst.init(None)

logger = logging.getLogger(__name__)

INFER_MAX_DIM = 1280
INFER_FPS = 10
NVINFER_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "assets", "config.txt")


class VideoSource(QThread):
    frame_for_infer = Signal(bytes)
    status_message = Signal(str)

    def __init__(self, camera_id=0, width=1920, height=1080, framerate=0,
                 pipeline=None):
        super().__init__()
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.framerate = framerate
        self._prebuilt = pipeline  # pre-built pipeline (sync_handler already set)
        self._pipeline = None
        self._loop = None

    # ----- enumeration (same as original) -----

    @staticmethod
    def scan_devices():
        devices = []
        for i in range(10):
            path = f"/dev/video{i}"
            if __import__("os").path.exists(path):
                name = f"Camera {i}"
                try:
                    out = subprocess.check_output(
                        ["v4l2-ctl", "-d", path, "--info"],
                        text=True, stderr=subprocess.DEVNULL)
                    m = re.search(r"Card type\s*:\s*(.+)", out)
                    if m: name = m.group(1).strip()
                except Exception: pass
                devices.append((name, str(i)))
        return devices if devices else [("Camera 0", "0")]

    @staticmethod
    def probe_formats(device_id):
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

    @staticmethod
    def parse_resolution(text):
        m = re.search(r"(\d+)x(\d+)@(\d+)", text)
        if m: return int(m.group(1)), int(m.group(2)), int(m.group(3))
        m = re.search(r"(\d+)x(\d+).*?(\d+)\s*fps", text)
        if m: return int(m.group(1)), int(m.group(2)), int(m.group(3))
        m = re.search(r"(\d+)x(\d+)", text)
        if m: return int(m.group(1)), int(m.group(2)), 0
        return 1920, 1080, 0

    # ----- pipeline -----

    def _build_pipeline(self):
        fps = self.framerate if self.framerate > 0 else 30
        if self.framerate <= 0:
            try:
                for mode in self.probe_formats(self.camera_id):
                    w, h, f = self.parse_resolution(mode)
                    if w == self.width and h == self.height:
                        fps = f; break
            except Exception: pass

        max_dim = max(self.width, self.height)
        if max_dim > INFER_MAX_DIM:
            r = INFER_MAX_DIM / max_dim
            iw, ih = int(self.width * r), int(self.height * r)
        else:
            iw, ih = self.width, self.height

        desc = (
            f"nvarguscamerasrc sensor-id={self.camera_id} ! "
            f"video/x-raw(memory:NVMM),width={self.width},height={self.height},"
            f"format=NV12,framerate={fps}/1 ! "
            f"tee name=t "
            # Display: nvstreammux → nvdsosd → nvegltransform → nveglglessink
            f"t. ! queue ! nvvidconv ! video/x-raw(memory:NVMM),format=NV12,"
            f"width={self.width},height={self.height} ! m.sink_0 "
            f"nvstreammux name=m batch-size=1 width={self.width} height={self.height} "
            f"live-source=1 batched-push-timeout=33333 ! "
            f"nvinfer name=nv_infer config-file-path={NVINFER_CONFIG} unique-id=1 ! "
            f"nvdsosd name=osd process-mode=1 display-text=1 display-bbox=1 ! "
            f"nvegltransform ! "
            f"nveglglessink name=gl_sink sync=false "
            # Infer: 10fps JPEG → appsink
            f"t. ! queue ! nvvidconv ! "
            f"video/x-raw,format=I420,width={iw},height={ih} ! "
            f"videorate ! video/x-raw,framerate={INFER_FPS}/1 ! "
            f"nvjpegenc ! "
            f"appsink name=infer_sink emit-signals=true max-buffers=1 drop=true sync=false"
        )
        logger.info("Pipeline: display=%dx%d infer=%dx%d@%dfps",
                     self.width, self.height, iw, ih, INFER_FPS)
        return desc

    def _on_infer_sample(self, appsink):
        sample = appsink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR
        buf = sample.get_buffer()
        if buf is None:
            return Gst.FlowReturn.OK
        ok, map_info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK
        try:
            self.frame_for_infer.emit(bytes(map_info.data))
        finally:
            buf.unmap(map_info)
        return Gst.FlowReturn.OK

    # ----- thread -----

    def run(self):
        self._loop = GLib.MainLoop()
        if self._prebuilt is not None:
            self._pipeline = self._prebuilt
        else:
            self._pipeline = Gst.parse_launch(self._build_pipeline())
        infer = self._pipeline.get_by_name("infer_sink")
        infer.connect("new-sample", self._on_infer_sample)
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_error)
        self._pipeline.set_state(Gst.State.PLAYING)
        self.status_message.emit(f"Streaming {self.width}x{self.height}")
        try:
            self._loop.run()
        except Exception:
            pass
        self._pipeline.set_state(Gst.State.NULL)

    def _on_error(self, _bus, msg):
        self.status_message.emit(f"GStreamer error: {msg.parse_error()[0]}")

    def stop(self):
        if self._loop:
            self._loop.quit()
        self.wait()

    def nvdsosd_element(self):
        """Return nvdsosd element for probe attachment (called after pipeline start)."""
        if self._pipeline:
            return self._pipeline.get_by_name("osd")
        return None
