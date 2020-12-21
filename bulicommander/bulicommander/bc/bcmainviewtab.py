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
#from .pktk import PkTk

from enum import Enum
from math import floor

import krita
import os
import re
import shutil
import sys
import time
import random

import PyQt5.uic


from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QFileSystemWatcher,
        QItemSelectionModel,
        QRunnable,
        QSize,
        QSortFilterProxyModel,
        QThreadPool
    )
from PyQt5.QtGui import (
        QFontDatabase,
        QImage,
        QMovie,
        QPixmap
    )
from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QFrame,
        QGraphicsView,
        QHBoxLayout,
        QLabel,
        QListView,
        QListWidget,
        QListWidgetItem,
        QMenu,
        QMessageBox,
        QTreeView,
        QWidget
    )


from .bcwmenuitem import (
        BCWMenuSlider,
        BCWMenuTitle
    )
from .bcbookmark import BCBookmark
from .bcclipboard import (
        BCClipboard,
        BCClipboardModel,
        BCClipboardDelegate,
        BCClipboardItemUrl
    )
from .bcfile import (
        BCBaseFile,
        BCDirectory,
        BCFile,
        BCFileList,
        BCFileListRule,
        BCFileListSortRule,
        BCFileManagedFormat,
        BCFileProperty,
        BCFileThumbnailSize,
        BCMissingFile
    )
from .bchistory import BCHistory
from .bcwpathbar import BCWPathBar
from .bcsettings import (
        BCSettingsKey,
        BCSettingsValues
    )
from .bcworkers import (
        BCWorkerPool
    )
from .bctable import (
        BCTable,
        BCTableSettingsText
    )
from .bcutils import (
        Debug,
        bytesSizeToStr,
        frToStrTime,
        getLangValue,
        secToStrTime,
        strDefault,
        tsToStr,
        stripTags,
        loadXmlUi
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )


# -----------------------------------------------------------------------------
class BCMainViewTabFilesLayout(Enum):
    FULL = 'full'
    TOP = 'top'
    LEFT = 'left'
    BOTTOM = 'bottom'
    RIGHT = 'right'

    def next(self):
        """Return next layout, if already to last layout, loop to first layout"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) + 1
        if index >= len(members):
            index = 0
        return members[index]

    def prev(self):
        """Return previous layout, if already to first layout, loop to last layout"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) - 1
        if index < 0:
            index = len(members) - 1
        return members[index]

class BCMainViewTabClipboardLayout(Enum):
    TOP = 'top'
    LEFT = 'left'
    BOTTOM = 'bottom'
    RIGHT = 'right'

    def next(self):
        """Return next layout, if already to last layout, loop to first layout"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) + 1
        if index >= len(members):
            index = 0
        return members[index]

    def prev(self):
        """Return previous layout, if already to first layout, loop to last layout"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) - 1
        if index < 0:
            index = len(members) - 1
        return members[index]

class BCMainViewTabFilesTabs(Enum):
    INFORMATIONS = 'info'
    DIRECTORIES_TREE = 'dirtree'

class BCMainViewTabFilesNfoTabs(Enum):
    GENERIC = 'generic'
    IMAGE = 'image'
    KRA = 'kra'

class BCMainViewTabTabs(Enum):
    FILES = 'files'
    DOCUMENTS = 'documents'
    CLIPBOARD = 'clipboard'

class BCIconSizes(object):
    def __init__(self, values, currentIndex=0):
        if not (isinstance(values, list) or isinstance(values, tuple)):
            raise EInvalidType('Given `values` must be a <list>')
        self.__values=[value for value in values if isinstance(value, int)]

        if len(self.__values) == 0:
            raise EInvalidValue('Given `values` must be a non empty list of <int>')

        self.__index = 0

        self.setIndex(currentIndex)

    def __repr__(self):
        return f"<BCIconSizes({self.__index}, {self.__values[self.__index]})>"

    def next(self):
        """Go to next value

        return True if current index has been modified, otherwise false
        """
        if self.__index < len(self.__values) - 1:
            self.__index+=1
            return True
        return False

    def prev(self):
        """Go to previous value

        return True if current index has been modified, otherwise false
        """
        if self.__index > 0:
            self.__index-=1
            return True
        return False

    def index(self):
        """Return current index"""
        return self.__index

    def setIndex(self, index):
        """Set current index

        return True if current index has been modified, otherwise false
        """
        if index == self.__index:
            return False
        if not isinstance(index, int):
            raise EInvalidType('Given `values` must be a <int>')

        if index < 0:
            self.__index = 0
        elif index > len(self.__values) - 1:
            self.__index = len(self.__values) - 1
        else:
            self.__index = index

        return True

    def value(self):
        """Return current value"""
        return self.__values[self.__index]

    def setValue(self, value):
        """Set current value

        If value doesn't exist in list of values, return the first value less than current

        return True if current index has been modified, otherwise false
        """
        currentIndex = self.__index
        if value in self.__values:
            self.__index = self.__values.indexOf(value)
        else:
            self.__index=0
            for v in self.__values:
                if v < value:
                    self.__index+=1
                else:
                    break
        if currentIndex == self.__index:
            return False
        return True


# -----------------------------------------------------------------------------
# create a model from abstract model
# use it for QListView and QTreeView
# -- https://doc.qt.io/qt-5/modelview.html

class BCMainViewFiles(QTreeView):
    """Tree view files"""
    focused = Signal()
    iconStartLoad = Signal(int)
    iconProcessed = Signal()
    iconStopLoad = Signal()

    COLNUM_ICON = 0
    COLNUM_PATH = 1
    COLNUM_NAME = 2
    COLNUM_TYPE = 3
    COLNUM_SIZE = 4
    COLNUM_DATE = 5
    COLNUM_WIDTH = 6
    COLNUM_HEIGHT = 7
    COLNUM_FULLNFO = 8
    COLNUM_LAST = 8

    __STATUS_READY = 0
    __STATUS_UPDATING = 1

    USERROLE_FILE = Qt.UserRole + 1

    keyPressed = Signal(int)

    @staticmethod
    def getIcon(itemIndex, file, viewThumbnail=False, size=0):
         if viewThumbnail:
             return file.thumbnail(size=size, thumbType=BCBaseFile.THUMBTYPE_ICON)
         else:
             return file.icon()


    def __init__(self, parent=None):
        super(BCMainViewFiles, self).__init__(parent)
        self.__model = None
        self.__proxyModel = None
        self.__filesFilter = ''
        self.__viewThumbnail = False
        self.__viewNfoRowLimit = 7
        self.__iconSize = BCIconSizes([16, 24, 32, 48, 64, 96, 128, 256, 512])
        self.__status = BCMainViewFiles.__STATUS_READY
        self.__changed = False
        self.__showPath = False

        self.__initHeaders()
        self.__iconPool = BCWorkerPool()
        self.__iconPool.signals.processed.connect(self.__updateIconsProcessed)
        self.__iconPool.signals.finished.connect(self.__updateIconsFinished)

    def __initHeaders(self):
        """Initialise treeview header & model"""
        self.__model = QStandardItemModel(0, self.COLNUM_LAST+1, self)
        self.__model.setHeaderData(self.COLNUM_ICON, Qt.Horizontal, '')
        self.__model.setHeaderData(self.COLNUM_PATH, Qt.Horizontal, i18n("Path"))
        self.__model.setHeaderData(self.COLNUM_NAME, Qt.Horizontal, i18n("Name"))
        self.__model.setHeaderData(self.COLNUM_TYPE, Qt.Horizontal, i18n("Type"))
        self.__model.setHeaderData(self.COLNUM_SIZE, Qt.Horizontal, i18n("Size"))
        self.__model.setHeaderData(self.COLNUM_DATE, Qt.Horizontal, i18n("Date"))
        self.__model.setHeaderData(self.COLNUM_WIDTH, Qt.Horizontal, i18n("Width"))
        self.__model.setHeaderData(self.COLNUM_HEIGHT, Qt.Horizontal, i18n("Height"))
        self.__model.setHeaderData(self.COLNUM_FULLNFO, Qt.Horizontal, i18n("File"))

        self.__proxyModel = QSortFilterProxyModel(self)
        self.__proxyModel.setSourceModel(self.__model)
        self.__proxyModel.setFilterKeyColumn(BCMainViewFiles.COLNUM_NAME)

        self.setModel(self.__proxyModel)

        # set colums size rules
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(self.COLNUM_ICON, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COLNUM_PATH, QHeaderView.Interactive)
        header.setSectionResizeMode(self.COLNUM_NAME, QHeaderView.Interactive)
        header.setSectionResizeMode(self.COLNUM_TYPE, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COLNUM_SIZE, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COLNUM_DATE, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COLNUM_WIDTH, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COLNUM_HEIGHT, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COLNUM_FULLNFO, QHeaderView.Interactive)

        header.setSectionHidden(self.COLNUM_PATH, True)
        header.setSectionHidden(self.COLNUM_FULLNFO, True)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)

    def __updateIconsProcessed(self, processedNfo):
        """update icon in treeview list"""
        fileIndex, icon = processedNfo

        if not fileIndex is None and fileIndex < self.__model.rowCount():
            if not icon is None:
                self.__model.item(fileIndex, BCMainViewFiles.COLNUM_ICON).setIcon(icon)
            else:
                self.__model.item(fileIndex, BCMainViewFiles.COLNUM_ICON).setText('?')

        if self.__model.rowCount() > 100:
            self.iconProcessed.emit()

    def __updateIconsFinished(self):
        """updateing icon in treeview list is terminated"""
        self.__status = BCMainViewFiles.__STATUS_READY
        self.iconStopLoad.emit()

    def __updateIcons(self):
        """Update files icons according to current view mode"""
        if self.__model.rowCount()==0:
            # nothing to update
            return

        self.iconStartLoad.emit(self.__model.rowCount())

        items = [self.__model.item(fileIndex, BCMainViewFiles.COLNUM_NAME).data(BCMainViewFiles.USERROLE_FILE) for fileIndex in range(self.__model.rowCount())]

        if not self.__viewThumbnail:
            self.__iconPool.startProcessing(items, BCMainViewFiles.getIcon, False)
        else:
            size = BCFileThumbnailSize.fromValue(self.iconSize().height())
            self.__iconPool.startProcessing(items, BCMainViewFiles.getIcon, True, size)

    def __stopUpdatingIcons(self):
        """Stop update icons/thumbnail

        All threads are stopped
        """
        self.__status = BCMainViewFiles.__STATUS_READY
        self.__iconPool.stopProcessing()

    def keyPressEvent(self, event):
        super(BCMainViewFiles, self).keyPressEvent(event)
        self.keyPressed.emit(event.key())

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                # Zoom in
                sizeChanged = self.__iconSize.next()
            else:
                # zoom out
                sizeChanged = self.__iconSize.prev()

            if sizeChanged:
                self.setIconSizeIndex()
        else:
            super(BCMainViewFiles, self).wheelEvent(event)

    def focusInEvent(self, event):
        super(BCMainViewFiles, self).focusInEvent(event)
        Debug.print('[BCMainViewFiles.focusInEvent]')
        self.focused.emit()

    def resizeColumns(self, fixedOnly=True):
        """Resize columns to content"""
        if not fixedOnly and self.__model.rowCount() > 1:
            # greater than 1 ==> if only '..' item don't change column width
            self.resizeColumnToContents(self.COLNUM_PATH)
            self.resizeColumnToContents(self.COLNUM_NAME)
        self.resizeColumnToContents(self.COLNUM_ICON)
        self.resizeColumnToContents(self.COLNUM_TYPE)
        self.resizeColumnToContents(self.COLNUM_SIZE)
        self.resizeColumnToContents(self.COLNUM_DATE)
        self.resizeColumnToContents(self.COLNUM_WIDTH)
        self.resizeColumnToContents(self.COLNUM_HEIGHT)
        self.resizeColumnToContents(self.COLNUM_FULLNFO)

    def filterModel(self):
        """Return proxy filter model"""
        return self.__proxyModel

    def addFile(self, fileNfo):
        """Add a file to treeview"""
        if not isinstance(fileNfo, BCBaseFile):
            raise EInvalidType("Given `fileNfo` must be a <BCBaseFile>")

        if not self.__status == BCMainViewFiles.__STATUS_UPDATING:
            raise EInvalidStatus("Current treeview is not in update mode")


        self.__changed = True

        newRow = [
                QStandardItem(''),
                QStandardItem(''),
                QStandardItem(''),
                QStandardItem(''),
                QStandardItem(''),
                QStandardItem(''),
                QStandardItem(''),
                QStandardItem(''),
                QStandardItem('')
            ]

        textFull=''
        if self.__showPath:
            textFull+=f'Path:       {fileNfo.path()}\n'

        textFull+=f'File:       {fileNfo.name()}'

        newRow[self.COLNUM_PATH].setText(fileNfo.path())
        newRow[self.COLNUM_NAME].setText(fileNfo.name())
        newRow[self.COLNUM_NAME].setData(fileNfo, BCMainViewFiles.USERROLE_FILE)

        # always add with icon
        # thumnbail loading (and generate) made asynchronously in a second time
        newRow[self.COLNUM_ICON].setIcon(fileNfo.icon())
        newRow[self.COLNUM_ICON].setTextAlignment(Qt.AlignCenter|Qt.AlignVCenter)

        date=tsToStr(fileNfo.lastModificationDateTime())
        if fileNfo.format() == BCFileManagedFormat.DIRECTORY:
            if fileNfo.name() != '..':
                newRow[self.COLNUM_DATE].setText(date)
                textFull+=f'\nDate:       {date}'
            newRow[self.COLNUM_TYPE].setText(i18n('<DIR>'))
        else:
            date=tsToStr(fileNfo.lastModificationDateTime(), valueNone='-')
            newRow[self.COLNUM_DATE].setText(date)
            newRow[self.COLNUM_DATE].setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            textFull+=f'\nDate:       {date}'

            if fileNfo.extension() != '':
                format = BCFileManagedFormat.translate(fileNfo.extension())
            else:
                format = BCFileManagedFormat.translate(fileNfo.format())

            if isinstance(fileNfo, BCMissingFile):
                size = '-'
            else:
                size = bytesSizeToStr(fileNfo.size())

            newRow[self.COLNUM_SIZE].setText(' '+size)
            newRow[self.COLNUM_SIZE].setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)

            newRow[self.COLNUM_TYPE].setText(format)
            textFull+=f'\nSize:       {size}'
            textFull+=f'\nFormat:     {format}'

            if fileNfo.imageSize().width() > 0 and fileNfo.imageSize().height() > 0:
                newRow[self.COLNUM_WIDTH].setText(str(fileNfo.imageSize().width()))
                newRow[self.COLNUM_HEIGHT].setText(str(fileNfo.imageSize().height()))
                textFull+=f'\nImage size: {fileNfo.imageSize().width()}x{fileNfo.imageSize().height()}'
            else:
                newRow[self.COLNUM_WIDTH].setText('-')
                newRow[self.COLNUM_HEIGHT].setText('-')
                if fileNfo.format() == BCFileManagedFormat.MISSING:
                    textFull+=f'\nImage size: -'
                else:
                    textFull+=f'\nImage size: Unable to retrieve image size'
            newRow[self.COLNUM_WIDTH].setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            newRow[self.COLNUM_HEIGHT].setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)

        newRow[self.COLNUM_FULLNFO].setText(textFull)

        self.__model.appendRow(newRow)

    def clear(self):
        """Clear content"""
        if not self.__status == BCMainViewFiles.__STATUS_UPDATING:
            raise EInvalidStatus("Current treeview is not in update mode")

        self.__model.removeRows(0, self.__model.rowCount())
        self.__changed = True

    def invertSelection(self):
        """Invert current selection"""
        first = self.__proxyModel.index(0, 0)
        last = self.__proxyModel.index(self.__proxyModel.rowCount() - 1, 7)

        self.selectionModel().select(QItemSelection(first, last), QItemSelectionModel.Toggle)

    def files(self):
        """Return a list of files"""
        returned=[]

        #for fileIndex in range(self.__model.rowCount()):
        #    fileNfo = self.__model.item(fileIndex, BCMainViewFiles.COLNUM_NAME).data(BCMainViewFiles.USERROLE_FILE)
        #    if not(fileNfo.name() == '..' and fileNfo.format() == BCFileManagedFormat.DIRECTORY):
        #        returned.append(fileNfo)
        for rowIndex in range(self.__proxyModel.rowCount()):
            fileNfo = self.__proxyModel.index(rowIndex, BCMainViewFiles.COLNUM_NAME).data(BCMainViewFiles.USERROLE_FILE)
            if not(fileNfo.name() == '..' and fileNfo.format() == BCFileManagedFormat.DIRECTORY):
                returned.append(fileNfo)

        return returned

    def selectedFiles(self):
        """Return a list of selected files

        Each returned item is a tuple (row, BCBaseFile)
        """
        returned=[]
        smodel=self.selectionModel().selectedRows(self.COLNUM_NAME)

        for item in smodel:
            fileNfo = item.data(BCMainViewFiles.USERROLE_FILE)
            if not(fileNfo.name() == '..' and fileNfo.format() == BCFileManagedFormat.DIRECTORY):
                returned.append(fileNfo)

        return returned

    def iconSizeIndex(self):
        """Return current icon size index"""
        return self.__iconSize.index()

    def setIconSizeIndex(self, index=None):
        """Set icon size from index value"""
        if index is None or self.__iconSize.setIndex(index):
            # new size defined
            self.setIconSize(QSize(self.__iconSize.value(), self.__iconSize.value()))

            # made asynchronously...
            if self.__viewThumbnail:
                self.__updateIcons()

            header = self.header()
            # ...then cnot possible to determinate column ICON width from content
            # and fix it to icon size
            header.resizeSection(self.COLNUM_ICON, self.__iconSize.value())
            if self.__iconSize.index() >= self.__viewNfoRowLimit:
                header.setSectionHidden(self.COLNUM_PATH, True)
                header.setSectionHidden(self.COLNUM_NAME, True)
                header.setSectionHidden(self.COLNUM_TYPE, True)
                header.setSectionHidden(self.COLNUM_SIZE, True)
                header.setSectionHidden(self.COLNUM_DATE, True)
                header.setSectionHidden(self.COLNUM_WIDTH, True)
                header.setSectionHidden(self.COLNUM_HEIGHT, True)
                header.setSectionHidden(self.COLNUM_FULLNFO, False)
                header.setStretchLastSection(True)
            else:
                header.setStretchLastSection(False)
                header.setSectionHidden(self.COLNUM_PATH, not self.__showPath)
                header.setSectionHidden(self.COLNUM_NAME, False)
                header.setSectionHidden(self.COLNUM_TYPE, False)
                header.setSectionHidden(self.COLNUM_SIZE, False)
                header.setSectionHidden(self.COLNUM_DATE, False)
                header.setSectionHidden(self.COLNUM_WIDTH, False)
                header.setSectionHidden(self.COLNUM_HEIGHT, False)
                header.setSectionHidden(self.COLNUM_FULLNFO, True)
                self.resizeColumns(False)

    def beginUpdate(self):
        """Start to update treeview content

        Execute clear/addFile inside a beginUpdate() / endUpdate()
        """
        self.__stopUpdatingIcons()

        self.__status = BCMainViewFiles.__STATUS_UPDATING

    def endUpdate(self):
        """End update content"""
        if self.__status != BCMainViewFiles.__STATUS_UPDATING:
            # we must be in updating status to en update :)
            return

        self.__status = BCMainViewFiles.__STATUS_READY

        if not self.__changed:
            # nothing has been changed, do nothing
            return

        self.__changed = False
        self.__updateIcons()

    def setFilter(self, filter):
        """Set current filter"""
        if filter == self.__filesFilter:
            # filter unchanged, do nothing
            return

        if filter is None:
            filter = self.__filesFilter

        if not isinstance(filter, str):
            raise EInvalidType('Given `filter` must be a <str>')

        if reFilter:=re.search('^re:(.*)', filter):
            self.__proxyModel.setFilterCaseSensitivity(Qt.CaseSensitive)
            self.__proxyModel.setFilterRegExp(reFilter.groups()[0])
        elif reFilter:=re.search('^re\/i:(.*)', filter):
            self.__proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
            self.__proxyModel.setFilterRegExp(reFilter.groups()[0])
        else:
            #reFilter = re.escape(filter).replace(';', '|')
            self.__proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
            self.__proxyModel.setFilterWildcard(filter)

        self.__filesFilter = filter

    def viewThumbnail(self):
        """Return current view mode (list/icon)"""
        return self.__viewThumbnail

    def setViewThumbnail(self, value):
        """Set current view mode"""
        if value is None or not isinstance(value, bool):
            value = False

        if value == self.__viewThumbnail:
            return

        self.__viewThumbnail = value
        self.__updateIcons()

    def updateFileSizeUnit(self):
        """Update file size unit"""
        # do not use multithreading for this...
        # may need some tests with heavy list but is it really needed?
        for fileIndex in range(self.__model.rowCount()):
            fileNfo = self.__model.item(fileIndex, BCMainViewFiles.COLNUM_NAME).data(BCMainViewFiles.USERROLE_FILE)
            if fileNfo.format() != BCFileManagedFormat.DIRECTORY:
                self.__model.item(fileIndex, BCMainViewFiles.COLNUM_SIZE).setText(' '+bytesSizeToStr(fileNfo.size()))

    def showPath(self):
        """Is path is visible or not"""
        return self.__showPath

    def setShowPath(self, value):
        """Set if path is visible or not"""
        if isinstance(value, bool):
            self.__showPath = value
            self.setIconSizeIndex()
        else:
            raise EInvalidType("Given `value` must be a <bool>")


class BCMainViewClipboard(QTreeView):
    """Tree view clipboard"""
    focused = Signal()

    def __init__(self, parent=None):
        super(BCMainViewClipboard, self).__init__(parent)
        self.__model = None
        self.__proxyModel = None
        self.__iconSize = BCIconSizes([16, 24, 32, 48, 64, 96, 128, 256, 512])
        self.clicked.connect(self.__itemClicked)

    def __itemClicked(self, index):
        """A cell has been clicked, check if it's a persistent column"""
        if index.column()==BCClipboardModel.COLNUM_PERSISTENT:
            item=index.data(BCClipboardModel.ROLE_ITEM)
            if item:
                item.setPersistent(not item.persistent())

    def __resizeColumns(self):
        """Resize columns"""
        self.resizeColumnToContents(BCClipboardModel.COLNUM_ICON)
        self.resizeColumnToContents(BCClipboardModel.COLNUM_PERSISTENT)
        self.resizeColumnToContents(BCClipboardModel.COLNUM_TYPE)
        self.resizeColumnToContents(BCClipboardModel.COLNUM_DATE)
        self.resizeColumnToContents(BCClipboardModel.COLNUM_SIZE)
        self.resizeColumnToContents(BCClipboardModel.COLNUM_URL)
        self.resizeColumnToContents(BCClipboardModel.COLNUM_FULLNFO)

    def setClipboard(self, clipboard):
        """Initialise treeview header & model"""
        self.__model = BCClipboardModel(clipboard)

        self.__proxyModel = QSortFilterProxyModel(self)
        self.__proxyModel.setSourceModel(self.__model)

        self.setModel(self.__proxyModel)

        # set colums size rules
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(BCClipboardModel.COLNUM_ICON, QHeaderView.Fixed)
        header.setSectionResizeMode(BCClipboardModel.COLNUM_PERSISTENT, QHeaderView.Fixed)

        self.__resizeColumns()

        header.setSectionHidden(BCClipboardModel.COLNUM_FULLNFO, True)

        delegate=BCClipboardDelegate(self)
        self.setItemDelegateForColumn(BCClipboardModel.COLNUM_URL, delegate)
        self.setItemDelegateForColumn(BCClipboardModel.COLNUM_PERSISTENT, delegate)

        self.__model.updateWidth.connect(self.__resizeColumns)

    def focusInEvent(self, event):
        super(BCMainViewClipboard, self).focusInEvent(event)
        Debug.print('[BCMainViewClipboard.focusInEvent]')
        self.focused.emit()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                # Zoom in
                sizeChanged = self.__iconSize.next()
            else:
                # zoom out
                sizeChanged = self.__iconSize.prev()

            if sizeChanged:
                self.setIconSizeIndex()
        else:
            super(BCMainViewClipboard, self).wheelEvent(event)

    def iconSizeIndex(self):
        """Return current icon size index"""
        return self.__iconSize.index()

    def setIconSizeIndex(self, index=None):
        """Set icon size from index value"""
        if index is None or self.__iconSize.setIndex(index):
            # new size defined
            self.__model.setIconSize(self.__iconSize.value())
            self.setIconSize(QSize(self.__iconSize.value(), self.__iconSize.value()))

            header = self.header()
            # ...then cnot possible to determinate column ICON width from content
            # and fix it to icon size
            header.resizeSection(BCClipboardModel.COLNUM_ICON, self.__iconSize.value())
            #if self.__iconSize.index() >= self.__viewNfoRowLimit:
            #    header.setSectionHidden(self.COLNUM_PATH, True)
            #    header.setSectionHidden(self.COLNUM_NAME, True)
            #    header.setSectionHidden(self.COLNUM_TYPE, True)
            #    header.setSectionHidden(self.COLNUM_SIZE, True)
            #    header.setSectionHidden(self.COLNUM_DATE, True)
            #    header.setSectionHidden(self.COLNUM_WIDTH, True)
            #    header.setSectionHidden(self.COLNUM_HEIGHT, True)
            #    header.setSectionHidden(self.COLNUM_FULLNFO, False)
            #    header.setStretchLastSection(True)
            #else:
            #    header.setStretchLastSection(False)
            #    header.setSectionHidden(self.COLNUM_PATH, not self.__showPath)
            #    header.setSectionHidden(self.COLNUM_NAME, False)
            #    header.setSectionHidden(self.COLNUM_TYPE, False)
            #    header.setSectionHidden(self.COLNUM_SIZE, False)
            #    header.setSectionHidden(self.COLNUM_DATE, False)
            #    header.setSectionHidden(self.COLNUM_WIDTH, False)
            #    header.setSectionHidden(self.COLNUM_HEIGHT, False)
            #    header.setSectionHidden(self.COLNUM_FULLNFO, True)
            #    self.resizeColumns(False)

    def selectedItems(self):
        """Return a list of selected clipboard items"""
        returned=[]
        if self.selectionModel():
            for item in self.selectionModel().selectedRows(BCClipboardModel.COLNUM_ICON):
                returned.append(item.data(BCClipboardModel.ROLE_ITEM))

        return returned

    def invertSelection(self):
        """Invert current selection"""
        first = self.__proxyModel.index(0, 0)
        last = self.__proxyModel.index(self.__proxyModel.rowCount() - 1, BCClipboardModel.COLNUM_LAST)

        self.selectionModel().select(QItemSelection(first, last), QItemSelectionModel.Toggle)


# -----------------------------------------------------------------------------
class BCMainViewTab(QFrame):
    """Buli Commander main view tab panel (left or right)"""
    highlightedStatusChanged = Signal(QTabWidget)
    tabFilesLayoutChanged = Signal(QTabWidget)
    tabClipboardLayoutChanged = Signal(QTabWidget)
    filesPathChanged = Signal(str)
    filesFilterChanged = Signal(str)

    def __init__(self, parent=None):
        super(BCMainViewTab, self).__init__(parent)

        self.__isHighlighted = False
        self.__uiController = None

        # -- files tab variables --
        self.__filesTabLayout = BCMainViewTabFilesLayout.TOP

        self.__filesAllowRefresh = False
        self.__filesBlockedRefresh = 0

        self.__filesQuery = None
        self.__filesFilter = None

        self.__filesPbMax=0
        self.__filesPbVal=0
        self.__filesPbInc=0
        self.__filesPbDispCount=0
        self.__filesPbVisible=False

        self.__filesCurrentStats = {
                'nbFiles': 0,
                'nbDir': 0,
                'nbTotal': 0,
                'sizeFiles': 0,

                'nbFilteredFiles': 0,
                'nbFilteredDir': 0,
                'nbFilteredTotal': 0,
                'sizeFilteredFiles': 0,

                'nbSelectedFiles': 0,
                'nbSelectedDir': 0,
                'nbSelectedTotal': 0,
                'sizeSelectedFiles': 0,

                'totalDiskSize': 0,
                'usedDiskSize': 0,
                'freeDiskSize': 0
            }

        self.__filesSelected = []
        self.__filesSelectedNbDir = 0
        self.__filesSelectedNbFile = 0
        self.__filesSelectedNbTotal = 0
        self.__filesSelectedNbReadable = 0

        self.__filesCurrentAnimatedFrame = 0
        self.__filesMaxAnimatedFrame = 0
        self.__filesImgReaderAnimated = None

        self.__filesDirTreeModel = QFileSystemModel()

        self.__filesFsWatcher = QFileSystemWatcher()
        self.__filesFsWatcherTmpList = []

        self.__actionFilesApplyTabLayoutFull = QAction(QIcon(":/images/dashboard_full"), i18n('Full mode'), self)
        self.__actionFilesApplyTabLayoutFull.setCheckable(True)
        self.__actionFilesApplyTabLayoutFull.setProperty('layout', BCMainViewTabFilesLayout.FULL)

        self.__actionFilesApplyTabLayoutTop = QAction(QIcon(":/images/dashboard_tb"), i18n('Top/Bottom'), self)
        self.__actionFilesApplyTabLayoutTop.setCheckable(True)
        self.__actionFilesApplyTabLayoutTop.setProperty('layout', BCMainViewTabFilesLayout.TOP)

        self.__actionFilesApplyTabLayoutLeft = QAction(QIcon(":/images/dashboard_lr"), i18n('Left/Right'), self)
        self.__actionFilesApplyTabLayoutLeft.setCheckable(True)
        self.__actionFilesApplyTabLayoutLeft.setProperty('layout', BCMainViewTabFilesLayout.LEFT)

        self.__actionFilesApplyTabLayoutBottom = QAction(QIcon(":/images/dashboard_bt"), i18n('Bottom/Top'), self)
        self.__actionFilesApplyTabLayoutBottom.setCheckable(True)
        self.__actionFilesApplyTabLayoutBottom.setProperty('layout', BCMainViewTabFilesLayout.BOTTOM)

        self.__actionFilesApplyTabLayoutRight = QAction(QIcon(":/images/dashboard_rl"), i18n('Right/Left'), self)
        self.__actionFilesApplyTabLayoutRight.setCheckable(True)
        self.__actionFilesApplyTabLayoutRight.setProperty('layout', BCMainViewTabFilesLayout.RIGHT)

        self.__actionFilesApplyIconSize = BCWMenuSlider(i18n("Icon size"))
        self.__actionFilesApplyIconSize.slider().setMinimum(0)
        self.__actionFilesApplyIconSize.slider().setMaximum(8)
        self.__actionFilesApplyIconSize.slider().setPageStep(1)
        self.__actionFilesApplyIconSize.slider().setSingleStep(1)

        # -- files tab variables --
        self.__clipboardTabLayout = BCMainViewTabClipboardLayout.TOP

        self.__clipboardSelected = []
        self.__clipboardSelectedNbTotal=0
        self.__clipboardSelectedNbUrl=0
        self.__clipboardSelectedNbFiles=0
        self.__clipboardSelectedNbImagesRaster=0
        self.__clipboardSelectedNbImagesSvg=0
        self.__clipboardSelectedNbImagesKraNode=0
        self.__clipboardSelectedNbImagesKraSelection=0
        self.__clipboardSelectedNbUrlDownloaded=0
        self.__clipboardSelectedNbUrlDownloading=0
        self.__clipboardSelectedNbUrlNotDownloaded=0


        self.__actionClipboardApplyTabLayoutTop = QAction(QIcon(":/images/dashboard_tb"), i18n('Top/Bottom'), self)
        self.__actionClipboardApplyTabLayoutTop.setCheckable(True)
        self.__actionClipboardApplyTabLayoutTop.setProperty('layout', BCMainViewTabClipboardLayout.TOP)

        self.__actionClipboardApplyTabLayoutLeft = QAction(QIcon(":/images/dashboard_lr"), i18n('Left/Right'), self)
        self.__actionClipboardApplyTabLayoutLeft.setCheckable(True)
        self.__actionClipboardApplyTabLayoutLeft.setProperty('layout', BCMainViewTabClipboardLayout.LEFT)

        self.__actionClipboardApplyTabLayoutBottom = QAction(QIcon(":/images/dashboard_bt"), i18n('Bottom/Top'), self)
        self.__actionClipboardApplyTabLayoutBottom.setCheckable(True)
        self.__actionClipboardApplyTabLayoutBottom.setProperty('layout', BCMainViewTabClipboardLayout.BOTTOM)

        self.__actionClipboardApplyTabLayoutRight = QAction(QIcon(":/images/dashboard_rl"), i18n('Right/Left'), self)
        self.__actionClipboardApplyTabLayoutRight.setCheckable(True)
        self.__actionClipboardApplyTabLayoutRight.setProperty('layout', BCMainViewTabClipboardLayout.RIGHT)

        self.__actionClipboardApplyIconSize = BCWMenuSlider(i18n("Icon size"))
        self.__actionClipboardApplyIconSize.slider().setMinimum(0)
        self.__actionClipboardApplyIconSize.slider().setMaximum(8)
        self.__actionClipboardApplyIconSize.slider().setPageStep(1)
        self.__actionClipboardApplyIconSize.slider().setSingleStep(1)


        # -----
        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcmainviewtab.ui')
        loadXmlUi(uiFileName, self)

        if sys.platform != 'linux':
            self.linePerm.setVisible(False)
            self.labelPerm.setVisible(False)
            self.lblPerm.setVisible(False)
            self.labelOwner.setVisible(False)
            self.lblOwner.setVisible(False)
        else:
            self.lblPerm.setText('-')
            self.lblOwner.setText('-')

        self.__filesSelectionChanged(None)
        self.__clipboardSelectionChanged(None)

        self.__initialise()


    def __initialise(self):
        @pyqtSlot('QString')
        def filesTabLayoutModel_Clicked(value):
            self.setFilesTabLayout(value.property('layout'))

        @pyqtSlot('QString')
        def clipboardTabLayoutModel_Clicked(value):
            self.setClipboardTabLayout(value.property('layout'))

        @pyqtSlot('QString')
        def filesTabLayoutReset_Clicked(value):
            self.setFilesTabLayout(BCMainViewTabFilesLayout.TOP)

        @pyqtSlot('QString')
        def clipboardTabLayoutReset_Clicked(value):
            self.setClipboardTabLayout(BCMainViewTabClipboardLayout.TOP)

        @pyqtSlot('QString')
        def children_Clicked(value=None):
            Debug.print('[BCMainViewTab.children_Clicked] value: {0} | path: {1}', value, self.filesPath())
            self.setHighlighted(True)

            if not self.__uiController is None:
                self.__uiController.updateMenuForPanel()

        @pyqtSlot('QString')
        def filesPath_Changed(value):
            def expand(item):
                self.tvDirectoryTree.setCurrentIndex(item)
                while item != self.tvDirectoryTree.rootIndex():
                    self.tvDirectoryTree.expand(item)
                    item=item.parent()

            self.__filesFsWatcherTmpList=self.__filesFsWatcher.directories()
            if len(self.__filesFsWatcherTmpList) > 0:
                self.__filesFsWatcher.removePaths(self.__filesFsWatcherTmpList)
            expand(self.__filesDirTreeModel.index(self.filesPath()))

            self.refresh()
            self.__filesFsWatcher.addPath(self.filesPath())
            self.__filesFsWatcherTmpList=self.__filesFsWatcher.directories()
            self.filesPathChanged.emit(value)

        @pyqtSlot('QString')
        def filesView_Changed(value):
            self.__filesFsWatcherTmpList=self.__filesFsWatcher.directories()
            if len(self.__filesFsWatcherTmpList) > 0:
                self.__filesFsWatcher.removePaths(self.__filesFsWatcherTmpList)
                self.__filesFsWatcherTmpList=self.__filesFsWatcher.directories()

            self.refresh()
            self.filesPathChanged.emit(value)

        @pyqtSlot('QString')
        def filesTvSelectedPath_changed(value):
            self.setFilesPath(self.__filesDirTreeModel.filePath(self.tvDirectoryTree.currentIndex()))

        @pyqtSlot('QString')
        def filesTvSelectedPath_expandedCollapsed(value):
            self.tvDirectoryTree.resizeColumnToContents(0)

        @pyqtSlot('QString')
        def filesFilter_Changed(value):
            self.refreshFilter(value)
            self.filesFilterChanged.emit(value)

        @pyqtSlot('QString')
        def filesPreview_ZoomChanged(value):
            self.lblFilesPreviewZoom.setText(f"View at {value:.2f}%")

        @pyqtSlot('QString')
        def clipboardPreview_ZoomChanged(value):
            self.lblClipboardPreviewZoom.setText(f"View at {value:.2f}%")

        @pyqtSlot('QString')
        def filesFilterVisibility_Changed(value):
            if value:
                self.__filesApplyFilter(self.filesFilter())
            else:
                self.__filesApplyFilter('')

        @pyqtSlot('QString')
        def filesDirectory_changed(value):
            self.refresh()

        @pyqtSlot('QString')
        def filesIconSize_changed(value):
            self.treeViewFiles.setIconSizeIndex(value)

        @pyqtSlot('QString')
        def clipboardIconSize_changed(value):
            self.treeViewClipboard.setIconSizeIndex(value)

        @pyqtSlot('QString')
        def filesIconSize_update():
            self.__actionFilesApplyIconSize.slider().setValue(self.treeViewFiles.iconSizeIndex())

        @pyqtSlot('QString')
        def clipboardIconSize_update():
            self.__actionClipboardApplyIconSize.slider().setValue(self.treeViewClipboard.iconSizeIndex())

        @pyqtSlot(int)
        def treeViewFiles_iconStartLoad(nbIcons):
            self.__filesProgressStart(nbIcons, i18n('Loading thumbnails %v of %m (%p%)'))

        @pyqtSlot()
        def treeViewFiles_iconStopLoad():
            self.__filesProgressStop()

        @pyqtSlot()
        def treeViewFiles_iconProcessed():
            self.__filesProgressSetNext()

        # -- files --

        # hide progress bar
        self.__filesProgressStop()

        self.__filesFsWatcher.directoryChanged.connect(filesDirectory_changed)

        self.__actionFilesApplyTabLayoutFull.triggered.connect(children_Clicked)
        self.__actionFilesApplyTabLayoutTop.triggered.connect(children_Clicked)
        self.__actionFilesApplyTabLayoutLeft.triggered.connect(children_Clicked)
        self.__actionFilesApplyTabLayoutBottom.triggered.connect(children_Clicked)
        self.__actionFilesApplyTabLayoutRight.triggered.connect(children_Clicked)
        self.__actionFilesApplyIconSize.slider().valueChanged.connect(filesIconSize_changed)

        # create menu for layout model button
        menu = QMenu(self.btFilesTabLayoutModel)
        menu.addAction(self.__actionFilesApplyTabLayoutFull)
        menu.addAction(self.__actionFilesApplyTabLayoutTop)
        menu.addAction(self.__actionFilesApplyTabLayoutLeft)
        menu.addAction(self.__actionFilesApplyTabLayoutBottom)
        menu.addAction(self.__actionFilesApplyTabLayoutRight)
        menu.addSeparator()
        menu.addAction(self.__actionFilesApplyIconSize)
        menu.triggered.connect(filesTabLayoutModel_Clicked)
        menu.aboutToShow.connect(filesIconSize_update)

        self.btFilesTabLayoutModel.setMenu(menu)
        self.btFilesTabLayoutModel.clicked.connect(filesTabLayoutReset_Clicked)

        self.splitterFiles.setSizes([1000, 1000])

        self.twInfo.setStyleSheet("QTabBar::tab::disabled {width: 0; height: 0; margin: 0; padding: 0; border: none;} ")

        #self.tabMain.tabBarClicked.connect(children_Clicked)
        self.tabMain.currentChanged.connect(children_Clicked)
        self.tabFilesDetails.tabBarClicked.connect(children_Clicked)
        self.tvDirectoryTree.activated.connect(children_Clicked)
        self.twInfo.currentChanged.connect(children_Clicked)
        self.btFilesTabLayoutModel.clicked.connect(children_Clicked)
        self.framePathBar.clicked.connect(children_Clicked)
        self.framePathBar.pathChanged.connect(filesPath_Changed)
        self.framePathBar.viewChanged.connect(filesView_Changed)
        self.framePathBar.filterChanged.connect(filesFilter_Changed)
        self.framePathBar.filterVisibilityChanged.connect(filesFilterVisibility_Changed)
        self.framePathBar.setPanel(self)
        self.treeViewFiles.focused.connect(children_Clicked)
        self.treeViewFiles.header().sectionClicked.connect(children_Clicked)
        self.treeViewClipboard.focused.connect(children_Clicked)
        self.treeViewClipboard.header().sectionClicked.connect(children_Clicked)

        self.treeViewFiles.header().setSectionsClickable(True)
        self.treeViewFiles.header().sectionClicked.connect(self.__filesSort)
        self.treeViewFiles.doubleClicked.connect(self.__filesDoubleClick)
        self.treeViewFiles.keyPressed.connect(self.__filesKeyPressed)

        self.treeViewFiles.selectionModel().selectionChanged.connect(self.__filesSelectionChanged)

        self.treeViewFiles.iconStartLoad.connect(treeViewFiles_iconStartLoad)
        self.treeViewFiles.iconStopLoad.connect(treeViewFiles_iconStopLoad)
        self.treeViewFiles.iconProcessed.connect(treeViewFiles_iconProcessed)

        self.widgetFilePreview.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.widgetFilePreview.contextMenuEvent = self.__filesContextMenuInformations

        self.treeViewFiles.beginUpdate()
        self.__filesAddParentDirectory()
        self.treeViewFiles.resizeColumns(False)
        self.treeViewFiles.endUpdate()

        # Allow zooming with right mouse button.
        # Drag for zoom box, doubleclick to view full image.
        self.gvFilesPreview.setCacheMode(QGraphicsView.CacheBackground)
        self.gvFilesPreview.zoomChanged.connect(filesPreview_ZoomChanged)
        self.hsAnimatedFrameNumber.valueChanged.connect(self.__filesAnimatedFrameChange)
        self.tbPlayPause.clicked.connect(self.__filesPlayPauseAnimation)
        self.__filesHidePreview()

        self.wAnimated.setVisible(False)

        self.__filesDirTreeModel.setRootPath(QDir.currentPath())
        self.__filesDirTreeModel.setFilter(QDir.AllDirs|QDir.Dirs|QDir.Drives|QDir.NoSymLinks|QDir.NoDotAndDotDot)
        self.tvDirectoryTree.setModel(self.__filesDirTreeModel)
        self.tvDirectoryTree.selectionModel().selectionChanged.connect(filesTvSelectedPath_changed)
        self.tvDirectoryTree.expanded.connect(filesTvSelectedPath_expandedCollapsed)
        self.tvDirectoryTree.collapsed.connect(filesTvSelectedPath_expandedCollapsed)
        self.tvDirectoryTree.contextMenuEvent = self.__filesContextMenuDirectoryTree
        self.tvDirectoryTree.hideColumn(1) # gide 'size'
        self.tvDirectoryTree.hideColumn(2) # gide 'type'

        # -- clipboard --
        self.__actionClipboardApplyTabLayoutTop.triggered.connect(children_Clicked)
        self.__actionClipboardApplyTabLayoutLeft.triggered.connect(children_Clicked)
        self.__actionClipboardApplyTabLayoutBottom.triggered.connect(children_Clicked)
        self.__actionClipboardApplyTabLayoutRight.triggered.connect(children_Clicked)
        self.__actionClipboardApplyIconSize.slider().valueChanged.connect(clipboardIconSize_changed)


        # create menu for layout model button
        menuC = QMenu(self.btClipboardTabLayoutModel)
        menuC.addAction(self.__actionClipboardApplyTabLayoutTop)
        menuC.addAction(self.__actionClipboardApplyTabLayoutLeft)
        menuC.addAction(self.__actionClipboardApplyTabLayoutBottom)
        menuC.addAction(self.__actionClipboardApplyTabLayoutRight)
        menuC.addSeparator()
        menuC.addAction(self.__actionClipboardApplyIconSize)
        menuC.triggered.connect(clipboardTabLayoutModel_Clicked)
        menuC.aboutToShow.connect(clipboardIconSize_update)

        self.btClipboardTabLayoutModel.setMenu(menuC)
        self.btClipboardTabLayoutModel.clicked.connect(clipboardTabLayoutReset_Clicked)
        self.btClipboardTabLayoutModel.clicked.connect(children_Clicked)

        # Allow zooming with right mouse button.
        # Drag for zoom box, doubleclick to view full image.
        self.gvClipboardPreview.setCacheMode(QGraphicsView.CacheBackground)
        self.gvClipboardPreview.zoomChanged.connect(clipboardPreview_ZoomChanged)
        self.__clipboardHidePreview()


        self.__filesRefreshTabLayout()
        self.__clipboardRefreshTabLayout()


    def __refreshPanelHighlighted(self):
        """Refresh panel highlighted and emit signal"""
        Debug.print('[BCMainViewTab.__refreshPanelHighlighted] value: {0} // {1}', self.__isHighlighted, self.filesPath())

        self.framePathBar.setHighlighted(self.__isHighlighted)
        if self.__isHighlighted:
            self.highlightedStatusChanged.emit(self)



    # -- PRIVATE FILES ---------------------------------------------------------

    def __filesHidePreview(self, msg=None):
        """Hide preview and display message"""
        if msg is None:
            self.lblFilesNoPreview.setText("No image selected")
        elif isinstance(msg, str):
            self.lblFilesNoPreview.setText(msg)
        else:
            self.lblFilesNoPreview.setPixmap(msg)

        self.swFilesPreview.setCurrentIndex(1)


    def __filesShowPreview(self, img=None):
        """Hide preview and display message"""
        self.swFilesPreview.setCurrentIndex(0)
        self.gvFilesPreview.setImage(img)
        self.lblFilesNoPreview.setText("...")


    def __filesSort(self, index=None):
        """Sort files according to column index"""
        if self.__filesQuery is None:
            return

        if index is None:
            index = self.treeViewFiles.header().sortIndicatorSection()

        if index is None:
            return

        self.__filesQuery.clearSortRules()

        ascending = (self.treeViewFiles.header().sortIndicatorOrder() == Qt.AscendingOrder)

        if index == BCMainViewFiles.COLNUM_NAME or index == BCMainViewFiles.COLNUM_ICON:
            self.__filesQuery.addSortRule([
                    BCFileListSortRule(BCFileProperty.FILE_NAME, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_DATE, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_SIZE, ascending)
                ])
        elif index == BCMainViewFiles.COLNUM_TYPE:
            self.__filesQuery.addSortRule([
                    BCFileListSortRule(BCFileProperty.FILE_FORMAT, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_NAME, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_DATE, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_SIZE, ascending)
                ])
        elif index == BCMainViewFiles.COLNUM_SIZE:
            self.__filesQuery.addSortRule([
                    BCFileListSortRule(BCFileProperty.FILE_SIZE, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_NAME, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_DATE, ascending)
                ])
        elif index == BCMainViewFiles.COLNUM_DATE:
            self.__filesQuery.addSortRule([
                    BCFileListSortRule(BCFileProperty.FILE_DATE, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_NAME, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_SIZE, ascending)
                ])
        elif index == BCMainViewFiles.COLNUM_WIDTH:
            self.__filesQuery.addSortRule([
                    BCFileListSortRule(BCFileProperty.IMAGE_WIDTH, ascending),
                    BCFileListSortRule(BCFileProperty.IMAGE_HEIGHT, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_NAME, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_DATE, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_SIZE, ascending)
                ])
        elif index == BCMainViewFiles.COLNUM_HEIGHT:
            self.__filesQuery.addSortRule([
                    BCFileListSortRule(BCFileProperty.IMAGE_HEIGHT, ascending),
                    BCFileListSortRule(BCFileProperty.IMAGE_WIDTH, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_NAME, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_DATE, ascending),
                    BCFileListSortRule(BCFileProperty.FILE_SIZE, ascending)
                ])

        self.__filesQuery.sort()
        self.__filesUpdate()


    def __filesAddParentDirectory(self):
        """Add parent directory to treeview"""
        if self.framePathBar.mode() == BCWPathBar.MODE_PATH:
            self.treeViewFiles.addFile(BCDirectory(os.path.join(self.filesPath(), '..')))


    def __filesUpdate(self):
        """Update file list from current fileQuery object"""
        if self.__filesQuery is None:
            return

        if self.__filesQuery.nbFiles() > 1500:
            self.__filesProgressStart(0,i18n('Loading list'))
            QApplication.setOverrideCursor(Qt.WaitCursor)

        self.treeViewFiles.beginUpdate()

        # clear all content
        self.treeViewFiles.clear()
        QApplication.instance().processEvents()

        # add parent directory '..'
        self.__filesAddParentDirectory()

        self.__filesFilter = None

        if self.framePathBar.mode() == BCWPathBar.MODE_PATH:
            self.treeViewFiles.setShowPath(False)
            totalSpace, usedSpace, freeSpace = shutil.disk_usage(self.filesPath())
        else:
            self.treeViewFiles.setShowPath(True)
            totalSpace, usedSpace, freeSpace = (-1, -1, -1)

        self.__filesCurrentStats = {
                'nbFiles': 0,
                'nbDir': 0,
                'nbTotal': 0,
                'sizeFiles': 0,

                'nbFilteredFiles': 0,
                'nbFilteredDir': 0,
                'nbFilteredTotal': 0,
                'sizeFilteredFiles': 0,

                'nbSelectedFiles': 0,
                'nbSelectedDir': 0,
                'nbSelectedTotal': 0,
                'sizeSelectedFiles': 0,

                'totalDiskSize': totalSpace,
                'usedDiskSize': usedSpace,
                'freeDiskSize': freeSpace
            }

        for file in self.__filesQuery.files():
            if file.format() == BCFileManagedFormat.DIRECTORY:
                self.__filesCurrentStats['nbDir']+=1
            else:
                self.__filesCurrentStats['nbFiles']+=1
                self.__filesCurrentStats['sizeFiles']+=file.size()

            self.treeViewFiles.addFile(file)


        self.__filesCurrentStats['nbTotal'] = self.__filesCurrentStats['nbDir'] + self.__filesCurrentStats['nbFiles']
        self.__filesUpdateStats()
        self.__filesApplyFilter(None)

        self.treeViewFiles.resizeColumns(True)

        self.__filesProgressStop()

        self.treeViewFiles.endUpdate()
        if self.__filesQuery.nbFiles() > 1500:
            QApplication.restoreOverrideCursor()


    def __filesRefresh(self, fileQuery=None):
        """update file list with current path"""
        def fileQueryStepExecuted(value):
            if value[0] == BCFileList.STEPEXECUTED_SEARCH:
                # in this case, value[1] returns number of files to scan
                if value[1] > 500:
                    self.__filesProgressStart(value[1], i18n('Analyzing file %v of %m (%p%)'))
            elif value[0] == BCFileList.STEPEXECUTED_SCAN:
                # in this case, scanning is finished
                if self.__filesPbVisible:
                    self.__filesProgressStop()
            elif value[0] == BCFileList.STEPEXECUTED_SCANNING:
                # in this case, value[1] give processed index
                if self.__filesPbVisible:
                    self.__filesProgressSetNext()


        if not self.isVisible():
            # if panel is not visible, do not update file list
            self.__filesAllowRefresh = False
            self.__filesBlockedRefresh+=1
            return

        if self.framePathBar.mode() == BCWPathBar.MODE_SAVEDVIEW:
            if self.__filesQuery is None:
                self.__filesQuery = BCFileList()

            refType = self.__uiController.quickRefType(self.filesPath())


            if refType == BCWPathBar.QUICKREF_RESERVED_LAST_OPENED:
                self.__filesQuery.setResult(self.filesLastDocumentsOpened().list())
            elif refType == BCWPathBar.QUICKREF_RESERVED_LAST_SAVED:
                self.__filesQuery.setResult(self.filesLastDocumentsSaved().list())
            elif refType == BCWPathBar.QUICKREF_RESERVED_LAST_ALL:
                self.__filesQuery.setResult(list(set(self.filesLastDocumentsOpened().list() + self.filesLastDocumentsSaved().list())))
            elif refType == BCWPathBar.QUICKREF_RESERVED_HISTORY:
                self.__filesQuery.setResult([directory for directory in self.filesHistory().list() if not directory.startswith('@')])
            elif refType == BCWPathBar.QUICKREF_SAVEDVIEW_LIST:
                self.__filesQuery.setResult(self.filesSavedView().get())
            elif refType == BCWPathBar.QUICKREF_RESERVED_BACKUPFILTERDVIEW:
                self.__filesQuery.setResult(self.filesBackupFilterDView().list())
            elif refType == BCWPathBar.QUICKREF_RESERVED_FLAYERFILTERDVIEW:
                self.__filesQuery.setResult(self.filesLayerFilterDView().list())

        else:
            # MODE_PATH
            if fileQuery is None:
                if self.__filesQuery is None:
                    filter = BCFileListRule()

                    if self.__uiController.optionViewFileManagedOnly():
                        reBase = [fr'\.{extension}' for extension in BCFileManagedFormat.list()]
                        if self.__uiController.optionViewFileBackup():
                            bckSufRe=BCFileManagedFormat.backupSuffixRe()
                            reBase+=[fr'\.{extension}{bckSufRe}' for extension in BCFileManagedFormat.list()]

                        filter.setName((r're:({0})$'.format('|'.join(reBase)), 'match'))
                    else:
                        filter.setName((r're:.*', 'match'))

                    self.__filesQuery = BCFileList()
                    self.__filesQuery.addPath(self.filesPath())
                    self.__filesQuery.setIncludeDirectories(True)

                    if self.__uiController.optionViewFileHidden():
                        self.__filesQuery.setIncludeHidden(True)
                    self.__filesQuery.addRule(filter)
            elif not isinstance(fileQuery, BCFileList):
                raise EInvalidType('Given `fileQuery` must be a <BCFileList>')
            else:
                self.__filesQuery = fileQuery


            try:
                # ensure there's no current connection before create a new one
                self.__filesQuery.stepExecuted.disconnect(fileQueryStepExecuted)
            except:
                pass
            self.__filesQuery.stepExecuted.connect(fileQueryStepExecuted)

            self.treeViewFiles.beginUpdate()
            self.treeViewFiles.clear()
            self.treeViewFiles.endUpdate()
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.__filesQuery.execute(True)
            QApplication.restoreOverrideCursor()

        # sort files according to columns + add to treeview
        self.__filesSort()
        self.__filesBlockedRefresh=0


    def __filesRefreshTabLayout(self):
        """Refresh layout according to current configuration"""
        if self.__filesTabLayout == BCMainViewTabFilesLayout.FULL:
            self.tabFilesDetails.setVisible(False)
            self.__actionFilesApplyTabLayoutFull.setChecked(True)
            self.__actionFilesApplyTabLayoutTop.setChecked(False)
            self.__actionFilesApplyTabLayoutLeft.setChecked(False)
            self.__actionFilesApplyTabLayoutBottom.setChecked(False)
            self.__actionFilesApplyTabLayoutRight.setChecked(False)
        else:
            self.__actionFilesApplyTabLayoutFull.setChecked(False)

            self.tabFilesDetails.setVisible(True)
            if self.__filesTabLayout == BCMainViewTabFilesLayout.TOP:
                self.splitterFiles.setOrientation(Qt.Vertical)
                self.splitterFiles.insertWidget(0, self.stackFiles)
                self.splitterPreview.setOrientation(Qt.Horizontal)
                self.splitterPreview.insertWidget(0, self.frameFileInformation)
                #self.tabFilesDetailsInformations.layout().setDirection(QBoxLayout.LeftToRight)

                self.__actionFilesApplyTabLayoutTop.setChecked(True)
                self.__actionFilesApplyTabLayoutLeft.setChecked(False)
                self.__actionFilesApplyTabLayoutBottom.setChecked(False)
                self.__actionFilesApplyTabLayoutRight.setChecked(False)

            elif self.__filesTabLayout == BCMainViewTabFilesLayout.LEFT:
                self.splitterFiles.setOrientation(Qt.Horizontal)
                self.splitterFiles.insertWidget(0, self.stackFiles)
                self.splitterPreview.setOrientation(Qt.Vertical)
                self.splitterPreview.insertWidget(0, self.frameFileInformation)
                #self.tabFilesDetailsInformations.layout().setDirection(QBoxLayout.TopToBottom)

                self.__actionFilesApplyTabLayoutTop.setChecked(False)
                self.__actionFilesApplyTabLayoutLeft.setChecked(True)
                self.__actionFilesApplyTabLayoutBottom.setChecked(False)
                self.__actionFilesApplyTabLayoutRight.setChecked(False)

            elif self.__filesTabLayout == BCMainViewTabFilesLayout.BOTTOM:
                self.splitterFiles.setOrientation(Qt.Vertical)
                self.splitterFiles.insertWidget(1, self.stackFiles)
                self.splitterPreview.setOrientation(Qt.Horizontal)
                self.splitterPreview.insertWidget(0, self.frameFileInformation)
                #self.tabFilesDetailsInformations.layout().setDirection(QBoxLayout.LeftToRight)

                self.__actionFilesApplyTabLayoutTop.setChecked(False)
                self.__actionFilesApplyTabLayoutLeft.setChecked(False)
                self.__actionFilesApplyTabLayoutBottom.setChecked(True)
                self.__actionFilesApplyTabLayoutRight.setChecked(False)

            elif self.__filesTabLayout == BCMainViewTabFilesLayout.RIGHT:
                self.splitterFiles.setOrientation(Qt.Horizontal)
                self.splitterFiles.insertWidget(1, self.stackFiles)
                self.splitterPreview.setOrientation(Qt.Vertical)
                self.splitterPreview.insertWidget(0, self.frameFileInformation)
                #self.tabFilesDetailsInformations.layout().setDirection(QBoxLayout.TopToBottom)

                self.__actionFilesApplyTabLayoutTop.setChecked(False)
                self.__actionFilesApplyTabLayoutLeft.setChecked(False)
                self.__actionFilesApplyTabLayoutBottom.setChecked(False)
                self.__actionFilesApplyTabLayoutRight.setChecked(True)

        self.tabFilesLayoutChanged.emit(self)


    def __filesDoubleClick(self, item):
        """Apply default action to item

        - Directory: go to directory
        - Image: open it
        - Other files: does nothing
        """
        if len(self.__filesSelected) == 1:
            if self.__uiController.commandFileDefaultAction(self.__filesSelected[0]):
                self.__uiController.commandQuit()
        elif not item is None:
            data = item.siblingAtColumn(BCMainViewFiles.COLNUM_NAME).data(BCMainViewFiles.USERROLE_FILE)

            if self.__uiController.commandFileDefaultAction(data):
                self.__uiController.commandQuit()


    def __filesKeyPressed(self, key):
        if key in (Qt.Key_Return, Qt.Key_Enter):
            closeBC = False
            for file in self.__filesSelected:
                if self.__uiController.commandFileDefaultAction(file):
                    closeBC = True
            if closeBC:
                self.__uiController.commandQuit()
        elif key == Qt.Key_Space:
            #print('__filesKeyPressed: Space', key)
            pass
        elif key == Qt.Key_Minus:
            self.filesSelectInvert()
        elif key == Qt.Key_Asterisk:
            self.filesSelectAll()
        elif key == Qt.Key_Slash:
            self.filesSelectNone()


    def __filesSelectionChanged(self, selection):
        """Made update according to current selection"""
        def cleanupNfoImageRows():
            """remove rows"""
            separatorRow, dummy = self.scrollAreaWidgetContentsNfoImage.layout().getWidgetPosition(self.lineImgExtraNfo)

            while self.scrollAreaWidgetContentsNfoImage.layout().rowCount() > separatorRow+1:
                self.scrollAreaWidgetContentsNfoImage.layout().removeRow(self.scrollAreaWidgetContentsNfoImage.layout().rowCount() - 1)

        def cleanupNfoFileRows():
            """remove rows"""
            separatorRow, dummy = self.scrollAreaWidgetContentsNfoGeneric.layout().getWidgetPosition(self.labelOwner)

            while self.scrollAreaWidgetContentsNfoGeneric.layout().rowCount() > separatorRow+1:
                self.scrollAreaWidgetContentsNfoGeneric.layout().removeRow(self.scrollAreaWidgetContentsNfoGeneric.layout().rowCount() - 1)

        def addNfoBtnRow(form, label, value, button, tooltip=None):
            fntValue = QFont()
            fntValue.setFamily('DejaVu Sans Mono')

            wContainer=QWidget()
            wContainerLayout=QHBoxLayout(wContainer)
            wContainerLayout.setContentsMargins(0,0,0,0)

            wValue = QLabel(value)
            wValue.setFont(fntValue)
            wValue.sizePolicy().setHorizontalPolicy(QSizePolicy.MinimumExpanding)
            if not tooltip is None:
                wValue.setToolTip(tooltip)

            button.sizePolicy().setHorizontalPolicy(QSizePolicy.Preferred)

            wContainerLayout.addWidget(wValue)
            wContainerLayout.addWidget(button)

            wContainer.setProperty('text', value)

            addNfoRow(form, label, wContainer)

        def addNfoRow(form, label, value, tooltip=None, style=None, shifted=False):
            """add a row"""
            fntLabel = QFont()
            fntLabel.setBold(True)

            wLabel = QLabel(label)
            wLabel.setFont(fntLabel)
            wLabel.sizePolicy().setVerticalPolicy(QSizePolicy.Expanding)

            if shifted:
                wLabel.setContentsMargins(30, 0, 0, 0)

            fntValue = QFont()
            fntValue.setFamily('DejaVu Sans Mono')

            if isinstance(value, str):
                wLabel.setAlignment(Qt.AlignLeft|Qt.AlignTop)
                wValue = QLabel(value)
                wValue.setFont(fntValue)
                if not tooltip is None:
                    wValue.setToolTip(tooltip)
            elif isinstance(value, QWidget):
                wValue=value

            if not style is None:
                wValue.setStyleSheet(self.__uiController.theme().style(style))

            form.layout().addRow(wLabel, wValue)

        def addSeparator(form, shifted=False):
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            if shifted:
                line.setContentsMargins(30, 0, 0, 0)
            form.layout().addRow(line)

        def applyBackupFilter(action):
            """Display opposite panel, go to given path, activate backup files, and apply filter"""
            oppositePanelId=self.__uiController.oppositePanelId(self)
            self.__uiController.commandGoBackupFilterDViewSet(backupList.files())
            self.__uiController.commandGoTo(oppositePanelId, '@backup filter')
            self.__uiController.commandViewDisplaySecondaryPanel(True)

        def applyLayerFileFilter(action):
            """Display opposite panel, go to given path, activate backup files, and apply filter"""
            oppositePanelId=self.__uiController.oppositePanelId(self)
            self.__uiController.commandGoFileLayerFilterDViewSet(fileLayerList)
            self.__uiController.commandGoTo(oppositePanelId, '@file layer filter')
            self.__uiController.commandViewDisplaySecondaryPanel(True)


        self.__filesCurrentStats['nbSelectedFiles'] = 0
        self.__filesCurrentStats['nbSelectedDir'] = 0
        self.__filesCurrentStats['nbSelectedTotal'] = 0
        self.__filesCurrentStats['sizeSelectedFiles'] = 0

        self.__filesSelected = self.treeViewFiles.selectedFiles()
        self.__filesSelectedNbDir = 0
        self.__filesSelectedNbFile = 0
        self.__filesSelectedNbTotal = 0
        self.__filesSelectedNbReadable = 0

        for file in self.__filesSelected:
            if file.format() == BCFileManagedFormat.DIRECTORY:
                if file.name() != '..':
                    self.__filesSelectedNbDir+=1
            else:
                self.__filesCurrentStats['sizeSelectedFiles']+=file.size()
                self.__filesSelectedNbFile+=1
                if file.readable():
                    self.__filesSelectedNbReadable+=1

        self.__filesSelectedNbTotal = self.__filesSelectedNbDir + self.__filesSelectedNbFile

        self.__filesCurrentStats['nbSelectedDir'] = self.__filesSelectedNbDir
        self.__filesCurrentStats['nbSelectedFiles'] = self.__filesSelectedNbFile
        self.__filesCurrentStats['nbSelectedTotal'] = self.__filesSelectedNbTotal
        self.__filesUpdateStats()
        if not self.__uiController is None:
            self.__uiController.updateMenuForPanel()

        cleanupNfoImageRows()
        cleanupNfoFileRows()
        # reset animation values
        self.wAnimated.setVisible(False)
        self.__filesCurrentAnimatedFrame=0
        self.__filesMaxAnimatedFrame=0
        if not self.__filesImgReaderAnimated is None:
            self.__filesImgReaderAnimated.stop()
            self.__filesImgReaderAnimated = None

        # ------------------- !!!!! Here start the noodle spaghetti !!!!! -------------------
        if self.__filesSelectedNbTotal == 1:
            # ------------------------------ File ------------------------------
            file = self.__filesSelected[0]

            self.lblPath.setText(file.path())
            self.lblPath.setToolTip(self.lblPath.text())

            self.lblName.setText(file.name())
            self.lblName.setToolTip(self.lblName.text())

            deltaTimeStr=''
            if not file.lastModificationDateTime() is None:
                deltaTime = round(time.time() - file.lastModificationDateTime(), 0)
                deltaTimeStr = i18n(f'<br><i>{secToStrTime(deltaTime)} ago<sup>(from current time)</sup></i>')

            self.lblModified.setText(tsToStr(file.lastModificationDateTime(), valueNone='-')+deltaTimeStr)
            self.lblModified.setToolTip(self.lblModified.text())

            if file.format() == BCFileManagedFormat.DIRECTORY:
                self.labelSize.setVisible(False)
                self.lblSize.setVisible(False)

                self.lblSize.setText('-')
                self.lblSize.setToolTip('')
            elif file.format() == BCFileManagedFormat.MISSING:
                self.labelSize.setVisible(True)
                self.lblSize.setVisible(True)

                self.lblSize.setText('-')
                self.lblSize.setToolTip(i18n('File is missing, size is not known'))
            else:
                self.labelSize.setVisible(True)
                self.lblSize.setVisible(True)

                self.lblSize.setText(f'{bytesSizeToStr(file.size())} ({file.size():n})')
                self.lblSize.setToolTip(self.lblSize.text())

            if sys.platform == 'linux':
                if file.format() == BCFileManagedFormat.MISSING:
                    self.lblPerm.setText('-')
                    self.lblPerm.setToolTip(i18n('File is missing, permission are not known'))

                    self.lblOwner.setText('-')
                    self.lblOwner.setToolTip(i18n('File is missing, owner is not known'))

                else:
                    og = file.ownerGroup()

                    self.lblPerm.setText(file.permissions())
                    self.lblPerm.setToolTip(self.lblPerm.text())

                    self.lblOwner.setText(f'{og[0]}/{og[1]}')
                    self.lblOwner.setToolTip(self.lblOwner.text())

            # Search for backup files...
            backupSuffix = Krita.instance().readSetting('', 'backupfilesuffix', '~').replace('.', r'\.')
            filePattern = file.name().replace('.', r'\.')
            rePattern = f"re:{filePattern}(?:\.\d+)?{backupSuffix}$"
            searchBackupRule = BCFileListRule()
            searchBackupRule.setName((rePattern, 'match'))


            backupList = BCFileList()
            backupList.addPath(file.path())
            backupList.addRule(searchBackupRule)
            backupList.addSortRule(BCFileListSortRule(BCFileProperty.FILE_DATE, False))

            backupList.execute()

            if backupList.nbFiles()>0:
                backupList.sort()

                filterButton = QPushButton(i18n("Show"))
                filterButton.setToolTip(i18n("Show in opposite panel"))
                filterButton.setStatusTip(i18n("Show backup files list in opposite panel"))
                filterButton.clicked.connect(applyBackupFilter)

                addSeparator(self.scrollAreaWidgetContentsNfoGeneric)
                if backupList.nbFiles() == 1:
                    addNfoBtnRow(self.scrollAreaWidgetContentsNfoGeneric, i18n("Backup files"), i18n("1 backup file found"), filterButton)
                else:
                    addNfoBtnRow(self.scrollAreaWidgetContentsNfoGeneric, i18n("Backup files"), i18n(f"{backupList.nbFiles()} backup files found"), filterButton)

                for fileBackup in backupList.files():
                    addSeparator(self.scrollAreaWidgetContentsNfoGeneric, shifted=True)
                    addNfoRow(self.scrollAreaWidgetContentsNfoGeneric, i18n("Backup file"), fileBackup.name(), shifted=True)

                    lastModifiedDiffStr=""
                    lastModifiedDiffTooltip=''
                    lastModifiedDiff=round(file.lastModificationDateTime() - fileBackup.lastModificationDateTime(),0)
                    if lastModifiedDiff>0:
                        lastModifiedDiffStr=i18n(f'<br><i>{secToStrTime(lastModifiedDiff)} ago<sup>(from current file)</sup></i>')
                        lastModifiedDiffTooltip=''

                    addNfoRow(self.scrollAreaWidgetContentsNfoGeneric, i18n("Modified"), tsToStr(fileBackup.lastModificationDateTime(), valueNone='-')+lastModifiedDiffStr, lastModifiedDiffTooltip, shifted=True)

                    backupSizeDiffTooltip=''
                    backupSizeDiffStr=""
                    backupSizeDiff=fileBackup.size() - file.size()
                    if backupSizeDiff>0:
                        backupSizeDiffStr=f'<br><i>+{bytesSizeToStr(backupSizeDiff)} (+{backupSizeDiff:n})</i>'
                        backupSizeDiffTooltip=''
                    elif backupSizeDiff<0:
                        backupSizeDiffStr=f'<br><i>-{bytesSizeToStr(abs(backupSizeDiff))} ({backupSizeDiff:n})</i>'
                        backupSizeDiffTooltip=''
                    addNfoRow(self.scrollAreaWidgetContentsNfoGeneric, i18n("Size"), f'{bytesSizeToStr(fileBackup.size())} ({fileBackup.size():n}){backupSizeDiffStr}', backupSizeDiffTooltip, shifted=True)


            # ------------------------------ Image ------------------------------
            if file.format() != BCFileManagedFormat.UNKNOWN:
                self.lblImgFormat.setText(BCFileManagedFormat.translate(file.format(), False))
            elif file.extension() != '':
                self.lblImgFormat.setText(BCFileManagedFormat.translate(file.extension(), False))
            else:
                self.lblImgFormat.setText("Unknown file type")

            if file.format() in BCFileManagedFormat.list():
                if file.imageSize().width() == -1 or file.imageSize().height() == -1:
                    self.lblImgSize.setText('-')
                else:
                    self.lblImgSize.setText(f'{file.imageSize().width()}x{file.imageSize().height()}')

                imgNfo = file.getMetaInformation()

                if 'resolution' in imgNfo:
                    self.lblImgResolution.setText(imgNfo['resolution'])
                else:
                    self.lblImgResolution.setText('-')

                if 'colorType' in imgNfo:
                    if 'paletteSize' in imgNfo:
                        if 'paletteCount' in imgNfo:
                            if imgNfo['paletteCount'] > 1 and imgNfo['paletteMin'] != imgNfo['paletteMax']:
                                self.lblImgMode.setText(f"{imgNfo['colorType'][1]}")
                            else:
                                self.lblImgMode.setText(f"{imgNfo['colorType'][1]} (Size: {imgNfo['paletteSize'][0]})")
                        else:
                            self.lblImgMode.setText(f"{imgNfo['colorType'][1]} (Size: {imgNfo['paletteSize']})")
                    else:
                        self.lblImgMode.setText(imgNfo['colorType'][1])
                else:
                    self.lblImgMode.setText('-')

                if 'bitDepth' in imgNfo:
                    self.lblImgDepth.setText(imgNfo['bitDepth'][1])
                else:
                    self.lblImgDepth.setText('-')

                if 'iccProfileName' in imgNfo:
                    iccProfilName = getLangValue(imgNfo['iccProfileName'], None, '-')
                    self.lblImgProfile.setText(iccProfilName)

                    if iccProfilName != '-' and 'iccProfileCopyright' in imgNfo:
                        iccProfilCprt = getLangValue(imgNfo['iccProfileCopyright'], None, '')
                        self.lblImgProfile.setToolTip(iccProfilCprt)
                    else:
                        self.lblImgProfile.setToolTip('')
                elif 'sRGBRendering' in imgNfo:
                    self.lblImgProfile.setText(f"sRGB: {imgNfo['sRGBRendering'][1]}")
                    self.lblImgProfile.setToolTip('')
                elif 'gamma' in imgNfo:
                    self.lblImgProfile.setText(f"<i>Gamma: {imgNfo['gamma']:.2f}</i>")
                    self.lblImgProfile.setToolTip('')
                else:
                    self.lblImgProfile.setText('-')
                    self.lblImgProfile.setToolTip('')

                if file.format() in [BCFileManagedFormat.PNG,
                                     BCFileManagedFormat.GIF,
                                     BCFileManagedFormat.WEBP,
                                     BCFileManagedFormat.ORA,
                                     BCFileManagedFormat.KRA]:
                    self.lineImgExtraNfo.setVisible(True)
                else:
                    self.lineImgExtraNfo.setVisible(False)

                if file.format() == BCFileManagedFormat.PNG:
                    if 'compressionLevel' in imgNfo:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Compression level', imgNfo['compressionLevel'][1])
                    else:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Compression level', '-')

                    if 'interlaceMethod' in imgNfo:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Interlace mode', imgNfo['interlaceMethod'][1])
                    else:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Interlace mode', '-')
                elif file.format() == BCFileManagedFormat.ORA:
                    if imgNfo['document.layerCount'] > 0:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Layers', str(imgNfo['document.layerCount']))
                    else:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Layers', '-')
                elif file.format() in [BCFileManagedFormat.GIF,
                                       BCFileManagedFormat.WEBP]:
                    if imgNfo['imageCount'] > 1:
                        try:
                            self.__filesImgReaderAnimated = QMovie(file.fullPathName())
                            self.__filesImgReaderAnimated.setCacheMode(QMovie.CacheAll)
                            self.tbPlayPause.setIcon(QIcon(":/images/play"))
                            self.wAnimated.setVisible(True)
                            self.lblAnimatedFrameNumber.setText(f"1/{imgNfo['imageCount']}")
                            self.hsAnimatedFrameNumber.setMaximum(imgNfo['imageCount'])
                            self.hsAnimatedFrameNumber.setValue(1)
                            self.__filesMaxAnimatedFrame=imgNfo['imageCount']
                            self.setFilesCurrentAnimatedFrame(1)
                            self.__filesAnimatedFrameChange(1)
                        except Exception as e:
                            Debug.print('[BCMainViewTab.__filesSelectionChanged] Unable to read animated GIF {0}: {1}', file.fullPathName(), e)
                            self.__filesImgReaderAnimated = None

                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Animated', 'Yes')
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, '',     f"<i>Frames:&nbsp;&nbsp;&nbsp;{imgNfo['imageCount']}</i>")

                        if 'imageDelayMin' in imgNfo:
                            if imgNfo['imageDelayMin'] == imgNfo['imageDelayMax']:
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, '', f"<i>Delay:&nbsp;&nbsp;&nbsp;&nbsp;{imgNfo['imageDelayMin']}ms</i>")
                            else:
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, '', f"<i>Delay:&nbsp;&nbsp;&nbsp;&nbsp;{imgNfo['imageDelayMin']} to {imgNfo['imageDelayMax']}ms</i>")
                        if 'loopDuration' in imgNfo:
                            addNfoRow(self.scrollAreaWidgetContentsNfoImage, '',     f"<i>Duration:&nbsp;{imgNfo['loopDuration']/1000:.2f}s</i>")

                        if 'paletteCount' in imgNfo and 'paletteMin' in imgNfo and 'paletteMax' in imgNfo:
                            if imgNfo['paletteCount'] > 1 and imgNfo['paletteMin'] != imgNfo['paletteMax']:
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, '',     f"<i>Palettes: {imgNfo['paletteCount']} (Sizes: {imgNfo['paletteMin']} to {imgNfo['paletteMax']})</i>")
                    else:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Animated', 'No')


                # ------------------------------ Image: KRA ------------------------------
                if file.format() == BCFileManagedFormat.KRA:
                    if imgNfo['imageCount'] > 1:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Animated', 'Yes')
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, '',     f"<i>Frames:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{imgNfo['imageCount']}</i>")


                        if imgNfo['imageDelay'] > 0:
                            addNfoRow(self.scrollAreaWidgetContentsNfoImage, '',     f"<i>Frame rate:&nbsp;{imgNfo['imageDelay']}fps</i>")
                            addNfoRow(self.scrollAreaWidgetContentsNfoImage, '',     f"<i>Duration:&nbsp;&nbsp;&nbsp;{frToStrTime(imgNfo['imageCount'],imgNfo['imageDelay'])}</i>")

                    else:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Animated', 'No')

                    addSeparator(self.scrollAreaWidgetContentsNfoImage)
                    if len(imgNfo['document.usedFonts']) > 0:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Used fonts', str(len(imgNfo['document.usedFonts'])))

                        fontList=QFontDatabase().families()

                        for fontName in imgNfo['document.usedFonts']:
                            if fontName in fontList:
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, '', f'<i>{fontName}</i>')
                            else:
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, '', f'<i>{fontName}</i>', i18n('Font is missing on this sytem!'), 'warning-label')
                    else:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Used fonts', 'None')


                    addSeparator(self.scrollAreaWidgetContentsNfoImage)
                    if imgNfo['document.layerCount'] > 0:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Layers', str(imgNfo['document.layerCount']))
                    else:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Layers', '-')

                    nbFileLayer = len(imgNfo['document.fileLayers'])
                    if nbFileLayer > 0:
                        filterButton = QPushButton(i18n("Show"))
                        filterButton.setToolTip(i18n("Show in opposite panel"))
                        filterButton.setStatusTip(i18n("Show layers files list in opposite panel"))
                        filterButton.clicked.connect(applyLayerFileFilter)

                        fileLayerList=[]

                        addSeparator(self.scrollAreaWidgetContentsNfoImage)
                        if nbFileLayer == 1:
                            addNfoBtnRow(self.scrollAreaWidgetContentsNfoImage, i18n("File layers"), i18n("1 file layer found"), filterButton)
                        else:
                            addNfoBtnRow(self.scrollAreaWidgetContentsNfoImage, i18n("File layers"), i18n(f"{nbFileLayer} file layers found"), filterButton)


                        for fileName in imgNfo['document.fileLayers']:
                            fullFileName = os.path.join(file.path(), fileName)
                            fileLayerList.append(fullFileName)

                            addSeparator(self.scrollAreaWidgetContentsNfoImage, shifted=True)
                            if os.path.isfile(fullFileName):
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n('File layer'), fileName, shifted=True)

                                fileLayer = BCFile(fullFileName)

                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n("Modified"), tsToStr(fileLayer.lastModificationDateTime(), valueNone='-'), shifted=True)
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n("File size"), f'{bytesSizeToStr(fileLayer.size())} ({fileLayer.size():n})', shifted=True)

                                if fileLayer.imageSize().width() == -1 or fileLayer.imageSize().height() == -1:
                                    addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n("Image size"), '-', shifted=True)
                                else:
                                    addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n("Image size"), f'{fileLayer.imageSize().width()}x{fileLayer.imageSize().height()}', shifted=True)
                            else:
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n('File layer'), f'<i>{fileName}</i>', 'File is missing!', 'warning-label', shifted=True)
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n("Modified"), '-', shifted=True)
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n("File size"), '-', shifted=True)
                                addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n("Image size"), '-', shifted=True)


                    addSeparator(self.scrollAreaWidgetContentsNfoImage)
                    if len(imgNfo['document.embeddedPalettes']) > 0:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Embedded palettes', str(len(imgNfo['document.embeddedPalettes'])))

                        for paletteName in imgNfo['document.embeddedPalettes']:
                            palette = imgNfo['document.embeddedPalettes'][paletteName]
                            addSeparator(self.scrollAreaWidgetContentsNfoImage, shifted=True)
                            addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n('Palette'), paletteName, shifted=True)
                            addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n('Dimension'), f'{palette["columns"]}x{palette["rows"]}', shifted=True)
                            addNfoRow(self.scrollAreaWidgetContentsNfoImage, i18n('Colors'), str(palette["colors"]), shifted=True)
                    else:
                        addNfoRow(self.scrollAreaWidgetContentsNfoImage, 'Embedded palettes', 'None')


                    self.twInfo.setTabEnabled(2, True)
                    self.twInfo.setTabEnabled(3, True)
                    self.setStyleSheet("QTabBar::tab::disabled {width: 0; height: 0; margin: 0; padding: 0; border: none;} ")

                    # ------------------------------ Image: KRA <ABOUT> ------------------------------
                    self.lblKraAboutTitle.setText(strDefault(imgNfo['about.title'], '-'))
                    self.lblKraAboutSubject.setText(strDefault(imgNfo['about.subject'], '-'))
                    self.lblKraAboutDesc.setText(strDefault(imgNfo['about.description'], '-'))
                    self.lblKraAboutKeywords.setText(strDefault(imgNfo['about.keywords'], '-'))
                    self.lblKraAboutInitCreator.setText(strDefault(imgNfo['about.creator'], '-'))
                    self.lblKraAboutCreationDate.setText(strDefault(imgNfo['about.creationDate'], '-'))
                    self.lblKraAboutEditingCycles.setText(strDefault(imgNfo['about.editingCycles'], '-'))

                    nbDay = 0
                    ttTime = imgNfo['about.editingTime']
                    if ttTime >= 86400:
                        nbDay = floor(ttTime/86400)
                        ttTime-= nbDay * 86400
                    value = tsToStr(ttTime-3600, 't')
                    if nbDay > 0:
                        value+= f' +{nbDay}d'
                    self.lblKraAboutEditingTime.setText(value)

                    # ------------------------------ Image: KRA <AUTHOR> ------------------------------
                    self.lblKraAuthorNickname.setText(strDefault(imgNfo['author.nickName'], '-'))
                    self.lblKraAuthorFName.setText(strDefault(imgNfo['author.firstName'], '-'))
                    self.lblKraAuthorLName.setText(strDefault(imgNfo['author.lastName'], '-'))
                    self.lblKraAuthorInitials.setText(strDefault(imgNfo['author.initials'], '-'))
                    self.lblKraAuthorTitle.setText(strDefault(imgNfo['author.title'], '-'))
                    self.lblKraAuthorPosition.setText(strDefault(imgNfo['author.position'], '-'))
                    self.lblKraAuthorCompagny.setText(strDefault(imgNfo['author.company'], '-'))

                    if len(imgNfo['author.contact']) == 0:
                        self.lblKraAuthorContact.setText('-')
                    else:
                        __KEY_TRANS = {
                            'telephone': 'Phone:  ',
                            'address':   'Adress: ',
                            'homepage':  'Site:   ',
                            'fax':       'Fax:    ',
                            'email':     'eMail:  '
                        }
                        value = []

                        for contact in imgNfo['author.contact']:
                            key = list(contact.keys())[0]
                            tmp = key
                            if key in __KEY_TRANS:
                                tmp = __KEY_TRANS[key].replace(' ', '&nbsp;')
                            value.append(f'{tmp}<i>{contact[key]}</i>')

                        self.lblKraAuthorContact.setText(strDefault('<br>'.join(value), '-'))

                else:
                    self.twInfo.setTabEnabled(2, False)
                    self.twInfo.setTabEnabled(3, False)
                    self.setStyleSheet("QTabBar::tab::disabled {width: 0; height: 0; margin: 0; padding: 0; border: none;} ")

                self.__filesShowPreview(file.image())
                if not self.gvFilesPreview.hasImage():
                    self.__filesHidePreview("Unable to read image")

            else:
                self.lblImgSize.setText('-')
                self.lblImgResolution.setText('-')
                self.lblImgMode.setText('-')
                self.lblImgDepth.setText('-')
                self.lblImgProfile.setText('-')
                self.lblImgProfile.setToolTip('')
                self.lineImgExtraNfo.setVisible(False)
                self.twInfo.setTabEnabled(2, False)
                self.twInfo.setTabEnabled(3, False)
                self.setStyleSheet("QTabBar::tab::disabled {width: 0; height: 0; margin: 0; padding: 0; border: none;} ")

                #self.__filesHidePreview("Not a recognized image file")
                qSize=self.swFilesPreview.size()
                size=min(qSize.width(), qSize.height()) - 16
                self.__filesHidePreview(file.icon().pixmap(QSize(size, size)))
        else:
            # file
            self.lblPath.setText('-')
            self.lblPath.setToolTip('')

            self.lblName.setText('-')
            self.lblName.setToolTip('')

            self.lblModified.setText('-')
            self.lblModified.setToolTip('')

            self.lblSize.setText('-')
            self.lblSize.setToolTip('')

            if sys.platform == 'linux':
                self.lblPerm.setText('-')
                self.lblPerm.setToolTip('')

                self.lblOwner.setText('-')
                self.lblOwner.setToolTip('')

            # image
            self.lblImgFormat.setText('-')
            self.lblImgSize.setText('-')
            self.lblImgResolution.setText('-')
            self.lblImgMode.setText('-')
            self.lblImgDepth.setText('-')
            self.lblImgProfile.setText('-')
            self.lineImgExtraNfo.setVisible(False)
            self.twInfo.setTabEnabled(2, False)
            self.twInfo.setTabEnabled(3, False)
            self.setStyleSheet("QTabBar::tab::disabled {width: 0; height: 0; margin: 0; padding: 0; border: none;} ")

            if self.__filesSelectedNbTotal>1:
                self.__filesHidePreview("No preview for multiple selection")
            else:
                self.__filesHidePreview("No image selected")


    def __filesUpdateStats(self):
        """Update current status bar with files statistics"""
        statusFileText = []
        fileText = []

        key=''
        if self.__filesCurrentStats['nbFilteredTotal'] > 0:
            key='Filtered'

        if self.__filesCurrentStats[f'nb{key}Total'] > 0:
            fileText.append(i18n(f"{self.__filesCurrentStats['nbSelectedTotal']} out of {self.__filesCurrentStats[f'nb{key}Total']}"))
            fileText.append(i18n(f"{bytesSizeToStr(self.__filesCurrentStats['sizeSelectedFiles'])} out of {bytesSizeToStr(self.__filesCurrentStats[f'size{key}Files'])}"))

            if self.__filesCurrentStats[f'nb{key}Dir'] > 0:
                text=i18n('Directories: ')

                if self.__filesCurrentStats['nbSelectedDir'] > 0:
                    text+=i18n(f"{self.__filesCurrentStats['nbSelectedDir']} out of ")
                text+=str(self.__filesCurrentStats[f'nb{key}Dir'])
                statusFileText.append(text)

            if self.__filesCurrentStats[f'nb{key}Files'] > 0:
                text=i18n('Files: ')

                if self.__filesCurrentStats['nbSelectedFiles'] > 0:
                    text+=i18n(f"{self.__filesCurrentStats['nbSelectedFiles']} out of ")
                text+=str(self.__filesCurrentStats[f'nb{key}Files'])

                if self.__filesCurrentStats[f'size{key}Files'] > 0:
                    text+=' ('
                    if self.__filesCurrentStats['nbSelectedFiles'] > 0:
                        text+=i18n(f"{bytesSizeToStr(self.__filesCurrentStats['sizeSelectedFiles'])} out of ")
                    text+=f"{bytesSizeToStr(self.__filesCurrentStats[f'size{key}Files'])})"
                statusFileText.append(text)
        elif key == 'Filtered':
            statusFileText.append( i18n("No file is matching filter") )
        else:
            statusFileText.append( i18n("Empty directory") )

        if key == 'Filtered':
            key = '[Filtered view] - '

        self.lblFileNfo.setText(key+', '.join(fileText))
        self.lblFileNfo.setStatusTip(key+', '.join(statusFileText))

        if self.framePathBar.mode() == BCWPathBar.MODE_PATH:
            if self.__filesCurrentStats['totalDiskSize'] > 0:
                pctUsed = 100 * (self.__filesCurrentStats['usedDiskSize']/self.__filesCurrentStats['totalDiskSize'])
                pUsed = f' ({pctUsed:.2f}%)'
                pFree = f' ({100 - pctUsed:.2f}%)'
            else:
                pUsed = ''
                pFree = ''

            self.lblDiskNfo.setText(f"{bytesSizeToStr(self.__filesCurrentStats['freeDiskSize'])} free")
            self.lblDiskNfo.setToolTip(i18n('Free space available on disk'))
            self.lblDiskNfo.setStatusTip(f"Disk size: {bytesSizeToStr(self.__filesCurrentStats['totalDiskSize'])}, Used size: {bytesSizeToStr(self.__filesCurrentStats['usedDiskSize'])}{pUsed}, Free size: {bytesSizeToStr(self.__filesCurrentStats['freeDiskSize'])}{pFree}")
        elif not self.filesSavedView().current() is None:
            # saved view mode =
            self.lblDiskNfo.setText(f"View <b><i>{self.filesSavedView().current(True)}</i><b>")
            self.lblDiskNfo.setToolTip('')
            self.lblDiskNfo.setStatusTip(i18n("You're currently into a saved view: there's no disk information available as listed files can be from different disks"))
        else:
            self.lblDiskNfo.setText(f"View <b><i>{self.__uiController.quickRefName(self.filesPath())}</i><b>")
            self.lblDiskNfo.setToolTip('')
            self.lblDiskNfo.setStatusTip(i18n("You're currently into a view: there's no disk information available as listed files can be from different disks"))


    def __filesApplyFilter(self, filter):
        """Apply filter to current file list"""
        self.treeViewFiles.setFilter(filter)

        self.__filesCurrentStats['nbFilteredFiles'] = 0
        self.__filesCurrentStats['nbFilteredDir'] = 0
        self.__filesCurrentStats['nbFilteredTotal'] = 0
        self.__filesCurrentStats['sizeFilteredFiles'] = 0

        if self.filesFilterVisible() and self.filesFilter() != '':
            filterModel = self.treeViewFiles.filterModel()
            for rowIndex in range(filterModel.rowCount()):
                file = filterModel.index(rowIndex, BCMainViewFiles.COLNUM_NAME).data(BCMainViewFiles.USERROLE_FILE)

                if file.format() == BCFileManagedFormat.DIRECTORY:
                    if file.name() != '..':
                        self.__filesCurrentStats['nbFilteredDir']+=1
                else:
                    self.__filesCurrentStats['sizeFilteredFiles']+=file.size()
                    self.__filesCurrentStats['nbFilteredFiles']+=1

                self.__filesCurrentStats['nbFilteredTotal'] = self.__filesCurrentStats['nbFilteredDir'] + self.__filesCurrentStats['nbFilteredFiles']

        self.__filesUpdateStats()


    def __filesAnimatedFrameChange(self, value):
        """Slider for animated frame has been moved"""
        self.__filesCurrentAnimatedFrame = value
        nbZ=len(str(self.__filesMaxAnimatedFrame))
        self.lblAnimatedFrameNumber.setText(f'Frame {self.__filesCurrentAnimatedFrame:>0{nbZ}}/{self.__filesMaxAnimatedFrame} ')

        if not self.__filesImgReaderAnimated is None:
            if self.__filesImgReaderAnimated.state() != QMovie.Running:
                self.__filesImgReaderAnimated.jumpToFrame(self.__filesCurrentAnimatedFrame - 1)
            self.gvFilesPreview.setImage(self.__filesImgReaderAnimated.currentImage(), False)


    def __filesPlayPauseAnimation(self, value):
        """Play/pause current animation"""
        if not self.__filesImgReaderAnimated is None:
            if self.__filesImgReaderAnimated.state() == QMovie.Running:
                self.__filesImgReaderAnimated.setPaused(True)
                self.tbPlayPause.setIcon(QIcon(":/images/play"))
                self.__filesImgReaderAnimated.frameChanged.disconnect(self.setCurrentAnimatedFrame)
            elif self.__filesImgReaderAnimated.state() == QMovie.Paused:
                self.__filesImgReaderAnimated.frameChanged.connect(self.setCurrentAnimatedFrame)
                self.__filesImgReaderAnimated.setPaused(False)
                self.tbPlayPause.setIcon(QIcon(":/images/pause"))
            else:
                # not running
                self.__filesImgReaderAnimated.frameChanged.connect(self.setCurrentAnimatedFrame)
                self.__filesImgReaderAnimated.start()
                self.tbPlayPause.setIcon(QIcon(":/images/pause"))


    def __filesProgressStart(self, maxValue, text=None):
        """Show progress bar / hide status bar information

        Progress value is initialized to 0
        Progress maxValue given maxValue

        Text value:
         %p = current percent
         %v = current step
         %m = total steps
        """
        if text is None or text == '':
            text = '%p%'

        self.__filesPbMax = maxValue
        self.__filesPbVal = 0
        self.__filesPbInc = max(1, round(maxValue/400, 0))
        self.__filesPbDispCount+=1
        self.__filesPbVisible=True

        self.pbProgress.setValue(0)
        self.pbProgress.setMaximum(maxValue)
        self.pbProgress.setFormat(text)
        #self.lblFileNfo.setVisible(False)
        self.lblDiskNfo.setVisible(False)
        self.lineDiskNfo.setVisible(False)
        self.pbProgress.setVisible(True)


    def __filesProgressStop(self):
        """Hide progress bar / display status bar information"""
        #self.lblFileNfo.setVisible(True)
        if self.__filesPbVisible:
            self.__filesPbDispCount-=1
            if self.__filesPbDispCount<=0:
                self.lblDiskNfo.setVisible(True)
                self.lineDiskNfo.setVisible(True)
                self.pbProgress.setVisible(False)
                self.__filesPbDispCount = 0
                self.__filesPbVisible=False


    def __filesProgressSetValue(self, value):
        """set progress bar value"""
        self.pbProgress.setValue(value)
        self.__filesPbVal = value


    def __filesProgressSetNext(self):
        """set progress bar next value"""
        self.__filesPbVal+=1
        if self.__filesPbVal >=  self.pbProgress.value() + self.__filesPbInc:
            self.pbProgress.setValue(self.__filesPbVal)


    def __filesContextMenuInformations(self, event):
        """Display context menu for informations tabs"""

        def copyToClipboard(source=None):
            data=[]

            if source is None:
                # loop on all tabs
                for index in range(self.twInfo.count()):
                    if self.twInfo.isTabEnabled(index):
                        data.append('\n'.join(copyToClipboard(index)))

            elif isinstance(source, int):
                # source is a tab index
                # loop on all QLabel
                formLayout = self.twInfo.widget(source).layout().itemAt(0).widget().widget().layout()

                if not formLayout is None:
                    table=BCTable()

                    table.setTitle(f'[ {stripTags(self.twInfo.tabText(source))} ]' )
                    table.setHeader(['Property', 'Value'])

                    for row in range(formLayout.rowCount()):
                        itemLabel = formLayout.itemAt(row, QFormLayout.LabelRole)
                        itemValue = formLayout.itemAt(row, QFormLayout.FieldRole)

                        if itemLabel is None:
                            textLabel = ''
                        else:
                            textLabel = stripTags(itemLabel.widget().text())

                        if itemValue is None:
                            textValue = ''
                        elif isinstance(itemValue.widget(), QLabel):
                            textValue = stripTags(itemValue.widget().text())
                            table.addRow([textLabel, textValue])
                        elif isinstance(itemValue.widget(), QFrame):
                            table.addSeparator()
                        elif isinstance(itemValue.widget(), QWidget):
                            textValue = stripTags(itemValue.widget().property('text'))
                            table.addRow([textLabel, textValue])
                    data.append(table.asText(self.__uiController.tableSettings())+os.linesep)
            elif isinstance(source, QLabel):
                data.append(stripTags(source.text()))

            return data

        @pyqtSlot('QString')
        def copyAllTabs(action):
            QApplication.clipboard().setText('\n'.join(copyToClipboard()))

        @pyqtSlot('QString')
        def copyCurrentTab(action):
            QApplication.clipboard().setText('\n'.join(copyToClipboard(index)))

        @pyqtSlot('QString')
        def copyItem(action):
            QApplication.clipboard().setText('\n'.join(copyToClipboard(currentItem)))

        @pyqtSlot('QString')
        def setBorderNone(action):
            self.__uiController.commandInfoToClipBoardBorder(BCTableSettingsText.BORDER_NONE)

        @pyqtSlot('QString')
        def setBorderBasic(action):
            self.__uiController.commandInfoToClipBoardBorder(BCTableSettingsText.BORDER_BASIC)

        @pyqtSlot('QString')
        def setBorderSimple(action):
            self.__uiController.commandInfoToClipBoardBorder(BCTableSettingsText.BORDER_SIMPLE)

        @pyqtSlot('QString')
        def setBorderDouble(action):
            self.__uiController.commandInfoToClipBoardBorder(BCTableSettingsText.BORDER_DOUBLE)

        @pyqtSlot('QString')
        def setHeader(action):
            self.__uiController.commandInfoToClipBoardHeader(cbOptHeader.isChecked())

        @pyqtSlot('QString')
        def setMinWidthActive(action):
            self.__uiController.commandInfoToClipBoardMinWidthActive(cbOptMinWidthActive.isChecked())
            slOptWidthMin.setEnabled(cbOptMinWidthActive.isChecked())

        @pyqtSlot('QString')
        def setMinWidth(value):
            self.__uiController.commandInfoToClipBoardMinWidth(value)
            cbOptMinWidthActive.setText(f"Minimum width ({value})")
            if value > self.__uiController.tableSettings().maxWidth():
                slOptWidthMax.slider().setValue(value)

        @pyqtSlot('QString')
        def setMaxWidthActive(action):
            self.__uiController.commandInfoToClipBoardMaxWidthActive(cbOptMaxWidthActive.isChecked())
            slOptWidthMax.setEnabled(cbOptMaxWidthActive.isChecked())

        @pyqtSlot('QString')
        def setMaxWidth(value):
            self.__uiController.commandInfoToClipBoardMaxWidth(value)
            cbOptMaxWidthActive.setText(f"Maximum width ({value})")
            if value < self.__uiController.tableSettings().minWidth():
                slOptWidthMin.slider().setValue(value)


        # current tab index
        index=self.twInfo.currentIndex()

        actionCopyAll = QAction(QIcon(":/images/tabs"), i18n('All tabs'), self)
        actionCopyAll.triggered.connect(copyAllTabs)

        actionCopyCurrent = QAction(self.twInfo.tabIcon(index), i18n(f'Current "{stripTags(self.twInfo.tabText(index))}" tab'), self)
        actionCopyCurrent.triggered.connect(copyCurrentTab)

        currentItem = QApplication.widgetAt(event.globalPos())
        if isinstance(currentItem, QLabel):
            actionCopyItem = QAction(QIcon(":/images/text"), i18n(f'Value "{stripTags(currentItem.text())}"'), self)
            actionCopyItem.triggered.connect(copyItem)
        else:
            currentItem = None

        title = BCWMenuTitle(i18n("Content to clipboard"))

        contextMenu = QMenu(i18n("Content to clipboard"))
        contextMenu.addAction(title)
        contextMenu.addAction(actionCopyAll)
        contextMenu.addAction(actionCopyCurrent)
        if not currentItem is None:
            contextMenu.addAction(actionCopyItem)

        contextMenu.addSeparator()
        optionMenu = contextMenu.addMenu(QIcon(":/images/tune"), i18n('Options'))

        # options menu widgets
        # do not use classic action, but built QWidgetAction with widget insed to avoid
        # context menu being closed after click

        # -- border options
        rbOptBorderNone = QRadioButton(i18n("No border"), optionMenu)
        rbOptBorderBasic = QRadioButton(i18n("Basic border (ascii)"), optionMenu)
        rbOptBorderSimple = QRadioButton(i18n("Simple border (UTF-8)"), optionMenu)
        rbOptBorderDouble = QRadioButton(i18n("Double border (UTF-8)"), optionMenu)

        rbOptBorderNone.clicked.connect(setBorderNone)
        rbOptBorderBasic.clicked.connect(setBorderBasic)
        rbOptBorderSimple.clicked.connect(setBorderSimple)
        rbOptBorderDouble.clicked.connect(setBorderDouble)

        rbOptBorderNoneAction = QWidgetAction(optionMenu)
        rbOptBorderNoneAction.setDefaultWidget(rbOptBorderNone)
        rbOptBorderBasicAction = QWidgetAction(optionMenu)
        rbOptBorderBasicAction.setDefaultWidget(rbOptBorderBasic)
        rbOptBorderSimpleAction = QWidgetAction(optionMenu)
        rbOptBorderSimpleAction.setDefaultWidget(rbOptBorderSimple)
        rbOptBorderDoubleAction = QWidgetAction(optionMenu)
        rbOptBorderDoubleAction.setDefaultWidget(rbOptBorderDouble)

        optionMenu.addAction(rbOptBorderNoneAction)
        optionMenu.addAction(rbOptBorderBasicAction)
        optionMenu.addAction(rbOptBorderSimpleAction)
        optionMenu.addAction(rbOptBorderDoubleAction)

        contextMenuOptBorderGroup = QActionGroup(self)
        contextMenuOptBorderGroup.addAction(rbOptBorderNoneAction)
        contextMenuOptBorderGroup.addAction(rbOptBorderBasicAction)
        contextMenuOptBorderGroup.addAction(rbOptBorderSimpleAction)
        contextMenuOptBorderGroup.addAction(rbOptBorderDoubleAction)

        if self.__uiController.tableSettings().border() == BCTableSettingsText.BORDER_NONE:
            rbOptBorderNone.setChecked(True)
        elif self.__uiController.tableSettings().border() == BCTableSettingsText.BORDER_BASIC:
            rbOptBorderBasic.setChecked(True)
        elif self.__uiController.tableSettings().border() == BCTableSettingsText.BORDER_SIMPLE:
            rbOptBorderSimple.setChecked(True)
        else:
        #elif self.__uiController.tableSettings().border() == BCTableSettingsText.BORDER_DOUBLE:
            rbOptBorderDouble.setChecked(True)

        optionMenu.addSeparator()

        # -- header options
        cbOptHeader = QCheckBox(i18n("Header"), optionMenu)
        cbOptHeader.setChecked(self.__uiController.tableSettings().headerActive())
        cbOptHeader.clicked.connect(setHeader)

        cbOptHeaderAction = QWidgetAction(optionMenu)
        cbOptHeaderAction.setDefaultWidget(cbOptHeader)

        optionMenu.addAction(cbOptHeaderAction)

        optionMenu.addSeparator()

        # -- size options
        value = self.__uiController.tableSettings().minWidth()
        cbOptMinWidthActive = QCheckBox(i18n(f"Minimum width ({value})"), optionMenu)
        cbOptMinWidthActive.setChecked(self.__uiController.tableSettings().minWidthActive())
        cbOptMinWidthActive.clicked.connect(setMinWidthActive)

        cbOptMinWidthActiveAction = QWidgetAction(optionMenu)
        cbOptMinWidthActiveAction.setDefaultWidget(cbOptMinWidthActive)

        optionMenu.addAction(cbOptMinWidthActiveAction)

        slOptWidthMin = BCWMenuSlider(None, optionMenu)
        slOptWidthMin.slider().setMinimum(BCTableSettingsText.MIN_WIDTH)
        slOptWidthMin.slider().setMaximum(BCTableSettingsText.MAX_WIDTH)
        slOptWidthMin.slider().setValue(value)
        slOptWidthMin.slider().setPageStep(10)
        slOptWidthMin.slider().setSingleStep(1)
        slOptWidthMin.slider().valueChanged.connect(setMinWidth)
        slOptWidthMin.setEnabled(cbOptMinWidthActive.isChecked())
        optionMenu.addAction(slOptWidthMin)


        value = self.__uiController.tableSettings().maxWidth()
        cbOptMaxWidthActive = QCheckBox(i18n(f"Maximum width ({value})"), optionMenu)
        cbOptMaxWidthActive.setChecked(self.__uiController.tableSettings().maxWidthActive())
        cbOptMaxWidthActive.clicked.connect(setMaxWidthActive)

        cbOptMaxWidthActiveAction = QWidgetAction(optionMenu)
        cbOptMaxWidthActiveAction.setDefaultWidget(cbOptMaxWidthActive)

        optionMenu.addAction(cbOptMaxWidthActiveAction)

        slOptWidthMax = BCWMenuSlider(None, optionMenu)
        slOptWidthMax.slider().setMinimum(BCTableSettingsText.MIN_WIDTH)
        slOptWidthMax.slider().setMaximum(BCTableSettingsText.MAX_WIDTH)
        slOptWidthMax.slider().setValue(value)
        slOptWidthMax.slider().setPageStep(10)
        slOptWidthMax.slider().setSingleStep(1)
        slOptWidthMax.slider().valueChanged.connect(setMaxWidth)
        slOptWidthMax.setEnabled(cbOptMaxWidthActive.isChecked())
        optionMenu.addAction(slOptWidthMax)

        contextMenu.exec_(event.globalPos())


    def __filesContextMenuDirectoryTree(self, event):
        """Display context menu for directory tree"""

        def expandAll(action):
            def expand(item):
                # item = QModelIndex
                if not item.isValid():
                    return

                model = item.model()
                childCount = model.rowCount(item)
                for index in range(childCount):
                    expand(model.index(index, 0, item))

                if not self.tvDirectoryTree.isExpanded(item):
                    self.tvDirectoryTree.expand(item)
            expand(self.tvDirectoryTree.currentIndex())

        def collapseAll(action):
            def collapse(item, current=True):
                # item = QModelIndex
                if not item.isValid():
                    return

                model = item.model()
                childCount = model.rowCount(item)
                for index in range(childCount):
                    collapse(model.index(index, 0, item))

                if current and self.tvDirectoryTree.isExpanded(item):
                    self.tvDirectoryTree.collapse(item)

            collapse(self.tvDirectoryTree.currentIndex(), False)

        actionExpandAll = QAction(QIcon(":/images/tree_expand"), i18n('Expand all subdirectories'), self)
        actionExpandAll.triggered.connect(expandAll)

        actionCollapseAll = QAction(QIcon(":/images/tree_collapse"), i18n('Collapse all subdirectories'), self)
        actionCollapseAll.triggered.connect(collapseAll)

        # current tab index
        contextMenu = QMenu()
        contextMenu.addAction(actionExpandAll)
        contextMenu.addAction(actionCollapseAll)

        contextMenu.exec_(event.globalPos())


    def __filesEnableWatchList(self, enabled):
        """Allow to enable/disable current watch list"""
        # TODO: need to check, but not used....
        if not enabled:
            # disable current watch

            # keep in memory current watched directories
            self.__filesFsWatcherTmpList=self.__filesFsWatcher.directories()
            if len(self.__filesFsWatcherTmpList) > 0:
                self.__filesFsWatcher.removePaths(self.__filesFsWatcherTmpList)
        else:
            # enable watch list
            if len(self.__filesFsWatcherTmpList) > 0:
                for path in self.__filesFsWatcherTmpList:
                    self.__filesFsWatcher.addPath(path)


    # -- PRIVATE CLIPBOARD -----------------------------------------------------

    def __clipboardHidePreview(self, msg=None):
        """Hide preview and display message"""
        if msg is None:
            self.lblClipboardNoPreview.setText("No image selected")
        elif isinstance(msg, str):
            self.lblClipboardNoPreview.setText(msg)
        else:
            self.lblClipboardNoPreview.setPixmap(msg)

        self.swClipboardPreview.setCurrentIndex(1)


    def __clipboardShowPreview(self, img=None):
        """Hide preview and display message"""
        self.swClipboardPreview.setCurrentIndex(0)
        self.gvClipboardPreview.setImage(img)
        self.lblClipboardNoPreview.setText("...")


    def __clipboardSelectionChanged(self, selection=None):
        """Made update according to current selection"""
        self.__clipboardSelected = self.treeViewClipboard.selectedItems()
        self.__clipboardSelectedNbTotal=len(self.__clipboardSelected)
        self.__clipboardSelectedNbUrl=0
        self.__clipboardSelectedNbFiles=0
        self.__clipboardSelectedNbImagesRaster=0
        self.__clipboardSelectedNbImagesSvg=0
        self.__clipboardSelectedNbImagesKraNode=0
        self.__clipboardSelectedNbImagesKraSelection=0
        self.__clipboardSelectedNbPersistent=0
        self.__clipboardSelectedNbUrlDownloaded=0
        self.__clipboardSelectedNbUrlDownloading=0
        self.__clipboardSelectedNbUrlNotDownloaded=0

        for item in self.__clipboardSelected:
            if item.persistent():
                self.__clipboardSelectedNbPersistent+=1

            if item.type() == 'BCClipboardItemUrl':
                self.__clipboardSelectedNbUrl+=1
                if item.urlStatus()==BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED:
                    self.__clipboardSelectedNbUrlNotDownloaded+=1
                elif item.urlStatus()==BCClipboardItemUrl.URL_STATUS_DOWNLOADED:
                    self.__clipboardSelectedNbUrlDownloaded+=1
                if item.urlStatus()==BCClipboardItemUrl.URL_STATUS_DOWNLOADING:
                    self.__clipboardSelectedNbUrlDownloading+=1
            elif item.type() == 'BCClipboardItemFile':
                self.__clipboardSelectedNbFiles+=1
            elif item.type() == 'BCClipboardItemImg':
                self.__clipboardSelectedNbImagesRaster+=1
            elif item.type() == 'BCClipboardItemSvg':
                self.__clipboardSelectedNbImagesSvg+=1
            elif item.type() == 'BCClipboardItemKra':
                if item.origin()=='application/x-krita-node':
                    self.__clipboardSelectedNbImagesKraNode+=1
                elif item.origin()=='application/x-krita-selection':
                    self.__clipboardSelectedNbImagesKraSelection+=1

        self.__clipboardUpdateStats()
        if not self.__uiController is None:
            self.__uiController.updateMenuForPanel()

        if self.__clipboardSelectedNbTotal == 1:
            # ------------------------------ File ------------------------------
            item = self.__clipboardSelected[0]

            if item.type() == 'BCClipboardItemUrl':
                if item.urlStatus()==BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED:
                    self.__clipboardHidePreview("Image not yet downloaded")
                    return
                elif item.urlStatus()==BCClipboardItemUrl.URL_STATUS_DOWNLOADING:
                    self.__clipboardHidePreview("Image currently downloading")
                    return

            if item.file():
                self.__clipboardShowPreview(item.file().image())
                if not self.gvClipboardPreview.hasImage():
                    self.__clipboardHidePreview("Unable to read image")
            else:
                self.__clipboardHidePreview("Unable to read image")
        else:
            # image
            if self.__clipboardSelectedNbTotal>1:
                self.__clipboardHidePreview("No preview for multiple selection")
            else:
                self.__clipboardHidePreview("Nothing selected")


    def __clipboardUpdateStats(self):
        """Update current status bar with clipboard statistics"""
        statusText = []
        text = []

        if not self.__uiController or self.__uiController.clipboard().length()==0:
            text.append("There's nothing in clipboard that can be managed here")
            statusText.append("Clipboard content can't be analyzed/used by clipboard manager")
        else:
            text.append(f"{self.__clipboardSelectedNbTotal} out of {self.__uiController.clipboard().length()}")

            if self.__clipboardSelectedNbPersistent>0:
                text.append(f"Persistent: {self.__clipboardSelectedNbPersistent}")

            if self.__clipboardSelectedNbUrlDownloading>0:
                text.append(f"Downloading: {self.__clipboardSelectedNbUrlDownloading}")

        self.lblClipboardNfo.setText(', '.join(text))
        self.lblClipboardNfo.setStatusTip(', '.join(statusText))


    def __clipboardRefreshTabLayout(self):
        """Refresh layout according to current configuration"""
        if self.__clipboardTabLayout == BCMainViewTabClipboardLayout.TOP:
            self.splitterClipboard.setOrientation(Qt.Vertical)
            self.splitterClipboard.insertWidget(0, self.treeViewClipboard)

            self.__actionClipboardApplyTabLayoutTop.setChecked(True)
            self.__actionClipboardApplyTabLayoutLeft.setChecked(False)
            self.__actionClipboardApplyTabLayoutBottom.setChecked(False)
            self.__actionClipboardApplyTabLayoutRight.setChecked(False)

        elif self.__clipboardTabLayout == BCMainViewTabClipboardLayout.LEFT:
            self.splitterClipboard.setOrientation(Qt.Horizontal)
            self.splitterClipboard.insertWidget(0, self.treeViewClipboard)

            self.__actionClipboardApplyTabLayoutTop.setChecked(False)
            self.__actionClipboardApplyTabLayoutLeft.setChecked(True)
            self.__actionClipboardApplyTabLayoutBottom.setChecked(False)
            self.__actionClipboardApplyTabLayoutRight.setChecked(False)

        elif self.__clipboardTabLayout == BCMainViewTabClipboardLayout.BOTTOM:
            self.splitterClipboard.setOrientation(Qt.Vertical)
            self.splitterClipboard.insertWidget(1, self.treeViewClipboard)

            self.__actionClipboardApplyTabLayoutTop.setChecked(False)
            self.__actionClipboardApplyTabLayoutLeft.setChecked(False)
            self.__actionClipboardApplyTabLayoutBottom.setChecked(True)
            self.__actionClipboardApplyTabLayoutRight.setChecked(False)

        elif self.__clipboardTabLayout == BCMainViewTabClipboardLayout.RIGHT:
            self.splitterClipboard.setOrientation(Qt.Horizontal)
            self.splitterClipboard.insertWidget(1, self.treeViewClipboard)

            self.__actionClipboardApplyTabLayoutTop.setChecked(False)
            self.__actionClipboardApplyTabLayoutLeft.setChecked(False)
            self.__actionClipboardApplyTabLayoutBottom.setChecked(False)
            self.__actionClipboardApplyTabLayoutRight.setChecked(True)

        self.tabClipboardLayoutChanged.emit(self)


    # -- PUBLIC GLOBAL ---------------------------------------------------------


    def setVisible(self, value):
        super(BCMainViewTab, self).setVisible(value)
        self.setAllowRefresh(value)


    def close(self):
        """When window is about to be closed, execute some cleanup/backup/stuff before exiting BuliCommander"""
        # will stop thumbnail generation
        self.treeViewFiles.beginUpdate()
        # clear all content
        self.treeViewFiles.clear()
        self.treeViewFiles.endUpdate()
        super(BCMainViewTab, self).close()


    def refresh(self, resetQuery=True):
        """Update current file list"""
        if not self.__filesAllowRefresh:
            self.__filesBlockedRefresh+=1
            return

        if resetQuery:
            self.__filesQuery = None

        self.__filesRefresh(None)


    def refreshFilter(self, filter=None):
        """Refresh current filter"""
        if filter==None:
            filter=self.filesFilter()
        self.__filesApplyFilter(filter)


    def allowRefresh(self):
        """Return current status for refresh, if allowed or not"""
        return self.__filesAllowRefresh


    def setAllowRefresh(self, value):
        """Define if refreshing is allowed or not

        By default, refresh is allowed
        But when multiple options are modified (show/hide hidden files, file perimeter, ...) rather
        than recalculating file content systematically, it's simpler to deactivate refresh, do stuff,
        and reactivate it.

        When reactivated, a refresh is applied automatically if some have been blocked
        """
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")


        if self.__filesAllowRefresh == value:
            # does nothing in is case
            return

        self.__filesAllowRefresh = value

        if self.__filesAllowRefresh and self.__filesBlockedRefresh > 0:
            self.refresh()


    def uiController(self):
        """Return uiController"""
        return self.__uiController


    def setUiController(self, uiController):
        """Set uiController"""
        #if not (uiController is None or isinstance(uiController, BCUIController)):
        #    raise EInvalidType('Given `uiController` must be a <BCUIController>')
        self.__uiController = uiController
        self.framePathBar.setUiController(uiController)

        self.treeViewClipboard.setClipboard(self.__uiController.clipboard())
        self.treeViewClipboard.selectionModel().selectionChanged.connect(self.__clipboardSelectionChanged)
        self.__uiController.clipboard().updated.connect(self.__clipboardSelectionChanged)
        self.__clipboardUpdateStats()


    def isHighlighted(self):
        """Return True is panel is highlighted, otherwise False"""
        return self.__isHighlighted


    def setHighlighted(self, value):
        """Set current highlighted panel status

        If highlighted status is changed, emit Signal
        """
        Debug.print('[BCMainViewTab.setHighlighted] current: {0} / new: {1} // {2}', self.__isHighlighted, value, self.filesPath())

        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
        elif self.__isHighlighted != value:
            self.__isHighlighted = value
            self.__refreshPanelHighlighted()


    def tabIndex(self, id):
        """Return tab (index, objectName) from given id"""
        if isinstance(id, str):
            id = BCMainViewTabTabs(id)

        if not isinstance(id, BCMainViewTabTabs):
            raise EInvalidType('Given `id` must be a BCMainViewTabTabs')

        for index in range(self.tabMain.count()):
            if self.tabMain.widget(index).objectName() == 'tabFiles' and id == BCMainViewTabTabs.FILES:
                return (index, 'tabFiles')
            elif self.tabMain.widget(index).objectName() == 'tabDocuments' and id == BCMainViewTabTabs.DOCUMENTS:
                return (index, 'tabDocuments')
            elif self.tabMain.widget(index).objectName() == 'tabClipboard' and id == BCMainViewTabTabs.CLIPBOARD:
                return (index, 'tabClipboard')

        return (-1, '')


    def tabActive(self):
        """Return current active tab"""
        if self.tabMain.currentWidget().objectName() == 'tabFiles':
            return BCMainViewTabTabs.FILES
        elif self.tabMain.currentWidget().objectName() == 'tabDocuments':
            return BCMainViewTabTabs.DOCUMENTS
        else:
            return BCMainViewTabTabs.CLIPBOARD


    def setTabActive(self, id):
        """Set current active tab"""
        index, name = self.tabIndex(id)

        if index > -1:
            self.tabMain.setCurrentIndex(index)


    def tabOrder(self):
        """Return list of tab, with current applied order"""
        returned = []
        for index in range(self.tabMain.count()):
            if self.tabMain.widget(index).objectName() == 'tabFiles':
                returned.append(BCMainViewTabTabs.FILES)
            elif self.tabMain.widget(index).objectName() == 'tabDocuments':
                returned.append(BCMainViewTabTabs.DOCUMENTS)
            elif self.tabMain.widget(index).objectName() == 'tabClipboard':
                returned.append(BCMainViewTabTabs.CLIPBOARD)
        return returned


    def setTabOrder(self, tabs):
        """Set tab order"""
        if not isinstance(tabs, list):
            raise EInvalidType('Given `tabs` must be a list')
        if len(tabs) != self.tabMain.count():
            raise EInvalidType('Given `tabs` list must have the same number of item than panel tab')

        for tabIndex in range(len(tabs)):
            index, name = self.tabIndex(tabs[tabIndex])
            if index != tabIndex:
                self.tabMain.tabBar().moveTab(index, tabIndex)


    def targetDirectoryReady(self):
        """return true if current panel can be a target for file operation (copy,
        move, ...)
        """
        print('TODO: targetDirectoryReady Need to implement rule')
        return True


    def previewBackground(self):
        """Return current background for preview"""
        # TODO: do it for clipboard
        return self.gvFilesPreview.backgroundType()


    def setPreviewBackground(self, value):
        """Set current background for preview"""
        # TODO: do it for clipboard
        self.gvFilesPreview.setBackgroundType(value)


    def updateFileSizeUnit(self):
        """Update widget if file size unit has been modified"""
        self.treeViewFiles.updateFileSizeUnit()
        self.__filesSelectionChanged(None)


    def selectAll(self):
        """Select all items in current tab"""
        if self.tabActive()==BCMainViewTabTabs.FILES:
            self.treeViewFiles.selectAll()
        elif self.tabActive()==BCMainViewTabTabs.CLIPBOARD:
            self.treeViewClipboard.selectAll()


    def selectNone(self):
        """Unselect all items in current tab"""
        if self.tabActive()==BCMainViewTabTabs.FILES:
            self.treeViewFiles.clearSelection()
        elif self.tabActive()==BCMainViewTabTabs.CLIPBOARD:
            self.treeViewClipboard.clearSelection()


    def selectInvert(self):
        """Invert selection all items in current tab"""
        if self.tabActive()==BCMainViewTabTabs.FILES:
            self.treeViewFiles.invertSelection()
        elif self.tabActive()==BCMainViewTabTabs.CLIPBOARD:
            self.treeViewClipboard.invertSelection()


    # -- PUBLIC FILES ----------------------------------------------------------

    def filesCurrentAnimatedFrame(self):
        """Return current animated frame number"""
        return self.__filesCurrentAnimatedFrame


    def setFilesCurrentAnimatedFrame(self, value):
        """set current animated frame number"""
        if value > 0 and value <= self.__filesMaxAnimatedFrame and value!=self.__filesCurrentAnimatedFrame:
            self.__filesCurrentAnimatedFrame = value
            self.hsAnimatedFrameNumber.setValue(self.__filesCurrentAnimatedFrame)


    def filesGotoNextAnimatedFrame(self, loop=True):
        """go to next animated frame number

        if last frame is reached, according to `loop` value:
            - if True, go to first frame
            - if False, stop
        """
        if self.__filesCurrentAnimatedFrame < self.__filesMaxAnimatedFrame:
            self.__filesCurrentAnimatedFrame+=1
        elif loop:
            self.__filesCurrentAnimatedFrame = 1
        else:
            return
        self.hsAnimatedFrameNumber.setValue(self.__filesCurrentAnimatedFrame)


    def filesGotoPrevAnimatedFrame(self, loop=True):
        """go to previous animated frame number

        if first frame is reached, according to `loop` value:
            - if True, go to first frame
            - if False, stop
        """
        if self.__filesCurrentAnimatedFrame > 1:
            self.__filesCurrentAnimatedFrame-=1
        elif loop:
            self.__filesCurrentAnimatedFrame = self.__filesMaxAnimatedFrame
        else:
            return
        self.hsAnimatedFrameNumber.setValue(self.__filesCurrentAnimatedFrame)


    def filesTabLayout(self):
        """return current layout for file panel"""
        return self.__filesTabLayout


    def setFilesTabLayout(self, layout):
        """Set new layout for file panel"""
        if layout is None:
            return
        if isinstance(layout, str):
            layout = BCMainViewTabFilesLayout(layout)
        elif not isinstance(layout, BCMainViewTabFilesLayout):
            raise EInvalidType("Given `layout` must be a <BCMainViewTabFilesLayout>")

        if self.__filesTabLayout != layout:
            self.__filesTabLayout = layout
            self.__filesRefreshTabLayout()


    def filesTabIndex(self, id):
        """Return tab (index, objectName) from given id"""
        if isinstance(id, str):
            id = BCMainViewTabFilesTabs(id)

        if not isinstance(id, BCMainViewTabFilesTabs):
            raise EInvalidType('Given `id` must be a BCMainViewTabFilesTabs')

        for index in range(self.tabFilesDetails.count()):
            if self.tabFilesDetails.widget(index).objectName() == 'tabFilesDetailsInformations' and id == BCMainViewTabFilesTabs.INFORMATIONS:
                return (index, 'tabFilesDetailsInformations')
            elif self.tabFilesDetails.widget(index).objectName() == 'tabFilesDetailsDirTree' and id == BCMainViewTabFilesTabs.DIRECTORIES_TREE:
                return (index, 'tabFilesDetailsDirTree')

        return (-1, '')


    def filesTabActive(self):
        """Return current active tab into tab files"""
        if self.tabFilesDetails.currentWidget().objectName() == 'tabFilesDetailsInformations':
            return BCMainViewTabFilesTabs.INFORMATIONS
        else:
            return BCMainViewTabFilesTabs.DIRECTORIES_TREE


    def setFilesTabActive(self, id):
        """Set current active tab into tab files"""
        index, name = self.filesTabIndex(id)

        if index > -1:
            self.tabFilesDetails.setCurrentIndex(index)


    def filesTabOrder(self):
        """Return list of tab, with current applied order"""
        returned = []
        for index in range(self.tabFilesDetails.count()):
            if self.tabFilesDetails.widget(index).objectName() == 'tabFilesDetailsInformations':
                returned.append(BCMainViewTabFilesTabs.INFORMATIONS)
            elif self.tabFilesDetails.widget(index).objectName() == 'tabFilesDetailsDirTree':
                returned.append(BCMainViewTabFilesTabs.DIRECTORIES_TREE)
        return returned


    def setFilesTabOrder(self, tabs):
        """Set tab order"""
        if not isinstance(tabs, list):
            raise EInvalidType('Given `tabs` must be a list')
        if len(tabs) != self.tabFilesDetails.count():
            raise EInvalidType('Given `tabs` list must have the same number of item than panel tab')

        for tabIndex in range(len(tabs)):
            index, name = self.filesTabIndex(tabs[tabIndex])
            if index != tabIndex:
                self.tabFilesDetails.tabBar().moveTab(index, tabIndex)


    def filesTabNfoIndex(self, id):
        """Return tab (index, objectName) from given id"""
        if isinstance(id, str):
            id = BCMainViewTabFilesNfoTabs(id)

        if not isinstance(id, BCMainViewTabFilesNfoTabs):
            raise EInvalidType('Given `id` must be a BCMainViewTabFilesNfoTabs')

        for index in range(self.twInfo.count()):
            if self.twInfo.widget(index).objectName() == 'pageFileNfoGeneric' and id == BCMainViewTabFilesNfoTabs.GENERIC:
                return (index, 'pageFileNfoGeneric')
            elif self.twInfo.widget(index).objectName() == 'pageFileNfoImage' and id == BCMainViewTabFilesNfoTabs.IMAGE:
                return (index, 'pageFileNfoImage')
            elif self.twInfo.widget(index).objectName() == 'pageFileNfoKra' and id == BCMainViewTabFilesNfoTabs.KRA:
                return (index, 'pageFileNfoKra')

        return (-1, '')


    def filesTabNfoActive(self):
        """Return current active nfo tab into tab files"""
        if self.twInfo.currentWidget().objectName() == 'pageFileNfoGeneric':
            return BCMainViewTabFilesNfoTabs.GENERIC
        elif self.twInfo.currentWidget().objectName() == 'pageFileNfoImage':
            return BCMainViewTabFilesNfoTabs.IMAGE
        else:
            return BCMainViewTabFilesNfoTabs.KRA


    def setFilesTabNfoActive(self, id):
        """Set current active tab into tab files"""
        index, name = self.filesTabNfoIndex(id)

        if index > -1:
            self.twInfo.setCurrentIndex(index)


    def filesTabSplitterFilesPosition(self):
        """Return splitter position for tab files"""
        return self.splitterFiles.sizes()


    def setFilesTabSplitterFilesPosition(self, positions=None):
        """Set splitter position for tab files"""
        if positions is None:
            positions = [1000, 1000]

        if not isinstance(positions, list) or len(positions) != 2:
            raise EInvalidValue('Given `positions` must be a list [l,r]')

        self.splitterFiles.setSizes(positions)

        return self.splitterFiles.sizes()


    def filesTabSplitterPreviewPosition(self):
        """Return splitter position for tab preview"""
        return self.splitterPreview.sizes()


    def setFilesTabSplitterPreviewPosition(self, positions=None):
        """Set splitter position for tab preview"""
        if positions is None:
            positions = [1000, 1000]

        if not isinstance(positions, list) or len(positions) != 2:
            raise EInvalidValue('Given `positions` must be a list [l,r]')

        self.splitterPreview.setSizes(positions)

        return self.splitterPreview.sizes()


    def filesPath(self):
        """Return current path"""
        return self.framePathBar.path()


    def setFilesPath(self, path=None):
        """Set current path"""
        Debug.print('[BCMainViewTab.setPath] path: {0}', path)
        return self.framePathBar.setPath(path)


    def filesGoToBackPath(self):
        """Go to previous path"""
        return self.framePathBar.goToBackPath()


    def filesGoBackEnabled(self):
        """Return True if go back is possible"""
        return self.framePathBar.goBackEnabled()


    def filesGoToUpPath(self):
        """Go to previous path"""
        return self.framePathBar.goToUpPath()


    def filesGoUpEnabled(self):
        """Return True if go up is possible"""
        return self.framePathBar.goUpEnabled()


    def filesHistory(self):
        """return history object"""
        return self.framePathBar.history()


    def setFilesHistory(self, value):
        """Set history object"""
        self.framePathBar.setHistory(value)


    def filesBookmark(self):
        """return bookmark object"""
        return self.framePathBar.bookmark()


    def setFilesBookmark(self, value):
        """Set bookmark object"""
        self.framePathBar.setBookmark(value)


    def filesSavedView(self):
        """return saved view object"""
        return self.framePathBar.savedView()


    def setFilesSavedView(self, value):
        """Set saved view object"""
        self.framePathBar.setSavedView(value)


    def filesLastDocumentsOpened(self):
        """return last opened documents view object"""
        return self.framePathBar.lastDocumentsOpened()


    def setFilesLastDocumentsOpened(self, value):
        """Set last opened documents view object"""
        self.framePathBar.setLastDocumentsOpened(value)


    def filesLastDocumentsSaved(self):
        """return last saved documents view object"""
        return self.framePathBar.lastDocumentsSaved()


    def setFilesLastDocumentsSaved(self, value):
        """Set last saved documents view object"""
        self.framePathBar.setLastDocumentsSaved(value)


    def filesBackupFilterDView(self):
        """set last backup dynamic view object"""
        return self.framePathBar.backupFilterDView()


    def setFilesBackupFilterDView(self, value):
        """Set last backup dynamic view object"""
        self.framePathBar.setBackupFilterDView(value)


    def filesLayerFilterDView(self):
        """set file layer dynamic view object"""
        return self.framePathBar.fileLayerFilterDView()


    def setFilesLayerFilterDView(self, value):
        """Set file layer dynamic view object"""
        self.framePathBar.setFileLayerFilterDView(value)


    def filesFilterVisible(self):
        """Return if filter is visible or not"""
        return self.framePathBar.filterVisible()


    def setFilesFilterVisible(self, visible=None):
        """Display the filter

        If visible is None, invert current status
        If True, display filter
        If False, hide
        """
        self.framePathBar.setFilterVisible(visible)


    def filesFilter(self):
        """Return current filter value"""
        return self.framePathBar.filter()


    def setFilesFilter(self, value=None):
        """Set current filter value"""
        self.framePathBar.setFilter(value)


    def filesHiddenPath(self):
        """Return if hidden path are displayed or not"""
        return self.framePathBar.hiddenPath()


    def setFilesHiddenPath(self, value=False):
        """Set if hidden path are displayed or not"""
        if value:
            self.__filesDirTreeModel.setFilter(QDir.AllDirs|QDir.Drives|QDir.NoSymLinks|QDir.NoDotAndDotDot|QDir.Hidden)
        else:
            self.__filesDirTreeModel.setFilter(QDir.AllDirs|QDir.Drives|QDir.NoSymLinks|QDir.NoDotAndDotDot)

        self.framePathBar.setHiddenPath(value)
        self.refresh()


    def filesSelectAll(self):
        """Select all items"""
        self.treeViewFiles.selectAll()


    def filesSelectNone(self):
        """Unselect all items"""
        self.treeViewFiles.clearSelection()


    def filesSelectInvert(self):
        """Invert selection all items"""
        self.treeViewFiles.invertSelection()


    def filesColumnSort(self):
        """Return current column sort status"""
        index = self.treeViewFiles.header().sortIndicatorSection()
        if index is None:
            index = BCMainViewFiles.COLNUM_NAME
        return [index ,(self.treeViewFiles.header().sortIndicatorOrder() == Qt.AscendingOrder)]


    def setFilesColumnSort(self, value):
        """Set current column sort status

        Given `value` is a list or a tuple(int, bool):
         - column index (int, 0 to 6)
         - ascending sort (bool)
        """
        if not (isinstance(value, list) or isinstance(value, tuple)) or len(value) != 2:
            raise EInvalidType('Given `value` must be a valid <list> or <tuple>')

        if not isinstance(value[0], int):
            raise EInvalidType('Given `value[column]` must be <int>')

        if not isinstance(value[1], bool):
            raise EInvalidType('Given `value[column]` must be <bool>')

        if value[0] < 0 or value[0] > 6:
            raise EInvalidValue('Given `value[column]` must be a valid column number')

        if value[1]:
            self.treeViewFiles.header().setSortIndicator(value[0], Qt.AscendingOrder)
        else:
            self.treeViewFiles.header().setSortIndicator(value[0], Qt.DescendingOrder)


    def filesColumnOrder(self):
        """Return current column order status

        Array index represent visual index
        Array value represent logical index
        """
        return [self.treeViewFiles.header().logicalIndex(index) for index in range(self.treeViewFiles.header().count())]


    def setFilesColumnOrder(self, value):
        """Set current column order

        Given `value` is a list or logical index
        Index in list provide position in header
        """
        if not (isinstance(value, list) or isinstance(value, tuple)) or len(value) > self.treeViewFiles.header().count():
            raise EInvalidType('Given `value` must be a valid <list> or <tuple>')

        for columnTo, logicalIndex in enumerate(value):
            columnFrom = self.treeViewFiles.header().visualIndex(logicalIndex)
            self.treeViewFiles.header().moveSection(columnFrom, columnTo)


    def filesColumnSize(self):
        """Return current column size status"""
        return [self.treeViewFiles.header().sectionSize(index) for index in range(self.treeViewFiles.header().count())]


    def setFilesColumnSize(self, value):
        """Set current column size

        Given `value` is a list or logical index
        Index in list provide position in header
        """
        if value is None:
            self.treeViewFiles.resizeColumns(False)
            return

        if not (isinstance(value, list) or isinstance(value, tuple)) or len(value) > self.treeViewFiles.header().count():
            raise EInvalidType('Given `value` must be a valid <list> or <tuple>')

        for logicalIndex, size in enumerate(value):
            if size == 0:
                self.treeViewFiles.resizeColumnToContents(logicalIndex)
            else:
                self.treeViewFiles.header().resizeSection(logicalIndex, size)


    def filesIconSize(self):
        """Return current icon size"""
        return self.treeViewFiles.iconSizeIndex()


    def setFilesIconSize(self, value=None):
        """Set current icon size"""
        self.treeViewFiles.setIconSizeIndex(value)
        self.__actionFilesApplyIconSize.slider().setValue(value)


    def filesViewThumbnail(self):
        """Return if current view display thumbnails"""
        return self.treeViewFiles.viewThumbnail()


    def setFilesViewThumbnail(self, value=None):
        """Set current view with thumbnail or not"""
        self.treeViewFiles.setViewThumbnail(value)


    def filesSelected(self):
        """Return information about selected files

        Information is provided as a tuple:
        [0] list of BCBaseFile
        [1] nb directories
        [2] nb files
        [3] nb directories + files
        [4] nb readable
        [5] list of BCFiles
        [6] size of files
        """
        return (self.__filesSelected,
                self.__filesSelectedNbDir,
                self.__filesSelectedNbFile,
                self.__filesSelectedNbTotal,
                self.__filesSelectedNbReadable,
                self.__filesSelected,
                self.__filesCurrentStats['sizeSelectedFiles'])


    def files(self):
        """Return information about files (filtered applied)

        Information is provided as a tuple:
        [0] list of BCBaseFile
        [1] nb directories
        [2] nb files
        [3] nb directories + files
        [4] nb readable
        [5] list of BCFiles
        [6] size of files
        """
        files = self.treeViewFiles.files()
        if self.__filesCurrentStats['nbFilteredTotal'] > 0:
            return (files,
                    self.__filesCurrentStats['nbFilteredDir'],
                    self.__filesCurrentStats['nbFilteredFiles'],
                    self.__filesCurrentStats['nbFilteredTotal'],
                    self.__filesCurrentStats['nbFilteredTotal'],
                    files,
                    self.__filesCurrentStats['sizeFilteredFiles'])
        else:
            return (files,
                    self.__filesCurrentStats['nbDir'],
                    self.__filesCurrentStats['nbFiles'],
                    self.__filesCurrentStats['nbTotal'],
                    self.__filesCurrentStats['nbTotal'],
                    files,
                    self.__filesCurrentStats['sizeFiles'])


    def filesShowBookmark(self, visible=True):
        """Display/Hide the bookmark button"""
        self.framePathBar.showBookmark(visible)


    def filesShowHistory(self, visible=True):
        """Display/Hide the history button"""
        self.framePathBar.showHistory(visible)


    def filesShowLastDocuments(self, visible=True):
        """Display/Hide the last documents button"""
        self.framePathBar.showLastDocuments(visible)


    def filesShowSavedView(self, visible=True):
        """Display/Hide the saved view button"""
        self.framePathBar.showSavedView(visible)


    def filesShowHome(self, visible=True):
        """Display/Hide the home button"""
        self.framePathBar.showHome(visible)


    def filesShowGoUp(self, visible=True):
        """Display/Hide the go up button"""
        self.framePathBar.showGoUp(visible)


    def filesShowGoBack(self, visible=True):
        """Display/Hide the go back button"""
        self.framePathBar.showGoBack(visible)


    def filesShowQuickFilter(self, visible=True):
        """Display/Hide the quickfilter button"""
        self.framePathBar.showQuickFilter(visible)


    def filesShowMargins(self, visible=False):
        """Display/Hide margins"""
        self.framePathBar.showMargins(visible)


    def filesShowMenuHistory(self, menu):
        """Build menu history"""
        self.framePathBar.menuHistoryShow(menu)


    def filesShowMenuBookmarks(self, menu):
        """Build menu bookmarks"""
        self.framePathBar.menuBookmarksShow(menu)


    def filesShowMenuSavedViews(self, menu):
        """Build menu saved views"""
        self.framePathBar.menuSavedViewsShow(menu)


    def filesShowMenuLastDocuments(self, menu):
        """Build menu last documents views"""
        self.framePathBar.menuLastDocumentsShow(menu)

    # -- PUBLIC CLIPBOARD ----------------------------------------------------------

    def clipboardTabLayout(self):
        """return current layout for clipboard panel"""
        return self.__clipboardTabLayout


    def setClipboardTabLayout(self, layout):
        """Set new layout for clipboard panel"""
        if layout is None:
            return
        if isinstance(layout, str):
            layout = BCMainViewTabClipboardLayout(layout)
        elif not isinstance(layout, BCMainViewTabClipboardLayout):
            raise EInvalidType("Given `layout` must be a <BCMainViewTabClipboardLayout>")

        if self.__clipboardTabLayout != layout:
            self.__clipboardTabLayout = layout
            self.__clipboardRefreshTabLayout()


    def clipboardSelectAll(self):
        """Select all items"""
        self.treeViewClipboard.selectAll()


    def clipboardSelectNone(self):
        """Unselect all items"""
        self.treeViewClipboard.clearSelection()


    def clipboardSelectInvert(self):
        """Invert selection all items"""
        self.treeViewClipboard.invertSelection()


    def clipboardTabSplitterPosition(self):
        """Return splitter position for clipboard tab"""
        return self.splitterClipboard.sizes()


    def setClipboardTabSplitterPosition(self, positions=None):
        """Set splitter position for clipboard tab"""
        if positions is None:
            positions = [1000, 1000]

        if not isinstance(positions, list) or len(positions) != 2:
            raise EInvalidValue('Given `positions` must be a list [l,r]')

        self.splitterClipboard.setSizes(positions)

        return self.splitterClipboard.sizes()


    def clipboardColumnSort(self):
        """Return current column sort status"""
        index = self.treeViewClipboard.header().sortIndicatorSection()
        if index is None:
            index = BCClipboardModel.COLNUM_DATE
        return [index, (self.treeViewClipboard.header().sortIndicatorOrder() == Qt.DescendingOrder)]


    def setClipboardColumnSort(self, value):
        """Set current column sort status

        Given `value` is a list or a tuple(int, bool):
         - column index (int, 0 to 6)
         - ascending sort (bool)
        """
        if not (isinstance(value, list) or isinstance(value, tuple)) or len(value) != 2:
            raise EInvalidType('Given `value` must be a valid <list> or <tuple>')

        if not isinstance(value[0], int):
            raise EInvalidType('Given `value[column]` must be <int>')

        if not isinstance(value[1], bool):
            raise EInvalidType('Given `value[column]` must be <bool>')

        if value[0] < 0 or value[0] > 6:
            raise EInvalidValue('Given `value[column]` must be a valid column number')

        if value[1]:
            self.treeViewClipboard.header().setSortIndicator(value[0], Qt.AscendingOrder)
        else:
            self.treeViewClipboard.header().setSortIndicator(value[0], Qt.DescendingOrder)


    def clipboardColumnOrder(self):
        """Return current column order status

        Array index represent visual index
        Array value represent logical index
        """
        return [self.treeViewClipboard.header().logicalIndex(index) for index in range(self.treeViewClipboard.header().count())]


    def setClipboardColumnOrder(self, value):
        """Set current column order

        Given `value` is a list or logical index
        Index in list provide position in header (visual index)
        """
        if not (isinstance(value, list) or isinstance(value, tuple)) or len(value) > self.treeViewClipboard.header().count():
            raise EInvalidType('Given `value` must be a valid <list> or <tuple>')

        for columnTo, logicalIndex in enumerate(value):
            columnFrom = self.treeViewClipboard.header().visualIndex(logicalIndex)
            self.treeViewClipboard.header().moveSection(columnFrom, columnTo)


    def clipboardColumnSize(self):
        """Return current column size status"""
        return [self.treeViewClipboard.header().sectionSize(index) for index in range(self.treeViewClipboard.header().count())]


    def setClipboardColumnSize(self, value):
        """Set current column size

        Given `value` is a list or logical index
        Index in list provide position in header
        """
        if value is None:
            self.treeViewClipboard.resizeColumns(False)
            return

        if not (isinstance(value, list) or isinstance(value, tuple)) or len(value) > self.treeViewClipboard.header().count():
            raise EInvalidType('Given `value` must be a valid <list> or <tuple>')

        for logicalIndex, size in enumerate(value):
            if size == 0:
                self.treeViewClipboard.resizeColumnToContents(logicalIndex)
            else:
                self.treeViewClipboard.header().resizeSection(logicalIndex, size)


    def clipboardIconSize(self):
        """Return current icon size"""
        return self.treeViewClipboard.iconSizeIndex()


    def setClipboardIconSize(self, value=None):
        """Set current icon size"""
        self.treeViewClipboard.setIconSizeIndex(value)
        #self.__actionFilesApplyIconSize.slider().setValue(value)

    def clipboardSelected(self):
        """Return information about selected clipboard items

        Information is provided as a tuple:
        [0] list of BCClipboardItem
        [1] nb selected
        [2] nb url
        [3] nb files
        [4] nb image (raster)
        [5] nb image (svg)
        [6] nb kra-nodes
        [7] nb kra-selection
        [8] nb url downloaded
        [9] nb url not downloaded
        [10] nb url downloading
        [11] nb persistent
        """
        return (self.__clipboardSelected,
                self.__clipboardSelectedNbTotal,
                self.__clipboardSelectedNbUrl,
                self.__clipboardSelectedNbFiles,
                self.__clipboardSelectedNbImagesRaster,
                self.__clipboardSelectedNbImagesSvg,
                self.__clipboardSelectedNbImagesKraNode,
                self.__clipboardSelectedNbImagesKraSelection,
                self.__clipboardSelectedNbUrlDownloaded,
                self.__clipboardSelectedNbUrlNotDownloaded,
                self.__clipboardSelectedNbUrlDownloading,
                self.__clipboardSelectedNbPersistent)
