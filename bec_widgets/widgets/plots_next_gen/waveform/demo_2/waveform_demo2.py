import json
from typing import List

import pyqtgraph as pg
from qtpy.QtCore import Property
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.widgets.plots_next_gen.waveform.demo_2.demo_curve import BECCurve, CurveConfig


class WaveformPlotDemo2(QWidget):
    """
    A Plot widget that stores multiple curves in a single JSON property (`curvesJson`).
    Internally, we keep a list of (CurveConfig, BECCurve).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves_json = "[]"
        self._curves: List[BECCurve] = []  # the actual PlotDataItems
        self._curve_configs: List[CurveConfig] = []

        layout = QVBoxLayout(self)
        self.plot_item = pg.PlotItem()
        self.plot_widget = pg.PlotWidget(plotItem=self.plot_item)
        layout.addWidget(self.plot_widget)
        self.plot_item.addLegend()

    # ------------------------------------------------------------------------
    # QProperty: curvesJson
    # ------------------------------------------------------------------------
    def getCurvesJson(self) -> str:
        return self._curves_json

    def setCurvesJson(self, val: str):
        if self._curves_json != val:
            self._curves_json = val
            self._rebuild_curves_from_json()

    curvesJson = Property(str, fget=getCurvesJson, fset=setCurvesJson)

    # ------------------------------------------------------------------------
    # Internal method: parse JSON -> create/update BECCurve objects
    # ------------------------------------------------------------------------
    def _rebuild_curves_from_json(self):
        # 1) Remove existing items from the plot
        for c in self._curves:
            self.plot_item.removeItem(c)
        self._curves.clear()
        self._curve_configs.clear()

        # 2) Parse JSON
        try:
            raw_list = json.loads(self._curves_json)
            if not isinstance(raw_list, list):
                raise ValueError("curvesJson must be a JSON list.")
        except Exception:
            raw_list = []

        # 3) Convert each raw dict -> CurveConfig -> BECCurve
        for entry in raw_list:
            try:
                cfg = CurveConfig(**entry)
            except Exception:
                # fallback or skip
                continue
            curve_obj = BECCurve(config=cfg, parent=self)
            # For demonstration, set some dummy data
            xdata = [0, 1, 2, 3, 4]
            ydata = [val + hash(cfg.label) % 3 for val in xdata]
            curve_obj.setData(xdata, ydata)

            self.plot_item.addItem(curve_obj)
            self._curves.append(curve_obj)
            self._curve_configs.append(cfg)

    # ------------------------------------------------------------------------
    # CLI / dynamic methods to add, remove, or modify curves at runtime
    # ------------------------------------------------------------------------
    def list_curve_labels(self) -> list[str]:
        return [cfg.label for cfg in self._curve_configs]

    def get_curve(self, label: str) -> BECCurve:
        # Return the actual BECCurve object (or a config, or both)
        for c in self._curves:
            if c.config.label == label:
                return c
        raise ValueError(f"No curve with label='{label}'")

    def add_curve(self, cfg: CurveConfig):
        """
        Add a new curve from code. We just insert the new config
        into the list, then re-serialize to JSON => triggers rebuild
        """
        # insert new config to the internal list
        self._curve_configs.append(cfg)
        self._sync_json_from_configs()

    def remove_curve(self, label: str):
        for i, c in enumerate(self._curve_configs):
            if c.label == label:
                self._curve_configs.pop(i)
                break
        else:
            raise ValueError(f"No curve with label='{label}' found to remove.")

        self._sync_json_from_configs()

    def set_curve_property(self, label: str, **kwargs):
        """
        For example, set_curve_property("Curve1", color="red", pen_width=4)
        We'll update the pydantic model, then re-sync to JSON, rebuild.
        """
        c = self._find_config(label)
        for k, v in kwargs.items():
            setattr(c, k, v)  # pydantic assignment
        self._sync_json_from_configs()

    def _find_config(self, label: str) -> CurveConfig:
        for cfg in self._curve_configs:
            if cfg.label == label:
                return cfg
        raise ValueError(f"No config with label='{label}' found.")

    def _sync_json_from_configs(self):
        """
        Re-serialize our internal curve configs -> JSON string,
        call setCurvesJson(...) => triggers the rebuild in the same widget
        so the user and Designer stay in sync
        """
        raw_list = [cfg.dict() for cfg in self._curve_configs]
        new_json = json.dumps(raw_list, indent=2)
        self.setCurvesJson(new_json)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    w = WaveformPlotDemo2()
    w.show()
    w.add_curve(CurveConfig(label="Curve1", color="red"))
    w.add_curve(CurveConfig(label="Curve2", color="blue"))
    app.exec_()
