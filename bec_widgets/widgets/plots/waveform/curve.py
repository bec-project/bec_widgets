from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from pydantic import BaseModel, Field, field_validator
from qtpy import QtCore

from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.colors import Colors

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.plots.waveform.waveform import Waveform

logger = bec_logger.logger


# noinspection PyDataclass
class DeviceSignal(BaseModel):
    """The configuration of a signal in the 1D waveform widget."""

    device: str
    signal: str
    dap: str | list[str] | None = None
    dap_oversample: int = 1
    dap_parameters: dict | list | None = None

    model_config: dict = {"validate_assignment": True}


# noinspection PyDataclass
class CurveConfig(ConnectionConfig):
    parent_id: str | None = Field(None, description="The parent plot of the curve.")
    label: str | None = Field(None, description="The label of the curve.")
    color: str | tuple | None = Field(None, description="The color of the curve.")
    symbol: str | None = Field("o", description="The symbol of the curve.")
    symbol_color: str | tuple | None = Field(
        None, description="The color of the symbol of the curve."
    )
    symbol_size: int | None = Field(7, description="The size of the symbol of the curve.")
    symbol_point_limit: int | None = Field(
        1000,
        description=(
            "Hide the symbol once the curve holds more than this many points. "
            "None keeps the symbol at every data size."
        ),
    )
    pen_width: int | None = Field(4, description="The width of the pen of the curve.")
    pen_style: Literal["solid", "dash", "dot", "dashdot"] | None = Field(
        "solid", description="The style of the pen of the curve."
    )
    source: Literal["device", "dap", "custom", "history"] = Field(
        "custom", description="The source of the curve."
    )
    signal: DeviceSignal | None = Field(None, description="The signal of the curve.")
    scan_id: str | None = Field(None, description="Scan ID to be used when `source` is 'history'.")
    scan_number: int | None = Field(
        None, description="Scan index to be used when `source` is 'history'."
    )
    current_x_mode: str | None = Field(None, description="The current x mode of the history curve.")
    parent_label: str | None = Field(
        None, description="The label of the parent plot, only relevant for dap curves."
    )

    model_config: dict = {"validate_assignment": True}

    _validate_color = field_validator("color")(Colors.validate_color)
    _validate_symbol_color = field_validator("symbol_color")(Colors.validate_color)


class Curve(BECConnector, pg.PlotDataItem):
    # Class-level defaults: pg.PlotDataItem.__init__ calls setData before Curve.__init__
    # has set its own state.
    _data_version = 0
    #: The full data of a curve that is drawn decimated, and the slice shown of it
    #: (see Waveform._apply_lod_windows).
    _lod_raw: tuple | None = None
    _lod_window: tuple[int, int] | None = None
    #: ((x_min, x_max), (y_min, y_max)) of the whole series, for a curve that draws a
    #: reduced or windowed copy of it; None for a curve that draws its data as it is.
    _full_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None
    #: For a history curve whose column is not held whole: what the DataAPI holds of it
    #: (``metadata["view"]`` of its source, see Waveform._render_view_curve).
    _view: dict | None = None
    #: The rows asked for and not delivered yet.
    _view_pending: tuple[int, int] | None = None
    USER_ACCESS = [
        "remove",
        "_rpc_id",
        "_config_dict",
        "_get_displayed_data",
        "set",
        "set_data",
        "set_color",
        "set_color_map_z",
        "set_symbol",
        "set_symbol_color",
        "set_symbol_size",
        "set_pen_width",
        "set_pen_style",
        "get_data",
        "dap_params",
        "dap_summary",
        "dap_oversample",
        "dap_oversample.setter",
    ]

    def __init__(
        self,
        name: str | None = None,
        config: CurveConfig | None = None,
        gui_id: str | None = None,
        parent_item: Waveform | None = None,
        **kwargs,
    ):
        # Set before PlotDataItem.__init__, whose first setData already runs updateItems().
        self._symbols_suppressed = False
        if config is None:
            config = CurveConfig(label=name, widget_class=self.__class__.__name__)
            self.config = config
        else:
            self.config = config
        self.parent_item = parent_item
        object_name = name.replace("-", "_").replace(" ", "_") if name else None
        super().__init__(name=name, object_name=object_name, config=config, gui_id=gui_id, **kwargs)

        self.apply_config()
        self.dap_params = None
        self.dap_summary = None
        self._data_version = 0
        self._last_dap_request_fingerprint: tuple | None = None
        if kwargs:
            self.set(**kwargs)
        # Activate setClipToView, to boost performance for large datasets per default
        self.setClipToView(True)

    def parent(self):
        return self.parent_item

    def apply_config(self, config: dict | CurveConfig | None = None, **kwargs) -> None:
        """
        Apply the configuration to the curve.

        Args:
            config(dict|CurveConfig, optional): The configuration to apply.
        """

        if config is not None:
            if isinstance(config, dict):
                config = CurveConfig(**config)
            self.config = config

        pen_style_map = {
            "solid": QtCore.Qt.SolidLine,
            "dash": QtCore.Qt.DashLine,
            "dot": QtCore.Qt.DotLine,
            "dashdot": QtCore.Qt.DashDotLine,
        }
        pen_style = pen_style_map.get(self.config.pen_style, QtCore.Qt.SolidLine)

        pen = pg.mkPen(color=self.config.color, width=self.config.pen_width, style=pen_style)
        self.setPen(pen)

        if self.config.symbol:
            symbol_color = self.config.symbol_color or self.config.color
            brush = pg.mkBrush(color=symbol_color)

            self.setSymbolBrush(brush)
            self.setSymbolSize(self.config.symbol_size)
            # updateItems() keeps it hidden while the curve is above the symbol limit.
            self.setSymbol(self.config.symbol)

    def dataBounds(self, ax, frac=1.0, orthoRange=None):
        """
        Range of the data along one axis, as the view box asks for it to autorange.

        pyqtgraph answers from what is drawn, which with clipToView and downsampling
        depends on the view: a new range changes the answer, and the view moves again.
        A curve that knows the bounds of its whole series (``_full_bounds``) answers with
        those instead.
        """
        bounds = self._full_bounds
        if bounds is None or frac < 1.0 or orthoRange is not None:
            return super().dataBounds(ax, frac, orthoRange)
        return bounds[ax]

    def setData(self, *args, **kwargs):
        """Wrap ``PlotDataItem.setData`` to track how often the data changes."""
        # getattr guards against setData being reached before __init__ sets the field.
        self._data_version = getattr(self, "_data_version", 0) + 1
        super().setData(*args, **kwargs)

    def updateItems(self, styleUpdate: bool = True):
        """
        Redraw the curve and its symbols, hiding the symbol above the symbol limit.

        pyqtgraph draws symbols through ``ScatterPlotItem``, which builds a style
        tuple per point in Python (``SymbolAtlas._keys``). That is linear in the
        number of points and dominates everything else: at 50k points a ``setData``
        costs ~90 ms with a symbol and ~0.5 ms without. Scans routinely exceed the
        limit, so the symbol is dropped there and restored when the data shrinks.

        pyqtgraph calls this after every data or style change, once the new dataset
        is in place, so the decision counts the points of the stored dataset, whatever
        form ``setData`` received them in. It also overrides the default ``"o"`` that
        pyqtgraph adds for ``symbolSize``/``symbolPen``/``symbolBrush`` without a symbol.

        Args:
            styleUpdate(bool): Passed on to ``PlotDataItem.updateItems``.
        """
        if getattr(self, "config", None) is not None:
            suppressed = self._exceeds_symbol_limit(self._point_count())
            if suppressed:
                self.opts["symbol"] = None
            elif getattr(self, "_symbols_suppressed", False):
                self.opts["symbol"] = self.config.symbol
            self._symbols_suppressed = suppressed
        super().updateItems(styleUpdate=styleUpdate)

    def _exceeds_symbol_limit(self, data_length: int) -> bool:
        """
        Whether a dataset of this length is above the configured symbol limit.

        Args:
            data_length(int): Number of points.

        Returns:
            bool: True if the symbol should be hidden; a limit of None never hides it.
        """
        limit = self.config.symbol_point_limit
        return limit is not None and data_length > limit

    def _point_count(self) -> int:
        """
        Number of points in the curve's current dataset.

        Returns:
            int: The number of points, 0 for an empty curve.
        """
        dataset = getattr(self, "_dataset", None)
        return 0 if dataset is None else len(dataset.y)

    @property
    def dap_params(self):
        """
        Get the dap parameters.
        """
        return self._dap_params

    @dap_params.setter
    def dap_params(self, value):
        """
        Set the dap parameters.

        Args:
            value(dict): The dap parameters.
        """
        self._dap_params = value

    @property
    def dap_summary(self):
        """
        Get the dap summary.
        """
        return self._dap_report

    @dap_summary.setter
    def dap_summary(self, value):
        """
        Set the dap summary.
        """
        self._dap_report = value

    @property
    def dap_oversample(self):
        """
        Get the dap oversample.
        """
        return self.config.signal.dap_oversample

    @dap_oversample.setter
    def dap_oversample(self, value):
        """
        Set the dap oversample.

        Args:
            value(int): The dap oversample.
        """
        self.config.signal.dap_oversample = value
        self.parent_item.request_dap()  # do immediate request for dap update

    @property
    def data_version(self) -> int:
        """Monotonic counter bumped on every ``setData`` call."""
        return self._data_version

    def set_data(self, x: list | np.ndarray, y: list | np.ndarray):
        """
        Set the data of the curve.

        Args:
            x(list|np.ndarray): The x data.
            y(list|np.ndarray): The y data.

        Raises:
            ValueError: If the source is not custom.
        """
        if self.config.source in ["custom", "history"]:
            self.setData(x, y)
            self.parent_item.request_dap_update.emit()
        else:
            raise ValueError(f"Source {self.config.source} do not allow custom data setting.")

    def set(self, **kwargs):
        """
        Set the properties of the curve.

        Args:
            **kwargs: Keyword arguments for the properties to be set.

        Possible properties:
            - color: str
            - symbol: str
            - symbol_color: str
            - symbol_size: int
            - symbol_point_limit: int | None
            - pen_width: int
            - pen_style: Literal["solid", "dash", "dot", "dashdot"]
        """

        # Mapping of keywords to setter methods
        method_map = {
            "color": self.set_color,
            "color_map_z": self.set_color_map_z,
            "symbol": self.set_symbol,
            "symbol_color": self.set_symbol_color,
            "symbol_size": self.set_symbol_size,
            "symbol_point_limit": self._set_symbol_point_limit,
            "pen_width": self.set_pen_width,
            "pen_style": self.set_pen_style,
        }
        for key, value in kwargs.items():
            if key in method_map:
                method_map[key](value)
            else:
                logger.warning(f"Warning: '{key}' is not a recognized property.")

    def set_color(self, color: str, symbol_color: str | None = None):
        """
        Change the color of the curve.

        Args:
            color(str): Color of the curve.
            symbol_color(str, optional): Color of the symbol. Defaults to None.
        """
        self.config.color = color
        self.config.symbol_color = symbol_color or color
        self.apply_config()

    def set_symbol(self, symbol: str):
        """
        Change the symbol of the curve.

        Above ``symbol_point_limit`` points the symbol stays hidden until the data
        shrinks or the limit is raised with ``set(symbol_point_limit=...)``.

        Args:
            symbol(str): Symbol of the curve.
        """
        self.config.symbol = symbol
        # While the curve is above the symbol limit, updateItems() keeps the symbol
        # hidden; the config keeps the request for when the data drops below it.
        self.setSymbol(symbol)
        self.updateItems()

    def set_symbol_color(self, symbol_color: str):
        """
        Change the symbol color of the curve.

        Args:
            symbol_color(str): Color of the symbol.
        """
        self.config.symbol_color = symbol_color
        self.apply_config()

    def set_symbol_size(self, symbol_size: int):
        """
        Change the symbol size of the curve.

        Args:
            symbol_size(int): Size of the symbol.
        """
        self.config.symbol_size = symbol_size
        self.apply_config()

    def _set_symbol_point_limit(self, limit: int | None):
        """
        Change the number of points above which the symbol of the curve is hidden.

        Args:
            limit(int | None): Number of points; None keeps the symbol at every data size.
        """
        self.config.symbol_point_limit = limit
        self.updateItems()

    def set_pen_width(self, pen_width: int):
        """
        Change the pen width of the curve.

        Args:
            pen_width(int): Width of the pen.
        """
        self.config.pen_width = pen_width
        self.apply_config()

    def set_pen_style(self, pen_style: Literal["solid", "dash", "dot", "dashdot"]):
        """
        Change the pen style of the curve.

        Args:
            pen_style(Literal["solid", "dash", "dot", "dashdot"]): Style of the pen.
        """
        self.config.pen_style = pen_style
        self.apply_config()

    def set_color_map_z(self, colormap: str):
        """
        Set the colormap for the scatter plot z gradient.

        Args:
            colormap(str): Colormap for the scatter plot.
        """
        self.config.color_map_z = colormap
        self.apply_config()
        self.parent_item.update_with_scan_history(-1)

    def get_data(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        """
        Get the data of the curve.
        Returns:
            tuple[np.ndarray,np.ndarray]: X and Y data of the curve.
        """
        try:
            x_data, y_data = self.getOriginalDataset()
        except TypeError:
            x_data, y_data = np.array([]), np.array([])
        return x_data, y_data

    def clear_data(self):
        """
        Clear the data of the curve.
        """
        self.setData([], [])

    def remove(self):
        """Remove the curve from the plot."""
        # self.parent_item.removeItem(self)
        self.parent_item.remove_curve(self.name())
        super().remove()

    def _get_displayed_data(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Get the displayed data of the curve.

        Returns:
            tuple[np.ndarray, np.ndarray]: The x and y data of the curve.
        """
        x_data, y_data = self.getData()
        if x_data is None or y_data is None:
            return np.array([]), np.array([])
        return x_data, y_data
