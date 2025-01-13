﻿from typing import Union

from .download_manager_table_model import DownloadManagerTableModel
from .download_sort_filter_proxy_model import DownloadSortFilterProxyModel

try:
  from PyQt6 import QtWidgets
  from PyQt6.QtCore import QModelIndex, Qt
  from PyQt6.QtWidgets import QHeaderView, QTableView
except ImportError:
  from PyQt5 import QtWidgets
  from PyQt5.QtCore import QModelIndex, Qt
  from PyQt5.QtWidgets import QHeaderView, QTableView


class DownloadsTable(QTableView):
  _proxy_model: DownloadSortFilterProxyModel

  def __init__(self, parent=None):
    super().__init__(parent)
    self.horizontalHeader().setHighlightSections(False)
    self.horizontalHeader().setSectionsClickable(True)
    # self.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
    self.horizontalHeader().setSortIndicatorShown(True)
    self.horizontalHeader().setStretchLastSection(True)

    self.setAlternatingRowColors(True)
    self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    self.setShowGrid(False)
    self.setSortingEnabled(True)
    self.verticalHeader().setVisible(False)

    self.setSizeAdjustPolicy(
      QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
    )
    self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    self.setEditTriggers(
      QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked
      | QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
    )
    self.setMouseTracking(True)
    self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    self._proxy_model = DownloadSortFilterProxyModel()
    self._proxy_model.setFilterKeyColumn(-1)
    self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    self._proxy_model.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

  def setModel(self, model: DownloadManagerTableModel):
    self._proxy_model.setSourceModel(model)
    super().setModel(self._proxy_model)  # type: ignore
    self.sortByColumn(1, Qt.SortOrder.AscendingOrder)

  def setFilterString(self, filter_string: str):
    self._proxy_model.setFilterFixedString(filter_string)

  def toggle_at_index(self, index: QModelIndex, selected: Union[bool, None] = None):
    if not index.isValid():
      return

    current_index = self._proxy_model.mapToSource(index)
    source: DownloadManagerTableModel = self._proxy_model.sourceModel()  # type: ignore
    source.toggle_at_index(current_index, selected)

  def keyPressEvent(self, e):
    if e.key() != Qt.Key.Key_Space:
      super().keyPressEvent(e)
      return

    current_index = self.currentIndex()
    if current_index.isValid():
      source_index = self._proxy_model.mapToSource(current_index)
      checkbox_index = source_index.siblingAtColumn(0)
      source: DownloadManagerTableModel = self._proxy_model.sourceModel()  # type: ignore
      source.toggle_at_index(checkbox_index, None)
