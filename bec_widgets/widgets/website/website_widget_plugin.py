# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from bec_qthemes import material_icon
from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QGuiApplication, QIcon

import bec_widgets
from bec_widgets.widgets.website.website import WebsiteWidget

DOM_XML = """
<ui language='c++'>
    <widget class='WebsiteWidget' name='website_widget'>
    </widget>
</ui>
"""
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class WebsiteWidgetPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = WebsiteWidget(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Utils"

    def icon(self):
        palette = QGuiApplication.palette()
        pixmap = material_icon("travel_explore", color=palette.text().color(), filled=True)
        return QIcon(pixmap)

    def includeFile(self):
        return "website_widget"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "WebsiteWidget"

    def toolTip(self):
        return ""

    def whatsThis(self):
        return self.toolTip()
