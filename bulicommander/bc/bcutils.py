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

import locale
import re
import time
import sys


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

def checkerBoardBrush(self, size=32):
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
