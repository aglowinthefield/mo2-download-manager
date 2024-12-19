import hashlib
from pathlib import Path

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:
    from PyQt5.QtCore import QThread, pyqtSignal


class HashWorker(QThread):
    progress_updated = pyqtSignal(int)
    hash_computed = pyqtSignal(str)

    def __init__(self, file_path, chunk_size=1024):
        super().__init__()
        self.file_path = file_path
        self.chunk_size = chunk_size

    def run(self):
        try:
            file_size = Path(self.file_path).stat().st_size
            processed_size = 0
            hash_md5 = hashlib.md5()

            with open(self.file_path, "rb") as f:
                for chunk in iter(lambda: f.read(self.chunk_size), b""):
                    hash_md5.update(chunk)
                    processed_size += len(chunk)
                    progress = int((processed_size / file_size) * 100)
                    self.progress_updated.emit(progress)

            self.hash_computed.emit(hash_md5.hexdigest())
        except Exception as e:
            self.hash_computed.emit(f"Error: {e}")