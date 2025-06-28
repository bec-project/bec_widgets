# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.editors.sbb_monitor.sbb_monitor import SBBMonitor

DOM_XML = """
<ui language='c++'>
    <widget class='SBBMonitor' name='sbb_monitor'>
    </widget>
</ui>
"""


class SBBMonitorPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = SBBMonitor(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(SBBMonitor.ICON_NAME)

    def includeFile(self):
        return "sbb_monitor"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "SBBMonitor"

    def toolTip(self):
        return ""

    def whatsThis(self):
        return self.toolTip()
