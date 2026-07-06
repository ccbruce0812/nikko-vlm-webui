import cv2
import platform
import logging
import os
import time
import subprocess
import re
from PySide6.QtCore import QThread, Signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoWorker(QThread):
    frame_ready = Signal(object)
    status_message = Signal(str)

    def __init__(self, sensor_id=0, width=1280, height=720, fps=30):
        super().__init__()
        try:
            self.sensor_id = int(sensor_id)
        except (ValueError, TypeError):
            self.sensor_id = 0
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self.cap = None

    @staticmethod
    def get_available_devices():
        device_configs = []
        if platform.system() == "Linux":
            for i in range(10):
                if os.path.exists(f"/dev/video{i}"):
                    device_configs.append({"name": f"Camera {i}", "path": str(i)})
        return device_configs if device_configs else [{"name": "Camera 0", "path": "0"}]

    @staticmethod
    def probe_sensor_modes(device_path):
        modes = {}
        try:
            cmd = f"v4l2-ctl -d /dev/video{device_path} --list-formats-ext"
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            current_res = None
            for line in output.split('\n'):
                size_match = re.search(r"Size: Discrete (\d+x\d+)", line)
                if size_match:
                    current_res = size_match.group(1)
                    if current_res not in modes:
                        modes[current_res] = []
                elif current_res:
                    fps_match = re.search(r"\(([\d\.]+)\s*fps\)", line)
                    if fps_match:
                        modes[current_res].append(float(fps_match.group(1)))
        except Exception as e:
            logger.warning(f"Failed to probe resolutions: {e}")

        best_modes = {res: int(max(fps_list)) for res, fps_list in modes.items() if fps_list}
        if not best_modes:
            best_modes = {
                "3280x2464": 21, "3280x1848": 28, "1920x1080": 30,
                "1640x1232": 30, "1280x720": 60
            }
        return best_modes

    @staticmethod
    def get_device_formats(device_path):
        modes = VideoWorker.probe_sensor_modes(device_path)
        return [f"{res} ({fps} fps)" for res, fps in modes.items()]

    def _get_csi_pipeline(self):
        modes = self.probe_sensor_modes(self.sensor_id)
        res_key = f"{self.width}x{self.height}"
        optimal_fps = modes.get(res_key, self.fps)
        logger.info(f"GStreamer: {res_key} @ {optimal_fps} FPS")
        return (
            f"nvarguscamerasrc sensor-id={self.sensor_id} ! "
            f"video/x-raw(memory:NVMM), width={self.width}, height={self.height}, "
            f"format=NV12, framerate={optimal_fps}/1 ! "
            "nvvidconv flip-method=0 ! "
            "video/x-raw, format=BGRx ! "
            "videoconvert ! "
            "video/x-raw, format=BGR ! appsink drop=true max-buffers=1 sync=false"
        )

    def _check_opencv_gstreamer(self):
        try:
            return "GStreamer:                   YES" in cv2.getBuildInformation()
        except Exception:
            return False

    def run(self):
        is_jetson = platform.system() == "Linux"
        use_hw = is_jetson and self._check_opencv_gstreamer()
        max_retries = 3

        for attempt in range(max_retries):
            if use_hw:
                pipeline = self._get_csi_pipeline()
                if attempt > 0:
                    logger.warning(f"Retrying HW Pipeline ({attempt + 1}/{max_retries})")
                self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            else:
                self.cap = cv2.VideoCapture(self.sensor_id)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            if self.cap and self.cap.isOpened():
                time.sleep(0.5)
                break

            if self.cap:
                self.cap.release()
                self.cap = None
            if attempt < max_retries - 1:
                time.sleep(1.5)

        if not self.cap or not self.cap.isOpened():
            self.status_message.emit("Error: Failed to open camera")
            return

        self.running = True
        self.status_message.emit("Streaming started")
        try:
            while self.running:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.frame_ready.emit(frame)
                else:
                    self.msleep(5)
                    if not self.cap.isOpened():
                        break
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        self.status_message.emit("Streaming stopped")

    def stop(self):
        self.running = False
        self.wait()
