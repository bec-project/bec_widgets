"""
waveform_plot_plugin.py
Registers WaveformPlotDemo2 with Qt Designer,
including the WaveformPlotDemo2TaskMenu extension.
"""

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.plots_next_gen.waveform.demo_2.waveform_demo2 import WaveformPlotDemo2

DOM_XML = """
<ui language='c++'>
    <widget class='WaveformPlotDemo2' name='WaveformPlotDemo2'>
        <property name='geometry'>
            <rect>
                <x>0</x>
                <y>0</y>
                <width>300</width>
                <height>200</height>
            </rect>
        </property>
        <property name='deviceName'>
            <string>MyDevice</string>
        </property>
        <property name='someFlag'>
            <bool>false</bool>
        </property>
        <property name='curvesJson'>
            <string>[{"label": "DefaultCurve", "color": "red"}]</string>
        </property>
    </widget>
</ui>
"""


class WaveformPlotDemo2Plugin(QDesignerCustomWidgetInterface):
    """
    Exposes WaveformPlotDemo2 to Designer, plus sets up the Task Menu extension
    for "Edit Configuration..." popup.
    """

    def __init__(self):
        super().__init__()
        self._initialized = False

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isInitialized(self):
        return self._initialized

    def createWidget(self, parent):
        return WaveformPlotDemo2(parent)

    def name(self):
        return "WaveformPlotDemo2"

    def group(self):
        return "Waveform Widgets"

    def icon(self):
        # If you have a real icon, load it here
        return QIcon()

    def toolTip(self):
        return "A multi-property WaveformPlotDemo2 example"

    def whatsThis(self):
        return self.toolTip()

    def isContainer(self):
        return False

    def domXml(self):
        return DOM_XML

    def includeFile(self):
        # The Python import path for your waveforms
        # E.g. "my_widgets.waveform.waveform_plot"
        return __name__
