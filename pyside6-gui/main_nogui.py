#!/usr/bin/env python3
"""
Headless validation mode: GStreamer pipeline + Router API + overlay modules.
No PySide6 window — FPS stats and inference results printed to console.  Ctrl-C to stop.

Overlay modules (yolo / reason2 / moondream2) handle both payload preparation and
result drawing.  System monitor stats are drawn via /proc and /sys (no jetson-stats needed).

Usage:
  python main_nogui.py [--camera-id 0] [--resolution 1920x1080@30]
                       [--model reason2] [--interval 1]
                       [--prompt "Describe this image in one sentence."]
                       [--max-tokens 512]
"""
import argparse
import base64
import json
import logging
import os
import signal
import sys
import time
import threading
import urllib.request

from PySide6.QtCore import QTimer, Slot, QBuffer, QIODevice
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QGuiApplication
from PySide6.QtCore import Qt

from src.modules.video_source import VideoSource
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nogui")

ROUTER_URL = "http://localhost:8080"


def parse_args():
    p = argparse.ArgumentParser(description="Headless VLM validation")
    p.add_argument("--camera-id", type=int, default=0)
    p.add_argument("--resolution", default="1920x1080",
                   help="e.g. 1920x1080@30, 1280x720@60 (FPS optional after @)")
    p.add_argument("--model", default="reason2")
    p.add_argument("--interval", type=int, default=1)
    p.add_argument("--prompt", default="Describe this image in one sentence.")
    p.add_argument("--max-tokens", type=int, default=512)
    return p.parse_args()

# re-export for convenience (no jetson-stats dependency)

# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
#  Monitor overlay drawing
# ---------------------------------------------------------------------------

def _draw_monitor_overlay(qimage: QImage, stats: dict, res_fps: str) -> QImage:
    result = qimage.copy()
    painter = QPainter(result)
    font = QFont("monospace", max(10, result.width() // 100))
    font.setBold(True)
    painter.setFont(font)

    gpu = stats.get("gpu", 0)
    cpu = stats.get("cpu", 0)
    ram = stats.get("ram", 0)
    vram = stats.get("vram", 0)
    text = (f"{res_fps}  GPU:{gpu:.0f}% VRAM:{vram:.1f}G\n"
            f"CPU:{cpu:.0f}% RAM:{ram:.1f}G")

    fm = painter.fontMetrics()
    lines = text.split("\n")
    max_w = max(fm.horizontalAdvance(line) for line in lines)
    line_h = fm.height() + 2
    total_h = line_h * len(lines) + 6

    x = result.width() - max_w - 16
    y = 8
    painter.fillRect(x - 4, y, max_w + 8, total_h, QColor(0, 0, 0, 140))
    painter.setPen(Qt.white)
    painter.drawText(x, y + line_h - 4, text)
    painter.end()
    return result


# ---------------------------------------------------------------------------
#  Headless runner
# ---------------------------------------------------------------------------

class HeadlessRunner:
    def __init__(self, args):
        self.args = args
        w, h, fps = VideoSource.parse_resolution(args.resolution)
        self.width = w
        self.height = h

        self._target_fps = fps if fps > 0 else None
        self._actual_fps = fps if fps > 0 else 30

        self._source = None
        self._latest_data = None
        self._latest_w = 0
        self._latest_h = 0
        self._pending = False
        self._interval_ms = max(1, args.interval) * 1000

        # FPS counters
        self._input_count = 0
        self._output_count = 0
        self._fps_t0 = 0.0
        self._fps_res = f"{w}x{h}"

        # System monitor (no jetson-stats; uses /proc + /sys)
        self._monitor_stats = {"gpu": 0, "cpu": 0, "ram": 0, "vram": 0}
        self._prev_cpu_snap = None

    # -----------------------------------------------------------------
    #  validation
    # -----------------------------------------------------------------

    def _validate(self):
        errors = []
        cam_path = f"/dev/video{self.args.camera_id}"
        if not os.path.exists(cam_path):
            errors.append(f"Camera {self.args.camera_id} not found ({cam_path})")

        if not errors:
            modes = VideoSource.probe_formats(self.args.camera_id)
            found = False
            avail = []
            for mode in modes:
                _w, _h, _f = VideoSource.parse_resolution(mode)
                avail.append(f"{_w}x{_h}@{_f}")
                if _w == self.width and _h == self.height:
                    found = True
                    if self._target_fps and self._target_fps > _f:
                        logger.warning("Requested %d fps exceeds max %d — capping",
                                       self._target_fps, _f)
            if not found:
                errors.append(f"Resolution {self.width}x{self.height} not supported. "
                              f"Available: {', '.join(avail[:6])}")

        if self.args.max_tokens < 1 or self.args.max_tokens > 2048:
            errors.append(f"max-tokens={self.args.max_tokens} out of range (1–2048)")

        try:
            req = urllib.request.Request("http://localhost:8080/v1/models")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                running = [m["id"] for m in data.get("data", [])]
            if not running:
                errors.append("Router reports no models running.")
            elif self.args.model not in running:
                errors.append(f"Model '{self.args.model}' not available. "
                              f"Running: {', '.join(running)}")
        except Exception as e:
            errors.append(f"Cannot reach router: {e}")

        if errors:
            print("Parameter validation failed:", file=sys.stderr)
            for err in errors:
                print(f"  • {err}", file=sys.stderr)
            sys.exit(1)

    # -----------------------------------------------------------------
    #  entry point
    # -----------------------------------------------------------------

    def run(self):
        app = QGuiApplication(sys.argv) if QGuiApplication.instance() is None \
            else QGuiApplication.instance()

        self._validate()

        # ---- framerate ----
        modes = VideoSource.probe_formats(self.args.camera_id)
        best = 0
        for mode in modes:
            _w, _h, f = VideoSource.parse_resolution(mode)
            if _w == self.width and _h == self.height:
                best = max(best, f)
        if best == 0:
            best = self._actual_fps or 30

        if self._target_fps is not None:
            if self._target_fps > best:
                logger.warning("Requested %d fps exceeds max %d — capping",
                               self._target_fps, best)
                self._actual_fps = best
            else:
                self._actual_fps = self._target_fps
        else:
            self._actual_fps = best

        self._fps_res = f"{self.width}x{self.height}@{self._actual_fps}"

        # ---- GStreamer ----
        self._source = VideoSource(self.args.camera_id, self.width, self.height,
                                   framerate=self._actual_fps,
                                   enable_raw_queue=True)
        self._source.frame_ready.connect(self._on_frame)
        self._source.status_message.connect(lambda msg: logger.info(msg))
        self._source.start()

        poll_timer = QTimer()
        poll_timer.timeout.connect(self._poll_queue)
        poll_timer.start(0)

        # ---- inference timer ----
        timer = QTimer()
        timer.timeout.connect(self._on_tick)
        timer.start(self._interval_ms)

        # ---- empty-run overlay timer (5 s) ----
        dry_timer = QTimer()
        dry_timer.timeout.connect(self._on_dry_overlay)
        dry_timer.start(5000)

        # ---- FPS report timer (5 s) ----
        self._fps_t0 = time.time()
        fps_timer = QTimer()
        fps_timer.timeout.connect(self._report_fps)
        fps_timer.start(5000)

        # ---- system monitor timer (5 s, /proc + /sys) ----
        mon_timer = QTimer()
        mon_timer.timeout.connect(self._on_monitor_tick)
        mon_timer.start(5000)

        logger.info("Streaming %s — interval %ds, model %s",
                    self._fps_res, self.args.interval, self.args.model)

        signal.signal(signal.SIGINT, lambda *_: app.quit())

        try:
            app.exec()
        finally:
            for t in (timer, fps_timer, poll_timer, dry_timer, mon_timer):
                t.stop()
            if self._source:
                self._source.stop()
            logger.info("Shutting down.")

    # -----------------------------------------------------------------
    #  frame reception
    # -----------------------------------------------------------------

    @Slot(bytes, int, int)
    def _on_frame(self, data, w, h):
        self._latest_data = data
        self._latest_w = w
        self._latest_h = h
        self._input_count += 1

    @Slot()
    def _poll_queue(self):
        if self._source is None:
            return
        q = self._source._raw_queue
        if q is None:
            return
        try:
            while True:
                data, w, h = q.get_nowait()
                self._latest_data = data
                self._latest_w = w
                self._latest_h = h
                self._input_count += 1
        except Exception:
            pass

    def _get_qimage(self):
        if self._latest_data is None:
            return None
        return QImage(self._latest_data, self._latest_w, self._latest_h,
                      self._latest_w * 4, QImage.Format_RGBA8888)

    # -----------------------------------------------------------------
    #  system monitor (no jetson-stats)
    # -----------------------------------------------------------------

    @Slot()
    def _on_monitor_tick(self):
        snap = read_stats()
        cpu = compute_cpu_pct(self._prev_cpu_snap, snap)
        self._prev_cpu_snap = snap
        self._monitor_stats = {
            "gpu": snap.get("gpu", 0),
            "cpu": cpu,
            "ram": snap.get("ram", 0),
            "vram": snap.get("vram", 0),
        }
        frame = self._get_qimage()
        if frame is not None:
            _draw_monitor_overlay(frame, self._monitor_stats, self._fps_res)
            self._output_count += 1

    # -----------------------------------------------------------------
    #  inference tick — delegates payload to overlay module
    # -----------------------------------------------------------------

    @Slot()
    def _on_tick(self):
        frame = self._get_qimage()
        if frame is None:
            return
        if self._pending:
            return
        self._pending = True

        model = self.args.model
        fn = PREPARE.get(model)
        if fn is None:
            self._pending = False
            return
        payload = fn(frame, self.args.prompt, self.args.max_tokens)

        size_kb = len(payload) * 3 // 4 // 1024
        logger.info("POST /v1/chat/completions → %s (%d KB)", model, size_kb)

        t = threading.Thread(target=self._do_inference, args=(payload,), daemon=True)
        t.start()

    def _do_inference(self, payload):
        try:
            req = urllib.request.Request(
                f"{ROUTER_URL}/v1/chat/completions",
                data=payload.encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"]
                print(f"{self.args.model}: {content}", flush=True)
            self._apply_overlay(content)
        except Exception as e:
            logger.error("Inference error: %s", e)
        finally:
            self._pending = False

    def _apply_overlay(self, response_text: str):
        frame = self._get_qimage()
        if frame is None:
            return
        fn = DRAW.get(self.args.model)
        if fn:
            fn(frame, response_text)
            self._output_count += 1

    # -----------------------------------------------------------------
    #  empty-run overlay (keeps output pipeline exercised)
    # -----------------------------------------------------------------

    @Slot()
    def _on_dry_overlay(self):
        frame = self._get_qimage()
        if frame is None:
            return
        fn = DRAW.get(self.args.model)
        if fn:
            fn(frame, "")
            self._output_count += 1

    # -----------------------------------------------------------------
    #  FPS report
    # -----------------------------------------------------------------

    @Slot()
    def _report_fps(self):
        now = time.time()
        elapsed = now - self._fps_t0
        if elapsed <= 0:
            return
        in_fps = self._input_count / elapsed
        out_fps = self._output_count / elapsed
        logger.info("FPS — input: %5.1f | output: %5.1f | target: %s | %s",
                    in_fps, out_fps, self._actual_fps, self._fps_res)


def main():
    args = parse_args()
    runner = HeadlessRunner(args)
    runner.run()


if __name__ == "__main__":
    main()
