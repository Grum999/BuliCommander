# -----------------------------------------------------------------------------
# PyKritaToolKit
# Copyright (C) 2019-2022 - Grum999
#
# A toolkit to make pykrita plugin coding easier :-)
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
#
# Reference documentation
#   https://littlecms.com/blog/2020/12/09/using-lcms2-on-qt/
#   https://raw.githubusercontent.com/mm2/Little-CMS/master/doc/LittleCMS2.13%20tutorial.pdf
#
# -----------------------------------------------------------------------------

import sys
import os.path
import ctypes
from PyQt5.Qt import *
from PyQt5.QtGui import QImage

from ..pktk import *

# -- global variables
# library has been loaded
LCMS_LIBRARY_LOADED = False

# library location on file system
LCMS_LIBRARY_PATH = ''

# current Krita application path
__KritaPath = QDir(QApplication.applicationDirPath())
__KritaPath.cdUp()

# According to platform, location of library might not be the same
if sys.platform == 'linux':
    checkedPathsList = [
        os.path.join(__KritaPath.path(), "lib", "liblcms2.so.2"),   # appimage
        '/usr/lib/x86_64-linux-gnu/liblcms2.so.2',                  # debian multiarch
        '/usr/lib64/liblcms2.so.2',                                 # other distro
        '/usr/lib/liblcms2.so.2'                                    # other distro
    ]
elif sys.platform == 'win32':
    checkedPathsList = [
        os.path.join(__KritaPath.path(), "liblcms2.dll"),         # provided with krita
    ]
else:
    # other platform are not supported
    checkedPathsList = []


# check paths to determinate where lcms library is located
for checkedPath in checkedPathsList:
    if os.path.exists(checkedPath):
        LCMS_LIBRARY_PATH = checkedPath
        break

# library has been found, try to load
if LCMS_LIBRARY_PATH != '':
    try:
        LCMS_LIBRARY = ctypes.CDLL(LCMS_LIBRARY_PATH)
        LCMS_LIBRARY_LOADED = True
    except e as Exception:
        # unable to load library??
        qWarning(f'LCMS not loaded {str(e)}')


class LcmsType:
    """Define aliases for LCMS types"""
    STRING = ctypes.c_char_p
    INT = ctypes.c_int
    DWORD = ctypes.c_ulong
    LPVOID = ctypes.c_void_p

    CMSHANDLE = ctypes.c_void_p

    HPROFILE = ctypes.c_void_p
    HTRANSFORM = ctypes.c_void_p

    BUFFER = ctypes.c_void_p


class LcmsPixelType:
    """Pixels types

    ==> not all Lcms pixels types are defined here
    """

    # -- format types --
    # From https://github.com/mm2/Little-CMS/blob/master/include/lcms2.h
    #   PT_RGB=4
    #   PT_GRAY=3
    #
    #   COLORSPACE_SH(s)       ((s) << 16)
    #   SWAPFIRST_SH(s)        ((s) << 14)
    #   DOSWAP_SH(e)           ((e) << 10)
    #   EXTRA_SH(e)            ((e) << 7)
    #   CHANNELS_SH(c)         ((c) << 3)
    #   BYTES_SH(b)            (b)

    # define TYPE_RGB_8             (COLORSPACE_SH(PT_RGB)|CHANNELS_SH(3)|BYTES_SH(1))
    RGB_8 = 262169

    # define TYPE_RGBA_8            (COLORSPACE_SH(PT_RGB)|EXTRA_SH(1)|CHANNELS_SH(3)|BYTES_SH(1))
    RGBA_8 = 262297

    # define TYPE_RGBA_16           (COLORSPACE_SH(PT_RGB)|EXTRA_SH(1)|CHANNELS_SH(3)|BYTES_SH(2))
    RGBA_16 = 262298

    # define TYPE_BGRA_8            (COLORSPACE_SH(PT_RGB)|EXTRA_SH(1)|CHANNELS_SH(3)|BYTES_SH(1)|DOSWAP_SH(1)|SWAPFIRST_SH(1))
    BGRA_8 = 279705

    # define TYPE_BGR_8             (COLORSPACE_SH(PT_RGB)|CHANNELS_SH(3)|BYTES_SH(1)|DOSWAP_SH(1))
    BGR_8 = 263321

    # define TYPE_GRAY_8            (COLORSPACE_SH(PT_GRAY)|CHANNELS_SH(1)|BYTES_SH(1))
    GRAY_8 = 196617

    # define TYPE_GRAY_16           (COLORSPACE_SH(PT_GRAY)|CHANNELS_SH(1)|BYTES_SH(2))
    # GRAY_16 = 196618

    @staticmethod
    def qtToLcmsFormat(qtImageFmt):
        """Convert a QImage.Format pixel format to Lcms pixels format

        If format is not managed, return 0
        """
        if qtImageFmt in (QImage.Format_ARGB32, QImage.Format_RGB32):
            return LcmsPixelType.BGRA_8
        elif qtImageFmt == QImage.Format_RGB888:
            return LcmsPixelType.RGB_8
        elif qtImageFmt in (QImage.Format_RGBX8888, QImage.Format_RGBA8888):
            return LcmsPixelType.RGBA_8
        elif qtImageFmt == QImage.Format_Grayscale8:
            return LcmsPixelType.GRAY_8
        # elif qtImageFmt == QImage.Format_Grayscale16:
        #    from Qt 5.13...
        #    return LcmsPixelType.GRAY_16
        elif qtImageFmt in (QImage.Format_RGBA64, QImage.Format_RGBX64):
            return LcmsPixelType.RGBA_16
        # elif qtImageFmt == QImage.Format_BGR888:
        #    from Qt 5.14...
        #    return LcmsPixelType.BGR_8
        else:
            return 0

    @staticmethod
    def isValidValue(value):
        """Return True if given `value` is a valid managed pixel type"""
        return value in (LcmsPixelType.RGB_8,
                         LcmsPixelType.RGBA_8,
                         LcmsPixelType.RGBA_16,
                         LcmsPixelType.BGRA_8,
                         LcmsPixelType.BGR_8,
                         LcmsPixelType.GRAY_8)


class LcmsIntent:
    """Intent values

    Descriptions from Lcms documentation
        https://raw.githubusercontent.com/mm2/Little-CMS/master/doc/LittleCMS2.13%20tutorial.pdf
        Page 12
    """

    # -- intent values --

    # -- INTENT_PERCEPTUAL --
    #   Hue hopefully maintained (but not required), lightness and saturation sacrificed to maintain the perceived color.
    #   White point changed to result in neutral grays.
    #   Intended for images.
    PERCEPTUAL = 0

    # -- INTENT_RELATIVE_COLORIMETRIC --
    #   Within and outside gamut; same as Absolute Colorimetric.
    #   White point changed to result in neutral grays
    RELATIVE_COLORIMETRIC = 1

    # -- INTENT_SATURATION --
    #   Hue and saturation maintained with lightnesssacrificed to maintain saturation. White point changed to result in neutral grays.
    #   Intended for business graphics (make it colorful charts, graphs, overheads, ...)
    SATURATION = 2

    # -- INTENT_ABSOLUTE_COLORIMETRIC --
    #   Within the destination device gamut; hue, lightness and saturation are maintained.
    #   Outside the gamut; hue and lightness are maintained, saturation is sacrificed.
    #   White point for source and destination; unchanged. Intended for spot colors (Pantone, TruMatch, logo colors, ...)
    ABSOLUTE_COLORIMETRIC = 3

    @staticmethod
    def isValidValue(value):
        """Return True if given `value` is a valid intent value"""
        return value in (LcmsIntent.PERCEPTUAL,
                         LcmsIntent.RELATIVE_COLORIMETRIC,
                         LcmsIntent.SATURATION,
                         LcmsIntent.ABSOLUTE_COLORIMETRIC)


class LcmsFlags:
    """Lcms transform flags"""

    FLAGS_NOCACHE =                         0x0040  # Inhibit 1-pixel cache
    FLAGS_NOOPTIMIZE =                      0x0100  # Inhibit optimizations
    FLAGS_NULLTRANSFORM =                   0x0200  # Don't transform anyway

    # - Proofing flags
    FLAGS_GAMUTCHECK =                      0x1000  # Out of Gamut alarm
    FLAGS_SOFTPROOFING =                    0x4000  # Do softproofing

    # - Misc
    FLAGS_BLACKPOINTCOMPENSATION =          0x2000  #
    FLAGS_NOWHITEONWHITEFIXUP =             0x0004  # Don't fix scum dot
    FLAGS_HIGHRESPRECALC =                  0x0400  # Use more memory to give better accuracy
    FLAGS_LOWRESPRECALC =                   0x0800  # Use less memory to minimize resources

    # - For devicelink creation
    FLAGS_8BITS_DEVICELINK =                0x0008  # Create 8 bits devicelinks
    FLAGS_GUESSDEVICECLASS =                0x0020  # Guess device class (for transform2devicelink)
    FLAGS_KEEP_SEQUENCE =                   0x0080  # Keep profile sequence for devicelink creation

    # - Specific to a particular optimizations
    FLAGS_FORCE_CLUT =                      0x0002  # Force CLUT optimization
    FLAGS_CLUT_POST_LINEARIZATION =         0x0001  # create postlinearization tables if possible
    FLAGS_CLUT_PRE_LINEARIZATION =          0x0010  # create prelinearization tables if possible

    # - Specific to unbounded mode
    FLAGS_NONEGATIVES =                     0x8000  # Prevent negative numbers in floating point transforms

    # - Copy alpha channels when transforming
    FLAGS_COPY_ALPHA =                  0x04000000  # Alpha channels are copied on cmsDoTransform()


if LCMS_LIBRARY_LOADED:
    # declare methods from lcms library

    # --
    _liblcms_cmsCreate_sRGBProfile = LCMS_LIBRARY['cmsCreate_sRGBProfile']
    _liblcms_cmsCreate_sRGBProfile.restype = LcmsType.HPROFILE

    # --
    _liblcms_cmsOpenProfileFromFile = LCMS_LIBRARY['cmsOpenProfileFromFile']
    _liblcms_cmsOpenProfileFromFile.restype = LcmsType.HPROFILE
    _liblcms_cmsOpenProfileFromFile.argtypes = [LcmsType.STRING,                    # file name
                                                LcmsType.STRING                     # r/w mode
                                                ]

    # --
    _liblcms_cmsOpenProfileFromMem = LCMS_LIBRARY['cmsOpenProfileFromMem']
    _liblcms_cmsOpenProfileFromMem.restype = LcmsType.HPROFILE
    _liblcms_cmsOpenProfileFromMem.argtypes = [LcmsType.STRING,                     # data
                                               LcmsType.DWORD                       # length of data
                                               ]

    _liblcms_cmsCreateTransform = LCMS_LIBRARY['cmsCreateTransform']
    _liblcms_cmsCreateTransform.restype = LcmsType.HTRANSFORM
    _liblcms_cmsCreateTransform.argtypes = [LcmsType.HPROFILE,                      # input profile
                                            LcmsType.INT,                           # input data format
                                            LcmsType.HPROFILE,                      # output profile
                                            LcmsType.INT,                           # output data format
                                            LcmsType.INT,                           # intent
                                            LcmsType.DWORD                          # flags
                                            ]

    _liblcms_cmsDeleteTransform = LCMS_LIBRARY['cmsDeleteTransform']
    _liblcms_cmsDeleteTransform.argtypes = [LcmsType.HTRANSFORM]

    _liblcms_cmsCloseProfile = LCMS_LIBRARY['cmsCloseProfile']
    _liblcms_cmsCloseProfile.argtypes = [LcmsType.HPROFILE]

    _liblcms_cmsDoTransform = LCMS_LIBRARY['cmsDoTransform']
    _liblcms_cmsDoTransform.argtypes = [LcmsType.HTRANSFORM,
                                        LcmsType.BUFFER,                           # input buffer
                                        LcmsType.BUFFER,                           # output buffer
                                        LcmsType.DWORD                             # buffer size
                                        ]

    _liblcms_cmsDoTransformLineStride = LCMS_LIBRARY['cmsDoTransformLineStride']
    _liblcms_cmsDoTransformLineStride.argtypes = [LcmsType.HTRANSFORM,
                                                  LcmsType.BUFFER,                  # input buffer
                                                  LcmsType.BUFFER,                  # output buffer
                                                  LcmsType.DWORD,                   # pixels per line
                                                  LcmsType.DWORD,                   # line count
                                                  LcmsType.DWORD,                   # bytes per line (input)
                                                  LcmsType.DWORD,                   # bytes per line (output)
                                                  LcmsType.DWORD,                   # bytes per plane (input)
                                                  LcmsType.DWORD                    # bytes per plane (output)
                                                  ]

    # cmsUInt32Number cmsGetProfileInfo(HPROFILE hProfile, cmsInfoType Info, const char LanguageCode[3],  const char CountryCode[3], wchar_t* Buffer, cmsUInt32Number BufferSize)


class LcmsProfile:
    """A lcms color profile"""

    def __init__(self, profile):
        """Initialise profile

        Given `profile` can be a string and then, must be a full path/file name to an ICC file
        or it can be a bytes and in this case, must be a ICC color file blob
        """
        self.__hProfile = 0

        if not LCMS_LIBRARY_LOADED:
            # class can be initialized only if lcms library has been loaded
            return

        if isinstance(profile, str):
            # consider a full path/file name has been provided
            if profile == ':sRGB':
                self.__hProfile = _liblcms_cmsCreate_sRGBProfile()
            elif os.path.exists(profile):
                self.__hProfile = _liblcms_cmsOpenProfileFromFile(ctypes.create_string_buffer(profile.encode()), ctypes.create_string_buffer(b'r'))
        elif isinstance(profile, bytes):
            self.__hProfile = _liblcms_cmsOpenProfileFromMem(ctypes.create_string_buffer(profile, len(profile)), ctypes.c_ulong(len(profile)))

    def __del__(self):
        """Free color profile from memory"""
        if self.__hProfile > 0:
            # free color profile memory
            _liblcms_cmsCloseProfile(self.__hProfile)
            self.__hProfile = 0

    def profile(self):
        """Return pointer to lcms profile"""
        return self.__hProfile


class LcmsTransform:
    """A lcms color transform"""

    def __init__(self, profileSource, lcmsFormatSource, profileTarget, lcmsFormatTarget, intent=LcmsIntent.PERCEPTUAL, flags=0):
        """Initialise color transform

        Given `profileSource` and `profileTarget` are <LcmsProfile> or pointer to lcms profile data
        Given `lcmsFormatSource` and `lcmsFormatTarget` are <LcmsPixelType> values
        Given `intent` is <LcmsIntent> value
        Given `flags` is combination of <LcmsFlags> values
        """
        self.__colorTransform = 0

        if isinstance(profileSource, LcmsProfile):
            profileSource = profileSource.profile()
        elif not isinstance(profileSource, LcmsType.HPROFILE):
            raise EInvalidType("Given `profileSource` must be a <LcmsProfile> or <LcmsType.HPROFILE>")

        if isinstance(profileTarget, LcmsProfile):
            profileTarget = profileTarget.profile()
        elif not isinstance(profileTarget, LcmsType.HPROFILE):
            raise EInvalidType("Given `profileTarget` must be a <LcmsProfile> or <LcmsType.HPROFILE>")

        if not LcmsPixelType.isValidValue(lcmsFormatSource):
            raise EInvalidType("Given `lcmsFormatSource` must be a <LcmsPixelType> value")

        if not LcmsPixelType.isValidValue(lcmsFormatTarget):
            raise EInvalidType("Given `lcmsFormatTarget` must be a <LcmsPixelType> value")

        if not LcmsIntent.isValidValue(intent):
            raise EInvalidType("Given `intent` must be a <LcmsIntent> value")

        if not isinstance(flags, int):
            raise EInvalidType("Given `flags` must be a <LcmsFlags> value")

        self.__colorTransform = _liblcms_cmsCreateTransform(profileSource, lcmsFormatSource, profileTarget, lcmsFormatTarget, intent, flags)

    def __del__(self):
        """Free color profile from memory"""
        if self.__colorTransform != 0:
            _liblcms_cmsDeleteTransform(self.__colorTransform)

    def transform(self):
        """Return pointer to lcms color transform"""
        return self.__colorTransform


class Lcms:
    """A class to bind some LCMS function"""
    @staticmethod
    def colorManagedQImage(image, profileSource, profileTarget, intent=LcmsIntent.PERCEPTUAL, flags=0):
        """Convert given QImage `image` from icc `profileSource` to `profileTarget` using given `intent` and `flags` for conversion options

        Return a QImage
        If not possible to apply conversion, return input image

        ==> Given profiles (source, target) are not freed by function
        """
        # check parameters validity
        if not LCMS_LIBRARY_LOADED:
            # class can be initialized only if lcms library has been loaded
            return None
        elif not isinstance(image, QImage):
            raise EInvalidType("Given `image` must be a <QImage>")
        elif not LcmsIntent.isValidValue(intent):
            raise EInvalidType("Given `intent` must be a <LcmsIntent> value")
        elif not isinstance(flags, int):
            raise EInvalidType("Given `flags` must be a <LcmsFlags> value")

        if isinstance(profileSource, LcmsProfile):
            profileSource = profileSource.profile()
        elif not isinstance(profileSource, LcmsType.HPROFILE):
            raise EInvalidType("Given `profileSource` must be a <LcmsProfile> or <LcmsType.HPROFILE>")

        if isinstance(profileTarget, LcmsProfile):
            profileTarget = profileTarget.profile()
        elif not isinstance(profileTarget, LcmsType.HPROFILE):
            raise EInvalidType("Given `profileTarget` must be a <LcmsProfile> or <LcmsType.HPROFILE>")

        # determinate lcms format from given QImage
        lcmsFormat = LcmsPixelType.qtToLcmsFormat(image.format())

        if lcmsFormat == 0:
            # unknown format, not possible to convert
            return image

        # define a lcms color transform
        colorTransform = _liblcms_cmsCreateTransform(profileSource, lcmsFormat, profileTarget, lcmsFormat, intent, flags)

        if colorTransform is None:
            # can't do conversion
            return image

        # define returned image (with current image by default)
        returnedImage = QImage(image)

        # get pointer to source & target images
        ptrSourceImage = ctypes.c_void_p(image.bits().__int__())
        ptrReturnedImage = ctypes.c_void_p(returnedImage.bits().__int__())

        # generate target content from source, using lcms color transform
        _liblcms_cmsDoTransformLineStride(colorTransform, ptrSourceImage, ptrReturnedImage, image.width(), image.height(), image.bytesPerLine(), returnedImage.bytesPerLine(), 0, 0)

        # free color transform
        _liblcms_cmsDeleteTransform(colorTransform)

        return returnedImage

