from .util import logger
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
            main_layout = QtWidgets.QHBoxLayout()

            self._wrapper_left = QtWidgets.QWidget()
            layout_left = QtWidgets.QVBoxLayout()
            layout_left.addWidget(self.create_refresh_button())
            layout_left.addWidget(self.create_select_duplicates_button())
            self._wrapper_left.setLayout(layout_left)

            self._wrapper_right = QtWidgets.QWidget()
            layout_right = QtWidgets.QVBoxLayout()
            layout_right.addWidget(self._table_widget)
            self._wrapper_right.setLayout(layout_right)

            # wrapper_delete = QtWidgets.QWidget()
            # layout_delete = QtWidgets.QHBoxLayout()
            # layout_delete.addWidget(self.create_delete_button())
            # wrapper_delete.setLayout(layout_delete)

            main_layout.addWidget(self._wrapper_left)
            main_layout.addWidget(self._wrapper_right)
            # main_layout.addWidget(wrapper_delete)

            # Dimensions / ratios
            main_layout.setStretch(0, 1)  # Buttons
            main_layout.setStretch(1, 6)  # Table

            self.setLayout(main_layout)
            self.setMinimumSize(1024, 768)

        except Exception as ex:
            show_error(
                repr(ex),
                "Critical error! Please report this on Nexus / GitHub.",
                QtWidgets.QMessageBox.Icon.Critical,
            )

    def create_delete_button(self):
        delete_button = QtWidgets.QPushButton("Delete Selected", self)
        delete_button.clicked.connect(self.delete_selected)  # type: ignore
        return delete_button

    def create_refresh_button(self):
        refresh_button = QtWidgets.QPushButton("Refresh", self)
        refresh_button.clicked.connect(self.refresh_data)  # type: ignore
        return refresh_button

    def create_select_duplicates_button(self):
        select_duplicates_button = QtWidgets.QPushButton("Select Duplicates", self)
        select_duplicates_button.clicked.connect(self.select_duplicates)  # type: ignore
        return select_duplicates_button

    def select_duplicates(self):
        return True

    def delete_selected(self):
        self._table_model.delete_selected()
        self.refresh_data()

    def refresh_data(self):
        self.__model.refresh()
        self._table_model.init_data(self.__model.data, self.__model)
        self.resize_window()

    def create_table_widget(self):
        table = QtWidgets.QTableView()
        table.setModel(self._table_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSortingEnabled(True)
        table.setSizeAdjustPolicy(
            QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        table.setShowGrid(False)
        table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked)
        table.setMouseTracking(True)
        return table

    def resize_window(self):
        max_column_width = 500
        padding = 50

        # Resize columns to contents
        resize_mode = QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        self._table_widget.horizontalHeader().setSectionResizeMode(resize_mode)

        # Adjust each column so they don't go over max width
        header = self._table_widget.horizontalHeader()
        for column in range(self._table_widget.model().columnCount()):
            header.setSectionResizeMode(column, resize_mode)
            actual_width = header.sectionSize(column)
            if actual_width > max_column_width:
                header.setSectionResizeMode(
                    column, QtWidgets.QHeaderView.ResizeMode.Interactive
                )
                header.resizeSection(column, max_column_width)

        # Make sure window doesn't get tall af
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_height = screen_geometry.height()

        # Maximum height: 80% of screen height
        max_height = int(screen_height * 0.5)

        table_size = self._table_widget.sizeHint()
        button_size = self._wrapper_left.sizeHint()
        new_height = min(table_size.height() + padding, max_height)

        # Resize window to fit the table with the new height constraint
        self.resize(table_size.width() + button_size.width() + padding, new_height)
        self._wrapper_left.adjustSize()

    def init(self):
        return True
