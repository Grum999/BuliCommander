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

from enum import Enum


import os.path

import PyQt5.uic


from PyQt5.Qt import *

from PyQt5.QtGui import (
        QImage,
        QMovie,
        QPixmap
    )
from PyQt5.QtWidgets import (
        QWidget
    )


from .bcutils import (
        Debug,
        loadXmlUi
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )


# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------
class BCWPreview(QWidget):
    """interface to display image previewBackground

    - Zoom label
    - Frame(s) for animated gif
    - Display text for unreadable images
    """

    def __init__(self, parent=None):
        super(BCWPreview, self).__init__(parent)

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcwpreview.ui')
        loadXmlUi(uiFileName, self)

        self.__currentAnimatedFrame = 0
        self.__maxAnimatedFrame = 0
        self.__imgReaderAnimated = None

        # Allow zooming with right mouse button.
        # Drag for zoom box, doubleclick to view full image.
        self.gvPreview.setCacheMode(QGraphicsView.CacheBackground)
        self.gvPreview.zoomChanged.connect(self.__zoomChanged)
        self.hsAnimatedFrameNumber.valueChanged.connect(self.__animatedFrameChange)
        self.tbPlayPause.clicked.connect(self.__playPauseAnimation)
        self.hidePreview()

        self.wAnimated.setVisible(False)

    def __zoomChanged(self, value):
        self.lblPreviewZoom.setText(f"View at {value:.2f}%")


    def hidePreview(self, msg=None):
        """Hide preview and display message"""
        if msg is None:
            self.lblNoPreview.setText("No image selected")
        elif isinstance(msg, str):
            self.lblNoPreview.setText(msg)
        else:
            self.lblNoPreview.setPixmap(msg)

        self.swPreview.setCurrentIndex(1)


    def showPreview(self, img=None):
        """Hide preview and display message"""
        self.swPreview.setCurrentIndex(0)
        self.gvPreview.setImage(img)
        self.lblNoPreview.setText("...")


    def setText(self, msg):
        """Set hidden text preview"""
        self.lblNoPreview.setText(msg)


    def __animatedFrameChange(self, value):
        """Slider for animated frame has been moved"""
        self.__currentAnimatedFrame = value
        nbZ=len(str(self.__maxAnimatedFrame))
        self.lblAnimatedFrameNumber.setText(f'Frame {self.__currentAnimatedFrame:>0{nbZ}}/{self.__maxAnimatedFrame} ')

        if not self.__imgReaderAnimated is None:
            if self.__imgReaderAnimated.state() != QMovie.Running:
                self.__imgReaderAnimated.jumpToFrame(self.__currentAnimatedFrame - 1)
            self.gvPreview.setImage(self.__imgReaderAnimated.currentImage(), False)


    def __playPauseAnimation(self, value):
        """Play/pause current animation"""
        if not self.__imgReaderAnimated is None:
            if self.__imgReaderAnimated.state() == QMovie.Running:
                self.__imgReaderAnimated.setPaused(True)
                self.tbPlayPause.setIcon(QIcon(":/images/play"))
                self.__imgReaderAnimated.frameChanged.disconnect(self.setCurrentAnimatedFrame)
            elif self.__imgReaderAnimated.state() == QMovie.Paused:
                self.__imgReaderAnimated.frameChanged.connect(self.setCurrentAnimatedFrame)
                self.__imgReaderAnimated.setPaused(False)
                self.tbPlayPause.setIcon(QIcon(":/images/pause"))
            else:
                # not running
                self.__imgReaderAnimated.frameChanged.connect(self.setCurrentAnimatedFrame)
                self.__imgReaderAnimated.start()
                self.tbPlayPause.setIcon(QIcon(":/images/pause"))


    def hideAnimatedFrames(self):
        """Hide animated frames"""
        self.wAnimated.setVisible(False)
        self.__currentAnimatedFrame=0
        self.__maxAnimatedFrame=0
        if not self.__imgReaderAnimated is None:
            self.__imgReaderAnimated.stop()
            self.__imgReaderAnimated = None


    def showAnimatedFrames(self, fileName, maxAnimatedFrames):
        """Show animated frames for given filename"""
        try:
            self.__imgReaderAnimated = QMovie(fileName)
            self.__imgReaderAnimated.setCacheMode(QMovie.CacheAll)
            self.__maxAnimatedFrame=maxAnimatedFrames
            self.tbPlayPause.setIcon(QIcon(":/images/play"))
            self.wAnimated.setVisible(True)
            self.hsAnimatedFrameNumber.setMaximum(self.__maxAnimatedFrame)
            self.hsAnimatedFrameNumber.setValue(1)
            self.lblAnimatedFrameNumber.setText(f"1/{self.__maxAnimatedFrame}")
        except:
            Debug.print('[BCWPreview.showAnimatedFrames] Unable to read animated GIF {0}: {1}', fileName, e)
            self.__imgReaderAnimated=None

            showAnimatedFrames


    def currentAnimatedFrame(self):
        """Return current animated frame number"""
        return self.__currentAnimatedFrame


    def setCurrentAnimatedFrame(self, value):
        """set current animated frame number"""
        if value > 0 and value <= self.__maxAnimatedFrame and value!=self.__currentAnimatedFrame:
            self.__currentAnimatedFrame = value
            self.hsAnimatedFrameNumber.setValue(self.__currentAnimatedFrame)


    def gotoNextAnimatedFrame(self, loop=True):
        """go to next animated frame number

        if last frame is reached, according to `loop` value:
            - if True, go to first frame
            - if False, stop
        """
        if self.__currentAnimatedFrame < self.__maxAnimatedFrame:
            self.__currentAnimatedFrame+=1
        elif loop:
            self.__currentAnimatedFrame = 1
        else:
            return
        self.hsAnimatedFrameNumber.setValue(self.__currentAnimatedFrame)


    def gotoPrevAnimatedFrame(self, loop=True):
        """go to previous animated frame number

        if first frame is reached, according to `loop` value:
            - if True, go to first frame
            - if False, stop
        """
        if self.__currentAnimatedFrame > 1:
            self.__currentAnimatedFrame-=1
        elif loop:
            self.__currentAnimatedFrame = self.__maxAnimatedFrame
        else:
            return
        self.hsAnimatedFrameNumber.setValue(self.__currentAnimatedFrame)


    def hasImage(self):
        """Return if current preview has an image"""
        return self.gvPreview.hasImage()

    def backgroundType(self):
        """Return current background type for preview"""
        return self.gvPreview.backgroundType()

    def setBackgroundType(self, value):
        """Set current background type for preview"""
        return self.gvPreview.setBackgroundType(value)
