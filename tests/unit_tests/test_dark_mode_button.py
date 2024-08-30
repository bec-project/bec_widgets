from unittest import mock

import pytest
from qtpy.QtCore import Qt

from bec_widgets.utils.colors import set_theme
from bec_widgets.widgets.dark_mode_button.dark_mode_button import DarkModeButton

# pylint: disable=unused-import
from .client_mocks import mocked_client

# pylint: disable=redefined-outer-name


@pytest.fixture
def dark_mode_button(qtbot, mocked_client):
    """
    Fixture for the dark mode button.
    """
    button = DarkModeButton(client=mocked_client)
    qtbot.addWidget(button)
    qtbot.waitExposed(button)
    set_theme("light")
    yield button


def test_dark_mode_button_init(dark_mode_button):
    """
    Test that the dark mode button is initialized correctly.
    """
    assert dark_mode_button.dark_mode_enabled is False
    assert dark_mode_button.mode_button.toolTip() == "Set Dark Mode"


def test_dark_mode_button_toggle(dark_mode_button):
    """
    Test that the dark mode button toggles correctly.
    """
    dark_mode_button.toggle_dark_mode()
    assert dark_mode_button.dark_mode_enabled is True
    assert dark_mode_button.mode_button.toolTip() == "Set Light Mode"

    dark_mode_button.toggle_dark_mode()
    assert dark_mode_button.dark_mode_enabled == False
    assert dark_mode_button.mode_button.toolTip() == "Set Dark Mode"


def test_dark_mode_button_toggles_on_click(dark_mode_button, qtbot):
    """
    Test that the dark mode button toggles correctly when clicked.
    """
    qtbot.mouseClick(dark_mode_button.mode_button, Qt.MouseButton.LeftButton)
    assert dark_mode_button.dark_mode_enabled is True
    assert dark_mode_button.mode_button.toolTip() == "Set Light Mode"

    qtbot.mouseClick(dark_mode_button.mode_button, Qt.MouseButton.LeftButton)
    assert dark_mode_button.dark_mode_enabled is False
    assert dark_mode_button.mode_button.toolTip() == "Set Dark Mode"


def test_dark_mode_button_changes_theme(dark_mode_button):
    """
    Test that the dark mode button changes the theme correctly.
    """
    with mock.patch(
        "bec_widgets.widgets.dark_mode_button.dark_mode_button.set_theme"
    ) as mocked_set_theme:
        dark_mode_button.toggle_dark_mode()
        mocked_set_theme.assert_called_with("dark")

        dark_mode_button.toggle_dark_mode()
        mocked_set_theme.assert_called_with("light")
