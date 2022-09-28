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

import os.path
import sys
import re
from pathlib import Path
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import (
        QDir,
        Qt
    )


if sys.platform == 'win32':
    # for windows, implement fcuntion to get drive name
    import ctypes

    kernel32 = ctypes.windll.kernel32

    def getVolumeName(drive):
        """given `drive' is like 'c:\\'"""
        volumeNameBuffer = ctypes.create_unicode_buffer(1024)
        fileSystemNameBuffer = ctypes.create_unicode_buffer(1024)
        serial_number = None
        max_component_length = None
        file_system_flags = None

        rc = kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive),
            volumeNameBuffer,
            ctypes.sizeof(volumeNameBuffer),
            serial_number,
            max_component_length,
            file_system_flags,
            fileSystemNameBuffer,
            ctypes.sizeof(fileSystemNameBuffer)
        )
        return volumeNameBuffer.value

    def getVolumeType(drive):
        rc = kernel32.GetDriveTypeA(
            ctypes.c_wchar_p(drive),
        )
        if rc == 0:
            # DRIVE_UNKNOWN
            return ''
        elif rc == 1:
            # DRIVE_NO_ROOT_DIR
            return ''
        elif rc == 2:
            # DRIVE_REMOVABLE
            return i18n('Removable drive')
        elif rc == 3:
            # DRIVE_FIXED
            return i18n('Local drive')
        elif rc == 4:
            # DRIVE_REMOTE
            return i18n('Network drive')
        elif rc == 5:
            # DRIVE_CDROM
            return i18n('CD-ROM drive')
        elif rc == 6:
            # DRIVE_RAMDISK
            return i18n('RAM Disk drive')
        else:
            return ''

else:
    # for other os method return an empty value
    def getVolumeName(drive):
        return ''

    def getVolumeType(drive):
        return ''


class FilenameModel(QtCore.QStringListModel):
    """
    Model used by QCompleter for file name completions.
    Constructor options:
    `filter_` (None, 'dirs') - include all entries or folders only
    `fs_engine` ('qt', 'pathlib') - enumerate files using `QDir` or `pathlib`
    `icon_provider` (func, 'internal', None) - a function which gets path
                                               and returns QIcon
    """
    def __init__(self, filter_=None, fs_engine='qt', icon_provider='internal', breadcrumbs=None):
        super().__init__()
        self.icon_provider = self.get_icon
        self.icons = QtWidgets.QFileIconProvider()

        self.current_path = ''
        self.fs_engine = fs_engine
        self.filter = filter_
        self.__hiddenPath = 0
        self.__breadcrumbs = breadcrumbs
        if icon_provider != 'internal':
            self.icon_provider = icon_provider

    def data(self, index, role):
        "Get names/icons of files"

        default = super().data(index, role)
        if role == Qt.DecorationRole and self.icon_provider:
            # self.setData(index, dat, role)
            return self.icon_provider(super().data(index, Qt.DisplayRole))
        elif role == Qt.DisplayRole:
            if r := re.search(r"(?:^([A-Z]:)$|\(([A-Z]:)\)$)", default, re.I):
                return default
            return Path(default).name

        return default

    def get_icon(self, path):
        "Internal icon provider"
        return self.icons.icon(QtCore.QFileInfo(path))

    def get_file_list(self, path):
        "List entries in `path` directory"
        lst = None
        if self.fs_engine == 'pathlib':
            lst = self.sort_paths([i for i in path.iterdir()
                                   if self.filter != 'dirs' or i.is_dir()])
        elif self.fs_engine == 'qt':
            qdir = QtCore.QDir(f"{path}")
            qdir.setFilter(qdir.NoDotAndDotDot |
                           self.__hiddenPath |
                           (qdir.Dirs if self.filter == 'dirs' else qdir.AllEntries))

            names = qdir.entryList(sort=QtCore.QDir.DirsFirst |
                                   QtCore.QDir.LocaleAware)
            lst = [f"{path / i}" for i in names]
        return lst

    @staticmethod
    def sort_paths(paths):
        "Windows-Explorer-like filename sorting (for 'pathlib' engine)"
        dirs, files = [], []
        for i in paths:
            if i.is_dir():
                dirs.append(f"{i}")
            else:
                files.append(f"{i}")
        return sorted(dirs, key=str.lower) + sorted(files, key=str.lower)

    def setPathPrefix(self, prefix, bname=''):
        if len(prefix) > 0 and prefix[0] == '@':
            # return a list of quick references
            if self.__breadcrumbs is None:
                quickRefDict = []
            else:
                quickRefDict = self.__breadcrumbs.quickRefDict()

            self.setStringList([key for key in quickRefDict])

            self.current_path = prefix
        if prefix == f'::{os.path.sep}':
            # windows drives
            drvList = []
            for drv in QDir().drives():
                volumeName = getVolumeName(drv.absoluteFilePath()).strip()

                if volumeName != '':
                    volumeName = f"{volumeName} ({drv.absoluteFilePath().replace('/', '')})"
                else:
                    volumeName = drv.absoluteFilePath().replace('/', '')

                # else:
                #    volumeType = getVolumeType(drv.absoluteFilePath())
                #    if volumeType != '':
                #        volumeName = f" [{volumeType}]"
                #    else:
                #        volumeName = f" [{i18n('No label')}]"

                drvList.append(volumeName)

            self.setStringList(drvList)
            self.current_path = prefix
        else:
            path = Path(prefix)

            if not (prefix.endswith(os.path.sep) or bname == '.'):
                path = path.parent

            if os.path.join(f"{path}", bname) == self.current_path:
                return  # already listed

            if not path.exists():
                return  # wrong path
            self.setStringList(self.get_file_list(path))
            self.current_path = os.path.join(f"{path}", bname)

    def setPathPrefixTextEdited(self, prefix):
        if len(prefix) > 0 and prefix[0] == '@':
            bname = ''
        else:
            bname = os.path.basename(prefix)

        if len(bname) > 0 and bname[0] == '.':
            lHiddenPath = self.__hiddenPath
            self.__hiddenPath = QDir.Hidden
            self.setPathPrefix(prefix, '.')
            self.__hiddenPath = lHiddenPath
        else:
            self.setPathPrefix(prefix)

    def hiddenPath(self):
        """Return if hidden path are returned or not"""
        return (self.__hiddenPath == QDir.Hidden)

    def setHiddenPath(self, value):
        """Define if hidden path are returned or not"""
        if value != self.hiddenPath():
            self.current_path = ''
            if value is True:
                self.__hiddenPath = QDir.Hidden
            else:
                self.__hiddenPath = 0


class MenuListView(QtWidgets.QMenu):
    """
    QMenu with QListView.
    Supports `activated`, `clicked`, `setModel`.
    """
    max_visible_items = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self.listview = lv = QtWidgets.QListView()
        lv.setFrameShape(lv.NoFrame)
        lv.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pal = lv.palette()
        pal.setColor(pal.Base, self.palette().color(pal.Window))
        lv.setPalette(pal)

        act_wgt = QtWidgets.QWidgetAction(self)
        act_wgt.setDefaultWidget(lv)
        self.addAction(act_wgt)

        self.activated = lv.activated
        self.clicked = lv.clicked
        self.setModel = lv.setModel

        lv.setIconSize(QtCore.QSize(32, 32))

        fnt = lv.font()
        fnt.setFamily('DejaVu Sans Mono, Consolas, Courier New')
        lv.setFont(fnt)

        lv.sizeHint = self.size_hint
        lv.minimumSizeHint = self.size_hint
        lv.mousePressEvent = lambda event: None  # skip
        lv.mouseMoveEvent = self.mouse_move_event
        lv.setMouseTracking(True)  # receive mouse move events
        lv.leaveEvent = self.mouse_leave_event
        lv.mouseReleaseEvent = self.mouse_release_event
        lv.keyPressEvent = self.key_press_event
        lv.setFocusPolicy(Qt.NoFocus)  # no focus rect
        lv.setFocus()

        self.last_index = QtCore.QModelIndex()  # selected index

    def key_press_event(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self.last_index.isValid():
                self.activated.emit(self.last_index)
            self.close()
        elif key == Qt.Key_Escape:
            self.close()
        elif key in (Qt.Key_Down, Qt.Key_Up):
            model = self.listview.model()
            row_from, row_to = 0, model.rowCount()-1
            if key == Qt.Key_Down:
                row_from, row_to = row_to, row_from
            if not self.last_index or self.last_index.row() == row_from:
                index = model.index(row_to, 0)
            else:
                shift = 1 if key == Qt.Key_Down else -1
                index = model.index(self.last_index.row()+shift, 0)
            self.listview.setCurrentIndex(index)
            self.last_index = index

    def mouse_move_event(self, event):
        self.listview.clearSelection()
        self.last_index = self.listview.indexAt(event.pos())

    def mouse_leave_event(self, event):
        self.listview.clearSelection()
        self.last_index = QtCore.QModelIndex()

    def mouse_release_event(self, event):
        "When item is clicked w/ left mouse button close menu, emit `clicked`"
        if event.button() == Qt.LeftButton:
            if self.last_index.isValid():
                self.clicked.emit(self.last_index)
            try:
                self.close()
            except Exception as e:
                pass

    def size_hint(self):
        lv = self.listview
        width = lv.sizeHintForColumn(0)
        width += lv.verticalScrollBar().sizeHint().width()
        if isinstance(self.parent(), QtWidgets.QToolButton):
            width = max(width, self.parent().width())
        visible_rows = min(self.max_visible_items, lv.model().rowCount())
        return QtCore.QSize(width, visible_rows * lv.sizeHintForRow(0))
