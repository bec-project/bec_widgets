"""Building blocks of the welcome view, drawn with the BEC UI kit tokens.

The welcome view rebuilds its pages on a theme switch, so these widgets read
:class:`ThemeTokens` once when they are created.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QRectF, Qt, Signal
from qtpy.QtGui import QColor, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.applications.views.welcome_view.welcome_data import (
    Event,
    Glance,
    QuickAction,
    RecentScan,
    RunningScan,
    Workspace,
)
from bec_widgets.utils.quick.tokens import ThemeTokens
from bec_widgets.utils.ux_kit import Card, IconButton, LinearProgress, StatusPill, TextButton

DOCK_ICONS = {
    "Waveform": "show_chart",
    "Image": "image",
    "Heatmap": "grid_on",
    "PositionerBox": "open_with",
    "Queue": "playlist_play",
    "Ring": "donut_large",
    "ScanControl": "tune",
}


def tokens() -> ThemeTokens:
    """Current theme tokens."""
    return ThemeTokens.current()


def label(
    text: str,
    size: int = 13,
    weight: int = 400,
    color: QColor | None = None,
    mono: bool = False,
    wrap: bool = False,
    spacing: float = 0.0,
) -> QLabel:
    """A transparent label with an explicit pixel size, weight and colour."""
    t = tokens()
    lab = QLabel(text)
    family = f"font-family: '{t.mono_family}';" if mono else ""
    extra = f"letter-spacing: {spacing}px;" if spacing else ""
    lab.setStyleSheet(
        f"background: transparent; color: {(color or t.fg).name()}; font-size: {size}px;"
        f" font-weight: {weight}; {family} {extra}"
    )
    lab.setWordWrap(wrap)
    lab.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return lab


def caption(text: str) -> QLabel:
    """Small uppercase section caption."""
    return label(text.upper(), 11, 700, tokens().fg_muted, spacing=0.8)


def icon_label(name: str, color: QColor, size: int = 18, filled: bool = False) -> QLabel:
    """A Material icon as a label."""
    lab = QLabel()
    lab.setStyleSheet("background: transparent;")
    pm = material_icon(
        name, size=(size * 2, size * 2), color=color, filled=filled, convert_to_pixmap=True
    )
    pm.setDevicePixelRatio(2.0)
    lab.setPixmap(pm)
    lab.setFixedSize(size, size)
    return lab


def icon_badge(name: str, tone: str, side: int = 36, icon: int = 20) -> QLabel:
    """Icon centred in a tinted rounded square."""
    t = tokens()
    lab = icon_label(name, t.tone_text(tone) if tone != "neutral" else t.fg_muted, icon)
    lab.setFixedSize(side, side)
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tint = t.tone_tint(tone) if tone != "neutral" else t.hover
    lab.setStyleSheet(f"background: {tint.name()}; border-radius: {side // 4}px;")
    return lab


def keycap(text: str) -> QLabel:
    """Keyboard shortcut hint."""
    t = tokens()
    lab = label(text, 11, 500, t.fg_muted)
    lab.setStyleSheet(
        lab.styleSheet() + f" border: 1px solid {t.border.name()}; border-radius: 4px;"
        f" padding: 1px 5px; background: {t.sunken.name()};"
    )
    return lab


def hline() -> QFrame:
    """Hairline separator."""
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {tokens().separator.name()}; border: none;")
    return line


def vline() -> QFrame:
    """Vertical hairline separator."""
    line = QFrame()
    line.setFixedWidth(1)
    line.setStyleSheet(f"background: {tokens().separator.name()}; border: none;")
    return line


class ClickFrame(QFrame):
    """Frame with a hover fill that emits :attr:`clicked`."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, radius: int = 8, bordered: bool = False):
        super().__init__(parent)
        t = tokens()
        self.setObjectName("wClick")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        border = f"border: 1px solid {t.border.name()};" if bordered else "border: none;"
        bg = t.card.name() if bordered else "transparent"
        self.setStyleSheet(
            f"QFrame#wClick {{ background: {bg}; {border} border-radius: {radius}px; }}"
            f"QFrame#wClick:hover {{ background: {t.hover.name()}; }}"
        )

    def mouseReleaseEvent(self, event):  # pylint: disable=invalid-name
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class GlanceTile(ClickFrame):
    """Subsystem tile: icon, label, big value and a detail line, with a tone accent."""

    def __init__(self, glance: Glance, parent: QWidget | None = None):
        super().__init__(parent, radius=10, bordered=True)
        t = tokens()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)
        lay.addWidget(icon_badge(glance.icon, glance.tone, 40, 22), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(glance.label, 12, 500, t.fg_muted))
        col.addWidget(label(glance.value, 18, 650))
        detail_color = (
            t.tone_text(glance.tone) if glance.tone in ("warning", "danger") else t.fg_subtle
        )
        col.addWidget(label(glance.detail, 12, 400, detail_color))
        lay.addLayout(col, 1)
        lay.addWidget(icon_label("chevron_right", t.fg_subtle, 18), 0, Qt.AlignmentFlag.AlignTop)


class StatusChip(QWidget):
    """Compact glance: tone dot, label and value in one line."""

    def __init__(self, glance: Glance, parent: QWidget | None = None):
        super().__init__(parent)
        t = tokens()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(icon_label(glance.icon, t.tone_text(glance.tone), 18))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(glance.label, 11, 500, t.fg_muted))
        col.addWidget(label(glance.value, 13, 600))
        lay.addLayout(col)


class RunningScanBlock(QWidget):
    """Running scan with progress and the main controls."""

    def __init__(self, scan: RunningScan, compact: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        t = tokens()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(10)
        if scan.paused:
            top.addWidget(StatusPill(text="Paused", tone="warning", icon_name="pause"))
        else:
            top.addWidget(StatusPill(text="Running", tone="info", pulse=True))
        top.addWidget(label(f"#{scan.number}", 14 if compact else 16, 650, t.fg_muted, mono=True))
        top.addWidget(label(scan.scan_type, 14 if compact else 16, 650))
        top.addStretch(1)
        if not compact:
            top.addWidget(TextButton("Live plot", "neutral", "show_chart", compact=True))
            top.addWidget(self._pause_button(scan))
            top.addWidget(TextButton("Abort", "dangerOutline", "stop", compact=True))
        lay.addLayout(top)
        meta = f"{scan.summary}  ·  sample {scan.sample}"
        lay.addWidget(label(meta, 12, 400, t.fg_muted, wrap=compact))
        bar = LinearProgress(
            tone="warning" if scan.paused else "info", thickness=8 if not compact else 6
        )
        bar.set_value(scan.done / scan.total, animate=False)
        lay.addWidget(bar)
        foot = QHBoxLayout()
        pct = round(100 * scan.done / scan.total)
        foot.addWidget(label(f"{scan.done} of {scan.total} points · {pct} %", 12, 500))
        foot.addStretch(1)
        if scan.paused:
            timing = "paused" if compact else "waiting for the interlock"
        else:
            timing = f"{scan.remaining} left"
        foot.addWidget(label(f"{scan.elapsed} elapsed · {timing}", 12, 400, t.fg_muted))
        lay.addLayout(foot)
        if compact:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(TextButton("Live plot", "neutral", "show_chart", compact=True))
            row.addWidget(self._pause_button(scan))
            row.addStretch(1)
            row.addWidget(TextButton("Abort", "dangerOutline", "stop", compact=True))
            lay.addLayout(row)

    @staticmethod
    def _pause_button(scan: RunningScan) -> TextButton:
        if scan.paused:
            return TextButton("Resume", "neutral", "play_arrow", compact=True)
        return TextButton("Pause", "neutral", "pause", compact=True)


class QueueRow(QWidget):
    """One waiting scan."""

    def __init__(
        self,
        index: int,
        scan_type: str,
        summary: str,
        sample: str,
        estimate: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        t = tokens()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(10)
        num = label(str(index), 12, 600, t.fg_subtle)
        num.setFixedWidth(14)
        lay.addWidget(num)
        lay.addWidget(StatusPill(text="Queued", tone="subtle", icon_name="schedule"))
        lay.addWidget(label(scan_type, 13, 600))
        lay.addWidget(label(summary, 12, 400, t.fg_muted), 1)
        if sample:
            lay.addWidget(StatusPill(text=sample, tone="neutral", outlined=True))
        lay.addWidget(label(estimate, 12, 400, t.fg_subtle))


class RecentScansTable(QWidget):
    """Recent scans with status and quick links."""

    def __init__(self, scans: list[RecentScan], parent: QWidget | None = None):
        super().__init__(parent)
        t = tokens()
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(0)
        heads = ["#", "Scan", "", "Sample", "Status", "Time", "Finished", ""]
        for col, head in enumerate(heads):
            grid.addWidget(label(head, 11, 600, t.fg_subtle), 0, col)
        for row, scan in enumerate(scans, start=1):
            r = row * 2
            grid.addWidget(hline(), r - 1, 0, 1, len(heads))
            grid.addWidget(label(str(scan.number), 13, 600, t.fg_muted, mono=True), r, 0)
            grid.addWidget(label(scan.scan_type, 13, 600), r, 1)
            grid.addWidget(label(scan.summary, 12, 400, t.fg_muted), r, 2)
            grid.addWidget(label(scan.sample, 12, 400), r, 3)
            grid.addWidget(StatusPill(text=scan.status, tone=scan.tone), r, 4)
            grid.addWidget(label(scan.duration, 12, 400, t.fg_muted, mono=True), r, 5)
            grid.addWidget(label(scan.finished, 12, 400, t.fg_muted, mono=True), r, 6)
            links = QHBoxLayout()
            links.setSpacing(0)
            links.addWidget(IconButton("show_chart", "Plot in current workspace", compact=True))
            links.addWidget(IconButton("replay", "Re-run in scan control", compact=True))
            links.addWidget(IconButton("more_horiz", "More", compact=True))
            holder = QWidget()
            holder.setStyleSheet("background: transparent;")
            holder.setLayout(links)
            grid.addWidget(holder, r, 7)
            grid.setRowMinimumHeight(r, 38)
        grid.setColumnStretch(2, 1)
        grid.setRowStretch(len(scans) * 2 + 1, 1)


class WorkspaceThumb(QWidget):
    """Schematic preview of a dock layout: one large dock on the left, the rest stacked."""

    def __init__(self, docks: list[str], parent: QWidget | None = None, size=(112, 70)):
        super().__init__(parent)
        self.docks = docks
        self.setFixedSize(*size)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        t = tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(t.border, 1))
        p.setBrush(t.sunken)
        p.drawRoundedRect(r, 6, 6)
        inner = r.adjusted(4, 4, -4, -4)
        rects = []
        if len(self.docks) == 1:
            rects = [inner]
        else:
            left_w = inner.width() * 0.6
            rects.append(QRectF(inner.left(), inner.top(), left_w - 2, inner.height()))
            rest = self.docks[1:]
            h = (inner.height() - 3 * (len(rest) - 1)) / len(rest)
            for i in range(len(rest)):
                rects.append(
                    QRectF(
                        inner.left() + left_w + 1,
                        inner.top() + i * (h + 3),
                        inner.width() - left_w - 1,
                        h,
                    )
                )
        for dock, rect in zip(self.docks, rects):
            p.setPen(QPen(t.border, 1))
            p.setBrush(t.card)
            p.drawRoundedRect(rect, 3, 3)
            if dock == "Waveform" and rect.height() > 30:
                path = QPainterPath()
                pts = [0.85, 0.82, 0.84, 0.78, 0.6, 0.25, 0.2, 0.5, 0.8, 0.83]
                for i, v in enumerate(pts):
                    x = rect.left() + 6 + i * (rect.width() - 12) / (len(pts) - 1)
                    y = rect.top() + 6 + v * (rect.height() - 12)
                    path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
                p.setPen(QPen(t.primary, 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            else:
                side = min(14, int(rect.height()) - 4)
                if side >= 8:
                    pm = material_icon(
                        DOCK_ICONS.get(dock, "widgets"),
                        size=(side * 2, side * 2),
                        color=t.fg_subtle,
                        convert_to_pixmap=True,
                    )
                    p.drawPixmap(
                        QRectF(
                            rect.center().x() - side / 2, rect.center().y() - side / 2, side, side
                        ).toRect(),
                        pm,
                    )
        p.end()


class WorkspaceRow(ClickFrame):
    """Recent workspace as a list row."""

    def __init__(self, ws: Workspace, parent: QWidget | None = None):
        super().__init__(parent)
        t = tokens()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 8, 6)
        lay.setSpacing(12)
        lay.addWidget(WorkspaceThumb(ws.docks, size=(64, 40)))
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(ws.name, 13, 600))
        col.addWidget(label(f"{len(ws.docks)} docks · {ws.opened}", 12, 400, t.fg_muted))
        lay.addLayout(col, 1)
        if ws.current:
            lay.addWidget(StatusPill(text="Open", tone="success"))
        else:
            lay.addWidget(icon_label("open_in_new", t.fg_subtle, 16))


class WorkspaceTile(ClickFrame):
    """Recent workspace as a large tile with a preview."""

    def __init__(self, ws: Workspace, parent: QWidget | None = None):
        super().__init__(parent, radius=10, bordered=True)
        t = tokens()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)
        lay.addWidget(WorkspaceThumb(ws.docks, size=(220, 120)), 0, Qt.AlignmentFlag.AlignHCenter)
        row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(ws.name, 14, 600))
        col.addWidget(label(f"{len(ws.docks)} docks · {ws.opened}", 12, 400, t.fg_muted))
        row.addLayout(col, 1)
        if ws.current:
            row.addWidget(StatusPill(text="Open", tone="success"), 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(row)


class ActionRow(ClickFrame):
    """Quick action as a compact row."""

    def __init__(self, action: QuickAction, parent: QWidget | None = None):
        super().__init__(parent, radius=8, bordered=True)
        self.setToolTip(action.text)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 10, 6)
        lay.setSpacing(10)
        lay.addWidget(icon_badge(action.icon, "primary", 28, 16))
        lay.addWidget(label(action.title, 13, 600), 1)
        if action.shortcut:
            lay.addWidget(keycap(action.shortcut))


class ActionTile(ClickFrame):
    """Quick action as a large tile."""

    def __init__(self, action: QuickAction, parent: QWidget | None = None):
        super().__init__(parent, radius=10, bordered=True)
        t = tokens()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 14)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(icon_badge(action.icon, "primary", 40, 22))
        top.addStretch(1)
        if action.shortcut:
            top.addWidget(keycap(action.shortcut), 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        lay.addSpacing(4)
        lay.addWidget(label(action.title, 14, 600))
        lay.addWidget(label(action.text, 12, 400, t.fg_muted, wrap=True))
        lay.addStretch(1)


class TimelineRow(QWidget):
    """One activity feed entry: time, icon on a rail, text, optional action."""

    def __init__(self, event: Event, last: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.last = last
        self.tone = event.tone
        t = tokens()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        time = label(event.time, 12, 500, t.fg_muted, mono=True)
        time.setFixedWidth(44)
        time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        time.setContentsMargins(0, 8, 0, 0)
        lay.addWidget(time, 0, Qt.AlignmentFlag.AlignTop)
        self.rail_x = 44 + 12 + 16
        badge = icon_badge(event.icon, event.tone, 32, 18)
        lay.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setContentsMargins(0, 6, 0, 14)
        col.setSpacing(2)
        col.addWidget(label(event.title, 13, 600))
        if event.text:
            col.addWidget(label(event.text, 12, 400, t.fg_muted, wrap=True))
        lay.addLayout(col, 1)
        if event.action:
            btn = TextButton(event.action, "ghost", compact=True)
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        if self.last:
            return
        p = QPainter(self)
        p.setPen(QPen(tokens().separator, 2))
        p.drawLine(self.rail_x, 34, self.rail_x, self.height())
        p.end()


class SummaryChip(QWidget):
    """Icon and short text for the 'since you were away' summary."""

    def __init__(self, icon: str, tone: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        t = tokens()
        self.setObjectName("wChip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QWidget#wChip {{ background: {t.tone_tint(tone).name()};" f" border-radius: 14px; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 5, 12, 5)
        lay.setSpacing(6)
        lay.addWidget(icon_label(icon, t.tone_text(tone), 16))
        lay.addWidget(label(text, 12, 600, t.tone_text(tone)))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


def section_card(title: str, icon: str = "", subtitle: str = "", link: str = "") -> Card:
    """A titled card, optionally with a 'View all' style link in the header."""
    card = Card(title, icon_name=icon, padding=16)
    if subtitle:
        card.set_title(title, subtitle)
    if link:
        card.add_header_widget(TextButton(link, "ghost", compact=True))
    return card
