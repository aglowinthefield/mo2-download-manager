from typing import Callable, Dict

from PyQt6.QtGui import QIcon

try:
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

class ComboBoxWithPlaceholder(QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.placeholder_text = "Select..."
        self.addItem(self.placeholder_text)
        self.setCurrentIndex(0)
        self.model().item(0).setEnabled(False)
        self.handlers = {}
        self.currentIndexChanged.connect(self._handle_selection)

    def addItemWithHandler(self, text: str, handler: Callable):
        self.addItem(text)
        self.handlers[self.count() - 1] = handler

    def _handle_selection(self, index: int):
        if index in self.handlers:
            self.handlers[index]()

def combo_box_with_handlers(parent, actions: Dict[str, Callable]) -> ComboBoxWithPlaceholder:
    combo_box = ComboBoxWithPlaceholder(parent)
    for action, handler in actions.items():
        combo_box.addItemWithHandler(action, handler)
    return combo_box


def bool_emoji(value: bool):
    if value:
        return "✅"
    return "🚫"

def value_or_no(value: object):
    return value if value else "❔"
