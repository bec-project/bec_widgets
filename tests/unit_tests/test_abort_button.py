# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest

from bec_widgets.widgets.control.buttons.button_abort.button_abort import AbortButton

from .client_mocks import mocked_client


@pytest.fixture
def abort_button(qtbot, mocked_client):
    widget = AbortButton(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_abort_button(abort_button):
    assert abort_button.button.text() == "Abort"
    abort_button.button.click()
    assert abort_button.queue.request_scan_abortion.called
    abort_button.close()
