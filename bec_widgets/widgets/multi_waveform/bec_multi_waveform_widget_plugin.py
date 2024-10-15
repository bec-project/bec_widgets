# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.multi_waveform.multi_waveform_widget import BECMultiWaveformWidget

DOM_XML = """
<ui language='c++'>
    <widget class='BECMultiWaveformWidget' name='bec_multi_waveform_widget'>
    </widget>
</ui>
"""


class BECMultiWaveformWidgetPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = BECMultiWaveformWidget(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Plots"

    def icon(self):
        return designer_material_icon(BECMultiWaveformWidget.ICON_NAME)

    def includeFile(self):
        return "bec_multi_waveform_widget"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECMultiWaveformWidget"

    def toolTip(self):
        return "BECMultiWaveformWidget"

    def whatsThis(self):
        return self.toolTip()
