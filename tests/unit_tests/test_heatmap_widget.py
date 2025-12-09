from unittest import mock

import numpy as np
import pytest
from bec_lib import messages
from bec_lib.scan_history import ScanHistory
from qtpy.QtGui import QTransform

from bec_widgets.widgets.plots.heatmap.heatmap import (
    Heatmap,
    HeatmapConfig,
    HeatmapDeviceSignal,
    _InterpolationRequest,
    _StepInterpolationWorker,
)

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
    scan_msg = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="grid_scan",
        metadata={},
        info={"positions": np.random.rand(100, 2).tolist()},
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
    heatmap_widget.scan_item.status_message = messages.ScanStatusMessage(
        scan_id="123",
        status="open",
        scan_name="grid_scan",
        metadata={},
        info={"positions": np.random.rand(100, 2).tolist()},
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
