# -----------------------------------------------------------------------------
# Qt navigation bar with breadcrumbs
# Andrey Makarov, 2019
# https://github.com/Winand/breadcrumbsaddressbar
# -----------------------------------------------------------------------------
# SPDX-License-Identifier: GPL-3.0-or-later
#
# https://spdx.org/licenses/GPL-3.0-or-later.html
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2019-2022 - Grum999
# -----------------------------------------------------------------------------
# Original widget from Andrey Makarov is published under MIT license and has
# been heavily modified for BuliCommander needs ^_^'
#
# Not possible here to list all technical changes, do a DIFF with original
# source code if you're interested about detailed modifications :-)
# ------------------------------------------------------------------------------

from pathlib import Path
import os
import sys
import re
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QFrame
from PyQt5.QtGui import QFont

from bulicommander.pktk.modules.imgutils import buildIcon

from PyQt5.QtCore import (
        pyqtSignal as Signal,
        Qt
    )
from PyQt5.Qt import *

if __package__:  # https://stackoverflow.com/a/28151907
    from .models_views import FilenameModel, MenuListView
    from .layouts import LeftHBoxLayout
else:
    from models_views import FilenameModel, MenuListView
    from layouts import LeftHBoxLayout


class BreadcrumbsAddressBar(QFrame):
    "Windows Explorer-like address bar"
    listdir_error = Signal(Path)  # failed to list a directory
    path_error = Signal(Path)  # entered path does not exist
    path_selected = Signal(Path)
    view_selected = Signal(str)
    clicked = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)

        self.file_ico_prov = QtWidgets.QFileIconProvider()
        self.fs_model = FilenameModel('dirs', icon_provider=self.get_icon, breadcrumbs=self)

        self.__paletteBase = None
        self.__paletteHighlighted = None
        self.updatePalette()

        self.__isHighlighted = False
        self.__hiddenPath = False

        self.__quickRef = None

        self.__iconSize = QtCore.QSize(32, 32)  # px, size of generated semi-transparent icons

        self.setPalette(self.__paletteBase)

        self.setFrameShape(self.NoFrame)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        self.font = QFont()
        self.font.setPointSize(9)
        self.font.setFamily('DejaVu Sans Mono, Consolas, Courier New')

        # A label used to display view name (when view reference is used)
        self.viewName = QtWidgets.QLabel(self)
        self.viewName.setFont(self.font)
        self.viewName.hide()
        self.viewName.mousePressEvent = self.viewName_mousePressEvent

        # Edit presented path textually
        self.line_address = QtWidgets.QLineEdit(self)
        self.line_address.setFrame(False)
        self.line_address.keyPressEvent_super = self.line_address.keyPressEvent
        self.line_address.keyPressEvent = self.line_address_keyPressEvent
        self.line_address.focusOutEvent = self.line_address_focusOutEvent
        self.line_address.contextMenuEvent_super = self.line_address.contextMenuEvent
        self.line_address.contextMenuEvent = self.line_address_contextMenuEvent
        self.line_address.setFont(self.font)
        self.line_address.hide()

        layout.addWidget(self.viewName)
        layout.addWidget(self.line_address)
        # Add QCompleter to address line
        completer = self.init_completer(self.line_address, self.fs_model)
        completer.activated.connect(self.set_path)

        # Container for `btn_crumbs_hidden`, `crumbs_panel`, `switch_space`
        self.crumbs_container = QtWidgets.QWidget(self)
        crumbs_cont_layout = QtWidgets.QHBoxLayout(self.crumbs_container)
        crumbs_cont_layout.setContentsMargins(0, 0, 0, 0)
        crumbs_cont_layout.setSpacing(0)

        layout.addWidget(self.crumbs_container)

        # Hidden breadcrumbs menu button
        self.btn_crumbs_hidden = QtWidgets.QToolButton(self)
        self.btn_crumbs_hidden.setAutoRaise(True)
        self.btn_crumbs_hidden.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.btn_crumbs_hidden.setArrowType(Qt.LeftArrow)
        self.btn_crumbs_hidden.setStyleSheet("QToolButton::menu-indicator {image: none;}")
        self.btn_crumbs_hidden.setMinimumSize(self.btn_crumbs_hidden.minimumSizeHint())
        self.btn_crumbs_hidden.hide()

        crumbs_cont_layout.addWidget(self.btn_crumbs_hidden)
        menu = QtWidgets.QMenu(self.btn_crumbs_hidden)  # FIXME:
        menu.aboutToShow.connect(self._hidden_crumbs_menu_show)
        menu.setFont(self.font)
        self.btn_crumbs_hidden.setMenu(menu)

        # Container for breadcrumbs
        self.crumbs_panel = QtWidgets.QWidget(self)
        crumbs_layout = LeftHBoxLayout(self.crumbs_panel)
        crumbs_layout.widget_state_changed.connect(self.crumb_hide_show)
        crumbs_layout.setContentsMargins(0, 0, 0, 0)
        crumbs_layout.setSpacing(0)
        crumbs_cont_layout.addWidget(self.crumbs_panel)

        # Clicking on empty space to the right puts the bar into edit mode
        self.switch_space = QtWidgets.QWidget(self)
        # s_policy = self.switch_space.sizePolicy()
        # s_policy.setHorizontalStretch(1)
        # self.switch_space.setSizePolicy(s_policy)
        self.switch_space.mouseReleaseEvent = self.switch_space_mouse_up
        # crumbs_cont_layout.addWidget(self.switch_space)
        crumbs_layout.set_space_widget(self.switch_space)

        self.btn_browse = QtWidgets.QToolButton(self)
        self.btn_browse.setAutoRaise(True)
        self.btn_browse.setIcon(buildIcon("pktk:folder_open_dots"))
        self.btn_browse.setToolTip(i18n("Browse for folder"))
        self.btn_browse.clicked.connect(self._browse_for_folder)
        self.btn_browse.clicked.connect(self.__clicked)
        sp = self.btn_browse.sizePolicy()
        sp.setVerticalPolicy(sp.Minimum)
        self.btn_browse.setSizePolicy(sp)
        layout.addWidget(self.btn_browse)

        # Grum999: remove setMaximumHeight(), consider that sizePolicy of parent will define height
        # self.setMaximumHeight(self.line_address.height())  # FIXME:

        self.ignore_resize = False
        self.path_ = None
        self.set_path(Path())

    @staticmethod
    def init_completer(edit_widget, model):
        "Init QCompleter to work with filesystem"
        completer = QtWidgets.QCompleter(edit_widget)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setModel(model)
        # Optimize performance https://stackoverflow.com/a/33454284/1119602
        popup = completer.popup()
        popup.setUniformItemSizes(True)
        popup.setLayoutMode(QtWidgets.QListView.Batched)
        edit_widget.setCompleter(completer)
        edit_widget.textEdited.connect(model.setPathPrefixTextEdited)
        return completer

    def get_icon(self, path: (str, Path)):
        "Path -> QIcon"
        if isinstance(path, str) and not re.match('^@', path) is None:
            # maybe a saved view or a bookmark
            path = path.lower()
            refDict = self.quickRefDict()

            if path not in refDict:
                # unable to find icon reference, return none
                dat = QIcon()
            else:
                dat = refDict[path][1]
        else:
            if isinstance(path, str):
                if r := re.search(r"(?:^([A-Z]:)$|\(([A-Z]:)\)$)", path, re.I):
                    if not r.groups()[0] is None:
                        path = r.groups()[0]
                    else:
                        path = r.groups()[1]

            fileinfo = QtCore.QFileInfo(f"{path}")
            dat = self.file_ico_prov.icon(fileinfo)
            currentSize = dat.actualSize(self.__iconSize, QIcon.Normal, QIcon.Off)
            if fileinfo.isHidden():
                pmap = QtGui.QPixmap(currentSize)
                pmap.fill(Qt.transparent)
                painter = QtGui.QPainter(pmap)
                painter.setOpacity(0.5)
                dat.paint(painter, 0, 0, currentSize.width(), currentSize.height())
                painter.end()
                dat = QtGui.QIcon(pmap)
        return dat

    def line_address_contextMenuEvent(self, event):
        self.line_address_context_menu_flag = True
        self.line_address.contextMenuEvent_super(event)

    def line_address_focusOutEvent(self, event):
        if getattr(self, 'line_address_context_menu_flag', False):
            self.line_address_context_menu_flag = False
            return  # do not cancel edit on context menu
        self._cancel_edit()

    def _hidden_crumbs_menu_show(self):
        "SLOT: fill menu with hidden breadcrumbs list"
        menu = self.sender()
        menu.clear()
        # hid_count = self.crumbs_panel.layout().count_hidden()
        for i in reversed(list(self.crumbs_panel.layout().widgets('hidden'))):
            action = menu.addAction(self.get_icon(i.path), i.text())
            action.path = i.path
            action.triggered.connect(self.set_path)

    def _browse_for_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, i18n("Choose folder"), f"{self.path()}")
        if path:
            self.set_path(path)

    def viewName_mousePressEvent(self, event):
        """Mouse pressed viewName label: go to edit mode"""
        self._edit_path()

    def line_address_keyPressEvent(self, event):
        "Actions to take after a key press in text address field"
        if event.key() == Qt.Key_Escape:
            self._cancel_edit()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.set_path(self.line_address.text())
            self._show_address_field(False)
        # elif event.text() == os.path.sep:  # FIXME: separator cannot be pasted
        #     print('fill completer data here')
        #     paths = [f"{i}" for i in
        #              Path(self.line_address.text()).iterdir() if i.is_dir()]
        #     self.completer.model().setStringList(paths)
        else:
            self.line_address.keyPressEvent_super(event)

    def _clear_crumbs(self):
        layout = self.crumbs_panel.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                layout.removeWidget(child.widget())
                # child.widget().deleteLater()
                # child.widget().setParent(None)

    def _insert_crumb(self, path):
        btn = QtWidgets.QToolButton(self.crumbs_panel)
        btn.setAutoRaise(True)
        btn.setStyleSheet("QToolButton {padding: 0;}")

        if path == '::':
            # for windows, list drives
            hasSubDir = True
            btn.setIcon(buildIcon('pktk:computer_monitor'))
            btn.setToolTip(i18n('This PC'))
        else:
            # last directory?
            hasSubDir = False
            for item in os.listdir(path):
                if os.path.isdir(os.path.join(path, item)):
                    hasSubDir = True
                    break

            # FIXME: C:\ has no name. Use rstrip on Windows only?
            # Grum999: for linux, return '/' for root directory
            if f"{path}" == '/':
                crumb_text = '/'
            else:
                crumb_text = path.name or f"{path}".upper().rstrip(os.path.sep)

            btn.setText(crumb_text)
            btn.setFont(self.font)
        btn.path = path
        if hasSubDir:
            if path == '::':
                btn.setPopupMode(btn.InstantPopup)
            else:
                btn.clicked.connect(self.crumb_clicked)
                btn.setPopupMode(btn.MenuButtonPopup)

            btn.clicked.connect(self.__clicked)
            menu = MenuListView(btn)
            menu.setModel(self.fs_model)
            menu.setFont(self.font)
            menu.aboutToShow.connect(self.crumb_menu_show)
            menu.clicked.connect(self.crumb_menuitem_clicked)
            menu.activated.connect(self.crumb_menuitem_clicked)
            btn.setMenu(menu)
        else:
            btn.clicked.connect(self._edit_path)

        self.crumbs_panel.layout().insertWidget(0, btn)
        btn.setMinimumSize(btn.minimumSizeHint())  # fixed size breadcrumbs

        sp = btn.sizePolicy()
        sp.setVerticalPolicy(sp.Minimum)
        btn.setSizePolicy(sp)
        # print(self._check_space_width(btn.minimumWidth()))
        # print(btn.size(), btn.sizeHint(), btn.minimumSizeHint())

    def crumb_menuitem_clicked(self, index):
        "SLOT: breadcrumb menu item was clicked"
        # print("crumb_clicked",  index.data(Qt.EditRole))
        if r := re.search(r"(?:^([A-Z]:)$|\(([A-Z]:)\)$)", index.data(Qt.EditRole), re.I):
            if not r.groups()[0] is None:
                path = r.groups()[0]
            else:
                path = r.groups()[1]
            self.set_path(path)
        else:
            self.set_path(index.data(Qt.EditRole))

        self.__clicked()

    def crumb_clicked(self):
        "SLOT: breadcrumb was clicked"
        self.set_path(self.sender().path)

    def crumb_menu_show(self):
        "SLOT: fill subdirectory list on menu open"
        menu = self.sender()
        self.fs_model.setPathPrefix(f"{menu.parent().path}{os.path.sep}")

    def set_path(self, path=None, force=False):
        """
        Set path displayed in this BreadcrumbsAddressBar
        Returns `False` if path does not exist or permission error.
        Can be used as a SLOT: `sender().path` is used if `path` is `None`)

        If `force` is True, force to set path even if path already set with given value (do a "refresh")
        """
        if path is None or path == '':
            try:
                path = f"{self.sender().path}"
            except Exception:
                path = '.'

        if isinstance(path, str) and not re.match('^@', path) is None:
            # maybe a saved view or a bookmark

            # if self.path_ != path:
            # => accept path if already the same, because target link (@home, @bookmark)
            #    or target content (@view, @history) may have changed

            path = path.lower()
            refDict = self.quickRefDict()

            if path not in refDict:
                emit_err = self.path_error
                self._cancel_edit()
                return False

            self.__quickRef = refDict[path]

            # BCWPathBar.QUICKREF_RESERVED_HOME, BCWPathBar.QUICKREF_BOOKMARK
            if self.__quickRef[0] in (0, 1):
                # bookmark
                path = self.getQuickRefPath(path)
                if path is None:
                    emit_err = self.path_error
                    self._cancel_edit()
                    return False

                return self.set_path(path, force)

            self.path_ = path
            self.line_address.setText(path)
            self._show_address_field(False)
            self.view_selected.emit(path)
            return True

        elif force or f"{path}" != f"{self.path_}":
            self.__quickRef = None
            path, emit_err = Path(path), None
            try:  # C: -> C:\, folder\..\folder -> folder
                path = path.resolve()
            except PermissionError:
                emit_err = self.listdir_error
            if not path.exists():
                emit_err = self.path_error
            self._cancel_edit()  # exit edit mode
            if emit_err:  # permission error or path does not exist
                emit_err.emit(path)
                return False
            self._clear_crumbs()
            self.path_ = path
            self.line_address.setText(f"{path}")
            self._insert_crumb(path)
            while path.parent != path:
                path = path.parent
                self._insert_crumb(path)

            if sys.platform == 'win32':
                # windows: add drives list
                self._insert_crumb('::')

            self._show_address_field(False)
            self.path_selected.emit(path)
            return True
        return False

    def _cancel_edit(self):
        "Set edit line text back to current path and switch to view mode"
        self.line_address.setText(f"{self.path()}")  # revert path
        self._show_address_field(False)  # switch back to breadcrumbs view

    def path(self):
        "Get path displayed in this BreadcrumbsAddressBar"
        return self.path_

    def switch_space_mouse_up(self, event):
        "EVENT: switch_space mouse clicked"
        if event.button() != Qt.LeftButton:  # left click only
            return
        self._edit_path()

    def _edit_path(self):
        """Activate the edit path mode"""
        self._show_address_field(True)
        self.__clicked()

    def _show_address_field(self, b_show):
        "Show text address field"
        if b_show:
            # show bread crumbs
            self.crumbs_container.hide()
            self.viewName.hide()

            self.line_address.show()
            self.line_address.setFocus()
            self.line_address.selectAll()
        else:
            # show reference
            self.line_address.hide()
            if isinstance(self.path_, str) and self.path_ != '' and self.path_[0] == '@' and self.__quickRef is not None:
                if self.__quickRef[0] == 0:
                    # reserved
                    self.viewName.setText(i18n(f"List view <b><i>{self.__quickRef[2]}</i></b>"))
                else:
                    # list view
                    self.viewName.setText(i18n(f"View <b><i>{self.__quickRef[2]}</i></b>"))

                self.crumbs_container.hide()
                self.viewName.show()
            else:
                self.viewName.hide()
                self.crumbs_container.show()

    def crumb_hide_show(self, widget, state: bool):
        "SLOT: a breadcrumb is hidden/removed or shown"
        layout = self.crumbs_panel.layout()
        if layout.count_hidden() > 0:
            self.btn_crumbs_hidden.show()
        else:
            self.btn_crumbs_hidden.hide()

    def minimumSizeHint(self):
        # print(self.layout().minimumSize().width())
        return QtCore.QSize(150, self.line_address.height())

    def __clicked(self):
        self.clicked.emit(False)

    def isHighlighted(self):
        """Return True is is highlighted, otherwise False"""
        return self.__isHighlighted

    def setHighlighted(self, value):
        """Set current highlighted status"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
        else:
            # if self.__isHighlighted != value:
            self.__isHighlighted = value

            if self.__isHighlighted:
                self.setPalette(self.__paletteHighlighted)
            else:
                self.setPalette(self.__paletteBase)

    def hiddenPath(self):
        """Return if hidden path are displayed or not"""
        return self.__hiddenPath

    def setHiddenPath(self, value=False):
        """Set if hidden path are displayed or not"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")

        self.__hiddenPath = value
        self.fs_model.setHiddenPath(value)

    def quickRefDict(self):
        """Return a dictionnary of quick reference

        key = @xxxx (view Id or Bookmark Id)
        value =(type of reference, Icon, Reference)
        """
        return {}

    def getQuickRefPath(self, refId):
        """Return path from reserved value or bookmark reference

        Return None if not found
        """
        return None

    def updatePalette(self, palette=None):
        """Refresh current palette"""
        if not isinstance(palette, QPalette):
            palette = QApplication.palette()

        self.__paletteBase = QPalette(palette)
        self.__paletteBase.setColor(QPalette.Window, self.__paletteBase.color(QPalette.Base))

        self.__paletteHighlighted = QPalette(palette)
        self.__paletteHighlighted.setColor(QPalette.Window, self.__paletteHighlighted.color(QPalette.Highlight))


if __name__ == '__main__':
    from qtapp import QtForm

    class Form(QtWidgets.QDialog):
        _layout_ = QtWidgets.QHBoxLayout
        _loop_ = True

        def perm_err(self, path):
            print('perm err', path)

        def path_err(self, path):
            print('path err', path)

        def b_clicked(self):
            pass

        def __init__(self):  # pylint: disable=super-init-not-called
            self.address = BreadcrumbsAddressBar()
            # self.b = QtWidgets.QPushButton("test_button_long_text", self)
            # self.b.setFixedWidth(200)
            # self.layout().addWidget(self.b)
            self.layout().addWidget(self.address)
            self.address.listdir_error.connect(self.perm_err)
            self.address.path_error.connect(self.path_err)
            # self.address.set_path(r"C:\Windows\System32\drivers\etc")
            # print(self.b.width())
            # self.b.hide()
            # QtCore.QTimer.singleShot(0, lambda: print(self.b.width()))
            # def act():
            #     for i in self.address.crumbs_panel.layout().widgets('hidden'):
            #         print(i.text())
            # self.b.clicked.connect(act)

    QtForm(Form)
