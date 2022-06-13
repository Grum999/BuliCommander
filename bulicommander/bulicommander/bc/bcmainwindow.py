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

import krita
import os
import re
import sys
import time

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal
    )
from PyQt5.QtWidgets import (
        QMainWindow
    )

from .bcbookmark import BCBookmark
from .bchistory import BCHistory
from .bcwpathbar import BCWPathBar
from .bcmainviewtab import (BCMainViewTab, BCMainViewTabFilesLayout, BCMainViewTabTabs)

from bulicommander.pktk.modules.utils import loadXmlUi
from bulicommander.pktk.modules.imgutils import buildIcon
from bulicommander.pktk.widgets.wiodialog import WDialogMessage
from bulicommander.pktk.widgets.wmenuitem import (
        WMenuSlider,
        WMenuTitle
    )
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )



# -----------------------------------------------------------------------------
class BCMainWindow(QMainWindow):
    """Buli Commander main window"""

    DARK_THEME = 'dark'
    LIGHT_THEME = 'light'

    dialogShown = pyqtSignal()

    # region: initialisation methods -------------------------------------------

    def __init__(self, uiController, parent=None):
        super(BCMainWindow, self).__init__(parent)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'mainwindow.ui')
        loadXmlUi(uiFileName, self)

        self.__uiController = uiController
        self.__eventCallBack = {}
        self.__highlightedPanel = 0
        self.actionViewLayoutIconSize=None
        self.panels = {
                0: self.mainViewTab0,
                1: self.mainViewTab1
            }

        self.__toolbars=[]

        self.__fontMono = QFont()
        self.__fontMono.setPointSize(9)
        self.__fontMono.setFamily('DejaVu Sans Mono, Consolas, Courier New')

        self.setStyleSheet("""
            QToolBar { border-width: 0px; }
            QToolBar QToolButton:checked {
                    background-color: palette(Highlight);
                }

            /* QMenu::icon ==> doesn't work?? */
            QMenu::item:checked:enabled {
                    background-color: palette(Highlight);
                }
        """)

        for panelId in self.panels:
            self.panels[panelId].setAllowRefresh(False)


    #def event(self, event):
    #    if event.type() == QEvent.ApplicationPaletteChange:
    #        # ...works...
    #        # or not :)
    #        # event if triggerred nbut icons are not reloaded
    #        self.__loadResources()
    #    return super(BCMainWindow, self).event(event)

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

        for panel in self.panels:
            self.splitterMainView.insertWidget(panel, self.panels[panel])
            self.panels[panel].setUiController(self.__uiController)

        self.mainViewTab0.highlightedStatusChanged.connect(panel_HighlightStatusChanged)
        self.mainViewTab1.highlightedStatusChanged.connect(panel_HighlightStatusChanged)
        self.mainViewTab0.filesPathChanged.connect(panel_pathChanged)
        self.mainViewTab1.filesPathChanged.connect(panel_pathChanged)
        self.actionFileCopyToOtherPanelNoConfirm = QShortcut(QKeySequence("Shift+F5"), self)
        self.actionFileMoveToOtherPanelNoConfirm = QShortcut(QKeySequence("Shift+F6"), self)
        self.actionFileDeleteNoConfirm = QShortcut(QKeySequence("Shift+F8"), self)

    def initMenu(self):
        """Initialise actions for menu default menu"""
        def updatePixelSize(value):
            if self.__uiController.panel().tabActive()==BCMainViewTabTabs.FILES:
                if self.__uiController.panel().filesTabViewMode()==BCMainViewTab.VIEWMODE_TV:
                    self.__uiController.panel().setFilesIconSizeTv(value)
                    iconPixelSize=self.__uiController.panel().filesIconSizeTv(True)
                else:
                    self.__uiController.panel().setFilesIconSizeLv(value)
                    iconPixelSize=self.__uiController.panel().filesIconSizeLv(True)
            elif self.__uiController.panel().tabActive()==BCMainViewTabTabs.CLIPBOARD:
                self.__uiController.panel().setClipboardIconSize(value)
                iconPixelSize=self.__uiController.panel().clipboardIconSize(True)
            else:
                return

            self.actionViewLayoutIconSize.setLabelText(i18n(f"Thumbnail size: {iconPixelSize}px"))

        # Menu FILE
        self.actionFolderNew.triggered.connect(self.__menuFileCreateDirectory)
        self.actionFileOpen.triggered.connect(self.__menuFileOpen)
        self.actionFileOpenAsNewDocument.triggered.connect(self.__menuFileOpenAsNewDocument)
        self.actionFileOpenAsImageReference.triggered.connect(self.__menuFileOpenAsImageReference)
        self.actionFileOpenAsLayer.triggered.connect(self.__menuFileOpenAsLayer)
        self.actionFileOpenAsFileLayer.triggered.connect(self.__menuFileOpenAsFileLayer)
        self.actionFileCopyToOtherPanel.triggered.connect(self.__menuFileCopyConfirm)
        self.actionFileMoveToOtherPanel.triggered.connect(self.__menuFileMoveConfirm)
        self.actionFileRename.triggered.connect(self.__menuFileRename)
        self.actionFileDelete.triggered.connect(self.__menuFileDeleteConfirm)
        self.actionFileQuit.triggered.connect(self.__uiController.commandQuit)

        # Menu CLIPBPOARD
        self.actionClipboardCheckContent.triggered.connect(self.__menuClipboardCheckContent)
        self.actionClipboardPushBack.triggered.connect(self.__menuClipboardPushBackClipboard)
        self.actionClipboardPasteAsNewLayer.triggered.connect(self.__menuClipboardPasteAsNewLayer)
        self.actionClipboardPasteAsNewDocument.triggered.connect(self.__menuClipboardPasteAsNewDocument)
        self.actionClipboardPasteAsRefImage.triggered.connect(self.__menuClipboardPasteAsRefImage)
        self.actionClipboardOpen.triggered.connect(self.__menuClipboardOpen)
        self.actionClipboardSetPersistent.triggered.connect(self.__menuClipboardSetPersistent)
        self.actionClipboardSetNotPersistent.triggered.connect(self.__menuClipboardSetNotPersistent)
        self.actionClipboardStartDownload.triggered.connect(self.__menuClipboardStartDownload)
        self.actionClipboardStopDownload.triggered.connect(self.__menuClipboardStopDownload)
        self.actionClipboardQuit.triggered.connect(self.__uiController.commandQuit)

        # Menu EDIT
        self.actionMenuEditSelectAll.triggered.connect(self.__menuEditSelectAll_clicked)
        self.actionMenuEditSelectNone.triggered.connect(self.__menuEditSelectNone_clicked)
        self.actionMenuEditSelectInvert.triggered.connect(self.__menuEditSelectInvert_clicked)
        self.actionMenuEditSelectMarked.triggered.connect(self.__menuEditSelectMarked_clicked)

        self.actionMenuEditMarkUnmark.triggered.connect(self.__menuEditMarkUnmark_clicked)
        self.actionMenuEditMarkAll.triggered.connect(self.__menuEditMarkAll_clicked)
        self.actionMenuEditMarkNone.triggered.connect(self.__menuEditMarkNone_clicked)
        self.actionMenuEditMarkInvert.triggered.connect(self.__menuEditMarkInvert_clicked)

        # Menu GO
        self.actionGoHome.triggered.connect(self.__menuGoHome_clicked)
        self.actionGoUp.triggered.connect(self.__menuGoUp_clicked)
        self.actionGoBack.triggered.connect(self.__menuGoBack_clicked)

        self.actionGoHistoryClearHistory.triggered.connect(self.__uiController.commandGoHistoryClearUI)

        self.actionGoBookmarksClearBookmarks.triggered.connect(self.__uiController.commandGoBookmarkClearUI)
        self.actionGoBookmarksAddBookmark.triggered.connect(lambda: self.__uiController.commandGoBookmarkAppendUI(self.__uiController.panel().filesPath()))
        self.actionGoBookmarksRemoveFromBookmark.triggered.connect(lambda: self.__uiController.commandGoBookmarkRemoveUI(self.__uiController.bookmark().nameFromValue(self.__uiController.panel().filesPath())))
        self.actionGoBookmarksRenameBookmark.triggered.connect(lambda: self.__uiController.commandGoBookmarkRenameUI(self.__uiController.bookmark().nameFromValue(self.__uiController.panel().filesPath())))

        self.actionGoSavedViewsAddToViewNewView.triggered.connect(lambda: self.__uiController.commandGoSavedViewCreateUI([file.fullPathName() for file in self.__uiController.panel().filesSelected()[0]]))
        self.actionGoSavedViewsClearViewContent.triggered.connect(lambda: self.__uiController.commandGoSavedViewClearUI(self.__uiController.savedViews().current(True)))
        self.actionGoSavedViewsRemoveFromView.triggered.connect(lambda: self.__uiController.commandGoSavedViewRemoveUI(self.__uiController.savedViews().current(True), [file.fullPathName() for file in self.__uiController.panel().filesSelected()[5]]))
        self.actionGoSavedViewsRenameView.triggered.connect(lambda: self.__uiController.commandGoSavedViewRenameUI(self.__uiController.savedViews().current(True)))
        self.actionGoSavedViewsDeleteView.triggered.connect(lambda: self.__uiController.commandGoSavedViewDeleteUI(self.__uiController.savedViews().current(True)))

        self.actionGoLastDocumentsLastDocuments.triggered.connect(lambda: self.__uiController.commandGoTo(self.__uiController.panelId(), '@last'))
        self.actionGoLastDocumentsLastOpenedDocuments.triggered.connect(lambda: self.__uiController.commandGoTo(self.__uiController.panelId(), '@last opened'))
        self.actionGoLastDocumentsLastSavedDocuments.triggered.connect(lambda: self.__uiController.commandGoTo(self.__uiController.panelId(), '@last saved'))

        # Menu VIEW
        self.actionViewThumbnail.triggered.connect(self.__menuViewThumbnail_clicked)
        self.actionViewShowImageFileOnly.triggered.connect(self.__menuViewShowImageFileOnly_clicked)
        self.actionViewShowBackupFiles.triggered.connect(self.__menuViewShowBackupFiles_clicked)
        self.actionViewShowHiddenFiles.triggered.connect(self.__menuViewShowHiddenFiles_clicked)
        self.actionViewDisplaySecondaryPanel.triggered.connect(self.__uiController.commandViewDisplaySecondaryPanel)
        self.actionViewDisplayQuickFilter.triggered.connect(self.__menuViewDisplayQuickFilter_clicked)
        self.actionViewSwapPanels.triggered.connect(self.__uiController.commandViewSwapPanels)

        # implemented into BCUIController.updateMenuForPanel()
        #self.actionViewLayoutFullMode.triggered.connect()
        #self.actionViewLayoutTopBottom.triggered.connect()
        #self.actionViewLayoutLeftRight.triggered.connect()
        #self.actionViewLayoutBottomTop.triggered.connect()
        #self.actionViewLayoutRightLeft.triggered.connect()

        self.actionViewLayoutViewAsList.triggered.connect(lambda: self.__uiController.commandPanelFilesTabViewMode(self.__uiController.panelId(), BCMainViewTab.VIEWMODE_TV ))
        self.actionViewLayoutViewAsGrid.triggered.connect(lambda: self.__uiController.commandPanelFilesTabViewMode(self.__uiController.panelId(), BCMainViewTab.VIEWMODE_LV ))

        groupViewLayout=QActionGroup(self)
        groupViewLayout.addAction(self.actionViewLayoutFullMode)
        groupViewLayout.addAction(self.actionViewLayoutTopBottom)
        groupViewLayout.addAction(self.actionViewLayoutLeftRight)
        groupViewLayout.addAction(self.actionViewLayoutBottomTop)
        groupViewLayout.addAction(self.actionViewLayoutRightLeft)
        groupViewLayout.setExclusive(True)

        self.actionViewLayoutFullMode.setData(i18n("Layout:"))
        self.actionViewLayoutTopBottom.setData(i18n("Layout:"))
        self.actionViewLayoutLeftRight.setData(i18n("Layout:"))
        self.actionViewLayoutBottomTop.setData(i18n("Layout:"))
        self.actionViewLayoutRightLeft.setData(i18n("Layout:"))

        groupViewMode=QActionGroup(self)
        groupViewMode.addAction(self.actionViewLayoutViewAsList)
        groupViewMode.addAction(self.actionViewLayoutViewAsGrid)
        groupViewMode.setExclusive(True)


        self.actionViewLayoutIconSize = WMenuSlider(i18n("Thumbnail size"), self)
        self.actionViewLayoutIconSize.setText(i18n("Thumbnail size"))
        self.actionViewLayoutIconSize.setIcon(buildIcon("pktk:tune_img_slider"))
        self.actionViewLayoutIconSize.setObjectName("actionViewLayoutIconSize")
        self.actionViewLayoutIconSize.slider().setMinimum(0)
        self.actionViewLayoutIconSize.slider().setMaximum(8)
        self.actionViewLayoutIconSize.slider().setPageStep(1)
        self.actionViewLayoutIconSize.slider().setSingleStep(1)
        self.actionViewLayoutIconSize.slider().valueChanged.connect(updatePixelSize)
        self.menuViewLayout.addAction(self.actionViewLayoutIconSize)

        # Menu TOOLS
        self.actionToolsCopyToClipboard.triggered.connect(self.__menuToolsCopyToClipboard_clicked)
        self.actionToolsSearch.triggered.connect(self.__menuToolsSearchFiles_clicked)
        self.actionToolsExportFiles.triggered.connect(self.__menuToolsExportFiles_clicked)
        self.actionToolsConvertFiles.triggered.connect(self.__menuToolsConvertFiles_clicked)

        # Menu SETTINGS
        self.actionSettingsPreferences.triggered.connect(self.__uiController.commandSettingsOpen)
        self.actionSettingsSaveSessionOnExit.triggered.connect(self.__uiController.commandSettingsSaveSessionOnExit)
        self.actionSettingsResetSessionToDefault.triggered.connect(self.__uiController.commandSettingsResetSessionToDefault)
        self.menuSettingsToolbars.aboutToShow.connect(self.__menuSettingsToolbarsShow)

        # Menu HELP
        self.actionHelpAboutBC.triggered.connect(self.__uiController.commandHelpAboutBc)
        self.actionHelpManagedFilesFormats.triggered.connect(self.__uiController.commandHelpManagedFilesFormat)

        self.actionFileCopyToOtherPanelNoConfirm.activated.connect(self.__menuFileCopyNoConfirm)
        self.actionFileMoveToOtherPanelNoConfirm.activated.connect(self.__menuFileMoveNoConfirm)
        self.actionFileDeleteNoConfirm.activated.connect(self.__menuFileDeleteNoConfirm)

    def initToolbar(self, toolbarsConfig, toolbarsSession=None):
        """Initialise toolbars

        Given `toolbars` is a list of dictionary
        Each dictionary contains at least the following keys:
            id: toolbar id
            label : toolbar label
            actions: list of QAction id

        Can additionally contains:
            visible: toolbar is visible or hidden
            area: area in which toolbar is docked
            rect: position+size of toolbar
        """
        def sortToolbar(toolbarSessionDef):

            if toolbarSessionDef['area'] in (Qt.LeftToolBarArea, Qt.RightToolBarArea):
                return f"{toolbarSessionDef['area']:02}{toolbarSessionDef['rect'][0]:05}{toolbarSessionDef['rect'][1]:05}"
            else:
                return f"{toolbarSessionDef['area']:02}{toolbarSessionDef['rect'][1]:05}{toolbarSessionDef['rect'][0]:05}"

        # Disable window updates while preparing content (avoid flickering effect)
        self.setUpdatesEnabled(False)

        for toolbar in self.toolbarList():
            self.removeToolBar(toolbar)
        self.__toolbars=[]

        # sort toolbar by area/position
        sortedId=[]
        if not toolbarsSession is None:
            toolbarsSession.sort(key=sortToolbar)

            tmp={toolbarDefinition['id']: toolbarDefinition for toolbarDefinition in toolbarsConfig}
            toolbarsConfigSorted=[]
            for toolbarId in [toolbarSession['id'] for toolbarSession in toolbarsSession]:
                if toolbarId in tmp:
                    toolbarsConfigSorted.append(tmp.pop(toolbarId))

            for toolbarDefinition in toolbarsConfig:
                if toolbarDefinition['id'] in tmp:
                    toolbarsConfigSorted.append(toolbarDefinition)

            toolbarsConfig=toolbarsConfigSorted

        for toolbarDefinition in toolbarsConfig:
            toolbar = self.addToolBar(toolbarDefinition['label'])
            toolbar.setObjectName(toolbarDefinition['id'])
            toolbar.setToolButtonStyle(1)
            toolbar.setToolButtonStyle(toolbarDefinition['style'])
            toolbar.setFloatable(False)
            for action in toolbarDefinition['actions']:
                if action=='ba32b31ff4730cbf42ba0962f981407bcb4e9c58': # separator Id
                    toolbar.addSeparator()
                else:
                    foundAction=self.findChild(QAction, action, Qt.FindChildrenRecursively)
                    if foundAction:
                        toolbar.addAction(foundAction)
            self.__toolbars.append(toolbar)

        if not toolbarsSession is None:
            for toolbarSession in toolbarsSession:
                for toolbar in self.__toolbars:
                    if toolbar.objectName()==toolbarSession['id']:
                        if toolbarSession['break']:
                            self.addToolBarBreak(toolbarSession['area'])
                        self.addToolBar(toolbarSession['area'], toolbar)
                        geometry=toolbarSession['rect']
                        toolbar.setVisible(toolbarSession['visible'])
                        # not working...?
                        #toolbar.setGeometry(geometry[0], geometry[1], geometry[2], geometry[3])
                        break

        self.menuSettingsToolbars.setEnabled(len(self.__toolbars)>0)
        self.setUpdatesEnabled(True)

    def toolbarList(self):
        """Return list of toolbar"""
        return self.__toolbars

    def __menuSettingsToolbarsToggled(self, value):
        """A toolbar Sub-menu checkedbox has been changed"""
        action=self.sender()
        action.data().setVisible(value)

    def __menuSettingsToolbarsShow(self):
        """Display toolbar menu"""
        self.menuSettingsToolbars.clear()

        for toolbar in self.__toolbars:
            action=self.menuSettingsToolbars.addAction(toolbar.windowTitle())
            action.setCheckable(True)
            action.setChecked(toolbar.isVisible())
            action.setData(toolbar)
            action.toggled.connect(self.__menuSettingsToolbarsToggled)


    # endregion: initialisation methods ----------------------------------------


    # region: define actions method --------------------------------------------

    def __actionNotYetImplemented(self, v=None):
        """"Method called when an action not yet implemented is triggered"""
        WDialogMessage.display(
                self.__uiController.name(),
                i18n(f"Sorry! Action has not yet been implemented ({v})")
            )

    def __menuFileOpen(self, action):
        """Open selected file(s)"""
        self.__uiController.commandFileOpen()

    def __menuFileCreateDirectory(self, action):
        """Create a new directory"""
        self.__uiController.commandFileCreateDir()

    def __menuFileOpenAsNewDocument(self, action):
        """Open selected file(s) as new document"""
        self.__uiController.commandFileOpenAsNew()

    def __menuFileOpenAsImageReference(self, action):
        """Open selected file(s) as image reference"""
        self.__uiController.commandFileOpenAsImageReference()

    def __menuFileOpenAsLayer(self, action):
        """Open selected file(s) as layer"""
        self.__uiController.commandFileOpenAsLayer()

    def __menuFileOpenAsFileLayer(self, action):
        """Open selected file(s) as file layer"""
        self.__uiController.commandFileOpenAsFileLayer()

    def __menuFileDeleteConfirm(self, action):
        """Delete file after confirmation"""
        self.__uiController.commandFileDelete(True)

    def __menuFileDeleteNoConfirm(self):
        """Delete file without confirmation"""
        self.__uiController.commandFileDelete(False)

    def __menuFileCopyConfirm(self, action):
        """Copy file after confirmation"""
        self.__uiController.commandFileCopy(True)

    def __menuFileCopyNoConfirm(self):
        """Copy file without confirmation"""
        self.__uiController.commandFileCopy(False)

    def __menuFileMoveConfirm(self, action):
        """Move file after confirmation"""
        self.__uiController.commandFileMove(True)

    def __menuFileMoveNoConfirm(self):
        """Move file without confirmation"""
        self.__uiController.commandFileMove(False)

    def __menuFileRename(self):
        """Rename file(s)"""
        self.__uiController.commandFileRename()

    def __menuClipboardCheckContent(self):
        """Check clipboard content manually"""
        self.__uiController.commandClipboardCheckContent()

    def __menuClipboardPushBackClipboard(self):
        """Push back content to clipboard"""
        self.__uiController.commandClipboardPushBackClipboard()

    def __menuClipboardPasteAsNewLayer(self):
        """Paste content as new layer"""
        self.__uiController.commandClipboardPasteAsNewLayer()

    def __menuClipboardPasteAsNewDocument(self):
        """Paste content as new document"""
        self.__uiController.commandClipboardPasteAsNewDocument()

    def __menuClipboardPasteAsRefImage(self):
        """Paste content as reference image"""
        self.__uiController.commandClipboardPasteAsRefImage()

    def __menuClipboardOpen(self):
        """Open document"""
        self.__uiController.commandClipboardOpen()

    def __menuClipboardSetPersistent(self):
        """Set clipboard item persistent"""
        self.__uiController.commandClipboardSetPersistent(None, True)

    def __menuClipboardSetNotPersistent(self):
        """Set clipboard item not persistent"""
        self.__uiController.commandClipboardSetPersistent(None, False)

    def __menuClipboardStartDownload(self):
        """Start download for selected items"""
        self.__uiController.commandClipboardStartDownload()

    def __menuClipboardStopDownload(self):
        """Stop download for selected items"""
        self.__uiController.commandClipboardStopDownload()

    def __menuEditSelectAll_clicked(self, action):
        """Select all files"""
        self.__uiController.commandPanelSelectAll(self.__highlightedPanel)

    def __menuEditSelectNone_clicked(self, action):
        """Select no files"""
        self.__uiController.commandPanelSelectNone(self.__highlightedPanel)

    def __menuEditSelectInvert_clicked(self, action):
        """Select inverted"""
        self.__uiController.commandPanelSelectInvert(self.__highlightedPanel)

    def __menuEditSelectMarked_clicked(self, action):
        """Select inverted"""
        self.__uiController.commandPanelSelectMarked(self.__highlightedPanel)

    def __menuEditMarkUnmark_clicked(self, action):
        """Select all files"""
        self.__uiController.commandPanelMarkUnmark(self.__highlightedPanel)

    def __menuEditMarkAll_clicked(self, action):
        """Select all files"""
        self.__uiController.commandPanelMarkAll(self.__highlightedPanel)

    def __menuEditMarkNone_clicked(self, action):
        """Select no files"""
        self.__uiController.commandPanelMarkNone(self.__highlightedPanel)

    def __menuEditMarkInvert_clicked(self, action):
        """Select inverted"""
        self.__uiController.commandPanelMarkInvert(self.__highlightedPanel)

    def __menuGoHome_clicked(self, action):
        """Go to home directory"""
        self.__uiController.commandGoHome(self.__highlightedPanel)

    def __menuGoUp_clicked(self, action):
        """Go to parent directory"""
        self.__uiController.commandGoUp(self.__highlightedPanel)

    def __menuGoBack_clicked(self, action):
        """Go to previous directory"""
        self.__uiController.commandGoBack(self.__highlightedPanel)

    def __menuViewThumbnail_clicked(self, action):
        """Set view mode as icon"""
        self.__uiController.commandViewThumbnail(self.__highlightedPanel, action)

    def __menuViewDisplayQuickFilter_clicked(self, action):
        """Display/hide quick filter for panel"""
        self.__uiController.commandViewDisplayQuickFilter(self.__highlightedPanel, action)

    def __menuViewShowImageFileOnly_clicked(self, action):
        """Display readable file only"""
        self.__uiController.commandViewShowImageFileOnly()

    def __menuViewShowBackupFiles_clicked(self, action):
        """Display backup files"""
        self.__uiController.commandViewShowBackupFiles()

    def __menuViewShowHiddenFiles_clicked(self, action):
        """Display hidden files"""
        self.__uiController.commandViewShowHiddenFiles()

    def __menuToolsCopyToClipboard_clicked(self, action):
        """Copy current selected items to clipboard"""
        self.__uiController.commandToolsListToClipboard()

    def __menuToolsExportFiles_clicked(self, action):
        """Open export file list tool"""
        self.__uiController.commandToolsExportFilesOpen()

    def __menuToolsConvertFiles_clicked(self, action):
        """Open convert file tool"""
        self.__uiController.commandToolsConvertFilesOpen()

    def __menuToolsSearchFiles_clicked(self, action):
        """Open search file tool"""
        self.__uiController.commandToolsSearchFilesOpen()

    # endregion: define actions method -----------------------------------------


    # region: events- ----------------------------------------------------------

    def showEvent(self, event):
        """Event trigerred when dialog is shown

           At this time, all widgets are initialised and size/visiblity is known


           Example
           =======
                # define callback function
                def my_callback_function():
                    # BCMainWindow shown!
                    pass

                # initialise a dialog from an xml .ui file
                dlgMain = BCMainWindow.loadUi(uiFileName)

                # execute my_callback_function() when dialog became visible
                dlgMain.dialogShown.connect(my_callback_function)
        """
        super(BCMainWindow, self).showEvent(event)

        for panelId in self.panels:
            self.panels[panelId].setAllowRefresh(True)

        self.dialogShown.emit()

    def closeEvent(self, event):
        """Event executed when window is about to be closed"""
        #event.ignore()
        self.__uiController.close()
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
                        # Event!
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
        self.__uiController.updateMenuForPanel()

    def getWidgets(self):
        """Return a list of ALL widgets"""
        def appendWithSubWidget(parent):
            list=[parent]
            if len(parent.children())>0:
                for w in parent.children():
                    list+=appendWithSubWidget(w)
            return list

        return appendWithSubWidget(self)

    # endregion: methods -------------------------------------------------------
