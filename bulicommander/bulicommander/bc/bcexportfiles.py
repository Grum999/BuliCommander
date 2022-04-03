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
        pyqtSignal as Signal,
        QSettings,
        QStandardPaths
    )
from PyQt5.QtWidgets import (
        QDialog,
        QFileDialog
    )

import os
import os.path
import re
import shutil
import time
import json
from math import (
        ceil,
        floor
    )

from .bcfile import (
        BCBaseFile,
        BCDirectory,
        BCFile,
        BCFileManagedFormat,
        BCFileProperty,
        BCFileThumbnailSize
    )
from .bcsettings import (
        BCSettingsKey,
        BCSettings
    )
from .bcsystray import BCSysTray

from bulicommander.pktk.widgets.wtextedit import (
        WTextEdit,
        WTextEditDialog
    )
from bulicommander.pktk.modules.strtable import (
        TextTable,
        TextTableSettingsText,
        TextTableSettingsTextCsv,
        TextTableSettingsTextMarkdown
    )
from bulicommander.pktk.modules.strutils import (
        bytesSizeToStr,
        strDefault
    )
from bulicommander.pktk.modules.imgutils import (
        checkerBoardBrush,
        buildIcon,
        megaPixels,
        ratioOrientation
    )
from bulicommander.pktk.modules.timeutils import tsToStr
from bulicommander.pktk.modules.utils import (
        JsonQObjectEncoder,
        JsonQObjectDecoder,
        cloneRect,
        replaceLineEditClearButton,
        Debug
    )
from bulicommander.pktk.modules.ekrita import EKritaNode
from bulicommander.pktk.widgets.wiodialog import (
        WDialogBooleanInput,
        WDialogMessage
    )
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# -----------------------------------------------------------------------------

# todo:
#
# Dialogbox
# =========
#   Should be able to open it for immediate export
#   - use last settings saved in global configuration
#   - execute export
#
#   Should be able to open it for configuration export
#   - use settings provided as dictionary (missing settings are get from global configuration)
#   - return configuration as dictionary
#    (do not execute export)
#
# Exporter
# ========
#   A class that can take configuration export (as dictionary)
#   and generate export from a given source file
#   - need to provides signals for export steps & progress

class BCExportFormat(object):
    EXPORT_FMT_TEXT =           0
    EXPORT_FMT_TEXT_MD =        1
    EXPORT_FMT_TEXT_CSV =       2
    EXPORT_FMT_DOC_PDF =        3
    EXPORT_FMT_IMG_KRA =        4
    EXPORT_FMT_IMG_PNG =        5
    EXPORT_FMT_IMG_JPG =        6



class BCExportFields:
    ID = {
                                                    # label:        value displayed in listbox
                                                    # tooltip:      tooltip affected to item in list
                                                    # data:         data to return in exported result
                                                    # alignment:    for format that support column alignment, define
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
                                                     'data':        '{BCExportFields.imgSize(file.imageSize().width(), file.imageSize().height()) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    True
                                                    },
        'image.size.width':                         {'label':       i18n('Image size (width)'),
                                                     'toolTip':     i18n('The current image size (width)'),
                                                     'data':        '{BCExportFields.numberOrEmpty(file.imageSize().width()) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'image.size.height':                        {'label':       i18n('Image size (height)'),
                                                     'toolTip':     i18n('The current image size (height)'),
                                                     'data':        '{BCExportFields.numberOrEmpty(file.imageSize().height()) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'image.ratio.value':                        {'label':       i18n('Image ratio (value)'),
                                                     'toolTip':     i18n('The current image ratio (width/height)<br/>Value is rounded to 4 decimals'),
                                                     'data':        '{BCExportFields.getRoundedValue(file.getProperty(BCFileProperty.IMAGE_RATIO), 4, False) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'image.ratio.type':                         {'label':       i18n('Image ratio (portrait, landscape, square)'),
                                                     'toolTip':     i18n('The current image ratio'),
                                                     'data':        '{ratioOrientation(file.getProperty(BCFileProperty.IMAGE_RATIO)) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   0,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'image.pixels.count':                       {'label':       i18n('Image pixels'),
                                                     'toolTip':     i18n('The current number of pixels (width * height)'),
                                                     'data':        '{BCExportFields.numberOrEmpty(file.getProperty(BCFileProperty.IMAGE_PIXELS), False) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    },
        'image.pixels.countMP':                     {'label':       i18n('Image pixels (in Megapixel)'),
                                                     'toolTip':     i18n('The current number of pixels (width * height), in megapixel (MP)<br/>Value is rounded to 2 decimals'),
                                                     'data':        '{megaPixels(file.getProperty(BCFileProperty.IMAGE_PIXELS), 2) if not isinstance(file, BCDirectory) else ""}',
                                                     'alignment':   1,
                                                     'format':      None,
                                                     'inList':      True,
                                                     'selected':    False
                                                    }
    }

    @staticmethod
    def imgSize(width, height):
        """return value width x height is number are valid
        Otherwise return empty string
        """
        if width is None or width<0 or height is None or height<0:
            return ""
        return f"{width}x{height}"

    @staticmethod
    def numberOrEmpty(value, acceptZero=True):
        """return value
        If value is None or negative, return empty string
        """
        if value is None or value<0 or value==0 and not acceptZero:
            return ""
        return value

    @staticmethod
    def getRoundedValue(value, roundDec=4, acceptZero=True):
        """return value rounded to given number of decimal

        If value is None or negative, return empty string
        """
        if value is None or value<0 or value==0 and not acceptZero:
            return ""
        return f"{value:.0{roundDec}f}"



class BCExportFiles(QObject):
    exportStart=Signal(int)     # total pages
    exportEnd=Signal()
    exportProgress=Signal(int)  # current page


    # -- Utils -----------------------------------------------------------------
    @staticmethod
    def convertSize(value, fromUnit, toUnit, resolution, roundValue=None, formatPdfImgPaperResolution=None):
        """Return converted `value` from given `fromUnit` to `toUnit`, using given `resolution` (if unit conversion implies px)


        The `roundValue` allows to define number of decimals for conversion
        The `formatPdfImgPaperResolution` allows to define target PDF document resolution
        """
        if formatPdfImgPaperResolution is None:
            formatPdfImgPaperResolution=resolution
        if roundValue is None:
            roundValue = BCExportFilesDialogBox.UNITS[toUnit]['marginDec']
        if fromUnit == 'mm':
            if toUnit == 'cm':
                return round(value/10, roundValue)
            elif toUnit == 'in':
                return round(value/25.4, roundValue)
            elif toUnit == 'px':
                return round(BCExportFiles.convertSize(value, fromUnit, 'in', formatPdfImgPaperResolution) * resolution, roundValue)
        elif fromUnit == 'cm':
            if toUnit == 'mm':
                return round(value*10, roundValue)
            elif toUnit == 'in':
                return round(value/2.54, roundValue)
            elif toUnit == 'px':
                return round(BCExportFiles.convertSize(value, fromUnit, 'in', formatPdfImgPaperResolution) * resolution, roundValue)
        elif fromUnit == 'in':
            if toUnit == 'mm':
                return round(value*25.4, roundValue)
            elif toUnit == 'cm':
                return round(value*2.54, roundValue)
            elif toUnit == 'px':
                return round(value * resolution, roundValue)
        elif fromUnit == 'px':
            if toUnit == 'mm':
                return round(BCExportFiles.convertSize(value, fromUnit, 'in', formatPdfImgPaperResolution)*25.4, roundValue)
            elif toUnit == 'cm':
                return round(BCExportFiles.convertSize(value, fromUnit, 'in', formatPdfImgPaperResolution)*2.54, roundValue)
            elif toUnit == 'in':
                return round(value / resolution, roundValue)
        elif fromUnit == 'pt':
            if toUnit == 'mm':
                return round(value * 0.35277777777777775, roundValue)   # 25.4/72
            elif toUnit == 'cm':
                return round(value * 0.035277777777777775, roundValue)  #2.54/72
            elif toUnit == 'in':
                return round(value / 72, roundValue)
            elif toUnit == 'px':
                return round(resolution * BCExportFiles.convertSize(value, fromUnit, 'in', formatPdfImgPaperResolution)/72, roundValue)
        # all other combination are not valid, return initial value
        return value

    @staticmethod
    def getPaperSize(paperSize, unit, orientation, resolution=None):
        """Return QSize for given paperSize + unit"""
        size=BCExportFilesDialogBox.PAPER_SIZES[paperSize][unit]

        if unit == 'px' and not resolution is None:
            # in this case, unit is in inch
            # need t oconvert to pixels
            size = QSizeF(size.width() * resolution, size.height() * resolution)

        if orientation == BCExportFilesDialogBox.ORIENTATION_LANDSCAPE:
            return QSize(size.height(), size.width())
        return size

    def __init__(self, uiController, filesNfo=None, parent=None):
        super(BCExportFiles, self).__init__(parent)

        # extra data are defined as global to class...
        # currently used to share some specific data
        self.__extraData = []

        self.__uiController=uiController

        self.__formatPdfImgPaperResolution = 300
        self.__formatPdfImgPageCurrent = 0
        self.__formatPdfImgPageTotal = 0
        self.__formatPdfImgPixmapResolution = QApplication.primaryScreen().logicalDotsPerInch()

        self.__exportedFileName=""
        self.__bcName=self.__uiController.bcName()
        self.__bcVersion=self.__uiController.bcVersion()
        self.__bcTitle=self.__uiController.bcTitle()

        if isinstance(filesNfo, list):
            self.__fileNfo = filesNfo
        else:
            self.__fileNfo = self.__uiController.panel().files()

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

    def __buildHtml(self, rows, fontName='DejaVu sans', fontSize=10, fontColor='#000000'):
        """Build a html text from given rows"""
        htmlP=f"<p style='margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;'>"
        htmlSpan=f"""<span style="font-family:'{fontName}'; font-size:{fontSize}pt; color:{fontColor};">"""

        nfoContent=f"</span></p>{htmlP}{htmlSpan}".join(rows)

        return f"<html><head><meta name='qrichtext' content='1'/><style type='text/css'>p, li {{ white-space: nowrap; }}</style></head><body>{htmlP}{htmlSpan}{nfoContent}</span></p></body></html>"

    def __parsePageNumber(self, text, pageCurrent, pageTotal):
        """Parse given text to replace current/total page number"""
        if result:=re.search("(?i)\{page:current(?:(:#+))?\}", text):
            if not result.groups()[0] is None:
                replaceHash=result.groups()[0]
            else:
                replaceHash=''

            text = re.sub(f"\{{page:current{replaceHash}\}}", f"{pageCurrent:0{max(0, len(replaceHash)-1)}}", text)

        if result:=re.search("(?i)\{page:total(?:(:#+))?\}", text):
            if not result.groups()[0] is None:
                replaceHash=result.groups()[0]
            else:
                replaceHash=''

            text = re.sub(f"\{{page:total{replaceHash}\}}", f"{pageTotal:0{max(0, len(replaceHash)-1)}}", text)

        return text

    def __parseText(self, text, tableContent='', currentPage=0, totalPage=0, source=''):
        """Parse given text to replace markup with their values"""
        returned = text

        if source != '':
            returned = re.sub("(?i)\{source\}",                     source,                                             returned)
        else:
            returned = re.sub("(?i)\{source}",                      "Current user selection",                           returned)

        currentDateTime = time.time()

        if self.__exportedFileName == BCExportFilesDialogBox.CLIPBOARD:
            fileName = i18n('Clipboard')
            baseName = i18n('Clipboard')
            extName = ''
        else:
            fileName = os.path.basename(self.__exportedFileName)
            if result:=re.match("(.*)(\.[^\.]*)$", fileName):
                baseName = result.groups()[0]
                extName = result.groups()[1]
            else:
                baseName = fileName
                extName = ''

        returned = re.sub("(?i)\{bc:name\}",                        self.__bcName,                                      returned)
        returned = re.sub("(?i)\{bc:version\}",                     self.__bcVersion,                                   returned)
        returned = re.sub("(?i)\{bc:title\}",                       self.__bcTitle,                                     returned)

        returned = re.sub("(?i)\{date\}",                           tsToStr(currentDateTime, "d" ),                     returned)
        returned = re.sub("(?i)\{date:yyyy\}",                      tsToStr(currentDateTime, "%Y" ),                    returned)
        returned = re.sub("(?i)\{date:mm\}",                        tsToStr(currentDateTime, "%m" ),                    returned)
        returned = re.sub("(?i)\{date:dd\}",                        tsToStr(currentDateTime, "%d" ),                    returned)

        returned = re.sub("(?i)\{time\}",                           tsToStr(currentDateTime, "t" ),                     returned)
        returned = re.sub("(?i)\{time:hh\}",                        tsToStr(currentDateTime, "%H" ),                    returned)
        returned = re.sub("(?i)\{time:mm\}",                        tsToStr(currentDateTime, "%M" ),                    returned)
        returned = re.sub("(?i)\{time:ss\}",                        tsToStr(currentDateTime, "%S" ),                    returned)

        returned = re.sub("(?i)\{items:total\.count\}",             f"{self.__fileNfo[3]}",                             returned)
        returned = re.sub("(?i)\{items:directories\.count\}",       f"{self.__fileNfo[3]}",                             returned)
        returned = re.sub("(?i)\{items:files\.count\}",             f"{self.__fileNfo[3]}",                             returned)
        returned = re.sub("(?i)\{items:files\.size\}",              f"{self.__fileNfo[3]}",                             returned)
        returned = re.sub("(?i)\{items:files\.size\(KiB\)\}",       bytesSizeToStr(self.__fileNfo[6], 'autobin'),       returned)
        returned = re.sub("(?i)\{items:files\.size\(KB\)\}",        bytesSizeToStr(self.__fileNfo[6], 'auto'),          returned)

        returned = self.__parsePageNumber(returned, currentPage, totalPage)

        returned = re.sub("(?i)\{file:name\}",                      fileName,                                           returned)
        returned = re.sub("(?i)\{file:baseName\}",                  baseName,                                           returned)
        returned = re.sub("(?i)\{file:ext\}",                       extName,                                            returned)

        returned = re.sub("(?i)\{table\}",                          tableContent,                                       returned)

        return returned

    def __getTable(self, fields, items, title=None, previewLimit=0):
        """Generic method to initialise a TextTable content"""
        returnedTable = TextTable()

        if not title is None:
            returnedTable.setTitle(title)

        headerFields = []
        for field in fields:
            headerFields.append(BCExportFields.ID[field]['label'])
        returnedTable.setHeader(headerFields)

        maxRows = None
        if previewLimit>0:
            maxRows = min(previewLimit, len(items))

        # 'extraData' is used in fString from BCExportFields.ID['file.thumbnailMD']['data']
        extraData = self.__extraData

        currentRow = 0
        for file in items:
            currentRow+=1
            if not maxRows is None and currentRow >= maxRows:
                break

            rowContent = []
            for field in fields:
                data = BCExportFields.ID[field]['data']
                rowContent.append( eval(f"f'{data}'") )

            returnedTable.addRow(rowContent)

        return returnedTable

    def __cleanupField(self, fields):
        """Cleanup given field list

        Example:
            ['.file.Name', '*file.path']
            will return ['file.path']
        """
        returned=[]
        for fieldId in fields:
            if fieldId[0]=='*':
                returned.append(fieldId[1:])
            elif fieldId[0]!='.':
                returned.append(fieldId)
        return returned

    def drawPage(self, painter, pagesInformation, config, defaultConfig, currentPage, totalPage):
        """Draw given page to `painter` (QPainter) using givens properties

        Given `options` is dictionary with the following properties:
        -

        Return a number of items drawn on page
        """
        # note: painter has been initialised (begin() already started)
        def drawThumbnail(index, position, file, thumbFields):
            def getData(data, file):
                return eval(f"f'{data}'")

            painter.resetTransform()
            painter.translate(position)
            painter.save()

            if not thumbnailBrush is None:
                # paint page background
                painter.setPen(QPen(Qt.NoPen))
                painter.setBrush(thumbnailBrush)
                if thumbnailBorderRadius>0:
                    painter.drawRoundedRect(0, 0, cellSize.width(), cellSize.height(), thumbnailBorderRadius, thumbnailBorderRadius)
                else:
                    painter.drawRect(0, 0, cellSize.width(), cellSize.height())
                painter.setBrush(QBrush(Qt.NoBrush))

            propertiesPosition = pagesInformation['cell.thumbnail.propPosition']
            cellInnerSpacing = pagesInformation['cell.thumbnail.innerSpacing']

            imgPosition = QPoint(cellInnerSpacing, cellInnerSpacing)
            txtPosition = QPoint(cellInnerSpacing, cellInnerSpacing)

            image=file.thumbnail(BCFileThumbnailSize.fromValue(512), BCBaseFile.THUMBTYPE_IMAGE)
            if isinstance(image, QImage):
                thumbWidth = floor(pagesInformation['cell.thumbnail.size'].width())
                thumbHeight = floor(pagesInformation['cell.thumbnail.size'].height())
                #thumbPixmap = QPixmap.fromImage(image.scaled(pagesInformation['cell.thumbnail.size'], Qt.KeepAspectRatio, Qt.SmoothTransformation))
                if config.get('thumbnails.image.displayMode', defaultConfig['thumbnails.image.displayMode'])=='fit':
                    thumbPixmap = QPixmap.fromImage(image.scaled(QSize(thumbWidth,thumbHeight), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    if image.width() > image.height():
                        tmpImg=image.scaledToHeight(thumbHeight, Qt.SmoothTransformation)
                        pX=floor((tmpImg.width() - thumbWidth)/2)
                        thumbPixmap = QPixmap.fromImage(tmpImg.copy(pX, 0, thumbWidth, tmpImg.height()))
                    else:
                        tmpImg=image.scaledToWidth(thumbWidth, Qt.SmoothTransformation)
                        pY=floor((tmpImg.height() - thumbHeight)/2)
                        thumbPixmap = QPixmap.fromImage(tmpImg.copy(0,pY,tmpImg.width(), thumbHeight))
            else:
                thumbPixmap = None

            if propertiesPosition == 'left':
                # left
                if not thumbPixmap is None:
                    imgPosition.setX(imgPosition.x() +  pagesInformation['cell.text.size'].width() + (pagesInformation['cell.thumbnail.size'].width() - thumbPixmap.width())/2)
                    imgPosition.setY((pagesInformation['cell.global.size'].height() - thumbPixmap.height())/2)
            elif propertiesPosition == 'right':
                # right
                txtPosition.setX(txtPosition.x() + pagesInformation['cell.thumbnail.size'].width())
                if not thumbPixmap is None:
                    imgPosition.setX(imgPosition.x()+(pagesInformation['cell.thumbnail.size'].width() - thumbPixmap.width())/2)
                    imgPosition.setY((pagesInformation['cell.global.size'].height() - thumbPixmap.height())/2)
            elif propertiesPosition == 'top':
                # top
                if not thumbPixmap is None:
                    imgPosition.setX((pagesInformation['cell.global.size'].width() - thumbPixmap.width())/2)
                    imgPosition.setY(2*cellInnerSpacing+(pagesInformation['cell.thumbnail.size'].height() - thumbPixmap.height())/2)
                imgPosition.setY(imgPosition.y() + pagesInformation['cell.text.size'].height())
            elif propertiesPosition == 'bottom':
                # bottom
                if not thumbPixmap is None:
                    imgPosition.setX((pagesInformation['cell.global.size'].width() - thumbPixmap.width())/2)
                    imgPosition.setY(cellInnerSpacing+(pagesInformation['cell.thumbnail.size'].height() - thumbPixmap.height())/2)
                txtPosition.setY(txtPosition.y() + cellInnerSpacing + pagesInformation['cell.thumbnail.size'].height())
            elif not thumbPixmap is None:
                # no text
                imgPosition.setX((pagesInformation['cell.global.size'].width() - thumbPixmap.width())/2)
                imgPosition.setY((pagesInformation['cell.global.size'].height() - thumbPixmap.height())/2)

            if not thumbPixmap is None:
                painter.drawPixmap(imgPosition.x(), imgPosition.y(), thumbPixmap)

            if propertiesPosition != 'none':
                # text
                fontName = config.get('thumbnails.text.font.name', defaultConfig['thumbnails.text.font.name'])
                fontSize = config.get('thumbnails.text.font.size', defaultConfig['thumbnails.text.font.size'])
                fontColor = config.get('thumbnails.text.font.color', defaultConfig['thumbnails.text.font.color']).name(QColor.HexArgb)

                painter.resetTransform()
                painter.translate(position)
                painter.translate(txtPosition)

                document = QTextDocument()
                document.setPageSize(QSizeF(pagesInformation['cell.text.size'].width(), 2*pagesInformation['cell.text.size'].height()))
                document.setHtml(self.updatePointSize(self.__buildHtml([getData(BCExportFields.ID[fieldName]['data'], file) for fieldName in thumbFields], fontName, fontSize, fontColor)))
                document.drawContents(painter)

            painter.restore()

            if not thumbnailPen is None:
                # paint page background
                painter.setPen(thumbnailPen)
                painter.setBrush(QBrush(Qt.NoBrush))
                if thumbnailBorderRadius>0:
                    painter.drawRoundedRect(0, 0, cellSize.width(), cellSize.height(), thumbnailBorderRadius, thumbnailBorderRadius)
                else:
                    painter.drawRect(0, 0, cellSize.width(), cellSize.height())
                painter.setPen(QPen(Qt.NoPen))

        painter.setRenderHint(QPainter.Antialiasing)

        unit = config.get('paper.unit', defaultConfig['paper.unit'])
        resolution = config.get('paper.resolution', defaultConfig['paper.resolution'])

        # initialise some thumbnail values to avoid to do it each time a thumbnail is drawn
        thumbnailBorderRadius = BCExportFiles.convertSize(config.get('thumbnails.border.radius', defaultConfig['thumbnails.border.radius']), unit, 'px', resolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)
        thumbnailBrush = None
        thumbnailPen = None
        if config.get('thumbnails.background.active', defaultConfig['thumbnails.background.active']):
            thumbnailBrush=QBrush(config.get('thumbnails.background.color', defaultConfig['thumbnails.background.color']), Qt.SolidPattern)

        thumbnailBorder = None
        if config.get('thumbnails.border.active', defaultConfig['thumbnails.border.active']):
            thumbnailPen=QPen(config.get('thumbnails.border.color', defaultConfig['thumbnails.border.color']))
            thumbnailPen.setJoinStyle(Qt.MiterJoin)
            thumbnailPen.setWidth(BCExportFiles.convertSize(config.get('thumbnails.border.width', defaultConfig['thumbnails.border.width']), unit, 'px', resolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution))

        # bounds for page (ie: margins)
        pageBounds = cloneRect(pagesInformation['page.global.bounds'])
        insideBounds = cloneRect(pagesInformation['page.inside.bounds'])
        pageBorderRadius = BCExportFiles.convertSize(config.get('page.border.radius', defaultConfig['page.border.radius']), unit, 'px', resolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)

        brush = QBrush(Qt.NoBrush)
        pen = QPen(Qt.NoPen)
        pen.setJoinStyle(Qt.MiterJoin)

        if config.get('page.background.active', defaultConfig['page.background.active']):
            # paint page background
            brush.setStyle(Qt.SolidPattern)
            brush.setColor(config.get('page.background.color', defaultConfig['page.background.color']))

            painter.setPen(pen)
            painter.setBrush(brush)
            if pageBorderRadius>0:
                painter.drawRoundedRect(pageBounds, pageBorderRadius, pageBorderRadius)
            else:
                painter.drawRect(pageBounds)

            brush = QBrush(Qt.NoBrush)
            painter.setBrush(brush)

        thumbPerRow = config.get('thumbnails.layout.nbPerRow', defaultConfig['thumbnails.layout.nbPerRow'])
        thumbSpacing = pagesInformation['cell.thumbnail.outerSpacing']

        # calculate current thumbnail index in list
        if currentPage == 1:
            thumbMaxPages = pagesInformation['page.first.nbRowsMax'] * thumbPerRow
            thumbIndex = 0
            thumbBounds = cloneRect(pagesInformation['page.first.bounds'])
        else:
            thumbMaxPages = pagesInformation['page.normal.nbRowsMax'] * thumbPerRow
            thumbIndex = pagesInformation['page.first.nbRowsMax'] * thumbPerRow + (pagesInformation['page.normal.nbRowsMax'] * thumbPerRow) * (currentPage - 2)
            thumbBounds = cloneRect(pagesInformation['page.normal.bounds'])

        #
        painter.translate(insideBounds.topLeft())

        document = QTextDocument()
        document.setPageSize(QSizeF(thumbBounds.size()))

        if pagesInformation['header.height'] > 0:
            # header to draw
            document.setHtml(self.updatePointSize(self.__parseText(config.get('header.content', defaultConfig['header.content']), '', currentPage, totalPage, source=config.get('source', defaultConfig['source']))))
            document.drawContents(painter)
            painter.translate(QPointF(0, pagesInformation['header.height']))

        if currentPage == 1 and pagesInformation['fpNotes.height'] > 0:
            # first page notes to draw
            document.setHtml(self.updatePointSize(self.__parseText(config.get('firstPageNotes.content', defaultConfig['firstPageNotes.content']), '', currentPage, totalPage, source=config.get('source', defaultConfig['source']))))
            document.drawContents(painter)
            painter.translate(QPointF(0, pagesInformation['fpNotes.height']))

        if pagesInformation['footer.height'] > 0:
            # footer to draw
            painter.resetTransform()
            painter.translate(QPointF(thumbBounds.left(), thumbBounds.bottom() + pagesInformation['cell.thumbnail.outerSpacing']))
            document.setHtml(self.updatePointSize(self.__parseText(config.get('footer.content', defaultConfig['footer.content']), '', currentPage, totalPage, source=config.get('source', defaultConfig['source']))))
            document.drawContents(painter)

        # thumbnails
        thumbFields = self.__cleanupField(config.get('fields', defaultConfig['fields']))
        thumbFiles = config.get('files', defaultConfig['files'])
        nbThumbFiles = len(thumbFiles)

        cellSize = pagesInformation['cell.global.size']
        position = thumbBounds.topLeft()
        for pageIndex in range(thumbMaxPages):
            if thumbIndex >= nbThumbFiles:
                # finished!
                break

            drawThumbnail(thumbIndex, position, thumbFiles[thumbIndex], thumbFields)

            if (pageIndex+1) % thumbPerRow == 0:
                # next row
                position.setX(thumbBounds.left())
                position.setY(position.y() + cellSize.height() + thumbSpacing)
            else:
                position.setX(position.x() + cellSize.width() + thumbSpacing)

            thumbIndex+=1

        painter.resetTransform()

        if config.get('page.border.active', defaultConfig['page.border.active']):
            # draw page borders
            brush.setStyle(Qt.NoBrush)
            pen.setStyle(Qt.SolidLine)
            pen.setColor(config.get('page.border.color', defaultConfig['page.border.color']))
            pen.setWidth(BCExportFiles.convertSize(config.get('page.border.width', defaultConfig['page.border.width']), unit, 'px', resolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution))

            painter.setPen(pen)
            painter.setBrush(brush)
            if pageBorderRadius>0:
                painter.drawRoundedRect(pageBounds, pageBorderRadius, pageBorderRadius)
            else:
                painter.drawRect(pageBounds)

    def updatePointSize(self, content):
        """QTextDocument convert pt to pixels, using default QPainter resolution

        QPainter resolution of device (printer) or screen

        Then, if QPainter is 96dpi and target is 300dpi, we need to convert given
        value
        """
        def repPt(v):
            point = float(v.groups()[1])
            newValue = round(point * ratio, 2)
            return v.groups()[0].replace(v.groups()[1], f"{newValue}")

        ratio = self.__formatPdfImgPaperResolution / self.__formatPdfImgPixmapResolution

        if isinstance(content, str):
            return re.sub(r"(?i)(font-size\s*:\s*(\d+|\d+\.\d*|\.d+)\s*pt\s*;)", repPt, content)
        return round(point * ratio, 2)

    def getPagesInformation(self, imageSize, config, defaultConfig):
        """Calculate pages informations

        return a dictionnary:
            {
                'page.size':                    QRect(),
                'page.global.bounds':           QRect(),
                'page.inside.bounds':           QRect(),

                'page.first.bounds':            QRect(),
                'page.first.nbRowsMax':         int,

                'page.normal.bounds':           QRect(),
                'page.normal.nbRowsMax':        int,

                'header.height':                int,
                'footer.height':                int,
                'fpNotes.height':               int,

                'cell.global.size':             QSize(),
                'cell.thumbnail.size':          QSize(),
                'cell.text.size':               QSize(),
                'cell.thumbnail.outerSpacing':  int,
                'cell.thumbnail.innerSpacing':  int,
                'cell.thumbnail.propPosition':  int,

                'rows.total':                   int,
                'page.total':                   int
            }
        """
        fieldsList=config.get('fields', defaultConfig['fields'])
        imageResolution = config.get('paper.resolution', defaultConfig['paper.resolution'])

        # calculate bounds within margins
        fromUnit = config.get('paper.unit', defaultConfig['paper.unit'])
        imageBounds = QRect(
                QPoint(floor(BCExportFiles.convertSize(config.get('margins.left', defaultConfig['margins.left']), fromUnit, 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)),
                       floor(BCExportFiles.convertSize(config.get('margins.top', defaultConfig['margins.top']), fromUnit, 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution))),
                QPoint(floor(imageSize.width() - BCExportFiles.convertSize(config.get('margins.right', defaultConfig['margins.right']), fromUnit, 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)),
                       floor(imageSize.height() - BCExportFiles.convertSize(config.get('margins.bottom', defaultConfig['margins.bottom']), fromUnit, 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)))
            )

        insideBounds = cloneRect(imageBounds)


        if config.get('page.background.active', defaultConfig['page.background.active']) or config.get('page.border.active', defaultConfig['page.border.active']):
            innerSpace = round(BCExportFiles.convertSize(max(1, config.get('thumbnails.layout.spacing.outer', defaultConfig['thumbnails.layout.spacing.outer']), config.get('page.border.radius', defaultConfig['page.border.radius']), config.get('page.border.width', defaultConfig['page.border.width'])), fromUnit, 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution), 0)

            insideBounds.setLeft(insideBounds.left() + innerSpace)
            insideBounds.setRight(insideBounds.right() - innerSpace)
            insideBounds.setTop(insideBounds.top() + innerSpace)
            insideBounds.setBottom(insideBounds.bottom() - innerSpace)

        fPageBounds=cloneRect(insideBounds)
        nPageBounds=cloneRect(insideBounds)

        # used to calculate texts sizes...
        document = QTextDocument()
        document.setPageSize(QSizeF(insideBounds.size()))

        thumbnailsOuterSpacing = round(BCExportFiles.convertSize(config.get('thumbnails.layout.spacing.outer', defaultConfig['thumbnails.layout.spacing.outer']), fromUnit, 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution), 0)

        # calculate height for Header
        headerHeight = 0
        if config.get('header.active', defaultConfig['header.active']) and config.get('header.content', defaultConfig['header.content']).strip() != '':
            document.setHtml(self.updatePointSize(config.get('header.content', defaultConfig['header.content'])))
            headerHeight = document.size().height() + thumbnailsOuterSpacing

            fPageBounds.setTop(fPageBounds.top() + headerHeight)
            nPageBounds.setTop(nPageBounds.top() + headerHeight)

        # calculate height for Footer
        footerHeight = 0
        if config.get('footer.active', defaultConfig['footer.active']) and config.get('footer.content', defaultConfig['footer.content']).strip() != '':
            document.setHtml(self.updatePointSize(config.get('footer.content', defaultConfig['footer.content'])))
            footerHeight = document.size().height() + thumbnailsOuterSpacing

            fPageBounds.setBottom(fPageBounds.bottom() - footerHeight)
            nPageBounds.setBottom(nPageBounds.bottom() - footerHeight)

        # calculate height for first page note
        fpNotesHeight = 0
        if config.get('firstPageNotes.active', defaultConfig['firstPageNotes.active']) and config.get('firstPageNotes.content', defaultConfig['firstPageNotes.content']).strip() != '':
            document.setHtml(self.updatePointSize(config.get('firstPageNotes.content', defaultConfig['firstPageNotes.content'])))
            fpNotesHeight = document.size().height() + thumbnailsOuterSpacing

            fPageBounds.setTop(fPageBounds.top() + fpNotesHeight)

        # calculate bounds for a thumbnail
        thumbPerRow = config.get('thumbnails.layout.nbPerRow', defaultConfig['thumbnails.layout.nbPerRow'])
        propertiesPosition = config.get('thumbnails.text.position', defaultConfig['thumbnails.text.position'])
        cellWidth = int(round((insideBounds.width() - thumbnailsOuterSpacing * (thumbPerRow - 1))/thumbPerRow, 0))

        fontName = config.get('thumbnails.text.font.name', defaultConfig['thumbnails.text.font.name'])
        fontSize = config.get('thumbnails.text.font.size', defaultConfig['thumbnails.text.font.size'])
        fontColor = '000000'

        document.setDefaultFont(QFont(config.get('thumbnails.text.font.name', defaultConfig['thumbnails.text.font.name'])))
        document.setHtml(self.updatePointSize(self.__buildHtml(["X"]*len(fieldsList), fontName, fontSize, fontColor)))
        cellTextHeight = document.size().height()
        thumbnailsInnerSpacing=BCExportFiles.convertSize(config.get('thumbnails.layout.spacing.inner', defaultConfig['thumbnails.layout.spacing.inner']), fromUnit, 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)

        if propertiesPosition == 'none':
            # no properties to display
            # then, height = width
            cellHeight = cellWidth

            # thumb size = 100% of cell
            thumbSize = cellWidth - thumbnailsInnerSpacing*2

            # no text
            cellTextWidth = 0
            cellTextHeight = 0
        elif propertiesPosition in ['left', 'right']:
            # left/right position
            # in this case, consider that image size = 50% of cellWidth
            thumbSize = (cellWidth - thumbnailsInnerSpacing*3)//2

            cellTextHeight+=thumbnailsInnerSpacing*2

            # cell height is the greatest height between thumbnail and text
            cellHeight = max(cellTextHeight, thumbSize + thumbnailsInnerSpacing*2)

            # text width is 50% of cell
            cellTextWidth = cellWidth - thumbSize - thumbnailsInnerSpacing*2
        else:
            # top/bottom position
            # in this case, consider that image size = cellWidth - textHeight; but can't be smaller than 25% of cell width
            thumbSize = max(cellWidth - cellTextHeight - thumbnailsInnerSpacing, cellWidth * 0.25) - thumbnailsInnerSpacing*2

            # cell height is the sum of thumb height and text height
            cellHeight = cellTextHeight + thumbSize + thumbnailsInnerSpacing*3

            # text width is 10% of cell
            cellTextWidth = cellWidth - thumbnailsInnerSpacing*2

        # - - calculate number of pages
        # total number of rows to display
        nbRows = ceil(len(config.get('files', defaultConfig['files']))/thumbPerRow)
        # maximum row per page
        fpNbRowsMax = (fPageBounds.height() + thumbnailsOuterSpacing) / (cellHeight+thumbnailsOuterSpacing)
        npNbRowsMax = (nPageBounds.height() + thumbnailsOuterSpacing) / (cellHeight+thumbnailsOuterSpacing)

        # allow a small error to derterminate number of rows
        # > value defined arbitrary, mybe need to be affined
        if abs(ceil(fpNbRowsMax) - fpNbRowsMax) <= 0.025:
            fpNbRowsMax = ceil(fpNbRowsMax)
        else:
            fpNbRowsMax = floor(fpNbRowsMax)

        if abs(ceil(npNbRowsMax) - npNbRowsMax) <= 0.025:
            npNbRowsMax = ceil(npNbRowsMax)
        else:
            npNbRowsMax = floor(npNbRowsMax)

        if nbRows <= fpNbRowsMax:
            nbPages = 1
        else:
            nbPages = 1 + ceil((nbRows - fpNbRowsMax) / npNbRowsMax)

        returned= {
            'page.size':                    imageSize,
            'page.global.bounds':           imageBounds,
            'page.inside.bounds':           insideBounds,

            'page.first.bounds':            fPageBounds,
            'page.first.nbRowsMax':         fpNbRowsMax,

            'page.normal.bounds':           nPageBounds,
            'page.normal.nbRowsMax':        npNbRowsMax,

            'header.height':                headerHeight,
            'footer.height':                footerHeight,
            'fpNotes.height':               fpNotesHeight,

            'cell.global.size':             QSize(cellWidth, cellHeight),
            'cell.thumbnail.size':          QSize(thumbSize, thumbSize),
            'cell.text.size':               QSize(cellTextWidth, cellTextHeight),
            'cell.thumbnail.outerSpacing':  thumbnailsOuterSpacing,
            'cell.thumbnail.innerSpacing':  thumbnailsInnerSpacing,
            'cell.thumbnail.propPosition':  propertiesPosition,

            'rows.total':                   nbRows,
            'page.total':                   nbPages
        }

        return returned

    def exportAsText(self, target, config=None):
        """Export content as text"""
        returned = {'exported': False,
                    'message': 'not processed :)'
                }
        # define a default configuration, if given config is missing...
        defaultConfig = {
                'userDefinedLayout.active': False,
                'userDefinedLayout.content': '{table}',

                'header.active': True,

                'borders.style': TextTableSettingsText.BORDER_BASIC,

                'minimumWidth.active': True,
                'minimumWidth.value': 80,

                'maximumWidth.active': False,
                'maximumWidth.value': 120,

                'fields': [key for key in BCExportFields.ID if BCExportFields.ID[key]['selected']],
                'files': [],
                'source': ''
            }

        if not isinstance(config, dict):
            config = defaultConfig

        fieldsList=self.__cleanupField(config.get('fields', defaultConfig['fields']))

        tableSettings = TextTableSettingsText()
        tableSettings.setHeaderActive(config.get('header.active', defaultConfig['header.active']))
        tableSettings.setBorder(config.get('borders.style', defaultConfig['borders.style']))
        tableSettings.setMinWidthActive(config.get('minimumWidth.active', defaultConfig['minimumWidth.active']))
        tableSettings.setMaxWidthActive(config.get('maximumWidth.active', defaultConfig['maximumWidth.active']))
        tableSettings.setMinWidth(config.get('minimumWidth.value', defaultConfig['minimumWidth.value']))
        tableSettings.setMaxWidth(config.get('maximumWidth.value', defaultConfig['maximumWidth.value']))
        tableSettings.setColumnsAlignment([BCExportFields.ID[key]['alignment'] for key in fieldsList])

        self.exportStart.emit(-1)
        try:
            table = self.__getTable(fieldsList,
                                    config.get('files', defaultConfig['files']),
                                    None)

            if config.get('userDefinedLayout.active', defaultConfig['userDefinedLayout.active']):
                # layout asked
                content = self.__parseText(config.get('userDefinedLayout.content', defaultConfig['userDefinedLayout.content']),
                                           table.asText(tableSettings),
                                           currentPage=0,
                                           totalPage=0,
                                           source=config.get('source', defaultConfig['source']))
            else:
                content = table.asText(tableSettings)

            # data are ready
            returned['exported'] = True
        except Exception as e:
            Debug.print('[BCExportFilesDialogBox.exportAsText] Unable to generate data: {0}', e)

        if target == BCExportFilesDialogBox.CLIPBOARD:
            returned['message'] = 'to clipboard'
            if returned['exported']:
                returned['exported'] = self.__exportDataToClipboard(content)
        else:
            returned['message'] = f'to file <b>{os.path.basename(target)}</b>'
            if returned['exported']:
                returned['exported'] = self.__exportDataToFile(target, content)

        self.exportEnd.emit()

        return returned

    def exportAsTextCsv(self, target, config=None):
        """Export content as text"""
        returned = {'exported': False,
                    'message': 'not processed :)'
                }
        # define a default configuration, if config is missing...
        defaultConfig = {
                'header.active': True,

                'fields.enclosed': False,
                'fields.separator': ',',

                'fields': [key for key in BCExportFields.ID if BCExportFields.ID[key]['selected']],
                'files': [],
                'source': ''
            }

        if not isinstance(config, dict):
            config = defaultConfig

        self.exportStart.emit(-1)

        tableSettings = TextTableSettingsTextCsv()
        tableSettings.setHeaderActive(config.get('header.active', defaultConfig['header.active']))
        tableSettings.setEnclosedField(config.get('fields.enclosed', defaultConfig['fields.enclosed']))
        tableSettings.setSeparator(config.get('fields.separator', defaultConfig['fields.separator']))


        try:
            table = self.__getTable(self.__cleanupField(config.get('fields', defaultConfig['fields'])),
                                    config.get('files', defaultConfig['files']),
                                    None)

            content = table.asTextCsv(tableSettings)

            # data are ready
            returned['exported'] = True
        except Exception as e:
            Debug.print('[BCExportFilesDialogBox.exportAsTextCsv] Unable to generate data: {0}', e)

        if target == BCExportFilesDialogBox.CLIPBOARD:
            returned['message'] = 'to clipboard'
            if returned['exported']:
                returned['exported'] = self.__exportDataToClipboard(content)
        else:
            returned['message'] = f'to file <b>{os.path.basename(target)}</b>'
            if returned['exported']:
                returned['exported'] = self.__exportDataToFile(target, content)

        self.exportEnd.emit()

        return returned

    def exportAsTextMd(self, target, config=None):
        """Export content as text"""
        returned = {'exported': False,
                    'message': 'not processed :)'
                }
        # define a default configuration, if config is missing...
        defaultConfig = {
                'userDefinedLayout.active': False,
                'userDefinedLayout.content': '{table}',

                'thumbnails.included': False,
                'thumbnails.size': 64,

                'fields': [key for key in BCExportFields.ID if BCExportFields.ID[key]['selected']],
                'files': [],
                'source': ''
            }

        if not isinstance(config, dict):
            config = defaultConfig

        includeThumbnails = config.get('thumbnails.included', defaultConfig['thumbnails.included'])

        self.exportStart.emit(-1)

        if includeThumbnails and target != BCExportFilesDialogBox.CLIPBOARD:
            targetBaseName=os.path.basename(target)
            self.__extraData = [BCFileThumbnailSize.fromValue(config.get('thumbnails.size', defaultConfig['thumbnails.size'])), # thumbnail size
                                f"{targetBaseName}-img" # Relative path to MD file
                                ]
            fieldsList=['file.thumbnailMD']
        else:
            fieldsList=[]
        fieldsList+=self.__cleanupField(config.get('fields', defaultConfig['fields']))

        tableSettings = TextTableSettingsTextMarkdown()
        tableSettings.setColumnsFormatting([BCExportFields.ID[key]['format'] for key in fieldsList])

        try:
            table = self.__getTable(fieldsList,
                                    config.get('files', defaultConfig['files']),
                                    None)

            if config.get('userDefinedLayout.active', defaultConfig['userDefinedLayout.active']):
                # layout asked
                content = self.__parseText(config.get('userDefinedLayout.content', defaultConfig['userDefinedLayout.content']),
                                           table.asTextMarkdown(tableSettings),
                                           currentPage=0,
                                           totalPage=0,
                                           source=config.get('source', defaultConfig['source']))
            else:
                content = table.asTextMarkdown(tableSettings)

            # data are ready
            returned['exported'] = True
        except Exception as e:
            Debug.print('[BCExportFilesDialogBox.exportAsTextMd] Unable to generate data: {0}', e)

        if target == BCExportFilesDialogBox.CLIPBOARD:
            returned['message'] = 'to clipboard'
            if returned['exported']:
                returned['exported'] = self.__exportDataToClipboard(content)
        else:
            returned['message'] = f'to file <b>{os.path.basename(target)}</b>'
            if returned['exported']:
                returned['exported'] = self.__exportDataToFile(target, content)

            if returned['exported'] and includeThumbnails:
                # MD file export is Ok, copy thumbnails
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

        self.exportEnd.emit()

        return returned

    def exportAsImageKra(self, target, config):
        """Export content as an image file (Krita document)"""
        def fillLayer(layer, color):
            rect = layer.bounds()
            img = QImage(rect.width(), rect.height(), QImage.Format_ARGB32)
            img.fill(color)
            EKritaNode.fromQImage(layer, img, rect.topLeft())

        def drawLayer(layer, pagesInformation, config, defaultConfig, currentPage, totalPage):
            rect = pagesInformation['page.size']
            pixmap = QPixmap(rect.width(), rect.height())
            pixmap.fill(Qt.transparent)
            painter = QPainter()
            painter.begin(pixmap)
            self.drawPage(painter, pagesInformation, config, defaultConfig, currentPage, totalPage)
            painter.end()
            EKritaNode.fromQPixmap(layer, pixmap)

        returned = {'exported': False,
                    'message': f'to file <b>{os.path.basename(target)}</b>'
                }
        # define a default configuration, if given config is missing...
        defaultConfig = {
                'thumbnails.background.active': False,
                'thumbnails.background.color': QColor("#FFFFFF"),
                'thumbnails.border.active': False,
                'thumbnails.border.color': QColor("#000000"),
                'thumbnails.border.width': 1.0,
                'thumbnails.border.radius': 0.0,
                'thumbnails.layout.spacing.inner': 2.0,
                'thumbnails.image.displayMode': 'fit',
                'thumbnails.text.position': 'none',
                'thumbnails.text.font.name': 'DejaVu sans',
                'thumbnails.text.font.size': 10,
                'thumbnails.text.font.color': QColor("#000000"),

                'thumbnails.layout.nbPerRow': 2,
                'thumbnails.layout.spacing.outer': 5.0,

                'page.background.active': False,
                'page.background.color': QColor("#FFFFFF"),
                'page.border.active': False,
                'page.border.color': QColor("#000000"),
                'page.border.width': 1.0,
                'page.border.radius': 0.0,

                'firstPageNotes.active': False,
                'firstPageNotes.content': "",
                'footer.active': False,
                'footer.content': "",
                'header.active': False,
                'header.content': "",
                'margins.bottom': 20.0,
                'margins.left': 20.0,
                'margins.right': 20.0,
                'margins.top': 20.0,
                'paper.orientation': BCExportFilesDialogBox.ORIENTATION_PORTRAIT, # portrait
                'paper.size': "A4",
                'paper.resolution': 300.0,
                'paper.color.active': False,
                'paper.color.value': QColor("#FFFFFF"),
                'paper.unit': "mm",

                'file.openInKrita': True,

                'fields': [key for key in BCExportFields.ID if BCExportFields.ID[key]['selected']],
                'files': [],
                'source': ''
            }

        if not isinstance(config, dict):
            config = defaultConfig

        # 1) Create KRA file
        # 2) Set white Background layer
        # While all thumbnails are not processed
        #   3.a) generate page
        #   3.b) create new layer "Page N"
        #   3.c) add page content to layer "Page N"
        # 4) save file
        #       ==> instead of "clipboard" option, set "create new document" ???

        imageResolution = config.get('paper.resolution', defaultConfig['paper.resolution'])

        # need image size in pixels
        imageSize = BCExportFiles.getPaperSize(config.get('paper.size', defaultConfig['paper.size']),
                                               'px',
                                               config.get('paper.orientation', defaultConfig['paper.orientation']),
                                               imageResolution)

        kraDocument = Krita.instance().createDocument(imageSize.width(),
                                                      imageSize.height(),
                                                      "Document name",
                                                      "RGBA",
                                                      "U8",
                                                      "",
                                                      imageResolution)

        kraDocument.setFileName(target)

        # prepare background layer
        rootNode = kraDocument.rootNode()
        bgNode = rootNode.childNodes()[0]
        bgNode.setOpacity(255) # it seems that node opactiry is 0% ??? not sure if normal or not, ensure that it's 100%
        if config.get('paper.color.active', defaultConfig['paper.color.active']):
            fillLayer(bgNode, config.get('paper.color.value', defaultConfig['paper.color.value']))
        else:
            fillLayer(bgNode, Qt.transparent)

        # calculate pages informations
        pagesInformation = self.getPagesInformation(imageSize, config, defaultConfig)

        totalPage = pagesInformation['page.total']

        self.exportStart.emit(totalPage)
        for page in range(totalPage):
            currentPage = page + 1
            self.exportProgress.emit(currentPage)
            QApplication.instance().processEvents()

            newPage = kraDocument.createNode(f'Page {currentPage}/{totalPage}', "paintLayer")
            if page > 0:
                newPage.setVisible(False)
            drawLayer(newPage, pagesInformation, config, defaultConfig, currentPage, totalPage)
            rootNode.addChildNode(newPage, bgNode)

        returned['exported']=kraDocument.save()

        if config.get('file.openInKrita', defaultConfig['file.openInKrita']):
            kraDocument.refreshProjection()
            Krita.instance().activeWindow().addView(kraDocument)

        self.exportEnd.emit()

        return returned

    def exportAsImageSeq(self, target, config, imageFormat=None):
        """Export content as (a sequence of) image file (PNG/JPEG)"""
        returned = {'exported': False,
                    'message': f'to file sequence <b>{os.path.basename(target)}</b>'
                }
        # define a default configuration, if given config is missing...
        defaultConfig = {
                'thumbnails.background.active': False,
                'thumbnails.background.color': QColor("#FFFFFF"),
                'thumbnails.border.active': False,
                'thumbnails.border.color': QColor("#000000"),
                'thumbnails.border.width': 1.0,
                'thumbnails.border.radius': 0.0,
                'thumbnails.layout.spacing.inner': 2.0,
                'thumbnails.image.displayMode': 'fit',
                'thumbnails.text.position': 'none',
                'thumbnails.text.font.name': 'DejaVu sans',
                'thumbnails.text.font.size': 10,
                'thumbnails.text.font.color': QColor("#000000"),

                'thumbnails.layout.nbPerRow': 2,
                'thumbnails.layout.spacing.outer': 5.0,

                'page.background.active': False,
                'page.background.color': QColor("#FFFFFF"),
                'page.border.active': False,
                'page.border.color': QColor("#000000"),
                'page.border.width': 1.0,
                'page.border.radius': 0.0,

                'firstPageNotes.active': False,
                'firstPageNotes.content': "",
                'footer.active': False,
                'footer.content': "",
                'header.active': False,
                'header.content': "",
                'margins.bottom': 20.0,
                'margins.left': 20.0,
                'margins.right': 20.0,
                'margins.top': 20.0,
                'paper.orientation': BCExportFilesDialogBox.ORIENTATION_PORTRAIT, # portrait
                'paper.size': "A4",
                'paper.resolution': 300.0,
                'paper.color.active': False,
                'paper.color.value': QColor("#FFFFFF"),
                'paper.unit': "mm",

                'file.openInKrita': False,

                'fields': [key for key in BCExportFields.ID if BCExportFields.ID[key]['selected']],
                'files': [],
                'source': ''
            }

        if not isinstance(config, dict):
            config = defaultConfig

        imageFormat = imageFormat.upper()

        imageResolution = config.get('paper.resolution', defaultConfig['paper.resolution'])

        # need image size in pixels
        imageSize = BCExportFiles.getPaperSize(config.get('paper.size', defaultConfig['paper.size']),
                                               'px',
                                               config.get('paper.orientation', defaultConfig['paper.orientation']),
                                               imageResolution)

        # calculate pages informations
        pagesInformation = self.getPagesInformation(imageSize, config, defaultConfig)

        totalPage = pagesInformation['page.total']

        self.exportStart.emit(totalPage)

        fileName = target
        if totalPage > 1:
            if re.search("(?i)\{page:current(?::(#+))?\}", target) is None:
                # no counter... add it
                fileName = re.sub('(\..*)$', r'-{page:current:###}\1', target)
            returned['message']=f'to file sequence <b>{os.path.basename(fileName)} (sequence: {totalPage} files)</b>'
        else:
            returned['message']=f'to file <b>{os.path.basename(fileName)}</b>'

        isOk = True
        for page in range(totalPage):
            currentPage = page + 1
            self.exportProgress.emit(currentPage)
            QApplication.instance().processEvents()

            imgDocument = QImage(imageSize.width(), imageSize.height(), QImage.Format_ARGB32)
            pxmDocument = QPixmap(imgDocument)

            if imageFormat == 'JPEG':
                pxmDocument.fill(Qt.white)
            else:
                pxmDocument.fill(Qt.transparent)

            if config.get('paper.color.active', defaultConfig['paper.color.active']):
                pxmDocument.fill(config.get('paper.color.value', defaultConfig['paper.color.value']))

            painter = QPainter()
            painter.begin(pxmDocument)
            self.drawPage(painter, pagesInformation, config, defaultConfig, currentPage, totalPage)
            painter.end()

            isOk = pxmDocument.toImage().save(self.__parseText(fileName, '', currentPage, totalPage, source=config.get('source', defaultConfig['source'])), imageFormat)

            if not isOk:
                break

        self.exportEnd.emit()

        returned['exported']=isOk

        return returned

    def exportAsDocumentPdf(self, target, config):
        """Export content as PDF document"""
        returned = {'exported': False,
                    'message': f'to file sequence <b>{os.path.basename(target)}</b>'
                }
        # define a default configuration, if given config is missing...
        defaultConfig = {
                'thumbnails.background.active': False,
                'thumbnails.background.color': QColor("#FFFFFF"),
                'thumbnails.border.active': False,
                'thumbnails.border.color': QColor("#000000"),
                'thumbnails.border.width': 1.0,
                'thumbnails.border.radius': 0.0,
                'thumbnails.layout.spacing.inner': 2.0,
                'thumbnails.image.displayMode': 'fit',
                'thumbnails.text.position': 'none',
                'thumbnails.text.font.name': 'DejaVu sans',
                'thumbnails.text.font.size': 10,
                'thumbnails.text.font.color': QColor("#000000"),

                'thumbnails.layout.nbPerRow': 2,
                'thumbnails.layout.spacing.outer': 5.0,

                'page.background.active': False,
                'page.background.color': QColor("#FFFFFF"),
                'page.border.active': False,
                'page.border.color': QColor("#000000"),
                'page.border.width': 1.0,
                'page.border.radius': 0.0,

                'firstPageNotes.active': False,
                'firstPageNotes.content': "",
                'footer.active': False,
                'footer.content': "",
                'header.active': False,
                'header.content': "",
                'margins.bottom': 20.0,
                'margins.left': 20.0,
                'margins.right': 20.0,
                'margins.top': 20.0,
                'paper.orientation': BCExportFilesDialogBox.ORIENTATION_PORTRAIT, # portrait
                'paper.size': "A4",
                'paper.resolution': 300.0,
                'paper.color.active': False,
                'paper.color.value': QColor("#FFFFFF"),
                'paper.unit': "mm",

                'file.openInKrita': False,

                'fields': [key for key in BCExportFields.ID if BCExportFields.ID[key]['selected']],
                'files': [],
                'source': ''
            }

        if not isinstance(config, dict):
            config = defaultConfig

        imageResolution = config.get('paper.resolution', defaultConfig['paper.resolution'])
        imageSizeUnit = config.get('paper.unit', defaultConfig['paper.unit'])

        imageSize = BCExportFiles.getPaperSize(config.get('paper.size', defaultConfig['paper.size']),
                                               imageSizeUnit,
                                               config.get('paper.orientation', defaultConfig['paper.orientation']))
        imageSizePx = BCExportFiles.getPaperSize(config.get('paper.size', defaultConfig['paper.size']),
                                                 'px',
                                                 config.get('paper.orientation', defaultConfig['paper.orientation']),
                                                 imageResolution)

        if imageSizeUnit == 'mm':
            printerSizeUnit = QPrinter.Millimeter
            factor = 1/BCExportFiles.convertSize(1, 'mm', 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)
        elif imageSizeUnit == 'in':
            printerSizeUnit = QPrinter.Inch
            factor = 1/BCExportFiles.convertSize(1, 'in', 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)
        if imageSizeUnit == 'cm':
            printerSizeUnit = QPrinter.Millimeter
            factor = 1/BCExportFiles.convertSize(0.1, 'cm', 'px', imageResolution, formatPdfImgPaperResolution=self.__formatPdfImgPaperResolution)

        printer = QPrinter()
        printer.setResolution(int(imageResolution))
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setPaperSize(imageSize, printerSizeUnit)
        #printer.setPageSize(imageSize, printerSizeUnit)
        printer.setOutputFileName(target)
        printer.setFullPage(True)
        painter = QPainter(printer)

        factor = painter.viewport().width() / imageSizePx.width()

        # calculate pages informations
        pagesInformation = self.getPagesInformation(imageSizePx, config, defaultConfig)

        pagesInformation['page.global.bounds'] = QRectF(
                            QPointF(factor * pagesInformation['page.global.bounds'].left(),
                                    factor * pagesInformation['page.global.bounds'].top()),
                            QPointF(factor * pagesInformation['page.global.bounds'].right(),
                                    factor * pagesInformation['page.global.bounds'].bottom()))

        pagesInformation['page.inside.bounds'] = QRectF(
                            QPointF(factor * pagesInformation['page.inside.bounds'].left(),
                                    factor * pagesInformation['page.inside.bounds'].top()),
                            QPointF(factor * pagesInformation['page.inside.bounds'].right(),
                                    factor * pagesInformation['page.inside.bounds'].bottom()))

        pagesInformation['page.first.bounds'] = QRectF(
                            QPointF(factor * pagesInformation['page.first.bounds'].left(),
                                    factor * pagesInformation['page.first.bounds'].top()),
                            QPointF(factor * pagesInformation['page.first.bounds'].right(),
                                    factor * pagesInformation['page.first.bounds'].bottom()))

        pagesInformation['page.normal.bounds'] = QRectF(
                            QPointF(factor * pagesInformation['page.normal.bounds'].left(),
                                    factor * pagesInformation['page.normal.bounds'].top()),
                            QPointF(factor * pagesInformation['page.normal.bounds'].right(),
                                    factor * pagesInformation['page.normal.bounds'].bottom()))

        pagesInformation['header.height']=factor * pagesInformation['header.height']
        pagesInformation['footer.height']=factor * pagesInformation['footer.height']
        pagesInformation['fpNotes.height']=factor * pagesInformation['fpNotes.height']

        pagesInformation['cell.global.size']=QSizeF(
                            factor * pagesInformation['cell.global.size'].width(),
                            factor * pagesInformation['cell.global.size'].height())

        pagesInformation['cell.thumbnail.size']=QSizeF(
                            factor * pagesInformation['cell.thumbnail.size'].width(),
                            factor * pagesInformation['cell.thumbnail.size'].height())

        pagesInformation['cell.text.size']=QSizeF(
                            factor * pagesInformation['cell.text.size'].width(),
                            factor * pagesInformation['cell.text.size'].height())

        pagesInformation['cell.thumbnail.outerSpacing']=factor * pagesInformation['cell.thumbnail.outerSpacing']
        pagesInformation['cell.thumbnail.innerSpacing']=factor * pagesInformation['cell.thumbnail.innerSpacing']

        totalPage = pagesInformation['page.total']

        self.exportStart.emit(totalPage)

        isOk = True
        for page in range(totalPage):
            if page > 0:
                printer.newPage()

            self.__formatPdfImgPageCurrent = page + 1
            self.exportProgress.emit(self.__formatPdfImgPageCurrent)
            QApplication.instance().processEvents()

            if config.get('paper.color.active', defaultConfig['paper.color.active']):
                painter.fillRect(painter.viewport(), config.get('paper.color.value', defaultConfig['paper.color.value']))

            self.drawPage(painter, pagesInformation, config, defaultConfig, self.__formatPdfImgPageCurrent, totalPage)

        painter.end()

        self.exportEnd.emit()

        returned['exported']=isOk

        return returned



class BCExportFilesDialogBox(QDialog):
    """User interface for export"""

    # note: IMPORT/EXPORT results codes identical to NodeEditorScene IMPORT/EXPORT results codes
    IMPORT_OK=                              0b00000000
    IMPORT_FILE_NOT_FOUND=                  0b00000001
    IMPORT_FILE_CANT_READ=                  0b00000010
    IMPORT_FILE_NOT_JSON=                   0b00000100
    IMPORT_FILE_INVALID_FORMAT_IDENTIFIER=  0b00001000
    IMPORT_FILE_MISSING_FORMAT_IDENTIFIER=  0b00010000
    IMPORT_FILE_MISSING_SCENE_DEFINITION=   0b00100000

    EXPORT_OK=       0b00000000
    EXPORT_CANT_SAVE=0b00000001

    __PAGE_PERIMETER = 0
    __PAGE_FORMAT = 1
    __PAGE_TARGET = 2

    __PANEL_FORMAT_DOCIMG_PAGESETUP = 0
    __PANEL_FORMAT_DOCIMG_PAGELAYOUT = 1
    __PANEL_FORMAT_DOCIMG_THUMBCONFIG = 2

    __PANEL_FORMAT_DOCIMG_PAGESETUP_UNIT_MM = 0
    __PANEL_FORMAT_DOCIMG_PAGESETUP_UNIT_CM = 1
    __PANEL_FORMAT_DOCIMG_PAGESETUP_UNIT_INCH = 2

    __PREVIEW_MODE_LAYOUT = 0
    __PREVIEW_MODE_STYLE = 1

    __FIELD_ID = 1000

    CLIPBOARD = '@clipboard'

    # paper size are defined in Portrait mode
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
        'Legal (US)':  {'mm':QSizeF(216, 356),
                        'cm':QSizeF(21.6, 35.6),
                     'in':QSizeF(8.5, 14.0),
                        'px':QSizeF(8.5, 14.0)
              },
        'Square (A2)': {'mm':QSizeF(420, 420),
                        'cm':QSizeF(42.0, 42.0),
                        'in':QSizeF(16.5, 16.5),
                        'px':QSizeF(16.5, 16.5)
              },
        'Square (A3)': {'mm':QSizeF(297, 297),
                       'cm':QSizeF(29.7, 29.7),
                       'in':QSizeF(11.7, 11.7),
                       'px':QSizeF(11.7, 11.7)
              },
        'Square (A4)': {'mm':QSizeF(210, 210),
                       'cm':QSizeF(21.0, 21.0),
                       'in':QSizeF(8.3, 8.3),
                       'px':QSizeF(8.3, 8.3)
              },
        'Square (A5)': {'mm':QSizeF(148, 148),
                       'cm':QSizeF(14.8, 14.8),
                       'in':QSizeF(5.8, 5.8),
                       'px':QSizeF(5.8, 5.8)
              },
        'Square (A6)': {'mm':QSizeF(105, 105),
                       'cm':QSizeF(10.5, 10.5),
                       'in':QSizeF(4.1, 4.1),
                       'px':QSizeF(4.1, 4.1)
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
        '72dpi': 72.00,
        '96dpi': 96.00,
        '150dpi': 150.00,
        '300dpi': 300.00,
        '600dpi': 600.00,
        '900dpi': 900.00,
        '1200dpi': 1200.00
    }
    ORIENTATION_PORTRAIT = 0x00
    ORIENTATION_LANDSCAPE = 0x01

    FMT_PROPERTIES = {
            BCExportFormat.EXPORT_FMT_TEXT:         {'label':               i18n('Text'),
                                                     'description':         i18n("Generate a basic text file, without any formatting<br>"
                                                                                 "This file can be opened in any text editor; use a monospace font is highly recommended for a better readability"),
                                                     'panelFormat':         0,
                                                     'clipboard':           True,
                                                     'openInKrita':         False,
                                                     'fileExtension':       'txt',
                                                     'dialogExtensions':    i18n('Text files (*.txt)')
                                                    },
            BCExportFormat.EXPORT_FMT_TEXT_CSV:     {'label':               i18n('Text/CSV'),
                                                     'description':         i18n("Generate a CSV file<br>"
                                                                                 "This file can be opened in a spreadsheet software"),
                                                     'panelFormat':         2,
                                                     'clipboard':           True,
                                                     'openInKrita':         False,
                                                     'fileExtension':       'csv',
                                                     'dialogExtensions':    i18n('CSV files (*.csv)')
                                                    },
            BCExportFormat.EXPORT_FMT_TEXT_MD:      {'label':               i18n('Text/Markdown'),
                                                     'description':         i18n("Generate a Markdown file (<a href='https://guides.github.com/features/mastering-markdown'><span style='text-decoration: underline; color:#2980b9;'>GitHub flavored version</span></a>)<br>"
                                                                                 "This file can be opened in any text editor, but use of a dedicated software to render result is recommended"),
                                                     'panelFormat':         1,
                                                     'clipboard':           True,
                                                     'openInKrita':         False,
                                                     'fileExtension':       'md',
                                                     'dialogExtensions':    i18n('Markdown files (*.md *.markdown)')
                                                    },
            BCExportFormat.EXPORT_FMT_DOC_PDF:      {'label':               i18n('Document/PDF'),
                                                     'description':         i18n("Generate a PDF file<br>"
                                                                                 "Document will contain as many pages as necessary to render complete files list with thumbnails"),
                                                     'panelFormat':         3,
                                                     'clipboard':           False,
                                                     'openInKrita':         False,
                                                     'fileExtension':       'pdf',
                                                     'dialogExtensions':    i18n('Portable Document Format (*.pdf)')
                                                    },
            BCExportFormat.EXPORT_FMT_IMG_KRA:      {'label':               i18n('Image/Krita'),
                                                     'description':         i18n("Generate a Krita document<br>"
                                                                                 "Document will contain as many layers as necessary to render complete files list with thumbnails"),
                                                     'panelFormat':         3,
                                                     'clipboard':           False,
                                                     'openInKrita':         True,
                                                     'fileExtension':       'kra',
                                                     'dialogExtensions':    i18n('Krita image (*.kra)')
                                                    },
            BCExportFormat.EXPORT_FMT_IMG_PNG:      {'label':               i18n('Image/PNG'),
                                                     'description':         i18n("Generate a PNG image file<br>"
                                                                                 "Will generate as many PNG files as necessary to render complete files list with thumbnails"),
                                                     'panelFormat':         3,
                                                     'clipboard':           False,
                                                     'openInKrita':         False,
                                                     'fileExtension':       'png',
                                                     'dialogExtensions':    i18n('PNG Image (*.png)')
                                                    },
            BCExportFormat.EXPORT_FMT_IMG_JPG:      {'label':               i18n('Image/JPEG'),
                                                     'description':         i18n("Generate a JPEG image file<br>"
                                                                                 "Will generate as many JPEG files as necessary to render complete files list with thumbnails"),
                                                     'panelFormat':         3,
                                                     'clipboard':           False,
                                                     'openInKrita':         False,
                                                     'fileExtension':       'jpeg',
                                                     'dialogExtensions':    i18n('JPEG Image (*.jpeg *.jpg)')
                                                    }
        }

    def __init__(self, title, uicontroller, options=None, parent=None):
        super(BCExportFilesDialogBox, self).__init__(parent)

        self.__title = title

        self.__exporter=BCExportFiles(uicontroller)

        self.__exporter.exportStart.connect(self.__exportStart)
        self.__exporter.exportProgress.connect(self.__exportProgress)
        self.__exporter.exportEnd.connect(self.__exportEnd)

        self.__formatPdfImgPaperResolution = 300
        self.__formatPdfImgPaperSizeUnit = "mm"
        self.__formatPdfImgPaperSize = QSizeF(0, 0)
        self.__formatPdfImgPaperOrientation = BCExportFilesDialogBox.ORIENTATION_PORTRAIT
        self.__formatPdfImgNbProperties = 0
        self.__formatPdfImgFontSize = 10
        self.__formatPdfImgPageCurrent = 0
        self.__formatPdfImgPageTotal = 0
        self.__formatPdfImgPixmapResolution = QApplication.primaryScreen().logicalDotsPerInch()
        self.__formatPdfImgEstimatedPages = 0
        self.__formatPdfImgPagesInformation = None
        self.__formatPdfImgConfig = None

        self.__exportedFileName = ''
        self.__currentLoadedConfigurationFile=''
        self.__isModified=False

        self.__blockedSlots = True

        self.__uiController = uicontroller
        self.__fileNfo = self.__uiController.panel().files()
        self.__selectedFileNfo = self.__uiController.panel().filesSelected()

        self.__hasSavedSettings = BCSettings.get(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_SAVED)
        self.__options=options

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcexportfiles.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.setWindowTitle(self.__title)

        self.__initialise()

    def __initialise(self):
        """Initialise interface"""
        def __initialisePagePerimeter():
            # Initialise interface widgets for page perimeter
            # interface widgets that don't depend of users settings
            self.lwPerimeterProperties.setSortOptionAvailable(False)
            self.lwPerimeterProperties.setCheckOptionAvailable(True)
            self.lwPerimeterProperties.setReorderOptionAvailable(True)

            if self.__options is None:
                # export

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
            else:
                # export configuration from a file selection
                self.lblPerimeterSelectPathNfo.setVisible(False)
                self.lblPerimeterSelectSelNfo.setText(i18n('From search results'))
                self.rbPerimeterSelectPath.setEnabled(False)
                # always select "Selected files" as default (as selected from a search results)
                self.rbPerimeterSelectSel.setEnabled(True)
                self.rbPerimeterSelectSel.setChecked(True)

            # define list of properties with default internal selection
            self.lwPerimeterProperties.clear()
            for field in BCExportFields.ID:
                if BCExportFields.ID[field]['inList']:
                    item=self.lwPerimeterProperties.addItem(BCExportFields.ID[field]['label'], field, BCExportFields.ID[field]['selected'])
                    item.setToolTip(BCExportFields.ID[field]['toolTip'])

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

            self.lblFormatDocImgPreview.paintEvent = self.__updateFormatDocImgConfigurationPreviewPaint

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

            self.__itemFormatDocImgRefPageSetup = QListWidgetItem(buildIcon("pktk:page_setup"), "Page setup")
            self.__itemFormatDocImgRefPageSetup.setData(Qt.UserRole, BCExportFilesDialogBox.__PANEL_FORMAT_DOCIMG_PAGESETUP)
            self.__itemFormatDocImgRefPageLayout = QListWidgetItem(buildIcon("pktk:page_layout"), "Page layout")
            self.__itemFormatDocImgRefPageLayout.setData(Qt.UserRole, BCExportFilesDialogBox.__PANEL_FORMAT_DOCIMG_PAGELAYOUT)
            self.__itemFormatDocImgRefThumbConfig = QListWidgetItem(buildIcon("pktk:image"), "Thumbnail")
            self.__itemFormatDocImgRefThumbConfig.setData(Qt.UserRole, BCExportFilesDialogBox.__PANEL_FORMAT_DOCIMG_THUMBCONFIG)

            self.lvFormatDocImgRef.addItem(self.__itemFormatDocImgRefPageSetup)
            self.lvFormatDocImgRef.addItem(self.__itemFormatDocImgRefPageLayout)
            self.lvFormatDocImgRef.addItem(self.__itemFormatDocImgRefThumbConfig)

            # - - - Page setup
            self.cbxFormatDocImgPaperResolution.clear()
            self.cbxFormatDocImgPaperUnit.clear()
            self.cbxFormatDocImgPaperSize.clear()

            for resolution in BCExportFilesDialogBox.IMAGE_RESOLUTIONS:
                self.cbxFormatDocImgPaperResolution.addItem(resolution, BCExportFilesDialogBox.IMAGE_RESOLUTIONS[resolution])
            self.cbxFormatDocImgPaperResolution.setCurrentIndex(3) # 300dpi

            self.cbxFormatDocImgPaperResolution.currentIndexChanged.connect(self.__slotPageFormatDocImgPageSetupResolutionChanged)
            self.cbxFormatDocImgPaperUnit.currentIndexChanged.connect(self.__slotPageFormatDocImgPageSetupUnitChanged)
            self.cbxFormatDocImgPaperSize.currentIndexChanged.connect(self.__slotPageFormatDocImgPageSetupSizeChanged)
            self.cbxFormatDocImgPaperOrientation.currentIndexChanged.connect(self.__slotPageFormatDocImgPageSetupOrientationChanged)
            self.cbFormatDocImgPaperColor.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.pbFormatDocImgPaperColor.colorChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.dsbFormatDocImgMarginsLeft.valueChanged.connect(self.__slotPageFormatDocImgPageSetupMarginLChanged)
            self.dsbFormatDocImgMarginsRight.valueChanged.connect(self.__slotPageFormatDocImgPageSetupMarginRChanged)
            self.dsbFormatDocImgMarginsTop.valueChanged.connect(self.__slotPageFormatDocImgPageSetupMarginTChanged)
            self.dsbFormatDocImgMarginsBottom.valueChanged.connect(self.__slotPageFormatDocImgPageSetupMarginBChanged)
            self.cbFormatDocImgMarginsLinked.toggled.connect(self.__slotPageFormatDocImgPageSetupMarginLinkChanged)

            # - - - Page layout
            self.cbFormatDocImgHeader.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.cbFormatDocImgFooter.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.cbFormatDocImgFPageNotes.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.cbFormatDocImgFPageNotesPreview.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.bcsteFormatDocImgHeader.textChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.bcsteFormatDocImgFooter.textChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.bcsteFormatDocImgFPageNotes.textChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.cbFormatDocImgPageBgColor.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.pbFormatDocImgPageBgColor.colorChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.cbFormatDocImgPageBorder.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.pbFormatDocImgPageBorderColor.colorChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.dsbFormatDocImgPageBorderWidth.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.dsbFormatDocImgPageBorderRadius.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.sbFormatDocImgThumbsPerRow.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.dsbFormatDocImgThumbsSpacingOuter.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.bcsteFormatDocImgHeader.setTitle(f"{self.__title}::{i18n('Document/PDF - Header')}")
            self.bcsteFormatDocImgFooter.setTitle(f"{self.__title}::{i18n('Document/PDF - Footer')}")
            self.bcsteFormatDocImgFPageNotes.setTitle(f"{self.__title}::{i18n('Document/PDF - First page layout')}")

            # - - - Thumb layout
            self.cbxFormatDocImgThumbMode.currentIndexChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.cbxFormatDocImgTextPosition.currentIndexChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.fcbxFormatDocImgTextFontFamily.currentFontChanged.connect(self.__slotPageFormatDocImgPropertiesFontChanged)
            self.dsbFormatDocImgTextFontSize.valueChanged.connect(self.__slotPageFormatDocImgPropertiesFontChanged)

            self.cbFormatDocImgThumbsBg.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.pbFormatDocImgThumbsBgColor.colorChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.cbFormatDocImgThumbsBorder.toggled.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.pbFormatDocImgThumbsBorderColor.colorChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.dsbFormatDocImgThumbsBorderWidth.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.dsbFormatDocImgThumbsBorderRadius.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)
            self.dsbFormatDocImgThumbsSpacingInner.valueChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.pbFormatDocImgTextFontColor.colorChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.pbFormatDocImgPageBorderColor.colorPicker().setStandardLayout('hsva')
            self.pbFormatDocImgThumbsBgColor.colorPicker().setStandardLayout('hsva')
            self.pbFormatDocImgThumbsBorderColor.colorPicker().setStandardLayout('hsva')
            self.pbFormatDocImgTextFontColor.colorPicker().setStandardLayout('hsva')
            self.pbFormatDocImgPageBgColor.colorPicker().setStandardLayout('hsva')
            self.pbFormatDocImgPaperColor.colorPicker().setStandardLayout('hsva')

            self.cbxFormatDocImgPreviewMode.currentIndexChanged.connect(self.__slotPageFormatDocImgPageLayoutChanged)

            self.__loadSettingsPageFormat()

        def __initialisePageTarget():
            # Initialise interface widgets for page target
            def saveAs():
                fileName = self.leTargetResultFile.text()
                if fileName == '':
                    # need to determinate a directory
                    fileName = ''

                fileName = QFileDialog.getSaveFileName(self, i18n('Save file'), fileName, BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['dialogExtensions'])

                if fileName != '':
                    self.leTargetResultFile.setText(fileName[0])
                self.__updateBtn()

            def checkButton(dummy):
                self.__updateBtn()

            self.pgbTargetResultExport.setVisible(False)

            self.pbTargetResultFile.clicked.connect(saveAs)
            self.rbTargetResultFile.toggled.connect(checkButton)
            self.rbTargetResultClipboard.toggled.connect(checkButton)
            self.leTargetResultFile.textChanged.connect(checkButton)
            replaceLineEditClearButton(self.leTargetResultFile)

            self.__loadSettingsPageTarget()

        def __initialiseButtonBar():
            # Initialise bottom button bar
            if(self.__options is None):
                self.pbExport.setText(i18n('Export'))
            else:
                self.pbExport.setText(i18n('Apply'))

            actionSave=QAction(i18n("Save"), self)
            actionSave.triggered.connect(lambda: self.saveFile())
            actionSaveAs=QAction(i18n("Save as..."), self)
            actionSaveAs.triggered.connect(lambda: self.saveFile(True))

            menuSave = QMenu(self.tbSaveExportDefinition)
            menuSave.addAction(actionSave)
            menuSave.addAction(actionSaveAs)
            self.tbSaveExportDefinition.setMenu(menuSave)

            self.tbNewExportDefinition.clicked.connect(self.__newExportDefinition)
            self.tbSaveExportDefinition.clicked.connect(lambda: self.saveFile())
            self.tbOpenExportDefinition.clicked.connect(lambda: self.openFile())

            self.pbPrevious.clicked.connect(self.__goPreviousPage)
            self.pbNext.clicked.connect(self.__goNextPage)
            self.pbCancel.clicked.connect(self.reject)
            self.pbExport.clicked.connect(self.__export)
            self.__updateBtn()

        __initialisePagePerimeter()
        __initialisePageFormat()
        __initialisePageTarget()
        __initialiseButtonBar()

        self.__blockSlot(False)
        self.__setModified(False)

    def __exportStart(self, totalPage):
        """Called during export"""
        self.pgbTargetResultExport.setValue(0)
        if totalPage==-1:
            self.pgbTargetResultExport.setMaximum(0)
        else:
            self.pgbTargetResultExport.setMaximum(totalPage)
        self.pgbTargetResultExport.setVisible(True)

    def __exportProgress(self, currentPage):
        """Called during export"""
        self.pgbTargetResultExport.setValue(currentPage)

    def __exportEnd(self):
        """Called during export"""
        self.pgbTargetResultExport.setValue(self.pgbTargetResultExport.maximum())

    def __blockSlot(self, value):
        self.__blockedSlots = value

    def __getPath(self):
        """Return path (path file/name or quick ref)"""
        path=self.__uiController.panel().filesPath()
        lPath=path.lower()
        refDict=self.__uiController.quickRefDict()

        if lPath in refDict:
            return f"{refDict[path][2]}"
        return path

    def __getSettings(self, settingKey):
        """Return value from
        - self.__options if not None
        - BCSettings is `settingKey` not in self.__options
        . BCSettings is self.__options is None
        """
        if self.__options is None:
            return BCSettings.get(settingKey)
        else:
            if settingKey==BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FILENAME:
                if not 'exportFileName' in self.__options:
                    return BCSettings.get(settingKey)
                else:
                    return self.__options['exportFileName']
            elif isinstance(settingKey, BCSettingsKey):
                # in options, there's no config.export prefix; remove it
                settingKey2=re.sub(r"^config\.export\.filesList\.(textCsv|textMd|text|doc\.pdf|img\.kra|img\.png|img\.jpg)\.", "", settingKey.value)
            else:
                settingKey2=settingKey

            if not settingKey2 in self.__options['exportConfig']:
                return BCSettings.get(settingKey)

            if settingKey2=='fields.separator' :
                return [',', ';', '\t', '|'].index(self.__options['exportConfig'][settingKey2])
            elif settingKey2=='thumbnails.size':
                return [64,128,256,512].index(self.__options['exportConfig'][settingKey2])

            return self.__options['exportConfig'][settingKey2]

    # -- Manage page Perimeter -------------------------------------------------
    def __loadDefaultPagePerimeter(self):
        """Load default internal configuration for page perimeter"""
        # reload default properties list
        self.swPages.setCurrentIndex(BCExportFilesDialogBox.__PAGE_PERIMETER)

        self.lwPerimeterProperties.clear()
        for field in BCExportFields.ID:
            if BCExportFields.ID[field]['inList']:
                item=self.lwPerimeterProperties.addItem(BCExportFields.ID[field]['label'], field, BCExportFields.ID[field]['selected'])
                item.setToolTip(BCExportFields.ID[field]['toolTip'])

    def __loadSettingsPagePerimeter(self):
        """Load saved settings for page perimeter"""
        # a list of string '<checked><value>'
        # example:
        #   '.file.path'    unchecked
        #   '*file.name'    checked
        # items order in list define sort
        # if some ID are missing in list, by default:
        #   - added in usual order/checked value
        checkedList=[]

        if isinstance(self.__options, dict) and 'exportConfig' in self.__options and 'fields' in self.__options['exportConfig']:
            # options has been provided, use it as settings
            self.swPages.setCurrentIndex(BCExportFilesDialogBox.__PAGE_PERIMETER)

            checkedList=self.__options['exportConfig']['fields']
        elif not self.__hasSavedSettings:
            # no saved settings: load default and exit
            self.__loadDefaultPagePerimeter()
            return
        else:
            checkedList = BCSettings.get(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_PROPERTIES)

        self.swPages.setCurrentIndex(BCExportFilesDialogBox.__PAGE_PERIMETER)

        checkedListId=[]
        # add items from settings
        self.lwPerimeterProperties.clear()
        for itemIndex in checkedList:
            fieldId=itemIndex[1:]
            if fieldId in BCExportFields.ID:
                checkedListId.append(fieldId)
                item=self.lwPerimeterProperties.addItem(BCExportFields.ID[fieldId]['label'], fieldId, (itemIndex[0]=='*'))
                item.setToolTip(BCExportFields.ID[fieldId]['toolTip'])

        # check all default items idf alaready set from settings or not; add them if not defined from settings
        for fieldId in BCExportFields.ID:
            if BCExportFields.ID[fieldId]['inList'] and not fieldId in checkedListId:
                item=self.lwPerimeterProperties.addItem(BCExportFields.ID[fieldId]['label'], fieldId, BCExportFields.ID[fieldId]['selected'])
                item.setToolTip(BCExportFields.ID[fieldId]['toolTip'])

    # -- slots
    def __slotPagePerimeterCheckAll(self):
        # check all properties
        for item in self.lwPerimeterProperties.items(False):
            item.setCheckState(True)
        self.__setModified(True)

    def __slotPagePerimeterUncheckAll(self):
        # uncheck all properties
        for item in self.lwPerimeterProperties.items(False):
            item.setCheckState(False)
        self.__setModified(True)

    def __slotPagePerimeterResetFields(self):
        # reset field list check state
        self.__loadSettingsPagePerimeter()
        self.__setModified(True)

    def __slotPagePerimeterPropertiesChanged(self, widget):
        self.__updateBtn()
        self.__setModified(True)

    # -- Manage page Format -------------------------------------------------

    def __loadDefaultPageFormat(self, index=None):
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
            self.cbxFormatDocImgPaperResolution.setCurrentIndex(3)  # 300dpi
            self.cbxFormatDocImgPaperUnit.setCurrentIndex(0)        # 'mm'
            self.cbxFormatDocImgPaperSize.setCurrentIndex(2)        # 'A4'
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(0) # 'portrait'
            self.cbFormatDocImgPaperColor.setChecked(False)
            self.pbFormatDocImgPaperColor.setColor('#FFFFFF')
            self.dsbFormatDocImgMarginsLeft.setValue(20.0)
            self.dsbFormatDocImgMarginsRight.setValue(20.0)
            self.dsbFormatDocImgMarginsTop.setValue(20.0)
            self.dsbFormatDocImgMarginsBottom.setValue(20.0)
            self.cbFormatDocImgMarginsLinked.setChecked(False)

            self.cbFormatDocImgHeader.setChecked(True)
            self.cbFormatDocImgFooter.setChecked(True)
            self.cbFormatDocImgFPageNotes.setChecked(True)
            self.cbFormatDocImgFPageNotesPreview.setChecked(True)

            self.bcsteFormatDocImgHeader.setHtml('')
            self.bcsteFormatDocImgFooter.setHtml('')
            self.bcsteFormatDocImgFPageNotes.setHtml('')

            self.sbFormatDocImgThumbsPerRow.setValue(2)
            self.dsbFormatDocImgThumbsSpacingOuter.setValue(5.0)

            self.cbFormatDocImgPageBgColor.setChecked(False)
            self.pbFormatDocImgPageBgColor.setColor('#FFFFFF')

            self.cbFormatDocImgPageBorder.setChecked(False)
            self.pbFormatDocImgPageBorderColor.setColor('#000000')
            self.dsbFormatDocImgPageBorderWidth.setValue(1.0)
            self.dsbFormatDocImgPageBorderRadius.setValue(0.0)

            self.cbFormatDocImgThumbsBg.setChecked(False)
            self.pbFormatDocImgThumbsBgColor.setColor('#FFFFFF')
            self.cbFormatDocImgThumbsBorder.setChecked(False)
            self.pbFormatDocImgThumbsBorderColor.setColor('#000000')
            self.dsbFormatDocImgThumbsBorderWidth.setValue(1.0)
            self.dsbFormatDocImgThumbsBorderRadius.setValue(0.0)
            self.dsbFormatDocImgThumbsSpacingInner.setValue(1.0)
            self.cbxFormatDocImgThumbMode.setCurrentIndex(0)        # fit

            self.cbxFormatDocImgTextPosition.setCurrentIndex(2)   # right

            self.fcbxFormatDocImgTextFontFamily.setCurrentFont(QFont('DejaVu sans'))
            self.dsbFormatDocImgTextFontSize.setValue(10)
            self.pbFormatDocImgTextFontColor.setColor('#000000')

            # placed here instead of __loadDefaultPageTarget
            self.cbTargetResultFileOpen.setChecked(False)

            self.cbxFormatDocImgPreviewMode.setCurrentIndex(0)

            self.__updateFormatDocImgPaperSizeList()
            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()

        # --- ALL format ---
        if index is None:
            self.cbxFormat.setCurrentIndex(BCExportFormat.EXPORT_FMT_TEXT)
            self.__slotPageFormatFormatChanged()

        # -- pages
        defaultText()
        defaultTextMd()
        defaultTextCsv()
        defaultDocImg()

    def __loadSettingsPageFormat(self, target=None):
        """Load saved settings for page format"""
        def defaultText():
            # --- TEXT interface ---
            self.cbFormatTextLayoutUserDefined.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_ACTIVE))
            self.teFormatTextLayoutUserDefined.setPlainText(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_CONTENT))

            self.cbFormatTextHeader.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_HEADER_ACTIVE))
            currentBordersStyle = self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE)
            if currentBordersStyle == 0:
                self.rbFormatTextBorderNone.setChecked(True)
            elif currentBordersStyle == 1:
                self.rbFormatTextBorderBasic.setChecked(True)
            elif currentBordersStyle == 2:
                self.rbFormatTextBorderSimple.setChecked(True)
            elif currentBordersStyle == 3:
                self.rbFormatTextBorderDouble.setChecked(True)
            self.cbFormatTextMinWidth.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_ACTIVE))
            self.hsFormatTextMinWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_VALUE))
            self.cbFormatTextMaxWidth.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_ACTIVE))
            self.hsFormatTextMaxWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_VALUE))

            self.__slotPageFormatTextLayoutUserDefined()
            self.__slotPageFormatTextBordersCheck()
            self.__slotPageFormatTextBordersStyleCheck()
            self.__slotPageFormatTextMinWidthCheck()
            self.__slotPageFormatTextMaxWidthCheck()
            self.__slotPageFormatTextMinWidthChanged()
            self.__slotPageFormatTextMaxWidthChanged()

        def defaultTextMd():
            # --- TEXT/MARKDOWN interface ---
            self.cbFormatTextMDLayoutUserDefined.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_ACTIVE))
            self.teFormatTextMDLayoutUserDefined.setPlainText(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_CONTENT))

            self.cbFormatTextMDIncludeThumbnails.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_INCLUDED))
            self.cbxFormatTextMDThumbnailsSize.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_SIZE))

            self.__slotPageFormatTextMDLayoutUserDefined()
            self.__slotPageFormatTextMDIncludeThumbnails()

        def defaultTextCsv():
            # --- TEXT/CSV interface ---
            self.cbFormatTextCSVHeader.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_HEADER_ACTIVE))
            self.cbFormatTextCSVEnclosedFields.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_ENCLOSED))
            self.cbxFormatTextCSVSeparator.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_SEPARATOR))

        def defaultDocPdf():
            # --- DOC/PDF interface ---
            imageResolution=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_RESOLUTION)
            imageIndex=3
            for itemIndex in range(self.cbxFormatDocImgPaperResolution.count()):
                if self.cbxFormatDocImgPaperResolution.itemData(itemIndex) == imageResolution:
                    imageIndex = itemIndex
                    break

            paperSize=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_SIZE)
            paperIndex=2
            for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
                if self.cbxFormatDocImgPaperSize.itemData(itemIndex) == paperSize:
                    paperIndex = itemIndex
                    break

            unit=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_UNIT)
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
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_ORIENTATION))
            self.cbFormatDocImgPaperColor.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR_ACTIVE))
            self.pbFormatDocImgPaperColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR))
            self.dsbFormatDocImgMarginsLeft.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LEFT))
            self.dsbFormatDocImgMarginsRight.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_RIGHT))
            self.dsbFormatDocImgMarginsTop.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_TOP))
            self.dsbFormatDocImgMarginsBottom.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_BOTTOM))
            self.cbFormatDocImgMarginsLinked.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LINKED))

            self.cbFormatDocImgHeader.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_ACTIVE))
            self.cbFormatDocImgFooter.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_ACTIVE))
            self.cbFormatDocImgFPageNotes.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_ACTIVE))
            self.cbFormatDocImgFPageNotesPreview.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_PREVIEW))

            self.bcsteFormatDocImgHeader.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_CONTENT))
            self.bcsteFormatDocImgFooter.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_CONTENT))
            self.bcsteFormatDocImgFPageNotes.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_CONTENT))

            self.sbFormatDocImgThumbsPerRow.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_NBPERROW))
            self.dsbFormatDocImgThumbsSpacingOuter.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_OUTER))

            self.cbFormatDocImgPageBgColor.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_ACTIVE))
            self.pbFormatDocImgPageBgColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_COL))

            self.cbFormatDocImgPageBorder.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_ACTIVE))
            self.pbFormatDocImgPageBorderColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_COL))
            self.dsbFormatDocImgPageBorderWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_WIDTH))
            self.dsbFormatDocImgPageBorderRadius.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_RADIUS))

            self.cbFormatDocImgThumbsBg.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_ACTIVE))
            self.pbFormatDocImgThumbsBgColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_COL))
            self.cbFormatDocImgThumbsBorder.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_ACTIVE))
            self.pbFormatDocImgThumbsBorderColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_COL))
            self.dsbFormatDocImgThumbsBorderWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_WIDTH))
            self.dsbFormatDocImgThumbsBorderRadius.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_RADIUS))
            self.dsbFormatDocImgThumbsSpacingInner.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_INNER))
            self.cbxFormatDocImgThumbMode.setCurrentIndex(['fit','crop'].index(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_IMGMOD)))

            self.cbxFormatDocImgTextPosition.setCurrentIndex(['none','left','right','top','bottom'].index(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_POS)))
            self.fcbxFormatDocImgTextFontFamily.setCurrentFont(QFont(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTNAME)))
            self.dsbFormatDocImgTextFontSize.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTSIZE))
            self.pbFormatDocImgTextFontColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTCOL))

            self.cbxFormatDocImgPreviewMode.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PREVIEW_MODE))

            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()
            self.__updateFormatDocImgPaperSizeList()

        def defaultImgKra():
            # --- IMG/KRA interface ---
            imageResolution=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_RESOLUTION)
            imageIndex=3
            for itemIndex in range(self.cbxFormatDocImgPaperResolution.count()):
                if self.cbxFormatDocImgPaperResolution.itemData(itemIndex) == imageResolution:
                    imageIndex = itemIndex
                    break

            paperSize=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_SIZE)
            paperIndex=2
            for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
                if self.cbxFormatDocImgPaperSize.itemData(itemIndex) == paperSize:
                    paperIndex = itemIndex
                    break

            unit=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_UNIT)
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
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_ORIENTATION))
            self.cbFormatDocImgPaperColor.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR_ACTIVE))
            self.pbFormatDocImgPaperColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR))
            self.dsbFormatDocImgMarginsLeft.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LEFT))
            self.dsbFormatDocImgMarginsRight.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_RIGHT))
            self.dsbFormatDocImgMarginsTop.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_TOP))
            self.dsbFormatDocImgMarginsBottom.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_BOTTOM))
            self.cbFormatDocImgMarginsLinked.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LINKED))

            self.cbFormatDocImgHeader.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_ACTIVE))
            self.cbFormatDocImgFooter.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_ACTIVE))
            self.cbFormatDocImgFPageNotes.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_ACTIVE))
            self.cbFormatDocImgFPageNotesPreview.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_PREVIEW))

            self.bcsteFormatDocImgHeader.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_CONTENT))
            self.bcsteFormatDocImgFooter.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_CONTENT))
            self.bcsteFormatDocImgFPageNotes.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_CONTENT))

            self.sbFormatDocImgThumbsPerRow.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_NBPERROW))
            self.dsbFormatDocImgThumbsSpacingOuter.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_OUTER))

            self.cbFormatDocImgPageBgColor.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_ACTIVE))
            self.pbFormatDocImgPageBgColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_COL))

            self.cbFormatDocImgPageBorder.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_ACTIVE))
            self.pbFormatDocImgPageBorderColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_COL))
            self.dsbFormatDocImgPageBorderWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_WIDTH))
            self.dsbFormatDocImgPageBorderRadius.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_RADIUS))

            self.cbFormatDocImgThumbsBg.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_ACTIVE))
            self.pbFormatDocImgThumbsBgColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_COL))
            self.cbFormatDocImgThumbsBorder.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_ACTIVE))
            self.pbFormatDocImgThumbsBorderColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_COL))
            self.dsbFormatDocImgThumbsBorderWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_WIDTH))
            self.dsbFormatDocImgThumbsBorderRadius.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_RADIUS))
            self.dsbFormatDocImgThumbsSpacingInner.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_INNER))
            self.cbxFormatDocImgThumbMode.setCurrentIndex(['fit','crop'].index(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_IMGMOD)))

            self.cbxFormatDocImgTextPosition.setCurrentIndex(['none','left','right','top','bottom'].index(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_POS)))
            self.fcbxFormatDocImgTextFontFamily.setCurrentFont(QFont(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTNAME)))
            self.dsbFormatDocImgTextFontSize.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTSIZE))
            self.pbFormatDocImgTextFontColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTCOL))

            # placed here instead of __loadSettingsPageTarget
            self.cbTargetResultFileOpen.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_OPT_OPENFILE))

            self.cbxFormatDocImgPreviewMode.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PREVIEW_MODE))


            self.__updateFormatDocImgPaperSizeList()
            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()

        def defaultImgPng():
            # --- IMG/PNG interface ---
            imageResolution=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_RESOLUTION)
            imageIndex=3
            for itemIndex in range(self.cbxFormatDocImgPaperResolution.count()):
                if self.cbxFormatDocImgPaperResolution.itemData(itemIndex) == imageResolution:
                    imageIndex = itemIndex
                    break

            paperSize=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_SIZE)
            paperIndex=2
            for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
                if self.cbxFormatDocImgPaperSize.itemData(itemIndex) == paperSize:
                    paperIndex = itemIndex
                    break

            unit=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_UNIT)
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
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_ORIENTATION))
            self.cbFormatDocImgPaperColor.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR_ACTIVE))
            self.pbFormatDocImgPaperColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR))
            self.dsbFormatDocImgMarginsLeft.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LEFT))
            self.dsbFormatDocImgMarginsRight.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_RIGHT))
            self.dsbFormatDocImgMarginsTop.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_TOP))
            self.dsbFormatDocImgMarginsBottom.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_BOTTOM))
            self.cbFormatDocImgMarginsLinked.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LINKED))

            self.cbFormatDocImgHeader.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_ACTIVE))
            self.cbFormatDocImgFooter.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_ACTIVE))
            self.cbFormatDocImgFPageNotes.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_ACTIVE))
            self.cbFormatDocImgFPageNotesPreview.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_PREVIEW))

            self.bcsteFormatDocImgHeader.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_CONTENT))
            self.bcsteFormatDocImgFooter.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_CONTENT))
            self.bcsteFormatDocImgFPageNotes.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_CONTENT))

            self.sbFormatDocImgThumbsPerRow.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_NBPERROW))
            self.dsbFormatDocImgThumbsSpacingOuter.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_OUTER))

            self.cbFormatDocImgPageBgColor.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_ACTIVE))
            self.pbFormatDocImgPageBgColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_COL))

            self.cbFormatDocImgPageBorder.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_ACTIVE))
            self.pbFormatDocImgPageBorderColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_COL))
            self.dsbFormatDocImgPageBorderWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_WIDTH))
            self.dsbFormatDocImgPageBorderRadius.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_RADIUS))

            self.cbFormatDocImgThumbsBg.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_ACTIVE))
            self.pbFormatDocImgThumbsBgColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_COL))
            self.cbFormatDocImgThumbsBorder.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_ACTIVE))
            self.pbFormatDocImgThumbsBorderColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_COL))
            self.dsbFormatDocImgThumbsBorderWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_WIDTH))
            self.dsbFormatDocImgThumbsBorderRadius.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_RADIUS))
            self.dsbFormatDocImgThumbsSpacingInner.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_INNER))
            self.cbxFormatDocImgThumbMode.setCurrentIndex(['fit','crop'].index(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_IMGMOD)))

            self.cbxFormatDocImgTextPosition.setCurrentIndex(['none','left','right','top','bottom'].index(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_POS)))
            self.fcbxFormatDocImgTextFontFamily.setCurrentFont(QFont(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTNAME)))
            self.dsbFormatDocImgTextFontSize.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTSIZE))
            self.pbFormatDocImgTextFontColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTCOL))

            # placed here instead of __loadSettingsPageTarget
            self.cbTargetResultFileOpen.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_OPT_OPENFILE))

            self.cbxFormatDocImgPreviewMode.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PREVIEW_MODE))

            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()
            self.__updateFormatDocImgPaperSizeList()

        def defaultImgJpg():
            # --- IMG/JPG interface ---
            imageResolution=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_RESOLUTION)
            imageIndex=3
            for itemIndex in range(self.cbxFormatDocImgPaperResolution.count()):
                if self.cbxFormatDocImgPaperResolution.itemData(itemIndex) == imageResolution:
                    imageIndex = itemIndex
                    break

            paperSize=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_SIZE)
            paperIndex=2
            for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
                if self.cbxFormatDocImgPaperSize.itemData(itemIndex) == paperSize:
                    paperIndex = itemIndex
                    break

            unit=self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_UNIT)
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
            self.cbxFormatDocImgPaperOrientation.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_ORIENTATION))
            self.cbFormatDocImgPaperColor.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR_ACTIVE))
            self.pbFormatDocImgPaperColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR))
            self.dsbFormatDocImgMarginsLeft.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LEFT))
            self.dsbFormatDocImgMarginsRight.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_RIGHT))
            self.dsbFormatDocImgMarginsTop.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_TOP))
            self.dsbFormatDocImgMarginsBottom.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_BOTTOM))
            self.cbFormatDocImgMarginsLinked.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LINKED))

            self.cbFormatDocImgHeader.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_ACTIVE))
            self.cbFormatDocImgFooter.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_ACTIVE))
            self.cbFormatDocImgFPageNotes.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_ACTIVE))
            self.cbFormatDocImgFPageNotesPreview.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_PREVIEW))

            self.bcsteFormatDocImgHeader.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_CONTENT))
            self.bcsteFormatDocImgFooter.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_CONTENT))
            self.bcsteFormatDocImgFPageNotes.setHtml(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_CONTENT))

            self.sbFormatDocImgThumbsPerRow.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_NBPERROW))
            self.dsbFormatDocImgThumbsSpacingOuter.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_OUTER))

            self.cbFormatDocImgPageBgColor.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_ACTIVE))
            self.pbFormatDocImgPageBgColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_COL))

            self.cbFormatDocImgPageBorder.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_ACTIVE))
            self.pbFormatDocImgPageBorderColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_COL))
            self.dsbFormatDocImgPageBorderWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_WIDTH))
            self.dsbFormatDocImgPageBorderRadius.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_RADIUS))

            self.cbFormatDocImgThumbsBg.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_ACTIVE))
            self.pbFormatDocImgThumbsBgColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_COL))
            self.cbFormatDocImgThumbsBorder.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_ACTIVE))
            self.pbFormatDocImgThumbsBorderColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_COL))
            self.dsbFormatDocImgThumbsBorderWidth.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_WIDTH))
            self.dsbFormatDocImgThumbsBorderRadius.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_RADIUS))
            self.dsbFormatDocImgThumbsSpacingInner.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_INNER))
            self.cbxFormatDocImgThumbMode.setCurrentIndex(['fit','crop'].index(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_IMGMOD)))

            self.cbxFormatDocImgTextPosition.setCurrentIndex(['none','left','right','top','bottom'].index(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_POS)))
            self.fcbxFormatDocImgTextFontFamily.setCurrentFont(QFont(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTNAME)))
            self.dsbFormatDocImgTextFontSize.setValue(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTSIZE))
            self.pbFormatDocImgTextFontColor.setColor(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTCOL))

            # placed here instead of __loadSettingsPageTarget
            self.cbTargetResultFileOpen.setChecked(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_OPT_OPENFILE))

            self.cbxFormatDocImgPreviewMode.setCurrentIndex(self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PREVIEW_MODE))

            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__slotPageFormatDocImgPropertiesFontChanged()
            self.__updateFormatDocImgPaperSizeList()

        if target is None and isinstance(self.__options, dict) and 'exportFormat' in self.__options and 'exportConfig' in self.__options:
            # options has been provided, use it as settings
            self.cbxFormat.setCurrentIndex(self.__options['exportFormat'])
            self.__slotPageFormatFormatChanged()

            target=None
        elif not self.__hasSavedSettings:
            # no saved settings: load default and exit
            self.__loadDefaultPageFormat(target)
            return
        elif target is None:
            # --- ALL format ---
            self.cbxFormat.setCurrentIndex(BCSettings.get(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FORMAT))
            self.__slotPageFormatFormatChanged()

        if target is None:
            # -- pages
            defaultText()
            defaultTextMd()
            defaultTextCsv()
            if self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_DOC_PDF:
                defaultDocPdf()
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_KRA:
                defaultImgKra()
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_PNG:
                defaultImgPng()
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_JPG:
                defaultImgJpg()
            self.__updateFormatDocImgConfigurationPreview()
        elif target == BCExportFormat.EXPORT_FMT_DOC_PDF:
            defaultDocPdf()
        elif target == BCExportFormat.EXPORT_FMT_IMG_KRA:
            defaultImgKra()
        elif target == BCExportFormat.EXPORT_FMT_IMG_PNG:
            defaultImgPng()
        elif target == BCExportFormat.EXPORT_FMT_IMG_JPG:
            defaultImgJpg()

    def __updateSmallTextEditColors(self):
        """Update background color for small text edit"""
        color = Qt.white
        if self.cbFormatDocImgPageBgColor.isChecked():
            color=self.pbFormatDocImgPageBgColor.color()
        elif self.cbFormatDocImgPaperColor.isChecked():
            color=self.pbFormatDocImgPaperColor.color()

        self.bcsteFormatDocImgHeader.setTextBackgroundColor(color)
        self.bcsteFormatDocImgFooter.setTextBackgroundColor(color)
        self.bcsteFormatDocImgFPageNotes.setTextBackgroundColor(color)

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

    def __export(self):
        """Export process"""

        if not self.__options is None:

            if self.rbTargetResultClipboard.isChecked():
                exportedFileName = BCExportFilesDialogBox.CLIPBOARD
            else:
                exportedFileName = self.leTargetResultFile.text()

            self.__options={
                    'exportFormat': self.cbxFormat.currentIndex(),
                    'exportFileName': exportedFileName,
                    'exportConfig': self.__generateConfig(True)
                }

            self.accept()
            return

        if self.rbTargetResultClipboard.isChecked():
            self.__exportedFileName = BCExportFilesDialogBox.CLIPBOARD
        else:
            self.__exportedFileName = self.leTargetResultFile.text()

            if os.path.exists(self.__exportedFileName):
                if not WDialogBooleanInput.display(self.__title, i18n(f"Target file <b>{os.path.basename(self.__exportedFileName)}</b> already exist.<br><br>Do you want to override it?")):
                    return

        QApplication.setOverrideCursor(Qt.WaitCursor)

        self.wToolbar.setEnabled(False)
        self.pbPrevious.setEnabled(False)
        self.pbNext.setEnabled(False)
        self.pbExport.setEnabled(False)
        self.pbCancel.setEnabled(False)
        self.rbTargetResultFile.setEnabled(False)
        self.leTargetResultFile.setEnabled(False)
        self.pbTargetResultFile.setEnabled(False)
        self.cbTargetResultFileOpen.setEnabled(False)
        self.rbTargetResultClipboard.setEnabled(False)

        self.__uiController.filesSetAllowRefresh(False)

        if self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT:
            exported = self.__exporter.exportAsText(self.__exportedFileName, self.__generateConfig())
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_CSV:
            exported = self.__exporter.exportAsTextCsv(self.__exportedFileName, self.__generateConfig())
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_MD:
            exported = self.__exporter.exportAsTextMd(self.__exportedFileName, self.__generateConfig())
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_DOC_PDF:
            exported = self.__exporter.exportAsDocumentPdf(self.__exportedFileName, self.__generateConfig())
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_KRA:
            exported = self.__exporter.exportAsImageKra(self.__exportedFileName, self.__generateConfig())
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_PNG:
            exported = self.__exporter.exportAsImageSeq(self.__exportedFileName, self.__generateConfig(), 'png')
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_JPG:
            exported = self.__exporter.exportAsImageSeq(self.__exportedFileName, self.__generateConfig(), 'jpeg')

        self.__uiController.filesSetAllowRefresh(True)

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

            self.wToolbar.setEnabled(True)
            self.pbPrevious.setEnabled(True)
            self.pbExport.setEnabled(True)
            self.pbCancel.setEnabled(True)
            self.rbTargetResultFile.setEnabled(True)
            self.leTargetResultFile.setEnabled(True)
            self.pbTargetResultFile.setEnabled(True)
            self.cbTargetResultFileOpen.setEnabled(True)
            self.rbTargetResultClipboard.setEnabled(True)
            self.__exportEnd()

    def __updateFormatDocImgPaperSizeList(self, unit=None, orientation=None):
        """Update the cbxFormatDocImgPaperSize list"""

        if unit is None:
            unit = self.__formatPdfImgPaperSizeUnit

        if orientation is None:
            orientation = self.__formatPdfImgPaperOrientation

        unitFmt=BCExportFilesDialogBox.UNITS[unit]['fmt']

        for itemIndex in range(self.cbxFormatDocImgPaperSize.count()):
            paperSize = self.cbxFormatDocImgPaperSize.itemData(itemIndex)
            size=BCExportFiles.getPaperSize(paperSize, unit, self.__formatPdfImgPaperOrientation, self.__formatPdfImgPaperResolution)

            self.cbxFormatDocImgPaperSize.setItemText(itemIndex, f"{paperSize} - {size.width():{unitFmt}}x{size.height():{unitFmt}}")

    def __updateFormatDocImgConfigurationPreview(self):
        """Generate a configuration preview and update it"""
        if self.__formatPdfImgPaperSize.height() == 0 or not self.cbxFormat.currentIndex() in [BCExportFormat.EXPORT_FMT_IMG_KRA,
                                                                                               BCExportFormat.EXPORT_FMT_IMG_JPG,
                                                                                               BCExportFormat.EXPORT_FMT_IMG_PNG,
                                                                                               BCExportFormat.EXPORT_FMT_DOC_PDF]:
            return

        # paper size w/h ratio
        self.__formatPdfImgRatioPaperSize = self.__formatPdfImgPaperSize.width() / self.__formatPdfImgPaperSize.height()

        # get current configuration
        self.__formatPdfImgConfig = self.__generateConfig()

        # need real image size in pixels
        imageSize = BCExportFiles.getPaperSize(self.__formatPdfImgConfig['paper.size'],
                                               'px',
                                               self.__formatPdfImgConfig['paper.orientation'],
                                               self.__formatPdfImgConfig['paper.resolution'])

        self.__formatPdfImgPagesInformation = self.__exporter.getPagesInformation(imageSize, self.__formatPdfImgConfig, self.__formatPdfImgConfig)

        self.lblFormatDocImgPreviewNbPages.setText(i18n(f"Number of pages: {self.__formatPdfImgPagesInformation['page.total']}"))

        self.lblFormatDocImgPreview.update()

    def __updateFormatDocImgConfigurationPreviewPaint(self, event):
        """Generate a configuration preview and update it"""
        # Mathod is paintEvent() for widget lblFormatDocImgPreview

        def setActiveColor(activePage):
            if self.swFormatDocImgRef.currentIndex() == activePage:
                pen.setColor(Qt.blue)
                brush.setColor(Qt.blue)
            else:
                pen.setColor(Qt.lightGray)
                brush.setColor(Qt.lightGray)

        def drawLayoutMargins():
            # first page / margins
            pen.setStyle(Qt.DashLine)
            setActiveColor(0)
            painter.setPen(pen)

            drawingArea = previewPagesInformation['page.global.bounds']

            painter.drawLine(drawingArea.left(), previewRect.top(), drawingArea.left(), previewRect.bottom())
            painter.drawLine(drawingArea.right(), previewRect.top(), drawingArea.right(), previewRect.bottom())
            painter.drawLine(previewRect.left(), drawingArea.top(), previewRect.right(), drawingArea.top())
            painter.drawLine(previewRect.left(), drawingArea.bottom(), previewRect.right(), drawingArea.bottom())

            drawingArea.setLeft(drawingArea.left() + 2)
            drawingArea.setRight(drawingArea.right() - 3)
            drawingArea.setTop(drawingArea.top() + 2)
            drawingArea.setBottom(drawingArea.bottom() - 3)

        def drawLayoutLayout():
            pen.setStyle(Qt.SolidLine)
            brush.setStyle(Qt.DiagCrossPattern)
            setActiveColor(1)
            painter.setPen(pen)

            drawingArea = previewPagesInformation['page.inside.bounds']

            # ----------------------------------------------------------------------
            # Header
            top = 0
            if self.cbFormatDocImgHeader.isChecked() and previewPagesInformation['header.height'] > 0:
                areaHeight=previewPagesInformation['header.height'] - 2

                painter.fillRect( drawingArea.left(), top + drawingArea.top(), drawingArea.width(), areaHeight, brush)
                painter.drawRect( drawingArea.left(), top + drawingArea.top(), drawingArea.width(), areaHeight )

                top = previewPagesInformation['header.height']

            # ----------------------------------------------------------------------
            # Footer
            if self.cbFormatDocImgFooter.isChecked() and previewPagesInformation['footer.height'] > 0:
                areaHeight=previewPagesInformation['footer.height'] - 2

                painter.fillRect( drawingArea.left(), drawingArea.bottom() - areaHeight, drawingArea.width(), areaHeight, brush)
                painter.drawRect( drawingArea.left(), drawingArea.bottom() - areaHeight, drawingArea.width(), areaHeight )

            # ----------------------------------------------------------------------
            # First page layout
            if (self.cbFormatDocImgFPageNotesPreview.isChecked() or previewPagesInformation['page.total'] == 1) and self.cbFormatDocImgFPageNotes.isChecked() and previewPagesInformation['fpNotes.height'] > 0:
                areaHeight=previewPagesInformation['fpNotes.height'] - 2

                painter.fillRect( drawingArea.left(), top + drawingArea.top(), drawingArea.width(), areaHeight, brush)
                painter.drawRect( drawingArea.left(), top + drawingArea.top(), drawingArea.width(), areaHeight )

        def getThumbnailCellPixmap(textRows):
            # return a pixmap

            # draw one cell in a pixmap and then, paste same pixmap for each cell
            imageThumb = QImage(previewPagesInformation['cell.global.size'].width(), previewPagesInformation['cell.global.size'].height(), QImage.Format_ARGB32)
            imageThumb.fill(Qt.transparent)
            pixmapThumb = QPixmap.fromImage(imageThumb)

            painterThumb = QPainter()
            painterThumb.begin(pixmapThumb)

            pen.setStyle(Qt.DashLine)
            brush.setStyle(Qt.SolidPattern)

            setActiveColor(1)

            propertiesPosition = previewPagesInformation['cell.thumbnail.propPosition']
            thumbSize  = previewPagesInformation['cell.thumbnail.size'].height()
            textWidth = previewPagesInformation['cell.text.size'].width()
            textHeight = previewPagesInformation['cell.text.size'].height()
            if propertiesPosition == 'left':
                # left
                imgLeft = 2 + previewPagesInformation['cell.text.size'].width()
                imgTop = 2
                textLeft = 2
                textTop = 2
                textWidth-=2
                textHeight-=4
            elif propertiesPosition == 'right':
                # right
                imgLeft = 2
                imgTop = 2
                textLeft = thumbSize - 1
                textTop = 2
                textWidth-=2
                textHeight-=4
            elif propertiesPosition == 'top':
                # top
                imgLeft = 2
                imgTop = 2 + textHeight
                textLeft = 2
                textTop = 2
                textWidth-=5
                textHeight-=4
            elif propertiesPosition == 'bottom':
                # bottom
                imgLeft = 2
                imgTop = 2
                textLeft = 2
                textTop = 2 + thumbSize
                textWidth-=5
                textHeight-=4
            else:
                imgLeft = 2
                imgTop = 2
                textLeft = 0
                textTop = 0
                textHeight-=4

            # cell bounds
            painterThumb.setPen(pen)
            painterThumb.drawRect(0, 0, previewPagesInformation['cell.global.size'].width() - 1, previewPagesInformation['cell.global.size'].height() - 1)

            setActiveColor(2)

            painterThumb.setPen(pen)

            # thumb image
            painterThumb.drawPixmap(imgLeft, imgTop, buildIcon('pktk:image').pixmap(thumbSize - 5, thumbSize - 5))

            painterThumb.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painterThumb.fillRect(imgLeft, imgTop, thumbSize - 5, thumbSize - 5, brush)

            # thumbnail bounds
            painterThumb.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painterThumb.drawRect(imgLeft, imgTop, thumbSize - 5, thumbSize - 5)

            pen.setStyle(Qt.SolidLine)
            brush.setStyle(Qt.DiagCrossPattern)
            painterThumb.setPen(pen)

            # texts
            if propertiesPosition != 'none':
                painterThumb.fillRect( textLeft, textTop, textWidth, textHeight, brush)
                painterThumb.drawRect( textLeft, textTop, textWidth, textHeight )

            painterThumb.end()

            return pixmapThumb

        def drawLayoutThumbnails():
            if (self.cbFormatDocImgFPageNotesPreview.isChecked() or previewPagesInformation['page.total'] == 1) and self.cbFormatDocImgFPageNotes.isChecked() and previewPagesInformation['fpNotes.height'] > 0:
                drawingArea = previewPagesInformation['page.first.bounds']
                nbRows = previewPagesInformation['page.first.nbRowsMax']
            else:
                drawingArea = previewPagesInformation['page.normal.bounds']
                nbRows = previewPagesInformation['page.normal.nbRowsMax']

            thumbPerRow = self.sbFormatDocImgThumbsPerRow.value()

            pixmapThumb = getThumbnailCellPixmap(self.__formatPdfImgNbProperties)

            for rowNumber in range(nbRows):
                offsetLeft = 0
                for column in range(thumbPerRow):
                    painter.drawPixmap(drawingArea.left() + offsetLeft, drawingArea.top(), pixmapThumb)

                    offsetLeft+=previewPagesInformation['cell.global.size'].width() + previewPagesInformation['cell.thumbnail.outerSpacing']

                drawingArea.setTop(drawingArea.top() + previewPagesInformation['cell.global.size'].height() + previewPagesInformation['cell.thumbnail.outerSpacing'])

        # margin to border / arbitrary 6px
        margin = 6
        shadowOffset = 4

        if self.__formatPdfImgPaperSize.height() == 0:
            return

        if self.__formatPdfImgPaperOrientation == BCExportFilesDialogBox.ORIENTATION_PORTRAIT:
            previewHeight = floor(self.lblFormatDocImgPreview.height() - 2 * margin)
            previewWidth = floor(previewHeight * self.__formatPdfImgRatioPaperSize)

            ratioPaperPreview = previewHeight / self.__formatPdfImgPagesInformation['page.size'].height()
        else:
            previewWidth = self.lblFormatDocImgPreview.width() - 2 * margin
            previewHeight = floor(previewWidth / self.__formatPdfImgRatioPaperSize)

            ratioPaperPreview = previewWidth / self.__formatPdfImgPagesInformation['page.size'].width()

        previewRect = QRect((self.lblFormatDocImgPreview.width() - previewWidth)/2,
                            (self.lblFormatDocImgPreview.height() - previewHeight)/2,
                            previewWidth,
                            previewHeight
                        )

        # ----------------------------------------------------------------------
        # start rendering paper
        painter = QPainter(self.lblFormatDocImgPreview)

        # ----------------------------------------------------------------------
        # initialise a default pen
        pen = QPen()
        pen.setStyle(Qt.SolidLine)
        pen.setWidth(1)
        pen.setColor(Qt.darkGray)
        brush = QBrush()
        painter.setPen(pen)

        # ----------------------------------------------------------------------
        # paper shadow
        painter.fillRect(previewRect.left() + shadowOffset, previewRect.top() + shadowOffset, previewRect.width(), previewRect.height(), QColor(0x202020))

        previewPagesInformation = self.__formatPdfImgPagesInformation.copy()

        if previewPagesInformation['page.total'] == 1:
            self.cbFormatDocImgFPageNotesPreview.setVisible(False)
        else:
            self.cbFormatDocImgFPageNotesPreview.setVisible(True)

        # start rendering preview
        if self.cbxFormatDocImgPreviewMode.currentIndex() == BCExportFilesDialogBox.__PREVIEW_MODE_LAYOUT:
            # ----------------------------------------------------------------------
            # Paper white
            painter.fillRect(previewRect, Qt.white)

            # ----------------------------------------------------------------------
            # Initialise drawing area rect
            #drawingArea = QRect(QPoint(previewRect.left() + round(self.dsbFormatDocImgMarginsLeft.value() * ratioPaperPreview, 0),
            #                           previewRect.top() + round(self.dsbFormatDocImgMarginsTop.value() * ratioPaperPreview, 0)),
            #                    QPoint(1 + previewRect.right() - round(self.dsbFormatDocImgMarginsRight.value() * ratioPaperPreview, 0),
            #                           1 + previewRect.bottom() - round(self.dsbFormatDocImgMarginsBottom.value() * ratioPaperPreview, 0)))
            previewPagesInformation['page.global.bounds'] = QRect(
                                QPoint(previewRect.left() + floor(previewPagesInformation['page.global.bounds'].left() * ratioPaperPreview),
                                       previewRect.top() + floor(previewPagesInformation['page.global.bounds'].top() * ratioPaperPreview)),
                                QPoint(previewRect.left() + floor(previewPagesInformation['page.global.bounds'].right() * ratioPaperPreview),
                                       previewRect.top() + floor(previewPagesInformation['page.global.bounds'].bottom() * ratioPaperPreview)))

            previewPagesInformation['page.inside.bounds'] = QRect(
                                QPoint(previewRect.left() + 2 + floor(previewPagesInformation['page.inside.bounds'].left() * ratioPaperPreview),
                                       previewRect.top() + 2 + floor(previewPagesInformation['page.inside.bounds'].top() * ratioPaperPreview)),
                                QPoint(previewRect.left() + floor(previewPagesInformation['page.inside.bounds'].right() * ratioPaperPreview),
                                       previewRect.top() + floor(previewPagesInformation['page.inside.bounds'].bottom() * ratioPaperPreview)))

            previewPagesInformation['page.first.bounds'] = QRect(
                                QPoint(previewRect.left() + 2 + floor(previewPagesInformation['page.first.bounds'].left() * ratioPaperPreview),
                                       previewRect.top() + 2 + floor(previewPagesInformation['page.first.bounds'].top() * ratioPaperPreview)),
                                QPoint(previewRect.left() + floor(previewPagesInformation['page.first.bounds'].right() * ratioPaperPreview),
                                       previewRect.top() + floor(previewPagesInformation['page.first.bounds'].bottom() * ratioPaperPreview)))

            previewPagesInformation['page.normal.bounds'] = QRect(
                                QPoint(previewRect.left() + 2 + floor(previewPagesInformation['page.normal.bounds'].left() * ratioPaperPreview),
                                       previewRect.top() + 2 + floor(previewPagesInformation['page.normal.bounds'].top() * ratioPaperPreview)),
                                QPoint(previewRect.left() + floor(previewPagesInformation['page.normal.bounds'].right() * ratioPaperPreview),
                                       previewRect.top() + floor(previewPagesInformation['page.normal.bounds'].bottom() * ratioPaperPreview)))

            previewPagesInformation['header.height']=floor(previewPagesInformation['header.height'] * ratioPaperPreview)
            previewPagesInformation['footer.height']=floor(previewPagesInformation['footer.height'] * ratioPaperPreview)
            previewPagesInformation['fpNotes.height']=floor(previewPagesInformation['fpNotes.height'] * ratioPaperPreview)

            previewPagesInformation['cell.global.size']=QSize(
                                floor(previewPagesInformation['cell.global.size'].width() * ratioPaperPreview),
                                floor(previewPagesInformation['cell.global.size'].height() * ratioPaperPreview))

            previewPagesInformation['cell.thumbnail.size']=QSize(
                                floor(previewPagesInformation['cell.thumbnail.size'].width() * ratioPaperPreview),
                                floor(previewPagesInformation['cell.thumbnail.size'].height() * ratioPaperPreview))

            previewPagesInformation['cell.text.size']=QSize(
                                floor(previewPagesInformation['cell.text.size'].width() * ratioPaperPreview),
                                floor(previewPagesInformation['cell.text.size'].height() * ratioPaperPreview))

            previewPagesInformation['cell.thumbnail.outerSpacing']=floor(previewPagesInformation['cell.thumbnail.outerSpacing'] * ratioPaperPreview)
            previewPagesInformation['cell.thumbnail.innerSpacing']=floor(previewPagesInformation['cell.thumbnail.innerSpacing'] * ratioPaperPreview)

            # ----------------------------------------------------------------------
            # Margins
            drawLayoutMargins()

            # ----------------------------------------------------------------------
            # Header / Footer / First page layout
            drawLayoutLayout()

            # ----------------------------------------------------------------------
            # Thumbnails
            drawLayoutThumbnails()
        else:
            # ----------------------------------------------------------------------
            # Paper background
            painter.fillRect(previewRect, checkerBoardBrush())

            if self.cbFormatDocImgPaperColor.isChecked():
                painter.fillRect(previewRect, self.pbFormatDocImgPaperColor.color())

            if self.cbFormatDocImgFPageNotesPreview.isChecked() or previewPagesInformation['page.total'] == 1:
                self.__formatPdfImgPageCurrent = 1
            else:
                self.__formatPdfImgPageCurrent = 2
            self.__formatPdfImgPageTotal=previewPagesInformation['page.total']

            previewImg = QImage(previewPagesInformation['page.size'].width(), previewPagesInformation['page.size'].height(), QImage.Format_ARGB32)
            previewImg.fill(Qt.transparent)
            previewPixmap = QPixmap.fromImage(previewImg)

            previewPainter = QPainter()
            previewPainter.begin(previewPixmap)

            self.__exporter.drawPage(previewPainter, self.__formatPdfImgPagesInformation, self.__formatPdfImgConfig, self.__formatPdfImgConfig, self.__formatPdfImgPageCurrent, self.__formatPdfImgPageTotal)

            previewPainter.end()

            painter.drawPixmap(previewRect.left(), previewRect.top(), previewPixmap.scaled(previewRect.width(), previewRect.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

        # ----------------------------------------------------------------------
        # finalize rendering paper
        # --
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

        self.dsbFormatDocImgThumbsSpacingOuter.setMaximum(round(self.__formatPdfImgPaperSize.width() * 0.25, roundDec))
        self.dsbFormatDocImgThumbsSpacingInner.setMaximum(round(self.__formatPdfImgPaperSize.width() * 0.25, roundDec))

    # -- slots
    def __slotPageFormatFormatChanged(self, index=None):
        # update current format page
        if index is None:
            index = self.cbxFormat.currentIndex()

        if index!=self.cbxFormat.currentIndex():
            self.__setModified(True)

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
                #self.lblFormatDocImgPaperResolution.setVisible(False)
                #self.cbxFormatDocImgPaperResolution.setVisible(False)
            else:
                self.lblFormatDocImgPaperOrImage.setText(i18n('Image'))
                #self.lblFormatDocImgPaperResolution.setVisible(True)
                #self.cbxFormatDocImgPaperResolution.setVisible(True)
            self.__loadSettingsPageFormat(index)
            self.__initFormatDocImgLists()
            self.__slotPageFormatDocImgPageSetupResolutionChanged()
            self.__slotPageFormatDocImgPageSetupUnitChanged()
            self.__slotPageFormatDocImgPageSetupSizeChanged()
            self.__slotPageFormatDocImgPageSetupOrientationChanged()
            self.__slotPageFormatDocImgPageSetupMarginLinkChanged()
            self.__slotPageFormatDocImgPageLayoutChanged()
            self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatTextLayoutUserDefined(self, checked=None):
        # user defined layout option ahs been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextLayoutUserDefined.isChecked()

        if checked!=self.cbFormatTextLayoutUserDefined.isChecked():
            self.__setModified(True)

        self.teFormatTextLayoutUserDefined.setEnabled(checked)

    def __slotPageFormatTextBordersCheck(self, checked=None):
        # user defined borders option ahs been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextBorders.isChecked()

        if checked!=self.cbFormatTextBorders.isChecked():
            self.__setModified(True)

        if not checked:
            self.rbFormatTextBorderNone.setChecked(True)

    def __slotPageFormatTextBordersStyleCheck(self, checked=None):
        self.__setModified(True)
        self.cbFormatTextBorders.setChecked(not self.rbFormatTextBorderNone.isChecked())

    def __slotPageFormatTextMinWidthCheck(self, checked=None):
        # State of checkbox Minimum width has been changed
        if checked is None:
            checked = self.cbFormatTextMinWidth.isChecked()

        if checked!=self.cbFormatTextMinWidth.isChecked():
            self.__setModified(True)

        self.hsFormatTextMinWidth.setEnabled(checked)
        self.spFormatTextMinWidth.setEnabled(checked)

    def __slotPageFormatTextMaxWidthCheck(self, checked=None):
        # State of checkbox Maximum width has been changed
        if checked is None:
            checked = self.cbFormatTextMaxWidth.isChecked()

        if checked!=self.cbFormatTextMaxWidth.isChecked():
            self.__setModified(True)

        self.hsFormatTextMaxWidth.setEnabled(checked)
        self.spFormatTextMaxWidth.setEnabled(checked)

    def __slotPageFormatTextMinWidthChanged(self, value=None):
        # Value of Minimum width has changed
        # > ensure that's not greater than maximum witdh
        if value is None:
            value = self.hsFormatTextMinWidth.value()

        if value!=self.hsFormatTextMinWidth.value():
            self.__setModified(True)

        if value > self.hsFormatTextMaxWidth.value():
            self.hsFormatTextMaxWidth.setValue(value)

    def __slotPageFormatTextMaxWidthChanged(self, value=None):
        # Value of Maximum width has changed
        # > ensure that's not greater than minimum witdh
        if value is None:
            value = self.hsFormatTextMaxWidth.value()

        if value!=self.hsFormatTextMaxWidth.value():
            self.__setModified(True)

        if value < self.hsFormatTextMinWidth.value():
            self.hsFormatTextMinWidth.setValue(value)

    def __slotPageFormatTextMDLayoutUserDefined(self, checked=None):
        # user defined layout option has been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextMDLayoutUserDefined.isChecked()

        if checked!=self.cbFormatTextMDLayoutUserDefined.isChecked():
            self.__setModified(True)

        self.teFormatTextMDLayoutUserDefined.setEnabled(checked)

    def __slotPageFormatTextMDIncludeThumbnails(self, checked=None):
        # include thumbnail in md export has been checked/unchecked
        if checked is None:
            checked = self.cbFormatTextMDIncludeThumbnails.isChecked()

        if checked!=self.cbFormatTextMDIncludeThumbnails.isChecked():
            self.__setModified(True)

        self.cbxFormatTextMDThumbnailsSize.setEnabled(checked)

    def __slotPageFormatDocImgRefChanged(self):
        """Set page according to current configuration type"""
        self.__setModified(True)
        self.swFormatDocImgRef.setCurrentIndex(self.lvFormatDocImgRef.currentIndex().data(Qt.UserRole))
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageSetupResolutionChanged(self):
        """Resolution has been changed"""
        self.__setModified(True)
        self.__formatPdfImgPaperResolution = BCExportFilesDialogBox.IMAGE_RESOLUTIONS[self.cbxFormatDocImgPaperResolution.currentText()]
        self.__slotPageFormatDocImgPageSetupSizeChanged()
        self.__slotPageFormatDocImgPageSetupUnitChanged()

    def __slotPageFormatDocImgPageSetupUnitChanged(self, dummy=None):
        """Choice of unit has been modified"""
        self.__setModified(True)
        unit=self.cbxFormatDocImgPaperUnit.currentData()
        if self.__blockedSlots or unit is None:
            return
        self.__blockSlot(True)

        # Temporary set No maximum value to ensure conversion will be proper applied
        self.dsbFormatDocImgMarginsLeft.setMaximum(9999)
        self.dsbFormatDocImgMarginsRight.setMaximum(9999)
        self.dsbFormatDocImgMarginsTop.setMaximum(9999)
        self.dsbFormatDocImgMarginsBottom.setMaximum(9999)
        self.dsbFormatDocImgThumbsSpacingOuter.setMaximum(9999)

        vMarginLeft = self.dsbFormatDocImgMarginsLeft.value()
        vMarginRight = self.dsbFormatDocImgMarginsRight.value()
        vMarginTop = self.dsbFormatDocImgMarginsTop.value()
        vMarginBottom = self.dsbFormatDocImgMarginsBottom.value()
        vMarginThumbSpacingOuter = self.dsbFormatDocImgThumbsSpacingOuter.value()
        vMarginThumbSpacingInner = self.dsbFormatDocImgThumbsSpacingInner.value()
        vPageBorderWidth = self.dsbFormatDocImgPageBorderWidth.value()
        vPageBorderRadius = self.dsbFormatDocImgPageBorderRadius.value()
        vThumbsBorderWidth = self.dsbFormatDocImgThumbsBorderWidth.value()
        vThumbsBorderRadius = self.dsbFormatDocImgThumbsBorderRadius.value()

        self.dsbFormatDocImgMarginsLeft.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgMarginsRight.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgMarginsTop.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgMarginsBottom.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgThumbsSpacingOuter.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgThumbsSpacingInner.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgPageBorderWidth.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgPageBorderRadius.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgThumbsBorderWidth.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])
        self.dsbFormatDocImgThumbsBorderRadius.setDecimals(BCExportFilesDialogBox.UNITS[unit]['marginDec'])

        self.dsbFormatDocImgMarginsLeft.setValue(BCExportFiles.convertSize(vMarginLeft, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgMarginsRight.setValue(BCExportFiles.convertSize(vMarginRight, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgMarginsTop.setValue(BCExportFiles.convertSize(vMarginTop, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgMarginsBottom.setValue(BCExportFiles.convertSize(vMarginBottom, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgThumbsSpacingOuter.setValue(BCExportFiles.convertSize(vMarginThumbSpacingOuter, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgThumbsSpacingInner.setValue(BCExportFiles.convertSize(vMarginThumbSpacingInner, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgPageBorderWidth.setValue(BCExportFiles.convertSize(vPageBorderWidth, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgPageBorderRadius.setValue(BCExportFiles.convertSize(vPageBorderRadius, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgThumbsBorderWidth.setValue(BCExportFiles.convertSize(vThumbsBorderWidth, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))
        self.dsbFormatDocImgThumbsBorderRadius.setValue(BCExportFiles.convertSize(vThumbsBorderRadius, self.__formatPdfImgPaperSizeUnit, unit, self.__formatPdfImgPaperResolution))

        self.dsbFormatDocImgMarginsLeft.setSuffix(f" {unit}")
        self.dsbFormatDocImgMarginsRight.setSuffix(f" {unit}")
        self.dsbFormatDocImgMarginsTop.setSuffix(f" {unit}")
        self.dsbFormatDocImgMarginsBottom.setSuffix(f" {unit}")
        self.dsbFormatDocImgThumbsSpacingOuter.setSuffix(f" {unit}")
        self.dsbFormatDocImgThumbsSpacingInner.setSuffix(f" {unit}")
        self.dsbFormatDocImgPageBorderWidth.setSuffix(f" {unit}")
        self.dsbFormatDocImgPageBorderRadius.setSuffix(f" {unit}")
        self.dsbFormatDocImgThumbsBorderWidth.setSuffix(f" {unit}")
        self.dsbFormatDocImgThumbsBorderRadius.setSuffix(f" {unit}")

        self.__formatPdfImgPaperSizeUnit = unit
        self.__blockSlot(False)
        self.__slotPageFormatDocImgPageSetupSizeChanged()
        self.__updateFormatDocImgMargins()
        self.__updateFormatDocImgPaperSizeList()
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageSetupSizeChanged(self, dummy=None):
        """Choice of size has been modified"""
        self.__setModified(True)
        if self.__formatPdfImgPaperSizeUnit is None or self.cbxFormatDocImgPaperSize.currentData() is None:
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

        if self.__blockedSlots:
            return

        self.__updateFormatDocImgMargins()
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageSetupOrientationChanged(self, dummy=None):
        """Choice of orientation has been modified"""
        self.__setModified(True)
        self.__formatPdfImgPaperOrientation = self.cbxFormatDocImgPaperOrientation.currentIndex()

        if self.__blockedSlots:
            return

        self.__slotPageFormatDocImgPageSetupSizeChanged()
        self.__updateFormatDocImgPaperSizeList()
        self.__updateFormatDocImgMargins()
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageSetupMarginLChanged(self, dummy=None):
        """Margin LEFT has been modified"""
        self.__setModified(True)
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            self.dsbFormatDocImgMarginsRight.setValue(self.dsbFormatDocImgMarginsLeft.value())
            self.dsbFormatDocImgMarginsTop.setValue(self.dsbFormatDocImgMarginsLeft.value())
            self.dsbFormatDocImgMarginsBottom.setValue(self.dsbFormatDocImgMarginsLeft.value())
        self.__blockSlot(False)
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageSetupMarginRChanged(self, dummy=None):
        """Margin RIGHT has been modified"""
        self.__setModified(True)
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            self.dsbFormatDocImgMarginsLeft.setValue(self.dsbFormatDocImgMarginsRight.value())
            self.dsbFormatDocImgMarginsTop.setValue(self.dsbFormatDocImgMarginsRight.value())
            self.dsbFormatDocImgMarginsBottom.setValue(self.dsbFormatDocImgMarginsRight.value())
        self.__blockSlot(False)
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageSetupMarginTChanged(self, dummy=None):
        """Margin TOP has been modified"""
        self.__setModified(True)
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            self.dsbFormatDocImgMarginsLeft.setValue(self.dsbFormatDocImgMarginsTop.value())
            self.dsbFormatDocImgMarginsRight.setValue(self.dsbFormatDocImgMarginsTop.value())
            self.dsbFormatDocImgMarginsBottom.setValue(self.dsbFormatDocImgMarginsTop.value())
        self.__blockSlot(False)
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageSetupMarginBChanged(self, dummy=None):
        """Margin BOTTOM has been modified"""
        self.__setModified(True)
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            self.dsbFormatDocImgMarginsLeft.setValue(self.dsbFormatDocImgMarginsBottom.value())
            self.dsbFormatDocImgMarginsRight.setValue(self.dsbFormatDocImgMarginsBottom.value())
            self.dsbFormatDocImgMarginsTop.setValue(self.dsbFormatDocImgMarginsBottom.value())
        self.__blockSlot(False)
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageSetupMarginLinkChanged(self, dummy=None):
        """Margins linked has been modified"""
        self.__setModified(True)
        if self.__blockedSlots:
            return
        self.__blockSlot(True)
        if self.cbFormatDocImgMarginsLinked.isChecked():
            # In this case, use Left margin as reference
            self.dsbFormatDocImgMarginsRight.setValue(self.dsbFormatDocImgMarginsLeft.value())
            self.dsbFormatDocImgMarginsTop.setValue(self.dsbFormatDocImgMarginsLeft.value())
            self.dsbFormatDocImgMarginsBottom.setValue(self.dsbFormatDocImgMarginsLeft.value())
        self.__blockSlot(False)
        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPageLayoutChanged(self, dummy=None):
        """page layout has been modified"""
        self.__setModified(True)
        self.bcsteFormatDocImgHeader.setEnabled(self.cbFormatDocImgHeader.isChecked())
        self.bcsteFormatDocImgFooter.setEnabled(self.cbFormatDocImgFooter.isChecked())
        self.bcsteFormatDocImgFPageNotes.setEnabled(self.cbFormatDocImgFPageNotes.isChecked())

        self.__updateSmallTextEditColors()

        self.__updateFormatDocImgConfigurationPreview()

    def __slotPageFormatDocImgPropertiesFontChanged(self, dummy=None):
        """Font family/size changed"""
        self.__setModified(True)
        self.__formatPdfImgFontSize = self.dsbFormatDocImgTextFontSize.value()
        self.__updateFormatDocImgConfigurationPreview()

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

        self.leTargetResultFile.setProperty('__bcExtension', self.__getSettings(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FILENAME))

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

            self.__formatPdfImgNbProperties=len(self.lwPerimeterProperties.items(True))
            self.__updateFormatDocImgConfigurationPreview()

        if self.swPages.currentIndex() == BCExportFilesDialogBox.__PAGE_TARGET:
            # when last page reached, enable/disable clipboard choice according to export format

            if self.leTargetResultFile.text() == '':
                # no file name defined, get file name from settings
                fileName = strDefault(self.leTargetResultFile.property('__bcExtension'))
            else:
                # a name is already set...?
                # update extension
                if result:=re.match("(.*)(\.[^\.]*)$", self.leTargetResultFile.text()):
                    fileName = f"{result.groups()[0]}.{{ext}}"
                else:
                    fileName = f"{self.leTargetResultFile.text()}.{{ext}}"

            fileOpenAllowed={
                    # do not allow option 'open file in krita' from search result
                    'status': (BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['openInKrita'] and self.__options is None),
                    'tooltip': ''
                }
            if fileOpenAllowed['status']:
                if self.cbxFormat.currentIndex() in [BCExportFormat.EXPORT_FMT_IMG_JPG, BCExportFormat.EXPORT_FMT_IMG_PNG] and self.__formatPdfImgEstimatedPages>10:
                    fileOpenAllowed['tooltip'] = i18n(f'Please be aware that {self.__formatPdfImgEstimatedPages} documents will be opened if option is checked!')

            if not fileOpenAllowed['status']:
                self.cbTargetResultFileOpen.setChecked(False)
                self.cbTargetResultFileOpen.setVisible(False)
            else:
                self.cbTargetResultFileOpen.setVisible(True)
                self.cbTargetResultFileOpen.setToolTip(fileOpenAllowed['tooltip'])

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

            if fileName==BCExportFilesDialogBox.CLIPBOARD:
                self.leTargetResultFile.setText('')
                if clipboardAllowed['status']:
                    self.rbTargetResultClipboard.setChecked(True)
            else:
                self.leTargetResultFile.setText(fileName.replace('{ext}', BCExportFilesDialogBox.FMT_PROPERTIES[self.cbxFormat.currentIndex()]['fileExtension']))


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
            self.pbNext.setEnabled(len(self.lwPerimeterProperties.items(True))>0)
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

    def __generateConfig(self, fullFields=False):
        """Generate export config"""
        def getFields(fullFields):
            if fullFields:
                checkedChar={True:'*', False:'.'}
                return [f"{checkedChar[item.checked()]}{item.value()}" for item in self.lwPerimeterProperties.items(False)]
            else:
                return [item.value() for item in self.lwPerimeterProperties.items(True)]

        def getFiles():
            if self.rbPerimeterSelectPath.isChecked():
                return self.__fileNfo[5]
            else:
                return self.__selectedFileNfo[5]

        def getSource():
            if self.rbPerimeterSelectPath.isChecked():
                return self.__getPath()
            else:
                return ''

        returned = {}

        if self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT:
            returned = {
                    'userDefinedLayout.active': self.cbFormatTextLayoutUserDefined.isChecked(),
                    'userDefinedLayout.content': self.teFormatTextLayoutUserDefined.toPlainText(),

                    'header.active': self.cbFormatTextHeader.isChecked(),

                    'borders.style': TextTableSettingsText.BORDER_NONE,

                    'minimumWidth.active': self.cbFormatTextMinWidth.isChecked(),
                    'minimumWidth.value': self.spFormatTextMinWidth.value(),

                    'maximumWidth.active': self.cbFormatTextMaxWidth.isChecked(),
                    'maximumWidth.value': self.spFormatTextMaxWidth.value(),

                    'fields': getFields(fullFields),
                    'files': getFiles(),
                    'source': getSource()
                }

            if self.rbFormatTextBorderBasic.isChecked():
                returned['borders.style'] = TextTableSettingsText.BORDER_BASIC
            elif self.rbFormatTextBorderSimple.isChecked():
                returned['borders.style'] = TextTableSettingsText.BORDER_SIMPLE
            elif self.rbFormatTextBorderDouble.isChecked():
                returned['borders.style'] = TextTableSettingsText.BORDER_DOUBLE

        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_CSV:
            returned = {
                    'header.active': self.cbFormatTextCSVHeader.isChecked(),

                    'fields.enclosed': self.cbFormatTextCSVEnclosedFields.isChecked(),
                    'fields.separator': [',', ';', '\t', '|'][self.cbxFormatTextCSVSeparator.currentIndex()],

                    'fields': getFields(fullFields),
                    'files': getFiles(),
                    'source': getSource()
                }
        elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_MD:
            returned = {
                    'userDefinedLayout.active': self.cbFormatTextMDLayoutUserDefined.isChecked(),
                    'userDefinedLayout.content': self.teFormatTextMDLayoutUserDefined.toPlainText(),

                    'thumbnails.included': self.cbFormatTextMDIncludeThumbnails.isChecked(),
                    'thumbnails.size': [64,128,256,512][self.cbxFormatTextMDThumbnailsSize.currentIndex()],

                    'fields': getFields(fullFields),
                    'files': getFiles(),
                    'source': getSource()
                }
        elif self.cbxFormat.currentIndex() in [BCExportFormat.EXPORT_FMT_IMG_KRA,
                                               BCExportFormat.EXPORT_FMT_IMG_JPG,
                                               BCExportFormat.EXPORT_FMT_IMG_PNG,
                                               BCExportFormat.EXPORT_FMT_DOC_PDF]:
            returned = {
                    'thumbnails.background.active': self.cbFormatDocImgThumbsBg.isChecked(),
                    'thumbnails.background.color': self.pbFormatDocImgThumbsBgColor.color(),
                    'thumbnails.border.active': self.cbFormatDocImgThumbsBorder.isChecked(),
                    'thumbnails.border.color': self.pbFormatDocImgThumbsBorderColor.color(),
                    'thumbnails.border.width': self.dsbFormatDocImgThumbsBorderWidth.value(),
                    'thumbnails.border.radius': self.dsbFormatDocImgThumbsBorderRadius.value(),
                    'thumbnails.image.displayMode': ['fit', 'crop'][self.cbxFormatDocImgThumbMode.currentIndex()],
                    'thumbnails.text.position': ['none', 'left', 'right', 'top', 'bottom'][self.cbxFormatDocImgTextPosition.currentIndex()],
                    'thumbnails.text.font.name': self.fcbxFormatDocImgTextFontFamily.currentFont().family(),
                    'thumbnails.text.font.size': self.dsbFormatDocImgTextFontSize.value(),
                    'thumbnails.text.font.color': self.pbFormatDocImgTextFontColor.color(),

                    'thumbnails.layout.nbPerRow': self.sbFormatDocImgThumbsPerRow.value(),
                    'thumbnails.layout.spacing.inner': self.dsbFormatDocImgThumbsSpacingInner.value(),
                    'thumbnails.layout.spacing.outer': self.dsbFormatDocImgThumbsSpacingOuter.value(),

                    'page.background.active': self.cbFormatDocImgPageBgColor.isChecked(),
                    'page.background.color': self.pbFormatDocImgPageBgColor.color(),
                    'page.border.active': self.cbFormatDocImgPageBorder.isChecked(),
                    'page.border.color': self.pbFormatDocImgPageBorderColor.color(),
                    'page.border.width': self.dsbFormatDocImgPageBorderWidth.value(),
                    'page.border.radius': self.dsbFormatDocImgPageBorderRadius.value(),

                    'firstPageNotes.active': self.cbFormatDocImgFPageNotes.isChecked(),
                    'firstPageNotes.content': self.bcsteFormatDocImgFPageNotes.toHtml(),
                    'footer.active': self.cbFormatDocImgFooter.isChecked(),
                    'footer.content': self.bcsteFormatDocImgFooter.toHtml(),
                    'header.active': self.cbFormatDocImgHeader.isChecked(),
                    'header.content': self.bcsteFormatDocImgHeader.toHtml(),
                    'margins.bottom': self.dsbFormatDocImgMarginsBottom.value(),
                    'margins.left': self.dsbFormatDocImgMarginsLeft.value(),
                    'margins.right': self.dsbFormatDocImgMarginsRight.value(),
                    'margins.top': self.dsbFormatDocImgMarginsTop.value(),
                    'paper.orientation': self.cbxFormatDocImgPaperOrientation.currentIndex(),
                    'paper.size': self.cbxFormatDocImgPaperSize.currentData(),
                    'paper.resolution': self.cbxFormatDocImgPaperResolution.currentData(),
                    'paper.color.active': self.cbFormatDocImgPaperColor.isChecked(),
                    'paper.color.value': self.pbFormatDocImgPaperColor.color(),
                    'paper.unit': self.cbxFormatDocImgPaperUnit.currentData(),

                    'file.openInKrita': self.cbTargetResultFileOpen.isChecked(),

                    'fields': getFields(fullFields),
                    'files': getFiles(),
                    'source': getSource()
                }

        return returned

    def __saveSettings(self):
        """Save current export configuration to settings"""
        def __savePagePerimeter():
            checkedChar={True:'*', False:'.'}
            BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_PROPERTIES, [f"{checkedChar[item.checked()]}{item.value()}" for item in self.lwPerimeterProperties.items(False)])

        def __savePageFormat():
            BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FORMAT, self.cbxFormat.currentIndex())

            if self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT:
                # -- TEXT format --
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_ACTIVE, self.cbFormatTextLayoutUserDefined.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_CONTENT, self.teFormatTextLayoutUserDefined.toPlainText())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_HEADER_ACTIVE, self.cbFormatTextHeader.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE, self.cbFormatTextBorders.isChecked())

                if self.rbFormatTextBorderNone.isChecked():
                    currentBordersStyle = 0
                elif self.rbFormatTextBorderBasic.isChecked():
                    currentBordersStyle = 1
                elif self.rbFormatTextBorderSimple.isChecked():
                    currentBordersStyle = 2
                elif self.rbFormatTextBorderDouble.isChecked():
                    currentBordersStyle = 3
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE, currentBordersStyle)

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_ACTIVE, self.cbFormatTextMinWidth.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_VALUE, self.hsFormatTextMinWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_ACTIVE, self.cbFormatTextMaxWidth.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_VALUE, self.hsFormatTextMaxWidth.value())
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_MD:
                # -- TEXT/MARKDOWN format --
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_ACTIVE, self.cbFormatTextMDLayoutUserDefined.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_CONTENT, self.teFormatTextMDLayoutUserDefined.toPlainText())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_INCLUDED, self.cbFormatTextMDIncludeThumbnails.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_SIZE, self.cbxFormatTextMDThumbnailsSize.currentIndex())
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_TEXT_CSV:
                # -- TEXT/CSV format --
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_HEADER_ACTIVE, self.cbFormatTextCSVHeader.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_ENCLOSED, self.cbFormatTextCSVEnclosedFields.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_SEPARATOR, self.cbxFormatTextCSVSeparator.currentIndex())
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_DOC_PDF:
                # -- DOC/PDF format --
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_RESOLUTION, self.cbxFormatDocImgPaperResolution.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_SIZE, self.cbxFormatDocImgPaperSize.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_UNIT, self.cbxFormatDocImgPaperUnit.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_ORIENTATION, self.cbxFormatDocImgPaperOrientation.currentIndex())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR_ACTIVE, self.cbFormatDocImgPaperColor.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR, self.pbFormatDocImgPaperColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LEFT, self.dsbFormatDocImgMarginsLeft.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_RIGHT, self.dsbFormatDocImgMarginsRight.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_TOP, self.dsbFormatDocImgMarginsTop.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_BOTTOM, self.dsbFormatDocImgMarginsBottom.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LINKED, self.cbFormatDocImgMarginsLinked.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_ACTIVE, self.cbFormatDocImgHeader.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_ACTIVE, self.cbFormatDocImgFooter.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_ACTIVE, self.cbFormatDocImgFPageNotes.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_PREVIEW, self.cbFormatDocImgFPageNotesPreview.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_CONTENT, self.bcsteFormatDocImgHeader.toHtml())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_CONTENT, self.bcsteFormatDocImgFooter.toHtml())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_CONTENT, self.bcsteFormatDocImgFPageNotes.toHtml())


                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_ACTIVE, self.cbFormatDocImgPageBgColor.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_COL, self.pbFormatDocImgPageBgColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_ACTIVE, self.cbFormatDocImgPageBorder.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_COL, self.pbFormatDocImgPageBorderColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_WIDTH, self.dsbFormatDocImgPageBorderWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_RADIUS, self.dsbFormatDocImgPageBorderRadius.value())


                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_NBPERROW, self.sbFormatDocImgThumbsPerRow.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_OUTER, self.dsbFormatDocImgThumbsSpacingOuter.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_INNER, self.dsbFormatDocImgThumbsSpacingInner.value())
                #BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_TEXT, self.xxx.value())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_ACTIVE, self.cbFormatDocImgThumbsBg.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_COL, self.pbFormatDocImgThumbsBgColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_ACTIVE, self.cbFormatDocImgThumbsBorder.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_COL, self.pbFormatDocImgThumbsBorderColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_WIDTH, self.dsbFormatDocImgThumbsBorderWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_RADIUS, self.dsbFormatDocImgThumbsBorderRadius.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_IMGMOD, ['fit', 'crop'][self.cbxFormatDocImgThumbMode.currentIndex()])

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_POS, ['none', 'left', 'right', 'top', 'bottom'][self.cbxFormatDocImgTextPosition.currentIndex()])
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTNAME, self.fcbxFormatDocImgTextFontFamily.currentFont().family())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTSIZE, self.dsbFormatDocImgTextFontSize.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTCOL, self.pbFormatDocImgTextFontColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PREVIEW_MODE, self.cbxFormatDocImgPreviewMode.currentIndex())
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_KRA:
                # -- IMG/KRA format --
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_RESOLUTION, self.cbxFormatDocImgPaperResolution.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_SIZE, self.cbxFormatDocImgPaperSize.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_UNIT, self.cbxFormatDocImgPaperUnit.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_ORIENTATION, self.cbxFormatDocImgPaperOrientation.currentIndex())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR_ACTIVE, self.cbFormatDocImgPaperColor.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR, self.pbFormatDocImgPaperColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LEFT, self.dsbFormatDocImgMarginsLeft.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_RIGHT, self.dsbFormatDocImgMarginsRight.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_TOP, self.dsbFormatDocImgMarginsTop.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_BOTTOM, self.dsbFormatDocImgMarginsBottom.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LINKED, self.cbFormatDocImgMarginsLinked.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_ACTIVE, self.cbFormatDocImgHeader.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_ACTIVE, self.cbFormatDocImgFooter.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_ACTIVE, self.cbFormatDocImgFPageNotes.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_PREVIEW, self.cbFormatDocImgFPageNotesPreview.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_CONTENT, self.bcsteFormatDocImgHeader.toHtml())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_CONTENT, self.bcsteFormatDocImgFooter.toHtml())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_CONTENT, self.bcsteFormatDocImgFPageNotes.toHtml())


                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_ACTIVE, self.cbFormatDocImgPageBgColor.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_COL, self.pbFormatDocImgPageBgColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_ACTIVE, self.cbFormatDocImgPageBorder.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_COL, self.pbFormatDocImgPageBorderColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_WIDTH, self.dsbFormatDocImgPageBorderWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_RADIUS, self.dsbFormatDocImgPageBorderRadius.value())


                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_NBPERROW, self.sbFormatDocImgThumbsPerRow.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_OUTER, self.dsbFormatDocImgThumbsSpacingOuter.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_INNER, self.dsbFormatDocImgThumbsSpacingInner.value())
                #BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_TEXT, self.xxx.value())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_ACTIVE, self.cbFormatDocImgThumbsBg.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_COL, self.pbFormatDocImgThumbsBgColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_ACTIVE, self.cbFormatDocImgThumbsBorder.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_COL, self.pbFormatDocImgThumbsBorderColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_WIDTH, self.dsbFormatDocImgThumbsBorderWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_RADIUS, self.dsbFormatDocImgThumbsBorderRadius.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_IMGMOD, ['fit', 'crop'][self.cbxFormatDocImgThumbMode.currentIndex()])

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_POS, ['none', 'left', 'right', 'top', 'bottom'][self.cbxFormatDocImgTextPosition.currentIndex()])
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTNAME, self.fcbxFormatDocImgTextFontFamily.currentFont().family())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTSIZE, self.dsbFormatDocImgTextFontSize.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTCOL, self.pbFormatDocImgTextFontColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_OPT_OPENFILE, self.cbTargetResultFileOpen.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PREVIEW_MODE, self.cbxFormatDocImgPreviewMode.currentIndex())
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_PNG:
                # -- IMG/PNG format --
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_RESOLUTION, self.cbxFormatDocImgPaperResolution.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_SIZE, self.cbxFormatDocImgPaperSize.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_UNIT, self.cbxFormatDocImgPaperUnit.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_ORIENTATION, self.cbxFormatDocImgPaperOrientation.currentIndex())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR_ACTIVE, self.cbFormatDocImgPaperColor.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR, self.pbFormatDocImgPaperColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LEFT, self.dsbFormatDocImgMarginsLeft.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_RIGHT, self.dsbFormatDocImgMarginsRight.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_TOP, self.dsbFormatDocImgMarginsTop.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_BOTTOM, self.dsbFormatDocImgMarginsBottom.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LINKED, self.cbFormatDocImgMarginsLinked.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_ACTIVE, self.cbFormatDocImgHeader.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_ACTIVE, self.cbFormatDocImgFooter.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_ACTIVE, self.cbFormatDocImgFPageNotes.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_PREVIEW, self.cbFormatDocImgFPageNotesPreview.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_CONTENT, self.bcsteFormatDocImgHeader.toHtml())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_CONTENT, self.bcsteFormatDocImgFooter.toHtml())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_CONTENT, self.bcsteFormatDocImgFPageNotes.toHtml())


                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_ACTIVE, self.cbFormatDocImgPageBgColor.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_COL, self.pbFormatDocImgPageBgColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_ACTIVE, self.cbFormatDocImgPageBorder.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_COL, self.pbFormatDocImgPageBorderColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_WIDTH, self.dsbFormatDocImgPageBorderWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_RADIUS, self.dsbFormatDocImgPageBorderRadius.value())


                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_NBPERROW, self.sbFormatDocImgThumbsPerRow.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_OUTER, self.dsbFormatDocImgThumbsSpacingOuter.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_INNER, self.dsbFormatDocImgThumbsSpacingInner.value())
                #BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_TEXT, self.xxx.value())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_ACTIVE, self.cbFormatDocImgThumbsBg.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_COL, self.pbFormatDocImgThumbsBgColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_ACTIVE, self.cbFormatDocImgThumbsBorder.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_COL, self.pbFormatDocImgThumbsBorderColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_WIDTH, self.dsbFormatDocImgThumbsBorderWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_RADIUS, self.dsbFormatDocImgThumbsBorderRadius.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_IMGMOD, ['fit', 'crop'][self.cbxFormatDocImgThumbMode.currentIndex()])

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_POS, ['none', 'left', 'right', 'top', 'bottom'][self.cbxFormatDocImgTextPosition.currentIndex()])
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTNAME, self.fcbxFormatDocImgTextFontFamily.currentFont().family())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTSIZE, self.dsbFormatDocImgTextFontSize.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTCOL, self.pbFormatDocImgTextFontColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PREVIEW_MODE, self.cbxFormatDocImgPreviewMode.currentIndex())
            elif self.cbxFormat.currentIndex() == BCExportFormat.EXPORT_FMT_IMG_JPG:
                # -- IMG/JPG format --
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_RESOLUTION, self.cbxFormatDocImgPaperResolution.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_SIZE, self.cbxFormatDocImgPaperSize.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_UNIT, self.cbxFormatDocImgPaperUnit.currentData())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_ORIENTATION, self.cbxFormatDocImgPaperOrientation.currentIndex())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR_ACTIVE, self.cbFormatDocImgPaperColor.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR, self.pbFormatDocImgPaperColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LEFT, self.dsbFormatDocImgMarginsLeft.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_RIGHT, self.dsbFormatDocImgMarginsRight.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_TOP, self.dsbFormatDocImgMarginsTop.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_BOTTOM, self.dsbFormatDocImgMarginsBottom.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LINKED, self.cbFormatDocImgMarginsLinked.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_ACTIVE, self.cbFormatDocImgHeader.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_ACTIVE, self.cbFormatDocImgFooter.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_ACTIVE, self.cbFormatDocImgFPageNotes.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_PREVIEW, self.cbFormatDocImgFPageNotesPreview.isChecked())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_CONTENT, self.bcsteFormatDocImgHeader.toHtml())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_CONTENT, self.bcsteFormatDocImgFooter.toHtml())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_CONTENT, self.bcsteFormatDocImgFPageNotes.toHtml())


                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_ACTIVE, self.cbFormatDocImgPageBgColor.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_COL, self.pbFormatDocImgPageBgColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_ACTIVE, self.cbFormatDocImgPageBorder.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_COL, self.pbFormatDocImgPageBorderColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_WIDTH, self.dsbFormatDocImgPageBorderWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_RADIUS, self.dsbFormatDocImgPageBorderRadius.value())


                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_NBPERROW, self.sbFormatDocImgThumbsPerRow.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_OUTER, self.dsbFormatDocImgThumbsSpacingOuter.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_INNER, self.dsbFormatDocImgThumbsSpacingInner.value())
                #BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_TEXT, self.xxx.value())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_ACTIVE, self.cbFormatDocImgThumbsBg.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_COL, self.pbFormatDocImgThumbsBgColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_ACTIVE, self.cbFormatDocImgThumbsBorder.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_COL, self.pbFormatDocImgThumbsBorderColor.color().name(QColor.HexArgb))
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_WIDTH, self.dsbFormatDocImgThumbsBorderWidth.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_RADIUS, self.dsbFormatDocImgThumbsBorderRadius.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_IMGMOD, ['fit', 'crop'][self.cbxFormatDocImgThumbMode.currentIndex()])

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_POS, ['none', 'left', 'right', 'top', 'bottom'][self.cbxFormatDocImgTextPosition.currentIndex()])
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTNAME, self.fcbxFormatDocImgTextFontFamily.currentFont().family())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTSIZE, self.dsbFormatDocImgTextFontSize.value())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTCOL, self.pbFormatDocImgTextFontColor.color().name(QColor.HexArgb))

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PREVIEW_MODE, self.cbxFormatDocImgPreviewMode.currentIndex())

                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_HEADER_ACTIVE, self.cbFormatTextCSVHeader.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_ENCLOSED, self.cbFormatTextCSVEnclosedFields.isChecked())
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_SEPARATOR, self.cbxFormatTextCSVSeparator.currentIndex())

        def __savePageTarget():
            fileName = self.leTargetResultFile.text()
            if fileName != '' and (result:=re.match("(.*)(\..*)$", fileName)):
                fileName = f"{result.groups()[0]}.{{ext}}"
                BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FILENAME, fileName)

        __savePagePerimeter()
        __savePageFormat()
        __savePageTarget()

        BCSettings.set(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_SAVED, True)
        self.__uiController.saveSettings()

    def __newExportDefinition(self):
        """Reset export configuration to default settings"""
        if self.__isModified:
            if not WDialogBooleanInput.display(i18n(f"{self.__title}::{i18n('New export files list definition')}"), i18n("Current export files list definition has been modified and will be lost, continue?")):
                return False

        self.__loadDefaultPagePerimeter()
        self.__loadDefaultPageFormat()
        self.__loadDefaultPageTarget()
        self.__currentLoadedConfigurationFile=''
        self.__setModified(False)


    def __openFile(self, fileName, title):
        """Open & load export files list definition defined by `fileName`"""
        if self.__isModified:
            if not WDialogBooleanInput.display(title, i18n("Current export files list definition has been modified and will be lost, continue?")):
                return False

        try:
            with open(fileName, 'r') as fHandle:
                jsonAsStr=fHandle.read()
        except Exception as e:
            Debug.print("Can't open/read file {0}: {1}", fileName, f"{e}")
            return BCExportFilesDialogBox.IMPORT_FILE_CANT_READ

        try:
            jsonAsDict = json.loads(jsonAsStr, cls=JsonQObjectDecoder)
        except Exception as e:
            Debug.print("Can't parse file {0}: {1}", fileName, f"{e}")
            return BCExportFilesDialogBox.IMPORT_FILE_NOT_JSON

        if not "formatIdentifier" in jsonAsDict:
            Debug.print("Missing format identifier file {0}", fileName)
            return BCExportFilesDialogBox.IMPORT_FILE_MISSING_FORMAT_IDENTIFIER

        if jsonAsDict["formatIdentifier"]!="bulicommander-export-file-list-definition":
            Debug.print("Invalid format identifier file {0}", fileName)
            return BCExportFilesDialogBox.IMPORT_FILE_INVALID_FORMAT_IDENTIFIER

        self.__options=jsonAsDict

        self.__loadSettingsPagePerimeter()
        self.__loadSettingsPageFormat()
        self.__loadSettingsPageTarget()

        self.leTargetResultFile.setText(self.__options['exportFileName'])
        self.rbTargetResultClipboard.setChecked(self.__options['exportClipboard'])

        BCSettings.set(BCSettingsKey.SESSION_EXPORTFILESLIST_LASTFILE, fileName)
        self.__currentLoadedConfigurationFile=fileName
        self.__setModified(False)

    def __saveFile(self, fileName, description=''):
        """Save export files list definition to defined `fileName`"""
        toExport={
                'formatIdentifier': "bulicommander-export-file-list-definition",
                'contentDescription': description,
                'exportFormat': self.cbxFormat.currentIndex(),
                'exportFileName': self.leTargetResultFile.text(),
                'exportClipboard': self.rbTargetResultClipboard.isChecked(),
                'exportConfig': self.__generateConfig(True)
            }
        # do not save file list!
        toExport['exportConfig'].pop('files')

        returned=BCExportFilesDialogBox.EXPORT_OK
        try:
            with open(fileName, 'w') as fHandle:
                fHandle.write(json.dumps(toExport, indent=4, sort_keys=True, cls=JsonQObjectEncoder))
        except Exception as e:
            Debug.print("Can't save file {0}: {1}", fileName, f"{e}")
            returned=BCExportFilesDialogBox.EXPORT_CANT_SAVE

        BCSettings.set(BCSettingsKey.SESSION_EXPORTFILESLIST_LASTFILE, fileName)
        self.__currentLoadedConfigurationFile=fileName
        self.__setModified(False)
        self.__updateFileNameLabel()

        return returned

    def __updateFileNameLabel(self):
        """Update file name in status bar according to current tab"""
        modified=''
        if self.__isModified:
            modified=f" ({i18n('modified')})"

        if self.__currentLoadedConfigurationFile is None or self.__currentLoadedConfigurationFile=='':
            self.lblExportDefinitionFileName.setText(f"")
        else:
            self.lblExportDefinitionFileName.setText(f"{self.__currentLoadedConfigurationFile}{modified}")

    def __setModified(self, value):
        """Set if export file list definition has been modified"""
        if self.__isModified!=value:
            self.__isModified=value
            self.__updateFileNameLabel()

    def options(self):
        """Return current defined options"""
        return self.__options

    def openFile(self, fileName=None):
        """Open file designed by `fileName`

        If fileName is None, open dialog box with predefined last opened/saved file
        """
        if fileName is None:
            fileName=BCSettings.get(BCSettingsKey.SESSION_EXPORTFILESLIST_LASTFILE)

        if fileName is None:
            fileName=''

        title=i18n(f"{self.__title}::{i18n('Open export files list definition')}")
        extension=i18n("BuliCommander Export Files List (*.bcefl)")

        fileName, dummy = QFileDialog.getOpenFileName(self, title, fileName, extension)

        if fileName != '':
            fileName=os.path.normpath(fileName)
            if not os.path.isfile(fileName):
                openResult=BCExportFilesDialogBox.IMPORT_FILE_NOT_FOUND
            else:
                openResult=self.__openFile(fileName, title)

            if BCExportFilesDialogBox.IMPORT_OK:
                return True
            elif openResult==BCExportFilesDialogBox.IMPORT_FILE_NOT_FOUND:
                WDialogMessage.display(title, "<br>".join(
                    [i18n("<h1>Can't open file!</h1>"),
                     i18n("File not found!"),
                    ]))
            elif openResult==BCExportFilesDialogBox.IMPORT_FILE_CANT_READ:
                WDialogMessage.display(title, "<br>".join(
                    [i18n("<h1>Can't open file!</h1>"),
                     i18n("File can't be read!"),
                    ]))
            elif openResult==BCExportFilesDialogBox.IMPORT_FILE_NOT_JSON:
                WDialogMessage.display(title, "<br>".join(
                    [i18n("<h1>Can't open file!</h1>"),
                     i18n("Invalid file format!"),
                    ]))

        return False

    def saveFile(self, saveAs=False, fileName=None):
        """Save current search to designed file name"""
        if fileName is None and self.__currentLoadedConfigurationFile!='':
            # a file is currently opened
            fileName=self.__currentLoadedConfigurationFile
        else:
            fileName=BCSettings.get(BCSettingsKey.SESSION_EXPORTFILESLIST_LASTFILE)
            saveAs=True

        if fileName is None:
            fileName=''
            saveAs=True

        title=i18n(f"{self.__title}::{i18n('Save export files list definition')}")
        extension=i18n("BuliCommander Export Files List (*.bcefl)")

        if saveAs:
            fileName, dummy = QFileDialog.getSaveFileName(self, title, fileName, extension)

        if fileName != '':
            fileName=os.path.normpath(fileName)
            saveResult=self.__saveFile(fileName)

            if saveResult==BCExportFilesDialogBox.EXPORT_OK:
                return True
            elif saveResult==BCExportFilesDialogBox.EXPORT_CANT_SAVE:
                WDialogMessage.display(title, i18n("<h1>Can't save file!</h1>"))

        return False



    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCExportFilesDialogBox(title, uicontroller)
        return db.exec()

    @staticmethod
    def openAsExportConfig(title, uicontroller, options):
        """Open dialog box"""
        db = BCExportFilesDialogBox(title, uicontroller, options)
        if db.exec()==QDialog.Accepted:
            return db.options()
        else:
            return None
