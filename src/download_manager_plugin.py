import mobase

from .download_manager_window import DownloadManagerWindow
from .util import logger

try:
    import PyQt6.QtGui as QtGui
except ImportError:
    import PyQt5.QtGui as QtGui

# import cProfile
# import pstats


# class Profiler:
#     def __init__(self, profile_filename='profile.prof'):
#         self.profiler = cProfile.Profile()
#         self.profile_filename = profile_filename
#
#     def start(self):
#         self.profiler.enable()
#
#     def stop(self):
#         self.profiler.disable()
#         self.save()
#
#     def save(self):
#         stats = pstats.Stats(self.profiler)
#         stats.sort_stats(pstats.SortKey.TIME)
#         stats.dump_stats(self.profile_filename)


class DownloadManagerPlugin(mobase.IPluginTool):

    NAME = "Download Manager"
    DESCRIPTION = "Cleans up large downloads folders. Better description TODO."

    __organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()
        logger.info("DownloadManagerPlugin.__init__")
        self.__window = None

    def init(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__window = DownloadManagerWindow(self.__organizer)
        return True

    def display(self):
        # profiler = Profiler()
        #
        # # Start profiling
        # profiler.start()

        self.__window.init()
        self.__window.setWindowTitle(f"{self.NAME} v{self.version().displayString()}")
        self.__window.show()

        # profiler.stop()

    def displayName(self):
        return self.NAME

    def icon(self):
        return QtGui.QIcon()

    def tooltip(self):
        return self.DESCRIPTION

    def author(self):
        return "aglowinthefield"

    def description(self):
        return self.DESCRIPTION

    def name(self):
        return self.NAME

    def settings(self):
        return [
            mobase.PluginSetting("nexusApiKey", "Nexus API Key", ""),
            mobase.PluginSetting(
                "columnVisibility", "Download table column visibility (managed automatically).", "[]"
            ),
            mobase.PluginSetting(
                "columnOrder", "Download table column order (managed automatically).", "[]"
            ),
            mobase.PluginSetting(
                "alternateRowColors", "Use alternating row colors in the download table.", True
            ),
        ]

    def version(self):
        return mobase.VersionInfo(1, 0, 0)
