"""Welcome view for the BEC main app: a rundown of what is happening at the beamline.

Three design directions render the same :class:`WelcomeSnapshot`, so they can be compared:

* ``board``: status board. Glance tiles, the running scan and queue, recent scans, problems,
  workspaces and quick actions on one screen.
* ``launchpad``: a calm start page. Greeting, one status line, recent workspaces as large
  previews and a few big actions.
* ``feed``: shift handover. What is true right now on the left, everything that happened since
  you were last here on the right.

This is a mockup: it shows :func:`demo_snapshot` data and is only added to the app when
``BEC_WELCOME_VIEW`` is set (``board``, ``launchpad`` or ``feed`` picks the first direction).
"""

from __future__ import annotations

import os

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.applications.views.view import ViewBase
from bec_widgets.applications.views.welcome_view.welcome_data import WelcomeSnapshot, demo_snapshot
from bec_widgets.applications.views.welcome_view.welcome_widgets import (
    ActionRow,
    ActionTile,
    GlanceTile,
    QueueRow,
    RecentScansTable,
    RunningScanBlock,
    StatusChip,
    SummaryChip,
    TimelineRow,
    WorkspaceRow,
    WorkspaceTile,
    caption,
    hline,
    icon_badge,
    icon_label,
    label,
    section_card,
    tokens,
    vline,
)
from bec_widgets.utils.quick.tokens import app_theme
from bec_widgets.utils.ux_kit import (
    Banner,
    Card,
    LinearProgress,
    SegmentedControl,
    StatusPill,
    TextButton,
)

DIRECTIONS = [("board", "Status board"), ("launchpad", "Launchpad"), ("feed", "Activity feed")]
ENV_FLAG = "BEC_WELCOME_VIEW"


def welcome_view_requested() -> str | None:
    """The direction requested through ``BEC_WELCOME_VIEW``, or None when the view is off."""
    value = os.environ.get(ENV_FLAG, "").strip().lower()
    if not value or value in ("0", "off", "false", "no"):
        return None
    keys = [key for key, _ in DIRECTIONS]
    return value if value in keys else keys[0]


def _scroll(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(widget)
    area.setStyleSheet("QScrollArea { background: transparent; }")
    area.viewport().setStyleSheet("background: transparent;")
    return area


def _page() -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    page.setObjectName("welcomePage")
    page.setStyleSheet(f"QWidget#welcomePage {{ background: {tokens().bg.name()}; }}")
    lay = QVBoxLayout(page)
    lay.setContentsMargins(28, 18, 28, 24)
    lay.setSpacing(14)
    return page, lay


def _experiment_header(snap: WelcomeSnapshot, big: bool = False) -> QWidget:
    t = tokens()
    exp = snap.experiment
    box = QWidget()
    col = QVBoxLayout(box)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(4)
    if big:
        col.addWidget(label(f"{snap.greeting}, e{exp.account[1:]}", 28, 650))
        col.addWidget(
            label(f"{exp.account} · {exp.title} · {exp.beamline} · {exp.day}", 14, 400, t.fg_muted)
        )
        return box
    col.addWidget(caption(exp.beamline))
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(label(exp.title, 20, 650))
    row.addWidget(StatusPill(text=exp.account, tone="primary", icon_name="badge"))
    row.addWidget(StatusPill(text=exp.day, tone="neutral", outlined=True))
    row.addStretch(1)
    col.addLayout(row)
    col.addWidget(
        label(
            f"Beamtime {exp.beamtime} · logged in as e{exp.account[1:]} on x12sa-console-2",
            12,
            400,
            t.fg_muted,
        )
    )
    return box


# --------------------------------------------------------------------------------------------
# Direction A: status board
# --------------------------------------------------------------------------------------------


def build_board(snap: WelcomeSnapshot) -> QWidget:
    """Everything at a glance: tiles, now running, recent scans, problems, workspaces, actions."""
    t = tokens()
    page, lay = _page()
    lay.addWidget(_experiment_header(snap))

    tiles = QHBoxLayout()
    tiles.setSpacing(12)
    for glance in snap.glances:
        tiles.addWidget(GlanceTile(glance), 1)
    lay.addLayout(tiles)

    body = QHBoxLayout()
    body.setSpacing(16)
    left = QVBoxLayout()
    left.setSpacing(16)
    right = QVBoxLayout()
    right.setSpacing(16)

    now = section_card("Now running", "play_circle", link="Open queue")
    if snap.running:
        now.body.addWidget(RunningScanBlock(snap.running))
    now.body.addSpacing(4)
    now.body.addWidget(hline())
    up = QHBoxLayout()
    up.addWidget(caption(f"Up next · {len(snap.queued)}"))
    up.addStretch(1)
    up.addWidget(label("queue empty in ~14 min", 12, 400, t.fg_subtle))
    now.body.addLayout(up)
    for i, q in enumerate(snap.queued, start=1):
        now.body.addWidget(QueueRow(i, q.scan_type, q.summary, q.sample, q.estimate))
    left.addWidget(now)

    recent = section_card("Recent scans", "history", link="Scan history")
    recent.body.addWidget(RecentScansTable(snap.recent))
    left.addWidget(recent)
    left.addStretch(1)

    attention = section_card("Needs attention", "notifications_active", link="All notifications")
    worst = "danger" if any(p.tone == "danger" for p in snap.problems) else "warning"
    count = StatusPill(text=f"{len(snap.problems)}", tone=worst)
    attention.add_header_widget(count)
    for prob in snap.problems:
        attention.body.addWidget(
            Banner(
                prob.tone,
                prob.title,
                f"{prob.text}  ·  {prob.when}",
                action_text=prob.action,
                closable=True,
            )
        )
    right.addWidget(attention)

    cont = section_card("Continue", "dashboard", link="All workspaces")
    for ws in snap.workspaces[:3]:
        cont.body.addWidget(WorkspaceRow(ws))
    right.addWidget(cont)

    quick = section_card("Quick actions", "rocket_launch")
    grid = QGridLayout()
    grid.setSpacing(8)
    for i, action in enumerate(snap.actions):
        grid.addWidget(ActionRow(action), i // 2, i % 2)
    quick.body.addLayout(grid)
    right.addWidget(quick)
    right.addStretch(1)

    body.addLayout(left, 62)
    body.addLayout(right, 38)
    lay.addLayout(body, 1)
    return page


# --------------------------------------------------------------------------------------------
# Direction B: launchpad
# --------------------------------------------------------------------------------------------


def build_launchpad(snap: WelcomeSnapshot) -> QWidget:
    """A calm start page focused on getting back to work."""
    t = tokens()
    outer, outer_lay = _page()
    outer_lay.setContentsMargins(28, 40, 28, 28)
    column = QWidget()
    column.setMaximumWidth(1120)
    lay = QVBoxLayout(column)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(22)
    outer_lay.addWidget(column, 1, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

    lay.addWidget(_experiment_header(snap, big=True))

    strip = Card(padding=14)
    srow = QHBoxLayout()
    srow.setSpacing(18)
    for i, glance in enumerate(snap.glances[:3]):
        if i:
            srow.addWidget(vline())
        srow.addWidget(StatusChip(glance))
    srow.addWidget(vline())
    if snap.running:
        r = snap.running
        now = QVBoxLayout()
        now.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        if r.paused:
            head.addWidget(StatusPill(text="Paused", tone="warning", icon_name="pause"))
        else:
            head.addWidget(StatusPill(text="Running", tone="info", pulse=True))
        head.addWidget(label(f"#{r.number} {r.scan_type}", 13, 600))
        left = "paused" if r.paused else f"{r.remaining} left"
        head.addWidget(label(f"· {left} · {len(snap.queued)} waiting", 12, 400, t.fg_muted))
        head.addStretch(1)
        now.addLayout(head)
        bar = LinearProgress(tone="warning" if r.paused else "info", thickness=6)
        bar.set_value(r.done / r.total, animate=False)
        now.addWidget(bar)
        srow.addLayout(now, 1)
    srow.addWidget(TextButton("Details", "ghost", "chevron_right", compact=True))
    strip.body.addLayout(srow)
    lay.addWidget(strip)

    warn = [p for p in snap.problems if p.tone in ("danger", "warning")]
    if warn:
        lay.addWidget(
            Banner(
                "danger" if any(p.tone == "danger" for p in warn) else "warning",
                f"{len(warn)} things need a look",
                " · ".join(p.title for p in warn),
                action_text="Review",
            )
        )

    head = QHBoxLayout()
    head.addWidget(label("Continue where you left off", 16, 650))
    head.addStretch(1)
    head.addWidget(TextButton("All workspaces", "ghost", compact=True))
    lay.addLayout(head)
    tiles = QHBoxLayout()
    tiles.setSpacing(14)
    for ws in snap.workspaces[:4]:
        tiles.addWidget(WorkspaceTile(ws), 1)
    lay.addLayout(tiles)

    lay.addWidget(label("Start something", 16, 650))
    actions = QHBoxLayout()
    actions.setSpacing(14)
    for action in snap.actions:
        tile = ActionTile(action)
        tile.setMinimumHeight(132)
        actions.addWidget(tile, 1)
    lay.addLayout(actions)

    tip = Card(padding=14, surface="sunken")
    trow = QHBoxLayout()
    trow.setSpacing(12)
    trow.addWidget(icon_badge("lightbulb", "warning", 36, 20), 0, Qt.AlignmentFlag.AlignTop)
    tcol = QVBoxLayout()
    tcol.setSpacing(2)
    tcol.addWidget(label(f"Tip · {snap.tip[0]}", 13, 600))
    tcol.addWidget(label(snap.tip[1], 12, 400, t.fg_muted, wrap=True))
    trow.addLayout(tcol, 1)
    trow.addWidget(TextButton("Next tip", "ghost", compact=True), 0, Qt.AlignmentFlag.AlignVCenter)
    trow.addWidget(
        TextButton("Don't show tips", "ghost", compact=True), 0, Qt.AlignmentFlag.AlignVCenter
    )
    tip.body.addLayout(trow)
    lay.addWidget(tip)
    return outer


# --------------------------------------------------------------------------------------------
# Direction C: activity feed
# --------------------------------------------------------------------------------------------


def build_feed(snap: WelcomeSnapshot) -> QWidget:
    """Shift handover: state now on the left, what happened since last visit on the right."""
    t = tokens()
    page, lay = _page()
    body = QHBoxLayout()
    body.setSpacing(18)
    lay.addLayout(body, 1)

    left = QVBoxLayout()
    left.setSpacing(14)
    side = QWidget()
    side.setFixedWidth(380)
    side.setLayout(left)

    exp = Card(padding=16)
    exp.body.addWidget(caption(snap.experiment.beamline))
    exp.body.addWidget(label(snap.experiment.title, 16, 650, wrap=True))
    prow = QHBoxLayout()
    prow.setSpacing(6)
    prow.addWidget(StatusPill(text=snap.experiment.account, tone="primary", icon_name="badge"))
    prow.addWidget(StatusPill(text=snap.experiment.day, tone="neutral", outlined=True))
    prow.addStretch(1)
    exp.body.addLayout(prow)
    left.addWidget(exp)

    state = section_card("Right now", "sensors")
    for i, glance in enumerate(snap.glances):
        if i:
            state.body.addWidget(hline())
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(icon_label(glance.icon, t.fg_muted, 18))
        row.addWidget(label(glance.label, 13, 500), 1)
        row.addWidget(StatusPill(text=glance.value, tone=glance.tone))
        state.body.addLayout(row)
        if glance.tone in ("warning", "danger"):
            state.body.addWidget(label(f"      {glance.detail}", 12, 400, t.tone_text(glance.tone)))
    left.addWidget(state)

    now = section_card("Now running", "play_circle")
    if snap.running:
        now.body.addWidget(RunningScanBlock(snap.running, compact=True))
    now.body.addWidget(hline())
    for i, q in enumerate(snap.queued, start=1):
        row = QHBoxLayout()
        row.addWidget(label(f"{i}", 12, 600, t.fg_subtle))
        row.addWidget(label(q.scan_type, 13, 600))
        row.addWidget(label(q.estimate, 12, 400, t.fg_muted))
        row.addStretch(1)
        if q.sample:
            row.addWidget(StatusPill(text=q.sample, tone="neutral", outlined=True))
        now.body.addLayout(row)
    left.addWidget(now)
    left.addStretch(1)
    body.addWidget(side)

    feed = Card(padding=18)
    head = QHBoxLayout()
    hcol = QVBoxLayout()
    hcol.setSpacing(2)
    hcol.addWidget(label("Since you were last here", 20, 650))
    hcol.addWidget(
        label(
            f"You left at {snap.away_since}, 4 h 10 min ago. " "Here is what happened.",
            13,
            400,
            t.fg_muted,
        )
    )
    head.addLayout(hcol, 1)
    head.addWidget(
        TextButton("Mark all seen", "neutral", "done_all", compact=True),
        0,
        Qt.AlignmentFlag.AlignTop,
    )
    feed.body.addLayout(head)
    chips = QHBoxLayout()
    chips.setSpacing(8)
    for icon, tone, text in snap.away_summary:
        chips.addWidget(SummaryChip(icon, tone, text))
    chips.addStretch(1)
    feed.body.addLayout(chips)
    feed.body.addSpacing(4)

    kinds = {"scan": 0, "problem": 0, "interlock": 0, "config": 0, "note": 0, "session": 0}
    for ev in snap.events:
        kinds[ev.kind] += 1
    problems = kinds["problem"] + kinds["interlock"]
    changes = kinds["config"] + kinds["note"] + kinds["session"]
    filt = SegmentedControl(
        [
            {"text": "All", "count": len(snap.events)},
            {"text": "Scans", "count": kinds["scan"]},
            {"text": "Problems", "count": problems},
            {"text": "Changes and notes", "count": changes},
        ],
        compact=True,
    )
    frow = QHBoxLayout()
    frow.addWidget(filt)
    frow.addStretch(1)
    frow.addWidget(TextButton("Open in logbook", "ghost", "open_in_new", compact=True))
    feed.body.addLayout(frow)
    feed.body.addWidget(hline())

    groups = [("Last hour", snap.events[:3]), ("Earlier this evening", snap.events[3:])]
    for title, events in groups:
        feed.body.addWidget(caption(title))
        for i, ev in enumerate(events):
            feed.body.addWidget(TimelineRow(ev, last=i == len(events) - 1))
    feed.body.addStretch(1)
    body.addWidget(feed, 1)
    return page


BUILDERS = {"board": build_board, "launchpad": build_launchpad, "feed": build_feed}


class WelcomeView(ViewBase):
    """Home view of the main app that summarises the current state of the beamline.

    Args:
        parent(QWidget | None): Parent widget.
        direction(str): First design direction to show: ``board``, ``launchpad`` or ``feed``.
        snapshot(WelcomeSnapshot | None): Data to show; defaults to the demo shift.
        show_switcher(bool): Show the direction switcher used for the design discussion.
    """

    RPC = False
    PLUGIN = False

    navigate = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        direction: str = "board",
        snapshot: WelcomeSnapshot | None = None,
        show_switcher: bool = True,
        **kwargs,
    ):
        super().__init__(parent=parent, view_id="welcome", title="Home", **kwargs)
        self.snapshot = snapshot or demo_snapshot()
        self._direction = direction if direction in BUILDERS else "board"
        self._show_switcher = show_switcher
        self._root = QWidget(self)
        self._root_lay = QVBoxLayout(self._root)
        self._root_lay.setContentsMargins(0, 0, 0, 0)
        self._root_lay.setSpacing(0)
        self.set_content(self._root)
        self._stack: QStackedWidget | None = None
        self._rebuild()
        theme = app_theme()
        if theme is not None:
            theme.theme_changed.connect(self._rebuild)

    @property
    def direction(self) -> str:
        """The design direction on screen."""
        return self._direction

    def set_direction(self, direction: str) -> None:
        """Switch between the design directions."""
        if direction not in BUILDERS:
            raise ValueError(f"Unknown direction {direction!r}; use one of {list(BUILDERS)}")
        self._direction = direction
        self._rebuild()

    def set_snapshot(self, snapshot: WelcomeSnapshot) -> None:
        """Show different data, e.g. another demo scenario."""
        self.snapshot = snapshot
        self._rebuild()

    def set_switcher_visible(self, visible: bool) -> None:
        """Show or hide the direction switcher, e.g. for screenshots."""
        self._show_switcher = visible
        self._rebuild()

    def _rebuild(self, *_args) -> None:
        while self._root_lay.count():
            item = self._root_lay.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if self._show_switcher:
            self._root_lay.addWidget(self._switcher_bar())
        page = BUILDERS[self._direction](self.snapshot)
        self._root_lay.addWidget(_scroll(page), 1)

    def _switcher_bar(self) -> QWidget:
        t = tokens()
        bar = QWidget()
        bar.setObjectName("welcomeSwitcher")
        bar.setStyleSheet(
            f"QWidget#welcomeSwitcher {{ background: {t.card.name()};"
            f" border-bottom: 1px solid {t.border.name()}; }}"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 6, 16, 6)
        row.addWidget(label("Welcome screen mockup", 12, 600, t.fg_muted))
        row.addStretch(1)
        seg = SegmentedControl([title for _, title in DIRECTIONS], compact=True)
        keys = [key for key, _ in DIRECTIONS]
        seg.set_current_index(keys.index(self._direction))
        seg.activated.connect(lambda i: self.set_direction(keys[i]))
        row.addWidget(seg)
        return bar


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_widgets.utils.colors import apply_theme

    qapp = QApplication(sys.argv)
    apply_theme("dark")
    view = WelcomeView(direction=sys.argv[1] if len(sys.argv) > 1 else "board")
    view.resize(1540, 900)
    view.show()
    sys.exit(qapp.exec())
