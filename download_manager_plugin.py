import mobase

from .download_manager_window import DownloadManagerWindow

try:
    import PyQt6.QtGui as QtGui
except ImportError:
    import PyQt5.QtGui as QtGui


class DownloadManagerPlugin(mobase.IPluginTool):

    NAME = "Download Manager"
    DESCRIPTION = "Cleans up large downloads folders. Better description TODO."

    __organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()
        self.__window = None

    def init(self, organizer: mobase.IOrganizer):
        self.__organizer = organizer
        self.__window = DownloadManagerWindow(self.__organizer)
        return True

    def display(self):
        self.__window.init()
        self.__window.setWindowTitle(f"{self.NAME} v{self.version().displayString()}")
        self.__window.exec()

    # pylint:disable=invalid-name
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
        return []

    def version(self):
        return mobase.VersionInfo(1, 0, 0)
