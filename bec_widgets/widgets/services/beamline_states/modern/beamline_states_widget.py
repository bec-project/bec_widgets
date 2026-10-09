"""Beamline states view built from QWidgets, with the same UX as the QML version."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from bec_qthemes import material_icon
from qtpy.QtCore import Property, QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QIcon, QPainter, QPen
from qtpy.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.eliding_label import ElidingLabel
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.qml_host import QmlTheme
from bec_widgets.widgets.services.beamline_states.modern.actions import (
    open_add_dialog,
    open_edit_dialog,
)
from bec_widgets.widgets.services.beamline_states.modern.states_controller import (
    INTERLOCK_SECTION,
    STATUSES,
    BeamlineStatesController,
)
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch

STATUS_TITLES = {"invalid": "Invalid", "warning": "Warning", "unknown": "Unknown", "valid": "Valid"}
STATUS_ICONS = {
    "invalid": "cancel",
    "warning": "warning",
    "unknown": "help",
    "valid": "check_circle",
}


def _status_color(theme: QmlTheme, status: str) -> QColor:
    return {"invalid": theme.danger, "warning": theme.warning, "valid": theme.success}.get(
        status, theme.muted
    )


def _rgba(color: QColor, alpha: float) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {int(alpha * 255)})"


@lru_cache(maxsize=256)
def _cached_icon(name: str, color: str, size: int, filled: bool):
    return material_icon(name, size=(size, size), color=color, filled=filled)


def _icon(name: str, color: QColor, size: int = 18, filled: bool = True):
    return _cached_icon(name, color.name(), size, filled)


def _set_prop(widget: QWidget, name: str, value) -> None:
    """Set a dynamic property used by the stylesheet and re-polish only if it changed."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _card_stylesheet(theme: QmlTheme) -> str:
    """Stylesheet for the cards, set once on the top-level widget per theme."""
    hover = theme.card.lighter(108) if theme.dark else theme.card.darker(102)
    rules = [
        "QFrame#state_card {"
        f"background: {theme.card.name()}; border: 1px solid {theme.border.name()};"
        "border-left-width: 4px; border-radius: 8px; }",
        f"QFrame#state_card:hover {{ background: {hover.name()}; }}",
        f'QFrame#state_card[expanded="true"] {{ background: {hover.name()}; }}',
        "QLabel#card_name { font-size: 13px; font-weight: 600; }",
        "QLabel#device_chip {"
        f"background: {_rgba(theme.foreground, 0.08)}; color: {theme.muted.name()};"
        "border-radius: 4px; padding: 1px 6px; font-size: 10px; font-family: monospace; }",
        f"QLabel#muted {{ color: {theme.muted.name()}; font-size: 11px; }}",
        "QLabel#detail_value { font-size: 11px; font-family: monospace; }",
        "QLabel#status_badge { border-radius: 15px; }",
        "QLabel#status_chip {"
        "border-radius: 11px; padding: 0px 8px; font-size: 10px; font-weight: 700; }",
        f"QFrame#rule {{ background: {theme.border.name()}; }}",
        "QPushButton#danger_button {"
        f"background: transparent; color: {theme.danger.name()};"
        f"border: 1px solid {_rgba(theme.danger, 0.6)}; border-radius: 6px;"
        "padding: 5px 12px; font-weight: 600; }",
        f"QPushButton#danger_button:hover {{ background: {_rgba(theme.danger, 0.14)}; }}",
        'QPushButton#danger_button[solid="true"] {'
        f"background: {theme.danger.name()}; color: white; }}",
    ]
    for status in STATUSES:
        accent = _status_color(theme, status)
        rules += [
            f'QFrame#state_card[status="{status}"] {{ border-left-color: {accent.name()}; }}',
            f'QFrame#state_card[status="{status}"][expanded="true"] {{'
            f"border-color: {_rgba(accent, 0.6)}; border-left-color: {accent.name()}; }}",
            f'QLabel#status_badge[status="{status}"] {{ background: {_rgba(accent, 0.18)}; }}',
            f'QLabel#status_chip[status="{status}"] {{'
            f"background: {_rgba(accent, 0.18)}; color: {accent.name()}; }}",
        ]
    rules.append(
        'QFrame#state_card[triggered="true"] {'
        f"border-color: {theme.danger.name()}; border-left-color: {theme.danger.name()}; }}"
    )
    return "".join(rules)


class _Pulse(QFrame):
    """Frame that can draw a pulsing red outline (scan-blocking marker)."""

    def __init__(self, theme: QmlTheme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._phase = 0.0
        self._pulsing = False
        self._animation = QPropertyAnimation(self, b"pulse_phase", self)
        self._animation.setDuration(1400)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._animation.setLoopCount(-1)

    @Property(float)
    def pulse_phase(self) -> float:
        """Animation phase of the outline."""
        return self._phase

    @pulse_phase.setter
    def pulse_phase(self, phase: float) -> None:
        self._phase = phase
        self.update()

    def set_pulsing(self, pulsing: bool) -> None:
        """Start or stop the pulsing outline."""
        if pulsing == self._pulsing:
            return
        self._pulsing = pulsing
        if pulsing:
            self._animation.start()
        else:
            self._animation.stop()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self._pulsing:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._theme.danger)
        color.setAlphaF(0.25 + 0.75 * abs(1.0 - 2.0 * self._phase))
        painter.setPen(QPen(color, 2))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

    def cleanup(self) -> None:
        """Stop the animation."""
        self._animation.stop()


class _Chip(QAbstractButton):
    """Checkable status chip with a colored dot and a count."""

    def __init__(self, status: str, theme: QmlTheme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.status = status
        self._theme = theme
        self._count = 0
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.set_count(0)

    def set_count(self, count: int) -> None:
        """Set the number shown on the chip."""
        self._count = count
        self.setText(f"{count} {STATUS_TITLES[self.status]}")
        self.setToolTip(
            f"Stop filtering by {STATUS_TITLES[self.status]}"
            if self.isChecked()
            else f"Show only {STATUS_TITLES[self.status]} states"
        )
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 34, 28)

    def paintEvent(self, _event) -> None:  # noqa: N802
        theme = self._theme
        accent = _status_color(theme, self.status)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._count == 0 and not self.isChecked():
            painter.setOpacity(0.45)
        rect = self.rect().adjusted(0, 0, -1, -1)
        fill = QColor(Qt.GlobalColor.transparent)
        if self.isChecked():
            fill = QColor(accent)
            fill.setAlphaF(0.22)
        elif self.underMouse():
            fill = QColor(theme.foreground)
            fill.setAlphaF(0.08)
        painter.setBrush(fill)
        painter.setPen(QPen(accent if self.isChecked() else theme.border, 1))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(10, rect.height() // 2 - 3, 8, 8)
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(self.isChecked())
        painter.setFont(font)
        painter.setPen(theme.foreground)
        painter.drawText(rect.adjusted(24, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self.text())


class _InterlockBanner(_Pulse):
    """Banner showing whether the scan interlock is off, armed, or blocking scans."""

    arm_requested = Signal(bool)

    def __init__(self, theme: QmlTheme, parent: QWidget | None = None) -> None:
        super().__init__(theme, parent)
        self.setObjectName("interlock_banner")
        self.setMinimumHeight(52)
        self._style_key = None
        self._badge = QLabel(self)
        self._badge.setObjectName("banner_badge")
        self._badge.setFixedSize(30, 30)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title = ElidingLabel(self)
        self._title.setObjectName("banner_title")
        self._subtitle = ElidingLabel(self)
        self._subtitle.setObjectName("banner_subtitle")
        self._state = QLabel(self)
        self._state.setObjectName("muted")
        self.toggle = ToggleSwitch(self, checked=False)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.stateChanged.connect(self.arm_requested)

        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(self._title)
        text.addWidget(self._subtitle)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        layout.addWidget(self._badge)
        layout.addLayout(text, 1)
        layout.addWidget(self._state)
        layout.addWidget(self.toggle)

    def update_from(self, controller: BeamlineStatesController) -> None:
        """Refresh the banner from the controller state."""
        theme = self._theme
        armed = controller.interlockArmed
        blocking = controller.blockingStates
        watched = controller.watchedCount
        tripped = armed and bool(blocking)
        accent = theme.danger if tripped else (theme.success if armed else theme.muted)
        if tripped:
            title = "Scans are blocked by the scan interlock"
            subtitle = "Blocking: " + ", ".join(blocking)
        elif armed:
            title = "Scan interlock armed, scans can run"
            subtitle = f"{watched} {'state is' if watched == 1 else 'states are'} watched."
        else:
            title = "Scan interlock is off"
            subtitle = (
                "No states are watched. Use the lock on a state to watch it."
                if watched == 0
                else f"{watched} {'state is' if watched == 1 else 'states are'} watched. "
                "Arm the interlock to block scans when they fail."
            )
        self._title.setText(title)
        self._subtitle.setText(subtitle)
        self._state.setText("Armed" if armed else "Off")
        self.toggle.blockSignals(True)
        self.toggle.active_track_color = theme.danger if tripped else theme.success
        self.toggle.setChecked(armed)
        self.toggle.blockSignals(False)
        style_key = (armed, tripped, accent.name(), theme.muted.name())
        if style_key != self._style_key:
            self._style_key = style_key
            icon_name = "block" if tripped else ("lock" if armed else "lock_open_right")
            self._badge.setPixmap(_icon(icon_name, accent))
            self.setStyleSheet(
                "QFrame#interlock_banner {"
                f"background: {_rgba(accent, 0.16 if armed else 0.08)};"
                f"border: 1px solid {_rgba(accent, 0.9 if tripped else 0.45)};"
                "border-radius: 8px; }"
                f"QLabel#banner_badge {{ background: {_rgba(accent, 0.22)}; border-radius: 15px; }}"
                "QLabel#banner_title { font-size: 13px; font-weight: 600; }"
                f"QLabel#banner_subtitle {{ font-size: 11px; color: "
                f"{(theme.danger if tripped else theme.muted).name()}; }}"
                f"QLabel#muted {{ color: {theme.muted.name()}; }}"
            )
        self.set_pulsing(tripped)


class _StateCard(_Pulse):
    """One beamline state: header row plus an expandable details panel."""

    expand_toggled = Signal(str)

    def __init__(
        self, name: str, controller: BeamlineStatesController, theme: QmlTheme, parent=None
    ) -> None:
        super().__init__(theme, parent)
        self.name = name
        self._controller = controller
        self._row: dict[str, Any] = {}
        self._expanded = False
        self.setObjectName("state_card")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._header = QWidget(self)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.mousePressEvent = self._header_clicked
        self._badge = QLabel(self._header)
        self._badge.setObjectName("status_badge")
        self._badge.setFixedSize(30, 30)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name = QLabel(name, self._header)
        self._name.setObjectName("card_name")
        self._device = QLabel(self._header)
        self._device.setObjectName("device_chip")
        self._label = ElidingLabel(self._header)
        self._label.setObjectName("muted")
        self._status = QLabel(self._header)
        self._status.setObjectName("status_chip")
        self._status.setFixedHeight(22)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lock = QToolButton(self._header)
        self._lock.setAutoRaise(True)
        self._lock.setIconSize(QSize(18, 18))
        self._lock.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lock.clicked.connect(lambda: controller.toggleWatched(self.name))
        self._chevron = QLabel(self._header)
        for child in (self._badge, self._name, self._device, self._label, self._status):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        title = QHBoxLayout()
        title.setSpacing(6)
        title.addWidget(self._name)
        title.addWidget(self._device)
        title.addStretch(1)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addLayout(title)
        text.addWidget(self._label)
        header = QHBoxLayout(self._header)
        header.setContentsMargins(14, 8, 8, 8)
        header.setSpacing(10)
        header.addWidget(self._badge)
        header.addLayout(text, 1)
        header.addWidget(self._status)
        header.addWidget(self._lock)
        header.addWidget(self._chevron)

        self._body = QWidget(self)
        self._body.setObjectName("card_body")
        self._body.setVisible(False)
        self._details = QGridLayout()
        self._details.setHorizontalSpacing(14)
        self._details.setVerticalSpacing(4)
        self._details.setColumnStretch(1, 1)
        self._warning_toggle = ToggleSwitch(self._body, checked=False)
        self._warning_toggle.stateChanged.connect(
            lambda value: controller.setTriggerOnWarning(self.name, bool(value))
        )
        self._warning_label = QLabel(self._body)
        warning_row = QHBoxLayout()
        warning_row.setSpacing(8)
        warning_row.addWidget(self._warning_toggle)
        warning_row.addWidget(self._warning_label, 1)
        self._edit = QPushButton("Edit parameters", self._body)
        self._edit.setObjectName("outline_button")
        self._edit.clicked.connect(lambda: controller.requestEdit(self.name))
        self._remove = QPushButton("Remove", self._body)
        self._remove.setObjectName("danger_button")
        self._remove.clicked.connect(self._remove_clicked)
        self._confirm_timer = QTimer(self)
        self._confirm_timer.setSingleShot(True)
        self._confirm_timer.setInterval(3000)
        self._confirm_timer.timeout.connect(lambda: self._set_confirming(False))
        buttons = QHBoxLayout()
        buttons.addWidget(self._edit)
        buttons.addStretch(1)
        buttons.addWidget(self._remove)
        rule = QFrame(self._body)
        rule.setObjectName("rule")
        rule.setFixedHeight(1)
        body = QVBoxLayout(self._body)
        body.setContentsMargins(14, 0, 14, 10)
        body.setSpacing(8)
        body.addWidget(rule)
        body.addLayout(self._details)
        body.addLayout(warning_row)
        body.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._body)
        self._confirming = False

    def _header_clicked(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.expand_toggled.emit(self.name)

    def is_expanded(self) -> bool:
        """Whether the details panel is open."""
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Open or close the details panel."""
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._body.setVisible(expanded)
        self._set_confirming(False)
        self._apply_style()

    def _remove_clicked(self) -> None:
        if self._confirming:
            self._set_confirming(False)
            self._controller.removeState(self.name)
        else:
            self._set_confirming(True)
            self._confirm_timer.start()

    def _set_confirming(self, confirming: bool) -> None:
        self._confirming = confirming
        self._remove.setText("Click again to remove" if confirming else "Remove")
        _set_prop(self._remove, "solid", confirming)
        self._apply_style()

    def update_row(self, row: dict[str, Any]) -> None:
        """Show the data of a controller row."""
        if row == self._row:
            return
        details_changed = row.get("details") != self._row.get("details") or row.get(
            "stateType"
        ) != self._row.get("stateType")
        self._row = row
        self._device.setText(row["device"])
        self._device.setVisible(bool(row["device"]))
        self._label.setText(row["label"])
        self.setToolTip(row["label"])
        self._status.setText(row["statusText"])
        self._lock.setToolTip(
            f"Watched by the scan interlock (accepts {row['accepted']}). Click to stop watching."
            if row["watched"]
            else "Not watched by the scan interlock. Click to watch this state."
        )
        self._warning_toggle.blockSignals(True)
        self._warning_toggle.setChecked(row["triggerOnWarning"])
        self._warning_toggle.blockSignals(False)
        self._warning_label.setText(
            "Block scans on WARNING too" + ("" if row["watched"] else " (applies once watched)")
        )
        if details_changed:
            self._fill_details()
        self.set_pulsing(row["triggered"])
        self._apply_style()

    def _fill_details(self) -> None:
        while self._details.count():
            item = self._details.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        pairs = [("Type", self._row["stateType"])] + [
            (d["key"], d["value"]) for d in self._row["details"]
        ]
        for i, (key, value) in enumerate(pairs):
            key_label = QLabel(key, self._body)
            key_label.setObjectName("muted")
            value_label = QLabel(value, self._body)
            value_label.setObjectName("detail_value" if i else "")
            self._details.addWidget(key_label, i, 0)
            self._details.addWidget(value_label, i, 1)

    def apply_theme(self) -> None:
        """Re-apply theme colors."""
        self._apply_style()

    def _apply_style(self) -> None:
        if not self._row:
            return
        theme = self._theme
        row = self._row
        accent = _status_color(theme, row["status"])
        for widget in (self, self._badge, self._status):
            _set_prop(widget, "status", row["status"])
        _set_prop(self, "expanded", self._expanded)
        _set_prop(self, "triggered", row["triggered"])
        lock_color = (
            theme.danger
            if row["triggered"]
            else (theme.foreground if row["watched"] else theme.muted)
        )
        self._badge.setPixmap(_icon(STATUS_ICONS[row["status"]], accent))
        self._lock.setIcon(
            QIcon(
                _icon(
                    "lock" if row["watched"] else "lock_open_right", lock_color, 18, row["watched"]
                )
            )
        )
        self._chevron.setPixmap(
            _icon("expand_less" if self._expanded else "expand_more", theme.muted)
        )
        self._edit.setIcon(QIcon(_icon("edit", theme.primary, 16)))
        self._remove.setIcon(
            QIcon(_icon("delete", QColor("#ffffff") if self._confirming else theme.danger, 16))
        )


class _SectionHeader(QWidget):
    """Small caps section title above the watched / not watched groups."""

    def __init__(self, section: str, theme: QmlTheme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._section = section
        self._theme = theme
        self._icon = QLabel(self)
        self._text = QLabel(
            "WATCHED BY SCAN INTERLOCK" if section == INTERLOCK_SECTION else "NOT WATCHED", self
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 8, 0, 2)
        layout.setSpacing(6)
        layout.addWidget(self._icon)
        layout.addWidget(self._text, 1)
        self.apply_theme()

    def apply_theme(self) -> None:
        """Re-apply theme colors."""
        name = "lock" if self._section == INTERLOCK_SECTION else "lock_open_right"
        self._icon.setPixmap(_icon(name, self._theme.muted, 14))
        self._text.setStyleSheet(
            f"color: {self._theme.muted.name()}; font-size: 10px; font-weight: 700;"
            "letter-spacing: 0.6px;"
        )


class BeamlineStatesWidget(BECWidget, QWidget):
    """
    Beamline states with the scan interlock, built from QWidgets.

    Same UX as :class:`BeamlineStatesQML`, for comparison with the QML version and the original
    ``BeamlineStateManager``.
    """

    PLUGIN = False
    RPC = False
    ICON_NAME = "format_list_bulleted"
    USER_ACCESS = ["clear_filters", "collapse_all", "state_summary", "remove", "attach", "detach"]

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self.setObjectName("beamline_states_widget")
        self.theme = QmlTheme(self)
        self._cards: dict[str, _StateCard] = {}
        self._expanded: set[str] = set()

        # Summary chips, search and add.
        self._chips = {status: _Chip(status, self.theme, self) for status in STATUSES}
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search name or device")
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumWidth(150)
        self._search_action = self._search.addAction(
            material_icon("search", size=(16, 16)), QLineEdit.ActionPosition.LeadingPosition
        )
        self._add = QPushButton("Add state", self)
        self._add.setObjectName("primary_button")
        self._add.setCursor(Qt.CursorShape.PointingHandCursor)
        top = QHBoxLayout()
        top.setSpacing(6)
        for chip in self._chips.values():
            top.addWidget(chip)
        top.addWidget(self._search, 1)
        top.addWidget(self._add)

        self._banner = _InterlockBanner(self.theme, self)

        # Scrollable list of section headers and cards.
        self._list = QWidget()
        self._list.setObjectName("states_list")
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        self._sections = {
            section: _SectionHeader(section, self.theme, self._list)
            for section in (INTERLOCK_SECTION, "others")
        }
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._list)

        self._footer = QWidget(self)
        self._hidden_label = QLabel(self._footer)
        self._show_hidden = QPushButton(self._footer)
        self._show_hidden.setObjectName("outline_button")
        self._clear = QPushButton("Clear filters", self._footer)
        self._clear.setObjectName("outline_button")
        footer = QHBoxLayout(self._footer)
        footer.setContentsMargins(0, 2, 0, 2)
        footer.addStretch(1)
        footer.addWidget(self._hidden_label)
        footer.addWidget(self._show_hidden)
        footer.addWidget(self._clear)
        footer.addStretch(1)

        self._empty = QWidget(self)
        self._empty_icon = QLabel(self._empty)
        self._empty_title = QLabel(self._empty)
        self._empty_title.setObjectName("empty_title")
        self._empty_text = QLabel(self._empty)
        self._empty_text.setObjectName("muted")
        self._empty_button = QPushButton(self._empty)
        empty = QVBoxLayout(self._empty)
        empty.addStretch(1)
        for child in (self._empty_icon, self._empty_title, self._empty_text, self._empty_button):
            empty.addWidget(child, 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self._banner)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._empty, 1)
        layout.addWidget(self._footer)

        self.controller = BeamlineStatesController(self.client, self.bec_dispatcher, self)
        self.controller.changed.connect(self._sync)
        self.controller.error_occurred.connect(self._show_error)
        self.controller.add_requested.connect(self._open_add_dialog)
        self.controller.edit_requested.connect(self._open_edit_dialog)
        for chip in self._chips.values():
            chip.clicked.connect(
                lambda _checked=False, s=chip.status: self.controller.toggleStatusFilter(s)
            )
        self._search.textEdited.connect(self.controller.setSearchText)
        self._add.clicked.connect(self.controller.requestAdd)
        self._banner.arm_requested.connect(self.controller.setInterlockArmed)
        self._show_hidden.clicked.connect(
            lambda: self.controller.setShowFiltered(not self.controller.showFiltered)
        )
        self._clear.clicked.connect(self.controller.clearFilters)
        self._empty_button.clicked.connect(self._empty_action)
        self.theme.changed.connect(self._restyle)
        self._restyle()

    # ------------------------------------------------------------------ rendering

    @SafeSlot()
    def _sync(self) -> None:
        controller = self.controller
        rows = controller.model.rows()
        names = {row["name"] for row in rows}
        for name in list(self._cards):
            if name not in names:
                card = self._cards.pop(name)
                card.cleanup()
                card.deleteLater()
                self._expanded.discard(name)

        # Re-insert headers and cards in display order; widgets that keep their slot do not move.
        wanted: list[QWidget] = []
        section = None
        for row in rows:
            if row["section"] != section:
                section = row["section"]
                wanted.append(self._sections[section])
            card = self._cards.get(row["name"])
            if card is None:
                card = _StateCard(row["name"], controller, self.theme, self._list)
                card.expand_toggled.connect(self._toggle_expanded)
                self._cards[row["name"]] = card
            card.update_row(row)
            card.set_expanded(row["name"] in self._expanded)
            wanted.append(card)
        for i, widget in enumerate(wanted):
            if self._list_layout.indexOf(widget) != i:
                self._list_layout.removeWidget(widget)
                self._list_layout.insertWidget(i, widget)
            widget.show()
        for header in self._sections.values():
            if header not in wanted:
                self._list_layout.removeWidget(header)
                header.hide()
        for row in rows:
            self._set_dimmed(self._cards[row["name"]], row["filteredOut"])

        counts = controller.counts
        filters = set(controller.statusFilter)
        for status, chip in self._chips.items():
            chip.setChecked(status in filters)
            chip.set_count(counts[status])
        if self._search.text() != controller.searchText:
            self._search.setText(controller.searchText)
        self._banner.update_from(controller)

        hidden = controller.hiddenCount
        has_rows = bool(rows)
        self._scroll.setVisible(has_rows)
        self._empty.setVisible(not has_rows)
        self._footer.setVisible(has_rows and hidden > 0)
        self._hidden_label.setText(
            f"{hidden} {'state' if hidden == 1 else 'states'} hidden by filters"
        )
        self._show_hidden.setText("Hide them" if controller.showFiltered else "Show them")
        no_states = controller.totalCount == 0
        self._empty_icon.setPixmap(
            _icon("playlist_add" if no_states else "filter_alt_off", self.theme.muted, 36)
        )
        self._empty_title.setText(
            "No beamline states yet" if no_states else "No states match the filters"
        )
        self._empty_text.setText(
            "States check conditions such as a motor within limits."
            if no_states
            else f"{hidden} states are hidden."
        )
        self._empty_button.setText("Add state" if no_states else "Clear filters")
        self._empty_button.setObjectName("primary_button" if no_states else "outline_button")
        self._empty_button.style().unpolish(self._empty_button)
        self._empty_button.style().polish(self._empty_button)

    @staticmethod
    def _set_dimmed(card: _StateCard, dimmed: bool) -> None:
        # Opacity effects are costly, so only filtered-out cards get one.
        if dimmed == (card.graphicsEffect() is not None):
            return
        if dimmed:
            effect = QGraphicsOpacityEffect(card)
            effect.setOpacity(0.5)
            card.setGraphicsEffect(effect)
        else:
            card.setGraphicsEffect(None)

    @SafeSlot(str)
    def _toggle_expanded(self, name: str) -> None:
        self._expanded ^= {name}
        card = self._cards.get(name)
        if card is not None:
            card.set_expanded(name in self._expanded)

    @SafeSlot()
    def _restyle(self) -> None:
        theme = self.theme
        self._search_action.setIcon(
            material_icon("search", size=(16, 16), color=theme.muted.name())
        )
        self._add.setIcon(material_icon("add", size=(16, 16), color=theme.onPrimary.name()))
        self.setStyleSheet(
            f"QWidget#beamline_states_widget {{ background: {theme.background.name()}; }}"
            "QWidget#states_list { background: transparent; }"
            "QLineEdit { border-radius: 6px; padding: 4px 6px; min-height: 18px; }"
            "QPushButton#primary_button {"
            f"background: {theme.primary.name()}; color: {theme.onPrimary.name()};"
            "border: none; border-radius: 6px; padding: 5px 12px; font-weight: 600; }"
            "QPushButton#primary_button:hover {"
            f"background: {theme.primary.darker(112).name()}; }}"
            "QPushButton#outline_button {"
            f"background: transparent; color: {theme.primary.name()};"
            f"border: 1px solid {_rgba(theme.primary, 0.6)}; border-radius: 6px;"
            "padding: 5px 12px; font-weight: 600; }"
            "QLabel#empty_title { font-size: 13px; font-weight: 600; }"
            f"QLabel#muted {{ color: {theme.muted.name()}; font-size: 11px; }}"
            + _card_stylesheet(theme)
        )
        for header in self._sections.values():
            header.apply_theme()
        for card in self._cards.values():
            card.apply_theme()
        self._sync()

    @SafeSlot()
    def _empty_action(self) -> None:
        if self.controller.totalCount == 0:
            self.controller.requestAdd()
        else:
            self.controller.clearFilters()

    # ------------------------------------------------------------------ public API

    @SafeSlot()
    def clear_filters(self) -> None:
        """Reset the status chips and the search text."""
        self.controller.clearFilters()

    @SafeSlot()
    def collapse_all(self) -> None:
        """Collapse every expanded state."""
        self._expanded.clear()
        for card in self._cards.values():
            card.set_expanded(False)

    def state_summary(self) -> dict[str, dict[str, str]]:
        """
        Return all beamline states (including filtered ones) with their current status and label.

        Returns:
            dict: Mapping of state name to a dictionary with ``status`` and ``label`` keys.
        """
        return self.controller.state_summary()

    @SafeSlot(str, str)
    def _show_error(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    @SafeSlot()
    def _open_add_dialog(self) -> None:
        open_add_dialog(self, self.controller)

    @SafeSlot(str)
    def _open_edit_dialog(self, name: str) -> None:
        open_edit_dialog(self, self.controller, name)

    def cleanup(self) -> None:
        self.controller.cleanup()
        self._banner.cleanup()
        for card in self._cards.values():
            card.cleanup()
        super().cleanup()
