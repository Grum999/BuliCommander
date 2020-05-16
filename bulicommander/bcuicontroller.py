#-----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2020 - Grum999
# -----------------------------------------------------------------------------
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.
# If not, see https://www.gnu.org/licenses/
# -----------------------------------------------------------------------------
# A Krita plugin designed to manage documents
# -----------------------------------------------------------------------------


from bulicommander.bcmainwindow import (
        BCMainWindow
    )
from bulicommander.bcabout import (
        BCAboutWindow
    )


from PyQt5.QtWidgets import (
        QMessageBox,
        QWidget
    )


# ------------------------------------------------------------------------------
class BCUIController(object):

    def __init__(self, bcName="Buli Commander", bcVersion="testing"):
        self.__window = BCMainWindow(self)
        self.__bcName = bcName
        self.__bcVersion = bcVersion
        self.__bcTitle = "{0} - {1}".format(bcName, bcVersion)


    def start(self):
        self.__initSettings()

        self.__window.setWindowTitle(self.__bcTitle)
        self.__window.show()
        self.__window.activateWindow()


    # region: initialisation methods -------------------------------------------

    def __initSettings(self):
        """Initialise settings"""
        pass

    # endregion: initialisation methods ----------------------------------------

    # region: getter/setters ---------------------------------------------------

    def name(self):
        """Return name"""
        return self.__bcName


    # endregion: getter/setters ------------------------------------------------


    # region: define commands --------------------------------------------------

    def commandCloseBc(self):
        """Close Buli Commander"""
        self.__window.close()

    def commandAboutBc(self):
        """Display 'About Buli Commander' dialog box"""
        BCAboutWindow(self.__bcName, self.__bcVersion)



    # endregion: define commands -----------------------------------------------
