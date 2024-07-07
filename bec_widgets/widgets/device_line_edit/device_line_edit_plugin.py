# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit

DOM_XML = """
<ui language='c++'>
    <widget class='DeviceLineEdit' name='device_line_edit'>
    </widget>
</ui>
"""


class DeviceLineEditPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = DeviceLineEdit(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Device Inputs"

    def icon(self):
        current_path = os.path.dirname(__file__)
        icon_path = os.path.join(current_path, "assets", "line_edit_icon.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "device_line_edit"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "DeviceLineEdit"

    def toolTip(self):
        return "Device LineEdit Example for BEC Widgets with autocomplete."

    def whatsThis(self):
        return self.toolTip()
