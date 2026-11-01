"""Qt presentation acceptance tests over real download action results."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import Organizer, Qt, archive
from src.download_manager_table_model import Column, DownloadManagerTableModel
from src.download_manager_window import DownloadFilterProxyModel


class DownloadTableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.table = DownloadManagerTableModel(Organizer(self.directory))
        self.addCleanup(self.table._model._executor.shutdown, wait=True)
        self.proxy = DownloadFilterProxyModel()
        self.proxy.setSourceModel(self.table)

    def test_delete_keeps_failed_checks_and_filters_and_removes_filtered_targets(self):
        locked = archive(self.directory, "visible-locked.7z")
        removed = archive(self.directory, "visible-remove.7z")
        installed = archive(self.directory, "installed.7z", "[General]\ninstalled=true\n")
        self.table.refresh()
        self.table.select_all()
        self.table.toggle_show_installed(True)
        self.proxy.set_search_text("visible")
        self.proxy.sort(Column.FILENAME, Qt.SortOrder.DescendingOrder)
        unlink = Path.unlink

        def deny_locked(path, *args, **kwargs):
            if path == locked:
                raise PermissionError("archive locked")
            return unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", deny_locked):
            result = self.table.delete_selected()
        self.assertEqual(sorted(item.status for item in result.outcomes), ["complete", "complete", "failed"])
        self.assertFalse(removed.exists())
        self.assertFalse(installed.exists())
        self.assertEqual({item.raw_file_path for item in self.table.get_selected()}, {locked})
        self.assertEqual(self.proxy.rowCount(), 1)
        self.assertEqual(self.proxy.sortOrder(), Qt.SortOrder.DescendingOrder)
        archive(self.directory, "another-installed.7z", "[General]\ninstalled=true\n")
        self.table.refresh()
        self.proxy.set_search_text("")
        self.assertEqual(self.table.rowCount(), 1)  # Hide Installed survives refresh.

    def test_hide_updates_snapshots_without_losing_unrelated_checks(self):
        first = archive(self.directory, "first.7z")
        second = archive(self.directory, "second.7z")
        self.table.refresh()
        self.table.select_all()
        target = next(item for item in self.table.get_selected() if item.raw_file_path == first)
        before = self.table._model.data
        result = self.table.hide_selected((target,))
        self.assertTrue(next(item for item in result.snapshot if item.raw_file_path == first).hidden)
        self.assertFalse(next(item for item in before if item.raw_file_path == first).hidden)
        self.assertEqual({item.raw_file_path for item in self.table.get_selected()}, {second})
        self.assertEqual(self.table.rowCount(), 2)
        self.table.sort(Column.FILENAME, Qt.SortOrder.DescendingOrder)
        self.assertIsInstance(self.table._model.data, tuple)
