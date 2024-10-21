from __future__ import annotations

import sys
from typing import Literal, Optional

import pyqtgraph as pg
from bec_lib.device import ReadoutPriority
from qtpy.QtWidgets import QComboBox, QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot, WarningPopupUtility
from bec_widgets.qt_utils.settings_dialog import SettingsDialog
from bec_widgets.qt_utils.toolbar import (
    DeviceSelectionAction,
    MaterialIconAction,
    ModularToolBar,
    SeparatorAction,
    WidgetAction,
)
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.figure.plots.axis_settings import AxisSettings
from bec_widgets.widgets.figure.plots.image.image import ImageConfig
from bec_widgets.widgets.figure.plots.image.image_item import BECImageItem


class BECImageWidget(BECWidget, QWidget):
    ICON_NAME = "image"
    USER_ACCESS = [
        "image",
        "set",
        "set_title",
        "set_x_label",
        "set_y_label",
        "set_x_scale",
        "set_y_scale",
        "set_x_lim",
        "set_y_lim",
        "set_vrange",
        "set_fft",
        "set_transpose",
        "set_rotation",
        "set_log",
        "set_grid",
        "enable_fps_monitor",
        "lock_aspect_ratio",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ImageConfig | dict = None,
        client=None,
        gui_id: str | None = None,
    ) -> None:
        if config is None:
            config = ImageConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = ImageConfig(**config)
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.fig = BECFigure()
        self.dim_combo_box = QComboBox()
        self.dim_combo_box.addItems(["1d", "2d"])
        self.toolbar = ModularToolBar(
            actions={
                "monitor": DeviceSelectionAction(
                    "Monitor:",
                    DeviceComboBox(
                        device_filter=BECDeviceFilter.DEVICE,
                        readout_priority_filter=[ReadoutPriority.ASYNC],
                    ),
                ),
                "monitor_type": WidgetAction(widget=self.dim_combo_box),
                "connect": MaterialIconAction(icon_name="link", tooltip="Connect Device"),
                "separator_0": SeparatorAction(),
                "save": MaterialIconAction(icon_name="save", tooltip="Open Export Dialog"),
                "separator_1": SeparatorAction(),
                "drag_mode": MaterialIconAction(
                    icon_name="open_with", tooltip="Drag Mouse Mode", checkable=True
                ),
                "rectangle_mode": MaterialIconAction(
                    icon_name="frame_inspect", tooltip="Rectangle Zoom Mode", checkable=True
                ),
                "auto_range": MaterialIconAction(
                    icon_name="open_in_full", tooltip="Autorange Plot"
                ),
                "auto_range_image": MaterialIconAction(
                    icon_name="hdr_auto", tooltip="Autorange Image Intensity", checkable=True
                ),
                "aspect_ratio": MaterialIconAction(
                    icon_name="aspect_ratio", tooltip="Lock image aspect ratio", checkable=True
                ),
                "separator_2": SeparatorAction(),
                "FFT": MaterialIconAction(icon_name="fft", tooltip="Toggle FFT", checkable=True),
                "log": MaterialIconAction(
                    icon_name="log_scale", tooltip="Toggle log scale", checkable=True
                ),
                "transpose": MaterialIconAction(
                    icon_name="transform", tooltip="Transpose Image", checkable=True
                ),
                "rotate_right": MaterialIconAction(
                    icon_name="rotate_right", tooltip="Rotate image clockwise by 90 deg"
                ),
                "rotate_left": MaterialIconAction(
                    icon_name="rotate_left", tooltip="Rotate image counterclockwise by 90 deg"
                ),
                "reset": MaterialIconAction(
                    icon_name="reset_settings", tooltip="Reset Image Settings"
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

        self.warning_util = WarningPopupUtility(self)

        self._image = self.fig.image()
        self._image.apply_config(config)
        self.rotation = 0

        self.config = config

        self._hook_actions()

        self.toolbar.widgets["drag_mode"].action.setChecked(True)
        self.toolbar.widgets["auto_range_image"].action.setChecked(True)

    def _hook_actions(self):
        self.toolbar.widgets["connect"].action.triggered.connect(self._connect_action)
        # sepatator
        self.toolbar.widgets["save"].action.triggered.connect(self.export)
        # sepatator
        self.toolbar.widgets["drag_mode"].action.triggered.connect(self.enable_mouse_pan_mode)
        self.toolbar.widgets["rectangle_mode"].action.triggered.connect(
            self.enable_mouse_rectangle_mode
        )
        self.toolbar.widgets["auto_range"].action.triggered.connect(self.toggle_auto_range)
        self.toolbar.widgets["auto_range_image"].action.triggered.connect(
            self.toggle_image_autorange
        )
        self.toolbar.widgets["aspect_ratio"].action.triggered.connect(self.toggle_aspect_ratio)
        # sepatator
        self.toolbar.widgets["FFT"].action.triggered.connect(self.toggle_fft)
        self.toolbar.widgets["log"].action.triggered.connect(self.toggle_log)
        self.toolbar.widgets["transpose"].action.triggered.connect(self.toggle_transpose)
        self.toolbar.widgets["rotate_left"].action.triggered.connect(self.rotate_left)
        self.toolbar.widgets["rotate_right"].action.triggered.connect(self.rotate_right)
        self.toolbar.widgets["reset"].action.triggered.connect(self.reset_settings)
        # sepatator
        self.toolbar.widgets["axis_settings"].action.triggered.connect(self.show_axis_settings)
        self.toolbar.widgets["fps_monitor"].action.toggled.connect(self.enable_fps_monitor)

    ###################################
    # Dialog Windows
    ###################################
    @SafeSlot(popup_error=True)
    def _connect_action(self):
        monitor_combo = self.toolbar.widgets["monitor"].device_combobox
        monitor_name = monitor_combo.currentText()
        monitor_type = self.toolbar.widgets["monitor_type"].widget.currentText()
        self.image(monitor=monitor_name, monitor_type=monitor_type)
        monitor_combo.setStyleSheet("QComboBox { background-color: " "; }")

    def show_axis_settings(self):
        dialog = SettingsDialog(
            self,
            settings_widget=AxisSettings(),
            window_title="Axis Settings",
            config=self._config_dict["axis"],
        )
        dialog.exec()

    ###################################
    # User Access Methods from image
    ###################################
    @SafeSlot(popup_error=True)
    def image(
        self,
        monitor: str,
        monitor_type: Optional[Literal["1d", "2d"]] = "2d",
        color_map: Optional[str] = "magma",
        color_bar: Optional[Literal["simple", "full"]] = "full",
        downsample: Optional[bool] = True,
        opacity: Optional[float] = 1.0,
        vrange: Optional[tuple[int, int]] = None,
        # post_processing: Optional[PostProcessingConfig] = None,
        **kwargs,
    ) -> BECImageItem:
        if self.toolbar.widgets["monitor"].device_combobox.currentText() != monitor:
            self.toolbar.widgets["monitor"].device_combobox.setCurrentText(monitor)
            self.toolbar.widgets["monitor"].device_combobox.setStyleSheet(
                "QComboBox {{ background-color: " "; }}"
            )
        if self.toolbar.widgets["monitor_type"].widget.currentText() != monitor_type:
            self.toolbar.widgets["monitor_type"].widget.setCurrentText(monitor_type)
            self.toolbar.widgets["monitor_type"].widget.setStyleSheet(
                "QComboBox {{ background-color: " "; }}"
            )
        return self._image.image(
            monitor=monitor,
            monitor_type=monitor_type,
            color_map=color_map,
            color_bar=color_bar,
            downsample=downsample,
            opacity=opacity,
            vrange=vrange,
            **kwargs,
        )

    def set_vrange(self, vmin: float, vmax: float, name: str = None):
        """
        Set the range of the color bar.
        If name is not specified, then set vrange for all images.

        Args:
            vmin(float): Minimum value of the color bar.
            vmax(float): Maximum value of the color bar.
            name(str): The name of the image. If None, apply to all images.
        """
        self._image.set_vrange(vmin, vmax, name)

    def set_color_map(self, color_map: str, name: str = None):
        """
        Set the color map of the image.
        If name is not specified, then set color map for all images.

        Args:
            cmap(str): The color map of the image.
            name(str): The name of the image. If None, apply to all images.
        """
        self._image.set_color_map(color_map, name)

    def set_fft(self, enable: bool = False, name: str = None):
        """
        Set the FFT of the image.
        If name is not specified, then set FFT for all images.

        Args:
            enable(bool): Whether to perform FFT on the monitor data.
            name(str): The name of the image. If None, apply to all images.
        """
        self._image.set_fft(enable, name)
        self.toolbar.widgets["FFT"].action.setChecked(enable)

    def set_transpose(self, enable: bool = False, name: str = None):
        """
        Set the transpose of the image.
        If name is not specified, then set transpose for all images.

        Args:
            enable(bool): Whether to transpose the monitor data before displaying.
            name(str): The name of the image. If None, apply to all images.
        """
        self._image.set_transpose(enable, name)
        self.toolbar.widgets["transpose"].action.setChecked(enable)

    def set_rotation(self, deg_90: int = 0, name: str = None):
        """
        Set the rotation of the image.
        If name is not specified, then set rotation for all images.

        Args:
            deg_90(int): The rotation angle of the monitor data before displaying.
            name(str): The name of the image. If None, apply to all images.
        """
        self._image.set_rotation(deg_90, name)

    def set_log(self, enable: bool = False, name: str = None):
        """
        Set the log of the image.
        If name is not specified, then set log for all images.

        Args:
            enable(bool): Whether to perform log on the monitor data.
            name(str): The name of the image. If None, apply to all images.
        """
        self._image.set_log(enable, name)
        self.toolbar.widgets["log"].action.setChecked(enable)

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
        self._image.set(**kwargs)

    def set_title(self, title: str):
        """
        Set the title of the plot widget.

        Args:
            title(str): Title of the plot.
        """
        self._image.set_title(title)

    def set_x_label(self, x_label: str):
        """
        Set the x-axis label of the plot widget.

        Args:
            x_label(str): Label of the x-axis.
        """
        self._image.set_x_label(x_label)

    def set_y_label(self, y_label: str):
        """
        Set the y-axis label of the plot widget.

        Args:
            y_label(str): Label of the y-axis.
        """
        self._image.set_y_label(y_label)

    def set_x_scale(self, x_scale: Literal["linear", "log"]):
        """
        Set the scale of the x-axis of the plot widget.

        Args:
            x_scale(Literal["linear", "log"]): Scale of the x-axis.
        """
        self._image.set_x_scale(x_scale)

    def set_y_scale(self, y_scale: Literal["linear", "log"]):
        """
        Set the scale of the y-axis of the plot widget.

        Args:
            y_scale(Literal["linear", "log"]): Scale of the y-axis.
        """
        self._image.set_y_scale(y_scale)

    def set_x_lim(self, x_lim: tuple):
        """
        Set the limits of the x-axis of the plot widget.

        Args:
            x_lim(tuple): Limits of the x-axis.
        """
        self._image.set_x_lim(x_lim)

    def set_y_lim(self, y_lim: tuple):
        """
        Set the limits of the y-axis of the plot widget.

        Args:
            y_lim(tuple): Limits of the y-axis.
        """
        self._image.set_y_lim(y_lim)

    def set_grid(self, x_grid: bool, y_grid: bool):
        """
        Set the grid visibility of the plot widget.

        Args:
            x_grid(bool): Visibility of the x-axis grid.
            y_grid(bool): Visibility of the y-axis grid.
        """
        self._image.set_grid(x_grid, y_grid)

    def lock_aspect_ratio(self, lock: bool):
        """
        Lock the aspect ratio of the plot widget.

        Args:
            lock(bool): Lock the aspect ratio.
        """
        self._image.lock_aspect_ratio(lock)

    ###################################
    # Toolbar Actions
    ###################################
    @SafeSlot()
    def toggle_auto_range(self):
        """
        Set the auto range of the plot widget from the toolbar.
        """
        self._image.set_auto_range(True, "xy")

    @SafeSlot()
    def toggle_fft(self):
        checked = self.toolbar.widgets["FFT"].action.isChecked()
        self.set_fft(checked)

    @SafeSlot()
    def toggle_log(self):
        checked = self.toolbar.widgets["log"].action.isChecked()
        self.set_log(checked)

    @SafeSlot()
    def toggle_transpose(self):
        checked = self.toolbar.widgets["transpose"].action.isChecked()
        self.set_transpose(checked)

    @SafeSlot()
    def rotate_left(self):
        self.rotation = (self.rotation + 1) % 4
        self.set_rotation(self.rotation)

    @SafeSlot()
    def rotate_right(self):
        self.rotation = (self.rotation - 1) % 4
        self.set_rotation(self.rotation)

    @SafeSlot()
    def reset_settings(self):
        self.set_log(False)
        self.set_fft(False)
        self.set_transpose(False)
        self.rotation = 0
        self.set_rotation(0)

        self.toolbar.widgets["FFT"].action.setChecked(False)
        self.toolbar.widgets["log"].action.setChecked(False)
        self.toolbar.widgets["transpose"].action.setChecked(False)

    @SafeSlot()
    def toggle_image_autorange(self):
        """
        Enable the auto range of the image intensity.
        """
        checked = self.toolbar.widgets["auto_range_image"].action.isChecked()
        self._image.set_autorange(checked)

    @SafeSlot()
    def toggle_aspect_ratio(self):
        """
        Enable the auto range of the image intensity.
        """
        checked = self.toolbar.widgets["aspect_ratio"].action.isChecked()
        self._image.lock_aspect_ratio(checked)

    @SafeSlot()
    def enable_mouse_rectangle_mode(self):
        self.toolbar.widgets["rectangle_mode"].action.setChecked(True)
        self.toolbar.widgets["drag_mode"].action.setChecked(False)
        self._image.plot_item.getViewBox().setMouseMode(pg.ViewBox.RectMode)

    @SafeSlot()
    def enable_mouse_pan_mode(self):
        self.toolbar.widgets["drag_mode"].action.setChecked(True)
        self.toolbar.widgets["rectangle_mode"].action.setChecked(False)
        self._image.plot_item.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    @SafeSlot()
    def enable_fps_monitor(self, enabled: bool):
        """
        Enable the FPS monitor of the plot widget.

        Args:
            enabled(bool): If True, enable the FPS monitor.
        """
        self._image.enable_fps_monitor(enabled)
        if self.toolbar.widgets["fps_monitor"].action.isChecked() != enabled:
            self.toolbar.widgets["fps_monitor"].action.setChecked(enabled)

    def export(self):
        """
        Show the export dialog for the plot widget.
        """
        self._image.export()

    def cleanup(self):
        self.fig.cleanup()
        self.toolbar.close()
        self.toolbar.deleteLater()
        return super().cleanup()


def main():  # pragma: no cover

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECImageWidget()
    widget.image("waveform", "1d")
    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
