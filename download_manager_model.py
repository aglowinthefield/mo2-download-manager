import os.path
from pathlib import Path
from typing import List

import mobase
import semver

try:
    from PyQt6.QtCore import QSettings
except ImportError:
    from PyQt5.QtCore import QSettings

from .download_entry import DownloadEntry


class DownloadManagerModel:
    __organizer: mobase.IOrganizer
    __data: List[DownloadEntry]

    __files = []

    def __init__(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__data = []

    def refresh(self):
        self.__files = self.collectMetaFiles()
        self.readMetaFiles()

    def readMetaFiles(self):
        self.__data = []
        for f in self.__files:
            normalized_path = os.path.normpath(f)
            if not os.path.exists(normalized_path):
                print(f"File not found: {normalized_path}")
            file_setting = QSettings(normalized_path, QSettings.Format.IniFormat)

            mod_name = file_setting.value("modName")
            file_name = file_setting.value("name")
            file_time = file_setting.value("fileTime")
            version = file_setting.value("version")
            installed = file_setting.value("installed")

            if mod_name is None and file_name is None:
                print(f"Empty meta found for: {normalized_path}")
                continue

            file_dl_entry = DownloadEntry(
                False,
                mod_name,
                file_name,
                file_time,
                # semver.VersionInfo.parse(file_setting.value("General/version")),
                version,
                installed
            )
            self.__data.append(file_dl_entry)

    def collectMetaFiles(self):
        directory_path = Path(self.getDownloadsPath())
        files = [str(f) for f in directory_path.glob("*.meta") if f.is_file()]
        return files

    def getDownloadsPath(self):
        return self.__organizer.downloadsPath()

    # TODO
    # def toggleAtIndex(self, index: int):
    #     self.__data[index][0] = not self.__data[index][0]

    @property
    def data(self):
        return self.__data
