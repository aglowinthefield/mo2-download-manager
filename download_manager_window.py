﻿import mobase

from .download_manager_table_model import DownloadManagerTableModel
from .mo2_compat_utils import get_qt_checked_value
from .ui_statics import create_basic_table_widget, button_with_handler

try:
    import PyQt6.QtWidgets as QtWidgets
    from PyQt6.QtGui import QAction
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QSizePolicy, QMenu
except ImportError:
    import PyQt5.QtWidgets as QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QSizePolicy, QMenu, QAction


def show_error(message, header, icon=QtWidgets.QMessageBox.Icon.Warning):
    exception_box = QtWidgets.QMessageBox()
    exception_box.setWindowTitle("Download Manager")
    exception_box.setText(header)
    exception_box.setIcon(icon)
    exception_box.setInformativeText(message)
    exception_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    exception_box.exec()


class DownloadManagerWindow(QtWidgets.QDialog):

    BUTTON_TEXT = {
        "INSTALL": lambda count: f"Install Selected ({count})",
        "REQUERY": lambda count: f"Re-query Selected ({count})",
        "DELETE": lambda count: f"Delete Selected ({count})",
        "HIDE": lambda count: f"Mark Hidden ({count})",
    }

    __initialized: bool = False

    def __init__(self, organizer: mobase.IOrganizer, parent=None):
        try:
            super().__init__(parent)

            self._table_model = DownloadManagerTableModel(organizer)
            self._table_widget = self.create_table_widget()

            self._main_layout = QtWidgets.QHBoxLayout()

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

            self._install_button = self.create_install_button()
            self._requery_button = self.create_requery_button()
            self._hide_button = self.create_hide_button()
            self._delete_button = self.create_delete_button()

            layout_left.addWidget(self._install_button)
            layout_left.addWidget(self._requery_button)
            layout_left.addWidget(self._hide_button)
            layout_left.addWidget(self._delete_button)

            # This area should have the operations for the selected elements
            self._wrapper_left.setLayout(layout_left)

            self._wrapper_right = QtWidgets.QWidget()
            layout_right = QtWidgets.QVBoxLayout()
            layout_right.addWidget(self._table_widget)
            self._wrapper_right.setLayout(layout_right)

            self._main_layout.addWidget(self._wrapper_left)
            self._main_layout.addWidget(self._wrapper_right)

            # Dimensions / ratios
            self._main_layout.setStretch(0, 1)  # Buttons
            self._main_layout.setStretch(1, 6)  # Table

            self.setLayout(self._main_layout)
            self.setMinimumSize(1024, 768)

            self._table_model.dataChanged.connect(self.update_button_states)

        except Exception as ex:
            show_error(
                repr(ex),
                "Critical error! Please report this on Nexus / GitHub.",
                QtWidgets.QMessageBox.Icon.Critical,
            )

    # region UI - Download Operations
    def create_delete_button(self):
        return button_with_handler(
            self.BUTTON_TEXT["DELETE"](0), self, self.delete_selected
        )

    def create_install_button(self):
        return button_with_handler(
            self.BUTTON_TEXT["INSTALL"](0), self, self.install_selected
        )

    def create_requery_button(self):
        return button_with_handler(
            self.BUTTON_TEXT["REQUERY"](0), self, self.requery_selected
        )

    def create_hide_button(self):
        return button_with_handler(
            self.BUTTON_TEXT["HIDE"](0), self, self.hide_selected
        )

    # endregion

    # region UI - Table Operations
    def create_hide_installed_checkbox(self):
        hide_installed_checkbox = QtWidgets.QCheckBox("Hide Installed Files", self)
        hide_installed_checkbox.stateChanged.connect(self.hide_install_state_changed)  # type: ignore
        return hide_installed_checkbox

    def hide_install_state_changed(self, checked: Qt.CheckState):
        self._table_model.toggle_show_installed(
            checked == get_qt_checked_value(Qt.CheckState.Checked)
        )

    def create_refresh_button(self):
        return button_with_handler("Refresh", self, self.refresh_data)

    def create_select_duplicates_button(self):
        return button_with_handler(
            "Select Old Duplicates", self, self._table_model.select_duplicates
        )

    def create_select_all_button(self):
        return button_with_handler("Select All", self, self._table_model.select_all)

    def create_select_none_button(self):
        return button_with_handler("Select None", self, self._table_model.select_none)

    # endregion

    # region UI change handler
    def update_button_states(self):
        selected = self._table_model.get_selected()
        self._toggle_button_operations(len(selected))

    def _toggle_button_operations(self, selected_count):
        self._hide_button.setEnabled(selected_count > 0)
        self._delete_button.setEnabled(selected_count > 0)
        self._requery_button.setEnabled(selected_count > 0)
        self._install_button.setEnabled(selected_count > 0)

        self._hide_button.setText(self.BUTTON_TEXT["HIDE"](selected_count))
        self._requery_button.setText(self.BUTTON_TEXT["REQUERY"](selected_count))
        self._delete_button.setText(self.BUTTON_TEXT["DELETE"](selected_count))
        self._install_button.setText(self.BUTTON_TEXT["INSTALL"](selected_count))

    # endregion

    # region
    def install_selected(self):
        self._table_model.install_selected()
        self.refresh_data()

    def requery_selected(self):
        self._table_model.requery_selected()
        self.refresh_data()

    def delete_selected(self):
        self._table_model.delete_selected()
        self.refresh_data()

    def hide_selected(self):
        self._table_model.hide_selected()
        self.refresh_data()

    def refresh_data(self):
        self.setUpdatesEnabled(False)
        self._table_model.refresh()
        self.resize_window()
        self.reapply_sort()
        self.setUpdatesEnabled(True)

    # endregion

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

            header_width = header.sectionSize(column)
            content_width = self._table_widget.columnWidth(column)

            actual_width = max(header_width, content_width)

            if actual_width > max_column_width:
                header.setSectionResizeMode(
                    column, QtWidgets.QHeaderView.ResizeMode.Interactive
                )
                header.resizeSection(column, max_column_width)

        # Make sure window doesn't get tall af
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_height = screen_geometry.height()

        max_height = int(screen_height * 0.5)

        table_size = self._wrapper_right.sizeHint()
        button_size = self._wrapper_left.sizeHint()
        new_height = min(table_size.height() + padding, max_height)

        # Resize window to fit the table with the new height constraint
        new_width = table_size.width() + button_size.width() + (padding * 3)
        self.resize(new_width, new_height)

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        select_action = QAction("Select", self)
        select_action.triggered.connect(self._select_from_context) # type: ignore
        context_menu.addAction(select_action)
        context_menu.exec(event.globalPos())

    def _select_from_context(self):
        self.setUpdatesEnabled(False)
        selection_model = self._table_widget.selectionModel()
        if not selection_model or len(selection_model.selectedIndexes()) == 0:
            return
        for index in selection_model.selectedIndexes():
            self._table_model.select_at_index(index)
        self.setUpdatesEnabled(True)

    @staticmethod
    def init():
        """MO2 requires this fn be present for QDialog."""
        return True
