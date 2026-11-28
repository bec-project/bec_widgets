"""Maps of scans that moved two motors: a signal as colour over the two motor positions."""

from __future__ import annotations

import numpy as np
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import QObject, Qt, Signal
from qtpy.QtWidgets import QButtonGroup, QHBoxLayout, QStackedWidget, QToolButton, QWidget

from bec_widgets.widgets.services.hdf5_viewer.scan_list import ScanEntry

logger = bec_logger.logger

SourceKey = tuple[str, str]

#: The views of a scan that moved two motors: key, label, icon, tooltip.
VIEWS = (
    ("heatmap", "Heatmap", "grid_on", "The signal as colour on a grid of the two motors"),
    ("scatter", "Scatter", "scatter_plot", "The signal as the colour of each scan point"),
    ("lines", "Lines", "show_chart", "The signals as lines against the first motor"),
)

#: Scans whose points lie on a regular grid of the two motors.
GRID_SCANS = frozenset({"grid_scan"})

#: Scans whose points cover an area of their first two motors: they open as a map. Every
#: other scan of two motors (line_scan, a scan of a beamline plugin, ...) opens as lines
#: against its first motor and can be switched to a map.
AREA_SCANS = frozenset(
    {
        "grid_scan",
        "fermat_scan",
        "round_scan",
        "round_roi_scan",
        "hexagonal_scan",
        "multi_region_grid_scan",
    }
)


#: Thinnest a scan's cloud of points may be across its length, as a share of that length,
#: before the points count as lying on one line (each motor scaled by its own range first).
ONE_LINE_RATIO = 0.02
#: Why a scan whose points lie on one line has no heatmap.
ONE_LINE_REASON = "the scan's points lie on one line"


def is_two_dimensional(entry: ScanEntry | None) -> bool:
    """
    Whether a scan moved two motors or more, so that its signals can be drawn as a map over
    the first two of them.

    Args:
        entry (ScanEntry | None): The scan.

    Returns:
        bool: True for a scan that moved two motors or more.
    """
    return entry is not None and len(entry.motors) >= 2


def is_area_scan(entry: ScanEntry | None) -> bool:
    """
    Whether a scan covers an area of its motors by its kind (grid, fermat, round, ...), so
    that it opens as a map. The history tells the scan and its motors, not the path.

    Args:
        entry (ScanEntry | None): The scan.

    Returns:
        bool: True for a scan named in :data:`AREA_SCANS`.
    """
    return entry is not None and entry.scan_name in AREA_SCANS


def points_on_one_line(x, y) -> bool:
    """
    Whether the points of a scan lie on one line, so that a heatmap of them has nothing to
    fill: each motor is scaled by its own range, then the spread of the points across their
    main direction is compared with the spread along it (:data:`ONE_LINE_RATIO`). A motor
    that did not move puts the points on one line as well.

    Args:
        x: Positions of the first motor.
        y: Positions of the second motor, as many.

    Returns:
        bool: True for points on one line, or for fewer than three points.
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    if x.size < 3:
        return True
    spans = (np.ptp(x), np.ptp(y))
    if min(spans) <= 0:
        return True
    points = np.column_stack(((x - x.min()) / spans[0], (y - y.min()) / spans[1]))
    points -= points.mean(axis=0)
    along, across = np.linalg.svd(points, compute_uv=False)[:2]
    return bool(across <= ONE_LINE_RATIO * along)


def map_axes(entry: ScanEntry | None) -> tuple[SourceKey, SourceKey] | None:
    """
    The two motors of an area scan as (device, entry) of their readbacks, when it stored
    both.

    Args:
        entry (ScanEntry | None): The scan.

    Returns:
        tuple[SourceKey, SourceKey] | None: x and y, or None when the scan is no map.
    """
    if not is_two_dimensional(entry):
        return None
    stored = entry.stored_data_info or {}
    axes = []
    for motor in entry.motors[:2]:
        if motor not in stored.get(motor, {}):
            return None
        axes.append((motor, motor))
    return axes[0], axes[1]


def default_view(entry: ScanEntry | None) -> str:
    """
    How a scan is shown at first: a heatmap for a regular grid, a scatter for other area
    scans (e.g. fermat), lines for everything else, other scans of two motors included.

    Args:
        entry (ScanEntry | None): The scan.

    Returns:
        str: ``heatmap``, ``scatter`` or ``lines``.
    """
    if map_axes(entry) is None or not is_area_scan(entry):
        return "lines"
    return "heatmap" if entry.scan_name in GRID_SCANS else "scatter"


class ViewSwitch(QWidget):
    """Three buttons in a row to switch between Heatmap, Scatter and Lines."""

    #: A view was chosen by the user: its key.
    chosen = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QToolButton] = {}
        for key, label, icon, tip in VIEWS:
            button = QToolButton(self)
            button.setObjectName(f"view_{key}_button")
            button.setText(label)
            button.setIcon(material_icon(icon, convert_to_pixmap=False))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.clicked.connect(lambda _checked=False, key=key: self.chosen.emit(key))
            self.group.addButton(button)
            self.buttons[key] = button
            layout.addWidget(button)

    def set_current(self, key: str) -> None:
        """
        Show which view is on, without announcing it.

        Args:
            key (str): ``heatmap``, ``scatter`` or ``lines``.
        """
        button = self.buttons.get(key)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def set_off(self, reasons: dict[str, str]) -> None:
        """
        Turn views off that the scan cannot be shown as, each with the reason in its tooltip.

        Args:
            reasons (dict[str, str]): Key of a view and why it is off; an empty reason, or a
                view not named, is on.
        """
        for key, label, _icon, tip in VIEWS:
            reason = reasons.get(key, "")
            button = self.buttons[key]
            button.setEnabled(not reason)
            button.setToolTip(f"No {label.lower()}: {reason}" if reason else tip)
            # A button that is off says why to screen readers too, in the same words.
            button.setAccessibleDescription(button.toolTip() if reason else "")

    def current(self) -> str:
        """
        The view that is on.

        Returns:
            str: Its key, or empty when none is.
        """
        for key, button in self.buttons.items():
            if button.isChecked():
                return key
        return ""


class MapPlots(QObject):
    """
    The Heatmap and the ScatterWaveform of the viewer, made when first needed and kept on one
    scan of the history, so that a scan starting meanwhile does not take them over.

    A map of a finished scan is ready once its data is drawn; until then the viewer shows a
    loading state instead of an empty plot or the map of the scan before.
    """

    #: The map of a view is drawn with the data of the scan it shows: the view's key.
    ready = Signal(str)

    def __init__(self, stack: QStackedWidget, client=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._stack = stack
        self._client = client
        self._owner = parent
        self.heatmap = None
        self.scatter = None
        self._shown: dict[str, tuple] = {}
        self._ready: dict[str, bool] = {}
        #: Whether the last :meth:`show` only changed the signal of a map drawn already.
        self.recoloured = False

    def widget(self, view: str) -> QWidget:
        """
        The plot of a view, made on first use.

        Args:
            view (str): ``heatmap`` or ``scatter``.

        Returns:
            QWidget: The Heatmap or the ScatterWaveform.
        """
        # pylint: disable=import-outside-toplevel
        if view == "heatmap":
            if self.heatmap is None:
                from bec_widgets.widgets.plots.heatmap.heatmap import Heatmap

                self.heatmap = Heatmap(parent=self._owner, client=self._client)
                self.heatmap.setObjectName("map_heatmap")
                self.heatmap.image_updated.connect(self._on_heatmap_image)
                self._stack.addWidget(self.heatmap)
            return self.heatmap
        if self.scatter is None:
            from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform

            self.scatter = ScatterWaveform(parent=self._owner, client=self._client)
            self.scatter.setObjectName("map_scatter")
            self._stack.addWidget(self.scatter)
        return self.scatter

    def is_ready(self, view: str) -> bool:
        """
        Whether the map of a view shows the data it was last asked for.

        Args:
            view (str): ``heatmap`` or ``scatter``.

        Returns:
            bool: True once the data is drawn, or at once for a running scan.
        """
        return self._ready.get(view, False)

    def show(
        self, view: str, entry: ScanEntry, axes: tuple[SourceKey, SourceKey], z: SourceKey
    ) -> QWidget:
        """
        Draw a signal of a scan as a map, unless that map is drawn already.

        Args:
            view (str): ``heatmap`` or ``scatter``.
            entry (ScanEntry): The scan.
            axes (tuple[SourceKey, SourceKey]): (device, entry) of the x and the y motor.
            z (SourceKey): (device, entry) of the signal drawn as colour.

        Returns:
            QWidget: The plot that shows it.
        """
        x, y = axes
        plot = self.widget(view)
        state = (entry.scan_id, entry.live, x, y, z)
        before = self._shown.get(view)
        self.recoloured = False
        if before == state:
            return plot
        self.recoloured = (
            before is not None and before[:4] == state[:4] and self._ready.get(view, False)
        )
        self._shown[view] = state
        # A running scan grows in place; a finished one waits for its data.
        self._ready[view] = entry.live
        scan_id = None if entry.live else entry.scan_id
        names = {
            "device_x": x[0],
            "signal_x": x[1],
            "device_y": y[0],
            "signal_y": y[1],
            "device_z": z[0],
            "signal_z": z[1],
            "validate_bec": False,
        }
        if view == "heatmap":
            self.heatmap.plot(**names, show_config_label=False, scan_id=scan_id)
            return plot
        label = z[0] if z[0] == z[1] else f"{z[0]}.{z[1]}"
        curve = self.scatter.plot(**names, label=label, scan_id=scan_id)
        # The scan path between the points hides them where they are dense (fermat).
        if curve is not None:
            curve.setPen(None)
            curve.sigPlotChanged.connect(self._on_scatter_data)
        # One curve, named in the signal list; its legend would only cover points.
        if plot.plot_item.legend is not None:
            plot.plot_item.legend.setVisible(False)
        return plot

    def _set_ready(self, view: str) -> None:
        if not self._ready.get(view, False):
            self._ready[view] = True
            self.ready.emit(view)

    def _on_heatmap_image(self) -> None:
        state = self._shown.get("heatmap")
        heatmap = self.heatmap
        if state is None or heatmap is None or heatmap.main_image.raw_data is None:
            return
        if state[1] or heatmap.scan_id == state[0]:
            self._set_ready("heatmap")

    def _on_scatter_data(self, curve) -> None:
        if self.scatter is None or curve is not self.scatter.main_curve:
            return
        if curve.xData is not None and len(curve.xData) > 0:
            self._set_ready("scatter")

    def forget(self) -> None:
        """Draw the next map anew, e.g. after the theme changed."""
        self._shown.clear()
        self._ready.clear()
