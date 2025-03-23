# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.plots.motor_map.motor_map import MotorMap

DOM_XML = """
<ui language='c++'>
    <widget class='MotorMap' name='motor_map'>
    </widget>
</ui>
"""


class MotorMapPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = MotorMap(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "Plot Widgets"

    def icon(self):
        return designer_material_icon(MotorMap.ICON_NAME)

    def includeFile(self):
        return "motor_map"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "MotorMap"

    def toolTip(self):
        return "MotorMap"

    def whatsThis(self):
        return self.toolTip()
