from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.utility.logpanel.logpanel import LogPanel

DOM_XML = """
<ui language='c++'>
    <widget class='LogPanel' name='log_panel'>
    </widget>
</ui>
"""


class LogPanelPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._initialized = False
        self._form_editor = None

    def createWidget(self, parent):
        # 1) Detect if Qt Designer is just enumerating your widget for the palette
        if parent is None:
            # Return a minimal stub (or do nothing) so you don’t initialize LogPanel fully
            return QWidget()

        # 2) Otherwise, create the real widget
        return LogPanel(parent)

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Utils"

    def icon(self):
        return designer_material_icon(LogPanel.ICON_NAME)

    def includeFile(self):
        # Return the Python import path for the actual class
        return "log_panel"

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._form_editor = form_editor
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return "LogPanel"

    def toolTip(self):
        return "Displays a log panel"

    def whatsThis(self):
        return self.toolTip()
