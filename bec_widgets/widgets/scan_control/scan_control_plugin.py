from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon

from bec_widgets.widgets.scan_control import ScanControl

DOM_XML = """
<ui language='c++'>
    <widget class='ScanControl' name='scan_control'>
    </widget>
</ui>
"""


class ScanControlPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = ScanControl(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return QIcon()

    def includeFile(self):
        return "scan_control"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "ScanControl"

    def toolTip(self):
        return "ScanControl widget"

    def whatsThis(self):
        return self.toolTip()
