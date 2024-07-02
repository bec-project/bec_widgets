import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.motor_map.motor_map_widget import BECMotorMapWidget

DOM_XML = """
<ui language='c++'>
    <widget class='BECMotorMapWidget' name='bec_motor_map_widget'>
    </widget>
</ui>
"""


class BECMotorMapWidgetPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = BECMotorMapWidget(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Visualization Widgets"

    def icon(self):
        current_path = os.path.dirname(__file__)
        icon_path = os.path.join(current_path, "assets", "motor_map.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "bec_motor_map_widget"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECMotorMapWidget"

    def toolTip(self):
        return "BECMotorMapWidget"

    def whatsThis(self):
        return self.toolTip()
