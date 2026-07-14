"""
Kiosk main window with nvdsosd GPU overlay (no Qt OSD).
nveglglessink embedded via sync bus handler.
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
from src.modules import yolo_overlay, reason2_overlay, moondream2_overlay

PREPARE = {
    "yolo": yolo_overlay.prepare_payload,
    "reason2": reason2_overlay.prepare_payload,
    "moondream2": moondream2_overlay.prepare_payload,
}

logger = logging.getLogger("gui")


class KioskWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.setWindowTitle("Kiosk VLM GUI")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self._config = config

        self._video_source = None
        self._router = RouterClient(config["router_url"])
        self._interval_timer = QTimer(self)
        self._interval_timer.timeout.connect(self._on_interval_tick)
        self._mon_timer = QTimer(self)
        self._mon_timer.timeout.connect(self._on_monitor_tick)

        self._params = {}
        self._input_count = 0
        self._fps_t0 = time.time()
        self._last_reason_ms = 0.0
        self._infer_start = 0.0
        self._yolo_infer_start = 0.0
        self._prev_cpu_snap = None
        self._latest_jpeg = b""

        # Perception
        self._yolo_response = None
        self._pending_perception = False
        self._perception_active = config["perception_default"] != "disable"

        # Reasoning
        self._pending_inference = False
        self._reasoning_active = config["reasoning_default"] != "disable"

        # OSD state (read by nvdsosd probe)
        self._osd_fps = 0.0
        self._osd_gpu = 0.0
        self._osd_cpu = 0.0
        self._osd_ram = 0.0
        self._osd_caption = ""  # reasoning caption

        self._sidebar = ControlSidebar(config)
        self._init_ui()
        self._connect_signals()
        self._router.start()
        self._start_ram_monitor(config["ram_threshold"])
        if config["auto_start"]:
            QTimer.singleShot(500, self._cli_auto_start)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
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

    # ----- start / stop -----

    def _cli_auto_start(self):
        dev_id = self._sidebar.camera_combo.currentData() or 0
        self._on_start(dev_id, self._config["resolution_w"],
                       self._config["resolution_h"])

    @Slot(int, int, int)
    def _on_start(self, camera_id, width, height):
        params = self._sidebar.get_params()
        self._params = params
        params["width"] = width
        params["height"] = height
        res = self._sidebar.res_combo.currentText()
        _, _, fps = VideoSource.parse_resolution(res)

        self._input_count = 0
        self._fps_t0 = time.time()
        self._yolo_response = None
        self._latest_jpeg = b""

        # Build pipeline in main thread, set sync_handler + nvdsosd probe BEFORE play
        vs = VideoSource(camera_id, width, height, fps)
        pipeline_str = vs._build_pipeline()
        pipeline = Gst.parse_launch(pipeline_str)

        bus = pipeline.get_bus()
        bus.set_sync_handler(self._bus_sync_handler)

        osd = pipeline.get_by_name("osd")
        if osd:
            osd.get_static_pad("sink").add_probe(
                Gst.PadProbeType.BUFFER, self._osd_probe, None)

        self._video_source = VideoSource(camera_id, width, height, fps,
                                          pipeline=pipeline)
        self._video_source.frame_for_infer.connect(self._on_frame_for_infer)
        self._video_source.status_message.connect(self._on_video_status)
        self._video_source.start()

        self._sidebar.set_streaming_state(True)
        self._mon_timer.start(5000)
        self._interval_timer.start(params["interval"])

        logger.info("Streaming %dx%d@%d perception=%s reasoning=%s interval=%dms",
                     width, height, fps, params["perception_model"],
                     params["reasoning_model"], params["interval"])

    def _bus_sync_handler(self, bus, message):
        if GstVideo.is_video_overlay_prepare_window_handle_message(message):
            message.src.set_window_handle(int(self._video_widget.winId()))
            return Gst.BusSyncReply.DROP
        return Gst.BusSyncReply.PASS

    @Slot()
    def _on_stop(self):
        self._interval_timer.stop()
        self._mon_timer.stop()
        self._pending_inference = False
        self._pending_perception = False
        self._yolo_response = None
        self._osd_logged = None
        if self._video_source:
            self._video_source.stop()
            self._video_source = None
        self._sidebar.set_streaming_state(False)

    @Slot(str)
    def _on_video_status(self, msg):
        logger.info(msg)

    # ----- inference frame -----

    @Slot(bytes)
    def _on_frame_for_infer(self, jpeg_data):
        if self._video_source is None:
            return
        self._input_count += 1
        self._latest_jpeg = jpeg_data
        self._maybe_fire_perception(jpeg_data)

    def _maybe_fire_perception(self, jpeg_data):
        if self._pending_perception or not self._perception_active:
            return
        p_model = self._sidebar.perception_combo.currentText()
        if p_model == "disable" or p_model not in PREPARE:
            return
        self._pending_perception = True
        self._yolo_infer_start = time.time()
        fn = PREPARE[p_model]
        b64 = base64.b64encode(jpeg_data).decode()
        payload = fn(b64, self._params.get("prompt", ""),
                     self._params.get("max_tokens", 512))
        logger.info("POST -> %s (%.0f KB)", p_model, len(payload) / 1024)
        self._router.send_raw_payload(payload)

    # ----- reasoning interval -----

    @Slot()
    def _on_interval_tick(self):
        if self._video_source is None:
            return
        if self._pending_inference or not self._reasoning_active:
            return
        if not self._latest_jpeg:
            return
        r_model = self._sidebar.reasoning_combo.currentText()
        if r_model == "disable" or r_model not in PREPARE:
            return
        self._pending_inference = True
        self._infer_start = time.time()
        fn = PREPARE[r_model]
        b64 = base64.b64encode(self._latest_jpeg).decode()
        payload = fn(b64, self._params.get("prompt", ""),
                     self._params.get("max_tokens", 512))
        logger.info("POST -> %s (%.0f KB)", r_model, len(payload) / 1024)
        self._router.send_raw_payload(payload)

    # ----- model change -----

    @Slot(str)
    def _on_perception_changed(self, model):
        self._perception_active = (model != "disable")
        if model == "disable":
            self._pending_perception = False
            self._yolo_response = None

    @Slot(str)
    def _on_reasoning_changed(self, model):
        self._reasoning_active = (model != "disable")
        if model == "disable":
            self._pending_inference = False
            self._osd_caption = ""

    # ----- nvdsosd probe (per-frame GPU OSD) -----

    def _osd_probe(self, pad, info, user_data):
        gst_buf = info.get_buffer()
        if not gst_buf:
            return Gst.PadProbeReturn.OK
        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buf))
        if not batch_meta:
            return Gst.PadProbeReturn.OK
        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break
            display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
            w = self._params.get("width", self._config.get("resolution_w", 1920))
            h = self._params.get("height", self._config.get("resolution_h", 1080))
            s = w / 1920.0
            ds = self._config.get("dpi_scale", 2.0)
            RIGHT_MARGIN = 0.04
            BOTTOM_MARGIN = 0.12
            label_idx = 0

            # --- BBOX detection ---
            detections = []
            if self._yolo_response:
                try:
                    detections = json.loads(self._yolo_response)
                except Exception:
                    pass
            if detections:
                import math
                INFER_MAX = 1280
                max_dim = max(w, h)
                iw = ih = INFER_MAX
                if max_dim >= INFER_MAX:
                    ratio = INFER_MAX / max_dim
                    iw, ih = int(w * ratio), int(h * ratio)
                sx = w / iw
                sy = h / ih

            # --- Total label count: OSD(1) + bbox labels(n) + caption(1) ---
            n_bbox_labels = len(detections)
            has_caption = bool(self._osd_caption)
            # Compute caption lines first (for accurate total_labels)
            n_caption_lines = 0
            if has_caption:
                cap_w = int(w * 0.95)
                chars_per_line = 150
                # Split by newline segments, then word-wrap each segment
                segments = self._osd_caption.split("\n")
                lines = []
                for segment in segments:
                    seg = segment.strip()
                    while len(seg) > chars_per_line:
                        lines.append(seg[:chars_per_line])
                        seg = seg[chars_per_line:]
                    if seg:
                        lines.append(seg)
                lines = lines[:5]
                n_caption_lines = len(lines)
            total_labels = 1 + n_bbox_labels + n_caption_lines
            display_meta.num_labels = total_labels

            # --- 1. Top-right OSD (20% image width, right margin 4%, top margin 4%) ---
            osd_w = int(w * 0.30)
            t0 = display_meta.text_params[label_idx]; label_idx += 1
            t0.display_text = (
                f"FPS:{self._osd_fps:.1f} | "
                f"GPU:{self._osd_gpu:.0f}% "
                f"CPU:{self._osd_cpu:.0f}% "
                f"RAM:{self._osd_ram:.1f}G"
            )
            t0.x_offset = int(w * (1 - RIGHT_MARGIN) - osd_w)
            t0.y_offset = int(h * 0.04)
            t0.font_params.font_name = "Monospace"
            t0.font_params.font_size = int(8 * s * ds)
            t0.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            t0.set_bg_clr = 1
            t0.text_bg_clr.set(0.0, 0.0, 0.0, 0.5)

            # --- 2. BBOX labels (inside box top-left, no background) ---
            if detections:
                display_meta.num_rects = n_bbox_labels
                for di, det in enumerate(detections):
                    cls_id = det.get("class", di)
                    r = cls_id * 0.6180339887  # golden ratio
                    cr = (r * 3.7) % 1.0
                    cg = (r * 7.3) % 1.0
                    cb = (r * 11.3) % 1.0

                    rect = display_meta.rect_params[di]
                    bbox = det.get("bbox", [0, 0, 0, 0])
                    rect.left = int(bbox[0] * sx)
                    rect.top = int(bbox[1] * sy)
                    rect.width = int((bbox[2] - bbox[0]) * sx)
                    rect.height = int((bbox[3] - bbox[1]) * sy)
                    rect.border_width = int(3 * s)
                    rect.border_color.set(cr, cg, cb, 1.0)
                    rect.has_bg_color = 0

                    tp = display_meta.text_params[label_idx]; label_idx += 1
                    tp.display_text = (
                        f"{det.get('name','obj')} {det.get('confidence',0):.2f}"
                    )
                    tp.x_offset = int(rect.left) + int(2 * s)
                    tp.y_offset = int(rect.top) + int(2 * s)
                    tp.font_params.font_name = "Monospace"
                    tp.font_params.font_size = int(8 * s * ds)
                    tp.font_params.font_color.set(cr, cg, cb, 1.0)
                    tp.set_bg_clr = 0

            # --- 3. Caption (95% image width, centered, bottom margin 3%) ---
            if has_caption:
                cap_line_h = int(14 * s * ds)
                cap_margin = int(h * BOTTOM_MARGIN)
                cap_x = int((w - cap_w) // 2)
                cap_text_h = cap_line_h * len(lines)
                cap_y = int(h - cap_margin - cap_text_h)

                # Background rect
                display_meta.num_rects += 1
                bg = display_meta.rect_params[display_meta.num_rects - 1]
                bg.left = cap_x
                bg.top = cap_y
                bg.width = cap_w
                bg.height = cap_text_h + cap_margin
                bg.border_width = 0
                bg.has_bg_color = 1
                bg.bg_color.set(0.0, 0.0, 0.0, 0.6)

                for li, line in enumerate(lines):
                    cap = display_meta.text_params[label_idx]; label_idx += 1
                    cap.display_text = line
                    cap.x_offset = cap_x + int(4 * s)
                    cap.y_offset = cap_y + int(2 * s) + li * cap_line_h
                    cap.font_params.font_name = "Monospace"
                    cap.font_params.font_size = int(8 * s * ds)
                    cap.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
                    cap.set_bg_clr = 1
                    cap.text_bg_clr.set(0.0, 0.0, 0.0, 0.6)

            pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
            try:
                l_frame = l_frame.next
            except StopIteration:
                break
        return Gst.PadProbeReturn.OK


    # ----- inference result -----

    @Slot(str, str)
    def _on_inference_result(self, model, response_text):
        if self._video_source is None:
            return
        t_now = time.time()
        if model == "yolo":
            self._pending_perception = False
            if not self._perception_active:
                return
            e_ms = (time.time() - self._yolo_infer_start) * 1000
            logger.info("<- %s OK (%.0fms)", model, e_ms)
            self._yolo_response = response_text
        else:
            self._pending_inference = False
            if not self._reasoning_active:
                return
            self._last_reason_ms = (t_now - self._infer_start) * 1000
            response_text = response_text.lstrip()
            self._osd_caption = f"Elapsed: {self._last_reason_ms:.0f}ms\n{response_text}"
            logger.info("<- %s OK (%.0fms)", model, self._last_reason_ms)
            logger.info("  %s", response_text[:200])
            self._interval_timer.start(self._params.get("interval", 1000))

    @Slot(str)
    def _on_router_error(self, msg):
        self._pending_inference = False
        self._pending_perception = False
        logger.error("Router error: %s", msg)

    # ----- monitor -----

    @Slot()
    def _on_monitor_tick(self):
        snap = read_stats()
        cpu_pct = compute_cpu_pct(self._prev_cpu_snap, snap)
        self._prev_cpu_snap = snap
        self._osd_fps = self._input_count / max(0.1, time.time() - self._fps_t0)
        self._osd_gpu = snap.get("gpu", 0)
        self._osd_cpu = cpu_pct
        self._osd_ram = snap.get("ram", 0)
        logger.info("FPS:%.1f | GPU:%.0f%% CPU:%.0f%% RAM:%.1fG",
                     self._osd_fps, self._osd_gpu, self._osd_cpu, self._osd_ram)

    # ----- RAM monitor -----

    def _start_ram_monitor(self, threshold: float):
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "..",
                              "util", "ram_monitor.py")
        if not os.path.exists(script):
            logger.warning("RAM monitor not found: %s", script)
            return
        env = os.environ.copy()
        env["INVOKER_PID"] = str(os.getpid())
        self._ram_monitor = subprocess.Popen(
            ["python3", script, str(threshold)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("RAM monitor started (threshold=%.1fGiB, pid=%d)",
                     threshold, self._ram_monitor.pid)

    def closeEvent(self, event):
        self._interval_timer.stop()
        self._mon_timer.stop()
        if self._video_source:
            self._video_source.stop()
        self._router.stop()
        if hasattr(self, "_ram_monitor"):
            self._ram_monitor.terminate()
        logger.info("Shutting down.")
        event.accept()
