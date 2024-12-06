from datetime import datetime
from typing import List

from PyQt6.QtGui import QColor

from .download_entry import DownloadEntry
from .download_manager_model import DownloadManagerModel
from .util import logger

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
    _selected: set[DownloadEntry] = set()

    # Remove selected from the DownloadEntry model. Not necessary
    _header = ("Name", "Mod Name", "Filename", "Date", "Version", "Installed?")
    _columnFields = ["name", "modname", "filename", "filetime", "version", "installed"]

    def init_data(self, data: List[DownloadEntry], model: DownloadManagerModel):
        self._data = data
        self._model = model
        self._selected.clear()
        self.notify_table_updated()
        self.layoutChanged.emit()

    def headerData(self, section, orientation, role=...):
        if role == Qt.ItemDataRole.DisplayRole:
            if section > len(self._header) - 1:
                logger.error(f"Section out of bounds {section} {role}")
            return self._header[section]

    def columnCount(self, parent=...):
        return 6

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
                    if item in self._selected
                    else Qt.CheckState.Unchecked
                )
            if role == Qt.ItemDataRole.DisplayRole:
                return item.name

        if role == Qt.ItemDataRole.DisplayRole and column > 0:
            if item is None:
                logger.info(
                    "Received null item for row "
                    + index.row()
                    + " and column "
                    + column
                )
                return None
            columns = [
                None,
                item.modname,
                item.filename,
                item.filetime,
                item.version,
                item.installed,
            ]
            if column < len(columns):
                column_value = columns[column]
                if isinstance(column_value, QtCore.QDateTime):
                    if not column_value.isValid():
                        return None
                    string_date = column_value.toString("yyyy-MM-dd HH:mm:ss")
                    logger.info(string_date)
                    return string_date
                if isinstance(column_value, datetime):
                    return column_value.strftime("%Y-%m-%d %H:%M:%S")
                return columns[column]
            return None

        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            # Set background color for selected rows
            opacity_red = QColor(255, 0, 0, 77)  # Red with 30% opacity
            return opacity_red if item in self._selected else None
            # if self._selected[row]:  # Check if the row is selected
            #     return opacity_red
            # return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def setData(self, index: QModelIndex, value, role=...):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            selected = value == Qt.CheckState.Checked.value
            selected_data = self._data[index.row()]
            (
                self._selected.add(selected_data)
                if selected
                else self._selected.remove(selected_data)
            )
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

    def select_duplicates(self):
        self._selected = self._model.get_duplicates()
        self.notify_table_updated()

    def select_all(self):
        for item in self._data:
            self._selected.add(item)
        self.notify_table_updated()

    def select_none(self):
        self._selected.clear()
        self.notify_table_updated()

    def install_selected(self):
        self._model.bulk_install(self._selected)
        self.notify_table_updated()

    def delete_selected(self):
        for item in self._selected:
            self._model.delete(item)

    def hide_selected(self):
        self._model.bulk_hide(self._selected)

    def notify_table_updated(self):
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self._data) - 1, len(self._header) - 1),
        )
