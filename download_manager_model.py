import os.path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import List

import mobase

from .download_entry import DownloadEntry
from .mo2_compat_utils import is_above_2_4
from .nexus_api import NexusApi, NexusMD5Response
from .util import logger

try:
    from PyQt6.QtCore import QSettings, QDateTime, QVariant
except ImportError:
    from PyQt5.QtCore import QSettings, QDateTime, QVariant


def _hide_download(item: DownloadEntry):
    file_settings = QSettings(str(item.raw_meta_path), QSettings.Format.IniFormat)
    file_settings.setValue("removed", "true")
    file_settings.sync()


def _file_path_to_download_entry(normalized_path: str):
    meta_path = normalized_path + ".meta"

    if not os.path.exists(meta_path):
        return _file_path_to_stub(Path(normalized_path))

    file_setting = QSettings(meta_path, QSettings.Format.IniFormat)

    # file_time: QVariant = file_setting.value("fileTime")
    name = file_setting.value("name")
    mod_name = file_setting.value("modName")
    file_name = os.path.basename(meta_path)
    file_time = datetime.fromtimestamp(os.path.getmtime(normalized_path))
    version = file_setting.value("version")
    installed = file_setting.value("installed") == "true"
    raw_path = Path(meta_path[:-5])
    raw_meta_path = Path(meta_path)
    file_size = raw_path.stat().st_size

    if mod_name is None and file_name is None:
        print(f"Empty meta found for: {normalized_path}")
        return None

    return DownloadEntry(
        name=name,
        modname=mod_name,
        filename=str(file_name),
        filetime=file_time,
        version=version,
        installed=installed,
        raw_file_path=raw_path,
        raw_meta_path=raw_meta_path,
        file_size=file_size,
    )


def _file_path_to_stub(normalized_path: Path):
    return DownloadEntry(
        name="",
        modname="",
        filename=str(os.path.basename(normalized_path)),
        filetime=datetime.fromtimestamp(os.path.getmtime(normalized_path)),
        version="",
        installed=False,
        raw_file_path=normalized_path,
        raw_meta_path=None,
        file_size=normalized_path.stat().st_size,
    )


def _process_file(path):
    normalized_path = os.path.normpath(path)
    if not os.path.exists(normalized_path):
        print(f"File not found: {normalized_path}")
        return None

    return _file_path_to_download_entry(normalized_path)


class DownloadManagerModel:
    __organizer: mobase.IOrganizer
    __data: List[DownloadEntry]
    __data_no_installed: List[DownloadEntry]

    __files: List[str] = []

    def __init__(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__data = []
        self.__data_no_installed = []

    def refresh(self):
        self.__files = self.collect_archive_files()
        self._read_meta_files()
        self.__data_no_installed = [d for d in self.__data if not d.installed]

    def _read_meta_files(self):
        self.__data = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for f in self.__files:
                futures.append(executor.submit(_process_file, f))

            for future in futures:
                entry = future.result()
                if entry:
                    self.__data.append(entry)
                else:
                    logger.info("Entry broken. Should not happen.")

    def collect_archive_files(self):
        directory_path = Path(self.__organizer.downloadsPath())
        extensions = ["*.zip", "*.7z", "*.rar", "*.7zip"]
        files = [
            str(f)
            for ext in extensions
            for f in directory_path.glob(ext)
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

    def requery(self, mod: DownloadEntry, md5_hash: str):
        nexus_api = NexusApi(
            self.__organizer.pluginSetting("Download Manager", "nexusApiKey")
        )
        response = nexus_api.md5_lookup(md5_hash)
        logger.info(response)
        if response is not None:
            self._create_meta_from_mod_and_nexus_response(mod, response)

    def _create_meta_from_mod_and_nexus_response(
        self, mod: DownloadEntry, response: NexusMD5Response
    ):
        meta_file_name = mod.raw_file_path.with_name(f"{mod.raw_file_path.name}.meta")

        meta_file = QSettings(str(meta_file_name), QSettings.Format.IniFormat)
        # meta_file.beginGroup("General")

        meta_file.setValue("gameName", self.__organizer.managedGame().gameName())
        meta_file.setValue("modID", response.mod.mod_id)
        meta_file.setValue("fileID", response.file_details.file_id)
        meta_file.setValue("url", "")  # how?
        meta_file.setValue("name", response.file_details.name)
        meta_file.setValue("description", response.mod.description)
        meta_file.setValue("modName", response.mod.name)
        meta_file.setValue("version", response.file_details.version)
        meta_file.setValue("newestVersion", "")  # omit?
        meta_file.setValue("fileTime", QDateTime.currentDateTime())
        meta_file.setValue("fileCategory", response.file_details.category_id)
        meta_file.setValue("category", response.mod.category_id)
        meta_file.setValue("repository", "Nexus")
        meta_file.setValue("userData", QVariant(response.mod.user))
        meta_file.setValue("installed", False)
        meta_file.setValue("uninstalled", False)
        meta_file.setValue("paused", False)
        meta_file.setValue("removed", False)

        # meta_file.endGroup()
        meta_file.sync()

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

    @property
    def data_no_installed(self):
        return self.__data_no_installed
