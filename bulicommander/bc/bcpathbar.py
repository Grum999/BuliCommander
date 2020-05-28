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

import sys
import os

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


# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------
class BCPathBar(QFrame):
    """Buli Commander path bar"""

    clicked = Signal(bool)
    pathChanged = Signal(str)

    def __init__(self, parent=None):
        super(BCPathBar, self).__init__(parent)

        self.__isHighlighted = False

        self.__uiController = None
        self.__panel = None

        self.__paletteBase = self.palette()
        self.__paletteBase.setColor(QPalette.Window, self.__paletteBase.color(QPalette.Base))

        self.__paletteHighlighted = self.palette()
        self.__paletteHighlighted.setColor(QPalette.Window, self.__paletteHighlighted.color(QPalette.Highlight))

        self.__history = None
        self.__bookmark = None
        self.__backList = BCHistory()

        self.__font = QFont()
        self.__font.setPointSize(9)
        self.__font.setFamily('DejaVu Sans Mono')

        self.__actionHistoryClear = QAction(i18n('Clear history'), self)

        self.__actionBookmarkClear = QAction(i18n('Clear bookmark'), self)
        self.__actionBookmarkAdd = QAction(i18n('Add to bookmark...'), self)
        self.__actionBookmarkAdd.triggered.connect(self.__menuBookmarkAppend_clicked)
        self.__actionBookmarkRemove = QAction(i18n('Remove from bookmark...'), self)
        self.__actionBookmarkRemove.triggered.connect(self.__menuBookmarkRemove_clicked)
        self.__actionBookmarkRename = QAction(i18n('Rename bookmark...'), self)
        self.__actionBookmarkRename.triggered.connect(self.__menuBookmarkRename_clicked)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcpathbar.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        print('bar', self)

        self.__initialise()

    def __initialise(self):
        """Initialise BCPathBar"""

        @pyqtSlot('QString')
        def item_Clicked(value):
            self.clicked.emit(False)

        @pyqtSlot('QString')
        def up_Clicked(value):
            if not self.__uiController is None:
                self.__uiController.commandGoUp(self.__panel)

        @pyqtSlot('QString')
        def back_Clicked(value):
            if not self.__uiController is None:
                self.__uiController.commandGoBack(self.__panel)

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
            self.pathChanged.emit(self.path())

        @pyqtSlot('QString')
        def menuHistory_Clicked(action):
            # change directory
            self.setPath(action.property('path'))

        @pyqtSlot('QString')
        def menuBookmarks_Clicked(action):
            # change directory
            self.setPath(action.property('path'))

        self.widgetPath.setPalette(self.__paletteBase)
        self.widgetPath.setAutoFillBackground(True)

        self.btBookmark.clicked.connect(item_Clicked)
        self.btHistory.clicked.connect(item_Clicked)
        self.btFilter.clicked.connect(item_Clicked)
        self.btFilter.clicked.connect(self.__refreshFilter)
        self.frameBreacrumbPath.clicked.connect(item_Clicked)
        self.frameBreacrumbPath.path_selected.connect(path_Selected)

        self.leFilterQuery.enterEvent=edit_Clicked

        self.btBack.clicked.connect(item_Clicked)
        self.btBack.clicked.connect(back_Clicked)
        self.btUp.clicked.connect(item_Clicked)
        self.btUp.clicked.connect(up_Clicked)

        menu = QMenu(self.btHistory)
        menu.aboutToShow.connect(self.__menuHistoryShow)
        menu.triggered.connect(menuHistory_Clicked)
        menu.addAction(self.__actionHistoryClear)
        self.btHistory.setMenu(menu)

        menu = QMenu(self.btBookmark)
        menu.aboutToShow.connect(self.__menuBookmarksShow)
        menu.triggered.connect(menuBookmarks_Clicked)
        menu.addAction(self.__actionBookmarkClear)
        self.btBookmark.setMenu(menu)


    def __menuHistoryShow(self):
        """Build menu history"""
        self.clicked.emit(False)

        menu = self.btHistory.menu()

        menu.clear()
        menu.addAction(self.__actionHistoryClear)
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


    def __menuBookmarksShow(self):
        """Build menu bookmarks"""
        self.clicked.emit(False)

        menu = self.btBookmark.menu()

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
                action.setCheckable(True)
                action.setStatusTip(bookmark[BCBookmark.VALUE])

                if currentPath == bookmark[BCBookmark.VALUE]:
                    action.setChecked(True)
                    isInBookmark = True
                else:
                    action.setChecked(False)

                menu.addAction(action)

            if isInBookmark:
                self.__actionBookmarkAdd.setEnabled(False)
                self.__actionBookmarkRemove.setEnabled(True)
                self.__actionBookmarkRename.setEnabled(True)
            else:
                self.__actionBookmarkAdd.setEnabled(True)
                self.__actionBookmarkRemove.setEnabled(False)
                self.__actionBookmarkRename.setEnabled(False)
        else:
            self.__actionBookmarkClear.setEnabled(False)
            self.__actionBookmarkClear.setText(i18n('Clear bookmark'))
            self.__actionBookmarkAdd.setEnabled(True)
            self.__actionBookmarkRemove.setEnabled(False)
            self.__actionBookmarkRename.setEnabled(False)


    def __refreshStyle(self):
        """refresh current style for BCPathBar"""
        if self.__isHighlighted:
            self.widgetPath.setPalette(self.__paletteHighlighted)
        else:
            self.widgetPath.setPalette(self.__paletteBase)

        self.frameBreacrumbPath.setHighlighted(self.__isHighlighted)


    def __refreshFilter(self):
        """Refresh filter layout"""
        if self.btFilter.isChecked():
            self.widgetQuery.setVisible(True)
            self.leFilterQuery.setFocus()
            self.leFilterQuery.selectAll()
        else:
            self.widgetQuery.setVisible(False)


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


    def __historyChanged(self):
        """History content has been modified"""
        pass

    def __bookmarkChanged(self):
        """Bookmark content has been modified"""
        pass

    def __updateUpBtn(self):
        """update up button status"""
        self.btUp.setEnabled(str(self.frameBreacrumbPath.path()) != self.frameBreacrumbPath.path().root)


    def __updateBackBtn(self):
        """update back button status"""
        self.btBack.setEnabled(self.__backList.length()>1)


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

    def panel(self):
        """Return current panel for which BCPathBar is attached to"""
        return self.__panel

    def setPanel(self, value):
        """Set current panel for which BCPathBar is attached to"""
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
        return str(self.frameBreacrumbPath.path())


    def setPath(self, path=None):
        """Set current path"""
        self.frameBreacrumbPath.set_path(path)

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
        self.setPath(str(self.frameBreacrumbPath.path().parent))

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