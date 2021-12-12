#-----------------------------------------------------------------------------
# PyKritaToolKit
# Copyright (C) 2019-2021 - Grum999
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


# Basically inspired from https://www.blenderfreak.com/tutorials/node-editor-tutorial-series
# First tutorials are really interesting to easily and quickly understand basic stuff ("how to" implement)
# but quickly rewritten everything according to my own vision of things :-)

import math

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )

from ..pktk import *

# forward declaration of classes (needed for NodeEditorScene Signal declaration...)
class NodeEditorNode(QObject):
    pass
class NodeEditorConnector(QObject):
    pass
class NodeEditorLink(QObject):
    pass






class NodeEditorScene(QObject):
    """Define the scene content, independently from graphic scene"""
    # define zIndex for object in scene
    NODE_ZINDEX=0.0
    NODE_ZINDEX_FRONT=1.0

    LINK_ZINDEX=-1.0
    LINK_ZINDEX_FRONT=-0.5

    CUT_ZINDEX=-0.25

    # declare signals
    sizeChanged=Signal(QSize, QSize)                    # scene size changed: newSize, oldSize

    startLinkingItem=Signal()                           # linking item started: 'from' connector
    endLinkingItem=Signal()                             # linking item stopped: 'to' connector  (or None if no connector)

    nodeAdded=Signal(NodeEditorNode)                    # a new node has been added: added node
    nodeRemoved=Signal(NodeEditorNode)                  # a node has been removed: removed node
    linkAdded=Signal(NodeEditorLink)                    # a new link has been added: added link
    linkRemoved=Signal(NodeEditorLink)                  # a link has been removed: removed link

    nodeSelection=Signal()                              # node selection has changed
    linkSelection=Signal()                              # link selection has changed

    defaultLinkRenderModeChanged=Signal(int)            # default render mode for links has been modified
    defaultLinkColorChanged=Signal(QColor)              # default color value for links has been modified
    defaultLinkSelectedColorChanged=Signal(QColor)      # default color value for selected links has been modified
    defaultLinkSizeChanged=Signal(float)                # default size value for links has been modified

    defaultNodeTitleColorChanged=Signal(QColor)         # default title color value for nodes has been modified
    defaultNodeTitleBgColorChanged=Signal(QColor)       # default title background value for nodes has been modified
    defaultNodeTitleSelectedColorChanged=Signal(QColor) # default title color value for selected nodes has been modified
    defaultNodeTitleSelectedBgColorChanged=Signal(QColor)  # default title background value for selected nodes has been modified
    defaultNodeBgColorChanged=Signal(QColor)            # default background color value for nodes has been modified
    defaultNodeSelectedBgColorChanged=Signal(QColor)    # default background color value for selected nodes has been modified
    defaultNodeBorderRadiusChanged=Signal(float)        # default border radius value for nodes has been modified
    defaultNodeBorderSizeChanged=Signal(float)          # default border size value for nodes has been modified
    defaultNodePaddingChanged=Signal(int)               # default padding value for nodes has been modified

    defaultConnectorRadiusChanged=Signal(float)         # default radius value for connectors has been modified
    defaultConnectorBorderSizeChanged=Signal(float)     # default border size value for connectors has been modified
    defaultConnectorBorderColorChanged=Signal(QColor)   # default color value for border connectors has been modified
    defaultConnectorInputColorChanged=Signal(QColor)    # default color value for input connectors has been modified
    defaultConnectorOutputColorChanged=Signal(QColor)   # default color value for output connectors has been modified

    def __init__(self, parent=None):
        super(NodeEditorScene, self).__init__(parent)

        palette=QApplication.palette()

        # list of nodes
        self.__nodes=[]
        self.__links=[]

        # number of current selected nodes
        self.__selectedNodesCount=0
        # number of current selected links
        self.__selectedLinksCount=0

        # current linking item (link currently created/updated)
        self.__linkingItem=None

        # scene size
        self.__size=QSize()

        # graphic scene
        self.__grScene=NodeEditorGrScene(self)
        self.__grScene.selectionChanged.connect(self.__checkSelection)

        # default title color (text); when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodeColorTitle=palette.color(QPalette.BrightText)

        # default title color (background); when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodeColorBgTitle=palette.color(QPalette.Dark)

        # default title color (text - node selected); when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodeColorSelectedTitle=palette.color(QPalette.HighlightedText)

        # default title color (background - node selected); when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodeColorSelectedBgTitle=palette.color(QPalette.Highlight)

        # default node bg color (background); when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodeColorBgNode=palette.color(QPalette.Window)

        # default node bg color (background - node selected); when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodeColorBgNodesSelected=palette.color(QPalette.Window)

        # default border radius (corners); when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodeBorderRadius=6.0

        # default border size; when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodeBorderSize=2.0

        # default padding value; when None, use default from scene
        # (will be used by new NodeEditorNode if none is defined)
        self.__defaultNodePadding=6.0

        # default render mode for links
        # (will be used by new NodeEditorLink if none is defined)
        self.__defaultLinkRender=NodeEditorLink.RENDER_CURVE

        # default color for links
        # (will be used by new NodeEditorLink if none is defined)
        self.__defaultLinkColor=palette.color(QPalette.Dark)

        # default color for selected links
        # (will be used by new NodeEditorLink if none is defined)
        self.__defaultLinkColorSelected=palette.color(QPalette.Highlight)

        # default size for links (line width)
        # (will be used by new NodeEditorLink if none is defined)
        self.__defaultLinkSize=2.0

        # default radius for connectors
        # (will be used by new NodeEditorConnector if none is defined)
        self.__defaultConnectorRadius=6.0

        # default border size for connectors
        # (will be used by new NodeEditorConnector if none is defined)
        self.__defaultConnectorBorderSize=2.0

        # default input/output connector colors
        # (will be used by new NodeEditorConnector if none is defined)
        self.__defaultConnectorBorderColor=palette.color(QPalette.Dark)
        self.__defaultConnectorInputColor=QColor("#1e74fd")
        self.__defaultConnectorOutputColor=QColor("#1dfd8e")

        # define default scene size to 10000x10000 pixels
        self.setSize(QSize(10000, 10000))

    def __checkSelection(self):
        """Check current selected items"""
        nbSelectedNodes=len(self.selectedNodes())
        nbSelectedLinks=len(self.selectedNodes())

        if nbSelectedNodes!=self.__selectedNodesCount:
            # selection has changed
            self.__selectedNodesCount=nbSelectedNodes
            self.nodeSelection.emit()

        if nbSelectedLinks!=self.__selectedLinksCount:
            # selection has changed
            self.__selectedLinksCount=nbSelectedLinks
            self.linkSelection.emit()

    def addNode(self, node):
        """Add node to current scene"""
        if not node in self.__nodes:
            self.__nodes.append(node)
            self.__grScene.addItem(node.graphicItem())
            self.nodeAdded.emit(node)

    def removeNode(self, node):
        """Remove node from current scene

        If node is not found, does nothing
        """
        if node in self.__nodes:
            linksToRemove=[]
            for link in self.__links:
                if node==link.nodeFrom() or node==link.nodeTo():
                    linksToRemove.append(link)
            for link in linksToRemove:
                self.removeLink(link)

            self.__grScene.removeItem(node.graphicItem())
            self.__nodes.remove(node)
            self.nodeRemoved.emit(node)

    def addLink(self, link):
        """Add link to current scene"""
        if isinstance(link, NodeEditorLink) and not link in self.__links:
            self.__links.append(link)
            self.__grScene.addItem(link.graphicItem())
            if link!=self.__linkingItem and not link.connectorTo() is None:
                self.linkAdded.emit(link)

    def removeLink(self, link):
        """Remove `link` from current scene

        If `link` is not found, does nothing
        """
        if isinstance(link, NodeEditorLink) and link in self.__links:
            self.__grScene.removeItem(link.graphicItem())
            self.__links.remove(link)
            if link!=self.__linkingItem and not link.connectorTo() is None:
                self.linkRemoved.emit(link)
            # need to force cleanup
            del link

    def grScene(self):
        """Return current graphic scene"""
        return self.__grScene

    def size(self):
        """Return scene size"""
        return self.__size

    def setSize(self, size):
        """Set scene size"""
        if not isinstance(size, QSize):
            raise EInvalidType("Given `size` must be <QSize>")

        if size!=self.__size:
            oldSize=self.__size
            self.__size=size
            self.sizeChanged.emit(self.__size, oldSize)

    def linkingItem(self):
        """Return current linking item if any (a link that is currently linked
        to an output node but not yet linked to input node), otherwise return None"""
        return self.__linkingItem

    def setLinkingItem(self, item):
        """Set current linking item (a link that is currently linked
        to an output node but not yet linked to input node)

        Given `item` must be a <NodeEditorLink> or None

        If there's already a linking item, raise an error (this case should not occurs)
        """
        if item is None:
            self.removeLink(self.__linkingItem)
            self.__linkingItem=None
            self.endLinkingItem.emit()
        elif not isinstance(item, NodeEditorLink):
            raise EInvalidType("Given `item` must be <NodeEditorLink>")
        elif not self.__linkingItem is None:
            raise EInvalidStatus("There's already a linking item!")
        else:
            self.__linkingItem=item
            self.startLinkingItem.emit()

    def nodes(self):
        """Return all nodes"""
        return self.__nodes

    def selectedNodes(self):
        """Return all selected nodes"""
        return [node for node in self.__nodes if node.isSelected()]

    def links(self, item=None):
        """Return links

        If `item` is None, return all links
        If `item` is a <NodeEditorNode>, return all links connected (input/output) to node
        If `item` is a <NodeEditorConnector>, return all links connected to connector
        """
        if item is None:
            return self.__links
        elif isinstance(item, NodeEditorNode):
            returned=[]
            for link in self.__links:
                if link.connectorFrom().node()==item or link.connectorTo() and link.connectorTo().node()==item:
                    returned.append(link)
            return returned
        elif isinstance(item, NodeEditorConnector):
            returned=[]
            for link in self.__links:
                if link.connectorFrom()==item or link.connectorTo()==item:
                    returned.append(link)
            return returned

    def selectedLinks(self):
        """Return all selected links"""
        return [link for link in self.__links if link.isSelected()]

    def cursorScenePosition(self):
        """Return current position of mouse on scene"""
        return self.__grScene.cursorScenePosition()

    # -- default render settings for items in scene --

    def defaultNodeTitleColor(self):
        """Return default color value for nodes title"""
        return self.__defaultNodeColorTitle

    def setDefaultNodeTitleColor(self, value):
        """Set default color value for nodes title"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultNodeColorTitle=QColor(value)
                self.defaultNodeTitleColorChanged.emit(self.__defaultNodeColorTitle)
            except:
                # ignore invalid color...
                pass

    def defaultNodeTitleBgColor(self):
        """Return default color value for nodes background title"""
        return self.__defaultNodeColorBgTitle

    def setDefaultNodeTitleBgColor(self, value):
        """Set default color value for nodes background title"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultNodeColorBgTitle=QColor(value)
                self.defaultNodeTitleBgColorChanged.emit(self.__defaultNodeColorBgTitle)
            except:
                # ignore invalid color...
                pass

    def defaultNodeTitleSelectedColor(self):
        """Return default color value for selected nodes title"""
        return self.__defaultNodeColorSelectedTitle

    def setDefaultNodeTitleSelectedColor(self, value):
        """Set default color value for selected nodes title"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultNodeColorSelectedTitle=QColor(value)
                self.defaultNodeTitleSelectedColorChanged.emit(self.__defaultNodeColorSelectedTitle)
            except:
                # ignore invalid color...
                pass

    def defaultNodeTitleSelectedBgColor(self):
        """Return default color value for selected nodes title"""
        return self.__defaultNodeColorSelectedBgTitle

    def setDefaultNodeTitleSelectedBgColor(self, value):
        """Set default color value for selected nodes title"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultNodeColorSelectedBgTitle=QColor(value)
                self.defaultNodeTitleSelectedBgColorChanged.emit(self.__defaultNodeColorSelectedBgTitle)
            except:
                # ignore invalid color...
                pass

    def defaultNodeBgColor(self):
        """Return default color value for selected nodes title"""
        return self.__defaultNodeColorBgNode

    def setDefaultNodeBgColor(self, value):
        """Set default color value for selected nodes title"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultNodeColorBgNode=QColor(value)
                self.defaultNodeBgColorChanged.emit(self.__defaultNodeColorBgNode)
            except:
                # ignore invalid color...
                pass

    def defaultNodeSelectedBgColor(self):
        """Return default color value for selected nodes title"""
        return self.__defaultNodeColorBgNodesSelected

    def setDefaultNodeSelectedBgColor(self, value):
        """Set default color value for selected nodes title"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultNodeColorBgNodesSelected=QColor(value)
                self.defaultNodeSelectedBgColorChanged.emit(self.__defaultNodeColorBgNodesSelected)
            except:
                # ignore invalid color...
                pass

    def defaultNodeBorderSize(self):
        """Return default border size value for connectors"""
        return self.__defaultNodeBorderSize

    def setDefaultNodeBorderSize(self, value):
        """Set default size value for connectors"""
        if isinstance(value, (int, float)) and value>=0:
            self.__defaultNodeBorderSize=float(value)
            self.defaultNodeBorderSizeChanged.emit(self.__defaultNodeBorderSize)

    def defaultNodeBorderRadius(self):
        """Return default radius value for connectors"""
        return self.__defaultNodeBorderRadius

    def setDefaultNodeBorderRadius(self, value):
        """Set default radius value for connectors"""
        if isinstance(value, (int, float)) and value>=0 and self.__defaultNodeBorderRadius!=value:
            self.__defaultNodeBorderRadius=float(value)
            self.defaultNodeBorderRadiusChanged.emit(self.__defaultNodeBorderRadius)

    def defaultNodePadding(self):
        """Return default radius value for connectors"""
        return self.__defaultNodePadding

    def setDefaultNodePadding(self, value):
        """Set default radius value for connectors"""
        if isinstance(value, (int, float)) and value>=0 and self.__defaultNodePadding!=value:
            self.__defaultNodePadding=float(value)
            self.defaultNodePaddingChanged.emit(self.__defaultNodePadding)

    def defaultLinkRenderMode(self):
        """Return default render value for links"""
        return self.__defaultLinkRender

    def setDefaultLinkRenderMode(self, value):
        """Set default render value for links"""
        if value in (NodeEditorLink.RENDER_CURVE, NodeEditorLink.RENDER_DIRECT, NodeEditorLink.RENDER_ANGLE) and self.__defaultLinkRender!=value:
            self.__defaultLinkRender=value
            self.defaultLinkRenderModeChanged.emit(self.__defaultLinkRender)

    def defaultLinkColor(self):
        """Return default color value for links"""
        return self.__defaultLinkColor

    def setDefaultLinkColor(self, value):
        """Set default color value for links"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultLinkColor=QColor(value)
                self.defaultLinkColorChanged.emit(self.__defaultLinkColor)
            except:
                # ignore invalid color...
                pass

    def defaultLinkColorSelected(self):
        """Return default color value for selected links"""
        return self.__defaultLinkColorSelected

    def setDefaultLinkColorSelected(self, value):
        """Set default color value for selected links"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultLinkColorSelected=QColor(value)
                self.defaultLinkSelectedColorChanged.emit(self.__defaultLinkColorSelected)
            except:
                # ignore invalid color...
                pass

    def defaultLinkSize(self):
        """Return default size value for links"""
        return self.__defaultLinkSize

    def setDefaultLinkSize(self, value):
        """Set default size value for links"""
        if isinstance(value, (int, float)) and value>0:
            self.__defaultLinkSize=float(value)
            self.defaultLinkSizeChanged.emit(self.__defaultLinkSize)

    def defaultConnectorBorderSize(self):
        """Return default border size value for connectors"""
        return self.__defaultConnectorBorderSize

    def setDefaultConnectorBorderSize(self, value):
        """Set default size value for connectors"""
        if isinstance(value, (int, float)) and value>=0:
            self.__defaultConnectorBorderSize=float(value)
            self.defaultConnectorBorderSizeChanged.emit(self.__defaultConnectorBorderSize)

    def defaultConnectorRadius(self):
        """Return default radius value for connectors"""
        return self.__defaultConnectorRadius

    def setDefaultConnectorRadius(self, value):
        """Set default radius value for connectors"""
        if isinstance(value, (int, float)) and value > 0 and self.__defaultConnectorRadius!=value:
            self.__defaultConnectorRadius=value
            self.defaultConnectorRadiusChanged.emit(self.__defaultConnectorRadius)

    def defaultConnectorBorderColor(self):
        """Return default border color value for connectors"""
        return self.__defaultConnectorBorderColor

    def setDefaultConnectorBorderColor(self, value):
        """Set default border color value for connectors"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultConnectorBorderColor=QColor(value)
                self.defaultConnectorBorderColorChanged.emit(self.__defaultConnectorBorderColor)
            except:
                # ignore invalid color...
                pass

    def defaultConnectorInputColor(self):
        """Return default color value for input connectors"""
        return self.__defaultConnectorInputColor

    def setDefaultConnectorInputColor(self, value):
        """Set default color value for input connectors"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultConnectorInputColor=QColor(value)
                self.defaultConnectorInputColorChanged.emit(self.__defaultConnectorInputColor)
            except:
                # ignore invalid color...
                pass

    def defaultConnectorOutputColor(self):
        """Return default color value for output connectors"""
        return self.__defaultConnectorOutputColor

    def setDefaultConnectorOutputColor(self, value):
        """Set default color value for output connectors"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultConnectorOutputColor=QColor(value)
                self.defaultConnectorOutputColorChanged.emit(self.__defaultConnectorOutputColor)
            except:
                # ignore invalid color...
                pass


class NodeEditorNode(QObject):
    """Define a node, independently from graphic rendered item"""
    titleChanged=Signal(NodeEditorNode)                                         # node title has been changed: current node
    titleColorChanged=Signal(QColor)                                            # title text color has been changed
    titleBgColorChanged=Signal(QColor)                                          # title background color has been changed (also used for border color)
    titleSelectedColorChanged=Signal(QColor)                                    # title text color (when node is selected) has been changed
    titleSelectedBgColorChanged=Signal(QColor)                                  # title background color (when node is selected) has been changed
    nodeBgColorChanged=Signal(QColor)                                           # node background color has been changed
    nodeSelectedBgColorChanged=Signal(QColor)                                   # node background color (when node is selected) has been changed
    borderRadiusChanged=Signal(float)                                           # border radius has been changed
    borderSizeChanged=Signal(float)                                             # border size has been changed
    paddingChanged=Signal(int)                                                  # padding value has been changed

    selectionChanged=Signal(bool)                                               # node selection state has been changed: boolean True=Selected/False=Unselected
    positionChanged=Signal(QPointF)                                             # node position has been modified: position as QPointF

    connectorLinked=Signal(NodeEditorNode, NodeEditorConnector)                 # a connector has been connected: node and concerned connector
    connectorUnlinked=Signal(NodeEditorNode, NodeEditorConnector)               # a connector has been disconnected: node and concerned connector

    inputValueChanged=Signal(NodeEditorConnector)
    outputValueChanged=Signal(NodeEditorConnector)

    defaultConnectorRadiusChanged=Signal(float)                                 # default radius for connector has been changed: new radius value as float
    defaultConnectorBorderSizeChanged=Signal(float)                             # default border size for connector has been changed: new value as float
    defaultConnectorBorderColorChanged=Signal(QColor)                           # default border color for connector has been changed: new color value
    defaultConnectorInputColorChanged=Signal(QColor)                            # default color for input connector has been changed: new color value
    defaultConnectorOutputColorChanged=Signal(QColor)                           # default color for output connector has been changed: new color value

    def __init__(self, scene, title, connectors=[], parent=None):
        super(NodeEditorNode, self).__init__(parent)

        if not isinstance(scene, NodeEditorScene):
            raise EInvalidType("Given `scene` must be <NodeEditorScene>")

        # parent scene
        self.__scene=scene
        self.__scene.defaultNodeTitleColorChanged.connect(self.__defaultSceneNodeTitleColorChanged)
        self.__scene.defaultNodeTitleBgColorChanged.connect(self.__defaultSceneNodeTitleBgColorChanged)
        self.__scene.defaultNodeTitleSelectedColorChanged.connect(self.__defaultSceneNodeTitleSelectedColorChanged)
        self.__scene.defaultNodeTitleSelectedBgColorChanged.connect(self.__defaultSceneNodeTitleSelectedBgColorChanged)
        self.__scene.defaultNodeBgColorChanged.connect(self.__defaultSceneNodeBgColorChanged)
        self.__scene.defaultNodeSelectedBgColorChanged.connect(self.__defaultSceneNodeSelectedBgColorChanged)
        self.__scene.defaultNodeBorderRadiusChanged.connect(self.__defaultSceneNodeBorderRadiusChanged)
        self.__scene.defaultNodeBorderSizeChanged.connect(self.__defaultSceneNodeBorderSizeChanged)
        self.__scene.defaultNodePaddingChanged.connect(self.__defaultSceneNodePaddingChanged)

        self.__scene.defaultConnectorRadiusChanged.connect(self.__defaultSceneConnectorRadiusChanged)
        self.__scene.defaultConnectorBorderSizeChanged.connect(self.__defaultSceneConnectorBorderSizeChanged)
        self.__scene.defaultConnectorBorderColorChanged.connect(self.__defaultSceneConnectorBorderColorChanged)
        self.__scene.defaultConnectorInputColorChanged.connect(self.__defaultSceneConnectorInputColorChanged)
        self.__scene.defaultConnectorOutputColorChanged.connect(self.__defaultSceneConnectorOutputColorChanged)
        self.__scene.linkAdded.connect(self.__checkAddedLink)
        self.__scene.linkRemoved.connect(self.__checkRemovedLink)

        # title (str) for node
        self.__title=title

        # title color (text); when None, use default from scene
        self.__colorTitle=None

        # title color (background); when None, use default from scene
        self.__colorBgTitle=None

        # title color (text - node selected); when None, use default from scene
        self.__colorSelectedTitle=None

        # title color (background - node selected); when None, use default from scene
        self.__colorSelectedBgTitle=None

        # node bg color (background); when None, use default from scene
        self.__colorBgNode=None

        # node bg color (background - node selected); when None, use default from scene
        self.__colorBgNodesSelected=None

        # border radius (corners); when None, use default from scene
        self.__borderRadius=None

        # border size; when None, use default from scene
        self.__borderSize=None

        # default border size for connectors
        # when None, border size from scene is used, otherwise border size from node is used
        self.__defaultConnectorBorderSize=None

        # default radius for connectors
        # when None, radius from scene is used, otherwise radius from node is used
        self.__defaultConnectorRadius=None
        # space between 2 connectors = default radius size + 25%
        self.__connectorSpace=round(self.defaultConnectorRadius()*1.25)

        # default input/output connector colors
        # when None, default colors from scene are used, otherwise color from node are used
        self.__defaultConnectorBorderColor=None
        self.__defaultConnectorInputColor=None
        self.__defaultConnectorOutputColor=None

        # connectors for nodes
        # a dictionary for which:
        # - key = connector identifier
        # - value = connector
        self.__connectors={}

        # selection state
        self.__isSelected=False

        # define node's padding
        self.__padding=None

        # QGraphicsItem for node
        self.__grItem=NodeEditorGrNode(self)

        # add curent node to scene
        self.__scene.addNode(self)

        # counters maintain number of connector for each node's corners
        self.__nbLeftTop=0
        self.__nbLeftBottom=0
        self.__nbRightTop=0
        self.__nbRightBottom=0
        self.__nbTopLeft=0
        self.__nbTopRight=0
        self.__nbBottomLeft=0
        self.__nbBottomRight=0

        self.__minSizeUserDefined=QSize(200, 200)
        self.__minSizeCalculated=QSize(self.__minSizeUserDefined)

        # add connectors to node, if some given
        for connector in connectors:
            self.addConnector(connector)

        self.titleColorChanged.emit(self.titleColor())
        self.titleBgColorChanged.emit(self.titleBgColor())
        self.titleSelectedColorChanged.emit(self.titleSelectedColor())
        self.titleSelectedBgColorChanged.emit(self.titleSelectedBgColor())
        self.nodeBgColorChanged.emit(self.nodeBgColor())
        self.nodeSelectedBgColorChanged.emit(self.nodeSelectedBgColor())
        self.borderRadiusChanged.emit(self.borderRadius())
        self.borderSizeChanged.emit(self.borderSize())

    def __updateMinSize(self):
        """Update minimum size for node"""
        self.__grItem.setMinimumSize(self.__minSizeUserDefined.expandedTo(self.__minSizeCalculated))

        # size has been updated; update connectors position
        for key in self.__connectors:
            # no value => just recalculate automatically position according to node's size
            self.__connectors[key].setPosition()

    def __updateConnectorPosition(self, connector, index, minPosition):
        """Calculate and update position for given `connector` at given `index`"""
        position=2*self.defaultConnectorRadius()+self.__connectorSpace + self.defaultConnectorBorderSize()
        connector.setPosition(index*position+minPosition)
        return connector.position()

    def __updateAllConnectorPosition(self):
        """recalculate and update position for all connector"""
        # 'local' counters maintain number of connector for each node's corners
        nbLeftTop=0
        nbLeftBottom=0
        nbRightTop=0
        nbRightBottom=0
        nbTopLeft=0
        nbTopRight=0
        nbBottomLeft=0
        nbBottomRight=0

        # maintain position for each corner
        # used to determinate minimum width/height needed for node to not have
        # overlapped connectors
        maxPositionLeftTop=0
        maxPositionLeftBottom=0
        maxPositionRightTop=0
        maxPositionRightBottom=0
        maxPositionTopLeft=0
        maxPositionTopRight=0
        maxPositionBottomLeft=0
        maxPositionBottomRight=0

        offsetPositionLeftTop=0
        offsetPositionLeftBottom=0
        offsetPositionRightTop=0
        offsetPositionRightBottom=0
        offsetPositionTopLeft=0
        offsetPositionTopRight=0
        offsetPositionBottomLeft=0
        offsetPositionBottomRight=0

        titleHeight=self.__grItem.titleSize().height()

        for key in self.__connectors:
            connector=self.__connectors[key]

            connectorRadius=connector.radius()
            minPosition=self.borderRadius()+2*connectorRadius
            minPositionTop=max(minPosition, titleHeight+2*connectorRadius)

            if connector.location()==NodeEditorConnector.LOCATION_LEFT_TOP:
                maxPositionLeftTop=self.__updateConnectorPosition(connector, nbLeftTop, minPositionTop)
                nbLeftTop+=1
                offsetPositionLeftTop+=connectorRadius
            elif connector.location()==NodeEditorConnector.LOCATION_LEFT_BOTTOM:
                maxPositionLeftBottom=self.__updateConnectorPosition(connector, nbLeftBottom, minPosition)
                nbLeftBottom+=1
                offsetPositionLeftBottom+=connectorRadius
            elif connector.location()==NodeEditorConnector.LOCATION_RIGHT_TOP:
                maxPositionRightTop=self.__updateConnectorPosition(connector, nbRightTop, minPositionTop)
                nbRightTop+=1
                offsetPositionRightTop+=connectorRadius
            elif connector.location()==NodeEditorConnector.LOCATION_RIGHT_BOTTOM:
                maxPositionRightBottom=self.__updateConnectorPosition(connector, nbRightBottom, minPosition)
                nbRightBottom+=1
                offsetPositionRightBottom+=connectorRadius
            elif connector.location()==NodeEditorConnector.LOCATION_TOP_LEFT:
                maxPositionTopLeft=self.__updateConnectorPosition(connector, nbTopLeft, minPosition)
                nbTopLeft+=1
                offsetPositionTopLeft+=connectorRadius
            elif connector.location()==NodeEditorConnector.LOCATION_TOP_RIGHT:
                maxPositionTopRight=self.__updateConnectorPosition(connector, nbTopRight, minPosition)
                nbTopRight+=1
                offsetPositionTopRight+=connectorRadius
            elif connector.location()==NodeEditorConnector.LOCATION_BOTTOM_LEFT:
                maxPositionBottomLeft=self.__updateConnectorPosition(connector, nbBottomLeft, minPosition)
                nbBottomLeft+=1
                offsetPositionBottomLeft+=connectorRadius
            elif connector.location()==NodeEditorConnector.LOCATION_BOTTOM_RIGHT:
                maxPositionBottomRight=self.__updateConnectorPosition(connector, nbBottomRight, minPosition)
                nbBottomRight+=1
                offsetPositionBottomRight+=connectorRadius

        self.__minSizeCalculated=QSize(2*self.__connectorSpace+max(offsetPositionTopLeft+offsetPositionTopRight+maxPositionTopLeft+maxPositionTopRight, offsetPositionBottomLeft+offsetPositionBottomRight+maxPositionBottomLeft+maxPositionBottomRight),
                                       2*self.__connectorSpace+max(offsetPositionLeftTop+offsetPositionLeftBottom+maxPositionLeftTop+maxPositionLeftBottom, offsetPositionRightTop+offsetPositionRightBottom+maxPositionRightTop+maxPositionRightBottom))
        self.__updateMinSize()

    def __defaultSceneNodeTitleColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__colorTitle is None:
            self.titleColorChanged.emit(value)

    def __defaultSceneNodeTitleBgColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__colorBgTitle is None:
            self.titleBgColorChanged.emit(value)

    def __defaultSceneNodeTitleSelectedColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__colorSelectedTitle is None:
            self.titleSelectedColorChanged.emit(value)

    def __defaultSceneNodeTitleSelectedBgColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__colorSelectedBgTitle is None:
            self.titleSelectedBgColorChanged.emit(value)

    def __defaultSceneNodeBgColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__colorBgNode is None:
            self.nodeBgColorChanged.emit(value)

    def __defaultSceneNodeSelectedBgColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__colorBgNodesSelected is None:
            self.nodeSelectedBgColorChanged.emit(value)

    def __defaultSceneNodeBorderRadiusChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__borderRadius is None:
            self.borderRadiusChanged.emit(value)
            self.__updateAllConnectorPosition()

    def __defaultSceneNodeBorderSizeChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__borderSize is None:
            self.borderSizeChanged.emit(value)

    def __defaultSceneNodePaddingChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__padding is None:
            self.paddingChanged.emit(value)

    def __defaultSceneConnectorRadiusChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__defaultConnectorRadius is None:
            self.defaultConnectorRadiusChanged.emit(value)
            self.__updateAllConnectorPosition()

    def __defaultSceneConnectorBorderSizeChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__defaultConnectorBorderSize is None:
            self.defaultConnectorBorderSizeChanged.emit(value)
            self.__updateAllConnectorPosition()

    def __defaultSceneConnectorBorderColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__defaultConnectorBorderColor is None:
            self.defaultConnectorBorderColorChanged.emit(value)

    def __defaultSceneConnectorInputColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__defaultConnectorInputColor is None:
            self.defaultConnectorInputColorChanged.emit(value)

    def __defaultSceneConnectorOutputColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__defaultConnectorOutputColor is None:
            self.defaultConnectorOutputColorChanged.emit(value)

    def __checkAddedLink(self, link):
        """Check if added link is connected to node and emit signal if needed"""
        if link.connectorFrom().node()==self:
            self.connectorLinked.emit(self, link.connectorFrom())
        elif link.connectorTo().node()==self:
            self.connectorLinked.emit(self, link.connectorFrom())

    def __checkRemovedLink(self, link):
        """Check if removed link was connected to node and emit signal if needed"""
        if link.connectorFrom().node()==self:
            self.connectorUnlinked.emit(self, link.connectorFrom())
        elif link.connectorTo().node()==self:
            self.connectorUnlinked.emit(self, link.connectorTo())

    def itemChange(self, change, value):
        """Something has been changed on graphic item

        Emit signal if needed
        """
        if change==QGraphicsItem.ItemSelectedChange:
            if value:
                # move node to front
                self.__grItem.setZValue(NodeEditorScene.NODE_ZINDEX_FRONT)
            else:
                # restore node to initial zIndex
                self.__grItem.setZValue(NodeEditorScene.NODE_ZINDEX)
            self.__isSelected=bool(value)
            self.selectionChanged.emit(self.__isSelected)
        elif change==QGraphicsItem.ItemPositionHasChanged:
            self.positionChanged.emit(value)

    def isSelected(self):
        """Return if current node is selected"""
        return self.__isSelected

    def setSelected(self, selectionStatus=True):
        """Select/Deselect item"""
        if selectionStatus!=self.__isSelected and isinstance(selectionStatus, bool):
            self.__grItem.setSelected(selectionStatus)

    def graphicItem(self):
        """Return graphic item for node"""
        return self.__grItem

    def connector(self, id=None):
        """Return connector for given `id` or all connectors (as a list) if `id` is None

        If no connector is found for given `id`, return None
        """
        if id is None:
            return [self.__connectors[key] for key in self.__connectors]
        elif id in self.__connectors:
            return self.__connectors[id]
        else:
            return None

    def inputs(self):
        """Return a list of inputs connectors"""
        return [self.__connectors[connector] for connector in self.__connectors if self.__connectors[connector].isInput()]

    def outputs(self):
        """Return a list of outputs connectors"""
        return [self.__connectors[connector] for connector in self.__connectors if self.__connectors[connector].isOutput()]

    def scene(self):
        """Return scene in which node is defined"""
        return self.__scene

    def title(self):
        """Return current title"""
        return self.__title

    def setTitle(self, title):
        """Define title for node"""
        if self.__title!=title:
            self.__title=title
            self.titleChanged.emit(self)

    def position(self):
        """Return current position in scene (as QPointF)"""
        return self.__grItem.pos()

    def setPosition(self, position):
        """Define position in scene for Node

        Given `position` is a QPointF
        """
        self.__grItem.setPos(position)

    def addConnector(self, connector):
        """Add a connector

        Given `connector` must be <NodeEditorConnector>
        If a connector already exists with the same identifier, connector is not added, and method return False
        Otherwise, connector is added and method return True
        """
        if not isinstance(connector, NodeEditorConnector):
            raise EInvalidType("Given `connector` must be <NodeEditorConnector>")

        if not connector.id() in self.__connectors:
            # add connector only if no connector with same identifier already exists
            connector.setNode(self)
            self.__connectors[connector.id()]=connector

            self.defaultConnectorRadiusChanged.emit(self.defaultConnectorRadius())
            self.defaultConnectorBorderSizeChanged.emit(self.defaultConnectorBorderSize())
            self.defaultConnectorBorderColorChanged.emit(self.defaultConnectorBorderColor())
            self.defaultConnectorInputColorChanged.emit(self.defaultConnectorInputColor())
            self.defaultConnectorOutputColorChanged.emit(self.defaultConnectorOutputColor())

            # need to recalculate positions
            self.__updateAllConnectorPosition()
            return True

        return False

    def removeConnector(self, connector):
        """Add a connector

        Given `connector` must be <NodeEditorConnector> or a <str> (connector's identifier value)

        If connector doesn't exists for node, connector is not removed, and method return False
        Otherwise, connector is removed and method return True
        """
        if not isinstance(connector, (str, NodeEditorConnector)):
            raise EInvalidType("Given `connector` must be <NodeEditorConnector> or <str>")

        if isinstance(connector, str):
            # a connector identifier has been provided
            # retrieve NodeEditorConnector
            connector=self.connector(connector)
            if connector is None:
                # no connector found? can't remove it
                return False

        if connector.id() in self.__connectors:
            # remove connector only if exists
            self.__connectors.pop(connector.id())
            # need to recalculate positions
            self.__updateAllConnectorPosition()
            return True

        return False

    def titleColor(self):
        """Return color for title text (unselected node)"""
        if self.__colorTitle is None:
            return self.__scene.defaultNodeTitleColor()
        return self.__colorTitle

    def setTitleColor(self, value):
        """Set color for title text (unselected node)"""
        if isinstance(value, (QColor, str)):
            try:
                self.__colorTitle=QColor(value)
                self.titleColorChanged.emit(self.titleColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__colorTitle=None
            self.titleColorChanged.emit(self.titleColor())

    def titleBgColor(self):
        """Return color for title background (unselected node)"""
        if self.__colorBgTitle is None:
            return self.__scene.defaultNodeTitleBgColor()
        return self.__colorBgTitle

    def setTitleBgColor(self, value):
        """Set color for title background (unselected node)"""
        if isinstance(value, (QColor, str)):
            try:
                self.__colorBgTitle=QColor(value)
                self.titleBgColorChanged.emit(self.titleBgColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__colorBgTitle=None
            self.titleBgColorChanged.emit(self.titleBgColor())

    def titleSelectedColor(self):
        """Return color for title text (selected node)"""
        if self.__colorSelectedTitle is None:
            return self.__scene.defaultNodeTitleSelectedColor()
        return self.__colorSelectedTitle

    def setTitleSelectedColor(self, value):
        """Set color for title text (selected node)"""
        if isinstance(value, (QColor, str)):
            try:
                self.__colorSelectedTitle=QColor(value)
                self.titleSelectedColorChanged.emit(self.titleSelectedColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__colorSelectedTitle=None
            self.titleSelectedColorChanged.emit(self.titleSelectedColor())

    def titleSelectedBgColor(self):
        """Return color for title background (selected node)"""
        if self.__colorSelectedBgTitle is None:
            return self.__scene.defaultNodeTitleSelectedBgColor()
        return self.__colorSelectedBgTitle

    def setTitleSelectedBgColor(self, value):
        """Set color for title background (selected node)"""
        if isinstance(value, (QColor, str)):
            try:
                self.__colorSelectedBgTitle=QColor(value)
                self.titleSelectedBgColorChanged.emit(self.titleSelectedBgColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__colorSelectedBgTitle=None
            self.titleSelectedBgColorChanged.emit(self.titleSelectedBgColor())

    def nodeBgColor(self):
        """Return color for node background (unselected node)"""
        if self.__colorBgNode is None:
            return self.__scene.defaultNodeBgColor()
        return self.__colorBgNode

    def setNodeBgColor(self, value):
        """Set color for node background (unselected node)"""
        if isinstance(value, (QColor, str)):
            try:
                self.__colorBgNode=QColor(value)
                self.nodeBgColorChanged.emit(self.nodeBgColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__colorBgNode=None
            self.nodeBgColorChanged.emit(self.nodeBgColor())

    def nodeSelectedBgColor(self):
        """Return color for node background (selected node)"""
        if self.__colorBgNodesSelected is None:
            return self.__scene.defaultNodeSelectedBgColor()
        return self.__colorBgNodesSelected

    def setNodeSelectedBgColor(self, value):
        """Set color for node background (selected node)"""
        if isinstance(value, (QColor, str)):
            try:
                self.__colorBgNodesSelected=QColor(value)
                self.nodeSelectedBgColorChanged.emit(self.nodeSelectedBgColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__colorBgNodesSelected=None
            self.nodeSelectedBgColorChanged.emit(self.nodeSelectedBgColor())

    def boundingRect(self):
        """Return node size"""
        return self.__grItem.boundingRect()

    def minimumSize(self):
        """return minimum size for node"""
        return self.__minSizeUserDefined

    def setMinimumSize(self, value):
        """Set minimum size for node"""
        if (value is None or isinstance(value, (int, float))) and self.__minSizeUserDefined!=value:
            self.__minSizeUserDefined=value
            self.__updateMinSize()

    def borderSize(self):
        """Return current connector border size (in pixels)"""
        if self.__borderSize is None:
            return self.__scene.defaultNodeBorderSize()
        return self.__borderSize

    def setBorderSize(self, value):
        """Set current connector border size (in pixels)"""
        if (value is None or isinstance(value, (int, float))) and self.__borderSize!=value:
            self.__borderSize=value
            self.borderSizeChanged.emit(self.borderSize())

    def borderRadius(self):
        """Return current connector radius (in pixels)"""
        if self.__borderRadius is None:
            return self.__scene.defaultNodeBorderRadius()
        return self.__borderRadius

    def setBorderRadius(self, value):
        """Set current connector radius (in pixels)"""
        if (value is None or isinstance(value, (int, float))) and self.__radius!=value:
            self.__borderRadius=value
            self.borderRadiusChanged.emit(self.borderRadius())
            self.__updateAllConnectorPosition()

    def padding(self):
        """Return current node padding value"""
        if self.__padding is None:
            return self.__scene.defaultNodePadding()
        return self.__padding

    def setPadding(self, value):
        """Set current node padding value"""
        if (value is None or isinstance(value, (int, float))) and self.__padding!=value:
            self.__padding=value
            self.paddingChanged.emit(self.padding())

    def defaultConnectorBorderSize(self):
        """Return default border size value for connectors

        If no default border size value is defined, return default scene value
        """
        if self.__defaultConnectorBorderSize is None:
            return self.__scene.defaultConnectorBorderSize()
        return self.__defaultConnectorBorderSize

    def setDefaultConnectorBorderSize(self, value):
        """Set default border size value for node's connectors"""
        if (value is None or isinstance(value, (int, float))) and self.__defaultConnectorBorderSize!=value:
            self.__defaultConnectorBorderSize=value
            self.defaultConnectorBorderSizeChanged.emit(self.defaultConnectorBorderSize())
            self.__updateAllConnectorPosition()

    def defaultConnectorRadius(self):
        """Return default radius value for connectors

        If no default radius value is defined, return default scene value
        """
        if self.__defaultConnectorRadius is None:
            return self.__scene.defaultConnectorRadius()
        return self.__defaultConnectorRadius

    def setDefaultConnectorRadius(self, value):
        """Set default radius value for node's connectors"""
        if (value is None or isinstance(value, (int, float))) and self.__defaultConnectorRadius!=value:
            self.__defaultConnectorRadius=value
            self.__connectorSpace=round(self.defaultConnectorRadius()*1.25)
            self.defaultConnectorRadiusChanged.emit(self.defaultConnectorRadius())
            self.__updateAllConnectorPosition()

    def defaultConnectorBorderColor(self):
        """Return default border color value for connectors"""
        if self.__defaultConnectorBorderColor is None:
            return self.__scene.defaultConnectorBorderColor()
        return self.__defaultConnectorBorderColor

    def setDefaultConnectorBorderColor(self, value):
        """Set default color border value for connectors"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultConnectorBorderColor=QColor(value)
                self.defaultConnectorBorderColorChanged.emit(self.defaultConnectorBorderColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__defaultConnectorBorderColor=None
            self.defaultConnectorBorderColorChanged.emit(self.defaultConnectorBorderColor())

    def defaultConnectorInputColor(self):
        """Return default color value for input connectors"""
        if self.__defaultConnectorInputColor is None:
            return self.__scene.defaultConnectorInputColor()
        return self.__defaultConnectorInputColor

    def setDefaultConnectorInputColor(self, value):
        """Set default color value for input connectors"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultConnectorInputColor=QColor(value)
                self.defaultConnectorInputColorChanged.emit(self.defaultConnectorInputColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__defaultConnectorInputColor=None
            self.defaultConnectorInputColorChanged.emit(self.defaultConnectorInputColor())

    def defaultConnectorOutputColor(self):
        """Return default color value for output connectors"""
        if self.__defaultConnectorOutputColor is None:
            return self.__scene.defaultConnectorOutputColor()
        return self.__defaultConnectorOutputColor

    def setDefaultConnectorOutputColor(self, value):
        """Set default color value for output connectors"""
        if isinstance(value, (QColor, str)):
            try:
                self.__defaultConnectorOutputColor=QColor(value)
                self.defaultConnectorOutputColorChanged.emit(self.defaultConnectorOutputColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__defaultConnectorOutputColor=None
            self.defaultConnectorOutputColorChanged.emit(self.defaultConnectorOutputColor())


class NodeEditorConnector(QObject):
    """Define a connection for a node (input/output connection)"""
    radiusChanged=Signal(float)
    borderSizeChanged=Signal(float)
    colorChanged=Signal(QColor)
    borderColorChanged=Signal(QColor)

    # position define position in which connector is defined
    LOCATION_LEFT_TOP =     0x00000001
    LOCATION_LEFT_BOTTOM =  0x00000010
    LOCATION_RIGHT_TOP =    0x00000100
    LOCATION_RIGHT_BOTTOM = 0x00001000
    LOCATION_TOP_LEFT =     0x00010000
    LOCATION_TOP_RIGHT =    0x00100000
    LOCATION_BOTTOM_LEFT =  0x01000000
    LOCATION_BOTTOM_RIGHT = 0x10000000

    # define connector direction
    DIRECTION_INPUT=0x01
    DIRECTION_OUTPUT=0x02

    def __init__(self, id=None, direction=0x01, location=0x01, color=None, borderColor=None, borderSize=None, parent=None):
        super(NodeEditorConnector, self).__init__(parent)

        if not location in (
                    NodeEditorConnector.LOCATION_LEFT_TOP,
                    NodeEditorConnector.LOCATION_LEFT_BOTTOM,
                    NodeEditorConnector.LOCATION_RIGHT_TOP,
                    NodeEditorConnector.LOCATION_RIGHT_BOTTOM,
                    NodeEditorConnector.LOCATION_TOP_LEFT,
                    NodeEditorConnector.LOCATION_TOP_RIGHT,
                    NodeEditorConnector.LOCATION_BOTTOM_LEFT,
                    NodeEditorConnector.LOCATION_BOTTOM_RIGHT):
            raise EInvalidValue("Given `location` is not valid")

        if not direction in (
                    NodeEditorConnector.DIRECTION_INPUT,
                    NodeEditorConnector.DIRECTION_OUTPUT):
            raise EInvalidValue("Given `direction` is not valid")

        if id is None:
            # no identifier provided, generate a default one
            id=QUuid.createUuid().toString()

        if not isinstance(id, str):
            raise EInvalidType("Given `id` must be None or <str>")
        elif id=='':
            raise EInvalidValue("Given `id` can't be empty")

        # unique identifier for connector allows to access easily to them from node
        self.__id=id
        # direction define if connector is Input/Output connector
        self.__direction=direction

        # position in pixel (relative to location start)
        self.__position=0

        # location defines node's corner on which connector is located
        self.__location=location

        # internal list of links connected to this connector
        # => the list is maintained by checkLinks() method, normaly called when
        #    a link
        self.__links=[]

        # define a list of accepted connection (item in list are NodeEditorConnector class types)
        # if empty, accept all connections
        self.__acceptedConnectionFrom=[]

        # connector border size
        # if None, use node default connector border size value
        self.__borderSize=None

        # connector radius
        # if None, use node default connector radius value
        self.__radius=None

        # connector border color
        # if None, use node default connector radius value
        if isinstance(borderColor, (QColor, str)):
            self.__borderColor=QColor(borderColor)
        else:
            self.__borderColor=None

        # connector color
        # if None, use node default connector radius value
        if isinstance(color, (QColor, str)):
            self.__color=QColor(color)
        else:
            self.__color=None

        # parent node
        self.__node=None

        # parent scene
        self.__scene=None

        # QGraphicsItem to represent connector on QGraphicsScene
        self.__grItem=NodeEditorGrConnector(self)

        self.checkLinks()

    def __updatePosition(self):
        """Update position for graphic item

        Position of QGraphicsItem is defined from location+position values
        """
        if self.__location == NodeEditorConnector.LOCATION_LEFT_TOP:
            self.__grItem.setPos(0, self.__position)
        elif self.__location == NodeEditorConnector.LOCATION_LEFT_BOTTOM:
            self.__grItem.setPos(0, self.__node.graphicItem().size().height() - self.__position)

        elif self.__location == NodeEditorConnector.LOCATION_RIGHT_TOP:
            self.__grItem.setPos(self.__node.graphicItem().size().width(), self.__position)
        elif self.__location == NodeEditorConnector.LOCATION_RIGHT_BOTTOM:
            self.__grItem.setPos(self.__node.graphicItem().size().width(), self.__node.graphicItem().size().height() - self.__position)

        elif self.__location == NodeEditorConnector.LOCATION_TOP_LEFT:
            self.__grItem.setPos(self.__position, 0)
        elif self.__location == NodeEditorConnector.LOCATION_TOP_RIGHT:
            self.__grItem.setPos(self.__node.graphicItem().size().width() - self.__position, 0)

        elif self.__location == NodeEditorConnector.LOCATION_BOTTOM_LEFT:
            self.__grItem.setPos(self.__position, self.__node.graphicItem().size().height())
        elif self.__location == NodeEditorConnector.LOCATION_BOTTOM_RIGHT:
            self.__grItem.setPos(self.__node.graphicItem().size().width() - self.__position, self.__node.graphicItem().size().height())

    def __defaultNodeConnectorRadiusChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__radius is None:
            self.radiusChanged.emit(value)

    def __defaultNodeConnectorBorderSizeChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__borderSize is None:
            self.borderSizeChanged.emit(value)

    def __defaultNodeConnectorBorderColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__borderColor is None:
            self.borderColorChanged.emit(value)

    def __defaultNodeConnectorInputColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__color is None:
            self.colorChanged.emit(value)

    def __defaultNodeConnectorOutputColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__color is None:
            self.colorChanged.emit(value)

    def id(self):
        """Return connector Id"""
        return self.__id

    def graphicItem(self):
        """Return QGraphicsItem for connector"""
        return self.__grItem

    def isInput(self):
        """Return True is connector is an input connector"""
        return (self.__direction==NodeEditorConnector.DIRECTION_INPUT)

    def isOutput(self):
        """Return True is connector is an output connector"""
        return (self.__direction==NodeEditorConnector.DIRECTION_OUTPUT)

    def location(self):
        """Return current location"""
        return self.__location

    def scene(self):
        """Return scene for connector"""
        return self.__scene

    def node(self):
        """Return parent node for connector"""
        return self.__node

    def setNode(self, node):
        """Set parent node for connector

        Once parent node has been defined, it's not possible anymore to modify it
        """
        if not isinstance(node, NodeEditorNode):
            raise EInvalidType("Given `node` <NodeEditorNode>")
        elif not self.__node is None:
            raise EInvalidType("Node is is already defined for connector")
        self.__node=node
        self.__node.defaultConnectorRadiusChanged.connect(self.__defaultNodeConnectorRadiusChanged)
        self.__node.defaultConnectorBorderSizeChanged.connect(self.__defaultNodeConnectorBorderSizeChanged)
        self.__node.defaultConnectorBorderColorChanged.connect(self.__defaultNodeConnectorBorderColorChanged)

        if self.isInput():
            self.__node.defaultConnectorInputColorChanged.connect(self.__defaultNodeConnectorInputColorChanged)
        else:
            self.__node.defaultConnectorOutputColorChanged.connect(self.__defaultNodeConnectorOutputColorChanged)

        self.__grItem.setParentItem(self.__node.graphicItem())
        self.__scene=self.__node.scene()

        self.checkLinks()

        self.radiusChanged.emit(self.radius())
        self.colorChanged.emit(self.color())
        self.borderSizeChanged.emit(self.borderSize())
        self.borderColorChanged.emit(self.borderColor())

    def position(self):
        """Return current position for location"""
        return self.__position

    def setPosition(self, value=None):
        """Set current position for location"""
        if not (value is None or isinstance(value, (int, float))):
            raise EInvalidType("Given `position` must be <int> or <float>")
        elif not value is None:
            self.__position=value
        self.__updatePosition()

    def borderSize(self):
        """Return current connector border size (in pixels)"""
        if self.__borderSize is None:
            if self.__node:
                return self.__node.defaultConnectorBorderSize()
            else:
                return 0
        return self.__borderSize

    def setBorderSize(self, value):
        """Set current connector border size (in pixels)"""
        if (value is None or isinstance(value, (int, float))) and self.__borderSize!=value:
            self.__borderSize=value
            self.borderSizeChanged.emit(self.borderSize())

    def radius(self):
        """Return current connector radius (in pixels)"""
        if self.__radius is None:
            if self.__node:
                return self.__node.defaultConnectorRadius()
            else:
                return 0
        return self.__radius

    def setRadius(self, value):
        """Set current connector radius (in pixels)"""
        if (value is None or isinstance(value, (int, float))) and self.__radius!=value:
            self.__radius=value
            self.radiusChanged.emit(self.radius())

    def color(self):
        """Return default color value for output connectors"""
        if self.__color is None:
            if self.__node:
                if self.isInput():
                    return self.__node.defaultConnectorInputColor()
                else:
                    return self.__node.defaultConnectorOutputColor()
            else:
                return QColor(Qt.transparent)
        return self.__color

    def setColor(self, value):
        """Set default color value for output connectors"""
        if isinstance(value, (QColor, str)):
            try:
                self.__color=QColor(value)
                self.colorChanged.emit(self.color())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__color=None
            self.colorChanged.emit(self.color())

    def borderColor(self):
        """Return default border color value for output connectors"""
        if self.__borderColor is None:
            if self.__node:
                return self.__node.defaultConnectorBorderColor()
            else:
                return QColor(Qt.transparent)
        return self.__borderColor

    def setBorderColor(self, value):
        """Set default border color value for output connectors"""
        if isinstance(value, (QColor, str)):
            try:
                self.__borderColor=QColor(value)
                self.borderColorChanged.emit(self.borderColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__borderColor=None
            self.borderColorChanged.emit(self.borderColor())

    def links(self):
        """Return a list of NodeEditorLink connected to connector"""
        self.checkLinks()
        return self.__links

    def acceptedConnectionFrom(self):
        """Return list of accepted connection types"""
        return self.__acceptedConnectionFrom

    def addAcceptedConnectionFrom(self, connectorType):
        """Add a new accepted connector type

        Only output connectors can accept connection
        Calling function on an output connector is ignored
        """
        if not connectorType in self.__acceptedConnectionFrom and issubclass(connectorType, NodeEditorConnector) and self.isInput():
            self.__acceptedConnectionFrom.append(connectorType)

    def removeAcceptedConnectionFrom(self, connectorType):
        """Add a new accepted connector type"""
        if connectorType in self.__acceptedConnectionFrom:
            self.__acceptedConnectionFrom.remove(connectorType)

    def checkLinks(self):
        """Check if links are connected to connector

        This is called by link when connector is connected/disconnected
        The connector then check currents links and keep internal information up
        to date

        (no direct method like addLink()/removeLink() to connector, better to check
        scene to ensure consistency)
        """
        if self.__scene is None:
            return

        self.__links=self.__scene.links(self)
        if self.isOutput() or len(self.__links)>0:
            if not self.__grItem.hasCursor():
                self.__grItem.setCursor(Qt.PointingHandCursor)
        else:
            self.__grItem.unsetCursor()

    def acceptInputLink(self, source=None):
        """Return True if connector can accept a link as input, otherwise False

        An output connector always return False
        An input connector return False if there's already a connected link

        Otherwise, for input connector, it will depend:
        - If there's no restriction for input, return True
        - If there's restriction for input, return True is input link match accepted value, otherwise return False
          (note: if there's restriction for input value, if link is None, return False)
        """
        self.checkLinks()
        if (self.__direction==NodeEditorConnector.DIRECTION_OUTPUT) or len(self.__links)>0:
            return False
        elif len(self.__acceptedConnectionFrom)>0:
            if (isinstance(source, NodeEditorLink) and not type(source.connectorFrom()) in self.__acceptedConnectionFrom or
                isinstance(source, NodeEditorConnector) and not type(source) in self.__acceptedConnectionFrom):
                return False

        return True


class NodeEditorLink(QObject):
    """Define a link (connection between 2 connector - from an output => input)"""
    renderModeChanged=Signal(int)                                               # render mode for link has been modifier: RENDER_DIRECT, RENDER_CURVE, RENDER_ANGLE
    colorChanged=Signal(QColor)                                                 # render color for link has been modified
    colorSelectedChanged=Signal(QColor)                                         # render color for selected link has been modified
    sizeChanged=Signal(float)                                                   # render size for link has been modified: line width in pixels (at 100%)
    selectionChanged=Signal(bool)                                               # node selection state has been changed: boolean True=Selected/False=Unselected

    RENDER_DIRECT =  0x01
    RENDER_CURVE =   0x02
    RENDER_ANGLE =   0x03

    def __init__(self, fromConnector, toConnector, renderMode=None, color=None, colorSelected=None, size=None, parent=None):
        super(NodeEditorLink, self).__init__(parent)

        if not isinstance(fromConnector, NodeEditorConnector):
            raise EInvalidType("Given `fromConnector` must be <NodeEditorConnector>")
        elif not (toConnector is None or isinstance(toConnector, NodeEditorConnector)):
            raise EInvalidType("Given `toConnector` must be <NodeEditorConnector>")
        elif not renderMode in (None, NodeEditorLink.RENDER_ANGLE, NodeEditorLink.RENDER_CURVE, NodeEditorLink.RENDER_DIRECT):
            raise EInvalidValue("Given `renderMode` value is not valid")
        elif fromConnector.isInput():
            raise EInvalidType("Given `fromConnector` must be an output connector")
        elif not toConnector is None and toConnector.isOutput():
            raise EInvalidType("Given `toConnector` must be an input connector")

        # QGraphicsItem definition
        self.__grItem=None

        # selection state
        self.__isSelected=False

        # define connector from which link start (mandatory)
        self.__fromConnector=fromConnector

        # define connector from which link end (optional)
        # - if None, means that link end to current mouse position on scene
        #   (used during creation/update of a link)
        # - if defined, means that link is finalized
        self.__toConnector=None

        # the temporary connector is used for temporary connection
        # (used during creation/update of a link - when mouse is over a valid connector,
        # connection is temporary made to it)
        self.__toConnectorTmp=None

        # define render mode (direct link, curves, angle, ...)
        self.__renderMode=renderMode

        # define render color
        self.__color=color

        # define render color for selected link
        self.__colorSelected=colorSelected

        # define render size
        self.__size=size

        # do connection to 'End' connector
        if not self.setConnectorTo(toConnector):
            # in this case, fromConnector has already been forced to None
            # exit
            return

        # parent scene
        self.__scene=self.__fromConnector.node().scene()
        self.__scene.defaultLinkRenderModeChanged.connect(self.__defaultSceneLinkRenderModeChanged)
        self.__scene.defaultLinkSizeChanged.connect(self.__defaultSceneLinkSizeChanged)
        self.__scene.defaultLinkColorChanged.connect(self.__defaultSceneLinkColorChanged)
        self.__scene.defaultLinkSelectedColorChanged.connect(self.__defaultSceneLinkColorSelectedChanged)

        # QGraphicsItem for link
        self.__grItem=NodeEditorGrLink(self)

        # add link to scene
        self.__scene.addLink(self)

        self.sizeChanged.emit(self.size())
        self.renderModeChanged.emit(self.renderMode())
        self.colorChanged.emit(self.color())
        self.colorSelectedChanged.emit(self.selectedColor())

        self.__updateConnectors()

    # Deleting (Calling destructor)
    def __del__(self):
        if self.__grItem and self.__grItem.scene():
            self.__grItem.scene().removeItem(self)
            del self.__grItem

    def __defaultSceneLinkRenderModeChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__renderMode is None:
            self.renderModeChanged.emit(value)

    def __defaultSceneLinkSizeChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__size is None:
            self.sizeChanged.emit(value)

    def __defaultSceneLinkColorChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__color is None:
            self.colorChanged.emit(value)

    def __defaultSceneLinkColorSelectedChanged(self, value):
        """Default value from scene has been changed; check for update"""
        if self.__colorSelected is None:
            self.colorSelectedChanged.emit(value)

    def __updateConnectors(self, fromConnector=None, toConnector=None):
        """Update connector, asking to check link connections"""
        if fromConnector:
            fromConnector.checkLinks()
        elif self.__fromConnector:
            self.__fromConnector.checkLinks()

        if toConnector:
            toConnector.checkLinks()
        elif self.__toConnector:
            self.__toConnector.checkLinks()

    def itemChange(self, change, value):
        """Something has been changed on graphic item

        Emit signal if needed
        """
        if change==QGraphicsItem.ItemSelectedChange:
            if value:
                # move node to front
                self.__grItem.setZValue(NodeEditorScene.LINK_ZINDEX_FRONT)
            else:
                # restore node to initial zIndex
                self.__grItem.setZValue(NodeEditorScene.LINK_ZINDEX)
            self.__isSelected=bool(value)
            self.selectionChanged.emit(self.__isSelected)

    def isValid(self):
        """Return True if link is valid, otherwise False

        An invalid link is a link that has been created but for which connection
        between 'from' and 'to' connector is not allowed

        For an invalid link, both Connector (from, to) are set to None
        """
        return not self.__fromConnector is None

    def graphicItem(self):
        """Return graphic item for node"""
        return self.__grItem

    def scene(self):
        """Return scene for link"""
        return self.__scene

    def connectorFrom(self):
        """Return connector from which link start"""
        return self.__fromConnector

    def connectorTo(self):
        """Return connector from which link start"""
        if self.__toConnectorTmp:
            return self.__toConnectorTmp
        return self.__toConnector

    def nodeFrom(self):
        """Return node from which link start"""
        return self.__fromConnector.node()

    def nodeTo(self):
        """Return node from which link start"""
        return self.__toConnector.node()

    def setConnectorTo(self, toConnector, linking=False):
        """Set node 'to' for link

        Can be None or a <NodeEditorConnector>

        Return True if connector is set, otherwise False
        """
        if not (toConnector is None or isinstance(toConnector, NodeEditorConnector)):
            raise EInvalidType("Given `toConnector` must be <NodeEditorConnector>")

        if linking:
            if not toConnector is None and not toConnector.acceptInputLink(self.__fromConnector):
                return False

            self.__toConnectorTmp=toConnector
            self.setRenderMode(self.__scene.defaultLinkRenderMode())
        else:
            if toConnector is None:
                checkConnector=self.__toConnector
            else:
                checkConnector=None

            if not toConnector is None:
                if not toConnector.acceptInputLink(self.__fromConnector):
                    # can't create the link
                    self.__fromConnector=None
                    return False

            self.__toConnectorTmp=None
            self.__toConnector=toConnector

            self.__updateConnectors(toConnector=checkConnector)

            #if self.__grItem:
            #    self.__grItem.update()

        return True

    def renderMode(self):
        """Return current render mode"""
        if self.__renderMode is None:
            return self.__scene.defaultLinkRenderMode()
        return self.__renderMode

    def setRenderMode(self, renderMode):
        """Return current render mode"""
        if not renderMode in (None, NodeEditorLink.RENDER_ANGLE, NodeEditorLink.RENDER_CURVE, NodeEditorLink.RENDER_DIRECT):
            raise EInvalidValue("Given `renderMode` value is not valid")

        if renderMode!=self.__renderMode:
            self.__renderMode=renderMode
            self.renderModeChanged.emit(self.renderMode())

    def size(self):
        """Return size value for link

        If no size value is defined, return default scene value
        """
        if self.__size is None:
            return self.__scene.defaultLinkSize()
        return self.__size

    def setSize(self, value):
        """Set size value for link"""
        if (value is None or isinstance(value, (int, float))) and self.__size!=value:
            self.__size=float(value)
            self.sizeChanged.emit(self.size())

    def color(self):
        """Return current render color"""
        if self.__color is None:
            return self.__scene.defaultLinkColor()
        return self.__color

    def setColor(self, value):
        """Return current render color"""
        if isinstance(value, (QColor, str)):
            try:
                self.__color=QColor(value)
                self.colorChanged.emit(self.color())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__color=None
            self.colorChanged.emit(self.color())

    def selectedColor(self):
        """Return current render color for selected link"""
        if self.__colorSelected is None:
            return self.__scene.defaultLinkColorSelected()
        return self.__colorSelected

    def setSelectedColor(self, value):
        """Return current render color for selected link"""
        if isinstance(value, (QColor, str)):
            try:
                self.__colorSelected=QColor(value)
                self.colorSelectedChanged.emit(self.selectedColor())
            except:
                # ignore invalid color...
                pass
        elif value is None:
            self.__colorSelected=None
            self.colorSelectedChanged.emit(self.selectedColor())

    def isSelected(self):
        """Return if current node is selected"""
        return self.__isSelected

    def setSelected(self, selectionStatus=True):
        """Select/Deselect item"""
        if selectionStatus!=self.__isSelected and isinstance(selectionStatus, bool):
            self.__grItem.setSelected(selectionStatus)


# ------------------------------------------------------------------------------


class NodeEditorGrScene(QGraphicsScene):
    """Render canvas scene: grid, origin, bounds, background, rendered graphics....

    Instancied automatically when a NodeEditorScene() is created
    """
    propertyChanged=Signal(tuple)       # tuple is defined by (<variable name>, <value)

    sceneUpdated=Signal(dict)           # scene has been updated

    __SECONDARY_FACTOR_OPACITY = 0.5    # define opacity of secondary grid relative to main grid
    __FULFILL_FACTOR_OPACITY = 0.75     # define opacity of position fulfill

    def __init__(self, scene, parent=None):
        super(NodeEditorGrScene, self).__init__(parent)

        if not isinstance(scene, NodeEditorScene):
            raise EInvalidType("Given `scene` must be a <NodeEditorScene>")

        self.__scene=scene
        self.__scene.sizeChanged.connect(lambda nSize, oSize: self.__setSize(nSize))

        # settings
        self.__gridSizeWidth = 20
        self.__gridSizeMain = 5
        self.__gridBrush=QBrush(QColor("#393939"))
        self.__gridPenMain=QPen(QColor("#FF292929"))
        self.__gridPenSecondary=QPen(QColor("#80292929"))
        self.__gridVisible=True

        # scene bounds in PX
        self.__sceneBounds=None

        # internal data for rendering
        self.__gridStrokesRect=QRect()
        self.__gridStrokesMain=[]
        self.__gridStrokesSecondary=[]
        self.__viewZoom=1.0

        self.__mouseScenePos=QPointF(0, 0)
        self.__mouseHoverConnector=None

        self.initialise()
        self.setBackgroundBrush(self.__gridBrush)
        self.setItemIndexMethod(QGraphicsScene.NoIndex)

    def __propertyChanged(self, name, value):
        """Emit signal for variable name"""
        self.propertyChanged.emit((name, value))

    def __generateGridStrokes(self, rect):
        """Generate grid strokes (avoid to regenerate them on each update)"""
        if rect==self.__gridStrokesRect:
            # viewport is the same, keep current grid definition
            return

        self.__gridStrokesSecondary=[]
        self.__gridStrokesMain=[]
        self.__gridStrokesRulerH=[]
        self.__gridStrokesRulerV=[]

        # bounds
        left = int(math.floor(rect.left()))
        right = int(math.ceil(rect.right()))
        top = int(math.floor(rect.top()))
        bottom = int(math.ceil(rect.bottom()))

        firstLeftStroke = left - (left % self.__gridSizeWidth)
        firstTopStroke = top - (top % self.__gridSizeWidth)

        # frequency of main strokes
        mainStroke=max(1, self.__gridSizeWidth * self.__gridSizeMain)

        # generate vertical grid lines
        for positionX in range(firstLeftStroke, right, self.__gridSizeWidth):
            if (positionX % mainStroke != 0):
                self.__gridStrokesSecondary.append(QLine(positionX, top, positionX, bottom))
                self.__gridStrokesRulerH.append((False, positionX))
            else:
                self.__gridStrokesMain.append(QLine(positionX, top, positionX, bottom))
                self.__gridStrokesRulerH.append((True, positionX))

        # generate horizontal grid lines
        for positionY in range(firstTopStroke, bottom, self.__gridSizeWidth):
            if (positionY % mainStroke != 0):
                self.__gridStrokesSecondary.append(QLine(left, positionY, right, positionY))
                self.__gridStrokesRulerV.append((False, positionY))
            else:
                self.__gridStrokesMain.append(QLine(left, positionY, right, positionY))
                self.__gridStrokesRulerV.append((True, positionY))

    def __calculateSceneSize(self):
        """Calculate scene size/rect"""
        if self.__sceneBounds is None:
            self.__sceneBounds=QRectF(-10000.0, -10000.0, 20000.0, 20000.0)

        self.setSceneRect(self.__sceneBounds)

    def __setSize(self, size):
        """Define size of scene with given `size`

        Note: they must be greater than painted area
        """
        self.__sceneBounds=QRectF(-size.width()/2, -size.height()/2, size.width(), size.height())
        self.__calculateSceneSize()
        self.update()

    def initialise(self):
        """Initialize render scene"""
        self.__gridPenMain.setWidth(0)
        self.__gridPenSecondary.setWidth(0)

    def drawBackground(self, painter, rect):
        """Draw background grid fro scene..."""
        super(NodeEditorGrScene, self).drawBackground(painter, rect)

        # generate grid lines
        self.__generateGridStrokes(rect)

        # draw the lines
        # -> if grid is not visible, there's no strokes generated
        if self.__gridVisible and len(self.__gridStrokesSecondary)>0:
            painter.setPen(self.__gridPenSecondary)
            painter.drawLines(*self.__gridStrokesSecondary)

        if self.__gridVisible and len(self.__gridStrokesMain)>0:
            painter.setPen(self.__gridPenMain)
            painter.drawLines(*self.__gridStrokesMain)

        self.__gridStrokesRect=rect

    def mouseMoveEvent(self, event):
        """Mouse move over scene"""
        # first, keep in memory current mouse position over scene
        self.__mouseScenePos=event.scenePos()

        # get current linkingItem
        link=self.__scene.linkingItem()
        if link:
            # a linkingItem exist, need to update it according to current mouse
            # position
            link.graphicItem().update()

            # check if mouse is over an item
            if isinstance(event.widget(), QGraphicsView):
                # in this case, event.widget() is the current view then use
                # current view QTransform value
                hoverItem=self.itemAt(self.__mouseScenePos, event.widget().transform())
            else:
                # in this case, event.widget() is???
                # use a default QTransform value (I suppose this can't occurs, but...)
                hoverItem=self.itemAt(self.__mouseScenePos, QTransform())

            # check in scene if mouse is over a connector
            if isinstance(hoverItem, NodeEditorGrConnector):
                # found a connector
                if self.__mouseHoverConnector!=hoverItem:
                    # connector is not the same than previous one, do updates
                    if self.__mouseHoverConnector:
                        # previous position was over a connector, force leave event
                        self.__mouseHoverConnector.hoverLeaveEvent(event)
                    # now keep in memory current connector for which mouse is over
                    self.__mouseHoverConnector=hoverItem
                    # and trigger hover event for connector
                    self.__mouseHoverConnector.hoverEnterEvent(event)
            elif self.__mouseHoverConnector:
                # we are not anymore over a connector, triger leave event
                self.__mouseHoverConnector.hoverLeaveEvent(event)
                # and memorize that we are not over a connector
                self.__mouseHoverConnector=None
        else:
            # default behavior
            super(NodeEditorGrScene, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Mouse release:
        - hover a valid connector: finalize link
        - hover an valid connector: delete link
        """
        # get current linkingItem
        linkingItem=self.__scene.linkingItem()
        if linkingItem and linkingItem.graphicItem().isEnabled():
            # there's a linkingItem ready to be processed (if not enabled, then
            # the linkingItem is still in initialisation phase and then we don't
            # have to do anything yet)
            if linkingItem.connectorTo():
                # have a temporary connector (is over a connector)
                fromConnector=linkingItem.connectorFrom()
                toConnector=linkingItem.connectorTo()
                # unset linkingItem
                self.__scene.setLinkingItem(None)
                # create definitive link
                NodeEditorLink(fromConnector, toConnector)
            else:
                # don't have a temporary connector (is not over a connector): delete temporary link
                self.__scene.setLinkingItem(None)

        if self.__mouseHoverConnector:
            # mouse was over a connector
            # trigger release event
            self.__mouseHoverConnector.mouseReleaseEvent(event)
            # and memorize that we are not over a connector (as we are not anymore creating/updating a link)
            self.__mouseHoverConnector=None

        super(NodeEditorGrScene, self).mouseReleaseEvent(event)

    # --------------------------------------------------------------------------
    # getters
    # --------------------------------------------------------------------------
    def scene(self):
        """Return scene"""
        return self.__scene

    def gridVisible(self):
        """Return if grid is visible"""
        return self.__gridVisible

    def gridSize(self):
        """Return a tuple (grid size width, main grid frequency) in PX"""
        return (self.__gridSizeWidth, self.__gridSizeMain)

    def gridBrush(self):
        """Return brush used to render background grid"""
        return self.__gridBrush

    def gridPenMain(self):
        """Return pen used to render main grid"""
        return self.__gridPenMain

    def gridPenSecondary(self):
        """Return pen used to render secondary grid"""
        return self.__gridPenSecondary

    def sceneBounds(self):
        """Return current scene bounds"""
        return self.__sceneBounds

    def cursorScenePosition(self):
        """Return current mouse position over scene"""
        return self.__mouseScenePos

    # --------------------------------------------------------------------------
    # setters
    # --------------------------------------------------------------------------
    def setViewZoom(self, value):
        self.__viewZoom=value

    def setGridVisible(self, value):
        """Set if grid is visible"""
        if isinstance(value, bool) and value!=self.__gridVisible:
            self.__gridVisible=value
            self.__propertyChanged('canvas.grid.visibility', self.__gridVisible)
            self.update()

    def setGridSize(self, width, main=0):
        """Set grid size, given `width` is in PX
        Given `main` is an integer that define to draw a main line everything `main` line
        """
        if width!=self.__gridSizeWidth or main!=self.__gridSizeMain:
            # force grid to be recalculated
            self.__gridStrokesRect=QRect()
            self.__gridSizeWidth=max(2, round(width))
            self.__gridSizeMain=max(0, main)
            self.__propertyChanged('canvas.grid.size.main', self.__gridSizeMain)
            self.__propertyChanged('canvas.grid.size.width', self.__gridSizeWidth)
            self.update()

    def setGridBrushColor(self, value):
        """Set color for grid background"""
        color=QColor(value)
        color.setAlpha(255)
        self.__gridBrush.setColor(color)
        self.setBackgroundBrush(self.__gridBrush)
        self.__propertyChanged('canvas.grid.bgColor', color)
        self.update()

    def setGridPenColor(self, value):
        """Set color for grid"""
        # get current opacity
        alphaF=self.__gridPenMain.color().alphaF()

        # apply current color and keep opacity
        color=QColor(value)
        self.__propertyChanged('canvas.grid.color', color)

        color.setAlphaF(alphaF)
        self.__gridPenMain.setColor(color)

        # apply current color and keep opacity
        color=QColor(value)
        color.setAlphaF(alphaF*NodeEditorGrScene.__SECONDARY_FACTOR_OPACITY)
        self.__gridPenSecondary.setColor(color)
        self.update()

    def setGridPenStyleMain(self, value):
        """Set stroke style for main grid"""
        self.__gridPenMain.setStyle(value)

        self.__propertyChanged('canvas.grid.style.main', value)
        self.update()

    def setGridPenStyleSecondary(self, value):
        """Set stroke style for secondary grid"""
        self.__gridPenSecondary.setStyle(value)
        self.__propertyChanged('canvas.origin.style.secondary', value)
        self.update()

    def setGridPenOpacity(self, value):
        """Set opacity for grid"""
        color=self.__gridPenMain.color()
        color.setAlphaF(value)
        self.__gridPenMain.setColor(QColor(color))

        color.setAlphaF(value*NodeEditorGrScene.__SECONDARY_FACTOR_OPACITY)
        self.__gridPenSecondary.setColor(QColor(color))

        self.__propertyChanged('canvas.grid.opacity', value)
        self.update()

    def setSceneBounds(self, bounds):
        """Set scene bounds

        Given `bounds` is a QRect()
        (because top-left can be negative...)
        """
        if isinstance(bounds, QRect):
            self.__sceneBounds=QRectF(bounds)
        elif isinstance(bounds, QRectF):
            self.__sceneBounds=bounds
        else:
            raise EInvalidType("Given `bounds` must be a <QRect>")
        self.__calculateSceneSize()
        self.update()


class NodeEditorGrNode(QGraphicsItem):
    """A default rendered node"""

    def __init__(self, node, parent=None):
        super(NodeEditorGrNode, self).__init__(parent)

        if not isinstance(node, NodeEditorNode):
            raise EInvalidType("Given `node` must be <NodeEditorNode>")

        palette=QApplication.palette()

        # node for graphic node
        self.__node=node
        self.__node.titleChanged.connect(self.__updateTitle)
        self.__node.titleColorChanged.connect(self.__updateTitleColor)
        self.__node.titleBgColorChanged.connect(self.__updateTitleBgColor)
        self.__node.titleSelectedColorChanged.connect(self.__updateTitleSelectorColor)
        self.__node.titleSelectedBgColorChanged.connect(self.__updateTitleSelectorBgColor)
        self.__node.nodeBgColorChanged.connect(self.__updateNodeBgColor)
        self.__node.nodeSelectedBgColorChanged.connect(self.__updateNodeSelectedBgColor)
        self.__node.borderRadiusChanged.connect(self.__updateBorderRadius)
        self.__node.borderSizeChanged.connect(self.__updateBorderSize)
        self.__node.paddingChanged.connect(self.__updatePadding)

        # curent node size
        self.__size=None
        self.__minSize=QSize()

        # define title rendering properties
        self.__titleTextColor=palette.color(QPalette.BrightText)
        self.__titleBgColor=palette.color(QPalette.Dark)
        self.__titleTextColorSelected=palette.color(QPalette.HighlightedText)
        self.__titleBgColorSelected=palette.color(QPalette.Highlight)

        self.__titleBrush=QBrush(self.__titleBgColor)
        self.__titleBrushSelected=QBrush(self.__titleBgColorSelected)

        # define borders rendering properties
        self.__borderColorSelected=palette.color(QPalette.Highlight)
        self.__borderSize=2.0
        self.__borderRadius=6.0

        # define padding (distance between border & widget)
        self.__padding=6.0
        self.__borderPen=QPen(self.__titleBgColor)
        self.__borderPen.setWidth(self.__borderSize)
        self.__borderPen.setJoinStyle(Qt.MiterJoin)
        self.__borderPenSelected=QPen(self.__titleBgColorSelected)
        self.__borderPenSelected.setWidth(self.__borderSize)
        self.__borderPenSelected.setJoinStyle(Qt.MiterJoin)

        # define window rendering properties
        self.__windowBgColor=palette.color(QPalette.Window)
        self.__windowBgColorSelected=palette.color(QPalette.Window)

        self.__windowBrush=QBrush(self.__windowBgColor)
        self.__windowBrushSelected=QBrush(self.__windowBgColorSelected)

        # define title
        self.__itemTitle=QGraphicsTextItem(self)
        self.__itemTitle.setDefaultTextColor(self.__titleTextColor)

        #node's bounding rect is calculated and stored when size/border size is modified
        self.__boundingRect=QRectF()

        # node properties
        self.setZValue(NodeEditorScene.NODE_ZINDEX)
        self.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        self.__updateTitle()

    def __updateTitle(self, node=None):
        """Update title from node"""
        self.__itemTitle.setPlainText(self.__node.title())
        self.__updateSize()

    def __updateTitleColor(self, value):
        """Title color has been modified"""
        if self.__titleTextColor!=value:
            self.__titleTextColor=value
            if not self.isSelected():
                self.__itemTitle.setDefaultTextColor(self.__titleTextColor)
                self.update()

    def __updateTitleBgColor(self, value):
        """Title background color has been modified"""
        if self.__titleBgColor!=value:
            self.__titleBgColor=value
            self.__titleBrush.setColor(self.__titleBgColor)
            self.__borderPen.setColor(self.__titleBgColor)
            if not self.isSelected():
                self.update()

    def __updateTitleSelectorColor(self, value):
        """Title color (selected node) has been modified"""
        if self.__titleTextColorSelected!=value:
            self.__titleTextColorSelected=value
            if self.isSelected():
                self.__itemTitle.setDefaultTextColor(self.__titleTextColorSelected)
                self.update()

    def __updateTitleSelectorBgColor(self, value):
        """Title background color (selected node) has been modified"""
        if self.__titleBgColorSelected!=value:
            self.__titleBgColorSelected=value
            self.__titleBrushSelected.setColor(self.__titleBgColorSelected)
            self.__borderPenSelected.setColor(self.__titleBgColorSelected)
            if self.isSelected():
                self.update()

    def __updateNodeBgColor(self, value):
        """Node background color has been modified"""
        if self.__windowBgColor!=value:
            self.__windowBgColor=value
            self.__windowBrush.setColor(self.__windowBgColor)
            if not self.isSelected():
                self.update()

    def __updateNodeSelectedBgColor(self, value):
        """Node background color (selected node) has been modified"""
        if self.__windowBgColorSelected!=value:
            self.__windowBgColorSelected=value
            self.__windowBrushSelected.setColor(self.__windowBgColorSelected)
            if self.isSelected():
                self.update()

    def __updateBorderRadius(self, value):
        """Border radius has been modified"""
        if self.__borderRadius!=value:
            self.__borderRadius=value
            self.update()

    def __updateBorderSize(self, value):
        """Border size has been modified"""
        if self.__borderSize!=value:
            self.__borderSize=value
            self.__borderPen.setWidth(self.__borderSize)
            self.__borderPenSelected.setWidth(self.__borderSize)

            if self.__borderSize==0:
                self.__borderPen.setStyle(Qt.NoPen)
                self.__borderPenSelected.setStyle(Qt.NoPen)
            else:
                self.__borderPen.setStyle(Qt.SolidLine)
                self.__borderPenSelected.setStyle(Qt.SolidLine)
            self.__updateSize()
    def __updatePadding(self, value):
        """Border size has been modified"""
        if self.__padding!=value:
            self.__padding=value
            self.update()

    def __updateSize(self):
        """Calculate bounds size for current node

        Take in account current title width + minimum size (200x200 pixels) for a node
        """
        self.__size=self.__itemTitle.boundingRect().size().toSize()
        self.__size=self.__size.expandedTo(self.__minSize)
        self.__updateBoundingRect()
        self.prepareGeometryChange()

    def __updateBoundingRect(self):
        """Calculate bounding rect according to connector properties"""
        hBs=-self.__borderSize/2
        self.__boundingRect=QRectF(QPointF(hBs,hBs), QSizeF(self.__size)+QSizeF(self.__borderSize,self.__borderSize))

    def itemChange(self, change, value):
        """A QGraphicsItem property has been changed"""
        if value==QGraphicsItem.ItemSelectedHasChanged:
            # item selection state has been modified, take it in account
            if value:
                self.__itemTitle.setDefaultTextColor(self.__titleTextColorSelected)
            else:
                self.__itemTitle.setDefaultTextColor(self.__titleTextColor)
        self.__node.itemChange(change, value)
        return super(NodeEditorGrNode, self).itemChange(change, value)

    def minimumSize(self):
        """Return minimum size for node"""
        return self.__minSize

    def setMinimumSize(self, value):
        """set minimum size for node"""
        if isinstance(value, QSize) and value!=self.__minSize:
            self.__minSize=value
            self.__updateSize()
            self.update()

    def size(self):
        """Return node size"""
        return self.__size

    def title(self):
        """Return instance of title

        (let user change font properties...)
        """
        return self.__itemTitle

    def titleSize(self):
        """Return node title size"""
        return self.__itemTitle.boundingRect().size().toSize()

    def boundingRect(self):
        """Return boundingRect for node"""
        return self.__boundingRect

    def paint(self, painter, options, widget=None):
        """Render node"""
        painter.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform, True)

        # window background
        pathWindowBorder=QPainterPath()
        pathWindowBorder.addRoundedRect(0, 0, self.__size.width(), self.__size.height(), self.__borderRadius, self.__borderRadius)

        # window title rect
        pathTitleRect=QPainterPath()
        pathTitleRect.addRect(0, 0, self.__size.width(), self.__itemTitle.boundingRect().size().height())

        # window title
        pathTitleBg=pathTitleRect.intersected(pathWindowBorder)

        # window background
        pathWindowBg=QPainterPath(pathWindowBorder)
        pathWindowBg=pathWindowBg.subtracted(pathTitleRect)

        # window borders
        pathWindowBorder=QPainterPath()
        pathWindowBorder.addRoundedRect(0, 0, self.__size.width(), self.__size.height(), self.__borderRadius, self.__borderRadius)


        # render
        painter.setPen(Qt.NoPen)
        if self.isSelected():
            painter.setBrush(self.__windowBrushSelected)
        else:
            painter.setBrush(self.__windowBrush)
        painter.drawPath(pathWindowBg)

        if self.isSelected():
            painter.setBrush(self.__titleBrushSelected)
        else:
            painter.setBrush(self.__titleBrush)
        painter.drawPath(pathTitleBg)

        if self.isSelected():
            painter.setPen(self.__borderPenSelected)
        else:
            painter.setPen(self.__borderPen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(pathWindowBorder)


class NodeEditorGrConnector(QGraphicsItem):
    """A default rendered connector"""

    def __init__(self, connector, parent=None):
        super(NodeEditorGrConnector, self).__init__(parent)

        if not isinstance(connector, NodeEditorConnector):
            raise EInvalidType("Given `link` must be <NodeEditorConnector>")

        palette=QApplication.palette()

        # connector for graphic item
        self.__connector=connector
        self.__connector.radiusChanged.connect(self.__updateRadius)
        self.__connector.colorChanged.connect(self.__updateColor)
        self.__connector.borderColorChanged.connect(self.__updateBorderColor)
        self.__connector.borderSizeChanged.connect(self.__updateBorderSize)

        # radius for connector
        self.__radius=self.__connector.radius()

        # color for connector
        self.__color=self.__connector.color()
        # color for connector
        self.__borderColor=self.__connector.borderColor()

        # border properties for connector=border width for links
        self.__borderSize=2.0

        # connector's bounding rect is calculated and stored when radius/border size is modified
        self.__boundingRect=QRectF()

        self.__borderPen=QPen(self.__borderColor)
        self.__borderPen.setWidth(self.__borderSize)

        # bg properties for connector
        self.__brush=QBrush(self.__color)

        self.__updateBoundingRect()
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

    def __updateBoundingRect(self):
        """Calculate bounding rect according to connector properties"""
        radius=-(self.__radius+self.__borderSize/2)
        diameter=2*self.__radius+self.__borderSize
        self.__boundingRect=QRectF(radius, radius, diameter, diameter)

    def mousePressEvent(self, event):
        """Mouse press on connector:

        - from output connector, start to drag a new link
        - from input connector, detach current link
        """
        if self.__connector.isOutput():
            # create a new link
            if self.__connector.scene().linkingItem() is None:
                # new link instance
                newLink=NodeEditorLink(self.__connector, None)
                # define current link as 'linkingItem' (a link in creation/update state)
                self.__connector.scene().setLinkingItem(newLink)
                newLink.graphicItem().setSelected(True)
        elif links:=self.__connector.scene().links(self.__connector):
            # input connector for which a link (links[0]) is connected to
            if self.__connector.scene().linkingItem() is None:
                # get start connector from current link
                fromConnector=links[0].connectorFrom()

                self.__connector.scene().removeLink(links[0])

                # new link instance
                newLink=NodeEditorLink(fromConnector, None)
                # define current link as 'linkingItem' (a link in creation/update state)
                self.__connector.scene().setLinkingItem(newLink)
                # everything is initialised, enable link
                newLink.graphicItem().setSelected(True)
        else:
            super(NodeEditorGrConnector, self).mousePressEvent(event)

    def hoverEnterEvent(self, event):
        """Mouse entered over connector

        Note: setAcceptsHoverEvents() is not enabled on connector
              tracking hover a connector is made from scene because hoverEnterEvent()
              seems not to work when mouse is pressed

              So here, the passed event is not a QGraphicsSceneHoverEvent but
              a QGraphicsSceneMouseEvent
        """
        # get current linkingItem
        linkingItem=self.__connector.scene().linkingItem()
        if linkingItem:
            # if currently in creation/update of a linkingItem, need to check if
            # connector accept the connection for link
            if self.__connector.acceptInputLink(linkingItem):
                # connection is possible, define current item as temporary 'end'
                # connector for the linkingItem
                linkingItem.setConnectorTo(self.__connector, True)
                self.setCursor(Qt.PointingHandCursor)

    def hoverLeaveEvent(self, event):
        """Mouse is not anymore over connector

        Note: setAcceptsHoverEvents() is not enabled on connector
              tracking hover a connector is made from scene because hoverLeaveEvent()
              seems not to work when mouse is pressed

              So here, the passed event is not a QGraphicsSceneHoverEvent but
              a QGraphicsSceneMouseEvent
        """
        # get current linkingItem
        linkingItem=self.__connector.scene().linkingItem()
        if linkingItem:
            # if currently in creation/update of a linkingItem, need to disconnect
            # temporary 'end' connector from linkingItem
            linkingItem.setConnectorTo(None, True)
            self.__connector.checkLinks()

    def boundingRect(self):
        """Return bouding rect for connector"""
        return self.__boundingRect

    def paint(self, painter, options, widget=None):
        """Render connector"""
        painter.setRenderHints(QPainter.Antialiasing, True)
        painter.setPen(self.__borderPen)
        painter.setBrush(self.__brush)
        painter.drawEllipse(QPoint(0, 0), self.__radius, self.__radius)

    def __updateBorderSize(self, value):
        """Update border size value"""
        self.__borderSize=value
        self.__borderPen.setWidth(self.__borderSize)
        if self.__borderSize==0:
            self.__borderPen.setStyle(Qt.NoPen)
        else:
            self.__borderPen.setStyle(Qt.SolidLine)

        self.__updateBoundingRect()
        self.update()

    def __updateRadius(self, value):
        """Update radius value"""
        self.__radius=value
        self.__updateBoundingRect()
        self.update()

    def __updateColor(self, value):
        """Update color value"""
        self.__color=value
        self.__brush.setColor(value)
        self.update()

    def __updateBorderColor(self, value):
        """Update color value"""
        self.__borderColor=value
        self.__borderPen.setColor(value)
        self.update()


class NodeEditorGrLink(QGraphicsPathItem):
    """A default rendered link"""

    # default factors for curves/angle links render
    __RENDER_CURVE_FACTOR = 0.75
    __RENDER_ANGLE_SIZE = 20

    def __init__(self, link, parent=None):
        super(NodeEditorGrLink, self).__init__(parent)

        if not isinstance(link, NodeEditorLink):
            raise EInvalidType("Given `link` must be <NodeEditorLink>")

        palette=QApplication.palette()

        # link for graphic item
        self.__link=link
        self.__link.renderModeChanged.connect(self.update)
        self.__link.colorChanged.connect(self.__colorUpdated)
        self.__link.colorSelectedChanged.connect(self.__colorSelectedUpdated)
        self.__link.sizeChanged.connect(self.__sizeUpdated)

        # define if link have a START/END values defined (by default, True)
        self.__isLinked=True

        # define link border
        self.__borderSize=2.0

        self.__borderColor=palette.color(QPalette.Dark)
        self.__borderColorSelected=palette.color(QPalette.Highlight)

        self.__borderPen=QPen(self.__borderColor)
        self.__borderPen.setWidth(self.__borderSize)
        self.__borderPen.setJoinStyle(Qt.MiterJoin)
        self.__borderPenSelected=QPen(self.__borderColorSelected)
        self.__borderPenSelected.setWidth(self.__borderSize)
        self.__borderPenSelected.setJoinStyle(Qt.MiterJoin)

        # link properties
        self.setZValue(NodeEditorScene.LINK_ZINDEX)
        self.setFlags(QGraphicsItem.ItemIsSelectable)

        self.__updatePath()

    def __updatePath(self):
        """Calculate path according to from/to points"""
        if self.__link is None:
            return

        fromPoint=self.__link.connectorFrom().graphicItem().scenePos()

        if self.__link.connectorTo() is None:
            # no 'end' connector (a temporary link): use current mouse position
            # over scene and update isLinked flag
            self.__isLinked=False
            toPoint=self.__link.scene().cursorScenePosition()
        else:
            # 'end' connector found: use connector position update isLinked flag
            self.__isLinked=True
            toPoint=self.__link.connectorTo().graphicItem().scenePos()

        # initialise path
        pathLink=QPainterPath()
        if self.__link.renderMode()==NodeEditorLink.RENDER_DIRECT or not self.__isLinked:
            # direct render mode: a simple line
            pathLink.moveTo(fromPoint)
            pathLink.lineTo(toPoint)
        elif self.__link.renderMode()==NodeEditorLink.RENDER_CURVE:
            # curve render mode:
            #   -- line from start
            #   -- a bezier curve
            #   -- line to end
            #
            # start/end lines take in account location on edge node
            #   left/right -- horizontal
            #   top/bottom -- vertical

            # calculate distance between start/end points
            deltaX=abs(fromPoint.x() - toPoint.x())
            deltaY=abs(fromPoint.y() - toPoint.y())

            # according to location, calculate points for line & bezier curves
            if self.__link.connectorFrom().location() in (NodeEditorConnector.LOCATION_LEFT_TOP, NodeEditorConnector.LOCATION_LEFT_BOTTOM):
                linePtF=QPointF(fromPoint.x() - NodeEditorGrLink.__RENDER_ANGLE_SIZE, fromPoint.y())
                cubicPtF=QPointF(fromPoint.x() - deltaX * NodeEditorGrLink.__RENDER_CURVE_FACTOR, fromPoint.y())
            elif self.__link.connectorFrom().location() in (NodeEditorConnector.LOCATION_RIGHT_TOP, NodeEditorConnector.LOCATION_RIGHT_BOTTOM):
                linePtF=QPointF(fromPoint.x() + NodeEditorGrLink.__RENDER_ANGLE_SIZE, fromPoint.y())
                cubicPtF=QPointF(fromPoint.x() + deltaX * NodeEditorGrLink.__RENDER_CURVE_FACTOR, fromPoint.y())
            elif self.__link.connectorFrom().location() in (NodeEditorConnector.LOCATION_TOP_LEFT, NodeEditorConnector.LOCATION_TOP_RIGHT):
                linePtF=QPointF(fromPoint.x(), fromPoint.y() - NodeEditorGrLink.__RENDER_ANGLE_SIZE)
                cubicPtF=QPointF(fromPoint.x(), fromPoint.y() - deltaY * NodeEditorGrLink.__RENDER_CURVE_FACTOR)
            elif self.__link.connectorFrom().location() in (NodeEditorConnector.LOCATION_BOTTOM_LEFT, NodeEditorConnector.LOCATION_BOTTOM_RIGHT):
                linePtF=QPointF(fromPoint.x(), fromPoint.y() + NodeEditorGrLink.__RENDER_ANGLE_SIZE)
                cubicPtF=QPointF(fromPoint.x(), fromPoint.y() + deltaY * NodeEditorGrLink.__RENDER_CURVE_FACTOR)

            if self.__link.connectorTo().location() in (NodeEditorConnector.LOCATION_LEFT_TOP, NodeEditorConnector.LOCATION_LEFT_BOTTOM):
                linePtT=QPointF(toPoint.x() - NodeEditorGrLink.__RENDER_ANGLE_SIZE, toPoint.y())
                cubicPtT=QPointF(toPoint.x() - deltaX * NodeEditorGrLink.__RENDER_CURVE_FACTOR, toPoint.y())
            elif self.__link.connectorTo().location() in (NodeEditorConnector.LOCATION_RIGHT_TOP, NodeEditorConnector.LOCATION_RIGHT_BOTTOM):
                linePtT=QPointF(toPoint.x() + NodeEditorGrLink.__RENDER_ANGLE_SIZE, toPoint.y())
                cubicPtT=QPointF(toPoint.x() + deltaX * NodeEditorGrLink.__RENDER_CURVE_FACTOR, toPoint.y())
            elif self.__link.connectorTo().location() in (NodeEditorConnector.LOCATION_TOP_LEFT, NodeEditorConnector.LOCATION_TOP_RIGHT):
                linePtT=QPointF(toPoint.x(), toPoint.y() - NodeEditorGrLink.__RENDER_ANGLE_SIZE)
                cubicPtT=QPointF(toPoint.x(), toPoint.y() - deltaY * NodeEditorGrLink.__RENDER_CURVE_FACTOR)
            elif self.__link.connectorTo().location() in (NodeEditorConnector.LOCATION_BOTTOM_LEFT, NodeEditorConnector.LOCATION_BOTTOM_RIGHT):
                linePtT=QPointF(toPoint.x(), toPoint.y() + NodeEditorGrLink.__RENDER_ANGLE_SIZE)
                cubicPtT=QPointF(toPoint.x(), toPoint.y() + deltaY * NodeEditorGrLink.__RENDER_CURVE_FACTOR)

            # generate path
            pathLink.moveTo(fromPoint)
            pathLink.lineTo(linePtF)
            pathLink.cubicTo(cubicPtF, cubicPtT, linePtT)
            pathLink.lineTo(toPoint)
        elif self.__link.renderMode()==NodeEditorLink.RENDER_ANGLE:
            # angle render mode:
            #   -- line from start
            #   -- line
            #   -- line to end
            #
            # start/end lines take in account location on edge node
            #   left/right -- horizontal
            #   top/bottom -- vertical

            # calculate distance between start/end points
            deltaX=abs(fromPoint.x() - toPoint.x()) - 2 * NodeEditorGrLink.__RENDER_ANGLE_SIZE
            deltaY=abs(fromPoint.y() - toPoint.y()) - 2 * NodeEditorGrLink.__RENDER_ANGLE_SIZE

            # according to location, calculate points for line & bezier curves
            if self.__link.connectorFrom().location() in (NodeEditorConnector.LOCATION_LEFT_TOP, NodeEditorConnector.LOCATION_LEFT_BOTTOM):
                linePtF=QPointF(fromPoint.x() - NodeEditorGrLink.__RENDER_ANGLE_SIZE, fromPoint.y())
            elif self.__link.connectorFrom().location() in (NodeEditorConnector.LOCATION_RIGHT_TOP, NodeEditorConnector.LOCATION_RIGHT_BOTTOM):
                linePtF=QPointF(fromPoint.x() + NodeEditorGrLink.__RENDER_ANGLE_SIZE, fromPoint.y())
            elif self.__link.connectorFrom().location() in (NodeEditorConnector.LOCATION_TOP_LEFT, NodeEditorConnector.LOCATION_TOP_RIGHT):
                linePtF=QPointF(fromPoint.x(), fromPoint.y() - NodeEditorGrLink.__RENDER_ANGLE_SIZE)
            elif self.__link.connectorFrom().location() in (NodeEditorConnector.LOCATION_BOTTOM_LEFT, NodeEditorConnector.LOCATION_BOTTOM_RIGHT):
                linePtF=QPointF(fromPoint.x(), fromPoint.y() + NodeEditorGrLink.__RENDER_ANGLE_SIZE)

            if self.__link.connectorTo().location() in (NodeEditorConnector.LOCATION_LEFT_TOP, NodeEditorConnector.LOCATION_LEFT_BOTTOM):
                linePtT=QPointF(toPoint.x() - NodeEditorGrLink.__RENDER_ANGLE_SIZE, toPoint.y())
            elif self.__link.connectorTo().location() in (NodeEditorConnector.LOCATION_RIGHT_TOP, NodeEditorConnector.LOCATION_RIGHT_BOTTOM):
                linePtT=QPointF(toPoint.x() + NodeEditorGrLink.__RENDER_ANGLE_SIZE, toPoint.y())
            elif self.__link.connectorTo().location() in (NodeEditorConnector.LOCATION_TOP_LEFT, NodeEditorConnector.LOCATION_TOP_RIGHT):
                linePtT=QPointF(toPoint.x(), toPoint.y() - NodeEditorGrLink.__RENDER_ANGLE_SIZE)
            elif self.__link.connectorTo().location() in (NodeEditorConnector.LOCATION_BOTTOM_LEFT, NodeEditorConnector.LOCATION_BOTTOM_RIGHT):
                linePtT=QPointF(toPoint.x(), toPoint.y() + NodeEditorGrLink.__RENDER_ANGLE_SIZE)

            pathLink.moveTo(fromPoint)
            pathLink.lineTo(linePtF)
            pathLink.lineTo(linePtT)
            pathLink.lineTo(toPoint)

        self.setPath(pathLink)

    def __colorUpdated(self, value):
        """Color has been updated"""
        self.__borderPen.setColor(QColor(value))
        self.update()

    def __colorSelectedUpdated(self, value):
        """Color has been updated for selected link"""
        self.__borderPenSelected.setColor(QColor(value))
        self.update()

    def __sizeUpdated(self, value):
        """Size has been updated"""
        self.__borderSize=value
        self.__borderPen.setWidth(self.__borderSize)
        self.__borderPenSelected.setWidth(self.__borderSize)
        self.update()

    def itemChange(self, change, value):
        """A QGraphicsItem property has been changed"""
        self.__link.itemChange(change, value)
        return super(NodeEditorGrLink, self).itemChange(change, value)

    def paint(self, painter, options, widget=None):
        """Render link"""
        painter.setRenderHints(QPainter.Antialiasing, True)

        # update path if needed
        self.__updatePath()

        # according to current selectionstate, define color
        if self.isSelected():
            pen=QPen(self.__borderPenSelected)
        else:
            pen=QPen(self.__borderPen)

        if not self.__isLinked:
            # if not linked, draw a bullet at current 'end' position
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(pen.color()))
            painter.drawEllipse(self.__link.scene().cursorScenePosition(), 2*self.__borderSize, 2*self.__borderSize)
            # and use dashed line to render path
            pen.setStyle(Qt.DotLine)

        painter.setPen(pen)

        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())


class NodeEditorGrCutLine(QGraphicsItem):
    """A cut line"""

    # default factors for curves/angle links render

    def __init__(self, parent=None):
        super(NodeEditorGrCutLine, self).__init__(parent)

        palette=QApplication.palette()

        # default bounding rect, no need here to have exactly a bounding rect...
        self.__boundingRect=QRectF(0,0,1,1)

        # link for graphic item
        self.__points=[]

        # define line properties
        self.__lineSize=1.0
        self.__lineColor=QColor("#88ffff00")
        self.__lineStyle=Qt.DashLine

        self.__pen=QPen(self.__lineColor)
        self.__pen.setWidth(self.__lineSize)
        self.__pen.setStyle(self.__lineStyle)

        # link properties
        self.setVisible(False)
        self.setZValue(NodeEditorScene.CUT_ZINDEX)

    def boundingRect(self):
        """Return bouding rect for connector"""
        return self.__boundingRect

    def points(self):
        """Return points from cut line"""
        return self.__points

    def color(self):
        """Return line color"""
        return self.__lineColor

    def setColor(self, value):
        """Update line color"""
        if isinstance(value, (QColor, str)):
            try:
                self.__lineColor=QColor(value)
                self.__pen.setColor(self.__lineColor)
            except:
                pass

    def size(self):
        """Return line width"""
        return self.__lineSize

    def setSize(self, value):
        """Update line width"""
        if isinstance(value, (int, float)):
            self.__lineSize=float(value)
            self.__pen.setWidth(self.__lineSize)

    def style(self):
        """Return line style"""
        return self.__lineStyle

    def setStyle(self, value):
        """Update line style"""
        if isinstance(value, int) and value>=1 and value<=5:
            self.__lineStyle=value
            self.__pen.setStyle(self.__lineStyle)
        elif isinstance(value, list):
            invalid=[item for item in value if not isinstance(item, (float, int))]
            if len(invalid)==0:
                # all values are valid
                self.__lineStyle=value
                self.__pen.setStyle(Qt.CustomDashLine)
                self.__pen.setDashPattern(value)

    def clear(self):
        """Clear line"""
        self.__points=[]
        self.update()

    def appendPosition(self, position):
        """Clear line"""
        if isinstance(position, (QPointF, QPoint)):
            self.__points.append(QPointF(position))
            self.update()

    def paint(self, painter, options, widget=None):
        """Render cut line"""
        painter.setRenderHints(QPainter.Antialiasing, True)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(self.__pen)

        polygon=QPolygonF(self.__points)
        painter.drawPolyline(polygon)



# ------------------------------------------------------------------------------


class WNodeEditorView(QGraphicsView):
    """A graphic view dedicated to render scene"""
    zoomChanged=Signal(float)

    def __init__(self, scene, parent=None):
        super(WNodeEditorView, self).__init__(scene, parent)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setRenderHint(QPainter.TextAntialiasing)

        #self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        #self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.setRubberBandSelectionMode(Qt.ContainsItemBoundingRect)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)

        self.__cutLine=NodeEditorGrCutLine()
        scene.addItem(self.__cutLine)
        self.__currentZoomFactor = 1.0
        self.__zoomStep=0.25
        self.setMouseTracking(True)
        self.setCacheMode(QGraphicsView.CacheBackground)

    def cutLine(self):
        """Return cut line instance

        Allows to modify properties
        """
        return self.__cutLine

    def cutLineDeleteLinks(self):
        """Delete all links which intersect cut line"""
        points=self.__cutLine.points()
        scene=self.scene().scene()
        for ptNumber in range(len(points)-1):
            path=QPainterPath(points[ptNumber])
            path.lineTo(points[ptNumber+1])

            linksToRemove=[]
            for link in scene.links():
                if path.intersects(link.graphicItem().path()):
                    linksToRemove.append(link)

            for link in linksToRemove:
                scene.removeLink(link)

    def mousePressEvent(self, event):
        """On left button pressed, start to pan scene"""
        if event.button() == Qt.LeftButton:
            hoverItem=self.itemAt(event.pos())
            if event.modifiers()&Qt.ShiftModifier==Qt.ShiftModifier:
                self.setDragMode(QGraphicsView.RubberBandDrag)
            elif event.modifiers()&Qt.AltModifier==Qt.AltModifier:
                self.setCursor(Qt.CrossCursor)
                self.__cutLine.setVisible(True)
                self.__cutLine.appendPosition(self.mapToScene(event.pos()))
            elif not isinstance(hoverItem, NodeEditorGrConnector):
                self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif event.button() == Qt.MidButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            # it seems Qt manage pan only with left button
            # so emulate leftbutton event when middle button is used for panning
            event=QMouseEvent(event.type(), event.localPos(), Qt.LeftButton, Qt.LeftButton, event.modifiers())
        elif event.button() == Qt.RightButton:
            self.centerOn(self.sceneRect().center())
            self.setDragMode(QGraphicsView.NoDrag)

        super(WNodeEditorView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """On left button released, stop to pan scene"""
        if event.button() in (Qt.LeftButton, Qt.MidButton) and self.dragMode()==QGraphicsView.ScrollHandDrag:
            self.setDragMode(QGraphicsView.NoDrag)
        elif event.button() == Qt.LeftButton and self.__cutLine.isVisible():
            self.setDragMode(QGraphicsView.NoDrag)
            self.cutLineDeleteLinks()
            self.__cutLine.setVisible(False)
            self.__cutLine.clear()
            self.unsetCursor()

        super(WNodeEditorView, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Mouse is moving..."""
        if event.buttons()&Qt.LeftButton == Qt.LeftButton and self.__cutLine.isVisible():
            self.__cutLine.appendPosition(self.mapToScene(event.pos()))

        super(WNodeEditorView, self).mouseMoveEvent(event)


    def wheelEvent(self, event:QWheelEvent):
        """Manage to zoom with wheel"""

        if event.angleDelta().y() > 0:
            self.setZoom(self.__currentZoomFactor + self.__zoomStep)
        else:
            self.setZoom(self.__currentZoomFactor - self.__zoomStep)

    def zoom(self):
        """Return current zoom property

        returned value is a tuple (ratio, QRectF) or None if there's no image
        """
        return self.__currentZoomFactor

    def setZoom(self, value=0.0):
        """Set current zoom value"""
        if value > 0:
            isIncreased=(value>self.__currentZoomFactor)

            self.__currentZoomFactor = round(value, 2)
            self.scene().setViewZoom(self.__currentZoomFactor)
            self.resetTransform()
            self.scale(self.__currentZoomFactor, self.__currentZoomFactor)

            self.zoomChanged.emit(self.__currentZoomFactor)

            if isIncreased:
                if self.__currentZoomFactor>=0.25:
                    self.__zoomStep=0.25
                elif self.__currentZoomFactor>=0.1:
                    self.__zoomStep=0.05
                else:
                    self.__zoomStep=0.01
            else:
                if self.__currentZoomFactor<=0.1:
                    self.__zoomStep=0.01
                elif self.__currentZoomFactor<=0.25:
                    self.__zoomStep=0.05
                else:
                    self.__zoomStep=0.25
