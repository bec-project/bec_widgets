# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea

DOM_XML = """
<ui language='c++'>
    <widget class='BECDockArea' name='bec_dock_area'>
    </widget>
</ui>
"""


class BECDockAreaPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        if parent is None:
            return QWidget()
        t = BECDockArea(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Containers"

    def icon(self):
        return designer_material_icon(BECDockArea.ICON_NAME)

    def includeFile(self):
        return "bec_dock_area"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECDockArea"

    def toolTip(self):
        return ""

    def whatsThis(self):
        return self.toolTip()
