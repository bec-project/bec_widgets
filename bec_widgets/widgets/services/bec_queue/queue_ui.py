"""
Animated rows, keyed row lists and small controls of the BECQueue widget.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from qtpy.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from qtpy.QtGui import QColor, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.theme_utils import DPR_EVENTS, crisp_icon, crisp_pixmap, css, theme_colors
from bec_widgets.widgets.progress.scan_progressbar.scan_hook_tracker import format_duration
from bec_widgets.widgets.progress.scan_progressbar.scan_ui import ElidedLabel, args_items
from bec_widgets.widgets.progress.stage_bar import Tone, mono_font
from bec_widgets.widgets.services.bec_queue.queue_model import QueueEntry


def set_style(widget: QWidget, sheet: str) -> None:
    """Set a stylesheet only when it changed; restyling on every update makes rows flicker."""
    if widget.styleSheet() != sheet:
        widget.setStyleSheet(sheet)


def tone_color(tone: Tone | str) -> QColor:
    """Theme colour for a tone; neutral is the muted colour."""
    colors = theme_colors()
    return {
        Tone.OK: colors["ok"],
        Tone.BAD: colors["bad"],
        Tone.WARN: colors["warn"],
        Tone.RUN: colors["run"],
        Tone.ACCENT: colors["primary"],
    }.get(Tone(tone), colors["muted"])


class IconButton(QToolButton):
    """A flat icon button with a tooltip, used for row actions."""

    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        tone: Tone | str = Tone.NEUTRAL,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._icon_name = icon_name
        self._tone = Tone(tone)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(18, 18))
        self.setFixedSize(26, 26)
        self.refresh_style()

    def event(self, event):  # pylint: disable=invalid-name
        if event.type() in DPR_EVENTS:
            self.refresh_style()  # re-render the icon for the new screen
        return super().event(event)

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        colors = theme_colors()
        color = tone_color(self._tone) if self._tone != Tone.NEUTRAL else colors["fg"]
        self.setIcon(crisp_icon(self._icon_name, 18, color, widget=self))
        set_style(
            self,
            "QToolButton { border: none; border-radius: 5px; background: transparent; }"
            f"QToolButton:hover {{ background: {css(colors['fg'], 0.10)}; }}"
            f"QToolButton:disabled {{ background: transparent; }}",
        )


class MoreButton(QToolButton):
    """
    A flat "more actions" button: three vertical dots in the text colour that open its menu.
    The dots are painted, so they are sharp at every scale and need no icon font.
    """

    def __init__(self, tooltip: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(26, 26)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.refresh_style()

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        colors = theme_colors()
        set_style(
            self,
            "QToolButton { border: none; border-radius: 5px; background: transparent; }"
            f"QToolButton:hover {{ background: {css(colors['fg'], 0.10)}; }}"
            f"QToolButton:focus {{ border: 1px solid {css(colors['primary'])}; }}"
            "QToolButton::menu-indicator { image: none; width: 0; }",
        )
        self.update()

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        colors = theme_colors()
        color = colors["fg"] if self.isEnabled() else colors["muted"]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        radius = 1.8
        center = QRectF(self.rect()).center()
        for offset in (-5.0, 0.0, 5.0):
            painter.drawEllipse(center + QPointF(0, offset), radius, radius)
        painter.end()


class StatusIcon(QLabel):
    """A small status icon whose tooltip tells the status in words."""

    def __init__(self, parent: QWidget | None = None, size: int = 16):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size + 4, size + 4)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_name = ""
        self.tone = Tone.NEUTRAL

    def set_status(self, icon_name: str, tone: Tone | str, tooltip: str) -> None:
        """Show an icon in a tone colour with a tooltip."""
        tone = Tone(tone)
        if (icon_name, tone) == (self.icon_name, self.tone) and self.toolTip() == tooltip:
            return
        self.icon_name, self.tone = icon_name, tone
        self._render_icon()
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)

    def _render_icon(self) -> None:
        if self.icon_name:
            self.setPixmap(
                crisp_pixmap(
                    self.icon_name, self._size, tone_color(self.tone), filled=True, widget=self
                )
            )

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        self._render_icon()

    def event(self, event):  # pylint: disable=invalid-name
        if event.type() in DPR_EVENTS:
            self._render_icon()
        return super().event(event)


class CountBadge(QLabel):
    """A count in a pill that pulses when asked."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("0", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(22)
        self._pulse = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(900)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_pulse)
        self.refresh_style()

    def _on_pulse(self, value) -> None:
        self._pulse = float(value)
        self.refresh_style()

    def pulse(self) -> None:
        """Flash the badge in the accent colour."""
        self._anim.stop()
        self._anim.start()

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        colors = theme_colors()
        bg = css(colors["primary"], 0.15 + 0.75 * self._pulse)
        fg = css(colors["on_primary"]) if self._pulse > 0.4 else css(colors["primary"])
        self.setStyleSheet(
            f"QLabel {{ background: {bg}; color: {fg}; border-radius: 9px; padding: 0 7px;"
            " font-weight: 600; }"
        )


class GroupTitle(QLabel):
    """Uppercase muted title above a group of rows or details."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text.upper(), parent)
        self.refresh_style()

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        self.setStyleSheet(
            f"color: {css(theme_colors()['muted'])}; font-weight: 700; letter-spacing: 1px;"
            " font-size: 11px;"
        )


class DetailGrid(QWidget):
    """Key/value grid for a scan's arguments and metadata."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(2)
        self._grid.setColumnStretch(1, 1)
        self._items: list[tuple[str, str]] | None = None
        self._keys: list[ElidedLabel] = []
        self._values: list[ElidedLabel] = []

    KEY_SHARE_MAX = 0.45  # a very long key may take at most this share of the grid width

    def natural_key_width(self) -> int:
        """Width of the widest key, unelided (with a little slack for fractional advances)."""
        widths = [k.fontMetrics().horizontalAdvance(t) for k, t in self._key_texts()]
        return max(widths) + 2 if widths else 0

    def natural_width(self) -> int:
        """Width this grid needs to show every key and value in full."""
        if not self._items:
            return 0
        values = max(
            (
                v.fontMetrics().horizontalAdvance(t)
                for v, t in zip(self._values, self._value_texts())
            ),
            default=0,
        )
        return self.natural_key_width() + self._grid.horizontalSpacing() + values + 2

    def fit_keys(self, width: int) -> None:
        """
        Give the keys their natural width. Only when key and value do not both fit, the keys
        give way first, down to KEY_SHARE_MAX of the width, then the values elide.
        """
        natural_key = self.natural_key_width()
        values = self.natural_width() - natural_key
        room_for_keys = max(width - values, int(width * self.KEY_SHARE_MAX))
        key_width = max(1, min(natural_key, room_for_keys))
        for key in self._keys:
            key.setFixedWidth(key_width)
        # the keys ignore their size hints, so the column needs its width set explicitly
        self._grid.setColumnMinimumWidth(0, key_width)

    def _key_texts(self):
        return [(k, k.full_text()) for k in self._keys]

    def _value_texts(self):
        return [v.full_text() for v in self._values]

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        if self._items is not None:
            self.set_items(self._items, force=True)

    def set_items(self, items: list[tuple[str, str]], force: bool = False) -> None:
        """Replace the rows, unless they did not change."""
        if items == self._items and not force:
            return
        self._items = list(items)
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        muted = css(theme_colors()["muted"])
        self._keys, self._values = [], []
        for row, (key, value) in enumerate(items):
            k = ElidedLabel(key, self)
            k.setStyleSheet(f"color: {muted};")
            k.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            # one line per value, cut with the full text as tooltip; never widens the view
            v = ElidedLabel(value, self)
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if key == "args":
                v.setFont(mono_font(-1))
            self._grid.addWidget(k, row, 0)
            self._grid.addWidget(v, row, 1)
            self._keys.append(k)
            self._values.append(v)


def entry_detail_columns(entry: QueueEntry) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """
    The details of an entry split in two: (scan arguments and request info, user metadata).
    Every argument is its own row.
    """
    arguments = args_items(getattr(entry.request, "parameter", None), entry.bundle_names)
    if not arguments and entry.args:
        arguments = [("args", entry.args)]
    if entry.scan_type and entry.scan_type != entry.name:
        arguments.append(("scan", entry.scan_type))
    if entry.blocks > 1:
        arguments.append(("requests", f"{entry.blocks} scans in this queue item"))
    return arguments, list(entry.metadata)


def finished_times(entry: QueueEntry, today: date | None = None) -> str:
    """
    Start time and duration of a finished entry: "14:03:21 (0:11)", or "Oct 29 14:03 (0:11)"
    for a scan from another day. Without a known start, the finish time minus the duration.
    """
    took = f"({format_duration(entry.duration)})" if entry.duration is not None else ""
    start = entry.started_at
    if start is None and entry.finished_at is not None and entry.duration is not None:
        start = entry.finished_at - entry.duration
    if not start:
        return took
    started = datetime.fromtimestamp(start)
    if started.date() == (today or date.today()):
        when = f"{started:%H:%M:%S}"
    else:
        when = f"{started:%b} {started.day} {started:%H:%M}"
    return f"{when} {took}".strip()


def finished_tooltip(entry: QueueEntry) -> str:
    """Tooltip for a finished entry's status icon: status, time, duration."""
    _, _, word = entry.history_status
    parts = [word]
    if entry.finished_at:
        parts.append(f"at {datetime.fromtimestamp(entry.finished_at):%H:%M:%S}")
    if entry.duration is not None:
        parts.append(f"took {format_duration(entry.duration)}")
    return " · ".join(parts)


class AnimatedRow(QFrame):
    """
    A rounded row that can flash, slide in, and collapse out; hovered or selected rows are
    highlighted.

    Subclasses add their content to ``self.body`` (a QVBoxLayout).
    """

    clicked = Signal(str)
    height_changed = Signal()

    def __init__(self, key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.key = key
        self.leaving = False
        self.selected = False
        self._hover = False
        self._flash = 0.0
        self._flash_tone = Tone.ACCENT
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(6, 3, 6, 3)
        self.body.setSpacing(3)

        self._flash_anim = QVariantAnimation(self)
        self._flash_anim.setDuration(1400)
        self._flash_anim.setStartValue(1.0)
        self._flash_anim.setEndValue(0.0)
        self._flash_anim.setEasingCurve(QEasingCurve.Type.InQuad)
        self._flash_anim.valueChanged.connect(self._on_flash)
        self._height_anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._height_anim.setDuration(260)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._height_anim.finished.connect(self._on_height_finished)
        self._height_anim.valueChanged.connect(lambda _v: self.height_changed.emit())
        self._height_done: Callable[[], None] | None = None
        self.move_anim = QPropertyAnimation(self, b"pos", self)
        self.move_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _on_flash(self, value) -> None:
        self._flash = float(value)
        self.update()

    def flash(self, tone: Tone | str = Tone.ACCENT) -> None:
        """Highlight the row and fade the highlight out."""
        self._flash_tone = Tone(tone)
        self._flash_anim.stop()
        self._flash_anim.start()

    @property
    def flashing(self) -> bool:
        """Whether a flash is running."""
        return self._flash_anim.state() == QVariantAnimation.State.Running

    def slide_in(self) -> None:
        """Grow from zero height, then flash."""
        target = max(self.sizeHint().height(), 24)
        self._height_anim.stop()
        self._height_done = lambda: self.setMaximumHeight(16777215)
        self._height_anim.setStartValue(0)
        self._height_anim.setEndValue(target)
        self._height_anim.start()
        self.flash(Tone.ACCENT)

    def leave(self, on_done: Callable[[], None] | None = None) -> None:
        """Turn red and collapse to zero height, then call on_done."""
        if self.leaving:
            return
        self.leaving = True
        self.setEnabled(False)
        self._flash_tone = Tone.BAD
        self._flash = 1.0
        self.update()
        self._height_anim.stop()
        self._height_done = on_done
        self._height_anim.setDuration(380)
        self._height_anim.setStartValue(self.height())
        self._height_anim.setEndValue(0)
        self._height_anim.start()

    def _on_height_finished(self) -> None:
        done, self._height_done = self._height_done, None
        if done is not None:
            done()
        self.height_changed.emit()

    def wanted_height(self, width: int) -> int:
        """Height for a width, limited by a running height animation."""
        if self.hasHeightForWidth():
            height = self.heightForWidth(width)
        else:
            height = self.sizeHint().height()
        return max(0, min(height, self.maximumHeight()))

    def set_selected(self, selected: bool) -> None:
        """Mark the row as selected."""
        if selected != self.selected:
            self.selected = selected
            self.update()

    def enterEvent(self, event):  # pylint: disable=invalid-name
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # pylint: disable=invalid-name
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self.key)
        super().mouseReleaseEvent(event)

    @property
    def gliding(self) -> bool:
        """Whether the row is moving to a new place in its list."""
        return self.move_anim.state() == QPropertyAnimation.State.Running

    def stop_animations(self) -> None:
        """Stop running animations (before deletion)."""
        self._flash_anim.stop()
        self._height_anim.stop()
        self.move_anim.stop()

    def paintEvent(self, event):  # pylint: disable=invalid-name
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 7, 7)
        if self.selected:
            sel = QColor(colors["primary"])
            sel.setAlphaF(0.16)
            painter.fillPath(path, sel)
        elif self._hover:
            hov = QColor(colors["fg"])
            hov.setAlphaF(0.06)
            painter.fillPath(path, hov)
        if self._flash > 0:
            flash = QColor(tone_color(self._flash_tone))
            flash.setAlphaF(0.32 * self._flash)
            painter.fillPath(path, flash)
        if self.selected:
            border = colors["primary"]
            if self._flash > 0.05:
                border = tone_color(self._flash_tone)
            painter.setPen(QPen(border, 1))
            painter.drawPath(path)
        painter.end()
        super().paintEvent(event)


class KeyedRowList(QWidget):
    """
    A vertical list of AnimatedRow widgets kept in sync with a list of entries by key.

    New rows slide in, vanished rows collapse out, kept rows are reused and glide to their new
    place when the order changes. Rows are placed by hand rather than by a layout, so a reorder
    can animate and an update that changes nothing does not touch the geometry.
    """

    MOVE_MS = 240

    def __init__(
        self,
        make_row: Callable[[QueueEntry], AnimatedRow],
        update_row: Callable[[AnimatedRow, QueueEntry], None],
        parent: QWidget | None = None,
        spacing: int = 4,
    ):
        super().__init__(parent)
        self._make_row = make_row
        self._update_row = update_row
        self._spacing = spacing
        self.rows: dict[str, AnimatedRow] = {}
        self.order: list[str] = []
        self._layout_keys: list[str] = []
        self._height = 0
        self._initialised = False
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def sync(self, entries: list[QueueEntry], animate: bool = True) -> list[str]:
        """
        Make the rows match the entries.

        Returns:
            list[str]: Keys of rows whose position changed.
        """
        animate = animate and self._initialised
        self._initialised = True
        new_order = [e.key for e in entries]
        old_index = {k: i for i, k in enumerate(self.order)}
        moved = []
        for index, entry in enumerate(entries):
            row = self.rows.get(entry.key)
            if row is None or row.leaving:
                if row is not None:
                    self._drop(row)
                row = self._make_row(entry)
                row.setParent(self)
                row.height_changed.connect(self._relayout)
                self.rows[entry.key] = row
                self._update_row(row, entry)
                if animate:
                    row.slide_in()
                row.show()
                continue
            if old_index.get(entry.key) != index:
                moved.append(entry.key)
            self._update_row(row, entry)

        for key in list(self.rows):
            if key not in new_order:
                row = self.rows[key]
                if not row.leaving:
                    if animate:
                        row.leave(lambda r=row: self._drop(r))
                    else:
                        self._drop(row)

        # leaving rows keep their old place until they have collapsed
        layout_keys = list(new_order)
        for key in self._layout_keys:
            row = self.rows.get(key)
            if row is not None and row.leaving and key not in layout_keys:
                layout_keys.insert(min(old_index.get(key, len(layout_keys)), len(layout_keys)), key)
        self._layout_keys = layout_keys
        self.order = new_order
        self._relayout(animate=animate, lift=moved)
        return moved

    def _targets(self) -> dict[str, QRect]:
        width = self.width()
        y = 0
        targets = {}
        for key in self._layout_keys:
            row = self.rows.get(key)
            if row is None:
                continue
            height = row.wanted_height(width)
            targets[key] = QRect(0, y, width, height)
            y += height + (self._spacing if height > 0 else 0)
        self._height = max(0, y - self._spacing) if targets else 0
        return targets

    def _relayout(self, animate: bool = False, lift: list[str] | None = None) -> None:
        targets = self._targets()
        if self.minimumHeight() != self._height or self.maximumHeight() != self._height:
            self.setFixedHeight(self._height)
        for key, rect in targets.items():
            row = self.rows[key]
            if row.size() != rect.size():
                row.resize(rect.size())
            running = row.gliding
            if row.pos() == rect.topLeft() and not running:
                continue
            if (animate or running) and row.isVisible() and row.height() > 0:
                self._glide(row, rect.topLeft())
            else:
                row.move(rect.topLeft())
        for key in lift or ():
            row = self.rows.get(key)
            if row is not None:
                row.raise_()

    def _glide(self, row: AnimatedRow, target: QPoint) -> None:
        anim = row.move_anim
        anim.setDuration(self.MOVE_MS)
        if anim.state() == QPropertyAnimation.State.Running:
            if anim.endValue() == target:
                return
            anim.stop()
        anim.setStartValue(row.pos())
        anim.setEndValue(target)
        anim.start()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        return QSize(super().sizeHint().width(), self._height)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._relayout()

    def event(self, event):
        if event.type() == QEvent.Type.LayoutRequest:
            # a row's content changed size
            self._relayout()
        return super().event(event)

    def _drop(self, row: AnimatedRow) -> None:
        if self.rows.get(row.key) is row:
            del self.rows[row.key]
        row.stop_animations()
        row.hide()
        row.deleteLater()
        if row.key in self._layout_keys and row.key not in self.rows:
            self._layout_keys.remove(row.key)
        self._relayout()

    def remove_animated(self, key: str) -> None:
        """Collapse a row out now, before the queue confirms its removal."""
        row = self.rows.get(key)
        if row is not None and not row.leaving:
            row.leave(lambda r=row: self._drop(r))

    def row(self, key: str) -> AnimatedRow | None:
        """The row for a key, if shown."""
        row = self.rows.get(key)
        return row if row is not None and not row.leaving else None

    @property
    def gliding(self) -> list[str]:
        """Keys of rows that are moving to a new place."""
        return [key for key, row in self.rows.items() if row.gliding]

    def stop_animations(self) -> None:
        """Stop all row animations."""
        for row in self.rows.values():
            row.stop_animations()
