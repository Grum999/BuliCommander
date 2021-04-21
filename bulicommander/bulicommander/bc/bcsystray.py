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

from PyQt5.Qt import *
from PyQt5.QtWidgets import (
        QAction,
        QMenu,
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
from pktk.modules.utils import Debug
from pktk.modules.imgutils import buildIcon

class BCSysTray(object):
    """Manage system tray"""

    SYSTRAY_MODE_NEVER = 0
    SYSTRAY_MODE_FORNOTIFICATION = 1
    SYSTRAY_MODE_WHENACTIVE = 2
    SYSTRAY_MODE_ALWAYS = 3

    # whhhooo that's ugly ^_^'
    __selfInstance = None


    def __init__(self, uiController):
        """Initialise SysTray manager"""
        def actionAbout(action):
            self.__uiController.commandAboutBc()

        def actionDisplayBc(action):
            self.__displayBuliCommander()

        def actionQuitBc(action):
            self.__uiController.commandQuit()

        def actionClipboardManagerActive(action):
            self.__uiController.commandSettingsClipboardCacheSystrayMode(action)

        # Note: theme must be loaded before BCSysTray is instancied (otherwise no icon will be set)
        self.__buliIcon = buildIcon([(QPixmap(':/buli/buli-rounded-border'), QIcon.Normal)])
        self.__tray = QSystemTrayIcon(self.__buliIcon, Krita.instance())
        self.__visibleMode = 1 # when active
        self.__uiController = uiController

        self.__uiController.bcWindowShown.connect(self.__displaySysTrayIcon)
        self.__uiController.bcWindowClosed.connect(self.__hideSysTrayIcon)
        self.__tray.activated.connect(self.__activated)

        BCSysTray.__selfInstance = self

        self.__actionAbout=QAction(i18n('About Buli Commander...'))
        self.__actionAbout.triggered.connect(actionAbout)
        self.__actionOpenBc=QAction(i18n('Open Buli Commander...'))
        self.__actionOpenBc.triggered.connect(actionDisplayBc)
        self.__actionCloseBc=QAction(i18n('Quit Buli Commander'))
        self.__actionCloseBc.triggered.connect(actionQuitBc)

        self.__actionClipboardActive=QAction(i18n('Clipboard manager active'))
        self.__actionClipboardActive.triggered.connect(actionClipboardManagerActive)
        self.__actionClipboardActive.setCheckable(True)
        if not self.__uiController is None:
            self.__actionClipboardActive.setChecked(self.__uiController.commandSettingsClipboardCacheSystrayMode())

        self.__menu = QMenu()
        self.__menu.addAction(self.__actionClipboardActive)
        self.__menu.addSeparator()
        self.__menu.addAction(self.__actionAbout)
        self.__menu.addSeparator()
        self.__menu.addAction(self.__actionOpenBc)
        self.__menu.addSeparator()
        self.__menu.addAction(self.__actionCloseBc)

        self.__menu.aboutToShow.connect(self.__displayContextMenu)

        self.__tray.setContextMenu(self.__menu)


    def __displayContextMenu(self):
        """Display context menu on systray icon"""
        # menu

        # [ ] Clipboard manager active
        # ----------------------------
        #     About BC
        # ----------------------------
        #     Open BC
        #     Quit BC
        self.__actionClipboardActive.setEnabled((self.__uiController.commandSettingsClipboardCacheMode() != 'manual'))


    def __displayBuliCommander(self):
        """Display buli commander"""
        if self.__uiController.started():
            self.__uiController.commandViewBringToFront()
        else:
            self.__uiController.start()


    def __activated(self, activationReason):
        """System tray icon has been activated"""
        if activationReason == QSystemTrayIcon.Context:
            # in fact, does nothing if context menu is set...?
            # use menu.aboutToShow() instead
            pass
        elif QSystemTrayIcon.DoubleClick:
            self.__displayBuliCommander()
        else:
            Debug.print('[BCSysTray] Unknown')


    def __displaySysTrayIcon(self):
        """Display systray if allowed by mode"""
        self.__actionOpenBc.setVisible(not self.__uiController.started())
        self.__actionCloseBc.setVisible(self.__uiController.started())

        if self.__visibleMode==BCSysTray.SYSTRAY_MODE_ALWAYS:
            self.__tray.show()
        elif self.__visibleMode==BCSysTray.SYSTRAY_MODE_WHENACTIVE:
            if not self.__uiController is None:
                if self.__uiController.started():
                    self.__tray.show()
                elif self.__uiController.started():
                    self.__tray.hide()
        else:
            # SYSTRAY_MODE_NEVER
            # SYSTRAY_MODE_FORNOTIFICATION
            self.__tray.hide()


    def __hideSysTrayIcon(self):
        """Hide systray if allowed by mode"""
        self.__actionOpenBc.setVisible(not self.__uiController.started())
        self.__actionCloseBc.setVisible(self.__uiController.started())

        if self.__visibleMode!=BCSysTray.SYSTRAY_MODE_ALWAYS:
            self.__tray.hide()


    def visible(self):
        """Return if icon is currently visible in system tray"""
        return self.__tray.isVisible()


    def visibleMode(self):
        """Return current Systray visible mode"""
        return self.__visibleMode


    def setVisibleMode(self, mode):
        """Set current Systray visible mode"""
        if not mode in [BCSysTray.SYSTRAY_MODE_NEVER,
                        BCSysTray.SYSTRAY_MODE_FORNOTIFICATION,
                        BCSysTray.SYSTRAY_MODE_WHENACTIVE,
                        BCSysTray.SYSTRAY_MODE_ALWAYS]:
            raise EInvalidValue("Given `mode` is not valid")

        self.__visibleMode=mode
        self.__displaySysTrayIcon()


    def __popMessage(self, title, message, icon):
        """Display an information message"""
        def hide():
            # hide icon in tray
            loop.quit()
            self.__hideSysTrayIcon()

        if self.__visibleMode in [BCSysTray.SYSTRAY_MODE_ALWAYS, BCSysTray.SYSTRAY_MODE_WHENACTIVE]:
            self.__tray.showMessage(title, message, icon)
        elif self.__visibleMode == BCSysTray.SYSTRAY_MODE_FORNOTIFICATION:
            self.__tray.show()
            self.__tray.showMessage(title, message, icon)

            # wait 5s before hiding icon in tray
            loop = QEventLoop()
            QTimer.singleShot(5000, hide)
        elif self.__visibleMode == BCSysTray.SYSTRAY_MODE_NEVER:
            tmpTray = QSystemTrayIcon(Krita.instance())
            tmpTray.show()
            tmpTray.showMessage(title, message, icon)
            tmpTray.hide()


    @staticmethod
    def messageInformation(title, message):
        """Display an information message"""
        BCSysTray.__selfInstance.__popMessage(title, message, QSystemTrayIcon.Information)

    @staticmethod
    def messageWarning(title, message):
        """Display a warning message"""
        BCSysTray.__selfInstance.__popMessage(title, message, QSystemTrayIcon.Warning)

    @staticmethod
    def messageCritical(title, message):
        """Display a critical message"""
        BCSysTray.__selfInstance.__popMessage(title, message, QSystemTrayIcon.Critical)
