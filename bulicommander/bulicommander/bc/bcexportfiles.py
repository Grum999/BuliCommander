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

from .bcfile import (
        BCDirectory,
        BCFile,
        BCFileManagedFormat,
        BCFileProperty
    )
from .bcsystray import BCSysTray
from .bctable import (
        BCTable,
        BCTableSettingsText,
        BCTableSettingsTextCsv
    )
from .bcutils import (
        bytesSizeToStr,
        tsToStr,
        Debug
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# -----------------------------------------------------------------------------


class BCExportFormat(object):
    EXPORT_FMT_TEXT =           0
    EXPORT_FMT_TEXT_CSV =       1
    EXPORT_FMT_TEXT_MD =        2


class BCExportFilesDialogBox(QDialog):
    """User interface for export"""

    __PAGE_PERIMETER = 0
    __PAGE_FORMAT = 1
    __PAGE_TARGET = 2

    __PANEL_FORMAT_TEXT = 0
    __PANEL_FORMAT_TEXT_CSV = 1
    __PANEL_FORMAT_TEXT_MD = 2


    FMT_PROPERTIES = {
            BCExportFormat.EXPORT_FMT_TEXT:         {'description': i18n("Generate a basic text file, without any formatting<br>"
                                                                         "This file can be opened in any text editor; use a monospace font is highly recommended for a better readability"),
                                                     'clipboard': True,
                                                     'extensions': 'Text files (*.txt)'
                                                    },
            BCExportFormat.EXPORT_FMT_TEXT_CSV:     {'description': i18n("Generate a CSV file<br>"
                                                                         "This file can be opened in a spreadsheet software"),
                                                     'clipboard': True,
                                                     'extensions': 'CSV files (*.csv)'
                                                    },
            BCExportFormat.EXPORT_FMT_TEXT_MD:      {'description': i18n("Generate a Markdown file (<a href='https://guides.github.com/features/mastering-markdown'><span style='text-decoration: underline; color:#2980b9;'>GitHub flavored version</span></a>)<br>"
                                                                         "This file can be opened in any text editor, but use of a dedicated software to render result is recommended"),
                                                     'clipboard': True,
                                                     'extensions': 'Markdown files (*.md *.markdown)'
                                                    }
        }

    FIELDS = {
                                                    # label:        value displayed in listbox
                                                    # tooltip:      tooltip affected to item in list
                                                    # data:         data to return in exported result
                                                    # alignment:    for format that support colupmn alignment, define
                                                    #               data alignment (0: left / 1: right)
                                                    # selected:     default status in listbox
        'file.path':                                {'label':       i18n('Path'),
                                                     'toolTip':     i18n('The file path'),
                                                     'data':        '{file.path()}',
                                                     'alignment':   0,
                                                     'selected':    True
                                                    },
        'file.name':                                {'label':       i18n('File name'),
                                                     'toolTip':     i18n('The file name, including extension'),
                                                     'data':        '{file.name()}',
                                                     'alignment':   0,
                                                     'selected':    True
                                                    },
        'file.baseName':                            {'label':       i18n('File base name'),
                                                     'toolTip':     i18n('The file name, excluding extension'),
                                                     'data':        '{file.baseName() if not isinstance(file, BCDirectory) else file.name()}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'file.extension':                           {'label':       i18n('File extension'),
                                                     'toolTip':     i18n('The file extension, including dot separator)'),
                                                     'data':        '{file.extension() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'file.fullPathName':                        {'label':       i18n('Full path/file name'),
                                                     'toolTip':     i18n('The complete file name, including path'),
                                                     'data':        '{file.fullPathName()}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'file.format.short':                        {'label':       i18n('File format (short)'),
                                                     'toolTip':     i18n('The file format (short value)'),
                                                     'data':        '{BCFileManagedFormat.translate(file.format(), True)}',
                                                     'alignment':   0,
                                                     'selected':    True
                                                    },
        'file.format.long':                         {'label':       i18n('File format (long)'),
                                                     'toolTip':     i18n('The file format (long value)'),
                                                     'data':        '{BCFileManagedFormat.translate(file.format(), False)}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'modified.datetime':                        {'label':       i18n('Date/Time'),
                                                     'toolTip':     i18n('File date/time (<span style="font-family:''monospace''"><i>yyyy-mm-dd hh:mi:ss</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"dt")}',
                                                     'alignment':   0,
                                                     'selected':    True
                                                    },
        'modified.date.full':                       {'label':       i18n('Date'),
                                                     'toolTip':     i18n('File date (<span style="font-family:''monospace''"><i>yyyy-mm-dd</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"d")}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'modified.date.year':                       {'label':       i18n('Date (year)'),
                                                     'toolTip':     i18n('File date (<i>Year: <span style="font-family:''monospace''">yyyy</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%Y")}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'modified.date.month':                      {'label':       i18n('Date (month)'),
                                                     'toolTip':     i18n('File date (<i>Month: <span style="font-family:''monospace''">mm</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%m")}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'modified.date.day':                        {'label':       i18n('Date (day)'),
                                                     'toolTip':     i18n('File date (<i>Month: <span style="font-family:''monospace''">dd</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%d")}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'modified.time.full':                       {'label':       i18n('Time'),
                                                     'toolTip':     i18n('File time (<span style="font-family:''monospace''"><i>hh:mi:ss</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"t")}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'modified.time.hour':                       {'label':       i18n('Time (hour)'),
                                                     'toolTip':     i18n('File time (<i>Hour (H24): <span style="font-family:''monospace''">hh</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%H")}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'modified.time.minute':                     {'label':       i18n('Time (minutes)'),
                                                     'toolTip':     i18n('File time (<i>Minutes: <span style="font-family:''monospace''">mm</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%M")}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'modified.time.seconds':                    {'label':       i18n('Date (seconds)'),
                                                     'toolTip':     i18n('File time (<i>Seconds: <span style="font-family:''monospace''">ss</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%S")}',
                                                     'alignment':   0,
                                                     'selected':    False
                                                    },
        'size.bytes':                               {'label':       i18n('Size (bytes)'),
                                                     'toolTip':     i18n('File size in bytes'),
                                                     'data':        '{file.size() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'selected':    False
                                                    },
        'size.unit.decimal':                        {'label':       i18n('Size (best decimal unit)'),
                                                     'toolTip':     i18n('File size, using the best decimal unit (KB, MB, GB)<br/>Size is rounded to 2 decimals'),
                                                     'data':        '{bytesSizeToStr(file.size(), "auto") if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'selected':    False
                                                    },
        'size.unit.binary':                         {'label':       i18n('Size (best binary unit)'),
                                                     'toolTip':     i18n('File size, using the best binary unit (KiB, MiB, GiB)<br/>Size is rounded to 2 decimals'),
                                                     'data':        '{bytesSizeToStr(file.size(), "autobin") if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'selected':    True
                                                    },
        'image.size.full':                          {'label':       i18n('Image size (width x height)'),
                                                     'toolTip':     i18n('The current image size (<span style="font-family:''monospace''"></i>width</i>x<i>height</i></span>)'),
                                                     'data':        '{str(file.imageSize().width()) + "x" + str(file.imageSize().height()) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'selected':    True
                                                    },
        'image.size.width':                         {'label':       i18n('Image size (width)'),
                                                     'toolTip':     i18n('The current image size (width)'),
                                                     'data':        '{file.imageSize().width() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'selected':    False
                                                    },
        'image.size.height':                         {'label':      i18n('Image size (height)'),
                                                     'toolTip':     i18n('The current image size (height)'),
                                                     'data':        '{file.imageSize().height() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'selected':    False
                                                    }
    }


    def __init__(self, title, uicontroller, parent=None):
        super(BCExportFilesDialogBox, self).__init__(parent)

        self.__title = title
        self.__previewLimit = 20

        self.__fileNfo = []
        self.__fileNfo = []

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcexportfiles.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.setWindowTitle(self.__title)

        self.__uiController = uicontroller

        self.__initialise()


    def __initialise(self):
        """Initialise interface"""
        self.__initialisePagePerimeter()
        self.__initialisePageFormat()
        self.__initialisePageTarget()

        self.swPages.setCurrentIndex(BCExportFilesDialogBox.__PAGE_PERIMETER)

        self.pbPrevious.clicked.connect(self.__goPreviousPage)
        self.pbNext.clicked.connect(self.__goNextPage)
        self.pbCancel.clicked.connect(self.reject)
        self.pbExport.clicked.connect(self.__export)
        self.__updateBtn()


    def __initialisePagePerimeter(self):
        """Initialise interface widgets for page perimeter"""
        def checkAll():
            # check all properties
            for itemIndex in range(self.lwPerimeterProperties.count()):
                self.lwPerimeterProperties.item(itemIndex).setCheckState(Qt.Checked)

        def uncheckAll():
            # uncheck all properties
            for itemIndex in range(self.lwPerimeterProperties.count()):
                self.lwPerimeterProperties.item(itemIndex).setCheckState(Qt.Unchecked)


        def resetFields():
            # reset field list
            self.lwPerimeterProperties.clear()
            for field in BCExportFilesDialogBox.FIELDS:
                item = QListWidgetItem(BCExportFilesDialogBox.FIELDS[field]['label'])

                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if BCExportFilesDialogBox.FIELDS[field]['selected']:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                item.setData(1000, field)   # store field ID
                item.setToolTip(BCExportFilesDialogBox.FIELDS[field]['toolTip'])
                self.lwPerimeterProperties.addItem(item)

        resetFields()

        self.rbPerimeterSelectPath.setChecked(True)

        self.__fileNfo = self.__uiController.panel().files()
        self.lblPerimeterSelectPathNfo.setText(i18n(f"<b>{self.__uiController.panel().path()}</b> (Files: {self.__fileNfo[2]}, Directories: {self.__fileNfo[1]})"))

        self.__selectedFileNfo = self.__uiController.panel().selectedFiles()
        self.lblPerimeterSelectSelNfo.setText(i18n(f"(Files: {self.__selectedFileNfo[2]}, Directories: {self.__selectedFileNfo[1]})"))
        if self.__selectedFileNfo[3] > 0:
            self.rbPerimeterSelectSel.setEnabled(True)
            self.lblPerimeterSelectSelNfo.setEnabled(True)
        else:
            self.rbPerimeterSelectSel.setEnabled(False)
            self.lblPerimeterSelectSelNfo.setEnabled(False)

        self.pbPerimeterReset.clicked.connect(resetFields)
        self.pbPerimeterCheckAll.clicked.connect(checkAll)
        self.pbPerimeterUncheckAll.clicked.connect(uncheckAll)


    def __initialisePageFormat(self):
        """Initialise interface widgets for page format"""
        # --- ALL format ---
        @pyqtSlot(int)
        def formatChanged(index):
            self.lblFormatDescription.setText(BCExportFilesDialogBox.FMT_PROPERTIES[index]['description'])
            self.swFormatProperties.setCurrentIndex(index)

        # --- TEXT format ---
        def formatTextMinWidthCheck(checked):
            # State of checkbox Minimum width has been changed
            self.hsFormatTextMinWidth.setEnabled(checked)
            self.spFormatTextMinWidth.setEnabled(checked)

        def formatTextMaxWidthCheck(checked):
            # State of checkbox Maximum width has been changed
            self.hsFormatTextMaxWidth.setEnabled(checked)
            self.spFormatTextMaxWidth.setEnabled(checked)

        @pyqtSlot(int)
        def formatTextMinWidthChanged(value):
            # Value of Minimum width has changed
            # > ensure that's not greater than maximum witdh
            if value > self.hsFormatTextMaxWidth.value():
                self.hsFormatTextMaxWidth.setValue(value)

        @pyqtSlot(int)
        def formatTextMaxWidthChanged(value):
            # Value of Maximum width has changed
            # > ensure that's not greater than minimum witdh
            if value < self.hsFormatTextMinWidth.value():
                self.hsFormatTextMinWidth.setValue(value)

        # --- ALL format ---
        self.cbxFormat.setCurrentIndex(BCExportFormat.EXPORT_FMT_TEXT)
        self.cbxFormat.currentIndexChanged.connect(formatChanged)
        formatChanged(BCExportFormat.EXPORT_FMT_TEXT)

        # --- TEXT interface ---
        self.cbFormatTextMinWidth.toggled.connect(formatTextMinWidthCheck)
        self.cbFormatTextMaxWidth.toggled.connect(formatTextMaxWidthCheck)
        self.hsFormatTextMinWidth.valueChanged.connect(formatTextMinWidthChanged)
        self.hsFormatTextMaxWidth.valueChanged.connect(formatTextMaxWidthChanged)

        formatTextMinWidthCheck(self.cbFormatTextMinWidth.isChecked())
        formatTextMaxWidthCheck(self.cbFormatTextMaxWidth.isChecked())


    def __initialisePageTarget(self):
        """Initialise interface widgets for page target"""
        def saveAs():
            fileName = self.leTargetResultFile.text()
            if fileName == '':
                # need to determinate a directory
                fileName = ''

            fileName = QFileDialog.getSaveFileName(self, 'Save file', fileName, BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['extensions'])

            print(fileName)
            if fileName != '':
                self.leTargetResultFile.setText(fileName[0])
            self.__updateBtn()

        def checkButton(dummy):
            self.__updateBtn()

        self.pbTargetResultFile.clicked.connect(saveAs)
        self.rbTargetResultFile.toggled.connect(checkButton)
        self.rbTargetResultClipboard.toggled.connect(checkButton)
        self.leTargetResultFile.textChanged.connect(checkButton)


    def __goPreviousPage(self, action):
        """Go to previous page"""
        if self.swPages.currentIndex() > 0:
            self.swPages.setCurrentIndex(self.swPages.currentIndex() - 1)
        self.__updateBtn()


    def __goNextPage(self, action):
        """Go to next page"""
        if self.swPages.currentIndex() < self.swPages.count() - 1:
            self.swPages.setCurrentIndex(self.swPages.currentIndex() + 1)

        if self.swPages.currentIndex() == BCExportFilesDialogBox.__PAGE_TARGET:
            # when last page reached, enable/disable clipboard choice according to export format
            if not BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['clipboard']:
                self.rbTargetResultFile.setChecked(True)
                self.rbTargetResultClipboard.setEnabled(False)
            else:
                self.rbTargetResultClipboard.setEnabled(True)

        self.__updateBtn()


    def __updateBtn(self):
        """Update buttons state according to current page"""
        # First page / previous button not visible
        self.pbPrevious.setVisible(self.swPages.currentIndex() != 0)

        #Last page / next button not visible
        self.pbNext.setVisible(self.swPages.currentIndex() < self.swPages.count() - 1)

        # Last page / OK button enabled if a file target is valid
        self.pbExport.setEnabled(self.__targetIsValid())

        self.pbClose.setVisible(False)


    def __targetIsValid(self):
        """Return True is current selected target is valid, otherwise False"""
        # first, we must be on the target page
        returned = (self.swPages.currentIndex() == self.swPages.count() - 1)
        if not returned:
            return returned

        if self.rbTargetResultClipboard.isChecked():
            # if clipboard is the target, consider that's a valid target
            return True
        else:
            # otherwise target is valid if a file name is provided
            # do not check if provided path/filename make sense...
            return (self.leTargetResultFile.text().strip() != '')


    def __generateConfig(self):
        """Generate export config"""
        def getFields():
            fields = []
            for itemIndex in range(self.lwPerimeterProperties.count()):
                if  self.lwPerimeterProperties.item(itemIndex).checkState() == Qt.Checked:
                    fields.append(self.lwPerimeterProperties.item(itemIndex).data(1000))
            return fields

        def getFiles():
            if self.rbPerimeterSelectPath.isChecked():
                return self.__fileNfo[5]
            else:
                return self.__selectedFileNfo[5]

        returned = {}

        if self.cbxFormat.currentIndex() == BCExportFilesDialogBox.__PANEL_FORMAT_TEXT:
            returned = {
                    'title.active': self.cbFormatTextTitle.isChecked(),
                    'title.content': self.teFormatTextTitle.toPlainText(),

                    'header.active': self.cbFormatTextHeader.isChecked(),

                    'border.style': BCTableSettingsText.BORDER_NONE,

                    'minimumWidth.active': self.cbFormatTextMinWidth.isChecked(),
                    'minimumWidth.value': self.spFormatTextMinWidth.value(),

                    'maximumWidth.active': self.cbFormatTextMaxWidth.isChecked(),
                    'maximumWidth.value': self.spFormatTextMaxWidth.value(),

                    'fields': getFields(),
                    'files': getFiles()
                }

            if self.rbFormatTextBorderBasic.isChecked():
                returned['border.style'] = BCTableSettingsText.BORDER_BASIC
            elif self.rbFormatTextBorderSimple.isChecked():
                returned['border.style'] = BCTableSettingsText.BORDER_SIMPLE
            elif self.rbFormatTextBorderDouble.isChecked():
                returned['border.style'] = BCTableSettingsText.BORDER_DOUBLE

        elif self.cbxFormat.currentIndex() == BCExportFilesDialogBox.__PANEL_FORMAT_TEXT_CSV:
            returned = {
                    'header.active': self.cbFormatTextCSVHeader.isChecked(),

                    'field.enclosed': self.cbxFormatTextCSVEnclosedFields.isChecked(),
                    'field.separator': [',', ';', '\t', '|'][self.cbxFormatTextCSVSeparator.currentIndex()],

                    'fields': getFields(),
                    'files': getFiles()
                }
        elif self.cbxFormat.currentIndex() == BCExportFilesDialogBox.__PANEL_FORMAT_TEXT_MD:
            returned = {
                    'title.active': self.cbFormatTextMD.isChecked(),
                    'title.content': self.teFormatTextMDTitle.toPlainText(),

                    'fields': getFields(),
                    'files': getFiles()
                }

        return returned


    def __export(self):
        """Export process"""
        if self.cbxFormat.currentIndex() == BCExportFilesDialogBox.__PANEL_FORMAT_TEXT:
            exportedContent = self.exportAsText(self.__generateConfig(), False)
        elif self.cbxFormat.currentIndex() == BCExportFilesDialogBox.__PANEL_FORMAT_TEXT_CSV:
            exportedContent = self.exportAsTextCsv(self.__generateConfig(), False)
        elif self.cbxFormat.currentIndex() == BCExportFilesDialogBox.__PANEL_FORMAT_TEXT_MD:
            exportedContent = self.exportAsTextMd(self.__generateConfig(), False)

        QApplication.clipboard().setText(exportedContent)


    def __getTable(self, fields, items, title=None, preview=False):
        """Generic method to intialise a BCTable content"""
        returnedTable = BCTable()

        if not title is None:
            returnedTable.setTitle(title)

        headerFields = []
        for field in fields:
            headerFields.append(BCExportFilesDialogBox.FIELDS[field]['label'])
        returnedTable.setHeader(headerFields)

        maxRows = None
        if preview:
            maxRows = min(self.__previewLimit, len(items))

        currentRow = 0
        for file in items:
            currentRow+=1
            if not maxRows is None and currentRow >= maxRows:
                break

            rowContent = []
            for field in fields:
                data = BCExportFilesDialogBox.FIELDS[field]['data']
                rowContent.append( eval(f"f'{data}'") )

            returnedTable.addRow(rowContent)

        return returnedTable


    def exportAsText(self, config=None, preview=False):
        """Export content as text

        If `preview`, only the Nth first items are exported
        """
        # define a default configuration, if config is missing...
        defaultConfig = {
                'title.active': False,
                'title.content': '',

                'header.active': True,

                'border.style': BCTableSettingsText.BORDER_BASIC,

                'minimumWidth.active': True,
                'minimumWidth.value': 80,

                'maximumWidth.active': False,
                'maximumWidth.value': 120,

                'fields': [key for key in BCExportFilesDialogBox.FIELDS if BCExportFilesDialogBox.FIELDS[key]['selected']],
                'files': []
            }

        if not isinstance(config, dict):
            config = defaultConfig

        titleContent = None
        if config.get('title.active', defaultConfig['title.active']):
            # title asked
            titleContent = config.get('title.content', defaultConfig['title.content'])

        tableSettings = BCTableSettingsText()
        tableSettings.setHeaderActive(config.get('header.active', defaultConfig['header.active']))
        tableSettings.setBorder(config.get('border.style', defaultConfig['border.style']))
        tableSettings.setMinWidthActive(config.get('minimumWidth.active', defaultConfig['minimumWidth.active']))
        tableSettings.setMaxWidthActive(config.get('maximumWidth.active', defaultConfig['maximumWidth.active']))
        tableSettings.setMinWidth(config.get('minimumWidth.value', defaultConfig['minimumWidth.value']))
        tableSettings.setMaxWidth(config.get('maximumWidth.value', defaultConfig['maximumWidth.value']))
        tableSettings.setColumnAlignment([BCExportFilesDialogBox.FIELDS[key]['alignment'] for key in config.get('fields', defaultConfig['fields'])])

        table = self.__getTable(config.get('fields', defaultConfig['fields']),
                                config.get('files', defaultConfig['files']),
                                titleContent,
                                preview)

        return table.asText(tableSettings)


    def exportAsTextCsv(self, config=None, preview=False):
        """Export content as text

        If `preview`, only the Nth first items are exported
        """
        # define a default configuration, if config is missing...
        defaultConfig = {
                'header.active': True,

                'field.enclosed': False,
                'field.separator': ',',

                'fields': [key for key in BCExportFilesDialogBox.FIELDS if BCExportFilesDialogBox.FIELDS[key]['selected']],
                'files': []
            }

        if not isinstance(config, dict):
            config = defaultConfig

        tableSettings = BCTableSettingsTextCsv()
        tableSettings.setHeaderActive(config.get('header.active', defaultConfig['header.active']))
        tableSettings.setEnclosedField(config.get('field.enclosed', defaultConfig['field.enclosed']))
        tableSettings.setSeparator(config.get('field.separator', defaultConfig['field.separator']))

        table = self.__getTable(config.get('fields', defaultConfig['fields']),
                                config.get('files', defaultConfig['files']),
                                None,
                                preview)

        return table.asTextCsv(tableSettings)


    def exportAsTextMd(self, config=None, preview=False):
        """Export content as text

        If `preview`, only the Nth first items are exported
        """
        return ''
        # define a default configuration, if config is missing...
        defaultConfig = {
                'title.active': False,
                'title.content': '',

                'fields': [key for key in BCExportFilesDialogBox.FIELDS if BCExportFilesDialogBox.FIELDS[key]['selected']],
                'files': []
            }

        if not isinstance(config, dict):
            config = defaultConfig

        tableSettings = BCTableSettingsMarkdown()

        table = self.__getTable(config.get('fields', defaultConfig['fields']),
                                config.get('files', defaultConfig['files']),
                                None,
                                preview)

        return table.asTextMarkdown(tableSettings)


    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCExportFilesDialogBox(title, uicontroller)
        return db.exec()

