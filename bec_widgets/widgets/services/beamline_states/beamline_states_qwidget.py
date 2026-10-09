"""Beamline state manager with the modernised UX in plain QWidgets.

This is the QWidget twin of :class:`BeamlineStatesQML`, built from the same view state so both
rendering stacks can be compared side by side. It keeps the public API of
:class:`BeamlineStateManager`.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, Signal
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.eliding_label import ElidingLabel
from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import (
    Card,
    IconButton,
    StatusPill,
    TextButton,
    ToggleSwitch,
    field_qss,
    refresh_kit_theme,
    rgba,
)
from bec_widgets.widgets.services.beamline_states.beamline_states_ux_common import (
    BeamlineStatesPortBase,
)

PLAIN = "background: none; border: none;"


def tone_color(tone: str, tokens: ThemeTokens) -> QColor:
    """Colour of a tone name used in the view state."""
    return {
        "primary": tokens.primary,
        "success": tokens.success,
        "warning": tokens.warning,
        "danger": tokens.danger,
    }.get(tone, tokens.fg_muted)


def alpha(color: QColor, value: float) -> QColor:
    """Copy of ``color`` with alpha ``value`` (0..1)."""
    result = QColor(color)
    result.setAlphaF(max(0.0, min(1.0, value)))
    return result


def icon_label(parent: QWidget, size: int = 18) -> QLabel:
    """Transparent label sized for a Material icon pixmap."""
    label = QLabel(parent)
    label.setFixedSize(size, size)
    label.setStyleSheet(PLAIN)
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return label


def set_icon(label: QLabel, name: str, color: QColor, size: int = 18, filled: bool = False):
    """Show a tinted Material icon in ``label``."""
    label.setPixmap(material_icon(name, size=(size, size), color=color, filled=filled))


class StatusChip(QPushButton):
    """Status count that toggles a status filter, matching the QML chip."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(24)
        self._tone = QColor("#808080")
        self._active = False
        self._fg = QColor("#808080")
        self.status = ""

    def set_chip(self, chip: dict, tokens: ThemeTokens) -> None:
        """Update text, colour and the active state from a view-state chip."""
        self.status = chip["status"]
        self._tone = tone_color(chip["tone"], tokens)
        self._active = chip["active"]
        self.setText(chip["text"])
        self.setAccessibleName(f"Show only {self.status} states")
        self.setToolTip(
            "Click to stop filtering by this status"
            if self._active
            else "Click to show only this status"
        )
        font = self.font()
        font.setPixelSize(12)
        font.setBold(self._active)
        self.setFont(font)
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(chip["text"]) + 30)
        self._fg = tokens.fg if self._active else tokens.fg_muted
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = (
            alpha(self._tone, 0.28)
            if self._active
            else alpha(self._tone, 0.16) if self.underMouse() else QColor(0, 0, 0, 0)
        )
        painter.setPen(QPen(self._tone if self._active else alpha(self._tone, 0.45), 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._tone)
        painter.drawEllipse(QRectF(10, rect.height() / 2 - 3, 7, 7))
        painter.setPen(self._fg)
        painter.setFont(self.font())
        painter.drawText(rect.adjusted(22, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self.text())
        painter.end()

    def enterEvent(self, event):  # pylint: disable=invalid-name
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        super().leaveEvent(event)
        self.update()


class SectionHeader(QWidget):
    """Lock icon, section title with count and a rule line."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(26)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(6)
        self.icon = icon_label(self, 14)
        self.title = QLabel(self)
        self.rule = QFrame(self)
        self.rule.setFixedHeight(1)
        self.rule.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.icon)
        layout.addWidget(self.title)
        layout.addWidget(self.rule, 1, Qt.AlignmentFlag.AlignVCenter)

    def set_row(self, row: dict, tokens: ThemeTokens) -> None:
        """Update from a header row of the view state."""
        armed = bool(row["armed"])
        color = tokens.fg if armed else tokens.fg_muted
        set_icon(
            self.icon, "lock" if row["name"] == "interlock" else "lock_open_right", color, 14, armed
        )
        self.title.setText(f"{row['title']}  ·  {row['count']}")
        self.title.setStyleSheet(
            f"color: {color.name()}; font-size: 11px; font-weight: 700; {PLAIN}"
        )
        self.rule.setStyleSheet(f"background: {tokens.border.name()}; border: none;")


class _ClickableHeader(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def enterEvent(self, event):  # pylint: disable=invalid-name
        super().enterEvent(event)
        self.parentWidget().update()

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        super().leaveEvent(event)
        self.parentWidget().update()


class StateRow(QFrame):
    """One beamline state: status, label, interlock lock and expandable details."""

    def __init__(self, manager: "BeamlineStatesQWidget", parent: QWidget | None = None):
        super().__init__(parent)
        self._manager = manager
        self.row: dict = {}
        self._flash = 0.0
        self._flash_animation = QVariantAnimation(self)
        self._flash_animation.setDuration(1400)
        self._flash_animation.setKeyValueAt(0.0, 0.0)
        self._flash_animation.setKeyValueAt(0.5, 1.0)
        self._flash_animation.setKeyValueAt(1.0, 0.0)
        self._flash_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._flash_animation.setLoopCount(-1)
        self._flash_animation.valueChanged.connect(self._on_flash)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = _ClickableHeader(self)
        self.header.setFixedHeight(52)
        self.header.clicked.connect(lambda: self._manager.toggle_expanded(self.row["name"]))
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 0, 4, 0)
        header_layout.setSpacing(10)
        self.icon = icon_label(self.header, 30)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        self.name_label = ElidingLabel(self.header)
        self.detail_label = ElidingLabel(self.header)
        for label in (self.name_label, self.detail_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_layout.addStretch(1)
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.detail_label)
        text_layout.addStretch(1)
        self.status_pill = StatusPill(self.header)
        self.lock_button = IconButton("lock_open_right", "", self.header)
        self.lock_button.clicked.connect(
            lambda: self._manager.toggle_interlock_for(self.row["name"])
        )
        self.expand_icon = icon_label(self.header)
        header_layout.addWidget(self.icon)
        header_layout.addLayout(text_layout, 1)
        header_layout.addWidget(self.status_pill)
        header_layout.addWidget(self.lock_button)
        header_layout.addWidget(self.expand_icon)
        layout.addWidget(self.header)

        self.details = QWidget(self)
        self.details.setStyleSheet("background: none;")
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(50, 0, 12, 12)
        details_layout.setSpacing(8)
        self.params = QGridLayout()
        self.params.setHorizontalSpacing(14)
        self.params.setVerticalSpacing(3)
        details_layout.addLayout(self.params)
        warning_row = QHBoxLayout()
        warning_row.setSpacing(0)
        self.trip_switch = ToggleSwitch(self.details)
        self.trip_switch.setFixedWidth(46)
        self.trip_switch.setAccessibleName("WARNING trips the scan interlock")
        self.trip_switch.clicked.connect(
            lambda checked: self._manager.set_trip_on_warning(self.row["name"], checked)
        )
        self.trip_label = QLabel("WARNING trips the scan interlock", self.details)
        warning_row.addWidget(self.trip_switch)
        warning_row.addWidget(self.trip_label)
        warning_row.addStretch(1)
        details_layout.addLayout(warning_row)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.edit_button = TextButton("Edit…", "neutral", "edit", self.details)
        self.edit_button.clicked.connect(lambda: self._manager.edit_state(self.row["name"]))
        self.remove_button = TextButton("Remove", "ghost", "delete", self.details)
        self.remove_button.clicked.connect(lambda: self._manager.remove_state(self.row["name"]))
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        details_layout.addLayout(buttons)
        layout.addWidget(self.details)
        self._param_labels: list[QLabel] = []

    def set_row(self, row: dict, tokens: ThemeTokens) -> None:
        """Update from a state row of the view state."""
        previous = self.row
        self.row = row
        tone = tone_color(row["tone"], tokens)
        if (previous.get("icon"), previous.get("tone"), previous.get("_theme")) != (
            row["icon"],
            row["tone"],
            tokens.name,
        ):
            set_icon(self.icon, row["icon"], tone, 18, True)
            self.icon.setStyleSheet(
                f"background: {rgba(tone, 0.18)}; border: none; border-radius: 15px;"
            )
        row["_theme"] = tokens.name
        self.name_label.setText(row["name"])
        self.detail_label.setText(row["label"])
        self.setToolTip(row["label"])
        self.name_label.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 13px; font-weight: 600; {PLAIN}"
        )
        self.detail_label.setStyleSheet(
            f"color: {tokens.fg_muted.name()}; font-size: 11px; {PLAIN}"
        )
        self.status_pill.set_status(row["statusText"], tone)

        watched = row["watched"]
        self.lock_button.set_icon_name("lock" if watched else "lock_open_right")
        lock_color = tokens.danger if row["tripped"] else tokens.fg if watched else tokens.fg_subtle
        self.lock_button.setIcon(
            material_icon(
                "lock" if watched else "lock_open_right",
                size=(48, 48),
                color=lock_color,
                convert_to_pixmap=False,
            )
        )
        tip = (
            f"Watched by the scan interlock (accepts {row['acceptedText']}). "
            "Click to stop watching."
            if watched
            else "Not watched by the scan interlock. Click to watch this state."
        )
        self.lock_button.setToolTip(tip)
        self.lock_button.setAccessibleName(tip)
        set_icon(
            self.expand_icon, "expand_less" if row["expanded"] else "expand_more", tokens.fg_muted
        )

        self.details.setVisible(row["expanded"])
        if row["expanded"]:
            self._set_params(row, tokens)
            self.trip_switch.setChecked(row["tripOnWarning"])
            self.trip_label.setStyleSheet(f"color: {tokens.fg.name()}; font-size: 13px; {PLAIN}")

        if row["tripped"]:
            if self._flash_animation.state() != QVariantAnimation.State.Running:
                self._flash_animation.start()
        else:
            self._flash_animation.stop()
            self._flash = 0.0
        self.update()

    def _set_params(self, row: dict, tokens: ThemeTokens) -> None:
        entries = [("type", row["stateType"])] + [(p["key"], p["value"]) for p in row["params"]]
        while len(self._param_labels) < 2 * len(entries):
            label = QLabel(self.details)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._param_labels.append(label)
        for index, label in enumerate(self._param_labels):
            entry = index // 2
            if entry >= len(entries):
                label.hide()
                continue
            is_value = index % 2 == 1
            label.setText(entries[entry][1 if is_value else 0])
            color = tokens.fg if is_value else tokens.fg_subtle
            family = "font-family: monospace;" if is_value and entry > 0 else ""
            label.setStyleSheet(f"color: {color.name()}; font-size: 12px; {family} {PLAIN}")
            self.params.addWidget(label, entry, 1 if is_value else 0)
            label.show()
        self.params.setColumnStretch(1, 1)

    def _on_flash(self, value) -> None:
        self._flash = float(value)
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        if not self.row:
            return
        tokens = ThemeTokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        tripped = self.row.get("tripped")
        expanded = self.row.get("expanded")
        if tripped:
            fill = alpha(tokens.danger, 0.08 + 0.10 * self._flash)
            pen = QPen(alpha(tokens.danger, 0.5 + 0.5 * self._flash), 2)
        elif expanded:
            fill, pen = tokens.field, QPen(tokens.border, 1)
        else:
            hovered = self.header.underMouse()
            fill = tokens.hover if hovered else QColor(0, 0, 0, 0)
            pen = QPen(QColor(0, 0, 0, 0), 1)
        inset = pen.widthF() / 2
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset), 8, 8)
        painter.end()

    def cleanup(self) -> None:
        """Stop animations."""
        self._flash_animation.stop()
        self.status_pill.cleanup()


class BeamlineStatesQWidget(BeamlineStatesPortBase):
    """Beamline state manager with the modernised UX in plain QWidgets."""

    def _init_view(self) -> None:
        self.setMinimumSize(320, 300)
        self._rows: dict[str, StateRow] = {}
        self._headers: dict[str, SectionHeader] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        self.card = Card("Beamline states", parent=self)
        outer.addWidget(self.card)
        body = self.card.body
        body.setSpacing(8)

        # scan interlock
        self.interlock_panel = QFrame(self.card)
        self.interlock_panel.setObjectName("interlockPanel")
        panel = QHBoxLayout(self.interlock_panel)
        panel.setContentsMargins(10, 6, 6, 6)
        panel.setSpacing(8)
        self.interlock_icon = icon_label(self.interlock_panel)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.interlock_title = QLabel("Scan interlock", self.interlock_panel)
        self.interlock_sub = QLabel(self.interlock_panel)
        titles.addWidget(self.interlock_title)
        titles.addWidget(self.interlock_sub)
        self.interlock_pill = StatusPill(self.interlock_panel)
        self.interlock_switch = ToggleSwitch(self.interlock_panel)
        self.interlock_switch.setFixedWidth(46)
        self.interlock_switch.setAccessibleName("Arm scan interlock")
        self.interlock_switch.clicked.connect(self.set_interlock_enabled)
        panel.addWidget(self.interlock_icon)
        panel.addLayout(titles, 1)
        panel.addWidget(self.interlock_pill)
        panel.addWidget(self.interlock_switch)
        body.addWidget(self.interlock_panel)

        # tripped banner
        self.banner = QFrame(self.card)
        self.banner.setObjectName("trippedBanner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(10, 7, 10, 7)
        banner_layout.setSpacing(8)
        self.banner_icon = icon_label(self.banner, 16)
        self.banner_text = QLabel(self.banner)
        self.banner_text.setWordWrap(True)
        banner_layout.addWidget(self.banner_icon, 0, Qt.AlignmentFlag.AlignTop)
        banner_layout.addWidget(self.banner_text, 1)
        body.addWidget(self.banner)

        # search, clear and add
        self.tools = QWidget(self.card)
        tools = QHBoxLayout(self.tools)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(6)
        self.search = QLineEdit(self.tools)
        self.search.setPlaceholderText("Filter by name or device")
        self.search.setAccessibleName("Filter states")
        self.search.setClearButtonEnabled(True)
        self.search_action = self.search.addAction(
            material_icon("search", convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search.textEdited.connect(self.set_filter_text)
        self.clear_button = IconButton("filter_alt_off", "Clear filters", self.tools)
        self.clear_button.clicked.connect(self.clear_filters)
        self.add_button = TextButton("Add", "primary", "add", self.tools)
        self.add_button.clicked.connect(self.open_add_state_dialog)
        tools.addWidget(self.search, 1)
        tools.addWidget(self.clear_button)
        tools.addWidget(self.add_button)
        body.addWidget(self.tools)

        # status chips
        self.chips_box = QWidget(self.card)
        self.chips_layout = QHBoxLayout(self.chips_box)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(6)
        self.chips_layout.addStretch(1)
        self._chips: list[StatusChip] = []
        body.addWidget(self.chips_box)

        # list
        self.scroll = QScrollArea(self.card)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget = QWidget(self.scroll)
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 2, 0)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_widget)
        body.addWidget(self.scroll, 1)

        # no matches
        self.no_match = QWidget(self.card)
        no_match = QVBoxLayout(self.no_match)
        no_match.addStretch(1)
        self.no_match_label = QLabel("No states match the filters.", self.no_match)
        self.no_match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_match_button = TextButton(
            "Clear filters", "neutral", "filter_alt_off", self.no_match
        )
        self.no_match_button.clicked.connect(self.clear_filters)
        no_match.addWidget(self.no_match_label)
        no_match.addWidget(self.no_match_button, 0, Qt.AlignmentFlag.AlignHCenter)
        no_match.addStretch(1)
        body.addWidget(self.no_match, 1)

        # hidden by filters
        self.hidden_button = QPushButton(self.card)
        self.hidden_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hidden_button.setFixedHeight(28)
        self.hidden_button.clicked.connect(lambda: self.set_show_hidden(not self._show_hidden))
        body.addWidget(self.hidden_button)

        # empty state
        self.empty = QWidget(self.card)
        empty = QVBoxLayout(self.empty)
        empty.setSpacing(8)
        empty.addStretch(1)
        self.empty_icon = icon_label(self.empty, 36)
        self.empty_title = QLabel("No beamline states yet", self.empty)
        self.empty_text = QLabel(
            "A state watches a device, for example whether a motor is within limits, "
            "and can block scans through the scan interlock.",
            self.empty,
        )
        self.empty_text.setWordWrap(True)
        for label in (self.empty_title, self.empty_text):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_button = TextButton("Add state", "primary", "add", self.empty)
        self.empty_button.clicked.connect(self.open_add_state_dialog)
        empty.addWidget(self.empty_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addWidget(self.empty_title)
        empty.addWidget(self.empty_text)
        empty.addWidget(self.empty_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addStretch(1)
        body.addWidget(self.empty, 1)

        self._apply_styles(ThemeTokens())

    # ---- rendering -----------------------------------------------------------------------

    def _apply_styles(self, tokens: ThemeTokens) -> None:
        self.card.setStyleSheet(self.card.styleSheet() + field_qss(tokens))
        self.search.setStyleSheet("QLineEdit { padding-left: 2px; }")
        self.search_action.setIcon(
            material_icon("search", color=tokens.fg_subtle, convert_to_pixmap=False)
        )
        for widget in (self.tools, self.chips_box, self.no_match, self.empty):
            widget.setStyleSheet("background: none;")
        self.scroll.setStyleSheet(
            f"QScrollArea {{ background: {tokens.card.name()}; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background: {tokens.card.name()}; }}"
        )
        self.interlock_title.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 13px; font-weight: 600; {PLAIN}"
        )
        self.interlock_sub.setStyleSheet(
            f"color: {tokens.fg_muted.name()}; font-size: 11px; {PLAIN}"
        )
        self.banner.setStyleSheet(
            f"QFrame#trippedBanner {{ background: {rgba(tokens.danger, 0.14)};"
            f" border: 1px solid {rgba(tokens.danger, 0.5)}; border-radius: 8px; }}"
        )
        self.banner_text.setStyleSheet(f"color: {tokens.fg.name()}; font-size: 12px; {PLAIN}")
        set_icon(self.banner_icon, "block", tokens.danger, 16)
        self.no_match_label.setStyleSheet(
            f"color: {tokens.fg_muted.name()}; font-size: 13px; {PLAIN}"
        )
        self.hidden_button.setStyleSheet(
            f"QPushButton {{ color: {tokens.fg_muted.name()}; font-size: 12px; text-align: left;"
            f" border: none; border-radius: 6px; padding: 0 6px; background: transparent; }}"
            f"QPushButton:hover {{ background: {tokens.hover.name()}; }}"
        )
        set_icon(self.empty_icon, "rule", tokens.fg_subtle, 36)
        self.empty_title.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 14px; font-weight: 600; {PLAIN}"
        )
        self.empty_text.setStyleSheet(f"color: {tokens.fg_muted.name()}; font-size: 12px; {PLAIN}")

    def _sync_view(self) -> None:
        if not hasattr(self, "card"):
            return
        state = self.view_state()
        tokens = ThemeTokens()
        total = state["total"]
        self.card.set_title(
            "Beamline states", f"{total} state{'s' if total != 1 else ''}" if total else ""
        )

        # interlock
        enabled = state["interlockEnabled"]
        tone = tone_color(state["interlockTone"], tokens)
        if enabled:
            panel_bg, panel_border = rgba(tone, 0.10), rgba(tone, 0.45)
        else:
            panel_bg, panel_border = tokens.field.name(), tokens.border.name()
        self.interlock_panel.setStyleSheet(
            f"QFrame#interlockPanel {{ background: {panel_bg}; border: 1px solid {panel_border};"
            f" border-radius: 8px; }}"
        )
        set_icon(self.interlock_icon, "lock" if enabled else "no_encryption", tone, 18, True)
        count = state["interlockCount"]
        self.interlock_sub.setText(
            "No states watched"
            if count == 0
            else f"{count} state{' watched' if count == 1 else 's watched'}"
        )
        self.interlock_pill.set_status(state["interlockText"], tone, bool(state["banner"]))
        self.interlock_switch.setChecked(enabled)
        self.interlock_switch.setToolTip(
            "Disarm the scan interlock" if enabled else "Arm the scan interlock"
        )
        self.banner.setVisible(bool(state["banner"]))
        self.banner_text.setText(state["banner"])

        # tools and chips
        empty = state["empty"]
        self.tools.setVisible(not empty)
        self.chips_box.setVisible(not empty)
        if not self.search.hasFocus() and self.search.text() != state["filterText"]:
            self.search.setText(state["filterText"])
        self.clear_button.setVisible(state["filtersActive"])
        self._sync_chips(state["chips"], tokens)

        # list
        show_list = not empty and not state["noMatches"]
        self.scroll.setVisible(show_list)
        self._sync_rows(state["rows"], tokens)
        self.no_match.setVisible(state["noMatches"])
        self.hidden_button.setVisible(state["hiddenCount"] > 0 and not state["noMatches"])
        self.hidden_button.setText(
            state["hiddenText"] + ("  ·  Hide them" if state["showHidden"] else "  ·  Show them")
        )
        self.hidden_button.setIcon(
            material_icon(
                "visibility_off" if state["showHidden"] else "visibility",
                color=tokens.fg_muted,
                convert_to_pixmap=False,
            )
        )
        self.hidden_button.setIconSize(QSize(16, 16))
        self.empty.setVisible(empty)

    def _sync_chips(self, chips: list[dict], tokens: ThemeTokens) -> None:
        while len(self._chips) < len(chips):
            chip = StatusChip(self.chips_box)
            chip.clicked.connect(lambda _=False, c=chip: self.toggle_status_filter(c.status))
            self.chips_layout.insertWidget(len(self._chips), chip)
            self._chips.append(chip)
        for index, chip in enumerate(self._chips):
            if index < len(chips):
                chip.set_chip(chips[index], tokens)
                chip.show()
            else:
                chip.hide()

    def _sync_rows(self, rows: list[dict], tokens: ThemeTokens) -> None:
        keys = {row["key"] for row in rows}
        for key in [key for key in self._rows if key not in keys]:
            widget = self._rows.pop(key)
            widget.cleanup()
            widget.deleteLater()
        for key in [key for key in self._headers if key not in keys]:
            self._headers.pop(key).deleteLater()
        for position, row in enumerate(rows):
            if row["kind"] == "header":
                widget = self._headers.get(row["key"])
                if widget is None:
                    widget = SectionHeader(self.list_widget)
                    self._headers[row["key"]] = widget
            else:
                widget = self._rows.get(row["key"])
                if widget is None:
                    widget = StateRow(self, self.list_widget)
                    self._rows[row["key"]] = widget
            widget.set_row(row, tokens)
            if self.list_layout.indexOf(widget) != position:
                self.list_layout.insertWidget(position, widget)
            widget.show()

    @property
    def state_rows(self) -> dict[str, StateRow]:
        """Row widgets by state name, for tests and inspection."""
        return {row.row["name"]: row for row in self._rows.values()}

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        tokens = refresh_kit_theme(self)
        self._apply_styles(tokens)
        self._sync_view()

    def cleanup(self):
        for row in self._rows.values():
            row.cleanup()
        self.interlock_pill.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = BeamlineStatesQWidget()
    widget.resize(460, 560)
    widget.show()
    sys.exit(app.exec())
