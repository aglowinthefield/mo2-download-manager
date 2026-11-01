"""Window acceptance tests using real Qt event loops and a controlled host."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from support import APP, Organizer, QTimer, archive
from src.download_manager_window import DownloadManagerWindow, HashProgressDialog, QThread, QtWidgets


class DownloadWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.organizer = Organizer(self.directory)
        self.window = DownloadManagerWindow(self.organizer)
        self.addCleanup(self.cleanup_window)
        self.dialogs = []
        network = patch("http.client.HTTPSConnection", side_effect=AssertionError("Network forbidden in tests"))
        self.network = network.start()
        self.addCleanup(network.stop)

    def cleanup_window(self):
        worker = self.window._refresh_worker
        if worker is not None:
            worker.wait(5000)
        APP.processEvents()
        self.window.close()
        self.window._table_model._model._executor.shutdown(wait=True)

    def load(self):
        self.window._table_model.refresh()
        self.window._table_model.select_all()
        self.window.update_button_states()

    def dismiss_message(self, answer=QtWidgets.QMessageBox.StandardButton.Ok):
        box = APP.activeModalWidget()
        if isinstance(box, QtWidgets.QMessageBox):
            self.dialogs.append((box.text(), box.informativeText(), box.detailedText()))
            box.button(answer).click()

    def wait_until(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            APP.processEvents()
            time.sleep(0.001)
        self.assertTrue(predicate(), "Qt operation did not finish")

    def test_delete_can_be_cancelled_and_confirmation_counts_filtered_checks(self):
        first = archive(self.directory, "visible.7z")
        second = archive(self.directory, "other.7z")
        self.load()
        self.window._search_input.setText("visible")
        QTimer.singleShot(0, lambda: self.dismiss_message(QtWidgets.QMessageBox.StandardButton.No))
        self.window.delete_selected()
        self.assertEqual(len(self.dialogs), 1)
        text = " ".join(self.dialogs[0])
        self.assertIn("2 checked downloads", text)
        self.assertIn("1 filtered-out", text)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        self.assertEqual(len(self.window._table_model.get_selected()), 2)
        self.assertTrue(self.window._refresh_button.isEnabled())

    def test_all_conflicting_entry_points_are_guarded_during_confirmation(self):
        path = archive(self.directory)
        self.load()
        observed = []

        def try_overlap():
            self.window.refresh_data()
            self.window.install_selected()
            # No credentials: a missing guard would open a nested error dialog.
            QTimer.singleShot(0, self.dismiss_message)
            self.window.requery_selected()
            observed.append((self.window._refresh_worker, self.window._install_panel.is_running()))
            self.dismiss_message(QtWidgets.QMessageBox.StandardButton.No)

        QTimer.singleShot(0, try_overlap)
        self.window.delete_selected()
        self.assertEqual(observed, [(None, False)])
        self.assertTrue(path.exists())

    def auto_dismiss_messages(self):
        timer = QTimer()
        def dismiss():
            box = APP.activeModalWidget()
            if isinstance(box, QtWidgets.QMessageBox):
                yes = QtWidgets.QMessageBox.StandardButton.Yes
                self.dismiss_message(yes if box.button(yes) else QtWidgets.QMessageBox.StandardButton.Ok)
        timer.timeout.connect(dismiss)
        timer.start(5)
        self.addCleanup(timer.stop)
        return timer

    def test_confirmed_delete_shows_one_summary_and_no_second_refresh(self):
        path = archive(self.directory)
        self.load()
        timer = self.auto_dismiss_messages()
        self.window.delete_selected()
        timer.stop()
        self.assertEqual(len(self.dialogs), 2)  # Confirmation, then the batch summary.
        self.assertIn("1 complete, 0 partial, 0 failed", self.dialogs[1][0])
        self.assertIn(str(path), self.dialogs[1][2])
        self.assertFalse(path.exists())
        self.assertEqual(self.window._table_model.rowCount(), 0)
        self.assertIsNone(self.window._refresh_worker)
        self.assertTrue(self.window._refresh_button.isEnabled())

    def test_failed_refresh_unlocks_and_preserves_snapshot_until_retry(self):
        path = archive(self.directory)
        self.load()
        timer = self.auto_dismiss_messages()
        with patch("os.scandir", side_effect=PermissionError("scan denied")):
            self.window.refresh_data()
            self.wait_until(lambda: self.window._operation is None)
        timer.stop()
        self.assertEqual(len(self.dialogs), 1)
        self.assertTrue(self.window._model.stale)
        self.assertEqual(self.window._table_model.rowCount(), 1)
        self.assertEqual(len(self.window._table_model.get_selected()), 1)
        self.assertTrue(self.window._refresh_button.isEnabled())
        self.assertFalse(self.window._delete_action.isEnabled())
        self.assertFalse(self.window._hide_action.isEnabled())
        self.window.delete_selected()  # Programmatic calls must also be rejected.
        self.window.hide_selected()
        self.assertTrue(path.exists())
        self.window.refresh_data()
        self.wait_until(lambda: self.window._operation is None)
        self.assertFalse(self.window._model.stale)
        self.assertTrue(self.window._delete_action.isEnabled())

    def test_hide_scan_failure_retains_verified_effect_and_reports_once(self):
        path = archive(self.directory)
        self.load()
        timer = self.auto_dismiss_messages()
        real_scandir = os.scandir
        def deny_download_scan(directory):
            if str(directory) == str(self.directory):
                raise PermissionError("scan denied")
            return real_scandir(directory)
        with patch("os.scandir", side_effect=deny_download_scan):
            self.window.hide_selected()
        timer.stop()
        self.assertEqual(len(self.dialogs), 1)
        self.assertIn("view is stale", self.dialogs[0][1])
        self.assertTrue(self.window._model.data[0].hidden)
        self.assertTrue(path.exists())
        self.assertFalse(self.window._table_model.get_selected())
        self.assertTrue(self.window._refresh_button.isEnabled())

    def test_install_guard_covers_host_callback_and_between_item_delay(self):
        path = archive(self.directory)
        self.load()
        observed = []
        def overlap():
            self.window._table_model.select_all()
            self.window.delete_selected()
            self.window.hide_selected()
            self.window.requery_selected()
            self.window.refresh_data()
            observed.append((self.window._operation, self.window._refresh_worker, path.exists()))
        self.organizer.on_install = overlap
        self.window.install_selected()
        self.wait_until(lambda: bool(self.organizer.installed))
        overlap()  # The model is idle between items, but the window must still guard.
        self.assertEqual(observed, [("install", None, True), ("install", None, True)])
        self.window._install_panel._cancel_button.click()
        self.wait_until(lambda: self.window._operation is None)
        self.assertTrue(self.window._refresh_button.isEnabled())
        self.assertTrue(path.exists())
        self.network.assert_not_called()

    def test_requery_cancellation_stops_hash_before_unlocking_and_skips_lookup(self):
        path = archive(self.directory)
        self.load()
        self.organizer.settings[("Download Manager", "nexusApiKey")] = "test-key"
        observed = []
        def cancel():
            self.window.delete_selected()
            self.window.hide_selected()
            self.window.install_selected()
            self.window.refresh_data()
            observed.append((self.window._operation, self.window._refresh_worker, path.exists()))
            self.window.hash_dialog.reject()
        QTimer.singleShot(0, cancel)
        self.window.requery_selected()
        self.assertEqual(observed, [("requery", None, True)])
        self.assertFalse(self.window.hash_worker.isRunning())
        self.assertIsNone(self.window._operation)
        self.assertTrue(self.window._refresh_button.isEnabled())
        self.assertEqual(len(self.window._table_model.get_selected()), 1)
        self.network.assert_not_called()

    def test_hash_failure_unlocks_without_lookup_or_wrong_typed_result(self):
        path = archive(self.directory)
        self.load()
        self.organizer.settings[("Download Manager", "nexusApiKey")] = "test-key"
        path.unlink()
        timer = self.auto_dismiss_messages()
        self.window.requery_selected()
        timer.stop()
        self.assertEqual(len(self.dialogs), 1)
        self.assertIn("Could not hash", self.dialogs[0][0])
        self.assertTrue(self.window.hash_worker.error)
        self.assertIsNone(self.window.hash_worker.result)
        self.assertFalse(self.window.hash_worker.isRunning())
        self.assertIsNone(self.window._operation)
        self.assertTrue(self.window._refresh_button.isEnabled())
        self.network.assert_not_called()

    def test_hash_dialog_exception_waits_for_worker_before_unlocking(self):
        archive(self.directory)
        self.load()
        self.organizer.settings[("Download Manager", "nexusApiKey")] = "test-key"
        waited = []
        real_wait, real_exec = QThread.wait, QtWidgets.QDialog.exec
        def record_wait(worker, *args):
            waited.append(worker)
            return real_wait(worker, *args)
        def fail_hash_dialog(dialog):
            if isinstance(dialog, HashProgressDialog):
                raise RuntimeError("dialog loop failed")
            return real_exec(dialog)
        timer = self.auto_dismiss_messages()
        with patch.object(QThread, "wait", record_wait), patch.object(QtWidgets.QDialog, "exec", fail_hash_dialog):
            self.window.requery_selected()
        timer.stop()
        try:
            self.assertIn(self.window.hash_worker, waited)
            self.assertFalse(self.window.hash_worker.isRunning())
            self.assertIsNone(self.window._operation)
            self.network.assert_not_called()
        finally:
            self.window.hash_worker.requestInterruption()
            self.window.hash_worker.wait()

    def test_already_hidden_summary_includes_full_path_and_noop_reason(self):
        path = archive(self.directory, metadata="[General]\nmodName=Example\nremoved=true\n")
        self.load()
        timer = self.auto_dismiss_messages()
        self.window.hide_selected()
        timer.stop()
        self.assertEqual(len(self.dialogs), 1)
        self.assertIn(str(path), self.dialogs[0][2])
        self.assertIn("already present", self.dialogs[0][2])
