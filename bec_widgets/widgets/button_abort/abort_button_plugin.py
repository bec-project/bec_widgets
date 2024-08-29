# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.button_abort.button_abort import AbortButton

DOM_XML = """
<ui language='c++'>
    <widget class='AbortButton' name='abort_button'>
    </widget>
</ui>
"""


class AbortButtonPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = AbortButton(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Buttons"

    def icon(self):
        return designer_material_icon(AbortButton.ICON_NAME)

    def includeFile(self):
        return "abort_button"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "AbortButton"

    def toolTip(self):
        return "A button that abort the scan."

    def whatsThis(self):
        return self.toolTip()
