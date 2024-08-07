import pytest
from qtpy.QtCore import QPointF, Qt

from bec_widgets.widgets.toggle.toggle import ToggleSwitch


@pytest.fixture
def toggle(qtbot):
    widget = ToggleSwitch()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_toggle(toggle):
    toggle.checked = False
    assert toggle.checked is False

    assert toggle.thumb_pos == QPointF(3, 2)

    toggle.checked = True
    assert toggle.checked is True

    assert toggle.thumb_pos == QPointF(22, 2)


def test_toggle_click(qtbot, toggle):
    init_state = toggle.checked

    qtbot.mouseClick(toggle, Qt.LeftButton)
    toggle.paintEvent(None)
    assert toggle.checked is not init_state

    init_state = toggle.checked

    qtbot.mouseClick(toggle, Qt.LeftButton)
    toggle.paintEvent(None)
    assert toggle.checked is not init_state
