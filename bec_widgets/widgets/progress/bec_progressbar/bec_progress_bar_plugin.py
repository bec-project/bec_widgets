# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.progress.bec_progressbar.bec_progressbar import BECProgressBar

DOM_XML = """
<ui language='c++'>
    <widget class='BECProgressBar' name='bec_progress_bar'>
    </widget>
</ui>
"""


class BECProgressBarPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = BECProgressBar(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Utils"

    def icon(self):
        return designer_material_icon(BECProgressBar.ICON_NAME)

    def includeFile(self):
        return "bec_progress_bar"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECProgressBar"

    def toolTip(self):
        return "A custom progress bar with smooth transitions and a modern design."

    def whatsThis(self):
        return self.toolTip()
