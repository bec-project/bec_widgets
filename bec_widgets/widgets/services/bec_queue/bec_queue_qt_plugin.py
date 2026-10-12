# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.services.bec_queue.bec_queue_qt import BECQueueQt

DOM_XML = """
<ui language='c++'>
    <widget class='BECQueueQt' name='bec_queue_qt'>
    </widget>
</ui>
"""


class BECQueueQtPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        if parent is None:
            return QWidget()
        t = BECQueueQt(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Services"

    def icon(self):
        return designer_material_icon(BECQueueQt.ICON_NAME)

    def includeFile(self):
        return "bec_queue_qt"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECQueueQt"

    def toolTip(self):
        return "BEC queue with a QWidget view, for comparison with the QML view."

    def whatsThis(self):
        return self.toolTip()
