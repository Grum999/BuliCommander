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
# The bcimportanimated module provides classes used to manage import of
# animated images, with options not provided by Krita
#
# Main classes from this module
#
# - BCImportDialogBoxAnimated:
#       A user interface with basics options for file import
#
# - BCImportAnimated
#       Provides methods to process import
#
# -----------------------------------------------------------------------------


from pathlib import Path

import os.path
import sys
import tempfile


import PyQt5.uic
from PyQt5.Qt import *

from PyQt5.QtWidgets import (
        QDialog
    )


from .bcfile import (
        BCFile,
        BCFileManagedFormat
    )

from bulicommander.pktk.modules.utils import Debug
from bulicommander.pktk.modules.ekrita import EKritaNode
from bulicommander.pktk.widgets.wiodialog import WDialogProgress
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )


# ------------------------------------------------------------------------------
class BCImportDialogBoxAnimated(QDialog):

    IMPORT_AS_FRAMELAYER = 0
    IMPORT_AS_STACKLAYER = 1
    IMPORT_AS_FRAME = 2
    IMPORT_AS_KRITA = 3

    def __init__(self, bcfile, panel, parent=None):
        super(BCImportDialogBoxAnimated, self).__init__(parent)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcimportanimated.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__imgNfo = bcfile.getMetaInformation()
        self.__panel = panel

        self.lblFileName.setText(bcfile.fullPathName())
        self.lblFileName.setElide(Qt.ElideLeft)
        self.hsKeyFrameNumber.setMaximum(self.__imgNfo['imageCount'])
        self.sbKeyFrameNumber.setMaximum(self.__imgNfo['imageCount'])
        self.hsKeyFrameNumber.setValue(panel.preview().currentAnimatedFrame())
        self.sbKeyFrameNumber.setValue(panel.preview().currentAnimatedFrame())
        self.hsKeyFrameNumber.valueChanged.connect(self.__currentFrameChanged)

        self.rbImportAsFrameLayer.toggled.connect(self.__setUiEnabled)
        self.rbImportAsLayers.toggled.connect(self.__setUiEnabled)
        self.rbImportSingleFrame.toggled.connect(self.__setUiEnabled)
        self.rbImportKritaDefault.toggled.connect(self.__setUiEnabled)

        self.dbbxOkCancel.accepted.connect(self.accept)
        self.dbbxOkCancel.rejected.connect(self.reject)

        self.__setUiEnabled()

    def __setUiEnabled(self, value=None):
        """Set ui item enabled/disabled according to current user choice"""
        self.hsKeyFrameStep.setEnabled(self.rbImportAsFrameLayer.isChecked())
        self.sbKeyFrameStep.setEnabled(self.rbImportAsFrameLayer.isChecked())

        self.hsKeyFrameNumber.setEnabled(self.rbImportSingleFrame.isChecked())
        self.sbKeyFrameNumber.setEnabled(self.rbImportSingleFrame.isChecked())

    def __currentFrameChanged(self, value):
        self.__panel.preview().setCurrentAnimatedFrame(value)

    def setup(self):
        """Return current selected mode"""
        if self.rbImportAsFrameLayer.isChecked():
            return (BCImportDialogBoxAnimated.IMPORT_AS_FRAMELAYER, self.sbKeyFrameStep.value())
        elif self.rbImportAsLayers.isChecked():
            return (BCImportDialogBoxAnimated.IMPORT_AS_STACKLAYER, None)
        elif self.rbImportSingleFrame.isChecked():
            return (BCImportDialogBoxAnimated.IMPORT_AS_FRAME, self.sbKeyFrameNumber.value())
        elif self.rbImportKritaDefault.isChecked():
            return (BCImportDialogBoxAnimated.IMPORT_AS_KRITA, None)

    @staticmethod
    def open(title, file, panel):
        """Open dialog box"""
        db = BCImportDialogBoxAnimated(file, panel)
        db.setWindowTitle(title)
        returned = db.exec()

        if returned:
            mode = db.setup()
            return (returned, mode[0], mode[1])
        else:
            return (returned, None, None)


class BCImportAnimated(object):
    """Provides function to import animated file files"""

    IMPORT_OK = 0
    IMPORT_KO = 1
    IMPORT_CANCELLED = 2

    SUPPORTED_FORMAT = [BCFileManagedFormat.GIF,
                        BCFileManagedFormat.WEBP]

    @staticmethod
    def importAsLayers(dialogTitle, file):
        """Import animated file

        Each frame is imported in a new layer
        """
        if isinstance(file, str):
            file = BCFile(file)

        if not isinstance(file, BCFile):
            raise EInvalidType('Given `file` must be <str> or <BCFile>')

        if file.format() in BCImportAnimated.SUPPORTED_FORMAT:
            imgNfo = file.getMetaInformation()
            if imgNfo['imageCount'] > 1:
                try:
                    dlgBox = WDialogProgress.display(dialogTitle,
                                                     f"<b>{i18n('Importing file as layers')}</b>"
                                                     f"<br>{i18n('File')}: <span style='font-family:monospace'>{file.fullPathName()}</span><br><br>",
                                                     True,
                                                     minValue=0,
                                                     maxValue=imgNfo['imageCount'])

                    imgReaderAnimated = QMovie(file.fullPathName())

                    document = Krita.instance().createDocument(file.imageSize().width(),
                                                               file.imageSize().height(),
                                                               f'Imported animation-{file.name()}',
                                                               'RGBA',
                                                               'U8',
                                                               '',
                                                               72.00
                                                               )
                    document.setFileName(f'Imported animation-{file.name()}')

                    groupLayer = document.createGroupLayer('Frames')

                    document.rootNode().addChildNode(groupLayer, None)

                    dlgBox.updateMessage(f"{i18n('Extract frames')}...<br>", False)
                    isCancelled = False
                    nbZ = len(f"{imgReaderAnimated.frameCount()}")
                    for frameNumber in range(imgReaderAnimated.frameCount()):
                        isCancelled = dlgBox.setProgress(frameNumber+1)
                        if isCancelled:
                            document.waitForDone()
                            document.close()
                            dlgBox.close()
                            return BCImportAnimated.IMPORT_CANCELLED
                        imgReaderAnimated.jumpToFrame(frameNumber)

                        frameLayer = document.createNode(f"Frame {frameNumber+1:>0{nbZ}}/{imgReaderAnimated.frameCount()} [{imgReaderAnimated.nextFrameDelay()}ms]", "paintLayer")
                        EKritaNode.fromQImage(frameLayer, imgReaderAnimated.currentImage())

                        groupLayer.addChildNode(frameLayer, None)
                        # imgReaderAnimated.jumpToNextFrame()

                    dlgBox.updateMessage(f"{i18n('Frames extracted')}: <i>{imgReaderAnimated.frameCount()}</i><br>", False)
                    dlgBox.setCancelButtonEnabled(False)
                    dlgBox.setInfinite()
                    document.refreshProjection()

                    view = Krita.instance().activeWindow().addView(document)
                    Krita.instance().activeWindow().showView(view)
                    dlgBox.close()
                    return BCImportAnimated.IMPORT_OK
                except Exception as e:
                    Debug.print('[BCImportAnimated.importAsLayers] Unable to read animated file {0}: {1}', file.fullPathName(), e)

        return BCImportAnimated.IMPORT_KO

    @staticmethod
    def importAsFrames(dialogTitle, file, keyFrameStep=1):
        """Import animated file

        Each frame is imported in an animated layer, as a new layer frame
        """
        if isinstance(file, str):
            file = BCFile(file)

        if not isinstance(file, BCFile):
            raise EInvalidType('Given `file` must be <str> or <BCFile>')

        if file.format() in BCImportAnimated.SUPPORTED_FORMAT:
            imgNfo = file.getMetaInformation()
            isOk = False
            if imgNfo['imageCount'] > 1:
                try:
                    dlgBox = WDialogProgress.display(dialogTitle,
                                                     f"<b>{i18n('Importing file as frames')}</b>"
                                                     f"<br>{i18n('File')}: <span style='font-family:monospace'>{file.fullPathName()}</span><br><br>",
                                                     True,
                                                     minValue=0,
                                                     maxValue=imgNfo['imageCount'])

                    imgReaderAnimated = QMovie(file.fullPathName())
                    imgReaderAnimated.setCacheMode(QMovie.CacheAll)

                    document = Krita.instance().createDocument(file.imageSize().width(),
                                                               file.imageSize().height(),
                                                               f'Imported animation-{file.name()}',
                                                               'RGBA',
                                                               'U8',
                                                               '',
                                                               72.00
                                                               )
                    document.setFileName(f'Imported animation-{file.name()}')

                    dlgBox.updateMessage(f"{i18n('Extract frames')}...<br>", False)
                    fileNames = []
                    with tempfile.TemporaryDirectory() as tmpDirName:
                        isCancelled = False
                        nbZ = len(f"{imgReaderAnimated.frameCount()}")
                        for frameNumber in range(imgReaderAnimated.frameCount()):
                            isCancelled = dlgBox.setProgress(frameNumber+1)
                            if isCancelled:
                                document.close()
                                dlgBox.close()
                                return BCImportAnimated.IMPORT_CANCELLED
                            fileName = os.path.join(tmpDirName, f'frame-{frameNumber:>0{nbZ}}.png')

                            imgReaderAnimated.jumpToFrame(frameNumber)
                            img = imgReaderAnimated.currentImage()
                            img.save(fileName)

                            fileNames.append(fileName)

                        dlgBox.updateMessage(f"{i18n('Frames extracted')}: <i>{frameNumber}</i><br>", False)
                        dlgBox.setCancelButtonEnabled(False)
                        dlgBox.setInfinite()
                        dlgBox.updateMessage(f"{i18n('Import frames')}...", False)
                        isOk = document.importAnimation(fileNames, 0, keyFrameStep)
                        document.refreshProjection()

                    if isOk:
                        view = Krita.instance().activeWindow().addView(document)
                        Krita.instance().activeWindow().showView(view)
                        dlgBox.close()
                        return BCImportAnimated.IMPORT_OK

                    dlgBox.close()
                except Exception as e:
                    Debug.print('[BCImportAnimated.importAsFrames] Unable to read animated file {0}: {1}', file.fullPathName(), e)

        return BCImportAnimated.IMPORT_KO

    @staticmethod
    def importInOneLayer(file, frameNumber=1):
        """Import animated file

        Given frame is imported in a layer
        """
        if isinstance(file, str):
            file = BCFile(file)

        if not isinstance(file, BCFile):
            raise EInvalidType('Given `file` must be <str> or <BCFile>')

        if file.format() in BCImportAnimated.SUPPORTED_FORMAT:
            imgNfo = file.getMetaInformation()
            if imgNfo['imageCount'] > 1:
                try:
                    imgReaderAnimated = QMovie(file.fullPathName())
                    imgReaderAnimated.setCacheMode(QMovie.CacheAll)

                    document = Krita.instance().createDocument(file.imageSize().width(),
                                                               file.imageSize().height(),
                                                               f'Imported animation-{file.name()}',
                                                               'RGBA',
                                                               'U8',
                                                               '',
                                                               72.00
                                                               )
                    document.setFileName(f'Imported animation-{file.name()}')

                    imgReaderAnimated.jumpToFrame(0)
                    imgReaderAnimated.currentImage()

                    imgReaderAnimated.jumpToFrame(frameNumber-1)

                    nbZ = len(f"{imgReaderAnimated.frameCount()}")
                    frameLayer = document.createNode(f"Frame {frameNumber:>0{nbZ}}/{imgReaderAnimated.frameCount()}", "paintLayer")
                    EKritaNode.fromQImage(frameLayer, imgReaderAnimated.currentImage())

                    document.rootNode().addChildNode(frameLayer, None)
                    document.refreshProjection()

                    view = Krita.instance().activeWindow().addView(document)
                    Krita.instance().activeWindow().showView(view)
                    return BCImportAnimated.IMPORT_OK
                except Exception as e:
                    Debug.print('[BCImportAnimated.importInOneLayer] Unable to read animated file {0}: {1}', file.fullPathName(), e)

        return BCImportAnimated.IMPORT_KO
