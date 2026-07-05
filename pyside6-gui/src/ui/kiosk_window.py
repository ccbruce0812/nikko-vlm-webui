"""
Kiosk main window: sidebar (1/6) + video display (5/6).
Orchestrates video_source, router_client, overlay modules, and system monitor.
"""
import base64
import logging
import time

from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QPushButton, QSizePolicy
from PySide6.QtCore import QTimer, Slot, QThread, QBuffer, Qt
from PySide6.QtGui import QImage, QShortcut, QKeySequence

from src.ui.control_sidebar import ControlSidebar
from src.ui.video_display import VideoDisplay
from src.modules.video_source import VideoSource
from src.modules.router_client import RouterClient
from src.modules.system_monitor import read_stats, compute_cpu_pct
from src.modules import yolo_overlay, reason2_overlay, moondream2_overlay

PREPARE = {
    "yolo": yolo_overlay.prepare_payload,
    "reason2": reason2_overlay.prepare_payload,
    "moondream2": moondream2_overlay.prepare_payload,
}
DRAW = {
    "yolo": yolo_overlay.draw_overlay,
    "reason2": reason2_overlay.draw_overlay,
    "moondream2": moondream2_overlay.draw_overlay,
}

logger = logging.getLogger("gui")


class KioskWindow(QMainWindow):
    """Single-window kiosk GUI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiosk VLM GUI")

        # Global shortcuts
        QShortcut(QKeySequence("Escape"), self, self.close)

        # Modules
        self._video_source = None
        self._router = RouterClient()

        # State
        self._interval_timer = QTimer(self)
        self._interval_timer.setSingleShot(False)
        self._interval_timer.timeout.connect(self._on_interval_tick)
        self._mon_timer = QTimer(self)
        self._mon_timer.timeout.connect(self._on_monitor_tick)
        self._mon_timer.start(5000)
        self._prev_cpu_snap = None
        self._params = {}
        self._latest_frame = None
        self._pending_inference = False

        # FPS & timing (like nogui)
        self._input_count = 0
        self._fps_t0 = time.time()
        self._prepare_ms = 0.0
        self._reason_ms = 0.0
        self._overlay_ms = 0.0
        self._infer_count = 0
        self._infer_start = 0.0
        self._payload_kb = 0
        self._last_overlay = ""
        self._yolo_response = None

        # UI
        self._sidebar = ControlSidebar()
        self._display = VideoDisplay()

        self._init_ui()
        self._connect_signals()

        # Start background
        self._router.start()

        QTimer.singleShot(500, self._router.fetch_models)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar.setFixedWidth(self._sidebar.sizeHint().width())
        layout.addWidget(self._sidebar, 2)

        # Video area: center the display widget
        from PySide6.QtWidgets import QVBoxLayout
        video_wrap = QWidget()
        vw = QVBoxLayout(video_wrap)
        vw.setContentsMargins(0, 0, 0, 0)
        vw.setAlignment(Qt.AlignCenter)
        self._display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vw.addWidget(self._display)
        layout.addWidget(video_wrap, 3)

    def _connect_signals(self):
        self._sidebar.start_clicked.connect(self._on_start)
        self._sidebar.stop_clicked.connect(self._on_stop)
        self._sidebar.quit_clicked.connect(self.close)
        self._router.models_ready.connect(self._sidebar.set_models)
        self._router.result_ready.connect(self._on_inference_result)
        self._router.error_occurred.connect(self._on_router_error)

    # ----- start / stop -----

    @Slot(int, int, int)
    def _on_start(self, camera_id, width, height):
        params = self._sidebar.get_params()
        params["width"] = width
        params["height"] = height
        res_text = self._sidebar.res_combo.currentText()
        _, _, fps = VideoSource.parse_resolution(res_text)
        params["fps"] = fps
        self._params = params

        # Reset all counters
        self._input_count = 0
        self._fps_t0 = time.time()
        self._prepare_ms = 0.0
        self._reason_ms = 0.0
        self._overlay_ms = 0.0
        self._infer_count = 0
        self._yolo_response = None

        self._video_source = VideoSource(camera_id, width, height)
        self._video_source.frame_ready.connect(self._on_frame)
        self._video_source.status_message.connect(
            lambda msg: logger.info(msg))
        self._video_source.start()

        self._display.set_res_fps(f"{width}x{height}")
        self._sidebar.set_streaming_state(True)

        interval_ms = max(1, params["interval"]) * 1000
        self._interval_timer.start(interval_ms)

        logger.info("Streaming %dx%d@%d — interval %ds, model %s",
                     width, height, fps, params["interval"], params["model"])

    @Slot()
    def _on_stop(self):
        self._interval_timer.stop()
        if self._video_source:
            self._video_source.stop()
            self._video_source = None
        self._sidebar.set_streaming_state(False)
        self._display.set_frame(QImage())

    def _on_toggle(self):
        """Toggle streaming."""
        if self._video_source is None:
            cam_id = self._sidebar.camera_combo.currentData() or 0
            w, h, _ = VideoSource.parse_resolution(
                self._sidebar.resolution_combo.currentText())
            self._on_start(cam_id, w, h)
        else:
            self._on_stop()

    # ----- system monitor (no jetson-stats) -----

    @Slot()
    def _on_monitor_tick(self):
        snap = read_stats()
        cpu_pct = compute_cpu_pct(self._prev_cpu_snap, snap)
        self._prev_cpu_snap = snap

        elapsed = time.time() - self._fps_t0
        in_fps = self._input_count / max(0.1, elapsed)

        n = max(1, self._infer_count)
        reas = self._reason_ms / n
        over = self._overlay_ms / n

        gpu = snap.get("gpu", 0)
        vram = snap.get("vram", 0)
        ram = snap.get("ram", 0)

        logger.info(
            "in:%.1f | reason:%.0fms overlay:%.0fms | "
            "GPU:%.0f%% CPU:%.0f%% RAM:%.1fG VRAM:%.1fG",
            in_fps, reas, over, gpu, cpu_pct, ram, vram)

        self._display.set_stats({
            "fps": in_fps,
            "gpu": gpu,
            "cpu": cpu_pct,
            "ram": ram,
            "vram": vram,
            "reason": reas,
            "overlay": over,
        })

    # ----- frame pipeline -----

    @Slot(bytes, int, int)
    def _on_frame(self, data, w, h):
        qimage = QImage(data, w, h, w * 4, QImage.Format_RGBA8888)
        self._latest_frame = qimage
        self._input_count += 1

        # Draw YOLO boxes on every frame for tracking effect
        if self._yolo_response:
            fn = DRAW.get("yolo")
            if fn:
                annotated = fn(qimage.copy(), self._yolo_response)
                self._display.set_frame(annotated)
                return

        self._display.set_frame(qimage)

    # ----- interval tick -----

    @Slot()
    def _on_interval_tick(self):
        if self._latest_frame is None or self._latest_frame.isNull():
            return
        if self._pending_inference:
            return

        params = self._sidebar.get_params()
        model = params["model"]
        if not model:
            return

        if model != "yolo":
            self._yolo_response = None

        fn = PREPARE.get(model)
        if fn is None:
            return
        t0 = time.time()
        payload = fn(self._latest_frame, params["prompt"], params["max_tokens"])
        self._prepare_ms += (time.time() - t0) * 1000
        self._payload_kb = len(payload) / 1024

        logger.info("POST /v1/chat/completions → %s (%.0f KB)", model, self._payload_kb)
        self._infer_start = time.time()
        self._pending_inference = True
        self._router.send_raw_payload(payload)

    # ----- inference result -----

    @Slot(str, str)
    def _on_inference_result(self, model, response_text):
        self._pending_inference = False
        t_now = time.time()
        self._reason_ms += (t_now - self._infer_start) * 1000
        self._infer_count += 1
        self._last_overlay = response_text

        t0 = time.time()
        fn = DRAW.get(model)
        if fn:
            frame = self._latest_frame
            if frame and not frame.isNull():
                annotated = fn(frame.copy(), response_text)
                self._display.set_frame(annotated)

        if model != "yolo":
            self._display.set_overlay_text(response_text)
        else:
            self._display.set_overlay_text("")
            self._yolo_response = response_text
        self._display.repaint()
        self._overlay_ms += (time.time() - t0) * 1000

        params = self._sidebar.get_params()
        interval_ms = max(1, params["interval"]) * 1000
        self._interval_timer.start(interval_ms)

    # ----- errors -----

    @Slot(str)
    def _on_router_error(self, msg):
        self._pending_inference = False
        logger.error("Router: %s", msg)

    # ----- keyboard -----

    def keyPressEvent(self, event):
        """Alt+Q = quit, Alt+S = toggle (Qt/xcb on Jetson)."""
        if event.key() == Qt.Key_Q and (event.modifiers() & Qt.AltModifier):
            self.close()
        elif event.key() == Qt.Key_S and (event.modifiers() & Qt.AltModifier):
            self._on_toggle()
        else:
            super().keyPressEvent(event)

    # ----- cleanup -----

    def closeEvent(self, event):
        self._interval_timer.stop()
        self._mon_timer.stop()
        if self._video_source:
            self._video_source.stop()
        self._router.stop()
        logger.info("Shutting down.")
        event.accept()
