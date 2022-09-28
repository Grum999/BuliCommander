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
# The bcfilenoperation_renamefile_visualformula_editor provides user inrterface
# to vosulay (nodes graph) build a renaming formula
#
# Main classes from this module
#
# - BCRenameFileVisualFormulaEditorDialogBox:
#       User interface to build formula
#
# - Other:
#       Classes used to manage dedicated nodes in graph
#
# -----------------------------------------------------------------------------

import PyQt5.uic
from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QSettings
    )
from PyQt5.QtWidgets import (
        QDialog,
        QFileDialog
    )
from PyQt5.QtGui import QColor

import os
import os.path
import re
import shutil
import time
import json
import copy
import html


from .bcfilenamemanipulationlanguage import (
        BCFileManipulateNameLanguageDef,
        BCFileManipulateName
    )

from .bcsettings import (
        BCSettings,
        BCSettingsKey
    )

from ..pktk.modules.strutils import (
        strDefault,
        boolYesNo
    )
from ..pktk.modules.utils import (
        regExIsValid,
        JsonQObjectEncoder,
        JsonQObjectDecoder,
        Debug
    )

from ..pktk.widgets.woperatorinput import (
        WOperatorType,
        WOperatorBaseInput,
        WOperatorCondition
    )
from ..pktk.modules.languagedef import LanguageDef
from ..pktk.modules.parser import (
        GrammarRules,
        GrammarRule,
        GROne,
        GROptional,
        GRNoneOrMore,
        GROneOrMore,
        GRToken,
        GRRule,
        GROperatorPrecedence,
        ASTItem,
        ASTSpecialItemType
    )
from ..pktk.modules.tokenizer import (
        Token,
        Tokenizer,
        TokenizerRule
    )

from ..pktk.widgets.wlabelelide import WLabelElide
from ..pktk.widgets.wiodialog import (
        WDialogBooleanInput,
        WDialogMessage
    )
from ..pktk.widgets.wcodeeditor import WCodeEditor
from ..pktk.widgets.wlineedit import WLineEdit
from ..pktk.widgets.wnodeeditor import (
        NodeEditorScene,
        NodeEditorNode,
        NodeEditorConnector,
        NodeEditorLink,
        NodeEditorNodeWidget,
        NodeEditorGrNode
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# -----------------------------------------------------------------------------


class BCRenameFileVisualFormulaEditorDialogBox(QDialog):
    """User interface to search files"""

    # note: IMPORT/EXPORT results codes identical to NodeEditorScene IMPORT/EXPORT results codes
    IMPORT_OK =                              0b00000000
    IMPORT_FILE_NOT_FOUND =                  0b00000001
    IMPORT_FILE_CANT_READ =                  0b00000010
    IMPORT_FILE_NOT_JSON =                   0b00000100
    IMPORT_FILE_INVALID_FORMAT_IDENTIFIER =  0b00001000
    IMPORT_FILE_MISSING_FORMAT_IDENTIFIER =  0b00010000
    IMPORT_FILE_MISSING_SCENE_DEFINITION =   0b00100000

    EXPORT_OK =       0b00000000
    EXPORT_CANT_SAVE = 0b00000001

    LANGUAGEDEF = BCFileManipulateNameLanguageDef()

    VSPACE = 150
    HSPACE = 100

    @staticmethod
    def open(title, codeEditor):
        """Open dialog box"""
        db = BCRenameFileVisualFormulaEditorDialogBox(title, codeEditor)
        db.exec()

    def __init__(self, title, codeEditor, parent=None):
        super(BCRenameFileVisualFormulaEditorDialogBox, self).__init__(parent)

        self.__inInit = True
        self.__title = title
        self.__codeEditor = codeEditor

        self.__initialFormula = self.__codeEditor.toPlainText()
        self.__renameFormula = None

        self.__currentLoadedConfigurationFile = ""

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcrenamefile_visualformulaeditor.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.__initialise()
        self.setWindowTitle(self.__title)
        self.setModal(True)
        self.__inInit = False

    def __initialise(self):
        """Initialise user interface"""
        actionSave = QAction(i18n("Save"), self)
        actionSave.triggered.connect(lambda: self.saveFile())
        actionSaveAs = QAction(i18n("Save as..."), self)
        actionSaveAs.triggered.connect(lambda: self.saveFile(True))

        menuSave = QMenu(self.tbSaveFormulaDefinition)
        menuSave.addAction(actionSave)
        menuSave.addAction(actionSaveAs)
        self.tbSaveFormulaDefinition.setMenu(menuSave)

        self.tbNewFormulaDefinition.clicked.connect(self.__newFormulaDefinition)
        self.tbOpenFormulaDefinition.clicked.connect(lambda: self.openFile())
        self.tbSaveFormulaDefinition.clicked.connect(lambda: self.saveFile())

        self.tbAddFunction.clicked.connect(self.__addFunction)
        self.tbAddKeyword.clicked.connect(self.__addKeyword)
        self.tbAddText.clicked.connect(self.__addText)
        self.tbAddStrConcatenate.clicked.connect(self.__addStrConcatenate)

        self.tbDeleteItems.clicked.connect(self.__deleteNode)
        self.tbZoomToFit.clicked.connect(self.wneFormulaEditor.zoomToFit)
        self.tbZoom1_1.clicked.connect(self.wneFormulaEditor.resetZoom)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.__scene = self.wneFormulaEditor.nodeScene()
        self.__scene.setOptionSnapToGrid(True)
        self.__scene.setOptionNodeCloseButtonVisible(True)
        self.__scene.nodeSelectionChanged.connect(self.__selectionChanged)
        self.__scene.linkSelectionChanged.connect(self.__selectionChanged)
        self.__scene.nodeAdded.connect(self.__formulaChanged)
        self.__scene.nodeRemoved.connect(self.__formulaChanged)
        self.__scene.linkAdded.connect(self.__formulaChanged)
        self.__scene.linkRemoved.connect(self.__formulaChanged)
        self.__scene.nodeOutputUpdated.connect(self.__formulaChanged)
        self.__scene.sceneModified.connect(self.__updateFileNameLabel)
        self.__scene.setFormatIdentifier("bulicommander-rename-formula-definition-n")

        self.__selectionChanged()

    def reject(self):
        """Dialog is closed"""
        self.__codeEditor.setPlainText(self.__initialFormula)
        self.close()

    def accept(self):
        """Dialog is closed"""
        self.close()

    def closeEvent(self, event):
        """Dialog is closed"""
        self.__saveSettings()
        event.accept()

    def openFile(self, fileName=None):
        """Open file designed by `fileName`

        If fileName is None, open dialog box with predefined last opened/saved file
        """
        if fileName is None:
            fileName = BCSettings.get(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_LASTFILE)

        if fileName is None:
            fileName = ''

        title = i18n(f"{self.__title}::{i18n('Open rename formula definition')}")
        extension = i18n("BuliCommander Rename Formula (*.bcrf)")

        fileName, dummy = QFileDialog.getOpenFileName(self, title, fileName, extension)

        if fileName != '':
            fileName = os.path.normpath(fileName)
            if not os.path.isfile(fileName):
                openResult = BCRenameFileVisualFormulaEditorDialogBox.IMPORT_FILE_NOT_FOUND
            else:
                openResult = self.__openFormulaDefinitionFile(fileName)

            if openResult == BCRenameFileVisualFormulaEditorDialogBox.IMPORT_OK:
                return True
            elif openResult == BCRenameFileVisualFormulaEditorDialogBox.IMPORT_FILE_NOT_FOUND:
                WDialogMessage.display(title, "<br >".join([i18n("<h1 >Can't open file!</h1 >"),
                                                            i18n("File not found!"),
                                                            ]))
            elif openResult == BCRenameFileVisualFormulaEditorDialogBox.IMPORT_FILE_CANT_READ:
                WDialogMessage.display(title, "<br >".join([i18n("<h1 >Can't open file!</h1 >"),
                                                            i18n("File can't be read!"),
                                                            ]))
            elif openResult == BCRenameFileVisualFormulaEditorDialogBox.IMPORT_FILE_NOT_JSON:
                WDialogMessage.display(title, "<br >".join([i18n("<h1 >Can't open file!</h1 >"),
                                                            i18n("Invalid file format!"),
                                                            ]))

            BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_LASTFILE, fileName)

        return False

    def saveFile(self, saveAs=False, fileName=None):
        """Save current rename formula to designed file name"""
        if fileName is None and self.__currentLoadedConfigurationFile != '':
            # a file is currently opened
            fileName = self.__currentLoadedConfigurationFile
        else:
            fileName = BCSettings.get(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_LASTFILE)
            saveAs = True

        if fileName is None:
            fileName = ''
            saveAs = True

        title = i18n(f"{self.__title}::{i18n('Save rename formula definition')}")
        extension = i18n("BuliCommander Rename Formula (*.bcrf)")

        if saveAs:
            fileName, dummy = QFileDialog.getSaveFileName(self, title, fileName, extension)
            if re.search(r"\.bcrf$", fileName) is None:
                fileName += ".bcrf"

        if fileName != '':
            fileName = os.path.normpath(fileName)
            saveResult = self.__saveFormulaDefinitionFile(fileName)

            BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_LASTFILE, fileName)

            if saveResult == BCRenameFileVisualFormulaEditorDialogBox.EXPORT_OK:
                return True
            elif saveResult == BCRenameFileVisualFormulaEditorDialogBox.EXPORT_CANT_SAVE:
                WDialogMessage.display(title, i18n("<h1 >Can't save file!</h1 >"))

        return False

    def showEvent(self, event):
        """When visible, update zoom to fit content"""
        self.__buildNodesFromFormula(self.__codeEditor.toPlainText())
        self.__viewWindowMaximized(BCSettings.get(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_WINDOW_MAXIMIZED))
        self.__viewWindowGeometry(BCSettings.get(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_WINDOW_GEOMETRY))
        self.wneFormulaEditor.zoomToFit()

    def __saveSettings(self):
        """Save current search window settings"""
        BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_WINDOW_MAXIMIZED, self.isMaximized())
        if not self.isMaximized():
            # when maximized geometry is full screen geometry, then do it only if not in maximized
            BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_WINDOW_GEOMETRY,
                           [self.geometry().x(),
                            self.geometry().y(),
                            self.geometry().width(),
                            self.geometry().height()])

    def __viewWindowMaximized(self, maximized=False):
        """Set the window state"""
        if not isinstance(maximized, bool):
            raise EInvalidValue('Given `maximized` must be a <bool>')

        if maximized:
            # store current geometry now because after window is maximized, it's lost
            BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_WINDOW_GEOMETRY,
                           [self.geometry().x(),
                            self.geometry().y(),
                            self.geometry().width(),
                            self.geometry().height()])
            self.showMaximized()
        else:
            self.showNormal()

        return maximized

    def __viewWindowGeometry(self, geometry=[-1, -1, -1, -1]):
        """Set the window geometry

        Given `geometry` is a list [x,y,width,height] or a QRect()
        """
        if isinstance(geometry, QRect):
            geometry = [geometry.x(), geometry.y(), geometry.width(), geometry.height()]

        if not isinstance(geometry, list) or len(geometry) != 4:
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

    def __updateFileNameLabel(self):
        """Update file name in status bar according to current tab"""
        modified = ''
        if self.__scene.isModified():
            modified = f" ({i18n('modified')})"

        if self.__currentLoadedConfigurationFile is None or self.__currentLoadedConfigurationFile == '':
            self.lblFileName.setText(f"[{i18n('Not saved')}]")
        else:
            self.lblFileName.setText(f"{self.__currentLoadedConfigurationFile}{modified}")

    def __calculateNodePosition(self):
        """Calculate position for a new node added to scene"""
        width, freq = self.__scene.gridSize()
        position = QPointF(3 * width, 3 * width)

        selectedNodes = self.__scene.selectedNodes()
        if len(selectedNodes) > 0:
            position += selectedNodes[0].position()

        return position

    def __selectionChanged(self):
        """Node/Link selection has changed"""
        selectedNodes = self.__scene.selectedNodes()
        nbSelectedNodes = len(selectedNodes)

        # if nothing selected, disable delete button
        removableNodes = 0
        for selectedNode in selectedNodes:
            if selectedNode.isRemovable():
                removableNodes += 1

        self.tbDeleteItems.setEnabled(removableNodes > 0 or len(self.__scene.selectedLinks()) > 0)

    def __formulaChanged(self, modified=None):
        """formula has been modified"""
        # update code editor
        if self.__renameFormula is not None:
            self.__codeEditor.setPlainText(self.__renameFormula.formulaValue())
            self.__scene.setModified(True)
            self.__updateFileNameLabel()

    def __deleteNode(self):
        """Delete all selected items"""
        for node in self.__scene.selectedNodes():
            self.__scene.removeNode(node)

    def __addFunction(self):
        """Add a BCNodeWFunction node"""
        position = self.__calculateNodePosition()

        nwFunction = BCNodeWFunction(self.__scene, i18n("Function"))
        nwFunction.node().setPosition(position)
        nwFunction.node().setSelected(True, False)

    def __addKeyword(self):
        """Add a BCNodeWKeyword node"""
        position = self.__calculateNodePosition()

        nwKeyword = BCNodeWKeyword(self.__scene, i18n("Keyword"))
        nwKeyword.node().setPosition(position)
        nwKeyword.node().setSelected(True, False)

    def __addText(self):
        """Add a BCNodeWText node"""
        position = self.__calculateNodePosition()

        nwText = BCNodeWText(self.__scene, i18n("Text"))
        nwText.node().setPosition(position)
        nwText.node().setSelected(True, False)

    def __addStrConcatenate(self):
        """Add a BCNodeWStrConcatenate node"""
        position = self.__calculateNodePosition()

        nwText = BCNodeWStrConcatenate(self.__scene, i18n("Concatenate"))
        nwText.node().setPosition(position)
        nwText.node().setSelected(True, False)

    def __buildNodesFromFormula(self, formula):
        """From given text formula, build nodes

        Nodes are built from AST returned by parser

        For the following formula:
            [upper:{file:baseName}"."{file:ext}]

        The following AST is returned
             <ASTItem(ASTSpecialItemType.ROOT, 1, ASTStatus.MATCH, {'from': {'column': 1, 'row': 1}, 'to': {'column': 37, 'row': 1}})>
            . . <ASTItem(Formula, 1, ASTStatus.MATCH, {'from': {'column': 1, 'row': 1}, 'to': {'column': 37, 'row': 1}})>
            . . . . <ASTItem(Function_Upper, 1, ASTStatus.MATCH, {'from': {'column': 1, 'row': 1}, 'to': {'column': 37, 'row': 1}})>
            . . . . . . <ASTItem(String_Expression, 3, ASTStatus.MATCH, {'from': {'column': 8, 'row': 1}, 'to': {'column': 36, 'row': 1}})>
            . . . . . . . . <ASTItem(Keyword, 1, ASTStatus.MATCH, {'from': {'column': 8, 'row': 1}, 'to': {'column': 23, 'row': 1}})>
            . . . . . . . . . . <Token(ITokenType.KW, `{file:baseName}`)>
            . . . . . . . . <ASTItem(Text, 1, ASTStatus.MATCH, {'from': {'column': 23, 'row': 1}, 'to': {'column': 26, 'row': 1}})>
            . . . . . . . . . . <ASTItem(String_Value, 1, ASTStatus.MATCH, {'from': {'column': 23, 'row': 1}, 'to': {'column': 26, 'row': 1}})>
            . . . . . . . . . . . . <Token(ITokenType.STRING, `"."`)>
            . . . . . . . . <ASTItem(Keyword, 1, ASTStatus.MATCH, {'from': {'column': 26, 'row': 1}, 'to': {'column': 36, 'row': 1}})>
            . . . . . . . . . . <Token(ITokenType.KW, `{file:ext}`)>

        And then built nodes should be like:
        ┌────────────────┐  ┌─────────────┐  ┌────────────────┐
        │ BCNodeWKeyword │  │ BCNodeWText │  │ BCNodeWKeyword │
        └─┬──────────────┘  └─┬───────────┘  └─┬──────────────┘
          │  ╭────────────────╯                │
          │  │  ╭──────────────────────────────╯
          │  │  │
        ┌─┴──┴──┴───────────────┐
        │ BCNodeWStrConcatenate │
        └─┬─────────────────────┘
          │
        ┌─┴───────────────┐
        │ BCNodeWFunction │
        └─┬───────────────┘
          │
        ┌─┴────────────────────┐
        │ BCNodeWRenameFormula │
        └──────────────────────┘
        """
        def updateNodePosition(node, position):
            # update position for given `node` to given `position`
            tgtRect = QRectF(position, node.boundingRect().size())
            rects = [rect for rect in [item.graphicItem().sceneBoundingRect() for item in self.__scene.nodes() if item != node] if rect.intersects(tgtRect)]

            if len(rects) > 0:
                unionRect = QRectF()
                for rect in rects:
                    unionRect = unionRect.united(rect)

                position.setY(rect.top() - tgtRect.height() - BCRenameFileVisualFormulaEditorDialogBox.VSPACE)

            node.setPosition(position)

        def buildNodesFromAst(astNode, linkedTo=None, position=None):
            # build nodes from AST
            #   linkedTo is the node from which built node have to be linked on
            #   position always define the bottom/left position for next node to build
            #
            #   function return built node
            if astNode.id() == ASTSpecialItemType.ROOT and astNode.countNodes() > 0:
                # root node, juts proceed child1
                return buildNodesFromAst(astNode.nodes()[0])
            elif astNode.id() == 'Formula':
                # formula, need to build a formula node
                self.__renameFormula = BCNodeWRenameFormula(self.__scene, i18n("Rename Formula"))
                self.__renameFormula.formulaUpdated.connect(self.__formulaChanged)

                childPosition = QPointF(self.__renameFormula.node().position().x() - BCRenameFileVisualFormulaEditorDialogBox.HSPACE,
                                        self.__renameFormula.node().position().y() - BCRenameFileVisualFormulaEditorDialogBox.VSPACE)

                # and then start to process all nodes linked to the formula
                for index, childNodes in enumerate(astNode.nodes()):
                    builtNode = buildNodesFromAst(childNodes, self.__renameFormula.node(), QPointF(childPosition))

                    fromConnector = builtNode.output('Output')
                    toConnector = self.__renameFormula.node().inputs()[index]
                    self.__scene.addLink(NodeEditorLink(fromConnector, toConnector))

                    childPosition.setX(childPosition.x() + BCRenameFileVisualFormulaEditorDialogBox.HSPACE + builtNode.boundingRect().width())

                return self.__renameFormula.node()
            elif astNode.id() in ('Function_OptionalStrParameter', 'Function_OptionalIntParameter'):
                # optional parameter should only have one child
                return buildNodesFromAst(astNode.nodes()[0], linkedTo, position)
            elif re.match('Function_', astNode.id()):
                # A function -> build a function node
                nwFunction = BCNodeWFunction(self.__scene, i18n("Function"))
                nwFunction.deserialize({"function": astNode.id(),
                                        "parameters": ["" for index in range(len(astNode.nodes()))]})
                nwFunction.node().setSelected(False, False)

                position.setY(position.y() - nwFunction.node().boundingRect().height())

                updateNodePosition(nwFunction.node(), position)

                childPosition = QPointF(position.x() - BCRenameFileVisualFormulaEditorDialogBox.HSPACE,
                                        position.y() - BCRenameFileVisualFormulaEditorDialogBox.VSPACE)

                # and then start to process all nodes linked to the formula
                for index, childNodes in enumerate(astNode.nodes()):
                    builtNode = buildNodesFromAst(childNodes, nwFunction.node(), QPointF(childPosition))

                    if isinstance(builtNode, NodeEditorNode):
                        # a node has been returned
                        fromConnector = builtNode.output('Output')
                        toConnector = nwFunction.node().inputs()[index]
                        self.__scene.addLink(NodeEditorLink(fromConnector, toConnector))

                        childPosition.setX(childPosition.x() - BCRenameFileVisualFormulaEditorDialogBox.HSPACE - builtNode.boundingRect().width())
                    else:
                        # a value has been returned, update connector input field
                        nwFunction.node().inputs()[index].setValue(builtNode)

                return nwFunction.node()
            elif astNode.id() == 'Keyword':
                # A function -> build a keyword node
                #   AST should only have one Token as child
                nwKeyword = BCNodeWKeyword(self.__scene, i18n("Keyword"))
                nwKeyword.deserialize({"value": astNode.nodes()[0].value()})
                nwKeyword.node().setSelected(False, False)

                position.setY(position.y() - nwKeyword.node().boundingRect().height())

                updateNodePosition(nwKeyword.node(), position)

                return nwKeyword.node()
            elif astNode.id() == 'Text':
                # A text return a String_Value or String_Unquoted
                # According to node `linkedTo` returned value is a node or a string
                value = buildNodesFromAst(astNode.nodes()[0])

                if isinstance(linkedTo.widget(), (BCNodeWRenameFormula, BCNodeWStrConcatenate)):
                    # return a BCNodeWText node
                    nwText = BCNodeWText(self.__scene, i18n("Text"))
                    nwText.deserialize({"value": value})
                    nwText.node().setSelected(False, False)

                    position.setY(position.y() - nwText.node().boundingRect().height())

                    updateNodePosition(nwText.node(), position)

                    return nwText.node()
                else:
                    # return a string
                    return value
            elif astNode.id() == 'String_Expression':
                # A string expression
                #   Can be: 'Text', 'Function', 'Keyword'
                #
                #   If only one child -> return value (can be a string value, or a node)
                #   If more than one child -> build a BCNodeWStrConcatenate
                if len(astNode.nodes()) == 1:
                    return buildNodesFromAst(astNode.nodes()[0], linkedTo, position)
                else:
                    # build a concatenate node
                    nwConcatenate = BCNodeWStrConcatenate(self.__scene, i18n("Concatenate"))
                    nwConcatenate.node().setSelected(False, False)

                    position.setY(position.y() - nwConcatenate.node().boundingRect().height())

                    updateNodePosition(nwConcatenate.node(), position)

                    childPosition = QPointF(position.x() - BCRenameFileVisualFormulaEditorDialogBox.HSPACE,
                                            position.y() - BCRenameFileVisualFormulaEditorDialogBox.VSPACE)

                    # and then start to process all nodes linked to the concatenate node
                    for index, childNodes in enumerate(astNode.nodes()):
                        builtNode = buildNodesFromAst(childNodes, nwConcatenate.node(), QPointF(childPosition))
                        fromConnector = builtNode.output('Output')
                        toConnector = nwConcatenate.node().inputs()[index]
                        self.__scene.addLink(NodeEditorLink(fromConnector, toConnector))

                        childPosition.setX(childPosition.x() + BCRenameFileVisualFormulaEditorDialogBox.VSPACE + builtNode.boundingRect().width())

                    return nwConcatenate.node()
            elif astNode.id() in ('String_Value', 'String_Unquoted'):
                # ast child nodes should only contain a Token
                return astNode.nodes()[0].value()
            elif astNode.id() == 'Integer_Expression':
                # An integer expression
                #   Can be: 'Integer_Value', 'Function'
                return buildNodesFromAst(astNode.nodes()[0], linkedTo, position)
            elif astNode.id() == 'Integer_Value':
                # ast child nodes should only contain a Token
                return astNode.nodes()[0].value()
            else:
                # should not occurs!
                return None

        # get tokens from current formula
        ast = BCFileManipulateName.parser().parse(formula)
        # print(ast)

        if not isinstance(ast, ASTItem):
            return None

        if self.__renameFormula is not None:
            try:
                self.__renameFormula.formulaUpdated.disconnect(self.__formulaChanged)
                self.__renameFormula = None
            except e as Exception:
                pass

        self.__scene.clear()

        buildNodesFromAst(ast)
        if self.isVisible():
            self.wneFormulaEditor.zoomToFit()

    def __newFormulaDefinition(self, force=False):
        """reset current formula definition"""
        if not force and self.__scene.isModified():
            if not WDialogBooleanInput.display(f"{self.__title}::{i18n('New formula')}", i18n("Current formula has been modified, do you confirm the new empty formula?")):
                return False

        self.__buildNodesFromFormula("{file:baseName}.{file:ext}")
        self.wneFormulaEditor.resetZoom()

        self.__scene.setModified(False)

        self.__currentLoadedConfigurationFile = None
        self.__updateFileNameLabel()

        self.wneFormulaEditor.zoomToFit()

    def __saveFormulaDefinitionFile(self, fileName):
        """Save formula definition to defined `fileName`"""
        self.__scene.setExtraData({'contentDescription': '',
                                   'formula': self.__renameFormula.formulaValue()})

        returned = BCRenameFileVisualFormulaEditorDialogBox.EXPORT_OK
        try:
            with open(fileName, 'w') as fHandle:
                fHandle.write(self.__scene.toJson())
        except Exception as e:
            Debug.print("Can't save file {0}: {1}", fileName, f"{e}")
            returned = BCRenameFileVisualFormulaEditorDialogBox.EXPORT_CANT_SAVE

        BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_LASTFILE, fileName)
        self.__currentLoadedConfigurationFile = fileName
        self.__scene.setModified(False)
        self.__updateFileNameLabel()

        return returned

    def __openFormulaDefinitionFile(self, fileName):
        """Open & load formula definition defined by `fileName`"""
        if self.__scene.isModified():
            if not WDialogBooleanInput.display(self.__title, i18n("Current formula definition has been modified and will be lost, continue?")):
                return False

        try:
            with open(fileName, 'r') as fHandle:
                jsonAsStr = fHandle.read()
        except Exception as e:
            Debug.print("Can't open/read file {0}: {1}", fileName, f"{e}")
            return BCRenameFileVisualFormulaEditorDialogBox.IMPORT_FILE_CANT_READ

        try:
            jsonAsDict = json.loads(jsonAsStr, cls=JsonQObjectDecoder)
        except Exception as e:
            Debug.print("Can't parse file {0}: {1}", fileName, f"{e}")
            return BCRenameFileVisualFormulaEditorDialogBox.IMPORT_FILE_NOT_JSON

        if "formatIdentifier" not in jsonAsDict:
            Debug.print("Missing format identifier file {0}", fileName)
            return BCRenameFileVisualFormulaEditorDialogBox.IMPORT_FILE_MISSING_FORMAT_IDENTIFIER

        if jsonAsDict["formatIdentifier"] == "bulicommander-rename-formula-definition-n":
            # contains nodes definitions
            self.__scene.deserialize(jsonAsDict)

            if self.__renameFormula is not None:
                try:
                    self.__renameFormula.formulaUpdated.disconnect(self.__formulaChanged)
                    self.__renameFormula = None
                except e as Exception:
                    pass

            renameFormulaNode = self.__scene.nodeFromId('renameFormula')
            if renameFormulaNode is not None:
                # if not it's not a norpmal case! what to do?
                self.__renameFormula = renameFormulaNode.widget()
                self.__renameFormula.formulaUpdated.connect(self.__formulaChanged)
        elif jsonAsDict["formatIdentifier"] == "bulicommander-rename-formula-definition":
            self.__buildNodesFromFormula(jsonAsDict['extraData']['formula'])
        else:
            Debug.print("Invalid format identifier file {0}", fileName)
            return BCRenameFileVisualFormulaEditorDialogBox.IMPORT_FILE_INVALID_FORMAT_IDENTIFIER

        BCSettings.set(BCSettingsKey.SESSION_MASSRENAMEWINDOW_VEDITOR_LASTFILE, fileName)
        self.wneFormulaEditor.zoomToFit()
        self.__currentLoadedConfigurationFile = fileName
        self.__scene.setModified(False)
        self.__updateFileNameLabel()
        self.__formulaChanged()


class NodeEditorConnectorInt(NodeEditorConnector):
    """An output Integer connector"""
    def __init__(self, id=None):
        super(NodeEditorConnectorInt, self).__init__(id, NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_BOTTOM_LEFT, None, None, None, None)
        self.setToolTip("".join(["<b>",
                                 i18n("Output integer"), "</b><br/><br/>",
                                 i18n("Can be connected to an&nbsp;<b>Input integer</b>&nbsp;connector of a&nbsp;<i>Function</i>")
                                 ]
                                )
                        )


class NodeEditorConnectorStr(NodeEditorConnector):
    """An output String connector"""
    def __init__(self, id=None):
        super(NodeEditorConnectorStr, self).__init__(id, NodeEditorConnector.DIRECTION_OUTPUT, NodeEditorConnector.LOCATION_BOTTOM_LEFT, None, None, None, None)
        self.setToolTip("".join(["<b>",
                                 i18n("Output string"),
                                 "</b><br/><br/>",
                                 i18n("Can be connected to an&nbsp;<b>Input string</b>&nbsp;connector of a&nbsp;<i>Function</i> and/or <i>Rename Formula</i>")
                                 ]
                                )
                        )


class NodeEditorConnectorField(NodeEditorConnector):
    """An input field connector

    Manage input field that will be set in node UI
    - Create widget
    - Emit widgetValueChanged signal when widget value is changed
    - Enable/Disabled widget according to connector link status (disconnected/connected)
    """

    widgetValueChanged = Signal(str)

    def __init__(self, valueLabel, connectorType, options=None, id=None):
        """Initialisate connector


        Given `valueLabel` define label used for value (used as tooltip)
        Given `connectorType` define from which type of connector a connection can be made
            Also define the type of widget
                > NodeEditorConnectorInt: QSpinBox
                > NodeEditorConnectorStr: WLineEdit

        Given `options` are related to widget and provided as dictionary
        Possible options value are
            - for a QSpinBox
                'minValue':     <int>       # minimum value alowed for QSpinBox (default=0)
                'maxValue':     <int>       # maximum value alowed for QSpinBox (default=99)
            - for a WLineEdit
                'regex':        <str>       # provided value is a regular expression - check if provided regex is valid (default=False)
                'quoted':       <bool>      # output value from field is quoted; False=only if value from field (not from connector) / True=always (default=False)

        Given `id` define connector unique identifier

        """
        super(NodeEditorConnectorField, self).__init__(id, NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_LEFT_TOP, None, None, None, None)
        self.addAcceptedConnectionFrom(connectorType)

        self.__valueLabel = valueLabel
        self.__connectorType = connectorType

        if options is None:
            options = {}
        if not isinstance(options, dict):
            raise EInvalidType("Given `options` must be None or a <dict>")

        if self.__connectorType == NodeEditorConnectorStr:
            self.__options = {'regex': False,
                              'quoted': False,
                              'maxLength': 0,   # 0 = no length limit
                              'values': []      # if provided, manage a combobox
                              }
            self.__options = {**self.__options, **options}  # merge options

            if len(self.__options['values']) > 0:
                # manage a combobox, ignore other options
                self.__widget = QComboBox()

                for value in self.__options['values']:
                    self.__widget.addItem(value)

                self.__widget.setCurrentIndex(0)

                self.__widget.currentTextChanged.connect(lambda v: self.widgetValueChanged.emit(v))
            else:
                self.__widget = WLineEdit()
                self.__widget.textChanged.connect(lambda v: self.widgetValueChanged.emit(v))

                self.__widget.setRegEx(self.__options['regex'])

                if self.__options['maxLength'] > 0:
                    self.__widget.setMaxLength(self.__options['maxLength'])
        else:
            self.__widget = QSpinBox()
            self.__widget.valueChanged.connect(lambda v: self.widgetValueChanged.emit(f"{v}"))
            self.__options = {'minValue': 0,
                              'maxValue': 999
                              }
            self.__options = {**self.__options, **options}  # merge options

            self.__widget.setMinimum(self.__options['minValue'])
            self.__widget.setMaximum(self.__options['maxValue'])

        self.__widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        # to updated widget status + tooltip
        self.linkConnectionRemoved(None)

        if self.__connectorType == NodeEditorConnectorStr:
            tooltip = "".join(["<b>", valueLabel, "</b><br/><br/>", i18n("Should be connected from a&nbsp;<b>String function</b>&nbsp;or a&nbsp;<b>Keyword</b>")])
        elif self.__connectorType == NodeEditorConnectorInt:
            tooltip = "".join(["<b>", valueLabel, "</b><br/><br/>", i18n("Should be connected from an&nbsp;<b>Integer function</b>")])

        self.setToolTip(tooltip)

    def setNode(self, node):
        """ """
        super(NodeEditorConnectorField, self).setNode(node)

        if node is None and self.__widget is not None:
            self.__widget.hide()
            self.__widget.setParent(None)
            self.__widget = None

    def options(self):
        """Returns options for connector"""
        return self.__options

    def linkConnectionAdded(self, link):
        """Called when `link` is connected TO or FROM current connector"""
        self.__widget.setEnabled(False)
        self.__widget.setToolTip(i18n(f"<span>Function parameter <b>&lt;{self.__valueLabel}&gt;</b></span><br><br><span>Value is currently provided from input connector</span>"))

    def linkConnectionRemoved(self, link):
        """Called when `link` is disconnected TO or FROM current connector"""
        self.__widget.setEnabled(True)
        self.__widget.setToolTip(i18n(f"<span>Function parameter <b>&lt;{self.__valueLabel}&gt;</b></span><br><br><span>Value is currently provided from input field</span>"))

    def valueLabel(self):
        """Return value label"""
        return self.__valueLabel

    def connectorType(self):
        """Return connector type"""
        return self.__connectorType

    def widget(self):
        """Return connector widget field"""
        return self.__widget

    def isValueFromWidget(self):
        """Return True if value is returned from widget, otherwise False"""
        return self.__widget.isEnabled()

    def value(self):
        """Return value for connector, taking in account field value (if not connected) or input value (if connected)"""
        if self.__widget.isEnabled():
            if self.__connectorType == NodeEditorConnectorStr:
                # WLineEdit / QComboBox
                if isinstance(self.__widget, WLineEdit):
                    return self.__widget.text()
                else:
                    return self.__widget.currentText()
            else:
                # QSpinBox
                return self.__widget.value()
        else:
            # from input
            returned = super(NodeEditorConnectorField, self).value()

            # -- if options are defined on widget to check value validity, need to apply it
            if self.__connectorType == NodeEditorConnectorStr:
                if returned is None:
                    returned = '""'

                # need to trim "
                returnedStripped = returned.strip('"')

                # WLineEdit / QComboBox
                if isinstance(self.__widget, WLineEdit):
                    if self.__options['maxLength'] > 0 and len(returnedStripped) > self.__options['maxLength']:
                        returned = f'"{returnedStripped[0:self.__options["maxLength"]]}"'
                else:
                    if returnedStripped not in self.__options['values']:
                        returned = f'"{self.__options["values"][0]}"'
            else:
                if returned is None:
                    returned = 0

                # QSpinBox
                if returned > self.__widget.maximum():
                    returned = self.__widget.maximum()
                elif returned > self.__widget.minimum():
                    returned = self.__widget.minimum()
            return returned

    def setValue(self, value):
        """Set value for widget"""
        if self.__widget.isEnabled():
            if self.__connectorType == NodeEditorConnectorStr and isinstance(value, str):
                # WLineEdit / QComboBox
                if isinstance(self.__widget, WLineEdit):
                    self.__widget.setText(value)
                else:
                    self.__widget.setCurrentText(value)
            elif self.__connectorType == NodeEditorConnectorInt and isinstance(value, int):
                # QSpinBox
                self.__widget.setValue(value)
        super(NodeEditorConnectorField, self).setValue(value)


class BCNodeWFunction(NodeEditorNodeWidget):
    """A file filter operator node"""

    def __init__(self, scene, title, parent=None):
        self.__inputs = []
        self.__outputConnector = None

        self.__cbValue = QComboBox()
        self.__maxLen = 0
        for rule in BCRenameFileVisualFormulaEditorDialogBox.LANGUAGEDEF.tokenizer().rules():
            if rule.type() in (BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, BCFileManipulateNameLanguageDef.ITokenType.FUNCO_INT):
                for autoCompletion in rule.autoCompletion():
                    textValue = autoCompletion[0].replace(LanguageDef.SEP_PRIMARY_VALUE, '').replace(LanguageDef.SEP_SECONDARY_VALUE, '')
                    self.__cbValue.addItem(textValue, autoCompletion)
                    if len(textValue) > self.__maxLen:
                        self.__maxLen = len(textValue)

        self.__monoFont = self.__cbValue.font()
        self.__monoFont.setFamily('DejaVu Sans Mono, Consolas, Courier New')
        self.__cbValue.setFont(self.__monoFont)
        self.__cbValue.setCurrentIndex(-1)

        self.__layout = QVBoxLayout()
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.__layout.addWidget(self.__cbValue)
        self.__layout.addStretch()

        super(BCNodeWFunction, self).__init__(scene, title, connectors=[], parent=parent)

        self.__cbValue.currentIndexChanged.connect(self.__cbValueChanged)
        self.__cbValue.highlighted.connect(self.__displayCompleterHint)

        self.node().connectorLinked.connect(self.__checkInputFilter)
        self.node().connectorUnlinked.connect(self.__checkInputFilter)
        self.node().scene().sceneLoaded.connect(self.__checkInputFilter)
        self.setLayout(self.__layout)
        self.__cbValue.setCurrentIndex(0)

    def __hideCompleterHint(self):
        """Hide completer hint"""
        QToolTip.showText(self.__cbValue.mapToGlobal(QPoint()), '')
        QToolTip.hideText()

    @pyqtSlot(int)
    def __displayCompleterHint(self, index):
        """Display completer hint"""
        data = self.__cbValue.itemData(index)
        if data is None or data[1] == '':
            self.__hideCompleterHint()
            return
        else:
            geometry = self.__cbValue.geometry()
            position = QPoint(geometry.left() + geometry.width(), geometry.top())
            # it's not possible to move a tooltip
            # need to set a different value to force tooltip being refreshed to new position
            QToolTip.showText(self.__cbValue.mapToGlobal(position), data[1]+' ')
            QToolTip.showText(self.__cbValue.mapToGlobal(position), data[1], self.__cbValue, QRect(), 600000)  # 10minutes..

    def __cbValueChanged(self, index):
        """Current function value has been changed"""
        self.__cbValue.setToolTip(self.__cbValue.currentData()[1])

        if self.__cbValue.currentData()[0] == '[upper:\x01<value>\x01]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'))
        elif self.__cbValue.currentData()[0] == '[lower:\x01<value>\x01]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'))
        elif self.__cbValue.currentData()[0] == '[capitalize:\x01<value>\x01]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'))
        elif self.__cbValue.currentData()[0] == '[camelize:\x01<value>\x01]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'))
        elif self.__cbValue.currentData()[0] == '[replace:\x01<value>\x01, "\x02<search>\x02", "\x02<replace>\x02"]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'),
                                  NodeEditorConnectorField('search', NodeEditorConnectorStr, None, 'search'),
                                  NodeEditorConnectorField('replace', NodeEditorConnectorStr, None, 'replace'))
        elif self.__cbValue.currentData()[0] == '[regex:\x01<value>\x01, "\x02<pattern>\x02"]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'),
                                  NodeEditorConnectorField('pattern', NodeEditorConnectorStr, {'regex': True}, 'pattern'))
        elif self.__cbValue.currentData()[0] == '[regex:\x01<value>\x01, "\x02<pattern>\x02", "\x02<replace>\x02"]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'),
                                  NodeEditorConnectorField('pattern', NodeEditorConnectorStr, {'regex': True}, 'pattern'),
                                  NodeEditorConnectorField('replace', NodeEditorConnectorStr, None, 'replace'))
        elif self.__cbValue.currentData()[0] == '[index:\x01<value>\x01, "\x02<separator>\x02", \x02<index>\x02]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'),
                                  NodeEditorConnectorField('separator', NodeEditorConnectorStr, None, 'separator'),
                                  NodeEditorConnectorField('index', NodeEditorConnectorInt, {'minValue': 1, 'maxValue': 1024}, 'index'))
        elif self.__cbValue.currentData()[0] == '[sub:\x01<value>\x01, \x02<start>\x02]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'),
                                  NodeEditorConnectorField('start', NodeEditorConnectorInt, {'minValue': -1024, 'maxValue': 1024}, 'start'))
        elif self.__cbValue.currentData()[0] == '[sub:\x01<value>\x01, \x02<start>\x02, \x02<length>\x02]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'),
                                  NodeEditorConnectorField('start', NodeEditorConnectorInt, {'minValue': -1024, 'maxValue': 1024}, 'start'),
                                  NodeEditorConnectorField('length', NodeEditorConnectorInt, {'minValue': 1, 'maxValue': 1024}, 'length'))
        elif self.__cbValue.currentData()[0] == '[padding:\x01<value>\x01, \x02<length>\x02, \x02<alignment>\x02, \x02<character>\x02]':
            self.__updateUiFields(NodeEditorConnectorStr,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'),
                                  NodeEditorConnectorField('length', NodeEditorConnectorInt, {'minValue': 1, 'maxValue': 1024}, 'length'),
                                  NodeEditorConnectorField('alignment', NodeEditorConnectorStr, {'values': ['left', 'right', 'center']}, 'alignment'),
                                  NodeEditorConnectorField('character', NodeEditorConnectorStr, {'maxLength': 1}, 'character'))
        elif self.__cbValue.currentData()[0] == '[len:\x01<value>\x01]':
            self.__updateUiFields(NodeEditorConnectorInt,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'))
        elif self.__cbValue.currentData()[0] == '[len:\x01<value>\x01, \x02<adjustment>\x02]':
            self.__updateUiFields(NodeEditorConnectorInt,
                                  NodeEditorConnectorField('value', NodeEditorConnectorStr, None, 'value'),
                                  NodeEditorConnectorField('adjustment', NodeEditorConnectorInt, {'minValue': -1024, 'maxValue': 1024}, 'adjustment'))

        self.inputUpdated('functionId', self.__cbValue.currentData())

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
        return
        if node is None:
            node = self.node()

        if node.scene().inMassModification():
            return

        if self.__cbValue.currentData() == 'not':
            firstInputIsUsed = True
        else:
            firstInputIsUsed = False

        lastNumber = 1
        nbInputFilterAvailable = 0
        nbInputFilter = 0
        toRemove = []
        connectors = node.connector()
        for connector in reversed(connectors):
            if isinstance(connector, NodeEditorConnector) and connector.isInput():
                nbInputFilter += 1

                if r := re.match(r"InputFilterRule(\d+)$", connector.id()):
                    lastNumber = max(lastNumber, int(r.groups()[0])+1)

                if len(connector.links()) == 0:
                    if firstInputIsUsed:
                        toRemove.append(connector)
                    else:
                        if nbInputFilterAvailable == 0:
                            nbInputFilterAvailable += 1
                        else:
                            toRemove.append(connector)

        if len(toRemove) > 0:
            # need to remove some connectors
            if firstInputIsUsed and nbInputFilter == 1:
                # if we "NOT" operator
                # if total number of input filter is 1, need to remove connector
                # from list, as we need to keep at least one connector
                toRemove.pop()

            # remove connectors, if any
            for connector in toRemove:
                node.removeConnector(connector)

        # according to operator type (AND, OR, NOT) need to define standard colors or warning (red) color
        # to connectors
        firstInput = True
        for connector in node.connector():
            if connector.isInput():
                if firstInputIsUsed and not firstInput:
                    # connector is used but we already have one connector used for "NOT"
                    # can't delete value but set it in red -- let user remove link or change operator type
                    connector.setColor(QColor(Qt.red))
                else:
                    connector.setColor(None)
                firstInput = False

        if nbInputFilterAvailable == 0 and not firstInputIsUsed:
            # no input connector available, add one if not "NOT" operator
            inputRuleConnector = NodeEditorConnector(f'InputFilterRule{lastNumber}', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_LEFT_TOP)
            inputRuleConnector.addAcceptedConnectionFrom(NodeEditorConnector)
            node.addConnector(inputRuleConnector)

    def __updateUiFields(self, outputConnector, *inputConnectors):
        """update inputs in user interface"""
        self.setUpdatesEnabled(False)

        node = self.node()

        # if output node type is the same, no need to delete it/recreate it
        replaceOutput = (type(self.__outputConnector) != outputConnector)

        # cleanup current connectors & layout
        hasValue = False
        for connector in reversed(node.connector()):
            if connector.id() == 'value':
                hasValue = True
            elif connector.isInput() or replaceOutput and connector.isOutput():
                if isinstance(connector, NodeEditorConnectorField):
                    # output is not NodeEditorConnectorField
                    self.__layout.removeWidget(connector.widget())
                node.removeConnector(connector)

        # all unused input have been removed
        # reinitiliase widget list
        self.__inputs = []

        # calculate size for node
        size = self.__cbValue.sizeHint()
        # add some additional space
        # current node editor implementation have a problem to determinate/apply size properly... ?
        size.setWidth(size.width()+40)
        size.setHeight(size.height()+self.__layout.spacing()+self.node().padding())

        for inputConnector in inputConnectors:
            if inputConnector.id() != 'value' or (inputConnector.id() == 'value' and not hasValue):
                # add input fields
                widget = inputConnector.widget()
                widget.setFont(self.__monoFont)
                self.__layout.insertWidget(self.__layout.count()-1, widget)
                self.__inputs.append(widget)
                size.setHeight(size.height()+widget.sizeHint().height()+self.__layout.spacing())

                inputConnector.setPosition(size.height() + widget.sizeHint().height()//2)
                inputConnector.setPositionLocked(True)
                inputConnector.widgetValueChanged.connect(lambda v: self.inputUpdated(inputConnector.id(), v))

                node.addConnector(inputConnector)
            else:
                size.setHeight(size.height()+inputConnector.widget().sizeHint().height()+self.__layout.spacing())

        if replaceOutput:
            # output need to be replaced, then recreate connector
            self.__outputConnector = outputConnector('Output')
            node.addConnector(self.__outputConnector)

        self.setMinimumSize(size)
        self.setUpdatesEnabled(True)
        self.__checkInputFilter()

    def inputUpdated(self, inputId, value):
        """An input connector has been updated"""
        function = self.__cbValue.currentData()[0].replace('"',
                                                           ''
                                                           ).replace(LanguageDef.SEP_SECONDARY_VALUE,
                                                                     LanguageDef.SEP_PRIMARY_VALUE
                                                                     ).split(LanguageDef.SEP_PRIMARY_VALUE)[::2]

        index = 0
        output = [function[index]]
        for connector in self.node().connector():
            if isinstance(connector, NodeEditorConnectorField):
                index += 1

                value = connector.value()
                if value is None:
                    value = ""

                quoted = False
                if connector.connectorType() == NodeEditorConnectorStr:
                    # a string input connector
                    # need to be quoted or not?
                    if connector.options()['quoted'] or connector.isValueFromWidget():
                        quoted = True

                if quoted:
                    output.append(f'"{value}"')
                else:
                    output.append(f'{value}')
                output.append(function[index])

        self.updateOutput('Output', "".join(output))

    def serialize(self):
        if self.__cbValue.currentData()[0] == '[upper:\x01<value>\x01]':
            value = 'Function_Upper'
        elif self.__cbValue.currentData()[0] == '[lower:\x01<value>\x01]':
            value = 'Function_Lower'
        elif self.__cbValue.currentData()[0] == '[capitalize:\x01<value>\x01]':
            value = 'Function_Capitalize'
        elif self.__cbValue.currentData()[0] == '[camelize:\x01<value>\x01]':
            value = 'Function_Camelize'
        elif self.__cbValue.currentData()[0] == '[replace:\x01<value>\x01, "\x02<search>\x02", "\x02<replace>\x02"]':
            value = 'Function_Replace'
        elif self.__cbValue.currentData()[0] in ('[regex:\x01<value>\x01, "\x02<pattern>\x02"]', '[regex:\x01<value>\x01, "\x02<pattern>\x02", "\x02<replace>\x02"]'):
            value = 'Function_RegEx'
        elif self.__cbValue.currentData()[0] == '[index:\x01<value>\x01, "\x02<separator>\x02", \x02<index>\x02]':
            value = 'Function_Index'
        elif self.__cbValue.currentData()[0] in ('[sub:\x01<value>\x01, \x02<start>\x02]', '[sub:\x01<value>\x01, \x02<start>\x02, \x02<length>\x02]'):
            value = 'Function_Sub'
        elif self.__cbValue.currentData()[0] in ('[len:\x01<value>\x01]', '[len:\x01<value>\x01, \x02<adjustment>\x02]'):
            value = 'Function_Len'

        parameters = []

        for connector in self.node().connector():
            if isinstance(connector, NodeEditorConnectorField):
                parameters.append(connector.value())

        return {
                "function": value,
                "parameters": parameters
            }

    def deserialize(self, data):
        if "function" in data and "parameters" in data:
            if data["function"] == 'Function_Upper':
                value = '[upper:\x01<value>\x01]'
            elif data["function"] == 'Function_Lower':
                value = '[lower:\x01<value>\x01]'
            elif data["function"] == 'Function_Capitalize':
                value = '[capitalize:\x01<value>\x01]'
            elif data["function"] == 'Function_Camelize':
                value = '[camelize:\x01<value>\x01]'
            elif data["function"] == 'Function_Replace':
                value = '[replace:\x01<value>\x01, "\x02<search>\x02", "\x02<replace>\x02"]'
            elif data["function"] == 'Function_RegEx':
                if len(data["parameters"]) == 2:
                    value = '[regex:\x01<value>\x01, "\x02<pattern>\x02"]'
                elif len(data["parameters"]) == 3:
                    value = '[regex:\x01<value>\x01, "\x02<pattern>\x02", "\x02<replace>\x02"]'
            elif data["function"] == 'Function_Index':
                value = '[index:\x01<value>\x01, "\x02<separator>\x02", \x02<index>\x02]'
            elif data["function"] == 'Function_Sub':
                if len(data["parameters"]) == 2:
                    value = '[sub:\x01<value>\x01, \x02<start>\x02]'
                elif len(data["parameters"]) == 3:
                    value = '[sub:\x01<value>\x01, \x02<start>\x02, \x02<length>\x02]'
            elif data["function"] == 'Function_Padding':
                value = '[padding:\x01<value>\x01, \x02<length>\x02, \x02<alignment>\x02, \x02<character>\x02]'
            elif data["function"] == 'Function_Len':
                if len(data["parameters"]) == 1:
                    value = '[len:\x01<value>\x01]'
                elif len(data["parameters"]) == 2:
                    value = '[len:\x01<value>\x01, \x02<adjustment>\x02]'

            for index in range(self.__cbValue.count()):
                if self.__cbValue.itemData(index)[0] == value:
                    self.__cbValue.setCurrentIndex(index)
                    break

            for index, connector in enumerate(self.node().connector()):
                if isinstance(connector, NodeEditorConnector) and len(connector.acceptedConnectionFrom()) == 0 and connector.isInput():
                    # ensure that added connector (NodeEditorConnector) can only receive connection from NodeEditorConnector
                    connector.addAcceptedConnectionFrom(NodeEditorConnector)
                    connector.setValue(data["parameters"][index])


class BCNodeWKeyword(NodeEditorNodeWidget):
    """A keyword node"""

    def __init__(self, scene, title, parent=None):
        outputConnector = NodeEditorConnectorStr('Output')

        self.__cbValue = QComboBox()
        self.__maxLen = 0
        for rule in BCRenameFileVisualFormulaEditorDialogBox.LANGUAGEDEF.tokenizer().rules():
            if rule.type() == BCFileManipulateNameLanguageDef.ITokenType.KW:
                for autoCompletion in rule.autoCompletion():
                    textValue = autoCompletion[0].replace(LanguageDef.SEP_PRIMARY_VALUE, '').replace(LanguageDef.SEP_SECONDARY_VALUE, '')
                    self.__cbValue.addItem(textValue, autoCompletion)
                    if len(textValue) > self.__maxLen:
                        self.__maxLen = len(textValue)

        self.__monoFont = self.__cbValue.font()
        self.__monoFont.setFamily('DejaVu Sans Mono, Consolas, Courier New')
        self.__cbValue.setFont(self.__monoFont)
        self.__cbValue.setCurrentIndex(-1)

        self.__layout = QVBoxLayout()
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.__layout.addWidget(self.__cbValue)
        self.__layout.addStretch()

        super(BCNodeWKeyword, self).__init__(scene, title, connectors=[outputConnector], parent=parent)

        self.__cbValue.currentIndexChanged.connect(self.__cbValueChanged)
        self.__cbValue.highlighted.connect(self.__displayCompleterHint)

        self.setLayout(self.__layout)
        self.setMinimumSize(self.calculateSize(f"{self.__maxLen*'X'}", 2, self.__layout.spacing()))
        self.__cbValue.setCurrentIndex(0)

    def __hideCompleterHint(self):
        """Hide completer hint"""
        QToolTip.showText(self.__cbValue.mapToGlobal(QPoint()), '')
        QToolTip.hideText()

    @pyqtSlot(int)
    def __displayCompleterHint(self, index):
        """Display completer hint"""
        data = self.__cbValue.itemData(index)
        if data is None or data[1] == '':
            self.__hideCompleterHint()
            return
        else:
            geometry = self.__cbValue.geometry()
            position = QPoint(geometry.left() + geometry.width(), geometry.top())
            # it's not possible to move a tooltip
            # need to set a different value to force tooltip being refreshed to new position
            QToolTip.showText(self.__cbValue.mapToGlobal(position), data[1]+' ')
            QToolTip.showText(self.__cbValue.mapToGlobal(position), data[1], self.__cbValue, QRect(), 600000)  # 10minutes..

    def __cbValueChanged(self, index):
        """Current keyword value has been changed"""
        self.__cbValue.setToolTip(self.__cbValue.currentData()[1])
        self.updateOutput('Output', self.__cbValue.currentData()[0])

    def serialize(self):
        return {
                "value": self.__cbValue.currentData()[0]
            }

    def deserialize(self, data):
        if "value" in data:
            for index in range(self.__cbValue.count()):
                if self.__cbValue.itemData(index)[0] == data['value']:
                    self.__cbValue.setCurrentIndex(index)
                    break


class BCNodeWText(NodeEditorNodeWidget):
    """A text node"""

    def __init__(self, scene, title, parent=None):
        outputConnector = NodeEditorConnectorStr('Output')

        self.__leValue = WLineEdit()
        self.__monoFont = self.__leValue.font()
        self.__monoFont.setFamily('DejaVu Sans Mono, Consolas, Courier New')
        self.__leValue.setFont(self.__monoFont)

        self.__layout = QVBoxLayout()
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.__layout.addWidget(self.__leValue)
        self.__layout.addStretch()

        super(BCNodeWText, self).__init__(scene, title, connectors=[outputConnector], parent=parent)

        self.__leValue.textChanged.connect(self.__leValueChanged)

        self.setLayout(self.__layout)
        self.setMinimumSize(self.calculateSize(f"{25*'X'}", 2, self.__layout.spacing()))

    def __leValueChanged(self, text):
        """Current value has been changed"""
        self.updateOutput('Output', f'"{self.__leValue.text()}"')

    def serialize(self):
        return {
                "value": self.__leValue.text()
            }

    def deserialize(self, data):
        if "value" in data:
            self.__leValue.setText(data['value'].strip('"'))


class BCNodeWStrConcatenate(NodeEditorNodeWidget):
    """A grouping node"""

    def __init__(self, scene, title, parent=None):
        inputConnector = NodeEditorConnector('Input1', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_TOP_LEFT)
        outputConnector = NodeEditorConnectorStr('Output')

        self.__wceFormula = WCodeEditor()
        self.__wceFormula.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        self.__wceFormula.setLanguageDefinition(BCRenameFileVisualFormulaEditorDialogBox.LANGUAGEDEF)
        self.__wceFormula.setReadOnly(True)
        self.__wceFormula.setOptionMultiLine(False)
        self.__wceFormula.setOptionShowLineNumber(False)
        self.__wceFormula.setOptionShowIndentLevel(False)
        self.__wceFormula.setOptionShowRightLimit(False)
        self.__wceFormula.setOptionShowSpaces(False)
        self.__wceFormula.setOptionAllowWheelSetFontSize(False)
        self.__wceFormula.setShortCut(Qt.Key_Tab, False, None)      # disable indent
        self.__wceFormula.setShortCut(Qt.Key_Backtab, False, None)  # disable dedent
        self.__wceFormula.setShortCut(Qt.Key_Slash, True, None)     # disable toggle comment
        self.__wceFormula.setShortCut(Qt.Key_Return, False, None)   # disable autoindent

        self.__layout = QFormLayout()
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.__layout.addRow(f"<b>{i18n('Result')}</b>", self.__wceFormula)

        super(BCNodeWStrConcatenate, self).__init__(scene, title, connectors=[inputConnector, outputConnector], parent=parent)

        self.node().connectorLinked.connect(self.__checkInput)
        self.node().connectorUnlinked.connect(self.__checkInput)
        self.node().scene().sceneLoaded.connect(self.__checkInput)

        self.__minSize = self.calculateSize(f"{i18n('Result')+'X'*60}", 1, self.__layout.spacing(), self.__wceFormula.fontMetrics())

        self.setLayout(self.__layout)
        self.setMinimumSize(self.__minSize)

    def inputUpdated(self, inputId, value):
        """An input connector has been updated"""

        formula = []
        for connector in self.node().inputs():
            value = connector.value()
            if value is None:
                value = ""
            formula.append(value)
        formula = "".join(formula)
        self.__wceFormula.setPlainText(formula)

        size = self.calculateSize(f"{i18n('Result')+'X'*60+formula}", 1, self.__layout.spacing(), self.__wceFormula.fontMetrics())

        if size.width() < self.__minSize.width():
            size = self.__minSize

        self.setMinimumSize(size)

        self.updateOutput('Output', formula)

    def __checkInput(self, node=None, connector=None):
        """A connector has been connected/disconnected

        Check input connector (always need a have ONE available connector)
        - Add connector if needed
        - Remove connector if not needed
        """
        if node is None:
            node = self.node()

        if node.scene().inMassModification():
            return

        lastNumber = 1
        nbInputAvailable = 0
        toRemove = []
        for connector in reversed(node.connector()):
            if isinstance(connector, NodeEditorConnector) and connector.isInput():
                if r := re.match(r"Input(\d+)$", connector.id()):
                    lastNumber = max(lastNumber, int(r.groups()[0])+1)

                if len(connector.links()) == 0:
                    if nbInputAvailable == 0:
                        nbInputAvailable += 1
                    else:
                        toRemove.append(connector)

        for connector in toRemove:
            node.removeConnector(connector)

        if nbInputAvailable == 0:
            # no input connector available, add one
            inputConnector = NodeEditorConnector(f'Input{lastNumber}', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_TOP_LEFT)
            inputConnector.addAcceptedConnectionFrom(NodeEditorConnectorStr)
            node.addConnector(inputConnector)

    def deserialize(self, data):
        for connector in self.node().connector():
            if isinstance(connector, NodeEditorConnector) and len(connector.acceptedConnectionFrom()) == 0:
                # ensure that added connector (NodeEditorConnector) can only receive connection from NodeEditorConnectorStr
                connector.addAcceptedConnectionFrom(NodeEditorConnectorStr)


class BCNodeWRenameFormula(NodeEditorNodeWidget):
    """Main rename formula"""

    formulaUpdated = Signal(str)

    def __init__(self, scene, title, parent=None):
        inputConnector = NodeEditorConnector('Input1', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_TOP_LEFT)
        inputConnector.addAcceptedConnectionFrom(NodeEditorConnectorStr)

        self.__wceFormula = WCodeEditor()
        self.__wceFormula.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        self.__wceFormula.setLanguageDefinition(BCRenameFileVisualFormulaEditorDialogBox.LANGUAGEDEF)
        self.__wceFormula.setReadOnly(True)
        self.__wceFormula.setOptionMultiLine(False)
        self.__wceFormula.setOptionShowLineNumber(False)
        self.__wceFormula.setOptionShowIndentLevel(False)
        self.__wceFormula.setOptionShowRightLimit(False)
        self.__wceFormula.setOptionShowSpaces(False)
        self.__wceFormula.setOptionAllowWheelSetFontSize(False)
        self.__wceFormula.setShortCut(Qt.Key_Tab, False, None)      # disable indent
        self.__wceFormula.setShortCut(Qt.Key_Backtab, False, None)  # disable dedent
        self.__wceFormula.setShortCut(Qt.Key_Slash, True, None)     # disable toggle comment
        self.__wceFormula.setShortCut(Qt.Key_Return, False, None)   # disable autoindent

        self.__layout = QFormLayout()
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.__layout.addRow(f"<b>{i18n('Formula')}</b>", self.__wceFormula)

        super(BCNodeWRenameFormula, self).__init__(scene, title, connectors=[inputConnector], parent=parent)

        self.node().setId('renameFormula')
        self.node().setRemovable(False)

        self.node().connectorLinked.connect(self.__checkInput)
        self.node().connectorUnlinked.connect(self.__checkInput)
        self.node().scene().sceneLoaded.connect(self.__checkInput)

        self.__minSize = self.calculateSize(f"{i18n('Formula')+'X'*60}", 1, self.__layout.spacing(), self.__wceFormula.fontMetrics())

        self.setLayout(self.__layout)
        self.setMinimumSize(self.__minSize)

    def inputUpdated(self, inputId, value):
        """An input connector has been updated"""

        formula = []
        for connector in self.node().connector():
            # all connector are input connectors...
            value = connector.value()
            if value is None:
                value = ""
            formula.append(value)
        formula = "".join(formula)
        self.__wceFormula.setPlainText(formula)
        self.formulaUpdated.emit(formula)

        size = self.calculateSize(f"{i18n('Formula')+'XXXXXX'+formula}", 1, self.__layout.spacing(), self.__wceFormula.fontMetrics())

        if size.width() < 350:
            size.setWidth(350)

        self.setMinimumSize(size)

    def __checkInput(self, node=None, connector=None):
        """A connector has been connected/disconnected

        Check input connector (always need a have ONE available connector)
        - Add connector if needed
        - Remove connector if not needed
        """
        if node is None:
            node = self.node()

        if node.scene().inMassModification():
            return

        lastNumber = 1
        nbInputAvailable = 0
        toRemove = []
        for connector in reversed(node.connector()):
            if isinstance(connector, NodeEditorConnector):
                if r := re.match(r"Input(\d+)$", connector.id()):
                    lastNumber = max(lastNumber, int(r.groups()[0])+1)

                if len(connector.links()) == 0:
                    if nbInputAvailable == 0:
                        nbInputAvailable += 1
                    else:
                        toRemove.append(connector)

        for connector in toRemove:
            node.removeConnector(connector)

        if nbInputAvailable == 0:
            # no input connector available, add one
            inputConnector = NodeEditorConnector(f'Input{lastNumber}', NodeEditorConnector.DIRECTION_INPUT, NodeEditorConnector.LOCATION_TOP_LEFT)
            inputConnector.addAcceptedConnectionFrom(NodeEditorConnectorStr)
            node.addConnector(inputConnector)

    def deserialize(self, data={}):
        """From given dictionary, rebuild widget"""
        for connector in self.node().connector():
            if isinstance(connector, NodeEditorConnector) and len(connector.acceptedConnectionFrom()) == 0:
                # ensure that added connector (NodeEditorConnector) can only receive connection from NodeEditorConnector
                connector.addAcceptedConnectionFrom(NodeEditorConnectorStr)

    def formulaValue(self):
        """Return current formula value"""
        return self.__wceFormula.toPlainText()