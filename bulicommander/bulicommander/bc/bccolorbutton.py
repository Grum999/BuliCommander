#-----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
from math import ceil

import PyQt5.uic

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )
from PyQt5.QtWidgets import (
        QPushButton,
    )

class BCColorButton(QPushButton):
    """A button to choose color"""
    colorChanged = Signal(QColor)

    def __init__(self, label, parent=None):
        super(BCColorButton, self).__init__(parent)

        def newSetText(value):
            # don't let external code trying to set button text: there's no text :)
            pass

        self.__color = Qt.white
        self.__brush = QBrush(self.__color, Qt.SolidPattern)
        self.__cbBrush = self.__checkerBoardBrush(16)
        self.__pen = QPen(QColor("#88888888"))
        self.__pen.setWidth(1)

        self.setText("")
        self.setText=newSetText

    def __checkerBoardBrush(self, size=32):
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


    def paintEvent(self, event):
        super(BCColorButton, self).paintEvent(event)

        margin = ceil(self.height()/2)//2
        margin2 = margin<<1

        painter = QPainter(self)
        painter.fillRect(margin, margin, self.width() - margin2,  self.height() - margin2, self.__cbBrush)
        painter.setPen(self.__pen)
        painter.setBrush(self.__brush)
        painter.drawRect(margin, margin, self.width() - margin2,  self.height() - margin2)

    def mouseReleaseEvent(self, event):
        returnedColor = QColorDialog.getColor(self.__color, None, i18n("Choose color"), QColorDialog.ShowAlphaChannel|QColorDialog.DontUseNativeDialog)
        if returnedColor.isValid():
            self.setColor(returnedColor)
            self.colorChanged.emit(self.__color)

    def color(self):
        """Return current button color"""
        return self.__color

    def setColor(self, color):
        """Set current button color"""
        self.__color = QColor(color)
        self.__brush.setColor(self.__color)
