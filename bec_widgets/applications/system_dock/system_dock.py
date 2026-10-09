"""
Right-edge system dock of the BEC main app.

The dock holds the core widgets that only make sense once per application (scan progress, the
scan queue, notifications, beamline states, BEC services). It has three parts:

* the **rail**: a narrow strip of icon buttons on the right edge of the window, visible in every
  view. Each button carries a live indicator (an unread count, a status dot or a progress ring),
  so the state of the beamline can be read without opening anything;
* the **flyout**: clicking a button slides its panel out over the content. A click outside, Esc
  or the same button closes it again. Opening on hover is available as an opt-in from the rail's
  context menu;
* the **pinned column**: the pin button in a panel header docks the panel next to the content,
  pushing the workspace aside instead of covering it. Up to two pinned panels share the column;
  the pinned set is restored on the next start.

Plugins can add their own entries with :meth:`SystemDock.add_panel`.
"""

from __future__ import annotations

from dataclasses import dataclass

import shiboken6
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSettings,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from qtpy.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPen,
    QShortcut,
)
from qtpy.QtWidgets import (
    QAbstractButton,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.eliding_label import ElidingLabel
from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import IconButton

logger = bec_logger.logger

RAIL_WIDTH = 48
BUTTON_HEIGHT = 44
PEEK_WIDTH = 480
PINNED_WIDTH = 484
PINNED_MIN_WIDTH = 380
PINNED_MAX_WIDTH = 600
MAX_PINNED = 2  # docked slots in the column; option D of the proposals would add areas
HEADER_HEIGHT = 44
SHADOW = 14
HOVER_OPEN_DELAY = 280  # ms the pointer has to rest on a rail button before its panel peeks out
LEAVE_CLOSE_DELAY = 450  # ms after the pointer left rail and panel before a hover peek hides
SLIDE_DURATION = 140

SETTINGS_PINNED = "system_dock/pinned"
SETTINGS_HOVER = "system_dock/hover_open"
SETTINGS_WIDTH = "system_dock/pinned_width"
SETTINGS_MODE = "system_dock/mode"
SETTINGS_COLLAPSED = "system_dock/collapsed"
SETTINGS_SPLIT = "system_dock/split"

MODE_DOCKED = "docked"  # a rail click docks the panel next to the workspace, pushing it aside
MODE_OVERLAY = "overlay"  # a rail click opens a flyout over the workspace


@dataclass
class RailIndicator:
    """What a rail button shows on top of its icon, and the panel header's summary line.

    Attributes:
        badge(str): Short text in a pill at the top right, e.g. an unread count. Empty for none.
        badge_color(QColor | None): Fill of the badge pill.
        dot_color(QColor | None): A small status dot, used when there is no badge.
        progress(float | None): 0..1 draws a progress ring around the icon; None for no ring.
        progress_color(QColor | None): Colour of the progress ring; the theme primary if None.
        pulse(bool): Pulse a halo around the badge, for something that needs attention now.
        tooltip(str): Tooltip of the rail button.
        summary(str): One line shown next to the title in the panel header.
    """

    badge: str = ""
    badge_color: QColor | None = None
    dot_color: QColor | None = None
    progress: float | None = None
    progress_color: QColor | None = None
    pulse: bool = False
    tooltip: str = ""
    summary: str = ""


class SystemPanel(QObject):
    """One entry of the system dock: a rail button plus a panel around ``content``.

    Subclasses compute the rail indicator from their widget's model and call
    :meth:`set_indicator` whenever it changes.

    Args:
        panel_id(str): Unique id, also used to persist the pinned state.
        title(str): Title in the panel header.
        icon(str): Material icon name of the rail button.
        label(str): Short name, used in menus and for accessibility.
        content(QWidget): The widget shown in the panel.
        preferred_height(int | None): Height of the content for a compact flyout that only
            covers part of the window next to its button; None for a full-height panel.
        min_width(int | None): Width the content needs, when more than the default panel width.
    """

    indicator_changed = Signal()

    def __init__(
        self,
        panel_id: str,
        title: str,
        icon: str,
        label: str,
        content: QWidget,
        parent: QObject | None = None,
        preferred_height: int | None = None,
        min_width: int | None = None,
    ):
        super().__init__(parent)
        self.panel_id = panel_id
        self.title = title
        self.icon = icon
        self.label = label
        self.content = content
        self.preferred_height = preferred_height
        self.min_width = min_width
        self._indicator = RailIndicator(tooltip=title)

    @property
    def indicator(self) -> RailIndicator:
        """The current rail indicator."""
        return self._indicator

    def set_indicator(self, indicator: RailIndicator) -> None:
        """Replace the rail indicator; emits :attr:`indicator_changed` only on a change."""
        if indicator != self._indicator:
            self._indicator = indicator
            self.indicator_changed.emit()

    def set_shown(self, shown: bool) -> None:
        """Called when the panel becomes visible (peeked or pinned) or hidden."""

    def cleanup(self) -> None:
        """Release the content widget."""
        if shiboken6.isValid(self.content):
            self.content.close()
            self.content.deleteLater()


class RailButton(QAbstractButton):
    """Rail button: icon, short label, and the panel's live indicator."""

    hovered = Signal(str, bool)

    def __init__(self, panel: SystemPanel, dock: "SystemDock"):
        super().__init__(dock)
        self.panel = panel
        self.dock = dock
        self._active = False
        self._pinned = False
        self._hover = False
        self.shortcut_text = ""
        self.setFixedSize(RAIL_WIDTH, BUTTON_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(panel.title)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        panel.indicator_changed.connect(self.refresh_indicator)
        self.refresh_indicator()

    def set_state(self, active: bool, pinned: bool) -> None:
        """Highlight the button while its panel is shown; mark pinned panels."""
        if (active, pinned) != (self._active, self._pinned):
            self._active, self._pinned = active, pinned
            self.update()

    @property
    def active(self) -> bool:
        """Whether the panel of this button is visible."""
        return self._active

    def refresh_indicator(self) -> None:
        ind = self.panel.indicator
        title = self.panel.title
        if self.shortcut_text:
            title = f"{title} ({self.shortcut_text})"
        tip = ind.tooltip
        self.setToolTip(f"{title}\n{tip}" if tip and tip != self.panel.title else title)
        self.update()

    def enterEvent(self, event):  # pylint: disable=invalid-name
        self._hover = True
        self.update()
        self.hovered.emit(self.panel.panel_id, True)
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        self._hover = False
        self.update()
        self.hovered.emit(self.panel.panel_id, False)
        super().leaveEvent(event)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = self.dock.tokens
        ind = self.panel.indicator
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        tile = QRectF(5, 3, w - 10, h - 6)
        if self._active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.soft(tokens.primary, 0.2 if tokens.dark else 0.14))
            painter.drawRoundedRect(tile, 8, 8)
        elif self._hover or self.hasFocus():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.hover)
            painter.drawRoundedRect(tile, 8, 8)
        if self._pinned:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.primary)
            painter.drawRoundedRect(QRectF(1, tile.top() + 9, 3, tile.height() - 18), 1.5, 1.5)

        if self._active:
            fg = tokens.primary
        elif self._hover:
            fg = tokens.fg
        else:
            fg = tokens.fg_muted
        center = QPointF(w / 2, h / 2)
        size = 20 if ind.progress is not None else 22
        pix = material_icon(
            self.panel.icon, size=(size * 2, size * 2), color=fg, filled=self._active
        )
        painter.drawPixmap(
            QRectF(center.x() - size / 2, center.y() - size / 2, size, size),
            pix,
            QRectF(pix.rect()),
        )

        if ind.progress is not None:
            ring = QRectF(center.x() - 15, center.y() - 15, 30, 30)
            pen = QPen(tokens.track, 2.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ring)
            pen.setColor(ind.progress_color or tokens.primary)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            span = int(-360 * 16 * max(0.0, min(1.0, ind.progress)))
            painter.drawArc(ring, 90 * 16, span)

        rail_bg = self.dock.palette().window().color()
        if ind.badge:
            bfont = QFont(self.font())
            bfont.setPointSizeF(max(7.0, bfont.pointSizeF() - 2.5))
            bfont.setWeight(QFont.Weight.Bold)
            metrics = QFontMetrics(bfont)
            bw = max(16, metrics.horizontalAdvance(ind.badge) + 8)
            rect = QRectF(min(center.x() + 2, w - bw - 2), 3, bw, 16)
            color = ind.badge_color or tokens.primary
            if ind.pulse:
                halo = QColor(color)
                halo.setAlphaF(0.45 * (1.0 - self.dock.pulse_phase))
                grow = 1 + 5 * self.dock.pulse_phase
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(halo)
                painter.drawRoundedRect(rect.adjusted(-grow, -grow, grow, grow), 8 + grow, 8 + grow)
            painter.setPen(QPen(rail_bg, 2))
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 8, 8)
            painter.setFont(bfont)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, ind.badge)
        elif ind.dot_color is not None:
            painter.setPen(QPen(rail_bg, 2))
            painter.setBrush(ind.dot_color)
            painter.drawEllipse(QPointF(center.x() + 10, center.y() - 10), 5, 5)
        painter.end()


class PanelFrame(QFrame):
    """A panel as shown in the dock: header with title, summary, pin and close, then content."""

    pin_toggled = Signal(str, bool)
    close_requested = Signal(str)

    def __init__(self, panel: SystemPanel, parent: QWidget | None = None):
        super().__init__(parent)
        self.panel = panel
        self.setObjectName("systemDockPanel")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.header = QWidget(self)
        self.header.setObjectName("systemDockPanelHeader")
        self.header.setFixedHeight(44)
        self.icon = QLabel(self.header)
        self.icon.setFixedSize(20, 20)
        self.title = QLabel(panel.title, self.header)
        self.title.setObjectName("systemDockPanelTitle")
        self.summary = ElidingLabel(self.header)
        self.summary.setObjectName("systemDockPanelSummary")
        self.pin_button = IconButton("push_pin", "Dock next to the workspace", self.header)
        self.pin_button.setCheckable(True)
        self.pin_button.clicked.connect(
            lambda checked: self.pin_toggled.emit(panel.panel_id, bool(checked))
        )
        self.close_button = IconButton("close", "Close", self.header)
        self.close_button.clicked.connect(lambda: self.close_requested.emit(panel.panel_id))

        head = QHBoxLayout(self.header)
        head.setContentsMargins(14, 0, 8, 0)
        head.setSpacing(8)
        head.addWidget(self.icon)
        head.addWidget(self.title)
        head.addWidget(self.summary, 1)
        head.addWidget(self.pin_button)
        head.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(panel.content, 1)
        panel.content.show()
        panel.indicator_changed.connect(self._update_summary)
        self._update_summary()

    def set_pinned(self, pinned: bool) -> None:
        """Reflect the pinned state on the pin button."""
        self.pin_button.setChecked(pinned)
        self.pin_button.setToolTip("Undock" if pinned else "Dock next to the workspace")
        self.pin_button.refresh_theme(ThemeTokens())

    def _update_summary(self) -> None:
        text = self.panel.indicator.summary
        self.summary.setText(text)
        self.summary.setToolTip(text)

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens to the header."""
        self.icon.setPixmap(
            material_icon(self.panel.icon, size=(20, 20), color=tokens.primary, filled=True)
        )
        self.header.setStyleSheet(
            f"#systemDockPanelHeader {{ border-bottom: 1px solid {tokens.track.name()}; }}"
            f"#systemDockPanelTitle {{ font-weight: 600; color: {tokens.fg.name()}; }}"
            f"#systemDockPanelSummary {{ color: {tokens.fg_muted.name()}; }}"
        )
        self.pin_button.refresh_theme(tokens)
        self.close_button.refresh_theme(tokens)


class _PeekHost(QWidget):
    """Floating container of the peek panel, drawn with a soft shadow on its left edge."""

    def __init__(self, dock: "SystemDock", overlay_parent: QWidget):
        super().__init__(overlay_parent)
        self.dock = dock
        self.setObjectName("systemDockPeek")
        self.stack = QStackedWidget(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SHADOW, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stack)
        self.hide()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = self.dock.tokens
        painter = QPainter(self)
        shade = QColor(0, 0, 0, 90 if tokens.dark else 40)
        gradient = QLinearGradient(0, 0, SHADOW, 0)
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, shade)
        painter.fillRect(QRect(0, 0, SHADOW, self.height()), gradient)
        painter.fillRect(QRect(SHADOW, 0, self.width() - SHADOW, self.height()), tokens.bg)
        painter.setPen(tokens.border)
        painter.drawLine(SHADOW, 0, SHADOW, self.height())
        if self.height() < self.dock.height():
            # compact flyout: close it off at the bottom as well
            painter.drawLine(SHADOW, self.height() - 1, self.width(), self.height() - 1)
        painter.end()


class SystemDock(QWidget):
    """The rail on the right edge, with its docked column and peek panel.

    The rail is this widget; put it at the right edge of the window layout. Put
    :attr:`pinned_column` between the main content and the rail, ideally in a ``QSplitter`` with
    the content so the user can resize it. Docked ("pinned") panels live in that column and push
    the content aside; they stay open whatever the content shows. The column has
    ``max_docked`` slots stacked in a vertical splitter.

    In the default docked mode a rail click docks or undocks a panel. While the column is
    collapsed (the arrow at the bottom of the rail, Ctrl+Shift+D) a click only peeks the panel in a
    flyout over the content, which a click outside or Esc closes. In overlay mode every click
    opens a flyout and the pin in the panel header docks it.

    Args:
        overlay_parent(QWidget): Widget the peek panel floats over, usually the central widget
            that also contains the rail.
        settings(QSettings | None): Where to persist pinned panels and the hover preference.
        hover_open(bool | None): Open panels when the pointer rests on a rail button. Defaults to
            the persisted preference, or False.
        mode(str | None): "docked" or "overlay"; defaults to the persisted preference, or docked.
        max_docked(int): Number of docked slots in the column.
    """

    panel_shown = Signal(str, bool)
    pinned_changed = Signal(list)
    collapsed_changed = Signal(bool)

    def __init__(
        self,
        overlay_parent: QWidget,
        parent: QWidget | None = None,
        settings: QSettings | None = None,
        hover_open: bool | None = None,
        mode: str | None = None,
        max_docked: int = MAX_PINNED,
    ):
        super().__init__(parent or overlay_parent)
        self.setObjectName("systemDockRail")
        self.setFixedWidth(RAIL_WIDTH)
        self.setAutoFillBackground(True)
        self.tokens = ThemeTokens()
        self._overlay_parent = overlay_parent
        self._settings = settings
        self._panels: dict[str, SystemPanel] = {}
        self._buttons: dict[str, RailButton] = {}
        self._frames: dict[str, PanelFrame] = {}
        self._pinned: list[str] = []
        self._peek_id: str | None = None
        self._peek_sticky = False
        self._filter_installed = False
        self._cleaned = False
        if hover_open is None:
            hover_open = self._read_setting(SETTINGS_HOVER, False, bool)
        self._hover_open = bool(hover_open)
        self._pending_hover: str | None = None
        if mode is None:
            mode = self._read_setting(SETTINGS_MODE, MODE_DOCKED, str)
        self._mode = MODE_OVERLAY if mode == MODE_OVERLAY else MODE_DOCKED
        self.max_docked = max(1, int(max_docked))
        self._collapsed = bool(self._read_setting(SETTINGS_COLLAPSED, False, bool))

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 8, 0, 8)
        self._layout.setSpacing(2)
        self._layout.addStretch(1)
        self.collapse_button = IconButton("right_panel_close", "Collapse docked panels", self)
        self.collapse_button.setObjectName("systemDockCollapse")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        self._layout.addWidget(self.collapse_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.peek = _PeekHost(self, overlay_parent)
        self.peek.installEventFilter(self)
        self._slide = QPropertyAnimation(self.peek, b"pos", self)
        self._slide.setDuration(SLIDE_DURATION)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.pinned_column = QSplitter(Qt.Orientation.Vertical)
        self.pinned_column.setObjectName("systemDockPinned")
        self.pinned_column.setChildrenCollapsible(False)
        self.pinned_column.setMinimumWidth(PINNED_MIN_WIDTH)
        self.pinned_column.setMaximumWidth(PINNED_MAX_WIDTH)
        self.pinned_column.hide()
        self.pinned_column.splitterMoved.connect(self._store_split)

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(HOVER_OPEN_DELAY)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(LEAVE_CLOSE_DELAY)
        self._leave_timer.timeout.connect(self._on_leave_timeout)
        # one clock for every pulsing badge, running only while a badge pulses
        self.pulse_phase = 0.0
        self._pulse = QVariantAnimation(self)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(1400)
        self._pulse.setLoopCount(-1)
        self._pulse.valueChanged.connect(self._on_pulse)
        self._shortcuts: list[QShortcut] = []
        self._add_shortcut("Ctrl+Shift+P", self.toggle_pin_current)
        self._add_shortcut("Ctrl+Shift+D", self.toggle_collapsed)
        self._update_collapse_button()

        overlay_parent.installEventFilter(self)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        app = QApplication.instance()
        theme = getattr(app, "theme", None)
        if theme is not None and hasattr(theme, "theme_changed"):
            theme.theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------ panels
    def add_panel(self, panel: SystemPanel, shortcut: str | None = None) -> RailButton:
        """Add a panel and its rail button below the existing ones.

        Args:
            panel(SystemPanel): The panel to add.
            shortcut(str | None): Key sequence that opens or closes the panel, e.g. "Ctrl+Shift+Q".

        Returns:
            RailButton: The rail button of the panel.
        """
        if panel.panel_id in self._panels:
            raise ValueError(f"Panel {panel.panel_id!r} already exists in the system dock.")
        panel.setParent(self)
        self._panels[panel.panel_id] = panel
        button = RailButton(panel, self)
        button.clicked.connect(lambda: self.toggle_panel(panel.panel_id))
        button.hovered.connect(self._on_button_hovered)
        self._layout.insertWidget(self._layout.count() - 2, button)
        self._buttons[panel.panel_id] = button
        panel.indicator_changed.connect(self._update_pulse)
        if shortcut:
            self._add_shortcut(shortcut, lambda: self.toggle_panel(panel.panel_id))
            button.shortcut_text = shortcut
            button.refresh_indicator()
        frame = PanelFrame(panel)
        frame.pin_toggled.connect(self.set_pinned)
        frame.close_requested.connect(self.close_panel)
        frame.refresh_theme(self.tokens)
        self.peek.stack.addWidget(frame)
        self._frames[panel.panel_id] = frame
        return button

    def add_separator(self) -> QFrame:
        """Add a divider below the existing rail buttons, e.g. before plugin panels."""
        line = QFrame(self)
        line.setObjectName("systemDockDivider")
        line.setFixedSize(RAIL_WIDTH - 20, 1)
        line.setStyleSheet(f"background: {self.tokens.border.name()};")
        self._layout.insertWidget(self._layout.count() - 2, line, 0, Qt.AlignmentFlag.AlignHCenter)
        self._layout.insertSpacing(self._layout.count() - 2, 2)
        return line

    def panel(self, panel_id: str) -> SystemPanel:
        """The panel with ``panel_id``."""
        return self._panels[panel_id]

    def button(self, panel_id: str) -> RailButton:
        """The rail button of ``panel_id``."""
        return self._buttons[panel_id]

    def frame(self, panel_id: str) -> PanelFrame:
        """The panel frame (header and content) of ``panel_id``."""
        return self._frames[panel_id]

    @property
    def panel_ids(self) -> list[str]:
        """Ids of all panels in rail order."""
        return list(self._panels)

    @property
    def peek_panel_id(self) -> str | None:
        """Id of the panel shown in the peek, or None when it is closed."""
        return self._peek_id

    @property
    def peek_sticky(self) -> bool:
        """Whether the peek stays open when the pointer leaves it (it was clicked)."""
        return self._peek_sticky

    @property
    def pinned(self) -> list[str]:
        """Ids of the pinned panels, top to bottom."""
        return list(self._pinned)

    def is_shown(self, panel_id: str) -> bool:
        """Whether ``panel_id`` is visible, peeked or docked in the expanded column."""
        docked = panel_id in self._pinned and not self._collapsed
        return docked or panel_id == self._peek_id

    # ------------------------------------------------------------------ mode and collapse
    @property
    def mode(self) -> str:
        """ "docked" when a rail click docks the panel, "overlay" when it opens a flyout."""
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Choose what a rail click does, and persist the choice."""
        self._mode = MODE_OVERLAY if mode == MODE_OVERLAY else MODE_DOCKED
        self._write_setting(SETTINGS_MODE, self._mode)

    @property
    def collapsed(self) -> bool:
        """Whether the docked column is folded away; the rail and its badges stay."""
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Fold the docked column away or bring it back, keeping which panels are docked."""
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return
        self.close_peek()
        self._collapsed = collapsed
        for panel_id in self._pinned:
            self._set_shown(panel_id, not collapsed)
        self.pinned_column.setVisible(self.isVisible() and bool(self._pinned) and not collapsed)
        self._update_buttons()
        self._update_collapse_button()
        self._write_setting(SETTINGS_COLLAPSED, collapsed)
        self.collapsed_changed.emit(collapsed)
        if not collapsed and self._pinned:
            self.pinned_changed.emit(list(self._pinned))

    def toggle_collapsed(self) -> None:
        """Collapse or expand the docked column (rail arrow, Ctrl+Shift+D)."""
        self.set_collapsed(not self._collapsed)

    # ------------------------------------------------------------------ hover preference
    @property
    def hover_open(self) -> bool:
        """Whether resting the pointer on a rail button peeks its panel."""
        return self._hover_open

    def set_hover_open(self, enabled: bool) -> None:
        """Enable or disable opening panels on hover, and persist the choice."""
        self._hover_open = bool(enabled)
        self._hover_timer.stop()
        self._write_setting(SETTINGS_HOVER, self._hover_open)

    # ------------------------------------------------------------------ open / close
    def toggle_panel(self, panel_id: str) -> None:
        """Rail button click: dock or undock the panel, or peek it while the column is collapsed.

        In overlay mode, and while the column is collapsed, the click opens the panel in a
        flyout and keeps it open, or closes a kept-open flyout.
        """
        self._hover_timer.stop()
        if not self.isVisible():
            self.set_dock_visible(True)
        if panel_id in self._pinned and self._collapsed:
            self.set_collapsed(False)  # a docked panel comes back with its column
            return
        if self._mode == MODE_DOCKED and not self._collapsed:
            self.set_pinned(panel_id, panel_id not in self._pinned)
            return
        if panel_id in self._pinned:
            self._frames[panel_id].panel.content.setFocus()
            return
        if self._peek_id == panel_id:
            if self._peek_sticky:
                self.close_peek()
            else:
                self._peek_sticky = True
                self._leave_timer.stop()
            return
        self.open_panel(panel_id, sticky=True)

    def open_panel(self, panel_id: str, sticky: bool = True) -> None:
        """Show ``panel_id`` in the peek (no-op if it is pinned).

        Args:
            panel_id(str): The panel to show.
            sticky(bool): Keep it open when the pointer leaves; otherwise it hides like a hover.
        """
        if panel_id not in self._panels:
            raise KeyError(panel_id)
        if panel_id in self._pinned:
            return
        was_open = self._peek_id is not None
        previous = self._peek_id
        self._peek_id = panel_id
        self._peek_sticky = sticky
        self.peek.stack.setCurrentWidget(self._frames[panel_id])
        if previous is not None and previous != panel_id:
            self._set_shown(previous, False)
        target = self._peek_geometry()
        if not was_open:
            self.peek.setGeometry(target.translated(24, 0))
            self.peek.show()
            self.peek.raise_()
            self._slide.stop()
            self._slide.setStartValue(target.topLeft() + QPoint(24, 0))
            self._slide.setEndValue(target.topLeft())
            self._slide.start()
        else:
            self.peek.setGeometry(target)
            self.peek.raise_()
        self._install_app_filter(True)
        if previous != panel_id:
            self._set_shown(panel_id, True)
        self._update_buttons()

    def close_peek(self) -> None:
        """Hide the peek panel."""
        self._hover_timer.stop()
        self._leave_timer.stop()
        if self._peek_id is None:
            return
        closing = self._peek_id
        self._peek_id = None
        self._peek_sticky = False
        self._slide.stop()
        self.peek.hide()
        self._install_app_filter(False)
        self._set_shown(closing, False)
        self._update_buttons()

    def close_panel(self, panel_id: str) -> None:
        """Close ``panel_id``, unpinning it if it is pinned."""
        if panel_id in self._pinned:
            self.set_pinned(panel_id, False)
            return
        if panel_id == self._peek_id:
            self.close_peek()

    def set_pinned(self, panel_id: str, pinned: bool) -> None:
        """Pin ``panel_id`` into the column next to the content, or unpin (and close) it."""
        frame = self._frames[panel_id]
        if pinned and self._collapsed:
            # docking from a peek while collapsed brings the column back
            self.set_collapsed(False)
        if pinned and panel_id not in self._pinned:
            if panel_id == self._peek_id:
                # the frame moves from the peek into the column: the panel stays visible
                self._peek_id = None
                self._peek_sticky = False
                self.peek.hide()
                self._install_app_filter(False)
            else:
                self._set_shown(panel_id, True)
            while len(self._pinned) >= self.max_docked:
                self.set_pinned(self._pinned[0], False)
            self._pinned.append(panel_id)
            self.pinned_column.addWidget(frame)
            frame.show()
        elif not pinned and panel_id in self._pinned:
            self._pinned.remove(panel_id)
            if panel_id == self._peek_id:
                self.close_peek()
            self.peek.stack.addWidget(frame)
            if not self._collapsed:
                self._set_shown(panel_id, False)
        else:
            frame.set_pinned(panel_id in self._pinned)
            return
        frame.set_pinned(pinned)
        needed = max([PINNED_MIN_WIDTH] + [self._panels[p].min_width or 0 for p in self._pinned])
        self.pinned_column.setMinimumWidth(needed)
        self.pinned_column.setMaximumWidth(max(PINNED_MAX_WIDTH, needed))
        self.pinned_column.setVisible(bool(self._pinned) and not self._collapsed)
        self._restore_split()
        self._update_buttons()
        self._update_collapse_button()
        self._write_setting(SETTINGS_PINNED, list(self._pinned))
        self.pinned_changed.emit(list(self._pinned))

    def toggle_pin_current(self) -> None:
        """Pin the open flyout, or unpin the last pinned panel when no flyout is open."""
        if self._peek_id is not None:
            self.set_pinned(self._peek_id, True)
        elif self._pinned:
            self.set_pinned(self._pinned[-1], False)

    def set_dock_visible(self, visible: bool) -> None:
        """Show or hide the whole dock: rail, flyout and pinned column."""
        if not visible:
            self.close_peek()
        self.setVisible(visible)
        self.pinned_column.setVisible(visible and bool(self._pinned) and not self._collapsed)

    def restore_state(self) -> None:
        """Dock the panels that were docked in the last session, with their split."""
        stored = self._read_setting(SETTINGS_PINNED, [], list)
        if isinstance(stored, str):
            stored = [stored]
        collapsed, self._collapsed = self._collapsed, False
        for panel_id in stored or []:
            if panel_id in self._panels:
                self.set_pinned(panel_id, True)
        if collapsed:
            self.set_collapsed(True)

    @property
    def pinned_width(self) -> int:
        """Width for the pinned column: the persisted one, at least what the pinned panels need."""
        width = int(self._read_setting(SETTINGS_WIDTH, PINNED_WIDTH, int))
        return max(width, self.pinned_column.minimumWidth())

    def store_pinned_width(self, width: int) -> None:
        """Persist the width of the pinned column."""
        if width >= PINNED_MIN_WIDTH:
            self._write_setting(SETTINGS_WIDTH, int(width))

    # ------------------------------------------------------------------ internals
    def _set_shown(self, panel_id: str, shown: bool) -> None:
        try:
            self._panels[panel_id].set_shown(shown)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"System dock panel {panel_id} failed to react to show={shown}: {exc}")
        self.panel_shown.emit(panel_id, shown)

    def _update_buttons(self) -> None:
        for panel_id, button in self._buttons.items():
            button.set_state(self.is_shown(panel_id), panel_id in self._pinned)

    def _update_collapse_button(self) -> None:
        self.collapse_button.setVisible(bool(self._pinned) or self._collapsed)
        if self._collapsed:
            names = ", ".join(self._panels[p].label for p in self._pinned) or "none"
            self.collapse_button.set_icon_name("right_panel_open")
            self.collapse_button.setToolTip(f"Expand docked panels ({names})  ·  Ctrl+Shift+D")
        else:
            self.collapse_button.set_icon_name("right_panel_close")
            self.collapse_button.setToolTip("Collapse docked panels  ·  Ctrl+Shift+D")
        self.collapse_button.refresh_theme(self.tokens)

    def _store_split(self, *_args) -> None:
        if len(self._pinned) > 1:
            self._write_setting(SETTINGS_SPLIT, [int(v) for v in self.pinned_column.sizes()])

    def _restore_split(self) -> None:
        stored = self._read_setting(SETTINGS_SPLIT, [], list) or []
        try:
            sizes = [int(v) for v in stored]
        except (TypeError, ValueError):
            return
        if len(self._pinned) > 1 and len(sizes) == len(self._pinned) and all(sizes):
            self.pinned_column.setSizes(sizes)

    def _peek_geometry(self) -> QRect:
        parent = self._overlay_parent
        rail = QRect(self.mapTo(parent, QPoint(0, 0)), self.size())
        anchor = rail.left()
        if self.pinned_column.isVisible():
            anchor = self.pinned_column.mapTo(parent, QPoint(0, 0)).x()
        panel = self._panels.get(self._peek_id) if self._peek_id else None
        wanted = max(PEEK_WIDTH, (panel.min_width or 0) if panel is not None else 0)
        width = min(wanted + SHADOW, max(240, anchor - 80))
        if panel is None or not panel.preferred_height:
            return QRect(anchor - width, rail.top(), width, rail.height())
        # compact flyout: next to its button, as tall as its content
        height = min(rail.height(), HEADER_HEIGHT + panel.preferred_height)
        button = self._buttons[panel.panel_id]
        top = self.mapTo(parent, button.geometry().topLeft()).y()
        top = max(rail.top(), min(top, rail.bottom() + 1 - height))
        return QRect(anchor - width, top, width, height)

    def _on_button_hovered(self, panel_id: str, entered: bool) -> None:
        if entered:
            self._leave_timer.stop()
            if not self._hover_open or panel_id in self._pinned:
                return
            if self._peek_id is not None and not self._peek_sticky:
                if self._peek_id != panel_id:
                    self.open_panel(panel_id, sticky=False)
                return
            if self._peek_id is None:
                self._pending_hover = panel_id
                self._hover_timer.start()
        else:
            if self._pending_hover == panel_id:
                self._hover_timer.stop()
                self._pending_hover = None

    def _on_hover_timeout(self) -> None:
        panel_id, self._pending_hover = self._pending_hover, None
        if panel_id is None or self._peek_id is not None:
            return
        if self._buttons[panel_id].underMouse():
            self.open_panel(panel_id, sticky=False)

    def _pointer_inside(self) -> bool:
        pos = QCursor.pos()
        for widget in (self, self.peek):
            if widget.isVisible() and widget.rect().contains(widget.mapFromGlobal(pos)):
                return True
        return False

    def _on_leave_timeout(self) -> None:
        if self._peek_id is None or self._peek_sticky or self._pointer_inside():
            return
        self.close_peek()

    def enterEvent(self, event):  # pylint: disable=invalid-name
        self._leave_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        if self._peek_id is not None and not self._peek_sticky:
            self._leave_timer.start()
        super().leaveEvent(event)

    def _add_shortcut(self, sequence: str, slot) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(slot)
        self._shortcuts.append(shortcut)

    def _update_pulse(self) -> None:
        pulsing = any(p.indicator.pulse for p in self._panels.values())
        running = self._pulse.state() == QVariantAnimation.State.Running
        if pulsing and not running:
            self._pulse.start()
        elif not pulsing and running:
            self._pulse.stop()
            self.pulse_phase = 0.0

    def _on_pulse(self, value) -> None:
        self.pulse_phase = float(value)
        for panel_id, button in self._buttons.items():
            if self._panels[panel_id].indicator.pulse:
                button.update()

    def _install_app_filter(self, install: bool) -> None:
        """Watch clicks and Esc on the window while a panel peeks, to close it on outside clicks.

        The filter sits on the window's ``QWindow``, which sees every mouse and key event of the
        window before it is dispatched to a widget. An application-wide Python event filter
        would also see events of objects being destroyed, which crashes PySide.
        """
        if install == self._filter_installed:
            return
        if install:
            handle = self.window().windowHandle()
            if handle is None:
                return
            handle.installEventFilter(self)
            self._filtered_window = handle
        else:
            handle = getattr(self, "_filtered_window", None)
            if handle is not None and shiboken6.isValid(handle):
                handle.removeEventFilter(self)
            self._filtered_window = None
        self._filter_installed = install

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        etype = event.type()
        if watched is self._overlay_parent and etype in (QEvent.Type.Resize, QEvent.Type.Show):
            if self._peek_id is not None:
                QTimer.singleShot(0, self._reposition_peek)
            return False
        if watched is self.peek:
            if etype == QEvent.Type.Enter:
                self._leave_timer.stop()
            elif etype == QEvent.Type.Leave and self._peek_id is not None:
                if not self._peek_sticky:
                    self._leave_timer.start()
            return False
        if self._peek_id is None:
            return False
        if watched is not getattr(self, "_filtered_window", None):
            return False
        if etype == QEvent.Type.MouseButtonPress:
            # popups and dialogs opened from the panel are other windows: they keep it open
            pos = event.globalPosition().toPoint()
            if self.peek.rect().contains(self.peek.mapFromGlobal(pos)):
                self._peek_sticky = True  # working in the panel keeps it open
            elif not self.rect().contains(self.mapFromGlobal(pos)):
                self.close_peek()
        elif etype == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.close_peek()
        return False

    def _reposition_peek(self) -> None:
        if self._peek_id is not None and self._slide.state() != QPropertyAnimation.State.Running:
            self.peek.setGeometry(self._peek_geometry())

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        overlay = QAction("Open panels as flyouts over the workspace", menu)
        overlay.setCheckable(True)
        overlay.setChecked(self._mode == MODE_OVERLAY)
        overlay.toggled.connect(
            lambda checked: self.set_mode(MODE_OVERLAY if checked else MODE_DOCKED)
        )
        menu.addAction(overlay)
        hover = QAction("Open panels on hover", menu)
        hover.setCheckable(True)
        hover.setChecked(self._hover_open)
        hover.toggled.connect(self.set_hover_open)
        menu.addAction(hover)
        unpin = QAction("Undock all panels", menu)
        unpin.setEnabled(bool(self._pinned))
        unpin.triggered.connect(lambda: [self.set_pinned(p, False) for p in list(self._pinned)])
        menu.addAction(unpin)
        menu.exec(self.mapToGlobal(pos))

    def _on_theme_changed(self, *_args) -> None:
        self.tokens = ThemeTokens()
        for frame in self._frames.values():
            frame.refresh_theme(self.tokens)
        self._apply_style()
        self._update_collapse_button()
        self.update()
        self.peek.update()
        for button in self._buttons.values():
            button.update()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"#systemDockRail {{ border-left: 1px solid {self.tokens.border.name()}; }}"
        )
        self.pinned_column.setStyleSheet(
            f"#systemDockPinned {{ background: {self.tokens.bg.name()}; }}"
            f"#systemDockPinned::handle {{ background: {self.tokens.track.name()}; height: 1px; }}"
        )

    def showEvent(self, event):  # pylint: disable=invalid-name
        self._apply_style()
        super().showEvent(event)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        painter.setPen(self.tokens.border)
        painter.drawLine(0, 0, 0, self.height())
        painter.end()

    def _read_setting(self, key: str, default, kind):
        if self._settings is None:
            return default
        try:
            return self._settings.value(key, default, type=kind)
        except Exception:  # pylint: disable=broad-except
            return default

    def _write_setting(self, key: str, value) -> None:
        if self._settings is None:
            return
        try:
            self._settings.setValue(key, value)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"Could not persist system dock setting {key}: {exc}")

    def cleanup(self) -> None:
        """Stop timers, detach event filters and release the panels."""
        if self._cleaned:
            return
        self._cleaned = True
        self._hover_timer.stop()
        self._leave_timer.stop()
        self._slide.stop()
        self._pulse.stop()
        self._install_app_filter(False)
        if shiboken6.isValid(self._overlay_parent):
            self._overlay_parent.removeEventFilter(self)
        app = QApplication.instance()
        theme = getattr(app, "theme", None)
        if theme is not None and hasattr(theme, "theme_changed"):
            try:
                theme.theme_changed.disconnect(self._on_theme_changed)
            except (RuntimeError, TypeError):
                pass
        for panel in self._panels.values():
            panel.cleanup()
        if shiboken6.isValid(self.pinned_column):
            self.pinned_column.deleteLater()
