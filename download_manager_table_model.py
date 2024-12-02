from collections import defaultdict
from typing import List, Dict

from .util import logger
from .download_entry import DownloadEntry

try:
    import PyQt6.QtCore as QtCore
    from PyQt6.QtCore import Qt, QModelIndex
    from PyQt6.QtWidgets import QApplication
except ImportError:
    import PyQt5.QtCore as QtCore
    from PyQt5.QtCore import Qt, QModelIndex
    from PyQt5.QtWidgets import QApplication

class DownloadManagerTableModel(QtCore.QAbstractTableModel):

    # filename, filetime, version, installed
    _data: List[DownloadEntry] = []
    _selected: Dict[int, bool] = defaultdict(lambda: False)

    # Remove selected from the DownloadEntry model. Not necessary
    _header = ("Mod Name", "Filename", "Date", "Version", "Installed?")

    def init_data(self, data):
        self._data = data
        self._selected.clear()
        self.dataChanged.emit(
            self.index(0, 1),
            self.index(len(self._data) - 1, len(self._header) - 1),
        )
        self.layoutChanged.emit()

    def headerData(self, section, orientation, role = ...):
        if role == Qt.ItemDataRole.DisplayRole:
            return self._header[section]

    def columnCount(self, parent = ...):
        return 5

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._data)

    def data(self, index: QModelIndex, role: int = ...):
        row = index.row()
        item = self._data[row]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if item is None:
                logger.info("Received null item for row " + index.row() + " and column " + column)
                return None
            columns = [None, item.modname, item.filename, item.filetime, item.version, item.installed]
            if column < len(columns): return columns[column]
            return None

        if role == Qt.ItemDataRole.CheckStateRole and column == 0:
            return Qt.CheckState.Checked if self._selected[row] else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def setData(self, index: QModelIndex, value, role = ...):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            row = index.row()
            # Update the checkbox state in the _selected dictionary
            self._selected[row] = value == Qt.CheckState.Checked
            # Log for debugging
            logger.info(f"Row {row} checkbox state updated to: {self._selected[row]}")
            # Emit dataChanged to notify the view
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return False

    def supportedDragActions(self): return None
    def supportedDropActions(self): return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        if index.column() == 0:
            return (
                    Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEditable
            )

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def isSelected(self, index: QModelIndex):
        return self._selected.get(index.row(), False)

