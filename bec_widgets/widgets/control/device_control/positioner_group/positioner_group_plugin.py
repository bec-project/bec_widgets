# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.control.device_control.positioner_group.positioner_group import (
    PositionerGroup,
)

DOM_XML = """
<ui language='c++'>
    <widget class='PositionerGroup' name='positioner_group'>
    </widget>
</ui>
"""


class PositionerGroupPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        if parent is None:
            return QWidget()
        t = PositionerGroup(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Device Control"

    def icon(self):
        return designer_material_icon(PositionerGroup.ICON_NAME)

    def includeFile(self):
        return "positioner_group"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "PositionerGroup"

    def toolTip(self):
        return "Simple Widget to control a positioner in box form"

    def whatsThis(self):
        return self.toolTip()
