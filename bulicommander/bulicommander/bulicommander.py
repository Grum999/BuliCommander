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


import os
import re
import sys
import time

import PyQt5.uic

from krita import (
        Extension,
        InfoObject,
        Node,
        Selection,
        Krita
    )

from PyQt5.Qt import *
from PyQt5 import QtCore
from PyQt5.QtCore import (
        pyqtSlot,
        # QByteArray,
        # QRect,
        # QStandardPaths,
        QObject
    )
from PyQt5.QtGui import (
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
        QMessageBox,
        QProgressBar,
        QProgressDialog,
        QVBoxLayout,
        QWidget
    )


if __name__ != '__main__':
    # script is executed from Krita, loaded as a module
    __PLUGIN_EXEC_FROM__ = 'KRITA'

    from .pktk.pktk import (
            EInvalidStatus,
            EInvalidType,
            EInvalidValue,
            PkTk
        )
    from bulicommander.pktk.modules.utils import checkKritaVersion
    from bulicommander.bc.bcuicontroller import BCUIController
else:
    # Execution from 'Scripter' plugin?
    __PLUGIN_EXEC_FROM__ = 'SCRIPTER_PLUGIN'

    from importlib import reload

    print("======================================")
    print(f'Execution from {__PLUGIN_EXEC_FROM__}')

    for module in list(sys.modules.keys()):
        if not re.search(r'^bulicommander\.', module) is None:
            print('Reload module {0}: {1}', module, sys.modules[module])
            reload(sys.modules[module])

    from bulicommander.pktk.pktk import (
            EInvalidStatus,
            EInvalidType,
            EInvalidValue,
            PkTk
        )
    from bulicommander.pktk.modules.utils import checkKritaVersion
    from bulicommander.bc.bcuicontroller import BCUIController

    print("======================================")


EXTENSION_ID = 'pykrita_bulicommander'
PLUGIN_VERSION = '0.9.0b'
PLUGIN_MENU_ENTRY = 'Buli Commander'

REQUIRED_KRITA_VERSION = (5, 0, 0)

PkTk.setPackageName('bulicommander')


class BuliCommander(Extension):

    def __init__(self, parent):
        # Default options

        # Always initialise the superclass.
        # This is necessary to create the underlying C++ object
        super().__init__(parent)
        self.parent = parent
        self.__uiController = None
        self.__isKritaVersionOk = checkKritaVersion(*REQUIRED_KRITA_VERSION)

    def __initUiController(self, kritaIsStarting=False):
        """Initialise UI controller

        `kritaIsStarting` set to True if UiController is initialised during Krita's startup,
        otherwise set to False (initialised on first manual execution)
        """
        @pyqtSlot('QString')
        def opened(document):
            # a document has been created: if filename is set, document has been opened
            # also, need to check if uiController is initialized
            # (possible case: document opened before uiController is initialized
            #                 can occurs when BC is opened at startup and user able to open
            #                 a document before/during intiialization)
            if self.__uiController and document.fileName() != '':
                self.__uiController.commandGoLastDocsOpenedAdd(document.fileName())

        @pyqtSlot('QString')
        def saved(fileName):
            # a document has been saved
            if self.__uiController and fileName != '':
                self.__uiController.commandGoLastDocsSavedAdd(fileName)

        if self.__uiController is None:
            try:
                Krita.instance().notifier().imageCreated.disconnect(opened)
            except Exception as e:
                pass

            try:
                Krita.instance().notifier().imageSaved.disconnect(saved)
            except Exception as e:
                pass

            # try:
            #    Krita.instance().notifier().applicationClosing.disconnect()
            # except Exception as e:
            #    pass

            # no controller, create it
            # (otherwise, with Krita 5.0.0, can be triggered more than once time - on each new window)
            Krita.instance().notifier().imageCreated.connect(opened)
            Krita.instance().notifier().imageSaved.connect(saved)

            self.__uiController = BCUIController(PLUGIN_MENU_ENTRY, PLUGIN_VERSION, kritaIsStarting)

    def setup(self):
        """Is executed at Krita's startup"""
        @pyqtSlot()
        def windowCreated():
            # the best place to initialise controller (just after main window is created)
            self.__initUiController(True)

        if not self.__isKritaVersionOk:
            return

        # windowCreated signal has been implemented with krita 5.0.0
        Krita.instance().notifier().windowCreated.connect(windowCreated)

    def createActions(self, window):
        action = window.createAction(EXTENSION_ID, PLUGIN_MENU_ENTRY, "tools/scripts")
        action.triggered.connect(self.start)

        actionSaveAll = window.createAction('pykrita_bulicommander_saveall', i18n('Save All'), "tools/scripts")

    def start(self):
        """Execute Buli Commander controller"""
        # ----------------------------------------------------------------------
        # Create dialog box
        if not self.__isKritaVersionOk:
            QMessageBox.information(QWidget(),
                                    PLUGIN_MENU_ENTRY,
                                    "At least, Krita version {0} is required to use plugin...".format('.'.join([f"{v}" for v in REQUIRED_KRITA_VERSION]))
                                    )
            return

        if self.__uiController is None:
            # with krita 5.0.0, might be created at krita startup
            self.__initUiController(False)
        self.__uiController.start()


if __PLUGIN_EXEC_FROM__ == 'SCRIPTER_PLUGIN':
    sys.stdout = sys.__stdout__

    # Disconnect signals if any before assigning new signals

    bc = BuliCommander(Krita.instance())
    bc.setup()
    bc.start()
