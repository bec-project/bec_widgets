from unittest import mock

import numpy as np
import pytest
from bec_lib import messages
from bec_lib.scan_history import ScanHistory
from qtpy.QtCore import QPointF
from qtpy.QtGui import QTransform

from bec_widgets.widgets.plots.heatmap.heatmap import (
    Heatmap,
    HeatmapConfig,
    HeatmapDeviceSignal,
    _InterpolationRequest,
    _StepInterpolationWorker,
)

# pytest: disable=unused-import


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
    heatmap_widget._pending_interpolation_request = object()
    heatmap_widget._latest_interpolation_version = 5
    heatmap_widget.scan_item = create_dummy_scan_item()
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    heatmap_widget.reset()
    assert heatmap_widget._grid_index is None
    assert heatmap_widget.main_image.raw_data is None
    assert heatmap_widget._pending_interpolation_request is None
    assert heatmap_widget._latest_interpolation_version == 5


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


def test_step_interpolation_worker_emits_finished(qtbot):
    worker = _StepInterpolationWorker()
    request = _InterpolationRequest(
        x_data=[0.0, 1.0, 0.5, 0.2],
        y_data=[0.0, 0.0, 1.0, 1.0],
        z_data=[1.0, 2.0, 3.0, 4.0],
        data_version=4,
        scan_id="scan-1",
        interpolation="linear",
        oversampling_factor=1.0,
    )
    with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
        worker.process(request, request.data_version)
    img, transform, data_version, scan_id = blocker.args
    assert img.shape[0] > 0
    assert isinstance(transform, QTransform)
    assert data_version == request.data_version
    assert scan_id == request.scan_id


def test_step_interpolation_worker_emits_failed(qtbot, monkeypatch):
    def _scan_goes_boom(**kwargs):
        raise RuntimeError("crash")

    monkeypatch.setattr(
        "bec_widgets.widgets.plots.heatmap.heatmap.Heatmap.compute_step_scan_image", _scan_goes_boom
    )
    worker = _StepInterpolationWorker()
    request = _InterpolationRequest(
        x_data=[0.0, 1.0, 0.5, 0.2],
        y_data=[0.0, 0.0, 1.0, 1.0],
        z_data=[1.0, 2.0, 3.0, 4.0],
        data_version=99,
        scan_id="scan-err",
        interpolation="linear",
        oversampling_factor=1.0,
    )
    with qtbot.waitSignal(worker.failed, timeout=1000) as blocker:
        worker.process(request, request.data_version)
    error, data_version, scan_id = blocker.args
    assert "crash" in error
    assert data_version == request.data_version
    assert scan_id == request.scan_id


def test_interpolation_generation_invalidation(heatmap_widget):
    heatmap_widget.scan_id = "scan-1"
    heatmap_widget._latest_interpolation_version = 2
    with (
        mock.patch.object(heatmap_widget, "_apply_image_update") as apply_mock,
        mock.patch.object(heatmap_widget, "_maybe_start_pending_interpolation") as maybe_mock,
    ):
        heatmap_widget._on_interpolation_finished(
            np.zeros((2, 2)), QTransform(), data_version=1, scan_id="scan-1"
        )
    apply_mock.assert_not_called()
    maybe_mock.assert_called_once()


def test_pending_request_queueing_and_start(heatmap_widget):
    heatmap_widget.scan_id = "scan-queue"
    heatmap_widget.status_message = messages.ScanStatusMessage(
        scan_id="scan-queue",
        status="open",
        scan_name="step_scan",
        scan_type="step",
        metadata={},
        info={"positions": [[0, 0], [1, 1], [2, 2], [3, 3]]},
    )
    # Simulate an active worker processing a job so new requests are queued.
    heatmap_widget._interpolation_worker = mock.MagicMock()
    heatmap_widget._interpolation_worker.is_processing = True

    with mock.patch.object(heatmap_widget, "_start_step_scan_interpolation") as start_mock:
        heatmap_widget._request_step_scan_interpolation(
            x_data=[0, 1, 2, 3],
            y_data=[0, 1, 2, 3],
            z_data=[0, 1, 2, 3],
            msg=heatmap_widget.status_message,
        )
        assert heatmap_widget._pending_interpolation_request is not None

        # Now simulate worker finished and thread cleaned up
        heatmap_widget._interpolation_worker.is_processing = False
        pending = heatmap_widget._pending_interpolation_request
        heatmap_widget._pending_interpolation_request = pending
        heatmap_widget._maybe_start_pending_interpolation()

        start_mock.assert_called_once()


def test_finish_interpolation_thread_cleans_references(heatmap_widget):
    worker_mock = mock.Mock()
    thread_mock = mock.Mock()
    thread_mock.isRunning.return_value = True
    heatmap_widget._interpolation_worker = worker_mock
    heatmap_widget._interpolation_thread = thread_mock

    heatmap_widget._finish_interpolation_thread()

    worker_mock.deleteLater.assert_called_once()
    thread_mock.quit.assert_called_once()
    thread_mock.wait.assert_called_once()
    thread_mock.deleteLater.assert_called_once()
    assert heatmap_widget._interpolation_worker is None
    assert heatmap_widget._interpolation_thread is None


def test_device_safe_properties_get(heatmap_widget):
    """Test that device SafeProperty getters work correctly."""
    # Initially devices should be empty
    assert heatmap_widget.x_device_name == ""
    assert heatmap_widget.x_device_entry == ""
    assert heatmap_widget.y_device_name == ""
    assert heatmap_widget.y_device_entry == ""
    assert heatmap_widget.z_device_name == ""
    assert heatmap_widget.z_device_entry == ""

    # Set devices via plot
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    # Check properties return device names and entries separately
    assert heatmap_widget.x_device_name == "samx"
    assert heatmap_widget.x_device_entry  # Should have some entry
    assert heatmap_widget.y_device_name == "samy"
    assert heatmap_widget.y_device_entry  # Should have some entry
    assert heatmap_widget.z_device_name == "bpm4i"
    assert heatmap_widget.z_device_entry  # Should have some entry


def test_device_safe_properties_set_name(heatmap_widget):
    """Test that device SafeProperty setters work for device names."""
    # Set x_device_name - should auto-validate entry
    heatmap_widget.x_device_name = "samx"
    assert heatmap_widget._image_config.x_device is not None
    assert heatmap_widget._image_config.x_device.name == "samx"
    assert heatmap_widget._image_config.x_device.entry is not None  # Entry should be validated
    assert heatmap_widget.x_device_name == "samx"

    # Set y_device_name
    heatmap_widget.y_device_name = "samy"
    assert heatmap_widget._image_config.y_device is not None
    assert heatmap_widget._image_config.y_device.name == "samy"
    assert heatmap_widget._image_config.y_device.entry is not None
    assert heatmap_widget.y_device_name == "samy"

    # Set z_device_name
    heatmap_widget.z_device_name = "bpm4i"
    assert heatmap_widget._image_config.z_device is not None
    assert heatmap_widget._image_config.z_device.name == "bpm4i"
    assert heatmap_widget._image_config.z_device.entry is not None
    assert heatmap_widget.z_device_name == "bpm4i"


def test_device_safe_properties_set_entry(heatmap_widget):
    """Test that device entry properties can override default entries."""
    # Set device name first - this auto-validates entry
    heatmap_widget.x_device_name = "samx"
    initial_entry = heatmap_widget.x_device_entry
    assert initial_entry  # Should have auto-validated entry

    # Override with specific entry
    heatmap_widget.x_device_entry = "samx"
    assert heatmap_widget._image_config.x_device.entry == "samx"
    assert heatmap_widget.x_device_entry == "samx"

    # Same for y device
    heatmap_widget.y_device_name = "samy"
    heatmap_widget.y_device_entry = "samy_setpoint"
    assert heatmap_widget._image_config.y_device.entry == "samy_setpoint"

    # Same for z device
    heatmap_widget.z_device_name = "bpm4i"
    heatmap_widget.z_device_entry = "bpm4i"
    assert heatmap_widget._image_config.z_device.entry == "bpm4i"


def test_device_entry_cannot_be_set_without_name(heatmap_widget):
    """Test that setting entry without device name logs warning and does nothing."""
    # Try to set entry without device name
    heatmap_widget.x_device_entry = "some_entry"
    # Should not crash, entry should remain empty
    assert heatmap_widget.x_device_entry == ""
    assert heatmap_widget._image_config.x_device is None


def test_device_safe_properties_set_empty(heatmap_widget):
    """Test that device SafeProperty setters handle empty strings."""
    # Set device first
    heatmap_widget.x_device_name = "samx"
    assert heatmap_widget._image_config.x_device is not None

    # Set to empty string - should clear the device
    heatmap_widget.x_device_name = ""
    assert heatmap_widget.x_device_name == ""
    assert heatmap_widget._image_config.x_device is None


def test_device_safe_properties_auto_plot(heatmap_widget):
    """Test that setting all three devices triggers auto-plot."""
    # Set all three devices
    heatmap_widget.x_device_name = "samx"
    heatmap_widget.y_device_name = "samy"
    heatmap_widget.z_device_name = "bpm4i"

    # Check that plot was called (image_config should be updated)
    assert heatmap_widget._image_config.x_device is not None
    assert heatmap_widget._image_config.y_device is not None
    assert heatmap_widget._image_config.z_device is not None


def test_device_properties_update_labels(heatmap_widget):
    """Test that setting device properties updates axis labels."""
    # Set x device - should update x label
    heatmap_widget.x_device_name = "samx"
    assert heatmap_widget.x_label == "samx"

    # Set y device - should update y label
    heatmap_widget.y_device_name = "samy"
    assert heatmap_widget.y_label == "samy"

    # Set z device - should update title
    heatmap_widget.z_device_name = "bpm4i"
    assert heatmap_widget.title == "bpm4i"


def test_device_properties_partial_configuration(heatmap_widget):
    """Test that widget handles partial device configuration gracefully."""
    # Set only x device
    heatmap_widget.x_device_name = "samx"
    assert heatmap_widget.x_device_name == "samx"
    assert heatmap_widget.y_device_name == ""
    assert heatmap_widget.z_device_name == ""

    # Set only y device (x already set)
    heatmap_widget.y_device_name = "samy"
    assert heatmap_widget.x_device_name == "samx"
    assert heatmap_widget.y_device_name == "samy"
    assert heatmap_widget.z_device_name == ""

    # Auto-plot should not trigger yet (z missing)
    # But devices should be configured
    assert heatmap_widget._image_config.x_device is not None
    assert heatmap_widget._image_config.y_device is not None


def test_device_properties_in_user_access(heatmap_widget):
    """Test that device properties are exposed in USER_ACCESS for RPC."""
    from bec_widgets.widgets.plots.heatmap.heatmap import Heatmap

    assert "x_device_name" in Heatmap.USER_ACCESS
    assert "x_device_name.setter" in Heatmap.USER_ACCESS
    assert "x_device_entry" in Heatmap.USER_ACCESS
    assert "x_device_entry.setter" in Heatmap.USER_ACCESS
    assert "y_device_name" in Heatmap.USER_ACCESS
    assert "y_device_name.setter" in Heatmap.USER_ACCESS
    assert "y_device_entry" in Heatmap.USER_ACCESS
    assert "y_device_entry.setter" in Heatmap.USER_ACCESS
    assert "z_device_name" in Heatmap.USER_ACCESS
    assert "z_device_name.setter" in Heatmap.USER_ACCESS
    assert "z_device_entry" in Heatmap.USER_ACCESS
    assert "z_device_entry.setter" in Heatmap.USER_ACCESS


def test_device_properties_validation(heatmap_widget):
    """Test that device entries are validated through entry_validator."""
    # Set device name - entry should be auto-validated
    heatmap_widget.x_device_name = "samx"
    initial_entry = heatmap_widget.x_device_entry

    # The entry should be validated (will be "samx" in the mock)
    assert initial_entry == "samx"

    # Set a different entry - should also be validated
    heatmap_widget.x_device_entry = "samx"  # Use same name as validated entry
    assert heatmap_widget.x_device_entry == "samx"


def test_device_properties_with_plot_method(heatmap_widget):
    """Test that device properties reflect values set via plot() method."""
    # Use plot method
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    # Properties should reflect the plotted devices
    assert heatmap_widget.x_device_name == "samx"
    assert heatmap_widget.y_device_name == "samy"
    assert heatmap_widget.z_device_name == "bpm4i"

    # Entries should be validated
    assert heatmap_widget.x_device_entry == "samx"
    assert heatmap_widget.y_device_entry == "samy"
    assert heatmap_widget.z_device_entry == "bpm4i"


def test_device_properties_overwrite_via_properties(heatmap_widget):
    """Test that device properties can overwrite values set via plot()."""
    # First set via plot
    heatmap_widget.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    # Overwrite x device via properties
    heatmap_widget.x_device_name = "samz"
    assert heatmap_widget.x_device_name == "samz"
    assert heatmap_widget._image_config.x_device.name == "samz"

    # Overwrite y device entry
    heatmap_widget.y_device_entry = "samy"
    assert heatmap_widget.y_device_entry == "samy"


def test_device_properties_clearing_devices(heatmap_widget):
    """Test clearing devices by setting to empty string."""
    # Set all devices
    heatmap_widget.x_device_name = "samx"
    heatmap_widget.y_device_name = "samy"
    heatmap_widget.z_device_name = "bpm4i"

    # Clear x device
    heatmap_widget.x_device_name = ""
    assert heatmap_widget.x_device_name == ""
    assert heatmap_widget._image_config.x_device is None

    # Y and Z should still be set
    assert heatmap_widget.y_device_name == "samy"
    assert heatmap_widget.z_device_name == "bpm4i"


def test_device_properties_property_changed_signal(heatmap_widget):
    """Test that property_changed signal is emitted when devices are set."""
    from unittest.mock import Mock

    # Connect mock to property_changed signal
    mock_handler = Mock()
    heatmap_widget.property_changed.connect(mock_handler)

    # Set device name
    heatmap_widget.x_device_name = "samx"

    # Signal should have been emitted
    assert mock_handler.called
    # Check it was called with correct arguments
    mock_handler.assert_any_call("x_device_name", "samx")


def test_auto_emit_syncs_heatmap_toolbar_actions(heatmap_widget):
    from unittest.mock import Mock

    fft_action = heatmap_widget.toolbar.components.get_action("image_processing_fft").action
    log_action = heatmap_widget.toolbar.components.get_action("image_processing_log").action

    mock_handler = Mock()
    heatmap_widget.property_changed.connect(mock_handler)

    heatmap_widget.fft = True
    heatmap_widget.log = True

    assert fft_action.isChecked()
    assert log_action.isChecked()
    mock_handler.assert_any_call("fft", True)
    mock_handler.assert_any_call("log", True)


def test_device_entry_validation_with_invalid_device(heatmap_widget):
    """Test that invalid device names are handled gracefully."""
    # Try to set invalid device name
    heatmap_widget.x_device_name = "nonexistent_device"

    # Should not crash, but device might not be set if validation fails
    # The implementation silently fails, so we just check it doesn't crash


def test_device_properties_sequential_entry_changes(heatmap_widget):
    """Test changing device entry multiple times."""
    # Set device
    heatmap_widget.x_device_name = "samx"

    # Change entry multiple times
    heatmap_widget.x_device_entry = "samx_velocity"
    assert heatmap_widget.x_device_entry == "samx_velocity"

    heatmap_widget.x_device_entry = "samx_setpoint"
    assert heatmap_widget.x_device_entry == "samx_setpoint"

    heatmap_widget.x_device_entry = "samx"
    assert heatmap_widget.x_device_entry == "samx"


def test_device_properties_with_none_values(heatmap_widget):
    """Test that None values are handled as empty strings."""
    # Device name None should be treated as empty
    heatmap_widget.x_device_name = None
    assert heatmap_widget.x_device_name == ""

    # Set a device first
    heatmap_widget.y_device_name = "samy"

    # Entry None should not change anything
    heatmap_widget.y_device_entry = None
    assert heatmap_widget.y_device_entry  # Should still have validated entry
