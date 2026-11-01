import os
import tempfile
from threading import Event, Thread
import unittest
from pathlib import Path
from unittest.mock import patch

from support import Organizer, QSettings, archive
from src.download_manager_model import DownloadManagerModel


class DownloadActionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.organizer = Organizer(self.directory)
        self.model = DownloadManagerModel(self.organizer)
        self.addCleanup(self.model._executor.shutdown, wait=True)
        network = patch("http.client.HTTPSConnection", side_effect=AssertionError("Network forbidden in tests"))
        network.start()
        self.addCleanup(network.stop)

    def test_delete_removes_archive_and_unparseable_sidecar_and_publishes_state(self):
        path = archive(self.directory, metadata="not valid metadata")
        self.model.refresh()
        result = self.model.delete_downloads(self.model.data)
        self.assertEqual([outcome.status for outcome in result.outcomes], ["complete"])
        self.assertEqual(self.model.data, ())
        self.assertEqual(result.snapshot, ())
        self.assertFalse(path.exists())
        self.assertFalse(Path(str(path) + ".meta").exists())

    def test_partial_delete_retains_sidecar_details_and_continues_batch(self):
        first = archive(self.directory, "first.7z", metadata=None)
        sidecar = Path(str(first) + ".meta")
        sidecar.mkdir()  # Cannot be unlinked as a file, on both Windows and Unix.
        second = archive(self.directory, "second.7z")
        self.model.refresh()
        entries = sorted(self.model.data, key=lambda item: item.raw_file_path.name)
        result = self.model.delete_downloads(entries)
        self.assertEqual([item.status for item in result.outcomes], ["partial", "complete"])
        self.assertEqual(result.outcomes[0].changed_paths, (first,))
        self.assertEqual(result.outcomes[0].remaining_paths, (sidecar,))
        self.assertTrue(result.outcomes[0].error)
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        self.assertEqual(result.snapshot, ())

    def test_reconciliation_failure_keeps_verified_effects_and_blocks_more_actions(self):
        deleted = archive(self.directory, "deleted.7z")
        kept = archive(self.directory, "kept.7z")
        self.model.refresh()
        target = next(item for item in self.model.data if item.raw_file_path == deleted)
        with patch("os.scandir", side_effect=PermissionError("scan denied")):
            result = self.model.delete_downloads([target])
        self.assertEqual(result.outcomes[0].status, "complete")
        self.assertIn("scan denied", result.refresh_error)
        self.assertEqual([item.raw_file_path for item in result.snapshot], [kept])
        self.assertTrue(self.model.stale)
        with self.assertRaisesRegex(RuntimeError, "refresh"):
            self.model.delete_downloads(self.model.data)
        self.assertTrue(kept.exists())
        self.model.refresh()
        self.assertFalse(self.model.stale)

    def test_replaced_archive_is_not_deleted_even_with_same_size_and_timestamp(self):
        path = archive(self.directory)
        self.model.refresh()
        stamp = path.stat()
        replacement = self.directory / "replacement"
        replacement.write_bytes(b"changed contents")  # Same byte count.
        os.utime(replacement, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        replacement.replace(path)
        result = self.model.delete_downloads(self.model.data)
        self.assertEqual(result.outcomes[0].status, "failed")
        self.assertIn("changed", result.outcomes[0].error)
        self.assertTrue(path.exists())
        self.assertTrue(Path(str(path) + ".meta").exists())

    def test_hide_verifies_marker_and_keeps_archive_and_unrelated_metadata(self):
        path = archive(self.directory, metadata="[General]\nmodName=Café\nremoved=false\ncustom=keep me\n")
        self.model.refresh()
        result = self.model.hide_downloads(self.model.data)
        self.assertEqual(result.outcomes[0].status, "complete")
        self.assertEqual(len(result.snapshot), 1)
        self.assertTrue(result.snapshot[0].hidden)
        self.assertEqual(result.snapshot[0].modname, "Café")
        self.assertTrue(path.exists())
        self.assertIn("custom=keep me", Path(str(path) + ".meta").read_text(encoding="utf-8"))

    def test_mutation_is_rejected_while_refresh_is_running(self):
        path = archive(self.directory)
        self.model.refresh()
        entered, release = Event(), Event()
        real_scandir = os.scandir

        def slow_scan(directory):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test scan was not released")
            return real_scandir(directory)

        with patch("os.scandir", side_effect=slow_scan):
            thread = Thread(target=self.model.refresh)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                item = self.model.data[0]
                for operation in (
                    lambda: self.model.delete_downloads((item,)),
                    lambda: self.model.hide_downloads((item,)),
                    lambda: self.model.requery(item, "unused"),
                    lambda: self.model.install_mod_safe(item),
                ):
                    with self.assertRaisesRegex(RuntimeError, "busy"):
                        operation()
                self.assertTrue(path.exists())
            finally:
                release.set()
                thread.join(5)
        self.assertFalse(self.model.busy)

    def test_hide_uses_the_metadata_group_not_defaults_or_first_section(self):
        for name, metadata in (
            ("defaults.7z", "[DEFAULT]\nremoved=true\n[General]\nmodName=Example\n"),
            ("sections.7z", "[Other]\ncustom=keep\n[General]\nremoved=false\n"),
            ("quoted.7z", '[General]\nremoved="true"\n'),
        ):
            with self.subTest(name=name):
                path = archive(self.directory, name, metadata)
                self.model.refresh()
                item = next(item for item in self.model.data if item.raw_file_path == path)
                result = self.model.hide_downloads((item,))
                self.assertEqual(result.outcomes[0].status, "complete")
                settings = QSettings(str(path) + ".meta", QSettings.Format.IniFormat)
                settings.sync()
                self.assertEqual(str(settings.value("removed")).lower(), "true")
                self.assertTrue(next(item for item in result.snapshot if item.raw_file_path == path).hidden)

    def test_hide_does_not_recreate_a_sidecar_that_disappears_during_preparation(self):
        path = archive(self.directory)
        sidecar = Path(str(path) + ".meta")
        self.model.refresh()
        sync = QSettings.sync
        removed = []

        def remove_sidecar(settings):
            sync(settings)
            if not removed:
                sidecar.unlink()
                removed.append(True)

        with patch.object(QSettings, "sync", remove_sidecar):
            result = self.model.hide_downloads(self.model.data)
        self.assertEqual(result.outcomes[0].status, "failed")
        self.assertFalse(sidecar.exists())
        self.assertNotIn(sidecar, result.outcomes[0].remaining_paths)

    def test_hide_missing_archive_and_failed_scan_removes_the_known_absent_row(self):
        path = archive(self.directory)
        self.model.refresh()
        path.unlink()
        with patch("os.scandir", side_effect=PermissionError("scan denied")):
            result = self.model.hide_downloads(self.model.data)
        self.assertEqual(result.outcomes[0].status, "failed")
        self.assertEqual(result.snapshot, ())
        self.assertTrue(self.model.stale)

    def test_hide_write_failure_reports_uncertain_persistence(self):
        path = archive(self.directory)
        self.model.refresh()
        with patch("os.fsync", side_effect=OSError("flush denied")):
            result = self.model.hide_downloads(self.model.data)
        outcome = result.outcomes[0]
        self.assertEqual(outcome.status, "partial")
        self.assertEqual(outcome.changed_paths, ())
        self.assertEqual(outcome.uncertain_paths, (Path(str(path) + ".meta"),))
        self.assertIn("persistence is uncertain", outcome.error)
        self.assertTrue(path.exists())

    def test_delete_already_absent_files_is_complete_without_sweeping_orphans(self):
        path = archive(self.directory)
        orphan = self.directory / "unrelated.7z.meta"
        orphan.write_text("leave me alone", encoding="utf-8")
        self.model.refresh()
        path.unlink()
        Path(str(path) + ".meta").unlink()
        result = self.model.delete_downloads(self.model.data)
        self.assertEqual(result.outcomes[0].status, "complete")
        self.assertEqual(result.outcomes[0].changed_paths, ())
        self.assertEqual(result.snapshot, ())
        self.assertTrue(orphan.exists())

    def test_hide_invalid_missing_or_unreadable_metadata_never_repairs_it(self):
        for name, contents in (("missing.7z", None), ("invalid.7z", "invalid"),
                               ("empty.7z", ""), ("unknown.7z", "[Other]\nkey=value\n")):
            with self.subTest(name=name):
                path = archive(self.directory, name, contents)
                sidecar = Path(str(path) + ".meta")
                self.model.refresh()
                item = next(item for item in self.model.data if item.raw_file_path == path)
                outcome = self.model.hide_downloads((item,)).outcomes[0]
                self.assertEqual(outcome.status, "failed")
                self.assertTrue(path.exists())
                self.assertEqual(sidecar.read_text(encoding="utf-8") if sidecar.exists() else None, contents)
        path = archive(self.directory, "unreadable.7z")
        sidecar = Path(str(path) + ".meta")
        contents = sidecar.read_bytes()
        self.model.refresh()
        item = next(item for item in self.model.data if item.raw_file_path == path)
        real_open = Path.open
        def deny_sidecar(target, *args, **kwargs):
            if target == sidecar:
                raise PermissionError("read denied")
            return real_open(target, *args, **kwargs)
        with patch.object(Path, "open", deny_sidecar):
            outcome = self.model.hide_downloads((item,)).outcomes[0]
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(sidecar.read_bytes(), contents)

    def test_missing_directory_is_failed_refresh_not_successful_empty_scan(self):
        path = archive(self.directory)
        self.model.refresh()
        before = self.model.data
        moved = self.directory.with_name(self.directory.name + "-moved")
        self.directory.rename(moved)
        try:
            with self.assertRaises(FileNotFoundError):
                self.model.refresh()
            self.assertEqual(self.model.data, before)
            self.assertTrue(self.model.stale)
        finally:
            moved.rename(self.directory)
        self.assertTrue(path.exists())

    def test_install_host_callback_cannot_reenter_refresh_or_mutation(self):
        archive(self.directory)
        self.model.refresh()
        item = self.model.data[0]
        def overlap():
            for operation in (self.model.refresh,
                              lambda: self.model.delete_downloads((item,)),
                              lambda: self.model.hide_downloads((item,))):
                with self.assertRaisesRegex(RuntimeError, "busy"):
                    operation()
        self.organizer.on_install = overlap
        self.assertTrue(self.model.install_mod_safe(item))
        self.assertFalse(self.model.busy)
        self.model.refresh()
        self.assertTrue(self.model.data[0].hidden)
