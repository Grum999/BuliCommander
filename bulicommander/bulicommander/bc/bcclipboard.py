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

import os
import time
import datetime
import hashlib
import json
import re

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )

from .bcutils import (
        Debug
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )

class BCClipboardItem(object):
    """An item stored in clipboard"""

    def __init__(self, hashValue, origin=None, timestamp=None):
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
        self.__persistent = BCClipboard.optionCacheDefaultPersistent()
        # image size
        self.__imageSize=QSize()
        # size in cache
        self.__cacheSize=-1

        self.setOrigin(origin)

    def __repr__(self):
        return (f'<{self.type()}({self.__hashValue}, '
                f'"{self.origin()}", '
                f'"{datetime.datetime.fromtimestamp(self.__timestamp):%Y-%m-%d %H:%M:%S}", '
                f'{self.imageSize().width()}x{self.imageSize().height()}, '
                f'{self.cacheSize()})>')

    def calculateCacheSize(self):
        """Calculate size of files in cache"""
        self.__cacheSize=0
        for root, dirs, files in os.walk(self.cachePath()):
            for name in files:
                if re.search(fr'^{self.hash()}\..*', name):
                    self.__cacheSize+=os.path.getsize(os.path.join(root, name))

    def cachePath(self):
        """Return current cache path for item"""
        if self.persistent():
            return BCClipboard.persistentCacheDirectory()
        else:
            return BCClipboard.flushedCacheDirectory()

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
            self.__origin=value

    def persistent(self):
        """Return if clipboard item is persistent or not"""
        return self.__persistent

    def setPersistent(self, value):
        """Set if clipboard item is persistent or not"""
        if not isinstance(value, bool):
            raise EInvalidType('Given `value` must be a <bool>')

        # TODO: need to move file:
        #   persistentCacheDirectory<-->flushedCacheDirectory

        if value != self.__persistent:
            # do soomething only if state is changed
            filesToProcess=[]
            if self.__persistent:
                # move from persistentCacheDirectory() to flushedCacheDirectory()
                targetPath=BCClipboard.flushedCacheDirectory()
                for root, dirs, files in os.walk(BCClipboard.persistentCacheDirectory()):
                    filesToProcess+=[os.path.join(root, name) for name in files if search(fr'^{self.hash()}\..*', name)]
            else:
                # move from flushedCacheDirectory() to persistentCacheDirectory()
                targetPath=BCClipboard.flushedCacheDirectory()
                for root, dirs, files in os.walk(BCClipboard.flushedCacheDirectory()):
                    filesToProcess+=[os.path.join(root, name) for name in files if search(fr'^{self.hash()}\..*', name)]

            for file in filesToProcess:
                try:
                    print('move', file, targetPath)
                    shutil.move(file, targetPath)
                except Exception as e:
                    Debug.print('[BCClipboardItem.setPersistent] Unable to move file {0} to {1}: {2}', fileName, targetPath, str(e))

            self.__persistent=value

    def saveToCache(self):
        """Save description to cache as a JSON file"""
        data = self.dataContentForCache()

        fileName = os.path.join(self.cachePath(), f'{self.hash()}.json')

        with open(fileName, 'w') as file:
            try:
                file.write(json.dumps(data, indent=4, sort_keys=True))
            except Exception as e:
                Debug.print('[BCClipboardItem.saveToCache] Unable to save file {0}: {1}', fileName, str(e))
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
        self.__imageSize=size

    def cacheSize(self):
        """Return size of files in cache"""
        if self.__cacheSize == -1:
            # not yet calculated, do it
            self.calculateCacheSize()
        return self.__cacheSize


class BCClipboardItemUrl(BCClipboardItem):
    """An url stored in clipboard"""

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
        """
        url=None
        origin=None
        timestamp=None
        if isinstance(options.get('url.url', None), str):
            url=QUrl(options['url.url'])
        if isinstance(options.get('origin', None), str):
            origin=options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp=options['timestamp']

        returned=BCClipboardItemUrl(hash, url, origin, timestamp, False)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options.get('imageSize.width', None), int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        if isinstance(options.get('persistent', None), bool):
            returned.setPersistent(options['persistent'])
        else:
            # consider the new() static method is used to load from json dict
            returned.setPersistent(True)

        return returned

    def __init__(self, hashValue, url, origin=None, timestamp=None, saveInCache=True):
        super(BCClipboardItemUrl, self).__init__(hashValue, origin, timestamp)

        if not isinstance(url, QUrl):
            raise EInvalidType('Given `url` must be a QUrl')

        self.__loadedFileName=f'{self.hash()}{os.path.splitext(url.fileName())[1]}'
        self.__url=url
        self.__urlIsValid=True
        self.__urlIsLoaded=os.path.exists(os.path.join(self.cachePath(), self.loadedFileName()))

        if saveInCache:
            self.saveToCache()

    def __repr__(self):
        return f'{super(BCClipboardItemUrl, self).__repr__()[:-2]}, "{self.__url.url()}", {self.__urlIsValid}, {self.__urlIsLoaded})>'

    def dataContentForCache(self):
        """Return data that have to be saved in cache

        return value is a dictionary key=value
        """
        returned=super(BCClipboardItemUrl, self).dataContentForCache()

        returned['url.url']=self.__url.url()
        returned['url.isValid']=self.__urlIsValid
        returned['url.isLoaded']=self.__urlIsLoaded
        returned['url.loadedFileName']=self.__loadedFileName

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
        self.__urlIsValid=value

    def urlIsLoaded(self):
        """Return if url content is loaded or not"""
        return self.__urlIsLoaded

    def loadedFileName(self):
        """Return file name (without path) for expected loaded file"""
        return self.__loadedFileName


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
        urlOrigin=None
        origin=None
        timestamp=None
        if isinstance(options.get('urlOrigin', None), str) and options['urlOrigin']!='':
            urlOrigin=QUrl(options['urlOrigin'])
        if isinstance(options.get('origin', None), str):
            origin=options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp=options['timestamp']

        returned=BCClipboardItemImg(hash, None, urlOrigin, origin, timestamp, False)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options['imageSize.width'], int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        if isinstance(options.get('persistent', None), bool):
            returned.setPersistent(options['persistent'])
        else:
            # consider the new() static method is used to load from json dict
            returned.setPersistent(True)

        if not os.path.exists(os.path.join(returned.cachePath(), f'{hash}.png')):
            # image file doesn't exist in cache, don't try to create item
            return None

        return returned

    def __init__(self, hashValue, image, urlOrigin=None, origin=None, timestamp=None, saveInCache=True):
        super(BCClipboardItemImg, self).__init__(hashValue, origin, timestamp)

        self.__urlOrigin = ''

        if isinstance(urlOrigin, QUrl):
            self.__urlOrigin = urlOrigin.url()

        if image:
            if not isinstance(image, QImage):
                raise EInvalidType('Given `image` must be a QImage')
            self.setImageSize(image.size())

            if saveInCache:
                self.saveToCache(image)

    def urlOrigin(self):
        """Return url from which image has been copied, if any"""
        return self.__urlOrigin

    def setUrlOrigin(self, urlOrigin):
        """set url from which image has been copied, if any"""
        if isinstance(urlOrigin, str):
            self.__urlOrigin=QUrl(urlOrigin)
        elif isinstance(urlOrigin, QUrl):
            self.__urlOrigin=urlOrigin

    def dataContentForCache(self):
        """Return data that have to be saved in cache

        return value is a dictionary key=value
        """
        returned=super(BCClipboardItemImg, self).dataContentForCache()

        if isinstance(self.__urlOrigin, QUrl):
            returned['url.origin']=self.__urlOrigin.url()
        else:
            returned['url.origin']=None

        return returned

    def saveToCache(self, image):
        """Save image to cache"""
        super(BCClipboardItemImg, self).saveToCache()

        return BCClipboard.saveQImage(os.path.join(self.cachePath(), f'{self.hash()}.png'), image, False)


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
        origin=None
        timestamp=None
        if isinstance(options.get('origin', None), str):
            origin=options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp=options['timestamp']

        returned=BCClipboardItemSvg(hash, None, None, origin, timestamp, False)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options.get('imageSize.width', None), int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        if isinstance(options.get('persistent', None), bool):
            returned.setPersistent(options['persistent'])
        else:
            # consider the new() static method is used to load from json dict
            returned.setPersistent(True)

        if not os.path.exists(os.path.join(returned.cachePath(), f'{hash}.svg')):
            # svg file doesn't exist in cache, don't try to create item
            return None

        return returned

    def __init__(self, hashValue, svgData, image=None, origin=None, timestamp=None, saveInCache=True):
        super(BCClipboardItemSvg, self).__init__(hashValue, origin, timestamp)
        if image and not isinstance(image, QImage):
            raise EInvalidType('Given `image` must be a QImage')

        if svgData and saveInCache:
            self.saveToCache(svgData, image)

    def saveToCache(self, svgData, image):
        """Save SVG+image data to cache"""
        saved = super(BCClipboardItemSvg, self).saveToCache()

        if isinstance(image, QImage):
            saved&=BCClipboard.saveQImage(os.path.join(self.cachePath(), f'{self.hash()}.png'), image)

        with open(os.path.join(self.cachePath(), f'{self.hash()}.svg'), 'wb') as file:
            try:
                file.write(svgData)
            except Exception as e:
                Debug.print('[BCClipboardItemSvg.saveToCache] Unable to save file {0}: {1}', fileName, str(e))
                saved=False

        return saved


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
        origin=None
        timestamp=None
        if isinstance(options.get('origin', None), str):
            origin=options['origin']
        if isinstance(options.get('timestamp', None), float):
            timestamp=options['timestamp']

        returned=BCClipboardItemKra(hash, None, None, origin, timestamp, False)

        if isinstance(options.get('imageSize.height', None), int) and isinstance(options.get('imageSize.width', None), int):
            returned.setImageSize(QSize(options['imageSize.width'], options['imageSize.height']))

        if isinstance(options.get('persistent', None), bool):
            returned.setPersistent(options['persistent'])
        else:
            # consider the new() static method is used to load from json dict
            returned.setPersistent(True)

        if not os.path.exists(os.path.join(returned.cachePath(), f'{hash}.kra')):
            # svg file doesn't exist in cache, don't try to create item
            return None

        return returned

    def __init__(self, hashValue, kraData, image=None, origin=None, timestamp=None, saveInCache=True):
        super(BCClipboardItemKra, self).__init__(hashValue, origin, timestamp)
        if image and not isinstance(image, QImage):
            raise EInvalidType('Given `image` must be a QImage')

        if image:
            self.setImageSize(image.size())

        if kraData:
            self.saveToCache(kraData, image)

    def saveToCache(self, kraData, image):
        """Save kra information+image to cache"""
        saved = super(BCClipboardItemKra, self).saveToCache()

        if isinstance(image, QImage):
            if self.persistent():
                fileName = os.path.join(BCClipboard.persistentCacheDirectory(), f'{self.hash()}.png')
            else:
                fileName = os.path.join(BCClipboard.flushedCacheDirectory(), f'{self.hash()}.png')

            saved &= BCClipboard.saveQImage(fileName, image)


        if self.persistent():
            fileName = os.path.join(BCClipboard.persistentCacheDirectory(), f'{self.hash()}.kra')
        else:
            fileName = os.path.join(BCClipboard.flushedCacheDirectory(), f'{self.hash()}.kra')

        with open(fileName, 'wb') as file:
            try:
                file.write(kraData)
            except Exception as e:
                Debug.print('[BCClipboardItemKra.saveToCache] Unable to save file {0}: {1}', fileName, str(e))
                saved=False

        return saved


class BCClipboard(QObject):
    """Manage clipboard content"""
    updated = Signal()

    __INITIALISED = False
    __OPTION_CACHE_PATH = ''
    __OPTION_CACHE_MAXSIZE = 1024000000 # 1GB
    __OPTION_URL_AUTOLOAD = True
    __OPTION_CACHE_DEFAULT_PERSISTENT = False

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
            os.makedirs(BCClipboard.flushedCacheDirectory(), exist_ok=True)
        except Exception as e:
            Debug.print('[BCClipboard.initialiseCache] Unable to create directory: {0}', str(e))
            return

        BCClipboard.__INITIALISED = True

    @staticmethod
    def persistentCacheDirectory():
        """Return path for persistent clipboard data"""
        if BCClipboard.__OPTION_CACHE_PATH == '':
            raise EInvalidStatus("BCClipboard hasn't been initialized!")
        return os.path.join(BCClipboard.__OPTION_CACHE_PATH, 'persistent')

    @staticmethod
    def flushedCacheDirectory():
        """Return path for non persistent clipboard data"""
        if BCClipboard.__OPTION_CACHE_PATH == '':
            raise EInvalidStatus("BCClipboard hasn't been initialized!")
        return os.path.join(BCClipboard.__OPTION_CACHE_PATH, 'flushed')

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
    def optionUrlAutoload():
        """Return if url are loaded automatically or not"""
        return BCClipboard.__OPTION_URL_AUTOLOAD

    @staticmethod
    def setOptionUrlAutoload(value):
        """Set if url are loaded automatically or not"""
        if not isinstance(value, bool):
            raise EInvalidType("Given `value` must be a <bool>")
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
    def saveQImage(fileName, image, resize=True):
        """Save QImage as png content

        Use a method to ensure all image are saved using the same parameters
        """
        if not isinstance(image, QImage):
            raise EInvalidType('Given `image` must be a <QImage>')

        if resize:
            return image.scaled(QSize(512,512), Qt.KeepAspectRatio, Qt.SmoothTransformation).save(fileName, b'png', 50)
        else:
            return image.save(fileName, b'png', 50)

    def __init__(self):
        """Initialize object"""
        super(BCClipboard, self).__init__(None)

        # store everything in a dictionary
        # key = hashValue (SHA1) of clipboard content
        # value = BCClipboardItem
        self.__pool = {}

        # instance to application clipboard
        self.__clipboard = QGuiApplication.clipboard()
        self.__clipboard.dataChanged.connect(self.__clipboardMimeContentChanged)

        # regular expressions used to parse HTML and find urls
        self.__reHtmlImg=QRegularExpression(r'(?im)<img(?:\s.*\s|\s+)(?:src="(?<url1>https?:\/\/[^"]+?\.(?:jpeg|jpg|png|gif|svg)[^"]*?)"|src=\'(?<url2>https?:\/\/[^\']+?\.(?:jpeg|jpg|png|gif|svg)[^\']*?)\')[^>]*?>')
        self.__reHtmlLink=QRegularExpression(r'(?im)<a(?:\s.*\s|\s+)(?:href="(?<url1>https?:\/\/[^"]+?\.(?:jpeg|jpg|png|gif|svg)[^"]*?)"|href=\'(?<url2>https?:\/\/[^\']+?\.(?:jpeg|jpg|png|gif|svg)[^\']*?)\')[^>]*?>')

        # regular expression used to parse PLAIN TEXT and find urls
        self.__reTextUrl=QRegularExpression(r'(?im)(["\'])?(?<url>https?:\/\/[^\s]+\.(?:jpeg|jpg|png|svg|gif)(?:\?[^\s]*)?)\1?.*')

        self.__totalCacheSizeP=0
        self.__totalCacheSizeF=0

        self.cacheFlush()
        self.__poolFromCache()

    def __getHash(self, data):
        """Return hash for data"""
        hash=hashlib.md5()
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
                if result:=re.search(r'^(.*)\.json$', name):
                    hash=result.groups()[0]

                    fileName=os.path.join(root, name)

                    with open(fileName, 'r') as file:
                        try:
                            jsonAsStr = file.read()
                        except Exception as e:
                            Debug.print('[BCClipboard.__poolFromCache] Unable to load file {0}: {1}', fileName, str(e))
                            continue

                    try:
                        jsonAsDict = json.loads(jsonAsStr)
                    except Exception as e:
                        Debug.print('[BCClipboard.__poolFromCache] Unable to parse file {0}: {1}', fileName, str(e))
                        continue

                    item=None
                    if jsonAsDict['type']=='BCClipboardItemUrl':
                        item=BCClipboardItemUrl.new(hash, jsonAsDict)
                    elif jsonAsDict['type']=='BCClipboardItemKra':
                        item=BCClipboardItemKra.new(hash, jsonAsDict)
                    elif jsonAsDict['type']=='BCClipboardItemSvg':
                        item=BCClipboardItemSvg.new(hash, jsonAsDict)
                    elif jsonAsDict['type']=='BCClipboardItemImg':
                        item=BCClipboardItemImg.new(hash, jsonAsDict)

                    if item:
                        self.__pool[hash]=item
                        self.__totalCacheSizeP+=self.__pool[hash].cacheSize()

    def __recalculateCacheSize(self):
        """Return current cache size as a tuple(flushed, persistent)"""
        self.__totalCacheSizeP=0
        self.__totalCacheSizeF=0
        for hash in self.__pool:
            if self.__pool[hash].persistent():
                self.__totalCacheSizeP+=self.__pool[hash].cacheSize()
            else:
                self.__totalCacheSizeF+=self.__pool[hash].cacheSize()

        return (self.__totalCacheSizeP, self.__totalCacheSizeF)

    def __addPool(self, item):
        """Add BCClipboardItem to pool"""
        if isinstance(item, BCClipboardItem):
            self.__pool[item.hash()]=item

            if item.persistent():
                self.__totalCacheSizeP+=item.cacheSize()
            else:
                self.__totalCacheSizeF+=item.cacheSize()

            return True
        return False

    def __addPoolUrls(self, urls, origin=None):
        """Add urls to pool

        Given urls are a list of QUrl
        """
        returned=False
        if isinstance(urls, list):
            for url in urls:
                hashValue=self.__getHash(url.url().encode())
                if self.__inPool(hashValue):
                    returned|=self.__updateTimeStamp(hashValue, origin)
                else:
                    returned|=self.__addPool(BCClipboardItemUrl(hashValue, url, origin))
        return returned

    def __addPoolSvg(self, svgData, image=None, origin=None):
        """Add svg image to pool

        Given image is a svg
        """
        hashValue = self.__getHash(svgData)

        if self.__inPool(hashValue):
            return self.__updateTimeStamp(hashValue, origin)

        if not svgData is None:
            return self.__addPool(BCClipboardItemSvg(hashValue, svgData, image, origin))
        return False

    def __addPoolKraImage(self, rawData, image=None, origin=None):
        """Add image to pool

        Given image is a QImage
        """

        hashValue = self.__getHash(rawData)

        if self.__inPool(hashValue):
            return self.__updateTimeStamp(hashValue, origin)

        if not image is None:
            return self.__addPool(BCClipboardItemKra(hashValue, rawData, image, origin))
        return False

    def __addPoolImage(self, hashValue, image, urlOrigin=None, origin=None):
        """Add image to pool

        Given image is a QImage
        """
        if self.__inPool(hashValue):
            return self.__updateTimeStamp(hashValue, origin, urlOrigin)

        if not image is None:
            item=BCClipboardItemImg(hashValue, image, urlOrigin, origin)
            return self.__addPool(item)
        return False

    def __parseHtmlForUrl(self, htmlContent):
        urls=[]
        for re in (self.__reHtmlImg, self.__reHtmlLink):
            globalMatches=re.globalMatch(htmlContent)
            while globalMatches.hasNext():
                match=globalMatches.next()
                for name in ('url1', 'url2'):
                    if (found:=match.captured(name))!='':
                        urls.append(found)

        # list(set(urls)) => ensure of unicity of urls
        return ([QUrl(url) for url in list(set(urls))], i18n('HTML page'))

    def __parseHtmlForOrigin(self, htmlContent):
        urls=[]
        globalMatches=self.__reHtmlImg.globalMatch(htmlContent)
        while globalMatches.hasNext():
            match = globalMatches.next()
            for name in ('url1', 'url2'):
                if (found:=match.captured(name))!='':
                    urls.append(found)
        # list(set(urls)) => ensure of unicity of urls
        urls=list(set(urls))
        if len(urls)>0:
            return (QUrl(urls[0]), i18n('HTML link'))
        else:
            return (None, None)

    def __parseTextForUrl(self, textContent):
        urls=[]

        globalMatches=self.__reTextUrl.globalMatch(textContent)
        while globalMatches.hasNext():
            match=globalMatches.next()
            urls.append(match.captured('url'))

        # list(set(urls)) => ensure of unicity of urls
        return ([QUrl(url) for url in list(set(urls))], i18n('Text document'))

    def __clipboardMimeContentChanged(self):
        clipboardMimeContent = self.__clipboard.mimeData(QClipboard.Clipboard)

        if clipboardMimeContent is None:
            return

        print('------------------------ Clipboard content changed ------------------------')
        print(clipboardMimeContent.formats())

        if clipboardMimeContent.hasUrls():
            if self.__addPoolUrls(clipboardMimeContent.urls(), 'URI list'):
                self.updated.emit()
            # don't need to process other mime type
            return

        updated = False

        # retrieve any image
        image = self.__clipboard.image()
        imageHash = None
        imageOrigin = None
        if not image is None:
            ptr = image.bits()
            if not ptr is None:
                # image is valid
                ptr.setsize(image.byteCount())
                imageHash = self.__getHash(ptr)
                print(f'Image({imageHash}): {image.width()}x{image.height()} - {image.bitPlaneCount()}bits/channels - {image.depth()}bpp - {image.format():04x}', )
            else:
                # image is not valid
                image = None

        for svgFmt in ('image/svg', 'image/svg+xml'):
            if clipboardMimeContent.hasFormat(svgFmt):
                rawData = clipboardMimeContent.data(svgFmt)
                updated = self.__addPoolSvg(rawData, image)

                if updated:
                    self.updated.emit()
                    return

        if image and clipboardMimeContent.hasFormat('application/x-krita-node'):
            rawData = clipboardMimeContent.data('application/x-krita-node')
            updated = self.__addPoolKraImage(rawData, image, 'application/x-krita-node')
        elif image and clipboardMimeContent.hasFormat('application/x-krita-selection'):
            rawData = clipboardMimeContent.data('application/x-krita-selection')
            updated = self.__addPoolKraImage(rawData, image, 'application/x-krita-selection')
        elif clipboardMimeContent.hasHtml():
            rawData=clipboardMimeContent.html()
            if rawData:
                if image is None:
                    urls, origin = self.__parseHtmlForUrl(rawData)
                    if urls:
                        updated = self.__addPoolUrls(urls, origin)
                else:
                    # an image has been found, parse html to eventually determinate origin of content
                    urlOrigin, origin = self.__parseHtmlForOrigin(rawData)
                    updated = self.__addPoolImage(imageHash, image, urlOrigin, origin)
        elif image is None and clipboardMimeContent.hasText():
            rawData=clipboardMimeContent.text()
            if rawData:
                urls, origin = self.__parseTextForUrl(rawData)
                if urls:
                    updated = self.__addPoolUrls(urls, origin)
        elif image:
            updated = self.__addPoolImage(imageHash, image)

        if updated:
            self.updated.emit()

    def __cacheCleanup(self):
        """Cleanup cache files: remove older items

        Older item are removed from pool and cache
        """
        updated = False

        if self.__totalCacheSizeF > BCClipboard.optionCacheMaxSize():
            # build list of item from flush, ascending sort on timestamp
            hashList=sorted([hash for hash in self.__pool if self.__pool[hash].persistent()], key=lambda hash: self.__pool[hash].timestamp())

            for hash in hashList:
                if self.__totalCacheSizeF < BCClipboard.optionCacheMaxSize():
                    # cache size is now less than maximum size, exit
                    break

                item = self.__pool.pop(hash)
                self.__totalCacheSizeF-=item.cacheSize()
                updated=True

        if updated:
            self.updated.emit()

    def cacheFlush(self):
        """Flush (non persistent) pool content"""
        updated=False
        for root, dirs, files in os.walk(BCClipboard.flushedCacheDirectory()):
            for fileName in files:
                try:
                    os.remove(os.path.join(root, fileName))
                    updated=True
                except Exception as e:
                    Debug.print('[BCClipboard.cacheFlush] Unable to save file {0}: {1}', fileName, str(e))

        if updated:
            self.updated.emit()

    def cacheSize(self, recalculate=False):
        """Return current cache size as a tuple(flushed, persistent)"""
        if recalculate:
            self.__recalculateCacheSize()
        return (self.__totalCacheSizeP, self.__totalCacheSizeF)
