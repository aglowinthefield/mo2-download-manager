from collections import defaultdict
from datetime import datetime
from typing import List, Dict

from PyQt6.QtGui import QColor

from .download_manager_model import DownloadManagerModel
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
    _model: DownloadManagerModel = None
    _selected: Dict[int, bool] = defaultdict(lambda: False)

    # Remove selected from the DownloadEntry model. Not necessary
    _header = ("Mod Name", "Filename", "Date", "Version", "Installed?")
    _columnFields = ["modname", "filename", "filetime", "version", "installed"]

    def init_data(self, data: List[DownloadEntry], model: DownloadManagerModel):
        self._data = data
        self._model = model
        self._selected.clear()
        self.dataChanged.emit(
            self.index(0, 1),
            self.index(len(self._data) - 1, len(self._header) - 1),
        )
        self.layoutChanged.emit()

    def headerData(self, section, orientation, role=...):
        if role == Qt.ItemDataRole.DisplayRole:
            if section > len(self._header) - 1:
                logger.error(f"Section out of bounds {section} {role}")
            return self._header[section]

    def columnCount(self, parent=...):
        return 5

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._data)

    def data(self, index: QModelIndex, role: int = ...):
        row = index.row()
        item = self._data[row]
        column = index.column()

        if column == 0:
            if role == Qt.ItemDataRole.CheckStateRole:
                return (
                    Qt.CheckState.Checked
                    if self._selected[row]
                    else Qt.CheckState.Unchecked
                )
            if role == Qt.ItemDataRole.DisplayRole:
                return item.modname

        if role == Qt.ItemDataRole.DisplayRole and column > 0:
            if item is None:
                logger.info(
                    "Received null item for row "
                    + index.row()
                    + " and column "
                    + column
                )
                return None
            columns = [None, item.filename, item.filetime, item.version, item.installed]
            if column < len(columns):
                column_value = columns[column]
                if isinstance(column_value, datetime):
                    return column_value.strftime("%Y-%m-%d %H:%M:%S")
                return columns[column]
            return None

        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            # Set background color for selected rows
            opacity_red = QColor(255, 0, 0, 77)  # Red with 30% opacity
            row = index.row()
            if self._selected[row]:  # Check if the row is selected
                return opacity_red
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def setData(self, index: QModelIndex, value, role=...):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            self._selected[index.row()] = value == Qt.CheckState.Checked.value
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return False

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        if index.column() == 0:
            return (
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def sort(self, column, order=...):
        self.layoutAboutToBeChanged.emit()
        self._data.sort(
            key=lambda row: str(row[self._columnFields[column]]).lower(),
            reverse=(order == Qt.SortOrder.DescendingOrder),
        )
        self.layoutChanged.emit()

    def isSelected(self, index: QModelIndex):
        return self._selected.get(index.row(), False)

    # def select_all(self):

    def delete_selected(self):
        indices = [key for key, value in self._selected.items() if value]
        for index in indices:
            self._model.delete_at_index(index)
