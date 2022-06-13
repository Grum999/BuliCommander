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


import zipfile
import tarfile
import os.path
import sys
import tempfile
import re


import PyQt5.uic
from PyQt5.Qt import *

from PyQt5.QtWidgets import (
        QDialog
    )


from .bcfile import (
        BCFile,
        BCFileManagedFormat,
        BCFileProperty,
        BCFileList,
        BCFileListRule,
        BCFileListPath,
        BCFileListSortRule,
        BCFileListRuleOperator,
        BCFileListRuleOperatorType
    )
from .bcwfile import (
        BCFileModel,
        BCViewFilesLv
    )

from .bcsettings import (
        BCSettings,
        BCSettingsKey
    )

from bulicommander.pktk.modules.uncompress import Uncompress
from bulicommander.pktk.modules.utils import Debug
from bulicommander.pktk.modules.imgutils import convertSize
from bulicommander.pktk.modules.ekrita import EKritaNode
from bulicommander.pktk.widgets.wiodialog import WDialogProgress
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )


# ------------------------------------------------------------------------------
class BCImportDialogBoxCbx(QDialog):

    def __init__(self, bcfile, panel, parent=None):
        super(BCImportDialogBoxCbx, self).__init__(parent)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcimportcbx.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__tmpDirectory=tempfile.TemporaryDirectory()

        self.__filesQuery = BCFileList()
        self.__filesQuery.searchSetIncludeDirectories(True)

        self.__filesModelLv=BCFileModel(self.__filesQuery)

        self.lvPageSelection.setModel(self.__filesModelLv)
        self.lvPageSelection.setViewThumbnail(True)
        self.lvPageSelection.setColumnsVisibility([True, False, True, False, False, False, False, True, False, False, True, True, False, False, True, True, False, False, False])
        self.lvPageSelection.setColumnsPosition(  [0,    -1,    1,    -1,    -1,    -1,    -1,    5,    -1,    -1,    6,    2,    -1,    -1,    3,    4,    -1,    -1,    -1   ])
        self.lvPageSelection.setIconSizeIndex(BCSettings.get(BCSettingsKey.SESSION_IMPORT_CBX_PREVIEW_ICONSSIZE))
        #self.lvPageSelection.contextMenuEvent=self.__filesContextMenuEvent
        self.lvPageSelection.selectionModel().selectionChanged.connect(self.__updateUi)


        self.__file=bcfile
        self.__imgNfo = bcfile.getMetaInformation()
        self.__maxSizeDocument=QSize(0, 0)

        self.lbImportCbxFile.setText(self.lbImportCbxFile.text().replace('CBX', bcfile.format().upper()))
        self.lblFileName.setText(bcfile.fullPathName())
        self.lblFileName.setElide(Qt.ElideLeft)

        # init ui
        defaultChoice=BCSettings.get(BCSettingsKey.SESSION_IMPORT_CBX_DEFAULTCHOICE)
        self.rbImportPagesAll.setChecked(defaultChoice==0)
        self.rbImportPagesSelected.setChecked(defaultChoice==1)

        self.rbImportPagesAll.toggled.connect(self.__updateUi)
        self.rbImportPagesSelected.toggled.connect(self.__updateUi)

        self.cbLayerOrder.addItem(i18n("First page on top of layers stack"))
        self.cbLayerOrder.addItem(i18n("First page on bottom of layers stack"))
        self.cbLayerOrder.setCurrentIndex(BCSettings.get(BCSettingsKey.SESSION_IMPORT_CBX_LAYERSORDER))

        self.cbPageAlignment.addItem(i18n("Centered"))
        self.cbPageAlignment.addItem(i18n("Top/Left"))
        self.cbPageAlignment.addItem(i18n("Top/Right"))
        self.cbPageAlignment.addItem(i18n("Middle/Left"))
        self.cbPageAlignment.addItem(i18n("Middle/Reft"))
        self.cbPageAlignment.addItem(i18n("Bottom/Left"))
        self.cbPageAlignment.addItem(i18n("Bottom/Right"))
        self.cbPageAlignment.setCurrentIndex(BCSettings.get(BCSettingsKey.SESSION_IMPORT_CBX_ALIGNMENT))

        self.dbbxOkCancel.accepted.connect(self.__accept)
        self.dbbxOkCancel.rejected.connect(self.reject)

        self.__loadThumbnail()
        self.__updateUi()


    def __loadThumbnail(self):
        """Load Comic Book Thumbnails in listview"""
        # extract files in a temporary directory
        BCImportCbx.extractTo(self.__file, self.__tmpDirectory.name)

        searchRule=BCFileListRule()
        searchRule.setName(BCFileListRuleOperator(re.compile("\.(png|jpg|jpeg)$", re.I), 'match', BCFileListRuleOperatorType.REGEX))

        self.__filesQuery.addSearchRules(searchRule)
        self.__filesQuery.addSearchPaths(BCFileListPath(self.__tmpDirectory.name, True, False, True, False))

        self.__filesQuery.addSortRule([
                BCFileListSortRule(BCFileProperty.PATH, True),
                BCFileListSortRule(BCFileProperty.FILE_NAME, True)
            ])
        self.__filesQuery.searchSetIncludeDirectories(False)
        self.__filesQuery.searchExecute(True, False, [BCFileList.STEPEXECUTED_UPDATERESET])


    def __accept(self):
        """Dialog button "OK" clicked"""
        if BCSettings.get(BCSettingsKey.CONFIG_SESSION_SAVE):
            if self.rbImportPagesAll.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_CBX_DEFAULTCHOICE, 0)
            elif self.rbImportPagesSelected.isChecked():
                BCSettings.set(BCSettingsKey.SESSION_IMPORT_CBX_DEFAULTCHOICE, 1)

            BCSettings.set(BCSettingsKey.SESSION_IMPORT_CBX_PREVIEW_ICONSSIZE, self.lvPageSelection.iconSizeIndex())

            BCSettings.set(BCSettingsKey.SESSION_IMPORT_CBX_LAYERSORDER, self.cbLayerOrder.currentIndex())
            BCSettings.set(BCSettingsKey.SESSION_IMPORT_CBX_ALIGNMENT, self.cbPageAlignment.currentIndex())

        self.accept()


    def __updateUi(self):
        """update ui item according to current user choice"""
        def calculateMaxPageSize(files):
            returned=QSize(0, 0)
            for file in files:
                returned=returned.expandedTo(file.imageSize())
            return returned

        nbTotalPages=self.__filesModelLv.rowCount()
        if self.rbImportPagesAll.isChecked():
            # all pages
            nbPages=nbTotalPages
            self.__maxSizeDocument=calculateMaxPageSize(self.lvPageSelection.files())
        else:
            selectedFiles=self.lvPageSelection.selectedFiles()
            nbPages=len(selectedFiles)
            self.__maxSizeDocument=calculateMaxPageSize(selectedFiles)

        text="<br>".join([i18n(f'Selected pages: {nbPages}/{nbTotalPages}'), i18n(f"Maximum page size: {self.__maxSizeDocument.width()}x{self.__maxSizeDocument.height()}")])
        self.lbPagesInfo.setText(text)

        self.dbbxOkCancel.button(QDialogButtonBox.Ok).setEnabled(nbPages>0)


    def closeEvent(self, event):
        """Dialog is closed, cleanup tmp directory"""
        self.__tmpDirectory.cleanup()


    def setup(self):
        """Return current selected mode"""
        nbCharTmpDirectory=len(self.__tmpDirectory.name)+1
        if self.rbImportPagesAll.isChecked():
            pages=[file.fullPathName()[nbCharTmpDirectory:] for file in self.lvPageSelection.files()]
        else:
            pages=[file.fullPathName()[nbCharTmpDirectory:] for file in self.lvPageSelection.selectedFiles()]

        return (pages, self.__maxSizeDocument, self.cbLayerOrder.currentIndex(), self.cbPageAlignment.currentIndex())

    @staticmethod
    def open(title, file, panel):
        """Open dialog box"""
        db = BCImportDialogBoxCbx(file, panel)
        db.setWindowTitle(title)
        returned = db.exec()

        if returned:
            mode = db.setup()
            return (returned, mode[0], mode[1], mode[2], mode[3])
        else:
            return (returned, None, None, None, None)



class BCImportCbx:
    """Provides function to import CBZ/CBT files"""

    IMPORT_OK=0
    IMPORT_KO=1
    IMPORT_CANCELLED=2

    SUPPORTED_FORMAT = [BCFileManagedFormat.CBZ,
                        BCFileManagedFormat.CBT]

    @staticmethod
    def initialize():
        if Uncompress.FORMAT_RAR in Uncompress.availableFormat():
            BCImportCbx.SUPPORTED_FORMAT.append(BCFileManagedFormat.CBR)

        if Uncompress.FORMAT_7Z in Uncompress.availableFormat():
            BCImportCbx.SUPPORTED_FORMAT.append(BCFileManagedFormat.CB7)


    @staticmethod
    def extractTo(file, targetDirectory):
        """Extrat CBZ/CBT file to target directory"""
        if isinstance(file, str):
            file = BCFile(file)

        if file.format() in BCImportCbx.SUPPORTED_FORMAT:
            if file.format() == BCFileManagedFormat.CBZ:
                try:
                    with zipfile.ZipFile(file.fullPathName(), 'r') as archive:
                        archive.extractall(targetDirectory)
                except Exception as e:
                    # can't be read (not exist, not a zip file?)
                    Debug.print('[BCImportCbx.extractTo] Unable to extract file {0}: {1}', file.fullPathName(), f"{e}")
                    return False
            elif file.format() == BCFileManagedFormat.CBT:
                try:
                    with tarfile.TarFile(file.fullPathName(), 'r') as archive:
                        archive.extractall(targetDirectory)
                except Exception as e:
                    # can't be read (not exist, not a zip file?)
                    Debug.print('[BCImportCbx.extractTo] Unable to extract file {0}: {1}', file.fullPathName(), f"{e}")
                    return False
            elif file.format() in (BCFileManagedFormat.CBR, BCFileManagedFormat.CB7):
                if Uncompress.extractAll(file.fullPathName(), targetDirectory):
                    return True
                else:
                    # can't be read (not exist, not a zip file?)
                    Debug.print('[BCImportCbx.extractTo] Unable to extract file {0}: {1}', file.fullPathName(), f"{e}")
                    return False
            return True
        else:
            return False


    @staticmethod
    def importAsLayers(dialogTitle, file, pages, documentSize, layersOrder, alignment):
        """Import CBZ/CBT file

        Given `pages` is list of filename
        """
        if isinstance(file, str):
            file = BCFile(file)

        if not isinstance(file, BCFile):
            raise EInvalidType('Given `file` must be <str> or <BCFile>')

        if file.format() in BCImportCbx.SUPPORTED_FORMAT:
            imgNfo = file.getMetaInformation()

            dlgBox=WDialogProgress.display(dialogTitle, f"<b>{i18n('Importing file as layers')}</b><br>{i18n('File')}: <span style='font-family:monospace'>{file.fullPathName()}</span><br><br>", True, minValue=0, maxValue=len(pages))

            # create new document
            document=Application.createDocument(documentSize.width(), documentSize.height(), file.baseName(), "RGBA", "U8", "", 300)
            document.rootNode().childNodes()[0].setOpacity(255)

            try:
                nbPages=len(pages)
                with tempfile.TemporaryDirectory() as tmpDirectory:
                    dlgBox.updateMessage(f"{i18n('Extract pages')}...<br>", False)
                    dlgBox.setInfinite()

                    BCImportCbx.extractTo(file, tmpDirectory)

                    isCancelled=False
                    dlgBox.setMaxValue(nbPages)
                    dlgBox.updateMessage(f"{i18n('Import page')}...<br>", False)

                    if layersOrder==0:
                        # first page on bottom
                        # need to reverse list as layers are added on top of stack
                        pages.reverse()

                    for pageNumber, page in enumerate(pages):
                        if isCancelled:
                            document.waitForDone()
                            document.close()
                            dlgBox.close()
                            Timer.sleep(5000)
                            return BCImportCbx.IMPORT_CANCELLED

                        fullPathName=os.path.join(tmpDirectory, page)
                        if os.path.isfile(fullPathName):
                            # Create paint layer and add it to document
                            paintLayer=document.createNode(page, "paintlayer")
                            document.rootNode().addChildNode(paintLayer, None)

                            # force conversion to ARGB32 to ensure QImage is able to be pasted in layer
                            image=QImage(fullPathName).convertToFormat(QImage.Format_ARGB32)

                            positionX=0
                            positionY=0

                            if alignment==0:
                                # Horizontally Centered
                                positionX=(documentSize.width()-image.width())//2
                            elif alignment in (2, 4, 6):
                                # Right aligned
                                positionX=documentSize.width()-image.width()

                            if alignment in (0, 3, 4):
                                # vertically Centered
                                positionY=(documentSize.height()-image.height())//2
                            elif alignment in (5, 6):
                                # Bottom aligned
                                positionY=documentSize.height()-image.height()

                            EKritaNode.fromQImage(paintLayer, image, QPoint(positionX, positionY))


                            if layersOrder==1:
                                # first page at bottom
                                # only first page is visible
                                paintLayer.setVisible(pageNumber==0)
                            else:
                                # first page on top
                                # only first page is visible
                                paintLayer.setVisible(pageNumber==(nbPages-1))

                        isCancelled=dlgBox.setProgress(pageNumber+1)


                document.refreshProjection()

                # add to document to view: need to do it before adding SVG content to vector layer
                # (otherwise Krita crash with Segmentation fault)
                view = Krita.instance().activeWindow().addView(document)
                Krita.instance().activeWindow().showView(view)

                return BCImportCbx.IMPORT_OK
            except Exception as e:
                Debug.print('[BCImportCbx.importAsLayers] Unable to read file {0}: {1}', file.fullPathName(), e)

            dlgBox.close()

        return BCImportCbx.IMPORT_KO


BCImportCbx.initialize()
