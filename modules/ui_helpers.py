# -*- coding: utf-8 -*-
# Module: modules/ui_helpers.py
# Contains: PythonSyntaxHighlighter

import re

try:
    from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
except ImportError:
    pass

class PythonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#000080"))
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            "\\bFalse\\b", "\\bNone\\b", "\\bTrue\\b", "\\band\\b", "\\bas\\b",
            "\\bassert\\b", "\\basync\\b", "\\bawait\\b", "\\bbreak\\b", "\\bclass\\b",
            "\\bcontinue\\b", "\\bdef\\b", "\\bdel\\b", "\\belif\\b", "\\belse\\b",
            "\\bexcept\\b", "\\bfinally\\b", "\\bfor\\b", "\\bfrom\\b", "\\bglobal\\b",
            "\\bif\\b", "\\bimport\\b", "\\bin\\b", "\\bis\\b", "\\blambda\\b",
            "\\bnonlocal\\b", "\\bnot\\b", "\\bor\\b", "\\bpass\\b", "\\braise\\b",
            "\\breturn\\b", "\\btry\\b", "\\bwhile\\b", "\\bwith\\b", "\\byield\\b",
            "\\bself\\b", "\\bin\\b", "\\bisinstance\\b", "\\bint\\b", "\\bfloat\\b",
            "\\bstr\\b", "\\blist\\b", "\\bdict\\b", "\\btuple\\b", "\\bset\\b", "\\bdatetime\\b"
        ]
        for word in keywords:
            rule = (re.compile(word), keywordFormat)
            self.highlightingRules.append(rule)

        selfFormat = QTextCharFormat()
        selfFormat.setForeground(QColor("#900090"))
        rule = (re.compile("\\bself\\."), selfFormat)
        self.highlightingRules.append(rule)

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#008000"))
        self.highlightingRules.append((re.compile("\".*?\""), stringFormat))
        self.highlightingRules.append((re.compile("'.*?'"), stringFormat))
        self.highlightingRules.append((re.compile("\"\"\"(.*?)\"\"\"", re.DOTALL), stringFormat))
        self.highlightingRules.append((re.compile("'''(.*?)'''", re.DOTALL), stringFormat))


        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#0000FF"))
        self.highlightingRules.append((re.compile("\\b[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?\\b"), numberFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#808080"))
        commentFormat.setFontItalic(True)
        self.highlightingRules.append((re.compile("#[^\n]*"), commentFormat))

        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#A020F0"))
        functionFormat.setFontWeight(QFont.Bold)
        self.highlightingRules.append((re.compile("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\()"), functionFormat))

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#2E8B57"))
        classFormat.setFontWeight(QFont.Bold)
        self.highlightingRules.append((re.compile("\\b[A-Z][a-zA-Z0-9_]*\\b"), classFormat))


    def highlightBlock(self, text):
        for pattern, format_obj in self.highlightingRules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, format_obj)
