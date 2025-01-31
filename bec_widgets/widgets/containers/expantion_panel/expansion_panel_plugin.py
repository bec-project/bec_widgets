from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon

# Make sure the path below is correct
from bec_widgets.widgets.containers.expantion_panel.expansion_panel import ExpansionPanel

DOM_XML = """
<ui language='c++'>
    <widget class='ExpansionPanel' name='expansion_panel'/>
</ui>
"""


class ExpansionPanelPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self.initialized = False

    def createWidget(self, parent):
        return ExpansionPanel(parent=parent)

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Widgets"

    def icon(self):
        return designer_material_icon(ExpansionPanel.ICON_NAME)

    def includeFile(self):
        return "bec_widgets.widgets.containers.expantion_panel.expansion_panel"

    def initialize(self, form_editor):
        if self.initialized:
            return
        self.initialized = True

    def isContainer(self):
        return True  # crucial for Designer to allow dropping child widgets

    def isInitialized(self):
        return self.initialized

    def name(self):
        return "ExpansionPanel"

    def toolTip(self):
        return "A collapsible panel container widget"

    def whatsThis(self):
        return self.toolTip()
