import os
import sys

from .plugin.download_manager_plugin import DownloadManagerPlugin
from .util.util import create_logger, logger

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
    logger.info("Debugger started")
except Exception as e:
    logger.info("Could not start debugger. Continuing.")
    logger.error(e)


def createPlugin():
    """MO2 init fn. Cant be snake case."""
    return DownloadManagerPlugin()
