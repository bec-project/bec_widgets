import json
from unittest.mock import MagicMock

import numpy as np
import pyqtgraph as pg
import pytest
from pyqtgraph.graphicsItems.DateAxisItem import DateAxisItem

from bec_widgets.widgets.plots.plot_base import UIMode
from bec_widgets.widgets.plots.waveform.curve import DeviceSignal
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from tests.unit_tests.client_mocks import (
    DummyData,
    create_dummy_scan_item,
    dap_plugin_message,
    mocked_client,
    mocked_client_with_dap,
)

from .conftest import create_widget

##################################################
# Waveform widget base functionality tests
##################################################


def test_waveform_initialization(qtbot, mocked_client):
    """
    Test that a new Waveform widget initializes with the correct defaults.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    assert wf.objectName() == "Waveform"
    # Inherited from PlotBase
    assert wf.title == ""
    assert wf.x_label == ""
    assert wf.y_label == ""
    # No crosshair or FPS monitor by default
    assert wf.crosshair is None
    assert wf.fps_monitor is None
    # No curves initially
    assert len(wf.plot_item.curves) == 0


def test_waveform_with_side_menu(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client, popups=False)

    assert wf.ui_mode == UIMode.SIDE


def test_plot_custom_curve(qtbot, mocked_client):
    """
    Test that calling plot with explicit x and y data creates a custom curve.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    curve = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="custom_curve")
    assert curve is not None
    assert curve.config.source == "custom"
    assert curve.config.label == "custom_curve"
    x_data, y_data = curve.get_data()
    np.testing.assert_array_equal(x_data, np.array([1, 2, 3]))
    np.testing.assert_array_equal(y_data, np.array([4, 5, 6]))


def test_plot_single_arg_input_1d(qtbot, mocked_client):
    """
    Test that when a single 1D numpy array is passed, the curve is created with
    x-data as a generated index.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    data = np.array([10, 20, 30])
    curve = wf.plot(data, label="curve_1d")
    x_data, y_data = curve.get_data()
    np.testing.assert_array_equal(x_data, np.arange(len(data)))
    np.testing.assert_array_equal(y_data, data)


def test_plot_single_arg_input_2d(qtbot, mocked_client):
    """
    Test that when a single 2D numpy array (N x 2) is passed,
    x and y data are extracted from the first and second columns.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    data = np.array([[1, 4], [2, 5], [3, 6]])
    curve = wf.plot(data, label="curve_2d")
    x_data, y_data = curve.get_data()
    np.testing.assert_array_equal(x_data, data[:, 0])
    np.testing.assert_array_equal(y_data, data[:, 1])


def test_plot_single_arg_input_sync(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    c1 = wf.plot(arg1="bpm4i")
    c2 = wf.plot(arg1="bpm3a")

    assert c1.config.source == "device"
    assert c2.config.source == "device"
    assert c1.config.signal == DeviceSignal(name="bpm4i", entry="bpm4i", dap=None)
    assert c2.config.signal == DeviceSignal(name="bpm3a", entry="bpm3a", dap=None)

    # Check that the curve is added to the plot
    assert len(wf.plot_item.curves) == 2


def test_plot_single_arg_input_async(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    c1 = wf.plot(arg1="eiger")
    c2 = wf.plot(arg1="async_device")

    assert c1.config.source == "device"
    assert c2.config.source == "device"
    assert c1.config.signal == DeviceSignal(name="eiger", entry="eiger", dap=None)
    assert c2.config.signal == DeviceSignal(name="async_device", entry="async_device", dap=None)

    # Check that the curve is added to the plot
    assert len(wf.plot_item.curves) == 2


def test_curve_access_pattern(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    c1 = wf.plot(arg1="bpm4i")
    c2 = wf.plot(arg1="bpm3a")

    # Check that the curve is added to the plot
    assert len(wf.plot_item.curves) == 2

    # Check that the curve is accessible by label
    assert wf.get_curve("bpm4i-bpm4i") == c1
    assert wf.get_curve("bpm3a-bpm3a") == c2

    # Check that the curve is accessible by index
    assert wf.get_curve(0) == c1
    assert wf.get_curve(1) == c2

    assert wf.curves[0] == c1
    assert wf.curves[1] == c2


def test_find_curve_by_label(qtbot, mocked_client):
    """
    Test the _find_curve_by_label method returns the correct curve or None if not found.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c1 = wf.plot(arg1="bpm4i", label="c1_label")
    c2 = wf.plot(arg1="bpm3a", label="c2_label")

    found = wf._find_curve_by_label("c1_label")
    assert found == c1, "Should return the first curve"
    missing = wf._find_curve_by_label("bogus_label")
    assert missing is None, "Should return None if not found"


def test_set_x_mode(qtbot, mocked_client):
    """
    Test that setting x_mode updates the internal x-axis mode state and switches
    the bottom axis of the plot.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "timestamp"
    assert wf.x_axis_mode["name"] == "timestamp"
    # When x_mode is 'timestamp', the bottom axis should be a DateAxisItem.
    assert isinstance(wf.plot_item.axes["bottom"]["item"], DateAxisItem)

    wf.x_mode = "index"
    # For other modes, the bottom axis becomes the default AxisItem.
    assert isinstance(wf.plot_item.axes["bottom"]["item"], pg.AxisItem)

    wf.x_mode = "samx"
    assert wf.x_axis_mode["name"] == "samx"
    assert isinstance(wf.plot_item.axes["bottom"]["item"], pg.AxisItem)


def test_color_palette_update(qtbot, mocked_client):
    """
    Test that updating the color_palette property changes the color of existing curves.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    curve = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="test_curve")
    original_color = curve.config.color
    # Change to a different valid palette
    wf.color_palette = "magma"
    assert wf.config.color_palette == "magma"
    # After updating the palette, the curve's color should be re-generated.
    assert curve.config.color != original_color


def test_curve_json_property(qtbot, mocked_client):
    """
    Test that the curve_json property returns a JSON string representing
    non-custom curves. Since custom curves are not serialized, if only a custom
    curve is added, an empty list should be returned.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="custom_curve")
    json_str = wf.curve_json
    data = json.loads(json_str)
    assert isinstance(data, list)
    # Only custom curves exist so none should be serialized.
    assert len(data) == 0


def test_remove_curve_waveform(qtbot, mocked_client):
    """
    Test that curves can be removed from the waveform using either their label or index.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="curve1")
    wf.plot(x=[4, 5, 6], y=[7, 8, 9], label="curve2")
    num_before = len(wf.plot_item.curves)
    wf.remove_curve("curve1")
    num_after = len(wf.plot_item.curves)
    assert num_after == num_before - 1

    wf.remove_curve(0)
    assert len(wf.plot_item.curves) == num_after - 1


def test_get_all_data_empty(qtbot, mocked_client):
    """
    Test that get_all_data returns an empty dictionary when no curves have been added.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    all_data = wf.get_all_data(output="dict")
    assert all_data == {}


def test_get_all_data_dict(qtbot, mocked_client):
    """
    Test that get_all_data returns a dictionary with the expected x and y data for each curve.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="curve1")
    wf.plot(x=[7, 8, 9], y=[10, 11, 12], label="curve2")

    all_data = wf.get_all_data(output="dict")

    expected = {
        "curve1": {"x": [1, 2, 3], "y": [4, 5, 6]},
        "curve2": {"x": [7, 8, 9], "y": [10, 11, 12]},
    }
    assert all_data == expected


def test_curve_json_getter_setter(qtbot, mocked_client):
    """
    Test that the curve_json getter returns a JSON string representing device curves
    and that setting curve_json re-creates the curves.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    # These curves should be in JSON
    wf.plot(arg1="bpm4i")
    wf.plot(arg1="bpm3a")
    # Custom curves should be ignored
    wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="custom_curve")
    wf.plot([1, 2, 3, 4])

    # Get JSON from the getter.
    json_str = wf.curve_json
    curve_configs = json.loads(json_str)
    # Only device curves are serialized; expect two configurations.
    assert isinstance(curve_configs, list)
    assert len(curve_configs) == 2
    labels = [cfg["label"] for cfg in curve_configs]
    assert "bpm4i-bpm4i" in labels
    assert "bpm3a-bpm3a" in labels

    # Clear all curves.
    wf.clear_all()
    assert len(wf.plot_item.curves) == 0

    # Use the JSON setter to re-create the curves.
    wf.curve_json = json_str
    # After setting, the waveform should have two curves.
    assert len(wf.plot_item.curves) == 2
    new_labels = [curve.name() for curve in wf.plot_item.curves]
    for lab in labels:
        assert lab in new_labels


def test_curve_json_setter_ignores_custom(qtbot, mocked_client):
    """
    Test that when curve_json setter is given a JSON string containing a
    curve with source "custom", that curve is not added.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    device_curve_config = {
        "widget_class": "Curve",
        "parent_id": wf.gui_id,
        "label": "device_curve",
        "color": "#ff0000",
        "source": "device",
        "signal": {"name": "bpm4i", "entry": "bpm4i", "dap": None},
    }
    custom_curve_config = {
        "widget_class": "Curve",
        "parent_id": wf.gui_id,
        "label": "custom_curve",
        "color": "#00ff00",
        "source": "custom",
        # No signal for custom curves.
    }
    json_str = json.dumps([device_curve_config, custom_curve_config], indent=2)
    wf.curve_json = json_str
    # Only the device curve should be added.
    curves = wf.plot_item.curves
    assert len(curves) == 1
    assert curves[0].name() == "device_curve"


##################################################
# Waveform widget scan logic tests
##################################################


def test_update_sync_curves(monkeypatch, qtbot, mocked_client):
    """
    Test that update_sync_curves retrieves live data correctly and calls setData on sync curves.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="bpm4i")
    wf._sync_curves = [c]
    wf.x_mode = "timestamp"
    dummy_scan = create_dummy_scan_item()
    wf.scan_item = dummy_scan

    recorded = {}

    def fake_setData(x, y):
        recorded["x"] = x
        recorded["y"] = y

    monkeypatch.setattr(c, "setData", fake_setData)

    wf.update_sync_curves()
    np.testing.assert_array_equal(recorded.get("x"), [101, 201, 301])
    np.testing.assert_array_equal(recorded.get("y"), [5, 6, 7])


def test_update_async_curves(monkeypatch, qtbot, mocked_client):
    """
    Test that update_async_curves retrieves live data correctly and calls setData on async curves.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="async_device", label="async_device-async_device")
    wf._async_curves = [c]
    wf.x_mode = "timestamp"  # Timestamp is not supported, fallback to index.
    dummy_scan = create_dummy_scan_item()
    wf.scan_item = dummy_scan

    recorded = {}

    def fake_setData(x, y):
        recorded["x"] = x
        recorded["y"] = y

    monkeypatch.setattr(c, "setData", fake_setData)

    wf.update_async_curves()
    np.testing.assert_array_equal(recorded.get("x"), [0, 1, 2])
    np.testing.assert_array_equal(recorded.get("y"), [1, 2, 3])


def test_get_x_data_custom(monkeypatch, qtbot, mocked_client):
    """
    Test that _get_x_data returns the correct custom signal data.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    # Set x_mode to a custom mode.
    wf.x_axis_mode["name"] = "custom_signal"
    wf.x_axis_mode["entry"] = "custom_entry"
    dummy_data = DummyData(val=[50, 60, 70], timestamps=[150, 160, 170])
    dummy_live = {"custom_signal": {"custom_entry": dummy_data}}
    monkeypatch.setattr(wf, "_fetch_scan_data_and_access", lambda: (dummy_live, "val"))
    x_data = wf._get_x_data("irrelevant", "irrelevant")
    np.testing.assert_array_equal(x_data, [50, 60, 70])


def test_get_x_data_timestamp(monkeypatch, qtbot, mocked_client):
    """
    Test that _get_x_data returns the correct timestamp data.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_axis_mode["name"] = "timestamp"
    dummy_data = DummyData(val=[50, 60, 70], timestamps=[101, 202, 303])
    dummy_live = {"deviceX": {"entryX": dummy_data}}
    monkeypatch.setattr(wf, "_fetch_scan_data_and_access", lambda: (dummy_live, "val"))
    x_data = wf._get_x_data("deviceX", "entryX")
    np.testing.assert_array_equal(x_data, [101, 202, 303])


def test_categorise_device_curves(monkeypatch, qtbot, mocked_client):
    """
    Test that _categorise_device_curves correctly categorizes curves.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    dummy_scan = create_dummy_scan_item()
    wf.scan_item = dummy_scan

    c_sync = wf.plot(arg1="bpm4i", label="bpm4i-bpm4i")
    c_async = wf.plot(arg1="async_device", label="async_device-async_device")

    mode = wf._categorise_device_curves()

    assert mode == "mixed"
    assert c_sync in wf._sync_curves
    assert c_async in wf._async_curves


@pytest.mark.parametrize(
    ["mode", "calls"], [("sync", (1, 0)), ("async", (0, 1)), ("mixed", (1, 1))]
)
def test_on_scan_status(qtbot, mocked_client, monkeypatch, mode, calls):
    """
    Test that on_scan_status sets up a new scan correctly,
    categorizes curves, and triggers sync/async updates as needed.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    # Force creation of a couple of device curves
    if mode == "sync":
        wf.plot(arg1="bpm4i")
    elif mode == "async":
        wf.plot(arg1="async_device")
    else:
        wf.plot(arg1="bpm4i")
        wf.plot(arg1="async_device")

    # We mock out the scan_item, pretending we found a new scan.
    dummy_scan = create_dummy_scan_item()
    dummy_scan.metadata["bec"]["scan_id"] = "1234"
    monkeypatch.setattr(wf.queue.scan_storage, "find_scan_by_ID", lambda scan_id: dummy_scan)

    # We'll track calls to sync_signal_update and async_signal_update
    sync_spy = MagicMock()
    async_spy = MagicMock()
    wf.sync_signal_update.connect(sync_spy)
    wf.async_signal_update.connect(async_spy)

    # Prepare fake message data
    msg = {"scan_id": "1234"}
    meta = {}
    wf.on_scan_status(msg, meta)

    assert wf.scan_id == "1234"
    assert wf.scan_item == dummy_scan
    assert wf._mode == mode

    assert sync_spy.call_count == calls[0], "sync_signal_update should be called exactly once"
    assert async_spy.call_count == calls[1], "async_signal_update should be called exactly once"


def test_add_dap_curve(qtbot, mocked_client_with_dap, monkeypatch):
    """
    Test add_dap_curve creates a new DAP curve from an existing device curve
    and verifies that the DAP call doesn't fail due to mock-based plugin_info.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", label="bpm4i-bpm4i")

    dap_curve = wf.add_dap_curve(device_label="bpm4i-bpm4i", dap_name="GaussianModel")
    assert dap_curve is not None
    assert dap_curve.config.source == "dap"
    assert dap_curve.config.signal.name == "bpm4i"
    assert dap_curve.config.signal.dap == "GaussianModel"


def test_fetch_scan_data_and_access(qtbot, mocked_client, monkeypatch):
    """
    Test the _fetch_scan_data_and_access method returns live_data/val if in a live scan,
    or device dict/value if in a historical scan. Also test fallback if no scan_item.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    wf.scan_item = None

    hist_mock = MagicMock()
    monkeypatch.setattr(wf, "update_with_scan_history", hist_mock)

    wf._fetch_scan_data_and_access()
    hist_mock.assert_called_once_with(-1)

    # Ckeck live mode
    dummy_scan = create_dummy_scan_item()
    wf.scan_item = dummy_scan
    data_dict, access_key = wf._fetch_scan_data_and_access()
    assert data_dict == dummy_scan.live_data
    assert access_key == "val"

    # Check history mode
    del dummy_scan.live_data
    dummy_scan.devices = {"some_device": {"some_entry": "some_value"}}
    data_dict, access_key = wf._fetch_scan_data_and_access()
    assert "some_device" in data_dict  # from dummy_scan.devices
    assert access_key == "value"


def test_setup_async_curve(qtbot, mocked_client, monkeypatch):
    """
    Test that _setup_async_curve properly disconnects old signals
    and re-connects the async readback for a new scan ID.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.old_scan_id = "111"
    wf.scan_id = "222"

    c = wf.plot(arg1="async_device", label="async_device-async_device")
    # check that it was placed in _async_curves or so
    wf._async_curves = [c]

    # We'll spy on connect_slot
    connect_spy = MagicMock()
    monkeypatch.setattr(wf.bec_dispatcher, "connect_slot", connect_spy)

    wf._setup_async_curve(c)
    connect_spy.assert_called_once()
    endpoint_called = connect_spy.call_args[0][1].endpoint
    # We expect MessageEndpoints.device_async_readback('222', 'async_device')
    assert "222" in endpoint_called
    assert "async_device" in endpoint_called


def test_on_async_readback_add_update(qtbot, mocked_client):
    """
    Test that on_async_readback extends or replaces async data depending on metadata instruction.
    'Index' mode
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.scan_item = create_dummy_scan_item()
    c = wf.plot(arg1="async_device", label="async_device-async_device")
    wf._async_curves = [c]
    # Suppose existing data
    c.setData([0, 1, 2], [10, 11, 12])

    # Set the x_axis_mode
    wf.x_axis_mode["name"] = "index"

    ############# Test add ################

    msg = {"signals": {"async_device": {"value": [100, 200], "timestamp": [1001, 1002]}}}
    metadata = {"async_update": {"max_shape": [None], "type": "add"}}
    wf.on_async_readback(msg, metadata)

    x_data, y_data = c.get_data()
    assert len(x_data) == 5
    # Check x_data based on x_mode
    np.testing.assert_array_equal(x_data, [0, 1, 2, 3, 4])

    np.testing.assert_array_equal(y_data, [10, 11, 12, 100, 200])

    # instruction='replace'
    msg2 = {"signals": {"async_device": {"value": [999], "timestamp": [555]}}}
    metadata2 = {"async_update": {"max_shape": [None], "type": "replace"}}
    wf.on_async_readback(msg2, metadata2)
    x_data2, y_data2 = c.get_data()
    np.testing.assert_array_equal(x_data2, [0])

    np.testing.assert_array_equal(y_data2, [999])

    ############# Test add_slice ################

    # Few updates, no downsampling, no symbol removed
    waveform_shape = 10
    for ii in range(10):
        msg = {"signals": {"async_device": {"value": [100], "timestamp": [1001]}}}
        metadata = {
            "async_update": {"max_shape": [None, waveform_shape], "index": 0, "type": "add_slice"}
        }
        wf.on_async_readback(msg, metadata)

    # Old data should be deleted since the slice_index did not match
    x_data, y_data = c.get_data()
    assert len(y_data) == 10
    assert len(x_data) == 10
    assert c.opts["symbol"] == "o"

    # Clear data from curve
    c.setData([], [])

    # Test large updates, limit 1000 to deactivate symbols, downsampling for 8000 should be factor 2.
    waveform_shape = 100000
    n_cycles = 10
    for ii in range(n_cycles):
        msg = {
            "signals": {
                "async_device": {
                    "value": np.array(range(waveform_shape // n_cycles)),
                    "timestamp": (ii + 1)
                    * np.linspace(0, waveform_shape // n_cycles - 1, waveform_shape // n_cycles),
                }
            }
        }
        metadata = {
            "async_update": {"max_shape": [None, waveform_shape], "index": 0, "type": "add_slice"}
        }
        wf.on_async_readback(msg, metadata)
    x_data, y_data = c.get_data()
    assert len(y_data) == waveform_shape
    assert len(x_data) == waveform_shape
    assert c.opts["symbol"] == None
    # Get displayed data
    displayed_x, displayed_y = c.getData()
    assert len(displayed_y) == len(displayed_x)

    ############# Test replace ################
    waveform_shape = 10
    for ii in range(10):
        msg = {
            "signals": {
                "async_device": {
                    "value": np.array(range(waveform_shape)),
                    "timestamp": np.array(range(waveform_shape)),
                }
            }
        }
        metadata = {"async_update": {"type": "replace"}}
        wf.on_async_readback(msg, metadata)

    x_data, y_data = c.get_data()
    assert np.array_equal(y_data, np.array(range(waveform_shape)))
    assert len(x_data) == waveform_shape
    assert c.opts["symbol"] == "o"
    y_displayed, x_displayed = c.getData()
    assert len(y_displayed) == waveform_shape


def test_get_x_data(qtbot, mocked_client, monkeypatch):
    """
    Test _get_x_data logic for multiple modes: 'timestamp', 'index', 'custom', 'auto'.
    Use a dummy scan_item that returns specific data for the requested signal.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    dummy_scan = create_dummy_scan_item()
    wf.scan_item = dummy_scan

    # 1) x_mode == 'timestamp'
    wf.x_axis_mode["name"] = "timestamp"
    x_data = wf._get_x_data("bpm4i", "bpm4i")
    np.testing.assert_array_equal(x_data, [101, 201, 301])

    # 2) x_mode == 'index' => returns None => means use Y data indexing
    wf.x_axis_mode["name"] = "index"
    x_data2 = wf._get_x_data("bpm4i", "bpm4i")
    assert x_data2 is None

    # 3) custom x => e.g. "samx"
    wf.x_axis_mode["name"] = "samx"
    x_custom = wf._get_x_data("bpm4i", "bpm4i")
    # because dummy_scan.live_data["samx"]["samx"].val => [10,20,30]
    np.testing.assert_array_equal(x_custom, [10, 20, 30])

    # 4) auto
    wf._async_curves.clear()
    wf._sync_curves = [MagicMock()]  # pretend we have a sync device
    wf.x_axis_mode["name"] = "auto"
    x_auto = wf._get_x_data("bpm4i", "bpm4i")
    # By default it tries the "scan_report_devices" => "samx" => same as custom above
    np.testing.assert_array_equal(x_auto, [10, 20, 30])


##################################################
# The following tests are for the Curve class
##################################################


def test_curve_set_appearance_methods(qtbot, mocked_client):
    """
    Test that the Curve appearance setter methods update the configuration properly.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="appearance_curve")
    c.set_color("#0000ff")
    c.set_symbol("x")
    c.set_symbol_color("#ff0000")
    c.set_symbol_size(10)
    c.set_pen_width(3)
    c.set_pen_style("dashdot")
    assert c.config.color == "#0000ff"
    assert c.config.symbol == "x"
    assert c.config.symbol_color == "#ff0000"
    assert c.config.symbol_size == 10
    assert c.config.pen_width == 3
    assert c.config.pen_style == "dashdot"


def test_curve_set_custom_data(qtbot, mocked_client):
    """
    Test that custom curves allow setting new data via set_data.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="custom_data_curve")
    # Change data
    c.set_data([7, 8, 9], [10, 11, 12])
    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, np.array([7, 8, 9]))
    np.testing.assert_array_equal(y_data, np.array([10, 11, 12]))


def test_curve_set_data_error_non_custom(qtbot, mocked_client):
    """
    Test that calling set_data on a non-custom (device) curve raises a ValueError.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    # Create a device curve by providing y_name (which makes source 'device')
    # Assume that entry_validator returns a valid entry.
    c = wf.plot(arg1="bpm4i", label="device_curve")
    with pytest.raises(ValueError):
        c.set_data([1, 2, 3], [4, 5, 6])


def test_curve_remove(qtbot, mocked_client):
    """
    Test that calling remove() on a Curve calls its parent's remove_curve method.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c1 = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="curve_1")
    c2 = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="curve_2")

    assert len(wf.plot_item.curves) == 2
    c1.remove()
    assert len(wf.plot_item.curves) == 1
    assert c1 not in wf.plot_item.curves
    assert c2 in wf.plot_item.curves


def test_curve_dap_params_and_summary(qtbot, mocked_client):
    """
    Test that dap_params and dap_summary properties work as expected.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="dap_curve")
    c.dap_params = {"param": 1}
    c.dap_summary = {"summary": "test"}
    assert c.dap_params == {"param": 1}
    assert c.dap_summary == {"summary": "test"}


def test_curve_set_method(qtbot, mocked_client):
    """
    Test the convenience set(...) method of the Curve for updating appearance properties.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="set_method_curve")
    c.set(
        color="#123456",
        symbol="d",
        symbol_color="#654321",
        symbol_size=12,
        pen_width=5,
        pen_style="dot",
    )
    assert c.config.color == "#123456"
    assert c.config.symbol == "d"
    assert c.config.symbol_color == "#654321"
    assert c.config.symbol_size == 12
    assert c.config.pen_width == 5
    assert c.config.pen_style == "dot"


##################################################
# Settings and popups
##################################################


def test_show_curve_settings_popup(qtbot, mocked_client):
    """
    Test that show_curve_settings_popup displays the settings dialog and toggles the toolbar icon.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    curve_action = wf.toolbar.widgets["curve"].action
    assert not curve_action.isChecked(), "Should start unchecked"

    wf.show_curve_settings_popup()

    assert wf.curve_settings_dialog is not None
    assert wf.curve_settings_dialog.isVisible()
    assert curve_action.isChecked()

    wf.curve_settings_dialog.close()
    assert wf.curve_settings_dialog is None
    assert not curve_action.isChecked(), "Should be unchecked after closing dialog"


def test_show_dap_summary_popup(qtbot, mocked_client):
    """
    Test that show_dap_summary_popup displays the DAP summary dialog and toggles the 'fit_params' toolbar icon.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client, popups=True)

    assert "fit_params" in wf.toolbar.widgets

    fit_action = wf.toolbar.widgets["fit_params"].action
    assert fit_action.isChecked() is False

    wf.show_dap_summary_popup()

    assert wf.dap_summary_dialog is not None
    assert wf.dap_summary_dialog.isVisible()
    assert fit_action.isChecked() is True

    wf.dap_summary_dialog.close()
    assert wf.dap_summary_dialog is None
    assert fit_action.isChecked() is False
