from .download_entry import DownloadEntry

try:
    from PyQt6.QtCore import QSortFilterProxyModel
except ImportError:
    from PyQt5.QtCore import QSortFilterProxyModel


class DownloadSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left)
        right_data = self.sourceModel().data(right)
        if left_data is None or right_data is None:
            return False
        return left_data < right_data
