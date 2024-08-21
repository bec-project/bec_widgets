# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import os

from bec_qthemes import material_icon
from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QGuiApplication, QIcon

from bec_widgets.widgets.positioner_box.positioner_control_line import PositionerControlLine

DOM_XML = """
<ui language='c++'>
    <widget class='PositionerControlLine' name='positioner_control_line'>
    </widget>
</ui>
"""
MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


class PositionerControlLinePlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = PositionerControlLine(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "Device Control"

    def icon(self):
        palette = QGuiApplication.palette()
        pixmap = material_icon("switch_left", color=palette.text().color(), filled=True)
        return QIcon(pixmap)

    def includeFile(self):
        return "positioner_control_line"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "PositionerControlLine"

    def toolTip(self):
        return "A widget that controls a single positioner in line form."

    def whatsThis(self):
        return self.toolTip()
