"""
waveform_plot.py
A minimal demonstration widget with multiple properties:
  - deviceName (str)
  - curvesJson (str)
  - someFlag (bool)

It uses pyqtgraph to show dummy curves from 'curvesJson'.
"""

import json

import pyqtgraph as pg
from qtpy.QtCore import Property, QPointF
from qtpy.QtWidgets import QVBoxLayout, QWidget


class WaveformPlot(QWidget):
    """
    Minimal demonstration of a multi-property widget:
      - deviceName   (string)
      - curvesJson   (string containing JSON)
      - someFlag     (boolean)
    """

    ICON_NAME = "multiline_chart"  # For a designer icon, if desired

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device_name = "MyDevice"
        self._curves_json = "[]"
        self._some_flag = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_item = pg.PlotItem()
        self.plot_widget = pg.PlotWidget(plotItem=self.plot_item)
        layout.addWidget(self.plot_widget)

        self._plot_curves = []

    # ------------------------------------------------------------------------
    # Property #1: deviceName
    # ------------------------------------------------------------------------
    def getDeviceName(self) -> str:
        return self._device_name

    def setDeviceName(self, val: str):
        if self._device_name != val:
            self._device_name = val
            # You might do something in your real code
            # e.g. re-subscribe to a device, etc.

    deviceName = Property(str, fget=getDeviceName, fset=setDeviceName)

    # ------------------------------------------------------------------------
    # Property #2: curvesJson
    # ------------------------------------------------------------------------
    def getCurvesJson(self) -> str:
        return self._curves_json

    def setCurvesJson(self, new_json: str):
        if self._curves_json != new_json:
            self._curves_json = new_json
            self._rebuild_curves()

    curvesJson = Property(str, fget=getCurvesJson, fset=setCurvesJson, designable=False)

    # ------------------------------------------------------------------------
    # Property #3: someFlag
    # ------------------------------------------------------------------------
    def getSomeFlag(self) -> bool:
        return self._some_flag

    def setSomeFlag(self, val: bool):
        if self._some_flag != val:
            self._some_flag = val
            # React to the flag in your real code if needed

    someFlag = Property(bool, fget=getSomeFlag, fset=setSomeFlag)

    # ------------------------------------------------------------------------
    # Re-build the curves from the JSON
    # ------------------------------------------------------------------------
    def _rebuild_curves(self):
        # Remove existing PlotDataItems
        for c in self._plot_curves:
            self.plot_item.removeItem(c)
        self._plot_curves.clear()

        # Try parse JSON
        try:
            arr = json.loads(self._curves_json)
            if not isinstance(arr, list):
                raise ValueError("curvesJson must be a JSON list.")
        except Exception:
            # If parsing fails, do nothing
            return

        # Create new PlotDataItems from the JSON
        for idx, cdef in enumerate(arr):
            label = cdef.get("label", f"Curve{idx + 1}")
            color = cdef.get("color", "blue")

            x = [0, 1, 2, 3, 4]
            y = [val + idx for val in x]

            item = pg.PlotDataItem(x, y, pen=color, name=label)
            self.plot_item.addItem(item)
            self._plot_curves.append(item)


# Optional standalone test
if __name__ == "__main__":
    import json
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = WaveformPlot()
    w.deviceName = "TestDevice"
    w.curvesJson = json.dumps([{"label": "A", "color": "red"}, {"label": "B", "color": "green"}])
    w.someFlag = True
    w.show()
    sys.exit(app.exec_())
