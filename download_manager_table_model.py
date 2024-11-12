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
    _header = ("Mod Name", "Filename", "Date", "Version", "Installed?")

    def init_data(self, data):
        self._data = data
        self._selected.clear()
        self.dataChanged.emit(
            self.index(0, 0),
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
        if role == Qt.ItemDataRole.DisplayRole:
            item = self._data[index.row()]
            column = index.column()
            if item is None:
                logger.info("Received null item for row " + index.row() + " and column " + column)
                return None

            if column == 0:
                return item.modname
            elif column == 1:
                return item.filename
            elif column == 2:
                return item.filetime
            elif column == 3:
                return item.version
            elif column == 4:
                return item.installed

            return None
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def supportedDragActions(self): return None
    def supportedDropActions(self): return None

    def isSelected(self, index: QModelIndex):
        return self._selected.get(index.row(), False)

