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

import sys
import os

import PyQt5.uic

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )
from PyQt5.QtWidgets import (
        QWidget,
        QFrame
    )
from PyQt5.QtGui import (
        QColor,
        QPalette
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


from bulicommander.pktk.pktk import (
        EInvalidType
    )

from bulicommander.libs.breadcrumbsaddressbar.breadcrumbsaddressbar import (
        BreadcrumbsAddressBar
    )



# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------
class BCPathBar(QFrame):
    """Buli Commander path bar"""

    clicked = Signal(bool)

    def __init__(self, id, parent=None):
        super(BCPathBar, self).__init__(parent)

        self.__id = id
        self.__isHighlighted = False

        self.__paletteBase = self.palette()
        self.__paletteBase.setColor(QPalette.Window, self.__paletteBase.color(QPalette.Base))

        self.__paletteHighlighted = self.palette()
        self.__paletteHighlighted.setColor(QPalette.Window, self.__paletteHighlighted.color(QPalette.Highlight))

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcpathbar.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__initialise()

    def __initialise(self):
        """Initialise BCPathBar"""

        @pyqtSlot('QString')
        def item_Clicked(value):
            self.clicked.emit(False)

        self.widgetPath.setPalette(self.__paletteBase)
        self.widgetPath.setAutoFillBackground(True)

        self.btBookmark.clicked.connect(item_Clicked)
        self.btSearch.clicked.connect(item_Clicked)
        self.frameBreacrumbPath.clicked.connect(item_Clicked)


    def __refreshStyle(self):
        """refresh current style for BCPathBar"""
        if self.__isHighlighted:
            self.widgetPath.setPalette(self.__paletteHighlighted)
        else:
            self.widgetPath.setPalette(self.__paletteBase)

        self.frameBreacrumbPath.setHighlighted(self.__isHighlighted)


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


