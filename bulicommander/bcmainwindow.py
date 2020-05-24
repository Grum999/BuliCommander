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

# Reload or Import
if 'bulicommander.pktk.pktk' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.pktk.pktk'])
else:
    import bulicommander.pktk.pktk

if 'bulicommander.bcmainviewtab' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.bcmainviewtab'])
else:
    import bulicommander.bcmainviewtab

if 'bulicommander.bcpathbar' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.bcpathbar'])
else:
    import bulicommander.bcpathbar




from bulicommander.bcpathbar import (
        BCPathBar
    )

from bulicommander.bcmainviewtab import (
        BCMainViewTab
    )

from bulicommander.pktk.pktk import (
        EInvalidValue
    )


# -----------------------------------------------------------------------------
class BCMainWindow(QMainWindow):
    """Buli Commander main window"""

    dialogShown = pyqtSignal()

    # region: initialisation methods -------------------------------------------

    def __init__(self, uiController, parent=None):
        super(BCMainWindow, self).__init__(parent)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'mainwindow.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__uiController = uiController
        self.__eventCallBack = {}
        self.__highlightedPanel = 0
        self.panels = {
                0: self.mainViewTab0,
                1: self.mainViewTab1
            }


    def initMainView(self):
        """Initialise main view content"""
        @pyqtSlot('QString')
        def panel_HighlightStatusChanged(signalPanel):
            for panelIndex in self.panels:
                if self.panels[panelIndex] == signalPanel:
                    self.__uiController.commandViewHighlightPanel(panelIndex)

        #@pyqtSlot('QString')
        #def panel_TabFilesLayoutChanged(signalPanel):
        #    pass

        #@pyqtSlot('QString')
        #def splitterMainView_Moved(pos, index):
        #    pass

        for panel in self.panels:
            self.splitterMainView.insertWidget(panel, self.panels[panel])

        self.mainViewTab0.highlightedStatusChanged.connect(panel_HighlightStatusChanged)
        self.mainViewTab1.highlightedStatusChanged.connect(panel_HighlightStatusChanged)
        #self.mainViewTab0.tabFilesLayoutChanged.connect(panel_TabFilesLayoutChanged)
        #self.mainViewTab1.tabFilesLayoutChanged.connect(panel_TabFilesLayoutChanged)
        #self.splitterMainView.splitterMoved.connect(splitterMainView_Moved)

    def initMenu(self):
        """Initialise actions for menu defaukt menu"""
        # Menu FILE
        self.actionFolderNew.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileOpen.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileOpenCloseBC.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileOpenAsNewDocument.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileOpenAsNewDocumentCloseBC.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileCopyToOtherPanel.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileMoveToOtherPanel.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileDelete.triggered.connect(self.__actionNotYetImplemented)
        self.actionFileRename.triggered.connect(self.__actionNotYetImplemented)
        self.actionQuit.triggered.connect(self.__uiController.commandQuit)

        # Menu EDIT
        self.actionSelectAll.triggered.connect(self.__actionNotYetImplemented)
        self.actionSelectNone.triggered.connect(self.__actionNotYetImplemented)
        self.actionSelectInvert.triggered.connect(self.__actionNotYetImplemented)
        self.actionSelectRegEx.triggered.connect(self.__actionNotYetImplemented)

        # Menu GO
        self.actionGoUp.triggered.connect(self.__actionNotYetImplemented)
        self.actionGoBack.triggered.connect(self.__actionNotYetImplemented)

        # Menu VIEW
        self.actionViewDetailled.triggered.connect(self.__uiController.commandViewModeDetailled)
        self.actionViewSmallIcon.triggered.connect(self.__uiController.commandViewModeSmallIcon)
        self.actionViewMediumIcon.triggered.connect(self.__uiController.commandViewModeMediumIcon)
        self.actionViewLargeIcon.triggered.connect(self.__uiController.commandViewModeLargeIcon)
        self.actionViewShowImageFileOnly.triggered.connect(self.__uiController.commandViewShowImageFileOnly)
        self.actionViewShowBackupFiles.triggered.connect(self.__uiController.commandViewShowBackupFiles)
        self.actionViewShowHiddenFiles.triggered.connect(self.__uiController.commandViewShowHiddenFiles)
        self.actionViewDisplaySecondaryPanel.triggered.connect(self.__uiController.commandViewDisplaySecondaryPanel)
        self.actionViewSwapPanels.triggered.connect(self.__uiController.commandViewSwapPanels)

        # Menu TOOLS
        self.actionToolsSearch.triggered.connect(self.__actionNotYetImplemented)
        self.actionToolsStatistics.triggered.connect(self.__actionNotYetImplemented)
        self.actionToolsSynchronizePanels.triggered.connect(self.__actionNotYetImplemented)
        self.actionConsole.triggered.connect(self.__actionNotYetImplemented)

        self.actionBCSManageScripts.triggered.connect(self.__actionNotYetImplemented)

        # Menu SETTINGS
        self.actionSettingsPreferences.triggered.connect(self.__actionNotYetImplemented)
        self.actionSettingsResetLayoutToDefault.triggered.connect(self.__uiController.commandSettingsResetLayoutToDefault)

        # Menu HELP
        self.actionHelpAboutBC.triggered.connect(self.__uiController.commandAboutBc)

    # endregion: initialisation methods ----------------------------------------


    # region: define actions method --------------------------------------------
    def __actionNotYetImplemented(self):
        """"Method called when an action not yet implemented is triggered"""
        QMessageBox.warning(
                QWidget(),
                self.__uiController.name(),
                i18n("Sorry! Action has not yet been implemented")
            )

    # endregion: define actions method -----------------------------------------


    # region: events- ----------------------------------------------------------

    def showEvent(self, event):
        """Event trigerred when dialog is shown

           At this time, all widgets are initialised and size/visiblity is known


           Example
           =======
                # define callback function
                def my_callback_function():
                    print("BCMainWindow shown!")

                # initialise a dialog from an xml .ui file
                dlgMain = BCMainWindow.loadUi(uiFileName)

                # execute my_callback_function() when dialog became visible
                dlgMain.dialogShown.connect(my_callback_function)
        """
        super(BCMainWindow, self).showEvent(event)
        self.dialogShown.emit()

    def closeEvent(self, event):
        """Event executed when window is about to be closed"""
        #event.ignore()
        self.__uiController.saveSettings()
        event.accept()

    def eventFilter(self, object, event):
        """Manage event filters for window"""
        if object in self.__eventCallBack.keys():
            return self.__eventCallBack[object](event)

        return super(BCMainWindow, self).eventFilter(object, event)

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
                dlgMain = BCMainWindow.loadUi(uiFileName)

                # define callback for widget from ui
                dlgMain.setEventCallback(dlgMain.my_widget, my_callback_function)
        """
        if object is None:
            return False

        self.__eventCallBack[object] = method
        object.installEventFilter(self)

    # endregion: events --------------------------------------------------------

    # region: methods ----------------------------------------------------------

    def highlightedPanel(self):
        """Return current highlighted panel"""
        return self.__highlightedPanel

    def setHighlightedPanel(self, highlightedPanel):
        """Set current highlighted panel"""
        if not highlightedPanel in self.panels:
            raise EInvalidValue('Given `highlightedPanel` must be 0 or 1')

        self.__highlightedPanel = highlightedPanel

    # endregion: methods -------------------------------------------------------



