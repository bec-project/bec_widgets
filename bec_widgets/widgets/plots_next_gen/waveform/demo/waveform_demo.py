"""
waveform_plot.py

Minimal WaveformPlot widget that has:
  - a 'curvesJson' property
  - a pyqtgraph PlotItem
  - dummy data for each curve
"""

import json

import pyqtgraph as pg
from qtpy.QtCore import Property
from qtpy.QtWidgets import QWidget, QVBoxLayout


class WaveformPlot(QWidget):
    """
    Minimal demonstration widget with a 'curvesJson' property.
    In your real code, you'd subclass your PlotBase, but let's keep it plain.
    """

    ICON_NAME = "multiline_chart"  # If you want to set an icon in the plugin

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves_json = "[]"  # Start with empty array
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # A PyQtGraph PlotItem inside a PlotWidget
        self.plot_item = pg.PlotItem()
        self.plot_widget = pg.PlotWidget(plotItem=self.plot_item)
        layout.addWidget(self.plot_widget)
        self.plot_item.addLegend()

        # Keep track of the actual PlotDataItems
        self._plot_curves = []

    def getCurvesJson(self) -> str:
        return self._curves_json

    def setCurvesJson(self, new_json: str):
        if self._curves_json != new_json:
            self._curves_json = new_json
            self._rebuild_curves()

    curvesJson = Property(str, fget=getCurvesJson, fset=setCurvesJson)

    def _rebuild_curves(self):
        """
        Parse the JSON, remove old plot items, create new ones with dummy data.
        """
        # Remove old
        for c in self._plot_curves:
            self.plot_item.removeItem(c)
        self._plot_curves.clear()

        # Parse the JSON
        try:
            data = json.loads(self._curves_json)
            if not isinstance(data, list):
                raise ValueError("curvesJson must be a JSON list.")
        except Exception:
            # If parse fails, just do nothing
            return

        # Create new PlotDataItems
        for idx, cdef in enumerate(data):
            label = cdef.get("label", f"Curve{idx + 1}")
            color = cdef.get("color", "blue")

            # Dummy data
            x = [0, 1, 2, 3, 4]
            y = [val + idx for val in x]

            item = pg.PlotDataItem(x, y, pen=color, name=label)
            self.plot_item.addItem(item)
            self._plot_curves.append(item)


if __name__ == "__main__":
    import sys
    from qtpy.QtWidgets import QApplication
    import json

    app = QApplication(sys.argv)
    w = WaveformPlot()
    w.curvesJson = json.dumps(
        [{"label": "FirstCurve", "color": "red"}, {"label": "SecondCurve", "color": "green"}]
    )
    w.show()
    sys.exit(app.exec_())
