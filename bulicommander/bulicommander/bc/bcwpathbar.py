# -----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2019-2022 - Grum999
# -----------------------------------------------------------------------------
# SPDX-License-Identifier: GPL-3.0-or-later
#
# https://spdx.org/licenses/GPL-3.0-or-later.html
# -----------------------------------------------------------------------------
# A Krita plugin designed to manage documents
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# The bcwpath module provides widget classes that allows to manage breadcrumb
# and quick access functions
# --> this module is a core module for plugin
#
# Main class from this module
#
# - BCWPathBar:
#       Breadcrumb + Buttons widget
#
# -----------------------------------------------------------------------------

from pathlib import Path

import os
import sys
import re

import PyQt5.uic

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QFileInfo
    )
from PyQt5.QtWidgets import (
        QFileIconProvider,
        QFrame,
        QMenu,
        QWidget
    )
from PyQt5.QtGui import (
        QColor,
        QIcon,
        QPainter,
        QPalette,
        QPixmap
    )

from .bcbookmark import BCBookmark
from .bchistory import BCHistory
from .bcsavedview import BCSavedView

from bulicommander.pktk.modules.imgutils import buildIcon
from bulicommander.pktk.modules.menuutils import (
        buildQAction,
        buildQMenu
    )
from bulicommander.pktk.modules.utils import (
        loadXmlUi,
        replaceLineEditClearButton,
        Debug
    )

from bulicommander.pktk.widgets.wsearchinput import WSearchInput

# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------

class BCWPathBar(QFrame):
    """Buli Commander path bar"""

    MODE_PATH = 0
    MODE_SAVEDVIEW = 1

    QUICKREF_RESERVED_HOME = 0
    QUICKREF_BOOKMARK = 1
    QUICKREF_SAVEDVIEW_LIST = 2
    QUICKREF_SAVEDVIEW_SEARCH = 3
    QUICKREF_RESERVED_LAST_ALL = 4
    QUICKREF_RESERVED_LAST_OPENED = 5
    QUICKREF_RESERVED_LAST_SAVED = 6
    QUICKREF_RESERVED_HISTORY = 7
    QUICKREF_RESERVED_BACKUPFILTERDVIEW = 8
    QUICKREF_RESERVED_FLAYERFILTERDVIEW = 9     # file layer
    QUICKREF_SEARCHRESULTS_LIST = 10            # search results

    OPTION_SHOW_NONE =              0b0000000000000000
    OPTION_SHOW_ALL =               0b0000000111111111
    OPTION_SHOW_QUICKFILTER =       0b0000000000000001
    OPTION_SHOW_UP =                0b0000000000000010
    OPTION_SHOW_PREVIOUS =          0b0000000000000100
    OPTION_SHOW_HISTORY =           0b0000000000001000
    OPTION_SHOW_BOOKMARKS =         0b0000000000010000
    OPTION_SHOW_SAVEDVIEWS =        0b0000000000100000
    OPTION_SHOW_HOME =              0b0000000001000000
    OPTION_SHOW_LASTDOCUMENTS =     0b0000000010000000
    OPTION_SHOW_MARGINS =           0b0000000100000000

    #                               ---vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv -- reserved from WSearchInput
    OPTION_FILTER_MARKED_ACTIVE =   0b100000000000000000000000000000000

    clicked = Signal(bool)
    pathChanged = Signal(str)
    viewChanged = Signal(str)
    filterChanged = Signal(str, object)            # search value, active options
    filterVisibilityChanged = Signal(bool)

    def __init__(self, parent=None):
        super(BCWPathBar, self).__init__(parent)

        self.__isHighlighted = False

        self.__uiController = None
        self.__panel = None

        self.__paletteBase = None
        self.__paletteHighlighted = None
        self.updatePalette()

        self.__history = None
        self.__bookmark = None
        self.__savedView = None
        self.__backList = BCHistory()
        self.__lastDocumentsSaved = None
        self.__lastDocumentsOpened = None
        self.__backupFilterDView = None
        self.__fileLayerFilterDView = None

        self.__mode = BCWPathBar.MODE_PATH

        self.__options = BCWPathBar.OPTION_SHOW_ALL

        self.__font = QFont()
        self.__font.setPointSize(9)
        self.__font.setFamily('DejaVu Sans Mono, Consolas, Courier New')

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcwpathbar.ui')
        loadXmlUi(uiFileName, self)

        self.__initialise()

    def __initialise(self):
        """Initialise BCWPathBar"""

        @pyqtSlot('QString')
        def item_Clicked(value=None):
            self.clicked.emit(False)

        @pyqtSlot('QString')
        def home_Clicked(value):
            if self.__uiController is not None:
                self.__uiController.commandGoHome(self.__panel)

        @pyqtSlot('QString')
        def up_Clicked(value):
            if self.__uiController is not None:
                self.__uiController.commandGoUp(self.__panel)
            else:
                self.goToUpPath()

        @pyqtSlot('QString')
        def back_Clicked(value):
            if self.__uiController is not None:
                self.__uiController.commandGoBack(self.__panel)
            else:
                self.goToBackPath()

        @pyqtSlot('QString')
        def edit_Clicked(event):
            # need to review
            self.clicked.emit(False)
            event.accept()

        @pyqtSlot('QString')
        def path_Selected(value):
            self.__backList.append(self.path())
            self.__updateUpBtn()
            self.__updateBackBtn()

            self.setMode(BCWPathBar.MODE_PATH)

            if self.__uiController is not None:
                self.__uiController.updateMenuForPanel()

            self.pathChanged.emit(self.path())

        @pyqtSlot('QString')
        def view_Selected(value):
            self.__savedView.setCurrent(value)

            self.__backList.append(self.path())
            self.__updateUpBtn()
            self.__updateBackBtn()

            self.setMode(BCWPathBar.MODE_SAVEDVIEW)

            if self.__uiController is not None:
                self.__uiController.updateMenuForPanel()

            self.viewChanged.emit(self.path())

        # @pyqtSlot('QString')
        # def menuSavedViews_Clicked(action):
        #    # change view
        #    self.setPath(action.property('path'))

        @pyqtSlot('QString')
        def filter_Changed(searchValue, options):
            if self.tbFilterMarkedFiles.isChecked():
                options |= BCWPathBar.OPTION_FILTER_MARKED_ACTIVE

            self.filterChanged.emit(searchValue, options)

        @pyqtSlot('QString')
        def filter_Changed2():
            searchValue = self.wsiFilterQuery.searchText()
            options = self.wsiFilterQuery.options()

            if self.tbFilterMarkedFiles.isChecked():
                options |= BCWPathBar.OPTION_FILTER_MARKED_ACTIVE

            self.filterChanged.emit(searchValue, options)

        @pyqtSlot('QString')
        def filter_Focused(e):
            item_Clicked(None)
            self.__wsiFilterQueryFocusInEvent(e)

        def mouseEvent(event, originalMouseEvent):
            # force to highlight panel owning BCWPathBar before popup menu
            self.clicked.emit(False)
            originalMouseEvent(event)

        self.widgetPath.setPalette(self.__paletteBase)

        self.__btSavedViewsMousePressEvent = self.btSavedViews.mousePressEvent
        self.__btBookmarkmousePressEvent = self.btBookmark.mousePressEvent
        self.__btHistorymousePressEvent = self.btHistory.mousePressEvent
        self.__btLastDocumentsmousePressEvent = self.btLastDocuments.mousePressEvent

        self.btSavedViews.mousePressEvent = lambda e: mouseEvent(e, self.__btSavedViewsMousePressEvent)
        self.btBookmark.mousePressEvent = lambda e: mouseEvent(e, self.__btBookmarkmousePressEvent)
        self.btHistory.mousePressEvent = lambda e: mouseEvent(e, self.__btHistorymousePressEvent)
        self.btLastDocuments.mousePressEvent = lambda e: mouseEvent(e, self.__btLastDocumentsmousePressEvent)

        self.btFilter.clicked.connect(item_Clicked)
        self.btFilter.clicked.connect(self.__refreshFilter)
        self.frameBreacrumbPath.clicked.connect(item_Clicked)
        self.frameBreacrumbPath.path_selected.connect(path_Selected)
        self.frameBreacrumbPath.view_selected.connect(view_Selected)
        if self.__savedView is not None:
            self.frameBreacrumbPath.checkViewId = self.__savedView.inList

        self.wsiFilterQuery.setOptions(WSearchInput.OPTION_SHOW_BUTTON_REGEX |
                                       WSearchInput.OPTION_SHOW_BUTTON_CASESENSITIVE |
                                       WSearchInput.OPTION_SHOW_BUTTON_CASESENSITIVE |
                                       WSearchInput.OPTION_STATE_BUTTONSHOW |
                                       WSearchInput.OPTION_HIDE_VSEPARATORL |
                                       WSearchInput.OPTION_HIDE_VSEPARATORR)
        self.wsiFilterQuery.searchOptionModified.connect(filter_Changed)
        self.wsiFilterQuery.searchModified.connect(filter_Changed)
        self.tbFilterMarkedFiles.toggled.connect(filter_Changed2)

        self.__wsiFilterQueryFocusInEvent = self.wsiFilterQuery.qLineEditSearch().focusInEvent
        self.wsiFilterQuery.qLineEditSearch().focusInEvent = filter_Focused

        self.btBack.clicked.connect(item_Clicked)
        self.btBack.clicked.connect(back_Clicked)
        self.btUp.clicked.connect(item_Clicked)
        self.btUp.clicked.connect(up_Clicked)
        self.btHome.clicked.connect(item_Clicked)
        self.btHome.clicked.connect(home_Clicked)

    def __refreshStyle(self):
        """refresh current style for BCWPathBar"""
        self.frameBreacrumbPath.setHighlighted(self.__isHighlighted)
        self.update()

    def __refreshFilter(self):
        """Refresh filter layout"""
        self.setMinimumHeight(0)
        idealMinHeight = self.widgetPath.sizeHint().height()

        if self.btFilter.isChecked():
            self.frameFilter.setVisible(True)
            self.wsiFilterQuery.qLineEditSearch().setFocus()
            self.wsiFilterQuery.qLineEditSearch().selectAll()
            self.filterVisibilityChanged.emit(True)
            idealMinHeight += self.widgetFilter.sizeHint().height()
        else:
            self.frameFilter.setVisible(False)
            self.filterVisibilityChanged.emit(False)

        self.setMinimumHeight(idealMinHeight)

    def __historyChanged(self):
        """History content has been modified"""
        pass

    def __bookmarkChanged(self):
        """Bookmark content has been modified"""
        pass

    def __savedViewChanged(self):
        """Saved view content has been modified"""
        pass

    def __lastDocumentsOpenedChanged(self):
        """Last opened documents view content has been modified"""
        pass

    def __lastDocumentsSavedChanged(self):
        """Last saved documents view content has been modified"""
        pass

    def __backupFilterDViewChanged(self):
        """backup filtered dynamic view content has been modified"""
        pass

    def __fileLayerFilterDViewChanged(self):
        """file layer filtered dynamic view content has been modified"""
        pass

    def __updateUpBtn(self):
        """Update up button status"""
        if f"{self.frameBreacrumbPath.path()}" != '' and f"{self.frameBreacrumbPath.path()}"[0] != '@':
            self.btUp.setEnabled(f"{self.frameBreacrumbPath.path()}" != self.frameBreacrumbPath.path().root)
        else:
            self.btUp.setEnabled(False)

    def __updateBackBtn(self):
        """update back button status"""
        self.btBack.setEnabled(self.__backList.length() > 1)

    def paintEvent(self, event):
        super(BCWPathBar, self).paintEvent(event)

        rect = QRect(0, 0, self.width(), self.height())

        painter = QPainter(self)
        if self.__isHighlighted:
            painter.fillRect(rect, QBrush(self.__paletteHighlighted.color(QPalette.Highlight)))
        else:
            painter.fillRect(rect, QBrush(self.__paletteBase.color(QPalette.Base)))

    def uiController(self):
        """Return uiController"""
        return self.__uiController

    def setUiController(self, uiController):
        """Set uiController"""
        # if not (uiController is None or isinstance(uiController, BCUIController)):
        #    raise EInvalidType('Given `uiController` must be a <BCUIController>')
        self.__uiController = uiController
        self.btHistory.setMenu(self.__uiController.window().menuGoHistory)
        self.btLastDocuments.setMenu(self.__uiController.window().menuGoLastDocuments)
        self.btBookmark.setMenu(self.__uiController.window().menuGoBookmark)
        self.btSavedViews.setMenu(self.__uiController.window().menuGoSavedViews)

    def mode(self):
        """Return current mode"""
        return self.__mode

    def setMode(self, mode):
        """Set current mode"""
        if mode not in [BCWPathBar.MODE_PATH, BCWPathBar.MODE_SAVEDVIEW]:
            raise EInvalidValue("Given `mode` is not valid")

        if mode != self.__mode:
            self.__mode = mode
            if mode in [BCWPathBar.MODE_PATH, BCWPathBar.MODE_SAVEDVIEW]:
                self.swBarMode.setCurrentIndex(0)
            else:
                # should not occurs...
                self.swBarMode.setCurrentIndex(1)

    def panel(self):
        """Return current panel for which BCWPathBar is attached to"""
        return self.__panel

    def setPanel(self, value):
        """Set current panel for which BCWPathBar is attached to"""
        self.__panel = value

    def setHighlighted(self, value):
        """Allows to change highlighted status"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
        elif self.__isHighlighted != value:
            self.__isHighlighted = value
            self.__refreshStyle()

    def highlighted(self):
        """Return current highlighted status (True if applied, otherwise False)"""
        return self.__isHighlighted

    def path(self):
        """Return current path"""
        if self.__mode in [BCWPathBar.MODE_PATH, BCWPathBar.MODE_SAVEDVIEW]:
            return f"{self.frameBreacrumbPath.path()}"
        elif self.__savedView is not None:
            # BCWPathBar.MODE_SAVEDVIEW
            return f"@{self.__savedView.current()}"
        else:
            return None

    def setPath(self, path=None, force=False):
        """Set current path

        If `force` is True, force to set path even if path already set with given value (do a "refresh")
        """
        self.frameBreacrumbPath.set_path(path, force)

    def goToBackPath(self):
        """Go to previous path

        If no previous path found, return False, otherwise True
        """
        if self.__backList.length() > 0:
            self.__backList.pop()
            last = self.__backList.last()
            if last is not None:
                self.setPath(last)
                return True

        return False

    def goToUpPath(self):
        """Go to parent path

        If no previous path found, return False, otherwise True
        """
        self.setPath(f"{self.frameBreacrumbPath.path().parent}")
        return self.btUp.isEnabled()

    def history(self):
        """Return history list"""
        return self.__history

    def setHistory(self, value):
        """Set history list"""
        # if not isinstance(value, BCHistory):
        #    raise EInvalidType("Given `value` must be a <BCHistory>")
        if value is not None:
            self.__history = value
            self.__history.changed.connect(self.__historyChanged)

    def bookmark(self):
        """Return bookmarks"""
        return self.__bookmark

    def setBookmark(self, value):
        """Set bookmark list"""
        # if not isinstance(value, BCBookmark):
        #    raise EInvalidType("Given `value` must be a <BCBookmark>")
        if value is not None:
            self.__bookmark = value
            self.__bookmark.changed.connect(self.__bookmarkChanged)

    def savedView(self):
        """Return saved views"""
        return self.__savedView

    def setSavedView(self, value):
        """Set saved views"""
        if value is not None:
            self.__savedView = value
            self.__savedView.updated.connect(self.__savedViewChanged)
            self.frameBreacrumbPath.quickRefDict = self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath = self.__uiController.quickRefPath

    def lastDocumentsOpened(self):
        """Return last opened document views"""
        return self.__lastDocumentsOpened

    def setLastDocumentsOpened(self, value):
        """Set last opened document views"""
        if value is not None:
            self.__lastDocumentsOpened = value
            self.__lastDocumentsOpened.changed.connect(self.__lastDocumentsOpenedChanged)
            self.frameBreacrumbPath.quickRefDict = self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath = self.__uiController.quickRefPath

    def lastDocumentsSaved(self):
        """Return last saved document views"""
        return self.__lastDocumentsSaved

    def setLastDocumentsSaved(self, value):
        """Set last saved document views"""
        if value is not None:
            self.__lastDocumentsSaved = value
            self.__lastDocumentsSaved.changed.connect(self.__lastDocumentsSavedChanged)
            self.frameBreacrumbPath.quickRefDict = self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath = self.__uiController.quickRefPath

    def backupFilterDView(self):
        """Return backup dynamic view object"""
        return self.__backupFilterDView

    def setBackupFilterDView(self, value):
        """Set backup dynamic view object"""
        if value is not None:
            self.__backupFilterDView = value
            self.__backupFilterDView.changed.connect(self.__backupFilterDViewChanged)
            self.frameBreacrumbPath.quickRefDict = self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath = self.__uiController.quickRefPath

    def fileLayerFilterDView(self):
        """Return file layer dynamic view object"""
        return self.__fileLayerFilterDView

    def setFileLayerFilterDView(self, value):
        """Set file layer dynamic view object"""
        if value is not None:
            self.__fileLayerFilterDView = value
            self.__fileLayerFilterDView.changed.connect(self.__fileLayerFilterDViewChanged)
            self.frameBreacrumbPath.quickRefDict = self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath = self.__uiController.quickRefPath

    def filterVisible(self):
        """Return if filter is visible or not"""
        return self.btFilter.isChecked()

    def setFilterVisible(self, visible=None):
        """Display the filter

        If visible is None, invert current status
        If True, display filter
        If False, hide
        """
        if visible is None:
            visible = not self.btFilter.isChecked()

        if not isinstance(visible, bool):
            raise EInvalidType('Given `visible` must be a <bool>')

        if visible:
            self.btFilter.setChecked(True)
        else:
            self.btFilter.setChecked(False)

        self.__refreshFilter()

    def filter(self):
        """Return current filter value as tuple (value, options)"""
        options = self.wsiFilterQuery.options() & WSearchInput.OPTION_ALL_SEARCH
        if self.tbFilterMarkedFiles.isChecked():
            options |= BCWPathBar.OPTION_FILTER_MARKED_ACTIVE

        return (self.wsiFilterQuery.searchText(), options)

    def setFilter(self, value=None, options=None):
        """Set current filter value"""
        if value is None:
            value = ''
        self.wsiFilterQuery.setSearchText(value)
        if isinstance(options, int):
            self.tbFilterMarkedFiles.setChecked(options & BCWPathBar.OPTION_FILTER_MARKED_ACTIVE == BCWPathBar.OPTION_FILTER_MARKED_ACTIVE)
            self.wsiFilterQuery.setOptions((options & WSearchInput.OPTION_ALL_SEARCH) |
                                           WSearchInput.OPTION_SHOW_BUTTON_REGEX |
                                           WSearchInput.OPTION_SHOW_BUTTON_CASESENSITIVE |
                                           WSearchInput.OPTION_SHOW_BUTTON_CASESENSITIVE |
                                           WSearchInput.OPTION_STATE_BUTTONSHOW |
                                           WSearchInput.OPTION_HIDE_VSEPARATORL |
                                           WSearchInput.OPTION_HIDE_VSEPARATORR)

    def hiddenPath(self):
        """Return if hidden path are displayed or not"""
        return self.frameBreacrumbPath.hiddenPath()

    def setHiddenPath(self, value=False):
        """Set if hidden path are displayed or not"""
        self.frameBreacrumbPath.setHiddenPath(value)

    def showBookmark(self, visible=True):
        """Display/Hide the bookmark button"""
        self.btBookmark.setVisible(visible)

    def showHistory(self, visible=True):
        """Display/Hide the history button"""
        self.btHistory.setVisible(visible)

    def showLastDocuments(self, visible=True):
        """Display/Hide the Last Documents button"""
        self.btLastDocuments.setVisible(visible)

    def showSavedView(self, visible=True):
        """Display/Hide the saved view button"""
        self.btSavedViews.setVisible(visible)

    def showHome(self, visible=True):
        """Display/Hide the home button"""
        self.btHome.setVisible(visible)

    def showGoUp(self, visible=True):
        """Display/Hide the go up button"""
        self.btUp.setVisible(visible)

    def showGoBack(self, visible=True):
        """Display/Hide the go back button"""
        self.btBack.setVisible(visible)

    def showQuickFilter(self, visible=True):
        """Display/Hide the quickfilter button"""
        self.btFilter.setVisible(visible)
        if not self.btFilter.isVisible():
            self.setFilterVisible(False)

    def showMargins(self, visible=False):
        """Display/Hide margins"""
        if visible:
            self.widgetPath.setMinimumHeight(40)
            self.widgetPath.setContentsMargins(2, 2, 2, 2)
        else:
            self.widgetPath.setMinimumHeight(0)
            self.widgetPath.setContentsMargins(0, 0, 0, 0)

    def goUpEnabled(self):
        """Return True if go up button is enabled"""
        return self.btUp.isEnabled()

    def goBackEnabled(self):
        """Return True if go back button is enabled"""
        return self.btBack.isEnabled()

    def options(self):
        """Return current options defined"""
        return self.__options

    def setOptions(self, options=None):
        """Set current options"""
        if isinstance(options, int):
            self.__options = options

        self.showQuickFilter(self.__options & BCWPathBar.OPTION_SHOW_QUICKFILTER == BCWPathBar.OPTION_SHOW_QUICKFILTER)
        self.showGoUp(self.__options & BCWPathBar.OPTION_SHOW_UP == BCWPathBar.OPTION_SHOW_UP)
        self.showGoBack(self.__options & BCWPathBar.OPTION_SHOW_PREVIOUS == BCWPathBar.OPTION_SHOW_PREVIOUS)
        self.showHistory(self.__options & BCWPathBar.OPTION_SHOW_HISTORY == BCWPathBar.OPTION_SHOW_HISTORY)
        self.showLastDocuments(self.__options & BCWPathBar.OPTION_SHOW_LASTDOCUMENTS == BCWPathBar.OPTION_SHOW_LASTDOCUMENTS)
        self.showBookmark(self.__options & BCWPathBar.OPTION_SHOW_BOOKMARKS == BCWPathBar.OPTION_SHOW_BOOKMARKS)
        self.showSavedView(self.__options & BCWPathBar.OPTION_SHOW_SAVEDVIEWS == BCWPathBar.OPTION_SHOW_SAVEDVIEWS)
        self.showHome(self.__options & BCWPathBar.OPTION_SHOW_HOME == BCWPathBar.OPTION_SHOW_HOME)

        self.showMargins(self.__options & BCWPathBar.OPTION_SHOW_MARGINS == BCWPathBar.OPTION_SHOW_MARGINS)

    def updatePalette(self, palette=None):
        """Refresh current palette"""
        if not isinstance(palette, QPalette):
            palette = QApplication.palette()

        self.__paletteBase = QPalette(palette)
        self.__paletteBase.setColor(QPalette.Window, self.__paletteBase.color(QPalette.Base))

        self.__paletteHighlighted = QPalette(palette)
        self.__paletteHighlighted.setColor(QPalette.Window, self.__paletteHighlighted.color(QPalette.Highlight))
