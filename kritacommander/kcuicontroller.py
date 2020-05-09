#-----------------------------------------------------------------------------
# Krita Commander
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


from kritacommander.kcmainwindow import (
        KCMainWindow
    )
from kritacommander.kcabout import (
        KCAboutWindow
    )


from PyQt5.QtWidgets import (
        QMessageBox,
        QWidget
    )


# ------------------------------------------------------------------------------
class KCUIController(object):

    def __init__(self, kcName="Krita Commander", kcVersion="testing"):
        self.__window = KCMainWindow(self)
        self.__kcName = kcName
        self.__kcVersion = kcVersion
        self.__kcTitle = "{0} - {1}".format(kcName, kcVersion)


    def start(self):
        self.__initSettings()

        self.__window.setWindowTitle(self.__kcTitle)
        self.__window.show()
        self.__window.activateWindow()


    # region: initialisation methods -------------------------------------------
    def __initSettings(self):
        """Initialise settings"""
        pass

    # endregion: initialisation methods ----------------------------------------


    # region: define commands --------------------------------------------------

    def commandCloseKc(self):
        """Close Krita Commander"""
        self.__window.close()

    def commandAboutKc(self):
        """Display 'About Krita Commander' dialog box"""
        KCAboutWindow(self.__kcName, self.__kcVersion)



    # endregion: define commands -----------------------------------------------
