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
from .bcexportfiles import (
        BCExportFormat,
        BCExportFiles,
        BCExportFilesDialogBox
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
from bulicommander.pktk.modules.timeutils import (
        tsToStr,
        Stopwatch
    )
from bulicommander.pktk.modules.utils import (
        JsonQObjectEncoder,
        JsonQObjectDecoder,
        Debug
    )

from bulicommander.pktk.widgets.woperatorinput import (
        WOperatorType,
        WOperatorBaseInput,
        WOperatorCondition
    )
from bulicommander.pktk.widgets.wlabelelide import WLabelElide
from bulicommander.pktk.widgets.wiodialog import (
        WDialogBooleanInput,
        WDialogMessage
    )
from bulicommander.pktk.widgets.wconsole import (
        WConsole,
        WConsoleType
    )
from bulicommander.pktk.widgets.worderedlist import OrderedItem
from bulicommander.pktk.widgets.wnodeeditor import (
        NodeEditorScene,
        NodeEditorNode,
        NodeEditorConnector,
        NodeEditorLink,
        NodeEditorNodeWidget
    )
from bulicommander.pktk.widgets.wcolorbutton import QEColor


from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# -----------------------------------------------------------------------------

class BCSearchFilesDialogBox(QDialog):
    """User interface to search files"""

    __PANEL_SEARCH_ENGINE = 0
    __PANEL_SEARCH_FROMPATH = 1
    __PANEL_SEARCH_FILEFILTERRULES = 2
    __PANEL_SEARCH_IMGFILTERRULES = 3
    __PANEL_SEARCH_SORTRULES = 4
    __PANEL_SEARCH_OUTPUTENGINE = 5

    __TAB_BASIC_SEARCH = 0
    __TAB_ADVANCED_SEARCH = 1
    __TAB_SEARCH_CONSOLE = 2

    __SEARCH_IN_PROGRESS_CANCEL=-1
    __SEARCH_IN_PROGRESS_NONE=0
    __SEARCH_IN_PROGRESS_SEARCH=1
    __SEARCH_IN_PROGRESS_SORTANDEXPORT=2


    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCSearchFilesDialogBox(title, uicontroller)
        db.show()

    @staticmethod
    def buildBCFileList(fileList, searchRulesAsDict, forTextOnly=False):
        """From a given search rule (provided as dictionnary) build and return
        a BCFileList object ready to use

        Return None if not able to parse dictionary properly



        Date/Time file filter when time is not checked ('dateOnly'=True)

                     | if date=2022-01-01
            Operator | Displayed condition              | Applied condition (BCFileRule)
            ---------+----------------------------------+--------------------------------------------------
            >        | >   2022-01-01                   | >   2022-01-01 00:00:00.0000
            >=       | >=  2022-01-01                   | >=  2022-01-01 00:00:00.0000
            <        | <   2022-01-01                   | <   2022-01-01 00:00:00.0000
            <=       | <=  2022-01-01                   | <=  2022-01-01 23:59:59.9999
            =        | >=  2022-01-01 and <= 2022-01-01 | >=  2022-01-01 00:00:00.0000 and <= 2022-01-01 23:59:59.9999
            !=       | <   2022-01-01 and >  2022-01-01 | <   2022-01-01 00:00:00.0000 and >  2022-01-01 23:59:59.9999
            between  | >=  2022-01-01 and <= 2022-01-01 | >=  2022-01-01 00:00:00.0000 and <= 2022-01-01 23:59:59.9999
            !between | <   2022-01-01 and >  2022-01-01 | <   2022-01-01 00:00:00.0000 and >  2022-01-01 23:59:59.9999

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

            if 'filePath' in filterRulesAsDict and filterRulesAsDict['filePath']['active']:
                if filterRulesAsDict['filePath']['ignoreCase']:
                    ignoreCase=re.I
                else:
                    ignoreCase=0

                # convert operator as regular expression
                if filterRulesAsDict['filePath']['operator'] in ('match', 'not match'):
                    ruleOperator=BCFileListRuleOperator(re.compile(filterRulesAsDict['filePath']['value'], ignoreCase),
                                                        filterRulesAsDict['filePath']['operator'],
                                                        BCFileListRuleOperatorType.REGEX)
                elif filterRulesAsDict['filePath']['operator'] in ('like', 'not like'):
                    ruleOperator=BCFileListRuleOperator(re.compile(re.escape(filterRulesAsDict['filePath']['value']).replace(r'\?', '.').replace(r'\*', '.*'), ignoreCase),
                                                        filterRulesAsDict['filePath']['operator'].replace('like', 'match'),
                                                        BCFileListRuleOperatorType.REGEX)
                else:
                    ruleOperator=BCFileListRuleOperator(re.compile(f"^{re.escape(filterRulesAsDict['filePath']['value'])}$", ignoreCase),
                                                        'match' if filterRulesAsDict['filePath']['operator']=='=' else 'not match',
                                                        BCFileListRuleOperatorType.REGEX)
                returned.setPath(ruleOperator)

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
                ruleType = BCFileListRuleOperatorType.DATETIME
                fmt='dt'
                if filterRulesAsDict['fileDate']['dateOnly']:
                    ruleType = BCFileListRuleOperatorType.DATE
                    fmt='d'

                if filterRulesAsDict['fileDate']['operator'] in ('between', 'not between'):
                    value=filterRulesAsDict['fileDate']['value']
                    value2=filterRulesAsDict['fileDate']['value2']+0.9999

                    ruleOperator=BCFileListRuleOperator((value, value2),
                                                        filterRulesAsDict['fileDate']['operator'],
                                                        ruleType,
                                                        (tsToStr(value, fmt),tsToStr(value2, fmt)))
                else:
                    value=filterRulesAsDict['fileDate']['value']
                    if filterRulesAsDict['fileDate']['operator']=='<=':
                        value+=0.9999

                    ruleOperator=BCFileListRuleOperator(value,
                                                        filterRulesAsDict['fileDate']['operator'],
                                                        ruleType,
                                                        tsToStr(value, fmt))

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
                if len(filterRulesAsDict['imageFormat']['value'])>0:
                    # if empty, consider it as not active
                    ruleOperator=BCFileListRuleOperator(filterRulesAsDict['imageFormat']['value'],
                                                        filterRulesAsDict['imageFormat']['operator'],
                                                        BCFileListRuleOperatorType.STRING,
                                                        [BCFileManagedFormat.translate(value) for value in filterRulesAsDict['imageFormat']['value']])

                    returned.setFormat(ruleOperator)

            if 'imageRatio' in filterRulesAsDict and filterRulesAsDict['imageRatio']['active']:
                if filterRulesAsDict['imageRatio']['operator'] in ('between', 'not between'):
                    ruleOperator=BCFileListRuleOperator((filterRulesAsDict['imageRatio']['value'], filterRulesAsDict['imageRatio']['value2']),
                                                        filterRulesAsDict['imageRatio']['operator'],
                                                        BCFileListRuleOperatorType.FLOAT,
                                                        (f"{filterRulesAsDict['imageRatio']['value']:.4f}",f"{filterRulesAsDict['imageRatio']['value2']:.4f}"))
                else:
                    ruleOperator=BCFileListRuleOperator(filterRulesAsDict['imageRatio']['value'],
                                                        filterRulesAsDict['imageRatio']['operator'],
                                                        BCFileListRuleOperatorType.FLOAT,
                                                        f"{filterRulesAsDict['imageRatio']['value']:.4f}")

                returned.setImageRatio(ruleOperator)

            if 'imagePixels' in filterRulesAsDict and filterRulesAsDict['imagePixels']['active']:
                if filterRulesAsDict['imagePixels']['operator'] in ('between', 'not between'):
                    ruleOperator=BCFileListRuleOperator((round(filterRulesAsDict['imagePixels']['value']*1000000), round(filterRulesAsDict['imagePixels']['value2']*1000000)),
                                                        filterRulesAsDict['imagePixels']['operator'],
                                                        BCFileListRuleOperatorType.INT,
                                                        (f"{filterRulesAsDict['imagePixels']['value']:.2f}MP",f"{filterRulesAsDict['imagePixels']['value2']:.2f}MP"))
                else:
                    ruleOperator=BCFileListRuleOperator(round(filterRulesAsDict['imagePixels']['value']*1000000),
                                                        filterRulesAsDict['imagePixels']['operator'],
                                                        BCFileListRuleOperatorType.INT,
                                                        f"{filterRulesAsDict['imagePixels']['value']:.2f}MP")

                returned.setImagePixels(ruleOperator)

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


        if not isinstance(fileList, BCFileList):
            raise EInvalidType("Given `fileList` must be a <BCFileList>")
        elif not isinstance(searchRulesAsDict, dict):
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
            return False

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

        fileList.clear()

        if not filterRules is None:
            fileList.addSearchRules(filterRules)

        for pathId in pathToLinks:
            fileList.addSearchPaths(BCFileListPath(nodeSearchPaths[pathId]['widget']["path"],
                                            nodeSearchPaths[pathId]['widget']["scanSubDirectories"],
                                            nodeSearchPaths[pathId]['widget']["scanHiddenFiles"],
                                            nodeSearchPaths[pathId]['widget']["scanManagedFilesOnly"],
                                            nodeSearchPaths[pathId]['widget']["scanManagedFilesBackup"]))

        return True

    def __init__(self, title, uicontroller, parent=None):
        super(BCSearchFilesDialogBox, self).__init__(parent)

        # dirty trick...
        self.__closed=False

        self.__inInit=True
        self.__title = title
        self.__uiController = uicontroller
        self.__fileNfo = self.__uiController.panel().files()

        self.__searchInProgress=BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_NONE
        self.__bcFileList=BCFileList()

        self.__currentFileBasic=None
        self.__currentFileAdvanced=None

        self.__currentSelectedNodeWidget=None

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcsearchfiles.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__initialise()
        self.setWindowTitle(self.__title)
        self.setModal(False)
        self.__inInit=False

    def __initialise(self):
        """Initialise user interface"""
        self.__uiController.bcWindowClosed.connect(self.close)

        self.tbBasicNewSearch.clicked.connect(self.__basicResetSearch)

        self.tbAdvancedNewSearch.clicked.connect(self.__advancedResetSearch)
        self.tbAdvancedAddPath.clicked.connect(self.__advancedAddPath)
        self.tbAdvancedAddFileFilter.clicked.connect(self.__advancedAddFileFilterRule)
        self.tbAdvancedAddImgFilter.clicked.connect(self.__advancedAddImgFilterRule)
        self.tbAdvancedAddFilterOperator.clicked.connect(self.__advancedAddFilterRuleOperator)
        self.tbAdvancedAddSortRules.clicked.connect(self.__advancedAddSortRules)
        self.tbAdvancedAddOutputEngine.clicked.connect(self.__advancedAddOutputEngine)
        self.tbAdvancedDeleteItems.clicked.connect(self.__advancedDelete)
        self.tbAdvancedZoomToFit.clicked.connect(self.wneAdvancedView.zoomToFit)
        self.tbAdvancedZoom1_1.clicked.connect(self.wneAdvancedView.resetZoom)

        actionBasicSearchSave=QAction(i18n("Save"), self)
        actionBasicSearchSave.triggered.connect(lambda: self.saveFile('basic'))
        actionBasicSearchSaveAs=QAction(i18n("Save as..."), self)
        actionBasicSearchSaveAs.triggered.connect(lambda: self.saveFile('basic', True))

        actionAdvancedSearchSave=QAction(i18n("Save"), self)
        actionAdvancedSearchSave.triggered.connect(lambda: self.saveFile('advanced'))
        actionAdvancedSearchSaveAs=QAction(i18n("Save as..."), self)
        actionAdvancedSearchSaveAs.triggered.connect(lambda: self.saveFile('advanced', True))

        menuBasicSearchSave = QMenu(self.tbBasicSearchSave)
        menuBasicSearchSave.addAction(actionBasicSearchSave)
        menuBasicSearchSave.addAction(actionBasicSearchSaveAs)
        self.tbBasicSearchSave.setMenu(menuBasicSearchSave)

        menuAdvancedSearchSave = QMenu(self.tbAdvancedSearchSave)
        menuAdvancedSearchSave.addAction(actionAdvancedSearchSave)
        menuAdvancedSearchSave.addAction(actionAdvancedSearchSaveAs)
        self.tbAdvancedSearchSave.setMenu(menuAdvancedSearchSave)

        self.tbAdvancedSearchSave.clicked.connect(lambda: self.saveFile('advanced'))
        self.tbAdvancedSearchOpen.clicked.connect(lambda: self.openFile('advanced'))
        self.tbBasicSearchSave.clicked.connect(lambda: self.saveFile('basic'))
        self.tbBasicSearchOpen.clicked.connect(lambda: self.openFile('basic'))

        self.pbClose.clicked.connect(self.close)
        self.pbSearch.clicked.connect(self.executeSearch)
        self.pbCancel.clicked.connect(self.__executeSearchCancel)

        self.twSearchModes.setCurrentIndex(0)
        self.twSearchModes.currentChanged.connect(self.__currentTabChanged)

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
        self.__scene.sceneModified.connect(self.__updateFileNameLabel)
        self.__scene.setFormatIdentifier("bulicommander-search-filter-advanced")

        self.wsffpAdvanced.modified.connect(self.__advancedFileFromPathChanged)
        self.wsffrAdvanced.modified.connect(self.__advancedFileFilterRuleChanged)
        self.wsifrAdvanced.modified.connect(self.__advancedImgFilterRuleChanged)
        self.wssrAdvanced.modified.connect(self.__advancedSortRuleChanged)
        self.wsoeAdvanced.modified.connect(self.__advancedOutputEngineChanged)

        self.wsoeAdvanced.setTitle(self.__title)
        self.wsoeAdvanced.setUiController(self.__uiController)

        self.wcExecutionConsole.setOptionShowGutter(False)
        self.wcExecutionConsole.appendLine(i18n('Not search executed yet'))
        self.wProgress.setVisible(False)

        self.__bcFileList.stepExecuted.connect(self.__executeSearchProcessSignals)

        self.wsffrBasic.modified.connect(self.__updateFileNameLabel)
        self.wsffpBasic.modified.connect(self.__updateFileNameLabel)
        self.wsifrBasic.modified.connect(self.__updateFileNameLabel)
        self.wssrBasic.modified.connect(self.__updateFileNameLabel)

        self.__basicResetSearch(True)
        self.__advancedResetSearch(True)
        self.__advancedSelectionChanged()

        self.__viewAdvSplitterPosition(BCSettings.get(BCSettingsKey.SESSION_SEARCHWINDOW_SPLITTER_POSITION))
        self.__viewWindowMaximized(BCSettings.get(BCSettingsKey.SESSION_SEARCHWINDOW_WINDOW_MAXIMIZED))
        self.__viewWindowGeometry(BCSettings.get(BCSettingsKey.SESSION_SEARCHWINDOW_WINDOW_GEOMETRY))
        self.__viewWindowActiveTab(BCSettings.get(BCSettingsKey.SESSION_SEARCHWINDOW_TAB_ACTIVE))

    def __allowClose(self):
        """Check if search window can be closed or not

        Return True if can be close, otherwise return False
        """
        if self.__closed:
            return True

        modified=False
        if self.twSearchModes.currentIndex()==BCSearchFilesDialogBox.__TAB_BASIC_SEARCH:
            if (self.wsffrBasic.isModified()
                or  self.wsffpBasic.isModified()
                or  self.wsifrBasic.isModified()
                or  self.wssrBasic.isModified()):
                modified=True
        elif self.twSearchModes.currentIndex()==BCSearchFilesDialogBox.__TAB_ADVANCED_SEARCH:
            if self.__scene.isModified():
                modified=True

        if modified:
            if WDialogBooleanInput.display(f"{self.__title}::{i18n('Close')}", i18n("<h1>A search definition has been modified</h1><p>Close without saving?")):
                return True
            return False
        return True

    def reject(self):
        """Dialog is closed"""
        if self.__allowClose():
            self.__closed=True
            self.done(0)

    def closeEvent(self, event):
        """Dialog is closed"""
        if not self.__allowClose():
            event.ignore()
            return

        self.__saveSettings()
        event.accept()
        self.__closed=True

    def __updateFileNameLabel(self):
        """Update file name in status bar according to current tab"""
        modified=''
        if self.twSearchModes.currentIndex()==BCSearchFilesDialogBox.__TAB_BASIC_SEARCH:
            if (self.wsffrBasic.isModified()
                or  self.wsffpBasic.isModified()
                or  self.wsifrBasic.isModified()
                or  self.wssrBasic.isModified()):
                modified=f" ({i18n('modified')})"

            if self.__currentFileBasic is None or self.__currentFileBasic=='':
                self.lblFileName.setText(f"[{i18n('Not saved')}]")
            else:
                self.lblFileName.setText(f"{self.__currentFileBasic}{modified}")
        elif self.twSearchModes.currentIndex()==BCSearchFilesDialogBox.__TAB_ADVANCED_SEARCH:
            if self.__scene.isModified():
                modified=f" ({i18n('modified')})"

            if self.__currentFileAdvanced is None or self.__currentFileAdvanced=='':
                self.lblFileName.setText(f"[{i18n('Not saved')}]")
            else:
                self.lblFileName.setText(f"{self.__currentFileAdvanced}{modified}")
        else:
            self.lblFileName.setText('')

    def __saveSettings(self):
        """Save current search window settings"""
        # note: for current tab, value is defined when tab is selected
        BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_SPLITTER_POSITION, self.sAdvTopBottomSplitter.sizes())
        BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_WINDOW_MAXIMIZED, self.isMaximized())
        if not self.isMaximized():
            # when maximized geometry is full screen geometry, then do it only if not in maximized
            BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_WINDOW_GEOMETRY, [self.geometry().x(), self.geometry().y(), self.geometry().width(), self.geometry().height()])

    def __viewAdvSplitterPosition(self, positions=None):
        """Set advanced tab splitter position

        Given `positions` is a list [<top size>,<bottom size>]
        If value is None, will define a default 80%-20%
        """
        if positions is None:
            positions = [800, 200]

        if not isinstance(positions, list) or len(positions) != 2:
            raise EInvalidValue('Given `positions` must be a list [t,b]')

        self.sAdvTopBottomSplitter.setSizes(positions)

        return positions

    def __viewWindowMaximized(self, maximized=False):
        """Set the window state"""
        if not isinstance(maximized, bool):
            raise EInvalidValue('Given `maximized` must be a <bool>')

        if maximized:
            # store current geometry now because after window is maximized, it's lost
            BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_WINDOW_GEOMETRY, [self.geometry().x(), self.geometry().y(), self.geometry().width(), self.geometry().height()])
            self.showMaximized()
        else:
            self.showNormal()

        return maximized

    def __viewWindowGeometry(self, geometry=[-1,-1,-1,-1]):
        """Set the window geometry

        Given `geometry` is a list [x,y,width,height] or a QRect()
        """
        if isinstance(geometry, QRect):
            geometry = [geometry.x(), geometry.y(), geometry.width(), geometry.height()]

        if not isinstance(geometry, list) or len(geometry)!=4:
            raise EInvalidValue('Given `geometry` must be a <list[x,y,w,h]>')

        rect = self.geometry()

        if geometry[0] >= 0:
            rect.setX(geometry[0])

        if geometry[1] >= 0:
            rect.setY(geometry[1])

        if geometry[2] >= 0:
            rect.setWidth(geometry[2])

        if geometry[3] >= 0:
            rect.setHeight(geometry[3])

        self.setGeometry(rect)

        return [self.geometry().x(), self.geometry().y(), self.geometry().width(), self.geometry().height()]

    def __viewWindowActiveTab(self, tabId='basic'):
        """Set the current tab"""
        if not isinstance(tabId, str):
            raise EInvalidValue('Given `tabId` must be a <str>')

        if tabId=='advanced':
            self.twSearchModes.setCurrentIndex(BCSearchFilesDialogBox.__TAB_ADVANCED_SEARCH)
        else:
            self.twSearchModes.setCurrentIndex(BCSearchFilesDialogBox.__TAB_BASIC_SEARCH)

    def __currentTabChanged(self, index):
        """Tab changed"""
        if self.__searchInProgress!=BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_NONE:
            self.pbSearch.setEnabled(False)
        else:
            self.pbSearch.setEnabled(index!=BCSearchFilesDialogBox.__TAB_SEARCH_CONSOLE)

            if index==BCSearchFilesDialogBox.__TAB_BASIC_SEARCH:
                BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_TAB_ACTIVE, 'basic')
            elif index==BCSearchFilesDialogBox.__TAB_ADVANCED_SEARCH:
                BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_TAB_ACTIVE, 'advanced')

            self.__updateFileNameLabel()

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
        removableNodes=0
        for selectedNode in selectedNodes:
            if selectedNode.isRemovable():
                removableNodes+=1

        self.tbAdvancedDeleteItems.setEnabled(removableNodes>0 or len(self.__scene.selectedLinks())>0)

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
        elif nbSelectedNodes==1 and isinstance(selectedNodes[0].widget(), BCNodeWSearchSortRule):
            self.__currentSelectedNodeWidget=selectedNodes[0].widget()
            self.wssrAdvanced.importFromDict(selectedNodes[0].serialize()['widget'])
            self.swAdvancedPanel.setCurrentIndex(BCSearchFilesDialogBox.__PANEL_SEARCH_SORTRULES)
        elif nbSelectedNodes==1 and isinstance(selectedNodes[0].widget(), BCNodeWSearchOutputEngine):
            self.__currentSelectedNodeWidget=selectedNodes[0].widget()
            self.wsoeAdvanced.importFromDict(selectedNodes[0].serialize()['widget'])
            self.swAdvancedPanel.setCurrentIndex(BCSearchFilesDialogBox.__PANEL_SEARCH_OUTPUTENGINE)
        else:
            # in all other case (None selected or more than one selected, or search engine selected)
            # display search engine panel
            self.__currentSelectedNodeWidget=None
            self.swAdvancedPanel.setCurrentIndex(BCSearchFilesDialogBox.__PANEL_SEARCH_ENGINE)
            self.__advancedSearchChanged()

    def __advancedSearchChanged(self, modified=None):
        """Search model has been modified"""
        if self.swAdvancedPanel.currentIndex()==BCSearchFilesDialogBox.__PANEL_SEARCH_ENGINE:
            self.__updateFileNameLabel()
            dataAsDict=self.__advancedExportConfig()
            if BCSearchFilesDialogBox.buildBCFileList(self.__bcFileList, dataAsDict, True):
                self.tbSearchDescription.setPlainText(self.__bcFileList.exportHQuery())

    def __advancedFileFromPathChanged(self):
        """Something has been modified, update node"""
        if self.__currentSelectedNodeWidget is None:
            return

        self.__currentSelectedNodeWidget.deserialize(self.wsffpAdvanced.exportAsDict()['widget'])
        self.__scene.setModified(True)

    def __advancedFileFilterRuleChanged(self):
        """Something has been modified, update node"""
        if self.__currentSelectedNodeWidget is None:
            return

        self.__currentSelectedNodeWidget.deserialize(self.wsffrAdvanced.exportAsDict()['widget'])
        self.__scene.setModified(True)

    def __advancedImgFilterRuleChanged(self):
        """Something has been modified, update node"""
        if self.__currentSelectedNodeWidget is None:
            return

        self.__currentSelectedNodeWidget.deserialize(self.wsifrAdvanced.exportAsDict()['widget'])
        self.__scene.setModified(True)

    def __advancedSortRuleChanged(self):
        """Something has been modified, update node"""
        if self.__currentSelectedNodeWidget is None:
            return

        self.__currentSelectedNodeWidget.deserialize(self.wssrAdvanced.exportAsDict()['widget'])
        self.__scene.setModified(True)

    def __advancedOutputEngineChanged(self):
        """Something has been modified, update node"""
        if self.__currentSelectedNodeWidget is None:
            return

        self.__currentSelectedNodeWidget.deserialize(self.wsoeAdvanced.exportAsDict()['widget'])
        self.__scene.setModified(True)

    def __advancedExportConfig(self):
        """Export current node schema"""
        return self.__scene.serialize()

    def __advancedResetSearch(self, force=False):
        """reset current advanced search"""
        if not force and self.wneAdvancedView.nodeScene().isModified():
            if not WDialogBooleanInput.display(f"{self.__title}::{i18n('Reset advanced search')}", i18n("Current search has been modified, do you confirm to reset to default values?")):
                return False

        self.__scene.clear()

        # instanciate default search engine
        nwSearchEngine=BCNodeWSearchEngine(self.__scene, i18n("Search engine"))

        self.wneAdvancedView.resetZoom()

        self.__scene.setModified(False)

        self.__currentFileAdvanced=None
        self.__updateFileNameLabel()

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

    def __advancedAddSortRules(self):
        """Add a BCNodeWSearchSortRule node"""
        position=self.__advancedCalculateNodePosition()

        nwFilterRuleOperator=BCNodeWSearchSortRule(self.__scene, i18n("Sort rules"))
        nwFilterRuleOperator.node().setPosition(position)
        nwFilterRuleOperator.node().setSelected(True, False)

    def __advancedAddOutputEngine(self):
        """Add a BCNodeWSearchOutputEngine node"""
        position=self.__advancedCalculateNodePosition()

        nwOutputEngine=BCNodeWSearchOutputEngine(self.__scene, i18n("Output engine"))
        nwOutputEngine.node().setPosition(position)
        nwOutputEngine.node().setSelected(True, False)

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
        idNodeWOutputEngine=QUuid.createUuid().toString()

        nodeFileFilterRule=self.wsffrBasic.exportAsDict()
        nodeImgFilterRule=self.wsifrBasic.exportAsDict()
        nodeFromPath=self.wsffpBasic.exportAsDict()
        nodeSortRules=self.wssrBasic.exportAsDict()

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
                        },
                      },
                      {
                        # Link between [SearchEngine] and [SortRules] is always present and hard-coded
                        "connect": {
                            "from": f"{idNodeWSearchEngine}:OutputResults",
                            "to": f"{nodeSortRules['properties']['id']}:InputSortRule"
                        }
                      },
                      {
                        # Link between [SortRules] and [OutputEngine] is always present and hard-coded
                        "connect": {
                            "from": f"{nodeSortRules['properties']['id']}:OutputSortRule",
                            "to": f"{idNodeWOutputEngine}:InputResults",
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
                                        },
                                        {
                                            "id": "OutputResults",
                                            "properties": {
                                                "direction": NodeEditorConnector.DIRECTION_OUTPUT,
                                                "location": NodeEditorConnector.LOCATION_BOTTOM_RIGHT
                                            }
                                        }
                                    ],
                            "widget": {"type": "BCNodeWSearchEngine"}
                        },
                        # sort rules is always provided with data from BCWSearchSortRules widget
                        nodeSortRules,
                        # search engine is always provided, and hard-coded
                        {
                            "properties": {
                                            "id": f"{idNodeWOutputEngine}",
                                            "title": i18n("Output engine")
                                        },
                            "connectors": [
                                        {
                                            "id": "InputResults",
                                            "properties": {
                                                "direction": NodeEditorConnector.DIRECTION_INPUT,
                                                "location": NodeEditorConnector.LOCATION_TOP_LEFT
                                            }
                                        }
                                    ],
                            "widget": {
                                        "type": "BCNodeWSearchOutputEngine",
                                        "outputProperties": {
                                            "target": 'aPanel',
                                            "documentExportInfo": {
                                                    'exportFormat': BCExportFormat.EXPORT_FMT_TEXT,
                                                    'exportFileName': '@clipboard',
                                                    'exportConfig': {}
                                                }
                                        }
                                }
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
        if not force and (self.wsffrBasic.isModified()
                      or  self.wsffpBasic.isModified()
                      or  self.wsifrBasic.isModified()
                      or  self.wssrBasic.isModified()):
            if not WDialogBooleanInput.display(f"{self.__title}::{i18n('Reset basic search')}", i18n("Current search has been modified, do you confirm to reset to default values?")):
                return False

        self.wsffrBasic.resetToDefault()
        self.wsffpBasic.resetToDefault()
        self.wsifrBasic.resetToDefault()
        self.wssrBasic.resetToDefault()

        self.__currentFileBasic=None
        self.__updateFileNameLabel()

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
                self.wcExecutionConsole.appendLine(f"""&nbsp;- {i18n('Scan directory')} #y#{informations[1]}#, {i18n('found files:')} #c#{informations[3]}#""")
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

            # infinite progress bar
            self.pbProgress.setValue(0)
            self.pbProgress.setMaximum(0)
            QApplication.processEvents()
        elif informations[0]==BCFileList.STEPEXECUTED_BUILD_RESULTS:
            # 0 => step identifier
            # 1 => total time duration (in seconds)
            self.wcExecutionConsole.append(f"""#g#{i18n('OK')}#""")
            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Build made in')}# #w#{informations[1]:0.4f}s##lk#)#*""")

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"#lk#...{i18n('Exporting results')}...#")

            # infinite progress bar
            self.pbProgress.setValue(0)
            self.pbProgress.setMaximum(0)
            QApplication.processEvents()
        elif informations[0]==BCFileList.STEPEXECUTED_PROGRESS_SORT:
            # 0 => step identifier
            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"""**{i18n('Sort results:')}** """)

            # infinite progress bar
            self.pbProgress.setValue(0)
            self.pbProgress.setMaximum(0)
            QApplication.processEvents()
        elif informations[0]==BCFileList.STEPEXECUTED_SORT_RESULTS:
            # 0 => step identifier
            # 1 => total time duration (in seconds)
            # 2 => list of <str>
            self.wcExecutionConsole.append(f"""#g#{i18n('OK')}#""")
            self.wcExecutionConsole.appendLine(f"""&nbsp;{i18n('Sorted by:')}""")
            for sortNfo in informations[2]:
                sortNfo=re.sub('^\[([^\]]+)\]', r'[##y#\1##c#]', sortNfo).replace(' ', '&nbsp;')
                self.wcExecutionConsole.appendLine(f"""&nbsp;. #c#{sortNfo}#""")

            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Sort made in')}# #w#{informations[1]:0.4f}s##lk#)#*""")
        elif informations[0]==BCFileList.STEPEXECUTED_CANCEL:
            # 0 => step identifier
            self.wcExecutionConsole.appendLine('')
            self.wcExecutionConsole.appendLine(f"""**#ly#Search cancelled!#**""", WConsoleType.WARNING)
            self.__searchInProgress=BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_CANCEL
        elif informations[0]==BCFileList.STEPEXECUTED_OUTPUT_RESULTS:
            # 0 => step identifier
            # 1 => total number of pages (-1 if no pages)
            # 2 => output file name (@clipboard if clipboard, @panel:ref if panel output)
            # 3 => output format
            self.wcExecutionConsole.appendLine("")

            asFormat=''
            if informations[3]==BCExportFormat.EXPORT_FMT_TEXT:
                asFormat=i18n("as #y#text#")
            elif informations[3]==BCExportFormat.EXPORT_FMT_TEXT_MD:
                asFormat=i18n("as #y#Markdown#")
            elif informations[3]==BCExportFormat.EXPORT_FMT_TEXT_CSV:
                asFormat=i18n("as #y#CSV#")
            elif informations[3]==BCExportFormat.EXPORT_FMT_DOC_PDF:
                asFormat=i18n("as #y#PDF# document")
            elif informations[3]==BCExportFormat.EXPORT_FMT_IMG_KRA:
                asFormat=i18n("as #y#Krita# document")
            elif informations[3]==BCExportFormat.EXPORT_FMT_IMG_PNG:
                asFormat=i18n("as #y#PNG# files sequence")
            elif informations[3]==BCExportFormat.EXPORT_FMT_IMG_JPG:
                asFormat=i18n("as #y#JPEG# files sequence")


            if informations[2]=='@clipboard':
                self.wcExecutionConsole.appendLine(f"""**{i18n(f'Export results {asFormat} to clipboard:')}** """)
            elif informations[2]=='@panel:a':
                self.wcExecutionConsole.appendLine(f"""**{i18n('Export results to active panel:')}** """)
            elif informations[2]=='@panel:l':
                self.wcExecutionConsole.appendLine(f"""**{i18n('Export results to left panel:')}** """)
            elif informations[2]=='@panel:r':
                self.wcExecutionConsole.appendLine(f"""**{i18n('Export results to right panel:')}** """)
            else:
                if informations[1]==-1:
                    self.wcExecutionConsole.appendLine(f"""**{i18n(f'Export results {asFormat} document:')}** """)
                else:
                    self.wcExecutionConsole.appendLine(f"""**{i18n(f'Export results {asFormat}:')}** """)

            self.pbProgress.setValue(0)
            if informations[1]==-1:
                # infinite progress bar
                self.pbProgress.setMaximum(0)
            else:
                self.pbProgress.setMaximum(informations[1])
            self.pbProgress.update()
            QApplication.processEvents()
        elif informations[0]==BCFileList.STEPEXECUTED_PROGRESS_OUTPUT:
            # 0 => step identifier
            # 1 => current pages (-1 if no pages)
            if informations[1]>-1:
                self.pbProgress.setValue(informations[1])
                self.pbProgress.update()
                QApplication.processEvents()
        elif informations[0]==BCFileList.STEPEXECUTED_FINISHED_OUTPUT:
            # 0 => step identifier
            # 1 => total time duration (in seconds)
            # 2 => output file name (@clipboard if clipboard, @panel:ref if panel output)
            # 3 => total number of pages (-1 if no pages)
            # 4 => output format
            self.wcExecutionConsole.append(f"""#g#{i18n('OK')}#""")

            pageName=i18n('Exported pages')
            if informations[4]==BCExportFormat.EXPORT_FMT_IMG_KRA:
                pageName=i18n('Exported layers')
            elif informations[4]==BCExportFormat.EXPORT_FMT_IMG_PNG:
                pageName=i18n('Exported files')
            elif informations[4]==BCExportFormat.EXPORT_FMT_IMG_JPG:
                pageName=i18n('Exported files')

            if not re.match("^@", informations[2]):
                self.wcExecutionConsole.appendLine(f"""&nbsp;{i18n('Exported file:')} #c#{informations[2]}#""")
            if informations[3]>0:
                self.wcExecutionConsole.appendLine(f"""&nbsp;{pageName} #c#{informations[3]}#""")

            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Export made in')}# #w#{informations[1]:0.4f}s##lk#)#*""")
            QApplication.processEvents()

    def __executeSearchCancel(self):
        """Cancel current search execution"""
        self.pbCancel.setEnabled(False)
        self.pbCancel.update()
        QApplication.processEvents()
        if self.__searchInProgress==BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_SEARCH:
            self.__bcFileList.cancelSearchExecution()
        else:
            self.__searchInProgress=BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_CANCEL

    def __executeSortAndExport(self, searchRulesAsDict):
        """Sort results and export

        Execute 'output engine' linked to 'search engine'

        Apply 'sort rules' linked to 'search engine' and for which at least,
        one 'output engine' is linked to
        Then, for each sort, execute 'output engine' linked to 'search engine'
        """
        def executeOutputEngine(outputEngineRules):
            # export current files results
            def exportStart(nbPages):
                self.__executeSearchProcessSignals([BCFileList.STEPEXECUTED_OUTPUT_RESULTS, nbPages, outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportFormat']])
                outputEngineRules['documentExportInfo']['exportPages']=nbPages

            def exportEnd():
                self.__executeSearchProcessSignals([BCFileList.STEPEXECUTED_FINISHED_OUTPUT, Stopwatch.duration("executeSortAndExport.export"), outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportPages'], outputEngineRules['documentExportInfo']['exportFormat']])

            def exportProgress(currentPage):
                self.__executeSearchProcessSignals([BCFileList.STEPEXECUTED_PROGRESS_OUTPUT, currentPage])

            if outputEngineRules['target']=='doc':
                # export as a document
                Stopwatch.start('executeSortAndExport.export')

                fileStats=self.__bcFileList.stats()
                filesNfo=[
                        [],
                        fileStats['nbDir'],
                        fileStats['nbKra'] + fileStats['nbOther'],
                        fileStats['nbKra'] + fileStats['nbOther'] + fileStats['nbDir'],
                        fileStats['nbKra'] + fileStats['nbOther'],
                        [],
                        fileStats['sizeKra'] + fileStats['sizeOther']
                    ]

                exportFiles=BCExportFiles(self.__uiController, filesNfo)
                exportFiles.exportStart.connect(exportStart)
                exportFiles.exportEnd.connect(exportEnd)
                exportFiles.exportProgress.connect(exportProgress)

                outputEngineRules['documentExportInfo']['exportConfig']['files']=self.__bcFileList.files()
                outputEngineRules['documentExportInfo']['exportConfig']['source']=i18n('Search query')

                if outputEngineRules['documentExportInfo']['exportFormat']==BCExportFormat.EXPORT_FMT_TEXT:
                    result=exportFiles.exportAsText(outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportConfig'])
                elif outputEngineRules['documentExportInfo']['exportFormat']==BCExportFormat.EXPORT_FMT_TEXT_MD:
                    result=exportFiles.exportAsTextMd(outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportConfig'])
                elif outputEngineRules['documentExportInfo']['exportFormat']==BCExportFormat.EXPORT_FMT_TEXT_CSV:
                    result=exportFiles.exportAsTextCsv(outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportConfig'])
                elif outputEngineRules['documentExportInfo']['exportFormat']==BCExportFormat.EXPORT_FMT_DOC_PDF:
                    result=exportFiles.exportAsDocumentPdf(outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportConfig'])
                elif outputEngineRules['documentExportInfo']['exportFormat']==BCExportFormat.EXPORT_FMT_IMG_KRA:
                    result=exportFiles.exportAsImageKra(outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportConfig'])
                elif outputEngineRules['documentExportInfo']['exportFormat']==BCExportFormat.EXPORT_FMT_IMG_PNG:
                    result=exportFiles.exportAsImageSeq(outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportConfig'], 'PNG')
                elif outputEngineRules['documentExportInfo']['exportFormat']==BCExportFormat.EXPORT_FMT_IMG_JPG:
                    result=exportFiles.exportAsImageSeq(outputEngineRules['documentExportInfo']['exportFileName'], outputEngineRules['documentExportInfo']['exportConfig'], 'JPEG')

                Stopwatch.stop('executeSortAndExport.export')

            else:
                # to panel
                outputEngineRules['documentExportInfo']['exportFileName']=f"@panel:{outputEngineRules['target'][0]}"
                Stopwatch.start('executeSortAndExport.export')
                exportStart(-1)

                if outputEngineRules['target'][0]=='a':
                    # active panel
                    if self.__uiController.panelId()==0:
                        searchResultId='searchresult:left'
                        panelId=0
                    else:
                        searchResultId='searchresult:right'
                        panelId=1
                elif outputEngineRules['target'][0]=='l':
                    searchResultId='searchresult:left'
                    panelId=0
                elif outputEngineRules['target'][0]=='r':
                    searchResultId='searchresult:right'
                    panelId=1

                self.__uiController.savedViews().set({searchResultId: [file.fullPathName() for file in self.__bcFileList.files()]})

                self.__uiController.commandGoTo(panelId, f"@{searchResultId}")

                Stopwatch.stop('executeSortAndExport.export')
                exportEnd()

        def executeSort(sortRules):
            # prepare and execute sort for file results
            txtAscending=f"[{i18n('Ascending')}]"
            txtDescending=f"[{i18n('Descending')}]"
            textMaxLen=1+max(len(txtAscending), len(txtDescending))

            txtAscending=f"{txtAscending:{textMaxLen}}"
            txtDescending=f"{txtDescending:{textMaxLen}}"

            sortNfoList=[]
            self.__executeSearchProcessSignals([BCFileList.STEPEXECUTED_PROGRESS_SORT])
            Stopwatch.start('executeSortAndExport.sort')
            self.__bcFileList.clearSortRules()
            for sortRule in sortRules['list']:
                if sortRule['checked']:
                    # need a conversion from BCWSearchSortRules.MAP_VALUE_LABEL and BCFileProperty
                    # as BCFile is more "generic" and BCWSearchSortRules is more oriented to image...
                    # maybe not a good thing, but currently prefer to keep it as is it
                    value=sortRule['value']
                    if value=='filePath':
                        value=BCFileProperty.PATH
                    elif value=='fileFullPathName':
                        value=BCFileProperty.FULL_PATHNAME
                    elif value=='imageFormat':
                        value=BCFileProperty.FILE_FORMAT
                    fileListSortRule=BCFileListSortRule(value, sortRule['ascending'])
                    self.__bcFileList.addSortRule(fileListSortRule)

                    if sortRule['ascending']:
                        sortNfoList.append(f"{txtAscending}{BCWSearchSortRules.MAP_VALUE_LABEL[sortRule['value']]}")
                    else:
                        sortNfoList.append(f"{txtDescending}{BCWSearchSortRules.MAP_VALUE_LABEL[sortRule['value']]}")
            self.__bcFileList.sortResults(sortRules['caseInsensitive'])
            Stopwatch.stop('executeSortAndExport.sort')
            self.__executeSearchProcessSignals([BCFileList.STEPEXECUTED_SORT_RESULTS,Stopwatch.duration("executeSortAndExport.sort"),sortNfoList])

        if self.__searchInProgress==BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_CANCEL:
            return

        self.__searchInProgress=BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_SORTANDEXPORT

        # need to parse dictionary to get references
        nodeSearchEngine=None
        nodeSearchSortRules={}
        nodeSearchOutputEngine={}

        for node in searchRulesAsDict['nodes']:
            if node['widget']['type']=='BCNodeWSearchEngine':
                nodeSearchEngine=node
            elif node['widget']['type'] == 'BCNodeWSearchOutputEngine':
                nodeSearchOutputEngine[node['properties']['id']]=node
            elif node['widget']['type']=='BCNodeWSearchSortRule':
                nodeSearchSortRules[node['properties']['id']]=node

        if nodeSearchEngine is None or (len(nodeSearchSortRules)==0 and len(nodeSearchOutputEngine)==0):
            # nothing to do...
            return False

        processOutputEngines=[]
        processSortRules=[]

        # rebuild links
        #   search engine --> output engine
        #   sort rules --> output engine
        for link in searchRulesAsDict['links']:
            linkTo, dummy=link['connect']['to'].split(':')
            linkFrom, dummy=link['connect']['from'].split(':')


            if linkTo in nodeSearchOutputEngine:
                # connection to output engine
                if linkFrom in nodeSearchSortRules:
                    # from a sort engine: add sort engine to process list
                    if not 'outputEngines' in nodeSearchSortRules[linkFrom]:
                        nodeSearchSortRules[linkFrom]['outputEngines']=[]
                        processSortRules.append(nodeSearchSortRules[linkFrom])
                    nodeSearchSortRules[linkFrom]['outputEngines'].append(nodeSearchOutputEngine[linkTo])
                elif linkFrom==nodeSearchEngine['properties']['id']:
                    # directly from search engine: add output engine to process list
                    processOutputEngines.append(nodeSearchOutputEngine[linkTo])

        # process direct output engines
        for outputEngine in processOutputEngines:
            if self.__searchInProgress==BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_CANCEL:
                self.__executeSearchProcessSignals([BCFileList.STEPEXECUTED_CANCEL])
                return
            executeOutputEngine(outputEngine['widget']['outputProperties'])

        # process sorts, then output engines
        for sortRule in processSortRules:
            # do sort...
            if self.__searchInProgress==BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_CANCEL:
                self.__executeSearchProcessSignals([BCFileList.STEPEXECUTED_CANCEL])
                return
            executeSort(sortRule['widget']['sortProperties'])
            for outputEngine in sortRule['outputEngines']:
                if self.__searchInProgress==BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_CANCEL:
                    self.__executeSearchProcessSignals([BCFileList.STEPEXECUTED_CANCEL])
                    return
                executeOutputEngine(outputEngine['widget']['outputProperties'])

    def __openFileBasic(self, fileName, title):
        """Open basic search file"""
        if (self.wsffrBasic.isModified()
            or  self.wsffpBasic.isModified()
            or  self.wsifrBasic.isModified()
            or  self.wssrBasic.isModified()):
            if not WDialogBooleanInput.display(title, i18n("Current search has been modified and will be lost, continue?")):
                return False

        try:
            with open(fileName, 'r') as fHandle:
                jsonAsStr=fHandle.read()
        except Exception as e:
            Debug.print("Can't open/read file {0}: {1}", fileName, f"{e}")
            return NodeEditorScene.IMPORT_FILE_CANT_READ

        try:
            jsonAsDict = json.loads(jsonAsStr, cls=JsonQObjectDecoder)
        except Exception as e:
            Debug.print("Can't parse file {0}: {1}", fileName, f"{e}")
            return NodeEditorScene.IMPORT_FILE_NOT_JSON

        if not "formatIdentifier" in jsonAsDict:
            Debug.print("Missing format identifier file {0}", fileName)
            return NodeEditorScene.IMPORT_FILE_MISSING_FORMAT_IDENTIFIER

        if jsonAsDict["formatIdentifier"]!="bulicommander-search-filter-basic":
            Debug.print("Invalid format identifier file {0}", fileName)
            return NodeEditorScene.IMPORT_FILE_INVALID_FORMAT_IDENTIFIER

        self.wsffrBasic.resetToDefault()
        self.wsffpBasic.resetToDefault()
        self.wsifrBasic.resetToDefault()
        self.wssrBasic.resetToDefault()

        if "nodes" in jsonAsDict:
            for node in jsonAsDict['nodes']:
                if "widget" in node and "type" in node["widget"]:
                    if node["widget"]["type"]=="BCNodeWSearchFromPath":
                        self.wsffpBasic.importFromDict(node["widget"])
                    elif node["widget"]["type"]=="BCNodeWSearchFileFilterRule":
                        self.wsffrBasic.importFromDict(node["widget"])
                    elif node["widget"]["type"]=="BCNodeWSearchImgFilterRule":
                        self.wsifrBasic.importFromDict(node["widget"])
                    elif node["widget"]["type"]=="BCNodeWSearchSortRule":
                        self.wssrBasic.importFromDict(node["widget"])

        BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_BASIC, fileName)
        self.__currentFileBasic=fileName
        self.__updateFileNameLabel()

    def __openFileAdvanced(self, fileName, title):
        """Open advanced search file"""
        if self.wneAdvancedView.nodeScene().isModified():
            if not WDialogBooleanInput.display(title, i18n("Current search has been modified and will be lost, continue?")):
                return False

        importResult=self.__scene.importFromFile(fileName)

        if importResult==NodeEditorScene.IMPORT_OK:
            self.__scene.setModified(False)
            BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_ADVANCED, fileName)
            self.__currentFileAdvanced=fileName
            self.__updateFileNameLabel()

        return importResult

    def __saveFileBasic(self, fileName):
        """Save basic search file"""
        toExport={
                'formatIdentifier': "bulicommander-search-filter-basic",
                'nodes': [
                        self.wsffpBasic.exportAsDict(True),
                        self.wsffrBasic.exportAsDict(True),
                        self.wsifrBasic.exportAsDict(True),
                        self.wssrBasic.exportAsDict(True)
                    ]
            }

        returned=NodeEditorScene.EXPORT_OK
        try:
            with open(fileName, 'w') as fHandle:
                fHandle.write(json.dumps(toExport, indent=4, sort_keys=True, cls=JsonQObjectEncoder))
        except Exception as e:
            Debug.print("Can't save file {0}: {1}", fileName, f"{e}")
            returned=NodeEditorScene.EXPORT_CANT_SAVE

        BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_BASIC, fileName)
        self.__currentFileBasic=fileName
        self.__updateFileNameLabel()

        return returned

    def __saveFileAdvanced(self, fileName):
        """Save advanced search file"""
        exportResult=self.__scene.exportToFile(fileName)

        if exportResult==NodeEditorScene.IMPORT_OK:
            self.__scene.setModified(False)
            BCSettings.set(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_ADVANCED, fileName)
            self.__currentFileAdvanced=fileName
            self.__updateFileNameLabel()

        return exportResult

    def executeSearch(self):
        """Execute basic/advanced search, according to current active tab"""
        if self.twSearchModes.currentIndex()==BCSearchFilesDialogBox.__TAB_BASIC_SEARCH:
            dataAsDict=self.__basicExportConfig()
        else:
            dataAsDict=self.__advancedExportConfig()

        if self.twSearchModes.currentIndex()==BCSearchFilesDialogBox.__TAB_BASIC_SEARCH:
            # for debug, to remove...
            #print("executeSearch", json.dumps(dataAsDict, indent=4, sort_keys=True))
            self.wneAdvancedView.nodeScene().deserialize(dataAsDict)
            self.wneAdvancedView.zoomToFit()

        self.__searchInProgress=BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_SEARCH
        self.wcExecutionConsole.clear()
        self.twSearchModes.setCurrentIndex(BCSearchFilesDialogBox.__TAB_SEARCH_CONSOLE)
        if BCSearchFilesDialogBox.buildBCFileList(self.__bcFileList, dataAsDict):
            self.pbProgress.setMinimum(0)
            self.pbProgress.setMaximum(0)
            self.pbProgress.setValue(0)
            self.wProgress.setVisible(True)

            self.twSearchModes.setTabEnabled(BCSearchFilesDialogBox.__TAB_BASIC_SEARCH, False)
            self.twSearchModes.setTabEnabled(BCSearchFilesDialogBox.__TAB_ADVANCED_SEARCH, False)
            self.pbClose.setEnabled(False)
            self.pbCancel.setEnabled(True)

            self.wcExecutionConsole.appendLine(f"""{i18n('Build search query:')} #g#{i18n('OK')}#""", WConsoleType.VALID)

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"#lk#...{i18n('Executing search')}...#")

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"""**{i18n('Scan directories:')}** """)

            self.__bcFileList.searchExecute(True, True, [
                BCFileList.STEPEXECUTED_SEARCH_FROM_PATHS,
                BCFileList.STEPEXECUTED_SEARCH_FROM_PATH,
                BCFileList.STEPEXECUTED_ANALYZE_METADATA,
                BCFileList.STEPEXECUTED_FILTER_FILES,
                BCFileList.STEPEXECUTED_BUILD_RESULTS,
                BCFileList.STEPEXECUTED_PROGRESS_ANALYZE,
                BCFileList.STEPEXECUTED_PROGRESS_FILTER
            ])

            # Even if BCFileList.execute can do sort, it's not used because only
            # one sort van be applied
            # Call to __executeSortAndExport is used instead to let the function
            # being able to manage more than one sort+linked exports
            self.__executeSortAndExport(dataAsDict)

            self.wcExecutionConsole.appendLine("")
            self.wcExecutionConsole.appendLine(f"#lk#...{i18n('Execution done')}...#")

            self.twSearchModes.setTabEnabled(BCSearchFilesDialogBox.__TAB_BASIC_SEARCH, True)
            self.twSearchModes.setTabEnabled(BCSearchFilesDialogBox.__TAB_ADVANCED_SEARCH, True)
            self.pbClose.setEnabled(True)

            self.wProgress.setVisible(False)
            self.__searchInProgress=BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_NONE
        else:
            self.wcExecutionConsole.appendLine(f"""{i18n('Build search query:')} #r#{i18n('KO')}#""", WConsoleType.ERROR)
            self.wcExecutionConsole.appendLine(f"""&nbsp;*#lk#({i18n('Current search definition is not valid')}#*""", WConsoleType.ERROR)

            self.wProgress.setVisible(False)
            self.__searchInProgress=BCSearchFilesDialogBox.__SEARCH_IN_PROGRESS_NONE

    def openFile(self, searchTab, fileName=None):
        """Open file designed by `fileName` to `searchTab`

        Value for `searchTab` can be 'basic' or 'advanced'

        If fileName is None, open dialog box with predefined last opened/saved file
        """
        if not searchTab in ('basic', 'advanced'):
            raise EInvalidValue("Given `searchTab` value is not valid")

        if fileName is None:
            if searchTab=='basic':
                fileName=BCSettings.get(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_BASIC)
            else:
                fileName=BCSettings.get(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_ADVANCED)

        if fileName is None:
            fileName=''


        if searchTab=='basic':
            title=i18n(f"{self.__title}::{i18n('Open basic search file definition')}")
            extension=i18n("BuliCommander Basic Search (*.bcbs)")
        else:
            title=i18n(f"{self.__title}::{i18n('Open advanced search file definition')}")
            extension=i18n("BuliCommander Advanced Search (*.bcas)")

        fileName, dummy = QFileDialog.getOpenFileName(self, title, fileName, extension)

        if fileName != '':
            if not os.path.isfile(fileName):
                openResult=NodeEditorScene.IMPORT_FILE_NOT_FOUND
            elif searchTab=='basic':
                openResult=self.__openFileBasic(fileName, title)
            else:
                openResult=self.__openFileAdvanced(fileName, title)

            if openResult==NodeEditorScene.IMPORT_OK:
                return True
            elif openResult==NodeEditorScene.IMPORT_FILE_NOT_FOUND:
                WDialogMessage.display(title, "<br>".join(
                    [i18n("<h1>Can't open file!</h1>"),
                     i18n("File not found!"),
                    ]))
            elif openResult==NodeEditorScene.IMPORT_FILE_CANT_READ:
                WDialogMessage.display(title, "<br>".join(
                    [i18n("<h1>Can't open file!</h1>"),
                     i18n("File can't be read!"),
                    ]))
            elif openResult in (NodeEditorScene.IMPORT_FILE_NOT_JSON,
                                NodeEditorScene.IMPORT_FILE_INVALID_FORMAT_IDENTIFIER,
                                NodeEditorScene.IMPORT_FILE_MISSING_FORMAT_IDENTIFIER,
                                NodeEditorScene.IMPORT_FILE_MISSING_SCENE_DEFINITION):
                WDialogMessage.display(title, "<br>".join(
                    [i18n("<h1>Can't open file!</h1>"),
                     i18n("Invalid file format!"),
                    ]))

        return False

    def saveFile(self, searchTab, saveAs=False, fileName=None):
        """Save current search to designed file name

        If fileName is None

        """
        if not searchTab in ('basic', 'advanced'):
            raise EInvalidValue("Given `searchTab` value is not valid")

        if searchTab=='basic':
            if fileName is None and not self.__currentFileBasic is None:
                # a file is currently opened
                fileName=self.__currentFileBasic
            else:
                fileName=BCSettings.get(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_BASIC)
                saveAs=True
        else:
            if fileName is None and not self.__currentFileAdvanced is None:
                # a file is currently opened
                fileName=self.__currentFileAdvanced
            else:
                fileName=BCSettings.get(BCSettingsKey.SESSION_SEARCHWINDOW_LASTFILE_ADVANCED)
                saveAs=True

        if fileName is None:
            fileName=''
            saveAs=True

        if searchTab=='basic':
            title=i18n(f"{self.__title}::{i18n('Save basic search file definition')}")
            extension=i18n("BuliCommander Basic Search (*.bcbs)")
        else:
            title=i18n(f"{self.__title}::{i18n('Save advanced search file definition')}")
            extension=i18n("BuliCommander Advanced Search (*.bcas)")

        if saveAs:
            fileName, dummy = QFileDialog.getSaveFileName(self, title, fileName, extension)
            if searchTab == 'basic' and re.search(r"\.bcbs", fileName) is None:
                fileName += ".bcbs"
            elif searchTab == 'advanced' and re.search(r"\.bcas", fileName) is None:
                fileName += ".bcas"

        if fileName != '':
            if searchTab=='basic':
                saveResult=self.__saveFileBasic(fileName)
            else:
                saveResult=self.__saveFileAdvanced(fileName)

            if saveResult==NodeEditorScene.EXPORT_OK:
                return True
            elif saveResult==NodeEditorScene.EXPORT_CANT_SAVE:
                WDialogMessage.display(title, i18n("<h1>Can't save file!</h1>"))

        return False



class BCWSearchWidget(QWidget):
    """Base widget for all BCWSearch* widgets"""
    modified=Signal()

    def __init__(self, uiFileName, parent=None):
        super(BCWSearchWidget, self).__init__(parent)

        uiFullPathFileName = os.path.join(os.path.dirname(__file__), 'resources', uiFileName)
        PyQt5.uic.loadUi(uiFullPathFileName, self)

        # flag to determinate if values has been modified
        self.__isModified=False
        self.__inUpdate=0

    def _setModified(self, value=True):
        """Set widget as modified"""
        self.__isModified=value

        if self.__inUpdate==0 and self.__isModified:
            self.modified.emit()

    def _startUpdate(self):
        """In an update, do not emit modification"""
        self.__inUpdate+=1

    def _endUpdate(self, modified=False):
        """End of update, emit modification if needed"""
        self.__inUpdate-=1
        if self.__inUpdate==0:
            self._setModified(modified)

    def isModified(self):
        """Return true if values has been modified"""
        return self.__isModified



class BCWSearchFileFromPath(BCWSearchWidget):
    """A widget to define search file from path source"""

    def __init__(self, parent=None):
        super(BCWSearchFileFromPath, self).__init__('bcwsearchfilefrompath.ui', parent)

        self.bcwpbBasicPath.setOptions(BCWPathBar.OPTION_SHOW_NONE)

        self._startUpdate()
        self.__initialise()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def __initialise(self):
        """Initialise widget interface"""
        # option checkbox
        self.bcwpbBasicPath.pathChanged.connect(lambda: self._setModified(True))
        self.cbSubDirScan.toggled.connect(lambda: self._setModified(True))
        self.cbManagedFilesOnlyScan.toggled.connect(lambda: self._setModified(True))
        self.cbManagedFilesBackupScan.toggled.connect(lambda: self._setModified(True))
        self.cbHiddenFilesScan.toggled.connect(lambda: self._setModified(True))

    def __setDefaultValues(self):
        """Initialise default values"""
        self.bcwpbBasicPath.setPath()
        self.cbSubDirScan.setChecked(True)
        self.cbManagedFilesOnlyScan.setChecked(True)
        self.cbManagedFilesBackupScan.setChecked(False)
        self.cbHiddenFilesScan.setChecked(False)

    def _setModified(self, value=True):
        """Set widget as modified"""
        self.cbManagedFilesBackupScan.setEnabled(self.cbManagedFilesOnlyScan.isChecked())
        super(BCWSearchFileFromPath, self)._setModified(value)

    def resetToDefault(self):
        """Reset to default values"""
        self._startUpdate()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def exportAsDict(self, setUnmodified=False):
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
                            "scanSubDirectories": self.cbSubDirScan.isChecked(),
                            "scanManagedFilesOnly": self.cbManagedFilesOnlyScan.isChecked(),
                            "scanManagedFilesBackup": self.cbManagedFilesBackupScan.isChecked(),
                            "scanHiddenFiles": self.cbHiddenFilesScan.isChecked(),
                        }
            }

        if setUnmodified:
            self._setModified(False)

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

        self._startUpdate()
        self.__setDefaultValues()

        if "path" in dataAsDict and isinstance(dataAsDict['path'], str):
            self.bcwpbBasicPath.setPath(dataAsDict['path'])

        if "scanSubDirectories" in dataAsDict and isinstance(dataAsDict['scanSubDirectories'], bool):
            self.cbSubDirScan.setChecked(dataAsDict['scanSubDirectories'])

        if "scanManagedFilesOnly" in dataAsDict and isinstance(dataAsDict['scanManagedFilesOnly'], bool):
            self.cbManagedFilesOnlyScan.setChecked(dataAsDict['scanManagedFilesOnly'])

        if "scanManagedFilesBackup" in dataAsDict and isinstance(dataAsDict['scanManagedFilesBackup'], bool):
            self.cbManagedFilesBackupScan.setChecked(dataAsDict['scanManagedFilesBackup'])

        if "scanHiddenFiles" in dataAsDict and isinstance(dataAsDict['scanHiddenFiles'], bool):
            self.cbHiddenFilesScan.setChecked(dataAsDict['scanHiddenFiles'])

        self._endUpdate()
        self._setModified(False)



class BCWSearchFileFilterRules(BCWSearchWidget):
    """A widget to define file filter rules"""

    def __init__(self, parent=None):
        super(BCWSearchFileFilterRules, self).__init__('bcwsearchfilefilterrules.ui', parent)

        self._startUpdate()
        self.__initialise()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def __initialise(self):
        """Initialise widget interface"""
        # option checkbox
        self.cbFileName.setMinimumHeight(self.woiFileName.minimumSizeHint().height())
        self.cbFilePath.setMinimumHeight(self.woiFilePath.minimumSizeHint().height())
        self.cbFileSize.setMinimumHeight(self.woiFileSize.minimumSizeHint().height())
        self.cbFileDtDate.setMinimumHeight(self.woiFileDtDate.minimumSizeHint().height())
        self.cbFileDtTime.setMinimumHeight(self.woiFileDtTime.minimumSizeHint().height())

        self.cbFileName.toggled.connect(self.__fileNameToggled)
        self.cbFilePath.toggled.connect(self.__filePathToggled)
        self.cbFileSize.toggled.connect(self.__fileSizeToggled)
        self.cbFileDtDate.toggled.connect(self.__fileDtDateToggled)
        self.cbFileDtTime.toggled.connect(self.__fileDtTimeToggled)

        self.__fileNameToggled(False)
        self.__filePathToggled(False)
        self.__fileSizeToggled(False)
        self.__fileDtTimeToggled(False)
        self.__fileDtDateToggled(False)

        # file name pattern
        self.woiFileName.operatorChanged.connect(lambda: self._setModified(True))
        self.woiFileName.setOperators([
                WOperatorType.OPERATOR_MATCH,
                WOperatorType.OPERATOR_NOT_MATCH,
                WOperatorType.OPERATOR_LIKE,
                WOperatorType.OPERATOR_NOT_LIKE
            ])
        self.woiFileName.valueChanged.connect(lambda: self._setModified(True))

        # file path pattern
        self.woiFilePath.operatorChanged.connect(lambda: self._setModified(True))
        self.woiFilePath.setOperators([
                WOperatorType.OPERATOR_MATCH,
                WOperatorType.OPERATOR_NOT_MATCH,
                WOperatorType.OPERATOR_LIKE,
                WOperatorType.OPERATOR_NOT_LIKE
            ])
        self.woiFilePath.valueChanged.connect(lambda: self._setModified(True))

        # file size
        self.woiFileSize.setMinimum(0)
        self.woiFileSize.setMaximum(999999999999.99)
        self.woiFileSize.setDecimals(2)
        self.woiFileSize.setSuffixLabel("Unit")
        self.woiFileSize.setSuffixList([('Kilobyte (kB)', 'kB'), ('Megabyte (MB)', 'MB'), ('Gigabytes (GB)', 'GB'),
                                        ('Kibibyte (KiB)', 'KiB'), ('Mebibyte (MiB)', 'MiB'), ('Gibibyte (GiB)', 'GiB')])
        self.woiFileSize.operatorChanged.connect(lambda: self._setModified(True))
        self.woiFileSize.valueChanged.connect(lambda: self._setModified(True))
        self.woiFileSize.value2Changed.connect(lambda: self._setModified(True))
        self.woiFileSize.suffixChanged.connect(lambda: self._setModified(True))

        # file date
        self.woiFileDtDate.setMinimum(0)
        self.woiFileDtDate.setMaximum(QDate.fromString("2099-12-31", "yyyy-MM-dd"))
        self.woiFileDtDate.operatorChanged.connect(lambda v: self.woiFileDtTime.setOperator(v))
        self.woiFileDtDate.operatorChanged.connect(lambda: self._setModified(True))
        self.woiFileDtDate.valueChanged.connect(lambda: self._setModified(True))
        self.woiFileDtDate.value2Changed.connect(lambda: self._setModified(True))

        self.woiFileDtTime.setOperatorEnabled(False)
        self.woiFileDtTime.setCheckRangeValues(False)
        self.woiFileDtTime.setMinimum(0)
        self.woiFileDtTime.setMaximum(QTime.fromString("23:59:59", "HH:mm:ss"))
        self.woiFileDtTime.valueChanged.connect(lambda: self._setModified(True))
        self.woiFileDtTime.value2Changed.connect(lambda: self._setModified(True))

    def __setDefaultValues(self):
        """Initialise default values"""
        self.cbFileName.setChecked(False)
        self.cbFilePath.setChecked(False)
        self.cbFileSize.setChecked(False)
        self.cbFileDtDate.setChecked(False)
        self.cbFileDtTime.setChecked(False)

        self.woiFileName.setValue("")
        self.woiFileName.setOperator(WOperatorType.OPERATOR_LIKE)
        self.woiFileName.setPredefinedConditionsLabel(i18n("Predefined name"))
        self.woiFileName.setPredefinedConditions([WOperatorCondition.fromFmtString(v) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_FILENAME)])
        self.cbFileNameIgnoreCase.setChecked(True)

        self.woiFilePath.setValue("")
        self.woiFilePath.setOperator(WOperatorType.OPERATOR_LIKE)
        self.woiFilePath.setPredefinedConditionsLabel(i18n("Predefined path"))
        self.woiFilePath.setPredefinedConditions([WOperatorCondition.fromFmtString(v) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_FILEPATH)])
        self.cbFilePathIgnoreCase.setChecked(True)

        self.woiFileSize.setValue(1.00)
        self.woiFileSize.setOperator(WOperatorType.OPERATOR_GE)
        self.woiFileSize.setPredefinedConditionsLabel(i18n("Predefined size"))
        self.woiFileSize.setPredefinedConditions([WOperatorCondition.fromFmtString(v, self.__convertToUnit) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_FILESIZE)])
        if BCSettings.get(BCSettingsKey.CONFIG_GLB_FILE_UNIT)==BCSettingsValues.FILE_UNIT_KIB:
            self.woiFileSize.setValue2(1024.00)
            self.woiFileSize.setSuffix('KiB')
        else:
            self.woiFileSize.setValue2(1000.00)
            self.woiFileSize.setSuffix('kB')

        dateTimeNow=QDateTime.currentDateTime()
        dateTimeYm1=QDateTime(dateTimeNow)
        dateTimeYm1.addYears(-1)
        self.woiFileDtDate.setValue(dateTimeYm1)
        self.woiFileDtDate.setValue2(dateTimeNow)
        self.woiFileDtDate.setOperator(WOperatorType.OPERATOR_BETWEEN)
        self.woiFileDtDate.setPredefinedConditionsLabel(i18n("Predefined date"))
        self.woiFileDtDate.setPredefinedConditions([WOperatorCondition.fromFmtString(v) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_FILEDATE)])

    def _setModified(self, value=True):
        """Set widget as modified"""
        self.woiFileDtTime.setCheckRangeValues(self.woiFileDtDate.value()==self.woiFileDtDate.value2())
        super(BCWSearchFileFilterRules, self)._setModified(value)

    def __fileNameToggled(self, checked):
        """Checkbox 'file name' has been toggled"""
        self.woiFileName.setEnabled(checked)
        self.woiFileName.setVisible(checked)
        self.cbFileNameIgnoreCase.setEnabled(checked)
        self.cbFileNameIgnoreCase.setVisible(checked)
        self._setModified()

    def __filePathToggled(self, checked):
        """Checkbox 'file name' has been toggled"""
        self.woiFilePath.setEnabled(checked)
        self.woiFilePath.setVisible(checked)
        self.cbFilePathIgnoreCase.setEnabled(checked)
        self.cbFilePathIgnoreCase.setVisible(checked)
        self._setModified()

    def __fileSizeToggled(self, checked):
        """Checkbox 'file size' has been toggled"""
        self.woiFileSize.setEnabled(checked)
        self.woiFileSize.setVisible(checked)
        self._setModified()

    def __fileDtDateToggled(self, checked):
        """Checkbox 'file date' has been toggled"""
        self.woiFileDtDate.setEnabled(checked)
        self.woiFileDtDate.setVisible(checked)
        self.cbFileDtTime.setEnabled(checked)
        self.woiFileDtTime.setVisible(checked and self.cbFileDtTime.isChecked())
        self._setModified()

    def __fileDtTimeToggled(self, checked):
        """Checkbox 'file time' has been toggled"""
        self.woiFileDtTime.setEnabled(checked and self.cbFileDtTime.isEnabled())
        self.woiFileDtTime.setVisible(checked and self.cbFileDtTime.isEnabled())
        self._setModified()

    def __convertToUnit(self, value, input):
        """Convert given value (in bytes) to unit defined in given input (here input=woiFileSize)"""
        unit=input.suffix().lower()
        if unit == 'gib':
            return value/1073741824
        elif unit == 'mib':
            return value/1048576
        elif unit == 'kib':
            return value/1024
        elif unit == 'gb':
            return value/1000000000
        elif unit == 'mb':
            return value/1000000
        elif unit == 'kb':
            return value/1000
        else:
            return value

    def resetToDefault(self):
        """Reset to default values"""
        self._startUpdate()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def exportAsDict(self, setUnmodified=False):
        """Export widget configuration as dictionnary"""
        dt1=self.woiFileDtDate.value()
        dt2=self.woiFileDtDate.value2()

        if self.cbFileDtTime.isEnabled() and self.cbFileDtTime.isChecked():
            # use time from input fields
            dt1+=self.woiFileDtTime.value()
            dt2+=self.woiFileDtTime.value2()

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
                            "filePath": {
                                    "active": self.cbFilePath.isChecked(),
                                    "operator": self.woiFilePath.operator(),
                                    "value": self.woiFilePath.value(),
                                    "ignoreCase": (self.cbFilePathIgnoreCase.isChecked() and self.cbFilePathIgnoreCase.isVisible()),
                                },
                            "fileSize": {
                                    "active": self.cbFileSize.isChecked(),
                                    "operator": self.woiFileSize.operator(),
                                    "value": self.woiFileSize.value(),
                                    "value2": self.woiFileSize.value2(),
                                    "unit": self.woiFileSize.suffix()
                                },
                            "fileDate": {
                                    "active": self.cbFileDtDate.isChecked(),
                                    "dateOnly": not self.cbFileDtTime.isChecked(),
                                    "operator": self.woiFileDtDate.operator(),
                                    "value": dt1,
                                    "value2": dt2
                                }
                        }
            }

        if setUnmodified:
            self._setModified(False)

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
                "filePath": {
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

        self._startUpdate()
        self.__setDefaultValues()

        if "fileName" in dataAsDict and isinstance(dataAsDict['fileName'], dict):
            self.cbFileName.setChecked(dataAsDict['fileName']['active'])
            self.cbFileNameIgnoreCase.setChecked(dataAsDict['fileName']['ignoreCase'])
            self.woiFileName.setValue(dataAsDict['fileName']['value'])
            self.woiFileName.setOperator(dataAsDict['fileName']['operator'])

        if "filePath" in dataAsDict and isinstance(dataAsDict['filePath'], dict):
            self.cbFilePath.setChecked(dataAsDict['filePath']['active'])
            self.cbFilePathIgnoreCase.setChecked(dataAsDict['filePath']['ignoreCase'])
            self.woiFilePath.setValue(dataAsDict['filePath']['value'])
            self.woiFilePath.setOperator(dataAsDict['filePath']['operator'])

        if "fileSize" in dataAsDict and isinstance(dataAsDict['fileSize'], dict):
            self.cbFileSize.setChecked(dataAsDict['fileSize']['active'])
            self.woiFileSize.setValue(dataAsDict['fileSize']['value'])
            self.woiFileSize.setValue2(dataAsDict['fileSize']['value2'])
            self.woiFileSize.setOperator(dataAsDict['fileSize']['operator'])
            self.woiFileSize.setSuffix(dataAsDict['fileSize']['unit'])

        if "fileDate" in dataAsDict and isinstance(dataAsDict['fileDate'], dict):
            dt1=QDateTime.fromMSecsSinceEpoch(1000*dataAsDict['fileDate']['value'])
            dt2=QDateTime.fromMSecsSinceEpoch(1000*dataAsDict['fileDate']['value2'])

            tt1=dt1.time().msecsSinceStartOfDay()
            tt2=dt2.time().msecsSinceStartOfDay()

            self.cbFileDtDate.setChecked(dataAsDict['fileDate']['active'])
            self.woiFileDtDate.setValue(dataAsDict['fileDate']['value'])
            self.woiFileDtDate.setValue2(dataAsDict['fileDate']['value2'])
            self.woiFileDtDate.setOperator(dataAsDict['fileDate']['operator'])
            self.cbFileDtTime.setChecked(not dataAsDict['fileDate']['dateOnly'])

            if self.cbFileDtDate.isChecked() and self.cbFileDtTime.isChecked():
                # time is defined, then activate time input
                self.woiFileDtTime.setValue(tt1/1000)
                self.woiFileDtTime.setValue2(tt2/1000)

        self._endUpdate()
        self._setModified(False)



class BCWSearchImgFilterRules(BCWSearchWidget):
    """A widget to define image filter rules"""
    modified=Signal()

    def __init__(self, parent=None):
        super(BCWSearchImgFilterRules, self).__init__('bcwsearchimgfilterrules.ui', parent)

        self._startUpdate()
        self.__initialise()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def __initialise(self):
        """Initialise widget interface"""
        # option checkbox
        self.cbImageFormat.setMinimumHeight(self.woiImageFormat.minimumSizeHint().height())
        self.cbImageWidth.setMinimumHeight(self.woiImageWidth.minimumSizeHint().height())
        self.cbImageHeight.setMinimumHeight(self.woiImageHeight.minimumSizeHint().height())
        self.cbImageRatio.setMinimumHeight(self.woiImageRatio.minimumSizeHint().height())
        self.cbImagePixels.setMinimumHeight(self.woiImagePixels.minimumSizeHint().height())

        self.cbImageFormat.toggled.connect(self.__imageFormatToggled)
        self.cbImageWidth.toggled.connect(self.__imageWidthToggled)
        self.cbImageHeight.toggled.connect(self.__imageHeightToggled)
        self.cbImageRatio.toggled.connect(self.__imageRatioToggled)
        self.cbImagePixels.toggled.connect(self.__imagePixelsToggled)

        self.__imageFormatToggled(False)
        self.__imageWidthToggled(False)
        self.__imageHeightToggled(False)
        self.__imageRatioToggled(False)
        self.__imagePixelsToggled(False)

        # image format
        # (exclude JPEG as JPG is already in list)
        self.woiImageFormat.tagInput().setAvailableTags([(imageFormat, BCFileManagedFormat.translate(imageFormat)) for imageFormat in BCFileManagedFormat.list() if imageFormat!=BCFileManagedFormat.JPEG] )
        self.woiImageFormat.setPredefinedConditionsLabel(i18n("Predefined format"))
        self.woiImageFormat.setPredefinedConditions([WOperatorCondition.fromFmtString(v) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGFORMAT)])
        self.woiImageFormat.operatorChanged.connect(lambda: self._setModified(True))
        self.woiImageFormat.valueChanged.connect(lambda: self._setModified(True))

        # file image width
        self.woiImageWidth.setMinimum(1)
        self.woiImageWidth.setMaximum(9999999)
        self.woiImageWidth.setSuffix('px')
        self.woiImageWidth.setPredefinedConditionsLabel(i18n("Predefined width"))
        self.woiImageWidth.setPredefinedConditions([WOperatorCondition.fromFmtString(v) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGWIDTH)])
        self.woiImageWidth.operatorChanged.connect(lambda: self._setModified(True))
        self.woiImageWidth.valueChanged.connect(lambda: self._setModified(True))
        self.woiImageWidth.value2Changed.connect(lambda: self._setModified(True))

        # file image height
        self.woiImageHeight.setMinimum(1)
        self.woiImageHeight.setMaximum(9999999)
        self.woiImageHeight.setSuffix('px')
        self.woiImageHeight.setPredefinedConditionsLabel(i18n("Predefined height"))
        self.woiImageHeight.setPredefinedConditions([WOperatorCondition.fromFmtString(v) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGHEIGHT)])
        self.woiImageHeight.operatorChanged.connect(lambda: self._setModified(True))
        self.woiImageHeight.valueChanged.connect(lambda: self._setModified(True))
        self.woiImageHeight.value2Changed.connect(lambda: self._setModified(True))

        # file image ratio
        self.woiImageRatio.setMinimum(0.0001)
        self.woiImageRatio.setMaximum(9999.9999)
        self.woiImageRatio.setDecimals(4)
        self.woiImageRatio.setPredefinedConditionsLabel(i18n("Predefined aspect ratio"))
        self.woiImageRatio.setPredefinedConditions([WOperatorCondition.fromFmtString(v) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGRATIO)])
        self.woiImageRatio.operatorChanged.connect(lambda: self._setModified(True))
        self.woiImageRatio.valueChanged.connect(lambda: self._setModified(True))
        self.woiImageRatio.value2Changed.connect(lambda: self._setModified(True))

        # file image pixels
        self.woiImagePixels.setMinimum(0.01)
        self.woiImagePixels.setMaximum(9999.99)
        self.woiImagePixels.setDecimals(2)
        self.woiImagePixels.setSuffix('MP')
        self.woiImagePixels.setPredefinedConditionsLabel(i18n("Predefined pixel sizes"))
        self.woiImagePixels.setPredefinedConditions([WOperatorCondition.fromFmtString(v) for v in BCSettings.get(BCSettingsKey.CONFIG_SEARCHFILES_PREDEFINED_IMGPIXELS)])
        self.woiImagePixels.operatorChanged.connect(lambda: self._setModified(True))
        self.woiImagePixels.valueChanged.connect(lambda: self._setModified(True))
        self.woiImagePixels.value2Changed.connect(lambda: self._setModified(True))

    def __setDefaultValues(self):
        """Initialise default values"""
        self.cbImageFormat.setChecked(False)
        self.cbImageWidth.setChecked(False)
        self.cbImageHeight.setChecked(False)

        self.woiImageFormat.setValue([])

        self.woiImageWidth.setValue(320)
        self.woiImageWidth.setValue2(1920)
        self.woiImageWidth.setOperator(WOperatorType.OPERATOR_GE)

        self.woiImageHeight.setValue(200)
        self.woiImageHeight.setValue2(1080)
        self.woiImageHeight.setOperator(WOperatorType.OPERATOR_GE)

        self.woiImageRatio.setValue(1)
        self.woiImageRatio.setValue2(1)
        self.woiImageRatio.setOperator(WOperatorType.OPERATOR_GT)

        self.woiImagePixels.setValue(1)
        self.woiImagePixels.setValue2(10)
        self.woiImagePixels.setOperator(WOperatorType.OPERATOR_GE)

    def __imageFormatToggled(self, checked):
        """Checkbox 'file type' has been toggled"""
        self._setModified()
        self.woiImageFormat.setEnabled(checked)
        self.woiImageFormat.setVisible(checked)

    def __imageWidthToggled(self, checked):
        """Checkbox 'file img width' has been toggled"""
        self._setModified()
        self.woiImageWidth.setEnabled(checked)
        self.woiImageWidth.setVisible(checked)

    def __imageHeightToggled(self, checked):
        """Checkbox 'file img height' has been toggled"""
        self._setModified()
        self.woiImageHeight.setEnabled(checked)
        self.woiImageHeight.setVisible(checked)

    def __imageRatioToggled(self, checked):
        """Checkbox 'file img ratio' has been toggled"""
        self._setModified()
        self.woiImageRatio.setEnabled(checked)
        self.woiImageRatio.setVisible(checked)

    def __imagePixelsToggled(self, checked):
        """Checkbox 'file img pixels' has been toggled"""
        self._setModified()
        self.woiImagePixels.setEnabled(checked)
        self.woiImagePixels.setVisible(checked)

    def resetToDefault(self):
        """Reset to default values"""
        self._startUpdate()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def exportAsDict(self, setUnmodified=False):
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
                                    "operator": self.woiImageFormat.operator(),
                                    "value": self.woiImageFormat.value()
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
                                },
                            "imageRatio": {
                                    "active": self.cbImageRatio.isChecked(),
                                    "operator": self.woiImageRatio.operator(),
                                    "value": self.woiImageRatio.value(),
                                    "value2": self.woiImageRatio.value2()
                                },
                            "imagePixels": {
                                    "active": self.cbImagePixels.isChecked(),
                                    "operator": self.woiImagePixels.operator(),
                                    "value": self.woiImagePixels.value(),
                                    "value2": self.woiImagePixels.value2()
                                }
                        }
            }

        if setUnmodified:
            self._setModified(False)

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
                    "active": true
                }
            }
        """
        if not isinstance(dataAsDict, dict):
            raise EInvalidType("Given `dataAsDict` must be a <dict>")
        elif not ("type" in dataAsDict and dataAsDict["type"]=="BCNodeWSearchImgFilterRule"):
            raise EInvalidValue("Given `dataAsDict` must contains key 'type' with value 'BCNodeWSearchImgFilterRule'")

        self._startUpdate()
        self.__setDefaultValues()

        if "imageFormat" in dataAsDict and isinstance(dataAsDict['imageFormat'], dict):
            self.cbImageFormat.setChecked(dataAsDict['imageFormat']['active'])
            self.woiImageFormat.setValue(dataAsDict['imageFormat']['value'])

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

        if "imageRatio" in dataAsDict and isinstance(dataAsDict['imageRatio'], dict):
            self.cbImageRatio.setChecked(dataAsDict['imageRatio']['active'])
            self.woiImageRatio.setValue(dataAsDict['imageRatio']['value'])
            self.woiImageRatio.setValue2(dataAsDict['imageRatio']['value2'])
            self.woiImageRatio.setOperator(dataAsDict['imageRatio']['operator'])

        if "imagePixels" in dataAsDict and isinstance(dataAsDict['imagePixels'], dict):
            self.cbImagePixels.setChecked(dataAsDict['imagePixels']['active'])
            self.woiImagePixels.setValue(dataAsDict['imagePixels']['value'])
            self.woiImagePixels.setValue2(dataAsDict['imagePixels']['value2'])
            self.woiImagePixels.setOperator(dataAsDict['imagePixels']['operator'])

        self._endUpdate()
        self._setModified(False)



class BCWSearchSortRules(BCWSearchWidget):
    """A widget to define sort rules"""

    MAP_VALUE_LABEL={
            'fileFullPathName': i18n('Full path/name'),
            'filePath': i18n('File path'),
            'fileName': i18n('File name'),
            'fileSize': i18n('File size'),
            'fileDate': i18n('File date'),
            'imageFormat': i18n('Image format'),
            'imageWidth': i18n('Image width'),
            'imageHeight': i18n('Image height'),
            'imageRatio': i18n('Image ratio'),
            'imagePixels': i18n('Image pixels')
        }

    @staticmethod
    def getDefaultList():
        """return a default sort properties list"""
        return [
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['fileFullPathName'], 'fileFullPathName', False, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['filePath'], 'filePath', True, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['fileName'], 'fileName', True, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['fileSize'], 'fileSize', False, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['fileDate'], 'fileDate', False, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['imageFormat'], 'imageFormat', False, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['imageWidth'], 'imageWidth', False, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['imageHeight'], 'imageHeight', False, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['imageRatio'], 'imageRatio', False, True),
                OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL['imagePixels'], 'imagePixels', False, True)
            ]

    def __init__(self, parent=None):
        super(BCWSearchSortRules, self).__init__('bcwsearchsortrules.ui', parent)

        self._startUpdate()
        self.__initialise()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def __initialise(self):
        """Initialise widget interface"""
        # option checkbox
        self.cbPropertiesSortCaseInsensitive.toggled.connect(lambda: self._setModified(True))
        self.lwPropertiesSortList.itemOrderChanged.connect(lambda: self._setModified(True))
        self.lwPropertiesSortList.itemChanged.connect(lambda: self._setModified(True))

    def __setDefaultValues(self):
        """Initialise default values"""
        self.cbPropertiesSortCaseInsensitive.setChecked(True)
        self.lwPropertiesSortList.clear()
        self.lwPropertiesSortList.addItems(BCWSearchSortRules.getDefaultList())

    def resetToDefault(self):
        """Reset to default values"""
        self._startUpdate()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def exportAsDict(self, setUnmodified=False):
        """Export widget configuration as dictionnary"""
        returned={
                "properties": {
                                "id": QUuid.createUuid().toString(),
                                "title": i18n("Sort condition")
                            },
                "connectors": [
                            {
                                "id": "InputSortRule",
                                "properties": {
                                    "direction": NodeEditorConnector.DIRECTION_INPUT,
                                    "location": NodeEditorConnector.LOCATION_TOP_LEFT
                                }
                            },
                            {
                                "id": "OutputSortRule",
                                "properties": {
                                    "direction": NodeEditorConnector.DIRECTION_OUTPUT,
                                    "location": NodeEditorConnector.LOCATION_BOTTOM_RIGHT
                                }
                            }
                        ],
                "widget": {
                            "type": "BCNodeWSearchSortRule",
                            "sortProperties": {
                                "list":[{
                                        "value": orderedItem.value(),
                                        "checked": orderedItem.checked(),
                                        "ascending": orderedItem.isSortAscending()
                                        } for orderedItem in self.lwPropertiesSortList.items(False)],
                                "caseInsensitive": self.cbPropertiesSortCaseInsensitive.isChecked()
                            }
                    }
            }

        if setUnmodified:
            self._setModified(False)

        return returned

    def importFromDict(self, dataAsDict):
        """Import widget configuration from dictionnary

        Note: only "widget" key content is expected for input


        Example of expected dictionary:
            "widget": {
                "type": "BCWSearchSortRules",
                "sortProperties": [],
                "sortCaseInsensitive": true
            }
        """
        if not isinstance(dataAsDict, dict):
            raise EInvalidType("Given `dataAsDict` must be a <dict>")
        elif not ("type" in dataAsDict and dataAsDict["type"]=="BCNodeWSearchSortRule"):
            raise EInvalidValue("Given `dataAsDict` must contains key 'type' with value 'BCNodeWSearchSortRule'")

        self._startUpdate()
        self.__setDefaultValues()

        if "sortProperties" in dataAsDict and isinstance(dataAsDict['sortProperties'], dict):
            self.cbPropertiesSortCaseInsensitive.setChecked(dataAsDict['sortProperties']['caseInsensitive'])

            # build list of properties
            # need to check is given properties are valid
            validatedList=[]
            validatedProperties=[]
            for properties in dataAsDict['sortProperties']['list']:
                if properties["value"] in BCWSearchSortRules.MAP_VALUE_LABEL:
                    validatedList.append(OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL[properties["value"]], properties["value"], properties["checked"], properties["ascending"]))
                    validatedProperties.append(properties["value"])

            if len(validatedList)<len(BCWSearchSortRules.MAP_VALUE_LABEL):
                # some properties are missing...
                # search them an add to list
                for properties in self.lwPropertiesSortList.items(False):
                    if not properties.value() in validatedProperties:
                        validatedList.append(OrderedItem(BCWSearchSortRules.MAP_VALUE_LABEL[properties.value()], properties.value(), properties.checked(), properties.isSortAscending()))

            self.lwPropertiesSortList.clear()
            self.lwPropertiesSortList.addItems(validatedList)

        self._endUpdate()
        self._setModified(False)



class BCWSearchOutputEngine(BCWSearchWidget):
    """A widget to define output engine"""

    OUTPUT_TARGET={
            "aPanel": i18n("Active panel"),
            "lPanel": i18n("Left panel"),
            "rPanel": i18n("Right panel"),
            "doc": i18n("Document"),
        }

    def __init__(self, parent=None):
        super(BCWSearchOutputEngine, self).__init__('bcwsearchoutputengine.ui', parent)

        self.__title=''
        self.__uiController=None

        # document settings informations
        # set default minimal keys
        # all other keys will be defined dynamically from BCExportFilesDialogBox
        # (or when imported from dict) according to defined export format
        self.__documentExportInfo={
                'exportFormat': BCExportFormat.EXPORT_FMT_TEXT,
                'exportFileName': '@clipboard',
                'exportConfig': {}
            }

        self._startUpdate()
        self.__initialise()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def __initialise(self):
        """Initialise widget interface"""
        self.cbOutputTarget.addItem(BCWSearchOutputEngine.OUTPUT_TARGET['aPanel'], "aPanel")
        self.cbOutputTarget.addItem(BCWSearchOutputEngine.OUTPUT_TARGET['lPanel'], "lPanel")
        self.cbOutputTarget.addItem(BCWSearchOutputEngine.OUTPUT_TARGET['rPanel'], "rPanel")
        self.cbOutputTarget.addItem(BCWSearchOutputEngine.OUTPUT_TARGET['doc'], "doc")
        self.cbOutputTarget.currentIndexChanged.connect(self.__cbOutputTargetChanged)

        self.wTgtDoc.setVisible(False)
        self.lblTgtDocFmtValue.setText('')
        self.leTgtDocFileName.setText('')
        self.pbTgtDocConfigure.clicked.connect(self.__pbTgtDocConfigureClicked)

    def __setDefaultValues(self):
        """Initialise default values"""
        self.__setOutputTarget('aPanel')
        self.__isModified=False

    def __cbOutputTargetChanged(self, index):
        """Current output target has been modified"""
        self.__setOutputTarget(self.cbOutputTarget.currentData())
        self._setModified(True)

    def __pbTgtDocConfigureClicked(self):
        """Edit current 'document output' settings"""
        returned=BCExportFilesDialogBox.openAsExportConfig(self.__title, self.__uiController, self.__documentExportInfo)
        if not returned is None:
            # apply returned configuration
            self.__documentExportInfo=returned
            # update view
            self.__setOutputTarget('doc')
            self._setModified(True)

    def __setOutputTarget(self, value):
        """Define output target format"""
        if value in ('aPanel', 'lPanel', 'rPanel'):
            if value == 'aPanel':
                self.cbOutputTarget.setCurrentIndex(0)
            elif value == 'lPanel':
                self.cbOutputTarget.setCurrentIndex(1)
            elif value == 'rPanel':
                self.cbOutputTarget.setCurrentIndex(2)
            self.wTgtDoc.setVisible(False)
        elif value == 'doc':
            self.lblTgtDocFmtValue.setText(BCExportFilesDialogBox.FMT_PROPERTIES[self.__documentExportInfo['exportFormat']]['label'])
            if self.__documentExportInfo['exportFileName'] == '@clipboard':
                self.leTgtDocFileName.setText(f"[{i18n('Clipboard')}]")
            else:
                self.leTgtDocFileName.setText(self.__documentExportInfo['exportFileName'])
            self.cbOutputTarget.setCurrentIndex(3)
            self.wTgtDoc.setVisible(True)

    def resetToDefault(self):
        """Reset to default values"""
        self._startUpdate()
        self.__setDefaultValues()
        self._endUpdate()
        self._setModified(False)

    def setTitle(self, title):
        """Set title used for BCExportFilesDialogBox"""
        self.__title=f"{title}::{i18n('Output result export settings')}"

    def setUiController(self, uiController):
        """Set uiController used for BCExportFilesDialogBox"""
        self.__uiController=uiController

    def exportAsDict(self, setUnmodified=False):
        """Export widget configuration as dictionnary"""
        returned={
                "properties": {
                                "id": QUuid.createUuid().toString(),
                                "title": i18n("Output engine")
                            },
                "connectors": [
                            {
                                "id": "InputResults",
                                "properties": {
                                    "direction": NodeEditorConnector.DIRECTION_INPUT,
                                    "location": NodeEditorConnector.LOCATION_TOP_LEFT
                                }
                            }
                        ],
                "widget": {
                            "type": "BCNodeWSearchOutputEngine",
                            "outputProperties": {
                                "target": self.cbOutputTarget.currentData(),
                                "documentExportInfo": self.__documentExportInfo
                            }
                    }
            }

        if setUnmodified:
            self._setModified(False)

        return returned

    def importFromDict(self, dataAsDict):
        """Import widget configuration from dictionnary

        Note: only "widget" key content is expected for input


        Example of expected dictionary:
            "widget": {
                "type": "BCNodeWSearchOutputEngine",
                "outputProperties": {[]}
            }
        """
        if not isinstance(dataAsDict, dict):
            raise EInvalidType("Given `dataAsDict` must be a <dict>")
        elif not ("type" in dataAsDict and dataAsDict["type"]=="BCNodeWSearchOutputEngine"):
            raise EInvalidValue("Given `dataAsDict` must contains key 'type' with value 'BCNodeWSearchOutputEngine'")

        self._startUpdate()
        self.__setDefaultValues()

        if "outputProperties" in dataAsDict and isinstance(dataAsDict['outputProperties'], dict):

            if "target" in dataAsDict['outputProperties'] and dataAsDict['outputProperties']['target'] in ('aPanel', 'lPanel', 'rPanel', 'doc'):
                if "documentExportInfo" in dataAsDict['outputProperties']:
                    self.__documentExportInfo=dataAsDict['outputProperties']['documentExportInfo']
                    self.__setOutputTarget(dataAsDict['outputProperties']['target'])
                else:
                    # fallback
                    self.__documentExportInfo={
                            'exportFormat': BCExportFormat.EXPORT_FMT_TEXT,
                            'exportFileName': '@clipboard',
                            'exportConfig': {}
                        }
                    self.__setOutputTarget('aPanel')

        self._endUpdate()
        self._setModified(False)



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



class NodeEditorConnectorResults(NodeEditorConnector):
    # a sort connector
    def __init__(self, id=None, direction=0x01, location=0x01, color=None, borderColor=None, borderSize=None, parent=None):
        super(NodeEditorConnectorResults, self).__init__(id, direction, location, color, borderColor, borderSize, parent)
        if direction==NodeEditorConnector.DIRECTION_INPUT:
            tooltip="".join(["<b>", i18n("Input results"), "</b><br/><br/>", i18n("Should be connected from an&nbsp;<b>Output results</b>&nbsp;connector of &nbsp;<i>Search engine</i>")])
        else:
            tooltip="".join(["<b>", i18n(f"Output results"), "</b><br/><br/>",
                             i18n("Should be connected to an&nbsp;<b>Input results</b>&nbsp;connector of:"), "<ul><li>",
                             i18n("a <i>Sort rule</i>"),
                             "</li><li>",
                             i18n("a <i>Output engine</i>")])
        self.setToolTip(tooltip)



class BCNodeWSearchEngine(NodeEditorNodeWidget):
    """Main search engine node"""

    def __init__(self, scene, title, parent=None):
        inputPathConnector=NodeEditorConnectorPath('InputPath1', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_LEFT_TOP)
        inputFilterRuleConnector=NodeEditorConnectorFilter('InputFilterRule', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_RIGHT_TOP)
        outputResults=NodeEditorConnectorResults('OutputResults', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_BOTTOM_RIGHT)

        inputPathConnector.addAcceptedConnectionFrom(NodeEditorConnectorPath)
        inputFilterRuleConnector.addAcceptedConnectionFrom(NodeEditorConnectorFilter)

        super(BCNodeWSearchEngine, self).__init__(scene, title, connectors=[inputPathConnector, inputFilterRuleConnector, outputResults], parent=parent)

        self.node().setRemovable(False)

        self.node().connectorLinked.connect(self.__checkInputPath)
        self.node().connectorUnlinked.connect(self.__checkInputPath)
        self.node().scene().sceneLoaded.connect(self.__checkInputPath)

        defaultSize=self.calculateSize(f"{self.node().title()}", 0, 0)
        self.setMinimumSize(QSize(200, round(defaultSize.width()*0.8) ))

    def __checkInputPath(self, node=None, connector=None):
        """A connector has been connected/disconnected

        Check paths connector (always need a have ONE available connector)
        - Add connector if needed
        - Remove connector if not needed
        """
        if node is None:
            node=self.node()

        if node.scene().inMassModification():
            return

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

    def deserialize(self, data={}):
        """From given dictionary, rebuild widget"""
        for connector in self.node().connector():
            if isinstance(connector, NodeEditorConnectorPath) and len(connector.acceptedConnectionFrom())==0:
                # ensure that added connector (NodeEditorConnectorPath) can only receive connection from NodeEditorConnectorPath
                connector.addAcceptedConnectionFrom(NodeEditorConnectorPath)



class BCNodeWSearchFromPath(NodeEditorNodeWidget):
    """A path source node"""

    def __init__(self, scene, title, parent=None):
        outputPathConnector=NodeEditorConnectorPath('OutputPath', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_RIGHT_BOTTOM)

        data={
                'path': os.path.expanduser("~"),
                'scanSubDirectories': True,
                'scanManagedFilesOnly': True,
                'scanManagedFilesBackup': False,
                'scanHiddenFiles': False
            }

        self.__lblPath=WLabelElide(Qt.ElideLeft)
        self.__lblRecursive=QLabel()
        self.__lblHiddenFiles=QLabel()
        self.__lblManagedFilesOnly=QLabel()
        self.__lblManagesFilesBackup=QLabel()

        self.__lblPath.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        self.__layout=QFormLayout()
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addRow(f"<b>{i18n('Path')}</b>", self.__lblPath)
        self.__layout.addRow(f"<b>{i18n('Scan Sub-directories')}</b>", self.__lblRecursive)
        self.__layout.addRow(f"<b>{i18n('Include hidden files')}</b>", self.__lblHiddenFiles)
        self.__layout.addRow(f"<b>{i18n('Search managed files only')}</b>", self.__lblManagedFilesOnly)
        self.__layout.addRow(f"└<b><i>{i18n('Including backup files')}</i></b>", self.__lblManagesFilesBackup)

        super(BCNodeWSearchFromPath, self).__init__(scene, title, connectors=[outputPathConnector], data=data, parent=parent)

        self.setLayout(self.__layout)
        self.setMinimumSize(self.calculateSize(f"{i18n('Search managed files only')+'X'*40}", 5, self.__layout.spacing()))

    def serialize(self):
        """Convert current widget node properties to dictionnary"""
        return copy.deepcopy(self._data)

    def deserialize(self, data):
        """Convert current given data dictionnary to update widget node properties"""
        if 'path' in data:
            self._data['path']=data['path']
            self.__lblPath.setText(self._data['path'])
            self.__lblPath.setToolTip(self._data['path'])

        if 'scanSubDirectories' in data:
            self._data['scanSubDirectories']=data['scanSubDirectories']
            self.__lblRecursive.setText(boolYesNo(self._data['scanSubDirectories']))

        if 'scanHiddenFiles' in data:
            self._data['scanHiddenFiles']=data['scanHiddenFiles']
            self.__lblHiddenFiles.setText(boolYesNo(self._data['scanHiddenFiles']))

        if 'scanManagedFilesOnly' in data:
            self._data['scanManagedFilesOnly']=data['scanManagedFilesOnly']
            self.__lblManagedFilesOnly.setText(boolYesNo(self._data['scanManagedFilesOnly']))

        if 'scanManagedFilesBackup' in data:
            self._data['scanManagedFilesBackup']=data['scanManagedFilesBackup']
            self.__lblManagesFilesBackup.setText(boolYesNo(self._data['scanManagedFilesBackup']))



class BCNodeWSearchFileFilterRule(NodeEditorNodeWidget):
    """A file filter source node"""

    def __init__(self, scene, title, parent=None):
        outputFilterRuleConnector=NodeEditorConnectorFilter('OutputFilterRule', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_LEFT_BOTTOM, source=i18n('file'))

        self.__lblDateTime=QLabel(f"<b>{i18n('Date/Time')}</b>")
        self.__lblName=WLabelElide(Qt.ElideRight)
        self.__lblPath=WLabelElide(Qt.ElideRight)
        self.__lblSize=WLabelElide(Qt.ElideRight)
        self.__lblDate=WLabelElide(Qt.ElideRight)
        self.__lblTime=WLabelElide(Qt.ElideRight)

        self.__lblName.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.__lblPath.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)


        self.__layout=QFormLayout()
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addRow(f"<b>{i18n('Name')}</b>", self.__lblName)
        self.__layout.addRow(f"<b>{i18n('Path')}</b>", self.__lblPath)
        self.__layout.addRow(f"<b>{i18n('Size')}</b>", self.__lblSize)
        self.__layout.addRow(self.__lblDateTime, self.__lblDate)

        if BCSettings.get(BCSettingsKey.CONFIG_GLB_FILE_UNIT)==BCSettingsValues.FILE_UNIT_KIB:
            sizeValue2=1024.00
            sizeunit='KiB'
        else:
            sizeValue2=1000.00
            sizeunit='kB'

        dateTimeNow=QDateTime.currentDateTime()
        dateTimeYm1=QDateTime(dateTimeNow)
        dateTimeYm1.addYears(-1)

        data={
                "fileName": {
                        "active": False,
                        "operator": WOperatorType.OPERATOR_LIKE,
                        "value": '',
                        "ignoreCase": True
                    },
                "filePath": {
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
                        "dateOnly": True,
                        "operator": WOperatorType.OPERATOR_BETWEEN,
                        "value": dateTimeYm1.toMSecsSinceEpoch()/1000,
                        "value2": dateTimeNow.toMSecsSinceEpoch()/1000
                    }
            }

        super(BCNodeWSearchFileFilterRule, self).__init__(scene, title, connectors=[outputFilterRuleConnector], data=data, parent=parent)

        self.setLayout(self.__layout)
        self.setMinimumSize(self.calculateSize(f"{i18n('Path')+'X'*35}", 4, self.__layout.spacing()))

    def serialize(self):
        """Convert current widget node properties to dictionnary"""
        return copy.deepcopy(self._data)

    def deserialize(self, data):
        """Convert current given data dictionnary to update widget node properties"""
        if 'fileDate' in data:
            self._data['fileDate']=copy.deepcopy(data['fileDate'])

            if self._data['fileDate']['active']:
                fmt='dt'
                if self._data['fileDate']['dateOnly']:
                    fmt='d'
                    self.__lblDateTime.setText(f"- <b>{i18n('Date')}</b>")
                else:
                    self.__lblDateTime.setText(f"- <b>{i18n('Date/Time')}</b>")

                if self._data['fileDate']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{tsToStr(self._data['fileDate']['value'], fmt)} and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{tsToStr(self._data['fileDate']['value2'], fmt)}"
                elif self._data['fileDate']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{tsToStr(self._data['fileDate']['value'], fmt)} or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{tsToStr(self._data['fileDate']['value2'], fmt)}"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self._data['fileDate']['operator'])}{tsToStr(self._data['fileDate']['value'], fmt)}"

                self.__lblDate.setText(text)
                self.__lblDate.setToolTip(text)
            else:
                self.__lblDate.setText(boolYesNo(False))
                self.__lblDate.setToolTip('')

        if 'fileName' in data:
            self._data['fileName']=copy.deepcopy(data['fileName'])
            if self._data['fileName']['active']:
                self.__lblName.setText(WOperatorBaseInput.operatorLabel(self._data['fileName']['operator'])+' "'+self._data['fileName']['value']+'"')

                text=f"""<i>{WOperatorBaseInput.operatorLabel(self._data['fileName']['operator'])}</i> "{self._data['fileName']['value']}"<br/>"""
                if self._data['fileName']['ignoreCase']:
                    text+=i18n("(case insensitive)")
                else:
                    text+=i18n("(case sensitive)")
                self.__lblName.setToolTip(text)
            else:
                self.__lblName.setText(boolYesNo(False))
                self.__lblName.setToolTip('')

        if 'filePath' in data:
            self._data['filePath']=copy.deepcopy(data['filePath'])
            if self._data['filePath']['active']:
                self.__lblPath.setText(WOperatorBaseInput.operatorLabel(self._data['filePath']['operator'])+' "'+self._data['filePath']['value']+'"')

                text=f"""<i>{WOperatorBaseInput.operatorLabel(self._data['filePath']['operator'])}</i> "{self._data['filePath']['value']}"<br/>"""
                if self._data['filePath']['ignoreCase']:
                    text+=i18n("(case insensitive)")
                else:
                    text+=i18n("(case sensitive)")
                self.__lblPath.setToolTip(text)
            else:
                self.__lblPath.setText(boolYesNo(False))
                self.__lblPath.setToolTip('')

        if 'fileSize' in data:
            self._data['fileSize']=copy.deepcopy(data['fileSize'])
            if self._data['fileSize']['active']:
                if self._data['fileSize']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{self._data['fileSize']['value']}{self._data['fileSize']['unit']} and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{self._data['fileSize']['value2']}{self._data['fileSize']['unit']}"
                elif self._data['fileSize']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{self._data['fileSize']['value']}{self._data['fileSize']['unit']} or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{self._data['fileSize']['value2']}{self._data['fileSize']['unit']}"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self._data['fileSize']['operator'])}{self._data['fileSize']['value']}{self._data['fileSize']['unit']}"
                self.__lblSize.setText(text)
                self.__lblSize.setToolTip(text)
            else:
                self.__lblSize.setText(boolYesNo(False))
                self.__lblSize.setToolTip('')



class BCNodeWSearchImgFilterRule(NodeEditorNodeWidget):
    """A file filter source node"""

    def __init__(self, scene, title, parent=None):
        outputFilterRuleConnector=NodeEditorConnectorFilter('OutputFilterRule', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_LEFT_BOTTOM, source=i18n('image'))

        self.__lblImgFormat=WLabelElide(Qt.ElideRight)
        self.__lblImgWidth=WLabelElide(Qt.ElideRight)
        self.__lblImgHeight=WLabelElide(Qt.ElideRight)
        self.__lblImgRatio=WLabelElide(Qt.ElideRight)
        self.__lblImgPixels=WLabelElide(Qt.ElideRight)

        self.__layout=QFormLayout()
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addRow(f"<b>{i18n('Format')}</b>", self.__lblImgFormat)
        self.__layout.addRow(f"<b>{i18n('Width')}</b>", self.__lblImgWidth)
        self.__layout.addRow(f"<b>{i18n('Height')}</b>", self.__lblImgHeight)
        self.__layout.addRow(f"<b>{i18n('Aspect ratio')}</b>", self.__lblImgRatio)
        self.__layout.addRow(f"<b>{i18n('Pixels')}</b>", self.__lblImgPixels)

        data={
                "imageFormat": {
                        "active": False,
                        "operator": WOperatorType.OPERATOR_IN,
                        "value": [BCFileManagedFormat.KRA]
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
                    },
                "imageRatio": {
                        "active": False,
                        "operator": WOperatorType.OPERATOR_GE,
                        "value": 1,
                        "value2": 1
                    },
                "imagePixels": {
                        "active": False,
                        "operator": WOperatorType.OPERATOR_GE,
                        "value": 1,
                        "value2": 8.3
                    }
            }

        super(BCNodeWSearchImgFilterRule, self).__init__(scene, title, connectors=[outputFilterRuleConnector], data=data, parent=parent)

        self.setLayout(self.__layout)
        self.setMinimumSize(self.calculateSize(f"{i18n('Aspect ratio')+'X'*35}", 5, self.__layout.spacing()))

    def serialize(self):
        """Convert current widget node properties to dictionnary"""
        return copy.deepcopy(self._data)

    def deserialize(self, data):
        """Convert current given data dictionnary to update widget node properties"""
        if 'imageHeight' in data:
            self._data['imageHeight']=copy.deepcopy(data['imageHeight'])
            if self._data['imageHeight']['active']:
                if self._data['imageHeight']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{self._data['imageHeight']['value']}px and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{self._data['imageHeight']['value2']}px"
                elif self._data['imageHeight']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{self._data['imageHeight']['value']}px or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{self._data['imageHeight']['value2']}px"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self._data['imageHeight']['operator'])}{self._data['imageHeight']['value']}px"
                self.__lblImgHeight.setText(text)
                self.__lblImgHeight.setToolTip(text)
            else:
                self.__lblImgHeight.setText(boolYesNo(False))
                self.__lblImgHeight.setToolTip('')

        if 'imageWidth' in data:
            self._data['imageWidth']=copy.deepcopy(data['imageWidth'])
            if self._data['imageWidth']['active']:
                if self._data['imageWidth']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{self._data['imageWidth']['value']}px and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{self._data['imageWidth']['value2']}px"
                elif self._data['imageWidth']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{self._data['imageWidth']['value']}px or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{self._data['imageWidth']['value2']}px"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self._data['imageWidth']['operator'])}{self._data['imageWidth']['value']}px"
                self.__lblImgWidth.setText(text)
                self.__lblImgWidth.setToolTip(text)
            else:
                self.__lblImgWidth.setText(boolYesNo(False))
                self.__lblImgWidth.setToolTip('')

        if 'imageRatio' in data:
            self._data['imageRatio']=copy.deepcopy(data['imageRatio'])
            if self._data['imageRatio']['active']:
                if self._data['imageRatio']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{self._data['imageRatio']['value']:.4f} and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{self._data['imageRatio']['value2']:.4f}"
                elif self._data['imageRatio']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{self._data['imageRatio']['value']:.4f} or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{self._data['imageRatio']['value2']:.4f}"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self._data['imageRatio']['operator'])}{self._data['imageRatio']['value']:.4f}"
                self.__lblImgRatio.setText(text)
                self.__lblImgRatio.setToolTip(text)
            else:
                self.__lblImgRatio.setText(boolYesNo(False))
                self.__lblImgRatio.setToolTip('')

        if 'imagePixels' in data:
            self._data['imagePixels']=copy.deepcopy(data['imagePixels'])
            if self._data['imagePixels']['active']:
                if self._data['imagePixels']['operator']==WOperatorType.OPERATOR_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GE)}{self._data['imagePixels']['value']:.2f}MP and {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LE)}{self._data['imagePixels']['value2']:.2f}MP"
                elif self._data['imagePixels']['operator']==WOperatorType.OPERATOR_NOT_BETWEEN:
                    text=f"{WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_LT)}{self._data['imagePixels']['value']:.2f}MP or {WOperatorBaseInput.operatorLabel(WOperatorType.OPERATOR_GT)}{self._data['imagePixels']['value2']:.2f}MP"
                else:
                    text=f"{WOperatorBaseInput.operatorLabel(self._data['imagePixels']['operator'])}{self._data['imagePixels']['value']:.2f}MP"
                self.__lblImgPixels.setText(text)
                self.__lblImgPixels.setToolTip(text)
            else:
                self.__lblImgPixels.setText(boolYesNo(False))
                self.__lblImgPixels.setToolTip('')

        if 'imageFormat' in data:
            self._data['imageFormat']=copy.deepcopy(data['imageFormat'])
            if self._data['imageFormat']['active'] and len(self._data['imageFormat']['value'])>0:
                text=", ".join([BCFileManagedFormat.translate(value) for value in self._data['imageFormat']['value']])
                text=f"{WOperatorBaseInput.operatorLabel(self._data['imageFormat']['operator'])} ({text})"
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
        self.node().scene().sceneLoaded.connect(self.__checkInputFilter)
        self.setLayout(self.__layout)
        self.setMinimumSize(self.calculateSize(f"XXXXXX", 1, self.__layout.spacing()))

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

        if node.scene().inMassModification():
            return

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

        for connector in self.node().connector():
            if isinstance(connector, NodeEditorConnectorFilter) and len(connector.acceptedConnectionFrom())==0 and connector.isInput():
                # ensure that added connector (NodeEditorConnectorFilter) can only receive connection from NodeEditorConnectorFilter
                connector.addAcceptedConnectionFrom(NodeEditorConnectorFilter)



class BCNodeWSearchSortRule(NodeEditorNodeWidget):
    """A sort source node"""

    def __init__(self, scene, title, parent=None):
        inputSortRuleConnector=NodeEditorConnectorResults('InputSortRule', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_TOP_LEFT)
        outputSortRuleConnector=NodeEditorConnectorResults('OutputSortRule', NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_BOTTOM_RIGHT)

        inputSortRuleConnector.addAcceptedConnectionFrom(NodeEditorConnectorResults)

        self.__lblSortedProperties=QLabel()
        self.__lblSortCaseInsensitive=QLabel()

        self.__fntSize=self.__lblSortedProperties.fontMetrics().height() - 4

        self.__layout=QFormLayout()
        self.__layout.setLabelAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addRow(f"<b>{i18n('Case insensitive')}</b>", self.__lblSortCaseInsensitive)
        self.__layout.addRow(f"<b>{i18n('Sort by')}</b>", self.__lblSortedProperties)

        data={
                "sortProperties": {
                        "list": [{
                                    "value": orderedItem.value(),
                                    "checked": orderedItem.checked(),
                                    "ascending": orderedItem.isSortAscending()
                                 } for orderedItem in BCWSearchSortRules.getDefaultList()
                                ],
                        "caseInsensitive": True
                    },
            }

        super(BCNodeWSearchSortRule, self).__init__(scene, title, connectors=[inputSortRuleConnector, outputSortRuleConnector], data=data, parent=parent)

        self.setLayout(self.__layout)
        self.setMinimumSize(self.calculateSize(f"{i18n('Case insensitive')}{'X'*20}", 5, self.__layout.spacing()))

    def serialize(self):
        """Convert current widget node properties to dictionnary"""
        return copy.deepcopy(self._data)

    def deserialize(self, data):
        """Convert current given data dictionnary to update widget node properties"""
        if 'sortProperties' in data:
            self._data['sortProperties']=copy.deepcopy(data['sortProperties'])

            self.__lblSortCaseInsensitive.setText(boolYesNo(self._data['sortProperties']['caseInsensitive']))

            text=[]
            tooltipText=[]
            if isinstance(self._data['sortProperties']['list'], list) and len(self._data['sortProperties']['list'])>0:
                for item in self._data['sortProperties']['list']:
                    if item['checked']:
                        if item['ascending']:
                            sortArrow=f"<img width={self.__fntSize} height={self.__fntSize} src=':/pktk/images/normal/arrow_big_filled_up'>"
                            sortText=i18n('Ascending')
                        else:
                            sortArrow=f"<img width={self.__fntSize} height={self.__fntSize} src=':/pktk/images/normal/arrow_big_filled_down'>"
                            sortText=i18n('Descending')
                        text.append(f"{sortArrow}{BCWSearchSortRules.MAP_VALUE_LABEL[item['value']]}")
                        tooltipText.append(f"{BCWSearchSortRules.MAP_VALUE_LABEL[item['value']]} [{sortText}]")

            if len(text)>0:
                self.__lblSortedProperties.setText("<br>".join(text))
                self.__lblSortedProperties.setToolTip("<br>".join(tooltipText))
            else:
                self.__lblSortedProperties.setText(i18n('No sort rule defined!'))
                self.__lblSortedProperties.setToolTip('No properties have been selected to define sort rules')



class BCNodeWSearchOutputEngine(NodeEditorNodeWidget):
    """An output engine node"""

    def __init__(self, scene, title, parent=None):
        inputResultsConnector=NodeEditorConnectorResults('InputResults', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_TOP_LEFT)
        inputResultsConnector.addAcceptedConnectionFrom(NodeEditorConnectorResults)

        data={
                "outputProperties": {
                        "target": "aPanel",
                        "documentExportInfo": {
                                'exportFormat': BCExportFormat.EXPORT_FMT_TEXT,
                                'exportFileName': '@clipboard',
                                'exportConfig': {}
                            }
                    },
            }

        self.__lblOutputTarget=WLabelElide(Qt.ElideRight)

        self.__lblLblOutputDocFmt=QLabel(f"<b>{i18n('Format')}</b>")
        self.__lblLblOutputDocFileName=QLabel(f"<b>{i18n('File')}</b>")
        self.__lblOutputDocFmt=WLabelElide(Qt.ElideRight)
        self.__lblOutputDocFileName=WLabelElide(Qt.ElideLeft)

        self.__lblLblOutputDocFmt.setVisible(False)
        self.__lblLblOutputDocFileName.setVisible(False)
        self.__lblOutputDocFmt.setVisible(False)
        self.__lblOutputDocFileName.setVisible(False)

        self.__layout=QFormLayout()
        self.__layout.setContentsMargins(0,0,0,0)
        self.__layout.addRow(f"<b>{i18n('Output target')}</b>", self.__lblOutputTarget)

        self.__layout.addRow(self.__lblLblOutputDocFmt, self.__lblOutputDocFmt)
        self.__layout.addRow(self.__lblLblOutputDocFileName, self.__lblOutputDocFileName)

        super(BCNodeWSearchOutputEngine, self).__init__(scene, title, connectors=[inputResultsConnector], data=data, parent=parent)

        self.setLayout(self.__layout)
        self.setMinimumSize(self.calculateSize(f"{i18n('Output target')}{'X'*35}", 3, self.__layout.spacing()))

    def serialize(self):
        """Convert current widget node properties to dictionnary"""
        return copy.deepcopy(self._data)

    def deserialize(self, data):
        """Convert current given data dictionnary to update widget node properties"""

        if 'outputProperties' in data:
            self._data['outputProperties']=copy.deepcopy(data['outputProperties'])

            self.__lblOutputTarget.setText(BCWSearchOutputEngine.OUTPUT_TARGET[self._data['outputProperties']['target']])
            self.__lblOutputTarget.setToolTip(BCWSearchOutputEngine.OUTPUT_TARGET[self._data['outputProperties']['target']])

            if self._data['outputProperties']['target']!='doc':
                # panel
                self.__lblLblOutputDocFmt.setVisible(False)
                self.__lblLblOutputDocFileName.setVisible(False)
                self.__lblOutputDocFmt.setVisible(False)
                self.__lblOutputDocFileName.setVisible(False)
            else:
                self.__lblOutputDocFmt.setText(BCExportFilesDialogBox.FMT_PROPERTIES[self._data['outputProperties']['documentExportInfo']['exportFormat']]['label'])
                self.__lblOutputDocFmt.setToolTip(BCExportFilesDialogBox.FMT_PROPERTIES[self._data['outputProperties']['documentExportInfo']['exportFormat']]['label'])

                if self._data['outputProperties']['documentExportInfo']['exportFileName']=='@clipboard':
                    self.__lblOutputDocFileName.setText(f"[{i18n('Clipboard')}]")
                    self.__lblOutputDocFileName.setToolTip(f"[{i18n('Clipboard')}]")
                else:
                    self.__lblOutputDocFileName.setText(self._data['outputProperties']['documentExportInfo']['exportFileName'])
                    self.__lblOutputDocFileName.setToolTip(self._data['outputProperties']['documentExportInfo']['exportFileName'])

                self.__lblLblOutputDocFmt.setVisible(True)
                self.__lblLblOutputDocFileName.setVisible(True)
                self.__lblOutputDocFmt.setVisible(True)
                self.__lblOutputDocFileName.setVisible(True)
