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
# The bcwpreview module provides class used to render image preview
#
# Main classes from this module
#
# - BCWPreview:
#       Widget to display image with function like zoom in/out, play animation
#
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

from bulicommander.pktk.modules.imgutils import buildIcon
from bulicommander.pktk.modules.utils import (
        Debug,
        loadXmlUi
    )

from bulicommander.pktk.pktk import (
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

        self.__lblNoPreviewPixmap = None
        self.__lblNoPreviewResizeEventOrigin = self.lblNoPreview.resizeEvent
        self.lblNoPreview.resizeEvent = self.__lblNoPreviewResizeEvent

        # Allow zooming with right mouse button.
        # Drag for zoom box, doubleclick to view full image.
        self.gvPreview.zoomChanged.connect(self.__zoomChanged)
        self.hsAnimatedFrameNumber.valueChanged.connect(self.__animatedFrameChange)
        self.tbPlayPause.clicked.connect(self.__playPauseAnimation)
        self.hidePreview()

        self.wAnimated.setVisible(False)

    def __zoomChanged(self, value):
        self.lblPreviewZoom.setText(f"View at {value:.2f}%")

    def __lblNoPreviewResizeEvent(self, event):
        """Resize pixmap when label is resized"""
        self.__lblNoPreviewResizeEventOrigin(event)

        if self.__lblNoPreviewPixmap:
            if event.size().width() > self.__lblNoPreviewPixmap.width() and event.size().height() > self.__lblNoPreviewPixmap.height():
                self.lblNoPreview.setPixmap(self.__lblNoPreviewPixmap)
            else:
                self.lblNoPreview.setPixmap(self.__lblNoPreviewPixmap.scaled(event.size().width(), event.size().height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def hidePreview(self, msg=None):
        """Hide preview and display message"""
        if msg is None:
            self.__lblNoPreviewPixmap = None
            self.lblNoPreview.setText("No image selected")
        elif isinstance(msg, str):
            self.__lblNoPreviewPixmap = None
            self.lblNoPreview.setText(msg)
        else:
            self.__lblNoPreviewPixmap = msg
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
        nbZ = len(f"{self.__maxAnimatedFrame}")
        self.lblAnimatedFrameNumber.setText(f'Frame {self.__currentAnimatedFrame:>0{nbZ}}/{self.__maxAnimatedFrame} ')

        if self.__imgReaderAnimated is not None:
            if self.__imgReaderAnimated.state() != QMovie.Running:
                self.__imgReaderAnimated.jumpToFrame(self.__currentAnimatedFrame - 1)
            self.gvPreview.setImage(self.__imgReaderAnimated.currentImage(), False)

    def __playPauseAnimation(self, value):
        """Play/pause current animation"""
        if self.__imgReaderAnimated is not None:
            if self.__imgReaderAnimated.state() == QMovie.Running:
                self.__imgReaderAnimated.setPaused(True)
                self.tbPlayPause.setIcon(buildIcon("pktk:play"))
                self.__imgReaderAnimated.frameChanged.disconnect(self.setCurrentAnimatedFrame)
            elif self.__imgReaderAnimated.state() == QMovie.Paused:
                self.__imgReaderAnimated.frameChanged.connect(self.setCurrentAnimatedFrame)
                self.__imgReaderAnimated.setPaused(False)
                self.tbPlayPause.setIcon(buildIcon("pktk:pause"))
            else:
                # not running
                self.__imgReaderAnimated.frameChanged.connect(self.setCurrentAnimatedFrame)
                self.__imgReaderAnimated.start()
                self.tbPlayPause.setIcon(buildIcon("pktk:pause"))

    def hideAnimatedFrames(self):
        """Hide animated frames"""
        self.wAnimated.setVisible(False)
        self.__currentAnimatedFrame = 0
        self.__maxAnimatedFrame = 0
        if self.__imgReaderAnimated is not None:
            self.__imgReaderAnimated.stop()
            self.__imgReaderAnimated = None

    def showAnimatedFrames(self, fileName, maxAnimatedFrames):
        """Show animated frames for given filename"""
        try:
            self.__imgReaderAnimated = QMovie(fileName)
            self.__imgReaderAnimated.setCacheMode(QMovie.CacheAll)
            self.__maxAnimatedFrame = maxAnimatedFrames
            self.tbPlayPause.setIcon(buildIcon("pktk:play"))
            self.wAnimated.setVisible(True)
            self.hsAnimatedFrameNumber.setMaximum(self.__maxAnimatedFrame)
            self.hsAnimatedFrameNumber.setValue(1)
            self.lblAnimatedFrameNumber.setText(f"1/{self.__maxAnimatedFrame}")
        except Exception:
            Debug.print('[BCWPreview.showAnimatedFrames] Unable to read animated GIF {0}: {1}', fileName, e)
            self.__imgReaderAnimated = None

            showAnimatedFrames

    def currentAnimatedFrame(self):
        """Return current animated frame number"""
        return self.__currentAnimatedFrame

    def setCurrentAnimatedFrame(self, value):
        """set current animated frame number"""
        if value > 0 and value <= self.__maxAnimatedFrame and value != self.__currentAnimatedFrame:
            self.__currentAnimatedFrame = value
            self.hsAnimatedFrameNumber.setValue(self.__currentAnimatedFrame)

    def gotoNextAnimatedFrame(self, loop=True):
        """go to next animated frame number

        if last frame is reached, according to `loop` value:
            - if True, go to first frame
            - if False, stop
        """
        if self.__currentAnimatedFrame < self.__maxAnimatedFrame:
            self.__currentAnimatedFrame += 1
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
            self.__currentAnimatedFrame -= 1
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
