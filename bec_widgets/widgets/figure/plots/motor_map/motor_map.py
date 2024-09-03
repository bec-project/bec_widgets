from __future__ import annotations

from collections import defaultdict
from typing import Optional, Union

import numpy as np
import pyqtgraph as pg
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from pydantic import Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError
from qtpy import QtCore, QtGui
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtWidgets import QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot as Slot
from bec_widgets.utils import Colors, EntryValidator
from bec_widgets.widgets.figure.plots.plot_base import BECPlotBase, SubplotConfig
from bec_widgets.widgets.figure.plots.waveform.waveform import Signal, SignalData

logger = bec_logger.logger


class MotorMapConfig(SubplotConfig):
    signals: Optional[Signal] = Field(None, description="Signals of the motor map")
    color: Optional[str | tuple] = Field(
        (255, 255, 255, 255), description="The color of the last point of current position."
    )
    scatter_size: Optional[int] = Field(5, description="Size of the scatter points.")
    max_points: Optional[int] = Field(5000, description="Maximum number of points to display.")
    num_dim_points: Optional[int] = Field(
        100,
        description="Number of points to dim before the color remains same for older recorded position.",
    )
    precision: Optional[int] = Field(2, description="Decimal precision of the motor position.")
    background_value: Optional[int] = Field(
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


class BECMotorMap(BECPlotBase):
    USER_ACCESS = [
        "_rpc_id",
        "_config_dict",
        "change_motors",
        "set_max_points",
        "set_precision",
        "set_num_dim_points",
        "set_background_value",
        "set_scatter_size",
        "get_data",
        "export",
        "remove",
        "reset_history",
    ]

    # QT Signals
    update_signal = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        parent_figure=None,
        config: Optional[MotorMapConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = MotorMapConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, parent_figure=parent_figure, config=config, client=client, gui_id=gui_id
        )

        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.get_bec_shortcuts()
        self.entry_validator = EntryValidator(self.dev)

        # connect update signal to update plot
        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self._update_plot
        )
        self.apply_config(self.config)

    def apply_config(self, config: dict | MotorMapConfig):
        """
        Apply the config to the motor map.

        Args:
            config(dict|MotorMapConfig): Config to be applied.
        """
        if isinstance(config, dict):
            try:
                config = MotorMapConfig(**config)
            except ValidationError as e:
                logger.error(f"Error in applying config: {e}")
                return

        self.config = config
        self.plot_item.clear()

        self.motor_x = None
        self.motor_y = None
        self.database_buffer = {"x": [], "y": []}
        self.plot_components = defaultdict(dict)  # container for plot components

        self.apply_axis_config()

        if self.config.signals is not None:
            self.change_motors(
                motor_x=self.config.signals.x.name,
                motor_y=self.config.signals.y.name,
                motor_x_entry=self.config.signals.x.entry,
                motor_y_entry=self.config.signals.y.entry,
            )

    @Slot(str, str, str, str, bool)
    def change_motors(
        self,
        motor_x: str,
        motor_y: str,
        motor_x_entry: str = None,
        motor_y_entry: str = None,
        validate_bec: bool = True,
    ) -> None:
        """
        Change the active motors for the plot.

        Args:
            motor_x(str): Motor name for the X axis.
            motor_y(str): Motor name for the Y axis.
            motor_x_entry(str): Motor entry for the X axis.
            motor_y_entry(str): Motor entry for the Y axis.
            validate_bec(bool, optional): If True, validate the signal with BEC. Defaults to True.
        """
        self.plot_item.clear()

        motor_x_entry, motor_y_entry = self._validate_signal_entries(
            motor_x, motor_y, motor_x_entry, motor_y_entry, validate_bec
        )

        motor_x_limit = self._get_motor_limit(motor_x)
        motor_y_limit = self._get_motor_limit(motor_y)

        signal = Signal(
            source="device_readback",
            x=SignalData(name=motor_x, entry=motor_x_entry, limits=motor_x_limit),
            y=SignalData(name=motor_y, entry=motor_y_entry, limits=motor_y_limit),
        )
        self.config.signals = signal

        # reconnect the signals
        self._connect_motor_to_slots()

        self.database_buffer = {"x": [], "y": []}

        # Redraw the motor map
        self._make_motor_map()

    def get_data(self) -> dict:
        """
        Get the data of the motor map.

        Returns:
            dict: Data of the motor map.
        """
        data = {"x": self.database_buffer["x"], "y": self.database_buffer["y"]}
        return data

    def reset_history(self):
        """
        Reset the history of the motor map.
        """
        self.database_buffer["x"] = [self.database_buffer["x"][-1]]
        self.database_buffer["y"] = [self.database_buffer["y"][-1]]
        self.update_signal.emit()

    def set_color(self, color: str | tuple):
        """
        Set color of the motor trace.

        Args:
            color(str|tuple): Color of the motor trace. Can be HEX(str) or RGBA(tuple).
        """
        if isinstance(color, str):
            color = Colors.validate_color(color)
            color = Colors.hex_to_rgba(color, 255)
        self.config.color = color
        self.update_signal.emit()

    def set_max_points(self, max_points: int) -> None:
        """
        Set the maximum number of points to display.

        Args:
            max_points(int): Maximum number of points to display.
        """
        self.config.max_points = max_points
        self.update_signal.emit()

    def set_precision(self, precision: int) -> None:
        """
        Set the decimal precision of the motor position.

        Args:
            precision(int): Decimal precision of the motor position.
        """
        self.config.precision = precision
        self.update_signal.emit()

    def set_num_dim_points(self, num_dim_points: int) -> None:
        """
        Set the number of dim points for the motor map.

        Args:
            num_dim_points(int): Number of dim points.
        """
        self.config.num_dim_points = num_dim_points
        self.update_signal.emit()

    def set_background_value(self, background_value: int) -> None:
        """
        Set the background value of the motor map.

        Args:
            background_value(int): Background value of the motor map.
        """
        self.config.background_value = background_value
        self._swap_limit_map()

    def set_scatter_size(self, scatter_size: int) -> None:
        """
        Set the scatter size of the motor map plot.

        Args:
            scatter_size(int): Size of the scatter points.
        """
        self.config.scatter_size = scatter_size
        self.update_signal.emit()

    def _disconnect_current_motors(self):
        """Disconnect the current motors from the slots."""
        if self.motor_x is not None and self.motor_y is not None:
            endpoints = [
                MessageEndpoints.device_readback(self.motor_x),
                MessageEndpoints.device_readback(self.motor_y),
            ]
            self.bec_dispatcher.disconnect_slot(self.on_device_readback, endpoints)

    def _connect_motor_to_slots(self):
        """Connect motors to slots."""
        self._disconnect_current_motors()

        self.motor_x = self.config.signals.x.name
        self.motor_y = self.config.signals.y.name

        endpoints = [
            MessageEndpoints.device_readback(self.motor_x),
            MessageEndpoints.device_readback(self.motor_y),
        ]

        self.bec_dispatcher.connect_slot(self.on_device_readback, endpoints)

    def _swap_limit_map(self):
        """Swap the limit map."""
        self.plot_item.removeItem(self.plot_components["limit_map"])
        if self.config.signals.x.limits is not None and self.config.signals.y.limits is not None:
            self.plot_components["limit_map"] = self._make_limit_map(
                self.config.signals.x.limits, self.config.signals.y.limits
            )
            self.plot_components["limit_map"].setZValue(-1)
            self.plot_item.addItem(self.plot_components["limit_map"])

    def _make_motor_map(self):
        """
        Create the motor map plot.
        """
        # Create limit map
        motor_x_limit = self.config.signals.x.limits
        motor_y_limit = self.config.signals.y.limits
        if motor_x_limit is not None or motor_y_limit is not None:
            self.plot_components["limit_map"] = self._make_limit_map(motor_x_limit, motor_y_limit)
            self.plot_item.addItem(self.plot_components["limit_map"])
            self.plot_components["limit_map"].setZValue(-1)

        # Create scatter plot
        scatter_size = self.config.scatter_size
        self.plot_components["scatter"] = pg.ScatterPlotItem(
            size=scatter_size, brush=pg.mkBrush(255, 255, 255, 255)
        )
        self.plot_item.addItem(self.plot_components["scatter"])
        self.plot_components["scatter"].setZValue(0)

        # Enable Grid
        self.set_grid(True, True)

        # Add the crosshair for initial motor coordinates
        initial_position_x = self._get_motor_init_position(
            self.motor_x, self.config.signals.x.entry, self.config.precision
        )
        initial_position_y = self._get_motor_init_position(
            self.motor_y, self.config.signals.y.entry, self.config.precision
        )

        self.database_buffer["x"] = [initial_position_x]
        self.database_buffer["y"] = [initial_position_y]

        self.plot_components["scatter"].setData([initial_position_x], [initial_position_y])
        self._add_coordinantes_crosshair(initial_position_x, initial_position_y)

        # Set default labels for the plot
        self.set(x_label=f"Motor X ({self.motor_x})", y_label=f"Motor Y ({self.motor_y})")

        self.update_signal.emit()

    def _add_coordinantes_crosshair(self, x: float, y: float) -> None:
        """
        Add crosshair to the plot to highlight the current position.

        Args:
            x(float): X coordinate.
            y(float): Y coordinate.
        """

        # Crosshair to highlight the current position
        highlight_H = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen(color="r", width=1, style=QtCore.Qt.DashLine)
        )
        highlight_V = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen(color="r", width=1, style=QtCore.Qt.DashLine)
        )

        # Add crosshair to the curve list for future referencing
        self.plot_components["highlight_H"] = highlight_H
        self.plot_components["highlight_V"] = highlight_V

        # Add crosshair to the plot
        self.plot_item.addItem(highlight_H)
        self.plot_item.addItem(highlight_V)

        highlight_V.setPos(x)
        highlight_H.setPos(y)

    def _make_limit_map(self, limits_x: list, limits_y: list) -> pg.ImageItem:
        """
        Create a limit map for the motor map plot.

        Args:
            limits_x(list): Motor limits for the x axis.
            limits_y(list): Motor limits for the y axis.

        Returns:
            pg.ImageItem: Limit map.
        """
        limit_x_min, limit_x_max = limits_x
        limit_y_min, limit_y_max = limits_y

        map_width = int(limit_x_max - limit_x_min + 1)
        map_height = int(limit_y_max - limit_y_min + 1)

        # Create limits map
        background_value = self.config.background_value
        limit_map_data = np.full((map_width, map_height), background_value, dtype=np.float32)
        limit_map = pg.ImageItem()
        limit_map.setImage(limit_map_data)

        # Translate and scale the image item to match the motor coordinates
        tr = QtGui.QTransform()
        tr.translate(limit_x_min, limit_y_min)
        limit_map.setTransform(tr)

        return limit_map

    def _get_motor_init_position(self, name: str, entry: str, precision: int) -> float:
        """
        Get the motor initial position from the config.

        Args:
            name(str): Motor name.
            entry(str): Motor entry.
            precision(int): Decimal precision of the motor position.

        Returns:
            float: Motor initial position.
        """
        init_position = round(float(self.dev[name].read()[entry]["value"]), precision)
        return init_position

    def _validate_signal_entries(
        self,
        x_name: str,
        y_name: str,
        x_entry: str | None,
        y_entry: str | None,
        validate_bec: bool = True,
    ) -> tuple[str, str]:
        """
        Validate the signal name and entry.

        Args:
            x_name(str): Name of the x signal.
            y_name(str): Name of the y signal.
            x_entry(str|None): Entry of the x signal.
            y_entry(str|None): Entry of the y signal.
            validate_bec(bool, optional): If True, validate the signal with BEC. Defaults to True.

        Returns:
            tuple[str,str]: Validated x and y entries.
        """
        if validate_bec:
            x_entry = self.entry_validator.validate_signal(x_name, x_entry)
            y_entry = self.entry_validator.validate_signal(y_name, y_entry)
        else:
            x_entry = x_name if x_entry is None else x_entry
            y_entry = y_name if y_entry is None else y_entry
        return x_entry, y_entry

    def _get_motor_limit(self, motor: str) -> Union[list | None]:  # TODO check if works correctly
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

    @Slot()
    def _update_plot(self, _=None):
        """Update the motor map plot."""
        # If the number of points exceeds max_points, delete the oldest points
        if len(self.database_buffer["x"]) > self.config.max_points:
            self.database_buffer["x"] = self.database_buffer["x"][-self.config.max_points :]
            self.database_buffer["y"] = self.database_buffer["y"][-self.config.max_points :]

        x = self.database_buffer["x"]
        y = self.database_buffer["y"]

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
        self.plot_components["scatter"].setData(
            x=x, y=y, brush=brushes, pen=None, size=scatter_size
        )

        # Get last know position for crosshair
        current_x = x[-1]
        current_y = y[-1]

        # Update the crosshair
        self.plot_components["highlight_V"].setPos(current_x)
        self.plot_components["highlight_H"].setPos(current_y)

        # TODO not update title but some label
        # Update plot title
        precision = self.config.precision
        self.set_title(
            f"Motor position: ({round(float(current_x),precision)}, {round(float(current_y),precision)})"
        )

    @Slot(dict, dict)
    def on_device_readback(self, msg: dict, metadata: dict) -> None:
        """
        Update the motor map plot with the new motor position.

        Args:
            msg(dict): Message from the device readback.
            metadata(dict): Metadata of the message.
        """
        if self.motor_x is None or self.motor_y is None:
            return

        if self.motor_x in msg["signals"]:
            x = msg["signals"][self.motor_x]["value"]
            self.database_buffer["x"].append(x)
            self.database_buffer["y"].append(self.database_buffer["y"][-1])

        elif self.motor_y in msg["signals"]:
            y = msg["signals"][self.motor_y]["value"]
            self.database_buffer["y"].append(y)
            self.database_buffer["x"].append(self.database_buffer["x"][-1])

        self.update_signal.emit()

    def cleanup(self):
        """Cleanup the widget."""
        self._disconnect_current_motors()
