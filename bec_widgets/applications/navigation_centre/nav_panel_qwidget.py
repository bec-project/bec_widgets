"""QWidget rendering of the main app's navigation panel; see :mod:`.nav_common`."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
    QAbstractButton,
    QFrame,
    QScrollArea,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.applications.navigation_centre.nav_common import (
    HEADER_HEIGHT,
    ITEM_HEIGHT,
    SECTION_HEIGHT,
    SEPARATOR_HEIGHT,
    NavEntry,
    NavPanelBase,
)
from bec_widgets.utils.quick.host import ThemeTokens

_ICON_CACHE: dict[tuple, QPixmap] = {}
# focus rings only show for keyboard focus, like CSS :focus-visible
_KEYBOARD_REASONS = (
    Qt.FocusReason.TabFocusReason,
    Qt.FocusReason.BacktabFocusReason,
    Qt.FocusReason.ShortcutFocusReason,
)


def _icon(name: str, color: QColor, filled: bool, size: int) -> QPixmap:
    key = (name, color.name(), filled, size)
    pixmap = _ICON_CACHE.get(key)
    if pixmap is None:
        try:
            pixmap = material_icon(name, size=QSize(size * 2, size * 2), color=color, filled=filled)
        except Exception:  # pylint: disable=broad-except
            # not every symbol has a filled variant
            pixmap = material_icon(name, size=QSize(size * 2, size * 2), color=color)
        _ICON_CACHE[key] = pixmap
    return pixmap


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _with_alpha(color: QColor, alpha: float) -> QColor:
    out = QColor(color)
    out.setAlphaF(max(0.0, min(1.0, alpha)) * color.alphaF())
    return out


def _font(px: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setPixelSize(px)
    font.setWeight(weight)
    return font


def label_alpha(progress: float) -> float:
    """Opacity of the drawer texts: they appear in the second half of the animation."""
    return max(0.0, (progress - 0.35) / 0.65)


def mini_alpha(progress: float) -> float:
    """Opacity of the rail labels: they leave in the first half of the animation."""
    return max(0.0, 1.0 - progress * 2.0)


class _NavRow(QAbstractButton):
    """One painted row: item, action, section heading or separator."""

    def __init__(self, panel: "NavPanelQWidget", entry: NavEntry, parent: QWidget):
        super().__init__(parent)
        self.panel = panel
        self.entry = entry
        self._hover = False
        self.focus_visible = False
        height = {"section": SECTION_HEIGHT, "separator": SEPARATOR_HEIGHT}.get(
            entry.kind, ITEM_HEIGHT
        )
        self.setFixedHeight(height)
        self.setObjectName(f"NavRow_{entry.id}")
        if entry.focusable:
            self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.clicked.connect(lambda: self.panel.activate_from_user(self.entry.id))
        else:
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.setEnabled(False)
        self.sync()

    def sync(self) -> None:
        """Refresh accessible texts after the entry changed."""
        name = self.entry.title
        if self.entry.active:
            name = f"{name} (current view)"
        self.setAccessibleName(name)
        self.setAccessibleDescription(self.entry.subtitle)
        self.update()

    # --- events
    def enterEvent(self, event):  # pylint: disable=invalid-name
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip and self.entry.focusable:
            if self.panel.progress < 0.5:
                QToolTip.showText(event.globalPos(), self.panel.tooltip_for(self.entry), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)

    def focusInEvent(self, event):  # pylint: disable=invalid-name
        self.focus_visible = event.reason() in _KEYBOARD_REASONS
        super().focusInEvent(event)
        self.panel.surface_widget.ensure_visible(self)

    def focusOutEvent(self, event):  # pylint: disable=invalid-name
        self.focus_visible = False
        super().focusOutEvent(event)

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        key = event.key()
        steps = {
            Qt.Key.Key_Up: -1,
            Qt.Key.Key_Down: 1,
            Qt.Key.Key_Home: -(10**6),
            Qt.Key.Key_End: 10**6,
        }
        if key in steps:
            self.panel.focus_row(self.panel.move_focus(self.entry.id, steps[key]))
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
        elif key == Qt.Key.Key_Escape:
            self.panel.handle_escape()
        elif key == Qt.Key.Key_Right and not self.panel.is_expanded:
            self.panel.set_expanded(True)
        elif key == Qt.Key.Key_Left and self.panel.is_expanded and not self.panel.pinned:
            self.panel.set_expanded(False, restore_focus=False)
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            super().keyPressEvent(event)

    def sizeHint(self):  # pylint: disable=invalid-name
        return QSize(self.panel.rail_width, self.height())

    # --- painting
    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = self.panel.tokens
        p = self.panel.progress
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        kind = self.entry.kind
        if kind == "separator":
            painter.setPen(QPen(tokens.border, 1))
            painter.drawLine(10, self.height() // 2, self.width() - 10, self.height() // 2)
            return
        if kind == "section":
            self._paint_section(painter, tokens, p)
            return
        self._paint_item(painter, tokens, p)

    def _paint_section(self, painter: QPainter, tokens: ThemeTokens, p: float) -> None:
        mid = self.height() // 2
        rail = self.panel.rail_width
        painter.setPen(QPen(_with_alpha(tokens.border, 1.0 - p), 1))
        painter.drawLine(14, mid, rail - 14, mid)
        painter.setPen(_with_alpha(tokens.fg_subtle, label_alpha(p)))
        painter.setFont(_font(11, QFont.Weight.DemiBold))
        text_rect = QRectF(16, 0, self.panel.drawer_width - 32, self.height())
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.entry.title.upper(),
        )

    def _paint_item(self, painter: QPainter, tokens: ThemeTokens, p: float) -> None:
        entry = self.entry
        rail = self.panel.rail_width
        drawer = self.panel.drawer_width
        active = entry.active and entry.kind == "item"

        # highlight: a pill behind the icon in the rail, the whole row in the drawer
        pill = QRectF(
            8, _lerp(5, 2, p), _lerp(rail - 16, self.width() - 16, p), _lerp(28, ITEM_HEIGHT - 4, p)
        )
        radius = _lerp(14, 8, p)
        painter.setPen(Qt.PenStyle.NoPen)
        if active:
            painter.setBrush(tokens.primary)
            painter.drawRoundedRect(pill, radius, radius)
        elif self._hover or self.isDown():
            painter.setBrush(tokens.pressed if self.isDown() else tokens.hover)
            painter.drawRoundedRect(pill, radius, radius)
        if self.hasFocus() and self.focus_visible:
            ring = tokens.on_primary if active else tokens.primary
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ring, 2))
            painter.drawRoundedRect(pill.adjusted(1, 1, -1, -1), radius - 1, radius - 1)

        # icon
        icon_size = 22
        icon_color = tokens.on_primary if active else tokens.fg
        icon_y = _lerp(8, (ITEM_HEIGHT - icon_size) / 2, p)
        pixmap = _icon(entry.icon, icon_color, active, icon_size)
        painter.drawPixmap(
            QRectF((rail - icon_size) / 2, icon_y, icon_size, icon_size),
            pixmap,
            QRectF(pixmap.rect()),
        )

        # rail label under the icon
        alpha = mini_alpha(p)
        if alpha > 0:
            weight = QFont.Weight.DemiBold if active else QFont.Weight.Normal
            painter.setFont(_font(10, weight))
            painter.setPen(_with_alpha(tokens.fg if active else tokens.fg_muted, alpha))
            metrics = painter.fontMetrics()
            text = metrics.elidedText(entry.mini_text, Qt.TextElideMode.ElideRight, rail - 4)
            painter.drawText(QRectF(2, 35, rail - 4, 16), Qt.AlignmentFlag.AlignCenter, text)

        # drawer texts, laid out for the full drawer width so they never reflow
        alpha = label_alpha(p)
        if alpha <= 0:
            return
        text_color = tokens.on_primary if active else tokens.fg
        sub_color = _with_alpha(tokens.on_primary, 0.78) if active else tokens.fg_muted
        right = drawer - 16
        if entry.shortcut and (self._hover or (self.hasFocus() and self.focus_visible)):
            painter.setFont(_font(11))
            painter.setPen(_with_alpha(sub_color, alpha))
            short_w = painter.fontMetrics().horizontalAdvance(entry.shortcut)
            painter.drawText(
                QRectF(right - short_w, 0, short_w, ITEM_HEIGHT),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                entry.shortcut,
            )
            right -= short_w + 8
        left = rail
        width = right - left
        painter.setFont(_font(13, QFont.Weight.DemiBold if active else QFont.Weight.Medium))
        painter.setPen(_with_alpha(text_color, alpha))
        title = painter.fontMetrics().elidedText(entry.title, Qt.TextElideMode.ElideRight, width)
        if entry.subtitle:
            painter.drawText(
                QRectF(left, 9, width, 20),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )
            painter.setFont(_font(11))
            painter.setPen(_with_alpha(sub_color, alpha))
            sub = painter.fontMetrics().elidedText(
                entry.subtitle, Qt.TextElideMode.ElideRight, width
            )
            painter.drawText(
                QRectF(left, 28, width, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                sub,
            )
        else:
            painter.drawText(
                QRectF(left, 0, width, ITEM_HEIGHT),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )


class _HeaderButton(QToolButton):
    """Round icon button of the panel header (menu and pin)."""

    def __init__(self, parent: QWidget, size: int):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(22, 22))
        self._hover = False
        self.focus_visible = False

    def focusInEvent(self, event):  # pylint: disable=invalid-name
        self.focus_visible = event.reason() in _KEYBOARD_REASONS
        super().focusInEvent(event)

    def focusOutEvent(self, event):  # pylint: disable=invalid-name
        self.focus_visible = False
        super().focusOutEvent(event)

    def enterEvent(self, event):  # pylint: disable=invalid-name
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens() if not hasattr(self.parent(), "tokens") else self.parent().tokens
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.isDown() or self._hover or self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.pressed if self.isDown() or self.isChecked() else tokens.hover)
            painter.drawRoundedRect(rect, 8, 8)
        if self.hasFocus() and self.focus_visible:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(tokens.primary, 2))
            painter.drawRoundedRect(rect, 8, 8)
        size = self.iconSize()
        pixmap = self.icon().pixmap(size)
        painter.drawPixmap(
            int((self.width() - size.width()) / 2), int((self.height() - size.height()) / 2), pixmap
        )


class _NavHeader(QWidget):
    """Top row: menu button (always at the same place), drawer title and pin button."""

    def __init__(self, panel: "NavPanelQWidget", parent: QWidget):
        super().__init__(parent)
        self.panel = panel
        self.setFixedHeight(HEADER_HEIGHT)
        self.menu_button = _HeaderButton(self, 40)
        self.menu_button.setObjectName("NavMenuButton")
        self.menu_button.setAccessibleName("Navigation menu")
        self.menu_button.move(8, (HEADER_HEIGHT - 40) // 2)
        self.menu_button.clicked.connect(panel.toggle_expanded)
        self.pin_button = _HeaderButton(self, 32)
        self.pin_button.setObjectName("NavPinButton")
        self.pin_button.setCheckable(True)
        self.pin_button.setIconSize(QSize(18, 18))
        self.pin_button.setAccessibleName("Keep navigation open")
        self.pin_button.move(panel.drawer_width - 8 - 32, (HEADER_HEIGHT - 32) // 2)
        self.pin_button.clicked.connect(panel.set_pinned)

    @property
    def tokens(self) -> ThemeTokens:
        """Theme tokens of the panel."""
        return self.panel.tokens

    def sync(self) -> None:
        """Refresh icons, tooltips and the pin state."""
        tokens = self.panel.tokens
        opened = self.panel.progress > 0.5
        self.menu_button.setIcon(
            material_icon(
                "menu_open" if opened else "menu",
                size=QSize(44, 44),
                color=tokens.fg,
                convert_to_pixmap=False,
            )
        )
        self.menu_button.setToolTip(self.panel.toggle_tooltip())
        pinned = self.panel.pinned
        self.pin_button.setChecked(pinned)
        self.pin_button.setIcon(
            material_icon(
                "keep",
                size=QSize(36, 36),
                color=tokens.fg if pinned else tokens.fg_muted,
                filled=pinned,
                convert_to_pixmap=False,
            )
        )
        self.pin_button.setToolTip(
            "Unpin: close the panel after choosing a view"
            if pinned
            else "Pin: keep the panel open next to the views"
        )
        # the pin is only reachable while the drawer is open
        self.pin_button.setVisible(self.panel.progress > 0.0 and not self.panel.push_mode)
        self.pin_button.setFocusPolicy(
            Qt.FocusPolicy.TabFocus
            if opened and not self.panel.push_mode
            else Qt.FocusPolicy.NoFocus
        )
        self.update()

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        if event.key() == Qt.Key.Key_Escape:
            self.panel.handle_escape()
        elif event.key() == Qt.Key.Key_Down:
            self.panel.focus_row(self.panel.move_focus(None, 1))
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        p = self.panel.progress
        alpha = label_alpha(p)
        if alpha <= 0:
            return
        tokens = self.panel.tokens
        painter = QPainter(self)
        painter.setFont(_font(14, QFont.Weight.DemiBold))
        painter.setPen(_with_alpha(tokens.fg, alpha))
        painter.drawText(
            QRectF(60, 0, 120, HEADER_HEIGHT),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.panel.title,
        )


class _NavSurface(QFrame):
    """The floating surface: header, scrolling top rows and fixed bottom rows."""

    def __init__(self, panel: "NavPanelQWidget"):
        super().__init__(None)
        self.panel = panel
        self.setObjectName("NavPanelSurface")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 1, 6)
        layout.setSpacing(0)

        self.header = _NavHeader(panel, self)
        layout.addWidget(self.header)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("NavPanelScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll.viewport().setAutoFillBackground(False)
        self.top_box = QWidget()
        self.top_box.setAutoFillBackground(False)
        self.top_layout = QVBoxLayout(self.top_box)
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_layout.setSpacing(0)
        self.scroll.setWidget(self.top_box)
        layout.addWidget(self.scroll, 1)

        self.bottom_box = QWidget(self)
        self.bottom_layout = QVBoxLayout(self.bottom_box)
        self.bottom_layout.setContentsMargins(0, 6, 0, 0)
        self.bottom_layout.setSpacing(0)
        layout.addWidget(self.bottom_box)

        self.rows: dict[str, _NavRow] = {}
        for name, widget in (
            ("NavPanelScroll", self.scroll),
            ("NavPanelViewport", self.scroll.viewport()),
            ("NavPanelTop", self.top_box),
            ("NavPanelBottom", self.bottom_box),
        ):
            widget.setObjectName(name)
        self.setStyleSheet(
            "#NavPanelScroll, #NavPanelViewport, #NavPanelTop, #NavPanelBottom"
            " { background: transparent; border: none; }"
            "#NavPanelScroll QScrollBar:vertical { width: 6px; background: transparent; }"
        )

    @property
    def tokens(self) -> ThemeTokens:
        """Theme tokens of the panel."""
        return self.panel.tokens

    def rebuild(self) -> None:
        """Recreate the rows from the panel entries."""
        focused = next((rid for rid, row in self.rows.items() if row.hasFocus()), None)
        for row in self.rows.values():
            row.hide()
            row.deleteLater()
        self.rows = {}
        for layout in (self.top_layout, self.bottom_layout):
            while layout.count():
                layout.takeAt(0)
        for entry in self.panel.ordered_entries():
            box = self.top_box if entry.group == "top" else self.bottom_box
            row = _NavRow(self.panel, entry, box)
            (self.top_layout if entry.group == "top" else self.bottom_layout).addWidget(row)
            self.rows[entry.id] = row
        self.top_layout.addStretch(1)
        self.bottom_box.setVisible(self.bottom_layout.count() > 0)
        self.sync()
        if focused in self.rows:
            self.rows[focused].setFocus(Qt.FocusReason.OtherFocusReason)

    def sync(self) -> None:
        """Repaint everything for the current progress and state."""
        for row in self.rows.values():
            row.sync()
        self.header.sync()
        self.update()

    def ensure_visible(self, row: QWidget) -> None:
        """Scroll ``row`` into view when it sits in the scrolling area."""
        if row.parentWidget() is self.top_box:
            self.scroll.ensureWidgetVisible(row, 0, 4)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = self.tokens
        painter = QPainter(self)
        painter.fillRect(self.rect(), tokens.card)
        painter.setPen(QPen(tokens.border, 1))
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        if self.bottom_box.isVisible():
            y = self.bottom_box.y()
            painter.drawLine(10, y, self.width() - 11, y)


class NavPanelQWidget(NavPanelBase):
    """Navigation panel of the main app rendered with QWidgets."""

    def __init__(self, parent: QWidget | None = None, **kwargs):
        self.tokens = ThemeTokens()
        self.surface_widget: _NavSurface | None = None
        super().__init__(parent=parent, **kwargs)
        # legacy attribute: the button that expands and collapses the panel
        self.toggle = self.surface_widget.header.menu_button
        self.surface_widget.sync()

    def _create_surface(self) -> QWidget:
        self.surface_widget = _NavSurface(self)
        return self.surface_widget

    def _surface_entries_changed(self) -> None:
        self.surface_widget.rebuild()

    def _surface_state_changed(self) -> None:
        self.surface_widget.sync()

    def _surface_progress(self, progress: float) -> None:
        self.surface_widget.sync()

    def _surface_theme_changed(self) -> None:
        self.tokens = ThemeTokens()
        _ICON_CACHE.clear()
        self.surface_widget.sync()

    def focus_row(self, entry_id: str | None) -> None:
        entry_id = entry_id or self.move_focus(None, 1)
        row = self.surface_widget.rows.get(entry_id) if entry_id else None
        if row is not None:
            row.setFocus(Qt.FocusReason.TabFocusReason)

    def row_widget(self, entry_id: str) -> QWidget | None:
        """Return the row widget of ``entry_id``."""
        return self.surface_widget.rows.get(entry_id)

    def tour_target(self, entry_id: str):
        if entry_id == "toggle":
            return self.surface_widget.header.menu_button
        return lambda: (self.surface_widget.rows.get(entry_id) or self.surface, None)
