from datetime import datetime
from typing import List

from .download_entry import DownloadEntry
from .download_manager_model import DownloadManagerModel
from .util import logger

try:
    import PyQt6.QtCore as QtCore
    from PyQt6.QtCore import Qt, QModelIndex
    from PyQt6.QtGui import QColor
except ImportError:
    import PyQt5.QtCore as QtCore
    from PyQt5.QtCore import Qt, QModelIndex
    from PyQt5.QtGui import QColor


def _render_column(item, index):
    column = index.column()
    if item is None:
        logger.info(
            "Received null item for row " + index.row() + " and column " + column
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

    # pylint:disable=invalid-name
    def headerData(self, section, _orientation, role=...):
        if role == Qt.ItemDataRole.DisplayRole:
            if section > len(self._header) - 1:
                logger.error("Section out of bounds %s %s", section, role)
                return None
            return self._header[section]
        return None

    # pylint:disable=invalid-name
    def columnCount(self, _parent=...):
        return 6

    # pylint:disable=invalid-name
    def rowCount(self, _parent=QtCore.QModelIndex()):
        return len(self._data)

    def _first_column(self, role, item):
        if role == Qt.ItemDataRole.CheckStateRole:
            return (
                Qt.CheckState.Checked
                if item in self._selected
                else Qt.CheckState.Unchecked
            )
        if role == Qt.ItemDataRole.DisplayRole:
            return item.name
        return None

    def data(self, index: QModelIndex, role: int = ...):
        row = index.row()
        item = self._data[row]
        column = index.column()

        # Decorative roles will go first to ensure they are applied evenly across columns
        if role == QtCore.Qt.ItemDataRole.BackgroundRole:
            opacity_red = QColor(255, 0, 0, 77)  # Red with 30% opacity
            return opacity_red if item in self._selected else None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if column == 0:
            return self._first_column(role, item)

        if role == Qt.ItemDataRole.DisplayRole and column > 0:
            return _render_column(item, index)

        return None

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
            # these qt5/qt6 imports act a little strangely with pylint. this member does exist.
            # pylint:disable=no-member
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
        if self._model:
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
        if self._model:
            self._model.bulk_install(self._selected)
            self.notify_table_updated()

    def delete_selected(self):
        if self._model:
            for item in self._selected:
                self._model.delete(item)

    def hide_selected(self):
        if self._model:
            self._model.bulk_hide(self._selected)

    def notify_table_updated(self):
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self._data) - 1, len(self._header) - 1),
        )
