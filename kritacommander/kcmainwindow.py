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




# -----------------------------------------------------------------------------
#from .pktk import PkTk

import krita
import os
import re
import sys
import time

import PyQt5.uic

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal
    )
from PyQt5.QtWidgets import (
        QDialog,
        QMainWindow
    )


# -----------------------------------------------------------------------------
class KCMainWindow(QMainWindow):
    """KritaCommander main window"""

    dialogShown = pyqtSignal()

    def __init__(self, uiController, parent=None):
        super(KCMainWindow, self).__init__(parent)

        self.__uiController = uiController
        self.__eventCallBack = {}

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'mainwindow.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        print('init menu a1')
        self.__initMenu()
        print('init menu a2')

    def showEvent(self, event):
        """Event trigerred when dialog is shown

           At this time, all widgets are initialised and size/visiblity is known


           Example
           =======
                # define callback function
                def my_callback_function():
                    print("KCMainWindow shown!")

                # initialise a dialog from an xml .ui file
                dlgMain = KCMainWindow.loadUi(uiFileName)

                # execute my_callback_function() when dialog became visible
                dlgMain.dialogShown.connect(my_callback_function)
        """
        super(KCMainWindow, self).showEvent(event)
        self.dialogShown.emit()

    def eventFilter(self, object, event):
        """Manage event filters for window"""
        if object in self.__eventCallBack.keys():
            return self.__eventCallBack[object](event)

        return super(KCMainWindow, self).eventFilter(object, event)

    def setEventCallback(self, object, method):
        """Add an event callback method for given object

           Example
           =======
                # define callback function
                def my_callback_function(event):
                    if event.type() == QEvent.xxxx:
                        print("Event!")
                        return True
                    return False


                # initialise a dialog from an xml .ui file
                dlgMain = KCMainWindow.loadUi(uiFileName)

                # define callback for widget from ui
                dlgMain.setEventCallback(dlgMain.my_widget, my_callback_function)
        """
        if object is None:
            return False

        self.__eventCallBack[object] = method
        object.installEventFilter(self)





    # region: initialisation methods -------------------------------------------
    def __initMenu(self):
        print('init menu b1')
        """Initialise actions for menu defaukt menu"""
        # Menu FILE
        self.actionFolderNew.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileOpen.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileOpenCloseKC.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileCopyToOtherPanel.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileMoveToOtherPanel.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileDelete.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileRename.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileToArchive.triggered.connect(self.__actionNotYetImplemented)
        self.actionQuit.triggered.connect(self.__actionQuit)
        print('self.actionQuit', self.actionQuit)

        # Menu EDIT
        self.actionSelectAll.triggered.connect(self.__actionNotYetImplemented)
        self.actionSelectNone.triggered.connect(self.__actionNotYetImplemented)
        self.actionSelectInvert.triggered.connect(self.__actionNotYetImplemented)
        self.actionSelectRegEx.triggered.connect(self.__actionNotYetImplemented)

        # Menu GO
        self.actionGoUp.triggered.connect(self.__actionNotYetImplemented)
        self.actionGoBack.triggered.connect(self.__actionNotYetImplemented)

        # Menu VIEW
        self.actionViewDetailled.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewSmallIcon.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewMediumIcon.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewLargeIcon.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewShowImageFileOnly.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewShowBackupFiles.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewShowHiddenFiles.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewDisplayLeftSidebar.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewDisplayRightSidebar.triggered.connect(self.__actionNotYetImplemented)
        self.actionViewSwapPanels.triggered.connect(self.__actionNotYetImplemented)

        # Menu TOOLS
        self.actionToolsSearch.triggered.connect(self.__actionNotYetImplemented)
        self.actionToolsStatistics.triggered.connect(self.__actionNotYetImplemented)
        self.actionToolsSynchronizePanels.triggered.connect(self.__actionNotYetImplemented)
        self.actionConsole.triggered.connect(self.__actionNotYetImplemented)

        self.actionKCSManageScripts.triggered.connect(self.__actionNotYetImplemented)

        # Menu SETTINGS
        self.actionSettingsPreferences.triggered.connect(self.__actionNotYetImplemented)

        # Menu HELP
        self.actionHelpAboutKC.triggered.connect(self.__actionHelpAboutKC)
        print('init menu b2')

    # endregion: initialisation methods ----------------------------------------



    # region: define actions method --------------------------------------------
    def __actionNotYetImplemented(self):
        """"Method called when an action not yet implemented is triggered"""
        QMessageBox.warning(
                QWidget(),
                self.__kcName,
                i18n("Sorry! Action has not yet been implemented")
            )

    def __actionQuit(self):
        """Close KritaCommander"""
        print('quit', self.__uiController)
        self.__uiController.commandCloseKc()

    def __actionHelpAboutKC(self):
        """Display 'About Krita Commander' dialog box"""
        self.__uiController.commandAboutKc()

    # endregion: define actions method -----------------------------------------


