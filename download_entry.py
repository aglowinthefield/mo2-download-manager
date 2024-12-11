from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class DictMixin:
    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)


@dataclass(frozen=True)
class DownloadEntry(DictMixin):
    name: str
    modname: str
    filename: str
    filetime: datetime
    version: str
    installed: bool
    raw_file_path: Path
    raw_meta_path: Path
    file_size: float
