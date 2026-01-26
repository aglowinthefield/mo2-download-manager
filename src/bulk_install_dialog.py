from typing import List, Callable

try:
    import PyQt6.QtWidgets as QtWidgets
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
except ImportError:
    import PyQt5.QtWidgets as QtWidgets
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication

from .download_entry import DownloadEntry
from .util import logger


class BulkInstallPanel(QtWidgets.QWidget):
    STATUS_PENDING = "⏳"
    STATUS_INSTALLING = "🔄"
    STATUS_SUCCESS = "✅"
    STATUS_FAILED = "❌"
    STATUS_SKIPPED = "⏭️"

    installation_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mods: List[DownloadEntry] = []
        self._install_fn: Callable[[DownloadEntry], bool] = None
        self._cancelled = False
        self._is_finished = False
        self._is_running = False
        self._current_index = 0
        self._success_count = 0
        self._fail_count = 0
        self._skipped_count = 0
        self._mod_to_row = {}

        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        self.setMinimumHeight(250)
        self.setMaximumHeight(400)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)

        header_layout = QtWidgets.QHBoxLayout()

        self._progress_label = QtWidgets.QLabel("Preparing to install...")
        progress_font = QFont()
        progress_font.setPointSize(12)
        progress_font.setBold(True)
        self._progress_label.setFont(progress_font)
        header_layout.addWidget(self._progress_label)

        header_layout.addStretch()

        self._cancel_button = QtWidgets.QPushButton("Cancel")
        self._cancel_button.setFixedWidth(90)
        self._cancel_button.setToolTip("Cancel remaining installations (there's a short delay between mods to click this)")
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        header_layout.addWidget(self._cancel_button)

        self._close_button = QtWidgets.QPushButton("Close")
        self._close_button.setFixedWidth(90)
        self._close_button.clicked.connect(self._on_close_clicked)
        self._close_button.hide()
        header_layout.addWidget(self._close_button)

        main_layout.addLayout(header_layout)

        self._current_mod_label = QtWidgets.QLabel("")
        self._current_mod_label.setWordWrap(True)
        current_font = QFont()
        current_font.setPointSize(11)
        self._current_mod_label.setFont(current_font)
        main_layout.addWidget(self._current_mod_label)

        self._list_widget = QtWidgets.QListWidget()
        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._list_widget.setMinimumHeight(150)
        list_font = QFont()
        list_font.setPointSize(11)
        self._list_widget.setFont(list_font)
        main_layout.addWidget(self._list_widget, 1)

        self._summary_label = QtWidgets.QLabel("")
        self._summary_label.setWordWrap(True)
        summary_font = QFont()
        summary_font.setPointSize(11)
        summary_font.setBold(True)
        self._summary_label.setFont(summary_font)
        self._summary_label.hide()
        main_layout.addWidget(self._summary_label)

    def start_installation(self, mods: List[DownloadEntry], install_fn: Callable[[DownloadEntry], bool]):
        if self._is_running:
            logger.warning("BulkInstallPanel: installation already in progress")
            return

        logger.debug("BulkInstallPanel.start_installation: starting with %d mods", len(mods))

        self._mods = list(mods)
        self._install_fn = install_fn
        self._cancelled = False
        self._is_finished = False
        self._is_running = True
        self._current_index = 0
        self._success_count = 0
        self._fail_count = 0
        self._skipped_count = 0
        self._mod_to_row.clear()

        self._list_widget.clear()
        self._progress_label.setText("Preparing to install...")
        self._current_mod_label.setText("")
        self._summary_label.hide()
        self._cancel_button.setText("Cancel")
        self._cancel_button.setEnabled(True)
        self._cancel_button.show()
        self._close_button.hide()

        self._populate_list()
        self.show()

        QTimer.singleShot(100, self._process_next_mod)

    def _populate_list(self):
        for i, mod in enumerate(self._mods):
            display_name = mod.name if mod.name else mod.filename
            item = QtWidgets.QListWidgetItem(f"{self.STATUS_PENDING} {display_name}")
            self._list_widget.addItem(item)
            self._mod_to_row[mod] = i

    def _process_next_mod(self):
        if self._cancelled or self._current_index >= len(self._mods):
            self._finish_installation()
            return

        mod = self._mods[self._current_index]
        logger.debug("BulkInstallPanel._process_next_mod: processing %d/%d: %s", 
                    self._current_index + 1, len(self._mods), mod.filename)

        self._update_ui_mod_starting(mod)
        QApplication.processEvents()

        logger.debug("BulkInstallPanel._process_next_mod: calling install_fn for %s", mod.filename)
        try:
            success = self._install_fn(mod)
            logger.debug("BulkInstallPanel._process_next_mod: install_fn returned %s for %s", success, mod.filename)
        except Exception as e:
            logger.error("BulkInstallPanel._process_next_mod: exception for %s: %s", mod.filename, e)
            success = False

        if success:
            self._success_count += 1
        else:
            self._fail_count += 1

        self._update_ui_mod_completed(mod, success)
        QApplication.processEvents()

        self._current_index += 1

        if self._cancelled:
            self._skipped_count = len(self._mods) - self._current_index
            self._finish_installation()
        else:
            QTimer.singleShot(2000, self._process_next_mod)

    def _update_ui_mod_starting(self, mod: DownloadEntry):
        row = self._mod_to_row.get(mod)
        if row is not None:
            display_name = mod.name if mod.name else mod.filename
            item = self._list_widget.item(row)
            if item:
                item.setText(f"{self.STATUS_INSTALLING} {display_name}")
                self._list_widget.scrollToItem(item)

        self._progress_label.setText(f"Installing {self._current_index + 1} of {len(self._mods)}...")
        self._current_mod_label.setText(f"Current: {mod.filename}")

    def _update_ui_mod_completed(self, mod: DownloadEntry, success: bool):
        row = self._mod_to_row.get(mod)
        if row is not None:
            display_name = mod.name if mod.name else mod.filename
            status = self.STATUS_SUCCESS if success else self.STATUS_FAILED
            item = self._list_widget.item(row)
            if item:
                item.setText(f"{status} {display_name}")

    def _finish_installation(self):
        logger.debug("BulkInstallPanel._finish_installation: success=%d, fail=%d, skipped=%d",
                    self._success_count, self._fail_count, self._skipped_count)
        self._is_finished = True
        self._is_running = False
        self._cancel_button.hide()
        self._close_button.show()

        for mod in self._mods:
            row = self._mod_to_row.get(mod)
            if row is not None:
                item = self._list_widget.item(row)
                if item and item.text().startswith(self.STATUS_PENDING):
                    display_name = mod.name if mod.name else mod.filename
                    item.setText(f"{self.STATUS_SKIPPED} {display_name}")

        self._progress_label.setText("Installation Complete")
        self._current_mod_label.hide()

        summary_parts = []
        if self._success_count > 0:
            summary_parts.append(f"{self._success_count} installed")
        if self._fail_count > 0:
            summary_parts.append(f"{self._fail_count} failed")
        if self._skipped_count > 0:
            summary_parts.append(f"{self._skipped_count} skipped")

        if summary_parts:
            self._summary_label.setText("Result: " + ", ".join(summary_parts))
            self._summary_label.show()

        self.installation_finished.emit()

    def _on_cancel_clicked(self):
        if not self._is_finished:
            logger.debug("BulkInstallPanel._on_cancel_clicked: cancel requested")
            self._cancel_button.setEnabled(False)
            self._cancel_button.setText("Cancelling...")
            self._cancelled = True

    def _on_close_clicked(self):
        self._current_mod_label.show()
        self.hide()

    def is_running(self) -> bool:
        return self._is_running
