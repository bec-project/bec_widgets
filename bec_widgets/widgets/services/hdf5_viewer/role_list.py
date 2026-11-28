"""
The list under a field of the box on top of the Signals panel, and the keys of the fields.

Typing in a field opens a list of the signals that fit the text, the best fit first; the arrow
of the field (or Down) opens the full list of what can take the role, by group. Enter gives
the marked signal the role. The list is a child of the panel, not a window of its own, so the
field keeps the focus and it behaves the same under every window manager.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt, Signal
from qtpy.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QStandardItem,
    QStandardItemModel,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.theme_utils import theme_colors
from bec_widgets.widgets.services.bec_queue.queue_ui import ROW_HOVER_ALPHA, ROW_SELECTED_ALPHA
from bec_widgets.widgets.services.hdf5_viewer.role_fields import (
    BORDER_ALPHA,
    FIELD_RADIUS,
    RoleBox,
    RoleField,
)
from bec_widgets.widgets.services.hdf5_viewer.style import paint_group_head

SourceKey = tuple[str, str]

#: Height of a line of the list, and the most and fewest lines it shows.
LIST_ROW_HEIGHT = 24
LIST_MAX_ROWS = 8
LIST_MIN_ROWS = 3
#: Space between the text of a line and the sides of the list.
LIST_PADDING = 10
#: Data of the lines of the list.
ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1
#: Why a field may lose the focus and keep its text and list: its window was left, or a menu
#: opened over it.
KEEP_REASONS = (Qt.FocusReason.ActiveWindowFocusReason, Qt.FocusReason.PopupFocusReason)
#: Line breaks and tabs in pasted text become spaces.
FLATTEN = str.maketrans({"\n": " ", "\r": " ", "\t": " "})


@dataclass(frozen=True)
class ListEntry:
    """A line of the list under a field."""

    #: ``head`` (a group with its count), ``entry`` (a signal) or ``message``.
    kind: str
    text: str
    key: SourceKey | None = None
    #: Letters of the name that the typed text matched.
    positions: tuple[int, ...] = ()
    #: Said at the right, e.g. "Monitored · 100"; ``short`` is what is left of it when it
    #: must give way, e.g. "100".
    right: str = ""
    short: str = ""
    #: ``""`` can take the role, ``on`` has it (a tick; the mark skips it), ``off`` cannot.
    state: str = ""
    #: The count of a group.
    count: int = 0
    #: A message in the colour of the text rather than muted.
    strong: bool = False

    @property
    def takeable(self) -> bool:
        """Whether the mark can rest on it and Enter give it the role."""
        return self.kind == "entry" and self.state == ""


@dataclass(frozen=True)
class Listing:
    """What the list under a field shows."""

    entries: tuple[ListEntry, ...]
    #: The entry marked when the list opens, or None.
    mark: int | None


def elide_marked(
    name: str, positions: tuple[int, ...], metrics: QFontMetrics, room: int
) -> tuple[str, tuple[int, ...]]:
    """
    Cut a name in its middle to fit, and move its marked letters along; a marked letter that
    falls into the cut is not shown.

    Args:
        name (str): The name.
        positions (tuple[int, ...]): Marked letters of the name.
        metrics (QFontMetrics): Metrics of the font it is drawn in.
        room (int): Width in pixels.

    Returns:
        tuple[str, tuple[int, ...]]: The name as shown and the marked letters in it.
    """
    shown = metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, max(room, 0))
    if shown == name:
        return name, positions
    cut = shown.find("…")
    if cut < 0:
        return shown, ()
    head, tail = cut, len(shown) - cut - 1
    moved = []
    for position in positions:
        if position < head:
            moved.append(position)
        elif position >= len(name) - tail:
            moved.append(position - (len(name) - tail) + head + 1)
    return shown, tuple(moved)


def runs(text: str, positions: tuple[int, ...]) -> list[tuple[str, bool]]:
    """
    Split a text into runs of marked and unmarked letters.

    Args:
        text (str): The text.
        positions (tuple[int, ...]): The marked letters.

    Returns:
        list[tuple[str, bool]]: Each run and whether it is marked.
    """
    marked = set(positions)
    out: list[tuple[str, bool]] = []
    for index, char in enumerate(text):
        state = index in marked
        if out and out[-1][1] == state:
            out[-1] = (out[-1][0] + char, state)
        else:
            out.append((char, state))
    return out


def _over(color: QColor, alpha: float, base: QColor) -> QColor:
    """A colour at ``alpha`` laid over an opaque one."""
    return QColor(
        round(color.red() * alpha + base.red() * (1 - alpha)),
        round(color.green() * alpha + base.green() * (1 - alpha)),
        round(color.blue() * alpha + base.blue() * (1 - alpha)),
    )


class _ListDelegate(QStyledItemDelegate):
    """Draws the lines of the list: groups with their count, signals with their matched
    letters and the length or reason at the right, and messages."""

    def __init__(self, view: QListView):
        super().__init__(view)
        self.mark: int | None = None
        #: The theme's colours, read once per filling of the list, not once per line.
        self.colors: dict[str, QColor] = {}
        self.tick = None

    def read_theme(self) -> None:
        """Read the colours of the theme."""
        colors = theme_colors()
        # The list lies over the rows below: its card must hide them, also where the theme
        # gives cards some transparency.
        card = _over(colors["card"], colors["card"].alphaF(), colors["bg"])
        self.colors = {
            "fg": colors["fg"],
            "muted": _over(colors["fg"], colors["muted"].alphaF(), card),
            "primary": colors["primary"],
            "card": card,
            "border": _over(colors["fg"], BORDER_ALPHA, card),
            "mark": _over(colors["primary"], ROW_SELECTED_ALPHA, card),
            "hover": _over(colors["fg"], ROW_HOVER_ALPHA, card),
        }
        self.tick = material_icon("check", size=(14, 14), color=colors["primary"].name())

    def sizeHint(self, option, index) -> QSize:  # pylint: disable=invalid-name
        return QSize(option.rect.width(), LIST_ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        entry: ListEntry = index.data(ENTRY_ROLE)
        if entry is None or not self.colors:
            return
        colors = self.colors
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRect(option.rect)
        shade = None
        if index.row() == self.mark:
            shade = colors["mark"]
        elif entry.takeable and option.state & QStyle.StateFlag.State_MouseOver:
            shade = colors["hover"]
        if shade is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shade)
            painter.drawRoundedRect(QRectF(rect).adjusted(3, 1, -3, -1), 5, 5)
        inner = rect.adjusted(LIST_PADDING, 0, -LIST_PADDING, 0)
        font = QFont(option.font)
        if entry.kind == "head":
            # The header of the signal list's groups; a line parts it from rows above.
            paint_group_head(
                painter,
                rect,
                entry.text,
                entry.count,
                colors["card"],
                font,
                rule=index.row() > 0,
                padding=LIST_PADDING,
            )
        elif entry.kind == "message":
            painter.setFont(font)
            painter.setPen(colors["fg"] if entry.strong else colors["muted"])
            text = QFontMetrics(font).elidedText(
                entry.text, Qt.TextElideMode.ElideRight, inner.width()
            )
            painter.drawText(inner, Qt.AlignmentFlag.AlignVCenter, text)
        else:
            self._paint_entry(painter, inner, entry, font)
        painter.restore()

    def _paint_entry(self, painter: QPainter, rect: QRect, entry: ListEntry, font: QFont):
        colors = self.colors
        metrics = QFontMetrics(font)
        small = QFont(font)
        small.setPixelSize(11)
        small_metrics = QFontMetrics(small)
        tick = 18 if entry.state == "on" else 0
        strong = QFont(font)
        strong.setWeight(QFont.Weight.Bold)
        strong.setUnderline(True)
        strong_metrics = QFontMetrics(strong)
        # Marked letters are drawn bold, so the name is that much wider.
        extra = sum(
            strong_metrics.horizontalAdvance(run) - metrics.horizontalAdvance(run)
            for run, marked in runs(entry.text, entry.positions)
            if marked
        )
        # The text at the right gives way first, to its short form and then wholly, before
        # the name is cut; the tick of a signal that has the role stays.
        name_width = metrics.horizontalAdvance(entry.text) + extra
        right = ""
        for candidate in (entry.right, entry.short):
            if not candidate:
                continue
            need = small_metrics.horizontalAdvance(candidate) + tick + 12
            if name_width + need <= rect.width():
                right = candidate
                break
        right_width = small_metrics.horizontalAdvance(right) if right else 0
        used = right_width + tick + (12 if right_width or tick else 0)
        room = rect.width() - used
        shown, positions = elide_marked(entry.text, entry.positions, metrics, room - extra)
        ink = colors["muted"] if entry.state == "off" else colors["fg"]
        x = rect.left()
        painter.setPen(ink)
        for run, marked in runs(shown, positions):
            run_font = strong if marked else font
            painter.setFont(run_font)
            width = QFontMetrics(run_font).horizontalAdvance(run)
            painter.drawText(
                QRect(x, rect.top(), width + 1, rect.height()), Qt.AlignmentFlag.AlignVCenter, run
            )
            x += width
        right_left = rect.right() - right_width
        if right:
            painter.setFont(small)
            painter.setPen(colors["muted"] if entry.state != "on" else colors["primary"])
            painter.drawText(
                QRect(right_left, rect.top(), right_width + 1, rect.height()),
                Qt.AlignmentFlag.AlignVCenter,
                right,
            )
        if tick and self.tick is not None:
            left = right_left - (4 if right else 0) - 14
            painter.drawPixmap(left, rect.center().y() - 6, self.tick)


class RoleList(QFrame):
    """The list under a field: what fits the typed text, or everything that can take the
    role; a child of the panel raised above what lies under it."""

    #: A line that can take the role was clicked: the key of its signal.
    entry_clicked = Signal(object)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("role_list")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view = QListView(self)
        self.view.setObjectName("role_list_view")
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setUniformItemSizes(True)
        self.view.setMouseTracking(True)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setStyleSheet("QListView { background: transparent; border: none; }")
        self.model = QStandardItemModel(self)
        self.view.setModel(self.model)
        self.delegate = _ListDelegate(self.view)
        self.view.setItemDelegate(self.delegate)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 4, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.view)
        self.view.clicked.connect(self._on_clicked)
        self.listing = Listing((), None)
        self.hide()

    def show_listing(self, listing: Listing, mark: int | None) -> None:
        """
        Fill the list and mark an entry.

        Args:
            listing (Listing): What to show.
            mark (int | None): The entry Enter takes, or None.
        """
        self.delegate.read_theme()
        self.listing = listing
        self.model.clear()
        self.view.scrollToTop()
        for entry in listing.entries:
            item = QStandardItem()
            item.setData(entry, ENTRY_ROLE)
            text = entry.text
            if entry.kind == "entry" and entry.right:
                text = f"{text}, {entry.right}"
            item.setData(text, Qt.ItemDataRole.AccessibleTextRole)
            if entry.kind == "entry" and entry.text != text:
                item.setToolTip(entry.text)
            item.setEditable(False)
            # Groups, messages and signals that cannot take the role cannot be chosen.
            item.setEnabled(entry.kind == "entry" and entry.state != "off")
            self.model.appendRow(item)
        self.set_mark(mark)

    def set_mark(self, mark: int | None) -> None:
        """
        Mark an entry, the one Enter takes, or none.

        Args:
            mark (int | None): Its line, or None.
        """
        self.delegate.mark = mark
        if mark is not None and self.listing.entries:
            self.view.scrollTo(self.model.index(mark, 0))
        self.view.viewport().update()

    def marked(self) -> int | None:
        """The marked entry, or None."""
        return self.delegate.mark

    def step(self, delta: int) -> None:
        """
        Move the mark to the next (or previous) entry that can take the role; groups and
        entries that have it or cannot take it are skipped.

        Args:
            delta (int): 1 for down, -1 for up.
        """
        entries = self.listing.entries
        mark = self.delegate.mark
        index = (-1 if delta > 0 else len(entries)) if mark is None else mark
        while 0 <= index + delta < len(entries):
            index += delta
            if entries[index].takeable:
                self.set_mark(index)
                return

    def fit_rows(self, room: int) -> int:
        """
        The lines to show: all up to eight, fewer in a short panel, never under three.

        Args:
            room (int): Height in pixels below the field.

        Returns:
            int: The number of lines.
        """
        count = len(self.listing.entries)
        rows = min(count, LIST_MAX_ROWS)
        while rows > LIST_MIN_ROWS and rows * LIST_ROW_HEIGHT + 8 > room:
            rows -= 1
        return max(rows, min(count, LIST_MIN_ROWS), 1)

    def place(self, field: QWidget, panel: QWidget, move: bool = True) -> None:
        """
        Lay the list under a field, as wide as it, within the panel.

        Args:
            field (QWidget): The field.
            panel (QWidget): The panel the list is a child of.
            move (bool): Whether to move it; False keeps it where it is, e.g. while the
                pointer is on it.
        """
        top_left = field.mapTo(panel, QPoint(0, field.height() + 2))
        self.setFixedWidth(field.width())
        if not move:
            top_left = self.pos()
        rows = self.fit_rows(panel.height() - top_left.y() - 4)
        self.view.setFixedHeight(rows * LIST_ROW_HEIGHT)
        self.adjustSize()
        self.move(top_left)
        self.raise_()
        mark = self.delegate.mark
        if mark is not None:
            # Now that the list has its height, the marked line is in view without a part
            # line above it.
            self.view.scrollTo(self.model.index(mark, 0))

    def _on_clicked(self, index) -> None:
        entry: ListEntry = index.data(ENTRY_ROLE)
        if entry is not None and entry.takeable:
            self.entry_clicked.emit(entry.key)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        colors = self.delegate.colors
        if not colors:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(colors["border"]))
        painter.setBrush(colors["card"])
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), FIELD_RADIUS, FIELD_RADIUS
        )
        painter.end()


class RoleTyping(QObject):
    """
    Typing in the fields of the box: opens, narrows and closes the list under a field, and
    gives the role to what is chosen in it. The keys are those of a combobox, plus walking
    the chips of the curves with Left and Right.
    """

    def __init__(
        self,
        panel: QWidget,
        box: RoleBox,
        listing_of: Callable[[str, str], Listing],
        take: Callable[[str, SourceKey], None],
        remove: Callable[[str, SourceKey], None],
    ):
        """
        Args:
            panel (QWidget): The Signals panel; the list is its child.
            box (RoleBox): The box with the fields.
            listing_of (Callable[[str, str], Listing]): The list of a role for a typed text;
                an empty text gives the full list.
            take (Callable[[str, SourceKey], None]): Gives a signal the role of a field.
            remove (Callable[[str, SourceKey], None]): Takes a curve off the plot.
        """
        super().__init__(panel)
        self.panel = panel
        self.box = box
        self.list = RoleList(panel)
        self._listing_of = listing_of
        self._take = take
        self._remove = remove
        #: The field whose list is open, and whether the user opened it rather than typing.
        self.letter: str | None = None
        self.by_user = False
        #: The chip marked with Left in a field of curves.
        self.chip_mark: int | None = None
        self._watching = False
        self._attached: set[int] = set()
        self.list.entry_clicked.connect(lambda key: self._take_key(self.letter, key))
        box.arrow_clicked.connect(self._on_arrow)
        panel.installEventFilter(self)

    def attach(self) -> None:
        """Listen to the fields of the box; call after it built its rows anew."""
        self.close()
        self.chip_mark = None
        for letter, field in self.box.fields.items():
            if id(field.edit) in self._attached:
                continue
            self._attached.add(id(field.edit))
            field.edit.installEventFilter(self)
            field.installEventFilter(self)
            field.edit.textChanged.connect(lambda text, letter=letter: self._on_text(letter, text))
            field.edit.destroyed.connect(
                lambda _obj=None, ident=id(field.edit): self._attached.discard(ident)
            )

    def field(self, letter: str | None) -> RoleField | None:
        """The field of a letter, if the box has it."""
        return self.box.fields.get(letter) if letter else None

    # -- the list ---------------------------------------------------------------------

    def is_open(self, letter: str | None = None) -> bool:
        """
        Whether a list is open, under the field of ``letter`` if given.

        Args:
            letter (str | None): The field.

        Returns:
            bool: True while it shows.
        """
        return self.list.isVisible() and (letter is None or letter == self.letter)

    def open(self, letter: str, by_user: bool, mark_first: bool = False) -> None:
        """
        Open (or fill again) the list under a field.

        Args:
            letter (str): The field.
            by_user (bool): Whether the user opened it with the arrow or Down; such a list
                stays until it is closed.
            mark_first (bool): Mark the first entry of a full list that can take the role.
        """
        field = self.field(letter)
        if field is None:
            return
        text = field.edit.text().strip()
        listing = self._listing_of(letter, text)
        mark = listing.mark
        if not text:
            first = next((i for i, e in enumerate(listing.entries) if e.takeable), None)
            mark = first if mark_first else None
        keep = self.is_open(letter) and self.list.underMouse()
        self.letter = letter
        self.by_user = by_user
        self.list.view.setAccessibleName(f"Signals that {field.role.can_be}")
        # A click on the list counts as a click on the field: the field keeps the focus, so
        # a pane that takes the focus on a click (a dock in bec-app) cannot close the list on
        # the press before the click takes its line.
        self.list.setFocusProxy(field.edit)
        self.list.show_listing(listing, mark)
        self.list.place(field, self.panel, move=not keep)
        self.list.show()
        self.list.place(field, self.panel, move=not keep)
        self._watch(True)

    def refresh(self) -> None:
        """Fill an open list again, e.g. after the signals or their roles changed."""
        if self.is_open() and self.field(self.letter) is not None:
            marked = self.list.marked()
            key = self.list.listing.entries[marked].key if marked is not None else None
            self.open(self.letter, self.by_user)
            if key is not None:
                entries = self.list.listing.entries
                again = next((i for i, e in enumerate(entries) if e.key == key), None)
                if again is not None and entries[again].takeable:
                    self.list.set_mark(again)
        elif self.is_open():
            self.close()

    def close(self) -> None:
        """Close the list; the text of the field stays."""
        if self.list.isVisible():
            self.list.hide()
        self.list.setFocusProxy(None)
        self.letter = None
        self.by_user = False
        self._watch(False)

    def _watch(self, on: bool) -> None:
        """Close the list on a click outside it while it is open."""
        app = QApplication.instance()
        if app is None or on == self._watching:
            return
        if on:
            app.installEventFilter(self)
        else:
            app.removeEventFilter(self)
        self._watching = on

    def _on_arrow(self, letter: str) -> None:
        field = self.field(letter)
        if field is None:
            return
        if self.is_open(letter) and self.by_user:
            self.close()
        else:
            self.open(letter, by_user=True)
        field.edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_text(self, letter: str, text: str) -> None:
        self._set_chip_mark(letter, None)
        field = self.field(letter)
        if field is None:
            return
        flat = text.translate(FLATTEN)
        if flat != text:
            # Pasted lines and tabs are spaces, as between typed words.
            cursor = field.edit.cursorPosition()
            field.edit.blockSignals(True)
            field.edit.setText(flat)
            field.edit.setCursorPosition(cursor)
            field.edit.blockSignals(False)
            text = flat
        field.scroll_to_text()
        if text.strip():
            self.open(letter, by_user=self.by_user and self.letter == letter)
        elif self.is_open(letter):
            if self.by_user:
                self.open(letter, by_user=True)
            else:
                self.close()

    def _take_key(self, letter: str | None, key: SourceKey | None) -> None:
        """Give the role of a field to a signal of its list."""
        field = self.field(letter)
        if field is None or key is None:
            return
        multi, by_user = field.role.multi, self.by_user
        self._take(letter, key)
        field = self.field(letter)
        if field is None:
            self.close()
            return
        field.edit.blockSignals(True)
        field.edit.clear()
        field.edit.blockSignals(False)
        if multi and by_user:
            # Several curves in a row: the tick shows in place, the mark moves on.
            self.open(letter, by_user=True)
            entries = self.list.listing.entries
            at = next((i for i, e in enumerate(entries) if e.key == key), -1)
            following = (i for i in range(at + 1, len(entries)) if entries[i].takeable)
            self.list.set_mark(next(following, None))
        else:
            self.close()
        field.edit.setFocus(Qt.FocusReason.OtherFocusReason)

    # -- the chips of the curves --------------------------------------------------------

    def _set_chip_mark(self, letter: str, index: int | None) -> None:
        field = self.field(letter)
        if field is None:
            return
        chips = field.flow.chips
        self.chip_mark = index if index is not None and 0 <= index < len(chips) else None
        for position, chip in enumerate(chips):
            chip.set_marked(position == self.chip_mark)
        if self.chip_mark is not None:
            field.ensure_visible(chips[self.chip_mark])

    # -- events -------------------------------------------------------------------------

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and self._watching:
            self._close_on_outside_click(watched)
            return False
        if watched is self.panel:
            if kind in (QEvent.Type.Resize, QEvent.Type.Hide):
                self.close()
            return False
        if kind in (QEvent.Type.Resize, QEvent.Type.Move) and self.is_open():
            field = self.field(self.letter)
            if watched is field and not self.list.underMouse():
                # The field grew a line of chips: the list follows it, unless the pointer is
                # on the list, which then stays where it is.
                self.list.place(field, self.panel)
            return False
        letter = next(
            (key for key, field in self.box.fields.items() if field.edit is watched), None
        )
        if letter is None:
            return False
        if kind == QEvent.Type.KeyPress:
            return self._key(letter, event)
        if kind == QEvent.Type.FocusOut:
            if event.reason() in KEEP_REASONS:
                # The window lost the focus (another application, or the pointer drifting out
                # under focus-follows-mouse) or a menu took it: all stays as the user left it.
                self.box.fields[letter].update()
                return False
            self._set_chip_mark(letter, None)
            if self.letter == letter:
                self.close()
            # Leaving for another widget drops what was typed; nothing changes on the plot.
            self.box.fields[letter].edit.clear()
            self.box.fields[letter].update()
        elif kind == QEvent.Type.FocusIn:
            self.box.fields[letter].update()
        return False

    def _close_on_outside_click(self, watched) -> None:
        if not isinstance(watched, QWidget):
            return
        for inside in (self.list, self.field(self.letter)):
            if inside is not None and (watched is inside or inside.isAncestorOf(watched)):
                return
        self.close()

    def _key(self, letter: str, event) -> bool:
        field = self.box.fields[letter]
        edit = field.edit
        key = event.key()
        chips = field.flow.chips
        multi = field.role.multi
        if self.chip_mark is not None:
            if self._chip_key(letter, key, chips):
                return True
            # Any other key returns to typing.
            self._set_chip_mark(letter, None)
        empty = not edit.text()
        if multi and chips and key == Qt.Key.Key_Left and edit.cursorPosition() == 0:
            if not edit.hasSelectedText():
                self.close()
                self._set_chip_mark(letter, len(chips) - 1)
                return True
        if multi and chips and key == Qt.Key.Key_Backspace and empty:
            self._remove(letter, chips[-1].info.key)
            return True
        open_here = self.is_open(letter)
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            if open_here:
                self.list.step(1 if key == Qt.Key.Key_Down else -1)
                return True
            if key == Qt.Key.Key_Down:
                alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
                self.open(letter, by_user=empty, mark_first=not alt)
                return True
            return False
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not open_here:
                return False
            mark = self.list.marked()
            if mark is not None:
                self._take_key(letter, self.list.listing.entries[mark].key)
            return True
        if key == Qt.Key.Key_Escape:
            if open_here:
                self.close()
                return True
            return False
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.close()
        return False

    def _chip_key(self, letter: str, key, chips) -> bool:
        """Keys while a chip is marked: walk, take it off, or leave the chips."""
        index = self.chip_mark
        if key == Qt.Key.Key_Left:
            self._set_chip_mark(letter, max(index - 1, 0))
            return True
        if key == Qt.Key.Key_Right:
            self._set_chip_mark(letter, index + 1 if index + 1 < len(chips) else None)
            return True
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._set_chip_mark(letter, None)
            self._remove(letter, chips[index].info.key)
            field = self.field(letter)
            remaining = len(field.flow.chips) if field is not None else 0
            if remaining:
                self._set_chip_mark(letter, min(index, remaining - 1))
            return True
        if key == Qt.Key.Key_Escape:
            self._set_chip_mark(letter, None)
            return True
        return False
