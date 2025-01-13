# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.plots_next_gen.waveform.waveform_demo import WaveformPlot


class WaveformPlotPlugin(QDesignerCustomWidgetInterface):
    """
    Minimal custom widget plugin for Qt Designer.
    - Creates WaveformPlot
    - Provides DOM XML
    - Installs our TaskMenu extension factory
    """

    def __init__(self):
        super().__init__()
        self._initialized = False
        self._extension_factory = None

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

        # Register our task menu extension factory with the form editor
        manager = form_editor.extensionManager()
        if manager:
            factory = WaveformPlotTaskMenuFactory(manager)
            manager.registerExtensions(factory, "org.qt-project.Qt.Designer.TaskMenu")

    def isInitialized(self):
        return self._initialized

    def createWidget(self, parent):
        return WaveformPlot(parent)

    def name(self):
        return "WaveformPlot"

    def group(self):
        return "MyPlotWidgets"

    def toolTip(self):
        return "WaveformPlot with multiple curves"

    def whatsThis(self):
        return self.toolTip()

    def includeFile(self):
        # Typically the python module name where WaveformPlot is defined
        # (used in the generated ui code)
        return __name__

    def icon(self):
        # Provide an icon if desired
        # e.g. QIcon(":/icons/waveform.png")
        return None

    def isContainer(self):
        return False

    def domXml(self):
        return """
<ui language='c++'>
    <widget class='WaveformPlot' name='waveformPlot'>
    </widget>
</ui>
"""
