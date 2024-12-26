from typing import Union

from .download_manager_table_model import DownloadManagerTableModel

try:
    from PyQt6.QtCore import QModelIndex, Qt, QSortFilterProxyModel
except ImportError:
    from PyQt5.QtCore import QModelIndex, Qt, QSortFilterProxyModel


class DownloadSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, Qt.ItemDataRole.CheckStateRole)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.CheckStateRole)

        if left_data is not None and right_data is not None:
            return left_data < right_data

        left_data = self.sourceModel().data(left, Qt.ItemDataRole.DisplayRole)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole)

        if left_data is None or right_data is None:
            return False
        return str(left_data).lower() < str(right_data).lower()

    # def toggle_at_index(self, index: QModelIndex, selected: Union[bool, None]):
