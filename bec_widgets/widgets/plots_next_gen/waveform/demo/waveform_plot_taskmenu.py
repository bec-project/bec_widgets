"""
waveform_plot_taskmenu.py
Task Menu extension for Qt Designer.
It attaches "Edit Configuration..." to the WaveformPlot,
launching WaveformPlotConfigDialog.
"""

from qtpy.QtCore import Slot
from qtpy.QtDesigner import QExtensionFactory, QPyDesignerTaskMenuExtension
from qtpy.QtGui import QAction

from bec_widgets.widgets.plots_next_gen.waveform.demo.waveform_demo import WaveformPlot
from bec_widgets.widgets.plots_next_gen.waveform.demo.waveform_plot_config_dialog import (
    WaveformPlotConfigDialog,
)


class WaveformPlotTaskMenu(QPyDesignerTaskMenuExtension):
    def __init__(self, widget: WaveformPlot, parent=None):
        super().__init__(parent)
        self._widget = widget
        self._edit_action = QAction("Edit Configuration...", self)
        self._edit_action.triggered.connect(self._on_edit)

    def taskActions(self):
        return [self._edit_action]

    def preferredEditAction(self):
        # Double-click in Designer might open this
        return self._edit_action

    @Slot()
    def _on_edit(self):
        # Show the same config dialog we can use in normal code
        dlg = WaveformPlotConfigDialog(self._widget)
        dlg.exec_()  # If user presses OK, the widget's properties are updated


class WaveformPlotTaskMenuFactory(QExtensionFactory):
    """
    Creates a WaveformPlotTaskMenu if the widget is an instance of WaveformPlot
    and the requested extension is 'TaskMenu'.
    """

    def createExtension(self, obj, iid, parent):
        if iid == "org.qt-project.Qt.Designer.TaskMenu" and isinstance(obj, WaveformPlot):
            return WaveformPlotTaskMenu(obj, parent)
        return None
