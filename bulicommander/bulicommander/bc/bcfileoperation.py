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
from operator import itemgetter, attrgetter
from functools import cmp_to_key

import os
import os.path
import shutil
import sys
import re
import time

import PyQt5.uic
from PyQt5.Qt import *

from PyQt5.QtWidgets import (
        QMessageBox,
        QDialog
    )
from .bcfile import (
        BCFile,
        BCFileList,
        BCFileListPath,
        BCFileManipulateName,
        BCFileManipulateNameLanguageDef,
        BCBaseFile,
        BCDirectory,
        BCFileManagedFormat,
        BCFileThumbnailSize
    )
from .bcsystray import BCSysTray
from .bcwpathbar import BCWPathBar
from .bcutils import (
        Debug,
        bytesSizeToStr,
        strDefault,
        tsToStr
    )
from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# ------------------------------------------------------------------------------
class BCFileOperationUi(object):
    """Open file operation dialog"""

    FILEEXISTS_ASK = 0
    FILEEXISTS_RENAME = 1
    FILEEXISTS_SKIP = 2
    FILEEXISTS_OVERWRITE = 3
    FILEEXISTS_ABORT = 4

    __targetPath = None

    @staticmethod
    def __buildMsg(typeAction, nbFiles, nbDirectories):
        """Return message to display to user"""
        # too lazy to implement/use a i18n() with plural :)
        message = typeAction
        if nbFiles > 0:
            message+=f" {nbFiles} file"
            if nbFiles > 1:
                message+="s"

        if nbDirectories > 0 and nbFiles > 0:
            message+=' and'

        if nbDirectories > 0:
            message+=f" {nbDirectories} director"
            if nbDirectories > 1:
                message+="ies"
            else:
                message+="y"
        return message

    @staticmethod
    def __dialogFileOperation(action, nbFiles, nbDirectories, fileList, message2=None, targetPath=None, message3=None):
        """Initialise default file dialog for delete/copy/move"""
        def pathChanged(value):
            BCFileOperationUi.__targetPath = dlgMain.frameBreacrumbPath.path()

        def showEvent(event):
            """Event trigerred when dialog is shown"""
            if not dlgMain._oldShowEvent is None:
                dlgMain._oldShowEvent()
            # need to set AFTER dialog is visible, otherwise there's a strange bug...
            dlgMain.frameBreacrumbPath.setPath(dlgMain.__targetPath)

        def deepDirAnalysis():
            dlgMain.pbOk.setEnabled(False)
            dlgMain.pbCancel.setEnabled(False)
            dlgMain.pbDeepDirAnalysis.setEnabled(False)

            informations = BCFileOperationUi.buildInformation(fileList, True)

            dlgMain.lblMessage.setText(informations['info']['short'])
            dlgMain.teInfo.setHtml(informations['info']['full'])

            dlgMain.pbDeepDirAnalysis.setVisible(False)

            dlgMain.pbOk.setEnabled(True)
            dlgMain.pbCancel.setEnabled(True)

        informations = BCFileOperationUi.buildInformation(fileList, False)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcfileoperation.ui')
        dlgMain = PyQt5.uic.loadUi(uiFileName)
        dlgMain._oldShowEvent = dlgMain.showEvent

        dlgMain.lblMessage.setText(informations['info']['short'])
        dlgMain.teInfo.setHtml(informations['info']['full'])

        if message2 is None or message2 == '':
            dlgMain.lblMessage2.setVisible(False)
            dlgMain.layout().removeWidget(dlgMain.lblMessage2)
        else:
            dlgMain.lblMessage2.setText(message2)

        if targetPath is None or targetPath == '':
            dlgMain.__targetPath = None
            dlgMain.frameBreacrumbPath.setVisible(False)
            dlgMain.layout().removeWidget(dlgMain.frameBreacrumbPath)
        else:
            dlgMain.frameBreacrumbPath.pathChanged.connect(pathChanged)
            dlgMain.frameBreacrumbPath.setOptions(BCWPathBar.OPTION_SHOW_NONE)
            dlgMain.frameBreacrumbPath.setPath(targetPath)
            BCFileOperationUi.__targetPath = targetPath

        if message3 is None or message3 == '':
            dlgMain.lblMessage3.setVisible(False)
            dlgMain.layout().removeWidget(dlgMain.lblMessage3)
        else:
            dlgMain.lblMessage3.setText(message3)

        if informations['stats']['nbDir'] == 0:
            dlgMain.pbDeepDirAnalysis.setVisible(False)

        dlgMain.pbOk.setText(action)

        dlgMain.pbOk.clicked.connect(dlgMain.accept)
        dlgMain.pbCancel.clicked.connect(dlgMain.reject)
        dlgMain.pbDeepDirAnalysis.clicked.connect(deepDirAnalysis)

        return dlgMain

    @staticmethod
    def __dialogFileExists(action, fileSrc, fileTgt, nbFiles=0):
        """Initialise default file dialog for existing files"""
        def action_rename(dummy):
            dlgMain.__action=BCFileOperationUi.FILEEXISTS_RENAME
            dlgMain.__renamed = dlgMain.cbxNewName.currentText()
            dlgMain.__applyToAll=dlgMain.cbApplyToAll.isChecked()
            dlgMain.accept()

        def action_skip(dummy):
            dlgMain.__action=BCFileOperationUi.FILEEXISTS_SKIP
            dlgMain.__applyToAll=dlgMain.cbApplyToAll.isChecked()
            dlgMain.accept()

        def action_overwrite(dummy):
            dlgMain.__action=BCFileOperationUi.FILEEXISTS_OVERWRITE
            dlgMain.__applyToAll=dlgMain.cbApplyToAll.isChecked()
            dlgMain.accept()

        def action_abort(dummy):
            dlgMain.__action=BCFileOperationUi.FILEEXISTS_ABORT
            dlgMain.reject()

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcfileexists.ui')
        dlgMain = PyQt5.uic.loadUi(uiFileName)

        if isinstance(fileSrc, str):
            if os.path.isfile(fileSrc):
                fileSrc=BCFile(fileSrc)
            elif os.path.isdir(fileSrc):
                fileSrc=BCDirectory(fileSrc)
            else:
                raise EInvalidValue("Given `fileSrc` is not a valid file/directory")
        elif not isinstance(fileSrc, BCBaseFile):
            raise EInvalidValue("Given `fileSrc` is not a valid <str> or <BCBaseFile>")

        if isinstance(fileTgt, str):
            if os.path.isfile(fileTgt):
                fileTgt=BCFile(fileTgt)
            elif os.path.isdir(fileTgt):
                fileTgt=BCDirectory(fileTgt)
            else:
                raise EInvalidValue("Given `fileTgt` is not a valid file/directory")
        elif not isinstance(fileTgt, BCBaseFile):
            raise EInvalidValue("Given `fileTgt` is not a valid <str> or <BCBaseFile>")

        dlgMain.lblActionDesc.setText(f"{action} <font face='monospace'><b>{fileSrc.name()}</b></font> from:")
        dlgMain.lblFileSrc.setText(f"  {fileSrc.path()}")
        dlgMain.lblFileTgt.setText(f"  {fileTgt.path()}")

        if fileSrc.format() == BCFileManagedFormat.DIRECTORY:
            dlgMain.lblMsg.setText("The destination directory already exists")
            iconSrc = fileSrc.icon()
            dlgMain.lblFileSrcNfo.setText(f"<b>Date:</b> {tsToStr(fileSrc.lastModificationDateTime())}")

            dlgMain.btActionOverwrite.setText(i18n("Write into"))
        else:
            dlgMain.lblMsg.setText("The destination file already exists")
            if fileSrc.readable():
                iconSrc = fileSrc.thumbnail(BCFileThumbnailSize.HUGE, BCBaseFile.THUMBTYPE_ICON)
                dlgMain.lblFileSrcNfo.setText(f"<b>Date:</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{tsToStr(fileSrc.lastModificationDateTime())}<br>"
                                              f"<b>Size:</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{bytesSizeToStr(fileSrc.size())} ({fileSrc.size():n})<br>"
                                              f"<b>Image size:</b>&nbsp;{fileSrc.imageSize().width()}x{fileSrc.imageSize().height()}")
            else:
                iconSrc = fileSrc.icon()
                dlgMain.lblFileSrcNfo.setText(f"<b>Date:</b> {tsToStr(fileSrc.lastModificationDateTime())}<br>"
                                              f"<b>Size:</b> {bytesSizeToStr(fileSrc.size())} ({fileSrc.size():n})")

        if fileTgt.format() == BCFileManagedFormat.DIRECTORY:
            iconTgt = fileTgt.icon()
            dlgMain.lblFileTgtNfo.setText(f"<b>Date:</b> {tsToStr(fileTgt.lastModificationDateTime())}")
        else:
            if fileTgt.readable():
                iconTgt = fileTgt.thumbnail(BCFileThumbnailSize.HUGE, BCBaseFile.THUMBTYPE_ICON)
                dlgMain.lblFileTgtNfo.setText(f"<b>Date:</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{tsToStr(fileTgt.lastModificationDateTime())}<br>"
                                              f"<b>Size:</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{bytesSizeToStr(fileTgt.size())} ({fileTgt.size():n})<br>"
                                              f"<b>Image size:</b>&nbsp;{fileTgt.imageSize().width()}x{fileTgt.imageSize().height()}")
            else:
                iconTgt = fileTgt.icon()
                dlgMain.lblFileTgtNfo.setText(f"<b>Date:</b> {tsToStr(fileTgt.lastModificationDateTime())}<br>"
                                              f"<b>Size:</b> {bytesSizeToStr(fileTgt.size())} ({fileTgt.size():n})")

        dlgMain.lblFileSrcImg.setPixmap(iconSrc.pixmap(BCFileThumbnailSize.HUGE.value, BCFileThumbnailSize.HUGE.value))
        dlgMain.lblFileTgtImg.setPixmap(iconTgt.pixmap(BCFileThumbnailSize.HUGE.value, BCFileThumbnailSize.HUGE.value))

        dlgMain.cbxNewName.addItems([
                '{file:baseName}_{counter:####}.{file:ext}',
                '{file:baseName}_{date}-{time}.{file:ext}',
                i18n('{file:baseName}-Copy {counter:####}.{file:ext}'),
                i18n('{file:baseName}-Copy {date}_{time}.{file:ext}')
            ])
        dlgMain.cbxNewName.setCurrentText(fileSrc.name())

        dlgMain.btActionRename.clicked.connect(action_rename)
        dlgMain.btActionSkip.clicked.connect(action_skip)
        dlgMain.btActionOverwrite.clicked.connect(action_overwrite)
        dlgMain.btActionAbort.clicked.connect(action_abort)

        dlgMain.__action = None
        dlgMain.__renamed = fileSrc.name()
        dlgMain.__applyToAll = False

        dlgMain.action = lambda: dlgMain.__action
        dlgMain.renamed = lambda: dlgMain.__renamed
        dlgMain.applyToAll = lambda: dlgMain.__applyToAll

        dlgMain.cbApplyToAll.setVisible(nbFiles>1)

        return dlgMain

    @staticmethod
    def __dialogFileRenameSingle(fileList):
        """Initialise default file dialog for single file rename"""
        def pathChanged(value):
            dlgMain.buttonBox.button(QDialogButtonBox.Ok).setEnabled( not (value.strip() == '' or value.strip() == sourceFileName) )

        def returnedValue():
            return {
                    'files': [fileList[0]],
                    'rule': dlgMain.leNewFileName.text()
                }

        if fileList[0].format()==BCFileManagedFormat.DIRECTORY:
            label=i18n('directory')
        else:
            label=i18n('file')

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcrenamefile_single.ui')
        dlgMain = PyQt5.uic.loadUi(uiFileName)

        sourceFileName=fileList[0].name()

        dlgMain.leCurrentPathFileName.setText(fileList[0].fullPathName())
        dlgMain.leNewFileName.setText(sourceFileName)
        dlgMain.leNewFileName.textChanged.connect(pathChanged)

        dlgMain.lblCurrentName.setText(i18n(f'Current {label} name'))
        dlgMain.lblNewName.setText(i18n(f'New {label} name'))

        dlgMain.buttonBox.accepted.connect(dlgMain.accept)
        dlgMain.buttonBox.rejected.connect(dlgMain.reject)
        dlgMain.returnedValue=returnedValue

        pathChanged(sourceFileName)

        return dlgMain

    @staticmethod
    def __dialogFileRenameMulti(fileList):
        """Initialise default file dialog for multiple file rename"""
        FILEDATA = Qt.UserRole + 1

        def patternChanged():
            newFileName=BCFileManipulateName.calculateFileName(fileList[0], dlgMain.cePattern.toPlainText())
            if not newFileName[1] is None:
                # error
                dlgMain.lblError.setText(newFileName[1])
                dlgMain.lblError.setVisible(True)
            elif dlgMain.cePattern.toPlainText()==defaultPattern:
                # error...
                dlgMain.lblError.setText(i18n(f"Note: can't rename {labelPlural} when source name is identical to target name"))
                dlgMain.lblError.setVisible(True)
            else:
                dlgMain.lblError.setText('')
                dlgMain.lblError.setVisible(False)
            updateFilesFromListView()
            updateNbFilesLabelAndBtnOk()

        def showPathChanged(value):
            header.setSectionHidden(0, (not value))

        def getNewFileName(file):
            newFileName=BCFileManipulateName.calculateFileName(file, dlgMain.cePattern.toPlainText())
            if not newFileName[1] is None:
                # error
                return i18n('Invalid renaming pattern')
            else:
                return newFileName[0]

        def returnedValue():
            returned=[]

            if dlgMain.cbExcludeSelected.isChecked():
                for row in range(model.rowCount()):
                    item=model.item(row, 1)
                    if not dlgMain.tvResultPreview.selectionModel().isSelected(item.index()):
                        returned.append(item.data(FILEDATA))
            else:
                returned=fileList

            return {
                    'files': returned,
                    'rule': dlgMain.cePattern.toPlainText()
                }

        def addFileToListView(file):
            newRow = [
                    QStandardItem(''),
                    QStandardItem(''),
                    QStandardItem('')
                ]

            newRow[0].setText(file.path())
            newRow[1].setText(file.name())
            newRow[1].setData(file, FILEDATA)
            newRow[2].setText(getNewFileName(file))

            model.appendRow(newRow)

        def updateFilesFromListView():
            for row in range(model.rowCount()):
                item=model.item(row, 2)
                item.setText(getNewFileName(model.item(row, 1).data(FILEDATA)))

            dlgMain.tvResultPreview.resizeColumnToContents(2)

        def updateNbFilesLabelAndBtnOk(dummy=None):
            toProcess=nbFiles
            textExcluded=''
            nbExcluded=0
            if dlgMain.cbExcludeSelected.isChecked():
                nbExcluded=len(dlgMain.tvResultPreview.selectionModel().selectedRows())
                toProcess-=nbExcluded
                textExcluded=i18n(f', {nbExcluded} excluded')

            text=i18n(f'{toProcess} to rename')+textExcluded

            dlgMain.buttonBox.button(QDialogButtonBox.Ok).setEnabled((toProcess>0) and not dlgMain.lblError.isVisible())

            dlgMain.lblNbFiles.setText(text)

        def selectionChanged(selected=None, deselected=None):
            if dlgMain.cbExcludeSelected.isChecked():
                updateNbFilesLabelAndBtnOk()


        nbFiles = 0

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcrenamefile_multi.ui')
        dlgMain = PyQt5.uic.loadUi(uiFileName)

        if fileList[0].format()==BCFileManagedFormat.DIRECTORY:
            label=i18n('directory')
            labelPlural=i18n('directories')
            defaultPattern='{file:baseName}'
        else:
            label=i18n('file')
            labelPlural=i18n('files')
            defaultPattern='{file:baseName}.{file:ext}'

        dlgMain.cePattern.setPlainText(defaultPattern)
        dlgMain.cePattern.textChanged.connect(patternChanged)
        dlgMain.cePattern.setLanguageDefinition(BCFileManipulateNameLanguageDef())
        dlgMain.cePattern.setOptionMultiLine(False)
        dlgMain.cePattern.setOptionShowLineNumber(False)
        dlgMain.cePattern.setOptionShowIndentLevel(False)
        dlgMain.cePattern.setOptionShowRightLimit(False)
        dlgMain.cePattern.setOptionShowSpaces(False)
        dlgMain.cePattern.setOptionAllowWheelSetFontSize(False)
        dlgMain.cePattern.setShortCut(Qt.Key_Tab, False, None) # disable indent
        dlgMain.cePattern.setShortCut(Qt.Key_Backtab, False, None) # disable dedent
        dlgMain.cePattern.setShortCut(Qt.Key_Slash, True, None) # disable toggle comment
        dlgMain.cePattern.setShortCut(Qt.Key_Return, False, None) # disable autoindent

        dlgMain.cbShowPath.toggled.connect(showPathChanged)

        dlgMain.lblError.setVisible(False)

        model = QStandardItemModel(0, 3, dlgMain)
        model.setHeaderData(0, Qt.Horizontal, i18n("Path"))
        model.setHeaderData(1, Qt.Horizontal, i18n(f"Source {label} name"))
        model.setHeaderData(2, Qt.Horizontal, i18n(f"Renamed {label} name"))

        dlgMain.tvResultPreview.setModel(model)

        header = dlgMain.tvResultPreview.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)

        for file in fileList:
            if not file.format() == BCFileManagedFormat.MISSING:
                addFileToListView(file)
                nbFiles+=1

        updateNbFilesLabelAndBtnOk()

        dlgMain.tvResultPreview.resizeColumnToContents(0)
        dlgMain.tvResultPreview.resizeColumnToContents(1)
        dlgMain.tvResultPreview.resizeColumnToContents(2)

        header.setSectionHidden(0, True)

        dlgMain.cbExcludeSelected.setText(i18n(f'Exclude selected {labelPlural}'))

        dlgMain.cbExcludeSelected.toggled.connect(updateNbFilesLabelAndBtnOk)
        dlgMain.tvResultPreview.selectionModel().selectionChanged.connect(updateNbFilesLabelAndBtnOk)

        dlgMain.buttonBox.accepted.connect(dlgMain.accept)
        dlgMain.buttonBox.rejected.connect(dlgMain.reject)
        dlgMain.returnedValue=returnedValue

        return dlgMain

    @staticmethod
    def buildInformation(fileList, full=False):
        """Build text information from given list of BCBaseFile"""
        QApplication.setOverrideCursor(Qt.WaitCursor)

        fullNfo = []
        files = sorted(fileList, key=cmp_to_key(BCBaseFile.fullPathNameCmpAsc))

        statFiles={
                'nbKra': 0,
                'nbOther': 0,
                'sizeKra': 0,
                'sizeOther': 0,
                'nbDir': 0
            }

        # ----------------------------------------------------------------------
        # Display total number of file (+size) including sub-directories
        # Improve BCFileList class to generate statistics ready-to-use about returned results (number of directories, nb files+size, nb non kra file+size)
        for file in files:
            if file.format() == BCFileManagedFormat.DIRECTORY:
                fullNfo.append(f"<img width=16 height=16 src=':/images/folder_open'/>&nbsp;{file.fullPathName()}")
                if full:
                    # build informations about directory content
                    pathFileList=BCFileList()
                    pathFileList.addPath(BCFileListPath(file.fullPathName(), True))
                    pathFileList.setIncludeDirectories(True)
                    pathFileList.execute(buildStats=True, strict=False) # strict should be an option?

                    stats = pathFileList.stats()
                    for key in stats:
                        statFiles[key]+=stats[key]

                    if stats['nbKra'] > 0 or stats['nbOther'] > 0 or stats['nbDir'] > 0:
                        nfo=["""<span style=" font-family:'monospace'; font-size:8pt; font-style:italic;">&nbsp;&nbsp;&gt; Directory contains:</span>"""]
                        if stats['nbDir'] > 0:
                            nfo.append(f"""<span style="margin-left: 40px; font-family:'monospace'; font-size:8pt; font-style:italic;">&nbsp;&nbsp;&nbsp;&nbsp;. Sub-directories: {stats['nbDir']}</span>""" )
                        if stats['nbKra'] > 0:
                            nfo.append(f"""<span style="margin-left: 40px; font-family:'monospace'; font-size:8pt; font-style:italic;">&nbsp;&nbsp;&nbsp;&nbsp;. Image files: {stats['nbKra']} ({bytesSizeToStr(stats['sizeKra'])})</span>""" )
                        if stats['nbOther'] > 0:
                            nfo.append(f"""<span style="margin-left: 40px; font-family:'monospace'; font-size:8pt; font-style:italic;">&nbsp;&nbsp;&nbsp;&nbsp;. Other files: {stats['nbOther']} ({bytesSizeToStr(stats['sizeOther'])})</span>""" )

                        fullNfo.append("<br/>".join(nfo))
                statFiles['nbDir']+=1
            elif file.format() == BCFileManagedFormat.UNKNOWN:
                fullNfo.append(f"<img width=16 height=16 src=':/images/file'/>&nbsp;{file.fullPathName()}")
                statFiles['nbOther']+=1
                statFiles['sizeOther']+=file.size()
            else:
                fullNfo.append(f"<img width=16 height=16 src=':/images/large_view'/>&nbsp;{file.fullPathName()}")
                statFiles['nbKra']+=1
                statFiles['sizeKra']+=file.size()


        shortNfo = []
        if statFiles['nbDir'] > 0:
            shortNfo.append(f"Directories: {statFiles['nbDir']}")
        if statFiles['nbKra'] > 0:
            shortNfo.append(f"Image files: {statFiles['nbKra']} ({bytesSizeToStr(statFiles['sizeKra'])})")
        if statFiles['nbOther'] > 0:
            shortNfo.append(f"Other files: {statFiles['nbOther']} ({bytesSizeToStr(statFiles['sizeOther'])})" )

        QApplication.restoreOverrideCursor()

        return {
                'stats': statFiles,
                'info': {
                        'full': "<br>".join(fullNfo),
                        'short': ", ".join(shortNfo)
                    }
            }

    @staticmethod
    def path():
        """Return path"""
        return BCFileOperationUi.__targetPath

    @staticmethod
    def delete(title, nbFiles, nbDirectories, fileList):
        """Open dialog box"""
        db = BCFileOperationUi.__dialogFileOperation('Delete', nbFiles, nbDirectories, fileList)
        db.setWindowTitle(f"{title}::Delete files")
        return db.exec()

    @staticmethod
    def copy(title, nbFiles, nbDirectories, fileList, targetPath):
        """Open dialog box"""
        db = BCFileOperationUi.__dialogFileOperation('Copy', nbFiles, nbDirectories, fileList, "To", targetPath)
        db.setWindowTitle(f"{title}::Copy files")
        return db.exec()

    @staticmethod
    def move(title, nbFiles, nbDirectories, fileList, targetPath):
        """Open dialog box"""
        db = BCFileOperationUi.__dialogFileOperation('Move', nbFiles, nbDirectories, fileList, "To", targetPath)
        db.setWindowTitle(f"{title}::Move files")
        return db.exec()

    @staticmethod
    def createDir(title, targetPath):
        """Open dialog box to create a new directory"""
        value, ok = QInputDialog.getText(QWidget(), f"{title}::Create directory", f"Create a new directory into\n{targetPath}", QLineEdit.Normal,"New directory")
        if ok and value != '':
            return os.path.join(targetPath, value)
        return None

    @staticmethod
    def rename(title, fileList):
        """Open dialog box to rename file

        If there's only one file to rename, open 'single' rename dialog box
        Otherwise open 'multi' rename dialog box

        Return None if user cancel action
        Otherwise return a dictionary
        {
            'files': BCFile List,
            'rule': rule to rename file
        }
        """
        if len(fileList) == 0:
            return None
        elif len(fileList) == 1:
            if fileList[0].format()==BCFileManagedFormat.DIRECTORY:
                label=i18n('directory')
            else:
                label=i18n('file')
            db = BCFileOperationUi.__dialogFileRenameSingle(fileList)
            db.setWindowTitle(i18n(f"{title}::Rename {label}"))
            if db.exec():
                return db.returnedValue()
        else:
            if fileList[0].format()==BCFileManagedFormat.DIRECTORY:
                label=i18n('directories')
            else:
                label=i18n('files')
            db = BCFileOperationUi.__dialogFileRenameMulti(fileList)
            db.setWindowTitle(i18n(f"{title}::Rename {label}"))
            if db.exec():
                return db.returnedValue()

        return None

    @staticmethod
    def fileExists(title, action, fileSrc, fileTgt, nbFiles=0):
        """Open dialog box to ask action on existing file"""
        db = BCFileOperationUi.__dialogFileExists(action, fileSrc, fileTgt, nbFiles)
        db.setWindowTitle(f"{title}::{action} files")
        returned = db.exec()
        if returned:
            return (db.action(), db.renamed(), db.applyToAll())
        else:
            return (db.action(), '', False)


class BCFileOperation(object):

    __PROGRESS = None
    __PROGRESS_currentStep = 0
    __PROGRESS_currentBytes = 0
    __PROGRESS_totalBytes = 0
    __PROGRESS_totalBytesStr = "0B"
    __PROGRESS_cancelled = False

    @staticmethod
    def __showProgressBar(title, nbFiles, nbBytes):
        """Show progress dialog bar"""
        def cancel_clicked():
            BCFileOperation.__PROGRESS_cancelled = True
            BCFileOperation.__PROGRESS.bbCancel.setEnabled(False)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcfileprogress.ui')

        BCFileOperation.__PROGRESS = PyQt5.uic.loadUi(uiFileName)
        BCFileOperation.__PROGRESS.setWindowTitle(title)
        BCFileOperation.__PROGRESS.setModal(True)
        BCFileOperation.__PROGRESS.show()

        BCFileOperation.__PROGRESS_cancelled = False
        BCFileOperation.__PROGRESS_currentStep = 0
        BCFileOperation.__PROGRESS_currentBytes = 0
        BCFileOperation.__PROGRESS_totalFiles = nbFiles
        BCFileOperation.__PROGRESS_totalBytes = nbBytes
        BCFileOperation.__PROGRESS_totalBytesStr = bytesSizeToStr(nbBytes)

        BCFileOperation.__PROGRESS.lblCurrentFile.setText('')
        BCFileOperation.__PROGRESS.lblProcessedFiles.setText(f'0/{BCFileOperation.__PROGRESS_totalFiles}')
        BCFileOperation.__PROGRESS.pbProcessedFiles.setValue(0)
        BCFileOperation.__PROGRESS.pbProcessedFiles.setMaximum(BCFileOperation.__PROGRESS_totalFiles)

        BCFileOperation.__PROGRESS.lblProcessedBytes.setText(f'0B/{BCFileOperation.__PROGRESS_totalBytesStr}')
        BCFileOperation.__PROGRESS.pbProcessedBytes.setValue(0)
        BCFileOperation.__PROGRESS.pbProcessedBytes.setMaximum(10000)

        BCFileOperation.__PROGRESS.bbCancel.clicked.connect(cancel_clicked)

    @staticmethod
    def __hideProgressBar():
        """Hide progress dialog bar"""
        BCFileOperation.__PROGRESS.accept()
        BCFileOperation.__PROGRESS = None

    @staticmethod
    def __progressBarNext(fileName, fileSize):
        """Update progress bar"""
        if not BCFileOperation.__PROGRESS is None:
            BCFileOperation.__PROGRESS_currentStep+=1
            BCFileOperation.__PROGRESS_currentBytes+=fileSize

            if BCFileOperation.__PROGRESS_totalBytes>0:
                nbBytes = 10000*BCFileOperation.__PROGRESS_currentBytes/BCFileOperation.__PROGRESS_totalBytes
            else:
                nbBytes = 0

            BCFileOperation.__PROGRESS.lblCurrentFile.setText(fileName)
            BCFileOperation.__PROGRESS.lblProcessedFiles.setText(f'{BCFileOperation.__PROGRESS_currentStep}/{BCFileOperation.__PROGRESS_totalFiles}')
            BCFileOperation.__PROGRESS.lblProcessedBytes.setText(f'{bytesSizeToStr(BCFileOperation.__PROGRESS_currentBytes)}/{BCFileOperation.__PROGRESS_totalBytesStr}')

            BCFileOperation.__PROGRESS.pbProcessedFiles.setValue(BCFileOperation.__PROGRESS_currentStep)
            BCFileOperation.__PROGRESS.pbProcessedBytes.setValue(nbBytes)
            QApplication.instance().processEvents()

    @staticmethod
    def __isCancelled():
        """Return true if 'cancel' button has been clicked"""
        return BCFileOperation.__PROGRESS_cancelled

    @staticmethod
    def __value():
        """Current value"""
        return BCFileOperation.__PROGRESS_currentStep

    @staticmethod
    def __copyOrMove(title, srcFiles, targetPath, mode):
        """Copy or move files, according to given mode 'copy' or 'move'

        Given `srcFiles` is a list of BCBaseFile

        The copy/move method is practically the same so use the same function as
        algorithm to manage automatic renaming is little bit complex
        """
        QApplication.setOverrideCursor(Qt.WaitCursor)

        # According to mode, define terms to use for user information
        if mode=='copy':
            modeMaj=i18n('Copy')
            modeEd=i18n('copied')
        else:
            modeMaj=i18n('Move')
            modeEd=i18n('moved')

        # define default action to apply if file/path already exists
        # note: for RENAME, it will always stay to FILEEXISTS_ASK (control is made
        #       on newFilePattern/newDirPattern content)
        actionOnFileExist = BCFileOperationUi.FILEEXISTS_ASK
        actionOnPathExist = BCFileOperationUi.FILEEXISTS_ASK

        # pattern to apply for automatic RENAME action
        newFilePattern=None
        newDirPattern=None

        # number of processed/error file
        processed=None
        inError=0

        # initialise process:
        # - calculate total size to copy/move (in bytes)
        # - determinate target path for file/dir to process
        files=[]
        index=0
        totalSize=0
        pathsList={}
        for file in srcFiles:
            if file.format() != BCFileManagedFormat.DIRECTORY:
                totalSize+=file.size()
            else:
                pathsList[file.fullPathName()]=file.name()
            file.setTag('newPath', targetPath)
            files.append(file)
            index+=1

        if len(pathsList)>0:
            # there's some directory to process
            # in this case, search all sub-directories & files and continue to feed list of items to process
            for srcPath in pathsList:
                fileList=BCFileList()
                fileList.addPath(BCFileListPath(srcPath, True))
                fileList.setIncludeDirectories(True)
                fileList.execute()
                srcPath = os.path.dirname(srcPath)
                for file in fileList.files():
                    file.setTag('newPath', os.path.join(targetPath, file.path().replace(srcPath, '').strip(os.sep)))
                    files.append(file)
                    totalSize+=file.size()

        # ascending sort
        files = sorted(files, key=cmp_to_key(BCBaseFile.fullPathNameCmpAsc))
        # path list, descending sort
        paths = sorted([file for file in files if file.format()==BCFileManagedFormat.DIRECTORY], key=cmp_to_key(BCBaseFile.fullPathNameCmpDesc))

        QApplication.restoreOverrideCursor()
        QApplication.setOverrideCursor(Qt.BusyCursor)
        BCFileOperation.__showProgressBar(i18n(f"{title}::{modeMaj} files"), len(files), totalSize)

        for file in files:
            isDir=False
            if file.format() == BCFileManagedFormat.DIRECTORY:
                BCFileOperation.__progressBarNext(file.fullPathName(), 0)
                isDir=True
            else:
                BCFileOperation.__progressBarNext(file.fullPathName(), file.size())

            # determinate new target full path name
            targetFile = os.path.join(file.tag('newPath'), file.name())

            actionToApply = BCFileOperationUi.FILEEXISTS_OVERWRITE

            while os.path.exists(targetFile):
                # the target file already exists..

                if isDir and not newDirPattern is None:
                    # current directory exist AND a rename pattern exist for directories
                    # => means that we try to rename directory automatically
                    currentTarget = targetFile
                    targetFile = os.path.join(file.tag('newPath'), BCFileManipulateName.parseFileNameKw(BCDirectory(targetFile), newDirPattern))

                    if not os.path.exists(targetFile):
                        # ok new name is valid, doesn't exist
                        # need to modify all file designed to be processed into the new directory
                        for fileToUpdate in files:
                            if (currentTarget + os.sep) in fileToUpdate.tag('newPath'):
                                fileToUpdate.setTag('newPath', fileToUpdate.tag('newPath').replace(currentTarget, targetFile))

                    if not os.path.exists(targetFile):
                        # ok new name is valid, doesn't exist
                        # need to modify all file designed to be processed into the new directory
                        for fileToUpdate in files:
                            if fileToUpdate.tag('newPath') == currentTarget:
                                fileToUpdate.setTag('newPath', targetFile)
                        break
                elif not isDir and not newFilePattern is None:
                    # current directory exist AND a rename pattern exist for files
                    # => means that we try to rename file automatically
                    targetFile = os.path.join(file.tag('newPath'), BCFileManipulateName.parseFileNameKw(BCFile(targetFile), newFilePattern))

                    if not os.path.exists(targetFile):
                        # ok new name is valid, doesn't exist
                        break

                if (not isDir and actionOnFileExist == BCFileOperationUi.FILEEXISTS_ASK) or (isDir and actionOnPathExist == BCFileOperationUi.FILEEXISTS_ASK):
                    # ask for user what to do...
                    QApplication.restoreOverrideCursor()
                    action = BCFileOperationUi.fileExists(title, modeMaj, file, targetFile, len(files))
                    QApplication.setOverrideCursor(Qt.BusyCursor)

                    if action[0] == BCFileOperationUi.FILEEXISTS_ABORT:
                        # exit immediately
                        actionToApply = BCFileOperationUi.FILEEXISTS_ABORT
                        # minus one because progress bar is already on next item while item has not yet been processed
                        processed=BCFileOperation.__value() - 1
                        break
                    elif action[0] == BCFileOperationUi.FILEEXISTS_RENAME:
                        # rename file
                        currentTarget = targetFile
                        if isDir:
                            targetFile = os.path.join(os.path.dirname(targetFile), BCFileManipulateName.parseFileNameKw(BCDirectory(targetFile), re.sub("(?i)\{file:(?:path|name)\}", '', action[1])))
                        else:
                            targetFile = os.path.join(os.path.dirname(targetFile), BCFileManipulateName.parseFileNameKw(BCFile(targetFile), re.sub("(?i)\{file:(?:path|name)\}", '', action[1])))
                        actionToApply = BCFileOperationUi.FILEEXISTS_RENAME

                        if isDir and not os.path.exists(targetFile):
                            # need to modify all file designed to be processed into the new directory
                            # do it only if new target not exists
                            for fileToUpdate in files:
                                if (currentTarget + os.sep) in fileToUpdate.tag('newPath'):
                                    fileToUpdate.setTag('newPath', fileToUpdate.tag('newPath').replace(currentTarget, targetFile))

                        # apply to all
                        if action[2]:
                            if isDir:
                                newDirPattern = re.sub("(?i)\{file:(?:path|name)\}", '', action[1])
                            else:
                                newFilePattern = re.sub("(?i)\{file:(?:path|name)\}", '', action[1])

                        # note: to do break loop
                        #       if new defined target file already exists, user will be asked again to change file name
                    else:
                        # apply to all
                        if action[2]:
                            if isDir:
                                actionOnPathExist = action[0]
                            else:
                                actionOnFileExist = action[0]
                        actionToApply = action[0]
                        break
                else:
                    if isDir:
                        actionToApply = actionOnPathExist
                    else:
                        actionToApply = actionOnFileExist
                    break

            if actionToApply == BCFileOperationUi.FILEEXISTS_ABORT:
                # minus one because progress bar is already on next item while item has not yet been processed
                processed=BCFileOperation.__value() - 1
                break
            elif actionToApply == BCFileOperationUi.FILEEXISTS_SKIP:
                continue
            elif isDir:
                try:
                    os.makedirs(targetFile, exist_ok=True)
                except Exception as e:
                    inError+=1
                    Debug.print('[BCFileOperation.__copyOrMove] Unable to {3} file from {0} to {1}: {2}', file.fullPathName(), targetFile, str(e), mode)
            elif not isDir:
                try:
                    targetPath = os.path.dirname(targetFile)
                    os.makedirs(targetPath, exist_ok=True)

                    if mode == 'copy':
                        shutil.copy2(file.fullPathName(), targetFile)
                    else:
                        shutil.move(file.fullPathName(), targetFile)
                except Exception as e:
                    inError+=1
                    Debug.print('[BCFileOperation.__copyOrMove] Unable to {3} file from {0} to {1}: {2}', file.fullPathName(), targetFile, str(e), mode)

            if BCFileOperation.__isCancelled():
                break

        if processed is None:
            processed=BCFileOperation.__value()

        if mode == 'move':
            # at this point, all file are normally moved (except if user have processed action or if
            # error occured on a file)
            # Directories are still present and need to be deleted too
            # note: works on path list with a descending sort allows to check/delete deepest directories first
            #           /home/xxx/temp/dir_to_delete_a/dir_to_delete_b/dir_to_delete_c              first deleted
            #           /home/xxx/temp/dir_to_delete_a/dir_to_delete_b                              and then deleted
            #           /home/xxx/temp/dir_to_delete_a                                              and then deleted
            for path in paths:
                if os.path.isdir(path.fullPathName()) and os.path.isdir(path.tag('newPath')):
                    # source directory still here AND target directory exists
                    if len(os.listdir(path.fullPathName())) == 0:
                        # source directory is empty, delete it
                        shutil.rmtree(path.fullPathName())


        BCFileOperation.__hideProgressBar()

        QApplication.restoreOverrideCursor()

        if inError>0:
            BCSysTray.messageCritical(
                i18n(f"{title}::{modeMaj} files"),
                i18n(f"{modeMaj} process has been finished with errors\n\n<i>Items not {modeEd}: <b>{inError}</b> of <b>{len(files)}</b></i>")
            )

        if processed!=len(files):
            BCSysTray.messageWarning(
                i18n(f"{title}::{modeMaj} files"),
                i18n(f"{modeMaj} process has been cancelled\n\n<i>Items {modeEd} before action has been cancelled: <b>{processed - inError}</b> of <b>{len(files)}</b></i>")
            )
        elif inError==0:
            BCSysTray.messageInformation(
                i18n(f"{title}::{modeMaj} files"),
                i18n(f"{modeMaj} finished\n\n<i>Items {modeEd}: <b>{len(files)}</b></i>")
            )

    @staticmethod
    def delete(title, files, moveToTrash=False):
        """Delete files

        Given `files` is a list of BCBaseFile
        """
        # TODO: implement move to trash options
        #       improve message when error is encountered?

        # cancelled=0
        #   when cancelled > 0, it's the number of items processed
        QApplication.setOverrideCursor(Qt.WaitCursor)

        cancelled=0
        inError=0

        totalSize=0
        for file in files:
            if file.format() != BCFileManagedFormat.DIRECTORY:
                totalSize+=file.size()

        QApplication.restoreOverrideCursor()
        QApplication.setOverrideCursor(Qt.BusyCursor)
        BCFileOperation.__showProgressBar(i18n(f"{title}::Delete files"), len(files), totalSize)

        for file in files:
            try:
                if file.format() == BCFileManagedFormat.DIRECTORY:
                    BCFileOperation.__progressBarNext(file.fullPathName(), 0)
                    shutil.rmtree(file.fullPathName())
                else:
                    BCFileOperation.__progressBarNext(file.fullPathName(), file.size())
                    os.remove(file.fullPathName())
            except Exception as e:
                inError+=1
                Debug.print('[BCFileOperation.delete] Unable to delete file {0}: {1}', file.fullPathName(), str(e))

            if BCFileOperation.__isCancelled():
                cancelled=BCFileOperation.__value()
                break

        BCFileOperation.__hideProgressBar()

        QApplication.restoreOverrideCursor()

        if cancelled>0:
            BCSysTray.messageWarning(
                i18n(f"{title}::Delete files"),
                i18n(f"Deletion process has been cancelled\n\n<i>Items deleted before action has been cancelled: <b>{cancelled}</b> of <b>{len(files)}<b></i>")
            )
        if inError>0:
            BCSysTray.messageCritical(
                i18n(f"{title}::Delete files"),
                i18n(f"Deletion process has been finished with errors\n\n<i>Items not deleted: <b>{inError}</b> of <b>{len(files)}</b></i>")
            )

    @staticmethod
    def copy(title, files, targetPath):
        """Copy files

        Given `files` is a list of BCBaseFile
        """
        return BCFileOperation.__copyOrMove(title, files, targetPath, 'copy')

    @staticmethod
    def move(title, files, targetPath):
        """Move files

        Given `files` is a list of BCBaseFile
        """
        return BCFileOperation.__copyOrMove(title, files, targetPath, 'move')

    @staticmethod
    def createDir(path, createParent=True):
        """Create a new directory for given path

        Return True if file as heen created otherwise False
        """
        try:
            Path(path).mkdir(parents=createParent)
            return True
        except Exception as e:
            BCSysTray.messageCritical(
                i18n(f"{title}::Create directory"),
                f"Unable to create directory <b>{path}</b>"
            )
            return False

    @staticmethod
    def rename(title, files, renamePattern):
        """Rename file(s)

        Given `files` is a list of BCBaseFile
        """
        QApplication.setOverrideCursor(Qt.WaitCursor)

        actionOnFileExist = BCFileOperationUi.FILEEXISTS_ASK

        # cancelled=0
        #   when cancelled > 0, it's the number of items processed
        cancelled=0
        inError=0
        processed=None

        totalFiles=len(files)
        totalSize=0
        for file in files:
            totalSize+=file.size()

        QApplication.restoreOverrideCursor()
        QApplication.setOverrideCursor(Qt.BusyCursor)

        if totalFiles>0:
            BCFileOperation.__showProgressBar(i18n(f"{title}::Rename files"), len(files), totalSize)

        for file in files:
            if totalFiles>0:
                BCFileOperation.__progressBarNext(file.fullPathName(), file.size())

            # determinate new target full path name
            newFileName=BCFileManipulateName.calculateFileName(file, renamePattern)
            if not newFileName[1] is None:
                inError+=1
                Debug.print('[BCFileOperation.rename] Unable to rename file {0}: {1}', file.fullPathName(), newFileName[1])
                continue
            targetFile = os.path.join(file.path(), newFileName[0] )

            actionToApply = BCFileOperationUi.FILEEXISTS_OVERWRITE

            while os.path.exists(targetFile):
                # the target file already exists..

                if actionOnFileExist == BCFileOperationUi.FILEEXISTS_ASK:
                    # ask for user what to do...
                    QApplication.restoreOverrideCursor()
                    action = BCFileOperationUi.fileExists(title, 'Rename', file, targetFile, len(files))
                    QApplication.setOverrideCursor(Qt.BusyCursor)

                    if action[0] == BCFileOperationUi.FILEEXISTS_ABORT:
                        # exit immediately
                        actionToApply = BCFileOperationUi.FILEEXISTS_ABORT
                        # minus one because progress bar is already on next item while item has not yet been processed
                        processed=BCFileOperation.__value() - 1
                        break
                    elif action[0] == BCFileOperationUi.FILEEXISTS_RENAME:
                        # rename file
                        currentTarget = targetFile
                        targetFile = os.path.join(os.path.dirname(targetFile), BCFileManipulateName.parseFileNameKw(BCFile(targetFile), re.sub("(?i)\{file:(?:path|name)\}", '', action[1])))
                        actionToApply = BCFileOperationUi.FILEEXISTS_RENAME

                        # apply to all
                        if action[2]:
                            newFilePattern = re.sub("(?i)\{file:(?:path|name)\}", '', action[1])

                        # note: to do break loop
                        #       if new defined target file already exists, user will be asked again to change file name
                    else:
                        # apply to all
                        if action[2]:
                            actionOnFileExist = action[0]
                        actionToApply = action[0]
                        break
                else:
                    actionToApply = actionOnFileExist
                    break

            if actionToApply == BCFileOperationUi.FILEEXISTS_ABORT:
                # minus one because progress bar is already on next item while item has not yet been processed
                processed=BCFileOperation.__value() - 1
                break
            elif actionToApply == BCFileOperationUi.FILEEXISTS_SKIP:
                continue
            else:
                try:
                    #print('rename', file.fullPathName(), targetFile)
                    os.rename(file.fullPathName(), targetFile)
                except Exception as e:
                    inError+=1
                    Debug.print('[BCFileOperation.rename] Unable to rename file from {0} to {1}: {2}', file.fullPathName(), newName, str(e))


            if BCFileOperation.__isCancelled():
                cancelled=BCFileOperation.__value()
                break

        if totalFiles>0:
            BCFileOperation.__hideProgressBar()

        QApplication.restoreOverrideCursor()

        if cancelled>0:
            BCSysTray.messageWarning(
                i18n(f"{title}::Rename files"),
                i18n(f"Renaming process has been cancelled\n\n<i>Items renamed before action has been cancelled: <b>{cancelled}</b> of <b>{totalFiles}<b></i>")
            )
        if inError>0:
            BCSysTray.messageCritical(
                i18n(f"{title}::Rename files"),
                i18n(f"Renaming process has been finished with errors\n\n<i>Items not renamed: <b>{inError}</b> of <b>{totalFiles}</b></i>")
            )
        elif inError==0 and cancelled==0:
            BCSysTray.messageInformation(
                i18n(f"{title}::Rename files"),
                i18n(f"Renaming finished\n\n<i>Items renamed: <b>{totalFiles}</b></i>")
            )
