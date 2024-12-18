# pylint:disable=invalid-name
import os
import sys

from .download_manager_plugin import DownloadManagerPlugin
from .util import create_logger

lib_dir = os.path.join(os.path.dirname(__file__), "libs")
sys.path.append(lib_dir)

try:
    import pydevd_pycharm

    pydevd_pycharm.settrace(
        "localhost",
        port=5678,
        stdoutToServer=True,
        stderrToServer=True,
        suspend=False,
    )
    print("Debugger started")
except Exception:
    print("Could not start debugger. Continuing.")


# pylint:disable=invalid-name
def createPlugin():
    """MO2 init fn. Cant be snake case."""
    create_logger()
    return DownloadManagerPlugin()
