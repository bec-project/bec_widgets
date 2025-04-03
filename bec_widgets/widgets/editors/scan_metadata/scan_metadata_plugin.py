# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.editors.scan_metadata.scan_metadata import ScanMetadata

DOM_XML = """
<ui language='c++'>
    <widget class='ScanMetadata' name='scan_metadata'>
    </widget>
</ui>
"""


class ScanMetadataPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ScanMetadata(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(ScanMetadata.ICON_NAME)

    def includeFile(self):
        return "scan_metadata"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ScanMetadata"

    def toolTip(self):
        return "Dynamically generates a form for inclusion of metadata for a scan."

    def whatsThis(self):
        return self.toolTip()
