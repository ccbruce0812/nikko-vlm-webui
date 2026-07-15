"""
Left sidebar control panel.
Grid layout — uniform spacing, no QGroupBox padding issues.
"""
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QSizePolicy,
    QStyledItemDelegate, QStyle, QFrame,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QColor


def _hline():
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setFrameShadow(QFrame.Sunken)
    sep.setStyleSheet("color: #444;")
    return sep


class _DarkComboDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#3a3a3a"))
        else:
            painter.fillRect(option.rect, QColor("#2a2a2a"))
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#444"))
        painter.setPen(QColor("#ddd"))
        painter.drawText(option.rect.adjusted(6, 0, -6, 0),
                         Qt.AlignLeft | Qt.AlignVCenter, index.data())


class ControlSidebar(QWidget):
    """Kiosk sidebar: camera / perception / reasoning controls."""

    start_clicked = Signal(int, int, int)
    stop_clicked = Signal()
    quit_clicked = Signal()
    perception_changed = Signal(str)
    reasoning_changed = Signal(str)
    interval_changed = Signal(int)
    prompt_changed = Signal(str)
    max_tokens_changed = Signal(int)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._streaming = False
        self._config = config
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        grid = QGridLayout(self)
        from PySide6.QtWidgets import QApplication
        sw = QApplication.primaryScreen().size().width() if QApplication.instance() else 1920
        sp = max(6, int(sw * 2 / 5 * 0.02))
        grid.setSpacing(sp)
        grid.setContentsMargins(sp, sp, sp, sp)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        bold = QFont(); bold.setBold(True)
        r = 0
        cfg = self._config

        # ---- Camera ----
        hdr = QLabel("Camera"); hdr.setFont(bold)
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

        # Fill camera combos from config
        from src.modules.video_source import VideoSource
        for name, dev_id in VideoSource.scan_devices():
            self.camera_combo.addItem(name, dev_id)
        formats = VideoSource.probe_formats(str(cfg["camera_id"]))
        for f in formats:
            self.res_combo.addItem(f)
        # Set defaults
        idx = self.res_combo.findText(cfg["resolution_text"], Qt.MatchStartsWith)
        if idx >= 0:
            self.res_combo.setCurrentIndex(idx)
        else:
            self.res_combo.setCurrentIndex(self.res_combo.count() - 1)

        grid.setRowMinimumHeight(r, 8); r += 1
        grid.addWidget(_hline(), r, 0, 1, 2); r += 1

        # ---- Perception AI ----
        hdr2 = QLabel("Perception AI"); hdr2.setFont(bold)
        grid.addWidget(hdr2, r, 0, 1, 2); r += 1

        grid.addWidget(QLabel("Model:"), r, 0)
        self.perception_combo = QComboBox()
        self.perception_combo.setItemDelegate(_DarkComboDelegate(self.perception_combo))
        self.perception_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for opt in ["yolo (nvinfer)"]:
            self.perception_combo.addItem(opt)
        self.perception_combo.setCurrentIndex(0)
        grid.addWidget(self.perception_combo, r, 1); r += 1

        grid.setRowMinimumHeight(r, 8); r += 1
        grid.addWidget(_hline(), r, 0, 1, 2); r += 1

        # ---- Reasoning AI ----
        hdr3 = QLabel("Reasoning AI"); hdr3.setFont(bold)
        grid.addWidget(hdr3, r, 0, 1, 2); r += 1

        grid.addWidget(QLabel("Model:"), r, 0)
        self.reasoning_combo = QComboBox()
        self.reasoning_combo.setItemDelegate(_DarkComboDelegate(self.reasoning_combo))
        self.reasoning_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for opt in cfg["reasoning_options"]:
            self.reasoning_combo.addItem(opt)
        r_idx = self.reasoning_combo.findText(cfg["reasoning_default"])
        if r_idx >= 0:
            self.reasoning_combo.setCurrentIndex(r_idx)
        grid.addWidget(self.reasoning_combo, r, 1); r += 1

        grid.addWidget(QLabel("Interval:"), r, 0)
        ir = QHBoxLayout(); ir.setContentsMargins(0, 0, 0, 0)
        self.interval_edit = QLineEdit(str(cfg["interval"]))
        self.interval_edit.setAlignment(Qt.AlignRight)
        ir.addWidget(self.interval_edit)
        ir.addWidget(QLabel("ms"))
        grid.addLayout(ir, r, 1); r += 1

        grid.addWidget(QLabel("Max Tokens:"), r, 0)
        self.tokens_edit = QLineEdit(str(cfg["max_tokens"]))
        self.tokens_edit.setAlignment(Qt.AlignRight)
        grid.addWidget(self.tokens_edit, r, 1); r += 1

        grid.addWidget(QLabel("Prompt:"), r, 0); r += 1
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(cfg["prompt"])
        fm = self.prompt_edit.fontMetrics()
        self.prompt_edit.setFixedHeight((fm.height() + 4) * 8)
        self.prompt_edit.setTabChangesFocus(True)
        grid.addWidget(self.prompt_edit, r, 0, 1, 2); r += 1

        grid.setRowMinimumHeight(r, 8); r += 1
        grid.addWidget(_hline(), r, 0, 1, 2); r += 1

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

        # Tab order
        self.setTabOrder(self.camera_combo, self.res_combo)
        self.setTabOrder(self.res_combo, self.perception_combo)
        self.setTabOrder(self.perception_combo, self.reasoning_combo)
        self.setTabOrder(self.reasoning_combo, self.interval_edit)
        self.setTabOrder(self.interval_edit, self.tokens_edit)
        self.setTabOrder(self.tokens_edit, self.prompt_edit)
        self.setTabOrder(self.prompt_edit, self.start_btn)
        self.setTabOrder(self.start_btn, self.quit_btn)

        grid.setRowStretch(r, 1)

    def _connect_signals(self):
        self.perception_combo.currentTextChanged.connect(
            lambda t: self.perception_changed.emit(t))
        self.reasoning_combo.currentTextChanged.connect(
            lambda t: self.reasoning_changed.emit(t))
        self.interval_edit.textChanged.connect(self._on_interval_changed)
        self.prompt_edit.textChanged.connect(
            lambda: self.prompt_changed.emit(self.prompt_edit.toPlainText()))
        self.tokens_edit.textChanged.connect(self._on_tokens_changed)

    def _on_start_stop(self):
        if self._streaming:
            self.stop_clicked.emit()
        else:
            dev_id = self.camera_combo.currentData() or 0
            res_text = self.res_combo.currentText()
            from src.modules.video_source import VideoSource
            w, h, _ = VideoSource.parse_resolution(res_text)
            self.start_clicked.emit(int(dev_id), w, h)

    def set_streaming_state(self, streaming):
        self._streaming = streaming
        self.start_btn.setText("STOP" if streaming else "START")
        self.camera_combo.setEnabled(not streaming)
        self.res_combo.setEnabled(not streaming)

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
            val = max(1, min(int(text), 2048))
            self.max_tokens_changed.emit(val)
        except ValueError:
            pass

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
            "reasoning_model": self.reasoning_combo.currentText(),
            "interval": max(1, interval),
            "prompt": self.prompt_edit.toPlainText().strip() or "Describe this image.",
            "max_tokens": max(1, min(max_tokens, 2048)),
        }

    def camera_count(self):
        return self.camera_combo.count()
