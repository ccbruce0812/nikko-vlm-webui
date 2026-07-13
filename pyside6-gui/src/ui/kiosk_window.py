"""
Kiosk main window: sidebar + video display.
Dual pipeline: perception (per-frame) + reasoning (interval-based).
"""
import logging, time, os

from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QSizePolicy, QVBoxLayout
from PySide6.QtCore import QTimer, Slot, Qt
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

        self._prev_cpu_snap = None
        self._params = {}
        self._latest_frame = None

        self._input_count = 0
        self._fps_t0 = time.time()
        self._last_reason_ms = 0.0
        self._infer_start = 0.0

        # Perception
        self._yolo_response = None
        self._pending_perception = False
        self._percept_start = 0.0
        self._perception_active = config["perception_default"] != "disable"

        # Reasoning
        self._pending_inference = False
        self._reasoning_active = config["reasoning_default"] != "disable"

        self._sidebar = ControlSidebar(config)
        self._display = VideoDisplay()
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
        self._router.result_ready.connect(self._on_inference_result)
        self._router.error_occurred.connect(self._on_router_error)

    # ----- start / stop -----

    def _cli_auto_start(self):
        dev_id = self._sidebar.camera_combo.currentData() or 0
        w = self._config["resolution_w"]
        h = self._config["resolution_h"]
        self._on_start(dev_id, w, h)

    @Slot(int, int, int)
    def _on_start(self, camera_id, width, height):
        params = self._sidebar.get_params()
        self._params = params
        self._params["width"] = width
        self._params["height"] = height
        res_text = self._sidebar.res_combo.currentText()
        _, _, fps = VideoSource.parse_resolution(res_text)

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

    # ----- frame pipeline: perception per-frame -----

    @Slot(bytes, int, int)
    def _on_frame(self, data, w, h):
        if self._video_source is None:
            return
        qimage = QImage(data, w, h, w * 4, QImage.Format_RGBA8888)
        self._input_count += 1

        annotated = qimage
        if self._yolo_response:
            fn = DRAW.get("yolo")
            if fn:
                annotated = fn(qimage.copy(), self._yolo_response)

        self._maybe_fire_perception(qimage)
        self._display.set_frame(annotated)
        self._latest_frame = qimage

    def _maybe_fire_perception(self, qimage):
        if self._pending_perception or not self._perception_active:
            return
        p_model = self._sidebar.perception_combo.currentText()
        if p_model == "disable" or p_model not in PREPARE:
            return
        self._pending_perception = True
        self._percept_start = time.time()
        fn = PREPARE[p_model]
        payload = fn(qimage, self._params.get("prompt", ""),
                     self._params.get("max_tokens", 512))
        logger.info("POST → %s (%.0f KB, %.0fms prep)", p_model, len(payload) / 1024, (time.time() - self._percept_start) * 1000)
        self._router.send_raw_payload(payload)

    # ----- reasoning interval tick -----

    @Slot()
    def _on_interval_tick(self):
        if self._latest_frame is None or self._latest_frame.isNull():
            return
        if self._pending_inference or not self._reasoning_active:
            return
        r_model = self._sidebar.reasoning_combo.currentText()
        if r_model == "disable" or r_model not in PREPARE:
            return
        fn = PREPARE[r_model]
        payload = fn(self._latest_frame, self._params.get("prompt", ""),
                     self._params.get("max_tokens", 512))
        logger.info("POST → %s (%.0f KB, %.0fms prep)", r_model, len(payload) / 1024, (time.time() - self._infer_start) * 1000)
        self._infer_start = time.time()
        self._pending_inference = True
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
            logger.info("  %s", response_text[:200])
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
            logger.info("  %s", response_text[:200])
            self._display.set_overlay_text(
                f"Elapsed: {self._last_reason_ms:.0f}ms\n{response_text}")
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
        in_fps = self._input_count / max(0.1, time.time() - self._fps_t0)
        gpu = snap.get("gpu", 0)
        ram = snap.get("ram", 0)
        logger.info("FPS:%.1f | GPU:%.0f%% CPU:%.0f%% RAM:%.1fG",
                     in_fps, gpu, cpu_pct, ram)
        self._display.set_stats({
            "fps": in_fps, "gpu": gpu, "cpu": cpu_pct, "ram": ram,
            "reason": self._last_reason_ms,
        })

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
