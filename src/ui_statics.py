try:
    import PyQt6.QtWidgets as QtWidgets
    from PyQt6.QtWidgets import QHeaderView
    from PyQt6.QtGui import QPalette, QColor, QFont, QPainter, QPen
    from PyQt6.QtCore import Qt, QTimer
except ImportError:
    import PyQt5.QtWidgets as QtWidgets
    from PyQt5.QtWidgets import QHeaderView
    from PyQt5.QtGui import QPalette, QColor, QFont, QPainter, QPen
    from PyQt5.QtCore import Qt, QTimer

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

def create_basic_table_widget(alternate_rows: bool = True):
    """Set the model after creating this. Cleans up window code"""
    table = QtWidgets.QTableView()
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(alternate_rows)
    table.setSizeAdjustPolicy(
        QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
    )
    table.setShowGrid(False)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(
        QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked
        | QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
    )
    table.setMouseTracking(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    return table


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
