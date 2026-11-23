"""QWidget rendering of the command palette card.

Twin of ``qml/CommandPaletteView.qml``: same layout, colours and keyboard handling, painted with
a :class:`QStyledItemDelegate` over the controller's list model.
"""

from __future__ import annotations

from functools import lru_cache

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QModelIndex, QObject, QPointF, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from qtpy.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeConnect, SafeSlot
from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.widgets.utility.command_palette.palette_core import (
    ROLES,
    SCOPES,
    CommandPaletteController,
)

ROW_HEIGHT = 46
SINGLE_LINE_ROW_HEIGHT = 36
HEADER_HEIGHT = 28
PAGE_STEP = 8
# every leading edge (search icon, chips, section headers, row icons, footer) sits on
# CONTENT_INSET; the row highlight is set back to ROW_INSET so its content stays on that line
CONTENT_INSET = 16
ROW_INSET = 8
ICON_SIZE = 18
ICON_GAP = 12


def _role(key: str) -> int:
    return Qt.ItemDataRole.UserRole + 1 + ROLES.index(key)


@lru_cache(maxsize=512)
def _icon(name: str, color: str, size: int) -> QPixmap:
    pixmap = material_icon(name, size=(size * 2, size * 2), color=color, filled=False)
    pixmap.setDevicePixelRatio(2.0)
    return pixmap


def _font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def draw_keycap(painter: QPainter, right: float, center_y: float, text: str, tokens) -> float:
    """Paint a small key label ending at ``right``; return its left edge."""
    font = _font(11, QFont.Weight.DemiBold)
    width = QFontMetrics(font).horizontalAdvance(text) + 12
    rect = QRectF(right - width, center_y - 10, width, 20)
    painter.setPen(tokens.border)
    painter.setBrush(tokens.field)
    painter.drawRoundedRect(rect, 5, 5)
    painter.setPen(tokens.fg_muted)
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    return rect.left()


class PaletteDelegate(QStyledItemDelegate):
    """Paints result rows: icon, highlighted title, subtitle and a right-hand hint."""

    def __init__(self, controller: CommandPaletteController, parent: QObject | None = None):
        super().__init__(parent)
        self.controller = controller
        self.tokens = ThemeTokens()
        self.single_section = False

    def has_header(self, index: QModelIndex) -> bool:
        """Whether a section header is drawn above ``index``."""
        if not self.controller.sectioned or self.single_section:
            return False
        section = index.data(_role("section"))
        if not section:
            return False
        if index.row() == 0:
            return True
        previous = index.siblingAtRow(index.row() - 1)
        return previous.data(_role("section")) != section

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        # pylint: disable=invalid-name
        height = ROW_HEIGHT if index.data(_role("subtitle")) else SINGLE_LINE_ROW_HEIGHT
        height += HEADER_HEIGHT if self.has_header(index) else 0
        return QSize(option.rect.width(), height)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        tokens = self.tokens
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(option.rect)

        if self.has_header(index):
            header = QRectF(
                rect.left() + CONTENT_INSET,
                rect.top(),
                rect.width() - 2 * CONTENT_INSET,
                HEADER_HEIGHT,
            )
            painter.setPen(tokens.fg_muted)
            painter.setFont(_font(11, QFont.Weight.DemiBold))
            painter.drawText(
                header.adjusted(0, 8, 0, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                str(index.data(_role("section"))),
            )
            rect.setTop(rect.top() + HEADER_HEIGHT)

        current = index.row() == self.controller.currentIndex
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        row = rect.adjusted(ROW_INSET, 1, -ROW_INSET, -1)
        if current or hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.soft(tokens.primary, 0.16) if current else tokens.hover)
            painter.drawRoundedRect(row, 8, 8)

        # icon on the content line, no tile behind it
        icon_left = rect.left() + CONTENT_INSET
        icon_color = tokens.primary if current else tokens.fg_muted
        pixmap = _icon(str(index.data(_role("icon")) or "bolt"), icon_color.name(), ICON_SIZE)
        painter.drawPixmap(QPointF(icon_left, row.center().y() - ICON_SIZE / 2), pixmap)

        # right-hand side: shortcut keycaps, run hint on the current row, else the category
        right = rect.right() - CONTENT_INSET
        shortcut = str(index.data(_role("shortcut")) or "")
        if current:
            right = draw_keycap(painter, right, row.center().y(), "↵", tokens) - 6
            painter.setFont(_font(12))
            painter.setPen(tokens.fg_muted)
            hint = str(index.data(_role("hint")) or "")
            width = QFontMetrics(painter.font()).horizontalAdvance(hint)
            painter.drawText(
                QRectF(right - width, row.top(), width, row.height()),
                Qt.AlignmentFlag.AlignVCenter,
                hint,
            )
            right -= width + 12
        elif shortcut:
            right = draw_keycap(painter, right, row.center().y(), shortcut, tokens) - 10
        elif not self.controller.sectioned and self.controller.scope == "all":
            painter.setFont(_font(11))
            painter.setPen(tokens.fg_muted)
            category = str(index.data(_role("category")) or "")
            width = QFontMetrics(painter.font()).horizontalAdvance(category)
            painter.drawText(
                QRectF(right - width, row.top(), width, row.height()),
                Qt.AlignmentFlag.AlignVCenter,
                category,
            )
            right -= width + 12

        # title with matched characters, subtitle below
        left = icon_left + ICON_SIZE + ICON_GAP
        available = max(20.0, right - left)
        title = str(index.data(_role("title")) or "")
        matched = set(index.data(_role("positions")) or [])
        regular = _font(13)
        bold = _font(13, QFont.Weight.Bold)
        subtitle = str(index.data(_role("subtitle")) or "")
        x = left
        if subtitle:
            baseline = row.top() + 20
        else:  # a title on its own sits on the row's centre line
            metrics = QFontMetrics(regular)
            baseline = row.center().y() + (metrics.ascent() - metrics.descent()) / 2
        elided = QFontMetrics(regular).elidedText(
            title, Qt.TextElideMode.ElideRight, int(available)
        )
        runs: list[tuple[bool, str]] = []
        for i, char in enumerate(elided):
            hit = i in matched and not (elided.endswith("…") and i == len(elided) - 1)
            if runs and runs[-1][0] == hit:
                runs[-1] = (hit, runs[-1][1] + char)
            else:
                runs.append((hit, char))
        for hit, text in runs:
            font = bold if hit else regular
            painter.setFont(font)
            painter.setPen(tokens.primary if hit else tokens.fg)
            painter.drawText(QPointF(x, baseline), text)
            x += QFontMetrics(font).horizontalAdvance(text)

        if subtitle:
            painter.setFont(_font(11))
            painter.setPen(tokens.fg_muted)
            painter.drawText(
                QRectF(left, row.top() + 24, available, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                QFontMetrics(painter.font()).elidedText(
                    subtitle, Qt.TextElideMode.ElideRight, int(available)
                ),
            )
        painter.restore()


class ScopeChip(QAbstractButton):
    """Checkable pill showing a scope and its query prefix, painted like the QML chip."""

    def __init__(self, label: str, scope: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setText(label)
        self.scope = scope
        self.tokens = ThemeTokens()
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedHeight(25)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        bold = _font(12, QFont.Weight.DemiBold)
        return QSize(QFontMetrics(bold).horizontalAdvance(self.text()) + 24, 25)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = self.tokens
        active = self.isChecked()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if active:
            fill = tokens.soft(tokens.primary, 0.18)
        elif self.underMouse():
            fill = tokens.hover
        else:
            fill = QColor(Qt.GlobalColor.transparent)
        painter.setBrush(fill)
        painter.setPen(tokens.soft(tokens.primary, 0.5) if active else tokens.border)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setFont(_font(12, QFont.Weight.DemiBold if active else QFont.Weight.Normal))
        painter.setPen(tokens.fg if active else tokens.fg_muted)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


class PaletteCardWidget(QFrame):
    """Search field, scope chips, result list and key hints of the command palette.

    Args:
        controller(CommandPaletteController): Shared search state.
        parent(QWidget | None): The hosting overlay.
    """

    shadow_margin = 0

    def __init__(self, controller: CommandPaletteController, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("PaletteCard")
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # search row
        search_bar = QWidget(self)
        search_bar.setFixedHeight(54)
        search_row = QHBoxLayout(search_bar)
        search_row.setContentsMargins(CONTENT_INSET, 0, CONTENT_INSET, 0)
        search_row.setSpacing(ICON_GAP)
        self.search_icon = QLabel(self)
        self.search_icon.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.input = QLineEdit(self)
        self.input.setObjectName("PaletteInput")
        self.input.setPlaceholderText("Search actions, widgets, devices and workspaces…")
        self.input.setFrame(False)
        self.input.installEventFilter(self)
        self.input.textEdited.connect(self._on_text_edited)
        search_row.addWidget(self.search_icon)
        search_row.addWidget(self.input, 1)
        layout.addWidget(search_bar)

        # scope chips
        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(CONTENT_INSET, 0, CONTENT_INSET, 12)
        chip_row.setSpacing(8)
        self.chips = QButtonGroup(self)
        self.chips.setExclusive(True)
        for scope, label, prefix in SCOPES:
            chip = ScopeChip(f"{label}  {prefix}".strip(), scope, self)
            chip.clicked.connect(lambda _=False, s=scope: self._pick_scope(s))
            self.chips.addButton(chip)
            chip_row.addWidget(chip)
        chip_row.addStretch(1)
        layout.addLayout(chip_row)

        self.divider = QFrame(self)
        self.divider.setFixedHeight(1)
        layout.addWidget(self.divider)

        # results / empty state
        self.stack = QStackedWidget(self)
        self.list = QListView(self)
        self.list.setObjectName("PaletteList")
        self.list.setModel(controller.model)
        self.delegate = PaletteDelegate(controller, self.list)
        self.list.setItemDelegate(self.delegate)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setMouseTracking(True)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setSpacing(0)
        self.list.clicked.connect(lambda index: controller.execute(index.row()))
        self.empty = QWidget(self)
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.addStretch(1)
        self.empty_icon = QLabel(self.empty)
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title = QLabel(self.empty)
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_all_button = QPushButton("Search all", self.empty)
        self.search_all_button.setObjectName("PaletteSearchAll")
        self.search_all_button.setFlat(True)
        self.search_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.search_all_button.clicked.connect(lambda: self._pick_scope("all"))
        empty_layout.addWidget(self.empty_icon)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.search_all_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(2)
        self.stack.addWidget(self.list)
        self.stack.addWidget(self.empty)
        layout.addWidget(self.stack, 1)

        # footer
        self.footer = QFrame(self)
        self.footer.setObjectName("PaletteFooter")
        footer_row = QHBoxLayout(self.footer)
        footer_row.setContentsMargins(CONTENT_INSET, 8, CONTENT_INSET, 8)
        footer_row.setSpacing(16)
        self.footer_hints = QLabel(self.footer)
        self.count_label = QLabel(self.footer)
        self.count_label.setObjectName("PaletteCount")
        footer_row.addWidget(self.footer_hints, 1)
        footer_row.addWidget(self.count_label)
        layout.addWidget(self.footer)

        controller.queryChanged.connect(self._sync_query)
        controller.scopeChanged.connect(self._sync_scope)
        controller.resultsChanged.connect(self._sync_results)
        controller.currentIndexChanged.connect(self._sync_current)
        self.refresh_theme(ThemeTokens())
        self._sync_scope()
        self._sync_results()

        self._theme_connection = None
        theme = getattr(QApplication.instance(), "theme", None)
        if theme is not None:
            self._theme_connection = SafeConnect(self, theme.theme_changed, self._on_theme_changed)

    # ------------------------------------------------------------------ host API
    def focus_input(self) -> None:
        """Give the keyboard focus to the search field."""
        self.input.setFocus(Qt.FocusReason.PopupFocusReason)
        self.input.selectAll()

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        self.delegate.tokens = tokens
        for chip in self.chips.buttons():
            chip.tokens = tokens
            chip.update()
        primary = tokens.primary.name()
        self.setStyleSheet(f"""
            #PaletteCard {{ background: {tokens.card.name()}; border: 1px solid
                {tokens.border.name()}; border-radius: 12px; }}
            #PaletteInput {{ background: transparent; border: none; color: {tokens.fg.name()};
                font-size: 16px; padding: 0px; selection-background-color: {primary}; }}
            #PaletteList {{ background: transparent; border: none; }}
            #PaletteFooter {{ background: {tokens.field.name()}; border: none;
                border-top: 1px solid {tokens.border.name()};
                border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}
            #PaletteFooter QLabel {{ color: {tokens.fg_muted.name()}; font-size: 11px;
                background: transparent; }}
            #PaletteFooter #PaletteCount {{ color: {tokens.fg.name()}; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 2px; }}
            QScrollBar::handle:vertical {{ background: {tokens.track.name()};
                border-radius: 2px; min-height: 24px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
            """)
        self.divider.setStyleSheet(f"background: {tokens.border.name()};")
        self.search_icon.setPixmap(_icon("search", tokens.fg_muted.name(), ICON_SIZE))
        self.empty_icon.setPixmap(_icon("search_off", tokens.fg_subtle.name(), 32))
        self.empty_title.setStyleSheet(f"color: {tokens.fg_muted.name()}; font-size: 14px;")
        self.search_all_button.setStyleSheet(
            f"QPushButton {{ color: {primary}; background: transparent; border: none;"
            f" font-size: 13px; padding: 4px 8px; }}"
            f" QPushButton:hover {{ text-decoration: underline; }}"
        )
        key = f"<span style='color:{tokens.fg_muted.name()}; font-weight:600'>{{}}</span>"
        self.footer_hints.setText(
            "&nbsp;&nbsp;&nbsp;".join(
                f"{key.format(k)}&nbsp;{label}"
                for k, label in (
                    ("↑↓", "navigate"),
                    ("↵", "run"),
                    ("tab", "scope"),
                    ("esc", "close"),
                )
            )
        )
        self.list.viewport().update()

    @SafeSlot(str)
    @SafeSlot()
    def _on_theme_changed(self, _theme: str | None = None) -> None:
        """Repaint in the new theme, also while the palette is open."""
        self.refresh_theme(ThemeTokens())
        overlay = self.parentWidget()
        if overlay is not None:
            overlay.update()

    def release(self) -> None:
        """Stop following the application theme."""
        connection, self._theme_connection = self._theme_connection, None
        theme = getattr(QApplication.instance(), "theme", None)
        if connection is None or theme is None:
            return
        connection.invalidate()
        try:
            theme.theme_changed.disconnect(connection)
        except (RuntimeError, TypeError):
            pass  # already gone with the theme object

    # ------------------------------------------------------------------ sync from controller
    def _pick_scope(self, scope: str) -> None:
        self.controller.set_scope(scope)
        self.input.setFocus()

    def _on_text_edited(self, text: str) -> None:
        self.controller.set_query(text)
        # a typed scope prefix (">", "+", "@", "#") selects the chip and leaves the field
        self._sync_query()

    def _sync_query(self) -> None:
        if self.input.text() != self.controller.query:
            self.input.setText(self.controller.query)

    def _sync_scope(self) -> None:
        for chip in self.chips.buttons():
            chip.setChecked(chip.scope == self.controller.scope)

    def _sync_results(self) -> None:
        count = self.controller.resultCount
        model = self.controller.model
        sections = {model.index(row, 0).data(_role("section")) for row in range(count)}
        self.delegate.single_section = len(sections) <= 1
        self.stack.setCurrentWidget(self.list if count else self.empty)
        self.empty_title.setText(self.controller.empty_text())
        # a scoped search that finds nothing offers the same query in every scope
        self.search_all_button.setVisible(
            not count and bool(self.controller.query) and self.controller.scope != "all"
        )
        self.count_label.setText(self._count_text())
        # row heights depend on the section headers
        self.list.doItemsLayout()
        self.list.scrollToTop()

    def _count_text(self) -> str:
        controller = self.controller
        count, total = controller.resultCount, controller.totalCount
        if total > count:
            return f"First {count} of {total}, type to narrow"
        if not controller.query or not count:
            return ""
        return f"{count} result{'s' if count != 1 else ''}"

    def _sync_current(self) -> None:
        row = self.controller.currentIndex
        if row >= 0:
            self.list.scrollTo(
                self.controller.model.index(row, 0), QAbstractItemView.ScrollHint.EnsureVisible
            )
        self.list.viewport().update()

    # ------------------------------------------------------------------ keyboard
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        if watched is not self.input or event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key = event.key()
        controller = self.controller
        if key == Qt.Key.Key_Down:
            controller.move(1)
        elif key == Qt.Key.Key_Up:
            controller.move(-1)
        elif key == Qt.Key.Key_PageDown:
            controller.move_page(PAGE_STEP)
        elif key == Qt.Key.Key_PageUp:
            controller.move_page(-PAGE_STEP)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            controller.execute()
        elif key == Qt.Key.Key_Tab:
            controller.cycle_scope(1)
        elif key == Qt.Key.Key_Backtab:
            controller.cycle_scope(-1)
        elif key == Qt.Key.Key_Escape:
            controller.request_dismiss()
        elif key == Qt.Key.Key_Backspace and not self.input.text():
            controller.clear_scope()
        else:
            return super().eventFilter(watched, event)
        return True
