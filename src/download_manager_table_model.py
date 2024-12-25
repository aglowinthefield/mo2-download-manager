from datetime import datetime
from typing import Callable, Dict, List, Set

import mobase

try:
    import PyQt6.QtCore as QtCore
    from PyQt6.QtCore import Qt, QModelIndex, QAbstractTableModel
    from PyQt6.QtGui import QColor
except ImportError:
    import PyQt5.QtCore as QtCore
    from PyQt5.QtCore import Qt, QModelIndex, QAbstractTableModel
    from PyQt5.QtGui import QColor

from .download_entry import DownloadEntry
from .download_manager_model import DownloadManagerModel
from .hash_worker import HashWorker
from .mo2_compat_utils import CHECKED_STATE
from .ui_statics import HashProgressDialog, bool_emoji, value_or_no
from .util import logger, sizeof_fmt



class DownloadManagerTableModel(QAbstractTableModel):

    SELECTED_ROW_COLOR = QColor(0, 128, 0, 70)

    COLUMN_MAPPING: Dict[int, Callable[[DownloadEntry], str]] = {
        0: lambda item: item.name,
        1: lambda item: item.modname,
        2: lambda item: item.filename,
        3: lambda item: item.filetime,
        4: lambda item: item.version,
        5: lambda item: item.file_size,
        6: lambda item: item.installed,
        7: lambda item: item.nexus_mod_id,
        8: lambda item: item.nexus_file_id,
    }

    # filename, filetime, version, installed
    _data: List[DownloadEntry] = []
    _model: DownloadManagerModel = None
    _selected: Set[DownloadEntry] = set()

    # Remove selected from the DownloadEntry model. Not necessary
    _header = ("Name", "Mod Name", "Filename", "Date", "Version", "Size", "Installed?", "Mod ID", "File ID")

    def __init__(self, organizer: mobase.IOrganizer):
        super().__init__()
        self.hash_worker: HashWorker
        self.hash_dialog: HashProgressDialog
        self._model = DownloadManagerModel(organizer)

    def init_data(self, data: List[DownloadEntry]):
        self._data = data
        self._selected.clear()
        self._notify_table_updated()
        self.layoutChanged.emit()

    def headerData(self, section, _orientation, role=...):
        if role == Qt.ItemDataRole.DisplayRole:
            if section > len(self._header) - 1:
                logger.error("Section out of bounds %s %s", section, role)
                return None
            return self._header[section]
        return None

    def columnCount(self, _parent=...):
        return len(self._header)

    def rowCount(self, _parent=QtCore.QModelIndex()):
        return len(self._data)

    def _render_column(self, item, index):
        get_value = self.COLUMN_MAPPING.get(index.column())

        if get_value is None:
            return None

        column_value = get_value(item)

        if index.column() == 5:
            return sizeof_fmt(column_value)
        if isinstance(column_value, bool):
            return bool_emoji(column_value)
        if isinstance(column_value, datetime):
            return column_value.strftime("%Y-%m-%d %H:%M:%S")
        return value_or_no(column_value)

    def data(self, index: QModelIndex, role: int = ...):
        item = self._data[index.row()]

        # Decorative roles will go first to ensure they are applied evenly across columns
        if role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return self.SELECTED_ROW_COLOR if item in self._selected else None

        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            return (
                Qt.CheckState.Checked
                if item in self._selected
                else Qt.CheckState.Unchecked
            )

        if role == Qt.ItemDataRole.DisplayRole:
            return self._render_column(item, index)

        get_value = self.COLUMN_MAPPING.get(index.column())(item)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if get_value == "" or get_value is None:
                return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


        return None

    def setData(self, index: QModelIndex, value, role=...):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            selected = value == CHECKED_STATE
            selected_data = self._data[index.row()]
            (
                self._selected.add(selected_data)
                if selected
                else self._selected.remove(selected_data)
            )
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return False

    def select_at_index(self, index: QModelIndex):
        selected_data = self._data[index.row()]
        if selected_data not in self._selected:
            self._selected.add(selected_data)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

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
            key=lambda row: (
                float(self.COLUMN_MAPPING[column](row))
                if isinstance(self.COLUMN_MAPPING[column](row), (int, float))
                else str(self.COLUMN_MAPPING[column](row)).lower()
            ),
            reverse=(order == Qt.SortOrder.DescendingOrder),
        )
        self.layoutChanged.emit()

    def get_selected(self):
        return self._selected

    def requery(self, mod: DownloadEntry, md5_hash: str):
        self._model.requery(mod, md5_hash)
        self._data = self._model.data
        self._selected.remove(mod)
        self._notify_table_updated()

    def select_duplicates(self):
        if self._model:
            self._selected = self._model.get_duplicates()
            self._notify_table_updated()

    def select_all(self):
        for item in self._data:
            self._selected.add(item)
        self._notify_table_updated()

    def select_none(self):
        self._selected.clear()
        self._notify_table_updated()

    def install_selected(self):
        if self._model:
            self._model.bulk_install(self._selected)
            self._notify_table_updated()

    def delete_selected(self):
        if self._model:
            for item in self._selected:
                self._model.delete(item)

    def hide_selected(self):
        if self._model:
            self._model.bulk_hide(self._selected)

    def toggle_show_installed(self, show_installed: bool):
        if show_installed:
            self._data = self._model.data_no_installed
        else:
            self._data = self._model.data
        self._notify_table_updated()

    def refresh(self):
        self._model.refresh()
        self.init_data(self._model.data)


    def _notify_index_updated(self, index: QModelIndex):
        self.dataChanged.emit(index, index)

    def _notify_table_updated(self):
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self._data) - 1, len(self._header) - 1),
        )

    @property
    def selected(self):
        return self._selected
