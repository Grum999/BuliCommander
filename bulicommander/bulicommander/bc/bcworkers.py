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
#from .pktk import PkTk

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QEventLoop,
        QRunnable,
        QThreadPool,
        QTimer
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

class BCTimer(object):

    @staticmethod
    def sleep(value):
        """Do a sleep of `value` milliseconds

        use of python timer.sleep() method seems to be not recommanded in a Qt application.. ??
        """
        loop = QEventLoop()
        QTimer.singleShot(value, loop.quit)
        loop.exec()


class BCWorkerSignals(QObject):
    processed = Signal(tuple)
    finished = Signal()


class BCWorker(QRunnable):
    """"A worker designed to process data from BCWorkerPool

    Not aimed to be instancied directly, jsut use BCWorkerPool
    """

    def __init__(self, pool, callback, *callbackArgv):
        """Initialise worker

        The given `callback` will be executed on each item from pool with give optional `*callbackArgv` arguements
        """
        super(BCWorker, self).__init__()
        self.__pool = pool
        self.__callback = callback
        self.__callbackArgv = callbackArgv
        self.signals = BCWorkerSignals()

    @pyqtSlot()
    def run(self):
        """Retrieve items from pool and process it

        If there's no more item to process in list, exit
        """
        while not self.__pool.stopProcessingAsked():
            # get next BCFile
            itemIndex, item = self.__pool.getNext()
            if item is None:
                # no more item to process
                break

            result = self.__callback(itemIndex, item, *self.__callbackArgv)
            self.signals.processed.emit((itemIndex, result))

        self.signals.finished.emit()


class BCWorkerPool(QObject):
    """A worker pool allows to process data using pyqt multithreading
    """

    def __init__(self, maxWorkerCount=None):
        super(BCWorkerPool, self).__init__()
        self.__threadpool = QThreadPool()
        #self.__threadpool = QThreadPool.globalInstance()

        if isinstance(maxWorkerCount, int) and maxWorkerCount>=1 and maxWorkerCount<=self.__threadpool.maxThreadCount():
            self.__maxWorkerCount = maxWorkerCount
        else:
            self.__maxWorkerCount =  self.__threadpool.maxThreadCount()

        self.__current = 0
        self.__locked = 0
        self.__started = 0
        self.__size = 0
        self.__nbWorkers = self.__threadpool.maxThreadCount()
        self.__workers = []
        self.__stopProcess = False
        self.__dataList = []
        self.__results = []
        self.__mapResults = False

        self.signals = BCWorkerSignals()

    def __lock(self):
        """Lock ensure that no worker will try to access to same item"""
        while self.__locked:
           BCTimer.sleep(1)
        self.__locked=True

    def __unlock(self):
        self.__locked=False

    def __onProcessed(self, processedNfo):
        """an item has been processed"""
        if self.__mapResults:
            index, item = processedNfo
            if not index is None:
                self.__results[index] = item
        self.signals.processed.emit(processedNfo)

    def __onFinished(self):
        """Do something.. ?"""
        self.__started-=1
        if self.__started==0:
            self.__workers.clear()
            self.signals.finished.emit()

    def stopProcessingAsked(self):
        return self.__stopProcess

    def getNext(self):
        """Get next item to process"""
        self.__lock()

        if self.__current is None:
            self.__unlock()
            return (None, None)
        returnedIndex = self.__current
        self.__current+=1

        if self.__current >= self.__size:
            self.__current = None

        self.__unlock()
        return (returnedIndex, self.__dataList[returnedIndex])

    def startProcessing(self, dataList, callback, *callbackArgv):
        """Start all current thread execution"""
        # ensure to stop current processing before creating a new one
        if self.__stopProcess == True:
            return
        else:
            self.stopProcessing()

        if not (isinstance(dataList, list) or isinstance(dataList, set) or isinstance(dataList, tuple)):
            raise EInvalidType('Given `dataList` must be a list')

        self.__size = len(dataList)

        if self.__size == 0:
            return

        self.__dataList = [v for v in dataList]

        if self.__mapResults:
            self.__results = [None] * self.__size
        else:
            self.__results = []


        # if number of items to process is less than number of possible threads,
        # don't use all threads
        self.__nbWorkers = min(self.__size, self.__maxWorkerCount)


        self.__started = 0
        self.__current = 0
        self.__workers.clear()

        # for test, force to 1 thread only
        #self.__nbWorkers = 1

        for index in range(self.__nbWorkers):
            self.__workers.append(BCWorker(self, callback, *callbackArgv))
            self.__workers[index].signals.processed.connect(self.__onProcessed)
            self.__workers[index].signals.finished.connect(self.__onFinished)
            self.__workers[index].setAutoDelete(True)
            self.__started+=1
            self.__threadpool.start(self.__workers[index])

    def stopProcessing(self):
        """Stop all current thread execution"""
        if self.__started > 0:
            self.__stopProcess = True
            while self.__started > 0:
                # check every 5ms if all thread are finished
                BCTimer.sleep(5)
            self.__stopProcess = False

    def waitProcessed(self):
        """Wait until all items in pool are processed"""
        # why self.__threadpool.waitForDone() don't work??
        while self.__started>0:
            BCTimer.sleep(1)

    def map(self, dataList, callback, *callbackArgv):
        """Apply `callback` function to each item `datalist` list and return a list

        Similar to python map() method, but for Qt threads
            https://docs.python.org/3/library/multiprocessing.html#multiprocessing.pool.Pool.map
        """
        if len(dataList) == 0:
            return []

        self.__mapResults = True
        self.startProcessing(dataList, callback, *callbackArgv)
        self.waitProcessed()
        self.__mapResults = False
        return self.__results


