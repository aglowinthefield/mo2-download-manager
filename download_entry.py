from dataclasses import dataclass
from datetime import datetime
import sys
import os

# Add the 'libs' folder to the system path to allow imports from there
lib_dir = os.path.join(os.path.dirname(__file__), 'libs')
sys.path.append(lib_dir)
import semver

@dataclass
class DownloadEntry:
    selected: bool
    modname: str
    filename: str
    filetime: datetime
    version: semver.Version
    installed: bool