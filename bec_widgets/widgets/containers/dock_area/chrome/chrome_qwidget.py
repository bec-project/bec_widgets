"""QWidget version of the dock area chrome: the Add widget gallery and the empty state."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QModelIndex, QPoint, QRect, QSize, Qt, Signal
from qtpy.QtGui import QFont, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import TextButton, field_qss, rgba
from bec_widgets.widgets.containers.dock_area.chrome.gallery_common import GalleryController

_KIND = Qt.ItemDataRole.UserRole + 1
_ROW = Qt.ItemDataRole.UserRole + 2
_DATA = Qt.ItemDataRole.UserRole + 3


class _GalleryDelegate(QStyledItemDelegate):
    """Paints category headers and widget rows (icon tile, name, description)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tokens = ThemeTokens()
        self.highlight_row = -1

    def sizeHint(self, option, index):  # pylint: disable=invalid-name
        """Headers are short, widget rows are two lines high."""
        if index.data(_KIND) == "header":
            return QSize(option.rect.width(), 30)
        return QSize(option.rect.width(), 50)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """Paint a category header or a widget row."""
        tokens = self.tokens
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        if index.data(_KIND) == "header":
            font = QFont(option.font)
            font.setPixelSize(11)
            font.setWeight(QFont.Weight.DemiBold)
            font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
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

        tile = QRect(card.left() + 8, card.center().y() - 16, 32, 32)
        path = QPainterPath()
        path.addRoundedRect(tile, 7, 7)
        painter.fillPath(path, tokens.soft(tokens.primary, 0.18))
        icon = material_icon(
            data.get("iconName", "widgets"),
            size=(40, 40),
            color=tokens.primary,
            convert_to_pixmap=False,
        )
        icon.paint(painter, tile.adjusted(7, 7, -7, -7))

        text_left = tile.right() + 12
        name_font = QFont(option.font)
        name_font.setPixelSize(13)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(tokens.fg)
        name_rect = QRect(text_left, card.top() + 7, card.right() - text_left - 10, 18)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft, data.get("name", ""))

        desc_font = QFont(option.font)
        desc_font.setPixelSize(12)
        painter.setFont(desc_font)
        painter.setPen(tokens.fg_muted)
        desc_rect = QRect(text_left, card.top() + 26, card.right() - text_left - 10, 18)
        desc = painter.fontMetrics().elidedText(
            data.get("description", ""), Qt.TextElideMode.ElideRight, desc_rect.width()
        )
        painter.drawText(desc_rect, Qt.AlignmentFlag.AlignLeft, desc)
        painter.restore()


class WidgetGalleryPopup(QFrame):
    """The Add widget gallery as a popup: search, placement, and the widgets by category.

    Args:
        controller(GalleryController): Shared gallery state.
        parent(QWidget | None): Parent widget.
    """

    def __init__(self, controller: GalleryController, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("widgetGallery")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.controller = controller
        self.resize(460, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(10)

        self.search = QLineEdit(self)
        self.search.setObjectName("gallerySearch")
        self.search.setPlaceholderText("Search widgets, e.g. plot, motor, queue")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(controller.set_query)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        place_row = QHBoxLayout()
        place_row.setSpacing(4)
        place_label = QLabel("Place", self)
        place_label.setObjectName("galleryMuted")
        place_row.addWidget(place_label)
        place_row.addSpacing(4)
        self.placement_group = QButtonGroup(self)
        self.placement_group.setExclusive(True)
        self.placement_buttons: dict[str, QToolButton] = {}
        for item in controller.placement_model.items:
            button = QToolButton(self)
            button.setObjectName("placementButton")
            button.setText(item["label"])
            button.setToolTip(item["hint"])
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, key=item["key"]: controller.set_placement(key))
            self.placement_group.addButton(button)
            self.placement_buttons[item["key"]] = button
            place_row.addWidget(button)
        place_row.addStretch(1)
        layout.addLayout(place_row)

        self.summary = QLabel(self)
        self.summary.setObjectName("galleryMuted")
        layout.addWidget(self.summary)

        self.list = QListWidget(self)
        self.list.setObjectName("galleryList")
        self.list.setMouseTracking(True)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delegate = _GalleryDelegate(self.list)
        self.list.setItemDelegate(self.delegate)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.list.entered.connect(self._on_item_entered)
        layout.addWidget(self.list, 1)

        self.empty_label = QLabel("No widget matches. Try another word.", self)
        self.empty_label.setObjectName("galleryMuted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        footer = QLabel("↑ ↓ choose  ·  Enter add  ·  Esc close", self)
        footer.setObjectName("galleryFooter")
        layout.addWidget(footer)

        controller.items.modelReset.connect(self._rebuild)
        controller.items.rowsInserted.connect(self._rebuild)
        controller.items.rowsRemoved.connect(self._rebuild)
        controller.items.dataChanged.connect(self._rebuild)
        controller.highlight_changed.connect(self._sync_highlight)
        controller.placement_changed.connect(self._sync_placement)
        controller.widget_requested.connect(lambda *_: self.close())
        self.refresh_theme()
        self._rebuild()
        self._sync_placement()

    # ------------------------------------------------------------------ build
    def _rebuild(self, *_args) -> None:
        self.list.clear()
        last_category = None
        for row, item in enumerate(self.controller.items.items):
            if item["category"] != last_category:
                header = QListWidgetItem(item["category"])
                header.setData(_KIND, "header")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list.addItem(header)
                last_category = item["category"]
            entry = QListWidgetItem(item["name"])
            entry.setData(_KIND, "item")
            entry.setData(_ROW, row)
            entry.setData(_DATA, item)
            entry.setToolTip(f"{item['description']}\nClass: {item['widgetClass']}")
            self.list.addItem(entry)
        self.empty_label.setVisible(self.controller.items.count == 0)
        self._sync_highlight()

    def _sync_highlight(self) -> None:
        self.delegate.highlight_row = self.controller.highlight
        for i in range(self.list.count()):
            if self.list.item(i).data(_ROW) == self.controller.highlight:
                self.list.scrollToItem(self.list.item(i))
                break
        self.list.viewport().update()

    def _sync_placement(self) -> None:
        current = self.controller.placement
        for item in self.controller.placement_model.items:
            button = self.placement_buttons[item["key"]]
            button.setEnabled(bool(item["available"]))
            button.setChecked(item["key"] == current)
        self.summary.setText(f"Goes: {self.controller.placement_summary()}")

    # ------------------------------------------------------------------ interaction
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        if item.data(_KIND) == "item":
            self.controller.activate(int(item.data(_ROW)))

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
                self.controller.activate()
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)

    def open_at(self, anchor: QWidget | None) -> None:
        """Show the gallery below ``anchor`` (or centred on the active window)."""
        self.controller.reset()
        self.search.clear()
        if anchor is not None:
            pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
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
            f"#widgetGallery {{ background: {tokens.card.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 10px; }}"
            f"#galleryList {{ background: transparent; }}"
            f"#galleryMuted {{ color: {tokens.fg_muted.name()}; font-size: 12px; }}"
            f"#galleryFooter {{ color: {tokens.fg_subtle.name()}; font-size: 11px; }}"
            f"#placementButton {{ color: {tokens.fg.name()}; background: transparent;"
            f" border: 1px solid {tokens.border.name()}; border-radius: 6px;"
            f" padding: 3px 9px; font-size: 12px; }}"
            f"#placementButton:hover {{ background: {tokens.hover.name()}; }}"
            f"#placementButton:checked {{ background: {tokens.soft(tokens.primary, 0.2).name()};"
            f" border-color: {tokens.primary.name()}; color: {tokens.fg.name()}; }}"
            f"#placementButton:disabled {{ color: {tokens.fg_subtle.name()};"
            f" border-color: {rgba(tokens.border, 0.5)}; }}" + field_qss(tokens)
        )
        self.list.viewport().update()


class _LayoutCard(QFrame):
    """Clickable card for a starter layout with a small schematic of its arrangement."""

    clicked = Signal(str)

    def __init__(self, item: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("layoutCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Start from the {item['name']} layout")
        self._name = item["name"]
        self.setFixedWidth(196)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        self.preview = _LayoutPreview(item["name"], self)
        layout.addWidget(self.preview)
        layout.addSpacing(6)
        title = QLabel(item["name"], self)
        title.setObjectName("layoutTitle")
        desc = QLabel(item["description"], self)
        desc.setObjectName("layoutDesc")
        desc.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addStretch(1)

    def mouseReleaseEvent(self, event):  # pylint: disable=invalid-name
        """A click on the card starts the layout."""
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self._name)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        """Enter or Space on the focused card starts the layout."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self._name)
            return
        super().keyPressEvent(event)


# Schematic rectangles (x, y, w, h in 0..1) of the starter layouts, matching catalog.STARTER_LAYOUTS
LAYOUT_SCHEMATICS: dict[str, list[tuple[float, float, float, float]]] = {
    "Scanning": [(0, 0, 0.36, 1), (0.38, 0, 0.62, 0.58), (0.38, 0.62, 0.62, 0.38)],
    "Alignment": [(0, 0, 0.58, 1), (0.6, 0, 0.4, 0.48), (0.6, 0.52, 0.4, 0.48)],
    "Monitoring": [(0, 0, 0.4, 0.48), (0, 0.52, 0.4, 0.48), (0.42, 0, 0.58, 1)],
}


class _LayoutPreview(QWidget):
    def __init__(self, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._name = name
        self.tokens = ThemeTokens()
        self.setFixedHeight(64)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Draw the schematic of the layout."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(0, 0, -1, -1)
        for x, y, w, h in LAYOUT_SCHEMATICS.get(self._name, []):
            rect = QRect(
                area.left() + int(x * area.width()),
                area.top() + int(y * area.height()),
                int(w * area.width()),
                int(h * area.height()),
            )
            path = QPainterPath()
            path.addRoundedRect(rect, 4, 4)
            painter.fillPath(path, self.tokens.soft(self.tokens.primary, 0.14))
            painter.setPen(QPen(self.tokens.soft(self.tokens.primary, 0.45), 1))
            painter.drawPath(path)
            title_bar = QRect(rect.left() + 5, rect.top() + 5, min(26, rect.width() - 10), 4)
            painter.fillRect(title_bar, self.tokens.soft(self.tokens.primary, 0.55))


class EmptyStateQWidget(QWidget):
    """What an empty dock area shows: Add widget, three starter layouts and a docking hint.

    Args:
        controller(GalleryController): Shared gallery state (starter layouts).
        parent(QWidget | None): Parent widget.
    """

    add_requested = Signal()

    def __init__(self, controller: GalleryController, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("dockEmptyState")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.controller = controller

        outer = QVBoxLayout(self)
        outer.addStretch(3)
        column = QVBoxLayout()
        column.setSpacing(8)
        column.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.icon = QLabel(self)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setFixedSize(56, 56)
        column.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("This workspace is empty", self)
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(title)
        subtitle = QLabel(
            "Add the widgets you need, or start from a layout and change it afterwards.", self
        )
        subtitle.setObjectName("emptySubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        column.addWidget(subtitle)
        column.addSpacing(8)

        self.add_button = TextButton("Add widget", "primary", "add", self)
        self.add_button.setToolTip("Open the widget gallery (Ctrl+Shift+A)")
        self.add_button.setMinimumWidth(150)
        self.add_button.clicked.connect(self.add_requested)
        column.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addSpacing(18)

        start = QLabel("Or start from a layout", self)
        start.setObjectName("emptySection")
        start.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(start)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.cards: list[_LayoutCard] = []
        for item in controller.layouts.items:
            card = _LayoutCard(item, self)
            card.clicked.connect(controller.activate_layout)
            cards.addWidget(card)
            self.cards.append(card)
        column.addLayout(cards)
        column.addSpacing(14)

        hint = QLabel(
            "Tip: drag a tab onto the edge of another widget to split the view, "
            "or onto its centre to stack them as tabs.",
            self,
        )
        hint.setObjectName("emptyHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        column.addWidget(hint)

        wrapper = QHBoxLayout()
        wrapper.addStretch(1)
        holder = QWidget(self)
        holder.setLayout(column)
        holder.setMaximumWidth(680)
        holder.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        wrapper.addWidget(holder)
        wrapper.addStretch(1)
        outer.addLayout(wrapper)
        outer.addStretch(4)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        """Apply the current theme colours."""
        tokens = ThemeTokens()
        self.icon.setPixmap(
            material_icon("dashboard_customize", size=(30, 30), color=tokens.primary)
        )
        self.icon.setStyleSheet(
            f"background: {tokens.soft(tokens.primary, 0.16).name()}; border-radius: 28px;"
        )
        self.setStyleSheet(
            f"#dockEmptyState {{ background: {tokens.bg.name()}; }}"
            f"#emptyTitle {{ color: {tokens.fg.name()}; font-size: 18px; font-weight: 600; }}"
            f"#emptySubtitle {{ color: {tokens.fg_muted.name()}; font-size: 13px; }}"
            f"#emptySection {{ color: {tokens.fg_muted.name()}; font-size: 12px;"
            f" font-weight: 600; }}"
            f"#emptyHint {{ color: {tokens.fg_subtle.name()}; font-size: 12px; }}"
            f"#layoutCard {{ background: {tokens.card.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 10px; }}"
            f"#layoutCard:hover, #layoutCard:focus {{ border-color: {tokens.primary.name()}; }}"
            f"#layoutTitle {{ color: {tokens.fg.name()}; font-size: 13px; font-weight: 600; }}"
            f"#layoutDesc {{ color: {tokens.fg_muted.name()}; font-size: 12px; }}"
        )
        self.add_button.refresh_theme(tokens)
        for card in self.cards:
            card.preview.tokens = tokens
            card.preview.update()
