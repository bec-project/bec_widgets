# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.plots_next_gen.scatter_waveform.scatter_waveform import ScatterWaveform

DOM_XML = """
<ui language='c++'>
    <widget class='ScatterWaveform' name='scatter_waveform'>
    </widget>
</ui>
"""


class ScatterWaveformPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ScatterWaveform(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "Plot Widgets Next Gen"

    def icon(self):
        return designer_material_icon(ScatterWaveform.ICON_NAME)

    def includeFile(self):
        return "scatter_waveform"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ScatterWaveform"

    def toolTip(self):
        return "ScatterWaveform"

    def whatsThis(self):
        return self.toolTip()
