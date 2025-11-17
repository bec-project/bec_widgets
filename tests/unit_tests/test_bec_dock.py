# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.containers.dock import BECDockArea

from .test_bec_queue import bec_queue_msg_full


@pytest.fixture
def bec_dock_area(qtbot, mocked_client):
    widget = BECDockArea(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_bec_dock_area_init(bec_dock_area):
    assert bec_dock_area is not None
    assert bec_dock_area.client is not None
    assert isinstance(bec_dock_area, BECDockArea)
    assert bec_dock_area.config.widget_class == "BECDockArea"


def test_bec_dock_area_add_remove_dock(bec_dock_area, qtbot):
    initial_count = len(bec_dock_area.dock_area.docks)

    # Adding 3 docks
    d0 = bec_dock_area.new()
    d1 = bec_dock_area.new()
    d2 = bec_dock_area.new()

    # Check if the docks were added
    assert len(bec_dock_area.dock_area.docks) == initial_count + 3
    assert d0.name() in dict(bec_dock_area.dock_area.docks)
    assert d1.name() in dict(bec_dock_area.dock_area.docks)
    assert d2.name() in dict(bec_dock_area.dock_area.docks)
    assert bec_dock_area.dock_area.docks[d0.name()].config.widget_class == "BECDock"
    assert bec_dock_area.dock_area.docks[d1.name()].config.widget_class == "BECDock"
    assert bec_dock_area.dock_area.docks[d2.name()].config.widget_class == "BECDock"

    # Check panels API for getting docks to CLI
    assert bec_dock_area.panels == dict(bec_dock_area.dock_area.docks)

    # Remove docks
    d0_name = d0.name()
    bec_dock_area.delete(d0_name)
    d1.remove()

    qtbot.waitUntil(lambda: len(bec_dock_area.dock_area.docks) == initial_count + 1, timeout=200)
    assert d0.name() not in dict(bec_dock_area.dock_area.docks)
    assert d1.name() not in dict(bec_dock_area.dock_area.docks)
    assert d2.name() in dict(bec_dock_area.dock_area.docks)


def test_close_docks(bec_dock_area, qtbot):
    _ = bec_dock_area.new(name="dock_0")
    _ = bec_dock_area.new(name="dock_1")
    _ = bec_dock_area.new(name="dock_2")

    bec_dock_area.delete_all()
    qtbot.waitUntil(lambda: len(bec_dock_area.dock_area.docks) == 0)


def test_undock_and_dock_docks(bec_dock_area, qtbot):
    d0 = bec_dock_area.new(name="dock_0")
    d1 = bec_dock_area.new(name="dock_1")
    d2 = bec_dock_area.new(name="dock_4")
    d3 = bec_dock_area.new(name="dock_3")

    d0.detach()
    bec_dock_area.detach_dock("dock_1")
    d2.detach()

    assert len(bec_dock_area.dock_area.docks) == 4
    assert len(bec_dock_area.dock_area.tempAreas) == 3

    d0.attach()
    assert len(bec_dock_area.dock_area.docks) == 4
    assert len(bec_dock_area.dock_area.tempAreas) == 2

    bec_dock_area.attach_all()
    assert len(bec_dock_area.dock_area.docks) == 4
    assert len(bec_dock_area.dock_area.tempAreas) == 0


def test_new_dock_raises_for_invalid_name(bec_dock_area):
    with pytest.raises(ValueError):
        bec_dock_area.new(
            name="new", _override_slot_params={"popup_error": False, "raise_error": True}
        )


###################################
# Toolbar Actions
###################################
def test_toolbar_add_plot_waveform(bec_dock_area):
    bec_dock_area.toolbar.components.get_action("menu_plots").actions["waveform"].action.trigger()
    assert "waveform_0" in bec_dock_area.panels
    assert bec_dock_area.panels["waveform_0"].widgets[0].config.widget_class == "Waveform"


def test_toolbar_add_plot_scatter_waveform(bec_dock_area):
    bec_dock_area.toolbar.components.get_action("menu_plots").actions[
        "scatter_waveform"
    ].action.trigger()
    assert "scatter_waveform_0" in bec_dock_area.panels
    assert (
        bec_dock_area.panels["scatter_waveform_0"].widgets[0].config.widget_class
        == "ScatterWaveform"
    )


def test_toolbar_add_plot_image(bec_dock_area):
    bec_dock_area.toolbar.components.get_action("menu_plots").actions["image"].action.trigger()
    assert "image_0" in bec_dock_area.panels
    assert bec_dock_area.panels["image_0"].widgets[0].config.widget_class == "Image"


def test_toolbar_add_plot_motor_map(bec_dock_area):
    bec_dock_area.toolbar.components.get_action("menu_plots").actions["motor_map"].action.trigger()
    assert "motor_map_0" in bec_dock_area.panels
    assert bec_dock_area.panels["motor_map_0"].widgets[0].config.widget_class == "MotorMap"


def test_toolbar_add_multi_waveform(bec_dock_area):
    bec_dock_area.toolbar.components.get_action("menu_plots").actions[
        "multi_waveform"
    ].action.trigger()
    # Check if the MultiWaveform panel is created
    assert "multi_waveform_0" in bec_dock_area.panels
    assert (
        bec_dock_area.panels["multi_waveform_0"].widgets[0].config.widget_class == "MultiWaveform"
    )


def test_toolbar_add_device_positioner_box(bec_dock_area):
    bec_dock_area.toolbar.components.get_action("menu_devices").actions[
        "positioner_box"
    ].action.trigger()
    assert "positioner_box_0" in bec_dock_area.panels
    assert (
        bec_dock_area.panels["positioner_box_0"].widgets[0].config.widget_class == "PositionerBox"
    )


def test_toolbar_add_utils_queue(bec_dock_area, bec_queue_msg_full):
    bec_dock_area.client.connector.set_and_publish(
        MessageEndpoints.scan_queue_status(), bec_queue_msg_full
    )
    bec_dock_area.toolbar.components.get_action("menu_utils").actions["queue"].action.trigger()
    assert "bec_queue_0" in bec_dock_area.panels
    assert bec_dock_area.panels["bec_queue_0"].widgets[0].config.widget_class == "BECQueue"


def test_toolbar_add_utils_status(bec_dock_area):
    bec_dock_area.toolbar.components.get_action("menu_utils").actions["status"].action.trigger()
    assert "bec_status_box_0" in bec_dock_area.panels
    assert bec_dock_area.panels["bec_status_box_0"].widgets[0].config.widget_class == "BECStatusBox"


def test_toolbar_add_utils_progress_bar(bec_dock_area):
    bec_dock_area.toolbar.components.get_action("menu_utils").actions[
        "progress_bar"
    ].action.trigger()
    assert "ring_progress_bar_0" in bec_dock_area.panels
    assert (
        bec_dock_area.panels["ring_progress_bar_0"].widgets[0].config.widget_class
        == "RingProgressBar"
    )


def test_toolbar_screenshot_action(bec_dock_area, tmpdir):
    """Test the screenshot functionality from the toolbar."""
    # Create a test screenshot file path in tmpdir
    screenshot_path = tmpdir.join("test_screenshot.png")

    # Mock the QFileDialog.getSaveFileName to return a test filename
    with mock.patch("bec_widgets.utils.bec_widget.QFileDialog.getSaveFileName") as mock_dialog:
        mock_dialog.return_value = (str(screenshot_path), "PNG Files (*.png)")

        # Mock the screenshot.save method
        with mock.patch.object(bec_dock_area, "grab") as mock_grab:
            mock_screenshot = mock.MagicMock()
            mock_grab.return_value = mock_screenshot

            # Trigger the screenshot action
            bec_dock_area.toolbar.components.get_action("screenshot").action.trigger()

            # Verify the dialog was called with correct parameters
            mock_dialog.assert_called_once()
            call_args = mock_dialog.call_args[0]
            assert call_args[0] == bec_dock_area  # parent widget
            assert call_args[1] == "Save Screenshot"  # dialog title
            assert call_args[2].startswith("bec_")  # filename starts with bec_
            assert call_args[2].endswith(".png")  # filename ends with .png
            assert (
                call_args[3] == "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*)"
            )  # file filter

            # Verify grab was called
            mock_grab.assert_called_once()

            # Verify save was called with the filename
            mock_screenshot.save.assert_called_once_with(str(screenshot_path))


def test_toolbar_screenshot_action_cancelled(bec_dock_area):
    """Test the screenshot functionality when user cancels the dialog."""
    # Mock the QFileDialog.getSaveFileName to return empty filename (cancelled)
    with mock.patch("bec_widgets.utils.bec_widget.QFileDialog.getSaveFileName") as mock_dialog:
        mock_dialog.return_value = ("", "")

        # Mock the screenshot.save method
        with mock.patch.object(bec_dock_area, "grab") as mock_grab:
            mock_screenshot = mock.MagicMock()
            mock_grab.return_value = mock_screenshot

            # Trigger the screenshot action
            bec_dock_area.toolbar.components.get_action("screenshot").action.trigger()

            # Verify the dialog was called
            mock_dialog.assert_called_once()

            # Verify grab was called (screenshot is taken before dialog)
            mock_grab.assert_called_once()

            # Verify save was NOT called since dialog was cancelled
            mock_screenshot.save.assert_not_called()
