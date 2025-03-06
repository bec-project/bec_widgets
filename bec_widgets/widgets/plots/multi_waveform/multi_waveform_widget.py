import os
from typing import Literal

import pyqtgraph as pg
from bec_lib.device import ReadoutPriority
from bec_lib.logger import bec_logger
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.settings_dialog import SettingsDialog
from bec_widgets.qt_utils.toolbar import (
    DeviceSelectionAction,
    MaterialIconAction,
    ModularToolBar,
    SeparatorAction,
    WidgetAction,
)
from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.containers.figure import BECFigure
from bec_widgets.widgets.containers.figure.plots.axis_settings import AxisSettings
from bec_widgets.widgets.containers.figure.plots.multi_waveform.multi_waveform import (
    BECMultiWaveformConfig,
)
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget

logger = bec_logger.logger


class BECMultiWaveformWidget(BECWidget, QWidget):
    PLUGIN = True
    ICON_NAME = "ssid_chart"
    USER_ACCESS = [
        "curves",
        "set_monitor",
        "set_curve_highlight",
        "set_opacity",
        "set_curve_limit",
        "set_buffer_flush",
        "set_highlight_last_curve",
        "set_colormap",
        "set",
        "set_title",
        "set_x_label",
        "set_y_label",
        "set_x_scale",
        "set_y_scale",
        "set_x_lim",
        "set_y_lim",
        "set_grid",
        "set_colormap",
        "enable_fps_monitor",
        "lock_aspect_ratio",
        "export",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        config: BECMultiWaveformConfig | dict = None,
        client=None,
        gui_id: str | None = None,
        **kwargs,
    ) -> None:
        if config is None:
            config = BECMultiWaveformConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = BECMultiWaveformConfig(**config)
        super().__init__(client=client, gui_id=gui_id, **kwargs)
        QWidget.__init__(self, parent)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.fig = BECFigure()
        self.colormap_button = BECColorMapWidget(cmap="magma")
        self.toolbar = ModularToolBar(
            actions={
                "monitor": DeviceSelectionAction(
                    "",
                    DeviceComboBox(
                        device_filter=BECDeviceFilter.DEVICE,
                        readout_priority_filter=ReadoutPriority.ASYNC,
                    ),
                ),
                "connect": MaterialIconAction(icon_name="link", tooltip="Connect Device"),
                "separator_0": SeparatorAction(),
                "colormap": WidgetAction(widget=self.colormap_button),
                "separator_1": SeparatorAction(),
                "save": MaterialIconAction(icon_name="save", tooltip="Open Export Dialog"),
                "matplotlib": MaterialIconAction(
                    icon_name="photo_library", tooltip="Open Matplotlib Plot"
                ),
                "separator_2": SeparatorAction(),
                "drag_mode": MaterialIconAction(
                    icon_name="drag_pan", tooltip="Drag Mouse Mode", checkable=True
                ),
                "rectangle_mode": MaterialIconAction(
                    icon_name="frame_inspect", tooltip="Rectangle Zoom Mode", checkable=True
                ),
                "auto_range": MaterialIconAction(
                    icon_name="open_in_full", tooltip="Autorange Plot"
                ),
                "crosshair": MaterialIconAction(
                    icon_name="point_scan", tooltip="Show Crosshair", checkable=True
                ),
                "separator_3": SeparatorAction(),
                "fps_monitor": MaterialIconAction(
                    icon_name="speed", tooltip="Show FPS Monitor", checkable=True
                ),
                "axis_settings": MaterialIconAction(
                    icon_name="settings", tooltip="Open Configuration Dialog"
                ),
            },
            target_widget=self,
        )

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.fig)

        self.waveform = self.fig.multi_waveform()  # FIXME config should be injected here
        self.config = config

        self.create_multi_waveform_controls()

        self._hook_actions()
        self.waveform.monitor_signal_updated.connect(self.update_controls_limits)

    def create_multi_waveform_controls(self):
        """
        Create the controls for the multi waveform widget.
        """
        current_path = os.path.dirname(__file__)
        self.controls = UILoader(self).loader(
            os.path.join(current_path, "multi_waveform_controls.ui")
        )
        self.layout.addWidget(self.controls)

        # Hook default controls properties
        self.controls.checkbox_highlight.setChecked(self.config.highlight_last_curve)
        self.controls.spinbox_opacity.setValue(self.config.opacity)
        self.controls.slider_opacity.setValue(self.config.opacity)
        self.controls.spinbox_max_trace.setValue(self.config.curve_limit)
        self.controls.checkbox_flush_buffer.setChecked(self.config.flush_buffer)

        # Connect signals
        self.controls.spinbox_max_trace.valueChanged.connect(self.set_curve_limit)
        self.controls.checkbox_flush_buffer.toggled.connect(self.set_buffer_flush)
        self.controls.slider_opacity.valueChanged.connect(self.controls.spinbox_opacity.setValue)
        self.controls.spinbox_opacity.valueChanged.connect(self.controls.slider_opacity.setValue)
        self.controls.slider_opacity.valueChanged.connect(self.set_opacity)
        self.controls.spinbox_opacity.valueChanged.connect(self.set_opacity)
        self.controls.slider_index.valueChanged.connect(self.controls.spinbox_index.setValue)
        self.controls.spinbox_index.valueChanged.connect(self.controls.slider_index.setValue)
        self.controls.slider_index.valueChanged.connect(self.set_curve_highlight)
        self.controls.spinbox_index.valueChanged.connect(self.set_curve_highlight)
        self.controls.checkbox_highlight.toggled.connect(self.set_highlight_last_curve)

        # Trigger first round of settings
        self.set_curve_limit(self.config.curve_limit)
        self.set_opacity(self.config.opacity)
        self.set_highlight_last_curve(self.config.highlight_last_curve)

    @Slot()
    def update_controls_limits(self):
        """
        Update the limits of the controls.
        """
        num_curves = len(self.waveform.curves)
        if num_curves == 0:
            num_curves = 1  # Avoid setting max to 0
        current_index = num_curves - 1
        self.controls.slider_index.setMinimum(0)
        self.controls.slider_index.setMaximum(self.waveform.number_of_visible_curves - 1)
        self.controls.spinbox_index.setMaximum(self.waveform.number_of_visible_curves - 1)
        if self.controls.checkbox_highlight.isChecked():
            self.controls.slider_index.setValue(current_index)
            self.controls.spinbox_index.setValue(current_index)

    def _hook_actions(self):
        self.toolbar.widgets["connect"].action.triggered.connect(self._connect_action)
        # Separator 0
        self.toolbar.widgets["save"].action.triggered.connect(self.export)
        self.toolbar.widgets["matplotlib"].action.triggered.connect(self.export_to_matplotlib)
        self.toolbar.widgets["colormap"].widget.colormap_changed_signal.connect(self.set_colormap)
        # Separator 1
        self.toolbar.widgets["drag_mode"].action.triggered.connect(self.enable_mouse_pan_mode)
        self.toolbar.widgets["rectangle_mode"].action.triggered.connect(
            self.enable_mouse_rectangle_mode
        )
        self.toolbar.widgets["auto_range"].action.triggered.connect(self._auto_range_from_toolbar)
        self.toolbar.widgets["crosshair"].action.triggered.connect(self.waveform.toggle_crosshair)
        # Separator 2
        self.toolbar.widgets["fps_monitor"].action.triggered.connect(self.enable_fps_monitor)
        self.toolbar.widgets["axis_settings"].action.triggered.connect(self.show_axis_settings)

    ###################################
    # Dialog Windows
    ###################################
    @SafeSlot(popup_error=True)
    def _connect_action(self):
        monitor_combo = self.toolbar.widgets["monitor"].device_combobox
        monitor_name = monitor_combo.currentText()
        self.set_monitor(monitor=monitor_name)
        monitor_combo.setStyleSheet("QComboBox { background-color: " "; }")

    def show_axis_settings(self):
        dialog = SettingsDialog(
            self,
            settings_widget=AxisSettings(),
            window_title="Axis Settings",
            config=self.waveform._config_dict["axis"],
        )
        dialog.exec()

    ########################################
    # User Access Methods from MultiWaveform
    ########################################
    @property
    def curves(self) -> list[pg.PlotDataItem]:
        """
        Get the curves of the plot widget as a list
        Returns:
            list: List of curves.
        """
        return list(self.waveform.curves)

    @curves.setter
    def curves(self, value: list[pg.PlotDataItem]):
        self.waveform.curves = value

    @SafeSlot(popup_error=True)
    def set_monitor(self, monitor: str) -> None:
        """
        Set the monitor of the plot widget.

        Args:
            monitor(str): The monitor to set.
        """
        self.waveform.set_monitor(monitor)
        if self.toolbar.widgets["monitor"].device_combobox.currentText() != monitor:
            self.toolbar.widgets["monitor"].device_combobox.setCurrentText(monitor)
            self.toolbar.widgets["monitor"].device_combobox.setStyleSheet(
                "QComboBox { background-color: " "; }"
            )

    @SafeSlot(int)
    def set_curve_highlight(self, index: int) -> None:
        """
        Set the curve highlight of the plot widget by index

        Args:
            index(int): The index of the curve to highlight.
        """
        if self.controls.checkbox_highlight.isChecked():
            # If always highlighting the last curve, set index to -1
            self.waveform.set_curve_highlight(-1)
        else:
            self.waveform.set_curve_highlight(index)

    @SafeSlot(int)
    def set_opacity(self, opacity: int) -> None:
        """
        Set the opacity of the plot widget.

        Args:
            opacity(int): The opacity to set.
        """
        self.waveform.set_opacity(opacity)

    @SafeSlot(int)
    def set_curve_limit(self, curve_limit: int) -> None:
        """
        Set the maximum number of traces to display on the plot widget.

        Args:
            curve_limit(int): The maximum number of traces to display.
        """
        flush_buffer = self.controls.checkbox_flush_buffer.isChecked()
        self.waveform.set_curve_limit(curve_limit, flush_buffer)
        self.update_controls_limits()

    @SafeSlot(bool)
    def set_buffer_flush(self, flush_buffer: bool) -> None:
        """
        Set the buffer flush property of the plot widget.

        Args:
            flush_buffer(bool): True to flush the buffer, False to not flush the buffer.
        """
        curve_limit = self.controls.spinbox_max_trace.value()
        self.waveform.set_curve_limit(curve_limit, flush_buffer)
        self.update_controls_limits()

    @SafeSlot(bool)
    def set_highlight_last_curve(self, enable: bool) -> None:
        """
        Enable or disable highlighting of the last curve.

        Args:
            enable(bool): True to enable highlighting of the last curve, False to disable.
        """
        self.waveform.config.highlight_last_curve = enable
        if enable:
            self.controls.slider_index.setEnabled(False)
            self.controls.spinbox_index.setEnabled(False)
            self.controls.checkbox_highlight.setChecked(True)
            self.waveform.set_curve_highlight(-1)
        else:
            self.controls.slider_index.setEnabled(True)
            self.controls.spinbox_index.setEnabled(True)
            self.controls.checkbox_highlight.setChecked(False)
            index = self.controls.spinbox_index.value()
            self.waveform.set_curve_highlight(index)

    @SafeSlot()
    def set_colormap(self, colormap: str) -> None:
        """
        Set the colormap of the plot widget.

        Args:
            colormap(str): The colormap to set.
        """
        self.waveform.set_colormap(colormap)

    ###################################
    # User Access Methods from PlotBase
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
            title(str): The title to set.
        """
        self.waveform.set_title(title)

    def set_x_label(self, x_label: str):
        """
        Set the x-axis label of the plot widget.

        Args:
            x_label(str): The x-axis label to set.
        """
        self.waveform.set_x_label(x_label)

    def set_y_label(self, y_label: str):
        """
        Set the y-axis label of the plot widget.

        Args:
            y_label(str): The y-axis label to set.
        """
        self.waveform.set_y_label(y_label)

    def set_x_scale(self, x_scale: Literal["linear", "log"]):
        """
        Set the x-axis scale of the plot widget.

        Args:
            x_scale(str): The x-axis scale to set.
        """
        self.waveform.set_x_scale(x_scale)

    def set_y_scale(self, y_scale: Literal["linear", "log"]):
        """
        Set the y-axis scale of the plot widget.

        Args:
            y_scale(str): The y-axis scale to set.
        """
        self.waveform.set_y_scale(y_scale)

    def set_x_lim(self, x_lim: tuple):
        """
        Set x-axis limits of the plot widget.

        Args:
            x_lim(tuple): The x-axis limits to set.
        """
        self.waveform.set_x_lim(x_lim)

    def set_y_lim(self, y_lim: tuple):
        """
        Set y-axis limits of the plot widget.

        Args:
            y_lim(tuple): The y-axis limits to set.
        """
        self.waveform.set_y_lim(y_lim)

    def set_legend_label_size(self, legend_label_size: int):
        """
        Set the legend label size of the plot widget.

        Args:
            legend_label_size(int): The legend label size to set.
        """
        self.waveform.set_legend_label_size(legend_label_size)

    def set_auto_range(self, enabled: bool, axis: str = "xy"):
        """
        Set the auto range of the plot widget.

        Args:
            enabled(bool): True to enable auto range, False to disable.
            axis(str): The axis to set the auto range for. Default is "xy".
        """
        self.waveform.set_auto_range(enabled, axis)

    def enable_fps_monitor(self, enabled: bool):
        """
        Enable or disable the FPS monitor

        Args:
            enabled(bool): True to enable the FPS monitor, False to disable.
        """
        self.waveform.enable_fps_monitor(enabled)
        if self.toolbar.widgets["fps_monitor"].action.isChecked() != enabled:
            self.toolbar.widgets["fps_monitor"].action.setChecked(enabled)

    @SafeSlot()
    def _auto_range_from_toolbar(self):
        """
        Set the auto range of the plot widget from the toolbar.
        """
        self.waveform.set_auto_range(True, "xy")

    def set_grid(self, x_grid: bool, y_grid: bool):
        """
        Set the grid of the plot widget.

        Args:
            x_grid(bool): True to enable the x-grid, False to disable.
            y_grid(bool): True to enable the y-grid, False to disable.
        """
        self.waveform.set_grid(x_grid, y_grid)

    def set_outer_axes(self, show: bool):
        """
        Set the outer axes of the plot widget.

        Args:
            show(bool): True to show the outer axes, False to hide.
        """
        self.waveform.set_outer_axes(show)

    def lock_aspect_ratio(self, lock: bool):
        """
        Lock the aspect ratio of the plot widget.

        Args:
            lock(bool): True to lock the aspect ratio, False to unlock.
        """
        self.waveform.lock_aspect_ratio(lock)

    @SafeSlot()
    def enable_mouse_rectangle_mode(self):
        """
        Enable the mouse rectangle mode of the plot widget.
        """
        self.toolbar.widgets["rectangle_mode"].action.setChecked(True)
        self.toolbar.widgets["drag_mode"].action.setChecked(False)
        self.waveform.plot_item.getViewBox().setMouseMode(pg.ViewBox.RectMode)

    @SafeSlot()
    def enable_mouse_pan_mode(self):
        """
        Enable the mouse pan mode of the plot widget.
        """
        self.toolbar.widgets["drag_mode"].action.setChecked(True)
        self.toolbar.widgets["rectangle_mode"].action.setChecked(False)
        self.waveform.plot_item.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    def export(self):
        """
        Export the plot widget.
        """
        self.waveform.export()

    def export_to_matplotlib(self):
        """
        Export the plot widget to matplotlib.
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
    def cleanup(self):
        self.fig.cleanup()
        return super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECMultiWaveformWidget()
    widget.show()
    sys.exit(app.exec())
