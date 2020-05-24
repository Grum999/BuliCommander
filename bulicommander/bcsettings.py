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


from PyQt5.QtCore import (
        pyqtSignal,
        QSettings,
        QStandardPaths
    )

import json
import os
import re
import sys


# Reload or Import
if 'bulicommander.bcutils' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.bcutils'])
else:
    import bulicommander.bcutils

if 'bulicommander.pktk.pktk' in sys.modules:
    from importlib import reload
    reload(sys.modules['bulicommander.pktk.pktk'])
else:
    import bulicommander.pktk.pktk


from bulicommander.bcutils import (
        Debug
    )

from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue
    )

# -----------------------------------------------------------------------------

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

        if not isinstance(value, self.__type):
            raise EInvalidType('Given `value` is not from expected type')

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
                    raise EInvalidValue('Given `value` is not in authorized perimeter')
            elif isinstance(self.__values, re.Pattern):
                if self.__values.match(value) is None:
                    raise EInvalidValue('Given `value` is not in authorized perimeter')


class BCSettingsKey(Enum):
    CONFIG_HISTORY_MAXITEMS =                                'config.history.maximumItems'
    CONFIG_SESSION_SAVE =                                    'config.session.save'


    SESSION_MAINWINDOW_SPLITTER_POSITION =                   'session.mainwindow.splitter.position'
    SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE =              'session.mainwindow.panel.secondaryVisible'
    SESSION_MAINWINDOW_PANEL_HIGHLIGHTED =                   'session.mainwindow.panel.highlighted'
    SESSION_MAINWINDOW_WINDOW_GEOMETRY =                     'session.mainwindow.window.geometry'
    SESSION_MAINWINDOW_WINDOW_MAXIMIZED =                    'session.mainwindow.window.maximized'

    SESSION_PANELS_VIEW_MODE =                               'session.panels.view.mode'
    SESSION_PANELS_VIEW_FILES_MANAGEDONLY =                  'session.panels.view.filesManagedOnly'
    SESSION_PANELS_VIEW_FILES_BACKUP =                       'session.panels.view.filesBackup'
    SESSION_PANELS_VIEW_FILES_HIDDEN =                       'session.panels.view.filesHidden'

    SESSION_PANEL_VIEW_LAYOUT =                              'session.panels.panel-{panelId}.view.layout'
    SESSION_PANEL_ACTIVETAB_MAIN =                           'session.panels.panel-{panelId}.activeTab.main'
    SESSION_PANEL_ACTIVETAB_FILES =                          'session.panels.panel-{panelId}.activeTab.files'
    SESSION_PANEL_ACTIVETAB_FILES_NFO =                      'session.panels.panel-{panelId}.activeTab.filesNfo'
    SESSION_PANEL_POSITIONTAB_MAIN =                         'session.panels.panel-{panelId}.positionTab.main'
    SESSION_PANEL_POSITIONTAB_FILES =                        'session.panels.panel-{panelId}.positionTab.files'
    SESSION_PANEL_SPLITTER_POSITION =                        'session.panels.panel-{panelId}.splitter.position'

    SESSION_HISTORY_ITEMS =                                  'session.history.items'

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
            BCSettingsKey.CONFIG_HISTORY_MAXITEMS.id():                         (25,                       BCSettingsFmt(int)),
            BCSettingsKey.CONFIG_SESSION_SAVE.id():                             (True,                     BCSettingsFmt(bool)),

            BCSettingsKey.SESSION_MAINWINDOW_SPLITTER_POSITION.id():            ([1000, 1000],             BCSettingsFmt(int), BCSettingsFmt(int)),
            BCSettingsKey.SESSION_MAINWINDOW_PANEL_SECONDARYVISIBLE.id():       (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_MAINWINDOW_PANEL_HIGHLIGHTED.id():            (0,                        BCSettingsFmt(int, [0, 1])),
            BCSettingsKey.SESSION_MAINWINDOW_WINDOW_GEOMETRY.id():              ([-1,-1,-1,-1],            BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int), BCSettingsFmt(int)),
            BCSettingsKey.SESSION_MAINWINDOW_WINDOW_MAXIMIZED.id():             (False,                    BCSettingsFmt(bool)),

            BCSettingsKey.SESSION_PANELS_VIEW_MODE.id():                        ('detailled',              BCSettingsFmt(str, ['detailled','small','medium','large'])),

            BCSettingsKey.SESSION_PANELS_VIEW_FILES_MANAGEDONLY.id():           (True,                     BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_PANELS_VIEW_FILES_BACKUP.id():                (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_PANELS_VIEW_FILES_HIDDEN.id():                (False,                    BCSettingsFmt(bool)),
            BCSettingsKey.SESSION_HISTORY_ITEMS.id():                           ([],                       BCSettingsFmt(list, str))
        }

        for panelId in panelIds:
            self.__rules[BCSettingsKey.SESSION_PANEL_VIEW_LAYOUT.id(panelId=panelId)] =       ('top',                    BCSettingsFmt(str, ['full','top','left','right','bottom']))
            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_MAIN.id(panelId=panelId)] =    ('files',                  BCSettingsFmt(str, ['files','documents']))
            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES.id(panelId=panelId)] =   ('info',                   BCSettingsFmt(str, ['info','dirtree']))
            self.__rules[BCSettingsKey.SESSION_PANEL_ACTIVETAB_FILES_NFO.id(panelId=panelId)]=('generic',                BCSettingsFmt(str, ['generic','kra']))
            self.__rules[BCSettingsKey.SESSION_PANEL_POSITIONTAB_MAIN.id(panelId=panelId)] =  (['files', 'documents'],   BCSettingsFmt(str, ['files','documents']), BCSettingsFmt(str, ['files','documents']))
            self.__rules[BCSettingsKey.SESSION_PANEL_POSITIONTAB_FILES.id(panelId=panelId)] = (['info', 'dirtree'],      BCSettingsFmt(str, ['info','dirtree']), BCSettingsFmt(str, ['info','dirtree']))
            self.__rules[BCSettingsKey.SESSION_PANEL_SPLITTER_POSITION.id(panelId=panelId)] = ([1000,1000],              BCSettingsFmt(int), BCSettingsFmt(int))

        self.setDefaultConfig()
        self.loadConfig()

    def __setValue(self, target, id, value):
        """From an id like 'a.b.c', set value in target dirctionary"""
        keys = id.split('.', 1)

        if len(keys) == 1:
            target[keys[0]] = value
        else:
            if not keys[0] in target:
                target[keys[0]] = {}

            self.__setValue(target[keys[0]], keys[1], value)

    def __getValue(self, target, id):
        """From an id like 'a.b.c', get value in target dirctionary"""
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
            raise EInvalidValue(f'Given `id` is not valid: {id}')

        # check if value is valid
        rules = self.__rules[id][1:]
        if len(rules) > 1:
            # value must be a list
            if not isinstance(value, list):
                raise EInvalidType(f'Given `value` must be a list: {value}')

            # number of item must match number of rules
            if len(rules) != len(value):
                raise EInvalidValue(f'Given `value` is not a valid list: {value}')

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
            raise EInvalidValue('Given `id` is not valid')


        return self.__getValue(self.__config, id)

    def options(self):
        return self.__config



