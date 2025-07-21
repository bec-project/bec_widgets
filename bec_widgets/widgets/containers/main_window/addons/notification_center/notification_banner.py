"""
Notification banner and centre widgets for displaying transient messages in a Qt application.

This module provides:
- NotificationToast: A widget for individual notification messages with severity, progress, and optional traceback.
- NotificationCentre: A scrollable container for stacking and managing multiple notifications.
- NotificationIndicator: A status-bar widget for filtering and toggling notification visibility.

Intended for use in desktop applications to provide user feedback, warnings, and error reporting.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from enum import Enum, auto
from typing import Literal
from uuid import uuid4

import pyqtgraph as pg
from bec_lib.alarm_handler import Alarms  # external enum
from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QObject, QTimer
from qtpy.QtWidgets import QApplication, QFrame, QMainWindow, QScrollArea, QWidget

from bec_widgets import SafeProperty, SafeSlot
from bec_widgets.utils import BECConnector
from bec_widgets.utils.widget_io import WidgetIO


class SeverityKind(str, Enum):
    INFO = "info"
    WARNING = "warning"
    MINOR = "minor"
    MAJOR = "major"


SEVERITY = {
    "info": {"color": "#00e676", "icon": "info"},  # green accent
    "warning": {"color": "#ffca28", "icon": "emergency_home"},  # yellow accent
    "minor": {"color": "#ff9100", "icon": "report"},  # orange accent
    "major": {"color": "#ff5252", "icon": "dangerous"},  # red accent
}

DARK_PALETTE = {
    "base": "#21272d",
    "title": "#ffffff",
    "body": "#cfd8dc",
    "separator": "rgba(255,255,255,40)",
}

LIGHT_PALETTE = {
    "base": "#e9ecef",
    "title": "#212121",
    "body": "#424242",
    "separator": "rgba(0,0,0,40)",
}


class NotificationToast(QFrame):
    """
    Notification toast widget with title, body, optional traceback,
    and lifetime progress bar. Emits signals on close and expire.

    Signals:
        closed: Emitted when the toast is closed by the user.
        expired: Emitted when the toast's lifetime expires.
        expanded: Emitted when the traceback is expanded or collapsed.

    Attributes:
        created (datetime): Timestamp when the toast was created.
        title (str): Title of the toast.
        body (str): Body text of the toast.
        kind (str): Severity kind of the toast ("info", "warning", "error").
        traceback (str | None): Optional traceback string for errors.
        lifetime_ms (int): Lifetime in milliseconds before auto-expire.
        theme (str): Theme to apply ("dark" or "light").
    """

    closed = QtCore.Signal()
    expired = QtCore.Signal()
    expanded = QtCore.Signal()

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        title: str,
        body: str,
        kind: SeverityKind | str = SeverityKind.INFO,
        traceback: str | None = None,
        fixed_width: int = 420,
        lifetime_ms: int = 5000,
        theme: Literal["light", "dark"] | None = None,
    ) -> None:
        super().__init__(parent=parent)
        # keep toast at a fixed width – prevents size oscillation
        self.setFixedWidth(fixed_width)
        self.setObjectName("NotificationToast")
        self._hover = False

        # QProperties' private fields
        self._title = title
        self._body = body
        self._kind = kind if isinstance(kind, SeverityKind) else SeverityKind(kind)
        self._traceback = traceback
        self._accent_color = QtGui.QColor(SEVERITY[self._kind.value]["color"])
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)

        self.created = datetime.now()

        icon_btn = QtWidgets.QToolButton()
        icon_btn.setIcon(
            material_icon(
                icon_name=SEVERITY[self._kind.value]["icon"],
                color=SEVERITY[self._kind.value]["color"],
                filled=True,
                size=(24, 24),
                convert_to_pixmap=False,
            )
        )
        icon_btn.setIconSize(QtCore.QSize(24, 24))
        icon_btn.setAutoRaise(True)  # flat look, no border
        icon_btn.setEnabled(False)  # purely decorative

        self._icon_btn = icon_btn  # keep reference for later colour update
        bg = QtGui.QColor(SEVERITY[self._kind.value]["color"])
        bg.setAlphaF(0.30)
        icon_bg = bg.name(QtGui.QColor.HexArgb)
        icon_btn.setFixedSize(40, 40)
        icon_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: {icon_bg};
                border: none;
                border-radius: 20px;   /* perfect circle */
            }}
            """
        )

        title_lbl = QtWidgets.QLabel(self._title)

        body_lbl = QtWidgets.QLabel(self._body)
        body_lbl.setWordWrap(True)

        self.time_lbl = QtWidgets.QLabel()
        self._update_relative_time()
        # enable absolute timestamp on hover
        self.time_lbl.setCursor(QtCore.Qt.PointingHandCursor)
        self.time_lbl.installEventFilter(self)
        self._showing_absolute = False

        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setObjectName("toastCloseBtn")
        self.close_btn.clicked.connect(self.close)

        self.expand_btn = QtWidgets.QPushButton("▼" if self._traceback else "")
        self.expand_btn.setObjectName("toastExpandBtn")
        self.expand_btn.setVisible(bool(self._traceback))
        self.expand_btn.clicked.connect(self._toggle_traceback)

        layout = QtWidgets.QVBoxLayout(self)
        # main vertical layout
        layout.setSpacing(4)
        layout.setContentsMargins(12, 12, 12, 8)

        # usable width inside the card (account for left/right margins)
        margins_h = layout.contentsMargins().left() + layout.contentsMargins().right()
        inner_width = fixed_width - margins_h

        # --- horizontal row: icon | separator | text column ---
        content_row = QtWidgets.QHBoxLayout()
        content_row.setSpacing(12)

        # subtle vertical separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Plain)
        separator.setFixedWidth(1)

        # keep refs for theme switching later
        self._title_lbl = title_lbl
        self._body_lbl = body_lbl
        self._separator = separator

        # text column = header row + body label
        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(2)

        header_row = QtWidgets.QHBoxLayout()
        header_row.addWidget(title_lbl)
        header_row.addStretch(1)
        header_row.addWidget(self.time_lbl)
        header_row.addWidget(self.expand_btn)
        header_row.addWidget(self.close_btn)

        text_col.addLayout(header_row)
        text_col.addWidget(body_lbl)

        content_row.addWidget(icon_btn)
        content_row.addWidget(separator)
        content_row.addLayout(text_col)

        layout.addLayout(content_row)

        self.trace_view = QtWidgets.QPlainTextEdit(self._traceback or "")
        self.trace_view.setVisible(False)
        self.trace_view.setReadOnly(True)
        # base style; colours will be updated in apply_theme
        self.trace_view.setStyleSheet("border:none; border-radius:8px;")

        layout.addWidget(self.trace_view)

        # coloured progress bar at the very bottom
        self.progress = QtWidgets.QFrame(self)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(
            f"background:{SEVERITY[self._kind.value]['color']}; border:none; border-radius: 2px;"
        )
        layout.addWidget(self.progress)

        # start progress bar at full width
        self.progress.setMaximumWidth(inner_width)

        # listen for global theme updates
        self._connect_to_theme_change()

        # If *theme* is None the method will auto‑detect from QApplication
        self.apply_theme(theme)

        self._timer = QtCore.QTimer(self, interval=60_000, timeout=self._update_relative_time)
        self._timer.start()

        # subtle drop‑shadow
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 2)
        shadow.setColor(QtGui.QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

        # lifetime progress animation
        self._lifetime = max(0, lifetime_ms)  # 0 → never expire
        self._progress_anim: QtCore.QPropertyAnimation | None = None

        if self._lifetime > 0:
            self._start_progress_animation()
        else:
            self.progress.hide()

        # flag to indicate this toast has fully expired (progress bar finished)
        self._expired = False

    # ------------------------------------------------------------------
    def _connect_to_theme_change(self):
        """Connect this toast to the global theme‑updated signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self.apply_theme)

    # helper methods -----------------------------------------------------
    def _current_inner_width(self) -> int:
        m = self.layout().contentsMargins()
        return self.width() - (m.left() + m.right())

    # ------------------------------------------------------------------
    def _start_progress_animation(self):
        """(Re)start the linear width‑shrink animation."""
        if self._progress_anim is not None:
            self._progress_anim.stop()

        inner_w = self._current_inner_width()
        self.progress.setMaximumWidth(inner_w)

        self._progress_anim = QtCore.QPropertyAnimation(self.progress, b"maximumWidth", self)
        self._progress_anim.setStartValue(inner_w)
        self._progress_anim.setEndValue(0)
        self._progress_anim.setDuration(self._lifetime)
        self._progress_anim.setEasingCurve(QtCore.QEasingCurve.Linear)
        self._progress_anim.finished.connect(self._on_progress_finished)
        self._progress_anim.start()

    def _on_progress_finished(self):
        """Handle animation end → toast lifetime expired."""
        if self._expired:  # already processed
            return
        self._expired = True
        self.expired.emit()

    ########################################
    # Qt Properties
    ########################################
    @SafeProperty(str)
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value
        self._title_lbl.setText(value)

    @SafeProperty(str)
    def body(self):
        return self._body

    @body.setter
    def body(self, value):
        self._body = value
        self._body_lbl.setText(value)

    @SafeProperty(SeverityKind)
    def kind(self):
        return self._kind

    @kind.setter
    def kind(self, value):
        value = value if isinstance(value, SeverityKind) else SeverityKind(value)
        self._kind = value
        self._accent_color = QtGui.QColor(SEVERITY[value.value]["color"])
        self._separator.setStyleSheet(f"color: {self._accent_color.name()};")
        # update circular badge background colour
        bg = QtGui.QColor(SEVERITY[value.value]["color"])
        bg.setAlphaF(0.30)
        icon_bg = bg.name(QtGui.QColor.HexArgb)
        self._icon_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: {icon_bg};
                border: none;
                border-radius: 20px;
            }}
            """
        )
        self.apply_theme(self._theme)
        # keep injected gradient in sync
        if getattr(self, "_hg_enabled", False):
            self._hg_cols[0] = self._accent_color

    @SafeProperty(str)
    def traceback(self):
        return self._traceback

    @traceback.setter
    def traceback(self, value):
        self._traceback = value
        self.trace_view.setPlainText(value)
        self.expand_btn.setVisible(bool(value))

    def apply_theme(self, theme: str | None = None):
        """
        Apply the theme to the toast and its content.

        Args:
            theme(str | None): "light" or "dark". If None, auto-detects from QApplication.
        """
        # determine effective theme
        if theme is None:
            app = QApplication.instance()
            theme = getattr(getattr(app, "theme", None), "theme", "dark")
        theme = theme.lower()
        self._theme = theme
        palette = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE

        # base colour for card
        self._base_color = QtGui.QColor(palette["base"])

        # title / body colours
        self._title_lbl.setStyleSheet(
            f"font-weight: 700; font-size:16px; color: {palette['title']};"
        )
        body_col = "#e0e0e0" if theme == "dark" else palette["body"]
        self._body_lbl.setStyleSheet(f"color:{body_col};")
        self.time_lbl.setStyleSheet(f"color:{body_col};")

        # separator colour
        self._separator.setStyleSheet(f"color: {palette['separator']};")

        # buttons (text colour)
        base_btn_color = palette["title"]
        self.setStyleSheet(
            """
            #NotificationToast {
                background: transparent;
                border-radius: 12px;
                color: %s;
            }
            #NotificationToast QPushButton {
                background: transparent;
                border: none;
                color: %s;
                font-size: 14px;
            }
            #NotificationToast QPushButton:hover { color: %s; }
            """
            % (base_btn_color, base_btn_color, self._accent_color.name())
        )
        # traceback panel colours
        trace_bg = "#1e1e1e" if theme == "dark" else "#f0f0f0"
        self.trace_view.setStyleSheet(
            f"""
            background:{trace_bg};
            color:{palette['body']};
            border:none;
            border-radius:8px;
            """
        )

        self.update()

    ########################################
    # private slots methods
    ########################################

    def _update_relative_time(self) -> None:
        if getattr(self, "_showing_absolute", False):
            return  # don't overwrite while user is viewing absolute time
        seconds = int((datetime.now() - self.created).total_seconds())
        if seconds < 10:
            text = "just now"
        elif seconds < 3600:
            text = f"{seconds // 60} min ago"
        elif seconds < 86400:
            text = f"{seconds // 3600} h ago"
        else:
            text = f"{seconds // 86400} d ago"
        self.time_lbl.setText(text)

    def _absolute_time_string(self) -> str:
        # convert created (UTC) to local time for display
        local = self.created.astimezone()
        return local.strftime("%Y-%m-%d %H:%M:%S")

    # (progress timer logic removed; now handled by animation)

    ########################################
    # Event Filters
    ########################################
    def eventFilter(self, watched, event):
        # timestamp label → toggle absolute time
        if watched is self.time_lbl:
            if event.type() == QtCore.QEvent.Enter and not self._showing_absolute:
                self.time_lbl.setText(self._absolute_time_string())
                self._showing_absolute = True
            elif event.type() == QtCore.QEvent.Leave and self._showing_absolute:
                self._showing_absolute = False
                self._update_relative_time()
        return super().eventFilter(watched, event)

    def enterEvent(self, event):
        """
        Pause the countdown while the cursor is over the toast, and reset the
        elapsed time and progress bar to full width.
        """
        if getattr(self, "_expired", False):
            return super().enterEvent(event)
        self._hover = True
        if self._progress_anim is not None:
            self._progress_anim.stop()
        # reset progress bar to full width
        self.progress.setMaximumWidth(self._current_inner_width())
        super().enterEvent(event)

    def leaveEvent(self, event):
        """
        Resume the countdown when the cursor leaves, continuing from the
        paused progress rather than restarting.
        """
        if getattr(self, "_expired", False):
            return super().leaveEvent(event)
        self._hover = False
        if self._lifetime > 0 and not self._expired:
            self._start_progress_animation()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect()
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect.adjusted(0, 0, -1, -1), 12, 12)

        # solid base
        painter.fillPath(path, self._base_color)

        # accent gradient, fades to transparent
        grad = QtGui.QLinearGradient(0, 0, self.width() * 0.7, 0)
        accent = QtGui.QColor(self._accent_color)
        accent.setAlpha(50)
        grad.setColorAt(0.0, accent)
        fade = QtGui.QColor(self._accent_color)
        fade.setAlpha(0)
        grad.setColorAt(1.0, fade)
        painter.fillPath(path, grad)

        painter.end()
        super().paintEvent(event)

    def _toggle_traceback(self) -> None:
        if not self.traceback:
            return
        visible = not self.trace_view.isVisible()
        self.trace_view.setVisible(visible)
        self.expand_btn.setText("▲" if visible else "▼")
        self.expanded.emit()

    def close(self) -> None:
        self.closed.emit()
        QtWidgets.QApplication.instance().removeEventFilter(self)
        super().close()  # this will remove the widget from its parent


class NotificationCentre(QScrollArea):
    """
    Right‑aligned scroll area that stacks NotificationToast widgets.
    Newest toast appears at the top; a slim vertical scrollbar emerges
    only when needed, so the main window size never changes.

    Signals:
        toast_added: Emitted when a new toast is added, with its kind.
        toast_removed: Emitted when a toast is removed, with its kind.

    Attributes:
        fixed_width (int): Fixed width of the notification centre.
        margin (int): Margin around the notification centre.
    """

    toast_added = QtCore.Signal(str)  # kind
    toast_removed = QtCore.Signal(str)  # kind
    counts_updated = QtCore.Signal(dict)  # emits {SeverityKind: int, ...}

    # ------------------------------------------------------------------
    def _emit_counts(self):
        """Emit a dict with current per‑kind counts."""
        cnt = {k: 0 for k in SeverityKind}
        for t in self.toasts:
            cnt[t.kind] += 1
        self.counts_updated.emit(cnt)

    def __init__(self, parent=None, *, fixed_width: int = 420, margin: int = 16):
        super().__init__(parent=parent)
        self.setObjectName("NotificationCentre")
        app = QApplication.instance()
        self._theme = getattr(getattr(app, "theme", None), "theme", "dark").lower()

        self.setWidgetResizable(True)
        # transparent background so only the toast cards are visible
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(
            """
            #NotificationCentre { background: transparent; }
            #NotificationCentre QScrollBar:vertical {
                background: transparent;
                width: 4px;
                margin: 0;
            }
            #NotificationCentre QScrollBar::handle:vertical {
                background: rgba(255,255,255,150);
                border-radius: 1px;
                min-height: 20px;
            }
            #NotificationCentre QScrollBar::add-line:vertical,
            #NotificationCentre QScrollBar::sub-line:vertical { height: 0; }
            #NotificationCentre QScrollBar::add-page:vertical,
            #NotificationCentre QScrollBar::sub-page:vertical { background: transparent; }
            """
        )
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setFixedWidth(fixed_width)

        # inner container that actually holds the toasts
        self._container = QtWidgets.QWidget()
        self._container.setAttribute(QtCore.Qt.WA_StyledBackground, False)
        self._container.setStyleSheet("background: transparent;")
        self._layout = QtWidgets.QVBoxLayout(self._container)
        self._layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
        self._layout.setContentsMargins(4, 18, 4, 2)  # to not overlap with scroll bar
        self._layout.setSpacing(8)

        # full‑width "Clear-All" button
        self._clear_btn = QtWidgets.QPushButton("Clear All")
        self._clear_btn.clicked.connect(self.clear_all_across_app)
        self._clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        # apply initial palette‑dependent style
        palette = DARK_PALETTE if self._theme == "dark" else LIGHT_PALETTE
        self._clear_btn.setStyleSheet(self._clear_btn_css(palette))
        self._clear_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        # initial width equals current toast width
        self._layout.addWidget(self._clear_btn)

        # spacer keeps newest toasts at the very top
        self._bottom_spacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self._layout.addItem(self._bottom_spacer)

        self.setWidget(self._container)

        self.toasts: list[NotificationToast] = []
        self._soft_hidden: set[NotificationToast] = set()
        self._margin = margin

        # ensure the scroll area expands vertically
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)

        # track whether user explicitly hid the panel
        self._user_hidden = False
        # True while panel is explicitly showing all toasts
        self._showing_all = False  # default: auto‑expire regime

        # active kind filter, None = show all
        self._active_filter: set[str] | None = None

        # start hidden; becomes visible when first toast arrives
        self.setVisible(False)
        # listen for any application‑wide theme update signal
        self._connect_to_theme_change()

        # watch parent resize so we can recompute max-height
        if self.parent():
            self.parent().installEventFilter(self)
        self._replayed = False
        QTimer.singleShot(0, self._replay_active_notifications)

    def _clear_btn_css(self, palette: dict[str, str]) -> str:
        """Return a stylesheet string for the clear‑all button."""
        return f"""
            QPushButton {{
                background: {palette['base']};
                color: {palette['title']};
                padding: 6px 0;
                border-radius: 4px;
                font-weight: 600;
            }}
            """

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self.apply_theme)

    #  public API
    def add_notification(
        self,
        title: str,
        body: str,
        kind: SeverityKind = SeverityKind.INFO,
        traceback: str | None = None,
        lifetime_ms: int = 5000,
        theme: str | None = None,
        notification_id: str | None = None,
    ) -> NotificationToast:
        """
        Create a new toast and insert it just above the bottom spacer.

        Args:
            title(str): Title of the notification.
            body(str): Body text of the notification.
            kind(SeverityKind): Severity kind of the notification.
            traceback(str | None): Optional traceback string for errors.
            lifetime_ms(int): Lifetime in milliseconds before auto-expire.
            theme(str | None): Theme to apply ("dark" or "light"). Defaults to current theme.

        Returns:
            NotificationToast: The created toast widget.
        """
        # ensure a shared ID for this notification
        if notification_id is None:
            notification_id = uuid4().hex
        # compute width available for a toast: viewport minus layout margins
        vp_w = self.viewport().width()  # viewport is always available
        margins = self._layout.contentsMargins().left() + self._layout.contentsMargins().right()
        fixed_width = max(120, vp_w - margins)

        toast = NotificationToast(
            title=title,
            body=body,
            kind=kind,
            traceback=traceback,
            parent=self,
            fixed_width=fixed_width,
            lifetime_ms=lifetime_ms,
            theme=theme or self._theme,
        )
        # tag with shared ID and hook closures to the singleton broker
        toast.notification_id = notification_id
        broker = BECNotificationBroker()
        toast.closed.connect(lambda nid=notification_id: broker.notification_closed.emit(nid))
        toast.expired.connect(lambda nid=notification_id: broker.notification_closed.emit(nid))
        toast.closed.connect(lambda: self._hide_notification(toast))
        toast.expired.connect(lambda t=toast: self._handle_expire(t))
        toast.expanded.connect(self._adjust_height)

        # newest toast right beneath the header row (index 1)
        self._layout.insertWidget(1, toast, 0, QtCore.Qt.AlignHCenter)
        self.toasts.insert(0, toast)
        self.toast_added.emit(kind.value)
        # ensure the centre is visible whenever there is at least one toast
        if not self.isVisible():
            self.setVisible(True)
        QTimer.singleShot(0, self._adjust_height)
        self._emit_counts()
        return toast

    def remove_notification(self, notification_id: str) -> None:
        """Close a specific notification in this centre if present."""
        for toast in list(self.toasts):
            if getattr(toast, "notification_id", None) == notification_id:
                self._hide_notification(toast)

    # ------------------------------------------------------------------
    @SafeSlot(str)
    def apply_theme(self, theme: Literal["light", "dark"] = "dark"):
        """
        Apply a dark/light theme to the notification centre and all its toasts.
        """
        theme = theme.lower()
        if theme == self._theme:
            return
        self._theme = theme
        for toast in self.toasts:
            toast.apply_theme(theme)
        # refresh clear‑all button colours
        palette = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
        self._clear_btn.setStyleSheet(self._clear_btn_css(palette))

    def toggle_theme(self):
        """Toggle between light and dark themes."""
        self.apply_theme("light" if self._theme == "dark" else "dark")

    # ------------------------------------------------------------------
    @SafeSlot(str)
    def change_theme(self, theme: str):
        """
        Qt‑slot wrapper around apply_theme so external callers
        (or a global theme signal) can switch themes with a single emit.
        """
        self.apply_theme(theme)

    # filtering
    def apply_filter(self, kinds: set[SeverityKind] | None):
        """
        Show only toasts whose kind is in *kinds*.
        Pass None to clear filter and show everything.
        """
        self._active_filter = kinds
        for t in self.toasts:
            t.setVisible(True if kinds is None else t.kind in kinds)
        # auto‑collapse if no toast passes the filter
        self.setVisible(any(t.isVisible() for t in self.toasts))
        self._adjust_height()

    #  helper slots
    def _hide_notification(self, toast: NotificationToast):
        """Remove a toast that has been closed or expired."""
        if toast in self.toasts:
            self.toasts.remove(toast)
            self._layout.removeWidget(toast)
            self.toast_removed.emit(toast.kind)
            toast.deleteLater()
            self._emit_counts()
            self._adjust_height()
            # collapse if either list is empty OR nothing visible to user
            if not self.toasts or not any(t.isVisible() for t in self.toasts):
                self.setVisible(False)

    def _handle_expire(self, toast: NotificationToast):
        """
        Handle a toast that has expired (lifetime reached).

        Args:
            toast(NotificationToast): The toast that has expired.
        """
        if self._active_filter is None or toast.kind not in self._active_filter:
            self._soft_hide(toast)

    def _soft_hide(self, toast: NotificationToast):
        """
        Softly hide a toast, keeping it in the list but not visible.

        Args:
            toast(NotificationToast): The toast to hide.
        """
        if toast not in self.toasts:
            return
        toast.setVisible(False)
        self._adjust_height()
        # collapse centre when nothing is visible anymore
        if not any(t.isVisible() for t in self.toasts):
            self.setVisible(False)
        self._soft_hidden.add(toast)

    def _replay_active_notifications(self):
        """Replay notifications stored in broker for this centre."""
        if self._replayed:
            return
        self._replayed = True
        broker = BECNotificationBroker()
        for nid, params in list(broker._active_notifications.items()):
            toast = self.add_notification(
                title=params["title"],
                body=params["body"],
                kind=params["kind"],
                traceback=params["traceback"],
                lifetime_ms=params["lifetime_ms"],
                notification_id=nid,
            )
            self._soft_hide(toast)

    # batch operations
    def clear_all_across_app(self):
        all_centers = WidgetIO.find_widgets(NotificationCentre)
        for centre in all_centers:
            centre.clear_all()

    def clear_all(self):
        """Immediately close every toast."""
        for t in list(self.toasts):
            self._hide_notification(t)

    def hide_all(self):
        """Hide the entire notification centre until a new toast arrives."""
        self._user_hidden = True
        self._showing_all = False
        self._active_filter = None  # clear any residual filter
        # hide every currently visible toast but keep references
        for t in self.toasts:
            if t.isVisible():
                t.setVisible(False)
                self._soft_hidden.add(t)
        self.setVisible(False)

    def show_all(self):
        """Show (unhide) the notification centre."""
        self._showing_all = True
        self._user_hidden = False
        self.setVisible(True)
        # bring back any soft‑hidden toasts, respecting active filter
        for t in reversed(self.toasts):  # iterate bottom‑up so oldest stays top
            if self._active_filter is not None and t.kind not in self._active_filter:
                continue  # keep hidden if not in current filter
            if not t.isVisible():
                t.setVisible(True)
                self._soft_hidden.discard(t)

    #  layout helpers and filters
    def _adjust_height(self):
        if not self.parent():
            return
        avail = self.parent().height() - 2 * self._margin
        content_h = self._container.sizeHint().height() + 4
        self.setFixedHeight(min(content_h, avail))

    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() == QtCore.QEvent.Resize:
            self._adjust_height()
        return super().eventFilter(watched, event)


class NotificationIndicator(QWidget):
    """Status-bar widget with 3 icons and live counts; click toggles panel."""

    KINDS: tuple[SeverityKind, ...] = (
        SeverityKind.INFO,
        SeverityKind.WARNING,
        SeverityKind.MINOR,
        SeverityKind.MAJOR,
    )

    # ────────────────────────── outbound commands ──────────────────────────
    filter_changed = QtCore.Signal(object)  # set[SeverityKind] or None
    show_all_requested = QtCore.Signal()
    hide_all_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(2)  # tighter gap between buttons

        kinds_enum = self.KINDS
        kinds = [k.value for k in kinds_enum]
        self._btn: dict[SeverityKind, QtWidgets.QToolButton] = {}

        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(False)
        self._btn_rev: dict[QtWidgets.QToolButton, SeverityKind] = {}

        for k in kinds:
            b = QtWidgets.QToolButton(
                autoRaise=True, checkable=True, cursor=QtCore.Qt.PointingHandCursor
            )
            sev = SeverityKind(k)
            icon = material_icon(
                icon_name=SEVERITY[sev.value]["icon"],
                color=SEVERITY[sev.value]["color"],
                filled=True,
                size=(20, 20),
                convert_to_pixmap=False,
            )
            b.setIcon(icon)
            b.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            lay.addWidget(b)

            self._btn[SeverityKind(k)] = b
            self._group.addButton(b)
            self._btn_rev[b] = SeverityKind(k)

        self._group.buttonToggled.connect(self._button_toggled)

        # minimalistic look: no frames or backgrounds on the buttons
        self.setStyleSheet(
            """
            QToolButton {
                border: none;
                background: transparent;
                padding: 2px 4px;
                border-radius: 4px;
            }
            QToolButton:checked {
                background: rgba(255, 255, 255, 40);
                font-weight: 600;
            }
            """
        )

        # initial state: none checked (auto‑dismiss behaviour)
        for k in kinds:
            self._btn[SeverityKind(k)].setChecked(False)
        # start hidden; will appear on first toast
        self.setVisible(False)

        # start with zero counts
        self.update_counts({k: 0 for k in self.KINDS})

    # ------------------------------------------------------------------
    @QtCore.Slot(dict)
    def update_counts(self, cnt: dict):
        """Slot: receive per‑kind counts from the centre."""
        total = sum(cnt.values())
        # update per‑kind text and visibility
        for k in self.KINDS:
            self._btn[k].setText(str(cnt[k]))
            self._btn[k].setVisible(cnt[k] > 0)

        # auto‑hide/show whole indicator
        self.setVisible(total > 0)

    def _checked_kinds(self) -> set[SeverityKind]:
        """Return kinds whose buttons are currently checked."""
        return {k for k in self.KINDS if self._btn[k].isChecked()}

    def _button_toggled(self, button: QtWidgets.QAbstractButton, checked: bool):
        """
        Central toggle handler wired to the QButtonGroup.
        """
        kind = self._btn_rev.get(button)
        if kind is None:
            return

        # Recompute the current set of checked kinds
        kinds = {k for k in self.KINDS if self._btn[k].isChecked()}
        if kinds:
            self.filter_changed.emit(kinds)
            self.show_all_requested.emit()
        else:
            self.hide_all_requested.emit()


class BECNotificationBroker(BECConnector, QObject):
    """
    Singleton notification broker that listens to the global notification signal and
    posts notifications to registered NotificationCentres.
    """

    RPC = False

    _instance: BECNotificationBroker | None = None
    _initialized: bool = False

    notification_closed = QtCore.Signal(str)

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, parent=None, gui_id: str = None, client=None, **kwargs):
        if self._initialized:
            return
        super().__init__(parent=parent, gui_id=gui_id, client=client, **kwargs)
        self._err_util = self.error_utility
        # listen to incoming alarms and scan status
        self.bec_dispatcher.connect_slot(self.post_notification, MessageEndpoints.alarm())
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        # propagate any close events to all centres
        self.notification_closed.connect(self._clear_across_centres)
        self._initialized = True
        # store active notifications to replay for new centres
        self._active_notifications: dict[str, dict] = {}

    def _clear_across_centres(self, notification_id: str) -> None:
        """Close the notification with this ID in every NotificationCentre."""
        for centre in WidgetIO.find_widgets(NotificationCentre):
            centre.remove_notification(notification_id)
        # remove from active store once closed
        self._active_notifications.pop(notification_id, None)

    @SafeSlot(dict, dict)
    def post_notification(self, msg: dict, meta: dict) -> None:
        """
        Called when a new alarm arrives. Builds and pushes a toast to each centre
        with a shared notification_id, and hooks its close/expire signals.
        """
        centres = WidgetIO.find_widgets(NotificationCentre)
        kind = self._banner_kind_from_severity(msg.get("severity", 0))
        # build title and body
        scan_id = meta.get("scan_id")
        scan_number = meta.get("scan_number")
        formatted_trace = self._err_util.format_traceback(msg.get("msg", ""))
        short_msg = self._err_util.parse_error_message(formatted_trace)
        title = msg.get("alarm_type", "Alarm")
        if scan_number:
            title += f" - Scan #{scan_number}"
        body_text = short_msg
        # build detailed traceback
        sections: list[str] = []
        if scan_id:
            sections.extend(["-------- SCAN_ID --------\n", scan_id])
        sections.extend(["-------- TRACEBACK --------", formatted_trace])
        source = msg.get("source")
        if source:
            source_pretty = json.dumps(source, indent=4, default=str)
            sections.extend(["", "-------- SOURCE --------", source_pretty])
        detailed_trace = "\n".join(sections)
        lifetime = 0 if kind == SeverityKind.MAJOR else 5_000

        # generate one ID for all toasts of this event
        notification_id = uuid4().hex
        # record this notification for future centres
        self._active_notifications[notification_id] = {
            "title": title,
            "body": body_text,
            "kind": kind,
            "traceback": detailed_trace,
            "lifetime_ms": lifetime,
        }
        for centre in centres:
            toast = centre.add_notification(
                title=title,
                body=body_text,
                traceback=detailed_trace,
                kind=kind,
                lifetime_ms=lifetime,
                notification_id=notification_id,
            )
            # broadcast any close or expire
            toast.closed.connect(lambda nid=notification_id: self.notification_closed.emit(nid))
            toast.expired.connect(lambda nid=notification_id: self.notification_closed.emit(nid))

    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, meta: dict) -> None:
        """
        Hides all the notifications when a new scan starts.

        Args:
            msg(dict): The message containing scan status.
            meta(dict): Metadata about the scan.
        """
        msg = msg or {}
        status = msg.get("status")
        if status == "open":
            from bec_widgets.utils.widget_io import WidgetIO

            for centre in WidgetIO.find_widgets(NotificationCentre):
                centre.hide_all()

    @staticmethod
    def _banner_kind_from_severity(severity: int) -> "SeverityKind":
        """
        Translate an integer severity (0/1/2) into a SeverityKind enum.
        Unknown values fall back to SeverityKind.WARNING.
        """
        try:
            return SeverityKind[Alarms(severity).name]  # e.g. WARNING → SeverityKind.WARNING
        except (ValueError, KeyError):
            return SeverityKind.WARNING

    @classmethod
    def reset_singleton(cls):
        """
        Reset the singleton instance of the BECNotificationBroker.
        """
        cls._instance = None
        cls._initialized = False

    def cleanup(self):
        """Disconnect from the notification signal."""
        self.bec_dispatcher.disconnect_slot(self.post_notification, MessageEndpoints.alarm())
        self.bec_dispatcher.disconnect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.remove()


########################################
# Demo App
########################################
class DemoWindow(QMainWindow):  # pragma: no cover
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setWindowTitle("Notification Centre Demo")
        self.resize(900, 500)

        # ----- central container -------------------------------------------------
        central_container = QtWidgets.QWidget(self)
        main_container_layout = QtWidgets.QHBoxLayout(central_container)

        # ----- main content ------------------------------------------------------
        base = QtWidgets.QWidget()
        main_lay = QtWidgets.QHBoxLayout(base)

        # control column
        ctrl_col = QtWidgets.QVBoxLayout()
        self.info_btn = QtWidgets.QPushButton("Add Info")
        self.warning_btn = QtWidgets.QPushButton("Add Alarm Warning")
        self.minor_btn = QtWidgets.QPushButton("Add Alarm Minor")
        self.major_btn = QtWidgets.QPushButton("Add Alarm Major")
        # Raise buttons simulate alarms
        self.raise_warning_btn = QtWidgets.QPushButton("Raise Warning ")
        self.raise_minor_btn = QtWidgets.QPushButton("Raise Minor ")
        self.raise_major_btn = QtWidgets.QPushButton("Raise Major ")

        for w in (
            self.info_btn,
            self.warning_btn,
            self.minor_btn,
            self.major_btn,
            self.raise_warning_btn,
            self.raise_minor_btn,
            self.raise_major_btn,
        ):
            ctrl_col.addWidget(w)
        ctrl_col.addStretch(1)
        main_lay.addLayout(ctrl_col)

        # dummy plot for visual weight
        plot = pg.PlotWidget()
        plot.plot([1, 3, 2, 4, 3, 5])
        main_lay.addWidget(plot, 1)

        # add base content to the container layout
        main_container_layout.addWidget(base)

        # ----- notification centre overlay --------------------------------------
        self.notification_centre = NotificationCentre(parent=self)
        self.notification_centre.raise_()  # keep above base content

        self.setCentralWidget(central_container)
        self.notification_broker = BECNotificationBroker(parent=self)

        # ----- wiring ------------------------------------------------------------
        self._counter = 1
        self.info_btn.clicked.connect(lambda: self._post("info"))
        self.warning_btn.clicked.connect(lambda: self._post("warning"))
        self.minor_btn.clicked.connect(lambda: self._post("minor"))
        self.major_btn.clicked.connect(lambda: self._post("major"))
        # Raise buttons simulate alarms
        self.raise_warning_btn.clicked.connect(lambda: self._raise_error(Alarms.WARNING))
        self.raise_minor_btn.clicked.connect(lambda: self._raise_error(Alarms.MINOR))
        self.raise_major_btn.clicked.connect(lambda: self._raise_error(Alarms.MAJOR))

        # indicator in status bar
        indicator = NotificationIndicator(self)
        self.statusBar().addPermanentWidget(indicator)
        # wire indicator and centre via signals
        self.notification_centre.counts_updated.connect(indicator.update_counts)
        indicator.filter_changed.connect(self.notification_centre.apply_filter)
        indicator.show_all_requested.connect(self.notification_centre.show_all)
        indicator.hide_all_requested.connect(self.notification_centre.hide_all)

    # ------------------------------------------------------------------
    def _post(self, kind):
        expire = 0 if kind == "error" else 5000
        trace = (
            'Traceback (most recent call last):\n  File "<stdin>", line 1\nZeroDivisionError: 1/0'
            if kind == "error"
            else None
        )
        self.notification_centre.add_notification(
            title=f"{kind.capitalize()} #{self._counter}",
            body="Lorem ipsum dolor sit amet.",
            kind=SeverityKind(kind),
            lifetime_ms=expire,
            traceback=trace,
        )
        self._counter += 1

    def _raise_error(self, severity):
        """Simulate an error that would be caught by the notification broker."""
        self.notification_broker.client.connector.raise_alarm(
            severity=severity,
            alarm_type="ValueError",
            source={"device": "samx", "source": "async_file_writer"},
            msg=f"test alarm",
            metadata={"test": 1},
        )

    # this part is same as implemented in the BECMainWindow
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_notification_centre()

    def _position_notification_centre(self):
        """Keep the notification panel at a fixed margin top-right."""
        if not hasattr(self, "notification_centre"):
            return
        margin = getattr(self, "_nc_margin", 16)  # px
        nc = self.notification_centre
        nc.move(self.width() - nc.width() - margin, margin)


def main():  # pragma: no cover
    app = QtWidgets.QApplication(sys.argv)
    win = DemoWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
