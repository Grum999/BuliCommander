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
import PyQt5.uic

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )
from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QFrame,
        QHBoxLayout,
        QVBoxLayout,
        QLabel,
        QMenu,
        QSlider,
        QWidget
    )




class BCMenuSlider(QWidgetAction):
    """Encapsulate a slider as a menu item"""
    def __init__(self, label, parent=None):
        super(BCMenuSlider, self).__init__(parent)

        self.__widget = QWidget()
        self.__layout = QVBoxLayout()
        self.__slider = QSlider()
        self.__slider.setOrientation(Qt.Horizontal)

        if not label is None and label != '':
            self.__layout.addWidget(QLabel(label))
        self.__layout.addWidget(self.__slider)
        self.__widget.setLayout(self.__layout)
        self.setDefaultWidget(self.__widget)

    def slider(self):
        return self.__slider


class BCMenuTitle(QWidgetAction):
    """Encapsulate a QLabel as a menu item title"""
    def __init__(self, label, parent=None):
        super(BCMenuTitle, self).__init__(parent)

        self.__widget = QWidget()
        self.__layout = QVBoxLayout()
        self.__label = QLabel(label)
        self.__label.setStyleSheet("background-color: palette(light);padding: 3; font: bold;")
        self.__layout.addWidget(self.__label)
        self.__widget.setLayout(self.__layout)
        self.setDefaultWidget(self.__widget)

