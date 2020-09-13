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

from math import floor
import locale
import re
import time
import sys
import os

from PyQt5.Qt import *
from PyQt5.QtGui import (
        QBrush,
        QPainter,
        QPixmap
    )
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QRect
    )


try:
    locale.setlocale(locale.LC_ALL, '')
except:
    pass

# ------------------------------------------------------------------------------
# don't really like to use global variable... create a class with static methods instead?
__bytesSizeToStrUnit = 'autobin'
def setBytesSizeToStrUnit(unit):
    global __bytesSizeToStrUnit
    if unit.lower() in ['auto', 'autobin']:
        __bytesSizeToStrUnit = unit

def getBytesSizeToStrUnit():
    global __bytesSizeToStrUnit
    return __bytesSizeToStrUnit

def strToBytesSize(value):
    """Convert a value to bytes

    Given `value` can be an integer (return value) or a string
    When provided as a string, can be in form:
        <size><unit>

        With:
            Size:
                An integer or decimal:
                    1
                    1.1
                    .1
            Unit
                'GB', 'GiB'
                'MB', 'MiB'
                'KB', 'KiB'
                'B', ''

    If unable to parse value, raise an exception
    """
    if isinstance(value, int):
        return value
    elif isinstance(value, float):
        return int(value)
    elif isinstance(value, str):
        fmt = re.match("^(\d*\.\d*|\d+)(gb|gib|mb|mib|kb|kib|b)?$", value.lower())

        if not fmt is None:
            returned = float(fmt.group(1))

            if fmt.group(2) == 'kb':
                returned *= 1000
            elif fmt.group(2) == 'kib':
                returned *= 1024
            elif fmt.group(2) == 'mb':
                returned *= 1000000
            elif fmt.group(2) == 'mib':
                returned *= 1048576
            elif fmt.group(2) == 'gb':
                returned *= 1000000000
            elif fmt.group(2) == 'gib':
                returned *= 1073741824

            return int(returned)

        else:
            raise Exception(f"Given value '{value}' can't be parsed!")
    else:
        raise Exception(f"Given value '{value}' can't be parsed!")

def strDefault(value, default=''):
    """Return value as str

    If value is empty or None, return default value
    """
    if value is None or value == '':
        return default
    return str(value)

def intDefault(value, default=0):
    """Return value as int

    If value is empty or None or not a valid integer, return default value
    """
    if value is None:
        return default

    try:
        return int(value)
    except:
        return default

def bytesSizeToStr(value, unit=None, decimals=2):
    """Convert a size (given in Bytes) to given unit

    Given unit can be:
    - 'auto'
    - 'autobin' (binary Bytes)
    - 'GiB', 'MiB', 'KiB' (binary Bytes)
    - 'GB', 'MB', 'KB', 'B'
    """
    global __bytesSizeToStrUnit
    if unit is None:
        unit = __bytesSizeToStrUnit

    if not isinstance(unit, str):
        raise Exception('Given `unit` must be a valid <str> value')

    unit = unit.lower()
    if not unit in ['auto', 'autobin', 'gib', 'mib', 'kib', 'gb', 'mb', 'kb', 'b']:
        raise Exception('Given `unit` must be a valid <str> value')

    if not isinstance(decimals, int) or decimals < 0 or decimals > 8:
        raise Exception('Given `decimals` must be a valid <int> between 0 and 8')

    if not (isinstance(value, int) or isinstance(value, float)):
        raise Exception('Given `value` must be a valid <int> or <float>')

    if unit == 'autobin':
        if value >= 1073741824:
            unit = 'gib'
        elif value >= 1048576:
            unit = 'mib'
        elif value >= 1024:
            unit = 'kib'
        else:
            unit = 'b'
    elif unit == 'auto':
        if value >= 1000000000:
            unit = 'gb'
        elif value >= 1000000:
            unit = 'mb'
        elif value >= 1000:
            unit = 'kb'
        else:
            unit = 'b'

    fmt = f'{{0:.{decimals}f}}{{1}}'

    if unit == 'gib':
        return fmt.format(value/1073741824, 'GiB')
    elif unit == 'mib':
        return fmt.format(value/1048576, 'MiB')
    elif unit == 'kib':
        return fmt.format(value/1024, 'KiB')
    elif unit == 'gb':
        return fmt.format(value/1000000000, 'GB')
    elif unit == 'mb':
        return fmt.format(value/1000000, 'MB')
    elif unit == 'kb':
        return fmt.format(value/1000, 'KB')
    else:
        return f'{value}B'

def tsToStr(value, pattern=None, valueNone=''):
    """Convert a timestamp to localtime string

    If no pattern is provided or if pattern = 'dt' or 'full', return full date/time (YYYY-MM-DD HH:MI:SS)
    If pattern = 'd', return date (YYYY-MM-DD)
    If pattern = 't', return time (HH:MI:SS)
    Otherwise try to use pattern literally (strftime)
    """
    if value is None:
        return valueNone
    if pattern is None or pattern.lower() in ['dt', 'full']:
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(value))
    elif pattern.lower() == 'd':
        return time.strftime('%Y-%m-%d', time.localtime(value))
    elif pattern.lower() == 't':
        return time.strftime('%H:%M:%S', time.localtime(value))
    else:
        return time.strftime(pattern, time.localtime(value))

def strToTs(value):
    """Convert a string to timestamp

    If value is a numeric value, return value

    Value must be in form:
    - YYYY-MM-DD HH:MI:SS
    - YYYY-MM-DD            (consider time is 00:00:00)
    - HH:MI:SS              (consider date is current date)

    otherwise return 0
    """
    if value is None or value == '':
        return None
    if isinstance(value, float) or isinstance(value, int):
        return value

    fmt = re.match("^(\d{4}-\d{2}-\d{2})?\s*(\d{2}:\d{2}:\d{2})?$", value)
    if not fmt is None:
        if fmt.group(1) is None:
            value = time.strftime('%Y-%m-%d ') + value
        if fmt.group(2) is None:
            value += ' 00:00:00'

        return time.mktime(time.strptime(value, '%Y-%m-%d %H:%M:%S'))

    return 0

def frToStrTime(nbFrames, frameRate):
    """Convert a number of frame to duration"""
    returned_ss=int(nbFrames/frameRate)
    returned_ff=nbFrames - returned_ss * frameRate
    returned_mn=int(returned_ss/60)
    returned_ss=returned_ss - returned_mn * 60

    return f"{returned_mn:02d}:{returned_ss:02d}.{returned_ff:02d}"

def secToStrTime(nbSeconds):
    """Convert a number of seconds to duration"""
    returned = ''
    nbDays = floor(nbSeconds / 86400)
    if nbDays > 0:
        nbSeconds = nbSeconds - nbDays * 86400
        returned = f'{nbDays}D, '

    returned+=time.strftime('%H:%M:%S', time.gmtime(nbSeconds))

    return returned

def getLangValue(dictionary, lang=None, default=''):
    """Return value from a dictionary for which key is lang code (like en-US)

    if `dictionary` is empty:
        return `default` value
    if `dictionary` contains one entry only:
        return it

    if `lang` is None:
        use current locale

    if `lang` exist in dictionary:
        return it
    else if language exist (with different country code):
        return it
    else if 'en-XX' exists:
        return it
    else:
        return first entry
    """
    if not isinstance(dictionary, dict):
        raise Exception('Given `dictionary` must be a valid <dict> value')

    if len(dictionary) == 0:
        return default
    elif len(dictionary) == 1:
        return dictionary[list(dictionary.keys())[0]]

    if lang is None:
        lang = locale.getlocale()[0].replace('_','-')

    if lang in dictionary:
        return dictionary[lang]
    else:
        language = lang.split('-')[0]
        for key in dictionary.keys():
            keyLang = key.split('-')[0]

            if keyLang == language:
                return dictionary[key]

        # not found, try "en"
        language = 'en'
        for key in dictionary.keys():
            keyLang = key.split('-')[0]

            if keyLang == language:
                return dictionary[key]

        # not found, return first entry
        return dictionary[list(dictionary.keys())[0]]

def checkerBoardBrush(size=32):
    """Return a checker board brush"""
    tmpPixmap = QPixmap(size,size)
    tmpPixmap.fill(QColor(255,255,255))
    brush = QBrush(QColor(220,220,220))

    canvas = QPainter()
    canvas.begin(tmpPixmap)
    canvas.setPen(Qt.NoPen)

    s1 = size>>1
    s2 = size - s1

    canvas.setRenderHint(QPainter.Antialiasing, False)
    canvas.fillRect(QRect(0, 0, s1, s1), brush)
    canvas.fillRect(QRect(s1, s1, s2, s2), brush)
    canvas.end()

    return QBrush(tmpPixmap)

def checkerBoardImage(size, checkerSize=32):
    """Return a checker board image"""
    if isinstance(size, int):
        size = QSize(size, size)

    if not isinstance(size, QSize):
        return None

    pixmap = QPixmap(size)
    painter = QPainter(pixmap)
    painter.begin()
    painter.fillRect(pixmap.rect(), checkerBoardBrush(checkerSize))
    painter.end()

    return pixmap

def buildIcon(icons):
    """Return a QIcon from given icons"""
    if isinstance(icons, QIcon):
        return icons
    elif isinstance(icons, list) and len(icons)>0:
        returned = QIcon()
        for icon in icons:
            returned.addPixmap(icon[0], icon[1])
        return returned
    else:
        raise EInvalidType("Given `icons` must be a list of tuples")

def kritaVersion():
    """Return a dictionary with following values:

    {
        'major': 0,
        'minor': 0,
        'revision': 0,
        'devRev': '',
        'git': '',
        'rawString': ''
    }

    Example:
        "5.0.0-prealpha (git 8f2fe10)"
        will return

        {
            'major': 5,
            'minor': 0,
            'revision', 0,
            'devFlag': 'prealpha',
            'git': '8f2fe10',
            'rawString': '5.0.0-prealpha (git 8f2fe10)'
        }
    """
    returned={
            'major': 0,
            'minor': 0,
            'revision': 0,
            'devFlag': '',
            'git': '',
            'rawString': Krita.instance().version()
        }
    nfo=re.match("(\d+)\.(\d+)\.(\d+)(?:-([^\s]+)\s\(git\s([^\)]+)\))?", returned['rawString'])
    if not nfo is None:
        returned['major']=int(nfo.groups()[0])
        returned['minor']=int(nfo.groups()[1])
        returned['revision']=int(nfo.groups()[2])
        returned['devFlag']=nfo.groups()[3]
        returned['git']=nfo.groups()[4]

    return returned

def checkKritaVersion(major, minor, revision):
    """Return True if current version is greater or equal to asked version"""
    nfo = kritaVersion()

    if major is None:
        return True
    elif nfo['major']==major:
        if minor is None:
            return True
        elif nfo['minor']==minor:
            if revision is None or nfo['revision']>=revision:
                return True
        elif nfo['minor']>minor:
            return True
    elif nfo['major']>major:
        return True
    return False

def strToMaxLength(value, maxLength, completeSpace=True):
    """Format given string `value` to fit in given `maxLength`

    If len is greater than `maxLength`, string is splitted with carriage return

    If value contains carriage return, each line is processed separately

    If `completeSpace` is True, value is completed with space characters to get
    the expected length.
    """
    returned = []
    if os.linesep in value:
        rows = value.split(os.linesep)

        for row in rows:
            returned.append(strToMaxLength(row, maxLength, completeSpace))
    else:
        textLen = len(value)

        if textLen < maxLength:
            if completeSpace:
                # need to complete with spaces
                returned.append( value + (' ' * (maxLength - textLen)))
            else:
                returned.append(value)
        elif textLen > maxLength:
            # keep spaces separators
            tmpWords=re.split('(\s)', value)
            words=[]

            # build words list
            for word in tmpWords:
                while len(word) > maxlength:
                    words.append(word[0:maxlength])
                    word=word[maxlength:]
                if word != '':
                    words.append(word)

            builtRow=''
            for word in words:
                if (len(builtRow) + len(word))<maxLength:
                    builtRow+=word
                else:
                    returned.append(strToMaxLength(builtRow, maxLength, completeSpace))
                    builtRow=word

            if builtRow!='':
                returned.append(strToMaxLength(builtRow, maxLength, completeSpace))
        else:
            returned.append(value)

    return os.linesep.join(returned)

def stripTags(value):
    """Strip HTML tags and remove amperseed added by Qt"""
    return re.sub('<[^<]+?>', '', re.sub('<br/?>', os.linesep, value))  \
                .replace('&nbsp;', ' ')     \
                .replace('&gt;', '>')       \
                .replace('&lt;', '<')       \
                .replace('&amp;', '&&')     \
                .replace('&&', chr(1))      \
                .replace('&', '')           \
                .replace(chr(1), '&')


# ------------------------------------------------------------------------------
class BCTable(object):
    """An object to store data in a table that can easily be exported as text"""
    BORDER_NONE = 0
    BORDER_BASIC = 1
    BORDER_SIMPLE = 2
    BORDER_DOUBLE = 3

    __BORDER_CHARS_TL=0
    __BORDER_CHARS_TM=1
    __BORDER_CHARS_TCA=2
    __BORDER_CHARS_TCB=3
    __BORDER_CHARS_TC=4
    __BORDER_CHARS_TR=5
    __BORDER_CHARS_BL=6
    __BORDER_CHARS_BM=7
    __BORDER_CHARS_BCA=8
    __BORDER_CHARS_BCB=9
    __BORDER_CHARS_BC=10
    __BORDER_CHARS_BR=11
    __BORDER_CHARS_RL=12
    __BORDER_CHARS_RM=13
    __BORDER_CHARS_RCA=14
    __BORDER_CHARS_RCB=15
    __BORDER_CHARS_RC=16
    __BORDER_CHARS_RR=17
    __BORDER_CHARS_SL=18
    __BORDER_CHARS_SM=19
    __BORDER_CHARS_SCA=20
    __BORDER_CHARS_SCB=21
    __BORDER_CHARS_SC=22
    __BORDER_CHARS_SR=23
    __BORDER_CHARS_HL=24
    __BORDER_CHARS_HM=25
    __BORDER_CHARS_HCA=26
    __BORDER_CHARS_HCB=27
    __BORDER_CHARS_HC=28
    __BORDER_CHARS_HR=29

    __BORDER_TYPE_SEP = 0
    __BORDER_TYPE_HSEP = 1
    __BORDER_TYPE_TOP = 2
    __BORDER_TYPE_BOTTOM = 3

    __BORDER_CHARS={
            # BCTable.BORDER_NONE
            0: [
                    '', '', '', '', '', '',             # tl, tm, tca, tcb, tc, tr
                    '', '', '', '', '', '',             # bl, bm, bca, bcb, bc, br
                    '', '', '', '', '', '',             # rl, rm, rca, rcb, rc, rr
                    '', '', '', '', '', '',             # sl, sm, sca, scb, sc, sr
                    '', '', '', '', '', ''              # hl, hm, hca, hcb, hc, hr
                ],
            # BCTable.BORDER_BASIC
            1: [
                    '+', '=', '+', '+', '+', '+',       # tl, tm, tca, tcb, tc, tr
                    '+', '=', '+', '+', '+', '+',       # bl, bm, bca, bcb, bc, br
                    '|', ' ', '|', '|', '|', '|',       # rl, rm, rca, rcb, rc, rr
                    '+', '-', '+', '+', '+', '+',       # sl, sm, sca, scb, sc, sr
                    '+', '=', '+', '+', '+', '+'        # hl, hm, hca, hcb, hc, hr
                ],
            # BCTable.BORDER_SIMPLE
            2: [
                    '┌', '─', '┬', '┬', '┬', '┐',       # tl, tm, tca, tcb, tc, tr
                    '└', '─', '┴', '┴', '┴', '┘',       # bl, bm, bca, bcb, bc, br
                    '│', ' ', '│', '│', '│', '│',       # rl, rm, rca, rcb, rc, rr
                    '├', '─', '┴', '┬', '┼', '┤',       # sl, sm, sca, scb, sc, sr
                    '├', '─', '┴', '┬', '┼', '┤'        # hl, hm, hca, hcb, hc, hr
                ],
            # BCTable.BORDER_DOUBLE
            3: [
                    '╔', '═', '╤', '╤', '╤', '╗',       # tl, tm, tca, tcb, tc, tr
                    '╚', '═', '╧', '╧', '╧', '╝',       # bl, bm, bca, bcb, bc, br
                    '║', ' ', '│', '│', '│', '║',       # rl, rm, rca, rcb, rc, rr
                    '╟', '─', '┴', '┬', '┼', '╢',       # sl, sm, sca, scb, sc, sr
                    '╠', '═', '╧', '╤', '╪', '╣'        # hl, hm, hca, hcb, hc, hr

                ]
        }

    def __init__(self):
        self.__nbRows = 0
        self.__nbCols = 0
        self.__header = []
        self.__rows = []
        self.__colSize = []
        self.__currentWidth = 0

        self.__title = ''

        self.__borderMode = BCTable.BORDER_BASIC

    def __repr__(self):
        return f"<BCTable()>"

    def addRow(self, rowContent):
        """Add a row to table

        A row can be:
        - a string (ie: one column)
        - an array of string; if number of columns is bigger than current columns
          count number, then this will define new columns count
          For rows with a number of columns less than total number of column, the
          first (or last, according to table configuration) will b e merged to
          extent colum size
        """
        if isinstance(rowContent, str):
            self.__rows.append([rowContent])
        elif isinstance(rowContent, list):
            self.__rows.append(rowContent)

    def addSeparator(self):
        """Add a separator in table"""
        self.__rows.append(0x01)

    def setHeader(self, headerContent):
        """Set a header to table

        A header can be:
        - a string (ie: one column)
        - an array of string; if number of columns is bigger than current columns
          count number, then this will define new columns count
        """
        if isinstance(headerContent, str):
            self.__header = [headerContent]
        elif isinstance(headerContent, list):
            self.__header = headerContent

    def setTitle(self, title=None):
        """Set current table title"""
        if isinstance(title, str) and title.strip()!='':
            self.__title = title
        else:
            self.__title = None

    def setBorderMode(self, mode):
        """Define border mode rendering method"""
        if mode in [BCTable.BORDER_NONE,
                    BCTable.BORDER_BASIC,
                    BCTable.BORDER_SIMPLE,
                    BCTable.BORDER_DOUBLE]:
            self.__borderMode = mode

    def asText(self, maxWidth=0, minWidth=0):
        """Return current table as a string

        If maxWidth = 0, there's no maximum width for table
        => maxWidth and minWidth values includes columns borders

        If mode is provided, it will overrides the table border mode, otherwise
        table border mode is used
        """
        def columnsWidth(row, ref=None):
            # calculate columns width
            returned = [0] * self.__nbColumns
            for index, column in enumerate(row):
                returned[index] = len(column)

            if not ref is None:
                for index in range(len(ref)):
                    if returned[index] < ref[index]:
                        returned[index] = ref[index]
            return returned

        def buildSep(columnsAbove=None, columnsBelow=None, sepType=None):
            # return a separator string, taking in account:
            # - columns above
            # - columns below
            # - render mode
            returned = ''
            headerOffset=0

            if columnsAbove is None:
                columnsAbove = 0
            if columnsBelow is None:
                columnsBelow = 0

            if sepType == BCTable.__BORDER_TYPE_TOP:
                headerOffset=-18
            elif sepType == BCTable.__BORDER_TYPE_BOTTOM:
                headerOffset=-12
            elif sepType == BCTable.__BORDER_TYPE_HSEP:
                headerOffset=6

            if self.__borderMode == BCTable.BORDER_NONE:
                # doesn't take in account above and below rows
                returned = '-' * self.__currentWidth
            else:
                returned = BCTable.__BORDER_CHARS[self.__borderMode][BCTable.__BORDER_CHARS_SL+headerOffset]

                for index in range(self.__nbCols):
                    returned += BCTable.__BORDER_CHARS[self.__borderMode][BCTable.__BORDER_CHARS_SM+headerOffset] * self.__colSize[index]
                    if index < (self.__nbCols - 1):
                        # add columns separator
                        offset = 0
                        if (index + 1) < columnsAbove:
                            offset += 0b01
                        if (index + 1) < columnsBelow:
                            offset += 0b10
                        returned += BCTable.__BORDER_CHARS[self.__borderMode][BCTable.__BORDER_CHARS_SM + offset + headerOffset]

                returned += BCTable.__BORDER_CHARS[self.__borderMode][BCTable.__BORDER_CHARS_SR + headerOffset]

            return [returned]

        def buildRow(columnsContent, columnsSize=None):
            # return a separator string, taking in account:
            # - columns content
            # - columns sizes
            # - render mode
            returned = []

            if columnsSize is None:
                columnsSize = self.__colSize

            nbRows=0
            colsContent=[]

            for index, column in enumerate(columnsContent):
                fmtRow=strToMaxLength(column, columnsSize[index], True).split(os.linesep)
                colsContent.append(fmtRow)

                nbFmtRows=len(fmtRow)
                if nbFmtRows > nbRows:
                    nbRows = nbFmtRows

            lastColIndex = len(columnsContent) -1
            for rowIndex in range(nbRows):
                returnedRow=BCTable.__BORDER_CHARS[self.__borderMode][BCTable.__BORDER_CHARS_RL]

                for colIndex, column in enumerate(colsContent):
                    if rowIndex < len(column):
                        returnedRow+=column[rowIndex]
                    else:
                        returnedRow+=strToMaxLength(' ', columnsSize[colIndex], True)

                    if colIndex < lastColIndex:
                        returnedRow+=BCTable.__BORDER_CHARS[self.__borderMode][BCTable.__BORDER_CHARS_RC]

                returnedRow+=BCTable.__BORDER_CHARS[self.__borderMode][BCTable.__BORDER_CHARS_RR]
                returned.append(returnedRow)

            return returned

        def buildTitle():
            """Add a title to generated table"""
            return [f'[ {self.__title} ]']

        def buildHeader():
            returned=[]

            if len(self.__header) == 0:
                # no header
                if len(self.__rows) == 0:
                    # no rows...
                    return returned

                returned+=buildSep(None, len(self.__rows[0]), BCTable.__BORDER_TYPE_TOP)
            else:
                returned+=buildSep(None, len(self.__header), BCTable.__BORDER_TYPE_TOP)
                returned+=buildRow(self.__header)

                if len(self.__rows) == 0:
                    # no rows...
                    returned+=buildSep(len(self.__header), None, BCTable.__BORDER_TYPE_BOTTOM)
                else:
                    returned+=buildSep(len(self.__header), len(self.__rows[0]), BCTable.__BORDER_TYPE_HSEP)

            return returned

        # one text row = one buffer row
        buffer=[]

        # 1. calculate number of columns
        # ------------------------------
        self.__nbColumns = len(self.__header)
        for row in self.__rows:
            if isinstance(row, list) and len(row) > self.__nbColumns:
                self.__nbColumns = len(row)

        # 2. calculate columns width
        # --------------------------
        self.__colSize = columnsWidth(self.__header)
        for row in self.__rows:
            if isinstance(row, list):
                self.__colSize = columnsWidth(row, self.__colSize)
        self.__nbCols=len(self.__colSize)

        # 3. Adjust columns width according to min/max table width
        # --------------------------------------------------------
        if self.__borderMode == BCTable.BORDER_NONE:
            # no external borders
            extBorderSize = -1
        else:
            # 2 external borders
            extBorderSize = 1
        self.__currentWidth = sum(self.__colSize) + self.__nbColumns + extBorderSize

        expectedWidth=None
        if maxWidth > 0 and self.__currentWidth > maxWidth:
            # need to reduce columns sizes
            expectedWidth=maxWidth
        elif minWidth > 0 and self.__currentWidth < minWidth:
            # need to increase columns sizes
            expectedWidth=minWidth

        if not expectedWidth is None:
            # need to apply factor size to columns width
            factor = expectedWidth / self.__currentWidth
            fixedWidth = 0

            for index in range(self.__nbColumns - 1):
                self.__colSize[index]=int(round(self.__colSize[index] * factor, 0))
                fixedWidth+=self.__colSize[index]

            self.__colSize[-1]=expectedWidth - fixedWidth - (self.__nbColumns + extBorderSize)
            self.__currentWidth = expectedWidth


        # 4. Generate table
        # --------------------------------------------------------
        lastRowIndex = len(self.__rows) - 1

        buffer+=buildTitle()
        buffer+=buildHeader()

        prevColCount = None
        nextColCount = None
        lastIndex = len(self.__rows) - 1
        for index, row in enumerate(self.__rows):
            if row == 0x01:
                if index > 1 and index < lastIndex:
                    nextColCount = len(self.__rows[index + 1])
                else:
                    nextColCount = None
                buffer+=buildSep(prevColCount, nextColCount)
            else:
                buffer+=buildRow(row)
                prevColCount=len(row)

        buffer+=buildSep(prevColCount, None, BCTable.__BORDER_TYPE_BOTTOM)

        return os.linesep.join(buffer)



class Stopwatch(object):
    """Manage stopwatch, mainly used for performances test & debug"""
    __current = {}

    @staticmethod
    def reset():
        """Reset all Stopwatches"""
        Stopwatch.__current = {}

    @staticmethod
    def start(name):
        """Start a stopwatch

        If stopwatch already exist, restart from now
        """
        Stopwatch.__current[name] = {'start': time.time(),
                                     'stop': None
                                }

    @staticmethod
    def stop(name):
        """Stop a stopwatch

        If stopwatch doesn't exist or is already stopped, do nothing
        """
        if name in Stopwatch.__current and Stopwatch.__current[name]['stop'] is None:
            Stopwatch.__current[name]['stop'] = time.time()

    @staticmethod
    def duration(name):
        """Return stopwatch duration, in seconds

        If stopwatch doesn't exist, return None
        If stopwatch is not stopped, return current duration from start time
        """
        if name in Stopwatch.__current:
            if Stopwatch.__current[name]['stop'] is None:
                return time.time() - Stopwatch.__current[name]['start']
            else:
                return Stopwatch.__current[name]['stop'] - Stopwatch.__current[name]['start']


class Debug(object):
    """Display debug info to console if debug is enabled"""
    __enabled = False

    @staticmethod
    def print(value, *argv):
        """Print value to console, using argv for formatting"""
        if Debug.__enabled and isinstance(value, str):
            sys.stdout = sys.__stdout__
            print('DEBUG:', value.format(*argv))

    def enabled():
        """return if Debug is enabled or not"""
        return Debug.__enabled

    def setEnabled(value):
        """set Debug enabled or not"""
        Debug.__enabled=value
