# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

import bec_widgets
from bec_widgets.widgets.scan_control.scan_control import ScanControl

DOM_XML = """
<ui language='c++'>
    <widget class='ScanControl' name='scan_control'>
    </widget>
</ui>
"""
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class ScanControlPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ScanControl(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "Device Control"

    def icon(self):
        icon_path = os.path.join(MODULE_PATH, "assets", "designer_icons", "scan_control.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "scan_control"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ScanControl"

    def toolTip(self):
        return "ScanControl"

    def whatsThis(self):
        return self.toolTip()
