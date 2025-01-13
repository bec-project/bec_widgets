"""
waveform_plot_plugin.py

Registers WaveformPlot with Qt Designer and installs the task-menu extension factory.
"""

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from .waveform_demo import WaveformPlot

# Import your classes
from .waveform_plot_taskmenu import WaveformPlotTaskMenuFactory

# If you have an icon in resources or a function:
# from .some_icon_provider import get_designer_icon


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
        <property name='curvesJson'>
            <stringlist>
                <string>[{"label":"DefaultCurve","color":"red"}]</string>
            </stringlist>
        </property>
    </widget>
</ui>
"""


class WaveformPlotPlugin(QDesignerCustomWidgetInterface):
    """
    Minimal plugin that exposes WaveformPlot to Qt Designer,
    plus sets up the WaveformPlotTaskMenu extension.
    """

    def __init__(self):
        super().__init__()
        self._initialized = False

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

        # Register the Task Menu extension factory
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

    def toolTip(self):
        return "WaveformPlot with multiple curves"

    def whatsThis(self):
        return self.toolTip()

    def isContainer(self):
        return False

    def domXml(self):
        return DOM_XML

    def includeFile(self):
        # The module path that Qt Designer uses in generated .ui -> .py code
        # e.g. "my_package.waveform_plot"
        return __name__

    def icon(self):
        # If you have an icon, return QIcon(":/myicon.png") or similar
        return QIcon()
