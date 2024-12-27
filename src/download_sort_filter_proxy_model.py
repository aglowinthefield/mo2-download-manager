from typing import Union

from .mo2_compat_utils import CHECKED_STATE

try:
    from PyQt6.QtCore import QModelIndex, Qt, QSortFilterProxyModel
except ImportError:
    from PyQt5.QtCore import QModelIndex, Qt, QSortFilterProxyModel


class DownloadSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def lessThan(self, left, right):

        did_compare_checked = self._compare_checked(left, right)
        if did_compare_checked is not None:
            return did_compare_checked

        left_data = self.sourceModel().data(left, Qt.ItemDataRole.DisplayRole)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole)

        if left_data is None or right_data is None:
            return False
        return str(left_data).lower() < str(right_data).lower()

    def _compare_checked(self, left, right) -> Union[bool, None]:
        left_data = self.sourceModel().data(left, Qt.ItemDataRole.CheckStateRole)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.CheckStateRole)

        if left_data is not None and right_data is not None:
            return left_data == Qt.CheckState.Checked and right_data != Qt.CheckState.Checked

        if left_data is not None:
            return left_data == Qt.CheckState.Checked

        if right_data is not None:
            return right_data != Qt.CheckState.Checked
        return None
