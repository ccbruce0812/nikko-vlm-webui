import re
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QGroupBox, QSizePolicy)
from PySide6.QtCore import Signal


class ControlPanel(QFrame):
    start_clicked = Signal(str, int, int)  # device_path, width, height
    stop_clicked = Signal()
    refresh_clicked = Signal()
    ai_config_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(500)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- 1. Video Device ---
        device_group = QGroupBox("1. Video Device")
        dev_layout = QVBoxLayout(device_group)

        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.refresh_btn = QPushButton("Refresh")
        dev_row.addWidget(self.device_combo)
        dev_row.addWidget(self.refresh_btn)
        dev_layout.addLayout(dev_row)

        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Resolution:"))
        self.res_combo = QComboBox()
        self.res_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        res_row.addWidget(self.res_combo)
        dev_layout.addLayout(res_row)
        main_layout.addWidget(device_group)

        # --- 2. Transport Control ---
        transport_group = QGroupBox("2. Transport Control")
        trans_layout = QHBoxLayout(transport_group)
        self.start_btn = QPushButton("\u25cf START STREAM")
        self.stop_btn = QPushButton("\u25a0 STOP STREAM")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #2d5a27; color: white; height: 45px; font-weight: bold; border-radius: 4px; }
            QPushButton:disabled { background-color: #1a2a1a; color: #444; }
        """)
        self.stop_btn.setStyleSheet("""
            QPushButton { background-color: #a33232; color: white; height: 45px; font-weight: bold; border-radius: 4px; }
            QPushButton:disabled { background-color: #2a1a1a; color: #444; }
        """)
        trans_layout.addWidget(self.start_btn)
        trans_layout.addWidget(self.stop_btn)
        main_layout.addWidget(transport_group)

        # --- 3. AI Config ---
        ai_group = QGroupBox("3. AI Inference")
        ai_layout = QHBoxLayout(ai_group)
        self.ai_config_btn = QPushButton("Open AI Panel")
        self.ai_config_btn.setCheckable(True)
        self.ai_config_btn.setStyleSheet("""
            QPushButton { height: 40px; font-weight: bold; }
        """)
        ai_layout.addWidget(self.ai_config_btn)
        main_layout.addWidget(ai_group)

        main_layout.addStretch()

        # Signals
        self.refresh_btn.clicked.connect(lambda: self.refresh_clicked.emit())
        self.start_btn.clicked.connect(self._on_start_emit)
        self.stop_btn.clicked.connect(lambda: self.stop_clicked.emit())
        self.ai_config_btn.clicked.connect(lambda: self.ai_config_clicked.emit())

    def update_device_list(self, devices):
        self.device_combo.clear()
        for dev in devices:
            self.device_combo.addItem(dev["name"], dev["path"])
        self.start_btn.setEnabled(len(devices) > 0)

    def update_format_list(self, formats):
        self.res_combo.clear()
        for f in formats:
            self.res_combo.addItem(f)

    def _on_start_emit(self):
        path = self.device_combo.currentData()
        res_text = self.res_combo.currentText()
        if path and res_text:
            match = re.search(r"(\d+)x(\d+)", res_text)
            w, h = (int(match.group(1)), int(match.group(2))) if match else (1280, 720)
            self.start_clicked.emit(path, w, h)

    def set_streaming_state(self, is_streaming):
        self.start_btn.setEnabled(not is_streaming)
        self.stop_btn.setEnabled(is_streaming)
        self.device_combo.setEnabled(not is_streaming)
        self.res_combo.setEnabled(not is_streaming)
        self.refresh_btn.setEnabled(not is_streaming)
