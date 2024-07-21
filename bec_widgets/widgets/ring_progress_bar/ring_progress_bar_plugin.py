# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

import bec_widgets
from bec_widgets.widgets.ring_progress_bar.ring_progress_bar import RingProgressBar

DOM_XML = """
<ui language='c++'>
    <widget class='RingProgressBar' name='ring_progress_bar'>
    </widget>
</ui>
"""
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class RingProgressBarPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = RingProgressBar(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Utils"

    def icon(self):
        icon_path = os.path.join(MODULE_PATH, "assets", "designer_icons", "ring_progress.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "ring_progress_bar"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "RingProgressBar"

    def toolTip(self):
        return "RingProgressBar"

    def whatsThis(self):
        return self.toolTip()
