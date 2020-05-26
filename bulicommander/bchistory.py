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

import sys


if 'bulicommander.pktk.pktk' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.pktk.pktk'])
else:
    import bulicommander.pktk.pktk

from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

class BCHistory(list):
    """A BCHistory is a list on which a maximum number of items is defined

    When a new item is append to list, if maximum number is reached, the first
    item of list is removed

    If an item already exists in history, he's moved from the current position to
    the last position
    """
    def __init__(self, items=[], maxItems=25):
        super(BCHistory, self).__init__(items)
        self.__maxItems=0
        self.setMaxItems(maxItems)

    def setMaxItems(self, value):
        """Define maximum items that can be stored by history

        If provided number is lower than current number of items, list is truncated
        """
        if not isinstance(value, int):
            raise EInvalidType('Given `value` must be an <int>')
        if value < 0:
            # negative value = no maximum items in history
            value = -1
        if self.__maxItems != value:
            self.__maxItems = value
            if len(self) > self.__maxItems:
                self[:] = self[-self.__maxItems:]

    def maxItems(self):
        """Return current maximum items in a list"""
        return self.__maxItems

    def append(self, value):
        """Add a value to history"""
        try:
            position = self.index(value)
        except:
            # value not found
            position = None
        if not position is None:
            self.pop(position)
        if len(self)>=self.__maxItems:
            self[:] = self[-self.__maxItems+1:]
        super(BCHistory, self).append(value)
