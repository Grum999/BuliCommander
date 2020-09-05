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


# Build resources files:
#   cd bulicommander/bc/resources
#   /usr/lib/qt5/bin/rcc --binary -o ./lighttheme_icons.rcc light_icons.qrc
#   /usr/lib/qt5/bin/rcc --binary -o ./darktheme_icons.rcc dark_icons.qrc


import krita
import os

from PyQt5.QtCore import (
        QResource
    )
from PyQt5.QtGui import (
        QPalette
    )

class BCTheme(object):
    """Manage theme"""

    DARK_THEME = 'dark'
    LIGHT_THEME = 'light'

    STYLES_SHEET = {
        'dark': {
                'warning-label': 'background-color: rgba(255, 255, 200, 75%); color:#440000; border: 1px solid rgba(255, 255, 200, 25%); border-radius: 3px; font-weight: bold;'
            },
        'light': {

            }
    }


    def __init__(self):
        print("===[BCTheme:__init__]===")
        self.__theme = BCTheme.DARK_THEME
        self.__registeredResource = None

        self.loadResources()


    def loadResources(self):
        """Load resourdes for current theme"""

        print("===[BCTheme:loadResources]===")
        if not Krita.activeWindow() is None:
            print("===[BCTheme:loadResources>>active window=YES]===")
            if not self.__registeredResource is None:
                print("===[BCTheme:loadResources>>unregister=YES]===")
                QResource.unregisterResource(self.__registeredResource)

            palette = Krita.activeWindow().qwindow().palette()

            if palette.color(QPalette.Window).value() <= 128:
                self.__theme = BCTheme.DARK_THEME
            else:
                self.__theme = BCTheme.LIGHT_THEME

            self.__registeredResource = os.path.join(os.path.dirname(__file__), 'resources', f'{self.__theme}theme_icons.rcc')
            print("===[BCTheme:loadResources>>__registeredResource]===", self.__registeredResource)

            if not QResource.registerResource(self.__registeredResource):
                print("===[BCTheme:loadResources>>QResource=No]===")
                self.__registeredResource = None

    def theme(self):
        """Return current theme"""
        return self.__theme

    def style(self, name):
        """Return style according to current theme"""
        if name in BCTheme.STYLES_SHEET[self.__theme]:
            return BCTheme.STYLES_SHEET[self.__theme][name]
        elif self.__theme != BCTheme.DARK_THEME and name in BCTheme.STYLES_SHEET[BCTheme.DARK_THEME]:
            return BCTheme.STYLES_SHEET[self.__theme][name]
        return ''


