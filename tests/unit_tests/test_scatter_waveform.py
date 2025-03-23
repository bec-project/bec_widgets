import json

import numpy as np

from bec_widgets.widgets.plots.scatter_waveform.scatter_curve import (
    ScatterCurveConfig,
    ScatterDeviceSignal,
)
from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform
from tests.unit_tests.client_mocks import create_dummy_scan_item, mocked_client

from .conftest import create_widget


def test_waveform_initialization(qtbot, mocked_client):
    """
    Test that a new Waveform widget initializes with the correct defaults.
    """
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)
    assert swf.objectName() == "ScatterWaveform"
    # Inherited from PlotBase
    assert swf.title == ""
    assert swf.x_label == ""
    assert swf.y_label == ""
    # No crosshair or FPS monitor by default
    assert swf.crosshair is None
    assert swf.fps_monitor is None
    assert swf.main_curve is not None


def test_scatter_waveform_plot(qtbot, mocked_client):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)
    curve = swf.plot("samx", "samy", "bpm4i")

    assert curve is not None
    assert isinstance(curve.config, ScatterCurveConfig)
    assert curve.config.x_device == ScatterDeviceSignal(name="samx", entry="samx")
    assert curve.config.label == "bpm4i-bpm4i"


def test_scatter_waveform_color_map(qtbot, mocked_client):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)
    assert swf.color_map == "magma"

    swf.color_map = "plasma"
    assert swf.color_map == "plasma"


def test_scatter_waveform_curve_json(qtbot, mocked_client):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Add a device-based scatter curve
    swf.plot(x_name="samx", y_name="samy", z_name="bpm4i", label="test_curve")

    json_str = swf.curve_json
    data = json.loads(json_str)
    assert isinstance(data, dict)
    assert data["label"] == "test_curve"
    assert data["x_device"]["name"] == "samx"
    assert data["y_device"]["name"] == "samy"
    assert data["z_device"]["name"] == "bpm4i"

    # Clear and reload from JSON
    swf.clear_all()
    assert swf.main_curve.getData() == (None, None)

    swf.curve_json = json_str
    assert swf.main_curve.config.label == "test_curve"


def test_scatter_waveform_update_with_scan_history(qtbot, mocked_client, monkeypatch):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    dummy_scan = create_dummy_scan_item()
    mocked_client.history.get_by_scan_id.return_value = dummy_scan
    mocked_client.history.__getitem__.return_value = dummy_scan

    swf.plot("samx", "samy", "bpm4i", label="test_curve")
    swf.update_with_scan_history(scan_id="dummy")
    qtbot.wait(500)

    assert swf.scan_item == dummy_scan

    x_data, y_data = swf.main_curve.getData()
    np.testing.assert_array_equal(x_data, [10, 20, 30])
    np.testing.assert_array_equal(y_data, [5, 10, 15])


def test_scatter_waveform_live_update(qtbot, mocked_client, monkeypatch):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    dummy_scan = create_dummy_scan_item()
    monkeypatch.setattr(swf.queue.scan_storage, "find_scan_by_ID", lambda scan_id: dummy_scan)

    swf.plot("samx", "samy", "bpm4i", label="live_curve")

    # Simulate scan status indicating new scan start
    msg = {"scan_id": "dummy"}
    meta = {}
    swf.on_scan_status(msg, meta)

    assert swf.scan_id == "dummy"
    assert swf.scan_item == dummy_scan

    qtbot.wait(500)

    x_data, y_data = swf.main_curve.getData()
    np.testing.assert_array_equal(x_data, [10, 20, 30])
    np.testing.assert_array_equal(y_data, [5, 10, 15])


def test_scatter_waveform_scan_progress(qtbot, mocked_client, monkeypatch):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    dummy_scan = create_dummy_scan_item()
    monkeypatch.setattr(swf.queue.scan_storage, "find_scan_by_ID", lambda scan_id: dummy_scan)

    swf.plot("samx", "samy", "bpm4i")

    # Simulate scan status indicating scan progress
    swf.scan_id = "dummy"
    swf.scan_item = dummy_scan

    msg = {"progress": 50}
    meta = {}
    swf.on_scan_progress(msg, meta)
    qtbot.wait(500)

    # swf.update_sync_curves()

    x_data, y_data = swf.main_curve.getData()
    np.testing.assert_array_equal(x_data, [10, 20, 30])
    np.testing.assert_array_equal(y_data, [5, 10, 15])


def test_scatter_waveform_settings_popup(qtbot, mocked_client):
    """
    Test that the settings popup is created correctly.
    """
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    scatter_popup_action = swf.toolbar.widgets["scatter_waveform_settings"].action
    assert not scatter_popup_action.isChecked(), "Should start unchecked"

    swf.show_scatter_curve_settings()

    assert swf.scatter_dialog is not None
    assert swf.scatter_dialog.isVisible()
    assert scatter_popup_action.isChecked()

    swf.scatter_dialog.close()
    assert swf.scatter_dialog is None
    assert not scatter_popup_action.isChecked(), "Should be unchecked after closing dialog"
