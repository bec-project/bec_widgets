# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.containers.expantion_panel.expansion_panel import ExpansionPanel

DOM_XML = """
<ui language='c++'>
    <widget class='ExpansionPanel' name='expansion_panel'>
    </widget>
</ui>
"""


class ExpansionPanelPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ExpansionPanel(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(ExpansionPanel.ICON_NAME)

    def includeFile(self):
        return "expansion_panel"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return True

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ExpansionPanel"

    def toolTip(self):
        return "ExpansionPanel"

    def whatsThis(self):
        return self.toolTip()
