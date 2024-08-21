import os

from bec_qthemes import material_icon
from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QGuiApplication, QIcon

import bec_widgets
from bec_widgets.widgets.color_button.color_button import ColorButton

DOM_XML = """
<ui language='c++'>
    <widget class='ColorButton' name='color_button'>
    </widget>
</ui>
"""
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


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
        palette = QGuiApplication.palette()
        pixmap = material_icon("colors", color=palette.text().color(), filled=True)
        return QIcon(pixmap)

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
