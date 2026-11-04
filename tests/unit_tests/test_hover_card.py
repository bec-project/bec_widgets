# pylint: disable=missing-function-docstring, missing-module-docstring
import pytest
from qtpy.QtCore import QEvent, QPoint
from qtpy.QtGui import QGuiApplication
from qtpy.QtWidgets import QApplication, QLabel, QWidget

from bec_widgets.utils.hover_card import HoverCard


@pytest.fixture
def owner(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    yield widget


def _card(owner, **kwargs):
    label = QLabel("Some help that explains what this section is for")
    return HoverCard(owner, label, **kwargs)


def _frame(card):
    return card.card.geometry().translated(card.pos())


def test_show_near_places_the_frame_below_right_of_the_point(owner):
    card = _card(owner)
    area = QGuiApplication.primaryScreen().availableGeometry()
    point = area.topLeft() + QPoint(50, 50)
    card.show_near(point)
    assert card.isVisible()
    frame = _frame(card)
    assert (frame.left(), frame.top()) == (point.x() + 12, point.y() + 16)
    card.hide()


def test_show_near_flips_at_the_screen_edge_and_stays_on_screen(owner):
    card = _card(owner)
    area = QGuiApplication.primaryScreen().availableGeometry()
    corner = area.bottomRight() - QPoint(5, 5)
    card.show_near(corner)
    frame = _frame(card)
    assert frame.right() < corner.x() and frame.bottom() < corner.y()  # flipped to up-left
    assert area.contains(card.geometry())
    card.hide()


def test_show_near_custom_offset(owner):
    card = _card(owner)
    area = QGuiApplication.primaryScreen().availableGeometry()
    point = area.topLeft() + QPoint(40, 40)
    card.show_near(point, QPoint(0, 30))
    frame = _frame(card)
    assert (frame.left(), frame.top()) == (point.x(), point.y() + 30)
    card.hide()


def test_hide_on_leave_only_when_asked(owner):
    area = QGuiApplication.primaryScreen().availableGeometry()
    sticky, tooltip = _card(owner), _card(owner, hide_on_leave=True)
    for card in (sticky, tooltip):
        card.show_near(area.topLeft() + QPoint(30, 30))
        QApplication.sendEvent(card, QEvent(QEvent.Type.Leave))
    assert sticky.isVisible()  # the status bar cards close through their controller
    assert not tooltip.isVisible()
    sticky.hide()
