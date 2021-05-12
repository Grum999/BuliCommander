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


from pathlib import Path

import os.path
import sys
import tempfile


import PyQt5.uic
from PyQt5.Qt import *

from PyQt5.QtWidgets import (
        QMessageBox,
        QDialog
    )


from .bcfile import (
        BCFile,
        BCFileManagedFormat
    )

from bulicommander.pktk.modules.utils import Debug
from bulicommander.pktk.modules.ekrita import EKritaNode
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )


# ------------------------------------------------------------------------------
class BCImportDialogBox(QDialog):

    IMPORT_AS_FRAMELAYER = 0
    IMPORT_AS_STACKLAYER = 1
    IMPORT_AS_FRAME = 2
    IMPORT_AS_KRITA = 3

    def __init__(self, bcfile, panel, parent=None):
        super(BCImportDialogBox, self).__init__(parent)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcimportanimated.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__imgNfo = bcfile.getMetaInformation()
        self.__panel = panel

        self.lblFileName.setText(bcfile.fullPathName())
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
            return (BCImportDialogBox.IMPORT_AS_FRAMELAYER, self.sbKeyFrameStep.value())
        elif self.rbImportAsLayers.isChecked():
            return (BCImportDialogBox.IMPORT_AS_STACKLAYER, None)
        elif self.rbImportSingleFrame.isChecked():
            return (BCImportDialogBox.IMPORT_AS_FRAME, self.sbKeyFrameNumber.value())
        elif self.rbImportKritaDefault.isChecked():
            return (BCImportDialogBox.IMPORT_AS_KRITA, None)

    @staticmethod
    def open(title, file, panel):
        """Open dialog box"""
        db = BCImportDialogBox(file, panel)
        db.setWindowTitle(title)
        returned = db.exec()

        if returned:
            mode = db.setup()
            return (returned, mode[0], mode[1])
        else:
            return (returned, None, None)


class BCImportAnimated(object):
    """Provides function to import animated file files"""

    SUPPORTED_FORMAT = [BCFileManagedFormat.GIF,
                        BCFileManagedFormat.WEBP]

    @staticmethod
    def importAsLayers(file):
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
                    imgReaderAnimated = QMovie(file.fullPathName())

                    document = Krita.instance().createDocument (
                            file.imageSize().width(),
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

                    nbZ=len(str(imgReaderAnimated.frameCount()))
                    for frameNumber in range(imgReaderAnimated.frameCount()):
                        imgReaderAnimated.jumpToFrame(frameNumber)

                        frameLayer = document.createNode(f"Frame {frameNumber+1:>0{nbZ}}/{imgReaderAnimated.frameCount()} [{imgReaderAnimated.nextFrameDelay()}ms]", "paintLayer")
                        EKritaNode.fromQImage(frameLayer, imgReaderAnimated.currentImage())

                        groupLayer.addChildNode(frameLayer, None)
                        #imgReaderAnimated.jumpToNextFrame()

                    document.refreshProjection()

                    view = Krita.instance().activeWindow().addView(document)
                    Krita.instance().activeWindow().showView(view)
                    return True
                except Exception as e:
                    Debug.print('[BCImportAnimated.importAsLayers] Unable to read animated file {0}: {1}', file.fullPathName(), e)

        return False

    @staticmethod
    def importAsFrames(file, keyFrameStep=1):
        """Import animated file

        Each frame is imported in an animated layer, as a new layer frame
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

                    document = Krita.instance().createDocument (
                            file.imageSize().width(),
                            file.imageSize().height(),
                            f'Imported animation-{file.name()}',
                            'RGBA',
                            'U8',
                            '',
                            72.00
                        )
                    document.setFileName(f'Imported animation-{file.name()}')

                    fileNames=[]
                    with tempfile.TemporaryDirectory() as tmpDirName:
                        nbZ=len(str(imgReaderAnimated.frameCount()))
                        for frameNumber in range(imgReaderAnimated.frameCount()):
                            fileName = os.path.join(tmpDirName, f'frame-{frameNumber:>0{nbZ}}.png')

                            imgReaderAnimated.jumpToFrame(frameNumber)
                            img = imgReaderAnimated.currentImage()
                            img.save(fileName)

                            fileNames.append(fileName)

                        document.importAnimation(fileNames, 0, keyFrameStep)
                    document.refreshProjection()

                    view = Krita.instance().activeWindow().addView(document)
                    Krita.instance().activeWindow().showView(view)
                    return True
                except Exception as e:
                    Debug.print('[BCImportAnimated.importAsFrames] Unable to read animated file {0}: {1}', file.fullPathName(), e)

        return False

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

                    document = Krita.instance().createDocument (
                            file.imageSize().width(),
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

                    nbZ=len(str(imgReaderAnimated.frameCount()))
                    frameLayer = document.createNode(f"Frame {frameNumber:>0{nbZ}}/{imgReaderAnimated.frameCount()}", "paintLayer")
                    EKritaNode.fromQImage(frameLayer, imgReaderAnimated.currentImage())

                    document.rootNode().addChildNode(frameLayer, None)
                    document.refreshProjection()

                    view = Krita.instance().activeWindow().addView(document)
                    Krita.instance().activeWindow().showView(view)
                    return True
                except Exception as e:
                    Debug.print('[BCImportAnimated.importInOneLayer] Unable to read animated file {0}: {1}', file.fullPathName(), e)

        return False
