import pytest

from bec_widgets.widgets.position_indicator.position_indicator import PositionIndicator


@pytest.fixture
def position_indicator(qtbot):
    """Fixture for PositionIndicator widget"""
    pi = PositionIndicator()
    qtbot.addWidget(pi)
    qtbot.waitExposed(pi)
    return pi


def test_position_indicator_set_range(position_indicator):
    """
    Test set_range method of PositionIndicator
    """
    position_indicator.set_range(0, 20)
    assert position_indicator.minimum == 0
    assert position_indicator.maximum == 20


def test_position_indicator_set_value(position_indicator):
    """
    Test set_value method of PositionIndicator and the correct mapping of the value
    within the paintEvent method
    """
    # pylint: disable=protected-access
    position_indicator.set_value(50)
    assert position_indicator.position == 50

    position_indicator.paintEvent(None)
    assert position_indicator._current_indicator_position == 50

    position_indicator.set_value(100)
    position_indicator.paintEvent(None)
    assert position_indicator._draw_position == position_indicator.width()

    position_indicator.vertical = True
    position_indicator.paintEvent(None)
    assert position_indicator._draw_position == position_indicator.height()
