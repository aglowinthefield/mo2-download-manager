from .download_manager_table_model import DownloadManagerTableModel
from .multi_filter_proxy_model import MultiFilterProxyModel, MultiFilterMode

try:
    import PyQt6.QtCore as QtCore
    import PyQt6.QtGui as QtGui
    import PyQt6.QtWidgets as QtWidgets
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
except ImportError:
    import PyQt5.QtCore as QtCore
    import PyQt5.QtGui as QtGui
    import PyQt5.QtWidgets as QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

import mobase

from .download_manager_model import DownloadManagerModel


def show_error(message, header, icon=QtWidgets.QMessageBox.Icon.Warning):
    exception_box = QtWidgets.QMessageBox()
    exception_box.setWindowTitle("Download Manager")
    exception_box.setText(header)
    exception_box.setIcon(icon)
    exception_box.setInformativeText(message)
    exception_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    exception_box.exec()


class DownloadManagerWindow(QtWidgets.QDialog):

    __model: DownloadManagerModel = None

    def __init__(self, organizer: mobase.IOrganizer, parent=None):
        try:
            self.__organizer = organizer
            self.__model = DownloadManagerModel(organizer)
            super().__init__(parent)

            self._table_model = DownloadManagerTableModel()

            self._table_model_proxy = MultiFilterProxyModel()
            self._table_model_proxy.setMultiFilterMode(MultiFilterMode.OR)
            self._table_model_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._table_model_proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._table_model_proxy.setSourceModel(self._table_model)

            self._table_widget = self.create_table_widget()

            """
            Top row has 3 buttons:
                Refresh: scans downloads for duplicates and makes the table
                Select Duplicates
                Select All
                
            Main layout: vertical
                Horizontal layout
                Table layout (horizontal)
                Delete Button
            """
            main_layout = QtWidgets.QVBoxLayout()

            wrapper_top = QtWidgets.QWidget()
            layout_top = QtWidgets.QHBoxLayout()
            layout_top.addWidget(self.create_refresh_button())
            wrapper_top.setLayout(layout_top)

            wrapper_bottom = QtWidgets.QWidget()
            layout_bottom = QtWidgets.QVBoxLayout()
            layout_bottom.addWidget(self._table_widget)
            wrapper_bottom.setLayout(layout_bottom)

            wrapper_delete = QtWidgets.QWidget()
            layout_delete = QtWidgets.QHBoxLayout()
            layout_delete.addWidget(self.create_delete_button())
            wrapper_delete.setLayout(layout_delete)

            main_layout.addWidget(wrapper_top)
            main_layout.addWidget(wrapper_bottom)
            main_layout.addWidget(wrapper_delete)

            self.setLayout(main_layout)
            self.setBaseSize(800, 600)

        except Exception as ex:
            show_error(repr(ex), "Critical error! Please report this on Nexus / GitHub.",
                            QtWidgets.QMessageBox.Icon.Critical)

    def create_delete_button(self):
        delete_button = QtWidgets.QPushButton("Delete Selected", self)
        delete_button.clicked.connect(self.delete_selected) # type: ignore
        return delete_button

    def create_refresh_button(self):
        refresh_button = QtWidgets.QPushButton("Refresh", self)
        refresh_button.clicked.connect(self.refresh_data) # type: ignore
        return refresh_button

    def delete_selected(self):
        return True

    def refresh_data(self):
        self.__model.refresh()
        self._table_model.init_data(self.__model.data)

    def create_table_widget(self):
        table = QtWidgets.QTableView()
        table.setModel(self._table_model)
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(False)
        table.setAlternatingRowColors(False)
        table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        table.setShowGrid(True)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked)

        return table


    def init(self): return True


