"""Interactive, device-independent preview for two-axis mapping scans."""

from dataclasses import dataclass
from math import isfinite, prod

import numpy as np
import pyqtgraph as pg
from bec_lib.signature_serializer import dict_to_signature
from qtpy.QtCore import Qt, QThreadPool, QTimer, Signal
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import Worker
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot

try:
    from bec_lib.path_optimization import PathOptimizerMixin
    from bec_lib.position_generators import Direction
    from bec_lib.scan_preview import generate_scan_positions
except ImportError:  # BW also supports BEC releases predating the preview API.
    generate_scan_positions = None

_GRID = "bec_lib.position_generators.nd_grid_positions"
_FERMAT = "bec_lib.position_generators.fermat_spiral_pos"
_BOUND_NAMES = ("start_motor1", "stop_motor1", "start_motor2", "stop_motor2")
_MAX_GENERATION_POINTS = 100_000
_MAX_DISPLAY_POINTS = 5_000
_MAX_NEAREST_POINTS = 5_000
_PREVIEW_MAPPINGS = {
    _GRID: {"axes": {"bundle": [1, 2, 3]}, "snaked": "snaked"},
    _FERMAT: {
        **dict(zip(("m1_start", "m1_stop", "m2_start", "m2_stop"), _BOUND_NAMES)),
        "step": "step",
        "spiral_type": "spiral_type",
    },
}


def supports_preview(info: dict) -> bool:
    """Check whether both the server and this client support the advertised generator."""
    generator = info.get("position_preview")
    if (
        generate_scan_positions is None
        or generator not in _PREVIEW_MAPPINGS
        or info.get("position_preview_parameter_mapping") != _PREVIEW_MAPPINGS[generator]
        or not info.get("signature")
    ):
        return False
    if generator == _GRID:
        return info.get("arg_bundle_size", {}).get("bundle") == 4 and tuple(
            info.get("arg_input", {})
        ) == ("device", "start", "stop", "steps")
    return not info.get("arg_input")


@dataclass(frozen=True)
class PathInputs:
    """A snapshot of the form, with geometry ordered by motor."""

    info: dict
    parameters: dict
    motors: tuple[str, str]
    bounds: tuple[float, float, float, float]

    @property
    def uses_bundles(self) -> bool:
        """Whether the bounds come from repeated positional form fields."""
        return self.info["position_preview"] == _GRID

    @property
    def optimization(self) -> str | None:
        """Return the trajectory setting for scans that apply an optimizer."""
        if self.info["position_preview"] == _FERMAT:
            return self.parameters.get("optim_trajectory")
        return None

    @classmethod
    def from_form(cls, info: dict, args: list, kwargs: dict) -> "PathInputs":
        """Bind scan parameters and reject oversized or incomplete geometry."""
        if not supports_preview(info):
            raise ValueError("This scan does not support a path preview.")
        signature = dict_to_signature(info["signature"])
        bound = signature.bind(*args, **{k: v for k, v in kwargs.items() if k != "metadata"})
        bound.apply_defaults()
        parameters = dict(bound.arguments)
        if info["position_preview"] == _GRID:
            if len(args) != 8:
                raise ValueError("Select exactly two grid axes to preview the path.")
            motor_x, x0, x1, nx, motor_y, y0, y1, ny = args
            if nx < 1 or ny < 1:
                raise ValueError("Set a positive point count for both axes.")
            work = prod((nx, ny))
        else:
            motor_x, motor_y = parameters["motor1"], parameters["motor2"]
            x0, x1, y0, y1 = (parameters[key] for key in _BOUND_NAMES)
            step = parameters["step"]
            if not isfinite(step) or step <= 0:
                raise ValueError("Set a positive point spacing.")
            work = abs(x1 - x0) * abs(y1 - y0) * 3.2 / step**2
        if not motor_x or not motor_y or motor_x == motor_y:
            raise ValueError("Select two distinct scan motors.")
        if not all(isfinite(value) for value in (x0, x1, y0, y1)):
            raise ValueError("Set finite scan bounds.")
        if work > _MAX_GENERATION_POINTS:
            raise ValueError(
                "Path is too dense to preview. Reduce the point count or increase spacing."
            )
        return cls(info, parameters, (motor_x, motor_y), (x0, x1, y0, y1))


def _optimize_fermat(points: np.ndarray, inputs: PathInputs, method: str) -> np.ndarray:
    # Match FermatSpiralScan.prepare_scan and ScanComponents.optimize_trajectory.
    optimizer = PathOptimizerMixin()
    if method == "corridor":
        x_start, x_stop, _, _ = inputs.bounds
        direction = Direction.ASCENDING if x_stop > x_start else Direction.DESCENDING
        return optimizer.optimize_corridor(
            points, num_iterations=5, fast_axis=0, first_corridor_direction=direction, snaked=True
        )
    if method == "shell":
        return optimizer.optimize_shell(points, num_iterations=5)
    if method == "nearest":
        if len(points) > _MAX_NEAREST_POINTS:
            raise ValueError("Path is too dense for nearest optimization in the preview.")
        return optimizer.optimize_nearest_neighbor(points)
    raise ValueError(f"Unsupported trajectory optimization: {method}")


def _generate(worker_signal, inputs: PathInputs, revision: int) -> None:
    try:
        points = generate_scan_positions(inputs.info, inputs.parameters)
        if not points.size:
            raise ValueError("No positions fit inside the scan region.")
        if method := inputs.optimization:
            points = _optimize_fermat(points, inputs, method)
        indices = np.linspace(0, len(points) - 1, min(len(points), _MAX_DISPLAY_POINTS), dtype=int)
        result = {"revision": revision, "points": points[indices], "count": len(points)}
    except (ArithmeticError, ImportError, AttributeError, TypeError, KeyError, ValueError) as exc:
        result = {"revision": revision, "error": str(exc)}
    worker_signal.emit(result)


class PathPreview(QWidget):
    """Plot a scan form's planned positions and let the operator adjust its bounds."""

    bounds_changed = Signal(object, object)

    def __init__(self, read_form, parent=None):
        super().__init__(parent)
        self._read_form = read_form
        self._revision = 0
        self._started_revision = 0
        self._worker = None
        self._active = False
        self._fit = True
        self._drag_revision = None
        self._inputs = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._refresh)
        layout = QVBoxLayout(self)
        self._status = QLabel("Path preview", self, wordWrap=True)
        layout.addWidget(self._status)
        self._plot = pg.PlotWidget(self, enableMenu=False)
        self._plot.setMinimumHeight(235)
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.hideButtons()
        self._plot.setToolTip("Drag the rectangle to move it or its corner to resize it.")
        layout.addWidget(self._plot)
        self._path = self._plot.plot(symbol="o", symbolSize=4, symbolPen=None)
        self._endpoints = self._plot.plot(pen=None, symbolSize=12, symbolBrush=None)
        self._region = pg.RectROI((0, 0), (1, 1))
        self._region.setZValue(1)
        self._plot.addItem(self._region)
        self._region.hide()
        self._region.sigRegionChangeStarted.connect(self._begin_drag)
        self._region.sigRegionChangeFinished.connect(self._finish_drag)
        menus = [self._plot.getPlotItem().ctrlMenu]
        menus.extend(handle.menu for handle in self._region.getHandles())
        for menu in menus:
            menu.setParent(self, menu.windowFlags())
        self.apply_palette()

    def apply_palette(self) -> None:
        """Refresh the plot and endpoint colors from the current theme."""
        palette = self.palette()
        self._plot.setBackground(palette.base().color())
        for axis in ("bottom", "left"):
            self._plot.getAxis(axis).setTextPen(palette.text().color())
        accent = palette.highlight().color()
        self._path.setPen(accent)
        self._path.setSymbolBrush(accent)
        self._region.setPen(palette.text().color(), style=Qt.DashLine)
        if self._active:
            self.request_update()

    def set_active(self, active: bool) -> None:
        """Show or hide the preview and invalidate pending work."""
        self._active = active
        self._drag_revision = None
        self.setVisible(active)
        if active:
            self._fit = True
        self.request_update()

    def cleanup(self) -> None:
        """Stop pending previews and dispose of PyQtGraph's detached menus."""
        self.set_active(False)
        self._read_form = None
        item = self._plot.getPlotItem()
        item.ctrlMenu.deleteLater()
        for handle in self._region.getHandles():
            handle.menu.deleteLater()
        self._plot.close()
        self._plot.deleteLater()

    def request_update(self) -> None:
        """Schedule a preview of the latest form values."""
        self._revision += 1
        self._timer.stop()
        if self._active:
            self._status.setText("Updating path…")
            self._clear_path()
            if self._drag_revision is None:
                self._region.setEnabled(False)
            self._timer.start()

    @SafeSlot()
    def _refresh(self) -> None:
        if not self._active or self._worker is not None or self._drag_revision is not None:
            return
        try:
            inputs = self._read_form()
        except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
            self._clear(str(exc))
            return
        if self._inputs is None or self._inputs.motors != inputs.motors:
            self._fit = True
        self._inputs = inputs
        self._update_region(inputs)
        worker = Worker(_generate)
        worker.args = (worker.signals.progress, inputs, self._revision)
        worker.signals.progress.connect(self._show_result)
        worker.signals.completed.connect(self._worker_finished)
        worker.signals.failed.connect(self._worker_failed)
        self._worker = worker
        self._started_revision = self._revision
        QThreadPool.globalInstance().start(worker)

    def _update_region(self, inputs: PathInputs) -> None:
        x0, x1, y0, y1 = inputs.bounds
        self._region.setPos((min(x0, x1), min(y0, y1)), update=False)
        self._region.setSize((abs(x1 - x0), abs(y1 - y0)), finish=False, update=False)
        self._region.stateChanged(finish=False)
        self._region.setVisible(x0 != x1 and y0 != y1)
        self._region.setEnabled(True)
        relative = bool(inputs.parameters.get("relative"))
        for axis, motor in zip(("bottom", "left"), inputs.motors):
            self._plot.setLabel(axis, f"{motor} offset" if relative else motor)

    @SafeSlot(dict)
    def _show_result(self, result: dict) -> None:
        if (
            result["revision"] != self._revision
            or not self._active
            or self._drag_revision is not None
        ):
            return
        if "error" in result:
            self._clear_path()
            self._status.setText(result["error"])
            return
        points = result["points"]
        sampled = result["count"] > len(points)
        # Connecting decimated points can draw moves that the motors never make.
        connect = np.zeros(len(points), dtype=bool) if sampled else "all"
        self._path.setData(*points.T, connect=connect)
        colors = get_accent_colors()
        start_color, stop_color = colors.success, colors.emergency
        self._endpoints.setData(
            *points[[0, -1]].T,
            symbol=["t", "s"],
            symbolPen=[pg.mkPen(start_color, width=2), pg.mkPen(stop_color, width=2)],
        )
        params = self._inputs.parameters
        count = result["count"]
        exposure = (
            count
            * params.get("exp_time", 0)
            * params.get("frames_per_trigger", 1)
            * params.get("burst_at_each_point", 1)
        )
        legend = (
            f'<span style="color:{start_color.name()}">△ Start</span> '
            f'<span style="color:{stop_color.name()}">□ Stop</span>'
        )
        details = [f"{count:,} points", f"{exposure:.2f} s exposure only", legend]
        if method := self._inputs.optimization:
            details.append(f"Trajectory: {method}")
            if params.get("relative") and method in ("shell", "nearest"):
                details.append("Preview order uses offsets. Run order depends on motor positions.")
        if sampled:
            details.append("Sampled points · path line hidden")
        self._status.setText(" · ".join(details))
        x_range, y_range = self._plot.viewRange()
        x0, x1, y0, y1 = self._inputs.bounds
        if self._fit or not (
            x_range[0] <= min(x0, x1) <= max(x0, x1) <= x_range[1]
            and y_range[0] <= min(y0, y1) <= max(y0, y1) <= y_range[1]
        ):
            self._plot.autoRange()
            self._fit = False

    @SafeSlot()
    def _worker_finished(self) -> None:
        self._worker = None
        if self._active and self._started_revision != self._revision and not self._timer.isActive():
            self._timer.start()

    @SafeSlot(str)
    def _worker_failed(self, _traceback: str) -> None:
        if self._active and self._started_revision == self._revision:
            self._clear("Could not generate the path preview.")
        self._worker_finished()

    def _clear_path(self) -> None:
        self._path.clear()
        self._endpoints.clear()

    def _clear(self, message: str) -> None:
        self._inputs = None
        self._clear_path()
        self._region.hide()
        self._status.setText(message)

    @SafeSlot(object)
    def _begin_drag(self, _region) -> None:
        if self._region.isEnabled():
            self._drag_revision = self._started_revision

    @SafeSlot(object)
    def _finish_drag(self, _region) -> None:
        revision, self._drag_revision = self._drag_revision, None
        if revision is None:
            return
        if revision == self._revision and self._inputs is not None:
            x, y = self._region.pos()
            width, height = self._region.size()
            x0, x1, y0, y1 = self._inputs.bounds
            xs = (x, x + width) if x0 <= x1 else (x + width, x)
            ys = (y, y + height) if y0 <= y1 else (y + height, y)
            self.bounds_changed.emit(self._inputs, (*xs, *ys))
        self.request_update()
