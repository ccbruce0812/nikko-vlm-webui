import logging
import time
from PySide6.QtCore import Slot, QTimer, Qt, QEvent
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QMessageBox
from PySide6.QtGui import QImage

from src.ui.control_panel import ControlPanel
from src.ui.ai_config_panel import AIConfigPanel
from src.ui.video_canvas import VideoCanvas
from src.modules.video_worker import VideoWorker
from src.modules.router_client import RouterClient
from src.modules.yolo_overlay import draw_overlay as yolo_draw_overlay
from src.modules.system_monitor import read_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [gui] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

ROUTER_URL = "http://localhost:8080"
YOLO_INTERVAL_MS = 500


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jetson VLM Control System")

        self.video_worker = None
        self._latest_frame = None
        self._is_stopping = False

        # Router client (HTTP API)
        self._router = RouterClient(ROUTER_URL)

        # YOLO state
        self._yolo_available = False
        self._yolo_paused = False
        self._yolo_response = None
        self._yolo_timer = QTimer(self)
        self._yolo_timer.timeout.connect(self._on_yolo_tick)

        # VLM state
        self._vlm_models = []

        # Counters / timing
        self._input_count = 0
        self._fps_t0 = time.time()
        self._reason_ms = 0.0
        self._overlay_ms = 0.0
        self._infer_count = 0
        self._infer_start = 0.0
        self._payload_kb = 0
        self._pending_inference = False

        # Monitor timer (5s)
        self._mon_timer = QTimer(self)
        self._mon_timer.timeout.connect(self._on_monitor_tick)

        # UI
        self.video_canvas = VideoCanvas()
        self.video_canvas.setWindowTitle("Main Stream")
        self._init_ui()
        self._connect_signals()

        # Start Router
        self._router.start()
        QTimer.singleShot(500, self._router.fetch_models)

    def _init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 10, 0, 10)

        self.control_panel = ControlPanel()
        self.status_label = QLabel("STATUS: Initializing...")
        self.status_label.setStyleSheet(
            "color: #7cfc00; font-family: monospace; font-size: 13px; font-weight: bold; "
            "padding: 8px; background-color: #000;"
        )
        main_layout.addWidget(self.control_panel)
        main_layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.control_panel.refresh_clicked.connect(self._refresh_devices)
        self.control_panel.start_clicked.connect(self._start_stream)
        self.control_panel.stop_clicked.connect(self._stop_stream)
        self.control_panel.device_combo.currentIndexChanged.connect(self._on_device_picked)
        self.control_panel.ai_config_clicked.connect(self._toggle_ai_config)
        self.video_canvas.closed.connect(self._stop_stream)

        self._router.models_ready.connect(self._on_models_ready)
        self._router.result_ready.connect(self._on_inference_result)
        self._router.error_occurred.connect(self._on_router_error)

    # ========== Router models ==========

    @Slot(list)
    def _on_models_ready(self, models):
        model_ids = [m[0] for m in models] if models and isinstance(models[0], (list, tuple)) else models
        self._yolo_available = "yolo" in model_ids
        self._vlm_models = [m for m in model_ids if m != "yolo"]
        logger.info("Router models: %s (yolo=%s)", model_ids, self._yolo_available)

        if hasattr(self, 'ai_config_panel'):
            self.ai_config_panel.set_vlm_models(self._vlm_models)
        else:
            self._vlm_models_for_later = self._vlm_models

    # ========== Device / Stream ==========

    @Slot()
    def _refresh_devices(self):
        devices = VideoWorker.get_available_devices()
        self.control_panel.update_device_list(devices)
        if devices:
            self._on_device_picked(0)

    @Slot(int)
    def _on_device_picked(self, idx):
        path = self.control_panel.device_combo.itemData(idx)
        if path:
            formats = VideoWorker.get_device_formats(path)
            self.control_panel.update_format_list(formats)

    @Slot(str, int, int)
    def _start_stream(self, device_path, width, height):
        if self.video_worker or self._is_stopping:
            return
        try:
            self._update_status("Checking hardware...")
            self.video_canvas.show()

            self.video_worker = VideoWorker(device_path, width, height)
            self.video_worker.frame_ready.connect(self._on_frame)
            self.video_worker.status_message.connect(self._handle_worker_status)
            self.video_worker.start()

            # Reset counters
            self._input_count = 0
            self._fps_t0 = time.time()
            self._reason_ms = 0.0
            self._overlay_ms = 0.0
            self._infer_count = 0
            self._pending_inference = False

            self.control_panel.set_streaming_state(True)
            self._update_status("Streaming")
            self._mon_timer.start(5000)

            if self._yolo_available:
                self._yolo_timer.start(YOLO_INTERVAL_MS)

            logger.info("Streaming %dx%d", width, height)

        except Exception as e:
            logger.error("Start stream failed: %s", e)

    @Slot()
    def _stop_stream(self):
        if self._is_stopping:
            return
        self._is_stopping = True
        self._yolo_timer.stop()
        self._mon_timer.stop()
        self._yolo_response = None
        if self.video_worker and self.video_worker.isRunning():
            self.video_worker.stop()
        self.video_worker = None
        self._latest_frame = None
        self._update_status("Stopped")
        QTimer.singleShot(500, self._finalize_stop)

    def _finalize_stop(self):
        self.video_canvas.hide()
        self.control_panel.set_streaming_state(False)
        self._is_stopping = False

    # ========== Monitor log ==========

    @Slot()
    def _on_monitor_tick(self):
        stats = read_stats()
        elapsed = max(time.time() - self._fps_t0, 0.001)
        fps = self._input_count / elapsed
        avg_r = self._reason_ms / max(self._infer_count, 1)
        avg_o = self._overlay_ms / max(self._infer_count, 1)
        logger.info("in:%.1f | reason:%.0fms overlay:%.0fms | GPU:%.0f%% CPU:%.0f%% RAM:%.1fG VRAM:%.1fG",
                    fps, avg_r, avg_o,
                    stats["gpu"], stats["cpu"], stats["ram"], stats["vram"])

    # ========== Frame callback ==========

    @Slot(object)
    def _on_frame(self, frame):
        if frame is None:
            return
        self._input_count += 1
        h, w = frame.shape[:2]
        qimage = QImage(frame.data, w, h, w * 3, QImage.Format_BGR888)
        self._latest_frame = qimage

        t0 = time.time()
        if self._yolo_response and not self._yolo_paused:
            annotated = yolo_draw_overlay(qimage.copy(), self._yolo_response)
            self.video_canvas.update_image(annotated)
        else:
            self.video_canvas.update_image(qimage)
        self._overlay_ms += (time.time() - t0) * 1000

    # ========== YOLO auto tick ==========

    @Slot()
    def _on_yolo_tick(self):
        if self._yolo_paused or not self._yolo_available or self._pending_inference:
            return
        if self._latest_frame is None or self._latest_frame.isNull():
            return

        from src.modules.yolo_overlay import prepare_payload
        payload = prepare_payload(self._latest_frame, "", 200)
        self._payload_kb = len(payload) / 1024
        self._infer_start = time.time()
        self._pending_inference = True
        logger.info("POST /v1/chat/completions → yolo (%.0f KB)", self._payload_kb)
        self._router.send_raw_payload("yolo", payload)

    # ========== VLM submit (from AI config panel) ==========

    @Slot(str, str)
    def _on_vlm_submit(self, model, prompt):
        if self._latest_frame is None:
            self.ai_config_panel.set_result("Error: No video stream")
            return
        if self._pending_inference:
            return

        self._yolo_paused = True
        self._yolo_response = None

        if model == "reason2":
            from src.modules.reason2_overlay import prepare_payload
        else:
            from src.modules.moondream2_overlay import prepare_payload
        payload = prepare_payload(self._latest_frame, prompt, 512)
        self._payload_kb = len(payload) / 1024
        self._infer_start = time.time()
        self._pending_inference = True
        logger.info("POST /v1/chat/completions → %s (%.0f KB)", model, self._payload_kb)
        self._router.send_raw_payload(model, payload)

    # ========== Inference results ==========

    @Slot(str, str)
    def _on_inference_result(self, model, response_text):
        self._pending_inference = False
        t_now = time.time()
        self._reason_ms += (t_now - self._infer_start) * 1000
        self._infer_count += 1

        if model == "yolo":
            self._yolo_response = response_text
            logger.info("← yolo OK (%.0fms)", (t_now - self._infer_start) * 1000)
            return

        self._yolo_paused = False
        logger.info("← %s OK (%.0fms)", model, (t_now - self._infer_start) * 1000)
        self.ai_config_panel.set_result(response_text)

    @Slot(str)
    def _on_router_error(self, msg):
        self._pending_inference = False
        self._yolo_paused = False
        logger.error("← %s ERROR: %s", self._yolo_available and "yolo" or "vlm", msg)
        self.ai_config_panel.set_result(f"Error: {msg}")

    # ========== AI config panel toggle ==========

    @Slot()
    def _toggle_ai_config(self):
        if not hasattr(self, 'ai_config_panel'):
            self.ai_config_panel = AIConfigPanel()
            self.ai_config_panel.setWindowFlags(Qt.Window)
            self.ai_config_panel.installEventFilter(self)
            self.ai_config_panel.submit_clicked.connect(self._on_vlm_submit)
            if hasattr(self, '_vlm_models_for_later'):
                self.ai_config_panel.set_vlm_models(self._vlm_models_for_later)
                del self._vlm_models_for_later

        if self.ai_config_panel.isVisible():
            self.ai_config_panel.hide()
        else:
            self.ai_config_panel.show()

    # ========== Status / Errors ==========

    def _handle_worker_status(self, msg):
        self._update_status(msg)
        if any(err in msg for err in ["Error", "Fatal", "1204", "1208", "NvBufSurface", "CaptureSession"]):
            self._handle_critical_error(msg)

    def _handle_critical_error(self, error_msg):
        self._stop_stream()
        hint = ""
        if any(code in error_msg for code in ["1204", "1208", "InvalidState", "NvBufSurface", "CaptureSession"]):
            hint = ("\n\n[Diagnosis] nvargus-daemon out of sync.\n"
                    "Run: sudo systemctl restart nvargus-daemon")
        QMessageBox.critical(self, "Hardware Error", f"Failure: {error_msg}{hint}")

    def _update_status(self, msg=None):
        state = msg if msg else ("Streaming" if self.video_worker else "Ready")
        self.status_label.setText(f"STATUS: {state}")

    def eventFilter(self, obj, event):
        if hasattr(self, 'ai_config_panel') and obj == self.ai_config_panel and event.type() == QEvent.Close:
            self.control_panel.ai_config_btn.setChecked(False)
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self._stop_stream()
        self._router.stop()
        self.video_canvas.close()
        if hasattr(self, 'ai_config_panel'):
            self.ai_config_panel.close()
        event.accept()
