import os.path
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List

import mobase

from .mo2_compat_utils import is_above_2_4
from .util import logger
from .download_entry import DownloadEntry


try:
    from PyQt6.QtCore import QSettings
except ImportError:
    from PyQt5.QtCore import QSettings


def _hide_download(item: DownloadEntry):
    file_settings = QSettings(str(item.raw_meta_path), QSettings.Format.IniFormat)
    file_settings.setValue("removed", "true")
    file_settings.sync()


def _meta_to_download_entry(normalized_path):
    file_setting = QSettings(normalized_path, QSettings.Format.IniFormat)

    # file_time: QVariant = file_setting.value("fileTime")
    name            = file_setting.value("name")
    mod_name        = file_setting.value("modName")
    file_name       = os.path.basename(normalized_path)
    file_time       = datetime.fromtimestamp(os.path.getmtime(normalized_path))
    version         = file_setting.value("version")
    installed       = file_setting.value("installed") == "true"
    raw_path        = Path(normalized_path[:-5])  # remove ".meta". removesuffix not supported in 3.9
    raw_meta_path   = Path(normalized_path)
    file_size       = raw_path.stat().st_size

    if mod_name is None and file_name is None:
        print(f"Empty meta found for: {normalized_path}")
        return None

    # Do we want to try semver parsing here? Most mods don't have valid semver strings
    return DownloadEntry(
        name,
        mod_name,
        str(file_name),
        file_time,
        version,
        installed,
        raw_path,
        raw_meta_path,
        file_size,
    )


class DownloadManagerModel:
    __organizer: mobase.IOrganizer
    __data: List[DownloadEntry]

    __files: List[str] = []

    def __init__(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__data = []

    def refresh(self, omit_installed: bool = False):
        self.__files = self.collect_meta_files()
        self.read_meta_files()
        if omit_installed:
            self.__data = [d for d in self.__data if not d.installed]

    def read_meta_files(self):
        self.__data = []
        for f in self.__files:
            normalized_path = os.path.normpath(f)
            if not os.path.exists(normalized_path):
                print(f"File not found: {normalized_path}")

            entry = _meta_to_download_entry(normalized_path)
            self.__data.append(entry) if entry else None

    def collect_meta_files(self):
        directory_path = Path(self.__organizer.downloadsPath())
        files = [
            str(f)
            for f in directory_path.glob("*.meta")
            if f.is_file() and not f.stem.endswith("unfinished")
        ]
        return files

    def get_duplicates(self):
        dupes = set()

        grouped_by_name = defaultdict(list)

        for entry in self.__data:
            grouped_by_name[entry.name].append(entry)

        logger.info(grouped_by_name)

        for _, value in grouped_by_name.items():
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
        if Path.is_file(file_to_delete.raw_meta_path):
            Path.unlink(file_to_delete.raw_meta_path)

    @staticmethod
    def bulk_hide(items):
        for entry in items:
            _hide_download(entry)

    def bulk_install(self, items):
        for mod in items:
            self.install_mod(mod)

    def install_mod(self, mod: DownloadEntry):
        mo2_version = self.__organizer.appVersion().canonicalString()
        print(f"Installing {mod.name} with MO2 API version {mo2_version}")
        if is_above_2_4(mo2_version):
            # mo2 v2.5.x
            self.__organizer.installMod(
                mod.raw_file_path,
            )
        else:
            # mo2 v2.4.x
            self.__organizer.installMod(str(mod.raw_file_path))
        _hide_download(mod)

    @property
    def data(self):
        return self.__data
