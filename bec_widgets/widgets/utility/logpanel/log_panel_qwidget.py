"""Reworked BEC log panel drawn with QWidgets.

Same UX as :mod:`log_panel_qml`; all state and actions live in
:class:`~.log_ux_common.LogPanelBackend`. The rows are painted by one delegate in a single
column ``QTreeView``, which computes row heights lazily, so expanded tracebacks stay cheap even
with tens of thousands of entries.
"""

from __future__ import annotations

from functools import partial

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QModelIndex, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from qtpy.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QShortcut,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import IconButton, StatusPill, field_qss
from bec_widgets.widgets.utility.logpanel.log_ux_common import LogEntry, LogPanelBackend

# geometry shared with qml/LogPanelView.qml
ROW_H = 26
LINE_H = 18
X_TIME = 12
X_BADGE = 112
X_SERVICE = 166
X_CHEVRON = 294
X_MESSAGE = 312
SERVICE_W = 120


def _mono(pixel_size: int = 12) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPixelSize(pixel_size)
    return font


def _ui(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(QApplication.font())
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


class LogRowDelegate(QStyledItemDelegate):
    """Paints one log row: level stripe, time, level badge, service, message and extras."""

    # pylint: disable=invalid-name,missing-function-docstring,unused-argument

    def __init__(self, view: LogTreeView, backend: LogPanelBackend):
        super().__init__(view)
        self._view = view
        self._backend = backend
        self.mono = _mono(12)
        self.mono_bold = _mono(12)
        self.mono_bold.setBold(True)
        self.badge_font = _ui(10, QFont.Weight.Bold)
        self.service_font = _ui(12)
        self.small_font = _ui(11, QFont.Weight.DemiBold)
        self._mono_metrics = QFontMetrics(self.mono)
        self._icons: dict[tuple[str, str], object] = {}
        self.tokens = ThemeTokens()

    def refresh_theme(self) -> None:
        """Drop cached colours and icons."""
        self.tokens = ThemeTokens()
        self._icons.clear()

    def _icon(self, name: str, color: QColor):
        key = (name, color.name())
        icon = self._icons.get(key)
        if icon is None:
            icon = self._icons[key] = material_icon(
                name, size=(32, 32), color=color, convert_to_pixmap=False
            )
        return icon

    # pylint: disable=invalid-name
    def sizeHint(self, option, index: QModelIndex) -> QSize:
        entry = self._backend.model.entry(index.row())
        if entry is None or entry.seq not in self._backend.model.expanded:
            return QSize(option.rect.width(), ROW_H)
        return QSize(option.rect.width(), ROW_H + len(entry.body_lines()) * LINE_H + 20)

    @staticmethod
    def chevron_rect(rect: QRect) -> QRect:
        """Clickable expand area of a row."""
        return QRect(rect.left() + X_CHEVRON - 4, rect.top(), 22, ROW_H)

    @staticmethod
    def copy_rect(rect: QRect) -> QRect:
        """Clickable copy button of a hovered row."""
        return QRect(rect.right() - 30, rect.top() + 2, 24, ROW_H - 4)

    def editorEvent(self, event, model, option, index) -> bool:
        if (
            event.type() != QEvent.Type.MouseButtonRelease
            or event.button() != Qt.MouseButton.LeftButton
        ):
            return False
        pos = event.position().toPoint()
        entry = self._backend.model.entry(index.row())
        if entry is None:
            return False
        if self.copy_rect(option.rect).contains(pos):
            self._backend.copyRow(index.row())
            return True
        if entry.line_count > 1 and self.chevron_rect(option.rect).contains(pos):
            self._view.toggle_row(index.row())
            return True
        return False

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        # pylint: disable=too-many-locals,too-many-statements
        model = self._backend.model
        entry: LogEntry | None = model.entry(index.row())
        if entry is None:
            return
        tokens = self.tokens
        rect = option.rect
        header = QRect(rect.left(), rect.top(), rect.width(), ROW_H)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        current = entry.seq == model.current_seq
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # background: error tint, then hover / selection
        tint = model.row_tint(entry.level)
        if tint is not None:
            painter.fillRect(rect, tint)
        if selected or current:
            fill = QColor(tokens.primary)
            fill.setAlphaF(0.20 if selected else 0.12)
            painter.fillRect(rect, fill)
        elif hovered:
            painter.fillRect(rect, tokens.hover)

        level_color = model.level_color(entry.level)
        # level stripe
        painter.fillRect(QRect(rect.left(), rect.top() + 3, 3, rect.height() - 6), level_color)

        # time
        painter.setFont(self.mono)
        painter.setPen(tokens.fg_subtle)
        painter.drawText(
            QRect(rect.left() + X_TIME, header.top(), X_BADGE - X_TIME - 6, ROW_H),
            Qt.AlignmentFlag.AlignVCenter,
            model.time_text(entry),
        )

        # level badge
        badge = QRectF(rect.left() + X_BADGE, header.top() + 4, 46, ROW_H - 8)
        badge_fill = QColor(level_color)
        badge_fill.setAlphaF(0.18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_fill)
        painter.drawRoundedRect(badge, 4, 4)
        painter.setFont(self.badge_font)
        painter.setPen(model.level_ink(entry.level))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, entry.badge)

        # service
        service_color = model.service_color(entry.service)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(service_color)
        painter.drawEllipse(
            QPointF(rect.left() + X_SERVICE + 4, header.center().y() + 0.5), 3.5, 3.5
        )
        painter.setFont(self.service_font)
        painter.setPen(tokens.fg_muted)
        service_rect = QRect(rect.left() + X_SERVICE + 13, header.top(), SERVICE_W - 13, ROW_H)
        painter.drawText(
            service_rect,
            Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(
                entry.service, Qt.TextElideMode.ElideRight, service_rect.width()
            ),
        )

        # chevron for multi-line entries
        expanded = entry.seq in model.expanded
        if entry.line_count > 1:
            self._icon("expand_more" if expanded else "chevron_right", tokens.fg_muted).paint(
                painter, QRect(rect.left() + X_CHEVRON, header.top() + 5, 16, 16)
            )

        # right side extras: repeat counter, line count, hover copy button
        right = rect.right() - 8
        if hovered:
            self._icon("content_copy", tokens.fg_muted).paint(
                painter, self.copy_rect(rect).adjusted(4, 3, -4, -3)
            )
            right = self.copy_rect(rect).left() - 4
        painter.setFont(self.small_font)
        metrics = painter.fontMetrics()
        if entry.count > 1:
            text = f"×{entry.count}"
            width = metrics.horizontalAdvance(text) + 12
            pill = QRectF(right - width, header.top() + 5, width, ROW_H - 10)
            fill = QColor(level_color)
            fill.setAlphaF(0.18)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
            painter.setPen(model.level_ink(entry.level))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
            right = int(pill.left()) - 6
        if entry.line_count > 1 and not expanded:
            text = f"+{entry.line_count - 1} lines"
            width = metrics.horizontalAdvance(text) + 12
            pill = QRectF(right - width, header.top() + 5, width, ROW_H - 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.track)
            painter.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
            painter.setPen(tokens.fg_muted)
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
            right = int(pill.left()) - 6

        # message summary with search highlights
        message_rect = QRect(
            rect.left() + X_MESSAGE, header.top(), max(0, right - rect.left() - X_MESSAGE), ROW_H
        )
        color = tokens.fg_muted if entry.group == "debug" else tokens.fg
        self._draw_text(painter, message_rect, entry.summary, color, self.mono)

        if expanded:
            self._paint_body(painter, rect, entry)
        painter.restore()

    def _draw_text(self, painter: QPainter, rect: QRect, text: str, color: QColor, font: QFont):
        painter.setFont(font)
        metrics = painter.fontMetrics()
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        spans = self._backend.model.matcher.spans(elided)
        if spans:
            mark = QColor(self.tokens.warning)
            mark.setAlphaF(0.45 if self.tokens.dark else 0.55)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(mark)
            for start, length in spans:
                x = rect.left() + metrics.horizontalAdvance(elided[:start])
                width = metrics.horizontalAdvance(elided[start : start + length])
                painter.drawRoundedRect(QRectF(x - 1, rect.center().y() - 8, width + 2, 17), 3, 3)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, elided)

    def _paint_body(self, painter: QPainter, rect: QRect, entry: LogEntry) -> None:
        tokens = self.tokens
        block = QRectF(
            rect.left() + X_CHEVRON,
            rect.top() + ROW_H,
            rect.width() - X_CHEVRON - 12,
            rect.height() - ROW_H - 6,
        )
        painter.setPen(tokens.border)
        painter.setBrush(tokens.field)
        painter.drawRoundedRect(block, 6, 6)
        y = int(block.top()) + 7
        width = int(block.width()) - 20
        exception_color = self._backend.model.level_ink("ERROR")
        for text, kind in entry.body_lines():
            line_rect = QRect(int(block.left()) + 10, y, width, LINE_H)
            if kind == "exception":
                self._draw_text(painter, line_rect, text, exception_color, self.mono_bold)
            elif kind in ("file", "head"):
                self._draw_text(painter, line_rect, text, tokens.fg_subtle, self.mono)
            else:
                self._draw_text(painter, line_rect, text, tokens.fg, self.mono)
            y += LINE_H


class LogTreeView(QTreeView):
    """Single column view of the log rows that tells the backend when the user leaves the tail."""

    # pylint: disable=invalid-name,missing-function-docstring

    def __init__(self, backend: LogPanelBackend, parent: QWidget | None = None):
        super().__init__(parent)
        self._backend = backend
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setUniformRowHeights(True)
        self.setItemsExpandable(False)
        self.setAllColumnsShowFocus(True)
        self.setMouseTracking(True)
        self.setFrameShape(QTreeView.Shape.NoFrame)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setModel(backend.model)
        self.delegate = LogRowDelegate(self, backend)
        self.setItemDelegate(self.delegate)
        self._scroll_pending = False
        self._expanded_role = backend.model.roleNames_ids()["expanded"]
        self.verticalScrollBar().actionTriggered.connect(self._on_user_scroll)
        self.verticalScrollBar().valueChanged.connect(self._on_value_changed)

    def toggle_row(self, row: int) -> None:
        """Expand or collapse a multi-line row."""
        self._backend.toggleExpanded(row)

    def sync_row_heights(self) -> None:
        """Use uniform row heights while nothing is expanded.

        With uniform heights the view lays out tens of thousands of rows without asking the
        delegate for every row's size, which keeps live updates cheap. Only while an entry is
        expanded does it measure each row.
        """
        uniform = not self._backend.model.expanded
        if self.uniformRowHeights() != uniform:
            self.setUniformRowHeights(uniform)

    def schedule_scroll_to_end(self) -> None:
        """Scroll to the newest row once the current model update has been laid out."""
        if self._scroll_pending:
            return
        self._scroll_pending = True
        QTimer.singleShot(0, self._scroll_to_end)

    def _scroll_to_end(self) -> None:
        self._scroll_pending = False
        if self._backend.follow:
            self.scrollToBottom()

    def at_bottom(self) -> bool:
        """Whether the newest row is visible."""
        scrollbar = self.verticalScrollBar()
        return scrollbar.value() >= scrollbar.maximum()

    def _on_user_scroll(self, *_):
        QTimer.singleShot(0, lambda: self._backend.setFollow(self.at_bottom()))

    def _on_value_changed(self, _value: int) -> None:
        if self.at_bottom() and not self._backend.follow:
            self._backend.setFollow(True)

    # pylint: disable=invalid-name
    def wheelEvent(self, event) -> None:
        super().wheelEvent(event)
        self._backend.setFollow(self.at_bottom())

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Right, Qt.Key.Key_Left):
            index = self.currentIndex()
            if index.isValid():
                self.toggle_row(index.row())
                return
        super().keyPressEvent(event)
        self._backend.setFollow(self.at_bottom())

    def mouseDoubleClickEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            self.toggle_row(index.row())
            return
        super().mouseDoubleClickEvent(event)

    def dataChanged(self, top_left: QModelIndex, bottom_right: QModelIndex, roles=()) -> None:
        super().dataChanged(top_left, bottom_right, roles)
        if self._expanded_role in (roles or ()):
            # an entry was expanded or collapsed, possibly from the backend or a test
            self.sync_row_heights()
            self.delegate.sizeHintChanged.emit(top_left)

    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        super().currentChanged(current, previous)
        self._backend.setCurrent(current.row() if current.isValid() else -1)


class Chip(QPushButton):
    """Level filter chip with a coloured dot and a count, matching the QML chip.

    Signals:
        double_clicked(): Show only this level.
    """

    double_clicked = Signal()

    def __init__(self, key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self._color = QColor("gray")
        self._label = ""
        self._count = 0

    def set_data(self, label: str, count: int, active: bool, color: QColor) -> None:
        """Update the chip from the backend state."""
        self._label, self._count, self._color = label, count, QColor(color)
        self.setChecked(active)
        text = f"{label}  {count:,}"
        self.setMinimumWidth(
            QFontMetrics(_ui(12, QFont.Weight.DemiBold)).horizontalAdvance(text) + 34
        )
        self.setToolTip(f"Show or hide {label.lower()} (double-click to show only {label.lower()})")
        self.update()

    def mouseDoubleClickEvent(self, _event):  # pylint: disable=invalid-name
        """Double-click shows only this level."""
        self.double_clicked.emit()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Paint the chip."""
        tokens = ThemeTokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        active = self.isChecked()
        if active:
            fill = QColor(self._color)
            fill.setAlphaF(0.16)
            painter.setBrush(fill)
            painter.setPen(QColor(self._color))
        else:
            painter.setBrush(tokens.hover if self.underMouse() else Qt.GlobalColor.transparent)
            painter.setPen(tokens.border)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color if active else tokens.fg_subtle)
        painter.drawEllipse(QPointF(14, rect.center().y()), 4, 4)
        font = _ui(12, QFont.Weight.DemiBold if active else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(tokens.fg if active else tokens.fg_subtle)
        label_rect = rect.adjusted(24, 0, -10, 0)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter, self._label)
        painter.setPen(tokens.fg_muted if active else tokens.fg_subtle)
        painter.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            f"{self._count:,}",
        )
        painter.end()


class LivePill(StatusPill):
    """Live / Paused status pill that toggles pausing when clicked.

    Signals:
        clicked(): The pill was clicked.
    """

    clicked = Signal()

    def mousePressEvent(self, _event):  # pylint: disable=invalid-name
        """Report the click."""
        self.clicked.emit()


class SelectButton(QToolButton):
    """Field styled button that opens a menu, matching ``BecUi.SelectField``."""

    def __init__(self, icon_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._icon_name = icon_name
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def refresh_theme(self, tokens: ThemeTokens, highlighted: bool = False) -> None:
        """Apply the theme tokens; ``highlighted`` marks an active filter."""
        color = tokens.primary if highlighted else tokens.fg_muted
        self.setIcon(
            material_icon(self._icon_name, size=(32, 32), color=color, convert_to_pixmap=False)
        )
        self.setIconSize(QSize(15, 15))
        border = tokens.primary.name() if highlighted else tokens.border.name()
        self.setStyleSheet(
            f"QToolButton {{ background: {tokens.field.name()}; color: {tokens.fg.name()};"
            f" border: 1px solid {border}; border-radius: 13px; padding: 0 12px 0 8px;"
            f" font-size: 12px; }}"
            f"QToolButton:hover {{ border-color: {tokens.fg_subtle.name()}; }}"
            f"QToolButton::menu-indicator {{ image: none; width: 0; }}"
        )


class _StayOpenMenu(QMenu):  # pylint: disable=too-few-public-methods
    """Menu whose checkable entries toggle without closing it."""

    def mouseReleaseEvent(self, event):  # pylint: disable=invalid-name
        """Toggle checkable entries in place."""
        action = self.actionAt(event.position().toPoint())
        if action is not None and action.isCheckable():
            action.trigger()
            return
        super().mouseReleaseEvent(event)


class LogPanelQWidget(BECWidget, QWidget):
    """Live BEC log viewer with level chips, search with highlight, follow-tail and folding.

    Args:
        parent: Parent widget.
        backend(LogPanelBackend | None): Use an existing backend (tests, demos). By default the
            panel creates one fed by the live BEC log stream.
    """

    PLUGIN = False
    RPC = False
    ICON_NAME = "browse_activity"

    def __init__(
        self, parent: QWidget | None = None, backend: LogPanelBackend | None = None, **kwargs
    ):
        super().__init__(parent=parent, **kwargs)
        self.backend = backend or LogPanelBackend(self)
        self._chips: dict[str, Chip] = {}
        self._build()
        self.backend.changed.connect(self._render)
        self.backend.scroll_to_end.connect(self.view.schedule_scroll_to_end)
        self.backend.reveal_row.connect(self._reveal_row)
        self.backend.toast.connect(self._show_toast)
        self.backend.focus_search.connect(self._focus_search)
        self.backend.model.modelReset.connect(self._after_reset)
        self.backend.model.rowsInserted.connect(self._update_overlays)
        self.backend.model.modelReset.connect(self._update_overlays)
        self._setup_shortcuts()
        self.apply_theme("")
        self._render()
        self.view.schedule_scroll_to_end()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        # pylint: disable=too-many-statements
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("logToolbar")
        rows = QVBoxLayout(self.toolbar)
        rows.setContentsMargins(10, 8, 10, 8)
        rows.setSpacing(8)

        # row 1: search and actions
        top = QHBoxLayout()
        top.setSpacing(6)
        self.search = QLineEdit(self.toolbar)
        self.search.setPlaceholderText("Search logs  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(440)
        self.search.setMinimumWidth(160)
        self._search_icon = self.search.addAction(
            material_icon("search", size=(32, 32), convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search.textEdited.connect(self.backend.setSearch)
        self.search.returnPressed.connect(self._on_return)
        top.addWidget(self.search, 1)

        self.mode_buttons: dict[str, QPushButton] = {}
        mode_box = QWidget(self.toolbar)
        mode_box.setObjectName("modeBox")
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.setSpacing(0)
        group = QButtonGroup(mode_box)
        for key, label, tip in (
            ("filter", "Filter", "Show only matching entries"),
            ("highlight", "Highlight", "Show everything and mark the matches"),
        ):
            button = QPushButton(label, mode_box)
            button.setCheckable(True)
            button.setToolTip(tip)
            button.setFixedHeight(26)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(partial(self.backend.setSearchMode, key))
            group.addButton(button)
            mode_layout.addWidget(button)
            self.mode_buttons[key] = button
        self.mode_box = mode_box
        top.addWidget(mode_box)

        self.regex_button = IconButton("regular_expression", "Regular expression", self.toolbar)
        self.regex_button.setCheckable(True)
        self.regex_button.toggled.connect(self.backend.setRegex)
        top.addWidget(self.regex_button)

        self.match_label = QLabel(self.toolbar)
        top.addWidget(self.match_label)
        self.prev_button = IconButton(
            "keyboard_arrow_up", "Previous match (Shift+Enter)", self.toolbar
        )
        self.prev_button.clicked.connect(self.backend.prevMatch)
        self.next_button = IconButton("keyboard_arrow_down", "Next match (Enter)", self.toolbar)
        self.next_button.clicked.connect(self.backend.nextMatch)
        top.addWidget(self.prev_button)
        top.addWidget(self.next_button)
        top.addStretch(1)

        self.live_pill = LivePill(self.toolbar)
        self.live_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.live_pill.clicked.connect(self.backend.togglePause)
        top.addWidget(self.live_pill)
        self.time_button = IconButton("schedule", "Show relative times", self.toolbar)
        self.time_button.clicked.connect(self.backend.toggleTimeMode)
        self.copy_button = IconButton("content_copy", "Copy visible entries", self.toolbar)
        self.copy_button.clicked.connect(self.backend.copyVisible)
        self.export_button = IconButton(
            "download", "Export visible entries to a file", self.toolbar
        )
        self.export_button.clicked.connect(self.backend.exportVisible)
        self.clear_button = IconButton("delete_sweep", "Clear the panel", self.toolbar)
        self.clear_button.clicked.connect(self.backend.clear)
        for button in (self.time_button, self.copy_button, self.export_button, self.clear_button):
            top.addWidget(button)
        rows.addLayout(top)

        # row 2: level chips, service and time filters, summary
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for group_state in self.backend.state["groups"]:
            chip = Chip(group_state["key"], self.toolbar)
            chip.clicked.connect(partial(self._on_chip_clicked, chip))
            chip.double_clicked.connect(partial(self.backend.soloGroup, chip.key))
            chips.addWidget(chip)
            self._chips[chip.key] = chip
        chips.addSpacing(6)
        self.service_button = SelectButton("dns", self.toolbar)
        self.service_menu = _StayOpenMenu(self.service_button)
        self.service_menu.aboutToShow.connect(self._fill_service_menu)
        self.service_button.setMenu(self.service_menu)
        chips.addWidget(self.service_button)
        self.since_button = SelectButton("schedule", self.toolbar)
        self.since_menu = QMenu(self.since_button)
        for option in self.backend.state["sinceOptions"]:
            self.since_menu.addAction(
                option["label"], partial(self.backend.setSince, option["key"])
            )
        self.since_button.setMenu(self.since_menu)
        chips.addWidget(self.since_button)
        chips.addStretch(1)
        self.summary_label = QLabel(self.toolbar)
        chips.addWidget(self.summary_label)
        self.reset_button = QPushButton("Reset filters", self.toolbar)
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setFlat(True)
        self.reset_button.clicked.connect(self._reset_filters)
        chips.addWidget(self.reset_button)
        rows.addLayout(chips)
        layout.addWidget(self.toolbar)

        self.view = LogTreeView(self.backend, self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.view, 1)

        # overlays
        self.jump_button = QPushButton(self.view.viewport())
        self.jump_button.setFixedHeight(30)
        self.jump_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.jump_button.clicked.connect(self.backend.jumpToLatest)
        self.jump_button.hide()
        self.empty = QWidget(self.view.viewport())
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_icon = QLabel(self.empty)
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title = QLabel(self.empty)
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint = QLabel(self.empty)
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_reset = QPushButton("Reset filters", self.empty)
        self.empty_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.empty_reset.clicked.connect(self._reset_filters)
        for widget in (self.empty_icon, self.empty_title, self.empty_hint):
            empty_layout.addWidget(widget)
        empty_layout.addWidget(self.empty_reset, 0, Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        self.toast_label = QLabel(self.view.viewport())
        self.toast_label.hide()
        self._toast_timer = QTimer(self, singleShot=True, interval=1600)
        self._toast_timer.timeout.connect(self.toast_label.hide)

    def _setup_shortcuts(self) -> None:
        find = QShortcut(QKeySequence.StandardKey.Find, self)
        find.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        find.activated.connect(self.backend.focus_search)
        for keys, slot in (
            (QKeySequence.StandardKey.FindNext, self.backend.nextMatch),
            (QKeySequence.StandardKey.FindPrevious, self.backend.prevMatch),
            (QKeySequence.StandardKey.Copy, self._copy_selection),
            (QKeySequence(Qt.Key.Key_End), self.backend.jumpToLatest),
        ):
            shortcut = QShortcut(keys, self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)
        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.search)
        escape.setContext(Qt.ShortcutContext.WidgetShortcut)
        escape.activated.connect(self._clear_search)

    # ------------------------------------------------------------------ actions
    @SafeSlot()
    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    @SafeSlot()
    def _clear_search(self) -> None:
        self.search.clear()
        self.backend.setSearch("")
        self.view.setFocus()

    @SafeSlot()
    def _on_return(self) -> None:
        modifiers = QApplication.keyboardModifiers()
        if self.backend.state["searchMode"] == "highlight":
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.backend.prevMatch()
            else:
                self.backend.nextMatch()

    def _on_chip_clicked(self, chip: Chip) -> None:
        self.backend.toggleGroup(chip.key)

    @SafeSlot()
    def _reset_filters(self) -> None:
        self.search.clear()
        self.backend.resetFilters()

    @SafeSlot()
    def _copy_selection(self) -> None:
        rows = [index.row() for index in self.view.selectionModel().selectedRows()]
        if not rows and self.view.currentIndex().isValid():
            rows = [self.view.currentIndex().row()]
        self.backend.copy_rows(rows)

    def _fill_service_menu(self) -> None:
        menu = self.service_menu
        menu.clear()
        menu.addAction("Show all services", self.backend.allServices)
        menu.addSeparator()
        for service in self.backend.state["services"]:
            action = QAction(f"{service['name']}    {service['count']:,}", menu)
            action.setCheckable(True)
            action.setChecked(service["active"])
            action.setIcon(self._dot_icon(service["color"]))
            action.triggered.connect(partial(self._toggle_service, service["name"]))
            menu.addAction(action)
        if not self.backend.state["services"]:
            empty = menu.addAction("No services yet")
            empty.setEnabled(False)

    def _toggle_service(self, name: str, *_):
        self.backend.toggleService(name)
        # keep the open menu in sync with the new selection
        active = {s["name"]: s["active"] for s in self.backend.state["services"]}
        for action in self.service_menu.actions():
            if action.isCheckable():
                action.setChecked(active.get(action.text().split("    ")[0], False))

    @staticmethod
    def _dot_icon(color: QColor):
        # pylint: disable=import-outside-toplevel
        from qtpy.QtGui import QIcon, QPixmap

        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(4, 4, 8, 8))
        painter.end()
        return QIcon(pixmap)

    def _show_context_menu(self, pos) -> None:
        index = self.view.indexAt(pos)
        menu = QMenu(self)
        entry = self.backend.model.entry(index.row()) if index.isValid() else None
        if entry is not None:
            row = index.row()
            menu.addAction("Copy entry", partial(self.backend.copyRow, row))
            menu.addAction("Copy message only", partial(self.backend.copyMessage, row))
            if len(self.view.selectionModel().selectedRows()) > 1:
                menu.addAction("Copy selected entries", self._copy_selection)
            if entry.line_count > 1:
                menu.addAction(
                    "Collapse" if entry.seq in self.backend.model.expanded else "Expand",
                    partial(self.view.toggle_row, row),
                )
            menu.addSeparator()
            menu.addAction(
                f"Only {entry.service}", partial(self.backend.soloService, entry.service)
            )
            menu.addAction(
                f"Hide {entry.service}", partial(self.backend.hideService, entry.service)
            )
            menu.addAction(
                f"Only {entry.group} level", partial(self.backend.soloGroup, entry.group)
            )
            menu.addSeparator()
        menu.addAction("Copy visible entries", self.backend.copyVisible)
        menu.addAction("Jump to latest", self.backend.jumpToLatest)
        menu.exec(self.view.viewport().mapToGlobal(pos))
        menu.deleteLater()

    @SafeSlot(int)
    def _reveal_row(self, row: int) -> None:
        index = self.backend.model.index(row, 0)
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)

    @SafeSlot(str)
    def _show_toast(self, text: str) -> None:
        self.toast_label.setText(text)
        self.toast_label.adjustSize()
        self._place_overlays()
        self.toast_label.show()
        self.toast_label.raise_()
        self._toast_timer.start()

    def _after_reset(self) -> None:
        if self.backend.follow:
            self.view.schedule_scroll_to_end()

    # ------------------------------------------------------------------ render
    @SafeSlot()
    def _render(self) -> None:
        state = self.backend.state
        tokens = self.view.delegate.tokens
        for group_state in state["groups"]:
            chip = self._chips.get(group_state["key"])
            if chip is not None:
                chip.set_data(
                    group_state["label"],
                    group_state["count"],
                    group_state["active"],
                    group_state["color"],
                )
        self.service_button.setText(state["servicesLabel"])
        self.service_button.refresh_theme(tokens, state["servicesFiltered"])
        self.since_button.setText(state["sinceLabel"])
        self.since_button.refresh_theme(tokens, state["since"] != "all")
        for key, button in self.mode_buttons.items():
            button.setChecked(state["searchMode"] == key)
        if self.search.text() != state["search"] and not self.search.hasFocus():
            self.search.setText(state["search"])
        self.search.setProperty("invalid", bool(state["regexError"]))
        self.search.style().unpolish(self.search)
        self.search.style().polish(self.search)
        self.search.setToolTip(state["regexError"])
        highlight = state["searchMode"] == "highlight" and bool(state["search"])
        self.match_label.setVisible(highlight)
        self.prev_button.setVisible(highlight)
        self.next_button.setVisible(highlight)
        if highlight:
            count = state["matchCount"]
            self.match_label.setText(
                f"{state['matchPos']} of {count}" if state["matchPos"] else f"{count} matches"
            )
        if state["paused"]:
            pending = state["pending"]
            self.live_pill.set_status(
                f"Paused · {pending:,} new" if pending else "Paused", tokens.warning
            )
            self.live_pill.setToolTip("Updates are paused. Click to resume.")
        else:
            self.live_pill.set_status("Live", tokens.success, pulse=True)
            self.live_pill.setToolTip("Receiving logs. Click to pause.")
        relative = state["timeMode"] == "relative"
        self.time_button.set_icon_name("history" if relative else "schedule")
        self.time_button.setToolTip("Show clock times" if relative else "Show relative times")
        self.summary_label.setText(state["summary"])
        self.reset_button.setVisible(state["filtered"])
        self._update_overlays()

    @SafeSlot()
    def _update_overlays(self, *_) -> None:
        state = self.backend.state
        tokens = self.view.delegate.tokens
        new = state["newBelow"]
        show_jump = not state["follow"] and self.backend.model.rowCount() > 0
        self.jump_button.setVisible(show_jump)
        if show_jump:
            self.jump_button.setText(f"  {new:,} new  " if new else "  Jump to latest  ")
            self.jump_button.setIcon(
                material_icon(
                    "arrow_downward",
                    size=(32, 32),
                    color=tokens.on_primary,
                    convert_to_pixmap=False,
                )
            )
            self.jump_button.adjustSize()
        empty = self.backend.model.rowCount() == 0
        self.empty.setVisible(empty)
        if empty:
            if state["empty"]:
                self._set_empty(
                    "hourglass_empty",
                    "Waiting for logs",
                    "New BEC log messages appear here.",
                    False,
                )
            else:
                self._set_empty(
                    "filter_alt_off",
                    "No entries match",
                    f"{state['total']:,} entries are hidden by the filters.",
                    True,
                )
        self._place_overlays()

    def _set_empty(self, icon: str, title: str, hint: str, reset: bool) -> None:
        tokens = self.view.delegate.tokens
        self.empty_icon.setPixmap(material_icon(icon, size=(40, 40), color=tokens.fg_subtle))
        self.empty_title.setText(title)
        self.empty_hint.setText(hint)
        self.empty_reset.setVisible(reset)

    def _place_overlays(self) -> None:
        viewport = self.view.viewport()
        self.jump_button.move(
            (viewport.width() - self.jump_button.width()) // 2,
            viewport.height() - self.jump_button.height() - 12,
        )
        self.jump_button.raise_()
        self.empty.setGeometry(viewport.rect())
        self.toast_label.move(12, viewport.height() - self.toast_label.height() - 12)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._place_overlays()

    # ------------------------------------------------------------------ theme
    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """Re-apply the BEC theme colours."""
        self.backend.refresh_theme()
        self.view.delegate.refresh_theme()
        tokens = self.view.delegate.tokens
        self.setStyleSheet(f"LogPanelQWidget {{ background: {tokens.bg.name()}; }}")
        self.toolbar.setStyleSheet(
            f"QWidget#logToolbar {{ background: {tokens.card.name()};"
            f" border-bottom: 1px solid {tokens.border.name()}; }}"
            + field_qss(tokens)
            + f"QLabel {{ color: {tokens.fg_subtle.name()}; font-size: 12px; background: none; }}"
            f'QPushButton[flat="true"] {{ color: {tokens.primary.name()}; border: none;'
            f" background: none; font-size: 12px; padding: 0 4px; }}"
        )
        self.mode_box.setStyleSheet(
            f"QWidget#modeBox {{ background: {tokens.field.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 7px; }}"
            f"QPushButton {{ background: transparent; color: {tokens.fg_muted.name()};"
            f" border: none; border-radius: 5px; padding: 0 10px; font-size: 12px; }}"
            f"QPushButton:hover {{ color: {tokens.fg.name()}; }}"
            f"QPushButton:checked {{ background: {tokens.hover.name()}; color: {tokens.fg.name()};"
            f" font-weight: 600; }}"
        )
        self._search_icon.setIcon(
            material_icon("search", size=(32, 32), color=tokens.fg_subtle, convert_to_pixmap=False)
        )
        self.view.setStyleSheet(
            f"QTreeView {{ background: {tokens.bg.name()}; border: none; outline: none; }}"
            f"QTreeView::item {{ border: none; }}"
        )
        self.jump_button.setStyleSheet(
            f"QPushButton {{ background: {tokens.primary.name()};"
            f" color: {tokens.on_primary.name()}; border: none; border-radius: 14px;"
            f" padding: 0 14px; font-size: 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {tokens.primary.lighter(110).name()}; }}"
        )
        self.toast_label.setStyleSheet(
            f"QLabel {{ background: {tokens.card.name()}; color: {tokens.fg.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 8px; padding: 6px 12px;"
            f" font-size: 12px; }}"
        )
        self.empty_title.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 14px; font-weight: 600;"
        )
        self.empty_hint.setStyleSheet(f"color: {tokens.fg_subtle.name()}; font-size: 12px;")
        self.empty_reset.setStyleSheet(
            f"QPushButton {{ color: {tokens.primary.name()}; background: transparent;"
            f" border: 1px solid {tokens.border.name()}; border-radius: 6px; padding: 5px 12px; }}"
        )
        for button in self.findChildren(IconButton):
            button.refresh_theme(tokens)
        self._render()
        self.view.viewport().update()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        return QSize(900, 420)

    def cleanup(self):
        """Stop timers and detach from the BEC log stream."""
        self._toast_timer.stop()
        self.live_pill.cleanup()
        self.backend.cleanup()
        super().cleanup()
