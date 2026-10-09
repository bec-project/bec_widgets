"""
QWidget rendering of the BEC queue, with the same UX as the QML view.

This exists to compare the two toolkits on the same data layer (:class:`QueueController`) and the
same shell (:class:`BECQueue`); only the view differs. It is not registered for RPC or Designer.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QPoint, QSize, Qt, QTimer
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.eliding_label import ElidingLabel
from bec_widgets.utils.qml_host import QmlTheme
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue
from bec_widgets.widgets.services.bec_queue.queue_model import QueueController, QueueRow

TONE_KEYS = {
    "busy": ("busyText", "busyTint"),
    "ok": ("okText", None),
    "warn": ("warnText", "warnTint"),
    "err": ("errText", "errTint"),
    "stale": ("faint", None),
    "neutral": ("muted", None),
}


class _FitLabel(ElidingLabel):
    """Eliding label that asks for its full text width, so it only shrinks when space runs out."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Width of the full, unelided text."""
        hint = super().sizeHint()
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 2, hint.height())


def _hex(color) -> str:
    return color.name()


def _icon_button(icon: str, tip: str, theme: QmlTheme, danger: bool = False) -> QToolButton:
    button = QToolButton()
    button.setObjectName("iconButton")
    button.setToolTip(tip)
    button.setAccessibleName(tip)
    button.setAutoRaise(True)
    button.setFixedSize(28, 28)
    button.setIconSize(QSize(18, 18))
    button.setProperty("iconName", icon)
    button.setProperty("danger", danger)
    _refresh_icon(button, theme)
    return button


def _refresh_icon(button, theme: QmlTheme, color=None):
    name = button.property("iconName")
    if not name:
        return
    if color is None:
        color = theme.errText if button.property("danger") else theme.muted
    button.setIcon(material_icon(name, color=_hex(color), filled=True, convert_to_pixmap=False))


class StatusPill(QFrame):
    """Glyph + word, coloured only for states that need attention."""

    def __init__(self, theme: QmlTheme, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("pill")
        self._theme = theme
        self._icon = QLabel(self)
        self._text = QLabel(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 2, 8, 2)
        layout.setSpacing(4)
        layout.addWidget(self._icon)
        layout.addWidget(self._text)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(22)
        self._state = ("", "help", "neutral")

    def set_state(self, label: str, icon: str, tone: str):
        """Show ``label`` with ``icon`` in the colours of ``tone``."""
        if (label, icon, tone) == self._state and self._text.text():
            return
        self._state = (label, icon, tone)
        text_key, tint_key = TONE_KEYS.get(tone, TONE_KEYS["neutral"])
        fg = getattr(self._theme, text_key)
        fill = _hex(getattr(self._theme, tint_key)) if tint_key else "transparent"
        border = "none" if tint_key else f"1px solid {_hex(self._theme.separator)}"
        self.setStyleSheet(
            f"#pill {{ background: {fill}; border: {border}; border-radius: 11px; }}"
            f"#pill QLabel {{ color: {_hex(fg)}; font-size: 11px; font-weight: 600;"
            " background: transparent; border: none; }"
        )
        self._icon.setPixmap(material_icon(icon, size=(14, 14), color=_hex(fg), filled=True))
        self._text.setText(label)
        self.setAccessibleName(label)

    def refresh(self):
        """Re-apply the colours after a theme change."""
        label, icon, tone = self._state
        self._state = ("", "", "")
        self.set_state(label, icon, tone)


class ConfirmPopup(QFrame):
    """Small popover with a title, an explanation and Cancel / confirm buttons."""

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("confirm")
        self.setFixedWidth(320)
        self._title = QLabel(self)
        self._title.setObjectName("confirmTitle")
        self._title.setWordWrap(True)
        self._body = QLabel(self)
        self._body.setObjectName("muted")
        self._body.setWordWrap(True)
        self._cancel = QPushButton("Cancel", self)
        self._ok = QPushButton(self)
        self._ok.setObjectName("dangerSolid")
        self._cancel.clicked.connect(self.close)
        self._ok.clicked.connect(self._accept)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._cancel)
        buttons.addWidget(self._ok)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        layout.addWidget(self._title)
        layout.addWidget(self._body)
        layout.addLayout(buttons)
        self._action = None

    def ask(self, anchor: QWidget, title: str, body: str, confirm: str, action):
        """Open below ``anchor``; run ``action`` if the user confirms."""
        self._title.setText(title)
        self._body.setText(body)
        self._ok.setText(confirm)
        self._action = action
        self.adjustSize()
        pos = anchor.mapToGlobal(QPoint(anchor.width() - self.width(), anchor.height() + 6))
        self.move(pos)
        self.show()
        self._cancel.setFocus()

    def _accept(self):
        self.close()
        if self._action:
            self._action()


class QueueRowWidget(QFrame):
    """One queue entry."""

    def __init__(self, view: "QueueView", row: QueueRow):
        super().__init__(view)
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(54)
        self._view = view
        theme = view.theme
        self.row = row

        self.number = QLabel(self)
        self.number.setObjectName("number")
        self.number.setFixedWidth(44)
        self.number.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.pill = StatusPill(theme, self)
        pill_box = QWidget(self)
        pill_box.setFixedWidth(136)
        QHBoxLayout(pill_box).setContentsMargins(0, 0, 0, 0)
        pill_box.layout().addWidget(self.pill)
        pill_box.layout().addStretch(1)

        self.title = _FitLabel(self)
        self.title.setObjectName("title")
        self.sample = QLabel(self)
        self.sample.setObjectName("sample")
        self.sample.setFixedHeight(18)
        self.subtitle = ElidingLabel(self)
        self.subtitle.setObjectName("muted")
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_row.addWidget(self.title)
        title_row.addWidget(self.sample)
        title_row.addStretch(1)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addLayout(title_row)
        text.addWidget(self.subtitle)

        # progress (running scan)
        self.progress_box = QWidget(self)
        self.progress_box.setFixedWidth(190)
        self.progress = QProgressBar(self.progress_box)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress_text = QLabel(self.progress_box)
        self.progress_text.setObjectName("small")
        progress_layout = QVBoxLayout(self.progress_box)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(4)
        progress_layout.addStretch(1)
        progress_layout.addWidget(self.progress)
        progress_layout.addWidget(self.progress_text)
        progress_layout.addStretch(1)

        # actions, with an inline Keep / Remove step
        self.actions = QStackedWidget(self)
        self.actions.setFixedWidth(130)
        normal = QWidget()
        normal_layout = QHBoxLayout(normal)
        normal_layout.setContentsMargins(0, 0, 0, 0)
        normal_layout.setSpacing(0)
        normal_layout.addStretch(1)
        self.up = _icon_button("arrow_upward", "Move up", theme)
        self.down = _icon_button("arrow_downward", "Move down", theme)
        self.remove = _icon_button(
            "delete", "Remove this waiting scan from the queue", theme, danger=True
        )
        self.abort = _icon_button("stop_circle", "Abort…", theme, danger=True)
        for button in (self.up, self.down, self.remove, self.abort):
            normal_layout.addWidget(button)
        confirm = QWidget()
        confirm_layout = QHBoxLayout(confirm)
        confirm_layout.setContentsMargins(0, 0, 0, 0)
        confirm_layout.setSpacing(4)
        confirm_layout.addStretch(1)
        self.keep = QPushButton("Keep")
        self.keep.setObjectName("small")
        self.confirm_remove = QPushButton("Remove")
        self.confirm_remove.setObjectName("dangerSolidSmall")
        confirm_layout.addWidget(self.keep)
        confirm_layout.addWidget(self.confirm_remove)
        self.actions.addWidget(normal)
        self.actions.addWidget(confirm)
        self._confirm_timer = QTimer(self)
        self._confirm_timer.setSingleShot(True)
        self._confirm_timer.setInterval(4000)
        self._confirm_timer.timeout.connect(lambda: self.actions.setCurrentIndex(0))

        controller = view.controller
        self.up.clicked.connect(lambda: controller.moveUp(self.row.scan_id))
        self.down.clicked.connect(lambda: controller.moveDown(self.row.scan_id))
        self.remove.clicked.connect(self._start_remove)
        self.keep.clicked.connect(lambda: self.actions.setCurrentIndex(0))
        self.confirm_remove.clicked.connect(self._remove)
        self.abort.clicked.connect(lambda: view.ask_abort(self.abort))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(10)
        layout.addWidget(self.number)
        layout.addWidget(pill_box)
        layout.addLayout(text, 1)
        layout.addWidget(self.progress_box)
        layout.addWidget(self.actions)
        self.set_row(row)

    def _start_remove(self):
        self.actions.setCurrentIndex(1)
        self._confirm_timer.start()
        self.keep.setFocus()

    def _remove(self):
        self.actions.setCurrentIndex(0)
        self._view.controller.remove(self.row.request_id)

    def set_row(self, row: QueueRow):
        """Show ``row``."""
        if row == self.row and self.number.text():
            return
        self.row = row
        self.number.setText(row.scan_number or "—")
        self.number.setProperty("empty", not row.scan_number)
        if row.removing:
            self.pill.set_state("Removing…", "hourglass_empty", "stale")
        else:
            self.pill.set_state(row.state_label, row.icon, row.tone)
        self.title.setText(row.title)
        self.sample.setText(row.sample)
        self.sample.setVisible(bool(row.sample))
        self.subtitle.setText(row.subtitle)
        self.subtitle.setVisible(bool(row.subtitle))
        self.setToolTip(row.details)
        running = row.section == "Now"
        self.progress_box.setVisible(running)
        if running:
            if row.progress >= 0:
                self.progress.setRange(0, 1000)
                self.progress.setValue(int(row.progress * 1000))
            else:
                self.progress.setRange(0, 0)  # busy indicator
            self.progress_text.setText(
                row.progress_text or ("Waiting for progress…" if row.tone == "busy" else "")
            )
        waiting = row.section == "Waiting"
        self.up.setVisible(waiting)
        self.down.setVisible(waiting)
        self.remove.setVisible(waiting)
        self.up.setEnabled(row.can_move_up and not row.removing)
        self.down.setEnabled(row.can_move_down and not row.removing)
        self.remove.setEnabled(bool(row.request_id) and not row.removing)
        self.abort.setVisible(running)
        self.abort.setEnabled(not row.removing and row.tone != "ok")
        label = f"scan {row.scan_number}" if row.scan_number else row.title
        self.abort.setToolTip(f"Abort {label}…")
        self.setProperty("recent", row.section == "Recent")
        self.setProperty("removing", row.removing)
        self.style().unpolish(self)
        self.style().polish(self)

    def refresh_theme(self):
        """Re-apply theme-dependent icons."""
        self.pill.refresh()
        for button in (self.up, self.down, self.remove, self.abort):
            _refresh_icon(button, self._view.theme)


class QueueView(QWidget):
    """The queue rendered with QWidgets, driven by a :class:`QueueController`."""

    def __init__(self, controller: QueueController, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("queueView")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.controller = controller
        self.theme = QmlTheme(self)
        self._rows: dict[str, QueueRowWidget] = {}
        self._section_labels: dict[str, QLabel] = {}
        self.popup = ConfirmPopup(self)

        # header
        self.header = QWidget(self)
        self.state_pill = StatusPill(self.theme, self.header)
        self.counts = QLabel(self.header)
        self.counts.setObjectName("muted")
        self.pause_button = QPushButton(self.header)
        self.abort_button = QPushButton("Abort scan", self.header)
        self.abort_button.setObjectName("danger")
        self.more = _icon_button("more_horiz", "More queue actions", self.theme)
        self.more.setParent(self.header)
        self.menu = QMenu(self)
        self.recent_action = self.menu.addAction("Show recent scans")
        self.recent_action.setCheckable(True)
        self.menu.addSeparator()
        self.halt_action = self.menu.addAction("Halt scan without cleanup…")
        self.clear_action = self.menu.addAction("Clear queue…")
        self.more.clicked.connect(self._open_menu)
        self.recent_action.toggled.connect(self._toggle_recent)
        self.halt_action.triggered.connect(self._ask_halt)
        self.clear_action.triggered.connect(self._ask_clear)
        self.pause_button.clicked.connect(self._pause_or_resume)
        self.abort_button.clicked.connect(lambda: self.ask_abort(self.abort_button))
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 10, 10, 8)
        header_layout.setSpacing(8)
        header_layout.addWidget(self.state_pill)
        header_layout.addWidget(self.counts, 1)
        header_layout.addWidget(self.pause_button)
        header_layout.addWidget(self.abort_button)
        header_layout.addWidget(self.more)

        # banner
        self.banner = QFrame(self)
        self.banner.setObjectName("banner")
        self.banner_icon = QLabel(self.banner)
        self.banner_title = QLabel(self.banner)
        self.banner_title.setObjectName("title")
        self.banner_text = QLabel(self.banner)
        self.banner_text.setObjectName("muted")
        self.banner_text.setWordWrap(True)
        self.banner_resume = QPushButton("Resume", self.banner)
        self.banner_resume.clicked.connect(controller.resume)
        banner_text = QVBoxLayout()
        banner_text.setSpacing(1)
        banner_text.addWidget(self.banner_title)
        banner_text.addWidget(self.banner_text)
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(10, 8, 8, 8)
        banner_layout.setSpacing(10)
        banner_layout.addWidget(self.banner_icon, 0, Qt.AlignmentFlag.AlignTop)
        banner_layout.addLayout(banner_text, 1)
        banner_layout.addWidget(self.banner_resume)
        banner_box = QWidget(self)
        QVBoxLayout(banner_box).setContentsMargins(10, 0, 10, 8)
        banner_box.layout().addWidget(self.banner)
        self.banner_box = banner_box

        self.separator = QFrame(self)
        self.separator.setObjectName("separator")
        self.separator.setFixedHeight(1)

        # rows
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list = QWidget()
        self.list.setObjectName("list")
        self.list_layout = QVBoxLayout(self.list)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list)

        # empty state
        self.empty = QWidget(self.scroll.viewport())
        self.empty_icon = QLabel(self.empty)
        self.empty_title = QLabel("Queue is empty", self.empty)
        self.empty_title.setObjectName("title")
        self.empty_text = QLabel(self.empty)
        self.empty_text.setObjectName("muted")
        empty_layout = QVBoxLayout(self.empty)
        for widget in (self.empty_icon, self.empty_title, self.empty_text):
            empty_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(banner_box)
        layout.addWidget(self.separator)
        layout.addWidget(self.scroll, 1)

        controller.changed.connect(self._sync)
        self.theme.changed.connect(self._apply_theme)
        self._apply_theme()

    # ------------------------------------------------------------------ actions

    def ask_abort(self, anchor: QWidget):
        """Confirm, then abort the running scan."""
        waiting = self.controller.waitingCount
        stays = ""
        if waiting:
            stays = f"; the {waiting} waiting scan{'s stay' if waiting > 1 else ' stays'} queued"
        self.popup.ask(
            anchor,
            f"Abort {self.controller.currentLabel}?",
            "Data recorded so far is kept and the cleanup runs. "
            f"The queue pauses afterwards{stays}.",
            "Abort scan",
            self.controller.abortCurrent,
        )

    def _ask_halt(self):
        self.popup.ask(
            self.more,
            f"Halt {self.controller.currentLabel} without cleanup?",
            "Stops immediately and skips the scan's cleanup routines, so motors may stay where "
            "they are. Use Abort unless cleanup itself is the problem.",
            "Halt scan",
            self.controller.halt,
        )

    def _ask_clear(self):
        c = self.controller
        n = c.waitingCount
        start = f"Stops {c.currentLabel} and removes " if c.runningCount else "Removes "
        self.popup.ask(
            self.more,
            "Clear the queue?",
            f"{start}{n} waiting scan{'' if n == 1 else 's'}. This cannot be undone, and the "
            "queue is paused afterwards.",
            "Clear queue",
            c.clear,
        )

    def _open_menu(self):
        self.recent_action.blockSignals(True)
        self.recent_action.setChecked(self.controller.showRecent)
        self.recent_action.blockSignals(False)
        self.halt_action.setEnabled(self.controller.runningCount > 0)
        self.clear_action.setEnabled(
            self.controller.runningCount > 0 or self.controller.waitingCount > 0
        )
        self.menu.popup(self.more.mapToGlobal(QPoint(0, self.more.height() + 4)))

    def _toggle_recent(self, checked: bool):
        self.controller.showRecent = checked

    def _pause_or_resume(self):
        if self.controller.state == "paused":
            self.controller.resume()
        else:
            self.controller.pause()

    # ------------------------------------------------------------------ rendering

    def _sync(self):
        c = self.controller
        state = c.state
        label, icon, tone = {
            "locked": ("Locked", "lock", "err"),
            "paused": ("Paused", "pause", "warn"),
            "running": ("Running", "play_arrow", "busy"),
        }.get(state, ("Ready", "check", "neutral"))
        self.state_pill.set_state(label, icon, tone)
        counts = [f"{c.runningCount} running"] if c.runningCount else []
        counts.append(f"{c.waitingCount} waiting")
        self.counts.setText(" · ".join(counts))
        paused, locked = state == "paused", state == "locked"
        self.pause_button.setText("Resume" if paused or locked else "Pause")
        self.pause_button.setProperty("iconName", "play_arrow" if paused or locked else "pause")
        self.pause_button.setEnabled(not locked)
        self.pause_button.setToolTip(
            f"The queue is locked: {c.lockReason}"
            if locked
            else (
                "Let the next scan start"
                if paused
                else "Pause the queue: the running scan holds at its next checkpoint, "
                "nothing new starts"
            )
        )
        self.abort_button.setEnabled(c.runningCount > 0)
        self.abort_button.setToolTip(
            f"Abort {c.currentLabel} (asks first)" if c.runningCount else "No scan is running"
        )
        self._apply_button_icons()
        self.header.setVisible(c.toolbarVisible)
        self.separator.setVisible(c.toolbarVisible)

        self.banner_box.setVisible(paused or locked)
        self.banner.setProperty("tone", "err" if locked else "warn")
        self.banner_title.setText("Queue locked" if locked else "Queue paused")
        if locked:
            reason = f"{c.lockReason}. " if c.lockReason else ""
            self.banner_text.setText(reason + "Scans start again when the lock is released.")
        elif c.runningCount:
            self.banner_text.setText(
                "The running scan holds at its next checkpoint; nothing new starts until "
                "you resume."
            )
        else:
            self.banner_text.setText("Nothing new starts until you resume.")
        self.banner_resume.setVisible(paused)
        self.banner_icon.setPixmap(
            material_icon(
                "lock" if locked else "pause_circle",
                size=(20, 20),
                color=_hex(self.theme.errText if locked else self.theme.warnText),
                filled=True,
            )
        )
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)

        self._sync_rows()

        empty = not c.runningCount and not c.waitingCount and not c.recentCount
        self.empty.setVisible(empty)
        self.empty_text.setText(
            f"Last: {c.lastFinished}"
            if c.lastFinished
            else "Scans you submit from Scan Control or the command line appear here."
        )
        self._place_empty()

    def _sync_rows(self):
        rows = self.controller.model.rows()
        keys = {row.key for row in rows}
        for key in list(self._rows):
            if key not in keys:
                widget = self._rows.pop(key)
                self.list_layout.removeWidget(widget)
                widget.deleteLater()
        sections = [r.section for r in rows]
        for name in list(self._section_labels):
            if name not in sections:
                label = self._section_labels.pop(name)
                self.list_layout.removeWidget(label)
                label.deleteLater()
        index = 0
        previous = None
        for row in rows:
            if row.section != previous:
                label = self._section_labels.get(row.section)
                if label is None:
                    label = QLabel(self.list)
                    label.setObjectName("section")
                    self._section_labels[row.section] = label
                title = "Recently finished" if row.section == "Recent" else row.section
                suffix = f"  ·  {self.controller.waitingCount}" if row.section == "Waiting" else ""
                label.setText(title.upper() + suffix)
                self.list_layout.insertWidget(index, label)
                index += 1
                previous = row.section
            widget = self._rows.get(row.key)
            if widget is None:
                widget = QueueRowWidget(self, row)
                self._rows[row.key] = widget
            else:
                widget.set_row(row)
            self.list_layout.insertWidget(index, widget)
            index += 1

    def _place_empty(self):
        viewport = self.scroll.viewport()
        self.empty.adjustSize()
        self.empty.move(
            (viewport.width() - self.empty.width()) // 2,
            (viewport.height() - self.empty.height()) // 2,
        )

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        """Keep the empty state centred."""
        super().resizeEvent(event)
        self._place_empty()

    def event(self, event):
        """Re-centre the empty state once the layout has settled."""
        if event.type() == QEvent.Type.LayoutRequest:
            QTimer.singleShot(0, self._place_empty)
        return super().event(event)

    def _apply_button_icons(self):
        t = self.theme
        pause_color = t.faint if not self.pause_button.isEnabled() else t.fg
        self.pause_button.setIcon(
            material_icon(
                self.pause_button.property("iconName") or "pause",
                color=_hex(pause_color),
                filled=True,
                convert_to_pixmap=False,
            )
        )
        abort_color = t.errText if self.abort_button.isEnabled() else t.faint
        self.abort_button.setIcon(
            material_icon("stop", color=_hex(abort_color), filled=True, convert_to_pixmap=False)
        )

    def _apply_theme(self):
        t = self.theme
        h = {
            name: _hex(getattr(t, name))
            for name in (
                "card",
                "bg",
                "fg",
                "muted",
                "faint",
                "border",
                "separator",
                "hover",
                "pressed",
                "primary",
                "err",
                "errText",
                "errTint",
                "warnTint",
                "busy",
                "field",
            )
        }
        self.setStyleSheet(f"""
            #queueView, #list, QScrollArea, QScrollArea > QWidget > QWidget {{
                background: {h['card']}; }}
            QLabel {{ color: {h['fg']}; background: transparent; }}
            QLabel#muted {{ color: {h['muted']}; font-size: 12px; }}
            QLabel#small {{ color: {h['muted']}; font-size: 11px; }}
            QLabel#title {{ font-size: 13px; font-weight: 600; }}
            QLabel#confirmTitle {{ font-size: 14px; font-weight: 600; }}
            QLabel#number {{ font-family: monospace; font-weight: 600; font-size: 12px; }}
            QLabel#number[empty="true"] {{ color: {h['faint']}; }}
            QLabel#sample {{ color: {h['muted']}; font-size: 11px; background: {h['field']};
                border: 1px solid {h['separator']}; border-radius: 4px; padding: 0 5px; }}
            QLabel#section {{ color: {h['faint']}; background: {h['bg']}; font-size: 11px;
                font-weight: 700; letter-spacing: 0.8px; padding: 6px 12px; }}
            QFrame#separator {{ background: {h['separator']}; }}
            QFrame#row {{ border: none; border-bottom: 1px solid {h['separator']};
                background: transparent; }}
            QFrame#row:hover {{ background: {h['hover']}; }}
            QFrame#banner {{ border-radius: 7px; }}
            QFrame#banner[tone="warn"] {{ background: {h['warnTint']}; }}
            QFrame#banner[tone="err"] {{ background: {h['errTint']}; }}
            QFrame#confirm {{ background: {h['card']}; border: 1px solid {h['border']};
                border-radius: 9px; }}
            QPushButton {{ color: {h['fg']}; background: transparent; font-size: 12px;
                font-weight: 500; border: 1px solid {h['border']}; border-radius: 6px;
                padding: 5px 12px; min-height: 16px; }}
            QPushButton:hover {{ background: {h['hover']}; }}
            QPushButton:pressed {{ background: {h['pressed']}; }}
            QPushButton:focus {{ border: 2px solid {h['primary']}; }}
            QPushButton:disabled {{ color: {h['faint']}; }}
            QPushButton#danger {{ color: {h['errText']}; border-color: {h['err']}; }}
            QPushButton#danger:disabled {{ color: {h['faint']}; border-color: {h['border']}; }}
            QPushButton#dangerSolid, QPushButton#dangerSolidSmall {{ color: white;
                background: {h['err']}; border: none; }}
            QPushButton#small, QPushButton#dangerSolidSmall {{ padding: 3px 10px; }}
            QToolButton#iconButton {{ border: none; border-radius: 6px; background: transparent; }}
            QToolButton#iconButton:hover {{ background: {h['hover']}; }}
            QToolButton#iconButton:focus {{ border: 2px solid {h['primary']}; }}
            QProgressBar {{ background: {h['separator']}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {h['busy']}; border-radius: 2px; }}
            """)
        _refresh_icon(self.more, t)
        self.empty_icon.setPixmap(
            material_icon("playlist_add", size=(30, 30), color=_hex(t.faint), filled=True)
        )
        for widget in self._rows.values():
            widget.refresh_theme()
        self._sync()


class BECQueueQt(BECQueue):
    """
    The BEC queue with a QWidget view instead of QML, for comparing the two toolkits.

    Same shell, controller and behaviour as :class:`BECQueue`; only the rendering differs.
    """

    PLUGIN = False
    RPC = False

    def _create_view(self) -> QWidget:
        return QueueView(self.controller, self)

    def _release_view(self):
        self.view.popup.close()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECQueueQt()
    widget.show()
    sys.exit(app.exec_())
