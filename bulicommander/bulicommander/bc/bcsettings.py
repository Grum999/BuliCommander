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
        QDialog
    )

from os.path import join, getsize
import json
import os
import re
import sys
import shutil

from .bcfile import (
        BCFile,
        BCFileCache
    )

from .bcwpathbar import BCWPathBar
from .bcsystray import BCSysTray
from bulicommander.pktk.modules.utils import (
        checkKritaVersion,
        Debug
    )
from bulicommander.pktk.modules.imgutils import buildIcon
from bulicommander.pktk.modules.strutils import bytesSizeToStr
from bulicommander.pktk.modules.settings import (
                        Settings,
                        SettingsFmt,
                        SettingsKey,
                        SettingsRule
                    )
from bulicommander.pktk.widgets.wiodialog import (
                        WDialogMessage,
                        WDialogBooleanInput
                    )
from bulicommander.pktk.pktk import (
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

    CLIPBOARD_MODE_ALWAYS =                                 'always'
    CLIPBOARD_MODE_ACTIVE =                                 'active'
    CLIPBOARD_MODE_MANUAL =                                 'manual'
    CLIPBOARD_ACTION_NLAYER =                               'layer'
    CLIPBOARD_ACTION_NDOCUMENT =                            'document'


class BCSettingsKey(SettingsKey):
    CONFIG_GLB_FILE_UNIT =                                   'config.global.file.unit'
    CONFIG_GLB_OPEN_ATSTARTUP =                              'config.global.open.atStartup'
    CONFIG_GLB_OPEN_OVERRIDEKRITA =                          'config.global.open.overrideKrita'
    CONFIG_GLB_SYSTRAY_MODE =                                'config.global.systray.mode'

    CONFIG_FILES_DEFAULTACTION_KRA =                         'config.files.defaultAction.kra'
    CONFIG_FILES_DEFAULTACTION_OTHER =                       'config.files.defaultAction.other'
    CONFIG_FILES_NEWFILENAME_KRA =                           'config.files.newFileName.kra'
    CONFIG_FILES_NEWFILENAME_OTHER =                         'config.files.newFileName.other'
    CONFIG_FILES_HOME_DIR_MODE =                             'config.files.homeDir.mode'
    CONFIG_FILES_HOME_DIR_UD =                               'config.files.homeDir.userDefined'
    CONFIG_FILES_HISTORY_MAXITEMS =                          'config.files.history.maximumItems'
    CONFIG_FILES_HISTORY_KEEPONEXIT =                        'config.files.history.keepOnExit'
    CONFIG_FILES_LASTDOC_MAXITEMS =                          'config.files.lastDocuments.maximumItems'
    CONFIG_FILES_NAVBAR_BUTTONS_HOME =                       'config.files.navbar.buttons.home'
    CONFIG_FILES_NAVBAR_BUTTONS_VIEWS =                      'config.files.navbar.buttons.views'
    CONFIG_FILES_NAVBAR_BUTTONS_BOOKMARKS =                  'config.files.navbar.buttons.bookmarks'
    CONFIG_FILES_NAVBAR_BUTTONS_HISTORY =                    'config.files.navbar.buttons.history'
    CONFIG_FILES_NAVBAR_BUTTONS_LASTDOCUMENTS =              'config.files.navbar.buttons.lastDocuments'
    CONFIG_FILES_NAVBAR_BUTTONS_BACK =                       'config.files.navbar.buttons.back'
    CONFIG_FILES_NAVBAR_BUTTONS_UP =                         'config.files.navbar.buttons.up'
    CONFIG_FILES_NAVBAR_BUTTONS_QUICKFILTER =                'config.files.navbar.buttons.quickFilter'

    CONFIG_CLIPBOARD_CACHE_MODE_GENERAL =                    'config.clipboard.cache.mode.general'
    CONFIG_CLIPBOARD_CACHE_MODE_SYSTRAY =                    'config.clipboard.cache.mode.systray'
    CONFIG_CLIPBOARD_CACHE_MAXISZE =                         'config.clipboard.cache.maxSize'
    CONFIG_CLIPBOARD_CACHE_PERSISTENT =                      'config.clipboard.cache.persistent'
    CONFIG_CLIPBOARD_URL_AUTOLOAD =                          'config.clipboard.url.autoLoad'
    CONFIG_CLIPBOARD_URL_PARSE_TEXTHTML =                    'config.clipboard.url.parseTextHtml'
    CONFIG_CLIPBOARD_PASTE_MODE_ASNEWDOC =                   'config.clipboard.paste.mode.asNewDocument'
    CONFIG_CLIPBOARD_DEFAULT_ACTION =                        'config.clipboard.defaultAction'

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

    CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_RESOLUTION =         'config.export.filesList.doc.pdf.paper.resolution'
    CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_UNIT =               'config.export.filesList.doc.pdf.paper.unit'
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

    CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_RESOLUTION =         'config.export.filesList.img.kra.paper.resolution'
    CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_UNIT =               'config.export.filesList.img.kra.paper.unit'
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

    CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_RESOLUTION =         'config.export.filesList.img.png.paper.resolution'
    CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_UNIT =               'config.export.filesList.img.png.paper.unit'
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

    CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_RESOLUTION =         'config.export.filesList.img.jpg.paper.resolution'
    CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_UNIT =               'config.export.filesList.img.jpg.paper.unit'
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

    CONFIG_CONVERTFILES_GLB_SAVED =                          'config.convert.global.saved'
    CONFIG_CONVERTFILES_GLB_FORMAT =                         'config.convert.global.format'
    CONFIG_CONVERTFILES_GLB_TARGET_MODE =                    'config.convert.global.target.mode'
    CONFIG_CONVERTFILES_GLB_TARGET_FILEPATTERN =             'config.convert.global.target.filePattern'
    CONFIG_CONVERTFILES_IMGPNG_SAVE_COMPRESSION =            'config.convert.img.png.compression'
    CONFIG_CONVERTFILES_IMGPNG_SAVE_INDEXED =                'config.convert.img.png.indexed'
    CONFIG_CONVERTFILES_IMGPNG_SAVE_INTERLACED =             'config.convert.img.png.interlaced'
    CONFIG_CONVERTFILES_IMGPNG_SAVE_SAVEICCPROFILE =         'config.convert.img.png.saveIccProfile'
    CONFIG_CONVERTFILES_IMGPNG_SAVE_FORCESRGB =              'config.convert.img.png.forceSRGB'
    CONFIG_CONVERTFILES_IMGPNG_SAVE_ALPHA =                  'config.convert.img.png.alpha'
    CONFIG_CONVERTFILES_IMGPNG_SAVE_BGCOLOR =                'config.convert.img.png.transparencyFillcolor'
    CONFIG_CONVERTFILES_IMGJPG_SAVE_QUALITY =                'config.convert.img.jpg.quality'
    CONFIG_CONVERTFILES_IMGJPG_SAVE_SMOOTHING =              'config.convert.img.jpg.smoothing'
    CONFIG_CONVERTFILES_IMGJPG_SAVE_SUBSAMPLING =            'config.convert.img.jpg.subsampling'
    CONFIG_CONVERTFILES_IMGJPG_SAVE_PROGRESSIVE =            'config.convert.img.jpg.progressive'
    CONFIG_CONVERTFILES_IMGJPG_SAVE_OPTIMIZE =               'config.convert.img.jpg.optimize'
    CONFIG_CONVERTFILES_IMGJPG_SAVE_SAVEICCPROFILE =         'config.convert.img.jpg.saveProfile'
    CONFIG_CONVERTFILES_IMGJPG_SAVE_BGCOLOR =                'config.convert.img.jpg.transparencyFillcolor'

    CONFIG_SESSION_SAVE =                                    'config.session.save'
    CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY =          'config.defaultSession.panels.view.files.managedOnly'
    CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP =               'config.defaultSession.panels.view.files.backup'
    CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN =               'config.defaultSession.panels.view.files.hidden'
    CONFIG_DSESSION_PANELS_VIEW_FILES_LAYOUT =               'config.defaultSession.panels.view.files.layout'
    CONFIG_DSESSION_PANELS_VIEW_FILES_THUMBNAIL =            'config.defaultSession.panels.view.files.thumbnail'
    CONFIG_DSESSION_PANELS_VIEW_FILES_ICONSIZE =             'config.defaultSession.panels.view.files.iconSize'
    CONFIG_DSESSION_PANELS_VIEW_FILES_NFOROW =               'config.defaultSession.panels.view.files.rowInformation'
    CONFIG_DSESSION_PANELS_VIEW_CLIPBOARD_ICONSIZE =         'config.defaultSession.panels.view.clipboard.iconSize'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_BORDER =                'config.defaultSession.information.clipboard.border'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_HEADER =                'config.defaultSession.information.clipboard.header'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH =              'config.defaultSession.information.clipboard.minWidth'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH =              'config.defaultSession.information.clipboard.maxWidth'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE =       'config.defaultSession.information.clipboard.minWidthActive'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE =       'config.defaultSession.information.clipboard.maxWidthActive'

    CONFIG_SEARCHFILES_PREDEFINED_FILEPATH =                 'config.searchFiles.predefined.filePath'
    CONFIG_SEARCHFILES_PREDEFINED_FILENAME =                 'config.searchFiles.predefined.fileName'
    CONFIG_SEARCHFILES_PREDEFINED_FILESIZE =                 'config.searchFiles.predefined.fileSize'
    CONFIG_SEARCHFILES_PREDEFINED_FILEDATE =                 'config.searchFiles.predefined.fileDate'
    CONFIG_SEARCHFILES_PREDEFINED_IMGFORMAT =                'config.searchFiles.predefined.imageFormat'
    CONFIG_SEARCHFILES_PREDEFINED_IMGWIDTH =                 'config.searchFiles.predefined.imageWidth'
    CONFIG_SEARCHFILES_PREDEFINED_IMGHEIGHT =                'config.searchFiles.predefined.imageHeight'
    CONFIG_SEARCHFILES_PREDEFINED_IMGRATIO =                 'config.searchFiles.predefined.imageRatio'
    CONFIG_SEARCHFILES_PREDEFINED_IMGPIXELS =                'config.searchFiles.predefined.imagePixels'

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

    SESSION_SEARCHWINDOW_SPLITTER_POSITION =                 'session.searchwindow.splitter.position'
    SESSION_SEARCHWINDOW_TAB_ACTIVE =                        'session.searchwindow.tab.active'
    SESSION_SEARCHWINDOW_WINDOW_GEOMETRY =                   'session.searchwindow.window.geometry'
    SESSION_SEARCHWINDOW_WINDOW_MAXIMIZED =                  'session.searchwindow.window.maximized'
    SESSION_SEARCHWINDOW_LASTFILE_BASIC =                    'session.searchwindow.lastFile.basic'
    SESSION_SEARCHWINDOW_LASTFILE_ADVANCED =                 'session.searchwindow.lastFile.advanced'

    SESSION_PANELS_VIEW_FILES_MANAGEDONLY =                  'session.panels.view.files.managedOnly'
    SESSION_PANELS_VIEW_FILES_BACKUP =                       'session.panels.view.files.backup'
    SESSION_PANELS_VIEW_FILES_HIDDEN =                       'session.panels.view.files.hidden'

    SESSION_PANEL_VIEW_FILES_LAYOUT =                        'session.panels.panel-{panelId}.view.files.layout'
    SESSION_PANEL_VIEW_FILES_CURRENTPATH =                   'session.panels.panel-{panelId}.view.files.currentPath'
    SESSION_PANEL_VIEW_FILES_FILTERVISIBLE =                 'session.panels.panel-{panelId}.view.files.filterVisible'
    SESSION_PANEL_VIEW_FILES_FILTERVALUE =                   'session.panels.panel-{panelId}.view.files.filterValue'
    SESSION_PANEL_VIEW_FILES_COLUMNSORT =                    'session.panels.panel-{panelId}.view.files.columnSort'
    SESSION_PANEL_VIEW_FILES_COLUMNORDER =                   'session.panels.panel-{panelId}.view.files.columnOrder'
    SESSION_PANEL_VIEW_FILES_COLUMNSIZE =                    'session.panels.panel-{panelId}.view.files.columnSize'
    SESSION_PANEL_VIEW_FILES_THUMBNAIL =                     'session.panels.panel-{panelId}.view.files.thumbnail'
    SESSION_PANEL_VIEW_FILES_ICONSIZE =                      'session.panels.panel-{panelId}.view.files.iconSize'
    SESSION_PANEL_VIEW_CLIPBOARD_LAYOUT =                    'session.panels.panel-{panelId}.view.clipboard.layout'
    SESSION_PANEL_VIEW_CLIPBOARD_COLUMNSORT =                'session.panels.panel-{panelId}.view.clipboard.columnSort'
    SESSION_PANEL_VIEW_CLIPBOARD_COLUMNORDER =               'session.panels.panel-{panelId}.view.clipboard.columnOrder'
    SESSION_PANEL_VIEW_CLIPBOARD_COLUMNSIZE =                'session.panels.panel-{panelId}.view.clipboard.columnSize'
    SESSION_PANEL_VIEW_CLIPBOARD_ICONSIZE =                  'session.panels.panel-{panelId}.view.clipboard.iconSize'
    SESSION_PANEL_SPLITTER_CLIPBOARD_POSITION =              'session.panels.panel-{panelId}.splitter.clipboard.position'
    SESSION_PANEL_SPLITTER_FILES_POSITION =                  'session.panels.panel-{panelId}.splitter.files.position'
    SESSION_PANEL_SPLITTER_PREVIEW_POSITION =                'session.panels.panel-{panelId}.splitter.preview.position'
    SESSION_PANEL_ACTIVETAB_MAIN =                           'session.panels.panel-{panelId}.activeTab.main'
    SESSION_PANEL_ACTIVETAB_FILES =                          'session.panels.panel-{panelId}.activeTab.files'
    SESSION_PANEL_ACTIVETAB_FILES_NFO =                      'session.panels.panel-{panelId}.activeTab.filesNfo'
    SESSION_PANEL_POSITIONTAB_MAIN =                         'session.panels.panel-{panelId}.positionTab.main'
    SESSION_PANEL_POSITIONTAB_FILES =                        'session.panels.panel-{panelId}.positionTab.files'
    SESSION_PANEL_PREVIEW_BACKGROUND =                       'session.panels.panel-{panelId}.preview.background'

    SESSION_FILES_HISTORY_ITEMS =                            'session.files.history.items'
    SESSION_FILES_BOOKMARK_ITEMS =                           'session.files.bookmark.items'
    SESSION_FILES_SAVEDVIEWS_ITEMS =                         'session.files.savedview.items'
    SESSION_FILES_LASTDOC_O_ITEMS =                          'session.files.lastDocuments.opened.items'
    SESSION_FILES_LASTDOC_S_ITEMS =                          'session.files.lastDocuments.saved.items'


class BCSettings(Settings):
    """Manage all BuliCommander settings with open&save options

    Configuration is saved as JSON file
    """

    def __init__(self, pluginId=None, panelIds=[0, 1]):
        """Initialise settings"""
        if pluginId is None or pluginId == '':
            pluginId = 'bulicommander'

        rules = [
            SettingsRule(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_KRA,                      BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                                        SettingsFmt(str, [BCSettingsValues.FILE_DEFAULTACTION_OPEN,
                                                                                                                                          BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                                                          BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW,
                                                                                                                                          BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE])),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NEWFILENAME_KRA,                        '<none>',                   SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_OTHER,                    BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE,
                                                                                                                        SettingsFmt(str, [BCSettingsValues.FILE_DEFAULTACTION_OPEN,
                                                                                                                                          BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                                                          BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW,
                                                                                                                                          BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE])),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NEWFILENAME_OTHER,                      '{file:name}.{file:ext}.kra',
                                                                                                                        SettingsFmt(str)),

            SettingsRule(BCSettingsKey.CONFIG_GLB_FILE_UNIT,                                BCSettingsValues.FILE_UNIT_KIB,
                                                                                                                        SettingsFmt(str, [BCSettingsValues.FILE_UNIT_KIB,
                                                                                                                                          BCSettingsValues.FILE_UNIT_KB])),
            SettingsRule(BCSettingsKey.CONFIG_FILES_HOME_DIR_MODE,                          BCSettingsValues.HOME_DIR_SYS,
                                                                                                                        SettingsFmt(str, [BCSettingsValues.HOME_DIR_SYS,
                                                                                                                                          BCSettingsValues.HOME_DIR_UD])),
            SettingsRule(BCSettingsKey.CONFIG_FILES_HOME_DIR_UD,                            '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_HISTORY_MAXITEMS,                       25,                         SettingsFmt(int)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_HISTORY_KEEPONEXIT,                     True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_LASTDOC_MAXITEMS,                       25,                         SettingsFmt(int)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_HOME,                    True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_VIEWS,                   True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_BOOKMARKS,               True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_HISTORY,                 True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_LASTDOCUMENTS,           True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_BACK,                    True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_UP,                      True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_QUICKFILTER,             True,                       SettingsFmt(bool)),

            SettingsRule(BCSettingsKey.CONFIG_GLB_SYSTRAY_MODE,                             2,                          SettingsFmt(int, [0,1,2,3])),

            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_SAVED,                    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_PROPERTIES,               [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FILENAME,                 '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_GLB_FORMAT,                   0,                          SettingsFmt(int, [0,1,2,3,4,5,6])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_ACTIVE,          True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_UDLAYOUT_CONTENT,         '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_HEADER_ACTIVE,            True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_BORDERS_STYLE,            2,                          SettingsFmt(int, [0,1,2,3])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_ACTIVE,          True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MINWIDTH_VALUE,           80,                         SettingsFmt(int)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_ACTIVE,          False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXT_MAXWIDTH_VALUE,           120,                        SettingsFmt(int)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_HEADER_ACTIVE,         True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_ENCLOSED,       False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTCSV_FIELDS_SEPARATOR,      0,                          SettingsFmt(int, [0,1,2,3])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_ACTIVE,        True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_UDLAYOUT_CONTENT,       '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_INCLUDED,        True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_TXTMD_THUMBS_SIZE,            0,                          SettingsFmt(int, [0,1,2,3])),

            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_RESOLUTION,      300.0,                      SettingsFmt(float, [72.00,96.00,150.00,300.00,600.00,900.00,1200.00])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_UNIT,            'mm',                       SettingsFmt(str, ['mm','cm','in'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_SIZE,            'A4',                       SettingsFmt(str, ['A2','A3','A4','A5','A6','B2 (ISO)','B3 (ISO)','B4 (ISO)','B5 (ISO)','B6 (ISO)','B2 (JIS)','B3 (JIS)','B4 (JIS)','B5 (JIS)','B6 (JIS)','Letter (US)','Legal (US)', 'Square (A2)', 'Square (A3)', 'Square (A4)', 'Square (A5)', 'Square (A6)'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_ORIENTATION,     0,                          SettingsFmt(int, [0,1])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR_ACTIVE,    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAPER_COLOR,           '#ffffff',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LEFT,          20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_RIGHT,         20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_TOP,           20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_BOTTOM,        20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_MARGINS_LINKED,        False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_ACTIVE,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_HEADER_CONTENT,        '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_ACTIVE,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FOOTER_CONTENT,        '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_ACTIVE,       False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_CONTENT,      '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_FPGNOTES_PREVIEW,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_ACTIVE,    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_COL,       '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_WIDTH,     1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BORDER_RADIUS,    0.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_ACTIVE,        False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PAGE_BG_COL,           '#FF000000',                SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_NBPERROW,       2,                          SettingsFmt(int, [1,2,3,4,5,6,7,8,9,10,11,12])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_OUTER,  5.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_INNER,  1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_SPACING_TEXT,   1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_POS,        'none',                     SettingsFmt(str, ['none','left','right','top','bottom'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTNAME,    'DejaVu sans',              SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTSIZE,    10.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_TXT_FNTCOL,     '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_ACTIVE,  False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_COL,     '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_WIDTH,   1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BORDER_RADIUS,  0.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_ACTIVE,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_BG_COL,         '#FF000000',                SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_THUMBS_IMGMOD,         'fit',                      SettingsFmt(str, ['fit', 'crop'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_DOCPDF_PREVIEW_MODE,          0,                          SettingsFmt(int, [0,1])),

            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_RESOLUTION,      300.0,                      SettingsFmt(float, [72.00,96.00,150.00,300.00,600.00,900.00,1200.00])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_UNIT,            'mm',                       SettingsFmt(str, ['mm','cm','in', 'px'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_SIZE,            'A4',                       SettingsFmt(str, ['A2','A3','A4','A5','A6','B2 (ISO)','B3 (ISO)','B4 (ISO)','B5 (ISO)','B6 (ISO)','B2 (JIS)','B3 (JIS)','B4 (JIS)','B5 (JIS)','B6 (JIS)','Letter (US)','Legal (US)', 'Square (A2)', 'Square (A3)', 'Square (A4)', 'Square (A5)', 'Square (A6)'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_ORIENTATION,     0,                          SettingsFmt(int, [0,1])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR_ACTIVE,    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAPER_COLOR,           '#FFFFFF',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LEFT,          20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_RIGHT,         20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_TOP,           20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_BOTTOM,        20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_MARGINS_LINKED,        False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_ACTIVE,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_HEADER_CONTENT,        '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_ACTIVE,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FOOTER_CONTENT,        '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_ACTIVE,       False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_CONTENT,      '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_FPGNOTES_PREVIEW,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_ACTIVE,    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_COL,       '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_WIDTH,     1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BORDER_RADIUS,    0.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_ACTIVE,        False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PAGE_BG_COL,           '#FF000000',                SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_NBPERROW,       2,                          SettingsFmt(int, [1,2,3,4,5,6,7,8,9,10,11,12])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_OUTER,  5.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_INNER,  1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_SPACING_TEXT,   1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_POS,        'none',                     SettingsFmt(str, ['none','left','right','top','bottom'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTNAME,    'DejaVu sans',              SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTSIZE,    10.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_TXT_FNTCOL,     '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_ACTIVE,  False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_COL,     '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_WIDTH,   1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BORDER_RADIUS,  0.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_ACTIVE,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_BG_COL,         '#FF000000',                SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_THUMBS_IMGMOD,         'fit',                      SettingsFmt(str, ['fit', 'crop'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_OPT_OPENFILE,          True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGKRA_PREVIEW_MODE,          0,                          SettingsFmt(int, [0,1])),

            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_RESOLUTION,      300.0,                      SettingsFmt(float, [72.00,96.00,150.00,300.00,600.00,900.00,1200.00])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_UNIT,            'mm',                       SettingsFmt(str, ['mm','cm','in', 'px'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_SIZE,            'A4',                       SettingsFmt(str, ['A2','A3','A4','A5','A6','B2 (ISO)','B3 (ISO)','B4 (ISO)','B5 (ISO)','B6 (ISO)','B2 (JIS)','B3 (JIS)','B4 (JIS)','B5 (JIS)','B6 (JIS)','Letter (US)','Legal (US)', 'Square (A2)', 'Square (A3)', 'Square (A4)', 'Square (A5)', 'Square (A6)'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_ORIENTATION,     0,                          SettingsFmt(int, [0,1])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR_ACTIVE,    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAPER_COLOR,           '#FFFFFF',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LEFT,          20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_RIGHT,         20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_TOP,           20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_BOTTOM,        20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_MARGINS_LINKED,        False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_ACTIVE,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_HEADER_CONTENT,        '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_ACTIVE,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FOOTER_CONTENT,        '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_ACTIVE,       False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_CONTENT,      '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_FPGNOTES_PREVIEW,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_ACTIVE,    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_COL,       '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_WIDTH,     1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BORDER_RADIUS,    0.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_ACTIVE,        False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PAGE_BG_COL,           '#FF000000',                SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_NBPERROW,       2,                          SettingsFmt(int, [1,2,3,4,5,6,7,8,9,10,11,12])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_OUTER,  5.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_INNER,  1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_SPACING_TEXT,   1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_POS,        'none',                     SettingsFmt(str, ['none','left','right','top','bottom'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTNAME,    'DejaVu sans',              SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTSIZE,    10.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_TXT_FNTCOL,     '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_ACTIVE,  False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_COL,     '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_WIDTH,   1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BORDER_RADIUS,  0.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_ACTIVE,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_BG_COL,         '#FF000000',                SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_THUMBS_IMGMOD,         'fit',                      SettingsFmt(str, ['fit', 'crop'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_OPT_OPENFILE,          False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGJPG_PREVIEW_MODE,          0,                          SettingsFmt(int, [0,1])),

            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_RESOLUTION,      300.0,                      SettingsFmt(float, [72.00,96.00,150.00,300.00,600.00,900.00,1200.00])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_UNIT,            'mm',                       SettingsFmt(str, ['mm','cm','in', 'px'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_SIZE,            'A4',                       SettingsFmt(str, ['A2','A3','A4','A5','A6','B2 (ISO)','B3 (ISO)','B4 (ISO)','B5 (ISO)','B6 (ISO)','B2 (JIS)','B3 (JIS)','B4 (JIS)','B5 (JIS)','B6 (JIS)','Letter (US)','Legal (US)', 'Square (A2)', 'Square (A3)', 'Square (A4)', 'Square (A5)', 'Square (A6)'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_ORIENTATION,     0,                          SettingsFmt(int, [0,1])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR_ACTIVE,    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAPER_COLOR,           '#FFFFFF',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LEFT,          20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_RIGHT,         20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_TOP,           20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_BOTTOM,        20.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_MARGINS_LINKED,        False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_ACTIVE,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_HEADER_CONTENT,        '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_ACTIVE,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FOOTER_CONTENT,        '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_ACTIVE,       False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_CONTENT,      '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_FPGNOTES_PREVIEW,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_ACTIVE,    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_COL,       '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_WIDTH,     1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BORDER_RADIUS,    0.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_ACTIVE,        False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PAGE_BG_COL,           '#FF000000',                SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_NBPERROW,       2,                          SettingsFmt(int, [1,2,3,4,5,6,7,8,9,10,11,12])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_OUTER,  5.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_INNER,  1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_SPACING_TEXT,   1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_POS,        'none',                     SettingsFmt(str, ['none','left','right','top','bottom'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTNAME,    'DejaVu sans',              SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTSIZE,    10.0,                       SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_TXT_FNTCOL,     '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_ACTIVE,  False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_COL,     '#000000',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_WIDTH,   1.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BORDER_RADIUS,  0.0,                        SettingsFmt(float)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_ACTIVE,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_BG_COL,         '#FF000000',                SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_THUMBS_IMGMOD,         'fit',                      SettingsFmt(str, ['fit', 'crop'])),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_OPT_OPENFILE,          False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_EXPORTFILESLIST_IMGPNG_PREVIEW_MODE,          0,                          SettingsFmt(int, [0,1])),

            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_GLB_SAVED,                       False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_GLB_FORMAT,                      'kra',                      SettingsFmt(str, ['kra','png','jpeg'])),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_GLB_TARGET_MODE,                 'sdir',                     SettingsFmt(str, ['sdir', 'ddir'])),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_GLB_TARGET_FILEPATTERN,          '{file:baseName}.{targetExtension}',
                                                                                                                        SettingsFmt(str)),

            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_COMPRESSION,         6,                          SettingsFmt(int, [0,1,2,3,4,5,6,7,8,9])),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_INDEXED,             False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_INTERLACED,          False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_SAVEICCPROFILE,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_FORCESRGB,           False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_ALPHA,               True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGPNG_SAVE_BGCOLOR,             '#FFFFFF',                  SettingsFmt(str)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_QUALITY,             85,                         SettingsFmt(int, list(range(0, 101)))),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SMOOTHING,           15,                         SettingsFmt(int, list(range(0, 101)))),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SUBSAMPLING,         '4:2:0',                    SettingsFmt(str, ['4:2:0','4:2:2','4:4:0','4:4:4'])),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_PROGRESSIVE,         True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_OPTIMIZE,            True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_SAVEICCPROFILE,      False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CONVERTFILES_IMGJPG_SAVE_BGCOLOR,             '#FFFFFF',                  SettingsFmt(str)),

            SettingsRule(BCSettingsKey.CONFIG_GLB_OPEN_ATSTARTUP,                           False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_GLB_OPEN_OVERRIDEKRITA,                       False,                      SettingsFmt(bool)),

            SettingsRule(BCSettingsKey.CONFIG_SESSION_SAVE,                                 True,                       SettingsFmt(bool)),

            SettingsRule(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY,       True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP,            False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN,            False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_LAYOUT,            'top',                      SettingsFmt(str, ['full','top','left','right','bottom'])),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_THUMBNAIL,         False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_ICONSIZE,          1,                          SettingsFmt(int, [0,1,2,3,4,5,6,7,8])),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_NFOROW,            7,                          SettingsFmt(int, [0,1,2,3,4,5,6,7,8,9])),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_CLIPBOARD_ICONSIZE,      1,                          SettingsFmt(int, [0,1,2,3,4,5,6,7,8])),

            SettingsRule(BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_BORDER,             3,                          SettingsFmt(int, [0,1,2,3])),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_HEADER,             True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH,           80,                         SettingsFmt(int)),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH,           120,                        SettingsFmt(int)),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE,    True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE,    False,                      SettingsFmt(bool)),

            SettingsRule(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MODE_GENERAL,                 BCSettingsValues.CLIPBOARD_MODE_ALWAYS,
                                                                                                                        SettingsFmt(str, [BCSettingsValues.CLIPBOARD_MODE_ALWAYS, BCSettingsValues.CLIPBOARD_MODE_ACTIVE, BCSettingsValues.CLIPBOARD_MODE_MANUAL])),
            SettingsRule(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MODE_SYSTRAY,                 True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MAXISZE,                      1024000000,                 SettingsFmt(int)),
            SettingsRule(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_PERSISTENT,                   False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CLIPBOARD_URL_AUTOLOAD,                       True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CLIPBOARD_URL_PARSE_TEXTHTML,                 True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CLIPBOARD_PASTE_MODE_ASNEWDOC,                False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.CONFIG_CLIPBOARD_DEFAULT_ACTION,                     BCSettingsValues.CLIPBOARD_ACTION_NLAYER,
                                                                                                                        SettingsFmt(str, [BCSettingsValues.CLIPBOARD_ACTION_NLAYER,BCSettingsValues.CLIPBOARD_ACTION_NDOCUMENT])),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_FILEPATH,              [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_FILENAME,              [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_FILESIZE,              [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_FILEDATE,              [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGFORMAT,             [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGWIDTH,              [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGHEIGHT,             [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGRATIO,              [f"{i18n('Portrait')}//<//f:1.0",
                                                                                             f"{i18n('Landscape')}//>//f:1.0",
                                                                                             f"{i18n('Square')}//=//f:1.0"],
                                                                                                                        SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGPIXELS,             [f"{i18n('Small')}//<//f:1.0",
                                                                                             f"{i18n('Medium')}//between//f:1.0//f:8.3",
                                                                                             f"{i18n('Large')}//>//f:8.3"],
                                                                                                                        SettingsFmt(list, str)),

            SettingsRule(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_BORDER,                     3,                          SettingsFmt(int, [0,1,2,3])),
            SettingsRule(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_HEADER,                     True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH,                   80,                         SettingsFmt(int)),
            SettingsRule(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH,                   120,                        SettingsFmt(int)),
            SettingsRule(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE,            True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE,            False,                      SettingsFmt(bool)),

            SettingsRule(BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION,                [1000, 1000],               SettingsFmt(int), SettingsFmt(int)),
            SettingsRule(BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE,           True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED,                0,                          SettingsFmt(int, [0, 1])),
            SettingsRule(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY,                  [-1,-1,-1,-1],              SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int)),
            SettingsRule(BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED,                 False,                      SettingsFmt(bool)),


            SettingsRule(BCSettingsKey.SESSION_SEARCHWINDOW_SPLITTER_POSITION,              [800, 200]  ,               SettingsFmt(int), SettingsFmt(int)),
            SettingsRule(BCSettingsKey.SESSION_SEARCHWINDOW_TAB_ACTIVE,                     'basic',                    SettingsFmt(str, ['basic','advanced'])),
            SettingsRule(BCSettingsKey.SESSION_SEARCHWINDOW_WINDOW_GEOMETRY,                [-1,-1,-1,-1],              SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int)),
            SettingsRule(BCSettingsKey.SESSION_SEARCHWINDOW_WINDOW_MAXIMIZED,               False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_BASIC,                 '',                         SettingsFmt(str)),
            SettingsRule(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_ADVANCED,              '',                         SettingsFmt(str)),


            SettingsRule(BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY,               True,                       SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP,                    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN,                    False,                      SettingsFmt(bool)),
            SettingsRule(BCSettingsKey.SESSION_FILES_HISTORY_ITEMS,                         [],                         SettingsFmt(list, str)),
            SettingsRule(BCSettingsKey.SESSION_FILES_BOOKMARK_ITEMS,                        [],                         SettingsFmt(list)),
            SettingsRule(BCSettingsKey.SESSION_FILES_SAVEDVIEWS_ITEMS,                      [],                         SettingsFmt(list)),
            SettingsRule(BCSettingsKey.SESSION_FILES_LASTDOC_O_ITEMS,                       [],                         SettingsFmt(list)),
            SettingsRule(BCSettingsKey.SESSION_FILES_LASTDOC_S_ITEMS,                       [],                         SettingsFmt(list))
        ]

        for panelId in panelIds:
            rules+=[
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_LAYOUT.id(panelId=panelId),             'top',                      SettingsFmt(str, ['full','top','left','right','bottom'])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_CURRENTPATH.id(panelId=panelId),        '@home',                    SettingsFmt(str)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_FILTERVISIBLE.id(panelId=panelId),      True,                       SettingsFmt(bool)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_FILTERVALUE.id(panelId=panelId),        '*',                        SettingsFmt(str)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNSORT.id(panelId=panelId),         [1,True],                   SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(bool)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNORDER.id(panelId=panelId),        [0,1,2,3,4,5,6,7,8],        SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(int, [0,1,2,3,4,5,6,7,8]), SettingsFmt(int, [0,1,2,3,4,5,6,7,8])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_COLUMNSIZE.id(panelId=panelId),         [0,0,0,0,0,0,0,0,0],        SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_ICONSIZE.id(panelId=panelId),           0,                          SettingsFmt(int, [0, 1, 2, 3, 4, 5, 6, 7, 8])),

                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_LAYOUT.id(panelId=panelId),         'top',                      SettingsFmt(str, ['top','left','right','bottom'])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNSORT.id(panelId=panelId),     [3,False],                  SettingsFmt(int, [0,1,2,3,4,5,6]), SettingsFmt(bool)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNORDER.id(panelId=panelId),    [0,1,2,3,4,5,6],            SettingsFmt(int, [0,1,2,3,4,5,6]), SettingsFmt(int, [0,1,2,3,4,5,6]), SettingsFmt(int, [0,1,2,3,4,5,6]), SettingsFmt(int, [0,1,2,3,4,5,6]), SettingsFmt(int, [0,1,2,3,4,5,6]), SettingsFmt(int, [0,1,2,3,4,5,6]), SettingsFmt(int, [0,1,2,3,4,5,6])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_COLUMNSIZE.id(panelId=panelId),     [0,0,0,0,0,0,0],            SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int), SettingsFmt(int)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_CLIPBOARD_ICONSIZE.id(panelId=panelId),       0,                          SettingsFmt(int, [0, 1, 2, 3, 4, 5, 6, 7, 8])),

                    SettingsRule(BCSettingsKey.SESSION_PANEL_VIEW_FILES_THUMBNAIL.id(panelId=panelId),          False,                      SettingsFmt(bool)),

                    SettingsRule(BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId),                'files',                    SettingsFmt(str, ['files','documents','clipboard'])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId),               'info',                     SettingsFmt(str, ['info','dirtree'])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId),           'generic',                  SettingsFmt(str, ['generic','image','kra'])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId),              ['files', 'documents', 'clipboard'],
                                                                                                                                            SettingsFmt(str, ['files','documents','clipboard']), SettingsFmt(str, ['files','documents','clipboard']), SettingsFmt(str, ['files','documents','clipboard'])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId),             ['info', 'dirtree'],        SettingsFmt(str, ['info','dirtree']), SettingsFmt(str, ['info','dirtree'])),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_SPLITTER_CLIPBOARD_POSITION.id(panelId=panelId),   [1000,1000],                SettingsFmt(int), SettingsFmt(int)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_SPLITTER_FILES_POSITION.id(panelId=panelId),       [1000,1000],                SettingsFmt(int), SettingsFmt(int)),
                    SettingsRule(BCSettingsKey.SESSION_PANEL_SPLITTER_PREVIEW_POSITION.id(panelId=panelId),     [1000,1000],                SettingsFmt(int), SettingsFmt(int)),

                    SettingsRule(BCSettingsKey.SESSION_PANEL_PREVIEW_BACKGROUND.id(panelId=panelId),            4,                          SettingsFmt(int, [0, 1, 2, 3, 4]))
                ]

        super(BCSettings, self).__init__(pluginId, rules)


class BCSettingsDialogBox(QDialog):
    """User interface fo settings"""

    CATEGORY_GENERAL = 0
    CATEGORY_NAVIGATION = 1
    CATEGORY_IMAGES = 2
    CATEGORY_CLIPBOARD = 3
    CATEGORY_CACHE = 4

    def __init__(self, title, uicontroller, parent=None):
        super(BCSettingsDialogBox, self).__init__(parent)

        self.__title = title

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcsettings.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.setWindowTitle(self.__title)
        self.lvCategory.itemSelectionChanged.connect(self.__categoryChanged)

        self.__itemCatGeneral = QListWidgetItem(buildIcon("pktk:tune"), i18n("General"))
        self.__itemCatGeneral.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_GENERAL)
        self.__itemCatNavigation = QListWidgetItem(buildIcon("pktk:navigation"), i18n("Navigation"))
        self.__itemCatNavigation.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_NAVIGATION)
        self.__itemCatImageFiles = QListWidgetItem(buildIcon("pktk:image"), i18n("Image files"))
        self.__itemCatImageFiles.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_IMAGES)
        self.__itemCatClipboard = QListWidgetItem(buildIcon("pktk:clipboard"), i18n("Clipboard"))
        self.__itemCatClipboard.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_CLIPBOARD)
        self.__itemCatCachedData = QListWidgetItem(buildIcon("pktk:cache_refresh"), i18n("Cached data"))
        self.__itemCatCachedData.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_CACHE)

        self.__uiController = uicontroller

        self.__replaceOpenDbAlertUser = True

        self.pbCCIClearCache.clicked.connect(self.__clearCache)
        self.pbCCIClearCacheCS.clicked.connect(self.__clearCacheCS)
        self.pbCCIClearCacheCP.clicked.connect(self.__clearCacheCP)
        self.pbCCIClearCacheMD.clicked.connect(self.__clearCacheMD)

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
        self.lvCategory.addItem(self.__itemCatClipboard)
        self.lvCategory.addItem(self.__itemCatCachedData)
        self.__setCategory(BCSettingsDialogBox.CATEGORY_GENERAL)

        # --- NAV Category -----------------------------------------------------
        self.bcpbCNUserDefined.setPath(BCSettings.get(BCSettingsKey.CONFIG_FILES_HOME_DIR_UD))
        self.bcpbCNUserDefined.setOptions(BCWPathBar.OPTION_SHOW_NONE)

        self.cbCNNavBarBtnHome.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_HOME))
        self.cbCNNavBarBtnViews.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_VIEWS))
        self.cbCNNavBarBtnBookmarks.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_BOOKMARKS))
        self.cbCNNavBarBtnHistory.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_HISTORY))
        self.cbCNNavBarBtnLastDocuments.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_LASTDOCUMENTS))
        self.cbCNNavBarBtnGoBack.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_BACK))
        self.cbCNNavBarBtnGoUp.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_UP))
        self.cbCNNavBarBtnQuickFilter.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_NAVBAR_BUTTONS_QUICKFILTER))

        if BCSettings.get(BCSettingsKey.CONFIG_FILES_HOME_DIR_MODE) == BCSettingsValues.HOME_DIR_SYS:
            self.rbCNHomeDirSys.setChecked(True)
            self.bcpbCNUserDefined.setEnabled(False)
        else:
            self.rbCNHomeDirUD.setChecked(True)
            self.bcpbCNUserDefined.setEnabled(True)

        self.rbCNHomeDirSys.clicked.connect(setHomeDirSys)
        self.rbCNHomeDirUD.clicked.connect(setHomeDirUD)

        self.hsCNHistoryMax.setValue(BCSettings.get(BCSettingsKey.CONFIG_FILES_HISTORY_MAXITEMS))
        self.cbCNHistoryKeepWhenQuit.setChecked(BCSettings.get(BCSettingsKey.CONFIG_FILES_HISTORY_KEEPONEXIT))

        self.hsCNLastDocsMax.setValue(BCSettings.get(BCSettingsKey.CONFIG_FILES_LASTDOC_MAXITEMS))

        self.pbCNHistoryClear.clicked.connect(historyClear)
        self.pbCNLastDocumentsClear.clicked.connect(lastDocumentsClear)
        self.pbCNLastDocumentsReset.clicked.connect(lastDocumentsReset)
        updateBtn()

        # --- GEN Category -----------------------------------------------------
        self.cbCGLaunchOpenBC.setEnabled(checkKritaVersion(5,0,0))
        self.cbCGLaunchOpenBC.setChecked(BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_ATSTARTUP))

        self.cbCGLaunchReplaceOpenDb.setEnabled(checkKritaVersion(5,0,0))
        self.cbCGLaunchReplaceOpenDb.setChecked(BCSettings.get(BCSettingsKey.CONFIG_GLB_OPEN_OVERRIDEKRITA))
        self.cbCGLaunchReplaceOpenDb.toggled.connect(self.__replaceOpenDbAlert)

        if BCSettings.get(BCSettingsKey.CONFIG_GLB_FILE_UNIT) == BCSettingsValues.FILE_UNIT_KIB:
            self.rbCGFileUnitBinary.setChecked(True)
        else:
            self.rbCGFileUnitDecimal.setChecked(True)

        value = BCSettings.get(BCSettingsKey.CONFIG_GLB_SYSTRAY_MODE)
        if value == BCSysTray.SYSTRAY_MODE_ALWAYS:
            self.rbCGSysTrayAlways.setChecked(True)
        elif value == BCSysTray.SYSTRAY_MODE_WHENACTIVE:
            self.rbCGSysTrayWhenActive.setChecked(True)
        elif value == BCSysTray.SYSTRAY_MODE_NEVER:
            self.rbCGSysTrayNever.setChecked(True)
        elif value == BCSysTray.SYSTRAY_MODE_FORNOTIFICATION:
            self.rbCGSysTrayNotification.setChecked(True)

        # --- Image Category -----------------------------------------------------
        value = BCSettings.get(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_KRA)
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
        self.cbxCIFKraOptCreDocName.setCurrentText(BCSettings.get(BCSettingsKey.CONFIG_FILES_NEWFILENAME_KRA))

        value = BCSettings.get(BCSettingsKey.CONFIG_FILES_DEFAULTACTION_OTHER)
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
        self.cbxCIFOthOptCreDocName.setCurrentText(BCSettings.get(BCSettingsKey.CONFIG_FILES_NEWFILENAME_OTHER))

        # --- Clipboard Category -----------------------------------------------------
        value = BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_MODE_GENERAL)
        if value == BCSettingsValues.CLIPBOARD_MODE_ALWAYS:
            self.rbCCModeAlways.setChecked(True)
        elif value == BCSettingsValues.CLIPBOARD_MODE_ACTIVE:
            self.rbCCModeActive.setChecked(True)
        elif value == BCSettingsValues.CLIPBOARD_MODE_MANUAL:
            self.rbCCModeManual.setChecked(True)

        value = BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_DEFAULT_ACTION)
        if value==BCSettingsValues.CLIPBOARD_ACTION_NLAYER:
            self.rbCCActionPasteAsNewLayer.setChecked(True)
        elif value==BCSettingsValues.CLIPBOARD_ACTION_NDOCUMENT:
            self.rbCCActionPasteAsNewDocument.setChecked(True)

        self.cbCCAsNewDocument.setChecked(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_PASTE_MODE_ASNEWDOC))
        self.cbCCParseTextHtml.setChecked(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_URL_PARSE_TEXTHTML))
        self.cbCCAutomaticUrlDownload.setChecked(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_URL_AUTOLOAD))
        self.cbCCUsePersistent.setChecked(BCSettings.get(BCSettingsKey.CONFIG_CLIPBOARD_CACHE_PERSISTENT))


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

        # --- Clipboard Category -----------------------------------------------------
        if self.rbCCModeAlways.isChecked():
            self.__uiController.commandSettingsClipboardCacheMode(BCSettingsValues.CLIPBOARD_MODE_ALWAYS)
        elif self.rbCCModeActive.isChecked():
            self.__uiController.commandSettingsClipboardCacheMode(BCSettingsValues.CLIPBOARD_MODE_ACTIVE)
        else:
            self.__uiController.commandSettingsClipboardCacheMode(BCSettingsValues.CLIPBOARD_MODE_MANUAL)

        if self.rbCCActionPasteAsNewLayer.isChecked():
            self.__uiController.commandSettingsClipboardDefaultAction(BCSettingsValues.CLIPBOARD_ACTION_NLAYER)
        else:
            #self.rbCCActionPasteAsNewDocument.isChecked():
            self.__uiController.commandSettingsClipboardDefaultAction(BCSettingsValues.CLIPBOARD_ACTION_NDOCUMENT)

        self.__uiController.commandSettingsClipboardPasteAsNewDocument(self.cbCCAsNewDocument.isChecked())
        self.__uiController.commandSettingsClipboardCachePersistent(self.cbCCUsePersistent.isChecked())
        self.__uiController.commandSettingsClipboardUrlAutomaticDownload(self.cbCCAutomaticUrlDownload.isChecked())
        self.__uiController.commandSettingsClipboardUrlParseTextHtml(self.cbCCParseTextHtml.isChecked())


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
            WDialogMessage.display(
                    i18n(f"{self.__title}::Override Krita's native ""Open file"" dialog"),
                    i18n(f"Once option is applied, Krita's native <i>Open file</i> dialog will be replaced by <i>Buli Commander</><br><br>"
                         f"If later you want restore original <i>Open file</i> dialog, keep in mind that at this moment you'll need to restart Krita"
                        )
                )
        else:
            # User want to restore native dialog box
            WDialogMessage.display(
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
            self.lblCCINbFileAndSize.setText(f'{nbFiles} files, {bytesSizeToStr(sizeFiles, BCSettingsValues.FILE_UNIT_KIB)}')
        else:
            self.lblCCINbFileAndSize.setText(f'{nbFiles} files, {bytesSizeToStr(sizeFiles, BCSettingsValues.FILE_UNIT_KB)}')

        self.pbCCIClearCache.setEnabled(sizeFiles>0)


        nbItemsS, sizeItemsS = self.__uiController.clipboard().cacheSizeS(True)
        if self.rbCGFileUnitBinary.isChecked():
            self.lblCCINbItemsAndSizeCS.setText(f'{nbItemsS} items, {bytesSizeToStr(sizeItemsS, BCSettingsValues.FILE_UNIT_KIB)}')
        else:
            self.lblCCINbItemsAndSizeCS.setText(f'{nbItemsS} items, {bytesSizeToStr(sizeItemsS, BCSettingsValues.FILE_UNIT_KB)}')
        self.pbCCIClearCacheCS.setEnabled(sizeItemsS>0)

        nbItemsP, sizeItemsP = self.__uiController.clipboard().cacheSizeP()
        if self.rbCGFileUnitBinary.isChecked():
            self.lblCCINbItemsAndSizeCP.setText(f'{nbItemsP} items, {bytesSizeToStr(sizeItemsP, BCSettingsValues.FILE_UNIT_KIB)}')
        else:
            self.lblCCINbItemsAndSizeCP.setText(f'{nbItemsP} items, {bytesSizeToStr(sizeItemsP, BCSettingsValues.FILE_UNIT_KB)}')
        self.pbCCIClearCacheCP.setEnabled(sizeItemsP>0)

        dbStats=BCFileCache.globalInstance().getStats()
        if self.rbCGFileUnitBinary.isChecked():
            self.lblCCIDbCache.setText(f"{dbStats['nbHash']} images, {bytesSizeToStr(dbStats['dbSize'], BCSettingsValues.FILE_UNIT_KIB)}")
        else:
            self.lblCCIDbCache.setText(f"{dbStats['nbHash']} images, {bytesSizeToStr(dbStats['dbSize'], BCSettingsValues.FILE_UNIT_KB)}")
        self.pbCCIClearCacheMD.setEnabled(dbStats['nbHash']>0)


    def __clearCache(self):
        """Clear cache after user confirmation"""

        if WDialogBooleanInput.display(
                    i18n(f"{self.__title}::Clear Cache"),
                    i18n(f"Current cache content will be cleared ({self.lblCCINbFileAndSize.text()})<br><br>Do you confirm action?")
                ):
            shutil.rmtree(BCFile.thumbnailCacheDirectory(), ignore_errors=True)
            BCFile.initialiseCache()
            BCFileCache.initialise()
            self.__calculateCacheSize()


    def __clearCacheCS(self):
        """Clear clipboard session cache after user confirmation"""
        if WDialogBooleanInput.display(
                    i18n(f"{self.__title}::Clear Clipboard Cache (session)"),
                    i18n(f"Current clipboard session cache content will be cleared ({self.lblCCINbItemsAndSizeCS.text()})<br><br>Do you confirm action?")
                ):
            self.__uiController.clipboard().cacheSessionFlush()
            BCClipboard.initialiseCache()
            self.__calculateCacheSize()


    def __clearCacheCP(self):
        """Clear clipboard persistent cache after user confirmation"""
        if WDialogBooleanInput.display(
                    i18n(f"{self.__title}::Clear Clipboard Cache (persistent)"),
                    i18n(f"Persitent clipboard cache content will be cleared ({self.lblCCINbItemsAndSizeCP.text()})<br><br>Do you confirm action?")
                ):
            self.__uiController.clipboard().cachePersistentFlush()
            BCClipboard.initialiseCache()
            self.__calculateCacheSize()


    def __clearCacheMD(self):
        """Clear metadata cache after user confirmation"""

        if WDialogBooleanInput.display(
                    i18n(f"{self.__title}::Clear Metadata Cache"),
                    i18n(f"Current metadata cache content will be cleared ({self.lblCCIDbCache.text()})<br><br>Do you confirm action?")
                ):
            BCFileCache.globalInstance().clearDbContent()
            self.__calculateCacheSize()


    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCSettingsDialogBox(title, uicontroller)
        return db.exec()
