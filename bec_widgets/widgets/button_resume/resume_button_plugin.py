# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.button_resume.button_resume import ResumeButton

DOM_XML = """
<ui language='c++'>
    <widget class='ResumeButton' name='resume_button'>
    </widget>
</ui>
"""


class ResumeButtonPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ResumeButton(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Buttons"

    def icon(self):
        return designer_material_icon(ResumeButton.ICON_NAME)

    def includeFile(self):
        return "resume_button"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ResumeButton"

    def toolTip(self):
        return "A button that continue scan queue."

    def whatsThis(self):
        return self.toolTip()
