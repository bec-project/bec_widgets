# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.utility.ide_explorer.ide_explorer import IDEExplorer

DOM_XML = """
<ui language='c++'>
    <widget class='IDEExplorer' name='ide_explorer'>
    </widget>
</ui>
"""


class IDEExplorerPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = IDEExplorer(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(IDEExplorer.ICON_NAME)

    def includeFile(self):
        return "ide_explorer"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "IDEExplorer"

    def toolTip(self):
        return "Integrated Development Environment Explorer"

    def whatsThis(self):
        return self.toolTip()
