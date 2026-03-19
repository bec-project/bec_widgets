from __future__ import annotations

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from bec_widgets.utils.colors import get_accent_colors, get_theme_name
from bec_widgets.widgets.control.device_control.positioner_box.positioner_control_line.positioner_control_line import (
    PositionerControlLine,
)
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog import LMFitDialog


class WaveformAlignmentPanel(QWidget):
    """Compact bottom panel used by Waveform alignment mode."""

    position_readback_changed = Signal(float)
    target_toggled = Signal(bool)
    target_move_requested = Signal()
    fit_selection_changed = Signal(str)
    fit_center_requested = Signal(float)

    def __init__(self, parent=None, client=None, gui_id: str | None = None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setProperty("skip_settings", True)

        self.positioner = PositionerControlLine(parent=self, client=client, gui_id=gui_id)
        self.positioner.hide_device_selection = True

        self.fit_dialog = LMFitDialog(
            parent=self, client=client, gui_id=gui_id, ui_file="lmfit_dialog_compact.ui"
        )
        self.fit_dialog.active_action_list = ["center"]
        self.fit_dialog.enable_actions = False

        self.target_toggle = QCheckBox("Target: --", parent=self)
        self.move_to_target_button = QPushButton("Move To Target", parent=self)
        self.move_to_target_button.setEnabled(False)
        self.target_group = QGroupBox("Target Position", parent=self)

        self.status_label = QLabel(parent=self)
        self.status_label.setWordWrap(False)
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self.status_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.status_label.setMaximumHeight(28)
        self.status_label.setVisible(False)

        self._init_ui()
        self.fit_dialog.setMinimumHeight(0)
        self.target_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._sync_target_group_size()
        self.refresh_theme_colors()
        self._connect_signals()

    def _connect_signals(self):
        self.positioner.position_update.connect(self.position_readback_changed)
        self.target_toggle.toggled.connect(self.target_toggled)
        self.move_to_target_button.clicked.connect(self.target_move_requested)
        self.fit_dialog.selected_fit.connect(self.fit_selection_changed)
        self.fit_dialog.move_action.connect(self._forward_fit_move_action)

    def _init_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(260)

        root = QGridLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.fit_dialog.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root.addWidget(
            self.status_label,
            0,
            0,
            1,
            2,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )
        root.addWidget(self.fit_dialog, 1, 0, 1, 2)

        target_layout = QHBoxLayout(self.target_group)
        target_layout.addWidget(self.target_toggle)
        target_layout.addWidget(self.move_to_target_button)

        root.addWidget(self.positioner, 2, 0, alignment=Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.target_group, 2, 1, alignment=Qt.AlignmentFlag.AlignTop)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 0)
        root.setRowStretch(1, 1)

    def _sync_target_group_size(self):
        representative_text = "Target: -99999.999"
        label_width = max(
            self.target_toggle.sizeHint().width(),
            self.target_toggle.fontMetrics().horizontalAdvance(representative_text) + 24,
        )
        self.target_toggle.setMinimumWidth(label_width)

        # To make those two box the same height
        target_height = max(
            self.positioner.height(),
            self.positioner.ui.device_box.minimumSizeHint().height(),
            self.positioner.ui.device_box.sizeHint().height(),
        )
        self.target_group.setFixedHeight(target_height)
        self.target_group.setFixedWidth(self.target_group.sizeHint().width() + 16)

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_target_group_size()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_target_group_size()

    def set_status_message(self, text: str | None):
        """Show or hide the alignment status pill.

        Args:
            text: Message to display. Pass `None` or an empty string to hide the pill.
        """

        text = text or ""
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    @staticmethod
    def _qcolor_to_rgba(color: QColor, alpha: int | None = None) -> str:
        if alpha is not None:
            color = QColor(color)
            color.setAlpha(alpha)
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"

    def refresh_theme_colors(self):
        """Apply theme-aware accent styling to the status pill."""
        warning = get_accent_colors().warning
        is_light = get_theme_name() == "light"
        text_color = "#202124" if is_light else warning.name()
        fill_alpha = 72 if is_light else 48
        border_alpha = 220 if is_light else 160

        self.status_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self._qcolor_to_rgba(warning, fill_alpha)};
                border: 1px solid {self._qcolor_to_rgba(warning, border_alpha)};
                border-radius: 12px;
                padding: 4px 10px;
                color: {text_color};
            }}
        """)

    def set_positioner_device(self, device: str | None):
        """Bind the embedded positioner control to a fixed device.

        Args:
            device: Name of the positioner device to display, or `None` to clear it.
        """
        if device is None:
            self.positioner.ui.device_box.setTitle("No positioner selected")
            return
        if self.positioner.device != device:
            self.positioner.set_positioner(device)
        self.positioner.hide_device_selection = True

    def set_positioner_enabled(self, enabled: bool):
        """Enable or disable the embedded positioner widget.

        Args:
            enabled: Whether the positioner widget should accept interaction.
        """
        self.positioner.setEnabled(enabled)

    def force_positioner_readback(self):
        """Trigger an immediate readback refresh on the embedded positioner widget."""
        self.positioner.force_update_readback()

    def set_target_enabled(self, enabled: bool):
        """Enable or disable the target-line toggle.

        Args:
            enabled: Whether the target toggle should accept interaction.
        """
        self.target_toggle.setEnabled(enabled)

    def set_target_move_enabled(self, enabled: bool):
        """Enable or disable the move-to-target button.

        Args:
            enabled: Whether the move button should accept interaction.
        """
        self.move_to_target_button.setEnabled(enabled)

    def set_target_active(self, active: bool):
        """Programmatically toggle the draggable target-line state.

        Args:
            active: Whether the target line should be considered active.
        """
        blocker = self.target_toggle.blockSignals(True)
        self.target_toggle.setChecked(active)
        self.target_toggle.blockSignals(blocker)
        if not active:
            self.set_target_value(None)

    def set_target_value(self, value: float | None, precision: int = 3) -> None:
        """
        Update the target checkbox label for the draggable target line.

        Args:
            value(float | None): The target value to display. If None, the label will show "--".
            precision(int): The number of decimal places to display for the target value.
        """
        if value is None or not self.target_toggle.isChecked():
            self.target_toggle.setText("Target: --")
            return
        self.target_toggle.setText(f"Target: {value:.{precision}f}")

    def set_fit_actions_enabled(self, enabled: bool):
        """Enable or disable LMFit action buttons in the embedded fit dialog.

        Args:
            enabled: Whether fit action buttons should be enabled.
        """
        self.fit_dialog.enable_actions = enabled

    def update_dap_summary(self, data: dict, metadata: dict):
        """Forward a DAP summary update into the embedded fit dialog.

        Args:
            data: DAP fit summary payload.
            metadata: Metadata describing the emitting DAP curve.
        """
        self.fit_dialog.update_summary_tree(data, metadata)

    def remove_dap_curve(self, curve_id: str):
        """Remove DAP summary state for a deleted fit curve.

        Args:
            curve_id: Label of the DAP curve that should be removed.
        """
        self.fit_dialog.remove_dap_data(curve_id)

    def clear_fit_selection_if_missing(self):
        """Select a remaining fit curve if the current selection no longer exists."""
        fit_curve_id = self.fit_dialog.fit_curve_id
        if fit_curve_id is not None and fit_curve_id not in self.fit_dialog.summary_data:
            remaining = list(self.fit_dialog.summary_data)
            self.fit_dialog.fit_curve_id = remaining[0] if remaining else None

    @property
    def target_active(self) -> bool:
        """Whether the target-line checkbox is currently checked."""
        return self.target_toggle.isChecked()

    @property
    def selected_fit_curve_id(self) -> str | None:
        """Return the currently selected fit curve label, if any."""
        return self.fit_dialog.fit_curve_id

    def selected_fit_summary(self) -> dict | None:
        """Return the summary payload for the currently selected fit curve.

        Returns:
            The selected fit summary, or `None` if no fit curve is selected.
        """
        fit_curve_id = self.selected_fit_curve_id
        if fit_curve_id is None:
            return None
        return self.fit_dialog.summary_data.get(fit_curve_id)

    def _forward_fit_move_action(self, action: tuple[str, float]):
        param_name, param_value = action
        if param_name == "center":
            self.fit_center_requested.emit(float(param_value))
