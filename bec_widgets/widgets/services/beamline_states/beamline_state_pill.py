from __future__ import annotations

import sys
from typing import Any

from bec_lib import bl_states
from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from pydantic import BaseModel
from qtpy.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, Signal
from qtpy.QtGui import QColor, QMouseEvent, QPalette
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListView,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors, get_accent_colors, get_theme_name, rgba, theme_color
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.forms_from_types.pydantic_widget_form import (
    OptionalValueWidget,
    PydanticWidgetForm,
)
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.services.beamline_states.dialogs import (
    BEAMLINE_STATE_STATUS_LABELS,
    SUPPORTED_BEAMLINE_STATES,
    AddBeamlineStateDialog,
    DeviceFilterDialog,
    StatusFilterDialog,
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
        title: str | None = None,
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
        self._state_name: str | None = None
        self._title: str | None = None
        self._state_config: dict[str, Any] = {}
        self._status = "unknown"
        self._label = "No state information available."
        self._expanded = False
        self._idle_card_background = False
        self._populating_settings = False
        self._settings_baseline: dict[str, Any] = {}
        self._settings_dirty_fields: set[str] = set()
        self._settings_form_stale = True

        self._init_ui(state_name, title)

    def _init_ui(self, state_name: str | None = None, title: str | None = None) -> None:
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
        self._name_label = QLabel(self)
        self._name_label.setObjectName("beamline_state_name")
        self._name_label.setTextFormat(Qt.TextFormat.PlainText)
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._status_label = QLabel(self)
        self._status_label.setObjectName("beamline_state_status")
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._detail_label = QLabel(self)
        self._detail_label.setObjectName("beamline_state_detail")
        self._detail_label.setTextFormat(Qt.TextFormat.PlainText)
        self._detail_label.setWordWrap(True)
        self._detail_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._expand_button = QToolButton(self)
        self._expand_button.setObjectName("beamline_state_expand")
        self._expand_button.setAutoRaise(True)
        self._expand_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_button.clicked.connect(self._toggle_expanded)

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

        settings_layout = QVBoxLayout(self._settings)
        settings_layout.setContentsMargins(12, 8, 12, 12)
        settings_layout.setSpacing(8)
        settings_layout.addLayout(self._settings_form)
        settings_layout.addLayout(self._config_form_host)
        settings_layout.addLayout(button_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._settings)
        self.setLayout(layout)

        self._settings.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.set_state_name(state_name, title=title)
        self._update_button.setEnabled(False)
        self._revert_button.setEnabled(False)

    @SafeProperty(str, default=None)
    def state_name(self) -> str | None:
        """Name of the BEC beamline state displayed by this pill."""
        return self._state_name

    @state_name.setter
    def state_name(self, state_name: str | None) -> None:
        self.set_state_name(state_name)

    def set_state_name(self, state_name: str | None, title: str | None = None) -> None:
        """
        Set the BEC beamline state this pill displays.

        Args:
            state_name: State name as published by ``AvailableBeamlineStatesMessage``.
            title: Optional human-readable title for the state.
        """
        if state_name == self._state_name and title == self._title:
            return

        if self._state_name is not None:
            self.bec_dispatcher.disconnect_slot(
                self.update_state, MessageEndpoints.beamline_state(self._state_name)
            )

        self._state_name = state_name
        self._title = title
        self._name_label.setText(title or state_name or "Beamline state")

        if self._state_name is None:
            self._set_visual_state("unknown", "No beamline state selected.")
            return

        self._set_visual_state("unknown", "No state information available.")
        self._refresh_latest_state()
        self.bec_dispatcher.connect_slot(
            self.update_state, MessageEndpoints.beamline_state(self._state_name)
        )

    def set_state_config(self, state_config: dict[str, Any]) -> None:
        """Set the editable BEC state configuration displayed by the expanded panel."""
        self._state_config = state_config
        self._settings_form_stale = True
        if self._config_form is not None:
            self._populate_settings()
            self._mark_settings_clean_from_current()

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
        on_accent = colors["on_accent"]
        active_card = self._expanded
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
        self._shadow.setColor(QColor(colors["shadow"]))
        self._shadow.setBlurRadius(int(colors["shadow_blur"]))
        self._shadow.setOffset(0, int(colors["shadow_y_offset"]))
        self._shadow.setEnabled(active_card)

        icon_name = self._STATUS_ICONS[self._status]
        self._icon_label.setPixmap(
            material_icon(icon_name, size=(20, 20), color=on_accent, filled=True)
        )
        expand_icon = "expand_less" if self._expanded else "expand_more"
        self._expand_button.setIcon(material_icon(expand_icon, convert_to_pixmap=False))
        self._status_label.setText(self._STATUS_LABELS[self._status])
        self._detail_label.setText(self._label)
        self.setToolTip(self._label)
        self.setStyleSheet(
            "#BeamlineStatePill {"
            f"background: {background};"
            f"border: 1px solid {border};"
            f"border-radius: {'12px' if active_card else '8px'};"
            "}"
            "#BeamlineStatePill:hover {"
            f"background: {hover_background};"
            f"border: 1px solid {colors['card_border']};"
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

    @SafeSlot()
    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def is_expanded(self) -> bool:
        """Return whether the editable settings panel is expanded."""
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Set the editable settings panel expanded state."""
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        if expanded:
            self._ensure_settings_form_current()
        self._expanded = expanded
        self._settings.setVisible(expanded)
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
            self._mark_settings_clean_from_current()
        return self._ensure_config_form()

    def _populate_settings(self) -> None:
        self._populating_settings = True
        try:
            state_type = str(self._state_config.get("state_type") or "")
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

    def mark_current_settings_clean(
        self, config: bl_states.BeamlineStateConfig | None = None
    ) -> None:
        """Mark the current editor values as saved."""
        if config is None:
            parameters = self._ensure_config_form().raw_editable_data()
        else:
            parameters = config.model_dump(exclude={"name"})
        if self._state_config:
            state_parameters = self._state_config.get("parameters")
            if isinstance(state_parameters, dict):
                state_parameters.update(parameters)
            else:
                self._state_config.update(parameters)
            if "title" in parameters:
                self._state_config["title"] = parameters["title"]
        self._mark_settings_clean_from_current()

    def _mark_settings_clean_from_current(self) -> None:
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
        parameters = self._state_config.get("parameters")
        parameter_values = parameters if isinstance(parameters, dict) else {}
        for name in config_class.model_fields:
            if name == "name":
                data[name] = self._state_name
            elif name in parameter_values:
                data[name] = parameter_values[name]
            elif name in self._state_config:
                data[name] = self._state_config[name]
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
            "shadow": "#00000024" if light_theme else "#00000078",
            "shadow_blur": "24" if light_theme else "18",
            "shadow_y_offset": "3" if light_theme else "2",
        }

    def cleanup(self) -> None:
        if self._state_name is not None:
            self.bec_dispatcher.disconnect_slot(
                self.update_state, MessageEndpoints.beamline_state(self._state_name)
            )
        if self._config_form is not None:
            self._config_form.cleanup()
        super().cleanup()


class _BeamlineStateListModel(QAbstractListModel):
    """Model owning beamline state row identity and configuration data."""

    NameRole = Qt.ItemDataRole.UserRole + 1
    ConfigRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state_order: list[str] = []
        self._state_rows: dict[str, int] = {}
        self._state_configs: dict[str, dict[str, Any]] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._state_order)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._state_order):
            return None
        name = self._state_order[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, self.NameRole):
            return name
        if role == self.ConfigRole:
            return self._state_configs.get(name, {})
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_states(self, state_configs: list[dict[str, Any]]) -> None:
        new_order = [str(state["name"]) for state in state_configs if state.get("name")]
        new_configs = {str(state["name"]): state for state in state_configs if state.get("name")}

        for row in reversed(
            [row for row, name in enumerate(self._state_order) if name not in new_configs]
        ):
            self.beginRemoveRows(QModelIndex(), row, row)
            name = self._state_order.pop(row)
            self._state_configs.pop(name, None)
            self.endRemoveRows()
        self._rebuild_rows()

        for target_row, name in enumerate(new_order):
            if name not in self._state_rows:
                self.beginInsertRows(QModelIndex(), target_row, target_row)
                self._state_order.insert(target_row, name)
                self._state_configs[name] = new_configs[name]
                self.endInsertRows()
                self._rebuild_rows()
                continue

            current_row = self._state_rows[name]
            if current_row != target_row:
                destination_row = target_row if current_row > target_row else target_row + 1
                self.beginMoveRows(
                    QModelIndex(), current_row, current_row, QModelIndex(), destination_row
                )
                self._state_order.insert(target_row, self._state_order.pop(current_row))
                self.endMoveRows()
                self._rebuild_rows()

            if self._state_configs.get(name) != new_configs[name]:
                self._state_configs[name] = new_configs[name]
                index = self.index(self._state_rows[name], 0)
                self.dataChanged.emit(index, index, [self.ConfigRole])

    def _rebuild_rows(self) -> None:
        self._state_rows = {name: row for row, name in enumerate(self._state_order)}

    def index_for_name(self, name: str) -> QModelIndex:
        row = self._state_rows.get(name)
        if row is None:
            return QModelIndex()
        return self.index(row, 0)


class _BeamlineStatePillDelegate(QStyledItemDelegate):
    """Delegate that provides BeamlineStatePill persistent editors for list rows."""

    def __init__(self, manager: "BeamlineStateManager") -> None:
        super().__init__(manager)
        self._manager = manager

    def paint(self, _painter, _option: QStyleOptionViewItem, _index: QModelIndex) -> None:
        return

    def createEditor(  # noqa: N802
        self, parent: QWidget, _option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        name = index.data(_BeamlineStateListModel.NameRole)
        state_config = index.data(_BeamlineStateListModel.ConfigRole) or {}
        title = state_config.get("title") or name
        pill = BeamlineStatePill(
            parent=parent, state_name=name, title=title, client=self._manager.client
        )
        pill.idle_card_background = self._manager.idle_card_background
        pill.set_state_config(state_config)
        pill.state_changed.connect(self._manager._on_pill_state_changed)
        pill.update_requested.connect(self._manager._update_state_parameters)
        pill.remove_requested.connect(self._manager._remove_state_requested)
        pill.row_height_changed.connect(lambda name=name: self._manager._sync_pill_item_size(name))
        self._manager._state_pills[str(name)] = pill
        return pill

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if not isinstance(editor, BeamlineStatePill):
            return
        name = index.data(_BeamlineStateListModel.NameRole)
        state_config = index.data(_BeamlineStateListModel.ConfigRole) or {}
        title = state_config.get("title") or name
        editor.set_state_name(str(name), title=str(title))
        editor.idle_card_background = self._manager.idle_card_background
        editor.set_state_config(state_config)

    def updateEditorGeometry(  # noqa: N802
        self, editor: QWidget, option: QStyleOptionViewItem, _index: QModelIndex
    ) -> None:
        editor.setGeometry(option.rect)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        name = index.data(_BeamlineStateListModel.NameRole)
        pill = self._manager._state_pills.get(str(name))
        if pill is not None:
            return pill.sizeHint()
        return QSize(120, 58)

    def destroyEditor(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, BeamlineStatePill):
            name = editor.state_name
            if name and self._manager._state_pills.get(name) is editor:
                self._manager._state_pills.pop(name, None)
            editor.cleanup()
        super().destroyEditor(editor, index)


class _BeamlineStateListView(QListView):
    """List view using persistent pill editors."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("beamline_state_pill_view")
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setSpacing(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "QListView#beamline_state_pill_view {"
            "background: transparent;"
            "border: none;"
            "}"
            "QListView#beamline_state_pill_view::item {"
            "background: transparent;"
            "border: none;"
            "padding: 0;"
            "}"
            "QListView#beamline_state_pill_view::item:selected {"
            "background: transparent;"
            "border: none;"
            "}"
        )


class BeamlineStateManager(BECWidget, QWidget):
    """
    Widget displaying and managing all BEC beamline states.

    The manager subscribes to ``MessageEndpoints.available_beamline_states()`` and creates,
    updates, or removes child ``BeamlineStatePill`` widgets as the set of configured states changes.
    """

    PLUGIN = True
    ICON_NAME = "format_list_bulleted"
    USER_ACCESS = [
        "idle_card_background",
        "set_idle_card_background",
        "clear_filters",
        "state_summary",
        "remove",
        "attach",
        "detach",
        "screenshot",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        idle_card_background: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(
            parent=parent, client=client, config=config, gui_id=gui_id, theme_update=True, **kwargs
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._state_pills: dict[str, BeamlineStatePill] = {}
        self._state_configs: dict[str, dict[str, Any]] = {}
        self._state_order: list[str] = []
        self._selected_statuses: set[str] | None = None
        self._selected_devices: set[str] | None = None
        self._device_filter_text = ""
        self._hidden_expanded = False
        self._idle_card_background = False
        self.idle_card_background = idle_card_background

        self._empty_label = QLabel(
            "No beamline states available.\n Add new state from toolbar or CLI.", self
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._toolbar = self._create_toolbar()
        self._model = _BeamlineStateListModel(self)
        self._view = _BeamlineStateListView(self)
        self._delegate = _BeamlineStatePillDelegate(self)
        self._view.setModel(self._model)
        self._view.setItemDelegate(self._delegate)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._empty_label)
        layout.addWidget(self._view, 1)
        self._hidden_summary = QToolButton(self)
        self._hidden_summary.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._hidden_summary.setCheckable(True)
        self._hidden_summary.toggled.connect(self._toggle_hidden_states)
        layout.addWidget(self._hidden_summary)
        self.setLayout(layout)

        self.bec_dispatcher.connect_slot(
            self.update_available_states, MessageEndpoints.available_beamline_states()
        )
        self.refresh_states()
        self._refresh_hidden_summary()

    @SafeProperty(bool, default=False)
    def idle_card_background(self) -> bool:
        """
        Whether idle collapsed pills keep the status-tinted card background.
        """
        return self._idle_card_background

    @idle_card_background.setter
    def idle_card_background(self, enabled: bool) -> None:
        self._idle_card_background = enabled
        for pill in self._state_pills.values():
            pill.idle_card_background = self._idle_card_background

    def set_idle_card_background(self, enabled: bool) -> None:
        """Set whether idle collapsed pills keep the status-tinted card background."""
        self.idle_card_background = enabled

    def _create_toolbar(self) -> ModularToolBar:
        toolbar = ModularToolBar(parent=self)

        add_state = MaterialIconAction("add", "Add beamline state", filled=True, parent=self)
        filter_states = MaterialIconAction(
            "filter_alt", "Filter displayed state status", filled=True, parent=self
        )
        filter_devices = MaterialIconAction(
            "devices", "Filter displayed devices", filled=True, parent=self
        )
        clear_filters = MaterialIconAction(
            "filter_alt_off", "Clear beamline state filters", filled=True, parent=self
        )

        add_state.action.triggered.connect(self.open_add_state_dialog)
        filter_states.action.triggered.connect(self.open_status_filter_dialog)
        filter_devices.action.triggered.connect(self.open_device_filter_dialog)
        clear_filters.action.triggered.connect(self.clear_filters)

        toolbar.components.add_safe("add_state", add_state)
        toolbar.components.add_safe("filter_states", filter_states)
        toolbar.components.add_safe("filter_devices", filter_devices)
        toolbar.components.add_safe("clear_filters", clear_filters)

        bundle = ToolbarBundle("beamline_state_manager", toolbar.components)
        bundle.add_action("add_state")
        bundle.add_action("filter_states")
        bundle.add_action("filter_devices")
        bundle.add_action("clear_filters")
        toolbar.add_bundle(bundle)
        toolbar.show_bundles(["beamline_state_manager"])
        return toolbar

    @SafeSlot(str)
    def apply_theme(self, _theme: str) -> None:
        colors = BeamlineStatePill._state_colors("unknown")
        self.setStyleSheet(
            "BeamlineStateManager { border: none; }"
            "QToolButton#hidden_states_summary {"
            f"background-color: {colors['background']};"
            f"border: 1px solid {colors['border']};"
            "border-radius: 6px;"
            "padding: 6px;"
            "text-align: left;"
            "}"
        )
        for pill in self._state_pills.values():
            pill.apply_theme(_theme)
        self._refresh_hidden_summary()

    @SafeSlot()
    def open_add_state_dialog(self) -> None:
        dialog = AddBeamlineStateDialog(self, client=self.client)
        config = None
        try:
            accepted = dialog.exec() == QDialog.Accepted
            if accepted:
                config = dialog.config_result
        finally:
            dialog.cleanup()
            dialog.deleteLater()

        if config is None:
            return
        try:
            self.client.beamline_states.add(config)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Add State", str(exc))

    @SafeSlot()
    def open_status_filter_dialog(self) -> None:
        dialog = StatusFilterDialog(self._selected_statuses, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._selected_statuses = dialog.selected_statuses()
        self._apply_filters()

    @SafeSlot()
    def open_device_filter_dialog(self) -> None:
        devices = sorted(
            {
                device
                for state in self._state_configs.values()
                if (device := self._state_device(state)) is not None
            }
        )
        dialog = DeviceFilterDialog(devices, self._selected_devices, self._device_filter_text, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._selected_devices = dialog.selected_devices()
        self._device_filter_text = dialog.filter_text()
        self._apply_filters()

    @SafeSlot()
    def clear_filters(self) -> None:
        self._selected_statuses = None
        self._selected_devices = None
        self._device_filter_text = ""
        self._hidden_expanded = False
        self._apply_filters()

    def state_summary(self) -> dict[str, dict[str, str]]:
        """
        Return the displayed beamline states with their current status and label.

        Returns:
            dict: Mapping of state name to a dictionary with ``status`` and ``label`` keys.
        """
        return {
            name: {"status": pill._status, "label": pill._label}
            for name, pill in self._state_pills.items()
        }

    @SafeSlot()
    def refresh_states(self) -> None:
        """Fetch the latest cached available beamline states and update the list immediately."""
        msg = self.client.connector.get_last(
            MessageEndpoints.available_beamline_states(), key="data"
        )
        if msg is not None:
            self.update_available_states(msg.content, msg.metadata)

    @SafeSlot(dict, dict)
    def update_available_states(
        self, content: dict[str, Any], _metadata: dict[str, Any] | None = None
    ) -> None:
        """Update the displayed pills from ``AvailableBeamlineStatesMessage`` content."""
        expanded_names = {name for name, pill in self._state_pills.items() if pill.is_expanded()}
        states = content.get("states", [])
        state_configs = [self._state_config_to_dict(state) for state in states]
        state_configs = [state for state in state_configs if state.get("name")]
        if state_configs == list(self._state_configs.values()):
            self._apply_filters()
            return
        self._state_configs = {str(state["name"]): state for state in state_configs}
        self._state_order = [str(state["name"]) for state in state_configs]
        self._model.set_states(state_configs)
        self._open_persistent_editors(expanded_names)
        self._apply_filters()

    def _open_persistent_editors(self, expanded_names: set[str] | None = None) -> None:
        expanded_names = expanded_names or set()
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            self._view.openPersistentEditor(index)
            name = str(index.data(_BeamlineStateListModel.NameRole))
            pill = self._state_pills.get(name)
            if pill is not None:
                pill.set_expanded(name in expanded_names)
                self._sync_pill_item_size(name)

    def _apply_filters(self) -> None:
        visible_names = []
        hidden_names = []
        for name in self._state_order:
            if self._is_state_visible(name):
                visible_names.append(name)
            else:
                hidden_names.append(name)

        visible_set = set(visible_names)
        show_hidden = self._hidden_expanded and bool(hidden_names)
        for row, name in enumerate(self._state_order):
            hidden_by_filter = name not in visible_set
            self._view.setRowHidden(row, hidden_by_filter and not show_hidden)
            self._sync_pill_item_size(name)
        self._empty_label.setVisible(
            not visible_names and not (self._hidden_expanded and hidden_names)
        )
        self._view.setVisible(bool(visible_names) or (self._hidden_expanded and bool(hidden_names)))
        self._refresh_hidden_summary(hidden_count=len(hidden_names))

    def _sync_pill_item_size(self, name: str) -> None:
        index = self._model.index_for_name(name)
        if not index.isValid():
            return
        self._model.dataChanged.emit(index, index, [Qt.ItemDataRole.SizeHintRole])
        self._view.update(index)

    def _is_state_visible(self, name: str) -> bool:
        pill = self._state_pills.get(name)
        if self._selected_statuses is not None and (
            pill is None or pill._status not in self._selected_statuses
        ):
            return False

        device = self._state_device(self._state_configs.get(name, {}))
        if self._selected_devices is not None and device not in self._selected_devices:
            return False

        tokens = [
            token.strip().casefold()
            for token in self._device_filter_text.split(",")
            if token.strip()
        ]
        if tokens:
            if device is None:
                return False
            device_lower = device.casefold()
            if not any(token in device_lower for token in tokens):
                return False
        return True

    @SafeSlot(str, str, str)
    def _on_pill_state_changed(self, _name: str, _status: str, _label: str) -> None:
        if self._selected_statuses is not None:
            self._apply_filters()

    @SafeSlot(str, object)
    def _update_state_parameters(
        self, state_name: str, config: bl_states.BeamlineStateConfig
    ) -> None:
        state_client = getattr(self.client.beamline_states, state_name, None)
        if state_client is None:
            QMessageBox.warning(
                self, "Cannot Update State", f"Beamline state '{state_name}' is not available."
            )
            return
        try:
            parameters = config.model_dump(exclude={"name"})
            state_client.update_parameters(**parameters)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Update State", str(exc))
            return
        pill = self._state_pills.get(state_name)
        if pill is not None:
            pill.mark_current_settings_clean(config)

    @SafeSlot(str)
    def _remove_state_requested(self, state_name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Remove Beamline State",
            f"Remove beamline state '{state_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.client.beamline_states.delete(state_name)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Remove State", str(exc))

    @SafeSlot(bool)
    def _toggle_hidden_states(self, checked: bool) -> None:
        self._hidden_expanded = bool(checked)
        self._apply_filters()

    def _refresh_hidden_summary(self, hidden_count: int | None = None) -> None:
        if hidden_count is None:
            hidden_count = sum(1 for name in self._state_order if not self._is_state_visible(name))
        self._hidden_summary.setObjectName("hidden_states_summary")
        self._hidden_summary.setVisible(hidden_count > 0)
        self._hidden_summary.setChecked(self._hidden_expanded and hidden_count > 0)
        icon_name = "expand_less" if self._hidden_expanded else "expand_more"
        self._hidden_summary.setIcon(material_icon(icon_name, convert_to_pixmap=False))
        suffix = "state is" if hidden_count == 1 else "states are"
        action = "Hide" if self._hidden_expanded else "Show"
        self._hidden_summary.setText(
            f"{hidden_count} {suffix} hidden by filters. {action} hidden states."
        )

    @staticmethod
    def _state_device(state: dict[str, Any]) -> str | None:
        parameters = state.get("parameters")
        if isinstance(parameters, dict):
            device = parameters.get("device")
        else:
            device = state.get("device")
        return str(device) if device else None

    @staticmethod
    def _state_config_to_dict(state: dict[str, Any] | BaseModel) -> dict[str, Any]:
        if isinstance(state, dict):
            return state
        state_dict = state.model_dump()
        state_type = getattr(state, "state_type", None)
        if state_type is not None:
            state_dict.setdefault("state_type", state_type)
        title = getattr(state, "title", None)
        if title is not None and not state_dict.get("title"):
            state_dict["title"] = title
        return state_dict

    def cleanup(self) -> None:
        self.bec_dispatcher.disconnect_slot(
            self.update_available_states, MessageEndpoints.available_beamline_states()
        )
        for row in range(self._model.rowCount()):
            self._view.closePersistentEditor(self._model.index(row, 0))
        for pill in list(self._state_pills.values()):
            pill.cleanup()
            pill.deleteLater()
        self._state_pills.clear()
        self._toolbar.components.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)

    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    apply_theme("dark")

    window = QWidget()
    window.setWindowTitle("Beamline States")
    layout = QVBoxLayout(window)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    theme_row = QHBoxLayout()
    theme_row.addStretch(1)
    theme_row.addWidget(DarkModeButton(parent=window))
    layout.addLayout(theme_row)

    manager = BeamlineStateManager(parent=window)
    idle_background = QCheckBox("Idle card background", window)
    idle_background.toggled.connect(
        lambda checked: setattr(manager, "idle_card_background", checked)
    )

    options_row = QHBoxLayout()
    options_row.addWidget(idle_background)
    options_row.addStretch(1)
    layout.addLayout(options_row)
    layout.addWidget(manager, 1)

    window.resize(760, 480)
    window.show()
    sys.exit(app.exec())
