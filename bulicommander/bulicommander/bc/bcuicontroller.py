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
import hashlib

from PyQt5.Qt import *
from PyQt5.QtCore import (
        QDir,
        QRect
    )

from PyQt5.QtWidgets import (
        QWidget
    )


from .bcbookmark import BCBookmark
from .bcclipboard import (
        BCClipboard,
        BCClipboardItem,
        BCClipboardItemUrl,
        BCClipboardItemFile
    )
from .bcfile import (
        BCBaseFile,
        BCDirectory,
        BCFile,
        BCFileCache,
        BCFileManagedFormat,
        BCFileManipulateName
    )
from .bcfileoperation import (
        BCFileOperationUi,
        BCFileOperation
    )
from .bcexportfiles import BCExportFilesDialogBox
from .bcconvertfiles import BCConvertFilesDialogBox
from .bcsearchfiles import BCSearchFilesDialogBox
from .bchistory import BCHistory
from .bcmainviewtab import (
        BCMainViewTab,
        BCMainViewTabClipboardLayout,
        BCMainViewTabFilesLayout,
        BCMainViewTabFilesNfoTabs,
        BCMainViewTabFilesTabs,
        BCMainViewTabTabs
    )
from .bcmainwindow import BCMainWindow
from .bcsystray import BCSysTray
from .bcwpathbar import BCWPathBar
from .bcsettings import (
        BCSettings,
        BCSettingsDialogBox,
        BCSettingsKey,
        BCSettingsValues,
    )

from .bcimportanimated import (
        BCImportDialogBox,
        BCImportAnimated
    )
from .bcsavedview import BCSavedView

from bulicommander.pktk.modules.uitheme import UITheme
from bulicommander.pktk.modules.strtable import (
        TextTable,
        TextTableSettingsText
    )
from bulicommander.pktk.modules.utils import (
        checkKritaVersion,
        Debug
    )
from bulicommander.pktk.modules.imgutils import buildIcon
from bulicommander.pktk.modules.menuutils import (
        buildQAction,
        buildQMenu
    )
from bulicommander.pktk.modules.strutils import (
        getBytesSizeToStrUnit,
        setBytesSizeToStrUnit
    )
from bulicommander.pktk.modules.about import AboutWindow
from bulicommander.pktk.widgets.wimageview import WImageView
from bulicommander.pktk.widgets.wiodialog import (
        WDialogMessage,
        WDialogBooleanInput,
        WDialogRadioButtonChoiceInput
    )
from bulicommander.pktk.widgets.wsearchinput import WSearchInput
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )
from bulicommander.pktk.modules.ekrita import (
        EKritaNode
    )

from ..libs.breadcrumbsaddressbar.breadcrumbsaddressbar import BreadcrumbsAddressBar

# ------------------------------------------------------------------------------
class BCUIController(QObject):
    """The controller provide an access to all BuliCommander functions
    """
    __EXTENDED_OPEN_OK = 1
    __EXTENDED_OPEN_KO = -1
    __EXTENDED_OPEN_CANCEL = 0

    bcWindowShown = pyqtSignal()
    bcWindowClosed = pyqtSignal()

    def __init__(self, bcName="Buli Commander", bcVersion="testing", kritaIsStarting=False):
        super(BCUIController, self).__init__(None)

        self.__bcStarted = False
        self.__bcStarting = False

        self.__fontMono = QFont()
        self.__fontMono.setPointSize(9)
        self.__fontMono.setFamily('DejaVu Sans Mono, Consolas, Courier New')

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
        self.__tableSettings = TextTableSettingsText()

        self.__confirmAction = True

        BCSettings.load()

        UITheme.load()
        # BC theme must be loaded before systray is initialized
        UITheme.load(os.path.join(os.path.dirname(__file__), 'resources'))
        UITheme.load(os.path.join(os.path.dirname(__file__), 'resources', 'color_icons.rcc'), False)

        self.__systray=BCSysTray(self)
        self.commandSettingsSysTrayMode(BCSettings.get(BCSettingsKey.CONFIG_GLB_SYSTRAY_MODE))

        # store a global reference to activeWindow to be able to work with
        # activeWindow signals
        # https://krita-artists.org/t/krita-4-4-new-api/12247?u=grum999
        self.__kraActiveWindow = None

        self.__initialised = False

        # load last documents
        self.commandGoLastDocsOpenedSet(BCSettings.get(BCSettingsKey.SESSION_FILES_LASTDOC_O_ITEMS))
        self.commandGoLastDocsSavedSet(BCSettings.get(BCSettingsKey.SESSION_FILES_LASTDOC_S_ITEMS))

        BCFile.initialiseCache()
        BCClipboard.initialiseCache()
        BCFileCache.initialise()

        self.__clipboard = BCClipboard(False)

        # overrides native Krita Open dialog...
        self.commandSettingsOpenOverrideKrita(BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_OVERRIDEKRITA))
        # add action to file menu
        self.commandSettingsOpenFromFileMenu(BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_FROMKRITAMENU))

        if kritaIsStarting and BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_ATSTARTUP):
            self.start()


    def start(self):
        if self.__bcStarted:
            # user interface is already started, bring to front and exit
            self.commandViewBringToFront()
            return
        elif self.__bcStarting:
            # user interface is already starting, exit
            return

        self.__bcStarting = True

        # Check if windows are opened and then, connect signal if needed
        self.__checkKritaWindows()


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
            self.__bcStarted = True
            self.bcWindowShown.emit()
            self.updateMenuForPanel()
            self.__clipboardActive()
            # already initialised, do nothing
            return

        # Here we know we have an active window
        if self.__kraActiveWindow is None:
            self.__kraActiveWindow=Krita.instance().activeWindow()
        try:
            # should not occurs as uicontroller is initialised only once, but...
            self.__kraActiveWindow.themeChanged.disconnect(self.__themeChanged)
        except:
            pass
        self.__kraActiveWindow.themeChanged.connect(self.__themeChanged)


        self.__window.initMainView()

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(False)

        self.commandSettingsFileDefaultActionKra(BCSettings.get(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_KRA))
        self.commandSettingsFileDefaultActionOther(BCSettings.get(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_OTHER))
        self.commandSettingsFileNewFileNameKra(BCSettings.get(BCSettingsKey.CONFIG_FILES_NEWFILENAME_KRA))
        self.commandSettingsFileNewFileNameOther(BCSettings.get(BCSettingsKey.CONFIG_FILES_NEWFILENAME_OTHER))
        self.commandSettingsFileUnit(BCSettings.get(BCSettingsKey.CONFIG_GLB_FILE_UNIT))
        self.commandSettingsHistoryMaxSize(BCSettings.get(BCSettingsKey.CONFIG_FILES_HISTORY_MAXITEMS))
        self.commandSettingsHistoryKeepOnExit(BCSettings.get(BCSettingsKey.CONFIG_FILES_HISTORY_KEEPONEXIT))
        self.commandSettingsLastDocsMaxSize(BCSettings.get(BCSettingsKey.CONFIG_FILES_LASTDOC_MAXITEMS))
        self.commandSettingsSaveSessionOnExit(BCSettings.get(BCSettingsKey.CONFIG_SESSION_SAVE))
        self.commandSettingsSysTrayMode(BCSettings.get(BCSettingsKey.CONFIG_GLB_SYSTRAY_MODE))
        self.commandSettingsOpenAtStartup(BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_ATSTARTUP))
        self.commandSettingsOpenOverrideKrita(BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_OVERRIDEKRITA))
        self.commandSettingsOpenFromFileMenu(BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_FROMKRITAMENU))

        self.commandViewMainWindowGeometry(BCSettings.get(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY))
        self.commandViewMainWindowMaximized(BCSettings.get(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED))
        self.commandViewMainSplitterPosition(BCSettings.get(BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION))
        self.commandViewDisplaySecondaryPanel(BCSettings.get(BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE))
        self.commandViewHighlightPanel(BCSettings.get(BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED))
        self.commandViewShowImageFileOnly(BCSettings.get(BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY))
        self.commandViewShowBackupFiles(BCSettings.get(BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP))
        self.commandViewShowHiddenFiles(BCSettings.get(BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN))

        # load history
        self.commandGoHistorySet(BCSettings.get(BCSettingsKey.SESSION_FILES_HISTORY_ITEMS))
        # load bookmarks
        self.commandGoBookmarkSet(BCSettings.get(BCSettingsKey.SESSION_FILES_BOOKMARK_ITEMS))
        # load saved views
        self.commandGoSavedViewSet(BCSettings.get(BCSettingsKey.SESSION_FILES_SAVEDVIEWS_ITEMS))

        self.commandSettingsNavBarBtnHome(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_HOME))
        self.commandSettingsNavBarBtnViews(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_VIEWS))
        self.commandSettingsNavBarBtnBookmarks(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_BOOKMARKS))
        self.commandSettingsNavBarBtnHistory(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_HISTORY))
        self.commandSettingsNavBarBtnLastDocuments(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_LASTDOCUMENTS))
        self.commandSettingsNavBarBtnGoBack(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_BACK))
        self.commandSettingsNavBarBtnGoUp(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_UP))
        self.commandSettingsNavBarBtnQuickFilter(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_QUICKFILTER))

        self.commandInfoToClipBoardBorder(BCSettings.get(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_BORDER))
        self.commandInfoToClipBoardHeader(BCSettings.get(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_HEADER))
        self.commandInfoToClipBoardMaxWidth(BCSettings.get(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH))
        self.commandInfoToClipBoardMinWidth(BCSettings.get(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH))
        self.commandInfoToClipBoardMaxWidthActive(BCSettings.get(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE))
        self.commandInfoToClipBoardMinWidthActive(BCSettings.get(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE))

        self.commandSettingsFilesNfoGridMode(BCSettings.get(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_LAYOUT))
        self.commandSettingsFilesNfoGridPropertiesFields(BCSettings.get(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_FIELDS))
        self.commandSettingsFilesNfoGridOverMinSize(BCSettings.get(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_OVERMINSIZE))

        self.commandSettingsClipboardDefaultAction(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_DEFAULT_ACTION))
        self.commandSettingsClipboardCacheMode(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MODE_GENERAL))
        self.commandSettingsClipboardCacheMaxSize(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MAXISZE))
        self.commandSettingsClipboardCachePersistent(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_PERSISTENT))
        self.commandSettingsClipboardUrlAutomaticDownload(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_URL_AUTOLOAD))
        self.commandSettingsClipboardUrlParseTextHtml(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_URL_PARSE_TEXTHTML))
        self.commandSettingsClipboardPasteAsNewDocument(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_PASTE_MODE_ASNEWDOC))

        self.commandSettingsToolbars(BCSettings.get(BCSettingsKey.CONFIG_TOOLBARS), BCSettings.get(BCSettingsKey.SESSION_TOOLBARS))

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setFilesHistory(self.__history)
            self.__window.panels[panelId].setFilesBookmark(self.__bookmark)
            self.__window.panels[panelId].setFilesSavedView(self.__savedView)
            self.__window.panels[panelId].setFilesLastDocumentsOpened(self.__lastDocumentsOpened)
            self.__window.panels[panelId].setFilesLastDocumentsSaved(self.__lastDocumentsSaved)
            self.__window.panels[panelId].setFilesBackupFilterDView(self.__backupFilterDView)
            self.__window.panels[panelId].setFilesLayerFilterDView(self.__fileLayerFilterDView)

            self.__window.panels[panelId].setFilesImageNfoSizeUnit(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_IMGSIZEUNIT.id(panelId=panelId)))

            self.commandPanelTabActive(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId)))
            self.commandPanelTabPosition(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId)))

            self.commandPanelClipboardTabLayout(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_LAYOUT.id(panelId=panelId)))

            self.commandPanelFilesTabLayout(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_LAYOUT.id(panelId=panelId)))
            self.commandPanelFilesTabActive(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId)))
            self.commandPanelFilesTabPosition(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId)))

            self.commandPanelFilesTabNfoActive(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId)))
            self.commandPanelFilesTabSplitterClipboardPosition(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_SPLITTER_CLIPBOARD_POSITION.id(panelId=panelId)))
            self.commandPanelFilesTabSplitterFilesPosition(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_SPLITTER_FILES_POSITION.id(panelId=panelId)))
            self.commandPanelFilesTabSplitterPreviewPosition(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_SPLITTER_PREVIEW_POSITION.id(panelId=panelId)))

            self.commandPanelPath(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_CURRENTPATH.id(panelId=panelId)), True)

            self.commandPanelFilterValue(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_FILTERVALUE.id(panelId=panelId)))
            self.commandPanelFilterOptions(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_FILTEROPTIONS.id(panelId=panelId)))
            self.commandPanelFilterVisible(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_FILTERVISIBLE.id(panelId=panelId)))

            self.commandViewThumbnail(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_THUMBNAIL.id(panelId=panelId)))

            self.commandPanelPreviewBackground(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_PREVIEW_BACKGROUND.id(panelId=panelId)))

            self.__window.panels[panelId].setFilesColumnSort(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNSORT.id(panelId=panelId)))
            self.__window.panels[panelId].setFilesColumnOrder(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNORDER.id(panelId=panelId)))
            self.__window.panels[panelId].setFilesColumnSize(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNSIZE.id(panelId=panelId)))
            self.__window.panels[panelId].setFilesColumnVisible(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNVISIBLE.id(panelId=panelId)))
            self.__window.panels[panelId].setFilesIconSizeTv(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_ICONSIZE_TV.id(panelId=panelId)))
            self.__window.panels[panelId].setFilesIconSizeLv(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_ICONSIZE_LV.id(panelId=panelId)))

            self.__window.panels[panelId].setClipboardColumnSort(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNSORT.id(panelId=panelId)))
            self.__window.panels[panelId].setClipboardColumnOrder(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNORDER.id(panelId=panelId)))
            self.__window.panels[panelId].setClipboardColumnSize(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNSIZE.id(panelId=panelId)))
            self.__window.panels[panelId].setClipboardIconSize(BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_ICONSIZE.id(panelId=panelId)))

            self.commandPanelFilesTabViewMode(panelId, BCSettings.get(BCSettingsKey.SESSION_PANEL_VIEW_FILES_VIEWMODE.id(panelId=panelId)))

        self.__window.initMenu()

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(True)

        self.__initialised = True
        self.__bcStarted = True
        self.__bcStarting = False
        self.bcWindowShown.emit()
        self.updateMenuForPanel()
        self.__clipboardActive()


    def __extendedOpen(self, file):
        bcfile = BCFile(file)
        if bcfile.format() in BCImportAnimated.SUPPORTED_FORMAT:
            imgNfo = bcfile.getMetaInformation()
            if imgNfo['imageCount'] > 1:
                dialogTitle=f'{self.__bcName}::Import {bcfile.format()} file'
                userChoice = BCImportDialogBox.open(dialogTitle, bcfile, self.panel())

                result=BCImportAnimated.IMPORT_KO
                if userChoice[0]:
                    if userChoice[1] == BCImportDialogBox.IMPORT_AS_FRAMELAYER:
                        result=BCImportAnimated.importAsFrames(dialogTitle, bcfile, userChoice[2])
                    elif userChoice[1] == BCImportDialogBox.IMPORT_AS_STACKLAYER:
                        result=BCImportAnimated.importAsLayers(dialogTitle, bcfile)
                    elif userChoice[1] == BCImportDialogBox.IMPORT_AS_FRAME:
                        result=BCImportAnimated.importInOneLayer(bcfile, userChoice[2])
                    #else:
                    #   krita's import mode=KO
                else:
                    # cancel
                    result=BCImportAnimated.IMPORT_CANCELLED

                if result==BCImportAnimated.IMPORT_OK:
                    return BCUIController.__EXTENDED_OPEN_OK
                elif result==BCImportAnimated.IMPORT_CANCELLED:
                    return BCUIController.__EXTENDED_OPEN_CANCEL
        return BCUIController.__EXTENDED_OPEN_KO


    def __themeChanged(self):
        """Theme has been changed, reload resources"""
        def buildPixmapList(widget):
            pixmaps=[]
            for propertyName in widget.dynamicPropertyNames():
                pName=bytes(propertyName).decode()
                if re.match('__bcIcon_', pName):
                    # a reference to resource path has been stored,
                    # reload icon from it
                    if pName == '__bcIcon_normalon':
                        pixmaps.append( (QPixmap(widget.property(propertyName)), QIcon.Normal, QIcon.On) )
                    elif pName == '__bcIcon_normaloff':
                        pixmaps.append( (QPixmap(widget.property(propertyName)), QIcon.Normal, QIcon.Off) )
                    elif pName == '__bcIcon_disabledon':
                        pixmaps.append( (QPixmap(widget.property(propertyName)), QIcon.Disabled, QIcon.On) )
                    elif pName == '__bcIcon_disabledoff':
                        pixmaps.append( (QPixmap(widget.property(propertyName)), QIcon.Disabled, QIcon.Off) )
                    elif pName == '__bcIcon_activeon':
                        pixmaps.append( (QPixmap(widget.property(propertyName)), QIcon.Active, QIcon.On) )
                    elif pName == '__bcIcon_activeoff':
                        pixmaps.append( (QPixmap(widget.property(propertyName)), QIcon.Active, QIcon.Off) )
                    elif pName == '__bcIcon_selectedon':
                        pixmaps.append( (QPixmap(widget.property(propertyName)), QIcon.Selected, QIcon.On) )
                    elif pName == '__bcIcon_selectedoff':
                        pixmaps.append( (QPixmap(widget.property(propertyName)), QIcon.Selected, QIcon.Off) )
            return pixmaps

        UITheme.reloadResources()

        # need to apply new palette to widgets
        # otherwise it seems they keep to refer to the old palette...
        palette = QApplication.palette()
        widgetList = self.__window.getWidgets()

        for widget in widgetList:
            if isinstance(widget, BCWPathBar) or isinstance(widget, BreadcrumbsAddressBar):
                widget.updatePalette()
            elif hasattr(widget, 'setPalette'):
                # force palette to be applied to widget
                widget.setPalette(palette)

            if isinstance(widget, QTabWidget):
                # For QTabWidget, it's not possible to set icon directly,
                # need to use setTabIcon()
                for tabIndex in range(widget.count()):
                    tabWidget = widget.widget(tabIndex)

                    if not widget.tabIcon(tabIndex) is None:
                        pixmaps=buildPixmapList(tabWidget)
                        if len(pixmaps) > 0:
                            widget.setTabIcon(tabIndex, buildIcon(pixmaps))

            # need to do something to relad icons...
            elif hasattr(widget, 'icon'):
                pixmaps=buildPixmapList(widget)
                if len(pixmaps) > 0:
                    widget.setIcon(buildIcon(pixmaps))


    def __checkKritaWindows(self):
        """Check if windows signal windowClosed() is already defined and, if not,
        define it
        """
        # applicationClosing signal can't be used, because when while BC is opened,
        # application is still running and then signal is not trigerred..
        #
        # solution is, when a window is closed, to check how many windows are still
        # opened
        #
        for window in Krita.instance().windows():
            # DO NOT SET PROPERTY ON WINDOW
            # but on qwindow() as the qwindow() is always the same
            # and as window is just an instance that wrap the underlied QMainWindow
            # a new object is returned each time windows() list is returned
            if window.qwindow().property('__bcWindowClosed') != True:
                window.windowClosed.connect(self.__windowClosed)
                window.qwindow().setProperty('__bcWindowClosed', True)


    def __windowClosed(self):
        """A krita window has been closed"""
        # check how many windows are still opened
        # if there's no window opened, close BC

        # need to ensure that all windows are connected to close signal
        # (maybe, since BC has been opened, new Krita windows has been created...)
        self.__checkKritaWindows()

        if len( Krita.instance().windows()) == 0:
            self.commandQuit()


    def __overrideOpenKrita(self):
        """Overrides the native "Open" Krita dialogcommand with BuliCommander"""
        if checkKritaVersion(5,0,0) and BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_OVERRIDEKRITA):
            # override the native "Open" Krita command with Buli Commander
            # notes:
            #   - once it's applied, to reactivate native Open Dialog file
            #     Krita must be restarted
            #   - deactivated for Krita < 5.0.0 as only krita 5.0.0 is able to initialize BC at startup
            actionOpen=Krita.instance().action("file_open")
            actionOpen.disconnect()
            actionOpen.triggered.connect(lambda checked : self.start())


    def __clipboardActive(self):
        """Determinate, according to options, if clipboard is active or not"""
        mode = self.commandSettingsClipboardCacheMode()

        if mode == BCSettingsValues.CLIPBOARD_MODE_ALWAYS:
            if self.__systray.visible():
                self.__clipboard.setEnabled(self.commandSettingsClipboardCacheSystrayMode())
            else:
                self.__clipboard.setEnabled(True)
        elif mode == BCSettingsValues.CLIPBOARD_MODE_ACTIVE:
            if self.__systray.visible():
                self.__clipboard.setEnabled(self.commandSettingsClipboardCacheSystrayMode())
            else:
                self.__clipboard.setEnabled(self.started())
        else:
            self.__clipboard.setEnabled(False)


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

    def panels(self):
        """Return current panels"""
        return [self.__window.panels[panelId] for panelId in self.__window.panels]

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

    def quickRefDict(self):
        """Return a dictionnary of quick references

        key = reference (a saved view Id @xxxx or a bpookmark id @xxxx)
        value = (Type, Icon, Case sensitive)
        """
        iconSavedView = buildIcon("pktk:saved_view_file")
        iconBookmark = buildIcon("pktk:bookmark")
        iconSearchResult = buildIcon("pktk:search")

        returned = {'@home': (BCWPathBar.QUICKREF_RESERVED_HOME, buildIcon("pktk:home"), 'Home'),
                    '@last': (BCWPathBar.QUICKREF_RESERVED_LAST_ALL, buildIcon("pktk:saved_view_last"), 'Last opened/saved documents'),
                    '@last opened': (BCWPathBar.QUICKREF_RESERVED_LAST_OPENED, buildIcon("pktk:saved_view_last"), 'Last opened documents'),
                    '@last saved': (BCWPathBar.QUICKREF_RESERVED_LAST_SAVED, buildIcon("pktk:saved_view_last"), 'Last saved documents'),
                    '@history': (BCWPathBar.QUICKREF_RESERVED_HISTORY, buildIcon("pktk:history"), 'History directories'),
                    '@backup filter': (BCWPathBar.QUICKREF_RESERVED_BACKUPFILTERDVIEW, buildIcon("pktk:filter_alt"), 'Backup files list'),
                    '@file layer filter': (BCWPathBar.QUICKREF_RESERVED_FLAYERFILTERDVIEW, buildIcon("pktk:image"), 'Layer files list')
                    }

        if not self.__bookmark is None and self.__bookmark.length() > 0:
            for bookmark in self.__bookmark.list():
                returned[f'@{bookmark[0].lower()}']=(BCWPathBar.QUICKREF_BOOKMARK, iconBookmark, bookmark[0])

        if not self.__savedView is None and self.__savedView.length() > 0:
            for savedView in self.__savedView.list():
                if not re.match("^searchresult:", savedView[0]):
                    returned[f'@{savedView[0].lower()}']=(BCWPathBar.QUICKREF_SAVEDVIEW_LIST, iconSavedView, savedView[0])
                else:
                    returned[f'@{savedView[0].lower()}']=(BCWPathBar.QUICKREF_SAVEDVIEW_LIST, iconSearchResult, savedView[0])

        return returned

    def quickRefPath(self, refId):
        """Return path from reserved value or bookmark reference

        Return None if not found
        """
        refId=refId.lstrip('@').lower()

        if refId == 'home':
            path = ''
            if BCSettings.get(BCSettingsKey.CONFIG_FILES_HOME_DIR_MODE) == BCSettingsValues.HOME_DIR_UD:
                path = BCSettings.get(BCSettingsKey.CONFIG_FILES_HOME_DIR_UD)

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

    def started(self):
        """Return True if BuliCommander interface is started"""
        return self.__bcStarted

    def bcVersion(self):
        return self.__bcVersion

    def bcName(self):
        return self.__bcName

    def bcTitle(self):
        return self.__bcTitle

    def clipboard(self):
        """Return clipboard instance"""
        return self.__clipboard

    def window(self):
        """return mainwindow"""
        return self.__window

    # endregion: getter/setters ------------------------------------------------


    # region: define commands --------------------------------------------------

    def saveSettings(self):
        """Save the current settings"""
        # get current toolbar configuration from settings as dict for which key is toolbar id
        toolbarSettings={toolbar['id']: toolbar for toolbar in BCSettings.get(BCSettingsKey.CONFIG_TOOLBARS)}
        toolbarSession=[]
        # loop over toolbar to update settings: visibility, area, position
        for toolbar in self.__window.toolbarList():
            id=toolbar.objectName()
            if id in toolbarSettings:
                geometry=toolbar.frameGeometry()
                toolbarSession.append({
                        'id': id,
                        'visible': toolbar.isVisible(),
                        'area': self.__window.toolBarArea(toolbar),
                        'break': self.__window.toolBarBreak(toolbar),
                        'rect': [geometry.left(), geometry.top(), geometry.width(), geometry.height()]
                    })
        # save toolbars session informations
        BCSettings.set(BCSettingsKey.SESSION_TOOLBARS, toolbarSession)


        BCSettings.set(BCSettingsKey.CONFIG_SESSION_SAVE, self.__window.actionSettingsSaveSessionOnExit.isChecked())

        if BCSettings.get(BCSettingsKey.CONFIG_SESSION_SAVE):
            # save current session properties only if allowed
            if self.__window.actionViewDisplaySecondaryPanel.isChecked():
                # if not checked, hidden panel size is 0 so, do not save it (splitter position is already properly defined)
                BCSettings.set(BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION, self.__window.splitterMainView.sizes())

            BCSettings.set(BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE, self.__window.actionViewDisplaySecondaryPanel.isChecked())
            BCSettings.set(BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED, self.__window.highlightedPanel())

            BCSettings.set(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED, self.__window.isMaximized())
            if not self.__window.isMaximized():
                # when maximized geometry is full screen geomtry, then do it only if no in maximized
                BCSettings.set(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY, [self.__window.geometry().x(), self.__window.geometry().y(), self.__window.geometry().width(), self.__window.geometry().height()])

            BCSettings.set(BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY, self.__window.actionViewShowImageFileOnly.isChecked())
            BCSettings.set(BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP, self.__window.actionViewShowBackupFiles.isChecked())
            BCSettings.set(BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN, self.__window.actionViewShowHiddenFiles.isChecked())

            # normally shouldn't be necessary
            if getBytesSizeToStrUnit() == 'auto':
                BCSettings.set(BCSettingsKey.CONFIG_GLB_FILE_UNIT, BCSettingsValues.FILE_UNIT_KB)
            else:
                BCSettings.set(BCSettingsKey.CONFIG_GLB_FILE_UNIT, BCSettingsValues.FILE_UNIT_KIB)

            for panelId in self.__window.panels:
                currentPath=self.__window.panels[panelId].filesPath()
                if re.match("@searchresult:", currentPath):
                    currentPath="@home"
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_CURRENTPATH.id(panelId=panelId), currentPath)
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_LAYOUT.id(panelId=panelId), self.__window.panels[panelId].filesTabLayout().value)
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_VIEWMODE.id(panelId=panelId), self.__window.panels[panelId].filesTabViewMode())

                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_THUMBNAIL.id(panelId=panelId), self.__window.panels[panelId].filesViewThumbnail())

                filterText, filterOptions=self.__window.panels[panelId].filesFilter()
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_FILTERVISIBLE.id(panelId=panelId), self.__window.panels[panelId].filesFilterVisible())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_FILTERVALUE.id(panelId=panelId), filterText)
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_FILTEROPTIONS.id(panelId=panelId), filterOptions&WSearchInput.OPTION_ALL) # avoid OPTION_FILTER_MARKED_ACTIVE as merkers are not kept accross sessions

                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNSORT.id(panelId=panelId), self.__window.panels[panelId].filesColumnSort())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNORDER.id(panelId=panelId), self.__window.panels[panelId].filesColumnOrder())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNSIZE.id(panelId=panelId), self.__window.panels[panelId].filesColumnSize())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNVISIBLE.id(panelId=panelId), self.__window.panels[panelId].filesColumnVisible())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_ICONSIZE_TV.id(panelId=panelId), self.__window.panels[panelId].filesIconSizeTv())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_ICONSIZE_LV.id(panelId=panelId), self.__window.panels[panelId].filesIconSizeLv())

                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_FILES_IMGSIZEUNIT.id(panelId=panelId), self.__window.panels[panelId].filesImageNfoSizeUnit())

                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_LAYOUT.id(panelId=panelId), self.__window.panels[panelId].clipboardTabLayout().value)
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNSORT.id(panelId=panelId), self.__window.panels[panelId].clipboardColumnSort())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNORDER.id(panelId=panelId), self.__window.panels[panelId].clipboardColumnOrder())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNSIZE.id(panelId=panelId), self.__window.panels[panelId].clipboardColumnSize())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_ICONSIZE.id(panelId=panelId), self.__window.panels[panelId].clipboardIconSize())

                BCSettings.set(BCSettingsKey.SESSION_PANEL_PREVIEW_BACKGROUND.id(panelId=panelId), self.__window.panels[panelId].previewBackground())

                BCSettings.set(BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId), [tab.value for tab in self.__window.panels[panelId].tabOrder()])
                BCSettings.set(BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId), [tab.value for tab in self.__window.panels[panelId].filesTabOrder()])
                BCSettings.set(BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId), self.__window.panels[panelId].tabActive().value)
                BCSettings.set(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId), self.__window.panels[panelId].filesTabActive().value)
                BCSettings.set(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId), self.__window.panels[panelId].filesTabNfoActive().value)

                BCSettings.set(BCSettingsKey.SESSION_PANEL_SPLITTER_CLIPBOARD_POSITION.id(panelId=panelId), self.__window.panels[panelId].clipboardTabSplitterPosition())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_SPLITTER_FILES_POSITION.id(panelId=panelId), self.__window.panels[panelId].filesTabSplitterFilesPosition())
                BCSettings.set(BCSettingsKey.SESSION_PANEL_SPLITTER_PREVIEW_POSITION.id(panelId=panelId), self.__window.panels[panelId].filesTabSplitterPreviewPosition())

            if BCSettings.get(BCSettingsKey.CONFIG_FILES_HISTORY_KEEPONEXIT):
                BCSettings.set(BCSettingsKey.SESSION_FILES_HISTORY_ITEMS, [directory for directory in self.__history.list() if not re.match("@searchresult:", directory)])
            else:
                BCSettings.set(BCSettingsKey.SESSION_FILES_HISTORY_ITEMS, [])

            BCSettings.set(BCSettingsKey.SESSION_FILES_BOOKMARK_ITEMS, self.__bookmark.list())
            BCSettings.set(BCSettingsKey.SESSION_FILES_SAVEDVIEWS_ITEMS, [savedViewItem for savedViewItem in self.__savedView.list() if not re.match("^searchresult:", savedViewItem[0])] )
            BCSettings.set(BCSettingsKey.SESSION_FILES_LASTDOC_O_ITEMS, self.__lastDocumentsOpened.list())
            BCSettings.set(BCSettingsKey.SESSION_FILES_LASTDOC_S_ITEMS, self.__lastDocumentsSaved.list())

            BCSettings.set(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_BORDER, self.__tableSettings.border())
            BCSettings.set(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_HEADER, self.__tableSettings.headerActive())
            BCSettings.set(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH, self.__tableSettings.minWidth())
            BCSettings.set(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH, self.__tableSettings.maxWidth())
            BCSettings.set(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE, self.__tableSettings.minWidthActive())
            BCSettings.set(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE, self.__tableSettings.maxWidthActive())

        return BCSettings.save()

    def updateMenuForPanel(self):
        """Update menu (enabled/disabled/checked/unchecked) according to current panel"""
        def enableSubMenu(enabled, menu):
            menu.setEnabled(enabled)
            if len(menu.actions())>0:
                for action in menu.actions():
                    if not action.isSeparator():
                        if action.menu() and len(action.menu().actions())>0:
                            enableSubMenu(enabled, action.menu())
                        else:
                            action.setEnabled(enabled)

        def buildMenuGoHistory():
            """Build menu history"""
            # remove history entry, only keep "clear history" and "separator"
            for action in [action for action in self.__window.menuGoHistory.actions() if (action.objectName()=='' and not action.isSeparator())]:
                self.__window.menuGoHistory.removeAction(action)

            if not self.__history is None:
                self.__history.removeMissing(False, refList=self.quickRefDict())

            if not self.__history is None and self.__history.length() > 0:
                self.__window.actionGoHistoryClearHistory.setEnabled(True)
                self.__window.actionGoHistoryClearHistory.setText(i18n(f'Clear history ({self.__history.length()})'))

                self.__window.menuGoHistory.addSeparator()
                for path in reversed(self.__history.list()):
                    action = QAction(path.replace('&', '&&'), self)
                    action.setFont(self.__fontMono)
                    action.setProperty('path', path)
                    action.triggered.connect(lambda: self.commandGoTo(self.panelId(), self.sender().property('path')))

                    self.__window.menuGoHistory.addAction(action)
            else:
                self.__window.actionGoHistoryClearHistory.setEnabled(False)
                self.__window.actionGoHistoryClearHistory.setText(i18n('Clear history'))

        def buildMenuGoBookmarks():
            """Build menu bookmarks"""
            def menuBookmarks_Clicked(panelId, action):
                # change directory
                path=action.property('path')
                if not path is None:
                    if os.path.isdir(path):
                        self.commandGoTo(panelId, path)
                    else:
                        name = self.bookmark().nameFromValue(path)
                        self.commandGoBookmarkRemoveUI(name)

            for action in [action for action in self.__window.menuGoBookmark.actions() if (action.objectName()=='' and not action.isSeparator())]:
                self.__window.menuGoBookmark.removeAction(action)

            if not self.__bookmark is None and self.__bookmark.length() > 0:
                self.__window.actionGoBookmarksClearBookmarks.setEnabled(True)
                self.__window.actionGoBookmarksClearBookmarks.setText(i18n('Clear bookmarks')+f' ({self.__bookmark.length()})')

                currentPath = self.panel().filesPath()
                isInBookmark = False

                for bookmark in self.__bookmark.list():
                    action = QAction(bookmark[BCBookmark.NAME].replace('&', '&&'), self)
                    action.setFont(self.__fontMono)
                    action.setProperty('path', bookmark[BCBookmark.VALUE])

                    if os.path.isdir(bookmark[BCBookmark.VALUE]):
                        action.setCheckable(True)
                        action.setStatusTip(bookmark[BCBookmark.VALUE])

                        if currentPath == bookmark[BCBookmark.VALUE]:
                            action.setChecked(True)
                            isInBookmark = True
                        else:
                            action.setChecked(False)
                    else:
                        action.setCheckable(False)
                        action.setStatusTip(f'Directory "{bookmark[BCBookmark.VALUE]}" is missing')
                        action.setIcon(buildIcon('pktk:warning'))

                    action.triggered.connect(lambda: menuBookmarks_Clicked(self.panelId(), self.sender()))

                    self.__window.menuGoBookmark.addAction(action)

                if isInBookmark:
                    self.__window.actionGoBookmarksAddBookmark.setEnabled(False)
                    self.__window.actionGoBookmarksRemoveFromBookmark.setEnabled(True)
                    self.__window.actionGoBookmarksRenameBookmark.setEnabled(True)
                else:
                    self.__window.actionGoBookmarksAddBookmark.setEnabled(self.panel().filesPathMode() != BCWPathBar.MODE_SAVEDVIEW)
                    self.__window.actionGoBookmarksRemoveFromBookmark.setEnabled(False)
                    self.__window.actionGoBookmarksRenameBookmark.setEnabled(False)
            else:
                self.__window.actionGoBookmarksClearBookmarks.setEnabled(False)
                self.__window.actionGoBookmarksClearBookmarks.setText(i18n('Clear bookmark'))
                self.__window.actionGoBookmarksAddBookmark.setEnabled(self.panel().filesPathMode() != BCWPathBar.MODE_SAVEDVIEW)
                self.__window.actionGoBookmarksRemoveFromBookmark.setEnabled(False)
                self.__window.actionGoBookmarksRenameBookmark.setEnabled(False)

        def buildMenuGoSavedViews():
            """Build menu bookmarks"""
            for action in [action for action in self.__window.menuGoSavedViews.actions() if (action.objectName()=='' and not (action.isSeparator() or action.menu()))]:
                self.__window.menuGoSavedViews.removeAction(action)

            for action in [action for action in self.__window.menuGoSavedViewsAddToView.actions() if (action.objectName()=='' and not action.isSeparator())]:
                self.__window.menuGoSavedViewsAddToView.removeAction(action)

            allowAddRemove = False
            if self.panel().filesSelected()[3] > 0:
                # Selected nb directories + files > 0
                # can be added to a current view
                allowAddRemove = True

            isSavedView = (self.quickRefType(self.panel().filesPath()) == BCWPathBar.QUICKREF_SAVEDVIEW_LIST)

            if self.__savedView.length() > 0:
                # there's some view saved
                # build list of saved views

                for view in self.__savedView.list():
                    # view = (name, files)
                    if not re.match("^searchresult:", view[0]):
                        action = buildQAction("pktk:saved_view_file", view[0].replace('&', '&&'), self)
                        action.setFont(self.__fontMono)
                        action.setStatusTip(i18n(f"Add selected files to view '{view[0].replace('&', '&&')}' (Current files in view: {len(view[1])})" ))
                        action.setProperty('path', f'{view[0]}')
                        action.triggered.connect(lambda: self.commandGoSavedViewAppend(self.sender().property('path'), [file.fullPathName() for file in self.panel().filesSelected()[0]]))

                        if isSavedView and self.__savedView.current(True) == view[0] or not allowAddRemove:
                            action.setEnabled(False)

                        self.__window.menuGoSavedViewsAddToView.addAction(action)

                        action = buildQAction("pktk:saved_view_file", view[0].replace('&', '&&'), self)
                        action.setFont(self.__fontMono)
                        action.setCheckable(True)
                        action.setStatusTip(i18n(f'Files in view: {len(view[1])}'))
                        action.setProperty('path', f'@{view[0]}')
                        action.triggered.connect(lambda: self.commandGoTo(self.panelId(), self.sender().property('path')))

                        if isSavedView and self.__savedView.current(True) == view[0]:
                            action.setChecked(True)

                        self.__window.menuGoSavedViews.addAction(action)

            self.__window.actionGoSavedViewsAddToViewNewView.setEnabled(allowAddRemove)
            if isSavedView:
                self.__window.actionGoSavedViewsClearViewContent.setEnabled(True)
                self.__window.actionGoSavedViewsRemoveFromView.setEnabled(allowAddRemove)
                self.__window.actionGoSavedViewsRenameView.setEnabled(True)
                self.__window.actionGoSavedViewsDeleteView.setEnabled(True)
            else:
                self.__window.actionGoSavedViewsClearViewContent.setEnabled(False)
                self.__window.actionGoSavedViewsRemoveFromView.setEnabled(False)
                self.__window.actionGoSavedViewsRenameView.setEnabled(False)
                self.__window.actionGoSavedViewsDeleteView.setEnabled(False)

        def buildMenuViewLayout():
            """Build menu layout"""
            if self.__window.actionViewLayoutIconSize is None:
                # not yet initialized
                return

            try:
                self.__window.actionViewLayoutTopBottom.triggered.disconnect()
                self.__window.actionViewLayoutLeftRight.triggered.disconnect()
                self.__window.actionViewLayoutBottomTop.triggered.disconnect()
                self.__window.actionViewLayoutRightLeft.triggered.disconnect()
                self.__window.actionViewLayoutFullMode.triggered.disconnect()
            except:
                pass

            if self.panel().tabActive()==BCMainViewTabTabs.FILES:
                self.__window.actionViewLayoutFullMode.setVisible(True)
                self.__window.actionViewLayoutFullMode.triggered.connect(lambda: self.commandPanelFilesTabLayout(self.panelId(), BCMainViewTabFilesLayout.FULL ))
                self.__window.actionViewLayoutTopBottom.triggered.connect(lambda: self.commandPanelFilesTabLayout(self.panelId(), BCMainViewTabFilesLayout.TOP ))
                self.__window.actionViewLayoutLeftRight.triggered.connect(lambda: self.commandPanelFilesTabLayout(self.panelId(), BCMainViewTabFilesLayout.LEFT ))
                self.__window.actionViewLayoutBottomTop.triggered.connect(lambda: self.commandPanelFilesTabLayout(self.panelId(), BCMainViewTabFilesLayout.BOTTOM ))
                self.__window.actionViewLayoutRightLeft.triggered.connect(lambda: self.commandPanelFilesTabLayout(self.panelId(), BCMainViewTabFilesLayout.RIGHT ))

                layout=self.panel().filesTabLayout()

                if self.panel().filesTabViewMode()==BCMainViewTab.VIEWMODE_TV:
                    self.__window.actionViewLayoutViewAsList.setChecked(True)
                    iconSize=self.panel().filesIconSizeTv()
                    iconPixelSize=self.panel().filesIconSizeTv(True)
                    maxIconSize=BCMainViewTab.MAX_ICON_SIZE_FILE_TV
                else:
                    self.__window.actionViewLayoutViewAsGrid.setChecked(True)
                    iconSize=self.panel().filesIconSizeLv()
                    iconPixelSize=self.panel().filesIconSizeLv(True)
                    maxIconSize=BCMainViewTab.MAX_ICON_SIZE_FILE_LV

                self.__window.actionViewLayoutViewAsList.setVisible(True)
                self.__window.actionViewLayoutViewAsGrid.setVisible(True)
                self.__window.actionViewLayoutIconSize.setVisible(True)

                if layout==BCMainViewTabFilesLayout.FULL:
                    self.__window.actionViewLayoutFullMode.setChecked(True)
                elif layout==BCMainViewTabFilesLayout.TOP:
                    self.__window.actionViewLayoutTopBottom.setChecked(True)
                elif layout==BCMainViewTabFilesLayout.LEFT:
                    self.__window.actionViewLayoutLeftRight.setChecked(True)
                elif layout==BCMainViewTabFilesLayout.BOTTOM:
                    self.__window.actionViewLayoutBottomTop.setChecked(True)
                elif layout==BCMainViewTabFilesLayout.RIGHT:
                    self.__window.actionViewLayoutRightLeft.setChecked(True)

            elif self.panel().tabActive()==BCMainViewTabTabs.CLIPBOARD:
                self.__window.actionViewLayoutFullMode.setVisible(False)
                self.__window.actionViewLayoutTopBottom.triggered.connect(lambda: self.commandPanelClipboardTabLayout(self.panelId(), BCMainViewTabClipboardLayout.TOP ))
                self.__window.actionViewLayoutLeftRight.triggered.connect(lambda: self.commandPanelClipboardTabLayout(self.panelId(), BCMainViewTabClipboardLayout.LEFT ))
                self.__window.actionViewLayoutBottomTop.triggered.connect(lambda: self.commandPanelClipboardTabLayout(self.panelId(), BCMainViewTabClipboardLayout.BOTTOM ))
                self.__window.actionViewLayoutRightLeft.triggered.connect(lambda: self.commandPanelClipboardTabLayout(self.panelId(), BCMainViewTabClipboardLayout.RIGHT ))

                layout=self.panel().clipboardTabLayout()
                iconSize=self.panel().clipboardIconSize()
                iconPixelSize=self.panel().clipboardIconSize(True)
                maxIconSize=BCMainViewTab.MAX_ICON_SIZE_CLIPBOARD

                self.__window.actionViewLayoutViewAsList.setVisible(False)
                self.__window.actionViewLayoutViewAsGrid.setVisible(False)
                self.__window.actionViewLayoutIconSize.setVisible(True)

                if layout==BCMainViewTabClipboardLayout.TOP:
                    self.__window.actionViewLayoutTopBottom.setChecked(True)
                elif layout==BCMainViewTabClipboardLayout.LEFT:
                    self.__window.actionViewLayoutLeftRight.setChecked(True)
                elif layout==BCMainViewTabClipboardLayout.BOTTOM:
                    self.__window.actionViewLayoutBottomTop.setChecked(True)
                elif layout==BCMainViewTabClipboardLayout.RIGHT:
                    self.__window.actionViewLayoutRightLeft.setChecked(True)
            else:
                self.__window.actionViewLayoutViewAsList.setVisible(False)
                self.__window.actionViewLayoutViewAsGrid.setVisible(False)
                self.__window.actionViewLayoutIconSize.setVisible(False)
                return

            self.__window.actionViewLayoutIconSize.slider().setMaximum(maxIconSize)
            self.__window.actionViewLayoutIconSize.slider().setValue(iconSize)
            self.__window.actionViewLayoutIconSize.setLabelText(i18n(f"Icon size: {iconPixelSize}px"))

        #print("updateMenuForPanel", self.panel().tabActive(), self.panelId())

        self.__window.actionViewThumbnail.setChecked(self.panel().filesViewThumbnail())
        self.__window.actionViewDisplayQuickFilter.setChecked(self.panel().filesFilterVisible())

        if self.panel().tabActive() == BCMainViewTabTabs.FILES:
            self.__window.actionClipboardQuit.setShortcut(QKeySequence())
            self.__window.actionClipboardOpen.setShortcut(QKeySequence())
            self.__window.actionClipboardPushBack.setShortcut(QKeySequence())
            self.__window.actionFileQuit.setShortcut("CTRL+Q")
            self.__window.actionFileOpen.setShortcut("CTRL+O")
            self.__window.actionToolsCopyToClipboard.setShortcut("CTRL+C")

            self.__window.menuFile.menuAction().setVisible(True)
            self.__window.menuClipboard.menuAction().setVisible(False)
            self.__window.menuDocument.menuAction().setVisible(False)
            self.__window.menuGo.menuAction().setVisible(True)

            enableSubMenu(True, self.__window.menuFile)
            enableSubMenu(False, self.__window.menuClipboard)
            enableSubMenu(False, self.__window.menuDocument)
            enableSubMenu(True, self.__window.menuGo)

            selectionInfo = self.panel().filesSelected()
            markedInfo = self.panel().filesMarked()

            oppositeTargetReady=self.panel(False).targetDirectoryReady()

            self.__window.actionFileOpen.setEnabled(selectionInfo[4]>0)
            self.__window.actionFileOpenAsNewDocument.setEnabled(selectionInfo[4]>0)
            self.__window.actionFileCopyToOtherPanel.setEnabled(oppositeTargetReady and (selectionInfo[3]>0))
            self.__window.actionFileMoveToOtherPanel.setEnabled(oppositeTargetReady and (selectionInfo[3]>0))
            self.__window.actionFileDelete.setEnabled(selectionInfo[3]>0)

            if Krita.instance().activeDocument():
                allow=self.panel().filesAllowPasteFilesAsRefimg([item.fullPathName() for item in selectionInfo[0] if isinstance(item, BCFile)])
                self.__window.actionFileOpenAsImageReference.setEnabled(allow)
                self.__window.actionFileOpenAsLayer.setEnabled(selectionInfo[4]>0)
                self.__window.actionFileOpenAsFileLayer.setEnabled(selectionInfo[4]>0)
            else:
                self.__window.actionFileOpenAsImageReference.setEnabled(False)
                self.__window.actionFileOpenAsLayer.setEnabled(False)
                self.__window.actionFileOpenAsFileLayer.setEnabled(False)

            # ^ ==> xor logical operator
            # Can do rename if:
            #   - one or more files are selected [2]
            # exclusive or
            #   - one or more directory is selected [1]
            #
            self.__window.actionFileRename.setEnabled( (selectionInfo[2]>0) ^ (selectionInfo[1]>0))

            self.__window.actionFileCopyToOtherPanelNoConfirm.setEnabled(selectionInfo[3]>0)
            self.__window.actionFileMoveToOtherPanelNoConfirm.setEnabled(selectionInfo[3]>0)
            self.__window.actionFileDeleteNoConfirm.setEnabled(selectionInfo[3]>0)

            self.__window.actionMenuEditSelectAll.setEnabled(True)
            self.__window.actionMenuEditSelectNone.setEnabled(True)
            self.__window.actionMenuEditSelectInvert.setEnabled(True)
            self.__window.actionMenuEditSelectMarked.setEnabled(markedInfo[0]>0)
            self.__window.actionMenuEditSelectMarked.setVisible(True)

            self.__window.actionMenuEditMarkUnmark.setEnabled(True)
            self.__window.actionMenuEditMarkAll.setEnabled(True)
            self.__window.actionMenuEditMarkNone.setEnabled(True)
            self.__window.actionMenuEditMarkInvert.setEnabled(True)
            self.__window.actionMenuEditMarkUnmark.setVisible(True)
            self.__window.actionMenuEditMarkAll.setVisible(True)
            self.__window.actionMenuEditMarkNone.setVisible(True)
            self.__window.actionMenuEditMarkInvert.setVisible(True)

            self.__window.actionViewThumbnail.setEnabled(True)
            self.__window.actionViewShowImageFileOnly.setEnabled(True)
            self.__window.actionViewShowBackupFiles.setEnabled(self.optionViewFileManagedOnly())
            self.__window.actionViewShowHiddenFiles.setEnabled(True)
            self.__window.actionViewDisplaySecondaryPanel.setEnabled(True)
            self.__window.actionViewDisplayQuickFilter.setEnabled(True)

            for panelId in range(len(self.__window.menuViewDisplayLayoutFiles)):
                self.__window.menuViewDisplayLayoutFiles[panelId].setVisible(panelId==self.panelId())
                self.__window.menuViewDisplayLayoutFiles[panelId].setEnabled(panelId==self.panelId())

            for panelId in range(len(self.__window.menuViewDisplayLayoutClipboard)):
                self.__window.menuViewDisplayLayoutClipboard[panelId].setVisible(False)
                self.__window.menuViewDisplayLayoutClipboard[panelId].setEnabled(False)

            self.__window.actionGoBack.setEnabled(self.panel().filesGoBackEnabled())
            self.__window.actionGoUp.setEnabled(self.panel().filesGoUpEnabled())
            buildMenuGoHistory()
            buildMenuGoBookmarks()
            buildMenuGoSavedViews()
            buildMenuViewLayout()

            self.__window.actionToolsCopyToClipboard.setEnabled(selectionInfo[3]>0)
            self.__window.actionToolsExportFiles.setEnabled(True)
            self.__window.actionToolsConvertFiles.setEnabled(True)
        elif self.panel().tabActive() == BCMainViewTabTabs.CLIPBOARD:
            self.__window.actionFileQuit.setShortcut(QKeySequence())
            self.__window.actionFileOpen.setShortcut(QKeySequence())
            self.__window.actionToolsCopyToClipboard.setShortcut(QKeySequence())
            self.__window.actionClipboardQuit.setShortcut("CTRL+Q")
            self.__window.actionClipboardOpen.setShortcut("CTRL+O")
            self.__window.actionClipboardPushBack.setShortcut("CTRL+C")

            self.__window.menuFile.menuAction().setVisible(False)
            self.__window.menuClipboard.menuAction().setVisible(True)
            self.__window.menuDocument.menuAction().setVisible(False)
            self.__window.menuGo.menuAction().setVisible(False)

            enableSubMenu(False, self.__window.menuFile)
            enableSubMenu(True, self.__window.menuClipboard)
            enableSubMenu(False, self.__window.menuDocument)
            enableSubMenu(False, self.__window.menuGo)

            selectionInfo = self.panel().clipboardSelected()

            self.__window.actionClipboardCheckContent.setVisible(not self.__clipboard.enabled())

            if self.__clipboard.length()==0:
                self.__window.actionMenuEditSelectAll.setEnabled(False)
                self.__window.actionMenuEditSelectNone.setEnabled(False)
                self.__window.actionMenuEditSelectInvert.setEnabled(False)
            else:
                self.__window.actionMenuEditSelectAll.setEnabled(True)
                self.__window.actionMenuEditSelectNone.setEnabled(True)
                self.__window.actionMenuEditSelectInvert.setEnabled(True)

            self.__window.actionMenuEditSelectMarked.setEnabled(False)
            self.__window.actionMenuEditSelectMarked.setVisible(False)

            self.__window.actionMenuEditMarkUnmark.setVisible(False)
            self.__window.actionMenuEditMarkAll.setVisible(False)
            self.__window.actionMenuEditMarkNone.setVisible(False)
            self.__window.actionMenuEditMarkInvert.setVisible(False)
            self.__window.actionMenuEditMarkUnmark.setEnabled(False)
            self.__window.actionMenuEditMarkAll.setEnabled(False)
            self.__window.actionMenuEditMarkNone.setEnabled(False)
            self.__window.actionMenuEditMarkInvert.setEnabled(False)

            if selectionInfo[1]==1:
                # nb item selected(1)
                self.__window.actionClipboardPushBack.setEnabled(True)

                if Krita.instance().activeDocument():
                    self.__window.actionClipboardPasteAsNewLayer.setEnabled(True)
                    self.__window.actionClipboardPasteAsRefImage.setEnabled(len([item for item in selectionInfo[0] if item.type()!="BCClipboardItemSvg"])>0)
                else:
                    self.__window.actionClipboardPasteAsNewLayer.setEnabled(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_PASTE_MODE_ASNEWDOC))
                    self.__window.actionClipboardPasteAsRefImage.setEnabled(False)

                self.__window.actionClipboardPasteAsNewDocument.setEnabled(True)
                self.__window.actionClipboardOpen.setEnabled(True)

                if selectionInfo[11]==1:
                    # nb item persistent(11)
                    self.__window.actionClipboardSetPersistent.setEnabled(False)
                    self.__window.actionClipboardSetNotPersistent.setEnabled(True)
                else:
                    self.__window.actionClipboardSetPersistent.setEnabled(True)
                    self.__window.actionClipboardSetNotPersistent.setEnabled(False)

                if selectionInfo[9]==1:
                    # nb item not downloaded(9)
                    self.__window.actionClipboardStartDownload.setEnabled(True)
                    self.__window.actionClipboardStopDownload.setEnabled(False)
                elif selectionInfo[10]==1:
                    # nb item downloading(10)
                    self.__window.actionClipboardStartDownload.setEnabled(False)
                    self.__window.actionClipboardStopDownload.setEnabled(True)
                else:
                    self.__window.actionClipboardStartDownload.setEnabled(False)
                    self.__window.actionClipboardStopDownload.setEnabled(False)
            elif selectionInfo[1]>1:
                # multiple items selected
                self.__window.actionClipboardPushBack.setEnabled(True)

                if Krita.instance().activeDocument():
                    self.__window.actionClipboardPasteAsNewLayer.setEnabled(True)
                    self.__window.actionClipboardPasteAsRefImage.setEnabled(len([item for item in selectionInfo[0] if item.type()!="BCClipboardItemSvg"])>0)
                else:
                    self.__window.actionClipboardPasteAsNewLayer.setEnabled(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_PASTE_MODE_ASNEWDOC))
                    self.__window.actionClipboardPasteAsRefImage.setEnabled(False)

                self.__window.actionClipboardPasteAsNewDocument.setEnabled(True)
                self.__window.actionClipboardOpen.setEnabled(True)

                if selectionInfo[11]==0:
                    # nb item persistent(11)
                    self.__window.actionClipboardSetPersistent.setEnabled(True)
                    self.__window.actionClipboardSetNotPersistent.setEnabled(False)
                elif selectionInfo[11]==selectionInfo[1]:
                    self.__window.actionClipboardSetPersistent.setEnabled(False)
                    self.__window.actionClipboardSetNotPersistent.setEnabled(True)
                else:
                    # a mix...
                    self.__window.actionClipboardSetPersistent.setEnabled(True)
                    self.__window.actionClipboardSetNotPersistent.setEnabled(True)

                if selectionInfo[9]==0:
                    # nb item not downloaded(9)
                    self.__window.actionClipboardStartDownload.setEnabled(False)
                else:
                    self.__window.actionClipboardStartDownload.setEnabled(True)

                if selectionInfo[10]==0:
                    # nb item downloading(10)
                    self.__window.actionClipboardStopDownload.setEnabled(False)
                else:
                    self.__window.actionClipboardStopDownload.setEnabled(True)
            else:
                # nothing selected
                self.__window.actionClipboardPushBack.setEnabled(False)
                self.__window.actionClipboardPasteAsNewLayer.setEnabled(False)
                self.__window.actionClipboardPasteAsNewDocument.setEnabled(False)
                self.__window.actionClipboardPasteAsRefImage.setEnabled(False)
                self.__window.actionClipboardOpen.setEnabled(False)
                self.__window.actionClipboardSetPersistent.setEnabled(False)
                self.__window.actionClipboardSetNotPersistent.setEnabled(False)
                self.__window.actionClipboardStartDownload.setEnabled(False)
                self.__window.actionClipboardStopDownload.setEnabled(False)

            self.__window.actionViewThumbnail.setEnabled(False)
            self.__window.actionViewShowImageFileOnly.setEnabled(False)
            self.__window.actionViewShowBackupFiles.setEnabled(False)
            self.__window.actionViewShowHiddenFiles.setEnabled(False)
            self.__window.actionViewDisplaySecondaryPanel.setEnabled(True)
            self.__window.actionViewDisplayQuickFilter.setEnabled(False)

            for panelId in range(len(self.__window.menuViewDisplayLayoutFiles)):
                self.__window.menuViewDisplayLayoutFiles[panelId].setVisible(False)
                self.__window.menuViewDisplayLayoutFiles[panelId].setEnabled(False)

            for panelId in range(len(self.__window.menuViewDisplayLayoutClipboard)):
                self.__window.menuViewDisplayLayoutClipboard[panelId].setVisible(panelId==self.panelId())
                self.__window.menuViewDisplayLayoutClipboard[panelId].setEnabled(panelId==self.panelId())

            buildMenuViewLayout()

            self.__window.actionToolsCopyToClipboard.setEnabled(False)
            self.__window.actionToolsExportFiles.setEnabled(False)
            self.__window.actionToolsConvertFiles.setEnabled(False)
        elif self.panel().tabActive() == BCMainViewTabTabs.DOCUMENTS:
            self.__window.actionFileQuit.setShortcut(QKeySequence())
            self.__window.actionFileOpen.setShortcut(QKeySequence())
            self.__window.actionClipboardQuit.setShortcut(QKeySequence())
            self.__window.actionClipboardOpen.setShortcut(QKeySequence())

            self.__window.menuFile.menuAction().setVisible(False)
            self.__window.menuClipboard.menuAction().setVisible(False)
            self.__window.menuDocument.menuAction().setVisible(False)
            self.__window.menuGo.menuAction().setVisible(False)

            enableSubMenu(False, self.__window.menuFile)
            enableSubMenu(False, self.__window.menuClipboard)
            enableSubMenu(False, self.__window.menuDocument)
            enableSubMenu(False, self.__window.menuGo)

            self.__window.actionMenuEditSelectAll.setEnabled(False)
            self.__window.actionMenuEditSelectNone.setEnabled(False)
            self.__window.actionMenuEditSelectInvert.setEnabled(False)
            self.__window.actionMenuEditSelectMarked.setEnabled(False)
            self.__window.actionMenuEditSelectMarked.setVisible(False)

            self.__window.actionMenuEditMarkUnmark.setVisible(False)
            self.__window.actionMenuEditMarkAll.setVisible(False)
            self.__window.actionMenuEditMarkNone.setVisible(False)
            self.__window.actionMenuEditMarkInvert.setVisible(False)
            self.__window.actionMenuEditMarkUnmark.setEnabled(False)
            self.__window.actionMenuEditMarkAll.setEnabled(False)
            self.__window.actionMenuEditMarkNone.setEnabled(False)
            self.__window.actionMenuEditMarkInvert.setEnabled(False)


            self.__window.actionViewThumbnail.setEnabled(False)
            self.__window.actionViewShowImageFileOnly.setEnabled(False)
            self.__window.actionViewShowBackupFiles.setEnabled(False)
            self.__window.actionViewShowHiddenFiles.setEnabled(False)
            self.__window.actionViewDisplaySecondaryPanel.setEnabled(True)
            self.__window.actionViewDisplayQuickFilter.setEnabled(False)

            for panelId in range(len(self.__window.menuViewDisplayLayoutFiles)):
                self.__window.menuViewDisplayLayoutFiles[panelId].setVisible(False)
                self.__window.menuViewDisplayLayoutFiles[panelId].setEnabled(False)

            for panelId in range(len(self.__window.menuViewDisplayLayoutClipboard)):
                self.__window.menuViewDisplayLayoutClipboard[panelId].setVisible(False)
                self.__window.menuViewDisplayLayoutClipboard[panelId].setEnabled(False)

            self.__window.actionToolsCopyToClipboard.setEnabled(False)
            self.__window.actionToolsExportFiles.setEnabled(False)
            self.__window.actionToolsConvertFiles.setEnabled(False)

    def close(self):
        """When window is about to be closed, execute some cleanup/backup/stuff before exiting BuliCommander"""
        # save current settings
        self.saveSettings()

        # stop all async processes (thumbnail generating)
        for panelRef in self.__window.panels:
            self.__window.panels[panelRef].close()

        self.__bcStarted = False
        self.bcWindowClosed.emit()
        self.__clipboardActive()

    def filesSetAllowRefresh(self, allow):
        """change allow refresh for both panels"""
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(allow)

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
        return BCSettings.get(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_KRA)

    def optionFileDefaultActionOther(self):
        """Return current option value"""
        return BCSettings.get(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_OTHER)

    def optionHistoryMaxSize(self):
        """Return current option value"""
        return BCSettings.get(BCSettingsKey.CONFIG_FILES_HISTORY_MAXITEMS)

    def optionClipboardDefaultAction(self):
        """Return default option value for clipboard"""
        return BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_DEFAULT_ACTION)

    def commandQuit(self):
        """Close Buli Commander"""
        BCFileCache.finalize()
        self.__window.close()

    def commandFileOpen(self, file=None):
        """Open file"""
        if file is None:
            selectionInfo = self.panel().filesSelected()
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

            # unable to process file, try default Krita import
            try:
                document = Krita.instance().openDocument(file)
                view = Krita.instance().activeWindow().addView(document)
                Krita.instance().activeWindow().showView(view)
            except Exception as e:
                Debug.print('[BCUIController.commandFileOpen] unable to open file {0}: {1}', file, f"{e}")
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

    def commandFileOpenAsNew(self, file=None, newFileNameFromSettings=True):
        """Open file as new document"""
        if file is None:
            selectionInfo = self.panel().filesSelected()
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
            if newFileNameFromSettings:
                if bcFile.format() == BCFileManagedFormat.KRA:
                    newFileName =BCFileManipulateName.parseFileNameKw(bcFile, BCSettings.get(BCSettingsKey.CONFIG_FILES_NEWFILENAME_KRA))
                else:
                    newFileName =BCFileManipulateName.parseFileNameKw(bcFile, BCSettings.get(BCSettingsKey.CONFIG_FILES_NEWFILENAME_OTHER))

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
                Debug.print('[BCUIController.commandFileOpenAsNew] unable to open file {0}: {1}', file, f"{e}")
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

    def commandFileOpenAsImageReference(self, file=None):
        """Open file as new document"""
        if file is None:
            selectionInfo = self.panel().filesSelected()
            if selectionInfo[4] > 0:
                nbOpened = 0
                for file in selectionInfo[0]:
                    if isinstance(file, BCFile) and file.readable():
                        if self.commandFileOpenAsImageReference(file.fullPathName()):
                            nbOpened+=1
                if nbOpened!=selectionInfo[4]:
                    return False
                else:
                    return True
        elif isinstance(file, BCFile) and file.readable():
            return self.commandFileOpenAsImageReference(file.fullPathName())
        elif isinstance(file, str):
            hash=hashlib.md5()
            hash.update(file.encode())
            cbFile = BCClipboardItemFile(hash.hexdigest(), file, saveInCache=False, persistent=False)
            self.commandClipboardPasteAsRefImage(cbFile)
            return True
        else:
            raise EInvalidType('Given `file` is not valid')

    def commandFileOpenAsImageReferenceCloseBC(self, file=None):
        """Open file and close BuliCommander"""
        if self.commandFileOpenAsImageReference(file):
            self.commandQuit()
            return True
        return False

    def commandFileOpenAsLayer(self, file=None):
        """Open file as layer"""
        def importFileAsLayer(file):
            document=Krita.instance().activeDocument()

            if file.format()==BCFileManagedFormat.SVG:
                try:
                    with open(file.fullPathName(), 'r') as fHandle:
                        svgContent=fHandle.read()
                except Exception as e:
                    return False

                fileName=file.fullPathName()
                importedFile=document.createVectorLayer(i18n(f"BC - Layer ({fileName})"))
                importedFile.addShapesFromSvg(svgContent)
            else:
                fileName=file.fullPathName()
                importedFile=document.createNode(i18n(f"BC - Layer ({fileName})"), "paintlayer")
                EKritaNode.fromQImage(importedFile, file.image())

            activeNode=document.activeNode()
            activeNode.parentNode().addChildNode(importedFile, activeNode)
            return True

        if file is None:
            selectionInfo = self.panel().filesSelected()
            if selectionInfo[4] > 0:
                nbOpened = 0
                for file in selectionInfo[0]:
                    if isinstance(file, BCFile) and file.readable():
                        if importFileAsLayer(file):
                            nbOpened+=1
                if nbOpened!=selectionInfo[4]:
                    return False
                else:
                    return True
        elif isinstance(file, BCFile) and file.readable():
            return importFileAsLayer(file)
        elif isinstance(file, str):
            if os.path.isfile(file):
                return importFileAsLayer(BCFile(file))
            else:
                return False
        else:
            raise EInvalidType('Given `file` is not valid')

    def commandFileOpenAsLayerCloseBC(self, file=None):
        """Open file as layer and close BuliCommander"""
        if self.commandFileOpenAsLayer(file):
            self.commandQuit()
            return True
        return False

    def commandFileOpenAsFileLayer(self, file=None, scalingMode=None):
        """Open file as file layer"""
        def scaleMode(applyForAll=False):
            if applyForAll:
                applyForAll=i18n("Apply for all image")
            else:
                applyForAll=None

            return WDialogRadioButtonChoiceInput.display(i18n(f"{self.__bcName}::Open as File layer"),
                                                            "<h1>Scaling mode</h1><p>Please choose a scaling mode for File layer</p>",
                                                            choicesValue=[
                                                                i18n("No scaling"),
                                                                i18n("Scale to Image Size"),
                                                                i18n("Adapt to Image Resolution (ppi)")],
                                                            optionalCheckboxMsg=applyForAll
                                                        )

        if file is None:
            selectionInfo = self.panel().filesSelected()
            if selectionInfo[4] > 0:
                moreThanOneFile=selectionInfo[4]>1
                applyToAll=False
                nbOpened = 0
                for file in selectionInfo[0]:
                    if isinstance(file, BCFile) and file.readable():
                        if applyToAll==False or scalingMode is None:
                            if moreThanOneFile:
                                scalingMode, applyToAll=scaleMode(moreThanOneFile)
                            else:
                                scalingMode=scaleMode(moreThanOneFile)

                        if scalingMode is None and (applyToAll or not moreThanOneFile):
                            return False

                        if self.commandFileOpenAsFileLayer(file.fullPathName(), scalingMode):
                            nbOpened+=1
                if nbOpened!=selectionInfo[4]:
                    return False
                else:
                    return True
        elif isinstance(file, BCFile) and file.readable():
            return self.commandFileOpenAsFileLayer(file.fullPathName(), scalingMode)
        elif isinstance(file, str):
            if scalingMode is None:
                scalingMode=scaleMode()

            if scalingMode is None:
                # user cancelled action
                return False
            elif scalingMode==0:
                scalingMode="None"
            elif scalingMode==1:
                scalingMode="ToImageSize"
            elif scalingMode==2:
                scalingMode="ToImagePPI"

            fileName=os.path.basename(file)
            document=Krita.instance().activeDocument()
            activeNode=document.activeNode()
            activeNode.parentNode().addChildNode(document.createFileLayer(i18n(f"BC - File layer ({fileName})"), file, scalingMode), activeNode)

            return True
        else:
            raise EInvalidType('Given `file` is not valid')

    def commandFileOpenAsFileLayerCloseBC(self, file=None):
        """Open file as file layer and close BuliCommander"""
        if self.commandFileOpenAsFileLayer(file):
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
            targetPath = self.panel().filesPath()

        newPath = BCFileOperationUi.createDir(self.__bcName, targetPath)
        if not newPath is None:
            if not BCFileOperation.createDir(self.__bcName, newPath):
                WDialogMessage.display(
                        i18n(f"{self.__bcName}::Create directory"),
                        "".join([i18n("<h1 class='warning'>Warning!</h1>"),
                                 i18n(f"""<p>Unable to create directory <span style="font-family:'consolas, monospace'; font-weight:bold; white-space: nowrap;">{newPath}</span></p>""")])
                    )

    def commandFileDelete(self, confirm=True):
        """Delete file(s)"""

        selectedFiles = self.panel().filesSelected()
        if confirm:
            choice = BCFileOperationUi.delete(self.__bcName, selectedFiles[2], selectedFiles[1], selectedFiles[5])
            if not choice:
                return

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(False)

        BCFileOperation.delete(self.__bcName, selectedFiles[5])

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(True)

    def commandFileCopy(self, confirm=True):
        """Copy file(s)"""
        targetPath = self.panel(False).filesPath()
        selectedFiles = self.panel().filesSelected()
        if confirm:
            choice = BCFileOperationUi.copy(self.__bcName, selectedFiles[2], selectedFiles[1], selectedFiles[5], targetPath)
            if not choice:
                return
            targetPath = BCFileOperationUi.path()

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(False)

        BCFileOperation.copy(self.__bcName, selectedFiles[5], targetPath)

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(True)

    def commandFileMove(self, confirm=True):
        """Move file(s)"""
        targetPath = self.panel(False).filesPath()
        selectedFiles = self.panel().filesSelected()
        if confirm:
            choice = BCFileOperationUi.move(self.__bcName, selectedFiles[2], selectedFiles[1], selectedFiles[5], targetPath)
            if not choice:
                return
            targetPath = BCFileOperationUi.path()

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(False)

        BCFileOperation.move(self.__bcName, selectedFiles[5], targetPath)

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(True)

    def commandFileRename(self):
        """Rename file(s)"""
        selectedFiles = self.panel().filesSelected()
        renameAction = BCFileOperationUi.rename(self.__bcName, selectedFiles[0])
        if renameAction is None:
            return

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(False)

        BCFileOperation.rename(self.__bcName, renameAction['files'], renameAction['rule'])

        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesSetAllowRefresh(True)

    def commandClipboardCheckContent(self):
        """Check clipboard content manually"""
        self.__clipboard.checkContent()

    def commandClipboardDefaultAction(self, item):
        """Execute default action on item"""
        if item is None:
            return

        if self.optionClipboardDefaultAction() == BCSettingsValues.CLIPBOARD_ACTION_NLAYER:
            self.commandClipboardPasteAsNewLayer(item)
        elif self.optionClipboardDefaultAction() == BCSettingsValues.CLIPBOARD_ACTION_NDOCUMENT:
            self.commandClipboardPasteAsNewDocument(item)

    def commandClipboardPushBackClipboard(self, items=None):
        """Push back items to clipboard"""
        if items is None:
            selectionInfo = self.panel().clipboardSelected()
            if selectionInfo[1]>0:
                self.commandClipboardPushBackClipboard(selectionInfo[0])
        else:
            self.__clipboard.pushBackToClipboard(items)

    def commandClipboardPasteAsNewLayer(self, items=None):
        """Push back items to clipboard and paste them as new layers"""
        if Krita.instance().activeDocument() is None:
            if BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_PASTE_MODE_ASNEWDOC):
                self.commandClipboardPasteAsNewDocument(items)
            return

        if items is None:
            selectionInfo = self.panel().clipboardSelected()
            if selectionInfo[1]>0:
                for item in selectionInfo[0]:
                    self.commandClipboardPasteAsNewLayer(item)
        elif isinstance(items, BCClipboardItem):
            if items.type() in ('BCClipboardItemUrl', 'BCClipboardItemFile'):
                image=QImage(items.fileName())
                if image:
                    document=Krita.instance().activeDocument()
                    activeNode=document.activeNode()

                    if items.type()=='BCClipboardItemUrl':
                        layerName=items.url().url()
                    else:
                        layerName=items.fileName()

                    newLayer=document.createNode(i18n(f'Pasted from {layerName}'), 'paintlayer')

                    EKritaNode.fromQImage(newLayer, image)

                    if activeNode.type()=='grouplayer':
                        activeNode.addChildNode(newLayer, None)
                    else:
                        activeNode.parentNode().addChildNode(newLayer, EKritaNode.above(activeNode))
            else:
                self.__clipboard.pushBackToClipboard(items)
                Krita.instance().action('edit_paste').trigger()

    def commandClipboardPasteAsNewDocument(self, items=None):
        """Push back items to clipboard and paste them as new document"""
        if items is None:
            selectionInfo = self.panel().clipboardSelected()
            if selectionInfo[1]>0:
                for item in selectionInfo[0]:
                    self.commandClipboardPasteAsNewDocument(item)
        elif isinstance(items, BCClipboardItem):
            if (items.type()=='BCClipboardItemKra' and items.origin()=='application/x-krita-node') or (items.type() in ('BCClipboardItemUrl', 'BCClipboardItemFile', 'BCClipboardItemImg', 'BCClipboardItemSvg')):
                self.commandFileOpenAsNew(items.fileName(), False)
            else:
                # krita selection...
                self.__clipboard.pushBackToClipboard(items)
                Krita.instance().action('paste_new').trigger()

    def commandClipboardPasteAsRefImage(self, items=None):
        """Push back items to clipboard and paste them as reference image"""
        if items is None:
            selectionInfo = self.panel().clipboardSelected()
            if selectionInfo[1]>0:
                for item in selectionInfo[0]:
                    self.commandClipboardPasteAsRefImage(item)
        elif isinstance(items, BCClipboardItem):
            self.__clipboard.pushBackToClipboard(items, True)
            Krita.instance().action('paste_as_reference').trigger()

    def commandClipboardOpen(self, items=None):
        """Open selected items from clipboard

        If item is a file, open file
        Otherwise, open file as a new document
        """
        if items is None:
            selectionInfo = self.panel().clipboardSelected()
            if selectionInfo[1]>0:
                for item in selectionInfo[0]:
                    self.commandClipboardOpen(item)
        elif isinstance(items, BCClipboardItem):
            if items.type() == 'BCClipboardItemFile':
                self.commandFileOpen(items.fileName())
            else:
                self.commandClipboardPasteAsNewDocument(items)

    def commandClipboardStartDownload(self, items=None):
        """Start download for selected items (that can be donwloaded)"""
        if items is None:
            selectionInfo = self.panel().clipboardSelected()
            if selectionInfo[1]>0:
                self.__clipboard.startDownload(selectionInfo[0])
        elif isinstance(items, BCClipboardItem):
            self.__clipboard.startDownload(items)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].clipboardRefresh()

    def commandClipboardStopDownload(self, items=None):
        """Stop download for selected items that currently are downloading"""
        if items is None:
            selectionInfo = self.panel().clipboardSelected()
            if selectionInfo[1]>0:
                self.__clipboard.stopDownload(selectionInfo[0])
        elif isinstance(items, BCClipboardItem):
            self.__clipboard.stopDownload(items)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].clipboardRefresh()

    def commandClipboardSetPersistent(self, item=None, persistent=True):
        """Set item as persistent/non-persistent"""
        if not isinstance(persistent, bool):
            raise EInvalidType("Given `persistent` must be a <bool>")

        if item is None:
            selectionInfo = self.panel().clipboardSelected()
            if selectionInfo[1]>0:
                for panelId in self.__window.panels:
                    self.__window.panels[panelId].clipboardSetAllowRefresh(False)
                for item in selectionInfo[0]:
                    self.commandClipboardSetPersistent(item, persistent)
                for panelId in self.__window.panels:
                    self.__window.panels[panelId].clipboardSetAllowRefresh(True)
        elif isinstance(item, BCClipboardItem):
            item.setPersistent(persistent)

    def commandViewBringToFront(self):
        """Bring main window to front"""
        self.__window.setWindowState( (self.__window.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.__window.activateWindow()

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
            BCSettings.set(BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION, self.__window.splitterMainView.sizes())


        self.__window.panels[1].setVisible(displaySecondary)
        self.__window.actionViewSwapPanels.setEnabled(displaySecondary)

        if not displaySecondary:
            # when the right panel is hidden, ensure the left is highlighted
            self.__window.panels[0].setHighlighted(True)

        self.updateMenuForPanel()

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
            BCSettings.set(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY, [self.__window.geometry().x(), self.__window.geometry().y(), self.__window.geometry().width(), self.__window.geometry().height()])
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
        self.__window.panels[panel].setFilesViewThumbnail(mode)

        self.updateMenuForPanel()

        return mode

    def commandViewDisplayQuickFilter(self, panel=None, mode=None):
        """Set current view mode"""
        if panel is None:
            panel = self.panelId()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if mode is None or not isinstance(mode, bool):
            mode = False

        self.__window.actionViewDisplayQuickFilter.setChecked(mode)
        self.__window.panels[panel].setFilesFilterVisible(mode)

        self.updateMenuForPanel()

        return mode

    def commandPanelPreviewBackground(self, panel=None, mode=None):
        """Set current preview view mode"""
        if panel is None:
            panel = self.panelId()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if not mode in WImageView.backgroundList():
            mode = WImageView.BG_CHECKER_BOARD

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
            self.__window.panels[panelId].filesRefresh()

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
            self.__window.panels[panelId].filesRefresh()

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
            self.__window.panels[panelId].setFilesHiddenPath(value)

        return value

    def commandPanelClipboardTabLayout(self, panel, value):
        """Set panel layout"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if isinstance(value, str):
            value = BCMainViewTabClipboardLayout(value)

        self.__window.panels[panel].setClipboardTabLayout(value)

        return value

    def commandPanelFilesTabViewMode(self, panel, value):
        """Set panel view mode"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        self.__window.panels[panel].setFilesTabViewMode(value)

        return value

    def commandPanelFilesTabLayout(self, panel, value):
        """Set panel layout"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if isinstance(value, str):
            value = BCMainViewTabFilesLayout(value)

        self.__window.panels[panel].setFilesTabLayout(value)

        return value

    def commandPanelFilesTabActive(self, panel, value):
        """Set active tab for files tab for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if isinstance(value, str):
            value = BCMainViewTabFilesTabs(value)

        self.__window.panels[panel].setFilesTabActive(value)

        return value

    def commandPanelFilesTabPosition(self, panel, value):
        """Set tabs positions for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        self.__window.panels[panel].setFilesTabOrder(value)

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

    def commandPanelFilesTabNfoActive(self, panel, value):
        """Set active tab for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        if isinstance(value, str):
            value = BCMainViewTabFilesNfoTabs(value)

        self.__window.panels[panel].setFilesTabNfoActive(value)

        return value

    def commandPanelFilesTabSplitterClipboardPosition(self, panel, positions=None):
        """Set splitter position for tab clipboard for given panel

        Given `positions` is a list [<panel0 size>,<panel1 size>]
        If value is None, will define a default 50%-50%
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setClipboardTabSplitterPosition(positions)

    def commandPanelFilesTabSplitterFilesPosition(self, panel, positions=None):
        """Set splitter position for tab files for given panel

        Given `positions` is a list [<panel0 size>,<panel1 size>]
        If value is None, will define a default 50%-50%
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setFilesTabSplitterFilesPosition(positions)

    def commandPanelFilesTabSplitterPreviewPosition(self, panel, positions=None):
        """Set splitter position for tab preview for given panel

        Given `positions` is a list [<panel0 size>,<panel1 size>]
        If value is None, will define a default 50%-50%
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setFilesTabSplitterPreviewPosition(positions)

    def commandPanelPath(self, panel, path=None, force=False):
        """Define path for given panel

        If `force` is True, force to set path even if path already set with given value (do a "refresh")
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        returned = self.__window.panels[panel].setFilesPath(path, force)
        self.updateMenuForPanel()
        return returned

    def commandPanelSelectAll(self, panel=None):
        """Select all item"""
        if panel is None:
            panel=self.__window.highlightedPanel()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].selectAll()

    def commandPanelSelectNone(self, panel=None):
        """Clear selection"""
        if panel is None:
            panel=self.__window.highlightedPanel()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].selectNone()

    def commandPanelSelectInvert(self, panel=None):
        """Invert selection"""
        if panel is None:
            panel=self.__window.highlightedPanel()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].selectInvert()

    def commandPanelSelectMarked(self, panel=None):
        """Select marked item"""
        if panel is None:
            panel=self.__window.highlightedPanel()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].selectMarked()

    def commandPanelMarkUnmark(self, panel=None):
        """mark/unmark current item"""
        if panel is None:
            panel=self.__window.highlightedPanel()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].markUnmark()

    def commandPanelMarkAll(self, panel=None):
        """mark all items"""
        if panel is None:
            panel=self.__window.highlightedPanel()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].markAll()

    def commandPanelMarkNone(self, panel=None):
        """unmark all items"""
        if panel is None:
            panel=self.__window.highlightedPanel()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].markNone()

    def commandPanelMarkInvert(self, panel=None):
        """invert marked items"""
        if panel is None:
            panel=self.__window.highlightedPanel()
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].markInvert()

    def commandPanelFilterVisible(self, panel, visible=None):
        """Display the filter

        If visible is None, invert current status
        If True, display filter
        If False, hide
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setFilesFilterVisible(visible)

    def commandPanelFilterValue(self, panel, value=None):
        """Set current filter text value"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setFilesFilter(value, None)

    def commandPanelFilterOptions(self, panel, value=None):
        """Set current filter options"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setFilesFilter(None, value)

    def commandGoTo(self, panel, path=None):
        """Go back to given path/bookmark/saved view"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setFilesPath(path)

    def commandGoBack(self, panel):
        """Go back to previous directory"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].filesGoToBackPath()

    def commandGoUp(self, panel):
        """Go to parent directory"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].filesGoToUpPath()

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
            if not WDialogBooleanInput.display(
                                        self.__bcName,
                                        "Are you sure you want to clear history?"
                                    ):
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
            if not WDialogBooleanInput.display(
                                        self.__bcName,
                                        "Are you sure you want to clear all bookmarks?"
                                    ):
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
            self.panel().filesRefresh()

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
            self.panel().filesRefresh()
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
            if WDialogBooleanInput.display(
                                        self.__bcName,
                                        "Are you sure you want to clear last opened/saved list?"
                                    ):
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
            if WDialogBooleanInput.display(
                                        self.__bcName,
                                        "Are you sure you want to reset last opened/saved list?"
                                    ):
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
        BCSettings.set(BCSettingsKey.CONFIG_FILES_HISTORY_MAXITEMS, self.__history.maxItems())

    def commandSettingsHistoryKeepOnExit(self, value=True):
        """When True, current history is saved when BuliCommander is exited"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_HISTORY_KEEPONEXIT, value)

    def commandSettingsLastDocsMaxSize(self, value=25):
        """Set maximum size for last documents list"""
        self.__lastDocumentsOpened.setMaxItems(value)
        self.__lastDocumentsSaved.setMaxItems(value)
        BCSettings.set(BCSettingsKey.CONFIG_FILES_LASTDOC_MAXITEMS, self.__lastDocumentsOpened.maxItems())

    def commandSettingsFileDefaultActionKra(self, value=BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE):
        """Set default action for kra file"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_KRA, value)

    def commandSettingsFileDefaultActionOther(self, value=BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE):
        """Set default action for kra file"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_OTHER, value)

    def commandSettingsFileNewFileNameKra(self, value=None):
        """Set default file name applied when a Krita file is opened as a new document"""
        if value is None:
            value = "<None>"
        elif not isinstance(value, str):
            raise EInvalidType("Given `value` must be a <str>")

        if value.lower().strip() == '<none>':
            value = "<None>"

        BCSettings.set(BCSettingsKey.CONFIG_FILES_NEWFILENAME_KRA, value)

    def commandSettingsFileNewFileNameOther(self, value=None):
        """Set default file name applied when a non Krita file is opened as a new document"""
        if value is None:
            value = "<None>"
        elif not isinstance(value, str):
            raise EInvalidType("Given `value` must be a <str>")

        if value.lower().strip() == '<none>':
            value = "<None>"

        BCSettings.set(BCSettingsKey.CONFIG_FILES_NEWFILENAME_OTHER, value)

    def commandSettingsFileUnit(self, value=BCSettingsValues.FILE_UNIT_KIB):
        """Set used file unit"""
        setBytesSizeToStrUnit(value)
        BCSettings.set(BCSettingsKey.CONFIG_GLB_FILE_UNIT, getBytesSizeToStrUnit())

        for panelId in self.__window.panels:
            self.__window.panels[panelId].updateFileSizeUnit()

    def commandSettingsHomeDirMode(self, value=BCSettingsValues.HOME_DIR_SYS):
        """Set mode for home directory"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_HOME_DIR_MODE, value)

    def commandSettingsHomeDirUserDefined(self, value=''):
        """Set user defined directory for home"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_HOME_DIR_UD, value)

    def commandSettingsSysTrayMode(self, value=BCSysTray.SYSTRAY_MODE_WHENACTIVE):
        """Set mode for systray notifier"""
        BCSettings.set(BCSettingsKey.CONFIG_GLB_SYSTRAY_MODE, value)
        self.__systray.setVisibleMode(value)

    def commandSettingsOpenAtStartup(self, value=False):
        """Set option to start BC at Krita's startup"""
        BCSettings.set(BCSettingsKey.CONFIG_GLB_OPEN_ATSTARTUP, value)

    def commandSettingsOpenOverrideKrita(self, value=False):
        """Set option to override krita's open command"""
        BCSettings.set(BCSettingsKey.CONFIG_GLB_OPEN_OVERRIDEKRITA, value)
        self.__overrideOpenKrita()

    def commandSettingsOpenFromFileMenu(self, value=False):
        """Set option to add a BC entry in Krita's File menu"""
        BCSettings.set(BCSettingsKey.CONFIG_GLB_OPEN_FROMKRITAMENU, value)

        # search for menu 'File'
        menuFile=Krita.instance().activeWindow().qwindow().findChild(QMenu,'file')
        # search for menu 'Tools>Scripts'
        menuScripts=Krita.instance().activeWindow().qwindow().findChild(QMenu,'scripts')

        # Buli Commander action
        actionOpenBC=Krita.instance().action('pykrita_bulicommander')
        actionOpenBC.setIcon(buildIcon([(':/bc/images/normal/bulicommander', QIcon.Normal), (':/bc/images/disabled/bulicommander', QIcon.Disabled)]))

        if isinstance(menuFile, QMenu) and isinstance(menuScripts, QMenu):
            if value:
                # move action to File menu
                if not actionOpenBC in menuFile.actions():
                    # currently not in menu file action

                    # search menu entry following "File>Open recent" menu
                    referenceMenuFile=None
                    for index, action in enumerate(menuFile.actions()):
                        if action.objectName()=='file_open_recent':
                            referenceMenuFile=menuFile.actions()[index+1]
                            break

                    if not referenceMenuFile is None:
                        # move menu entry
                        menuScripts.removeAction(actionOpenBC)
                        menuFile.insertAction(referenceMenuFile, actionOpenBC)
            else:
                # move action to Tools>Scripts menu
                if not actionOpenBC in menuScripts.actions():
                    # currently not in menu scripts action

                    # move menu entry
                    menuFile.removeAction(actionOpenBC)
                    menuScripts.addAction(actionOpenBC)

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
            self.__window.panels[panelId].filesSetAllowRefresh(False)

        self.commandViewDisplaySecondaryPanel(True)
        self.commandViewHighlightPanel(0)
        self.commandViewMainSplitterPosition()
        self.commandViewShowImageFileOnly(BCSettings.get(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY))
        self.commandViewShowBackupFiles(BCSettings.get(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP))
        self.commandViewShowHiddenFiles(BCSettings.get(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN))

        for panelId in self.__window.panels:
            self.commandViewThumbnail(panelId, BCSettings.get(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_THUMBNAIL))

            self.commandPanelFilesTabLayout(panelId, BCSettings.get(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_LAYOUT))
            self.commandPanelFilesTabActive(panelId, BCMainViewTabFilesTabs.INFORMATIONS)
            self.commandPanelFilesTabPosition(panelId, [BCMainViewTabFilesTabs.INFORMATIONS, BCMainViewTabFilesTabs.DIRECTORIES_TREE])

            self.commandPanelTabActive(panelId, BCMainViewTabTabs.FILES)
            self.commandPanelTabPosition(panelId, [BCMainViewTabTabs.FILES, BCMainViewTabTabs.DOCUMENTS, BCMainViewTabTabs.CLIPBOARD])

            self.commandPanelFilesTabNfoActive(panelId, BCMainViewTabFilesNfoTabs.GENERIC)

            self.commandPanelFilesTabSplitterClipboardPosition(panelId)
            self.commandPanelFilesTabSplitterFilesPosition(panelId)
            self.commandPanelFilesTabSplitterPreviewPosition(panelId)

            self.__window.panels[panelId].filesSetAllowRefresh(True)

            self.__window.panels[panelId].setFilesColumnSort([1, True])
            self.__window.panels[panelId].setFilesColumnOrder([0,1,2,3,4,5,6,7,8])
            self.__window.panels[panelId].setFilesColumnSize([0,0,0,0,0,0,0,0,0])
            self.__window.panels[panelId].setFilesIconSizeTv(BCSettings.get(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_ICONSIZE_TV))
            self.__window.panels[panelId].setFilesIconSizeLv(BCSettings.get(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_ICONSIZE_LV))

            self.__window.panels[panelId].setClipboardColumnSort([3, False])
            self.__window.panels[panelId].setClipboardColumnOrder([0,1,2,3,4,5,6])
            self.__window.panels[panelId].setClipboardIconSize(BCSettings.get(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_CLIPBOARD_ICONSIZE))

    def commandSettingsNavBarBtnHome(self, visible=True):
        """Set button home visible/hidden"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_HOME, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesShowHome(visible)

    def commandSettingsNavBarBtnViews(self, visible=True):
        """Set button views visible/hidden"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_VIEWS, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesShowSavedView(visible)

    def commandSettingsNavBarBtnBookmarks(self, visible=True):
        """Set button bookmarks visible/hidden"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_BOOKMARKS, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesShowBookmark(visible)

    def commandSettingsNavBarBtnHistory(self, visible=True):
        """Set button history visible/hidden"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_HISTORY, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesShowHistory(visible)

    def commandSettingsNavBarBtnLastDocuments(self, visible=True):
        """Set button history visible/hidden"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_LASTDOCUMENTS, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesShowLastDocuments(visible)

    def commandSettingsNavBarBtnGoBack(self, visible=True):
        """Set button go back visible/hidden"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_BACK, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesShowGoBack(visible)

    def commandSettingsNavBarBtnGoUp(self, visible=True):
        """Set button go up visible/hidden"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_UP, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesShowGoUp(visible)

    def commandSettingsNavBarBtnQuickFilter(self, visible=True):
        """Set button quick filter visible/hidden"""
        BCSettings.set(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_QUICKFILTER, visible)
        for panelId in self.__window.panels:
            self.__window.panels[panelId].filesShowQuickFilter(visible)

    def commandSettingsFilesNfoGridMode(self, value=None):
        """Set information grid mode"""
        if value is None:
            return BCSettings.get(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_LAYOUT)
        else:
            BCSettings.set(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_LAYOUT, value)
            for panelId in self.__window.panels:
                self.__window.panels[panelId].setFilesGridNfoLayout(value)

    def commandSettingsFilesNfoGridPropertiesFields(self, value=None):
        """Set information grid properties"""
        if value is None:
            return BCSettings.get(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_FIELDS)
        else:
            BCSettings.set(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_FIELDS, value)
            for panelId in self.__window.panels:
                self.__window.panels[panelId].setFilesGridNfoFieds(value)

    def commandSettingsFilesNfoGridOverMinSize(self, value=None):
        """Set information grid properties"""
        if value is None:
            return BCSettings.get(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_OVERMINSIZE)
        else:
            BCSettings.set(BCSettingsKey.CONFIG_PANELVIEW_FILES_GRIDINFO_OVERMINSIZE, value)
            for panelId in self.__window.panels:
                self.__window.panels[panelId].setFilesGridNfoOverMinSize(value)

    def commandSettingsToolbars(self, config=None, session=None):
        """Set toolbars definition"""
        if config is None:
            return (BCSettings.get(BCSettingsKey.CONFIG_TOOLBARS), BCSettings.get(BCSettingsKey.SESSION_TOOLBARS))
        else:
            BCSettings.set(BCSettingsKey.CONFIG_TOOLBARS, config)
            if not session is None:
                BCSettings.set(BCSettingsKey.SESSION_TOOLBARS, session)
            self.__window.initToolbar(config, session)

    def commandInfoToClipBoardBorder(self, border=TextTableSettingsText.BORDER_DOUBLE):
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

    def commandToolsExportFilesOpen(self):
        """Open window for tool 'Export file list'"""
        BCExportFilesDialogBox.open(f'{self.__bcName}::Export files list', self)

    def commandToolsConvertFilesOpen(self):
        """Open window for tool 'Convert files'"""
        BCConvertFilesDialogBox.open(f'{self.__bcName}::Convert files', self)

    def commandToolsSearchFilesOpen(self):
        """Open window for tool 'Search files'"""
        BCSearchFilesDialogBox.open(f'{self.__bcName}::Search files', self)

    def commandToolsListToClipboard(self):
        """Copy current selection to clipboard"""
        selectionInfo = self.panel().filesSelected()
        if selectionInfo[3] > 0:
            uriList=[]
            for file in selectionInfo[0]:
                uriList.append(BCClipboardItemFile('00000000000000000000000000000000', file.fullPathName(), saveInCache=False, persistent=False))

            if len(uriList)>0:
                self.__clipboard.pushBackToClipboard(uriList)

    def commandSettingsOpen(self):
        """Open dialog box settings"""
        if BCSettingsDialogBox.open(f'{self.__bcName}::Settings', self):
            self.saveSettings()

    def commandSettingsClipboardCacheMode(self, value=None):
        """Define default mode for clipboard"""
        if not value is None:
            BCSettings.set(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MODE_GENERAL, value)
            self.__clipboardActive()
        return BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MODE_GENERAL)

    def commandSettingsClipboardDefaultAction(self, value=None):
        """Define default action (on double-click) for clipboard manager"""
        if not value is None:
            BCSettings.set(BCSettingsKey.CONFIG_CLIPBOARD_DEFAULT_ACTION, value)
        return BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_DEFAULT_ACTION)

    def commandSettingsClipboardCacheSystrayMode(self, value=None):
        """Define default mode for clipboard"""
        if not value is None:
            BCSettings.set(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MODE_SYSTRAY, value)
            self.__clipboardActive()
        return BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MODE_SYSTRAY)

    def commandSettingsClipboardCacheMaxSize(self, value=None):
        """Define default mode for clipboard"""
        if not value is None:
            BCSettings.set(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MAXISZE, value)
            BCClipboard.setOptionCacheMaxSize(value)
        return BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MAXISZE)

    def commandSettingsClipboardCachePersistent(self, value=False):
        """Define default cache used clipboard items"""
        BCSettings.set(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_PERSISTENT, value)
        BCClipboard.setOptionCacheDefaultPersistent(value)

    def commandSettingsClipboardUrlAutomaticDownload(self, value=True):
        """Define default action on clipboard url"""
        BCSettings.set(BCSettingsKey.CONFIG_CLIPBOARD_URL_AUTOLOAD, value)
        BCClipboard.setOptionUrlAutoload(value)
        if value:
            self.__clipboard.startDownload()

    def commandSettingsClipboardUrlParseTextHtml(self, value=True):
        """Define default action on clipboard url"""
        BCSettings.set(BCSettingsKey.CONFIG_CLIPBOARD_URL_PARSE_TEXTHTML, value)
        BCClipboard.setOptionUrlParseTextHtml(value)

    def commandSettingsClipboardPasteAsNewDocument(self, value=False):
        """Replace default action <paste as new layer> by <paste as new document> when there no active document"""
        BCSettings.set(BCSettingsKey.CONFIG_CLIPBOARD_PASTE_MODE_ASNEWDOC, value)

    def commandAboutBc(self):
        """Display 'About Buli Commander' dialog box"""
        AboutWindow(self.__bcName, self.__bcVersion, os.path.join(os.path.dirname(__file__), 'resources', 'png', 'buli-powered-big.png'), None, ':BuliCommander')

    # endregion: define commands -----------------------------------------------
