﻿try:
    import PyQt6.QtWidgets as QtWidgets
except ImportError:
    import PyQt5.QtWidgets as QtWidgets

class HashProgressDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛠️ Hashing Archive...")
        self.progress_bar = QtWidgets.QProgressBar() # import properly later
        self.progress_bar.setRange(0, 100)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel) # type: ignore
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.cancel_button)
        self.setLayout(layout)

    def update_progress(self, value: int):
        self.progress_bar.setValue(value)

    def cancel(self):
        self.reject()

def button_with_handler(text, parent, handler) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text, parent)
    button.clicked.connect(handler) # type: ignore
    return button

def bool_emoji(value: bool):
    if value:
        return "✅"
    return "🚫"

def value_or_no(value: object):
    return value if value else "❔"
