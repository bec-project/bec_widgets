"""QWidget version of the profile switcher popup."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QModelIndex, QPoint, QRect, QSize, Qt
from qtpy.QtGui import QFont, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import TextButton, field_qss
from bec_widgets.widgets.containers.dock_area.chrome.profile_switcher import (
    FOOTER_ACTIONS,
    THUMB_SIZE,
    ProfileSwitcherController,
)

_KIND = Qt.ItemDataRole.UserRole + 1
_ROW = Qt.ItemDataRole.UserRole + 2
_DATA = Qt.ItemDataRole.UserRole + 3


class _ProfileDelegate(QStyledItemDelegate):
    """Paints section headers and profile rows (thumbnail, name, badges, subtitle)."""

    def __init__(self, controller: ProfileSwitcherController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.tokens = ThemeTokens()
        self.highlight_row = -1

    def sizeHint(self, option, index):  # pylint: disable=invalid-name
        """Headers are short, profile rows fit the thumbnail."""
        if index.data(_KIND) == "header":
            return QSize(option.rect.width(), 30)
        return QSize(option.rect.width(), THUMB_SIZE.height() + 14)

    def _badge(self, painter: QPainter, right: int, top: int, text: str, color) -> int:
        font = QFont(painter.font())
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 12
        rect = QRect(right - width, top, width, 17)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, self.tokens.soft(color, 0.18))
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        return rect.left() - 6

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """Paint a section header or a profile row."""
        tokens = self.tokens
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        if index.data(_KIND) == "header":
            font = QFont(option.font)
            font.setPixelSize(11)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(tokens.fg_subtle)
            painter.drawText(
                rect.adjusted(12, 8, -12, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                str(index.data(Qt.ItemDataRole.DisplayRole)).upper(),
            )
            painter.restore()
            return

        data = index.data(_DATA) or {}
        highlighted = index.data(_ROW) == self.highlight_row
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        card = rect.adjusted(4, 1, -4, -1)
        if highlighted or hovered:
            path = QPainterPath()
            path.addRoundedRect(card, 7, 7)
            painter.fillPath(
                path, tokens.soft(tokens.primary, 0.14) if highlighted else tokens.hover
            )
            if highlighted:
                painter.setPen(QPen(tokens.soft(tokens.primary, 0.5), 1))
                painter.drawPath(path)

        thumb_rect = QRect(
            card.left() + 6, card.center().y() - THUMB_SIZE.height() // 2 + 1, *THUMB_SIZE.toTuple()
        )
        clip = QPainterPath()
        clip.addRoundedRect(thumb_rect, 5, 5)
        thumb = self.controller.thumbnail_for(data.get("name", ""))
        if thumb is not None:
            painter.save()
            painter.setClipPath(clip)
            painter.drawPixmap(thumb_rect, thumb)
            painter.restore()
        else:
            painter.fillPath(clip, tokens.soft(tokens.fg, 0.05))
            icon = material_icon(
                "dashboard", size=(40, 40), color=tokens.fg_subtle, convert_to_pixmap=False
            )
            icon.paint(painter, thumb_rect.adjusted(36, 15, -36, -15))
        painter.setPen(QPen(tokens.border, 1))
        painter.drawPath(clip)

        text_left = thumb_rect.right() + 12
        right = card.right() - 10
        badge_top = card.top() + 9
        if data.get("isCurrent"):
            right = self._badge(painter, right, badge_top, "Open here", tokens.primary)
        elif data.get("isOpenElsewhere"):
            right = self._badge(painter, right, badge_top, "In another tab", tokens.fg_muted)
        if data.get("readOnly"):
            right = self._badge(painter, right, badge_top, "Read-only", tokens.fg_muted)

        name_font = QFont(option.font)
        name_font.setPixelSize(13)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(tokens.fg)
        name_rect = QRect(text_left, card.top() + 8, right - text_left, 20)
        name = painter.fontMetrics().elidedText(
            data.get("name", ""), Qt.TextElideMode.ElideRight, name_rect.width()
        )
        painter.drawText(
            name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name
        )

        sub_font = QFont(option.font)
        sub_font.setPixelSize(12)
        painter.setFont(sub_font)
        painter.setPen(tokens.fg_muted)
        sub_rect = QRect(text_left, card.top() + 30, card.right() - text_left - 10, 18)
        subtitle = painter.fontMetrics().elidedText(
            data.get("subtitle", ""), Qt.TextElideMode.ElideRight, sub_rect.width()
        )
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft, subtitle)
        painter.restore()


class ProfileSwitcherPopup(QFrame):
    """The profile switcher as a popup below the toolbar profile button.

    Args:
        controller(ProfileSwitcherController): Shared switcher state.
        parent(QWidget | None): Parent widget.
    """

    def __init__(self, controller: ProfileSwitcherController, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("profileSwitcher")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.controller = controller
        self.resize(420, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Find a profile")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(controller.set_query)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.list = QListWidget(self)
        self.list.setObjectName("switcherList")
        self.list.setMouseTracking(True)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delegate = _ProfileDelegate(controller, self.list)
        self.list.setItemDelegate(self.delegate)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.list.entered.connect(self._on_item_entered)
        layout.addWidget(self.list, 1)

        self.empty_label = QLabel(self)
        self.empty_label.setObjectName("switcherMuted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        separator = QFrame(self)
        separator.setObjectName("switcherSeparator")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        footer = QHBoxLayout()
        footer.setSpacing(4)
        self.footer_buttons: dict[str, TextButton] = {}
        for key, label, icon, tooltip in FOOTER_ACTIONS:
            button = TextButton(label, "ghost", icon, self)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _=False, k=key: self._run(k))
            self.footer_buttons[key] = button
            footer.addWidget(button)
        footer.addStretch(1)
        layout.addLayout(footer)

        self.hint = QLabel(self)
        self.hint.setObjectName("switcherFooter")
        layout.addWidget(self.hint)

        controller.rows_changed.connect(self._rebuild)
        controller.highlight_changed.connect(self._sync_highlight)
        controller.profile_chosen.connect(lambda *_: self.close())
        self.refresh_theme()

    # ------------------------------------------------------------------ build
    def _rebuild(self, *_args) -> None:
        self.list.clear()
        last_section = None
        rows = self.controller.rows.items
        show_headers = len({row["section"] for row in rows}) > 1
        for row, item in enumerate(rows):
            if show_headers and item["section"] != last_section:
                header = QListWidgetItem(item["section"])
                header.setData(_KIND, "header")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list.addItem(header)
                last_section = item["section"]
            entry = QListWidgetItem(item["name"])
            entry.setData(_KIND, "item")
            entry.setData(_ROW, row)
            entry.setData(_DATA, item)
            entry.setToolTip(item["subtitle"])
            self.list.addItem(entry)
        self.empty_label.setText(self.controller.emptyText)
        self.empty_label.setVisible(not rows)
        self.footer_buttons["revert"].setEnabled(self.controller.canRevert)
        hint = "↑ ↓ choose  ·  Enter open"
        if self.controller.hasTabs:
            hint += "  ·  Ctrl+Enter or Ctrl+click new tab"
        self.hint.setText(hint + "  ·  Esc close")
        self._sync_highlight()

    def _sync_highlight(self) -> None:
        self.delegate.highlight_row = self.controller.highlight
        for i in range(self.list.count()):
            if self.list.item(i).data(_ROW) == self.controller.highlight:
                self.list.scrollToItem(self.list.item(i))
                break
        self.list.viewport().update()

    # ------------------------------------------------------------------ interaction
    def _run(self, key: str) -> None:
        self.close()
        self.controller.request(key)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        if item.data(_KIND) == "item":
            ctrl = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier
            new_tab = bool(ctrl) and self.controller.hasTabs
            self.controller.activate(int(item.data(_ROW)), new_tab)

    def _on_item_entered(self, index: QModelIndex) -> None:
        if index.data(_KIND) == "item":
            self.controller.set_highlight(int(index.data(_ROW)))

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        """Arrow keys, Enter and Escape in the search field drive the list."""
        if watched is self.search and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self.controller.move_highlight(1)
                return True
            if key == Qt.Key.Key_Up:
                self.controller.move_highlight(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                self.controller.activate(-1, ctrl and self.controller.hasTabs)
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)

    def open_at(self, anchor: QWidget | None) -> None:
        """Show the switcher below ``anchor``, right-aligned with it."""
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.controller.reset()
        if anchor is not None:
            pos = anchor.mapToGlobal(QPoint(anchor.width() - self.width(), anchor.height() + 4))
        else:
            parent = self.parentWidget()
            center = parent.mapToGlobal(parent.rect().center()) if parent else QPoint(200, 200)
            pos = center - QPoint(self.width() // 2, self.height() // 2)
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None:
            pos.setX(max(screen.left(), min(pos.x(), screen.right() - self.width())))
            pos.setY(max(screen.top(), min(pos.y(), screen.bottom() - self.height())))
        self.move(pos)
        self.show()
        self.search.setFocus(Qt.FocusReason.PopupFocusReason)

    def refresh_theme(self) -> None:
        """Apply the current theme colours."""
        tokens = ThemeTokens()
        self.delegate.tokens = tokens
        self.setStyleSheet(
            f"#profileSwitcher {{ background: {tokens.card.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 10px; }}"
            f"#switcherList {{ background: transparent; }}"
            f"#switcherSeparator {{ background: {tokens.border.name()}; }}"
            f"#switcherMuted {{ color: {tokens.fg_muted.name()}; font-size: 12px; padding: 16px; }}"
            f"#switcherFooter {{ color: {tokens.fg_subtle.name()}; font-size: 11px; }}"
            + field_qss(tokens)
        )
        for button in self.footer_buttons.values():
            button.refresh_theme(tokens)
        self.list.viewport().update()


def paint_profile_button(combo: QWidget, painter: QPainter) -> None:
    """Paint the closed profile combo as a button: icon, profile name and a chevron.

    Args:
        combo(QWidget): The toolbar profile combo (a ``QComboBox``).
        painter(QPainter): Active painter on ``combo``.
    """
    tokens = ThemeTokens()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = combo.rect().adjusted(1, 1, -1, -1)
    path = QPainterPath()
    path.addRoundedRect(rect, 6, 6)
    hovered = combo.underMouse()
    painter.fillPath(path, tokens.hover if hovered else tokens.field)
    painter.setPen(QPen(tokens.primary if combo.hasFocus() else tokens.border, 1))
    painter.drawPath(path)

    icon_rect = QRect(rect.left() + 8, rect.center().y() - 8, 16, 16)
    material_icon("dashboard", size=(32, 32), color=tokens.fg_muted, convert_to_pixmap=False).paint(
        painter, icon_rect
    )
    chevron = QRect(rect.right() - 24, rect.center().y() - 8, 16, 16)
    material_icon(
        "expand_more", size=(32, 32), color=tokens.fg_muted, convert_to_pixmap=False
    ).paint(painter, chevron)

    text = combo.currentText()
    font = QFont(combo.font())
    font.setPixelSize(13)
    if text:
        font.setWeight(QFont.Weight.DemiBold)
        painter.setPen(tokens.fg)
    else:
        text = "Unsaved workspace"
        font.setItalic(True)
        painter.setPen(tokens.fg_muted)
    painter.setFont(font)
    text_rect = QRect(
        icon_rect.right() + 8, rect.top(), chevron.left() - icon_rect.right() - 12, rect.height()
    )
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()),
    )
