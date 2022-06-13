#-----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2022 - Grum999
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
import xml.etree.ElementTree as xmlElement
import gzip
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

from .bcsettings import (
        BCSettings,
        BCSettingsKey
    )

from bulicommander.pktk.modules.utils import Debug
from bulicommander.pktk.modules.imgutils import convertSize
from bulicommander.pktk.modules.ekrita import EKritaNode
from bulicommander.pktk.widgets.wiodialog import WDialogProgress
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )


# ------------------------------------------------------------------------------
class BCImportDialogBoxSvg(QDialog):

    IMPORT_AS_DEFAULT = 0
    IMPORT_AS_ORIGINAL_SIZE = 1
    IMPORT_AS_DEFINED_SIZE = 2
    IMPORT_AS_DEFINED_RESOLUTION = 3

    def __init__(self, bcfile, panel, parent=None):
        super(BCImportDialogBoxSvg, self).__init__(parent)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcimportsvg.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__imgNfo = bcfile.getMetaInformation()

        self.lblFileName.setText(bcfile.fullPathName())
        self.lblFileName.setElide(Qt.ElideLeft)

        # need document unit, default is 'px' if none defined
        self.__unit='px'
        self.rbImportOriginalDocSize.setEnabled(True)
        if 'width.unit' in self.__imgNfo:
            self.__unit=self.__imgNfo['width.unit']
        elif 'height.unit' in self.__imgNfo:
            self.__unit=self.__imgNfo['height.unit']

        # original size only if in pixels
        self.rbImportOriginalDocSize.setEnabled(self.__unit=='px')

        # default original/target sizes
        self.__oSize=None
        self.__tSize=None

        # define original size
        if self.__unit=='px':
            self.__oSize=QSize(int(round(self.__imgNfo['width'], 0)), int(round(self.__imgNfo['height'], 0)))
            self.lblSizeOrig.setText(f"{self.__oSize.width()}x{self.__oSize.height()}{self.__unit}")
        else:
            self.lblSizeOrig.setText(f"{self.__imgNfo['width']:.03f}x{self.__imgNfo['height']:.03f}{self.__unit}")

        # init ui
        defaultChoice=BCSettings.get(BCSettingsKey.SESSION_IMPORT_SVG_DEFAULTCHOICE)
        self.rbImportKritaDefault.setChecked(defaultChoice==0)
        self.rbImportOriginalDocSize.setChecked(defaultChoice==1)
        self.rbImportSetDocSize.setChecked(defaultChoice==2)
        self.rbImportSetDocResolution.setChecked(defaultChoice==3)

        self.rbImportKritaDefault.toggled.connect(self.__updateUi)
        self.rbImportOriginalDocSize.toggled.connect(self.__updateUi)
        self.rbImportSetDocResolution.toggled.connect(self.__updateUi)
        self.rbImportSetDocSize.toggled.connect(self.__updateUi)

        self.cbSetDocSizeRef.addItem(i18n("Width"))
        self.cbSetDocSizeRef.addItem(i18n("Height"))
        self.cbSetDocSizeRef.setCurrentIndex(BCSettings.get(BCSettingsKey.SESSION_IMPORT_SVG_SETSIZE_SELECTED))
        self.hsSetDocSize.setValue(BCSettings.get(BCSettingsKey.SESSION_IMPORT_SVG_SETSIZE_VALUE))
        self.sbSetDocSize.setValue(BCSettings.get(BCSettingsKey.SESSION_IMPORT_SVG_SETSIZE_VALUE))
        self.hsSetDocSize.valueChanged.connect(self.__updateTgtSize)
        self.cbSetDocSizeRef.currentIndexChanged.connect(self.__updateTgtSize)

        self.hsSetDocResolution.setValue(BCSettings.get(BCSettingsKey.SESSION_IMPORT_SVG_SETRESOLUTION_RESOLUTION))
        self.sbSetDocResolution.setValue(BCSettings.get(BCSettingsKey.SESSION_IMPORT_SVG_SETRESOLUTION_RESOLUTION))
        self.hsSetDocResolution.valueChanged.connect(self.__updateTgtSize)

        self.cbIgnoreViewBox.setChecked(BCSettings.get(BCSettingsKey.SESSION_IMPORT_SVG_IGNOREVIEWBOX))
        self.cbIgnoreViewBox.setEnabled('viewBox' in self.__imgNfo)

        self.dbbxOkCancel.accepted.connect(self.__accept)
        self.dbbxOkCancel.rejected.connect(self.reject)

        self.__updateUi()

        if bcfile.format()==BCFileManagedFormat.SVGZ:
            self.rbImportKritaDefault.setEnabled(False)
            if self.rbImportKritaDefault.isChecked():
                self.rbImportSetDocSize.setChecked(True)


    def __accept(self):
        """Dialog button "OK" clicked"""
        if BCSettings.get(BCSettingsKey.CONFIG_SESSION_SAVE):
            if self.rbImportKritaDefault.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_SVG_DEFAULTCHOICE, 0)
            elif self.rbImportOriginalDocSize.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_SVG_DEFAULTCHOICE, 1)
            elif self.rbImportSetDocSize.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_SVG_DEFAULTCHOICE, 2)
            elif self.rbImportSetDocResolution.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_SVG_DEFAULTCHOICE, 3)

            BCSettings.set(BCSettingsKey.SESSION_IMPORT_SVG_SETSIZE_SELECTED, self.cbSetDocSizeRef.currentIndex())
            BCSettings.set(BCSettingsKey.SESSION_IMPORT_SVG_SETSIZE_VALUE, self.hsSetDocSize.value())

            BCSettings.set(BCSettingsKey.SESSION_IMPORT_SVG_SETRESOLUTION_RESOLUTION, self.hsSetDocResolution.value())

            BCSettings.set(BCSettingsKey.SESSION_IMPORT_SVG_IGNOREVIEWBOX, self.cbIgnoreViewBox.isChecked())

        self.accept()


    def __updateUi(self):
        """update ui item according to current user choice"""
        self.cbSetDocSizeRef.setEnabled(self.rbImportSetDocSize.isChecked())
        self.hsSetDocSize.setEnabled(self.rbImportSetDocSize.isChecked())
        self.sbSetDocSize.setEnabled(self.rbImportSetDocSize.isChecked())

        self.hsSetDocResolution.setEnabled(self.rbImportSetDocResolution.isChecked())
        self.sbSetDocResolution.setEnabled(self.rbImportSetDocResolution.isChecked())
        self.cbIgnoreViewBox.setEnabled('viewBox' in self.__imgNfo and not self.rbImportKritaDefault.isChecked())

        self.__updateTgtSize()

    def __updateTgtSize(self):
        """Update target size"""
        if self.rbImportKritaDefault.isChecked():
            self.lblSizeTgt.setText("-")
        elif self.rbImportOriginalDocSize.isChecked():
            self.lblSizeTgt.setText(self.lblSizeOrig.text())
        elif self.rbImportSetDocResolution.isChecked():
            w=int(convertSize(self.__imgNfo['width'], self.__unit, 'px', self.hsSetDocResolution.value(), 0))
            h=int(convertSize(self.__imgNfo['height'], self.__unit, 'px', self.hsSetDocResolution.value(), 0))
            self.__tSize=QSize(w, h)
            self.lblSizeTgt.setText(f"{w}x{h}px")
        elif self.rbImportSetDocSize.isChecked():
            if self.cbSetDocSizeRef.currentIndex()==0:
                # width as reference, calculate height
                w=self.hsSetDocSize.value()
                h=round(w/self.__imgNfo['imageRatio'])
            else:
                # height as reference, calculate width
                h=self.hsSetDocSize.value()
                w=round(h*self.__imgNfo['imageRatio'])
            self.__tSize=QSize(w, h)
            self.lblSizeTgt.setText(f"{w}x{h}px")

    def setup(self):
        """Return current selected mode"""
        defaultResolution=int(Krita.instance().readSetting('', 'preferredVectorImportResolution', "300"))
        if self.rbImportKritaDefault.isChecked():
            return (BCImportDialogBoxSvg.IMPORT_AS_DEFAULT, None, None, None)
        elif self.rbImportOriginalDocSize.isChecked():
            return (BCImportDialogBoxSvg.IMPORT_AS_ORIGINAL_SIZE, self.__oSize, defaultResolution, self.cbIgnoreViewBox.isChecked())
        elif self.rbImportSetDocSize.isChecked():
            return (BCImportDialogBoxSvg.IMPORT_AS_DEFINED_SIZE, self.__tSize, defaultResolution, self.cbIgnoreViewBox.isChecked())
        elif self.rbImportSetDocResolution.isChecked():
            return (BCImportDialogBoxSvg.IMPORT_AS_DEFINED_RESOLUTION, self.__tSize, self.hsSetDocResolution.value(), self.cbIgnoreViewBox.isChecked())

    @staticmethod
    def open(title, file, panel):
        """Open dialog box"""
        db = BCImportDialogBoxSvg(file, panel)
        db.setWindowTitle(title)
        returned = db.exec()

        if returned:
            mode = db.setup()
            return (returned, mode[0], mode[1], mode[2], mode[3])
        else:
            return (returned, None, None, None, None)



class BCImportSvg:
    """Provides function to import SVG files"""

    IMPORT_OK=0
    IMPORT_KO=1
    IMPORT_CANCELLED=2

    SUPPORTED_FORMAT = [BCFileManagedFormat.SVG,
                        BCFileManagedFormat.SVGZ]

    @staticmethod
    def importInOneLayer(file, size, resolution, ignoreViewBox=True):
        """Import SVG file

        Given `file` (BCFile) is imported with provided `size` at given `resolution`
        """
        from io import StringIO
        import xml.etree.ElementTree as ET

        if isinstance(file, str):
            file = BCFile(file)

        if not isinstance(file, BCFile):
            raise EInvalidType('Given `file` must be <str> or <BCFile>')

        if file.format() in BCImportSvg.SUPPORTED_FORMAT:
            imgNfo = file.getMetaInformation()
            try:
                if file.format() == BCFileManagedFormat.SVG:
                    with open(file.fullPathName(), 'r') as fHandle:
                        svgContent=fHandle.read()
                else:
                    with gzip.open(file.fullPathName(), 'rb') as fHandle:
                        svgContent=fHandle.read().decode()

                # parse document as XML
                namespaces = dict([node for _, node in xmlElement.iterparse(StringIO(svgContent), events=['start-ns'])])
                xmlDoc = xmlElement.fromstring(svgContent)

                # update size to expected pixels size
                try:
                    xmlDoc.attrib['width']=f"{size.width()}px"
                    xmlDoc.attrib['height']=f"{size.height()}px"
                except:
                    pass


                # update svgContent from modified XML document
                for namespace in namespaces:
                    if namespace!='svg':
                        ET.register_namespace(namespace, namespaces[namespace])

                svgContent=ET.tostring(xmlDoc, encoding="unicode")

                # create new document
                document=Application.createDocument(size.width(), size.height(), file.baseName(), "RGBA", "U8", "", resolution)
                document.setFileName(file.name())

                # Create vector layer and add it to document
                importedSvgFile=document.createVectorLayer(i18n(f"Imported Layer {file.format()} document"))
                document.rootNode().addChildNode(importedSvgFile, None)

                # add to document to view: need to do it before adding SVG content to vector layer
                # (otherwise Krita crash with Segmentation fault)
                view = Krita.instance().activeWindow().addView(document)

                # add SVG content to vector layer
                importedSvgFile.addShapesFromSvg(svgContent)

                if ignoreViewBox:
                    def convertPtPx(value, resolution):
                        return value * 72/resolution

                    def convertRectPtPx(rect, resolution):
                        return QRectF(
                            convertPtPx(rect.left(), resolution),
                            convertPtPx(rect.top(), resolution),
                            convertPtPx(rect.width(), resolution),
                            convertPtPx(rect.height(), resolution)
                        )

                    # ignore view box
                    # process is little bit complex
                    # maybe a better solution exists :)
                    #
                    # 1: loop over all shape within layer to get real bouding boxes
                    #    compute global bouding box for all shapes
                    #    -> bounding box is returned in Pt
                    #
                    # 2: calculate document size in Pt
                    #
                    # 3: calculate ratio to apply to shape to let them fit in document
                    #    basically, ratio=doc size/shapes size
                    #
                    # 4: calculate transformation matrix
                    #    > scale
                    #    > translation
                    #
                    # 5: loop over shape to apply transformation

                    # 1--
                    sr=QRectF(0,0,0,0)
                    for shape in importedSvgFile.shapes():
                        sr=sr.united(shape.boundingBox())

                    # 2--
                    dr=convertRectPtPx(QRect(0,0,size.width(), size.height()), resolution)

                    # 3--
                    ratio=min(dr.width()/sr.width(), dr.height()/sr.height())

                    # 4--
                    t=QTransform()
                    t.scale(ratio, ratio)
                    t.translate(-sr.left(), -sr.top())

                    # 5--
                    for shape in importedSvgFile.shapes():
                        shape.setTransformation(shape.transformation()*t)
                        shape.update()

                # refresh document and show it
                document.refreshProjection()
                Krita.instance().activeWindow().showView(view)

                return BCImportSvg.IMPORT_OK
            except Exception as e:
                Debug.print('[BCImportSvg.importInOneLayer] Unable to read file {0}: {1}', file.fullPathName(), e)

        return BCImportSvg.IMPORT_KO
