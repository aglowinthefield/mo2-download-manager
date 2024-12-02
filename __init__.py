import os
import sys
from .download_manager_plugin import DownloadManagerPlugin
from .util import create_logger

# Add the 'libs' folder to the system path to allow imports from there
lib_dir = os.path.join(os.path.dirname(__file__), 'libs')
sys.path.append(lib_dir)
import pydevd_pycharm

try:
    pydevd_pycharm.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=True)
except Exception:
    pass

def createPlugin():
    create_logger()
    return DownloadManagerPlugin()