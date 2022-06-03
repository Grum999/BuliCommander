#-----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2019-2022 - Grum999
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


# -----------------------------------------------------------------------------
# The bcfile module provides some classes that can be used to work with images
#
# Main classes are:
# - BCFile:
#       Define a fileproperties and allows, when it's a [valid] image to easily
#       get some informations (size, thumbnail, preview)
#       The class allows to manage thumbnails with a cache system
#
# - BCFileList:
#       Allows to build file list from directories with filtering&sort criterias
#       using multiprocessing
#       Also provide the possibilty to retrieve thumbnails
#       Results can be exported into different format





from enum import Enum
from functools import cmp_to_key
from multiprocessing import Pool

import hashlib
import io
import json
import os
import re
import struct
import sys
import textwrap
import time
import xml.etree.ElementTree as xmlElement
import zipfile
import zlib
import math
import copy


from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QFileInfo,
        QSize,
        QStandardPaths
    )
from PyQt5.QtGui import (
        QImage,
        QImageReader
    )
from PyQt5.QtWidgets import (
        QFileIconProvider
    )
from PyQt5.QtSql import (QSqlDatabase, QSqlQuery)

from bulicommander.pktk.modules.bytesrw import BytesRW
from bulicommander.pktk.modules.languagedef import LanguageDef
from bulicommander.pktk.modules.tokenizer import (
        Tokenizer,
        TokenizerRule,
        TokenType
    )
from bulicommander.pktk.modules.workers import (
        WorkerPool,
        Worker
    )
from bulicommander.pktk.modules.uitheme import UITheme
from bulicommander.pktk.modules.imgutils import buildIcon
from bulicommander.pktk.modules.utils import (
        Debug,
        JsonQObjectEncoder,
        JsonQObjectDecoder,
        regExIsValid,
        intDefault
    )
from bulicommander.pktk.modules.timeutils import (
        Stopwatch,
        strToTs,
        tsToStr,
        Timer
    )
from bulicommander.pktk.modules.strutils import (
        strToBytesSize,
        bytesSizeToStr,
        strDefault
    )
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )

if sys.platform == 'linux':
    import pwd
    import grp


# ------------------------------------------------------------------------------

class EInvalidExpression(Exception):
    """An invalid expression is detected"""
    pass


class EInvalidRuleParameter(Exception):
    """An invalid rule parameter has been detected"""
    pass


class EInvalidQueryResult(Exception):
    """Query result is not valid"""
    pass


# ------------------------------------------------------------------------------

class BCFileManipulateNameLanguageDef(LanguageDef):

    class ITokenType(TokenType, Enum):
        STRING = ('String', 'A STRING value')
        KW = ('Keyword', 'A keyword return a STRING value')
        FUNCO_STR = ('String function', 'A FUNCTION for which returned result is a STRING')
        FUNCO_NUM = ('Number function', 'A FUNCTION for which returned result is a NUMBER')
        FUNCC = ('Function terminator', 'Define end of function')
        SEPARATOR = ('Separator', 'A separator for functions arguments')
        NUMBER = ('Number', 'A NUMBER value')
        TEXT = ('Text', 'A TEXT value')
        ETEXT = ('Escaped text', 'A TEXT value')

    def __init__(self):
        super(BCFileManipulateNameLanguageDef, self).__init__([
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.STRING, r'"[^"\\]*(?:\\.[^"\\]*)*"'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.STRING, r"'[^'\\]*(?:\\.[^'\\]*)*'"),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, r'\[(?:upper|lower|capitalize|replace|sub|regex|index|camelize):',
                                                                    'Function [STRING]',
                                                                    [('[upper:\x01<value>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Convert text *<value>* to uppercase text\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[upper:{file:baseName}]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`MY_FILE__NAME01`**')),
                                                                     ('[lower:\x01<value>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Convert text *<value>* to lowercase text\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[lower:{file:baseName}]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`MY-FILE--NAME01`*:\n'
                                                                                '**`my_file__name01`**')),
                                                                     ('[capitalize:\x01<value>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Convert text *<value>* to capitalized text\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[capitalize:{file:baseName}]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`My_file__name01`**')),
                                                                     ('[camelize:\x01<value>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Convert text *<value>* to camel case text\n'
                                                                                '(First alpha character after non-alpha character is set yo upper case)\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[camelize:{file:baseName}]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`My_File__Name01`**')),
                                                                     ('[replace:\x01<value>, "<search>", "<replace>"]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Search *<search>* sequences in *<value>* and replace it with *<replace>*\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword\n\n'
                                                                                'Given *<search>* and *<replace>* must be a string',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[replace:{file:baseName}, "_", "-"]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`my-file--name`**')),
                                                                     ('[regex:\x01<value>, "<pattern>"]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Return sequences from *<value>* that match given regular expression *<pattern>*\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword\n\n'
                                                                                'Given *<pattern>* must be a valid regular expression string',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[regex:{file:baseName}, "[a-z]+"]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`myfilename`**')),
                                                                     ('[regex:\x01<value>, "<pattern>", "<replace>"]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Replace sequences from *<value>* that match given regular expression *<pattern>* with *<replace>*\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword\n\n'
                                                                                'Given *<pattern>* must be a valid regular expression string\n\n'
                                                                                'Given *<replace>* must be a string (use $1, $2, $*n*... to replace captured groups)\n\n',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[regex:{file:baseName}, "([^\d]+)(\d+)", "$2--$1"]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`01--my_file__name`**')),
                                                                     ('[index:\x01<value>, "<separator>", <index>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Return string defined by *<index>* whitin *<value>* splitted with *<separator>*\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword\n\n'
                                                                                'Given *<separator>* position must be a valid string\n'
                                                                                'Given *<index>* position must be a valid number\n'
                                                                                ' - First index position is 1\n',
                                                                                # example
                                                                                'Following instructions:\n'
                                                                                '**`[index:{file:baseName}, "_", 2]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`file`**')),
                                                                     ('[sub:\x01<value>, <start>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Return substring from *<value>* from *<start>* position\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword\n\n'
                                                                                'Given *<start>* position must be a valid number\n'
                                                                                ' - First character position is 1\n'
                                                                                ' - Negative value means to start from last character',
                                                                                # example
                                                                                'Following instructions:\n'
                                                                                '**`[sub:{file:baseName}, 4]`** and **`[sub:{file:baseName}, -6]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`file__name01`** and **`name01`**')),
                                                                     ('[sub:\x01<value>, <start>, <length>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [STRING]',
                                                                                # description
                                                                                'Return substring from *<value>* from *<start>* position for *<length>* characters\n\n'
                                                                                'Given *<value>* can be:\n'
                                                                                ' - a string\n'
                                                                                ' - a keyword\n\n'
                                                                                'Given *<start>* position must be a valid number\n'
                                                                                ' - First character position is 1\n'
                                                                                ' - Negative value means to start from last character\n\n'
                                                                                'Given *<length>* must be a valid number\n',
                                                                                # example
                                                                                'Following instructions:\n'
                                                                                '**`[sub:{file:baseName}, 4, 4]`** and **`[sub:{file:baseName}, -6, 4]`**\n\n'
                                                                                'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                                                                '**`file`** and **`name`**'))
                                                                    ],
                                                                    'f'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_NUM, r'\[(?:len):',
                                                                    'Function [NUMBER]',
                                                                    [('[len:\x01<value>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [NUMBER]',
                                                                                # description
                                                                                'Return length (number of characters) for given text *<value>*',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[len:"text"]`**\n\n'
                                                                                'Will return:\n'
                                                                                '**4**')),
                                                                     ('[len:\x01<value>, <adjustment>]',
                                                                            TokenizerRule.formatDescription(
                                                                                'Function [NUMBER]',
                                                                                # description
                                                                                'Return length (number of characters) for given text *<value>* with adjusted with given *<adjustment>* number',
                                                                                # example
                                                                                'Following instruction:\n'
                                                                                '**`[len:"text", 1]`**\n\n'
                                                                                'Will return:\n'
                                                                                '**5**'))
                                                                    ],
                                                                    'f'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.KW, r'\{(?:counter(?::#+)?|image:size(?::(?:width|height)(?::#+)?)?|time(?::(?:hh|mm|ss))?|date(?::(?:yyyy|mm|dd))?|file:date(?::(?:yyyy|mm|dd))?|file:time(?::(?:hh|mm|ss))?|file:ext|file:baseName|file:path|file:format|file:hash:(?:md5|sha1|sha256|sha512))\}',
                                                                  'Keyword',
                                                                  [('{file:baseName}',
                                                                         TokenizerRule.formatDescription(
                                                                             'Keyword',
                                                                             # description
                                                                             'Return file name, without path and without extension')),
                                                                   ('{file:ext}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return file extension, without dot **`.`**')),
                                                                   ('{file:path}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return file path\n\n'
                                                                              'Please note, path separators are stripped')),
                                                                   ('{file:format}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return file format (can be different than extension)')),
                                                                   ('{file:date}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return file date, with format *`YYYYMMDD`*')),
                                                                   ('{file:date:yyyy}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *year* from file date, with format *`YYYY`*')),
                                                                   ('{file:date:mm}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *month* from file date, with format *`MM`*')),
                                                                   ('{file:date:dd}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *day* from file date, with format *`DD`*')),
                                                                   ('{file:time}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return file time, with format *`HHMMSS`*')),
                                                                   ('{file:time:hh}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *hours* from file time, with format *`HH`*')),
                                                                   ('{file:time:mm}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *minutes* from file time, with format *`MM`*')),
                                                                   ('{file:time:ss}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *seconds* from file time, with format *`SS`*')),
                                                                   ('{file:hash:md5}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return hash for file using MD5 algorithm (32 characters length)')),
                                                                   ('{file:hash:sha1}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return hash for file using SHA-1 algorithm (40 characters length)')),
                                                                   ('{file:hash:sha256}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return hash for file using SHA-256 algorithm (64 characters length)')),
                                                                   ('{file:hash:sha512}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return hash for file using SHA-512 algorithm (128 characters length)')),
                                                                   ('{image:size}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return image size from file, with format *`WxH`*')),
                                                                   ('{image:size:width}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return image width from file')),
                                                                   ('{image:size:width:####}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return image width from file\n\n'
                                                                              'Use hash character **`#`** to define minimum number of digits')),
                                                                   ('{image:size:height}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return image height from file')),
                                                                   ('{image:size:height:####}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return image height from file\n\n'
                                                                              'Use hash character **`#`** to define minimum number of digits')),
                                                                   ('{date}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return current sytem date, with format *`YYYYMMDD`*')),
                                                                   ('{date:yyyy}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *year* from current sytem date, with format *`YYYY`*')),
                                                                   ('{date:mm}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *month* from current sytem date, with format *`MM`*')),
                                                                   ('{date:dd}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *day* from current sytem date, with format *`DD`*')),
                                                                   ('{time}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return current sytem time, with format *`HHMMSS`*')),
                                                                   ('{time:hh}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *hours* from current sytem time, with format *`HH`*')),
                                                                   ('{time:mm}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *minutes* from current sytem time, with format *`MM`*')),
                                                                   ('{time:ss}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return *seconds* from current sytem time, with format *`SS`*')),
                                                                   ('{counter}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return a counter value\n\n'
                                                                              'Counter start from 1, and is incremented if a target file already match the same pattern\n\n'
                                                                              '*Please note, due to technical reason, use of counter with many files is **slow***')),
                                                                   ('{counter:####}',
                                                                          TokenizerRule.formatDescription(
                                                                              'Keyword',
                                                                              # description
                                                                              'Return a counter value\n\n'
                                                                              'Counter start from 1, and is incremented if a target file already match the same pattern\n\n'
                                                                              'Use hash character **`#`** to define minimum counter digits\n\n'
                                                                              '*Please note, due to technical reason, use of counter with many files is **slow***'))
                                                                  ],
                                                                  'k'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.ETEXT, r'\\\[|\\\]|\\,|\\\{|\\\}'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.NUMBER, r'-\d+|^\d+'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, r',{1}?'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, r'\]{1}?'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.SPACE, r'\s+'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.TEXT, r'[{\[,][^{\[\]\}"\'\\\/\s,]*|[^{\[\]\}"\'\\\/\s,]+')
        ])

        self.setStyles(UITheme.DARK_THEME, [
            (BCFileManipulateNameLanguageDef.ITokenType.STRING, '#9ac07c', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.NUMBER, '#c9986a', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, '#e5dd82', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCO_NUM, '#e5dd82', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCC, '#e5dd82', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.KW, '#e18890', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, '#c278da', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.SPACE, None, False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.TEXT, '#ffffff', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.ETEXT, '#999999', False, False)
        ])
        self.setStyles(UITheme.LIGHT_THEME, [
            (BCFileManipulateNameLanguageDef.ITokenType.STRING, '#9ac07c', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.NUMBER, '#c9986a', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, '#c278da', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCC, '#c278da', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.KW, '#e18890', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, '#c278da', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.SPACE, None, False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.TEXT, '#6aafec', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.ETEXT, '#c278da', False, False)
        ])


class BCFileManagedFormat(object):
    """Managed files format """
    KRA = 'kra'
    KRZ = 'krz'
    PNG = 'png'
    JPG = 'jpg'
    JPEG = 'jpeg'
    ORA = 'ora'
    SVG = 'svg'
    GIF = 'gif'
    PSD = 'psd'
    XCF = 'xcf'
    BMP = 'bmp'
    WEBP = 'webp'

    UNKNOWN = 'unknown'
    MISSING = 'missing'
    DIRECTORY = 'directory'

    __TRANSLATIONS = {
            'KRA': ('Krita image', 'Krita native image'),
            'KRZ': ('Krita archive', 'Krita archival image'),
            'JPG': ('JPEG image', 'JPEG Interchange Format'),
            'JPEG': ('JPEG image', 'JPEG Interchange Format'),
            'PNG': ('PNG image', 'Portable Network Graphic'),
            'ORA': ('OpenRaster image', 'Open raster'),
            'SVG': ('SVG image', 'Scalable Vector Graphic'),
            'GIF': ('GIF image', 'Graphics Interchange Format'),

            'PSD': ('PSD image', 'PhotoShop Document'),
            'TIF': ('TIFF image', 'Tagged Image File Format'),
            'TIFF': ('TIFF image', 'Tagged Image File Format'),
            'TGA': ('TGA image', 'Truevision TGA'),
            'XCF': ('Gimp image', 'eXperimental Computing Facility'),
            'WEBP': ('WebP', 'WebP'),
            'BMP': ('BMP image', 'Bitmap Image File'),

            'ZIP': 'ZIP archive',
            '7Z': '7Zip archive',
            'GZ': 'GZ archive',
            'TAR': 'TAR archive',

            'PY': 'Python file',
            'PYC': 'Compiled Python file',

            'BIN': 'Binary file',
            'DAT': 'Data file',
            'TMP': 'Temporary file',
            'BAK': 'Backup file',

            'TXT': 'Text document',
            'MD': 'Markdown document',
            'PDF': 'PDF document',

            'DIRECTORY': (i18n('<DIR>'), i18n('Directory')),
            'MISSING': 'Missing file'
        }

    @staticmethod
    def format(value):
        if isinstance(value, str):
            lvalue=value.lower()
            if lvalue in BCFileManagedFormat.list():
                return lvalue
            elif lvalue == 'jpg':
                return BCFileManagedFormat.JPEG
        raise EInvalidType("Invalid given format")

    @staticmethod
    def translate(value, short=True):
        backupFile=False

        if value == '' or value == '~':
            return 'Unknown file'

        if value[0] == '.':
            value = value[1:]

        if reResult:=re.search(f'([^\.]+)({BCFileManagedFormat.backupSuffixRe()})$', value):
            backupFile = True
            value=reResult.groups()[0]

        value = value.upper()

        if value in BCFileManagedFormat.__TRANSLATIONS:
            if isinstance(BCFileManagedFormat.__TRANSLATIONS[value], str):
                returned = BCFileManagedFormat.__TRANSLATIONS[value]
            elif short:
                returned = BCFileManagedFormat.__TRANSLATIONS[value][0]
            else:
                returned = BCFileManagedFormat.__TRANSLATIONS[value][1]
        else:
            returned = f'{value} file'

        if backupFile:
            returned+=' (backup)'

        return returned

    @staticmethod
    def list(full=True):
        if full:
            return [BCFileManagedFormat.KRA,
                    BCFileManagedFormat.KRZ,
                    BCFileManagedFormat.PNG,
                    BCFileManagedFormat.JPG,
                    BCFileManagedFormat.JPEG,
                    BCFileManagedFormat.ORA,
                    BCFileManagedFormat.SVG,
                    BCFileManagedFormat.GIF,
                    BCFileManagedFormat.PSD,
                    BCFileManagedFormat.XCF,
                    BCFileManagedFormat.BMP,
                    BCFileManagedFormat.WEBP]
        else:
            # remove KRA/ORA/PSD/XCF (use dedicated code from plugin to retrieve basic information)
            return [BCFileManagedFormat.PNG,
                    BCFileManagedFormat.JPG,
                    BCFileManagedFormat.JPEG,
                    BCFileManagedFormat.SVG,
                    BCFileManagedFormat.GIF,
                    BCFileManagedFormat.BMP,
                    BCFileManagedFormat.WEBP]

    @staticmethod
    def backupSuffixRe():
        """return backup suffix as regular expression"""
        return r'(?:\.\d+)?'+Krita.instance().readSetting('', 'backupfilesuffix', '~').replace('.', r'\.')

    @staticmethod
    def inExtensions(value, withBackup=False, noExtIsOk=False):
        if value == '':
            return noExtIsOk

        for extension in BCFileManagedFormat.list():
            if BCFileManagedFormat.isExtension(value, extension, withBackup):
                return True
        return False

    @staticmethod
    def isExtension(value, extReference, withBackup=False):
        if value.lower() == f'.{extReference}' or (withBackup and re.match(f"\.{extReference}{BCFileManagedFormat.backupSuffixRe()}$", value)):
            return True
        return False


class BCFileThumbnailSize(Enum):
    """Possible sizes for a thumbnail file"""

    SMALL = 64
    MEDIUM = 128
    LARGE = 256
    HUGE = 512

    def next(self):
        """Return next size, None if there's no next size"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) + 1
        if index >= len(members):
            return None
        return members[index]

    def prev(self):
        """Return previous size, None if there's no previous size"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) - 1
        if index < 0:
            return None
        return members[index]

    def size(self, type=int):
        """return the size as int or QSize"""
        if type==int:
            return self.value
        elif type==QSize:
            return QSize(self.value, self.value)
        else:
            raise EInvalidType("Given `type` must be int or QSize")

    @staticmethod
    def fromValue(value):
        """Return a BCFileThumbnailSize according to given value"""
        if not isinstance(value, int):
            return BCFile.thumbnailCacheDefaultSize()
        elif value <= 64:
            return BCFileThumbnailSize.SMALL
        elif value <= 128:
            return BCFileThumbnailSize.MEDIUM
        elif value <= 256:
            return BCFileThumbnailSize.LARGE
        else:
            return BCFileThumbnailSize.HUGE


class BCFileThumbnailFormat(Enum):
    """Possible format for a thumbnail file"""
    PNG = 'png'
    JPEG = 'jpeg'


class BCFileProperty(Enum):
    PATH = 'path'
    FULL_PATHNAME = 'fullPathName'
    FILE_NAME = 'fileName'
    FILE_FORMAT = 'fileFormat'
    FILE_SIZE = 'fileSize'
    FILE_DATE = 'fileDate'
    FILE_EXTENSION = 'fileExtension'
    IMAGE_WIDTH = 'imageWidth'
    IMAGE_HEIGHT = 'imageHeight'
    IMAGE_RATIO = 'imageRatio'
    IMAGE_PIXELS = 'imagePixels'

    def translate(self):
        if self == BCFileProperty.PATH:
            return i18n('path')
        elif self == BCFileProperty.FULL_PATHNAME:
            return i18n('full path/file name')
        elif self == BCFileProperty.FILE_NAME:
            return i18n('file name')
        elif self == BCFileProperty.FILE_FORMAT:
            return i18n('file format')
        elif self == BCFileProperty.FILE_SIZE:
            return i18n('file size')
        elif self == BCFileProperty.FILE_EXTENSION:
            return i18n('file extension')
        elif self == BCFileProperty.FILE_DATE:
            return i18n('file date')
        elif self == BCFileProperty.IMAGE_WIDTH:
            return i18n('image width')
        elif self == BCFileProperty.IMAGE_HEIGHT:
            return i18n('image height')
        elif self == BCFileProperty.IMAGE_RATIO:
            return i18n('image aspect ratio')
        elif self == BCFileProperty.IMAGE_PIXELS:
            return i18n('image number of pixels')
        else:
            return self.value


class BCFileManipulateName(object):

    __tokenizer = None

    @staticmethod
    def parseFileNameKw(file, pattern=None, targetPath=None):
        """Return a file name build from given file and pattern

        If pattern equals "<None>"
        => return empty string

        Otherwise, the following markup can be used:
            "{file:path}"       The file path name
            "{file:baseName}"   The file base name without extension
            "{file:name}"       The file path+base name without extension
            "{file:ext}"        The file extension
            "{file:format}"     The file format

            "{file:date}"            The current system date (yyyymmdd)
            "{file:date:yyyy}"       The current system year
            "{file:date:mm}"         The current system month
            "{file:date:dd}"         The current system day

            "{file:time}"            The current system time (hhmmss)
            "{file:time:hh}"         The current system hour (00-24)
            "{file:time:mm}"         The current system minutes
            "{file:time:ss}"         The current system seconds

            "{file:hash:md5}"        File hash - MD5
            "{file:hash:sha1}"       File hash - SHA-1
            "{file:hash:sha256}"     File hash - SHA-256
            "{file:hash:sha512}"     File hash - SHA-512

            "{date}"            The current system date (yyyymmdd)
            "{date:yyyy}"       The current system year
            "{date:mm}"         The current system month
            "{date:dd}"         The current system day

            "{time}"            The current system time (hhmmss)
            "{time:hh}"         The current system hour (00-24)
            "{time:mm}"         The current system minutes
            "{time:ss}"         The current system seconds

            "{image:size}"            The current image size (widthxheight)
            "{image:size:width}"      The current image width
            "{image:size:width:####}"      The current image width
            "{image:size:height}"     The current image height
            "{image:size:height:####}"     The current image height

            "{counter}"         A counter to file name
            "{counter:####}"    A counter to file name
        """
        if pattern is None:
            return ''

        if not isinstance(file, BCBaseFile):
            raise EInvalidType('Given `file` must be a <BCBaseFile>')

        if not isinstance(pattern, str):
            raise EInvalidType('Given `pattenr` must be a <str>')

        if pattern.strip() == '' or re.search(r'(?i)<none>', pattern):
            return ''

        currentDateTime = time.time()
        fileName = pattern

        if targetPath is None:
            targetPath = file.path()

        targetPath=targetPath.replace('\\', r'\\')

        isDir = False
        if file.format() != BCFileManagedFormat.DIRECTORY:
            baseFileNameWithoutExt = os.path.splitext(file.name())[0]
            nameFileNameWithoutExt = os.path.splitext(file.fullPathName())[0]
            if file.extension(False) == '' and file.name()[-1] != '.' :
                replaceExtExpr = r"(?i)\.\{file:ext\}"
            else:
                replaceExtExpr = r"(?i)\{file:ext\}"

            fileName = re.sub(replaceExtExpr,      file.extension(False),                        fileName)
            fileName = re.sub(r"(?i)\{image:size\}",           f"{file.getProperty(BCFileProperty.IMAGE_WIDTH)}x{file.getProperty(BCFileProperty.IMAGE_HEIGHT)}", fileName)
            fileName = re.sub(r"(?i)\{image:size:width\}",     f"{file.getProperty(BCFileProperty.IMAGE_WIDTH)}", fileName)
            fileName = re.sub(r"(?i)\{image:size:height\}",    f"{file.getProperty(BCFileProperty.IMAGE_HEIGHT)}", fileName)

            if kw:=re.search("(?i)\{image:size:width:(#+)\}", fileName):
                replaceHash=kw.groups()[0]
                fileName = re.sub(f"(?i){{image:size:width:{replaceHash}}}", f"{file.getProperty(BCFileProperty.IMAGE_WIDTH):0{len(replaceHash)}}", fileName)

            if kw:=re.search("(?i)\{image:size:height:(#+)\}", fileName):
                replaceHash=kw.groups()[0]
                fileName = re.sub(f"(?i){{image:size:height:{replaceHash}}}", f"{file.getProperty(BCFileProperty.IMAGE_HEIGHT):0{len(replaceHash)}}", fileName)


        else:
            isDir = True
            baseFileNameWithoutExt = file.name()
            nameFileNameWithoutExt = file.fullPathName()
            replaceExtExpr = None

            fileName = re.sub(r"(?i)\.\{file:ext\}",     "", fileName)
            fileName = re.sub(r"(?i)\{file:ext\}",       "", fileName)
            fileName = re.sub(r"(?i)\{image:size\}",           "0x0", fileName)
            fileName = re.sub(r"(?i)\{image:size:width\}",     "0", fileName)
            fileName = re.sub(r"(?i)\{image:size:height\}",    "0", fileName)

        baseFileNameWithoutExt=baseFileNameWithoutExt.replace('\\', r'\\')
        nameFileNameWithoutExt=nameFileNameWithoutExt.replace('\\', r'\\')

        fileName = re.sub(r"(?i)\{file:path\}", targetPath,                                   fileName)
        fileName = re.sub(r"(?i)\{file:baseName\}", baseFileNameWithoutExt,                   fileName)
        fileName = re.sub(r"(?i)\{file:name\}", nameFileNameWithoutExt,     fileName)
        fileName = re.sub(r"(?i)\{file:format\}", file.format(),     fileName)

        if re.match(r"(?i)\{file:hash:md5\}", fileName):
            fileName = re.sub(r"(?i)\{file:hash:md5\}",      file.hash('md5'),           fileName)
        if re.match(r"(?i)\{file:hash:sha1\}", fileName):
            fileName = re.sub(r"(?i)\{file:hash:sha1\}",      file.hash('sha1'),           fileName)
        if re.match(r"(?i)\{file:hash:sha256\}", fileName):
            fileName = re.sub(r"(?i)\{file:hash:sha256\}",      file.hash('sha256'),           fileName)
        if re.match(r"(?i)\{file:hash:sha512\}", fileName):
            fileName = re.sub(r"(?i)\{file:hash:sha512\}",      file.hash('sha512'),           fileName)

        fileName = re.sub(r"(?i)\{file:date\}",      tsToStr(file.lastModificationDateTime(), '%Y%m%d'),           fileName)
        fileName = re.sub(r"(?i)\{file:date:yyyy\}", tsToStr(file.lastModificationDateTime(), '%Y'),               fileName)
        fileName = re.sub(r"(?i)\{file:date:mm\}",   tsToStr(file.lastModificationDateTime(), '%m'),               fileName)
        fileName = re.sub(r"(?i)\{file:date:dd\}",   tsToStr(file.lastModificationDateTime(), '%d'),               fileName)

        fileName = re.sub(r"(?i)\{file:time\}",      tsToStr(file.lastModificationDateTime(), '%H%M%S'),           fileName)
        fileName = re.sub(r"(?i)\{file:time:hh\}",   tsToStr(file.lastModificationDateTime(), '%H'),               fileName)
        fileName = re.sub(r"(?i)\{file:time:mm\}",   tsToStr(file.lastModificationDateTime(), '%M'),               fileName)
        fileName = re.sub(r"(?i)\{file:time:ss\}",   tsToStr(file.lastModificationDateTime(), '%S'),               fileName)

        fileName = re.sub(r"(?i)\{date\}",      tsToStr(currentDateTime, '%Y%m%d'),           fileName)
        fileName = re.sub(r"(?i)\{date:yyyy\}", tsToStr(currentDateTime, '%Y'),               fileName)
        fileName = re.sub(r"(?i)\{date:mm\}",   tsToStr(currentDateTime, '%m'),               fileName)
        fileName = re.sub(r"(?i)\{date:dd\}",   tsToStr(currentDateTime, '%d'),               fileName)

        fileName = re.sub(r"(?i)\{time\}",      tsToStr(currentDateTime, '%H%M%S'),           fileName)
        fileName = re.sub(r"(?i)\{time:hh\}",   tsToStr(currentDateTime, '%H'),               fileName)
        fileName = re.sub(r"(?i)\{time:mm\}",   tsToStr(currentDateTime, '%M'),               fileName)
        fileName = re.sub(r"(?i)\{time:ss\}",   tsToStr(currentDateTime, '%S'),               fileName)

        if resultCounter:=re.search("(?i)\{counter(?::(#+))?\}", fileName):
            regEx = re.sub(r"(?i)\{file:path\}", targetPath,                        pattern)

            regEx = re.sub(r"(?i)\{file:baseName\}", baseFileNameWithoutExt,        regEx)
            regEx = re.sub(r"(?i)\{file:name\}", nameFileNameWithoutExt,            regEx)
            if not replaceExtExpr is None:
                regEx = re.sub(replaceExtExpr,  re.escape(file.extension(False)),             regEx)
            else:
                regEx = re.sub(r"(?i)\.\{file:ext\}",     "", regEx)
                regEx = re.sub(r"(?i)\{file:ext\}",       "", regEx)

            regEx = re.sub(r"(?i)\{file:format\}", re.escape(file.format()),     regEx)


            regEx = re.sub(r"(?i)\{file:hash:md5\}",      r'[a-z0-9]{32}',           regEx)
            regEx = re.sub(r"(?i)\{file:hash:sha1\}",     r'[a-z0-9]{40}',           regEx)
            regEx = re.sub(r"(?i)\{file:hash:sha256\}",   r'[a-z0-9]{64}',           regEx)
            regEx = re.sub(r"(?i)\{file:hash:sha512\}",   r'[a-z0-9]{128}',          regEx)

            regEx = re.sub(r"(?i)\{file:date\}",      r'\\d{8}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:date:yyyy\}", r'\\d{4}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:date:mm\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:date:dd\}",   r'\\d{2}',                                    regEx)

            regEx = re.sub(r"(?i)\{file:time\}",      r'\\d{6}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:time:hh\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:time:mm\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:time:ss\}",   r'\\d{2}',                                    regEx)

            regEx = re.sub(r"(?i)\{date\}",      r'\\d{8}',                                    regEx)
            regEx = re.sub(r"(?i)\{date:yyyy\}", r'\\d{4}',                                    regEx)
            regEx = re.sub(r"(?i)\{date:mm\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{date:dd\}",   r'\\d{2}',                                    regEx)

            regEx = re.sub(r"(?i)\{time\}",      r'\\d{6}',                                    regEx)
            regEx = re.sub(r"(?i)\{time:hh\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{time:mm\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{time:ss\}",   r'\\d{2}',                                    regEx)

            regEx = re.sub(r"(?i)\{image:size\}",       r'\\d+x\\d+',                                 regEx)
            regEx = re.sub(r"(?i)\{image:size:width\}", r'\\d+',                                     regEx)
            regEx = re.sub(r"(?i)\{image:size:height\}",r'\\d+',                                     regEx)

            regEx = re.sub(r"(?i)\{counter\}",r'(\\d+)',                                         regEx)

            for replaceHash in resultCounter.groups():
                if not replaceHash is None:
                    regEx = re.sub(f"\{{counter:{replaceHash}\}}", f"(\\\\d{{{len(replaceHash)},}})", regEx)

            regEx = regEx.replace(".", r'\.')

            regEx = f"^{regEx}$"

            if not regExIsValid(regEx):
                return fileName

            # a counter is defined, need to determinate counter value
            #nbFiles = len([foundFile for foundFile in os.listdir(file.path()) if os.path.isfile(os.path.join(file.path(), foundFile)) and not re.search(regEx, foundFile) is None]) + 1

            if isDir:
                fileList = [int(rr.groups()[0]) for foundFile in os.listdir(targetPath) if os.path.isdir(os.path.join(targetPath, foundFile)) and (rr:=re.search(regEx, foundFile))]
            else:
                fileList = [int(rr.groups()[0]) for foundFile in os.listdir(targetPath) if os.path.isfile(os.path.join(targetPath, foundFile)) and (rr:=re.search(regEx, foundFile))]
            if len(fileList) == 0:
                nbFiles = 1
            else:
                nbFiles = max(fileList) + 1

            fileName = re.sub(r"(?i)\{counter\}", f"{nbFiles}",   fileName)

            for replaceHash in resultCounter.groups():
                if not replaceHash is None:
                    fileName = re.sub(f"\{{counter:{replaceHash}\}}", f"{nbFiles:0{len(replaceHash)}}", fileName)

        return fileName

    @staticmethod
    def calculateFileName(file, pattern=None, keepInvalidCharacters=False, targetPath=None, checkOnly=False, tokenizer=None, kwCallBack=None):
        """Process file name manipulation

        Following keywords are supported (same than parseFileNameKw):
            "{file:path}"       The file path name
            "{file:baseName}"   The file base name without extension
            "{file:ext}"        The file extension
            "{file:format}"     The file format

            "{file:date}"            The current system date (yyyymmdd)
            "{file:date:yyyy}"       The current system year
            "{file:date:mm}"         The current system month
            "{file:date:dd}"         The current system day

            "{file:time}"            The current system time (hhmmss)
            "{file:time:hh}"         The current system hour (00-24)
            "{file:time:mm}"         The current system minutes
            "{file:time:ss}"         The current system seconds

            "{file:hash:md5}"        File hash - MD5
            "{file:hash:sha1}"       File hash - SHA-1
            "{file:hash:sha256}"     File hash - SHA-256
            "{file:hash:sha512}"     File hash - SHA-512

            "{date}"            The current system date (yyyymmdd)
            "{date:yyyy}"       The current system year
            "{date:mm}"         The current system month
            "{date:dd}"         The current system day

            "{time}"            The current system time (hhmmss)
            "{time:hh}"         The current system hour (00-24)
            "{time:mm}"         The current system minutes
            "{time:ss}"         The current system seconds

            "{image:size}"            The current image size (widthxheight)
            "{image:size:width}"      The current image width
            "{image:size:width:####}"      The current image width
            "{image:size:height}"     The current image height
            "{image:size:height:####}"     The current image height

            "{counter}"         A counter to file name
            "{counter:####}"    A counter to file name

        Following functions are supporter:
            return STRING:
                upper(value)
                lower(value)
                capitalize(value)
                camelize(values)
                replace(value, regex, replaced)
                sub(value, start[, length])
                regex(value, find[, replace])
                index(value, separator, index)
            return NUMBER
                len(value)

        Example:
            pattern="[lower:[sub:{file:baseName},1,4]]-[sub:{file:baseName},-4].[upper:{file:ext}]"

        Return a tuple:
            (value, error)

        If any error occurs, returned value is None
        Otherwise returned error is None

        """
        NL='\n'

        def processTokenFuncIsArg(token):
            # return True if token can be considered as a function argument
            if token:
                return (not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.FUNCC, BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, BCFileManipulateNameLanguageDef.ITokenType.SPACE))
            else:
                return False

        def processTokenFuncGetNextArg(tokenName):
            # return next token that can be considered as a function argument
            token=tokens.next()

            while token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.SPACE:
                token=tokens.next()

            if not token:
                return None

            if token.type() == BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR:
                token=tokens.next()
            elif token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                return token
            else:
                raise EInvalidExpression(f'Invalid expression for [{tokenName}] function, a separator is missing{NL}{tokens.inText()}')

            while token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.SPACE:
                token=tokens.next()

            return token

        def processTokenFunc(token):
            # token is a function, current processed value for function
            returned=""
            tokenName=token.text()[1:-1].capitalize()
            terminatorMissing=''

            if tokenName == 'Lower':
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid argument type for [Lower] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=processToken(token).lower()
                else:
                    raise EInvalidExpression(f'Missing argument for [Lower] function{NL}{tokens.inText()}')

                token=tokens.next()
            elif tokenName == 'Upper':
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid <value> argument type for [Upper] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=processToken(token).upper()
                else:
                    raise EInvalidExpression(f'Missing <value> argument for [Upper] function{NL}{tokens.inText()}')

                token=tokens.next()
            elif tokenName == 'Capitalize':
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid <value> argument type for [Capitalize] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=processToken(token).capitalize()
                else:
                    raise EInvalidExpression(f'Missing <value> argument for [Capitalize] function{NL}{tokens.inText()}')

                token=tokens.next()
            elif tokenName == 'Camelize':
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid <value> argument type for [Camelize] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=processToken(token).title()
                else:
                    raise EInvalidExpression(f'Missing <value> argument for [Camelize] function{NL}{tokens.inText()}')

                token=tokens.next()
            elif tokenName == 'Replace':
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid <value> argument type for [Replace] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=processToken(token)
                else:
                    raise EInvalidExpression(f'Missing <value> argument for [Replace] function{NL}{tokens.inText()}')

                find=0
                replace=0

                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                    find=processToken(token)
                elif not token or token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Missing <search> argument for [Replace] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                else:
                    raise EInvalidExpression(f'Invalid <search> argument for [Replace] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')


                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                    replace=processToken(token)
                elif not token or token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Missing <replace> argument for [Replace] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                else:
                    raise EInvalidExpression(f'Invalid <replace> argument for [Replace] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')

                returned=returned.replace(find, replace)
                token=tokens.next()
            elif tokenName == 'Regex':
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid <value> argument type for [Regex] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=processToken(token)
                else:
                    raise EInvalidExpression(f'Missing <value> argument for [Regex] function{NL}{tokens.inText()}')

                find=""
                replace=None

                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.STRING:
                    find=processToken(token)

                    if not regExIsValid(find):
                        raise EInvalidExpression(f'Invalid <pattern> argument for [Regex] function{NL}Expected argument must be a valid regular expression STRING{NL}{tokens.inText()}')
                elif not token or token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Missing <pattern> argument for [Regex] function{NL}Expected argument must be a regular expression STRING{NL}{tokens.inText()}')
                else:
                    raise EInvalidExpression(f'Invalid <pattern> argument for [Regex] function{NL}Expected argument must be a regular expression STRING{NL}{tokens.inText()}')

                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                    replace=processToken(token)
                    token=tokens.next()
                elif token and token.type() != BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Invalid <replace> argument for [Regex] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')

                terminatorMissing='<replace>'

                if replace is None:
                    # return found value(s)
                    if result:=re.findall(find, returned, re.IGNORECASE):
                        returned=''.join([value for value in result if not value is None])
                else:
                    returned=re.sub(find, re.sub(r"\$", "\\\\",  replace,flags=re.IGNORECASE), returned, flags=re.IGNORECASE)
            elif tokenName == 'Sub':
                # returned=text to process
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid <value> argument type for [Sub] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=processToken(token)
                else:
                    raise EInvalidExpression(f'Missing <value> argument for [Sub] function{NL}{tokens.inText()}')

                start=0
                length=0

                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.NUMBER:
                    start=int(token.text())
                    if start>0:
                        start-=1
                elif token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCO_NUM:
                    start=processToken(token)
                    if start>0:
                        start-=1
                elif not token or token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Missing <start> argument for [Sub] function{NL}Expected argument must be a NUMBER, a NUMBER FUNCTION{NL}{tokens.inText()}')
                else:
                    raise EInvalidExpression(f'Invalid <start> argument for [Sub] function{NL}Expected argument must be a NUMBER, a NUMBER FUNCTION{NL}{tokens.inText()}')

                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.NUMBER:
                    length=int(token.text())
                    token=tokens.next()
                elif token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCO_NUM:
                    length=processToken(token)
                    token=tokens.next()
                elif token and token.type() != BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Invalid <length> argument for [Sub] function{NL}Expected argument must be a NUMBER, a NUMBER FUNCTION{NL}{tokens.inText()}')

                terminatorMissing='<length>'

                if length!=0:
                    returned=returned[start:(start+length)]
                else:
                    returned=returned[start:]
            elif tokenName == 'Index':
                # returned=text to process
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid <value> argument type for [Index] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=processToken(token)
                else:
                    raise EInvalidExpression(f'Missing <value> argument for [Index] function{NL}{tokens.inText()}')

                separator=''
                index=0

                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                    separator=processToken(token)
                elif not token or token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Missing <separator> argument for [Index] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                else:
                    raise EInvalidExpression(f'Invalid <separator> argument for [Index] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')

                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.NUMBER:
                    index=int(token.text())
                elif token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCO_NUM:
                    index=processToken(token)
                elif not token or token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Missing <index> argument for [Index] function{NL}Expected argument must be a NUMBER, a NUMBER FUNCTION{NL}{tokens.inText()}')
                else:
                    raise EInvalidExpression(f'Invalid <index> argument for [Index] function{NL}Expected argument must be a NUMBER, a NUMBER FUNCTION{NL}{tokens.inText()}')

                try:
                    if index>1:
                        index-=1
                    returned=returned.split(separator)[index]
                except Exception as e:
                    returned=''
                token=tokens.next()
            elif tokenName == 'Len':
                token=tokens.next()
                if processTokenFuncIsArg(token):
                    if not token.type() in (BCFileManipulateNameLanguageDef.ITokenType.STRING, BCFileManipulateNameLanguageDef.ITokenType.KW, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR):
                        raise EInvalidExpression(f'Invalid argument type for [Len] function{NL}Expected argument must be a STRING, a KEYWORD, a STRING FUNCTION{NL}{tokens.inText()}')
                    returned=len(processToken(token))
                else:
                    raise EInvalidExpression(f'Missing argument for [Len] function{NL}{tokens.inText()}')

                adjustment=0
                token=processTokenFuncGetNextArg(tokenName)
                if token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.NUMBER:
                    adjustment=int(token.text())
                    token=tokens.next()
                elif token and token.type() == BCFileManipulateNameLanguageDef.ITokenType.FUNCO_NUM:
                    adjustment=processToken(token)
                    token=tokens.next()
                elif token and token.type() != BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                    raise EInvalidExpression(f'Invalid <adjustment> argument for [Len] function{NL}Expected argument must be a NUMBER, a NUMBER FUNCTION{NL}{tokens.inText()}')

                terminatorMissing='<length>'

                if adjustment!=0:
                    returned=returned+adjustment


            if not token or token.type() != BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                if terminatorMissing != '':
                    raise EInvalidExpression(f'Missing argument {terminatorMissing} and/or function terminator "]" for [{tokenName}] function{NL}{tokens.inText()}')
                else:
                    raise EInvalidExpression(f'Missing function terminator "]" for [{tokenName}] function{NL}{tokens.inText()}')

            return returned

        def processToken(token):
            # return value for token
            returned = ""

            if token is None:
                return ""

            if token.type() == BCFileManipulateNameLanguageDef.ITokenType.STRING:
                return token.text().strip('"')
            elif token.type() in (BCFileManipulateNameLanguageDef.ITokenType.TEXT, BCFileManipulateNameLanguageDef.ITokenType.NUMBER, BCFileManipulateNameLanguageDef.ITokenType.SPACE):
                return token.text()
            elif token.type() == BCFileManipulateNameLanguageDef.ITokenType.ETEXT:
                return token.text().strip(r'\\')
            elif token.type() == BCFileManipulateNameLanguageDef.ITokenType.KW:
                returned=BCFileManipulateName.parseFileNameKw(file, token.text(), targetPath)
                if callable(kwCallBack):
                    returned=kwCallBack(file, returned)
                return returned
            elif token.type() in (BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_NUM):
                return processTokenFunc(token)
            else:
                return ""

        # Rules to tokenize expression
        if isinstance(tokenizer, Tokenizer):
            cfnTokenizer=tokenizer
        elif BCFileManipulateName.__tokenizer is None:
            BCFileManipulateName.__tokenizer = BCFileManipulateNameLanguageDef().tokenizer()
            cfnTokenizer=BCFileManipulateName.__tokenizer
        else:
            cfnTokenizer=BCFileManipulateName.__tokenizer

        returnedValue = ""
        # need to pre-process pattern to manage counter...
        # 1) replace {counter} keyword by a non-recognized keyword {excludeCounter}
        # 2) replace all keywords by their value as string
        #    Example:
        #       {file:ext} ==> "kra"
        # 3) tokenize
        # 4) process tokens
        # 5) restore {counter} keyword
        # 6) replace all keywords(ie: {counter}) by their value as string
        # 7) cleanup
        #
        # this is mandatory to be able to determinate counter value AFTER everything has been processed (functions applied)
        #
        # but doing this will need to re-tokenize pattern (and this is slow)
        # so apply this method only if a counter have to be calculated

        manageCounter=False

        if not checkOnly:
            if re.search(r"(?i)\{(counter(?::#+)?)\}", pattern):
                manageCounter=True

            if manageCounter:
                # 1)
                pattern=re.sub(r"(?i)\{(counter(?::#+)?)\}", "\x01exclude\\1\x01", pattern)
                # 2)
                pattern=re.sub(r"(?i)(\{[^}]+\})", r'"\1"', pattern)
                pattern=BCFileManipulateName.parseFileNameKw(file, pattern, targetPath)
                if callable(kwCallBack):
                    pattern=kwCallBack(file, pattern)

        # 3)
        tokens = cfnTokenizer.tokenize(pattern)
        # 4)
        # get first token (or None if no tokens)
        try:
            token=tokens.next()
            while not token is None:
                returnedValue+=processToken(token)
                token=tokens.next()
        except Exception as e:
            return (None, f"{e}")

        if manageCounter:
            # 5)
            returnedValue=re.sub(r"(?i)\x01excludecounter(:#+)?\x01", r"{counter\1}", returnedValue)
            # 6)
            returnedValue=BCFileManipulateName.parseFileNameKw(file, returnedValue, targetPath)

            # 7) cleanup
            if not keepInvalidCharacters:
                returnedValue=re.sub(r'[*\\/<>?:;"|]', '', returnedValue)
        return (returnedValue, None)


# ------------------------------------------------------------------------------

class BCBaseFile(object):
    """Base class for directories and files"""

    THUMBTYPE_ICON = 'qicon'
    THUMBTYPE_IMAGE = 'qimage'
    THUMBTYPE_FILENAME = 'filename'     # in this case, return thumbnail file name instead of icon/image

    def __init__(self, fileName):
        """Initialise BCFile"""
        self._fullPathName = os.path.expanduser(fileName)
        self._name = os.path.basename(self._fullPathName)

        # Need to normalize path
        if self._name!='..':
            self._fullPathName=os.path.normpath(self._fullPathName)

        self._path = os.path.dirname(self._fullPathName)
        if os.path.isdir(self._fullPathName) or os.path.isfile(self._fullPathName):
            self._mdatetime = os.path.getmtime(self._fullPathName)
        else:
            self._mdatetime = None
        self._format = BCFileManagedFormat.UNKNOWN
        self._tag = {}
        # a unique Id for BCBaseFile object based on file name
        self.__uuid=BCBaseFile.getUuid(self._fullPathName)

    @staticmethod
    def fullPathNameCmpAsc(f1, f2):
        # compare file for ascending sort
        if f1.fullPathName()>f2.fullPathName():
            return 1
        return -1

    @staticmethod
    def fullPathNameCmpDesc(f1, f2):
        # compare file for descending sort
        if f1.fullPathName()>f2.fullPathName():
            return -1
        return 1

    @staticmethod
    def getUuid(fullPathName):
        return hashlib.sha1(fullPathName.encode()).digest()

    def path(self):
        """Return file path"""
        return self._path

    def name(self):
        """Return file name"""
        return self._name

    def fullPathName(self):
        """Return full file path/name"""
        return self._fullPathName

    def baseName(self):
        """Return file name"""
        return self._name

    def format(self):
        """Return file format"""
        return self._format

    def lastModificationDateTime(self, onlyDate=False):
        """Return file last modification time stamp"""
        if onlyDate:
            return strToTs(tsToStr(self._mdatetime, 'd'))
        return self._mdatetime

    def getProperty(self, property):
        """return property value"""
        if property == BCFileProperty.PATH:
            return self._path
        elif property == BCFileProperty.FULL_PATHNAME:
            return self._fullPathName
        elif property == BCFileProperty.FILE_NAME:
            return self._name
        elif property == BCFileProperty.FILE_FORMAT:
            return self._format
        elif property == BCFileProperty.FILE_DATE:
            return self._mdatetime
        elif isinstance(property, BCFileProperty):
            return None
        else:
            raise EInvalidType('Given `property` must be a valid <BCFileProperty>')

    def tag(self, key):
        """Return tag value

        If no tag exist for given key, return None
        """
        if key in self._tag:
            return self._tag[key]
        return None

    def setTag(self, key, value):
        """Set tag value"""
        self._tag[key] = value

    def icon(self):
        """return system icon for file"""
        return BCFileIcon.get(self._fullPathName)

    def thumbnail(self, size=None, thumbType=None, icon=None):
        """return system icon for file"""
        if size is None or not isinstance(size, BCFileThumbnailSize):
            size = BCFile.thumbnailCacheDefaultSize()

        # that's not the best way to do this
        if not isinstance(icon, QIcon):
            # generate icon from file
            icon = BCFileIcon.get(self._fullPathName)

        if thumbType is None or thumbType==BCBaseFile.THUMBTYPE_IMAGE:
            return icon.pixmap(size.size(QSize)).toImage()
        elif thumbType==BCBaseFile.THUMBTYPE_ICON:
            return icon
        else:
            # BCBaseFile.THUMBTYPE_FILENAME
            # get pixmap of icon
            thumbnailImg = icon.pixmap(size.size(QSize)).toImage()

            ptrBits = thumbnailImg.constBits()
            ptrBits.setsize(thumbnailImg.byteCount())

            # calculate hash on pixmap
            fileHash = hashlib.blake2b(digest_size=32)
            fileHash.update(ptrBits)
            hash=fileHash.hexdigest()

            thumbnailFile = os.path.join(BCFile.thumbnailCacheDirectory(size), hash)

            if not os.path.isfile(thumbnailFile):
                # generate thumbnail file
                try:
                    thumbnailImg.save(thumbnailFile, quality=BCFile.thumbnailCacheCompression())
                except Exception as e:
                    Debug.print('[BCBaseFile.thumbnail] Unable to save thumbnail in cache {0}: {1}', thumbnailFile, f"{e}")

            return thumbnailFile

    def permissions(self):
        """Return permission as rwx------ string"""
        if sys.platform == 'linux':
            octalPerm = oct(os.stat(self._fullPathName)[0])[-3:]
            # https://stackoverflow.com/a/59925828
            returned = ""
            letters = [(4, "r"), (2, "w"), (1, "x")]
            for permission in [int(n) for n in f"{octalPerm}"]:
                for value, letter in letters:
                    if permission >= value:
                        returned += letter
                        permission -= value
                    else:
                        returned += "-"
            return returned
        return ''

    def ownerGroup(self):
        """return a tuple (owner, group) names (if linux) otherwise ('', '') """
        if sys.platform == 'linux':
            fs = os.stat(self._fullPathName)
            return (pwd.getpwuid(fs.st_uid).pw_name, grp.getgrgid(fs.st_uid).gr_name)
        return ('', '')

    def hash(self, method):
        """Return hash for file"""
        if not method in ('md5', 'sha1', 'sha256', 'sha512'):
            raise EInvalidValue('Given `method` value must be "md5", "sha1", "sha256" or "sha512"')

        if method=='md5':
            return '0' * 32
        elif method=='sha1':
            return '0' * 40
        elif method=='sha256':
            return '0' * 64
        elif method=='sha512':
            return '0' * 128

    def uuid(self):
        """Return UUID defined for BCBaseFile"""
        return self.__uuid


class BCDirectory(BCBaseFile):
    """Provides common properties with BCFile to normalize way directory & file
    informations are managed

    Note: BCDirectory is not aimed to be instancied directly and to improve execution
          times there's no real control about file (is it a directory? does it exists?)
          consider that this kind of controls must be made before
    """

    def __init__(self, fileName):
        super(BCDirectory, self).__init__(fileName)
        self._format = BCFileManagedFormat.DIRECTORY

    def __repr__(self):
        """Format internal representation"""
        return f'<BCDirectory({self._path}, {self._name})>'

    def size(self):
        """Return directory size"""
        return 0

    def isEmpty(self):
        """Return True if directory is empty, otherwise False"""
        return len(os.listdir(self._fullPathName))==0


class BCMissingFile(BCBaseFile):
    """A missing file"""

    def __init__(self, fileName):
        """Initialise BCFile"""
        super(BCMissingFile, self).__init__(fileName)
        self._fullPathName = os.path.expanduser(fileName)
        self._name = os.path.basename(self._fullPathName)
        self._path = os.path.dirname(self._fullPathName)
        self._mdatetime = None
        self._format = BCFileManagedFormat.MISSING

        self.__baseName, self.__extension = os.path.splitext(fileName)

        if reResult:=re.match(r'^\.\d+'+Krita.instance().readSetting('', 'backupfilesuffix', '~').replace('.', r'\.'), self.__extension):
            # seems to be an extension for a backup file with number
            baseName, originalExtension = os.path.splitext(self.__baseName)
            self.__extension=f'{originalExtension}{self.__extension}'

        self.__baseName = os.path.basename(self.__baseName)
        self.__extension=self.__extension.lower()

    def baseName(self):
        return self.__baseName

    def lastModificationDateTime(self, onlyDate=False):
        """Return file last modification time stamp"""
        return None

    def icon(self):
        """return system icon for file"""
        return buildIcon('pktk:warning')

    def thumbnail(self, size=None, thumbType=None, icon=None):
        """return system icon for file"""
        return super(BCMissingFile, self).thumbnail(size, thumbType, buildIcon('pktk:warning'))

    def permissions(self):
        """Return permission as rwx------ string"""
        return '-'

    def ownerGroup(self):
        """return a tuple (owner, group) names (if linux) otherwise ('', '') """
        return ('', '')

    def size(self):
        """Return file size"""
        return 0

    def extension(self, dot=True):
        """Return file extension"""
        if dot:
            return self.__extension
        else:
            return self.__extension[1:]

    def imageSize(self):
        """Return file image size"""
        return QSize(-1, -1)

    def qHash(self):
        """Return file quick hash"""
        return ''

    def readable(self):
        """Return True if file is readable"""
        return False


class BCFile(BCBaseFile):
    """Provide an easy way to work with images files:
    - File properties (name, path, size, date)
    - Image information (format, size)
    - Image content (jpeg, png, kra)
    - Image thumbnail (with cache)

    Note: BCFile is not aimed to be instancied directly and to improve execution
          times there's no real control about file (is it a file? does it exists?)
          consider that this kind of controls must be made before
    """
    # TODO: if file timestamp is modified, regenerate infor + thumbnail

    __CHUNK_SIZE = 8192

    __BC_CACHE_PATH = ''
    __THUMBNAIL_CACHE_FMT = BCFileThumbnailFormat.PNG
    __THUMBNAIL_CACHE_DEFAULTSIZE = BCFileThumbnailSize.MEDIUM

    __INITIALISED = False

    @staticmethod
    def initialiseCache(bcCachePath=None, thumbnailCacheDefaultSize=None):
        """Initialise thumbnails cache properties


        By default, cache will be defined into user cache directory
        If `bcCachePath` is provided, it will define the thumbnail cache directory to use

        If directory doesn't exist, it will be created
        """

        BCFile.setCacheDirectory(bcCachePath)
        BCFile.setThumbnailCacheDefaultSize(thumbnailCacheDefaultSize)

        BCFile.__INITIALISED = True


    def __init__(self, fileName, strict=False, bcFileCache=None):
        """Initialise BCFile

        If strict is True, check only files for which extension is known
        If strict is False, try to determinate file format even if there's no extension
        """
        super(BCFile, self).__init__(fileName)
        self._format = BCFileManagedFormat.UNKNOWN
        self.__size = 0
        self.__imgSize = QSize(-1, -1)
        self.__qHash = ''
        self.__readable = False
        self.__extension = ''
        self.__baseName = ''

        if not isinstance(bcFileCache, BCFileCache):
            self.__bcFileCache=BCFileCache.globalInstance()
        else:
            self.__bcFileCache=bcFileCache

        # hash in cache
        self.__hashCache={
                'md5': None,
                'sha1': None,
                'sha256': None,
                'sha512': None
            }
        self.__metadata={}

        if not BCFile.__INITIALISED:
            raise EInvalidStatus('BCFile class is not initialised')

        self.__initFromFileName(fileName, strict)

    # region: miscellaneous ----------------------------------------------------

    def __repr__(self):
        """Format internal representation"""
        return f'<BCFile({self.__readable}, {self._format}, {self._path}, {self._name}, {self.__size}, {self.__qHash}, {self.__imgSize})>'

    # endregion: miscellaneous -------------------------------------------------


    # region: initialisation ---------------------------------------------------

    def __initFromFileName(self, fileName, strict):
        """Initialize file information from given full file name

        BCFile will:
        - Check if file exists
        - Read file property (format, file size, image dimension, qHash)

        If strict is True, check only files for which extension is known
        If strict is False, try to determinate file format even if there's no extension
        """
        #if os.path.isfile(fileName):
        self.__readable = True

        self.__baseName, self.__extension = os.path.splitext(fileName)

        if reResult:=re.match(r'^\.\d+'+Krita.instance().readSetting('', 'backupfilesuffix', '~').replace('.', r'\.'), self.__extension):
            # seems to be an extension for a backup file with number
            baseName, originalExtension = os.path.splitext(self.__baseName)
            self.__extension=f'{originalExtension}{self.__extension}'

        self.__baseName = os.path.basename(self.__baseName)
        self.__extension=self.__extension.lower()
        self.__size = os.path.getsize(self._fullPathName)

        if strict and not BCFileManagedFormat.inExtensions(self.__extension, True, False):
            self.__readable = True
            return
        elif BCFileManagedFormat.inExtensions(self.__extension, True, True):
            # update qHash for file
            self.__calculateQuickHash()

            if self.__readMetaCacheFile():
                # data has been read from cache file; exit
                return

            # can't read from cache, read file...
            imageReader = QImageReader(self._fullPathName)

            if imageReader.canRead():
                self._format = bytes(imageReader.format()).decode().lower()
                if self._format == BCFileManagedFormat.JPG:
                    # harmonize file type
                    self._format = BCFileManagedFormat.JPEG
            else:
                self._format = self.__extension[1:]    # remove '.'

            if self._format == BCFileManagedFormat.KRA:
                # in case of Qt readed is able to determinate Krita file, it can't made
                # distinction between KRA and KRZ
                # then need to check
                if self.__extension[1:].lower()==BCFileManagedFormat.KRZ:
                    self._format = BCFileManagedFormat.KRZ

            if self._format in BCFileManagedFormat.list(False):
                # Use image reader as fallback
                self.__imgSize = imageReader.size()

            if self._format==BCFileManagedFormat.PNG:
                cacheData=self.__readMetaDataPng(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData and cacheData['width']!=0 and cacheData['height']!=0:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                else:
                    cacheData['width']=self.__imgSize.width()
                    cacheData['height']=self.__imgSize.height()
            elif self._format in (BCFileManagedFormat.JPG, BCFileManagedFormat.JPEG):
                cacheData=self.__readMetaDataJpeg(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData and cacheData['width']!=0 and cacheData['height']!=0:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                else:
                    cacheData['width']=self.__imgSize.width()
                    cacheData['height']=self.__imgSize.height()
            elif self._format==BCFileManagedFormat.SVG:
                cacheData={
                        'width': self.__imgSize.width(),
                        'height': self.__imgSize.height()
                    }
            elif self._format==BCFileManagedFormat.GIF:
                cacheData=self.__readMetaDataGif(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData and cacheData['width']!=0 and cacheData['height']!=0:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                else:
                    cacheData['width']=self.__imgSize.width()
                    cacheData['height']=self.__imgSize.height()
            elif self._format==BCFileManagedFormat.BMP:
                cacheData=self.__readMetaDataBmp(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData and cacheData['width']!=0 and cacheData['height']!=0:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                else:
                    cacheData['width']=self.__imgSize.width()
                    cacheData['height']=self.__imgSize.height()
            elif self._format==BCFileManagedFormat.WEBP:
                cacheData=self.__readMetaDataWebP(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData and cacheData['width']!=0 and cacheData['height']!=0:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                else:
                    cacheData['width']=self.__imgSize.width()
                    cacheData['height']=self.__imgSize.height()
            elif self._format == BCFileManagedFormat.PSD:
                cacheData = self.__readMetaDataPsd(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
            elif self._format == BCFileManagedFormat.XCF:
                cacheData = self.__readMetaDataXcf(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
            elif self._format == BCFileManagedFormat.KRA or BCFileManagedFormat.isExtension(self.__extension, BCFileManagedFormat.KRA, True):
                # Image reader can't read file...
                # or some file type (kra, ora) seems to not properly be managed
                # by qimagereader
                cacheData = self.__readMetaDataKra(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                    self._format = BCFileManagedFormat.KRA
            elif self._format == BCFileManagedFormat.KRZ or BCFileManagedFormat.isExtension(self.__extension, BCFileManagedFormat.KRZ, True):
                # Image reader can't read file...
                # or some file type (kra, ora) seems to not properly be managed
                # by qimagereader
                cacheData = self.__readMetaDataKra(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                    self._format = BCFileManagedFormat.KRZ
            elif self._format == BCFileManagedFormat.ORA or BCFileManagedFormat.isExtension(self.__extension, BCFileManagedFormat.ORA, True):
                # Image reader can't read file...
                # or some file type (kra, ora) seems to not properly be managed
                # by qimagereader
                cacheData = self.__readMetaDataOra(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                    self._format = BCFileManagedFormat.ORA
            elif self.__extension == '':
                # don't know file format by ImageReader or extension...
                # and there's no extension
                # try Kra..
                cacheData = self.__readMetaDataKra(False)
                if cacheData and 'width' in cacheData and 'height' in cacheData:
                    self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                    self._format = BCFileManagedFormat.KRA
                else:
                    # try ora
                    cacheData = self.__readMetaDataOra(False)
                    if cacheData and 'width' in cacheData and 'height' in cacheData:
                        self.__imgSize = QSize(cacheData['width'], cacheData['height'])
                        self._format = BCFileManagedFormat.ORA
                    else:
                        # Unable to determinate format
                        self.__readable = False

            cacheData['format']=self._format

            # add some extra metadata information
            cacheData[BCFileProperty.IMAGE_PIXELS.value]=self.__imgSize.width()*self.__imgSize.height()
            if self.__imgSize.height()!=0:
                cacheData[BCFileProperty.IMAGE_RATIO.value]=self.__imgSize.width()/self.__imgSize.height()
            else:
                cacheData[BCFileProperty.IMAGE_RATIO.value]=0
            self.__writeMetaCacheFile(cacheData)
        else:
            self.__readable = False

    # endregion: initialisation ------------------------------------------------


    # region: utils ------------------------------------------------------------

    def __readMetaCacheFile(self):
        """Calculate meta cache file name

        If file exists, load it and return True
        Otherwise return False
        """
        if self.__bcFileCache and self.__qHash!='':
            contentAsDict=self.__bcFileCache.getMetadata(self.__qHash)
            if contentAsDict:
                # meta cache file loaded
                # get values
                if not ('format' in contentAsDict and
                        'width' in contentAsDict and
                        'height' in contentAsDict):
                    # invalid content?
                    return False

                self.__imgSize = QSize(contentAsDict['width'], contentAsDict['height'])
                self._format=contentAsDict["format"]
                self.__metadata=contentAsDict

                return True

        return False


    def __writeMetaCacheFile(self, dataAsDict):
        """Calculate meta cache file name

        If file exists, load it and return True
        Otherwise return False
        """
        self.__metadata=dataAsDict

        if self.__bcFileCache is None:
            return

        try:
            if 'iccProfile' in dataAsDict or 'document.referenceImages.data' in dataAsDict:
                # exclude extradata from cache (can be heavy data)
                dataAsDictToPass=copy.copy(dataAsDict)

                if 'iccProfile' in dataAsDictToPass:
                    dataAsDictToPass['iccProfile']=b''
                if 'document.referenceImages.data' in dataAsDict:
                    dataAsDictToPass['document.referenceImages.data']=[]
            else:
                dataAsDictToPass=dataAsDict

            return self.__bcFileCache.setMetadata(self.__qHash, dataAsDictToPass)
        except Exception as e:
            # can't write meta cache file
            Debug.print('Unable to write meta cache data {0}: {1}', self.__qHash, f"{e}")
            return False

        return True


    def __readICCData(self, iccData):
        """Read an ICC byte array and return ICC profile information

        ICC specifications: http://www.color.org/specification/ICC1v43_2010-12.pdf
                            http://www.color.org/specification/ICC.2-2018.pdf
                            http://www.littlecms.com/LittleCMS2.10%20API.pdf
                            http://www.color.org/ICC_Minor_Revision_for_Web.pdf
        """
        def decode_mluc(data):
            """Decode MLUC (multiLocalizedUnicodeType) tag type

                Byte position           Field length    Content                                                     Encoded
                0 to 3                  4               ‘mluc’ (0x6D6C7563) type signature
                4 to 7                  4               Reserved, shall be set to 0
                8 to 11                 4               Number of records (n)                                       uInt32Number
                12 to 15                4               Record size: the length in bytes of every record.           0000000Ch
                                                        The value is 12.
                16 to 17                2               First record language code: in accordance with the          uInt16Number
                                                        language code specified in ISO 639-1
                18 to 19                2               First record country code: in accordance with the           uInt16Number
                                                        country code specified in ISO 3166-1
                20 to 23                4               First record string length: the length in bytes of          uInt32Number
                                                        the string
                24 to 27                4               First record string offset: the offset from the start       uInt32Number
                                                        of the tag to the start of the string, in bytes
                28 to 28+[12(n−1)]−1    12(n−1)         Additional records as needed
                (or 15+12n)

                28+[12(n−1)]            Variable        Storage area of strings of Unicode characters
                (or 16+12n) to end

                return a dict (key=lang, value=text)
            """
            returned = {}
            if data[0:4] != b'mluc':
                return returned

            nbRecords = struct.unpack('!I', data[8:12])[0]
            if nbRecords == 0:
                return returned

            szRecords = struct.unpack('!I', data[12:16])[0]
            if szRecords != 12:
                # if records size is not 12, it's not normal??
                return returned

            for index in range(nbRecords):
                offset = 16 + index * szRecords
                try:
                    langCode = data[offset:offset+2].decode()
                    countryCode = data[offset+2:offset+4].decode()

                    txtSize = struct.unpack('!I', data[offset+4:offset+8])[0]
                    txtOffset = struct.unpack('!I', data[offset+8:offset+12])[0]

                    text = data[txtOffset:txtOffset+txtSize].decode('utf-16be')

                    returned[f'{langCode}-{countryCode}'] = text.rstrip('\x00')
                except Exception as a:
                    Debug.print('[BCFile...decode_mluc] Unable to decode MLUC: {0}', f"{e}")
                    continue
            return returned

        def decode_text(data):
            """Decode TEXT (multiLocalizedUnicodeType) tag type

                Byte position           Field length    Content                                                     Encoded
                0 to 3                  4               ‘text’ (74657874h) type signature
                4 to 7                  4               Reserved, shall be set to 0
                8 to end                Variable        A string of (element size 8) 7-bit ASCII characters

                return a dict (key='en-US', value=text)
            """
            returned = {}
            if data[0:4] != b'text':
                return returned

            try:
                returned['en-US'] = data[8:].decode().rstrip('\x00')
            except Exception as a:
                Debug.print('[BCFile...decode_mluc] Unable to decode TEXT: {0}', f"{e}")

            return returned

        def decode_desc(data):
            """Decode DESC (textDescriptionType) tag type [deprecated]

                Byte position           Field length    Content                                                     Encoded
                0..3                    4               ‘desc’ (64657363h) type signature
                4..7                    4               reserved, must be set to 0
                8..11                   4               ASCII invariant description count, including terminating    uInt32Number
                                                        null (description length)
                12..n-1                                 ASCII invariant description                                 7-bit ASCII

                ignore other data

                return a dict (key='en-US', value=text)
            """
            returned = {}
            if data[0:4] != b'desc':
                return returned

            try:
                txtLen = struct.unpack('!I', data[8:12])[0]
                returned['en-US'] = data[12:11+txtLen].decode().rstrip('\x00')
            except Exception as e:
                Debug.print('[BCFile...decode_mluc] Unable to decode DESC: {0}', f"{e}")

            return returned

        returned = {
            'iccProfileName': {},
            'iccProfileCopyright': {},
        }

        nbTags=struct.unpack('!I', iccData[128:132])[0]

        for i in range(nbTags):
            tData = iccData[132+i * 12:132+(i+1)*12]

            tagId = tData[0:4]
            offset = struct.unpack('!I', tData[4:8])[0]
            size = struct.unpack('!I', tData[8:12])[0]

            data = iccData[offset:offset+size]

            if tagId == b'desc':
                # description (color profile name)
                if data[0:4] == b'mluc':
                    returned['iccProfileName']=decode_mluc(data)
                elif data[0:4] == b'text':
                    returned['iccProfileName']=decode_text(data)
                elif data[0:4] == b'desc':
                    returned['iccProfileName']=decode_desc(data)
            elif tagId == b'cprt':
                # copyright
                if data[0:4] == b'mluc':
                    returned['iccProfileCopyright']=decode_mluc(data)
                elif data[0:4] == b'text':
                    returned['iccProfileCopyright']=decode_text(data)
                elif data[0:4] == b'desc':
                    returned['iccProfileCopyright']=decode_desc(data)
        return returned


    def __readArchiveDataFile(self, file, source=None):
        """Read an archive file (.kra, .ora) file and return data from archive

        The function will unzip the given `file` and return it

        If `source` is provided, use it a zip file source to open

        return None if not able to read Krita file
        """
        if not self.__readable:
            # file must exist
            return None

        if source is None:
            source = self._fullPathName

        try:
            archive = zipfile.ZipFile(source, 'r')
        except Exception as e:
            # can't be read (not exist, not a zip file?)
            self.__readable = False
            if re.match(fr"\.(kra|krz|ora)({BCFileManagedFormat.backupSuffixRe()})?$", source):
                Debug.print('[BCFile.__readArchiveDataFile] Unable to open file {0}: {1}', self._fullPathName, f"{e}")
            return None

        try:
            imgfile = archive.open(file)
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            archive.close()
            Debug.print('[BCFile.__readArchiveDataFile] Unable to find "{2}" in file {0}: {1}', self._fullPathName, f"{e}", file)
            return None

        try:
            data = imgfile.read()
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            imgfile.close()
            archive.close()
            Debug.print('[BCFile.__readArchiveDataFile] Unable to read "{2}" in file {0}: {1}', self._fullPathName, f"{e}", file)
            return None

        imgfile.close()
        archive.close()

        return data


    def __calculateQuickHash(self):
        """Calculate a 'quick' hash on file with SHA256 method
        (fastest than Blake2b)

        To improve speedup on hash calculation, read only first and last 8.00KB from file
        => most of file have their image properties (size and other technical information) at the beginning of file
           + use the last 8KB to reduce risk of colision

          Risk for collision is not null, but tested on ~12000 different images from 16KB to 160MB, nothing bad happened
          Hash calculation for 12000 files (~114.00GB) take ~2.70s, that's seems good enough (hope nobody have so much image
          files in the same directory ^_^')
        """
        if self.__readable:
            try:
                with open(self._fullPathName, "rb") as fileHandle:
                    # digest = 256bits (32Bytes)
                    fileHash = hashlib.sha256()

                    # file size is the first part of hash (ie: file size changed then ensure that hash is not the same event if 1st/last 8KB of file are the same)
                    fileHash.update(f"{self.__size}".encode())

                    # read 1st 8.00KB and update hash
                    fileHash.update(fileHandle.read(BCFile.__CHUNK_SIZE))

                    if self.__size > BCFile.__CHUNK_SIZE:
                        # file size is greater than 8.00KB, read last 8.00KB and update hash
                        fileHandle.seek(self.__size - BCFile.__CHUNK_SIZE)
                        fileHash.update(fileHandle.read(BCFile.__CHUNK_SIZE))

                    self.__qHash = fileHash.hexdigest()
            except Exception as e:
                Debug.print('[BCFile.__calculateQuickHash] Unable to calculate hash file {0}: {1}', self._fullPathName, f"{e}")
                self.__qHash = ''
        else:
            self.__qHash = ''


    def __readKraImage(self):
        """Return Krita file image

        The function only unzip the mergedimage.png to speedup the process

        return None if not able to read Krita file
        return a QImage() otherwise
        """
        if not self.__readable:
            # file must exist
            return None


        try:
            archive = zipfile.ZipFile(self._fullPathName, 'r')
        except Exception as e:
            # can't be read (not exist, not a zip file?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImage] Unable to open file {0}: {1}', self._fullPathName, f"{e}")
            return None

        pngFound = True

        try:
            imgfile = archive.open('mergedimage.png')
        except Exception as e:
            pngFound = False

        if not pngFound:
            try:
                # fallback: try to read preview file
                imgfile = archive.open('preview.png')
                pngFound = True
            except Exception as e:
                pngFound = False

        if not pngFound:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            archive.close()
            Debug.print('[BCFile.__readKraImage] Unable to find "mergedimage.png" in file {0}', self._fullPathName)
            return None

        try:
            image = imgfile.read()
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            imgfile.close()
            archive.close()
            Debug.print('[BCFile.__readKraImage] Unable to read "mergedimage.png" in file {0}: {1}', self._fullPathName, f"{e}")
            return None

        imgfile.close()
        archive.close()

        try:
            returned = QImage()
            returned.loadFromData(image)
        except Exception as e:
            # can't be read (not png?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImage] Unable to parse "mergedimage.png" in file {0}: {1}', self._fullPathName, f"{e}")
            return None

        return returned


    def __readOraImage(self):
        """Return OpenRaster file image

        The function only unzip the Thumbnail/thumbnail.png to speedup the process
        Note: this file is a thumbnail and might have a big reduced size...

        return None if not able to read OpenRaster file
        return a QImage() otherwise
        """
        if not self.__readable:
            # file must exist
            return None

        try:
            archive = zipfile.ZipFile(self._fullPathName, 'r')
        except Exception as e:
            # can't be read (not exist, not a zip file?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImage] Unable to open file {0}: {1}', self._fullPathName, f"{e}")
            return None

        try:
            # try to read merged image preview
            imgfile = archive.open('mergedimage.png')
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            imgfile = None


        if imgfile is None:
            # ora file is an old ora file without mergedimage.png
            # try to read thumbnail file
            try:
                imgfile = archive.open('Thumbnails/thumbnail.png')
            except Exception as e:
                # can't be read (not exist, not a Kra file?)
                self.__readable = False
                archive.close()
                Debug.print('[BCFile.__readOraImage] Unable to find "thumbnail.png" in file {0}: {1}', self._fullPathName, f"{e}")
                return None


        try:
            image = imgfile.read()
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            imgfile.close()
            archive.close()
            Debug.print('[BCFile.__readOraImage] Unable to read "thumbnail.png" in file {0}: {1}', self._fullPathName, f"{e}")
            return None

        imgfile.close()
        archive.close()

        try:
            returned = QImage()
            returned.loadFromData(image)
        except Exception as e:
            # can't be read (not png?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImage] Unable to parse "thumbnail.png" in file {0}: {1}', self._fullPathName, f"{e}")
            return None

        return returned


    def __readMetaDataJpeg(self, fromCache=True, getExtraData=False):
        """
        Read metadata from JPEG file

        https://exiftool.org/TagNames/JPEG.html
        """
        def readMarkerSegment(fHandle):
            """Read a marker segment and return it
            {
                'valid': <bool>,
                'size': <int>,
                'id': <int>,
                'data': bytes
            }
            If marker segment can't be read, size = 0 and data is None
            """
            returned = {
                    'valid': True,
                    'size': 0,
                    'id': '',
                    'data': None
                }
            try:
                returned['id'] = fHandle.read(2)
                returned['size'] = struct.unpack('!H', fHandle.read(2))[0]
                returned['data'] = fHandle.read(returned['size'] - 2)
            except:
                returned['valid']=False

            if returned['id'][0] != 0xFF:
                returned['valid']=False

            return returned

        def decodeChunk_APP0(markerSegment):
            """Decode APP0 marker:

            {
                'resolutionX': (<float>, <str>),
                'resolutionY': (<float>, <str>),
                'resolution': <str>
            }
            """
            returned = {
                'resolutionX': (0, 'Unknown'),
                'resolutionY': (0, 'Unknown'),
                'resolution': ''
            }

            if not markerSegment['data'][0:5] in [b'JFIF\x00', b'JFXX\x00']:
                # not a valid segment
                return returned

            if markerSegment['data'][0:5] == b'JFIF\x00':
                # 0: no unit
                # 1: pixels per inch
                # 2: pixels per centimer
                unit = markerSegment['data'][7]

                ppX = float(struct.unpack('!H', markerSegment['data'][8:10])[0])
                ppY = float(struct.unpack('!H', markerSegment['data'][10:12])[0])


                if unit > 0:
                    # unit = 1: ppi
                    if unit == 2:
                        # unit in meter
                        # convert in pixels per inches
                        ppX*=2.54
                        ppY*=2.54

                    returned['resolutionX'] = (ppX, f'{ppX:.3f}ppi')
                    returned['resolutionY'] = (ppY, f'{ppY:.3f}ppi')

                    if ppX == ppY:
                        returned['resolution'] = f'{ppX:.3f}ppi'
                    else:
                        returned['resolution'] = f'{ppX:.3f}x{ppY:.3f}ppi'
                else:
                    returned['resolutionX'] = (ppX, f'{ppX:.2f}')
                    returned['resolutionY'] = (ppY, f'{ppY:.2f}')

                    if ppX == ppY:
                        returned['resolution'] = f'{ppX:.2f}'
                    else:
                        returned['resolution'] = f'{ppX:.2f}x{ppY:.2f}'

            return returned

        def decodeChunk_APP2(markerSegment, returned, getExtraData):
            """Decode APP2 marker:

            {
                'iccProfileName': <str>,
                'iccProfileCopyright': <str>
                'iccProfile': <byte str>
            }
            """
            if markerSegment['data'][0:12] == b'ICC_PROFILE\x00':
                # is an ICC profile
                if not 'iccProfile' in returned:
                    # not yet initialised (first chunk): create empty value
                    returned['iccProfile'] = b''

                chunkNum = int(markerSegment['data'][12])
                chunkTotal = int(markerSegment['data'][13])

                returned['iccProfile']+=markerSegment['data'][14:]

                if chunkNum == chunkTotal:
                    tmp = self.__readICCData(returned['iccProfile'])
                    if getExtraData==False:
                        # don't want icc profile data (for performance, memory, ... don't need it)
                        returned['iccProfile']=b'Y'
                    returned.update(tmp)
            return returned

        def decodeChunk_APP14(markerSegment):
            """Decode APP14 marker:

            {
                'bitDepth': (<int>, <str>),
                'colorType': (<int>, <str>)
            }
            """
            returned = {}

            if markerSegment['data'][0:6] == b'Adobe\x00':
                # is a colour encoding
                pass

            return returned

        def decodeChunk_SOFx(markerSegment):
            """Decode SOF0, SOF2 markers:

            {
                'colorType': (<int>, <str>)
            }
            """
            __COLOR_TYPE = {
                    1: 'Grayscale',
                    3: 'RGB',
                    4: 'CMYK'
                }

            returned={}

            cType = int(markerSegment['data'][5])
            if cType in __COLOR_TYPE:
                returned['colorType']=(cType, __COLOR_TYPE[cType])
            else:
                returned['colorType']=(cType, 'Unknown')

            return returned

        if getExtraData==False and fromCache and not self.__metadata is None:
            return self.__metadata

        # by default
        # - a JPEG is always 8bit
        # - is RGB, unless other encoding is defined
        returned = {
                'bitDepth': (8, '8-bit integer/channel'),
                'colorType': ('RGB', 'RGB')
            }

        with open(self._fullPathName , 'rb') as fHandler:
            # check signature (2 bytes)
            bytes = fHandler.read(2)

            # SOI
            if bytes != b'\xFF\xD8':
                Debug.print('[BCFile.__readMetaDataJpeg] Invalid header: {0}', bytes)
                return returned

            markerSegment = readMarkerSegment(fHandler)
            while markerSegment['valid']:
                if markerSegment['id'] == b'\xFF\xE0':
                    returned.update(decodeChunk_APP0(markerSegment))
                elif markerSegment['id'] == b'\xFF\xE2':
                    returned.update(decodeChunk_APP2(markerSegment, returned, getExtraData))
                elif markerSegment['id'] in [b'\xFF\xC0', b'\xFF\xC2']:
                    returned.update(decodeChunk_SOFx(markerSegment))
                #else:
                #    Debug.print('[BCFile.__readMetaDataJpeg] markerSegment({0}) size: {1} / data: {2}', markerSegment['id'], markerSegment['size'], markerSegment['data'][0:25])

                markerSegment = readMarkerSegment(fHandler)

        return returned


    def __readMetaDataPng(self, fromCache=True, getExtraData=False):
        """Read metadata from PNG file

        PNG specifications: http://www.libpng.org/pub/png/spec/1.2/png-1.2-pdg.html
                            http://www.libpng.org/pub/png/pngsuite.html
        """
        def readChunk(fHandle):
            """Read a chunk and return it as a dictionary
            {
                'size': <int>,
                'id': <str>,
                'data': bytes,
                'crc': <int>
            }
            If chunk can't be read, size = 0 and data is None
            """
            returned = {
                    'valid': True,
                    'size': 0,
                    'id': '',
                    'data': None
                }
            try:
                bytes = fHandle.read(8)
                returned['size'] = struct.unpack('!I', bytes[0:4])[0]
                returned['id'] = bytes[4:].decode()
                if returned['id']!='IDAT':
                    returned['data'] = fHandle.read(returned['size'])
                    # ignore CRC
                    fHandle.seek(4, os.SEEK_CUR)
                else:
                    returned['data'] = fHandle.read(2)
                    # +2 ==> +4 (CRC) -2 (already read data)
                    fHandle.seek(returned['size']+2, os.SEEK_CUR)

                    # skip all IDAT chunks
                    readIDATChunks(fHandle, returned['size']+8)
            except Exception as e:
                Debug.print("Exception {0}: {1}", self._fullPathName, f"{e}")
                returned['valid']=False
            return returned

        def readIDATChunks(fHandle, chunkSize=8196):
            """Skip all IDAT chunks

            Have example of PNG files with 20000 to 60000 IDAT chunks of 8196bytes
            Skip time using this method (on 20~30 files) is reduced from 68seconds to 1.6s
            """
            while True:
                currentPosition=fHandle.tell()
                bufferSize=max(chunkSize*100, 16777216)

                # use memory reader to reduce disk read access
                bytes = BytesRW(fHandle.read(bufferSize))

                size = bytes.readUInt4()
                id = bytes.readStr(4)

                while id=='IDAT':
                    bytes.seek(size+4, os.SEEK_CUR)

                    # +12 = +8 (size + header Id) +4 (CRC)
                    currentPosition+=size+12

                    size = bytes.readUInt4()
                    id = bytes.readStr(4)

                    if bytes.tell()+size>=bufferSize:
                        # there's still IDAT chunk but data buffer is not
                        # complete and need to work on an another data buffer
                        id='_next'

                fHandle.seek(currentPosition, os.SEEK_SET)
                if id!='_next':
                    return

        def decodeChunk_IHDR(chunk):
            """Decode IHDR chunk and return a dictionary with:

            {
                'width': <int>,
                'height': <int>,
                'bitDepth': (<int>, <str),
                'colorType': (<int>, <str>)
                'compressionMethod': <int>,
                'filterMethod': <int>,
                'interlaceMethod': (<int>, <str>)
            }

            width (4 bytes)
            height (4 bytes)
            bit depth (1 byte)
            color type (1 byte)
            compression method (1 byte)
            filter method (1 byte)
            interlace method (1 byte)
            """
            __COLOR_TYPE = {
                    0: 'Grayscale',
                    2: 'RGB',
                    3: 'Indexed palette',
                    4: 'Grayscale with Alpha',
                    6: 'RGB with Alpha'
                }
            __INTERLACE_METHOD = {
                    0: 'No interlace',
                    1: 'Adam7 interlace'
                }

            returned = {
                'width': struct.unpack('!I', chunk['data'][0:4])[0],
                'height': struct.unpack('!I', chunk['data'][4:8])[0],
                'bitDepth': (int(chunk['data'][8]), f"{int(chunk['data'][8])}-bit integer/channel"),
                'colorType': int(chunk['data'][9]),
                'compressionMethod': int(chunk['data'][10]),
                'filterMethod': int(chunk['data'][11]),
                'interlaceMethod': int(chunk['data'][12])
            }
            if returned['colorType'] in __COLOR_TYPE:
                returned['colorType'] = (returned['colorType'], __COLOR_TYPE[returned['colorType']])
            else:
                returned['colorType'] = (returned['colorType'], 'Unknown type')

            if returned['interlaceMethod'] in __INTERLACE_METHOD:
                returned['interlaceMethod'] = (returned['interlaceMethod'], __INTERLACE_METHOD[returned['interlaceMethod']])
            else:
                returned['interlaceMethod'] = (returned['interlaceMethod'], 'Unknown method')
            return returned

        def decodeChunk_PLTE(chunk):
            """Decode PLTE chunk and return a dictionary with:

            {
                'paletteSize': <int>
            }

            Palette size is chunk size divied by 3
            Palette entries (R, B, G) are not returned
            """
            returned = {
                'paletteSize': int(chunk['size']/3)
            }

            return returned

        def decodeChunk_pHYs(chunk):
            """Decode pHYs chunk and return a dictionary with:

            {
                'resolutionX': (<float>, <str>),
                'resolutionY': (<float>, <str>),
                'resolution': <str>
            }

            note: if resolutionX = resolutionY, resolution is defined

            Pixels per unit, X axis: 4 bytes (unsigned integer)
            Pixels per unit, Y axis: 4 bytes (unsigned integer)
            Unit specifier:          1 byte


            """
            returned = {
                'resolutionX': (0, 'Unknown'),
                'resolutionY': (0, 'Unknown'),
                'resolution': ''
            }

            ppX = struct.unpack('!I', chunk['data'][0:4])[0]
            ppY = struct.unpack('!I', chunk['data'][4:8])[0]
            unit = int(chunk['data'][8])

            if unit == 1:
                # unit in meter
                # convert in pixels per inches
                ppX*=0.0254
                ppY*=0.0254

                returned['resolutionX'] = (ppX, f'{ppX:.3f}ppi')
                returned['resolutionY'] = (ppY, f'{ppY:.3f}ppi')

                if ppX == ppY:
                    returned['resolution'] = f'{ppX:.3f}ppi'
                else:
                    returned['resolution'] = f'{ppX:.3f}x{ppY:.3f}ppi'
            else:
                returned['resolutionX'] = (ppX, f'{ppX:.2f}')
                returned['resolutionY'] = (ppY, f'{ppY:.2f}')

                if ppX == ppY:
                    returned['resolution'] = f'{ppX:.2f}'
                else:
                    returned['resolution'] = f'{ppX:.2f}x{ppY:.2f}'


            return returned

        def decodeChunk_IDAT(chunk):
            """Decode IDAT chunk and return a dictionary with:

            {
                'compressionLevel': (<int>, <str>)
            }

            Decode only header of PNG chunk => assume that compression method is 0 (zlib)

            ZLib header: https://stackoverflow.com/questions/9050260/what-does-a-zlib-header-look-like
                         https://tools.ietf.org/html/rfc1950
            """
            __COMPRESSION_LEVEL = {
                    0: 'Lowest compression (level: 1)',
                    1: 'Low compression (level:2 to 5)',
                    2: 'Default compression (level: 6)',
                    3: 'Highest compression (level: 7 to 9)'
                }

            returned = {
                'compressionLevel': (None, '')
            }

            if len(chunk['data'])>=2:
                try:
                    level = (chunk['data'][1] & 0b11000000) >> 6
                    returned['compressionLevel'] = (level, __COMPRESSION_LEVEL[level])
                except Exception as e:
                    Debug.print('[BCFile..decodeChunk_IDAT] Unable to decode compression level: {0}', f"{e}")

            return returned

        def decodeChunk_gAMA(chunk):
            """Decode gAMA chunk and return a dictionary with:

            {
                'gamma': <float>
            }

            The value is encoded as a 4-byte unsigned integer, representing gamma times 100000.
            For example, a gamma of 1/2.2 would be stored as 45455.
            """
            returned = {
                'gamma': 1/(struct.unpack('!I', chunk['data'][0:4])[0]/100000)
            }

            return returned

        def decodeChunk_sRGB(chunk):
            """Decode sRGB chunk and return a dictionary with:

            {
                'sRGBRendering': (<int>, <str>)
            }

            """
            __RENDERING_INTENT = {
                   0: 'Perceptual',
                   1: 'Relative colorimetric',
                   2: 'Saturation',
                   3: 'Absolute colorimetric'
                }

            returned = {
                'sRGBRendering': int(chunk['data'][0])
            }

            if returned['sRGBRendering'] in __RENDERING_INTENT:
                returned['sRGBRendering'] = (returned['sRGBRendering'], __RENDERING_INTENT[returned['sRGBRendering']])
            else:
                returned['sRGBRendering'] = (returned['sRGBRendering'], 'Unknown')

            return returned

        def decodeChunk_iCCP(chunk, getExtraData):
            """Decode iCCP chunk and return a dictionary with:

            {
                'iccProfileName': <str>,
                'iccProfileCopyright': <str>
                'iccProfile': <byte str>
            }

            """
            returned = {
                'iccProfileName': {},
                'iccProfileCopyright': {},
                'iccProfile': b''
            }

            for index, character in enumerate(chunk['data'][0:80]):
                if character==0:
                    break

            index+=2

            zData = chunk['data'][index:]

            iccData = zlib.decompress(zData)

            if getExtraData==False:
                returned['iccProfile']=b'Y'
            else:
                returned['iccProfile']=iccData

            returned.update(self.__readICCData(iccData))

            return returned

        if getExtraData==False and fromCache and not self.__metadata is None:
            return self.__metadata

        returned = {}

        with open(self._fullPathName, 'rb') as fHandler:
            # check signature (8 bytes)
            bytes = fHandler.read(8)
            if bytes != b'\x89PNG\r\n\x1a\n':
                Debug.print('[BCFile.__readMetaDataPng] Invalid header ({0}): {1}', self._fullPathName, bytes)
                return returned

            chunk = readChunk(fHandler)
            while chunk['valid']:
                if chunk['id']=='IHDR':
                    returned.update(decodeChunk_IHDR(chunk))
                elif chunk['id']=='pHYs':
                    returned.update(decodeChunk_pHYs(chunk))
                elif chunk['id']=='PLTE':
                    returned.update(decodeChunk_PLTE(chunk))
                elif chunk['id']=='gAMA':
                    returned.update(decodeChunk_gAMA(chunk))
                elif chunk['id']=='sRGB':
                    returned.update(decodeChunk_sRGB(chunk))
                    # if sRGB, ignore gamma
                    returned.pop('gamma', None)
                elif chunk['id']=='iCCP':
                    returned.update(decodeChunk_iCCP(chunk, getExtraData))
                    # if icc profile, ignore gamma and sRGB
                    returned.pop('gamma', None)
                    returned.pop('sRGBRendering', None)
                elif chunk['id']=='IDAT':
                    returned.update(decodeChunk_IDAT(chunk))
                    idat1Processed = True
                elif chunk['id']=='IEND':
                    break
                #elif chunk['id']=='IDAT':
                #    Debug.print('[BCFile.__readMetaDataPng] File: {0} // Chunk: {1}', self._fullPathName, chunk['id'])

                chunk = readChunk(fHandler)

        return returned


    def __readMetaDataGif(self, fromCache=True, getExtraData=False):
        """Read metadata from GIF file

        GIF specifications: https://www.w3.org/Graphics/GIF/spec-gif89a.txt
        """
        def skip_subBlock(fHandler, skipFirstByte=False):
            # skip a sub-block
            if skipFirstByte:
                fByte = fHandler.read(1)
                if fByte == b'\0':
                    return

            bufSize = struct.unpack('B', fHandler.read(1))[0]
            while bufSize > 0:
                fHandler.seek(bufSize, 1)
                bufSize = struct.unpack('B', fHandler.read(1))[0]

        def read_ID(fHandler):
            # read image descriptor
            returned={
                # -1 = no local palette
                'paletteSize': -1
            }

            data = fHandler.read(9)
            if data[8] & 0b10000000 == 0b10000000:
                # bit set to 1: there's a local table
                # calculate local color table size
                lctSize =  pow(2, (data[8] & 0b00000111) + 1 )
                returned['paletteSize']=lctSize
                lctSize*=3
                # skip color table
                fHandler.seek(lctSize, 1)

            # skip image data content
            skip_subBlock(fHandler, True)

            return returned

        def read_GCE(fHandler):
            # read Graphic Control Extension
            # return only delay in milliseconds
            data = fHandler.read(6)
            returned=10 * int(struct.unpack('<H', data[2:4])[0])
            return returned

        def read_CE(fHandler):
            # read Comment Extension
            # return nothing, only skip block
            skip_subBlock(fHandler)

        def read_PTE(fHandler):
            # read Plain Text Extension
            # return nothing, only skip block
            fHandler.seek(13, 1)
            skip_subBlock(fHandler)

        def read_AE(fHandler):
            # read Application Extension
            # return nothing, only skip block
            fHandler.seek(12, 1)
            skip_subBlock(fHandler)

        # if getExtraData==False and fromCache and not self.__metadata is None:
        # => no extradata for gif files
        if fromCache and not self.__metadata is None:
            return self.__metadata

        returned = {
                'colorType': (3, 'Indexed palette'),
                'imageCount': 0,
                'imageDelay': [],
                'imageDelayMin': 0,
                'imageDelayMax': 0,
                'paletteMin': 0,
                'paletteMax': 0,
                'paletteCount': 0,
                'paletteSize': [],
                'loopDuration': 0
            }

        with open(self._fullPathName, 'rb') as fHandler:
            # check signature (8 bytes)
            bytes = fHandler.read(6)
            if not bytes in [b'GIF87a', b'GIF89a']:
                Debug.print('[BCFile.__readMetaDataPng] Invalid header: {0}', bytes)

            logicalScreenDescriptor = fHandler.read(7)

            if logicalScreenDescriptor[4] & 0b10000000 == 0b10000000:
                # a global color table follows the logical screen descriptor
                gctSize = pow(2, (logicalScreenDescriptor[4] & 0b00000111) + 1 )
                returned['paletteSize'].append(gctSize)
                gctSize*=3
                # skip gct
                fHandler.seek(gctSize, 1)

            gceAllowed=True
            while True:
                blockType=fHandler.read(1)

                if blockType == b'\x21':
                    blockType=fHandler.read(1)
                    if blockType==b'\xF9':
                        # Graphic Control Extension
                        returned['imageDelay'].append(read_GCE(fHandler))
                        gceAllowed=False
                    elif blockType==b'\xFE':
                        # Comment Extension
                        read_CE(fHandler)
                    elif blockType==b'\x01':
                        # Plain Text Extension
                        read_PTE(fHandler)
                    elif blockType==b'\xFF':
                        # Application Extension
                        read_AE(fHandler)
                elif blockType == b'\x2C':
                    # Image Descriptor
                    idContent=read_ID(fHandler)
                    if idContent['paletteSize'] > 0:
                        returned['paletteSize'].append(idContent['paletteSize'])
                    returned['imageCount']+=1
                    gceAllowed=True
                else:
                    break

            returned['paletteCount'] = len(returned['paletteSize'])
            if returned['paletteCount']>0:
                returned['paletteMin'] = min(returned['paletteSize'])
                returned['paletteMax'] = max(returned['paletteSize'])

            if len(returned['imageDelay'])>0:
                returned['imageDelayMin'] = min(returned['imageDelay'])
                returned['imageDelayMax'] = max(returned['imageDelay'])
                returned['loopDuration'] = sum(returned['imageDelay'])

            if returned['imageCount'] > 1 and (len(returned['imageDelay']) ==0 or max(returned['imageDelay']) == 0):
                # need to apply default [arbitrary] delay of 1/10s (100ms)
                returned['imageDelay'] = [100] * returned['imageCount']
                returned['imageDelayMin'] = 100
                returned['imageDelayMax'] = 100
                returned['loopDuration'] = sum(returned['imageDelay'])

        return returned


    def __readMetaDataWebP(self, fromCache=True, getExtraData=False):
        """Read metadata from GIF file

        """
        # if getExtraData==False and fromCache and not self.__metadata is None:
        # => no extradata for webp files
        if fromCache and not self.__metadata is None:
            return self.__metadata

        returned = {
                'imageCount': 0
            }
        ir = QImageReader(self._fullPathName)
        returned['imageCount']=ir.imageCount()
        return returned


    def __readMetaDataPsd(self, fromCache=True, getExtraData=False):
        """Read metadata from PSD file

        PSD specifications: https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/#50577409_pgfId-1030196
                            https://www.fileformat.info/format/psd/egff.htm
                            https://wiki.fileformat.com/image/psd/

        """
        def read_header(fHandle):
            """Decode header return a dictionary with:

            {
                'width': <int>,
                'height': <int>,
                'bitDepth': (<int>, <str),
                'colorMode': (<int>, <str>),
                'colorChannels': (<int>, <str>),
            }

            """
            bytes =fHandle.read(22)

            __COLOR_TYPE = {
                    0: 'Bitmap',
                    1: 'Grayscale',
                    2: 'Indexed palette',
                    3: 'RGB',
                    4: 'CMYK',
                    7: 'Multichannel',
                    8: 'Duotone',
                    9: 'L*a*b*',
                }

            returned = {
                'width': struct.unpack('!I', bytes[14:18])[0],
                'height': struct.unpack('!I', bytes[10:14])[0],
                'colorChannels': struct.unpack('!H', bytes[8:10])[0],
                'bitDepth': (struct.unpack('!H', bytes[18:20])[0], f"{struct.unpack('!H', bytes[18:20])[0]}-bit integer/channel"),
                'colorType': struct.unpack('!H', bytes[20:22])[0]
            }

            if returned['colorType'] in __COLOR_TYPE:
                withAlpha = ''
                if returned['colorType'] == 3 and returned['colorChannels'] == 4 or returned['colorType'] == 4 and returned['colorChannels'] == 5:
                    withAlpha = ' with Alpha'

                returned['colorType']=(returned['colorType'], __COLOR_TYPE[returned['colorType']] + withAlpha)
            else:
                returned['colorType']=(returned['colorType'], 'Unknown')

            return returned

        def read_CMD(fHandle):
            """Decode Color Mode Data section

            return nothing
            """
            # color mode data section
            length = struct.unpack('!L', fHandle.read(4))[0]
            if length > 0:
                # skip color table content
                fHandle.seek(length)

        def read_IRB(fHandle):
            """Decode Image Resources Block section

            return nothing
            """
            # ==> commented, used for debug and psd file format analysis
            #__IRB_ID = {
            #    0x03E8: "(Obsolete--Photoshop 2.0 only ) Contains five 2-byte values: number of channels, rows, columns, depth, and mode",
            #    0x03E9: "Macintosh print manager print info record",
            #    0x03EA: "Macintosh page format information. No longer read by Photoshop. (Obsolete)",
            #    0x03EB: "(Obsolete--Photoshop 2.0 only ) Indexed color table",
            #    0x03ED: "ResolutionInfo structure. See Appendix A in Photoshop API Guide.pdf.",
            #    0x03EE: "Names of the alpha channels as a series of Pascal strings.",
            #    0x03EF: "(Obsolete) See ID 1077DisplayInfo structure. See Appendix A in Photoshop API Guide.pdf.",
            #    0x03F0: "The caption as a Pascal string.",
            #    0x03F1: "Border information. Contains a fixed number (2 bytes real, 2 bytes fraction) for the border width, and 2 bytes for border units (1 = inches, 2 = cm, 3 = points, 4 = picas, 5 = columns).",
            #    0x03F2: "Background color. See See Color structure.",
            #    0x03F3: "Print flags. A series of one-byte boolean values (see Page Setup dialog): labels, crop marks, color bars, registration marks, negative, flip, interpolate, caption, print flags.",
            #    0x03F4: "Grayscale and multichannel halftoning information",
            #    0x03F5: "Color halftoning information",
            #    0x03F6: "Duotone halftoning information",
            #    0x03F7: "Grayscale and multichannel transfer function",
            #    0x03F8: "Color transfer functions",
            #    0x03F9: "Duotone transfer functions",
            #    0x03FA: "Duotone image information",
            #    0x03FB: "Two bytes for the effective black and white values for the dot range",
            #    0x03FC: "(Obsolete)",
            #    0x03FD: "EPS options",
            #    0x03FE: "Quick Mask information. 2 bytes containing Quick Mask channel ID; 1- byte boolean indicating whether the mask was initially empty.",
            #    0x03FF: "(Obsolete)",
            #    0x0400: "Layer state information. 2 bytes containing the index of target layer (0 = bottom layer).",
            #    0x0401: "Working path (not saved). See See Path resource format.",
            #    0x0402: "Layers group information. 2 bytes per layer containing a group ID for the dragging groups. Layers in a group have the same group ID.",
            #    0x0403: "(Obsolete)",
            #    0x0404: "IPTC-NAA record. Contains the File Info... information. See the documentation in the IPTC folder of the Documentation folder. ",
            #    0x0405: "Image mode for raw format files",
            #    0x0406: "JPEG quality. Private.",
            #    0x0408: "(Photoshop 4.0) Grid and guides information. See See Grid and guides resource format.",
            #    0x0409: "(Photoshop 4.0) Thumbnail resource for Photoshop 4.0 only. See See Thumbnail resource format.",
            #    0x040A: "(Photoshop 4.0) Copyright flag. Boolean indicating whether image is copyrighted. Can be set via Property suite or by user in File Info...",
            #    0x040B: "(Photoshop 4.0) URL. Handle of a text string with uniform resource locator. Can be set via Property suite or by user in File Info...",
            #    0x040C: "(Photoshop 5.0) Thumbnail resource (supersedes resource 1033). See See Thumbnail resource format. ",
            #    0x040D: "(Photoshop 5.0) Global Angle. 4 bytes that contain an integer between 0 and 359, which is the global lighting angle for effects layer. If not present, assumed to be 30.",
            #    0x040E: "(Obsolete) See ID 1073 below. (Photoshop 5.0) Color samplers resource. See See Color samplers resource format.",
            #    0x040F: "(Photoshop 5.0) ICC Profile. The raw bytes of an ICC (International Color Consortium) format profile. See ICC1v42_2006-05.pdf in the Documentation folder and icProfileHeader.h in Sample Code\Common\Includes . ",
            #    0x0410: "(Photoshop 5.0) Watermark. One byte. ",
            #    0x0411: "(Photoshop 5.0) ICC Untagged Profile. 1 byte that disables any assumed profile handling when opening the file. 1 = intentionally untagged.",
            #    0x0412: "(Photoshop 5.0) Effects visible. 1-byte global flag to show/hide all the effects layer. Only present when they are hidden.",
            #    0x0413: "(Photoshop 5.0) Spot Halftone. 4 bytes for version, 4 bytes for length, and the variable length data.",
            #    0x0414: "(Photoshop 5.0) Document-specific IDs seed number. 4 bytes: Base value, starting at which layer IDs will be generated (or a greater value if existing IDs already exceed it). Its purpose is to avoid the case where we add layers, flatten, save, open, and then add more layers that end up with the same IDs as the first set.",
            #    0x0415: "(Photoshop 5.0) Unicode Alpha Names. Unicode string",
            #    0x0416: "(Photoshop 6.0) Indexed Color Table Count. 2 bytes for the number of colors in table that are actually defined",
            #    0x0417: "(Photoshop 6.0) Transparency Index. 2 bytes for the index of transparent color, if any.",
            #    0x0419: "(Photoshop 6.0) Global Altitude. 4 byte entry for altitude",
            #    0x041A: "(Photoshop 6.0) Slices. See See Slices resource format.",
            #    0x041B: "(Photoshop 6.0) Workflow URL. Unicode string",
            #    0x041C: "(Photoshop 6.0) Jump To XPEP. 2 bytes major version, 2 bytes minor version, 4 bytes count. Following is repeated for count: 4 bytes block size, 4 bytes key, if key = 'jtDd' , then next is a Boolean for the dirty flag; otherwise it's a 4 byte entry for the mod date.",
            #    0x041D: "(Photoshop 6.0) Alpha Identifiers. 4 bytes of length, followed by 4 bytes each for every alpha identifier.",
            #    0x041E: "(Photoshop 6.0) URL List. 4 byte count of URLs, followed by 4 byte long, 4 byte ID, and Unicode string for each count.",
            #    0x0421: "(Photoshop 6.0) Version Info. 4 bytes version, 1 byte hasRealMergedData , Unicode string: writer name, Unicode string: reader name, 4 bytes file version.",
            #    0x0422: "(Photoshop 7.0) EXIF data 1. See http://www.kodak.com/global/plugins/acrobat/en/service/digCam/exifStandard2.pdf",
            #    0x0423: "(Photoshop 7.0) EXIF data 3. See http://www.kodak.com/global/plugins/acrobat/en/service/digCam/exifStandard2.pdf",
            #    0x0424: "(Photoshop 7.0) XMP metadata. File info as XML description. See http://www.adobe.com/devnet/xmp/",
            #    0x0425: "(Photoshop 7.0) Caption digest. 16 bytes: RSA Data Security, MD5 message-digest algorithm",
            #    0x0426: "(Photoshop 7.0) Print scale. 2 bytes style (0 = centered, 1 = size to fit, 2 = user defined). 4 bytes x location (floating point). 4 bytes y location (floating point). 4 bytes scale (floating point)",
            #    0x0428: "(Photoshop CS) Pixel Aspect Ratio. 4 bytes (version = 1 or 2), 8 bytes double, x / y of a pixel. Version 2, attempting to correct values for NTSC and PAL, previously off by a factor of approx. 5%.",
            #    0x0429: "(Photoshop CS) Layer Comps. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure)",
            #    0x042A: "(Photoshop CS) Alternate Duotone Colors. 2 bytes (version = 1), 2 bytes count, following is repeated for each count: [ Color: 2 bytes for space followed by 4 * 2 byte color component ], following this is another 2 byte count, usually 256, followed by Lab colors one byte each for L, a, b. This resource is not read or used by Photoshop.",
            #    0x042B: "(Photoshop CS)Alternate Spot Colors. 2 bytes (version = 1), 2 bytes channel count, following is repeated for each count: 4 bytes channel ID, Color: 2 bytes for space followed by 4 * 2 byte color component. This resource is not read or used by Photoshop.",
            #    0x042D: "(Photoshop CS2) Layer Selection ID(s). 2 bytes count, following is repeated for each count: 4 bytes layer ID",
            #    0x042E: "(Photoshop CS2) HDR Toning information",
            #    0x042F: "(Photoshop CS2) Print info",
            #    0x0430: "(Photoshop CS2) Layer Group(s) Enabled ID. 1 byte for each layer in the document, repeated by length of the resource. NOTE: Layer groups have start and end markers",
            #    0x0431: "(Photoshop CS3) Color samplers resource. Also see ID 1038 for old format. See See Color samplers resource format.",
            #    0x0432: "(Photoshop CS3) Measurement Scale. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure)",
            #    0x0433: "(Photoshop CS3) Timeline Information. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure)",
            #    0x0434: "(Photoshop CS3) Sheet Disclosure. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure)",
            #    0x0435: "(Photoshop CS3) DisplayInfo structure to support floating point clors. Also see ID 1007. See Appendix A in Photoshop API Guide.pdf .",
            #    0x0436: "(Photoshop CS3) Onion Skins. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure)",
            #    0x0438: "(Photoshop CS4) Count Information. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure) Information about the count in the document. See the Count Tool.",
            #    0x043A: "(Photoshop CS5) Print Information. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure) Information about the current print settings in the document. The color management options.",
            #    0x043B: "(Photoshop CS5) Print Style. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure) Information about the current print style in the document. The printing marks, labels, ornaments, etc.",
            #    0x043C: "(Photoshop CS5) Macintosh NSPrintInfo. Variable OS specific info for Macintosh. NSPrintInfo. It is recommened that you do not interpret or use this data.",
            #    0x043D: "(Photoshop CS5) Windows DEVMODE. Variable OS specific info for Windows. DEVMODE. It is recommened that you do not interpret or use this data.",
            #    0x043E: "(Photoshop CS6) Auto Save File Path. Unicode string. It is recommened that you do not interpret or use this data.",
            #    0x043F: "(Photoshop CS6) Auto Save Format. Unicode string. It is recommened that you do not interpret or use this data.",
            #    0x0440: "(Photoshop CC) Path Selection State. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure) Information about the current path selection state.",
            #    0x0BB7: "Name of clipping path. See See Path resource format.",
            #    0x0BB8: "(Photoshop CC) Origin Path Info. 4 bytes (descriptor version = 16), Descriptor (see See Descriptor structure) Information about the origin path data.",
            #    0x1B58: "Image Ready variables. XML representation of variables definition",
            #    0x1B59: "Image Ready data sets",
            #    0x1B5A: "Image Ready default selected state",
            #    0x1B5B: "Image Ready 7 rollover expanded state",
            #    0x1B5C: "Image Ready rollover expanded state",
            #    0x1B5D: "Image Ready save layer settings",
            #    0x1B5E: "Image Ready version",
            #    0x1F40: "(Photoshop CS3) Lightroom workflow, if present the document is in the middle of a Lightroom workflow.",
            #    0x2710: "Print flags information. 2 bytes version ( = 1), 1 byte center crop marks, 1 byte ( = 0), 4 bytes bleed width value, 2 bytes bleed width scale."
            #}

            returned = {}

            # color mode data section
            length = struct.unpack('!I', fHandle.read(4))[0]
            if length == 0:
                return returned

            maxPos = fHandle.tell() + length

            while fHandle.tell() < maxPos:
                irbSignature = fHandle.read(4)
                if irbSignature != b'8BIM':
                    Debug.print('invalid irb signature', irbSignature)
                    fHandle.seek(-4, 1)
                    break

                resId = struct.unpack('!H', fHandle.read(2))[0]
                # ==> commented, used for debug and psd file format analysis
                #if resId in __IRB_ID:
                #    Debug.print('[BCFile.__readMetaDataPsd] IRB({0}): {1}', hex(resId), __IRB_ID[resId])
                #elif resId >= 0x0FA0 and resId <= 0x1387:
                #    Debug.print('[BCFile.__readMetaDataPsd] IRB({0}): "Plug-In resource(s). Resources added by a plug-in. See the plug-in API found in the SDK documentation"', hex(resId))
                #elif resId >= 0x07D0 and resId <= 0x0BB6:
                #    Debug.print('[BCFile.__readMetaDataPsd] IRB({0}): "Path Information (saved paths). See See Path resource format."', hex(resId))


                pStringSize = struct.unpack('B', fHandler.read(1))[0]
                if pStringSize%2 == 0:
                    # odd value
                    pStringSize+=1
                # skip name
                fHandle.seek(pStringSize, 1)

                length = struct.unpack('!I', fHandle.read(4))[0]
                if length%2 != 0:
                    # odd value
                    length+=1

                if resId in [0x03ED, 0x040F]:
                    data = fHandle.read(length)
                    if resId == 0x03ED:
                        returned.update(decode_IRB_03ED(data))
                    elif resId == 0x040F:
                        returned.update(decode_IRB_040F(data, getExtraData))
                else:
                    # skip data
                    fHandle.seek(length, 1)

            return returned

        def decode_IRB_03ED(data):
            # 0x03ED = resolution
            ppX = round(struct.unpack('!I', data[0:4])[0] / 0xFFFF, 2)
            unit = struct.unpack('!H', data[4:6])[0]
            if unit == 2:
                # pcm / convert to ppi
                ppX*=0.0254

            ppY = round(struct.unpack('!I', data[8:12])[0] / 0xFFFF, 2)
            unit = struct.unpack('!H', data[12:14])[0]
            if unit == 2:
                # pcm / convert to ppi
                ppY*=0.0254

            returned = {
                'resolutionX': (ppX, f'{ppX:.3f}ppi'),
                'resolutionY': (ppY, f'{ppY:.3f}ppi'),
                'resolution': ''
            }

            if ppX == ppY:
                returned['resolution'] = f'{ppX:.3f}ppi'
            else:
                returned['resolution'] = f'{ppX:.3f}x{ppY:.3f}ppi'

            return returned

        def decode_IRB_040F(data, getExtraData):
            # 0x040F = ICC profile

            returned = {
                'iccProfileName': {},
                'iccProfileCopyright': {},
                'iccProfile': b''
            }

            if getExtraData==False:
                returned['iccProfile']=b'Y'
            else:
                returned['iccProfile']=data
            returned.update(self.__readICCData(data))

            return returned

        def read_LMI(fHandle):
            """Decode Layer and Mask Information section"""
            # Layer and Mask Information
            #print(hex(fHandle.tell()))
            length = struct.unpack('!L', fHandle.read(4))[0]
            #print('lmi length', length)
            if length > 0:
                # skip color table content
                fHandle.seek(length)

            return {}

        if getExtraData==False and fromCache and not self.__metadata is None:
            return self.__metadata

        returned = {}

        with open(self._fullPathName , 'rb') as fHandler:
            # check signature (4 bytes)
            bytes = fHandler.read(4)
            if bytes != b'8BPS':
                Debug.print('[BCFile.__readMetaDataPsd] Invalid header: {0}', bytes)
                return returned

            returned.update(read_header(fHandler))
            read_CMD(fHandler)
            returned.update(read_IRB(fHandler))
            #returned.update(read_LMI(fHandler))

        return returned


    def __readMetaDataXcf(self, fromCache=True, getExtraData=False):
        """Read metadata from XCF file

        XCF specifications: http://henning.makholm.net/xcftools/xcfspec-saved
                            https://gitlab.gnome.org/GNOME/gimp/-/blob/master/devel-docs/xcf.txt
        """
        def read_header(fHandle):
            # read xcf header
            __COLOR_TYPE = {
                    0: 'RGB',
                    1: 'Grayscale',
                    2: 'Indexed palette'
                }

            __BIT_DEPTH = {
                      0: "8-bit integer/channel [gamma]",
                      1: "16-bit integer/channel [gamma]",
                      2: "32-bit integer/channel [linear]",
                      3: "16-bit float/channel [linear]",
                      4: "32-bit float/channel [linear]",

                    100: "8-bit integer/channel [linear]",
                    150: "8-bit integer/channel [gamma]",
                    200: "16-bit integer/channel [linear]",
                    250: "16-bit integer/channel [gamma]",
                    300: "32-bit integer/channel [linear]",
                    350: "32-bit integer/channel [gamma]",
                    500: "16-bit float/channel [linear]",
                    550: "16-bit float/channel [gamma]",
                    600: "32-bit float/channel [linear]",
                    650: "32-bit float/channel [gamma]",
                    700: "64-bit float/channel [linear]",
                    750: "64-bit float/channel [gamma]"
                }

            returned = {
                'width': 0,
                'height': 0,
                'colorType': 0,
                'bitDepth': (8, "8-bit integer/channel"),
                'iccProfileName': {'en-US': '- [<i>Default GIMP: sRGB</i>]'},
                'iccProfileCopyright': {'en-US': ''}
            }

            # skip file version
            version = fHandle.read(5)

            returned['width'] = int(struct.unpack('!I', fHandle.read(4) )[0])
            returned['height'] = int(struct.unpack('!I', fHandle.read(4) )[0])
            returned['colorType'] = int(struct.unpack('!I', fHandle.read(4) )[0])

            if returned['colorType'] in __COLOR_TYPE:
                returned['colorType'] = (returned['colorType'], __COLOR_TYPE[returned['colorType']])
            else:
                returned['colorType'] = (returned['colorType'], 'Unknown')

            if returned['colorType'][0] == 1:
                # in gray scale, default GIMP color profile is D65 Linear Grayscale
                returned['iccProfileName']={'en-US': '- [<i>Default GIMP: D65 Linear Grayscale</i>]'}

            if version in [b'file\0', b'v001\0', b'v002\0', b'v003\0']:
                return returned

            bitDepth = int(struct.unpack('!I', fHandle.read(4) )[0])
            if bitDepth in __BIT_DEPTH:
                returned['bitDepth'] = (bitDepth, __BIT_DEPTH[bitDepth])
            else:
                returned['bitDepth'] = (bitDepth, 'Unknown')



            return returned

        def read_imageProperties(fHandle, getExtraData):
            # read xcf image properties
            returned = {}

            while True:
                id = int(struct.unpack('!I', fHandle.read(4) )[0])

                if id == 0:
                    break

                length = int(struct.unpack('!I', fHandle.read(4) )[0])

                if id in [0x01, 0x13, 0x15]:
                    bytes = fHandle.read(length)

                    if id == 0x01:
                        # color table
                        returned.update(read_imageProperties_01(bytes))
                    elif id == 0x13:
                        # resolution
                        returned.update(read_imageProperties_13(bytes))
                    elif id == 0x15:
                        # parasite
                        returned.update(read_imageProperties_15(bytes, getExtraData))
                else:
                    # ignore properties and skip data
                    fHandle.seek(length, 1)

            return returned

        def read_imageProperties_01(data):
            # read color map table (#01)
            returned = {
                'paletteSize': int(struct.unpack('!I', data[0:4] )[0])
            }
            return returned

        def read_imageProperties_13(data):
            # read a resolution (#19)
            ppX = struct.unpack('!f', data[0:4])[0]
            ppY = struct.unpack('!f', data[4:8])[0]

            returned = {
                'resolutionX': (ppX, f'{ppX:.3f}ppi'),
                'resolutionY': (ppY, f'{ppY:.3f}ppi'),
                'resolution': ''
            }

            if ppX == ppY:
                returned['resolution'] = f'{ppX:.3f}ppi'
            else:
                returned['resolution'] = f'{ppX:.3f}x{ppY:.3f}ppi'

            return returned

        def read_imageProperties_15(data, getExtraData):
            # read a parasite (#21)
            # can contains N parasites...

            position = 0
            while position<len(data):
                lName = int(struct.unpack('!I', data[position:position+4])[0])
                if lName == 0:
                    break

                position+=4
                name = data[position:position+lName - 1]   # remove trailing 0x00 character

                position+=lName+4 #+4 => ignore flags
                parasiteSize=int(struct.unpack('!I', data[position:position+4])[0])
                position+=4


                if name == b'icc-profile':
                    returned['iccProfile']=data[position:position+parasiteSize]
                    returned.update(self.__readICCData(returned['iccProfile']))
                    if getExtraData==False:
                        returned['iccProfile']=b'Y'
                else:
                    pass
                    #print(name, 'skip')


                position+=parasiteSize

            return {}

        if getExtraData==False and fromCache and not self.__metadata is None:
            return self.__metadata

        returned = {}

        with open(self._fullPathName , 'rb') as fHandler:
            # check signature (8 bytes)
            bytes = fHandler.read(9)
            if bytes != b'gimp xcf ':
                Debug.print('[BCFile.__readMetaDataXcf] Invalid header: {0}', bytes)
                return returned

            returned.update(read_header(fHandler))

            returned.update(read_imageProperties(fHandler, getExtraData))

        return returned


    def __readMetaDataKra(self, fromCache=True, getExtraData=False):
        """Read metadata from Krita file"""
        def getShapeLayerList():
            # return a list of shape layer files into archive

            try:
                archive = zipfile.ZipFile(self._fullPathName, 'r')
            except Exception as e:
                # can't be read (not exist, not a zip file?)
                self.__readable = False
                Debug.print('[BCFile.__readMetaDataKra] Unable to open file {0}: {1}', self._fullPathName, f"{e}")
                return []

            # notes:
            #   - look directly for content.svg files into all *.shapelayer directory
            #     simpler to get shapelayer node and then build filename...
            #   - dot '.' is used because don't know how path is returned in windows --------+
            #                                                                                V
            returned = [file.filename for file in archive.filelist if re.search('\.shapelayer.content\.svg', file.filename)]
            archive.close()

            return returned

        def getKeyFramesList():
            # return a list of keyframes files into archive

            try:
                archive = zipfile.ZipFile(self._fullPathName, 'r')
            except Exception as e:
                # can't be read (not exist, not a zip file?)
                self.__readable = False
                Debug.print('[BCFile.__readMetaDataKra] Unable to open file {0}: {1}', self._fullPathName, f"{e}")
                return []

            # notes:
            #   - look directly for *.keyframes.xml files into all layers directory
            #     simpler to get keyframes files and then build filename...
            #   - dot '.' is used because don't know how path is returned in windows --------+
            #                                                                                V
            returned = [file.filename for file in archive.filelist if re.search('.layers.*keyframes\.xml$', file.filename)]
            archive.close()

            return returned

        def getPaletteList():
            # return a list of palette files into archive

            try:
                archive = zipfile.ZipFile(self._fullPathName, 'r')
            except Exception as e:
                # can't be read (not exist, not a zip file?)
                self.__readable = False
                Debug.print('[BCFile.__readMetaDataKra] Unable to open file {0}: {1}', self._fullPathName, f"{e}")
                return []

            # notes:
            #   - look directly for content.svg files into all *.shapelayer directory
            #     simpler to get shapelayer node and then build filename...
            #   - dot '.' is used because don't know how path is returned in windows ----+
            #                                                                            V
            returned = [file.filename for file in archive.filelist if re.search('palettes..*\.kpl$', file.filename)]
            archive.close()

            return returned

        if getExtraData==False and fromCache and not self.__metadata is None:
            return self.__metadata

        returned = {
            'width': 0,
            'height': 0,
            'resolutionX': (0, 'Unknown'),
            'resolutionY': (0, 'Unknown'),
            'resolution': '',
            'colorType': (None, ''),
            'bitDepth': (None, ''),
            'iccProfileName': {},
            'imageFrom': 0,
            'imageTo': 0,
            'imageMaxKeyFrameTime': 0,
            'imageNbKeyFrames': 0,
            'imageDelay': 0,
            'kritaVersion': '-',

            'document.layerCount': 0,
            'document.fileLayers': [],
            'document.usedFonts': [],
            'document.embeddedPalettes': {},
            'document.referenceImages.data': [],
            'document.referenceImages.count': 0,

            'about.title': '',
            'about.subject': '',
            'about.description': '',
            'about.keywords': '',
            'about.creator': '',
            'about.creationDate': '',
            'about.editingTime': 0,
            'about.editingCycles': 0,

            'author.nickName': '',
            'author.firstName': '',
            'author.lastName': '',
            'author.initials': '',
            'author.title': '',
            'author.position': '',
            'author.company': '',
            'author.contact': [],
        }

        tmpRefImgList=[]

        maindoc = self.__readArchiveDataFile("maindoc.xml")
        if not maindoc is None:
            # process file

            parsed = False
            try:
                xmlDoc = xmlElement.fromstring(maindoc.decode())
                parsed = True
            except Exception as e:
                # can't be read (not xml?)
                self.__readable = False
                Debug.print('[BCFile.__readMetaDataKra] Unable to parse "maindoc.xml" in file {0}: {1}', self._fullPathName, f"{e}")

            if parsed:
                try:
                    returned['kritaVersion'] = xmlDoc.attrib['kritaVersion']
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve Krita version in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    returned['width']=int(xmlDoc[0].attrib['width'])
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve image width in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    returned['height']=int(xmlDoc[0].attrib['height'])
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve image height in file {0}: {1}', self._fullPathName, f"{e}")
                    return None

                try:
                    ppX = 0
                    ppX = float(xmlDoc[0].attrib['x-res'])
                    returned['resolutionX'] = (ppX, f'{ppX:.3f}ppi')
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve image resolution-x in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    ppY = 0
                    ppY = float(xmlDoc[0].attrib['y-res'])
                    returned['resolutionY'] = (ppY, f'{ppX:.3f}ppi')
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve image resolution-y in file {0}: {1}', self._fullPathName, f"{e}")

                if ppX == ppY:
                    returned['resolution'] = f'{ppX:.3f}ppi'
                else:
                    returned['resolution'] = f'{ppX:.3f}x{ppY:.3f}ppi'

                # Color model id comparison through the ages (from kis_kra_loader.cpp)
                #
                #   2.4        2.5          2.6         ideal
                #
                #   ALPHA      ALPHA        ALPHA       ALPHAU8
                #
                #   CMYK       CMYK         CMYK        CMYKAU8
                #              CMYKAF32     CMYKAF32
                #   CMYKA16    CMYKAU16     CMYKAU16
                #
                #   GRAYA      GRAYA        GRAYA       GRAYAU8
                #   GrayF32    GRAYAF32     GRAYAF32
                #   GRAYA16    GRAYAU16     GRAYAU16
                #
                #   LABA       LABA         LABA        LABAU16
                #              LABAF32      LABAF32
                #              LABAU8       LABAU8
                #
                #   RGBA       RGBA         RGBA        RGBAU8
                #   RGBA16     RGBA16       RGBA16      RGBAU16
                #   RgbAF32    RGBAF32      RGBAF32
                #   RgbAF16    RgbAF16      RGBAF16
                #
                #   XYZA16     XYZA16       XYZA16      XYZAU16
                #              XYZA8        XYZA8       XYZAU8
                #   XyzAF16    XyzAF16      XYZAF16
                #   XyzAF32    XYZAF32      XYZAF32
                #
                #   YCbCrA     YCBCRA8      YCBCRA8     YCBCRAU8
                #   YCbCrAU16  YCBCRAU16    YCBCRAU16
                #              YCBCRF32     YCBCRF32
                try:
                    csn = xmlDoc[0].attrib['colorspacename']

                    # RGB
                    if csn in ['RGBA', 'RGBAU8']:
                        returned['colorType'] = ('RGBA', 'RGB with Alpha')
                        returned['bitDepth'] = (8, '8-bit integer/channel')
                    elif csn in ['RGBA16', 'RGBAU16']:
                        returned['colorType'] = ('RGBA', 'RGB with Alpha')
                        returned['bitDepth'] = (16, '16-bit integer/channel')
                    elif csn in ['RgbAF16', 'RGBAF16']:
                        returned['colorType'] = ('RGBA', 'RGB with Alpha')
                        returned['bitDepth'] = (16.0, '16-bit float/channel')
                    elif csn in ['RgbAF32', 'RGBAF32']:
                        returned['colorType'] = ('RGBA', 'RGB with Alpha')
                        returned['bitDepth'] = (32.0, '32-bit float/channel')

                    # CYMK
                    elif csn in ['CMYK', 'CMYKAU8']:
                        returned['colorType'] = ('CMYKA', 'CMYK with Alpha')
                        returned['bitDepth'] = (8, '8-bit integer/channel')
                    elif csn in ['CMYKA16', 'CMYKAU16']:
                        returned['colorType'] = ('CMYKA', 'CMYK with Alpha')
                        returned['bitDepth'] = (16, '16-bit integer/channel')
                    elif csn in ['CMYKAF32', 'CMYKAF32']:
                        returned['colorType'] = ('CMYKA', 'CMYK with Alpha')
                        returned['bitDepth'] = (32.0, '32-bit float/channel')

                    # GRAYSCALE
                    elif csn in ['GRAYA', 'GRAYAU8']:
                        returned['colorType'] = ('GRAYA', 'Grayscale with Alpha')
                        returned['bitDepth'] = (8, '8-bit integer/channel')
                    elif csn in ['GRAYA16', 'GRAYAU16']:
                        returned['colorType'] = ('GRAYA', 'Grayscale with Alpha')
                        returned['bitDepth'] = (16, '16-bit integer/channel')
                    elif csn == 'GRAYAF16':
                        returned['colorType'] = ('GRAYA', 'Grayscale with Alpha')
                        returned['bitDepth'] = (16, '16-bit float/channel')
                    elif csn in ['GrayF32', 'GRAYAF32']:
                        returned['colorType'] = ('GRAYA', 'Grayscale with Alpha')
                        returned['bitDepth'] = (32.0, '32-bit float/channel')

                    # L*A*B*
                    elif csn == 'LABAU8':
                        returned['colorType'] = ('LABA', 'L*a*b* with Alpha')
                        returned['bitDepth'] = (8, '8-bit integer/channel')
                    elif csn in ['LABA', 'LABAU16']:
                        returned['colorType'] = ('LABA', 'L*a*b* with Alpha')
                        returned['bitDepth'] = (16, '16-bit integer/channel')
                    elif csn == 'LABAF32':
                        returned['colorType'] = ('LABA', 'L*a*b* with Alpha')
                        returned['bitDepth'] = (32.0, '32-bit float/channel')

                    # XYZ
                    elif csn in ['XYZAU8', 'XYZA8']:
                        returned['colorType'] = ('XYZA', 'XYZ with Alpha')
                        returned['bitDepth'] = (8, '8-bit integer/channel')
                    elif csn in ['XYZA16', 'XYZAU16']:
                        returned['colorType'] = ('XYZA', 'XYZ with Alpha')
                        returned['bitDepth'] = (16, '16-bit integer/channel')
                    elif csn in ['XyzAF16', 'XYZAF16']:
                        returned['colorType'] = ('XYZA', 'XYZ with Alpha')
                        returned['bitDepth'] = (16.0, '16-bit float/channel')
                    elif csn in ['XyzAF32', 'XYZAF32']:
                        returned['colorType'] = ('XYZA', 'XYZ with Alpha')
                        returned['bitDepth'] = (32.0, '32-bit float/channel')

                    # YCbCr
                    elif csn in ['YCbCrA', 'YCBCRA8', 'YCBCRAU8']:
                        returned['colorType'] = ('YCbCr', 'YCbCr with Alpha')
                        returned['bitDepth'] = (8, '8-bit integer/channel')
                    elif csn in ['YCbCrAU16', 'YCBCRAU16']:
                        returned['colorType'] = ('YCbCr', 'YCbCr with Alpha')
                        returned['bitDepth'] = (16, '16-bit integer/channel')
                    elif csn == 'YCBCRF32':
                        returned['colorType'] = ('YCbCr', 'YCbCr with Alpha')
                        returned['bitDepth'] = (32.0, '32-bit float/channel')


                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve image colorspacename in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    returned['iccProfileName'] = {'en-US': xmlDoc[0].attrib['profile']}
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve image resolution-x in file {0}: {1}', self._fullPathName, f"{e}")


                try:
                    nodes=xmlDoc.findall(".//{*}layers/{*}layer[@keyframes]")
                    if len(nodes)>0:
                        # there's some nodes with keyframes
                        node=xmlDoc.find(".//{*}animation/{*}range")
                        if not node is None:
                            returned['imageFrom'] = int(node.attrib['from'])
                            returned['imageTo'] = int(node.attrib['to'])
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve currentTime in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    node=xmlDoc.find(".//{*}animation/{*}framerate")
                    if not node is None:
                        returned['imageDelay'] = int(node.attrib['value'])
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve framerate in file {0}: {1}', self._fullPathName, f"{e}")


                try:
                    returned['document.fileLayers']=[node.attrib['source'] for node in xmlDoc.findall(".//{*}layer[@nodetype='filelayer']")]
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve layers "filelayer" in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    returned['document.layerCount']=len(xmlDoc.findall(".//{*}layer"))
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve layers in file {0}: {1}', self._fullPathName, f"{e}")


                try:
                    tmpRefImgList=[node.attrib['src'] for node in xmlDoc.findall(".//{*}layer[@nodetype='referenceimages']/{*}referenceimage")]
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataKra] Unable to retrieve layers "referenceimage" in file {0}: {1}', self._fullPathName, f"{e}")

        else:
            # unable to read maindoc??
            # don't try to analyse file more..
            self.__readable = False
            return returned

        infoDoc = self.__readArchiveDataFile("documentinfo.xml")
        if not infoDoc is None:
            parsed = False
            try:
                xmlDoc = xmlElement.fromstring(infoDoc.decode())
                parsed = True
            except Exception as e:
                # can't be read (not xml?)
                self.__readable = False
                Debug.print('[BCFile.__readMetaDataKra] Unable to parse "documentinfo.xml" in file {0}: {1}', self._fullPathName, f"{e}")

            if parsed:
                node = xmlDoc.find('{*}about/{*}title')
                if not node is None:
                    returned['about.title'] = strDefault(node.text)

                node = xmlDoc.find('{*}about/{*}subject')
                if not node is None:
                    returned['about.subject'] = strDefault(node.text)

                node = xmlDoc.find('{*}about/{*}description')
                if not node is None:
                    if strDefault(node.text) != '':
                        returned['about.description'] = strDefault(node.text)
                    else:
                        # seems to get description ins abstract node?
                        node = xmlDoc.find('{*}about/{*}abstract')
                        if not node is None:
                            if strDefault(node.text) != '':
                                returned['about.description'] = strDefault(node.text)

                node = xmlDoc.find('{*}about/{*}keyword')
                if not node is None:
                    returned['about.keywords'] = strDefault(node.text)

                node = xmlDoc.find('{*}about/{*}initial-creator')
                if not node is None:
                    returned['about.creator'] = strDefault(node.text)

                node = xmlDoc.find('{*}about/{*}creation-date')
                if not node is None:
                    returned['about.creationDate'] = strDefault(node.text).replace('T', ' ')

                node = xmlDoc.find('{*}about/{*}editing-cycles')
                if not node is None:
                    returned['about.editingCycles'] = intDefault(node.text, 1)

                node = xmlDoc.find('{*}about/{*}editing-time')
                if not node is None:
                    # in seconds
                    returned['about.editingTime'] = intDefault(node.text)

                node = xmlDoc.find('{*}author/{*}full-name')
                if not node is None:
                    returned['author.nickName'] = strDefault(node.text)

                node = xmlDoc.find('{*}author/{*}creator-first-name')
                if not node is None:
                    returned['author.firstName'] = strDefault(node.text)

                node = xmlDoc.find('{*}author/{*}creator-last-name')
                if not node is None:
                    returned['author.lastName'] = strDefault(node.text)

                node = xmlDoc.find('{*}author/{*}initial')
                if not node is None:
                    returned['author.initials'] = strDefault(node.text)

                node = xmlDoc.find('{*}author/{*}author-title')
                if not node is None:
                    returned['author.title'] = strDefault(node.text)

                node = xmlDoc.find('{*}author/{*}position')
                if not node is None:
                    returned['author.position'] = strDefault(node.text)

                node = xmlDoc.find('{*}author/{*}company')
                if not node is None:
                    returned['author.company'] = strDefault(node.text)

                nodeList = xmlDoc.findall('{*}author/{*}contact')
                if not nodeList is None:
                    for node in nodeList:
                        if strDefault(node.text) != '':
                            returned['author.contact'].append({node.attrib['type']: strDefault(node.text)})


        for filename in getKeyFramesList():
            contentDoc = self.__readArchiveDataFile(filename)

            if not contentDoc is None:
                parsed = False
                try:
                    xmlDoc = xmlElement.fromstring(contentDoc.decode())
                    parsed = True
                except Exception as e:
                    # can't be read (not xml?)
                    self.__readable = False
                    Debug.print('[BCFile.__readMetaDataKra] Unable to parse "{2}" in file {0}: {1}', self._fullPathName, f"{e}", filename)

                if parsed:
                    nodes = xmlDoc.findall(".//{*}channel/{*}keyframe[@time]")
                    returned['imageNbKeyFrames']+=len(nodes)

                    for node in nodes:
                        nodeTime=int(node.attrib['time'])
                        returned['imageMaxKeyFrameTime']=max(returned['imageMaxKeyFrameTime'], nodeTime)

        for filename in getShapeLayerList():
            contentDoc = self.__readArchiveDataFile(filename)

            if not contentDoc is None:
                parsed = False
                try:
                    xmlDoc = xmlElement.fromstring(contentDoc.decode())
                    parsed = True
                except Exception as e:
                    # can't be read (not xml?)
                    self.__readable = False
                    Debug.print('[BCFile.__readMetaDataKra] Unable to parse "{2}" in file {0}: {1}', self._fullPathName, f"{e}", filename)

                if parsed:
                    fontList=[node.attrib['font-family'] for node in xmlDoc.findall('.//*[@font-family]')]

                    if len(fontList) > 0:
                        returned['document.usedFonts'] = list(set(returned['document.usedFonts'] + fontList))

        returned['document.usedFonts'].sort()

        for filename in getPaletteList():
            kplFile = self.__readArchiveDataFile(filename)

            if not kplFile is None:
                # retrieved kpl file is a ZIP archive
                contentDoc = self.__readArchiveDataFile('colorset.xml', io.BytesIO(kplFile))

                parsed = False
                try:
                    xmlDoc = xmlElement.fromstring(contentDoc.decode())
                    parsed = True
                except Exception as e:
                    # can't be read (not xml?)
                    self.__readable = False
                    Debug.print('[BCFile.__readMetaDataKra] Unable to parse "{2}" in file {0}: {1}', self._fullPathName, f"{e}", filename)

                if parsed:
                    try:
                        returned['document.embeddedPalettes'][xmlDoc.attrib['name']]={
                                            'colors':  len(xmlDoc.findall('ColorSetEntry')),
                                            'rows':    int(xmlDoc.attrib['rows']),
                                            'columns': int(xmlDoc.attrib['columns'])
                                        }
                    except Exception as e:
                        Debug.print('[BCFile.__readMetaDataKra] Malformed palette {2} in file {0}: {1}', self._fullPathName, f"{e}", filename)

        # load reference image details
        returned['document.referenceImages.count']=len(tmpRefImgList)
        if getExtraData:
            for refImg in tmpRefImgList:
                if not re.match(r'file://', refImg):
                    # embedded file
                    imageData = self.__readArchiveDataFile(refImg)
                    if imageData:
                        image = QImage()
                        if image.loadFromData(imageData):
                            returned['document.referenceImages.data'].append(image)
                else:
                    image = QImage()
                    if image.load(refImg.replace('file://', '')):
                        returned['document.referenceImages.data'].append(image)


        # References images are stored in a layer
        # Do not consider it as a layer because reference image layer is not visible in layer tree
        returned['document.layerCount']-=returned['document.referenceImages.count']


        return returned


    def __readMetaDataOra(self, fromCache=True, getExtraData=False):
        """Read metadata from Open Raster file"""
        # if getExtraData==False and fromCache and not self.__metadata is None:
        # => no extradata for ora files
        if fromCache and not self.__metadata is None:
            return self.__metadata

        returned = {
            'width': 0,
            'height': 0,
            'resolutionX': (0, 'Unknown'),
            'resolutionY': (0, 'Unknown'),
            'resolution': '',

            'document.layerCount': 0
        }

        maindoc = self.__readArchiveDataFile("stack.xml")
        if not maindoc is None:
            # process file

            parsed = False
            try:
                xmlDoc = xmlElement.fromstring(maindoc.decode())
                parsed = True
            except Exception as e:
                # can't be read (not xml?)
                self.__readable = False
                Debug.print('[BCFile.__readMetaDataOra] Unable to parse "stack.xml" in file {0}: {1}', self._fullPathName, f"{e}")

            if parsed:
                try:
                    returned['width']=int(xmlDoc.attrib['w'])
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataOra] Unable to retrieve image width in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    returned['height']=int(xmlDoc.attrib['h'])
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataOra] Unable to retrieve image height in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    ppX = 0
                    ppX = float(xmlDoc.attrib['xres'])
                    returned['resolutionX'] = (ppX, f'{ppX:.3f}ppi')
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataOra] Unable to retrieve image resolution-x in file {0}: {1}', self._fullPathName, f"{e}")

                try:
                    ppY = 0
                    ppY = float(xmlDoc.attrib['yres'])
                    returned['resolutionY'] = (ppY, f'{ppX:.3f}ppi')
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataOra] Unable to retrieve image resolution-y in file {0}: {1}', self._fullPathName, f"{e}")

                if ppX == 0 and ppY ==0:
                    # no resolution information
                    returned.pop('resolutionX')
                    returned.pop('resolutionY')
                    returned.pop('resolution')
                elif ppX == ppY:
                    returned['resolution'] = f'{ppX:.3f}ppi'
                else:
                    returned['resolution'] = f'{ppX:.3f}x{ppY:.3f}ppi'

                try:
                    returned['document.layerCount']=len(xmlDoc.findall(".//{*}layer"))
                except Exception as e:
                    Debug.print('[BCFile.__readMetaDataOra] Unable to retrieve layers in file {0}: {1}', self._fullPathName, f"{e}")

        return returned


    def __readMetaDataBmp(self, fromCache=True, getExtraData=False):
        """Read metadata from BMP file

        BMP specifications: https://en.wikipedia.org/wiki/BMP_file_format
                            https://www.digicamsoft.com/bmp/bmp.html
                            https://docs.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapv5header
                            https://formats.kaitai.io/bmp/
                            https://exiftool.org/TagNames/BMP.html
        """
        if fromCache and not self.__metadata is None:
            return self.__metadata

        returned = {}

        with open(self._fullPathName, 'rb') as fHandler:
            # check signature (2 bytes)
            bytes = fHandler.read(2)
            if not bytes in (b'BM', b'BA', b'CI', b'CP', b'IC', b'PT'):
                Debug.print('[BCFile.__readMetaDataBmp] Invalid header: {0}', bytes)
                return returned

            # skip useless data from header
            fHandler.seek(12, os.SEEK_CUR)

            # now in DIB header
            bytes = fHandler.read(4)
            dibHeaderSize=struct.unpack('<I', bytes)[0]

            if dibHeaderSize in (12, 16, 64):
                # with/height stored on 2bytes each
                bytes = fHandler.read(2)
                returned['width']=struct.unpack('<H', bytes)[0]

                # height can be negative?
                bytes = fHandler.read(2)
                returned['height']=abs(struct.unpack('<H', bytes)[0])
            else:
                # with/height stored on 4bytes each
                bytes = fHandler.read(4)
                returned['width']=struct.unpack('<I', bytes)[0]

                bytes = fHandler.read(4)
                returned['height']=struct.unpack('<I', bytes)[0]

                # colorPlane = 1, useless
                bytes = fHandler.read(2)

                # bits per pixels
                bytes = fHandler.read(2)
                bitsPerPixel=struct.unpack('<H', bytes)[0]

                # bits per pixels
                bytes = fHandler.read(4)
                compressionMethod=struct.unpack('<I', bytes)[0]

                if bitsPerPixel==1:
                    returned['colorType']=(3, 'Indexed palette')
                    returned['bitDepth']=(1, f"1-bit/pixel")
                elif bitsPerPixel==2:
                    returned['colorType']=(3, 'Indexed palette')
                    returned['bitDepth']=(2, f"2-bit/pixel")
                elif bitsPerPixel==4:
                    returned['colorType']=(3, 'Indexed palette')
                    returned['bitDepth']=(4, f"4-bit/pixel")
                elif bitsPerPixel==8:
                    returned['colorType']=(3, 'Indexed palette')
                    returned['bitDepth']=(8, f"8-bit")
                elif bitsPerPixel==16:
                    returned['colorType']=(6, 'RGB with Alpha')
                    returned['bitDepth']=(16, f"4-bit/channel")
                elif bitsPerPixel==24:
                    returned['colorType']=(2, 'RGB')
                    returned['bitDepth']=(24, f"8-bit/channel")
                elif bitsPerPixel==32:
                    returned['colorType']=(6, 'RGB with Alpha')
                    returned['bitDepth']=(32, f"8-bit/channel")

                # image data size
                bytes = fHandler.read(4)

                # Horizontal resolution (pixels per meter)
                bytes = fHandler.read(4)
                ppX=struct.unpack('<i', bytes)[0]*0.0254

                # Vertical resolution (pixels per meter)
                bytes = fHandler.read(4)
                ppY=struct.unpack('<i', bytes)[0]*0.0254

                if ppX>0:
                    returned['resolutionX'] = (ppX, f'{ppX:.3f}ppi')
                if ppY>0:
                    returned['resolutionY'] = (ppY, f'{ppY:.3f}ppi')

                if ppX>0:
                    if ppX == ppY:
                        returned['resolution'] = f'{ppX:.3f}ppi'
                    else:
                        returned['resolution'] = f'{ppX:.3f}x{ppY:.3f}ppi'

                # Palette size
                bytes = fHandler.read(4)
                paletteSize=struct.unpack('<I', bytes)[0]
                if paletteSize>0:
                    returned['paletteSize']=paletteSize

                if dibHeaderSize >= 108:
                    # BITMAPV5HEADER -- get icc profile

                    # skip useless data from header
                    # 4: important colors
                    skipSize=4

                    if compressionMethod in (3,6) or dibHeaderSize==124:
                        # not really sure, documentations are not clear about
                        # this format

                        # 4: Red channel bit mask
                        # 4: Green channel bit mask
                        # 4: Blue channel bit mask
                        skipSize+=12

                        if dibHeaderSize==124 or bitsPerPixel in (16,32):
                            # 4: Alpha channel bit mask
                            skipSize+=4


                    fHandler.seek(skipSize, os.SEEK_CUR)

                    # 4: color space
                    #       b'\x00\x00\x00\x00      None (Calibrated RGB)
                    #       b'\x01\x00\x00\x00      None (Device RGB)
                    #       b'\x02\x00\x00\x00      None (Device CMYK)
                    #       'sRGB' => b'BGRs'       sRGB
                    #       'Win ' => b' niW'       Windows Color Space
                    #       'LINK' => b'KNIL'       Linked Color Profile
                    #       'MBED' => b'DEBM'       Embedded Color Profile
                    colorSpace = fHandler.read(4)

                    skipSize=None
                    if colorSpace==b'BGRs':
                        returned['iccProfileName']={'en-gb': 'sRGB built-in'}
                    elif colorSpace==b'KNIL':
                        skipSize=48
                        embedded=False
                    elif colorSpace==b'DEBM':
                        skipSize=48
                        embedded=True
                    elif colorSpace==b' niW':
                        returned['iccProfileName']={'en-gb': 'Windows color space'}

                    if not skipSize is None:
                        fHandler.seek(skipSize, os.SEEK_CUR)

                        bytes=fHandler.read(4)
                        intent=struct.unpack('<I', bytes)[0]

                        bytes=fHandler.read(4)
                        iccProfileDataPos=struct.unpack('<I', bytes)[0]

                        bytes=fHandler.read(4)
                        iccProfileDataSize=struct.unpack('<I', bytes)[0]

                        fHandler.seek(14+iccProfileDataPos, os.SEEK_SET)
                        bytes=fHandler.read(iccProfileDataSize)

                        if embedded:
                            iccNfo=self.__readICCData(bytes)
                            returned.update(iccNfo)
                            if getExtraData==False:
                                returned['iccProfile']=b'Y'
                            else:
                                returned['iccProfile']=bytes
                        else:
                            returned['iccProfileName']={'en-gb': 'Linked to external file'}
                            returned['iccProfileCopyright']={'en-gb': bytes.decode('utf-8', 'ignore')}

        return returned



    # endregion: utils ---------------------------------------------------------


    # region: getter/setters ---------------------------------------------------

    @staticmethod
    def thumbnailCacheDirectory(size=None):
        """Return current thumbnail cache directory"""

        if not isinstance(size, BCFileThumbnailSize):
            # size is not a BCFileThumbnailSize (none or invalid value)
            # return root path
            return BCFile.__BC_CACHE_PATH
        else:
            return os.path.join(BCFile.__BC_CACHE_PATH, f"{size.value}")

    @staticmethod
    def metaCacheDirectory():
        """Return current metadata cache directory"""
        return os.path.join(BCFile.__BC_CACHE_PATH, 'meta')

    @staticmethod
    def setCacheDirectory(bcCachePath=None):
        """Set current cache directory

        If no value provided, reset to default value
        """
        if bcCachePath is None or bcCachePath == '':
            bcCachePath = os.path.join(QStandardPaths.writableLocation(QStandardPaths.CacheLocation), "bulicommander")
        else:
            bcCachePath = os.path.expanduser(bcCachePath)

        if not isinstance(bcCachePath, str):
            raise EInvalidType("Given `bcCachePath` must be a valid <str> ")

        try:
            BCFile.__BC_CACHE_PATH = bcCachePath

            os.makedirs(bcCachePath, exist_ok=True)
            for size in BCFileThumbnailSize:
                os.makedirs(BCFile.thumbnailCacheDirectory(size), exist_ok=True)
            os.makedirs(BCFile.metaCacheDirectory(), exist_ok=True)
        except Exception as e:
            Debug.print('[BCFile.setCacheDirectory] Unable to create directory {0}: {1}', bcCachePath, f"{e}")
            return

    @staticmethod
    def thumbnailCacheCompression(format, size):
        """Return current thumbnail cache compression parameter"""
        if format== BCFileThumbnailFormat.JPEG:
            if size in [BCFileThumbnailSize.SMALL, BCFileThumbnailSize.MEDIUM]:
                # on smaller image, jpeg compression artifact are more visible, so reduce compression
                return 95
            else:
                # on bigger image, we can reduce quality to get a better compression and save disk :)
                return 85
        else:
            # PNG compression
            return 80

    @staticmethod
    def thumbnailCacheDefaultSize():
        """Return current thumbnail cdefault cache size"""
        return BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE

    @staticmethod
    def setThumbnailCacheDefaultSize(thumbnailCacheDefaultSize=None):
        """Set current thumbnail default cache size

        If no size is provided or if invalid, set default size MEDIUM
        """
        if not isinstance(thumbnailCacheDefaultSize, BCFileThumbnailSize):
            BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE = BCFileThumbnailSize.MEDIUM
        else:
            BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE = thumbnailCacheDefaultSize

    def baseName(self):
        return self.__baseName

    def size(self):
        """Return file size"""
        return self.__size

    def extension(self, dot=True):
        """Return file extension"""
        if dot:
            return self.__extension
        else:
            return self.__extension[1:]

    def imageSize(self):
        """Return file image size"""
        return self.__imgSize

    def qHash(self):
        """Return file quick hash"""
        return self.__qHash

    def readable(self):
        """Return True if file is readable"""
        return self.__readable

    def image(self):
        """Return file image

        Note:
        - for OpenRaster, return thumbnail
        - for Krita, return merged preview

        If not possible to return image, return None
        Otherwise, return a QImage
        """
        if not self.__readable:
            return None

        if self._format in (BCFileManagedFormat.KRA, BCFileManagedFormat.KRZ):
            return self.__readKraImage()
        elif self._format == BCFileManagedFormat.ORA:
            return self.__readOraImage()
        else:
            try:
                return QImage(self._fullPathName)
            except:
                return None

    def thumbnail(self, size=None, thumbType=BCBaseFile.THUMBTYPE_IMAGE, cache=True):
        """Return file thumbnail according to current BCFile default cache size

        If `cache` is True:
            If a thumbnail already exist in cache, method will use it
            Otherwise, method will:
            - Load image
            - Reduce size
            - Save thumbnail into cache
            - Return thumbnail

        If `cache` is False:
            - Load image
            - Reduce size
            - Return thumbnail

        If not possible to return image, return None
        Otherwise, return a QImage
        """
        if not self.readable():
            return super(BCFile, self).thumbnail(size, thumbType)

        imageSrc = None

        if size is None or not isinstance(size, BCFileThumbnailSize):
            size = BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE

        if cache:
            # check if thumbnail is cached
            sourceSize = size

            while not sourceSize is None:
                thumbnailFile = os.path.join(BCFile.thumbnailCacheDirectory(sourceSize), f'{self.__qHash}')

                if os.path.isfile(thumbnailFile):
                    # thumbnail found!
                    imageSrc = QImage(thumbnailFile)

                    if sourceSize == size:
                        # the found thumbnail is already to expected size, return it
                        if thumbType==BCBaseFile.THUMBTYPE_IMAGE:
                            return imageSrc
                        elif thumbType==BCBaseFile.THUMBTYPE_ICON:
                            return QIcon(QPixmap.fromImage(imageSrc))
                        else:
                            # BCBaseFile.THUMBTYPE_FILENAME
                            return thumbnailFile
                    break

                # use larger thumbnail size as source
                sourceSize = sourceSize.next()

        thumbnailImg = None
        if not cache or imageSrc is None:
            # no image cache found
            # load full image size from file
            imageSrc = self.image()
            if imageSrc is None or imageSrc.isNull():
                return None

            if cache:
                # build all image size in cache, from the biggest to smallest
                buildSize = BCFileThumbnailSize.HUGE
                while not buildSize is None:
                    if imageSrc.width() <= buildSize.value or imageSrc.height() <= buildSize.value:
                        # when image is smaller than thumbnail
                        # create a thumbnail bigger than thumbnail o_O'
                        # without antialiasing
                        imageSrc = QImage(imageSrc.scaled(QSize(buildSize.value, buildSize.value), Qt.KeepAspectRatio, Qt.FastTransformation))
                    else:
                        imageSrc = QImage(imageSrc.scaled(QSize(buildSize.value, buildSize.value), Qt.KeepAspectRatio, Qt.SmoothTransformation))

                    thumbnailFile = os.path.join(BCFile.thumbnailCacheDirectory(buildSize), f'{self.__qHash}')
                    try:
                        if imageSrc.hasAlphaChannel():
                            imageSrc.save(thumbnailFile, BCFileThumbnailFormat.PNG.value, BCFile.thumbnailCacheCompression(BCFileThumbnailFormat.PNG, buildSize))
                        else:
                            imageSrc.save(thumbnailFile, BCFileThumbnailFormat.JPEG.value, BCFile.thumbnailCacheCompression(BCFileThumbnailFormat.JPEG, buildSize))
                    except Exception as e:
                        Debug.print('[BCFile.thumbnail] Unable to save thumbnail in cache {0}: {1}', thumbnailFile, f"{e}")

                    if size == buildSize:
                        thumbnailImg = QImage(imageSrc)

                    buildSize = buildSize.prev()

                if not thumbnailImg is None:
                    if thumbType==BCBaseFile.THUMBTYPE_IMAGE:
                        return thumbnailImg
                    elif thumbType==BCBaseFile.THUMBTYPE_ICON:
                        return QIcon(QPixmap.fromImage(thumbnailImg))
                    else:
                        # BCBaseFile.THUMBTYPE_FILENAME
                        return thumbnailFile

        if imageSrc.isNull():
            return None

        if thumbnailImg is None:
            # make thumbnail
            thumbnailImg = imageSrc.scaled(QSize(size.value, size.value), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        if not cache:
            # no need to save thumbnail
            if thumbType==BCBaseFile.THUMBTYPE_IMAGE:
                return thumbnailImg
            elif thumbType==BCBaseFile.THUMBTYPE_ICON:
                return QIcon(QPixmap.fromImage(thumbnailImg))
            else:
                # BCBaseFile.THUMBTYPE_FILENAME
                # in this case (no cache + asked for file name?) return None -- this should not occurs, otherwise I'm a dumb :)
                return None

        thumbnailFile = os.path.join(BCFile.thumbnailCacheDirectory(size), f'{self.__qHash}')
        try:
            if thumbnailImg.hasAlphaChannel():
                thumbnailImg.save(thumbnailFile, BCFileThumbnailFormat.PNG.value, BCFile.thumbnailCacheCompression(BCFileThumbnailFormat.PNG, size))
            else:
                thumbnailImg.save(thumbnailFile, BCFileThumbnailFormat.JPEG.value, BCFile.thumbnailCacheCompression(BCFileThumbnailFormat.JPEG, size))
        except Exception as e:
            Debug.print('[BCFile.thumbnail] Unable to save thumbnail in cache {0}: {1}', thumbnailFile, f"{e}")

        # finally, return thumbnail
        if thumbType==BCBaseFile.THUMBTYPE_IMAGE:
            return thumbnailImg
        elif thumbType==BCBaseFile.THUMBTYPE_ICON:
            return QIcon(QPixmap.fromImage(thumbnailImg))
        else:
            # BCBaseFile.THUMBTYPE_FILENAME
            return thumbnailFile

    def getProperty(self, property):
        """return property value"""
        if property == BCFileProperty.FILE_SIZE:
            return self.__size
        elif property == BCFileProperty.FILE_EXTENSION:
            return self.__extension
        elif property == BCFileProperty.IMAGE_WIDTH:
            return self.__imgSize.width()
        elif property == BCFileProperty.IMAGE_HEIGHT:
            return self.__imgSize.height()
        elif isinstance(property, str) and property in self.__metadata:
            return self.__metadata[property]
        elif isinstance(property, BCFileProperty) and property.value in self.__metadata:
            return self.__metadata[property.value]
        else:
            return super(BCFile, self).getProperty(property)

    def getInformation(self):
        if self._format in [BCFileManagedFormat.JPEG, BCFileManagedFormat.PNG, BCFileManagedFormat.SVG]:
            imageReader = QImage(self._fullPathName)
            keys = imageReader.textKeys()

    def getMetaInformation(self, getExtraData=False):
        """Return metadata informations"""
        if self._format in (BCFileManagedFormat.KRA, BCFileManagedFormat.KRZ):
            return self.__readMetaDataKra(True, getExtraData)
        elif self._format == BCFileManagedFormat.ORA:
            return self.__readMetaDataOra(True, getExtraData)
        elif self._format == BCFileManagedFormat.PNG:
            return self.__readMetaDataPng(True, getExtraData)
        elif self._format == BCFileManagedFormat.JPEG:
            return self.__readMetaDataJpeg(True, getExtraData)
        elif self._format == BCFileManagedFormat.GIF:
            return self.__readMetaDataGif(True, getExtraData)
        elif self._format == BCFileManagedFormat.WEBP:
            return self.__readMetaDataWebP(True, getExtraData)
        elif self._format == BCFileManagedFormat.PSD:
            return self.__readMetaDataPsd(True, getExtraData)
        elif self._format == BCFileManagedFormat.XCF:
            return self.__readMetaDataXcf(True, getExtraData)
        elif self._format == BCFileManagedFormat.BMP:
            return self.__readMetaDataBmp(True, getExtraData)
        else:
            return {}

    def hash(self, method, chunkSize=8192):
        """Return hash for file, using method (md5, sha1, sha256, sha512)

        Hash is stored in cache
        """
        if not method in ('md5', 'sha1', 'sha256', 'sha512'):
            raise EInvalidValue('Given `method` value must be "md5", "sha1", "sha256" or "sha512"')

        if os.path.isfile(self._fullPathName):
            _mdatetime = os.path.getmtime(self._fullPathName)
        else:
            return super(BCFile, self).hash(method)

        if self._mdatetime != _mdatetime or self.__hashCache[method] is None:
            # recalculate hash
            fileHash={
                    'md5': hashlib.md5(),
                    'sha1': hashlib.sha1(),
                    'sha256': hashlib.sha256(),
                    'sha512': hashlib.sha512()
                }

            with open(self._fullPathName, "rb") as fileHandle:
                buffer=fileHandle.read(chunkSize)
                while buffer:
                    fileHash[method].update(buffer)
                    buffer=fileHandle.read(chunkSize)

                self.__hashCache[method]=fileHash[method].hexdigest()

        return self.__hashCache[method]

    # endregion: getter/setters ------------------------------------------------

# ------------------------------------------------------------------------------

class BCWorkerCache(Worker):
    """A worker class that allows to work with BCFile and BCFileCache in a WorkerPool"""

    def __init__(self, pool, callback, *callbackArgv):
        self.__dbFileCache=BCFileCache(QUuid.createUuid().toString().strip('{}').replace('-',''))
        super(BCWorkerCache, self).__init__(pool, callback, self.__dbFileCache, *callbackArgv)

    def startEvent(self):
        """Worker will start execution; begin transaction mode for BCFileCache database"""
        self.__dbFileCache.beginTransaction()

    def cleanupEvent(self):
        """Worker have finished and is about to stop; close transaction mode and commit chnage for BCFileCache database"""
        # close database connexion
        self.__dbFileCache.commitTransaction()
        self.__dbFileCache.close()


class BCFileCache(QObject):
    """Manage BCFile cache in a SQLite database"""

    # Cache is stored in a SQLite file to improve performances
    # - use less space on disk than unitary file
    # - avoid to open/close files (faster to read content from sqlite file than on many small files)
    #   => https://www.sqlite.org/fasterthanfs.html
    #
    # Problem:
    #   => Cache is (in most case) read/updated through workers
    #   As it seems SQlite support multithreaded connection, different test made with QSqlDatabase connections
    #   return some problems:
    #   - Outside transaction: slow
    #   - Within transaction:
    #       . the first worker who start a transactoin lock the database
    #       . then, all other worker waits for database is unlocked to be able to work
    #       . the, only the first worker process data files... (so useless multithreading...)
    #
    # Solution:
    #   *Not the most elegant solution found*
    #
    #   When reading metadata from database file, if not found, BCFile (instancied from worker)
    #   needs to read metadata from file and write it to database file
    #
    #   The solution is to write in an attached database
    #   Attached database is in memory, for performances
    #   When worker is terminated, data from memory database is flushed to database file
    #
    #
    #                       ╔═══════════════════════════════════════╗
    #                       ║ ┌───┬───┬───┬───┬───┬───┬───┬───┬───┐ ║
    # Pool of data          ║ │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ ..... │ N │ ║           Pool contains a list of files to process
    #                       ║ └───┴───┴───┴───┴───┴───┴───┴───┴───┘ ║
    #                       ╚═╤══════╤══════╤══════╤══════╤══════╤══╝
    #                         ┊      ┊      ┊      ┊      ┊      ┊
    #                         ▽      ▽      ▽      ▽      ▽      ▽
    #                         ┊      ┊      ┊      ┊      ┊      ┊
    #                       ┌─┴─┐  ┌─┴─┐  ┌─┴─┐  ┌─┴─┐  ┌─┴─┐  ┌─┴─┐            Each worker is connected to pool of data to process,
    #  Workers              │ 1 │  │ 2 │  │ 3 │  │...│  │...│  │ n │            picking next available data in pool
    #                       └─┬─┘  └─┬─┘  └─┬─┘  └─┬─┘  └─┬─┘  └─┬─┘
    #                         ┊      ┊      ┊      ┊      ┊      ┊
    #                         △      △      △      △      △      △
    #                         ▽      ▽      ▽      ▽      ▽      ▽
    #                         ┊      ┊      ┊      ┊      ┊      ┊
    #                       ┌─┴─┐  ┌─┴─┐  ┌─┴─┐  ┌─┴─┐  ┌─┴─┐  ┌─┴─┐            Need one database connection per thread
    #  DB Connection        │ 1 │  │ 2 │  │ 3 │  │...│  │...│  │ n │            (Different thread can't use the same database connection)
    #                       └─┬─┘  └─┬─┘  └─┬─┘  └─┬─┘  └─┬─┘  └─┬─┘
    #                         ┊      ┊      ┊      ┊      ┊      ┊
    #                         △      △      △      △      △      △
    #                         ▽      ▽      ▽      ▽      ▽      ▽
    #                         ┊      ┊      ┊      ┊      ┊      ┊
    #                      ╭╌╌┤   ╭╌╌┤   ╭╌╌┤   ╭╌╌┤   ╭╌╌┤   ╭╌╌┤
    #                    ┌─┴─┐┊ ┌─┴─┐┊ ┌─┴─┐┊ ┌─┴─┐┊ ┌─┴─┐┊ ┌─┴─┐┊
    #  Memory database   │ 1 │┊ │ 2 │┊ │ 3 │┊ │...│┊ │...│┊ │ n │┊              ATTACH a :memory: database on each connection
    #                    └───┘┊ └───┘┊ └───┘┊ └───┘┊ └───┘┊ └───┘┊              Allows to write
    #                         ┊      ┊      ┊      ┊      ┊      ┊
    #                       ╔═╧══════╧══════╧══════╧══════╧══════╧══╗           Workers:
    #                       ║                                       ║           . read from database file
    #  Database file        ║                                       ║           . write to attached memory database
    #                       ║                                       ║           . flush content of memory database to file when terminated
    #                       ╚═══════════════════════════════════════╝
    #
    #  This solution allows to get good performances and maintain a metadata cache
    #  up to date
    #
    #  But there's exception
    #  In case of files with differents names but same content (same hash), if database is not yet up to date
    #  with metadata, then each worker will read file and update attached memory database
    #
    #  This case is not considered as a problem; first time workers will encounter it, metadata will be processed X times
    #  but execution time is insignificant
    #

    __BC_CACHE_PATH=''
    __BC_CACHE_FILE=None
    __DB_EXPECTED_VERSION=100   #1.00

    __GLOBAL_INSTANCE=None

    @staticmethod
    def __setCacheDirectory(bcCachePath=None):
        """Set current cache directory

        If no value provided, reset to default value
        """
        if bcCachePath is None or bcCachePath == '':
            bcCachePath = os.path.join(QStandardPaths.writableLocation(QStandardPaths.CacheLocation), "bulicommander")
        else:
            bcCachePath = os.path.expanduser(bcCachePath)

        if not isinstance(bcCachePath, str):
            raise EInvalidType("Given `bcCachePath` must be a valid <str> ")

        try:
            BCFileCache.__BC_CACHE_PATH = bcCachePath

            os.makedirs(bcCachePath, exist_ok=True)
        except Exception as e:
            Debug.print('[BCFile.setCacheDirectory] Unable to create directory: {0} / {1}', bcCachePath, f"{e}")

    @staticmethod
    def initialise(bcCachePath=None):
        """Initialise cache

        If no database cache exists, create it
        """
        BCFileCache.__setCacheDirectory(bcCachePath)
        if BCFileCache.__GLOBAL_INSTANCE is None:
            BCFileCache.__GLOBAL_INSTANCE=BCFileCache()

    @staticmethod
    def finalize():
        if not BCFileCache.__GLOBAL_INSTANCE is None:
            BCFileCache.__GLOBAL_INSTANCE.close()
            BCFileCache.__GLOBAL_INSTANCE=None

    @staticmethod
    def cacheDirectory():
        """Return current cache directory"""
        return BCFileCache.__BC_CACHE_PATH

    @staticmethod
    def cacheFile():
        """Return SQlite databse cache file"""
        if BCFileCache.__BC_CACHE_FILE is None:
            BCFileCache.__BC_CACHE_FILE=os.path.join(BCFileCache.__BC_CACHE_PATH, f'metaDataCache.sqlite')
        return BCFileCache.__BC_CACHE_FILE

    @staticmethod
    def globalInstance():
        """Return a global instance of cache database"""
        if BCFileCache.__GLOBAL_INSTANCE is None:
            BCFileCache.initialise()
        return BCFileCache.__GLOBAL_INSTANCE

    def __init__(self, id=None):
        """Given `id` is used when database is accessed through Workers; each thread need its own database reference

        Also when `id` is provided, setMeta will write into attached memory database
        """
        super(BCFileCache, self).__init__()

        self.__id=id

        if isinstance(id, str):
            self.__databaseInstance=QSqlDatabase.addDatabase("QSQLITE", f"dbBCFileCache{self.__id}")
        else:
            self.__databaseInstance=QSqlDatabase.addDatabase("QSQLITE", f"dbBCFileCache")

        # current database file version
        self.__db_version=0
        # prepared queries
        self.__databaseQuerySetMetadata=None
        self.__databaseQueryGetMetadata=None
        self.__databaseQuerySetDirectory=None
        self.__databaseQueryGetDirectory=None

        # database filename
        self.__fileName=BCFileCache.cacheFile()

        # flag to determinate if there's data to flush
        self.__dataToFlush=False

        self.__open()

    def __initializeQueries(self):
        """Initialise default queries"""
        if self.__databaseInstance is None:
            return

        # prepare query that will be used to set metadata in cache
        if self.__id is None:
            dbSchema=''
        else:
            dbSchema='`tmpDb`.'
        self.__databaseQuerySetMetadata=QSqlQuery(self.__databaseInstance)
        self.__databaseQuerySetMetadata.prepare(f"""
                INSERT INTO {dbSchema}`metadata` (hash, metadata, fileFormat)
                            VALUES(:hash, :metadata, :fileFormat)
                ON CONFLICT(hash)
                            DO UPDATE SET metadata=:metadata
            """)

        # prepare query that will be used to get metadata in cache
        self.__databaseQueryGetMetadata=QSqlQuery(self.__databaseInstance)
        self.__databaseQueryGetMetadata.prepare("""
                SELECT metadata
                FROM metadata
                WHERE hash=:hash
            """)

        # prepare query that will be used to set cached directories list
        self.__databaseQuerySetDirectories=QSqlQuery(self.__databaseInstance)
        self.__databaseQuerySetDirectories.prepare("""
                INSERT INTO directories (path, timestamp)
                            VALUES(:path, strftime('%s', 'now', 'localtime'))
                ON CONFLICT(path)
                            DO UPDATE SET timestamp=excluded.timestamp
            """)

        # prepare query that will be used to get cached directories list
        self.__databaseQueryGetDirectories=QSqlQuery(self.__databaseInstance)
        self.__databaseQueryGetDirectories.prepare("""
                SELECT path, timestamp
                FROM directories
            """)

    def __updateDatabaseVersion(self):
        """Update database version"""
        sqlQuery=QSqlQuery(self.__databaseInstance)
        upToDate=True
        version=0

        if self.__db_version==0:
            # need to create database schema
            updatedVersion=100

            # Create the main metadata table
            #   This table contains image metadata for each file
            #       hash=       unique primary key ==> file hash
            #       metadata=   metadata stored as json string
            #       fileFormat= file type (BCFileManagedFormat value)
            #                   --> if metadata parser is improved for given file type,
            #                       we'll need to delete them in cache to force metadata
            #                       being regenerated
            if upToDate and not sqlQuery.exec("""
                CREATE TABLE `metadata` (
                    `hash` TEXT NOT NULL UNIQUE,
                    `metadata` TEXT,
                    `fileFormat` TEXT,
                    PRIMARY KEY(`hash`)
                )"""):
                    upToDate=False

            # Create the directories table
            #   path=           directory location
            #   timestamp=      last time directory has been scanned
            if upToDate and not sqlQuery.exec("""
                CREATE TABLE `directories` (
                    `path` TEXT NOT NULL UNIQUE,
                    `timestamp` REAL,
                    PRIMARY KEY(`path`)
                )"""):
                    upToDate=False

        if upToDate and not self.__id is None:
            # create temporary metadata table in an "memory" database if
            # an id has been provided
            if not sqlQuery.exec("""
                CREATE TABLE `tmpDb`.`metadata` (
                    `hash` TEXT NOT NULL UNIQUE,
                    `metadata` TEXT,
                    `fileFormat` TEXT,
                    PRIMARY KEY(`hash`)
                )"""):
                upToDate=False

        if upToDate:
            # all tables has been created!
            if self.__db_version!=BCFileCache.__DB_EXPECTED_VERSION:
                # update version if needed
                if sqlQuery.exec(f"PRAGMA user_version={updatedVersion}"):
                    self.__db_version=updatedVersion
                else:
                    upToDate=False

        if not upToDate:
            # unable to create/update database schema
            Debug.print(f"[BCFileCache.__updateDatabaseVersion] Unable to create/update cache database schema: 0.00 ==> {updatedVersion/100:.2f}", )

        sqlQuery.finish()

        return upToDate

    def __flushMemoryDatabase(self):
        """Flush data from memory database"""
        if self.__databaseInstance is None or self.__id is None or not self.__dataToFlush:
            return False

        sqlQuery=QSqlQuery(self.__databaseInstance)
        # WHERE clause is mandatory to let parser being able to understand the ON CONFLICT statement
        #  https://www.sqlite.org/lang_upsert.html
        #  chapter 2.2 Parsing Ambiguity
        #sqlQuery.exec("BEGIN IMMEDIATE TRANSACTION")
        if sqlQuery.exec("""
                INSERT INTO metadata (hash, metadata, fileFormat)
                    SELECT hash, metadata, fileFormat FROM tmpDb.metadata
                    WHERE true
                ON CONFLICT(hash)
                    DO UPDATE SET metadata=excluded.metadata,
                                  fileFormat=excluded.fileFormat
            """):
            self.__dataToFlush=False
            #sqlQuery.exec("COMMIT TRANSACTION")
            sqlQuery.finish()
            return True
        #sqlQuery.exec("ROLLBACK TRANSACTION")
        sqlQuery.finish()
        return False

    def __open(self):
        """Open database"""
        if self.__databaseInstance is None:
            if isinstance(self.__id, str):
                self.__databaseInstance=QSqlDatabase.addDatabase("QSQLITE", f"dbBCFileCache{self.__id}")
            else:
                self.__databaseInstance=QSqlDatabase.addDatabase("QSQLITE",  "dbBCFileCache")

        self.__databaseInstance.setDatabaseName(self.__fileName)

        if self.__databaseInstance.open():
            # database is opened, prepare database
            sqlQuery=QSqlQuery(self.__databaseInstance)

            # create a temporary database in memory
            # will be used to insert/update cache data in multithread mode
            if not sqlQuery.exec(f"ATTACH DATABASE ':memory:' AS tmpDb"):
                # can't attach memory database??
                # do not continue
                self.__databaseInstance.close()
                self.__databaseInstance=None
                return False

            # need to check version
            if sqlQuery.exec("PRAGMA user_version"):
                while sqlQuery.next():
                    self.__db_version=sqlQuery.value('user_version')
                    break

                if not self.__updateDatabaseVersion():
                    # database schema is not correct and/or unable to create/update database schema
                    self.__databaseInstance.close()
                    self.__databaseInstance=None
                    return False

            self.__initializeQueries()

            # db settings
            for pragma in ["PRAGMA journal_mode=WAL"]:
                if not sqlQuery.exec(pragma):
                    Debug.print(f"Can't set: {pragma}")

            return True
        else:
            return False

    def fileName(self):
        """Return current database file name"""
        return self.__fileName

    def close(self):
        """Close cache database if open"""
        if self.__databaseInstance:
            self.__flushMemoryDatabase()
            if not self.__id is None:
                self.__databaseInstance.exec(f"DETACH DATABASE tmpDb")
            self.__databaseInstance.close()
            self.__databaseInstance=None

            if isinstance(self.__id, str):
                QSqlDatabase.removeDatabase(f"dbBCFileCache{self.__id}")
            else:
                QSqlDatabase.removeDatabase("dbBCFileCache")

    def setMetadata(self, hash, metadata):
        """Set `metadata` for `hash`

        If exist, update otherwise insert
        If database is not opened, do nothing

        Return True if metadata are set, otherwise false
        """
        if self.__databaseInstance is None:
            return False

        if isinstance(metadata, dict) and 'format' in metadata:
            fileFormat=metadata['format']
            # convert it to string
            try:
                metadata=json.dumps(metadata, cls=JsonQObjectEncoder)
            except Exception as e:
                metadata='{isNotValidJson:true}'
        else:
            fileFormat=BCFileManagedFormat.UNKNOWN
            metadata='{}'

        self.__databaseQuerySetMetadata.bindValue(":hash", hash)
        self.__databaseQuerySetMetadata.bindValue(":metadata", metadata)
        self.__databaseQuerySetMetadata.bindValue(":fileFormat", fileFormat)

        if self.__databaseQuerySetMetadata.exec():
            self.__dataToFlush=(not self.__id is None)
            return True
        return False

    def getMetadata(self, hash):
        """Return `metadata` for `hash`

        If exist, Metadata are returned as a dictionnary
        Otherwise return None
        If database is not opened, return None
        """
        if self.__databaseInstance is None:
            return None

        self.__databaseQueryGetMetadata.bindValue(":hash", hash)
        if self.__databaseQueryGetMetadata.exec():
            while self.__databaseQueryGetMetadata.next():
                try:
                    return json.loads(self.__databaseQueryGetMetadata.value('metadata'), cls=JsonQObjectDecoder)
                except Exception as e:
                    Debug.print('Unable to load meta cache data ({2}) {0}: {1}', self.__databaseQueryGetMetadata.value('metadata'), f"{e}", hash)
                    return None
        return None

    def setDirectory(self, directory):
        """Set given directory in list"""
        if self.__databaseInstance is None:
            return False

        if isinstance(directory, list):
            nbKo=0
            inTransaction=self.beginTransaction()
            for path in directory:
                if not self.setDirectory(path):
                    nbKo+=1
            if inTransaction:
                return self.commitTransaction() and (nbKo==0)
        elif isinstance(directory , str):
            self.__databaseQuerySetDirectories.bindValue(":path", directory)
            if self.__databaseQuerySetDirectories.exec():
                return True
        return False

    def getDirectory(self):
        """Return list of all directories as a dictionnary
            key=path
            value=timestamp (last time directory has been scanned)

        If database is not opened, return empty list
        """
        returned={}
        if self.__databaseInstance is None:
            return returned

        if self.__databaseQueryGetDirectories.exec():
            while self.__databaseQueryGetDirectories.next():
                returned[self.__databaseQueryGetDirectories.value('path')]=self.__databaseQueryGetDirectories.value('timestamp')

        return returned

    def beginTransaction(self):
        """Begin a transaction if possible, otherwise is ignored

        If an Id is provided, means we're working on memory database, and then ignore transaction action
        """
        if self.__databaseInstance is None or not self.__databaseInstance.driver().hasFeature(QSqlDriver.Transactions) or not self.__id is None:
            return False
        return self.__databaseInstance.exec("BEGIN DEFERRED TRANSACTION")

    def commitTransaction(self):
        """Commit a transaction if possible, otherwise is ignored

        If an Id is provided, means we're working on memory database, and then ignore transaction action
        """
        if self.__databaseInstance is None or not self.__databaseInstance.driver().hasFeature(QSqlDriver.Transactions) or not self.__id is None:
            return False
        return self.__databaseInstance.exec("COMMIT TRANSACTION")

    def rollbackTransaction(self):
        """Rollback a transaction if possible, otherwise is ignored

        If an Id is provided, means we're working on memory database, and then ignore transaction action
        """
        if self.__databaseInstance is None or not self.__databaseInstance.driver().hasFeature(QSqlDriver.Transactions):
            return False
        return self.__databaseInstance.exec("ROLLBACK TRANSACTION")

    def getStats(self):
        """Return statistics about database cache"""
        returned={
                'dbFile': self.__fileName,
                'dbSize': 0,
                'nbHash': 0,
                'nbDir': 0,
            }
        #print('getStats')

        if os.path.isfile(self.__fileName):
            returned['dbSize']=os.path.getsize(self.__fileName)

            for ext in ('-shm', '-wal'):
                fileName=f"{self.__fileName}{ext}"
                if os.path.isfile(fileName):
                    returned['dbSize']+=os.path.getsize(fileName)

        if self.__databaseInstance is None:
            #print('getStats: self.__databaseInstance is None')
            return returned

        query=QSqlQuery(self.__databaseInstance)

        if query.exec("SELECT count(*) AS nbHash FROM metadata"):
            #print('getStats: metadata')
            while query.next():
                #print('getStats: metadata - '+f"{query.value('nbHash'}"))
                returned['nbHash']=int(query.value('nbHash'))

        if query.exec("SELECT count(*) AS nbDir FROM directories"):
            while query.next():
                returned['nbDir']=int(query.value('nbDir'))

        query.finish()

        #print('getStats', returned)

        return returned

    def clearDbContent(self):
        """Clear database content"""
        if self.__databaseInstance is None:
            return False

        query=QSqlQuery(self.__databaseInstance)

        self.beginTransaction()
        query.prepare("DELETE FROM metadata")
        if query.exec():
            query.prepare("DELETE FROM directories")
            self.commitTransaction()
            if query.exec():
                return self.vacuum()
        self.rollbackTransaction()
        return False

    def vacuum(self):
        """Rebuild database content"""
        if self.__databaseInstance is None:
            return


        # to avoid SQL error: "cannot VACUUM - SQL statements in progress Unable to fetch row"
        # need to be seure that all SQL statement are processed

        # to be sure:
        # - close the current SQL connection
        # - open a new connection (do not used method __open(); we just need a simple connection without all checks & temp db)
        # - do VACUUM
        # - force WAL checkpoint
        # - close connection
        # - reopen standard connection using __open() method
        self.close()

        tmpDbVacuum=QSqlDatabase.addDatabase("QSQLITE",  "tmpDbVacuum")
        tmpDbVacuum.setDatabaseName(self.__fileName)
        tmpDbVacuum.open()
        tmpDbVacuum.exec("VACUUM")
        tmpDbVacuum.exec("PRAGMA wal_checkpoint(TRUNCATE)")
        tmpDbVacuum.close()
        tmpDbVacuum=QSqlDatabase.removeDatabase("tmpDbVacuum")

        self.__open()


# ------------------------------------------------------------------------------


class BCFileListRuleOperatorType(Enum):
    """Possible rule operator value type"""
    INT = 0
    FLOAT = 1
    DATE = 2
    DATETIME = 3
    STRING = 4
    LIST = 5
    ENUM = 6
    REGEX = 7


class BCFileListRuleOperator(object):
    """Store properties for a rule:
    - Value (to compare)
    - Displayed value (for string representation)
    - Operator

    Do controls about value type and allows to do comparison with another value
    """
    def __init__(self, value, operator=None, type=None, displayValue=None):
        """Operator need:
        - `value`           => value to compare
        - `operator`        => operator to apply, can be
                                type==REGEX: 'match', 'not match'

                                    '=', '<>', '<', '>', '<=', '>=', 'in', 'between', 'not in', 'not between'
        - `type`            => comparison type (must be BCFileListRuleOperatorType)
        - `displayValue`    => value displayed for user interface
        """
        self.__type = None
        self.__operator = None
        self.__value = None
        self.__displayValue = None

        if isinstance(value, BCFileListRuleOperator):
            self.__type = value.type()
            self.__setOperator(value.operator())
            self.setValue(value.value(), value.displayValue())
        else:
            if not isinstance(type, BCFileListRuleOperatorType):
                raise EInvalidType("Rule type must be of type <BCFileListRuleOperatorType>")

            self.__type = type

            self.__setOperator(operator)
            self.setValue(value, displayValue)

    def __checkValueType(self, value=None):
        """Check if given value match to expected type"""
        if value is None:
            value = self.__value

        if isinstance(value, list) or isinstance(value, tuple):
            values = value
        elif self.__type == BCFileListRuleOperatorType.LIST:
            if not (isinstance(value, list) or isinstance(value, tuple)):
                raise EInvalidType("Given value type must be <list>")
            else:
                return
        else:
            values = [value]

        for value in values:
            # check if all item in list match given type
            if self.__type == BCFileListRuleOperatorType.INT and not isinstance(value, int):
                raise EInvalidType("Given value type must be <int>")
            elif self.__type == BCFileListRuleOperatorType.FLOAT and not isinstance(value, float):
                raise EInvalidType("Given value type must be <float>")
            elif self.__type in [BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME] and not (isinstance(value, float) or isinstance(value, int)):
                raise EInvalidType("Given value type must be <float>")
            elif self.__type == BCFileListRuleOperatorType.STRING and not isinstance(value, str):
                raise EInvalidType("Given value type must be <str>")
            elif self.__type == BCFileListRuleOperatorType.ENUM and not isinstance(value, Enum):
                raise EInvalidType("Given value type must be <Enum>")
            if self.__type == BCFileListRuleOperatorType.REGEX and not isinstance(value, re.Pattern):
                raise EInvalidType("Given value type must be <re.Pattern>")

    def __setOperator(self, value):
        """Set current operator"""
        if self.__type == BCFileListRuleOperatorType.REGEX:
            if not value is None and value.lower() in ['match', 'not match']:
                # in this case, operator is 'match' or 'not match':
                self.__operator = value.lower()
            else:
                raise EInvalidValue("Given `operator` must be one of the following value: 'match', 'not match'")
        elif not value is None and value.lower() in ['=', '<>', '<', '>', '<=', '>=', 'in', 'between', 'not in', 'not between']:
            self.__operator = value.lower()
        elif value == '!=':
            self.__operator = '<>'
        else:
            raise EInvalidValue("Given `operator` must be one of the following value: '=', '<>', '<', '>', '<=', '>=', 'in', 'between', 'not in', 'not between'")

    def __str__(self):
        """Return rule operator as string"""
        value = self.__value
        if self.__type == BCFileListRuleOperatorType.ENUM and isinstance(value, Enum):
            value = value.value

        if isinstance(value, list) and self.__operator in ['in', 'not in']:
            return f"{self.__operator} {self.__enumToStr(value)}"
        elif isinstance(value, tuple) and self.__operator in ['between', 'not between']:
            if self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM]:
                return f'{self.__operator} ("{self.__enumToStr(value[0])}", "{self.__enumToStr(value[1])}")'
            else:
                return f"{self.__operator} ({value[0]}, {value[1]})"
        elif self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM]:
            return f'{self.__operator} "{value}"'
        elif self.__type == BCFileListRuleOperatorType.REGEX:
            return f'{self.__operator} "{value.pattern}"'
        else:
            return f"{self.__operator} {value}"

    def __enumToStr(self, value):
        """return printable value for enum"""
        if self.__type == BCFileListRuleOperatorType.ENUM:
            if isinstance(value, tuple):
                return tuple([v.value for v in value])
            elif isinstance(value, list):
                return [v.value for v in value]
            else:
                return value.value
        return value

    def type(self):
        """Return current type"""
        return self.__type

    def displayValue(self):
        """Return current set displayValue"""
        return self.__displayValue

    def value(self):
        """Return current set value"""
        return self.__value

    def setValue(self, value, displayValue=None):
        """Set current value"""
        if value is None:
            raise EInvalidValue("Given value can't be None")

        if self.__type == BCFileListRuleOperatorType.REGEX and isinstance(value, str):
            self.__value = re.compile(value)
        elif self.__operator == 'in':
            if isinstance(value, tuple):
                self.__value = list(value)
            elif isinstance(value, list):
                self.__value = value
            else:
                self.__value = [value]
        elif self.__operator == 'between':
            if isinstance(value, tuple):
                self.__value = value[0:2]
            elif isinstance(value, list):
                self.__value = tuple(value[0:2])
            else:
                self.__value = (value, value)
        else:
            self.__value = value

        if displayValue is None:
            if self.__type == BCFileListRuleOperatorType.DATETIME:
                if isinstance(self.__value, tuple):
                    self.__displayValue = tuple([tsToStr(value) for value in self.__value])
                elif isinstance(self.__value, list):
                    self.__displayValue = [tsToStr(value) for value in self.__value]
                else:
                    self.__displayValue = tsToStr(self.__value)
            elif self.__type == BCFileListRuleOperatorType.DATE:
                if isinstance(self.__value, tuple):
                    self.__displayValue = tuple([tsToStr(value, 'd') for value in self.__value])
                elif isinstance(self.__value, list):
                    self.__displayValue = [tsToStr(value, 'd') for value in self.__value]
                else:
                    self.__displayValue = tsToStr(self.__value, 'd')
            elif self.__type == BCFileListRuleOperatorType.REGEX:
                self.__displayValue = self.__value.pattern
            else:
                self.__displayValue = self.__value
        else:
            self.__displayValue = displayValue

        self.__checkValueType()

    def operator(self):
        """Return current set operator"""
        return self.__operator

    def translate(self, short=False):
        returned = ''
        if short:
            if self.__operator == 'between':
                returned = i18n('between ({0}, {1})')
            elif self.__operator == 'not between':
                returned = i18n('not between ({0}, {1})')
            else:
                returned = self.__operator + ' '
        elif self.__operator == '=':
            returned = i18n('is equal to ')
        elif self.__operator == '<>':
            returned = i18n('is not equal to ')
        elif self.__operator == '<':
            returned = i18n('is lower than ')
        elif self.__operator == '>':
            returned = i18n('is greater than ')
        elif self.__operator == '<=':
            returned = i18n('is lower or equal than ')
        elif self.__operator == '>=':
            returned = i18n('is greater or equal than ')
        elif self.__operator == 'in':
            returned = i18n('is in ')
        elif self.__operator == 'between':
            returned = i18n('is between {0} and {1}')
        elif self.__operator == 'match':
            returned = i18n('match ')
        elif self.__operator == 'not match':
            returned = i18n('not match ')
        elif self.__operator == 'not in':
            returned = i18n('is not in ')
        elif self.__operator == 'not between':
            returned = i18n('is not between {0} and {1}')
        else:
            # shnould not occurs
            returned =self.__operator + ' '

        value = self.__displayValue
        if isinstance(value, Enum):
            value = value.value

        if isinstance(value, list) and self.__operator in ['in', 'not in']:

            if self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM, BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME]:
                returned += '["'+ '", "'.join([self.__enumToStr(v) for v in value]) +'"]'
            else:
                returned += '['+ ', '.join([self.__enumToStr(v) for v in value]) +']'

        elif isinstance(value, tuple) and self.__operator in ['between', 'not between']:
            if self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM, BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME]:
                returned = returned.format(f'"{self.__enumToStr(value[0])}"', f'"{self.__enumToStr(value[1])}"')
            else:
                returned = returned.format(value[0], value[1])
        elif self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM, BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME, BCFileListRuleOperatorType.REGEX]:
            returned += f'"{value}"'
        else:
            returned += f"{value}"

        return returned

    def compare(self, value):
        """Compare value according to current rule, and return True or False"""
        if self.__type == BCFileListRuleOperatorType.REGEX:
            if not isinstance(value, str):
                raise EInvalidType("Given value type must be <str>")
        elif not self.__type in [BCFileListRuleOperatorType.LIST]:
            self.__checkValueType(value)

        if self.__operator == '=':
            return (value == self.__value)
        elif self.__operator == '<>':
            return (value != self.__value)
        elif self.__operator == '<':
            return (value < self.__value)
        elif self.__operator == '>':
            return (value > self.__value)
        elif self.__operator == '<=':
            return (value <= self.__value)
        elif self.__operator == '>=':
            return (value >= self.__value)
        elif self.__operator == 'in':
            return (value in self.__value)
        elif self.__operator == 'between':
            return (self.__value[0] <= value and value <= self.__value[1])
        elif self.__operator == 'not in':
            return not(value in self.__value)
        elif self.__operator == 'not between':
            return not(self.__value[0] <= value and value <= self.__value[1])
        elif self.__operator == 'match':
            return not(self.__value.search(value) is None)
        elif self.__operator == 'not match':
            return (self.__value.search(value) is None)
        else:
            # should not occurs
            return False


class BCFileListRule(object):
    """Define single rules to search files"""

    def __init__(self, source=None):
        """Initialise a rule"""
        self.__name = None
        self.__path = None
        self.__size = None
        self.__mdatetime = None
        self.__format = None
        self.__imageWidth = None
        self.__imageHeight = None
        self.__imageRatio = None
        self.__imagePixels = None
        self.__hash=0
        self.__updateHash()

        if isinstance(source, BCFileListRule):
            self.setName(source.name())
            self.setPath(source.path())
            self.setSize(source.size())
            self.setModifiedDateTime(source.modifiedDateTime())
            self.setFormat(source.format())
            self.setImageWidth(source.imageWidth())
            self.setImageHeight(source.imageHeight())

    def __str__(self):
        """Return rule as string"""

        returned = []

        if not self.__name is None:
            returned.append(f"{BCFileProperty.FILE_NAME.value} {self.__name.translate(True)}")

        if not self.__path is None:
            returned.append(f"{BCFileProperty.PATH.value} {self.__path.translate(True)}")

        if not self.__size is None:
            returned.append(f"{BCFileProperty.FILE_SIZE.value} {self.__size.translate(True)}")

        if not self.__mdatetime is None:
            returned.append(f"{BCFileProperty.FILE_DATE.value} {self.__mdatetime.translate(True)}")

        if not self.__format is None:
            returned.append(f"{BCFileProperty.FILE_FORMAT.value} {self.__format.translate(True)}")

        if not self.__imageWidth is None:
            returned.append(f"{BCFileProperty.IMAGE_WIDTH.value} {self.__imageWidth.translate(True)}")

        if not self.__imageHeight is None:
            returned.append(f"{BCFileProperty.IMAGE_HEIGHT.value} {self.__imageHeight.translate(True)}")

        if not self.__imageRatio is None:
            returned.append(f"{BCFileProperty.IMAGE_RATIO.value} {self.__imageRatio.translate(True)}")

        if not self.__imagePixels is None:
            returned.append(f"{BCFileProperty.IMAGE_PIXELS.value} {self.__imagePixels.translate(True)}")

        return ' and '.join(returned)

    def __repr__(self):
        """Return rule as string"""
        return f'<BCFileListRule(path {self.__path}; name {self.__name}; fileSize {self.__size}; datetime {self.__mdatetime}; format {self.__format}; width {self.__imageWidth}; height {self.__imageHeight}; hash={self.__hash:016x})>'

    def __eq__(self, other):
        """Return if other BCFileListRule is the same than current one"""
        if isinstance(other, BCFileListRule):
            return (self.__hash == other.__hash)
        return False

    def __hash__(self):
        """Return hash for BCFileRule"""
        return self.__hash

    def __updateHash(self):
        """Return a hash from rule"""
        self.__hash=hash((self.__name,
                          self.__path,
                          self.__size,
                          self.__mdatetime,
                          self.__format,
                          self.__imageWidth,
                          self.__imageHeight,
                          self.__imageRatio,
                          self.__imagePixels))

    def translate(self, short=False):
        """Return rule as a human readable string"""
        returned = []

        if short:
            return self.__str__()

        if not self.__name is None:
            returned.append(f"{BCFileProperty.FILE_NAME.translate()} {self.__name.translate()}")

        if not self.__path is None:
            returned.append(f"{BCFileProperty.PATH.translate()} {self.__path.translate()}")

        if not self.__size is None:
            returned.append(f"{BCFileProperty.FILE_SIZE.translate()} {self.__size.translate()}")

        if not self.__mdatetime is None:
            if self.__mdatetime.type()== BCFileListRuleOperatorType.DATE:
                returned.append(f"{BCFileProperty.FILE_DATE.translate()} {self.__mdatetime.translate()}")
            else:
                returned.append(f"{i18n('file date/time')} {self.__mdatetime.translate()}")

        if not self.__format is None:
            returned.append(f"{BCFileProperty.FILE_FORMAT.translate()} {self.__format.translate()}")

        if not self.__imageWidth is None:
            returned.append(f"{BCFileProperty.IMAGE_WIDTH.translate()} {self.__imageWidth.translate()}")

        if not self.__imageHeight is None:
            returned.append(f"{BCFileProperty.IMAGE_HEIGHT.translate()} {self.__imageHeight.translate()}")

        if not self.__imageRatio is None:
            returned.append(f"{BCFileProperty.IMAGE_RATIO.translate()} {self.__imageRatio.translate()}")

        if not self.__imagePixels is None:
            returned.append(f"{BCFileProperty.IMAGE_PIXELS.translate()} {self.__imagePixels.translate()}")

        if len(returned) == 0:
            return ''

        return "- "+f"\n  {i18n('and')}\n- ".join(returned)

    def name(self):
        """Return current matching pattern"""
        return self.__name

    def setName(self, value):
        """Set current matching pattern"""
        if isinstance(value, tuple):
            displayValue = value[0]

            if isinstance(value[0], str):
                if checkIsRegEx:=re.search('^re(/i)?:(.*)', value[0]):
                    # provided as a regular expression
                    displayValue = checkIsRegEx.groups()[1]

                    if not checkIsRegEx.groups()[0] is None:
                        displayValue=f"(?i)(?:{displayValue})"
                    value = (re.compile(displayValue), value[1])
                else:
                    # provided as a wildcard character
                    # convert to regex
                    displayValue = value[0]
                    value = (re.compile( '(?i)(?:^'+value[0].replace('.', r'\.').replace('*', r'.*').replace('?', '.')+'$)'), value[1])
            elif isinstance(value[0], re.Pattern):
                displayValue = value[0].pattern
            else:
                raise EInvalidRuleParameter("Given `name` must be a valid value")

            self.__name = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.REGEX, displayValue)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.REGEX:
            self.__name = value
        else:
            raise EInvalidRuleParameter("Given `name` must be a valid value")
        self.__updateHash()

    def path(self):
        """Return current path pattern"""
        return self.__path

    def setPath(self, value):
        """Set current path pattern"""
        if isinstance(value, tuple):
            displayValue = value[0]

            if isinstance(value[0], str):
                if checkIsRegEx:=re.search('^re(/i)?:(.*)', value[0]):
                    # provided as a regular expression
                    displayValue = checkIsRegEx.groups()[1]

                    if not checkIsRegEx.groups()[0] is None:
                        displayValue=f"(?i)(?:{displayValue})"
                    value = (re.compile(displayValue), value[1])
                else:
                    # provided as a wildcard character
                    # convert to regex
                    displayValue = value[0]
                    value = (re.compile( '(?i)(?:^'+value[0].replace('.', r'\.').replace('*', r'.*').replace('?', '.')+'$)'), value[1])
            elif isinstance(value[0], re.Pattern):
                displayValue = value[0].pattern
            else:
                raise EInvalidRuleParameter("Given `path` must be a valid value")

            self.__path = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.REGEX, displayValue)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.REGEX:
            self.__path = value
        else:
            raise EInvalidRuleParameter("Given `path` must be a valid value")
        self.__updateHash()

    def size(self):
        """Return current size rule"""
        return self.__size

    def setSize(self, value):
        """set current size rule

        Given `value` can be:
        - A BCFileListRuleOperator
        - A tuple (value, operator)
        """
        if isinstance(value, tuple):
            displayValue = value[0]
            if isinstance(value[0], str):
                value = (strToBytesSize(value[0]), value[1])
            elif isinstance(value[0], float):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([strToBytesSize(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([strToBytesSize(v) for v in value[0]], value[1])
            elif not isinstance(value[0], int):
                raise EInvalidRuleParameter("Given `size` must be a valid value")

            self.__size = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.INT, displayValue)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.INT:
            self.__size = value
        else:
            raise EInvalidRuleParameter("Given `size` must be a valid value")
        self.__updateHash()

    def modifiedDateTime(self):
        """Return current modification date/time rule"""
        return self.__mdatetime

    def setModifiedDateTime(self, value):
        """set current modification date/time rule"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (strToTs(value[0]), value[1])
            elif isinstance(value[0], int):
                value = (float(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([strToTs(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([strToTs(v) for v in value[0]], value[1])
            elif not isinstance(value[0], float):
                raise EInvalidRuleParameter("Given `date` must be a valid value")

            ruleType = BCFileListRuleOperatorType.DATETIME

            # now, value is a timestamp
            # reconvert it to string => YYYY-MM-DD HH:MI:SS
            # and determinate if it's a DATE (HH:MI:SS = 00:00:00) a DATETIME (HH:MI:SS <> 00:00:00)
            if isinstance(value[0], float):
                if QDateTime.fromMSecsSinceEpoch(1000*value[0]).time().msecsSinceStartOfDay()==0:
                    # hour = 00:00:00
                    ruleType = BCFileListRuleOperatorType.DATE
                elif value[1] == '<=':
                    value = (value[0]+0.9999, value[1])
            elif isinstance(value[0], tuple):
                # interval (between)
                # in this case, always date/time
                # => fix end hour to 23:59:59.9999 if not already defined
                if QDateTime.fromMSecsSinceEpoch(1000*value[0]).time().msecsSinceStartOfDay()==0:
                    # hour = 00:00:00
                    value = ((value[0][0], value[0][1] + 86399.9999), value[1])
                else:
                    value = ((value[0][0], value[0][1] + 0.9999), value[1])
            elif isinstance(value[0], list):
                # list (in)
                # not possible to mix dates and date/time so consider that if all items are date, it's date
                # otherwise it's date/time
                ruleType = BCFileListRuleOperatorType.DATE

                for dateItem in value[0]:
                    if QDateTime.fromMSecsSinceEpoch(1000*value[0]).time().msecsSinceStartOfDay()!=0:
                        ruleType = BCFileListRuleOperatorType.DATETIME
                        break

            self.__mdatetime = BCFileListRuleOperator(value[0], value[1], ruleType)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() in [BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME]:
            self.__mdatetime = value
        else:
            raise EInvalidRuleParameter("Given `date` must be a valid value")
        self.__updateHash()

    def format(self):
        """Return current format rule"""
        return self.__format

    def setFormat(self, value):
        """set current format rule"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (BCFileManagedFormat.format(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([BCFileManagedFormat.format(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([BCFileManagedFormat.format(v) for v in value[0]], value[1])
            elif not isinstance(value[0], BCFileManagedFormat):
                raise EInvalidRuleParameter("Given `format` must be a valid value")

            self.__format = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.STRING)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.STRING:
            self.__format = value
        else:
            raise EInvalidRuleParameter("Given `format` must be a valid value")
        self.__updateHash()

    def imageWidth(self):
        """Return current image width rule"""
        return self.__imageWidth

    def setImageWidth(self, value):
        """set current image width rule"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], float):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([int(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([int(v) for v in value[0]], value[1])
            elif not isinstance(value[0], int):
                raise EInvalidRuleParameter("Given `image width` must be a valid value")

            self.__imageWidth = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.INT)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.INT:
            self.__imageWidth = value
        else:
            raise EInvalidRuleParameter("Given `image width` must be a valid value")
        self.__updateHash()

    def imageHeight(self):
        """Return current image width rule"""
        return self.__imageHeight

    def setImageHeight(self, value):
        """set current image height rule"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], float):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([int(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([int(v) for v in value[0]], value[1])
            elif not isinstance(value[0], int):
                raise EInvalidRuleParameter("Given `image height` must be a valid value")

            self.__imageHeight = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.INT)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.INT:
            self.__imageHeight = value
        else:
            raise EInvalidRuleParameter("Given `image height` must be a valid value")
        self.__updateHash()

    def imageRatio(self):
        """Return current image width/height ratio"""
        return self.__imageRatio

    def setImageRatio(self, value):
        """set current image with/height ratio"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], float):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([int(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([int(v) for v in value[0]], value[1])
            elif not isinstance(value[0], int):
                raise EInvalidRuleParameter("Given `image height` must be a valid value")

            self.__imageRatio = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.FLOAT)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.FLOAT:
            self.__imageRatio = value
        else:
            raise EInvalidRuleParameter("Given `image ratio` must be a valid value")
        self.__updateHash()

    def imagePixels(self):
        """Return current image width*height pixels"""
        return self.__imagePixels

    def setImagePixels(self, value):
        """set current image with*height pixels"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], float):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([int(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([int(v) for v in value[0]], value[1])
            elif not isinstance(value[0], int):
                raise EInvalidRuleParameter("Given `image pixels` must be a valid value")

            self.__imagePixels = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.INT)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.INT:
            self.__imagePixels = value
        else:
            raise EInvalidRuleParameter("Given `image pixels` must be a valid value")
        self.__updateHash()

    def fileMatch(self, file):
        """Return True if given `file` match current rule"""
        if isinstance(file, BCDirectory):
            # do not filter directories
            return True
        elif not isinstance(file, BCFile):
            raise EInvalidRuleParameter("Given `file` type must be <BCFile>")

        if not self.__name is None:
            if not self.__name.compare(file.name()):
                return False

        if not self.__path is None:
            if not self.__path.compare(file.path()):
                return False

        if not self.__size is None:
            if not self.__size.compare(file.size()):
                return False

        if not self.__mdatetime is None:
            if not self.__mdatetime.compare(file.lastModificationDateTime(self.__mdatetime.type() == BCFileListRuleOperatorType.DATE)):
                return False

        if not self.__format is None:
            if not self.__format.compare(file.format()):
                return False

        if not self.__imageWidth is None:
            if not self.__imageWidth.compare(file.imageSize().width()):
                return False

        if not self.__imageHeight is None:
            if not self.__imageHeight.compare(file.imageSize().width()):
                return False

        if not self.__imageRatio is None:
            property=file.getProperty(BCFileProperty.IMAGE_RATIO)
            if property is None or not self.__imageRatio.compare(property):
                return False

        if not self.__imagePixels is None:
            property=file.getProperty(BCFileProperty.IMAGE_PIXELS)
            if property is None or not self.__imagePixels.compare(property):
                return False

        return True


class BCFileListRuleCombination(object):
    """Define a combination operator"""

    OPERATOR_NOT = 0x01
    OPERATOR_AND = 0x02
    OPERATOR_OR = 0x03

    def __init__(self, operatorType, *items):
        """Initialise combination rule"""
        if not operatorType in (BCFileListRuleCombination.OPERATOR_NOT,
                                BCFileListRuleCombination.OPERATOR_AND,
                                BCFileListRuleCombination.OPERATOR_OR):
            raise EInvalidValue("Given `operatorType` is not valid")

        self.__type = operatorType
        self.__hash = None

        self.__items = []
        self.__itemsSorted = []

        for item in items:
            if isinstance(item, BCFileListRuleCombination) or isinstance(item, BCFileListRule):
                self.__items.append(item)
            else:
                raise EInvalidValue("Given `items` must be <BCFileListRuleCombination> or <BCFileListRule>")
        self.__updateHash()

    def __str__(self):
        """Return rule as string"""
        returned=[f"{item}" for item in self.__items]

        if self.__type == BCFileListRuleCombination.OPERATOR_NOT:
            return f"NOT ({returned[0]})"
        elif self.__type == BCFileListRuleCombination.OPERATOR_AND:
            return f"({') AND ('.join(returned)})"
        elif self.__type == BCFileListRuleCombination.OPERATOR_OR:
            return f"({') OR ('.join(returned)})"

    def __eq__(self, other):
        """Return if other BCFileListRule is the same than current one"""
        if isinstance(other, BCFileListRuleCombination):
            return (self.__hash == other.__hash)
        return False

    def __hash__(self):
        """Return hash for BCFileListRuleCombination"""
        return self.__hash

    def __updateHash(self):
        """Return a hash from rule"""
        self.__hash=hash((self.__type, *[hash(item) for item in self.__items]))
        self.__sortRules()

    def __sortRules(self):
        """Sort items to ensure best evaluation order

        If current operator is NOT, do not sort (ensure the first item is always the same)
        If current operator is AND or OR, sort items in the following order:
        - BCFileListRule: simplest evaluation first (from file/image)
        - BCFileListRuleCombination: NOT
        - BCFileListRuleCombination: AND
        - BCFileListRuleCombination: OR
        """
        def sortKey(value):
            if isinstance(value, BCFileListRule):
                return 1
            elif isinstance(value, BCFileListRuleCombination):
                if value.operatorType()==BCFileListRuleCombination.OPERATOR_NOT:
                    return 2
                elif value.operatorType()==BCFileListRuleCombination.OPERATOR_AND:
                    return 3
                elif value.operatorType()==BCFileListRuleCombination.OPERATOR_OR:
                    return 4
            return 5

        self.__itemsSorted=sorted(self.__items, key=sortKey)

    def translate(self, short=False):
        """Return rule as a human readable string"""
        returned = []

        if short:
            return self.__str__()

        if self.__type == BCFileListRuleCombination.OPERATOR_NOT:
            opStr=i18n('not')+'\n'
            return textwrap.indent(opStr+self.__items[0].translate(short),'  ')
        elif self.__type == BCFileListRuleCombination.OPERATOR_AND:
            opStr=i18n('and')+' '
        elif self.__type == BCFileListRuleCombination.OPERATOR_OR:
            opStr=i18n('or')+' '

        opJoin=f"\n  {opStr}\n"
        returned=[item.translate(short) for item in self.__itemsSorted]
        return textwrap.indent(opJoin.join(returned),'  ')

    def fileMatch(self, file):
        """Return True if given `file` match current rule"""
        if isinstance(file, BCDirectory):
            # do not filter directories
            return True
        elif not isinstance(file, BCFile):
            raise EInvalidRuleParameter("Given `file` type must be <BCFile>")
        elif len(self.__itemsSorted)==0:
            # if empty combination, then always return False
            return False

        if self.__type==BCFileListRuleCombination.OPERATOR_NOT:
            # only one item in rule, return negative value
            return not self.__items[0].fileMatch(file)
        elif self.__type==BCFileListRuleCombination.OPERATOR_AND:
            # AND => parse all rule, exit on first False
            for item in self.__itemsSorted:
                if not item.fileMatch(file):
                    return False
            return True
        elif self.__type==BCFileListRuleCombination.OPERATOR_OR:
            # OR => parse all rules, exit on first True
            for item in self.__itemsSorted:
                if item.fileMatch(file):
                    return True
            return False

    def rules(self):
        """Return current defined filter rules to combine"""
        return self.__items

    def inRules(self, value):
        """Return True if a rule is already defined in list"""
        if isinstance(value, (BCFileListRuleCombination, BCFileListRule)):
            return value in self.__items
        else:
            raise EInvalidType("Given `value` is not a valid rule")

    def addRule(self, item):
        """Add a filter rule to combination"""
        if isinstance(item, BCFileListRuleCombination) and item==self:
            return

        if isinstance(item, BCFileListRuleCombination) or isinstance(item, BCFileListRule):
            if not item in self.__items:
                self.__items.append(item)
        else:
            raise EInvalidValue("Given `items` must be <BCFileListRuleCombination> or <BCFileListRule>")
        self.__updateHash()

    def removeRule(self, item):
        """Remove a filter rule from combination

        If not found does nothing
        """
        if isinstance(value, list):
            for rule in value:
                self.removeRule(rule)
        else:
            if self.inRules(value):
                self.__items.remove(value)
                self.__invalidate()
        self.__updateHash()

    def operatorType(self):
        """Return operator type"""
        return self.__type


class BCFileListPath(object):
    """A search path definition"""

    def __init__(self, path=None, recursive=False, hiddenFiles=False, managedFilesOnly=False, managedFilesBackup=False):
        self.__path = ''
        self.__recursive = False
        self.__hiddenFiles = False
        self.__managedFilesOnly = False
        self.__managedFilesBackup = False

        self.setPath(path)
        self.setRecursive(recursive)
        self.setHiddenFiles(hiddenFiles)
        self.setManagedFilesOnly(managedFilesOnly)
        self.setManagedFilesBackup(managedFilesBackup)

    def __repr__(self):
        return f"<BCFileListPath('{self.__path}', {self.__recursive})>"

    def path(self):
        """Return current search path"""
        return self.__path

    def setPath(self, value):
        """set search path"""
        if isinstance(value, str) and value != '':
            self.__path = value
        else:
            raise EInvalidRuleParameter("Given `path` must be a valid string")

    def recursive(self):
        """Return if search is recursive or not"""
        return self.__recursive

    def setRecursive(self, value):
        """set recursive search status"""
        if isinstance(value, bool):
            self.__recursive = value
        else:
            raise EInvalidRuleParameter("Given `recursive` must be a valid boolean")

    def hiddenFiles(self):
        """Return if search is include hidden files or not"""
        return self.__hiddenFiles

    def setHiddenFiles(self, value):
        """Set if search is include hidden files or not"""
        if isinstance(value, bool):
            self.__hiddenFiles = value
        else:
            raise EInvalidRuleParameter("Given `hiddenFiles` must be a valid boolean")

    def managedFilesOnly(self):
        """Return if search is made on managed files only or not"""
        return self.__managedFilesOnly

    def setManagedFilesOnly(self, value):
        """Set if search is made on managed files only or not"""
        if isinstance(value, bool):
            self.__managedFilesOnly = value
        else:
            raise EInvalidRuleParameter("Given `managedFilesOnly` must be a valid boolean")

    def managedFilesBackup(self):
        """Return if search is made on managed files include backup files or not"""
        return self.__managedFilesBackup

    def setManagedFilesBackup(self, value):
        """Set if search is made on managed files i nclude backup files or not"""
        if isinstance(value, bool):
            self.__managedFilesBackup = value
        else:
            raise EInvalidRuleParameter("Given `managedFilesBackup` must be a valid boolean")


class BCFileListSortRule(object):
    """Define sort rule for file"""

    def __init__(self, property, ascending=True):
        """Initialise a sort rule"""
        if isinstance(property, BCFileProperty):
            self.__property = property
        elif isinstance(property, str):
            self.__property = BCFileProperty(property)
        else:
            raise EInvalidType('Given `property` must be a valid <BCFileProperty>')

        if isinstance(ascending, bool):
            self.__ascending = ascending
        else:
            raise EInvalidType('Given `ascending` must be a valid <bool>')

        self.__hash=0
        self.__updateHash()

    def __str__(self):
        """Return sort rule as string"""
        if self.__ascending:
            return f'{self.__property.value} ASC'
        else:
            return f'{self.__property.value} DESC'

    def __repr__(self):
        """Return rule as string"""
        return f'<BCFileListSortRule(property={self.__property.value}; ascending={self.__ascending}; hash={self.__hash:016x})>'

    def __eq__(self, other):
        """Return if other BCFileListRule is the same than current one"""
        if isinstance(other, BCFileListSortRule):
            return (self.__hash == other.__hash)
        return False

    def __hash__(self):
        """Return hash for BCFileListSortRule"""
        return self.__hash

    def __updateHash(self):
        """UPdate a hash value"""
        self.__hash=hash((self.__property, self.__ascending))

    def translate(self, short=False):
        """Return rule as a human readable string"""
        if short:
            return self.__str__()

        if self.__ascending:
            return f'{self.__property.translate()} (ascending)'
        else:
            return f'{self.__property.translate()} (descending)'

    def property(self):
        """return sorted property"""
        return self.__property

    def ascending(self):
        """return True if sort is ascending, otherwise False"""
        return self.__ascending


class BCFileList(QObject):
    """A file list wrapper

    Allows to manage from the simplest query (files in a directory) to the most complex (search in multiple path with
    multiple specifics criteria inclyuding add/exclude)
    """
    stepExecuted = Signal(tuple)        # signals emitted during searchExecute, tuple varies according to search step
    stepCancel = Signal()               # search execution is cancelled
    resultsUpdatedReset = Signal()
    resultsUpdatedSort = Signal()
    resultsUpdatedAdd = Signal(list)        # results are updated: list of added items (BCBaseFile)
    resultsUpdatedRemove = Signal(list)     # results are updated: list of removed items (BCBaseFile)
    resultsUpdatedUpdate = Signal(list)     # results are updated: list of updates items (BCBaseFile)

    # activated by default
    STEPEXECUTED_SEARCH_FROM_PATHS = 0b0000000000000100      # search files in path finished
    STEPEXECUTED_ANALYZE_METADATA =  0b0000000000001000      # read files for metadata finished
    STEPEXECUTED_FILTER_FILES =      0b0000000000010000      # filter files according to rules finished
    STEPEXECUTED_BUILD_RESULTS =     0b0000000000100000      # prepare results
    STEPEXECUTED_SORT_RESULTS =      0b0000000001000000      # sort results
    STEPEXECUTED_OUTPUT_RESULTS =    0b0000000010000000

    # not activated by default
    STEPEXECUTED_SEARCH_FROM_PATH =  0b0000000000000101      # during path scan, a path has been scanned (scan next directory will start)
    STEPEXECUTED_PROGRESS_ANALYZE =  0b0000000000001001      # each file analyzed will emit a signal; allows to track analysis progress and update a progress bar for exwample
    STEPEXECUTED_PROGRESS_FILTER =   0b0000000000010001      # each file filtered will emit a signal; allows to track analysis progress and update a progress bar for exwample
    STEPEXECUTED_PROGRESS_SORT =     0b0000000001000001      # each file sorted will emit a signal; allows to track analysis progress and update a progress bar for exwample
    STEPEXECUTED_PROGRESS_OUTPUT =   0b0000000010000001

    STEPEXECUTED_FINISHED_OUTPUT =   0b0000000010000010

    STEPEXECUTED_CANCEL =            0b0000000100000000      # execution has been cancelled
    STEPEXECUTED_UPDATERESET =       0b0000001000000000      # emit resultsUpdatedReset() during searchExecute
    STEPEXECUTED_UPDATESORT =        0b0000010000000000      # emit resultsUpdatedSort() during searchExecute

    CANCELLED_SEARCH = -1

    __MTASKS_RULES = []

    @staticmethod
    def getBcFile(itemIndex, fileName, bcFileCache=None, strict=False):
        """Return a BCFile from given fileName

        If strict is True, check only files for which extension is known
        If strict is False, try to determinate file format even if there's no extension

        > Used for multiprocessing tasks
        """
        if isinstance(fileName, BCFile) or isinstance(fileName, BCMissingFile):
            return fileName

        try:
            return BCFile(fileName, strict, bcFileCache=bcFileCache)
        except Exception as e:
            Debug.print('[BCFileList.getBcFile] Unable to analyse file {0}: {1}', fileName, e)
            return None

    @staticmethod
    def getBcDirectory(itemIndex, fileName, dummy1=None, dummy2=None):
        """Return a BCDirectory from given fileName

        > Used for multiprocessing tasks
        """
        if isinstance(fileName, BCDirectory):
            return fileName

        try:
            return BCDirectory(fileName)
        except Exception as e:
            Debug.print('[BCFileList.getBcDirectory] Unable to analyse directory {0}: {1}', fileName, e)
            return None

    @staticmethod
    def checkBcFile(itemIndex, file):
        """Return file if matching query rules, otherwise return None

        > Used for multiprocessing tasks
        """
        if not file is None:
            if len(BCFileList.__MTASKS_RULES) > 0:
                for rule in BCFileList.__MTASKS_RULES:
                    if rule.fileMatch(file):
                        #updateStats(file, statFile)
                        return file
            else:
                #updateStats(file, statFile)
                return file
        return None

    @staticmethod
    def getBcFileUuid(itemIndex, file):
        """Return fullPathName

        > Used for multiprocessing task
        """
        return file.uuid()

    @staticmethod
    def getBcFileStats(itemIndex, file):
        returned={}
        if file.format() == BCFileManagedFormat.DIRECTORY:
            returned['nbDir']=1
        elif file.format() == BCFileManagedFormat.UNKNOWN:
            returned['nbOther']=1
            returned['sizeOther']=file.size()
        else:
            returned['nbKra']=1
            returned['sizeKra']=file.size()
        return returned

    def __init__(self):
        """Initialiser current list query"""
        super(BCFileList, self).__init__(None)
        self.__currentFiles = []
        self.__currentFilesUuid = set()

        self.__pathList = []
        self.__ruleList = []
        self.__sortList = []
        self.__sortCaseInsensitive=False

        self.__statFiles=None

        self.__includeDirectories = False

        self.__invalidated = True

        self.__cancelProcess=False

        self.__workerPool=WorkerPool()

        self.__progressFilesPctThreshold=0
        self.__progressFilesPctTracker=0
        self.__progressFilesPctCurrent=0
        self.__progressFilesTracker=0

        self.__massProcess=False

    def __invalidate(self):
        self.__invalidated = True

    def __sort(self, fileA, fileB):
        # if A < B : -1
        #    A > B : 1
        #    A = B : 0
        if self.__progressFilesPctThreshold>0:
            self.__progressSorting()

        # very long: need to check all sort criteria
        for sortKey in self.__sortList:
            pA = fileA.getProperty(sortKey.property())
            pB = fileB.getProperty(sortKey.property())

            if self.__sortCaseInsensitive:
                if isinstance(pA, str):
                    pA=pA.lower()
                if isinstance(pB, str):
                    pB=pB.lower()

            # note: directories are always before files
            #       if directories and "..", always first...
            if fileA.format() == BCFileManagedFormat.DIRECTORY and (fileB.format() != BCFileManagedFormat.DIRECTORY or fileA.name()=='..'):
                return -1
            elif fileB.format() == BCFileManagedFormat.DIRECTORY and (fileA.format() != BCFileManagedFormat.DIRECTORY or fileB.name()=='..'):
                return 1

            # both are directories OR both are not directories

            if pA == pB:
                # same value, need to compare on next sort key
                continue
            elif sortKey.ascending():
                if pA is None:
                    return -1
                elif pB is None:
                    return 1
                elif pA < pB:
                    return -1
                else:
                    return 1
            else:
                if pA is None:
                    return 1
                elif pB is None:
                    return -1
                elif pA > pB:
                    return -1
                else:
                    return 1

        return 0

    def __progressScanning(self, value):
        """Emit signal during scanning progress

        Emit signal every 1%
        """
        self.__progressFilesPctTracker+=1
        self.__progressFilesTracker+=1
        if self.__progressFilesPctTracker>=self.__progressFilesPctThreshold:
            self.__progressFilesPctCurrent+=1
            self.__progressFilesPctTracker=0
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_PROGRESS_ANALYZE,self.__progressFilesPctCurrent,self.__progressFilesTracker))

    def __progressFiltering(self, value):
        """Emit signal during scanning progress

        Emit signal every 1%
        """
        self.__progressFilesPctTracker+=1
        self.__progressFilesTracker+=1
        if self.__progressFilesPctTracker>=self.__progressFilesPctThreshold:
            self.__progressFilesPctCurrent+=1
            self.__progressFilesPctTracker=0
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_PROGRESS_FILTER,self.__progressFilesPctCurrent,self.__progressFilesTracker))

    def __progressSorting(self):
        """Emit signal during scanning progress

        Emit signal every 1%
        """
        self.__progressFilesPctTracker+=1
        self.__progressFilesTracker+=1
        if self.__progressFilesPctTracker>=self.__progressFilesPctThreshold:
            self.__progressFilesPctCurrent+=1
            self.__progressFilesPctTracker=0
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_PROGRESS_SORT,self.__progressFilesPctCurrent,self.__progressFilesTracker))

    def clear(self):
        """Clear everything
        - paths
        - rules
        - results
        """
        self.clearSearchPaths()
        self.clearSearchRules()
        self.clearResults()

    def clearSearchPaths(self):
        """Clear paths definitions"""
        self.__pathList = []
        self.__invalidate()

    def clearSearchRules(self):
        """Clear rules definitions"""
        self.__ruleList = []
        self.__invalidate()

    def clearSortRules(self):
        """Clear rules definitions"""
        self.__sortList = []
        self.__invalidate()

    def clearResults(self, emitSignal=True):
        """Clear current results"""
        self.__currentFiles = []
        self.__currentFilesUuid = set()
        self.__invalidate()
        if emitSignal:
            self.resultsUpdatedReset.emit()

    def searchIncludeDirectories(self):
        """Return if query include directories or not"""
        return self.__includeDirectories

    def searchSetIncludeDirectories(self, value):
        """Set if query should include directories or not"""
        if isinstance(value, bool):
            if self.__includeDirectories != value:
                self.__invalidate()
            self.__includeDirectories = value

    def searchPaths(self):
        """Return current defined paths where to search files"""
        return self.__pathList

    def inSearchPaths(self, value):
        """Return True if a path is defined in list"""
        if isinstance(value, str):
            refValue = value
        else:
            refValue = value.path()

        for path in self.__pathList:
            if path.path() == refValue:
                return True
        return False

    def addSearchPaths(self, value):
        """Add a new path in path list

        If path already exist in list, it will be ignored

        Given `path` can be:
        - A string (recurse scan is disabled)
        - A BCFileListPath
        - A list of string (recurse scan is disabled) / BCFileListPath
        """
        if isinstance(value, list):
            for path in value:
                self.addSearchPaths(path)
        elif isinstance(value, str):
            if not self.inSearchPaths(value):
                self.__pathList.append( BCFileListPath(value) )
                self.__invalidate()
        elif isinstance(value, BCFileListPath):
            if not self.inSearchPaths(value):
                self.__pathList.append( value )
                self.__invalidate()
        else:
            raise EInvalidType("Given path is not valid")

    def removeSearchPaths(self, value):
        """Remove given path from list

        If path is not found, do nothing

        Given `path` can be:
        - A string
        - A BCFileListPath
        - A list of string / BCFileListPath
        """
        if isinstance(value, list):
            for path in value:
                self.removeSearchPaths(path)
        else:
            if self.inSearchPaths(value):
                if isinstance(value, str):
                    refValue = value
                else:
                    refValue = value.path()

                for path in self.__pathList:
                    if path.path() == refValue:
                        self.__pathList.remove(path)
                        self.__invalidate()

    def searchRules(self):
        """Return current defined rules used to filter files"""
        return self.__ruleList

    def inSearchRules(self, value):
        """Return True if a rule is already defined in list"""
        if isinstance(value, (BCFileListRuleCombination, BCFileListRule)):
            return value in self.__ruleList
        else:
            raise EInvalidType("Given `value` is not a valid rule")

    def addSearchRules(self, value):
        """Add a new filtering rule

        If rule is already defined, ignore it

        Filtering rules works in OR mode: a file is selected if at least it match one of the given rules
        """
        if isinstance(value, list):
            for rule in value:
                self.addSearchRules(rule)
        elif isinstance(value, (BCFileListRule, BCFileListRuleCombination)):
            if not self.inSearchRules(value):
                self.__ruleList.append(value)
                self.__invalidate()
        else:
            raise EInvalidType("Given rule is not valid")

    def removeSearchRules(self, value):
        """Remove given rule from list

        If rule is not found, do nothing
        """
        if isinstance(value, list):
            for rule in value:
                self.removeSearchRules(rule)
        else:
            if self.inSearchRules(value):
                self.__ruleList.remove(value)
                self.__invalidate()

    def sortRules(self):
        """Return sort rules"""
        return self.__sortlist

    def inSortRules(self, value):
        """Return True if sort is already defined in sort list"""
        if isinstance(value, BCFileListSortRule):
            return value in self.__sortList
        else:
            raise EInvalidType("Given `value` is not a valid sort rule")

    def addSortRule(self, value):
        """Add a new sort rule

        If sort rule is already defined, ignore it
        """
        if isinstance(value, list):
            for rule in value:
                self.addSortRule(rule)
        elif isinstance(value, BCFileListSortRule):
            if not self.inSortRules(value):
                self.__sortList.append(value)
                self.__invalidate()
        else:
            raise EInvalidType("Given sort rule is not valid")

    def removeSortRule(self, value):
        """Remove given sort rule from list

        If sort rule is not found, do nothing
        """
        if isinstance(value, list):
            for rule in value:
                self.removeSortRule(rule)
        else:
            if self.inSortRules(value):
                self.__sortList.remove(value)
                self.__invalidate()

    def exportHQuery(self):
        """Export query into a 'human natural language'

        Return result as a string
        """
        returned = []

        # build "search from directories" declaration
        if len(self.__pathList) > 0:
            fromClause = []

            # need to work with translated strings
            searchStr=i18n('Search files from')+' '
            andFromStr=i18n("and from")+' '
            searchAnd='\n'+(' '*(len(searchStr)-len(andFromStr)))+andFromStr

            directoryStr=i18n('directory')
            clauseIncludingStr="\n" + (' ' * (len(directoryStr) + len(searchAnd))) + "- "

            for path in self.__pathList:
                clause=f'{directoryStr} "{path.path()}"'

                if path.recursive():
                    clause+=clauseIncludingStr+i18n('including sub-directories')

                if path.hiddenFiles():
                    clause+=clauseIncludingStr+i18n('including hidden files')

                if path.managedFilesOnly():
                    clause+=clauseIncludingStr+i18n('looking for managed files only')
                    if path.managedFilesBackup():
                        clause+=f" ({i18n('including backup files')})"

                fromClause.append(clause)

            returned.append(searchStr+searchAnd.join(fromClause))
            returned.append('')
        else:
            returned.append(i18n('Search files from [search path not defined]'))
            returned.append('')

        # build "include" declaration
        includes = []
        if self.__includeDirectories:
            includes.append(i18n('directories'))

        if len(includes) > 0:
            searchStr=i18n('Including')+' '
            searchAnd='\n'+(' '*len(searchStr))+i18n("and")+'\n'+(' '*len(searchStr))

            returned.append(searchStr+searchAnd.join(includes))
            returned.append('')

        if len(self.__ruleList) > 0:
            whereClause = []

            for rule in self.__ruleList:
                whereClause.append(rule.translate())

            if len(whereClause):
                searchStr=i18n('For which')+'\n'
                searchAnd='\n'+(' '*len(searchStr))+i18n("and")+'\n'+(' '*len(searchStr))

                returned.append(searchStr+searchAnd.join(whereClause))
                returned.append('')

        if len(self.__sortList) > 0:
            returned.append('Sort result by:\n - '+ '\n - '.join([v.translate() for v in self.__sortList]) )

        return '\n'.join(returned)

    def cancelSearchExecution(self):
        """Cancel current execution"""
        if not self.__cancelProcess:
            self.__cancelProcess=True
            if self.__workerPool:
                self.__workerPool.stopProcessing()

    def searchExecute(self, clearResults=True, buildStats=False, signals=None):
        """Search for files

        Files matching criteria are added to selection.

        If `clearResults` is False, current selection is kept, otherwise
        selection is cleared before execution

        If `buildStats` is True, calculate statistics from file query
        => use stats() method to get statistics (nbDir, NbKra files, nb other files, sizes, ...)

        Return number of files matching criteria
        """
        self.__cancelProcess=False

        Stopwatch.reset('^BCFileList.execute')
        Stopwatch.start('BCFileList.execute.99-global')

        if signals is None:
            signals=[
                BCFileList.STEPEXECUTED_SEARCH_FROM_PATHS,
                BCFileList.STEPEXECUTED_ANALYZE_METADATA,
                BCFileList.STEPEXECUTED_FILTER_FILES,
                BCFileList.STEPEXECUTED_BUILD_RESULTS,
                BCFileList.STEPEXECUTED_SORT_RESULTS,
                BCFileList.STEPEXECUTED_CANCEL
            ]

        if clearResults:
            # reset current list if asked
            self.clearResults(False)

        if buildStats:
            self.__statFiles={
                    'nbKra': 0,
                    'nbOther': 0,
                    'sizeKra': 0,
                    'sizeOther': 0,
                    'nbDir': 0
                }
        else:
            self.__statFiles=None

        Debug.print('===========================================')
        Debug.print('BCFileList.execute')
        Debug.print('...........................................')

        # stopwatches are just used to measure execution time performances
        managedFilesOnly = None

        # nbTotal=counter used to determinate when to process application events
        nbTotal = 0

        # same search rule than in BCMainViewTab.__filesDirectoryContentChanged()
        # if updated here, must be updated in BCMainViewTab too
        Stopwatch.start('BCFileList.execute.01-search')
        # work on a set, faster for searching if a file is already in list
        foundFiles = set()
        foundDirectories = set()
        for processedPath in self.__pathList:
            # counter for files (exclufing directories) founds in current path
            nbFilesInPath=0

            pathName = processedPath.path()
            includeHidden=processedPath.hiddenFiles()

            # build regex to prefilter files if needed
            if processedPath.managedFilesOnly():
                extensionList=[fr'\.{extension}' for extension in BCFileManagedFormat.list()]

                if processedPath.managedFilesBackup():
                    bckSufRe=BCFileManagedFormat.backupSuffixRe()
                    extensionList+=[fr'\.{extension}{bckSufRe}' for extension in BCFileManagedFormat.list()]

                managedFilesOnly = re.compile(f"({'|'.join(extensionList)})$", re.I)
            else:
                managedFilesOnly=None

            BCFileCache.globalInstance().setDirectory(pathName)

            if processedPath.recursive():
                # recursive search for path, need to use os.walk()
                for path, subdirs, files in os.walk(pathName):
                    if not includeHidden:
                        # do not include hidden files/directories then need to remove hidden items from subdirs/files
                        # trick from https://stackoverflow.com/a/13454267
                        # > Note the dirs[:] = slice assignment; os.walk recursively traverses the subdirectories listed in dirs.
                        # >                    By replacing the elements of dirs with those that satisfy a criteria (e.g., directories whose names don't begin with .),
                        # >                    os.walk() will not visit directories that fail to meet the criteria.
                        # >                    This only works if you keep the topdown keyword argument to True
                        subdirs[:]=[dirName for dirName in subdirs if not QFileInfo(os.path.join(path, dirName)).isHidden()]

                    if self.__includeDirectories:
                        for dir in subdirs:
                            nbTotal+=1
                            fullPathName = os.path.join(path, dir)

                            uuid=BCBaseFile.getUuid(fullPathName)
                            if not uuid in self.__currentFilesUuid and not fullPathName in foundDirectories:
                                foundDirectories.add(fullPathName)
                                self.__currentFilesUuid.add(uuid)

                            if nbTotal%1000==0:
                                if self.__cancelProcess:
                                    self.stepExecuted.emit((BCFileList.STEPEXECUTED_CANCEL,))
                                    self.__invalidated = False
                                    return BCFileList.CANCELLED_SEARCH
                                QApplication.processEvents()

                    for name in files:
                        nbTotal+=1
                        fullPathName=os.path.join(path, name)

                        if includeHidden or not QFileInfo(name).isHidden():
                            # check if file name match given pattern (if pattern) and is not already in file list
                            if (managedFilesOnly is None or managedFilesOnly.search(name)) and not fullPathName in foundFiles:
                                uuid=BCBaseFile.getUuid(fullPathName)
                                if not uuid in self.__currentFilesUuid:
                                    foundFiles.add(fullPathName)
                                    self.__currentFilesUuid.add(uuid)
                                    nbFilesInPath+=1

                        if nbTotal%1000==0:
                            if self.__cancelProcess:
                                self.stepExecuted.emit((BCFileList.STEPEXECUTED_CANCEL,))
                                self.__invalidated = False
                                return BCFileList.CANCELLED_SEARCH
                            QApplication.processEvents()


            elif os.path.isdir(pathName):
                # return current directory content
                with os.scandir(pathName) as files:
                    for file in files:
                        nbTotal+=1

                        fullPathName = os.path.join(pathName, file.name)
                        if includeHidden or not QFileInfo(fullPathName).isHidden():
                            if file.is_file():
                                # check if file name match given pattern (if pattern) and is not already in file list
                                if (managedFilesOnly is None or managedFilesOnly.search(file.name)) and not fullPathName in foundFiles:
                                    uuid=BCBaseFile.getUuid(fullPathName)
                                    if not uuid in self.__currentFilesUuid:
                                        foundFiles.add(fullPathName)
                                        self.__currentFilesUuid.add(uuid)
                                        nbFilesInPath+=1
                            elif self.__includeDirectories and file.is_dir():
                                # if directories are asked and file is a directory, add it
                                uuid=BCBaseFile.getUuid(fullPathName)
                                if not uuid in self.__currentFilesUuid and not fullPathName in foundDirectories:
                                    foundDirectories.add(fullPathName)
                                    self.__currentFilesUuid.add(uuid)

                        if nbTotal%1000==0:
                            if self.__cancelProcess:
                                self.stepExecuted.emit((BCFileList.STEPEXECUTED_CANCEL,))
                                self.__invalidated = False
                                return BCFileList.CANCELLED_SEARCH
                            QApplication.processEvents()

            if BCFileList.STEPEXECUTED_SEARCH_FROM_PATH in signals:
                self.stepExecuted.emit((BCFileList.STEPEXECUTED_SEARCH_FROM_PATH, pathName, processedPath.recursive(), nbFilesInPath))

        totalMatch = len(foundFiles) + len(foundDirectories)

        Stopwatch.stop("BCFileList.execute.01-search")
        if BCFileList.STEPEXECUTED_SEARCH_FROM_PATHS in signals:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_SEARCH_FROM_PATHS, len(foundFiles), len(foundDirectories), totalMatch, Stopwatch.duration("BCFileList.execute.01-search")))

        #Debug.print("Search in paths: {0}", self.__pathList)
        #Debug.print('Found {0} of {1} files in {2}s', totalMatch, nbTotal, Stopwatch.duration("BCFileList.execute.01-search"))

        if totalMatch == 0:
            self.__invalidated = False
            return totalMatch

        # ----
        Stopwatch.start('BCFileList.execute.02-scan')
        # list file is built, now scan files to retrieve all file/image properties
        # the returned filesList is an array of BCFile if file is readable, otherwise it contain a None value
        filesList = set()
        directoriesList = set()

        self.__progressFilesPctThreshold=math.ceil(len(foundFiles)/100)
        self.__progressFilesPctTracker=0
        self.__progressFilesPctCurrent=0
        self.__progressFilesTracker=0

        self.__workerPool.setWorkerClass(BCWorkerCache)
        if BCFileList.STEPEXECUTED_PROGRESS_ANALYZE in signals:
            self.__workerPool.signals.processed.connect(self.__progressScanning)
        filesList = self.__workerPool.mapNoNone(foundFiles, BCFileList.getBcFile)
        if BCFileList.STEPEXECUTED_PROGRESS_ANALYZE in signals:
            if self.__progressFilesPctCurrent<100:
                self.stepExecuted.emit((BCFileList.STEPEXECUTED_PROGRESS_ANALYZE,100,len(foundFiles)))
            self.__workerPool.signals.processed.disconnect(self.__progressScanning)
        self.__workerPool.setWorkerClass()
        directoriesList = self.__workerPool.mapNoNone(foundDirectories, BCFileList.getBcDirectory)

        Stopwatch.stop('BCFileList.execute.02-scan')

        if self.__cancelProcess:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_CANCEL,))
            self.__invalidated = False
            return BCFileList.CANCELLED_SEARCH

        if BCFileList.STEPEXECUTED_ANALYZE_METADATA in signals:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_ANALYZE_METADATA, Stopwatch.duration("BCFileList.execute.02-scan")))

        #Debug.print('Scan {0} files in {1}s', totalMatch, Stopwatch.duration("BCFileList.execute.02-scan"))

        # ----
        Stopwatch.start('BCFileList.execute.03-filter')
        # filter files
        # will apply a filter on filesList BCFiles
        #   all files that don't match rule are replaced by None value

        # as callback called by pool can't be a method of an instancied object, we need to call static method
        # with static data
        # so pass current object rules to static class...
        if len(self.__ruleList) > 0:
            BCFileList.__MTASKS_RULES = self.__ruleList

            if BCFileList.STEPEXECUTED_PROGRESS_FILTER in signals:
                self.__progressFilesPctThreshold=math.ceil(len(filesList)/100)
                self.__progressFilesPctTracker=0
                self.__progressFilesPctCurrent=0
                self.__progressFilesTracker=0
                self.__workerPool.signals.processed.connect(self.__progressFiltering)

            # use all processors to parallelize files analysis
            self.__currentFiles = self.__workerPool.mapNoNone(filesList, BCFileList.checkBcFile)

            if BCFileList.STEPEXECUTED_PROGRESS_FILTER in signals:
                self.__workerPool.signals.processed.disconnect(self.__progressFiltering)

            if self.__cancelProcess:
                self.stepExecuted.emit((BCFileList.STEPEXECUTED_CANCEL,))
                self.__invalidated = False
                return BCFileList.CANCELLED_SEARCH

            self.__currentFiles += self.__workerPool.mapNoNone(directoriesList, BCFileList.checkBcFile)
        else:
            # no rules=return currents lists
            self.__currentFiles = filesList
            self.__currentFiles += directoriesList
            BCFileList.__MTASKS_RULES = []

        Stopwatch.stop('BCFileList.execute.03-filter')

        if self.__cancelProcess:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_CANCEL,))
            self.__invalidated = False
            return BCFileList.CANCELLED_SEARCH

        if BCFileList.STEPEXECUTED_FILTER_FILES in signals:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_FILTER_FILES, len(self.__currentFiles), Stopwatch.duration("BCFileList.execute.03-filter")))
        #Debug.print('Filter {0} files in {1}s', len(filesList), Stopwatch.duration("BCFileList.execute.03-filter"))

        # ----
        Stopwatch.start('BCFileList.execute.04-result')
        # build final result
        #   all files that match selection rules are added to current selected images
        self.__currentFilesUuid=set(self.__workerPool.map(self.__currentFiles, BCFileList.getBcFileUuid))
        nb = len(self.__currentFiles)

        #Debug.print('Add {0} files to result in {1}s', nb, Stopwatch.duration("BCFileList.execute.04-result"))

        Stopwatch.stop('BCFileList.execute.04-result')

        if buildStats:
            Stopwatch.start('BCFileList.execute.05-buildStats')
            self.__statFiles=self.__workerPool.aggregate(self.__currentFiles, self.__statFiles, BCFileList.getBcFileStats)
            Stopwatch.stop('BCFileList.execute.05-buildStats')
            #Debug.print('Build stats in {0}s', Stopwatch.duration("BCFileList.execute.05-buildStats"))


        if BCFileList.STEPEXECUTED_BUILD_RESULTS in signals:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_BUILD_RESULTS,Stopwatch.duration("BCFileList.execute.04-result")))


        if self.__cancelProcess:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_CANCEL,))
            self.__invalidated = False
            return BCFileList.CANCELLED_SEARCH

        # ----
        Stopwatch.start('BCFileList.execute.06-sort')
        if BCFileList.STEPEXECUTED_PROGRESS_SORT in signals:
            self.__progressFilesPctThreshold=math.ceil(nb/100)
            self.__progressFilesPctTracker=0
            self.__progressFilesPctCurrent=0
            self.__progressFilesTracker=0
        else:
            self.__progressFilesPctThreshold=0
        self.sortResults(None, (BCFileList.STEPEXECUTED_UPDATESORT in signals))
        Stopwatch.stop('BCFileList.execute.06-sort')
        if BCFileList.STEPEXECUTED_SORT_RESULTS in signals:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_SORT_RESULTS,Stopwatch.duration("BCFileList.execute.06-sort")))

        if self.__cancelProcess:
            self.stepExecuted.emit((BCFileList.STEPEXECUTED_CANCEL,))
            self.__invalidated = False
            return BCFileList.CANCELLED_SEARCH

        #Debug.print('Sort {0} files to result in {1}s', nb, Stopwatch.duration("BCFileList.execute.06-sort"))
        #Debug.print('Selected {0} of {1} file to result in {2}s', nb, nbTotal, Stopwatch.duration("BCFileList.execute.99-global"))

        Stopwatch.stop('BCFileList.execute.99-global')

        dummy=list(map(Debug.print, [f"{d[0]}: {d[1]:.4f}" for d in Stopwatch.list()]))
        Debug.print('===========================================')

        self.__invalidated = False

        if BCFileList.STEPEXECUTED_UPDATERESET in signals:
            self.resultsUpdatedReset.emit()

        return nb

    def sortResults(self, caseInsensitive=False, emitSignal=True):
        """Sort current result using current sort rules"""
        if isinstance(caseInsensitive, bool):
            self.__sortCaseInsensitive=caseInsensitive

        if len(self.__sortList) > 0:
            self.__currentFiles = sorted(self.__currentFiles, key=cmp_to_key(self.__sort))

            if emitSignal==True:
                self.resultsUpdatedSort.emit()

    def nbFiles(self):
        """Return number of found image files"""
        return len(self.__currentFiles)

    def files(self):
        """Return found image files"""
        return self.__currentFiles

    def setResults(self, files):
        """Allows to build result from a predefined list of files (fullpath name string and/or BCFile and/or BCDirectory)

        Note: when result is set:
        - current paths are cleared
        - current rules are cleared
        - current results are cleared
        """
        if not isinstance(files, list):
            raise EInvalidType("Given `files` must be a <list> of <str>, <BCFile> or <BCDirectory> items")

        self.clearSearchPaths()
        self.clearSearchRules()
        self.clearResults(False)

        foundFiles = set()
        foundDirectories = set()

        filesList = set()
        directoriesList = set()

        for file in files:
            if isinstance(file, str):
                if os.path.isfile(file):
                    foundFiles.add(file)
                elif os.path.isdir(file):
                    foundDirectories.add(file)
                else:
                    foundFiles.add(BCMissingFile(file))
            elif isinstance(file, BCFile) or isinstance(file, BCMissingFile):
                filesList.add(file)
            elif isinstance(file, BCDirectory):
                directoriesList.add(file)

        #Debug.print('[BCFileList.setResult] FoundFile: {0}', foundFiles)
        pool = WorkerPool()
        pool.setWorkerClass(BCWorkerCache)
        if len(foundFiles)>0:
            filesList = filesList.union( pool.mapNoNone(foundFiles, BCFileList.getBcFile) )
        if len(foundDirectories)>0:
            directoriesList = directoriesList.union( pool.mapNoNone(foundDirectories, BCFileList.getBcDirectory) )

        self.addResults(filesList.union(directoriesList))

        self.__invalidated = False

        return len(self.__currentFiles)

    def addResults(self, files, position=-1):
        """Add files to current results

        Given `files` can be list or unique item of:
        - fullpath name <str>
        - <BCFile> and/or <BCDirectory>

        Files can be added to given `position`:
        - If value is -1, added at the end
        - If value > 0, inserted to position

        A file already in list is not added
        """
        currentFilesCount=len(self.__currentFiles)

        if isinstance(files, (list, tuple, set)):
            added=[]
            self.__massProcess=True
            for file in files:
                if self.addResults(file):
                    added.append(file)
            self.__massProcess=False
            if len(added)>0:
                if currentFilesCount==0:
                    # list was empty, then it's a reset
                    self.resultsUpdatedReset.emit()
                else:
                    # list wasn't empty, then it's an addition
                    self.resultsUpdatedAdd.emit(added)
                return True
            return False

        if isinstance(files, str):
            if os.path.isdir():
                files=BCDirectory(files)
            elif os.path.isfile():
                files=BCFile(files)
            else:
                files=BCMissingFile(files)

        if isinstance(files, BCBaseFile):
            if not files.uuid() in self.__currentFilesUuid:
                # add only if not already in current results
                if position<0:
                    self.__currentFiles.append(files)
                else:
                    self.__currentFiles.insert(files, position)

                self.__currentFilesUuid.add(files.uuid())

                if not self.__massProcess:
                    if currentFilesCount==0:
                        # list was empty, then it's a reset
                        self.resultsUpdatedReset.emit()
                    else:
                        # list wasn't empty, then it's an addition
                        self.resultsUpdatedAdd.emit([files])

                return True
            return False
        else:
            raise EInvalidType("Given `files` must be <BCBaseFile> or <list>")

    def updateResults(self, files):
        """Update files to current results

        Given `files` can be list or unique item of:
        - fullpath name <str>
        - <BCFile> and/or <BCDirectory>
        """
        if isinstance(files, (list, tuple, set)):
            updated=[]
            self.__massProcess=True
            for file in files:
                if self.updateResults(file):
                    updated.append(file)
            self.__massProcess=False
            if len(updated)>0:
                # list wasn't empty, then it's an addition
                self.resultsUpdatedUpdate.emit(updated)
                return True
            return False

        if isinstance(files, str):
            if os.path.isdir():
                files=BCDirectory(files)
            elif os.path.isfile():
                files=BCFile(files)
            else:
                files=BCMissingFile(files)

        if isinstance(files, BCBaseFile):
            if files.uuid() in self.__currentFilesUuid:
                # update only if in current results

                self.__currentFiles[self.inResults(files.uuid())]=files

                if not self.__massProcess:
                    # list wasn't empty, then it's an addition
                    self.resultsUpdatedUpdate.emit([files])
                return True
            return False
        else:
            raise EInvalidType("Given `files` must be <BCBaseFile> or <list>")

    def removeResults(self, files):
        """Remove files from current results

        Given `files` can be list or unique item of:
        - <int> (define current position in result list)
        - fullpath name <str>
        - a file uuid
        - <BCFile> and/or <BCDirectory>
        """
        if isinstance(files, (list, tuple, set)):
            removed=[]
            self.__massProcess=True
            # first we need to process values given as row number
            # need reverse order to avoid index being broken when removed
            nbFiles=len(self.__currentFiles)
            intList=sorted([v for v in files if isinstance(v, int) and (v>=0 and v<nbFiles)], reverse=True)

            for index in intList:
                removed.append(self.__currentFiles.pop(index))

            notIntList=[v for v in files if not isinstance(v, int)]

            for file in notIntList:
                if self.removeResults(file):
                    removed.append(file)
            self.__massProcess=False
            if len(removed)>0:
                if len(self.__currentFiles)==0:
                    # everything was removed, then it's a reset
                    self.resultsUpdatedReset.emit()
                else:
                    # list wasn't empty, then it's an remove
                    self.resultsUpdatedRemove.emit(removed)
                return True
            return False

        if isinstance(files, str):
            if os.path.isdir():
                files=BCDirectory(files)
            elif os.path.isfile():
                files=BCFile(files)
            else:
                files=BCMissingFile(files)

        if isinstance(files, BCBaseFile):
            files=files.uuid()

        if isinstance(files, bytes):
            index=self.inResults(files)

            if index>=0:
                # remove only if found in current results
                file=self.__currentFiles.pop(index)
                self.__currentFilesUuid.discard(files)

                if not self.__massProcess:
                    if len(self.__currentFiles)==0:
                        # everything was removed, then it's a reset
                        self.resultsUpdatedReset.emit()
                    else:
                        # list wasn't empty, then it's an remove
                        self.resultsUpdatedRemove.emit([file])

                return True
            return False
        else:
            raise EInvalidType("Given `files` must be <BCBaseFile> or <list>")

    def inResults(self, bcFileUuid):
        """Return if `bcFileUuid` is in current results

        Given `bcFileUuid` can be:
        - An item: in this case, returned value is an integer
        - A list of items: in this case, returned value is a list of integer

        Provided values for `bcFileUuid` can be:
        - A uuid (as byte-string, BCBaseFile.uuid() )
        - A BCBaseFile object

        If found, index of first occurence is returned (note we don't expect to have duplicates values in a BCFileList)
        Otherwise return -1

        Examples:

            p=xx.inResults(bcfile0.uuid())

            If uuid not found in results, p=-1
            If uuid found in results at position 10, p=10


            p=xx.inResults([bcfile0.uuid(), bcfile1, bcfile2])

            If p=[-1,5,-1]
            It mean that uuid and bcfile2 were not found in results, and bcfile1 was found in position 5
        """
        if isinstance(bcFileUuid, (list, tuple)):
            return [self.inResults(item) for item in bcFileUuid]

        if isinstance(bcFileUuid, BCBaseFile):
            bcFileUuid=bcFileUuid.uuid()

        if isinstance(bcFileUuid, bytes):
            if bcFileUuid in self.__currentFilesUuid:
                for index, file in enumerate(self.__currentFiles):
                    if file.uuid()==bcFileUuid:
                        return index
            return -1
        else:
            raise EInvalidType("Given `bcFileUuid` must be <BCBaseFile> of <bytes>")

    def stats(self):
        """Return stats from last execution, if any (otherwise return None)"""
        return self.__statFiles


# ------------------------------------------------------------------------------

class BCFileIcon(object):
    """Provide icon for a BCBaseFile"""

    __IconProvider = QFileIconProvider()

    @staticmethod
    def get(file):
        """Return icon for given file"""
        if isinstance(file, str):
            fileInfo = QFileInfo(file)
        elif isinstance(file, BCBaseFile):
            fileInfo = QFileInfo(file.fullPathName())
        else:
            raise EInvalidType("Given `file` must be a <str> or <BCBaseFile>")

        if fileInfo.fileName() == '..':
            return buildIcon('pktk:goup')


        return BCFileIcon.__IconProvider.icon(fileInfo)


#Debug.setEnabled(True)
