from PyQt5.QtDesigner import QPyDesignerCustomWidgetPlugin
from PyQt5.QtGui import QIcon
from scan_plot import BECScanPlot


class BECScanPlotPlugin(QPyDesignerCustomWidgetPlugin):
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
        return BECScanPlot(parent)

    def name(self):
        return "BECScanPlot"

    def group(self):
        return "BEC widgets"

    def icon(self):
        return QIcon()

    def toolTip(self):
        return "BEC plot for scans"

    def whatsThis(self):
        return "BEC plot for scans"

    def isContainer(self):
        return False

    def domXml(self):
        return (
            '<widget class="BECScanPlot" name="BECScanPlot">\n'
            ' <property name="toolTip" >\n'
            "  <string>BEC plot for scans</string>\n"
            " </property>\n"
            ' <property name="whatsThis" >\n'
            "  <string>BEC plot for scans in Python using PyQt.</string>\n"
            " </property>\n"
            "</widget>\n"
        )

    def includeFile(self):
        return "scan_plot"
