import os.path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import List

import mobase

from ..model.download_entry import DownloadEntry
from ..nexus.nexus_api import NexusApi, NexusMD5Response
from ..util.mo2_compat_utils import is_above_2_4
from ..util.util import logger

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

    archive_path = Path(meta_path[:-5])

    return DownloadEntry(
        name=file_setting.value("name"),
        modname=file_setting.value("modName"),
        filename=str(os.path.basename(meta_path)),
        filetime=datetime.fromtimestamp(os.path.getmtime(normalized_path)),
        version=file_setting.value("version"),
        installed=file_setting.value("installed") == "true",
        raw_file_path=archive_path,
        raw_meta_path=Path(meta_path),
        file_size=archive_path.stat().st_size,
        nexus_file_id=file_setting.value("fileID"),
        nexus_mod_id=file_setting.value("modID"),
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
        nexus_file_id=None,
        nexus_mod_id=None
    )


def _process_file(path):
    try:
        normalized_path = os.path.normpath(path)
        if not os.path.exists(normalized_path):
            print(f"File not found: {normalized_path}")
            return None
        return _file_path_to_download_entry(normalized_path)
    except Exception as e:
        logger.error(f"Error processing file {path}: {e}")
        return None

def _matches_seq_item(seq_item: str, *args):
    for arg in args:
        if seq_item == arg:
            return True
    return False

class DownloadManagerModel:
    __organizer: mobase.IOrganizer
    __data: List[DownloadEntry]
    __data_no_installed: List[DownloadEntry]

    def __init__(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__data = []
        self.__data_no_installed = []

    def refresh(self):
        files: List[str] = self._collect_archive_files()
        self._read_meta_files(files)
        self.__data_no_installed = [d for d in self.__data if not d.installed]

    def _read_meta_files(self, files: List[str]):
        self.__data = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for f in files:
                futures.append(executor.submit(_process_file, f))

            for future in futures:
                entry = future.result()
                if entry:
                    self.__data.append(entry)
                else:
                    logger.info("Entry broken. Should not happen.")

    def _collect_archive_files(self):
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
        if file_to_delete.raw_file_path and Path.is_file(file_to_delete.raw_file_path):
            Path.unlink(file_to_delete.raw_file_path)
        if file_to_delete.raw_meta_path and Path.is_file(file_to_delete.raw_meta_path):
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
        if response is not None:
            # Create a new meta file for this download
            self._create_meta_from_mod_and_nexus_response(mod, response)
            # Create a new DownloadEntry for the meta file. Assuming the meta file now exists, we pass the raw_file_path
            updated_entry: DownloadEntry = _process_file(mod.raw_file_path)
            if updated_entry:
                self.__data = [updated_entry if x == mod else x for x in self.__data]
                # TODO: This should just be a filter on the table. Rework the table UI in the next version
                self.__data_no_installed = [d for d in self.__data if not d.installed]


    def _create_meta_from_mod_and_nexus_response(
        self, mod: DownloadEntry, response: NexusMD5Response
    ) -> Path:
        meta_file_name = mod.raw_file_path.with_name(f"{mod.raw_file_path.name}.meta")

        name = response.file_details.name
        mod_name = response.mod.name

        # check if mod installed using possible guessed names. might not be perfect. might be bad! who knows.
        mod_list = self.__organizer.modList()
        all_mods = mod_list.allMods()
        match = next((m for m in all_mods if _matches_seq_item(m, name, mod_name)), None)
        installed = match is not None

        meta_file = QSettings(str(meta_file_name), QSettings.Format.IniFormat)
        meta_file.setValue("gameName", self.__organizer.managedGame().gameShortName())
        meta_file.setValue("modID", response.mod.mod_id)
        meta_file.setValue("fileID", response.file_details.file_id)
        meta_file.setValue("url", f"https://www.nexusmods.com/skyrimspecialedition/mods/{response.mod.mod_id}")
        meta_file.setValue("name", name)
        meta_file.setValue("description", response.mod.description)
        meta_file.setValue("modName", mod_name)
        meta_file.setValue("version", response.file_details.version)
        meta_file.setValue("newestVersion", "")  # omit?
        meta_file.setValue("fileTime", QDateTime.currentDateTime())
        meta_file.setValue("fileCategory", response.file_details.category_id)
        meta_file.setValue("category", response.mod.category_id)
        meta_file.setValue("repository", "Nexus")
        meta_file.setValue("userData", QVariant(response.mod.user))
        meta_file.setValue("installed", installed)
        meta_file.setValue("uninstalled", False)
        meta_file.setValue("paused", False)
        meta_file.setValue("removed", False)
        meta_file.sync()
        return meta_file_name

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
