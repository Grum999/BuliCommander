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

import os
import sys

import PyQt5.uic
from PyQt5.Qt import *
from PyQt5.QtWidgets import (
        QDialog,
        QMainWindow
    )
from PyQt5.QtCore import (
        pyqtSignal as Signal,
        QObject
    )


class BCBookmarkEdit(QDialog):
    """A simple interface to edit a bookmark"""

    APPEND = 0
    REMOVE = 1
    UPDATE = 2
    RENAME = 3

    def __init__(self, mode, bookmark, name='', value='', valueName='path', parent=None):
        super(BCBookmarkEdit, self).__init__(parent)

        if not mode in [BCBookmarkEdit.APPEND,
                        BCBookmarkEdit.REMOVE,
                        BCBookmarkEdit.UPDATE,
                        BCBookmarkEdit.RENAME]:
            raise EInvalidValue('Given `mode` is not valid')

        if not isinstance(bookmark, BCBookmark):
            raise EInvalidType('Given `bookmark` must be a <BCBookmark>')
        if not isinstance(name, str):
            raise EInvalidType('Given `name` must be a <str>')
        if not isinstance(value, str):
            raise EInvalidType('Given `value` must be a <str>')

        self.__bookmark = bookmark
        self.__mode = mode
        self.__valueName = valueName

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcbookmark_edit.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.lblValue.setText(valueName)
        self.ledValue.setText(value)
        self.ledName.setText(name)

        if mode == BCBookmarkEdit.APPEND:
            self.setWindowTitle('Add bookmark')
            self.ledValue.setEnabled(False)
        elif mode == BCBookmarkEdit.REMOVE:
            self.setWindowTitle('Remove bookmark')
            self.ledName.setEnabled(False)
            self.ledValue.setEnabled(False)
        elif mode == BCBookmarkEdit.UPDATE:
            self.setWindowTitle('Update bookmark')
            self.ledName.setEnabled(False)
        elif mode == BCBookmarkEdit.RENAME:
            self.setWindowTitle('Rename bookmark')
            self.ledValue.setEnabled(False)

        self.ledName.textEdited.connect(self.__checkButton)
        self.ledValue.textEdited.connect(self.__checkButton)
        self.lblMsg.setText('')

    def __checkButton(self):
        enabled = True
        if self.ledName.isEnabled():
            if self.ledName.text() == '':
                enabled = False
                self.lblMsg.setText(i18n('A bookmark name is mandatory'))
            elif not self.__bookmark.valueFromName(self.ledName.text()) is None:
                enabled = False
                self.lblMsg.setText(i18n('A bookmark already exists for given name'))
        elif self.ledValue.isEnabled():
            if self.ledValue.text() == '':
                enabled = False
                self.lblMsg.setText(i18n(f'A bookmark {self.__valueName} is mandatory'))
            elif not self.__bookmark.nameFromValue(self.ledValue.text()) is None:
                enabled = False
                self.lblMsg.setText(i18n(f'A bookmark already exists for given {self.__valueName}'))

        if enabled:
            self.lblMsg.setText('')

        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(enabled)

    @staticmethod
    def append(bookmark, value):
        """Open editor to append a bookmark

        If value already exist, do nothing

        If value is added to bookmark, return a tuple (True, name, value)
        Otherwise return tuple (False, None, None)
        """
        if not isinstance(bookmark, BCBookmark):
            raise Exception('Given `bookmark` must be a <BCBookmark>')
        if not isinstance(value, str):
            raise Exception('Given `value` must be a <str>')

        if not bookmark.nameFromValue(value) is None:
            return (False, None, None)

        dlg = BCBookmarkEdit(BCBookmarkEdit.APPEND, bookmark, value=value)
        returned = dlg.exec_()

        if returned and bookmark.append(dlg.ledName.text(), dlg.ledValue.text()):
            return (True, dlg.ledName.text(), dlg.ledValue.text())
        else:
            return (False, None, None)

    @staticmethod
    def remove(bookmark, name):
        """Open editor to remove a bookmark

        If name doesn't exist, do nothing

        If name is removed from bookmark, return a tuple (True, name, value)
        Otherwise return tuple (False, None, None)
        """
        if not isinstance(bookmark, BCBookmark):
            raise Exception('Given `bookmark` must be a <BCBookmark>')
        if not isinstance(name, str):
            raise Exception('Given `name` must be a <str>')

        value = bookmark.valueFromName(name)
        if value is None:
            return (False, None, None)

        dlg = BCBookmarkEdit(BCBookmarkEdit.REMOVE, bookmark, name=name, value=value)
        returned = dlg.exec_()

        if returned and bookmark.remove(dlg.ledName.text()):
            return (True, dlg.ledName.text(), dlg.ledValue.text())
        else:
            return (False, None, None)

    @staticmethod
    def update(bookmark, name, newValue=None):
        """Open editor to update a bookmark

        If name doesn't exist, do nothing
        If newValue is provided, pre-fill new value, otherwise use current bookmark value

        If value is updated, return a tuple (True, name, value)
        Otherwise return tuple (False, None, None)
        """
        if not isinstance(bookmark, BCBookmark):
            raise Exception('Given `bookmark` must be a <BCBookmark>')
        if not isinstance(value, str):
            raise Exception('Given `name` must be a <str>')
        if not (newValue is None or isinstance(newValue, str)):
            raise Exception('Given `newValue` must be a <str>')

        value = bookmark.valueFromName(name)
        if value is None:
            return (False, None, None)
        if not newValue is None:
            value = newValue

        dlg = BCBookmarkEdit(BCBookmarkEdit.UPDATE, bookmark, name=name, value=value)
        returned = dlg.exec_()

        if returned and bookmark.update(dlg.ledName.text(), dlg.ledValue.text()):
            return (True, dlg.ledName.text(), dlg.ledValue.text())
        else:
            return (False, None, None)

    @staticmethod
    def rename(bookmark, name):
        """Open editor to rename a bookmark

        If name doesn't exist, do nothing

        If value is renamed, return a tuple (True, name, value)
        Otherwise return tuple (False, None, None)
        """
        if not isinstance(bookmark, BCBookmark):
            raise Exception('Given `bookmark` must be a <BCBookmark>')
        if not isinstance(name, str):
            raise Exception('Given `name` must be a <str>')

        value = bookmark.valueFromName(name)
        if value is None:
            return (False, None, None)

        dlg = BCBookmarkEdit(BCBookmarkEdit.RENAME, bookmark, name=name, value=value)
        returned = dlg.exec_()

        if returned and bookmark.rename(name, dlg.ledName.text()):
            return (True, dlg.ledName.text(), dlg.ledValue.text())
        else:
            return (False, None, None)


class BCBookmark(QObject):
    """A BCBookmark provide a simple way to manage bookmark

    When a new item is added, bookmark ensure:
    - that bookmark name doesn't already exists
    - that bookmark value doesn't already exists

    it also provides a simple bookmark user interface for managing bookmarks
    """

    changed = Signal()

    NAME = 0
    VALUE = 1

    def __init__(self, items=[]):
        super(BCBookmark, self).__init__(None)
        self.__bookmark={}
        self.set(items)

    def set(self, values):
        """Set bookmark

        Note: bookmark is not cleared before action
        """
        if not isinstance(values, list):
            raise EInvalidType("Given `values` must be a list")

        if len(values) > 0:
            for value in values:
                if not isinstance(value, list) or len(value)!=2:
                    raise EInvalidType("Given `value` must be a list[name, path]")
                self.append(value[BCBookmark.NAME], value[BCBookmark.VALUE])

            self.changed.emit()


    def clear(self):
        """Clear bookmark content"""
        self.__bookmark.clear()
        self.changed.emit()

    def nameFromValue(self, value):
        """return bookmark name for given value

        Return None is not found
        """
        if value is None:
            return None

        for name in self.__bookmark:
            if self.__bookmark[name] == value:
                return name
        return None

    def valueFromName(self, name):
        """return bookmark value for given name

        Return None is not found
        """
        if name is None:
            return None

        if name in self.__bookmark:
            return self.__bookmark[name]

        return None

    def append(self, name, value):
        """Add a value to bookmark

        Return True if added, otherwise False

        if a bookmark already exists for given name, do nothing
        if a bookmark already exists for given value, do nothing
        """
        if not isinstance(name, str):
            raise EInvalidType("Given `name` must be a string")
        if not isinstance(value, str):
            raise EInvalidType("Given `value` must be a string")

        if not self.valueFromName(name) is None:
            # bookmark already exist for given name
            return False

        if not self.nameFromValue(value) is None:
            # bookmark already exist for given value
            return False

        self.__bookmark[name]=value
        self.changed.emit()

        return True

    def remove(self, name):
        """Remove bookmark with given name

        if removed, return True
        otherwise return False
        """
        if not isinstance(name, str):
            raise EInvalidType("Given `name` must be a string")

        if self.valueFromName(name) is None:
            # bookmark doesn't exist for given name
            return False

        self.__bookmark.pop(name)
        self.changed.emit()

        return True

    def rename(self, name, newName):
        """Rename bookmark for given name to newName

        if name not found, does nothing
        if newName already exist, do nothing

        if renamed, return True
        otherwise return False
        """
        if not isinstance(name, str):
            raise EInvalidType("Given `name` must be a string")
        if not isinstance(newName, str):
            raise EInvalidType("Given `newName` must be a string")

        if self.valueFromName(name) is None or not self.valueFromName(newName) is None :
            # bookmark doesn't exist for given name
            return False

        self.__bookmark[newName] = self.__bookmark.pop(name)
        self.changed.emit()

        return True

    def update(self, name, value):
        """update a value to bookmark

        Return True if updated, otherwise False

        if a bookmark does not exists for given name, do nothing
        if a bookmark already exists for given value, do nothing
        """
        if not isinstance(name, str):
            raise EInvalidType("Given `name` must be a string")
        if not isinstance(value, str):
            raise EInvalidType("Given `value` must be a string")

        if self.valueFromName(name) is None or not self.nameFromValue(value) is None:
            return False

        self.__bookmark[name]=value
        self.changed.emit()

        return True

    def length(self):
        """Return number of bookmarks"""
        return len(self.__bookmark)

    def list(self):
        """Return bookmarks as a list, sorted by names

        list items are list [name, value]
        """
        returned = []
        for name in sorted(self.__bookmark):
            returned.append([name, self.__bookmark[name]])

        return returned

    def uiAppend(self, value):
        """Open editor to add a bookmark"""
        return BCBookmarkEdit.append(self, value)

    def uiRemove(self, name):
        """Open editor to remove a bookmark"""
        return BCBookmarkEdit.remove(self, name)

    def uiRename(self, name):
        """Open editor to rename a bookmark"""
        return BCBookmarkEdit.rename(self, name)

    def uiUpdate(self, name, value):
        """Open editor to update a bookmark"""
        return BCBookmarkEdit.update(self, name, value)

