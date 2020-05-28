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


from pathlib import Path

import sys

from PyQt5.Qt import *
from PyQt5.QtCore import (
        QRect
    )

from PyQt5.QtWidgets import (
        QMessageBox,
        QWidget
    )


from .bcabout import BCAboutWindow
from .bcbookmark import BCBookmark
from .bchistory import BCHistory
from .bcmainviewtab import (
        BCMainViewTab,
        BCMainViewTabFilesLayout,
        BCMainViewTabFilesNfoTabs,
        BCMainViewTabFilesTabs,
        BCMainViewTabTabs
    )
from .bcmainwindow import BCMainWindow
from .bcsettings import (
        BCSettings,
        BCSettingsKey
    )




# ------------------------------------------------------------------------------
class BCUIController(object):
    """The controller provide an access to all BuliCommander functions


    """

    def __init__(self, bcName="Buli Commander", bcVersion="testing"):
        self.__window = BCMainWindow(self)
        self.__bcName = bcName
        self.__bcVersion = bcVersion
        self.__bcTitle = "{0} - {1}".format(bcName, bcVersion)

        self.__history = BCHistory()
        self.__bookmark = BCBookmark()

        self.__confirmAction = True

        self.__window.dialogShown.connect(self.__initSettings)
        self.__inInit = False



    def start(self):
        self.__settings = BCSettings('bulicommander')
        self.__window.setWindowTitle(self.__bcTitle)
        self.__window.show()
        self.__window.activateWindow()


    # region: initialisation methods -------------------------------------------

    def __initSettings(self):
        """There's some visual settings that need to have the window visible
        (ie: the widget size are known) to be applied
        """
        self.__window.initMainView()



        self.commandSettingsHistoryMaxSize(self.__settings.option(BCSettingsKey.CONFIG_HISTORY_MAXITEMS.id()))
        self.commandSettingsSaveSessionOnExit(self.__settings.option(BCSettingsKey.CONFIG_SESSION_SAVE.id()))

        self.commandViewMainWindowGeometry(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY.id()))
        self.commandViewMainWindowMaximized(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED.id()))
        self.commandViewMainSplitterPosition(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION.id()))
        self.commandViewDisplaySecondaryPanel(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE.id()))
        self.commandViewHighlightPanel(self.__settings.option(BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED.id()))
        self.commandViewMode(self.__settings.option(BCSettingsKey.SESSION_PANELS_VIEW_MODE.id()))
        self.commandViewShowImageFileOnly(self.__settings.option(BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY.id()))
        self.commandViewShowBackupFiles(self.__settings.option(BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP.id()))
        self.commandViewShowHiddenFiles(self.__settings.option(BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN.id()))

        for panelId in self.__window.panels:
            self.__window.panels[panelId].setHistory(self.__history)
            self.__window.panels[panelId].setBookmark(self.__bookmark)

            self.commandPanelTabActive(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId)))
            self.commandPanelTabPosition(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId)))

            self.commandPanelTabFilesLayout(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_LAYOUT.id(panelId=panelId)))
            self.commandPanelTabFilesActive(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId)))
            self.commandPanelTabFilesPosition(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId)))

            self.commandPanelTabFilesNfoActive(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId)))
            self.commandPanelTabFilesSplitterPosition(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_SPLITTER_POSITION.id(panelId=panelId)))

            self.commandPanelPath(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_CURRENTPATH.id(panelId=panelId)))

            self.commandPanelFilterVisible(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_FILTERVISIBLE.id(panelId=panelId)))
            self.commandPanelFilterValue(panelId, self.__settings.option(BCSettingsKey.SESSION_PANEL_VIEW_FILTERVALUE.id(panelId=panelId)))


        # load history
        self.commandGoHistorySet(self.__settings.option(BCSettingsKey.SESSION_HISTORY_ITEMS.id()))
        self.commandGoBookmarkSet(self.__settings.option(BCSettingsKey.SESSION_BOOKMARK_ITEMS.id()))

        self.__window.initMenu()

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

            if self.__window.actionViewSmallIcon.isChecked():
                self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_MODE, 'small')
            elif self.__window.actionViewMediumIcon.isChecked():
                self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_MODE, 'medium')
            elif self.__window.actionViewLargeIcon.isChecked():
                self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_MODE, 'large')
            else:
                self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_MODE, 'detailled')


            self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY, self.__window.actionViewShowImageFileOnly.isChecked())
            self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP, self.__window.actionViewShowBackupFiles.isChecked())
            self.__settings.setOption(BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN, self.__window.actionViewShowHiddenFiles.isChecked())

            for panelId in self.__window.panels:
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_LAYOUT.id(panelId=panelId), self.__window.panels[panelId].tabFilesLayout().value)
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_CURRENTPATH.id(panelId=panelId), self.__window.panels[panelId].currentPath())

                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_FILTERVISIBLE.id(panelId=panelId), self.__window.panels[panelId].filterVisible())
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_VIEW_FILTERVALUE.id(panelId=panelId), self.__window.panels[panelId].filter())

                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId), [tab.value for tab in self.__window.panels[panelId].tabOrder()])
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId), [tab.value for tab in self.__window.panels[panelId].tabFilesOrder()])
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId), self.__window.panels[panelId].tabActive().value)
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId), self.__window.panels[panelId].tabFilesActive().value)
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId), self.__window.panels[panelId].tabFilesNfoActive().value)
                self.__settings.setOption(BCSettingsKey.SESSION_PANEL_SPLITTER_POSITION.id(panelId=panelId), self.__window.panels[panelId].tabFilesSplitterPosition())

            self.__settings.setOption(BCSettingsKey.SESSION_HISTORY_ITEMS, self.__history.list())
            self.__settings.setOption(BCSettingsKey.SESSION_BOOKMARK_ITEMS, self.__bookmark.list())

        return self.__settings.saveConfig()

    def commandQuit(self):
        """Close Buli Commander"""
        self.__window.close()

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

    def commandViewModeDetailled(self):
        """Set current view in detailled mode"""
        self.__window.actionViewDetailled.setChecked(True)
        self.__window.actionViewSmallIcon.setChecked(False)
        self.__window.actionViewMediumIcon.setChecked(False)
        self.__window.actionViewLargeIcon.setChecked(False)

        print('TODO: commandViewDetailled Need to implement changed view')

    def commandViewModeSmallIcon(self):
        """Set current view in small icon mode"""
        self.__window.actionViewDetailled.setChecked(False)
        self.__window.actionViewSmallIcon.setChecked(True)
        self.__window.actionViewMediumIcon.setChecked(False)
        self.__window.actionViewLargeIcon.setChecked(False)

        print('TODO: commandViewSmallIcon Need to implement changed view')

    def commandViewModeMediumIcon(self):
        """Set current view in medium icon mode"""
        self.__window.actionViewDetailled.setChecked(False)
        self.__window.actionViewSmallIcon.setChecked(False)
        self.__window.actionViewMediumIcon.setChecked(True)
        self.__window.actionViewLargeIcon.setChecked(False)

        print('TODO: commandViewMediumIcon Need to implement changed view')

    def commandViewModeLargeIcon(self, value=None):
        """Set current view in large icon mode"""
        self.__window.actionViewDetailled.setChecked(False)
        self.__window.actionViewSmallIcon.setChecked(False)
        self.__window.actionViewMediumIcon.setChecked(False)
        self.__window.actionViewLargeIcon.setChecked(True)

        print('TODO: commandViewLargeIcon Need to implement changed view')

    def commandViewMode(self, mode=None):
        """Set current view mode"""
        if mode is None:
            mode = 'detailled'

        if mode == 'detailled':
            self.commandViewModeDetailled()
        elif mode == 'small':
            self.commandViewModeSmallIcon()
        elif mode == 'medium':
            self.commandViewModeMediumIcon()
        elif mode == 'large':
            self.commandViewModeLargeIcon()
        else:
            raise EInvalidValue('Given `mode` must be "detailled", "small", "medium" or "large"')

        return mode

    def commandViewShowImageFileOnly(self, value=None):
        """Display image files

        If `value` is True, display image files only
        If `value` is False, display all files
        """
        if value is None:
            value = self.__window.actionViewShowImageFileOnly.isChecked()
        else:
            self.__window.actionViewShowImageFileOnly.setChecked(value)

        print('TODO: commandViewShowImageFileOnly Need to implement changed view')

        return value

    def commandViewShowBackupFiles(self, value=None):
        """Display image backup files

        If `value` is True, display image backup files
        If `value` is False, don't display image backup files
        """
        if value is None:
            value = self.__window.actionViewShowBackupFiles.isChecked()
        else:
            self.__window.actionViewShowBackupFiles.setChecked(value)

        print('TODO: commandViewShowBackupFiles Need to implement changed view')

        return value

    def commandViewShowHiddenFiles(self, value=None):
        """Display hidden files

        If `value` is True, display hidden files
        If `value` is False, don't display hidden files
        """
        if value is None:
            value = self.__window.actionViewShowHiddenFiles.isChecked()
        else:
            self.__window.actionViewShowHiddenFiles.setChecked(value)

        print('TODO: commandViewShowHiddenFiles Need to implement changed view')
        for panel in self.__window.panels:
            self.__window.panels[panel].setHiddenPath(value)

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

    def commandPanelTabFilesSplitterPosition(self, panel, positions=None):
        """Set splitter position for tab files for given panel

        Given `positions` is a list [<panel0 size>,<panel1 size>]
        If value is None, will define a default 50%-50%
        """
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setTabFilesSplitterPosition(positions)

    def commandPanelPath(self, panel, path=None):
        """Define path for given panel"""
        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        return self.__window.panels[panel].setCurrentPath(path)

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

    def commandGoBack(self, panel):
        """Go back to previous directory"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        self.__window.panels[panel].goToBackPath()

    def commandGoUp(self, panel):
        """Go to parent directory"""
        if isinstance(panel, BCMainViewTab):
            for panelId in self.__window.panels:
                if self.__window.panels[panelId] == panel:
                    panel = panelId
                    break

        if not panel in self.__window.panels:
            raise EInvalidValue('Given `panel` is not valid')

        self.__window.panels[panel].goToUpPath()

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
                return
        self.commandGoHistoryClear()

    def commandGoHistorySet(self, value=[]):
        """Set history content"""
        self.__history.clear()
        self.__history.setItems(value)

    def commandGoHistoryAdd(self, value):
        """Set history content"""
        self.__history.append(value)

    def commandSettingsHistoryMaxSize(self, value=25):
        """Set maximum size history for history content"""
        self.__history.setMaxItems(value)
        self.__settings.setOption(BCSettingsKey.CONFIG_HISTORY_MAXITEMS, self.__history.maxItems())

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
        self.__bookmark.uiAppend(path)

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
        self.__bookmark.uiRename(name)

    def commandSettingsSaveSessionOnExit(self, saveSession=None):
        """Define if current session properties have to be save or not"""
        if saveSession is None:
            saveSession = self.__window.actionSettingsSaveSessionOnExit.isChecked()
        else:
            self.__window.actionSettingsSaveSessionOnExit.setChecked(saveSession)

        return saveSession

    def commandSettingsResetSessionToDefault(self):
        """Reset session configuration to default"""
        self.commandViewDisplaySecondaryPanel(True)
        self.commandViewHighlightPanel(0)
        self.commandViewMainSplitterPosition()
        self.commandViewMode(self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_MODE.id()))
        self.commandViewShowImageFileOnly(self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY.id()))
        self.commandViewShowBackupFiles(self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP.id()))
        self.commandViewShowHiddenFiles(self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN.id()))

        for panelId in self.__window.panels:
            self.commandPanelTabFilesLayout(panelId, self.__settings.option(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_LAYOUT.id()))
            self.commandPanelTabFilesActive(panelId, BCMainViewTabFilesTabs.INFORMATIONS)
            self.commandPanelTabFilesPosition(panelId, [BCMainViewTabFilesTabs.INFORMATIONS, BCMainViewTabFilesTabs.DIRECTORIES_TREE])

            self.commandPanelTabActive(panelId, BCMainViewTabTabs.FILES)
            self.commandPanelTabPosition(panelId, [BCMainViewTabTabs.FILES, BCMainViewTabTabs.DOCUMENTS])

            self.commandPanelTabFilesNfoActive(panelId, BCMainViewTabFilesNfoTabs.GENERIC)

            self.commandPanelTabFilesSplitterPosition(panelId)


    def commandAboutBc(self):
        """Display 'About Buli Commander' dialog box"""
        BCAboutWindow(self.__bcName, self.__bcVersion)



    # endregion: define commands -----------------------------------------------
