# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

import bec_widgets
from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.text_box.text_box import TextBox

DOM_XML = """
<ui language='c++'>
    <widget class='TextBox' name='text_box'>
    </widget>
</ui>
"""
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class TextBoxPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = TextBox(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Utils"

    def icon(self):
        return designer_material_icon("chat")

    def includeFile(self):
        return "text_box"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "TextBox"

    def toolTip(self):
        return "TextBox"

    def whatsThis(self):
        return self.toolTip()
