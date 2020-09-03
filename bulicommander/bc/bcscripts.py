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


from .bcutils import (
        Debug,
        Stopwatch,

        strToBytes,
        strToTs,
        tsToStr
    )

from .bctokenizer import (
        BCTokenType,
        BCTokenizer,
        BCTokenizerRule
    )



class BCFileQueryTokenType(BCTokenType):
    COMMENT = 'comment'

    SEPARATOR = 'separator'
    SPACE = 'space'
    NEWLINE = 'new line'

    STRING = 'string'
    NUMBER = 'number'
    DATE = 'date'
    DATETIME = 'datetime'

    OPEN_RANGE = 'open_range'
    CLOSE_RANGE = 'close_range'

    OPEN_LIST = 'open_list'
    CLOSE_LIST = 'close_list'

    NUMBER_SIZE = 'number size'

    FILE_PROPERTY = 'file property'
    FILE_PROPERTY_NAME = 'file name'
    FILE_PROPERTY_SIZE = 'file size'
    FILE_PROPERTY_DATE = 'file date'
    FILE_PROPERTY_FORMAT = 'file format'

    IMAGE_PROPERTY_WIDTH = 'image width'
    IMAGE_PROPERTY_HEIGHT = 'image height'

    KEYWORD_SEARCH = 'kw search'
    KEYWORD_FROM = 'kw from'
    KEYWORD_DIRECTORY = 'kw directory'
    KEYWORD_RECURSIVELY = 'kw recursively'
    KEYWORD_MATCHING_RULE = 'kw matching'
    KEYWORD_MATCHING_RULE_OR = 'kw rule'

    OPERATOR_MATCH = 'op match'
    OPERATOR_NOT = 'op not'
    OPERATOR_BETWEEN = 'op between'
    OPERATOR_IN = 'op in'
    OPERATOR = 'operator'






    # def parseSSQuery(self, value):
    #     """Use Simple Selection Query to define query properties"""
    #     # clear current query definition
    #     self.clearPaths()
    #     self.clearRules()
    #
    #     tokenizer = BCTokenizer([
    #             BCTokenizerRule(BCFileQueryTokenType.DATE, r'"\d{4}-\d{2}-\d{2}"'),
    #             BCTokenizerRule(BCFileQueryTokenType.DATETIME, r'"\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}"'),
    #             BCTokenizerRule(BCFileQueryTokenType.STRING, r'"[^"]*"'),
    #             BCTokenizerRule(BCFileQueryTokenType.KEYWORD_SEARCH, r'search'),
    #             BCTokenizerRule(BCFileQueryTokenType.KEYWORD_IMAGE, r'images'),
    #             BCTokenizerRule(BCFileQueryTokenType.KEYWORD_FROM, r'from'),
    #             BCTokenizerRule(BCFileQueryTokenType.KEYWORD_DIRECTORY, r'directory'),
    #             BCTokenizerRule(BCFileQueryTokenType.KEYWORD_RECURSIVELY, r'recursively'),
    #             BCTokenizerRule(BCFileQueryTokenType.KEYWORD_MATCHING, r'matching'),
    #             BCTokenizerRule(BCFileQueryTokenType.KEYWORD_RULE, r'rule'),
    #             BCTokenizerRule(BCFileQueryTokenType.KEYWORD_OR, r'or'),
    #             BCTokenizerRule(BCFileQueryTokenType.OPERATOR_MATCH, r'match'),
    #             BCTokenizerRule(BCFileQueryTokenType.OPERATOR_NOT, r'not'),
    #             BCTokenizerRule(BCFileQueryTokenType.OPERATOR_BETWEEN, r'between'),
    #             BCTokenizerRule(BCFileQueryTokenType.OPERATOR_IN, r'in'),
    #             BCTokenizerRule(BCFileQueryTokenType.OPERATOR, r'<=|>=|<>|<|>|!=|='),
    #             BCTokenizerRule(BCFileQueryTokenType.SEPARATOR, r','),
    #             BCTokenizerRule(BCFileQueryTokenType.OPEN_RANGE, r'\('),
    #             BCTokenizerRule(BCFileQueryTokenType.CLOSE_RANGE, r'\)'),
    #             BCTokenizerRule(BCFileQueryTokenType.OPEN_LIST, r'\['),
    #             BCTokenizerRule(BCFileQueryTokenType.CLOSE_LIST, r'\]'),
    #             BCTokenizerRule(BCFileQueryTokenType.COMMENT, r'\s*(?://|#)[^\r\n]*'),
    #
    #             BCTokenizerRule(BCFileQueryTokenType.NEWLINE, r'\n'),
    #             BCTokenizerRule(BCFileQueryTokenType.SPACE, r'\s+'),
    #
    #             BCTokenizerRule(BCFileQueryTokenType.NUMBER_SIZE, r'(?:\.\d+|\d+\.\d+|\d+)(?:GB|GiB|MB|MiB|KB|KiB|B)'),
    #             BCTokenizerRule(BCFileQueryTokenType.NUMBER, r'\.\d+|\d+\.\d+|\d+'),
    #
    #             BCTokenizerRule(BCFileQueryTokenType.FILE_PROPERTY_NAME, r'filename'),
    #             BCTokenizerRule(BCFileQueryTokenType.FILE_PROPERTY_SIZE, r'filesize'),
    #             BCTokenizerRule(BCFileQueryTokenType.FILE_PROPERTY_DATE, r'filedate'),
    #             BCTokenizerRule(BCFileQueryTokenType.FILE_PROPERTY_FORMAT, r'fileformat'),
    #             BCTokenizerRule(BCFileQueryTokenType.IMAGE_PROPERTY_WIDTH, r'imagewidth'),
    #             BCTokenizerRule(BCFileQueryTokenType.IMAGE_PROPERTY_HEIGHT, r'imageheight')
    #         ])
    #
    #     tokens = tokenizer.tokenize(value)
    #
    #     if tokens.length() == 0:
    #         return
    #
    #     # define which token can be
    #     tokenFollow = {
    #             BCFileQueryTokenType.KEYWORD_SEARCH:            [(None, None, 'search')],
    #             BCFileQueryTokenType.KEYWORD_IMAGE:             [(BCFileQueryTokenType.KEYWORD_SEARCH, 'search', None)],
    #             BCFileQueryTokenType.KEYWORD_FROM:              [(BCFileQueryTokenType.KEYWORD_IMAGE, '')],
    #             BCFileQueryTokenType.KEYWORD_DIRECTORY:         [BCFileQueryTokenType.KEYWORD_FROM,
    #                                                              BCFileQueryTokenType.SEPARATOR],
    #             BCFileQueryTokenType.KEYWORD_RECURSIVELY:       [BCFileQueryTokenType.STRING],
    #             BCFileQueryTokenType.KEYWORD_MATCHING:          [BCFileQueryTokenType.STRING,
    #                                                              BCFileQueryTokenType.KEYWORD_RECURSIVELY],
    #
    #
    #         }
    #     ignoredToken = [BCFileQueryTokenType.NEWLINE, BCFileQueryTokenType.SPACE, BCFileQueryTokenType.COMMENT]
    #
    #     previousToken = None
    #
    #     print(tokens.text())
    #
    #     # iterate over tokens
    #     while not tokens.next() is None:
    #         while not tokens.value() is None and tokens.value().type() in ignoredToken:
    #             # ignore tokens that are not used
    #             tokens.next()
    #
    #         if not tokens.value() is None:
    #             # there's a token to process!
    #             print( str(tokens.value()).replace('\n', r'\n') )
    #
    #             if tokens.value().type() == BCFileQueryTokenType.NUMBER_SIZE:
    #                 print(tokens.inText(True))




