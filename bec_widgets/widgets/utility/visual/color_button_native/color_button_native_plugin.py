# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.utility.visual.color_button_native.color_button_native import (
    ColorButtonNative,
)

DOM_XML = """
<ui language='c++'>
    <widget class='ColorButtonNative' name='color_button_native'>
    </widget>
</ui>
"""


class ColorButtonNativePlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ColorButtonNative(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Buttons"

    def icon(self):
        return designer_material_icon(ColorButtonNative.ICON_NAME)

    def includeFile(self):
        return "color_button_native"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ColorButtonNative"

    def toolTip(self):
        return "A QPushButton subclass that displays a color."

    def whatsThis(self):
        return self.toolTip()
