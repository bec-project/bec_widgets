"""Device and signal pickers whose popup is built from QWidgets.

Same behaviour as the QML pickers in :mod:`picker_qml`; both popups are views over
:class:`~bec_widgets.widgets.control.device_input.picker.picker_common.PickerController`.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QModelIndex, QRect, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap, QRegion
from qtpy.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import rgba
from bec_widgets.widgets.control.device_input.picker.picker_common import (
    DevicePickerBase,
    PickerPopupBase,
    SignalPickerBase,
)
from bec_widgets.widgets.control.device_input.picker.picker_model import PickerRowsModel

ROW_HEIGHT = 34
HEADER_HEIGHT = 28
EMPTY_HEIGHT = 96

_ICON_CACHE: dict[tuple[str, str, int], QPixmap] = {}


def cached_icon(name: str, color: QColor, size: int = 16) -> QPixmap:
    """Material icon pixmap, cached per name, colour and size."""
    key = (name, color.name(), size)
    pixmap = _ICON_CACHE.get(key)
    if pixmap is None:
        pixmap = material_icon(name, size=(size * 2, size * 2), color=color)
        pixmap.setDevicePixelRatio(2.0)
        _ICON_CACHE[key] = pixmap
    return pixmap


class PickerRowDelegate(QStyledItemDelegate):
    """Paints header, item and empty rows like ``PickerPopupView.qml``."""

    def __init__(self, popup: "PickerPopupWidget"):
        super().__init__(popup)
        self._popup = popup
        self.tokens = ThemeTokens()

    def _row(self, index: QModelIndex) -> dict:
        model = index.model()
        if isinstance(model, PickerRowsModel):
            return model.row(index.row())
        return {}

    def sizeHint(self, option, index):  # pylint: disable=invalid-name
        row_type = self._row(index).get("rowType")
        height = {"header": HEADER_HEIGHT, "empty": EMPTY_HEIGHT}.get(row_type, ROW_HEIGHT)
        return QSize(option.rect.width(), height)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        row = self._row(index)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        row_type = row.get("rowType")
        if row_type == "header":
            self._paint_header(painter, rect, row)
        elif row_type == "empty":
            self._paint_empty(painter, rect, row)
        else:
            highlighted = index.row() == self._popup.controller.highlight
            self._paint_item(painter, rect, row, highlighted)
        painter.restore()

    def _paint_header(self, painter: QPainter, rect: QRect, row: dict) -> None:
        tokens = self.tokens
        font = QFont(painter.font())
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
        painter.setFont(font)
        x = rect.left() + 12
        if row.get("icon"):
            painter.drawPixmap(
                x,
                rect.top() + (rect.height() - 14) // 2 + 2,
                cached_icon(row["icon"], tokens.fg_subtle, 14),
            )
            x += 20
        painter.setPen(tokens.fg_subtle)
        title = row.get("title", "").upper()
        text_rect = QRect(x, rect.top() + 4, rect.width() - x - 12, rect.height() - 4)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, title)
        width = QFontMetrics(font).horizontalAdvance(title)
        count = row.get("count") or 0
        if count:
            font.setWeight(QFont.Weight.Normal)
            painter.setFont(font)
            painter.drawText(
                text_rect.adjusted(width + 8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, str(count)
            )

    def _paint_empty(self, painter: QPainter, rect: QRect, row: dict) -> None:
        tokens = self.tokens
        icon = cached_icon(row.get("icon") or "search_off", tokens.fg_subtle, 24)
        painter.drawPixmap(rect.center().x() - 12, rect.top() + 18, icon)
        font = QFont(painter.font())
        font.setPixelSize(13)
        painter.setFont(font)
        painter.setPen(tokens.fg_muted)
        painter.drawText(
            rect.adjusted(12, 48, -12, -8),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            row.get("title", ""),
        )

    def _paint_item(self, painter: QPainter, rect: QRect, row: dict, highlighted: bool) -> None:
        tokens = self.tokens
        card = QRectF(rect.adjusted(4, 1, -4, -1))
        painter.setPen(Qt.PenStyle.NoPen)
        if highlighted:
            painter.setBrush(tokens.hover)
            painter.drawRoundedRect(card, 6, 6)
        if row.get("isCurrent"):
            painter.setBrush(tokens.primary)
            painter.drawRoundedRect(
                QRectF(card.left(), card.top() + 7, 3, card.height() - 14), 1.5, 1.5
            )
        left = int(card.left()) + 10
        if row.get("icon"):
            color = tokens.primary if row.get("isCurrent") else tokens.fg_muted
            painter.drawPixmap(
                left, rect.top() + (rect.height() - 16) // 2, cached_icon(row["icon"], color)
            )
        right = self._paint_badge(painter, rect, int(card.right()) - 8, row.get("badge") or "")
        self._paint_title(painter, rect, left + 24, right, row)

    def _paint_badge(self, painter: QPainter, rect: QRect, right: int, badge: str) -> int:
        """Paint the chip right-aligned at ``right``; return the x where the text must end."""
        if not badge:
            return right
        font = QFont(painter.font())
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Medium)
        width = QFontMetrics(font).horizontalAdvance(badge) + 14
        chip = QRectF(right - width, rect.top() + (rect.height() - 18) / 2, width, 18)
        tone = _badge_tone(self.tokens, badge)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.tokens.soft(tone, 0.18))
        painter.drawRoundedRect(chip, 9, 9)
        painter.setFont(font)
        painter.setPen(tone)
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, badge)
        return int(chip.left()) - 8

    def _paint_title(self, painter: QPainter, rect: QRect, left: int, right: int, row: dict):
        """Paint the title with the matched part highlighted, then the muted subtitle."""
        tokens = self.tokens
        font = QFont(painter.font())
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Medium if row.get("isCurrent") else QFont.Weight.Normal)
        bold = QFont(font)
        bold.setWeight(QFont.Weight.Bold)
        title = row.get("title", "")
        start, length = row.get("matchStart", -1), row.get("matchLength", 0)
        segments = [(title, font, tokens.fg)]
        if start >= 0 and length > 0:
            segments = [
                (title[:start], font, tokens.fg),
                (title[start : start + length], bold, tokens.primary),
                (title[start + length :], font, tokens.fg),
            ]
        cursor = left
        for text, segment_font, color in segments:
            if not text:
                continue
            metrics = QFontMetrics(segment_font)
            text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(0, right - cursor))
            painter.setFont(segment_font)
            painter.setPen(color)
            painter.drawText(
                QRect(cursor, rect.top(), max(0, right - cursor), rect.height()),
                Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            cursor += metrics.horizontalAdvance(text)
        subtitle = row.get("subtitle") or ""
        if not subtitle or cursor + 38 >= right:
            return
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Normal)
        cursor += 8
        painter.setFont(font)
        painter.setPen(tokens.fg_subtle)
        painter.drawText(
            QRect(cursor, rect.top(), right - cursor, rect.height()),
            Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(font).elidedText(subtitle, Qt.TextElideMode.ElideRight, right - cursor),
        )


def _badge_tone(tokens: ThemeTokens, badge: str) -> QColor:
    """Chip colour of a readout priority or signal kind badge."""
    return {
        "monitored": tokens.primary,
        "hinted": tokens.primary,
        "async": tokens.highlight,
        "baseline": tokens.fg_muted,
        "config": tokens.fg_muted,
        "on_request": tokens.warning,
        "continuous": tokens.success,
        "normal": tokens.success,
    }.get(badge, tokens.fg_muted)


class _SearchField(QLineEdit):
    """Search input that forwards navigation keys to the controller."""

    def __init__(self, popup: "PickerPopupWidget"):
        super().__init__(popup)
        self._popup = popup

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        controller = self._popup.controller
        key = event.key()
        if key == Qt.Key.Key_Down or (key == Qt.Key.Key_Tab and not event.modifiers()):
            controller.move_highlight(1)
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Backtab):
            controller.move_highlight(-1)
        elif key == Qt.Key.Key_PageDown:
            controller.page_highlight(1)
        elif key == Qt.Key.Key_PageUp:
            controller.page_highlight(-1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            controller.accept()
        elif key == Qt.Key.Key_Escape:
            controller.dismiss()
        else:
            super().keyPressEvent(event)


class PickerPopupWidget(PickerPopupBase):  # pylint: disable=too-many-instance-attributes
    """Popup with search field, grouped list and live-value footer, built from QWidgets."""

    def __init__(self, picker):
        super().__init__(picker)
        self.card = QFrame(self)
        self.card.setObjectName("pickerCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.card)
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(self._build_search())
        layout.addWidget(self._separator())
        layout.addWidget(self._build_list(), 1)
        layout.addWidget(self._separator())
        layout.addWidget(self._build_footer())

        self.search.textChanged.connect(self.controller.set_query)
        self.controller.rows_changed.connect(self._sync_rows)
        self.controller.highlight_changed.connect(self._sync_highlight)
        self.controller.detail_changed.connect(self._sync_detail)
        self.controller.query_changed.connect(self._sync_query)
        self.refresh_theme()
        self._sync_query()
        self._sync_rows()
        self._sync_highlight()

    def _build_search(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(12, 7, 12, 7)
        header.setSpacing(8)
        self.search_icon = QLabel(self.card)
        self.search = _SearchField(self)
        self.search.setObjectName("pickerSearch")
        self.search.setClearButtonEnabled(True)
        self.summary = QLabel(self.card)
        self.summary.setObjectName("pickerSummary")
        header.addWidget(self.search_icon)
        header.addWidget(self.search, 1)
        header.addWidget(self.summary)
        return header

    def _build_list(self) -> QListView:
        self.list = QListView(self.card)
        self.list.setObjectName("pickerList")
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setMouseTracking(True)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.viewport().installEventFilter(self)
        self.delegate = PickerRowDelegate(self)
        self.list.setItemDelegate(self.delegate)
        self.list.setModel(self.controller.model)
        self.list.clicked.connect(lambda index: self.controller.accept(index.row()))
        return self.list

    def _build_footer(self) -> QWidget:
        self.footer = QWidget(self.card)
        footer = QVBoxLayout(self.footer)
        footer.setContentsMargins(12, 8, 12, 8)
        footer.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.detail_icon = QLabel(self.footer)
        self.detail_title = QLabel(self.footer)
        self.detail_title.setObjectName("pickerDetailTitle")
        self.detail_value = QLabel(self.footer)
        self.detail_value.setObjectName("pickerDetailValue")
        self.detail_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.detail_icon)
        top.addWidget(self.detail_title, 1)
        top.addWidget(self.detail_value)
        footer.addLayout(top)
        self.detail_sub = QLabel(self.footer)
        self.detail_sub.setObjectName("pickerDetailSub")
        footer.addWidget(self.detail_sub)
        self.hints = QLabel("↑↓ move   ↵ select   esc close", self.footer)
        self.hints.setObjectName("pickerHints")
        footer.addWidget(self.hints)
        return self.footer

    def _separator(self) -> QFrame:
        line = QFrame(self.card)
        line.setObjectName("pickerSeparator")
        line.setFixedHeight(1)
        return line

    # ---- PickerPopupBase -----------------------------------------------------------------------

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.end(False)

    def refresh_theme(self) -> None:
        tokens = ThemeTokens()
        self.delegate.tokens = tokens
        self.search_icon.setPixmap(cached_icon("search", tokens.fg_muted, 18))
        self.setStyleSheet(f"""
            QFrame#pickerCard {{ background: {tokens.card.name()};
                border: 1px solid {tokens.border.name()}; border-radius: 10px; }}
            QFrame#pickerSeparator {{ background: {tokens.border.name()}; border: none; }}
            QLineEdit#pickerSearch {{ background: transparent; border: none; color: {tokens.fg.name()};
                font-size: 14px; padding: 0px; min-height: 32px; max-height: 32px;
                selection-background-color: {tokens.primary.name()}; }}
            QLabel {{ background: transparent; }}
            QLabel#pickerSummary {{ color: {tokens.fg_subtle.name()}; font-size: 12px; }}
            QLabel#pickerDetailTitle {{ color: {tokens.fg.name()}; font-size: 13px; font-weight: 600; }}
            QLabel#pickerDetailSub {{ color: {tokens.fg_muted.name()}; font-size: 12px; }}
            QLabel#pickerHints {{ color: {tokens.fg_subtle.name()}; font-size: 11px; padding-top: 4px; }}
            QListView#pickerList {{ background: transparent; border: none; outline: none; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {rgba(tokens.fg, 0.25)}; border-radius: 3px;
                min-height: 24px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
            QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
            """)
        self.search.setPlaceholderText(self.controller.placeholder)
        self._sync_detail()
        self.list.viewport().update()

    # ---- sync from the controller ----------------------------------------------------------------

    def _sync_query(self) -> None:
        if self.search.text() != self.controller.query:
            self.search.blockSignals(True)
            self.search.setText(self.controller.query)
            self.search.blockSignals(False)
        self.search.setPlaceholderText(self.controller.placeholder)

    def _sync_rows(self) -> None:
        self.summary.setText(self.controller.summary)
        self.list.viewport().update()

    def _sync_highlight(self) -> None:
        row = self.controller.highlight
        model = self.controller.model
        if row >= 0:
            # keep the section header of the highlighted row in view as well
            if row > 0 and model.row(row - 1).get("rowType") == "header":
                self.list.scrollTo(model.index(row - 1, 0))
            self.list.scrollTo(model.index(row, 0))
        self.list.viewport().update()

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        self.list.doItemsLayout()
        self._sync_highlight()

    def _sync_detail(self) -> None:
        detail = self.controller.detail
        tokens = self.delegate.tokens
        self.footer.setVisible(bool(detail))
        if not detail:
            return
        self.detail_icon.setPixmap(
            cached_icon(detail.get("icon") or "sensors", tokens.fg_muted, 16)
        )
        self.detail_title.setText(detail.get("title", ""))
        parts = [part for part in (detail.get("subtitle"), detail.get("details")) if part]
        self.detail_sub.setText(" · ".join(parts))
        self.detail_sub.setVisible(bool(parts))
        state = detail.get("valueState")
        if state == "live" and detail.get("value"):
            stamp = detail.get("valueTime")
            self.detail_value.setText(detail["value"] + (f"  ·  {stamp}" if stamp else ""))
            color = tokens.success
        elif state == "loading":
            self.detail_value.setText("reading…")
            color = tokens.fg_subtle
        else:
            self.detail_value.setText("no value yet")
            color = tokens.fg_subtle
        self.detail_value.setStyleSheet(
            f"color: {color.name()}; font-size: 12px; font-family: monospace; background: none;"
        )

    # ---- events -------------------------------------------------------------------------------

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if watched is self.list.viewport() and event.type() == QEvent.Type.MouseMove:
            index = self.list.indexAt(event.position().toPoint())
            if index.isValid():
                self.controller.set_highlight(index.row())
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))


class DevicePicker(DevicePickerBase):
    """Device combobox with a searchable, grouped popup built from QWidgets.

    Drop-in replacement for :class:`DeviceComboBox`; see :class:`DevicePickerBase`.
    """

    ICON_NAME = "manage_search"

    def _create_popup(self):
        return PickerPopupWidget(self)


class SignalPicker(SignalPickerBase):
    """Signal combobox with a searchable, grouped popup built from QWidgets.

    Drop-in replacement for :class:`SignalComboBox`; see :class:`SignalPickerBase`.
    """

    ICON_NAME = "manage_search"

    def _create_popup(self):
        return PickerPopupWidget(self)
