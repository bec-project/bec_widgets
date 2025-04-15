# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import os

import pytest
from bec_lib.endpoints import MessageEndpoints

import bec_widgets
from bec_widgets.applications.launch_window import LaunchWindow
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow, UILaunchWindow

from .client_mocks import mocked_client

base_path = os.path.dirname(bec_widgets.__file__)


@pytest.fixture
def bec_launch_window(qtbot, mocked_client):
    widget = LaunchWindow(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_launch_window_initialization(bec_launch_window):
    assert isinstance(bec_launch_window, BECMainWindow)


def test_launch_window_launch_ui_file(bec_launch_window):
    # Mock the file dialog to return a specific UI file path
    ui_file_path = os.path.join(
        base_path, "widgets/control/device_control/positioner_box/positioner_box/positioner_box.ui"
    )
    bec_launch_window._open_custom_ui_file = lambda: ui_file_path

    # Call the method to launch the custom UI file
    res = bec_launch_window.launch("custom_ui_file", ui_file=ui_file_path)

    assert isinstance(res, UILaunchWindow)

    # Check if the custom UI file was launched correctly
    assert res.object_name == "positioner_box"
    assert res.windowTitle() == "BEC - positioner_box"

    # We need to manually close the launched window as it is not registered with qtbot.
    # In real usage, the GUIServer would handle this in the sigint handler in case of a ctrl-c initiated shutdown.
    res.close()
    res.deleteLater()


def test_launch_window_launch_ui_file_raises_for_qmainwindow(bec_launch_window):
    # Mock the file dialog to return a specific UI file path
    # the selected file must contain a QMainWindow widget but can be any file
    ui_file_path = os.path.join(base_path, "applications/alignment/alignment_1d/alignment_1d.ui")

    # Call the method to launch the custom UI file
    with pytest.raises(ValueError) as excinfo:
        bec_launch_window.launch("custom_ui_file", ui_file=ui_file_path)

    assert "Loading a QMainWindow from a UI file is currently not supported." in str(excinfo.value)
