# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.signal_line_edit.signal_line_edit import SignalLineEdit

DOM_XML = """
<ui language='c++'>
    <widget class='SignalLineEdit' name='signal_line_edit'>
    </widget>
</ui>
"""


class SignalLineEditPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = SignalLineEdit(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Input Widgets"

    def icon(self):
        return designer_material_icon(SignalLineEdit.ICON_NAME)

    def includeFile(self):
        return "signal_line_edit"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "SignalLineEdit"

    def toolTip(self):
        return ""

    def whatsThis(self):
        return self.toolTip()
