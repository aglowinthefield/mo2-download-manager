﻿from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Union

from .class_helpers import DictMixin


@dataclass(frozen=True)
class DownloadEntry(DictMixin):
    name: str
    modname: str
    filename: str
    filetime: datetime
    version: str
    installed: bool
    raw_file_path: Path
    raw_meta_path: Union[Path, None]  # 3.9 doesn't allow X | Y union
    file_size: float
