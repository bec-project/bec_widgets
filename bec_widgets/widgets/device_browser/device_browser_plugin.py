# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from bec_qthemes import material_icon
from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QGuiApplication, QIcon

from bec_widgets.widgets.device_browser.device_browser import DeviceBrowser

DOM_XML = """
<ui language='c++'>
    <widget class='DeviceBrowser' name='device_browser'>
    </widget>
</ui>
"""


class DeviceBrowserPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = DeviceBrowser(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Services"

    def icon(self):
        palette = QGuiApplication.palette()
        pixmap = material_icon("lists", color=palette.text().color(), filled=True)
        return QIcon(pixmap)

    def includeFile(self):
        return "device_browser"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "DeviceBrowser"

    def toolTip(self):
        return "DeviceBrowser"

    def whatsThis(self):
        return self.toolTip()
