import os.path
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List

import mobase

from .util import logger

try:
    from PyQt6.QtCore import QSettings, QDateTime, QVariant
except ImportError:
    from PyQt5.QtCore import QSettings

from .download_entry import DownloadEntry


class DownloadManagerModel:
    __organizer: mobase.IOrganizer
    __data: List[DownloadEntry]

    __files: List[str] = []

    def __init__(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__data = []

    def refresh(self, omit_installed: bool = False):
        self.__files = self.collectMetaFiles()
        self.readMetaFiles()
        if omit_installed:
            self.__data = [d for d in self.__data if not d.installed]

    def readMetaFiles(self):
        self.__data = []
        for f in self.__files:
            normalized_path = os.path.normpath(f)
            if not os.path.exists(normalized_path):
                print(f"File not found: {normalized_path}")
            file_setting = QSettings(normalized_path, QSettings.Format.IniFormat)

            name = file_setting.value("name")
            mod_name = file_setting.value("modName")
            file_name = os.path.basename(normalized_path)
            # file_time: QVariant = file_setting.value("fileTime")
            file_time = datetime.fromtimestamp(os.path.getmtime(normalized_path))
            version = file_setting.value("version")
            installed = file_setting.value("installed") == "true"
            raw_path = Path(normalized_path.removesuffix(".meta"))

            # if not file_time.isValid():
            #     logger.info("Invalid QDateTime " + str(file_time))
            if mod_name is None and file_name is None:
                print(f"Empty meta found for: {normalized_path}")
                continue

            # TODO: Do we want to try semver parsing here? Most mods don't have valid semver strings
            file_dl_entry = DownloadEntry(
                name,
                mod_name,
                file_name,
                file_time,
                version,
                installed,
                raw_path,
            )
            self.__data.append(file_dl_entry)

        self.__data.sort(key=lambda x: (x.modname or x.filename, x.version, x.filetime))

    def collectMetaFiles(self):
        directory_path = Path(self.getDownloadsPath())
        files = [str(f) for f in directory_path.glob("*.meta") if f.is_file()]
        return files

    def getDownloadsPath(self):
        return self.__organizer.downloadsPath()

    def get_duplicates(self) -> set[DownloadEntry]:
        dupes = set()

        grouped_by_name = defaultdict(list)

        for entry in self.__data:
            grouped_by_name[entry.name].append(entry)

        logger.info(grouped_by_name)

        for key, value in grouped_by_name.items():
            if len(value) > 1:
                dupes.update(
                    sorted([dl for dl in value if dl.version], key=lambda x: x.version)[
                        :-1
                    ]
                )
        return dupes

    def delete(self, item: DownloadEntry):
        file_to_delete = next((d for d in self.__data if d == item), None)
        if file_to_delete is None:
            return
        if Path.is_file(file_to_delete.raw_file_path):
            Path.unlink(file_to_delete.raw_file_path)

    def bulk_install(self, items: set[DownloadEntry]):
        for mod in items:
            self.__organizer.installMod(mod.raw_file_path)

    @property
    def data(self):
        return self.__data
