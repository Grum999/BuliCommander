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




# -----------------------------------------------------------------------------

import re
from enum import Enum

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )
from PyQt5.QtWidgets import (
        QWidget
    )

from ..modules.utils import replaceLineEditClearButton


class WOperatorType:
    OPERATOR_GT=          '>'
    OPERATOR_GE=          '>='
    OPERATOR_LT=          '<'
    OPERATOR_LE=          '<='
    OPERATOR_EQ=          '='
    OPERATOR_NE=          '!='
    OPERATOR_BETWEEN=     'between'
    OPERATOR_NOT_BETWEEN= 'not between'
    OPERATOR_MATCH=       'match'
    OPERATOR_NOT_MATCH=   'not match'
    OPERATOR_LIKE=        'like'
    OPERATOR_NOT_LIKE=    'not like'


class WOperatorBaseInput(QWidget):
    """A widget to define search condition using operator

    Class <WOperatorBaseInput> is ancestor for:
    - WOperatorInputInt
    - WOperatorInputFloat
    - WOperatorInputStr
    - WOperatorInputDateTime

             | int   |     |      |           |
    Operator | float | str | date | date/time |
    ---------+-------+-----+------+-----------+
    >        | x     |     | x    | x         |
    >=       | x     |     | x    | x         |
    <        | x     |     | x    | x         |
    <=       | x     |     | x    | x         |
    =        | x     | x   | x    | x         |
    !=       | x     | x   | x    | x         |
    between  | x     |     | x    | x         |
    !between | x     |     | x    | x         |
    match    |       | x   |      |           |
    !match   |       | x   |      |           |
    like     |       | x   |      |           |
    !like    |       | x   |      |           |
             |       |     |      |           |

    According to searched type:

                                       (for between operator)
                QComboBox   Input*     Input*
                <-------->  <--------> <---------------->      *Input

                +--------+  +--------+         +--------+
    int         |       V|  |      <>|     and |      <>|      QSpinBox
                +--------+  +--------+         +--------+

                +--------+  +--------+         +--------+
    float       |       V|  |      <>|     and |      <>|      QDoubleSpinBox
                +--------+  +--------+         +--------+

                +--------+  +--------+
    str         |       V|  |        |                         QLineEdit
                +--------+  +--------+

                +--------+  +--------+         +--------+
    date        |       V|  |      <>|     and |      <>|      QDateEdit
                +--------+  +--------+         +--------+

                +--------+  +--------+         +--------+
    date/time   |       V|  |      <>|     and |      <>|      QDateTimeEdit
                +--------+  +--------+         +--------+

    """
    operatorChanged=Signal(str)
    valueChanged=Signal(object)
    value2Changed=Signal(object)

    __LABELS={
            WOperatorType.OPERATOR_GT:          '>',
            WOperatorType.OPERATOR_GE:          '≥',
            WOperatorType.OPERATOR_LT:          '<',
            WOperatorType.OPERATOR_LE:          '≤',
            WOperatorType.OPERATOR_EQ:          '=',
            WOperatorType.OPERATOR_NE:          '≠',
            WOperatorType.OPERATOR_BETWEEN:     i18n('between'),
            WOperatorType.OPERATOR_NOT_BETWEEN: i18n('not between'),
            WOperatorType.OPERATOR_MATCH:       i18n('match'),
            WOperatorType.OPERATOR_NOT_MATCH:   i18n('not match'),
            WOperatorType.OPERATOR_LIKE:        i18n('like'),
            WOperatorType.OPERATOR_NOT_LIKE:    i18n('not like')
        }

    @staticmethod
    def operatorLabel(operator):
        """Return label for operator"""
        if operator in WOperatorBaseInput.__LABELS:
            return WOperatorBaseInput.__LABELS[operator]
        return str(operator)

    def __init__(self, parent=None):
        super(WOperatorBaseInput, self).__init__(parent)
        self._inInit=True

        self._defaultOperatorList=[]

        self.__layout=QBoxLayout(QBoxLayout.LeftToRight)
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.__layout.setDirection(QBoxLayout.LeftToRight)

        self._cbOperatorList=QComboBox()
        self._cbOperatorList.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self._cbOperatorList.currentIndexChanged.connect(self.__operatorChanged)

        self._input1=QWidget()
        self._input2=QWidget()
        self._lblAnd=QLabel(i18n('and'))
        self._lblAnd.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        # initialise UI
        self._initializeUi()

        self.__layout.addWidget(self._cbOperatorList)
        self.__layout.addWidget(self._input1)
        self.__layout.addWidget(self._lblAnd)
        self.__layout.addWidget(self._input2)

        self.setLayout(self.__layout)
        self._inInit=False

    def _initOperator(self, values):
        """Initialise operator combox box from given list"""
        self._inInit=True
        self._cbOperatorList.clear()
        for operator in values:
            self._cbOperatorList.addItem(WOperatorBaseInput.__LABELS[operator], operator)
        self._inInit=False

    def __operatorChanged(self, index):
        """Operator value has been changed"""
        self._operator=self._cbOperatorList.currentData()

        input2Visible=(self._operator in [WOperatorType.OPERATOR_BETWEEN, WOperatorType.OPERATOR_NOT_BETWEEN])

        self._lblAnd.setVisible(input2Visible)
        self._input2.setVisible(input2Visible)
        self._input2.setEnabled(input2Visible)

        if self._inInit:
            return

        self.operatorChanged.emit(self._operator)

    def _initializeUi(self):
        """Implemented by sub classes to initialise interface"""
        raise EInvalidStatus("Method '_initialize' must be overrided by sub-classes")

    def operator(self):
        """Return current operator"""
        return self._operator

    def setOperator(self, value):
        """Set current operator"""
        if value==self._cbOperatorList.currentData():
            return

        for index in range(self._cbOperatorList.count()):
            if self._cbOperatorList.itemData(index)==value:
                self._cbOperatorList.setCurrentIndex(index)

    def value(self):
        """Return current value"""
        pass

    def setValue(self, value):
        """set current value"""
        pass

    def value2(self):
        """Return current 2nd value (when 'between' operator)"""
        pass

    def setValue2(self, value):
        """Set current 2nd value (when 'between' operator)"""
        pass

    def orientation(self):
        """Return current layout orientation"""
        if self.__layout.direction() in (QBoxLayout.LeftToRight, QBoxLayout.RightToLeft):
            return Qt.Horizontal
        else:
            return Qt.Vertical

    def setOrientation(self, value):
        """Set current layout orientation"""
        if value==Qt.Horizontal:
            self.__layout.setDirection(QBoxLayout.LeftToRight)
        else:
            self.__layout.setDirection(QBoxLayout.TopToBottom)

    def operators(self):
        """Return list of available operators"""
        return [self._cbOperatorList.itemData(index) for index in range(self._cbOperatorList.count())]

    def setOperators(self, operators=None):
        """Define list of available operators

        If `operators` is None or empty list, reset to default operators for widget
        """
        validList=[]
        if isinstance(operators, list):
            validList=[operator for operator in operators if operator in self._defaultOperatorList]

        if operators is None or len(validList)==0:
            validList=self._defaultOperatorList

        self._initOperator(validList)
        self.setOperator(self._operator)


class WOperatorBaseInputNumber(WOperatorBaseInput):
    """Search operator for Integer"""
    suffixChanged=Signal(str)

    def __init__(self, parent=None):
        super(WOperatorBaseInputNumber, self).__init__(parent)
        self._suffixList=[]
        self._suffixLabel=""

    def _initializeUi(self):
        """Initialise widget

        - Operator list
        - Input widgets
        """
        self._defaultOperatorList=[
                WOperatorType.OPERATOR_GT,
                WOperatorType.OPERATOR_GE,
                WOperatorType.OPERATOR_LT,
                WOperatorType.OPERATOR_LE,
                WOperatorType.OPERATOR_EQ,
                WOperatorType.OPERATOR_NE,
                WOperatorType.OPERATOR_BETWEEN,
                WOperatorType.OPERATOR_NOT_BETWEEN
            ]
        self._initOperator(self._defaultOperatorList)
        self.setOperator(WOperatorType.OPERATOR_GT)

        # keep a pointer to original contextMenuEvent method
        self._input1._contextMenuEvent=self._input1.contextMenuEvent
        self._input2._contextMenuEvent=self._input1.contextMenuEvent

        # define dedicated contextMenuEvent method to manage suffix
        self._input1.contextMenuEvent=self.__contextMenuEvent1
        self._input2.contextMenuEvent=self.__contextMenuEvent2

        self._input1.setAlignment(Qt.AlignRight)
        self._input2.setAlignment(Qt.AlignRight)

        self._input1.valueChanged.connect(self.__input1Changed)
        self._input2.valueChanged.connect(self.__input2Changed)

    def __input1Changed(self, value):
        """Value for input1 has changed"""
        self.valueChanged.emit(value)
        if self._input1.value()>self._input2.value():
            self._input2.setValue(self._input1.value())

    def __input2Changed(self, value):
        """Value for input2 has changed"""
        self.value2Changed.emit(value)
        if self._input1.value()>self._input2.value():
            self._input1.setValue(self._input2.value())

    def __contextMenuEvent1(self, event):
        """Manage context menu event for input 1"""
        self.__contextMenuEvent(self._input1, event)

    def __contextMenuEvent2(self, event):
        """Manage context menu event for input 2"""
        self.__contextMenuEvent(self._input2, event)

    def __contextMenuEvent(self, input, event):
        """Display context menu for given input

        If suffix list is not empty, add action to select a suffix
        """
        def executeAction(action):
            if action.data():
                self.setSuffix(action.data())

        if len(self._suffixList)==0:
            input._contextMenuEvent(event)
            return

        group=QActionGroup(self)
        group.setExclusive(True)
        subMenu=QMenu(self._suffixLabel)
        for suffix in self._suffixList:
            action=None
            if isinstance(suffix, str):
                action=QAction(suffix)
                action.setData(suffix)
                action.setCheckable(True)
            elif isinstance(suffix, (tuple, list)) and len(suffix)==2:
                action=QAction(suffix[0])
                action.setData(suffix[1])
                action.setCheckable(True)

            if action:
                group.addAction(action)
                subMenu.addAction(action)

                if self._input1.suffix()==action.data():
                    action.setChecked(True)

        actionStepUp=QAction(i18n('Step up'))
        actionStepUp.triggered.connect(input.stepUp)
        actionStepDown=QAction(i18n('Step down'))
        actionStepDown.triggered.connect(input.stepDown)

        menu=input.lineEdit().createStandardContextMenu()
        fAction=menu.actions()[0]
        menu.insertMenu(fAction, subMenu)
        menu.insertSeparator(fAction)
        menu.addSeparator()
        menu.addAction(actionStepUp)
        menu.addAction(actionStepDown)
        menu.triggered.connect(executeAction)
        menu.exec(event.globalPos())


    def value(self):
        """Return current value"""
        return self._input1.value()

    def setValue(self, value):
        """set current value"""
        if value!=self._input1.value():
            self._input1.setValue(value)

    def value2(self):
        """Return current 2nd value (when 'between' operator)"""
        return self._input2.value()

    def setValue2(self, value):
        """Set current 2nd value (when 'between' operator)"""
        if value!=self._input2.value():
            self._input2.setValue(value)

    def minimum(self):
        """Return minimum value"""
        return self._input1.minimum()

    def setMinimum(self, value):
        """Set minimum value"""
        self._input1.setMinimum(value)
        self._input2.setMinimum(value)

    def maximum(self):
        """Return minimum value"""
        return self._input1.maximum()

    def setMaximum(self, value):
        """Set minimum value"""
        self._input1.setMaximum(value)
        self._input2.setMaximum(value)

    def suffix(self):
        """Return current suffix"""
        return self._input1.suffix()

    def setSuffix(self, value):
        """Return current suffix"""
        self._input1.setSuffix(value)
        self._input2.setSuffix(value)
        self.suffixChanged.emit(value)

    def suffixList(self):
        """Return suffix list"""
        return self._suffixList

    def setSuffixList(self, values):
        """Set suffix list"""
        self._suffixList=values

    def suffixLabel(self):
        """Return suffix label"""
        return self._suffixLabel

    def setSuffixLabel(self, value):
        """Set suffix label"""
        if isinstance(value, str):
            self._suffixLabel=value


class WOperatorInputInt(WOperatorBaseInputNumber):
    """Search operator for Integer"""

    def _initializeUi(self):
        """Initialise widget

        - Operator list
        - Input widgets
        """
        self._input1=QSpinBox()
        self._input2=QSpinBox()
        super(WOperatorInputInt, self)._initializeUi()


class WOperatorInputFloat(WOperatorBaseInputNumber):
    """Search operator for Float"""

    def _initializeUi(self):
        """Initialise widget

        - Operator list
        - Input widgets
        """
        self._input1=QDoubleSpinBox()
        self._input2=QDoubleSpinBox()
        super(WOperatorInputFloat, self)._initializeUi()

    def decimals(self):
        """Return current number of decimals"""
        return self._input1.decimals()

    def setDecimals(self, value):
        """Return current number of decimals"""
        self._input1.setDecimals(value)
        self._input2.setDecimals(value)


class WOperatorInputDateTime(WOperatorBaseInput):
    """Search operator for DateTime"""

    def _initializeUi(self):
        """Initialise widget

        - Operator list
        - Input widgets
        """
        self._defaultOperatorList=[
                WOperatorType.OPERATOR_GT,
                WOperatorType.OPERATOR_GE,
                WOperatorType.OPERATOR_LT,
                WOperatorType.OPERATOR_LE,
                WOperatorType.OPERATOR_EQ,
                WOperatorType.OPERATOR_NE,
                WOperatorType.OPERATOR_BETWEEN,
                WOperatorType.OPERATOR_NOT_BETWEEN
            ]
        self._initOperator(self._defaultOperatorList)
        self.setOperator(WOperatorType.OPERATOR_GT)

        self._input1=QDateTimeEdit()
        self._input2=QDateTimeEdit()

        self._input1.setCalendarPopup(True)
        self._input2.setCalendarPopup(True)

        self._input1.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._input2.setDisplayFormat("yyyy-MM-dd HH:mm:ss")

        self._input1.dateTimeChanged.connect(self.__input1Changed)
        self._input2.dateTimeChanged.connect(self.__input2Changed)

    def __input1Changed(self, value):
        """Value for input1 has changed"""
        self.valueChanged.emit(value.toMSecsSinceEpoch())
        if self._input1.dateTime()>self._input2.dateTime():
            self._input2.setDateTime(self._input1.dateTime())

    def __input2Changed(self, value):
        """Value for input2 has changed"""
        self.value2Changed.emit(value.toMSecsSinceEpoch())
        if self._input1.dateTime()>self._input2.dateTime():
            self._input1.setDateTime(self._input2.dateTime())

    def value(self):
        """Return current value (as timestamp)"""
        return self._input1.dateTime().toMSecsSinceEpoch()/1000

    def setValue(self, value):
        """set current value

        Can be a time stamp or QDateTime
        """
        if isinstance(value, (int, float)):
            value=QDateTime.fromMSecsSinceEpoch(value*1000)

        if isinstance(value, QDateTime) and value!=self._input1.dateTime():
            self._input1.setDateTime(value)

    def value2(self):
        """Return current 2nd value (as timestamp) - (when 'between' operator)"""
        return self._input2.dateTime().toMSecsSinceEpoch()/1000

    def setValue2(self, value):
        """Set current 2nd value (when 'between' operator)"""
        if isinstance(value, (int, float)):
            value=QDateTime.fromMSecsSinceEpoch(value*1000)

        if isinstance(value, QDateTime) and value!=self._input2.dateTime():
            self._input2.setDateTime(value)

    def minimum(self):
        """Return minimum value  (as timestamp)"""
        return self._input1.minimumDateTime().toMSecsSinceEpoch()/1000

    def setMinimum(self, value):
        """Set minimum value"""
        if isinstance(value, (int, float)):
            value=QDateTime.fromMSecsSinceEpoch(value*1000)

        if isinstance(value, QDateTime):
            self._input1.setMinimumDateTime(value)
            self._input2.setMinimumDateTime(value)

    def maximum(self):
        """Return minimum value  (as timestamp)"""
        return self._input1.maximumDateTime().toMSecsSinceEpoch()/1000

    def setMaximum(self, value):
        """Set minimum value"""
        if isinstance(value, (int, float)):
            value=QDateTime.fromMSecsSinceEpoch(value*1000)

        if isinstance(value, QDateTime):
            self._input1.setMaximumDateTime(value)
            self._input2.setMaximumDateTime(value)


class WOperatorInputDate(WOperatorBaseInput):
    """Search operator for DateTime"""

    def _initializeUi(self):
        """Initialise widget

        - Operator list
        - Input widgets
        """
        self._defaultOperatorList=[
                WOperatorType.OPERATOR_GT,
                WOperatorType.OPERATOR_GE,
                WOperatorType.OPERATOR_LT,
                WOperatorType.OPERATOR_LE,
                WOperatorType.OPERATOR_EQ,
                WOperatorType.OPERATOR_NE,
                WOperatorType.OPERATOR_BETWEEN,
                WOperatorType.OPERATOR_NOT_BETWEEN
            ]
        self._initOperator(self._defaultOperatorList)
        self.setOperator(WOperatorType.OPERATOR_GT)

        self._input1=QDateEdit()
        self._input2=QDateEdit()

        self._input1.setCalendarPopup(True)
        self._input2.setCalendarPopup(True)

        self._input1.setDisplayFormat("yyyy-MM-dd")
        self._input2.setDisplayFormat("yyyy-MM-dd")

        self._input1.userDateChanged.connect(self.__input1Changed)
        self._input2.userDateChanged.connect(self.__input2Changed)

    def __input1Changed(self, value):
        """Value for input1 has changed"""
        self.valueChanged.emit(QDateTime(value).toMSecsSinceEpoch())
        if self._input1.date()>self._input2.date():
            self._input2.setDate(self._input1.date())

    def __input2Changed(self, value):
        """Value for input2 has changed"""
        self.value2Changed.emit(QDateTime(value).toMSecsSinceEpoch())
        if self._input1.date()>self._input2.date():
            self._input1.setDate(self._input2.date())

    def value(self):
        """Return current value (as timestamp)"""
        return QDateTime(self._input1.date()).toMSecsSinceEpoch()/1000

    def setValue(self, value):
        """set current value

        Can be a time stamp or QDateTime
        """
        if isinstance(value, (int, float)):
            value=QDateTime.fromMSecsSinceEpoch(value*1000).date()

        if isinstance(value, QDate) and value!=self._input1.date():
            self._input1.setDate(value)

    def value2(self):
        """Return current 2nd value (as timestamp) - (when 'between' operator)"""
        return QDateTime(self._input2.date()).toMSecsSinceEpoch()/1000

    def setValue2(self, value):
        """Set current 2nd value (when 'between' operator)"""
        if isinstance(value, (int, float)):
            value=QDateTime.fromMSecsSinceEpoch(value*1000).date()

        if isinstance(value, QDate) and value!=self._input2.date():
            self._input2.setDate(value)

    def minimum(self):
        """Return minimum value  (as timestamp)"""
        return QDateTime(self._input1.minimumDate()).toMSecsSinceEpoch()/1000

    def setMinimum(self, value):
        """Set minimum value"""
        if isinstance(value, (int, float)):
            value=QDateTime.fromMSecsSinceEpoch(value*1000).date()

        if isinstance(value, QDate):
            self._input1.setMinimumDate(value)
            self._input2.setMinimumDate(value)

    def maximum(self):
        """Return minimum value  (as timestamp)"""
        return QDateTime(self._input1.maximumDate()).toMSecsSinceEpoch()/1000

    def setMaximum(self, value):
        """Set minimum value"""
        if isinstance(value, (int, float)):
            value=QDateTime.fromMSecsSinceEpoch(value*1000).date()

        if isinstance(value, QDate):
            self._input1.setMaximumDate(value)
            self._input2.setMaximumDate(value)


class WOperatorInputTime(WOperatorBaseInput):
    """Search operator for DateTime"""

    def _initializeUi(self):
        """Initialise widget

        - Operator list
        - Input widgets
        """
        self._defaultOperatorList=[
                WOperatorType.OPERATOR_GT,
                WOperatorType.OPERATOR_GE,
                WOperatorType.OPERATOR_LT,
                WOperatorType.OPERATOR_LE,
                WOperatorType.OPERATOR_EQ,
                WOperatorType.OPERATOR_NE,
                WOperatorType.OPERATOR_BETWEEN,
                WOperatorType.OPERATOR_NOT_BETWEEN
            ]
        self._initOperator(self._defaultOperatorList)
        self.setOperator(WOperatorType.OPERATOR_GT)

        self._input1=QTimeEdit()
        self._input2=QTimeEdit()

        self._input1.setDisplayFormat("HH:mm:ss")
        self._input2.setDisplayFormat("HH:mm:ss")

        self._input1.userTimeChanged.connect(self.__input1Changed)
        self._input2.userTimeChanged.connect(self.__input2Changed)

    def __input1Changed(self, value):
        """Value for input1 has changed"""
        self.valueChanged.emit(value.msecsSinceStartOfDay())
        if self._input1.time()>self._input2.time():
            self._input2.setTime(self._input1.time())

    def __input2Changed(self, value):
        """Value for input2 has changed"""
        self.value2Changed.emit(value.msecsSinceStartOfDay())
        if self._input1.time()>self._input2.time():
            self._input1.setTime(self._input2.time())

    def value(self):
        """Return current value (as number of seconds since start of day)"""
        return self._input1.time().msecsSinceStartOfDay()

    def setValue(self, value):
        """set current value

        Can be a time stamp or QDateTime
        """
        if isinstance(value, (int, float)):
            value=QTime.fromMSecsSinceStartOfDay(value)

        if isinstance(value, QTime) and value!=self._input1.time():
            self._input1.setTime(value)

    def value2(self):
        """Return current 2nd value (as timestamp) - (when 'between' operator)"""
        return self._input2.time().msecsSinceStartOfDay()

    def setValue2(self, value):
        """Set current 2nd value (when 'between' operator)"""
        if isinstance(value, (int, float)):
            value=QTime.fromMSecsSinceStartOfDay(value)

        if isinstance(value, QTime) and value!=self._input2.time():
            self._input2.setTime(value)

    def minimum(self):
        """Return minimum value  (as timestamp)"""
        return self._input1.minimumTime().msecsSinceStartOfDay()

    def setMinimum(self, value):
        """Set minimum value"""
        if isinstance(value, (int, float)):
            value=QTime.fromMSecsSinceStartOfDay(value)

        if isinstance(value, QDate):
            self._input1.setMinimumTime(value)
            self._input2.setMinimumTime(value)

    def maximum(self):
        """Return minimum value  (as timestamp)"""
        return self._input1.maximumTime().msecsSinceStartOfDay()

    def setMaximum(self, value):
        """Set minimum value"""
        if isinstance(value, (int, float)):
            value=QTime.fromMSecsSinceStartOfDay(value)

        if isinstance(value, QDate):
            self._input1.setMaximumTime(value)
            self._input2.setMaximumTime(value)


class WOperatorInputStr(WOperatorBaseInput):
    """Search operator for DateTime"""

    def _initializeUi(self):
        """Initialise widget

        - Operator list
        - Input widgets
        """
        self._defaultOperatorList=[
                WOperatorType.OPERATOR_EQ,
                WOperatorType.OPERATOR_NE,
                WOperatorType.OPERATOR_MATCH,
                WOperatorType.OPERATOR_NOT_MATCH,
                WOperatorType.OPERATOR_LIKE,
                WOperatorType.OPERATOR_NOT_LIKE
            ]
        self._initOperator(self._defaultOperatorList)
        self.setOperator(WOperatorType.OPERATOR_EQ)

        self._input1=QLineEdit()

        self._input1.textChanged.connect(lambda v: self.valueChanged.emit(v))

    def value(self):
        """Return current value"""
        return self._input1.text()

    def setValue(self, value):
        """set current value"""
        if value!=self._input1.text():
            self._input1.setText(value)
