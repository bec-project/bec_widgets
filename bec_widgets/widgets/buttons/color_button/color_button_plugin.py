import os

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.buttons.color_button.color_button import ColorButton

DOM_XML = """
<ui language='c++'>
    <widget class='ColorButton' name='color_button'>
    </widget>
</ui>
"""


class ColorButtonPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ColorButton(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Buttons"

    def icon(self):
        current_path = os.path.dirname(__file__)
        icon_path = os.path.join(current_path, "assets", "color_button.png")
        return QIcon(icon_path)

    def includeFile(self):
        return "color_button"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ColorButton"

    def toolTip(self):
        return "ColorButton which opens a color dialog."

    def whatsThis(self):
        return self.toolTip()
