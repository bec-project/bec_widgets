from __future__ import annotations

from dataclasses import dataclass

import pyqtgraph as pg
from qtpy.QtCore import QObject, Qt, Signal
from qtpy.QtGui import QColor

from bec_widgets.utils.colors import get_accent_colors, get_theme_name
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.plots.waveform.utils.alignment_panel import WaveformAlignmentPanel


@dataclass(slots=True)
class AlignmentContext:
    """Alignment state produced by `Waveform` and consumed by the controller.

    Attributes:
        visible: Whether alignment mode is currently visible.
        positioner_name: Name of the resolved x-axis positioner, if available.
        precision: Decimal precision to use for readback and target labels.
        limits: Optional positioner limits for the draggable target line.
        readback: Current cached positioner readback value.
        has_dap_curves: Whether the waveform currently contains any DAP curves.
        force_readback: Whether the embedded positioner should refresh its readback immediately.
    """

    visible: bool
    positioner_name: str | None
    precision: int = 3
    limits: tuple[float, float] | None = None
    readback: float | None = None
    has_dap_curves: bool = False
    force_readback: bool = False


class WaveformAlignmentController(QObject):
    """Own the alignment plot overlays and synchronize them with the alignment panel."""

    move_absolute_requested = Signal(float)

    def __init__(self, plot_item: pg.PlotItem, panel: WaveformAlignmentPanel, parent=None):
        super().__init__(parent=parent)
        self._plot_item = plot_item
        self._panel = panel

        self._visible = False
        self._positioner_name: str | None = None
        self._precision = 3
        self._limits: tuple[float, float] | None = None
        self._readback: float | None = None
        self._marker_line: pg.InfiniteLine | None = None
        self._target_line: pg.InfiniteLine | None = None

        self._panel.position_readback_changed.connect(self.update_position)
        self._panel.target_toggled.connect(self._on_target_toggled)
        self._panel.target_move_requested.connect(self._on_target_move_requested)
        self._panel.fit_selection_changed.connect(self._on_fit_selection_changed)
        self._panel.fit_center_requested.connect(self._on_fit_center_requested)

    @property
    def marker_line(self) -> pg.InfiniteLine | None:
        """Return the current-position indicator line, if it exists."""
        return self._marker_line

    @property
    def target_line(self) -> pg.InfiniteLine | None:
        """Return the draggable target indicator line, if it exists."""
        return self._target_line

    def update_context(self, context: AlignmentContext):
        """Apply waveform-owned alignment context to the panel and plot overlays.

        Args:
            context: Snapshot of the current alignment-relevant waveform/device state.
        """
        previous_name = self._positioner_name
        self._visible = context.visible
        self._positioner_name = context.positioner_name
        self._precision = context.precision
        self._limits = context.limits
        self._readback = context.readback

        self._panel.set_positioner_device(context.positioner_name)
        self._panel.set_positioner_enabled(context.visible and context.positioner_name is not None)
        self._panel.set_status_message(self._status_message_for_context(context))

        if context.positioner_name is None or not context.visible:
            self.clear()
            self._refresh_fit_actions()
            self._refresh_target_controls()
            return

        if previous_name != context.positioner_name:
            self._clear_marker()
            if self._panel.target_active:
                self._clear_target_line()

        if context.readback is not None:
            self.update_position(context.readback)

        if self._panel.target_active:
            if previous_name != context.positioner_name or self._target_line is None:
                self._show_target_line()
            else:
                self._refresh_target_line_metadata()
                self._on_target_line_changed()

        if context.force_readback or previous_name != context.positioner_name:
            self._panel.force_positioner_readback()

        self._refresh_fit_actions()
        self._refresh_target_controls()

    @SafeSlot(float)
    def update_position(self, position: float):
        """Update the live position marker from a positioner readback value.

        Args:
            position: Current absolute position of the active alignment positioner.
        """
        self._readback = float(position)
        if not self._visible or self._positioner_name is None:
            self._clear_marker()
            return

        self._ensure_marker()
        self._marker_line.setValue(self._readback)
        self._marker_line.label.setText(
            f"{self._positioner_name}: {self._readback:.{self._precision}f}"
        )

    @SafeSlot(dict, dict)
    def update_dap_summary(self, data: dict, metadata: dict):
        """Forward DAP summary updates into the alignment fit panel.

        Args:
            data: DAP fit summary payload.
            metadata: Metadata describing the emitting DAP curve.
        """
        self._panel.update_dap_summary(data, metadata)
        self._refresh_fit_actions()

    @SafeSlot(str)
    def remove_dap_curve(self, curve_id: str):
        """Remove a deleted DAP curve from the alignment fit selection state.

        Args:
            curve_id: Label of the DAP curve that was removed from the waveform.
        """
        self._panel.remove_dap_curve(curve_id)
        self._panel.clear_fit_selection_if_missing()
        self._refresh_fit_actions()

    def clear(self):
        """Remove alignment overlay items from the plot and reset target state."""
        self._clear_marker()
        self._clear_target_line()

    def cleanup(self):
        """Disconnect panel signals and remove all controller-owned overlay items."""
        self.clear()
        self._disconnect_panel_signals()

    def refresh_theme_colors(self):
        """Reapply theme-aware styling to any existing alignment overlay items."""
        self._apply_marker_style()
        self._apply_target_style()

    def _disconnect_panel_signals(self):
        signal_pairs = [
            (self._panel.position_readback_changed, self.update_position),
            (self._panel.target_toggled, self._on_target_toggled),
            (self._panel.target_move_requested, self._on_target_move_requested),
            (self._panel.fit_selection_changed, self._on_fit_selection_changed),
            (self._panel.fit_center_requested, self._on_fit_center_requested),
        ]
        for signal, slot in signal_pairs:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                continue

    def _selected_fit_has_center(self) -> bool:
        data = self._panel.selected_fit_summary()
        params = data.get("params", []) if isinstance(data, dict) else []
        return any(param[0] == "center" for param in params if param)

    @staticmethod
    def _status_message_for_context(context: AlignmentContext) -> str | None:
        if context.positioner_name is None:
            return "Alignment mode requires a positioner on the x axis."
        if not context.has_dap_curves:
            return "Add a DAP curve in Curve Settings to enable alignment fitting."
        return None

    def _refresh_fit_actions(self):
        self._panel.set_fit_actions_enabled(
            self._visible and self._positioner_name is not None and self._selected_fit_has_center()
        )

    def _refresh_target_controls(self):
        has_positioner = self._visible and self._positioner_name is not None
        self._panel.set_target_enabled(has_positioner)
        self._panel.set_target_move_enabled(has_positioner and self._target_line is not None)
        if self._target_line is None:
            self._panel.set_target_value(None)

    def _ensure_marker(self):
        if self._marker_line is not None:
            return

        warning = get_accent_colors().warning

        self._marker_line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(warning, width=4),
            label="",
            labelOpts={"position": 0.95, "color": warning},
        )
        self._marker_line.skip_auto_range = True
        self._apply_marker_style()
        self._plot_item.addItem(self._marker_line)

    def _clear_marker(self):
        if self._marker_line is None:
            return
        self._plot_item.removeItem(self._marker_line)
        self._marker_line = None

    def _show_target_line(self):
        if not self._visible or self._positioner_name is None:
            return

        if self._target_line is None:
            accent_colors = get_accent_colors()
            label = f"{self._positioner_name} target={{value:0.{self._precision}f}}"
            self._target_line = pg.InfiniteLine(
                movable=True,
                angle=90,
                pen=pg.mkPen(accent_colors.default, width=2, style=Qt.PenStyle.DashLine),
                hoverPen=pg.mkPen(accent_colors.success, width=2),
                label=label,
                labelOpts={"movable": True, "color": accent_colors.default},
            )
            self._target_line.sigPositionChanged.connect(self._on_target_line_changed)
            self._apply_target_style()
            self._plot_item.addItem(self._target_line)
        self._refresh_target_line_metadata()

        value = 0.0 if self._readback is None else self._readback
        if self._limits is not None:
            value = min(max(value, self._limits[0]), self._limits[1])
        self._target_line.setValue(value)
        self._on_target_line_changed()

    def _refresh_target_line_metadata(self):
        if self._target_line is None or self._positioner_name is None:
            return
        self._apply_target_style()
        self._target_line.label.setFormat(
            f"{self._positioner_name} target={{value:0.{self._precision}f}}"
        )
        if self._limits is not None:
            self._target_line.setBounds(list(self._limits))
        else:
            self._target_line.setBounds((None, None))
        if self._limits is not None:
            current_value = float(self._target_line.value())
            clamped_value = min(max(current_value, self._limits[0]), self._limits[1])
            if clamped_value != current_value:
                self._target_line.setValue(clamped_value)

    def _clear_target_line(self):
        if self._target_line is not None:
            try:
                self._target_line.sigPositionChanged.disconnect(self._on_target_line_changed)
            except (RuntimeError, TypeError):
                pass
            self._plot_item.removeItem(self._target_line)
            self._target_line = None
        self._panel.set_target_value(None)

    def _apply_marker_style(self):
        if self._marker_line is None:
            return

        accent_colors = get_accent_colors()
        warning = accent_colors.warning

        self._marker_line.setPen(pg.mkPen(warning, width=4))
        self._marker_line.label.setColor(warning)
        self._marker_line.label.fill = pg.mkBrush(self._label_fill_color())

    def _apply_target_style(self):
        if self._target_line is None:
            return

        accent_colors = get_accent_colors()
        default = accent_colors.default
        success = accent_colors.success

        self._target_line.setPen(pg.mkPen(default, width=2, style=Qt.PenStyle.DashLine))
        self._target_line.setHoverPen(pg.mkPen(success, width=2))
        self._target_line.label.setColor(default)
        self._target_line.label.fill = pg.mkBrush(self._label_fill_color())

    @staticmethod
    def _label_fill_color() -> QColor:
        if get_theme_name() == "light":
            return QColor(244, 244, 244, 228)
        return QColor(48, 48, 48, 210)

    @SafeSlot(bool)
    def _on_target_toggled(self, checked: bool):
        if checked:
            self._show_target_line()
        else:
            self._clear_target_line()
        self._refresh_target_controls()

    @SafeSlot(object)
    def _on_target_line_changed(self, _line=None):
        if self._target_line is None:
            return
        self._panel.set_target_value(float(self._target_line.value()), precision=self._precision)
        self._refresh_target_controls()

    @SafeSlot()
    def _on_target_move_requested(self):
        if self._visible and self._positioner_name is not None and self._target_line is not None:
            self.move_absolute_requested.emit(float(self._target_line.value()))

    @SafeSlot(str)
    def _on_fit_selection_changed(self, _curve_id: str):
        self._refresh_fit_actions()

    @SafeSlot(float)
    def _on_fit_center_requested(self, value: float):
        if self._visible and self._positioner_name is not None:
            self.move_absolute_requested.emit(float(value))
