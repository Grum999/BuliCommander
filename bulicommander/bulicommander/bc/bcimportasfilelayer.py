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
# The bcimportasfilelayer module provides classes used to manage import of files
# as file layer
#
# Main classes from this module
#
# - BCImportDialogBoxAsFileLayer:
#       A user interface with options for file import
#
# -----------------------------------------------------------------------------


from pathlib import Path
import xml.etree.ElementTree as xmlElement
import os.path
import sys
import tempfile


import PyQt5.uic
from PyQt5.Qt import *

from PyQt5.QtWidgets import (
        QDialog
    )

from .bcsettings import (
        BCSettings,
        BCSettingsKey
    )

from bulicommander.pktk.modules.utils import Debug
from bulicommander.pktk.modules.ekrita import (
        EKritaResizeMethodsId,
        EKritaResizeMethods
    )
from bulicommander.pktk.widgets.wiodialog import WDialogProgress
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )


# ------------------------------------------------------------------------------
class BCImportDialogBoxAsFileLayer(QDialog):

    def __init__(self, bcfile, applyToAll, parent=None):
        super(BCImportDialogBoxAsFileLayer, self).__init__(parent)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcimportasfilelayer.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__imgNfo = bcfile.getMetaInformation()

        self.lblFileName.setText(bcfile.fullPathName())
        self.lblFileName.setElide(Qt.ElideLeft)

        # init ui
        defaultChoice = BCSettings.get(BCSettingsKey.SESSION_IMPORT_ASFILELAYER_DEFAULTCHOICE)
        self.rbImportScaleNone.setChecked(defaultChoice == 0)
        self.rbImportScaleDocSize.setChecked(defaultChoice == 1)
        self.rbImportScaleDocResolution.setChecked(defaultChoice == 2)

        defaultIndex=0
        for index, methodId in enumerate(EKritaResizeMethods.resizeMethodIdList()):
            self.cbScalingMethod.addItem(EKritaResizeMethods.resizeMethodName(methodId), methodId)
            if methodId == BCSettings.get(BCSettingsKey.SESSION_IMPORT_ASFILELAYER_METHOD):
                defaultIndex = index

        self.rbImportScaleNone.toggled.connect(self.__updateUi)
        self.rbImportScaleDocSize.toggled.connect(self.__updateUi)
        self.rbImportScaleDocResolution.toggled.connect(self.__updateUi)

        self.cbApplyForAll.setVisible(applyToAll)

        self.dbbxOkCancel.accepted.connect(self.__accept)
        self.dbbxOkCancel.rejected.connect(self.reject)

        self.__updateUi()

    def __accept(self):
        """Dialog button "OK" clicked"""
        if BCSettings.get(BCSettingsKey.CONFIG_SESSION_SAVE):
            if self.rbImportScaleNone.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_ASFILELAYER_DEFAULTCHOICE, 0)
            elif self.rbImportScaleDocSize.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_ASFILELAYER_DEFAULTCHOICE, 1)
            elif self.rbImportScaleDocResolution.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_ASFILELAYER_DEFAULTCHOICE, 2)

            BCSettings.set(BCSettingsKey.SESSION_IMPORT_ASFILELAYER_METHOD, self.cbScalingMethod.currentData())

        self.accept()

    def __updateUi(self):
        """update ui item according to current user choice"""
        self.cbScalingMethod.setEnabled(not self.rbImportScaleNone.isChecked())

    def setup(self):
        """Return current selected mode"""
        if self.rbImportScaleNone.isChecked():
            scaleMethod = "None"
        elif self.rbImportScaleDocSize.isChecked():
            scaleMethod = "ToImageSize"
        elif self.rbImportScaleDocResolution.isChecked():
            scaleMethod = "ToImagePPI"

        return (scaleMethod, self.cbScalingMethod.currentData(), self.cbApplyForAll.isChecked())

    @staticmethod
    def open(title, file, applyToAll):
        """Open dialog box"""
        db = BCImportDialogBoxAsFileLayer(file, applyToAll)
        db.setWindowTitle(title)
        returned = db.exec()

        if returned:
            mode = db.setup()
            return (True, mode[0], mode[1], mode[2])
        else:
            return (False, None, None, None)
