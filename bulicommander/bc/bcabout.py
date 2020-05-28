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
import os

import PyQt5.uic

from PyQt5.Qt import *
from PyQt5.QtWidgets import (
        QDialog
    )


# -----------------------------------------------------------------------------
class BCAboutWindow(QDialog):
    """About Buli Commander window"""

    def __init__(self, bcName="Buli Commander", bcVersion="testing"):
        super(BCAboutWindow, self).__init__()

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcabout.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.setWindowTitle(i18n(f'About {bcName}'))
        self.setWindowFlags(Qt.Dialog|Qt.WindowTitleHint)
        self.setWindowFlags(self.windowFlags()&~Qt.WindowMinMaxButtonsHint)
        self.lblKcName.setText(bcName)
        self.lblKcVersion.setText(f'v{bcVersion}')

        self.dbbxOk.accepted.connect(self.close)

        self.exec_()

