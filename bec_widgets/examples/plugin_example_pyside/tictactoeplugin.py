# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon
from tictactoe import TicTacToe
from tictactoetaskmenu import TicTacToeTaskMenuFactory

import bec_widgets

DOM_XML = """
<ui language='c++'>
    <widget class='TicTacToe' name='ticTacToe'>
        <property name='geometry'>
            <rect>
                <x>0</x>
                <y>0</y>
                <width>200</width>
                <height>200</height>
            </rect>
        </property>
        <property name='state'>
            <string>-X-XO----</string>
        </property>
    </widget>
</ui>
"""

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class TicTacToePlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = TicTacToe(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "Games"

    def icon(self):
        icon_path = os.path.join(MODULE_PATH, "assets", "designer_icons", "games.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "tictactoe"

    def initialize(self, form_editor):
        self._form_editor = form_editor
        manager = form_editor.extensionManager()
        iid = TicTacToeTaskMenuFactory.task_menu_iid()
        manager.registerExtensions(TicTacToeTaskMenuFactory(manager), iid)

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "TicTacToe"

    def toolTip(self):
        return "Tic Tac Toe Example, demonstrating class QDesignerTaskMenuExtension (Python)"

    def whatsThis(self):
        return self.toolTip()
