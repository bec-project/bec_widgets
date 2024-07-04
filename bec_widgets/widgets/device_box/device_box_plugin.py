# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.device_box.device_box import DeviceBox

DOM_XML = """
<ui language='c++'>
    <widget class='DeviceBox' name='device_box'>
    </widget>
</ui>
"""


class DeviceBoxPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = DeviceBox(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "Device Control"

    def icon(self):
        return QIcon()

    def includeFile(self):
        return "device_box"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "DeviceBox"

    def toolTip(self):
        return "A widget for controlling a single positioner. "

    def whatsThis(self):
        return self.toolTip()
