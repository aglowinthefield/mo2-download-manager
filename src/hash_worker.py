import hashlib
from dataclasses import dataclass
from pathlib import Path

from .download_entry import DownloadEntry

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:
    from PyQt5.QtCore import QThread, pyqtSignal

@dataclass
class HashResult:
    md5_hash: str
    mod: DownloadEntry

class HashWorker(QThread):
    progress_updated = pyqtSignal(int)
    hash_computed = pyqtSignal(HashResult)
    failed = pyqtSignal(str)

    def __init__(self, mod: DownloadEntry, chunk_size=4096):
        super().__init__()
        self.mod = mod
        self.file_path = mod.raw_file_path
        self.chunk_size = chunk_size
        self.result = None
        self.error = ""

    def run(self):
        try:
            file_size = Path(self.file_path).stat().st_size
            processed_size = 0
            hash_md5 = hashlib.md5()
            last_update = -1

            with open(self.file_path, "rb") as f:
                for chunk in iter(lambda: f.read(self.chunk_size), b""):
                    if self.isInterruptionRequested():
                        return
                    hash_md5.update(chunk)
                    processed_size += len(chunk)
                    progress = min(100, int((processed_size / max(file_size, 1)) * 100))

                    # ensure progress only updates in 1% intervals.
                    if progress > last_update:
                        self.progress_updated.emit(progress)
                        last_update = progress

            if not self.isInterruptionRequested():
                self.result = HashResult(md5_hash=hash_md5.hexdigest(), mod=self.mod)
                self.hash_computed.emit(self.result)
        except Exception as exc:
            self.error = str(exc) or type(exc).__name__
            self.failed.emit(self.error)
