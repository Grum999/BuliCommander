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
        BCFileProperty,
        BCFileThumbnailSize
    )
from .bcsettings import BCSettingsKey
from .bcsystray import BCSysTray
from .bctable import (
        BCTable,
        BCTableSettingsText,
        BCTableSettingsTextCsv,
        BCTableSettingsTextMarkdown
    )
from .bctextedit import (
        BCTextEdit,
        BCTextEditDialog
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
    EXPORT_FMT_DOC_PDF =        3
    EXPORT_FMT_IMG_KRA =        4
    EXPORT_FMT_IMG_PNG =        5
    EXPORT_FMT_IMG_JPG =        6


class BCExportFilesDialogBox(QDialog):
    """User interface for export"""

    __PAGE_PERIMETER = 0
    __PAGE_FORMAT = 1
    __PAGE_TARGET = 2

    __PANEL_FORMAT_DOCIMG_PAGESETUP = 0
    __PANEL_FORMAT_DOCIMG_PAGELAYOUT = 1
    __PANEL_FORMAT_DOCIMG_THUMBCONFIG = 2

    __PANEL_FORMAT_DOCIMG_PAGESETUP_UNIT_MM = 0
    __PANEL_FORMAT_DOCIMG_PAGESETUP_UNIT_CM = 1
    __PANEL_FORMAT_DOCIMG_PAGESETUP_UNIT_INCH = 2


    __FIELD_ID = 1000

    __CLIPBOARD = '@clipboard'


    # paper size are define in Portrait mode
    PAPER_SIZES = {
        'A2': {'mm':QSizeF(420,  594),
               'cm':QSizeF(42.0, 59.4),
               'in':QSizeF(16.5, 23.4),
               'px':QSizeF(16.5, 23.4)
              },
        'A3': {'mm':QSizeF(297,  420),
               'cm':QSizeF(29.7, 42.0),
               'in':QSizeF(11.7, 16.5),
               'px':QSizeF(11.7, 16.5)
              },
        'A4': {'mm':QSizeF(210, 297),
               'cm':QSizeF(21.0, 29.7),
               'in':QSizeF(8.3, 11.7),
               'px':QSizeF(8.3, 11.7)
              },
        'A5': {'mm':QSizeF(148, 210),
               'cm':QSizeF(14.8, 21.0),
               'in':QSizeF(5.8, 8.3),
               'px':QSizeF(5.8, 8.3)
              },
        'A6': {'mm':QSizeF(105, 148),
               'cm':QSizeF(10.5, 14.8),
               'in':QSizeF(4.1, 5.8),
               'px':QSizeF(4.1, 5.8)
              },

        'B2 (ISO)': {'mm':QSizeF(500,  707),
                     'cm':QSizeF(50.0, 70.7),
                     'in':QSizeF(19.7, 27.8),
                     'px':QSizeF(19.7, 27.8)
              },
        'B3 (ISO)': {'mm':QSizeF(353,  500),
                     'cm':QSizeF(35.3, 50.0),
                     'in':QSizeF(13.9, 19.7),
                     'px':QSizeF(13.9, 19.7)
              },
        'B4 (ISO)': {'mm':QSizeF(250, 353),
                     'cm':QSizeF(25.0, 35.3),
                     'in':QSizeF(9.8, 13.9),
                     'px':QSizeF(9.8, 13.9)
              },
        'B5 (ISO)': {'mm':QSizeF(176, 250),
                     'cm':QSizeF(17.6, 25.0),
                     'in':QSizeF(6.9, 9.8),
                     'px':QSizeF(6.9, 9.8)
              },
        'B6 (ISO)': {'mm':QSizeF(125, 176),
                     'cm':QSizeF(12.5, 17.6),
                     'in':QSizeF(4.9, 6.9),
                     'px':QSizeF(4.9, 6.9)
              },

        'B2 (JIS)': {'mm':QSizeF(515,  728),
                     'cm':QSizeF(51.5, 72.8),
                     'in':QSizeF(20.3, 28.7),
                     'px':QSizeF(20.3, 28.7)
              },
        'B3 (JIS)': {'mm':QSizeF(364,  515),
                     'cm':QSizeF(36.4, 51.5),
                     'in':QSizeF(14.3, 20.3),
                     'px':QSizeF(14.3, 20.3)
              },
        'B4 (JIS)': {'mm':QSizeF(257, 364),
                     'cm':QSizeF(25.7, 36.4),
                     'in':QSizeF(10.1, 14.3),
                     'px':QSizeF(10.1, 14.3)
              },
        'B5 (JIS)': {'mm':QSizeF(182, 257),
                     'cm':QSizeF(18.2, 25.7),
                     'in':QSizeF(7.2, 10.1),
                     'px':QSizeF(7.2, 10.1)
              },
        'B6 (JIS)': {'mm':QSizeF(128, 182),
                     'cm':QSizeF(12.8, 18.2),
                     'in':QSizeF(5.0, 7.2),
                     'px':QSizeF(5.0, 7.2)
              },

        'Letter (US)': {'mm':QSizeF(216, 279),
                        'cm':QSizeF(21.6, 27.9),
                        'in':QSizeF(8.5, 11.0),
                        'px':QSizeF(8.5, 11.0)
              },
        'Legal (US)': {'mm':QSizeF(216, 356),
                       'cm':QSizeF(21.6, 35.6),
                       'in':QSizeF(8.5, 14.0),
                       'px':QSizeF(8.5, 14.0)
              }
    }
    UNITS = {
        'mm': {'label': i18n('Millimeters'),
               'fmt': '0.0f',
               'marginDec': 0,
               'format': [BCExportFormat.EXPORT_FMT_DOC_PDF,
                          BCExportFormat.EXPORT_FMT_IMG_JPG,
                          BCExportFormat.EXPORT_FMT_IMG_PNG,
                          BCExportFormat.EXPORT_FMT_IMG_KRA]
              },
        'cm': {'label': i18n('Centimeters'),
               'fmt': '0.2f',
               'marginDec': 2,
               'format': [BCExportFormat.EXPORT_FMT_DOC_PDF,
                          BCExportFormat.EXPORT_FMT_IMG_JPG,
                          BCExportFormat.EXPORT_FMT_IMG_PNG,
                          BCExportFormat.EXPORT_FMT_IMG_KRA]
              },
        'in': {'label': i18n('Inches'),
               'fmt': '0.2f',
               'marginDec': 4,
               'format': [BCExportFormat.EXPORT_FMT_DOC_PDF,
                          BCExportFormat.EXPORT_FMT_IMG_JPG,
                          BCExportFormat.EXPORT_FMT_IMG_PNG,
                          BCExportFormat.EXPORT_FMT_IMG_KRA]
              },
        'px': {'label': i18n('Pixels'),
               'fmt': '0.0f',
               'marginDec': 0,
               'format': [BCExportFormat.EXPORT_FMT_IMG_JPG,
                          BCExportFormat.EXPORT_FMT_IMG_PNG,
                          BCExportFormat.EXPORT_FMT_IMG_KRA]
              }
    }
    IMAGE_RESOLUTIONS = {
        '72dpi': 72,
        '96dpi': 96,
        '150dpi': 150,
        '300dpi': 300,
        '600dpi': 600,
        '900dpi': 900,
        '1200dpi': 1200
    }
    ORIENTATION_PORTRAIT = 0x00
    ORIENTATION_LANDSCAPE = 0x01

    FMT_PROPERTIES = {
            BCExportFormat.EXPORT_FMT_TEXT:         {'label':               i18n('Text'),
                                                     'description':         i18n("Generate a basic text file, without any formatting<br>"
                                                                                 "This file can be opened in any text editor; use a monospace font is highly recommended for a better readability"),
                                                     'panelFormat':         0,
                                                     'clipboard':           True,
                                                     'fileExtension':       'txt',
                                                     'dialogExtensions':    i18n('Text files (*.txt)')
                                                    },
            BCExportFormat.EXPORT_FMT_TEXT_CSV:     {'label':               i18n('Text/CSV'),
                                                     'description':         i18n("Generate a CSV file<br>"
                                                                                 "This file can be opened in a spreadsheet software"),
                                                     'panelFormat':         2,
                                                     'clipboard':           True,
                                                     'fileExtension':       'csv',
                                                     'dialogExtensions':    i18n('CSV files (*.csv)')
                                                    },
            BCExportFormat.EXPORT_FMT_TEXT_MD:      {'label':               i18n('Text/Markdown'),
                                                     'description':         i18n("Generate a Markdown file (<a href='https://guides.github.com/features/mastering-markdown'><span style='text-decoration: underline; color:#2980b9;'>GitHub flavored version</span></a>)<br>"
                                                                                 "This file can be opened in any text editor, but use of a dedicated software to render result is recommended"),
                                                     'panelFormat':         1,
                                                     'clipboard':           True,
                                                     'fileExtension':       'md',
                                                     'dialogExtensions':    i18n('Markdown files (*.md *.markdown)')
                                                    },
            BCExportFormat.EXPORT_FMT_DOC_PDF:      {'label':               i18n('Document/PDF'),
                                                     'description':         i18n("Generate a PDF file<br>"
                                                                                 "Document will contain as many pages as necessary to render complete files list with thumbnails"),
                                                     'panelFormat':         3,
                                                     'clipboard':           False,
                                                     'fileExtension':       'pdf',
                                                     'dialogExtensions':    i18n('Portable Document Format (*.pdf)')
                                                    },
            BCExportFormat.EXPORT_FMT_IMG_KRA:      {'label':               i18n('Image/Krita'),
                                                     'description':         i18n("Generate a Krita document<br>"
                                                                                 "Document will contain as many layers as necessary to render complete files list with thumbnails"),
                                                     'panelFormat':         3,
                                                     'clipboard':           False,
                                                     'fileExtension':       'kra',
                                                     'dialogExtensions':    i18n('Krita image (*.kra)')
                                                    },
            BCExportFormat.EXPORT_FMT_IMG_PNG:      {'label':               i18n('Image/PNG'),
                                                     'description':         i18n("Generate a PNG image file<br>"
                                                                                 "Will generate as many PNG files as necessary to render complete files list with thumbnails"),
                                                     'panelFormat':         3,
                                                     'clipboard':           True,
                                                     'fileExtension':       'png',
                                                     'dialogExtensions':    i18n('PNG Image (*.png)')
                                                    },
            BCExportFormat.EXPORT_FMT_IMG_JPG:      {'label':               i18n('Image/JPEG'),
                                                     'description':         i18n("Generate a JPEG image file<br>"
                                                                                 "Will generate as many JPEG files as necessary to render complete files list with thumbnails"),
                                                     'panelFormat':         3,
                                                     'clipboard':           True,
                                                     'fileExtension':       'jpeg',
                                                     'dialogExtensions':    i18n('JPEG Image (*.jpeg *.jpg)')
                                                    }
        }

    FIELDS = {
                                                    # label:        value displayed in listbox
                                                    # tooltip:      tooltip affected to item in list
                                                    # data:         data to return in exported result
                                                    # alignment:    for format that support colupmn alignment, define
                                                    #               data alignment (0: left / 1: right)
                                                    # format:       how to format data (use markdown notation)
                                                    # inList:       visible in selection list or not,
                                                    # selected:     default status in listbox
        'file.thumbnailMD':                         {'label':       i18n('Thumbnail'),
                                                     'toolTip':     i18n('The image thumbnail'),
                                                     'data':        '![](./{extraData[1]}/{os.path.basename(file.thumbnail(extraData[0], BCBaseFile.THUMBTYPE_FILENAME))})',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      False,
                                                     'selected':    True
                                                    },
        'file.path':                                {'label':       i18n('Path'),
                                                     'toolTip':     i18n('The file path'),
                                                     'data':        '{file.path()}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'inList':      True,
                                                     'selected':    True
                                                    },
        'file.name':                                {'label':       i18n('File name'),
                                                     'toolTip':     i18n('The file name, including extension'),
                                                     'data':        '{file.name()}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'inList':      True,
                                                     'selected':    True
                                                    },
        'file.baseName':                            {'label':       i18n('File base name'),
                                                     'toolTip':     i18n('The file name, excluding extension'),
                                                     'data':        '{file.baseName() if not isinstance(file, BCDirectory) else file.name()}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'file.extension':                           {'label':       i18n('File extension'),
                                                     'toolTip':     i18n('The file extension, including dot separator)'),
                                                     'data':        '{file.extension() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'file.fullPathName':                        {'label':       i18n('Full path/file name'),
                                                     'toolTip':     i18n('The complete file name, including path'),
                                                     'data':        '{file.fullPathName()}',
                                                     'alignment':   0,
                                                     'format':      ('`{text}`', ),
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'file.format.short':                        {'label':       i18n('File format (short)'),
                                                     'toolTip':     i18n('The file format (short value)'),
                                                     'data':        '{BCFileManagedFormat.translate(file.format(), True)}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    True
                                                    },
        'file.format.long':                         {'label':       i18n('File format (long)'),
                                                     'toolTip':     i18n('The file format (long value)'),
                                                     'data':        '{BCFileManagedFormat.translate(file.format(), False)}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'modified.datetime':                        {'label':       i18n('Date/Time'),
                                                     'toolTip':     i18n('File date/time (<span style="font-family:''monospace''"><i>yyyy-mm-dd hh:mi:ss</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"dt")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    True
                                                    },
        'modified.date.full':                       {'label':       i18n('Date'),
                                                     'toolTip':     i18n('File date (<span style="font-family:''monospace''"><i>yyyy-mm-dd</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"d")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'modified.date.year':                       {'label':       i18n('Date (year)'),
                                                     'toolTip':     i18n('File date (<i>Year: <span style="font-family:''monospace''">yyyy</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%Y")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'modified.date.month':                      {'label':       i18n('Date (month)'),
                                                     'toolTip':     i18n('File date (<i>Month: <span style="font-family:''monospace''">mm</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%m")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'modified.date.day':                        {'label':       i18n('Date (day)'),
                                                     'toolTip':     i18n('File date (<i>Month: <span style="font-family:''monospace''">dd</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%d")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'modified.time.full':                       {'label':       i18n('Time'),
                                                     'toolTip':     i18n('File time (<span style="font-family:''monospace''"><i>hh:mi:ss</i></span>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"t")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'modified.time.hour':                       {'label':       i18n('Time (hour)'),
                                                     'toolTip':     i18n('File time (<i>Hour (H24): <span style="font-family:''monospace''">hh</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%H")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'modified.time.minute':                     {'label':       i18n('Time (minutes)'),
                                                     'toolTip':     i18n('File time (<i>Minutes: <span style="font-family:''monospace''">mm</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%M")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'modified.time.seconds':                    {'label':       i18n('Date (seconds)'),
                                                     'toolTip':     i18n('File time (<i>Seconds: <span style="font-family:''monospace''">ss</span></i>)'),
                                                     'data':        '{tsToStr(file.lastModificationDateTime(),"%S")}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'size.bytes':                               {'label':       i18n('Size (bytes)'),
                                                     'toolTip':     i18n('File size in bytes'),
                                                     'data':        '{file.size() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'size.unit.decimal':                        {'label':       i18n('Size (best decimal unit)'),
                                                     'toolTip':     i18n('File size, using the best decimal unit (KB, MB, GB)<br/>Size is rounded to 2 decimals'),
                                                     'data':        '{bytesSizeToStr(file.size(), "auto") if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'size.unit.binary':                         {'label':       i18n('Size (best binary unit)'),
                                                     'toolTip':     i18n('File size, using the best binary unit (KiB, MiB, GiB)<br/>Size is rounded to 2 decimals'),
                                                     'data':        '{bytesSizeToStr(file.size(), "autobin") if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    True
                                                    },
        'image.size.full':                          {'label':       i18n('Image size (width x height)'),
                                                     'toolTip':     i18n('The current image size (<span style="font-family:''monospace''"></i>width</i>x<i>height</i></span>)'),
                                                     'data':        '{str(file.imageSize().width()) + "x" + str(file.imageSize().height()) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    True
                                                    },
        'image.size.width':                         {'label':       i18n('Image size (width)'),
                                                     'toolTip':     i18n('The current image size (width)'),
                                                     'data':        '{file.imageSize().width() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'image.size.height':                         {'label':      i18n('Image size (height)'),
                                                     'toolTip':     i18n('The current image size (height)'),
                                                     'data':        '{file.imageSize().height() if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    }
    }


    def __init__(self, title, uicontroller, parent=None):
        super(BCExportFilesDialogBox, self).__init__(parent)

        self.__title = title
        self.__previewLimit = 20

        # defined as global to class...
        self.__extraData = []

        self.__formatPdfImgPaperResolution = 300
        self.__formatPdfImgPaperSizeUnit = "mm"
        self.__formatPdfImgPaperSize = QSizeF(0, 0)
        self.__formatPdfImgPaperOrientation = BCExportFilesDialogBox.ORIENTATION_PORTRAIT
        self.__formatPdfImgNbProperties = 0
        self.__formatPdfImgFontSize = 10

        self.__blockedSlots = True

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

            self.lblPerimeterSelectPathNfo.setText(i18n(f"<b>{self.__getPath()}</b> (Files: {self.__fileNfo[2]}, Directories: {self.__fileNfo[1]})"))
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
                if BCExportFilesDialogBox.FIELDS[field]['inList']:
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

            self.lblFormatDocImgPreview.paintEvent = self.__updateFormatDocImgConfigurationPreview

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

            # --- DOC/PDF -- IMG/* interface ---
            # - - - Page list
            self.lvFormatDocImgRef.itemSelectionChanged.connect(self.__slotPageFormatDocImgRefChanged)

            self.__itemFormatDocImgRefPageSetup = QListWidgetItem(QIcon(":/images/page_setup"), "Page setup")
            self.__itemFormatDocImgRefPageSetup.setData(Qt.UserRole, BCExportFilesDialogBox.__PANEL_FORMAT_DOCIMG_PAGESETUP)
            self.__itemFormatDocImgRefPageLayout = QListWidgetItem(QIcon(":/images/page_layout"), "Page layout")
            self.__itemFormatDocImgRefPageLayout.setData(Qt.UserRole, BCExportFilesDialogBox.__PANEL_FORMAT_DOCIMG_PAGELAYOUT)
            self.__itemFormatDocImgRefThumbConfig = QListWidgetItem(QIcon(":/images/large_view"), "Thumbnail")
            self.__itemFormatDocImgRefThumbConfig.setData(Qt.UserRole, BCExportFilesDialogBox.__PANEL_FORMAT_DOCIMG_THUMBCONFIG)

            self.lvFormatDocImgRef.addItem(self.__itemFormatDocImgRefPageSetup)
            self.lvFormatDocImgRef.addItem(self.__itemFormatDocImgRefPageLayout)
            self.lvFormatDocImgRef.addItem(self.__itemFormatDocImgRefThumbConfig)

            # - - - Page setup
            self.cbxFormatDocImgPaperResolution.clear()
            self.cbxFormatDocImgPaperUnit.clear()
            self.cbxFormatDocImgPaperSize.clear()

            for resolution in BCExportFilesDialogBox.IMAGE_RESOLUTIONS:
                self.cbxFormatDocImgPaperResolution.addItem(resolution)
            self.cbxFormatDocImgPaperResolution.setCurrentIndex(3) # 300dpi

            self.cbxFormatDocImgPaperResolution.currentIndexChanged.connect(self.__slotPageFormatDocImgPageSetupResolutionChanged)
            self.cbxFormatDocImgPaperUnit.currentIndexChanged.connect(self.__slotPageFormatDocImgPageSetupUnitChanged)
            self.cbxFormatDocImgPaperSize.currentIndexChanged.connect(self.__slotPageFormatDocImgPageSetupSizeChanged)
            self.cbxFormatDocImgPaperOrientation.currentIndexChanged.connect(self.__slotPageFormatDocImgPageSetupOrientationChanged)

            self.dsbFormatDocImgMarginsLeft.valueChanged.connect(self.__slotPageFormatDocImgPageSetupMarginLChanged)
            self.dsbFormatDocImgMarginsRight.valueChanged.connect(self.__slotPageFormatDocImgPageSetupMarginRChanged)
            self.dsbFormatDocImgMarginsTop.valueChanged.connect(self.__slotPageFormatDocImgPageSetupMarginTChanged)
            self.dsbFormatDocImgMarginsBottom.valueChanged.connect(self.__slotPageFormatDocImgPageSetupMarginBChanged)
            self.cbFormatDocImgMarginsLinked.toggled.connect(self.__slotPageFormatDocImgPageSetupMarginLinkChanged)

            # - - - Page layout
            self.cbFormatDocImgHeader.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.cbFormatDocImgFooter.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.cbFormatDocImgFPageNotes.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.cbFormatDocImgFPageLayoutPreview.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.bcsteFormatDocImgHeader.textChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.bcsteFormatDocImgFooter.textChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.bcsteFormatDocImgFPageNotes.textChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.sbFormatDocImgThumbsPerRow.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.dsbFormatDocImgThumbsSpacing.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.bcsteFormatDocImgHeader.setTitle(f"{self.__title}::{i18n('Document/PDF - Header')}")
            self.bcsteFormatDocImgFooter.setTitle(f"{self.__title}::{i18n('Document/PDF - Footer')}")
            self.bcsteFormatDocImgFPageNotes.setTitle(f"{self.__title}::{i18n('Document/PDF - First page layout')}")

            # - - - Thumb layout
            self.cbxFormatDocImgPropertiesPosition.currentIndexChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.fcbxFormatDocImgPropertiesFontFamily.currentFontChanged.connect(self.__slotPageFormatDocImgPropertiesFontChanged)
            self.dsbFormatDocImgPropertiesFontSize.valueChanged.connect(self.__slotPageFormatDocImgPropertiesFontChanged)

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

        self.__blockSlot(False)

    # -- Utils -----------------------------------------------------------------
    def convertSize(self, value, fromUnit, toUnit, roundValue=None):
        """Return converted value from given `fromUnit` to `toUnit`"""
        if roundValue is None:
            roundValue = BCExportFilesDialogBox.UNITS[toUnit]['marginDec']
        if fromUnit == 'mm':
            if toUnit == 'cm':
                return round(value/10, roundValue)
            elif toUnit == 'in':
                return round(value/25.4, roundValue)
            elif toUnit == 'px':
                return round(self.convertSize(value, fromUnit, 'in') * self.__formatPdfImgPaperResolution, roundValue)
        elif fromUnit == 'cm':
            if toUnit == 'mm':
                return round(value*10, roundValue)
            elif toUnit == 'in':
                return round(value/2.54, roundValue)
            elif toUnit == 'px':
                return round(self.convertSize(value, fromUnit, 'in') * self.__formatPdfImgPaperResolution, roundValue)
        elif fromUnit == 'in':
            if toUnit == 'mm':
                return round(value*25.4, roundValue)
            elif toUnit == 'cm':
                return round(value*2.54, roundValue)
            elif toUnit == 'px':
                return round(value * self.__formatPdfImgPaperResolution, roundValue)
        elif fromUnit == 'px':
            if toUnit == 'mm':
                return round(self.convertSize(value, fromUnit, 'in')*25.4, roundValue)
            elif toUnit == 'cm':
                return round(self.convertSize(value, fromUnit, 'in')*2.54, roundValue)
            elif toUnit == 'in':
                return round(value / self.__formatPdfImgPaperResolution, roundValue)
        elif fromUnit == 'pt':
            if toUnit == 'mm':
                return round(value * 0.35277777777777775, roundValue)   # 25.4/72
            elif toUnit == 'cm':
                return round(value * 0.035277777777777775, roundValue)  #2.54/72
            elif toUnit == 'in':
                return round(value / 72, roundValue)
            elif toUnit == 'px':
                return round(self.__formatPdfImgPaperResolution * self.convertSize(value, fromUnit, 'in')/72, roundValue)
        # all other combination are not valid, return initial value
        return value

    def __blockSlot(self, value):
        self.__blockedSlots = value

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

        def defaultDocImg():
            # --- DOC/PDF interface ---
            self.swFormatDocImgRef.setCurrentIndex(0)
            self.lvFormatDocImgRef.setCurrentRow(0)
            self.cbxFormatDocImgPaperUnit.setCurrentIndex(0)        # 'mm'
            self.cbxFormatDocImgPaperSize.setCurrentIndex(2)        # 'A4'
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(0) # 'portrait'
            self.dsbFormatDocImgMarginsLeft.setValue(20.0)
            self.dsbFormatDocImgMarginsRight.setValue(20.0)
            self.dsbFormatDocImgMarginsTop.setValue(20.0)
            self.dsbFormatDocImgMarginsBottom.setValue(20.0)
            self.cbFormatDocImgMarginsLinked.setChecked(False)

            self.cbFormatDocImgHeader.setChecked(True)
            self.cbFormatDocImgFooter.setChecked(True)
            self.cbFormatDocImgFPageNotes.setChecked(True)
            self.cbFormatDocImgFPageLayoutPreview.setChecked(True)

            self.bcsteFormatDocImgHeader.setPlainText('')
            self.bcsteFormatDocImgFooter.setPlainText('')
            self.bcsteFormatDocImgFPageNotes.setPlainText('')

            self.sbFormatDocImgThumbsPerRow.setValue(2)
            self.dsbFormatDocImgThumbsSpacing.setValue(5.0)
            self.cbxFormatDocImgPropertiesPosition.setCurrentIndex(2)   # right

            self.fcbxFormatDocImgPropertiesFontFamily.setCurrentFont(QFont('DejaVu sans'))
            self.dsbFormatDocImgPropertiesFontSize.setValue(10)

            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()

        # --- ALL format ---
        self.cbxFormat.setCurrentIndex(BCExportFormat.EXPORT_FMT_TEXT)
        self.__slotPageFormatFormatChanged()

        # -- pages
        defaultText()
        defaultTextMd()
        defaultTextCsv()
        defaultDocImg()

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

        def defaultDocPdf():
            # --- DOC/PDF interface ---
            paperSize=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPERSIZE.id())
            paperIndex=2
            for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
                if self.cbxFormatDocImgPaperSize.itemData(itemIndex) == paperSize:
                    paperIndex = itemIndex
                    break

            unit=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_UNIT.id())
            unitIndex=0
            for itemIndex in range(self.cbxFormatDocImgPaperUnit.count()):
                if self.cbxFormatDocImgPaperUnit.itemData(itemIndex) == unit:
                    unitIndex = itemIndex
                    break

            self.swFormatDocImgRef.setCurrentIndex(0)
            self.lvFormatDocImgRef.setCurrentRow(0)
            self.cbxFormatDocImgPaperUnit.setCurrentIndex(unitIndex)
            self.cbxFormatDocImgPaperSize.setCurrentIndex(paperIndex)
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_ORIENTATION.id()))
            self.dsbFormatDocImgMarginsLeft.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LEFT.id()))
            self.dsbFormatDocImgMarginsRight.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_RIGHT.id()))
            self.dsbFormatDocImgMarginsTop.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_TOP.id()))
            self.dsbFormatDocImgMarginsBottom.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_BOTTOM.id()))
            self.cbFormatDocImgMarginsLinked.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LINKED.id()))

            self.cbFormatDocImgHeader.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_ACTIVE.id()))
            self.cbFormatDocImgFooter.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_ACTIVE.id()))
            self.cbFormatDocImgFPageNotes.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGLAYOUT_ACTIVE.id()))
            self.cbFormatDocImgFPageLayoutPreview.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGLAYOUT_PREVIEW.id()))

            self.bcsteFormatDocImgHeader.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_CONTENT.id()))
            self.bcsteFormatDocImgFooter.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_CONTENT.id()))
            self.bcsteFormatDocImgFPageNotes.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGLAYOUT_CONTENT.id()))

            self.sbFormatDocImgThumbsPerRow.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_APGLAYOUT_THUMPROW.id()))
            self.dsbFormatDocImgThumbsSpacing.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_APGLAYOUT_THUMSP.id()))
            self.cbxFormatDocImgPropertiesPosition.setCurrentIndex(['none','left','right','top','bottom'].index(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_APGLAYOUT_PROPPOS.id())))

            self.fcbxFormatDocImgPropertiesFontFamily.setCurrentFont(QFont(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_APGLAYOUT_PROPFNAME.id())))
            self.dsbFormatDocImgPropertiesFontSize.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_APGLAYOUT_PROPFSIZE.id()))

            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()

        def defaultImgKra():
            # --- IMG/KRA interface ---
            imageResolution=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_RESOLUTION.id())
            imageIndex=3
            for itemIndex in range(self.cbxFormatDocImgPaperResolution.count()):
                if self.cbxFormatDocImgPaperResolution.itemData(itemIndex) == imageResolution:
                    imageIndex = itemIndex
                    break

            paperSize=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPERSIZE.id())
            paperIndex=2
            for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
                if self.cbxFormatDocImgPaperSize.itemData(itemIndex) == paperSize:
                    paperIndex = itemIndex
                    break

            unit=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_UNIT.id())
            unitIndex=0
            for itemIndex in range(self.cbxFormatDocImgPaperUnit.count()):
                if self.cbxFormatDocImgPaperUnit.itemData(itemIndex) == unit:
                    unitIndex = itemIndex
                    break

            self.swFormatDocImgRef.setCurrentIndex(0)
            self.lvFormatDocImgRef.setCurrentRow(0)
            self.cbxFormatDocImgPaperResolution.setCurrentIndex(imageIndex)
            self.cbxFormatDocImgPaperUnit.setCurrentIndex(unitIndex)
            self.cbxFormatDocImgPaperSize.setCurrentIndex(paperIndex)
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_ORIENTATION.id()))
            self.dsbFormatDocImgMarginsLeft.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LEFT.id()))
            self.dsbFormatDocImgMarginsRight.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_RIGHT.id()))
            self.dsbFormatDocImgMarginsTop.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_TOP.id()))
            self.dsbFormatDocImgMarginsBottom.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_BOTTOM.id()))
            self.cbFormatDocImgMarginsLinked.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LINKED.id()))

            self.cbFormatDocImgHeader.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_ACTIVE.id()))
            self.cbFormatDocImgFooter.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_ACTIVE.id()))
            self.cbFormatDocImgFPageNotes.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGLAYOUT_ACTIVE.id()))
            self.cbFormatDocImgFPageLayoutPreview.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGLAYOUT_PREVIEW.id()))

            self.bcsteFormatDocImgHeader.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_CONTENT.id()))
            self.bcsteFormatDocImgFooter.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_CONTENT.id()))
            self.bcsteFormatDocImgFPageNotes.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGLAYOUT_CONTENT.id()))

            self.sbFormatDocImgThumbsPerRow.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_APGLAYOUT_THUMPROW.id()))
            self.dsbFormatDocImgThumbsSpacing.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_APGLAYOUT_THUMSP.id()))
            self.cbxFormatDocImgPropertiesPosition.setCurrentIndex(['none','left','right','top','bottom'].index(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_APGLAYOUT_PROPPOS.id())))

            self.fcbxFormatDocImgPropertiesFontFamily.setCurrentFont(QFont(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_APGLAYOUT_PROPFNAME.id())))
            self.dsbFormatDocImgPropertiesFontSize.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_APGLAYOUT_PROPFSIZE.id()))

            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()

        def defaultImgPng():
            # --- IMG/PNG interface ---
            imageResolution=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_RESOLUTION.id())
            imageIndex=3
            for itemIndex in range(self.cbxFormatDocImgPaperResolution.count()):
                if self.cbxFormatDocImgPaperResolution.itemData(itemIndex) == imageResolution:
                    imageIndex = itemIndex
                    break

            paperSize=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPERSIZE.id())
            paperIndex=2
            for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
                if self.cbxFormatDocImgPaperSize.itemData(itemIndex) == paperSize:
                    paperIndex = itemIndex
                    break

            unit=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_UNIT.id())
            unitIndex=0
            for itemIndex in range(self.cbxFormatDocImgPaperUnit.count()):
                if self.cbxFormatDocImgPaperUnit.itemData(itemIndex) == unit:
                    unitIndex = itemIndex
                    break

            self.swFormatDocImgRef.setCurrentIndex(0)
            self.lvFormatDocImgRef.setCurrentRow(0)
            self.cbxFormatDocImgPaperResolution.setCurrentIndex(imageIndex)
            self.cbxFormatDocImgPaperUnit.setCurrentIndex(unitIndex)
            self.cbxFormatDocImgPaperSize.setCurrentIndex(paperIndex)
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_ORIENTATION.id()))
            self.dsbFormatDocImgMarginsLeft.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LEFT.id()))
            self.dsbFormatDocImgMarginsRight.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_RIGHT.id()))
            self.dsbFormatDocImgMarginsTop.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_TOP.id()))
            self.dsbFormatDocImgMarginsBottom.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_BOTTOM.id()))
            self.cbFormatDocImgMarginsLinked.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LINKED.id()))

            self.cbFormatDocImgHeader.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_ACTIVE.id()))
            self.cbFormatDocImgFooter.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_ACTIVE.id()))
            self.cbFormatDocImgFPageNotes.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGLAYOUT_ACTIVE.id()))
            self.cbFormatDocImgFPageLayoutPreview.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGLAYOUT_PREVIEW.id()))

            self.bcsteFormatDocImgHeader.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_CONTENT.id()))
            self.bcsteFormatDocImgFooter.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_CONTENT.id()))
            self.bcsteFormatDocImgFPageNotes.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGLAYOUT_CONTENT.id()))

            self.sbFormatDocImgThumbsPerRow.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_APGLAYOUT_THUMPROW.id()))
            self.dsbFormatDocImgThumbsSpacing.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_APGLAYOUT_THUMSP.id()))
            self.cbxFormatDocImgPropertiesPosition.setCurrentIndex(['none','left','right','top','bottom'].index(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_APGLAYOUT_PROPPOS.id())))

            self.fcbxFormatDocImgPropertiesFontFamily.setCurrentFont(QFont(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_APGLAYOUT_PROPFNAME.id())))
            self.dsbFormatDocImgPropertiesFontSize.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_APGLAYOUT_PROPFSIZE.id()))

            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()

        def defaultImgJpg():
            # --- IMG/JPG interface ---
            imageResolution=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_RESOLUTION.id())
            imageIndex=3
            for itemIndex in range(self.cbxFormatDocImgPaperResolution.count()):
                if self.cbxFormatDocImgPaperResolution.itemData(itemIndex) == imageResolution:
                    imageIndex = itemIndex
                    break

            paperSize=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPERSIZE.id())
            paperIndex=2
            for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
                if self.cbxFormatDocImgPaperSize.itemData(itemIndex) == paperSize:
                    paperIndex = itemIndex
                    break

            unit=self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_UNIT.id())
            unitIndex=0
            for itemIndex in range(self.cbxFormatDocImgPaperUnit.count()):
                if self.cbxFormatDocImgPaperUnit.itemData(itemIndex) == unit:
                    unitIndex = itemIndex
                    break

            self.swFormatDocImgRef.setCurrentIndex(0)
            self.lvFormatDocImgRef.setCurrentRow(0)
            self.cbxFormatDocImgPaperResolution.setCurrentIndex(imageIndex)
            self.cbxFormatDocImgPaperUnit.setCurrentIndex(unitIndex)
            self.cbxFormatDocImgPaperSize.setCurrentIndex(paperIndex)
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_ORIENTATION.id()))
            self.dsbFormatDocImgMarginsLeft.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LEFT.id()))
            self.dsbFormatDocImgMarginsRight.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_RIGHT.id()))
            self.dsbFormatDocImgMarginsTop.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_TOP.id()))
            self.dsbFormatDocImgMarginsBottom.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_BOTTOM.id()))
            self.cbFormatDocImgMarginsLinked.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LINKED.id()))

            self.cbFormatDocImgHeader.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_ACTIVE.id()))
            self.cbFormatDocImgFooter.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_ACTIVE.id()))
            self.cbFormatDocImgFPageNotes.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGLAYOUT_ACTIVE.id()))
            self.cbFormatDocImgFPageLayoutPreview.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGLAYOUT_PREVIEW.id()))

            self.bcsteFormatDocImgHeader.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_CONTENT.id()))
            self.bcsteFormatDocImgFooter.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_CONTENT.id()))
            self.bcsteFormatDocImgFPageNotes.setHtml(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGLAYOUT_CONTENT.id()))

            self.sbFormatDocImgThumbsPerRow.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_APGLAYOUT_THUMPROW.id()))
            self.dsbFormatDocImgThumbsSpacing.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_APGLAYOUT_THUMSP.id()))
            self.cbxFormatDocImgPropertiesPosition.setCurrentIndex(['none','left','right','top','bottom'].index(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_APGLAYOUT_PROPPOS.id())))

            self.fcbxFormatDocImgPropertiesFontFamily.setCurrentFont(QFont(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_APGLAYOUT_PROPFNAME.id())))
            self.dsbFormatDocImgPropertiesFontSize.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_APGLAYOUT_PROPFSIZE.id()))

            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()

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
        defaultDocPdf()
        defaultImgKra()
        defaultImgPng()
        defaultImgJpg()

    def __initFormatDocImgLists(self):
        wasBlocked = self.__blockedSlots
        self.__blockSlot(True)

        self.cbxFormatDocImgPaperUnit.clear()
        self.cbxFormatDocImgPaperSize.clear()

        fmtIndex = self.cbxFormat.currentIndex()

        for paperSize in BCExportFilesDialogBox.PAPER_SIZES:
            #if fmtIndex in BCExportFilesDialogBox.UNITS[unit]['format']:
            self.cbxFormatDocImgPaperSize.addItem(paperSize, paperSize)

        for unit in BCExportFilesDialogBox.UNITS:
            if fmtIndex in BCExportFilesDialogBox.UNITS[unit]['format']:
                self.cbxFormatDocImgPaperUnit.addItem(BCExportFilesDialogBox.UNITS[unit]['label'], unit)

        self.cbxFormatDocImgPaperSize.setCurrentIndex(2) # A4
        self.__blockSlot(wasBlocked)

    def __updateFormatDocImgPaperSizeList(self, unit=None, orientation=None):
        """Update the cbxFormatDocImgPaperSize list"""

        if unit is None:
            unit = self.__formatPdfImgPaperSizeUnit

        if orientation is None:
            orientation = self.__formatPdfImgPaperOrientation

        unitFmt=BCExportFilesDialogBox.UNITS[unit]['fmt']

        for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
            paperSize = self.cbxFormatDocImgPaperSize.itemData(itemIndex)
            size=BCExportFilesDialogBox.PAPER_SIZES[paperSize][unit]

            if unit == 'px':
                # in this case, unit is in inch
                # need t oconvert to pixels
                size = QSizeF(size.width() * self.__formatPdfImgPaperResolution, size.height() * self.__formatPdfImgPaperResolution)

            if self.__formatPdfImgPaperOrientation == BCExportFilesDialogBox.ORIENTATION_PORTRAIT:
                self.cbxFormatDocImgPaperSize.setItemText(itemIndex, f"{paperSize} - {size.width():{unitFmt}}x{size.height():{unitFmt}}")
            else:
                self.cbxFormatDocImgPaperSize.setItemText(itemIndex, f"{paperSize} - {size.height():{unitFmt}}x{size.width():{unitFmt}}")

    def __updateFormatDocImgConfigurationPreview(self, event):
        """Generate a configuration preview and update it"""
        # Mathod is paintEvent() for widget lblFormatDocImgPreview

        def setActiveColor(activePage):
            if self.swFormatDocImgRef.currentIndex() == activePage:
                pen.setColor(Qt.blue)
                brush.setColor(Qt.blue)
            else:
                pen.setColor(Qt.lightGray)
                brush.setColor(Qt.lightGray)

        def drawMargins():
            # first page / margins
            pen.setStyle(Qt.DashLine)
            setActiveColor(0)
            painter.setPen(pen)

            painter.drawLine(drawingArea.left(), previewRect.top(), drawingArea.left(), previewRect.bottom())
            painter.drawLine(drawingArea.right(), previewRect.top(), drawingArea.right(), previewRect.bottom())
            painter.drawLine(previewRect.left(), drawingArea.top(), previewRect.right(), drawingArea.top())
            painter.drawLine(previewRect.left(), drawingArea.bottom(), previewRect.right(), drawingArea.bottom())

            drawingArea.setLeft(drawingArea.left() + 2)
            drawingArea.setRight(drawingArea.right() - 3)
            drawingArea.setTop(drawingArea.top() + 2)
            drawingArea.setBottom(drawingArea.bottom() - 3)

        def drawLayout():
            pen.setStyle(Qt.SolidLine)
            brush.setStyle(Qt.DiagCrossPattern)
            setActiveColor(1)
            painter.setPen(pen)

            # ----------------------------------------------------------------------
            # Header
            if self.cbFormatDocImgHeader.isChecked() and self.bcsteFormatDocImgHeader.toPlainText() != '':
                # represent Header
                for textRow in range(self.bcsteFormatDocImgHeader.toPlainText().count("\n") + 1):
                    painter.fillRect( drawingArea.left(), drawingArea.top(), drawingArea.width(), characterHeight, brush)
                    painter.drawRect( drawingArea.left(), drawingArea.top(), drawingArea.width(), characterHeight )

                    drawingArea.setTop(drawingArea.top() + characterHeight + 2)

                # +5mm space after header
                drawingArea.setTop(drawingArea.top() + characterHeight + 2)

            # ----------------------------------------------------------------------
            # Footer
            footerHeight = 0
            if self.cbFormatDocImgFooter.isChecked() and self.bcsteFormatDocImgFooter.toPlainText() != '':
                # calculate footer height
                footerHeight = characterHeight - 2

                for textRow in range(self.bcsteFormatDocImgFooter.toPlainText().count("\n") + 1):
                    painter.fillRect( drawingArea.left(), drawingArea.bottom() - footerHeight, drawingArea.width(), characterHeight, brush)
                    painter.drawRect( drawingArea.left(), drawingArea.bottom() - footerHeight, drawingArea.width(), characterHeight )

                    footerHeight+=characterHeight + 2

                drawingArea.setBottom(drawingArea.bottom() - footerHeight)

            # ----------------------------------------------------------------------
            # First page layout
            if self.cbFormatDocImgFPageLayoutPreview.isChecked() and self.cbFormatDocImgFPageNotes.isChecked() and self.bcsteFormatDocImgFPageNotes.toPlainText() != '':
                # represent First page layout
                for textRow in range(self.bcsteFormatDocImgFPageNotes.toPlainText().count("\n") + 1):
                    painter.fillRect( drawingArea.left(), drawingArea.top(), drawingArea.width(), characterHeight, brush)
                    painter.drawRect( drawingArea.left(), drawingArea.top(), drawingArea.width(), characterHeight )

                    drawingArea.setTop(drawingArea.top() + characterHeight + 2)

                # +5mm space after layout
                drawingArea.setTop(drawingArea.top() + characterHeight + 2)

        def getThumbnailCellPixmap(propertiesPosition, cellWidth, cellHeight, thumbSize, textWidth, textHeight, textRows):
            # return a pixmap

            # draw one cell in a pixmap and then, paste same pixmap for each cell
            imageThumb = QImage(cellWidth, cellHeight, QImage.Format_ARGB32)
            imageThumb.fill(Qt.transparent)
            pixmapThumb = QPixmap.fromImage(imageThumb)

            painterThumb = QPainter()
            painterThumb.begin(pixmapThumb)

            pen.setStyle(Qt.DashLine)
            brush.setStyle(Qt.SolidPattern)

            setActiveColor(1)

            #
            if propertiesPosition == 1:
                # left
                imgLeft = 2 + textWidth
                imgTop = 2
                textLeft = 2
                textTop = 2
                textWidth-=3
            elif propertiesPosition == 2:
                # right
                imgLeft = 2
                imgTop = 2
                textLeft = thumbSize - 1
                textTop = 2
                textWidth-=3
            elif propertiesPosition == 3:
                # top
                imgLeft = 2
                imgTop = 2 + textHeight
                textLeft = 2
                textTop = 2
                textWidth-=5
            elif propertiesPosition == 4:
                # bottom
                imgLeft = 2
                imgTop = 2
                textLeft = 2
                textTop = 2 + thumbSize
                textWidth-=5
            else:
                imgLeft = 2
                imgTop = 2
                textLeft = 0
                textTop = 0

            # cell bounds
            painterThumb.setPen(pen)
            painterThumb.drawRect(0, 0, cellWidth - 1, cellHeight - 1)

            setActiveColor(2)

            painterThumb.setPen(pen)

            # thumb image
            painterThumb.drawPixmap(imgLeft, imgTop, QIcon(':/images/large_view').pixmap(thumbSize - 5, thumbSize - 5))

            painterThumb.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painterThumb.fillRect(imgLeft, imgTop, thumbSize - 5, thumbSize - 5, brush)

            # thumbnail bounds
            painterThumb.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painterThumb.drawRect(imgLeft, imgTop, thumbSize - 5, thumbSize - 5)

            pen.setStyle(Qt.SolidLine)
            brush.setStyle(Qt.DiagCrossPattern)
            painterThumb.setPen(pen)

            # texts
            if propertiesPosition > 0:
                for row in range(textRows):
                    painterThumb.fillRect( textLeft, textTop, textWidth, characterHeight, brush)
                    painterThumb.drawRect( textLeft, textTop, textWidth, characterHeight )

                    textTop+=characterHeight+2

            painterThumb.end()

            return pixmapThumb

        def drawThumbnails():
            thumbPerRow = self.sbFormatDocImgThumbsPerRow.value()
            thumbSpacing = ratioPaperPreview * self.dsbFormatDocImgThumbsSpacing.value()
            propertiesPosition = self.cbxFormatDocImgPropertiesPosition.currentIndex()

            # cell width for a thumnbail is (drawing area width - spacing * (nb cells - 1)) / nb cell
            cellWidth = int(round( (drawingArea.width() - thumbSpacing * (thumbPerRow - 1) ) / thumbPerRow, 0))

            # height calculation is more complicated; it depends of:
            # - number of properties (with 1 property per line)
            # - position of properties

            textHeight = self.__formatPdfImgNbProperties * (characterHeight + 2)

            if propertiesPosition == 0:
                # no properties to display
                # then, height = width
                cellHeight = cellWidth

                # thumb size = 100% of cell
                thumbSize = cellWidth

                # no text
                textWidth = 0
                textHeight = 0
            elif propertiesPosition in [1, 2]:
                # left/right position
                # in this case, consider that image size = 50% of cellWidth
                thumbSize = (cellWidth - characterHeight)//2

                # cell height is the greatest height between thumbnail and text
                cellHeight = max(textHeight, thumbSize)

                # text width is 50% of cell
                textWidth = cellWidth - thumbSize
            else:
                # top/bottom position
                # in this case, consider that image size = cellWidth - textHeight; but can't be smaller than 25% of cell width
                thumbSize = max(cellWidth - textHeight - 2, cellWidth * 0.25)

                # cell height is the sum of thumb height and text height
                cellHeight = textHeight + thumbSize + 2

                # text width is 10% of cell
                textWidth = cellWidth

            pixmapThumb = getThumbnailCellPixmap(propertiesPosition, cellWidth, cellHeight, thumbSize, textWidth, textHeight, self.__formatPdfImgNbProperties)

            while drawingArea.top() + cellHeight <= drawingArea.bottom():
                offsetLeft = 0
                for column in range(thumbPerRow):
                    painter.drawPixmap(drawingArea.left() + offsetLeft, drawingArea.top(), pixmapThumb)

                    offsetLeft+=cellWidth + thumbSpacing

                drawingArea.setTop(drawingArea.top() + cellHeight + thumbSpacing)

        # margin to border / arbitrary 6px
        margin = 6
        shadowOffset = 4

        # paper size w/h ratio
        ratioPaperSize = self.__formatPdfImgPaperSize.width() / self.__formatPdfImgPaperSize.height()

        if self.__formatPdfImgPaperOrientation == BCExportFilesDialogBox.ORIENTATION_PORTRAIT:
            previewHeight = round(self.lblFormatDocImgPreview.height() - 2 * margin, 0)
            previewWidth = round(previewHeight * ratioPaperSize, 0)
        else:
            previewWidth = self.lblFormatDocImgPreview.width() - 2 * margin
            previewHeight = round(previewWidth / ratioPaperSize, 0)

        ratioPaperPreview = previewWidth / self.__formatPdfImgPaperSize.width()

        previewRect = QRect((self.lblFormatDocImgPreview.width() - previewWidth)/2,
                            (self.lblFormatDocImgPreview.height() - previewHeight)/2,
                            previewWidth,
                            previewHeight
                        )

        # nb pixels used to represent one text line in preview
        characterHeight = round(ratioPaperPreview * self.convertSize(self.__formatPdfImgFontSize, 'pt', self.__formatPdfImgPaperSizeUnit, 6), 0)

        # ----------------------------------------------------------------------
        # initialise a default pen
        pen = QPen()
        pen.setStyle(Qt.SolidLine)
        pen.setWidth(1)
        pen.setColor(Qt.darkGray)

        brush = QBrush()

        # ----------------------------------------------------------------------
        # start rendering preview
        painter = QPainter(self.lblFormatDocImgPreview)

        painter.setPen(pen)

        # ----------------------------------------------------------------------
        # paper shadow
        painter.fillRect(previewRect.left() + shadowOffset, previewRect.top() + shadowOffset, previewRect.width(), previewRect.height(), QColor(0x202020))

        # ----------------------------------------------------------------------
        # Paper white
        painter.fillRect(previewRect, Qt.white)


        # ----------------------------------------------------------------------
        # Initialise drawing area rect
        drawingArea = QRect(QPoint(previewRect.left() + round(self.dsbFormatDocImgMarginsLeft.value() * ratioPaperPreview, 0),
                                   previewRect.top() + round(self.dsbFormatDocImgMarginsTop.value() * ratioPaperPreview, 0)),
                            QPoint(1 + previewRect.right() - round(self.dsbFormatDocImgMarginsRight.value() * ratioPaperPreview, 0),
                                   1 + previewRect.bottom() - round(self.dsbFormatDocImgMarginsBottom.value() * ratioPaperPreview, 0)))

        # ----------------------------------------------------------------------
        # Margins
        drawMargins()

        # ----------------------------------------------------------------------
        # Header / Footer / First page layout
        drawLayout()

        # ----------------------------------------------------------------------
        # Thumbnails
        drawThumbnails()


        # paper border limit
        pen.setStyle(Qt.SolidLine)
        pen.setColor(Qt.darkGray)
        painter.setPen(pen)
        painter.drawRect(previewRect)

    def __updateFormatDocImgMargins(self):
        """Calculate maximum margins size according to paper size and unit"""
        # maximum value is set to 50% of paper size
        roundDec = BCExportFilesDialogBox.UNITS[self.__formatPdfImgPaperSizeUnit]['marginDec']

        self.dsbFormatDocImgMarginsLeft.setMaximum(round(self.__formatPdfImgPaperSize.width() * 0.5, roundDec))
        self.dsbFormatDocImgMarginsRight.setMaximum(round(self.__formatPdfImgPaperSize.width() * 0.5, roundDec))
        self.dsbFormatDocImgMarginsTop.setMaximum(round(self.__formatPdfImgPaperSize.height() * 0.5, roundDec))
        self.dsbFormatDocImgMarginsBottom.setMaximum(round(self.__formatPdfImgPaperSize.height() * 0.5, roundDec))

        self.dsbFormatDocImgThumbsSpacing.setMaximum(round(self.__formatPdfImgPaperSize.width() * 0.25, roundDec))

    # -- slots
    def __slotPageFormatFormatChanged(self, index=None):
        # update current format page
        if index is None:
            index = self.cbxFormat.currentIndex()

        text = BCExportFilesDialogBox.FMT_PROPERTIES[index]['label']

        self.lblFormatDescription.setText(BCExportFilesDialogBox.FMT_PROPERTIES[index]['description'])
        self.lblFormatOptions.setText( i18n(f"Options for <i>{text}</i> format") )
        self.swFormatProperties.setCurrentIndex(BCExportFilesDialogBox.FMT_PROPERTIES[index]['panelFormat'])

        if index in [BCExportFormat.EXPORT_FMT_DOC_PDF,
                     BCExportFormat.EXPORT_FMT_IMG_KRA,
                     BCExportFormat.EXPORT_FMT_IMG_JPG,
                     BCExportFormat.EXPORT_FMT_IMG_PNG]:
            if index == BCExportFormat.EXPORT_FMT_DOC_PDF:
                self.lblFormatDocImgPaperOrImage.setText(i18n('Paper'))
                self.lblFormatDocImgPaperResolution.setVisible(False)
                self.cbxFormatDocImgPaperResolution.setVisible(False)
            else:
                self.lblFormatDocImgPaperOrImage.setText(i18n('Image'))
                self.lblFormatDocImgPaperResolution.setVisible(True)
                self.cbxFormatDocImgPaperResolution.setVisible(True)
            self.__initFormatDocImgLists()
            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextLayoutUserDefined(self, checked=None):
        # user defined layout option ahs been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextLayoutUserDefined.isChecked()

        self.teFormatTextLayoutUserDefined.setEnabled(checked)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextBordersCheck(self, checked=None):
        # user defined borders option ahs been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextBorders.isChecked()

        if not checked:
            self.rbFormatTextBorderNone.setChecked(True)

        self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextBordersStyleCheck(self, checked=None):
        self.cbFormatTextBorders.setChecked(not self.rbFormatTextBorderNone.isChecked())
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextMinWidthCheck(self, checked=None):
        # State of checkbox Minimum width has been changed
        if checked is None:
            checked = self.cbFormatTextMinWidth.isChecked()

        self.hsFormatTextMinWidth.setEnabled(checked)
        self.spFormatTextMinWidth.setEnabled(checked)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextMaxWidthCheck(self, checked=None):
        # State of checkbox Maximum width has been changed
        if checked is None:
            checked = self.cbFormatTextMaxWidth.isChecked()

        self.hsFormatTextMaxWidth.setEnabled(checked)
        self.spFormatTextMaxWidth.setEnabled(checked)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextMinWidthChanged(self, value=None):
        # Value of Minimum width has changed
        # > ensure that's not greater than maximum witdh
        if value is None:
            value = self.hsFormatTextMinWidth.value()

        if value > self.hsFormatTextMaxWidth.value():
            self.hsFormatTextMaxWidth.setValue(value)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextMaxWidthChanged(self, value=None):
        # Value of Maximum width has changed
        # > ensure that's not greater than minimum witdh
        if value is None:
            value = self.hsFormatTextMaxWidth.value()

        if value < self.hsFormatTextMinWidth.value():
            self.hsFormatTextMinWidth.setValue(value)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextMDLayoutUserDefined(self, checked=None):
        # user defined layout option has been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextMDLayoutUserDefined.isChecked()

        self.teFormatTextMDLayoutUserDefined.setEnabled(checked)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatTextMDIncludeThumbnails(self, checked=None):
        # include thumbnail in md export has been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextMDIncludeThumbnails.isChecked()

        self.cbxFormatTextMDThumbnailsSize.setEnabled(checked)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgRefChanged(self):
        """Set page according to current configuration type"""
        self.swFormatDocImgRef.setCurrentIndex(self.lvFormatDocImgRef.currentIndex().data(Qt.UserRole))
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageSetupResolutionChanged(self):
        """Resolution has been changed"""
        self.__formatPdfImgPaperResolution = BCExportFilesDialogBox.IMAGE_RESOLUTIONS[self.cbxFormatDocImgPaperResolution.currentText()]
        self.__slotPageFormatDocImgPageSetupSizeChanged()
        self.__slotPageFormatDocImgPageSetupUnitChanged()

    def __slotPageFormatDocImgPageSetupUnitChanged(self, dummy=None):
        """Choice of unit has been modified"""
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        unit=self.cbxFormatDocImgPaperUnit.currentData()

        # Temporary set No maximum value to ensure conversion will be proper applied
        self.dsbFormatDocImgMarginsLeft.setMaximum(9999)
        self.dsbFormatDocImgMarginsRight.setMaximum(9999)
        self.dsbFormatDocImgMarginsTop.setMaximum(9999)
        self.dsbFormatDocImgMarginsBottom.setMaximum(9999)
        self.dsbFormatDocImgThumbsSpacing.setMaximum(9999)

        vMarginLeft = self.dsbFormatDocImgMarginsLeft.value()
        vMarginRight = self.dsbFormatDocImgMarginsRight.value()
        vMarginTop = self.dsbFormatDocImgMarginsTop.value()
        vMarginBottom = self.dsbFormatDocImgMarginsBottom.value()
        vMarginThumbSpacing = self.dsbFormatDocImgThumbsSpacing.value()

        self.dsbFormatDocImgMarginsLeft.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgMarginsRight.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgMarginsTop.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgMarginsBottom.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgThumbsSpacing.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])

        self.dsbFormatDocImgMarginsLeft.setValue(self.convertSize(vMarginLeft, self.__formatPdfImgPaperSizeUnit, unit))
        self.dsbFormatDocImgMarginsRight.setValue(self.convertSize(vMarginRight, self.__formatPdfImgPaperSizeUnit, unit))
        self.dsbFormatDocImgMarginsTop.setValue(self.convertSize(vMarginTop, self.__formatPdfImgPaperSizeUnit, unit))
        self.dsbFormatDocImgMarginsBottom.setValue(self.convertSize(vMarginBottom, self.__formatPdfImgPaperSizeUnit, unit))
        self.dsbFormatDocImgThumbsSpacing.setValue(self.convertSize(vMarginThumbSpacing, self.__formatPdfImgPaperSizeUnit, unit))

        self.dsbFormatDocImgMarginsLeft.setSuffix(f" {unit}")
        self.dsbFormatDocImgMarginsRight.setSuffix(f" {unit}")
        self.dsbFormatDocImgMarginsTop.setSuffix(f" {unit}")
        self.dsbFormatDocImgMarginsBottom.setSuffix(f" {unit}")
        self.dsbFormatDocImgThumbsSpacing.setSuffix(f" {unit}")

        self.__formatPdfImgPaperSizeUnit = unit
        self.__blockSlot(False)
        self.__slotPageFormatDocImgPageSetupSizeChanged()
        self.__updateFormatDocImgMargins()
        self.__updateFormatDocImgPaperSizeList()
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageSetupSizeChanged(self, dummy=None):
        """Choice of size has been modified"""
        if self.__blockedSlots:
            return

        size=BCExportFilesDialogBox.PAPER_SIZES[self.cbxFormatDocImgPaperSize.currentData()][self.__formatPdfImgPaperSizeUnit]

        if self.__formatPdfImgPaperOrientation == BCExportFilesDialogBox.ORIENTATION_PORTRAIT:
            self.__formatPdfImgPaperSize = QSizeF(size)
        else:
            self.__formatPdfImgPaperSize = QSizeF(size.height(), size.width())

        if self.__formatPdfImgPaperSizeUnit == 'px':
            # in this case, unit is in inch
            # need to convert to pixels
            self.__formatPdfImgPaperSize = QSizeF(self.__formatPdfImgPaperSize.width() * self.__formatPdfImgPaperResolution, self.__formatPdfImgPaperSize.height() * self.__formatPdfImgPaperResolution)

        self.__updateFormatDocImgMargins()
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageSetupOrientationChanged(self, dummy=None):
        """Choice of orientation has been modified"""
        self.__formatPdfImgPaperOrientation = self.cbxFormatDocImgPaperOrientation.currentIndex()

        if self.__blockedSlots:
            return

        self.__slotPageFormatDocImgPageSetupSizeChanged()
        self.__updateFormatDocImgPaperSizeList()
        self.__updateFormatDocImgMargins()
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageSetupMarginLChanged(self, dummy=None):
        """Margin LEFT has been modified"""
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            self.dsbFormatDocImgMarginsRight.setValue(self.dsbFormatDocImgMarginsLeft.value())
            self.dsbFormatDocImgMarginsTop.setValue(self.dsbFormatDocImgMarginsLeft.value())
            self.dsbFormatDocImgMarginsBottom.setValue(self.dsbFormatDocImgMarginsLeft.value())
        self.__blockSlot(False)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageSetupMarginRChanged(self, dummy=None):
        """Margin RIGHT has been modified"""
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            self.dsbFormatDocImgMarginsLeft.setValue(self.dsbFormatDocImgMarginsRight.value())
            self.dsbFormatDocImgMarginsTop.setValue(self.dsbFormatDocImgMarginsRight.value())
            self.dsbFormatDocImgMarginsBottom.setValue(self.dsbFormatDocImgMarginsRight.value())
        self.__blockSlot(False)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageSetupMarginTChanged(self, dummy=None):
        """Margin TOP has been modified"""
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            self.dsbFormatDocImgMarginsLeft.setValue(self.dsbFormatDocImgMarginsTop.value())
            self.dsbFormatDocImgMarginsRight.setValue(self.dsbFormatDocImgMarginsTop.value())
            self.dsbFormatDocImgMarginsBottom.setValue(self.dsbFormatDocImgMarginsTop.value())
        self.__blockSlot(False)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageSetupMarginBChanged(self, dummy=None):
        """Margin BOTTOM has been modified"""
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            self.dsbFormatDocImgMarginsLeft.setValue(self.dsbFormatDocImgMarginsBottom.value())
            self.dsbFormatDocImgMarginsRight.setValue(self.dsbFormatDocImgMarginsBottom.value())
            self.dsbFormatDocImgMarginsTop.setValue(self.dsbFormatDocImgMarginsBottom.value())
        self.__blockSlot(False)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageSetupMarginLinkChanged(self, dummy=None):
        """Margins linked has been modified"""
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            # In this case, use Left margin as reference
            self.dsbFormatDocImgMarginsRight.setValue(self.dsbFormatDocImgMarginsLeft.value())
            self.dsbFormatDocImgMarginsTop.setValue(self.dsbFormatDocImgMarginsLeft.value())
            self.dsbFormatDocImgMarginsBottom.setValue(self.dsbFormatDocImgMarginsLeft.value())
        self.__blockSlot(False)
        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPageLayoutChanged(self, dummy=None):
        """page layout has been modified"""
        self.bcsteFormatDocImgHeader.setEnabled(self.cbFormatDocImgHeader.isChecked())
        self.bcsteFormatDocImgFooter.setEnabled(self.cbFormatDocImgFooter.isChecked())
        self.bcsteFormatDocImgFPageNotes.setEnabled(self.cbFormatDocImgFPageNotes.isChecked())

        self.lblFormatDocImgPreview.update()

    def __slotPageFormatDocImgPropertiesFontChanged(self, dummy=None):
        """Font family/size changed"""
        self.__formatPdfImgFontSize = self.dsbFormatDocImgPropertiesFontSize.value()
        self.lblFormatDocImgPreview.update()

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

        if self.swPages.currentIndex() == BCExportFilesDialogBox.__PAGE_FORMAT:
            self.__formatPdfImgNbProperties = 0
            for itemIndex in range(self.lwPerimeterProperties.count()):
                if  self.lwPerimeterProperties.item(itemIndex).checkState() == Qt.Checked:
                    self.__formatPdfImgNbProperties+=1
            self.lblFormatDocImgPreview.update()

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


            clipboardAllowed={
                    'status': BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['clipboard'],
                    'tooltip': ''
                }

            if not clipboardAllowed['status']:
                clipboardAllowed['tooltip']=i18n("This format doesn't allow export to clipboard")
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_MD and self.cbFormatTextMDIncludeThumbnails.isChecked():
                clipboardAllowed['status']=False
                clipboardAllowed['tooltip']=i18n("When option <i>Include thumbnails</i> is checked, Markdown can't be exported to clipboard")

            if not clipboardAllowed['status']:
                self.rbTargetResultFile.setChecked(True)
                self.rbTargetResultClipboard.setEnabled(False)
            else:
                self.rbTargetResultClipboard.setEnabled(True)

            self.rbTargetResultClipboard.setToolTip(clipboardAllowed['tooltip'])

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
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_DOC_PDF:
            exported = self.exportAsDocumentPdf(target, self.__generateConfig(), False)
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_KRA:
            exported = self.exportAsImageKra(target, self.__generateConfig(), False)
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_PNG:
            exported = self.exportAsImageSeq(target, self.__generateConfig(), False, 'png')
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_JPG:
            exported = self.exportAsImageSeq(target, self.__generateConfig(), False, 'jpeg')

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
            self.accept()
        else:
            BCSysTray.messageCritical(i18n(f"{self.__uiController.bcName()}::Export files list"),
                                      i18n(f"Export as <i>{BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['label']}</i> format {exported['message']} has failed!"))

            QApplication.restoreOverrideCursor()
            ##### export failed: do not close window, let user try to check/fix the problem
            ##### DON'T UNCOMMENT! :-)
            ##### self.reject()

        # the pass... is useless i know; it's used to let Atom editor being avle to fold the function properly
        # (not able to fold properly if last line in function are comment ^_^')
        pass

    def __getPath(self):
        """Return path (path file/name or quick ref)"""
        path=self.__uiController.panel().path()
        lPath=path.lower()
        refDict=self.__uiController.quickRefDict()

        if lPath in refDict:
            return f"{refDict[path][2]}"
        return path

    def __parseText(self, text, tableContent):
        """Parse given text to replace markup with their values"""
        returned = text

        if self.rbPerimeterSelectPath.isChecked():
            returned = re.sub("(?i)\{source\}",                     self.__getPath(),                                   returned)
        else:
            returned = re.sub("(?i)\{source}",                      "Current user selection",                           returned)

        currentDateTime = time.time()

        returned = re.sub("(?i)\{bc:name\}",                        self.__uiController.bcName(),                       returned)
        returned = re.sub("(?i)\{bc:version\}",                     self.__uiController.bcVersion(),                    returned)
        returned = re.sub("(?i)\{bc:title\}",                       self.__uiController.bcTitle(),                      returned)

        returned = re.sub("(?i)\{date\}",                           tsToStr(currentDateTime, "d" ),                     returned)
        returned = re.sub("(?i)\{date:yyyy\}",                      tsToStr(currentDateTime, "%Y" ),                    returned)
        returned = re.sub("(?i)\{date:mm\}",                        tsToStr(currentDateTime, "%m" ),                    returned)
        returned = re.sub("(?i)\{date:dd\}",                        tsToStr(currentDateTime, "%d" ),                    returned)

        returned = re.sub("(?i)\{time\}",                           tsToStr(currentDateTime, "t" ),                     returned)
        returned = re.sub("(?i)\{time:hh\}",                        tsToStr(currentDateTime, "%H" ),                    returned)
        returned = re.sub("(?i)\{time:mm\}",                        tsToStr(currentDateTime, "%M" ),                    returned)
        returned = re.sub("(?i)\{time:ss\}",                        tsToStr(currentDateTime, "%S" ),                    returned)

        returned = re.sub("(?i)\{items:total\.count\}",             str(self.__fileNfo[3]),                             returned)
        returned = re.sub("(?i)\{items:directories\.count\}",       str(self.__fileNfo[1]),                             returned)
        returned = re.sub("(?i)\{items:files\.count\}",             str(self.__fileNfo[2]),                             returned)
        returned = re.sub("(?i)\{items:files\.size\}",              str(self.__fileNfo[6]),                             returned)
        returned = re.sub("(?i)\{items:files\.size\(KiB\)\}",       bytesSizeToStr(self.__fileNfo[6], 'autobin'),       returned)
        returned = re.sub("(?i)\{items:files\.size\(KB\)\}",        bytesSizeToStr(self.__fileNfo[6], 'auto'),          returned)

        returned = re.sub("(?i)\{table\}",                          tableContent,                                       returned)

        return returned

    def __getTable(self, fields, items, title=None, preview=False):
        """Generic method to initialise a BCTable content"""
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

        extraData = self.__extraData

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

    def __drawPage(self, painter, options, fields, items, title):
        """Draw given to `painter` using givens properties

        Given `options` is dictionary with the following properties:
        -

        Return a number of items drawn on page
        """
        pass

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

        includeThumbnails = config.get('thumbnails.included', defaultConfig['thumbnails.included'])

        if includeThumbnails and target != BCExportFilesDialogBox.__CLIPBOARD:
            targetBaseName=os.path.basename(target)
            self.__extraData = [BCFileThumbnailSize.fromValue(config.get('thumbnails.size', defaultConfig['thumbnails.size'])), # thumbnail size
                                f"{targetBaseName}-img" # Relative path to MD file
                                ]
            fieldsList=['file.thumbnailMD']
        else:
            fieldsList=[]
        fieldsList+=config.get('fields', defaultConfig['fields'])

        tableSettings = BCTableSettingsTextMarkdown()
        tableSettings.setColumnsFormatting([BCExportFilesDialogBox.FIELDS[key]['format'] for key in fieldsList])

        try:
            table = self.__getTable(fieldsList,
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

            if returned['exported'] and includeThumbnails:
                # MD file export is Ok, copy thumnails
                try:
                    # create target directory
                    targetPath = os.path.join(os.path.dirname(target), self.__extraData[1])
                    if os.path.isdir(targetPath):
                        shutil.rmtree(targetPath)

                    os.makedirs(targetPath, exist_ok=True)
                except Exception as e:
                    returned['exported'] = False
                    Debug.print('[BCExportFilesDialogBox.exportAsTextMd] Unable to create target directory: {0}', e)

            if returned['exported'] and includeThumbnails:
                # MD file export is Ok, copy thumnails
                for file in config.get('files', defaultConfig['files']):
                    try:
                        thumbnailFileName=file.thumbnail(self.__extraData[0], BCBaseFile.THUMBTYPE_FILENAME)
                        if os.path.isfile(thumbnailFileName):
                            shutil.copy2(thumbnailFileName, os.path.join(targetPath, os.path.basename(thumbnailFileName)))
                    except Exception as e:
                        Debug.print('[BCExportFilesDialogBox.exportAsTextMd] Unable to copy thumbnails: {0}', e)



        return returned

    def exportAsImageKra(self, target, config, preview=False):
        """Export content as an image file (Krita document)

        If `preview`, only the first layer is generated
        """
        returned = {'exported': False,
                    'message': 'not yet implemented!'
                }

        return returned

    def exportAsImageSeq(self, target, config, preview=False, imageFormat=None):
        """Export content as (a sequence of) image file (PNG/JPEG)

        If `preview`, only the first sequence is generated
        """
        returned = {'exported': False,
                    'message': 'not yet implemented!'
                }

        return returned

    def exportAsDocumentPdf(self, target, config, preview=False):
        """Export content as PDF document

        If `preview`, only the first page is exported
        """
        returned = {'exported': False,
                    'message': 'not processed :)'
                }
        # define a default configuration, if given config is missing...
        defaultConfig = {
                'thumbnails.included': True,
                'thumbnails.size': 256,

                'fields': [key for key in BCExportFilesDialogBox.FIELDS if BCExportFilesDialogBox.FIELDS[key]['selected']],
                'files': []
            }

        if not isinstance(config, dict):
            config = defaultConfig

        includeThumbnails = config.get('thumbnails.included', defaultConfig['thumbnails.included'])

        fieldsList+=config.get('fields', defaultConfig['fields'])

        return returned

    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCExportFilesDialogBox(title, uicontroller)
        return db.exec()

