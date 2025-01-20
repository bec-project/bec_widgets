# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox

DOM_XML = """
<ui language='c++'>
    <widget class='SignalComboBox' name='signal_combo_box'>
    </widget>
</ui>
"""


class SignalComboBoxPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = SignalComboBox(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Input Widgets"

    def icon(self):
        return designer_material_icon(SignalComboBox.ICON_NAME)

    def includeFile(self):
        return "signal_combo_box"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "SignalComboBox"

    def toolTip(self):
        return ""

    def whatsThis(self):
        return self.toolTip()
