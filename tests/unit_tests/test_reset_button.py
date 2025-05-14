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
