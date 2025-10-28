# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.utility.pdf_viewer.pdf_viewer import PdfViewerWidget

DOM_XML = """
<ui language='c++'>
    <widget class='PdfViewerWidget' name='pdf_viewer_widget'>
    </widget>
</ui>
"""


class PdfViewerWidgetPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        if parent is None:
            return QWidget()
        t = PdfViewerWidget(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Utils"

    def icon(self):
        return designer_material_icon(PdfViewerWidget.ICON_NAME)

    def includeFile(self):
        return "pdf_viewer_widget"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "PdfViewerWidget"

    def toolTip(self):
        return "A widget to display PDF documents with toolbar controls."

    def whatsThis(self):
        return self.toolTip()
