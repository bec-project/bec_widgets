from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from bec_lib.endpoints import MessageEndpoints
from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError
from qtpy import QtCore, QtGui
from qtpy.QtCore import Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from bec_widgets.utils import Colors, ConnectionConfig
from bec_widgets.utils.colors import set_theme
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.settings_dialog import SettingsDialog
from bec_widgets.utils.toolbar import MaterialIconAction
from bec_widgets.widgets.plots.motor_map.settings.motor_map_settings import MotorMapSettings
from bec_widgets.widgets.plots.motor_map.toolbar_bundles.motor_selection import (
    MotorSelectionToolbarBundle,
)
from bec_widgets.widgets.plots.plot_base import PlotBase

logger = bec_logger.logger


class FilledRectItem(pg.GraphicsObject):
    """
    Custom rectangle item for the motor map plot defined by 4 points and a brush.
    """

    def __init__(self, x: float, y: float, width: float, height: float, brush: QtGui.QBrush):
        super().__init__()
        self._rect = QtCore.QRectF(x, y, width, height)
        self._brush = brush
        self._pen = pg.mkPen(None)

    def boundingRect(self):
        return self._rect

    def paint(self, painter, *args):
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        painter.drawRect(self.boundingRect())


class MotorConfig(BaseModel):
    name: str | None = Field(None, description="Motor name.")
    limits: list[float] | None = Field(None, description="Motor limits.")


# noinspection PyDataclass
class MotorMapConfig(ConnectionConfig):
    x_motor: MotorConfig = Field(default_factory=MotorConfig, description="Motor X name.")
    y_motor: MotorConfig = Field(default_factory=MotorConfig, description="Motor Y name.")
    color: str | tuple | None = Field(
        (255, 255, 255, 255), description="The color of the last point of current position."
    )
    scatter_size: int | None = Field(5, description="Size of the scatter points.")
    max_points: int | None = Field(5000, description="Maximum number of points to display.")
    num_dim_points: int | None = Field(
        100,
        description="Number of points to dim before the color remains same for older recorded position.",
    )
    precision: int | None = Field(2, description="Decimal precision of the motor position.")
    background_value: int | None = Field(
        25, description="Background value of the motor map. Has to be between 0 and 255."
    )

    model_config: dict = {"validate_assignment": True}

    _validate_color = field_validator("color")(Colors.validate_color)

    @field_validator("background_value")
    def validate_background_value(cls, value):
        if not 0 <= value <= 255:
            raise PydanticCustomError(
                "wrong_value", f"'{value}' hs to be between 0 and 255.", {"wrong_value": value}
            )
        return value


class MotorMap(PlotBase):
    PLUGIN = True
    RPC = True
    ICON_NAME = "my_location"
    USER_ACCESS = [
        # General PlotBase Settings
        "enable_toolbar",
        "enable_toolbar.setter",
        "enable_side_panel",
        "enable_side_panel.setter",
        "enable_fps_monitor",
        "enable_fps_monitor.setter",
        "set",
        "title",
        "title.setter",
        "x_label",
        "x_label.setter",
        "y_label",
        "y_label.setter",
        "x_limits",
        "x_limits.setter",
        "y_limits",
        "y_limits.setter",
        "x_grid",
        "x_grid.setter",
        "y_grid",
        "y_grid.setter",
        "inner_axes",
        "inner_axes.setter",
        "outer_axes",
        "outer_axes.setter",
        "lock_aspect_ratio",
        "lock_aspect_ratio.setter",
        "auto_range_x",
        "auto_range_x.setter",
        "auto_range_y",
        "auto_range_y.setter",
        "x_log",
        "x_log.setter",
        "y_log",
        "y_log.setter",
        "legend_label_size",
        "legend_label_size.setter",
        # motor_map specific
        "color",
        "color.setter",
        "max_points",
        "max_points.setter",
        "precision",
        "precision.setter",
        "num_dim_points",
        "num_dim_points.setter",
        "background_value",
        "background_value.setter",
        "scatter_size",
        "scatter_size.setter",
        "map",
        "reset_history",
        "get_data",
    ]

    update_signal = Signal()
    """Motor map widget for plotting motor positions."""

    def __init__(
        self,
        parent: QWidget | None = None,
        config: MotorMapConfig | None = None,
        client=None,
        gui_id: str | None = None,
        popups: bool = True,
        **kwargs,
    ):
        if config is None:
            config = MotorMapConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, config=config, client=client, gui_id=gui_id, popups=popups, **kwargs
        )

        # Default values for PlotBase
        self.x_grid = True
        self.y_grid = True

        # Gui specific
        self._buffer = {"x": [], "y": []}
        self._limit_map = None
        self._trace = None
        self.v_line = None
        self.h_line = None
        self.coord_label = None
        self.motor_map_settings = None

        # Connect slots
        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self._update_plot
        )
        self._add_motor_map_settings()

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################

    def _init_toolbar(self):
        """
        Initialize the toolbar for the motor map widget.
        """
        self.motor_selection_bundle = MotorSelectionToolbarBundle(
            bundle_id="motor_selection", target_widget=self
        )
        self.toolbar.add_bundle(self.motor_selection_bundle, target_widget=self)
        super()._init_toolbar()
        self.toolbar.widgets["reset_legend"].action.setVisible(False)

        self.reset_legend_action = MaterialIconAction(
            icon_name="history", tooltip="Reset the position of legend."
        )
        self.toolbar.add_action_to_bundle(
            bundle_id="roi",
            action_id="motor_map_history",
            action=self.reset_legend_action,
            target_widget=self,
        )
        self.reset_legend_action.action.triggered.connect(self.reset_history)

    def _add_motor_map_settings(self):
        """Add the motor map settings to the side panel."""
        motor_map_settings = MotorMapSettings(parent=self, target_widget=self, popup=False)
        self.side_panel.add_menu(
            action_id="motor_map_settings",
            icon_name="settings_brightness",
            tooltip="Show Motor Map Settings",
            widget=motor_map_settings,
            title="Motor Map Settings",
        )

    def add_popups(self):
        """
        Add popups to the ScatterWaveform widget.
        """
        super().add_popups()
        scatter_curve_setting_action = MaterialIconAction(
            icon_name="settings_brightness",
            tooltip="Show Motor Map Settings",
            checkable=True,
            parent=self,
        )
        self.toolbar.add_action_to_bundle(
            bundle_id="popup_bundle",
            action_id="motor_map_settings",
            action=scatter_curve_setting_action,
            target_widget=self,
        )
        self.toolbar.widgets["motor_map_settings"].action.triggered.connect(
            self.show_motor_map_settings
        )

    def show_motor_map_settings(self):
        """
        Show the DAP summary popup.
        """
        action = self.toolbar.widgets["motor_map_settings"].action
        if self.motor_map_settings is None or not self.motor_map_settings.isVisible():
            motor_map_settings = MotorMapSettings(parent=self, target_widget=self, popup=True)
            self.motor_map_settings = SettingsDialog(
                self,
                settings_widget=motor_map_settings,
                window_title="Motor Map Settings",
                modal=False,
            )
            self.motor_map_settings.setFixedSize(250, 300)
            # When the dialog is closed, update the toolbar icon and clear the reference
            self.motor_map_settings.finished.connect(self._motor_map_settings_closed)
            self.motor_map_settings.show()
            action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.motor_map_settings.raise_()
            self.motor_map_settings.activateWindow()
            action.setChecked(True)  # keep it toggled

    def _motor_map_settings_closed(self):
        """
        Slot for when the axis settings dialog is closed.
        """
        self.motor_map_settings.deleteLater()
        self.motor_map_settings = None
        self.toolbar.widgets["motor_map_settings"].action.setChecked(False)

    ################################################################################
    # Widget Specific Properties
    ################################################################################

    # color_scatter for designer, color for CLI to not bother users with QColor
    @SafeProperty("QColor")
    def color_scatter(self) -> QtGui.QColor:
        """
        Get the color of the motor trace.

        Returns:
            QColor: Color of the motor trace.
        """
        return QColor(*self.config.color)

    @color_scatter.setter
    def color_scatter(self, color: str | tuple | QColor) -> None:
        """
        Set color of the motor trace.

        Args:
            color(str|tuple): Color of the motor trace. Can be HEX(str) or RGBA(tuple).
        """
        if isinstance(color, str):
            color = Colors.hex_to_rgba(color, 255)
        if isinstance(color, QColor):
            color = (color.red(), color.green(), color.blue(), color.alpha())
        color = Colors.validate_color(color)
        self.config.color = color
        self.update_signal.emit()
        self.property_changed.emit("color_scatter", color)

    @property
    def color(self) -> tuple:
        """
        Get the color of the motor trace.

        Returns:
            tuple: Color of the motor trace.
        """
        return self.config.color

    @color.setter
    def color(self, color: str | tuple) -> None:
        """
        Set color of the motor trace.

        Args:
            color(str|tuple): Color of the motor trace. Can be HEX(str) or RGBA(tuple).
        """
        self.color_scatter = color

    @SafeProperty(int)
    def max_points(self) -> int:
        """Get the maximum number of points to display."""
        return self.config.max_points

    @max_points.setter
    def max_points(self, max_points: int) -> None:
        """
        Set the maximum number of points to display.

        Args:
            max_points(int): Maximum number of points to display.
        """
        self.config.max_points = max_points
        self.update_signal.emit()
        self.property_changed.emit("max_points", max_points)

    @SafeProperty(int)
    def precision(self) -> int:
        """
        Set the decimal precision of the motor position.
        """
        return self.config.precision

    @precision.setter
    def precision(self, precision: int) -> None:
        """
        Set the decimal precision of the motor position.

        Args:
            precision(int): Decimal precision of the motor position.
        """
        self.config.precision = precision
        self.update_signal.emit()
        self.property_changed.emit("precision", precision)

    @SafeProperty(int)
    def num_dim_points(self) -> int:
        """
        Get the number of dim points for the motor map.
        """
        return self.config.num_dim_points

    @num_dim_points.setter
    def num_dim_points(self, num_dim_points: int) -> None:
        """
        Set the number of dim points for the motor map.

        Args:
            num_dim_points(int): Number of dim points.
        """
        self.config.num_dim_points = num_dim_points
        self.update_signal.emit()
        self.property_changed.emit("num_dim_points", num_dim_points)

    @SafeProperty(int)
    def background_value(self) -> int:
        """
        Get the background value of the motor map.
        """
        return self.config.background_value

    @background_value.setter
    def background_value(self, background_value: int) -> None:
        """
        Set the background value of the motor map.

        Args:
            background_value(int): Background value of the motor map.
        """
        self.config.background_value = background_value
        self._swap_limit_map()
        self.property_changed.emit("background_value", background_value)

    @SafeProperty(int)
    def scatter_size(self) -> int:
        """
        Get the scatter size of the motor map plot.
        """
        return self.config.scatter_size

    @scatter_size.setter
    def scatter_size(self, scatter_size: int) -> None:
        """
        Set the scatter size of the motor map plot.

        Args:
            scatter_size(int): Size of the scatter points.
        """
        self.config.scatter_size = scatter_size
        self.update_signal.emit()
        self.property_changed.emit("scatter_size", scatter_size)

    ################################################################################
    # High Level methods for API
    ################################################################################
    @SafeSlot()
    def map(self, x_name: str, y_name: str, validate_bec: bool = True) -> None:
        """
        Set the x and y motor names.

        Args:
            x_name(str): The name of the x motor.
            y_name(str): The name of the y motor.
            validate_bec(bool, optional): If True, validate the signal with BEC. Defaults to True.
        """
        self.plot_item.clear()

        if validate_bec:
            self.entry_validator.validate_signal(x_name, None)
            self.entry_validator.validate_signal(y_name, None)

        self.config.x_motor.name = x_name
        self.config.y_motor.name = y_name

        motor_x_limit = self._get_motor_limit(self.config.x_motor.name)
        motor_y_limit = self._get_motor_limit(self.config.y_motor.name)

        self.config.x_motor.limits = motor_x_limit
        self.config.y_motor.limits = motor_y_limit

        # reconnect the signals
        self._connect_motor_to_slots()

        # Reset the buffer
        self._buffer = {"x": [], "y": []}

        # Redraw the motor map
        self._make_motor_map()

        self._sync_motor_map_selection_toolbar()

    def reset_history(self):
        """
        Reset the history of the motor map.
        """
        self._buffer["x"] = [self._buffer["x"][-1]]
        self._buffer["y"] = [self._buffer["y"][-1]]
        self.update_signal.emit()

    ################################################################################
    # BEC Update Methods
    ################################################################################
    @SafeSlot()
    def _update_plot(self, _=None):
        """Update the motor map plot."""
        if self._trace is None:
            return
        # If the number of points exceeds max_points, delete the oldest points
        if len(self._buffer["x"]) > self.config.max_points:
            self._buffer["x"] = self._buffer["x"][-self.config.max_points :]
            self._buffer["y"] = self._buffer["y"][-self.config.max_points :]

        x = self._buffer["x"]
        y = self._buffer["y"]

        # Setup gradient brush for history
        brushes = [pg.mkBrush(50, 50, 50, 255)] * len(x)

        # RGB color
        r, g, b, a = self.config.color

        # Calculate the decrement step based on self.num_dim_points
        num_dim_points = self.config.num_dim_points
        decrement_step = (255 - 50) / num_dim_points

        for i in range(1, min(num_dim_points + 1, len(x) + 1)):
            brightness = max(60, 255 - decrement_step * (i - 1))
            dim_r = int(r * (brightness / 255))
            dim_g = int(g * (brightness / 255))
            dim_b = int(b * (brightness / 255))
            brushes[-i] = pg.mkBrush(dim_r, dim_g, dim_b, a)
        brushes[-1] = pg.mkBrush(r, g, b, a)  # Newest point is always full brightness
        scatter_size = self.config.scatter_size

        # Update the scatter plot
        self._trace.setData(x=x, y=y, brush=brushes, pen=None, size=scatter_size)

        # Get last know position for crosshair
        current_x = x[-1]
        current_y = y[-1]

        # Update the crosshair
        self._set_motor_indicator_position(current_x, current_y)

    @SafeSlot(dict, dict)
    def on_device_readback(self, msg: dict, metadata: dict) -> None:
        """
        Update the motor map plot with the new motor position.

        Args:
            msg(dict): Message from the device readback.
            metadata(dict): Metadata of the message.
        """
        x_motor = self.config.x_motor.name
        y_motor = self.config.y_motor.name

        if x_motor is None or y_motor is None:
            return

        if x_motor in msg["signals"]:
            x = msg["signals"][x_motor]["value"]
            self._buffer["x"].append(x)
            self._buffer["y"].append(self._buffer["y"][-1])

        elif y_motor in msg["signals"]:
            y = msg["signals"][y_motor]["value"]
            self._buffer["y"].append(y)
            self._buffer["x"].append(self._buffer["x"][-1])

        self.update_signal.emit()

    def _connect_motor_to_slots(self):
        """Connect motors to slots."""
        self._disconnect_current_motors()

        endpoints_readback = [
            MessageEndpoints.device_readback(self.config.x_motor.name),
            MessageEndpoints.device_readback(self.config.y_motor.name),
        ]
        endpoints_limits = [
            MessageEndpoints.device_limits(self.config.x_motor.name),
            MessageEndpoints.device_limits(self.config.y_motor.name),
        ]

        self.bec_dispatcher.connect_slot(self.on_device_readback, endpoints_readback)
        self.bec_dispatcher.connect_slot(self.on_device_limits, endpoints_limits)

    def _disconnect_current_motors(self):
        """Disconnect the current motors from the slots."""
        if self.config.x_motor.name is not None and self.config.y_motor.name is not None:
            endpoints_readback = [
                MessageEndpoints.device_readback(self.config.x_motor.name),
                MessageEndpoints.device_readback(self.config.y_motor.name),
            ]
            endpoints_limits = [
                MessageEndpoints.device_limits(self.config.x_motor.name),
                MessageEndpoints.device_limits(self.config.y_motor.name),
            ]
            self.bec_dispatcher.disconnect_slot(self.on_device_readback, endpoints_readback)
            self.bec_dispatcher.disconnect_slot(self.on_device_limits, endpoints_limits)

    ################################################################################
    # Utility Methods
    ################################################################################
    @SafeSlot(dict, dict)
    def on_device_limits(self, msg: dict, metadata: dict) -> None:
        """
        Update the motor limits in the config.

        Args:
            msg(dict): Message from the device limits.
            metadata(dict): Metadata of the message.
        """
        self.config.x_motor.limits = self._get_motor_limit(self.config.x_motor.name)
        self.config.y_motor.limits = self._get_motor_limit(self.config.y_motor.name)
        self._swap_limit_map()

    def _get_motor_limit(self, motor: str) -> list | None:
        """
        Get the motor limit from the config.

        Args:
            motor(str): Motor name.

        Returns:
            float: Motor limit.
        """
        try:
            limits = self.dev[motor].limits
            if limits == [0, 0]:
                return None
            return limits
        except AttributeError:  # TODO maybe not needed, if no limits it returns [0,0]
            # If the motor doesn't have a 'limits' attribute, return a default value or raise a custom exception
            logger.error(f"The device '{motor}' does not have defined limits.")
            return None

    def _make_motor_map(self) -> None:
        """
        Make the motor map.
        """

        motor_x_limit = self.config.x_motor.limits
        motor_y_limit = self.config.y_motor.limits

        self._limit_map = self._make_limit_map(motor_x_limit, motor_y_limit)
        self.plot_item.addItem(self._limit_map)
        self._limit_map.setZValue(-1)

        # Create scatter plot
        scatter_size = self.config.scatter_size
        self._trace = pg.ScatterPlotItem(size=scatter_size, brush=pg.mkBrush(255, 255, 255, 255))
        self.plot_item.addItem(self._trace)
        self._trace.setZValue(0)

        # Add the crosshair for initial motor coordinates
        initial_position_x = self._get_motor_init_position(
            self.config.x_motor.name, self.config.precision
        )
        initial_position_y = self._get_motor_init_position(
            self.config.y_motor.name, self.config.precision
        )

        self._buffer["x"] = [initial_position_x]
        self._buffer["y"] = [initial_position_y]

        self._trace.setData([initial_position_x], [initial_position_y])

        # Add initial crosshair
        self._add_coordinates_crosshair(initial_position_x, initial_position_y)

        # Set default labels for the plot
        self.set_x_label_suffix(f"[{self.config.x_motor.name}-{self.config.x_motor.name}]")
        self.set_y_label_suffix(f"[{self.config.y_motor.name}-{self.config.y_motor.name}]")

        self.update_signal.emit()

    def _add_coordinates_crosshair(self, x: float, y: float) -> None:
        """
        Add position crosshair indicator to the plot.

        Args:
            x(float): X coordinate of the crosshair.
            y(float): Y coordinate of the crosshair.
        """
        if self.v_line is not None and self.h_line is not None and self.coord_label is not None:
            self.plot_item.removeItem(self.h_line)
            self.plot_item.removeItem(self.v_line)
            self.plot_item.removeItem(self.coord_label)

        self.h_line = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen(color="r", width=1, style=QtCore.Qt.DashLine)
        )
        self.v_line = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen(color="r", width=1, style=QtCore.Qt.DashLine)
        )

        self.coord_label = pg.TextItem("", anchor=(1, 1), fill=(0, 0, 0, 100))

        # Add crosshair to the plot
        self.plot_item.addItem(self.h_line)
        self.plot_item.addItem(self.v_line)
        self.plot_item.addItem(self.coord_label)

        self._set_motor_indicator_position(x, y)

    def _set_motor_indicator_position(self, x: float, y: float) -> None:
        """
        Set the position of the motor indicator.

        Args:
            x(float): X coordinate of the motor indicator.
            y(float): Y coordinate of the motor indicator.
        """
        if self.v_line is None or self.h_line is None or self.coord_label is None:
            return

        text = f"({x:.{self.config.precision}f}, {y:.{self.config.precision}f})"

        self.v_line.setPos(x)
        self.h_line.setPos(y)
        self.coord_label.setText(text)
        self.coord_label.setPos(x, y)

    def _make_limit_map(self, limits_x: list | None, limits_y: list | None) -> FilledRectItem:
        """
        Create a limit map for the motor map plot. Each limit can be:
          - [int, int]
          - [None, None]
          - [int, None]
          - [None, int]
          - or None
        If any element of a limit list is None, it is treated as unbounded,
        and replaced with ±1e6 (or any large float of your choice).

        Args:
            limits_x(list): Motor limits for the x-axis.
            limits_y(list): Motor limits for the y-axis.

        Returns:
            FilledRectItem: Limit map.
        """

        def fix_limit_pair(limits):
            if not limits:
                return [-1e6, 1e6]
            low, high = limits
            if low is None:
                low = -1e6
            if high is None:
                high = 1e6
            return [low, high]

        limits_x = fix_limit_pair(limits_x)
        limits_y = fix_limit_pair(limits_y)

        limit_x_min, limit_x_max = limits_x
        limit_y_min, limit_y_max = limits_y

        rect_width = limit_x_max - limit_x_min
        rect_height = limit_y_max - limit_y_min
        background_value = self.config.background_value

        brush_color = pg.mkBrush(background_value, background_value, background_value, 150)

        filled_rect = FilledRectItem(
            x=limit_x_min, y=limit_y_min, width=rect_width, height=rect_height, brush=brush_color
        )
        return filled_rect

    def _swap_limit_map(self):
        """Swap the limit map."""
        self.plot_item.removeItem(self._limit_map)
        x_limits = self.config.x_motor.limits
        y_limits = self.config.y_motor.limits
        if x_limits is not None and y_limits is not None:
            self._limit_map = self._make_limit_map(x_limits, y_limits)
            self._limit_map.setZValue(-1)
            self.plot_item.addItem(self._limit_map)

    def _get_motor_init_position(self, name: str, precision: int) -> float:
        """
        Get the motor initial position from the config.

        Args:
            name(str): Motor name.
            precision(int): Decimal precision of the motor position.

        Returns:
            float: Motor initial position.
        """
        entry = self.entry_validator.validate_signal(name, None)
        init_position = round(float(self.dev[name].read()[entry]["value"]), precision)
        return init_position

    def _sync_motor_map_selection_toolbar(self):
        """
        Sync the motor map selection toolbar with the current motor map.
        """
        if self.motor_selection_bundle is not None:
            motor_x = self.motor_selection_bundle.motor_x.currentText()
            motor_y = self.motor_selection_bundle.motor_y.currentText()

            if motor_x != self.config.x_motor.name:
                self.motor_selection_bundle.motor_x.blockSignals(True)
                self.motor_selection_bundle.motor_x.set_device(self.config.x_motor.name)
                self.motor_selection_bundle.motor_x.check_validity(self.config.x_motor.name)
                self.motor_selection_bundle.motor_x.blockSignals(False)
            if motor_y != self.config.y_motor.name:
                self.motor_selection_bundle.motor_y.blockSignals(True)
                self.motor_selection_bundle.motor_y.set_device(self.config.y_motor.name)
                self.motor_selection_bundle.motor_y.check_validity(self.config.y_motor.name)
                self.motor_selection_bundle.motor_y.blockSignals(False)

    ################################################################################
    # Export Methods
    ################################################################################

    def get_data(self) -> dict:
        """
        Get the data of the motor map.

        Returns:
            dict: Data of the motor map.
        """
        data = {"x": self._buffer["x"], "y": self._buffer["y"]}
        return data


class DemoApp(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Waveform Demo")
        self.resize(800, 600)
        self.main_widget = QWidget()
        self.layout = QHBoxLayout(self.main_widget)
        self.setCentralWidget(self.main_widget)

        self.motor_map_popup = MotorMap(popups=True)
        self.motor_map_popup.map(x_name="samx", y_name="samy", validate_bec=True)

        self.motor_map_side = MotorMap(popups=False)
        self.motor_map_side.map(x_name="samx", y_name="samy", validate_bec=True)

        self.layout.addWidget(self.motor_map_side)
        self.layout.addWidget(self.motor_map_popup)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    set_theme("dark")
    widget = DemoApp()
    widget.show()
    widget.resize(1400, 600)
    sys.exit(app.exec_())
