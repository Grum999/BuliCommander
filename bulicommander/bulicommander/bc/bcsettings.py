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

from enum import Enum


import PyQt5.uic
from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal,
        QSettings,
        QStandardPaths
    )
from PyQt5.QtWidgets import (
        QDialog,
        QMessageBox
    )

from os.path import join, getsize
import json
import os
import re
import sys
import shutil

from .bcfile import (
        BCFile
    )

from .bcpathbar import BCPathBar
from .bcsystray import BCSysTray
from .bcutils import (
        bytesSizeToStr,
        checkKritaVersion,
        Debug
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# -----------------------------------------------------------------------------

class BCSettingsValues(object):
    FILE_DEFAULTACTION_OPEN =                               'open'
    FILE_DEFAULTACTION_OPEN_AND_CLOSE =                     'open and close'
    FILE_DEFAULTACTION_OPEN_AS_NEW =                        'open as new document'
    FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE =              'open as new document and close'

    FILE_UNIT_KB =                                          'auto'
    FILE_UNIT_KIB =                                         'autobin'

    HOME_DIR_SYS =                                          'system'
    HOME_DIR_UD =                                           'user defined'


class BCSettingsFmt(object):

    def __init__(self, settingType, values=None):
        if not isinstance(settingType, type):
            raise EInvalidType('Given `settingType` must be a type')

        self.__type = settingType
        self.__values = values

    def check(self, value, checkType=None):
        """Check if given value match setting format"""
        if checkType is None:
            checkType = self.__type

        if not isinstance(value, checkType):
            raise EInvalidType(f'Given `value` ({value}) is not from expected type ({checkType})')

        if not self.__values is None:
            if isinstance(value, list) or isinstance(value, tuple):
                # need to check all items
                if isinstance(self.__values, type):
                    # check if all items are of given type
                    for item in value:
                        self.check(item, self.__values)
                else:
                    # check items values
                    for item in value:
                        self.check(item)
            elif isinstance(self.__values, list) or isinstance(self.__values, tuple):
                if not value in self.__values:
                    raise EInvalidValue('Given `value` ({0}) is not in authorized perimeter ({1})'.format(value, self.__values))
            elif isinstance(self.__values, re.Pattern):
                if self.__values.match(value) is None:
                    raise EInvalidValue('Given `value` ({0}) is not in authorized perimeter'.format(value))


class BCSettingsKey(Enum):
    CONFIG_FILE_DEFAULTACTION_KRA =                          'config.file.defaultAction.kra'
    CONFIG_FILE_DEFAULTACTION_OTHER =                        'config.file.defaultAction.other'
    CONFIG_FILE_NEWFILENAME_KRA =                            'config.file.newFileName.kra'
    CONFIG_FILE_NEWFILENAME_OTHER =                          'config.file.newFileName.other'
    CONFIG_FILE_UNIT =                                       'config.file.unit'
    CONFIG_HOME_DIR_MODE =                                   'config.homeDir.mode'
    CONFIG_HOME_DIR_UD =                                     'config.homeDir.userDefined'
    CONFIG_HISTORY_MAXITEMS =                                'config.history.maximumItems'
    CONFIG_HISTORY_KEEPONEXIT =                              'config.history.keepOnExit'
    CONFIG_LASTDOC_MAXITEMS =                                'config.lastDocuments.maximumItems'
    CONFIG_NAVBAR_BUTTONS_HOME =                             'config.navbar.buttons.home'
    CONFIG_NAVBAR_BUTTONS_VIEWS =                            'config.navbar.buttons.views'
    CONFIG_NAVBAR_BUTTONS_BOOKMARKS =                        'config.navbar.buttons.bookmarks'
    CONFIG_NAVBAR_BUTTONS_HISTORY =                          'config.navbar.buttons.history'
    CONFIG_NAVBAR_BUTTONS_LASTDOCUMENTS =                    'config.navbar.buttons.lastDocuments'
    CONFIG_NAVBAR_BUTTONS_BACK =                             'config.navbar.buttons.back'
    CONFIG_NAVBAR_BUTTONS_UP =                               'config.navbar.buttons.up'
    CONFIG_NAVBAR_BUTTONS_QUICKFILTER =                      'config.navbar.buttons.quickFilter'
    CONFIG_OPEN_ATSTARTUP =                                  'config.open.atStartup'
    CONFIG_OPEN_OVERRIDEKRITA =                              'config.open.overrideKrita'
    CONFIG_SYSTRAY_MODE =                                    'config.systray.mode'

    CONFIG_EXPORTFILESLIST_GLB_SAVED =                       'config.export.filesList.global.saved'
    CONFIG_EXPORTFILESLIST_GLB_PROPERTIES =                  'config.export.filesList.global.properties'
    CONFIG_EXPORTFILESLIST_GLB_FILENAME =                    'config.export.filesList.global.fileName'
    CONFIG_EXPORTFILESLIST_GLB_FORMAT =                      'config.export.filesList.global.format'
    CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_ACTIVE =             'config.export.filesList.text.userDefinedLayout.active'
    CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_CONTENT =            'config.export.filesList.text.userDefinedLayout.content'
    CONFIG_EXPORTFILESLIST_TXT_HEADER_ACTIVE =               'config.export.filesList.text.header.active'
    CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE =               'config.export.filesList.text.borders.style'
    CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_ACTIVE =             'config.export.filesList.text.minimumWidth.active'
    CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_VALUE =              'config.export.filesList.text.minimumWidth.value'
    CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_ACTIVE =             'config.export.filesList.text.maximumWidth.active'
    CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_VALUE =              'config.export.filesList.text.maximumWidth.value'
    CONFIG_EXPORTFILESLIST_TXTCSV_HEADER_ACTIVE =            'config.export.filesList.textCsv.header.active'
    CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_ENCLOSED =          'config.export.filesList.textCsv.fields.enclosed'
    CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_SEPARATOR =         'config.export.filesList.textCsv.fields.separator'
    CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_ACTIVE =           'config.export.filesList.textMd.userDefinedLayout.active'
    CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_CONTENT =          'config.export.filesList.textMd.userDefinedLayout.content'
    CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_INCLUDED =           'config.export.filesList.textMd.thumbnails.included'
    CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_SIZE =               'config.export.filesList.textMd.thumbnails.size'

    CONFIG_EXPORTFILESLIST_DOCPDF_RESOLUTION =               'config.export.filesList.doc.pdf.resolution'
    CONFIG_EXPORTFILESLIST_DOCPDF_UNIT =                     'config.export.filesList.doc.pdf.unit'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_SIZE =               'config.export.filesList.doc.pdf.paper.size'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_ORIENTATION =        'config.export.filesList.doc.pdf.paper.orientation'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR_ACTIVE =       'config.export.filesList.doc.pdf.paper.color.active'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR =              'config.export.filesList.doc.pdf.paper.color.value'
    CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LEFT =             'config.export.filesList.doc.pdf.margins.left'
    CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_RIGHT =            'config.export.filesList.doc.pdf.margins.right'
    CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_TOP =              'config.export.filesList.doc.pdf.margins.top'
    CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_BOTTOM =           'config.export.filesList.doc.pdf.margins.bottom'
    CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LINKED =           'config.export.filesList.doc.pdf.margins.linked'
    CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_ACTIVE =            'config.export.filesList.doc.pdf.header.active'
    CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_CONTENT =           'config.export.filesList.doc.pdf.header.content'
    CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_ACTIVE =            'config.export.filesList.doc.pdf.footer.active'
    CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_CONTENT =           'config.export.filesList.doc.pdf.footer.content'
    CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_ACTIVE =          'config.export.filesList.doc.pdf.firstPageNotes.active'
    CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_CONTENT =         'config.export.filesList.doc.pdf.firstPageNotes.content'
    CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_PREVIEW =         'config.export.filesList.doc.pdf.firstPageNotes.preview'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_ACTIVE =       'config.export.filesList.doc.pdf.page.border.active'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_COL =          'config.export.filesList.doc.pdf.page.border.color'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_WIDTH =        'config.export.filesList.doc.pdf.page.border.width'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_RADIUS =       'config.export.filesList.doc.pdf.page.border.radius'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_ACTIVE =           'config.export.filesList.doc.pdf.page.background.active'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_COL =              'config.export.filesList.doc.pdf.page.background.color'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_NBPERROW =          'config.export.filesList.doc.pdf.thumbnails.layout.nbPerRow'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_OUTER =     'config.export.filesList.doc.pdf.thumbnails.layout.spacing.outer'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_INNER =     'config.export.filesList.doc.pdf.thumbnails.layout.spacing.inner'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_TEXT =      'config.export.filesList.doc.pdf.thumbnails.layout.spacing.text'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_POS =           'config.export.filesList.doc.pdf.thumbnails.text.position'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTNAME =       'config.export.filesList.doc.pdf.thumbnails.text.font.name'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTSIZE =       'config.export.filesList.doc.pdf.thumbnails.text.font.size'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTCOL =        'config.export.filesList.doc.pdf.thumbnails.text.font.color'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_ACTIVE =     'config.export.filesList.doc.pdf.thumbnails.border.active'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_COL =        'config.export.filesList.doc.pdf.thumbnails.border.color'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_WIDTH =      'config.export.filesList.doc.pdf.thumbnails.border.width'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_RADIUS =     'config.export.filesList.doc.pdf.thumbnails.border.radius'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_ACTIVE =         'config.export.filesList.doc.pdf.thumbnails.background.active'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_COL =            'config.export.filesList.doc.pdf.thumbnails.background.color'
    CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_IMGMOD =            'config.export.filesList.doc.pdf.thumbnails.image.displayMode'
    CONFIG_EXPORTFILESLIST_DOCPDF_PREVIEW_MODE =             'config.export.filesList.doc.pdf.preview.mode'

    CONFIG_EXPORTFILESLIST_IMGKRA_RESOLUTION =               'config.export.filesList.img.kra.resolution'
    CONFIG_EXPORTFILESLIST_IMGKRA_UNIT =                     'config.export.filesList.img.kra.unit'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_SIZE =               'config.export.filesList.img.kra.paper.size'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_ORIENTATION =        'config.export.filesList.img.kra.paper.orientation'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR_ACTIVE =       'config.export.filesList.img.kra.paper.color.active'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR =              'config.export.filesList.img.kra.paper.color.value'
    CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LEFT =             'config.export.filesList.img.kra.margins.left'
    CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_RIGHT =            'config.export.filesList.img.kra.margins.right'
    CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_TOP =              'config.export.filesList.img.kra.margins.top'
    CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_BOTTOM =           'config.export.filesList.img.kra.margins.bottom'
    CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LINKED =           'config.export.filesList.img.kra.margins.linked'
    CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_ACTIVE =            'config.export.filesList.img.kra.header.active'
    CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_CONTENT =           'config.export.filesList.img.kra.header.content'
    CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_ACTIVE =            'config.export.filesList.img.kra.footer.active'
    CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_CONTENT =           'config.export.filesList.img.kra.footer.content'
    CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_ACTIVE =          'config.export.filesList.img.kra.firstPageNotes.active'
    CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_CONTENT =         'config.export.filesList.img.kra.firstPageNotes.content'
    CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_PREVIEW =         'config.export.filesList.img.kra.firstPageNotes.preview'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_ACTIVE =       'config.export.filesList.img.kra.page.border.active'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_COL =          'config.export.filesList.img.kra.page.border.color'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_WIDTH =        'config.export.filesList.img.kra.page.border.width'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_RADIUS =       'config.export.filesList.img.kra.page.border.radius'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_ACTIVE =           'config.export.filesList.img.kra.page.background.active'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_COL =              'config.export.filesList.img.kra.page.background.color'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_NBPERROW =          'config.export.filesList.img.kra.thumbnails.layout.nbPerRow'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_OUTER =     'config.export.filesList.img.kra.thumbnails.layout.spacing.outer'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_INNER =     'config.export.filesList.img.kra.thumbnails.layout.spacing.inner'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_TEXT =      'config.export.filesList.img.kra.thumbnails.layout.spacing.text'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_POS =           'config.export.filesList.img.kra.thumbnails.text.position'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTNAME =       'config.export.filesList.img.kra.thumbnails.text.font.name'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTSIZE =       'config.export.filesList.img.kra.thumbnails.text.font.size'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTCOL =        'config.export.filesList.img.kra.thumbnails.text.font.color'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_ACTIVE =     'config.export.filesList.img.kra.thumbnails.border.active'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_COL =        'config.export.filesList.img.kra.thumbnails.border.color'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_WIDTH =      'config.export.filesList.img.kra.thumbnails.border.width'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_RADIUS =     'config.export.filesList.img.kra.thumbnails.border.radius'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_ACTIVE =         'config.export.filesList.img.kra.thumbnails.background.active'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_COL =            'config.export.filesList.img.kra.thumbnails.background.color'
    CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_IMGMOD =            'config.export.filesList.img.kra.thumbnails.image.displayMode'
    CONFIG_EXPORTFILESLIST_IMGKRA_OPT_OPENFILE =             'config.export.filesList.img.kra.options.openFileInKrita'
    CONFIG_EXPORTFILESLIST_IMGKRA_PREVIEW_MODE =             'config.export.filesList.img.kra.preview.mode'

    CONFIG_EXPORTFILESLIST_IMGPNG_RESOLUTION =               'config.export.filesList.img.png.resolution'
    CONFIG_EXPORTFILESLIST_IMGPNG_UNIT =                     'config.export.filesList.img.png.unit'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_SIZE =               'config.export.filesList.img.png.paper.size'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_ORIENTATION =        'config.export.filesList.img.png.paper.orientation'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR_ACTIVE =       'config.export.filesList.img.png.paper.color.active'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR =              'config.export.filesList.img.png.paper.color.value'
    CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LEFT =             'config.export.filesList.img.png.margins.left'
    CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_RIGHT =            'config.export.filesList.img.png.margins.right'
    CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_TOP =              'config.export.filesList.img.png.margins.top'
    CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_BOTTOM =           'config.export.filesList.img.png.margins.bottom'
    CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LINKED =           'config.export.filesList.img.png.margins.linked'
    CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_ACTIVE =            'config.export.filesList.img.png.header.active'
    CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_CONTENT =           'config.export.filesList.img.png.header.content'
    CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_ACTIVE =            'config.export.filesList.img.png.footer.active'
    CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_CONTENT =           'config.export.filesList.img.png.footer.content'
    CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_ACTIVE =          'config.export.filesList.img.png.firstPageNotes.active'
    CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_CONTENT =         'config.export.filesList.img.png.firstPageNotes.content'
    CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_PREVIEW =         'config.export.filesList.img.png.firstPageNotes.preview'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_ACTIVE =       'config.export.filesList.img.png.page.border.active'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_COL =          'config.export.filesList.img.png.page.border.color'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_WIDTH =        'config.export.filesList.img.png.page.border.width'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_RADIUS =       'config.export.filesList.img.png.page.border.radius'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_ACTIVE =           'config.export.filesList.img.png.page.background.active'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_COL =              'config.export.filesList.img.png.page.background.color'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_NBPERROW =          'config.export.filesList.img.png.thumbnails.layout.nbPerRow'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_OUTER =     'config.export.filesList.img.png.thumbnails.layout.spacing.outer'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_INNER =     'config.export.filesList.img.png.thumbnails.layout.spacing.inner'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_TEXT =      'config.export.filesList.img.png.thumbnails.layout.spacing.text'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_POS =           'config.export.filesList.img.png.thumbnails.text.position'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTNAME =       'config.export.filesList.img.png.thumbnails.text.font.name'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTSIZE =       'config.export.filesList.img.png.thumbnails.text.font.size'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTCOL =        'config.export.filesList.img.png.thumbnails.text.font.color'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_ACTIVE =     'config.export.filesList.img.png.thumbnails.border.active'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_COL =        'config.export.filesList.img.png.thumbnails.border.color'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_WIDTH =      'config.export.filesList.img.png.thumbnails.border.width'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_RADIUS =     'config.export.filesList.img.png.thumbnails.border.radius'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_ACTIVE =         'config.export.filesList.img.png.thumbnails.background.active'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_COL =            'config.export.filesList.img.png.thumbnails.background.color'
    CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_IMGMOD =            'config.export.filesList.img.png.thumbnails.image.displayMode'
    CONFIG_EXPORTFILESLIST_IMGPNG_OPT_OPENFILE =             'config.export.filesList.img.png.options.openFileInKrita'
    CONFIG_EXPORTFILESLIST_IMGPNG_PREVIEW_MODE =             'config.export.filesList.img.png.preview.mode'

    CONFIG_EXPORTFILESLIST_IMGJPG_RESOLUTION =               'config.export.filesList.img.jpg.resolution'
    CONFIG_EXPORTFILESLIST_IMGJPG_UNIT =                     'config.export.filesList.img.jpg.unit'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_SIZE =               'config.export.filesList.img.jpg.paper.size'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_ORIENTATION =        'config.export.filesList.img.jpg.paper.orientation'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR_ACTIVE =       'config.export.filesList.img.jpg.paper.color.active'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR =              'config.export.filesList.img.jpg.paper.color.value'
    CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LEFT =             'config.export.filesList.img.jpg.margins.left'
    CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_RIGHT =            'config.export.filesList.img.jpg.margins.right'
    CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_TOP =              'config.export.filesList.img.jpg.margins.top'
    CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_BOTTOM =           'config.export.filesList.img.jpg.margins.bottom'
    CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LINKED =           'config.export.filesList.img.jpg.margins.linked'
    CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_ACTIVE =            'config.export.filesList.img.jpg.header.active'
    CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_CONTENT =           'config.export.filesList.img.jpg.header.content'
    CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_ACTIVE =            'config.export.filesList.img.jpg.footer.active'
    CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_CONTENT =           'config.export.filesList.img.jpg.footer.content'
    CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_ACTIVE =          'config.export.filesList.img.jpg.firstPageNotes.active'
    CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_CONTENT =         'config.export.filesList.img.jpg.firstPageNotes.content'
    CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_PREVIEW =         'config.export.filesList.img.jpg.firstPageNotes.preview'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_ACTIVE =       'config.export.filesList.img.jpg.page.border.active'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_COL =          'config.export.filesList.img.jpg.page.border.color'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_WIDTH =        'config.export.filesList.img.jpg.page.border.width'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_RADIUS =       'config.export.filesList.img.jpg.page.border.radius'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_ACTIVE =           'config.export.filesList.img.jpg.page.background.active'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_COL =              'config.export.filesList.img.jpg.page.background.color'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_NBPERROW =          'config.export.filesList.img.jpg.thumbnails.layout.nbPerRow'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_OUTER =     'config.export.filesList.img.jpg.thumbnails.layout.spacing.outer'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_INNER =     'config.export.filesList.img.jpg.thumbnails.layout.spacing.inner'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_TEXT =      'config.export.filesList.img.jpg.thumbnails.layout.spacing.text'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_POS =           'config.export.filesList.img.jpg.thumbnails.text.position'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTNAME =       'config.export.filesList.img.jpg.thumbnails.text.font.name'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTSIZE =       'config.export.filesList.img.jpg.thumbnails.text.font.size'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTCOL =        'config.export.filesList.img.jpg.thumbnails.text.font.color'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_ACTIVE =     'config.export.filesList.img.jpg.thumbnails.border.active'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_COL =        'config.export.filesList.img.jpg.thumbnails.border.color'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_WIDTH =      'config.export.filesList.img.jpg.thumbnails.border.width'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_RADIUS =     'config.export.filesList.img.jpg.thumbnails.border.radius'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_ACTIVE =         'config.export.filesList.img.jpg.thumbnails.background.active'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_COL =            'config.export.filesList.img.jpg.thumbnails.background.color'
    CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_IMGMOD =            'config.export.filesList.img.jpg.thumbnails.image.displayMode'
    CONFIG_EXPORTFILESLIST_IMGJPG_OPT_OPENFILE =             'config.export.filesList.img.jpg.options.openFileInKrita'
    CONFIG_EXPORTFILESLIST_IMGJPG_PREVIEW_MODE =             'config.export.filesList.img.jpg.preview.mode'

    CONFIG_SESSION_SAVE =                                    'config.session.save'
    CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY =          'config.defaultSession.panels.view.filesManagedOnly'
    CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP =               'config.defaultSession.panels.view.filesBackup'
    CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN =               'config.defaultSession.panels.view.filesHidden'
    CONFIG_DSESSION_PANELS_VIEW_LAYOUT =                     'config.defaultSession.panels.view.layout'
    CONFIG_DSESSION_PANELS_VIEW_THUMBNAIL =                  'config.defaultSession.panels.view.thumbnail'
    CONFIG_DSESSION_PANELS_VIEW_ICONSIZE =                   'config.defaultSession.panels.view.iconSize'
    CONFIG_DSESSION_PANELS_VIEW_NFOROW =                     'config.defaultSession.panels.view.rowInformation'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_BORDER =                'config.defaultSession.information.clipboard.border'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_HEADER =                'config.defaultSession.information.clipboard.header'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH =              'config.defaultSession.information.clipboard.minWidth'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH =              'config.defaultSession.information.clipboard.maxWidth'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE =       'config.defaultSession.information.clipboard.minWidthActive'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE =       'config.defaultSession.information.clipboard.maxWidthActive'

    SESSION_INFO_TOCLIPBOARD_BORDER =                        'session.information.clipboard.border'
    SESSION_INFO_TOCLIPBOARD_HEADER =                        'session.information.clipboard.header'
    SESSION_INFO_TOCLIPBOARD_MINWIDTH =                      'session.information.clipboard.minWidth'
    SESSION_INFO_TOCLIPBOARD_MAXWIDTH =                      'session.information.clipboard.maxWidth'
    SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE =               'session.information.clipboard.minWidthActive'
    SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE =               'session.information.clipboard.maxWidthActive'

    SESSION_MAINWINDOW_SPLITTER_POSITION =                   'session.mainwindow.splitter.position'
    SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE =              'session.mainwindow.panel.secondaryVisible'
    SESSION_MAINWINDOW_PANEL_HIGHLIGHTED =                   'session.mainwindow.panel.highlighted'
    SESSION_MAINWINDOW_WINDOW_GEOMETRY =                     'session.mainwindow.window.geometry'
    SESSION_MAINWINDOW_WINDOW_MAXIMIZED =                    'session.mainwindow.window.maximized'

    SESSION_PANELS_VIEW_FILES_MANAGEDONLY =                  'session.panels.view.filesManagedOnly'
    SESSION_PANELS_VIEW_FILES_BACKUP =                       'session.panels.view.filesBackup'
    SESSION_PANELS_VIEW_FILES_HIDDEN =                       'session.panels.view.filesHidden'

    SESSION_PANEL_VIEW_LAYOUT =                              'session.panels.panel-{panelId}.view.layout'
    SESSION_PANEL_VIEW_CURRENTPATH =                         'session.panels.panel-{panelId}.view.currentPath'
    SESSION_PANEL_VIEW_FILTERVISIBLE =                       'session.panels.panel-{panelId}.view.filterVisible'
    SESSION_PANEL_VIEW_FILTERVALUE =                         'session.panels.panel-{panelId}.view.filterValue'
    SESSION_PANEL_VIEW_COLUMNSORT =                          'session.panels.panel-{panelId}.view.columnSort'
    SESSION_PANEL_VIEW_COLUMNORDER =                         'session.panels.panel-{panelId}.view.columnOrder'
    SESSION_PANEL_VIEW_COLUMNSIZE =                          'session.panels.panel-{panelId}.view.columnSize'
    SESSION_PANEL_VIEW_THUMBNAIL =                           'session.panels.panel-{panelId}.view.thumbnail'
    SESSION_PANEL_VIEW_ICONSIZE =                            'session.panels.panel-{panelId}.view.iconSize'
    SESSION_PANEL_SPLITTER_FILES_POSITION =                  'session.panels.panel-{panelId}.splitter.files.position'
    SESSION_PANEL_SPLITTER_PREVIEW_POSITION =                'session.panels.panel-{panelId}.splitter.preview.position'
    SESSION_PANEL_ACTIVETAB_MAIN =                           'session.panels.panel-{panelId}.activeTab.main'
    SESSION_PANEL_ACTIVETAB_FILES =                          'session.panels.panel-{panelId}.activeTab.files'
    SESSION_PANEL_ACTIVETAB_FILES_NFO =                      'session.panels.panel-{panelId}.activeTab.filesNfo'
    SESSION_PANEL_POSITIONTAB_MAIN =                         'session.panels.panel-{panelId}.positionTab.main'
    SESSION_PANEL_POSITIONTAB_FILES =                        'session.panels.panel-{panelId}.positionTab.files'
    SESSION_PANEL_PREVIEW_BACKGROUND =                       'session.panels.panel-{panelId}.preview.background'

    SESSION_HISTORY_ITEMS =                                  'session.history.items'
    SESSION_BOOKMARK_ITEMS =                                 'session.bookmark.items'
    SESSION_SAVEDVIEWS_ITEMS =                               'session.savedview.items'
    SESSION_LASTDOC_O_ITEMS =                                'session.lastDocuments.opened.items'
    SESSION_LASTDOC_S_ITEMS =                                'session.lastDocuments.saved.items'

    def id(self, **param):
        if isinstance(param, dict):
            return self.value.format(**param)
        else:
            return self.value


class BCSettings(object):
    """Manage all BuliCommander settings with open&save options

    Configuration is saved as JSON file
    """

    def __init__(self, pluginId=None, panelIds=[0, 1]):
        """Initialise settings"""
        if pluginId is None or pluginId == '':
            pluginId = 'bulicommander'

        self.__pluginCfgFile = os.path.join(QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation), f'krita-plugin-{pluginId}rc.json')
        self.__config = {}

        # define current rules for options
        self.__rules = {
            # values are tuples:
            # [0]       = default value
            # [1..n]    = values types & accepted values
            BCSettingsKey.CONFIG_FILE_DEFAULTACTION_KRA.id():                   (BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                            BCSettingsFmt(str, [BCSettingsValues.FILE_DEFAULTACTION_OPEN,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE])),
            BCSettingsKey.CONFIG_FILE_NEWFILENAME_KRA.id():                     ('<none>',                  BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_FILE_DEFAULTACTION_OTHER.id():                 (BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE,
                                                                                                            BCSettingsFmt(str, [BCSettingsValues.FILE_DEFAULTACTION_OPEN,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE])),
            BCSettingsKey.CONFIG_FILE_NEWFILENAME_OTHER.id():                   ('{file:name}.{file:ext}.kra',
                                                                                                            BCSettingsFmt(str)),

            BCSettingsKey.CONFIG_FILE_UNIT.id():                                (BCSettingsValues.FILE_UNIT_KIB,
                                                                                                            BCSettingsFmt(str, [BCSettingsValues.FILE_UNIT_KIB,
                                                                                                                                BCSettingsValues.FILE_UNIT_KB])),
            BCSettingsKey.CONFIG_HOME_DIR_MODE.id():                            (BCSettingsValues.HOME_DIR_SYS,
                                                                                                            BCSettingsFmt(str, [BCSettingsValues.HOME_DIR_SYS,
                                                                                                                                BCSettingsValues.HOME_DIR_UD])),
            BCSettingsKey.CONFIG_HOME_DIR_UD.id():                              ('',                        BCSettingsFmt(str)),

            BCSettingsKey.CONFIG_HISTORY_MAXITEMS.id():                         (25,                       BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_HISTORY_KEEPONEXIT.id():                       (True,                     BCSettingsFmt(bool)),

            BCSettingsKey.CONFIG_LASTDOC_MAXITEMS.id():                         (25,                       BCSettingsFmt(int)),

            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HOME.id():                      (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_VIEWS.id():                     (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BOOKMARKS.id():                 (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HISTORY.id():                   (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_LASTDOCUMENTS.id():             (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BACK.id():                      (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_UP.id():                        (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_QUICKFILTER.id():               (True,                     BCSettingsFmt(bool)),

            BCSettingsKey.CONFIG_SYSTRAY_MODE.id():                             (2,                        BCSettingsFmt(int, [0,1,2,3])),

            BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_SAVED.id():                (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_PROPERTIES.id():           ([],                       BCSettingsFmt(list, str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FILENAME.id():             ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FORMAT.id():               (0,                        BCSettingsFmt(int, [0,1,2,3,4,5,6])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_ACTIVE.id():      (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_CONTENT.id():     ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_HEADER_ACTIVE.id():        (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE.id():        (2,                        BCSettingsFmt(int, [0,1,2,3])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_ACTIVE.id():      (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_VALUE.id():       (80,                       BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_ACTIVE.id():      (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_VALUE.id():       (120,                      BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_HEADER_ACTIVE.id():     (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_ENCLOSED.id():   (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_SEPARATOR.id():  (0,                        BCSettingsFmt(int, [0,1,2,3])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_ACTIVE.id():    (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_CONTENT.id():   ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_INCLUDED.id():    (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_SIZE.id():        (0,                        BCSettingsFmt(int, [0,1,2,3])),

            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_RESOLUTION.id():        (300.0,                    BCSettingsFmt(float, [72.00,96.00,150.00,300.00,600.00,900.00,1200.00])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_UNIT.id():              ('mm',                     BCSettingsFmt(str, ['mm','cm','in'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_SIZE.id():        ('A4',                     BCSettingsFmt(str, ['A2','A3','A4','A5','A6','B2 (ISO)','B3 (ISO)','B4 (ISO)','B5 (ISO)','B6 (ISO)','B2 (JIS)','B3 (JIS)','B4 (JIS)','B5 (JIS)','B6 (JIS)','Letter (US)','Legal (US)', 'Square (A2)', 'Square (A3)', 'Square (A4)', 'Square (A5)', 'Square (A6)'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_ORIENTATION.id(): (0,                        BCSettingsFmt(int, [0,1])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR_ACTIVE.id():(False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR.id():       ('#ffffff',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LEFT.id():      (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_RIGHT.id():     (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_TOP.id():       (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_BOTTOM.id():    (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LINKED.id():    (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_ACTIVE.id():     (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_CONTENT.id():    ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_ACTIVE.id():     (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_CONTENT.id():    ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_ACTIVE.id():   (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_CONTENT.id():  ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_PREVIEW.id():  (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_ACTIVE.id():(False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_COL.id():   ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_WIDTH.id(): (1.0,                      BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_RADIUS.id():(0.0,                      BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_ACTIVE.id():    (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_COL.id():       ('#FF000000',              BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_NBPERROW.id():   (2,                        BCSettingsFmt(int, [1,2,3,4,5,6,7,8,9,10,11,12])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_OUTER.id():(5.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_INNER.id():(1.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_TEXT.id():(1.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_POS.id():    ('none',                   BCSettingsFmt(str, ['none','left','right','top','bottom'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTNAME.id():('DejaVu sans',            BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTSIZE.id():(10.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTCOL.id(): ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_ACTIVE.id():(False,                  BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_COL.id(): ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_WIDTH.id():(1.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_RADIUS.id():(0.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_ACTIVE.id():  (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_COL.id():     ('#FF000000',              BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_IMGMOD.id():     ('fit',                    BCSettingsFmt(str, ['fit', 'crop'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PREVIEW_MODE.id():      (0,                        BCSettingsFmt(int, [0,1])),

            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_RESOLUTION.id():        (300.0,                    BCSettingsFmt(float, [72.00,96.00,150.00,300.00,600.00,900.00,1200.00])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_UNIT.id():              ('mm',                     BCSettingsFmt(str, ['mm','cm','in', 'px'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_SIZE.id():        ('A4',                     BCSettingsFmt(str, ['A2','A3','A4','A5','A6','B2 (ISO)','B3 (ISO)','B4 (ISO)','B5 (ISO)','B6 (ISO)','B2 (JIS)','B3 (JIS)','B4 (JIS)','B5 (JIS)','B6 (JIS)','Letter (US)','Legal (US)', 'Square (A2)', 'Square (A3)', 'Square (A4)', 'Square (A5)', 'Square (A6)'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_ORIENTATION.id(): (0,                        BCSettingsFmt(int, [0,1])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR_ACTIVE.id():(False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR.id():       ('#FFFFFF',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LEFT.id():      (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_RIGHT.id():     (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_TOP.id():       (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_BOTTOM.id():    (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LINKED.id():    (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_ACTIVE.id():     (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_CONTENT.id():    ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_ACTIVE.id():     (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_CONTENT.id():    ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_ACTIVE.id():   (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_CONTENT.id():  ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_PREVIEW.id():  (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_ACTIVE.id():(False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_COL.id():   ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_WIDTH.id(): (1.0,                      BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_RADIUS.id():(0.0,                      BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_ACTIVE.id():    (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_COL.id():       ('#FF000000',              BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_NBPERROW.id():   (2,                        BCSettingsFmt(int, [1,2,3,4,5,6,7,8,9,10,11,12])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_OUTER.id():(5.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_INNER.id():(1.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_TEXT.id():(1.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_POS.id():    ('none',                   BCSettingsFmt(str, ['none','left','right','top','bottom'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTNAME.id():('DejaVu sans',            BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTSIZE.id():(10.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTCOL.id(): ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_ACTIVE.id():(False,                  BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_COL.id(): ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_WIDTH.id():(1.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_RADIUS.id():(0.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_ACTIVE.id():  (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_COL.id():     ('#FF000000',              BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_IMGMOD.id():     ('fit',                    BCSettingsFmt(str, ['fit', 'crop'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_OPT_OPENFILE.id():      (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PREVIEW_MODE.id():      (0,                        BCSettingsFmt(int, [0,1])),

            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_RESOLUTION.id():        (300.0,                    BCSettingsFmt(float, [72.00,96.00,150.00,300.00,600.00,900.00,1200.00])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_UNIT.id():              ('mm',                     BCSettingsFmt(str, ['mm','cm','in', 'px'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_SIZE.id():        ('A4',                     BCSettingsFmt(str, ['A2','A3','A4','A5','A6','B2 (ISO)','B3 (ISO)','B4 (ISO)','B5 (ISO)','B6 (ISO)','B2 (JIS)','B3 (JIS)','B4 (JIS)','B5 (JIS)','B6 (JIS)','Letter (US)','Legal (US)', 'Square (A2)', 'Square (A3)', 'Square (A4)', 'Square (A5)', 'Square (A6)'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_ORIENTATION.id(): (0,                        BCSettingsFmt(int, [0,1])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR_ACTIVE.id():(False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR.id():       ('#FFFFFF',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LEFT.id():      (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_RIGHT.id():     (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_TOP.id():       (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_BOTTOM.id():    (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LINKED.id():    (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_ACTIVE.id():     (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_CONTENT.id():    ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_ACTIVE.id():     (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_CONTENT.id():    ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_ACTIVE.id():   (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_CONTENT.id():  ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_PREVIEW.id():  (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_ACTIVE.id():(False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_COL.id():   ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_WIDTH.id(): (1.0,                      BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_RADIUS.id():(0.0,                      BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_ACTIVE.id():    (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_COL.id():       ('#FF000000',              BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_NBPERROW.id():   (2,                        BCSettingsFmt(int, [1,2,3,4,5,6,7,8,9,10,11,12])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_OUTER.id():(5.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_INNER.id():(1.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_TEXT.id():(1.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_POS.id():    ('none',                   BCSettingsFmt(str, ['none','left','right','top','bottom'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTNAME.id():('DejaVu sans',            BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTSIZE.id():(10.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTCOL.id(): ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_ACTIVE.id():(False,                  BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_COL.id(): ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_WIDTH.id():(1.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_RADIUS.id():(0.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_ACTIVE.id():  (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_COL.id():     ('#FF000000',              BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_IMGMOD.id():     ('fit',                    BCSettingsFmt(str, ['fit', 'crop'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_OPT_OPENFILE.id():      (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PREVIEW_MODE.id():      (0,                        BCSettingsFmt(int, [0,1])),

            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_RESOLUTION.id():        (300.0,                    BCSettingsFmt(float, [72.00,96.00,150.00,300.00,600.00,900.00,1200.00])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_UNIT.id():              ('mm',                     BCSettingsFmt(str, ['mm','cm','in', 'px'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_SIZE.id():        ('A4',                     BCSettingsFmt(str, ['A2','A3','A4','A5','A6','B2 (ISO)','B3 (ISO)','B4 (ISO)','B5 (ISO)','B6 (ISO)','B2 (JIS)','B3 (JIS)','B4 (JIS)','B5 (JIS)','B6 (JIS)','Letter (US)','Legal (US)', 'Square (A2)', 'Square (A3)', 'Square (A4)', 'Square (A5)', 'Square (A6)'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_ORIENTATION.id(): (0,                        BCSettingsFmt(int, [0,1])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR_ACTIVE.id():(False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR.id():       ('#FFFFFF',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LEFT.id():      (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_RIGHT.id():     (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_TOP.id():       (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_BOTTOM.id():    (20.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LINKED.id():    (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_ACTIVE.id():     (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_CONTENT.id():    ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_ACTIVE.id():     (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_CONTENT.id():    ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_ACTIVE.id():   (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_CONTENT.id():  ('',                       BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_PREVIEW.id():  (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_ACTIVE.id():(False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_COL.id():   ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_WIDTH.id(): (1.0,                      BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_RADIUS.id():(0.0,                      BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_ACTIVE.id():    (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_COL.id():       ('#FF000000',              BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_NBPERROW.id():   (2,                        BCSettingsFmt(int, [1,2,3,4,5,6,7,8,9,10,11,12])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_OUTER.id():(5.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_INNER.id():(1.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_TEXT.id():(1.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_POS.id():    ('none',                   BCSettingsFmt(str, ['none','left','right','top','bottom'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTNAME.id():('DejaVu sans',            BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTSIZE.id():(10.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTCOL.id(): ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_ACTIVE.id():(False,                  BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_COL.id(): ('#000000',                BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_WIDTH.id():(1.0,                     BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_RADIUS.id():(0.0,                    BCSettingsFmt(float)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_ACTIVE.id():  (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_COL.id():     ('#FF000000',              BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_IMGMOD.id():     ('fit',                    BCSettingsFmt(str, ['fit', 'crop'])),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_OPT_OPENFILE.id():      (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PREVIEW_MODE.id():      (0,                        BCSettingsFmt(int, [0,1])),

            BCSettingsKey.CONFIG_OPEN_ATSTARTUP.id():                           (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_OPEN_OVERRIDEKRITA.id():                       (False,                    BCSettingsFmt(bool)),

            BCSettingsKey.CONFIG_SESSION_SAVE.id():                             (True,                     BCSettingsFmt(bool)),

            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY.id():   (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP.id():        (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN.id():        (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_LAYOUT.id():              ('top',                    BCSettingsFmt(str, ['full','top','left','right','bottom'])),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_THUMBNAIL.id():           (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_ICONSIZE.id():            (0,                        BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8])),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_NFOROW.id():              (7,                        BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8,9])),

            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_BORDER.id():         (3,                        BCSettingsFmt(int, [0,1,2,3])),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_HEADER.id():         (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH.id():       (80,                       BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH.id():       (120,                      BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE.id():(True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE.id():(False,                    BCSettingsFmt(bool)),

            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_BORDER.id():                 (3,                        BCSettingsFmt(int, [0,1,2,3])),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_HEADER.id():                 (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH.id():               (80,                       BCSettingsFmt(int)),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH.id():               (120,                      BCSettingsFmt(int)),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE.id():        (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE.id():        (False,                    BCSettingsFmt(bool)),

            BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION.id():            ([1000, 1000],             BCSettingsFmt(int), BCSettingsFmt(int)),
            BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE.id():       (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED.id():            (0,                        BCSettingsFmt(int, [0, 1])),
            BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY.id():              ([-1,-1,-1,-1],            BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int)),
            BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED.id():             (False,                    BCSettingsFmt(bool)),


            BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY.id():           (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP.id():                (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN.id():                (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_HISTORY_ITEMS.id():                           ([],                       BCSettingsFmt(list, str)),
            BCSettingsKey.SESSION_BOOKMARK_ITEMS.id():                          ([],                       BCSettingsFmt(list)),
            BCSettingsKey.SESSION_SAVEDVIEWS_ITEMS.id():                        ([],                       BCSettingsFmt(list)),
            BCSettingsKey.SESSION_LASTDOC_O_ITEMS.id():                         ([],                       BCSettingsFmt(list)),
            BCSettingsKey.SESSION_LASTDOC_S_ITEMS.id():                         ([],                       BCSettingsFmt(list))
        }

        for panelId in panelIds:
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_LAYOUT.id(panelId=panelId)] =       ('top',                       BCSettingsFmt(str, ['full','top','left','right','bottom']))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_CURRENTPATH.id(panelId=panelId)] =  ('@home',                     BCSettingsFmt(str))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_FILTERVISIBLE.id(panelId=panelId)] =(True,                        BCSettingsFmt(bool))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_FILTERVALUE.id(panelId=panelId)] =  ('*',                         BCSettingsFmt(str))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_COLUMNSORT.id(panelId=panelId)] =   ([1,True],                    BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(bool))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_COLUMNORDER.id(panelId=panelId)] =  ([0,1,2,3,4,5,6,7,8],         BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_COLUMNSIZE.id(panelId=panelId)] =   ([0,0,0,0,0,0,0,0,0],         BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_ICONSIZE.id(panelId=panelId)] =     (0,                           BCSettingsFmt(int, [0, 1, 2, 3, 4, 5, 6, 7, 8]))

            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_THUMBNAIL.id(panelId=panelId)] =    (False,                       BCSettingsFmt(bool))

            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId)] =    ('files',                             BCSettingsFmt(str, ['files','documents','clipboard']))
            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId)] =   ('info',                              BCSettingsFmt(str, ['info','dirtree']))
            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId)]=('generic',                           BCSettingsFmt(str, ['generic','image','kra']))
            self.__rules[BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId)] =  (['files', 'documents', 'clipboard'], BCSettingsFmt(str, ['files','documents','clipboard']), BCSettingsFmt(str, ['files','documents','clipboard']), BCSettingsFmt(str, ['files','documents','clipboard']))
            self.__rules[BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId)] = (['info', 'dirtree'],                 BCSettingsFmt(str, ['info','dirtree']), BCSettingsFmt(str, ['info','dirtree']))
            self.__rules[BCSettingsKey.SESSION_PANEL_SPLITTER_FILES_POSITION.id(panelId=panelId)] = ([1000,1000],                   BCSettingsFmt(int), BCSettingsFmt(int))
            self.__rules[BCSettingsKey.SESSION_PANEL_SPLITTER_PREVIEW_POSITION.id(panelId=panelId)] = ([1000,1000],                 BCSettingsFmt(int), BCSettingsFmt(int))

            self.__rules[BCSettingsKey.SESSION_PANEL_PREVIEW_BACKGROUND.id(panelId=panelId)] =(4,                           BCSettingsFmt(int, [0, 1, 2, 3, 4]))

        self.setDefaultConfig()
        self.loadConfig()

    def __setValue(self, target, id, value):
        """From an id like 'a.b.c', set value in target dictionary"""
        keys = id.split('.', 1)

        if len(keys) == 1:
            target[keys[0]] = value
        else:
            if not keys[0] in target:
                target[keys[0]] = {}

            self.__setValue(target[keys[0]], keys[1], value)

    def __getValue(self, target, id):
        """From an id like 'a.b.c', get value in target dictionary"""
        keys = id.split('.', 1)

        if len(keys) == 1:
            return target[keys[0]]
        else:
            return self.__getValue(target[keys[0]], keys[1])

    def configurationFile(self):
        """Return the configuration file name"""
        return self.__pluginCfgFile

    def setDefaultConfig(self):
        """Reset default configuration"""
        self.__config = {}

        for rule in self.__rules:
            self.__setValue(self.__config, rule, self.__rules[rule][0])

    def loadConfig(self):
        """Load configuration from file

        If file doesn't exist return False
        Otherwise True
        """
        def setKeyValue(sourceKey, value):
            if isinstance(value, dict):
                for key in value:
                    setKeyValue(f'{sourceKey}.{key}', value[key])
            else:
                self.setOption(sourceKey, value)

        jsonAsDict = None

        if os.path.isfile(self.__pluginCfgFile):
            with open(self.__pluginCfgFile, 'r') as file:
                try:
                    jsonAsStr = file.read()
                except Exception as e:
                    Debug.print('[BCSettings.loadConfig] Unable to load file {0}: {1}', self.__pluginCfgFile, str(e))
                    return False

                try:
                    jsonAsDict = json.loads(jsonAsStr)
                except Exception as e:
                    Debug.print('[BCSettings.loadConfig] Unable to parse file {0}: {1}', self.__pluginCfgFile, str(e))
                    return False
        else:
            return False

        # parse all items, and set current config
        for key in jsonAsDict:
            setKeyValue(key, jsonAsDict[key])

        return True

    def saveConfig(self):
        """Save configuration to file

        If file can't be saved, return False
        Otherwise True
        """
        with open(self.__pluginCfgFile, 'w') as file:
            try:
                file.write(json.dumps(self.__config, indent=4, sort_keys=True))
            except Exception as e:
                Debug.print('[BCSettings.saveConfig] Unable to save file {0}: {1}', self.__pluginCfgFile, str(e))
                return False

        return True

    def setOption(self, id, value):
        """Set value for given option

        Given `id` must be valid (a BCSettingsKey)
        Given `value` format must be valid (accordiing to id, a control is made)
        """
        # check if id is valid
        if isinstance(id, BCSettingsKey):
            id = id.id()

        if not isinstance(id, str) or not id in self.__rules:
            #raise EInvalidValue(f'Given `id` is not valid: {id}')
            Debug.print('[BCSettings.setOption] Given id `{0}` is not valid', id)
            return

        # check if value is valid
        rules = self.__rules[id][1:]
        if len(rules) > 1:
            # value must be a list
            if not isinstance(value, list):
                #raise EInvalidType(f'Given `value` must be a list: {value}')
                Debug.print('[BCSettings.setOption] Given value for id `{1}` must be a list: `{0}`', value, id)
                return

            # number of item must match number of rules
            if len(rules) != len(value):
                Debug.print('[BCSettings.setOption] Given value for id `{1}` is not a valid list: `{0}`', value, id)
                return

            # check if each item match corresponding rule
            for index in range(len(value)):
                rules[index].check(value[index])
        else:
            rules[0].check(value)

        # value is valid, set it
        self.__setValue(self.__config, id, value)

    def option(self, id):
        """Return value for option"""
        # check if id is valid
        if isinstance(id, BCSettingsKey):
            id = id.id()

        if not isinstance(id, str) or not id in self.__rules:
            raise EInvalidValue(f'Given `id` is not valid: {id}')


        return self.__getValue(self.__config, id)

    def options(self):
        return self.__config


class BCSettingsDialogBox(QDialog):
    """User interface fo settings"""

    CATEGORY_GENERAL = 0
    CATEGORY_NAVIGATION = 1
    CATEGORY_IMAGES = 2
    CATEGORY_CACHE = 3

    def __init__(self, title, uicontroller, parent=None):
        super(BCSettingsDialogBox, self).__init__(parent)

        self.__title = title

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcsettings.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.setWindowTitle(self.__title)
        self.lvCategory.itemSelectionChanged.connect(self.__categoryChanged)

        self.__itemCatGeneral = QListWidgetItem(QIcon(":/images/tune"), "General")
        self.__itemCatGeneral.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_GENERAL)
        self.__itemCatNavigation = QListWidgetItem(QIcon(":/images/navigation"), "Navigation")
        self.__itemCatNavigation.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_NAVIGATION)
        self.__itemCatImageFiles = QListWidgetItem(QIcon(":/images/large_view"), "Image files")
        self.__itemCatImageFiles.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_IMAGES)
        self.__itemCatCachedImages = QListWidgetItem(QIcon(":/images/cached"), "Cached images")
        self.__itemCatCachedImages.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_CACHE)

        self.__uiController = uicontroller

        self.__replaceOpenDbAlertUser = True

        self.pbCCIClearCache.clicked.connect(self.__clearCache)

        self.bbOkCancel.accepted.connect(self.__applySettings)

        self.__initialise()


    def __initialise(self):
        """Initialise interface"""
        def updateBtn():
            if self.__uiController.history().length()>0:
                self.pbCNHistoryClear.setEnabled(True)
                self.pbCNHistoryClear.setToolTip(i18n(f'Clear current navigation history ({self.__uiController.history().length()} places in history)'))
            else:
                self.pbCNHistoryClear.setEnabled(False)
                self.pbCNHistoryClear.setToolTip(i18n(f'Clear current navigation history (no places in history)'))

            nbTotalDoc = len(set((self.__uiController.lastDocumentsOpened().list() + self.__uiController.lastDocumentsSaved().list())))
            if nbTotalDoc>0:
                self.pbCNLastDocumentsClear.setEnabled(True)
                self.pbCNLastDocumentsClear.setToolTip(i18n(f'Clear list of last opened/saved documents ({nbTotalDoc} documents in list)'))
            else:
                self.pbCNLastDocumentsClear.setEnabled(False)
                self.pbCNLastDocumentsClear.setToolTip(i18n(f'Clear list of last opened/saved documents (no document in list)'))

            if len(Krita.instance().recentDocuments())>0:
                self.pbCNLastDocumentsReset.setEnabled(True)
                self.pbCNLastDocumentsReset.setToolTip(i18n(f'Reset list of last opened/saved documents from Krita\'s internal list ({len(Krita.instance().recentDocuments())} documents in list)'))
            else:
                self.pbCNLastDocumentsReset.setEnabled(False)
                self.pbCNLastDocumentsReset.setToolTip(i18n(f'Reset list of last opened/saved documents from Krita\'s internal list (no document in list)'))

        @pyqtSlot('QString')
        def setHomeDirSys(action):
            self.bcpbCNUserDefined.setEnabled(False)
        @pyqtSlot('QString')
        def setHomeDirUD(action):
            self.bcpbCNUserDefined.setEnabled(True)
        @pyqtSlot('QString')
        def historyClear(action):
            if self.__uiController.commandGoHistoryClearUI():
                self.pbCNHistoryClear.setEnabled(False)
                updateBtn()
        @pyqtSlot('QString')
        def lastDocumentsClear(action):
            if self.__uiController.commandGoLastDocsClearUI():
                self.pbCNLastDocumentsClear.setEnabled(False)
                updateBtn()
        @pyqtSlot('QString')
        def lastDocumentsReset(action):
            if self.__uiController.commandGoLastDocsResetUI():
                updateBtn()

        self.lvCategory.addItem(self.__itemCatGeneral)
        self.lvCategory.addItem(self.__itemCatNavigation)
        self.lvCategory.addItem(self.__itemCatImageFiles)
        self.lvCategory.addItem(self.__itemCatCachedImages)
        self.__setCategory(BCSettingsDialogBox.CATEGORY_GENERAL)

        # --- NAV Category -----------------------------------------------------
        self.bcpbCNUserDefined.setPath(self.__uiController.settings().option(BCSettingsKey.CONFIG_HOME_DIR_UD.id()))
        self.bcpbCNUserDefined.setOptions(BCPathBar.OPTION_SHOW_NONE)

        self.cbCNNavBarBtnHome.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HOME.id()))
        self.cbCNNavBarBtnViews.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_VIEWS.id()))
        self.cbCNNavBarBtnBookmarks.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BOOKMARKS.id()))
        self.cbCNNavBarBtnHistory.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HISTORY.id()))
        self.cbCNNavBarBtnLastDocuments.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_LASTDOCUMENTS.id()))
        self.cbCNNavBarBtnGoBack.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BACK.id()))
        self.cbCNNavBarBtnGoUp.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_UP.id()))
        self.cbCNNavBarBtnQuickFilter.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_QUICKFILTER.id()))

        if self.__uiController.settings().option(BCSettingsKey.CONFIG_HOME_DIR_MODE.id()) == BCSettingsValues.HOME_DIR_SYS:
            self.rbCNHomeDirSys.setChecked(True)
            self.bcpbCNUserDefined.setEnabled(False)
        else:
            self.rbCNHomeDirUD.setChecked(True)
            self.bcpbCNUserDefined.setEnabled(True)

        self.rbCNHomeDirSys.clicked.connect(setHomeDirSys)
        self.rbCNHomeDirUD.clicked.connect(setHomeDirUD)

        self.hsCNHistoryMax.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_HISTORY_MAXITEMS.id()))
        self.cbCNHistoryKeepWhenQuit.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_HISTORY_KEEPONEXIT.id()))

        self.hsCNLastDocsMax.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_LASTDOC_MAXITEMS.id()))

        self.pbCNHistoryClear.clicked.connect(historyClear)
        self.pbCNLastDocumentsClear.clicked.connect(lastDocumentsClear)
        self.pbCNLastDocumentsReset.clicked.connect(lastDocumentsReset)
        updateBtn()

        # --- GEN Category -----------------------------------------------------
        self.cbCGLaunchOpenBC.setEnabled(checkKritaVersion(5,0,0))
        self.cbCGLaunchOpenBC.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_OPEN_ATSTARTUP.id()))

        # not yet implemented...
        self.cbCGLaunchReplaceOpenDb.setEnabled(checkKritaVersion(5,0,0))
        self.cbCGLaunchReplaceOpenDb.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_OPEN_OVERRIDEKRITA.id()))
        self.cbCGLaunchReplaceOpenDb.toggled.connect(self.__replaceOpenDbAlert)

        if self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_UNIT.id()) == BCSettingsValues.FILE_UNIT_KIB:
            self.rbCGFileUnitBinary.setChecked(True)
        else:
            self.rbCGFileUnitDecimal.setChecked(True)

        value = self.__uiController.settings().option(BCSettingsKey.CONFIG_SYSTRAY_MODE.id())
        if value == BCSysTray.SYSTRAY_MODE_ALWAYS:
            self.rbCGSysTrayAlways.setChecked(True)
        elif value == BCSysTray.SYSTRAY_MODE_WHENACTIVE:
            self.rbCGSysTrayWhenActive.setChecked(True)
        elif value == BCSysTray.SYSTRAY_MODE_NEVER:
            self.rbCGSysTrayNever.setChecked(True)
        elif value == BCSysTray.SYSTRAY_MODE_FORNOTIFICATION:
            self.rbCGSysTrayNotification.setChecked(True)

        # --- Image Category -----------------------------------------------------
        value = self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_KRA.id())
        if value == BCSettingsValues.FILE_DEFAULTACTION_OPEN:
            self.rbCIFKraOpenDoc.setChecked(True)
            self.cbCIFKraOptCloseBC.setChecked(False)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE:
            self.rbCIFKraOpenDoc.setChecked(True)
            self.cbCIFKraOptCloseBC.setChecked(True)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW:
            self.rbCIFKraCreateDoc.setChecked(True)
            self.cbCIFKraOptCloseBC.setChecked(False)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE:
            self.rbCIFKraCreateDoc.setChecked(True)
            self.cbCIFKraOptCloseBC.setChecked(True)

        self.cbxCIFKraOptCreDocName.addItems([
                '<None>',
                '{file:name}-{counter:####}.kra',
                '{file:name}_{date}_{time}.kra',
                i18n('{file:name}-Copy {counter:####}.kra'),
                i18n('{file:name}-Copy {date}_{time}.kra')
            ])
        self.cbxCIFKraOptCreDocName.setCurrentText(self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_NEWFILENAME_KRA.id()))

        value = self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_OTHER.id())
        if value == BCSettingsValues.FILE_DEFAULTACTION_OPEN:
            self.rbCIFOthOpenDoc.setChecked(True)
            self.cbCIFOthOptCloseBC.setChecked(False)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE:
            self.rbCIFOthOpenDoc.setChecked(True)
            self.cbCIFOthOptCloseBC.setChecked(True)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW:
            self.rbCIFOthCreateDoc.setChecked(True)
            self.cbCIFOthOptCloseBC.setChecked(False)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE:
            self.rbCIFOthCreateDoc.setChecked(True)
            self.cbCIFOthOptCloseBC.setChecked(True)

        self.cbxCIFOthOptCreDocName.addItems([
                '<None>',
                '{file:name}.{file:ext}.kra',
                '{file:name}({file:ext}).kra',
                '{file:name}.kra',
                '{file:name}_{date}_{time}.kra',
                i18n('{file:name}-Copy {counter:####}.kra'),
                i18n('{file:name}-Copy {date}_{time}.kra')
            ])
        self.cbxCIFOthOptCreDocName.setCurrentText(self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_NEWFILENAME_OTHER.id()))


    def __applySettings(self):
        """Apply current settings"""

        # --- NAV Category -----------------------------------------------------
        self.__uiController.commandSettingsHomeDirUserDefined(self.bcpbCNUserDefined.path())
        if self.rbCNHomeDirSys.isChecked():
            self.__uiController.commandSettingsHomeDirMode(BCSettingsValues.HOME_DIR_SYS)
        else:
            self.__uiController.commandSettingsHomeDirMode(BCSettingsValues.HOME_DIR_UD)

        self.__uiController.commandSettingsNavBarBtnHome(self.cbCNNavBarBtnHome.isChecked())
        self.__uiController.commandSettingsNavBarBtnViews(self.cbCNNavBarBtnViews.isChecked())
        self.__uiController.commandSettingsNavBarBtnBookmarks(self.cbCNNavBarBtnBookmarks.isChecked())
        self.__uiController.commandSettingsNavBarBtnHistory(self.cbCNNavBarBtnHistory.isChecked())
        self.__uiController.commandSettingsNavBarBtnLastDocuments(self.cbCNNavBarBtnLastDocuments.isChecked())
        self.__uiController.commandSettingsNavBarBtnGoBack(self.cbCNNavBarBtnGoBack.isChecked())
        self.__uiController.commandSettingsNavBarBtnGoUp(self.cbCNNavBarBtnGoUp.isChecked())
        self.__uiController.commandSettingsNavBarBtnQuickFilter(self.cbCNNavBarBtnQuickFilter.isChecked())

        self.__uiController.commandSettingsHistoryMaxSize(self.hsCNHistoryMax.value())
        self.__uiController.commandSettingsHistoryKeepOnExit(self.cbCNHistoryKeepWhenQuit.isChecked())

        self.__uiController.commandSettingsLastDocsMaxSize(self.hsCNLastDocsMax.value())

        # --- GEN Category -----------------------------------------------------
        self.__uiController.commandSettingsOpenAtStartup(self.cbCGLaunchOpenBC.isChecked())
        self.__uiController.commandSettingsOpenOverrideKrita(self.cbCGLaunchReplaceOpenDb.isChecked())

        if self.rbCGFileUnitBinary.isChecked():
            self.__uiController.commandSettingsFileUnit(BCSettingsValues.FILE_UNIT_KIB)
        else:
            self.__uiController.commandSettingsFileUnit(BCSettingsValues.FILE_UNIT_KB)

        if self.rbCGSysTrayAlways.isChecked():
            self.__uiController.commandSettingsSysTrayMode(BCSysTray.SYSTRAY_MODE_ALWAYS)
        elif self.rbCGSysTrayWhenActive.isChecked():
            self.__uiController.commandSettingsSysTrayMode(BCSysTray.SYSTRAY_MODE_WHENACTIVE)
        elif self.rbCGSysTrayNever.isChecked():
            self.__uiController.commandSettingsSysTrayMode(BCSysTray.SYSTRAY_MODE_NEVER)
        elif self.rbCGSysTrayNotification.isChecked():
            self.__uiController.commandSettingsSysTrayMode(BCSysTray.SYSTRAY_MODE_FORNOTIFICATION)

        # --- Image Category -----------------------------------------------------
        if self.rbCIFKraOpenDoc.isChecked():
            if self.cbCIFKraOptCloseBC.isChecked():
                self.__uiController.commandSettingsFileDefaultActionKra(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE)
            else:
                self.__uiController.commandSettingsFileDefaultActionKra(BCSettingsValues.FILE_DEFAULTACTION_OPEN)
        elif self.rbCIFKraCreateDoc.isChecked():
            if self.cbCIFKraOptCloseBC.isChecked():
                self.__uiController.commandSettingsFileDefaultActionKra(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE)
            else:
                self.__uiController.commandSettingsFileDefaultActionKra(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW)

        if self.rbCIFOthOpenDoc.isChecked():
            if self.cbCIFOthOptCloseBC.isChecked():
                self.__uiController.commandSettingsFileDefaultActionOther(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE)
            else:
                self.__uiController.commandSettingsFileDefaultActionOther(BCSettingsValues.FILE_DEFAULTACTION_OPEN)
        elif self.rbCIFOthCreateDoc.isChecked():
            if self.cbCIFOthOptCloseBC.isChecked():
                self.__uiController.commandSettingsFileDefaultActionOther(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE)
            else:
                self.__uiController.commandSettingsFileDefaultActionOther(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW)

        self.__uiController.commandSettingsFileNewFileNameKra(self.cbxCIFKraOptCreDocName.currentText())
        self.__uiController.commandSettingsFileNewFileNameOther(self.cbxCIFOthOptCreDocName.currentText())


    def __replaceOpenDbAlert(self, checked):
        """Tick has been changed for checkbox cbCGLaunchReplaceOpenDb<"Overrides Krita 'Open' function">

        Alert user about impact
        """
        if not self.__replaceOpenDbAlertUser:
            # user have already been alerted, then do not display alert again
            return

        self.__replaceOpenDbAlertUser = False

        if checked:
            # User will ask to replace native dialog box
            QMessageBox.warning(
                    self,
                    i18n(f"{self.__title}::Override Krita's native ""Open file"" dialog"),
                    i18n(f"Once option is applied, Krita's native <i>Open file</i> dialog will be replaced by <i>Buli Commander</><br><br>"
                         f"If later you want restore original <i>Open file</i> dialog, keep in mind that at this moment you'll need to restart Krita"
                        )
                )
        else:
            # User want to restore native dialog box
            QMessageBox.warning(
                    self,
                    i18n(f"{self.__title}::Restore Krita's native ""Open file"" dialog"),
                    i18n(f"Please keep in mind that original <i>Open file</i> dialog will be restored only on next Krita's startup"
                        )
                )


    def __categoryChanged(self):
        """Set page according to category"""
        self.swCatPages.setCurrentIndex(self.lvCategory.currentItem().data(Qt.UserRole))

        if self.lvCategory.currentItem().data(Qt.UserRole) == BCSettingsDialogBox.CATEGORY_CACHE:
            # calculate cache nb files+size
            self.__calculateCacheSize()


    def __setCategory(self, value):
        """Set category setting

        Select icon, switch to panel
        """
        self.lvCategory.setCurrentRow(value)


    def __calculateCacheSize(self):
        """Calculate cache size"""
        nbFiles = 0
        sizeFiles = 0
        for root, dirs, files in os.walk(BCFile.thumbnailCacheDirectory()):
            sizeFiles+=sum(getsize(join(root, name)) for name in files)
            nbFiles+=len(files)

        if self.rbCGFileUnitBinary.isChecked():
            self.__uiController.commandSettingsFileUnit(BCSettingsValues.FILE_UNIT_KIB)
            self.lblCCINbFileAndSize.setText(f'{nbFiles} files, {bytesSizeToStr(sizeFiles, BCSettingsValues.FILE_UNIT_KIB)}')
        else:
            self.__uiController.commandSettingsFileUnit(BCSettingsValues.FILE_UNIT_KB)
            self.lblCCINbFileAndSize.setText(f'{nbFiles} files, {bytesSizeToStr(sizeFiles, BCSettingsValues.FILE_UNIT_KB)}')

        self.pbCCIClearCache.setEnabled(sizeFiles>0)


    def __clearCache(self):
        """Clear cache after user confirmation"""

        if QMessageBox.question(self, i18n(f"{self.__title}::Clear Cache"), i18n(f"Current cache content will be cleared ({self.lblCCINbFileAndSize.text()})\n\nDo you confirm action?"), QMessageBox.Yes, QMessageBox.No) == QMessageBox.Yes:
            shutil.rmtree(BCFile.thumbnailCacheDirectory(), ignore_errors=True)
            self.__calculateCacheSize()


    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCSettingsDialogBox(title, uicontroller)
        return db.exec()

