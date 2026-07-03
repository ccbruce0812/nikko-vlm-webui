"""
Kiosk main window: sidebar (1/6) + video display (5/6).
Orchestrates video_source, router_client, overlay modules, and system monitor.
"""
import base64
import logging

from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QWidget
from PySide6.QtCore import QTimer, Slot, QThread, QBuffer
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

logger = logging.getLogger(__name__)


class KioskWindow(QMainWindow):
    """Single-window kiosk GUI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiosk VLM GUI")

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
        layout.addWidget(self._sidebar, 1)
        layout.addWidget(self._display, 5)

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
        self._params = params

        self._video_source = VideoSource(camera_id, width, height)
        self._video_source.frame_ready.connect(self._on_frame)
        self._video_source.status_message.connect(
            lambda msg: logger.info("Video: %s", msg))
        self._video_source.start()

        self._display.set_res_fps(f"{width}x{height}")
        self._sidebar.set_streaming_state(True)

        interval_ms = max(1, params["interval"]) * 1000
        self._interval_timer.start(interval_ms)

    @Slot()
    def _on_stop(self):
        self._interval_timer.stop()
        if self._video_source:
            self._video_source.stop()
            self._video_source = None
        self._sidebar.set_streaming_state(False)
        self._display.set_frame(QImage())
        self._display.set_overlay_frame(QImage())

    # ----- system monitor (no jetson-stats) -----

    @Slot()
    def _on_monitor_tick(self):
        snap = read_stats()
        cpu = compute_cpu_pct(self._prev_cpu_snap, snap)
        self._prev_cpu_snap = snap
        self._display.set_stats({
            "gpu": snap.get("gpu", 0),
            "cpu": cpu,
            "ram": snap.get("ram", 0),
            "vram": snap.get("vram", 0),
        })

    # ----- frame pipeline -----

    @Slot(bytes, int, int)
    def _on_frame(self, data, w, h):
        qimage = QImage(data, w, h, w * 4, QImage.Format_RGBA8888)
        self._latest_frame = qimage
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

        fn = PREPARE.get(model)
        if fn is None:
            return
        payload = fn(self._latest_frame, params["prompt"], params["max_tokens"])

        self._pending_inference = True
        self._router.send_raw_payload(payload)

    # ----- inference result -----

    @Slot(str, str)
    def _on_inference_result(self, model, response_text):
        self._pending_inference = False

        if self._latest_frame is None:
            return

        fn = DRAW.get(model)
        if fn:
            annotated = fn(self._latest_frame, response_text)
            self._display.set_overlay_frame(annotated)

        params = self._sidebar.get_params()
        interval_ms = max(1, params["interval"]) * 1000
        self._interval_timer.start(interval_ms)

    # ----- errors -----

    @Slot(str)
    def _on_router_error(self, msg):
        self._pending_inference = False
        logger.error("Router: %s", msg)

    # ----- cleanup -----

    def closeEvent(self, event):
        self._interval_timer.stop()
        self._mon_timer.stop()
        if self._video_source:
            self._video_source.stop()
        self._router.stop()
        event.accept()
