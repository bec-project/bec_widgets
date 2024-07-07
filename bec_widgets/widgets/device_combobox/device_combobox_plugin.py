# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.device_combobox.device_combobox import DeviceComboBox

DOM_XML = """
<ui language='c++'>
    <widget class='DeviceComboBox' name='device_combobox'>
    </widget>
</ui>
"""


class DeviceComboBoxPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = DeviceComboBox(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Device Inputs"

    def icon(self):
        current_path = os.path.dirname(__file__)
        icon_path = os.path.join(current_path, "assets", "device_combobox_icon.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "device_combobox"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "DeviceComboBox"

    def toolTip(self):
        return "Device ComboBox Example for BEC Widgets"

    def whatsThis(self):
        return self.toolTip()
