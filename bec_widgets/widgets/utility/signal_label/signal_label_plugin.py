# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.utility.signal_label.signal_label import SignalLabel

DOM_XML = """
<ui language='c++'>
    <widget class='SignalLabel' name='signal_label'>
    </widget>
</ui>
"""


class SignalLabelPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = SignalLabel(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Utils"

    def icon(self):
        return designer_material_icon(SignalLabel.ICON_NAME)

    def includeFile(self):
        return "signal_label"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "SignalLabel"

    def toolTip(self):
        return "Display the live value of any signal"

    def whatsThis(self):
        return self.toolTip()
