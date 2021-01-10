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

import re
import os
import os.path
import sys
import tempfile
import zipfile
import pprint
import xml.etree.ElementTree as xmlElement

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

        return zContent


    def __checkFileStep01(self):
        """Initialise list of documents

        Return BCRepairKraFile.REPAIR_STATUS_FILE_IS_DEAD if can't read document list, otherwise return BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID
        """
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
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_DEAD

        return BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID


    def __checkFileStep02(self):
        """Try to read files content

        Return BCRepairKraFile.REPAIR_STATUS_FILE_IS_BROKEN if there's
        some files for which CRC is KO
        """
        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        for fileName in self.__archiveDocs:
            zipFile=self.__archiveDocs[fileName]['zipInfo']
            try:
                zFile = self.__archive.open(fileName)
            except Exception as e:
                self.__archiveDocs[fileName]['analysis']['status']|=BCRepairKraFile.DOC_CANT_BE_OPENED
                self.__archiveDocs[fileName]['analysis']['statusMsg'].append(str(e))
                self.__archiveDocs[fileName]['analysis']['readable']=0
                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_BROKEN
                continue

            cantRead=False
            try:
                zContent = zFile.read()
            except Exception as e:
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

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        for document in documents:
            if not document in self.__archiveDocs:
                print('misssing doc', document)
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
                self.__archiveDocs['maindoc.xml'][f'{key}.framerate']={
                                                                        'type': None,
                                                                        'value': None,
                                                                    }
            else:
                loadAttribs(subNode, f'{key}.framerate', ['type', 'value'])

            subNode=node.find("./{*}range")
            if subNode is None:
                self.__archiveDocs['maindoc.xml'][f'{key}.framerate']={
                                                                        'to': None,
                                                                        'from': None,
                                                                        'type': None
                                                                    }
            else:
                loadAttribs(subNode, f'{key}.framerate', ['to', 'from', 'type'])

            subNode=node.find("./{*}currentTime")
            if subNode is None:
                self.__archiveDocs['maindoc.xml'][f'{key}.currentTime']={
                                                                        'type': None,
                                                                        'value': None,
                                                                    }
            else:
                loadAttribs(subNode, f'{key}.currentTime', ['type', 'value'])

        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        docContent=self.__getDocumentContent("maindoc.xml")

        if isinstance(docContent, int):
            # can't read document content
            return docContent

        # now, we have file content...
        strDocContent=docContent.decode('UTF-8')

        xmlParsable=True
        try:
            xmlDoc = xmlElement.fromstring(strDocContent)
        except Exception as e:
            xmlParsable=False
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
            return BCRepairKraFile.REPAIR_STATUS_FILE_VERSION_NOT_MANAGED
        loadAttribs(node, 'xml.doc', ['syntaxVersion', 'editor', 'kritaVersion'])

        node=xmlDoc.find("./{*}IMAGE")
        if node is None:
            # no IMAGE node??
            # not a valid file...
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3
        loadAttribs(node, 'xml.doc.image', ['name', 'profile', 'width', 'height', 'colorspacename', 'mime'])

        # load layers tree...
        nodes=xmlDoc.findall(".//{*}IMAGE/{*}layers/{*}layer")
        if len(nodes)>0:
            loadNodes(nodes, 'xml.doc.image.layers')

        # load global assistant color
        node=xmlDoc.find(".//{*}IMAGE/{*}ProjectionBackgroundColor")
        if node is None:
            self.__archiveDocs['maindoc.xml']['xml.image.ProjectionBackgroundColor']['ColorData']=None
            returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
        else:
            loadAttribs(node, 'xml.image.ProjectionBackgroundColor', ['ColorData'])

        # load global assistant color
        node=xmlDoc.find(".//{*}IMAGE/{*}GlobalAssistantsColor")
        if node is None:
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
        def addMissingFile(fileName, nodeId):
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
            if not fName in self.__archiveDocs:
                # add file
                addMissingFile(fName)
                return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        def checkLayerStyles(name):
            fName=f'{name}/annotations/layerstyles.asl'
            # need to check if there's some layers for which a style is applied
            found=False
            nodeIdList=[]
            for item in self.__archiveDocs['maindoc.xml']:
                if isinstance(self.__archiveDocs['maindoc.xml'][item], dict) and 'layerstyle' in self.__archiveDocs['maindoc.xml'][item] and not self.__archiveDocs['maindoc.xml'][item]['layerstyle'] is None:
                    found=True
                    nodeIdList.append(item)

            if found and not fName in self.__archiveDocs:
                # there's at least on layer style applied, but no layerfile
                addMissingFile(fName)
                return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2
            else:
                self.__archiveDocs[fName]['maindoc.nodeId']=nodeIdList

            return BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

        def checkAssistants(name):
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID
            fName=f'{name}/assistants/'

            for item in self.__archiveDocs['maindoc.xml']:
                if re.match('xml\.doc\.image\.assistants\.assistant\[\d+\]', item):
                    # item is an assistant
                    if not self.__archiveDocs['maindoc.xml'][item]['filename'] is None:
                        afName=f"{fName}{self.__archiveDocs['maindoc.xml'][item]['filename']}"
                        if not afName in self.__archiveDocs:
                            # assistant file not found
                            addMissingFile(afName)
                            returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
                        else:
                            self.__archiveDocs[afName]['maindoc.nodeId']=item

            return returned

        def checkPalettes(name):
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID
            fName=f'{name}/palettes/'

            for item in self.__archiveDocs['maindoc.xml']:
                if re.match('xml\.doc\.image\.Palettes\.palette\[\d+\]', item):
                    # item is a palette
                    if not self.__archiveDocs['maindoc.xml'][item]['filename'] is None:
                        pfName=f"{fName}{self.__archiveDocs['maindoc.xml'][item]['filename']}"
                        if not pfName is None:
                            if not pfName in self.__archiveDocs:
                                # assistant file not found
                                addMissingFile(pfName)
                                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1
                            else:
                                self.__archiveDocs[pfName]['maindoc.nodeId']=item

            return returned

        def checkReferenceImages():
            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

            for item in self.__archiveDocs['maindoc.xml']:
                if isinstance(self.__archiveDocs['maindoc.xml'][item], dict) and 'nodetype' in self.__archiveDocs['maindoc.xml'][item] and self.__archiveDocs['maindoc.xml'][item]['nodetype']=='referenceimage':
                    # item is a palette
                    if not self.__archiveDocs['maindoc.xml'][item]['src'] is None:
                        fName=self.__archiveDocs['maindoc.xml'][item]['src']
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
                    return docContent

                # now, we have file content...
                strDocContent=docContent.decode('UTF-8')

                xmlParsable=True
                try:
                    xmlDoc = xmlElement.fromstring(strDocContent)
                except Exception as e:
                    xmlParsable=False
                    self.__archiveDocs[file]['analysis']['status']|=BCRepairKraFile.DOC_FORMAT_INVALID
                    self.__archiveDocs[file]['analysis']['statusMsg'].append(i18n(f'Not a parsable XML content ({str(e)})'))

                if not xmlParsable:
                    # TODO: need to think what to do here if XML is not parsable...
                    return BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3

                nodes=xmlDoc.findall(".//{*}keyframe[@frame]")
                if len(nodes)>0:
                    returned=[keyframe.attrib['frame'] for keyframe in nodes]

                return returned

            returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

            checks={
                'paintlayer':       {f'{name}/layers/{{filename}}': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3,
                                     f'{name}/layers/{{filename}}.icc': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2,
                                     f'{name}/layers/{{filename}}.defaultpixel': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1},
                'shapelayer':       {f'{name}/layers/{{filename}}.shapelayer/content.svg': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3},
                'generatorlayer':   {f'{name}/layers/{{filename}}.filterconfig': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2,
                                     f'{name}/layers/{{filename}}.pixelselection': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3,
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1},
                'adjustmentlayer':  {f'{name}/layers/{{filename}}.filterconfig': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2,
                                     f'{name}/layers/{{filename}}.pixelselection': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3,
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1},
                'filtermask':       {f'{name}/layers/{{filename}}.pixelselection': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3,
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1,
                                     f'{name}/layers/{{filename}}.filterconfig': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE2},
                'selectionmask':    {f'{name}/layers/{{filename}}.pixelselection': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3,
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1},
                'transparencymask': {f'{name}/layers/{{filename}}.pixelselection': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3,
                                     f'{name}/layers/{{filename}}.pixelselection.defaultpixel': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE1},
                'transformmask':    {f'{name}/layers/{{filename}}.transformconfig': BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3}
            }

            for item in self.__archiveDocs['maindoc.xml']:
                if isinstance(self.__archiveDocs['maindoc.xml'][item], dict) and 'nodetype' in self.__archiveDocs['maindoc.xml'][item]:

                    nodeType=self.__archiveDocs['maindoc.xml'][item]['nodetype']

                    if nodeType in checks:
                        fileName=self.__archiveDocs['maindoc.xml'][item]['filename']

                        for check in checks[nodeType]:
                            fName=check.replace('{filename}', fileName)

                            if fName and not fName in self.__archiveDocs:
                                # assistant file not found
                                addMissingFile(pfName)
                                returned|=checks[check]
                            else:
                                self.__archiveDocs[fName]['maindoc.nodeId']=item

                        if nodeType=='paintlayer' and not self.__archiveDocs['maindoc.xml'][item]['keyframes'] is None:
                            fName=f"{name}/layers/{self.__archiveDocs['maindoc.xml'][item]['keyframes']}"
                            if fName and not fName in self.__archiveDocs:
                                # assistant file not found
                                addMissingFile(pfName)
                                returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3
                            else:
                                # xml file found, need to read it to determinate how much keyframes files are expected
                                frames=getKeyframeFiles(fName)
                                if isinstance(frames, int):
                                    returned|=frames
                                else:
                                    for frame in frames:
                                        fName=f"{name}/layers/{frame}"
                                        if fName and not fName in self.__archiveDocs:
                                            # assistant file not found
                                            addMissingFile(fName)
                                            returned|=BCRepairKraFile.REPAIR_STATUS_FILE_IS_UNCOMPLETE3
                                        else:
                                            self.__archiveDocs[fName]['maindoc.nodeId']=item

            return returned


        returned=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID
        name=self.__archiveDocs['maindoc.xml']['xml.doc.image']['name']

        returned|=checkICC(name)
        returned|=checkLayerStyles(name)
        returned|=checkAssistants(name)
        returned|=checkPalettes(name)
        returned|=checkReferenceImages()
        returned|=checkLayers(name)

        return returned


    def __setStatus(self, value):
        """Set current file status"""
        self.__status=value
        return self.__status


    def checkFile(self):
        """Check current file for analysis"""
        if not os.access(self.__file.fullPathName(), os.F_OK):
            return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOT_EXISTS)
        elif not os.access(self.__file.fullPathName(), os.R_OK):
            return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOT_READABLE)
        elif self.__file.size()==0:
            return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_EMPTY)
        elif self.__file.format()!=BCFileManagedFormat.KRA:
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
            #   4.b) Check all references
            #           . layers/keyframes
            #           . palettes
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
            # 9) Check all layers file
            #   9.a) Check layers/layerN
            #   9.b) Check layers/layerN.icc
            #   9.c) Check layers/layerN.keyframes.xml (if exists)
            #   9.d) Check layers/layerN.defaultpixel
            #   9.e) Check layers/layerN.fX
            #   9.f) Check layers/layerN.fX.defaultpixel
            #
            # 10) Check reference images
            #
            # 11) Check layers/layerN.shapelayer/content.svg
            #
            #zFile
            #
            #
            # Annotations?
            # guides
            # ...
            try:
                self.__archive = zipfile.ZipFile(self.__file.fullPathName(), 'r')
            except Exception as e:
                return self.__setStatus(BCRepairKraFile.REPAIR_STATUS_FILE_IS_NOTZIP)

            # by default consider file is valid
            currentStatus=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID

            currentStatus|=self.__checkFileStep01()

            if currentStatus!=BCRepairKraFile.REPAIR_STATUS_FILE_IS_VALID:
                self.__archive.close()
                return self.__setStatus(currentStatus)

            currentStatus|=self.__checkFileStep02()
            currentStatus|=self.__checkFileStep03()
            currentStatus|=self.__checkFileStep04a()
            currentStatus|=self.__checkFileStep04b()

            pp = pprint.PrettyPrinter(indent=2)
            pp.pprint(self.__archiveDocs)

            self.__archive.close()


            return self.__setStatus(currentStatus)


    def file(self):
        """Return BCFile instance"""
        return self.__file
