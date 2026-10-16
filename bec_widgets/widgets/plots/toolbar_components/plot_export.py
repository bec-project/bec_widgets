from __future__ import annotations

import traceback

import numpy as np
import pyqtgraph as pg
from pyqtgraph import functions as fn
from qtpy.QtCore import Qt

from bec_widgets.utils.error_popups import SafeSlot, WarningPopupUtility
from bec_widgets.utils.toolbars.actions import MaterialIconAction, SwitchableToolBarAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents
from bec_widgets.utils.toolbars.connections import BundleConnection


def plot_export_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a plot export toolbar bundle.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The plot export toolbar bundle.
    """
    components.add_safe(
        "save",
        MaterialIconAction(
            icon_name="save", tooltip="Open Export Dialog", parent=components.toolbar
        ),
    )
    components.add_safe(
        "matplotlib",
        MaterialIconAction(
            icon_name="photo_library", tooltip="Open Matplotlib Dialog", parent=components.toolbar
        ),
    )
    components.add_safe(
        "export_switch",
        SwitchableToolBarAction(
            actions={
                "save": components.get_action_reference("save")(),
                "matplotlib": components.get_action_reference("matplotlib")(),
            },
            initial_action="save",
            tooltip="Export Plot",
            checkable=False,
            parent=components.toolbar,
        ),
    )
    bundle = ToolbarBundle("plot_export", components)
    bundle.add_action("export_switch")
    return bundle


# pyqtgraph symbol names mapped to matplotlib markers, as in pyqtgraph's own MatplotlibExporter
_SYMBOL_PG_TO_MPL = {
    "o": "o",
    "s": "s",
    "t": "v",
    "t1": "^",
    "t2": ">",
    "t3": "<",
    "d": "d",
    "+": "P",
    "x": "X",
    "p": "p",
    "h": "h",
    "star": "*",
    "arrow_up": 6,
    "arrow_right": 5,
    "arrow_down": 7,
    "arrow_left": 4,
    "crosshair": "o",
    "|": "|",
    "_": "_",
}


def _is_per_point(spec) -> bool:
    """Return True if a pen/brush option holds one entry per data point."""
    return (
        isinstance(spec, (list, np.ndarray))
        and len(spec) > 0
        and not isinstance(spec[0], (int, float, np.number))
    )


def _brush_colors(spec, default=None) -> list[tuple] | tuple | None:
    """Convert a pyqtgraph brush option (single or per point) to matplotlib RGBA colors."""
    if spec is None:
        return default
    if _is_per_point(spec):
        return [_brush_colors(entry, default) for entry in spec]
    brush = fn.mkBrush(spec)
    if brush.style() == Qt.BrushStyle.NoBrush:
        return "none"
    return brush.color().getRgbF()


def _pen_colors(spec, default=None) -> list[tuple] | tuple | None:
    """Convert a pyqtgraph pen option (single or per point) to matplotlib RGBA colors."""
    if spec is None:
        return default
    if _is_per_point(spec):
        return [_pen_colors(entry, default) for entry in spec]
    pen = fn.mkPen(spec)
    if pen.style() == Qt.PenStyle.NoPen:
        return "none"
    return pen.color().getRgbF()


def export_to_matplotlib(plot_item: pg.PlotItem):
    """
    Open the curves and scatter points of a plot item in a Matplotlib window.

    Unlike pyqtgraph's MatplotlibExporter, this also handles points that each have their own
    color (ScatterWaveform, MotorMap). Requires matplotlib to be installed.

    Args:
        plot_item (pg.PlotItem): The plot item to export.

    Returns:
        MatplotlibWindow: The opened Matplotlib window.
    """
    from pyqtgraph.exporters.Matplotlib import MatplotlibExporter, MatplotlibWindow

    window = MatplotlibWindow()
    MatplotlibExporter.windows.append(window)
    try:
        _draw_plot_item(window.getFigure(), plot_item)
    except Exception:
        window.close()
        raise
    window.draw()
    return window


def _mpl_marker(symbol) -> str | int:
    """Map a pyqtgraph symbol to a matplotlib marker; other symbols become circles."""
    return _SYMBOL_PG_TO_MPL.get(symbol, "o") if isinstance(symbol, str) else "o"


def _draw_plot_item(fig, plot_item: pg.PlotItem):
    """Draw the visible data items of a plot item into a new axes of a matplotlib figure."""
    x_axis = plot_item.getAxis("bottom")
    y_axis = plot_item.getAxis("left")
    # Scale the data like pyqtgraph does so matplotlib doesn't add its own scale factor label
    x_scale = x_axis.autoSIPrefixScale if x_axis.autoSIPrefix else 1.0
    y_scale = y_axis.autoSIPrefixScale if y_axis.autoSIPrefix else 1.0

    ax = fig.add_subplot(111)
    ax.set_title(plot_item.titleLabel.text)
    ax.spines["right"].set_color("none")
    ax.spines["top"].set_color("none")
    ax.xaxis.set_ticks_position("bottom")

    for item in plot_item.curves:
        if not item.isVisible():
            continue
        x, y = item.getData()
        if x is None or y is None or len(x) == 0:
            continue
        x = np.asarray(x) * x_scale
        y = np.asarray(y) * y_scale
        if isinstance(item, pg.ScatterPlotItem):
            _draw_scatter_item(ax, item, x, y)
        else:
            _draw_data_item(ax, item, x, y)

    (x_min, x_max), (y_min, y_max) = plot_item.viewRange()
    ax.set_xbound(x_min * x_scale, x_max * x_scale)
    ax.set_ybound(y_min * y_scale, y_max * y_scale)
    ax.set_xlabel(x_axis.label.toPlainText())
    ax.set_ylabel(y_axis.label.toPlainText())


def _draw_data_item(ax, item: pg.PlotDataItem, x: np.ndarray, y: np.ndarray):
    """Draw a curve (line, fill and symbols) of a PlotDataItem or PlotCurveItem."""
    opts = item.opts
    pen = fn.mkPen(opts.get("pen"))
    if pen.style() != Qt.PenStyle.NoPen:
        if opts.get("fillLevel") is not None and opts.get("fillBrush") is not None:
            ax.fill_between(
                x=x, y1=y, y2=opts["fillLevel"], facecolor=_brush_colors(opts["fillBrush"])
            )
        ax.plot(x, y, color=pen.color().getRgbF(), linewidth=pen.widthF(), linestyle="-")

    symbol = opts.get("symbol")
    if symbol is None:
        return
    face = _brush_colors(opts.get("symbolBrush"))
    edge = _pen_colors(opts.get("symbolPen"))
    size = opts.get("symbolSize", 10)
    if _is_per_point(face) or _is_per_point(edge) or np.ndim(size) > 0:
        ax.scatter(
            x,
            y,
            marker=_mpl_marker(symbol),
            s=np.asarray(size, dtype=float) ** 2,
            facecolors=face,
            edgecolors=edge,
            zorder=3,
        )
    else:
        ax.plot(
            x,
            y,
            linestyle="",
            marker=_mpl_marker(symbol),
            markersize=size,
            markerfacecolor=face,
            markeredgecolor=edge,
        )


def _draw_scatter_item(ax, item: pg.ScatterPlotItem, x: np.ndarray, y: np.ndarray):
    """Draw a ScatterPlotItem, whose brushes, pens and sizes may be set per point."""
    opts = item.opts
    face = _brush_colors(list(item.data["brush"]), default=_brush_colors(opts["brush"]))
    edge = _pen_colors(list(item.data["pen"]), default=_pen_colors(opts["pen"]))
    sizes = np.where(item.data["size"] < 0, opts["size"], item.data["size"])
    ax.scatter(
        x,
        y,
        marker=_mpl_marker(opts["symbol"]),
        s=np.asarray(sizes, dtype=float) ** 2,
        facecolors=face,
        edgecolors=edge,
        zorder=3,
    )


class PlotExportConnection(BundleConnection):
    def __init__(self, components: ToolbarComponents, target_widget):
        super().__init__()
        self.bundle_name = "plot_export"
        self.components = components
        self.target_widget = target_widget
        self._connected = False  # Track if the connection has been made

    def connect(self):
        self._connected = True
        # Connect the actions to the target widget
        self.components.get_action_reference("save")().action.triggered.connect(self.export_dialog)
        self.components.get_action_reference("matplotlib")().action.triggered.connect(
            self.matplotlib_dialog
        )

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the actions from the target widget
        self.components.get_action_reference("save")().action.triggered.disconnect(
            self.export_dialog
        )
        self.components.get_action_reference("matplotlib")().action.triggered.disconnect(
            self.matplotlib_dialog
        )

    @SafeSlot()
    def export_dialog(self):
        """
        Open the export dialog for the plot widget.
        """
        if self.target_widget:
            scene = self.target_widget.plot_item.scene()
            scene.contextMenuItem = self.target_widget.plot_item
            scene.showExportDialog()

    @SafeSlot()
    def matplotlib_dialog(self):
        """
        Export the plot widget to Matplotlib.
        """
        if self.target_widget:
            try:
                import matplotlib as mpl

                export_to_matplotlib(self.target_widget.plot_item)
            except ModuleNotFoundError:
                warning_util = WarningPopupUtility()
                warning_util.show_warning(
                    title="Matplotlib not installed",
                    message="Matplotlib is required for this feature.",
                    detailed_text="Please install matplotlib in your Python environment by using 'pip install matplotlib'.",
                )
                return
            except TypeError:
                warning_util = WarningPopupUtility()
                error_msg = traceback.format_exc()
                warning_util.show_warning(
                    title="Matplotlib TypeError",
                    message="Matplotlib exporter could not resolve the plot item.",
                    detailed_text=error_msg,
                )
                return
