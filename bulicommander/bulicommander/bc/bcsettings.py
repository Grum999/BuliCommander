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

from enum import Enum


import PyQt5.uic
from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal,
        QSettings,
        QStandardPaths
    )
from PyQt5.QtWidgets import (
        QDialog,
        QMessageBox
    )

from os.path import join, getsize
import json
import os
import re
import sys
import shutil

from .bcfile import (
        BCFile
    )

from .bcpathbar import BCPathBar
from .bcutils import (
        bytesSizeToStr,
        Debug
    )

from ..pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# -----------------------------------------------------------------------------

class BCSettingsValues(object):
    FILE_DEFAULTACTION_OPEN =                               'open'
    FILE_DEFAULTACTION_OPEN_AND_CLOSE =                     'open and close'
    FILE_DEFAULTACTION_OPEN_AS_NEW =                        'open as new document'
    FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE =              'open as new document and close'

    FILE_UNIT_KB =                                          'auto'
    FILE_UNIT_KIB =                                         'autobin'

    HOME_DIR_SYS =                                          'system'
    HOME_DIR_UD =                                           'user defined'


class BCSettingsFmt(object):

    def __init__(self, settingType, values=None):
        if not isinstance(settingType, type):
            raise EInvalidType('Given `settingType` must be a type')

        self.__type = settingType
        self.__values = values

    def check(self, value, checkType=None):
        """Check if given value match setting format"""
        if checkType is None:
            checkType = self.__type

        if not isinstance(value, checkType):
            raise EInvalidType(f'Given `value` ({value}) is not from expected type ({checkType})')

        if not self.__values is None:
            if isinstance(value, list) or isinstance(value, tuple):
                # need to check all items
                if isinstance(self.__values, type):
                    # check if all items are of given type
                    for item in value:
                        self.check(item, self.__values)
                else:
                    # check items values
                    for item in value:
                        self.check(item)
            elif isinstance(self.__values, list) or isinstance(self.__values, tuple):
                if not value in self.__values:
                    raise EInvalidValue('Given `value` ({0}) is not in authorized perimeter ({1})'.format(value, self.__values))
            elif isinstance(self.__values, re.Pattern):
                if self.__values.match(value) is None:
                    raise EInvalidValue('Given `value` ({0}) is not in authorized perimeter'.format(value))


class BCSettingsKey(Enum):
    CONFIG_FILE_DEFAULTACTION_KRA =                          'config.file.defaultAction.kra'
    CONFIG_FILE_DEFAULTACTION_OTHER =                        'config.file.defaultAction.other'
    CONFIG_FILE_NEWFILENAME_KRA =                            'config.file.newFileName.kra'
    CONFIG_FILE_NEWFILENAME_OTHER =                          'config.file.newFileName.other'
    CONFIG_FILE_UNIT =                                       'config.file.unit'
    CONFIG_HOME_DIR_MODE =                                   'config.homeDir.mode'
    CONFIG_HOME_DIR_UD =                                     'config.homeDir.userDefined'
    CONFIG_HISTORY_MAXITEMS =                                'config.history.maximumItems'
    CONFIG_HISTORY_KEEPONEXIT =                              'config.history.keepOnExit'
    CONFIG_LASTDOC_MAXITEMS =                                'config.lastDocuments.maximumItems'
    CONFIG_NAVBAR_BUTTONS_HOME =                             'config.navbar.buttons.home'
    CONFIG_NAVBAR_BUTTONS_VIEWS =                            'config.navbar.buttons.views'
    CONFIG_NAVBAR_BUTTONS_BOOKMARKS =                        'config.navbar.buttons.bookmarks'
    CONFIG_NAVBAR_BUTTONS_HISTORY =                          'config.navbar.buttons.history'
    CONFIG_NAVBAR_BUTTONS_LASTDOCUMENTS =                    'config.navbar.buttons.lastDocuments'
    CONFIG_NAVBAR_BUTTONS_BACK =                             'config.navbar.buttons.back'
    CONFIG_NAVBAR_BUTTONS_UP =                               'config.navbar.buttons.up'
    CONFIG_NAVBAR_BUTTONS_QUICKFILTER =                      'config.navbar.buttons.quickFilter'
    CONFIG_SESSION_SAVE =                                    'config.session.save'
    CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY =          'config.defaultSession.panels.view.filesManagedOnly'
    CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP =               'config.defaultSession.panels.view.filesBackup'
    CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN =               'config.defaultSession.panels.view.filesHidden'
    CONFIG_DSESSION_PANELS_VIEW_LAYOUT =                     'config.defaultSession.panels.view.layout'
    CONFIG_DSESSION_PANELS_VIEW_THUMBNAIL =                  'config.defaultSession.panels.view.thumbnail'
    CONFIG_DSESSION_PANELS_VIEW_ICONSIZE =                   'config.defaultSession.panels.view.iconSize'
    CONFIG_DSESSION_PANELS_VIEW_NFOROW =                     'config.defaultSession.panels.view.rowInformation'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_BORDER =                'config.defaultSession.information.clipboard.border'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_HEADER =                'config.defaultSession.information.clipboard.header'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH =              'config.defaultSession.information.clipboard.minWidth'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH =              'config.defaultSession.information.clipboard.maxWidth'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE =       'config.defaultSession.information.clipboard.minWidthActive'
    CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE =       'config.defaultSession.information.clipboard.maxWidthActive'

    SESSION_INFO_TOCLIPBOARD_BORDER =                        'session.information.clipboard.border'
    SESSION_INFO_TOCLIPBOARD_HEADER =                        'session.information.clipboard.header'
    SESSION_INFO_TOCLIPBOARD_MINWIDTH =                      'session.information.clipboard.minWidth'
    SESSION_INFO_TOCLIPBOARD_MAXWIDTH =                      'session.information.clipboard.maxWidth'
    SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE =               'session.information.clipboard.minWidthActive'
    SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE =               'session.information.clipboard.maxWidthActive'

    SESSION_MAINWINDOW_SPLITTER_POSITION =                   'session.mainwindow.splitter.position'
    SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE =              'session.mainwindow.panel.secondaryVisible'
    SESSION_MAINWINDOW_PANEL_HIGHLIGHTED =                   'session.mainwindow.panel.highlighted'
    SESSION_MAINWINDOW_WINDOW_GEOMETRY =                     'session.mainwindow.window.geometry'
    SESSION_MAINWINDOW_WINDOW_MAXIMIZED =                    'session.mainwindow.window.maximized'

    SESSION_PANELS_VIEW_FILES_MANAGEDONLY =                  'session.panels.view.filesManagedOnly'
    SESSION_PANELS_VIEW_FILES_BACKUP =                       'session.panels.view.filesBackup'
    SESSION_PANELS_VIEW_FILES_HIDDEN =                       'session.panels.view.filesHidden'

    SESSION_PANEL_VIEW_LAYOUT =                              'session.panels.panel-{panelId}.view.layout'
    SESSION_PANEL_VIEW_CURRENTPATH =                         'session.panels.panel-{panelId}.view.currentPath'
    SESSION_PANEL_VIEW_FILTERVISIBLE =                       'session.panels.panel-{panelId}.view.filterVisible'
    SESSION_PANEL_VIEW_FILTERVALUE =                         'session.panels.panel-{panelId}.view.filterValue'
    SESSION_PANEL_VIEW_COLUMNSORT =                          'session.panels.panel-{panelId}.view.columnSort'
    SESSION_PANEL_VIEW_COLUMNORDER =                         'session.panels.panel-{panelId}.view.columnOrder'
    SESSION_PANEL_VIEW_COLUMNSIZE =                          'session.panels.panel-{panelId}.view.columnSize'
    SESSION_PANEL_VIEW_THUMBNAIL =                           'session.panels.panel-{panelId}.view.thumbnail'
    SESSION_PANEL_VIEW_ICONSIZE =                            'session.panels.panel-{panelId}.view.iconSize'
    SESSION_PANEL_SPLITTER_FILES_POSITION =                  'session.panels.panel-{panelId}.splitter.files.position'
    SESSION_PANEL_SPLITTER_PREVIEW_POSITION =                'session.panels.panel-{panelId}.splitter.preview.position'
    SESSION_PANEL_ACTIVETAB_MAIN =                           'session.panels.panel-{panelId}.activeTab.main'
    SESSION_PANEL_ACTIVETAB_FILES =                          'session.panels.panel-{panelId}.activeTab.files'
    SESSION_PANEL_ACTIVETAB_FILES_NFO =                      'session.panels.panel-{panelId}.activeTab.filesNfo'
    SESSION_PANEL_POSITIONTAB_MAIN =                         'session.panels.panel-{panelId}.positionTab.main'
    SESSION_PANEL_POSITIONTAB_FILES =                        'session.panels.panel-{panelId}.positionTab.files'
    SESSION_PANEL_PREVIEW_BACKGROUND =                       'session.panels.panel-{panelId}.preview.background'

    SESSION_HISTORY_ITEMS =                                  'session.history.items'
    SESSION_BOOKMARK_ITEMS =                                 'session.bookmark.items'
    SESSION_SAVEDVIEWS_ITEMS =                               'session.savedview.items'
    SESSION_LASTDOC_O_ITEMS =                                'session.lastDocuments.opened.items'
    SESSION_LASTDOC_S_ITEMS =                                'session.lastDocuments.saved.items'

    def id(self, **param):
        if isinstance(param, dict):
            return self.value.format(**param)
        else:
            return self.value


class BCSettings(object):
    """Manage all BuliCommander settings with open&save options

    Configuration is saved as JSON file
    """

    def __init__(self, pluginId=None, panelIds=[0, 1]):
        """Initialise settings"""
        if pluginId is None or pluginId == '':
            pluginId = 'bulicommander'

        self.__pluginCfgFile = os.path.join(QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation), f'krita-plugin-{pluginId}rc.json')
        self.__config = {}

        # define current rules for options
        self.__rules = {
            # values are tuples:
            # [0]       = default value
            # [1..n]    = values types & accepted values
            BCSettingsKey.CONFIG_FILE_DEFAULTACTION_KRA.id():                   (BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                            BCSettingsFmt(str, [BCSettingsValues.FILE_DEFAULTACTION_OPEN,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE])),
            BCSettingsKey.CONFIG_FILE_NEWFILENAME_KRA.id():                     ('<none>',                  BCSettingsFmt(str)),
            BCSettingsKey.CONFIG_FILE_DEFAULTACTION_OTHER.id():                 (BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE,
                                                                                                            BCSettingsFmt(str, [BCSettingsValues.FILE_DEFAULTACTION_OPEN,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW,
                                                                                                                                BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE])),
            BCSettingsKey.CONFIG_FILE_NEWFILENAME_OTHER.id():                   ('{file:name}.{file:ext}.kra',
                                                                                                            BCSettingsFmt(str)),

            BCSettingsKey.CONFIG_FILE_UNIT.id():                                (BCSettingsValues.FILE_UNIT_KIB,
                                                                                                            BCSettingsFmt(str, [BCSettingsValues.FILE_UNIT_KIB,
                                                                                                                                BCSettingsValues.FILE_UNIT_KB])),
            BCSettingsKey.CONFIG_HOME_DIR_MODE.id():                            (BCSettingsValues.HOME_DIR_SYS,
                                                                                                            BCSettingsFmt(str, [BCSettingsValues.HOME_DIR_SYS,
                                                                                                                                BCSettingsValues.HOME_DIR_UD])),
            BCSettingsKey.CONFIG_HOME_DIR_UD.id():                              ('',                        BCSettingsFmt(str)),

            BCSettingsKey.CONFIG_HISTORY_MAXITEMS.id():                         (25,                       BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_HISTORY_KEEPONEXIT.id():                       (True,                     BCSettingsFmt(bool)),

            BCSettingsKey.CONFIG_LASTDOC_MAXITEMS.id():                         (25,                       BCSettingsFmt(int)),

            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HOME.id():                      (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_VIEWS.id():                     (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BOOKMARKS.id():                 (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HISTORY.id():                   (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_LASTDOCUMENTS.id():             (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BACK.id():                      (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_UP.id():                        (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_NAVBAR_BUTTONS_QUICKFILTER.id():               (True,                     BCSettingsFmt(bool)),

            BCSettingsKey.CONFIG_SESSION_SAVE.id():                             (True,                     BCSettingsFmt(bool)),

            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_MANAGEDONLY.id():   (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_BACKUP.id():        (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_FILES_HIDDEN.id():        (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_LAYOUT.id():              ('top',                    BCSettingsFmt(str, ['full','top','left','right','bottom'])),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_THUMBNAIL.id():           (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_ICONSIZE.id():            (0,                        BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8])),
            BCSettingsKey.CONFIG_DSESSION_PANELS_VIEW_NFOROW.id():              (7,                        BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8,9])),

            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_BORDER.id():         (3,                        BCSettingsFmt(int, [0,1,2,3])),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_HEADER.id():         (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH.id():       (80,                       BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH.id():       (120,                      BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE.id():(True,                     BCSettingsFmt(bool)),
            BCSettingsKey.CONFIG_DSESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE.id():(False,                    BCSettingsFmt(bool)),

            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_BORDER.id():                 (3,                        BCSettingsFmt(int, [0,1,2,3])),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_HEADER.id():                 (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH.id():               (80,                       BCSettingsFmt(int)),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH.id():               (120,                      BCSettingsFmt(int)),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MINWIDTH_ACTIVE.id():        (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_INFO_TOCLIPBOARD_MAXWIDTH_ACTIVE.id():        (False,                    BCSettingsFmt(bool)),

            BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION.id():            ([1000, 1000],             BCSettingsFmt(int), BCSettingsFmt(int)),
            BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE.id():       (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED.id():            (0,                        BCSettingsFmt(int, [0, 1])),
            BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY.id():              ([-1,-1,-1,-1],            BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int)),
            BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED.id():             (False,                    BCSettingsFmt(bool)),


            BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY.id():           (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP.id():                (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN.id():                (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_HISTORY_ITEMS.id():                           ([],                       BCSettingsFmt(list, str)),
            BCSettingsKey.SESSION_BOOKMARK_ITEMS.id():                          ([],                       BCSettingsFmt(list)),
            BCSettingsKey.SESSION_SAVEDVIEWS_ITEMS.id():                        ([],                       BCSettingsFmt(list)),
            BCSettingsKey.SESSION_LASTDOC_O_ITEMS.id():                         ([],                       BCSettingsFmt(list)),
            BCSettingsKey.SESSION_LASTDOC_S_ITEMS.id():                         ([],                       BCSettingsFmt(list))
        }

        for panelId in panelIds:
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_LAYOUT.id(panelId=panelId)] =       ('top',                       BCSettingsFmt(str, ['full','top','left','right','bottom']))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_CURRENTPATH.id(panelId=panelId)] =  ('@home',                     BCSettingsFmt(str))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_FILTERVISIBLE.id(panelId=panelId)] =(True,                        BCSettingsFmt(bool))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_FILTERVALUE.id(panelId=panelId)] =  ('*',                         BCSettingsFmt(str))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_COLUMNSORT.id(panelId=panelId)] =   ([1,True],                    BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(bool))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_COLUMNORDER.id(panelId=panelId)] =  ([0,1,2,3,4,5,6,7,8],         BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]), BCSettingsFmt(int, [0,1,2,3,4,5,6,7,8]))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_COLUMNSIZE.id(panelId=panelId)] =   ([0,0,0,0,0,0,0,0,0],         BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int))
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_ICONSIZE.id(panelId=panelId)] =     (0,                           BCSettingsFmt(int, [0, 1, 2, 3, 4, 5, 6, 7, 8]))

            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_THUMBNAIL.id(panelId=panelId)] =    (False,                       BCSettingsFmt(bool))

            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId)] =    ('files',                             BCSettingsFmt(str, ['files','documents','clipboard']))
            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId)] =   ('info',                              BCSettingsFmt(str, ['info','dirtree']))
            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId)]=('generic',                           BCSettingsFmt(str, ['generic','image','kra']))
            self.__rules[BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId)] =  (['files', 'documents', 'clipboard'], BCSettingsFmt(str, ['files','documents','clipboard']), BCSettingsFmt(str, ['files','documents','clipboard']), BCSettingsFmt(str, ['files','documents','clipboard']))
            self.__rules[BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId)] = (['info', 'dirtree'],                 BCSettingsFmt(str, ['info','dirtree']), BCSettingsFmt(str, ['info','dirtree']))
            self.__rules[BCSettingsKey.SESSION_PANEL_SPLITTER_FILES_POSITION.id(panelId=panelId)] = ([1000,1000],                   BCSettingsFmt(int), BCSettingsFmt(int))
            self.__rules[BCSettingsKey.SESSION_PANEL_SPLITTER_PREVIEW_POSITION.id(panelId=panelId)] = ([1000,1000],                 BCSettingsFmt(int), BCSettingsFmt(int))

            self.__rules[BCSettingsKey.SESSION_PANEL_PREVIEW_BACKGROUND.id(panelId=panelId)] =(4,                           BCSettingsFmt(int, [0, 1, 2, 3, 4]))

        self.setDefaultConfig()
        self.loadConfig()

    def __setValue(self, target, id, value):
        """From an id like 'a.b.c', set value in target dictionary"""
        keys = id.split('.', 1)

        if len(keys) == 1:
            target[keys[0]] = value
        else:
            if not keys[0] in target:
                target[keys[0]] = {}

            self.__setValue(target[keys[0]], keys[1], value)

    def __getValue(self, target, id):
        """From an id like 'a.b.c', get value in target dictionary"""
        keys = id.split('.', 1)

        if len(keys) == 1:
            return target[keys[0]]
        else:
            return self.__getValue(target[keys[0]], keys[1])

    def configurationFile(self):
        """Return the configuration file name"""
        return self.__pluginCfgFile

    def setDefaultConfig(self):
        """Reset default configuration"""
        self.__config = {}

        for rule in self.__rules:
            self.__setValue(self.__config, rule, self.__rules[rule][0])

    def loadConfig(self):
        """Load configuration from file

        If file doesn't exist return False
        Otherwise True
        """
        def setKeyValue(sourceKey, value):
            if isinstance(value, dict):
                for key in value:
                    setKeyValue(f'{sourceKey}.{key}', value[key])
            else:
                self.setOption(sourceKey, value)

        jsonAsDict = None

        if os.path.isfile(self.__pluginCfgFile):
            with open(self.__pluginCfgFile, 'r') as file:
                try:
                    jsonAsStr = file.read()
                except Exception as e:
                    Debug.print('[BCSettings.loadConfig] Unable to load file {0}: {1}', self.__pluginCfgFile, str(e))
                    return False

                try:
                    jsonAsDict = json.loads(jsonAsStr)
                except Exception as e:
                    Debug.print('[BCSettings.loadConfig] Unable to parse file {0}: {1}', self.__pluginCfgFile, str(e))
                    return False
        else:
            return False

        # parse all items, and set current config
        for key in jsonAsDict:
            setKeyValue(key, jsonAsDict[key])

        return True

    def saveConfig(self):
        """Save configuration to file

        If file can't be saved, return False
        Otherwise True
        """
        with open(self.__pluginCfgFile, 'w') as file:
            try:
                file.write(json.dumps(self.__config, indent=4, sort_keys=True))
            except Exception as e:
                Debug.print('[BCSettings.saveConfig] Unable to save file {0}: {1}', self.__pluginCfgFile, str(e))
                return False

        return True

    def setOption(self, id, value):
        """Set value for given option

        Given `id` must be valid (a BCSettingsKey)
        Given `value` format must be valid (accordiing to id, a control is made)
        """
        # check if id is valid
        if isinstance(id, BCSettingsKey):
            id = id.id()

        if not isinstance(id, str) or not id in self.__rules:
            #raise EInvalidValue(f'Given `id` is not valid: {id}')
            Debug.print('[BCSettings.setOption] Given id `{0}` is not valid', id)
            return

        # check if value is valid
        rules = self.__rules[id][1:]
        if len(rules) > 1:
            # value must be a list
            if not isinstance(value, list):
                #raise EInvalidType(f'Given `value` must be a list: {value}')
                Debug.print('[BCSettings.setOption] Given value for id `{1}` must be a list: `{0}`', value, id)
                return

            # number of item must match number of rules
            if len(rules) != len(value):
                Debug.print('[BCSettings.setOption] Given value for id `{1}` is not a valid list: `{0}`', value, id)
                return

            # check if each item match corresponding rule
            for index in range(len(value)):
                rules[index].check(value[index])
        else:
            rules[0].check(value)

        # value is valid, set it
        self.__setValue(self.__config, id, value)

    def option(self, id):
        """Return value for option"""
        # check if id is valid
        if isinstance(id, BCSettingsKey):
            id = id.id()

        if not isinstance(id, str) or not id in self.__rules:
            raise EInvalidValue(f'Given `id` is not valid: {id}')


        return self.__getValue(self.__config, id)

    def options(self):
        return self.__config


class BCSettingsDialogBox(QDialog):

    CATEGORY_GENERAL = 0
    CATEGORY_NAVIGATION = 1
    CATEGORY_IMAGES = 2
    CATEGORY_CACHE = 3

    def __init__(self, title, uicontroller, parent=None):
        super(BCSettingsDialogBox, self).__init__(parent)

        self.__title = title

        uiFileName = os.path.join(os.path.dirname(__file__), 'resources', 'bcsettings.ui')
        PyQt5.uic.loadUi(uiFileName, self)

        self.setWindowTitle(self.__title)
        self.lvCategory.itemSelectionChanged.connect(self.__categoryChanged)

        self.__itemCatGeneral = QListWidgetItem(QIcon(":/images/tune"), "General")
        self.__itemCatGeneral.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_GENERAL)
        self.__itemCatNavigation = QListWidgetItem(QIcon(":/images/navigation"), "Navigation")
        self.__itemCatNavigation.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_NAVIGATION)
        self.__itemCatImageFiles = QListWidgetItem(QIcon(":/images/large_view"), "Image files")
        self.__itemCatImageFiles.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_IMAGES)
        self.__itemCatCachedImages = QListWidgetItem(QIcon(":/images/cached"), "Cached images")
        self.__itemCatCachedImages.setData(Qt.UserRole, BCSettingsDialogBox.CATEGORY_CACHE)

        self.__uiController = uicontroller

        self.pbCCIClearCache.clicked.connect(self.__clearCache)

        self.bbOkCancel.accepted.connect(self.__applySettings)

        self.__initialise()


    def __initialise(self):
        """Initialise interface"""
        def updateBtn():
            if self.__uiController.history().length()>0:
                self.pbCNHistoryClear.setEnabled(True)
                self.pbCNHistoryClear.setToolTip(i18n(f'Clear current navigation history ({self.__uiController.history().length()} places in history)'))
            else:
                self.pbCNHistoryClear.setEnabled(False)
                self.pbCNHistoryClear.setToolTip(i18n(f'Clear current navigation history (no places in history)'))

            nbTotalDoc = len(set((self.__uiController.lastDocumentsOpened().list() + self.__uiController.lastDocumentsSaved().list())))
            if nbTotalDoc>0:
                self.pbCNLastDocumentsClear.setEnabled(True)
                self.pbCNLastDocumentsClear.setToolTip(i18n(f'Clear list of last opened/saved documents ({nbTotalDoc} documents in list)'))
            else:
                self.pbCNLastDocumentsClear.setEnabled(False)
                self.pbCNLastDocumentsClear.setToolTip(i18n(f'Clear list of last opened/saved documents (no document in list)'))

            if len(Krita.instance().recentDocuments())>0:
                self.pbCNLastDocumentsReset.setEnabled(True)
                self.pbCNLastDocumentsReset.setToolTip(i18n(f'Reset list of last opened/saved documents from Krita\'s internal list ({len(Krita.instance().recentDocuments())} documents in list)'))
            else:
                self.pbCNLastDocumentsReset.setEnabled(False)
                self.pbCNLastDocumentsReset.setToolTip(i18n(f'Reset list of last opened/saved documents from Krita\'s internal list (no document in list)'))

        @pyqtSlot('QString')
        def setHomeDirSys(action):
            self.bcpbCNUserDefined.setEnabled(False)
        @pyqtSlot('QString')
        def setHomeDirUD(action):
            self.bcpbCNUserDefined.setEnabled(True)
        @pyqtSlot('QString')
        def historyClear(action):
            if self.__uiController.commandGoHistoryClearUI():
                self.pbCNHistoryClear.setEnabled(False)
                updateBtn()
        @pyqtSlot('QString')
        def lastDocumentsClear(action):
            if self.__uiController.commandGoLastDocsClearUI():
                self.pbCNLastDocumentsClear.setEnabled(False)
                updateBtn()
        @pyqtSlot('QString')
        def lastDocumentsReset(action):
            if self.__uiController.commandGoLastDocsResetUI():
                updateBtn()


        self.bcpbCNUserDefined.setPath(self.__uiController.settings().option(BCSettingsKey.CONFIG_HOME_DIR_UD.id()))
        self.bcpbCNUserDefined.setOptions(BCPathBar.OPTION_SHOW_NONE)


        self.cbCNNavBarBtnHome.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HOME.id()))
        self.cbCNNavBarBtnViews.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_VIEWS.id()))
        self.cbCNNavBarBtnBookmarks.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BOOKMARKS.id()))
        self.cbCNNavBarBtnHistory.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_HISTORY.id()))
        self.cbCNNavBarBtnLastDocuments.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_LASTDOCUMENTS.id()))
        self.cbCNNavBarBtnGoBack.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_BACK.id()))
        self.cbCNNavBarBtnGoUp.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_UP.id()))
        self.cbCNNavBarBtnQuickFilter.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_NAVBAR_BUTTONS_QUICKFILTER.id()))

        if self.__uiController.settings().option(BCSettingsKey.CONFIG_HOME_DIR_MODE.id()) == BCSettingsValues.HOME_DIR_SYS:
            self.rbCNHomeDirSys.setChecked(True)
            self.bcpbCNUserDefined.setEnabled(False)
        else:
            self.rbCNHomeDirUD.setChecked(True)
            self.bcpbCNUserDefined.setEnabled(True)

        self.rbCNHomeDirSys.clicked.connect(setHomeDirSys)
        self.rbCNHomeDirUD.clicked.connect(setHomeDirUD)

        self.lvCategory.addItem(self.__itemCatGeneral)
        self.lvCategory.addItem(self.__itemCatNavigation)
        self.lvCategory.addItem(self.__itemCatImageFiles)
        self.lvCategory.addItem(self.__itemCatCachedImages)
        self.__setCategory(BCSettingsDialogBox.CATEGORY_GENERAL)

        self.hsCNHistoryMax.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_HISTORY_MAXITEMS.id()))
        self.cbCNHistoryKeepWhenQuit.setChecked(self.__uiController.settings().option(BCSettingsKey.CONFIG_HISTORY_KEEPONEXIT.id()))

        self.hsCNLastDocsMax.setValue(self.__uiController.settings().option(BCSettingsKey.CONFIG_LASTDOC_MAXITEMS.id()))

        if self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_UNIT.id()) == BCSettingsValues.FILE_UNIT_KIB:
            self.rbCGFileUnitBinary.setChecked(True)
        else:
            self.rbCGFileUnitDecimal.setChecked(True)

        value = self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_KRA.id())
        if value == BCSettingsValues.FILE_DEFAULTACTION_OPEN:
            self.rbCIFKraOpenDoc.setChecked(True)
            self.cbCIFKraOptCloseBC.setChecked(False)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE:
            self.rbCIFKraOpenDoc.setChecked(True)
            self.cbCIFKraOptCloseBC.setChecked(True)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW:
            self.rbCIFKraCreateDoc.setChecked(True)
            self.cbCIFKraOptCloseBC.setChecked(False)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE:
            self.rbCIFKraCreateDoc.setChecked(True)
            self.cbCIFKraOptCloseBC.setChecked(True)

        self.cbxCIFKraOptCreDocName.addItems([
                '<None>',
                '{file:name}-{counter:####}.kra',
                '{file:name}_{date}_{time}.kra',
                i18n('{file:name}-Copy {counter:####}.kra'),
                i18n('{file:name}-Copy {date}_{time}.kra')
            ])
        self.cbxCIFKraOptCreDocName.setCurrentText(self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_NEWFILENAME_KRA.id()))

        value = self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_DEFAULTACTION_OTHER.id())
        if value == BCSettingsValues.FILE_DEFAULTACTION_OPEN:
            self.rbCIFOthOpenDoc.setChecked(True)
            self.cbCIFOthOptCloseBC.setChecked(False)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE:
            self.rbCIFOthOpenDoc.setChecked(True)
            self.cbCIFOthOptCloseBC.setChecked(True)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW:
            self.rbCIFOthCreateDoc.setChecked(True)
            self.cbCIFOthOptCloseBC.setChecked(False)
        elif value == BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE:
            self.rbCIFOthCreateDoc.setChecked(True)
            self.cbCIFOthOptCloseBC.setChecked(True)

        self.cbxCIFOthOptCreDocName.addItems([
                '<None>',
                '{file:name}.{file:ext}.kra',
                '{file:name}({file:ext}).kra',
                '{file:name}.kra',
                '{file:name}_{date}_{time}.kra',
                i18n('{file:name}-Copy {counter:####}.kra'),
                i18n('{file:name}-Copy {date}_{time}.kra')
            ])
        self.cbxCIFOthOptCreDocName.setCurrentText(self.__uiController.settings().option(BCSettingsKey.CONFIG_FILE_NEWFILENAME_OTHER.id()))


        self.pbCNHistoryClear.clicked.connect(historyClear)
        self.pbCNLastDocumentsClear.clicked.connect(lastDocumentsClear)
        self.pbCNLastDocumentsReset.clicked.connect(lastDocumentsReset)
        updateBtn()


    def __applySettings(self):
        """Apply current settings"""

        self.__uiController.commandSettingsHomeDirUserDefined(self.bcpbCNUserDefined.path())
        if self.rbCNHomeDirSys.isChecked():
            self.__uiController.commandSettingsHomeDirMode(BCSettingsValues.HOME_DIR_SYS)
        else:
            self.__uiController.commandSettingsHomeDirMode(BCSettingsValues.HOME_DIR_UD)


        if self.rbCGFileUnitBinary.isChecked():
            self.__uiController.commandSettingsFileUnit(BCSettingsValues.FILE_UNIT_KIB)
        else:
            self.__uiController.commandSettingsFileUnit(BCSettingsValues.FILE_UNIT_KB)

        if self.rbCIFKraOpenDoc.isChecked():
            if self.cbCIFKraOptCloseBC.isChecked():
                self.__uiController.commandSettingsFileDefaultActionKra(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE)
            else:
                self.__uiController.commandSettingsFileDefaultActionKra(BCSettingsValues.FILE_DEFAULTACTION_OPEN)
        elif self.rbCIFKraCreateDoc.isChecked():
            if self.cbCIFKraOptCloseBC.isChecked():
                self.__uiController.commandSettingsFileDefaultActionKra(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE)
            else:
                self.__uiController.commandSettingsFileDefaultActionKra(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW)

        if self.rbCIFOthOpenDoc.isChecked():
            if self.cbCIFOthOptCloseBC.isChecked():
                self.__uiController.commandSettingsFileDefaultActionOther(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AND_CLOSE)
            else:
                self.__uiController.commandSettingsFileDefaultActionOther(BCSettingsValues.FILE_DEFAULTACTION_OPEN)
        elif self.rbCIFOthCreateDoc.isChecked():
            if self.cbCIFOthOptCloseBC.isChecked():
                self.__uiController.commandSettingsFileDefaultActionOther(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW_AND_CLOSE)
            else:
                self.__uiController.commandSettingsFileDefaultActionOther(BCSettingsValues.FILE_DEFAULTACTION_OPEN_AS_NEW)

        self.__uiController.commandSettingsFileNewFileNameKra(self.cbxCIFKraOptCreDocName.currentText())
        self.__uiController.commandSettingsFileNewFileNameOther(self.cbxCIFOthOptCreDocName.currentText())

        self.__uiController.commandSettingsNavBarBtnHome(self.cbCNNavBarBtnHome.isChecked())
        self.__uiController.commandSettingsNavBarBtnViews(self.cbCNNavBarBtnViews.isChecked())
        self.__uiController.commandSettingsNavBarBtnBookmarks(self.cbCNNavBarBtnBookmarks.isChecked())
        self.__uiController.commandSettingsNavBarBtnHistory(self.cbCNNavBarBtnHistory.isChecked())
        self.__uiController.commandSettingsNavBarBtnLastDocuments(self.cbCNNavBarBtnLastDocuments.isChecked())
        self.__uiController.commandSettingsNavBarBtnGoBack(self.cbCNNavBarBtnGoBack.isChecked())
        self.__uiController.commandSettingsNavBarBtnGoUp(self.cbCNNavBarBtnGoUp.isChecked())
        self.__uiController.commandSettingsNavBarBtnQuickFilter(self.cbCNNavBarBtnQuickFilter.isChecked())

        self.__uiController.commandSettingsHistoryMaxSize(self.hsCNHistoryMax.value())
        self.__uiController.commandSettingsHistoryKeepOnExit(self.cbCNHistoryKeepWhenQuit.isChecked())

        self.__uiController.commandSettingsLastDocsMaxSize(self.hsCNLastDocsMax.value())

    def __categoryChanged(self):
        """Set page according to category"""
        self.swCatPages.setCurrentIndex(self.lvCategory.currentItem().data(Qt.UserRole))

        if self.lvCategory.currentItem().data(Qt.UserRole) == BCSettingsDialogBox.CATEGORY_CACHE:
            # calculate cache nb files+size
            self.__calculateCacheSize()


    def __setCategory(self, value):
        """Set category setting

        Select icon, switch to panel
        """
        self.lvCategory.setCurrentRow(value)


    def __calculateCacheSize(self):
        """Calculate cache size"""
        nbFiles = 0
        sizeFiles = 0
        for root, dirs, files in os.walk(BCFile.thumbnailCacheDirectory()):
            sizeFiles+=sum(getsize(join(root, name)) for name in files)
            nbFiles+=len(files)

        if self.rbCGFileUnitBinary.isChecked():
            self.__uiController.commandSettingsFileUnit(BCSettingsValues.FILE_UNIT_KIB)
            self.lblCCINbFileAndSize.setText(f'{nbFiles} files, {bytesSizeToStr(sizeFiles, BCSettingsValues.FILE_UNIT_KIB)}')
        else:
            self.__uiController.commandSettingsFileUnit(BCSettingsValues.FILE_UNIT_KB)
            self.lblCCINbFileAndSize.setText(f'{nbFiles} files, {bytesSizeToStr(sizeFiles, BCSettingsValues.FILE_UNIT_KB)}')

        self.pbCCIClearCache.setEnabled(sizeFiles>0)


    def __clearCache(self):
        """Clear cache after user confirmation"""

        if QMessageBox.question(self, f"{self.__title}::Clear Cache", f"Current cache content will be cleared ({self.lblCCINbFileAndSize.text()})\n\nDo you confirm action?", QMessageBox.Yes, QMessageBox.No) == QMessageBox.Yes:
            shutil.rmtree(BCFile.thumbnailCacheDirectory(), ignore_errors=True)
            self.__calculateCacheSize()

    @staticmethod
    def open(title, uicontroller):
        """Open dialog box"""
        db = BCSettingsDialogBox(title, uicontroller)
        return db.exec()

