import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from typing import List, Set, Tuple

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


def _determine_worker_count() -> int:
    cpu_count = os.cpu_count() or 1
    return min(32, max(4, cpu_count * 4))


def _to_bool(value) -> bool:
    return str(value).strip().lower() == "true"


def _load_meta_file(meta_path: Path):
    parser = ConfigParser()
    parser.optionxform = str  # preserve key casing used by MO2

    try:
        with meta_path.open("r", encoding="utf-8", errors="ignore") as handle:
            parser.read_file(handle)
    except FileNotFoundError:
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to read meta file %s: %s", meta_path, exc)
        return None

    if parser.sections():
        section = parser[parser.sections()[0]]
    else:
        section = parser.defaults()

    return dict(section)


def _file_path_to_download_entry(archive_path: Path, stat_result: os.stat_result):
    meta_path = archive_path.with_name(f"{archive_path.name}.meta")
    meta_values = _load_meta_file(meta_path)

    if not meta_values:
        return _file_path_to_stub(archive_path, stat_result)

    return DownloadEntry(
        name=meta_values.get("name", archive_path.stem),
        modname=meta_values.get("modName", ""),
        filename=meta_path.name,
        filetime=datetime.fromtimestamp(stat_result.st_mtime),
        version=meta_values.get("version", ""),
        installed=_to_bool(meta_values.get("installed", "")),
        hidden=_to_bool(meta_values.get("removed", "")),
        raw_file_path=archive_path,
        raw_meta_path=meta_path,
        file_size=stat_result.st_size,
        nexus_file_id=meta_values.get("fileID"),
        nexus_mod_id=meta_values.get("modID"),
        repository=meta_values.get("repository"),
        game_name=meta_values.get("gameName"),
    )


def _file_path_to_stub(archive_path: Path, stat_result: os.stat_result):
    return DownloadEntry(
        name="",
        modname="",
        filename=archive_path.name,
        filetime=datetime.fromtimestamp(stat_result.st_mtime),
        version="",
        installed=False,
        hidden=False,
        raw_file_path=archive_path,
        raw_meta_path=None,
        file_size=stat_result.st_size,
        nexus_file_id=None,
        nexus_mod_id=None,
        repository=None,
        game_name=None,
    )


def _process_file(file_info: Tuple[Path, os.stat_result]):
    try:
        archive_path, stat_result = file_info
        return _file_path_to_download_entry(archive_path, stat_result)
    except Exception as e:
        logger.error(f"Error processing file {file_info[0]}: {e}")
        return None


class DownloadManagerModel:
    __organizer: mobase.IOrganizer
    __data: List[DownloadEntry]
    __data_no_installed: List[DownloadEntry]

    def __init__(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__data = []
        self.__data_no_installed = []
        self._executor = ThreadPoolExecutor(max_workers=_determine_worker_count())

    def refresh(self):
        files: List[Tuple[Path, os.stat_result]] = self._collect_archive_files()
        self._read_meta_files(files)
        self.__data_no_installed = [d for d in self.__data if not d.installed]

    def _read_meta_files(self, files: List[Tuple[Path, os.stat_result]]):
        self.__data = []
        futures = [self._executor.submit(_process_file, file_info) for file_info in files]

        for future in as_completed(futures):
            entry = future.result()
            if entry:
                self.__data.append(entry)
            else:
                logger.info("Entry broken. Should not happen.")

    def _collect_archive_files(self) -> List[Tuple[Path, os.stat_result]]:
        directory_path = Path(self.__organizer.downloadsPath())
        if not directory_path.exists():
            return []

        files: List[Tuple[Path, os.stat_result]] = []
        valid_suffixes = (".zip", ".7z", ".rar", ".7zip")

        try:
            with os.scandir(directory_path) as iterator:
                for entry in iterator:
                    if not entry.is_file():
                        continue

                    lower_name = entry.name.lower()
                    if not lower_name.endswith(valid_suffixes):
                        continue

                    archive_path = Path(entry.path)
                    if archive_path.stem.endswith("unfinished"):
                        continue

                    try:
                        stat_result = entry.stat(follow_symlinks=False)
                    except FileNotFoundError:
                        continue

                    files.append((archive_path, stat_result))
        except FileNotFoundError:
            return []

        return files

    @staticmethod
    def _duplicate_group_key(entry: DownloadEntry) -> str:
        for candidate in (entry.name, entry.modname):
            if candidate:
                return candidate.strip().lower()
        if entry.raw_file_path:
            return entry.raw_file_path.stem.lower()
        return entry.filename.lower()

    def get_duplicates(self):
        duplicates: Set[DownloadEntry] = set()
        grouped_by_key = defaultdict(list)

        for entry in self.__data:
            key = self._duplicate_group_key(entry)
            grouped_by_key[key].append(entry)

        for entries in grouped_by_key.values():
            if len(entries) < 2:
                continue

            ordered = sorted(
                entries,
                key=lambda item: (
                    item.filetime.timestamp(),
                    item.filename.lower(),
                    item.version or "",
                ),
                reverse=True,
            )

            duplicates.update(ordered[1:])

        return duplicates

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
            try:
                stat_result = mod.raw_file_path.stat()
                updated_entry = _file_path_to_download_entry(mod.raw_file_path, stat_result)
            except FileNotFoundError:
                updated_entry = None

            if updated_entry:
                self.__data = [updated_entry if x == mod else x for x in self.__data]
                self.__data_no_installed = [d for d in self.__data if not d.installed]


    def _create_meta_from_mod_and_nexus_response(
        self, mod: DownloadEntry, response: NexusMD5Response
    ) -> Path:
        meta_file_name = mod.raw_file_path.with_name(f"{mod.raw_file_path.name}.meta")

        name = response.file_details.name
        mod_name = response.mod.name

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
        meta_file.setValue("installed", str(mod.installed).lower())
        meta_file.setValue("uninstalled", "false")
        meta_file.setValue("paused", "false")
        meta_file.setValue("removed", "false") # read settings to see if DLs are hidden?
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

    def __del__(self):
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
