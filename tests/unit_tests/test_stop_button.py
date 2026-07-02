# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

from unittest.mock import MagicMock

import pytest

from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton

from .client_mocks import mocked_client


@pytest.fixture
def stop_button(qtbot, mocked_client):
    widget = StopButton(client=mocked_client)
    widget.queue = MagicMock()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget, qtbot


def test_stop_button(stop_button):
    widget, qtbot = stop_button

    assert widget.button.text() == "Stop"

    widget.button.click()

    assert widget.queue.request_scan_abortion.called
    assert widget._emergency_stop_active is True
    qtbot.waitUntil(lambda: widget.button.text() == "Emergency Stop")

    qtbot.wait(widget.EMERGENCY_STOP_TIMEOUT_MS // 2)
    widget.button.click()

    assert widget.queue.request_scan_halt.called

    qtbot.wait((widget.EMERGENCY_STOP_TIMEOUT_MS // 2) + 100)
    assert widget.button.text() == "Emergency Stop"

    qtbot.wait((widget.EMERGENCY_STOP_TIMEOUT_MS // 2) + 100)
    assert widget.button.text() == "Stop"

    widget.close()


def test_stop_button_click_extends_emergency_timeout(stop_button):
    widget, qtbot = stop_button

    widget.button.click()
    qtbot.wait(500)

    widget.button.click()
    assert widget._emergency_stop_active is True
    qtbot.waitUntil(lambda: widget.button.text() == "Emergency Stop")

    qtbot.waitUntil(
        lambda: not widget._reset_timer.isActive(), timeout=widget.EMERGENCY_STOP_TIMEOUT_MS + 500
    )
    assert widget.button.text() == "Stop"
    widget.close()
