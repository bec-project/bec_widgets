# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.button_reset.button_reset import ResetButton

DOM_XML = """
<ui language='c++'>
    <widget class='ResetButton' name='reset_button'>
    </widget>
</ui>
"""


class ResetButtonPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ResetButton(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Buttons"

    def icon(self):
        return designer_material_icon(ResetButton.ICON_NAME)

    def includeFile(self):
        return "reset_button"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ResetButton"

    def toolTip(self):
        return "A button that reset the scan queue."

    def whatsThis(self):
        return self.toolTip()
