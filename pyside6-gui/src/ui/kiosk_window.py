"""
Kiosk main window with nvdsosd GPU overlay.
YOLO via nvinfer (hw pipeline), reasoning via slot-based dispatch.
"""
import base64
import json
import logging
import time
import os

from PySide6.QtWidgets import (
    QMainWindow, QHBoxLayout, QWidget, QLabel, QSizePolicy,
)
from PySide6.QtCore import QTimer, Slot, Qt

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gst, GstVideo

import pyds

from src.ui.control_sidebar import ControlSidebar
from src.modules.video_source import VideoSource
from src.modules.router_client import RouterClient
from src.modules.system_monitor import read_stats, compute_cpu_pct
from src.modules import reason2_overlay, moondream2_overlay, yolo_overlay

logger = logging.getLogger("gui")

MODULES = {
    "reason2":     reason2_overlay,
    "moondream2":  moondream2_overlay,
}


class _Slot:
    __slots__ = ("name", "prepare", "fill", "pending", "result", "infer_start")
    def __init__(self):
        self.name = "disable"; self.prepare = None; self.fill = None
        self.pending = False; self.result = None; self.infer_start = 0.0
    def activate(self, model_name: str):
        if model_name == "disable" or model_name not in MODULES:
            self.name = "disable"; self.prepare = None; self.fill = None
        else:
            m = MODULES[model_name]
            self.name = model_name
            self.prepare = m.prepare_payload
            self.fill = m.fill_display_meta
        self.pending = False; self.result = None


class KioskWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self._config = config
        self._video_source = None
        self._router = RouterClient(config["router_url"])
        self._interval_timer = QTimer(self)
        self._interval_timer.timeout.connect(self._on_interval_tick)
        self._mon_timer = QTimer(self)
        self._mon_timer.timeout.connect(self._on_monitor_tick)
        self._params = {}
        self._input_count = 0; self._fps_t0 = time.time()
        self._prev_cpu_snap = None
        self._latest_jpeg = b""
        self._osd_logged = None
        self._reos = _Slot()
        self._reos.activate(config.get("reasoning_default", "disable"))
        self._osd_fps = self._osd_gpu = self._osd_cpu = self._osd_ram = 0.0
        self._sidebar = ControlSidebar(config)
        self._init_ui(); self._connect_signals(); self._router.start()
        self._start_ram_monitor(config["ram_threshold"])
        if config["auto_start"]:
            QTimer.singleShot(500, self._cli_auto_start)

    def _init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        self._sidebar.setFixedWidth(self._sidebar.sizeHint().width())
        layout.addWidget(self._sidebar, 2)
        self._video_widget = QLabel()
        self._video_widget.setStyleSheet("background-color: black;")
        self._video_widget.setAttribute(Qt.WA_NativeWindow, True)
        self._video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._video_widget, 3)

    def _connect_signals(self):
        self._sidebar.start_clicked.connect(self._on_start)
        self._sidebar.stop_clicked.connect(self._on_stop)
        self._sidebar.quit_clicked.connect(self.close)
        self._sidebar.perception_changed.connect(self._on_perception_changed)
        self._sidebar.reasoning_changed.connect(self._on_reasoning_changed)
        self._router.result_ready.connect(self._on_inference_result)
        self._router.error_occurred.connect(self._on_router_error)

    def _cli_auto_start(self):
        dev_id = self._sidebar.camera_combo.currentData() or 0
        self._on_start(dev_id, self._config["resolution_w"], self._config["resolution_h"])

    @Slot(int, int, int)
    def _on_start(self, camera_id, width, height):
        params = self._sidebar.get_params(); self._params = params
        params["width"] = width; params["height"] = height
        res = self._sidebar.res_combo.currentText()
        _, _, fps = VideoSource.parse_resolution(res)
        self._input_count = 0; self._fps_t0 = time.time()
        self._latest_jpeg = b""
        self._reos.result = None; self._osd_logged = None
        vs = VideoSource(camera_id, width, height, fps)
        pipeline_str = vs._build_pipeline()
        pipeline = Gst.parse_launch(pipeline_str)
        bus = pipeline.get_bus()
        bus.set_sync_handler(self._bus_sync_handler)
        osd_el = pipeline.get_by_name("osd")
        if osd_el:
            osd_el.get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, self._osd_probe, None)
        self._video_source = VideoSource(camera_id, width, height, fps, pipeline=pipeline)
        self._video_source.frame_for_infer.connect(self._on_frame_for_infer)
        self._video_source.status_message.connect(self._on_video_status)
        self._video_source.start()
        self._sidebar.set_streaming_state(True)
        self._mon_timer.start(5000)
        self._interval_timer.start(params["interval"])
        logger.info("Streaming %dx%d@%d reasoning=%s interval=%dms (YOLO via nvinfer)",
                     width, height, fps, self._reos.name, params["interval"])

    def _bus_sync_handler(self, bus, message):
        if GstVideo.is_video_overlay_prepare_window_handle_message(message):
            message.src.set_window_handle(int(self._video_widget.winId()))
            return Gst.BusSyncReply.DROP
        return Gst.BusSyncReply.PASS

    @Slot()
    def _on_stop(self):
        self._interval_timer.stop(); self._mon_timer.stop()
        self._reos.pending = False; self._reos.result = None
        if self._video_source: self._video_source.stop(); self._video_source = None
        self._sidebar.set_streaming_state(False)

    @Slot(str)
    def _on_video_status(self, msg): logger.info(msg)

    @Slot(bytes)
    def _on_frame_for_infer(self, jpeg_data):
        self._input_count += 1; self._latest_jpeg = jpeg_data

    def _maybe_fire(self, slot: _Slot, jpeg_data: bytes):
        if slot.name == "disable" or slot.pending: return
        b64 = base64.b64encode(jpeg_data).decode()
        slot.pending = True; slot.infer_start = time.time()
        payload = slot.prepare(b64, self._params.get("prompt",""), self._params.get("max_tokens",512))
        logger.info("POST -> %s (%.0f KB)", slot.name, len(payload)/1024)
        self._router.send_raw_payload(payload)

    @Slot()
    def _on_interval_tick(self):
        if self._latest_jpeg: self._maybe_fire(self._reos, self._latest_jpeg)

    @Slot(str)
    def _on_perception_changed(self, model):
        """Enable/disable nvinfer interval dynamically."""
        if model == "yolo" and self._video_source and self._video_source._pipeline:
            nv = self._video_source._pipeline.get_by_name("nv_infer")
            if nv:
                nv.set_property("interval", 0)
                logger.info("nvinfer interval=0 (YOLO enabled)")
        elif model == "disable" and self._video_source and self._video_source._pipeline:
            nv = self._video_source._pipeline.get_by_name("nv_infer")
            if nv:
                nv.set_property("interval", 999999)
                logger.info("nvinfer interval=999999 (YOLO disabled)")

    @Slot(str)
    def _on_reasoning_changed(self, model): self._reos.activate(model)

    def _osd_probe(self, pad, info, user_data):
        gst_buf = info.get_buffer()
        if not gst_buf: return Gst.PadProbeReturn.OK
        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buf))
        if not batch_meta: return Gst.PadProbeReturn.OK
        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            try: frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration: break
            display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
            w = self._params.get("width", self._config.get("resolution_w",1920))
            h = self._params.get("height", self._config.get("resolution_h",1080))
            s = w / 1920.0; ds = self._config.get("dpi_scale",2.0)
            RIGHT_MARGIN = 0.04; label_idx = 0
            osd_w = int(w * 0.30)
            display_meta.num_labels = 1
            t0 = display_meta.text_params[0]; label_idx = 1
            t0.display_text = f"Sample:{self._osd_fps:.1f}fps | GPU:{self._osd_gpu:.0f}% CPU:{self._osd_cpu:.0f}% RAM:{self._osd_ram:.1f}G"
            t0.x_offset = int(w*(1-RIGHT_MARGIN)-osd_w); t0.y_offset = int(h*0.04)
            t0.font_params.font_name = "Monospace"
            t0.font_params.font_size = int(16*s)
            t0.font_params.font_color.set(1.0,1.0,1.0,1.0)
            t0.set_bg_clr = 1; t0.text_bg_clr.set(0.0,0.0,0.0,0.5)
            if not self._osd_logged or self._osd_logged != (w,h):
                self._osd_logged = (w,h)
                logger.info("OSD scale: %dx%d s=%.2f font=%d/%d top_right=(%d,%d)",
                             w,h,s,int(16*s),int(16*s),int(w*(1-RIGHT_MARGIN)-osd_w),int(h*0.04))

            # --- Override bbox colors per class (nvinfer → NvDsObjectMeta) ---
            yolo_overlay.override_bbox_colors(frame_meta)

            # --- Reasoning (caption) ---
            if self._reos.fill and self._reos.result:
                label_idx = self._reos.fill(display_meta, self._reos.result, w, h, s, ds, label_idx)
            display_meta.num_labels = label_idx
            pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
            try: l_frame = l_frame.next
            except StopIteration: break
        return Gst.PadProbeReturn.OK

    @Slot(str, str)
    def _on_inference_result(self, model, response_text):
        if self._video_source is None: return
        if model == self._reos.name: slot = self._reos
        else: return
        elapsed = (time.time() - slot.infer_start) * 1000
        slot.pending = False
        slot.result = {"response": response_text, "elapsed_ms": elapsed}
        logger.info("<- %s OK (%.0fms)", model, elapsed)
        logger.info("  %s", response_text.lstrip()[:200])
        self._interval_timer.start(self._params.get("interval", 1000))

    @Slot(str)
    def _on_router_error(self, msg):
        self._reos.pending = False
        logger.error("Router error: %s", msg)

    @Slot()
    def _on_monitor_tick(self):
        snap = read_stats()
        cpu_pct = compute_cpu_pct(self._prev_cpu_snap, snap)
        self._prev_cpu_snap = snap
        self._osd_fps = self._input_count / max(0.1, time.time()-self._fps_t0)
        self._osd_gpu = snap.get("gpu",0)
        self._osd_cpu = cpu_pct; self._osd_ram = snap.get("ram",0)
        logger.info("Sample:%.1ffps | GPU:%.0f%% CPU:%.0f%% RAM:%.1fG",
                     self._osd_fps, self._osd_gpu, self._osd_cpu, self._osd_ram)

    def _start_ram_monitor(self, threshold: float):
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "..", "util", "ram_monitor.py")
        if not os.path.exists(script):
            logger.warning("RAM monitor not found: %s", script); return
        env = os.environ.copy(); env["INVOKER_PID"] = str(os.getpid())
        self._ram_monitor = subprocess.Popen(["python3",script,str(threshold)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("RAM monitor started (threshold=%.1fGiB, pid=%d)", threshold, self._ram_monitor.pid)

    def closeEvent(self, event):
        self._interval_timer.stop(); self._mon_timer.stop()
        if self._video_source: self._video_source.stop()
        self._router.stop()
        if hasattr(self, "_ram_monitor"): self._ram_monitor.terminate()
        logger.info("Shutting down."); event.accept()
