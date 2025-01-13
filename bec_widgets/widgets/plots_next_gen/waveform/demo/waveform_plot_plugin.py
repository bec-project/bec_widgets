"""
waveform_plot_plugin.py
Registers WaveformPlot with Qt Designer,
including the WaveformPlotTaskMenu extension.
"""

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from .waveform_demo import WaveformPlot
from .waveform_plot_taskmenu import WaveformPlotTaskMenuFactory

DOM_XML = """
<ui language='c++'>
    <widget class='WaveformPlot' name='waveformPlot'>
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


class WaveformPlotPlugin(QDesignerCustomWidgetInterface):
    """
    Exposes WaveformPlot to Designer, plus sets up the Task Menu extension
    for "Edit Configuration..." popup.
    """

    def __init__(self):
        super().__init__()
        self._initialized = False

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

        # Register the TaskMenu extension
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
        return "Waveform Widgets"

    def icon(self):
        # If you have a real icon, load it here
        return QIcon()

    def toolTip(self):
        return "A multi-property WaveformPlot example"

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
