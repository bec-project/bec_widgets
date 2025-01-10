# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_2d.positioner_box_2d import (
    PositionerBox2D,
)

DOM_XML = """
<ui language='c++'>
    <widget class='PositionerBox2D' name='positioner_box2_d'>
    </widget>
</ui>
"""


class PositionerBox2DPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = PositionerBox2D(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "Device Control"

    def icon(self):
        return designer_material_icon(PositionerBox2D.ICON_NAME)

    def includeFile(self):
        return "positioner_box2_d"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "PositionerBox2D"

    def toolTip(self):
        return "Simple Widget to control two positioners in box form"

    def whatsThis(self):
        return self.toolTip()
