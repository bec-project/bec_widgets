# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest

from bec_widgets.widgets import StopButton

from .client_mocks import mocked_client


@pytest.fixture
def stop_button(qtbot, mocked_client):
    widget = StopButton(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_stop_button(stop_button):
    assert stop_button.text() == "Stop"
    assert stop_button.styleSheet() == "background-color:  #cc181e; color: white"
    stop_button.click()
    assert stop_button.queue.request_scan_abortion.called
    assert stop_button.queue.request_queue_reset.called
    stop_button.close()
