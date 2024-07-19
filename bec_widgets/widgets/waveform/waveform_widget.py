from __future__ import annotations

import sys
from typing import Literal

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot, WarningPopupUtility
from bec_widgets.qt_utils.settings_dialog import SettingsDialog
from bec_widgets.qt_utils.toolbar import ModularToolBar, SeparatorAction
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.figure.plots.axis_settings import AxisSettings
from bec_widgets.widgets.figure.plots.waveform.waveform import Waveform1DConfig
from bec_widgets.widgets.figure.plots.waveform.waveform_curve import BECCurve
from bec_widgets.widgets.waveform.waveform_toolbar.curve_dialog.curve_dialog import CurveSettings
from bec_widgets.widgets.waveform.waveform_toolbar.dap_summary_dialog.dap_summary_dialog import (
    FitSummaryWidget,
)
from bec_widgets.widgets.waveform.waveform_toolbar.waveform_toolbar import *

try:
    import pandas as pd
except ImportError:
    pd = None


class BECWaveformWidget(BECWidget, QWidget):
    USER_ACCESS = [
        "curves",
        "plot",
        "add_dap",
        "get_dap_params",
        "remove_curve",
        "scan_history",
        "get_all_data",
        "set",
        "set_x",
        "set_title",
        "set_x_label",
        "set_y_label",
        "set_x_scale",
        "set_y_scale",
        "set_x_lim",
        "set_y_lim",
        "set_legend_label_size",
        "set_grid",
        "lock_aspect_ratio",
        "export",
        "export_to_matplotlib",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        config: Waveform1DConfig | dict = None,
        client=None,
        gui_id: str | None = None,
    ) -> None:
        if config is None:
            config = Waveform1DConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = Waveform1DConfig(**config)
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.fig = BECFigure()
        self.toolbar = ModularToolBar(
            actions={
                "save": SaveAction(),
                "matplotlib": MatplotlibAction(),
                "separator_1": SeparatorAction(),
                "drag_mode": DragModeAction(),
                "rectangle_mode": RectangeModeAction(),
                "auto_range": AutoRangeAction(),
                "separator_2": SeparatorAction(),
                "curves": CurveAction(),
                "fit_params": FitParamsAction(),
                "axis_settings": SettingsAction(),
                # "separator_3": SeparatorAction(),
                # "import": ImportAction(),
                # "export": ExportAction(),
            },
            target_widget=self,
        )

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.fig)

        self.warning_util = WarningPopupUtility(self)

        self.waveform = self.fig.plot()
        self.waveform.apply_config(config)

        self.config = config

        self._hook_actions()

    def _hook_actions(self):
        self.toolbar.widgets["save"].action.triggered.connect(self.export)
        self.toolbar.widgets["matplotlib"].action.triggered.connect(self.export_to_matplotlib)
        self.toolbar.widgets["drag_mode"].action.triggered.connect(self.enable_mouse_pan_mode)
        self.toolbar.widgets["rectangle_mode"].action.triggered.connect(
            self.enable_mouse_rectangle_mode
        )
        self.toolbar.widgets["auto_range"].action.triggered.connect(self._auto_range_from_toolbar)
        self.toolbar.widgets["curves"].action.triggered.connect(self.show_curve_settings)
        self.toolbar.widgets["fit_params"].action.triggered.connect(self.show_fit_summary_dialog)
        self.toolbar.widgets["axis_settings"].action.triggered.connect(self.show_axis_settings)
        # self.toolbar.widgets["import"].action.triggered.connect(
        #     lambda: self.load_config(path=None, gui=True)
        # )
        # self.toolbar.widgets["export"].action.triggered.connect(
        #     lambda: self.save_config(path=None, gui=True)
        # )

    ###################################
    # Dialog Windows
    ###################################
    def show_axis_settings(self):
        dialog = SettingsDialog(
            self,
            settings_widget=AxisSettings(),
            window_title="Axis Settings",
            config=self._config_dict["axis"],
        )
        dialog.exec()

    def show_curve_settings(self):
        dialog = SettingsDialog(
            self,
            settings_widget=CurveSettings(),
            window_title="Curve Settings",
            config=self.waveform._curves_data,
        )
        dialog.resize(800, 600)
        dialog.exec()

    def show_fit_summary_dialog(self):
        dialog = FitSummaryWidget(target_widget=self)
        dialog.resize(800, 600)
        dialog.show()

    ###################################
    # User Access Methods from Waveform
    ###################################
    @property
    def curves(self) -> list[BECCurve]:
        """
        Get the curves of the plot widget as a list
        Returns:
            list: List of curves.
        """
        return self.waveform._curves

    @curves.setter
    def curves(self, value: list[BECCurve]):
        self.waveform._curves = value

    def get_curve(self, identifier) -> BECCurve:
        """
        Get the curve by its index or ID.

        Args:
            identifier(int|str): Identifier of the curve. Can be either an integer (index) or a string (curve_id).

        Returns:
            BECCurve: The curve object.
        """
        return self.waveform.get_curve(identifier)

    def set_colormap(self, colormap: str):
        """
        Set the colormap of the plot widget.

        Args:
            colormap(str, optional): Scale the colors of curves to colormap. If None, use the default color palette.
        """
        self.waveform.set_colormap(colormap)

    @SafeSlot(popup_error=True)
    def set_x(self, x_name: str, x_entry: str | None = None):
        """
        Change the x axis of the plot widget.

        Args:
            x_name(str): Name of the x signal.
                - "best_effort": Use the best effort signal.
                - "timestamp": Use the timestamp signal.
                - "index": Use the index signal.
                - Custom signal name of device from BEC.
            x_entry(str): Entry of the x signal.
        """
        self.waveform.set_x(x_name, x_entry)

    @SafeSlot(popup_error=True)
    def plot(
        self,
        arg1: list | np.ndarray | str | None = None,
        x: list | np.ndarray | None = None,
        y: list | np.ndarray | None = None,
        x_name: str | None = None,
        y_name: str | None = None,
        z_name: str | None = None,
        x_entry: str | None = None,
        y_entry: str | None = None,
        z_entry: str | None = None,
        color: str | None = None,
        color_map_z: str | None = "plasma",
        label: str | None = None,
        validate: bool = True,
        dap: str | None = None,  # TODO add dap custom curve wrapper
        **kwargs,
    ) -> BECCurve:
        """
        Plot a curve to the plot widget.
        Args:
            arg1(list | np.ndarray | str | None): First argument which can be x data(list | np.ndarray), y data(list | np.ndarray), or y_name(str).
            x(list | np.ndarray): Custom x data to plot.
            y(list | np.ndarray): Custom y data to plot.
            x_name(str): The name of the device for the x-axis.
            y_name(str): The name of the device for the y-axis.
            z_name(str): The name of the device for the z-axis.
            x_entry(str): The name of the entry for the x-axis.
            y_entry(str): The name of the entry for the y-axis.
            z_entry(str): The name of the entry for the z-axis.
            color(str): The color of the curve.
            color_map_z(str): The color map to use for the z-axis.
            label(str): The label of the curve.
            validate(bool): If True, validate the device names and entries.
            dap(str): The dap model to use for the curve. If not specified, none will be added.

        Returns:
            BECCurve: The curve object.
        """
        # self._check_if_scans_have_same_x(enabled=True, x_name_to_check=x_name)
        return self.waveform.plot(
            arg1=arg1,
            x=x,
            y=y,
            x_name=x_name,
            y_name=y_name,
            z_name=z_name,
            x_entry=x_entry,
            y_entry=y_entry,
            z_entry=z_entry,
            color=color,
            color_map_z=color_map_z,
            label=label,
            validate=validate,
            dap=dap,
            **kwargs,
        )

    @SafeSlot(popup_error=True)
    def add_dap(
        self,
        x_name: str,
        y_name: str,
        x_entry: str | None = None,
        y_entry: str | None = None,
        color: str | None = None,
        dap: str = "GaussianModel",
        validate_bec: bool = True,
        **kwargs,
    ) -> BECCurve:
        """
        Add LMFIT dap model curve to the plot widget.

        Args:
            x_name(str): Name of the x signal.
            x_entry(str): Entry of the x signal.
            y_name(str): Name of the y signal.
            y_entry(str): Entry of the y signal.
            color(str, optional): Color of the curve. Defaults to None.
            dap(str): The dap model to use for the curve.
            validate_bec(bool, optional): If True, validate the signal with BEC. Defaults to True.
            **kwargs: Additional keyword arguments for the curve configuration.

        Returns:
            BECCurve: The curve object.
        """
        return self.waveform.add_dap(
            x_name=x_name,
            y_name=y_name,
            x_entry=x_entry,
            y_entry=y_entry,
            color=color,
            dap=dap,
            validate_bec=validate_bec,
            **kwargs,
        )

    def get_dap_params(self) -> dict:
        """
        Get the DAP parameters of all DAP curves.

        Returns:
            dict: DAP parameters of all DAP curves.
        """

        return self.waveform.get_dap_params()

    def get_dap_summary(self) -> dict:
        """
        Get the DAP summary of all DAP curves.

        Returns:
            dict: DAP summary of all DAP curves.
        """
        return self.waveform.get_dap_summary()

    def remove_curve(self, *identifiers):
        """
        Remove a curve from the plot widget.

        Args:
            *identifiers: Identifier of the curve to be removed. Can be either an integer (index) or a string (curve_id).
        """
        self.waveform.remove_curve(*identifiers)

    def scan_history(self, scan_index: int = None, scan_id: str = None):
        """
        Update the scan curves with the data from the scan storage.
        Provide only one of scan_id or scan_index.

        Args:
            scan_id(str, optional): ScanID of the scan to be updated. Defaults to None.
            scan_index(int, optional): Index of the scan to be updated. Defaults to None.
        """
        self.waveform.scan_history(scan_index, scan_id)

    def get_all_data(self, output: Literal["dict", "pandas"] = "dict") -> dict | pd.DataFrame:
        """
        Extract all curve data into a dictionary or a pandas DataFrame.

        Args:
            output (Literal["dict", "pandas"]): Format of the output data.

        Returns:
            dict | pd.DataFrame: Data of all curves in the specified format.
        """
        try:
            import pandas as pd
        except ImportError:
            pd = None
            if output == "pandas":
                print(
                    "Pandas is not installed. "
                    "Please install pandas using 'pip install pandas'."
                    "Output will be dictionary instead."
                )
                output = "dict"
        return self.waveform.get_all_data(output)

    ###################################
    # User Access Methods from Plotbase
    ###################################

    def set(self, **kwargs):
        """
        Set the properties of the plot widget.

        Args:
            **kwargs: Keyword arguments for the properties to be set.

        Possible properties:
            - title: str
            - x_label: str
            - y_label: str
            - x_scale: Literal["linear", "log"]
            - y_scale: Literal["linear", "log"]
            - x_lim: tuple
            - y_lim: tuple
            - legend_label_size: int
        """
        self.waveform.set(**kwargs)

    def set_title(self, title: str):
        """
        Set the title of the plot widget.

        Args:
            title(str): Title of the plot.
        """
        self.waveform.set_title(title)

    def set_x_label(self, x_label: str):
        """
        Set the x-axis label of the plot widget.

        Args:
            x_label(str): Label of the x-axis.
        """
        self.waveform.set_x_label(x_label)

    def set_y_label(self, y_label: str):
        """
        Set the y-axis label of the plot widget.

        Args:
            y_label(str): Label of the y-axis.
        """
        self.waveform.set_y_label(y_label)

    def set_x_scale(self, x_scale: Literal["linear", "log"]):
        """
        Set the scale of the x-axis of the plot widget.

        Args:
            x_scale(Literal["linear", "log"]): Scale of the x-axis.
        """
        self.waveform.set_x_scale(x_scale)

    def set_y_scale(self, y_scale: Literal["linear", "log"]):
        """
        Set the scale of the y-axis of the plot widget.

        Args:
            y_scale(Literal["linear", "log"]): Scale of the y-axis.
        """
        self.waveform.set_y_scale(y_scale)

    def set_x_lim(self, x_lim: tuple):
        """
        Set the limits of the x-axis of the plot widget.

        Args:
            x_lim(tuple): Limits of the x-axis.
        """
        self.waveform.set_x_lim(x_lim)

    def set_y_lim(self, y_lim: tuple):
        """
        Set the limits of the y-axis of the plot widget.

        Args:
            y_lim(tuple): Limits of the y-axis.
        """
        self.waveform.set_y_lim(y_lim)

    def set_legend_label_size(self, legend_label_size: int):
        """
        Set the size of the legend labels of the plot widget.

        Args:
            legend_label_size(int): Size of the legend labels.
        """
        self.waveform.set_legend_label_size(legend_label_size)

    def set_auto_range(self, enabled: bool, axis: str = "xy"):
        """
        Set the auto range of the plot widget.

        Args:
            enabled(bool): If True, enable the auto range.
            axis(str, optional): The axis to enable the auto range.
                - "xy": Enable auto range for both x and y axis.
                - "x": Enable auto range for x axis.
                - "y": Enable auto range for y axis.
        """
        self.waveform.set_auto_range(enabled, axis)

    @SafeSlot()
    def _auto_range_from_toolbar(self):
        """
        Set the auto range of the plot widget from the toolbar.
        """
        self.waveform.set_auto_range(True, "xy")

    def set_grid(self, x_grid: bool, y_grid: bool):
        """
        Set the grid visibility of the plot widget.

        Args:
            x_grid(bool): Visibility of the x-axis grid.
            y_grid(bool): Visibility of the y-axis grid.
        """
        self.waveform.set_grid(x_grid, y_grid)

    def lock_aspect_ratio(self, lock: bool):
        """
        Lock the aspect ratio of the plot widget.

        Args:
            lock(bool): Lock the aspect ratio.
        """
        self.waveform.lock_aspect_ratio(lock)

    @SafeSlot()
    def enable_mouse_rectangle_mode(self):
        self.toolbar.widgets["rectangle_mode"].action.setChecked(True)
        self.toolbar.widgets["drag_mode"].action.setChecked(False)
        self.waveform.plot_item.getViewBox().setMouseMode(pg.ViewBox.RectMode)

    @SafeSlot()
    def enable_mouse_pan_mode(self):
        self.toolbar.widgets["drag_mode"].action.setChecked(True)
        self.toolbar.widgets["rectangle_mode"].action.setChecked(False)
        self.waveform.plot_item.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    def export(self):
        """
        Show the export dialog for the plot widget.
        """
        self.waveform.export()

    def export_to_matplotlib(self):
        """
        Export the plot widget to Matplotlib.
        """
        try:
            import matplotlib as mpl
        except ImportError:
            self.warning_util.show_warning(
                title="Matplotlib not installed",
                message="Matplotlib is required for this feature.",
                detailed_text="Please install matplotlib in your Python environment by using 'pip install matplotlib'.",
            )
            return
        self.waveform.export_to_matplotlib()

    #######################################
    # User Access Methods from BECConnector
    ######################################
    def load_config(self, path: str | None = None, gui: bool = False):
        """
        Load the configuration of the widget from YAML.

        Args:
            path(str): Path to the configuration file for non-GUI dialog mode.
            gui(bool): If True, use the GUI dialog to load the configuration file.
        """
        self.fig.load_config(path=path, gui=gui)

    def save_config(self, path: str | None = None, gui: bool = False):
        """
        Save the configuration of the widget to YAML.

        Args:
            path(str): Path to save the configuration file for non-GUI dialog mode.
            gui(bool): If True, use the GUI dialog to save the configuration file.
        """
        self.fig.save_config(path=path, gui=gui)

    def cleanup(self):
        self.fig.cleanup()
        self.client.shutdown()
        return super().cleanup()


def main():  # pragma: no cover

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECWaveformWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
