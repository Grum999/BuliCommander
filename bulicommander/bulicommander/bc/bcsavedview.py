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
# The bcsavedview module provides classes used to manage saved views
#
# Main classes from this module
#
# - BCSavedViewEdit:
#       A basic user interface to manage views
#
# - BCSavedView:
#       Allows to easily manage views
#
# -----------------------------------------------------------------------------

import os
import re
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
from bulicommander.pktk.pktk import EInvalidType


class BCSavedViewEdit(QDialog):
    """A simple interface to edit a saved view"""

    CREATE = 0
    DELETE = 1
    RENAME = 2
    CLEAR_CONTENT = 3
    REMOVE_CONTENT = 4

    def __init__(self, mode, savedView, key='', value=[], refList=None, parent=None):
        super(BCSavedViewEdit, self).__init__(parent)

        if mode not in [BCSavedViewEdit.CREATE,
                        BCSavedViewEdit.DELETE,
                        BCSavedViewEdit.RENAME,
                        BCSavedViewEdit.CLEAR_CONTENT,
                        BCSavedViewEdit.REMOVE_CONTENT]:
            raise EInvalidValue('Given `mode` is not valid')

        if not isinstance(savedView, BCSavedView):
            raise EInvalidType('Given `savedView` must be a <BCSavedView>')
        if not isinstance(key, str):
            raise EInvalidType('Given `key` must be a <str>')
        if not isinstance(value, list):
            raise EInvalidType('Given `value` must be a <list>')

        key = key.lstrip('@').lower()
        name = savedView.name(key)

        self.__savedView = savedView
        self.__mode = mode

        self.__refList = []

        if isinstance(refList, list):
            self.__refList = [v.lstrip('@').lower() for v in refList]
        elif isinstance(refList, dict):
            # in this case, key = id
            self.__refList = [key.lstrip('@').lower() for key in refList]

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcsavedview_edit.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.pteFiles.setPlainText("\n".join(value))
        self.ledName.setText(name)
        if len(value) == 0:
            self.lblNbFiles.setText('No files in view')
        else:
            self.lblNbFiles.setText(f'Files: {len(value)}')

        if mode == BCSavedViewEdit.CREATE:
            self.setWindowTitle('Create new view')
        elif mode == BCSavedViewEdit.DELETE:
            self.setWindowTitle('Delete view')
            self.ledName.setEnabled(False)
        elif mode == BCSavedViewEdit.RENAME:
            self.setWindowTitle('Rename view')
        elif mode == BCSavedViewEdit.CLEAR_CONTENT:
            self.setWindowTitle('Clear view content')
            self.ledName.setEnabled(False)
        elif mode == BCSavedViewEdit.REMOVE_CONTENT:
            self.setWindowTitle('Remove files from view content')
            self.ledName.setEnabled(False)

        self.ledName.textEdited.connect(self.__checkButton)
        self.lblMsg.setText('')
        self.lblMsg.setVisible(False)

        self.__checkButton()

    def __checkButton(self):
        enabled = True
        if self.ledName.isEnabled():
            viewName = self.ledName.text().strip()

            if viewName == '':
                enabled = False
                self.lblMsg.setText(i18n('A view name is mandatory'))
            elif not self.__savedView.get(viewName) is None or viewName.lower() in self.__refList:
                enabled = False
                self.lblMsg.setText(i18n('Given name is already used'))

        if enabled:
            self.lblMsg.setText('')
            self.lblMsg.setVisible(False)
        else:
            self.lblMsg.setVisible(True)

        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(enabled)

    @staticmethod
    def clearContent(savedView, name):
        """Open editor to clear a view content

        If name doesn't exist, do nothing

        If view content is cleared, return a tuple (True, name)
        Otherwise return tuple (False, name)
        """
        if not isinstance(savedView, BCSavedView):
            raise Exception('Given `savedView` must be a <BCSavedView>')
        if not isinstance(name, str):
            raise Exception('Given `name` must be a <str>')

        value = savedView.get(name)
        if value is None:
            return (False, name)

        dlg = BCSavedViewEdit(BCSavedViewEdit.CLEAR_CONTENT, savedView, key=name, value=value)
        returned = dlg.exec_()

        if returned and savedView.viewClear(name):
            return (True, name)
        else:
            return (False, name)

    @staticmethod
    def removeContent(savedView, name, files):
        """Open editor to clear a view content

        If name doesn't exist, do nothing

        If view content is cleared, return a tuple (True, name)
        Otherwise return tuple (False, name)
        """
        if not isinstance(savedView, BCSavedView):
            raise Exception('Given `savedView` must be a <BCSavedView>')
        if not isinstance(name, str):
            raise Exception('Given `name` must be a <str>')

        value = files
        if value is None:
            return (False, name)

        dlg = BCSavedViewEdit(BCSavedViewEdit.REMOVE_CONTENT, savedView, key=name, value=value)
        returned = dlg.exec_()

        if returned and savedView.viewRemove(name, value):
            return (True, name)
        else:
            return (False, name)

    @staticmethod
    def create(savedView, value, refList=None):
        """Open editor to create a view

        Return tuple (True, <str>) if OK
        otherwise (False, None) if not created
        """
        if not isinstance(savedView, BCSavedView):
            raise Exception('Given `savedView` must be a <BCSavedView>')
        if not isinstance(value, list):
            raise Exception('Given `value` must be a <list>')

        dlg = BCSavedViewEdit(BCSavedViewEdit.CREATE, savedView, value=value, refList=refList)
        returned = dlg.exec_()

        if returned and savedView.create(dlg.ledName.text(), value):
            return (True, dlg.ledName.text())
        else:
            return (False, None)

    @staticmethod
    def delete(savedView, name):
        """Open editor to remove a view

        If name doesn't exist, do nothing

        If name is removed from views, return a tuple (True, name)
        Otherwise return tuple (False, None)
        """
        if not isinstance(savedView, BCSavedView):
            raise Exception('Given `savedView` must be a <BCSavedView>')
        if not isinstance(name, str):
            raise Exception('Given `name` must be a <str>')

        value = savedView.get(name)
        if value is None:
            return (False, None)

        dlg = BCSavedViewEdit(BCSavedViewEdit.DELETE, savedView, key=name, value=value)
        returned = dlg.exec_()

        if returned and savedView.delete(name):
            return (True, name)
        else:
            return (False, None)

    @staticmethod
    def rename(savedView, name, refList=None):
        """Open editor to rename a view

        If value is renamed, return a tuple (True, name)
        Otherwise return tuple (False, None)
        """
        if not isinstance(savedView, BCSavedView):
            raise Exception('Given `savedView` must be a <BCSavedView>')
        if not isinstance(name, str):
            raise Exception('Given `name` must be a <str>')

        value = savedView.get(name)
        if value is None:
            return (False, None)

        dlg = BCSavedViewEdit(BCSavedViewEdit.RENAME, savedView, key=name, value=value, refList=refList)
        returned = dlg.exec_()

        if returned and savedView.rename(name, dlg.ledName.text().strip()):
            return (True, dlg.ledName.text().strip())
        else:
            return (False, None)


class BCSavedView(QObject):
    """A BCSavedView provide a simple way to manage view

    When a new view is added, ensure that view name doesn't already exists

    it also provides a simple view user interface for managing view
    """

    updated = Signal(str)
    created = Signal(str)
    deleted = Signal(str)
    renamed = Signal(str, str)

    def __init__(self, items={}):
        super(BCSavedView, self).__init__(None)
        self.__savedView = {}
        self.__emit = True
        self.__current = None
        self.set(items)

    def __toKey(self, name):
        """Convert given name to a key"""
        if isinstance(name, str):
            return name.lstrip('@').lower()
        return None

    def clear(self):
        """Clear all views"""
        self.__savedView = {}

    def set(self, values):
        """Set views

        values is a dictionary
        key = <str>                 [name]
        value = <list<str>>         [list of filename]
        """
        if not isinstance(values, dict):
            raise EInvalidType("Given `values` must be a <dict>")

        if len(values) > 0:
            nbCreated = 0
            self.__emit = False
            for name in values:
                if self.create(name, values[name]):
                    nbCreated += 1

            self.__emit = True
            if nbCreated:
                self.created.emit('')

    def get(self, name=None):
        """return view content for given name

        Return None if there's no view for given name

        If no name is given, return content of  current view
        """
        if name is None:
            name = self.__current

        key = self.__toKey(name)

        if key in self.__savedView:
            return self.__savedView[key]['value']

        return None

    def name(self, id=None):
        """return view name for given id

        Return None if there's no view for given id

        If no id is given, return name of current view
        """
        if id is None:
            id = self.__current

        key = self.__toKey(id)

        if key in self.__savedView:
            return self.__savedView[key]['name']

        return None

    def viewClear(self, name):
        """Clear view content

        If there's no view for given name, does nothing
        """
        if name is None:
            return None

        key = self.__toKey(name)

        if key in self.__savedView:
            self.__savedView[key] = {'name':    name,
                                     'value':   []
                                     }
            if self.__emit:
                self.updated.emit(name)

    def viewAppend(self, name, values):
        """Append values to view

        If there's no view for given name, does nothing

        Given values are list of filename (str)
        If a value already exists, value is not added
        """
        returned = 0
        if name is None:
            return returned

        key = self.__toKey(name)

        if key in self.__savedView:
            for value in values:
                if value not in self.__savedView[key]['value']:
                    self.__savedView[key]['value'].append(value)
                    returned += 1

            if returned > 0 and self.__emit:
                self.updated.emit(name)

        return returned

    def viewRemove(self, name, values):
        """Remove values to view

        If there's no view for given name, does nothing

        Given values are list of filename (str)
        If a value doesn't exists, value is ignored
        """
        returned = 0
        if name is None:
            return returned

        key = self.__toKey(name)

        if key in self.__savedView:
            for value in values:
                if value in self.__savedView[key]['value']:
                    self.__savedView[key]['value'].remove(value)
                    returned += 1

            if returned > 0 and self.__emit:
                self.updated.emit(name)

        return returned

    def create(self, name, value, refList=None):
        """Create a value to bookmark

        Return True if created, otherwise False

        if a view already exists for given name, do nothing
        """
        if not isinstance(name, str):
            raise EInvalidType("Given `name` must be a <str>")
        if not isinstance(value, list):
            raise EInvalidType("Given `value` must be a <list>")

        additionalList = []
        if isinstance(refList, list) or isinstance(refList, dict):
            additionalList = [self.__toKey(name) for name in refList]

        key = self.__toKey(name)

        if key in self.__savedView or key in additionalList:
            # view already exist for given name
            return False

        self.__savedView[key] = {'name': name,
                                 'value': value
                                 }
        if self.__emit:
            self.created.emit(name)

        return True

    def delete(self, name):
        """Delete view for given name

        if not view exists for given name, do nothing

        if removed, return True
        otherwise return False
        """
        if not isinstance(name, str):
            raise EInvalidType("Given `name` must be a string")

        key = self.__toKey(name)

        if key not in self.__savedView:
            # view doesn't exist for given name
            return False

        self.__savedView.pop(key)
        if self.__emit:
            self.deleted.emit(name)

        return True

    def rename(self, name, newName, refList=None):
        """Rename view for given name to newName

        if no view exist for given name, does nothing
        if newName already exist, do nothing

        if renamed, return True
        otherwise return False
        """
        if not isinstance(name, str):
            raise EInvalidType("Given `name` must be a string")
        if not isinstance(newName, str):
            raise EInvalidType("Given `newName` must be a string")

        additionalList = []
        if isinstance(refList, list) or isinstance(refList, dict):
            additionalList = [self.__toKey(name) for name in refList]

        key = self.__toKey(name)
        newKey = self.__toKey(newName)

        if key not in self.__savedView or newKey in self.__savedView or newKey in additionalList:
            # view already exist for given name
            return False

        self.__savedView[newKey] = self.__savedView.pop(key)
        self.__savedView[newKey]['name'] = newName
        if self.__emit:
            self.renamed.emit(name, newName)

        return True

    def length(self):
        """Return number of views"""
        return len(self.__savedView)

    def list(self):
        """Return views as a list, sorted by names

        list items are list [name, files]
        """
        returned = []
        for key in sorted(self.__savedView):
            returned.append([self.__savedView[key]['name'], self.__savedView[key]['value']])

        return returned

    def uiCreate(self, value, refList=None):
        """Open editor to create a view"""
        return BCSavedViewEdit.create(self, value, refList)

    def uiDelete(self, name):
        """Open editor to delete a view"""
        return BCSavedViewEdit.delete(self, name)

    def uiRename(self, name, refList=None):
        """Open editor to rename a view"""
        return BCSavedViewEdit.rename(self, name, refList)

    def uiClearContent(self, name):
        """Open editor to clear view content"""
        return BCSavedViewEdit.clearContent(self, name)

    def uiRemoveContent(self, name, value):
        """Open editor to remove content from view"""
        return BCSavedViewEdit.removeContent(self, name, value)

    def current(self, asLabel=False):
        """Return current active view

        If none is active, return None
        """
        if asLabel and self.__current:
            return self.__savedView[self.__current]['name']
        return self.__current

    def setCurrent(self, viewName):
        """set current active view

        If view doesn't exist, set None as current

        return True if current view has been set, otherwise False
        """
        key = self.__toKey(viewName)

        if key not in self.__savedView:
            self.__current = None
            return False

        self.__current = key
        return True

    def inList(self, viewName):
        """Return True if view exist, otherwise False"""
        key = self.__toKey(viewName)

        return (key in self.__savedView)
