"""Geometry shared by the QML and QWidget overlays: targets, card placement and click-through."""

from __future__ import annotations

from qtpy.QtCore import QPoint, QRect, QSize
from qtpy.QtGui import QAction, QRegion
from qtpy.QtWidgets import QAbstractButton, QMenu, QMenuBar, QToolBar, QWidget

#: Space between the spotlight and the card, and between the card and the window edge.
GAP = 14
MARGIN = 16
#: Padding of the spotlight around its target.
SPOT_PADDING = 6


def resolve_target(target: object) -> object:
    """Unwrap callables and toolbar actions until a widget, action or rectangle is left."""
    for _ in range(3):
        if target is None or isinstance(target, (QWidget, QAction, QRect)):
            return target
        if hasattr(target, "get_toolbar_button") and callable(target.get_toolbar_button):
            target = target.get_toolbar_button()
            continue
        if hasattr(target, "action") and isinstance(getattr(target, "action"), QAction):
            target = target.action
            continue
        if callable(target):
            target = target()
            if isinstance(target, tuple):  # GuidedTour-style (target, text) callables
                target = target[0]
            continue
        return None
    return target


def _action_rect(action: QAction, window: QWidget) -> QRect | None:
    for toolbar in window.findChildren(QToolBar):
        button = toolbar.widgetForAction(action)
        if button is not None and button.isVisible():
            return QRect(button.mapTo(window, QPoint(0, 0)), button.size())
    for button in window.findChildren(QAbstractButton):
        if getattr(button, "defaultAction", lambda: None)() is action and button.isVisible():
            return QRect(button.mapTo(window, QPoint(0, 0)), button.size())
    bars: list[QWidget] = list(window.findChildren(QMenuBar)) + list(window.findChildren(QMenu))
    for menu in bars:
        if menu.isVisible() and action in menu.actions():
            geometry = menu.actionGeometry(action)
            return QRect(menu.mapTo(window, geometry.topLeft()), geometry.size())
    return None


def target_rect(target: object, window: QWidget) -> QRect | None:
    """Rectangle of ``target`` in ``window`` coordinates, or None if it is not on screen.

    Args:
        target(object): Widget, action, rectangle, toolbar action or a callable returning one.
        window(QWidget): The window the overlay covers.

    Returns:
        QRect | None: The visible rectangle, clipped to the window.
    """
    target = resolve_target(target)
    rect: QRect | None = None
    if isinstance(target, QRect):
        rect = QRect(target)
    elif isinstance(target, QAction):
        rect = _action_rect(target, window)
    elif isinstance(target, QWidget):
        if not target.isVisible() or target.window() is not window.window():
            return None
        rect = QRect(target.mapTo(window, QPoint(0, 0)), target.size())
    if rect is None or not rect.isValid():
        return None
    rect = rect.intersected(window.rect())
    return rect if rect.width() > 2 and rect.height() > 2 else None


def spotlight(rect: QRect, bounds: QRect, padding: int = SPOT_PADDING) -> QRect:
    """Grow ``rect`` by the spotlight padding, staying inside ``bounds``."""
    return rect.adjusted(-padding, -padding, padding, padding).intersected(bounds)


def place_card(spot: QRect | None, card: QSize, bounds: QRect) -> tuple[QPoint, str]:
    """Place a card next to the spotlight without covering it.

    Tries right, left, below and above the spotlight, in that order, then falls back to the
    bottom-right corner. Without a spotlight the card is centred.

    Args:
        spot(QRect | None): Spotlight rectangle.
        card(QSize): Size of the card.
        bounds(QRect): Area the card must stay inside.

    Returns:
        tuple[QPoint, str]: Top-left of the card and the side of the spotlight it sits on
        (``"right"``, ``"left"``, ``"below"``, ``"above"``, ``"center"`` or ``"corner"``). The
        side tells the card where to draw its pointer.
    """
    width, height = card.width(), card.height()
    if spot is None or not spot.isValid():
        center = bounds.center()
        return QPoint(center.x() - width // 2, center.y() - height // 2), "center"

    def clamp_y(y: int) -> int:
        return max(bounds.top() + MARGIN, min(y, bounds.bottom() - MARGIN - height))

    def clamp_x(x: int) -> int:
        return max(bounds.left() + MARGIN, min(x, bounds.right() - MARGIN - width))

    middle_y = spot.center().y() - height // 2
    middle_x = spot.center().x() - width // 2
    candidates = [
        ("right", spot.right() + GAP, clamp_y(middle_y)),
        ("left", spot.left() - GAP - width, clamp_y(middle_y)),
        ("below", clamp_x(middle_x), spot.bottom() + GAP),
        ("above", clamp_x(middle_x), spot.top() - GAP - height),
    ]
    inner = bounds.adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)
    for side, x, y in candidates:
        rect = QRect(x, y, width, height)
        if inner.contains(rect) and not rect.intersects(spot):
            return QPoint(x, y), side
    x = bounds.right() - MARGIN - width
    y = bounds.bottom() - MARGIN - height
    return QPoint(x, y), "corner"


def pointer_offset(spot: QRect | None, card: QRect, side: str) -> int:
    """Position of the card's pointer along the edge facing the spotlight, in card coordinates."""
    if spot is None:
        return 0
    if side in ("right", "left"):
        return max(18, min(spot.center().y() - card.top(), card.height() - 18))
    if side in ("below", "above"):
        return max(18, min(spot.center().x() - card.left(), card.width() - 18))
    return 0


#: Modes in which the overlay takes all clicks except the spotlight.
BLOCKING_MODES = ("step", "hub", "done", "whatsthis")


def interaction_region(mode: str, bounds: QRect, spot: QRect | None, cards: list[QRect]) -> QRegion:
    """Region of the overlay that receives mouse input.

    ``welcome`` and ``hint`` only take clicks on their card, so the app stays usable. In a step
    the spotlight is cut out, so the highlighted control can be tried while the tour runs.

    Args:
        mode(str): Overlay mode.
        bounds(QRect): Overlay rectangle.
        spot(QRect | None): Spotlight rectangle of the current step.
        cards(list[QRect]): Rectangles of the cards on screen.

    Returns:
        QRegion: Region to pass to ``QWidget.setMask``.
    """
    if mode in BLOCKING_MODES:
        region = QRegion(bounds)
        if mode == "step" and spot is not None:
            region = region.subtracted(QRegion(spot))
            for card in cards:
                region = region.united(QRegion(card))
        return region
    region = QRegion()
    for card in cards:
        region = region.united(QRegion(card))
    if region.isEmpty():
        # an empty mask means "no mask" to Qt, which would block the whole window
        region = QRegion(QRect(0, 0, 1, 1))
    return region
