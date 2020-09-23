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

import os.path
from pathlib import Path

import sys
import re

from PyQt5.Qt import *
from PyQt5.QtCore import (
        QDir,
        QRect
    )

from PyQt5.QtWidgets import (
        QMessageBox,
        QWidget
    )


from .bcabout import BCAboutWindow
from .bcbookmark import BCBookmark
from .bcfile import (
        BCBaseFile,
        BCDirectory,
        BCFile,
        BCFileManagedFormat
    )
from .bcfileoperation import (
        BCFileOperationUi,
        BCFileOperation
    )
from .bchistory import BCHistory
from .bcmainviewtab import (
        BCMainViewTab,
        BCMainViewTabFilesLayout,
        BCMainViewTabFilesNfoTabs,
        BCMainViewTabFilesTabs,
        BCMainViewTabTabs
    )
from .bcmainwindow import BCMainWindow
from .bcpathbar import BCPathBar
from .bcsettings import (
        BCSettings,
        BCSettingsDialogBox,
        BCSettingsKey,
        BCSettingsValues,
    )
from .bctheme import BCTheme

from .bcimportanimated import (
        BCImportDialogBox,
        BCImportAnimated
    )
from .bcimagepreview import (
        BCImagePreview
    )
from .bcsavedview import BCSavedView
from .bctable import (
        BCTable,
        BCTableSettings
    )
from .bcutils import (
        buildIcon,
        getBytesSizeToStrUnit,
        setBytesSizeToStrUnit,
        Debug
    )
from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )

from ..pktk.ekrita import (
        EKritaNode
    )



# ------------------------------------------------------------------------------
class BCUIController(object):
    """The controller provide an access to all BuliCommander functions
    """
    __EXTENDED_OPEN_OK = 1
    __EXTENDED_OPEN_KO = -1
    __EXTENDED_OPEN_CANCEL = 0

    def __init__(self, bcName="Buli Commander", bcVersion="testing"):
        self.__theme = BCTheme()
        self.__window = None
        self.__bcName = bcName
        self.__bcVersion = bcVersion
        self.__bcTitle = "{0} - {1}".format(bcName, bcVersion)

        self.__history = BCHistory()
        self.__bookmark = BCBookmark()
        self.__savedView = BCSavedView()
        self.__lastDocumentsOpened = BCHistory()
        self.__lastDocumentsSaved = BCHistory()
        self.__backupFilterDView = BCHistory()
        self.__fileLayerFilterDView = BCHistory()
        self.__tableSettings = BCTableSettings()

        self.__confirmAction = True

        self.__settings = BCSettings('bulicommander')

        self.__initialised = False

        # load last documents
        self.commandGoLastDocsOpenedSet(self.__settings.option(BCSettingsKey.SESSION_LASTDOC_O_ITEMS.id()))
        self.commandGoLastDocsSavedSet(self.__settings.option(BCSettingsKey.SESSION_LASTDOC_S_ITEMS.id()))

        BCFile.initialiseCache()

    def start(self):
        if not self.__theme is None:
            self.__theme.loadResources()

        self.__initialised = False
        self.__window = BCMainWindow(self)
        self.__window.dialogShown.connect(self.__initSettings)

        self.__window.setWindowTitle(self.__bcTitle)
        self.__window.show()
        self.__window.activateWindow()

    # region: initialisation methods -------------------------------------------

    def __initSettings(self):
        """There's some visual settings that need to have the window visible
        (ie: the widget size are known) to be applied
        """
        if self.__initialised:
            # already initialised, do nothing
            return

        # Here we know we have an active window
        aw=Krita.instance().activeWindow()
        try:
            # should not occurs as uicontroller is initialised only once, but...
            aw.themeChanged.disconnect(self.__themeChanged)
        except:
            pass
        aw.themeChanged.connect(self.__themeChanged)


        self.__window.initMainView()

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(False)

        self.commandSettingsFileDefaultActionKra(self.__settings.option(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_KRA.id()))
        self.commandSettingsFileDefaultActionOther(self.__settings.option(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_OTHER.id()))
        self.commandSettingsFileNewFileNameKra(self.__settings.option(BCSettingsKey.CONFIG_FILE_NEWFILENAME_KRA.id()))
        self.commandSettingsFileNewFileNameOther(self.__settings.option(BCSettingsKey.CONFIG_FILE_NEWFILENAME_OTHER.id()))
        self.commandSettingsFileUnit(self.__settings.option(BCSettingsKey.CONFIG_FILE_UNIT.id()))
        self.commandSettingsHistoryMaxSize(self.__settings.option(BCSettingsKey.CONFIG_HISTORY_MAXITEMS.id()))
        self.commandSettingsHistoryKeepOnExit(self.__settings.option(BCSettingsKey.CONFIG_HISTORY_KEEPONEXIT.id()))
        self.commandSettingsLastDocsMaxSize(self.__settings.option(BCSettingsKey.CONFIG_LASTDOC_MAXITEMS.id()))
        self.commandSettingsSaveSessionOnExit(self.__settings.option(BCSettingsKey.CONFIG_SESSION_SAVE.id()))

        self.commandViewMainWindowGeometry(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY.id()))
        self.commandViewMainWindowMaximized(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED.id()))
        self.commandViewMainSplitterPosition(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION.id()))
        self.commandViewDisplaySecondaryPanel(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE.id()))
        self.commandViewHighlightPanel(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED.id()))
        self.commandViewShowImageFileOnly(self.__settings.option(BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY.id()))
        self.commandViewShowBackupFiles(self.__settings.option(BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP.id()))
        self.commandViewShowHiddenFiles(self.__settings.option(BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN.id()))

        # load history
        self.commandGoHistorySet(self.__settings.option(BCSettingsKey.SESSION_HISTORY_ITEMS.id()))
        # load bookmarks
        self.commandGoBookmarkSet(self.__settings.option(BCSettingsKey.SESSION_BOOKMARK_ITEMS.id()))
        # load saved views
        self.commandGoSavedViewSet(self.__settings.option(BCSettingsKey.SESSION_SAVEDVIEWS_ITEMS.id()))

        self.commandSettingsNavBarBtnHome(self.__settings.option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HOME.id()))
        self.commandSettingsNavBarBtnViews(self.__settings.option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_VIEWS.id()))
        self.commandSettingsNavBarBtnBookmarks(self.__settings.option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BOOKMARKS.id()))
        self.commandSettingsNavBarBtnHistory(self.__settings.option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HISTORY.id()))
        self.commandSettingsNavBarBtnLastDocuments(self.__settings.option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_LASTDOCUMENTS.id()))
        self.commandSettingsNavBarBtnGoBack(self.__settings.option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BACK.id()))
        self.commandSettingsNavBarBtnGoUp(self.__settings.option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_UP.id()))
        self.commandSettingsNavBarBtnQuickFilter(self.__settings.option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_QUICKFILTER.id()))

        self.commandInfoToClipBoardBorder(self.__settings.option(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_BORDER.id()))
        self.commandInfoToClipBoardHeader(self.__settings.option(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_HEADER.id()))
        self.commandInfoToClipBoardMaxWidth(self.__settings.option(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH.id()))
        self.commandInfoToClipBoardMinWidth(self.__settings.option(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH.id()))
        self.commandInfoToClipBoardMaxWidthActive(self.__settings.option(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE.id()))
        self.commandInfoToClipBoardMinWidthActive(self.__settings.option(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE.id()))

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setHistory(self.__history)
            self.__window.panels[panelId].setBookmark(self.__bookmark)
            self.__window.panels[panelId].setSavedView(self.__savedView)
            self.__window.panels[panelId].setLastDocumentsOpened(self.__lastDocumentsOpened)
            self.__window.panels[panelId].setLastDocumentsSaved(self.__lastDocumentsSaved)
            self.__window.panels[panelId].setBackupFilterDView(self.__backupFilterDView)
            self.__window.panels[panelId].setFileLayerFilterDView(self.__fileLayerFilterDView)

            self.commandPanelTabActive(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId)))
            self.commandPanelTabPosition(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId)))

            self.commandPanelTabFilesLayout(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_LAYOUT.id(panelId=panelId)))
            self.commandPanelTabFilesActive(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId)))
            self.commandPanelTabFilesPosition(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId)))

            self.commandPanelTabFilesNfoActive(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId)))
            self.commandPanelTabFilesSplitterFilesPosition(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_SPLITTER_FILES_POSITION.id(panelId=panelId)))
            self.commandPanelTabFilesSplitterPreviewPosition(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_SPLITTER_PREVIEW_POSITION.id(panelId=panelId)))

            self.commandPanelPath(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_CURRENTPATH.id(panelId=panelId)))

            self.commandPanelFilterValue(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_FILTERVALUE.id(panelId=panelId)))
            self.commandPanelFilterVisible(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_FILTERVISIBLE.id(panelId=panelId)))

            self.commandViewThumbnail(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_THUMBNAIL.id(panelId=panelId)))

            self.commandPanelPreviewBackground(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_PREVIEW_BACKGROUND.id(panelId=panelId)))

            self.__window.panels[panelId].setColumnSort(self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_COLUMNSORT.id(panelId=panelId)))
            self.__window.panels[panelId].setColumnOrder(self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_COLUMNORDER.id(panelId=panelId)))
            self.__window.panels[panelId].setColumnSize(self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_COLUMNSIZE.id(panelId=panelId)))
            self.__window.panels[panelId].setIconSize(self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_ICONSIZE.id(panelId=panelId)))

        self.__window.initMenu()

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(True)

        self.__initialised = True


    def __extendedOpen(self, file):
        bcfile = BCFile(file)
        if bcfile.format() in BCImportAnimated.SUPPORTED_FORMAT:
            imgNfo = bcfile.getMetaInformation()
            if imgNfo['imageCount'] > 1:
                userChoice = BCImportDialogBox.open(f'{self.__bcName}::Import {bcfile.format()} file', bcfile, self.panel())

                if userChoice[0]:
                    if userChoice[1] == BCImportDialogBox.IMPORT_AS_FRAMELAYER:
                        if BCImportAnimated.importAsFrames(bcfile, userChoice[2]):
                            return BCUIController.__EXTENDED_OPEN_OK
                    elif userChoice[1] == BCImportDialogBox.IMPORT_AS_STACKLAYER:
                        if BCImportAnimated.importAsLayers(bcfile):
                            return BCUIController.__EXTENDED_OPEN_OK
                    elif userChoice[1] == BCImportDialogBox.IMPORT_AS_FRAME:
                        if BCImportAnimated.importInOneLayer(bcfile, userChoice[2]):
                            return BCUIController.__EXTENDED_OPEN_OK
                    #else:
                    #   krita's import mode
                else:
                    # cancel
                    return BCUIController.__EXTENDED_OPEN_CANCEL
        return BCUIController.__EXTENDED_OPEN_KO


    def __themeChanged(self):
        """Theme has been changed, reload resources"""
        #print("Theme changed!")
        if not self.__theme is None:
            #print("Reload resources")
            self.__theme.loadResources()

    # endregion: initialisation methods ----------------------------------------

    # region: getter/setters ---------------------------------------------------

    def name(self):
        """Return name"""
        return self.__bcName

    def history(self):
        """Return history manager"""
        return self.__history

    def bookmark(self):
        """Return bookmark manager"""
        return self.__bookmark

    def savedViews(self):
        """Return saved views manager"""
        return self.__savedView

    def lastDocumentsOpened(self):
        """Return last opened doc views manager"""
        return self.__lastDocumentsOpened

    def lastDocumentsSaved(self):
        """Return last saved doc views manager"""
        return self.__lastDocumentsSaved

    def backupFilterDView(self):
        """Return dynamic view for backup filter"""
        return self.__backupFilterDView

    def fileLayerFilterDView(self):
        """Return dynamic view for file layer filter"""
        return self.__fileLayerFilterDView

    def settings(self):
        """return setting manager"""
        return self.__settings

    def tableSettings(self):
        """return table setting manager"""
        return self.__tableSettings

    def panelId(self):
        """Return current highlighted panelId"""
        return self.__window.highlightedPanel()

    def panel(self, current=True):
        """Return current highlighted panel"""
        if current:
            return self.__window.panels[self.__window.highlightedPanel()]
        else:
            return self.__window.panels[1 - self.__window.highlightedPanel()]

    def oppositePanelId(self, panel):
        """Return opposite panel"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    return 1 - panelId
            # should not occurs
            raise EInvalidValue("Unable to determinate opposite panel")
        elif panel in self.__window.panels:
            return 1 - panel
        else:
            raise EInvalidValue("Not a valid panel Id (0 or 1)")

    def oppositePanel(self, panel):
        """Return opposite panel"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    return self.__window.panels[1 - panelId]
            # should not occurs
            raise EInvalidValue("Unable to determinate opposite panel")
        elif panel in self.__window.panels:
            return self.__window.panels[1 - panel]
        else:
            raise EInvalidValue("Not a valid panel Id (0 or 1)")

    def theme(self):
        """Return theme object"""
        return self.__window.theme()

    def quickRefDict(self):
        """Return a dictionnary of quick references

        key = reference (a saved view Id @xxxx or a bpookmark id @xxxx)
        value = (Type, Icon, Case sensitive)
        """
        iconSavedView = buildIcon([(QPixmap(":/images/saved_view_file"), QIcon.Normal)])
        iconBookmark = buildIcon([(QPixmap(":/images/bookmark"), QIcon.Normal)])

        returned = {'@home': (BCPathBar.QUICKREF_RESERVED_HOME, buildIcon([(QPixmap(":/images/home"), QIcon.Normal)]), 'Home'),
                    '@last': (BCPathBar.QUICKREF_RESERVED_LAST_ALL, buildIcon([(QPixmap(":/images/saved_view_last"), QIcon.Normal)]), 'Last opened/saved documents'),
                    '@last opened': (BCPathBar.QUICKREF_RESERVED_LAST_OPENED, buildIcon([(QPixmap(":/images/saved_view_last"), QIcon.Normal)]), 'Last opened documents'),
                    '@last saved': (BCPathBar.QUICKREF_RESERVED_LAST_SAVED, buildIcon([(QPixmap(":/images/saved_view_last"), QIcon.Normal)]), 'Last saved documents'),
                    '@history': (BCPathBar.QUICKREF_RESERVED_HISTORY, buildIcon([(QPixmap(":/images/history"), QIcon.Normal)]), 'History directories'),
                    '@backup filter': (BCPathBar.QUICKREF_RESERVED_BACKUPFILTERDVIEW, buildIcon([(QPixmap(":/images/filter"), QIcon.Normal)]), 'Backup files list'),
                    '@file layer filter': (BCPathBar.QUICKREF_RESERVED_FLAYERFILTERDVIEW, buildIcon([(QPixmap(":/images/large_view"), QIcon.Normal)]), 'Layer files list')
                    }

        if not self.__bookmark is None and self.__bookmark.length() > 0:
            for bookmark in self.__bookmark.list():
                returned[f'@{bookmark[0].lower()}']=(BCPathBar.QUICKREF_BOOKMARK, iconBookmark, bookmark[0])

        if not self.__savedView is None and self.__savedView.length() > 0:
            for savedView in self.__savedView.list():
                returned[f'@{savedView[0].lower()}']=(BCPathBar.QUICKREF_SAVEDVIEW_LIST, iconSavedView, savedView[0])

        return returned

    def quickRefPath(self, refId):
        """Return path from reserved value or bookmark reference

        Return None if not found
        """
        refId=refId.lstrip('@').lower()

        if refId == 'home':
            path = ''
            if self.__settings.option(BCSettingsKey.CONFIG_HOME_DIR_MODE.id()) == BCSettingsValues.HOME_DIR_UD:
                path = self.__settings.option(BCSettingsKey.CONFIG_HOME_DIR_UD.id())

            if path == '' or not os.path.isdir(path):
                path = QDir.homePath()

            return path
        else:
            return self.__bookmark.valueFromName(refId)

    def quickRefType(self, refId):
        """Return current type """
        refDict = self.quickRefDict()

        if refId in refDict:
            return refDict[refId][0]
        return None

    def quickRefName(self, refId):
        """Return current type """
        refDict = self.quickRefDict()

        if refId in refDict:
            return refDict[refId][2]
        return None


    # endregion: getter/setters ------------------------------------------------


    # region: define commands --------------------------------------------------

    def saveSettings(self):
        """Save the current settings"""

        self.__settings.setOption(BCSettingsKey.CONFIG_SESSION_SAVE, self.__window.actionSettingsSaveSessionOnExit.isChecked())

        if self.__settings.option(BCSettingsKey.CONFIG_SESSION_SAVE.id()):
            # save current session properties only if allowed
            if self.__window.actionViewDisplaySecondaryPanel.isChecked():
                # if not checked, hidden panel size is 0 so, do not save it (splitter position is already properly defined)
                self.__settings.setOption(BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION, self.__window.splitterMainView.sizes())

            self.__settings.setOption(BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE, self.__window.actionViewDisplaySecondaryPanel.isChecked())
            self.__settings.setOption(BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED, self.__window.highlightedPanel())

            self.__settings.setOption(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED, self.__window.isMaximized())
            if not self.__window.isMaximized():
                # when maximized geometry is full screen geomtry, then do it only if no in maximized
                self.__settings.setOption(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY, [self.__window.geometry().x(), self.__window.geometry().y(), self.__window.geometry().width(), self.__window.geometry().height()])

            self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY, self.__window.actionViewShowImageFileOnly.isChecked())
            self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP, self.__window.actionViewShowBackupFiles.isChecked())
            self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN, self.__window.actionViewShowHiddenFiles.isChecked())

            # normally shouldn't be necessary
            if getBytesSizeToStrUnit() == 'auto':
                self.__settings.setOption(BCSettingsKey.CONFIG_FILE_UNIT, BCSettingsValues.FILE_UNIT_KB)
            else:
                self.__settings.setOption(BCSettingsKey.CONFIG_FILE_UNIT, BCSettingsValues.FILE_UNIT_KIB)

            for panelId in self.__window.panels:
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_LAYOUT.id(panelId=panelId), self.__window.panels[panelId].tabFilesLayout().value)
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_CURRENTPATH.id(panelId=panelId), self.__window.panels[panelId].path())

                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_THUMBNAIL.id(panelId=panelId), self.__window.panels[panelId].viewThumbnail())

                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_FILTERVISIBLE.id(panelId=panelId), self.__window.panels[panelId].filterVisible())
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_FILTERVALUE.id(panelId=panelId), self.__window.panels[panelId].filter())

                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_COLUMNSORT.id(panelId=panelId), self.__window.panels[panelId].columnSort())
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_COLUMNORDER.id(panelId=panelId), self.__window.panels[panelId].columnOrder())
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_COLUMNSIZE.id(panelId=panelId), self.__window.panels[panelId].columnSize())
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_ICONSIZE.id(panelId=panelId), self.__window.panels[panelId].iconSize())

                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_PREVIEW_BACKGROUND.id(panelId=panelId), self.__window.panels[panelId].previewBackground())

                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId), [tab.value for tab in self.__window.panels[panelId].tabOrder()])
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId), [tab.value for tab in self.__window.panels[panelId].tabFilesOrder()])
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId), self.__window.panels[panelId].tabActive().value)
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId), self.__window.panels[panelId].tabFilesActive().value)
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId), self.__window.panels[panelId].tabFilesNfoActive().value)

                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_SPLITTER_FILES_POSITION.id(panelId=panelId), self.__window.panels[panelId].tabFilesSplitterFilesPosition())
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_SPLITTER_PREVIEW_POSITION.id(panelId=panelId), self.__window.panels[panelId].tabFilesSplitterPreviewPosition())

            if self.__settings.option(BCSettingsKey.CONFIG_HISTORY_KEEPONEXIT.id()):
                self.__settings.setOption(BCSettingsKey.SESSION_HISTORY_ITEMS, self.__history.list())
            else:
                self.__settings.setOption(BCSettingsKey.SESSION_HISTORY_ITEMS, [])

            self.__settings.setOption(BCSettingsKey.SESSION_BOOKMARK_ITEMS, self.__bookmark.list())
            self.__settings.setOption(BCSettingsKey.SESSION_SAVEDVIEWS_ITEMS, self.__savedView.list())
            self.__settings.setOption(BCSettingsKey.SESSION_LASTDOC_O_ITEMS, self.__lastDocumentsOpened.list())
            self.__settings.setOption(BCSettingsKey.SESSION_LASTDOC_S_ITEMS, self.__lastDocumentsSaved.list())

            self.__settings.setOption(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_BORDER, self.__tableSettings.border())
            self.__settings.setOption(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_HEADER, self.__tableSettings.headerActive())
            self.__settings.setOption(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH, self.__tableSettings.minWidth())
            self.__settings.setOption(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH, self.__tableSettings.maxWidth())
            self.__settings.setOption(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE, self.__tableSettings.minWidthActive())
            self.__settings.setOption(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE, self.__tableSettings.maxWidthActive())

        return self.__settings.saveConfig()

    def updateMenuForPanel(self):
        """Update menu (enabled/disabled/checked/unchecked) according to current panel"""
        self.__window.actionViewThumbnail.setChecked(self.panel().viewThumbnail())

        selectionInfo = self.panel().selectedFiles()

        self.__window.actionFileOpen.setEnabled(selectionInfo[4]>0)
        self.__window.actionFileOpenCloseBC.setEnabled(selectionInfo[4]>0)
        self.__window.actionFileOpenAsNewDocument.setEnabled(selectionInfo[4]>0)
        self.__window.actionFileOpenAsNewDocumentCloseBC.setEnabled(selectionInfo[4]>0)
        self.__window.actionFileCopyToOtherPanel.setEnabled(selectionInfo[3]>0)
        self.__window.actionFileMoveToOtherPanel.setEnabled(selectionInfo[3]>0)
        self.__window.actionFileDelete.setEnabled(selectionInfo[3]>0)
        self.__window.actionFileRename.setEnabled(selectionInfo[3]==1)

        self.__window.actionFileCopyToOtherPanelNoConfirm.setEnabled(selectionInfo[3]>0)
        self.__window.actionFileMoveToOtherPanelNoConfirm.setEnabled(selectionInfo[3]>0)
        self.__window.actionFileDeleteNoConfirm.setEnabled(selectionInfo[3]>0)

        self.__window.actionViewShowBackupFiles.setEnabled(self.optionViewFileManagedOnly())

        self.__window.actionGoBack.setEnabled(self.panel().goBackEnabled())
        self.__window.actionGoUp.setEnabled(self.panel().goUpEnabled())

    def close(self):
        """When window is about to be closed, execute some cleanup/backup/stuff before exiting BuliCommander"""
        # save current settings
        self.saveSettings()

        # stop all async processes (thumbnail generating)
        for panelRef in self.__window.panels:
            self.__window.panels[panelRef].close()

    def optionViewDisplaySecondaryPanel(self):
        """Return current option value"""
        return self.__window.actionViewDisplaySecondaryPanel.isChecked()

    def optionHighlightedPanel(self):
        """Return current option value"""
        return self.__window.highlightedPanel()

    def optionIsMaximized(self):
        """Return current option value"""
        return self.__window.isMaximized()

    def optionViewFileManagedOnly(self):
        """Return current option value"""
        return self.__window.actionViewShowImageFileOnly.isChecked()

    def optionViewFileBackup(self):
        """Return current option value"""
        return self.__window.actionViewShowBackupFiles.isChecked()

    def optionViewFileHidden(self):
        """Return current option value"""
        return self.__window.actionViewShowHiddenFiles.isChecked()

    def optionFileDefaultActionKra(self):
        """Return current option value"""
        return self.__settings.option(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_KRA.id())

    def optionFileDefaultActionOther(self):
        """Return current option value"""
        return self.__settings.option(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_OTHER.id())

    def optionHistoryMaxSize(self):
        """Return current option value"""
        return self.__settings.option(BCSettingsKey.CONFIG_HISTORY_MAXITEMS.id())

    def commandQuit(self):
        """Close Buli Commander"""
        self.__window.close()

    def commandFileOpen(self, file=None):
        """Open file"""
        if file is None:
            selectionInfo = self.panel().selectedFiles()
            if selectionInfo[4] > 0:
                nbOpened = 0
                for file in selectionInfo[0]:
                    if isinstance(file, BCFile) and file.readable():
                        if self.commandFileOpen(file.fullPathName()):
                            nbOpened+=1
                if nbOpened!=selectionInfo[4]:
                    return False
                else:
                    return True
        elif isinstance(file, BCFile) and file.readable():
            return self.commandFileOpen(file.fullPathName())
        elif isinstance(file, str):
            opened = self.__extendedOpen(file)
            if opened == BCUIController.__EXTENDED_OPEN_CANCEL:
                return False
            elif opened == BCUIController.__EXTENDED_OPEN_OK:
                return True

            try:
                document = Krita.instance().openDocument(file)
                view = Krita.instance().activeWindow().addView(document)
                Krita.instance().activeWindow().showView(view)
            except Exception as e:
                Debug.print('[BCUIController.commandFileOpen] unable to open file {0}: {1}', file, str(e))
                return False
            return True
        else:
            raise EInvalidType('Given `file` is not valid')

    def commandFileOpenCloseBC(self, file=None):
        """Open file and close BuliCommander"""
        if self.commandFileOpen(file):
            self.commandQuit()
            return True
        return False

    def commandFileOpenAsNew(self, file=None):
        """Open file as new document"""
        if file is None:
            selectionInfo = self.panel().selectedFiles()
            if selectionInfo[4] > 0:
                nbOpened = 0
                for file in selectionInfo[0]:
                    if isinstance(file, BCFile) and file.readable():
                        if self.commandFileOpenAsNew(file.fullPathName()):
                            nbOpened+=1
                if nbOpened!=selectionInfo[4]:
                    return False
                else:
                    return True
        elif isinstance(file, BCFile) and file.readable():
            return self.commandFileOpenAsNew(file.fullPathName())
        elif isinstance(file, str):
            opened = self.__extendedOpen(file)
            if opened == BCUIController.__EXTENDED_OPEN_CANCEL:
                return False
            elif opened == BCUIController.__EXTENDED_OPEN_OK:
                return True

            bcFile = BCFile(file)

            newFileName = None
            if bcFile.format() == BCFileManagedFormat.KRA:
                newFileName = BCFile.formatFileName(bcFile, self.__settings.option(BCSettingsKey.CONFIG_FILE_NEWFILENAME_KRA.id()))
            else:
                newFileName = BCFile.formatFileName(bcFile, self.__settings.option(BCSettingsKey.CONFIG_FILE_NEWFILENAME_OTHER.id()))

            if isinstance(newFileName, str):
                if newFileName != '' and not re.search("\.kra$", newFileName):
                    newFileName+='.kra'
                elif newFileName.strip() == '':
                    newFileName = None

            try:
                document = Krita.instance().openDocument(file)
                document.setFileName(newFileName)
                view = Krita.instance().activeWindow().addView(document)
                Krita.instance().activeWindow().showView(view)
            except Exception as e:
                Debug.print('[BCUIController.commandFileOpenAsNew] unable to open file {0}: {1}', file, str(e))
                return False
            return True
        else:
            raise EInvalidType('Given `file` is not valid')

    def commandFileOpenAsNewCloseBC(self, file=None):
        """Open file and close BuliCommander"""
        if self.commandFileOpenAsNew(file):
            self.commandQuit()
            return True
        return False

    def commandFileDefaultAction(self, file):
        """Execute default action to item

        - Directory: go to directory
        - Image: open it
        - Other files: does nothing
        """
        #if not isinstance(file, BCBaseFile):
        #    raise EInvalidType('Given `file` must be a <BCBaseFile>')

        closeBC = False

        if file is None:
            return

        if file.format() == BCFileManagedFormat.DIRECTORY:
            if file.name() == '..':
                self.commandGoUp(self.__window.highlightedPanel())
            else:
                self.commandPanelPath(self.__window.highlightedPanel(), file.fullPathName())
        else:
            if file.readable():
                if file.format() == BCFileManagedFormat.KRA:
                    if self.optionFileDefaultActionKra() in [BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE, BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE]:
                        closeBC = True

                    if self.optionFileDefaultActionKra() == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE:
                        closeBC = self.commandFileOpen(file)
                    elif self.optionFileDefaultActionKra() == BCSettingsValues.FILE_DEFAULTACTION_OPEN:
                        self.commandFileOpen(file)
                    elif self.optionFileDefaultActionKra() == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE:
                        closeBC = self.commandFileOpenAsNew(file)
                    elif self.optionFileDefaultActionKra() == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW:
                        self.commandFileOpenAsNew(file)
                else:
                    if self.optionFileDefaultActionOther() in [BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE, BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE]:
                        closeBC = True

                    if self.optionFileDefaultActionOther() == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE:
                        closeBC = self.commandFileOpen(file)
                    elif self.optionFileDefaultActionOther() == BCSettingsValues.FILE_DEFAULTACTION_OPEN:
                        self.commandFileOpen(file)
                    elif self.optionFileDefaultActionOther() == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE:
                        closeBC = self.commandFileOpenAsNew(file)
                    elif self.optionFileDefaultActionOther() == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW:
                        self.commandFileOpenAsNew(file)
            else:
                Debug.print('[BCUIController.commandFileDefaultAction] File not readable: {0}', file)

        return closeBC

    def commandFileCreateDir(self, targetPath=None):
        """Create directory for given path"""
        if targetPath is None:
            targetPath = self.panel().path()

        newPath = BCFileOperationUi.createDir(self.__bcName, targetPath)
        if not newPath is None:
            if not BCFileOperation.createDir(newPath):
                QMessageBox.warning(
                        QWidget(),
                        f"{self.__bcName}::Create directory",
                        f"Unable to create directory:\n{newPath}"
                    )

    def commandFileDelete(self, confirm=True):
        """Delete file(s)"""

        selectedFiles = self.panel().selectedFiles()
        if confirm:
            fileList = "\n".join([file.fullPathName() for file in selectedFiles[5]])
            choice = BCFileOperationUi.delete(self.__bcName, selectedFiles[2], selectedFiles[1], fileList)
            if not choice:
                return

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(False)

        BCFileOperation.delete(self.__bcName, selectedFiles[5])

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(True)

    def commandFileCopy(self, confirm=True):
        """Copy file(s)"""
        targetPath = self.panel(False).path()
        selectedFiles = self.panel().selectedFiles()
        if confirm:
            fileList = "\n".join([file.fullPathName() for file in selectedFiles[5]])
            choice = BCFileOperationUi.copy(self.__bcName, selectedFiles[2], selectedFiles[1], fileList, targetPath)
            if not choice:
                return
            targetPath = BCFileOperationUi.path()

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(False)

        BCFileOperation.copy(self.__bcName, selectedFiles[5], targetPath)

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(True)

    def commandFileMove(self, confirm=True):
        """Move file(s)"""
        targetPath = self.panel(False).path()
        selectedFiles = self.panel().selectedFiles()
        if confirm:
            fileList = "\n".join([file.fullPathName() for file in selectedFiles[5]])
            choice = BCFileOperationUi.move(self.__bcName, selectedFiles[2], selectedFiles[1], fileList, targetPath)
            if not choice:
                return
            targetPath = BCFileOperationUi.path()

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(False)

        BCFileOperation.move(self.__bcName, selectedFiles[5], targetPath)

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(True)

    def commandViewSwapPanels(self):
        """Swap panels positions"""
        if self.__window.actionViewDisplaySecondaryPanel.isChecked():
            self.__window.splitterMainView.insertWidget(0, self.__window.panels[1])
            self.__window.panels[0],self.__window.panels[1] = self.__window.panels[1],self.__window.panels[0]

    def commandViewDisplaySecondaryPanel(self, displaySecondary=None):
        """Display/Hide secondary panel

        If `displaySecondary` is True, force display
        If `displaySecondary` is False, force hide
        """
        if displaySecondary is None:
            displaySecondary = self.__window.actionViewDisplaySecondaryPanel.isChecked()
        else:
            self.__window.actionViewDisplaySecondaryPanel.setChecked(displaySecondary)


        if not displaySecondary:
            # when hidden, secondary panel width is set to 0, then save current size now
            self.__settings.setOption(BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION, self.__window.splitterMainView.sizes())


        self.__window.panels[1].setVisible(displaySecondary)
        self.__window.actionViewSwapPanels.setEnabled(displaySecondary)

        if not displaySecondary:
            # when the right panel is hidden, ensure the left is highlighted
            self.__window.panels[0].setHighlighted(True)

        return displaySecondary

    def commandViewHighlightPanel(self, highlightedPanel=0):
        """Set the highlighted panel

        If `highlightedPanel` is 0, left panel is highlighted
        If `highlightedPanel` is 1, right panel is highlighted (if visible)
        """
        if not highlightedPanel in self.__window.panels:
            raise EInvalidValue('Given `panelIndex` must be 0 or 1')

        if not self.__window.actionViewDisplaySecondaryPanel.isChecked():
            # secondary is not visible, force left panel to be highlighted
            highlightedPanel = 0

        self.__window.panels[highlightedPanel].setHighlighted(True)
        self.__window.panels[1-highlightedPanel].setHighlighted(False)
        self.__window.setHighlightedPanel(highlightedPanel)

    def commandViewMainSplitterPosition(self, positions=None):
        """Set the mainwindow splitter position

        Given `positions` is a list [<panel0 size>,<panel1 size>]
        If value is None, will define a default 50%-50%
        """
        if positions is None:
            positions = [1000, 1000]

        if not isinstance(positions, list) or len(positions) != 2:
            raise EInvalidValue('Given `positions` must be a list [l,r]')

        self.__window.splitterMainView.setSizes(positions)

        return positions

    def commandViewMainWindowMaximized(self, maximized=False):
        """Set the window state"""
        if not isinstance(maximized, bool):
            raise EInvalidValue('Given `maximized` must be a <bool>')

        if maximized:
            # store current geometry now because after window is maximized, it's lost
            self.__settings.setOption(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY, [self.__window.geometry().x(), self.__window.geometry().y(), self.__window.geometry().width(), self.__window.geometry().height()])
            self.__window.showMaximized()
        else:
            self.__window.showNormal()

        return maximized

    def commandViewMainWindowGeometry(self, geometry=[-1,-1,-1,-1]):
        """Set the window geometry

        Given `geometry` is a list [x,y,width,height] or a QRect()
        """
        if isinstance(geometry, QRect):
            geometry = [geometry.x(), geometry.y(), geometry.width(), geometry.height()]

        if not isinstance(geometry, list) or len(geometry)!=4:
            raise EInvalidValue('Given `geometry` must be a <list[x,y,w,h]>')

        rect = self.__window.geometry()

        if geometry[0] >= 0:
            rect.setX(geometry[0])

        if geometry[1] >= 0:
            rect.setY(geometry[1])

        if geometry[2] >= 0:
            rect.setWidth(geometry[2])

        if geometry[3] >= 0:
            rect.setHeight(geometry[3])

        self.__window.setGeometry(rect)

        return [self.__window.geometry().x(), self.__window.geometry().y(), self.__window.geometry().width(), self.__window.geometry().height()]

    def commandViewThumbnail(self, panel=None, mode=None):
        """Set current view mode"""
        if panel is None:
            panel = self.panelId()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if mode is None or not isinstance(mode, bool):
            mode = False

        self.__window.actionViewThumbnail.setChecked(mode)
        self.__window.panels[panel].setViewThumbnail(mode)

        self.updateMenuForPanel()

        return mode

    def commandPanelPreviewBackground(self, panel=None, mode=None):
        """Set current preview view mode"""
        if panel is None:
            panel = self.panelId()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if not mode in BCImagePreview.backgroundList():
            mode = BCImagePreview.BG_CHECKER_BOARD

        self.__window.panels[panel].setPreviewBackground(mode)

        return mode

    def commandViewShowImageFileOnly(self, value=None):
        """Display image files

        If `value` is True, display image files only
        If `value` is False, display all files
        """
        if value is None:
            value = self.__window.actionViewShowImageFileOnly.isChecked()
        elif self.__window.actionViewShowImageFileOnly.isChecked() == value:
            # already set, do nothing
            return
        else:
            self.__window.actionViewShowImageFileOnly.setChecked(value)

        for panelId in self.__window.panels:
            self.__window.panels[panelId].refresh()

        self.updateMenuForPanel()

        return value

    def commandViewShowBackupFiles(self, value=None):
        """Display image backup files

        If `value` is True, display image backup files
        If `value` is False, don't display image backup files
        """
        if value is None:
            value = self.__window.actionViewShowBackupFiles.isChecked()
        elif self.__window.actionViewShowBackupFiles.isChecked() == value:
            # already set, do nothing
            return
        else:
            self.__window.actionViewShowBackupFiles.setChecked(value)

        for panelId in self.__window.panels:
            self.__window.panels[panelId].refresh()

        return value

    def commandViewShowHiddenFiles(self, value=None):
        """Display hidden files

        If `value` is True, display hidden files
        If `value` is False, don't display hidden files
        """
        if value is None:
            value = self.__window.actionViewShowHiddenFiles.isChecked()
        elif self.__window.actionViewShowHiddenFiles.isChecked() == value:
            # already set, do nothing
            return
        else:
            self.__window.actionViewShowHiddenFiles.setChecked(value)

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setHiddenPath(value)

        return value

    def commandPanelTabFilesLayout(self, panel, value):
        """Set panel layout"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if isinstance(value, str):
            value = BCMainViewTabFilesLayout(value)

        self.__window.panels[panel].setTabFilesLayout(value)

        return value

    def commandPanelTabFilesActive(self, panel, value):
        """Set active tab for files tab for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if isinstance(value, str):
            value = BCMainViewTabFilesTabs(value)

        self.__window.panels[panel].setTabFilesActive(value)

        return value

    def commandPanelTabFilesPosition(self, panel, value):
        """Set tabs positions for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        self.__window.panels[panel].setTabFilesOrder(value)

        return value

    def commandPanelTabActive(self, panel, value):
        """Set active tab for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if isinstance(value, str):
            value = BCMainViewTabTabs(value)

        self.__window.panels[panel].setTabActive(value)

        return value

    def commandPanelTabPosition(self, panel, value):
        """Set tabs positions for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        self.__window.panels[panel].setTabOrder(value)

        return value

    def commandPanelTabFilesNfoActive(self, panel, value):
        """Set active tab for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if isinstance(value, str):
            value = BCMainViewTabFilesNfoTabs(value)

        self.__window.panels[panel].setTabFilesNfoActive(value)

        return value

    def commandPanelTabFilesSplitterFilesPosition(self, panel, positions=None):
        """Set splitter position for tab files for given panel

        Given `positions` is a list [<panel0 size>,<panel1 size>]
        If value is None, will define a default 50%-50%
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setTabFilesSplitterFilesPosition(positions)

    def commandPanelTabFilesSplitterPreviewPosition(self, panel, positions=None):
        """Set splitter position for tab preview for given panel

        Given `positions` is a list [<panel0 size>,<panel1 size>]
        If value is None, will define a default 50%-50%
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setTabFilesSplitterPreviewPosition(positions)

    def commandPanelPath(self, panel, path=None):
        """Define path for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        returned = self.__window.panels[panel].setPath(path)
        self.updateMenuForPanel()
        return returned

    def commandPanelSelectAll(self, panel):
        """Select all item"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].selectAll()

    def commandPanelSelectNone(self, panel):
        """Clear selection"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].selectNone()

    def commandPanelSelectInvert(self, panel):
        """Clear selection"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].selectInvert()

    def commandPanelFilterVisible(self, panel, visible=None):
        """Display the filter

        If visible is None, invert current status
        If True, display filter
        If False, hide
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setFilterVisible(visible)

    def commandPanelFilterValue(self, panel, value=None):
        """Set current filter value"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setFilter(value)

    def commandGoTo(self, panel, path=None):
        """Go back to given path/bookmark/saved view"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setPath(path)

    def commandGoBack(self, panel):
        """Go back to previous directory"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].goToBackPath()

    def commandGoUp(self, panel):
        """Go to parent directory"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].goToUpPath()

    def commandGoHome(self, panel):
        """Go to parent directory"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.commandGoTo(panel, '@home')

    def commandGoHistoryClear(self):
        """Clear history content"""
        self.__history.clear()

    def commandGoHistoryClearUI(self):
        """Clear history content"""
        if self.__confirmAction:
            if QMessageBox.question(QWidget(),
                                          self.__bcName,
                                          "Are you sure you want to clear history?"
                                        ) == QMessageBox.No:
                return False
        self.commandGoHistoryClear()
        return True

    def commandGoHistorySet(self, value=[]):
        """Set history content"""
        self.__history.clear()
        self.__history.setItems(value)

    def commandGoHistoryAdd(self, value):
        """Set history content"""
        self.__history.append(value)

    def commandGoBookmarkSet(self, values=[]):
        """Set bookmark content"""
        self.__bookmark.clear()
        self.__bookmark.set(values)

    def commandGoBookmarkClear(self):
        """Clear bookmark content"""
        self.__bookmark.clear()

    def commandGoBookmarkClearUI(self):
        """Clear bookmark content"""
        if self.__confirmAction:
            if QMessageBox.question(QWidget(),
                                          self.__bcName,
                                          "Are you sure you want to clear all bookmarks?"
                                        ) == QMessageBox.No:
                return
        self.commandGoBookmarkClear()

    def commandGoBookmarkAppend(self, name, path):
        """append bookmark content"""
        self.__bookmark.append(name, path)

    def commandGoBookmarkAppendUI(self, path):
        """append bookmark content"""
        self.__bookmark.uiAppend(path, self.quickRefDict())

    def commandGoBookmarkRemove(self, name):
        """remove bookmark content"""
        self.__bookmark.remove(name, path)

    def commandGoBookmarkRemoveUI(self, name):
        """remove bookmark content"""
        self.__bookmark.uiRemove(name)

    def commandGoBookmarkRename(self, name, newName):
        """rename bookmark content"""
        self.__bookmark.rename(name, newName)

    def commandGoBookmarkRenameUI(self, name):
        """rename bookmark content"""
        self.__bookmark.uiRename(name, self.quickRefDict())

    def commandGoSavedViewSet(self, values):
        """Set saved views content"""
        self.__savedView.clear()

        if isinstance(values, dict):
            # assume key = name, value = list of files/directories
            self.__savedView.set(values)
        elif isinstance(values, list):
            # assume item in list are tuple (or list) (name, list of files/directories)
            dictValues = {}
            for item in values:
                dictValues[item[0]]=item[1]
            self.__savedView.set(dictValues)
        else:
            raise EInvalidType('Given `values` must be a <dict> or a <list>')

    def commandGoSavedViewClear(self, name):
        """Clear content for view `name`"""
        self.__savedView.viewClear(name)

    def commandGoSavedViewClearUI(self, name):
        """Clear saved views content"""
        cleared, name = self.__savedView.uiClearContent(name)
        if cleared:
            self.panel().refresh(False)

    def commandGoSavedViewAppend(self, name, files):
        """append files to saved view"""
        return self.__savedView.viewAppend(name, files)

    def commandGoSavedViewRemove(self, name, files):
        """remove files from saved view"""
        return self.__savedView.viewRemove(name, files)

    def commandGoSavedViewRemoveUI(self, name, files):
        """remove files from saved view"""
        removed, name = self.__savedView.uiRemoveContent(name, files)
        if removed:
            self.panel().refresh(False)
        return removed

    def commandGoSavedViewCreate(self, name, files):
        """rename saved view"""
        return self.__savedView.create(name, newName)

    def commandGoSavedViewCreateUI(self, files):
        """rename saved views content"""
        self.__savedView.uiCreate(files, self.quickRefDict())

    def commandGoSavedViewRename(self, name, newName):
        """rename saved view"""
        return self.__savedView.rename(name, newName)

    def commandGoSavedViewRenameUI(self, name):
        """rename saved views content"""
        renamed, newName = self.__savedView.uiRename(name, self.quickRefDict())
        if renamed:
            self.commandGoTo(self.panel(), f'@{newName}')
        return renamed

    def commandGoSavedViewDelete(self, name):
        """delete saved view"""
        return self.__savedView.delete(name)

    def commandGoSavedViewDeleteUI(self, name):
        """delete saved view"""
        deleted, deletedName = self.__savedView.uiDelete(name)
        if deleted:
            if not self.commandGoBack(self.panel()):
                # go to user directory if no previous path in history
                self.commandGoTo(self.panel(), self.quickRefPath('@home'))

    def commandGoLastDocsOpenedSet(self, value=[]):
        """Set last opened documents content"""
        self.__lastDocumentsOpened.clear()
        self.__lastDocumentsOpened.setItems(value)

    def commandGoLastDocsOpenedAdd(self, value):
        """Set last opened documents content"""
        self.__lastDocumentsOpened.append(value)

    def commandGoLastDocsSavedSet(self, value=[]):
        """Set last saved documents content"""
        self.__lastDocumentsSaved.clear()
        self.__lastDocumentsSaved.setItems(value)

    def commandGoLastDocsSavedAdd(self, value):
        """Set last saved documents content"""
        self.__lastDocumentsSaved.append(value)

    def commandGoLastDocsClear(self):
        """Clear last doc content"""
        self.__lastDocumentsOpened.clear()
        self.__lastDocumentsSaved.clear()

    def commandGoLastDocsClearUI(self):
        """Clear history content"""
        if self.__confirmAction:
            if QMessageBox.question(QWidget(),
                                          self.__bcName,
                                          "Are you sure you want to clear last opened/saved list?"
                                        ) == QMessageBox.No:
                return False
        self.commandGoLastDocsClear()
        return True

    def commandGoLastDocsReset(self):
        """Reset last doc content from Krita last documents list"""
        self.__lastDocumentsOpened.clear()
        self.__lastDocumentsSaved.clear()

        for fileName in Krita.instance().recentDocuments():
            if not fileName is None and fileName != '':
                self.__lastDocumentsOpened.append(fileName)

    def commandGoLastDocsResetUI(self):
        """Reset last doc content from Krita last documents list"""
        if self.__confirmAction:
            if QMessageBox.question(QWidget(),
                                          self.__bcName,
                                          "Are you sure you want to reset last opened/saved list?"
                                        ) == QMessageBox.No:
                return False
        self.commandGoLastDocsReset()
        return True

    def commandGoBackupFilterDViewSet(self, value=[]):
        """Set backup filter dynamic view content"""
        self.__backupFilterDView.clear()
        self.__backupFilterDView.setItems(value)

    def commandGoFileLayerFilterDViewSet(self, value=[]):
        """Set file layer filter dynamic view content"""
        self.__fileLayerFilterDView.clear()
        self.__fileLayerFilterDView.setItems(value)

    def commandSettingsHistoryMaxSize(self, value=25):
        """Set maximum size history for history content"""
        self.__history.setMaxItems(value)
        self.__settings.setOption(BCSettingsKey.CONFIG_HISTORY_MAXITEMS, self.__history.maxItems())

    def commandSettingsHistoryKeepOnExit(self, value=True):
        """When True, current history is saved when BuliCommander is exited"""
        self.__settings.setOption(BCSettingsKey.CONFIG_HISTORY_KEEPONEXIT, value)

    def commandSettingsLastDocsMaxSize(self, value=25):
        """Set maximum size for last documents list"""
        self.__lastDocumentsOpened.setMaxItems(value)
        self.__lastDocumentsSaved.setMaxItems(value)
        self.__settings.setOption(BCSettingsKey.CONFIG_LASTDOC_MAXITEMS, self.__lastDocumentsOpened.maxItems())

    def commandSettingsFileDefaultActionKra(self, value=BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE):
        """Set default action for kra file"""
        self.__settings.setOption(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_KRA, value)

    def commandSettingsFileDefaultActionOther(self, value=BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE):
        """Set default action for kra file"""
        self.__settings.setOption(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_OTHER, value)

    def commandSettingsFileNewFileNameKra(self, value=None):
        """Set default file name applied when a Krita file is opened as a new document"""
        if value is None:
            value = "<None>"
        elif not isinstance(value, str):
            raise EInvalidType("Given `value` must be a <str>")

        if value.lower().strip() == '<none>':
            value = "<None>"

        self.__settings.setOption(BCSettingsKey.CONFIG_FILE_NEWFILENAME_KRA, value)

    def commandSettingsFileNewFileNameOther(self, value=None):
        """Set default file name applied when a non Krita file is opened as a new document"""
        if value is None:
            value = "<None>"
        elif not isinstance(value, str):
            raise EInvalidType("Given `value` must be a <str>")

        if value.lower().strip() == '<none>':
            value = "<None>"

        self.__settings.setOption(BCSettingsKey.CONFIG_FILE_NEWFILENAME_OTHER, value)

    def commandSettingsFileUnit(self, value=BCSettingsValues.FILE_UNIT_KIB):
        """Set used file unit"""
        setBytesSizeToStrUnit(value)
        self.__settings.setOption(BCSettingsKey.CONFIG_FILE_UNIT, getBytesSizeToStrUnit())

        for panelId in self.__window.panels:
            self.__window.panels[panelId].updateFileSizeUnit()

    def commandSettingsHomeDirMode(self, value=BCSettingsValues.HOME_DIR_SYS):
        """Set mode for home directory"""
        self.__settings.setOption(BCSettingsKey.CONFIG_HOME_DIR_MODE, value)

    def commandSettingsHomeDirUserDefined(self, value=''):
        """Set user defined directory for home"""
        self.__settings.setOption(BCSettingsKey.CONFIG_HOME_DIR_UD, value)

    def commandSettingsSaveSessionOnExit(self, saveSession=None):
        """Define if current session properties have to be save or not"""
        if saveSession is None:
            saveSession = self.__window.actionSettingsSaveSessionOnExit.isChecked()
        else:
            self.__window.actionSettingsSaveSessionOnExit.setChecked(saveSession)

        return saveSession

    def commandSettingsResetSessionToDefault(self):
        """Reset session configuration to default"""
        for panelId in self.__window.panels:
            self.__window.panels[panelId].setAllowRefresh(False)

        self.commandViewDisplaySecondaryPanel(True)
        self.commandViewHighlightPanel(0)
        self.commandViewMainSplitterPosition()
        self.commandViewShowImageFileOnly(self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY.id()))
        self.commandViewShowBackupFiles(self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP.id()))
        self.commandViewShowHiddenFiles(self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN.id()))

        for panelId in self.__window.panels:
            self.commandViewThumbnail(panelId, self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_THUMBNAIL.id()))

            self.commandPanelTabFilesLayout(panelId, self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_LAYOUT.id()))
            self.commandPanelTabFilesActive(panelId, BCMainViewTabFilesTabs.INFORMATIONS)
            self.commandPanelTabFilesPosition(panelId, [BCMainViewTabFilesTabs.INFORMATIONS, BCMainViewTabFilesTabs.DIRECTORIES_TREE])

            self.commandPanelTabActive(panelId, BCMainViewTabTabs.FILES)
            self.commandPanelTabPosition(panelId, [BCMainViewTabTabs.FILES, BCMainViewTabTabs.DOCUMENTS])

            self.commandPanelTabFilesNfoActive(panelId, BCMainViewTabFilesNfoTabs.GENERIC)

            self.commandPanelTabFilesSplitterFilesPosition(panelId)
            self.commandPanelTabFilesSplitterPreviewPosition(panelId)

            self.__window.panels[panelId].setAllowRefresh(True)

            self.__window.panels[panelId].setColumnSort([1, True])
            self.__window.panels[panelId].setColumnOrder([0,1,2,3,4,5,6,7,8])
            self.__window.panels[panelId].setColumnSize([0,0,0,0,0,0,0,0,0])
            self.__window.panels[panelId].setIconSize(self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_ICONSIZE.id()))

    def commandSettingsNavBarBtnHome(self, visible=True):
        """Set button home visible/hidden"""
        self.__settings.setOption(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HOME, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].showHome(visible)

    def commandSettingsNavBarBtnViews(self, visible=True):
        """Set button views visible/hidden"""
        self.__settings.setOption(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_VIEWS, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].showSavedView(visible)

    def commandSettingsNavBarBtnBookmarks(self, visible=True):
        """Set button bookmarks visible/hidden"""
        self.__settings.setOption(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BOOKMARKS, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].showBookmark(visible)

    def commandSettingsNavBarBtnHistory(self, visible=True):
        """Set button history visible/hidden"""
        self.__settings.setOption(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HISTORY, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].showHistory(visible)

    def commandSettingsNavBarBtnLastDocuments(self, visible=True):
        """Set button history visible/hidden"""
        self.__settings.setOption(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_LASTDOCUMENTS, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].showLastDocuments(visible)

    def commandSettingsNavBarBtnGoBack(self, visible=True):
        """Set button go back visible/hidden"""
        self.__settings.setOption(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BACK, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].showGoBack(visible)

    def commandSettingsNavBarBtnGoUp(self, visible=True):
        """Set button go up visible/hidden"""
        self.__settings.setOption(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_UP, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].showGoUp(visible)

    def commandSettingsNavBarBtnQuickFilter(self, visible=True):
        """Set button quick filter visible/hidden"""
        self.__settings.setOption(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_QUICKFILTER, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].showQuickFilter(visible)

    def commandInfoToClipBoardBorder(self, border=BCTable.BORDER_DOUBLE):
        """Set border for information panel content to clipboard"""
        self.__tableSettings.setBorder(border)

    def commandInfoToClipBoardHeader(self, header=True):
        """Set header for information panel content to clipboard"""
        self.__tableSettings.setHeaderActive(header)

    def commandInfoToClipBoardMinWidth(self, width=0):
        """Set minimum width for information panel content to clipboard"""
        self.__tableSettings.setMinWidth(width)

    def commandInfoToClipBoardMaxWidth(self, width=0):
        """Set maximum width for information panel content to clipboard"""
        self.__tableSettings.setMaxWidth(width)

    def commandInfoToClipBoardMinWidthActive(self, active=True):
        """Set minimum width active for information panel content to clipboard"""
        self.__tableSettings.setMinWidthActive(active)

    def commandInfoToClipBoardMaxWidthActive(self, active=False):
        """Set maximum width active for information panel content to clipboard"""
        self.__tableSettings.setMaxWidthActive(active)

    def commandSettingsOpen(self):
        """Open dialog box settings"""
        if BCSettingsDialogBox.open(f'{self.__bcName}::Settings', self):
            self.saveSettings()

    def commandAboutBc(self):
        """Display 'About Buli Commander' dialog box"""
        BCAboutWindow(self.__bcName, self.__bcVersion)

    # endregion: define commands -----------------------------------------------
