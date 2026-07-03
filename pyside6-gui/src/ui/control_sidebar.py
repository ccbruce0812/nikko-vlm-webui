"""
Left sidebar control panel (1/6 width).
Contains Video Source and AI Model configuration sections.
"""
import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QGroupBox, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from src.modules.video_source import VideoSource


class ControlSidebar(QWidget):
    """Kiosk sidebar: camera/model controls + START/STOP/QUIT buttons."""

    start_clicked = Signal(int, int, int)       # camera_id, width, height
    stop_clicked = Signal()
    quit_clicked = Signal()
    model_changed = Signal(str)                  # model name
    interval_changed = Signal(int)
    prompt_changed = Signal(str)
    max_tokens_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._streaming = False
        self._init_ui()
        self._connect_signals()
        self._refresh_devices()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ---- Video Source ----
        src_group = QGroupBox("Video Source")
        src_layout = QVBoxLayout(src_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Camera ID:"))
        self.camera_combo = QComboBox()
        self.camera_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row1.addWidget(self.camera_combo)
        src_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Res/FPS:"))
        self.res_combo = QComboBox()
        self.res_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row2.addWidget(self.res_combo)
        src_layout.addLayout(row2)

        layout.addWidget(src_group)

        # ---- AI Model ----
        ai_group = QGroupBox("AI Model")
        ai_layout = QVBoxLayout(ai_group)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row3.addWidget(self.model_combo)
        ai_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Interval:"))
        self.interval_edit = QLineEdit("1")
        self.interval_edit.setFixedWidth(50)
        self.interval_edit.setAlignment(Qt.AlignRight)
        row4.addWidget(self.interval_edit)
        row4.addWidget(QLabel("sec"))
        row4.addStretch()
        ai_layout.addLayout(row4)

        ai_layout.addWidget(QLabel("Prompt:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Describe this image in one sentence.")
        self.prompt_edit.setMaximumHeight(80)
        self.prompt_edit.setTabChangesFocus(True)  # Ctrl+Tab exits
        ai_layout.addWidget(self.prompt_edit)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Max Tokens:"))
        self.tokens_edit = QLineEdit("512")
        self.tokens_edit.setFixedWidth(60)
        self.tokens_edit.setAlignment(Qt.AlignRight)
        row5.addWidget(self.tokens_edit)
        row5.addStretch()
        ai_layout.addLayout(row5)

        layout.addWidget(ai_group)
        layout.addStretch()

        # ---- Action buttons ----
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("&START")
        self.start_btn.setShortcut("Alt+S")
        self.start_btn.setMinimumHeight(44)
        self.quit_btn = QPushButton("&QUIT")
        self.quit_btn.setShortcut("Alt+Q")
        self.quit_btn.setMinimumHeight(44)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.quit_btn)
        layout.addLayout(btn_row)

    def _connect_signals(self):
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        self.start_btn.clicked.connect(self._on_start_stop)
        self.quit_btn.clicked.connect(self.quit_clicked)
        self.model_combo.currentTextChanged.connect(
            lambda t: self.model_changed.emit(t))
        self.interval_edit.textChanged.connect(self._on_interval_changed)
        self.prompt_edit.textChanged.connect(
            lambda: self.prompt_changed.emit(self.prompt_edit.toPlainText()))
        self.tokens_edit.textChanged.connect(self._on_tokens_changed)

    # ----- device / resolution -----

    def _refresh_devices(self):
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        for name, dev_id in VideoSource.scan_devices():
            self.camera_combo.addItem(name, dev_id)
        self.camera_combo.blockSignals(False)
        if self.camera_combo.count() > 0:
            self._on_camera_changed(0)

    def _on_camera_changed(self, index):
        dev_id = self.camera_combo.itemData(index)
        if dev_id is None:
            return
        formats = VideoSource.probe_formats(dev_id)
        self.res_combo.blockSignals(True)
        self.res_combo.clear()
        for f in formats:
            self.res_combo.addItem(f)
        self.res_combo.blockSignals(False)

    # ----- start / stop -----

    def _on_start_stop(self):
        if self._streaming:
            self.stop_clicked.emit()
        else:
            dev_id = self.camera_combo.currentData()
            if dev_id is None:
                return
            res_text = self.res_combo.currentText()
            w, h, _ = VideoSource.parse_resolution(res_text)
            self.start_clicked.emit(int(dev_id), w, h)

    def set_streaming_state(self, streaming):
        self._streaming = streaming
        if streaming:
            self.start_btn.setText("&STOP")
        else:
            self.start_btn.setText("&START")
        self.camera_combo.setEnabled(not streaming)
        self.res_combo.setEnabled(not streaming)

    # ----- validation -----

    def _on_interval_changed(self, text):
        try:
            val = int(text)
            if val < 1:
                val = 1
                self.interval_edit.blockSignals(True)
                self.interval_edit.setText("1")
                self.interval_edit.blockSignals(False)
            self.interval_changed.emit(val)
        except ValueError:
            pass

    def _on_tokens_changed(self, text):
        try:
            val = int(text)
            val = max(1, min(val, 2048))
            self.max_tokens_changed.emit(val)
        except ValueError:
            pass

    # ----- public helpers -----

    def set_models(self, models):
        """Populate model dropdown: models is list of (model_id, owned_by)."""
        current = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model_id, _ in models:
            self.model_combo.addItem(model_id)
        if current:
            idx = self.model_combo.findText(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)

    def get_params(self):
        """Return current settings as dict."""
        try:
            interval = int(self.interval_edit.text())
        except ValueError:
            interval = 1
        try:
            max_tokens = int(self.tokens_edit.text())
        except ValueError:
            max_tokens = 512
        return {
            "model": self.model_combo.currentText(),
            "interval": max(1, interval),
            "prompt": self.prompt_edit.toPlainText().strip() or "Describe this image in one sentence.",
            "max_tokens": max(1, min(max_tokens, 2048)),
        }
