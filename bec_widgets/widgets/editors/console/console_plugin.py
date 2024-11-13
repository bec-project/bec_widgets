# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

import bec_widgets
from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.editors.console.console import BECConsole

DOM_XML = """
<ui language='c++'>
    <widget class='BECConsole' name='bec_console'>
    </widget>
</ui>
"""

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class BECConsolePlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = BECConsole(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Console"

    def icon(self):
        return designer_material_icon(BECConsole.ICON_NAME)

    def includeFile(self):
        return "bec_console"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECConsole"

    def toolTip(self):
        return "A terminal-like vt100 widget."

    def whatsThis(self):
        return self.toolTip()
