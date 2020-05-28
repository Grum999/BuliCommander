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
        QMainWindow
    )


from .bcbookmark import BCBookmark
from .bchistory import BCHistory
from .bcpathbar import BCPathBar
from .bcmainviewtab import BCMainViewTab

from ..pktk.pktk import EInvalidType
from ..pktk.pktk import EInvalidValue
    

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

        self.__fontMono = QFont()
        self.__fontMono.setPointSize(9)
        self.__fontMono.setFamily('DejaVu Sans Mono')

    def initMainView(self):
        """Initialise main view content"""
        @pyqtSlot('QString')
        def panel_HighlightStatusChanged(signalPanel):
            for panelIndex in self.panels:
                if self.panels[panelIndex] == signalPanel:
                    self.__uiController.commandViewHighlightPanel(panelIndex)

        @pyqtSlot('QString')
        def panel_pathChanged(newPath):
            self.__uiController.commandGoHistoryAdd(newPath)

        #@pyqtSlot('QString')
        #def panel_TabFilesLayoutChanged(signalPanel):
        #    pass

        #@pyqtSlot('QString')
        #def splitterMainView_Moved(pos, index):
        #    pass

        for panel in self.panels:
            self.splitterMainView.insertWidget(panel, self.panels[panel])
            self.panels[panel].setUiController(self.__uiController)

        self.mainViewTab0.highlightedStatusChanged.connect(panel_HighlightStatusChanged)
        self.mainViewTab1.highlightedStatusChanged.connect(panel_HighlightStatusChanged)
        self.mainViewTab0.pathChanged.connect(panel_pathChanged)
        self.mainViewTab1.pathChanged.connect(panel_pathChanged)
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
        self.menuGoHistory.aboutToShow.connect(self.__menuHistoryShow)
        self.menuGoHistory.triggered.connect(self.__menuHistory_Clicked)
        self.menuGoBookmark.aboutToShow.connect(self.__menuBookmarkShow)
        self.menuGoBookmark.triggered.connect(self.__menuBookmark_Clicked)

        self.actionGoUp.triggered.connect(self.__menuGoUp_clicked)
        self.actionGoBack.triggered.connect(self.__menuGoBack_clicked)
        self.actionGoHistory_clearHistory.triggered.connect(self.__uiController.commandGoHistoryClear)
        self.actionGoBookmark_clearBookmark.triggered.connect(self.__uiController.commandGoBookmarkClearUI)
        self.actionGoBookmark_addBookmark.triggered.connect(self.__menuBookmarkAppend_clicked)
        self.actionGoBookmark_removeBookmark.triggered.connect(self.__menuBookmarkRemove_clicked)
        self.actionGoBookmark_renameBookmark.triggered.connect(self.__menuBookmarkRename_clicked)

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
        self.actionSettingsSaveSessionOnExit.triggered.connect(self.__uiController.commandSettingsSaveSessionOnExit)
        self.actionSettingsResetSessionToDefault.triggered.connect(self.__uiController.commandSettingsResetSessionToDefault)

        # Menu HELP
        self.actionHelpAboutBC.triggered.connect(self.__uiController.commandAboutBc)


    def __menuHistoryShow(self):
        """Build menu history"""

        self.menuGoHistory.clear()
        self.menuGoHistory.addAction(self.actionGoHistory_clearHistory)
        if not self.__uiController.history() is None and self.__uiController.history().length() > 0:
            self.actionGoHistory_clearHistory.setEnabled(True)
            self.actionGoHistory_clearHistory.setText(i18n(f'Clear history ({self.__uiController.history().length()})'))
            self.menuGoHistory.addSeparator()

            for path in reversed(self.__uiController.history().list()):
                action = QAction(path.replace('&', '&&'), self)
                action.setFont(self.__fontMono)
                action.setProperty('path', path)

                self.menuGoHistory.addAction(action)
        else:
            self.actionGoHistory_clearHistory.setEnabled(False)
            self.actionGoHistory_clearHistory.setText(i18n('Clear history'))

    def __menuBookmarkShow(self):
        """Build menu history"""
        self.menuGoBookmark.clear()
        self.menuGoBookmark.addAction(self.actionGoBookmark_clearBookmark)
        self.menuGoBookmark.addAction(self.actionGoBookmark_addBookmark)
        self.menuGoBookmark.addAction(self.actionGoBookmark_removeBookmark)
        self.menuGoBookmark.addAction(self.actionGoBookmark_renameBookmark)

        if not self.__uiController.bookmark() is None and self.__uiController.bookmark().length() > 0:
            self.actionGoBookmark_clearBookmark.setEnabled(True)
            self.actionGoBookmark_clearBookmark.setText(i18n('Clear bookmark')+f' ({self.__uiController.bookmark().length()})')

            self.menuGoBookmark.addSeparator()

            currentPath = self.panels[self.__highlightedPanel].currentPath()
            isInBookmark = False

            for bookmark in self.__uiController.bookmark().list():
                action = QAction(bookmark[BCBookmark.NAME].replace('&', '&&'), self)
                action.setFont(self.__fontMono)
                action.setProperty('path', bookmark[BCBookmark.VALUE])
                action.setCheckable(True)
                action.setStatusTip(bookmark[BCBookmark.VALUE])

                if currentPath == bookmark[BCBookmark.VALUE]:
                    action.setChecked(True)
                    isInBookmark = True
                else:
                    action.setChecked(False)

                self.menuGoBookmark.addAction(action)

            if isInBookmark:
                self.actionGoBookmark_addBookmark.setEnabled(False)
                self.actionGoBookmark_removeBookmark.setEnabled(True)
                self.actionGoBookmark_renameBookmark.setEnabled(True)
            else:
                self.actionGoBookmark_addBookmark.setEnabled(True)
                self.actionGoBookmark_removeBookmark.setEnabled(False)
                self.actionGoBookmark_renameBookmark.setEnabled(False)
        else:
            self.actionGoBookmark_clearBookmark.setEnabled(False)
            self.actionGoBookmark_clearBookmark.setText(i18n('Clear bookmark'))
            self.actionGoBookmark_addBookmark.setEnabled(True)
            self.actionGoBookmark_removeBookmark.setEnabled(False)
            self.actionGoBookmark_renameBookmark.setEnabled(False)


    # endregion: initialisation methods ----------------------------------------


    # region: define actions method --------------------------------------------
    def __actionNotYetImplemented(self):
        """"Method called when an action not yet implemented is triggered"""
        QMessageBox.warning(
                QWidget(),
                self.__uiController.name(),
                i18n("Sorry! Action has not yet been implemented")
            )

    def __menuHistory_Clicked(self, action):
        """Go to defined directory for current highlighted panel"""
        if not action.property('path') is None:
            # change directory
            self.__uiController.commandPanelPath(self.__highlightedPanel, action.property('path'))

    def __menuBookmark_Clicked(self, action):
        """Go to defined directory for current highlighted panel"""
        if not action.property('path') is None:
            # change directory
            self.__uiController.commandPanelPath(self.__highlightedPanel, action.property('path'))

    def __menuBookmarkAppend_clicked(self, action):
        """Append current path to bookmark"""
        self.__uiController.commandGoBookmarkAppendUI(self.panels[self.__highlightedPanel].currentPath())

    def __menuBookmarkRemove_clicked(self, action):
        """Remove bookmark"""
        name = self.__uiController.bookmark().nameFromValue(self.panels[self.__highlightedPanel].currentPath())
        self.__uiController.commandGoBookmarkRemoveUI(name)

    def __menuBookmarkRename_clicked(self, action):
        """Rename bookmark"""
        name = self.__uiController.bookmark().nameFromValue(self.panels[self.__highlightedPanel].currentPath())
        self.__uiController.commandGoBookmarkRenameUI(name)

    def __menuGoUp_clicked(self, action):
        """Go to parent directory"""
        self.__uiController.commandGoUp(self.__highlightedPanel)

    def __menuGoBack_clicked(self, action):
        """Go to previous directory"""
        self.__uiController.commandGoBack(self.__highlightedPanel)

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



