from unittest import mock

import numpy as np
import pytest
from bec_lib import messages
from bec_lib.scan_history import ScanHistory
from qtpy.QtCore import QPointF

from bec_widgets.widgets.plots.heatmap.heatmap import Heatmap, HeatmapConfig, HeatmapDeviceSignal

# pytest: disable=unused-import
from tests.unit_tests.client_mocks import mocked_client

from .client_mocks import create_dummy_scan_item


@pytest.fixture
def heatmap_widget(qtbot, mocked_client):
    widget = Heatmap(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_heatmap_plot(heatmap_widget):
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    assert heatmap_widget._image_config.x_device.name == "samx"
    assert heatmap_widget._image_config.y_device.name == "samy"
    assert heatmap_widget._image_config.z_device.name == "bpm4i"


def test_heatmap_on_scan_status_no_scan_id(heatmap_widget):

    scan_msg = messages.ScanStatusMessage(scan_id=None, status="open", metadata={}, info={})
    with mock.patch.object(heatmap_widget, "reset") as mock_reset:

        heatmap_widget.on_scan_status(scan_msg.content, scan_msg.metadata)
        mock_reset.assert_not_called()


def test_heatmap_on_scan_status_same_scan_id(heatmap_widget):
    scan_msg = messages.ScanStatusMessage(scan_id="123", status="open", metadata={}, info={})
    heatmap_widget.scan_id = "123"
    with mock.patch.object(heatmap_widget, "reset") as mock_reset:
        heatmap_widget.on_scan_status(scan_msg.content, scan_msg.metadata)
        mock_reset.assert_not_called()


def test_heatmap_widget_on_scan_status_different_scan_id(heatmap_widget):
    scan_msg = messages.ScanStatusMessage(scan_id="123", status="open", metadata={}, info={})
    heatmap_widget.scan_id = "456"
    with mock.patch.object(heatmap_widget, "reset") as mock_reset:
        heatmap_widget.on_scan_status(scan_msg.content, scan_msg.metadata)
        mock_reset.assert_called_once()


def test_heatmap_get_image_data_missing_data(heatmap_widget):
    """
    If the data is missing or incomplete, the method should return None.
    """
    assert heatmap_widget.get_image_data() == (None, None)


def test_heatmap_get_image_data_grid_scan(heatmap_widget):
    scan_msg = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="grid_scan",
        metadata={},
        info={},
        request_inputs={"arg_bundle": ["samx", -5, 5, 10, "samy", -5, 5, 10], "kwargs": {}},
    )
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    heatmap_widget.status_message = scan_msg
    with mock.patch.object(heatmap_widget, "get_grid_scan_image") as mock_get_grid_scan_image:
        heatmap_widget.get_image_data(x_data=[1, 2], y_data=[3, 4], z_data=[5, 6])
        mock_get_grid_scan_image.assert_called_once()


def test_heatmap_get_image_data_step_scan(heatmap_widget):
    """
    If the step scan has too few points, it should return None.
    """
    scan_msg = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="step_scan",
        scan_type="step",
        metadata={},
        info={"positions": [[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4]]},
    )
    with mock.patch.object(heatmap_widget, "get_step_scan_image") as mock_get_step_scan_image:
        heatmap_widget.status_message = scan_msg
        heatmap_widget.get_image_data(x_data=[1, 2, 3, 4], y_data=[1, 2, 3, 4], z_data=[1, 2, 5, 6])
        mock_get_step_scan_image.assert_called_once()


def test_heatmap_get_image_data_step_scan_too_few_points(heatmap_widget):
    """
    If the step scan has too few points, it should return None.
    """
    scan_msg = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="step_scan",
        scan_type="step",
        metadata={},
        info={"positions": [[1, 2], [3, 4]]},
    )
    heatmap_widget.status_message = scan_msg
    out = heatmap_widget.get_image_data(x_data=[1, 2], y_data=[3, 4], z_data=[5, 6])
    assert out == (None, None)


def test_heatmap_get_image_data_unsupported_scan(heatmap_widget):
    scan_msg = messages.ScanStatusMessage(
        scan_id="123", status="open", scan_type="fly", metadata={}, info={}
    )
    heatmap_widget.status_message = scan_msg
    assert heatmap_widget.get_image_data(x_data=[1, 2], y_data=[3, 4], z_data=[5, 6]) == (
        None,
        None,
    )


def test_heatmap_get_grid_scan_image(heatmap_widget):
    x_levels = np.linspace(-5, 5, 10).tolist()
    y_levels = np.linspace(-5, 5, 10).tolist()
    scan_msg = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="grid_scan",
        metadata={},
        info={
            "positions": _grid_positions(slow_levels=x_levels, fast_levels=y_levels, snaked=True)
        },
        request_inputs={"arg_bundle": ["samx", -5, 5, 10, "samy", -5, 5, 10], "kwargs": {}},
    )
    heatmap_widget._image_config = HeatmapConfig(
        parent_id="parent_id",
        x_device=HeatmapDeviceSignal(name="samx", entry="samx"),
        y_device=HeatmapDeviceSignal(name="samy", entry="samy"),
        z_device=HeatmapDeviceSignal(name="bpm4i", entry="bpm4i"),
        color_map="viridis",
    )
    img, _ = heatmap_widget.get_grid_scan_image(list(range(100)), msg=scan_msg)
    assert img.shape == (10, 10)
    assert sorted(np.asarray(img, dtype=int).flatten().tolist()) == list(range(100))


def _grid_positions(
    *, slow_levels: list[float], fast_levels: list[float], snaked: bool, slow_is_col0: bool = True
) -> list[list[float]]:
    positions: list[list[float]] = []
    for slow_i, slow_val in enumerate(slow_levels):
        row_fast = fast_levels if (not snaked or slow_i % 2 == 0) else list(reversed(fast_levels))
        for fast_val in row_fast:
            if slow_is_col0:
                positions.append([slow_val, fast_val])
            else:
                positions.append([fast_val, slow_val])
    return positions


def test_heatmap_grid_scan_direction_and_snaking_x_fast(heatmap_widget):
    heatmap_widget._image_config = HeatmapConfig(
        parent_id="parent_id",
        x_device=HeatmapDeviceSignal(name="samx", entry="samx"),
        y_device=HeatmapDeviceSignal(name="samy", entry="samy"),
        z_device=HeatmapDeviceSignal(name="bpm4i", entry="bpm4i"),
        color_map="viridis",
    )

    # x decreases (relative), y increases (relative), x is fast axis
    x0 = 10.0
    y0 = -3.0
    x_levels = (x0 + np.linspace(1.0, -1.0, 3)).tolist()
    y_levels = (y0 + np.linspace(-2.0, 2.0, 2)).tolist()
    snaked = True

    scan_msg = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="grid_scan",
        metadata={},
        info={
            "positions": _grid_positions(slow_levels=y_levels, fast_levels=x_levels, snaked=snaked)
        },
        request_inputs={
            "arg_bundle": ["samy", -2.0, 2.0, 2, "samx", 1.0, -1.0, 3],
            "kwargs": {"snaked": snaked, "relative": True},
        },
    )

    img, transform = heatmap_widget.get_grid_scan_image(list(range(6)), msg=scan_msg)

    assert img.shape == (3, 2)
    assert img[0, 0] == 0  # first point: (x0,y0) in scan order
    assert img[2, 1] == 3  # second row first point due to snaking
    assert img[0, 1] == 5  # last point in second row

    p0 = transform.map(QPointF(0.5, 0.5))
    p1 = transform.map(QPointF(2.5, 1.5))
    assert p0.x() == pytest.approx(x_levels[0])
    assert p0.y() == pytest.approx(y_levels[0])
    assert p1.x() == pytest.approx(x_levels[-1])
    assert p1.y() == pytest.approx(y_levels[-1])


def test_heatmap_grid_scan_direction_and_snaking_y_fast(heatmap_widget):
    heatmap_widget._image_config = HeatmapConfig(
        parent_id="parent_id",
        x_device=HeatmapDeviceSignal(name="samx", entry="samx"),
        y_device=HeatmapDeviceSignal(name="samy", entry="samy"),
        z_device=HeatmapDeviceSignal(name="bpm4i", entry="bpm4i"),
        color_map="viridis",
    )

    # x decreases (relative), y increases (relative), y is fast axis
    x0 = 1.5
    y0 = 22.0
    x_levels = (x0 + np.linspace(1.0, -1.0, 3)).tolist()
    y_levels = (y0 + np.linspace(-2.0, 2.0, 2)).tolist()
    snaked = True

    scan_msg = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="grid_scan",
        metadata={},
        info={
            "positions": _grid_positions(slow_levels=x_levels, fast_levels=y_levels, snaked=snaked)
        },
        request_inputs={
            "arg_bundle": ["samx", 1.0, -1.0, 3, "samy", -2.0, 2.0, 2],
            "kwargs": {"snaked": snaked, "relative": True},
        },
    )

    img, transform = heatmap_widget.get_grid_scan_image(list(range(6)), msg=scan_msg)

    assert img.shape == (3, 2)
    assert img[0, 0] == 0
    # For y-fast scans, snaking reverses the y index on every odd x row.
    assert img[1, 1] == 2
    assert img[1, 0] == 3

    p0 = transform.map(QPointF(0.5, 0.5))
    p1 = transform.map(QPointF(2.5, 1.5))
    assert p0.x() == pytest.approx(x_levels[0])
    assert p0.y() == pytest.approx(y_levels[0])
    assert p1.x() == pytest.approx(x_levels[-1])
    assert p1.y() == pytest.approx(y_levels[-1])


def test_heatmap_get_step_scan_image(heatmap_widget):

    scan_msg = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="step_scan",
        scan_type="step",
        metadata={},
        info={"positions": np.random.rand(100, 2).tolist()},
    )
    heatmap_widget.status_message = scan_msg
    heatmap_widget.scan_item = create_dummy_scan_item()
    heatmap_widget.scan_item.status_message = scan_msg
    heatmap_widget._image_config = HeatmapConfig(
        parent_id="parent_id",
        x_device=HeatmapDeviceSignal(name="samx", entry="samx"),
        y_device=HeatmapDeviceSignal(name="samy", entry="samy"),
        z_device=HeatmapDeviceSignal(name="bpm4i", entry="bpm4i"),
        color_map="viridis",
    )
    img, _ = heatmap_widget.get_step_scan_image(
        list(np.random.rand(100)), list(np.random.rand(100)), list(range(100)), msg=scan_msg
    )
    assert img.shape > (10, 10)


def test_heatmap_update_plot_no_scan_item(heatmap_widget):
    heatmap_widget._image_config = HeatmapConfig(
        parent_id="parent_id",
        x_device=HeatmapDeviceSignal(name="samx", entry="samx"),
        y_device=HeatmapDeviceSignal(name="samy", entry="samy"),
        z_device=HeatmapDeviceSignal(name="bpm4i", entry="bpm4i"),
        color_map="viridis",
    )
    with mock.patch.object(heatmap_widget.main_image, "setImage") as mock_set_image:
        heatmap_widget.update_plot(_override_slot_params={"verify_sender": False})
        mock_set_image.assert_not_called()


def test_heatmap_update_plot(heatmap_widget):
    heatmap_widget._image_config = HeatmapConfig(
        parent_id="parent_id",
        x_device=HeatmapDeviceSignal(name="samx", entry="samx"),
        y_device=HeatmapDeviceSignal(name="samy", entry="samy"),
        z_device=HeatmapDeviceSignal(name="bpm4i", entry="bpm4i"),
        color_map="viridis",
    )
    heatmap_widget.scan_item = create_dummy_scan_item()
    x_levels = np.linspace(-5, 5, 10).tolist()
    y_levels = np.linspace(-5, 5, 10).tolist()
    heatmap_widget.scan_item.status_message = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="grid_scan",
        metadata={},
        info={
            "positions": _grid_positions(slow_levels=x_levels, fast_levels=y_levels, snaked=True)
        },
        request_inputs={"arg_bundle": ["samx", -5, 5, 10, "samy", -5, 5, 10], "kwargs": {}},
    )
    with mock.patch.object(heatmap_widget.main_image, "setImage") as mock_set_image:
        heatmap_widget.update_plot(_override_slot_params={"verify_sender": False})
        img = mock_set_image.mock_calls[0].args[0]
        assert img.shape == (10, 10)


def test_heatmap_update_plot_without_status_message(heatmap_widget):
    heatmap_widget._image_config = HeatmapConfig(
        parent_id="parent_id",
        x_device=HeatmapDeviceSignal(name="samx", entry="samx"),
        y_device=HeatmapDeviceSignal(name="samy", entry="samy"),
        z_device=HeatmapDeviceSignal(name="bpm4i", entry="bpm4i"),
        color_map="viridis",
    )
    heatmap_widget.scan_item = create_dummy_scan_item()
    heatmap_widget.scan_item.status_message = None
    with mock.patch.object(heatmap_widget.main_image, "setImage") as mock_set_image:
        heatmap_widget.update_plot(_override_slot_params={"verify_sender": False})
        mock_set_image.assert_not_called()


def test_heatmap_update_plot_no_img_data(heatmap_widget):
    heatmap_widget._image_config = HeatmapConfig(
        parent_id="parent_id",
        x_device=HeatmapDeviceSignal(name="samx", entry="samx"),
        y_device=HeatmapDeviceSignal(name="samy", entry="samy"),
        z_device=HeatmapDeviceSignal(name="bpm4i", entry="bpm4i"),
        color_map="viridis",
    )
    heatmap_widget.scan_item = create_dummy_scan_item()
    heatmap_widget.scan_item.status_message = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="grid_scan",
        metadata={},
        info={},
        request_inputs={"arg_bundle": ["samx", -5, 5, 10, "samy", -5, 5, 10], "kwargs": {}},
    )
    with mock.patch.object(heatmap_widget, "get_image_data", return_value=None):
        with mock.patch.object(heatmap_widget.main_image, "setImage") as mock_set_image:
            heatmap_widget.update_plot(_override_slot_params={"verify_sender": False})
            mock_set_image.assert_not_called()


def test_heatmap_settings_popup(heatmap_widget, qtbot):
    """
    Test that the settings popup opens and contains the expected elements.
    """
    settings_action = heatmap_widget.toolbar.components.get_action("heatmap_settings").action
    heatmap_widget.show_heatmap_settings()
    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is not None)

    assert heatmap_widget.heatmap_dialog.isVisible()

    assert settings_action.isChecked()

    heatmap_widget.heatmap_dialog.reject()
    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is None)

    assert not settings_action.isChecked()


def test_heatmap_settings_popup_already_open(heatmap_widget, qtbot):
    """
    Test that if the settings dialog is already open, it is brought to the front.
    """
    heatmap_widget.show_heatmap_settings()
    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is not None)

    initial_dialog = heatmap_widget.heatmap_dialog

    heatmap_widget.show_heatmap_settings()
    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is initial_dialog)

    assert heatmap_widget.heatmap_dialog.isVisible()  # Dialog should still be visible
    assert heatmap_widget.heatmap_dialog is initial_dialog  # Should be the same dialog

    heatmap_widget.heatmap_dialog.reject()
    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is None)


def test_heatmap_settings_popup_accept_changes(heatmap_widget, qtbot):
    """
    Test that changes made in the settings dialog are applied correctly.
    """
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")
    assert heatmap_widget.color_map == "plasma"  # Default colormap
    heatmap_widget.show_heatmap_settings()
    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is not None)

    dialog = heatmap_widget.heatmap_dialog
    assert dialog.widget.isVisible()

    # Simulate changing a setting
    dialog.widget.ui.color_map.colormap = "viridis"

    # Accept changes
    dialog.accept()

    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is None)

    # Verify that the setting was applied
    assert heatmap_widget.color_map == "viridis"


def test_heatmap_settings_popup_show_settings(heatmap_widget, qtbot):
    """
    Test that the settings dialog opens and contains the expected elements.
    """
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")
    heatmap_widget.show_heatmap_settings()
    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is not None)

    dialog = heatmap_widget.heatmap_dialog
    assert dialog.isVisible()
    assert dialog.widget is not None
    assert hasattr(dialog.widget.ui, "color_map")
    assert hasattr(dialog.widget.ui, "x_name")
    assert hasattr(dialog.widget.ui, "y_name")
    assert hasattr(dialog.widget.ui, "z_name")

    # Check that the ui elements are correctly initialized
    assert dialog.widget.ui.color_map.colormap == heatmap_widget.color_map
    assert dialog.widget.ui.x_name.currentText() == heatmap_widget._image_config.x_device.name

    dialog.reject()
    qtbot.waitUntil(lambda: heatmap_widget.heatmap_dialog is None)


def test_heatmap_widget_reset(heatmap_widget):
    """
    Test that the reset method clears the plot.
    """
    heatmap_widget.scan_item = create_dummy_scan_item()
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    heatmap_widget.reset()
    assert heatmap_widget._grid_index is None
    assert heatmap_widget.main_image.raw_data is None


def test_heatmap_widget_update_plot_with_scan_history(heatmap_widget, grid_scan_history_msg, qtbot):
    """
    Test that the update_plot method updates the plot with scan history.
    """
    heatmap_widget.client.history = ScanHistory(heatmap_widget.client, False)
    heatmap_widget.client.history._scan_data[grid_scan_history_msg.scan_id] = grid_scan_history_msg
    heatmap_widget.client.history._scan_ids.append(grid_scan_history_msg.scan_id)
    heatmap_widget.client.queue.scan_storage.current_scan = None
    heatmap_widget.plot(
        x_name="samx",
        y_name="samy",
        z_name="bpm4i",
        x_entry="samx",
        y_entry="samy",
        z_entry="bpm4i",
    )
    qtbot.waitUntil(lambda: heatmap_widget.main_image.raw_data is not None)
    qtbot.waitUntil(lambda: heatmap_widget.main_image.raw_data.shape == (10, 10))

    heatmap_widget.enforce_interpolation = True
    heatmap_widget.oversampling_factor = 2.0
    qtbot.waitUntil(lambda: heatmap_widget.main_image.raw_data.shape == (20, 20))
