# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

from unittest.mock import patch

import pytest
from qtpy.QtWidgets import QMessageBox

from bec_widgets.widgets.control.buttons.button_reset.button_reset import ResetButton

from .client_mocks import mocked_client


@pytest.fixture
def reset_button(qtbot, mocked_client):
    widget = ResetButton(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_reset_button_appearance(reset_button):
    assert reset_button.button.text() == "Reset Queue"
    assert (
        reset_button.button.styleSheet()
        == "background-color:  #F19E39; color: white; font-weight: bold; font-size: 12px;"
    )


@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Yes)
def test_reset_button_confirmed(mock_exec, reset_button):
    reset_button.button.click()
    assert reset_button.queue.request_queue_reset.called
    reset_button.close()


@patch.object(QMessageBox, "exec_", return_value=QMessageBox.No)
def test_reset_button_cancelled(mock_exec, reset_button):
    reset_button.button.click()
    assert not reset_button.queue.request_queue_reset.called
    reset_button.close()
