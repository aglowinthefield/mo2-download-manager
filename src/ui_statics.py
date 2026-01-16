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


class SpinnerWidget(QtWidgets.QWidget):
    """A simple animated spinning arc."""

    def __init__(self, parent=None, size: int = 48, line_width: int = 4):
        super().__init__(parent)
        self._size = size
        self._line_width = line_width
        self._rotation = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)  # type: ignore
        self._timer.setInterval(16)  # ~60fps

        self.setFixedSize(size, size)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _animate(self):
        self._rotation = (self._rotation + 5) % 360
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Use palette color for the spinner
        color = self.palette().color(QPalette.ColorRole.Highlight)

        pen = QPen(color)
        pen.setWidth(self._line_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Draw arc
        margin = self._line_width
        rect_size = self._size - (margin * 2)
        rect = (margin, margin, rect_size, rect_size)

        # Arc spans 270 degrees, rotates around
        start_angle = int(self._rotation * 16)  # Qt uses 1/16th of a degree
        span_angle = 270 * 16

        painter.drawArc(*rect, start_angle, span_angle)
        painter.end()


class LoadingOverlay(QtWidgets.QWidget):
    """A full-window loading overlay with an animated spinner and message."""

    def __init__(self, parent=None, message: str = "Loading downloads..."):
        super().__init__(parent)
        self._message = message

        # Make overlay cover the entire parent with semi-transparent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAutoFillBackground(True)

        # Use a semi-transparent version of the window background
        palette = self.palette()
        bg_color = palette.color(QPalette.ColorRole.Window)
        bg_color.setAlpha(230)
        palette.setColor(QPalette.ColorRole.Window, bg_color)
        self.setPalette(palette)

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Spinner
        self._spinner = SpinnerWidget(self, size=64, line_width=5)
        layout.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        # Spacer
        layout.addSpacing(20)

        # Message label
        self._label = QtWidgets.QLabel(message)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_font = QFont()
        label_font.setPointSize(12)
        label_font.setBold(True)
        self._label.setFont(label_font)
        layout.addWidget(self._label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Sub-message
        self._sub_label = QtWidgets.QLabel("Reading download metadata...")
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_font = QFont()
        sub_font.setPointSize(10)
        self._sub_label.setFont(sub_font)
        layout.addWidget(self._sub_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
        self.hide()

    def set_message(self, message: str):
        self._label.setText(message)

    def set_sub_message(self, message: str):
        self._sub_label.setText(message)

    def show_overlay(self):
        if self.parent():
            self.setGeometry(self.parent().rect())
        self._spinner.start()
        self.show()
        self.raise_()

    def hide_overlay(self):
        self._spinner.stop()
        self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())
