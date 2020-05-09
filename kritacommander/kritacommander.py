#-----------------------------------------------------------------------------
# Krita Commander
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

import os
import re
import sys
import time

import PyQt5.uic


from krita import (
        Extension,
        InfoObject,
        Node,
        Selection
    )

from PyQt5.Qt import *
from PyQt5 import QtCore
from PyQt5.QtCore import (
        pyqtSlot,
        #QByteArray,
        #QRect,
        #QStandardPaths,
        QObject
    )
from PyQt5.QtGui import (
        #QColor,
        QImage,
        QPixmap,
        QPolygonF
    )
from PyQt5.QtWidgets import (
        QApplication,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressBar,
        QProgressDialog,
        QVBoxLayout,
        QWidget
    )

if __name__ != '__main__':
    # script is executed from Krita, loaded as a module
    from .kcuicontroller import (
            KCUIController
        )

    from .pktk.edialog import (
            EDialog
        )

    from .pktk.ekrita import (
            EKritaNode
        )

    PLUGIN_EXEC_FROM = 'KRITA'
else:
    # Execution from 'Scripter' plugin?

    # Reload or Import
    if 'kritacommander.pktk.edialog' in sys.modules:
        from importlib import reload
        reload(sys.modules['kritacommander.pktk.edialog'])
    else:
        import kritacommander.pktk.edialog

    from kritacommander.pktk.edialog import (
            EDialog
        )

    if 'kritacommander.pktk.ekrita' in sys.modules:
        from importlib import reload
        reload(sys.modules['kritacommander.pktk.ekrita'])
    else:
        import kritacommander.pktk.ekrita

    from kritacommander.pktk.ekrita import (
            EKritaDocument,
            EKritaNode
        )

    if 'kritacommander.kcuicontroller' in sys.modules:
        from importlib import reload
        reload(sys.modules['kritacommander.kcuicontroller'])
    else:
        import kritacommander.kcuicontroller

    from kritacommander.kcuicontroller import (
            KCUIController
        )

    PLUGIN_EXEC_FROM = 'SCRIPTER_PLUGIN'


EXTENSION_ID = 'pykrita_kritacommander'
PLUGIN_VERSION = '0.1.0a'
PLUGIN_MENU_ENTRY = 'Krita Commander'



class KritaCommander(Extension):

    def __init__(self, parent):
        # Default options

        # Always initialise the superclass.
        # This is necessary to create the underlying C++ object
        super().__init__(parent)
        self.parent = parent


    def setup(self):
        """Is executed at Krita's startup"""
        pass


    def createActions(self, window):
        action = window.createAction(EXTENSION_ID, PLUGIN_MENU_ENTRY, "tools/scripts")
        action.triggered.connect(self.start)



    def start(self):
        """Execute KritaCommander controller"""
        # ----------------------------------------------------------------------
        # Create dialog box
        uiController = KCUIController(PLUGIN_MENU_ENTRY, PLUGIN_VERSION)
        uiController.start()



if PLUGIN_EXEC_FROM == 'SCRIPTER_PLUGIN':
    KritaCommander(Krita.instance()).start()
