from __future__ import annotations

from typing import Any

from bec_lib import bl_states, messages
from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from qtpy.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from qtpy.QtGui import QColor, QMouseEvent, QPalette
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors, get_accent_colors, get_theme_name, rgba, theme_color
from bec_widgets.utils.eliding_label import ElidingLabel
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.forms_from_types.pydantic_widget_form import (
    OptionalValueWidget,
    PydanticWidgetForm,
)
from bec_widgets.widgets.services.beamline_states.dialogs import (
    BEAMLINE_STATE_STATUS_LABELS,
    SUPPORTED_BEAMLINE_STATES,
)


class _BeamlineStatePillHeader(QWidget):
    """Header surface responsible for pill click gestures."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class BeamlineStatePill(BECWidget, QWidget):
    """
    Compact widget showing one BEC beamline state.

    The pill subscribes to ``MessageEndpoints.beamline_state(state_name)`` and updates whenever
    a ``BeamlineStateMessage`` is published for that state.
    """

    PLUGIN = False
    RPC = False

    state_changed = Signal(str, str, str)
    update_requested = Signal(str, object)
    remove_requested = Signal(str)
    scan_interlock_toggle_requested = Signal(str, bool)
    scan_interlock_statuses_changed = Signal(str, object)
    row_height_changed = Signal()

    _STATUS_LABELS = BEAMLINE_STATE_STATUS_LABELS
    _STATUS_ICONS = {
        "valid": "check_circle",
        "invalid": "cancel",
        "warning": "warning",
        "unknown": "help",
    }

    def __init__(
        self,
        parent: QWidget | None = None,
        state_name: str | None = None,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            parent=parent, client=client, config=config, gui_id=gui_id, theme_update=True, **kwargs
        )
        self.setObjectName("BeamlineStatePill")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        # Floor below which the pill keeps its structure; the title/detail elide rather than
        # pushing the pill wider or taller, so collapsed rows stay a consistent size.
        self.setMinimumWidth(200)
        self._state_name: str | None = None
        self._state_config: messages.BeamlineStateConfig | None = None
        self._status = "unknown"
        self._label = "No state information available."
        self._expanded = False
        self._idle_card_background = False
        self._interlock_required_statuses: list[str] | None = None
        self._interlock_statuses: list[str] = ["valid", "warning"]
        self._interlock_triggered = False
        self._interlock_pulse = 0.0
        self._header_icon_cache_key: tuple | None = None
        self._populating_settings = False
        self._settings_baseline: dict[str, Any] = {}
        self._settings_dirty_fields: set[str] = set()
        self._settings_form_stale = True

        self._init_ui(state_name)

    def _init_ui(self, state_name: str | None = None) -> None:
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(18)
        self._shadow.setOffset(0, 2)
        self._shadow.setColor(QColor(0, 0, 0, 120))
        self._shadow.setEnabled(False)
        self.setGraphicsEffect(self._shadow)

        self._header = _BeamlineStatePillHeader(self)
        self._header.setObjectName("beamline_state_header")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.clicked.connect(self._toggle_expanded)

        self._stripe = QWidget(self)
        self._stripe.setObjectName("beamline_state_stripe")
        self._stripe.setFixedWidth(4)
        self._stripe.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._stripe.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("beamline_state_icon")
        self._icon_label.setFixedSize(32, 32)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._name_label = ElidingLabel(self)
        self._name_label.setObjectName("beamline_state_name")
        self._name_label.setTextFormat(Qt.TextFormat.PlainText)
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._status_label = QLabel(self)
        self._status_label.setObjectName("beamline_state_status")
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._detail_label = ElidingLabel(self)
        self._detail_label.setObjectName("beamline_state_detail")
        self._detail_label.setTextFormat(Qt.TextFormat.PlainText)
        self._detail_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._interlock_button = QToolButton(self)
        self._interlock_button.setObjectName("beamline_state_interlock")
        self._interlock_button.setAutoRaise(True)
        self._interlock_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._interlock_button.clicked.connect(self._emit_interlock_toggle_requested)
        self._expand_button = QToolButton(self)
        self._expand_button.setObjectName("beamline_state_expand")
        self._expand_button.setAutoRaise(True)
        self._expand_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_button.clicked.connect(self._toggle_expanded)

        self._interlock_animation = QPropertyAnimation(self, b"interlock_pulse", self)
        self._interlock_animation.setDuration(1400)
        self._interlock_animation.setStartValue(0.0)
        self._interlock_animation.setEndValue(1.0)
        self._interlock_animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._interlock_animation.setLoopCount(-1)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        text_layout.addWidget(self._name_label)
        text_layout.addWidget(self._detail_label)

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10, 8, 12, 8)
        header_layout.setSpacing(10)
        header_layout.addWidget(self._stripe)
        header_layout.addWidget(self._icon_label)
        header_layout.addLayout(text_layout, 1)
        header_layout.addWidget(self._status_label, 0, Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self._interlock_button)
        header_layout.addWidget(self._expand_button)

        self._settings = QWidget(self)
        self._settings.setObjectName("beamline_state_settings")
        self._settings.setVisible(False)
        self._state_type_value = QLabel(self._settings)
        self._config_form: PydanticWidgetForm | None = None
        self._config_form_host = QVBoxLayout()
        self._config_form_host.setContentsMargins(0, 0, 0, 0)
        self._config_form_host.setSpacing(0)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        self._update_button = QPushButton("Update", self._settings)
        self._update_button.setIcon(material_icon("save", convert_to_pixmap=False))
        self._revert_button = QPushButton("Revert", self._settings)
        self._revert_button.setIcon(material_icon("undo", convert_to_pixmap=False))
        self._remove_button = QPushButton("Remove", self._settings)
        self._remove_button.setObjectName("beamline_state_remove_button")
        self._remove_button.setIcon(material_icon("delete", convert_to_pixmap=False))
        self._update_button.clicked.connect(self._emit_update_requested)
        self._revert_button.clicked.connect(self._revert_settings)
        self._remove_button.clicked.connect(self._emit_remove_requested)
        button_layout.addWidget(self._update_button)
        button_layout.addWidget(self._revert_button)
        button_layout.addWidget(self._remove_button)
        button_layout.addStretch(1)

        self._settings_form = QFormLayout()
        self._settings_form.setContentsMargins(0, 0, 0, 0)
        self._settings_form.setHorizontalSpacing(10)
        self._settings_form.setVerticalSpacing(8)
        self._settings_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self._settings_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._settings_form.addRow("Type", self._state_type_value)

        self._interlock_warning_checkbox = QCheckBox(
            "Trigger ScanInterlock on WARNING state", self._settings
        )
        self._interlock_warning_checkbox.setToolTip(
            "By default both VALID and WARNING are accepted. Enable this so a WARNING status also "
            "trips the scan interlock (only VALID accepted)."
        )
        self._interlock_warning_checkbox.toggled.connect(self._on_interlock_warning_toggled)
        self._sync_interlock_warning_checkbox()

        settings_layout = QVBoxLayout(self._settings)
        settings_layout.setContentsMargins(12, 8, 12, 12)
        settings_layout.setSpacing(8)
        settings_layout.addLayout(self._settings_form)
        settings_layout.addLayout(self._config_form_host)
        settings_layout.addWidget(self._interlock_warning_checkbox)
        settings_layout.addLayout(button_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._settings)
        self.setLayout(layout)

        self._settings.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.set_state_name(state_name)
        self._update_button.setEnabled(False)
        self._revert_button.setEnabled(False)

    @SafeProperty(str, default=None)
    def state_name(self) -> str | None:
        """Name of the BEC beamline state displayed by this pill."""
        return self._state_name

    @state_name.setter
    def state_name(self, state_name: str | None) -> None:
        self.set_state_name(state_name)

    def set_state_name(self, state_name: str | None) -> None:
        """
        Set the BEC beamline state this pill displays.

        Args:
            state_name: State name as published by ``AvailableBeamlineStatesMessage``.
        """
        if state_name == self._state_name:
            return

        if self._state_name is not None:
            self.bec_dispatcher.disconnect_slot(
                self.update_state, MessageEndpoints.beamline_state(self._state_name)
            )

        self._state_name = state_name
        self._name_label.setText(state_name or "Beamline state")

        if self._state_name is None:
            self._set_visual_state("unknown", "No beamline state selected.")
            return

        self._set_visual_state("unknown", "No state information available.")
        self._refresh_latest_state()
        self.bec_dispatcher.connect_slot(
            self.update_state, MessageEndpoints.beamline_state(self._state_name)
        )

    def set_state_config(self, state_config: messages.BeamlineStateConfig | None) -> None:
        """Set the editable BEC state configuration displayed by the expanded panel."""
        self._state_config = state_config
        self._settings_form_stale = True
        if self._config_form is not None:
            self._populate_settings()
            self.mark_current_settings_clean()

    @SafeProperty(bool, default=False)
    def idle_card_background(self) -> bool:
        """
        Whether idle collapsed pills keep the status-tinted card background.
        """
        return self._idle_card_background

    @idle_card_background.setter
    def idle_card_background(self, enabled: bool) -> None:
        self._idle_card_background = enabled
        self._apply_visual_state()

    def set_idle_card_background(self, enabled: bool) -> None:
        """Set whether idle collapsed pills keep the status-tinted card background."""
        self.idle_card_background = enabled

    @Property(float)
    def interlock_pulse(self) -> float:
        """Animation phase in [0, 1] driving the triggered scan-interlock highlight."""
        return self._interlock_pulse

    @interlock_pulse.setter
    def interlock_pulse(self, phase: float) -> None:
        self._interlock_pulse = float(phase)
        if self._interlock_triggered:
            self._apply_visual_state()

    def set_scan_interlock(self, required_statuses: list[str] | None, triggered: bool) -> None:
        """
        Set the scan-interlock participation of this pill.

        Args:
            required_statuses: Statuses the scan interlock accepts for this state, or ``None``
                if the state is not included in the scan interlock.
            triggered: Whether the armed scan interlock is currently tripped by this state.
        """
        triggered = bool(triggered) and required_statuses is not None
        if required_statuses is not None:
            self._interlock_statuses = list(required_statuses)
            self._sync_interlock_warning_checkbox()
        if (required_statuses, triggered) == (
            self._interlock_required_statuses,
            self._interlock_triggered,
        ):
            return
        self._interlock_required_statuses = required_statuses
        self._interlock_triggered = triggered
        if triggered:
            if self._interlock_animation.state() != QPropertyAnimation.State.Running:
                self._interlock_animation.start()
        else:
            self._interlock_animation.stop()
            self._interlock_pulse = 0.0
        self._apply_visual_state()

    @property
    def interlock_statuses(self) -> list[str]:
        """Accepted statuses to enroll this state with when it joins the scan interlock."""
        return list(self._interlock_statuses)

    def set_interlock_statuses(self, statuses: list[str]) -> None:
        """Configure the accepted scan-interlock statuses for this state."""
        self._interlock_statuses = list(statuses)
        self._sync_interlock_warning_checkbox()

    def _sync_interlock_warning_checkbox(self) -> None:
        trigger_on_warning = "warning" not in self._interlock_statuses
        self._interlock_warning_checkbox.blockSignals(True)
        self._interlock_warning_checkbox.setChecked(trigger_on_warning)
        self._interlock_warning_checkbox.blockSignals(False)

    @SafeSlot(bool)
    def _on_interlock_warning_toggled(self, trigger_on_warning: bool) -> None:
        statuses = ["valid"] if trigger_on_warning else ["valid", "warning"]
        if statuses == self._interlock_statuses:
            return
        self._interlock_statuses = statuses
        if self._state_name is not None:
            self.scan_interlock_statuses_changed.emit(self._state_name, statuses)

    @SafeSlot()
    def _emit_interlock_toggle_requested(self) -> None:
        if self._state_name is None:
            return
        include = self._interlock_required_statuses is None
        self.scan_interlock_toggle_requested.emit(self._state_name, include)

    def _refresh_latest_state(self) -> None:
        if self._state_name is None:
            return
        msg = self.client.connector.get_last(
            MessageEndpoints.beamline_state(self._state_name), key="data"
        )
        if msg is not None:
            self.update_state(msg.content, msg.metadata)

    @SafeSlot(dict, dict)
    def update_state(
        self, content: dict[str, Any], _metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Update this pill from a ``BeamlineStateMessage`` content dictionary.
        """
        name = content.get("name")
        if self._state_name is not None and name and name != self._state_name:
            return

        status = str(content.get("status", "unknown")).lower()
        label = str(content.get("label", "No state information available."))
        self._set_visual_state(status, label)
        self.state_changed.emit(self._state_name or str(name or ""), status, label)

    @SafeSlot(str)
    def apply_theme(self, _theme: str) -> None:
        self._apply_visual_state()

    def _set_visual_state(self, status: str, label: str) -> None:
        status = status if status in self._STATUS_LABELS else "unknown"
        self._status = status
        self._label = label

        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        colors = self._state_colors(self._status)
        accent = colors["accent"]
        included = self._interlock_required_statuses is not None
        active_card = self._expanded or included
        border = colors["border"] if self._idle_card_background else "transparent"
        background = colors["background"] if self._idle_card_background else "transparent"
        card_gradient = (
            "qlineargradient("
            "x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {colors['gradient_accent']}, "
            f"stop:{colors['gradient_stop']} {colors['card_background']}, "
            f"stop:1 {colors['card_background']}"
            ")"
        )
        if active_card:
            background = card_gradient
            border = colors["card_border"]
        hover_background = card_gradient
        hover_border = colors["card_border"]
        border_width = 1
        shadow_color = QColor(colors["shadow"])
        shadow_blur = int(colors["shadow_blur"])
        shadow_enabled = active_card
        if self._interlock_triggered:
            flash = 1.0 - abs(2.0 * self._interlock_pulse - 1.0)
            background = self._traveling_gradient(
                colors["card_background"], colors["interlock_band"], self._interlock_pulse
            )
            hover_background = background
            border = rgba(QColor(colors["interlock_trigger"]), 110 + int(145 * flash))
            hover_border = border
            border_width = 2
            shadow_color = QColor(colors["interlock_trigger"])
            shadow_color.setAlpha(150)
            shadow_blur = int(colors["shadow_blur"]) + 10
            shadow_enabled = True
        self._shadow.setColor(shadow_color)
        self._shadow.setBlurRadius(shadow_blur)
        self._shadow.setOffset(0, int(colors["shadow_y_offset"]))
        self._shadow.setEnabled(shadow_enabled)

        self._update_header_icons(colors)
        self._status_label.setText(self._STATUS_LABELS[self._status])
        self._detail_label.setText(self._label)
        self.setToolTip(self._label)
        self.setStyleSheet(
            "#BeamlineStatePill {"
            f"background: {background};"
            f"border: {border_width}px solid {border};"
            f"border-radius: {'12px' if active_card else '8px'};"
            "}"
            "#BeamlineStatePill:hover {"
            f"background: {hover_background};"
            f"border: {border_width}px solid {hover_border};"
            "border-radius: 12px;"
            "}"
            "QWidget#beamline_state_header {"
            "background: transparent;"
            "}"
            "QWidget#beamline_state_stripe {"
            f"background-color: {accent};"
            "border-radius: 2px;"
            "}"
            "QLabel#beamline_state_icon {"
            f"background-color: {accent};"
            "border-radius: 16px;"
            "}"
            "QLabel#beamline_state_name {"
            f"color: {colors['foreground']};"
            "font-weight: 600;"
            "}"
            "QLabel#beamline_state_status {"
            f"color: {accent};"
            "font-weight: 700;"
            "font-size: 13px;"
            "}"
            "QLabel#beamline_state_detail {"
            f"color: {colors['muted']};"
            "font-size: 11px;"
            "}"
            "QToolButton#beamline_state_interlock {"
            "background: transparent;"
            "border: none;"
            "border-radius: 4px;"
            "padding: 2px;"
            "}"
            "QToolButton#beamline_state_interlock:hover {"
            f"background-color: {colors['button_hover']};"
            "}"
            "QWidget#beamline_state_settings {"
            "background: transparent;"
            f"border-top: 1px solid {colors['border']};"
            "}"
            '*[beamlineStateDirty="true"] {'
            f"background-color: {colors['dirty_background']};"
            f"border: 1px solid {colors['dirty_border']};"
            "border-radius: 4px;"
            "}"
            "QPushButton#beamline_state_remove_button {"
            "background-color: #cc181e;"
            "border: 1px solid #cc181e;"
            "color: white;"
            "border-radius: 4px;"
            "padding: 4px 10px;"
            "}"
            "QPushButton#beamline_state_remove_button:hover {"
            "background-color: #a91419;"
            "border-color: #a91419;"
            "}"
        )

    def _update_header_icons(self, colors: dict[str, str]) -> None:
        cache_key = (
            self._status,
            self._expanded,
            tuple(self._interlock_required_statuses or ()),
            self._interlock_required_statuses is not None,
            self._interlock_triggered,
            get_theme_name(),
        )
        if cache_key == self._header_icon_cache_key:
            return
        self._header_icon_cache_key = cache_key

        self._icon_label.setPixmap(
            material_icon(
                self._STATUS_ICONS[self._status],
                size=(20, 20),
                color=colors["on_accent"],
                filled=True,
            )
        )
        expand_icon = "expand_less" if self._expanded else "expand_more"
        self._expand_button.setIcon(
            material_icon(expand_icon, size=(20, 20), convert_to_pixmap=False)
        )
        if self._interlock_required_statuses is not None:
            lock_color = (
                colors["interlock_trigger"] if self._interlock_triggered else colors["foreground"]
            )
            self._interlock_button.setIcon(
                material_icon(
                    "lock", size=(18, 18), color=lock_color, filled=True, convert_to_pixmap=False
                )
            )
            self._interlock_button.setToolTip(
                "Watched by the scan interlock (accepted statuses: "
                f"{', '.join(self._interlock_required_statuses)}).\n"
                "Click to remove this state from the scan interlock."
            )
        else:
            self._interlock_button.setIcon(
                material_icon(
                    "lock_open_right", size=(18, 18), color=colors["muted"], convert_to_pixmap=False
                )
            )
            self._interlock_button.setToolTip(
                "Not watched by the scan interlock.\n"
                "Click to add this state to the scan interlock."
            )

    @staticmethod
    def _traveling_gradient(base: str, highlight: str, phase: float) -> str:
        """Return a horizontal QSS gradient with a highlight band centered at ``phase``."""
        span = 0.3
        center = phase * (1.0 + 2.0 * span) - span
        stops: list[tuple[float, str]] = [(0.0, base)]
        for position, color in ((center - span, base), (center, highlight), (center + span, base)):
            position = min(1.0, max(0.0, position))
            if position - stops[-1][0] > 0.001:
                stops.append((position, color))
        if 1.0 - stops[-1][0] > 0.001:
            stops.append((1.0, base))
        body = ", ".join(f"stop:{position:.4f} {color}" for position, color in stops)
        return f"qlineargradient(x1:0, y1:0, x2:1, y2:0, {body})"

    @SafeSlot()
    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def is_expanded(self) -> bool:
        """Return whether the editable settings panel is expanded."""
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """
        Set the editable settings panel expanded state.

        The settings form is built on demand when the panel expands and released again on
        collapse, so collapsed pills do not keep live device/signal widgets and their BEC
        subscriptions around. Unsaved edits are discarded on collapse.
        """

        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        if expanded:
            self._ensure_settings_form_current()
        self._expanded = expanded
        self._settings.setVisible(expanded)
        if not expanded:
            self._release_config_form()
        self._apply_visual_state()
        self.row_height_changed.emit()

    def _ensure_config_form(
        self, config_class: type[bl_states.BeamlineStateConfig] = bl_states.DeviceStateConfig
    ) -> PydanticWidgetForm:
        if self._config_form is None:
            self._config_form = PydanticWidgetForm(
                config_class, parent=self._settings, client=self.client, read_only_fields={"name"}
            )
            self._config_form.changed.connect(self._update_settings_dirty_state)
            self._config_form_host.addWidget(self._config_form)
        return self._config_form

    def _ensure_settings_form_current(self) -> PydanticWidgetForm:
        if self._settings_form_stale:
            self._populate_settings()
            self.mark_current_settings_clean()
        return self._ensure_config_form()

    def _release_config_form(self) -> None:
        if self._config_form is None:
            return
        self._config_form_host.removeWidget(self._config_form)
        self._config_form.cleanup()
        self._config_form.setParent(None)
        self._config_form.deleteLater()
        self._config_form = None
        self._settings_baseline = {}
        self._settings_form_stale = True
        self._update_settings_dirty_state()

    def _populate_settings(self) -> None:
        self._populating_settings = True
        try:
            state_type = self._state_config.state_type if self._state_config is not None else ""
            config_class = None
            for state_class in SUPPORTED_BEAMLINE_STATES:
                if state_type in {state_class.__name__, state_class.CONFIG_CLASS.state_type}:
                    config_class = state_class.CONFIG_CLASS
                    break
            if config_class is None:
                raise ValueError(f"Unsupported beamline state type '{state_type}'.")
            config_form = self._ensure_config_form(config_class)
            if config_form.model is not config_class:
                config_form.set_model(config_class)
            self._state_type_value.setText(state_type or "-")
            config_form.set_partial_data(self._state_data_for_form(config_class))
            self._settings_form_stale = False
        finally:
            self._populating_settings = False
            self._update_settings_dirty_state()

    def edited_config(self) -> bl_states.BeamlineStateConfig:
        """Return the validated config currently represented by the expanded settings panel."""
        config = self._ensure_settings_form_current().model_instance()
        return config  # type: ignore[return-value]

    def mark_current_settings_clean(self) -> None:
        """Mark the current editor values as saved."""
        config_form = self._ensure_config_form()
        self._settings_baseline = config_form.raw_editable_data()
        config_form.mark_clean()
        self._update_settings_dirty_state()

    @SafeSlot()
    def _revert_settings(self) -> None:
        self._populating_settings = True
        try:
            self._ensure_config_form().set_partial_data(self._settings_baseline)
        finally:
            self._populating_settings = False
            self._update_settings_dirty_state()

    def _update_settings_dirty_state(self) -> None:
        if self._populating_settings:
            return
        if self._config_form is None:
            self._settings_dirty_fields = set()
            self._update_button.setEnabled(False)
            self._revert_button.setEnabled(False)
            return

        self._settings_dirty_fields = self._config_form.dirty_fields() - {"name"}

        has_changes = bool(self._settings_dirty_fields)
        self._update_button.setEnabled(has_changes)
        self._revert_button.setEnabled(has_changes)
        self._apply_dirty_field_highlights()

    def _apply_dirty_field_highlights(self) -> None:
        if self._config_form is None:
            return
        for name, widget in self._config_form.widgets.items():
            self._set_dirty_property(widget, name in self._settings_dirty_fields)

    @staticmethod
    def _set_dirty_property(widget: QWidget, dirty: bool) -> None:
        widgets = [widget]
        if isinstance(widget, OptionalValueWidget):
            widgets.append(widget.value_widget)
            if widget.value_widget.parentWidget() is not None:
                widgets.append(widget.value_widget.parentWidget())
        for target in widgets:
            if target.property("beamlineStateDirty") == dirty:
                continue
            target.setProperty("beamlineStateDirty", dirty)
            target.style().unpolish(target)
            target.style().polish(target)
            target.update()

    @SafeSlot()
    def _emit_update_requested(self) -> None:
        if self._state_name is None:
            return
        if not self._settings_dirty_fields:
            return
        try:
            config = self.edited_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Beamline State", str(exc))
            return
        self.update_requested.emit(self._state_name, config)

    @SafeSlot()
    def _emit_remove_requested(self) -> None:
        if self._state_name is None:
            return
        self.remove_requested.emit(self._state_name)

    def _state_data_for_form(
        self, config_class: type[bl_states.BeamlineStateConfig]
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        parameters = self._state_config.parameters if self._state_config is not None else {}
        for name in config_class.model_fields:
            if name == "name":
                data[name] = self._state_name
            elif name in parameters:
                data[name] = parameters[name]
        return data

    @staticmethod
    def _state_colors(status: str) -> dict[str, str]:
        app = QApplication.instance()
        palette = app.palette() if app is not None else QPalette()
        theme = getattr(app, "theme", None) if app is not None else None
        light_theme = get_theme_name() == "light"
        accents = get_accent_colors()

        card_bg = theme_color(theme, "CARD_BG", palette.window().color())
        border = theme_color(theme, "BORDER", palette.mid().color())
        foreground = theme_color(theme, "FG", palette.text().color())
        on_primary = theme_color(theme, "ON_PRIMARY", QColor("#ffffff"))
        warning = accents.warning
        accent = {
            "valid": accents.success,
            "invalid": accents.emergency,
            "warning": warning,
            "unknown": accents.default,
        }.get(status, accents.default)

        gradient_alpha = 18 if light_theme else 62
        gradient_stop = "0.38" if light_theme else "0.62"
        background_mix = 0.0 if light_theme else 0.10
        card_border_mix = 0.34 if light_theme else 0.45
        border_mix = 0.34 if light_theme else 0.35

        return {
            "accent": accent.name(),
            "on_accent": on_primary.name(),
            "card_background": card_bg.name(),
            "card_border": Colors._blend(border, accent, card_border_mix).name(),
            "gradient_accent": rgba(accent, gradient_alpha),
            "gradient_stop": gradient_stop,
            "background": Colors._blend(card_bg, accent, background_mix).name(),
            "border": Colors._blend(border, accent, border_mix).name(),
            "dirty_background": Colors._blend(
                card_bg, warning, 0.12 if light_theme else 0.18
            ).name(),
            "dirty_border": Colors._blend(border, warning, 0.70).name(),
            "foreground": foreground.name(),
            "muted": Colors._blend(card_bg, foreground, 0.66).name(),
            "interlock_trigger": accents.emergency.name(),
            "interlock_band": rgba(accents.emergency, 64 if light_theme else 110),
            "button_hover": rgba(accent, 28 if light_theme else 48),
            "shadow": "#00000024" if light_theme else "#00000078",
            "shadow_blur": "24" if light_theme else "18",
            "shadow_y_offset": "3" if light_theme else "2",
        }

    def cleanup(self) -> None:
        self._interlock_animation.stop()
        if self._state_name is not None:
            self.bec_dispatcher.disconnect_slot(
                self.update_state, MessageEndpoints.beamline_state(self._state_name)
            )
        if self._config_form is not None:
            self._config_form.cleanup()
        super().cleanup()
