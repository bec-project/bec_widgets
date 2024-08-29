# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest

from bec_widgets.widgets.stop_button.stop_button import StopButton

from .client_mocks import mocked_client


@pytest.fixture
def stop_button(qtbot, mocked_client):
    widget = StopButton(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_stop_button(stop_button):
    assert stop_button.button.text() == "Stop"
    assert (
        stop_button.button.styleSheet()
        == "background-color:  #cc181e; color: white; font-weight: bold; font-size: 12px;"
    )
    stop_button.button.click()
    assert stop_button.queue.request_scan_halt.called
    stop_button.close()
