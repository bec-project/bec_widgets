from qtpy.QtDesigner import QPyDesignerCustomWidgetPlugin
from qtpy.QtGui import QIcon

from bec_widgets.widgets.scan_plot.scan2d_plot import BECScanPlot2D


class BECScanPlot2DPlugin(QPyDesignerCustomWidgetPlugin):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._initialized = False

    def initialize(self, formEditor):
        if self._initialized:
            return

        self._initialized = True

    def isInitialized(self):
        return self._initialized

    def createWidget(self, parent):
        return BECScanPlot2D(parent)

    def name(self):
        return "BECScanPlot2D"

    def group(self):
        return "BEC widgets"

    def icon(self):
        return QIcon()

    def toolTip(self):
        return "BEC plot for 2D scans"

    def whatsThis(self):
        return "BEC plot for 2D scans"

    def isContainer(self):
        return False

    def domXml(self):
        return (
            '<widget class="BECScanPlot2D" name="BECScanPlot2D">\n'
            ' <property name="toolTip" >\n'
            "  <string>BEC plot for 2D scans</string>\n"
            " </property>\n"
            ' <property name="whatsThis" >\n'
            "  <string>BEC plot for 2D scans in Python using PyQt.</string>\n"
            " </property>\n"
            "</widget>\n"
        )

    def includeFile(self):
        return "scan2d_plot"
