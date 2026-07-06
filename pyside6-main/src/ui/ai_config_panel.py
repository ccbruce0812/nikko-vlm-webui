from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTextEdit, QComboBox, QSizePolicy)
from PySide6.QtCore import Qt, Signal, Slot


class AIConfigPanel(QWidget):
    submit_clicked = Signal(str, str)  # model, prompt

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Inference")
        self.setMinimumWidth(500)
        self._vlm_models = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Model selector (VLM only, YOLO is auto)
        layout.addWidget(QLabel("VLM Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.model_combo)

        # Prompt
        layout.addWidget(QLabel("Prompt:"))
        self.prompt_edit = QLineEdit("Describe this image in one sentence.")
        layout.addWidget(self.prompt_edit)

        # Submit
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self._on_submit)
        self.submit_btn.setEnabled(False)
        layout.addWidget(self.submit_btn)

        # Result display
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setPlaceholderText("Inference result...")
        self.result_display.setMinimumHeight(120)
        layout.addWidget(self.result_display)

        layout.addStretch()
        self._update_state()

    # ---- Public ----

    def set_vlm_models(self, models):
        self._vlm_models = models
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for m in models:
            self.model_combo.addItem(m)
        self.model_combo.blockSignals(False)
        self._update_state()

    @Slot(str)
    def set_result(self, text):
        self.result_display.setText(text)

    # ---- Private ----

    def _on_submit(self):
        model = self.model_combo.currentText()
        prompt = self.prompt_edit.text().strip()
        if not model or not prompt:
            return
        self.submit_btn.setEnabled(False)
        self.result_display.setText(f"Running {model}...")
        self.submit_clicked.emit(model, prompt)

    def _update_state(self):
        has_vlm = len(self._vlm_models) > 0
        self.model_combo.setEnabled(has_vlm)
        self.prompt_edit.setEnabled(has_vlm)
        self.submit_btn.setEnabled(has_vlm)
        if not has_vlm:
            self.result_display.setPlaceholderText(
                "No VLM models available. Start reason2 or moondream2 first."
            )
