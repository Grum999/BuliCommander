#-----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2021 - Grum999
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

import PyQt5.uic
from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QSettings,
        QStandardPaths
    )
from PyQt5.QtWidgets import (
        QDialog,
        QFileDialog
    )

import os
import os.path
import re
import shutil
import time
import json
import copy

from .bcfile import (
        BCBaseFile,
        BCDirectory,
        BCFile,
        BCFileManagedFormat,
        BCFileManipulateName,
        BCFileManipulateNameLanguageDef,
        BCFileProperty,
        BCFileThumbnailSize,
        BCFileList,
        BCFileListSortRule,
        BCFileListPath,
        BCFileListRuleCombination,
        BCFileListRule,
        BCFileListRuleOperator,
        BCFileListRuleOperatorType
    )
from .bcsettings import (
        BCSettingsValues,
        BCSettingsKey,
        BCSettings
    )

from .bcwpathbar import BCWPathBar

from bulicommander.pktk.modules.strutils import (
        bytesSizeToStr,
        strToBytesSize,
        strDefault,
        boolYesNo
    )
from bulicommander.pktk.modules.timeutils import tsToStr
from bulicommander.pktk.widgets.woperatorinput import (
        WOperatorType,
        WOperatorBaseInput
    )
from bulicommander.pktk.widgets.wiodialog import WDialogBooleanInput
from bulicommander.pktk.widgets.wconsole import WConsole
from bulicommander.pktk.widgets.wnodeeditor import (
        NodeEditorScene,
        NodeEditorNode,
        NodeEditorConnector,
        NodeEditorLink,
        NodeEditorNodeWidget
    )

from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# -----------------------------------------------------------------------------

def setElidedText(wLabel, text, elideMode=Qt.ElideMiddle):
    """Set elided text to given qlabel"""
    metrics=QFontMetrics(wLabel.font())
    wLabel.setText(metrics.elidedText(text, elideMode, wLabel.width()))



class BCSearchFilesDialogBox(QDialog):
    """User interface to search files"""

    __PANEL_SEARCH_ENGINE = 0
    __PANEL_SEARCH_FROMPATH = 1
    __PANEL_SEARCH_FILEFILTERRULES = 2
    __PANEL_SEARCH_IMGFILTERRULES = 3
    __PANEL_SEARCH_CONSOLE = 4

    __TAB_BASIC_SEARCH = 0
    __TAB_ADVANCED_SEARCH = 1
    __TAB_SEARCH_CONSOLE = 2

    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCSearchFilesDialogBox(title, uicontroller)
        db.exec()

    @staticmethod
    def buildBCFileList(searchRulesAsDict, forTextOnly=False):
        """From a given search rule (provided as dictionnary) build and return
        a BCFileList object ready to use

        Return None if not able to parse dictionary properly
        """
        def buildBCFileListRule(filterRulesAsDict):
            # build BCFileListRule from a BCNodeWSearchFileFilterRule dictionary
            returned=BCFileListRule()

            if 'fileName' in filterRulesAsDict and filterRulesAsDict['fileName']['active']:
                if filterRulesAsDict['fileName']['ignoreCase']:
                    ignoreCase=re.I
                else:
                    ignoreCase=0

                # convert operator as regular expression
                if filterRulesAsDict['fileName']['operator'] in ('match', 'not match'):
                    ruleOperator=BCFileListRuleOperator(re.compile(filterRulesAsDict['fileName']['value'], ignoreCase),
                                                        filterRulesAsDict['fileName']['operator'],
                                                        BCFileListRuleOperatorType.REGEX)
                elif filterRulesAsDict['fileName']['operator'] in ('like', 'not like'):
                    ruleOperator=BCFileListRuleOperator(re.compile(re.escape(filterRulesAsDict['fileName']['value']).replace(r'\?', '.').replace(r'\*', '.*'), ignoreCase),
                                                        filterRulesAsDict['fileName']['operator'].replace('like', 'match'),
                                                        BCFileListRuleOperatorType.REGEX)
                else:
                    ruleOperator=BCFileListRuleOperator(re.compile(f"^{re.escape(filterRulesAsDict['fileName']['value'])}$", ignoreCase),
                                                        'match' if filterRulesAsDict['fileName']['operator']=='=' else 'not match',
                                                        BCFileListRuleOperatorType.REGEX)
                returned.setName(ruleOperator)

            if 'fileSize' in filterRulesAsDict and filterRulesAsDict['fileSize']['active']:
                value=strToBytesSize(f"{filterRulesAsDict['fileSize']['value']}{filterRulesAsDict['fileSize']['unit']}")
                value2=strToBytesSize(f"{filterRulesAsDict['fileSize']['value2']}{filterRulesAsDict['fileSize']['unit']}")

                if filterRulesAsDict['fileSize']['operator'] in ('between', 'not between'):
                    ruleOperator=BCFileListRuleOperator((value, value2),
                                                        filterRulesAsDict['fileSize']['operator'],
                                                        BCFileListRuleOperatorType.INT,
                                                        (f"{filterRulesAsDict['fileSize']['value']}{filterRulesAsDict['fileSize']['unit']}",f"{filterRulesAsDict['fileSize']['value2']}{filterRulesAsDict['fileSize']['unit']}"))
                else:
                    ruleOperator=BCFileListRuleOperator(value,
                                                        filterRulesAsDict['fileSize']['operator'],
                                                        BCFileListRuleOperatorType.INT,
                                                        f"{filterRulesAsDict['fileSize']['value']}{filterRulesAsDict['fileSize']['unit']}")

                returned.setSize(ruleOperator)

            if 'fileDate' in filterRulesAsDict and filterRulesAsDict['fileDate']['active']:
                if filterRulesAsDict['fileDate']['operator'] in ('between', 'not between'):
                    ruleOperator=BCFileListRuleOperator((filterRulesAsDict['fileDate']['value'], filterRulesAsDict['fileDate']['value2']),
                                                        filterRulesAsDict['fileDate']['operator'],
                                                        BCFileListRuleOperatorType.DATETIME,
                                                        (tsToStr(filterRulesAsDict['fileDate']['value']),tsToStr(filterRulesAsDict['fileDate']['value2'])))
                else:
                    ruleOperator=BCFileListRuleOperator(filterRulesAsDict['fileDate']['value'],
                                                        filterRulesAsDict['fileDate']['operator'],
                                                        BCFileListRuleOperatorType.DATETIME,
                                                        tsToStr(filterRulesAsDict['fileDate']['value']))

                returned.setModifiedDateTime(ruleOperator)

            if 'imageWidth' in filterRulesAsDict and filterRulesAsDict['imageWidth']['active']:
                if filterRulesAsDict['imageWidth']['operator'] in ('between', 'not between'):
                    ruleOperator=BCFileListRuleOperator((filterRulesAsDict['imageWidth']['value'], filterRulesAsDict['imageWidth']['value2']),
                                                        filterRulesAsDict['imageWidth']['operator'],
                                                        BCFileListRuleOperatorType.INT,
                                                        (f"{filterRulesAsDict['imageWidth']['value']}px",f"{filterRulesAsDict['imageWidth']['value2']}px"))
                else:
                    ruleOperator=BCFileListRuleOperator(filterRulesAsDict['imageWidth']['value'],
                                                        filterRulesAsDict['imageWidth']['operator'],
                                                        BCFileListRuleOperatorType.INT,
                                                        f"{filterRulesAsDict['imageWidth']['value']}px")

                returned.setImageWidth(ruleOperator)

            if 'imageHeight' in filterRulesAsDict and filterRulesAsDict['imageHeight']['active']:
                if filterRulesAsDict['imageHeight']['operator'] in ('between', 'not between'):
                    ruleOperator=BCFileListRuleOperator((filterRulesAsDict['imageHeight']['value'], filterRulesAsDict['imageHeight']['value2']),
                                                        filterRulesAsDict['imageHeight']['operator'],
                                                        BCFileListRuleOperatorType.INT,
                                                        (f"{filterRulesAsDict['imageHeight']['value']}px",f"{filterRulesAsDict['imageHeight']['value2']}px"))
                else:
                    ruleOperator=BCFileListRuleOperator(filterRulesAsDict['imageHeight']['value'],
                                                        filterRulesAsDict['imageHeight']['operator'],
                                                        BCFileListRuleOperatorType.INT,
                                                        f"{filterRulesAsDict['imageHeight']['value']}px")

                returned.setImageHeight(ruleOperator)

            if 'imageFormat' in filterRulesAsDict and filterRulesAsDict['imageFormat']['active']:
                ruleOperator=BCFileListRuleOperator(filterRulesAsDict['imageFormat']['value'],
                                                    '=',
                                                    BCFileListRuleOperatorType.STRING,
                                                    BCFileManagedFormat.translate(filterRulesAsDict['imageFormat']['value']))

                returned.setFormat(ruleOperator)

            return returned

        def buildBCFileListRules(currentId, linksTo, nodeSearchFilters):
            # return a BCFileListRule tree
            if nodeSearchFilters[currentId]['widget']['type'] in ('BCNodeWSearchFileFilterRule', 'BCNodeWSearchImgFilterRule'):
                # no need to search anymore, return filter rule
                return buildBCFileListRule(nodeSearchFilters[currentId]['widget'])
            else:
                # a <BCNodeWSearchFileFilterRuleOperator>
                # need to build connection with input filters
                operatorNode=nodeSearchFilters[currentId]

                operatorsTable={
                        'and': BCFileListRuleCombination.OPERATOR_AND,
                        'or': BCFileListRuleCombination.OPERATOR_OR,
                        'not': BCFileListRuleCombination.OPERATOR_NOT
                    }

                ruleCombination=BCFileListRuleCombination(operatorsTable[operatorNode['widget']['value']])

                if currentId in linksTo:
                    for link in linksTo[currentId]:
                        ruleCombination.addRule(buildBCFileListRules(link, linksTo, nodeSearchFilters))

                return ruleCombination


        if not isinstance(searchRulesAsDict, dict):
            raise EInvalidType("Given `searchRulesAsDict` must be a <dict>")
        elif not 'nodes' in searchRulesAsDict:
            raise EInvalidValue("Given `searchRulesAsDict` must contains a 'nodes' key")
        elif not 'links' in searchRulesAsDict:
            raise EInvalidValue("Given `searchRulesAsDict` must contains a 'links' key")

        # need to parse dictionary to get references
        nodeSearchEngine=None
        nodeSearchPaths={}
        nodeSearchFilters={}

        for node in searchRulesAsDict['nodes']:
            if node['widget']['type']=='BCNodeWSearchEngine':
                nodeSearchEngine=node
            elif node['widget']['type'] in ('BCNodeWSearchFileFilterRule', 'BCNodeWSearchImgFilterRule', 'BCNodeWSearchFileFilterRuleOperator'):
                nodeSearchFilters[node['properties']['id']]=node
            elif node['widget']['type']=='BCNodeWSearchFromPath':
                nodeSearchPaths[node['properties']['id']]=node

        if nodeSearchEngine is None or (len(nodeSearchPaths)==0 and not forTextOnly):
            # can't continue...
            return None

        # need to search for filters relationships
        # rebuild links from Id, easier to rebuild relationship tree
        filterToLinks={}
        pathToLinks=[]
        for link in searchRulesAsDict['links']:
            toNId, toCId=link['connect']['to'].split(':')
            fromNId, fromCId=link['connect']['from'].split(':')

            if re.match("InputFilterRule", toCId) and re.match("OutputFilterRule", fromCId):
                if not toNId in filterToLinks:
                    filterToLinks[toNId]=[]
                if not fromNId in filterToLinks[toNId]:
                    filterToLinks[toNId].append(fromNId)
            elif re.match("InputPath", toCId) and re.match("OutputPath", fromCId):
                pathToLinks.append(fromNId)

        #print('toLinks', json.dumps(toLinks, indent=4, sort_keys=True))
        #print('nodeSearchEngine', nodeSearchEngine)
        #print('nodeSearchFilters', nodeSearchFilters)
        #print('nodeSearchFilters', nodeSearchPaths)

        filterRules=None
        # start from BCNodeWSearchEngine 'InputFilterRule'
        if nodeSearchEngine['properties']['id'] in filterToLinks:
            # a filter conditions is connected to search engine
            startFromId=filterToLinks[nodeSearchEngine['properties']['id']][0]
            filterRules=buildBCFileListRules(startFromId, filterToLinks, nodeSearchFilters)

        returnedFileList=BCFileList()

        if not filterRules is None:
            returnedFileList.addRule(filterRules)

        for pathId in pathToLinks:
            returnedFileList.addPath(BCFileListPath(nodeSearchPaths[pathId]['widget']["path"], nodeSearchPaths[pathId]['widget']["scanSubDirectories"]))

        return returnedFileList

    def __init__(self, title, uicontroller, parent=None):
        super(BCSearchFilesDialogBox, self).__init__(parent)

        self.__inInit=True
        self.__title = title
        self.__uiController = uicontroller
        self.__fileNfo = self.__uiController.panel().files()

        self.__processing=False

        self.__currentSelectedNodeWidget=None

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcsearchfiles.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__initialise()
        self.setWindowTitle(self.__title)
        self.setModal(False)
        self.__inInit=False

    def __initialise(self):
        """Initialise user interface"""
        self.tbBasicNewSearch.clicked.connect(self.__basicResetSearch)

        self.tbAdvancedNewSearch.clicked.connect(self.__advancedResetSearch)
        self.tbAdvancedAddPath.clicked.connect(self.__advancedAddPath)
        self.tbAdvancedAddFileFilter.clicked.connect(self.__advancedAddFileFilterRule)
        self.tbAdvancedAddImgFilter.clicked.connect(self.__advancedAddImgFilterRule)
        self.tbAdvancedAddFilterOperator.clicked.connect(self.__advancedAddFilterRuleOperator)
        self.tbAdvancedDeleteItems.clicked.connect(self.__advancedDelete)
        self.tbAdvancedZoomToFit.clicked.connect(self.wneAdvancedView.zoomToFit)
        self.tbAdvancedZoom1_1.clicked.connect(self.wneAdvancedView.resetZoom)

        self.tbAdvancedSearchSave.clicked.connect(lambda x: self.__scene.exportToFile('/home/grum/Temporaire/tmp_search.json'))
        self.tbAdvancedSearchOpen.clicked.connect(lambda x: self.__scene.importFromFile('/home/grum/Temporaire/tmp_search.json'))

        self.pbClose.clicked.connect(self.accept)
        self.pbSearch.clicked.connect(self.executeSearch)

        self.twSearchModes.setCurrentIndex(0)

        self.__scene=self.wneAdvancedView.nodeScene()
        self.__scene.setOptionSnapToGrid(True)
        self.__scene.setOptionNodeCloseButtonVisible(True)
        self.__scene.nodeSelectionChanged.connect(self.__advancedSelectionChanged)
        self.__scene.linkSelectionChanged.connect(self.__advancedSelectionChanged)
        self.__scene.nodeAdded.connect(self.__advancedSearchChanged)
        self.__scene.nodeRemoved.connect(self.__advancedSearchChanged)
        self.__scene.linkAdded.connect(self.__advancedSearchChanged)
        self.__scene.linkRemoved.connect(self.__advancedSearchChanged)
        self.__scene.nodeOutputUpdated.connect(self.__advancedSearchChanged)
        self.__scene.setFormatIdentifier("bulicommander-search-filter-advanced")


        self.wsffpAdvanced.modified.connect(self.__advancedFileFromPathChanged)
        self.wsffrAdvanced.modified.connect(self.__advancedFileFilterRule)
        self.wsifrAdvanced.modified.connect(self.__advancedImgFilterRule)

        self.wcExecutionConsole.setOptionShowGutter(False)
        self.wcExecutionConsole.appendLine(i18n('Not search executed yet'))
        self.pbProgress.setVisible(False)

        self.__basicResetSearch(True)
        self.__advancedResetSearch(True)
        self.__advancedSelectionChanged()

    def __advancedCalculateNodePosition(self):
        """Calculate position for a new node added to scene"""
        width, freq=self.__scene.gridSize()
        position=QPointF(3*width, 3*width)

        selectedNodes=self.__scene.selectedNodes()
        if len(selectedNodes)>0:
            position+=selectedNodes[0].position()

        return position

    def __advancedSelectionChanged(self):
        """Node/Link selection has changed"""
        selectedNodes=self.__scene.selectedNodes()
        nbSelectedNodes=len(selectedNodes)

        # if nothing selected, disable delete button
        self.tbAdvancedDeleteItems.setEnabled(nbSelectedNodes>0 or len(self.__scene.selectedLinks())>0)

        # switch to right panel according to current selection
        if nbSelectedNodes==1 and isinstance(selectedNodes[0].widget(), BCNodeWSearchFromPath):
            self.__currentSelectedNodeWidget=selectedNodes[0].widget()
            self.wsffpAdvanced.importFromDict(selectedNodes[0].serialize()['widget'])
            self.swAdvancedPanel.setCurrentIndex(BCSearchFilesDialogBox.__PANEL_SEARCH_FROMPATH)
        elif nbSelectedNodes==1 and isinstance(selectedNodes[0].widget(), BCNodeWSearchFileFilterRule):
            self.__currentSelectedNodeWidget=selectedNodes[0].widget()
            self.wsffrAdvanced.importFromDict(selectedNodes[0].serialize()['widget'])
            self.swAdvancedPanel.setCurrentIndex(BCSearchFilesDialogBox.__PANEL_SEARCH_FILEFILTERRULES)
        elif nbSelectedNodes==1 and isinstance(selectedNodes[0].widget(), BCNodeWSearchImgFilterRule):
            self.__currentSelectedNodeWidget=selectedNodes[0].widget()
            self.wsifrAdvanced.importFromDict(selectedNodes[0].serialize()['widget'])
            self.swAdvancedPanel.setCurrentIndex(BCSearchFilesDialogBox.__PANEL_SEARCH_IMGFILTERRULES)
        else:
            # in all other case (None selected or more than one selected, or search engine selected)
            # display search engine panel
            self.__currentSelectedNodeWidget=None
            self.swAdvancedPanel.setCurrentIndex(BCSearchFilesDialogBox.__PANEL_SEARCH_ENGINE)
            self.__advancedSearchChanged()

    def __advancedSearchChanged(self, modified=None):
        """Search model has been modified"""
        if self.swAdvancedPanel.currentIndex()==BCSearchFilesDialogBox.__PANEL_SEARCH_ENGINE:
            dataAsDict=self.__advancedExportConfig()
            bcFileList=BCSearchFilesDialogBox.buildBCFileList(dataAsDict, True)
            if bcFileList:
                self.tbSearchDescription.setPlainText(bcFileList.exportHQuery())

    def __advancedFileFromPathChanged(self):
        """Something has been modified, update node"""
        if self.__currentSelectedNodeWidget is None:
            return

        self.__currentSelectedNodeWidget.deserialize(self.wsffpAdvanced.exportAsDict()['widget'])

    def __advancedFileFilterRule(self):
        """Something has been modified, update node"""
        if self.__currentSelectedNodeWidget is None:
            return

        self.__currentSelectedNodeWidget.deserialize(self.wsffrAdvanced.exportAsDict()['widget'])

    def __advancedImgFilterRule(self):
        """Something has been modified, update node"""
        if self.__currentSelectedNodeWidget is None:
            return

        self.__currentSelectedNodeWidget.deserialize(self.wsifrAdvanced.exportAsDict()['widget'])

    def __advancedExportConfig(self):
        """Export current node schema"""
        return self.__scene.serialize()

    def __advancedResetSearch(self, force=False):
        """reset current advanced search"""
        if not force and self.wneAdvancedView.nodeScene().isModified():
            if not WDialogBooleanInput.display(f"{self.__title}::{i18n('Reset advanced search')}", i18n("Current search has been modified, do you confirm to reset to default values?")):
                return

        scene=self.wneAdvancedView.nodeScene()

        scene.clear()
        nwSearchEngine=BCNodeWSearchEngine(scene, i18n("Search engine"))
        self.wneAdvancedView.resetZoom()

    def __advancedAddPath(self):
        """Add a BCNodeWSearchFromPath node"""
        position=self.__advancedCalculateNodePosition()

        nwSearchFromPath=BCNodeWSearchFromPath(self.__scene, i18n("Source directory"))
        nwSearchFromPath.node().setPosition(position)
        nwSearchFromPath.node().setSelected(True, False)

    def __advancedAddFileFilterRule(self):
        """Add a BCNodeWSearchFileFilterRule node"""
        position=self.__advancedCalculateNodePosition()

        nwFilterRule=BCNodeWSearchFileFilterRule(self.__scene, i18n("File filter"))
        nwFilterRule.node().setPosition(position)
        nwFilterRule.node().setSelected(True, False)

    def __advancedAddImgFilterRule(self):
        """Add a BCNodeWSearchImgFilterRule node"""
        position=self.__advancedCalculateNodePosition()

        nwFilterRule=BCNodeWSearchImgFilterRule(self.__scene, i18n("Image filter"))
        nwFilterRule.node().setPosition(position)
        nwFilterRule.node().setSelected(True, False)

    def __advancedAddFilterRuleOperator(self):
        """Add a BCNodeWSearchFileFilterRuleOperator node"""
        position=self.__advancedCalculateNodePosition()

        nwFilterRuleOperator=BCNodeWSearchFileFilterRuleOperator(self.__scene, i18n("Filter operator"))
        nwFilterRuleOperator.node().setPosition(position)
        nwFilterRuleOperator.node().setSelected(True, False)

    def __advancedDelete(self):
        """Delete all selected items"""
        for node in self.__scene.selectedNodes():
            self.__scene.removeNode(node)

    def __basicExportConfig(self):
        """Export current basic configuration as a WNodeEditor dictionnary:
        - Allows to easily convert a basic search to advanced search
        - Allows to use the same format than advanced search to apply BCFileListRule conversion
          (less code, same data format, same results for identical basic<->advanced search definition)
        """
        # define Uuid for main nodes
        idNodeWSearchEngine=QUuid.createUuid().toString()

        nodeFileFilterRule=self.wsffrBasic.exportAsDict()
        nodeImgFilterRule=self.wsifrBasic.exportAsDict()
        nodeFromPath=self.wsffpBasic.exportAsDict()

        filterList=[]
        for nodeProperties in [nodeFileFilterRule, nodeImgFilterRule]:
            for property in nodeProperties['widget']:
                if isinstance(nodeProperties['widget'][property], dict) and nodeProperties['widget'][property]['active']:
                    filterList.append(nodeProperties)
                    break

        #   Case 1
        #   ------
        #       > No file filter
        #       > No image filter
        #
        #       filterList=[]
        #
        #       ┌──────────┐      ┌──────────────┐
        #       │ FromPath ├╌╌╌╌╌╌┤ SearchEngine │
        #       └──────────┘      └──────────────┘
        #
        #
        #   Case 2
        #   ------
        #       > File filter
        #       > No image filter
        #
        #       filterList=[nodeFileFilterRule]
        #
        #       ┌──────────┐      ┌──────────────┐      ┌────────────────┐
        #       │ FromPath ├╌╌╌╌╌╌┤ SearchEngine ├╌╌╌╌╌╌┤ FileFilterRule │
        #       └──────────┘      └──────────────┘      └────────────────┘
        #
        #
        #   Case 3
        #   ------
        #       > No file filter
        #       > Image filter
        #
        #       filterList=[nodeImgFilterRule]
        #
        #       ┌──────────┐      ┌──────────────┐      ┌────────────────┐
        #       │ FromPath ├╌╌╌╌╌╌┤ SearchEngine ├╌╌╌╌╌╌┤ ImgFilterRule  │
        #       └──────────┘      └──────────────┘      └────────────────┘
        #
        #
        #   Case 4
        #   ------
        #       > File filter
        #       > Image filter
        #
        #       filterList=[nodeFileFilterRule, nodeImgFilterRule]
        #                                                                      ┌────────────────┐
        #                                               ┌────────────────┐  ╭╌╌┤ FileFilterRule │
        #       ┌──────────┐      ┌──────────────┐      │ FilterOperator ├╌╌╯  └────────────────┘
        #       │ FromPath ├╌╌╌╌╌╌┤ SearchEngine ├╌╌╌╌╌╌┤                │
        #       └──────────┘      └──────────────┘      │     (AND)      ├╌╌╮  ┌────────────────┐
        #                                               └────────────────┘  ╰╌╌┤ ImgFilterRule  │
        #                                                                      └────────────────┘

        # define main properties
        exportedResult={
            "extraData": {},
            "formatIdentifier": "bulicommander-search-filter-basic",
            "links": [{
                        # Link between [FromPath] and [SearchEngine] is always present and hard-coded
                        "connect": {
                            "from": f"{nodeFromPath['properties']['id']}:OutputPath",
                            "to": f"{idNodeWSearchEngine}:InputPath1"
                        }
                    }],
            "nodes": [
                        # search engine is always provided, and hard-coded
                        {
                            "properties": {
                                            "id": f"{idNodeWSearchEngine}",
                                            "title": i18n("Search engine")
                                        },
                            "connectors": [
                                        {
                                            "id": "InputPath1",
                                            "properties": {
                                                "direction": NodeEditorConnector.DIRECTION_INPUT,
                                                "location": NodeEditorConnector.LOCATION_LEFT_TOP
                                            }
                                        },
                                        {
                                            "id": "InputFilterRule",
                                            "properties": {
                                                "direction": NodeEditorConnector.DIRECTION_INPUT,
                                                "location": NodeEditorConnector.LOCATION_RIGHT_TOP
                                            }
                                        }
                                    ],
                            "widget": {"type": "BCNodeWSearchEngine"}
                        },
                        # from path is always provided with data from BCWSearchFileFromPath widget
                        nodeFromPath
                    ]
        }
        # => default exported result already cover case 1

        if len(filterList)==1:
            # No FilterOperator (case 2&3)
            #
            # direct link between [filterList] item (FileFilterRule or ImgFilterRule)
            # and [SearchEngine]
            exportedResult['nodes'].append(filterList[0])
            exportedResult['links'].append({
                    "connect": {
                        "from": f"{filterList[0]['properties']['id']}:OutputFilterRule",
                        "to": f"{idNodeWSearchEngine}:InputFilterRule"
                    }
                })
        elif len(filterList)==2:
            # Need FilterOperator (case 4)
            idNodeWSearchFilterOperator=QUuid.createUuid().toString()

            # Filter Operator definition is hard-coded
            exportedResult['nodes'].append({
                    "properties": {
                                    "id": f"{idNodeWSearchFilterOperator}",
                                    "title": i18n("Filter operator")
                                },
                    "connectors": [
                                {
                                    "id": "OutputFilterRule",
                                    "properties": {
                                        "direction": NodeEditorConnector.DIRECTION_OUTPUT,
                                        "location": NodeEditorConnector.LOCATION_LEFT_BOTTOM
                                    }
                                },
                                {
                                    "id": "InputFilterRule1",
                                    "properties": {
                                        "direction": NodeEditorConnector.DIRECTION_INPUT,
                                        "location": NodeEditorConnector.LOCATION_RIGHT_TOP
                                    }
                                },
                                {
                                    "id": "InputFilterRule2",
                                    "properties": {
                                        "direction": NodeEditorConnector.DIRECTION_INPUT,
                                        "location": NodeEditorConnector.LOCATION_RIGHT_TOP
                                    }
                                }
                            ],
                    "widget":   {
                                    "type": "BCNodeWSearchFileFilterRuleOperator",
                                    "value": "and"
                                }
                })
            # Link between [FilterOperator] and [SearchEngine] is hard-coded
            exportedResult['links'].append({
                    "connect": {
                        "from": f"{idNodeWSearchFilterOperator}:OutputFilterRule",
                        "to": f"{idNodeWSearchEngine}:InputFilterRule"
                    }
                })

            # now need to add filterList items
            for index, filter in enumerate(filterList):
                exportedResult['nodes'].append(filter)
                exportedResult['links'].append({
                        "connect": {
                            "from": f"{filter['properties']['id']}:OutputFilterRule",
                            "to": f"{idNodeWSearchFilterOperator}:InputFilterRule{index}"
                        }
                    })

        return exportedResult

    def __basicResetSearch(self, force=False):
        """reset current basic search"""
        if not force and (self.wsffrBasic.isModified() or self.wsffpBasic.isModified()):
            if not WDialogBooleanInput.display(f"{self.__title}::{i18n('Reset basic search')}", i18n("Current search has been modified, do you confirm to reset to default values?")):
                return

        self.wsffrBasic.resetToDefault()
        self.wsffpBasic.resetToDefault()

    def __executeSearchProcessSignals(self, informations):
        """Search is in progress...

        Each information is a tuple, first item determine current search steps
        """
        if informations[0]==BCFileList.STEPEXECUTED_SEARCH_FROM_PATH:
            # 0 => step identifier
            # 1 => path
            # 2 => flag for sub-dir. scan
            # 3 => number of files found
            if informations[2]:
                self.wcExecutionConsole.appendLine(f"""&nbsp;- {i18n('Scan directory (and sub-directories)')} #y#{informations[1]}#, {i18n('found files:')} #c#{informations[3]}#""")
            else:
                self.wcExecutionConsole.appendLine(f"""&nbsp;- {i18n('Scan directory')} #y#{informatins[1]}#, {i18n('found files:')} #c#{informations[3]}#""")
        elif informations[0]==BCFileList.STEPEXECUTED_SEARCH_FROM_PATHS:
            # 0 => step identifier
            # 1 => total number of files
            # 2 => total number of directories (if asked to return directories)
            # 3 => total (number of files + number of directories)
            # 4 => total time duration (in seconds)
            self.wcExecutionConsole.appendLine(f"""&nbsp;{i18n('Total files:')} #c#{informations[3]}#""")
            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Scan executed in')}# #w#{informations[4]:0.4f}s##lk#)#*""")

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"""**{i18n('Analyze files:')}** """)
            self.pbProgress.setMaximum(100)
        elif informations[0]==BCFileList.STEPEXECUTED_PROGRESS_ANALYZE:
            # 0 => step identifier
            # 1 => current pct
            print("STEPEXECUTED_PROGRESS_ANALYZE", informations[1])
            self.pbProgress.setValue(informations[1])
            self.pbProgress.update()
            QApplication.processEvents()
        elif informations[0]==BCFileList.STEPEXECUTED_ANALYZE_METADATA:
            # 0 => step identifier
            # 1 => total time duration (in seconds)
            self.wcExecutionConsole.append(f"""#g#{i18n('OK')}#""")
            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Analysis executed in')}# #w#{informations[1]:0.4f}s##lk#)#*""")

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"""**{i18n('Filter files:')}** """)
            self.pbProgress.setValue(0)
        elif informations[0]==BCFileList.STEPEXECUTED_PROGRESS_FILTER:
            # 0 => step identifier
            # 1 => current pct
            print("STEPEXECUTED_PROGRESS_FILTER", informations[1])
            self.pbProgress.setValue(informations[1])
            self.pbProgress.update()
            QApplication.processEvents()
        elif informations[0]==BCFileList.STEPEXECUTED_FILTER_FILES:
            # 0 => step identifier
            # 1 => number of files after filter applied
            # 2 => total time duration (in seconds)
            self.wcExecutionConsole.append(f"""#g#{i18n('OK')}#""")
            self.wcExecutionConsole.appendLine(f"""&nbsp;{i18n('Total files:')} #c#{informations[1]}#""")
            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Filter applied in')}# #w#{informations[2]:0.4f}s##lk#)#*""")

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"""**{i18n('Build results:')}** """)

            self.pbProgress.setValue(0)
            self.pbProgress.setMaximum(0)
        elif informations[0]==BCFileList.STEPEXECUTED_BUILD_RESULTS:
            # 0 => step identifier
            # 1 => total time duration (in seconds)
            self.wcExecutionConsole.append(f"""#g#{i18n('OK')}#""")
            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Build made in')}# #w#{informations[1]:0.4f}s##lk#)#*""")

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"""**{i18n('Sort results:')}** """)

            self.pbProgress.setMaximum(100)
        elif informations[0]==BCFileList.STEPEXECUTED_PROGRESS_SORT:
            # 0 => step identifier
            # 1 => current pct
            print("STEPEXECUTED_PROGRESS_SORT", informations[1])
            self.pbProgress.setValue(informations[1])
            self.pbProgress.update()
            QApplication.processEvents()
        elif informations[0]==BCFileList.STEPEXECUTED_SORT_RESULTS:
            # 0 => step identifier
            # 1 => total time duration (in seconds)
            self.wcExecutionConsole.append(f"""#g#{i18n('OK')}#""")
            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Sort made in')}# #w#{informations[1]:0.4f}s##lk#)#*""")


    def executeSearch(self):
        """Execute basic/advanced search, according to current active tab"""
        if self.twSearchModes.currentIndex()==BCSearchFilesDialogBox.__TAB_BASIC_SEARCH:
            dataAsDict=self.__basicExportConfig()
        else:
            dataAsDict=self.__advancedExportConfig()

        if self.twSearchModes.currentIndex()==BCSearchFilesDialogBox.__TAB_BASIC_SEARCH:
            # for debug, to remove...
            print(json.dumps(dataAsDict, indent=4, sort_keys=True))
            self.wneAdvancedView.nodeScene().deserialize(dataAsDict)
            self.wneAdvancedView.zoomToFit()

        self.wcExecutionConsole.clear()
        self.wcExecutionConsole.appendLine(i18n('Build search query:')+' ')
        self.twSearchModes.setCurrentIndex(BCSearchFilesDialogBox.__TAB_SEARCH_CONSOLE)
        bcFileList=BCSearchFilesDialogBox.buildBCFileList(dataAsDict)
        if bcFileList:
            self.pbProgress.setMinimum(0)
            self.pbProgress.setMaximum(0)
            self.pbProgress.setValue(0)
            self.pbProgress.setVisible(True)

            self.tabBasicSearch.setEnabled(False)
            self.tabAdvancedSearch.setEnabled(False)
            self.pbSearch.setEnabled(False)
            self.pbClose.setEnabled(False)

            bcFileList.stepExecuted.connect(self.__executeSearchProcessSignals)

            self.wcExecutionConsole.append(f"#g#{i18n('OK')}#")

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(i18n('Execute search...'))

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"""**{i18n('Scan directories:')}** """)

            print(bcFileList.execute(True, True, True, False, [
                BCFileList.STEPEXECUTED_SEARCH_FROM_PATHS,
                BCFileList.STEPEXECUTED_SEARCH_FROM_PATH,
                BCFileList.STEPEXECUTED_ANALYZE_METADATA,
                BCFileList.STEPEXECUTED_FILTER_FILES,
                BCFileList.STEPEXECUTED_BUILD_RESULTS,
                BCFileList.STEPEXECUTED_SORT_RESULTS,
                BCFileList.STEPEXECUTED_PROGRESS_ANALYZE,
                BCFileList.STEPEXECUTED_PROGRESS_FILTER,
                BCFileList.STEPEXECUTED_PROGRESS_SORT
            ]))

            #print('--'*80)
            print(bcFileList.exportTxtResults())
            #print('--'*80)
            print(bcFileList.stats())

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(i18n('Execution done'))

            self.tabBasicSearch.setEnabled(True)
            self.tabAdvancedSearch.setEnabled(True)
            self.pbSearch.setEnabled(True)
            self.pbClose.setEnabled(True)
        else:
            self.wcExecutionConsole.append(f"#r#{i18n('KO')}#")
            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Current search definition is not valid')}#*""")

        self.pbProgress.setVisible(False)



class BCWSearchFileFromPath(QWidget):
    """A widget to define search file from path source"""
    modified=Signal()

    def __init__(self, parent=None):
        super(BCWSearchFileFromPath, self).__init__(parent)
        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcwsearchfilefrompath.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.bcwpbBasicPath.setOptions(BCWPathBar.OPTION_SHOW_NONE)

        # flag to determinate if values has been modified
        self.__isModified=False

        self.__initialise()
        self.__setDefaultValues()

    def __initialise(self):
        """Initialise widget interface"""
        # option checkbox
        self.bcwpbBasicPath.pathChanged.connect(self.__setModified)
        self.cbBasicSubDirScan.toggled.connect(self.__setModified)

    def __setDefaultValues(self):
        """Initialise default values"""
        self.bcwpbBasicPath.setPath()
        self.cbBasicSubDirScan.setChecked(True)

        self.__isModified=False

    def __setModified(self):
        """Set widget as modified"""
        self.__isModified=True
        self.modified.emit()

    def resetToDefault(self):
        """Reset to default values"""
        self.__setDefaultValues()

    def isModified(self):
        """Return true if values has been modified"""
        return self.__isModified

    def exportAsDict(self):
        """Export widget configuration as dictionnary"""
        returned={
                "properties": {
                                "id": QUuid.createUuid().toString(),
                                "title": i18n("Source directory")
                            },
                "connectors": [
                            {
                                "id": "OutputPath",
                                "properties": {
                                    "direction": NodeEditorConnector.DIRECTION_OUTPUT,
                                    "location": NodeEditorConnector.LOCATION_RIGHT_BOTTOM
                                }
                            }
                        ],
                "widget": {
                            "type": "BCNodeWSearchFromPath",
                            "path": self.bcwpbBasicPath.path(),
                            "scanSubDirectories": self.cbBasicSubDirScan.isChecked()
                        }
            }

        return returned

    def importFromDict(self, dataAsDict):
        """Import widget configuration from dictionnary

        Note: only "widget" key content is expected for input


        Example of expected dictionary:
            {
                "type": "BCNodeWSearchFromPath",
                "path": "/home/xxx/myDirectory",
                "scanSubDirectories": True
            }
        """
        if not isinstance(dataAsDict, dict):
            raise EInvalidType("Given `dataAsDict` must be a <dict>")
        elif not ("type" in dataAsDict and dataAsDict["type"]=="BCNodeWSearchFromPath"):
            raise EInvalidValue("Given `dataAsDict` must contains key 'type' with value 'BCNodeWSearchFromPath'")

        # reset to default
        self.__setDefaultValues()

        if "path" in dataAsDict and isinstance(dataAsDict['path'], str):
            self.bcwpbBasicPath.setPath(dataAsDict['path'])

        if "scanSubDirectories" in dataAsDict and isinstance(dataAsDict['scanSubDirectories'], bool):
            self.cbBasicSubDirScan.setChecked(dataAsDict['scanSubDirectories'])

        self.__isModified=False



class BCWSearchFileFilterRules(QWidget):
    """A widget to define file filter rules"""
    modified=Signal()

    def __init__(self, parent=None):
        super(BCWSearchFileFilterRules, self).__init__(parent)
        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcwsearchfilefilterrules.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        # flag to determinate if values has been modified
        self.__isModified=False

        self.__initialise()
        self.__setDefaultValues()

    def __initialise(self):
        """Initialise widget interface"""
        # option checkbox
        self.cbFileName.setMinimumHeight(self.woiFileName.minimumSizeHint().height())
        self.cbFileSize.setMinimumHeight(self.woiFileSize.minimumSizeHint().height())
        self.cbFileDateTime.setMinimumHeight(self.woiFileDateTime.minimumSizeHint().height())

        self.cbFileName.toggled.connect(self.__fileNameToggled)
        self.cbFileSize.toggled.connect(self.__fileSizeToggled)
        self.cbFileDateTime.toggled.connect(self.__fileDateTimeToggled)

        self.__fileNameToggled(False)
        self.__fileSizeToggled(False)
        self.__fileDateTimeToggled(False)

        # file pattern
        self.woiFileName.operatorChanged.connect(self.__setModified)
        self.woiFileName.setOperators([
                WOperatorType.OPERATOR_MATCH,
                WOperatorType.OPERATOR_NOT_MATCH,
                WOperatorType.OPERATOR_LIKE,
                WOperatorType.OPERATOR_NOT_LIKE
            ])
        self.woiFileName.valueChanged.connect(self.__setModified)

        # file size
        self.woiFileSize.setMinimum(0)
        self.woiFileSize.setMaximum(999999999999.99)
        self.woiFileSize.setDecimals(2)
        self.woiFileSize.setSuffixLabel("Unit")
        self.woiFileSize.setSuffixList([('Kilobyte (kB)', 'kB'), ('Megabyte (MB)', 'MB'), ('Gigabytes (GB)', 'GB'),
                                        ('Kibibyte (KiB)', 'KiB'), ('Mebibyte (MiB)', 'MiB'), ('Gibibyte (GiB)', 'GiB')])
        self.woiFileSize.operatorChanged.connect(self.__setModified)
        self.woiFileSize.valueChanged.connect(self.__setModified)
        self.woiFileSize.value2Changed.connect(self.__setModified)
        self.woiFileSize.suffixChanged.connect(self.__setModified)

        # file date
        self.woiFileDateTime.setMinimum(0)
        self.woiFileDateTime.setMaximum(QDateTime.fromString("2099-12-31 23:59:59", "yyyy-MM-dd HH:mm:ss"))
        self.woiFileDateTime.operatorChanged.connect(self.__setModified)
        self.woiFileDateTime.valueChanged.connect(self.__setModified)
        self.woiFileDateTime.value2Changed.connect(self.__setModified)

    def __setDefaultValues(self):
        """Initialise default values"""
        self.cbFileName.setChecked(False)
        self.cbFileSize.setChecked(False)
        self.cbFileDateTime.setChecked(False)

        self.woiFileName.setValue("")
        self.woiFileName.setOperator(WOperatorType.OPERATOR_LIKE)
        self.cbFileNameIgnoreCase.setChecked(True)

        self.woiFileSize.setValue(1.00)
        self.woiFileSize.setOperator(WOperatorType.OPERATOR_GE)
        if BCSettings.get(BCSettingsKey.CONFIG_GLB_FILE_UNIT)==BCSettingsValues.FILE_UNIT_KIB:
            self.woiFileSize.setValue2(1024.00)
            self.woiFileSize.setSuffix('KiB')
        else:
            self.woiFileSize.setValue2(1000.00)
            self.woiFileSize.setSuffix('kB')

        dateTimeNow=QDateTime.currentDateTime()
        dateTimeYm1=QDateTime(dateTimeNow)
        dateTimeYm1.addYears(-1)
        self.woiFileDateTime.setValue(dateTimeYm1)
        self.woiFileDateTime.setValue2(dateTimeNow)
        self.woiFileDateTime.setOperator(WOperatorType.OPERATOR_BETWEEN)

        self.__isModified=False

    def __setModified(self):
        """Set widget as modified"""
        self.__isModified=True
        self.modified.emit()

    def __fileNameToggled(self, checked):
        """Checkbox 'file name' has been toggled"""
        self.__setModified()
        self.woiFileName.setEnabled(checked)
        self.woiFileName.setVisible(checked)
        self.cbFileNameIgnoreCase.setEnabled(checked)
        self.cbFileNameIgnoreCase.setVisible(checked)

    def __fileSizeToggled(self, checked):
        """Checkbox 'file size' has been toggled"""
        self.__setModified()
        self.woiFileSize.setEnabled(checked)
        self.woiFileSize.setVisible(checked)

    def __fileDateTimeToggled(self, checked):
        """Checkbox 'file date/time' has been toggled"""
        self.__setModified()
        self.woiFileDateTime.setEnabled(checked)
        self.woiFileDateTime.setVisible(checked)

    def resetToDefault(self):
        """Reset to default values"""
        self.__setDefaultValues()

    def isModified(self):
        """Return true if values has been modified"""
        return self.__isModified

    def exportAsDict(self):
        """Export widget configuration as dictionnary"""
        returned={
                "properties": {
                                "id": QUuid.createUuid().toString(),
                                "title": i18n("Filter condition")
                            },
                "connectors": [
                            {
                                "id": "OutputFilterRule",
                                "properties": {
                                    "direction": NodeEditorConnector.DIRECTION_OUTPUT,
                                    "location": NodeEditorConnector.LOCATION_BOTTOM_RIGHT
                                }
                            }
                        ],
                "widget": {
                            "type": "BCNodeWSearchFileFilterRule",
                            "fileName": {
                                    "active": self.cbFileName.isChecked(),
                                    "operator": self.woiFileName.operator(),
                                    "value": self.woiFileName.value(),
                                    "ignoreCase": (self.cbFileNameIgnoreCase.isChecked() and self.cbFileNameIgnoreCase.isVisible()),
                                },
                            "fileSize": {
                                    "active": self.cbFileSize.isChecked(),
                                    "operator": self.woiFileSize.operator(),
                                    "value": self.woiFileSize.value(),
                                    "value2": self.woiFileSize.value2(),
                                    "unit": self.woiFileSize.suffix()
                                },
                            "fileDate": {
                                    "active": self.cbFileDateTime.isChecked(),
                                    "operator": self.woiFileDateTime.operator(),
                                    "value": self.woiFileDateTime.value(),
                                    "value2": self.woiFileDateTime.value2()
                                }
                        }
            }

        return returned

    def importFromDict(self, dataAsDict):
        """Import widget configuration from dictionnary

        Note: only "widget" key content is expected for input


        Example of expected dictionary:
            "widget": {
                "type": "BCNodeWSearchFileFilterRule",
                "fileDate": {
                    "active": false
                },
                "fileName": {
                    "active": true,
                    "ignoreCase": true,
                    "operator": "WOperatorType.OPERATOR_LIKE",
                    "value": ""
                },
                "fileSize": {
                    "active": true,
                    "operator": "WOperatorType.OPERATOR_GE",
                    "unit": "KiB",
                    "value": 1.0,
                    "value2": 1024.0
                }
            }
        """
        if not isinstance(dataAsDict, dict):
            raise EInvalidType("Given `dataAsDict` must be a <dict>")
        elif not ("type" in dataAsDict and dataAsDict["type"]=="BCNodeWSearchFileFilterRule"):
            raise EInvalidValue("Given `dataAsDict` must contains key 'type' with value 'BCNodeWSearchFileFilterRule'")

        self.__setDefaultValues()

        if "fileName" in dataAsDict and isinstance(dataAsDict['fileName'], dict):
            self.cbFileName.setChecked(dataAsDict['fileName']['active'])
            self.cbFileNameIgnoreCase.setChecked(dataAsDict['fileName']['ignoreCase'])
            self.woiFileName.setValue(dataAsDict['fileName']['value'])
            self.woiFileName.setOperator(dataAsDict['fileName']['operator'])

        if "fileSize" in dataAsDict and isinstance(dataAsDict['fileSize'], dict):
            self.cbFileSize.setChecked(dataAsDict['fileSize']['active'])
            self.woiFileSize.setValue(dataAsDict['fileSize']['value'])
            self.woiFileSize.setValue2(dataAsDict['fileSize']['value2'])
            self.woiFileSize.setOperator(dataAsDict['fileSize']['operator'])
            self.woiFileSize.setSuffix(dataAsDict['fileSize']['unit'])

        if "fileDate" in dataAsDict and isinstance(dataAsDict['fileDate'], dict):
            self.cbFileDateTime.setChecked(dataAsDict['fileDate']['active'])
            self.woiFileDateTime.setValue(dataAsDict['fileDate']['value'])
            self.woiFileDateTime.setValue2(dataAsDict['fileDate']['value2'])
            self.woiFileDateTime.setOperator(dataAsDict['fileDate']['operator'])

        self.__isModified=False



class BCWSearchImgFilterRules(QWidget):
    """A widget to define image filter rules"""
    modified=Signal()

    def __init__(self, parent=None):
        super(BCWSearchImgFilterRules, self).__init__(parent)
        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcwsearchimgfilterrules.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        # flag to determinate if values has been modified
        self.__isModified=False

        self.__initialise()
        self.__setDefaultValues()

    def __initialise(self):
        """Initialise widget interface"""
        # option checkbox
        self.cbImageFormat.setMinimumHeight(self.cblImageFormat.minimumSizeHint().height())
        self.cbImageWidth.setMinimumHeight(self.woiImageWidth.minimumSizeHint().height())
        self.cbImageHeight.setMinimumHeight(self.woiImageHeight.minimumSizeHint().height())

        self.cbImageFormat.toggled.connect(self.__imageFormatToggled)
        self.cbImageWidth.toggled.connect(self.__imageWidthToggled)
        self.cbImageHeight.toggled.connect(self.__imageHeightToggled)

        self.__imageFormatToggled(False)
        self.__imageWidthToggled(False)
        self.__imageHeightToggled(False)

        # image format
        for imageFormat in BCFileManagedFormat.list():
            if imageFormat!=BCFileManagedFormat.JPEG:
                self.cblImageFormat.addItem(BCFileManagedFormat.translate(imageFormat), imageFormat)
        self.cblImageFormat.currentIndexChanged.connect(self.__setModified)

        # file image width
        self.woiImageWidth.setMinimum(1)
        self.woiImageWidth.setMaximum(9999999)
        self.woiImageWidth.setSuffix('px')
        self.woiImageWidth.operatorChanged.connect(self.__setModified)
        self.woiImageWidth.valueChanged.connect(self.__setModified)
        self.woiImageWidth.value2Changed.connect(self.__setModified)

        # file image height
        self.woiImageHeight.setMinimum(1)
        self.woiImageHeight.setMaximum(9999999)
        self.woiImageHeight.setSuffix('px')
        self.woiImageHeight.operatorChanged.connect(self.__setModified)
        self.woiImageHeight.valueChanged.connect(self.__setModified)
        self.woiImageHeight.value2Changed.connect(self.__setModified)

    def __setDefaultValues(self):
        """Initialise default values"""
        self.cbImageFormat.setChecked(False)
        self.cbImageWidth.setChecked(False)
        self.cbImageHeight.setChecked(False)

        self.cblImageFormat.setCurrentIndex(0)

        self.woiImageWidth.setValue(320)
        self.woiImageWidth.setValue2(1920)
        self.woiImageWidth.setOperator(WOperatorType.OPERATOR_GE)

        self.woiImageHeight.setValue(200)
        self.woiImageHeight.setValue2(1080)
        self.woiImageHeight.setOperator(WOperatorType.OPERATOR_GE)

        self.__isModified=False

    def __setModified(self):
        """Set widget as modified"""
        self.__isModified=True
        self.modified.emit()

    def __imageFormatToggled(self, checked):
        """Checkbox 'file type' has been toggled"""
        self.__setModified()
        self.cblImageFormat.setEnabled(checked)
        self.cblImageFormat.setVisible(checked)

    def __imageWidthToggled(self, checked):
        """Checkbox 'file img width' has been toggled"""
        self.__setModified()
        self.woiImageWidth.setEnabled(checked)
        self.woiImageWidth.setVisible(checked)

    def __imageHeightToggled(self, checked):
        """Checkbox 'file img height' has been toggled"""
        self.__setModified()
        self.woiImageHeight.setEnabled(checked)
        self.woiImageHeight.setVisible(checked)

    def resetToDefault(self):
        """Reset to default values"""
        self.__setDefaultValues()

    def isModified(self):
        """Return true if values has been modified"""
        return self.__isModified

    def exportAsDict(self):
        """Export widget configuration as dictionnary"""
        returned={
                "properties": {
                                "id": QUuid.createUuid().toString(),
                                "title": i18n("Filter condition")
                            },
                "connectors": [
                            {
                                "id": "OutputFilterRule",
                                "properties": {
                                    "direction": NodeEditorConnector.DIRECTION_OUTPUT,
                                    "location": NodeEditorConnector.LOCATION_BOTTOM_RIGHT
                                }
                            }
                        ],
                "widget": {
                            "type": "BCNodeWSearchImgFilterRule",
                            "imageFormat": {
                                    "active": self.cbImageFormat.isChecked(),
                                    "value": self.cblImageFormat.currentData()
                                },
                            "imageWidth": {
                                    "active": self.cbImageWidth.isChecked(),
                                    "operator": self.woiImageWidth.operator(),
                                    "value": self.woiImageWidth.value(),
                                    "value2": self.woiImageWidth.value2()
                                },
                            "imageHeight": {
                                    "active": self.cbImageHeight.isChecked(),
                                    "operator": self.woiImageHeight.operator(),
                                    "value": self.woiImageHeight.value(),
                                    "value2": self.woiImageHeight.value2()
                                }
                        }
            }

        return returned

    def importFromDict(self, dataAsDict):
        """Import widget configuration from dictionnary

        Note: only "widget" key content is expected for input


        Example of expected dictionary:
            "widget": {
                "type": "BCNodeWSearchFileFilterRule",
                "imageHeight": {
                    "active": false
                },
                "imageWidth": {
                    "active": false
                },
                "imageFormat": {
                    "active": true,
                    "value": "kra"
                }
            }
        """
        if not isinstance(dataAsDict, dict):
            raise EInvalidType("Given `dataAsDict` must be a <dict>")
        elif not ("type" in dataAsDict and dataAsDict["type"]=="BCNodeWSearchImgFilterRule"):
            raise EInvalidValue("Given `dataAsDict` must contains key 'type' with value 'BCNodeWSearchImgFilterRule'")

        self.__setDefaultValues()

        if "imageFormat" in dataAsDict and isinstance(dataAsDict['imageFormat'], dict):
            self.cbImageFormat.setChecked(dataAsDict['imageFormat']['active'])
            for index in range(self.cblImageFormat.count()):
                if self.cblImageFormat.itemData(index)==dataAsDict['imageFormat']['value']:
                    self.cblImageFormat.setCurrentIndex(index)
                    break

        if "imageWidth" in dataAsDict and isinstance(dataAsDict['imageWidth'], dict):
            self.cbImageWidth.setChecked(dataAsDict['imageWidth']['active'])
            self.woiImageWidth.setValue(dataAsDict['imageWidth']['value'])
            self.woiImageWidth.setValue2(dataAsDict['imageWidth']['value2'])
            self.woiImageWidth.setOperator(dataAsDict['imageWidth']['operator'])

        if "imageHeight" in dataAsDict and isinstance(dataAsDict['imageHeight'], dict):
            self.cbImageHeight.setChecked(dataAsDict['imageHeight']['active'])
            self.woiImageHeight.setValue(dataAsDict['imageHeight']['value'])
            self.woiImageHeight.setValue2(dataAsDict['imageHeight']['value2'])
            self.woiImageHeight.setOperator(dataAsDict['imageHeight']['operator'])

        self.__isModified=False



class NodeEditorConnectorPath(NodeEditorConnector):
    # a path connector
    def __init__(self, id=None, direction=0x01, location=0x01, color=None, borderColor=None, borderSize=None, parent=None):
        super(NodeEditorConnectorPath, self).__init__(id, direction, location, color, borderColor, borderSize, parent)
        if direction==NodeEditorConnector.DIRECTION_INPUT:
            tooltip="".join(["<b>", i18n("Input path"), "</b><br/><br/>", i18n("Should be connected from an&nbsp;<b>Output path</b>&nbsp;connector of a&nbsp;<i>Source directory</i>")])
        else:
            tooltip="".join(["<b>", i18n("Output path"), "</b><br/><br/>", i18n("Should be connected to an&nbsp;<b>Input path</b>&nbsp;connector of a&nbsp;<i>Search engine</i>")])
        self.setToolTip(tooltip)



class NodeEditorConnectorFilter(NodeEditorConnector):
    # a filter connector
    def __init__(self, id=None, direction=0x01, location=0x01, color=None, borderColor=None, borderSize=None, parent=None, source=''):
        super(NodeEditorConnectorFilter, self).__init__(id, direction, location, color, borderColor, borderSize, parent)
        if direction==NodeEditorConnector.DIRECTION_INPUT:
            tooltip="".join(["<b>", i18n("Input file filter"), "</b><br/><br/>",
                             i18n("Should be connected from an&nbsp;<b>Output file filter</b>&nbsp;connector of:"), "<ul><li>",
                             i18n("a <i>File filter</i>"),
                             "</li><li>",
                             i18n("an <i>Image filter</i>"),
                             "</li><li>",
                             i18n("a <i>Filter operator</i>")])
        else:
            tooltip="".join(["<b>", i18n(f"Output {source} filter"), "</b><br/><br/>",
                             i18n("Should be connected to an&nbsp;<b>Input file filter</b>&nbsp;connector of:"), "<ul><li>",
                             i18n("a <i>Search engine</i>"),
                             "</li><li>",
                             i18n("a <i>Filter operator</i>")])
        self.setToolTip(tooltip)



class BCNodeWSearchEngine(NodeEditorNodeWidget):
    """Main search engine node"""

    def __init__(self, scene, title, parent=None):
        inputPathConnector=NodeEditorConnectorPath('InputPath1', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_LEFT_TOP)
        inputFilterRuleConnector=NodeEditorConnectorFilter('InputFilterRule', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_RIGHT_TOP)

        inputPathConnector.addAcceptedConnectionFrom(NodeEditorConnectorPath)
        inputFilterRuleConnector.addAcceptedConnectionFrom(NodeEditorConnectorFilter)

        super(BCNodeWSearchEngine, self).__init__(scene, title, connectors=[inputPathConnector, inputFilterRuleConnector], parent=parent)

        self.node().setRemovable(False)

        self.node().connectorLinked.connect(self.__checkInputPath)
        self.node().connectorUnlinked.connect(self.__checkInputPath)

    def __checkInputPath(self, node, connector):
        """A connector has been connected/disconnected

        Check paths connector (always need a have ONE available connector)
        - Add connector if needed
        - Remove connector if not needed
        """
        lastNumber=1
        nbInputPathAvailable=0
        toRemove=[]
        for connector in reversed(node.connector()):
            if isinstance(connector, NodeEditorConnectorPath):
                if r:=re.match("InputPath(\d+)$", connector.id()):
                    lastNumber=max(lastNumber, int(r.groups()[0])+1)

                if len(connector.links())==0:
                    if nbInputPathAvailable==0:
                        nbInputPathAvailable+=1
                    else:
                        toRemove.append(connector)

        for connector in toRemove:
            node.removeConnector(connector)

        if nbInputPathAvailable==0:
            # no input path connector available, add one
            inputPathConnector=NodeEditorConnectorPath(f'InputPath{lastNumber}', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_LEFT_TOP)
            inputPathConnector.addAcceptedConnectionFrom(NodeEditorConnectorPath)
            node.addConnector(inputPathConnector)



class BCNodeWSearchFromPath(NodeEditorNodeWidget):
    """A path source node"""

    def __init__(self, scene, title, parent=None):
        outputPathConnector=NodeEditorConnectorPath('OutputPath', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_RIGHT_BOTTOM)

        self.__lblPath=QLabel()
        self.__lblRecursive=QLabel()

        self.__lblPath.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        self.__layout=QFormLayout()
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addRow(f"<b>{i18n('Path')}</b>", self.__lblPath)
        self.__layout.addRow(f"<b>{i18n('Scan sub-dir.')}</b>", self.__lblRecursive)

        self.__data={
                'path': os.path.expanduser("~"),
                'scanSubDirectories': True
            }

        super(BCNodeWSearchFromPath, self).__init__(scene, title, connectors=[outputPathConnector], parent=parent)

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        self.node().setMinimumSize(QSize(400, 150))
        self.setLayout(self.__layout)

    def serialize(self):
        """Convert current widget node properties to dictionnary"""
        return copy.deepcopy(self.__data)

    def deserialize(self, data):
        """Convert current given data dictionnary to update widget node properties"""
        if 'path' in data:
            self.__data['path']=data['path']
            setElidedText(self.__lblPath, self.__data['path'], Qt.ElideLeft)
            self.__lblPath.setToolTip(self.__data['path'])

        if 'scanSubDirectories' in data:
            self.__data['scanSubDirectories']=data['scanSubDirectories']
            self.__lblRecursive.setText(boolYesNo(self.__data['scanSubDirectories']))



class BCNodeWSearchFileFilterRule(NodeEditorNodeWidget):
    """A file filter source node"""

    def __init__(self, scene, title, parent=None):
        outputFilterRuleConnector=NodeEditorConnectorFilter('OutputFilterRule', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_LEFT_BOTTOM, source=i18n('file'))

        self.__lblName=QLabel()
        self.__lblSize=QLabel()
        self.__lblDate=QLabel()

        self.__lblName.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)


        self.__layout=QFormLayout()
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addRow(QLabel(f"<b>{i18n('Filtered by:')}</b>"))
        self.__layout.addRow(f"- <b>{i18n('Name')}</b>", self.__lblName)
        self.__layout.addRow(f"- <b>{i18n('Size')}</b>", self.__lblSize)
        self.__layout.addRow(f"- <b>{i18n('Date')}</b>", self.__lblDate)

        if BCSettings.get(BCSettingsKey.CONFIG_GLB_FILE_UNIT)==BCSettingsValues.FILE_UNIT_KIB:
            sizeValue2=1024.00
            sizeunit='KiB'
        else:
            sizeValue2=1000.00
            sizeunit='kB'

        dateTimeNow=QDateTime.currentDateTime()
        dateTimeYm1=QDateTime(dateTimeNow)
        dateTimeYm1.addYears(-1)

        self.__data={
                    "fileName": {
                            "active": False,
                            "operator": WOperatorType.OPERATOR_LIKE,
                            "value": '',
                            "ignoreCase": True
                        },
                    "fileSize": {
                            "active": False,
                            "operator": WOperatorType.OPERATOR_GE,
                            "value": 1.00,
                            "value2": sizeValue2,
                            "unit": sizeunit
                        },
                    "fileDate": {
                            "active": False,
                            "operator": WOperatorType.OPERATOR_BETWEEN,
                            "value": dateTimeYm1,
                            "value2": dateTimeNow
                        }
                }

        super(BCNodeWSearchFileFilterRule, self).__init__(scene, title, connectors=[outputFilterRuleConnector], parent=parent)

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        self.node().setMinimumSize(QSize(400, 200))
        self.setLayout(self.__layout)

    def serialize(self):
        """Convert current widget node properties to dictionnary"""
        return copy.deepcopy(self.__data)

    def deserialize(self, data):
        """Convert current given data dictionnary to update widget node properties"""
        if 'fileDate' in data:
            self.__data['fileDate']=copy.deepcopy(data['fileDate'])
            if self.__data['fileDate']['active']:
                if self.__data['fileDate']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{tsToStr(self.__data['fileDate']['value'])} and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{tsToStr(self.__data['fileDate']['value2'])}"
                elif self.__data['fileDate']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{tsToStr(self.__data['fileDate']['value'])} or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{tsToStr(self.__data['fileDate']['value2'])}"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self.__data['fileDate']['operator'])}{tsToStr(self.__data['fileDate']['value'])}"
                setElidedText(self.__lblDate, text, Qt.ElideRight)
                self.__lblDate.setToolTip(text)
            else:
                self.__lblDate.setText(boolYesNo(False))
                self.__lblDate.setToolTip('')

        if 'fileName' in data:
            self.__data['fileName']=copy.deepcopy(data['fileName'])
            if self.__data['fileName']['active']:
                setElidedText(self.__lblName, WOperatorBaseInput.operatorLabel(self.__data['fileName']['operator'])+' "'+self.__data['fileName']['value']+'"', Qt.ElideRight)

                text=f"""<i>{WOperatorBaseInput.operatorLabel(self.__data['fileName']['operator'])}</i> "{self.__data['fileName']['value']}"<br/>"""
                if self.__data['fileName']['ignoreCase']:
                    text+=i18n("(case insensitive)")
                else:
                    text+=i18n("(case sensitive)")
                self.__lblName.setToolTip(text)
            else:
                self.__lblName.setText(boolYesNo(False))
                self.__lblName.setToolTip('')

        if 'fileSize' in data:
            self.__data['fileSize']=copy.deepcopy(data['fileSize'])
            if self.__data['fileSize']['active']:
                if self.__data['fileSize']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{self.__data['fileSize']['value']}{self.__data['fileSize']['unit']} and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{self.__data['fileSize']['value2']}{self.__data['fileSize']['unit']}"
                elif self.__data['fileSize']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{self.__data['fileSize']['value']}{self.__data['fileSize']['unit']} or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{self.__data['fileSize']['value2']}{self.__data['fileSize']['unit']}"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self.__data['fileSize']['operator'])}{self.__data['fileSize']['value']}{self.__data['fileSize']['unit']}"
                setElidedText(self.__lblSize, text, Qt.ElideRight)
                self.__lblSize.setToolTip(text)
            else:
                self.__lblSize.setText(boolYesNo(False))
                self.__lblSize.setToolTip('')



class BCNodeWSearchImgFilterRule(NodeEditorNodeWidget):
    """A file filter source node"""

    def __init__(self, scene, title, parent=None):
        outputFilterRuleConnector=NodeEditorConnectorFilter('OutputFilterRule', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_LEFT_BOTTOM, source=i18n('image'))

        self.__lblImgFormat=QLabel()
        self.__lblImgWidth=QLabel()
        self.__lblImgHeight=QLabel()

        self.__layout=QFormLayout()
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addRow(QLabel(f"<b>{i18n('Filtered by:')}</b>"))
        self.__layout.addRow(f"- <b>{i18n('Format')}</b>", self.__lblImgFormat)
        self.__layout.addRow(f"- <b>{i18n('Width')}</b>", self.__lblImgWidth)
        self.__layout.addRow(f"- <b>{i18n('Height')}</b>", self.__lblImgHeight)

        self.__data={
                    "imageFormat": {
                            "active": False,
                            "value": BCFileManagedFormat.KRA
                        },
                    "imageWidth": {
                            "active": False,
                            "operator": WOperatorType.OPERATOR_GE,
                            "value": 320,
                            "value2": 1920
                        },
                    "imageHeight": {
                            "active": False,
                            "operator": WOperatorType.OPERATOR_GE,
                            "value": 200,
                            "value2": 1080
                        }
                }

        super(BCNodeWSearchImgFilterRule, self).__init__(scene, title, connectors=[outputFilterRuleConnector], parent=parent)

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        self.node().setMinimumSize(QSize(400, 200))
        self.setLayout(self.__layout)

    def serialize(self):
        """Convert current widget node properties to dictionnary"""
        return copy.deepcopy(self.__data)

    def deserialize(self, data):
        """Convert current given data dictionnary to update widget node properties"""
        if 'imageHeight' in data:
            self.__data['imageHeight']=copy.deepcopy(data['imageHeight'])
            if self.__data['imageHeight']['active']:
                if self.__data['imageHeight']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{self.__data['imageHeight']['value']}px and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{self.__data['imageHeight']['value2']}px"
                elif self.__data['imageHeight']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{self.__data['imageHeight']['value']}px or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{self.__data['imageHeight']['value2']}px"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self.__data['imageHeight']['operator'])}{self.__data['imageHeight']['value']}px"
                setElidedText(self.__lblImgHeight, text, Qt.ElideRight)
                self.__lblImgHeight.setToolTip(text)
            else:
                self.__lblImgHeight.setText(boolYesNo(False))
                self.__lblImgHeight.setToolTip('')

        if 'imageWidth' in data:
            self.__data['imageWidth']=copy.deepcopy(data['imageWidth'])
            if self.__data['imageWidth']['active']:
                if self.__data['imageWidth']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{self.__data['imageWidth']['value']}px and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{self.__data['imageWidth']['value2']}px"
                elif self.__data['imageWidth']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{self.__data['imageWidth']['value']}px or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{self.__data['imageWidth']['value2']}px"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self.__data['imageWidth']['operator'])}{self.__data['imageWidth']['value']}px"
                setElidedText(self.__lblImgWidth, text, Qt.ElideRight)
                self.__lblImgWidth.setToolTip(text)
            else:
                self.__lblImgWidth.setText(boolYesNo(False))
                self.__lblImgWidth.setToolTip('')

        if 'imageFormat' in data:
            self.__data['imageFormat']=copy.deepcopy(data['imageFormat'])
            if self.__data['imageFormat']['active']:
                text=BCFileManagedFormat.translate(self.__data['imageFormat']['value'])
                self.__lblImgFormat.setText(text)
                self.__lblImgFormat.setToolTip(text)
            else:
                self.__lblImgFormat.setText(boolYesNo(False))
                self.__lblImgFormat.setToolTip('')



class BCNodeWSearchFileFilterRuleOperator(NodeEditorNodeWidget):
    """A file filter operator node"""

    def __init__(self, scene, title, parent=None):
        inputFilterRuleConnector=NodeEditorConnectorFilter('InputFilterRule1', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_RIGHT_TOP)
        outputFilterRuleConnector=NodeEditorConnectorFilter('OutputFilterRule', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_LEFT_BOTTOM)

        inputFilterRuleConnector.addAcceptedConnectionFrom(NodeEditorConnectorFilter)

        self.__cbValue=QComboBox()
        self.__cbValue.addItem(i18n("AND"), "and")
        self.__cbValue.addItem(i18n("OR"), "or")
        self.__cbValue.addItem(i18n("NOT"), "not")
        self.__cbValue.currentIndexChanged.connect(self.__cbValueChanged)

        self.__layout=QVBoxLayout()
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addWidget(self.__cbValue)
        self.__layout.addStretch()

        super(BCNodeWSearchFileFilterRuleOperator, self).__init__(scene, title, connectors=[inputFilterRuleConnector, outputFilterRuleConnector], parent=parent)

        self.node().connectorLinked.connect(self.__checkInputFilter)
        self.node().connectorUnlinked.connect(self.__checkInputFilter)
        self.node().setMinimumSize(QSize(200, 100))
        self.setLayout(self.__layout)

    def __cbValueChanged(self, index):
        """Current operator value has been changed"""
        self.__checkInputFilter()
        self.updateOutput('OutputFilterRule', self.__cbValue.currentData())

    def __checkInputFilter(self, node=None, connector=None):
        """A connector has been connected/disconnected

        Check filters connectors
        ========================

        If operator is "AND" or "OR",
            Can have more than one input entry
            In this case, we always need to have ONE available input connector
            - Add connector if needed
            - Remove connector if not needed

        If operator is "NOT"
            Can have only ONE input entry
            In this case:
            - Available connector are removed
            - Connector that should not be used are colored in red
        """
        if node is None:
            node=self.node()

        if self.__cbValue.currentData()=='not':
            firstInputIsUsed=True
        else:
            firstInputIsUsed=False

        lastNumber=1
        nbInputFilterAvailable=0
        nbInputFilter=0
        toRemove=[]
        connectors=node.connector()
        for connector in reversed(connectors):
            if isinstance(connector, NodeEditorConnectorFilter) and connector.isInput():
                nbInputFilter+=1

                if r:=re.match("InputFilterRule(\d+)$", connector.id()):
                    lastNumber=max(lastNumber, int(r.groups()[0])+1)

                if len(connector.links())==0:
                    if firstInputIsUsed:
                        toRemove.append(connector)
                    else:
                        if nbInputFilterAvailable==0:
                            nbInputFilterAvailable+=1
                        else:
                            toRemove.append(connector)

        if len(toRemove)>0:
            # need to remove some connectors
            if firstInputIsUsed and nbInputFilter==1:
                # if we "NOT" operator
                # if total number of input filter is 1, need to remove connector
                # from list, as we need to keep at least one connector
                toRemove.pop()

            # remove connectors, if any
            for connector in toRemove:
                node.removeConnector(connector)

        # according to operator type (AND, OR, NOT) need to define standard colors or warning (red) color
        # to connectors
        firstInput=True
        for connector in node.connector():
            if connector.isInput():
                if firstInputIsUsed and not firstInput:
                    # connector is used but we already have one connector used for "NOT"
                    # can't delete value but set it in red -- let user remove link or change operator type
                    connector.setColor(QColor(Qt.red))
                else:
                    connector.setColor(None)
                firstInput=False

        if nbInputFilterAvailable==0 and not firstInputIsUsed:
            # no input path connector available, add one if not "NOT" operator
            inputFilterRuleConnector=NodeEditorConnectorFilter(f'InputFilterRule{lastNumber}', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_RIGHT_TOP)
            inputFilterRuleConnector.addAcceptedConnectionFrom(NodeEditorConnectorFilter)
            node.addConnector(inputFilterRuleConnector)

    def serialize(self):
        return {
                "value": self.__cbValue.currentData()
            }

    def deserialize(self, data):
        if "value" in data:
            for index in range(self.__cbValue.count()):
                if self.__cbValue.itemData(index)==data['value']:
                    self.__cbValue.setCurrentIndex(index)
                    break
