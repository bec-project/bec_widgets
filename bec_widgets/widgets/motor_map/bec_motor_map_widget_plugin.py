import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

import bec_widgets
from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.motor_map.motor_map_widget import BECMotorMapWidget

DOM_XML = """
<ui language='c++'>
    <widget class='BECMotorMapWidget' name='bec_motor_map_widget'>
    </widget>
</ui>
"""

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


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
        return "BEC Plots"

    def icon(self):
        return designer_material_icon(BECMotorMapWidget.ICON_NAME)

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
