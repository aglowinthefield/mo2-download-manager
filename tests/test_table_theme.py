"""Rendered contrast regressions for GitHub #20, without an installed MO2 theme."""
import tempfile
import unittest
from pathlib import Path

from support import APP, Organizer, Qt, archive
from src.download_manager_table_model import Column, DownloadManagerTableModel
from src.ui_statics import QtWidgets, create_basic_table_widget

try:
    from PyQt6.QtGui import QBrush, QColor, QFont, QGradient, QLinearGradient, QPalette
except ImportError:
    from PyQt5.QtGui import QBrush, QColor, QFont, QGradient, QLinearGradient, QPalette


# Minimal reproduction of dark.qss: tree/list colours omit QTableView.
INCOMPLETE_DARK_THEME = """
QWidget { color: #e9e6e4; background-color: #2f3031; }
QAbstractItemView {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #484f53, stop:0.7 #656666, stop:1 #484f53);
}
QTreeView, QListView {
    background-color: #3f4041; alternate-background-color: #2f3031;
}
"""


def luminance(color):
    channels = [value / 255 for value in (color.red(), color.green(), color.blue())]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


class TableThemeTests(unittest.TestCase):
    def setUp(self):
        self.parent = None
        self.previous_style = APP.style().objectName()
        self.previous_palette = QPalette(APP.palette())
        self.previous_font = QFont(APP.font())
        self.previous_stylesheet = APP.styleSheet()
        self.addCleanup(self.restore_application)
        APP.setStyleSheet("")
        APP.setStyle("Fusion")
        palette = APP.style().standardPalette()
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f7f7f7"))
        APP.setPalette(palette)
        APP.setFont(QFont("Arial", 12))
        APP.setStyleSheet(INCOMPLETE_DARK_THEME)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = Path(self.temp.name)
        for index in range(4):
            archive(directory, f"{index}.7z", "[General]\nname=MMMMMMMM\n")
        self.model = DownloadManagerTableModel(Organizer(directory))
        self.addCleanup(self.model._model._executor.shutdown, wait=True)
        self.model.refresh()
        self.table = create_basic_table_widget()
        self.addCleanup(self.table.close)
        self.table.setModel(self.model)
        for column in range(self.model.columnCount()):
            self.table.setColumnHidden(column, column != Column.NAME)
        self.table.setColumnWidth(Column.NAME, 300)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.resize(360, 210)
        self.table.show()
        self.table.clearSelection()
        APP.processEvents()

    def restore_application(self):
        APP.setStyleSheet("")
        APP.setStyle(self.previous_style)
        APP.setPalette(self.previous_palette)
        APP.setFont(self.previous_font)
        APP.setStyleSheet(self.previous_stylesheet)
        APP.processEvents()

    def row_colors(self, row, selected=False):
        APP.processEvents()
        image = self.table.viewport().grab().toImage()
        ratio = image.devicePixelRatio()
        rect = self.table.visualRect(self.model.index(row, Column.NAME))
        role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        text = self.table.palette().color(role)
        background = image.pixelColor(int((rect.right() - 10) * ratio), int(rect.center().y() * ratio))
        self.assertTrue(any(
            image.pixelColor(int(x * ratio), int(y * ratio)) == text
            for x in range(rect.left() + 3, rect.left() + 125)
            for y in range(rect.top() + 2, rect.bottom() - 2)
        ), "No solid foreground pixels; rendering setup is invalid")
        return text, background

    def assert_readable(self, row):
        text, background = self.row_colors(row)
        low, high = sorted((luminance(text), luminance(background)))
        self.assertGreaterEqual((high + 0.05) / (low + 0.05), 4.5,
                                f"Row {row}: {text.name()} on {background.name()}")

    def test_incomplete_dark_theme_does_not_inherit_a_light_alternate_row(self):
        self.assertTrue(self.table.alternatingRowColors())
        self.assert_readable(2)
        self.assert_readable(3)

    def test_readable_theme_colors_survive_theme_changes_on_the_same_table(self):
        for foreground, base, alternate in (
                ("#dcdcdc", "#1e1e1e", "#262626"),
                ("#d3d3d3", "#141414", "#1c1c1c"),
                ("#202020", "#ffffff", "#eeeeee")):
            with self.subTest(alternate=alternate):
                APP.setStyleSheet("QTableView {"
                                  f"color:{foreground}; background-color:{base};"
                                  f"alternate-background-color:{alternate};" + "}")
                self.assertEqual(self.row_colors(2)[1].name(), base)
                self.assertEqual(self.row_colors(3)[1].name(), alternate)
                self.assert_readable(3)
        APP.setStyleSheet(INCOMPLETE_DARK_THEME)
        self.assert_readable(3)
        self.assertTrue(self.table.alternatingRowColors())

    def test_disabling_alternation_keeps_normal_background_and_user_setting(self):
        APP.setStyleSheet("QTableView {color:#e9e6e4; background-color:#3f4041;}")
        self.table.setAlternatingRowColors(False)
        self.assertFalse(self.table.alternatingRowColors())
        self.assertEqual(self.row_colors(2)[1].name(), "#3f4041")
        self.assertEqual(self.row_colors(3)[1].name(), "#3f4041")

    def test_parent_palette_changes_and_selection_do_not_get_frozen_by_fallback(self):
        APP.setStyleSheet("")
        original = QPalette(APP.palette())
        self.parent = QtWidgets.QWidget()
        self.addCleanup(self.parent.close)
        self.parent.resize(360, 210)
        self.table.setParent(self.parent)
        palette = QPalette(original)
        palette.setColor(QPalette.ColorRole.Base, QColor("#202020"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f7f7f7"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#eeeeee"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#123456"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.parent.setPalette(palette)
        self.parent.show()
        self.table.show()
        self.assertEqual(self.row_colors(3)[1].name(), "#202020")
        self.assertEqual(self.parent.palette().color(QPalette.ColorRole.AlternateBase).name(), "#f7f7f7")
        self.assertEqual(APP.palette(), original)
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#303030"))
        self.parent.setPalette(palette)
        self.assertEqual(self.row_colors(3)[1].name(), "#303030")
        self.table.selectRow(3)
        self.assertEqual(self.row_colors(3, selected=True)[1].name(), "#123456")

    def test_fallback_does_not_assume_gradient_endpoints_prove_readability(self):
        APP.setStyleSheet("")
        gradient = QLinearGradient(0, 0, 1, 0)
        gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
        gradient.setColorAt(0, QColor("#000000"))
        gradient.setColorAt(1, QColor("#ffffff"))
        palette = self.table.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#757575"))
        palette.setBrush(QPalette.ColorRole.Base, QBrush(gradient))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#757575"))
        self.table.setPalette(palette)
        # Both endpoints contrast with grey text; the interpolated middle does not.
        # With no demonstrably readable normal brush, leave this theme alone.
        self.assertEqual(self.row_colors(3)[1].name(), "#757575")

    def test_checked_row_background_survives_fallback(self):
        APP.setStyleSheet("QTableView {color:#e9e6e4; background-color:#3f4041;}")
        self.model.set_rows_selected([2, 3], True)
        ordinary = self.row_colors(2)[1]
        alternate = self.row_colors(3)[1]
        self.assertEqual(ordinary, alternate)
        self.assertNotEqual(alternate.name(), "#3f4041")
        self.assert_readable(3)
