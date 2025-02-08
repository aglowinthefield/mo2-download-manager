import os
import sys

from .src.download_manager_plugin import DownloadManagerPlugin
from .src.util import create_logger, logger

lib_dir = os.path.join(os.path.dirname(__file__), "libs")
sys.path.append(lib_dir)

create_logger()

try:
    logger.debug("Attempting to initialize DL manager debugger")
    import pydevd_pycharm
    logger.debug("pydevd_pycharm imported")

    pydevd_pycharm.settrace(
        "localhost",
        port=5678,
        stdoutToServer=True,
        stderrToServer=True,
        suspend=False,
    )
    logger.debug("Debugger started")

except Exception as e:
    logger.debug("Could not start debugger. Continuing.")
    logger.debug(e)

def createPlugin():
    """MO2 init fn. Cant be snake case."""
    return DownloadManagerPlugin()
