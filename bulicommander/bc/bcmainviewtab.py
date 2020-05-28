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

from enum import Enum

import krita
import os
import re
import sys
import time

import PyQt5.uic

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )
from PyQt5.QtWidgets import (
        QAction,
        QFrame,
        QMenu,
        QWidget
    )

from .bcbookmark import BCBookmark
from .bchistory import BCHistory
from .bcpathbar import BCPathBar


# -----------------------------------------------------------------------------
class BCMainViewTabFilesLayout(Enum):
    FULL = 'full'
    TOP = 'top'
    LEFT = 'left'
    BOTTOM = 'bottom'
    RIGHT = 'right'

    def next(self):
        """Return next layout, if already to last layout, loop to first layout"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) + 1
        if index >= len(members):
            index = 0
        return members[index]

    def prev(self):
        """Return previous layout, if already to first layout, loop to last layout"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) - 1
        if index < 0:
            index = len(members) - 1
        return members[index]

class BCMainViewTabFilesTabs(Enum):
    INFORMATIONS = 'info'
    DIRECTORIES_TREE = 'dirtree'

class BCMainViewTabFilesNfoTabs(Enum):
    GENERIC = 'generic'
    KRA = 'kra'

class BCMainViewTabTabs(Enum):
    FILES = 'files'
    DOCUMENTS = 'documents'


# -----------------------------------------------------------------------------
class BCMainViewTab(QFrame):
    """Buli Commander main view tab panel (left or right)"""

    highlightedStatusChanged = Signal(QTabWidget)
    tabFilesLayoutChanged = Signal(QTabWidget)
    pathChanged = Signal(str)

    def __init__(self, parent=None):
        super(BCMainViewTab, self).__init__(parent)

        self.__tabFilesLayout = BCMainViewTabFilesLayout.TOP
        self.__isHighlighted = False
        self.__uiController = None


        self.__actionApplyTabFilesLayoutFull = QAction(i18n('Full mode'), self)
        self.__actionApplyTabFilesLayoutFull.setCheckable(True)
        self.__actionApplyTabFilesLayoutFull.setProperty('layout', BCMainViewTabFilesLayout.FULL)

        self.__actionApplyTabFilesLayoutTop = QAction(i18n('Top/Bottom'), self)
        self.__actionApplyTabFilesLayoutTop.setCheckable(True)
        self.__actionApplyTabFilesLayoutTop.setProperty('layout', BCMainViewTabFilesLayout.TOP)

        self.__actionApplyTabFilesLayoutLeft = QAction(i18n('Left/Right'), self)
        self.__actionApplyTabFilesLayoutLeft.setCheckable(True)
        self.__actionApplyTabFilesLayoutLeft.setProperty('layout', BCMainViewTabFilesLayout.LEFT)

        self.__actionApplyTabFilesLayoutBottom = QAction(i18n('Bottom/Top'), self)
        self.__actionApplyTabFilesLayoutBottom.setCheckable(True)
        self.__actionApplyTabFilesLayoutBottom.setProperty('layout', BCMainViewTabFilesLayout.BOTTOM)

        self.__actionApplyTabFilesLayoutRight = QAction(i18n('Right/Left'), self)
        self.__actionApplyTabFilesLayoutRight.setCheckable(True)
        self.__actionApplyTabFilesLayoutRight.setProperty('layout', BCMainViewTabFilesLayout.RIGHT)


        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcmainviewtab.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__initialise()


    def __initialise(self):
        #@pyqtSlot('QString')
        #def splitterFiles_Moved(pos, index):
        #    print('splitter:', pos, index, '-', self.splitterFiles.sizes())

        @pyqtSlot('QString')
        def tabFilesLayoutModel_Clicked(value):
            self.setTabFilesLayout(value.property('layout'))

        @pyqtSlot('QString')
        def tabFilesLayoutReset_Clicked(value):
            self.setTabFilesLayout(BCMainViewTabFilesLayout.TOP)

        @pyqtSlot('QString')
        def children_Clicked(value):
            self.setHighlighted(True)

        @pyqtSlot('QString')
        def path_Changed(value):
            self.pathChanged.emit(value)

        self.__actionApplyTabFilesLayoutFull.triggered.connect(children_Clicked)
        self.__actionApplyTabFilesLayoutTop.triggered.connect(children_Clicked)
        self.__actionApplyTabFilesLayoutLeft.triggered.connect(children_Clicked)
        self.__actionApplyTabFilesLayoutBottom.triggered.connect(children_Clicked)
        self.__actionApplyTabFilesLayoutRight.triggered.connect(children_Clicked)

        # create menu for layout model button
        menu = QMenu(self.btTabFilesLayoutModel)
        menu.addAction(self.__actionApplyTabFilesLayoutFull)
        menu.addAction(self.__actionApplyTabFilesLayoutTop)
        menu.addAction(self.__actionApplyTabFilesLayoutLeft)
        menu.addAction(self.__actionApplyTabFilesLayoutBottom)
        menu.addAction(self.__actionApplyTabFilesLayoutRight)
        menu.triggered.connect(tabFilesLayoutModel_Clicked)

        self.btTabFilesLayoutModel.setMenu(menu)
        self.btTabFilesLayoutModel.clicked.connect(tabFilesLayoutReset_Clicked)

        self.splitterFiles.setSizes([1000, 1000]);
        #self.splitterFiles.splitterMoved.connect(splitterFiles_Moved)

        self.tabMain.tabBarClicked.connect(children_Clicked)
        self.tabFilesDetails.tabBarClicked.connect(children_Clicked)
        self.treeViewFiles.activated.connect(children_Clicked)
        self.treewDirectoryTree.activated.connect(children_Clicked)
        self.toolBoxInfo.currentChanged.connect(children_Clicked)
        self.btTabFilesLayoutModel.clicked.connect(children_Clicked)
        self.framePathBar.clicked.connect(children_Clicked)
        self.framePathBar.pathChanged.connect(path_Changed)
        self.framePathBar.setPanel(self)

        self.__refreshTabFilesLayout()


    def __refreshTabFilesLayout(self):
        """Refresh layout according to current configuration"""
        if self.__tabFilesLayout == BCMainViewTabFilesLayout.FULL:
            self.tabFilesDetails.setVisible(False)
            self.__actionApplyTabFilesLayoutFull.setChecked(True)
            self.__actionApplyTabFilesLayoutTop.setChecked(False)
            self.__actionApplyTabFilesLayoutLeft.setChecked(False)
            self.__actionApplyTabFilesLayoutBottom.setChecked(False)
            self.__actionApplyTabFilesLayoutRight.setChecked(False)
        else:
            self.__actionApplyTabFilesLayoutFull.setChecked(False)

            self.tabFilesDetails.setVisible(True)
            if self.__tabFilesLayout == BCMainViewTabFilesLayout.TOP:
                self.splitterFiles.setOrientation(Qt.Vertical)
                self.splitterFiles.insertWidget(0, self.stackFiles)
                self.tabFilesDetailsInformations.layout().setDirection(QBoxLayout.LeftToRight)

                self.__actionApplyTabFilesLayoutTop.setChecked(True)
                self.__actionApplyTabFilesLayoutLeft.setChecked(False)
                self.__actionApplyTabFilesLayoutBottom.setChecked(False)
                self.__actionApplyTabFilesLayoutRight.setChecked(False)

            elif self.__tabFilesLayout == BCMainViewTabFilesLayout.LEFT:
                self.splitterFiles.setOrientation(Qt.Horizontal)
                self.splitterFiles.insertWidget(0, self.stackFiles)
                self.tabFilesDetailsInformations.layout().setDirection(QBoxLayout.TopToBottom)

                self.__actionApplyTabFilesLayoutTop.setChecked(False)
                self.__actionApplyTabFilesLayoutLeft.setChecked(True)
                self.__actionApplyTabFilesLayoutBottom.setChecked(False)
                self.__actionApplyTabFilesLayoutRight.setChecked(False)

            elif self.__tabFilesLayout == BCMainViewTabFilesLayout.BOTTOM:
                self.splitterFiles.setOrientation(Qt.Vertical)
                self.splitterFiles.insertWidget(1, self.stackFiles)
                self.tabFilesDetailsInformations.layout().setDirection(QBoxLayout.LeftToRight)

                self.__actionApplyTabFilesLayoutTop.setChecked(False)
                self.__actionApplyTabFilesLayoutLeft.setChecked(False)
                self.__actionApplyTabFilesLayoutBottom.setChecked(True)
                self.__actionApplyTabFilesLayoutRight.setChecked(False)

            elif self.__tabFilesLayout == BCMainViewTabFilesLayout.RIGHT:
                self.splitterFiles.setOrientation(Qt.Horizontal)
                self.splitterFiles.insertWidget(1, self.stackFiles)
                self.tabFilesDetailsInformations.layout().setDirection(QBoxLayout.TopToBottom)

                self.__actionApplyTabFilesLayoutTop.setChecked(False)
                self.__actionApplyTabFilesLayoutLeft.setChecked(False)
                self.__actionApplyTabFilesLayoutBottom.setChecked(False)
                self.__actionApplyTabFilesLayoutRight.setChecked(True)

        self.tabFilesLayoutChanged.emit(self)


    def __refreshPanelHighlighted(self):
        """Refresh panel highlighted and emit signal"""
        self.framePathBar.setHighlighted(self.__isHighlighted)
        if self.__isHighlighted:
            self.highlightedStatusChanged.emit(self)


    def uiController(self):
        """Return uiController"""
        return self.__uiController


    def setUiController(self, uiController):
        """Set uiController"""
        #if not (uiController is None or isinstance(uiController, BCUIController)):
        #    raise EInvalidType('Given `uiController` must be a <BCUIController>')
        self.__uiController = uiController
        self.framePathBar.setUiController(uiController)


    def tabFilesLayout(self):
        """return current layout for file panel"""
        return self.__tabFilesLayout


    def setTabFilesLayout(self, layout):
        """Set new layout for file panel"""
        if isinstance(layout, str):
            layout = BCMainViewTabFilesLayout(layout)
        elif not isinstance(layout, BCMainViewTabFilesLayout):
            raise EInvalidType("Given `layout` must be a <BCMainViewTabFilesLayout>")

        if self.__tabFilesLayout != layout:
            self.__tabFilesLayout = layout
            self.__refreshTabFilesLayout()


    def isHighlighted(self):
        """Return True is panel is highlighted, otherwise False"""
        return self.__isHighlighted


    def setHighlighted(self, value):
        """Set current highlighted panel status

        If highlighted status is changed, emit Signal
        """
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
        elif self.__isHighlighted != value:
            self.__isHighlighted = value
            self.__refreshPanelHighlighted()


    def tabIndex(self, id):
        """Return tab (index, objectName) from given id"""
        if isinstance(id, str):
            id = BCMainViewTabTabs(id)

        if not isinstance(id, BCMainViewTabTabs):
            raise EInvalidType('Given `id` must be a BCMainViewTabTabs')

        for index in range(self.tabMain.count()):
            if self.tabMain.widget(index).objectName() == 'tabFiles' and id == BCMainViewTabTabs.FILES:
                return (index, 'tabFiles')
            elif self.tabMain.widget(index).objectName() == 'tabDocuments' and id == BCMainViewTabTabs.DOCUMENTS:
                return (index, 'tabDocuments')

        return (-1, '')


    def tabActive(self):
        """Return current active tab"""
        if self.tabMain.currentWidget().objectName() == 'tabFiles':
            return BCMainViewTabTabs.FILES
        else:
            return BCMainViewTabTabs.DOCUMENTS


    def setTabActive(self, id):
        """Set current active tab"""
        index, name = self.tabIndex(id)

        if index > -1:
            self.tabMain.setCurrentIndex(index)


    def tabOrder(self):
        """Return list of tab, with current applied order"""
        returned = []
        for index in range(self.tabMain.count()):
            if self.tabMain.widget(index).objectName() == 'tabFiles':
                returned.append(BCMainViewTabTabs.FILES)
            elif self.tabMain.widget(index).objectName() == 'tabDocuments':
                returned.append(BCMainViewTabTabs.DOCUMENTS)
        return returned


    def setTabOrder(self, tabs):
        """Set tab order"""
        if not isinstance(tabs, list):
            raise EInvalidType('Given `tabs` must be a list')
        if len(tabs) != self.tabMain.count():
            raise EInvalidType('Given `tabs` list must have the same number of item than panel tab')

        for tabIndex in range(len(tabs)):
            index, name = self.tabIndex(tabs[tabIndex])
            if index != tabIndex:
                self.tabMain.tabBar().moveTab(index, tabIndex)


    def tabFilesIndex(self, id):
        """Return tab (index, objectName) from given id"""
        if isinstance(id, str):
            id = BCMainViewTabFilesTabs(id)

        if not isinstance(id, BCMainViewTabFilesTabs):
            raise EInvalidType('Given `id` must be a BCMainViewTabFilesTabs')

        for index in range(self.tabFilesDetails.count()):
            if self.tabFilesDetails.widget(index).objectName() == 'tabFilesDetailsInformations' and id == BCMainViewTabFilesTabs.INFORMATIONS:
                return (index, 'tabFilesDetailsInformations')
            elif self.tabFilesDetails.widget(index).objectName() == 'tabFilesDetailsDirTree' and id == BCMainViewTabFilesTabs.DIRECTORIES_TREE:
                return (index, 'tabFilesDetailsDirTree')

        return (-1, '')


    def tabFilesActive(self):
        """Return current active tab into tab files"""
        if self.tabFilesDetails.currentWidget().objectName() == 'tabFilesDetailsInformations':
            return BCMainViewTabFilesTabs.INFORMATIONS
        else:
            return BCMainViewTabFilesTabs.DIRECTORIES_TREE


    def setTabFilesActive(self, id):
        """Set current active tab into tab files"""
        index, name = self.tabFilesIndex(id)

        if index > -1:
            self.tabFilesDetails.setCurrentIndex(index)


    def tabFilesOrder(self):
        """Return list of tab, with current applied order"""
        returned = []
        for index in range(self.tabFilesDetails.count()):
            if self.tabFilesDetails.widget(index).objectName() == 'tabFilesDetailsInformations':
                returned.append(BCMainViewTabFilesTabs.INFORMATIONS)
            elif self.tabFilesDetails.widget(index).objectName() == 'tabFilesDetailsDirTree':
                returned.append(BCMainViewTabFilesTabs.DIRECTORIES_TREE)
        return returned


    def setTabFilesOrder(self, tabs):
        """Set tab order"""
        if not isinstance(tabs, list):
            raise EInvalidType('Given `tabs` must be a list')
        if len(tabs) != self.tabFilesDetails.count():
            raise EInvalidType('Given `tabs` list must have the same number of item than panel tab')

        for tabIndex in range(len(tabs)):
            index, name = self.tabFilesIndex(tabs[tabIndex])
            if index != tabIndex:
                self.tabFilesDetails.tabBar().moveTab(index, tabIndex)


    def tabFilesNfoIndex(self, id):
        """Return tab (index, objectName) from given id"""
        if isinstance(id, str):
            id = BCMainViewTabFilesNfoTabs(id)

        if not isinstance(id, BCMainViewTabFilesNfoTabs):
            raise EInvalidType('Given `id` must be a BCMainViewTabFilesNfoTabs')

        for index in range(self.toolBoxInfo.count()):
            if self.toolBoxInfo.widget(index).objectName() == 'pageFileNfoGeneric' and id == BCMainViewTabFilesNfoTabs.GENERIC:
                return (index, 'pageFileNfoGeneric')
            elif self.toolBoxInfo.widget(index).objectName() == 'pageFileNfoKra' and id == BCMainViewTabFilesNfoTabs.KRA:
                return (index, 'pageFileNfoKra')

        return (-1, '')


    def tabFilesNfoActive(self):
        """Return current active nfo tab into tab files"""
        if self.toolBoxInfo.currentWidget().objectName() == 'pageFileNfoGeneric':
            return BCMainViewTabFilesNfoTabs.GENERIC
        else:
            return BCMainViewTabFilesNfoTabs.KRA


    def setTabFilesNfoActive(self, id):
        """Set current active tab into tab files"""
        index, name = self.tabFilesNfoIndex(id)

        if index > -1:
            self.toolBoxInfo.setCurrentIndex(index)


    def tabFilesSplitterPosition(self):
        """Return splitter position for tab files"""
        return self.splitterFiles.sizes()


    def setTabFilesSplitterPosition(self, positions=None):
        """Set splitter position for tab files"""
        if positions is None:
            positions = [1000, 1000]

        if not isinstance(positions, list) or len(positions) != 2:
            raise EInvalidValue('Given `positions` must be a list [l,r]')

        self.splitterFiles.setSizes(positions)

        return self.splitterFiles.sizes()


    def currentPath(self):
        """Return current path"""
        return self.framePathBar.path()


    def setCurrentPath(self, path=None):
        """Set current path"""
        return self.framePathBar.setPath(path)

    def goToBackPath(self):
        """Go to previous path"""
        return self.framePathBar.goToBackPath()

    def goToUpPath(self):
        """Go to previous path"""
        return self.framePathBar.goToUpPath()


    def history(self, value):
        """return history object"""
        self.framePathBar.history()


    def setHistory(self, value):
        """Set history object"""
        self.framePathBar.setHistory(value)


    def bookmark(self):
        """return bookmark object"""
        self.framePathBar.bookmark()


    def setBookmark(self, value):
        """Set bookmark object"""
        self.framePathBar.setBookmark(value)


    def filterVisible(self):
        """Return if filter is visible or not"""
        return self.framePathBar.filterVisible()


    def setFilterVisible(self, visible=None):
        """Display the filter

        If visible is None, invert current status
        If True, display filter
        If False, hide
        """
        self.framePathBar.setFilterVisible(visible)


    def filter(self):
        """Return current filter value"""
        return self.framePathBar.filter()


    def setFilter(self, value=None):
        """Set current filter value"""
        self.framePathBar.setFilter(value)


    def hiddenPath(self):
        """Return if hidden path are displayed or not"""
        return self.framePathBar.hiddenPath()


    def setHiddenPath(self, value=False):
        """Set if hidden path are displayed or not"""
        self.framePathBar.setHiddenPath(value)