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
# The bcfilenoperation module provides methods to copy/move/rename/delete files
#
# Main classes from this module
#
# - BCFileOperationUi & BCFileOperationMassRenameUi:
#       User interface for actions on files
#
# - BCFileOperation:
#       Execute files operation with user information progress, taking in
#       account user choice for skip/override case, ....
#
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
import json
import html

import PyQt5.uic
from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )
from PyQt5.QtWidgets import (
        QDialog
    )
from PyQt5.QtGui import (
        QTextCursor,
        QBrush,
        QStandardItem,
        QStandardItemModel,
        QColor
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
from .bcfilenamemanipulationlanguage import (
        BCFileManipulateName,
        BCFileManipulateNameLanguageDef
    )
from .bcfileoperation_renamefile_visualformulaeditor import BCRenameFileVisualFormulaEditorDialogBox
from .bcsystray import BCSysTray
from .bcwpathbar import BCWPathBar
from .bcsettings import (
        BCSettingsKey,
        BCSettings
    )

from bulicommander.pktk.modules.utils import (
        Debug,
        JsonQObjectEncoder,
        JsonQObjectDecoder
    )
from bulicommander.pktk.modules.imgutils import buildIcon
from bulicommander.pktk.modules.strutils import (
        bytesSizeToStr,
        strDefault,
        stripHtml
    )

from bulicommander.pktk.modules.timeutils import tsToStr
from bulicommander.pktk.widgets.wiodialog import WDialogStrInput
from bulicommander.pktk.modules.tokenizer import TokenizerRule
from bulicommander.pktk.modules.menuutils import buildQMenu

from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )
from bulicommander.pktk.widgets.wiodialog import (
        WDialogBooleanInput,
        WDialogMessage
    )

# ------------------------------------------------------------------------------


class WMenuForCommand(QWidgetAction):
    """Encapsulate a QLabel as a menu item, used to display completion command properly formatted in menu"""
    onEnter = Signal()

    def __init__(self, label, help, parent=None):
        super(WMenuForCommand, self).__init__(parent)
        self.__label = QLabel(self.__reformattedText(label))
        self.__label.setStyleSheet("QLabel:hover { background: palette(highlight); color: palette(highlighted-text);}")
        self.__label.setContentsMargins(4, 4, 4, 4)
        self.__label.mousePressEvent = self.__pressEvent
        self.__label.enterEvent = self.__enterEvent

        self.__layout = QVBoxLayout()
        self.__layout.setSpacing(0)
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.__layout.addWidget(self.__label)

        self.__widget = QWidget()
        self.__widget.setContentsMargins(0, 0, 0, 0)
        self.__widget.setMouseTracking(True)
        self.__widget.setLayout(self.__layout)

        self.__hover = False
        self.__help = help

        self.setDefaultWidget(self.__widget)

    def __reformattedText(self, text):
        """Reformat given text, assuming it's a completion text command"""
        returned = []
        texts = text.replace(BCFileManipulateNameLanguageDef.SEP_SECONDARY_VALUE,
                             BCFileManipulateNameLanguageDef.SEP_PRIMARY_VALUE).split(BCFileManipulateNameLanguageDef.SEP_PRIMARY_VALUE)
        for index, textItem in enumerate(texts):
            if index % 2 == 1:
                # odd text ("optionnal" information) are written smaller, with darker color
                returned.append(f"<i>{textItem}</i>")
            else:
                # normal font
                returned.append(textItem)

        return ''.join(returned)

    def __pressEvent(self, event):
        """When label clicked, trigger event for QWidgetAction and close parent menu"""
        self.trigger()
        menu = None
        parentWidget = self.parentWidget()
        while(isinstance(parentWidget, QMenu)):
            menu = parentWidget
            parentWidget = menu.parentWidget()

        if menu:
            menu.close()

    def __enterEvent(self, event):
        """When mouse goes over label, trigger signal onEnter"""
        self.__displayCompleterHint()
        self.onEnter.emit()

    def __hideCompleterHint(self):
        """Hide completer hint"""
        QToolTip.showText(self.mapToGlobal(QPoint()), '')
        QToolTip.hideText()

    def __displayCompleterHint(self, index=None):
        """Display completer hint"""
        if self.__help is None or self.__help == '':
            self.__hideCompleterHint()
            return
        else:
            geometry = self.__label.geometry()
            position = QPoint(geometry.left() + geometry.width(), geometry.top())
            # it's not possible to move a tooltip
            # need to set a different value to force tooltip being refreshed to new position
            QToolTip.showText(self.__label.mapToGlobal(position), self.__help+' ')
            QToolTip.showText(self.__label.mapToGlobal(position), self.__help, self.__label, QRect(), 600000)  # 10minutes..


class BCFileOperationMassRenameUi(QDialog):
    """Dedicated mass rename window dialog

    Use of static function is not possible anymore due t complexity of UI
    """

    # note: IMPORT/EXPORT results codes identical to NodeEditorScene IMPORT/EXPORT results codes
    IMPORT_OK =                              0b00000000
    IMPORT_FILE_NOT_FOUND =                  0b00000001
    IMPORT_FILE_CANT_READ =                  0b00000010
    IMPORT_FILE_NOT_JSON =                   0b00000100
    IMPORT_FILE_INVALID_FORMAT_IDENTIFIER =  0b00001000
    IMPORT_FILE_MISSING_FORMAT_IDENTIFIER =  0b00010000
    IMPORT_FILE_MISSING_SCENE_DEFINITION =   0b00100000

    EXPORT_OK =       0b00000000
    EXPORT_CANT_SAVE = 0b00000001

    FILEDATA = Qt.UserRole + 1

    def __init__(self, title, fileList, parent=None):
        super(BCFileOperationMassRenameUi, self).__init__(parent)
        self.__nbFiles = 0
        self.__fileList = fileList
        self.__currentLoadedConfigurationFile = ''
        self.__title = title
        self.__isModified = False

        self.setWindowTitle(title)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcrenamefile_multi.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        if self.__fileList[0].format() == BCFileManagedFormat.DIRECTORY:
            label = i18n('directory')
            self.__labelPlural = i18n('directories')
            self.__defaultPattern = '{file:baseName}'
        else:
            label = i18n('file')
            self.__labelPlural = i18n('files')
            self.__defaultPattern = '{file:baseName}.{file:ext}'

        self.__fileManipulateNameLanguageDef = BCFileManipulateName.languageDefinition()

        self.cePattern.setPlainText(self.__defaultPattern)
        self.cePattern.textChanged.connect(self.__patternChanged)
        self.cePattern.setLanguageDefinition(self.__fileManipulateNameLanguageDef)
        self.cePattern.setOptionMultiLine(False)
        self.cePattern.setOptionShowLineNumber(False)
        self.cePattern.setOptionShowIndentLevel(False)
        self.cePattern.setOptionShowRightLimit(False)
        self.cePattern.setOptionShowSpaces(False)
        self.cePattern.setOptionAllowWheelSetFontSize(False)
        self.cePattern.setUndoRedoEnabled(True)
        self.cePattern.setShortCut(Qt.Key_Tab, False, None)      # disable indent
        self.cePattern.setShortCut(Qt.Key_Backtab, False, None)  # disable dedent
        self.cePattern.setShortCut(Qt.Key_Slash, True, None)     # disable toggle comment
        self.cePattern.setShortCut(Qt.Key_Return, False, None)   # disable autoindent
        self.cePattern.contextMenu = self.__cePatternContextMenu

        actionSave = QAction(i18n("Save"), self)
        actionSave.triggered.connect(lambda: self.saveFile())
        actionSaveAs = QAction(i18n("Save as..."), self)
        actionSaveAs.triggered.connect(lambda: self.saveFile(True))

        menuSave = QMenu(self.tbSaveFormulaDefinition)
        menuSave.addAction(actionSave)
        menuSave.addAction(actionSaveAs)
        self.tbSaveFormulaDefinition.setMenu(menuSave)

        self.tbNewFormulaDefinition.clicked.connect(self.__newFormulaDefinition)
        self.tbOpenFormulaDefinition.clicked.connect(lambda: self.openFile())
        self.tbSaveFormulaDefinition.clicked.connect(lambda: self.saveFile())
        self.tbVisualFormulaEditor.clicked.connect(self.__visualFormulaEditor)

        self.cbShowPath.toggled.connect(self.__showPathChanged)

        self.lblError.setVisible(False)

        self.__model = QStandardItemModel(0, 3, self)
        self.__model.setHeaderData(0, Qt.Horizontal, i18n("Path"))
        self.__model.setHeaderData(1, Qt.Horizontal, i18n(f"Source {label} name"))
        self.__model.setHeaderData(2, Qt.Horizontal, i18n(f"Renamed {label} name"))

        self.tvResultPreview.setModel(self.__model)

        self.__header = self.tvResultPreview.header()
        self.__header.setStretchLastSection(False)
        self.__header.setSectionResizeMode(0, QHeaderView.Interactive)
        self.__header.setSectionResizeMode(1, QHeaderView.Interactive)

        for file in self.__fileList:
            if not file.format() == BCFileManagedFormat.MISSING:
                self.__addFileToListView(file)
                self.__nbFiles += 1

        self.__updateNbFilesLabelAndBtnOk()

        self.tvResultPreview.resizeColumnToContents(0)
        self.tvResultPreview.resizeColumnToContents(1)
        self.tvResultPreview.resizeColumnToContents(2)

        self.__header.setSectionHidden(0, True)

        self.cbExcludeSelected.setText(i18n(f'Exclude selected {self.__labelPlural}'))

        self.cbExcludeSelected.toggled.connect(self.__updateNbFilesLabelAndBtnOk)
        self.tvResultPreview.selectionModel().selectionChanged.connect(self.__selectionChanged)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.__viewWindowMaximized(BCSettings.get(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_WINDOW_MAXIMIZED))
        self.__viewWindowGeometry(BCSettings.get(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_WINDOW_GEOMETRY))

        self.__isModified = False
        self.__updateFileNameLabel()

    def __saveSettings(self):
        """Save current search window settings"""
        BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_WINDOW_MAXIMIZED, self.isMaximized())
        if not self.isMaximized():
            # when maximized geometry is full screen geometry, then do it only if not in maximized
            BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_WINDOW_GEOMETRY,
                           [self.geometry().x(),
                            self.geometry().y(),
                            self.geometry().width(),
                            self.geometry().height()])

    def __viewWindowMaximized(self, maximized=False):
        """Set the window state"""
        if not isinstance(maximized, bool):
            raise EInvalidValue('Given `maximized` must be a <bool>')

        if maximized:
            # store current geometry now because after window is maximized, it's lost
            BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_WINDOW_GEOMETRY,
                           [self.geometry().x(),
                            self.geometry().y(),
                            self.geometry().width(),
                            self.geometry().height()])
            self.showMaximized()
        else:
            self.showNormal()

        return maximized

    def __viewWindowGeometry(self, geometry=[-1, -1, -1, -1]):
        """Set the window geometry

        Given `geometry` is a list [x,y,width,height] or a QRect()
        """
        if isinstance(geometry, QRect):
            geometry = [geometry.x(), geometry.y(), geometry.width(), geometry.height()]

        if not isinstance(geometry, list) or len(geometry) != 4:
            raise EInvalidValue('Given `geometry` must be a <list[x,y,w,h]>')

        rect = self.geometry()

        if geometry[0] >= 0:
            rect.setX(geometry[0])

        if geometry[1] >= 0:
            rect.setY(geometry[1])

        if geometry[2] >= 0:
            rect.setWidth(geometry[2])

        if geometry[3] >= 0:
            rect.setHeight(geometry[3])

        self.setGeometry(rect)

        return [self.geometry().x(), self.geometry().y(), self.geometry().width(), self.geometry().height()]

    def __visualFormulaEditor(self):
        """Open visual formula editor"""
        BCRenameFileVisualFormulaEditorDialogBox.open(i18n(f"{self.__title}::Visual Formula Editor"), self.cePattern)

    def __cePatternContextMenu(self, standardMenu):
        """Build context menu of editor"""
        def __insertLanguageAction(menu, autoCompletion):
            """Create action for Language menu

            Title = autoCompletion
            Action = insert autoCompletion
            """
            def onExecute(dummy=None):
                self.cePattern.insertLanguageText(self.sender().property('insert'), self.sender().parentWidget() == menuKeywords)
                self.cePattern.setFocus()

            # print(autoCompletion[0])
            action = WMenuForCommand(html.escape(autoCompletion[0]), autoCompletion[1], menu)
            action.setProperty('insert', autoCompletion[0])
            if len(autoCompletion) > 1 and isinstance(autoCompletion[1], str):
                tip = TokenizerRule.descriptionExtractSection(autoCompletion[1], 'title')
                if tip == '':
                    tip = autoCompletion[1]
                action.setStatusTip(stripHtml(tip))

            action.triggered.connect(onExecute)
            menu.addAction(action)

        menuFunctions = buildQMenu('pktk:text_function', i18n('Functions'), standardMenu)
        menuKeywords = buildQMenu('pktk:text_keyword', i18n('Keywords'), standardMenu)

        standardMenu.addSeparator()
        standardMenu.addMenu(menuFunctions)
        standardMenu.addMenu(menuKeywords)

        for rule in self.__fileManipulateNameLanguageDef.tokenizer().rules():
            if rule.type() in (BCFileManipulateNameLanguageDef.ITokenType.KW,
                               BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR,
                               BCFileManipulateNameLanguageDef.ITokenType.FUNCO_INT):

                if rule.type() == BCFileManipulateNameLanguageDef.ITokenType.KW:
                    menu = menuKeywords
                else:
                    menu = menuFunctions

                for autoCompletion in rule.autoCompletion():
                    __insertLanguageAction(menu, autoCompletion)

    def __patternChanged(self):
        """Pattern has been modified, update renamed files in list"""
        selectedErrors = []
        newFileName = BCFileManipulateName.calculateFileName(self.__fileList[0], self.cePattern.toPlainText(), checkOnly=True)
        if newFileName[1] is not None:
            # !!!!
            # !!!! error during formula evaluation (BCFileManipulateNameErrorDefinition)
            # !!!!
            token = newFileName[1].token()
            # print(token, newFileName[1].message())

            if token is not None:
                cursor = self.cePattern.textCursor()

                # define cursor from token, to highlight error
                cursor.setPosition(token.positionStart(), QTextCursor.MoveAnchor)
                cursor.setPosition(token.positionEnd(), QTextCursor.KeepAnchor)

                # define extra selection to append to editor
                extraSelection = QTextEdit.ExtraSelection()
                extraSelection.cursor = cursor
                extraSelection.format.setBackground(QBrush(QColor('#88ff0000')))

                selectedErrors.append(extraSelection)

            self.lblError.setText(newFileName[1].message())
            self.lblError.setVisible(True)
            # disable access to visual formula editor as it won't be possible to properly rebuild nodes
            self.tbVisualFormulaEditor.setEnabled(False)
        elif self.cePattern.toPlainText() == self.__defaultPattern:
            # error...
            self.lblError.setText(i18n(f"Note: can't rename {self.__labelPlural} when source name is identical to target name"))
            self.lblError.setVisible(True)
            self.tbVisualFormulaEditor.setEnabled(True)
        else:
            self.lblError.setText('')
            self.lblError.setVisible(False)
            self.tbVisualFormulaEditor.setEnabled(True)
        self.cePattern.setExtraSelections(selectedErrors)
        self.__updateFilesFromListView()
        self.__updateNbFilesLabelAndBtnOk()
        self.__setModified(True)

    def __showPathChanged(self, value):
        self.__header.setSectionHidden(0, (not value))

    def __getNewFileName(self, file, pattern):
        newFileName = BCFileManipulateName.calculateFileName(file, pattern)
        if not newFileName[1] is None:
            # error
            return i18n('Invalid renaming pattern')
        else:
            return newFileName[0]

    def __addFileToListView(self, file):
        newRow = [
                QStandardItem(''),
                QStandardItem(''),
                QStandardItem('')
            ]

        newRow[0].setText(file.path())
        newRow[1].setText(file.name())
        newRow[1].setData(file, BCFileOperationMassRenameUi.FILEDATA)
        newRow[2].setText(self.__getNewFileName(file, self.cePattern.toPlainText()))

        self.__model.appendRow(newRow)

    def __updateFilesFromListView(self):
        pattern = self.cePattern.toPlainText()
        for row in range(self.__model.rowCount()):
            item = self.__model.item(row, 2)
            item.setText(self.__getNewFileName(self.__model.item(row, 1).data(BCFileOperationMassRenameUi.FILEDATA), pattern))

        self.tvResultPreview.resizeColumnToContents(2)

    def __updateNbFilesLabelAndBtnOk(self, dummy=None):
        toProcess = self.__nbFiles
        textExcluded = ''
        nbExcluded = 0
        if self.cbExcludeSelected.isChecked():
            nbExcluded = len(self.tvResultPreview.selectionModel().selectedRows())
            toProcess -= nbExcluded
            textExcluded = i18n(f', {nbExcluded} excluded')

        text = i18n(f'{toProcess} to rename')+textExcluded

        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled((toProcess > 0) and not self.lblError.isVisible())

        self.lblNbFiles.setText(text)

    def __selectionChanged(self, selected=None, deselected=None):
        if self.cbExcludeSelected.isChecked():
            self.__updateNbFilesLabelAndBtnOk()

    def __updateFileNameLabel(self):
        """Update file name in status bar according to current state"""
        modified = ''
        if self.__isModified:
            modified = f" ({i18n('modified')})"

        if self.__currentLoadedConfigurationFile is None or self.__currentLoadedConfigurationFile == '':
            self.lblFormulaDefinitionFileName.setText(f"")
        else:
            self.lblFormulaDefinitionFileName.setText(f"{self.__currentLoadedConfigurationFile}{modified}")

    def __setModified(self, value):
        """Set if rename formula definition has been modified"""
        if self.__isModified != value:
            self.__isModified = value
            self.__updateFileNameLabel()

    def __saveFormulaDefinitionFile(self, fileName):
        """Save formula definition to defined `fileName`"""
        toExport = {
                "extraData": {
                    "contentDescription": "",
                    "formula": self.cePattern.toPlainText()
                },
                "formatIdentifier": "bulicommander-rename-formula-definition"
            }

        returned = BCFileOperationMassRenameUi.EXPORT_OK
        try:
            with open(fileName, 'w') as fHandle:
                fHandle.write(json.dumps(toExport, indent=4, sort_keys=True, cls=JsonQObjectEncoder))
        except Exception as e:
            Debug.print("Can't save file {0}: {1}", fileName, f"{e}")
            returned = BCFileOperationMassRenameUi.EXPORT_CANT_SAVE

        BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_LASTFILE, fileName)
        self.__currentLoadedConfigurationFile = fileName
        self.__setModified(False)
        self.__updateFileNameLabel()

        return returned

    def __openFormulaDefinitionFile(self, fileName):
        """Open & load formula definition defined by `fileName`"""
        if self.__isModified:
            if not WDialogBooleanInput.display(self.__title, i18n("Current formula definition has been modified and will be lost, continue?")):
                return False

        try:
            with open(fileName, 'r') as fHandle:
                jsonAsStr = fHandle.read()
        except Exception as e:
            Debug.print("Can't open/read file {0}: {1}", fileName, f"{e}")
            return BCFileOperationMassRenameUi.IMPORT_FILE_CANT_READ

        try:
            jsonAsDict = json.loads(jsonAsStr, cls=JsonQObjectDecoder)
        except Exception as e:
            Debug.print("Can't parse file {0}: {1}", fileName, f"{e}")
            return BCFileOperationMassRenameUi.IMPORT_FILE_NOT_JSON

        if "formatIdentifier" not in jsonAsDict:
            Debug.print("Missing format identifier file {0}", fileName)
            return BCFileOperationMassRenameUi.IMPORT_FILE_MISSING_FORMAT_IDENTIFIER

        if jsonAsDict["formatIdentifier"] not in ("bulicommander-rename-formula-definition", "bulicommander-rename-formula-definition-n"):
            Debug.print("Invalid format identifier file {0}", fileName)
            return BCFileOperationMassRenameUi.IMPORT_FILE_INVALID_FORMAT_IDENTIFIER

        # from here, consider that file format is correct
        self.cePattern.setPlainText(jsonAsDict['extraData']['formula'])

        BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_LASTFILE, fileName)
        self.__currentLoadedConfigurationFile = fileName
        self.__setModified(False)

    def __newFormulaDefinition(self):
        """Reset formula"""
        if self.__isModified:
            if not WDialogBooleanInput.display(self.__title, i18n("Current rename formula definition has been modified and will be lost, continue?")):
                return False

        self.cePattern.setPlainText(self.__defaultPattern)
        self.__currentLoadedConfigurationFile = ''
        self.__setModified(False)

    def closeEvent(self, event):
        """Dialog is closed"""
        self.__saveSettings()
        event.accept()

    def openFile(self, fileName=None):
        """Open file designed by `fileName`

        If fileName is None, open dialog box with predefined last opened/saved file
        """
        if fileName is None:
            fileName = BCSettings.get(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_LASTFILE)

        if fileName is None:
            fileName = ''

        title = i18n(f"{self.__title}::{i18n('Open rename formula definition')}")
        extension = i18n("BuliCommander Rename Formula (*.bcrf)")

        fileName, dummy = QFileDialog.getOpenFileName(self, title, fileName, extension)

        if fileName != '':
            fileName = os.path.normpath(fileName)
            if not os.path.isfile(fileName):
                openResult = BCFileOperationMassRenameUi.IMPORT_FILE_NOT_FOUND
            else:
                openResult = self.__openFormulaDefinitionFile(fileName)

            if openResult == BCFileOperationMassRenameUi.IMPORT_OK:
                return True
            elif openResult == BCFileOperationMassRenameUi.IMPORT_FILE_NOT_FOUND:
                WDialogMessage.display(title, "<br>".join(
                                                        [i18n("<h1>Can't open file!</h1>"),
                                                         i18n("File not found!"),
                                                         ]))
            elif openResult == BCFileOperationMassRenameUi.IMPORT_FILE_CANT_READ:
                WDialogMessage.display(title, "<br>".join(
                                                        [i18n("<h1>Can't open file!</h1>"),
                                                         i18n("File can't be read!"),
                                                         ]))
            elif openResult == BCFileOperationMassRenameUi.IMPORT_FILE_NOT_JSON:
                WDialogMessage.display(title, "<br>".join(
                                                        [i18n("<h1>Can't open file!</h1>"),
                                                         i18n("Invalid file format!"),
                                                         ]))

            BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_LASTFILE, fileName)

        return False

    def saveFile(self, saveAs=False, fileName=None):
        """Save current rename formula to designed file name"""
        if fileName is None and self.__currentLoadedConfigurationFile != '':
            # a file is currently opened
            fileName = self.__currentLoadedConfigurationFile
        else:
            fileName = BCSettings.get(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_LASTFILE)
            saveAs = True

        if fileName is None:
            fileName = ''
            saveAs = True

        title = i18n(f"{self.__title}::{i18n('Save rename formula definition')}")
        extension = i18n("BuliCommander Rename Formula (*.bcrf)")

        if saveAs:
            fileName, dummy = QFileDialog.getSaveFileName(self, title, fileName, extension)
            if re.search(r"\.bcrf$", fileName) is None:
                fileName += ".bcrf"

        if fileName != '':
            fileName = os.path.normpath(fileName)
            saveResult = self.__saveFormulaDefinitionFile(fileName)

            BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_EDITOR_LASTFILE, fileName)

            if saveResult == BCFileOperationMassRenameUi.EXPORT_OK:
                return True
            elif saveResult == BCFileOperationMassRenameUi.EXPORT_CANT_SAVE:
                WDialogMessage.display(title, i18n("<h1>Can't save file!</h1>"))

        return False

    def returnedValue(self):
        returned = []

        if self.cbExcludeSelected.isChecked():
            for row in range(self.__model.rowCount()):
                item = self.__model.item(row, 1)
                if not self.tvResultPreview.selectionModel().isSelected(item.index()):
                    returned.append(item.data(BCFileOperationMassRenameUi.FILEDATA))
        else:
            returned = self.__fileList

        return {
                'files': returned,
                'rule': self.cePattern.toPlainText()
            }


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
            message += f" {nbFiles} file"
            if nbFiles > 1:
                message += "s"

        if nbDirectories > 0 and nbFiles > 0:
            message += ' and'

        if nbDirectories > 0:
            message += f" {nbDirectories} directories"
            if nbDirectories > 1:
                message += "ies"
            else:
                message += "y"
        return message

    @staticmethod
    def __dialogFileOperation(action, nbFiles, nbDirectories, fileList, message2=None, targetPath=None, message3=None):
        """Initialise default file dialog for delete/copy/move"""
        def pathChanged(value):
            BCFileOperationUi.__targetPath = dlgMain.frameBreacrumbPath.path()

        def showEvent(event):
            """Event trigerred when dialog is shown"""
            if dlgMain._oldShowEvent is not None:
                dlgMain._oldShowEvent()
            # need to set AFTER dialog is visible, otherwise there's a strange bug...
            dlgMain.frameBreacrumbPath.setPath(dlgMain.__targetPath)

        def deepDirAnalysis():
            dlgMain.pbOk.setEnabled(False)
            dlgMain.pbCancel.setEnabled(False)
            dlgMain.pbDeepDirAnalysis.setEnabled(False)

            informations = BCFileOperationUi.buildInformation(fileList, True)

            dlgMain.lblMessage.setText(informations['info']['short'])
            dlgMain.teInfo.setHtml(header+"<p style = 'font-family: consolas, monospace;'>"+informations['info']['full']+"</p>")

            dlgMain.pbDeepDirAnalysis.setVisible(False)

            dlgMain.pbOk.setEnabled(True)
            dlgMain.pbCancel.setEnabled(True)

        def haveSubItems():
            for item in fileList:
                if isinstance(item, BCDirectory) and not item.isEmpty():
                    return True
            return False

        informations = BCFileOperationUi.buildInformation(fileList, False)

        header = ''
        if action == 'Delete':
            header = i18n('<h2>Please confirm deletion</h2>')
            if haveSubItems():
                header += "<p><table><tr><td valign = middle width = 48>"\
                          "<img width = 32 height = 32 src = ':/pktk/images/normal/warning'/></td><td><span style = 'margin-left: 16px; font-style: italic;'>"
                header += i18n("Warning: some directories are not empty!")
                header += "<br>"+i18n("Please execute <b>Sub-directories analysis</b> to check content before deletion") + "</span></td></tr></table></p>"
            translatedAction = i18n('Delete')
        elif action == 'Copy':
            header = i18n('<h2>Please confirm copy</h2>')
            translatedAction = i18n('Copy')
        elif action == 'Move':
            header = i18n('<h2>Please confirm move</h2>')
            translatedAction = i18n('Move')
        else:
            translatedAction = action

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcfileoperation.ui')
        dlgMain = PyQt5.uic.loadUi(uiFileName)
        dlgMain._oldShowEvent = dlgMain.showEvent

        dlgMain.lblMessage.setText(informations['info']['short'])
        dlgMain.teInfo.setHtml(header+"<p style = 'font-family: consolas, monospace;'>"+informations['info']['full']+"</p>")

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
        else:
            dlgMain.pbDeepDirAnalysis.setVisible(haveSubItems())

        dlgMain.pbOk.setText(translatedAction)

        dlgMain.pbOk.clicked.connect(dlgMain.accept)
        dlgMain.pbCancel.clicked.connect(dlgMain.reject)
        dlgMain.pbDeepDirAnalysis.clicked.connect(deepDirAnalysis)

        return dlgMain

    @staticmethod
    def __dialogFileExists(action, fileSrc, fileTgt, nbFiles=0):
        """Initialise default file dialog for existing files"""
        def action_rename(dummy):
            dlgMain.__action = BCFileOperationUi.FILEEXISTS_RENAME
            dlgMain.__renamed = dlgMain.cbxNewName.currentText()
            dlgMain.__applyToAll = dlgMain.cbApplyToAll.isChecked()
            dlgMain.accept()

        def action_skip(dummy):
            dlgMain.__action = BCFileOperationUi.FILEEXISTS_SKIP
            dlgMain.__applyToAll = dlgMain.cbApplyToAll.isChecked()
            dlgMain.accept()

        def action_overwrite(dummy):
            dlgMain.__action = BCFileOperationUi.FILEEXISTS_OVERWRITE
            dlgMain.__applyToAll = dlgMain.cbApplyToAll.isChecked()
            dlgMain.accept()

        def action_abort(dummy):
            dlgMain.__action = BCFileOperationUi.FILEEXISTS_ABORT
            dlgMain.reject()

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcfileexists.ui')
        dlgMain = PyQt5.uic.loadUi(uiFileName)

        if isinstance(fileSrc, str):
            if os.path.isfile(fileSrc):
                fileSrc = BCFile(fileSrc)
            elif os.path.isdir(fileSrc):
                fileSrc = BCDirectory(fileSrc)
            else:
                raise EInvalidValue("Given `fileSrc` is not a valid file/directory")
        elif not isinstance(fileSrc, BCBaseFile):
            raise EInvalidValue("Given `fileSrc` is not a valid <str> or <BCBaseFile>")

        if isinstance(fileTgt, str):
            if os.path.isfile(fileTgt):
                fileTgt = BCFile(fileTgt)
            elif os.path.isdir(fileTgt):
                fileTgt = BCDirectory(fileTgt)
            else:
                raise EInvalidValue("Given `fileTgt` is not a valid file/directory")
        elif not isinstance(fileTgt, BCBaseFile):
            raise EInvalidValue("Given `fileTgt` is not a valid <str> or <BCBaseFile>")

        dlgMain.lblActionDesc.setText(f"{action} <font face = 'monospace'><b>{fileSrc.name()}</b></font> from:")
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
                i18n('{file:baseName}-Copy {date}-{time}.{file:ext}')
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

        dlgMain.cbApplyToAll.setVisible(nbFiles > 1)

        return dlgMain

    @staticmethod
    def __dialogFileRenameSingle(fileList):
        """Initialise default file dialog for single file rename"""
        def pathChanged(value):
            dlgMain.buttonBox.button(QDialogButtonBox.Ok).setEnabled(not (value.strip() == '' or value.strip() == sourceFileName))

        def returnedValue():
            return {
                    'files': [fileList[0]],
                    'rule': dlgMain.leNewFileName.text()
                }

        if fileList[0].format() == BCFileManagedFormat.DIRECTORY:
            label = i18n('directory')
        else:
            label = i18n('file')

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcrenamefile_single.ui')
        dlgMain = PyQt5.uic.loadUi(uiFileName)

        sourceFileName = fileList[0].name()

        dlgMain.leCurrentPathFileName.setText(fileList[0].fullPathName())
        dlgMain.leNewFileName.setText(sourceFileName)
        dlgMain.leNewFileName.textChanged.connect(pathChanged)

        dlgMain.lblCurrentName.setText(i18n(f'Current {label} name'))
        dlgMain.lblNewName.setText(i18n(f'New {label} name'))

        dlgMain.buttonBox.accepted.connect(dlgMain.accept)
        dlgMain.buttonBox.rejected.connect(dlgMain.reject)
        dlgMain.returnedValue = returnedValue

        pathChanged(sourceFileName)

        return dlgMain

    @staticmethod
    def buildInformation(fileList, full=False):
        """Build text information from given list of BCBaseFile"""
        QApplication.setOverrideCursor(Qt.WaitCursor)

        fullNfo = []
        files = sorted(fileList, key=cmp_to_key(BCBaseFile.fullPathNameCmpAsc))

        statFiles = {
                'nbKra': 0,
                'nbOther': 0,
                'sizeKra': 0,
                'sizeOther': 0,
                'nbDir': 0,
                'nbTotal': 0

            }

        # ----------------------------------------------------------------------
        # Display total number of file (+size) including sub-directories
        # Improve BCFileList class to generate statistics ready-to-use about returned results (number of directories, nb files+size, nb non kra file+size)
        for file in files:
            if file.format() == BCFileManagedFormat.DIRECTORY:
                fullNfo.append(f"<img width = 16 height = 16 src = ':/pktk/images/normal/folder_open'/>&nbsp;{file.fullPathName()}")
                if full:
                    # build informations about directory content
                    pathFileList = BCFileList()
                    pathFileList.addSearchPaths(BCFileListPath(file.fullPathName(), True, True))
                    pathFileList.searchSetIncludeDirectories(True)
                    pathFileList.searchExecute(True, True)  # build stats

                    stats = pathFileList.stats()
                    for key in stats:
                        statFiles[key] += stats[key]

                    if stats['nbKra'] > 0 or stats['nbOther'] > 0 or stats['nbDir'] > 0:
                        nfo = ["""<span style = " font-family:'consolas, monospace'; font-size:9pt; font-style:italic;">&nbsp;&nbsp;&gt;&nbsp;""" +
                               i18n("Directory contains:")+"</span>"]
                        if stats['nbDir'] > 0:
                            nfo.append(f"""<span style = "margin-left: 40px; font-family:'consolas, monospace'; font-size:9pt; font-style:italic;">&nbsp;&nbsp;&nbsp;&nbsp;. """
                                       + i18n("Sub-directories:")+f" {stats['nbDir']}</span>")
                        if stats['nbKra'] > 0:
                            nfo.append(f"""<span style = "margin-left: 40px; font-family:'consolas, monospace'; font-size:9pt; font-style:italic;">&nbsp;&nbsp;&nbsp;&nbsp;. """
                                       + i18n("Image files:")+f" {stats['nbKra']} ({bytesSizeToStr(stats['sizeKra'])})</span>")
                        if stats['nbOther'] > 0:
                            nfo.append(f"""<span style = "margin-left: 40px; font-family:'consolas, monospace'; font-size:9pt; font-style:italic;">&nbsp;&nbsp;&nbsp;&nbsp;. """
                                       + i18n("Other files:")+f" {stats['nbOther']} ({bytesSizeToStr(stats['sizeOther'])})</span>")

                        fullNfo.append("<br/>".join(nfo))
                statFiles['nbDir'] += 1
            elif file.format() == BCFileManagedFormat.UNKNOWN:
                fullNfo.append(f"<img width = 16 height = 16 src = ':/pktk/images/normal/file'/>&nbsp;{file.fullPathName()}")
                statFiles['nbOther'] += 1
                statFiles['sizeOther'] += file.size()
            else:
                fullNfo.append(f"<img width = 16 height = 16 src = ':/pktk/images/normal/image'/>&nbsp;{file.fullPathName()}")
                statFiles['nbKra'] += 1
                statFiles['sizeKra'] += file.size()

        shortNfo = []
        if statFiles['nbDir'] > 0:
            shortNfo.append(i18n("Directories: ")+f"{statFiles['nbDir']}")
        if statFiles['nbKra'] > 0:
            shortNfo.append(i18n("Image files: ")+f"{statFiles['nbKra']} ({bytesSizeToStr(statFiles['sizeKra'])})")
        if statFiles['nbOther'] > 0:
            shortNfo.append(i18n("Other files: ")+f"{statFiles['nbOther']} ({bytesSizeToStr(statFiles['sizeOther'])})")

        statFiles['nbTotal'] = statFiles['nbKra']+statFiles['nbOther']+statFiles['nbDir']

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
        db.setWindowTitle(i18n(f"{title}::Delete files"))
        return db.exec()

    @staticmethod
    def copy(title, nbFiles, nbDirectories, fileList, targetPath):
        """Open dialog box"""
        db = BCFileOperationUi.__dialogFileOperation('Copy', nbFiles, nbDirectories, fileList, "To", targetPath)
        db.setWindowTitle(i18n(f"{title}::Copy files"))
        return db.exec()

    @staticmethod
    def move(title, nbFiles, nbDirectories, fileList, targetPath):
        """Open dialog box"""
        db = BCFileOperationUi.__dialogFileOperation('Move', nbFiles, nbDirectories, fileList, "To", targetPath)
        db.setWindowTitle(i18n(f"{title}::Move files"))
        return db.exec()

    @staticmethod
    def createDir(title, targetPath):
        """Open dialog box to create a new directory"""

        value = WDialogStrInput.display(i18n(f"{title}::Create directory"),
                                        i18n(f"""<h2>Create a new directory</h2>"""
                                             f"""<p>Directory will be created into <span style = "font-family:'consolas, monospace'; font-weight:bold; white-space: nowrap;">"""
                                             f"""{targetPath}</span></p>"""),
                                        i18n("Please provide name for new directory"),
                                        i18n('New directory'),
                                        r'^[^\\/<>?:"*|]+$')
        if value is not None:
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
            if fileList[0].format() == BCFileManagedFormat.DIRECTORY:
                label = i18n('directory')
            else:
                label = i18n('file')
            db = BCFileOperationUi.__dialogFileRenameSingle(fileList)
            db.setWindowTitle(i18n(f"{title}::Rename {label}"))
            if db.exec():
                return db.returnedValue()
        else:
            if fileList[0].format() == BCFileManagedFormat.DIRECTORY:
                label = i18n('directories')
            else:
                label = i18n('files')
            db = BCFileOperationMassRenameUi(i18n(f"{title}::Rename {label}"), fileList)
            if db.exec():
                return db.returnedValue()

        return None

    @staticmethod
    def fileExists(title, action, fileSrc, fileTgt, nbFiles=0):
        """Open dialog box to ask action on existing file"""
        db = BCFileOperationUi.__dialogFileExists(action, fileSrc, fileTgt, nbFiles)
        db.setWindowTitle(i18n(f"{title}::{action} files"))
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

    __PROGRESS_Time = 0

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

        BCFileOperation.__PROGRESS_Time = time.time_ns()
        QApplication.instance().processEvents()

    @staticmethod
    def __hideProgressBar():
        """Hide progress dialog bar"""
        BCFileOperation.__PROGRESS.accept()
        BCFileOperation.__PROGRESS = None

    @staticmethod
    def __progressBarNext(fileName, fileSize):
        """Update progress bar"""
        if BCFileOperation.__PROGRESS is not None:
            BCFileOperation.__PROGRESS_currentStep += 1
            BCFileOperation.__PROGRESS_currentBytes += fileSize

            if BCFileOperation.__PROGRESS_totalBytes > 0:
                nbBytes = round(10000*BCFileOperation.__PROGRESS_currentBytes / BCFileOperation.__PROGRESS_totalBytes)
            else:
                nbBytes = 0

            BCFileOperation.__PROGRESS.lblCurrentFile.setText(fileName)
            BCFileOperation.__PROGRESS.lblProcessedFiles.setText(f'{BCFileOperation.__PROGRESS_currentStep}/{BCFileOperation.__PROGRESS_totalFiles}')
            BCFileOperation.__PROGRESS.lblProcessedBytes.setText(f'{bytesSizeToStr(BCFileOperation.__PROGRESS_currentBytes)}/{BCFileOperation.__PROGRESS_totalBytesStr}')

            BCFileOperation.__PROGRESS.pbProcessedFiles.setValue(BCFileOperation.__PROGRESS_currentStep)
            BCFileOperation.__PROGRESS.pbProcessedBytes.setValue(nbBytes)

            if time.time_ns() - BCFileOperation.__PROGRESS_Time >= 150000000:
                # can't update on each file processed: this slow down copy/move/delete drastically
                # refresh progress bar every 100ms (100000000ns)
                QApplication.instance().processEvents()
                BCFileOperation.__PROGRESS_Time = time.time_ns()

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

        # According to mode, define terms to use for user information
        if mode == 'copy':
            modeMaj = i18n('Copy')
            modeEd = i18n('copied')
        else:
            modeMaj = i18n('Move')
            modeEd = i18n('moved')

        # define default action to apply if file/path already exists
        # note: for RENAME, it will always stay to FILEEXISTS_ASK (control is made
        #       on newFilePattern/newDirPattern content)
        actionOnFileExist = BCFileOperationUi.FILEEXISTS_ASK
        actionOnPathExist = BCFileOperationUi.FILEEXISTS_ASK

        # pattern to apply for automatic RENAME action
        newFilePattern = None
        newDirPattern = None

        # number of processed/error file
        processed = None
        inError = 0

        targetPath = targetPath.rstrip(os.sep)

        # initialise process:
        # - calculate total size to copy/move (in bytes)
        # - determinate target path for file/dir to process
        files = []
        index = 0
        totalSize = 0
        pathsList = {}
        for file in srcFiles:
            if file.format() != BCFileManagedFormat.DIRECTORY:
                totalSize += file.size()
            else:
                pathsList[file.fullPathName()] = file.name()
            file.setTag('newPath', targetPath)
            files.append(file)
            index += 1

        if len(pathsList) > 0:
            # there's some directory to process
            # in this case, search all sub-directories & files and continue to feed list of items to process
            for srcPath in pathsList:
                fileList = BCFileList()
                fileList.addSearchPaths(BCFileListPath(srcPath, True, True))
                fileList.searchSetIncludeDirectories(True)
                fileList.searchExecute()
                srcPath = os.path.dirname(srcPath)
                for file in fileList.files():
                    file.setTag('newPath', os.path.join(targetPath, file.path().replace(srcPath, '').strip(os.sep)))
                    files.append(file)
                    totalSize += file.size()

        # ascending sort
        files = sorted(files, key=cmp_to_key(BCBaseFile.fullPathNameCmpAsc))
        # path list, descending sort
        paths = sorted([file for file in files if file.format() == BCFileManagedFormat.DIRECTORY], key=cmp_to_key(BCBaseFile.fullPathNameCmpDesc))

        QApplication.restoreOverrideCursor()
        QApplication.setOverrideCursor(Qt.BusyCursor)
        BCFileOperation.__showProgressBar(i18n(f"{title}::{modeMaj} files"), len(files), totalSize)

        for file in files:
            isDir = False
            if file.format() == BCFileManagedFormat.DIRECTORY:
                BCFileOperation.__progressBarNext(file.fullPathName(), 0)
                isDir = True
            else:
                BCFileOperation.__progressBarNext(file.fullPathName(), file.size())

            # determinate new target full path name
            targetFile = os.path.join(file.tag('newPath'), file.name())

            actionToApply = BCFileOperationUi.FILEEXISTS_OVERWRITE

            while os.path.exists(targetFile):
                # the target file already exists..

                if isDir and newDirPattern is not None:
                    # current directory exist AND a rename pattern exist for directories
                    #  => means that we try to rename directory automatically
                    currentTarget = targetFile
                    targetFile = os.path.join(file.tag('newPath'), BCFileManipulateName.parseFileNameKw(BCDirectory(targetFile), newDirPattern))

                    if not os.path.exists(targetFile):
                        # ok new name is valid, doesn't exist
                        # need to modify all file designed to be processed into the new directory
                        for fileToUpdate in files:
                            if currentTarget in fileToUpdate.tag('newPath'):
                                fileToUpdate.setTag('newPath', fileToUpdate.tag('newPath').replace(currentTarget, targetFile))

                    if not os.path.exists(targetFile):
                        # ok new name is valid, doesn't exist
                        # need to modify all file designed to be processed into the new directory
                        for fileToUpdate in files:
                            if fileToUpdate.tag('newPath') == currentTarget:
                                fileToUpdate.setTag('newPath', targetFile)
                        break
                elif not isDir and newFilePattern is not None:
                    # current file exist AND a rename pattern exist for files
                    #  => means that we try to rename file automatically
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
                        processed = BCFileOperation.__value() - 1
                        break
                    elif action[0] == BCFileOperationUi.FILEEXISTS_RENAME:
                        # rename file
                        currentTarget = targetFile
                        if isDir:
                            targetFile = os.path.join(os.path.dirname(targetFile),
                                                      BCFileManipulateName.parseFileNameKw(BCDirectory(targetFile), re.sub(r"(?i)\{file:(?:path|name)\}", '', action[1])))
                        else:
                            targetFile = os.path.join(os.path.dirname(targetFile),
                                                      BCFileManipulateName.parseFileNameKw(BCFile(targetFile), re.sub(r"(?i)\{file:(?:path|name)\}", '', action[1])))
                        actionToApply = BCFileOperationUi.FILEEXISTS_RENAME

                        if isDir and not os.path.exists(targetFile):
                            # need to modify all file designed to be processed into the new directory
                            # do it only if new target not exists
                            for fileToUpdate in files:
                                if currentTarget in fileToUpdate.tag('newPath'):
                                    fileToUpdate.setTag('newPath', fileToUpdate.tag('newPath').replace(currentTarget, targetFile))

                        # apply to all
                        if action[2]:
                            if isDir:
                                newDirPattern = re.sub(r"(?i)\{file:(?:path|name)\}", '', action[1])
                            else:
                                newFilePattern = re.sub(r"(?i)\{file:(?:path|name)\}", '', action[1])

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
                processed = BCFileOperation.__value() - 1
                break
            elif actionToApply == BCFileOperationUi.FILEEXISTS_SKIP:
                continue
            elif isDir:
                try:
                    os.makedirs(targetFile, exist_ok=True)
                except Exception as e:
                    inError += 1
                    Debug.print('[BCFileOperation.__copyOrMove] Unable to {3} file from {0} to {1}: {2}', file.fullPathName(), targetFile, f"{e}", mode)
            elif not isDir:
                try:
                    targetPath = os.path.dirname(targetFile)
                    os.makedirs(targetPath, exist_ok=True)

                    if mode == 'copy':
                        shutil.copy2(file.fullPathName(), targetFile)
                    else:
                        shutil.move(file.fullPathName(), targetFile)
                except Exception as e:
                    inError += 1
                    Debug.print('[BCFileOperation.__copyOrMove] Unable to {3} file from {0} to {1}: {2}', file.fullPathName(), targetFile, f"{e}", mode)

            if BCFileOperation.__isCancelled():
                break

        if processed is None:
            processed = BCFileOperation.__value()

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

        if inError > 0:
            BCSysTray.messageCritical(
                i18n(f"{title}::{modeMaj} files"),
                i18n(f"{modeMaj} process has been finished with errors\n\n<i>Items not {modeEd}: <b>{inError}</b> of <b>{len(files)}</b></i>")
            )

        if processed != len(files):
            BCSysTray.messageWarning(
                i18n(f"{title}::{modeMaj} files"),
                i18n(f"{modeMaj} process has been cancelled\n\n<i>Items {modeEd} before action has been cancelled: <b>{processed - inError}</b> of <b>{len(files)}</b></i>")
            )
        elif inError == 0:
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

        QApplication.setOverrideCursor(Qt.WaitCursor)

        # cancelled = 0
        #   when cancelled > 0, it's the number of items processed
        cancelled = 0
        inError = 0

        totalSize = 0
        for file in files:
            if file.format() != BCFileManagedFormat.DIRECTORY:
                totalSize += file.size()

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
                inError += 1
                Debug.print('[BCFileOperation.delete] Unable to delete file {0}: {1}', file.fullPathName(), f"{e}")

            if BCFileOperation.__isCancelled():
                cancelled = BCFileOperation.__value()
                break

        BCFileOperation.__hideProgressBar()

        QApplication.restoreOverrideCursor()

        if cancelled > 0:
            BCSysTray.messageWarning(
                i18n(f"{title}::Delete files"),
                i18n(f"Deletion process has been cancelled\n\n<i>Items deleted before action has been cancelled: <b>{cancelled}</b> of <b>{len(files)}<b></i>")
            )
        if inError > 0:
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
    def createDir(title, path, createParent=True):
        """Create a new directory for given path

        Return True if file as heen created otherwise False
        """
        try:
            Path(path).mkdir(parents=createParent)
            return True
        except Exception as e:
            BCSysTray.messageCritical(
                i18n(f"{title}::Create directory"),
                i18n(f"Unable to create directory <b>{path}</b>")
            )
            return False

    @staticmethod
    def rename(title, files, renamePattern):
        """Rename file(s)

        Given `files` is a list of BCBaseFile
        """
        QApplication.setOverrideCursor(Qt.WaitCursor)

        actionOnFileExist = BCFileOperationUi.FILEEXISTS_ASK

        # cancelled = 0
        #   when cancelled > 0, it's the number of items processed
        cancelled = 0
        inError = 0
        processed = None

        totalFiles = len(files)
        totalSize = 0
        for file in files:
            totalSize += file.size()

        QApplication.restoreOverrideCursor()
        QApplication.setOverrideCursor(Qt.BusyCursor)

        if totalFiles > 0:
            BCFileOperation.__showProgressBar(i18n(f"{title}::Rename files"), len(files), totalSize)

        for file in files:
            if totalFiles > 0:
                BCFileOperation.__progressBarNext(file.fullPathName(), file.size())

            # determinate new target full path name
            newFileName = BCFileManipulateName.calculateFileName(file, renamePattern)
            if not newFileName[1] is None:
                inError += 1
                Debug.print('[BCFileOperation.rename] Unable to rename file {0}: {1}', file.fullPathName(), newFileName[1])
                continue
            targetFile = os.path.join(file.path(), newFileName[0])

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
                        processed = BCFileOperation.__value() - 1
                        break
                    elif action[0] == BCFileOperationUi.FILEEXISTS_RENAME:
                        # rename file
                        currentTarget = targetFile
                        targetFile = os.path.join(os.path.dirname(targetFile),
                                                  BCFileManipulateName.parseFileNameKw(BCFile(targetFile), re.sub(r"(?i)\{file:(?:path|name)\}", '', action[1])))
                        actionToApply = BCFileOperationUi.FILEEXISTS_RENAME

                        # apply to all
                        if action[2]:
                            newFilePattern = re.sub(r"(?i)\{file:(?:path|name)\}", '', action[1])

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
                processed = BCFileOperation.__value() - 1
                break
            elif actionToApply == BCFileOperationUi.FILEEXISTS_SKIP:
                continue
            else:
                try:
                    # print('rename', file.fullPathName(), targetFile)
                    os.rename(file.fullPathName(), targetFile)
                except Exception as e:
                    inError += 1
                    Debug.print('[BCFileOperation.rename] Unable to rename file from {0} to {1}: {2}', file.fullPathName(), targetFile, f"{e}")

            if BCFileOperation.__isCancelled():
                cancelled = BCFileOperation.__value()
                break

        if totalFiles > 0:
            BCFileOperation.__hideProgressBar()

        QApplication.restoreOverrideCursor()

        if cancelled > 0:
            BCSysTray.messageWarning(
                i18n(f"{title}::Rename files"),
                i18n(f"Renaming process has been cancelled\n\n<i>Items renamed before action has been cancelled: <b>{cancelled}</b> of <b>{totalFiles}<b></i>")
            )
        if inError > 0:
            BCSysTray.messageCritical(
                i18n(f"{title}::Rename files"),
                i18n(f"Renaming process has been finished with errors\n\n<i>Items not renamed: <b>{inError}</b> of <b>{totalFiles}</b></i>")
            )
        elif inError == 0 and cancelled == 0:
            BCSysTray.messageInformation(
                i18n(f"{title}::Rename files"),
                i18n(f"Renaming finished\n\n<i>Items renamed: <b>{totalFiles}</b></i>")
            )
