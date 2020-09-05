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


#from bulicommander import (
#        BCList
#    )

from enum import Enum

import re

from .bclist import BCList

class BCTokenType(Enum):
    pass

class BCToken(object):
    """A token

    Once created, can't be changed

    A token have the following properties:
    - a type
    - a value
    - position (column and row) from original text
    """
    def __init__(self, type, value, col=None, row=None):
        self.__type = type
        self.__value = value
        self.__pCol = col
        self.__pRow = row

    def __repr__(self):
        return f'<BCToken(Position={self.__pCol},{self.__pRow}; Type={self.__type}; Value={self.__value})>'

    def __str__(self):
        return f'| {self.__pCol:>5} | {self.__pRow:>5} | {self.__type:<50} | {self.__value}'

    def type(self):
        """Return token type"""
        return self.__type

    def value(self):
        """Return token value"""
        return self.__value

    def column(self):
        """Return column number for token"""
        return self.__pCol

    def row(self):
        """Return row number for token"""
        return self.__pRow

class BCTokens(BCList):
    """A tokenized text with facilities to access and parse tokens"""

    def __init__(self, text, tokens):
        super(BCTokens, self).__init__(tokens)

        self.__text = None

        if isinstance(text, str):
            self.__text = text
        else:
            raise Exception('Given `text` must be a <str>')

    def text(self):
        """Return original tokenized text"""
        return self.__text

    def inText(self, displayPosition=False, position=None):
        """Return current token in text

        if `position` is provided (a tuple(column, row)), return text at the given
        position
        """
        col = 0
        row = 0
        length = 1

        if position is None:
            if self.value() is None:
                # nothing to return
                return ""
            else:
                col = self.value().column()
                row = self.value().row()
                length = len(self.value().value())
        elif isinstance(position, tuple):
            if len(position) >= 2 and isinstance(position[0], int):
                col = position[0]
            else:
                raise Exception("Given `position` must be a <tuple(<int>,<int>)>")

            if len(position) >= 2 and isinstance(position[1], int):
                row = position[1]
            else:
                raise Exception("Given `position` must be a <tuple(<int>,<int>)>")

            if len(position) >= 3 and isinstance(position[3], int):
                length = max(1, position[1])
        else:
            raise Exception("Given `position` must be a <tuple(<int>,<int>)>")

        rows = self.__text.split('\n')

        returned = []
        if row >= 0 and row < len(rows):
            if displayPosition:
                returned.append(f'At position ({col}, {row}):')

            returned.append(rows[row])

            if col >=0 and col < len(rows[row]):
                returned.append( ('.' * col) + ('^' * length) )
            elif col<0:
                returned.append( '<--' )
            else:
                returned.append( ('-' * len(rows[row])) + '>' )

            return '\n'.join(returned)
        else:
            return f"Given position ({col}, {row}) is outside text"

class BCTokenizerRule(object):
    """Define a rule used by tokenizer to build a token

    A tokenizer rule is defined by:
    - A regular expression
    - A token type
    """
    def __init__(self, type, regex):
        self.__type = None
        self.__regex = ''
        self.__error = []

        self.__setRegEx(regex)
        self.__setType(type)

    def __str__(self):
        return f'{self.__type.value}: {self.__regex}'

    def __repr__(self):
        return f"<BCTokenizerRule({self.__type.value}, '{self.__regex}')>"

    def regEx(self):
        """Return current regular expression for rule"""
        return self.__regex

    def type(self):
        """Return current type for rule"""
        return self.__type

    def __setRegEx(self, value):
        """Set current regular expression for rule

        Given `value` can be:
        - A regex.pattern
        - A string

        If invalid, doesn't raise error: just define rule as 'in error' with a message
        """
        if isinstance(value, re.Pattern):
            self.__regex = value.pattern
        elif isinstance(value, str):
            self.__regex = str(value)
            try:
                re.compile(value)
            except Exception as e:
                self.__error = "Given rule is not a valid regular expression: " + str(e)
        else:
            self.__regex = str(value)
            self.__error.append("Given rule must be a valid regular expression string")

    def __setType(self, value):
        """Set current type for rule"""
        if isinstance(value, BCTokenType):
            self.__type = value
        else:
            self.__error.append("Given type must be a valid <BCTokenType>")

    def isValid(self):
        """Return True is token rule is valid"""
        return len(self.__error) == 0

    def errors(self):
        """Return errors list"""
        return self.__error

class BCTokenizer(object):
    """A tokenizer will 'split' a text into tokens, according to given rules


    note: the tokenizer doesn't verify the validity of tokenized text (this is
          made in a second time by parser)
    """

    def __init__(self, rules=None):
        self.__ruleList = []
        self.__ruleDict = {}

        self.__invalidRules = []

        self.__reBuilt = None
        self.__caseRule = re.IGNORECASE

        if not rules is None:
            self.setRules(rules)

    def __str__(self):
        return ""

    def __add(self, rule):
        """Add a tokenizer rule

        Given `rule` must be a <BCTokenizerRule>
        """
        if isinstance(rule, BCTokenizerRule):
            if not rule.type() in self.__ruleDict:
                if rule.type() != None:
                    self.__ruleList.append(rule.regEx())
                    self.__ruleDict[rule.type()] = rule
                else:
                    self.__invalidRules.append((rule, "The rule type is set to NONE: the NONE type is reserved"))
            else:
                self.__invalidRules.append((rule, 'A rule has already been provided for type!'))
        else:
            raise Exception("Given `rule` must be a <BCTokenizerRule>")

    def __identify(self, value):
        """Identify type or given token"""
        for ruleType in self.__ruleDict:
            #print('identify:', self.__ruleDict[ruleType].regEx(), ' / ', value)
            if not re.match(self.__ruleDict[ruleType].regEx(), value, self.__caseRule) is None:
                return ruleType

        return None

    def rules(self):
        """return list of given (and valid) rules"""
        return self.__ruleList

    def invalidRules(self):
        """Return list of invalid given rules"""
        return self.__invalidRules

    def setRules(self, rules):
        """Define tokenizer rules"""
        if isinstance(rules, list):
            self.__ruleList = []
            self.__ruleDict = {}
            self.__invalidRules = []

            for rule in rules:
                self.__add(rule)

            self.__reBuilt = re.compile('|'.join(self.__ruleList), self.__caseRule)
        else:
            raise Exception("Given `rules` must be a list of <BCTokenizerRule>")

    def tokenize(self, text):
        """Tokenize given text

        Return a BCTokens object
        """
        returned = []

        if not isinstance(text, str):
            raise Exception("Given `text` must be a <str>")

        if text == "" or len(self.__ruleList) == 0:
            # nothing to process (empty string and/or no rules?)
            returned.append(BCToken(None, ''))
            return returned

        tokens = self.__reBuilt.findall(text)
        if len(tokens) > 0:
            currentCol = 0
            currentRow = 0
            for token in tokens:
                #print('Token:', token, ' / Type:', self.identify(token))

                returned.append(BCToken(self.__identify(token), token, currentCol, currentRow))

                if token == '\n':
                    currentCol = 0
                    currentRow += 1
                else:
                    currentCol += len(token)

        else:
            returned.append(BCToken(None, ''))
            return returned



        return BCTokens(text, returned)

class BCTokenFollow(object):

    def __init__(self, tokenType, section=None, newSection=None):
        pass