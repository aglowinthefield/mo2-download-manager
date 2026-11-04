"""Re-query regressions reported in GitHub PR #22, through the model interface."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import Organizer, QSettings, archive
from src.download_manager_model import DownloadManagerModel


class NexusRequeryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.model = DownloadManagerModel(Organizer(self.directory))
        self.addCleanup(self.model._executor.shutdown, wait=True)
        network = patch("http.client.HTTPSConnection")
        connection = network.start().return_value
        self.addCleanup(network.stop)
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = (Path(__file__).parent / "fixtures" / "nexus-md5.json").read_bytes()

    def test_requery_writes_metadata_in_qt_root_not_literal_general_group(self):
        path = archive(self.directory, metadata=None)
        self.model.refresh()
        self.model.requery(self.model.data[0], "00000000000000000000000000000000")
        settings = QSettings(str(path) + ".meta", QSettings.Format.IniFormat)
        settings.sync()
        self.assertEqual(settings.value("modID", type=int), 1234)
        self.assertEqual(settings.value("fileID", type=int), 5678)
        self.assertNotIn("General", settings.childGroups())
        self.assertEqual(self.model.data[0].name, "Example main file")

    def test_requery_uses_the_matched_file_description_not_the_mod_page(self):
        path = archive(self.directory, metadata=None)
        self.model.refresh()
        self.model.requery(self.model.data[0], "00000000000000000000000000000000")
        settings = QSettings(str(path) + ".meta", QSettings.Format.IniFormat)
        settings.sync()
        self.assertEqual(settings.value("description"), "Only this file's installation notes.")

    def test_requery_updates_existing_root_and_keeps_installed_and_custom_values(self):
        path = archive(self.directory, metadata=(
            "[General]\nname=Stale root name\ninstalled=true\ncustom=keep\n"
            "[%General]\nname=Stale legacy name\n"
        ))
        self.model.refresh()
        self.model.requery(self.model.data[0], "00000000000000000000000000000000")
        settings = QSettings(str(path) + ".meta", QSettings.Format.IniFormat)
        settings.sync()
        self.assertEqual(settings.value("name"), "Example main file")
        self.assertEqual(settings.value("custom"), "keep")
        self.assertEqual(self.model.data[0].name, "Example main file")
        self.assertTrue(self.model.data[0].installed)
