from __future__ import annotations

import json
from typing import Optional

import pyqtgraph as pg
from qtpy.QtCore import Property, Signal
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout

from bec_widgets.utils.bec_widget import BECWidget


##############################################################################
# MinimalPlotBase (a stand-in for your real PlotBase)
##############################################################################
class MinimalPlotBase(QWidget):
    """
    A trivial container that just holds a single pyqtgraph PlotWidget.
    In your actual code, replace this with your real 'PlotBase' class.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_item = pg.PlotItem()
        self.plot_widget = pg.PlotWidget(plotItem=self.plot_item)
        layout.addWidget(self.plot_widget)
        self.plot_item.addLegend()


##############################################################################
# WaveformPlot subclass that uses a QProperty for multiple curve definitions
##############################################################################
class WaveformPlot(BECWidget, MinimalPlotBase):
    """
    Demonstrates a 'curvesJson' QProperty that holds an array of curve definitions.
    Each array entry might look like:
        {
          "label": "MyCurve",
          "color": "#ff0000"
          // optionally: "device": "devA", "signal": "sigB", ...
        }

    On setting 'curvesJson', the widget parses the JSON, clears old curves,
    and creates new PlotDataItems with dummy data (for demonstration).
    """

    PLUGIN = True
    # Signal to notify when any property changes (optional convenience signal)
    property_changed = Signal(str, object)

    # We'll store our JSON string in this private attribute
    _curves_json: str = ""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__()
        MinimalPlotBase.__init__(self, parent=parent)
        # Keep track of the PlotDataItem objects so we can remove them on update
        self._waveform_curves = []

    # ------------------------------------------------------------------------
    # QProperty: curvesJson
    # ------------------------------------------------------------------------
    def getCurvesJson(self) -> str:
        """Return the JSON string describing all curves."""
        return self._curves_json

    def setCurvesJson(self, new_json: str):
        """Set a new JSON definition for the curves; parse and rebuild them."""
        if self._curves_json != new_json:
            self._curves_json = new_json
            # Emit a signal if you like
            self.property_changed.emit("curvesJson", new_json)
            # Rebuild the curves
            self._build_curves_from_json(new_json)

    # The actual QProperty for Designer (or QSettings) to see
    curvesJson = Property(str, fget=getCurvesJson, fset=setCurvesJson)

    # ------------------------------------------------------------------------
    # Build or rebuild the curves from the JSON definition
    # ------------------------------------------------------------------------
    def _build_curves_from_json(self, json_str: str):
        """
        Clears out any existing PlotDataItems,
        then parses the JSON and creates new items.
        Here we just do dummy data to show them visually.
        """
        # 1. Remove old items
        for c in self._waveform_curves:
            self.plot_item.removeItem(c)
        self._waveform_curves.clear()

        # 2. Parse the JSON
        try:
            curve_defs = json.loads(json_str)
            if not isinstance(curve_defs, list):
                raise ValueError("curvesJson must be a JSON list of objects.")
        except Exception as e:
            print(f"[WaveformPlot] Error parsing curvesJson: {e}")
            return

        # 3. Create new PlotDataItems for each definition
        for idx, cdef in enumerate(curve_defs):
            label = cdef.get("label", f"Curve{idx + 1}")
            color = cdef.get("color", "blue")
            # In your real code, you might also parse "device", "signal", etc.

            # Dummy data (just to show distinct lines)
            xdata = [0, 1, 2, 3, 4]
            ybase = idx * 3
            ydata = [ybase + 0, ybase + 1, ybase + 2, ybase + 1, ybase + 0]

            curve_item = pg.PlotDataItem(xdata, ydata, pen=color, name=label)
            self.plot_item.addItem(curve_item)
            self._waveform_curves.append(curve_item)


##############################################################################
# Standalone test
##############################################################################
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    widget = WaveformPlot()
    widget.setWindowTitle("Minimal multiple-curves example with QProperty + PlotBase-like class")

    # Example JSON: two curves with different color/labels
    example_json = json.dumps(
        [{"label": "Alpha", "color": "red"}, {"label": "Beta", "color": "#00ff00"}]
    )
    widget.curvesJson = example_json

    widget.show()
    sys.exit(app.exec_())
