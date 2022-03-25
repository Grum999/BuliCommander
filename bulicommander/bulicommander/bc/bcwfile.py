#-----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2019-2022 - Grum999
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

import re

from multiprocessing import Pool


from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )

from .bcfile import (
        BCBaseFile,
        BCDirectory,
        BCFile,
        BCFileList,
        BCFileManagedFormat,
        BCFileProperty,
        BCFileThumbnailSize
    )
from .bciconsizes import BCIconSizes

from bulicommander.pktk.modules.workers import (
        WorkerPool,
        Worker
    )
from bulicommander.pktk.modules.imgutils import (
        megaPixels,
        ratioOrientation
    )
from bulicommander.pktk.modules.utils import (
        Debug
    )
from bulicommander.pktk.modules.timeutils import (
        tsToStr
    )
from bulicommander.pktk.modules.strutils import (
        bytesSizeToStr
    )
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )


# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------

class BCFileModel(QAbstractTableModel):
    """A model to manage list of BCFiles for QTreeView/QListView"""
    iconStartLoad = Signal(int)
    iconProcessed = Signal()
    iconStopLoad = Signal()

    # define columns
    COLNUM_ICON = 0
    COLNUM_FILE_PATH = 1
    COLNUM_FILE_NAME = 2

    COLNUM_FILE_BASENAME = 3
    COLNUM_FILE_EXTENSION = 4

    COLNUM_FILE_FORMAT_SHORT = 5
    COLNUM_FILE_FORMAT_LONG = 6

    COLNUM_FILE_DATETIME = 7
    COLNUM_FILE_DATE = 8
    COLNUM_FILE_TIME = 9

    COLNUM_FILE_SIZE = 10

    COLNUM_IMAGE_SIZE = 11
    COLNUM_IMAGE_WIDTH = 12
    COLNUM_IMAGE_HEIGHT = 13

    COLNUM_IMAGE_RATIO = 14
    COLNUM_IMAGE_ORIENTATION = 15

    COLNUM_IMAGE_PIXELS = 16
    COLNUM_IMAGE_PIXELSMP = 17

    COLNUM_FULLNFO = 18
    COLNUM_LAST = 18

    DEFAULT_COLUMN_VISIBILITY=[True,False,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,False]

    ROLE_ICON = Qt.UserRole + 1
    ROLE_FILE = Qt.UserRole + 2
    ROLE_FULLNFO = Qt.UserRole + 3

    __STATUS_READY = 0
    __STATUS_UPDATING = 1

    __STATUS_ICON_LOADED = 0
    __STATUS_ICON_LOADING = 1
    __STATUS_ICON_STOPLOADING = -1

    # headers labels: must be defined in same order than column
    #                 (label value index in list must match with column number)
    HEADERS=['',
             i18n('Path'),
             i18n('Name'),
             i18n('Base name'),
             i18n('Extension'),
             i18n('Format'),
             i18n('Format (Long)'),
             i18n('Date/Time'),
             i18n('Date'),
             i18n('Time'),
             i18n('Size'),
             i18n('Dimension'),
             i18n('Width'),
             i18n('Height'),
             i18n('Ratio W/H'),
             i18n('Orientation'),
             i18n('Pixels'),
             i18n('Pixels (MP)'),
             i18n('File information'),
        ]

    @staticmethod
    def getIcon(itemIndex, file, size=None):
        return file.thumbnail(size=size, thumbType=BCBaseFile.THUMBTYPE_ICON)

    def __init__(self, fileList, parent=None):
        """Initialise list"""
        super(BCFileModel, self).__init__(parent)

        if not isinstance(fileList, BCFileList):
            raise EInvalidType("Given `fileList` must be <BCFileList>")

        self.__iconAsThumbnail=False
        self.__iconSize=BCFileThumbnailSize.SMALL

        self.__updatingIcons = BCFileModel.__STATUS_ICON_LOADED

        self.__fileList=fileList
        self.__fileList.resultsUpdatedReset.connect(self.__dataUpdateReset)
        self.__fileList.resultsUpdatedAdd.connect(self.__dataUpdatedAdd)
        self.__fileList.resultsUpdatedRemove.connect(self.__dataUpdateRemove)
        self.__fileList.resultsUpdatedSort.connect(self.__dataUpdateSort)

        self.__fileNfoCache={}
        self.__icons={}
        self.__items=self.__fileList.files()
        self.__headerRightAlign=(BCFileModel.COLNUM_FILE_SIZE,
                                 BCFileModel.COLNUM_IMAGE_SIZE,
                                 BCFileModel.COLNUM_IMAGE_WIDTH,
                                 BCFileModel.COLNUM_IMAGE_HEIGHT,
                                 BCFileModel.COLNUM_IMAGE_RATIO,
                                 BCFileModel.COLNUM_IMAGE_PIXELS,
                                 BCFileModel.COLNUM_IMAGE_PIXELSMP)

        self.__iconPool = WorkerPool()
        self.__iconPool.signals.started.connect(self.__updateIconsStarted)
        self.__iconPool.signals.processed.connect(self.__updateIconsProcessed)
        self.__iconPool.signals.finished.connect(self.__updateIconsFinished)

        # index = logical index
        self.__columnsVisibility=[v for v in BCFileModel.DEFAULT_COLUMN_VISIBILITY]     # value: visible=True, otherwise False
        self.__columnsPosition=[column for column in range(BCFileModel.COLNUM_LAST+1)]  # value: visual index

        self.__headerMaxCharacters=max([len(v) for v in BCFileModel.HEADERS])

    def __updateIconsProcessed(self, processedNfo):
        """update icon in treeview list"""
        fileIndex, icon, nbProcessed = processedNfo

        if not fileIndex is None and fileIndex < self.rowCount():
            if not icon is None:
                self.setData(fileIndex, icon, Qt.DecorationRole)
                self.iconProcessed.emit()

    def __updateIconsStarted(self):
        """updating icon in treeview list is started"""
        self.iconStartLoad.emit(self.rowCount())

    def __updateIconsFinished(self):
        """updating icon in treeview list is terminated"""
        self.__updatingIcons = BCFileModel.__STATUS_ICON_LOADED
        self.iconStopLoad.emit()

    def __stopUpdatingIcons(self):
        """Stop update icons/thumbnail

        All threads are stopped
        """
        if self.__updatingIcons==BCFileModel.__STATUS_ICON_LOADING:
            # process only if currently loading
            self.__updatingIcons=BCFileModel.__STATUS_ICON_STOPLOADING
            self.__iconPool.stopProcessing()
            self.__iconPool.waitProcessed()
            self.__updatingIcons=BCFileModel.__STATUS_ICON_LOADED

    def __updateIcons(self):
        """Update icons asynchronously"""
        if self.__updatingIcons==BCFileModel.__STATUS_ICON_STOPLOADING:
            # currently stop loading icons, so don't need to update them as
            # an update is already waiting
            return

        self.__stopUpdatingIcons()

        if not self.__iconAsThumbnail:
            self.__updatingIcons = BCFileModel.__STATUS_ICON_LOADED
            self.iconStopLoad.emit()
            return

        self.__updatingIcons=BCFileModel.__STATUS_ICON_LOADING

        self.__iconPool.startProcessing([item for item in self.__items], BCFileModel.getIcon, self.__iconSize)

    def __dataUpdateReset(self):
        """Data has entirely been changed (reset/reload)"""
        self.__stopUpdatingIcons()
        self.beginResetModel()
        self.__fileNfoCache={}
        self.__icons={}
        self.__items=self.__fileList.files()
        self.endResetModel()
        self.__updateIcons()

    def __dataUpdateSort(self):
        """Data has been sorted"""
        self.__stopUpdatingIcons()
        self.beginResetModel()
        self.__items=self.__fileList.files()
        self.endResetModel()
        self.__updateIcons()

    def __dataUpdatedAdd(self, items):
        """Add a new file to model"""
        self.modelReset.emit()

    def __dataUpdateRemove(self, items):
        """Remove file from model"""
        self.modelReset.emit()

    def __getValueForColumn(self, file, column):
        """Return value of file for given role"""
        if column==BCFileModel.COLNUM_FILE_PATH:
            return file.path()
        elif column==BCFileModel.COLNUM_FILE_NAME:
            return file.name()
        elif column==BCFileModel.COLNUM_FILE_BASENAME:
            return file.baseName()
        elif column==BCFileModel.COLNUM_FILE_EXTENSION:
            if not isinstance(file, BCDirectory):
                return file.extension(False)
        elif column==BCFileModel.COLNUM_FILE_FORMAT_SHORT:
            return BCFileManagedFormat.translate(file.format(), True)
        elif column==BCFileModel.COLNUM_FILE_FORMAT_LONG:
            return BCFileManagedFormat.translate(file.format(), False)
        elif column==BCFileModel.COLNUM_FILE_DATETIME:
            if not (isinstance(file, BCDirectory) and file.name()=='..'):
                return tsToStr(file.lastModificationDateTime())
        elif column==BCFileModel.COLNUM_FILE_DATE:
            if not (isinstance(file, BCDirectory) and file.name()=='..'):
                return tsToStr(file.lastModificationDateTime(), 'd')
        elif column==BCFileModel.COLNUM_FILE_TIME:
            if not (isinstance(file, BCDirectory) and file.name()=='..'):
                return tsToStr(file.lastModificationDateTime(), 't')
        elif column==BCFileModel.COLNUM_FILE_SIZE:
            if isinstance(file, BCFile):
                return bytesSizeToStr(file.size())
        elif column==BCFileModel.COLNUM_IMAGE_SIZE:
            if isinstance(file, BCFile):
                valueW=file.imageSize().width()
                if valueW>=0:
                    valueH=file.imageSize().height()
                    if valueH>=0:
                        return f"{valueW}x{valueH}"
        elif column==BCFileModel.COLNUM_IMAGE_WIDTH:
            if isinstance(file, BCFile):
                value=file.imageSize().width()
                if value>=0:
                    return f"{value}"
        elif column==BCFileModel.COLNUM_IMAGE_HEIGHT:
            if isinstance(file, BCFile):
                value=file.imageSize().height()
                if value>=0:
                    return f"{value}"
        elif column==BCFileModel.COLNUM_IMAGE_RATIO:
            if isinstance(file, BCFile):
                ratio=file.getProperty(BCFileProperty.IMAGE_RATIO)
                if not ratio is None:
                    return f"{ratio:0.4f}"
        elif column==BCFileModel.COLNUM_IMAGE_ORIENTATION:
            if isinstance(file, BCFile):
                return ratioOrientation(file.getProperty(BCFileProperty.IMAGE_RATIO))
        elif column==BCFileModel.COLNUM_IMAGE_PIXELS:
            if isinstance(file, BCFile):
                nbPixels=file.getProperty(BCFileProperty.IMAGE_PIXELS)
                if not nbPixels is None:
                    return f"{nbPixels}"
        elif column==BCFileModel.COLNUM_IMAGE_PIXELSMP:
            if isinstance(file, BCFile):
                nbPixels=file.getProperty(BCFileProperty.IMAGE_PIXELS)
                if not nbPixels is None:
                    return megaPixels(nbPixels)
        return None

    def columnCount(self, parent=QModelIndex()):
        """Return total number of column"""
        return BCFileModel.COLNUM_LAST+1

    def rowCount(self, parent=QModelIndex()):
        """Return total number of rows"""
        return len(self.__items)

    def setData(self, index, value, role):
        """Set icon for given row"""
        if isinstance(index, int):
            file=self.__items[index]
            index=self.index(index, BCFileModel.COLNUM_ICON, QModelIndex())
        elif isinstance(index, QModelIndex):
            file=self.__items[index.row()]
        else:
            raise EInvalidType("Given `index` must be <QModelIndex> or <int>")

        if role==Qt.DecorationRole:
            self.__icons[file.uuid()]=value
            self.dataChanged.emit(index, index, [Qt.DecorationRole])

    def data(self, index, role=Qt.DisplayRole):
        """Return data for index+role"""
        column = index.column()
        row=index.row()
        file=self.__items[row]
        if file is None:
            return None

        if role == Qt.DecorationRole:
            if column==BCFileModel.COLNUM_ICON:
                if self.__iconAsThumbnail:
                    try:
                        return self.__icons[file.uuid()]
                    except:
                        pass

                return file.icon()
        elif role == Qt.DisplayRole:
            return self.__getValueForColumn(file, column)
        elif role== Qt.TextAlignmentRole:
            if column in self.__headerRightAlign:
                return Qt.AlignRight
            else:
                return Qt.AlignLeft
        elif role == BCFileModel.ROLE_FILE:
            return file
        elif role == BCFileModel.ROLE_FULLNFO:
            try:
                return self.__fileNfoCache[file.uuid()]
            except:
                pass
            # not in cache: build it

            # tmpDict:
            #   key=visibleIndex
            #   value=info to display
            tmpDict={}
            for logicalIndex in range(1, BCFileModel.COLNUM_LAST):
                # exclude first index (icon)
                # exclude COLNUM_LAST as is currently COLNUM_FULLNFO
                # if new columns are added, should exclude logicalIndex==COLNUM_FULLNFO
                # and loop over COLNUM_LAST+1

                if self.__columnsVisibility[logicalIndex]:
                    # column is visible
                    position=self.__columnsPosition[logicalIndex]
                    if not position is None:
                        tmpDict[position]=(BCFileModel.HEADERS[logicalIndex], self.__getValueForColumn(file, logicalIndex))

            self.__fileNfoCache[file.uuid()]=([tmpDict[visualIndex] for visualIndex in sorted(tmpDict.keys())], self.__headerMaxCharacters)

            return self.__fileNfoCache[file.uuid()]

        return None

    def headerData(self, section, orientation, role):
        """Return information for header according to role"""
        if orientation == Qt.Horizontal and section>=0 and role == Qt.DisplayRole:
            return BCFileModel.HEADERS[section]

        return QAbstractTableModel.headerData(self, section, orientation, role)

    def columnsVisibility(self):
        """Return columns positions"""
        return self.__columnsVisibility

    def setColumnsVisibility(self, values):
        """Set information for columns visibility to role"""
        self.__columnsVisibility=[value for value in values]
        self.__fileNfoCache={}
        self.headerDataChanged.emit(Qt.Horizontal, BCFileModel.COLNUM_FULLNFO, BCFileModel.COLNUM_FULLNFO)

    def columnsPosition(self):
        """Return columns positions"""
        return self.__columnsPosition

    def setColumnsPosition(self, values):
        """Set information for header according to role"""
        self.__columnsPosition=[value for value in values]
        self.__fileNfoCache={}
        self.headerDataChanged.emit(Qt.Horizontal, BCFileModel.COLNUM_FULLNFO, BCFileModel.COLNUM_FULLNFO)

    def iconAsThumbnail(self):
        """Return if icons are displayed as thumbnail or mime type"""
        return self.__iconAsThumbnail

    def setIconAsThumbnail(self, value):
        """Set if icons are displayed as thumbnail or mime type"""
        if isinstance(value, bool) and value!=self.__iconAsThumbnail:
            self.__iconAsThumbnail=value
            self.__updateIcons()

    def iconSize(self):
        """Return icons size"""
        return self.__iconSize

    def setIconSize(self, size):
        """Update icons size"""
        if self.__iconSize==size:
            # nothing to update
            return

        self.__iconSize=size
        # do not reset icons => avoid flickering when icon size is modified
        #self.__icons={}

        if self.rowCount()==0:
            # nothing to update
            return

        self.__updateIcons()

    def files(self):
        """Expose BCFileList object"""
        return self.__fileList

    def indexUuid(self, uuid):
        """Return index for given uuid

        Can be a list of uuid, return a list of index
        """
        def index(value):
            if value>-1:
                return self.index(value, 0, QModelIndex())
            return QModelIndex()

        if isinstance(uuid, (list, tuple, set)):
            uuidPositions=self.__fileList.inResults(uuid)
        else:
            uuidPositions=[self.__fileList.inResults(uuid)]

        return [index(position) for position in uuidPositions]


class BCMainViewFiles(QTreeView):
    """Tree view files"""
    focused = Signal()
    keyPressed = Signal(int)

    def __init__(self, parent=None):
        super(BCMainViewFiles, self).__init__(parent)
        self.__model = None
        self.__proxyModel = None
        self.__filesFilter = ''
        self.__viewNfoRowLimit = 7
        self.__iconSize = BCIconSizes([16, 24, 32, 48, 64, 96, 128, 256, 512])
        self.__changed = False
        self.__showPath = False

        self.__visibleColumns=[v for v in BCFileModel.DEFAULT_COLUMN_VISIBILITY]

        self.__delegate=BCMainViewFilesDelegate(self)
        self.setItemDelegate(self.__delegate)
        self.setAutoScroll(True)
        self.setUniformRowHeights(True)

        # set colums size rules
        self.__header = self.header()
        self.__header.setStretchLastSection(False)
        self.__header.setSortIndicatorShown(True)
        self.__header.setSectionsClickable(True)
        self.__header.sectionMoved.connect(self.__headerSectionMoved)

    def __headerSectionMoved(self, logicalIndex, oldVisualIndex, newVisualIndex):
        """Column position has been changed"""
        self.__model.setColumnsPosition([self.header().visualIndex(column) for column in range(BCFileModel.COLNUM_LAST)])

    def keyPressEvent(self, event):
        """Emit signal on keyPressed"""
        super(BCMainViewFiles, self).keyPressEvent(event)
        self.keyPressed.emit(event.key())

    def wheelEvent(self, event):
        """Mange zoom level through mouse wheel"""
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
        """Emit signal when treeview get focused"""
        super(BCMainViewFiles, self).focusInEvent(event)
        self.focused.emit()

    def setModel(self, model):
        """Initialise treeview header & model"""
        self.__model=model
        self.__proxyModel=QSortFilterProxyModel(self)
        self.__proxyModel.setSourceModel(self.__model)
        self.__proxyModel.setDynamicSortFilter(False)
        self.__proxyModel.setFilterKeyColumn(BCFileModel.COLNUM_FILE_NAME)

        QTreeView.setModel(self, self.__proxyModel)

        self.__header.setSectionResizeMode(BCFileModel.COLNUM_ICON, QHeaderView.Fixed)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_PATH, QHeaderView.Interactive)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_NAME, QHeaderView.Interactive)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_BASENAME, QHeaderView.Interactive)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_EXTENSION, QHeaderView.Interactive)

        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_FORMAT_SHORT, QHeaderView.Fixed)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_FORMAT_LONG, QHeaderView.Fixed)

        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_DATETIME, QHeaderView.Fixed)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_DATE, QHeaderView.Fixed)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_TIME, QHeaderView.Fixed)

        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FILE_SIZE, QHeaderView.Fixed)

        self.__header.setSectionResizeMode(BCFileModel.COLNUM_IMAGE_SIZE, QHeaderView.Fixed)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_IMAGE_WIDTH, QHeaderView.Fixed)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_IMAGE_HEIGHT, QHeaderView.Fixed)

        self.__header.setSectionResizeMode(BCFileModel.COLNUM_IMAGE_RATIO, QHeaderView.Fixed)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_IMAGE_ORIENTATION, QHeaderView.Fixed)

        self.__header.setSectionResizeMode(BCFileModel.COLNUM_IMAGE_PIXELS, QHeaderView.Fixed)
        self.__header.setSectionResizeMode(BCFileModel.COLNUM_IMAGE_PIXELSMP, QHeaderView.Fixed)

        self.__header.setSectionResizeMode(BCFileModel.COLNUM_FULLNFO, QHeaderView.Interactive)

        self.__header.setSectionHidden(BCFileModel.COLNUM_FILE_PATH, True)
        self.__header.setSectionHidden(BCFileModel.COLNUM_FULLNFO, True)

    def resizeColumns(self, fixedOnly=True):
        """Resize columns to content"""
        if not fixedOnly and self.__model.rowCount() > 1:
            # greater than 1 ==> if only '..' item don't change column width
            self.resizeColumnToContents(BCFileModel.COLNUM_FILE_PATH)
            self.resizeColumnToContents(BCFileModel.COLNUM_FILE_NAME)
            self.resizeColumnToContents(BCFileModel.COLNUM_FILE_BASENAME)
            self.resizeColumnToContents(BCFileModel.COLNUM_FILE_EXTENSION)

        self.resizeColumnToContents(BCFileModel.COLNUM_ICON)

        self.resizeColumnToContents(BCFileModel.COLNUM_FILE_FORMAT_SHORT)
        self.resizeColumnToContents(BCFileModel.COLNUM_FILE_FORMAT_LONG)

        self.resizeColumnToContents(BCFileModel.COLNUM_FILE_DATETIME)
        self.resizeColumnToContents(BCFileModel.COLNUM_FILE_DATE)
        self.resizeColumnToContents(BCFileModel.COLNUM_FILE_TIME)

        self.resizeColumnToContents(BCFileModel.COLNUM_FILE_SIZE)

        self.resizeColumnToContents(BCFileModel.COLNUM_IMAGE_SIZE)
        self.resizeColumnToContents(BCFileModel.COLNUM_IMAGE_WIDTH)
        self.resizeColumnToContents(BCFileModel.COLNUM_IMAGE_HEIGHT)

        self.resizeColumnToContents(BCFileModel.COLNUM_IMAGE_RATIO)
        self.resizeColumnToContents(BCFileModel.COLNUM_IMAGE_ORIENTATION)

        self.resizeColumnToContents(BCFileModel.COLNUM_IMAGE_PIXELS)
        self.resizeColumnToContents(BCFileModel.COLNUM_IMAGE_PIXELSMP)

        self.resizeColumnToContents(BCFileModel.COLNUM_FULLNFO)

    def filterModel(self):
        """Return proxy filter model"""
        return self.__proxyModel

    def invertSelection(self):
        """Invert current selection"""
        first = self.__proxyModel.index(0, 0)
        last = self.__proxyModel.index(self.__proxyModel.rowCount() - 1, 7)

        self.selectionModel().select(QItemSelection(first, last), QItemSelectionModel.Toggle)

    def files(self):
        """Return a list of files, taking in account current proxymodel (return filtered files only)"""
        returned=[]

        for rowIndex in range(self.__proxyModel.rowCount()):
            fileNfo = self.__proxyModel.index(rowIndex, 0).data(BCFileModel.ROLE_FILE)
            if not(fileNfo.name() == '..' and fileNfo.format() == BCFileManagedFormat.DIRECTORY):
                returned.append(fileNfo)

        return returned

    def selectedFiles(self):
        """Return a list of selected files

        Each returned item is a tuple (row, BCBaseFile)
        """
        returned=[]
        if self.selectionModel() is None:
            return returned

        smodel=self.selectionModel().selectedRows(BCFileModel.COLNUM_FILE_NAME)

        for item in smodel:
            fileNfo = item.data(BCFileModel.ROLE_FILE)
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

            # made asynchronously...
            # update model before treeview
            self.__model.setIconSize(BCFileThumbnailSize.fromValue(self.__iconSize.value()))

            self.__delegate.setIconSize(self.__iconSize.value())
            self.setIconSize(QSize(self.__iconSize.value(), self.__iconSize.value()))

            header = self.header()
            # ...then not possible to determinate column ICON width from content
            # and fix it to icon size
            header.resizeSection(BCFileModel.COLNUM_ICON, self.__iconSize.value())

            if self.__iconSize.index() < self.__viewNfoRowLimit:
                # user defined columns model
                header.setStretchLastSection(False)
                for logicalIndex, visible in enumerate(self.__visibleColumns):
                    if logicalIndex==BCFileModel.COLNUM_FILE_PATH:
                        header.setSectionHidden(logicalIndex, not self.__showPath)
                    elif logicalIndex==BCFileModel.COLNUM_ICON:
                        header.setSectionHidden(logicalIndex, False)
                    else:
                        header.setSectionHidden(logicalIndex, not visible)
                self.resizeColumns(True)
            else:
                # specific columns model
                header.setStretchLastSection(True)
                for logicalIndex, visible in enumerate(self.__visibleColumns):
                    header.setSectionHidden(logicalIndex, not logicalIndex in (BCFileModel.COLNUM_FULLNFO, BCFileModel.COLNUM_ICON))
                self.resizeColumns(False)

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
        return self.__model.iconAsThumbnail()

    def setViewThumbnail(self, value):
        """Set current view mode"""
        if value is None or not isinstance(value, bool):
            value = False

        self.__model.setIconAsThumbnail(value)

    def columnIsVisible(self, column):
        """Return if given (logical) column is visible or not"""
        return self.__visibleColumns[column]

    def setColumnVisible(self, column, isVisible=True):
        """Set given (logical) column visibility"""
        # column ICON must be always visible, then ignore visibility action for this one
        # column PATH is displayed in specific case only: view (manually built, search result, ...); visiblity is defined by self.__showPath, defined according current view type
        if column>=0 and column<len(self.__visibleColumns) and isinstance(isVisible, bool) and not column in (BCFileModel.COLNUM_ICON, BCFileModel.COLNUM_FILE_PATH):
            self.__visibleColumns[column]=isVisible
            self.header().setSectionHidden(column, not isVisible)
            self.__model.setColumnsVisibility(self.__visibleColumns)

    def columnsVisibility(self):
        """Return list of columns visibility"""
        return self.__visibleColumns

    def columnPosition(self, column):
        """Return visual position for logical index column"""
        return self.header().visualIndex(column)

    def setColumnPosition(self, column, visualPosition):
        """Set visual position for logical index column"""
        self.header().moveSection(column, visualPosition)
        self.__headerSectionMoved(column, -1, visualPosition)

    def showPath(self):
        """Is path is visible or not"""
        return self.__showPath

    def setShowPath(self, value):
        """Set if path is visible or not"""
        if isinstance(value, bool):
            self.__showPath = value
            self.__model.setColumnsVisibility([self.__visibleColumns[column] if column!=BCFileModel.COLNUM_FILE_PATH else self.__showPath for column in range(BCFileModel.COLNUM_LAST)])
            self.setIconSizeIndex()
        else:
            raise EInvalidType("Given `value` must be a <bool>")


class BCMainViewFilesDelegate(QStyledItemDelegate):
    """Extend QStyledItemDelegate class to return properly row height"""

    def __init__(self, parent=None):
        """Constructor, nothingspecial"""
        super(BCMainViewFilesDelegate, self).__init__(parent)
        self.__iconSize=QSize(64, 64)
        self.__charHeight=0

    def setIconSize(self, value):
        self.__iconSize=QSize(value, value)
        self.sizeHintChanged.emit(self.parent().model().createIndex(0, BCFileModel.COLNUM_ICON))

    def paint(self, painter, option, index):
        """Paint list item"""
        if index.column() == BCFileModel.COLNUM_FULLNFO:
            # render full information
            self.initStyleOption(option, index)

            rectTxt = QRect(option.rect.left(), option.rect.top(), option.rect.width(), option.rect.height())

            # tuple (data(label, value), header max characters)
            dataNfo=index.data(BCFileModel.ROLE_FULLNFO)

            fntBold=QFont(option.font)
            fntBold.setBold(True)
            fm=QFontMetrics(fntBold)
            hOffset=fm.height()
            wOffset=5+fm.horizontalAdvance('W')*dataNfo[1]

            painter.save()

            painter.translate(QPointF(option.rect.topLeft()))

            top=0
            for nfo in dataNfo[0]:
                painter.setFont(fntBold)
                painter.drawText(5, top, option.rect.width(), option.rect.height(), Qt.AlignLeft, nfo[0])

                painter.setFont(option.font)
                painter.drawText(wOffset, top, option.rect.width(), option.rect.height(), Qt.AlignLeft, nfo[1])

                top+=hOffset

            painter.restore()
            return

        QStyledItemDelegate.paint(self, painter, option, index)


    def sizeHint(self, option, index):
        """Calculate size for items"""
        if index.column() == BCFileModel.COLNUM_ICON:
            return self.__iconSize
        elif index.column() == BCFileModel.COLNUM_FULLNFO:
            currentSize=QStyledItemDelegate.sizeHint(self, option, index)
            currentSize.setHeight(option.fontMetrics.height() * len(index.data(BCFileModel.ROLE_FULLNFO)[0]))
            return currentSize

        return QStyledItemDelegate.sizeHint(self, option, index)
