# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.color_map_selector.color_map_selector import ColormapSelector

DOM_XML = """
<ui language='c++'>
    <widget class='ColormapSelector' name='color_map_selector'>
    </widget>
</ui>
"""


class ColormapSelectorPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ColormapSelector(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Buttons"

    def icon(self):
        current_path = os.path.dirname(__file__)
        icon_path = os.path.join(current_path, "assets", "color_map_selector_icon.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "color_map_selector"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ColormapSelector"

    def toolTip(self):
        return "A custom QComboBox widget for selecting colormaps."

    def whatsThis(self):
        return self.toolTip()
