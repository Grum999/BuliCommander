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
import time
import re

from .bcfile import (
        BCDirectory,
        BCFile,
        BCFileManagedFormat,
        BCFileProperty
    )
from .bcsettings import BCSettingsKey
from .bcsystray import BCSysTray
from .bctable import (
        BCTable,
        BCTableSettingsText,
        BCTableSettingsTextCsv,
        BCTableSettingsTextMarkdown
    )
from .bcutils import (
        bytesSizeToStr,
        strDefault,
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
    EXPORT_FMT_TEXT_MD =        1
    EXPORT_FMT_TEXT_CSV =       2


class BCExportFilesDialogBox(QDialog):
    """User interface for export"""

    __PAGE_PERIMETER = 0
    __PAGE_FORMAT = 1
    __PAGE_TARGET = 2

    __PANEL_FORMAT_TEXT = 0
    __PANEL_FORMAT_TEXT_MD = 1
    __PANEL_FORMAT_TEXT_CSV = 2

    __FIELD_ID = 1000

    __CLIPBOARD = '@clipboard'


    FMT_PROPERTIES = {
            BCExportFormat.EXPORT_FMT_TEXT:         {'label':               i18n('Text'),
                                                     'description':         i18n("Generate a basic text file, without any formatting<br>"
                                                                                 "This file can be opened in any text editor; use a monospace font is highly recommended for a better readability"),
                                                     'clipboard':           True,
                                                     'fileExtension':       'txt',
                                                     'dialogExtensions':    i18n('Text files (*.txt)')
                                                    },
            BCExportFormat.EXPORT_FMT_TEXT_CSV:     {'label':               i18n('Text/CSV'),
                                                     'description':         i18n("Generate a CSV file<br>"
                                                                                 "This file can be opened in a spreadsheet software"),
                                                     'clipboard':           True,
                                                     'fileExtension':       'csv',
                                                     'dialogExtensions':    i18n('CSV files (*.csv)')
                                                    },
            BCExportFormat.EXPORT_FMT_TEXT_MD:      {'label':               i18n('Text/Markdown'),
                                                     'description':         i18n("Generate a Markdown file (<a href='https://guides.github.com/features/mastering-markdown'><span style='text-decoration: underline; color:#2980b9;'>GitHub flavored version</span></a>)<br>"
                                                                                 "This file can be opened in any text editor, but use of a dedicated software to render result is recommended"),
                                                     'clipboard':           True,
                                                     'fileExtension':       'md',
                                                     'dialogExtensions':    i18n('Markdown files (*.md *.markdown)')
                                                    }
        }

    FIELDS = {
                                                    # label:        value displayed in listbox
                                                    # tooltip:      tooltip affected to item in list
                                                    # data:         data to return in exported result
                                                    # alignment:    for format that support colupmn alignment, define
                                                    #               data alignment (0: left / 1: right)
                                                    # format:       how to format data (use markdown notation)
                                                    # selected:     default status in listbox
        'file.path':                                {'label':       i18n('Path'),
                                                     'toolTip':     i18n('The file path'),
                                                     'data':        '{file.path()}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'selected':    True
                                                    },
        'file.name':                                {'label':       i18n('File name'),
                                                     'toolTip':     i18n('The file name, including extension'),
                                                     'data':        '{file.name()}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'selected':    True
                                                    },
        'file.baseName':                            {'label':       i18n('File base name'),
                                                     'toolTip':     i18n('The file name, excluding extension'),
                                                     'data':        '{file.baseName() if not isinstance(file, BCDirectory) else file.name()}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'selected':    False
                                                    },
        'file.extension':                           {'label':       i18n('File extension'),
                                                     'toolTip':     i18n('The file extension, including dot separator)'),
                                                     'data':        '{file.extension() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'selected':    False
                                                    },
        'file.fullPathName':                        {'label':       i18n('Full path/file name'),
                                                     'toolTip':     i18n('The complete file name, including path'),
                                                     'data':        '{file.fullPathName()}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'selected':    False
                                                    },
        'file.format.short':                        {'label':       i18n('File format (short)'),
                                                     'toolTip':     i18n('The file format (short value)'),
                                                     'data':        '{BCFileManagedFormat.translate(file.format(), True)}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    True
                                                    },
        'file.format.long':                         {'label':       i18n('File format (long)'),
                                                     'toolTip':     i18n('The file format (long value)'),
                                                     'data':        '{BCFileManagedFormat.translate(file.format(), False)}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'modified.datetime':                        {'label':       i18n('Date/Time'),
                                                     'toolTip':     i18n('File date/time (<span style="font-family:''monospace''"><i>yyyy-mm-dd hh:mi:ss</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"dt")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    True
                                                    },
        'modified.date.full':                       {'label':       i18n('Date'),
                                                     'toolTip':     i18n('File date (<span style="font-family:''monospace''"><i>yyyy-mm-dd</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"d")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'modified.date.year':                       {'label':       i18n('Date (year)'),
                                                     'toolTip':     i18n('File date (<i>Year: <span style="font-family:''monospace''">yyyy</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%Y")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'modified.date.month':                      {'label':       i18n('Date (month)'),
                                                     'toolTip':     i18n('File date (<i>Month: <span style="font-family:''monospace''">mm</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%m")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'modified.date.day':                        {'label':       i18n('Date (day)'),
                                                     'toolTip':     i18n('File date (<i>Month: <span style="font-family:''monospace''">dd</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%d")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'modified.time.full':                       {'label':       i18n('Time'),
                                                     'toolTip':     i18n('File time (<span style="font-family:''monospace''"><i>hh:mi:ss</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"t")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'modified.time.hour':                       {'label':       i18n('Time (hour)'),
                                                     'toolTip':     i18n('File time (<i>Hour (H24): <span style="font-family:''monospace''">hh</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%H")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'modified.time.minute':                     {'label':       i18n('Time (minutes)'),
                                                     'toolTip':     i18n('File time (<i>Minutes: <span style="font-family:''monospace''">mm</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%M")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'modified.time.seconds':                    {'label':       i18n('Date (seconds)'),
                                                     'toolTip':     i18n('File time (<i>Seconds: <span style="font-family:''monospace''">ss</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%S")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'size.bytes':                               {'label':       i18n('Size (bytes)'),
                                                     'toolTip':     i18n('File size in bytes'),
                                                     'data':        '{file.size() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'size.unit.decimal':                        {'label':       i18n('Size (best decimal unit)'),
                                                     'toolTip':     i18n('File size, using the best decimal unit (KB, MB, GB)<br/>Size is rounded to 2 decimals'),
                                                     'data':        '{bytesSizeToStr(file.size(), "auto") if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'size.unit.binary':                         {'label':       i18n('Size (best binary unit)'),
                                                     'toolTip':     i18n('File size, using the best binary unit (KiB, MiB, GiB)<br/>Size is rounded to 2 decimals'),
                                                     'data':        '{bytesSizeToStr(file.size(), "autobin") if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'selected':    True
                                                    },
        'image.size.full':                          {'label':       i18n('Image size (width x height)'),
                                                     'toolTip':     i18n('The current image size (<span style="font-family:''monospace''"></i>width</i>x<i>height</i></span>)'),
                                                     'data':        '{str(file.imageSize().width()) + "x" + str(file.imageSize().height()) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'selected':    True
                                                    },
        'image.size.width':                         {'label':       i18n('Image size (width)'),
                                                     'toolTip':     i18n('The current image size (width)'),
                                                     'data':        '{file.imageSize().width() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'selected':    False
                                                    },
        'image.size.height':                         {'label':      i18n('Image size (height)'),
                                                     'toolTip':     i18n('The current image size (height)'),
                                                     'data':        '{file.imageSize().height() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'selected':    False
                                                    }
    }


    def __init__(self, title, uicontroller, parent=None):
        super(BCExportFilesDialogBox, self).__init__(parent)

        self.__title = title
        self.__previewLimit = 20

        self.__uiController = uicontroller
        self.__fileNfo = self.__uiController.panel().files()
        self.__selectedFileNfo = self.__uiController.panel().selectedFiles()

        self.__hasSavedSettings = self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_SAVED.id())

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcexportfiles.ui')
        PyQt5.uic.loadUi(uiFileName, self)

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

            self.lblPerimeterSelectPathNfo.setText(i18n(f"<b>{self.__uiController.panel().path()}</b> (Files: {self.__fileNfo[2]}, Directories: {self.__fileNfo[1]})"))
            self.lblPerimeterSelectSelNfo.setText(i18n(f"(Files: {self.__selectedFileNfo[2]}, Directories: {self.__selectedFileNfo[1]})"))
            if self.__selectedFileNfo[3] > 0:
                self.rbPerimeterSelectSel.setEnabled(True)
                self.lblPerimeterSelectSelNfo.setEnabled(True)
            else:
                self.rbPerimeterSelectSel.setEnabled(False)
                self.lblPerimeterSelectSelNfo.setEnabled(False)

            # define list of properties with default internal selection
            self.lwPerimeterProperties.clear()
            for field in BCExportFilesDialogBox.FIELDS:
                item = QListWidgetItem(BCExportFilesDialogBox.FIELDS[field]['label'])

                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if BCExportFilesDialogBox.FIELDS[field]['selected']:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                item.setData(BCExportFilesDialogBox.__FIELD_ID, field)   # store field ID
                item.setToolTip(BCExportFilesDialogBox.FIELDS[field]['toolTip'])
                self.lwPerimeterProperties.addItem(item)

            # connectors
            self.pbPerimeterReset.clicked.connect(self.__slotPagePerimeterResetFields)
            self.pbPerimeterCheckAll.clicked.connect(self.__slotPagePerimeterCheckAll)
            self.pbPerimeterUncheckAll.clicked.connect(self.__slotPagePerimeterUncheckAll)
            self.lwPerimeterProperties.itemChanged.connect(self.__slotPagePerimeterPropertiesChanged)

            self.__loadSettingsPagePerimeter()

        def __initialisePageFormat():
            # Initialise interface widgets for page format
            # --- ALL ---
            self.cbxFormat.currentIndexChanged.connect(self.__slotPageFormatFormatChanged)

            # --- TEXT interface ---
            self.cbFormatTextLayoutUserDefined.toggled.connect(self.__slotPageFormatTextLayoutUserDefined)
            self.cbFormatTextBorders.toggled.connect(self.__slotPageFormatTextBordersCheck)
            self.rbFormatTextBorderNone.toggled.connect(self.__slotPageFormatTextBordersStyleCheck)
            self.rbFormatTextBorderBasic.toggled.connect(self.__slotPageFormatTextBordersStyleCheck)
            self.rbFormatTextBorderSimple.toggled.connect(self.__slotPageFormatTextBordersStyleCheck)
            self.rbFormatTextBorderDouble.toggled.connect(self.__slotPageFormatTextBordersStyleCheck)
            self.cbFormatTextMinWidth.toggled.connect(self.__slotPageFormatTextMinWidthCheck)
            self.cbFormatTextMaxWidth.toggled.connect(self.__slotPageFormatTextMaxWidthCheck)
            self.hsFormatTextMinWidth.valueChanged.connect(self.__slotPageFormatTextMinWidthChanged)
            self.hsFormatTextMaxWidth.valueChanged.connect(self.__slotPageFormatTextMaxWidthChanged)

            # --- TEXT/MD interface ---
            self.cbFormatTextMDLayoutUserDefined.toggled.connect(self.__slotPageFormatTextMDLayoutUserDefined)
            self.cbFormatTextMDIncludeThumbnails.toggled.connect(self.__slotPageFormatTextMDIncludeThumbnails)

            self.__loadSettingsPageFormat()

        def __initialisePageTarget():
            # Initialise interface widgets for page target
            def saveAs():
                fileName = self.leTargetResultFile.text()
                if fileName == '':
                    # need to determinate a directory
                    fileName = ''

                fileName = QFileDialog.getSaveFileName(self, 'Save file', fileName, BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['dialogExtensions'])

                if fileName != '':
                    self.leTargetResultFile.setText(fileName[0])
                self.__updateBtn()

            def checkButton(dummy):
                self.__updateBtn()

            self.pbTargetResultFile.clicked.connect(saveAs)
            self.rbTargetResultFile.toggled.connect(checkButton)
            self.rbTargetResultClipboard.toggled.connect(checkButton)
            self.leTargetResultFile.textChanged.connect(checkButton)

            self.__loadSettingsPageTarget()

        def __initialiseButtonBar():
            # Initialise bottom button bar
            self.pbPrevious.clicked.connect(self.__goPreviousPage)
            self.pbNext.clicked.connect(self.__goNextPage)
            self.pbCancel.clicked.connect(self.reject)
            self.pbExport.clicked.connect(self.__export)
            self.pbOptionsLoadDefault.clicked.connect(self.__resetSettings)
            self.__updateBtn()

        __initialisePagePerimeter()
        __initialisePageFormat()
        __initialisePageTarget()
        __initialiseButtonBar()


    # -- Manage page Perimeter -------------------------------------------------
    def __loadDefaultPagePerimeter(self):
        """Load default internal configuration for page perimeter"""
        # reload default properties list
        self.swPages.setCurrentIndex(BCExportFilesDialogBox.__PAGE_PERIMETER)

        for itemIndex in range(self.lwPerimeterProperties.count()):
            if BCExportFilesDialogBox.FIELDS[self.lwPerimeterProperties.item(itemIndex).data(BCExportFilesDialogBox.__FIELD_ID)]['selected']:
                self.lwPerimeterProperties.item(itemIndex).setCheckState(Qt.Checked)
            else:
                self.lwPerimeterProperties.item(itemIndex).setCheckState(Qt.Unchecked)

    def __loadSettingsPagePerimeter(self):
        """Load saved settings for page perimeter"""
        if not self.__hasSavedSettings:
            # no saved settings: load default and exit
            self.__loadDefaultPagePerimeter()
            return

        self.swPages.setCurrentIndex(BCExportFilesDialogBox.__PAGE_PERIMETER)

        checkedList = self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_PROPERTIES.id())
        for itemIndex in range(self.lwPerimeterProperties.count()):
            if self.lwPerimeterProperties.item(itemIndex).data(BCExportFilesDialogBox.__FIELD_ID) in checkedList:
                self.lwPerimeterProperties.item(itemIndex).setCheckState(Qt.Checked)
            else:
                self.lwPerimeterProperties.item(itemIndex).setCheckState(Qt.Unchecked)

    # -- slots
    def __slotPagePerimeterCheckAll(self):
        # check all properties
        for itemIndex in range(self.lwPerimeterProperties.count()):
            self.lwPerimeterProperties.item(itemIndex).setCheckState(Qt.Checked)

    def __slotPagePerimeterUncheckAll(self):
        # uncheck all properties
        for itemIndex in range(self.lwPerimeterProperties.count()):
            self.lwPerimeterProperties.item(itemIndex).setCheckState(Qt.Unchecked)

    def __slotPagePerimeterResetFields(self):
        # reset field list check state
        self.__loadSettingsPagePerimeter()

    def __slotPagePerimeterPropertiesChanged(self, widget):
        self.__updateBtn()

    # -- Manage page Format -------------------------------------------------
    def __loadDefaultPageFormat(self):
        """Load default internal configuration for page perimeter"""
        def defaultText():
            # --- TEXT interface ---
            self.cbFormatTextLayoutUserDefined.setChecked(True)
            self.teFormatTextLayoutUserDefined.setPlainText(
"""Buli Commander v{bc:version} - File list exporter
--------------------------------------------------------------------------------

Exported from: {source}
Exported at:   {date} {time}

{table}

Directories:   {items:directories.count}
Files:         {items:files.count} ({items:files.size(KiB)})
"""
            )

            self.cbFormatTextHeader.setChecked(True)
            self.cbFormatTextBorders.setChecked(True)
            self.rbFormatTextBorderSimple.setChecked(True)
            self.cbFormatTextMinWidth.setChecked(True)
            self.hsFormatTextMinWidth.setValue(80)
            self.cbFormatTextMaxWidth.setChecked(False)
            self.hsFormatTextMaxWidth.setValue(120)

            self.__slotPageFormatTextLayoutUserDefined()
            self.__slotPageFormatTextBordersCheck()
            self.__slotPageFormatTextBordersStyleCheck()
            self.__slotPageFormatTextMinWidthCheck()
            self.__slotPageFormatTextMaxWidthCheck()
            self.__slotPageFormatTextMinWidthChanged()
            self.__slotPageFormatTextMaxWidthChanged()

        def defaultTextMd():
            # --- TEXT/MARKDOWN interface ---
            self.cbFormatTextMDLayoutUserDefined.setChecked(True)
            self.teFormatTextMDLayoutUserDefined.setPlainText(
"""## Buli Commander *v{bc:version}* - File list exporter

> Export from | Exported at | Directories | Files
> -- | -- | -- | --
> `{source}` | {date} {time} | {items:directories.count} | {items:files.count} *({items:files.size(KiB)})*

{table}
"""
            )

            self.cbFormatTextMDIncludeThumbnails.setChecked(False)
            self.cbxFormatTextMDThumbnailsSize.setCurrentIndex(0)

            self.__slotPageFormatTextMDLayoutUserDefined()
            self.__slotPageFormatTextMDIncludeThumbnails()

        def defaultTextCsv():
            # --- TEXT/CSV interface ---
            self.cbFormatTextCSVHeader.setChecked(True)
            self.cbFormatTextCSVEnclosedFields.setChecked(False)
            self.cbxFormatTextCSVSeparator.setCurrentIndex(0)

        # --- ALL format ---
        self.cbxFormat.setCurrentIndex(BCExportFormat.EXPORT_FMT_TEXT)
        self.__slotPageFormatFormatChanged()

        # -- pages
        defaultText()
        defaultTextMd()
        defaultTextCsv()

    def __loadSettingsPageFormat(self):
        """Load saved settings for page format"""
        def defaultText():
            # --- TEXT interface ---
            self.cbFormatTextLayoutUserDefined.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_ACTIVE.id()))
            self.teFormatTextLayoutUserDefined.setPlainText(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_CONTENT.id()))

            self.cbFormatTextHeader.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_HEADER_ACTIVE.id()))
            currentBordersStyle = self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE.id())
            if currentBordersStyle == 0:
                self.rbFormatTextBorderNone.setChecked(True)
            elif currentBordersStyle == 1:
                self.rbFormatTextBorderBasic.setChecked(True)
            elif currentBordersStyle == 2:
                self.rbFormatTextBorderSimple.setChecked(True)
            elif currentBordersStyle == 3:
                self.rbFormatTextBorderDouble.setChecked(True)
            self.cbFormatTextMinWidth.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_ACTIVE.id()))
            self.hsFormatTextMinWidth.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_VALUE.id()))
            self.cbFormatTextMaxWidth.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_ACTIVE.id()))
            self.hsFormatTextMaxWidth.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_VALUE.id()))

            self.__slotPageFormatTextLayoutUserDefined()
            self.__slotPageFormatTextBordersCheck()
            self.__slotPageFormatTextBordersStyleCheck()
            self.__slotPageFormatTextMinWidthCheck()
            self.__slotPageFormatTextMaxWidthCheck()
            self.__slotPageFormatTextMinWidthChanged()
            self.__slotPageFormatTextMaxWidthChanged()

        def defaultTextMd():
            # --- TEXT/MARKDOWN interface ---
            self.cbFormatTextMDLayoutUserDefined.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_ACTIVE.id()))
            self.teFormatTextMDLayoutUserDefined.setPlainText(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_CONTENT.id()))

            self.cbFormatTextMDIncludeThumbnails.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_INCLUDED.id()))
            self.cbxFormatTextMDThumbnailsSize.setCurrentIndex(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_SIZE.id()))

            self.__slotPageFormatTextMDLayoutUserDefined()
            self.__slotPageFormatTextMDIncludeThumbnails()

        def defaultTextCsv():
            # --- TEXT/CSV interface ---
            self.cbFormatTextCSVHeader.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_HEADER_ACTIVE.id()))
            self.cbFormatTextCSVEnclosedFields.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_ENCLOSED.id()))
            self.cbxFormatTextCSVSeparator.setCurrentIndex(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_SEPARATOR.id()))

        if not self.__hasSavedSettings:
            # no saved settings: load default and exit
            self.__loadDefaultPageFormat()
            return

        # --- ALL format ---
        self.cbxFormat.setCurrentIndex(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FORMAT.id()))
        self.__slotPageFormatFormatChanged()

        # -- pages
        defaultText()
        defaultTextMd()
        defaultTextCsv()

    # -- slots
    def __slotPageFormatFormatChanged(self, index=None):
        # update current format page
        if index is None:
            index = self.cbxFormat.currentIndex()

        text = BCExportFilesDialogBox.FMT_PROPERTIES[index]['label']

        self.lblFormatDescription.setText(BCExportFilesDialogBox.FMT_PROPERTIES[index]['description'])
        self.lblFormatOptions.setText( i18n(f"Options for <i>{text}</i> format") )
        self.swFormatProperties.setCurrentIndex(index)

    def __slotPageFormatTextLayoutUserDefined(self, checked=None):
        # user defined layout option ahs been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextLayoutUserDefined.isChecked()

        self.teFormatTextLayoutUserDefined.setEnabled(checked)

    def __slotPageFormatTextBordersCheck(self, checked=None):
        # user defined borders option ahs been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextBorders.isChecked()

        if not checked:
            self.rbFormatTextBorderNone.setChecked(True)

    def __slotPageFormatTextBordersStyleCheck(self, checked=None):
        self.cbFormatTextBorders.setChecked(not self.rbFormatTextBorderNone.isChecked())

    def __slotPageFormatTextMinWidthCheck(self, checked=None):
        # State of checkbox Minimum width has been changed
        if checked is None:
            checked = self.cbFormatTextMinWidth.isChecked()

        self.hsFormatTextMinWidth.setEnabled(checked)
        self.spFormatTextMinWidth.setEnabled(checked)

    def __slotPageFormatTextMaxWidthCheck(self, checked=None):
        # State of checkbox Maximum width has been changed
        if checked is None:
            checked = self.cbFormatTextMaxWidth.isChecked()

        self.hsFormatTextMaxWidth.setEnabled(checked)
        self.spFormatTextMaxWidth.setEnabled(checked)

    def __slotPageFormatTextMinWidthChanged(self, value=None):
        # Value of Minimum width has changed
        # > ensure that's not greater than maximum witdh
        if value is None:
            value = self.hsFormatTextMinWidth.value()

        if value > self.hsFormatTextMaxWidth.value():
            self.hsFormatTextMaxWidth.setValue(value)

    def __slotPageFormatTextMaxWidthChanged(self, value=None):
        # Value of Maximum width has changed
        # > ensure that's not greater than minimum witdh
        if value is None:
            value = self.hsFormatTextMaxWidth.value()

        if value < self.hsFormatTextMinWidth.value():
            self.hsFormatTextMinWidth.setValue(value)

    def __slotPageFormatTextMDLayoutUserDefined(self, checked=None):
        # user defined layout option has been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextMDLayoutUserDefined.isChecked()

        self.teFormatTextMDLayoutUserDefined.setEnabled(checked)

    def __slotPageFormatTextMDIncludeThumbnails(self, checked=None):
        # include thumbnail in md export has been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextMDIncludeThumbnails.isChecked()

        self.cbxFormatTextMDThumbnailsSize.setEnabled(checked)

    # -- Manage page Target -------------------------------------------------
    def __loadDefaultPageTarget(self):
        """Load default internal configuration for page target"""
        self.leTargetResultFile.setText('')

    def __loadSettingsPageTarget(self):
        """Load saved settings for page format"""
        if not self.__hasSavedSettings:
            # no saved settings: load default and exit
            self.__loadDefaultPageTarget()
            return

        self.leTargetResultFile.setProperty('__bcExtension', self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FILENAME.id()))


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

        if self.swPages.currentIndex() == BCExportFilesDialogBox.__PAGE_TARGET:
            # when last page reached, enable/disable clipboard choice according to export format

            if self.leTargetResultFile.text() == '':
                # no file name defined, get file name from settings
                fileName = strDefault(self.leTargetResultFile.property('__bcExtension'))
            else:
                # a name is already set...?
                # update extension
                if result:=re.match("(.*)(\..*)$", self.leTargetResultFile.text()):
                    fileName = f"{result.groups()[0]}.{{ext}}"
                else:
                    fileName = f"{self.leTargetResultFile.text()}.{{ext}}"

            self.leTargetResultFile.setText(fileName.replace('{ext}', BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['fileExtension']))

            if not BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['clipboard']:
                self.rbTargetResultFile.setChecked(True)
                self.rbTargetResultClipboard.setEnabled(False)
            else:
                self.rbTargetResultClipboard.setEnabled(True)

        self.__updateBtn()


    def __updateBtn(self):
        """Update buttons state according to current page"""
        # note: enable/disable instead of show/hide, that's less disturbing in the
        #       navigation

        # First page / previous button not enabled
        self.pbPrevious.setEnabled(self.swPages.currentIndex() != 0)

        if self.swPages.currentIndex() == 0:
            # first page
            # need to check if, at least, one properties is checked for export :)
            noneChecked = True
            for itemIndex in range(self.lwPerimeterProperties.count()):
                if self.lwPerimeterProperties.item(itemIndex).checkState() == Qt.Checked:
                    noneChecked = False
                    break

            self.pbNext.setEnabled(not noneChecked)
        elif self.swPages.currentIndex() == self.swPages.count() - 1:
            # Last page / next button disabled
            self.pbNext.setEnabled(False)
        else:
            self.pbNext.setEnabled(True)

        # Last page / OK button enabled if a file target is valid
        self.pbExport.setEnabled(self.__targetIsValid())


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
                    fields.append(self.lwPerimeterProperties.item(itemIndex).data(BCExportFilesDialogBox.__FIELD_ID))
            return fields

        def getFiles():
            if self.rbPerimeterSelectPath.isChecked():
                return self.__fileNfo[5]
            else:
                return self.__selectedFileNfo[5]

        returned = {}

        if self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT:
            returned = {
                    'userDefinedLayout.active': self.cbFormatTextLayoutUserDefined.isChecked(),
                    'userDefinedLayout.content': self.teFormatTextLayoutUserDefined.toPlainText(),

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

        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_CSV:
            returned = {
                    'header.active': self.cbFormatTextCSVHeader.isChecked(),

                    'field.enclosed': self.cbFormatTextCSVEnclosedFields.isChecked(),
                    'field.separator': [',', ';', '\t', '|'][self.cbxFormatTextCSVSeparator.currentIndex()],

                    'fields': getFields(),
                    'files': getFiles()
                }
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_MD:
            returned = {
                    'userDefinedLayout.active': self.cbFormatTextMDLayoutUserDefined.isChecked(),
                    'userDefinedLayout.content': self.teFormatTextMDLayoutUserDefined.toPlainText(),

                    'thumbnails.included': self.cbFormatTextMDIncludeThumbnails.isChecked(),
                    'thumbnails.size': [64,128,256,512][self.cbxFormatTextMDThumbnailsSize.currentIndex()],

                    'fields': getFields(),
                    'files': getFiles()
                }

        return returned


    def __saveSettings(self):
        """Save current export configuration to settings"""
        def __savePagePerimeter():
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_PROPERTIES, [self.lwPerimeterProperties.item(itemIndex).data(BCExportFilesDialogBox.__FIELD_ID) for itemIndex in range(self.lwPerimeterProperties.count()) if self.lwPerimeterProperties.item(itemIndex).checkState() == Qt.Checked])

        def __savePageFormat():
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FORMAT, self.cbxFormat.currentIndex())

            # -- TEXT format --
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_ACTIVE, self.cbFormatTextLayoutUserDefined.isChecked())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_CONTENT, self.teFormatTextLayoutUserDefined.toPlainText())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_HEADER_ACTIVE, self.cbFormatTextHeader.isChecked())

            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE, self.cbFormatTextBorders.isChecked())

            if self.rbFormatTextBorderSimple.isChecked():
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FORMAT, )

            if self.rbFormatTextBorderNone.isChecked():
                currentBordersStyle = 0
            elif self.rbFormatTextBorderBasic.isChecked():
                currentBordersStyle = 1
            elif self.rbFormatTextBorderSimple.isChecked():
                currentBordersStyle = 2
            elif self.rbFormatTextBorderDouble.isChecked():
                currentBordersStyle = 3
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE, currentBordersStyle)

            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_ACTIVE, self.cbFormatTextMinWidth.isChecked())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_VALUE, self.hsFormatTextMinWidth.value())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_ACTIVE, self.cbFormatTextMaxWidth.isChecked())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_VALUE, self.hsFormatTextMaxWidth.value())

            # -- TEXT/MARKDOWN format --
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_ACTIVE, self.cbFormatTextMDLayoutUserDefined.isChecked())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_CONTENT, self.teFormatTextMDLayoutUserDefined.toPlainText())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_INCLUDED, self.cbFormatTextMDIncludeThumbnails.isChecked())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_SIZE, self.cbxFormatTextMDThumbnailsSize.currentIndex())

            # -- TEXT/CSV format --
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_HEADER_ACTIVE, self.cbFormatTextCSVHeader.isChecked())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_ENCLOSED, self.cbFormatTextCSVEnclosedFields.isChecked())
            self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_SEPARATOR, self.cbxFormatTextCSVSeparator.currentIndex())

        def __savePageTarget():
            fileName = self.leTargetResultFile.text()
            if fileName != '' and (result:=re.match("(.*)(\..*)$", fileName)):
                fileName = f"{result.groups()[0]}.{{ext}}"
                self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FILENAME, fileName)


        __savePagePerimeter()
        __savePageFormat()
        __savePageTarget()

        self.__uiController.settings().setOption(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_SAVED, True)
        self.__uiController.saveSettings()


    def __resetSettings(self):
        """Reset export configuration to default settings"""
        self.__loadDefaultPagePerimeter()
        self.__loadDefaultPageFormat()
        self.__loadDefaultPageTarget()


    def __exportDataToFile(self, fileName, data):
        """Save data to file :)

        if data is string, save as UTF-8 text file otherwise try to save binary
        data according to type

        return True if file has been saved, otherwise False
        """
        try:
            if isinstance(data, str):
                with open(fileName, 'wb') as file:
                    file.write(data.encode('utf-8'))
            else:
                # othercase, try binary data save
                with open(fileName, 'wb') as file:
                    file.write(data)
            return True
        except Exception as e:
            Debug.print('[BCExportFilesDialogBox.__exportDataToFile] Unable to save file {0}: {1}', fileName, e)
            return False


    def __exportDataToClipboard(self, data):
        """Export data to clipboard

        return True if file has been copied to clipboard, otherwise False
        """
        try:
            QApplication.clipboard().setText(data)
            return True
        except Exception as e:
            Debug.print('[BCExportFilesDialogBox.__exportDataToClipboard] Unable to copy to clipboard: {0}', e)
            return False


    def __export(self):
        """Export process"""
        QApplication.setOverrideCursor(Qt.WaitCursor)

        if self.rbTargetResultClipboard.isChecked():
            target = BCExportFilesDialogBox.__CLIPBOARD
        else:
            target = self.leTargetResultFile.text()

        if self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT:
            exported = self.exportAsText(target, self.__generateConfig(), False)
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_CSV:
            exported = self.exportAsTextCsv(target, self.__generateConfig(), False)
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_MD:
            exported = self.exportAsTextMd(target, self.__generateConfig(), False)

        QApplication.restoreOverrideCursor()

        # exported is a dict
        # {'exported': bool
        #  'message': string
        # }
        if exported['exported']:
            # export successful, save current settings
            self.__saveSettings()
            BCSysTray.messageInformation(i18n(f"{self.__uiController.bcName()}::Export files list"),
                                         i18n(f"Export as <i>{BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['label']}</i> format {exported['message']} is finished"))

            QApplication.restoreOverrideCursor()
            # and close export window
            # self.accept()
        else:
            BCSysTray.messageCritical(i18n(f"{self.__uiController.bcName()}::Export files list"),
                                      i18n(f"Export as <i>{BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['label']}</i> format {exported['message']} has failed!"))

            QApplication.restoreOverrideCursor()
            ##### export failed: do not close window, let user try to check/fix the problem
            ##### DON'T UNCOMMENT! :-)
            ##### self.reject()


    def __parseText(self, text, tableContent):
        """Parse given text to replace markup with their values"""
        returned = text

        if self.rbPerimeterSelectPath.isChecked():
            returned = returned.replace("{source}", self.__uiController.panel().path())
        else:
            returned = returned.replace("{source}", "Current user selection")

        currentDateTime = time.time()

        returned = returned.replace("{bc:name}", self.__uiController.bcName())
        returned = returned.replace("{bc:version}", self.__uiController.bcVersion())
        returned = returned.replace("{bc:title}", self.__uiController.bcTitle())

        returned = returned.replace("{date}", tsToStr(currentDateTime, "d" ))
        returned = returned.replace("{date:yyyy}", tsToStr(currentDateTime, "%Y" ))
        returned = returned.replace("{date:mm}", tsToStr(currentDateTime, "%m" ))
        returned = returned.replace("{date:dd}", tsToStr(currentDateTime, "%d" ))

        returned = returned.replace("{time}", tsToStr(currentDateTime, "t" ))
        returned = returned.replace("{time:hh}", tsToStr(currentDateTime, "%H" ))
        returned = returned.replace("{time:mm}", tsToStr(currentDateTime, "%M" ))
        returned = returned.replace("{time:ss}", tsToStr(currentDateTime, "%S" ))

        returned = returned.replace("{items:total.count}", str(self.__fileNfo[3]))
        returned = returned.replace("{items:directories.count}", str(self.__fileNfo[1]))
        returned = returned.replace("{items:files.count}", str(self.__fileNfo[2]))
        returned = returned.replace("{items:files.size}", str(self.__fileNfo[6]))
        returned = returned.replace("{items:files.size(KiB)}", bytesSizeToStr(self.__fileNfo[6], 'autobin'))
        returned = returned.replace("{items:files.size(KB)}", bytesSizeToStr(self.__fileNfo[6], 'auto'))

        returned = returned.replace("{table}", tableContent)

        return returned


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


    def exportAsText(self, target, config=None, preview=False):
        """Export content as text

        If `preview`, only the Nth first items are exported
        """
        returned = {'exported': False,
                    'message': 'not processed :)'
                }
        # define a default configuration, if given config is missing...
        defaultConfig = {
                'userDefinedLayout.active': False,
                'userDefinedLayout.content': '{table}',

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

        tableSettings = BCTableSettingsText()
        tableSettings.setHeaderActive(config.get('header.active', defaultConfig['header.active']))
        tableSettings.setBorder(config.get('border.style', defaultConfig['border.style']))
        tableSettings.setMinWidthActive(config.get('minimumWidth.active', defaultConfig['minimumWidth.active']))
        tableSettings.setMaxWidthActive(config.get('maximumWidth.active', defaultConfig['maximumWidth.active']))
        tableSettings.setMinWidth(config.get('minimumWidth.value', defaultConfig['minimumWidth.value']))
        tableSettings.setMaxWidth(config.get('maximumWidth.value', defaultConfig['maximumWidth.value']))
        tableSettings.setColumnsAlignment([BCExportFilesDialogBox.FIELDS[key]['alignment'] for key in config.get('fields', defaultConfig['fields'])])

        try:
            table = self.__getTable(config.get('fields', defaultConfig['fields']),
                                    config.get('files', defaultConfig['files']),
                                    None,
                                    preview)

            if config.get('userDefinedLayout.active', defaultConfig['userDefinedLayout.active']):
                # layout asked
                content = self.__parseText(config.get('userDefinedLayout.content', defaultConfig['userDefinedLayout.content']), table.asText(tableSettings))
            else:
                content = table.asText(tableSettings)

            # data are ready
            returned['exported'] = True
        except Exception as e:
            Debug.print('[BCExportFilesDialogBox.exportAsText] Unable to generate data: {0}', e)

        if target == BCExportFilesDialogBox.__CLIPBOARD:
            returned['message'] = 'to clipboard'
            if returned['exported']:
                returned['exported'] = self.__exportDataToClipboard(content)
        else:
            returned['message'] = f'to file <b>{os.path.basename(target)}</b>'
            if returned['exported']:
                returned['exported'] = self.__exportDataToFile(target, content)

        return returned


    def exportAsTextCsv(self, target, config=None, preview=False):
        """Export content as text

        If `preview`, only the Nth first items are exported
        """
        returned = {'exported': False,
                    'message': 'not processed :)'
                }
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

        try:
            table = self.__getTable(config.get('fields', defaultConfig['fields']),
                                    config.get('files', defaultConfig['files']),
                                    None,
                                    preview)

            content = table.asTextCsv(tableSettings)

            # data are ready
            returned['exported'] = True
        except Exception as e:
            Debug.print('[BCExportFilesDialogBox.exportAsTextCsv] Unable to generate data: {0}', e)

        if target == BCExportFilesDialogBox.__CLIPBOARD:
            returned['message'] = 'to clipboard'
            if returned['exported']:
                returned['exported'] = self.__exportDataToClipboard(content)
        else:
            returned['message'] = f'to file <b>{os.path.basename(target)}</b>'
            if returned['exported']:
                returned['exported'] = self.__exportDataToFile(target, content)

        return returned


    def exportAsTextMd(self, target, config=None, preview=False):
        """Export content as text

        If `preview`, only the Nth first items are exported
        """
        returned = {'exported': False,
                    'message': 'not processed :)'
                }
        # define a default configuration, if config is missing...
        defaultConfig = {
                'userDefinedLayout.active': False,
                'userDefinedLayout.content': '{table}',

                'thumbnails.included': False,
                'thumbnails.size': 64,

                'fields': [key for key in BCExportFilesDialogBox.FIELDS if BCExportFilesDialogBox.FIELDS[key]['selected']],
                'files': []
            }

        if not isinstance(config, dict):
            config = defaultConfig

        tableSettings = BCTableSettingsTextMarkdown()
        tableSettings.setColumnsFormatting([BCExportFilesDialogBox.FIELDS[key]['format'] for key in config.get('fields', defaultConfig['fields'])])

        try:
            table = self.__getTable(config.get('fields', defaultConfig['fields']),
                                    config.get('files', defaultConfig['files']),
                                    None,
                                    preview)

            if config.get('userDefinedLayout.active', defaultConfig['userDefinedLayout.active']):
                # layout asked
                content = self.__parseText(config.get('userDefinedLayout.content', defaultConfig['userDefinedLayout.content']), table.asTextMarkdown(tableSettings))
            else:
                content = table.asTextMarkdown(tableSettings)

            # data are ready
            returned['exported'] = True
        except Exception as e:
            Debug.print('[BCExportFilesDialogBox.exportAsTextMd] Unable to generate data: {0}', e)

        if target == BCExportFilesDialogBox.__CLIPBOARD:
            returned['message'] = 'to clipboard'
            if returned['exported']:
                returned['exported'] = self.__exportDataToClipboard(content)
        else:
            returned['message'] = f'to file <b>{os.path.basename(target)}</b>'
            if returned['exported']:
                returned['exported'] = self.__exportDataToFile(target, content)

        return returned


    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCExportFilesDialogBox(title, uicontroller)
        return db.exec()

