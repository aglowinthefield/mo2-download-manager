import json
import os
import stat
import tempfile
from contextlib import contextmanager
from threading import Lock
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import ConfigParser
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Set, Tuple

import mobase

from .download_entry import DownloadEntry
from .mo2_compat_utils import is_above_2_4
from .nexus_api import NexusApi, NexusMD5Response
from .util import logger

try:
    from PyQt6.QtCore import QSettings, QDateTime
except ImportError:
    from PyQt5.QtCore import QSettings, QDateTime


class _HiddenWriteError(OSError):
    """A sidecar write started, but its final persistence could not be verified."""


def _metadata_section(parser):
    # ConfigParser defaults are not Qt defaults. Prefer MO2's root group, with
    # compatibility for sidecars previously written as a literal General group.
    parser.defaults().clear()
    for section in ("General", "%General"):
        if parser.has_section(section):
            return section
    raise ValueError("Metadata has no General group; it has not been repaired.")


def _write_hidden_marker(meta_path: Path, validate_archive=None) -> bool:
    """Serialize with Qt, then update an existing sidecar without create-on-write."""
    identity = meta_path.lstat()
    if not stat.S_ISREG(identity.st_mode):
        raise ValueError("Metadata sidecar is not a regular file.")
    original = meta_path.read_bytes()
    parser = ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(original.decode("utf-8"))
    section = _metadata_section(parser)
    if not parser[section]:
        raise ValueError("Metadata is empty or unusable; it has not been repaired.")
    if _to_bool(parser[section].get("removed", "")):
        return False

    # QSettings may create a vanished target or retain buffered writes after an
    # error. Use it only on a disposable copy, never on the live hide target.
    with tempfile.TemporaryDirectory(prefix="mo2-hidden-") as directory:
        staged = Path(directory) / "download.meta"
        staged.write_bytes(original)
        settings = QSettings(str(staged), QSettings.Format.IniFormat)
        if hasattr(settings, "setIniCodec"):  # Qt5 otherwise interprets UTF-8 as Latin-1.
            settings.setIniCodec("UTF-8")
        settings.setFallbacksEnabled(False)
        settings.sync()
        if settings.status() != QSettings.Status.NoError:
            raise OSError(f"Cannot read metadata: {settings.status()}")
        settings.beginGroup("" if section == "General" else "General")
        settings.setValue("removed", "true")
        settings.endGroup()
        settings.sync()
        if settings.status() != QSettings.Status.NoError:
            raise OSError(f"Cannot serialize hidden marker: {settings.status()}")
        persisted = _load_meta_file(staged)
        if not persisted or not _to_bool(persisted.get("removed", "")):
            raise OSError("Hidden marker was not verified in serialized metadata.")
        payload = staged.read_bytes()
        del settings  # Release Qt's file cache before removing the temporary copy.

    if validate_archive is not None:
        validate_archive()
    write_started = False
    try:
        # r+b cannot create a missing sidecar. In-place I/O can fail partially;
        # report that explicitly instead of claiming atomicity or rolling back.
        with meta_path.open("r+b") as target:
            if (_archive_identity(os.fstat(target.fileno())) != _archive_identity(identity)
                    or _archive_identity(meta_path.lstat()) != _archive_identity(identity)):
                raise ValueError("Metadata changed during hiding; refresh before retrying.")
            write_started = True
            if target.write(payload) != len(payload):
                raise OSError("Incomplete metadata write.")
            target.truncate()
            target.flush()
            os.fsync(target.fileno())
            target.seek(0)
            if target.read() != payload:
                raise OSError("Hidden marker was not verified on disk.")
    except Exception as exc:
        if write_started:
            raise _HiddenWriteError(f"Metadata write started; persistence is uncertain: {exc}") from exc
        raise
    return True


def _hide_download(item: DownloadEntry) -> bool:
    try:
        if item.raw_meta_path is None:
            return False
        _write_hidden_marker(item.raw_meta_path)
        return True
    except Exception as exc:
        logger.error("Failed to hide %s: %s", item.filename, exc)
        return False


def _determine_worker_count() -> int:
    cpu_count = os.cpu_count() or 1
    return min(32, max(4, cpu_count * 4))


def _to_bool(value) -> bool:
    return str(value).strip().strip('"').lower() == "true"


def _parse_version_tuple(version: str) -> Tuple:
    """
    Parse a version string into a tuple for proper numeric comparison.
    
    Examples:
        "1.0" -> (1, 0)
        "2.10.3" -> (2, 10, 3)
        "1.0a" -> (1, 0, 'a')
        "" -> ()
    
    This ensures "10.0" > "9.0" and "1.10" > "1.9" (numeric comparison),
    unlike lexicographic string comparison where "9" > "10".
    """
    if not version:
        return ()
    
    parts = []
    current = ""
    
    for char in version:
        if char.isdigit():
            current += char
        elif char in ".-_":
            if current:
                parts.append(int(current) if current.isdigit() else current)
                current = ""
        else:
            if current:
                parts.append(int(current) if current.isdigit() else current)
                current = ""
            current = char
    
    if current:
        parts.append(int(current) if current.isdigit() else current)
    
    return tuple(parts)


def _load_meta_file(meta_path: Path):
    parser = ConfigParser(interpolation=None)
    parser.optionxform = str  # preserve key casing used by MO2

    try:
        with meta_path.open("r", encoding="utf-8", errors="ignore") as handle:
            parser.read_file(handle)
    except FileNotFoundError:
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to read meta file %s: %s", meta_path, exc)
        return None

    try:
        return dict(parser[_metadata_section(parser)])
    except ValueError:
        return None


def _archive_identity(stat_result):
    return (stat_result.st_dev, stat_result.st_ino, stat_result.st_size, stat_result.st_mtime_ns)


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
        archive_identity=_archive_identity(stat_result),
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
        archive_identity=_archive_identity(stat_result),
    )


def _process_file(file_info: Tuple[Path, os.stat_result]):
    archive_path, _ = file_info
    try:
        stat_result = archive_path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(stat_result.st_mode):
        return None
    return _file_path_to_download_entry(archive_path, stat_result)


@dataclass(frozen=True)
class DownloadOutcome:
    """One target: complete, partial, or failed; uncertain writes are not verified changes."""

    download: DownloadEntry
    status: str  # complete, partial, or failed
    changed_paths: Tuple[Path, ...] = ()
    remaining_paths: Tuple[Path, ...] = ()
    error: str = ""
    archive_absent: bool = False
    uncertain_paths: Tuple[Path, ...] = ()


@dataclass(frozen=True)
class DownloadBatchResult:
    """Per-target facts and the resulting collection, even when reconciliation failed."""

    outcomes: Tuple[DownloadOutcome, ...]
    snapshot: Tuple[DownloadEntry, ...]
    refresh_error: str = ""


class DownloadManagerModel:
    __organizer: mobase.IOrganizer
    __data: List[DownloadEntry]

    def __init__(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__data = []
        self._stale = True
        self._operation_lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=_determine_worker_count())

    def refresh(self):
        """Publish a complete snapshot, or retain the last known state as stale."""
        with self._exclusive():
            return self._refresh_snapshot()

    @contextmanager
    def _exclusive(self):
        if not self._operation_lock.acquire(blocking=False):
            raise RuntimeError("Downloads are busy; wait for the current operation.")
        try:
            yield
        finally:
            self._operation_lock.release()

    @property
    def busy(self):
        return self._operation_lock.locked()

    def _refresh_snapshot(self):
        try:
            files = self._collect_archive_files()
            data = self._read_meta_files(files)
        except Exception:
            self._stale = True
            raise
        self.__data = data
        self._stale = False
        return self.data

    def _read_meta_files(self, files: List[Tuple[Path, os.stat_result]]):
        data = []
        futures = [self._executor.submit(_process_file, file_info) for file_info in files]
        for future in as_completed(futures):
            entry = future.result()
            if entry is not None:
                data.append(entry)
        return data

    def _collect_archive_files(self) -> List[Tuple[Path, os.stat_result]]:
        directory_path = Path(self.__organizer.downloadsPath())
        files: List[Tuple[Path, os.stat_result]] = []
        valid_suffixes = (".zip", ".7z", ".rar", ".7zip")
        # A missing/unreadable directory is a failed scan, not an empty collection.
        with os.scandir(directory_path) as iterator:
            for entry in iterator:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if not entry.name.lower().endswith(valid_suffixes):
                    continue
                archive_path = Path(entry.path)
                if archive_path.stem.endswith("unfinished"):
                    continue
                try:
                    stat_result = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                files.append((archive_path, stat_result))
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

            # Sort by filetime (primary), then by version using semantic comparison.
            # This ensures "10.0" > "9.0" even when filetimes are identical.
            ordered = sorted(
                entries,
                key=lambda item: (
                    item.filetime.timestamp(),
                    _parse_version_tuple(item.version),
                ),
                reverse=True,
            )

            duplicates.update(ordered[1:])

        return duplicates

    def get_not_installed(self) -> Set[DownloadEntry]:
        not_installed: Set[DownloadEntry] = set()
        grouped_by_key = defaultdict(list)

        for entry in self.__data:
            key = self._duplicate_group_key(entry)
            grouped_by_key[key].append(entry)

        for entries in grouped_by_key.values():
            # Find the newest installed version's timestamp (if any)
            installed_entries = [e for e in entries if e.installed]
            
            if not installed_entries:
                # No installed version exists - add all not-installed entries
                for entry in entries:
                    if not entry.installed:
                        not_installed.add(entry)
            else:
                # Find the newest installed version by filetime
                newest_installed_time = max(e.filetime for e in installed_entries)
                
                # Include not-installed entries that are NEWER than the newest installed version
                # (these are likely updates the user hasn't installed yet)
                for entry in entries:
                    if not entry.installed and entry.filetime > newest_installed_time:
                        not_installed.add(entry)

        return not_installed

    def delete_downloads(self, items: Iterable[DownloadEntry]) -> DownloadBatchResult:
        """Delete checked archives and their exact sidecars, then reconcile once."""
        return self._apply_batch(items, "delete")

    def _apply_batch(self, items, action):
        with self._exclusive():
            if self._stale:
                raise RuntimeError("Downloads are stale; refresh before changing files.")
            targets = {item.raw_file_path: item for item in items}
            apply_one = self._delete_one if action == "delete" else self._hide_one
            outcomes = []
            for item in targets.values():
                try:
                    outcomes.append(apply_one(item))
                except Exception as exc:
                    outcomes.append(DownloadOutcome(item, "failed", error=f"Unexpected error: {exc}"))
            absent = {result.download.raw_file_path for result in outcomes if result.archive_absent}
            hidden = {result.download.raw_file_path for result in outcomes
                      if action == "hide" and result.status == "complete"}
            self.__data = [replace(item, hidden=True) if item.raw_file_path in hidden else item
                           for item in self.__data if item.raw_file_path not in absent]
            return self._reconcile(outcomes)

    def _reconcile(self, outcomes):
        error = ""
        try:
            self._refresh_snapshot()
        except Exception as exc:
            error = str(exc) or type(exc).__name__
            logger.warning("Download reconciliation failed: %s", error)
        return DownloadBatchResult(tuple(outcomes), self.data, error)

    @property
    def stale(self):
        return self._stale

    @staticmethod
    def _remaining_paths(paths):
        remaining = []
        for path in paths:
            try:
                path.lstat()
            except FileNotFoundError:
                continue
            except Exception:
                pass  # An inaccessible path is not verified absent.
            remaining.append(path)
        return tuple(remaining)

    def _validate_target(self, item, allow_missing=False):
        if not any(entry.raw_file_path == item.raw_file_path for entry in self.__data):
            raise ValueError("Download is not in the current collection; refresh before retrying.")
        try:
            current = item.raw_file_path.lstat()
        except FileNotFoundError:
            if allow_missing:
                return
            raise ValueError("Archive is missing; refresh before retrying.") from None
        if not stat.S_ISREG(current.st_mode) or _archive_identity(current) != item.archive_identity:
            raise ValueError("Archive changed since it was displayed; refresh before retrying.")

    def _delete_one(self, item):
        paths = (item.raw_file_path, Path(str(item.raw_file_path) + ".meta"))
        try:
            self._validate_target(item, allow_missing=True)
        except Exception as exc:
            return DownloadOutcome(item, "failed", remaining_paths=self._remaining_paths(paths),
                                   error=str(exc))
        changed = []
        archive_absent = False
        error = ""
        for path in paths:
            try:
                path.unlink()
                changed.append(path)
            except FileNotFoundError:
                pass
            except Exception as exc:
                error = f"{path}: {exc}"
                break  # Preserve metadata when the archive could not be deleted.
            if path == item.raw_file_path:
                archive_absent = True
        remaining = self._remaining_paths(paths)
        if remaining and not error:
            error = "Files appeared again during deletion; refresh before retrying."
        status = "complete" if not error else ("partial" if archive_absent else "failed")
        return DownloadOutcome(item, status, tuple(changed), remaining, error,
                               archive_absent and item.raw_file_path not in remaining)

    def hide_downloads(self, items: Iterable[DownloadEntry]) -> DownloadBatchResult:
        """Persist hidden markers without deleting archives or repairing metadata."""
        return self._apply_batch(items, "hide")

    def _hide_one(self, item):
        meta_path = Path(str(item.raw_file_path) + ".meta")
        try:
            self._validate_target(item)
            changed = _write_hidden_marker(meta_path, lambda: self._validate_target(item))
            return DownloadOutcome(item, "complete", (meta_path,) if changed else ())
        except Exception as exc:
            remaining = self._remaining_paths((item.raw_file_path, meta_path))
            partial = isinstance(exc, _HiddenWriteError)
            return DownloadOutcome(item, "partial" if partial else "failed",
                                   remaining_paths=remaining, error=str(exc),
                                   archive_absent=item.raw_file_path not in remaining,
                                   uncertain_paths=(meta_path,) if partial else ())

    def bulk_install(self, items):
        for mod in items:
            self.install_mod(mod)

    def requery(self, mod: DownloadEntry, md5_hash: str):
        with self._exclusive():
            self._validate_target(mod)
            self._requery(mod, md5_hash)

    def _requery(self, mod, md5_hash):
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
        meta_file.setValue("description", response.file_details.description)
        meta_file.setValue("modName", mod_name)
        meta_file.setValue("version", response.file_details.version)
        meta_file.setValue("newestVersion", "")
        meta_file.setValue("fileTime", QDateTime.currentDateTime())
        meta_file.setValue("fileCategory", response.file_details.category_id)
        meta_file.setValue("category", response.mod.category_id)
        meta_file.setValue("repository", "Nexus")
        meta_file.setValue("userData", json.dumps(asdict(response.mod.user)))
        meta_file.setValue("installed", str(mod.installed).lower())
        meta_file.setValue("uninstalled", "false")
        meta_file.setValue("paused", "false")
        meta_file.setValue("removed", "false")
        meta_file.sync()
        return meta_file_name

    def install_mod(self, mod: DownloadEntry):
        with self._exclusive():
            self._validate_target(mod)
            self._install_mod(mod)

    def _install_mod(self, mod):
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
        self._validate_target(mod)
        _hide_download(mod)

    def install_mod_safe(self, mod: DownloadEntry) -> bool:
        with self._exclusive():
            self._validate_target(mod)
            return self._install_mod_safe(mod)

    def _install_mod_safe(self, mod):
        mo2_version = self.__organizer.appVersion().canonicalString()
        logger.debug("install_mod_safe: starting for %s (MO2 version %s)", mod.name or mod.filename, mo2_version)
        try:
            logger.debug("install_mod_safe: about to call organizer.installMod for %s", mod.filename)
            if is_above_2_4(mo2_version):
                self.__organizer.installMod(mod.raw_file_path)
            else:
                self.__organizer.installMod(str(mod.raw_file_path))
            logger.debug("install_mod_safe: organizer.installMod returned for %s", mod.filename)
            self._validate_target(mod)
            result = _hide_download(mod)
            logger.debug("install_mod_safe: _hide_download returned %s for %s", result, mod.filename)
            return result
        except Exception as e:
            logger.error("install_mod_safe: exception for %s: %s", mod.filename, e)
            return False

    @property
    def data(self):
        return tuple(self.__data)

    @property
    def data_no_installed(self):
        return tuple(item for item in self.__data if not item.installed)

    def __del__(self):
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
