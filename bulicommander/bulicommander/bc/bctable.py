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
from .bcutils import (
    strToMaxLength
)

import os

class BCTableSettings(object):
    """Define settings to render a table"""
    MIN_WIDTH = 1
    MAX_WIDTH = 512

    def __init__(self):
        self.__border = BCTable.BORDER_DOUBLE
        self.__headerActive = True
        self.__minWidthActive = True
        self.__minWidthValue = 80
        self.__maxWidthActive = False
        self.__maxWidthValue = 120

    def border(self):
        return self.__border

    def setBorder(self, border):
        if border in [BCTable.BORDER_NONE,
                      BCTable.BORDER_BASIC,
                      BCTable.BORDER_SIMPLE,
                      BCTable.BORDER_DOUBLE]:
            self.__border = border

    def headerActive(self):
        return self.__headerActive

    def setHeaderActive(self, headerActive):
        if isinstance(headerActive, bool):
            self.__headerActive = headerActive

    def minWidthActive(self):
        return self.__minWidthActive

    def setMinWidthActive(self, minWidthActive):
        if isinstance(minWidthActive, bool):
            self.__minWidthActive = minWidthActive

    def maxWidthActive(self):
        return self.__maxWidthActive

    def setMaxWidthActive(self, maxWidthActive):
        if isinstance(maxWidthActive, bool):
            self.__maxWidthActive = maxWidthActive

    def minWidth(self):
        return self.__minWidthValue

    def setMinWidth(self, minWidth):
        if isinstance(minWidth, int) and minWidth >= BCTableSettings.MIN_WIDTH and minWidth <= BCTableSettings.MAX_WIDTH:
            self.__minWidthValue = minWidth

    def maxWidth(self):
        return self.__maxWidthValue

    def setMaxWidth(self, maxWidth):
        if isinstance(maxWidth, int) and maxWidth >= BCTableSettings.MIN_WIDTH and maxWidth <= BCTableSettings.MAX_WIDTH:
            self.__maxWidthValue = maxWidth


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

    def asText(self, settings):
        """Return current table as a string, ussing given settings (BCTableSettings)"""
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

            if settings.border() == BCTable.BORDER_NONE:
                # doesn't take in account above and below rows
                returned = '-' * self.__currentWidth
            else:
                returned = BCTable.__BORDER_CHARS[settings.border()][BCTable.__BORDER_CHARS_SL+headerOffset]

                for index in range(self.__nbCols):
                    returned += BCTable.__BORDER_CHARS[settings.border()][BCTable.__BORDER_CHARS_SM+headerOffset] * self.__colSize[index]
                    if index < (self.__nbCols - 1):
                        # add columns separator
                        offset = 0
                        if (index + 1) < columnsAbove:
                            offset += 0b01
                        if (index + 1) < columnsBelow:
                            offset += 0b10
                        returned += BCTable.__BORDER_CHARS[settings.border()][BCTable.__BORDER_CHARS_SM + offset + headerOffset]

                returned += BCTable.__BORDER_CHARS[settings.border()][BCTable.__BORDER_CHARS_SR + headerOffset]

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
                returnedRow=BCTable.__BORDER_CHARS[settings.border()][BCTable.__BORDER_CHARS_RL]

                for colIndex, column in enumerate(colsContent):
                    if rowIndex < len(column):
                        returnedRow+=column[rowIndex]
                    else:
                        returnedRow+=strToMaxLength(' ', columnsSize[colIndex], True)

                    if colIndex < lastColIndex:
                        returnedRow+=BCTable.__BORDER_CHARS[settings.border()][BCTable.__BORDER_CHARS_RC]

                returnedRow+=BCTable.__BORDER_CHARS[settings.border()][BCTable.__BORDER_CHARS_RR]
                returned.append(returnedRow)

            return returned

        def buildTitle():
            """Add a title to generated table"""
            return [f'[ {self.__title} ]']

        def buildHeader():
            returned=[]

            if len(self.__header) == 0 or not settings.headerActive():
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

        if not isinstance(settings, BCTableSettings):
            raise EInvalidType("Given `settings` must be BCTableSettings")


        maxWidth = settings.maxWidth()
        if not settings.maxWidthActive():
            maxWidth = 0

        minWidth = settings.minWidth()
        if not settings.minWidthActive():
            minWidth = 1


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
        if settings.border() == BCTable.BORDER_NONE:
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
            nextIndex = index + 1
            while nextIndex < (len(self.__rows) - 1 ) and isinstance(self.__rows[nextIndex], int):
                nextIndex+=1

            if nextIndex > (len(self.__rows) - 1 ) or nextIndex < (len(self.__rows) - 1 ) and isinstance(self.__rows[nextIndex], int):
                nextRow = None
            else:
                nextRow = self.__rows[nextIndex]

            if row == 0x01:
                if not nextRow is None:
                    nextColCount = len(nextRow)
                else:
                    nextColCount = None
                buffer+=buildSep(prevColCount, nextColCount)
            else:
                buffer+=buildRow(row)
                prevColCount=len(row)

        buffer+=buildSep(prevColCount, None, BCTable.__BORDER_TYPE_BOTTOM)

        return os.linesep.join(buffer)

