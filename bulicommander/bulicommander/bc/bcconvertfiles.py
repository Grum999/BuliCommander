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

import PyQt5.uic
from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal,
        QSettings,
        QStandardPaths
    )
from PyQt5.QtWidgets import (
        QDialog,
        QFileDialog,
        QMessageBox
    )

import os
import re
import shutil
import time


from .bcfile import (
        BCBaseFile,
        BCDirectory,
        BCFile,
        BCFileManagedFormat,
        BCFileManipulateName,
        BCFileProperty,
        BCFileThumbnailSize
    )
from .bcsettings import BCSettingsKey
from .bcsystray import BCSysTray

from .bcwconsole import BCWConsole
from .bcwexportoptions import (
        BCWExportOptionsJpeg,
        BCWExportOptionsPng
    )
from .bcwpathbar import BCWPathBar
from .bcutils import (
        bytesSizeToStr,
        checkerBoardBrush,
        strDefault,
        tsToStr,
        cloneRect,
        Debug
    )
from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )
from ..pktk.ekrita import EKritaNode

# -----------------------------------------------------------------------------


class BCConvertFilesDialogBox(QDialog):
    """User interface to convert files"""

    __PAGE_PERIMETER = 0
    __PAGE_TARGET = 1

    FMT_PROPERTIES = {
            0: {'label': 'Krita'},
            1: {'label': 'PNG'},
            2: {'label': 'JPEG'}
        }

    def __init__(self, title, uicontroller, parent=None):
        super(BCConvertFilesDialogBox, self).__init__(parent)

        self.__title = title
        self.__convertedFileName = ''
        self.__targetExtension = 'kra'

        self.__uiController = uicontroller
        self.__fileNfo = self.__uiController.panel().files()
        self.__selectedFileNfo = self.__uiController.panel().selectedFiles()

        self.__hasSavedSettings = self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_GLB_SAVED.id())

        self.__processing=False

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcconvertfiles.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.bcwpbTargetDirectory.setOptions(BCWPathBar.OPTION_SHOW_NONE)

        self.setWindowTitle(self.__title)

        self.__initialise()

    def __initialise(self):
        """Initialise interface"""
        def __initialisePagePerimeter():
            # Initialise interface widgets for page perimeter
            # interface widgets that don't depend of users settings

            # always select "Selected path" as default (not stored in settings) as
            # the "Selected files" can be disabled
            self.rbPerimeterSelectPath.setChecked(True)

            self.lblPerimeterSelectPathNfo.setText(i18n(f"<b>{self.__getPath()}</b> (Files: {self.__fileNfo[2]}, Directories: {self.__fileNfo[1]})"))
            self.lblPerimeterSelectSelNfo.setText(i18n(f"(Files: {self.__selectedFileNfo[2]}, Directories: {self.__selectedFileNfo[1]})"))
            if self.__selectedFileNfo[3] > 0:
                self.rbPerimeterSelectSel.setEnabled(True)
                self.lblPerimeterSelectSelNfo.setEnabled(True)
            else:
                self.rbPerimeterSelectSel.setEnabled(False)
                self.lblPerimeterSelectSelNfo.setEnabled(False)

            self.cbxFormat.currentIndexChanged.connect(self.__slotFormatChanged)

            self.__loadSettingsPagePerimeter()

        def __initialisePageTarget():
            # Initialise interface widgets for page target
            def checkButton(dummy):
                self.__updateBtn()

            self.wProgress.setVisible(False)

            self.rbTargetDirectorySame.toggled.connect(checkButton)
            self.rbTargetDirectoryDesigned.toggled.connect(checkButton)
            self.leTargetFilePattern.textChanged.connect(checkButton)

            self.__loadSettingsPageTarget()

        def __initialiseButtonBar():
            # Initialise bottom button bar
            self.pbPrevious.clicked.connect(self.__goPreviousPage)
            self.pbNext.clicked.connect(self.__goNextPage)
            self.pbCancel.clicked.connect(self.__cancel)
            self.pbConvert.clicked.connect(self.__convert)
            self.pbOptionsLoadDefault.clicked.connect(self.__resetSettings)
            self.__updateBtn()

        __initialisePagePerimeter()
        __initialisePageTarget()
        __initialiseButtonBar()

    # -- Manage page Perimeter -------------------------------------------------
    def __loadDefaultPagePerimeter(self):
        """Load default internal configuration for page perimeter"""
        # reload default properties list
        self.bcweoPng.setOptions()
        self.bcweoJpg.setOptions()
        self.swPages.setCurrentIndex(BCConvertFilesDialogBox.__PAGE_PERIMETER)
        self.cbxFormat.setCurrentIndex(0)
        self.swSaveOptions.setCurrentIndex(0)

    def __loadSettingsPagePerimeter(self):
        """Load saved settings for page perimeter"""
        if not self.__hasSavedSettings:
            # no saved settings: load default and exit
            self.__loadDefaultPagePerimeter()
            return

        self.swPages.setCurrentIndex(BCConvertFilesDialogBox.__PAGE_PERIMETER)
        self.cbxFormat.setCurrentIndex(['kra','png','jpeg'].index(self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_GLB_FORMAT.id())))
        self.__slotFormatChanged(self.cbxFormat.currentIndex())
        self.bcweoPng.setOptions({
            'compression': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_COMPRESSION.id()),
            'indexed': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_INDEXED.id()),
            'interlaced': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_INTERLACED.id()),
            'saveSRGBProfile': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_SAVEICCPROFILE.id()),
            'forceSRGB': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_FORCESRGB.id()),
            'alpha': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_ALPHA.id()),
            'transparencyFillcolor': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_BGCOLOR.id()),
        })
        self.bcweoJpg.setOptions({
            'quality': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_QUALITY.id()),
            'smoothing': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SMOOTHING.id()),
            'subsampling': ['4:2:0','4:2:2','4:4:0','4:4:4'].index(self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SUBSAMPLING.id())),
            'progressive': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_PROGRESSIVE.id()),
            'optimize': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_OPTIMIZE.id()),
            'saveProfile': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SAVEICCPROFILE.id()),
            'transparencyFillcolor': self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_BGCOLOR.id()),
        })

    def __slotFormatChanged(self, index):
        """File format has been changed"""
        self.swSaveOptions.setCurrentIndex(index)

    def __slotTargetChanged(self, index):
        """File format has been changed"""
        self.swSaveOptions.setCurrentIndex(index)

    # -- Manage page Target -------------------------------------------------
    def __loadDefaultPageTarget(self):
        """Load default internal configuration for page target"""
        self.leTargetFilePattern.setText('{file:baseName}.{targetExtension}')

    def __loadSettingsPageTarget(self):
        """Load saved settings for page format"""
        # opposite panel path by default
        self.bcwpbTargetDirectory.setPath(self.__uiController.panel(False).path())

        if not self.__hasSavedSettings:
            # no saved settings: load default and exit
            self.__loadDefaultPageTarget()
            return

        self.leTargetFilePattern.setText(self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_GLB_TARGET_FILEPATTERN.id()))
        self.rbTargetDirectorySame.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_GLB_TARGET_MODE.id())=='sdir')
        self.rbTargetDirectoryDesigned.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_CONVERTFILES_GLB_TARGET_MODE.id())=='ddir')

    # -- Other functions -------------------------------------------------
    def __goPreviousPage(self, action):
        """Go to previous page"""
        if self.swPages.currentIndex() > 0:
            self.swPages.setCurrentIndex(self.swPages.currentIndex() - 1)
        self.__updateBtn()

    def __goNextPage(self, action):
        """Go to next page"""
        if self.swPages.currentIndex() < self.swPages.count() - 1:
            # while page is not the last, continue to next page:
            self.swPages.setCurrentIndex(self.swPages.currentIndex() + 1)

        if self.swPages.currentIndex() == BCConvertFilesDialogBox.__PAGE_TARGET:
            # xxx
            pass

        self.__updateBtn()

    def __cancel(self, action):
        """Button cancel clicked"""
        if self.__processing:
            self.__processing=False
        else:
            self.reject()

    def __updateBtn(self):
        """Update buttons state according to current page"""
        # note: enable/disable instead of show/hide, that's less disturbing in the
        #       navigation

        # First page / previous button not enabled
        self.pbPrevious.setEnabled(self.swPages.currentIndex() != 0)

        if self.swPages.currentIndex() == 0:
            # first page
            self.pbNext.setEnabled(True)
        elif self.swPages.currentIndex() == self.swPages.count() - 1:
            # Last page / next button disabled
            self.pbNext.setEnabled(False)
        else:
            self.pbNext.setEnabled(True)

        # Last page / OK button enabled if a file target is valid
        self.pbConvert.setEnabled(self.__targetIsValid())

        self.bcwpbTargetDirectory.setEnabled(self.rbTargetDirectoryDesigned.isChecked())

    def __targetIsValid(self):
        """Return True is current selected target is valid, otherwise False"""
        # first, we must be on the target page
        returned = (self.swPages.currentIndex() == self.swPages.count() - 1)
        if not returned:
            return returned

        # otherwise target is valid if a file name is provided
        # do not check if provided path/filename make sense...
        return (self.leTargetFilePattern.text().strip() != '')

    def __generateConfig(self):
        """Generate export config"""
        def getFiles():
            if self.rbPerimeterSelectPath.isChecked():
                return self.__fileNfo[5]
            else:
                return self.__selectedFileNfo[5]

        returned = {}

        return returned

    def __saveSettings(self):
        """Save current export configuration to settings"""
        def __savePagePerimeter():
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_GLB_FORMAT, ['kra','png','jpeg'][self.cbxFormat.currentIndex()])

            if self.cbxFormat.currentIndex()==1:
                pngOptions=self.bcweoPng.options()
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_COMPRESSION, pngOptions['compression'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_INDEXED, pngOptions['indexed'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_INTERLACED, pngOptions['interlaced'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_SAVEICCPROFILE, pngOptions['saveSRGBProfile'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_FORCESRGB, pngOptions['forceSRGB'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_ALPHA, pngOptions['alpha'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_BGCOLOR, pngOptions['transparencyFillcolor'].name(QColor.HexRgb))
            elif self.cbxFormat.currentIndex()==2:
                jpgOptions=self.bcweoJpg.options()
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_QUALITY, jpgOptions['quality'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SMOOTHING, jpgOptions['smoothing'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SUBSAMPLING, ['4:2:0','4:2:2','4:4:0','4:4:4'][jpgOptions['subsampling']])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_PROGRESSIVE, jpgOptions['progressive'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_OPTIMIZE, jpgOptions['optimize'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SAVEICCPROFILE, jpgOptions['saveProfile'])
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_BGCOLOR, jpgOptions['transparencyFillcolor'].name(QColor.HexRgb))

        def __savePageTarget():
            if self.rbTargetDirectorySame.isChecked():
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_GLB_TARGET_MODE, 'sdir')
            else:
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_GLB_TARGET_MODE, 'ddir')

            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_GLB_TARGET_FILEPATTERN, self.leTargetFilePattern.text())

        __savePagePerimeter()
        __savePageTarget()

        self.__uiController.settings().setOption(BCSettingsKey.CONFIG_CONVERTFILES_GLB_SAVED, True)
        self.__uiController.saveSettings()

    def __resetSettings(self):
        """Reset export configuration to default settings"""
        self.__loadDefaultPagePerimeter()
        self.__loadDefaultPageTarget()

    def __convert(self):
        """Export process"""

        self.__saveSettings()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.__processing=True

        if self.cbxFormat.currentIndex()==0:
            self.__targetExtension = 'kra'
            exportOptions = None
        elif self.cbxFormat.currentIndex()==1:
            self.__targetExtension = 'png'
            exportOptions = self.bcweoPng.options(True)
        elif self.cbxFormat.currentIndex()==2:
            self.__targetExtension = 'jpeg'
            exportOptions = self.bcweoJpg.options(True)

        if self.rbTargetDirectorySame.isChecked():
            targetDirectory = self.__uiController.panel().path()
        else:
            targetDirectory = self.bcwpbTargetDirectory.path()

        self.pbOptionsLoadDefault.setEnabled(False)
        self.pbPrevious.setEnabled(False)
        self.pbNext.setEnabled(False)
        self.pbConvert.setEnabled(False)
        #self.pbCancel.setEnabled(False)
        self.rbTargetDirectorySame.setEnabled(False)
        self.rbTargetDirectoryDesigned.setEnabled(False)
        self.bcwpbTargetDirectory.setEnabled(False)
        self.leTargetFilePattern.setEnabled(False)

        self.__uiController.setAllowRefresh(False)



        if self.rbPerimeterSelectPath.isChecked():
            files = self.__fileNfo[5]
        else:
            files = self.__selectedFileNfo[5]

        filePattern = self.leTargetFilePattern.text()

        self.pteConsole.clear()

        self.pgbTargetResultExport.setValue(0)
        self.pgbTargetResultExport.setMaximum(len(files))
        self.wProgress.setVisible(True)

        fileKo=0
        fileNumber = 1
        fileTotalNumber = len(files)
        for file in files:
            if self.__processing==False:
                break
            self.__convertedFileName = file.fullPathName()
            targetName = os.path.join(targetDirectory, self.__parseFileNameKw(file, filePattern, targetDirectory))


            self.pgbTargetResultExport.setValue(fileNumber)
            QApplication.instance().processEvents()

            self.pteConsole.appendLine(i18n(f'Convert file <i>{fileNumber}</i> of <i>{fileTotalNumber}</i>'))
            self.pteConsole.appendLine(i18n(f'. Source file <i>{self.__convertedFileName}</i> ({bytesSizeToStr(file.size())})'))
            self.pteConsole.appendLine(i18n(f'. Target file <i>{targetName}</i>'))

            if targetName != self.__convertedFileName:
                if not os.path.exists(targetName):
                    self.pteConsole.appendLine(i18n('> Load source file: '))
                    currentDocument = Krita.instance().openDocument(self.__convertedFileName)

                    if not currentDocument is None:
                        self.pteConsole.append(i18n('OK'), 'ok')

                        currentDocument.setBatchmode(True) # no popups while saving

                        if self.__processing==False:
                            break

                        if self.__targetExtension == 'kra':
                            self.pteConsole.appendLine(i18n('> Save target file: '))
                            saved = currentDocument.saveAs(targetName)
                        else:
                            self.pteConsole.appendLine(i18n('> Export target file: '))
                            saved = currentDocument.exportImage(targetName, exportOptions)

                        if not saved:
                            self.pteConsole.append(i18n('KO'), 'error')
                            fileKo+=1
                        else:
                            self.pteConsole.append(i18n('OK'), 'ok')

                        currentDocument.close()
                    else:
                        self.pteConsole.append([(i18n('KO '), 'error'),  (i18n('<i>(Unable to open file)</i>'), 'info')])
                else:
                    self.pteConsole.appendLine('> ')
                    self.pteConsole.append([(i18n('SKIPPED '), 'ignore'),  (i18n('<i>(Target file already exists)</i>'), 'info')])
            else:
                self.pteConsole.appendLine('> ')
                self.pteConsole.append([(i18n('SKIPPED '), 'ignore'),  (i18n('<i>(Target and source are identical)</i>'), 'info')])

            self.pteConsole.appendLine('')
            fileNumber+=1

        self.__uiController.setAllowRefresh(True)

        QApplication.restoreOverrideCursor()

        if self.__processing==False:
            self.pteConsole.appendLine('> ')
            self.pteConsole.append(i18n('Process cancelled by user!'), 'warning')
            BCSysTray.messageCritical(i18n(f"{self.__uiController.bcName()}::Convert files"),
                                      i18n(f"Convert {fileTotalNumber} as <i>{BCConvertFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['label']}</i> format has been cancelled by user"))
        elif fileKo == 0:
            # export successful, save current settings
            BCSysTray.messageInformation(i18n(f"{self.__uiController.bcName()}::Convert files"),
                                         i18n(f"Convert {fileTotalNumber} files as <i>{BCConvertFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['label']}</i> format is finished"))
            ##### export ok: do not close window, let user read console and/or redo a convert...
            ##### DON'T UNCOMMENT! :-)
            #self.accept()
        else:
            BCSysTray.messageCritical(i18n(f"{self.__uiController.bcName()}::Convert files"),
                                      i18n(f"Convert {fileTotalNumber} as <i>{BCConvertFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['label']}</i> format has failed (files in failure: {fileKo})"))
            ##### export failed: do not close window, let user try to check/fix the problem
            ##### DON'T UNCOMMENT! :-)
            ##### self.reject()

        QApplication.restoreOverrideCursor()
        #self.wProgress.setVisible(False)
        self.__updateBtn()
        self.rbTargetDirectorySame.setEnabled(True)
        self.rbTargetDirectoryDesigned.setEnabled(True)
        if self.rbTargetDirectoryDesigned.isChecked():
            self.bcwpbTargetDirectory.setEnabled(True)
        self.leTargetFilePattern.setEnabled(True)
        #self.pbCancel.setEnabled(True)
        self.__processing=False

    def __getPath(self):
        """Return path (path file/name or quick ref)"""
        path=self.__uiController.panel().path()
        lPath=path.lower()
        refDict=self.__uiController.quickRefDict()

        if lPath in refDict:
            return f"{refDict[path][2]}"
        return path

    def __parseFileNameKw(self, file, filePattern, targetDirectory):
        """Parse given text to replace markup with their values"""
        returned = filePattern

        returned = re.sub("(?i)\{bc:name\}",                        self.__uiController.bcName(),                       returned)
        returned = re.sub("(?i)\{bc:version\}",                     self.__uiController.bcVersion(),                    returned)
        returned = re.sub("(?i)\{bc:title\}",                       self.__uiController.bcTitle(),                      returned)

        returned = re.sub("(?i)\{targetExtension\}",                self.__targetExtension,                             returned)

        returned = BCFileManipulateName.parseFileNameKw(file, returned, targetDirectory)

        return returned

    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCConvertFilesDialogBox(title, uicontroller)
        return db.exec()
