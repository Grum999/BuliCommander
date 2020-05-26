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




if 'bulicommander.pktk.pktk' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.pktk.pktk'])
else:
    import bulicommander.pktk.pktk

if 'bulicommander.libs.breadcrumbsaddressbar.breadcrumbsaddressbar' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.libs.breadcrumbsaddressbar.breadcrumbsaddressbar'])
else:
    import bulicommander.libs.breadcrumbsaddressbar.breadcrumbsaddressbar

if 'bulicommander.bchistory' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.bchistory'])
else:
    import bulicommander.bchistory


from bulicommander.pktk.pktk import (
        EInvalidType
    )

from bulicommander.libs.breadcrumbsaddressbar.breadcrumbsaddressbar import (
        BreadcrumbsAddressBar
    )

from bulicommander.bchistory import (
        BCHistory
    )


# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------
class BCPathBar(QFrame):
    """Buli Commander path bar"""

    clicked = Signal(bool)
    pathChanged = Signal(str)

    def __init__(self, id, parent=None):
        super(BCPathBar, self).__init__(parent)

        self.__id = id
        self.__isHighlighted = False

        self.__paletteBase = self.palette()
        self.__paletteBase.setColor(QPalette.Window, self.__paletteBase.color(QPalette.Base))

        self.__paletteHighlighted = self.palette()
        self.__paletteHighlighted.setColor(QPalette.Window, self.__paletteHighlighted.color(QPalette.Highlight))

        self.__history = None

        self.__font = QFont()
        self.__font.setPointSize(9)
        self.__font.setFamily('DejaVu Sans Mono')

        self.__actionHistoryClear = QAction(i18n('(History is empty)'), self)
        self.__actionHistoryClear.setProperty('action', ':clear history')



        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcpathbar.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__initialise()

    def __initialise(self):
        """Initialise BCPathBar"""

        @pyqtSlot('QString')
        def item_Clicked(value):
            self.clicked.emit(False)

        @pyqtSlot('QString')
        def edit_Clicked(event):
            # need to review
            self.clicked.emit(False)
            event.accept()

        @pyqtSlot('QString')
        def path_Selected(value):
            self.pathChanged.emit(self.path())

        @pyqtSlot('QString')
        def menuHistory_Clicked(action):
            if action.property('action') == ':clear history':
                self.__history.clear()
            else:
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

        menu = QMenu(self.btHistory)
        menu.aboutToShow.connect(self.__menuHistoryShow)
        menu.triggered.connect(menuHistory_Clicked)
        menu.addAction(self.__actionHistoryClear)
        self.btHistory.setMenu(menu)


    def __menuHistoryShow(self):
        """Build menu"""
        self.clicked.emit(False)

        menu = self.btHistory.menu()

        menu.clear()
        menu.addAction(self.__actionHistoryClear)
        if not self.__history is None and len(self.__history) > 0:
            self.__actionHistoryClear.setEnabled(True)
            self.__actionHistoryClear.setText(i18n(f'Clear history ({len(self.__history)})'))
            menu.addSeparator()

            for path in reversed(self.__history):
                action = QAction(path.replace('&', '&&'), self)
                action.setFont(self.__font)
                action.setProperty('path', path)

                menu.addAction(action)
        else:
            self.__actionHistoryClear.setEnabled(False)
            self.__actionHistoryClear.setText(i18n('(History is empty)'))


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

    def setHistory(self, value):
        """Set history list"""
        #if not isinstance(value, BCHistory):
        #    raise EInvalidType("Given `value` must be a <BCHistory>")
        self.__history = value

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