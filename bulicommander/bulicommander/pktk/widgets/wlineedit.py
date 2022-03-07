#-----------------------------------------------------------------------------
# PyKritaToolKit
# Copyright (C) 2019-2022 - Grum999
#
# A toolkit to make pykrita plugin coding easier :-)
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




# -----------------------------------------------------------------------------

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )
from PyQt5.QtWidgets import (
        QWidget
    )



class WLineEdit(QLineEdit):
    """A QLineEdit with signals emitted when focus In/Out changed"""
    focusIn=Signal()
    focusOut=Signal()
    keyPressed=Signal(QKeyEvent, str, str)

    def focusInEvent(self, event):
        super(WLineEdit, self).focusInEvent(event)
        self.focusIn.emit()

    def focusOutEvent(self, event):
        super(WLineEdit, self).focusOutEvent(event)
        self.focusOut.emit()

    def keyPressEvent(self, event):
        before=self.text()
        super(WLineEdit, self).keyPressEvent(event)
        self.keyPressed.emit(event, self.text(), before)
