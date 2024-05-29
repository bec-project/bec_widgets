# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from selection import MotorControlSelection

from PySide6.QtGui import QIcon
from PySide6.QtDesigner import QDesignerCustomWidgetInterface


DOM_XML = """
<ui language='c++'>
    <widget class='MotorControlSelection' name='selection'>
    </widget>
</ui>
"""


class MotorControlSelectionPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = MotorControlSelection(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return QIcon()

    def includeFile(self):
        return "selection"

    def initialize(self, form_editor):
        self._form_editor = form_editor
        # manager = form_editor.extensionManager()
        # iid = TicTacToeTaskMenuFactory.task_menu_iid()
        # manager.registerExtensions(TicTacToeTaskMenuFactory(manager), iid)

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "MotorControlSelection"

    def toolTip(self):
        return "MotorControl Selection Example for BEC Widgets"

    def whatsThis(self):
        return self.toolTip()
