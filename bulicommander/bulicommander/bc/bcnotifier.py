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


from PyQt5.QtWidgets import (
        QSystemTrayIcon
    )
from PyQt5.QtGui import (
        QIcon,
        QPixmap
    )
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QEventLoop,
        QTimer
    )
from .bcutils import buildIcon

class BCNotifier(object):
    """Manage notifier in system tray"""

    __buliIcon = buildIcon([(QPixmap(':/buli/buli-rounded-border'), QIcon.Normal)])
    __tray = QSystemTrayIcon(__buliIcon, Krita.instance())
    __alwaysVisible = False

    @staticmethod
    def init():
        BCNotifier.__tray.activated.connect(BCNotifier.__activated)

    @staticmethod
    def __activated(activationReason):
        """System tray icon has been activated"""
        if activationReason == QSystemTrayIcon.Context:
            print('[BCNotifier] Display context menu')
        elif QSystemTrayIcon.DoubleClick:
            # Seems a simple click is enough to trigger signal
            # (Qt 5.12.9 // Linux Debian 10 // KDE Plasma)
            print('[BCNotifier] Double click')
        else:
            print('[BCNotifier] Unknown')

    @staticmethod
    def visible(self):
        """Return if icon is visible in system tray"""
        return BCNotifier.__alwaysVisible

    @staticmethod
    def setVisible(self, visible):
        """Set if icon is visible in system tray"""
        BCNotifier.__alwaysVisible=visible
        BCNotifier.__tray.setVisible(visible)

    @staticmethod
    def __popMessage(title, message, icon):
        """Display an information message"""
        def hide():
            # hide icon in tray
            loop.quit()
            BCNotifier.__tray.hide()

        if BCNotifier.__alwaysVisible:
            BCNotifier.__tray.showMessage(title, message, icon)
        else:
            BCNotifier.__tray.show()
            BCNotifier.__tray.showMessage(title, message, icon)

            # wait 10s before hiding icon in tray
            loop = QEventLoop()
            QTimer.singleShot(10000, hide)


    @staticmethod
    def messageInformation(title, message):
        """Display an information message"""
        BCNotifier.__popMessage(title, message, QSystemTrayIcon.Information)

    @staticmethod
    def messageWarning(title, message):
        """Display a warning message"""
        BCNotifier.__popMessage(title, message, QSystemTrayIcon.Warning)

    @staticmethod
    def messageCritical(title, message):
        """Display a critical message"""
        BCNotifier.__popMessage(title, message, QSystemTrayIcon.Critical)



BCNotifier.init()
