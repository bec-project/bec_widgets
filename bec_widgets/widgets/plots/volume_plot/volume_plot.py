"""
VolumePlot: a 3D view of volume data with cuts, for example a 3D grid scan.

Left: the volume in 3D (pyqtgraph.opengl) with the current cut, pinned cuts and
projections on the far walls. Right: the current cut as a regular BEC image plot (colour
bar, crosshair, ROIs, export). Below: the cut axis and a slider, and the pinned cuts.

Three ways to cut:
- move the slider (or press the arrow keys on it) along the chosen axis;
- "Click to cut": click the volume, the cut jumps to the brightest point under the
  pointer; Shift+click also pins it;
- "Cut follows pointer": the cut follows the pointer over the volume; a click pins it.

"Cut away" hides the part of the volume in front of the cut, so moving the slider peels
the volume layer by layer.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from bec_lib.data_api import ScanTarget
from bec_lib.endpoints import MessageEndpoints
from pydantic import Field, field_validator
from qtpy.QtCore import QPointF, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QImage, QKeySequence, QPixmap, QShortcut, QTransform
from qtpy.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.colors import Colors, get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.qt_data_subscription import QtDataSubscription
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.widgets.plots.heatmap.heatmap import HeatmapDeviceSignal
from bec_widgets.widgets.plots.image.image_base import ImageBase
from bec_widgets.widgets.plots.image.image_item import ImageItem
from bec_widgets.widgets.plots.plot_base import PlotBase, expand_sample_columns
from bec_widgets.widgets.plots.volume_plot.gl_volume_view import (
    VolumeGLView,
    plane_rgba,
    volume_rgba,
)
from bec_widgets.widgets.plots.volume_plot.volume_data import (
    AXIS_NAMES,
    VolumeData,
    grid_from_points,
)

logger = bec_logger.logger

MouseMode = Literal["click", "follow"]


class VolumePlotConfig(ConnectionConfig):
    """Configuration of the VolumePlot widget."""

    color_map: str | None = Field("plasma", description="Colour map of volume and cut.")
    color_bar: Literal["full", "simple"] | None = Field(None, description="Colour bar type.")
    lock_aspect_ratio: bool = Field(False, description="Lock the aspect ratio of the cut.")
    device_x: HeatmapDeviceSignal | None = Field(None, description="Device of the first axis.")
    device_y: HeatmapDeviceSignal | None = Field(None, description="Device of the second axis.")
    device_z: HeatmapDeviceSignal | None = Field(None, description="Device of the third axis.")
    device_value: HeatmapDeviceSignal | None = Field(None, description="Device of the value.")
    cut_axis: int = Field(2, description="Axis the cut is perpendicular to (0, 1, 2).")
    mouse_mode: MouseMode = Field("click", description="What the pointer does in 3D.")
    clip_volume: bool = Field(False, description="Hide the volume in front of the cut.")
    show_projections: bool = Field(True, description="Projections on the far walls.")
    opacity: float = Field(0.5, ge=0.0, le=1.0, description="Opacity of the volume.")

    model_config: dict = {"validate_assignment": True}
    _validate_color_palette = field_validator("color_map")(Colors.validate_color_map)


class _CutThumb(QToolButton):
    """One pinned cut in the strip: a small picture with its label."""

    remove_requested = Signal(object)

    def __init__(self, key: tuple, text: str, tooltip: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("volume_cut_thumb")
        self.setText(text)
        self.setToolTip(tooltip)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setAutoRaise(True)
        self.setCheckable(True)
        self.setIconSize(QSize(88, 64))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def _menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Remove cut", lambda: self.remove_requested.emit(self.key))
        menu.exec(self.mapToGlobal(pos))


class VolumePlot(ImageBase):
    """
    3D view of volume data with cuts along x, y or z, for example of a 3D grid scan.
    """

    #: Volume rendering is costly; points of a 3D scan arrive slowly anyway.
    DEFAULT_UPDATE_RATE = 5.0
    #: Coalesce cut updates from a fast pointer to about 40 per second.
    CUT_INTERVAL_MS = 25

    PLUGIN = True
    RPC = True
    ICON_NAME = "view_in_ar"
    USER_ACCESS = [
        *PlotBase.USER_ACCESS,
        "color_map",
        "color_map.setter",
        "v_range",
        "v_range.setter",
        "autorange",
        "autorange.setter",
        "enable_simple_colorbar",
        "enable_simple_colorbar.setter",
        "enable_full_colorbar",
        "enable_full_colorbar.setter",
        "main_image",
        "plot",
        "set_volume",
        "load_demo",
        "cut_axis",
        "cut_axis.setter",
        "cut_index",
        "cut_index.setter",
        "cut_coordinate",
        "mouse_mode",
        "mouse_mode.setter",
        "clip_volume",
        "clip_volume.setter",
        "show_projections",
        "show_projections.setter",
        "opacity",
        "opacity.setter",
        "pin_cut",
        "clear_pinned_cuts",
        "pinned_cuts",
        "reset_camera",
    ]

    cut_changed = Signal(int, int, float)
    volume_changed = Signal()

    def __init__(self, parent=None, config: VolumePlotConfig | None = None, **kwargs):
        if config is None:
            config = VolumePlotConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, config=config, **kwargs)
        self._volume_config = config
        self.volume: VolumeData | None = None
        self._cut_index = 0
        self._pinned: list[tuple[int, int, str]] = []
        self._normalized: np.ndarray | None = None
        self._lut = self._make_lut(self.config.color_map)
        self._volume_rgba: np.ndarray | None = None
        self._data_bridge: QtDataSubscription | None = None
        self._planned_positions: np.ndarray | None = None
        self._data_bridge_scope: str | None = None
        #: While True the cut follows the newest data of a running scan; any cut the user
        #: makes (slider, click, axis, pinned cut) ends it until the next scan.
        self._follow_live = False
        self.scan_id: str | None = None
        self._cut_timer = QTimer(self)
        self._cut_timer.setSingleShot(True)
        self._cut_timer.setInterval(self.CUT_INTERVAL_MS)
        self._cut_timer.timeout.connect(self._apply_cut)

        self._build_layout()
        self._empty_hint = pg.TextItem("No data in this cut yet", anchor=(0.5, 0.5))
        self._empty_hint.setZValue(50)
        self._empty_hint.hide()
        self.plot_item.addItem(self._empty_hint, ignoreBounds=True)
        self.plot_item.vb.sigRangeChanged.connect(lambda *_: self._place_empty_hint())
        self._init_volume_toolbar()
        self._init_shortcuts()
        self.toolbar.show_bundles(
            [
                "volume_cut",
                "volume_display",
                "plot_export",
                "image_crosshair",
                "image_autorange",
                "image_colorbar",
                "image_processing",
            ]
        )
        processing = self.toolbar.get_bundle("image_processing")
        for name, action in processing.bundle_actions.items():
            if name != "image_processing_log":
                action().action.setVisible(False)
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.autorange_mode = "max"
        # Coordinates carry their own units (µm, mm, motor units); no extra SI scaling.
        for side in ("bottom", "left"):
            self.plot_item.getAxis(side).enableAutoSIPrefix(False)
        self._splitter_sized = False
        self._sync_controls()
        self._update_theme(None)
        if self._config_sources() is not None:
            self._setup_data_api_subscription()

    # ------------------------------------------------------------------ layout
    def _build_layout(self):
        frame_layout = self.round_plot_widget.layout()
        frame_layout.removeWidget(self.plot_widget)

        area = QWidget(self.round_plot_widget)
        area.setObjectName("volume_area")
        area_layout = QVBoxLayout(area)
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(4)

        self.gl_view = VolumeGLView(area)
        self.gl_view.hovered.connect(self._on_gl_hover)
        self.gl_view.clicked.connect(self._on_gl_click)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, area)
        self.splitter.setObjectName("volume_splitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.gl_view)
        self.splitter.addWidget(self.plot_widget)
        self.splitter.setStretchFactor(0, 11)
        self.splitter.setStretchFactor(1, 9)
        area_layout.addWidget(self.splitter, 1)

        area_layout.addWidget(self._build_cut_bar(area))
        area_layout.addWidget(self._build_cut_strip(area))
        frame_layout.addWidget(area)

    def _build_cut_bar(self, parent: QWidget) -> QWidget:
        bar = QWidget(parent)
        bar.setObjectName("volume_cut_bar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)
        title = QLabel("Cut along", bar)
        title.setProperty("variant", "muted")
        layout.addWidget(title)
        self.axis_buttons = QButtonGroup(bar)
        self.axis_buttons.setExclusive(True)
        for axis in range(3):
            button = QToolButton(bar)
            button.setObjectName(f"volume_axis_{AXIS_NAMES[axis]}")
            button.setCheckable(True)
            button.setText(AXIS_NAMES[axis])
            button.setToolTip(
                f"Cut perpendicular to {AXIS_NAMES[axis]} (key {AXIS_NAMES[axis].upper()})"
            )
            self.axis_buttons.addButton(button, axis)
            layout.addWidget(button)
        self.axis_buttons.idClicked.connect(self._on_axis_clicked)

        self.cut_slider = QSlider(Qt.Orientation.Horizontal, bar)
        self.cut_slider.setObjectName("volume_cut_slider")
        self.cut_slider.setToolTip(
            "Move the cut. Arrow keys step one voxel, Page Up and Page Down step ten."
        )
        self.cut_slider.setPageStep(10)
        self.cut_slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self.cut_slider, 1)

        self.cut_label = QLabel(bar)
        self.cut_label.setObjectName("volume_cut_label")
        self.cut_label.setMinimumWidth(150)
        self.cut_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.cut_label)
        self.cut_index_label = QLabel(bar)
        self.cut_index_label.setObjectName("volume_cut_index")
        self.cut_index_label.setProperty("variant", "muted")
        self.cut_index_label.setMinimumWidth(64)
        layout.addWidget(self.cut_index_label)
        return bar

    def _on_axis_clicked(self, axis: int):
        self._stop_following()
        self.cut_axis = axis

    def _build_cut_strip(self, parent: QWidget) -> QWidget:
        strip = QWidget(parent)
        strip.setObjectName("volume_cut_strip")
        layout = QVBoxLayout(strip)
        layout.setContentsMargins(6, 0, 6, 2)
        layout.setSpacing(0)
        self.pins_hint = QLabel(
            "Pinned cuts appear here. Press P, or Shift+click the volume, to pin a cut.", strip
        )
        self.pins_hint.setObjectName("volume_pins_hint")
        self.pins_hint.setProperty("variant", "muted")
        layout.addWidget(self.pins_hint)
        self.pins_scroll = QScrollArea(strip)
        self.pins_scroll.setObjectName("volume_pins_scroll")
        self.pins_scroll.setWidgetResizable(True)
        self.pins_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.pins_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pins_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pins_scroll.setFixedHeight(118)
        holder = QWidget(self.pins_scroll)
        self.pins_layout = QHBoxLayout(holder)
        self.pins_layout.setContentsMargins(0, 0, 0, 0)
        self.pins_layout.setSpacing(4)
        self.pins_layout.addStretch(1)
        self.pins_scroll.setWidget(holder)
        layout.addWidget(self.pins_scroll)
        self.pins_scroll.hide()
        self._thumbs: list[_CutThumb] = []
        return strip

    def _init_volume_toolbar(self):
        components = self.toolbar.components
        bundle = self.toolbar.new_bundle("volume_cut")
        actions = {
            "volume_mode_click": MaterialIconAction(
                icon_name="ads_click",
                tooltip="Click to cut: click the volume to move the cut there, "
                "Shift+click also pins it",
                checkable=True,
                parent=self,
            ),
            "volume_mode_follow": MaterialIconAction(
                icon_name="pan_tool_alt",
                tooltip="Cut follows pointer: the cut follows the pointer over the volume, "
                "a click pins it",
                checkable=True,
                parent=self,
            ),
            "volume_pin": MaterialIconAction(
                icon_name="push_pin", tooltip="Pin the current cut (P)", parent=self
            ),
            "volume_clip": MaterialIconAction(
                icon_name="content_cut",
                tooltip="Cut away the volume in front of the cut (C)",
                checkable=True,
                parent=self,
            ),
        }
        for name, action in actions.items():
            components.add_safe(name, action)
            bundle.add_action(name)
        components.get_action("volume_mode_click").action.triggered.connect(
            lambda: setattr(self, "mouse_mode", "click")
        )
        components.get_action("volume_mode_follow").action.triggered.connect(
            lambda: setattr(self, "mouse_mode", "follow")
        )
        components.get_action("volume_pin").action.triggered.connect(lambda: self.pin_cut())
        components.get_action("volume_clip").action.toggled.connect(
            lambda checked: setattr(self, "clip_volume", checked)
        )

        display = self.toolbar.new_bundle("volume_display")
        display_actions = {
            "volume_projections": MaterialIconAction(
                icon_name="flip_to_back",
                tooltip="Projections on the walls",
                checkable=True,
                parent=self,
            ),
            "volume_reset_camera": MaterialIconAction(
                icon_name="3d_rotation", tooltip="Reset the 3D view (R)", parent=self
            ),
        }
        for name, action in display_actions.items():
            components.add_safe(name, action)
            display.add_action(name)
        components.get_action("volume_projections").action.toggled.connect(
            lambda checked: setattr(self, "show_projections", checked)
        )
        components.get_action("volume_reset_camera").action.triggered.connect(self.reset_camera)

    def _init_shortcuts(self):
        def shortcut(key: str, slot):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)

        shortcut("P", lambda: self.pin_cut())
        shortcut("C", lambda: setattr(self, "clip_volume", not self.clip_volume))
        shortcut("R", self.reset_camera)
        for axis, name in enumerate(AXIS_NAMES):
            shortcut(name.upper(), lambda a=axis: self._on_axis_clicked(a))

    def _sync_controls(self):
        """Bring toolbar and cut bar in line with the configuration."""
        components = self.toolbar.components
        mode = self.config.mouse_mode
        for name, value in (("volume_mode_click", "click"), ("volume_mode_follow", "follow")):
            action = components.get_action(name).action
            action.blockSignals(True)
            action.setChecked(mode == value)
            action.blockSignals(False)
        for name, value in (
            ("volume_clip", self.config.clip_volume),
            ("volume_projections", self.config.show_projections),
        ):
            action = components.get_action(name).action
            action.blockSignals(True)
            action.setChecked(value)
            action.blockSignals(False)
        button = self.axis_buttons.button(self.config.cut_axis)
        if button is not None:
            button.setChecked(True)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._splitter_sized:
            # QSplitter splits by size hints at first; give the 3D view the larger share
            # once the widget has its real size.
            self._splitter_sized = True
            QTimer.singleShot(0, self._size_splitter)

    def _size_splitter(self):
        total = max(self.splitter.width(), 2)
        self.splitter.setSizes([int(total * 0.56), total - int(total * 0.56)])

    # ------------------------------------------------------------------ theme
    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        if not hasattr(self, "gl_view"):
            return
        dark = theme != "light"
        palette = self.palette()
        background = QColor("#0b0b0f") if dark else palette.window().color()
        self.gl_view.set_dark(dark, background)
        self.gl_view.set_box_color(QColor(255, 255, 255, 70) if dark else QColor(0, 0, 0, 90))
        self._refresh_scene_decor()

    def _accent(self) -> QColor:
        return QColor(get_accent_colors().highlight)

    def _text_color(self) -> QColor:
        return self.palette().windowText().color()

    # ------------------------------------------------------------------ data in
    @SafeSlot(popup_error=True)
    def set_volume(
        self,
        values: np.ndarray,
        x: np.ndarray | None = None,
        y: np.ndarray | None = None,
        z: np.ndarray | None = None,
        labels: tuple[str, str, str] | None = None,
        units: tuple[str, str, str] | None = None,
        value_label: str = "value",
    ) -> None:
        """
        Show a 3D array.

        Args:
            values (np.ndarray): Array of shape (nx, ny, nz); NaN marks voxels without data.
            x (np.ndarray | None): Voxel centre coordinates of the first axis.
            y (np.ndarray | None): Voxel centre coordinates of the second axis.
            z (np.ndarray | None): Voxel centre coordinates of the third axis.
            labels (tuple[str, str, str] | None): Axis names.
            units (tuple[str, str, str] | None): Axis units.
            value_label (str): Name of the values.
        """
        self._stop_data_feed()
        volume = VolumeData.from_array(
            np.asarray(values),
            x=x,
            y=y,
            z=z,
            labels=tuple(labels) if labels else AXIS_NAMES,
            units=tuple(units) if units else ("", "", ""),
            value_label=value_label,
        )
        self.show_volume(volume)

    def show_volume(self, volume: VolumeData, keep_view: bool = False) -> None:
        """
        Show a VolumeData, with its marks as pinned cuts.

        Args:
            volume (VolumeData): The volume.
            keep_view (bool): Keep camera, cut and pinned cuts (live updates of one scan).
        """
        same_shape = self.volume is not None and self.volume.shape == volume.shape
        self.volume = volume
        self._normalized = volume.normalized()
        self._volume_rgba = volume_rgba(self._normalized, self._lut, self.config.opacity)
        if keep_view and same_shape:
            self.gl_view.update_volume_rgba(self._volume_rgba)
        else:
            self.gl_view.set_volume(volume, self._volume_rgba, reset_camera=True)
            self._pinned = [
                (m.axis, volume.index_of(m.axis, m.coordinate), m.label) for m in volume.marks
            ]
            if volume.marks:
                self.config.cut_axis = volume.marks[0].axis
            self._cut_index = volume.shape[self.config.cut_axis] // 2
        for axis, button in enumerate(self.axis_buttons.buttons()):
            name = volume.labels[axis]
            unit = f" ({volume.units[axis]})" if volume.units[axis] else ""
            button.setText(name)
            button.setToolTip(f"Cut perpendicular to {name}{unit} (key {AXIS_NAMES[axis].upper()})")
        self._sync_controls()
        self._configure_slider()
        self._refresh_scene_decor()
        self._apply_cut()
        self._rebuild_thumbs()
        self.volume_changed.emit()

    @SafeSlot(popup_error=True)
    def load_demo(self, astigmatism: float = 1.0, central_stop: float = 0.25) -> None:
        """
        Show the simulated astigmatic beam (soft X-ray zone plate, about 1.24 keV).

        Args:
            astigmatism (float): Astigmatism in waves; it sets the distance of the foci.
            central_stop (float): Central stop radius as a fraction of the aperture.
        """
        from bec_widgets.widgets.plots.volume_plot.beam_simulation import simulate_astigmatic_beam

        self._stop_data_feed()
        self.show_volume(
            simulate_astigmatic_beam(astigmatism=astigmatism, central_stop=central_stop)
        )

    # ------------------------------------------------------------------ BEC data
    @SafeSlot(popup_error=True)
    def plot(
        self,
        device_x: str,
        device_y: str,
        device_z: str,
        device_value: str,
        signal_x: str | None = None,
        signal_y: str | None = None,
        signal_z: str | None = None,
        signal_value: str | None = None,
        scan_id: str | None = None,
    ) -> None:
        """
        Plot a monitored signal against three positioners, live or from a finished scan.

        A 3D grid scan fills its whole grid from the start; other scans are gridded from
        the measured positions.

        Args:
            device_x (str): Positioner of the first axis.
            device_y (str): Positioner of the second axis.
            device_z (str): Positioner of the third axis.
            device_value (str): Device whose signal is shown.
            signal_x (str | None): Entry of device_x; the device's hinted signal by default.
            signal_y (str | None): Entry of device_y.
            signal_z (str | None): Entry of device_z.
            signal_value (str | None): Entry of device_value.
            scan_id (str | None): A finished scan; the running or next scan when None.
        """
        signals = []
        for device, signal in (
            (device_x, signal_x),
            (device_y, signal_y),
            (device_z, signal_z),
            (device_value, signal_value),
        ):
            entry = self.entry_validator.validate_signal(device, signal)
            signals.append(HeatmapDeviceSignal(device=device, signal=entry))
        (
            self.config.device_x,
            self.config.device_y,
            self.config.device_z,
            self.config.device_value,
        ) = signals
        self.volume = None
        self._planned_positions = None
        self._setup_data_api_subscription(scan=scan_id or ScanTarget.LIVE)

    def _config_sources(self) -> list[tuple[str, str]] | None:
        devices = (
            self.config.device_x,
            self.config.device_y,
            self.config.device_z,
            self.config.device_value,
        )
        if any(d is None for d in devices):
            return None
        return [(d.device, d.signal) for d in devices]

    def _setup_data_api_subscription(self, scan: str = ScanTarget.LIVE):
        self._stop_data_feed()
        sources = self._config_sources()
        if sources is None:
            return
        try:
            self._data_bridge = QtDataSubscription(
                self.client,
                sources=list(dict.fromkeys(sources)),
                scan=scan,
                parent=self,
                min_emit_interval=self.update_interval_s,
            )
            self._data_bridge.updated.connect(self._on_data_update)
            self._data_bridge_scope = scan
        except Exception as exc:
            logger.warning(f"VolumePlot could not subscribe to its data: {exc}")
            self._stop_data_feed()
            return
        self._warn_if_unaligned(list(dict.fromkeys(sources)), scan)

    def _stop_data_feed(self):
        if self._data_bridge is None:
            return
        try:
            self._data_bridge.close()
        finally:
            self._data_bridge = None

    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, meta: dict):
        """Take the planned positions of a new scan, for grid scans."""
        if self._config_sources() is None:
            return
        scan_id = msg.get("scan_id")
        if scan_id is None or scan_id == self.scan_id:
            return
        self.scan_id = scan_id
        self._planned_positions = self._planned_from_status(msg)
        self.volume = None
        self._follow_live = True

    def _planned_from_status(self, msg: dict) -> np.ndarray | None:
        """Planned positions in (x, y, z) order of a grid scan over our three devices."""
        try:
            if msg.get("scan_name") != "grid_scan":
                return None
            bundle = msg["request_inputs"]["arg_bundle"]
            motors = list(bundle[0::4])
            positions = np.asarray(msg["info"]["positions"], dtype=float)
            columns = [
                motors.index(d.device)
                for d in (self.config.device_x, self.config.device_y, self.config.device_z)
            ]
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            return None
        if positions.ndim != 2 or positions.shape[1] < 3:
            return None
        return positions[:, columns]

    @SafeSlot(object)
    def _on_data_update(self, update) -> None:
        """Grid one aligned DataAPI update and show it."""
        sources = self._config_sources()
        if sources is None or self._data_bridge is None:
            return
        if self._alignment_binding_changed(update):
            self._warn_if_unaligned(list(dict.fromkeys(sources)), self._data_bridge_scope)
        columns = update.aligned()
        try:
            expanded = expand_sample_columns(*(columns[tuple(s)] for s in sources))
        except KeyError:
            return
        if expanded is None or not expanded[0]:
            return
        x, y, z, values = (np.asarray(c, dtype=float) for c in expanded)
        if update.scan_id != self.scan_id:
            self.scan_id = update.scan_id
            self._planned_positions = None
            self.volume = None
            self._follow_live = self._data_bridge_scope == ScanTarget.LIVE
        grid, axes = grid_from_points(x, y, z, values, planned=self._planned_positions)
        labels = tuple(
            d.device for d in (self.config.device_x, self.config.device_y, self.config.device_z)
        )
        volume = VolumeData(
            values=grid,
            axes=axes,
            labels=labels,
            units=tuple(self._device_unit(name) for name in labels),
            value_label=self.config.device_value.signal,
        )
        first = self.volume is None
        self.show_volume(volume, keep_view=not first)
        if self._follow_live:
            self._follow_newest(np.column_stack([x, y, z]), choose_axis=first)

    def _follow_newest(self, points: np.ndarray, choose_axis: bool):
        """
        Keep the cut on the layer that receives data, so a running scan is visible.

        Args:
            points (np.ndarray): Measured positions of shape (n, 3), newest last.
            choose_axis (bool): Also switch the cut to the slowest scan axis (first update).
        """
        volume = self.volume
        if volume is None or points.size == 0:
            return
        if choose_axis and len(points) > 1:
            changes = np.count_nonzero(np.abs(np.diff(points, axis=0)) > 0, axis=0)
            self.config.cut_axis = int(np.argmin(changes))
            self._sync_controls()
            self._refresh_scene_decor()
        axis = self.config.cut_axis
        self._cut_index = volume.index_of(axis, float(points[-1, axis]))
        self._configure_slider()
        self._apply_cut()

    def _stop_following(self):
        self._follow_live = False

    def _device_unit(self, device: str) -> str:
        try:
            device_obj = self.dev[device]
            return str(device_obj.egu()) if hasattr(device_obj, "egu") else ""
        except Exception:  # pylint: disable=broad-except
            return ""

    # ------------------------------------------------------------------ cuts
    def _configure_slider(self):
        if self.volume is None:
            self.cut_slider.setEnabled(False)
            return
        n = self.volume.shape[self.config.cut_axis]
        self._cut_index = int(np.clip(self._cut_index, 0, n - 1))
        self.cut_slider.blockSignals(True)
        self.cut_slider.setRange(0, n - 1)
        self.cut_slider.setValue(self._cut_index)
        self.cut_slider.setEnabled(n > 1)
        self.cut_slider.blockSignals(False)

    @SafeSlot(int)
    def _on_slider(self, value: int):
        self._stop_following()
        self._cut_index = int(value)
        self._schedule_cut()

    def _schedule_cut(self):
        if not self._cut_timer.isActive():
            self._cut_timer.start()

    @SafeSlot()
    def _apply_cut(self):
        """Show the current cut in 3D and in the 2D plot."""
        self._cut_timer.stop()
        volume = self.volume
        if volume is None:
            return
        axis, index = self.config.cut_axis, self._cut_index
        cut = volume.slice(axis, index)
        normalized = np.take(self._normalized, index, axis=axis)
        normalized = np.where(np.isfinite(cut), normalized, np.nan)
        self.gl_view.set_cut(axis, index, plane_rgba(normalized, self._lut), self._accent())
        self.gl_view.set_clip(axis if self.config.clip_volume else None, index)
        self._show_cut_image(cut, axis)
        coordinate = volume.coordinate(axis, index)
        unit = volume.units[axis]
        self.cut_label.setText(f"{volume.labels[axis]} = {coordinate:.4g} {unit}".rstrip())
        self.cut_index_label.setText(f"{index + 1} / {volume.shape[axis]}")
        if self.cut_slider.value() != index:
            self.cut_slider.blockSignals(True)
            self.cut_slider.setValue(index)
            self.cut_slider.blockSignals(False)
        for thumb in self._thumbs:
            thumb.setChecked(thumb.key[:2] == (axis, index))
        self.cut_changed.emit(axis, index, coordinate)

    def _show_cut_image(self, cut: np.ndarray, axis: int):
        """Put the cut into the image plot; a clearly longer display axis goes horizontal."""
        volume = self.volume
        p, q = VolumeData.plane_axes(axis)
        box = volume.display_box()
        image = cut
        if box[q] >= 1.5 * box[p]:
            # a clearly longer side (the beam axis of a caustic) reads better horizontally
            image, p, q = cut.T, q, p
        transform = QTransform()
        sp, sq = volume.spacing(p), volume.spacing(q)
        transform.translate(volume.extent(p)[0], volume.extent(q)[0])
        transform.scale(sp, sq)
        empty = not np.isfinite(image).any()
        self._empty_hint.setVisible(empty)
        if empty:
            # ImageItem skips all-NaN data and would keep showing the previous cut
            self.main_image.clear()
        else:
            self.main_image.set_data(np.ascontiguousarray(image), transform=transform)
        self._place_empty_hint()
        self.x_label = volume.labels[p]
        self.x_label_units = volume.units[p]
        self.y_label = volume.labels[q]
        self.y_label_units = volume.units[q]
        self.lock_aspect_ratio = volume.units[p] == volume.units[q] and bool(volume.units[p])
        self.image_updated.emit()

    def _place_empty_hint(self):
        if not self._empty_hint.isVisible():
            return
        rect = self.plot_item.vb.viewRect()
        self._empty_hint.setPos(rect.center())

    def _on_gl_hover(self, pos: QPointF):
        if self.volume is None or self.config.mouse_mode != "follow":
            return
        index = self.gl_view.pick(pos, self.volume, self.config.cut_axis)
        if index is not None and index != self._cut_index:
            self._stop_following()
            self._cut_index = index
            self._schedule_cut()

    def _on_gl_click(self, pos: QPointF, modifiers: int):
        if self.volume is None:
            return
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier.value)
        if self.config.mouse_mode == "follow":
            self.pin_cut()
            return
        index = self.gl_view.pick(pos, self.volume, self.config.cut_axis)
        if index is None:
            return
        self._stop_following()
        self._cut_index = index
        self._apply_cut()
        if shift:
            self.pin_cut()

    # ------------------------------------------------------------------ pins
    @SafeSlot()
    def pin_cut(self, label: str | None = None) -> None:
        """
        Pin the current cut: it stays outlined in 3D and appears in the cut strip.

        Args:
            label (str | None): Name of the cut; its coordinate when None.
        """
        if self.volume is None:
            return
        axis, index = self.config.cut_axis, self._cut_index
        if any(p[:2] == (axis, index) for p in self._pinned):
            return
        self._pinned.append((axis, index, label or ""))
        self._pinned.sort(key=lambda p: (p[0], p[1]))
        self._refresh_scene_decor()
        self._rebuild_thumbs()

    @SafeSlot()
    def clear_pinned_cuts(self) -> None:
        """Remove all pinned cuts."""
        self._pinned = []
        self._refresh_scene_decor()
        self._rebuild_thumbs()

    def pinned_cuts(self) -> list[dict]:
        """
        The pinned cuts.

        Returns:
            list[dict]: One dict per cut with axis, index, coordinate and label.
        """
        if self.volume is None:
            return []
        return [
            {
                "axis": AXIS_NAMES[a],
                "index": i,
                "coordinate": self.volume.coordinate(a, i),
                "label": label,
            }
            for a, i, label in self._pinned
        ]

    def _remove_pin(self, key: tuple):
        self._pinned = [p for p in self._pinned if p[:2] != key[:2]]
        self._refresh_scene_decor()
        self._rebuild_thumbs()

    def _go_to_pin(self, key: tuple):
        self._stop_following()
        axis, index = key[:2]
        if axis != self.config.cut_axis:
            self.config.cut_axis = axis
            self._sync_controls()
            self._refresh_scene_decor()
        self._cut_index = index
        self._configure_slider()
        self._apply_cut()

    def _rebuild_thumbs(self):
        for thumb in self._thumbs:
            self.pins_layout.removeWidget(thumb)
            thumb.deleteLater()
        self._thumbs = []
        volume = self.volume
        self.pins_hint.setVisible(not self._pinned)
        self.pins_scroll.setVisible(bool(self._pinned))
        if volume is None:
            return
        for axis, index, label in self._pinned:
            coordinate = volume.coordinate(axis, index)
            where = f"{volume.labels[axis]} = {coordinate:.3g} {volume.units[axis]}".rstrip()
            text = f"{label}\n{where}" if label else where
            thumb = _CutThumb(
                (axis, index, label), text, f"{text}\nClick to show, right-click to remove."
            )
            thumb.setIcon(self._thumb_pixmap(axis, index))
            thumb.clicked.connect(lambda _=False, k=(axis, index): self._go_to_pin(k))
            thumb.remove_requested.connect(self._remove_pin)
            thumb.setChecked((axis, index) == (self.config.cut_axis, self._cut_index))
            self.pins_layout.insertWidget(self.pins_layout.count() - 1, thumb)
            self._thumbs.append(thumb)

    def _thumb_pixmap(self, axis: int, index: int) -> QPixmap:
        volume = self.volume
        cut = volume.slice(axis, index)
        p, q = VolumeData.plane_axes(axis)
        if volume.display_box()[q] >= 1.5 * volume.display_box()[p]:
            cut = cut.T
        finite = cut[np.isfinite(cut)]
        low, high = (finite.min(), finite.max()) if finite.size else (0.0, 1.0)
        norm = np.nan_to_num((cut - low) / ((high - low) or 1.0))
        rgb = self._lut[np.clip((norm * 255).astype(int), 0, 255), :3]
        # array (u, v) with v upwards -> image rows top to bottom
        rgb = np.ascontiguousarray(np.transpose(rgb, (1, 0, 2))[::-1])
        h, w = rgb.shape[:2]
        image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(image).scaled(
            88, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )

    def _refresh_scene_decor(self):
        """Pinned outlines, labels and projections in the 3D view."""
        if self.volume is None or not hasattr(self, "gl_view"):
            return
        text = self._text_color()
        self.gl_view.set_pinned_cuts(self._pinned, text)
        self.gl_view.set_labels([p for p in self._pinned if p[2]], text)
        if self.config.show_projections:
            projections = {}
            longest = int(np.argmax(self.volume.display_box()))
            box = np.asarray(self.volume.display_box())
            elongated = box.max() >= 1.5 * np.sort(box)[1]
            for axis in range(3):
                if elongated and axis == longest:
                    continue
                proj = self.volume.projection(axis, "sum")
                low, high = float(np.min(proj)), float(np.max(proj))
                projections[axis] = (proj - low) / (high - low) if high > low else proj * 0
            dark = self.palette().window().color().lightness() < 128
            glow = QColor(235, 235, 245) if dark else QColor(40, 40, 60)
            self.gl_view.set_projections(projections, glow)
        else:
            self.gl_view.set_projections(None, QColor())

    # ------------------------------------------------------------------ properties
    @SafeProperty(str)
    def cut_axis(self) -> str:
        """Axis the cut is perpendicular to: "x", "y" or "z"."""
        return AXIS_NAMES[self.config.cut_axis]

    @cut_axis.setter
    def cut_axis(self, value):
        axis = AXIS_NAMES.index(value) if isinstance(value, str) else int(value)
        if axis not in (0, 1, 2):
            raise ValueError("cut_axis must be x, y or z.")
        if axis == self.config.cut_axis and self.volume is not None:
            self._sync_controls()
            return
        self.config.cut_axis = axis
        if self.volume is not None:
            self._cut_index = self.volume.shape[axis] // 2
        self._sync_controls()
        self._configure_slider()
        self._apply_cut()

    @SafeProperty(int)
    def cut_index(self) -> int:
        """Voxel index of the cut along the cut axis."""
        return self._cut_index

    @cut_index.setter
    def cut_index(self, value: int):
        if self.volume is None:
            self._cut_index = int(value)
            return
        self._cut_index = int(np.clip(value, 0, self.volume.shape[self.config.cut_axis] - 1))
        self._configure_slider()
        self._apply_cut()

    def cut_coordinate(self) -> float | None:
        """Coordinate of the current cut along the cut axis."""
        if self.volume is None:
            return None
        return self.volume.coordinate(self.config.cut_axis, self._cut_index)

    @SafeProperty(str)
    def mouse_mode(self) -> str:
        """What the pointer does over the volume: "click" (click to cut) or "follow"."""
        return self.config.mouse_mode

    @mouse_mode.setter
    def mouse_mode(self, value: str):
        if value not in ("click", "follow"):
            raise ValueError('mouse_mode must be "click" or "follow".')
        self.config.mouse_mode = value
        self._sync_controls()

    @SafeProperty(bool)
    def clip_volume(self) -> bool:
        """Hide the volume in front of the cut."""
        return self.config.clip_volume

    @clip_volume.setter
    def clip_volume(self, value: bool):
        self.config.clip_volume = bool(value)
        self._sync_controls()
        self._apply_cut()

    @SafeProperty(bool)
    def show_projections(self) -> bool:
        """Show projections on the far walls of the box."""
        return self.config.show_projections

    @show_projections.setter
    def show_projections(self, value: bool):
        self.config.show_projections = bool(value)
        self._sync_controls()
        self._refresh_scene_decor()

    @SafeProperty(float)
    def opacity(self) -> float:
        """Opacity of the brightest voxel, 0..1."""
        return self.config.opacity

    @opacity.setter
    def opacity(self, value: float):
        self.config.opacity = float(np.clip(value, 0.0, 1.0))
        self._recolor()

    @SafeProperty(str)
    def color_map(self) -> str:
        """Colour map of the volume, the cut and the pinned cuts."""
        return self.config.color_map

    @color_map.setter
    def color_map(self, value: str):
        ImageBase.color_map.fset(self, value)
        self._lut = self._make_lut(self.config.color_map)
        self._recolor()

    # The cut image's processing, as the image toolbar expects it (only log is offered).
    @SafeProperty(bool, auto_emit=True)
    def log(self) -> bool:
        """Logarithmic colour scale of the cut."""
        return self.main_image.log

    @log.setter
    def log(self, enable: bool):
        self.main_image.log = enable

    @SafeProperty(bool, auto_emit=True)
    def fft(self) -> bool:
        """FFT of the cut."""
        return self.main_image.fft

    @fft.setter
    def fft(self, enable: bool):
        self.main_image.fft = enable

    @SafeProperty(bool, auto_emit=True)
    def transpose(self) -> bool:
        """Transpose the cut."""
        return self.main_image.transpose

    @transpose.setter
    def transpose(self, enable: bool):
        self.main_image.transpose = enable

    @SafeProperty(int)
    def num_rotation_90(self) -> int:
        """Counterclockwise quarter turns of the cut."""
        return self.main_image.num_rotation_90

    @num_rotation_90.setter
    def num_rotation_90(self, value: int):
        self.main_image.num_rotation_90 = value

    @property
    def main_image(self) -> ImageItem:
        """The image item showing the current cut."""
        return self.layer_manager["main"].image

    @SafeSlot()
    def reset_camera(self) -> None:
        """Look at the whole volume from the default direction."""
        self.gl_view.reset_camera()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _make_lut(name: str | None) -> np.ndarray:
        cmap = pg.colormap.get(name or "plasma")
        if cmap is None:
            cmap = pg.colormap.get("plasma")
        return cmap.getLookupTable(0.0, 1.0, 256, alpha=False).astype(np.ubyte)

    def _recolor(self):
        if self.volume is None or not hasattr(self, "gl_view"):
            return
        self._volume_rgba = volume_rgba(self._normalized, self._lut, self.config.opacity)
        self.gl_view.update_volume_rgba(self._volume_rgba)
        self._apply_cut()
        self._rebuild_thumbs()

    def cleanup(self):
        self._cut_timer.stop()
        self._stop_data_feed()
        self.bec_dispatcher.disconnect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.gl_view.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtCore import QCoreApplication
    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = VolumePlot()
    widget.load_demo()
    widget.resize(1400, 820)
    widget.show()
    sys.exit(app.exec())
