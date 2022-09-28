# -----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2019-2022 - Grum999
# -----------------------------------------------------------------------------
# SPDX-License-Identifier: GPL-3.0-or-later
#
# https://spdx.org/licenses/GPL-3.0-or-later.html
# -----------------------------------------------------------------------------
# A Krita plugin designed to manage documents
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# The bcclipboard module provides classes used to manage clipboard content
#
# Main classes from this module
#
# - BCClipboardItem:
#       Base classe that provides basic methods for clipboard items
#       Normally must be overrided according to content type
#       - BCClipboardItemUrl
#       - BCClipboardItemFile
#       - BCClipboardItemImg
#       - ...
#
# - BCClipboard:
#       Manage clipboard
#       (get/set clipboard content according to item type)
#
# - BCClipboardModel & BCClipboardDelegate
#       To be used with QListView to get visual clipboard items managed content
#
# -----------------------------------------------------------------------------

import os
import time
import datetime
import hashlib
import json
import re
import shutil
import sys

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )

from .bcfile import (
        BCBaseFile,
        BCFile,
        BCFileThumbnailSize
    )
from .bcdownloader import BCDownloader

from bulicommander.pktk.modules.strutils import bytesSizeToStr
from bulicommander.pktk.modules.utils import Debug
from bulicommander.pktk.modules.imgutils import (
        buildIcon,
        qImageToPngQByteArray
    )
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )


class BCClipboardItem(QObject):
    """An item stored in clipboard"""
    persistentChanged = Signal(QObject)

    def __init__(self, hashValue, origin=None, timestamp=None, persistent=None):
        super(BCClipboardItem, self).__init__(None)
        # item uid
        self.__hashValue = hashValue
        # Date/time at which item as been created/updated
        if isinstance(timestamp, float):
            self.__timestamp = timestamp
        else:
            self.__timestamp = time.time()
        # origin of data
        self.__origin = ''
        # define if data are persistent or not
        if isinstance(persistent, bool):
            self.__persistent = persistent
        else:
            self.__persistent = BCClipboard.optionCacheDefaultPersistent()
        # image size
        self.__imageSize = QSize()
        # size in cache
        self.__cacheSize = -1

        # BCFile of image in cache
        self.__file = None

        self.setOrigin(origin)

    def __repr__(self):
        return (f'<{self.type()}({self.__hashValue}, '
                f'"{self.origin()}", '
                f'"{datetime.datetime.fromtimestamp(self.__timestamp):%Y-%m-%d %H:%M:%S}", '
                f'{self.imageSize().width()}x{self.imageSize().height()}, '
                f'{self.cacheSize()})>')

    def calculateCacheSize(self):
        """Calculate size of files in cache"""
        self.__cacheSize = 0
        for root, dirs, files in os.walk(self.cachePath()):
            for name in files:
                if re.search(fr'^{self.hash()}\..*', name):
                    self.__cacheSize += os.path.getsize(os.path.join(root, name))

    def cachePath(self):
        """Return current cache path for item"""
        if self.persistent():
            return BCClipboard.persistentCacheDirectory()
        else:
            return BCClipboard.sessionCacheDirectory()

    def dataContentForCache(self):
        """Return data that have to be saved in cache file

        return value is a dictionary key=value
        """
        return {
                'timestamp': self.__timestamp,
                'origin': self.__origin,
                'type': self.type(),
                'imageSize.width': self.__imageSize.width(),
                'imageSize.height': self.__imageSize.height()
            }

    def updateTimeStamp(self, origin=None):
        """Update time stamp with current date/time"""
        self.__timestamp = time.time()
        self.setOrigin(origin)
        # update cache file with timestamp
        # note: use base class method and not instance method to be sure to not
        #       save anything else than json data
        BCClipboardItem.saveToCache(self)

    def timestamp(self):
        """Return timestamp for item"""
        return self.__timestamp

    def hash(self):
        """Return hash for item"""
        return self.__hashValue

    def origin(self):
        """Return origin for item"""
        return self.__origin

    def setOrigin(self, value):
        """Set origin for item"""
        if isinstance(value, str):
            self.__origin = value

    def persistent(self):
        """Return if clipboard item is persistent or not"""
        return self.__persistent

    def setPersistent(self, value):
        """Set if clipboard item is persistent or not"""
        if not isinstance(value, bool):
            raise EInvalidType('Given `value` must be a <bool>')

        # move file: persistentCacheDirectory<-->sessionCacheDirectory
        if value != self.__persistent:
            # do something only if state is changed
            filesToProcess = []
            if self.__persistent:
                # move from persistentCacheDirectory() to sessionCacheDirectory()
                targetPath = BCClipboard.sessionCacheDirectory()
                for root, dirs, files in os.walk(BCClipboard.persistentCacheDirectory()):
                    filesToProcess += [os.path.join(root, name) for name in files if re.search(fr'^{self.hash()}\..*', name)]
            else:
                # move from sessionCacheDirectory() to persistentCacheDirectory()
                targetPath = BCClipboard.persistentCacheDirectory()
                for root, dirs, files in os.walk(BCClipboard.sessionCacheDirectory()):
                    filesToProcess += [os.path.join(root, name) for name in files if re.search(fr'^{self.hash()}\..*', name)]

            for file in filesToProcess:
                try:
                    shutil.move(file, targetPath)
                except Exception as e:
                    Debug.print('[BCClipboardItem.setPersistent] Unable to move file {0} to {1}: {2}', file, targetPath, f"{e}")

            self.__persistent = value
            self.updateBcFile()
            self.persistentChanged.emit(self)

    def saveToCache(self):
        """Save description to cache as a JSON file"""
        data = self.dataContentForCache()

        fileName = os.path.join(self.cachePath(), f'{self.hash()}.json')

        with open(fileName, 'w') as file:
            try:
                file.write(json.dumps(data, indent=4, sort_keys=True))
            except Exception as e:
                Debug.print('[BCClipboardItem.saveToCache] Unable to save file {0}: {1}', fileName, f"{e}")
                return False

        return True

    def type(self):
        """Return type of item"""
        return self.__class__.__name__

    def imageSize(self):
        """Return image size, if any"""
        return self.__imageSize

    def setImageSize(self, size):
        """set image size"""
        if not isinstance(size, QSize):
            raise EInvalidType('Given `value` must be a QSize()')
        self.__imageSize = size

    def cacheSize(self):
        """Return size of files in cache"""
        if self.__cacheSize == -1:
            # not yet calculated, do it
            self.calculateCacheSize()
        return self.__cacheSize

    def file(self):
        """A BCFile instance of file in cache

        None if there's no file in cache
        """
        return self.__file

    def setFile(self, fileName):
        """Set BCFile from given file name"""
        self.__file = BCFile(fileName)

    def updateBcFile(self):
        pass

    def fileName(self, full=True):
        """Return current fileName"""
        if full:
            return os.path.join(self.cachePath(), f'{self.hash()}.png')
        else:
            return f'{self.hash()}.png'

    def contentBackToClipboard(self):
        """return content to push back into clipboard

        returned content is a list of tuple (data, mime-type)
        """
        return None


class BCClipboardItemUrl(BCClipboardItem):
    """An url stored in clipboard"""
    downloadFinished = Signal(QObject)
    downloadProgress = Signal(QObject)

    URL_STATUS_NOTDOWNLOADED = 0
    URL_STATUS_DOWNLOADING = 1
    URL_STATUS_DOWNLOADED = 2
    URL_STATUS_DOWNLOADERROR = 3

    @staticmethod
    def new(hash, options):
        """Create a new URL item from options

        options is a dictionnary with the following key:
            "origin"
            "imageSize.height"
            "imageSize.width"
            "timestamp"
            "url.url"
            "url.isValid"
            "url.downloadSize"
        """
        url = None
        origin = None
        timestamp = None
        persistent = True
        if isinstance(options.get('url.url', None), str):
            url = QUrl(options['url.url'])
        if isinstance(options.get('origin', None), str):
            origin = options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp = options['timestamp']
        if isinstance(options.get('persistent', None), bool):
            persistent = options['persistent']

        returned = BCClipboardItemUrl(hash, url, origin, timestamp, False, persistent)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options.get('imageSize.width', None), int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        if isinstance(options.get('url.downloadSize', None), int):
            returned.setDownloadSize(options['url.downloadSize'])

        return returned

    def __init__(self, hashValue, url, origin=None, timestamp=None, saveInCache=True, persistent=None):
        super(BCClipboardItemUrl, self).__init__(hashValue, origin, timestamp, persistent)

        if not isinstance(url, QUrl):
            raise EInvalidType('Given `url` must be a QUrl')

        self.__fileName = f'{self.hash()}{os.path.splitext(url.fileName())[1]}'
        self.__url = url
        self.__urlIsValid = True
        self.__downloader = None
        self.__pctDelta = 0
        self.__downloadSize = 0
        self.__downloadErrorCode = 0
        self.__downloadErrorStr = 0
        if self.urlIsLoaded():
            self.__status = BCClipboardItemUrl.URL_STATUS_DOWNLOADED
            self.updateBcFile()
        else:
            self.__status = BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED

        if saveInCache:
            self.saveToCache()

    def __repr__(self):
        return f'{super(BCClipboardItemUrl, self).__repr__()[:-2]}, "{self.__url.url()}", {self.__urlIsValid}, {self.urlIsLoaded()})>'

    def __downloadFinished(self, error=0, errorStr=''):
        """Download has finished

        Move file from download directory to cache directory
        Update BCFile
        Save current url properties to cache
        Emit signal for clipboard url
        """
        if error == 0:
            try:
                shutil.move(self.__downloader.target(), self.cachePath())
            except Exception as e:
                Debug.print('[BCClipboardItem.__downloadFinished] Unable to move file {0} to {1}: {2}', self.__downloader.target(), self.cachePath(), f"{e}")
                self.__status = BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED
                self.downloadFinished.emit(self)
                return

            self.__status = BCClipboardItemUrl.URL_STATUS_DOWNLOADED
            self.updateBcFile()
            if self.file():
                self.setImageSize(self.file().imageSize())
            self.saveToCache()
            self.calculateCacheSize()
        else:
            # operation cancelled (error=5) or download error
            # maybe need to manage this a little bit more...
            if os.path.exists(self.__downloader.target()):
                try:
                    os.remove(self.__downloader.target())
                except Exception:
                    Debug.print('[BCDownloader.downloadStop] unable to remove target file {0}: {1}', self.__downloader.target(), e)

            self.__downloadErrorCode = error
            self.__downloadErrorStr = errorStr
            self.__status = BCClipboardItemUrl.URL_STATUS_DOWNLOADERROR
            self.setImageSize(QSize(-1, -1))
            self.saveToCache()
            self.calculateCacheSize()

        self.downloadFinished.emit(self)
        try:
            self.__downloader.finished.disconnect()
        except Exception:
            pass

        try:
            self.__downloader.progress.disconnect()
        except Exception:
            pass
        self.__downloader = None

    def __downloadProgress(self, bytesReceived, bytesTotal):
        """Download is in progress, emit signal for clipboard url"""
        if self.__downloadSize == 0:
            self.__downloadSize = bytesTotal
            self.saveToCache()
        pct = self.__downloader.downloadProgress()[0]
        if (pct - self.__pctDelta) > 0.5:
            # emit signal (to model) only if delta on download pct is greater than 0.5
            self.__pctDelta = pct
            self.downloadProgress.emit(self)

    def dataContentForCache(self):
        """Return data that have to be saved in cache

        return value is a dictionary key=value
        """
        returned = super(BCClipboardItemUrl, self).dataContentForCache()

        returned['url.url'] = self.__url.url()
        returned['url.isValid'] = self.__urlIsValid
        returned['url.isLoaded'] = self.urlIsLoaded()
        returned['url.loadedFileName'] = self.__fileName
        returned['url.downloadSize'] = self.__downloadSize

        return returned

    def url(self):
        """Return current url as QUrl instance"""
        return self.__url

    def urlIsValid(self):
        """Return if url is valid or not"""
        return self.__urlIsValid

    def setUrlIsValid(self, value):
        """set if url is valid or not"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
        self.__urlIsValid = value

    def urlIsLoaded(self):
        """Return if url content is loaded or not"""
        fileName = self.fileName(True)
        exist = os.path.exists(fileName)
        if exist and self.__downloadSize > 0:
            fileSize = os.path.getsize(fileName)
            if fileSize != self.__downloadSize:
                # file size is not expected size
                # delete file to force reload
                try:
                    os.remove(fileName)
                except Exception:
                    pass
                return False

        return exist

    def urlStatus(self):
        """Return if url is downloaded, downloading, not downloaded"""
        return self.__status

    def fileName(self, full=True):
        """Return file name for expected loaded file"""
        if full:
            return os.path.join(self.cachePath(), self.__fileName)
        else:
            return self.__fileName

    def updateBcFile(self):
        """Update BCFile according to current clipboard item properties"""
        imgCacheFileName = self.fileName(True)
        if os.path.exists(imgCacheFileName):
            self.setFile(imgCacheFileName)
            if self.__status != BCClipboardItemUrl.URL_STATUS_DOWNLOADING:
                self.__status = BCClipboardItemUrl.URL_STATUS_DOWNLOADED
            if self.imageSize().width() == -1 or self.imageSize().height() == -1:
                self.setImageSize(self.file().imageSize())
                self.saveToCache()
        elif self.__status != BCClipboardItemUrl.URL_STATUS_DOWNLOADING:
            self.__status = BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED

    def download(self):
        """Start download"""
        if self.__status == BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED:
            self.__pctDelta = 0
            self.__status = BCClipboardItemUrl.URL_STATUS_DOWNLOADING
            self.__downloader = BCDownloader(self.__url, os.path.join(BCClipboard.downloadingCacheDirectory(), self.fileName(False)))
            self.__downloader.finished.connect(self.__downloadFinished)
            self.__downloader.progress.connect(self.__downloadProgress)
            self.__downloader.download()

    def downloadStop(self):
        """Stop download"""
        if self.__status == BCClipboardItemUrl.URL_STATUS_DOWNLOADING and self.__downloader:
            self.__downloader.downloadStop()

    def downloader(self):
        """Return current downloader, if set"""
        return self.__downloader

    def downloadSize(self):
        """Recturn expected download file size"""
        return self.__downloadSize

    def downloadErrorCode(self):
        """Return download error code"""
        return self.__downloadError

    def downloadErrorStr(self):
        """Return download error code as human readble string"""
        return self.__downloadErrorStr

    def setDownloadSize(self, value):
        """Set expected download file size"""
        self.__downloadSize = value

    def contentBackToClipboard(self):
        """Push item back into clipboard"""
        returned = [(self.url(), 'text/uri-list'), (self.url().url(), 'text/plain')]

        if os.path.exists(self.fileName()):
            with open(self.fileName(), 'rb') as fHandle:
                data = fHandle.read()

            if data:
                returned.append((data, QMimeDatabase().mimeTypeForFile(self.fileName()).name()))

        return returned


class BCClipboardItemFile(BCClipboardItem):
    """A file name stored in clipboard"""

    @staticmethod
    def new(hash, options):
        """Create a new FILE item from options

        options is a dictionnary with the following key:
            "origin"
            "imageSize.height"
            "imageSize.width"
            "timestamp"
            "fileName"
        """
        fileName = None
        origin = None
        timestamp = None
        persistent = True
        if isinstance(options.get('fileName', None), str):
            fileName = options['fileName']
        if isinstance(options.get('origin', None), str):
            origin = options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp = options['timestamp']
        if isinstance(options.get('persistent', None), bool):
            persistent = options['persistent']

        returned = BCClipboardItemFile(hash, fileName, origin, timestamp, False, persistent)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options.get('imageSize.width', None), int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        if not returned.fileExists():
            return None

        return returned

    def __init__(self, hashValue, fileName, origin=None, timestamp=None, saveInCache=True, persistent=None):
        super(BCClipboardItemFile, self).__init__(hashValue, origin, timestamp, persistent)

        self.__fileName = os.path.normpath(fileName)

        if saveInCache:
            self.saveToCache()

        self.updateBcFile()

    def __repr__(self):
        return f'{super(BCClipboardItemFile, self).__repr__()[:-2]}, "{self.__fileName}", {self.fileExists()})>'

    def dataContentForCache(self):
        """Return data that have to be saved in cache

        return value is a dictionary key=value
        """
        returned = super(BCClipboardItemFile, self).dataContentForCache()

        returned['fileName'] = self.__fileName

        return returned

    def fileName(self, full=True):
        """Return current fileName"""
        if full:
            return self.__fileName
        else:
            return os.path.basename(self.__fileName)

    def fileExists(self):
        """Return if fileName exists or not"""
        return os.path.exists(self.__fileName)

    def updateBcFile(self):
        """Update BCFile according to current clipboard item properties"""
        if self.fileExists():
            self.setFile(self.__fileName)
            if self.imageSize().width() == -1 or self.imageSize().height() == -1:
                self.setImageSize(self.file().imageSize())
                self.saveToCache()
        else:
            # file doesn't exist...
            return None

    def contentBackToClipboard(self):
        """Push item back into clipboard"""
        returned = [(QUrl(f'file://{self.fileName()}'), 'text/uri-list'), (self.fileName(), 'text/plain')]

        if os.path.isfile(self.fileName()):
            data = None
            with open(self.fileName(), 'rb') as fHandle:
                data = fHandle.read()

            if data:
                returned.append((data, QMimeDatabase().mimeTypeForFile(self.fileName()).name(), self.file()))

        return returned


class BCClipboardItemImg(BCClipboardItem):
    """An image stored in clipboard"""

    @staticmethod
    def new(hash, options):
        """Create a new Image item from options

        options is a dictionnary with the following key:
            "origin"
            "imageSize.height"
            "imageSize.width"
            "timestamp"
        """
        urlOrigin = None
        origin = None
        timestamp = None
        persistent = True
        if isinstance(options.get('urlOrigin', None), str) and options['urlOrigin'] != '':
            urlOrigin = QUrl(options['urlOrigin'])
        if isinstance(options.get('origin', None), str):
            origin = options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp = options['timestamp']
        if isinstance(options.get('persistent', None), bool):
            persistent = options['persistent']

        returned = BCClipboardItemImg(hash, None, urlOrigin, origin, timestamp, False, persistent)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options['imageSize.width'], int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        imgCacheFileName = os.path.join(returned.cachePath(), f'{hash}.png')
        if not os.path.exists(imgCacheFileName):
            # image file doesn't exist in cache, don't try to create item
            return None

        return returned

    def __init__(self, hashValue, image, urlOrigin=None, origin=None, timestamp=None, saveInCache=True, persistent=None):
        super(BCClipboardItemImg, self).__init__(hashValue, origin, timestamp, persistent)

        self.__urlOrigin = None

        if isinstance(urlOrigin, QUrl):
            self.__urlOrigin = urlOrigin
        elif isinstance(urlOrigin, str):
            self.__urlOrigin = QUrl(urlOrigin)

        if image:
            if not isinstance(image, QImage):
                raise EInvalidType('Given `image` must be a QImage')
            self.setImageSize(image.size())

            if saveInCache:
                self.saveToCache(image)

        self.updateBcFile()

    def urlOrigin(self):
        """Return url from which image has been copied, if any"""
        return self.__urlOrigin

    def setUrlOrigin(self, urlOrigin):
        """set url from which image has been copied, if any"""
        if isinstance(urlOrigin, str):
            self.__urlOrigin = QUrl(urlOrigin)
        elif isinstance(urlOrigin, QUrl):
            self.__urlOrigin = urlOrigin

    def dataContentForCache(self):
        """Return data that have to be saved in cache

        return value is a dictionary key=value
        """
        returned = super(BCClipboardItemImg, self).dataContentForCache()

        if isinstance(self.__urlOrigin, QUrl):
            returned['url.origin'] = self.__urlOrigin.url()
        else:
            returned['url.origin'] = None

        return returned

    def saveToCache(self, image):
        """Save image to cache"""
        super(BCClipboardItemImg, self).saveToCache()

        return BCClipboard.saveQImage(os.path.join(self.cachePath(), f'{self.hash()}.png'), image, False)

    def updateBcFile(self):
        """Update BCFile according to current clipboard item properties"""
        imgCacheFileName = self.fileName(True)
        if os.path.exists(imgCacheFileName):
            self.setFile(imgCacheFileName)

    def contentBackToClipboard(self):
        """Push item back into clipboard"""
        returned = []
        if os.path.exists(self.fileName()):
            data = None
            with open(self.fileName(), 'rb') as fHandle:
                data = fHandle.read()

            if data:
                returned.append((data, 'image/png'))

        if self.urlOrigin():
            returned.append((self.urlOrigin(), 'text/uri-list'))

        return returned


class BCClipboardItemSvg(BCClipboardItem):
    """A SVG image stored in clipboard"""

    @staticmethod
    def new(hash, options):
        """Create a new SVG item from options

        options is a dictionnary with the following key:
            "origin"
            "imageSize.height"
            "imageSize.width"
            "timestamp"
        """
        origin = None
        timestamp = None
        persistent = True
        if isinstance(options.get('origin', None), str):
            origin = options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp = options['timestamp']
        if isinstance(options.get('persistent', None), bool):
            persistent = options['persistent']

        returned = BCClipboardItemSvg(hash, None, None, origin, timestamp, False, persistent)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options.get('imageSize.width', None), int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        if not os.path.exists(os.path.join(returned.cachePath(), f'{hash}.svg')):
            # svg file doesn't exist in cache, don't try to create item
            return None

        return returned

    def __init__(self, hashValue, svgData, image=None, origin=None, timestamp=None, saveInCache=True, persistent=None):
        super(BCClipboardItemSvg, self).__init__(hashValue, origin, timestamp, persistent)
        if image and not isinstance(image, QImage):
            raise EInvalidType('Given `image` must be a QImage')

        if svgData and saveInCache:
            self.saveToCache(svgData, image)

        self.updateBcFile()

    def saveToCache(self, svgData, image):
        """Save SVG+image data to cache"""
        saved = super(BCClipboardItemSvg, self).saveToCache()

        if isinstance(image, QImage):
            saved &= BCClipboard.saveQImage(os.path.join(self.cachePath(), f'{self.hash()}.png'), image)

        with open(self.fileName(True), 'wb') as file:
            try:
                file.write(svgData)
            except Exception as e:
                Debug.print('[BCClipboardItemSvg.saveToCache] Unable to save file {0}: {1}', self.fileName(True), f"{e}")
                saved = False

        return saved

    def fileName(self, full=True):
        """Return current fileName"""
        if full:
            return os.path.join(self.cachePath(), f'{self.hash()}.svg')
        else:
            return f'{self.hash()}.svg'

    def contentBackToClipboard(self):
        """Push item back into clipboard"""
        returned = []

        if os.path.exists(self.fileName()):
            data = None
            with open(self.fileName(), 'rb') as fHandle:
                data = fHandle.read()

            if data:
                returned.append((data, 'image/svg'))

        return returned

    def updateBcFile(self):
        """Update BCFile according to current clipboard item properties"""
        imgCacheFileName = self.fileName(True)
        if os.path.exists(imgCacheFileName):
            self.setFile(imgCacheFileName)


class BCClipboardItemKra(BCClipboardItem):
    """A SVG image stored in clipboard"""

    @staticmethod
    def new(hash, options):
        """Create a new SVG item from options

        options is a dictionnary with the following key:
            "origin"
            "imageSize.height"
            "imageSize.width"
            "timestamp"
        """
        origin = None
        timestamp = None
        persistent = True
        if isinstance(options.get('origin', None), str):
            origin = options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp = options['timestamp']
        if isinstance(options.get('persistent', None), bool):
            persistent = options['persistent']

        returned = BCClipboardItemKra(hash, None, None, origin, timestamp, False, persistent)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options.get('imageSize.width', None), int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        imgCacheFileName = os.path.join(returned.cachePath(), f'{hash}.kra')
        if not os.path.exists(imgCacheFileName):
            # kra file doesn't exist in cache, don't try to create item
            return None

        return returned

    def __init__(self, hashValue, kraData, image=None, origin=None, timestamp=None, saveInCache=True, persistent=None):
        super(BCClipboardItemKra, self).__init__(hashValue, origin, timestamp, persistent)
        if image and not isinstance(image, QImage):
            raise EInvalidType('Given `image` must be a QImage')

        if image:
            self.setImageSize(image.size())

        if kraData:
            self.saveToCache(kraData, image)

        self.updateBcFile()

    def saveToCache(self, kraData, image):
        """Save kra information+image to cache"""
        saved = super(BCClipboardItemKra, self).saveToCache()

        if isinstance(image, QImage):
            fileName = os.path.join(self.cachePath(), f'{self.hash()}.png')
            saved &= BCClipboard.saveQImage(fileName, image)

        fileName = self.fileName(True)
        with open(fileName, 'wb') as file:
            try:
                file.write(kraData)
            except Exception as e:
                Debug.print('[BCClipboardItemKra.saveToCache] Unable to save file {0}: {1}', fileName, f"{e}")
                saved = False

        return saved

    def updateBcFile(self):
        """Update BCFile according to current clipboard item properties"""
        imgCacheFileName = os.path.join(self.cachePath(), f'{self.hash()}.png')
        if os.path.exists(imgCacheFileName):
            # prefer to use png file for thumbnail
            self.setFile(imgCacheFileName)
        else:
            imgCacheFileName = os.path.join(self.cachePath(), f'{self.hash()}.kra')
            if os.path.exists(imgCacheFileName):
                # prefer to use png file for thumbnail
                self.setFile(imgCacheFileName)

    def fileName(self, full=True):
        """Return current fileName"""
        if full:
            return os.path.join(self.cachePath(), f'{self.hash()}.kra')
        else:
            return f'{self.hash()}.kra'

    def contentBackToClipboard(self):
        """Push item back into clipboard"""
        returned = []

        if os.path.exists(self.fileName()):
            data = None
            with open(self.fileName(), 'rb') as fHandle:
                data = fHandle.read()

            if data:
                returned.append((data, self.origin()))

        fileName = os.path.join(self.cachePath(), f'{self.hash()}.png')
        if os.path.exists(fileName):
            with open(fileName, 'rb') as fHandle:
                data = fHandle.read()
            if data:
                returned.append((data, 'image/png'))

        return returned


class BCClipboard(QObject):
    """Manage clipboard content"""
    updated = Signal()
    updateAdded = Signal(list)
    updateRemoved = Signal(list)
    updateDownload = Signal(bool, QObject)
    updatePersistent = Signal(QObject)

    __INITIALISED = False
    __OPTION_CACHE_PATH = ''
    __OPTION_CACHE_MAXSIZE = 1024000000  # 1GB
    __OPTION_URL_AUTOLOAD = False
    __OPTION_CACHE_DEFAULT_PERSISTENT = False
    __OPTION_URL_PARSE_TEXTHTML = True

    @staticmethod
    def initialiseCache(bcCachePath=None):
        """Initialise clipboard cache

        Clipboard cache is the place where image from clipboard and/or loaded from url
        in clipboard are stored

        By default, cache will be defined into user cache directory
        If `bcCachePath` is provided, it will define the cache directory to use

        If directory doesn't exist, it will be created
        """

        if bcCachePath is None or bcCachePath == '':
            bcCachePath = os.path.join(QStandardPaths.writableLocation(QStandardPaths.CacheLocation), "bulicommander", "clipboard")
        else:
            bcCachePath = os.path.expanduser(bcCachePath)

        if not isinstance(bcCachePath, str):
            raise EInvalidType("Given `bcCachePath` must be a valid <str> ")

        try:
            BCClipboard.__OPTION_CACHE_PATH = bcCachePath
            os.makedirs(bcCachePath, exist_ok=True)

            os.makedirs(BCClipboard.persistentCacheDirectory(), exist_ok=True)
            os.makedirs(BCClipboard.sessionCacheDirectory(), exist_ok=True)
            os.makedirs(BCClipboard.downloadingCacheDirectory(), exist_ok=True)
        except Exception as e:
            Debug.print('[BCClipboard.initialiseCache] Unable to create directory: {0}', f"{e}")
            return

        # cleanup downloading directory to ensure there's nothing left inside...
        for root, dirs, files in os.walk(BCClipboard.downloadingCacheDirectory()):
            for fileName in files:
                try:
                    os.remove(os.path.join(root, fileName))
                    updated = True
                except Exception as e:
                    Debug.print('[BCClipboard.cacheDownloadFlush] Unable to delete file {0}: {1}', fileName, f"{e}")

        BCClipboard.__INITIALISED = True

    @staticmethod
    def persistentCacheDirectory():
        """Return path for persistent clipboard data"""
        if BCClipboard.__OPTION_CACHE_PATH == '':
            raise EInvalidStatus("BCClipboard hasn't been initialized!")
        return os.path.join(BCClipboard.__OPTION_CACHE_PATH, 'persistent')

    @staticmethod
    def sessionCacheDirectory():
        """Return path for non persistent clipboard data"""
        if BCClipboard.__OPTION_CACHE_PATH == '':
            raise EInvalidStatus("BCClipboard hasn't been initialized!")
        return os.path.join(BCClipboard.__OPTION_CACHE_PATH, 'session')

    @staticmethod
    def downloadingCacheDirectory():
        """Return path for downloading data

        When a download is in progress, this allows to change cache/target (persistent/session)
        without interupting current download
        """
        if BCClipboard.__OPTION_CACHE_PATH == '':
            raise EInvalidStatus("BCClipboard hasn't been initialized!")
        return os.path.join(BCClipboard.__OPTION_CACHE_PATH, 'downloading')

    @staticmethod
    def optionCachePath():
        """Return current defined path for cache"""
        return BCClipboard.__OPTION_CACHE_PATH

    @staticmethod
    def optionCacheMaxSize():
        """Return current defined maximum cache size (in bytes)"""
        return BCClipboard.__OPTION_CACHE_MAXSIZE

    @staticmethod
    def setOptionCacheMaxSize(value):
        """Set current maximum cache size (in bytes)"""
        if not isinstance(value, int):
            raise EInvalidType("Given `value` must be a <int>")
        BCClipboard.__OPTION_CACHE_MAXSIZE = value

    @staticmethod
    def optionUrlParseTextHtml():
        """Return if text/html clipboard content are parsed to find urls"""
        return BCClipboard.__OPTION_URL_PARSE_TEXTHTML

    @staticmethod
    def setOptionUrlParseTextHtml(value):
        """Set if text/html clipboard content are parsed to find urls"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
        BCClipboard.__OPTION_URL_PARSE_TEXTHTML = value

    @staticmethod
    def optionUrlAutoload():
        """Return if url are loaded automatically or not"""
        return BCClipboard.__OPTION_URL_AUTOLOAD

    @staticmethod
    def setOptionUrlAutoload(value):
        """Set if url are loaded automatically or not"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
        if value != BCClipboard.__OPTION_URL_AUTOLOAD:
            BCClipboard.__OPTION_URL_AUTOLOAD = value

    @staticmethod
    def optionCacheDefaultPersistent():
        """Return if items are persistent by default or not"""
        return BCClipboard.__OPTION_CACHE_DEFAULT_PERSISTENT

    @staticmethod
    def setOptionCacheDefaultPersistent(value):
        """Set if items are persistent by default or not"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
        BCClipboard.__OPTION_CACHE_DEFAULT_PERSISTENT = value

    @staticmethod
    def saveQImage(fileName, image, resize=False):
        """Save QImage as png content

        Use a method to ensure all image are saved using the same parameters
        """
        if not isinstance(image, QImage):
            raise EInvalidType('Given `image` must be a <QImage>')

        if resize:
            return image.scaled(QSize(512, 512), Qt.KeepAspectRatio, Qt.SmoothTransformation).save(fileName, b'png', 50)
        else:
            return image.save(fileName, b'png', 50)

    def __init__(self, enabled=True):
        """Initialize object"""
        super(BCClipboard, self).__init__(None)

        # store everything in a dictionary
        # key = hashValue (SHA1) of clipboard content
        # value = BCClipboardItem
        self.__pool = {}

        # instance to application clipboard
        self.__clipboard = QGuiApplication.clipboard()

        # regular expressions used to parse HTML and find urls
        self.__reHtmlImg = QRegularExpression(r'(?im)<img(?:\s.*\s|\s+)(?:src="(?<url1>https?:\/\/[^"]+?\.(?:jpeg|jpg|png|gif|svg|webp|kra)[^"]*?)"|'
                                              r'src=\'(?<url2>https?:\/\/[^\']+?\.(?:jpeg|jpg|png|gif|svg|webp|kra)[^\']*?)\')[^>]*?>')
        self.__reHtmlLink = QRegularExpression(r'(?im)<a(?:\s.*\s|\s+)(?:href="(?<url1>https?:\/\/[^"]+?\.(?:jpeg|jpg|png|gif|svg|webp|kra)[^"]*?)"|'
                                               r'href=\'(?<url2>https?:\/\/[^\']+?\.(?:jpeg|jpg|png|gif|svg|webp|kra)[^\']*?)\')[^>]*?>')

        # regular expression used to parse PLAIN TEXT and find urls
        self.__reTextUrl = QRegularExpression(r'(?im)(["\'])?(?<url>https?:\/\/[^\s]+\.(?:jpeg|jpg|png|svg|gif|webp|kra)(?:\?[^\s]*)?)\1?.*')

        # regular expression used to parse FILE path/name
        self.__reTextFile = QRegularExpression(r'(?i)\.(?:jpeg|jpg|png|svg|gif|webp|kra)$')

        self.__totalCacheSizeP = 0
        self.__totalCacheSizeS = 0

        self.__totalCacheItemP = 0
        self.__totalCacheItemS = 0

        self.__stats = {
                'persistent': 0,
                'session': 0,
                'downloading': 0,

                'urls': 0,
                'files': 0,
                'images': 0,
                'kraNodes': 0,
                'kraSelection': 0
            }

        self.__enabled = False
        self.__temporaryDisabled = False

        # list of added hash
        self.__updateAdd = []
        self.__updateRemove = []

        self.cacheSessionFlush()
        self.__poolFromCache()
        self.setEnabled(enabled)

    def __repr__(self):
        return f"<BCClipboard({self.length()})>"

    def __urlDownloadInProgress(self, clipboardUrlItem):
        self.updateDownload.emit(False, clipboardUrlItem)

    def __urlDownloadFinished(self, clipboardUrlItem):
        self.updateDownload.emit(True, clipboardUrlItem)
        self.updated.emit()

    def __emitUpdateAdded(self):
        """Emit update signal with list of hash to update

        An empty list mean a complete update
        """
        items = self.__updateAdd.copy()
        self.__updateAdd = []
        self.updateAdded.emit(items)
        self.updated.emit()

    def __emitUpdateRemoved(self):
        """Emit update signal with list of hash to update

        An empty list mean a complete update
        """
        items = self.__updateRemove.copy()
        self.__updateRemove = []
        self.updateRemoved.emit(items)
        self.updated.emit()

    def __emitPersistentChanged(self, clipboardItem):
        """persistent value has been modified in clipboard item, transmit signal to model"""
        self.updatePersistent.emit(clipboardItem)
        self.updated.emit()

    def __getHash(self, data):
        """Return hash for data"""
        hash = hashlib.md5()
        hash.update(data)
        return hash.hexdigest()

    def __inPool(self, hashValue):
        """Return True if hashValue is already in pool, otherwise False"""
        return (hashValue in self.__pool)

    def __updateTimeStamp(self, hashValue, origin=None, urlOrigin=None):
        """Update time stamp for clipboard item defined by given hashValue"""
        if hashValue in self.__pool:
            if isinstance(self.__pool[hashValue], BCClipboardItemImg):
                self.__pool[hashValue].setUrlOrigin(urlOrigin)
            self.__pool[hashValue].updateTimeStamp(origin)
            return True

        return False

    def __poolFromCache(self):
        """Load pool content from cache"""

        self.__pool = {}

        for root, dirs, files in os.walk(BCClipboard.persistentCacheDirectory()):
            for name in files:
                if result := re.search(r'^(.*)\.json$', name):
                    hash = result.groups()[0]

                    fileName = os.path.join(root, name)

                    with open(fileName, 'r') as file:
                        try:
                            jsonAsStr = file.read()
                        except Exception as e:
                            Debug.print('[BCClipboard.__poolFromCache] Unable to load file {0}: {1}', fileName, f"{e}")
                            continue

                    try:
                        jsonAsDict = json.loads(jsonAsStr)
                    except Exception as e:
                        Debug.print('[BCClipboard.__poolFromCache] Unable to parse file {0}: {1}', fileName, f"{e}")
                        continue

                    item = None
                    if jsonAsDict['type'] == 'BCClipboardItemUrl':
                        item = BCClipboardItemUrl.new(hash, jsonAsDict)

                        item.downloadFinished.connect(self.__urlDownloadFinished)
                        item.downloadProgress.connect(self.__urlDownloadInProgress)

                        if BCClipboard.optionUrlAutoload() and not item.urlIsLoaded():
                            item.download()

                    elif jsonAsDict['type'] == 'BCClipboardItemFile':
                        item = BCClipboardItemFile.new(hash, jsonAsDict)
                    elif jsonAsDict['type'] == 'BCClipboardItemKra':
                        item = BCClipboardItemKra.new(hash, jsonAsDict)
                    elif jsonAsDict['type'] == 'BCClipboardItemSvg':
                        item = BCClipboardItemSvg.new(hash, jsonAsDict)
                    elif jsonAsDict['type'] == 'BCClipboardItemImg':
                        item = BCClipboardItemImg.new(hash, jsonAsDict)

                    if item:
                        item.persistentChanged.connect(self.__emitPersistentChanged)
                        self.__pool[hash] = item
                        self.__totalCacheSizeP += self.__pool[hash].cacheSize()

    def __recalculateCacheSize(self):
        """Recalculate cache size"""
        self.__totalCacheSizeP = 0
        self.__totalCacheSizeS = 0
        self.__totalCacheItemP = 0
        self.__totalCacheItemS = 0

        self.__stats = {
                'persistent': 0,
                'session': 0,
                'downloading': 0,

                'urls': 0,
                'files': 0,
                'images': 0,
                'kraNodes': 0,
                'kraSelection': 0
            }

        for hash in self.__pool:
            if self.__pool[hash].persistent():
                self.__totalCacheSizeP += self.__pool[hash].cacheSize()
                self.__totalCacheItemP += 1
            else:
                self.__totalCacheSizeS += self.__pool[hash].cacheSize()
                self.__totalCacheItemS += 1

            if self.__pool[hash].type() == 'BCClipboardItemUrl':
                self.__stats['urls'] += 1
            elif self.__pool[hash].type() == 'BCClipboardItemFile':
                self.__stats['files'] += 1
            elif self.__pool[hash].type() == 'BCClipboardItemImg':
                self.__stats['images'] += 1
            elif self.__pool[hash].type() == 'BCClipboardItemSvg':
                self.__stats['images'] += 1
            elif self.__pool[hash].type() == 'BCClipboardItemKra':
                if self.__pool[hash].origin() == 'application/x-krita-node':
                    self.__stats['kraNodes'] += 1
                else:
                    self.__stats['kraSelection'] += 1

        self.__stats['persistent'] = self.__totalCacheItemP
        self.__stats['session'] = self.__totalCacheItemS

    def __addPool(self, item):
        """Add BCClipboardItem to pool"""
        if isinstance(item, BCClipboardItem):
            item.persistentChanged.connect(self.__emitPersistentChanged)
            self.__updateAdd.append(item.hash())
            self.__pool[item.hash()] = item

            if item.persistent():
                self.__totalCacheSizeP += item.cacheSize()
            else:
                self.__totalCacheSizeS += item.cacheSize()

            return True
        return False

    def __addPoolUrls(self, urls, origin=None):
        """Add urls to pool

        Given urls are a list of QUrl
        """
        returned = False
        if isinstance(urls, list):
            for url in urls:
                hashValue = self.__getHash(url.url().encode())
                if self.__inPool(hashValue):
                    returned |= self.__updateTimeStamp(hashValue, origin)
                elif url.scheme() == 'file':
                    if sys.platform == 'win32':
                        # in windows, QUrl() likes "file:///C:/Temp/filetest/20190728_200521-01.jpeg"
                        # and returned .path() likes "/C:/Temp/filetest/20190728_200521-01.jpeg"
                        # ==> need to remove the leading "/" if here
                        clipboardItem = BCClipboardItemFile(hashValue, re.sub(r"^/([A-Z]):", r"\1:", url.path()), origin)
                    else:
                        clipboardItem = BCClipboardItemFile(hashValue, url.path(), origin)

                    returned |= self.__addPool(clipboardItem)
                else:
                    clipboardItem = BCClipboardItemUrl(hashValue, url, origin)

                    clipboardItem.downloadFinished.connect(self.__urlDownloadFinished)
                    clipboardItem.downloadProgress.connect(self.__urlDownloadInProgress)

                    if BCClipboard.optionUrlAutoload() and not clipboardItem.urlIsLoaded():
                        clipboardItem.download()

                    returned |= self.__addPool(clipboardItem)
        return returned

    def __addPoolSvg(self, svgData, image=None, origin=None):
        """Add svg image to pool

        Given image is a svg
        """
        hashValue = self.__getHash(svgData)

        if self.__inPool(hashValue):
            return self.__updateTimeStamp(hashValue, origin)

        if svgData is not None:
            return self.__addPool(BCClipboardItemSvg(hashValue, svgData, image, origin))
        return False

    def __addPoolKraImage(self, rawData, image=None, origin=None):
        """Add image to pool

        Given image is a QImage
        """

        hashValue = self.__getHash(rawData)

        if self.__inPool(hashValue):
            return self.__updateTimeStamp(hashValue, origin)

        if image is not None:
            return self.__addPool(BCClipboardItemKra(hashValue, rawData, image, origin))
        return False

    def __addPoolImage(self, hashValue, image, urlOrigin=None, origin=None):
        """Add image to pool

        Given image is a QImage
        """
        if self.__inPool(hashValue):
            return self.__updateTimeStamp(hashValue, origin, urlOrigin)

        if image is not None:
            item = BCClipboardItemImg(hashValue, image, urlOrigin, origin)
            return self.__addPool(item)
        return False

    def __parseHtmlForUrl(self, htmlContent):
        urls = []
        for re in (self.__reHtmlImg, self.__reHtmlLink):
            globalMatches = re.globalMatch(htmlContent)
            while globalMatches.hasNext():
                match = globalMatches.next()
                for name in ('url1', 'url2'):
                    if (found := match.captured(name)) != '':
                        urls.append(found)

        # list(set(urls)) => ensure of unicity of urls
        return ([QUrl(url) for url in list(set(urls))], i18n('HTML page'))

    def __parseHtmlForOrigin(self, htmlContent):
        urls = []
        globalMatches = self.__reHtmlImg.globalMatch(htmlContent)
        while globalMatches.hasNext():
            match = globalMatches.next()
            for name in ('url1', 'url2'):
                if (found := match.captured(name)) != '':
                    urls.append(found)
        # list(set(urls)) => ensure of unicity of urls
        urls = list(set(urls))
        if len(urls) > 0:
            return (QUrl(urls[0]), i18n('HTML link'))
        else:
            return (None, None)

    def __parseTextForUrl(self, textContent):
        urls = []

        globalMatches = self.__reTextUrl.globalMatch(textContent)
        while globalMatches.hasNext():
            match = globalMatches.next()
            urls.append(match.captured('url'))

        # list(set(urls)) => ensure of unicity of urls
        return ([QUrl(url) for url in list(set(urls))], i18n('Text document'))

    def __clipboardMimeContentChanged(self):
        """Clipboard content has been changed"""
        # print('------------------------ Clipboard content changed ------------------------')
        clipboardMimeContent = self.__clipboard.mimeData(QClipboard.Clipboard)

        if clipboardMimeContent is None:
            return

        # print(self.__temporaryDisabled, clipboardMimeContent.formats())
        # qDebug(f'__temporaryDisabled: {self.__temporaryDisabled} // hasUrls: {clipboardMimeContent.hasUrls()} // formats: {clipboardMimeContent.formats()}')

        if self.__temporaryDisabled or clipboardMimeContent.hasFormat('BCIGNORE'):
            return

        if clipboardMimeContent.hasUrls():
            if sys.platform == 'win32':
                # in windows, QUrl() likes "file:///C:/Temp/filetest/20190728_200521-01.jpeg"
                # and returned .path() likes "/C:/Temp/filetest/20190728_200521-01.jpeg"
                # ==> need to remove the leading "/" if here
                list = [url for url in clipboardMimeContent.urls()
                        if self.__reTextFile.match(url.url()).hasMatch() and url.path() != '' and os.path.exists(re.sub(r"^/([A-Z]):", r"\1:", url.path()))]
            else:
                list = [url for url in clipboardMimeContent.urls()
                        if self.__reTextFile.match(url.url()).hasMatch() and url.path() != '' and os.path.exists(url.path())]

            if len(list) > 0 and self.__addPoolUrls(list, 'URI list'):
                self.__emitUpdateAdded()
            # don't need to process other mime type
            return

        updated = False

        # retrieve any image
        image = self.__clipboard.image()
        imageHash = None
        imageOrigin = None
        if image is not None:
            ptr = image.bits()
            if ptr is not None:
                # image is valid
                ptr.setsize(image.byteCount())
                imageHash = self.__getHash(ptr)
            else:
                # image is not valid
                image = None

        for svgFmt in ('image/svg', 'image/svg+xml'):
            if clipboardMimeContent.hasFormat(svgFmt):
                rawData = clipboardMimeContent.data(svgFmt)
                updated = self.__addPoolSvg(rawData, image)

                if updated:
                    self.__emitUpdateAdded()
                    return

        if image and clipboardMimeContent.hasFormat('application/x-krita-node'):
            rawData = clipboardMimeContent.data('application/x-krita-node')
            updated = self.__addPoolKraImage(rawData, image, 'application/x-krita-node')
        elif image and clipboardMimeContent.hasFormat('application/x-krita-selection'):
            rawData = clipboardMimeContent.data('application/x-krita-selection')
            updated = self.__addPoolKraImage(rawData, image, 'application/x-krita-selection')
        elif clipboardMimeContent.hasHtml():
            rawData = clipboardMimeContent.html()
            if rawData:
                if image is None:
                    if BCClipboard.optionUrlParseTextHtml():
                        urls, origin = self.__parseHtmlForUrl(rawData)
                        if urls:
                            updated = self.__addPoolUrls(urls, origin)
                else:
                    # an image has been found, parse html to eventually determinate origin of content
                    urlOrigin, origin = self.__parseHtmlForOrigin(rawData)
                    updated = self.__addPoolImage(imageHash, image, urlOrigin, origin)
        elif image is None and clipboardMimeContent.hasText() and BCClipboard.optionUrlParseTextHtml():
            rawData = clipboardMimeContent.text()
            if rawData:
                urls, origin = self.__parseTextForUrl(rawData)
                if urls:
                    updated = self.__addPoolUrls(urls, origin)
        elif image:
            updated = self.__addPoolImage(imageHash, image)

        if updated:
            self.__emitUpdateAdded()

    def __cacheCleanup(self):
        """Cleanup cache files: remove older items

        Older item are removed from pool and cache
        """
        updated = False

        if self.__totalCacheSizeS > BCClipboard.optionCacheMaxSize():
            # build list of item from session, ascending sort on timestamp
            hashList = sorted([hash for hash in self.__pool if self.__pool[hash].persistent()], key=lambda hash: self.__pool[hash].timestamp())

            for hash in hashList:
                if self.__totalCacheSizeS < BCClipboard.optionCacheMaxSize():
                    # cache size is now less than maximum size, exit
                    break

                self.__updateRemove.append(hash)
                item = self.__pool.pop(hash)
                self.__totalCacheSizeS -= item.cacheSize()
                updated = True

        if updated:
            if len(self.__pool) == 0:
                self.__updateRemove = []
            self.__emitUpdateRemoved()

    def startDownload(self, items=None):
        """Start download for all url for which download is not started/done"""
        keys = []
        if items is None:
            keys = self.__pool.keys()
        elif isinstance(items, BCClipboardItemUrl):
            keys = [items.hash()]
        elif isinstance(items, list):
            keys = [item.hash() for item in items if isinstance(item, BCClipboardItemUrl)]

        for itemKey in keys:
            if self.__pool[itemKey].type() == 'BCClipboardItemUrl' and self.__pool[itemKey].urlStatus() == BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED:
                self.__pool[itemKey].download()

    def stopDownload(self, items=None):
        """Stop download for all url for which download is started"""
        keys = []
        if items is None:
            keys = self.__pool.keys()
        elif isinstance(items, BCClipboardItemUrl):
            keys = [items.hash()]
        elif isinstance(items, list):
            keys = [item.hash() for item in items if isinstance(item, BCClipboardItemUrl)]

        for itemKey in keys:
            if self.__pool[itemKey].type() == 'BCClipboardItemUrl' and self.__pool[itemKey].urlStatus() == BCClipboardItemUrl.URL_STATUS_DOWNLOADING:
                self.__pool[itemKey].downloadStop()

    def length(self):
        """Return number of item in pool"""
        return len(self.__pool)

    def hashList(self):
        """Return list of hash; no sort"""
        return list(self.__pool.keys())

    def get(self, hash):
        """Return clipboard item from hash, or None if nothing is found"""
        if hash in self.__pool:
            return self.__pool[hash]
        return None

    def enabled(self):
        """Return if clipboard management is enabled"""
        return self.__enabled

    def setEnabled(self, value):
        """Set if clipboard management is enabled"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")

        if self.__enabled != value:
            self.__enabled = value
            if self.__enabled:
                self.__clipboard.dataChanged.connect(self.__clipboardMimeContentChanged)
            else:
                self.__clipboard.dataChanged.disconnect(self.__clipboardMimeContentChanged)

    def cacheSessionFlush(self):
        """Flush (session) pool content"""
        updated = False
        for root, dirs, files in os.walk(BCClipboard.sessionCacheDirectory()):
            for fileName in files:
                try:
                    os.remove(os.path.join(root, fileName))
                    updated = True
                except Exception as e:
                    Debug.print('[BCClipboard.cacheSessionFlush] Unable to delete file {0}: {1}', fileName, f"{e}")

        if updated:
            self.__poolFromCache()
            self.__updateAdd = []
            self.__emitUpdateAdded()

    def cachePersistentFlush(self):
        """Flush (persistent) pool content"""
        updated = False
        for root, dirs, files in os.walk(BCClipboard.persistentCacheDirectory()):
            for fileName in files:
                try:
                    os.remove(os.path.join(root, fileName))
                    updated = True
                except Exception as e:
                    Debug.print('[BCClipboard.cachePersistentFlush] Unable to delete file {0}: {1}', fileName, f"{e}")

        if updated:
            self.__poolFromCache()
            self.__updateAdd = []
            self.__emitUpdateAdded()

    def cacheSizeP(self, recalculate=False):
        """Return current cache size as a tuple(nb items, size)"""
        if recalculate:
            self.__recalculateCacheSize()
        return (self.__totalCacheItemP, self.__totalCacheSizeP)

    def cacheSizeS(self, recalculate=False):
        """Return current cache size as a tuple(nb items, size)"""
        if recalculate:
            self.__recalculateCacheSize()
        return (self.__totalCacheItemS, self.__totalCacheSizeS)

    def pushBackToClipboard(self, data, forceImgAsPng=False):
        """Push back data to clipboard

        Given `data` can be:
        - BCClipboardItemUrl or list of BCClipboardItemUrl
        - BCClipboardItemFile or list of BCClipboardItemFile
        - BCClipboardItemImg
        - BCClipboardItemSvg
        - BCClipboardItemKra

        If `forceImgAsPng` is True, if content pushed back into clipboard is an
        image (jpeg, kra, ...) content is forced to be converted as png mime/type
        before being pushed back in clipboard

        This is an ugly workaround to allow any type of image format (that can be
        read by bc) to be pasted as reference image
        """
        def processItem(item):
            contentList = item.contentBackToClipboard()
            for content in contentList:
                if content[1] == 'text/uri-list':
                    qurlList.append(content[0])
                elif content[1] == 'text/plain':
                    textList.append(content[0])
                else:
                    # print(content[1])
                    if forceImgAsPng and content[1] != 'image/png' and re.match('(image/|application/x-krita)', content[1]):
                        # content[0] = image raw data
                        # content[1] = mime/type
                        # content[2] = BCFile
                        #
                        # in this case:
                        #   . retrieve image from BCFile (a QImage)
                        #   . convert it on the fly as PNG byte array
                        #   . push it back in clipboard
                        content = (qImageToPngQByteArray(content[2].image()), 'image/png')
                    mimeContent.setData(content[1], content[0])

        mimeContent = QMimeData()
        qurlList = []
        textList = []
        if isinstance(data, list):
            if len(data) == 1:
                processItem(data[0])
            else:
                for item in data:
                    processItem(item)
        else:
            processItem(data)

        if len(qurlList) > 0:
            mimeContent.setUrls(qurlList)

        if len(textList) > 0:
            mimeContent.setText(os.linesep.join(textList))

        if len(mimeContent.formats()) > 0:
            self.__temporaryDisabled = True
            self.__clipboard.setMimeData(mimeContent)
            self.__temporaryDisabled = False

    def stats(self):
        """Return statistics"""
        return self.__stats

    def checkContent(self):
        """Check clipboard content manually"""
        self.__clipboardMimeContentChanged()


class BCClipboardModel(QAbstractTableModel):
    """A model provided by clipboard"""
    updateWidth = Signal()

    COLNUM_ICON = 0
    COLNUM_PERSISTENT = 1
    COLNUM_TYPE = 2
    COLNUM_DATE = 3
    COLNUM_SIZE = 4
    COLNUM_SRC = 5
    COLNUM_FULLNFO = 6
    COLNUM_LAST = 6

    ROLE_HASH = Qt.UserRole + 1
    ROLE_PCT = Qt.UserRole + 2
    ROLE_ITEM = Qt.UserRole + 3

    __PIN_ICON_WIDTH = 30
    PIN_ICON_SIZE = QSize(22, 22)

    FULLNFO_ICON_SIZE = 256

    HEADERS = ['', '', i18n("Type"), i18n("Date"), i18n("Image size"), i18n("Source"), i18n("Nfo")]

    def __init__(self, clipboard, parent=None):
        """Initialise list"""
        super(BCClipboardModel, self).__init__(parent)
        if not isinstance(clipboard, BCClipboard):
            raise EInvalidType('Given `clipboard` must be a <BCClipboard>')
        self.__clipboard = clipboard
        self.__clipboard.updateAdded.connect(self.__dataUpdatedAdd)
        self.__clipboard.updateRemoved.connect(self.__dataUpdateRemove)
        self.__clipboard.updateDownload.connect(self.__dataUpdateDownload)
        self.__clipboard.updatePersistent.connect(self.__dataUpdatePersistent)
        self.__items = self.__clipboard.hashList()
        self.__iconSize = QSize(12, 12)
        self.__thumbSize = BCFileThumbnailSize.SMALL

    def __repr__(self):
        return f'<BCClipboardModel()>'

    def __hashRow(self, hash):
        """Return row number for a given hash; return -1 if not found"""
        try:
            return self.__items.index(hash)
        except Exception as e:
            return -1

    def __dataUpdatedAdd(self, items):
        # if nb items is the same, just update... ?
        # self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(self.__clipboard.length()-1, BCClipboardModel.COLNUM_LAST) )
        print('TODO: need to update only for added items')
        self.__items = self.__clipboard.hashList()
        self.modelReset.emit()
        self.updateWidth.emit()

    def __dataUpdateRemove(self, items):
        # if nb items is the same, just update... ?
        # self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(self.__clipboard.length()-1, BCClipboardModel.COLNUM_LAST) )
        print('TODO: need to update only for removed items')
        self.__items = self.__clipboard.hashList()
        self.modelReset.emit()

    def __dataUpdatePersistent(self, item):
        index = self.createIndex(self.__hashRow(item.hash()), BCClipboardModel.COLNUM_PERSISTENT)
        self.dataChanged.emit(index, index, [Qt.DecorationRole])

    def __dataUpdateDownload(self, downloadFinished, item):
        row = self.__hashRow(item.hash())
        if downloadFinished:
            indexS = self.createIndex(row, BCClipboardModel.COLNUM_ICON)
            indexE = self.createIndex(row, BCClipboardModel.COLNUM_LAST)
            self.dataChanged.emit(indexS, indexE, [Qt.DisplayRole])
        else:
            if self.__iconSize.width() >= BCClipboardModel.FULLNFO_ICON_SIZE:
                index = self.createIndex(row, BCClipboardModel.COLNUM_FULLNFO)
            else:
                index = self.createIndex(row, BCClipboardModel.COLNUM_SRC)
            self.dataChanged.emit(index, index, [Qt.DisplayRole])

    def columnCount(self, parent=QModelIndex()):
        """Return total number of column"""
        return BCClipboardModel.COLNUM_LAST+1

    def rowCount(self, parent=QModelIndex()):
        """Return total number of rows"""
        return self.__clipboard.length()

    def data(self, index, role=Qt.DisplayRole):
        """Return data for index+role"""
        column = index.column()
        row = index.row()
        if role == Qt.DecorationRole:
            if column == BCClipboardModel.COLNUM_ICON:
                hash = self.__items[row]
                item = self.__clipboard.get(hash)
                if isinstance(item.file(), BCBaseFile):
                    return item.file().thumbnail(self.__thumbSize, thumbType=BCBaseFile.THUMBTYPE_ICON)
                elif item.type() == 'BCClipboardItemUrl':
                    return buildIcon('pktk:url')
                else:
                    return buildIcon('pktk:warning')
        elif role == Qt.DisplayRole:
            hash = self.__items[row]
            item = self.__clipboard.get(hash)
            if item:
                if column == BCClipboardModel.COLNUM_TYPE:
                    if item.type() == 'BCClipboardItemFile':
                        return i18n('File')
                    elif item.type() == 'BCClipboardItemUrl':
                        return i18n('Url')
                    elif item.type() == 'BCClipboardItemImg':
                        return i18n('Image (Raster)')
                    elif item.type() == 'BCClipboardItemSvg':
                        return i18n('Image (Vector)')
                    elif item.type() == 'BCClipboardItemKra':
                        if item.origin() == 'application/x-krita-selection':
                            return i18n('Krita selection')
                        elif item.origin() == 'application/x-krita-node':
                            return i18n('Krita layer')
                    else:
                        return i18n('Invalid')
                elif column == BCClipboardModel.COLNUM_DATE:
                    return f'{datetime.datetime.fromtimestamp(item.timestamp()):%Y-%m-%d %H:%M:%S}'
                elif column == BCClipboardModel.COLNUM_SIZE:
                    if item.type() == 'BCClipboardItemUrl':
                        if item.urlStatus() == BCClipboardItemUrl.URL_STATUS_DOWNLOADING:
                            return i18n('Downloading...')
                        elif item.urlStatus() == BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED:
                            return i18n('Not downloaded')
                        elif item.urlStatus() == BCClipboardItemUrl.URL_STATUS_DOWNLOADERROR:
                            return i18n('Download error')

                    size = item.imageSize()
                    if size and size.width() > -1 and size.height() > -1:
                        return f'{size.width()}x{size.height()}'

                    # no size? not downloaded/not in cache?
                    return ''
                elif column == BCClipboardModel.COLNUM_SRC:
                    if item.type() == 'BCClipboardItemFile':
                        return item.fileName()
                    if item.type() == 'BCClipboardItemUrl':
                        return item.url().url()
                    elif item.type() == 'BCClipboardItemImg' and item.urlOrigin():
                        return item.urlOrigin().url()
                    return ''
                elif column == BCClipboardModel.COLNUM_PERSISTENT:
                    if item.persistent():
                        return 'T'
                    else:
                        return 'F'
                elif column == BCClipboardModel.COLNUM_FULLNFO:
                    returned = f'Type:       '

                    if item.type() == 'BCClipboardItemFile':
                        returned += i18n('File')
                    elif item.type() == 'BCClipboardItemUrl':
                        returned += i18n('Url')
                    elif item.type() == 'BCClipboardItemImg':
                        returned += i18n('Image (Raster)')
                    elif item.type() == 'BCClipboardItemSvg':
                        returned += i18n('Image (Vector)')
                    elif item.type() == 'BCClipboardItemKra':
                        if item.origin() == 'application/x-krita-selection':
                            returned += i18n('Krita selection')
                        elif item.origin() == 'application/x-krita-node':
                            returned += i18n('Krita layer')
                    else:
                        returned += i18n('Invalid')

                    returned += f'\nDate:       {datetime.datetime.fromtimestamp(item.timestamp()):%Y-%m-%d %H:%M:%S}'
                    returned += f'\nImage size: '

                    if item.type() == 'BCClipboardItemUrl':
                        if item.urlStatus() == BCClipboardItemUrl.URL_STATUS_DOWNLOADING:
                            returned += i18n('Downloading...')
                        elif item.urlStatus() == BCClipboardItemUrl.URL_STATUS_NOTDOWNLOADED:
                            returned += i18n('Not downloaded')
                    else:
                        size = item.imageSize()
                        if size and size.width() > -1 and size.height() > -1:
                            returned += f'{size.width()}x{size.height()}'
                        else:
                            returned += '-'

                    if item.type() == 'BCClipboardItemFile':
                        returned += f'\nSource:     {item.fileName()}'
                    if item.type() == 'BCClipboardItemUrl':
                        returned += f'\nSource:     {item.url().url()}'
                    elif item.type() == 'BCClipboardItemImg' and item.urlOrigin():
                        returned += f'\nSource:     {item.urlOrigin().url()}'

                    return returned
        elif role == BCClipboardModel.ROLE_HASH:
            return self.__items[row]
        elif role == BCClipboardModel.ROLE_PCT:
            item = self.__clipboard.get(self.__items[row])
            if item.type() == 'BCClipboardItemUrl':
                if item.urlStatus() == BCClipboardItemUrl.URL_STATUS_DOWNLOADING:
                    return item.downloader().downloadProgress()[0]
            return -1
        elif role == BCClipboardModel.ROLE_ITEM:
            hash = self.__items[row]
            return self.__clipboard.get(hash)
        elif role == Qt.SizeHintRole:
            if column == BCClipboardModel.COLNUM_ICON:
                # calculate only for 1st cell
                return self.__iconSize
            elif column == BCClipboardModel.COLNUM_PERSISTENT:
                return BCClipboardModel.__PIN_ICON_WIDTH
        return None

    def roleNames(self):
        return {
            BCClipboardModel.ROLE_HASH: b'hash'
        }

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return BCClipboardModel.HEADERS[section]
        return None

    def setIconSize(self, value):
        self.__iconSize = QSize(value, value)
        self.__thumbSize = BCFileThumbnailSize.fromValue(value)
        topLeft = self.createIndex(0, BCClipboardModel.COLNUM_ICON)
        self.dataChanged.emit(topLeft, topLeft, [Qt.SizeHintRole])


class BCClipboardDelegate(QStyledItemDelegate):
    """Extend QStyledItemDelegate class to build an improved IN CACHE informations
    (display download progress)
    """
    def __init__(self, parent=None):
        """Constructor, nothingspecial"""
        super(BCClipboardDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        """Paint list item"""
        if index.column()in (BCClipboardModel.COLNUM_SRC, BCClipboardModel.COLNUM_FULLNFO):
            pct = index.data(BCClipboardModel.ROLE_PCT)
            if pct == -1:
                # not progress bar to display
                QStyledItemDelegate.paint(self, painter, option, index)
                return

            self.initStyleOption(option, index)

            rectTxt = QRect(option.rect.left() + 4, option.rect.top()+1, option.rect.width()-4, option.rect.height()-2)
            rectTextH = QRect(option.rect.left() + 4, option.rect.top()+1, round(option.rect.width() * pct/100, 2)-4, option.rect.height()-2)

            if index.column() == BCClipboardModel.COLNUM_SRC:
                rectPct = QRect(option.rect.left(), option.rect.top()+1, round(option.rect.width() * pct/100, 2), option.rect.height()-2)
            else:
                rectPct = QRect(option.rect.left(), option.rect.top()+option.rect.height()*0.75, round(option.rect.width() * pct/100, 2), option.rect.height()*0.25-1)

            palette = QApplication.palette()

            painter.save()

            painter.setPen(QPen(palette.text().color()))
            painter.drawText(rectTxt, Qt.AlignLeft | Qt.AlignVCenter, index.data())

            painter.fillRect(rectPct, palette.highlight())

            painter.setPen(QPen(palette.highlightedText().color()))
            painter.drawText(rectTextH, Qt.AlignLeft | Qt.AlignVCenter, index.data())

            painter.restore()
        elif index.column() == BCClipboardModel.COLNUM_PERSISTENT:
            self.initStyleOption(option, index)

            item = index.data(BCClipboardModel.ROLE_ITEM)

            painter.save()

            if (option.state & QStyle.State_Selected) == QStyle.State_Selected:
                painter.fillRect(option.rect, option.palette.color(QPalette.Highlight))

            iconPosition = QPoint(option.rect.left() + 4, option.rect.top())

            if item.persistent():
                painter.drawPixmap(iconPosition, QIcon.fromTheme('lock').pixmap(BCClipboardModel.PIN_ICON_SIZE))
            else:
                painter.drawPixmap(iconPosition, QIcon.fromTheme('unlock').pixmap(BCClipboardModel.PIN_ICON_SIZE))

            painter.restore()
