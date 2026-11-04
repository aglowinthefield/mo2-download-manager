"""Controlled MO2 host adapter; filesystem and Qt behavior remain real."""
import os
import sys
import types
from pathlib import Path

class Organizer:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.settings = {}
        self.installed = []
        self.on_install = None

    def appVersion(self):
        return types.SimpleNamespace(canonicalString=lambda: "2.5.2")

    def installMod(self, path, *args):
        self.installed.append(path)
        if self.on_install:
            self.on_install()
        return True

    def downloadsPath(self):
        return str(self.directory)

    def managedGame(self):
        return types.SimpleNamespace(gameShortName=lambda: "skyrimse")

    def pluginSetting(self, plugin, key):
        return self.settings.get((plugin, key), "")

    def setPluginSetting(self, plugin, key, value):
        self.settings[plugin, key] = value


try:
    import mobase
except ImportError:
    mobase = types.ModuleType("mobase")
    mobase.IOrganizer = Organizer
    sys.modules["mobase"] = mobase

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QSettings, QTimer
    DEFAULT_PLATFORM = "offscreen"
except ImportError:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt, QSettings, QTimer
    # Qt 5.15.2 QMessageBox dereferences a null native interface with offscreen on Windows.
    DEFAULT_PLATFORM = "windows" if os.name == "nt" else "offscreen"

os.environ.setdefault("QT_QPA_PLATFORM", DEFAULT_PLATFORM)
APP = QApplication.instance() or QApplication([])


def archive(directory, name="Example.v1.2.7z", metadata="[General]\nmodName=Example\nremoved=false\n"):
    path = Path(directory) / name
    path.write_bytes(b"archive contents")
    if metadata is not None:
        Path(str(path) + ".meta").write_text(metadata, encoding="utf-8")
    return path
