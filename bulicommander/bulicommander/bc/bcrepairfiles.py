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

# TODO:
#   - Add layers with another ICC profile/Color Space



from pathlib import Path

import io
import re
import os
import os.path
import sys
import tempfile
import zipfile
import pprint
import xml.etree.ElementTree as xmlElement
import struct
import lzma

import PyQt5.uic
from PyQt5.Qt import *

from PyQt5.QtWidgets import (
        QMessageBox,
        QDialog
    )

from .bcfile import (
        BCFile,
        BCFileManagedFormat
    )
from .bcutils import (
        bytesSizeToStr,
        tsToStr,
        Debug
    )
from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )


# ------------------------------------------------------------------------------
class BCRepairFilesDialogBox(QDialog):

    def __init__(self, file, title, uicontroller, parent=None):
        super(BCRepairFilesDialogBox, self).__init__(parent)

        self.__title = title
        self.__kraFile = BCRepairKraFile(file)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcrepairfiles.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.setWindowTitle(self.__title)

        self.__initialise()
        self.__updateStatus(self.__kraFile.checkFile())


    def __initialise(self):
        """Initialise interface"""
        self.lblFileName.setText(self.__kraFile.file().fullPathName())
        self.lblFileSize.setText( f'{bytesSizeToStr(self.__kraFile.file().size())} ({self.__kraFile.file().size():n})' )
        self.lblFileDate.setText( tsToStr(self.__kraFile.file().lastModificationDateTime(), valueNone='-') )

        self.pbClose.clicked.connect(self.reject)
        self.pbTryRepair.clicked.connect(self.__repair)

    def __updateStatus(self, status, additionalText=None):
        """Display a text status according to current document status"""
        def flag(status, flag):
            return (status&flag==flag)

        text=[]
        canBeRepaired=True
        if status==BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID:
            text=["<li>Document is valid, there's nothing to repair :-)</li>"]
            canBeRepaired=False
        elif flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOT_EXISTS):
            text+=[i18n("<li>File doesn't exists and can't be repaired<br>"),
                   i18n("<i>As file doesn't exist, it can't be analyzed and repaired<i><br>"),
                   i18n("<i>Please check if file hasn't ben deleted or renamed...<i></li>")
                ]
                # TODO: linux user, check chmod/owner?
                #       windows, check ACL?
            canBeRepaired=False
        elif flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOT_READABLE):
            text+=[i18n("<li>File is not readable and can't be repaired<br>"),
                   i18n("<i>As file is not readable, content can't be analyzed and repaired<i><br>"),
                   i18n("<i>Please check if file can be accessed by user<i></li>")
                ]
                # TODO: linux user, check chmod/owner?
                #       windows, check ACL?
            canBeRepaired=False
        elif flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_EMPTY):
            text+=[i18n("<li>File is empty and can't be repaired<br>"),
                   i18n("<i>As file is complety empty (0 bytes size), it's not possible to try to repair it as there's absolutely nothing to work on<i></li>"),
                ]
            canBeRepaired=False
        elif flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOTKRA):
            text+=[i18n("<li>File is not a Krita document and can't be repaired</li>"),
                   i18n("<i>Only Krita documents can be repaired<i>"),
                   i18n("<i>If current document is a Krita document, then content might be corrupted at a state it can't be recognized as Krita document<i></li>"),
                ]
            canBeRepaired=False
        elif flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOTZIP):
            text+=[i18n("<li>File is not a Zip archive and can't be repaired</li>"),
                   i18n("<i>File structure can't be recognized as a Zip archive<i>"),
                   i18n("<i>Content might be corrupted at a state it can't be repaired<i></li>"),
                ]
            canBeRepaired=False
        elif flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_DEAD):
            text+=[i18n("<li>File content can't be read<br>"),
                   i18n("<i>Document structure can't be read<i>"),
                   i18n("<i>Content might be corrupted at a state it can't be repaired<i></li>"),
                ]
            canBeRepaired=False
        else:
            if flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_VERSION_NOT_MANAGED):
                text+=[i18n("<li>Current file version is not supported<br>"),
                       i18n("<i>Document can't berepaired<i></li>")
                    ]
                canBeRepaired=False

            if flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_BROKEN):
                text+=[i18n("<li>Some data are corrupted<br>")]
                if canBeRepaired:
                       text+=[i18n("<i>Document can be repaired and some data could be save, but it's not possible to rebuild original document<i><br>"),
                              i18n("<i>Some data are definitively lost<i>")
                            ]
                if isinstance(additionalText, str):
                    text.append(additionalText.replace('\n', '<br>'))
                elif isinstance(additionalText, list):
                    text+=additionalText
                text.append("</li>")

            if flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1):
                text+=[i18n("<li>Some non-critical data are missing<br>")]
                if canBeRepaired:
                    text+=["<i>Non critical data can be repaired<i>"]
                text.append("</li>")

            if flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2):
                text+=[i18n("<li>Some important data are missing<br>")]
                if canBeRepaired:
                   text+=[i18n("<i>Important data might be lost, but document can be repaired<i>")]
                text.append("</li>")

            if flag(status, BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3):
                text+=[i18n("<li>Some critical data are missing<br>")]
                if canBeRepaired:
                    text+=[i18n("<i>Maybe document can be repaired and some data could be saved, but it's not possible to rebuild original document<i>"),
                           i18n("<i>Some data are definitively lost<i>")
                        ]
                text.append("</li>")


        self.lblDocStatus.setText(f"<ul>{''.join(text)}</ul>")
        self.pbTryRepair.setEnabled(canBeRepaired)
        self.cbOpenRepairedFile.setEnabled(canBeRepaired)


    def __repair(self, dummy=None):
        """try to repair file"""
        pass


    @staticmethod
    def open(file, title, uicontroller):
        """Open dialog box"""
        db = BCRepairFilesDialogBox(file, title, uicontroller)

        return db.exec()


class BCDataReader:
    def __init__(self, data):
        self.__data=data
        self.__position=0

    def read(self, size):
        returned=self.__data[self.__position:self.__position+size]
        self.__position+=size
        return returned

    def readInt16(self):
        return struct.unpack('!H', self.read(2))[0]

    def readInt32(self):
        return struct.unpack('!I', self.read(4))[0]

    def seek(self, nbBytes, relative=True):
        if relative:
            self.__position+=nbBytes
        else:
            # absolute
            self.__position=nbBytes

    def tell(self):
        """Return current position"""
        return self.__position


class BCRepairKraFile:
    """A class to read, analyze and repai Kra file"""

    REPAIR_STATUS_FILE_IS_VALID =             0b0000000000000000
    REPAIR_STATUS_FILE_IS_NOT_EXISTS =        0b0000000000000001
    REPAIR_STATUS_FILE_IS_NOT_READABLE =      0b0000000000000010
    REPAIR_STATUS_FILE_IS_EMPTY =             0b0000000000000100
    REPAIR_STATUS_FILE_IS_NOTKRA =            0b0000000000001000
    REPAIR_STATUS_FILE_IS_NOTZIP =            0b0000000000010000
    REPAIR_STATUS_FILE_IS_DEAD =              0b0000000000100000
    REPAIR_STATUS_FILE_IS_BROKEN =            0b0000000001000000
    REPAIR_STATUS_FILE_IS_UNCOMPLETE1 =       0b0000000010000000 # ok, not a real problem
    REPAIR_STATUS_FILE_IS_UNCOMPLETE2 =       0b0000000100000000 # some data lost, not a real problem
    REPAIR_STATUS_FILE_IS_UNCOMPLETE3 =       0b0000001000000000 # some data lost, could be a problem
    REPAIR_STATUS_FILE_VERSION_NOT_MANAGED =  0b0000010000000000 # fileformat is not managed...

    DOC_IS_VALID =                        0b00000000
    DOC_CANT_BE_OPENED =                  0b00000001
    DOC_CANT_BE_READ =                    0b00000010
    DOC_IS_MISSING =                      0b00000100
    DOC_FORMAT_INVALID =                  0b00001000
    DOC_UNEXPECTED_CONTENT =              0b00010000
    DOC_DATA_CORRUPTED =                  0b00100000

    __COMMON_NODES_ATTRIB=['nodetype',
                           'colorlabel',
                           'locked',
                           'opacity',
                           'selected',
                           'name',
                           'visible',
                           'compositeop',
                           'filename',
                           'channelflags',
                           'intimeline',
                           'passthrough',
                           'x',
                           'y',
                           'collapsed',
                           'layerstyle']


    def __init__(self, file):
        # get a BCFile instance
        if isinstance(file, BCFile):
            self.__file = file
        else:
            self.__file = BCFile(file)

        # instance of ZipFile for Krita document
        self.__archive=None

        # list of document in Zip file
        self.__archiveDocs={}

        # list of analyszed problems
        self.__analysis=[]

        self.__status=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        self.__isAnimated=False


    def __getDocumentContent(self, documentName):
        """Read document content in archive

        If OK, return a bytearray
        Otherwise return an integer as error code
        """
        if self.__archiveDocs[documentName]['analysis']['status'] in (BCRepairKraFile.DOC_IS_MISSING, BCRepairKraFile.DOC_CANT_BE_OPENED):
            # There's no maindoc.xml (or file can't be opened) ==> can't check format & references
            # current status should already be BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3
            # return it because there's no other possible value
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3

        if self.__archiveDocs[documentName]['analysis']['status']==BCRepairKraFile.DOC_CANT_BE_READ:
            # file exists, but can't be read...
            if self.__archiveDocs[documentName]['analysis']['readable']==0:
                # nothing can be read, then consider file is definitively lost
                return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3

        # read mainxml.doc content
        zipFile=self.__archiveDocs[documentName]['zipInfo']
        try:
            zFile = self.__archive.open(documentName)
        except Exception as e:
            # should not occurs as has already been tested, but...
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3

        if self.__archiveDocs[documentName]['analysis']['status']!=BCRepairKraFile.DOC_CANT_BE_READ:
            # read all file content
            try:
                zContent = zFile.read()
            except Exception as e:
                zFile.close()
                # should not occurs as has already been tested, but...
                return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3
        else:
            # in this case, we can try to read a number of bytes..
            # need to read byte per byte; reading total number of readable byte seems not to work in all case (due to read buffering, using 4096 bytes block or something like this...??)
            zContent=bytearray(self.__archiveDocs[documentName]['analysis']['readable'])
            for position in range(self.__archiveDocs[documentName]['analysis']['readable']):
                try:
                    zContent[position] = zFile.read(1)
                except Exception as e:
                    # exit..
                    break

        zFile.close()
        return zContent


    def __readICCData(self, iccData):
        """Read an ICC byte array and return ICC profile information

        ICC specifications: http://www.color.org/specification/ICC1v43_2010-12.pdf
                            http://www.color.org/specification/ICC.2-2018.pdf
                            http://www.littlecms.com/LittleCMS2.10%20API.pdf
                            http://www.color.org/ICC_Minor_Revision_for_Web.pdf
        """
        def decode_mluc(data):
            """Decode MLUC (multiLocalizedUnicodeType) tag type

                Byte position           Field length    Content                                                     Encoded
                0 to 3                  4               ‘mluc’ (0x6D6C7563) type signature
                4 to 7                  4               Reserved, shall be set to 0
                8 to 11                 4               Number of records (n)                                       uInt32Number
                12 to 15                4               Record size: the length in bytes of every record.           0000000Ch
                                                        The value is 12.
                16 to 17                2               First record language code: in accordance with the          uInt16Number
                                                        language code specified in ISO 639-1
                18 to 19                2               First record country code: in accordance with the           uInt16Number
                                                        country code specified in ISO 3166-1
                20 to 23                4               First record string length: the length in bytes of          uInt32Number
                                                        the string
                24 to 27                4               First record string offset: the offset from the start       uInt32Number
                                                        of the tag to the start of the string, in bytes
                28 to 28+[12(n−1)]−1    12(n−1)         Additional records as needed
                (or 15+12n)

                28+[12(n−1)]            Variable        Storage area of strings of Unicode characters
                (or 16+12n) to end

                return a dict (key=lang, value=text)
            """
            returned = {}
            if data[0:4] != b'mluc':
                return returned

            nbRecords = struct.unpack('!I', data[8:12])[0]
            if nbRecords == 0:
                return returned

            szRecords = struct.unpack('!I', data[12:16])[0]
            if szRecords != 12:
                # if records size is not 12, it's not normal??
                return returned

            for index in range(nbRecords):
                offset = 16 + index * szRecords
                try:
                    langCode = data[offset:offset+2].decode()
                    countryCode = data[offset+2:offset+4].decode()

                    txtSize = struct.unpack('!I', data[offset+4:offset+8])[0]
                    txtOffset = struct.unpack('!I', data[offset+8:offset+12])[0]

                    text = data[txtOffset:txtOffset+txtSize].decode('utf-16be')

                    returned[f'{langCode}-{countryCode}'] = text.rstrip('\x00')
                except Exception as a:
                    Debug.print('[BCFile...decode_mluc] Unable to decode MLUC: {0}', e)
                    continue
            return returned

        def decode_text(data):
            """Decode TEXT (multiLocalizedUnicodeType) tag type

                Byte position           Field length    Content                                                     Encoded
                0 to 3                  4               ‘text’ (74657874h) type signature
                4 to 7                  4               Reserved, shall be set to 0
                8 to end                Variable        A string of (element size 8) 7-bit ASCII characters

                return a dict (key='en-US', value=text)
            """
            returned = {}
            if data[0:4] != b'text':
                return returned

            try:
                returned['en-US'] = data[8:].decode().rstrip('\x00')
            except Exception as a:
                Debug.print('[BCFile...decode_mluc] Unable to decode TEXT: {0}', e)

            return returned

        def decode_desc(data):
            """Decode DESC (textDescriptionType) tag type [deprecated]

                Byte position           Field length    Content                                                     Encoded
                0..3                    4               ‘desc’ (64657363h) type signature
                4..7                    4               reserved, must be set to 0
                8..11                   4               ASCII invariant description count, including terminating    uInt32Number
                                                        null (description length)
                12..n-1                                 ASCII invariant description                                 7-bit ASCII

                ignore other data

                return a dict (key='en-US', value=text)
            """
            returned = {}
            if data[0:4] != b'desc':
                return returned

            try:
                txtLen = struct.unpack('!I', data[8:12])[0]
                returned['en-US'] = data[12:11+txtLen].decode().rstrip('\x00')
            except Exception as e:
                Debug.print('[BCFile...decode_mluc] Unable to decode DESC: {0}', e)

            return returned

        returned = {
            'error': None,
            'iccProfileName': {},
            'iccProfileCopyright': {},
        }

        iccSize=struct.unpack('!I', iccData[0:4])[0]

        if len(iccData)!=iccSize:
            returned['error']="Invalid ICC size"
            return returned

        nbTags=struct.unpack('!I', iccData[128:132])[0]

        for i in range(nbTags):
            tData = iccData[132+i * 12:132+(i+1)*12]

            tagId = tData[0:4]
            offset = struct.unpack('!I', tData[4:8])[0]
            size = struct.unpack('!I', tData[8:12])[0]

            data = iccData[offset:offset+size]

            if tagId == b'desc':
                # description (color profile name)
                if data[0:4] == b'mluc':
                    returned['iccProfileName']=decode_mluc(data)
                elif data[0:4] == b'text':
                    returned['iccProfileName']=decode_text(data)
                elif data[0:4] == b'desc':
                    returned['iccProfileName']=decode_desc(data)
            elif tagId == b'cprt':
                # copyright
                if data[0:4] == b'mluc':
                    returned['iccProfileCopyright']=decode_mluc(data)
                elif data[0:4] == b'text':
                    returned['iccProfileCopyright']=decode_text(data)
                elif data[0:4] == b'desc':
                    returned['iccProfileCopyright']=decode_desc(data)
        return returned


    def __readASLData(self, aslData):
        """Read an ASL byte array and return informations

        ASL specifications: https://github.com/tonton-pixel/json-photoshop-scripting/tree/master/Documentation/Photoshop-Styles-File-Format
                            https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/#50577411_21585

        Note:
            Currently only return uuid for defined styles, allowing to check if they match layers
            Need to improve parser to ensure that data are not corrupted...?
        """
        def readStrUnicode(dataReader):
            size = dataReader.readInt32()
            return dataReader.read(size * 2).decode('UTF-16BE')[:-1]    # strip last character \x00

        def readKey(dataReader):
            size=dataReader.readInt32()
            if size==0:
                return dataReader.read(4).decode()
            else:
                return dataReader.read(size).decode()

        def readItem(dataReader, type):
            if type=='TEXT':
                return readStrUnicode(dataReader)
            elif type=='long':
                return dataReader.readInt32()

        def readDescriptor(dataReader, returned):
            descriptor=dataReader.read(4) # should be x'00 00 00 10'

            if descriptor!=b'\x00\x00\x00\x10':
                raise EInvalidValue("Not a valid descriptor")

            readStrUnicode(dataReader)
            readKey(dataReader)

            itemCount = dataReader.readInt32() # number of items in descriptor

            uuid=''
            layer=''
            for item in range(itemCount):
                key=readKey(dataReader)
                typeKey=dataReader.read(4).decode()

                if key=='Nm  ':
                    layer=readItem(dataReader, typeKey)
                elif key=='Idnt':
                    uuid=readItem(dataReader, typeKey)

            if uuid!='':
                returned['styles'][uuid]={'layer': layer}

        def checkPatterns(dataReader, returned):
            # need to check if patterns are used or not...
            version=dataReader.read(2) # should x'00 03'
            dataReader.seek(dataReader.readInt32()) # following pattern data size; skip bytes...

        def checkStyles(dataReader, returned):
            nbStyles=dataReader.readInt32()

            for number in range(nbStyles):
                dataSize=dataReader.readInt32() # data size for style??

                currentPosition=dataReader.tell()

                try:
                    readDescriptor(dataReader, returned)
                except Exception as e:
                    break

                dataReader.seek(currentPosition+dataSize, False)

        returned = {
            'error': None,
            'version': None,
            'styles': {}
        }

        # check header

        if len(aslData)<10:
            returned['error']='Invalid data size'
            return returned

        dataReader=BCDataReader(aslData)
        returned['version']=dataReader.readInt16()

        if dataReader.read(4)!=b'8BSL':
            returned['error']='Invalid header (not 8BSL)'
            return returned

        checkPatterns(dataReader, returned)
        checkStyles(dataReader, returned)

        # header checked


        return returned


    def __readKPLData(self, kplData):
        """Read an KPL byte array and return informations

        KPL is a ZIP file...
        1) Unzip file
        2) Check file list

        Should be enough to determinate if file is valid of not
        """
        returned = {
            'error': None,
            'missingFiles': [],
            'invalidFiles': []
        }

        if len(kplData)==0:
            returned['error']='No palette data'
            return returned

        try:
            kplArchive = zipfile.ZipFile(io.BytesIO(kplData), 'r')
        except Exception as e:
            returned['error']='Not a valid archive file'
            return returned

        kplFiles=[zipInfo.filename for zipInfo in kplArchive.infolist()]
        for file in ['colorset.xml', 'mimetype', 'profiles.xml']:
            if not file in kplFiles:
                returned['missingFiles'].append(file)
                returned['error']='File is missing'

        # maybe read all files to get a detailled list of corrupted files???
        invalidFile=kplArchive.testzip()
        if not invalidFile is None:
            if isinstance(returned['error'], str):
                returned['error']+=', file is corrupted'
            returned['invalidFiles'].append(invalidFile)

        kplArchive.close()

        return returned


    def __readTilesData(self, tilesData):
        """Read an Tiles byte array and return informations

        Tiles file is a binary file

        -- Header --
        'VERSION 2\n'
        'TILEWIDTH <w>\n'          # with <w> value for tile width (variable width)
        'TILEHEIGHT <h>\n'         # with <h> value for tile height (variable width)
        'PIXELSIZE <v>\n'          # with <s> value for pixel size (in bytes; variable width)
        'DATA <t>\n'               # with <t> value for number of tiles (can be 0 for empty layer; variable width)
                                   # note: only tiles with data are defined in layer?

            . Example:
                b'VERSION 2\n'
                b'TILEWIDTH 64\n'
                b'TILEHEIGHT 64\n'
                b'PIXELSIZE 4\n'
                b'DATA 31\n'
                => 31 tiles of 64x64 pixels, 4bytes per pixels

        -- for each tiles --
        - tile header
        '<x>,<y>,LZF,<length>\n'    # with <x> value for tile X position (can be negative)
                                    # with <y> value for tile Y position (can be negative)
                                    # with <length> value for (compressed) data following header
            . Example:
                b'64,64,LZF,647\n'
                => tile position 64,64 is 647bytes

        - tile data
        Data is an array of bytes, for which size is defined in header (<length> value)
        First byte can take the following value:
        0x00    Uncompressed data; in this case the next <length>-1 bytes are raw pixels values
        0x01    Compresssed data; in this case the next <length>-1 bytes are LZF compressed pixels values

        1) Unzip file
        2) Check file list


        Method return a dictionary with following informations:
        {
            'error':            if errrors have been encountered
            'tiles':            list of tiles, each tile is a dict
                                    {
                                        'x':            position X (int)
                                        'y':            position Y (int)
                                        'compressed':   tile data are compressed or not (bool)
                                        'size':         tile data size, excluding compression byte flag (int)
                                        'seek':         position in file at which start, excluding compression byte flag (int)
                                        'valid':        data are valid or not (bool)
                                        }
            'invalidTiles':             list of invalid tiles (indexes on 'tiles' list)
            'tiles.size':       QSize()
            'tiles.count':      int
            'pixel.size':       int
            'position.x.min'    minimum x position for tiles
            'position.y.min'    minimum y position for tiles
            'position.x.max'    maximum x position for tiles
            'position.y.max'    maximum y position for tiles
        }
        """

        def getHeaderValue(bLine):
            # return value from a header line
            # b'TILEWIDTH 64\n' will return 64 for example
            # return None if not able to return a value
            line=bLine.decode()
            result=re.search("\s(\d+)\n$", line)
            if result:
                return int(result.groups()[0])
            return None

        def getTileNfo(bLine):
            # return a dictionary of a tile from tile header
            # return None if not possible to return a value
            line=bLine.decode()
            result=re.search("^(-?\d+),(-?\d+),LZF,(\d+)\n$", line)
            if result:
                return {'x': int(result.groups()[0]),
                        'y': int(result.groups()[1]),
                        'size': int(result.groups()[2]) - 1,
                        'seek': 0,
                        'valid': True,
                        'compressed': True
                        }
            return None

        def lzfUncompress(dataIn, lenDataOut):
            # Uncompress given dataIn (bytearray)
            # return a bytearray() of size lenDataOut
            # if not possible to uncompress data, return None
            dataOut=bytearray(lenDataOut)
            lenDataIn=len(dataIn)

            inputPos=0
            outputPos=0

            while True:
                ctrl = dataIn[inputPos]
                inputPos+=1

                if ctrl < 32:
                    # literal run
                    # note: 32 ==> 1 << 5
                    ctrl+=1

                    if outputPos + ctrl > lenDataOut:
                        Debug.print("lzfUncompress: output buffer to small(1): {0} {1} {2}", outputPos, ctrl, lenDataOut)
                        return None

                    for loop in range(ctrl):
                        dataOut[outputPos] = dataIn[inputPos]
                        outputPos+=1
                        inputPos+=1
                else:
                    dataLen = ctrl >> 5

                    reference = outputPos - ((ctrl & 0x1f) << 8) - 1

                    if dataLen == 7:
                        dataLen+=dataIn[inputPos]
                        inputPos+=1

                    reference-=dataIn[inputPos]
                    inputPos+=1

                    if outputPos + dataLen + 2 > lenDataOut:
                        Debug.print("lzfUncompress: output buffer to small(2): {0} {1} {2", outputPos, dataLen+2, lenDataOut)
                        return None

                    if reference < 0:
                        Debug.print("lzfUncompress: invalid reference")
                        return None

                    for loop in range(dataLen+2):
                        dataOut[outputPos]=dataOut[reference]
                        outputPos+=1
                        reference+=1

                if inputPos >= lenDataIn:
                    break

            return dataOut

        returned = {
                'error': None,
                'tiles': [],
                'invalidTiles': [],
                'tiles.size': None,
                'tiles.count': 0,
                'pixel.size': None,
                'position.x.min': 9999999,
                'position.y.min': 9999999,
                'position.x.max': 0,
                'position.y.max': 0
            }

        # Use LZMA module to uncompress LZF data
        # define LZMA module configuration
        lzmaFilters = [
            {"id": lzma.FILTER_DELTA, "dist": 5},
            {"id": lzma.FILTER_LZMA2, "preset": 7},
        ]


        with io.BytesIO(tilesData) as fHandle:
            version=fHandle.readline()
            if version!=b"VERSION 2\n":
                returned['error']="Invalid file format (header); file version can't be analyzed"
                return returned

            tileWidth=getHeaderValue(fHandle.readline())
            if tileWidth is None:
                returned['error']="Invalid file format (header); tile width can't be analyzed"
                return returned
            tileHeight=getHeaderValue(fHandle.readline())
            if tileHeight is None:
                returned['error']="Invalid file for-1mat (header); tile height can't be analyzed"
                return returned
            returned['tiles.size']=QSize(tileWidth, tileHeight)

            pixelSize=getHeaderValue(fHandle.readline())
            if pixelSize is None:
                returned['error']="Invalid file format (header); pixel size can't be analyzed"
                return returned
            returned['pixel.size']=pixelSize

            tilesCount=getHeaderValue(fHandle.readline())
            if tilesCount is None:
                returned['error']="Invalid file format (header); number of tiles can't be analyzed"
                return returned
            returned['tiles.count']=tilesCount

            tileSize=tileWidth*tileHeight*pixelSize

            Debug.print(f'                         . Tile definition: {tileWidth}x{tileHeight}, pixel size: {pixelSize}, tiles count: {tilesCount}')

            tileKo=0
            tileNumber=0
            while True:
                #Debug.print(f'                         . Check tile: {tileNumber}')
                line=fHandle.readline()

                if not line:
                    # EOF
                    break

                tileNfo=getTileNfo(line)
                if tileNfo is None:
                    returned['error']=f"Invalid file format (data); unable to parse tile header (tile #{tileNumber}; position: {fHandle.tell()})"
                    return returned

                isCompressed=fHandle.read(1)

                tileNfo['compressed']=(isCompressed==0x01)
                tileNfo['seek']=fHandle.tell()

                lzfBuffer=fHandle.read(tileNfo["size"])
                if isCompressed==0x01:
                    try:
                        data=lzma.decompress(lzfBuffer, lzma.FORMAT_RAW, filters=lzmaFilters)
                        dataBlockOk=True
                    except Exception as e:
                        Debug.print(f'  /!\ Invalid tile')
                        returned['invalidTiles'].append(tileNumber)
                        tileNfo['valid']=False
                else:
                    # can't do test on raw data...
                    pass

                returned['tiles'].append(tileNfo)

                returned['position.x.min']=min(returned['position.x.min'], tileNfo['x'])
                returned['position.y.min']=min(returned['position.y.min'], tileNfo['y'])
                returned['position.x.max']=max(returned['position.x.max'], tileNfo['x'])
                returned['position.y.max']=max(returned['position.y.max'], tileNfo['y'])

                tileNumber+=1

        if len(returned['tiles'])!=returned['tiles.count']:
            # a bloking error
            returned['error']="Tiles number doesn't match to header"
        elif returned['tiles.count']>0 and len(returned['invalidTiles'])==returned['tiles.count']:
            # a bloking error
            # otherwise, con't consider error is blocking (let error to None)
            # in this case the analysis is made in a second time from invalidTiles len
            returned['error']='All tiles are invalid'

        return returned


    def __readSVGData(self, svgData):
        """Read an SVG byte array and return informations

        SVG is a XML file...
        Parsing file should be enough to determinate if file is valid or not..
        """
        returned = {
            'error': None
        }

        if len(svgData)==0:
            returned['error']='No SVG data'
            return returned

        # now, we have file content...
        strSvgData=svgData.decode('UTF-8')

        try:
            xmlDoc = xmlElement.fromstring(strSvgData)
        except Exception as e:
            Debug.print("                         (!) XML content can't be parsed: {0}", e)
            returned['error']=f"Can't parse SVG content ({(str(e))})"

        return returned


    def __readParamsData(self, paramsData):
        """Read an Params byte array and return informations

        Params is a XML file...
        Parsing file should be enough to determinate if file is valid or not..
        """
        returned = {
            'error': None
        }

        if len(paramsData)==0:
            returned['error']='No Params data'
            return returned

        # now, we have file content...
        strParamsData=paramsData.decode('UTF-8')

        try:
            xmlDoc = xmlElement.fromstring(strParamsData)
        except Exception as e:
            Debug.print("                         (!) XML content can't be parsed: {0}", e)
            returned['error']=f"Can't parse Params content ({(str(e))})"

        return returned


    def __readTransformParamsData(self, tparamsData):
        """Read an TransformParams byte array and return informations

        Params is a XML file...
        Parsing file should be enough to determinate if file is valid or not..
        """
        returned = {
            'error': None
        }

        if len(tparamsData)==0:
            returned['error']='No TransformParams data'
            return returned

        # now, we have file content...
        strTParamsData=tparamsData.decode('UTF-8')

        try:
            xmlDoc = xmlElement.fromstring(strTParamsData)
        except Exception as e:
            Debug.print("                         (!) XML content can't be parsed: {0}", e)
            returned['error']=f"Can't parse TransformParams content ({(str(e))})"

        return returned


    def __checkFileStep01(self):
        """Initialise list of documents

        Return BCRepairKraFile.REPAIR_STATUS_FILE_IS_DEAD if can't read document list, otherwise return BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID
        """
        Debug.print("(i) [__checkFileStep01] Initialise documents list")
        try:
            self.__archiveDocs={fileInfo.filename: {
                                            'maindoc.nodeId': None,
                                            'zipInfo':  fileInfo,
                                            'analysis': {
                                                    'status':       BCRepairKraFile.DOC_IS_VALID,
                                                    'statusMsg':    [],
                                                    'readable':     fileInfo.file_size
                                                }
                                        } for fileInfo in self.__archive.infolist()
                                }
        except Exception as e:
            # can't list files??
            Debug.print("(!) [__checkFileStep01] Error: {0}", e)
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_DEAD

        return BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID


    def __checkFileStep02(self):
        """Try to read files content

        Return BCRepairKraFile.REPAIR_STATUS_FILE_IS_BROKEN if there's
        some files for which CRC is KO
        """
        Debug.print("(i) [__checkFileStep02] Try to read files content")
        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        for fileName in self.__archiveDocs:
            Debug.print("                        Get document: {0}", fileName)

            zipFile=self.__archiveDocs[fileName]['zipInfo']
            try:
                zFile = self.__archive.open(fileName)
            except Exception as e:
                Debug.print("                                      (!) Can't be opened: {0}", e)
                self.__archiveDocs[fileName]['analysis']['status']|=BCRepairKraFile.DOC_CANT_BE_OPENED
                self.__archiveDocs[fileName]['analysis']['statusMsg'].append(str(e))
                self.__archiveDocs[fileName]['analysis']['readable']=0
                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_BROKEN
                continue

            cantRead=False
            try:
                zContent = zFile.read()
            except Exception as e:
                Debug.print("                                      (!) Can't be read: {0}", e)
                self.__archiveDocs[fileName]['analysis']['status']|=BCRepairKraFile.DOC_CANT_BE_READ
                self.__archiveDocs[fileName]['analysis']['statusMsg'].append(str(e))
                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_BROKEN
                cantRead=True

            if cantRead:
                # try to determinate how many bytes can be read in corrupted document
                bytesRead=0
                # reset position to file start
                zFile.seek(0)
                for position in range(zipFile.file_size):
                    try:
                        # read byte per byte....
                        data = zFile.read(1)
                    except Exception as e:
                        Debug.print("                                      (!) Can't be read; max read size: {0}", position)
                        self.__archiveDocs[fileName]['analysis']['readable']=position
                        break

            zFile.close()

        return returned


    def __checkFileStep03(self):
        """Check for missing files
        Only default files are tested here:
        . maindoc.xml
        . documentinfo.xml
        . mimetype
        . preview.png
        . mergedimage.png

        """
        documents={
            'maindoc.xml': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3,
            'documentinfo.xml': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2,
            'mimetype': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1,
            'preview.png': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1,
            'mergedimage.png': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
        }

        Debug.print("(i) [__checkFileStep03] Check for missing files")
        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        for document in documents:
            Debug.print("                        Check document: {0}", document)
            if not document in self.__archiveDocs:
                Debug.print("                                        (!) Document is missing")
                returned|=documents[document]
                self.__archiveDocs[document]={
                                        'maindoc.nodeId': None,
                                        'zipInfo':  None,
                                        'analysis': {
                                                'status':       BCRepairKraFile.DOC_IS_MISSING,
                                                'statusMsg':    [f'File {document} is missing'],
                                                'readable':     0
                                            }
                                    }

        return returned


    def __checkFileStep04a(self):
        """Check maindoc.xml"""
        def loadAttribs(node, key, attribs):
            self.__archiveDocs['maindoc.xml'][key]={}
            for attrib in attribs:
                if attrib in node.attrib:
                    value=node.attrib[attrib]
                else:
                    Debug.print("                         /!\ Node attribute not found: {0}[{1}]", key, attrib)
                    value=None

                self.__archiveDocs['maindoc.xml'][key][attrib]=value

        def loadNodes(nodes, key):
            for node in nodes:
                nodeType=None

                if 'nodetype' in node.attrib:
                    nodeType=node.attrib['nodetype']

                if nodeType:
                    # process only if layer has a node type

                    uuid=None
                    if 'uuid' in node.attrib:
                        uuid=node.attrib['uuid']
                    else:
                        # no uuid? create one
                        uuid=QUuid.createUuid().toString(QUuid.WithBraces)


                    if nodeType=='referenceimages':
                        loadNodesReferenceImages(node, f'{key}.referenceimages')
                    elif nodeType=='grouplayer':
                        loadNodesGroupLayer(node, f'{key}.grouplayer[{uuid}]', uuid)
                    elif nodeType=='shapelayer':
                        # vectorlayer
                        loadNodesShapeLayer(node, f'{key}.shapelayer[{uuid}]', uuid)
                    elif nodeType=='paintlayer':
                        loadNodesPaintLayer(node, f'{key}.paintlayer[{uuid}]', uuid)
                    elif nodeType=='generatorlayer':
                        # filllayer
                        loadNodesGeneratorLayer(node, f'{key}.generatorlayer[{uuid}]', uuid)
                    elif nodeType=='filelayer':
                        loadNodesFileLayer(node, f'{key}.filelayer[{uuid}]', uuid)
                    elif nodeType=='adjustmentlayer':
                        # filterlayer
                        loadNodesAdjustmentLayer(node, f'{key}.adjustmentlayer[{uuid}]', uuid)
                    elif nodeType=='clonelayer':
                        loadNodesCloneLayer(node, f'{key}.clonelayer[{uuid}]', uuid)
                    elif nodeType=='transformmask':
                        loadNodesTransformMask(node, f'{key}.transformmask[{uuid}]', uuid)
                    elif nodeType=='filtermask':
                        loadNodesFilterMask(node, f'{key}.filtermask[{uuid}]', uuid)
                    elif nodeType=='transparencymask':
                        loadNodesTransparencyMask(node, f'{key}.transparencymask[{uuid}]', uuid)
                    elif nodeType=='selectionmask':
                        loadNodesSelectionMask(node, f'{key}.selectionmask[{uuid}]', uuid)

        def loadSubNodes(node, key):
            nodes=node.findall("./{*}layers/{*}layer")
            if len(nodes)>0:
                loadNodes(nodes, key)
            nodes=node.findall("./{*}masks/{*}mask")
            if len(nodes)>0:
                loadNodes(nodes, key)

        def loadNodesReferenceImages(node, key):
            loadAttribs(node, key, ['nodetype'])
            nodes=node.findall("./{*}referenceimage")
            if len(nodes)>0:
                for index, refImgNode in enumerate(nodes):
                    loadAttribs(refImgNode, f'{key}[{index}]', ['transform', 'opacity', 'saturation', 'src', 'height', 'keepAspectRatio', 'width'])
                    self.__archiveDocs['maindoc.xml'][f'{key}[{index}]']['nodetype']='referenceimage'
            self.__archiveDocs['maindoc.xml'][key]['images']=len(nodes)

        def loadNodesGroupLayer(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB)
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesShapeLayer(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB)
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesPaintLayer(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB+['onionskin', 'colorspacename', 'channellockflags', 'keyframes'])
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesGeneratorLayer(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB+['generatorname', 'generatorversion', 'channellockflags', 'keyframes'])
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesFileLayer(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB+['scale', 'source', 'scalingmethod'])
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesCloneLayer(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB+['clonefromuuid', 'clonefrom'])
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesAdjustmentLayer(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB+['filterversion', 'filtername'])
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesTransparencyMask(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB)
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesSelectionMask(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB)
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesFilterMask(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB+['filterversion', 'filtername'])
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadNodesTransformMask(node, key, uuid):
            loadAttribs(node, key, BCRepairKraFile.__COMMON_NODES_ATTRIB)
            loadSubNodes(node, key)
            self.__archiveDocs['maindoc.xml'][key]['uuid']=uuid

        def loadAssistants(nodes, key):
            for index, node in enumerate(nodes):
                loadAttribs(node, f'{key}.assistant[{index}]', ['type', 'filename'])

        def loadPalettes(nodes, key):
            for index, node in enumerate(nodes):
                loadAttribs(node, f'{key}.palette[{index}]', ['filename'])

        def loadAnimation(node, key):
            subNode=node.find("./{*}framerate")
            if subNode is None:
                Debug.print("                         /!\ Missing node: {0}.framerate", key)
                self.__archiveDocs['maindoc.xml'][f'{key}.framerate']={
                                                                        'type': None,
                                                                        'value': None,
                                                                    }
            else:
                loadAttribs(subNode, f'{key}.framerate', ['type', 'value'])

            subNode=node.find("./{*}range")
            if subNode is None:
                Debug.print("                         /!\ Missing node: {0}.range", key)
                self.__archiveDocs['maindoc.xml'][f'{key}.framerate']={
                                                                        'to': None,
                                                                        'from': None,
                                                                        'type': None
                                                                    }
            else:
                loadAttribs(subNode, f'{key}.framerate', ['to', 'from', 'type'])

            subNode=node.find("./{*}currentTime")
            if subNode is None:
                Debug.print("                         /!\ Missing node: {0}.currentTime", key)
                self.__archiveDocs['maindoc.xml'][f'{key}.currentTime']={
                                                                        'type': None,
                                                                        'value': None,
                                                                    }
            else:
                loadAttribs(subNode, f'{key}.currentTime', ['type', 'value'])

        Debug.print("(i) [__checkFileStep04a] Check maindoc.xml (content)")
        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        Debug.print("                         Get document: maindoc.xml")
        docContent=self.__getDocumentContent("maindoc.xml")

        if isinstance(docContent, int):
            # can't read document content
            Debug.print("                         (!) Can't get content: {0}", docContent)
            return docContent

        # now, we have file content...
        strDocContent=docContent.decode('UTF-8')

        xmlParsable=True
        try:
            xmlDoc = xmlElement.fromstring(strDocContent)
        except Exception as e:
            xmlParsable=False
            Debug.print("                         (!) XML content can't be parsed: {0}", e)
            self.__archiveDocs['maindoc.xml']['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
            self.__archiveDocs['maindoc.xml']['analysis']['statusMsg'].append(i18n(f'Not a parsable XML content ({str(e)})'))

        if not xmlParsable:
            # TODO: need to think what to do here if XML is not parsable...
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3

        # start to check dependencies documents
        # shapes Layers
        # palettes
        # paint layer/keyframes
        # references image
        # guides
        # ...
        node=xmlDoc.find(".[@syntaxVersion='2']")
        if node is None:
            Debug.print("                         (!) Can't find document version")
            return BCRepairKraFile.REPAIR_STATUS_FILE_VERSION_NOT_MANAGED
        loadAttribs(node, 'xml.doc', ['syntaxVersion', 'editor', 'kritaVersion'])

        node=xmlDoc.find("./{*}IMAGE")
        if node is None:
            # no IMAGE node??
            # not a valid file...
            Debug.print("                         (!) Can't find IMAGE node")
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3
        loadAttribs(node, 'xml.doc.image', ['name', 'profile', 'width', 'height', 'colorspacename', 'mime'])

        # load layers tree...
        nodes=xmlDoc.findall(".//{*}IMAGE/{*}layers/{*}layer")
        if len(nodes)>0:
            loadNodes(nodes, 'xml.doc.image.layers')

        # load global assistant color
        node=xmlDoc.find(".//{*}IMAGE/{*}ProjectionBackgroundColor")
        if node is None:
            Debug.print("                         /!\ Missing node: IMAGE.ProjectionBackgroundColor")
            self.__archiveDocs['maindoc.xml']['xml.image.ProjectionBackgroundColor']['ColorData']=None
            returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
        else:
            loadAttribs(node, 'xml.image.ProjectionBackgroundColor', ['ColorData'])

        # load global assistant color
        node=xmlDoc.find(".//{*}IMAGE/{*}GlobalAssistantsColor")
        if node is None:
            Debug.print("                         /!\ Missing node: IMAGE.GlobalAssistantsColor")
            self.__archiveDocs['maindoc.xml']['xml.image.GlobalAssistantsColor']['SimpleColorData']=None
            returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
        else:
            loadAttribs(node, 'xml.image.GlobalAssistantsColor', ['SimpleColorData'])

        # load assistants
        nodes=xmlDoc.findall(".//{*}IMAGE/{*}assistants/{*}assistant")
        if len(nodes)>0:
            loadAssistants(nodes, 'xml.doc.image.assistants')

        # load palettes
        nodes=xmlDoc.findall(".//{*}IMAGE/{*}Palettes/{*}palette")
        if len(nodes)>0:
            loadPalettes(nodes, 'xml.doc.image.Palettes')

        # load animation
        node=xmlDoc.find(".//{*}IMAGE/{*}animation")
        if node is None:
            Debug.print("                         /!\ Missing node: IMAGE.animation")
            self.__archiveDocs['maindoc.xml']['xml.image.animation.framerate']={
                                                                                'type': None,
                                                                                'value': None,
                                                                            }
            self.__archiveDocs['maindoc.xml']['xml.image.animation.range']={
                                                                            'to': None,
                                                                            'from': None,
                                                                            'type': None
                                                                        }
            self.__archiveDocs['maindoc.xml']['xml.image.animation.currentTime']={
                                                                            'type': None,
                                                                            'value': None
                                                                        }

            if self.__isAnimated:
                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2
            else:
                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
        else:
            loadAnimation(node, 'xml.doc.image.animation')

        return returned


    def __checkFileStep04b(self):
        """Check if references files from maindoc.xml exists
        (do not check if files are valid or not)

        icc profile:            {name}/annotations/icc
        layer styles:           {name}/annotations/layerstyles.asl
        assistants:             {name}/assistants/{assistant.filename}
        palettes:               {name}/palettes/{palette.filename}
        referenceimage:         {referenceimage.src}
        layers:
            paintlayer:         {name}/layers/{layer.filename}
                                {name}/layers/{layer.filename}.icc
                                {name}/layers/{layer.filename}.defaultpixel
                                # if layer have keyframes
                                {name}/layers/{layer.filename}.keyframes.xml
                                {name}/layers/{layer.filename}.f{N}
                                {name}/layers/{layer.filename}.f{N}.defaultpixel
            shapelayer:         {name}/layers/{layer.filename}.shapelayer/content.svg
            filelayer:          <no files>
            grouplayer:         <no files>
            clonelayer:         <no files>
            generatorlayer:     {name}/layers/{layer.filename}.filterconfig
                                {name}/layers/{layer.filename}.pixelselection
                                {name}/layers/{layer.filename}.pixelselection.defaultpixel
            adjustmentlayer:    {name}/layers/{layer.filename}.filterconfig
                                {name}/layers/{layer.filename}.pixelselection
                                {name}/layers/{layer.filename}.pixelselection.defaultpixel
            filtermask:         {name}/layers/{layer.filename}.pixelselection
                                {name}/layers/{layer.filename}.pixelselection.defaultpixel
                                {name}/layers/{layer.filename}.filterconfig
            selectionmask:      {name}/layers/{layer.filename}.pixelselection
                                {name}/layers/{layer.filename}.pixelselection.defaultpixel
            transparencymask:   {name}/layers/{layer.filename}.pixelselection
                                {name}/layers/{layer.filename}.pixelselection.defaultpixel
            transformmask:      {name}/layers/{layer.filename}.transformconfig
        """
        def addMissingFile(fileName, nodeId=None):
            Debug.print("                         /!\ Add missing file: {0}", fileName)
            Debug.print("                                               {0}", nodeId)
            self.__archiveDocs[fileName]={
                                'maindoc.nodeId':   nodeId,
                                'zipInfo':  None,
                                'analysis': {
                                        'status':       BCRepairKraFile.DOC_IS_MISSING,
                                        'statusMsg':    [],
                                        'readable':     0
                                    }
                            }

        def checkICC(name):
            fName=f'{name}/annotations/icc'
            Debug.print("                         -- Checking ICC --")
            Debug.print("                         Check document: {0}", fName)
            if not fName in self.__archiveDocs:
                # add file
                addMissingFile(fName)
                return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        def checkLayerStyles(name):
            fName=f'{name}/annotations/layerstyles.asl'
            Debug.print("                         -- Checking Layer styles --")
            Debug.print("                         Check document: {0}", fName)
            # need to check if there's some layers for which a style is applied
            found=False
            nodeIdList=[]
            for item in self.__archiveDocs['maindoc.xml']:
                if isinstance(self.__archiveDocs['maindoc.xml'][item], dict) and 'layerstyle' in self.__archiveDocs['maindoc.xml'][item] and not self.__archiveDocs['maindoc.xml'][item]['layerstyle'] is None:
                    found=True
                    nodeIdList.append(item)

            Debug.print(f"                         Layers with style document: {len(nodeIdList)}", '\n                                                   '.join(nodeIdList))

            if found:
                if not fName in self.__archiveDocs:
                    # there's at least on layer style applied, but no layerfile
                    addMissingFile(fName)
                    return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2
                else:
                    self.__archiveDocs[fName]['maindoc.nodeId']=nodeIdList

            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        def checkAssistants(name):
            Debug.print("                         -- Checking Assistants --")
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID
            fName=f'{name}/assistants/'

            for item in self.__archiveDocs['maindoc.xml']:
                if re.match('xml\.doc\.image\.assistants\.assistant\[\d+\]', item):
                    # item is an assistant
                    if not self.__archiveDocs['maindoc.xml'][item]['filename'] is None:
                        afName=f"{fName}{self.__archiveDocs['maindoc.xml'][item]['filename']}"
                        Debug.print("                         Check document: {0}", afName)
                        if not afName in self.__archiveDocs:
                            # assistant file not found
                            addMissingFile(afName)
                            returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
                        else:
                            self.__archiveDocs[afName]['maindoc.nodeId']=item

            return returned

        def checkPalettes(name):
            Debug.print("                         -- Checking Palettes --")
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID
            fName=f'{name}/palettes/'

            for item in self.__archiveDocs['maindoc.xml']:
                if re.match('xml\.doc\.image\.Palettes\.palette\[\d+\]', item):
                    # item is a palette
                    if not self.__archiveDocs['maindoc.xml'][item]['filename'] is None:
                        pfName=f"{fName}{self.__archiveDocs['maindoc.xml'][item]['filename']}"
                        Debug.print("                         Check document: {0}", pfName)
                        if not pfName is None:
                            if not pfName in self.__archiveDocs:
                                # assistant file not found
                                addMissingFile(pfName)
                                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
                            else:
                                self.__archiveDocs[pfName]['maindoc.nodeId']=item

            return returned

        def checkReferenceImages():
            Debug.print("                         -- Checking Reference images --")
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

            for item in self.__archiveDocs['maindoc.xml']:
                if isinstance(self.__archiveDocs['maindoc.xml'][item], dict) and 'nodetype' in self.__archiveDocs['maindoc.xml'][item] and self.__archiveDocs['maindoc.xml'][item]['nodetype']=='referenceimage':
                    # item is a reference image
                    if not self.__archiveDocs['maindoc.xml'][item]['src'] is None:
                        fName=self.__archiveDocs['maindoc.xml'][item]['src']
                        Debug.print("                         Check document: {0}", fName)
                        if fName and not re.match('file:///', fName):
                            if not fName in self.__archiveDocs:
                                # assistant file not found
                                addMissingFile(fName)
                                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
                            else:
                                self.__archiveDocs[fName]['maindoc.nodeId']=item


            return returned

        def checkLayers(name):
            def getKeyframeFiles(file):
                docContent=self.__getDocumentContent(file)

                if isinstance(docContent, int):
                    # can't read document content
                    Debug.print("                         /!\ Unable to read document")
                    return docContent

                # now, we have file content...
                strDocContent=docContent.decode('UTF-8')

                xmlParsable=True
                try:
                    xmlDoc = xmlElement.fromstring(strDocContent)
                except Exception as e:
                    xmlParsable=False
                    Debug.print("                         /!\ XML content can't be parsed: {0}", e)
                    self.__archiveDocs[file]['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
                    self.__archiveDocs[file]['analysis']['statusMsg'].append(i18n(f'Not a parsable XML content ({str(e)})'))

                if not xmlParsable:
                    # TODO: need to think what to do here if XML is not parsable...
                    return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3

                nodes=xmlDoc.findall(".//{*}keyframe[@frame]")
                if len(nodes)>0:
                    returned=[keyframe.attrib['frame'] for keyframe in nodes]

                return returned

            Debug.print("                         -- Checking Layers --")
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

            checks={
                'paintlayer':       {f'{name}/layers/{{filename}}': ('tiles', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3),
                                     f'{name}/layers/{{filename}}.icc': ('icc', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2),
                                     f'{name}/layers/{{filename}}.defaultpixel': ('pixel', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1)},
                'paintlayer.kf':    {f'{name}/layers/{{filename}}': ('tiles', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3),
                                     f'{name}/layers/{{filename}}.defaultpixel': ('pixel', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1)},
                'shapelayer':       {f'{name}/layers/{{filename}}.shapelayer/content.svg': ('xml/svg', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3)},
                'generatorlayer':   {f'{name}/layers/{{filename}}.filterconfig': ('xml/params', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2),
                                     f'{name}/layers/{{filename}}.pixelselection': ('tiles', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3),
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': ('pixel', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1)},
                'adjustmentlayer':  {f'{name}/layers/{{filename}}.filterconfig': ('xml/params', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2),
                                     f'{name}/layers/{{filename}}.pixelselection': ('tiles', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3),
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': ('pixel', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1)},
                'filtermask':       {f'{name}/layers/{{filename}}.pixelselection': ('tiles', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3),
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': ('pixel', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1),
                                     f'{name}/layers/{{filename}}.filterconfig': ('xml/params', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2)},
                'selectionmask':    {f'{name}/layers/{{filename}}.pixelselection': ('tiles', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3),
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': ('pixel', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1)},
                'transparencymask': {f'{name}/layers/{{filename}}.pixelselection': ('tiles', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3),
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': ('pixel', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1)},
                'transformmask':    {f'{name}/layers/{{filename}}.transformconfig': ('xml/transform_params', BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3)}
            }

            for item in self.__archiveDocs['maindoc.xml']:
                if isinstance(self.__archiveDocs['maindoc.xml'][item], dict) and 'nodetype' in self.__archiveDocs['maindoc.xml'][item]:

                    nodeType=self.__archiveDocs['maindoc.xml'][item]['nodetype']

                    if nodeType in checks:
                        fileName=self.__archiveDocs['maindoc.xml'][item]['filename']

                        # process layers
                        for check in checks[nodeType]:
                            fName=check.replace('{filename}', fileName)
                            Debug.print("                         Check document[{0}]: {1}", checks[nodeType][check][0], fName)

                            if not fName in self.__archiveDocs:
                                # assistant file not found
                                addMissingFile(fName, item)
                                returned|=checks[nodeType][check][1]
                            else:
                                self.__archiveDocs[fName]['maindoc.nodeId']=item
                            self.__archiveDocs[fName]['fileType']=checks[nodeType][check][0]
                            self.__archiveDocs[fName]['fileErrLvl']=checks[nodeType][check][1]

                        # paint layers: process keyframes
                        if nodeType=='paintlayer' and not self.__archiveDocs['maindoc.xml'][item]['keyframes'] is None:
                            fName=f"{name}/layers/{self.__archiveDocs['maindoc.xml'][item]['keyframes']}"
                            Debug.print("                         Check document: {0}", fName)
                            if fName and not fName in self.__archiveDocs:
                                # assistant file not found
                                addMissingFile(pfName, item)
                                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3
                            else:
                                # xml file found, need to read it to determinate how much keyframes files are expected
                                frames=getKeyframeFiles(fName)
                                if isinstance(frames, int):
                                    returned|=frames
                                else:
                                    for frame in frames:
                                        for kfCheck in checks['paintlayer.kf']:
                                            kfName=kfCheck.replace('{filename}', frame)
                                            Debug.print("                         Check document[{0}]: {1}", checks['paintlayer.kf'][kfCheck][0], kfName)
                                            if not kfName in self.__archiveDocs:
                                                # assistant file not found
                                                addMissingFile(kfName, item)
                                                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3
                                            else:
                                                self.__archiveDocs[kfName]['maindoc.nodeId']=item
                                            self.__archiveDocs[kfName]['fileType']=checks['paintlayer.kf'][kfCheck][0]
                                            self.__archiveDocs[kfName]['fileErrLvl']=checks['paintlayer.kf'][kfCheck][1]

            return returned

        Debug.print("(i) [__checkFileStep04b] Check maindoc.xml (referenced files)")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID
        name=self.__archiveDocs['maindoc.xml']['xml.doc.image']['name']

        returned|=checkICC(name)
        returned|=checkLayerStyles(name)
        returned|=checkAssistants(name)
        returned|=checkPalettes(name)
        returned|=checkReferenceImages()
        returned|=checkLayers(name)

        return returned


    def __checkFileStep05a(self):
        """Check documentinfo.xml"""
        Debug.print("(i) [__checkFileStep05a] Check documentinfo.xml")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        Debug.print("                         Get document: documentinfo.xml")
        docContent=self.__getDocumentContent("documentinfo.xml")

        if isinstance(docContent, int):
            # can't read document content
            Debug.print("                         /!\ Can't get content: {0}", docContent)
            return docContent

        # now, we have file content...
        strDocContent=docContent.decode('UTF-8')

        xmlParsable=True
        try:
            xmlDoc = xmlElement.fromstring(strDocContent)
        except Exception as e:
            Debug.print("                         /!\ XML content can't be parsed: {0}", e)
            xmlParsable=False
            self.__archiveDocs['documentinfo.xml']['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
            self.__archiveDocs['documentinfo.xml']['analysis']['statusMsg'].append(i18n(f'Not a parsable XML content ({str(e)})'))
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2

        return returned


    def __checkFileStep06a(self):
        """Check mimetype"""
        Debug.print("(i) [__checkFileStep06a] Check mimetype")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        Debug.print("                         Get document: mimetype")
        docContent=self.__getDocumentContent("mimetype")

        if isinstance(docContent, int):
            # can't read document content
            Debug.print("                         /!\ Can't get content: {0}", docContent)
            return docContent

        # now, we have file content...
        strDocContent=docContent.decode('UTF-8')

        if strDocContent!='application/x-krita':
            Debug.print("                         /!\ Invalid content: {0}", strDocContent)
            self.__archiveDocs['mimetype']['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
            self.__archiveDocs['mimetype']['analysis']['statusMsg'].append(i18n(f'Not expected mime type'))
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1

        return returned


    def __checkFileStep07a(self):
        """Check mergedimage.png"""
        Debug.print("(i) [__checkFileStep07a] Check mergedimage.png")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        Debug.print("                         Get document: mergedimage.png")
        docContent=self.__getDocumentContent("mergedimage.png")

        if isinstance(docContent, int):
            # can't read document content
            Debug.print("                         /!\ Can't get content: {0}", docContent)
            return docContent

        try:
            image=QImage()
            image.loadFromData(docContent)
        except:
            Debug.print("                         /!\ Invalid PNG file: {0}", e)
            self.__archiveDocs['mergedimage.png']['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
            self.__archiveDocs['mergedimage.png']['analysis']['statusMsg'].append(i18n(f'Not a PNG file?'))
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1

        return returned


    def __checkFileStep08a(self):
        """Check preview.png"""
        Debug.print("(i) [__checkFileStep07a] Check preview.png")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        Debug.print("                         Get document: preview.png")
        docContent=self.__getDocumentContent("preview.png")

        if isinstance(docContent, int):
            # can't read document content
            Debug.print("                         /!\ Can't get content: {0}", docContent)
            return docContent

        try:
            image=QImage()
            image.loadFromData(docContent)
        except:
            Debug.print("                         /!\ Invalid PNG file: {0}", e)
            self.__archiveDocs['preview.png']['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
            self.__archiveDocs['preview.png']['analysis']['statusMsg'].append(i18n(f'Not a PNG file?'))
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1

        return returned


    def __checkFileStep09a(self):
        """Check ICC file format"""
        Debug.print("(i) [__checkFileStep09a] Check icc")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        name=self.__archiveDocs['maindoc.xml']['xml.doc.image']['name']
        fName=f"{name}/annotations/icc"

        if not fName in self.__archiveDocs:
            return returned

        Debug.print("                         Get document: {0}", fName)
        docContent=self.__getDocumentContent(fName)

        if isinstance(docContent, int):
            # can't read document content
            Debug.print("                         /!\ Can't get content: {0}", docContent)
            return docContent

        decodedData=self.__readICCData(docContent)

        if not decodedData['error'] is None:
            Debug.print("                         /!\ Invalid ICC file: {0}", decodedData["error"])
            self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
            self.__archiveDocs[fName]['analysis']['statusMsg'].append(i18n(f'Not a valid ICC file ({decodedData["error"]})'))
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
        elif decodedData['iccProfileName']['en-US']!=self.__archiveDocs['maindoc.xml']['xml.doc.image']['profile']:
            Debug.print("                         /!\ Invalid ICC profile: {0}", decodedData['iccProfileName']['en-US'])
            expectedIcc=self.__archiveDocs['maindoc.xml']['xml.doc.image']['profile']
            self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_UNEXPECTED_CONTENT
            self.__archiveDocs[fName]['analysis']['statusMsg'].append(i18n(f"Embedded ICC profile ({decodedData['iccProfileName']['en-US']}) doesn't match expected profile({expectedIcc})"))
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2

        return returned


    def __checkFileStep09b(self):
        """Check ASL file format"""
        Debug.print("(i) [__checkFileStep09b] Check ASL file format")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        name=self.__archiveDocs['maindoc.xml']['xml.doc.image']['name']
        fName=f"{name}/annotations/layerstyles.asl"

        if not fName in self.__archiveDocs:
            return returned

        Debug.print("                         Get document: {0}", fName)
        docContent=self.__getDocumentContent(fName)

        if isinstance(docContent, int):
            # can't read document content
            Debug.print("                         /!\ Can't get content: {0}", docContent)
            return docContent

        decodedData=self.__readASLData(docContent)

        if not decodedData['error'] is None:
            Debug.print("                         /!\ Invalid ASL file: {0}", decodedData["error"])
            self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
            self.__archiveDocs[fName]['analysis']['statusMsg'].append(i18n(f'Not a valid ICC file ({decodedData["error"]})'))
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
        else:
            self.__archiveDocs[fName]['styles']=decodedData['styles']

        return returned


    def __checkFileStep09c(self):
        """Check assistant file format"""
        Debug.print("(i) [__checkFileStep09c] Check assistant files format")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        name=self.__archiveDocs['maindoc.xml']['xml.doc.image']['name']

        for fName in self.__archiveDocs:
            if re.search('\/assistants\/.*\.assistant$', fName):

                Debug.print("                         Get document: {0}", fName)
                docContent=self.__getDocumentContent(fName)

                if isinstance(docContent, int):
                    # can't read document content
                    Debug.print("                         /!\ Can't get content: {0}", docContent)
                    returned|=docContent
                    self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_CANT_BE_READ
                else:
                    # now, we have file content...
                    strDocContent=docContent.decode('UTF-8')

                    xmlParsable=True
                    try:
                        xmlDoc = xmlElement.fromstring(strDocContent)
                    except Exception as e:
                        Debug.print("                         /!\ XML content can't be parsed: {0}", e)
                        xmlParsable=False
                        self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
                        self.__archiveDocs[fName]['analysis']['statusMsg'].append(i18n(f'Not a parsable XML content ({str(e)})'))
                        returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2

        return returned


    def __checkFileStep09d(self):
        """Check palette file format"""
        Debug.print("(i) [__checkFileStep09d] Check palette files format")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        name=self.__archiveDocs['maindoc.xml']['xml.doc.image']['name']

        for fName in self.__archiveDocs:
            if re.search('\/palettes\/.*\.kpl$', fName):
                Debug.print("                         Get document: {0}", fName)
                docContent=self.__getDocumentContent(fName)

                if isinstance(docContent, int):
                    Debug.print("                         /!\ Can't get content: {0}", docContent)
                    # can't read document content
                    returned|=docContent
                    self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_CANT_BE_READ
                else:
                    # now, we have file content...
                    decodedData=self.__readKPLData(docContent)

                    if not decodedData['error'] is None:
                        Debug.print("                         /!\ Invalid KPL file: {0}", decodedData["error"])
                        returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
                        self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
                        self.__archiveDocs[fName]['analysis']['statusMsg'].append(decodedData['error'])
                        if len(decodedData['missingFiles'])>0:
                            self.__archiveDocs[fName]['analysis']['statusMsg'].append(f'Missing files: {", ".join(decodedData["missingFiles"])}')
                        if len(decodedData['invalidFiles'])>0:
                            self.__archiveDocs[fName]['analysis']['statusMsg'].append(f'Invalid files: {", ".join(decodedData["invalidFiles"])}')

        return returned


    def __checkFileStep09e(self):
        """Check references files"""
        Debug.print("(i) [__checkFileStep09e] Check reference files format")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        name=self.__archiveDocs['maindoc.xml']['xml.doc.image']['name']

        for node in self.__archiveDocs['maindoc.xml']:
            if re.match('xml\.doc\.image\.layers\.referenceimages\[\d+\]', node):
                fName=self.__archiveDocs['maindoc.xml'][node]['src']
                if fName in self.__archiveDocs:
                    # check only embedded files
                    Debug.print("                         Get document: {0}", fName)
                    docContent=self.__getDocumentContent(fName)

                    if isinstance(docContent, int):
                        # can't read document content
                        Debug.print("                         /!\ Can't get content: {0}", docContent)
                        returned|=docContent
                        self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_CANT_BE_READ
                        self.__archiveDocs[fName]['analysis']['statusMsg'].append(i18n(f"Unable to read file"))
                    else:
                        try:
                            image=QImage()
                            image.loadFromData(docContent)
                        except:
                            self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
                            self.__archiveDocs[fName]['analysis']['statusMsg'].append(i18n(f'Not a PNG file?'))
                            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1

        return returned


    def __checkFileStep09f(self):
        """Check layers files"""
        Debug.print("(i) [__checkFileStep09f] Check layers files format")

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        name=self.__archiveDocs['maindoc.xml']['xml.doc.image']['name']

        pixelDataSize=None
        for fName in self.__archiveDocs:
            if 'fileType' in self.__archiveDocs[fName]:
                Debug.print("                         Get document[{0}]: {1}", self.__archiveDocs[fName]['fileType'], fName)
                docContent=self.__getDocumentContent(fName)

                if isinstance(docContent, int):
                    # can't read document content
                    Debug.print("                         /!\ Can't get content: {0}", docContent)
                    continue

                if self.__archiveDocs[fName]['fileType']=='tiles':
                    decodedData=self.__readTilesData(docContent)
                    self.__archiveDocs[fName]['fileData']=decodedData
                    # .defaultpixel files is normaly defined AFTER
                    if decodedData['error'] is None:
                        pixelDataSize=decodedData['pixel.size']
                    else:
                        pixelDataSize=None
                elif self.__archiveDocs[fName]['fileType']=='icc':
                    decodedData=self.__readICCData(docContent)
                elif self.__archiveDocs[fName]['fileType']=='pixel':

                    decodedData={'error': None}
                    if pixelDataSize is None:
                        # TODO: if paintlayer, try to determinate pixel size from maindoc.xml
                        #       otherwise, should be 1 byte (mask, selection, ...)
                        pixelDataSize=1

                    if len(docContent)!=pixelDataSize:
                        decodedData['error']="Pixel data size is not expected"

                    pixelDataSize=None # reset status
                elif self.__archiveDocs[fName]['fileType']=='xml/svg':
                    decodedData=self.__readSVGData(docContent)
                elif self.__archiveDocs[fName]['fileType']=='xml/params':
                    decodedData=self.__readParamsData(docContent)
                elif self.__archiveDocs[fName]['fileType']=='xml/transform_params':
                    decodedData=self.__readTransformParamsData(docContent)

                if not decodedData['error'] is None:
                    returned|=self.__archiveDocs[fName]['fileErrLvl']
                    self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
                    self.__archiveDocs[fName]['analysis']['statusMsg'].append(decodedData['error'])
                    Debug.print("                         /!\ Invalid format: {0}", decodedData['error'])
                elif self.__archiveDocs[fName]['fileType']=='tiles' and len(decodedData['invalidTiles'])>0:
                    msg=f"Some tiles ({len(decodedData['invalidTiles'])} of {decodedData['tiles.count']}) can't be decoded"
                    returned|=self.__archiveDocs[fName]['fileErrLvl']
                    self.__archiveDocs[fName]['analysis']['status']|=BCRepairKraFile.DOC_DATA_CORRUPTED
                    self.__archiveDocs[fName]['analysis']['statusMsg'].append(i18n(msg))
                    Debug.print("                         /!\ Invalid format: {0}", msg)

        return returned


    def __setStatus(self, value):
        """Set current file status"""
        self.__status=value
        return self.__status


    def checkFile(self):
        """Check current file for analysis"""
        Debug.print('Start file analysis: {0}', self.__file.fullPathName())

        if not os.access(self.__file.fullPathName(), os.F_OK):
            Debug.print("(!) File doesn't exists")
            return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOT_EXISTS)
        elif not os.access(self.__file.fullPathName(), os.R_OK):
            Debug.print("(!) File can't be read")
            return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOT_READABLE)
        elif self.__file.size()==0:
            Debug.print("(!) File is empty")
            return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_EMPTY)
        elif self.__file.format()!=BCFileManagedFormat.KRA:
            Debug.print("(!) Not a .kra file")
            return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOTKRA)
        else:
            # try to check if file is corrupted or not...
            # 1) List file content
            #
            # 2) Try to read files content
            #       . any file in error => file is invalid
            #       . store file status
            #
            # 3) Check for missing files
            #       . maindoc.xml       => file is invalid; can try to rebuild it...
            #       . documentinfo.xml  => file is invalid; can be built
            #       . mimetype          => file is invalid; can be built
            #       . preview.png       => file is invalid; can be built
            #       . mergedimage.png   => file is invalid; can be built
            #
            # 4) If maindoc.xml exist and readable
            #   4.a) Check format
            #   4.b) Check all files references, if exist (do not check content)
            #           . layers/keyframes
            #           . palettes
            #           . references images
            #           . ...
            #
            # 5) If documentinfo.xml exist and readable
            #   5.a) Check format
            #
            # 6) If mimetype exist and readable
            #   6.a) Check format
            #
            # 7) If preview exist and readable
            #   7.a) Check format
            #
            # 8) If preview exist and readable
            #   8.a) Check format
            #
            # 9) Check files
            #   9.a)    icc:                    {name}/annotations/icc
            #   9.b)    layer styles:           {name}/annotations/layerstyles.asl
            #   9.c)    assistants:             {name}/assistants/{assistant.filename}
            #   9.d)    palettes:               {name}/palettes/{palette.filename}
            #   9.e)    referenceimage:         {referenceimage.src}
            #   9.f)    layers:
            #               paintlayer:         {name}/layers/{layer.filename}
            #                                   {name}/layers/{layer.filename}.icc
            #                                   {name}/layers/{layer.filename}.defaultpixel
            #                                   # if layer have keyframes
            #                                   {name}/layers/{layer.filename}.keyframes.xml
            #                                   {name}/layers/{layer.filename}.f{N}
            #                                   {name}/layers/{layer.filename}.f{N}.defaultpixel
            #               shapelayer:         {name}/layers/{layer.filename}.shapelayer/content.svg
            #               generatorlayer:     {name}/layers/{layer.filename}.filterconfig
            #                                   {name}/layers/{layer.filename}.pixelselection
            #                                   {name}/layers/{layer.filename}.pixelselection.defaultpixel
            #               adjustmentlayer:    {name}/layers/{layer.filename}.filterconfig
            #                                   {name}/layers/{layer.filename}.pixelselection
            #                                   {name}/layers/{layer.filename}.pixelselection.defaultpixel
            #               filtermask:         {name}/layers/{layer.filename}.pixelselection
            #                                   {name}/layers/{layer.filename}.pixelselection.defaultpixel
            #                                   {name}/layers/{layer.filename}.filterconfig
            #               selectionmask:      {name}/layers/{layer.filename}.pixelselection
            #                                   {name}/layers/{layer.filename}.pixelselection.defaultpixel
            #               transparencymask:   {name}/layers/{layer.filename}.pixelselection
            #                                   {name}/layers/{layer.filename}.pixelselection.defaultpixel
            #               transformmask:      {name}/layers/{layer.filename}.transformconfig
            #
            try:
                self.__archive = zipfile.ZipFile(self.__file.fullPathName(), 'r')
            except Exception as e:
                Debug.print("(!) Not a zip file: {0}", e)
                return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOTZIP)

            # by default consider file is valid
            currentStatus=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

            currentStatus|=self.__checkFileStep01()

            if currentStatus!=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID:
                Debug.print("(!) File is not valid, cancel")
                self.__archive.close()
                return self.__setStatus(currentStatus)

            currentStatus|=self.__checkFileStep02()
            currentStatus|=self.__checkFileStep03()
            currentStatus|=self.__checkFileStep04a()
            currentStatus|=self.__checkFileStep04b()
            currentStatus|=self.__checkFileStep05a()
            currentStatus|=self.__checkFileStep06a()
            currentStatus|=self.__checkFileStep07a()
            currentStatus|=self.__checkFileStep08a()
            currentStatus|=self.__checkFileStep09a()
            currentStatus|=self.__checkFileStep09b()
            currentStatus|=self.__checkFileStep09c()
            currentStatus|=self.__checkFileStep09d()
            currentStatus|=self.__checkFileStep09e()
            currentStatus|=self.__checkFileStep09f()

            pp = pprint.PrettyPrinter(indent=2)
            pp.pprint(self.__archiveDocs)

            self.__archive.close()


            return self.__setStatus(currentStatus)


    def file(self):
        """Return BCFile instance"""
        return self.__file
