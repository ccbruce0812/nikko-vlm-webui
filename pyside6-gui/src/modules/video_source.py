"""
GStreamer pipeline for CSI camera capture on Jetson Orin Nano.
Emits raw RGBA bytes via Qt signals — zero OpenCV dependency, minimal copies.

Pipeline:
  nvarguscamerasrc ! NV12 NVMM ! tee
    --> nvvidconv ! BGRx ! appsink (display)
    --> nvvidconv ! NVMM I420 (scaled) ! nvjpegenc ! appsink_jpeg (inference)

Signals:
  frame_ready(bytes: BGRx, int: width, int: height)        -- display frames
  inference_ready(bytes: JPEG, int: width, int: height)    -- inference frames
"""
import os
import re
import subprocess
import logging
import queue

from PySide6.QtCore import QThread, Signal

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

Gst.init(None)

logger = logging.getLogger(__name__)


class VideoSource(QThread):
    """GStreamer-based CSI camera capture thread with tee + hardware JPEG inference branch."""

    frame_ready = Signal(bytes, int, int)      # raw BGRx, width, height (display)
    inference_ready = Signal(bytes, int, int)  # JPEG bytes, width, height (inference)
    status_message = Signal(str)

    INFER_MAX_DIM = 1280

    def __init__(self, camera_id=0, width=1920, height=1080, framerate=0,
                 enable_raw_queue=False, output_width=0, output_height=0):
        super().__init__()
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.framerate = framerate
        self.out_w = output_width
        self.out_h = output_height
        self._raw_queue = queue.Queue(maxsize=32) if enable_raw_queue else None
        self._pipeline = None
        self._loop = None
        self._actual_w = 0
        self._actual_h = 0
        self._infer_w = 0
        self._infer_h = 0
        self.paused = False
        self._latest_jpeg = None  # latest inference frame (JPEG bytes)

    # ----- device enumeration -----

    @staticmethod
    def scan_devices():
        """Scan /dev/video* and return list of (display_name, device_path)."""
        devices = []
        for i in range(10):
            path = f"/dev/video{i}"
            if os.path.exists(path):
                name = f"Camera {i}"
                try:
                    out = subprocess.check_output(
                        ["v4l2-ctl", "-d", path, "--info"],
                        text=True, stderr=subprocess.DEVNULL,
                    )
                    m = re.search(r"Card type\s*:\s*(.+)", out)
                    if m:
                        name = m.group(1).strip()
                except Exception:
                    pass
                devices.append((name, str(i)))
        return devices if devices else [("Camera 0", "0")]

    @staticmethod
    def probe_formats(device_id):
        """Probe v4l2-ctl --list-formats-ext, return ['WxH (N fps)', ...]."""
        modes = {}
        try:
            out = subprocess.check_output(
                ["v4l2-ctl", "-d", f"/dev/video{device_id}", "--list-formats-ext"],
                text=True, stderr=subprocess.DEVNULL,
            )
            current_res = None
            for line in out.split("\n"):
                m = re.search(r"Size:\s+Discrete\s+(\d+x\d+)", line)
                if m:
                    current_res = m.group(1)
                    modes.setdefault(current_res, [])
                elif current_res:
                    m = re.search(r"\(([\d.]+)\s*fps\)", line)
                    if m:
                        modes[current_res].append(float(m.group(1)))
        except Exception:
            pass

        if not modes:
            modes = {
                "3280x2464": [21], "3280x1848": [28],
                "1920x1080": [30], "1640x1232": [30],
                "1280x720": [60],
            }

        result = []
        for res, fps_list in modes.items():
            if fps_list:
                result.append(f"{res} ({int(max(fps_list))} fps)")
        return result

    @staticmethod
    def parse_resolution(text):
        """Parse resolution string.
        '1920x1080@30' → (1920, 1080, 30)
        '1920x1080 (30 fps)' → (1920, 1080, 30)
        '1280x720' → (1280, 720, 0)  (0 = auto framerate)
        Fallback: (1920, 1080, 0)
        """
        # "@" format: 1920x1080@30
        m = re.search(r"(\d+)x(\d+)@(\d+)", text)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        # "(N fps)" format
        m = re.search(r"(\d+)x(\d+).*?(\d+)\s*fps", text)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        # plain WxH (no FPS)
        m = re.search(r"(\d+)x(\d+)", text)
        if m:
            return int(m.group(1)), int(m.group(2)), 0
        return 1920, 1080, 0

    # ----- pipeline -----

    def _build_pipeline(self):
        fps = self.framerate if self.framerate > 0 else 30
        if self.framerate <= 0:
            try:
                modes = self.probe_formats(self.camera_id)
                for mode in modes:
                    w, h, f = self.parse_resolution(mode)
                    if w == self.width and h == self.height:
                        fps = f
                        break
            except Exception:
                pass

        # Inference resolution: scale to <= INFER_MAX_DIM, keep aspect ratio
        max_dim = max(self.width, self.height)
        if max_dim > self.INFER_MAX_DIM:
            ratio = self.INFER_MAX_DIM / max_dim
            self._infer_w = int(self.width * ratio)
            self._infer_h = int(self.height * ratio)
        else:
            self._infer_w = self.width
            self._infer_h = self.height

        # Tee BEFORE nvvidconv: two independent hardware paths
        disp_caps = "video/x-raw,format=BGRx"
        if self.out_w > 0 and self.out_h > 0:
            disp_caps += f",width={self.out_w},height={self.out_h}"

        pipeline_str = (
            f"nvarguscamerasrc sensor-id={self.camera_id} ! "
            f"video/x-raw(memory:NVMM),width={self.width},height={self.height},"
            f"format=NV12,framerate={fps}/1 ! "
            f"tee name=t "
            # Display: nvvidconv → BGRx → appsink (QImage display)
            f"t. ! queue max-size-buffers=2 ! "
            f"nvvidconv flip-method=0 ! {disp_caps} ! "
            f"appsink name=sink emit-signals=true max-buffers=1 drop=true sync=false "
            # Inference: nvvidconv → NVMM I420 scaled → nvjpegenc → appsink (JPEG)
            f"t. ! queue max-size-buffers=1 leaky=downstream ! "
            f"nvvidconv ! "
            f"video/x-raw(memory:NVMM),format=I420,"
            f"width={self._infer_w},height={self._infer_h} ! "
            f"nvjpegenc ! "
            f"appsink name=jpeg_sink emit-signals=true max-buffers=1 drop=true sync=false"
        )
        logger.info("GStreamer tee pipeline (display + %dx%d JPEG infer)",
                     self._infer_w, self._infer_h)
        return pipeline_str

    def _on_new_sample(self, appsink):
        sample = appsink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR
        buf = sample.get_buffer()
        if buf is None:
            return Gst.FlowReturn.OK

        # Extract actual dimensions from caps (stride-safe)
        caps = sample.get_caps()
        if caps:
            s = caps.get_structure(0)
            self._actual_w = s.get_int("width")[1]
            self._actual_h = s.get_int("height")[1]

        ok, map_info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK

        try:
            data = bytes(map_info.data)
            if self._raw_queue is not None:
                try:
                    self._raw_queue.put_nowait((data, self._actual_w, self._actual_h))
                except queue.Full:
                    pass
            else:
                self.frame_ready.emit(data, self._actual_w, self._actual_h)
        finally:
            buf.unmap(map_info)

        return Gst.FlowReturn.OK

    def _on_jpeg_sample(self, appsink):
        """Inference branch: JPEG bytes. Skips copy when paused."""
        sample = appsink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR
        buf = sample.get_buffer()
        if buf is None:
            return Gst.FlowReturn.OK

        if self.paused:
            return Gst.FlowReturn.OK

        ok, map_info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK
        try:
            self._latest_jpeg = bytes(map_info.data)
        finally:
            buf.unmap(map_info)
        return Gst.FlowReturn.OK

    # ----- thread life-cycle -----

    def run(self):
        self._loop = GLib.MainLoop()

        pipeline_str = self._build_pipeline()
        self._pipeline = Gst.parse_launch(pipeline_str)

        appsink = self._pipeline.get_by_name("sink")
        appsink.connect("new-sample", self._on_new_sample)

        jpeg_sink = self._pipeline.get_by_name("jpeg_sink")
        jpeg_sink.connect("new-sample", self._on_jpeg_sample)

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_error)
        bus.connect("message::eos", self._on_eos)

        self._pipeline.set_state(Gst.State.PLAYING)
        self.status_message.emit(
            f"Streaming {self.width}x{self.height}"
        )

        try:
            self._loop.run()
        except Exception:
            pass

        self._pipeline.set_state(Gst.State.NULL)

    def _on_error(self, _bus, msg):
        err, dbg = msg.parse_error()
        self.status_message.emit(f"GStreamer error: {err}")

    def _on_eos(self, _bus, _msg):
        self.status_message.emit("Stream ended")

    @property
    def latest_jpeg(self):
        """Return latest inference frame (JPEG bytes, width, height) or (None, 0, 0)."""
        data = self._latest_jpeg
        if data is not None:
            return data, self._infer_w, self._infer_h
        return None, 0, 0

    def stop(self):
        if self._loop:
            self._loop.quit()
        self.wait()
