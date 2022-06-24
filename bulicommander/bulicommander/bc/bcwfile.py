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
import html

from multiprocessing import Pool


from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )

from .bcwpathbar import BCWPathBar
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
from .bcsettings import (
        BCSettings,
        BCSettingsKey
    )

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
from bulicommander.pktk.modules.menuutils import (
        buildQAction,
        buildQMenu
    )
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )

from bulicommander.pktk.widgets.wsearchinput import SearchOptions


# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------

class BCFileModel(QAbstractTableModel):
    """A model to manage list of BCFiles for QTreeView/QListView"""
    iconStartLoad = Signal(int)
    iconProcessed = Signal()
    iconStopLoad = Signal()
    markersChanged = Signal()

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
    ROLE_MARKER = Qt.UserRole + 4
    ROLE_GRIDNFO = Qt.UserRole + 1000

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

        self.__tooltipEnabled=False

        self.__fileList=fileList
        self.__fileList.resultsUpdatedReset.connect(self.__dataUpdateReset)
        self.__fileList.resultsUpdatedAdd.connect(self.__dataUpdatedAdd)
        self.__fileList.resultsUpdatedRemove.connect(self.__dataUpdateRemove)
        self.__fileList.resultsUpdatedUpdate.connect(self.__dataUpdateUpdate)
        self.__fileList.resultsUpdatedSort.connect(self.__dataUpdateSort)

        self.__fileNfoCache={}
        self.__icons={}
        self.__markers=set()
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
        self.__markers.clear()
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
        pass

    def __dataUpdateRemove(self, items):
        """Remove file from model"""
        pass

    def __dataUpdateUpdate(self, items):
        """Update file from model"""
        pass

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

    def setData(self, index, value, role, emitDataChanged=True):
        """Set icon for given row"""
        if isinstance(index, int):
            file=self.__items[index]
            index=self.index(index, BCFileModel.COLNUM_ICON, QModelIndex())
        elif isinstance(index, QModelIndex):
            file=self.__items[index.row()]
        elif isinstance(index, list):
            rS=2147483647
            rE=0
            for item in index:
                if isinstance(item, BCBaseFile):
                    itemIndex=self.indexUuid(item.uuid())
                    if len(itemIndex)==0:
                        continue
                    item=itemIndex[0]

                if rS>item.row():
                    rS=item.row()
                if rE<item.row():
                    rE=item.row()
                self.setData(item, value, role, False)
            if emitDataChanged and rS<rE:
                indexS=self.index(rS, 0)
                indexE=self.index(rE, BCFileModel.COLNUM_LAST)
                self.dataChanged.emit(indexS, indexE, [role])
                if role==BCFileModel.ROLE_MARKER:
                    self.markersChanged.emit()
            return
        elif isinstance(index, BCBaseFile):
            file=index
            itemIndex=self.indexUuid(item.uuid())
            if len(itemIndex)==0:
                return
            index=itemIndex[0]
        else:
            raise EInvalidType("Given `index` must be <QModelIndex> or <int>")

        if role==Qt.DecorationRole:
            self.__icons[file.uuid()]=value
            if emitDataChanged:
                self.dataChanged.emit(index, index, [Qt.DecorationRole])
        elif role==BCFileModel.ROLE_MARKER:
            if value:
                self.__markers.add(file.uuid())
            else:
                try:
                    self.__markers.remove(file.uuid())
                except:
                    pass
            if emitDataChanged:
                indexS=self.index(index.row(), 0)
                indexE=self.index(index.row(), BCFileModel.COLNUM_LAST)
                self.dataChanged.emit(indexS, indexE, [BCFileModel.ROLE_MARKER])
                self.markersChanged.emit()

    def data(self, index, role=Qt.DisplayRole):
        """Return data for index+role"""
        def buildNfoFileCache(uuid):
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
        elif role==Qt.ToolTipRole:
            if self.__tooltipEnabled:
                try:
                    cacheData=self.__fileNfoCache[file.uuid()]
                except:
                    # not in cache: build it
                    buildNfoFileCache(file.uuid())
                    cacheData=self.__fileNfoCache[file.uuid()]

                returned=[]
                for nfo in cacheData[0]:
                    if nfo[1] is not None:
                        returned.append(f"<tr><td><b>{html.escape(nfo[0]).replace(' ', '&nbsp;')}</b></td><td>{html.escape(nfo[1]).replace(' ', '&nbsp;')}</td></tr>")

                return f"<table style='font-family:monospace'>{''.join(returned)}</table>"
        elif role == BCFileModel.ROLE_FILE:
            return file
        elif role == BCFileModel.ROLE_FULLNFO:
            try:
                return self.__fileNfoCache[file.uuid()]
            except:
                pass
            # not in cache: build it
            buildNfoFileCache(file.uuid())

            return self.__fileNfoCache[file.uuid()]
        elif role == BCFileModel.ROLE_MARKER:
            return file.uuid() in self.__markers
        elif role==(BCFileModel.ROLE_GRIDNFO + BCFileModel.COLNUM_FILE_NAME):
            return self.__getValueForColumn(file, BCFileModel.COLNUM_FILE_NAME)
        elif role>=BCFileModel.ROLE_GRIDNFO:
            return self.__getValueForColumn(file, role - BCFileModel.ROLE_GRIDNFO)

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

    def tooltipEnabled(self):
        """Return if tooltip is enabled or not"""
        return self.__tooltipEnabled

    def setTooltipEnabled(self, value):
        """Return if tooltip is enabled or not"""
        if isinstance(value, bool):
            self.__tooltipEnabled=value

    def isThumbnailLoading(self):
        """Return if there's currently an asynchronous thumbnail loading process"""
        return self.__updatingIcons != BCFileModel.__STATUS_ICON_LOADED

    def nbMarkers(self):
        """Return number of marked files"""
        return len(self.__markers)

    def markers(self):
        """Return list of uuid of marked files"""
        return self.__markers



class BCSortFilterProxyModel(QSortFilterProxyModel):
    """A proxy model that take in account marked files"""

    def __init__(self, parent=None):
        super(BCSortFilterProxyModel, self).__init__(parent)
        self.__markedFilesOnly=False

    def setMarkedFilesOnly(self, value):
        """Define if only marked files are returned or not"""
        if self.__markedFilesOnly!=value:
            self.__markedFilesOnly=value
            self.invalidateFilter()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Override method to take in account option self.__markedFilesOnly"""
        returned=super(BCSortFilterProxyModel, self).filterAcceptsRow(sourceRow, sourceParent)

        if not (returned or self.__markedFilesOnly):
            # doesn't match current rules, no need to check for mark filter
            return returned


        index = self.sourceModel().index(sourceRow, 0, sourceParent)
        isMarked=self.sourceModel().data(index, BCFileModel.ROLE_MARKER)

        if isMarked and self.__markedFilesOnly or not self.__markedFilesOnly:
            return returned
        else:
            return False



class BCViewFilesTv(QTreeView):
    """Tree view files"""
    focused = Signal()
    keyPressed = Signal(int)
    columnVisibilityChanged = Signal(list)     # [logicalIndex]=visibility
    columnPositionChanged = Signal(list)       # [logicalIndex]=visualIndex
    iconSizeChanged = Signal(int)

    def __init__(self, parent=None):
        super(BCViewFilesTv, self).__init__(parent)
        self.__model = None
        self.__proxyModel = None
        self.__filesFilterText = ''
        self.__filesFilterOptions = 0
        self.__viewNfoRowLimit = 7
        self.__iconSize = BCIconSizes([16, 24, 32, 48, 64, 96, 128, 256, 512])
        self.__showPath = False

        self.__visibleColumns=[v for v in BCFileModel.DEFAULT_COLUMN_VISIBILITY]

        self.__delegate=BCViewFilesTvDelegate(self)
        self.setItemDelegate(self.__delegate)
        self.setAutoScroll(True)
        self.setUniformRowHeights(True)

        # set colums size rules
        self.__header = self.header()
        self.__header.setStretchLastSection(False)
        self.__header.setSortIndicatorShown(True)
        self.__header.setSectionsClickable(True)
        self.__header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.__header.sectionMoved.connect(self.__headerSectionMoved)
        self.__header.customContextMenuRequested.connect(self.__headerContextMenu)

    def __headerContextMenu(self, position):
        """Display context menu on treeview header"""
        def columnVisible(visible):
            action=self.sender()
            self.setColumnVisible(action.property('logicalIndex'), visible)

        contextMenu = QMenu(self.__header)

        menuShowColumns = buildQMenu("pktk:tune", i18n('Visible columns'), contextMenu)
        contextMenu.addMenu(menuShowColumns)

        for logicalIndex in range(1, BCFileModel.COLNUM_LAST+1):
            if not logicalIndex in (BCFileModel.COLNUM_FILE_PATH, BCFileModel.COLNUM_FULLNFO):
                # use checkbox as widgetaction to prevent menu being hidden after action is clicked
                checkBox=QCheckBox(BCFileModel.HEADERS[logicalIndex])
                checkBox.setChecked(self.__visibleColumns[logicalIndex])
                checkBox.setProperty('logicalIndex', logicalIndex)
                checkBox.toggled.connect(columnVisible)
                checkBox.setStyleSheet("padding-left: 4px;")

                checkableAction=QWidgetAction(menuShowColumns)
                checkableAction.setDefaultWidget(checkBox)
                menuShowColumns.addAction(checkableAction)

        action=buildQAction('pktk:column_resize', i18n('Resize columns to content'), self)
        action.triggered.connect(lambda: self.resizeColumns(False))

        contextMenu.addSeparator()
        contextMenu.addAction(action)

        contextMenu.exec(self.__header.mapToGlobal(position))

    def __headerSectionMoved(self, logicalIndex, oldVisualIndex, newVisualIndex):
        """Column position has been changed"""
        columns=[self.header().visualIndex(column) for column in range(BCFileModel.COLNUM_LAST)]
        self.__model.setColumnsPosition(columns)
        self.columnPositionChanged.emit(columns)

    def keyPressEvent(self, event):
        """Emit signal on keyPressed"""
        super(BCViewFilesTv, self).keyPressEvent(event)
        self.keyPressed.emit(event.key())

    def wheelEvent(self, event):
        """Manage zoom level through mouse wheel"""
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
            super(BCViewFilesTv, self).wheelEvent(event)

    def focusInEvent(self, event):
        """Emit signal when treeview get focused"""
        super(BCViewFilesTv, self).focusInEvent(event)
        self.focused.emit()

    def setModel(self, model):
        """Initialise treeview header & model"""
        self.__model=model
        self.__proxyModel=BCSortFilterProxyModel(self)
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

    def selectMarked(self):
        """Select marked items"""
        selection=QItemSelection()
        for rowIndex in range(self.__proxyModel.rowCount()):
            itemIndex=self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0))
            if self.__model.data(itemIndex, BCFileModel.ROLE_MARKER):
                selection.select(itemIndex, itemIndex)

        self.selectionModel().select(selection, QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)

    def markUnmark(self):
        """Invert current marked items"""
        itemIndex=self.__proxyModel.mapToSource(self.currentIndex())
        self.__model.setData(itemIndex, not self.__model.data(itemIndex, BCFileModel.ROLE_MARKER), BCFileModel.ROLE_MARKER)

        if BCSettings.get(BCSettingsKey.CONFIG_PANELVIEW_FILES_MARKERS_MOVETONEXT):
            nextIndex=self.indexBelow(self.currentIndex())
            if nextIndex.row()>-1:
                self.setCurrentIndex(nextIndex)

    def markAll(self):
        """Mark all items"""
        self.__model.setData([self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0)) for rowIndex in range(self.__proxyModel.rowCount())], True, BCFileModel.ROLE_MARKER)

    def markNone(self):
        """Unmark all items"""
        self.__model.setData([self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0)) for rowIndex in range(self.__proxyModel.rowCount())], False, BCFileModel.ROLE_MARKER)

    def markInvert(self):
        """Invert current marked items"""
        indexList=[]
        indexListInverted=[]
        for rowIndex in range(self.__proxyModel.rowCount()):
            itemIndex=self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0))
            indexList.append(itemIndex)

            if not self.__model.data(itemIndex, BCFileModel.ROLE_MARKER):
                indexListInverted.append(itemIndex)

        self.__model.setData(indexList, False, BCFileModel.ROLE_MARKER, False)
        self.__model.setData(indexListInverted, True, BCFileModel.ROLE_MARKER)

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

    def iconSizePixels(self):
        """Return current icon size in pixels"""
        return self.__iconSize.value()

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

            self.iconSizeChanged.emit(self.__iconSize.index())

    def setFilter(self, filterText, filterOptions):
        """Set current filter"""

        if filterText is None:
            filterText = self.__filesFilterText

        if filterOptions is None:
            filterOptions = self.__filesFilterOptions

        if filterText == self.__filesFilterText and filterOptions == self.__filesFilterOptions:
            # filter unchanged, do nothing
            return

        if not isinstance(filterText, str):
            raise EInvalidType('Given `filterText` must be a <str>')

        self.__proxyModel.setMarkedFilesOnly(filterOptions&BCWPathBar.OPTION_FILTER_MARKED_ACTIVE==BCWPathBar.OPTION_FILTER_MARKED_ACTIVE)

        if filterOptions&SearchOptions.CASESENSITIVE:
            self.__proxyModel.setFilterCaseSensitivity(Qt.CaseSensitive)
        else:
            self.__proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)


        if filterOptions&SearchOptions.REGEX:
            self.__proxyModel.setFilterRegExp(filterText)
        else:
            self.__proxyModel.setFilterWildcard(filterText)

        self.__filesFilterText = filterText
        self.__filesFilterOptions = filterOptions

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
            self.columnVisibilityChanged.emit(self.__visibleColumns)

    def columnsVisibility(self):
        """Return list of columns visibility"""
        return self.__visibleColumns

    def columnsPosition(self):
        """Return visual position for logical index column"""
        return [self.header().visualIndex(column) for column in range(BCFileModel.COLNUM_LAST)]

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

    def markers(self):
        """Return a <BCFile> list of marked files"""
        markers=[]
        for rowIndex in range(self.__proxyModel.rowCount()):
            index=self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0))
            if self.__model.data(index, BCFileModel.ROLE_MARKER):
                markers.append(self.__model.data(index, BCFileModel.ROLE_FILE))
        return markers

    def setMarkers(self, markers):
        """Set marked files"""
        self.__model.setData([self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0)) for rowIndex in range(self.__proxyModel.rowCount())], False, BCFileModel.ROLE_MARKER, False)
        self.__model.setData(markers, True, BCFileModel.ROLE_MARKER)



class BCViewFilesTvDelegate(QStyledItemDelegate):
    """Extend QStyledItemDelegate class to return properly row height"""

    ICON_RPADDING=5

    def __init__(self, parent=None):
        """Constructor, nothingspecial"""
        super(BCViewFilesTvDelegate, self).__init__(parent)
        self.__iconSize=QSize(64, 64)
        self.__iconSizeColumn=QSize(64+BCViewFilesTvDelegate.ICON_RPADDING, 64)

    def setIconSize(self, value):
        self.__iconSize=QSize(value, value)
        self.__iconSizeColumn=QSize(value+BCViewFilesTvDelegate.ICON_RPADDING, value)
        self.sizeHintChanged.emit(self.parent().model().createIndex(0, BCFileModel.COLNUM_ICON))

    def paint(self, painter, option, index):
        """Paint list item"""
        self.initStyleOption(option, index)
        painter.save()

        color=None
        overlay=False
        isSelected=False

        if (option.state & QStyle.State_Selected) == QStyle.State_Selected:
            colorText=option.palette.color(QPalette.HighlightedText)
            overlay=True
            isSelected=True
            if self.parent().hasFocus():
                color=option.palette.color(QPalette.Active, QPalette.Highlight)
            else:
                color=option.palette.color(QPalette.Inactive, QPalette.Highlight)

            painter.setBrush(QBrush(color))
        else:
            colorText=option.palette.color(QPalette.Text)
            if (option.features & QStyleOptionViewItem.Alternate):
                color=option.palette.color(QPalette.AlternateBase)
            else:
                color=option.palette.color(QPalette.Base)

        # draw background
        painter.fillRect(option.rect, color)

        marked=index.data(BCFileModel.ROLE_MARKER)

        if index.column() == BCFileModel.COLNUM_ICON:
            # render centered icon
            painter.setRenderHint(QPainter.Antialiasing)

            # icon as QIcon
            img=index.data(Qt.DecorationRole).pixmap(self.__iconSize)

            # calculate centered position for icon
            position=QPoint(option.rect.left()+(option.rect.width()-img.width()-BCViewFilesTvDelegate.ICON_RPADDING)//2, option.rect.top()+(option.rect.height()-img.height())//2)

            #painter.setPen(QPen(Qt.NoPen))

            # draw icon
            painter.drawPixmap(position, img)

            if overlay:
                # selected item
                color.setAlphaF(0.25)
                painter.fillRect(QRect(position, img.size()), color)

            if marked:
                painter.setBrush(colorText)
                painter.drawPolygon(QPoint(option.rect.right(), option.rect.bottom()),
                                    QPoint(option.rect.right()-(BCViewFilesTvDelegate.ICON_RPADDING<<1), option.rect.bottom()),
                                    QPoint(option.rect.right(), option.rect.bottom()-(BCViewFilesTvDelegate.ICON_RPADDING<<1)))


        elif index.column() == BCFileModel.COLNUM_FULLNFO:
            # render full information
            rectTxt = QRect(option.rect.left(), option.rect.top(), option.rect.width(), option.rect.height())

            # tuple (data(label, value), header max characters)
            dataNfo=index.data(BCFileModel.ROLE_FULLNFO)

            fntBold=QFont(option.font)
            fntBold.setBold(True)
            fm=QFontMetrics(fntBold)
            hOffset=fm.height()
            wOffset=5+fm.horizontalAdvance('W')*dataNfo[1]

            painter.translate(QPointF(option.rect.topLeft()))

            fntNormal=QFont(option.font)
            if marked:
                fntNormal.setItalic(True)
                fntBold.setItalic(True)

            top=0
            for nfo in dataNfo[0]:
                painter.setFont(fntBold)
                painter.drawText(5, top, option.rect.width(), option.rect.height(), Qt.AlignLeft, nfo[0])

                painter.setFont(fntNormal)
                painter.drawText(wOffset, top, option.rect.width(), option.rect.height(), Qt.AlignLeft, nfo[1])

                top+=hOffset
        else:
            rectTxt = QRect(option.rect.left(), option.rect.top(), option.rect.width(), option.rect.height())

            dataNfo=index.data(Qt.DisplayRole)

            if not dataNfo is None:
                if marked:
                    fntMarker=QFont(option.font)
                    fntMarker.setItalic(True)
                    painter.setFont(fntMarker)

                painter.drawText(option.rect.left(), option.rect.top(), option.rect.width(), option.rect.height(), index.data(Qt.TextAlignmentRole)|Qt.AlignVCenter, dataNfo)

        painter.restore()

    def sizeHint(self, option, index):
        """Calculate size for items"""
        if index.column() == BCFileModel.COLNUM_ICON:
            return self.__iconSizeColumn
        elif index.column() == BCFileModel.COLNUM_FULLNFO:
            currentSize=QStyledItemDelegate.sizeHint(self, option, index)
            currentSize.setHeight(option.fontMetrics.height() * len(index.data(BCFileModel.ROLE_FULLNFO)[0]))
            return currentSize

        return QStyledItemDelegate.sizeHint(self, option, index)



class BCViewFilesLv(QListView):
    """List view files"""
    focused = Signal()
    keyPressed = Signal(int)
    iconSizeChanged = Signal(int)

    OPTION_LAYOUT_GRIDINFO_NONE = 0
    OPTION_LAYOUT_GRIDINFO_OVER = 1
    OPTION_LAYOUT_GRIDINFO_BOTTOM = 2
    OPTION_LAYOUT_GRIDINFO_RIGHT = 3

    def __init__(self, parent=None):
        super(BCViewFilesLv, self).__init__(parent)
        self.__model = None
        self.__proxyModel = None
        self.__filesFilterText = ''
        self.__filesFilterOptions = 0
        self.__iconSize = BCIconSizes([64, 96, 128, 192, 256, 512])
        self.__iconSizeIsDefault=True
        self.__showPath = False

        self.__gridNfoFields=[BCFileModel.COLNUM_FILE_NAME]
        self.__gridNfoLayout=BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_NONE
        self.__gridNfoOverMinSize=2

        self.__visibleColumns=[v for v in BCFileModel.DEFAULT_COLUMN_VISIBILITY]
        self.__positionColumns=[v for v in range(BCFileModel.COLNUM_LAST+1)]

        self.__delegate=BCViewFilesLvDelegate(self)
        self.setItemDelegate(self.__delegate)
        self.setAutoScroll(True)
        self.setViewMode(QListView.IconMode)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSpacing(5)
        self.setUniformItemSizes(True)

    def __updateScrollBarSensitivity(self):
        """Update scrollbar sensitivity"""
        index=self.__iconSize.index()
        sStep=round((self.__iconSize.value()/(1+index))*((1+index/2)*self.viewport().height()/1024), 0)
        self.verticalScrollBar().setSingleStep(sStep)

    def resizeEvent(self, event):
        """Listview is resized, update scrollbar sensitivity"""
        super(BCViewFilesLv, self).resizeEvent(event)
        self.__updateScrollBarSensitivity()

    def keyPressEvent(self, event):
        """Emit signal on keyPressed"""
        super(BCViewFilesLv, self).keyPressEvent(event)
        self.keyPressed.emit(event.key())

    def wheelEvent(self, event):
        """Manage zoom level through mouse wheel"""
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
            super(BCViewFilesLv, self).wheelEvent(event)

    def focusInEvent(self, event):
        """Emit signal when treeview get focused"""
        super(BCViewFilesLv, self).focusInEvent(event)
        self.focused.emit()

    def setModel(self, model):
        """Initialise treeview header & model"""
        self.__model=model
        self.__model.setIconAsThumbnail(True)
        self.__model.setTooltipEnabled(True)
        self.__proxyModel=BCSortFilterProxyModel(self)
        self.__proxyModel.setSourceModel(self.__model)
        self.__proxyModel.setDynamicSortFilter(False)
        self.__proxyModel.setFilterKeyColumn(BCFileModel.COLNUM_FILE_NAME)

        QListView.setModel(self, self.__proxyModel)

    def filterModel(self):
        """Return proxy filter model"""
        return self.__proxyModel

    def invertSelection(self):
        """Invert current selection"""
        first = self.__proxyModel.index(0, 0)
        last = self.__proxyModel.index(self.__proxyModel.rowCount() - 1, 7)

        self.selectionModel().select(QItemSelection(first, last), QItemSelectionModel.Toggle)

    def selectMarked(self):
        """Select marked items"""
        selection=QItemSelection()
        for rowIndex in range(self.__proxyModel.rowCount()):
            itemIndex=self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0))
            if self.__model.data(itemIndex, BCFileModel.ROLE_MARKER):
                selection.select(itemIndex, itemIndex)

        self.selectionModel().select(selection, QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)

    def markUnmark(self):
        """Invert current marked items"""
        itemIndex=self.__proxyModel.mapToSource(self.currentIndex())
        self.__model.setData(itemIndex, not self.__model.data(itemIndex, BCFileModel.ROLE_MARKER), BCFileModel.ROLE_MARKER)

        if BCSettings.get(BCSettingsKey.CONFIG_PANELVIEW_FILES_MARKERS_MOVETONEXT):
            nextIndex=self.__proxyModel.index(self.currentIndex().row()+1, 0)
            if nextIndex.row()>-1:
                self.setCurrentIndex(nextIndex)

    def markAll(self):
        """Mark all items"""
        self.__model.setData([self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0)) for rowIndex in range(self.__proxyModel.rowCount())], True, BCFileModel.ROLE_MARKER)

    def markNone(self):
        """Unmark all items"""
        self.__model.setData([self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0)) for rowIndex in range(self.__proxyModel.rowCount())], False, BCFileModel.ROLE_MARKER)

    def markInvert(self):
        """Invert current marked items"""
        indexList=[]
        indexListInverted=[]
        for rowIndex in range(self.__proxyModel.rowCount()):
            itemIndex=self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0))
            indexList.append(itemIndex)

            if not self.__model.data(itemIndex, BCFileModel.ROLE_MARKER):
                indexListInverted.append(itemIndex)

        self.__model.setData(indexList, False, BCFileModel.ROLE_MARKER, False)
        self.__model.setData(indexListInverted, True, BCFileModel.ROLE_MARKER)

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

    def iconSizePixels(self):
        """Return current icon size in pixels"""
        return self.__iconSize.value()

    def iconSizeIndex(self):
        """Return current icon size index"""
        return self.__iconSize.index()

    def setIconSizeIndex(self, index=None):
        """Set icon size from index value"""
        if index is None or self.__iconSize.setIndex(index) or self.__iconSizeIsDefault:
            self.__iconSizeIsDefault=False
            newSize=self.__iconSize.value()
            # new size defined

            # made asynchronously...
            # update model before listview
            self.__model.setIconSize(BCFileThumbnailSize.fromValue(newSize))

            self.__delegate.setIconSize(newSize)
            self.setIconSize(QSize(newSize, newSize))
            self.iconSizeChanged.emit(self.__iconSize.index())

            # update scrollbar sensitivity according to icon size
            self.__updateScrollBarSensitivity()

    def setFilter(self, filterText, filterOptions):
        """Set current filter"""

        if filterText is None:
            filterText = self.__filesFilterText

        if filterOptions is None:
            filterOptions = self.__filesFilterOptions

        if filterText == self.__filesFilterText and filterOptions == self.__filesFilterOptions:
            # filter unchanged, do nothing
            return

        if not isinstance(filterText, str):
            raise EInvalidType('Given `filterText` must be a <str>')

        self.__proxyModel.setMarkedFilesOnly(filterOptions&BCWPathBar.OPTION_FILTER_MARKED_ACTIVE==BCWPathBar.OPTION_FILTER_MARKED_ACTIVE)

        if filterOptions&SearchOptions.CASESENSITIVE:
            self.__proxyModel.setFilterCaseSensitivity(Qt.CaseSensitive)
        else:
            self.__proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)


        if filterOptions&SearchOptions.REGEX:
            self.__proxyModel.setFilterRegExp(filterText)
        else:
            self.__proxyModel.setFilterWildcard(filterText)

        self.__filesFilterText = filterText
        self.__filesFilterOptions = filterOptions

    def viewThumbnail(self):
        """Return current view mode (list/icon)"""
        return self.__model.iconAsThumbnail()

    def setViewThumbnail(self, value):
        """Set current view mode"""
        if value is None or not isinstance(value, bool):
            value = False

        self.__model.setIconAsThumbnail(value)

    def columnsVisibility(self):
        """Return list of columns visibility"""
        return self.__visibleColumns

    def setColumnsVisibility(self, columns):
        """Set given (logical) column visibility"""
        self.__visibleColumns=[value for value in columns]
        self.__model.setColumnsVisibility(self.__visibleColumns)

    def columnsPosition(self):
        """Return visual position for logical index column"""
        return self.__positionColumns

    def setColumnsPosition(self, columns):
        """Set visual position for logical index column"""
        self.__positionColumns=[value for value in columns]
        self.__model.setColumnsPosition(self.__positionColumns)

    def showPath(self):
        """Is path is visible or not"""
        return self.__showPath

    def setShowPath(self, value):
        """Set if path is visible or not"""
        if isinstance(value, bool):
            self.__showPath = value
            self.__model.setColumnsVisibility([self.__visibleColumns[column] if column!=BCFileModel.COLNUM_FILE_PATH else self.__showPath for column in range(BCFileModel.COLNUM_LAST)])
        else:
            raise EInvalidType("Given `value` must be a <bool>")

    def gridNfoFields(self):
        """Return current fields displayed as grid information"""
        return self.__gridNfoFields

    def setGridNfoFields(self, gridNfoFields):
        """Set current fields displayed as grid information"""
        if not isinstance(gridNfoFields, (list, tuple)):
            raise EInvalidType("Given `gridNfoFields` must be a <list> or a <tuple>")

        self.__gridNfoFields=[]
        for field in gridNfoFields:
            if isinstance(field, int) and (field in [BCFileModel.COLNUM_FILE_NAME,
                                                     BCFileModel.COLNUM_FILE_FORMAT_SHORT,
                                                     BCFileModel.COLNUM_FILE_DATETIME,
                                                     BCFileModel.COLNUM_FILE_SIZE,
                                                     BCFileModel.COLNUM_IMAGE_SIZE]):
                self.__gridNfoFields.append(field)

        if len(self.__gridNfoFields)==0:
            self.__gridNfoFields=[BCFileModel.COLNUM_FILE_NAME]

        self.__delegate.setNfoFields(self.__gridNfoFields)

    def gridNfoLayout(self):
        """Return current grid information layout"""
        return self.__gridNfoLayout

    def setGridNfoLayout(self, gridNfoLayout):
        """Set current fields displayed as grid information"""
        if not isinstance(gridNfoLayout, int):
            raise EInvalidType("Given `gridNfoLayout` must be a <int>")
        if not gridNfoLayout in (BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_NONE,
                                 BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_OVER,
                                 BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_BOTTOM,
                                 BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_RIGHT):
            raise EInvalidValue("Given `gridNfoLayout` must be a valid value")

        if self.__gridNfoLayout!=gridNfoLayout:
            self.__gridNfoLayout=gridNfoLayout
            self.__delegate.setNfoLayout(self.__gridNfoLayout)

    def gridNfoOverMinSize(self):
        """Return current grid over minimum size
        (Under this size, no information is displayed)
        """
        return self.__gridNfoOverMinSize

    def setGridNfoOverMinSize(self, value):
        """Set current fields displayed as grid information"""
        if not isinstance(value, int):
            raise EInvalidType("Given `value` must be a <int>")

        if value!=self.__gridNfoOverMinSize:
            self.__gridNfoOverMinSize=value
            self.__delegate.setNfoOverMinSize(self.__gridNfoOverMinSize)

    def markers(self):
        """Return a <BCFile> list of marked files"""
        markers=[]
        for rowIndex in range(self.__proxyModel.rowCount()):
            index=self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0))
            if self.__model.data(index, BCFileModel.ROLE_MARKER):
                markers.append(self.__model.data(index, BCFileModel.ROLE_FILE))
        return markers

    def setMarkers(self, markers):
        """Set marked files"""
        self.__model.setData([self.__proxyModel.mapToSource(self.__proxyModel.index(rowIndex, 0)) for rowIndex in range(self.__proxyModel.rowCount())], False, BCFileModel.ROLE_MARKER, False)
        self.__model.setData(markers, True, BCFileModel.ROLE_MARKER)



class BCViewFilesLvDelegate(QStyledItemDelegate):
    """Extend QStyledItemDelegate class to return properly cell size"""

    PADDING=6

    ICON_SIZE_INDEX_FONT_FACTOR=[0.75, 0.75, 0.8, 0.9, 0.95, 1.0]

    def __init__(self, parent=None):
        """Constructor, nothingspecial"""
        super(BCViewFilesLvDelegate, self).__init__(parent)
        self.__font=QFont(self.parent().font())
        self.__fontMetrics=QFontMetrics(self.__font)
        self.__iconSizeIndex=self.parent().iconSizeIndex()
        self.__nfoOverMinSize=2
        self.__nfoNbFields=1
        self.__nfoFields=[2]
        self.__nfoLayout=BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_NONE
        self.__iconSizeThumb=QSize(64, 64)
        self.__iconSizeGrid=QSize(BCViewFilesLvDelegate.PADDING+64, BCViewFilesLvDelegate.PADDING+64)
        self.__iconNfoRect=None

        self.__fontPixelSize=self.__font.pixelSize()
        self.__fontPointSizeF=self.__font.pointSizeF()

    def setIconSize(self, value):
        self.__iconSizeThumb=QSize(value, value)
        self.__iconSizeGrid=QSize(2*BCViewFilesLvDelegate.PADDING+value, 2*BCViewFilesLvDelegate.PADDING+value)
        self.__iconSizeIndex=self.parent().iconSizeIndex()

        if self.__fontPixelSize>-1:
            self.__font.setPixelSize(round(self.__fontPixelSize * BCViewFilesLvDelegate.ICON_SIZE_INDEX_FONT_FACTOR[self.__iconSizeIndex]))
        else:
            self.__font.setPointSizeF(round(self.__fontPointSizeF * BCViewFilesLvDelegate.ICON_SIZE_INDEX_FONT_FACTOR[self.__iconSizeIndex]))

        self.sizeHintChanged.emit(self.parent().model().createIndex(0, BCFileModel.COLNUM_ICON))

    def setNfoLayout(self, value):
        self.__nfoLayout=value
        self.sizeHintChanged.emit(self.parent().model().createIndex(0, BCFileModel.COLNUM_ICON))

    def setNfoOverMinSize(self, value):
        self.__nfoOverMinSize=value
        self.sizeHintChanged.emit(self.parent().model().createIndex(0, BCFileModel.COLNUM_ICON))

    def setNfoFields(self, value):
        self.__nfoNbFields=len(value)
        self.__nfoFields=value
        self.sizeHintChanged.emit(self.parent().model().createIndex(0, BCFileModel.COLNUM_ICON))

    def paint(self, painter, option, index):
        """Paint list item"""
        if index.column() == BCFileModel.COLNUM_ICON:
            # render full information
            self.initStyleOption(option, index)
            painter.setRenderHint(QPainter.Antialiasing)

            # icon as QIcon
            img=index.data(Qt.DecorationRole).pixmap(self.__iconSizeThumb)

            position=QPoint(option.rect.left()+(self.__iconSizeGrid.width()-img.width())//2, option.rect.top()+(self.__iconSizeGrid.height()-img.height())//2)

            isSelected=False
            color=None
            painter.setPen(QPen(Qt.NoPen))
            if (option.state & QStyle.State_Selected) == QStyle.State_Selected:
                isSelected=True
                if self.parent().hasFocus():
                    color=option.palette.color(QPalette.Active, QPalette.Highlight)
                else:
                    color=option.palette.color(QPalette.Inactive, QPalette.Highlight)

                colorText=option.palette.color(QPalette.HighlightedText)
            else:
                color=option.palette.color(QPalette.AlternateBase)
                colorText=option.palette.color(QPalette.Text)

            textPen=QPen(colorText)
            textPenS=QPen(color)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(option.rect, 6, 6)
            painter.drawPixmap(position, img)

            if not self.__iconNfoRect is None:
                textRect=QRect(option.rect.topLeft() + self.__iconNfoRect.topLeft(), self.__iconNfoRect.size())

                if self.__nfoLayout==BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_OVER:
                    colorOver=QColor(color)
                    colorOver.setAlphaF(0.65)
                    painter.setBrush(QBrush(colorOver))
                    painter.drawRect(textRect)

            if isSelected:
                # selected item
                color.setAlphaF(0.25)
                overRect=QRect(position, img.size())
                painter.fillRect(overRect, color)

            marked=index.data(BCFileModel.ROLE_MARKER)

            if not self.__iconNfoRect is None:
                if marked:
                    self.__font.setItalic(True)
                painter.setFont(self.__font)
                painter.setPen(textPen)
                for fieldIndex in self.__nfoFields:
                    fieldText=self.__fontMetrics.elidedText(index.data(BCFileModel.ROLE_GRIDNFO + fieldIndex), Qt.ElideRight, textRect.width())
                    if self.__nfoLayout==BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_OVER:
                        painter.setPen(textPenS)
                        painter.drawText(QRect(textRect.topLeft()+QPoint(1,1), textRect.size()), Qt.AlignLeft|Qt.AlignTop, fieldText)
                        painter.setPen(textPen)
                    painter.drawText(textRect, Qt.AlignLeft|Qt.AlignTop, fieldText)
                    textRect.setTop(textRect.top()+self.__fontMetrics.height())

            if marked:
                painter.setBrush(colorText)
                painter.drawPolygon(QPoint(option.rect.right(), option.rect.bottom()),
                                    QPoint(option.rect.right()-(BCViewFilesLvDelegate.PADDING<<1), option.rect.bottom()),
                                    QPoint(option.rect.right(), option.rect.bottom()-(BCViewFilesLvDelegate.PADDING<<1)))

            return

        QStyledItemDelegate.paint(self, painter, option, index)

    def sizeHint(self, option, index):
        """Calculate size for items"""
        if index.column() == BCFileModel.COLNUM_ICON:
            if self.__nfoLayout==BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_NONE or self.parent().iconSizeIndex()<self.__nfoOverMinSize:
                self.__iconNfoRect=None
                return self.__iconSizeGrid

            height=self.__nfoNbFields * self.__fontMetrics.height()
            width=self.__iconSizeThumb.width()

            if self.__nfoLayout==BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_OVER:
                self.__iconNfoRect=QRect(BCViewFilesLvDelegate.PADDING, self.__iconSizeGrid.height() - BCViewFilesLvDelegate.PADDING - height, width, height)
                return self.__iconSizeGrid
            elif self.__nfoLayout==BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_BOTTOM:
                self.__iconNfoRect=QRect(BCViewFilesLvDelegate.PADDING, self.__iconSizeThumb.height()+2*BCViewFilesLvDelegate.PADDING, width, height)
                return QSize(self.__iconSizeGrid.width(), self.__iconSizeGrid.height() + self.__iconNfoRect.height() + BCViewFilesLvDelegate.PADDING)
            elif self.__nfoLayout==BCViewFilesLv.OPTION_LAYOUT_GRIDINFO_RIGHT:
                self.__iconNfoRect=QRect(self.__iconSizeThumb.width() + 2 * BCViewFilesLvDelegate.PADDING, BCViewFilesLvDelegate.PADDING, width, height)
                return QSize(self.__iconSizeThumb.width()*2+3*BCViewFilesLvDelegate.PADDING, self.__iconSizeGrid.height())

            return self.__iconSizeGrid

        return QStyledItemDelegate.sizeHint(self, option, index)
