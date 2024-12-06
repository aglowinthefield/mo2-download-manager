from .util import logger
from .download_manager_table_model import DownloadManagerTableModel

try:
    import PyQt6.QtCore as QtCore
    import PyQt6.QtGui as QtGui
    import PyQt6.QtWidgets as QtWidgets
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QSizePolicy
except ImportError:
    import PyQt5.QtCore as QtCore
    import PyQt5.QtGui as QtGui
    import PyQt5.QtWidgets as QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QSizePolicy

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

            main_layout = QtWidgets.QHBoxLayout()

            self._wrapper_left = QtWidgets.QWidget()

            # This area has the select/refresh/table operations fields
            layout_left = QtWidgets.QVBoxLayout()
            layout_left.addWidget(self.create_refresh_button())
            layout_left.addWidget(self.create_select_duplicates_button())
            layout_left.addWidget(self.create_select_all_button())
            layout_left.addWidget(self.create_select_none_button())

            spacer = QtWidgets.QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
            layout_left.addItem(spacer)

            layout_left.addWidget(self.create_install_button())
            layout_left.addWidget(self.create_delete_button())

            # This area should have the operations for the selected elements
            self._wrapper_left.setLayout(layout_left)

            self._wrapper_right = QtWidgets.QWidget()
            layout_right = QtWidgets.QVBoxLayout()
            layout_right.addWidget(self._table_widget)
            self._wrapper_right.setLayout(layout_right)

            main_layout.addWidget(self._wrapper_left)
            main_layout.addWidget(self._wrapper_right)

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

    # region UI - Download Operations
    def create_delete_button(self):
        delete_button = QtWidgets.QPushButton("Delete Selected", self)
        delete_button.clicked.connect(self.delete_selected)  # type: ignore
        return delete_button

    def create_install_button(self):
        delete_button = QtWidgets.QPushButton("Install Selected", self)
        delete_button.clicked.connect(self.install_selected)  # type: ignore
        return delete_button

    # endregion

    # region UI - Table Operations
    def create_refresh_button(self):
        refresh_button = QtWidgets.QPushButton("Refresh", self)
        refresh_button.clicked.connect(self.refresh_data)  # type: ignore
        return refresh_button

    def create_select_duplicates_button(self):
        select_duplicates_button = QtWidgets.QPushButton("Select Old Duplicates", self)
        select_duplicates_button.clicked.connect(self.select_duplicates)  # type: ignore
        return select_duplicates_button

    def create_select_all_button(self):
        select_all_button = QtWidgets.QPushButton("Select All", self)
        select_all_button.clicked.connect(self.select_all)  # type: ignore
        return select_all_button

    def create_select_none_button(self):
        select_none_button = QtWidgets.QPushButton("Select None", self)
        select_none_button.clicked.connect(self.select_none)  # type: ignore
        return select_none_button

    # endregion

    def select_all(self):
        return self._table_model.select_all()

    def select_none(self):
        return self._table_model.select_none()

    def select_duplicates(self):
        return True

    def install_selected(self):
        self._table_model.install_selected()
        self.refresh_data()

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

    def init(self):
        return True
