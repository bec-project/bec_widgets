"""QML overlay of the tour guide, built from the ``BecUi`` controls.

Same look and behaviour as :mod:`overlay_qwidget`: the guide hands over a state, the QML scene
draws it and reports clicks. Card placement and the click-through region use the same functions
from :mod:`geometry` as the QWidget overlay.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, QRect, QSize, Qt, Signal, Slot
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils.quick import create_quick_widget, release_quick_widget
from bec_widgets.utils.tour_guide.geometry import interaction_region, place_card, pointer_offset

QML_FILE = Path(__file__).parent / "qml" / "TourOverlay.qml"


def _rect(rect: QRect | None) -> dict | None:
    if rect is None or not rect.isValid():
        return None
    return {"x": rect.x(), "y": rect.y(), "w": rect.width(), "h": rect.height()}


def to_qml_state(state: dict) -> dict:
    """Convert a guide state to plain QML values (rectangles become ``{x, y, w, h}``)."""
    converted = {}
    for key, value in state.items():
        if isinstance(value, QRect):
            converted[key] = _rect(value)
        elif key == "anchors":
            converted[key] = [{**anchor, "rect": _rect(anchor["rect"])} for anchor in value]
        else:
            converted[key] = value
    return converted


class TourOverlayBackend(QObject):
    """Bridge between the QML scene and the guide."""

    stateChanged = Signal()
    triggered = Signal(str, str)
    cardChanged = Signal()

    def __init__(self, overlay: QmlTourOverlay):
        super().__init__(overlay)
        self._overlay = overlay
        self._state: dict = {"mode": "hidden"}
        self._raw: dict = {"mode": "hidden"}
        self._card = QRect()

    @Property("QVariantMap", notify=stateChanged)
    def state(self) -> dict:  # pylint: disable=missing-function-docstring
        return self._state

    def set_state(self, state: dict) -> None:
        """Hand a new guide state to the scene."""
        self._raw = state
        self._state = to_qml_state(state)
        self.stateChanged.emit()

    @Slot(str, str)
    def trigger(self, action: str, arg: str = "") -> None:
        """Called from QML when the user clicks something."""
        self.triggered.emit(action, arg)

    @Slot(str, int, int, result="QVariantMap")
    def place(self, mode: str, width: int, height: int) -> dict:
        """Card position for ``mode`` at the given size, with the side and pointer offset."""
        bounds = self._overlay.rect()
        size = QSize(width, height)
        if mode in ("welcome", "hint"):
            anchor = self._raw.get("anchor")
            if anchor is None:
                return {
                    "x": bounds.right() - width - 18,
                    "y": bounds.bottom() - height - 40,
                    "side": "corner",
                    "pointer": 0,
                }
        elif mode in ("hub", "done"):
            anchor = None
        else:
            anchor = self._raw.get("spot")
            if mode == "whatsthis" and anchor is None:
                return {"x": (bounds.width() - width) // 2, "y": 18, "side": "center", "pointer": 0}
        position, side = place_card(anchor, size, bounds)
        offset = pointer_offset(anchor, QRect(position, size), side)
        return {"x": position.x(), "y": position.y(), "side": side, "pointer": offset}

    # pylint: disable=invalid-name
    @Slot(int, int, int, int)
    def setCardRect(self, x: int, y: int, width: int, height: int) -> None:
        """QML reports where the card ended up, for the click-through mask."""
        self._card = QRect(x, y, width, height)
        self._overlay.update_mask()

    @property
    def card_rect(self) -> QRect:
        """Last card rectangle reported by QML."""
        return self._card

    @property
    def raw_state(self) -> dict:
        """The state as the guide sent it."""
        return self._raw


class QmlTourOverlay(QWidget):
    """Full-window overlay drawing the tour guide state with QML.

    Signals:
        triggered(str, str): Same actions as the QWidget overlay.
    """

    triggered = Signal(str, str)

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.backend = TourOverlayBackend(self)
        self.backend.triggered.connect(self.triggered)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self, QML_FILE, properties={"backend": self.backend}, background="transparent"
        )
        self.view.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout.addWidget(self.view)
        self.setGeometry(window.rect())
        self.hide()

    def apply_state(self, state: dict) -> None:
        """Draw ``state`` (see ``TourGuide.state``)."""
        mode = state.get("mode", "hidden")
        if mode == "hidden":
            self.backend.set_state(state)
            self.hide()
            return
        self.setGeometry(self.parentWidget().rect())
        self.backend.set_state(state)
        self.show()
        self.raise_()
        self.update_mask()

    def update_mask(self) -> None:
        """Let clicks through where the guide wants the app to stay usable."""
        state = self.backend.raw_state
        mode = state.get("mode", "hidden")
        cards = [self.backend.card_rect] if self.backend.card_rect.isValid() else []
        if mode in ("welcome", "hint"):
            cards = [rect.adjusted(-12, -12, 12, 12) for rect in cards]
            anchor = state.get("anchor")
            if anchor is not None:
                cards.append(anchor.adjusted(-8, -8, 8, 8))
        self.setMask(interaction_region(mode, self.rect(), state.get("spot"), cards))

    def cleanup(self) -> None:
        """Unload the scene."""
        release_quick_widget(self.view)
