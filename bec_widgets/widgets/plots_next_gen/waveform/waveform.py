from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from collections import defaultdict
from typing import Literal

from bec_lib.device import ReadoutPriority
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget

from bec_lib.endpoints import MessageEndpoints
from bec_widgets.qt_utils.error_popups import SafeProperty
from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.colors import set_theme
from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase
from bec_widgets.widgets.plots_next_gen.waveform.curve import Curve, CurveConfig


class Waveform(PlotBase):
    PLUGIN = False
    ICON_NAME = "show_chart"

    READOUT_PRIORITY_HANDLER = {
        ReadoutPriority.ON_REQUEST: "on_request",
        ReadoutPriority.BASELINE: "baseline",
        ReadoutPriority.MONITORED: "monitored",
        ReadoutPriority.ASYNC: "async",
        ReadoutPriority.CONTINUOUS: "continuous",
    }

    # TODO implement signals
    # scan_signal_update = Signal()
    # async_signal_update = Signal()
    # dap_params_update = Signal(dict, dict)
    # dap_summary_update = Signal(dict, dict)
    # autorange_signal = Signal()
    # new_scan = Signal()
    # roi_changed = Signal(tuple)
    # roi_active = Signal(bool)
    # request_dap_refresh = Signal()
    def __init__(
        self,
        parent: QWidget | None = None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
    ):
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, config=config, client=client, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        # For PropertyManager identification
        self.setObjectName("Waveform")

        # Curve data
        self._curves_data = defaultdict(
            dict
        )  # TODO maybe not needed since I want to iterate through the curve list just
        self._curves = self.plot_item.curves
        self._mode: Literal["sync, async"] = "sync"

        # Scan data
        self.old_scan_id = None
        self.scan_id = None
        self.scan_item = None

        # TODO review relevant bec_dispatcher signals
        # Scan segment update proxy
        # self.proxy_update_plot = pg.SignalProxy(
        #     self.scan_signal_update, rateLimit=25, slot=self._update_scan_curves
        # )
        # self.proxy_update_dap = pg.SignalProxy(
        #     self.scan_signal_update, rateLimit=25, slot=self.refresh_dap
        # )
        # self.async_signal_update.connect(self.replot_async_curve)
        # self.autorange_signal.connect(self.auto_range)
        # self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())

    ################################################################################
    # High Level methods for API
    ################################################################################
    # TODO such as plot, add, remove curve, etc.
    def plot(
        self,
        arg1: list | np.ndarray | str | None = None,
        y: list | np.ndarray | None = None,
        x: list | np.ndarray | None = None,
        x_name: str | None = None,
        y_name: str | None = None,
        z_name: str | None = None,
        x_entry: str | None = None,
        y_entry: str | None = None,
        z_entry: str | None = None,
        color: str | None = None,
        color_map_z: str | None = "magma",
        label: str | None = None,
        validate: bool = True,
        dap: str | None = None,  # TODO add dap custom curve wrapper
        **kwargs,
    ) -> Curve:
        # TODO review the docstring
        """
        Plot a curve to the plot widget.

        Args:
            arg1(list | np.ndarray | str | None): First argument which can be x data, y data, or y_name.
            y(list | np.ndarray): Custom y data to plot.
            x(list | np.ndarray): Custom y data to plot.
            x_name(str): Name of the x signal.
                - "best_effort": Use the best effort signal.
                - "timestamp": Use the timestamp signal.
                - "index": Use the index signal.
                - Custom signal name of device from BEC.
            y_name(str): The name of the device for the y-axis.
            z_name(str): The name of the device for the z-axis.
            x_entry(str): The name of the entry for the x-axis.
            y_entry(str): The name of the entry for the y-axis.
            z_entry(str): The name of the entry for the z-axis.
            color(str): The color of the curve.
            color_map_z(str): The color map to use for the z-axis.
            label(str): The label of the curve.
            validate(bool): If True, validate the device names and entries.
            dap(str): The dap model to use for the curve, only available for sync devices. If not specified, none will be added.

        Returns:
            Curve: The curve object.
        """
        # TODO implement the plot method

    ################################################################################
    # Curve Management Methods
    ################################################################################
    # TODO implement curve management methods
    @SafeProperty(str)
    def curve_json(self) -> str:
        json_data = {}
        return json_data

    @curve_json.setter
    def curve_json(self, json_data: str):
        pass

    @property
    def curves(self) -> list[Curve]:
        """
        Get the curves of the plot widget as a list.

        Returns:
            list: List of curves.
        """
        return self._curves

    @curves.setter
    def curves(self, value: list[Curve]):
        self._curves = value

    def _add_curve(
        self,
        name: str,
        source: str,  # TODO maybe not implement if source is unknown
        config: CurveConfig,
        data: tuple[list | np.ndarray, list | np.ndarray] = None,
    ):
        curve = Curve(name=name, config=config, parent_item=self)
        self.plot_item.addItem(curve)

        return curve

        # TODO create logic for sync and async curves to switch mode and not allow combination of them
        # TODO user should be also notified about the mode change

    def _remove_curve_by_source(self, source: str):
        # TODO consider if this is needed
        pass

    ################################################################################
    # BEC Update Methods
    ################################################################################
    # TODO here will go bec related update slots

    ################################################################################
    # Export Methods
    ################################################################################


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    set_theme("dark")
    widget = PlotBase()
    widget.show()
    # Just some example data and parameters to test
    widget.y_grid = True
    widget.plot_item.plot([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])

    sys.exit(app.exec_())
