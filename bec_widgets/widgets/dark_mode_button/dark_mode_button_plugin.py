# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.dark_mode_button.dark_mode_button import DarkModeButton

DOM_XML = """
<ui language='c++'>
    <widget class='DarkModeButton' name='dark_mode_button'>
    </widget>
</ui>
"""


class DarkModeButtonPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = DarkModeButton(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Buttons"

    def icon(self):
        return designer_material_icon(DarkModeButton.ICON_NAME)

    def includeFile(self):
        return "dark_mode_button"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "DarkModeButton"

    def toolTip(self):
        return "Button to toggle between dark and light mode."

    def whatsThis(self):
        return self.toolTip()
