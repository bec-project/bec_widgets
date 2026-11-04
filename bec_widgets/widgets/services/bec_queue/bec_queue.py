"""
Scan queue: the running scan with its live progress, compact one-line lists of the scans up next
and the finished ones, and a drawer at the bottom with the selected scan's details and actions.
"""

from __future__ import annotations

import time
from enum import StrEnum

from qtpy.QtCore import QEvent, QSize, Qt, QTimer
from qtpy.QtGui import QAction, QFont, QPainter, QPen
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSplitterHandle,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.theme_utils import DPR_EVENTS, crisp_icon, css, theme_colors
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import ScanProgressBar
from bec_widgets.widgets.progress.stage_bar import Chip, Tone, mono_font
from bec_widgets.widgets.services.bec_queue.queue_model import (
    QueueAction,
    QueueEntry,
    QueueMove,
    ScanQueueModel,
)
from bec_widgets.widgets.services.bec_queue.queue_ui import (
    AnimatedRow,
    CountBadge,
    DetailGrid,
    ElidedLabel,
    GroupTitle,
    IconButton,
    KeyedRowList,
    MoreButton,
    StatusIcon,
    entry_detail_columns,
    finished_times,
    finished_tooltip,
    set_style,
)

PAUSE_TOOLTIP = "Pause the queue; the running scan pauses at its next safe point"


class ListRow(AnimatedRow):
    """
    One line: position or status icon, name, the user metadata, the scan arguments (with
    show_details on the queue, elided to the row) and, for finished scans, the duration. The
    scan arguments are always the row's tooltip and are listed in full in the drawer.
    """

    def __init__(self, owner: "BECQueue", entry: QueueEntry, finished: bool):
        super().__init__(entry.key)
        self.finished = finished
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        line = QHBoxLayout()
        line.setSpacing(8)
        if finished:
            self.lead = StatusIcon(self, size=14)
        else:
            self.lead = QLabel(self)
            self.lead.setFont(mono_font(-1))
            self.lead.setFixedWidth(20)
            self.lead.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.name_label = QLabel(self)
        self.name_label.setFont(mono_font(0, bold=not finished))
        self.meta_label = ElidedLabel(parent=self)
        self.tail_label = QLabel(self)
        self.tail_label.setFont(mono_font(-1))
        self.tail_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        line.addWidget(self.lead)
        line.addWidget(self.name_label)
        line.addWidget(self.meta_label, 1)
        line.addWidget(self.tail_label)
        self.buttons: list[IconButton] = []
        if finished:
            self.rerun_button = IconButton(
                "replay", "Run again with the same parameters", parent=self
            )
            self.rerun_button.setFixedSize(22, 22)
            self.rerun_button.setIconSize(QSize(16, 16))
            # clicking the button must not also select the row
            self.rerun_button.clicked.connect(lambda: owner.rerun_scan(self.key))
            keep = self.rerun_button.sizePolicy()
            keep.setRetainSizeWhenHidden(True)  # rows keep their size while "Queued ✓" shows
            self.rerun_button.setSizePolicy(keep)
            self.buttons = [self.rerun_button]
            line.addWidget(self.rerun_button)
        else:
            self.up_button = IconButton("arrow_upward", "Move up", parent=self)
            self.down_button = IconButton("arrow_downward", "Move down", parent=self)
            self.remove_button = IconButton(
                "delete", "Remove from the queue", Tone.BAD, parent=self
            )
            self.up_button.clicked.connect(lambda: owner.move_scan(self.key, QueueMove.UP))
            self.down_button.clicked.connect(lambda: owner.move_scan(self.key, QueueMove.DOWN))
            self.remove_button.clicked.connect(lambda: owner.remove_scan(self.key))
            self.buttons = [self.up_button, self.down_button, self.remove_button]
            actions = QHBoxLayout()
            actions.setSpacing(0)
            for button in self.buttons:
                button.setFixedSize(22, 22)
                button.setIconSize(QSize(16, 16))
                actions.addWidget(button)
            line.addLayout(actions)
        self.body.addLayout(line)
        self.clicked.connect(owner.select)
        self.owner = owner

    def set_entry(
        self,
        entry: QueueEntry,
        selected: bool,
        requeued: bool = False,
        index: int = 0,
        count: int = 1,
    ) -> None:
        """Fill the row from an entry; index and count place a waiting row in its list."""
        colors = theme_colors()
        muted = css(colors["muted"])
        if self.finished:
            icon, tone, _ = entry.history_status
            self.lead.set_status(icon, tone, finished_tooltip(entry))
            self.tail_label.setText("Queued ✓" if requeued else finished_times(entry))
            tail_color = css(colors["ok"]) if requeued else muted
            self.rerun_button.setVisible(not requeued)
            self.rerun_button.setEnabled(entry.can_rerun)
            self.rerun_button.setToolTip(
                "Run again with the same parameters"
                if entry.can_rerun
                else "Cannot run again: the original request is not known"
            )
        else:
            self.lead.setText(str(entry.position))
            set_style(self.lead, f"color: {muted};")
            self.tail_label.setText("")
            tail_color = muted
            self.up_button.setEnabled(index > 0)
            self.down_button.setEnabled(index < count - 1)
            self.up_button.setToolTip("Move up")
            self.down_button.setToolTip("Move down")
        set_style(self.tail_label, f"color: {tail_color};")
        self.tail_label.setVisible(bool(self.tail_label.text()))
        self.name_label.setText(entry.title)
        # a scan with its own name keeps its type visible, muted, before the metadata
        scan_type = [entry.scan_type] if entry.scan_type and entry.scan_type != entry.name else []
        parts = scan_type + [value for _, value in entry.metadata]
        if self.owner.show_details and entry.args:
            parts.append(entry.args)
        self.meta_label.setText(" · ".join(parts))
        set_style(self.meta_label, f"color: {muted};")
        if self.toolTip() != entry.args:  # also restores it after a failure note
            self.setToolTip(entry.args)
        self.set_selected(selected)


class _SplitHandle(QSplitterHandle):
    """An invisible splitter handle that shows a faint line while hovered."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def event(self, event):  # pylint: disable=invalid-name
        if event.type() in (QEvent.Type.HoverEnter, QEvent.Type.HoverLeave):
            self.update()
        return super().event(event)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        if not self.underMouse() or self.orientation() != Qt.Orientation.Horizontal:
            return
        painter = QPainter(self)
        painter.setPen(QPen(theme_colors()["border"], 1))
        x = self.width() // 2
        painter.drawLine(x, 0, x, self.height())
        painter.end()


class ColumnSplitter(QSplitter):
    """The drawer's column splitter: a transparent, draggable boundary between the columns."""

    HANDLE = 8

    def __init__(self, parent: QWidget | None = None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setHandleWidth(self.HANDLE)
        self.setChildrenCollapsible(False)

    def createHandle(self):  # pylint: disable=invalid-name
        return _SplitHandle(self.orientation(), self)


class DetailDrawer(QFrame):
    """
    The drawer at the bottom: the selected scan's details and its actions. The details are two
    columns, the scan arguments and the user metadata, stacked when the drawer is narrow.
    """

    STACK_BELOW = 360

    def __init__(self, owner: "BECQueue"):
        super().__init__(owner)
        self.owner = owner
        self.setObjectName("scan_queue_drawer")
        layout = self._outer_layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.status_icon = StatusIcon(self, size=14)
        self.label = QLabel(self)
        head.addWidget(self.status_icon)
        head.addWidget(self.label, 1)
        self.close_button = IconButton("close", "Close details", parent=self)
        self.close_button.setFixedSize(22, 22)
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.clicked.connect(owner.clear_selection)
        head.addWidget(self.close_button)
        layout.addLayout(head)
        self.name_label = QLabel(self)
        self.name_label.setFont(mono_font(1.5, bold=True))
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.name_label)
        self.details = QWidget(self)
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 2, 0, 0)
        self.splitter = ColumnSplitter(self.details)
        details_layout.addWidget(self.splitter)
        self.args_box, self.args_grid = self._column("Arguments")
        self.meta_box, self.meta_grid = self._column("Metadata", left_gap=True)
        self.splitter.addWidget(self.args_box)
        self.splitter.addWidget(self.meta_box)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        self._arranged: tuple | None = None
        self._is_stacked = False
        self._dragged_args_width: int | None = None  # kept while this drawer lives
        self._arranging = False
        layout.addWidget(self.details)

        self.waiting_actions = QWidget(self)
        actions = QHBoxLayout(self.waiting_actions)
        actions.setContentsMargins(0, 2, 0, 0)
        actions.setSpacing(6)
        self.up_button = self._button("arrow_upward", "Up")
        self.down_button = self._button("arrow_downward", "Down")
        self.top_button = self._button("vertical_align_top", "To top")
        self.remove_button = self._button("delete", "Remove", danger=True)
        self.up_button.clicked.connect(lambda: owner.move_scan(owner.selected_key, QueueMove.UP))
        self.down_button.clicked.connect(
            lambda: owner.move_scan(owner.selected_key, QueueMove.DOWN)
        )
        self.top_button.clicked.connect(lambda: owner.move_scan(owner.selected_key, QueueMove.TOP))
        self.remove_button.clicked.connect(lambda: owner.remove_scan(owner.selected_key))
        for button in (self.up_button, self.down_button, self.top_button):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(self.remove_button)
        layout.addWidget(self.waiting_actions)

        self.finished_actions = QWidget(self)
        factions = QHBoxLayout(self.finished_actions)
        factions.setContentsMargins(0, 2, 0, 0)
        self.rerun_button = self._button("replay", "Run again with these parameters")
        self.rerun_button.clicked.connect(lambda: owner.rerun_scan(owner.selected_key))
        self.queued_label = QLabel("Added to Up next ✓", self)
        factions.addWidget(self.rerun_button)
        factions.addWidget(self.queued_label)
        factions.addStretch(1)
        layout.addWidget(self.finished_actions)

        self.hint = QLabel("Select a scan to see its arguments, metadata and actions.", self)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.refresh_style()
        self.show_entry(None)

    def _column(self, title: str, left_gap: bool = False) -> tuple[QWidget, DetailGrid]:
        box = QWidget(self.details)
        box.setMinimumWidth(40)
        column = QVBoxLayout(box)
        # the splitter handle plus this margin make the gap between the columns
        gap = self.COLUMN_GAP - ColumnSplitter.HANDLE if left_gap else 0
        column.setContentsMargins(gap, 0, 0, 0)
        column.setSpacing(3)
        column.addWidget(GroupTitle(title, box))
        grid = DetailGrid(box)
        column.addWidget(grid)
        column.addStretch(1)
        return box, grid

    COLUMN_GAP = 16

    def column_widths(self, width: int) -> tuple[bool, int, int]:
        """
        Decide the layout for a drawer content width: (stacked, args width, metadata width).

        The arguments get their natural width and the metadata follows after a gap, packed to
        the left, with the rest of the width. Only when both do not fit, a column narrower
        than half keeps its natural width and the other gets the rest, else both get half.
        Stacked when the drawer is narrow, or when side by side would cut argument values
        that stacked fit. A position the user dragged the splitter to wins while it fits.
        """
        args_n = self.args_grid.natural_width()
        meta_n = self.meta_grid.natural_width() if not self.meta_box.isHidden() else 0
        if not meta_n:
            return False, width, 0
        gap = self.COLUMN_GAP
        if args_n + gap + meta_n <= width:
            args_w = args_n
        else:
            half = (width - gap) // 2
            if meta_n <= half:
                args_w = width - gap - meta_n
            elif args_n <= half:
                args_w = args_n
            else:
                args_w = half
        stacked = width < self.STACK_BELOW or (args_w < args_n and args_n <= width)
        if stacked:
            return True, width, width
        if self._dragged_args_width is not None:
            args_w = max(40, min(self._dragged_args_width, width - gap - 40))
        return False, args_w, width - gap - args_w

    def _arrange_columns(self) -> None:
        """Lay the columns out for the current width and content; no-op when nothing changed."""
        margins = self._outer_layout.contentsMargins()
        width = max(0, self.width() - margins.left() - margins.right())
        content = (self.args_grid.natural_width(), self.meta_grid.natural_width())
        key = (width, content, self.meta_box.isHidden(), self._dragged_args_width)
        if key == self._arranged:
            return
        self._arranged = key
        stacked, args_w, meta_w = self.column_widths(width)
        self._is_stacked = stacked
        self._arranging = True
        try:
            if stacked:
                self.splitter.setOrientation(Qt.Orientation.Vertical)
                self.splitter.setSizes(
                    [self.args_box.sizeHint().height(), self.meta_box.sizeHint().height()]
                )
            else:
                self.splitter.setOrientation(Qt.Orientation.Horizontal)
                handle = self.splitter.handleWidth()
                self.splitter.setSizes([args_w, max(0, width - args_w - handle)])
        finally:
            self._arranging = False
        self.args_grid.fit_keys(args_w)
        self.meta_grid.fit_keys(meta_w or width)

    @SafeSlot(int, int)
    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        if self._arranging or self._is_stacked:
            return
        self._dragged_args_width = self.splitter.sizes()[0]
        self.args_grid.fit_keys(self.args_box.width())
        self.meta_grid.fit_keys(self.meta_box.width())

    @property
    def stacked(self) -> bool:
        """Whether the metadata column sits under the arguments."""
        return self._is_stacked

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._arrange_columns()

    def event(self, event):  # pylint: disable=invalid-name
        if event.type() in DPR_EVENTS:
            self.refresh_style()  # re-render the button icons for the new screen
        return super().event(event)

    def _button(self, icon: str, text: str, danger: bool = False) -> QPushButton:
        button = QPushButton(text, self)
        button.setProperty("_icon", icon)
        button.setProperty("_danger", danger)
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        colors = theme_colors()
        self.setStyleSheet(
            f"#scan_queue_drawer {{ background: {css(colors['card'])};"
            f" border-top: 1px solid {css(colors['border'])}; }}"
        )
        self.label.setStyleSheet(f"color: {css(colors['muted'])};")
        self.hint.setStyleSheet(f"color: {css(colors['muted'])};")
        self.queued_label.setStyleSheet(f"color: {css(colors['ok'])}; font-weight: 600;")
        for button in self.findChildren(QPushButton):
            danger = bool(button.property("_danger"))
            color = colors["bad"] if danger else colors["fg"]
            button.setIcon(crisp_icon(button.property("_icon"), 16, color, widget=button))
            if danger:
                button.setStyleSheet(f"color: {css(colors['bad'])};")

    def show_entry(self, entry: QueueEntry | None, finished: bool = False, **state) -> None:
        """Show an entry, or the hint when nothing is selected."""
        has = entry is not None
        self.close_button.setVisible(has)
        for widget in (self.name_label, self.details, self.label):
            widget.setVisible(has)
        self.hint.setVisible(not has)
        self.status_icon.setVisible(has and finished)
        self.waiting_actions.setVisible(has and not finished)
        self.finished_actions.setVisible(has and finished)
        if not has:
            return
        self.name_label.setText(entry.title)
        arguments, metadata = entry_detail_columns(entry)
        self.args_grid.set_items(arguments)
        self.meta_grid.set_items(metadata)
        self.meta_box.setVisible(bool(metadata))
        self._arrange_columns()
        if finished:
            icon, tone, _ = entry.history_status
            self.status_icon.set_status(icon, tone, finished_tooltip(entry))
            self.label.setText(f"Finished · {finished_tooltip(entry)}")
            requeued = state.get("requeued", False)
            self.rerun_button.setVisible(not requeued)
            self.rerun_button.setEnabled(entry.can_rerun)
            self.queued_label.setVisible(requeued)
        else:
            index, count = state.get("index", 0), state.get("count", 1)
            self.label.setText(f"Waiting · position {entry.position} of {count}")
            self.up_button.setEnabled(index > 0)
            self.top_button.setEnabled(index > 0)
            self.down_button.setEnabled(index < count - 1)


class PauseState(StrEnum):
    """What the pause button of the queue offers."""

    RUNNING = "running"  # a scan runs: pause the queue
    PAUSING = "pausing"  # a pause was asked for and has not landed yet
    PAUSED = "paused"  # resume the queue
    IDLE = "idle"  # nothing runs: disabled


class BECQueue(BECWidget, QWidget):
    """
    Live scan queue with the running scan, the scans up next and the finished scans.

    The running scan shows its live progress; every scan up next and every finished scan is one
    compact line, and a drawer at the bottom shows the selected scan's details and actions.
    """

    PLUGIN = True
    RPC = True
    ICON_NAME = "view_list"

    REMOVE_GRACE_S = 5.0
    QUEUED_NOTE_S = 3.0
    FAILURE_SHOWN_MS = 4000
    PAUSE_TEXTS = ("Pause queue", "Resume queue", "Pausing…")
    PAUSE_PENDING_S = 10.0

    def __init__(self, parent: QWidget | None = None, client=None, config=None, gui_id=None, **kw):
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kw)
        self.get_bec_shortcuts()
        self.setMinimumWidth(300)
        self.selected_key: str | None = None
        self._show_details = True
        self._waiting_index: dict[str, int] = {}
        self._removing: dict[str, float] = {}
        self._flash_next: dict[str, str] = {}
        self._requeued: dict[str, float] = {}
        self._new_rid: str | None = None
        self._last_moved: list[str] = []

        self.model = ScanQueueModel(self.client, self.bec_dispatcher, parent=self)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)
        self._build_header()

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget(self.scroll)
        self.content.setObjectName("scan_queue_content")
        # click focus on the children, so Esc reaches the queue; a dock area profile restores
        # the focusPolicy of the queue itself from the file
        self.content.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 6, 10, 10)
        self.content_layout.setSpacing(8)
        self.scroll.setWidget(self.content)
        self._outer.addWidget(self.scroll, 1)

        self.running_card = QFrame(self.content)
        self.running_card.setObjectName("scan_queue_running")
        running_layout = QVBoxLayout(self.running_card)
        running_layout.setContentsMargins(0, 0, 0, 0)
        self.progress = ScanProgressBar(
            parent=self.running_card, client=self.client, fill_height=False
        )
        running_layout.addWidget(self.progress)

        self._build_lists()
        # a refused action is shown in the "Up next" hint for a while; nothing pops over the list
        self._failure = ""
        self._failure_timer = QTimer(self)
        self._failure_timer.setSingleShot(True)
        self._failure_timer.setInterval(self.FAILURE_SHOWN_MS)
        self._failure_timer.timeout.connect(self._clear_failure)
        self._expire_timer = QTimer(self)
        self._expire_timer.setInterval(1000)
        self._expire_timer.timeout.connect(self._expire_notes)

        self.model.changed.connect(self._on_model_changed)
        self.model.action_sent.connect(self._on_action_sent)
        self.model.action_failed.connect(self._on_action_failed)
        self._apply_styles()
        self.model.start()
        # the queue is read in the background; until it lands, show no "empty" or "ready" state
        self._render_header()
        self.waiting_empty.hide()

    ################################################################################
    # Building
    ################################################################################

    def _build_header(self) -> None:
        self.header = QFrame(self)
        self.header.setObjectName("scan_queue_header")
        layout = QHBoxLayout(self.header)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)
        self.title_label = QLabel("Scan queue", self.header)
        self.title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        self.queue_chip = Chip("Loading", Tone.NEUTRAL, self.header)
        self.pause_button = QPushButton(self.header)
        self.pause_button.setObjectName("scan_queue_pause")
        self.pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_button.setFixedHeight(26)
        self.pause_button.setIconSize(QSize(16, 16))
        font = QFont(self.pause_button.font())
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        self.pause_button.setFont(font)
        metrics = self.pause_button.fontMetrics()
        widest = max(metrics.horizontalAdvance(t) for t in self.PAUSE_TEXTS)
        self.pause_button.setMinimumWidth(widest + 16 + 6 + 2 * 10 + 4)  # text, icon, padding
        self.pause_button.clicked.connect(self._toggle_pause)
        self._pause_state: PauseState | None = None
        self._pause_requested_at: float | None = None
        self._pause_timeout = QTimer(self)
        self._pause_timeout.setSingleShot(True)
        self._pause_timeout.setInterval(int(self.PAUSE_PENDING_S * 1000))
        self._pause_timeout.timeout.connect(self._render_header)
        layout.addWidget(self.title_label)
        layout.addWidget(self.queue_chip)
        layout.addStretch(1)
        layout.addWidget(self.pause_button)
        # actions that are rarely needed and cannot be undone sit in a menu, out of the way
        self.more_button = MoreButton("More queue actions", parent=self.header)
        self.more_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # keyboard: Tab, then Space
        more_menu = QMenu(self.more_button)
        self.reset_action = QAction("Reset queue…", more_menu)
        self.reset_action.setToolTip(
            "Stop the running scan and remove all waiting scans; asks for confirmation"
        )
        self.reset_action.triggered.connect(self.ask_reset)
        more_menu.addAction(self.reset_action)
        self.more_button.setMenu(more_menu)
        layout.addWidget(self.more_button)
        self._outer.addWidget(self.header)

    def _group_header(self, title: str, badge: bool = False) -> tuple[QWidget, CountBadge | None]:
        row = QWidget(self.content)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 4, 2, 0)
        layout.setSpacing(6)
        layout.addWidget(GroupTitle(title, row))
        count = None
        if badge:
            count = CountBadge(row)
            layout.addWidget(count)
        layout.addStretch(1)
        row.hint = QLabel(row)
        layout.addWidget(row.hint)
        self._group_hints.append(row.hint)
        return row, count

    def _build_lists(self) -> None:
        self._group_hints: list[QLabel] = []
        layout = self.content_layout
        running_header, _ = self._group_header("Running")
        layout.addWidget(running_header)
        layout.addWidget(self.running_card)
        next_header, self.waiting_badge = self._group_header("Up next", badge=True)
        self.waiting_hint = next_header.hint
        layout.addWidget(next_header)
        self.waiting_empty = QLabel("No scans waiting.", self.content)
        layout.addWidget(self.waiting_empty)
        self.waiting_rows = KeyedRowList(
            lambda e: ListRow(self, e, finished=False), self._update_waiting, self.content, 1
        )
        layout.addWidget(self.waiting_rows)
        self.finished_rule = QFrame(self.content)
        self.finished_rule.setObjectName("scan_queue_rule")
        self.finished_rule.setFixedHeight(1)
        layout.addSpacing(4)
        layout.addWidget(self.finished_rule)
        self.finished_header, self.finished_badge = self._group_header("Finished", badge=True)
        layout.addWidget(self.finished_header)
        self.finished_rows = KeyedRowList(
            lambda e: ListRow(self, e, finished=True), self._update_finished, self.content, 1
        )
        layout.addWidget(self.finished_rows)
        layout.addStretch(1)
        self.drawer = DetailDrawer(self)
        self.drawer.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._outer.addWidget(self.drawer)

    def _apply_styles(self) -> None:
        colors = theme_colors()
        self.header.setStyleSheet(
            f"#scan_queue_header {{ border-bottom: 1px solid {css(colors['border'])}; }}"
        )
        self.running_card.setStyleSheet(
            f"#scan_queue_running {{ background: {css(colors['card'])};"
            f" border: 1px solid {css(colors['border'])}; border-radius: 8px; }}"
        )
        self.waiting_empty.setStyleSheet(f"color: {css(colors['muted'])}; padding: 6px 4px;")
        for hint in self._group_hints:
            hint.setStyleSheet(f"color: {css(colors['muted'])}; font-size: 11px;")
        self.finished_rule.setStyleSheet(
            f"#scan_queue_rule {{ background: {css(colors['border'])}; border: none; }}"
        )

    def apply_theme(self, theme: str):
        """Restyle after a theme change."""
        self._apply_styles()
        for widget in self.findChildren(QWidget):
            refresh = getattr(widget, "refresh_style", None)
            if callable(refresh):
                refresh()
        self._pause_state = None  # restyle the pause button even though its state is the same
        self._render_header()
        self._render()

    ################################################################################
    # Properties
    ################################################################################

    @SafeProperty(bool)
    def show_details(self) -> bool:
        """
        Show the scan arguments in the rows, after the user metadata, elided to the row. They
        stay in the row's tooltip and in the drawer either way.
        """
        return self._show_details

    @show_details.setter
    def show_details(self, show: bool) -> None:
        self._show_details = show
        self._render()

    ################################################################################
    # Model
    ################################################################################

    def waiting_entries(self) -> list[QueueEntry]:
        """Waiting entries, without those being removed right now."""
        now = time.monotonic()
        self._removing = {k: t for k, t in self._removing.items() if now - t < self.REMOVE_GRACE_S}
        return [e for e in self.model.waiting if e.key not in self._removing]

    def is_requeued(self, key: str) -> bool:
        """Whether this finished entry was queued again in the last seconds."""
        stamp = self._requeued.get(key)
        return stamp is not None and time.monotonic() - stamp < self.QUEUED_NOTE_S

    @SafeSlot()
    def _on_model_changed(self) -> None:
        self._render_header()
        self._render()
        self._flash_after_sync()

    def _render_header(self) -> None:
        model = self.model
        if model.paused:
            self.queue_chip.setText("Paused")
            self.queue_chip.set_tone(Tone.WARN)
        elif model.running is not None:
            self.queue_chip.setText("Running")
            self.queue_chip.set_tone(Tone.RUN)
        elif not model.loaded:
            self.queue_chip.setText("Loading")
            self.queue_chip.set_tone(Tone.NEUTRAL)
        else:
            self.queue_chip.setText("Ready")
            self.queue_chip.set_tone(Tone.OK)
        self._style_pause_button(self.pause_state())
        self.reset_action.setEnabled(model.running is not None or bool(model.waiting))

    def pause_state(self) -> PauseState:
        """running, pausing, paused or idle: what the pause button offers."""
        model = self.model
        if model.paused:
            self._pause_requested_at = None
            return PauseState.PAUSED
        requested = self._pause_requested_at
        if requested is not None and time.monotonic() - requested < self.PAUSE_PENDING_S:
            return PauseState.PAUSING
        self._pause_requested_at = None
        return PauseState.RUNNING if model.running is not None else PauseState.IDLE

    def _style_pause_button(self, state: PauseState) -> None:
        """Restyle the pause button only when its state changes."""
        if state == self._pause_state:
            return
        self._pause_state = state
        colors = theme_colors()
        button = self.pause_button
        if state == PauseState.PAUSED:
            text, icon, tooltip = "Resume queue", "play_arrow", "Resume the queue"
            icon_color = colors["on_primary"]
            sheet = (
                f"#scan_queue_pause {{ background: {css(colors['primary'])};"
                f" color: {css(colors['on_primary'])}; border: 1px solid {css(colors['primary'])};"
                " border-radius: 6px; padding: 0 10px; }"
                f"#scan_queue_pause:hover {{ background: {css(colors['primary'], 0.85)}; }}"
            )
        else:
            text = "Pausing…" if state == PauseState.PAUSING else "Pause queue"
            icon, tooltip = "pause", PAUSE_TOOLTIP
            icon_color = colors["warn"] if state == PauseState.RUNNING else colors["muted"]
            sheet = (
                f"#scan_queue_pause {{ background: transparent; color: {css(colors['fg'])};"
                f" border: 1px solid {css(colors['warn'], 0.8)}; border-radius: 6px;"
                " padding: 0 10px; }"
                f"#scan_queue_pause:hover {{ background: {css(colors['warn'], 0.12)}; }}"
                f"#scan_queue_pause:disabled {{ color: {css(colors['muted'])};"
                f" border-color: {css(colors['border'])}; }}"
            )
        button.setText(text)
        button.setToolTip(tooltip)
        button.setIcon(crisp_icon(icon, 16, icon_color, widget=button))
        button.setStyleSheet(sheet)
        button.setEnabled(state in (PauseState.RUNNING, PauseState.PAUSED))
        self.pause_icon_name = icon

    def _flash_after_sync(self) -> None:
        rows = self.waiting_rows
        for key, tone in list(self._flash_next.items()):
            row = rows.row(key)
            if row is None:
                del self._flash_next[key]
            elif key in self._last_moved:
                row.flash(tone)
                del self._flash_next[key]
        if self._new_rid:
            for entry in self.model.waiting:
                if entry.rid == self._new_rid:
                    row = rows.row(entry.key)
                    if row is not None and not row.flashing:
                        row.flash(Tone.ACCENT)
                    self._new_rid = None
                    break

    ################################################################################
    # Selection and rendering
    ################################################################################

    @SafeSlot()
    def clear_selection(self) -> None:
        """Close the details: nothing selected, no row highlighted."""
        if self.selected_key is not None:
            self.selected_key = None
            self._render()

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        if event.key() == Qt.Key.Key_Escape and self.selected_key is not None:
            self.clear_selection()
            return
        super().keyPressEvent(event)

    @SafeSlot(str)
    def select(self, key: str) -> None:
        """Select a scan and show it in the drawer; selecting it again clears the selection."""
        self.selected_key = None if key == self.selected_key else key
        self._render()

    def _update_waiting(self, row: ListRow, entry: QueueEntry) -> None:
        index = self._waiting_index.get(entry.key, 0)
        selected = entry.key == self.selected_key
        row.set_entry(entry, selected, index=index, count=len(self._waiting_index))

    def _update_finished(self, row: ListRow, entry: QueueEntry) -> None:
        row.set_entry(entry, entry.key == self.selected_key, self.is_requeued(entry.key))

    def _render(self) -> None:
        waiting = self.waiting_entries()
        self._waiting_index = {e.key: i for i, e in enumerate(waiting)}
        finished = self.model.finished
        self.waiting_badge.setText(str(len(waiting)))
        self.waiting_hint.setText(self.reorder_hint())
        self.waiting_empty.setVisible(self.model.loaded and not waiting)
        self._last_moved = self.waiting_rows.sync(waiting)
        self.finished_badge.setText(str(len(finished)))
        self.finished_rows.sync(finished, animate=False)

        index = next((i for i, e in enumerate(waiting) if e.key == self.selected_key), -1)
        if index >= 0:
            self.drawer.show_entry(waiting[index], index=index, count=len(waiting))
            return
        entry = next((e for e in finished if e.key == self.selected_key), None)
        if entry is not None:
            self.drawer.show_entry(entry, finished=True, requeued=self.is_requeued(entry.key))
            return
        if self.selected_key is not None and self.selected_key not in self._removing:
            self.selected_key = None
        self.drawer.show_entry(None)

    ################################################################################
    # Actions
    ################################################################################

    @SafeSlot(str, object)
    def move_scan(self, key: str, action: QueueMove | str) -> None:
        """Reorder a waiting scan (up, down, top, bottom)."""
        self.model.move(key, action)

    @SafeSlot(str)
    def remove_scan(self, key: str) -> None:
        """Remove a waiting scan, animating its row out."""
        self.model.remove(key)

    @SafeSlot(str)
    def rerun_scan(self, key: str) -> None:
        """Queue a finished scan again with the same parameters."""
        self.model.rerun(key)

    def reset_text(self) -> str:
        """What a reset does to the queue as it is now, for the confirmation."""
        model = self.model
        parts = []
        if model.running is not None:
            parts.append(f"stops the running scan {model.running.title} and its devices")
        waiting = len(self.waiting_entries())
        if waiting:
            parts.append(f"removes the {waiting} waiting scan{'s' if waiting != 1 else ''}")
        what = " and ".join(parts) or "clears the queue"
        return f"Resetting the queue {what}. This cannot be undone."

    @SafeSlot()
    def ask_reset(self) -> None:
        """Reset the queue after the user confirmed it in a dialog."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Reset queue")
        box.setText("Reset the scan queue?")
        box.setInformativeText(self.reset_text())
        reset = box.addButton("Reset queue", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() is reset:
            self.model.reset()
        box.deleteLater()

    @SafeSlot()
    def _toggle_pause(self) -> None:
        if self.model.paused:
            self.model.resume()
        else:
            self.model.pause()
            self._pause_requested_at = time.monotonic()
            self._pause_timeout.start()  # fall back to "Pause queue" if the pause never lands
        self._render_header()

    @SafeSlot(object, str, str)
    def _on_action_sent(self, kind: QueueAction, key: str, text: str) -> None:
        match kind:
            case QueueAction.MOVE:
                self._flash_next[key] = Tone.ACCENT
            case QueueAction.REMOVE:
                self._removing[key] = time.monotonic()
                self.waiting_rows.remove_animated(key)
                self._render()
            case QueueAction.RERUN:
                self._new_rid = self.model.last_rerun_rid
                self._requeued[key] = time.monotonic()
                self._expire_timer.start()
                self.waiting_badge.pulse()
                # no announcement: the new waiting row flashes and the badge pulses
                self._render()
            case _:
                # pause/resume/reset: the header and the lists are the feedback
                self._render_header()

    @SafeSlot(object, str, str)
    def _on_action_failed(self, kind: QueueAction, key: str, reason: str) -> None:
        self._flash_next.pop(key, None)
        self._failure = reason
        self._failure_timer.start()
        self._render()
        row = self.waiting_rows.row(key)
        if row is not None:
            row.flash(Tone.WARN)
            row.setToolTip(reason)  # until the row's next update

    @SafeSlot()
    def _clear_failure(self) -> None:
        self._failure = ""
        self._render()

    def reorder_hint(self) -> str:
        """Short hint next to Up next: why the last action was refused, for a few seconds."""
        tone = "warn" if self._failure else "muted"
        set_style(self.waiting_hint, f"color: {css(theme_colors()[tone])}; font-size: 11px;")
        return self._failure

    def _expire_notes(self) -> None:
        if not any(self.is_requeued(k) for k in self._requeued):
            self._requeued.clear()
            self._expire_timer.stop()
            self._render()

    def cleanup(self):
        """Disconnect the model and stop timers and animations."""
        self._expire_timer.stop()
        self._failure_timer.stop()
        self._pause_timeout.stop()
        self.model.cleanup()
        for rows in self.findChildren(KeyedRowList):
            rows.stop_animations()
        for badge in self.findChildren(CountBadge):
            badge._anim.stop()  # pylint: disable=protected-access
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = BECQueue()
    widget.resize(460, 900)
    widget.show()
    sys.exit(app.exec_())
