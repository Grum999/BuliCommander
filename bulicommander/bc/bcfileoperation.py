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

import os
import os.path
import shutil
import sys


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
        BCBaseFile,
        BCDirectory,
        BCFileManagedFormat,
        BCFileThumbnailSize
    )
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
    def __dialogFileOperation(message, information, message2=None, targetPath=None, message3=None):
        """Initialise default file dialog for delete/copy/move"""
        def pathChanged(value):
            BCFileOperationUi.__targetPath = self.frameBreacrumbPath.path()

        def showEvent(event):
            """Event trigerred when dialog is shown"""
            if not dlgMain._oldShowEvent is None:
                dlgMain._oldShowEvent()
            # need to set AFTER dialog is visible, otherwise there's a strange bug...
            dlgMain.frameBreacrumbPath.setPath(dlgMain.__targetPath)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcfileoperation.ui')
        dlgMain = PyQt5.uic.loadUi(uiFileName)
        dlgMain._oldShowEvent = dlgMain.showEvent

        dlgMain.lblMessage.setText(message)
        dlgMain.pteInfo.setPlainText(information)

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
            dlgMain.frameBreacrumbPath.showFilter(False)
            dlgMain.frameBreacrumbPath.showBookmark(False)
            dlgMain.frameBreacrumbPath.showHistory(False)
            BCFileOperationUi.__targetPath = targetPath

        if message3 is None or message3 == '':
            dlgMain.lblMessage3.setVisible(False)
            dlgMain.layout().removeWidget(dlgMain.lblMessage3)
        else:
            dlgMain.lblMessage3.setText(message3)

        dlgMain.buttonBox.accepted.connect(dlgMain.accept)
        dlgMain.buttonBox.rejected.connect(dlgMain.reject)

        return dlgMain

    @staticmethod
    def __dialogFileExists(action, fileSrc, fileTgt, nbFiles=0):
        """Initialise default file dialog for existing files"""
        def action_rename(dummy):
            dlgMain.__action=BCFileOperationUi.FILEEXISTS_RENAME
            dlgMain.__renamed = dlgMain.leFileRename.text()
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
                dlgMain.lblFileSrcNfo.setText(f"<b>Date:</b> {tsToStr(fileSrc.lastModificationDateTime())}<br><b>Size:</b> {bytesSizeToStr(fileSrc.size())} ({fileSrc.size():n})<br><b>Image size:</b> {fileSrc.imageSize().width()}x{fileSrc.imageSize().height()}")
            else:
                iconSrc = fileSrc.icon()
                dlgMain.lblFileSrcNfo.setText(f"<b>Date:</b> {tsToStr(fileSrc.lastModificationDateTime())}<br><b>Size:</b> {bytesSizeToStr(fileSrc.size())} ({fileSrc.size():n})")

        if fileTgt.format() == BCFileManagedFormat.DIRECTORY:
            iconTgt = fileTgt.icon()
            dlgMain.lblFileTgtNfo.setText(f"<b>Date:</b> {tsToStr(fileTgt.lastModificationDateTime())}")
        else:
            if fileTgt.readable():
                iconTgt = fileTgt.thumbnail(BCFileThumbnailSize.HUGE, BCBaseFile.THUMBTYPE_ICON)
                dlgMain.lblFileTgtNfo.setText(f"<b>Date:</b> {tsToStr(fileTgt.lastModificationDateTime())}<br><b>Size:</b> {bytesSizeToStr(fileTgt.size())} ({fileTgt.size():n})<br><b>Image size:</b> {fileTgt.imageSize().width()}x{fileTgt.imageSize().height()}")
            else:
                iconTgt = fileTgt.icon()
                dlgMain.lblFileTgtNfo.setText(f"<b>Date:</b> {tsToStr(fileTgt.lastModificationDateTime())}<br><b>Size:</b> {bytesSizeToStr(fileTgt.size())} ({fileTgt.size():n})")

        dlgMain.lblFileSrcImg.setPixmap(iconSrc.pixmap(BCFileThumbnailSize.HUGE.value, BCFileThumbnailSize.HUGE.value))
        dlgMain.lblFileTgtImg.setPixmap(iconTgt.pixmap(BCFileThumbnailSize.HUGE.value, BCFileThumbnailSize.HUGE.value))

        dlgMain.leFileRename.setText(fileSrc.name())

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
    def path():
        """Return path"""
        return BCFileOperationUi.__targetPath

    @staticmethod
    def delete(title, nbFiles, nbDirectories, information):
        """Open dialog box"""
        db = BCFileOperationUi.__dialogFileOperation(BCFileOperationUi.__buildMsg('Delete', nbFiles, nbDirectories), information)
        db.setWindowTitle(f"{title}::Delete files")
        return db.exec()

    @staticmethod
    def copy(title, nbFiles, nbDirectories, information, targetPath):
        """Open dialog box"""
        db = BCFileOperationUi.__dialogFileOperation(BCFileOperationUi.__buildMsg('Copy', nbFiles, nbDirectories), information, "To", targetPath)
        db.setWindowTitle(f"{title}::Copy files")
        return db.exec()

    @staticmethod
    def move(title, nbFiles, nbDirectories, information, targetPath):
        """Open dialog box"""
        db = BCFileOperationUi.__dialogFileOperation(BCFileOperationUi.__buildMsg('Move', nbFiles, nbDirectories), information, "To", targetPath)
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

        BCFileOperation.__PROGRESS.bbCancel.rejected.connect(BCFileOperation.__PROGRESS.reject)

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
    def delete(title, files, moveToTrash=False):
        """Delete files

        Given `files` is a list of BCBaseFile
        """
        # TODO: implement move to trash options
        #       improve message when error is encountered?

        # cancelled=0
        #   when cancelled > 0, it's the number of items processed
        cancelled=0
        inError=0

        totalSize=0
        for file in files:
            if file.format() != BCFileManagedFormat.DIRECTORY:
                totalSize+=file.size()

        BCFileOperation.__showProgressBar(f"{title}::Delete files", len(files), totalSize)

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

        if cancelled>0:
            QMessageBox.information(
                QWidget(),
                f"{title}::Delete files",
                f"Deletion process has been cancelled\n\nItems deleted before action has been cancelled: {cancelled}/{len(files)}"
            )
        elif inError>0:
            QMessageBox.warning(
                QWidget(),
                f"{title}::Delete files",
                f"Deletion process has been finished with errors\n\nItems not deleted: {inError}/{len(files)}"
            )

    @staticmethod
    def copy(title, files, targetPath):
        """Copy files

        Given `files` is a list of BCBaseFile
        """
        actionOnFileExist = BCFileOperationUi.FILEEXISTS_ASK
        actionOnPathExist = BCFileOperationUi.FILEEXISTS_ASK
        actionForFile = actionOnFileExist
        actionForPath = actionOnPathExist

        cancelled=0
        inError=0

        index=0
        totalSize=0
        pathsList={}
        for file in files:
            if file.format() != BCFileManagedFormat.DIRECTORY:
                totalSize+=file.size()
            else:
                pathsList[file.fullPathName()]=file.name()
            index+=1

        print("copy-0", pathsList)

        if len(pathsList)>0:
            fileList=BCFileList()
            fileList.addPath([BCFileListPath(path, True) for path in list(pathsList.keys())])
            fileList.execute()
            files+=fileList.files()
            for file in fileList.files():
                totalSize+=file.size()
                print(file.fullPathName())

        BCFileOperation.__showProgressBar(f"{title}::Copy files", len(files), totalSize)

        for file in files:
            isDir=False
            if file.format() == BCFileManagedFormat.DIRECTORY:
                BCFileOperation.__progressBarNext(file.fullPathName(), 0)
                isDir=True
            else:
                BCFileOperation.__progressBarNext(file.fullPathName(), file.size())

            if file.path() in pathsList:
                # use new name for current directory
                targetFile = os.path.join(targetPath, pathsList[file.path()], file.name())
            else:
                targetFile = os.path.join(targetPath, file.name())

            print("copy-1", file.path(), file.name(), isDir, targetFile)

            actionToApply = BCFileOperationUi.FILEEXISTS_OVERWRITE

            while os.path.exists(targetFile):
                if (not isDir and actionOnFileExist == BCFileOperationUi.FILEEXISTS_ASK) or (isDir and actionOnPathExist == BCFileOperationUi.FILEEXISTS_ASK):
                    action = BCFileOperationUi.fileExists(title, 'Copy', file, targetFile, len(files))

                    if action[0] == BCFileOperationUi.FILEEXISTS_ABORT:
                        actionToApply = BCFileOperationUi.FILEEXISTS_ABORT
                        cancelled=BCFileOperation.__value()
                        break
                    elif action[0] == BCFileOperationUi.FILEEXISTS_RENAME:
                        if isDir and os.path.join(file.path(), file.name()) in pathsList:
                            pathsList[os.path.join(file.path(), file.name())] = action[1]
                            print("copy-r1", pathsList)
                        targetFile = os.path.join(targetPath, action[1])
                        print("copy-r2", targetFile)
                        actionToApply = BCFileOperationUi.FILEEXISTS_RENAME
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

            print("copy-2", targetFile, actionToApply)

            if actionToApply == BCFileOperationUi.FILEEXISTS_ABORT:
                cancelled=BCFileOperation.__value()
                break
            elif actionToApply == BCFileOperationUi.FILEEXISTS_SKIP:
                continue
            elif isDir:
                try:
                    os.makedirs(targetFile, exist_ok=True)
                except Exception as e:
                    inError+=1
                    Debug.print('[BCFileOperation.copy] Unable to copy file from {0} to {1}: {2}', file.fullPathName(), targetFile, str(e))
            elif not isDir:
                try:
                    shutil.copy2(file.fullPathName(), targetFile)
                except Exception as e:
                    inError+=1
                    Debug.print('[BCFileOperation.copy] Unable to copy file from {0} to {1}: {2}', file.fullPathName(), targetFile, str(e))

            if BCFileOperation.__isCancelled():
                cancelled=BCFileOperation.__value()
                break

        BCFileOperation.__hideProgressBar()

        if cancelled>0:
            QMessageBox.information(
                QWidget(),
                f"{title}::Copy files",
                f"Copy process has been cancelled\n\nItems copied before action has been cancelled: {cancelled}/{len(files)}"
            )
        elif inError>0:
            QMessageBox.warning(
                QWidget(),
                f"{title}::Copy files",
                f"Copy process has been finished with errors\n\nItems not copied: {inError}/{len(files)}"
            )

    @staticmethod
    def move(files, targetPath):
        """Move files

        Given `files` is a list of BCBaseFile
        """
        print('move to', targetPath)

    @staticmethod
    def createDir(path, createParent=True):
        """Create a new directory for given path

        Return True if file as heen created otherwise False
        """
        try:
            Path(path).mkdir(parents=createParent)
            return True
        except Exception as e:
            return False


