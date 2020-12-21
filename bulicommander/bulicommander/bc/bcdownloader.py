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


import time
import os.path

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )

from .bcutils import (
        bytesSizeToStr,
        BCTimer,
        Debug
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )



class BCDownloader(QObject):
    finished = Signal(int)
    progress = Signal(int, int)

    def __init__(self, url, target, parent=None):
        super(BCDownloader, self).__init__(parent)
        self.__manager = QNetworkAccessManager()
        self.__url=url
        self.__target=target
        self.__reply = None
        self.__totalBytes = 0
        self.__currentBytes = 0
        self.__startTime=0
        self.__endTime=0
        self.__fHandle=None

    def __repr__(self):
        return f"<BCDownloader({self.downloadProgress()}, {round(self.downloadTime(), 2)}s,  {bytesSizeToStr(self.downloadRate())}/s, {self.__url})>"

    def __flush(self):
        """Flush received data to file"""
        error=0
        if self.__reply:
            error=self.__reply.error()

        if self.__reply and self.__reply.bytesAvailable()>0 and error==0:
            if self.__fHandle:
                try:
                    self.__fHandle.write(self.__reply.read(self.__reply.bytesAvailable()))
                except Exception as e:
                    Debug.print('[BCDownloader.download] unable to flush buffer to target file {0}: {1}', self.__target, e)

        if self.__reply and self.__reply.isFinished():
            if self.__fHandle:
                self.__fHandle.close()
                self.__fHandle=None

            self.__reply.downloadProgress.disconnect(self.__onProgress)
            self.__reply.deleteLater()
            self.__reply=None
            self.finished.emit(error)

    def __onProgress(self, bytesReceived, bytesTotal):
        """Received data from host, flush buffer and emit singal"""
        self.__totalBytes = bytesTotal
        self.__currentBytes = bytesReceived
        self.__flush()
        self.progress.emit(bytesReceived, bytesTotal)

    def download(self):
        """Start download"""
        self.__startTime=time.time()
        self.__reply = self.__manager.get(QNetworkRequest(QUrl(self.__url)))
        if self.__reply.error():
            return self.__reply.error()

        try:
            self.__fHandle=open(self.__target, 'wb')
        except Exception as e:
            Debug.print('[BCDownloader.download] unable to open target file {0}: {1}', self.__target, e)

        self.__reply.downloadProgress.connect(self.__onProgress)

        return True

    def downloadStop(self):
        """Stop download"""
        if self.__reply:
            self.__reply.abort()
            self.__startTime=0
            self.__endTime=0

        return True

    def url(self):
        """Return current url"""
        return self.__url

    def target(self):
        """Return current target"""
        return self.__target

    def downloadTime(self):
        """Return time (in seconds) needed to download file

        If download is not yet started, return 0
        If download is not yet finished, return current downloading time
        """
        if self.__startTime==0:
            return 0

        if self.__endTime==0:
            return time.time() - self.__startTime

        return self.__endTime - self.__startTime

    def downloadRate(self):
        """Return average byte rate (in bytes/seconds) needed to download file

        If download is not yet started, return 0
        If download is not yet finished, return current average byte rate
        """
        if self.__startTime==0 or self.downloadTime()==0:
            return 0

        return self.__currentBytes/self.downloadTime()

    def downloadProgress(self):
        """Return current download progress as a tuple (pct, currentBytes, totalBytes)"""
        if self.__totalBytes==0:
            return (0.0, 0, 0)
        else:
            return (round(100*self.__currentBytes/self.__totalBytes, 2), self.__currentBytes, self.__totalBytes)
