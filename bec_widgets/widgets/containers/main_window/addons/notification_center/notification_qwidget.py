"""Notification toasts, history drawer and bell built with QWidgets.

Same UX as :mod:`notification_qml`; the state comes from
:class:`~.notification_ux_common.NotificationHostBase`.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QAbstractListModel, QModelIndex, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import IconButton, TextButton, field_qss, rgba
from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_ux_common import (
    NotificationHostBase,
)


def _icon_badge(painter: QPainter, rect: QRectF, icon: str, color: QColor, tint: QColor):
    """Paint a round tinted badge with a Material icon, as used by toasts and rows."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(tint)
    painter.drawEllipse(rect)
    size = int(rect.width() * 0.6)
    pixmap = material_icon(icon, size=(size * 2, size * 2), color=color, filled=True)
    target = QRectF(rect.center().x() - size / 2, rect.center().y() - size / 2, size, size).toRect()
    painter.drawPixmap(target, pixmap)


class _Badge(QWidget):
    """Round severity icon painted on a tinted circle."""

    def __init__(self, parent: QWidget | None = None, size: int = 32):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._icon = "info"
        self._color = QColor("#888")
        self._tint = QColor("#333")

    def set_icon(self, icon: str, color: str, tint: str) -> None:
        """Set icon name and colours."""
        self._icon, self._color, self._tint = icon, QColor(color), QColor(tint)
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _icon_badge(painter, QRectF(self.rect()), self._icon, self._color, self._tint)
        painter.end()


class ToastCard(QFrame):
    """One toast: badge, title, message, meta line and actions."""

    def __init__(self, host: NotificationHostBase, parent: QWidget | None = None):
        super().__init__(parent)
        self.host = host
        self.entry_id = ""
        self._row: dict = {}
        self.setObjectName("toastCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self.badge = _Badge(self, 32)
        self.title = QLabel(self)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.count = QLabel(self)
        self.close_btn = IconButton("close", "Dismiss", self, size=16)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(lambda: self.host.dismiss_toast(self.entry_id))
        self.body = QLabel(self)
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.meta = QLabel(self)
        self.details_btn = TextButton("Details", "ghost", "open_in_new", self)
        self.details_btn.setMinimumHeight(28)
        self.details_btn.clicked.connect(lambda: self.host.open_details(self.entry_id))
        self.copy_btn = IconButton("content_copy", "Copy report", self, size=16)
        self.copy_btn.setFixedSize(28, 28)
        self.copy_btn.clicked.connect(lambda: self.host.copy_details(self.entry_id))
        self.ack_btn = TextButton("Acknowledge", "danger", "done", self)
        self.ack_btn.setMinimumHeight(28)
        self.ack_btn.clicked.connect(lambda: self.host.acknowledge(self.entry_id))

        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(self.title, 1)
        head.addWidget(self.count)
        head.addWidget(self.close_btn)
        text = QVBoxLayout()
        text.setSpacing(3)
        text.addLayout(head)
        text.addWidget(self.body)
        text.addWidget(self.meta)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(6)
        self.actions.addStretch(1)
        self.actions.addWidget(self.copy_btn)
        self.actions.addWidget(self.details_btn)
        self.actions.addWidget(self.ack_btn)
        text.addLayout(self.actions)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 10, 10)
        row.setSpacing(12)
        row.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(text, 1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

    def set_row(self, row: dict, tokens: ThemeTokens) -> None:
        """Show the entry described by ``row``."""
        self._row = row
        self.entry_id = row["id"]
        self.badge.set_icon(row["icon"], row["color"], row["tint"])
        self.title.setText(row["title"])
        self.title.setToolTip(row["title"])
        self.count.setText(f"×{row['count']}")
        self.count.setVisible(row["count"] > 1)
        body = row["body"] or ""
        self.body.setText(body if len(body) <= 220 else body[:217] + "…")
        self.body.setToolTip(body if len(body) > 220 else "")
        self.body.setVisible(bool(body))
        self.meta.setText(row["meta"])
        self.close_btn.setVisible(not row["needsAck"])
        self.ack_btn.setVisible(row["needsAck"])
        self.details_btn.setVisible(row["hasDetails"] or row["needsAck"])
        self.copy_btn.setVisible(row["severity"] in ("error", "critical"))
        self._style(tokens)
        self.update()

    def _style(self, tokens: ThemeTokens) -> None:
        self.title.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 13px; font-weight: 600; background: none;"
        )
        self.body.setStyleSheet(
            f"color: {tokens.fg_muted.name()}; font-size: 12px; background: none;"
        )
        self.meta.setStyleSheet(
            f"color: {tokens.fg_subtle.name()}; font-size: 11px; background: none;"
        )
        self.count.setStyleSheet(
            f"color: {self._row.get('color', tokens.fg.name())}; font-size: 11px;"
            f" font-weight: 700; background: {self._row.get('tint', 'transparent')};"
            " border-radius: 8px; padding: 0px 6px;"
        )
        self.count.setFixedHeight(16)
        for button in (self.close_btn, self.details_btn, self.copy_btn, self.ack_btn):
            button.refresh_theme(tokens)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, tokens.card)
        accent = QColor(self._row.get("color", tokens.border.name()))
        critical = self._row.get("needsAck", False)
        painter.setPen(QPen(accent if critical else tokens.border, 1.5 if critical else 1))
        painter.drawPath(path)
        # severity stripe along the straight part of the left edge
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(rect.left(), rect.top() + 10, 4, rect.height() - 20), 2, 2)
        painter.end()


class ToastStack(QWidget):
    """Bottom-right column of toasts with an overflow link; hovering pauses the countdowns."""

    def __init__(self, host: NotificationHostBase, parent: QWidget):
        super().__init__(parent)
        self.host = host
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._cards: dict[str, ToastCard] = {}
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)  # room for the shadow
        self._layout.setSpacing(10)
        self.more_btn = TextButton("", "neutral", "expand_less", self)
        self.more_btn.clicked.connect(lambda: self.host.set_drawer_open(True))
        self._layout.addWidget(self.more_btn, 0, Qt.AlignmentFlag.AlignRight)

    def set_state(self, state: dict, tokens: ThemeTokens) -> None:
        """Show the toasts of ``state``; cards are reused by entry id."""
        rows = state["toasts"]
        wanted = [row["id"] for row in rows]
        for entry_id in list(self._cards):
            if entry_id not in wanted:
                card = self._cards.pop(entry_id)
                self._layout.removeWidget(card)
                card.deleteLater()
        # newest at the bottom, nearest to the status bar
        for position, row in enumerate(rows, start=1):
            card = self._cards.get(row["id"])
            if card is None:
                card = ToastCard(self.host, self)
                self._cards[row["id"]] = card
            card.set_row(row, tokens)
            if self._layout.indexOf(card) != position:
                self._layout.removeWidget(card)
                self._layout.insertWidget(position, card)
        overflow = state["overflow"]
        self.more_btn.setText(f"{overflow} more in notifications")
        self.more_btn.setVisible(overflow > 0)
        self.more_btn.refresh_theme(tokens)
        # solid like a card: the link floats over plots
        self.more_btn.setStyleSheet(
            self.more_btn.styleSheet()
            + f"QPushButton {{ background: {tokens.card.name()}; }}"
            + f"QPushButton:hover {{ background: {tokens.hover.name()}; }}"
        )
        self.setVisible(bool(rows))

    @property
    def cards(self) -> list[ToastCard]:
        """Cards on screen, oldest first."""
        return [
            self._layout.itemAt(i).widget()
            for i in range(self._layout.count())
            if isinstance(self._layout.itemAt(i).widget(), ToastCard)
        ]

    def enterEvent(self, event):  # pylint: disable=invalid-name
        self.host.set_toasts_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        self.host.set_toasts_hovered(False)
        super().leaveEvent(event)


class _RowsModel(QAbstractListModel):
    """Rows of the history list; each row is the dictionary from ``entry_row``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        """Replace the rows."""
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # pylint: disable=invalid-name
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role == Qt.ItemDataRole.DisplayRole:
            return row["title"]
        if role == Qt.ItemDataRole.ToolTipRole:
            return row["timeAbs"]
        return None


class _RowDelegate(QStyledItemDelegate):
    """Paints a history row: stripe, badge, title, time, message and meta line."""

    HEIGHT = 78

    def sizeHint(self, _option, _index):  # pylint: disable=invalid-name
        return QSize(200, self.HEIGHT)

    def paint(self, painter: QPainter, option, index):
        row = index.data(Qt.ItemDataRole.UserRole)
        if row is None:
            return
        tokens = ThemeTokens()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(8, 3, -8, -3)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        background = QColor(row["tint"]) if row["needsAck"] else tokens.card
        if hovered:
            background = tokens.hover if not row["needsAck"] else QColor(row["tint"]).lighter(110)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, background)
        painter.setPen(QPen(QColor(row["color"]) if row["needsAck"] else tokens.border, 1))
        painter.drawPath(path)
        _icon_badge(
            painter,
            QRectF(rect.left() + 10, rect.top() + 10, 28, 28),
            row["icon"],
            QColor(row["color"]),
            QColor(row["tint"]) if not row["needsAck"] else tokens.card,
        )
        left = rect.left() + 48
        right = rect.right() - 10
        font = QFont(option.font)
        font.setPixelSize(11)
        painter.setFont(font)
        time_w = painter.fontMetrics().horizontalAdvance(row["time"])
        painter.setPen(tokens.fg_subtle)
        painter.drawText(
            QRectF(right - time_w, rect.top() + 8, time_w, 18),
            Qt.AlignmentFlag.AlignVCenter,
            row["time"],
        )
        title_right = right - time_w - 8
        if row["unread"]:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.primary)
            painter.drawEllipse(QRectF(title_right - 7, rect.top() + 14, 7, 7))
            title_right -= 14
        if row["count"] > 1:
            badge = f"×{row['count']}"
            badge_w = painter.fontMetrics().horizontalAdvance(badge) + 12
            badge_rect = QRectF(title_right - badge_w, rect.top() + 9, badge_w, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(row["tint"]))
            painter.drawRoundedRect(badge_rect, 8, 8)
            painter.setPen(QColor(row["color"]))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge)
            title_right -= badge_w + 6
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(tokens.fg)
        title = painter.fontMetrics().elidedText(
            row["title"], Qt.TextElideMode.ElideRight, int(title_right - left)
        )
        painter.drawText(
            QRectF(left, rect.top() + 8, title_right - left, 18),
            Qt.AlignmentFlag.AlignVCenter,
            title,
        )
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(tokens.fg_muted)
        body = painter.fontMetrics().elidedText(
            row["body"].replace("\n", " "), Qt.TextElideMode.ElideRight, int(right - left)
        )
        painter.drawText(
            QRectF(left, rect.top() + 28, right - left, 18), Qt.AlignmentFlag.AlignVCenter, body
        )
        font.setPixelSize(11)
        painter.setFont(font)
        meta_color = QColor(row["color"]) if row["needsAck"] else tokens.fg_subtle
        painter.setPen(meta_color)
        meta = ("Needs acknowledgement · " if row["needsAck"] else "") + " · ".join(
            part for part in (row["severityLabel"], row["source"], row["scan"]) if part
        )
        meta = painter.fontMetrics().elidedText(
            meta, Qt.TextElideMode.ElideRight, int(right - left)
        )
        painter.drawText(
            QRectF(left, rect.top() + 48, right - left, 16), Qt.AlignmentFlag.AlignVCenter, meta
        )
        painter.restore()


class _DetailsPage(QWidget):
    """Full view of one entry: message, metadata, details text and actions."""

    def __init__(self, host: NotificationHostBase, parent: QWidget | None = None):
        super().__init__(parent)
        self.host = host
        self.entry_id = ""
        self.back_btn = TextButton("All notifications", "ghost", "arrow_back", self)
        self.back_btn.clicked.connect(lambda: self.host.select(None))
        self.badge = _Badge(self, 36)
        self.title = QLabel(self)
        self.title.setWordWrap(True)
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.pill = QLabel(self)
        self.pill.setFixedHeight(18)
        self.body = QLabel(self)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.facts = QLabel(self)
        self.facts.setTextFormat(Qt.TextFormat.RichText)
        self.details_label = QLabel("Details", self)
        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPixelSize(11)
        self.details.setFont(mono)
        self.copy_btn = TextButton("Copy report", "neutral", "content_copy", self)
        self.copy_btn.clicked.connect(self._copy)
        self.ack_btn = TextButton("Acknowledge", "danger", "done", self)
        self.ack_btn.clicked.connect(lambda: self.host.acknowledge(self.entry_id))
        self.remove_btn = TextButton("Remove", "ghost", "delete", self)
        self.remove_btn.clicked.connect(lambda: self.host.remove(self.entry_id))

        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_col.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignLeft)
        title_col.addWidget(self.title)
        head.addLayout(title_col, 1)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.ack_btn)
        actions.addStretch(1)
        actions.addWidget(self.remove_btn)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.back_btn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(head)
        layout.addWidget(self.body)
        layout.addWidget(self.facts)
        layout.addWidget(self.details_label)
        layout.addWidget(self.details, 1)
        layout.addStretch(0)
        layout.addLayout(actions)

    def _copy(self) -> None:
        if self.host.copy_details(self.entry_id):
            self.copy_btn.setText("Copied")

    def set_row(self, row: dict, tokens: ThemeTokens) -> None:
        """Show ``row``."""
        if row["id"] != self.entry_id:
            self.copy_btn.setText("Copy report")
        self.entry_id = row["id"]
        self.badge.set_icon(row["icon"], row["color"], row["tint"])
        self.title.setText(row["title"])
        label = row["severityLabel"] + (" · needs acknowledgement" if row["needsAck"] else "")
        self.pill.setText(label)
        self.body.setText(row["body"] or "No message.")
        facts = [("When", row["timeAbs"])]
        if row["count"] > 1:
            facts.append(("Repeated", f"{row['count']} times since {row['firstAbs']}"))
        if row["source"]:
            facts.append(("Source", row["source"]))
        if row["scan"]:
            facts.append(("Scan", row["scan"]))
        self.facts.setText(
            "<table cellspacing='0' cellpadding='2'>"
            + "".join(
                f"<tr><td style='color:{tokens.fg_subtle.name()}; padding-right:12px'>{k}</td>"
                f"<td style='color:{tokens.fg.name()}'>{v}</td></tr>"
                for k, v in facts
            )
            + "</table>"
        )
        if self.details.toPlainText() != row["details"]:
            self.details.setPlainText(row["details"])
        self.details.setVisible(row["hasDetails"])
        self.details_label.setVisible(row["hasDetails"])
        self.ack_btn.setVisible(row["needsAck"])
        self.title.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 15px; font-weight: 600; background: none;"
        )
        self.pill.setStyleSheet(
            f"color: {row['color']}; background: {row['tint']}; border-radius: 9px;"
            " padding: 1px 8px; font-size: 11px; font-weight: 600;"
        )
        self.body.setStyleSheet(f"color: {tokens.fg.name()}; font-size: 13px; background: none;")
        self.facts.setStyleSheet("font-size: 12px; background: none;")
        self.details_label.setStyleSheet(
            f"color: {tokens.fg_subtle.name()}; font-size: 11px; font-weight: 600;"
            " text-transform: uppercase; background: none;"
        )
        self.details.setStyleSheet(
            f"QPlainTextEdit {{ background: {tokens.field.name()}; color: {tokens.fg.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 8px; padding: 6px; }}"
        )
        for button in (self.back_btn, self.copy_btn, self.ack_btn, self.remove_btn):
            button.refresh_theme(tokens)


class HistoryDrawer(QFrame):
    """Right-edge panel with filters, search, the notification history and details."""

    def __init__(self, host: NotificationHostBase, parent: QWidget):
        super().__init__(parent)
        self.host = host
        self.setObjectName("notificationDrawer")
        self.title = QLabel("Notifications", self)
        self.subtitle = QLabel(self)
        self.read_btn = IconButton("done_all", "Mark all as read", self)
        self.read_btn.clicked.connect(self.host.mark_all_read)
        self.clear_btn = IconButton("clear_all", "Clear history", self)
        self.clear_btn.clicked.connect(self.host.clear_history)
        self.close_btn = IconButton("close", "Close", self)
        self.close_btn.clicked.connect(lambda: self.host.set_drawer_open(False))
        self.chips: dict[str, QPushButton] = {}
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        for key in ("all", "errors", "warnings", "info"):
            chip = QPushButton(self)
            chip.setCheckable(True)
            chip.setFixedHeight(26)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, k=key: self.host.set_filter(k))
            self.chips[key] = chip
            chips_row.addWidget(chip)
        chips_row.addStretch(1)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search notifications")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.host.set_search)

        self.model = _RowsModel(self)
        self.list = QListView(self)
        self.list.setModel(self.model)
        self.list.setItemDelegate(_RowDelegate(self.list))
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(True)
        self.list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.clicked.connect(
            lambda index: self.host.select(index.data(Qt.ItemDataRole.UserRole)["id"])
        )
        self.empty = QLabel(self)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.details = _DetailsPage(host, self)
        details_scroll = QScrollArea(self)
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        details_scroll.setWidget(self.details)
        self.pages = QStackedWidget(self)
        self.pages.addWidget(self.list)
        self.pages.addWidget(self.empty)
        self.pages.addWidget(details_scroll)

        header = QHBoxLayout()
        header.setSpacing(4)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(self.title)
        title_col.addWidget(self.subtitle)
        header.addLayout(title_col, 1)
        header.addWidget(self.read_btn)
        header.addWidget(self.clear_btn)
        header.addWidget(self.close_btn)
        self.list_tools = QWidget(self)
        tools = QVBoxLayout(self.list_tools)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(8)
        tools.addLayout(chips_row)
        tools.addWidget(self.search)
        top = QVBoxLayout()
        top.setContentsMargins(16, 14, 12, 8)
        top.setSpacing(10)
        top.addLayout(header)
        top.addWidget(self.list_tools)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addWidget(self.pages, 1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(-4, 0)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def set_state(self, state: dict, tokens: ThemeTokens) -> None:
        """Render the drawer part of ``state``."""
        self.setVisible(state["drawerOpen"])
        if not state["drawerOpen"]:
            return
        self._style(tokens)
        unread = state["openCriticals"]
        self.subtitle.setText(
            f"{state['total']} in history" + (f" · {unread} critical open" if unread else "")
        )
        for item in state["filters"]:
            chip = self.chips[item["key"]]
            chip.setText(f"{item['label']}  {item['count']}")
            chip.setChecked(item["active"])
        if self.search.text() != state["search"]:
            self.search.blockSignals(True)
            self.search.setText(state["search"])
            self.search.blockSignals(False)
        self.model.set_rows(state["rows"])
        selected = state["selected"]
        self.list_tools.setVisible(selected is None)
        if selected is not None:
            self.details.set_row(selected, tokens)
            self.pages.setCurrentIndex(2)
        elif state["rows"]:
            self.pages.setCurrentIndex(0)
        else:
            if state["total"]:
                self.empty.setText("Nothing matches this filter.")
            else:
                self.empty.setText("You're all caught up.\nNew messages and errors appear here.")
            self.pages.setCurrentIndex(1)

    def _style(self, tokens: ThemeTokens) -> None:
        chip_qss = (
            f"QPushButton {{ background: transparent; color: {tokens.fg_muted.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 13px;"
            f" padding: 3px 10px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {tokens.hover.name()}; }}"
            f"QPushButton:checked {{ background: {rgba(tokens.primary, 0.18)};"
            f" color: {tokens.fg.name()}; border-color: {tokens.primary.name()};"
            f" font-weight: 600; }}"
        )
        self.setStyleSheet(
            f"QFrame#notificationDrawer {{ background: {tokens.bg.name()};"
            f" border-left: 1px solid {tokens.border.name()}; }}"
            f"QListView, QScrollArea, QStackedWidget, QScrollArea > QWidget > QWidget"
            f" {{ background: {tokens.bg.name()}; border: none; }}" + field_qss(tokens)
        )
        for chip in self.chips.values():
            chip.setStyleSheet(chip_qss)
        self.title.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 15px; font-weight: 600; background: none;"
        )
        self.subtitle.setStyleSheet(
            f"color: {tokens.fg_subtle.name()}; font-size: 11px; background: none;"
        )
        self.empty.setStyleSheet(
            f"color: {tokens.fg_subtle.name()}; font-size: 13px; background: none;"
        )
        for button in (self.read_btn, self.clear_btn, self.close_btn):
            button.refresh_theme(tokens)


class BellButton(QToolButton):
    """Status-bar bell with a badge counting unread notifications."""

    def __init__(self, host: NotificationHostBase, parent: QWidget | None = None):
        super().__init__(parent)
        self.host = host
        self._state: dict = {}
        self.setAutoRaise(True)
        self.setCheckable(True)
        self.setFixedSize(36, 24)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Notifications")
        self.clicked.connect(self.host.toggle_drawer)

    def set_state(self, state: dict, tokens: ThemeTokens) -> None:
        """Update icon, badge and tooltip."""
        self._state = state
        self.setChecked(state["drawerOpen"])
        color = state["bellColor"] if state["unread"] or state["openCriticals"] else tokens.fg_muted
        self.setIcon(
            material_icon(state["bellIcon"], size=(36, 36), color=color, convert_to_pixmap=False)
        )
        self.setToolTip(state["bellTip"])
        self.setStyleSheet(
            f"QToolButton {{ border: none; border-radius: 6px; background: transparent; }}"
            f"QToolButton:hover, QToolButton:checked {{ background: {tokens.hover.name()}; }}"
        )
        self.update()

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        unread = self._state.get("unread", 0)
        if not unread:
            return
        text = "99+" if unread > 99 else str(unread)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = self.font()
        font.setPixelSize(9)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        width = max(14, painter.fontMetrics().horizontalAdvance(text) + 8)
        rect = QRectF(self.width() - width - 1, 1, width, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._state["bellColor"]))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(QColor("white"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.end()


class NotificationHostQWidget(NotificationHostBase):
    """Notification UI drawn with QWidgets. See :class:`NotificationHostBase`."""

    def _create_views(self) -> None:
        self.toasts = ToastStack(self, self.window)
        self.drawer = HistoryDrawer(self, self.window)
        self.drawer.hide()
        self.toasts.hide()
        self.bell = BellButton(self)
        if self.status_bar is not None:
            self.status_bar.addPermanentWidget(self.bell)

    def _sync_views(self, state: dict) -> None:
        tokens = ThemeTokens()
        self.toasts.set_state(state, tokens)
        self.drawer.set_state(state, tokens)
        self.bell.set_state(state, tokens)

    def _place_views(self) -> None:
        if self.drawer.isVisible():
            self.drawer.setGeometry(self.drawer_geometry())
            self.drawer.raise_()
        if self.toasts.isVisible():
            # the stack has an 8 px margin for the shadow, so the cards line up with MARGIN
            width = self.toast_geometry(0).width() + 16
            layout = self.toasts.layout()
            height = (
                layout.totalHeightForWidth(width)
                if layout.hasHeightForWidth()
                else layout.totalSizeHint().height()
            )
            rect = self.toast_geometry(height - 16)
            self.toasts.setGeometry(rect.adjusted(-8, -8, 8, 8) & self.window.rect())
            self.toasts.raise_()

    def _destroy_views(self) -> None:
        for widget in (self.toasts, self.drawer, self.bell):
            widget.hide()
            widget.deleteLater()
