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


import re
import time


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

def bytesSizeToStr(value, unit='AutoBin', decimals=2):
    """Convert a size (given in Bytes) to given unit

    Given unit can be:
    - 'Auto'
    - 'AutoBin' (binary Bytes)
    - 'GiB', 'MiB', 'KiB' (binary Bytes)
    - 'GB', 'MB', 'KB', 'B'
    """
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


def tsToStr(value, pattern=None):
    """Convert a timestamp to localtime string

    If no pattern is provided or if pattern = 'dt' or 'full', return full date/time (YYYY-MM-DD HH:MI:SS)
    If pattern = 'd', return date (YYYY-MM-DD)
    If pattern = 't', return time (HH:MI:SS)
    Otherwise try to use pattern literally (strftime)
    """
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
            print('DEBUG:', value.format(*argv))

    def enabled():
        """return if Debug is enabled or not"""
        return Debug.__enabled

    def setEnabled(value):
        """set Debug enabled or not"""
        Debug.__enabled=value



if __name__ == '__main__':
    import os.path

    for unit in ['GB', 'GiB', 'MB', 'MiB', 'KB', 'KiB', 'B', '']:
        v1 = '2.35' + unit
        v2 = '.78' + unit
        v3 = '1' + unit
        print("To BS", v1, '=', strToBytesSize(v1), '/', v2,  '=', strToBytesSize(v2),  '/', v3, '=',  strToBytesSize(v3))
        print("From BS (auto)", v1, '=', bytesSizeToStr(strToBytesSize(v1), 'auto'), '/', v2,  '=', bytesSizeToStr(strToBytesSize(v2), 'auto'),  '/', v3, '=', bytesSizeToStr(strToBytesSize(v3), 'auto'))
        print("From BS (autobin)", v1, '=', bytesSizeToStr(strToBytesSize(v1)), '/', v2,  '=', bytesSizeToStr(strToBytesSize(v2)),  '/', v3, '=', bytesSizeToStr(strToBytesSize(v3)))
        print("From BS (GiB)", v1, '=', bytesSizeToStr(strToBytesSize(v1), 'GiB'), '/', v2,  '=', bytesSizeToStr(strToBytesSize(v2), 'GiB'),  '/', v3, '=', bytesSizeToStr(strToBytesSize(v3), 'GiB'))
        print("From BS (MiB)", v1, '=', bytesSizeToStr(strToBytesSize(v1), 'MiB'), '/', v2,  '=', bytesSizeToStr(strToBytesSize(v2), 'MiB'),  '/', v3, '=', bytesSizeToStr(strToBytesSize(v3), 'MiB'))
        print("From BS (KiB)", v1, '=', bytesSizeToStr(strToBytesSize(v1), 'KiB'), '/', v2,  '=', bytesSizeToStr(strToBytesSize(v2), 'KiB'),  '/', v3, '=', bytesSizeToStr(strToBytesSize(v3), 'KiB'))

    fn="/home/grum/Temporaire/Temp/3615ygal.xcf"
    print(tsToStr(os.path.getmtime(fn)))
    print(tsToStr(os.path.getmtime(fn), 'd'))
    print(tsToStr(os.path.getmtime(fn), 't'))

    print(os.path.getmtime(fn))
    print(strToTs('2016-12-20 00:34:20'))
    print(strToTs('2016-12-20'))
    print(strToTs('12:30:30'))

    print(tsToStr(strToTs('2016-12-20 00:34:20')))
    print(tsToStr(strToTs('2016-12-20')))
    print(tsToStr(strToTs('00:34:20')))



