from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.jupyter_console.jupyter_console import BECJupyterConsole

DOM_XML = """
<ui language='c++'>
    <widget class='BECJupyterConsole' name='bec_jupyter'>
    </widget>
</ui>
"""


class BECJupyterConsolePlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = BECJupyterConsole(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return QIcon()

    def includeFile(self):
        return "bec_jupyter"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECJupyterConsole"

    def toolTip(self):
        return "BECJupyterConsole widget"

    def whatsThis(self):
        return self.toolTip()
