# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest

from bec_widgets.widgets.button_reset.button_reset import ResetButton

from .client_mocks import mocked_client


@pytest.fixture
def reset_button(qtbot, mocked_client):
    widget = ResetButton(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_stop_button(reset_button):
    assert reset_button.button.text() == "Reset Queue"
    assert (
        reset_button.button.styleSheet()
        == "background-color:  #F19E39; color: white; font-weight: bold; font-size: 12px;"
    )
    reset_button.button.click()
    assert reset_button.queue.request_queue_reset.called
    reset_button.close()
