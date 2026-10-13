# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.control.scan_scheduler.scan_scheduler import ScanScheduler

DOM_XML = """
<ui language='c++'>
    <widget class='ScanScheduler' name='scan_scheduler'>
    </widget>
</ui>
"""


class ScanSchedulerPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        if parent is None:
            return QWidget()
        t = ScanScheduler(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(ScanScheduler.ICON_NAME)

    def includeFile(self):
        return "scan_scheduler"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ScanScheduler"

    def toolTip(self):
        return "Edit nested components and execute validated sequences through procedures."

    def whatsThis(self):
        return self.toolTip()
