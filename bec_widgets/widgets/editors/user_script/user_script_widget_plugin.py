# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.editors.user_script.user_script import UserScriptWidget

DOM_XML = """
<ui language='c++'>
    <widget class='UserScriptWidget' name='user_script_widget'>
    </widget>
</ui>
"""


class UserScriptWidgetPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = UserScriptWidget(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Services"

    def icon(self):
        return designer_material_icon(UserScriptWidget.ICON_NAME)

    def includeFile(self):
        return "user_script_widget"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "UserScriptWidget"

    def toolTip(self):
        return "Dialog for displaying the fit summary and params for LMFit DAP processes"

    def whatsThis(self):
        return self.toolTip()
