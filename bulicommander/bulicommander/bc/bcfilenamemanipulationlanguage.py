# -----------------------------------------------------------------------------
# Buli Commander
# Copyright (C) 2019-2022 - Grum999
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

from PyQt5.Qt import *
from PyQt5.QtCore import (
        pyqtSignal as Signal
    )

from enum import Enum
import os
import sys
import re
import shutil
import time

from .bcfile import (
        BCBaseFile,
        BCFile,
        BCDirectory,
        BCMissingFile,
        BCFileProperty,
        BCFileManagedFormat
    )

from bulicommander.pktk.modules.uitheme import UITheme
from bulicommander.pktk.modules.languagedef import LanguageDef
from bulicommander.pktk.modules.tokenizer import (
        Tokenizer,
        TokenizerRule,
        TokenType,
        Token
    )
from bulicommander.pktk.modules.parser import (
        GrammarRules,
        GrammarRule,
        GROne,
        GROptional,
        GRNoneOrMore,
        GROneOrMore,
        GRToken,
        GRRule,
        GROperatorPrecedence,
        ASTItem,
        ASTStatus,
        ASTSpecialItemType,
        Parser,
        ParserError
    )
from bulicommander.pktk.modules.timeutils import tsToStr
from bulicommander.pktk.modules.utils import (
        Debug,
        regExIsValid
    )
from bulicommander.pktk.pktk import (
        EInvalidType,
        EInvalidValue,
        EInvalidStatus
    )



class BCFileManipulateNameLanguageDef(LanguageDef):

    class ITokenType(TokenType, Enum):
        STRING = ('String', 'A STRING value')
        KW = ('Keyword', 'A keyword return a STRING value')
        FUNCO_STR = ('String function', 'A FUNCTION for which returned result is a STRING')
        FUNCO_INT = ('Number function', 'A FUNCTION for which returned result is an INTEGER')
        FUNCC = ('Function terminator', 'Define end of function')
        SEPARATOR = ('Separator', 'A separator for functions arguments')
        NUMBER = ('Number', 'A NUMBER value')
        TEXT = ('Text', 'A TEXT value')

    def __init__(self):
        super(BCFileManipulateNameLanguageDef, self).__init__([
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.STRING,
                          r'''\`[^\`\\]*(?:\\.[^`\\]*)*\`|'[^'\\]*(?:\\.[^'\\]*)*'|"[^"\\]*(?:\\.[^"\\]*)*"''',
                          onInitValue=self.__initTokenString),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR,
                          r'\[(?:upper|lower|capitalize|replace|sub|regex|index|camelize):',
                          'Function [STRING]',
                          [('[upper:\x01<value>\x01]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Convert text *<value>* to uppercase text\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword',
                                        # example
                                        'Following instruction:\n'
                                        '**`[upper:{file:baseName}]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`MY_FILE__NAME01`**')),
                           ('[lower:\x01<value>\x01]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Convert text *<value>* to lowercase text\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword',
                                        # example
                                        'Following instruction:\n'
                                        '**`[lower:{file:baseName}]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`MY-FILE--NAME01`*:\n'
                                        '**`my_file__name01`**')),
                           ('[capitalize:\x01<value>\x01]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Convert text *<value>* to capitalized text\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword',
                                        # example
                                        'Following instruction:\n'
                                        '**`[capitalize:{file:baseName}]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`My_file__name01`**')),
                           ('[camelize:\x01<value>\x01]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Convert text *<value>* to camel case text\n'
                                        '(First alpha character after non-alpha character is set yo upper case)\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword',
                                        # example
                                        'Following instruction:\n'
                                        '**`[camelize:{file:baseName}]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`My_File__Name01`**')),
                           ('[replace:\x01<value>\x01, "\x02<search>\x02", "\x02<replace>\x02"]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Search *<search>* sequences in *<value>* and replace it with *<replace>*\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword\n\n'
                                        'Given *<search>* and *<replace>* must be a string',
                                        # example
                                        'Following instruction:\n'
                                        '**`[replace:{file:baseName}, "_", "-"]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`my-file--name`**')),
                           ('[regex:\x01<value>\x01, "\x02<pattern>\x02"]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Return sequences from *<value>* that match given regular expression *<pattern>*\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword\n\n'
                                        'Given *<pattern>* must be a valid regular expression string',
                                        # example
                                        'Following instruction:\n'
                                        '**`[regex:{file:baseName}, "[a-z]+"]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`myfilename`**')),
                           ('[regex:\x01<value>\x01, "\x02<pattern>\x02", "\x02<replace>\x02"]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Replace sequences from *<value>* that match given regular expression *<pattern>* with *<replace>*\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword\n\n'
                                        'Given *<pattern>* must be a valid regular expression string\n\n'
                                        'Given *<replace>* must be a string (use $1, $2, $*n*... to replace captured groups)\n\n',
                                        # example
                                        'Following instruction:\n'
                                        r'**`[regex:{file:baseName}, "([^\d]+)(\d+)", "$2--$1"]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`01--my_file__name`**')),
                           ('[index:\x01<value>\x01, "\x02<separator>\x02", \x02<index>\x02]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Return string defined by *<index>* whitin *<value>* splitted with *<separator>*\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword\n\n'
                                        'Given *<separator>* position must be a valid string\n'
                                        'Given *<index>* position must be a valid number\n'
                                        ' - First index position is 1\n',
                                        # example
                                        'Following instructions:\n'
                                        '**`[index:{file:baseName}, "_", 2]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`file`**')),
                           ('[sub:\x01<value>\x01, \x02<start>\x02]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Return substring from *<value>* from *<start>* position\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword\n\n'
                                        'Given *<start>* position must be a valid number\n'
                                        ' - First character position is 1\n'
                                        ' - Negative value means to start from last character',
                                        # example
                                        'Following instructions:\n'
                                        '**`[sub:{file:baseName}, 4]`** and **`[sub:{file:baseName}, -6]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`file__name01`** and **`name01`**')),
                           ('[sub:\x01<value>\x01, \x02<start>\x02, \x02<length>\x02]',
                            TokenizerRule.formatDescription(
                                        'Function [STRING]',
                                        # description
                                        'Return substring from *<value>* from *<start>* position for *<length>* characters\n\n'
                                        'Given *<value>* can be:\n'
                                        ' - a string\n'
                                        ' - a keyword\n\n'
                                        'Given *<start>* position must be a valid number\n'
                                        ' - First character position is 1\n'
                                        ' - Negative value means to start from last character\n\n'
                                        'Given *<length>* must be a valid number\n',
                                        # example
                                        'Following instructions:\n'
                                        '**`[sub:{file:baseName}, 4, 4]`** and **`[sub:{file:baseName}, -6, 4]`**\n\n'
                                        'Will return, if *`{file:baseName}`* equals *`my_file__name01`*:\n'
                                        '**`file`** and **`name`**'))
                           ],
                          'f',
                          onInitValue=self.__initTokenAsLowerCase),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_INT,
                          r'\[(?:len):',
                          'Function [NUMBER]',
                          [('[len:\x01<value>\x01]',
                            TokenizerRule.formatDescription(
                                        'Function [NUMBER]',
                                        # description
                                        'Return length (number of characters) for given text *<value>*',
                                        # example
                                        'Following instruction:\n'
                                        '**`[len:"text"]`**\n\n'
                                        'Will return:\n'
                                        '**4**')),
                           ('[len:\x01<value>\x01, \x02<adjustment>\x02]',
                            TokenizerRule.formatDescription(
                                        'Function [NUMBER]',
                                        # description
                                        'Return length (number of characters) for given text *<value>* with adjusted with given *<adjustment>* number',
                                        # example
                                        'Following instruction:\n'
                                        '**`[len:"text", 1]`**\n\n'
                                        'Will return:\n'
                                        '**5**'))
                           ],
                          'f',
                          onInitValue=self.__initTokenAsLowerCase),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.KW,
                          r'\{(?:counter(?::#+)?|image:size(?::(?:width|height)(?::#+)?)?|time(?::(?:hh|mm|ss))?|date(?::(?:yyyy|mm|dd))?|file:date(?::(?:yyyy|mm|dd))?|'
                          r'file:time(?::(?:hh|mm|ss))?|file:ext|file:baseName|file:path|file:format|file:hash:(?:md5|sha1|sha256|sha512))\}',
                          'Keyword',
                          [('{file:baseName}',
                            TokenizerRule.formatDescription(
                                     'Keyword',
                                     # description
                                     'Return file name, without path and without extension')),
                           ('{file:ext}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return file extension, without dot **`.`**')),
                           ('{file:path}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return file path\n\n'
                                      'Please note, path separators are stripped')),
                           ('{file:format}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return file format (can be different than extension)')),
                           ('{file:date}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return file date, with format *`YYYYMMDD`*')),
                           ('{file:date:yyyy}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *year* from file date, with format *`YYYY`*')),
                           ('{file:date:mm}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *month* from file date, with format *`MM`*')),
                           ('{file:date:dd}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *day* from file date, with format *`DD`*')),
                           ('{file:time}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return file time, with format *`HHMMSS`*')),
                           ('{file:time:hh}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *hours* from file time, with format *`HH`*')),
                           ('{file:time:mm}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *minutes* from file time, with format *`MM`*')),
                           ('{file:time:ss}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *seconds* from file time, with format *`SS`*')),
                           ('{file:hash:md5}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return hash for file using MD5 algorithm (32 characters length)')),
                           ('{file:hash:sha1}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return hash for file using SHA-1 algorithm (40 characters length)')),
                           ('{file:hash:sha256}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return hash for file using SHA-256 algorithm (64 characters length)')),
                           ('{file:hash:sha512}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return hash for file using SHA-512 algorithm (128 characters length)')),
                           ('{image:size}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return image size from file, with format *`WxH`*')),
                           ('{image:size:width}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return image width from file')),
                           ('{image:size:width:####}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return image width from file\n\n'
                                      'Use hash character **`#`** to define minimum number of digits')),
                           ('{image:size:height}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return image height from file')),
                           ('{image:size:height:####}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return image height from file\n\n'
                                      'Use hash character **`#`** to define minimum number of digits')),
                           ('{date}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return current sytem date, with format *`YYYYMMDD`*')),
                           ('{date:yyyy}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *year* from current sytem date, with format *`YYYY`*')),
                           ('{date:mm}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *month* from current sytem date, with format *`MM`*')),
                           ('{date:dd}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *day* from current sytem date, with format *`DD`*')),
                           ('{time}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return current sytem time, with format *`HHMMSS`*')),
                           ('{time:hh}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *hours* from current sytem time, with format *`HH`*')),
                           ('{time:mm}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *minutes* from current sytem time, with format *`MM`*')),
                           ('{time:ss}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return *seconds* from current sytem time, with format *`SS`*')),
                           ('{counter}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return a counter value\n\n'
                                      'Counter start from 1, and is incremented if a target file already match the same pattern\n\n'
                                      '*Please note, due to technical reason, use of counter with many files is **slow***')),
                           ('{counter:####}',
                            TokenizerRule.formatDescription(
                                      'Keyword',
                                      # description
                                      'Return a counter value\n\n'
                                      'Counter start from 1, and is incremented if a target file already match the same pattern\n\n'
                                      'Use hash character **`#`** to define minimum counter digits\n\n'
                                      '*Please note, due to technical reason, use of counter with many files is **slow***'))
                           ],
                          'k',
                          onInitValue=self.__initTokenAsLowerCase),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.NUMBER,
                          r'-\d+$|^\d+$',
                          onInitValue=self.__initTokenNumber),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, r',{1}?'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, r'\]{1}?'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.SPACE, r'\s+'),
            TokenizerRule(BCFileManipulateNameLanguageDef.ITokenType.TEXT, r'[{\[,][^{\[\]\}"\'\\\/\s,]*|[^{\[\]\}"\'\\\/\s,]+')
        ])

        self.setStyles(UITheme.DARK_THEME, [
            (BCFileManipulateNameLanguageDef.ITokenType.STRING, '#9ac07c', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.NUMBER, '#c9986a', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, '#e5dd82', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCO_INT, '#e5dd82', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCC, '#e5dd82', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.KW, '#e18890', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, '#c278da', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.SPACE, None, False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.TEXT, '#ffffff', False, False)
        ])
        self.setStyles(UITheme.LIGHT_THEME, [
            (BCFileManipulateNameLanguageDef.ITokenType.STRING, '#9ac07c', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.NUMBER, '#c9986a', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, '#c278da', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.FUNCC, '#c278da', True, False),
            (BCFileManipulateNameLanguageDef.ITokenType.KW, '#e18890', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, '#c278da', False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.SPACE, None, False, False),
            (BCFileManipulateNameLanguageDef.ITokenType.TEXT, '#6aafec', False, False)
        ])

        self.__grammarRules = GrammarRule.setGrammarRules()
        self.__initialiseGrammar()

    def __initialiseGrammar(self):
        """Initialise Grammar for BC File manipulate language

        Grammar is defined from language definition class for convenience
        (centralise everything related to language in the same place)
        """
        GrammarRule('FormulaScript',
                    GrammarRule.OPTION_FIRST,   # the 'FormulaScript' grammar is defined as the first grammar rule
                    GROptional('Formula')
                    )

        GrammarRule('Formula',
                    GrammarRule.OPTION_AST,
                    # --
                    GROneOrMore('FunctionStr',
                                'Keyword',
                                'Text'
                                )
                    )

        GrammarRule('FunctionStr',
                    GROne('Function_Upper',
                          'Function_Lower',
                          'Function_Capitalize',
                          'Function_Camelize',
                          'Function_Replace',
                          'Function_RegEx',
                          'Function_Index',
                          'Function_Sub'
                          )
                    )

        GrammarRule('FunctionInt',
                    GROne('Function_Len')
                    )

        GrammarRule('Function_Upper',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, False, '[upper:'),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Function_Lower',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, False, '[lower:'),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Function_Capitalize',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, False, '[capitalize:'),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Function_Camelize',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, False, '[camelize:'),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Function_Replace',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, False, '[replace:'),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, False),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, False),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Function_RegEx',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, False, '[regex:'),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, False),
                    GROne('String_Expression'),
                    GROptional('Function_OptionalStrParameter'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Function_Index',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, False, '[index:'),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, False),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, False),
                    GROne('Integer_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Function_Sub',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_STR, False, '[sub:'),
                    GROne('String_Expression'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, False),
                    GROne('Integer_Expression'),
                    GROptional('Function_OptionalIntParameter'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Function_Len',
                    GrammarRule.OPTION_AST | GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCO_INT, False, '[len:'),
                    GROne('String_Expression'),
                    GROptional('Function_OptionalIntParameter'),
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.FUNCC, False)
                    )

        GrammarRule('Keyword',
                    GrammarRule.OPTION_AST,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.KW)
                    )

        GrammarRule('Text',
                    GrammarRule.OPTION_AST,
                    # --
                    GROneOrMore('String_Value',
                                'String_Unquoted'
                                )
                    )

        GrammarRule('Function_OptionalStrParameter',
                    GrammarRule.OPTION_AST,  # |GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, False),
                    GROne('String_Expression')
                    )

        GrammarRule('Function_OptionalIntParameter',
                    GrammarRule.OPTION_AST,  # |GrammarRule.OPTION_PARTIAL_MATCH,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR, False),
                    GROne('Integer_Expression')
                    )

        GrammarRule('String_Expression',
                    GrammarRule.OPTION_AST,
                    # --
                    GROneOrMore('Text',
                                'FunctionStr',
                                'Keyword'
                                )
                    )

        GrammarRule('Integer_Expression',
                    GrammarRule.OPTION_AST,
                    # --
                    GROne('Integer_Value',
                          'FunctionInt'
                          )
                    )

        GrammarRule('String_Value',
                    GrammarRule.OPTION_AST,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.STRING)
                    )

        GrammarRule('Integer_Value',
                    GrammarRule.OPTION_AST,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.NUMBER)
                    )

        GrammarRule('String_Unquoted',
                    GrammarRule.OPTION_AST,
                    # --
                    GRToken(BCFileManipulateNameLanguageDef.ITokenType.TEXT)
                    )

    def __initTokenNumber(self, tokenType, value):
        """Convert value for NUMBER token from string to integer or decimal"""
        try:
            # try to convert value as integer
            return int(value)
        except Exception as e:
            # not an integer??
            pass

        try:
            # try to convert value as a decimal value
            return float(value)
        except Exception as e:
            # not a decimal??
            pass

        # normally shouln't occurs... return initial value
        Debug.print('__initTokenNumber ERROR??', tokenType, value)
        return value

    def __initTokenString(self, tokenType, value):
        """Convert value for STRING (remove string delimiters)"""

        if len(value) > 1:
            return value[1:-1]

        return value

    def __initTokenCharacterEscaped(self, tokenType, value):
        """Remove escape character"""
        return value.replace("\\", "")

    def __initTokenAsLowerCase(self, tokenType, value):
        """Return keuword as lowercase"""
        return value.lower()

    def grammarRules(self):
        """Return defined grammar rules"""
        return self.__grammarRules


class BCFileManipulateNameError(Exception):
    """An error occured while interpreting formula"""
    ERROR_LEVEL_STOP = 0
    ERROR_LEVEL_ERROR = 1
    ERROR_LEVEL_CRITICAL = 2

    def __init__(self, message, ast, errorLevel=1):
        super(BCFileManipulateNameError, self).__init__(message)
        self.__ast = ast
        self.__errorLevel = errorLevel

    def ast(self):
        """Return AST from which exception has been raised"""
        return self.__ast

    def errorLevel(self):
        """Return error level for exception"""
        return self.__errorLevel


class BCFileManipulateNameInternalError(BCFileManipulateNameError):
    """An error occured while interprrting formula

    These exception are more related to an internal problem (initialisation, internal bug, ...)
    than a problem from formula
    """
    def __init__(self, message, ast, errorLevel=2):
        super(BCFileManipulateNameError, self).__init__(f"Internal error: <<{message}>>", ast, errorLevel)


class BCFileManipulateNameErrorDefinition(object):
    """A returned error from parser"""

    def __init__(self, token, grammar, message):
        """initialise error"""
        self.__token = token
        self.__grammar = grammar
        self.__message = message

    def token(self):
        """Return token from which error has occured"""
        return self.__token

    def grammar(self):
        """Return grammar rule from which error has occured"""
        return self.__grammar

    def message(self):
        """return textual message about error"""
        return self.__message


class BCFileManipulateName(object):

    __PARSER = None
    __LANGUAGEDEF = None

    @staticmethod
    def init():
        """Initialise BCFileManipulateName static class"""
        # initialise language definition + grammar
        BCFileManipulateName.__LANGUAGEDEF = BCFileManipulateNameLanguageDef()

        # initialise Parser
        BCFileManipulateName.__PARSER = Parser(BCFileManipulateName.__LANGUAGEDEF.tokenizer(), BCFileManipulateName.__LANGUAGEDEF.grammarRules())
        # ignore useless tokens for interpreation
        BCFileManipulateName.__PARSER.setIgnoredTokens([BCFileManipulateNameLanguageDef.ITokenType.SPACE])

    @staticmethod
    def parseFileNameKw(file, pattern=None, targetPath=None):
        """Return a file name build from given file and pattern

        If pattern equals "<None>"
        => return empty string

        Otherwise, the following markup can be used:
            "{file:path}"       The file path name
            "{file:baseName}"   The file base name without extension
            "{file:name}"       The file path+base name without extension
            "{file:ext}"        The file extension
            "{file:format}"     The file format

            "{file:date}"            The current system date (yyyymmdd)
            "{file:date:yyyy}"       The current system year
            "{file:date:mm}"         The current system month
            "{file:date:dd}"         The current system day

            "{file:time}"            The current system time (hhmmss)
            "{file:time:hh}"         The current system hour (00-24)
            "{file:time:mm}"         The current system minutes
            "{file:time:ss}"         The current system seconds

            "{file:hash:md5}"        File hash - MD5
            "{file:hash:sha1}"       File hash - SHA-1
            "{file:hash:sha256}"     File hash - SHA-256
            "{file:hash:sha512}"     File hash - SHA-512

            "{date}"            The current system date (yyyymmdd)
            "{date:yyyy}"       The current system year
            "{date:mm}"         The current system month
            "{date:dd}"         The current system day

            "{time}"            The current system time (hhmmss)
            "{time:hh}"         The current system hour (00-24)
            "{time:mm}"         The current system minutes
            "{time:ss}"         The current system seconds

            "{image:size}"            The current image size (widthxheight)
            "{image:size:width}"      The current image width
            "{image:size:width:####}"      The current image width
            "{image:size:height}"     The current image height
            "{image:size:height:####}"     The current image height

            "{counter}"         A counter to file name
            "{counter:####}"    A counter to file name
        """
        if pattern is None:
            return ''

        if not isinstance(file, BCBaseFile):
            raise EInvalidType('Given `file` must be a <BCBaseFile>')

        if not isinstance(pattern, str):
            raise EInvalidType('Given `pattenr` must be a <str>')

        if pattern.strip() == '' or re.search(r'(?i)<none>', pattern):
            return ''

        currentDateTime = time.time()
        fileName = pattern

        if targetPath is None:
            targetPath = file.path()

        targetPath = targetPath.replace('\\', r'\\')

        isDir = False
        if file.format() != BCFileManagedFormat.DIRECTORY:
            baseFileNameWithoutExt = os.path.splitext(file.name())[0]
            nameFileNameWithoutExt = os.path.splitext(file.fullPathName())[0]

            if file.extension(False) == '' and file.name()[-1] != '.':
                replaceExtExpr = r"(?i)\.\{file:ext\}"
            else:
                replaceExtExpr = r"(?i)\{file:ext\}"

            fileName = re.sub(replaceExtExpr,      file.extension(False),                        fileName)
            fileName = re.sub(r"(?i)\{image:size\}",           f"{file.getProperty(BCFileProperty.IMAGE_WIDTH)}x{file.getProperty(BCFileProperty.IMAGE_HEIGHT)}", fileName)
            fileName = re.sub(r"(?i)\{image:size:width\}",     f"{file.getProperty(BCFileProperty.IMAGE_WIDTH)}", fileName)
            fileName = re.sub(r"(?i)\{image:size:height\}",    f"{file.getProperty(BCFileProperty.IMAGE_HEIGHT)}", fileName)

            if kw := re.search(r"(?i)\{image:size:width:(#+)\}", fileName):
                replaceHash = kw.groups()[0]
                fileName = re.sub(f"(?i){{image:size:width:{replaceHash}}}", f"{file.getProperty(BCFileProperty.IMAGE_WIDTH):0{len(replaceHash)}}", fileName)

            if kw := re.search(r"(?i)\{image:size:height:(#+)\}", fileName):
                replaceHash = kw.groups()[0]
                fileName = re.sub(f"(?i){{image:size:height:{replaceHash}}}", f"{file.getProperty(BCFileProperty.IMAGE_HEIGHT):0{len(replaceHash)}}", fileName)
        else:
            isDir = True
            baseFileNameWithoutExt = file.name()
            nameFileNameWithoutExt = file.fullPathName()
            replaceExtExpr = None

            fileName = re.sub(r"(?i)\.\{file:ext\}",     "", fileName)
            fileName = re.sub(r"(?i)\{file:ext\}",       "", fileName)
            fileName = re.sub(r"(?i)\{image:size\}",           "0x0", fileName)
            fileName = re.sub(r"(?i)\{image:size:width\}",     "0", fileName)
            fileName = re.sub(r"(?i)\{image:size:height\}",    "0", fileName)

        baseFileNameWithoutExt = baseFileNameWithoutExt.replace('\\', r'\\')
        nameFileNameWithoutExt = nameFileNameWithoutExt.replace('\\', r'\\')

        fileName = re.sub(r"(?i)\{file:path\}", targetPath,                                   fileName)
        fileName = re.sub(r"(?i)\{file:baseName\}", baseFileNameWithoutExt,                   fileName)
        fileName = re.sub(r"(?i)\{file:name\}", nameFileNameWithoutExt,     fileName)
        fileName = re.sub(r"(?i)\{file:format\}", file.format(),     fileName)

        if re.match(r"(?i)\{file:hash:md5\}", fileName):
            fileName = re.sub(r"(?i)\{file:hash:md5\}",      file.hash('md5'),           fileName)
        if re.match(r"(?i)\{file:hash:sha1\}", fileName):
            fileName = re.sub(r"(?i)\{file:hash:sha1\}",      file.hash('sha1'),           fileName)
        if re.match(r"(?i)\{file:hash:sha256\}", fileName):
            fileName = re.sub(r"(?i)\{file:hash:sha256\}",      file.hash('sha256'),           fileName)
        if re.match(r"(?i)\{file:hash:sha512\}", fileName):
            fileName = re.sub(r"(?i)\{file:hash:sha512\}",      file.hash('sha512'),           fileName)

        fileName = re.sub(r"(?i)\{file:date\}",      tsToStr(file.lastModificationDateTime(), '%Y%m%d'),           fileName)
        fileName = re.sub(r"(?i)\{file:date:yyyy\}", tsToStr(file.lastModificationDateTime(), '%Y'),               fileName)
        fileName = re.sub(r"(?i)\{file:date:mm\}",   tsToStr(file.lastModificationDateTime(), '%m'),               fileName)
        fileName = re.sub(r"(?i)\{file:date:dd\}",   tsToStr(file.lastModificationDateTime(), '%d'),               fileName)

        fileName = re.sub(r"(?i)\{file:time\}",      tsToStr(file.lastModificationDateTime(), '%H%M%S'),           fileName)
        fileName = re.sub(r"(?i)\{file:time:hh\}",   tsToStr(file.lastModificationDateTime(), '%H'),               fileName)
        fileName = re.sub(r"(?i)\{file:time:mm\}",   tsToStr(file.lastModificationDateTime(), '%M'),               fileName)
        fileName = re.sub(r"(?i)\{file:time:ss\}",   tsToStr(file.lastModificationDateTime(), '%S'),               fileName)

        fileName = re.sub(r"(?i)\{date\}",      tsToStr(currentDateTime, '%Y%m%d'),           fileName)
        fileName = re.sub(r"(?i)\{date:yyyy\}", tsToStr(currentDateTime, '%Y'),               fileName)
        fileName = re.sub(r"(?i)\{date:mm\}",   tsToStr(currentDateTime, '%m'),               fileName)
        fileName = re.sub(r"(?i)\{date:dd\}",   tsToStr(currentDateTime, '%d'),               fileName)

        fileName = re.sub(r"(?i)\{time\}",      tsToStr(currentDateTime, '%H%M%S'),           fileName)
        fileName = re.sub(r"(?i)\{time:hh\}",   tsToStr(currentDateTime, '%H'),               fileName)
        fileName = re.sub(r"(?i)\{time:mm\}",   tsToStr(currentDateTime, '%M'),               fileName)
        fileName = re.sub(r"(?i)\{time:ss\}",   tsToStr(currentDateTime, '%S'),               fileName)

        if resultCounter := re.search(r"(?i)\{counter(?::(#+))?\}", fileName):
            regEx = re.sub(r"(?i)\{file:path\}", targetPath,                        pattern)

            regEx = re.sub(r"(?i)\{file:baseName\}", baseFileNameWithoutExt,        regEx)
            regEx = re.sub(r"(?i)\{file:name\}", nameFileNameWithoutExt,            regEx)
            if replaceExtExpr is not None:
                regEx = re.sub(replaceExtExpr,  re.escape(file.extension(False)),             regEx)
            else:
                regEx = re.sub(r"(?i)\.\{file:ext\}",     "", regEx)
                regEx = re.sub(r"(?i)\{file:ext\}",       "", regEx)

            regEx = re.sub(r"(?i)\{file:format\}", re.escape(file.format()),     regEx)

            regEx = re.sub(r"(?i)\{file:hash:md5\}",      r'[a-z0-9]{32}',           regEx)
            regEx = re.sub(r"(?i)\{file:hash:sha1\}",     r'[a-z0-9]{40}',           regEx)
            regEx = re.sub(r"(?i)\{file:hash:sha256\}",   r'[a-z0-9]{64}',           regEx)
            regEx = re.sub(r"(?i)\{file:hash:sha512\}",   r'[a-z0-9]{128}',          regEx)

            regEx = re.sub(r"(?i)\{file:date\}",      r'\\d{8}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:date:yyyy\}", r'\\d{4}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:date:mm\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:date:dd\}",   r'\\d{2}',                                    regEx)

            regEx = re.sub(r"(?i)\{file:time\}",      r'\\d{6}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:time:hh\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:time:mm\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{file:time:ss\}",   r'\\d{2}',                                    regEx)

            regEx = re.sub(r"(?i)\{date\}",      r'\\d{8}',                                    regEx)
            regEx = re.sub(r"(?i)\{date:yyyy\}", r'\\d{4}',                                    regEx)
            regEx = re.sub(r"(?i)\{date:mm\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{date:dd\}",   r'\\d{2}',                                    regEx)

            regEx = re.sub(r"(?i)\{time\}",      r'\\d{6}',                                    regEx)
            regEx = re.sub(r"(?i)\{time:hh\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{time:mm\}",   r'\\d{2}',                                    regEx)
            regEx = re.sub(r"(?i)\{time:ss\}",   r'\\d{2}',                                    regEx)

            regEx = re.sub(r"(?i)\{image:size\}",        r'\\d+x\\d+',                                regEx)
            regEx = re.sub(r"(?i)\{image:size:width\}",  r'\\d+',                                     regEx)
            regEx = re.sub(r"(?i)\{image:size:height\}", r'\\d+',                                     regEx)

            regEx = re.sub(r"(?i)\{counter\}", r'(\\d+)',                                             regEx)

            for replaceHash in resultCounter.groups():
                if replaceHash is not None:
                    regEx = re.sub(fr"\{{counter:{replaceHash}\}}", f"(\\\\d{{{len(replaceHash)},}})", regEx)

            regEx = regEx.replace(".", r'\.')

            regEx = f"^{regEx}$"

            if not regExIsValid(regEx):
                return fileName

            # a counter is defined, need to determinate counter value
            if isDir:
                fileList = [int(rr.groups()[0])
                            for foundFile in
                            os.listdir(targetPath) if os.path.isdir(os.path.join(targetPath, foundFile)) and (rr:=re.search(regEx, foundFile))]
            else:
                fileList = [int(rr.groups()[0])
                            for foundFile in
                            os.listdir(targetPath) if os.path.isfile(os.path.join(targetPath, foundFile)) and (rr:=re.search(regEx, foundFile))]
            if len(fileList) == 0:
                nbFiles = 1
            else:
                nbFiles = max(fileList) + 1

            fileName = re.sub(r"(?i)\{counter\}", f"{nbFiles}",   fileName)

            for replaceHash in resultCounter.groups():
                if replaceHash is not None:
                    fileName = re.sub(fr"\{{counter:{replaceHash}\}}", f"{nbFiles:0{len(replaceHash)}}", fileName)

        return fileName

    @staticmethod
    def calculateFileName(file, pattern=None, keepInvalidCharacters=False, targetPath=None, checkOnly=False, tokenizer=None, kwCallBack=None):
        r"""Process file name manipulation

        Given `file` is a BCBaseFile from which properties file name will be built

        Given `pattern` is a string (keywords+functions+...) that define new file name

        If given `keepInvalidCharacters` is False, all invalid characters for a file name are removed
        - For windows ==>   * \ / < > ? : " |
        - For Linux   ==>   /
        Other OS are processed like Linux

        If `targetPath` is provided, given path will override `file` path

        If `checkOnly`, {counter}} computation are not applied (faster but returned file name could not match real final file name)

        Following keywords are supported:
            "{file:path}"               The file path name
            "{file:baseName}"           The file base name without extension
            "{file:ext}"                The file extension
            "{file:format}"             The file format

            "{file:date}"               The current system date (yyyymmdd)
            "{file:date:yyyy}"          The current system year
            "{file:date:mm}"            The current system month
            "{file:date:dd}"            The current system day

            "{file:time}"               The current system time (hhmmss)
            "{file:time:hh}"            The current system hour (00-24)
            "{file:time:mm}"            The current system minutes
            "{file:time:ss}"            The current system seconds

            "{file:hash:md5}"           File hash - MD5
            "{file:hash:sha1}"          File hash - SHA-1
            "{file:hash:sha256}"        File hash - SHA-256
            "{file:hash:sha512}"        File hash - SHA-512

            "{date}"                    The current system date (yyyymmdd)
            "{date:yyyy}"               The current system year
            "{date:mm}"                 The current system month
            "{date:dd}"                 The current system day

            "{time}"                    The current system time (hhmmss)
            "{time:hh}"                 The current system hour (00-24)
            "{time:mm}"                 The current system minutes
            "{time:ss}"                 The current system seconds

            "{image:size}"              The current image size (widthxheight)
            "{image:size:width}"        The current image width
            "{image:size:width:####}"   The current image width
            "{image:size:height}"       The current image height
            "{image:size:height:####}"  The current image height

            "{counter}"         A counter to file name
            "{counter:####}"    A counter to file name

        Following functions are supporter:
            return STRING:
                upper(value)
                lower(value)
                capitalize(value)
                camelize(values)
                replace(value, regex, replaced)
                sub(value, start[, length])
                regex(value, find[, replace])
                index(value, separator, index)
            return NUMBER
                len(value[, offset])

        Example:
            pattern="[lower:[sub:{file:baseName},1,4]]-[sub:{file:baseName},-4].[upper:{file:ext}]"

        Return a tuple:
            (value, error)

        If any error occurs, returned value is None
        Otherwise returned error is None
        """
        def evaluate(item):
            """Evaluate item value

            If item is a Token, return Token value
            If item is an AST, return AST evaluation
            """
            if isinstance(item, Token):
                # return token value
                return item.value()
            elif isinstance(item, ASTItem):
                return executeAst(item)
            else:
                # a str, int, float, .... provided directly
                return item

        def returnKeyword(keyword):
            """Return value from keyword"""
            if isinstance(file, BCFile):
                # a file (BCFile)
                if keyword == "{file:path}":
                    if targetPath is None:
                        return file.path()
                    elif isinstance(targetPath, str):
                        return targetPath.replace('\\', r'\\')
                elif keyword == "{file:basename}":
                    return file.baseName()
                elif keyword == "{file:ext}":
                    return file.extension(False)
                elif keyword == "{file:format}":
                    return file.format()
                elif keyword == "{file:date}":
                    return tsToStr(file.lastModificationDateTime(), 'd')
                elif keyword == "{file:date:yyyy}":
                    return tsToStr(file.lastModificationDateTime(), '%Y')
                elif keyword == "{file:date:mm}":
                    return tsToStr(file.lastModificationDateTime(), '%m')
                elif keyword == "{file:date:dd}":
                    return tsToStr(file.lastModificationDateTime(), '%d')
                elif keyword == "{file:time}":
                    return tsToStr(file.lastModificationDateTime(), 't')
                elif keyword == "{file:time:hh}":
                    return tsToStr(file.lastModificationDateTime(), '%H')
                elif keyword == "{file:time:mm}":
                    return tsToStr(file.lastModificationDateTime(), '%M')
                elif keyword == "{file:time:ss}":
                    return tsToStr(file.lastModificationDateTime(), '%S')
                elif keyword == "{file:hash:md5}":
                    return file.hash('md5')
                elif keyword == "{file:hash:sha1}":
                    return file.hash('sha1')
                elif keyword == "{file:hash:sha256}":
                    return file.hash('sha256')
                elif keyword == "{file:hash:sha512}":
                    return file.hash('sha512')
                elif keyword == "{date}":
                    return tsToStr(currentDateTime, 'd')
                elif keyword == "{date:yyyy}":
                    return tsToStr(currentDateTime, '%Y')
                elif keyword == "{date:mm}":
                    return tsToStr(currentDateTime, '%m')
                elif keyword == "{date:dd}":
                    return tsToStr(currentDateTime, '%d')
                elif keyword == "{time}":
                    return tsToStr(currentDateTime, 't')
                elif keyword == "{time:hh}":
                    return tsToStr(currentDateTime, '%H')
                elif keyword == "{time:mm}":
                    return tsToStr(currentDateTime, '%M')
                elif keyword == "{time:ss}":
                    return tsToStr(currentDateTime, '%S')
                elif keyword == "{image:size}":
                    return f"{file.getProperty(BCFileProperty.IMAGE_WIDTH)}x{file.getProperty(BCFileProperty.IMAGE_HEIGHT)}"
                elif keyword == "{image:size:width}":
                    return file.getProperty(BCFileProperty.IMAGE_WIDTH)
                elif keyword == "{image:size:height}":
                    return file.getProperty(BCFileProperty.IMAGE_HEIGHT)
                elif kw := re.search(r"\{image:size:width:(#+)\}", keyword):
                    return f"{file.getProperty(BCFileProperty.IMAGE_WIDTH):0{len(kw.groups()[0])}}"
                elif kw := re.search(r"\{image:size:height:(#+)\}", keyword):
                    return f"{file.getProperty(BCFileProperty.IMAGE_HEIGHT):0{len(kw.groups()[0])}}"
                elif kw := re.search(r"\{counter(:#+)?\}", keyword):
                    if checkOnly:
                        if kw.groups()[0] is None:
                            return "1"
                        else:
                            return f"{1:0{len(kw.groups()[0])}}"
                    else:
                        return keyword
            elif isinstance(file, BCDirectory):
                if keyword == "{file:path}":
                    if targetPath is None:
                        return file.path()
                    elif isinstance(targetPath, str):
                        return targetPath.replace('\\', r'\\')
                elif keyword == "{file:baseName}":
                    return file.baseName()
                elif keyword == "{date}":
                    return tsToStr(currentDateTime, 'd')
                elif keyword == "{date:yyyy}":
                    return tsToStr(currentDateTime, '%Y')
                elif keyword == "{date:mm}":
                    return tsToStr(currentDateTime, '%m')
                elif keyword == "{date:dd}":
                    return tsToStr(currentDateTime, '%d')
                elif keyword == "{time}":
                    return tsToStr(currentDateTime, 't')
                elif keyword == "{time:hh}":
                    return tsToStr(currentDateTime, '%H')
                elif keyword == "{time:mm}":
                    return tsToStr(currentDateTime, '%M')
                elif keyword == "{time:ss}":
                    return tsToStr(currentDateTime, '%S')
                elif kw := re.search(r"\{counter(:#+)?\}", keyword):
                    if checkOnly:
                        if kw.groups()[0] is None:
                            return "1"
                        else:
                            return f"{1:0{len(kw.groups()[0])}}"
                    else:
                        return keyword
            elif isinstance(file, BCMissingFile):
                if keyword == "{file:path}":
                    return file.path()
                elif keyword == "{file:baseName}":
                    return file.baseName()
                elif keyword == "{file:ext}":
                    return file.extension(False)
            return ""

        def returnStringExpression(nodes):
            # --define final size of array, a little bit "faster" than append data
            returned = ['']*len(nodes)
            for index, node in enumerate(nodes):
                returned[index] = executeAst(node)
            return "".join(returned)

        def returnFunctionUpper(nodes):
            return evaluate(nodes[0]).upper()

        def returnFunctionLower(nodes):
            return evaluate(nodes[0]).lower()

        def returnFunctionCapitalize(nodes):
            return evaluate(nodes[0]).capitalize()

        def returnFunctionCamelize(nodes):
            return evaluate(nodes[0]).title()

        def returnFunctionReplace(nodes):
            # 3 nodes provided
            # -[0] value
            # -[1] search string
            # -[2] replace string
            returned = evaluate(nodes[0])
            searchValue = evaluate(nodes[1])
            if searchValue == '':
                return returned
            return returned.replace(searchValue, evaluate(nodes[2]))

        def returnFunctionRegEx(nodes):
            # 2-3 nodes provided
            # -[0] value
            # -[1] regex pattern string
            # -[2] replace string (if provided)
            returned = evaluate(nodes[0])
            regExPattern = evaluate(nodes[1])

            if regExPattern == '':
                return returned

            if len(nodes) == 2:
                # return found value(s)
                try:
                    if result := re.findall(regExPattern, returned, re.IGNORECASE):
                        returned = ''.join([value for value in result if value is not None])
                except e as exception:
                    pass
            else:
                try:
                    returned = re.sub(regExPattern, re.sub(r"\$", "\\\\", evaluate(nodes[2]), flags=re.IGNORECASE), returned, flags=re.IGNORECASE)
                except e as exception:
                    pass

            return returned

        def returnFunctionIndex(nodes):
            # 3 nodes provided
            # -[0] value
            # -[1] separator
            # -[2] index
            returned = evaluate(nodes[0])
            separator = evaluate(nodes[1])
            index = evaluate(nodes[2])

            if index == 0 or separator == '':
                # index start from 1 to NbIndex
                # if outside range, return initial value
                return returned

            if index > 0:
                # in python, index start from 0
                index -= 1

            splitted = returned.split(separator)
            try:
                return splitted[index]
            except e as exception:
                # index out of range: return empty value
                return ""

        def returnFunctionSub(nodes):
            # 2-3 nodes provided
            # -[0] value
            # -[1] start (int)
            # -[2] length (int, if provided)
            returned = evaluate(nodes[0])
            start = evaluate(nodes[1])

            if start == 0:
                # index start from 1 to NbIndex
                # if outside range, return initial value
                return returned

            if start > 0:
                # in python, index start from 0
                start -= 1

            if len(nodes) == 2:
                # return from start to end
                try:
                    return returned[start:]
                except e as exception:
                    return ""
            else:
                # from start, to start+length
                length = evaluate(nodes[2])
                try:
                    return returned[start:start+length]
                except e as exception:
                    return ""

        def returnFunctionLen(nodes):
            # 1-2 nodes provided
            # -[0] value
            # -[1] offset
            returned = evaluate(nodes[0])

            if len(nodes) == 1:
                # return from start to end
                return len(returned)
            else:
                offset = evaluate(nodes[1])
                return len(returned)+offset

        def executeAst(astNode):
            """Execute current given AST"""

            astId = astNode.id()

            if astNode.status() == ASTStatus.MATCH:
                if astId == 'Keyword':
                    return returnKeyword(astNode.nodes()[0].value())
                # ------------------------------------------------------------------
                elif astId in ('Text', 'String_Expression'):
                    return returnStringExpression(astNode.nodes())
                elif astId in ('String_Value', 'Integer_Value', 'String_Unquoted'):
                    return astNode.nodes()[0].value()
                elif astId == 'Integer_Expression':
                    return evaluate(astNode.nodes()[0])
                # ------------------------------------------------------------------
                elif astId == 'Function_Upper':
                    return returnFunctionUpper(astNode.nodes())
                elif astId == 'Function_Lower':
                    return returnFunctionLower(astNode.nodes())
                elif astId == 'Function_Capitalize':
                    return returnFunctionCapitalize(astNode.nodes())
                elif astId == 'Function_Camelize':
                    return returnFunctionCamelize(astNode.nodes())
                elif astId == 'Function_Replace':
                    return returnFunctionReplace(astNode.nodes())
                elif astId == 'Function_RegEx':
                    return returnFunctionRegEx(astNode.nodes())
                elif astId == 'Function_Index':
                    return returnFunctionIndex(astNode.nodes())
                elif astId == 'Function_Sub':
                    return returnFunctionSub(astNode.nodes())
                elif astId == 'Function_Len':
                    return returnFunctionLen(astNode.nodes())
                # ------------------------------------------------------------------
                elif astId in ('Function_OptionalStrParameter', 'Function_OptionalIntParameter'):
                    return evaluate(astNode.nodes()[0])
                # ------------------------------------------------------------------
                elif astId == 'Formula':
                    # formula: concatenate all returned value in string to build final filename
                    # --define final size of array, a little bit "faster" than append data
                    returned = ['']*astNode.countNodes()
                    for index, astChildNode in enumerate(astNode.nodes()):
                        # execute all instructions from current script block
                        returned[index] = executeAst(astChildNode)
                    return "".join(returned)
            else:
                return ""

            return "(not yet implemented!?)"

        def manageError(ast):
            """Parser has returned an error

            Try to analyse case and return a readable and useable result to provide to user
            """
            def getFunction(ast, functionName):
                """Search for function Id in error"""
                if isinstance(ast, Token):
                    return functionName

                if isinstance(ast.id(), str) and ast.status() != ASTStatus.MATCH:
                    if r := re.match("^Function_.*", ast.id()):
                        functionName = ast.id()

                for astChild in ast.nodes():
                    functionName = getFunction(astChild, functionName)

                return functionName

            def getTextualGrRule(rule):
                """return textual value for given GrRule"""
                if rule.id() in ("Integer_Expression", "Function_OptionalIntParameter"):
                    return i18n("integer value")
                elif rule.id() in ("String_Expression", "Function_OptionalStrParameter"):
                    return i18n("string value")
                return rule.id()

            def getGrOne(grammarRule):
                """Return textual explanation for GrOne grammar rule"""
                if len(grammarRule.grammarList()) == 1:
                    expected = getTextualGrRule(grammarRule.grammarList()[0])
                    return i18n(f"one <i>{expected }</i> is expected")
                else:
                    return i18n(f"one of following value is expected: <i>"+"</i>, <i>".join([getTextualGrRule(rule) for rule in grammarRule.grammarList()])+"</i>")

            def getGrOptional(grammarRule):
                """Return textual explanation for GrOptional grammar rule"""
                if len(grammarRule.grammarList()) == 1:
                    expected = getTextualGrRule(grammarRule.grammarList()[0])
                    return i18n(f"one <i>{expected }</i> is expected")
                else:
                    return i18n(f"one of following value is expected: <i>"+"</i>, <i>".join([getTextualGrRule(rule) for rule in grammarRule.grammarList()])+"</i>")

            if len(BCFileManipulateName.__PARSER.errors()) > 0:
                message = ['<b>Invalid syntax</b>']

                # only first error (ParserError) is interesting here
                error = BCFileManipulateName.__PARSER.errors()[0]

                # get token to define error position
                token = error.errorToken()

                # get GRObject expected
                grammarRule = error.errorGrammarRule()

                # define default values decalration
                grammarCurrentIndex = None
                grammarCurrentRule = None
                grammarPreviousIndex = None
                grammarPreviousRule = None
                functionName = ""

                # check current grammar rule/token status
                if isinstance(grammarRule, GRRule):
                    # if it's a GRRule, everything is available directly
                    functionName = grammarRule.id()
                    grammarCurrentIndex = grammarRule.currentCheckedGrammarIndex()
                    grammarCurrentRule = grammarRule.currentCheckedGrammar()

                    # get previous rule reference, needed (later) to check if previous is optional or not
                    grammarPreviousIndex = grammarCurrentIndex-1
                    if grammarPreviousIndex >= 0:
                        grammarPreviousRule = grammarRule.grammarList()[grammarPreviousIndex]
                    else:
                        grammarPreviousIndex = None
                        grammarPreviousRule = None

                    if isinstance(grammarCurrentRule, GRToken):
                        grammarCurrentRule = GRToken(grammarCurrentRule.tokenType())
                elif grammarRule is None or isinstance(grammarRule, GRToken):
                    if isinstance(grammarRule, GRToken):
                        grammarCurrentRule = grammarRule
                    else:
                        # a token??
                        grammarCurrentRule = GRToken(token.type())

                    if grammarCurrentRule.tokenType() in (BCFileManipulateNameLanguageDef.ITokenType.FUNCC,
                                                          BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR):
                        # these token must be quoted
                        # other token are interpreted
                        message.append(i18n(f'Language delimiters must be quoted: <b>"{token.text()}"</b>'))
                        return BCFileManipulateNameErrorDefinition(token, grammarRule, "<br>".join(message))
                    elif grammarCurrentRule.tokenType() == BCFileManipulateNameLanguageDef.ITokenType.NUMBER:
                        # these token must be quoted
                        # other token are interpreted
                        message.append(i18n(f'Number values in file name must be quoted: <b>"{token.text()}"</b>'))
                        return BCFileManipulateNameErrorDefinition(token, grammarRule, "<br>".join(message))
                else:
                    # not a normal case..?
                    print("--E1-- NEED TO CHECK, NOT A NORMAL CASE: ", grammarRule)
                    message.append("Unknown error case...")
                    return BCFileManipulateNameErrorDefinition(token, grammarRule, "<br>".join(message))

                if r := re.match("Function_(.*)", functionName):
                    message.append(i18n(f'<i>Function <b>{r.groups()[0].lower()}</b></i>'))

                previousExpected = ""
                if isinstance(grammarPreviousRule, (GROptional, GRNoneOrMore)) and grammarPreviousRule.matchCount() == 0:
                    # previous rule was optional
                    # then it's 'xxxx' or 'previous rule' expected
                    previousExpected = ' or ' + getGrOptional(grammarPreviousRule)

                if isinstance(grammarCurrentRule, GRToken):
                    if grammarCurrentRule.tokenType() == BCFileManipulateNameLanguageDef.ITokenType.SEPARATOR:
                        if previousExpected == '':
                            message.append(i18n(f"A function parameter separator '<b>,</b>' is expected"))
                        else:
                            message.append(i18n(f"A function parameter separator '<b>,</b>'{previousExpected}"))
                    elif grammarCurrentRule.tokenType() == BCFileManipulateNameLanguageDef.ITokenType.FUNCC:
                        if previousExpected == '':
                            message.append(i18n(f"A function closing '<b>]</b>' is expected"))
                        else:
                            message.append(i18n(f"A function closing '<b>]</b>'{previousExpected}"))
                    else:
                        message.append("token? "+str(grammarCurrentRule.tokenType()))
                elif isinstance(grammarCurrentRule, GROne):
                    message.append(getGrOptional(grammarCurrentRule))
                else:
                    print("--E2-- NEED TO CHECK, NOT A NORMAL CASE: ", grammarRule, grammarCurrentRule)
                    message.append("grammar rule is None?")

                return BCFileManipulateNameErrorDefinition(token, grammarRule, "<br>".join(message))

            return None

        currentDateTime = time.time()
        hasCounter = False

        ast = BCFileManipulateName.__PARSER.parse(pattern)

        if ast.status() != ASTStatus.MATCH:
            return (None, manageError(ast))
        elif ast.id() == ASTSpecialItemType.ROOT and ast.countNodes() > 0:
            try:
                returnedFileName = executeAst(ast.nodes()[0])

                if not keepInvalidCharacters:
                    # based on list from: https://en.wikipedia.org/wiki/Filename
                    # +tested file creation from Windows Explorer (provide list of unauthorized characters)
                    if sys.platform == 'win32':
                        returnedFileName = re.sub(r'[*\/<>?:"|]', '', returnedFileName)
                    else:
                        returnedFileName = re.sub(r'[/]', '', returnedFileName)

                if counters := re.findall(r"(\{counter(?::(#+))?\})", returnedFileName, re.I):
                    # a counter is defined, need to determinate counter value
                    # hasCounter value define number of hash
                    if targetPath is None:
                        targetPath = file.path()
                    elif isinstance(targetPath, str):
                        targetPath = targetPath.replace('\\', r'\\')

                    # build regular expression to replace counter values with \d+
                    # !!!do not use re.escape() here!!!
                    regEx = re.sub(r'([\{\[\}\]\.])', r'\\\1', returnedFileName)

                    testFileName = returnedFileName
                    for replaceHash in counters:
                        nbHash = len(replaceHash[1])
                        if nbHash == 0:
                            regEx = re.sub(r'\\\{counter\\\}', r'(\\d+)', regEx)
                            testFileName = re.sub(r"\{counter\}", "1", testFileName)
                        else:
                            regEx = re.sub(rf'\\\{{counter:{replaceHash[1]}\\\}}', rf'(\\d{{{nbHash}}})', regEx)
                            testFileName = re.sub(rf"\{{counter:{replaceHash[1]}\}}", f"{1:0{nbHash}}", testFileName)

                    if os.path.exists(os.path.join(targetPath, testFileName)):
                        # file already exists, need to increment counter
                        # search for all files matching file pattern
                        if isinstance(file, BCDirectory):
                            fileList = [int(rr.groups()[0])
                                        for foundFile in
                                        os.listdir(targetPath) if os.path.isdir(os.path.join(targetPath, foundFile)) and (rr:=re.search(regEx, foundFile))]
                        else:
                            fileList = [int(rr.groups()[0])
                                        for foundFile in
                                        os.listdir(targetPath) if os.path.isfile(os.path.join(targetPath, foundFile)) and (rr:=re.search(regEx, foundFile))]

                        if len(fileList) == 0:
                            nbFiles = 1
                        else:
                            nbFiles = max(fileList) + 1

                        # define final name
                        for replaceHash in counters:
                            nbHash = len(replaceHash[1])
                            if nbHash == 0:
                                returnedFileName = re.sub(r"\{counter\}", f"{nbFiles}", returnedFileName)
                            else:
                                returnedFileName = re.sub(rf"\{{counter:{replaceHash[1]}\}}", f"{nbFiles:0{nbHash}}", returnedFileName)
                    else:
                        # file doesn't exist and file name with {counter} value equals 1 can be used
                        returnedFileName = testFileName
                return (returnedFileName, None)
            except BCFileManipulateNameError as e:
                # need to review this...
                if e.errorLevel() == BCFileManipulateNameError.ERROR_LEVEL_STOP:
                    raise BCFileManipulateNameError(f"{str(e)}", e.ast(), BCFileManipulateNameError.ERROR_LEVEL_STOP)
                raise e
            except Exception as e:
                # need to review this...
                raise e

        return ("", None)

    @staticmethod
    def parser():
        """Return parser"""
        return BCFileManipulateName.__PARSER

    @staticmethod
    def languageDefinition():
        """Return parser"""
        return BCFileManipulateName.__LANGUAGEDEF


BCFileManipulateName.init()
