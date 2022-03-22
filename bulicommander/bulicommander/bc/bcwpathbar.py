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
    QUICKREF_RESERVED_FLAYERFILTERDVIEW = 9 # file layer
    QUICKREF_SEARCHRESULTS_LIST = 10 # search results

    OPTION_SHOW_NONE        =       0b0000000000000000
    OPTION_SHOW_ALL         =       0b0000000111111111
    OPTION_SHOW_QUICKFILTER =       0b0000000000000001
    OPTION_SHOW_UP =                0b0000000000000010
    OPTION_SHOW_PREVIOUS =          0b0000000000000100
    OPTION_SHOW_HISTORY =           0b0000000000001000
    OPTION_SHOW_BOOKMARKS =         0b0000000000010000
    OPTION_SHOW_SAVEDVIEWS =        0b0000000000100000
    OPTION_SHOW_HOME =              0b0000000001000000
    OPTION_SHOW_LASTDOCUMENTS =     0b0000000010000000
    OPTION_SHOW_MARGINS =           0b0000000100000000


    clicked = Signal(bool)
    pathChanged = Signal(str)
    viewChanged = Signal(str)
    filterChanged = Signal(str)
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

        self.__actionHistoryClear = buildQAction("pktk:history_clear", i18n('Clear history'), self)
        self.__actionHistoryClear.setStatusTip(i18n('Clear all paths from history'))

        self.__actionLastDocumentsAll = buildQAction("pktk:saved_view_last", i18n('Last documents'), self)
        self.__actionLastDocumentsAll.setStatusTip(i18n('Show list of last opened and/or saved documents'))
        self.__actionLastDocumentsAll.setProperty('path', '@last')
        self.__actionLastDocumentsOpened = buildQAction("pktk:saved_view_last", i18n('Last opened documents'), self)
        self.__actionLastDocumentsOpened.setStatusTip(i18n('Show list of last opened documents'))
        self.__actionLastDocumentsOpened.setProperty('path', '@last opened')
        self.__actionLastDocumentsSaved = buildQAction("pktk:saved_view_last", i18n('Last saved documents'), self)
        self.__actionLastDocumentsSaved.setStatusTip(i18n('Show list of last saved documents'))
        self.__actionLastDocumentsSaved.setProperty('path', '@last saved')

        self.__actionBookmarkClear = buildQAction("pktk:bookmark_clear", i18n('Clear bookmark'), self)
        self.__actionBookmarkClear.setStatusTip(i18n('Remove all bookmarked paths'))
        self.__actionBookmarkAdd = buildQAction("pktk:bookmark_add", i18n('Add to bookmark...'), self)
        self.__actionBookmarkAdd.triggered.connect(self.__menuBookmarkAppend_clicked)
        self.__actionBookmarkAdd.setStatusTip(i18n('Add current path to bookmarks'))
        self.__actionBookmarkRemove = buildQAction("pktk:bookmark_remove", i18n('Remove from bookmark...'), self)
        self.__actionBookmarkRemove.triggered.connect(self.__menuBookmarkRemove_clicked)
        self.__actionBookmarkRemove.setStatusTip(i18n('Remove current path from bookmarks'))
        self.__actionBookmarkRename = buildQAction("pktk:bookmark_rename", i18n('Rename bookmark...'), self)
        self.__actionBookmarkRename.triggered.connect(self.__menuBookmarkRename_clicked)
        self.__actionBookmarkRename.setStatusTip(i18n('Rename current bookmark'))


        self.__actionSavedViewsClear = buildQAction("pktk:saved_view_clear", i18n('Clear view content'), self)
        self.__actionSavedViewsClear.setStatusTip(i18n('Clear current view content'))
        self.__actionSavedViewsClear.setProperty('action', 'clear_view_content')
        self.__actionSavedViewsClear.setProperty('path', ':CURRENT')

        self.__actionSavedViewsAdd = buildQMenu("pktk:saved_view_add", i18n('Add to view'), self)
        self.__actionSavedViewsAdd.setStatusTip(i18n('Add selected files to view'))
        self.__actionSavedViewsAddNewView = buildQAction("pktk:saved_view_new", i18n('New view'), self)
        self.__actionSavedViewsAddNewView.setStatusTip(i18n('Add selected files to a new view'))
        self.__actionSavedViewsAddNewView.setProperty('action', 'create_view')
        self.__actionSavedViewsAddNewView.setProperty('path', ':NEW')

        self.__actionSavedViewsRemove = buildQAction("pktk:saved_view_remove", i18n('Remove from view...'), self)
        self.__actionSavedViewsRemove.setStatusTip(i18n('Remove selected files from view'))
        self.__actionSavedViewsRemove.setProperty('action', 'remove_from_view')
        self.__actionSavedViewsRemove.setProperty('path', ':CURRENT')

        self.__actionSavedViewsRename = buildQAction("pktk:saved_view_rename", i18n('Rename view...'), self)
        self.__actionSavedViewsRename.setStatusTip(i18n('Rename current view'))
        self.__actionSavedViewsRename.setProperty('action', 'rename_view')
        self.__actionSavedViewsRename.setProperty('path', ':CURRENT')
        self.__actionSavedViewsDelete = buildQAction("pktk:saved_view_delete", i18n('Delete view...'), self)
        self.__actionSavedViewsDelete.setStatusTip(i18n('Delete current view'))
        self.__actionSavedViewsDelete.setProperty('action', 'delete_view')
        self.__actionSavedViewsDelete.setProperty('path', ':CURRENT')


        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcwpathbar.ui')
        loadXmlUi(uiFileName, self)

        self.__initialise()

    def __initialise(self):
        """Initialise BCWPathBar"""

        @pyqtSlot('QString')
        def item_Clicked(value):
            self.clicked.emit(False)

        @pyqtSlot('QString')
        def home_Clicked(value):
            if not self.__uiController is None:
                self.__uiController.commandGoHome(self.__panel)

        @pyqtSlot('QString')
        def up_Clicked(value):
            if not self.__uiController is None:
                self.__uiController.commandGoUp(self.__panel)
            else:
                self.goToUpPath()

        @pyqtSlot('QString')
        def back_Clicked(value):
            if not self.__uiController is None:
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

            if not self.__uiController is None:
                self.__uiController.updateMenuForPanel()

            self.pathChanged.emit(self.path())

        @pyqtSlot('QString')
        def view_Selected(value):
            self.__savedView.setCurrent(value)

            self.__backList.append(self.path())
            self.__updateUpBtn()
            self.__updateBackBtn()

            self.setMode(BCWPathBar.MODE_SAVEDVIEW)

            if not self.__uiController is None:
                self.__uiController.updateMenuForPanel()

            self.viewChanged.emit(self.path())

        #@pyqtSlot('QString')
        #def menuSavedViews_Clicked(action):
        #    # change view
        #    self.setPath(action.property('path'))

        @pyqtSlot('QString')
        def filter_Finished():
            #self.filterChanged.emit(self.leFilterQuery.text())
            pass

        @pyqtSlot('QString')
        def filter_Changed():
            self.filterChanged.emit(self.leFilterQuery.text())

        @pyqtSlot('QString')
        def filter_Focused(e):
            item_Clicked(None)
            self.__leFilterQueryFocusInEvent(e)

        self.widgetPath.setPalette(self.__paletteBase)

        self.btSavedViews.clicked.connect(item_Clicked)
        self.btBookmark.clicked.connect(item_Clicked)
        self.btHistory.clicked.connect(item_Clicked)
        self.btFilter.clicked.connect(item_Clicked)
        self.btFilter.clicked.connect(self.__refreshFilter)
        self.frameBreacrumbPath.clicked.connect(item_Clicked)
        self.frameBreacrumbPath.path_selected.connect(path_Selected)
        self.frameBreacrumbPath.view_selected.connect(view_Selected)
        if not self.__savedView is None:
            self.frameBreacrumbPath.checkViewId=self.__savedView.inList

        fnt=self.leFilterQuery.font()
        fnt.setFamily('DejaVu Sans Mono, Consolas, Courier New')
        self.__leFilterQueryFocusInEvent=self.leFilterQuery.focusInEvent
        self.leFilterQuery.focusInEvent=filter_Focused
        self.leFilterQuery.editingFinished.connect(filter_Finished)
        self.leFilterQuery.textChanged.connect(filter_Changed)
        replaceLineEditClearButton(self.leFilterQuery)
        self.leFilterQuery.setFont(fnt)

        self.btBack.clicked.connect(item_Clicked)
        self.btBack.clicked.connect(back_Clicked)
        self.btUp.clicked.connect(item_Clicked)
        self.btUp.clicked.connect(up_Clicked)
        self.btHome.clicked.connect(item_Clicked)
        self.btHome.clicked.connect(home_Clicked)

        menu = QMenu(self.btHistory)
        menu.aboutToShow.connect(self.menuHistoryShow)
        menu.addAction(self.__actionHistoryClear)
        self.btHistory.setMenu(menu)

        menu = QMenu(self.btLastDocuments)
        menu.aboutToShow.connect(self.menuLastDocumentsShow)
        self.btLastDocuments.setMenu(menu)

        menu = QMenu(self.btBookmark)
        menu.aboutToShow.connect(self.menuBookmarksShow)
        menu.addAction(self.__actionBookmarkClear)
        self.btBookmark.setMenu(menu)

        menu = QMenu(self.btSavedViews)
        menu.aboutToShow.connect(self.menuSavedViewsShow)
        menu.addAction(self.__actionSavedViewsClear)
        self.btSavedViews.setMenu(menu)

    def menuHistoryShow(self, menu=None):
        """Build menu history"""
        @pyqtSlot('QString')
        def menuHistory_Clicked(action):
            # change directory
            self.setPath(action.property('path'))

        self.clicked.emit(False)

        if menu is None:
            menu = self.btHistory.menu()

        try:
            menu.triggered.disconnect()
        except Exception as e:
            pass
        menu.triggered.connect(menuHistory_Clicked)

        menu.clear()
        menu.addAction(self.__actionHistoryClear)
        if not self.__history is None:
            self.__history.removeMissing(False, refList=self.__uiController.quickRefDict())
        if not self.__history is None and self.__history.length() > 0:
            self.__actionHistoryClear.setEnabled(True)
            self.__actionHistoryClear.setText(i18n(f'Clear history ({self.__history.length()})'))
            menu.addSeparator()

            for path in reversed(self.__history.list()):
                action = QAction(path.replace('&', '&&'), self)
                action.setFont(self.__font)
                action.setProperty('path', path)

                menu.addAction(action)
        else:
            self.__actionHistoryClear.setEnabled(False)
            self.__actionHistoryClear.setText(i18n('Clear history'))

    def menuBookmarksShow(self, menu=None):
        """Build menu bookmarks"""
        @pyqtSlot('QString')
        def menuBookmarks_Clicked(action):
            # change directory
            path=action.property('path')
            if not path is None:
                if os.path.isdir(path):
                    self.setPath(path)
                else:
                    name = self.__uiController.bookmark().nameFromValue(path)
                    self.__uiController.commandGoBookmarkRemoveUI(name)

        self.clicked.emit(False)

        if menu is None:
            menu = self.btBookmark.menu()

        try:
            menu.triggered.disconnect()
        except Exception as e:
            pass

        menu.triggered.connect(menuBookmarks_Clicked)

        menu.clear()
        menu.addAction(self.__actionBookmarkClear)
        menu.addAction(self.__actionBookmarkAdd)
        menu.addAction(self.__actionBookmarkRemove)
        menu.addAction(self.__actionBookmarkRename)


        if not self.__bookmark is None and self.__bookmark.length() > 0:
            self.__actionBookmarkClear.setEnabled(True)
            self.__actionBookmarkClear.setText(i18n('Clear bookmark')+f' ({self.__bookmark.length()})')
            menu.addSeparator()

            currentPath = self.path()
            isInBookmark = False

            for bookmark in self.__bookmark.list():
                action = QAction(bookmark[BCBookmark.NAME].replace('&', '&&'), self)
                action.setFont(self.__font)
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

                menu.addAction(action)

            if isInBookmark:
                self.__actionBookmarkAdd.setEnabled(False)
                self.__actionBookmarkRemove.setEnabled(True)
                self.__actionBookmarkRename.setEnabled(True)
            else:
                self.__actionBookmarkAdd.setEnabled(self.mode() != BCWPathBar.MODE_SAVEDVIEW)
                self.__actionBookmarkRemove.setEnabled(False)
                self.__actionBookmarkRename.setEnabled(False)
        else:
            self.__actionBookmarkClear.setEnabled(False)
            self.__actionBookmarkClear.setText(i18n('Clear bookmark'))
            self.__actionBookmarkAdd.setEnabled(self.mode() != BCWPathBar.MODE_SAVEDVIEW)
            self.__actionBookmarkRemove.setEnabled(False)
            self.__actionBookmarkRename.setEnabled(False)

    def menuSavedViewsShow(self, menu=None):
        # TODO: build menu
        self.clicked.emit(False)

        if menu is None:
            menu = self.btSavedViews.menu()

        try:
            menu.triggered.disconnect()
        except Exception as e:
            pass

        menu.triggered.connect(self.__menuSavedViews_clicked)

        menu.clear()
        menu.addAction(self.__actionSavedViewsClear)
        menu.addMenu(self.__actionSavedViewsAdd)
        menu.addAction(self.__actionSavedViewsRemove)
        menu.addSeparator()
        menu.addAction(self.__actionSavedViewsRename)
        menu.addAction(self.__actionSavedViewsDelete)

        menu2 = self.__actionSavedViewsAdd
        menu2.clear()
        menu2.addAction(self.__actionSavedViewsAddNewView)

        allowAddRemove = False
        if self.__panel.filesSelected()[3] > 0:
            # Selected nb directories + files > 0
            # can be added to a current view
            allowAddRemove = True

        self.__actionSavedViewsAddNewView.setEnabled(allowAddRemove)


        isSavedView = (self.__uiController.quickRefType(self.path()) == BCWPathBar.QUICKREF_SAVEDVIEW_LIST)


        if self.__savedView.length() > 0:
            # there's some view saved
            # build list of saved views
            menu.addSeparator()
            menu2.addSeparator()

            for view in self.__savedView.list():
                # view = (name, files)
                if not re.match("^searchresult:", view[0]):
                    action = buildQAction([("pktk:saved_view_file", QIcon.Normal),
                                           ("pktk:saved_view_file", QIcon.Disabled)], view[0].replace('&', '&&'), self)
                    action.setFont(self.__font)
                    action.setStatusTip(i18n(f"Add selected files to view '{view[0].replace('&', '&&')}' (Current files in view: {len(view[1])})" ))
                    action.setProperty('action', 'add_to_view')
                    action.setProperty('path', f'@{view[0]}')

                    if isSavedView and self.__savedView.current(True) == view[0] or not allowAddRemove:
                        action.setEnabled(False)

                    menu2.addAction(action)

                    action = buildQAction([("pktk:saved_view_file", QIcon.Normal),
                                           ("pktk:saved_view_file", QIcon.Disabled)], view[0].replace('&', '&&'), self)
                    action.setFont(self.__font)
                    action.setCheckable(True)
                    action.setStatusTip(i18n(f'Files in view: {len(view[1])}'))
                    action.setProperty('action', 'go_to_view')
                    action.setProperty('path', f'@{view[0]}')

                    if isSavedView and self.__savedView.current(True) == view[0]:
                        action.setChecked(True)

                    menu.addAction(action)

        if isSavedView:
            self.__actionSavedViewsClear.setEnabled(True)
            self.__actionSavedViewsRemove.setEnabled(allowAddRemove)
            self.__actionSavedViewsRename.setEnabled(True)
            self.__actionSavedViewsDelete.setEnabled(True)
        else:
            self.__actionSavedViewsClear.setEnabled(False)
            self.__actionSavedViewsRemove.setEnabled(False)
            self.__actionSavedViewsRename.setEnabled(False)
            self.__actionSavedViewsDelete.setEnabled(False)

    def menuLastDocumentsShow(self, menu=None):
        """Build menu last documents"""
        @pyqtSlot('QString')
        def menuLastDocuments_Clicked(action):
            # change directory
            self.setPath(action.property('path'))

        self.clicked.emit(False)

        if menu is None:
            menu = self.btLastDocuments.menu()

        try:
            menu.triggered.disconnect()
        except Exception as e:
            pass
        menu.triggered.connect(menuLastDocuments_Clicked)


        self.__actionLastDocumentsAll.setEnabled(self.__lastDocumentsSaved.length() + self.__lastDocumentsOpened.length())
        self.__actionLastDocumentsSaved.setEnabled(self.__lastDocumentsSaved.length())
        self.__actionLastDocumentsOpened.setEnabled(self.__lastDocumentsOpened.length())

        menu.clear()
        menu.addAction(self.__actionLastDocumentsAll)
        menu.addSeparator()
        menu.addAction(self.__actionLastDocumentsOpened)
        menu.addAction(self.__actionLastDocumentsSaved)

    def __refreshStyle(self):
        """refresh current style for BCWPathBar"""
        self.frameBreacrumbPath.setHighlighted(self.__isHighlighted)
        self.update()

    def __refreshFilter(self):
        """Refresh filter layout"""
        self.setMinimumHeight(0)
        idealMinHeight=self.widgetPath.sizeHint().height()

        if self.btFilter.isChecked():
            self.frameFilter.setVisible(True)
            self.leFilterQuery.setFocus()
            self.leFilterQuery.selectAll()
            self.filterVisibilityChanged.emit(True)
            idealMinHeight+=self.widgetFilter.sizeHint().height()
        else:
            self.frameFilter.setVisible(False)
            self.filterVisibilityChanged.emit(False)

        self.setMinimumHeight(idealMinHeight)

    def __menuBookmarkAppend_clicked(self, action):
        """Append current path to bookmark"""
        self.__uiController.commandGoBookmarkAppendUI(self.path())

    def __menuBookmarkRemove_clicked(self, action):
        """Remove bookmark"""
        name = self.__uiController.bookmark().nameFromValue(self.path())
        self.__uiController.commandGoBookmarkRemoveUI(name)

    def __menuBookmarkRename_clicked(self, action):
        """Rename bookmark"""
        name = self.__uiController.bookmark().nameFromValue(self.path())
        self.__uiController.commandGoBookmarkRenameUI(name)

    def __menuSavedViews_clicked(self, action):
        """AN action from saved view is triggered"""
        menuAction = action.property('action')
        viewId=action.property('path')

        if viewId == ':CURRENT':
            viewId = self.__savedView.current(True)

        if menuAction == 'create_view':
            self.__uiController.commandGoSavedViewCreateUI([file.fullPathName() for file in self.__panel.filesSelected()[0]])
        elif menuAction == 'add_to_view':
            self.__uiController.commandGoSavedViewAppend(viewId[1:], [file.fullPathName() for file in self.__panel.filesSelected()[0]])
        elif menuAction == 'go_to_view':
            self.setPath(viewId)
        elif menuAction == 'delete_view':
            self.__uiController.commandGoSavedViewDeleteUI(viewId)
        elif menuAction == 'rename_view':
            self.__uiController.commandGoSavedViewRenameUI(viewId)
        elif menuAction == 'remove_from_view':
            if self.__panel.filesSelected()[3] > 0:
                # Remove given files from view
                self.__uiController.commandGoSavedViewRemoveUI(viewId, [file.fullPathName() for file in self.__panel.filesSelected()[5]])
        elif menuAction == 'clear_view_content':
            self.__uiController.commandGoSavedViewClearUI(viewId)

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
        self.btBack.setEnabled(self.__backList.length()>1)

    def paintEvent(self, event):
        super(BCWPathBar, self).paintEvent(event)

        rect=QRect(0, 0, self.width(), self.height())

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
        #if not (uiController is None or isinstance(uiController, BCUIController)):
        #    raise EInvalidType('Given `uiController` must be a <BCUIController>')
        self.__uiController = uiController
        self.__actionHistoryClear.triggered.connect(self.__uiController.commandGoHistoryClearUI)
        self.__actionBookmarkClear.triggered.connect(self.__uiController.commandGoBookmarkClearUI)

    def mode(self):
        """Return current mode"""
        return self.__mode

    def setMode(self, mode):
        """Set current mode"""
        if not mode in [BCWPathBar.MODE_PATH, BCWPathBar.MODE_SAVEDVIEW]:
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
        elif not self.__savedView is None:
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
            if not last is None:
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
        #if not isinstance(value, BCHistory):
        #    raise EInvalidType("Given `value` must be a <BCHistory>")
        if not value is None:
            self.__history=value
            self.__history.changed.connect(self.__historyChanged)

    def bookmark(self):
        """Return bookmarks"""
        return self.__bookmark

    def setBookmark(self, value):
        """Set bookmark list"""
        #if not isinstance(value, BCBookmark):
        #    raise EInvalidType("Given `value` must be a <BCBookmark>")
        if not value is None:
            self.__bookmark = value
            self.__bookmark.changed.connect(self.__bookmarkChanged)

    def savedView(self):
        """Return saved views"""
        return self.__savedView

    def setSavedView(self, value):
        """Set saved views"""
        if not value is None:
            self.__savedView = value
            self.__savedView.updated.connect(self.__savedViewChanged)
            self.frameBreacrumbPath.quickRefDict=self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath=self.__uiController.quickRefPath

    def lastDocumentsOpened(self):
        """Return last opened document views"""
        return self.__lastDocumentsOpened

    def setLastDocumentsOpened(self, value):
        """Set last opened document views"""
        if not value is None:
            self.__lastDocumentsOpened = value
            self.__lastDocumentsOpened.changed.connect(self.__lastDocumentsOpenedChanged)
            self.frameBreacrumbPath.quickRefDict=self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath=self.__uiController.quickRefPath

    def lastDocumentsSaved(self):
        """Return last saved document views"""
        return self.__lastDocumentsSaved

    def setLastDocumentsSaved(self, value):
        """Set last saved document views"""
        if not value is None:
            self.__lastDocumentsSaved = value
            self.__lastDocumentsSaved.changed.connect(self.__lastDocumentsSavedChanged)
            self.frameBreacrumbPath.quickRefDict=self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath=self.__uiController.quickRefPath

    def backupFilterDView(self):
        """Return backup dynamic view object"""
        return self.__backupFilterDView

    def setBackupFilterDView(self, value):
        """Set backup dynamic view object"""
        if not value is None:
            self.__backupFilterDView = value
            self.__backupFilterDView.changed.connect(self.__backupFilterDViewChanged)
            self.frameBreacrumbPath.quickRefDict=self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath=self.__uiController.quickRefPath

    def fileLayerFilterDView(self):
        """Return file layer dynamic view object"""
        return self.__fileLayerFilterDView

    def setFileLayerFilterDView(self, value):
        """Set file layer dynamic view object"""
        if not value is None:
            self.__fileLayerFilterDView = value
            self.__fileLayerFilterDView.changed.connect(self.__fileLayerFilterDViewChanged)
            self.frameBreacrumbPath.quickRefDict=self.__uiController.quickRefDict
            self.frameBreacrumbPath.getQuickRefPath=self.__uiController.quickRefPath

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
        """Return current filter value"""
        return self.leFilterQuery.text()

    def setFilter(self, value=None):
        """Set current filter value"""
        if value is None:
            value = ''
        self.leFilterQuery.setText(value)

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
            self.widgetPath.setContentsMargins(2,2,2,2)
        else:
            self.widgetPath.setMinimumHeight(0)
            self.widgetPath.setContentsMargins(0,0,0,0)

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
