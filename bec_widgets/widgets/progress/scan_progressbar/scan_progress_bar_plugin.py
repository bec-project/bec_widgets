# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import ScanProgressBar

DOM_XML = """
<ui language='c++'>
    <widget class='ScanProgressBar' name='scan_progress_bar'>
    </widget>
</ui>
"""


class ScanProgressBarPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ScanProgressBar(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Utils"

    def icon(self):
        return designer_material_icon(ScanProgressBar.ICON_NAME)

    def includeFile(self):
        return "scan_progress_bar"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ScanProgressBar"

    def toolTip(self):
        return "A progress bar that is hooked up to the scan progress of a scan."

    def whatsThis(self):
        return self.toolTip()
