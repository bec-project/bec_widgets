"""
The box on top of the Signals panel: one field per role of the plot (x axis, curves, y axis,
colour), each holding the signals that have the role as chips.

The box shows the state of :class:`~bec_widgets.widgets.services.hdf5_viewer.signal_list.SignalList`
and changes it through the list; the role buttons in the rows below show and change the same
state.
"""

from __future__ import annotations

from dataclasses import dataclass

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.theme_utils import theme_colors
from bec_widgets.widgets.progress.stage_bar import Tone
from bec_widgets.widgets.services.bec_queue.queue_ui import CountBadge
from bec_widgets.widgets.services.hdf5_viewer.style import mute, tone_color

SourceKey = tuple[str, str]

#: Height of a chip, and the space between two chips and two lines of chips.
CHIP_HEIGHT = 20
CHIP_GAP = 5
LINE_GAP = 4
#: Space inside a chip at its sides, and between its parts.
CHIP_PADDING = 7
CHIP_SPACING = 5
CHIP_RADIUS = 5
#: Length of the line drawn as the swatch of a curve.
SWATCH_WIDTH = 14
#: Size of the x that takes a chip off.
REMOVE_SIZE = 14
#: Corner radius of a field and of the box, and the space between a field's edge and its chips.
FIELD_RADIUS = 6
FIELD_PADDING = 4
#: Lines of chips a field shows; more scroll inside it.
MAX_CHIP_LINES = 3
#: Narrowest the text a field is typed into gets before it starts a line of its own.
EDIT_MIN_WIDTH = 64
#: Size of the letter badge of a role.
LETTER_SIZE = QSize(22, 20)
#: Opacity of the text colour over a chip's background and its border.
CHIP_FILL_ALPHA = 0.07
CHIP_BORDER_ALPHA = 0.18
#: Opacity of the text colour of the border of the box and of a field.
BORDER_ALPHA = 0.22
#: Pen styles the plot draws a signal with, by the names the Waveform uses.
PEN_STYLES = {
    "solid": Qt.PenStyle.SolidLine,
    "dash": Qt.PenStyle.DashLine,
    "dot": Qt.PenStyle.DotLine,
    "dashdot": Qt.PenStyle.DashDotLine,
}


@dataclass(frozen=True)
class Swatch:
    """How a signal is drawn on the plot: its colour and line style."""

    color: str
    style: str = "solid"


@dataclass(frozen=True)
class ChipInfo:
    """A signal that has a role, or the name of an axis that is no listed signal."""

    #: (device, entry) of the signal; None for an axis such as the sample number.
    key: SourceKey | None
    label: str
    #: Whether the list chose it, not the user.
    auto: bool = False
    #: Whether the chip has an x that takes it off.
    removable: bool = False
    #: The line of a curve; None for an axis.
    swatch: Swatch | None = None
    tip: str = ""
    #: Why a signal on the plot is not drawn: none of its reads came through. Empty when it
    #: is drawn.
    problem: str = ""
    #: A word said after the name in place of "auto", e.g. "selected"; empty for none.
    tag: str = ""

    @property
    def mark(self) -> str:
        """The small word after the name: the tag, else "auto" for a chip the list chose."""
        return self.tag or ("auto" if self.auto else "")


@dataclass(frozen=True)
class Role:
    """One role of the plot, as a row of the box."""

    #: ``X``, ``Y`` or ``Z``, as on the role buttons of the rows.
    letter: str
    #: Whether the role is an axis (a dark badge) rather than what is drawn (a blue one).
    axis: bool
    #: Whether the role holds several signals (the curves) or one.
    multi: bool
    #: Says the role at the right end of the field, e.g. "x axis"; may be empty.
    caption: str
    chips: tuple[ChipInfo, ...]
    #: What the field is called for assistive tools, e.g. "The curves on the plot, 2 curves".
    name: str
    #: What typing in the field does, e.g. "Type to add a signal".
    hint: str
    #: What a signal that takes the role becomes, e.g. "can be a curve", "can colour the map".
    can_be: str = ""
    placeholder: str = ""
    #: Set when the role does not apply to the plot shown, e.g. "Not used in Lines": the
    #: field says it in its empty text and takes no typing.
    inactive: str = ""


def paint_swatch(painter: QPainter, rect: QRectF, swatch: Swatch) -> None:
    """
    Draw the line of a curve across the middle of a rectangle, in its colour and style.

    Args:
        painter (QPainter): The painter.
        rect (QRectF): Where the line goes.
        swatch (Swatch): The colour and style.
    """
    painter.save()
    pen = QPen(QColor(swatch.color), 2)
    pen.setStyle(PEN_STYLES.get(swatch.style, Qt.PenStyle.SolidLine))
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    painter.setPen(pen)
    y = rect.center().y()
    painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
    painter.restore()


def _alpha(color: QColor, alpha: float) -> QColor:
    out = QColor(color)
    out.setAlphaF(alpha)
    return out


def _small_font(font: QFont) -> QFont:
    small = QFont(font)
    small.setPixelSize(11)
    return small


class RoleChip(QWidget):
    """A signal in a field: its swatch, its name cut in the middle when needed, "auto" and x."""

    #: The x was clicked: the signal should be taken off.
    remove_requested = Signal(object)

    def __init__(self, info: ChipInfo, parent: QWidget | None = None):
        super().__init__(parent)
        self.info = info
        self.marked = False
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.remove_button: QToolButton | None = None
        if info.removable:
            button = QToolButton(self)
            button.setObjectName("chip_remove")
            button.setAutoRaise(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setIcon(material_icon("close", size=(12, 12), convert_to_pixmap=False))
            button.setIconSize(QSize(12, 12))
            button.setFixedSize(REMOVE_SIZE, REMOVE_SIZE)
            text = f"Take {info.label} off the plot"
            button.setToolTip(text)
            button.setAccessibleName(text)
            button.setStyleSheet("QToolButton { border: none; padding: 0; }")
            button.clicked.connect(lambda: self.remove_requested.emit(info.key))
            self.remove_button = button
        if info.problem:
            self.setAccessibleName(f"{info.label}, not drawn. {info.problem}")
        else:
            self.setAccessibleName(info.label + (" (chosen automatically)" if info.auto else ""))
        self._update_tip()

    def _fixed_width(self) -> int:
        """Width of everything but the name: the parts that never give way."""
        width = 2 * CHIP_PADDING
        if self.info.swatch is not None:
            width += SWATCH_WIDTH + CHIP_SPACING
        if self.info.mark:
            mark = self.info.mark
            width += CHIP_SPACING + QFontMetrics(_small_font(self.font())).horizontalAdvance(mark)
        if self.remove_button is not None:
            width += CHIP_SPACING + REMOVE_SIZE
        return width

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        name = self.fontMetrics().horizontalAdvance(self.info.label)
        return QSize(self._fixed_width() + name + 1, CHIP_HEIGHT)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        return QSize(self._fixed_width() + self.fontMetrics().horizontalAdvance("a…z"), CHIP_HEIGHT)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        if self.remove_button is not None:
            self.remove_button.move(
                self.width() - CHIP_PADDING - REMOVE_SIZE + 2, (CHIP_HEIGHT - REMOVE_SIZE) // 2
            )
        self._update_tip()

    def _update_tip(self) -> None:
        """Say why the chip's curve is not drawn, and the whole name once it is cut."""
        tip = f"Not drawn: {self.info.problem}." if self.info.problem else self.info.tip
        if self.shown_name() != self.info.label:
            tip = f"{self.info.label}\n{tip}" if tip else self.info.label
        self.setToolTip(tip)

    def shown_name(self) -> str:
        """The name as it fits the chip: cut in the middle when the chip is too narrow."""
        room = self.width() - self._fixed_width()
        return self.fontMetrics().elidedText(self.info.label, Qt.TextElideMode.ElideMiddle, room)

    def set_marked(self, marked: bool) -> None:
        """Mark the chip as the one the keys act on."""
        if marked != self.marked:
            self.marked = marked
            self.update()

    def paintEvent(self, event):  # pylint: disable=invalid-name
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(_alpha(colors["fg"], CHIP_FILL_ALPHA))
        if self.marked:
            painter.setPen(QPen(colors["primary"], 2))
            body = body.adjusted(0.5, 0.5, -0.5, -0.5)
        else:
            painter.setPen(QPen(_alpha(colors["fg"], CHIP_BORDER_ALPHA), 1))
        painter.drawRoundedRect(body, CHIP_RADIUS, CHIP_RADIUS)
        x = CHIP_PADDING
        if self.info.problem:
            # Asked for but not drawn: the swatch as an outline in the colour of a problem,
            # as on the button of its row.
            painter.setPen(QPen(tone_color(Tone.BAD), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            mid = self.height() / 2
            painter.drawRoundedRect(QRectF(x + 0.75, mid - 4, SWATCH_WIDTH - 1.5, 8), 2, 2)
            x += SWATCH_WIDTH + CHIP_SPACING
        elif self.info.swatch is not None:
            paint_swatch(painter, QRectF(x, 0, SWATCH_WIDTH, self.height()), self.info.swatch)
            x += SWATCH_WIDTH + CHIP_SPACING
        name = self.shown_name()
        painter.setPen(colors["fg"])
        name_width = self.fontMetrics().horizontalAdvance(name)
        painter.drawText(
            QRect(x, 0, name_width + 1, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            name,
        )
        x += name_width + CHIP_SPACING
        if self.info.mark:
            painter.setFont(_small_font(self.font()))
            painter.setPen(colors["primary"])
            painter.drawText(
                QRect(x, 0, self.width() - x, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self.info.mark,
            )
        painter.end()


class LetterBadge(QWidget):
    """The letter of a role: dark for an axis, blue for what is drawn."""

    def __init__(self, letter: str, axis: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.letter = letter
        self.axis = axis
        self.setFixedSize(LETTER_SIZE)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        colors = theme_colors()
        fill = colors["fg"] if self.axis else colors["primary"]
        ink = colors["bg"] if self.axis else colors["on_primary"]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(self.rect()), CHIP_RADIUS, CHIP_RADIUS)
        font = QFont(self.font())
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(ink)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.letter)
        painter.end()


class _ChipFlow(QWidget):
    """The chips of a field and the text typed into it, wrapped into lines."""

    def __init__(self, field: RoleField):
        super().__init__()
        self._field = field
        self.chips: list[RoleChip] = []
        self.edit = QLineEdit(self)
        self.edit.setFrame(False)
        # The field draws the frame: the text has none of its own, at the height of a chip.
        self.edit.setStyleSheet(
            "QLineEdit { background: transparent; border: none; padding: 0; margin: 0;"
            " min-height: 0; }"
        )
        self.edit.setFixedHeight(CHIP_HEIGHT)
        self.content_height = CHIP_HEIGHT
        self.lines = 1
        #: The placeholder of the field; the text field shows it only where it fits whole.
        self.placeholder = ""

    def place(self, width: int) -> None:
        """Lay out the chips and the text field for a width; remember the height it takes."""
        x, y, line = 0, 0, 0
        for chip in self.chips:
            want = min(chip.sizeHint().width(), width)
            want = max(want, min(chip.minimumSizeHint().width(), width))
            if x > 0 and x + want > width:
                x, y, line = 0, y + CHIP_HEIGHT + LINE_GAP, line + 1
            chip.setGeometry(x, y, want, CHIP_HEIGHT)
            x += want + CHIP_GAP
        if x > 0 and width - x < EDIT_MIN_WIDTH:
            x, y, line = 0, y + CHIP_HEIGHT + LINE_GAP, line + 1
        self.edit.setGeometry(x, y, max(width - x, 0), CHIP_HEIGHT)
        self.lines = line + 1
        self.content_height = y + CHIP_HEIGHT
        self.fit_placeholder()

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        self.fit_placeholder()

    def placeholder_need(self) -> int:
        """The width the text field needs to show the whole placeholder, measured in its font."""
        if not self.placeholder:
            return 0
        margins = self.edit.textMargins()
        # QLineEdit keeps 2 px between its text and each side of its contents.
        beside = margins.left() + margins.right() + 2 * 2 + 1
        return beside + self.edit.fontMetrics().horizontalAdvance(self.placeholder)

    def fit_placeholder(self) -> None:
        """
        Show the placeholder whole or not at all: a cut placeholder says nothing. A field not
        on screen has no width yet and keeps it; it is fitted when it is shown.
        """
        fits = not self.isVisible() or self.edit.width() >= self.placeholder_need()
        shown = self.placeholder if fits else ""
        if self.edit.placeholderText() != shown:
            self.edit.setPlaceholderText(shown)


class RoleField(QFrame):
    """
    A field of the box: the chips of the signals that have a role, a text to type a signal
    into, the caption of the role and an arrow that opens the full list.
    """

    #: The x of a chip was clicked: (letter, key).
    remove_requested = Signal(str, object)
    #: The field's arrow was clicked.
    arrow_clicked = Signal(str)

    def __init__(self, role: Role, parent: QWidget | None = None):
        super().__init__(parent)
        self.role = role
        self.setObjectName(f"role_field_{role.letter.lower()}")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._scroll = QScrollArea(self)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # The count badge under the letter says that there is more; a bar would take width
        # from the chips and make them wrap anew.
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(False)
        self._scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.flow = _ChipFlow(self)
        self.flow.setAutoFillBackground(False)
        self._scroll.setWidget(self.flow)
        self._scroll.viewport().installEventFilter(self)
        self.edit = self.flow.edit
        self.caption = QLabel(self)
        self.caption.setObjectName("role_caption")
        self.caption.setFixedHeight(CHIP_HEIGHT)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        mute(self.caption)
        self.arrow = QToolButton(self)
        self.arrow.setObjectName("role_arrow")
        self.arrow.setAutoRaise(True)
        self.arrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.arrow.setIcon(material_icon("expand_more", size=(16, 16), convert_to_pixmap=False))
        self.arrow.setIconSize(QSize(16, 16))
        self.arrow.setFixedSize(QSize(18, CHIP_HEIGHT))
        self.arrow.setStyleSheet("QToolButton { border: none; padding: 0; }")
        self.arrow.clicked.connect(lambda: self.arrow_clicked.emit(self.role.letter))
        row = QHBoxLayout(self)
        row.setContentsMargins(FIELD_PADDING + 1, FIELD_PADDING, 2, FIELD_PADDING)
        row.setSpacing(4)
        row.addWidget(self._scroll, 1, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.caption, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.arrow, 0, Qt.AlignmentFlag.AlignTop)
        self._caption_width = 0
        font = QFont(self.font())
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        self.caption.setFont(font)
        self._shown: Role | None = None
        self.set_role(role)

    def set_role(self, role: Role) -> None:
        """Show the signals that have the role now. A role shown already changes nothing."""
        if role == self._shown:
            return
        self._shown = role
        old = [chip.info for chip in self.flow.chips]
        self.role = role
        if self.caption.text() != role.caption:
            self.caption.setText(role.caption)
            self._caption_width = QFontMetrics(self.caption.font()).horizontalAdvance(role.caption)
            self._fit_caption()
        self.flow.placeholder = role.inactive or role.placeholder
        self.flow.fit_placeholder()
        self.edit.setEnabled(not role.inactive)
        self.arrow.setEnabled(not role.inactive)
        if role.inactive:
            self.edit.clear()
        self.arrow.setToolTip(f"Show every signal that {role.can_be}")
        self.arrow.setAccessibleName(self.arrow.toolTip())
        if old != list(role.chips):
            added = [info for info in role.chips if info not in old]
            for chip in self.flow.chips:
                chip.hide()
                chip.deleteLater()
            self.flow.chips = []
            for info in role.chips:
                chip = RoleChip(info, self.flow)
                chip.remove_requested.connect(
                    lambda key, letter=role.letter: self.remove_requested.emit(letter, key)
                )
                chip.show()
                self.flow.chips.append(chip)
            self._relayout()
            if added:
                # Show where the change is: the chip that was just added.
                chip = self.flow.chips[[c.info for c in self.flow.chips].index(added[-1])]
                self._scroll.ensureWidgetVisible(chip, 0, 0)
        self.update_names()

    def update_names(self) -> None:
        """Name the field for assistive tools: the role, what it holds and how to change it."""
        # What typing does, or why the field takes none.
        more = self.role.hint or self.role.inactive
        hint = f". {more}" if more else ""
        self.edit.setAccessibleName(f"{self.role.name}{hint}")
        self.edit.setToolTip(self.role.hint or self.role.inactive)

    def set_top(self) -> None:
        """Scroll the field to its first line, e.g. for a newly chosen scan."""
        self._scroll.verticalScrollBar().setValue(0)

    def lines(self) -> int:
        """Lines of chips and text the field holds, also those scrolled out of view."""
        return self.flow.lines

    def chip_of(self, key: SourceKey) -> RoleChip | None:
        """The chip of a signal, if it has the role."""
        return next((chip for chip in self.flow.chips if chip.info.key == key), None)

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if watched is self._scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._relayout()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._fit_caption()

    def _fit_caption(self) -> None:
        """Hide the caption as a whole where it would squeeze the chips."""
        if not self.role.caption:
            self.caption.hide()
            return
        room = self.width() - 2 * FIELD_PADDING - self.arrow.width() - 8
        need = max((chip.sizeHint().width() for chip in self.flow.chips), default=0)
        # A field of one signal keeps its chip and the text on one line; the curves wrap.
        typing = EDIT_MIN_WIDTH // 2 if self.role.multi else EDIT_MIN_WIDTH + CHIP_GAP
        need += typing + self._caption_width + 4
        self.caption.setVisible(room >= need)

    def _relayout(self) -> None:
        width = self._scroll.viewport().width()
        self.flow.setFixedWidth(width)
        self.flow.place(width)
        self.flow.setFixedHeight(self.flow.content_height)
        cap = MAX_CHIP_LINES * CHIP_HEIGHT + (MAX_CHIP_LINES - 1) * LINE_GAP
        height = min(self.flow.content_height, cap)
        if self._scroll.height() != height:
            self._scroll.setFixedHeight(height)
        self._fit_caption()

    def scroll_to_text(self) -> None:
        """Bring the text being typed into view."""
        self._scroll.ensureWidgetVisible(self.edit, 0, 0)

    def ensure_visible(self, chip: RoleChip) -> None:
        """Bring a chip into view, e.g. the one marked with the arrow keys."""
        self._scroll.ensureWidgetVisible(chip, 0, 0)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        focused = self.edit.hasFocus()
        painter.setPen(
            QPen(colors["primary"], 1.5) if focused else QPen(_alpha(colors["fg"], BORDER_ALPHA))
        )
        painter.setBrush(colors["field"])
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75), FIELD_RADIUS, FIELD_RADIUS
        )
        painter.end()


#: The reset of the box, the same in the Signals and the File tab.
RESET_TEXT = "Reset"
RESET_TIP = "Plot the scan's default curve against its axes again; other curves go off"


class RoleBox(QFrame):
    """The box on top of the Signals panel: one row per role, and Reset."""

    #: The x of a chip was clicked: (letter, key).
    remove_requested = Signal(str, object)
    #: The arrow of a field was clicked: letter.
    arrow_clicked = Signal(str)
    #: Reset was clicked.
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("role_box")
        self.fields: dict[str, RoleField] = {}
        self._letters: dict[str, LetterBadge] = {}
        #: The rows made so far by letter: holder of the letter, the letter, the field.
        self._made: dict[str, tuple[QWidget, LetterBadge, RoleField]] = {}
        self.count_badge = CountBadge(self)
        self.count_badge.setObjectName("curve_count")
        self.count_badge.hide()
        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(6)
        self._grid.setVerticalSpacing(5)
        self._grid.setColumnStretch(1, 1)
        self.reset_button = QToolButton(self)
        self.reset_button.setObjectName("reset_axes_button")
        self.reset_button.setText(RESET_TEXT)
        self.reset_button.setAutoRaise(True)
        self.reset_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.reset_button.setToolTip(RESET_TIP)
        self.reset_button.clicked.connect(self.reset_requested)
        self.reset_button.hide()
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addStretch(1)
        reset_row.addWidget(self.reset_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        layout.addLayout(self._grid)
        layout.addLayout(reset_row)
        # Content stays at the top while the box keeps a height it no longer needs.
        layout.addStretch(1)

    def set_roles(self, roles: list[Role], show_reset: bool) -> None:
        """
        Show the roles of the plot.

        Args:
            roles (list[Role]): The rows, top to bottom.
            show_reset (bool): Whether the plot differs from the scan's default, so Reset
                shows.
        """
        letters = [role.letter for role in roles]
        if letters != list(self.fields):
            self._build(roles)
        for role in roles:
            self.fields[role.letter].set_role(role)
            letter = self._letters[role.letter]
            if letter.axis != role.axis:
                letter.axis = role.axis
                letter.update()
        self.reset_button.setVisible(show_reset)
        self.update_count()
        self.setVisible(bool(roles))

    def _build(self, roles: list[Role]) -> None:
        """
        Show one row per role: the letter (with the curve count under it) and the field. The
        rows of a letter are made once and kept, so that a change between scans with other
        letters moves rows instead of making new ones.
        """
        column = (
            self.count_badge.parentWidget().layout() if self.count_badge.parentWidget() else None
        )
        if column is not None:
            column.removeWidget(self.count_badge)
        self.count_badge.setParent(self)
        self.count_badge.hide()
        while self._grid.count():
            self._grid.takeAt(0)
        for holder, _badge, field in self._made.values():
            holder.hide()
            field.hide()
            field.edit.clear()
        self.fields, self._letters = {}, {}
        for row, role in enumerate(roles):
            if role.letter not in self._made:
                self._made[role.letter] = self._make_row(role)
            holder, badge, field = self._made[role.letter]
            if role.multi:
                holder.layout().insertWidget(1, self.count_badge, 0, Qt.AlignmentFlag.AlignHCenter)
            self._grid.addWidget(holder, row, 0)
            self._grid.addWidget(field, row, 1, Qt.AlignmentFlag.AlignTop)
            holder.show()
            field.show()
            self.fields[role.letter] = field
            self._letters[role.letter] = badge

    def _make_row(self, role: Role) -> tuple[QWidget, LetterBadge, RoleField]:
        """The letter of a role, level with the first line of chips, and its field."""
        holder = QWidget(self)
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, FIELD_PADDING, 0, 0)
        column.setSpacing(4)
        badge = LetterBadge(role.letter, role.axis, holder)
        column.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addStretch(1)
        field = RoleField(role, self)
        field.remove_requested.connect(self.remove_requested)
        field.arrow_clicked.connect(self.arrow_clicked)
        field.flow.installEventFilter(self)
        return holder, badge, field

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if event.type() == QEvent.Type.Resize:
            self.update_count()
        return super().eventFilter(watched, event)

    def update_count(self) -> None:
        """Show the number of curves under the letter once not all chips are in view."""
        field = next((f for f in self.fields.values() if f.role.multi), None)
        if field is None:
            self.count_badge.hide()
            return
        count = len(field.role.chips)
        self.count_badge.setText(str(count))
        self.count_badge.setToolTip(f"{count} curve{'' if count == 1 else 's'} on the plot")
        self.count_badge.setVisible(field.lines() > MAX_CHIP_LINES)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(_alpha(colors["fg"], BORDER_ALPHA)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), FIELD_RADIUS, FIELD_RADIUS
        )
        painter.end()
