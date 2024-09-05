# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.designer_signal_proxy.signal_proxy import DesignerSignalProxy

DOM_XML = """
<ui language='c++'>
    <widget class='DesignerSignalProxy' name='designer_signal_proxy'>
    </widget>
</ui>
"""


class DesignerSignalProxyPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = DesignerSignalProxy(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(DesignerSignalProxy.ICON_NAME)

    def includeFile(self):
        return "designer_signal_proxy"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "DesignerSignalProxy"

    def toolTip(self):
        return "DesignerSignalProxy"

    def whatsThis(self):
        return self.toolTip()
