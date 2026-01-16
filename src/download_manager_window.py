import webbrowser

import mobase

from .download_manager_table_model import DownloadManagerTableModel
from .hash_worker import HashResult, HashWorker
from .mo2_compat_utils import CHECKED_STATE
from .ui_statics import HashProgressDialog, LoadingOverlay, create_basic_table_widget

import json

from pathlib import Path

try:
    import PyQt6.QtWidgets as QtWidgets
    from PyQt6.QtGui import QAction, QScreen, QIcon
    from PyQt6.QtCore import Qt, QEvent, QSortFilterProxyModel, QThread, pyqtSignal
    from PyQt6.QtWidgets import QApplication, QSizePolicy, QMenu, QStyle
except ImportError:
    import PyQt5.QtWidgets as QtWidgets
    from PyQt5.QtCore import Qt, QEvent, QSortFilterProxyModel, QThread, pyqtSignal
    from PyQt5.QtGui import QScreen, QIcon
    from PyQt5.QtWidgets import QApplication, QSizePolicy, QMenu, QAction, QStyle

# Icon paths
ICON_DIR = Path(__file__).parent / "icon"


def show_error(message, header, icon=QtWidgets.QMessageBox.Icon.Warning):
    exception_box = QtWidgets.QMessageBox()
    exception_box.setWindowTitle("Download Manager")
    exception_box.setText(header)
    exception_box.setIcon(icon)
    exception_box.setInformativeText(message)
    exception_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    exception_box.exec()


class RefreshWorker(QThread):
    """Background worker thread for refreshing download data."""
    finished = pyqtSignal()

    def __init__(self, table_model):
        super().__init__()
        self._table_model = table_model

    def run(self):
        self._table_model.refresh()
        self.finished.emit()


class DownloadFilterProxyModel(QSortFilterProxyModel):

    FILTER_COLUMNS = (2, 3)  # Mod Name, Filename (shifted by 1 due to selection column)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self.setDynamicSortFilter(True)

    def set_search_text(self, text: str):
        normalized = text.strip().lower()
        if normalized == self._search_text:
            return
        self._search_text = normalized
        self.invalidateFilter()

    def lessThan(self, left, right):
        # Column 0 is the selection checkbox - sort by check state
        if left.column() == 0:
            source = self.sourceModel()
            # Direct set lookup is O(1) and avoids expensive data() calls
            left_item = source._data[left.row()]
            right_item = source._data[right.row()]
            return (left_item in source._selected) < (right_item in source._selected)
        return super().lessThan(left, right)

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._search_text:
            return True

        source_model = self.sourceModel()
        if source_model is None:
            return True

        for column in self.FILTER_COLUMNS:
            index = source_model.index(source_row, column, source_parent)
            value = source_model.data(index, Qt.ItemDataRole.DisplayRole)
            if value is None:
                continue
            if self._search_text in str(value).lower():
                return True
        return False


class DownloadManagerWindow(QtWidgets.QDialog):

    # v2 suffix added to invalidate old settings after selection column was added
    COLUMN_VISIBILITY_SETTING = "columnVisibilityV2"
    COLUMN_ORDER_SETTING = "columnOrderV2"
    ALTERNATE_ROWS_SETTING = "alternateRowColors"

    BUTTON_TEXT = {
        "INSTALL": lambda count: f"Install Selected ({count})",
        "REQUERY": lambda count: f"Re-query Selected ({count})",
        "DELETE": lambda count: f"Delete Selected ({count})",
        "HIDE": lambda count: f"Mark Hidden ({count})",
    }

    __initialized: bool = False
    __organizer: mobase.IOrganizer = None
    hash_worker = None
    hash_dialog = None
    _has_resized = False
    _is_refreshing = False
    _refresh_worker = None
    _has_loaded_data = False

    def __init__(self, organizer: mobase.IOrganizer, parent=None):
        try:
            super().__init__(parent)

            self.__organizer = organizer

            self._table_model = DownloadManagerTableModel(organizer)
            self._proxy_model = DownloadFilterProxyModel(self)
            self._proxy_model.setSourceModel(self._table_model)

            self._column_visibility = []
            self._column_order = []
            self._alternate_row_colors = self._load_alternate_row_setting()

            self._table_widget = self.create_table_widget()

            self._main_layout = QtWidgets.QVBoxLayout()
            self._controls_widget = self._create_controls_bar()
            self._main_layout.addWidget(self._controls_widget)
            self._secondary_controls = self._create_secondary_controls()
            self._main_layout.addWidget(self._secondary_controls)
            self._main_layout.addWidget(self._table_widget)

            self.setLayout(self._main_layout)

            # Loading overlay - must be created after layout is set
            self._loading_overlay = LoadingOverlay(self, "Loading Downloads...")
            self._loading_overlay.hide()

            screen = QScreen.availableGeometry(QApplication.primaryScreen())
            max_width = int(screen.width() * 0.8)
            max_height = int(screen.height() * 0.8)

            min_width = min(1024, max_width)
            min_height = min(768, max_height)

            self.setMinimumSize(min_width, min_height)
            self._center_window()

            self._table_model.dataChanged.connect(self.update_button_states)

            self.setWindowModality(Qt.WindowModality.NonModal)

        except Exception as ex:
            show_error(
                repr(ex),
                "Critical error! Please report this on Nexus / GitHub.",
                QtWidgets.QMessageBox.Icon.Critical,
            )

    def _standard_icon(self, pixmap: QStyle.StandardPixmap):
        return QApplication.style().standardIcon(pixmap)

    def _custom_icon(self, name: str) -> QIcon:
        icon_path = ICON_DIR / name
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

    @staticmethod
    def _dropdown_button_style() -> str:
        return """
            QToolButton {
                padding: 4px 8px;
            }
            QToolButton::menu-indicator {
                subcontrol-position: right center;
            }
        """

    def _create_controls_bar(self):
        controls = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(8)

        self._refresh_button = self.create_refresh_button()
        layout.addWidget(self._refresh_button)

        self._search_input = self._create_search_input()
        layout.addWidget(self._search_input, 1)

        self._select_menu_button = self._create_select_button()
        layout.addWidget(self._select_menu_button)

        self._actions_menu_button = self._create_actions_button()
        layout.addWidget(self._actions_menu_button)

        self._selection_count_label = QtWidgets.QLabel("0 mods selected", self)
        layout.addWidget(self._selection_count_label)

        layout.addStretch(1)

        controls.setLayout(layout)
        return controls

    def _create_secondary_controls(self):
        controls = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 0, 4, 8)
        layout.setSpacing(8)

        layout.addWidget(self.create_hide_installed_checkbox())
        layout.addStretch(1)

        controls.setLayout(layout)
        return controls

    def _create_search_input(self):
        search = QtWidgets.QLineEdit(self)
        search.setPlaceholderText("Search filename or mod name...")
        search.textChanged.connect(self._on_search_text_changed)  # type: ignore
        search.addAction(
            self._custom_icon("icon_search.png"),
            QtWidgets.QLineEdit.ActionPosition.LeadingPosition
        )
        search.setMinimumHeight(28)
        return search

    def _create_select_button(self):
        button = QtWidgets.QToolButton(self)
        button.setText("Select")
        button.setIcon(self._custom_icon("icon_select.png"))
        button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setMinimumHeight(28)
        button.setStyleSheet(self._dropdown_button_style())

        menu = QMenu(button)

        action_duplicates = QAction("Select Old Duplicates", self)
        action_duplicates.triggered.connect(self._table_model.select_duplicates)  # type: ignore
        menu.addAction(action_duplicates)

        action_not_installed = QAction("Select Not Installed", self)
        action_not_installed.setToolTip(
            "Selects downloads that haven't been installed, "
            "excluding old versions of already-installed mods"
        )
        action_not_installed.triggered.connect(self._table_model.select_not_installed)  # type: ignore
        menu.addAction(action_not_installed)

        action_all = QAction("Select All", self)
        action_all.triggered.connect(self._table_model.select_all)  # type: ignore
        menu.addAction(action_all)

        action_none = QAction("Select None", self)
        action_none.triggered.connect(self._table_model.select_none)  # type: ignore
        menu.addAction(action_none)

        button.setMenu(menu)
        return button

    def _create_actions_button(self):
        button = QtWidgets.QToolButton(self)
        button.setText("Actions")
        button.setIcon(self._custom_icon("icon_action.png"))
        button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setMinimumHeight(28)
        button.setStyleSheet(self._dropdown_button_style())

        menu = QMenu(button)

        self._install_action = QAction(self.BUTTON_TEXT["INSTALL"](0), self)
        self._install_action.triggered.connect(self.install_selected)  # type: ignore
        menu.addAction(self._install_action)

        self._requery_action = QAction(self.BUTTON_TEXT["REQUERY"](0), self)
        self._requery_action.triggered.connect(self.requery_selected)  # type: ignore
        menu.addAction(self._requery_action)

        self._hide_action = QAction(self.BUTTON_TEXT["HIDE"](0), self)
        self._hide_action.triggered.connect(self.hide_selected)  # type: ignore
        menu.addAction(self._hide_action)

        self._delete_action = QAction(self.BUTTON_TEXT["DELETE"](0), self)
        self._delete_action.triggered.connect(self.delete_selected)  # type: ignore
        menu.addAction(self._delete_action)

        for action in (
            self._install_action,
            self._requery_action,
            self._hide_action,
            self._delete_action,
        ):
            action.setEnabled(False)

        button.setMenu(menu)
        return button

    # region UI - Table Operations
    def create_hide_installed_checkbox(self):
        hide_installed_checkbox = QtWidgets.QCheckBox("Hide Installed Files", self)
        hide_installed_checkbox.stateChanged.connect(self.hide_install_state_changed)  # type: ignore
        return hide_installed_checkbox

    def hide_install_state_changed(self, checked: Qt.CheckState):
        self._table_model.toggle_show_installed(
            checked == CHECKED_STATE
        )
        self._proxy_model.invalidateFilter()

    def create_refresh_button(self):
        button = QtWidgets.QPushButton("Refresh", self)
        button.setIcon(self._custom_icon("icon_refresh.png"))
        button.clicked.connect(self.refresh_data)  # type: ignore
        button.setMinimumHeight(28)
        return button

    # endregion

    def _on_search_text_changed(self, text: str):
        self._proxy_model.set_search_text(text)

    # region UI change handler
    def update_button_states(self):
        selected = self._table_model.get_selected()
        self._toggle_button_operations(len(selected))

    def _toggle_button_operations(self, selected_count):
        operations_enabled = selected_count > 0
        for action in (
            self._hide_action,
            self._delete_action,
            self._requery_action,
            self._install_action,
        ):
            action.setEnabled(operations_enabled)

        self._hide_action.setText(self.BUTTON_TEXT["HIDE"](selected_count))
        self._requery_action.setText(self.BUTTON_TEXT["REQUERY"](selected_count))
        self._delete_action.setText(self.BUTTON_TEXT["DELETE"](selected_count))
        self._install_action.setText(self.BUTTON_TEXT["INSTALL"](selected_count))

        self._selection_count_label.setText(f"{selected_count} mods selected")

    # endregion

    # region
    def install_selected(self):
        self._table_model.install_selected()
        self.refresh_data()

    def requery_selected(self):
        if not self._validate_nexus_api_key():
            return

        to_requery = self._table_model.get_selected().copy() # don't use selected directly, the model will change it
        for item in to_requery:
            self.hash_dialog = HashProgressDialog(self) # type: ignore
            self.hash_worker = HashWorker(item)
            self.hash_worker.progress_updated.connect(self.hash_dialog.update_progress)
            self.hash_worker.hash_computed.connect(self._on_hash_complete)

            self.hash_worker.start()
            self.hash_dialog.exec()

    def _on_hash_complete(self, result: HashResult):
        self.hash_dialog.accept()
        self._table_model.requery(result.mod, result.md5_hash)
        print(result)

    def delete_selected(self):
        self._table_model.delete_selected()
        self.refresh_data()

    def hide_selected(self):
        self._table_model.hide_selected()
        self.refresh_data()

    def refresh_data(self):
        if self._is_refreshing:
            return
        self._is_refreshing = True
        self._refresh_button.setEnabled(False)

        # Show loading overlay
        self._loading_overlay.set_message("Refreshing Downloads...")
        self._loading_overlay.set_sub_message("Scanning download folder...")
        self._loading_overlay.show_overlay()

        # Run refresh in background thread
        self._refresh_worker = RefreshWorker(self._table_model)
        self._refresh_worker.finished.connect(self._on_refresh_complete)  # type: ignore
        self._refresh_worker.start()

    def _on_refresh_complete(self):
        self._loading_overlay.hide_overlay()
        if not self._has_resized:
            self.resize_window()
            self._has_resized = True
        self.reapply_sort()
        self._refresh_button.setEnabled(True)
        self._is_refreshing = False
        self._has_loaded_data = True

    # endregion

    def reapply_sort(self):
        header = self._table_widget.horizontalHeader()
        current_sort_col = header.sortIndicatorSection()
        current_sort_order = header.sortIndicatorOrder()
        self._proxy_model.sort(current_sort_col, current_sort_order)

    def create_table_widget(self):
        table = create_basic_table_widget(self._alternate_row_colors)
        table.setModel(self._proxy_model)
        table.setSortingEnabled(True)
        table.sortByColumn(1, Qt.SortOrder.AscendingOrder)  # Sort by Name column (column 0 is selection)
        self._enable_column_customization(table)
        table.installEventFilter(self)
        return table

    def _enable_column_customization(self, table: QtWidgets.QTableView):
        header = table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        column_count = self._table_model.columnCount()
        self._column_visibility = self._load_column_visibility(column_count)
        self._column_order = self._load_column_order(column_count)
        self._apply_column_order(header)
        # Start from column 1 to skip the checkbox column (column 0) - it should always be visible
        for column in range(1, column_count):
            column_name = self._table_model.headerData(
                column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            action = QAction(str(column_name), header)
            action.setCheckable(True)
            initial_state = self._column_visibility[column]
            action.setChecked(initial_state)
            action.toggled.connect(
                lambda checked, col=column: self._handle_column_toggle(
                    table, col, checked
                )
            )
            header.addAction(action)
            table.setColumnHidden(column, not initial_state)
        header.sectionMoved.connect(self._handle_section_moved)

    def _handle_column_toggle(
        self, table: QtWidgets.QTableView, column: int, checked: bool
    ):
        table.setColumnHidden(column, not checked)
        if column < len(self._column_visibility):
            self._column_visibility[column] = checked
        self._save_column_visibility()

    def _handle_section_moved(self, *_):
        header = self._table_widget.horizontalHeader()
        self._column_order = [
            header.logicalIndex(visual_index) for visual_index in range(header.count())
        ]
        self._save_column_order()

    def _apply_column_order(self, header: QtWidgets.QHeaderView):
        for target_index, logical_index in enumerate(self._column_order):
            current_visual_index = header.visualIndex(logical_index)
            if current_visual_index == -1:
                continue
            if current_visual_index != target_index:
                header.moveSection(current_visual_index, target_index)

    def _load_column_visibility(self, column_count: int):
        default_visibility = [True] * column_count
        if not self.__organizer:
            return default_visibility

        try:
            stored_value = self.__organizer.pluginSetting(
                "Download Manager", self.COLUMN_VISIBILITY_SETTING
            )
        except Exception:
            return default_visibility

        if not stored_value:
            return default_visibility

        parsed_value = None
        if isinstance(stored_value, list):
            parsed_value = stored_value
        elif isinstance(stored_value, str):
            try:
                parsed_value = json.loads(stored_value)
            except json.JSONDecodeError:
                return default_visibility

        if not isinstance(parsed_value, list):
            return default_visibility

        visibility = default_visibility.copy()
        for idx in range(min(len(parsed_value), column_count)):
            visibility[idx] = bool(parsed_value[idx])

        return visibility

    def _load_column_order(self, column_count: int):
        default_order = list(range(column_count))
        if not self.__organizer:
            return default_order

        try:
            stored_value = self.__organizer.pluginSetting(
                "Download Manager", self.COLUMN_ORDER_SETTING
            )
        except Exception:
            return default_order

        if not stored_value:
            return default_order

        parsed_value = None
        if isinstance(stored_value, list):
            parsed_value = stored_value
        elif isinstance(stored_value, str):
            try:
                parsed_value = json.loads(stored_value)
            except json.JSONDecodeError:
                return default_order

        if not isinstance(parsed_value, list):
            return default_order

        filtered_order = []
        for value in parsed_value:
            if (
                isinstance(value, int)
                and 0 <= value < column_count
                and value not in filtered_order
            ):
                filtered_order.append(value)

        for logical_index in range(column_count):
            if logical_index not in filtered_order:
                filtered_order.append(logical_index)

        return filtered_order

    def _save_column_visibility(self):
        if not self.__organizer:
            return
        try:
            self.__organizer.setPluginSetting(
                "Download Manager",
                self.COLUMN_VISIBILITY_SETTING,
                json.dumps(self._column_visibility),
            )
        except Exception:
            pass

    def _save_column_order(self):
        if not self.__organizer:
            return
        try:
            self.__organizer.setPluginSetting(
                "Download Manager",
                self.COLUMN_ORDER_SETTING,
                json.dumps(self._column_order),
            )
        except Exception:
            pass

    def _load_alternate_row_setting(self):
        if not self.__organizer:
            return True
        try:
            stored_value = self.__organizer.pluginSetting(
                "Download Manager", self.ALTERNATE_ROWS_SETTING
            )
        except Exception:
            return True
        if stored_value in (None, ""):
            return True
        return self._coerce_bool(stored_value, True)

    @staticmethod
    def _coerce_bool(value, default):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    def resize_window(self):
        max_column_width = 500
        padding = 50

        # Resize columns to contents
        resize_mode = QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        header = self._table_widget.horizontalHeader()
        header.setSectionResizeMode(resize_mode)

        # Adjust each column so they don't go over max width
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
            # After the initial sizing pass, leave the column in interactive mode
            header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeMode.Interactive
            )

        controls_size = self._controls_widget.sizeHint()
        table_size = self._table_widget.sizeHint()
        screen = QApplication.primaryScreen().availableGeometry()
        max_width = int(screen.width() * 0.8)
        max_height = int(screen.height() * 0.8)

        content_width = max(controls_size.width(), table_size.width())
        new_width = min(content_width + (padding * 2), max_width)

        content_height = controls_size.height() + table_size.height() + padding
        new_height = min(content_height, max_height)

        self.resize(new_width, new_height)
        self._center_window()

    def _center_window(self):
        screen = QApplication.primaryScreen().availableGeometry()
        this_window = self.frameGeometry()
        this_window.moveCenter(screen.center())
        self.move(this_window.topLeft())

    def eventFilter(self, watched, event):
        if (
            watched == self._table_widget
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Space
        ):
            if self._toggle_selected_rows():
                return True
        return super().eventFilter(watched, event)

    def _toggle_selected_rows(self):
        row_list = self._selected_source_rows()
        if not row_list:
            return False
        all_selected = self._table_model.are_rows_selected(row_list)
        self._table_model.set_rows_selected(row_list, not all_selected)
        self.update_button_states()
        return True

    def _selected_source_rows(self):
        if not self._table_widget:
            return []
        selection_model = self._table_widget.selectionModel()
        if not selection_model:
            return []
        indexes = selection_model.selectedRows()
        if not indexes:
            indexes = selection_model.selectedIndexes()
        rows = set()
        for index in indexes:
            source_index = self._proxy_model.mapToSource(index)
            if source_index.isValid():
                rows.add(source_index.row())
        return sorted(rows)

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        toggle_action = QAction("Toggle Selected", self)
        toggle_action.triggered.connect(self._toggle_from_context) # type: ignore
        context_menu.addAction(toggle_action)

        view_nexus_action = QAction("View on Nexus", self)
        view_nexus_action.triggered.connect(self._view_on_nexus) # type: ignore
        context_menu.addAction(view_nexus_action)

        context_menu.exec(event.globalPos())

    def _toggle_from_context(self):
        """Toggle selection state for all highlighted rows (invert each row's state)."""
        self.setUpdatesEnabled(False)
        selection_model = self._table_widget.selectionModel()
        if not selection_model or len(selection_model.selectedIndexes()) == 0:
            self.setUpdatesEnabled(True)
            return
        # Track which rows we've already toggled to avoid toggling multiple times
        # when multiple columns are selected in the same row
        toggled_rows = set()
        for index in selection_model.selectedIndexes():
            source_index = self._proxy_model.mapToSource(index)
            if source_index.isValid() and source_index.row() not in toggled_rows:
                self._table_model.toggle_at_index(source_index)
                toggled_rows.add(source_index.row())
        self.setUpdatesEnabled(True)

    def _view_on_nexus(self):
        """Open Nexus mod page in browser for each highlighted SkyrimSE mod from Nexus."""
        selection_model = self._table_widget.selectionModel()
        if not selection_model or len(selection_model.selectedIndexes()) == 0:
            return

        # Collect all valid entries first
        urls_to_open = []
        seen_rows = set()
        for index in selection_model.selectedIndexes():
            source_index = self._proxy_model.mapToSource(index)
            if not source_index.isValid() or source_index.row() in seen_rows:
                continue
            seen_rows.add(source_index.row())

            entry = self._table_model._data[source_index.row()]

            # Only open if repository is Nexus and game is SkyrimSE
            if entry.repository != "Nexus":
                continue
            if entry.game_name != "SkyrimSE":
                continue
            if not entry.nexus_mod_id:
                continue

            url = f"https://www.nexusmods.com/skyrimspecialedition/mods/{entry.nexus_mod_id}"
            urls_to_open.append(url)

        if not urls_to_open:
            return

        # Confirm if opening more than 5 tabs
        if len(urls_to_open) > 5:
            confirm = QtWidgets.QMessageBox(self)
            confirm.setWindowTitle("Open browser tabs?")
            confirm.setText(f"Open {len(urls_to_open)} browser tabs?")
            confirm.setInformativeText(
                f"Viewing everything you selected would open {len(urls_to_open)} browser tabs. "
                "Just checking, you want to do that, right?"
            )
            open_btn = confirm.addButton("Open the tabs", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            confirm.addButton("Nevermind", QtWidgets.QMessageBox.ButtonRole.RejectRole)
            confirm.exec()

            if confirm.clickedButton() != open_btn:
                return

        for url in urls_to_open:
            webbrowser.open(url)

    def _validate_nexus_api_key(self):
        api_key: str = self.__organizer.pluginSetting("Download Manager", "nexusApiKey")
        if api_key:
            return True
        show_error(
            "Please add your API key in plugin settings and try again. "
            "See the README/Nexus page for information.",
            "Nexus API key not found")
        return False

    def showEvent(self, event):
        """Called when window is shown. Auto-refresh if no data loaded yet."""
        super().showEvent(event)
        # Auto-refresh on first show if we haven't loaded data yet
        if not self._has_loaded_data and not self._is_refreshing:
            self._loading_overlay.set_message("Loading Downloads...")
            self._loading_overlay.set_sub_message("First launch - scanning download folder...")
            self.refresh_data()

    def resizeEvent(self, event):
        """Ensure loading overlay covers the window when resized."""
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    #################
    # Required by MO2
    #################
    @staticmethod
    def init():
        """MO2 requires this fn be present for QDialog."""
        return True
