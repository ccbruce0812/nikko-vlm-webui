"""
Kiosk main window: sidebar + video display.
Orchestrates video_source, router_client, overlay modules, system monitor.
Dual pipeline: perception (per-frame) + reasoning (interval-based).
"""
import base64
import logging
import time
import os

from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QPushButton, QSizePolicy, QVBoxLayout, QApplication
from PySide6.QtCore import QTimer, Slot, QThread, QBuffer, Qt
from PySide6.QtGui import QImage

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
    """Single-window kiosk GUI with dual perception/reasoning AI pipeline."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiosk VLM GUI")
        self.setWindowFlags(Qt.FramelessWindowHint)

        self._video_source = None
        self._router = RouterClient()

        self._interval_timer = QTimer(self)
        self._interval_timer.timeout.connect(self._on_interval_tick)
        self._mon_timer = QTimer(self)
        self._mon_timer.timeout.connect(self._on_monitor_tick)

        self._prev_cpu_snap = None
        self._params = {}
        self._latest_frame = None
        self._cli_perception = None
        self._cli_reasoning = None
        self._models_received = False

        self._input_count = 0
        self._fps_t0 = time.time()
        self._last_reason_ms = 0.0
        self._infer_start = 0.0
        self._payload_kb = 0

        # Perception
        self._yolo_response = None
        self._pending_perception = False
        self._percept_start = 0.0
        self._perception_active = True

        # Reasoning
        self._pending_inference = False
        self._reasoning_active = True

        self._sidebar = ControlSidebar()
        self._display = VideoDisplay()
        self._init_ui()
        self._connect_signals()

        if self._sidebar.camera_count() == 0:
            logger.error("No camera found — exiting")
            QTimer.singleShot(100, self.close)
            return

        self._router.start()
        QTimer.singleShot(500, self._router.fetch_models)
        QTimer.singleShot(5000, self._on_router_timeout)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._sidebar.setFixedWidth(self._sidebar.sizeHint().width())
        layout.addWidget(self._sidebar, 2)
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
        self._sidebar.perception_changed.connect(self._on_perception_changed)
        self._sidebar.reasoning_changed.connect(self._on_reasoning_changed)
        self._router.models_ready.connect(self._on_models_ready)
        self._router.result_ready.connect(self._on_inference_result)
        self._router.error_occurred.connect(self._on_router_error)

    # ----- models ready -----

    @Slot(list)
    def _on_models_ready(self, models):
        self._models_received = True
        self._sidebar.set_models(models)
        if not models:
            logger.warning("No models available")

        if self._cli_perception:
            idx = self._sidebar.perception_combo.findText(self._cli_perception)
            if idx >= 0:
                self._sidebar.perception_combo.setCurrentIndex(idx)
                logger.info("CLI: perception '%s' applied", self._cli_perception)
            self._cli_perception = None
        if self._cli_reasoning:
            idx = self._sidebar.reasoning_combo.findText(self._cli_reasoning)
            if idx >= 0:
                self._sidebar.reasoning_combo.setCurrentIndex(idx)
                logger.info("CLI: reasoning '%s' applied", self._cli_reasoning)
            self._cli_reasoning = None

    @Slot()
    def _on_router_timeout(self):
        if self._models_received:
            return

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

        self._input_count = 0
        self._fps_t0 = time.time()
        self._yolo_response = None

        self._video_source = VideoSource(camera_id, width, height)
        self._video_source.frame_ready.connect(self._on_frame)
        self._video_source.status_message.connect(self._on_video_status)
        self._video_source.start()

        self._display.set_res_fps(f"{width}x{height}")
        self._sidebar.set_streaming_state(True)
        self._mon_timer.start(5000)
        self._interval_timer.start(params["interval"])

        logger.info("Streaming %dx%d@%d perception=%s reasoning=%s interval=%dms",
                     width, height, fps, params["perception_model"],
                     params["reasoning_model"], params["interval"])

    @Slot()
    def _on_stop(self):
        self._interval_timer.stop()
        self._mon_timer.stop()
        self._pending_inference = False
        self._pending_perception = False
        self._yolo_response = None
        if self._video_source:
            self._video_source.stop()
            self._video_source = None
        self._latest_frame = None
        self._sidebar.set_streaming_state(False)
        self._display.set_overlay_text("")
        self._display.set_stats({})
        self._display.set_frame(QImage())
        self._display.repaint()

    @Slot(str)
    def _on_video_status(self, msg):
        logger.info(msg)

    # ----- frame pipeline -----

    @Slot(bytes, int, int)
    def _on_frame(self, data, w, h):
        if self._video_source is None:
            return
        qimage = QImage(data, w, h, w * 4, QImage.Format_RGBA8888)
        self._input_count += 1

        # Draw YOLO bbox from previous response
        annotated = qimage
        if self._yolo_response:
            fn = DRAW.get("yolo")
            if fn:
                annotated = fn(qimage.copy(), self._yolo_response)

        # Fire perception (fire-and-forget)
        self._maybe_fire_perception(qimage)

        # Display
        self._display.set_frame(annotated)

        # Save for reasoning tick
        self._latest_frame = qimage

    def _maybe_fire_perception(self, qimage):
        if self._pending_perception:
            return
        p_model = self._sidebar.perception_combo.currentText()
        if p_model == "disable" or p_model not in PREPARE:
            return
        self._pending_perception = True
        self._percept_start = time.time()
        fn = PREPARE[p_model]
        payload = fn(qimage, self._params.get("prompt", ""),
                     self._params.get("max_tokens", 512))
        logger.info("POST → %s (%.0f KB)", p_model, len(payload) / 1024)
        self._router.send_raw_payload(payload)

    # ----- reasoning interval tick -----

    @Slot()
    def _on_interval_tick(self):
        if self._latest_frame is None or self._latest_frame.isNull():
            return
        if self._pending_inference:
            return
        r_model = self._sidebar.reasoning_combo.currentText()
        if r_model == "disable" or r_model not in PREPARE:
            return
        fn = PREPARE[r_model]
        payload = fn(self._latest_frame, self._params.get("prompt", ""),
                     self._params.get("max_tokens", 512))
        self._payload_kb = len(payload) / 1024
        logger.info("POST → %s (%.0f KB)", r_model, self._payload_kb)
        self._infer_start = time.time()
        self._pending_inference = True
        self._router.send_raw_payload(payload)

    # ----- model change handlers -----

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
            self._display.set_overlay_text("")

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
            p_elapsed = (t_now - self._percept_start) * 1000
            logger.info("← %s OK (%.0fms)", model, p_elapsed)
            self._yolo_response = response_text
            if self._latest_frame and not self._latest_frame.isNull():
                fn = DRAW.get("yolo")
                if fn:
                    annotated = fn(self._latest_frame.copy(), response_text)
                    self._display.set_frame(annotated)
        else:
            self._pending_inference = False
            if not self._reasoning_active:
                return
            self._last_reason_ms = (t_now - self._infer_start) * 1000
            response_text = response_text.lstrip()
            logger.info("← %s OK (%.0fms)", model, self._last_reason_ms)
            self._display.set_overlay_text(
                f"Elapsed: {self._last_reason_ms:.0f}ms\n{response_text}")
            self._interval_timer.start(self._params.get("interval", 1000))

    # ----- errors -----

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
        in_fps = self._input_count / max(0.1, time.time() - self._fps_t0)
        gpu = snap.get("gpu", 0)
        ram = snap.get("ram", 0)
        logger.info("FPS:%.1f | GPU:%.0f%% CPU:%.0f%% RAM:%.1fG",
                     in_fps, gpu, cpu_pct, ram)
        self._display.set_stats({
            "fps": in_fps, "gpu": gpu, "cpu": cpu_pct, "ram": ram,
            "reason": self._last_reason_ms,
        })

    # ----- CLI args -----

    def apply_cli_args(self, camera_id: int, width: int, height: int, fps: int,
                       perception_model: str, reasoning_model: str,
                       interval: int, prompt: str, max_tokens: int,
                       router_url: str, ram_threshold: float,
                       auto_start: bool = False):
        sidebar = self._sidebar

        sidebar.perception_combo.blockSignals(True)
        p_idx = sidebar.perception_combo.findText(perception_model)
        if p_idx >= 0:
            sidebar.perception_combo.setCurrentIndex(p_idx)
        else:
            self._cli_perception = perception_model
        sidebar.perception_combo.blockSignals(False)

        sidebar.reasoning_combo.blockSignals(True)
        r_idx = sidebar.reasoning_combo.findText(reasoning_model)
        if r_idx >= 0:
            sidebar.reasoning_combo.setCurrentIndex(r_idx)
        else:
            self._cli_reasoning = reasoning_model
        sidebar.reasoning_combo.blockSignals(False)

        sidebar.interval_edit.setText(str(interval))
        sidebar.prompt_edit.setPlainText(prompt)
        sidebar.tokens_edit.setText(str(max_tokens))

        if router_url != self._router._url:
            self._router._url = router_url
            sidebar.reasoning_combo.clear()
            sidebar.reasoning_combo.addItem("disable")
            sidebar.perception_combo.clear()
            sidebar.perception_combo.addItem("disable")
            self._router.fetch_models()

        self._start_ram_monitor(ram_threshold)

        if auto_start:
            logger.info("CLI: auto-start %dx%d@%d perception=%s reasoning=%s interval=%d",
                         width, height, fps, perception_model, reasoning_model, interval)
            dev_id = sidebar.camera_combo.currentData() or 0
            self._on_start(int(dev_id), width, height)

    # ----- RAM monitor -----

    def _start_ram_monitor(self, threshold: float):
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "..", "..", "util", "ram_monitor.py")
        if not os.path.exists(script):
            logger.warning("RAM monitor not found: %s", script)
            return
        env = os.environ.copy()
        env["INVOKER_PID"] = str(os.getpid())
        self._ram_monitor = subprocess.Popen(
            ["python3", script, str(threshold)],
            env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        logger.info("RAM monitor started (threshold=%.1fGiB, pid=%d)", threshold, self._ram_monitor.pid)

    def closeEvent(self, event):
        self._interval_timer.stop()
        self._mon_timer.stop()
        if self._video_source:
            self._video_source.stop()
        self._router.stop()
        logger.info("Shutting down.")
        event.accept()
