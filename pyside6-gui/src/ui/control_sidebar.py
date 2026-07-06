"""
Left sidebar control panel (1/6 width).
Grid layout — uniform spacing, no QGroupBox padding issues.
"""
import os
import re
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QSizePolicy,
    QStyledItemDelegate, QStyle, QFrame,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QColor

from src.modules.video_source import VideoSource


class _DarkComboDelegate(QStyledItemDelegate):
    """Custom delegate: dark background, hover highlight for combo items."""

    def paint(self, painter, option, index):
        # Hover highlight
        if option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#3a3a3a"))
        else:
            painter.fillRect(option.rect, QColor("#2a2a2a"))
        # Selected item
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#444"))
        # Text
        painter.setPen(QColor("#ddd"))
        painter.drawText(option.rect.adjusted(6, 0, -6, 0),
                         Qt.AlignLeft | Qt.AlignVCenter,
                         index.data())


class ControlSidebar(QWidget):
    """Kiosk sidebar: camera/model controls in uniform grid."""

    start_clicked = Signal(int, int, int)
    stop_clicked = Signal()
    quit_clicked = Signal()
    model_changed = Signal(str)
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
        grid = QGridLayout(self)

        # Spacing = 5% of sidebar width (sidebar = 2/5 of screen)
        from PySide6.QtWidgets import QApplication
        sw = QApplication.primaryScreen().size().width() if QApplication.instance() else 1920
        sp = max(6, int(sw * 2 / 5 * 0.02))
        grid.setSpacing(sp)
        grid.setContentsMargins(sp, sp, sp, sp)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        bold = QFont()
        bold.setBold(True)
        r = 0

        # ---- Section: Video Source ----
        hdr = QLabel("Video Source"); hdr.setFont(bold)
        grid.addWidget(hdr, r, 0, 1, 2); r += 1

        grid.addWidget(QLabel("Camera ID:"), r, 0)
        self.camera_combo = QComboBox()
        self.camera_combo.setItemDelegate(_DarkComboDelegate(self.camera_combo))
        self.camera_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid.addWidget(self.camera_combo, r, 1); r += 1

        grid.addWidget(QLabel("Res/FPS:"), r, 0)
        self.res_combo = QComboBox()
        self.res_combo.setItemDelegate(_DarkComboDelegate(self.res_combo))
        self.res_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid.addWidget(self.res_combo, r, 1); r += 1

        grid.setRowMinimumHeight(r, 12); r += 1  # spacer row

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("color: #444;")
        grid.addWidget(sep, r, 0, 1, 2)
        r += 1

        # ---- Section: AI Model ----
        hdr2 = QLabel("AI Model"); hdr2.setFont(bold)
        grid.addWidget(hdr2, r, 0, 1, 2); r += 1

        grid.addWidget(QLabel("Model:"), r, 0)
        self.model_combo = QComboBox()
        self.model_combo.setItemDelegate(_DarkComboDelegate(self.model_combo))
        self.model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid.addWidget(self.model_combo, r, 1); r += 1

        grid.addWidget(QLabel("Interval:"), r, 0)
        ir = QHBoxLayout(); ir.setContentsMargins(0, 0, 0, 0)
        self.interval_edit = QLineEdit("1000")
        self.interval_edit.setAlignment(Qt.AlignRight)
        ir.addWidget(self.interval_edit)
        ir.addWidget(QLabel("ms"))
        grid.addLayout(ir, r, 1); r += 1

        grid.addWidget(QLabel("Max Tokens:"), r, 0)
        self.tokens_edit = QLineEdit("512")
        self.tokens_edit.setAlignment(Qt.AlignRight)
        grid.addWidget(self.tokens_edit, r, 1); r += 1

        grid.addWidget(QLabel("Prompt:"), r, 0); r += 1
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText("Describe this image in one sentence without coordinates or numbers.")
        fm = self.prompt_edit.fontMetrics()
        self.prompt_edit.setFixedHeight((fm.height() + 4) * 10)
        self.prompt_edit.setTabChangesFocus(True)
        grid.addWidget(self.prompt_edit, r, 0, 1, 2); r += 1

        grid.setRowMinimumHeight(r, 6); r += 1  # spacer

        # Separator line
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        sep2.setStyleSheet("color: #444;")
        grid.addWidget(sep2, r, 0, 1, 2)
        r += 1

        # ---- Buttons ----
        btn_layout = QHBoxLayout(); btn_layout.setContentsMargins(0, 0, 0, 0)
        self.start_btn = QPushButton("START")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._on_start_stop)
        self.quit_btn = QPushButton("QUIT")
        self.quit_btn.setMinimumHeight(40)
        self.quit_btn.clicked.connect(self.quit_clicked)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.quit_btn)
        grid.addLayout(btn_layout, r, 0, 1, 2); r += 1

        # bottom filler
        grid.setRowStretch(r, 1)

    def _connect_signals(self):
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
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

    def camera_count(self):
        return self.camera_combo.count()

    def _on_camera_changed(self, index):
        dev_id = self.camera_combo.itemData(index)
        if dev_id is None:
            return
        formats = VideoSource.probe_formats(dev_id)
        self.res_combo.blockSignals(True)
        self.res_combo.clear()
        for f in formats:
            self.res_combo.addItem(f)
        # Prefer 1920x1080
        idx = self.res_combo.findText("1920x1080", Qt.MatchStartsWith)
        if idx < 0:
            idx = self.res_combo.findText("1920x1080@30")
        if idx >= 0:
            self.res_combo.setCurrentIndex(idx)
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
            self.start_btn.setText("STOP")
        else:
            self.start_btn.setText("START")
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
        current = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("No Model")
        for model_id, _ in models:
            self.model_combo.addItem(model_id)
        if current and current != "No Model":
            idx = self.model_combo.findText(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)

    def get_params(self):
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
