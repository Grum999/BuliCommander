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
# The bcdownloader module provides used to manage download
#
# Main classes from this module
#
# - BCDownloader:
#       A simple class to asynchronous download files from given url
#
# -----------------------------------------------------------------------------


import time
import os.path

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )

from bulicommander.pktk.modules.strutils import bytesSizeToStr
from bulicommander.pktk.modules.utils import Debug

from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )


class BCDownloader(QObject):
    finished = Signal(int, str)
    progress = Signal(int, int)

    def __init__(self, url, target, parent=None):
        super(BCDownloader, self).__init__(parent)
        self.__manager = QNetworkAccessManager()
        self.__url = url
        self.__target = os.path.normpath(target)
        self.__reply = None
        self.__totalBytes = 0
        self.__currentBytes = 0
        self.__startTime = 0
        self.__endTime = 0
        self.__fHandle = None
        self.__sslErrors = []

        self.__manager.setStrictTransportSecurityEnabled(False)

    def __repr__(self):
        return f"<BCDownloader({self.downloadProgress()}, {round(self.downloadTime(), 2)}s,  {bytesSizeToStr(self.downloadRate())}/s, {self.__url})>"

    def __flush(self):
        """Flush received data to file"""
        error = 0
        if self.__reply:
            error = self.__reply.error()

        if self.__reply and self.__reply.bytesAvailable() > 0 and error == 0:
            if self.__fHandle:
                try:
                    self.__fHandle.write(self.__reply.read(self.__reply.bytesAvailable()))
                except Exception as e:
                    Debug.print('[BCDownloader.download] unable to flush buffer to target file {0}: {1}', self.__target, e)

        if self.__reply and self.__reply.isFinished():
            if self.__fHandle:
                self.__fHandle.close()
                self.__fHandle = None

            if error != 0:
                errorStr = "\n".join([self.__reply.errorString()]+self.__sslErrors)
            else:
                errorStr = ''
            self.__reply.downloadProgress.disconnect(self.__onProgress)
            self.__reply.deleteLater()
            self.__reply = None
            self.finished.emit(error, errorStr)

    def __onProgress(self, bytesReceived, bytesTotal):
        """Received data from host, flush buffer and emit singal"""
        self.__totalBytes = bytesTotal
        self.__currentBytes = bytesReceived
        self.__flush()
        self.progress.emit(bytesReceived, bytesTotal)

    def download(self):
        """Start download"""
        def sslErrors(errors):
            for error in errors:
                self.__sslErrors.append(error.errorString())

        self.__startTime = time.time()
        self.__reply = self.__manager.get(QNetworkRequest(QUrl(self.__url)))
        self.__reply.ignoreSslErrors([QSslError(QSslError.CertificateExpired),
                                      QSslError(QSslError.SelfSignedCertificate),
                                      QSslError(QSslError.UnableToGetLocalIssuerCertificate)])

        self.__reply.sslErrors.connect(sslErrors)
        self.__reply.downloadProgress.connect(self.__onProgress)

        if self.__reply.error():
            return self.__reply.error() != 0

        try:
            self.__fHandle = open(self.__target, 'wb')
        except Exception as e:
            Debug.print('[BCDownloader.download] unable to open target file {0}: {1}', self.__target, e)

        return True

    def downloadStop(self):
        """Stop download"""
        if self.__reply:
            self.__reply.abort()
            self.__startTime = 0
            self.__endTime = 0

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
        if self.__startTime == 0:
            return 0

        if self.__endTime == 0:
            return time.time() - self.__startTime

        return self.__endTime - self.__startTime

    def downloadRate(self):
        """Return average byte rate (in bytes/seconds) needed to download file

        If download is not yet started, return 0
        If download is not yet finished, return current average byte rate
        """
        if self.__startTime == 0 or self.downloadTime() == 0:
            return 0

        return self.__currentBytes/self.downloadTime()

    def downloadProgress(self):
        """Return current download progress as a tuple (pct, currentBytes, totalBytes)"""
        if self.__totalBytes == 0:
            return (0.0, 0, 0)
        else:
            return (round(100*self.__currentBytes/self.__totalBytes, 2), self.__currentBytes, self.__totalBytes)
