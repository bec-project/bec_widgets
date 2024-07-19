import sys
from typing import Literal, Optional
import pyqtgraph as pg

from qtpy.QtWidgets import QWidget, QVBoxLayout

from bec_widgets.qt_utils.error_popups import WarningPopupUtility, SafeSlot
from bec_widgets.qt_utils.settings_dialog import SettingsDialog
from bec_widgets.qt_utils.toolbar import (
    ModularToolBar,
    SeparatorAction,
    IconAction,
    DeviceSelectionAction,
)
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.figure.plots.axis_settings import AxisSettings
from bec_widgets.widgets.figure.plots.image.image import ImageConfig
from bec_widgets.widgets.figure.plots.image.image_item import BECImageItem


# TODO move the actions to general place


class BECImageWidget(BECWidget, QWidget):
    USER_ACCESS = []

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
        self.toolbar = ModularToolBar(
            actions={
                "monitor": DeviceSelectionAction(
                    "Monitor:", DeviceComboBox(device_filter="Device")
                ),
                "connect": IconAction(icon_path="connection.svg", tooltip="Connect Motors"),
                "separator_0": SeparatorAction(),
                "save": IconAction(icon_path="save.svg", tooltip="Open Export Dialog"),
                "separator_1": SeparatorAction(),
                "drag_mode": IconAction(
                    icon_path="drag_pan_mode.svg", tooltip="Drag Mouse Mode", checkable=True
                ),
                "rectangle_mode": IconAction(
                    icon_path="rectangle_mode.svg", tooltip="Rectangle Zoom Mode", checkable=True
                ),
                "auto_range": IconAction(icon_path="auto_range.svg", tooltip="Autorange Plot"),
                "auto_range_image": IconAction(
                    icon_path="image_autorange.svg",
                    tooltip="Autorange Image Intensity",
                    checkable=True,
                ),
                "separator_2": SeparatorAction(),
                "FFT": IconAction(icon_path="compare.svg", tooltip="Toggle FFT", checkable=True),
                "log": IconAction(
                    icon_path="line_curve.svg", tooltip="Toggle log scale", checkable=True
                ),
                "transpose": IconAction(
                    icon_path="transform.svg", tooltip="Transpose Image", checkable=True
                ),
                "rotate_right": IconAction(
                    icon_path="rotate_right.svg", tooltip="Rotate image clockwise by 90 deg"
                ),
                "rotate_left": IconAction(
                    icon_path="rotate_left.svg", tooltip="Rotate image counterclockwise by 90 deg"
                ),
                "reset": IconAction(icon_path="reset_settings.svg", tooltip="Reset Image Settings"),
                "separator_3": SeparatorAction(),
                "axis_settings": IconAction(
                    icon_path="settings.svg", tooltip="Open Configuration Dialog"
                ),
            },
            target_widget=self,
        )

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.fig)

        self.warning_util = WarningPopupUtility(self)

        self.image = self.fig.image()
        self.image.apply_config(config)
        self.rotation = 0

        self.config = config

        self._hook_actions()

        # TODO test commands
        # self.image.add_monitor_image("eiger")

    def _hook_actions(self):
        self.toolbar.widgets["connect"].action.triggered.connect(self._connect_action)
        # sepatator
        self.toolbar.widgets["save"].action.triggered.connect(self.export)
        # sepatator
        self.toolbar.widgets["drag_mode"].action.triggered.connect(self.enable_mouse_pan_mode)
        self.toolbar.widgets["rectangle_mode"].action.triggered.connect(
            self.enable_mouse_rectangle_mode
        )
        self.toolbar.widgets["auto_range"].action.triggered.connect(self._auto_range_from_toolbar)
        self.toolbar.widgets["auto_range_image"].action.triggered.connect(
            self.toogle_image_autorange
        )
        # sepatator
        self.toolbar.widgets["FFT"].action.triggered.connect(self.toogle_fft)
        self.toolbar.widgets["log"].action.triggered.connect(self.toogle_log)
        self.toolbar.widgets["transpose"].action.triggered.connect(self.toogle_transpose)
        self.toolbar.widgets["rotate_left"].action.triggered.connect(self.rotate_left)
        self.toolbar.widgets["rotate_right"].action.triggered.connect(self.rotate_right)
        self.toolbar.widgets["reset"].action.triggered.connect(self.reset_settings)
        # sepatator
        self.toolbar.widgets["axis_settings"].action.triggered.connect(self.show_axis_settings)

    ###################################
    # Dialog Windows
    ###################################
    @SafeSlot(popup_error=True)
    def _connect_action(self):
        monitor_combo = self.toolbar.widgets["monitor"].device_combobox
        monitor_name = monitor_combo.currentText()
        # self.add_monitor_image(monitor_name)
        self.set_monitor_image(monitor_name)
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
    def add_monitor_image(
        self,
        monitor: str,
        color_map: Optional[str] = "magma",
        color_bar: Optional[Literal["simple", "full"]] = "full",
        downsample: Optional[bool] = True,
        opacity: Optional[float] = 1.0,
        vrange: Optional[tuple[int, int]] = None,
        # post_processing: Optional[PostProcessingConfig] = None,
        **kwargs,
    ) -> BECImageItem:
        return self.image.add_monitor_image(
            monitor,
            color_map=color_map,
            color_bar=color_bar,
            downsample=downsample,
            opacity=opacity,
            vrange=vrange,
            **kwargs,
        )

    def set_fft(self, enable: bool = False, name: str = None):
        """
        Set the FFT of the image.
        If name is not specified, then set FFT for all images.

        Args:
            enable(bool): Whether to perform FFT on the monitor data.
            name(str): The name of the image. If None, apply to all images.
        """
        self.image.set_fft(enable, name)

    def set_transpose(self, enable: bool = False, name: str = None):
        """
        Set the transpose of the image.
        If name is not specified, then set transpose for all images.

        Args:
            enable(bool): Whether to transpose the monitor data before displaying.
            name(str): The name of the image. If None, apply to all images.
        """
        self.image.set_transpose(enable, name)

    def set_rotation(self, deg_90: int = 0, name: str = None):
        """
        Set the rotation of the image.
        If name is not specified, then set rotation for all images.

        Args:
            deg_90(int): The rotation angle of the monitor data before displaying.
            name(str): The name of the image. If None, apply to all images.
        """
        self.image.set_rotation(deg_90, name)

    def set_log(self, enable: bool = False, name: str = None):
        """
        Set the log of the image.
        If name is not specified, then set log for all images.

        Args:
            enable(bool): Whether to perform log on the monitor data.
            name(str): The name of the image. If None, apply to all images.
        """
        self.image.set_log(enable, name)

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
        self.image.set(**kwargs)

    def set_title(self, title: str):
        """
        Set the title of the plot widget.

        Args:
            title(str): Title of the plot.
        """
        self.image.set_title(title)

    def set_x_label(self, x_label: str):
        """
        Set the x-axis label of the plot widget.

        Args:
            x_label(str): Label of the x-axis.
        """
        self.image.set_x_label(x_label)

    def set_y_label(self, y_label: str):
        """
        Set the y-axis label of the plot widget.

        Args:
            y_label(str): Label of the y-axis.
        """
        self.image.set_y_label(y_label)

    def set_x_scale(self, x_scale: Literal["linear", "log"]):
        """
        Set the scale of the x-axis of the plot widget.

        Args:
            x_scale(Literal["linear", "log"]): Scale of the x-axis.
        """
        self.image.set_x_scale(x_scale)

    def set_y_scale(self, y_scale: Literal["linear", "log"]):
        """
        Set the scale of the y-axis of the plot widget.

        Args:
            y_scale(Literal["linear", "log"]): Scale of the y-axis.
        """
        self.image.set_y_scale(y_scale)

    def set_x_lim(self, x_lim: tuple):
        """
        Set the limits of the x-axis of the plot widget.

        Args:
            x_lim(tuple): Limits of the x-axis.
        """
        self.image.set_x_lim(x_lim)

    def set_y_lim(self, y_lim: tuple):
        """
        Set the limits of the y-axis of the plot widget.

        Args:
            y_lim(tuple): Limits of the y-axis.
        """
        self.image.set_y_lim(y_lim)

    def set_legend_label_size(self, legend_label_size: int):
        """
        Set the size of the legend labels of the plot widget.

        Args:
            legend_label_size(int): Size of the legend labels.
        """
        self.image.set_legend_label_size(legend_label_size)

    @SafeSlot()
    def _auto_range_from_toolbar(self):
        """
        Set the auto range of the plot widget from the toolbar.
        """
        self.image.set_auto_range(True, "xy")

    def set_grid(self, x_grid: bool, y_grid: bool):
        """
        Set the grid visibility of the plot widget.

        Args:
            x_grid(bool): Visibility of the x-axis grid.
            y_grid(bool): Visibility of the y-axis grid.
        """
        self.image.set_grid(x_grid, y_grid)

    def lock_aspect_ratio(self, lock: bool):
        """
        Lock the aspect ratio of the plot widget.

        Args:
            lock(bool): Lock the aspect ratio.
        """
        self.image.lock_aspect_ratio(lock)

    ###################################
    # Toolbar Actions
    ###################################
    @SafeSlot()
    def toogle_fft(self):
        checked = self.toolbar.widgets["FFT"].action.isChecked()
        self.set_fft(checked)

    @SafeSlot()
    def toogle_log(self):
        checked = self.toolbar.widgets["log"].action.isChecked()
        self.set_log(checked)

    @SafeSlot()
    def toogle_transpose(self):
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
    def toogle_image_autorange(self):
        """
        Enable the auto range of the image intensity.
        """
        checked = self.toolbar.widgets["auto_range_image"].action.isChecked()
        self.image.set_autorange(checked)

    @SafeSlot()
    def enable_mouse_rectangle_mode(self):
        self.toolbar.widgets["rectangle_mode"].action.setChecked(True)
        self.toolbar.widgets["drag_mode"].action.setChecked(False)
        self.image.plot_item.getViewBox().setMouseMode(pg.ViewBox.RectMode)

    @SafeSlot()
    def enable_mouse_pan_mode(self):
        self.toolbar.widgets["drag_mode"].action.setChecked(True)
        self.toolbar.widgets["rectangle_mode"].action.setChecked(False)
        self.image.plot_item.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    def export(self):
        """
        Show the export dialog for the plot widget.
        """
        self.image.export()

    def cleanup(self):
        self.fig.cleanup()
        self.client.shutdown()
        return super().cleanup()


def main():  # pragma: no cover

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECImageWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
