# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.control.device_control.positioner_box.positioner_control_line.positioner_control_line import (
    PositionerControlLine,
)

DOM_XML = """
<ui language='c++'>
    <widget class='PositionerControlLine' name='positioner_control_line'>
    </widget>
</ui>
"""


class PositionerControlLinePlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        if parent is None:
            return QWidget()
        t = PositionerControlLine(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Device Control"

    def icon(self):
        return designer_material_icon(PositionerControlLine.ICON_NAME)

    def includeFile(self):
        return "positioner_control_line"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "PositionerControlLine"

    def toolTip(self):
        return "A widget that controls a single device."

    def whatsThis(self):
        return self.toolTip()
