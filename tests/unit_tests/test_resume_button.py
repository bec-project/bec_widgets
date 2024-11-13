# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest

from bec_widgets.widgets.control.buttons.button_resume.button_resume import ResumeButton

from .client_mocks import mocked_client


@pytest.fixture
def resume_button(qtbot, mocked_client):
    widget = ResumeButton(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_resume_button(resume_button):
    assert resume_button.button.text() == "Resume"
    assert (
        resume_button.button.styleSheet()
        == "background-color:  #2793e8; color: white; font-weight: bold; font-size: 12px;"
    )
    resume_button.button.click()
    assert resume_button.queue.request_scan_continuation.called
    resume_button.close()
