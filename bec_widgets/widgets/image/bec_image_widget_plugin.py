# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

import bec_widgets
from bec_widgets.widgets.image.image_widget import BECImageWidget

DOM_XML = """
<ui language='c++'>
    <widget class='BECImageWidget' name='bec_image_widget'>
    </widget>
</ui>
"""

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class BECImageWidgetPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = BECImageWidget(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Plots"

    def icon(self):
        icon_path = os.path.join(MODULE_PATH, "assets", "designer_icons", "image.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "bec_image_widget"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECImageWidget"

    def toolTip(self):
        return "BECImageWidget"

    def whatsThis(self):
        return self.toolTip()
