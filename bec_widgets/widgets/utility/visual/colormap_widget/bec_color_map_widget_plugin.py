# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget

DOM_XML = """
<ui language='c++'>
    <widget class='BECColorMapWidget' name='bec_color_map_widget'>
    </widget>
</ui>
"""


class BECColorMapWidgetPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = BECColorMapWidget(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Buttons"

    def icon(self):
        return designer_material_icon(BECColorMapWidget.ICON_NAME)

    def includeFile(self):
        return "bec_color_map_widget"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECColorMapWidget"

    def toolTip(self):
        return "BECColorMapWidget"

    def whatsThis(self):
        return self.toolTip()
