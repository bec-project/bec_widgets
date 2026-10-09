"""QWidget overlay of the tour guide, built from the ``ux_kit`` controls.

The overlay covers the window, paints the dimming, spotlight and "What's this?" outlines, and
shows one card at a time. It only draws the state handed to :meth:`TourOverlay.apply_state` and
reports clicks through :attr:`TourOverlay.triggered`; the logic lives in ``TourGuide``.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEasingCurve, QPoint, QRect, QRectF, QSize, Qt, QVariantAnimation, Signal
from qtpy.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygon
from qtpy.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.quick.tokens import ThemeTokens
from bec_widgets.utils.tour_guide.geometry import interaction_region, place_card, pointer_offset
from bec_widgets.utils.ux_kit import (
    Divider,
    IconButton,
    LinearProgress,
    StatusPill,
    TextButton,
    _ThemeFollower,
)

STATUS_TONES = {"new": "info", "in_progress": "warning", "done": "success"}
CARD_WIDTHS = {"step": 340, "welcome": 380, "hint": 330, "hub": 560, "done": 380, "whatsthis": 320}


def _label(text: str = "", size: int = 13, weight: QFont.Weight | None = None, wrap=True) -> QLabel:
    label = QLabel(text)
    font = QFont(label.font())
    font.setPixelSize(size)
    if weight is not None:
        font.setWeight(weight)
    label.setFont(font)
    label.setWordWrap(wrap)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _icon_tile(name: str, tokens: ThemeTokens, size: int = 36, tone: str = "primary") -> QLabel:
    tile = QLabel()
    tile.setFixedSize(size, size)
    tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tile.setPixmap(
        material_icon(
            name, size=(size - 14, size - 14), color=tokens.tone_text(tone), convert_to_pixmap=True
        )
    )
    tile.setStyleSheet(
        f"background: {tokens.tone_tint(tone).name(QColor.NameFormat.HexArgb)};"
        f" border-radius: {size // 4}px;"
    )
    return tile


class StepDots(QWidget):
    """Segmented progress: one bar per step, done steps filled."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._index = 0
        self._count = 1
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_progress(self, index: int, count: int) -> None:
        """Highlight steps up to ``index`` of ``count``."""
        self._index, self._count = index, max(1, count)
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Paint one rounded bar per step."""
        tokens = ThemeTokens.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gap = 4
        width = (self.width() - gap * (self._count - 1)) / self._count
        for i in range(self._count):
            color = tokens.primary if i <= self._index else tokens.track
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(i * (width + gap), 0, width, 6), 3, 3)
        painter.end()


class OverlayCard(_ThemeFollower, QFrame):
    """Surface of every overlay card; rebuilt from the state on each update."""

    triggered = Signal(str, str)

    def __init__(self, parent: QWidget, mode: str):
        super().__init__(parent)
        self.mode = mode
        self.setObjectName("tourCard")
        self.setFixedWidth(CARD_WIDTHS[mode])
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(10)
        self._state: dict = {}
        self.refresh_theme(ThemeTokens.current())
        self._follow_theme()

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        self.setStyleSheet(
            f"#tourCard {{ background: {tokens.card.name()}; border: 1px solid"
            f" {tokens.border.name()}; border-radius: {tokens.metrics['radiusLarge'] + 2}px; }}"
            f"#tourCard QLabel {{ color: {tokens.fg.name()}; background: transparent; }}"
            f'#tourCard QLabel[muted="true"] {{ color: {tokens.fg_muted.name()}; }}'
            f'#tourCard QLabel[caption="true"] {{ color: {tokens.primary.name()}; }}'
        )
        if self._state:
            self.set_state(self._state)

    def _emit(self, action: str, arg: str = "") -> None:
        self.triggered.emit(action, arg)

    def _clear(self) -> None:
        def clear(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget() is not None:
                    item.widget().hide()
                    item.widget().deleteLater()
                elif item.layout() is not None:
                    clear(item.layout())

        clear(self._layout)

    def _button(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, text, variant, action, arg="", icon="", compact=False
    ) -> TextButton:
        button = TextButton(text, variant, icon, compact=compact)
        button.clicked.connect(lambda: self._emit(action, arg))
        return button

    def _muted(self, text: str, size: int = 12) -> QLabel:
        label = _label(text, size)
        label.setProperty("muted", True)
        return label

    def _header(self, caption: str, close_tip: str = "Close") -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        label = _label(caption.upper(), 11, QFont.Weight.Bold, wrap=False)
        label.setProperty("caption", True)
        row.addWidget(label, 1)
        close = IconButton("close", close_tip, compact=True)
        close.clicked.connect(lambda: self._emit("close"))
        row.addWidget(close)
        return row

    def set_state(self, state: dict) -> None:
        """Rebuild the card for ``state``."""
        self._state = state
        self._clear()
        tokens = ThemeTokens.current()
        getattr(self, f"_build_{self.mode}")(state, tokens)
        self.style().unpolish(self)
        self.style().polish(self)

    def preferred_size(self) -> QSize:
        """Size of the card at its fixed width."""
        width = self.width()
        layout = self.layout()
        height = layout.totalHeightForWidth(width) if layout.hasHeightForWidth() else 0
        return QSize(width, max(height, layout.totalSizeHint().height()))

    # -- cards ---------------------------------------------------------------
    def _build_step(self, state: dict, tokens: ThemeTokens) -> None:
        self._layout.addLayout(
            self._header(state.get("tourTitle", ""), "Close tour (resume later)")
        )
        self._layout.addWidget(_label(state.get("title", ""), 16, QFont.Weight.DemiBold))
        self._layout.addWidget(_label(state.get("text", ""), 13))
        if state.get("hint"):
            hint = QFrame()
            hint.setStyleSheet(
                f"background: {tokens.tone_tint('primary').name(QColor.NameFormat.HexArgb)};"
                f" border-radius: {tokens.metrics['radiusSmall']}px;"
            )
            row = QHBoxLayout(hint)
            row.setContentsMargins(10, 8, 10, 8)
            icon = QLabel()
            icon.setPixmap(
                material_icon(
                    "touch_app", size=(18, 18), color=tokens.primary, convert_to_pixmap=True
                )
            )
            row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
            text = _label(f"Try it: {state['hint']}", 12)
            row.addWidget(text, 1)
            self._layout.addWidget(hint)
        index, count = state.get("index", 0), state.get("count", 1)
        dots = StepDots()
        dots.set_progress(index, count)
        self._layout.addSpacing(2)
        self._layout.addWidget(dots)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addWidget(self._muted(f"{index + 1} of {count}"))
        footer.addStretch(1)
        back = self._button("Back", "ghost", "back", compact=True)
        back.setEnabled(index > 0)
        footer.addWidget(back)
        last = index >= count - 1
        footer.addWidget(
            self._button("Finish" if last else "Next", "primary", "next", compact=True)
        )
        self._layout.addLayout(footer)

    def _tour_row(self, tour: dict, tokens: ThemeTokens, detailed: bool) -> QWidget:
        row = QFrame()
        row.setObjectName("tourRow")
        row.setStyleSheet(
            f"#tourRow {{ background: {tokens.sunken.name()}; border-radius:"
            f" {tokens.metrics['radiusSmall'] + 2}px; }}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(12)
        tone = STATUS_TONES[tour["status"]] if tour["status"] == "done" else "primary"
        layout.addWidget(_icon_tile(tour["icon"], tokens, 34, tone), 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(_label(tour["title"], 13, QFont.Weight.DemiBold))
        if detailed:
            text.addWidget(self._muted(tour["summary"], 12))
        meta = QHBoxLayout()
        meta.setSpacing(8)
        meta.addWidget(self._muted(f"{tour['steps']} steps · {tour['minutes']} min", 11))
        if detailed:
            meta.addWidget(
                StatusPill(text=tour["label"], tone=STATUS_TONES[tour["status"]], outlined=True)
            )
        meta.addStretch(1)
        text.addLayout(meta)
        if detailed and tour["status"] == "in_progress":
            progress_bar = LinearProgress(tone="warning", thickness=4)
            progress_bar.set_value(tour["progress"], animate=False)
            text.addWidget(progress_bar)
        layout.addLayout(text, 1)
        verb = {"new": "Start", "in_progress": "Resume", "done": "Replay"}[tour["status"]]
        action = "start" if tour["status"] == "done" else "resume"
        variant = "primary" if tour["status"] == "in_progress" else "neutral"
        layout.addWidget(
            self._button(verb, variant, action, tour["id"], compact=True),
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        return row

    def _build_welcome(self, state: dict, tokens: ThemeTokens) -> None:
        self._layout.addLayout(self._header("Welcome to BEC", "Close (show again next time)"))
        self._layout.addWidget(
            _label("New here? Let us show you around.", 16, QFont.Weight.DemiBold)
        )
        self._layout.addWidget(
            self._muted(
                "Short tours of a minute or two, one task each. Pick one now, or find them later"
                " under Help (F1).",
                12,
            )
        )
        for tour in state.get("tours", [])[:4]:
            self._layout.addWidget(self._tour_row(tour, tokens, detailed=False))
        footer = QHBoxLayout()
        footer.addWidget(self._button("Don't show again", "ghost", "never", compact=True))
        footer.addStretch(1)
        footer.addWidget(self._button("Later", "neutral", "close", compact=True))
        first = next((t for t in state.get("tours", []) if t["status"] != "done"), None)
        if first:
            footer.addWidget(
                self._button("Show me around", "primary", "resume", first["id"], compact=True)
            )
        self._layout.addLayout(footer)

    def _build_hint(self, state: dict, tokens: ThemeTokens) -> None:
        tour = state.get("tour") or {}
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(
            _icon_tile(tour.get("icon", "explore"), tokens, 36), 0, Qt.AlignmentFlag.AlignTop
        )
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(_label(f"New here? {tour.get('title', '')}", 13, QFont.Weight.DemiBold))
        text.addWidget(
            self._muted(
                f"A {tour.get('steps', 0)}-step tour of this view,"
                f" about {tour.get('minutes', 1)} min.",
                12,
            )
        )
        row.addLayout(text, 1)
        close = IconButton("close", "Not now", compact=True)
        close.clicked.connect(lambda: self._emit("close"))
        row.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(row)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self._button("Not now", "ghost", "close", compact=True))
        footer.addWidget(
            self._button("Start tour", "primary", "start", tour.get("id", ""), compact=True)
        )
        self._layout.addLayout(footer)

    def _build_hub(self, state: dict, tokens: ThemeTokens) -> None:
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(_icon_tile("school", tokens, 40), 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(_label("Tours", 20, QFont.Weight.DemiBold))
        titles.addWidget(
            self._muted("Short guided tours, one task each. Your progress is saved.", 12)
        )
        head.addLayout(titles, 1)
        close = IconButton("close", "Close", compact=True)
        close.clicked.connect(lambda: self._emit("close"))
        head.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(head)
        done, total = state.get("done", 0), max(1, state.get("total", 1))
        progress = QHBoxLayout()
        progress_bar = LinearProgress(tone="success", thickness=6)
        progress_bar.set_value(done / total, animate=False)
        progress.addWidget(progress_bar, 1)
        progress.addWidget(self._muted(f"{done} of {state.get('total', 0)} done", 12))
        self._layout.addLayout(progress)
        for tour in state.get("tours", []):
            self._layout.addWidget(self._tour_row(tour, tokens, detailed=True))
        self._layout.addWidget(Divider())
        footer = QHBoxLayout()
        footer.addWidget(
            self._button(
                "What's this?  Shift+F1", "neutral", "whatsthis", icon="help_center", compact=True
            )
        )
        footer.addStretch(1)
        footer.addWidget(self._button("Reset progress", "ghost", "reset", compact=True))
        self._layout.addLayout(footer)

    def _build_done(self, state: dict, tokens: ThemeTokens) -> None:
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(
            _icon_tile("check_circle", tokens, 40, "success"), 0, Qt.AlignmentFlag.AlignTop
        )
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(_label("Tour complete", 16, QFont.Weight.DemiBold))
        titles.addWidget(self._muted(f"You finished “{state.get('finished', '')}”.", 12))
        head.addLayout(titles, 1)
        self._layout.addLayout(head)
        following = state.get("next")
        footer = QHBoxLayout()
        if following:
            self._layout.addWidget(Divider())
            self._layout.addWidget(self._muted("UP NEXT", 11))
            self._layout.addWidget(
                _label(
                    f"{following['title']} · {following['steps']} steps", 13, QFont.Weight.Medium
                )
            )
        footer.addWidget(self._button("All tours", "ghost", "hub", compact=True))
        footer.addStretch(1)
        footer.addWidget(self._button("Close", "neutral", "close", compact=True))
        if following:
            footer.addWidget(
                self._button("Start next", "primary", "resume", following["id"], compact=True)
            )
        self._layout.addLayout(footer)

    def _build_whatsthis(self, state: dict, tokens: ThemeTokens) -> None:
        anchors, selected = state.get("anchors", []), state.get("selected", -1)
        if not 0 <= selected < len(anchors):
            row = QHBoxLayout()
            row.setSpacing(10)
            icon = QLabel()
            icon.setPixmap(
                material_icon(
                    "help_center", size=(20, 20), color=tokens.primary, convert_to_pixmap=True
                )
            )
            row.addWidget(icon)
            row.addWidget(
                _label(f"What's this? Click any outlined control ({len(anchors)} on screen).", 13),
                1,
            )
            row.addWidget(self._button("Done", "neutral", "close", compact=True))
            self._layout.addLayout(row)
            return
        anchor = anchors[selected]
        self._layout.addLayout(self._header("What's this?", "Leave What's this"))
        self._layout.addWidget(_label(anchor["title"], 15, QFont.Weight.DemiBold))
        self._layout.addWidget(_label(anchor["text"], 13))
        if anchor.get("tour_id"):
            footer = QHBoxLayout()
            footer.addWidget(self._muted(f"Part of “{anchor['tour_title']}”", 12), 1)
            footer.addWidget(
                self._button("Take the tour", "primary", "resume", anchor["tour_id"], compact=True)
            )
            self._layout.addLayout(footer)


class TourOverlay(QWidget):
    """Full-window overlay drawing the tour guide state with QWidgets.

    Signals:
        triggered(str, str): An action (``next``, ``back``, ``close``, ``start``, ``resume``,
            ``hub``, ``never``, ``whatsthis``, ``reset`` or ``anchor``) and its argument.
    """

    triggered = Signal(str, str)

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setObjectName("tourOverlay")
        self._state: dict = {"mode": "hidden"}
        self._spot = QRect()
        self._side = "center"
        self._cards = {mode: OverlayCard(self, mode) for mode in CARD_WIDTHS}
        for card in self._cards.values():
            card.triggered.connect(self.triggered)
            card.hide()
        self._spot_animation = QVariantAnimation(self)
        self._spot_animation.setDuration(220)
        self._spot_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._spot_animation.valueChanged.connect(self._on_spot_animated)
        self.setGeometry(window.rect())
        self.hide()

    @property
    def card(self) -> OverlayCard | None:
        """The visible card."""
        card = self._cards.get(self._state.get("mode", "hidden"))
        return card if card is not None and card.isVisible() else None

    def apply_state(self, state: dict) -> None:
        """Draw ``state`` (see ``TourGuide.state``)."""
        mode = state.get("mode", "hidden")
        previous_mode = self._state.get("mode")
        self._state = state
        self._spot_animation.stop()
        if mode == "hidden":
            for card in self._cards.values():
                card.hide()
            self.hide()
            return
        self.setGeometry(self.parentWidget().rect())
        for name, card in self._cards.items():
            if name != mode:
                card.hide()
        card = self._cards[mode]
        # rebuild hidden: widgets added to a visible parent are only shown later, so they would be
        # missing from the size hint
        card.hide()
        card.set_state(state)
        spot = state.get("spot") or QRect()
        if mode == "step" and previous_mode == "step" and self._spot.isValid() and spot.isValid():
            self._spot_animation.setStartValue(QRect(self._spot))
            self._spot_animation.setEndValue(QRect(spot))
            self._spot_animation.start()
        else:
            self._spot = QRect(spot)
        self._layout_card(spot if spot.isValid() else None)
        card.show()
        self.show()
        self.raise_()
        self._update_mask()
        self.update()

    def _anchor_for_card(self, spot: QRect | None) -> QRect | None:
        mode = self._state.get("mode")
        if mode in ("welcome", "hint"):
            return self._state.get("anchor")
        if mode in ("hub", "done"):
            return None
        if mode == "whatsthis" and spot is None:
            return None
        return spot

    def _layout_card(self, spot: QRect | None) -> None:
        mode = self._state.get("mode")
        card = self._cards[mode]
        size = card.preferred_size()
        bounds = self.rect()
        if mode == "whatsthis" and spot is None:
            position, side = QPoint((bounds.width() - size.width()) // 2, 18), "center"
        else:
            anchor = self._anchor_for_card(spot)
            position, side = place_card(anchor, size, bounds)
            if mode in ("welcome", "hint") and anchor is None:
                position, side = (
                    QPoint(
                        bounds.right() - size.width() - 18, bounds.bottom() - size.height() - 40
                    ),
                    "corner",
                )
        self._side = side
        card.setGeometry(QRect(position, size))

    def _on_spot_animated(self, value) -> None:
        self._spot = QRect(value)
        self._update_mask()
        self.update()

    def _update_mask(self) -> None:
        mode = self._state.get("mode", "hidden")
        card = self._cards.get(mode)
        cards = [card.geometry()] if card is not None else []
        anchor = self._state.get("anchor")
        if mode in ("welcome", "hint"):
            # leave room for the pointer and the ring around the help button
            cards = [rect.adjusted(-12, -12, 12, 12) for rect in cards]
            if anchor is not None:
                cards.append(anchor.adjusted(-8, -8, 8, 8))
        spot = self._spot if self._spot.isValid() else None
        self.setMask(interaction_region(mode, self.rect(), spot, cards))

    # -- painting --------------------------------------------------------------
    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Paint the dimming, the spotlight ring, the What's this outlines and the pointer."""
        mode = self._state.get("mode", "hidden")
        tokens = ThemeTokens.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dim = {"step": 0.55, "hub": 0.5, "done": 0.5, "whatsthis": 0.28}.get(mode)
        spot = self._spot if self._spot.isValid() else None
        if dim is not None:
            path = QPainterPath()
            path.addRect(QRectF(self.rect()))
            if spot is not None and mode in ("step", "whatsthis"):
                hole = QPainterPath()
                hole.addRoundedRect(QRectF(spot), 10, 10)
                path = path.subtracted(hole)
            painter.fillPath(path, QColor(0, 0, 0, int(dim * 255)))
        if mode == "whatsthis":
            pen = QPen(tokens.primary, 1.5, Qt.PenStyle.DashLine)
            for index, anchor in enumerate(self._state.get("anchors", [])):
                if index == self._state.get("selected", -1):
                    continue
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(QRectF(anchor["rect"]).adjusted(1, 1, -1, -1), 6, 6)
                self._paint_marker(painter, anchor["rect"], tokens)
        if spot is not None and mode in ("step", "whatsthis"):
            self._paint_ring(painter, QRectF(spot), tokens)
        anchor = self._state.get("anchor")
        if mode in ("welcome", "hint") and anchor is not None:
            self._paint_ring(painter, QRectF(anchor.adjusted(-4, -4, 4, 4)), tokens)
        card = self.card
        if card is not None and self._side in ("right", "left", "below", "above"):
            self._paint_pointer(painter, card.geometry(), tokens)
        painter.end()

    def _paint_ring(self, painter: QPainter, rect: QRectF, tokens: ThemeTokens) -> None:
        glow = QColor(tokens.primary)
        for width, alpha in ((10, 40), (6, 70)):
            glow.setAlpha(alpha)
            painter.setPen(QPen(glow, width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(QPen(tokens.primary, 2))
        painter.drawRoundedRect(rect, 10, 10)

    def _paint_marker(self, painter: QPainter, rect: QRect, tokens: ThemeTokens) -> None:
        center = QPoint(rect.right() - 2, rect.top() + 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(tokens.primary)
        painter.drawEllipse(center, 7, 7)
        painter.setPen(tokens.on_primary)
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRect(center.x() - 7, center.y() - 7, 14, 14), Qt.AlignmentFlag.AlignCenter, "?"
        )

    def _paint_pointer(self, painter: QPainter, card: QRect, tokens: ThemeTokens) -> None:
        mode = self._state.get("mode")
        target = self._state.get("anchor") if mode in ("welcome", "hint") else self._spot
        offset = pointer_offset(target, card, self._side)
        size = 8
        if self._side == "right":
            tip, base = QPoint(card.left() - size, card.top() + offset), card.left() + 1
            points = [tip, QPoint(base, tip.y() - size), QPoint(base, tip.y() + size)]
        elif self._side == "left":
            tip, base = QPoint(card.right() + size + 1, card.top() + offset), card.right()
            points = [tip, QPoint(base, tip.y() - size), QPoint(base, tip.y() + size)]
        elif self._side == "below":
            tip, base = QPoint(card.left() + offset, card.top() - size), card.top() + 1
            points = [tip, QPoint(tip.x() - size, base), QPoint(tip.x() + size, base)]
        else:
            tip, base = QPoint(card.left() + offset, card.bottom() + size + 1), card.bottom()
            points = [tip, QPoint(tip.x() - size, base), QPoint(tip.x() + size, base)]
        painter.setPen(QPen(tokens.border, 1))
        painter.setBrush(tokens.card)
        painter.drawPolygon(QPolygon(points))

    # -- input -----------------------------------------------------------------
    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        """Route clicks outside the card: pick an anchor, open the tour list or close."""
        mode = self._state.get("mode")
        pos = event.position().toPoint()
        if mode == "whatsthis":
            for index, anchor in enumerate(self._state.get("anchors", [])):
                if anchor["rect"].contains(pos):
                    self.triggered.emit("anchor", str(index))
                    return
            self.triggered.emit("anchor", "-1")
            return
        if mode in ("welcome", "hint"):
            anchor = self._state.get("anchor")
            if anchor is not None and anchor.adjusted(-6, -6, 6, 6).contains(pos):
                self.triggered.emit("hub", "")
            return
        if mode in ("hub", "done"):
            card = self.card
            if card is None or not card.geometry().contains(pos):
                self.triggered.emit("close", "")
        event.accept()

    def cleanup(self) -> None:
        """Stop animations."""
        self._spot_animation.stop()
