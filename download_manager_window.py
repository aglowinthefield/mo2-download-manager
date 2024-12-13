import mobase

from .mo2_compat_utils import get_qt_checked_value
from .download_manager_table_model import DownloadManagerTableModel
from .ui_statics import create_basic_table_widget, button_with_handler

try:
    import PyQt6.QtWidgets as QtWidgets
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QSizePolicy
except ImportError:
    import PyQt5.QtWidgets as QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QSizePolicy


def show_error(message, header, icon=QtWidgets.QMessageBox.Icon.Warning):
    exception_box = QtWidgets.QMessageBox()
    exception_box.setWindowTitle("Download Manager")
    exception_box.setText(header)
    exception_box.setIcon(icon)
    exception_box.setInformativeText(message)
    exception_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    exception_box.exec()


class DownloadManagerWindow(QtWidgets.QDialog):

    __omit_uninstalled: bool = False
    __initialized: bool = False

    def __init__(self, organizer: mobase.IOrganizer, parent=None):
        self.__omit_uninstalled = False
        try:
            super().__init__(parent)

            self._table_model = DownloadManagerTableModel(organizer)
            self._table_widget = self.create_table_widget()

            main_layout = QtWidgets.QHBoxLayout()

            self._wrapper_left = QtWidgets.QWidget()

            # This area has the select/refresh/table operations fields
            layout_left = QtWidgets.QVBoxLayout()
            layout_left.addWidget(self.create_refresh_button())
            layout_left.addWidget(self.create_select_duplicates_button())
            layout_left.addWidget(self.create_select_all_button())
            layout_left.addWidget(self.create_select_none_button())
            layout_left.addWidget(self.create_hide_installed_checkbox())

            spacer = QtWidgets.QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
            layout_left.addItem(spacer)

            layout_left.addWidget(self.create_install_button())
            layout_left.addWidget(self.create_hide_button())
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
        return button_with_handler("Delete Selected", self, self.delete_selected)

    def create_install_button(self):
        return button_with_handler("Install Selected", self, self.install_selected)

    def create_hide_button(self):
        return button_with_handler("Mark Hidden", self, self.hide_selected)
    # endregion

    # region UI - Table Operations
    def create_hide_installed_checkbox(self):
        hide_installed_checkbox = QtWidgets.QCheckBox("Hide Installed Files", self)
        hide_installed_checkbox.stateChanged.connect(self.hide_install_state_changed)  # type: ignore
        return hide_installed_checkbox

    def hide_install_state_changed(self, checked: Qt.CheckState):
        self.__omit_uninstalled = checked == get_qt_checked_value(Qt.CheckState.Checked)
        self.refresh_data()

    def create_refresh_button(self):
        return button_with_handler("Refresh", self, self.refresh_data)

    def create_select_duplicates_button(self):
        return button_with_handler("Select Old Duplicates", self, self.select_duplicates)

    def create_select_all_button(self):
        return button_with_handler("Select All", self, self.select_all)

    def create_select_none_button(self):
        return button_with_handler("Select None", self, self.select_none)
    # endregion

    def select_all(self):
        return self._table_model.select_all()

    def select_none(self):
        return self._table_model.select_none()

    def select_duplicates(self):
        return self._table_model.select_duplicates()

    def install_selected(self):
        self._table_model.install_selected()
        self.refresh_data()

    def delete_selected(self):
        self._table_model.delete_selected()
        self.refresh_data()

    def hide_selected(self):
        self._table_model.hide_selected()
        self.refresh_data()

    def refresh_data(self):
        self._table_model.refresh(self.__omit_uninstalled)
        self.resize_window()
        self.reapply_sort()

    def reapply_sort(self):
        if not self.__initialized:
            return
        header = self._table_widget.horizontalHeader()
        current_sort_col = header.sortIndicatorSection()
        current_sort_order = header.sortIndicatorOrder()
        self._table_model.sort(current_sort_col, current_sort_order)

    def create_table_widget(self):
        table = create_basic_table_widget()
        table.setModel(self._table_model)
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
        self.resize(
            table_size.width() + button_size.width() + (padding * 2), new_height
        )

    @staticmethod
    def init():
        """MO2 requires this fn be present for QDialog."""
        return True
