"""
Kiosk main window: sidebar (1/6) + video display (5/6).
Orchestrates video_source, router_client, overlay modules, and system monitor.
"""
import base64
import logging
import os
import time

from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QPushButton, QSizePolicy, QApplication
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
        self._prev_cpu_snap = None
        self._params = {}
        self._latest_frame = None
        self._pending_inference = False

        # FPS & timing
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
        self._cli_model = None   # deferred CLI model (set after router responds)

        # UI
        self._sidebar = ControlSidebar()
        self._display = VideoDisplay()

        self._init_ui()
        self._connect_signals()

        # ---- Camera check: fatal if none ----
        if self._sidebar.camera_count() == 0:
            logger.error("No camera found — exiting")
            QTimer.singleShot(100, self.close)
            return

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
        self._router.models_ready.connect(self._on_models_ready)
        self._router.result_ready.connect(self._on_inference_result)
        self._router.error_occurred.connect(self._on_router_error)

    # ----- start / stop -----

    def _validate_play_args(self, camera_id: int, width: int, height: int,
                            model: str):
        """Validate --play CLI args.  Returns (camera_id, width, height, model)
        or (None, ...) on fatal error.  Resolution is matched to nearest
        supported; model falls back to 'disable' if not found."""
        # 1. Camera device must exist
        cam_path = f"/dev/video{camera_id}"
        if not os.path.exists(cam_path):
            logger.error("--play: camera %d not found (%s)", camera_id, cam_path)
            print(f"[ERROR] Camera {camera_id} not found ({cam_path})",
                  file=__import__("sys").stderr)
            return (None, width, height, model)

        # 2. Resolution — find closest supported
        formats = VideoSource.probe_formats(camera_id)
        supported = []
        for f in formats:
            fw, fh, _ = VideoSource.parse_resolution(f)
            supported.append((fw, fh))

        if not supported:
            logger.error("--play: no formats available for camera %d", camera_id)
            return (None, width, height, model)

        # exact match?
        matched = None
        for fw, fh in supported:
            if fw == width and fh == height:
                matched = (fw, fh)
                break

        if matched is None:
            target = width * height
            best = min(supported, key=lambda wh: abs(wh[0] * wh[1] - target))
            matched = best
            logger.warning("--play: %dx%d not supported, using closest %dx%d",
                           width, height, matched[0], matched[1])

        width, height = matched

        # 3. Model — fall back to 'disable'
        sidebar = self._sidebar
        model_idx = sidebar.model_combo.findText(model)
        if model_idx < 0:
            logger.warning("--play: model '%s' not available, using 'disable'", model)
            model = "disable"

        return (camera_id, width, height, model)

    def apply_cli_args(self, camera_id: int, width: int, height: int, fps: int,
                       model: str, interval: int, prompt: str, max_tokens: int,
                       auto_start: bool = False):
        """Validate CLI args, populate sidebar, optionally auto-start.
        Model selection is deferred until router responds (via _cli_model)."""
        if self._video_source is not None:
            return

        camera_id, width, height, model = self._validate_play_args(
            camera_id, width, height, model)
        if camera_id is None:
            return  # fatal — logged by _validate_play_args

        sidebar = self._sidebar

        # Camera
        for i in range(sidebar.camera_combo.count()):
            if sidebar.camera_combo.itemData(i) == str(camera_id):
                sidebar.camera_combo.setCurrentIndex(i)
                break

        # Resolution — match exact width/height (already validated)
        res_idx = -1
        for i in range(sidebar.res_combo.count()):
            rw, rh, _ = VideoSource.parse_resolution(sidebar.res_combo.itemText(i))
            if rw == width and rh == height:
                res_idx = i
                break
        if res_idx < 0 and sidebar.res_combo.count() > 0:
            res_idx = 0
        if res_idx >= 0:
            sidebar.res_combo.setCurrentIndex(res_idx)

        # Model — try now, defer if not yet in combo
        sidebar.model_combo.blockSignals(True)
        model_idx = sidebar.model_combo.findText(model)
        if model_idx >= 0:
            sidebar.model_combo.setCurrentIndex(model_idx)
        else:
            self._cli_model = model   # will apply in _on_models_ready
        sidebar.model_combo.blockSignals(False)

        # Interval / prompt / max_tokens
        sidebar.interval_edit.setText(str(interval))
        sidebar.prompt_edit.setPlainText(prompt)
        sidebar.tokens_edit.setText(str(max_tokens))

        if auto_start:
            logger.info("CLI: auto-starting %dx%d@%d model=%s interval=%d",
                         width, height, fps, model, interval)
            self._on_start(camera_id, width, height)

    @Slot(list)
    def _on_models_ready(self, models):
        self._sidebar.set_models(models)

        # Apply deferred CLI model
        if self._cli_model:
            idx = self._sidebar.model_combo.findText(self._cli_model)
            if idx >= 0:
                self._sidebar.model_combo.setCurrentIndex(idx)
                logger.info("CLI: model '%s' applied (router responded)", self._cli_model)
            self._cli_model = None

        if not models:
            logger.warning("No models available — select \"disable\" for view-only")

    @Slot(int, int, int)
    def _on_start(self, camera_id, width, height):
        params = self._sidebar.get_params()
        params["width"] = width
        params["height"] = height
        res_text = self._sidebar.res_combo.currentText()
        _, _, fps = VideoSource.parse_resolution(res_text)
        params["fps"] = fps
        self._params = params

        # Output resolution: match video display area, aligned to 16
        screen = QApplication.primaryScreen()
        if screen:
            sw = screen.size().width()
            out_w = (int(sw * 3 / 5) // 16) * 16
            out_h = (int(out_w * 9 / 16) // 16) * 16
        else:
            out_w = out_h = 0

        # Reset all counters
        self._input_count = 0
        self._output_count = 0
        self._fps_t0 = time.time()
        self._prepare_ms = 0.0
        self._reason_ms = 0.0
        self._overlay_ms = 0.0
        self._infer_count = 0

        self._display.set_res_fps(f"{width}x{height}@{fps}")
        self._sidebar.set_streaming_state(True)

        self._video_source = VideoSource(camera_id, width, height, fps,
                                         output_width=out_w, output_height=out_h)
        self._video_source.frame_ready.connect(self._on_frame)
        self._video_source.status_message.connect(
            lambda msg: logger.info("Video: %s", msg))
        self._video_source.start()

        self._mon_timer.start(5000)

        interval_ms = max(1, params["interval"])
        self._interval_timer.start(interval_ms)

        logger.info("Streaming %dx%d@%d — interval %dms, model %s",
                     width, height, fps, params["interval"], params["model"])

    @Slot()
    def _on_stop(self):
        self._interval_timer.stop()
        self._pending_inference = False
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
        self._mon_timer.stop()

    @Slot(str)
    def _on_video_status(self, msg):
        logger.info(msg)
        if "Failed to create CaptureSession" in msg or "error 12" in msg or "unable to allocate" in msg.lower():
            logger.error("NVMM allocation failed — stopping stream")
            QTimer.singleShot(100, self._on_stop)

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
        if self._video_source is None:
            return  # stopped, ignore late frame
        qimage = QImage(data, w, h, w * 4, QImage.Format_RGB32)
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
        if self._video_source is None:
            return
        if self._pending_inference:
            return

        params = self._sidebar.get_params()
        model = params["model"]
        if not model or model == "disable":
            return

        if model != "yolo":
            self._yolo_response = None

        # Request one fresh JPEG frame (unpause → appsink captures one → auto-re-pause)
        self._video_source.paused = False
        jpeg_data, iw, ih = self._video_source.latest_jpeg
        if not jpeg_data:
            return

        import base64, json
        image_b64 = base64.b64encode(jpeg_data).decode()
        payload = json.dumps({
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": params["prompt"]},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    }},
                ]
            }],
            "max_tokens": params["max_tokens"],
        })
        t0 = time.time()
        self._prepare_ms += (time.time() - t0) * 1000
        self._payload_kb = len(payload) / 1024

        logger.info("POST /v1/chat/completions → %s (%.0f KB JPEG)", model, self._payload_kb)
        self._infer_start = time.time()
        self._pending_inference = True
        self._router.send_raw_payload(payload)

    # ----- inference result -----

    @Slot(str, str)
    def _on_inference_result(self, model, response_text):
        if self._video_source is None:
            return  # stopped, ignore late response
        self._pending_inference = False
        t_now = time.time()
        self._reason_ms += (t_now - self._infer_start) * 1000
        self._infer_count += 1
        self._last_overlay = response_text

        logger.info("← %s OK (%.0fms)", model, (t_now - self._infer_start) * 1000)

        t0 = time.time()
        if model == "yolo":
            fn = DRAW.get(model)
            if fn:
                frame = self._latest_frame
                if frame and not frame.isNull():
                    annotated = fn(frame.copy(), response_text)
                    self._display.set_frame(annotated)
            self._display.set_overlay_text("")
            self._yolo_response = response_text
        else:
            self._display.set_overlay_text(response_text)
        self._overlay_ms += (time.time() - t0) * 1000

        params = self._sidebar.get_params()
        interval_ms = max(1, params["interval"])
        self._interval_timer.start(interval_ms)

    # ----- errors -----

    @Slot(str)
    def _on_router_error(self, msg):
        self._pending_inference = False
        logger.error("← %s ERROR: %s", self._params.get("model", "?"), msg)

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
