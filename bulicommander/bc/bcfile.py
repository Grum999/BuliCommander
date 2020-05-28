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
# The bcfile module provides some classes that can be used to work with images
#
# Main classes are:
# - BCFile:
#       Define a fileproperties and allows, when it's a [valid] image to easily
#       get some informations (size, thumbnail, preview)
#       The class allows to manage thumbnails with a cache system
#
# - BCFileList:
#       Allows to build file list from directories with filtering&sort criterias
#       using multiprocessing
#       Also provide the possibilty to retrieve thumbnails
#       Results can be exported into different format





from enum import Enum
from functools import cmp_to_key
from multiprocessing import Pool

import hashlib
import json
import os
import re
import sys
import textwrap
import xml.etree.ElementTree as xmlElement
import zipfile

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )

from .bcutils import (
        Debug,
        Stopwatch,

        strToBytesSize,
        bytesSizeToStr,
        strToTs,
        tsToStr
    )

from PyQt5.Qt import *
from PyQt5.QtCore import (
        QSize,
        QStandardPaths
    )
from PyQt5.QtGui import (
        QImage,
        QImageReader
    )

# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
class EInvalidRuleParameter(Exception):
    """An invalid rule parameter has been detected"""
    pass

class EInvalidQueryResult(Exception):
    """Query result is not valid"""
    pass

class BCFileManagedFormat(object):
    """Managed files format """
    KRA = 'kra'
    PNG = 'png'
    JPG = 'jpeg'
    JPEG = 'jpeg'
    ORA = 'ora'
    SVG = 'svg'

    UNKNOWN = 'unknown'
    DIRECTORY = 'directory'

    @staticmethod
    def format(value):
        if isinstance(value, str):
            lvalue=value.lower()
            if lvalue in [BCFileManagedFormat.KRA,
                          BCFileManagedFormat.PNG,
                          BCFileManagedFormat.JPEG,
                          BCFileManagedFormat.ORA,
                          BCFileManagedFormat.SVG]:
                return lvalue
            elif lvalue == 'jpg':
                return BCFileManagedFormat.JPEG
        raise EInvalidType("Invalid given format")

class BCFileThumbnailSize(Enum):
    """Possible sizes for a thumbnail file"""

    SMALL = 64
    MEDIUM = 128
    LARGE = 256
    HUGE = 512

    def next(self):
        """Return next size, None if there's no next size"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) + 1
        if index >= len(members):
            return None
        return members[index]

    def prev(self):
        """Return previous size, None if there's no previous size"""
        cls = self.__class__
        members = list(cls)
        index = members.index(self) - 1
        if index < 0:
            return None
        return members[index]

class BCFileThumbnailFormat(Enum):
    """Possible format for a thumbnail file"""
    PNG = 'png'
    JPEG = 'jpeg'

class BCFileProperty(Enum):
    PATH = 'path'
    FULL_PATHNAME = 'fullPathName'
    FILE_NAME = 'fileName'
    FILE_FORMAT = 'fileFormat'
    FILE_SIZE = 'fileSize'
    FILE_DATE = 'fileDate'
    IMAGE_WIDTH = 'imageWidth'
    IMAGE_HEIGHT = 'imageHeight'

    def translate(self):
        if self == BCFileProperty.PATH:
            return 'path'
        elif self == BCFileProperty.FULL_PATHNAME:
            return 'full path/file name'
        elif self == BCFileProperty.FILE_NAME:
            return 'file name'
        elif self == BCFileProperty.FILE_FORMAT:
            return 'file format'
        elif self == BCFileProperty.FILE_SIZE:
            return 'file size'
        elif self == BCFileProperty.FILE_DATE:
            return 'file date'
        elif self == BCFileProperty.IMAGE_WIDTH:
            return 'image width'
        elif self == BCFileProperty.IMAGE_HEIGHT:
            return 'image height'
        else:
            return self.value

class BCBaseFile(object):
    """Base class for directories and files"""

    def __init__(self, fileName):
        """Initialise BCFile"""
        self._fullPathName = os.path.expanduser(fileName)
        self._name = os.path.basename(self._fullPathName)
        self._path = os.path.dirname(self._fullPathName)
        self._mdatetime = os.path.getmtime(self._fullPathName)
        self._format = BCFileManagedFormat.UNKNOWN

    def path(self):
        """Return file path"""
        return self._path

    def name(self):
        """Return file name"""
        return self._name

    def fullPathName(self):
        """Return full file path/name"""
        return self._fullPathName

    def format(self):
        """Return file format"""
        return self._format

    def lastModificationDateTime(self, onlyDate=False):
        """Return file last modification time stamp"""
        if onlyDate:
            return strToTs(tsToStr(self._mdatetime, 'd'))
        return self._mdatetime

    def getProperty(self, property):
        """return property value"""
        if property == BCFileProperty.PATH:
            return self._path
        elif property == BCFileProperty.FULL_PATHNAME:
            return self._fullPathName
        elif property == BCFileProperty.FILE_NAME:
            return self._name
        elif property == BCFileProperty.FILE_FORMAT:
            return self._format
        elif property == BCFileProperty.FILE_DATE:
            return self._mdatetime
        elif isinstance(property, BCFileProperty):
            return None
        else:
            raise EInvalidType('Given `property` must be a valid <BCFileProperty>')

class BCDirectory(BCBaseFile):
    """Provides common properties with BCFile to normalize way directory & file
    informations are managed

    Note: BCDirectory is not aimed to be instancied directly and to improve execution
          times there's no real control about file (is it a directory? does it exists?)
          consider that this kind of controls must be made before
    """

    def __init__(self, fileName):
        super(BCDirectory, self).__init__(fileName)
        self._format = BCFileManagedFormat.DIRECTORY

    def __repr__(self):
        """Format internal representation"""
        return f'<BCDirectory({self._path}, {self._name})>'

class BCFile(BCBaseFile):
    """Provide an easy way to work with images files:
    - File properties (name, path, siz, date)
    - Image information (format, size)
    - Image content (jpeg, png, kra)
    - Image thumbnail (with cache)

    Note: BCFile is not aimed to be instancied directly and to improve execution
          times there's no real control about file (is it a file? does it exists?)
          consider that this kind of controls must be made before
    """
    # TODO: if file timestamp is modified, regenerate infor + thumbnail

    __CHUNK_SIZE = 8192

    __THUMBNAIL_CACHE_PATH = ''
    __THUMBNAIL_CACHE_FMT = BCFileThumbnailFormat.JPEG
    __THUMBNAIL_CACHE_DEFAULTSIZE = BCFileThumbnailSize.MEDIUM
    __THUMBNAIL_CACHE_COMPRESSION = 100

    __INITIALISED = False

    __EXTENSIONS = ['.png', '.jpeg', '.jpg', '.ora', '.svg', '.kra', '.kra~', '']

    @staticmethod
    def initialiseCache(thumbnailCachePath=None, thumbnailCacheFormat=None, thumbnailCacheDefaultSize=None):
        """Initialise thumbnails cache properties


        By default, cache will be defined into user cache directory
        If `thumbnailCachePath` is provided, it will define the thumbnail cache directory to use

        If directory doesn't exist, it will be created
        """

        BCFile.setThumbnailCacheDirectory(thumbnailCachePath)
        BCFile.setThumbnailCacheFormat(thumbnailCacheFormat)
        BCFile.setThumbnailCacheDefaultSize(thumbnailCacheDefaultSize)

        BCFile.__INITIALISED = True

    def __init__(self, fileName, strict=True):
        """Initialise BCFile"""
        super(BCFile, self).__init__(fileName)
        self._format = BCFileManagedFormat.UNKNOWN
        self.__size = 0
        self.__imgSize = QSize(-1, -1)
        self.__qHash = ''
        self.__readable = False

        if not BCFile.__INITIALISED:
            raise EInvalidStatus('BCFile class is not initialised')

        self.__initFromFileName(fileName, strict)

    # region: miscellaneous ----------------------------------------------------

    def __repr__(self):
        """Format internal representation"""
        return f'<BCFile({self.__readable}, {self._format}, {self._path}, {self._name}, {self.__size}, {self.__qHash}, {self.__imgSize})>'

    # endregion: miscellaneous -------------------------------------------------


    # region: initialisation ---------------------------------------------------

    def __initFromFileName(self, fileName, strict):
        """Initialize file information from given full file name

        BCFile will:
        - Check if file exists
        - Read file property (format, file size, image dimension, qHash)

        If strict is True, check only files for which extension is known
        If strict is False, try to determinate file format even if there's no extension
        """
        #if os.path.isfile(fileName):
        self.__readable = True

        dummy, fileExtension = os.path.splitext(fileName)
        fileExtension=fileExtension.lower()

        self.__size = os.path.getsize(self._fullPathName)

        if strict and fileExtension == '':
            self.__readable = True
            return

        if fileExtension in self.__EXTENSIONS:
            imageReader = QImageReader(self._fullPathName)

            if imageReader.canRead():
                self._format = bytes(imageReader.format()).decode().lower()
                if self._format == 'jpg':
                    # harmonize file type
                    self._format = BCFileManagedFormat.JPEG
            else:
                self._format = fileExtension[1:]    # remove '.'

            if self._format in [BCFileManagedFormat.JPEG, BCFileManagedFormat.PNG, BCFileManagedFormat.SVG]:
                # Use image reader
                self.__imgSize = imageReader.size()
            elif self._format == BCFileManagedFormat.KRA or fileExtension in ['.kra', '.kra~']:
                # Image reader can't read file...
                # or some file type (kra, ora) seems to not properly be managed
                # by qimagereader
                size = self.__readKraImageSize()
                if not size is None:
                    self.__imgSize = size
                    self._format = BCFileManagedFormat.KRA
            elif self._format == BCFileManagedFormat.ORA or fileExtension == '.ora':
                # Image reader can't read file...
                # or some file type (kra, ora) seems to not properly be managed
                # by qimagereader
                size = self.__readOraImageSize()
                if not size is None:
                    self.__imgSize = size
                    self._format = BCFileManagedFormat.ORA
            elif fileExtension == '':
                # don't know file format by ImageReader or extension...
                # and there's no extension
                # try Kra..
                size = self.__readKraImageSize()
                if not size is None:
                    self.__imgSize = size
                    self._format = BCFileManagedFormat.KRA
                else:
                    # try ora
                    size = self.__readOraImageSize()
                    if not size is None:
                        self.__imgSize = size
                        self._format = BCFileManagedFormat.ORA
                    else:
                        # Unable to determinate format
                        self.__readable = False

            # update qHash for file
            if self.__readable:
                self.__calculateQuickHash()
        else:
            self.__readable = False

    # endregion: initialisation ------------------------------------------------


    # region: utils ------------------------------------------------------------


    def __calculateQuickHash(self):
        """Calculate a 'quick' hash on file with Blake2B method

        To improve speedup on hash calculation, read only first and last 8.00KB from file
        => most of file have their image properties (size and other technical information) at the beginning of file
           + use the last 8KB to reduce risk of colision

          Risk for collision is not null, but tested on ~12000 different images from 16KB to 160MB, nothing bad happened
          Hash calculation for 12000 files (~114.00GB) take ~2.70s, that's seems good enough (hopr nobody have so much image
          files in the same directory ^_^')
        """
        if self.__readable:
            try:
                with open(self._fullPathName, "rb") as fileHandle:
                    # digest = 256bits (32Bytes)
                    fileHash = hashlib.blake2b(digest_size=32)

                    # read 1st 8.00KB and update hash
                    fileHash.update(fileHandle.read(BCFile.__CHUNK_SIZE))

                    if self.__size > BCFile.__CHUNK_SIZE:
                        # file size is greater than 8.00KB, read last 8.00KB and update hash
                        fileHandle.seek(self.__size - BCFile.__CHUNK_SIZE)
                        fileHash.update(fileHandle.read(BCFile.__CHUNK_SIZE))

                    self.__qHash = fileHash.hexdigest()
            except Exception as e:
                Debug.print('[BCFile.__readKraImageSize] Unable to calculate hash file {0}: {1}', self._fullPathName, str(e))
                self.__qHash = ''
        else:
            self.__qHash = ''


    def __readKraImageSize(self):
        """Read a krita (.kra) file and return image size

        The function only unzip the maindoc.xml to speedup the process

        return None if not able to read Krita file
        return a QSize() otherwise
        """
        if not self.__readable:
            # file must exist
            return None

        try:
            archive = zipfile.ZipFile(self._fullPathName, 'r')
        except Exception as e:
            # can't be read (not exist, not a zip file?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImageSize] Unable to open file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            imgfile = archive.open('maindoc.xml')
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImageSize] Unable to find "maindoc.xml" in file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            maindoc = imgfile.read()
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImageSize] Unable to read "maindoc.xml" in file {0}: {1}', self._fullPathName, str(e))
            return None


        try:
            xmlDoc = xmlElement.fromstring(maindoc.decode())
        except Exception as e:
            # can't be read (not xml?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImageSize] Unable to parse "maindoc.xml" in file {0}: {1}', self._fullPathName, str(e))
            return None

        returned = QSize(-1, -1)

        try:
            returned.setWidth(int(xmlDoc[0].attrib['width']))
        except Exception as e:
            Debug.print('[BCFile.__readKraImageSize] Unable to retrieve image width in file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            returned.setHeight(int(xmlDoc[0].attrib['height']))
        except Exception as e:
            Debug.print('[BCFile.__readKraImageSize] Unable to retrieve image height in file {0}: {1}', self._fullPathName, str(e))
            return None

        return returned


    def __readOraImageSize(self):
        """Read an OpenRaster (.ora) file and return image size

        The function only unzip the stack.xml to speedup the process

        return None if not able to read OpenRaster file
        return a QSize() otherwise
        """
        if not self.__readable:
            # file must exist
            return None

        try:
            archive = zipfile.ZipFile(self._fullPathName, 'r')
        except Exception as e:
            # can't be read (not exist, not a zip file?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImageSize] Unable to open file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            imgfile = archive.open('stack.xml')
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImageSize] Unable to find "stack.xml" in file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            maindoc = imgfile.read()
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImageSize] Unable to read "stack.xml" in file {0}: {1}', self._fullPathName, str(e))
            return None


        try:
            xmlDoc = xmlElement.fromstring(maindoc.decode())
        except Exception as e:
            # can't be read (not xml?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImageSize] Unable to parse "stack.xml" in file {0}: {1}', self._fullPathName, str(e))
            return None

        returned = QSize(-1, -1)

        try:
            returned.setWidth(int(xmlDoc.attrib['w']))
        except Exception as e:
            Debug.print('[BCFile.__readOraImageSize] Unable to retrieve image width in file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            returned.setHeight(int(xmlDoc.attrib['h']))
        except Exception as e:
            Debug.print('[BCFile.__readOraImageSize] Unable to retrieve image height in file {0}: {1}', self._fullPathName, str(e))
            return None


        return returned


    def __readKraImage(self):
        """Return Krita file image

        The function only unzip the mergedimage.png to speedup the process

        return None if not able to read Krita file
        return a QImage() otherwise
        """
        if not self.__readable:
            # file must exist
            return None


        try:
            archive = zipfile.ZipFile(self._fullPathName, 'r')
        except Exception as e:
            # can't be read (not exist, not a zip file?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImage] Unable to open file {0}: {1}', self._fullPathName, str(e))
            return None

        pngFound = True

        try:
            imgfile = archive.open('mergedimage.png')
        except Exception as e:
            pngFound = False

        if not pngFound:
            try:
                # fallback: try to read preview file
                imgfile = archive.open('preview.png')
                pngFound = True
            except Exception as e:
                pngFound = False

        if not pngFound:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImage] Unable to find "mergedimage.png" in file {0}', self._fullPathName)
            return None

        try:
            image = imgfile.read()
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImage] Unable to read "mergedimage.png" in file {0}: {1}', self._fullPathName, str(e))
            return None


        try:
            returned = QImage()
            returned.loadFromData(image)
        except Exception as e:
            # can't be read (not png?)
            self.__readable = False
            Debug.print('[BCFile.__readKraImage] Unable to parse "mergedimage.png" in file {0}: {1}', self._fullPathName, str(e))
            return None

        return returned


    def __readOraImage(self):
        """Return OpenRaster file image

        The function only unzip the Thumbnail/thumbnail.png to speedup the process
        Note: this file is a thumbnail and might have a big reduced size...

        return None if not able to read OpenRaster file
        return a QImage() otherwise
        """
        if not self.__readable:
            # file must exist
            return None

        try:
            archive = zipfile.ZipFile(self._fullPathName, 'r')
        except Exception as e:
            # can't be read (not exist, not a zip file?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImage] Unable to open file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            imgfile = archive.open('/Thumbnail/thumbnail.png')
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImage] Unable to find "thumbnail.png" in file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            image = imgfile.read()
        except Exception as e:
            # can't be read (not exist, not a Kra file?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImage] Unable to read "thumbnail.png" in file {0}: {1}', self._fullPathName, str(e))
            return None

        try:
            returned = QImage()
            returned.loadFromData(image)
        except Exception as e:
            # can't be read (not png?)
            self.__readable = False
            Debug.print('[BCFile.__readOraImage] Unable to parse "thumbnail.png" in file {0}: {1}', self._fullPathName, str(e))
            return None

        return returned


    # endregion: utils ---------------------------------------------------------


    # region: getter/setters ---------------------------------------------------

    @staticmethod
    def thumbnailCacheDirectory(size=None):
        """Return current thumbnail cache directory"""

        if not isinstance(size, BCFileThumbnailSize):
            # size is not a BCFileThumbnailSize (none or invalid value)
            # return root path
            return BCFile.__THUMBNAIL_CACHE_PATH
        else:
            return os.path.join(BCFile.__THUMBNAIL_CACHE_PATH, str(size.value))

    @staticmethod
    def setThumbnailCacheDirectory(thumbnailCachePath=None):
        """Set current thumbnail cache directory

        If no value provided, reset to default value
        """
        if thumbnailCachePath is None or thumbnailCachePath == '':
            thumbnailCachePath = os.path.join(QStandardPaths.writableLocation(QStandardPaths.CacheLocation), "bulicommander")
        else:
            thumbnailCachePath = os.path.expanduser(thumbnailCachePath)

        if not isinstance(thumbnailCachePath, str):
            raise EInvalidType("Given `thumbnailCachePath` must be a valid <str> ")

        try:
            BCFile.__THUMBNAIL_CACHE_PATH = thumbnailCachePath
            os.makedirs(thumbnailCachePath, exist_ok=True)
            for size in BCFileThumbnailSize:
                os.makedirs(BCFile.thumbnailCacheDirectory(size), exist_ok=True)
        except Exception as e:
            Debug.print('[BCFile.setThumbnailCacheDirectory] Unable to create directory {0}: {1}', thumbnailCachePath, str(e))
            return

    @staticmethod
    def thumbnailCacheFormat():
        """Return current thumbnail cache format"""
        return BCFile.__THUMBNAIL_CACHE_FMT

    @staticmethod
    def setThumbnailCacheFormat(thumbnailCacheFormat=None):
        """Set current thumbnail cache format

        If no file format is provided or if invalid, set default format JPEG
        """
        if not isinstance(thumbnailCacheFormat, BCFileThumbnailFormat):
            BCFile.__THUMBNAIL_CACHE_FMT = BCFileThumbnailFormat.JPEG
        else:
            BCFile.__THUMBNAIL_CACHE_FMT = thumbnailCacheFormat

        if BCFile.__THUMBNAIL_CACHE_FMT == BCFileThumbnailFormat.PNG:
            BCFile.__THUMBNAIL_CACHE_COMPRESSION = 100
        else:
            if BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE in [BCFileThumbnailSize.SMALL, BCFileThumbnailSize.MEDIUM]:
                # on smaller image, jpeg compression artifact are more visible, so reduce compression
                BCFile.__THUMBNAIL_CACHE_COMPRESSION = 95
            else:
                # on bigger image, we can reduce quality to get a better compression and sve disk :)
                BCFile.__THUMBNAIL_CACHE_COMPRESSION = 85

    @staticmethod
    def thumbnailCacheDefaultSize():
        """Return current thumbnail cdefault cache size"""
        return BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE

    @staticmethod
    def setThumbnailCacheDefaultSize(thumbnailCacheDefaultSize=None):
        """Set current thumbnail default cache size

        If no size is provided or if invalid, set default size MEDIUM
        """
        if not isinstance(thumbnailCacheDefaultSize, BCFileThumbnailSize):
            BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE = BCFileThumbnailSize.MEDIUM
        else:
            BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE = thumbnailCacheDefaultSize

        if BCFile.__THUMBNAIL_CACHE_FMT == BCFileThumbnailFormat.JPEG:
            if BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE in [BCFileThumbnailSize.SMALL, BCFileThumbnailSize.MEDIUM]:
                # on smaller image, jpeg compression artifact are more visible, so reduce compression
                BCFile.__THUMBNAIL_CACHE_COMPRESSION = 95
            else:
                # on bigger image, we can reduce quality to get a better compression and sve disk :)
                BCFile.__THUMBNAIL_CACHE_COMPRESSION = 85

    def size(self):
        """Return file size"""
        return self.__size

    def imageSize(self):
        """Return file image size"""
        return self.__imgSize

    def qHash(self):
        """Return file quick hash"""
        return self.__qHash

    def readable(self):
        """Return True if file is readable"""
        return self.__readable

    def image(self):
        """Return file image

        Note:
        - for OpenRaster, return thumbnail
        - for Krita, return merged preview

        If not possible to return image, return None
        Otherwise, return a QImage
        """
        if not self.__readable:
            return None

        if self._format == BCFileManagedFormat.KRA:
            return self.__readKraImage()
        elif self._format == BCFileManagedFormat.ORA:
            return self.__readOraImage()
        else:
            try:
                return QImage(self._fullPathName)
            except:
                return None

    def thumbnail(self, cache=True):
        """Return file thumbnail according to current BCFile default cache size

        If `cache` is True:
            If a thumbnail already exist in cache, method will use it
            Otherwise, method will:
            - Load image
            - Reduce size
            - Save thumbnail into cache
            - Return thumbnail

        If `cache` is False:
            - Load image
            - Reduce size
            - Return thumbnail

        If not possible to return image, return None
        Otherwise, return a QImage
        """
        imageSrc = None

        if cache:
            # check if thumbnail is cached
            sourceSize = BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE

            while not sourceSize is None:
                thumbnailFile = os.path.join(BCFile.thumbnailCacheDirectory(sourceSize), f'{self.__qHash}.{BCFile.__THUMBNAIL_CACHE_FMT.value}')

                if os.path.isfile(thumbnailFile):
                    # thumbnail found!
                    imageSrc = QImage(thumbnailFile)

                    if sourceSize == BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE:
                        # the found thumbnail is already to expected size, return it
                        return imageSrc
                    break

                # use larger thumbnail size as source
                sourceSize = sourceSize.next()


        if not cache or imageSrc is None:
            # load full image size from file
            imageSrc = self.image()
            if imageSrc is None:
                return None

        # make thumbnail
        thumbnailImg = imageSrc.scaled(QSize(BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE.value, BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE.value), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        if not cache:
            # no need to save thumbnail
            return thumbnailImg

        thumbnailFile = os.path.join(BCFile.thumbnailCacheDirectory(BCFile.__THUMBNAIL_CACHE_DEFAULTSIZE), f'{self.__qHash}.{BCFile.__THUMBNAIL_CACHE_FMT.value}')
        try:
            thumbnailImg.save(thumbnailFile, quality=BCFile.__THUMBNAIL_CACHE_COMPRESSION)
        except Exception as e:
            Debug.print('[BCFile.thumbnail] Unable to save thumbnail in cache {0}: {1}', thumbnailFile, str(e))

        # finally, return thumbnail
        return thumbnailImg

    def getProperty(self, property):
        """return property value"""
        if property == BCFileProperty.FILE_SIZE:
            return self.__size
        elif property == BCFileProperty.IMAGE_WIDTH:
            return self.__imgSize.width()
        elif property == BCFileProperty.IMAGE_HEIGHT:
            return self.__imgSize.height()
        else:
            return super(BCFile, self).getProperty(property)

    # endregion: getter/setters ------------------------------------------------

class BCFileListRuleOperatorType(Enum):
    """Possible rule operator value type"""
    INT = 0
    FLOAT = 1
    DATE = 2
    DATETIME = 3
    STRING = 4
    LIST = 5
    ENUM = 6
    REGEX = 7

class BCFileListRuleOperator(object):
    """Store properties for a rule:
    - Value (to compare)
    - Displayed value (for string representation)
    - Operator

    Do controls about value type and allows to do comparisaon with another value
    """
    def __init__(self, value, operator=None, type=None, displayValue=None):
        self.__type = None
        self.__operator = None
        self.__value = None
        self.__displayValue = None

        if isinstance(value, BCFileListRuleOperator):
            self.__type = value.type()
            self.__setOperator(value.operator())
            self.setValue(value.value(), value.displayValue())
        else:
            if not isinstance(type, BCFileListRuleOperatorType):
                raise EInvalidType("Rule type must be of type <BCFileListRuleOperatorType>")

            self.__type = type

            self.__setOperator(operator)
            self.setValue(value, displayValue)

    def __checkValueType(self, value=None):
        if value is None:
            value = self.__value

        if isinstance(value, list) or isinstance(value, tuple):
            values = value
        elif self.__type == BCFileListRuleOperatorType.LIST:
            if not (isinstance(value, list) or isinstance(value, tuple)):
                raise EInvalidType("Given value type must be <list>")
            else:
                return
        else:
            values = [value]

        for value in values:
            # check if all item in list match given type
            if self.__type == BCFileListRuleOperatorType.INT and not isinstance(value, int):
                raise EInvalidType("Given value type must be <int>")
            elif self.__type == BCFileListRuleOperatorType.FLOAT and not isinstance(value, float):
                raise EInvalidType("Given value type must be <float>")
            elif self.__type in [BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME] and not (isinstance(value, float) or isinstance(value, int)):
                raise EInvalidType("Given value type must be <float>")
            elif self.__type == BCFileListRuleOperatorType.STRING and not isinstance(value, str):
                raise EInvalidType("Given value type must be <str>")
            elif self.__type == BCFileListRuleOperatorType.ENUM and not isinstance(value, Enum):
                raise EInvalidType("Given value type must be <Enum>")
            if self.__type == BCFileListRuleOperatorType.REGEX and not isinstance(value, re.Pattern):
                raise EInvalidType("Given value type must be <re.Pattern>")

    def __setOperator(self, value):
        """Set current operator"""
        if self.__type == BCFileListRuleOperatorType.REGEX:
            if not value is None and value.lower() in ['match', 'not match']:
                # in this case, operator is 'match' or 'not match':
                self.__operator = value.lower()
            else:
                raise EInvalidValue("Given `operator` must be one of the following value: 'match', 'not match'")
        elif not value is None and value.lower() in ['=', '<>', '<', '>', '<=', '>=', 'in', 'between', 'not in', 'not between']:
            self.__operator = value.lower()
        elif value == '!=':
            self.__operator = '<>'
        else:
            raise EInvalidValue("Given `operator` must be one of the following value: '=', '<>', '<', '>', '<=', '>=', 'in', 'between', 'not in', 'not between'")

    def __str__(self):
        """Return rule operator as string"""
        value = self.__value
        if self.__type == BCFileListRuleOperatorType.ENUM and isinstance(value, Enum):
            value = value.value

        if isinstance(value, list) and self.__operator in ['in', 'not in']:
            return f"{self.__operator} {self.__enumToStr(value)}"
        elif isinstance(value, tuple) and self.__operator in ['between', 'not between']:
            if self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM]:
                return f'{self.__operator} ("{self.__enumToStr(value[0])}", "{self.__enumToStr(value[1])}")'
            else:
                return f"{self.__operator} ({value[0]}, {value[1]})"
        elif self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM]:
            return f'{self.__operator} "{value}"'
        elif self.__type == BCFileListRuleOperatorType.REGEX:
            return f'{self.__operator} "{value.pattern}"'
        else:
            return f"{self.__operator} {value}"

    def __enumToStr(self, value):
        """return printable value for enum"""
        if self.__type == BCFileListRuleOperatorType.ENUM:
            if isinstance(value, tuple):
                return tuple([v.value for v in value])
            elif isinstance(value, list):
                return [v.value for v in value]
            else:
                return value.value
        return value

    def type(self):
        """Return current type"""
        return self.__type

    def displayValue(self):
        """Return current set displayValue"""
        return self.__displayValue

    def value(self):
        """Return current set value"""
        return self.__value

    def setValue(self, value, displayValue=None):
        """Set current value"""
        if value is None:
            raise EInvalidValue("Given value can't be None")

        if self.__type == BCFileListRuleOperatorType.REGEX and isinstance(value, str):
            self.__value = re.compile(value)
        elif self.__operator == 'in':
            if isinstance(value, tuple):
                self.__value = list(value)
            elif isinstance(value, list):
                self.__value = value
            else:
                self.__value = [value]
        elif self.__operator == 'between':
            if isinstance(value, tuple):
                self.__value = value[0:2]
            elif isinstance(value, list):
                self.__value = tuple(value[0:2])
            else:
                self.__value = (value, value)
        else:
            self.__value = value



        if displayValue is None:
            if self.__type == BCFileListRuleOperatorType.DATETIME:
                if isinstance(self.__value, tuple):
                    self.__displayValue = tuple([tsToStr(value) for value in self.__value])
                elif isinstance(self.__value, list):
                    self.__displayValue = [tsToStr(value) for value in self.__value]
                else:
                    self.__displayValue = tsToStr(self.__value)
            elif self.__type == BCFileListRuleOperatorType.DATE:
                if isinstance(self.__value, tuple):
                    self.__displayValue = tuple([tsToStr(value, 'd') for value in self.__value])
                elif isinstance(self.__value, list):
                    self.__displayValue = [tsToStr(value, 'd') for value in self.__value]
                else:
                    self.__displayValue = tsToStr(self.__value, 'd')
            elif self.__type == BCFileListRuleOperatorType.REGEX:
                self.__displayValue = self.__value.pattern
            else:
                self.__displayValue = self.__value
        else:
            self.__displayValue = displayValue

        self.__checkValueType()

    def operator(self):
        """Return current set operator"""
        return self.__operator

    def translate(self, short=False):
        returned = ''
        if short:
            if self.__operator == 'between':
                returned = 'between ({0}, {1})'
            elif self.__operator == 'not between':
                returned = 'not between ({0}, {1})'
            else:
                returned = self.__operator + ' '
        elif self.__operator == '=':
            returned = 'is equal to '
        elif self.__operator == '<>':
            returned = 'is not equal to '
        elif self.__operator == '<':
            returned = 'is lower than '
        elif self.__operator == '>':
            returned = 'is greater than '
        elif self.__operator == '<=':
            returned = 'is lower or equal than '
        elif self.__operator == '>=':
            returned = 'is greater or equal than '
        elif self.__operator == 'in':
            returned = 'is in '
        elif self.__operator == 'between':
            returned = 'is between {0} and {1}'
        elif self.__operator == 'match':
            returned = 'match '
        elif self.__operator == 'not match':
            returned = 'not match '
        elif self.__operator == 'not in':
            returned = 'is not in '
        elif self.__operator == 'not between':
            returned = 'is not between {0} and {1}'
        else:
            # shnould not occurs
            returned =self.__operator + ' '

        value = self.__displayValue
        if isinstance(value, Enum):
            value = value.value

        if isinstance(value, list) and self.__operator in ['in', 'not in']:

            if self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM, BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME]:
                returned += '["'+ '", "'.join([self.__enumToStr(v) for v in value]) +'"]'
            else:
                returned += '['+ ', '.join([self.__enumToStr(v) for v in value]) +']'

        elif isinstance(value, tuple) and self.__operator in ['between', 'not between']:
            if self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM, BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME]:
                returned = returned.format(f'"{self.__enumToStr(value[0])}"', f'"{self.__enumToStr(value[1])}"')
            else:
                returned = returned.format(value[0], value[1])
        elif self.__type in [BCFileListRuleOperatorType.STRING, BCFileListRuleOperatorType.ENUM, BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME, BCFileListRuleOperatorType.REGEX]:
            returned += f'"{value}"'
        else:
            returned += f"{value}"

        return returned

    def compare(self, value):
        """Compare value according to current rule, and return True or False"""
        if self.__type == BCFileListRuleOperatorType.REGEX:
            if not isinstance(value, str):
                raise EInvalidType("Given value type must be <str>")
        elif not self.__type in [BCFileListRuleOperatorType.LIST]:
            self.__checkValueType(value)

        if self.__operator == '=':
            return (value == self.__value)
        elif self.__operator == '<>':
            return (value != self.__value)
        elif self.__operator == '<':
            return (value < self.__value)
        elif self.__operator == '>':
            return (value > self.__value)
        elif self.__operator == '<=':
            return (value <= self.__value)
        elif self.__operator == '>=':
            return (value >= self.__value)
        elif self.__operator == 'in':
            return (value in self.__value)
        elif self.__operator == 'between':
            return (self.__value[0] <= value and value <= self.__value[1])
        elif self.__operator == 'not in':
            return not(value in self.__value)
        elif self.__operator == 'not between':
            return not(self.__value[0] <= value and value <= self.__value[1])
        elif self.__operator == 'match':
            return not(self.__value.search(value) is None)
        elif self.__operator == 'not match':
            return (self.__value.search(value) is None)
        else:
            # should not occurs
            return False

class BCFileListRule(object):
    """Define single rules to search files"""

    def __init__(self, source=None):
        """Initialise a rule"""
        self.__name = None
        self.__size = None
        self.__mdatetime = None
        self.__format = None
        self.__imageWidth = None
        self.__imageHeight = None

        if isinstance(source, BCFileListRule):
            self.setName(source.name())
            self.setSize(source.size())
            self.setModifiedDateTime(source.modifiedDateTime())
            self.setFormat(source.format())
            self.setImageWidth(source.imageWidth())
            self.setImageHeight(source.imageHeight())

    def __str__(self):
        """Return rule as string"""

        returned = []

        if not self.__name is None:
            returned.append(f"{BCFileProperty.FILE_NAME.value} {self.__name.translate(True)}")

        if not self.__size is None:
            returned.append(f"{BCFileProperty.FILE_SIZE.value} {self.__size.translate(True)}")

        if not self.__mdatetime is None:
            returned.append(f"{BCFileProperty.FILE_DATE.value} {self.__mdatetime.translate(True)}")

        if not self.__format is None:
            returned.append(f"{BCFileProperty.FILE_FORMAT.value} {self.__format.translate(True)}")

        if not self.__imageWidth is None:
            returned.append(f"{BCFileProperty.IMAGE_WIDTH.value} {self.__imageWidth.translate(True)}")

        if not self.__imageHeight is None:
            returned.append(f"{BCFileProperty.IMAGE_HEIGHT.value} {self.__imageHeight.translate(True)}")

        return ' and '.join(returned)

    def __repr__(self):
        """Return rule as string"""
        return f'<BCFileListRule(name {self.__name}; fileSize {self.__size}; datetime {self.__mdatetime}; format {self.__format}; width {self.__imageWidth}; height {self.__imageHeight}; hash={self.hash()})>'

    def hash(self):
        """Return a hash from rule"""
        hashNfo = hashlib.blake2b(digest_size=32)
        hashNfo.update(self.__str__().encode())
        return hashNfo.hexdigest()

    def translate(self, short=False):
        """Return rule as a human readable string"""
        returned = []

        if short:
            return self.__str__()

        if not self.__name is None:
            returned.append(f"{BCFileProperty.FILE_NAME.translate()} {self.__name.translate()}")

        if not self.__size is None:
            returned.append(f"{BCFileProperty.FILE_SIZE.translate()} {self.__size.translate()}")

        if not self.__mdatetime is None:
            returned.append(f"{BCFileProperty.FILE_DATE.translate()} {self.__mdatetime.translate()}")

        if not self.__format is None:
            returned.append(f"{BCFileProperty.FILE_FORMAT.translate()} {self.__format.translate()}")

        if not self.__imageWidth is None:
            returned.append(f"{BCFileProperty.IMAGE_WIDTH.translate()} {self.__imageWidth.translate()}")

        if not self.__imageHeight is None:
            returned.append(f"{BCFileProperty.IMAGE_HEIGHT.translate()} {self.__imageHeight.translate()}")

        if len(returned) == 0:
            return ''

        return " - "+"\n - ".join(returned)

    def name(self):
        """Return current matching pattern"""
        return self.__name

    def setName(self, value):
        """Set current matching pattern"""
        if isinstance(value, tuple):
            displayValue = value[0]

            if isinstance(value[0], str):
                checkIsRegEx = re.search('^re:(.*)', value[0])
                if not checkIsRegEx is None:
                    # provided as a regular expression
                    displayValue = checkIsRegEx.group(1)
                    value = (re.compile( checkIsRegEx.group(1) ), value[1])
                else:
                    # provided as a wildcard character
                    # convert to regex
                    displayValue = value[0]
                    value = (re.compile( '^'+value[0].replace('.', r'\.').replace('*', r'.*').replace('?', '.')+'$' ), value[1])
            elif isinstance(value[0], re.Pattern):
                displayValue = value[0].pattern
            else:
                raise EInvalidRuleParameter("Given `name` must be a valid value")

            self.__name = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.REGEX, displayValue)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.REGEX:
            self.__name = value
        else:
            raise EInvalidRuleParameter("Given `name` must be a valid value")

    def size(self):
        """Return current size rule"""
        return self.__size

    def setSize(self, value):
        """set current size rule

        Given `value` can be:
        - A BCFileListRuleOperator
        - A tuple (value, operator)
        """
        if isinstance(value, tuple):
            displayValue = value[0]
            if isinstance(value[0], str):
                value = (strToBytesSize(value[0]), value[1])
            elif isinstance(value[0], float):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([strToBytesSize(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([strToBytesSize(v) for v in value[0]], value[1])
            elif not isinstance(value[0], int):
                raise EInvalidRuleParameter("Given `size` must be a valid value")

            self.__size = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.INT, displayValue)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.INT:
            self.__size = value
        else:
            raise EInvalidRuleParameter("Given `size` must be a valid value")

    def modifiedDateTime(self):
        """Return current modification date/time rule"""
        return self.__mdatetime

    def setModifiedDateTime(self, value):
        """set current modification date/time rule"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (strToTs(value[0]), value[1])
            elif isinstance(value[0], int):
                value = (float(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([strToTs(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([strToTs(v) for v in value[0]], value[1])
            elif not isinstance(value[0], float):
                raise EInvalidRuleParameter("Given `date` must be a valid value")


            ruleType = BCFileListRuleOperatorType.DATETIME

            # now, value is a timestamp
            # reconvert it to string => YYYY-MM-DD HH:MI:SS
            # and determinate if it's a DATE (HH:MI:SS = 00:00:00) a DATETIME (HH:MI:SS <> 00:00:00)
            if isinstance(value[0], float):
                checkHour = re.search('00:00:00', tsToStr(value[0]))
                if not checkHour is None:
                    # hour = 00:00:00
                    ruleType = BCFileListRuleOperatorType.DATE
            elif isinstance(value[0], tuple):
                # interval (between)
                # in this case, always date/time
                # => fix end hour to 23:59:59.9999 if not already defined
                checkHour = re.search('00:00:00', tsToStr(value[0][1]))
                if not checkHour is None:
                    # hour = 00:00:00
                    value = ((value[0][0], value[0][1] + 86399.9999), value[1])
            elif isinstance(value[0], list):
                # list (in)
                # not possible to mix dates and date/time so consider that if all items are date, it's date
                # otherwise it's date/time
                ruleType = BCFileListRuleOperatorType.DATE

                for dateItem in value[0]:
                    checkHour = re.search('00:00:00', tsToStr(dateItem))
                    if checkHour is None:
                        ruleType = BCFileListRuleOperatorType.DATETIME
                        break

            self.__mdatetime = BCFileListRuleOperator(value[0], value[1], ruleType)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() in [BCFileListRuleOperatorType.DATE, BCFileListRuleOperatorType.DATETIME]:
            self.__mdatetime = value
        else:
            raise EInvalidRuleParameter("Given `date` must be a valid value")

    def format(self):
        """Return current format rule"""
        return self.__format

    def setFormat(self, value):
        """set current format rule"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (BCFileManagedFormat.format(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([BCFileManagedFormat.format(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([BCFileManagedFormat.format(v) for v in value[0]], value[1])
            elif not isinstance(value[0], BCFileManagedFormat):
                raise EInvalidRuleParameter("Given `format` must be a valid value")

            self.__format = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.STRING)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.STRING:
            self.__format = value
        else:
            raise EInvalidRuleParameter("Given `format` must be a valid value")

    def imageWidth(self):
        """Return current image width rule"""
        return self.__imageWidth

    def setImageWidth(self, value):
        """set current image width rule"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], float):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([int(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([int(v) for v in value[0]], value[1])
            elif not isinstance(value[0], int):
                raise EInvalidRuleParameter("Given `image width` must be a valid value")

            self.__imageWidth = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.INT)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.INT:
            self.__imageWidth = value
        else:
            raise EInvalidRuleParameter("Given `image width` must be a valid value")

    def imageHeight(self):
        """Return current image width rule"""
        return self.__imageHeight

    def setImageHeight(self, value):
        """set current image height rule"""
        if isinstance(value, tuple):
            if isinstance(value[0], str):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], float):
                value = (int(value[0]), value[1])
            elif isinstance(value[0], tuple):
                value = (tuple([int(v) for v in value[0]]), value[1])
            elif isinstance(value[0], list):
                value = ([int(v) for v in value[0]], value[1])
            elif not isinstance(value[0], int):
                raise EInvalidRuleParameter("Given `image height` must be a valid value")

            self.__imageHeight = BCFileListRuleOperator(value[0], value[1], BCFileListRuleOperatorType.INT)
        elif value is None or isinstance(value, BCFileListRuleOperator) and value.type() == BCFileListRuleOperatorType.INT:
            self.__imageHeight = value
        else:
            raise EInvalidRuleParameter("Given `image height` must be a valid value")

    def fileMatch(self, file):
        if isinstance(file, BCDirectory):
            # do not filter directories
            return True
        if not isinstance(file, BCFile):
            raise EInvalidRuleParameter("Given `file` type must be <BCFile>")

        if not self.__name is None:
            if not self.__name.compare(file.name()):
                return False

        if not self.__size is None:
            if not self.__size.compare(file.size()):
                return False

        if not self.__mdatetime is None:
            if not self.__mdatetime.compare(file.lastModificationDateTime(self.__mdatetime.type() == BCFileListRuleOperatorType.DATE)):
                return False

        if not self.__format is None:
            if not self.__format.compare(file.format()):
                return False

        if not self.__imageWidth is None:
            if not self.__imageWidth.compare(file.imageSize().width()):
                return False

        if not self.__imageHeight is None:
            if not self.__imageHeight.compare(file.imageSize().width()):
                return False

        return True

class BCFileListPath(object):
    """A search path definition"""

    def __init__(self, path=None, recursive=False):
        self.__path = ''
        self.__recursive = False

        self.setPath(path)
        self.setRecursive(recursive)

    def __repr__(self):
        return f"<BCFileListPath('{self.__path}', {self.__recursive})>"

    def path(self):
        """Return current search path"""
        return self.__path

    def setPath(self, value):
        """set search path"""
        if isinstance(value, str) and value != '':
            self.__path = value
        else:
            raise EInvalidRuleParameter("Given `path` must be a valid string")

    def recursive(self):
        """Return if search is recursive or not"""
        return self.__recursive

    def setRecursive(self, value):
        """set recursive search status"""
        if isinstance(value, bool):
            self.__recursive = value
        else:
            raise EInvalidRuleParameter("Given `recursive` must be a valid boolean")

class BCFileListSortRule(object):
    """Define sort rule for file"""

    def __init__(self, property, ascending=True):
        """Initialise a sort rule"""
        if isinstance(property, BCFileProperty):
            self.__property = property
        elif isinstance(property, str):
            self.__property = BCFileProperty(property)
        else:
            raise EInvalidType('Given `property` must be a valid <BCFileProperty>')

        if isinstance(ascending, bool):
            self.__ascending = ascending
        else:
            raise EInvalidType('Given `ascending` must be a valid <bool>')

    def __str__(self):
        """Return sort rule as string"""
        if self.__ascending:
            return f'{self.__property.value} ASC'
        else:
            return f'{self.__property.value} DESC'

    def __repr__(self):
        """Return rule as string"""
        return f'<BCFileListSortRule(property={self.__property.value}; ascending={self.__ascending}; hash={self.hash()})>'

    def hash(self):
        """Return a hash from rule"""
        hashNfo = hashlib.blake2b(digest_size=8)
        hashNfo.update(self.__property.value.encode())
        return hashNfo.hexdigest()

    def translate(self, short=False):
        """Return rule as a human readable string"""
        if short:
            return self.__str__()

        if self.__ascending:
            return f'{self.__property.translate()} (ascending)'
        else:
            return f'{self.__property.translate()} (descending)'

    def property(self):
        """return sorted property"""
        return self.__property

    def ascending(self):
        """return True if sort is ascending, otherwise False"""
        return self.__ascending

class BCFileList(object):
    """A file list wrapper

    Allows to manage from the simplest query (files in a directory) to the most complex (search in multiple path with
    multiple specifics criteria inclyuding add/exclude)


    The engine query:
    - can be set from methods
    - can be set from 2 differents languages
        . A SQL Like language
        . A human natural language
    """

    __MTASKS_RULES = []

    @staticmethod
    def getBcFile(fileName):
        """Return a BCFile from given fileName

        > Used for multiprocessing taks
        """
        try:
            returned = BCFile(fileName)
            return returned
        except Exception as e:
            print(e)
            return None

    @staticmethod
    def getBcDirectory(fileName):
        """Return a BCDirectory from given fileName

        > Used for multiprocessing taks
        """
        try:
            returned = BCDirectory(fileName)
            return returned
        except Exception as e:
            print(e)
            return None

    @staticmethod
    def checkBcFile(file):
        """Return file if matching query rules, otherwise return None

        > Used for multiprocessing taks
        """
        if not file is None:
            if len(BCFileList.__MTASKS_RULES) > 0:
                for rule in BCFileList.__MTASKS_RULES:
                    if rule.fileMatch(file):
                        return file
            else:
                return file
        return None

    def __init__(self, currentList=None):
        """Initialiser current list query"""
        self.__currentFiles = []
        self.__currentFilesName = set()

        self.__pathList = []
        self.__ruleList = []
        self.__sortList = []

        self.__includeDirectories = False
        self.__includeHidden = False

        self.__invalidated = True

        #if isinstance(currentList, BCFileList):
        #    self.__initList(currentList)

    def __invalidate(self):
        self.__invalidated = True

    def __sort(self, fileA, fileB):
        # if A < B : -1
        #    A > B : 1
        #    A = B : 0

        # very long: need to check all sort criteria
        for sortKey in self.__sortList:
            pA = fileA.getProperty(sortKey.property())
            pB = fileB.getProperty(sortKey.property())

            # note: directories are always before files
            if fileA.format() == BCFileManagedFormat.DIRECTORY and fileB.format() != BCFileManagedFormat.DIRECTORY:
                return -1
            elif fileB.format() == BCFileManagedFormat.DIRECTORY and fileA.format() != BCFileManagedFormat.DIRECTORY:
                return 1

            # both are directories OR both are not directories

            if pA == pB:
                # same value, need to compare on next sort key
                continue
            elif sortKey.ascending():
                if pA is None:
                    return -1
                elif pB is None:
                    return 1
                elif pA < pB:
                    return -1
                else:
                    return 1
            else:
                if pA is None:
                    return 1
                elif pB is None:
                    return -1
                elif pA > pB:
                    return -1
                else:
                    return 1

        return 0

    def clear(self):
        """Clear everything
        - paths
        - rules
        - results
        """
        self.clearPaths()
        self.clearRules()
        self.clearResults()

    def clearPaths(self):
        """Clear paths definitions"""
        self.__pathList = []
        self.__invalidate()

    def clearRules(self):
        """Clear rules definitions"""
        self.__ruleList = []
        self.__invalidate()

    def clearResults(self):
        """Clear current results"""
        self.__currentFiles = []
        self.__currentFilesName = set()
        self.__invalidate()

    def includeDirectories(self):
        """Return if query include directories or not"""
        return self.__includeDirectories

    def setIncludeDirectories(self, value):
        """Set if query should include directories or not"""
        if isinstance(value, bool):
            if self.__includeDirectories != value:
                self.__invalidate()
            self.__includeDirectories = value

    def includeHidden(self):
        """Return if query include hidden files or not"""
        return self.__includeHidden

    def setIncludeHidden(self, value):
        """Set if query should include hidden files or not"""
        if isinstance(value, bool):
            if self.__includeHidden != value:
                self.__invalidate()
            self.__includeHidden = value

    def paths(self):
        """Return current defined paths where to search files"""
        return self.__pathList

    def inPaths(self, value):
        """Return True if a path is defined in list"""
        if isinstance(value, str):
            refValue = value
        else:
            refValue = value.path()

        for path in self.__pathList:
            if path.path() == refValue:
                return True
        return False

    def addPath(self, value):
        """Add a new path in path list

        If path already exist in list, it will be ignored

        Given `path` can be:
        - A string (recurse scan is disabled)
        - A BCFileListPath
        - A list of string (recurse scan is disabled) / BCFileListPath
        """
        if isinstance(value, list):
            for path in value:
                self.addPath(path)
        elif isinstance(value, str):
            if not self.inPaths(value):
                self.__pathList.append( BCFileListPath(value) )
                self.__invalidate()
        elif isinstance(value, BCFileListPath):
            if not self.inPaths(value):
                self.__pathList.append( value )
                self.__invalidate()
        else:
            raise EInvalidType("Given path is not valid")

    def removePath(self, value):
        """Remove given path from list

        If path is not found, do nothing

        Given `path` can be:
        - A string
        - A BCFileListPath
        - A list of string / BCFileListPath
        """
        if isinstance(value, list):
            for path in value:
                self.removePath(path)
        else:
            if self.inPaths(value):
                if isinstance(value, str):
                    refValue = value
                else:
                    refValue = value.path()

                for path in self.__pathList:
                    if path.path() == refValue:
                        self.__pathList.remove(path)
                        self.__invalidate()

    def rules(self):
        """Return current defined rules used to filter files"""
        return self.__ruleList

    def inRules(self, value):
        """Return True if a rule is already defined in list"""
        if isinstance(value, BCFileListRule):
            hashValue = value.hash()

            for rule in self.__ruleList:
                if rule.hash() == hashValue:
                    return True

            return False
        else:
            raise EInvalidType("Given `value` is not a valid rule")

    def addRule(self, value):
        """Add a new filtering rule

        If rule is already defined, ignore it

        Filtering rules works in OR mode: a file is selected if at least it match one of the given rules
        """
        if isinstance(value, list):
            for rule in value:
                self.addRule(rule)
        elif isinstance(value, BCFileListRule):
            if not self.inRules(value):
                self.__ruleList.append(value)
                self.__invalidate()
        else:
            raise EInvalidType("Given rule is not valid")

    def removeRule(self, value):
        """Remove given rule from list

        If rule is not found, do nothing
        """
        if isinstance(value, list):
            for rule in value:
                self.removeRule(rule)
        else:
            if self.inRules(value):
                hashValue = value.hash()

                for rule in self.__ruleList:
                    if rule.hash() == hashValue:
                        self.__ruleList.remove(rule)
                        self.__invalidate()

    def sortRules(self):
        """Return sort rules"""
        return self.__sortlist

    def inSortRules(self, value):
        """Return True if sort is already defined in sort list"""
        if isinstance(value, BCFileListSortRule):
            hashValue = value.hash()

            for sortRule in self.__sortList:
                if sortRule.hash() == hashValue:
                    return True

            return False
        else:
            raise EInvalidType("Given `value` is not a valid sort rule")

    def addSortRule(self, value):
        """Add a new sort rule

        If sort rule is already defined, ignore it
        """
        if isinstance(value, list):
            for rule in value:
                self.addSortRule(rule)
        elif isinstance(value, BCFileListSortRule):
            if not self.inSortRules(value):
                self.__sortList.append(value)
                self.__invalidate()
        else:
            raise EInvalidType("Given sort rule is not valid")

    def removeSortRule(self, value):
        """Remove given sort rule from list

        If sort rule is not found, do nothing
        """
        if isinstance(value, list):
            for rule in value:
                self.removeSortRule(rule)
        else:
            if self.inSortRules(value):
                hashValue = value.hash()

                for sortRule in self.__ruleList:
                    if sortRule.hash() == hashValue:
                        self.__sortList.remove(sortRule)
                        self.__invalidate()

    def exportJsonQuery(self):
        """Export query into JSON format

        Return result as a string
        """
        returned = []

        return '\n'.join(returned)

    def exportSSQuery(self):
        """Export query into Simple Selection Query format

        Return result as a string
        """
        returned = []

        if len(self.__pathList) > 0:
            fromClause = []

            for path in self.__pathList:
                clause = f'DIRECTORY "{path.path()}"'
                if path.recursive():
                    clause+=' RECURSIVELY'

                fromClause.append(clause)

            returned.append('SEARCH FROM '+ textwrap.indent(',\n'.join(fromClause), '            ').strip() )
        else:
            returned.append('SEARCH')

        includes = []
        if self.__includeDirectories:
            includes.append('DIRECTORIES')
        if self.__includeHidden:
            includes.append('HIDDEN FILES')

        if len(includes) > 0:
            returned.append(f'INCLUDE {", ".join(includes)}')

        if len(self.__ruleList) > 0:
            whereClause = []

            for rule in self.__ruleList:
                whereClause.append(
                    textwrap.indent(rule.translate(True).replace(' and ', ',\n'), '              ').strip()
                )

            returned.append('MATCHING RULE '+ '\n      OR RULE '.join(whereClause) )

        if len(self.__sortList) > 0:
            returned.append('SORT BY '+ ',\n        '.join([str(v) for v in self.__sortList]) )

        return '\n'.join(returned)

    def exportHQuery(self):
        """Export query into a human natural language

        Return result as a string
        """
        returned = []

        if len(self.__pathList) > 0:
            fromClause = []

            for path in self.__pathList:
                clause = 'directory '

                if path.recursive():
                    clause+='(and sub-directories) '

                clause+=f'"{path.path()}"'

                fromClause.append(clause)

            returned.append('Search from '+ '\n        and '.join(fromClause) )
        else:
            returned.append('Search')

        includes = []
        if self.__includeDirectories:
            includes.append('directories')
        if self.__includeHidden:
            includes.append('hidden files')

        if len(includes) > 0:
            returned.append('Including {0}'.format("\n      and ".join(includes)))


        if len(self.__ruleList) > 0:
            whereClause = []

            for rule in self.__ruleList:
                whereClause.append(rule.translate())

            returned.append('For which:\n'+ '\nOr for which:\n'.join(whereClause) )

        if len(self.__sortList) > 0:
            returned.append('Sort result by:\n - '+ '\n - '.join([v.translate() for v in self.__sortList]) )



        return '\n'.join(returned)

    def exportJsonResults(self, compact=True):
        """Export image list result as a json string

        If `compact` is True, returned json string is formatted as small as possible
        Otherwise json is returned to be easy to read by human (but bigger string!)
        """
        if self.__invalidated:
            raise EInvalidQueryResult("Current query results are not up to date: query has been modified but not yet executed")

        returned = {
            'exportQuery': self.exportSSQuery(),
            'exportDate': tsToStr(time.time()),
            'exportFiles': {
                    'count': len(self.__currentFiles),
                    'files': []
                }
            }

        for file in self.__currentFiles:
            if file.format() == BCFileManagedFormat.DIRECTORY:
                returned['exportFiles']['files'].append({
                    'path': file.path(),
                    'name': file.name(),
                    'date': tsToStr(file.lastModificationDateTime()),
                    'date_ts': file.lastModificationDateTime(),
                    'format': '<dir>'
                })
            elif file.format() == BCFileManagedFormat.UNKNOWN:
                returned['exportFiles']['files'].append({
                    'path': file.path(),
                    'name': file.name(),
                    'size': file.size(),
                    'date': tsToStr(file.lastModificationDateTime()),
                    'date_ts': file.lastModificationDateTime(),
                    'format': 'unknown'
                })
            else:
                returned['exportFiles']['files'].append({
                    'path': file.path(),
                    'name': file.name(),
                    'size': file.size(),
                    'date': tsToStr(file.lastModificationDateTime()),
                    'date_ts': file.lastModificationDateTime(),
                    'format': file.format(),
                    'width': file.imageSize().width(),
                    'height': file.imageSize().height()
                })

        if compact:
            return json.dumps(returned)
        else:
            return json.dumps(returned, indent=2)

    def exportCsvResults(self, csvSeparator='\t', header=True):
        """Export image list result as a csv string

        The `csvSeparator` parameter allows to define which character is used as separator
        When `header` is True, first line define columns names, otherwise no header is defined
        """
        if self.__invalidated:
            raise EInvalidQueryResult("Current query results are not up to date: query has been modified but not yet executed")

        returned = []

        if header:
            returned.append(csvSeparator.join([
                'Path',
                'File name',
                'File size',
                'File date',
                'Image format',
                'Image Width',
                'Image Height'
            ]))

        for file in self.__currentFiles:
            if file.format() == BCFileManagedFormat.DIRECTORY:
                returned.append(csvSeparator.join([
                    file.path(),
                    file.name(),
                    '',
                    tsToStr(file.lastModificationDateTime()),
                    '<dir>',
                    '',
                    ''
                ]))
            elif file.format() == BCFileManagedFormat.UNKNOWN:
                returned.append(csvSeparator.join([
                    file.path(),
                    file.name(),
                    str(file.size()),
                    tsToStr(file.lastModificationDateTime()),
                    '',
                    '',
                    ''
                ]))
            else:
                returned.append(csvSeparator.join([
                    file.path(),
                    file.name(),
                    str(file.size()),
                    tsToStr(file.lastModificationDateTime()),
                    file.format(),
                    str(file.imageSize().width()),
                    str(file.imageSize().height())
                ]))

        return '\n'.join(returned)

    def exportTxtResults(self, header=True):
        """Export image list result as a text string"""
        if self.__invalidated:
            raise EInvalidQueryResult("Current query results are not up to date: query has been modified but not yet executed")

        returned = []

        colWidths=[4, 9]
        for file in self.__currentFiles:
            if len(file.path()) > colWidths[0]:
                colWidths[0] = len(file.path())

            if len(file.name()) > colWidths[1]:
                colWidths[1] = len(file.name())

        #                 path                       name                      file size    file date     img format   img width    img height
        rowString = f'| {{{0}:<{colWidths[0]}}} | {{{1}:<{colWidths[1]}}} | {{{2}:>9}} | {{{3}:<19}} | {{{4}:<12}} | {{{5}:>12}} | {{{6}:>12}} |'
        sepString = f'+-{{{0}:<{colWidths[0]}}}-+-{{{1}:<{colWidths[1]}}}-+-{{{2}:>9}}-+-{{{3}:<19}}-+-{{{4}:<12}}-+-{{{5}:>11}}-+-{{{6}:>11}}-+'.format('-'*colWidths[0], '-'*colWidths[1], '-'*9, '-'*19, '-'*12, '-'*12, '-'*12)

        if header:
            returned.append( 'Exported query:  ' + textwrap.indent(self.exportHQuery(), '                 ').strip())
            returned.append(f'Exported at:     {tsToStr(time.time())}')
            returned.append(f'Number of files: {len(self.__currentFiles)}')

            returned.append(sepString)
            returned.append(rowString.format(
                    'Path',
                    'File name',
                    'File size',
                    'File date',
                    'Image format',
                    'Image Width ',
                    'Image Height'
                ))

        returned.append(sepString)

        for file in self.__currentFiles:
            if file.format() == BCFileManagedFormat.DIRECTORY:
                returned.append(rowString.format(
                        file.path(),
                        file.name(),
                        '<dir>',
                        tsToStr(file.lastModificationDateTime()),
                        '',
                        '',
                        ''
                    ))
            elif file.format() == BCFileManagedFormat.UNKNOWN:
                returned.append(rowString.format(
                        file.path(),
                        file.name(),
                        bytesSizeToStr(file.size()),
                        tsToStr(file.lastModificationDateTime()),
                        '',
                        '',
                        ''
                    ))
            else:
                returned.append(rowString.format(
                        file.path(),
                        file.name(),
                        bytesSizeToStr(file.size()),
                        tsToStr(file.lastModificationDateTime()),
                        file.format(),
                        file.imageSize().width(),
                        file.imageSize().height()
                    ))

        returned.append(sepString)

        return '\n'.join(returned)

    def execute(self, clearResults=True):
        """Search for files

        Files matching criteria are added to selection.

        If `clearSelection` is False, current selection is kept, otherwise
        selection is cleared before execution

        Return number of files matching criteria
        """
        if clearResults:
            # reset current list if asked
            self.clearResults()
            Stopwatch.start('BCFileList.execute.search')

        # stopwatches are just used to measure execution time performances
        Stopwatch.start('BCFileList.execute.global')

        # to reduce execution times on filtering, test if file name is matching
        # rule is applied in directory scan
        # regular expression for matching pattern is built from all rules for
        # which file name must match a pattern
        namePattern = None
        namePatterns = []
        for rule in self.__ruleList:
            if not rule.name() is None:
                namePatterns.append(rule.name().value().pattern)

        if len(namePatterns) > 0:
            namePattern = re.compile( '|'.join(namePatterns) )

        # search for ALL files matching pattern in given path(s)
        nbTotal = 0
        # work on a set, faster for searching if a file is already in list
        foundFiles = set()
        foundDirectories = set()
        for processedPath in self.__pathList:
            pathName = processedPath.path()
            if processedPath.recursive():
                # recursive search for path, need to use os.walk()
                for path, subdirs, files in os.walk(pathName):
                    if self.__includeDirectories:
                        for dir in subdirs:
                            fullPathName = os.path.join(path, dir)

                            if self.__includeHidden or not QFileInfo(dir).isHidden():
                                nbTotal+=1

                                if not fullPathName in self.__currentFilesName and not fullPathName in foundDirectories:
                                    foundDirectories.add(fullPathName)

                    for name in files:
                        fullPathName = os.path.join(path, name)
                        if self.__includeHidden or not QFileInfo(name).isHidden():
                            nbTotal+=1

                            # check if file name match given pattern (if pattern) and is not already in file list
                            if (namePattern is None or namePattern.search(name)) and not fullPathName in self.__currentFilesName and not fullPathName in foundFiles:
                                foundFiles.add(fullPathName)
            else:
                # return current directory content
                with os.scandir(pathName) as files:
                    for file in files:
                        fullPathName = os.path.join(pathName, file.name)
                        if self.__includeHidden or QFileInfo(file.name).isHidden():
                            if file.is_file():
                                nbTotal+=1

                                # check if file name match given pattern (if pattern) and is not already in file list
                                if (namePattern is None or namePattern.search(name)) and not fullPathName in self.__currentFilesName and not fullPathName in foundFiles:
                                    foundFiles.add(fullPathName)
                            elif self.__includeDirectories and file.is_dir():
                                # if directories are asked and file is a directory, add it
                                nbTotal+=1

                                if not fullPathName in self.__currentFilesName and not fullPathName in foundDirectories:
                                    foundDirectories.add(fullPathName)

        totalMatch = len(foundFiles) + len(foundDirectories)

        Debug.print('Found {0} of {1} files in {2}s', totalMatch, nbTotal, Stopwatch.duration("BCFileList.execute.search"))

        if totalMatch == 0:
            return totalMatch

        # ----
        Stopwatch.start('BCFileList.execute.scan')
        # list file is built, now scan files to retrieve all file/image properties
        # the returned filesList is an array of BCFile if file is readbale, otherwise it contain a None value
        filesList = set()
        directoriesList = set()

        with Pool() as pool:
            # use all processors to parallelize files analysis
            filesList = pool.map(BCFileList.getBcFile, foundFiles, os.cpu_count() * 10)
            directoriesList = pool.map(BCFileList.getBcDirectory, foundDirectories, os.cpu_count() * 10)

        Debug.print('Scan {0} files in {1}s', totalMatch, Stopwatch.duration("BCFileList.execute.scan"))

        # ----
        Stopwatch.start('BCFileList.execute.filter')
        # filter files
        # will apply a filter on filesList BCFiles
        #   all files that don't match rule are replaced by None value

        # as callback called by pool can't be a method of an instancied object, we need to call static method
        # with static data
        # so pass current object rules to static class...
        if len(self.__ruleList) > 0:
            BCFileList.__MTASKS_RULES = self.__ruleList
            with Pool() as pool:
                # use all processors to parallelize files analysis
                filesList = pool.map(BCFileList.checkBcFile, filesList, os.cpu_count() * 10)
                directoriesList = pool.map(BCFileList.checkBcFile, directoriesList, os.cpu_count() * 10)

        Debug.print('Filter {0} files in {1}s', len(filesList), Stopwatch.duration("BCFileList.execute.filter"))

        # ----
        Stopwatch.start('BCFileList.execute.result')
        # build final result
        #   all files that match selection rules are added to current selected images
        nb=0
        for file in filesList:
            if not file is None:
                nb+=1
                self.__currentFiles.append(file)
                self.__currentFilesName.add(file.fullPathName())
        for file in directoriesList:
            if not file is None:
                nb+=1
                self.__currentFiles.append(file)
                self.__currentFilesName.add(file.fullPathName())

        Debug.print('Add {0} files to result in {1}s', nb, Stopwatch.duration("BCFileList.execute.result"))


        # ----
        Stopwatch.start('BCFileList.execute.sort')
        if len(self.__sortList) > 0:
            self.__currentFiles = sorted(self.__currentFiles, key=cmp_to_key(self.__sort))

        Debug.print('Sort {0} files to result in {1}s', nb, Stopwatch.duration("BCFileList.execute.sort"))


        Debug.print('Selected {0} of {1} file to result in {2}s', nb, nbTotal, Stopwatch.duration("BCFileList.execute.global"))

        self.__invalidated = False

        return len(self.__currentFiles)

    def nbFiles(self):
        """Return number of found image files"""
        return len(self.__currentFiles)

    def files(self):
        """Return found image files"""
        return self.__currentFiles

    def thumbnails(self):
        """return thumbails for files"""
        raise EInvalidStatus("Not yet implemented!")







