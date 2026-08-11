from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock
from unittest.mock import MagicMock

import numpy as np
import pyqtgraph as pg
import pytest
from pyqtgraph.graphicsItems.DateAxisItem import DateAxisItem
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox

from bec_widgets.widgets.plots.plot_base import UIMode
from bec_widgets.widgets.plots.waveform.curve import DeviceSignal
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.services.scan_history_browser.scan_history_browser import (
    ScanHistoryBrowser,
)
from tests.unit_tests.client_mocks import (
    create_dummy_scan_item,
    dap_plugin_message,
    inject_scan_history,
    mocked_client,
    mocked_client_with_dap,
)

from .conftest import create_widget

# pylint: disable=unexpected-keyword-arg

##################################################
# Waveform widget base functionality tests
##################################################


def make_alignment_fit_summary(center: float | None = None) -> dict:
    params = []
    if center is not None:
        params.append(["center", center, True, None, -np.inf, np.inf, None, 0.1, {}, 0.0, None])
    params.append(["sigma", 0.5, True, None, 0.0, np.inf, None, 0.1, {}, 1.0, None])
    return {
        "model": "Model(test)",
        "method": "leastsq",
        "chisqr": 1.0,
        "redchi": 1.0,
        "rsquared": 0.99,
        "message": "Fit succeeded.",
        "params": params,
    }


##################################################
# DataAPI test helpers
##################################################


def _fake_bridge_factory(monkeypatch, gated_bytes: int | None = None):
    """
    Patch QtDataSubscription in the waveform module with a lightweight
    stand-in. Returns the list of created bridges (newest last).

    Args:
        gated_bytes(int | None): When given, every bridge created with a
            ``size_limit_bytes`` smaller than this value reports itself as
            size-gated with ``estimated_bytes = gated_bytes`` (mirrors the
            backend gate without any file I/O).
    """
    created = []

    class _FakeBridge:
        def __init__(
            self,
            client,
            sources,
            scan="live",
            parent=None,
            min_emit_interval=0.1,
            size_limit_bytes=None,
        ):
            self.client = client
            self.sources = list(sources)
            self.scan = scan
            self.scan_id = None if scan == "live" else scan
            self.healthy = True
            self.closed = False
            self.updated = MagicMock()
            self.size_limit_bytes = size_limit_bytes
            self.min_emit_interval = min_emit_interval
            self.estimated_bytes = gated_bytes
            self.size_gated = (
                gated_bytes is not None
                and size_limit_bytes is not None
                and gated_bytes > size_limit_bytes
            )
            self.confirmed = False

        def confirm_size(self):
            self.confirmed = True
            self.size_gated = False

        def close(self):
            self.closed = True

    def factory(
        client, sources, scan="live", parent=None, min_emit_interval=0.1, size_limit_bytes=None
    ):
        bridge = _FakeBridge(
            client,
            sources,
            scan=scan,
            min_emit_interval=min_emit_interval,
            size_limit_bytes=size_limit_bytes,
        )
        created.append(bridge)
        return bridge

    monkeypatch.setattr("bec_widgets.widgets.plots.waveform.waveform.QtDataSubscription", factory)
    return created


def _monitored_source(device, values, entry=None, timestamps=None, ordinals=None, as_numpy=False):
    from bec_lib.data_api.models import SourceData

    entry = entry or device
    ordinals = tuple(range(len(values))) if ordinals is None else tuple(ordinals)
    if timestamps is None:
        timestamps = tuple(float(i) for i in ordinals)
    wrap = (lambda seq: np.asarray(seq)) if as_numpy else tuple
    return SourceData(
        device=device,
        entry=entry,
        kind="monitored",
        ordinals=wrap(ordinals),
        values=wrap(values),
        timestamps=wrap(timestamps),
        complete=True,
    )


def _async_source(
    device,
    values,
    entry=None,
    timestamps=None,
    update_type="add",
    max_shape=(None,),
    kind="async",
    ordinals=None,
    as_numpy=False,
):
    from bec_lib.data_api.models import SourceData

    entry = entry or device
    ordinals = tuple(range(len(values))) if ordinals is None else tuple(ordinals)
    if timestamps is None:
        timestamps = tuple(float(i) for i in ordinals)
    wrap = (lambda seq: np.asarray(seq)) if as_numpy else tuple
    return SourceData(
        device=device,
        entry=entry,
        kind=kind,
        ordinals=wrap(ordinals),
        values=wrap(values),
        timestamps=wrap(timestamps),
        complete=True,
        metadata={
            "async_update_type": update_type,
            "max_shape": list(max_shape),
            "acquisition_group": None,
        },
    )


def _make_update(sources, scan_id="dummy", reason="live", group="scan"):
    from bec_lib.data_api.models import SubscriptionUpdate

    source_map = {source.key: source for source in sources}
    ordinal_sets = [set(source.ordinals) for source in source_map.values()]
    aligned = tuple(sorted(set.intersection(*ordinal_sets))) if ordinal_sets else ()
    return SubscriptionUpdate(
        scan_id=scan_id,
        reason=reason,
        sources=source_map,
        aligned_ordinals=aligned,
        complete=True,
        metadata={"group": group},
    )


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


def test_update_rate_reaches_bridge(qtbot, mocked_client, monkeypatch):
    """The widget's update_rate defines the bridge coalescing interval."""
    created = _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    assert wf.update_rate == 15.0  # Waveform default (benchmarked)
    wf.plot(arg1="bpm4i")
    assert created, "no data bridge was created"
    assert created[-1].min_emit_interval == pytest.approx(1.0 / 15.0)


def test_plot_single_arg_input_sync(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    c1 = wf.plot(arg1="bpm4i")
    c2 = wf.plot(arg1="bpm3a")

    assert c1.config.source == "device"
    assert c2.config.source == "device"
    assert c1.config.signal == DeviceSignal(device="bpm4i", signal="bpm4i", dap=None)
    assert c2.config.signal == DeviceSignal(device="bpm3a", signal="bpm3a", dap=None)

    # Check that the curve is added to the plot
    assert len(wf.plot_item.curves) == 2


def test_plot_single_arg_input_async(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    c1 = wf.plot(arg1="eiger")
    c2 = wf.plot(arg1="async_device")

    assert c1.config.source == "device"
    assert c2.config.source == "device"
    assert c1.config.signal == DeviceSignal(device="eiger", signal="eiger", dap=None)
    assert c2.config.signal == DeviceSignal(device="async_device", signal="async_device", dap=None)

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
        "signal": {"device": "bpm4i", "signal": "bpm4i", "dap": None},
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


def test_on_data_update_sync_timestamp_mode(monkeypatch, qtbot, mocked_client):
    """
    A monitored curve in timestamp mode is rendered from the aligned columns
    against the source timestamps.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="bpm4i")
    wf.x_mode = "timestamp"
    wf.scan_id = "dummy"

    update = _make_update(
        [_monitored_source("bpm4i", values=(5, 6, 7), timestamps=(101, 201, 301))]
    )
    wf._on_data_update(update)

    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [101, 201, 301])
    np.testing.assert_array_equal(y_data, [5, 6, 7])


def test_on_data_update_sync_index_mode(monkeypatch, qtbot, mocked_client):
    """
    A monitored curve in index mode is rendered against the aligned ordinals.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="bpm4i")
    wf.x_mode = "index"
    wf.scan_id = "dummy"

    wf._on_data_update(_make_update([_monitored_source("bpm4i", values=(5, 6, 7))]))

    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [0, 1, 2])
    np.testing.assert_array_equal(y_data, [5, 6, 7])


def test_on_data_update_sync_custom_x_device(monkeypatch, qtbot, mocked_client):
    """
    A monitored curve in custom device mode uses the aligned values of the x
    device delivered in the same update; a missing x source falls back to
    the index.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="bpm4i")
    wf.x_mode = "samx"
    wf.scan_id = "dummy"

    update = _make_update(
        [
            _monitored_source("bpm4i", values=(5, 6, 7)),
            _monitored_source("samx", values=(50, 60, 70)),
        ]
    )
    wf._on_data_update(update)

    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [50, 60, 70])
    np.testing.assert_array_equal(y_data, [5, 6, 7])
    assert wf._current_x_device == ("samx", "samx")

    # X source missing from the update -> index fallback
    wf._on_data_update(_make_update([_monitored_source("bpm4i", values=(5, 6, 7))]))
    x_data, _ = c.get_data()
    np.testing.assert_array_equal(x_data, [0, 1, 2])


def test_on_data_update_sync_auto_mode(monkeypatch, qtbot, mocked_client):
    """
    Auto mode resolves the x device from the scan report devices when no
    async curves are present, and falls back to the index otherwise.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="bpm4i")
    wf.scan_id = "dummy"
    wf.scan_item = create_dummy_scan_item()  # scan_report_devices == ["samx"]

    update = _make_update(
        [
            _monitored_source("bpm4i", values=(5, 6, 7)),
            _monitored_source("samx", values=(10, 20, 30)),
        ]
    )
    wf._on_data_update(update)

    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [10, 20, 30])
    np.testing.assert_array_equal(y_data, [5, 6, 7])
    assert wf._current_x_device == ("samx", "samx")

    # With an async curve present, auto mode falls back to index.
    wf._async_curves = [MagicMock()]
    wf._on_data_update(update)
    x_data, _ = c.get_data()
    np.testing.assert_array_equal(x_data, [0, 1, 2])
    assert wf._current_x_device is None


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


@pytest.mark.parametrize("mode", ["sync", "async", "mixed"])
def test_on_scan_status(qtbot, mocked_client, monkeypatch, mode):
    """
    Test that on_scan_status performs the per-scan bookkeeping (scan id,
    categorisation) and rebuilds the DataAPI subscription for the new scan.
    """
    bridges = _fake_bridge_factory(monkeypatch)
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

    n_bridges = len(bridges)
    wf.on_scan_status({"scan_id": "1234"}, {})

    assert wf.scan_id == "1234"
    assert wf.scan_item == dummy_scan
    assert wf._mode == mode

    # The DataAPI subscription is rebuilt for the new scan and follows it live.
    assert len(bridges) > n_bridges
    assert bridges[-1].scan == "live"
    expected_sources = []
    if mode in ("sync", "mixed"):
        expected_sources.append(("bpm4i", "bpm4i"))
    if mode in ("async", "mixed"):
        expected_sources.append(("async_device", "async_device"))
    for key in expected_sources:
        assert key in bridges[-1].sources
    if mode == "sync":
        # Auto mode resolves the x device from the scan report devices.
        assert ("samx", "samx") in bridges[-1].sources


def test_on_scan_status_ignored_without_device_curves(qtbot, mocked_client_with_dap, monkeypatch):
    """
    A widget with only custom/dap curves (no live scan to follow) must not have its
    scan_id -- and therefore its DAP request/response subscription -- reassigned by
    unrelated scan_status messages. Otherwise an in-flight DAP request can have its
    response dropped because the widget resubscribed to a different scan_id before
    the response arrived.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    x = np.linspace(-1, 1, 50)
    y = np.sin(x)
    wf.plot(x=x, y=y, label="custom-curve", dap="GaussianModel")

    dummy_scan = create_dummy_scan_item()
    dummy_scan.metadata["bec"]["scan_id"] = "unrelated-scan-1"
    monkeypatch.setattr(wf.queue.scan_storage, "find_scan_by_ID", lambda scan_id: dummy_scan)

    setup_dap_spy = MagicMock(wraps=wf.setup_dap_for_scan)
    monkeypatch.setattr(wf, "setup_dap_for_scan", setup_dap_spy)

    scan_id_before = wf.scan_id
    calls_before = setup_dap_spy.call_count

    wf.on_scan_status({"scan_id": "unrelated-scan-1"}, {})
    wf.on_scan_status({"scan_id": "unrelated-scan-2"}, {})

    assert wf.scan_id == scan_id_before
    assert setup_dap_spy.call_count == calls_before


def test_request_dap_skips_unchanged_static_parent(qtbot, mocked_client_with_dap, monkeypatch):
    """
    DAP curves whose parent is a static custom curve must not be resubmitted by
    scan-driven request_dap calls when the fit inputs are unchanged. Changing the
    custom data (or the oversample) triggers exactly one new request.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    curve = wf.plot(x=[0, 1, 2], y=[1, 2, 3], label="custom-static", dap="GaussianModel")
    dap_curve = wf.get_curve(f"{curve.name()}-GaussianModel")
    assert dap_curve is not None

    published = []
    monkeypatch.setattr(
        wf.client.connector,
        "set_and_publish",
        lambda topic, msg, *args, **kwargs: published.append(msg),
    )

    # The creation-time request already stored a fingerprint; identical inputs are skipped
    wf.request_dap()
    wf.request_dap()
    assert len(published) == 0

    # New custom data -> one new request, further identical calls skipped again
    curve.set_data([0, 1, 2], [3, 2, 1])
    wf.request_dap()
    wf.request_dap()
    assert len(published) == 1

    # Oversample change requests immediately via the setter and updates the fingerprint
    dap_curve.dap_oversample = 4
    assert len(published) == 2
    wf.request_dap()
    assert len(published) == 2


def test_request_dap_resubmits_on_roi_change_for_static_parent(
    qtbot, mocked_client_with_dap, monkeypatch
):
    """
    Changing the linear region selector changes the cropped fit inputs, so a DAP
    curve with a static custom parent must be resubmitted even though the parent
    data itself did not change.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    x = np.linspace(0, 10, 50)
    wf.plot(x=x, y=np.sin(x), label="custom-roi", dap="GaussianModel")

    published = []
    monkeypatch.setattr(
        wf.client.connector,
        "set_and_publish",
        lambda topic, msg, *args, **kwargs: published.append(msg),
    )

    wf.request_dap()
    assert len(published) == 0

    wf.roi_region = (2.0, 8.0)
    wf.request_dap()
    assert len(published) == 1
    assert len(published[0].content["config"]["kwargs"]["data_x"]) < len(x)

    # Same region again -> no resubmission
    wf.request_dap()
    assert len(published) == 1

    # Removing the region restores the full data set -> one resubmission
    wf.roi_region = None
    wf.request_dap()
    assert len(published) == 2


def test_request_dap_releases_proxy_when_nothing_published(
    qtbot, mocked_client_with_dap, monkeypatch
):
    """
    When request_dap skips every DAP curve (static parents, unchanged inputs), no
    dap_response will arrive to unblock proxy_dap_request. The proxy must be
    released immediately, otherwise the next trigger (e.g. an ROI change) would be
    delayed by the proxy timeout.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(x=[0, 1, 2], y=[1, 2, 3], label="custom-blocked", dap="GaussianModel")

    monkeypatch.setattr(
        wf.client.connector, "set_and_publish", lambda topic, msg, *args, **kwargs: None
    )

    wf.request_dap_update.emit()
    assert wf.proxy_dap_request.blocked is True
    # The proxy timeout is 10 s; the no-publish call must release it much earlier
    qtbot.waitUntil(lambda: wf.proxy_dap_request.blocked is False, timeout=3000)


def test_request_dap_always_resubmits_device_parent(qtbot, mocked_client_with_dap, monkeypatch):
    """
    DAP curves attached to device curves keep the resubmit-on-every-update behavior,
    since their parent data changes as the scan progresses.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", label="bpm4i-bpm4i", dap="GaussianModel")

    published = []
    monkeypatch.setattr(
        wf.client.connector,
        "set_and_publish",
        lambda topic, msg, *args, **kwargs: published.append(msg),
    )

    wf.request_dap()
    wf.request_dap()
    assert len(published) == 2


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
    assert dap_curve.config.signal.device == "bpm4i"
    assert dap_curve.config.signal.dap == "GaussianModel"


def test_add_dap_curve_custom_source(qtbot, mocked_client_with_dap):
    """
    Ensure that custom curves can also serve as parents for DAP fits.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    x = np.linspace(-1, 1, 50)
    y = np.sin(x)
    custom_curve = wf.plot(x=x, y=y, label="custom-curve")

    dap_curve = wf.add_dap_curve(device_label=custom_curve.name(), dap_name="GaussianModel")
    assert dap_curve.config.source == "dap"
    assert dap_curve.config.parent_label == custom_curve.name()
    assert dap_curve.config.signal.device == custom_curve.name()
    assert dap_curve.config.signal.signal == "custom"
    assert dap_curve.config.signal.dap == "GaussianModel"


def test_alignment_mode_toggle_shows_bottom_panel(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    action = wf.toolbar.components.get_action("alignment_mode").action
    action.trigger()

    assert wf._alignment_panel_visible is True
    assert wf._alignment_side_panel.panel_visible is True
    assert action.isChecked() is True

    action.trigger()

    assert wf._alignment_panel_visible is False
    assert wf._alignment_side_panel.panel_visible is False
    assert action.isChecked() is False


def test_resolve_alignment_positioner(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    wf.x_mode = "samx"
    assert wf._resolve_alignment_positioner() == "samx"

    wf.x_mode = "auto"
    wf._current_x_device = ("samx", "samx")
    assert wf._resolve_alignment_positioner() == "samx"

    wf._current_x_device = ("bpm4i", "bpm4i")
    assert wf._resolve_alignment_positioner() is None

    wf.x_mode = "index"
    assert wf._resolve_alignment_positioner() is None

    wf.x_mode = "timestamp"
    assert wf._resolve_alignment_positioner() is None


def test_alignment_panel_updates_when_auto_x_motor_changes(
    qtbot, mocked_client_with_dap, monkeypatch
):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", dap="GaussianModel")
    wf.x_mode = "auto"
    wf.toolbar.components.get_action("alignment_mode").action.trigger()

    wf._current_x_device = ("samx", "samx")
    wf._alignment_panel.set_positioner_device("samx")
    wf.scan_item = create_dummy_scan_item()
    # A real scan carries the report devices on its (in-memory) status
    # message; the data file is only the last-resort source.
    wf.scan_item.status_message.info["scan_report_devices"] = ["samy"]
    wf.scan_item.metadata["bec"]["scan_report_devices"] = ["samy"]

    # Rendering a DataAPI update re-resolves the auto x device from the scan
    # report devices and refreshes the alignment state.
    wf._resolve_x_axis()

    assert wf._current_x_device == ("samy", "samy")
    assert wf._alignment_positioner_name == "samy"
    assert wf._alignment_panel.positioner.device == "samy"


def test_alignment_panel_disables_without_positioner(qtbot, mocked_client_with_dap):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i")
    wf.x_mode = "index"

    wf.toolbar.components.get_action("alignment_mode").action.trigger()

    assert wf._alignment_panel.positioner.isEnabled() is False
    assert "positioner on the x axis" in wf._alignment_panel.status_label.text()


def test_alignment_marker_updates_from_positioner_readback(qtbot, mocked_client_with_dap):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", dap="GaussianModel")
    wf.x_mode = "samx"

    wf.toolbar.components.get_action("alignment_mode").action.trigger()
    wf.dev["samx"].signals["samx"]["value"] = 4.2
    wf._alignment_panel.positioner.force_update_readback()

    assert wf._alignment_controller is not None
    assert wf._alignment_controller.marker_line is not None
    assert np.isclose(wf._alignment_controller.marker_line.value(), 4.2)
    assert "samx" in wf._alignment_controller.marker_line.label.toPlainText()
    assert "4.200" in wf._alignment_controller.marker_line.label.toPlainText()


def test_alignment_panel_uses_existing_dap_curves_and_moves_positioner(
    qtbot, mocked_client_with_dap
):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    source_curve = wf.plot(arg1="bpm4i")
    dap_curve = wf.add_dap_curve(device_label=source_curve.name(), dap_name="GaussianModel")
    wf.x_mode = "samx"

    wf.toolbar.components.get_action("alignment_mode").action.trigger()
    fit_summary = make_alignment_fit_summary(center=2.5)
    wf.dap_summary_update.emit(fit_summary, {"curve_id": dap_curve.name()})
    wf._alignment_panel.fit_dialog.select_curve(dap_curve.name())

    move_spy = MagicMock()
    wf.dev["samx"].move = move_spy

    assert wf._alignment_panel.fit_dialog.fit_curve_id == dap_curve.name()
    assert wf._alignment_panel.fit_dialog.action_buttons["center"].isEnabled() is True

    wf._alignment_panel.fit_dialog.action_buttons["center"].click()

    move_spy.assert_called_once_with(2.5, relative=False)


def test_alignment_target_line_toggle_updates_target_value_label(qtbot, mocked_client_with_dap):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", dap="GaussianModel")
    wf.x_mode = "samx"

    wf.toolbar.components.get_action("alignment_mode").action.trigger()
    wf._alignment_panel.target_toggle.setChecked(True)

    assert wf._alignment_controller is not None
    assert wf._alignment_controller.target_line is not None
    assert wf._alignment_panel.move_to_target_button.isEnabled() is True

    wf._alignment_controller.target_line.setValue(1.5)

    assert "1.500" in wf._alignment_panel.target_toggle.text()


def test_alignment_move_to_target_uses_draggable_line_value(qtbot, mocked_client_with_dap):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", dap="GaussianModel")
    wf.x_mode = "samx"

    wf.toolbar.components.get_action("alignment_mode").action.trigger()
    wf._alignment_panel.target_toggle.setChecked(True)
    wf._alignment_controller.target_line.setValue(1.25)

    move_spy = MagicMock()
    wf.dev["samx"].move = move_spy

    wf._alignment_panel.move_to_target_button.click()

    move_spy.assert_called_once_with(1.25, relative=False)


def test_alignment_mode_toggle_off_keeps_user_dap_curve(qtbot, mocked_client_with_dap):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    source_curve = wf.plot(arg1="bpm4i")
    dap_curve = wf.add_dap_curve(device_label=source_curve.name(), dap_name="GaussianModel")
    wf.x_mode = "samx"

    action = wf.toolbar.components.get_action("alignment_mode").action
    action.trigger()
    action.trigger()

    assert wf.get_curve(dap_curve.name()) is not None


def test_alignment_mode_toggle_off_clears_controller_overlays(qtbot, mocked_client_with_dap):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", dap="GaussianModel")
    wf.x_mode = "samx"

    action = wf.toolbar.components.get_action("alignment_mode").action
    action.trigger()
    wf._alignment_panel.target_toggle.setChecked(True)
    wf.dev["samx"].signals["samx"]["value"] = 2.0
    wf._alignment_panel.positioner.force_update_readback()

    assert wf._alignment_controller.marker_line is not None
    assert wf._alignment_controller.target_line is not None

    action.trigger()

    assert wf._alignment_controller.marker_line is None
    assert wf._alignment_controller.target_line is None


def test_alignment_panel_removes_deleted_dap_curve_from_fit_list(qtbot, mocked_client_with_dap):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    source_curve = wf.plot(arg1="bpm4i")
    dap_curve = wf.add_dap_curve(device_label=source_curve.name(), dap_name="GaussianModel")

    wf.toolbar.components.get_action("alignment_mode").action.trigger()
    wf.dap_summary_update.emit(
        make_alignment_fit_summary(center=1.5), {"curve_id": dap_curve.name()}
    )

    assert dap_curve.name() in wf._alignment_panel.fit_dialog.summary_data

    wf.remove_curve(dap_curve.name())

    assert dap_curve.name() not in wf._alignment_panel.fit_dialog.summary_data


def test_alignment_controller_move_request_moves_positioner(qtbot, mocked_client_with_dap):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", dap="GaussianModel")
    wf.x_mode = "samx"

    move_spy = MagicMock()
    wf.dev["samx"].move = move_spy

    wf.toolbar.components.get_action("alignment_mode").action.trigger()
    wf._alignment_controller.move_absolute_requested.emit(3.5)

    move_spy.assert_called_once_with(3.5, relative=False)


def test_curve_set_data_emits_dap_update(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(x=[1, 2, 3], y=[4, 5, 6], label="test_curve")
    with qtbot.waitSignal(wf.request_dap_update):
        c.set_data([7, 8, 9], [10, 11, 12])


def test_plot_custom_curve_with_inline_dap(qtbot, mocked_client_with_dap):
    """
    Supplying the `dap` kwarg when plotting custom data should auto-create the fit curve.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    curve = wf.plot(x=[0, 1, 2], y=[1, 2, 3], label="custom-inline", dap="GaussianModel")

    dap_curve = wf.get_curve(f"{curve.name()}-GaussianModel")
    assert dap_curve is not None
    assert dap_curve.config.parent_label == curve.name()
    assert dap_curve.config.signal.dap == "GaussianModel"


def test_normalize_dap_parameters_number_dict():
    normalized = Waveform._normalize_dap_parameters({"amplitude": 1.0, "center": 2})
    assert normalized == {
        "amplitude": {"name": "amplitude", "value": 1.0, "vary": False},
        "center": {"name": "center", "value": 2.0, "vary": False},
    }


def test_normalize_dap_parameters_dict_spec_defaults_vary_false():
    normalized = Waveform._normalize_dap_parameters({"sigma": {"value": 0.8, "min": 0.0}})
    assert normalized["sigma"]["name"] == "sigma"
    assert normalized["sigma"]["value"] == 0.8
    assert normalized["sigma"]["min"] == 0.0
    assert normalized["sigma"]["vary"] is False


def test_normalize_dap_parameters_invalid_type_raises():
    with pytest.raises(TypeError):
        Waveform._normalize_dap_parameters(["amplitude", 1.0])  # type: ignore[arg-type]


def test_normalize_dap_parameters_composite_list():
    normalized = Waveform._normalize_dap_parameters(
        [{"center": 1.0}, {"sigma": {"value": 0.5, "min": 0.0}}],
        dap_name=["GaussianModel", "GaussianModel"],
    )
    assert normalized == [
        {"center": {"name": "center", "value": 1.0, "vary": False}},
        {"sigma": {"name": "sigma", "value": 0.5, "min": 0.0, "vary": False}},
    ]


def test_normalize_dap_parameters_composite_dict():
    normalized = Waveform._normalize_dap_parameters(
        {
            "GaussianModel": {"center": {"value": 1.0, "vary": True}},
            "LorentzModel": {"amplitude": 2.0},
        },
        dap_name=["GaussianModel", "LorentzModel"],
    )
    assert normalized["GaussianModel"]["center"]["value"] == 1.0
    assert normalized["GaussianModel"]["center"]["vary"] is True
    assert normalized["LorentzModel"]["amplitude"]["value"] == 2.0
    assert normalized["LorentzModel"]["amplitude"]["vary"] is False


def test_request_dap_includes_normalized_parameters(qtbot, mocked_client_with_dap, monkeypatch):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)

    captured = {}

    def capture(topic, msg, *args, **kwargs):  # noqa: ARG001
        captured["topic"] = topic
        captured["msg"] = msg

    monkeypatch.setattr(wf.client.connector, "set_and_publish", capture)

    curve = wf.plot(
        x=[0, 1, 2],
        y=[1, 2, 3],
        label="custom-inline-params",
        dap="GaussianModel",
        dap_parameters={"amplitude": 1.0},
    )
    dap_curve = wf.get_curve(f"{curve.name()}-GaussianModel")
    assert dap_curve is not None
    # The oversample setter issues a fresh DAP request with the new value
    dap_curve.dap_oversample = 3

    msg = captured["msg"]
    dap_kwargs = msg.content["config"]["kwargs"]
    assert dap_kwargs["oversample"] == 3
    assert dap_kwargs["parameters"] == {
        "amplitude": {"name": "amplitude", "value": 1.0, "vary": False}
    }


def test_request_dap_includes_composite_parameters_list(qtbot, mocked_client_with_dap, monkeypatch):
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)

    captured = {}

    def capture(topic, msg, *args, **kwargs):  # noqa: ARG001
        captured["topic"] = topic
        captured["msg"] = msg

    monkeypatch.setattr(wf.client.connector, "set_and_publish", capture)

    curve = wf.plot(
        x=[0, 1, 2],
        y=[1, 2, 3],
        label="custom-composite",
        dap=["GaussianModel", "GaussianModel"],
        dap_parameters=[{"center": 0.0}, {"center": 1.0}],
    )
    dap_curve = wf.get_curve(f"{curve.name()}-GaussianModel+GaussianModel")
    assert dap_curve is not None

    msg = captured["msg"]
    dap_kwargs = msg.content["config"]["kwargs"]
    assert dap_kwargs["parameters"] == [
        {"center": {"name": "center", "value": 0.0, "vary": False}},
        {"center": {"name": "center", "value": 1.0, "vary": False}},
    ]
    assert msg.content["config"]["class_kwargs"]["model"] == ["GaussianModel", "GaussianModel"]


# NOTE: the legacy pull path (_fetch_scan_data_and_access, update_sync_curves,
# update_async_curves, _setup_async_curve, on_async_readback, _get_x_data) was
# replaced by the DataAPI subscription; its behaviour is asserted through the
# _on_data_update tests below.


def test_async_curve_sources_in_subscription(qtbot, mocked_client, monkeypatch):
    """
    Async curves are served by the DataAPI subscription (the backend resolves
    the async endpoints); their (device, entry) pairs are part of the bridge
    sources and are not duplicated.
    """
    bridges = _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    wf.plot(arg1="async_device", label="async_device-async_device")
    first_bridge = bridges[-1]
    assert ("async_device", "async_device") in first_bridge.sources

    # A second curve on the same signal replaces the subscription without
    # duplicating the source.
    wf.plot(arg1="async_device", label="second-curve")
    assert first_bridge.closed is True
    assert bridges[-1].sources.count(("async_device", "async_device")) == 1


def test_on_data_update_async_add(qtbot, mocked_client, monkeypatch):
    """
    An async 'add' source concatenates its fragments (1-D max_shape); a
    'replace' source displays only the current full state.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="async_device", label="async_device-async_device")
    wf.scan_id = "dummy"
    wf.x_axis_mode["name"] = "index"

    # 'add': fragments accumulate into one displayed series
    source = _async_source(
        "async_device", values=([10, 11, 12], [100, 200]), update_type="add", max_shape=(None,)
    )
    wf._on_data_update(_make_update([source]))

    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [0, 1, 2, 3, 4])
    np.testing.assert_array_equal(y_data, [10, 11, 12, 100, 200])

    # 'replace': only the last full state is shown
    source = _async_source("async_device", values=([999],), update_type="replace")
    wf._on_data_update(_make_update([source]))
    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [0])
    np.testing.assert_array_equal(y_data, [999])


def test_on_data_update_async_add_2d(qtbot, mocked_client, monkeypatch):
    """
    An async 'add' source with a 2-D max_shape displays the latest waveform.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="async_device", label="async_device-async_device")
    wf.scan_id = "dummy"
    wf.x_axis_mode["name"] = "index"

    source = _async_source(
        "async_device", values=([1, 2, 3], [4, 5, 6]), update_type="add", max_shape=(None, 3)
    )
    wf._on_data_update(_make_update([source]))

    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [0, 1, 2])
    np.testing.assert_array_equal(y_data, [4, 5, 6])


def test_on_data_update_async_add_slice(qtbot, mocked_client, monkeypatch):
    """
    An async 'add_slice' source displays the last accumulated row. Small rows
    keep the symbol, large rows activate the downsampling settings.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="async_device", label="async_device-async_device")
    wf.scan_id = "dummy"
    wf.x_axis_mode["name"] = "index"

    # Small accumulated row: symbol stays, no downsampling
    source = _async_source(
        "async_device",
        values=([100] * 10,),
        ordinals=(0,),
        update_type="add_slice",
        max_shape=(None, 10),
    )
    wf._on_data_update(_make_update([source]))
    x_data, y_data = c.get_data()
    assert len(y_data) == 10
    assert len(x_data) == 10
    assert c.opts["symbol"] == "o"

    # Large accumulated row: symbol removed, downsampling active
    waveform_shape = 100000
    source = _async_source(
        "async_device",
        values=(np.arange(waveform_shape),),
        ordinals=(0,),
        update_type="add_slice",
        max_shape=(None, waveform_shape),
    )
    wf._on_data_update(_make_update([source]))
    x_data, y_data = c.get_data()
    assert len(y_data) == waveform_shape
    assert len(x_data) == waveform_shape
    assert c.opts["symbol"] is None
    displayed_x, displayed_y = c.getData()
    assert len(displayed_y) == len(displayed_x)


def test_on_data_update_async_timestamp_mode(qtbot, mocked_client, monkeypatch):
    """
    Async curves in timestamp mode use the source timestamps when they match
    the displayed length and fall back to index otherwise.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="async_device", label="async_device-async_device")
    wf.scan_id = "dummy"
    wf.x_axis_mode["name"] = "timestamp"

    # One timestamp per single-sample fragment: lengths match -> timestamps
    source = _async_source(
        "async_device", values=([1], [2], [3]), timestamps=(11, 21, 31), update_type="add"
    )
    wf._on_data_update(_make_update([source]))
    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [11, 21, 31])
    np.testing.assert_array_equal(y_data, [1, 2, 3])

    # One timestamp for a multi-sample fragment: length mismatch -> index
    source = _async_source("async_device", values=([1, 2, 3],), timestamps=(11,), update_type="add")
    wf._on_data_update(_make_update([source]))
    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [0, 1, 2])
    np.testing.assert_array_equal(y_data, [1, 2, 3])


def test_on_data_update_async_history_rows(qtbot, mocked_client, monkeypatch):
    """
    History emissions carry no async-update metadata: scalar rows form the
    full series, array rows display the last row (mirrors the legacy 2-D
    behaviour).
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="async_device", label="async_device-async_device")
    wf.scan_id = "dummy"
    wf.x_axis_mode["name"] = "index"

    # Scalar rows (1-D dataset)
    source = _async_source("async_device", values=(1, 2, 3), update_type=None, max_shape=())
    wf._on_data_update(_make_update([source], reason="history"))
    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [0, 1, 2])
    np.testing.assert_array_equal(y_data, [1, 2, 3])

    # Array rows (2-D dataset): last row is displayed
    source = _async_source(
        "async_device", values=([1, 2, 3], [4, 5, 6]), update_type=None, max_shape=()
    )
    wf._on_data_update(_make_update([source], reason="history"))
    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [0, 1, 2])
    np.testing.assert_array_equal(y_data, [4, 5, 6])


def test_on_data_update_async_add_incremental_matches_full_rebuild(
    qtbot, mocked_client, monkeypatch
):
    """
    The incremental 1-D 'add' render path must yield exactly the series the
    from-scratch concatenation yields, across live appends (contiguous and
    gapped), an unchanged reused snapshot, an out-of-order hole-fill, a
    non-live reason and a scan change — and must only fall back to the full
    rebuild for the emissions that cannot be pure appends.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c = wf.plot(arg1="async_device", label="async_device-async_device")
    wf.scan_id = None  # render updates of any scan
    wf.x_axis_mode["name"] = "index"

    from_scratch = Waveform._async_display_values
    rebuilds = []

    def counting(source):
        rebuilds.append(source)
        return from_scratch(source)

    monkeypatch.setattr(Waveform, "_async_display_values", staticmethod(counting))

    steps = [
        # (scan_id, reason, values, ordinals, expected rebuild count so far)
        ("scan_1", "live", ([0.0, 1.0],), (0,), 1),  # first emission seeds the cache
        ("scan_1", "live", ([0.0, 1.0], [2.0]), (0, 1), 1),  # append
        ("scan_1", "live", ([0.0, 1.0], [2.0]), (0, 1), 1),  # unchanged reused snapshot
        ("scan_1", "live", ([0.0, 1.0], [2.0], [4.0, 5.0]), (0, 1, 3), 1),  # gapped append
        # late hole-fill below the frontier -> full rebuild
        ("scan_1", "live", ([0.0, 1.0], [2.0], [3.0], [4.0, 5.0]), (0, 1, 2, 3), 2),
        ("scan_1", "live", ([0.0, 1.0], [2.0], [3.0], [4.0, 5.0], [6.0]), (0, 1, 2, 3, 4), 2),
        # non-live reason -> full rebuild
        ("scan_1", "backfill", ([0.0, 1.0], [2.0], [3.0], [4.0, 5.0], [6.0]), tuple(range(5)), 3),
        ("scan_2", "live", ([7.0],), (0,), 4),  # scan change -> full rebuild
        ("scan_2", "live", ([7.0], [8.0, 9.0]), (0, 1), 4),  # incremental resumes
    ]
    for scan_id, reason, values, ordinals, expected_rebuilds in steps:
        source = _async_source("async_device", values=values, ordinals=ordinals, update_type="add")
        wf._on_data_update(_make_update([source], scan_id=scan_id, reason=reason))
        x_data, y_data = c.get_data()
        expected = from_scratch(source)
        np.testing.assert_array_equal(y_data, expected)
        np.testing.assert_array_equal(x_data, np.arange(len(expected)))
        assert len(rebuilds) == expected_rebuilds


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
    # Create a device curve by providing device_y (which makes source 'device')
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

    curve_action = wf.toolbar.components.get_action("curve").action
    assert not curve_action.isChecked(), "Should start unchecked"

    wf.show_curve_settings_popup()

    assert wf.curve_settings_dialog is not None
    assert wf.curve_settings_dialog.isVisible()
    assert curve_action.isChecked()

    # add a new row to the curve tree
    add_action = wf.curve_settings_dialog.widget.curve_manager.toolbar.components.get_action("add")
    add_action.action.trigger()
    add_action.action.trigger()
    qtbot.wait(100)
    # Check that the new row is added
    assert wf.curve_settings_dialog.widget.curve_manager.tree.model().rowCount() == 2

    wf.curve_settings_dialog.close()
    assert wf.curve_settings_dialog is None
    assert not curve_action.isChecked(), "Should be unchecked after closing dialog"


def test_show_dap_summary_popup(qtbot, mocked_client):
    """
    Test that show_dap_summary_popup displays the DAP summary dialog and toggles the 'fit_params' toolbar icon.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client, popups=True)

    assert wf.toolbar.components.exists("fit_params")

    fit_action = wf.toolbar.components.get_action("fit_params").action
    assert fit_action.isChecked() is False

    wf.show_dap_summary_popup()

    assert wf.dap_summary_dialog is not None
    assert wf.dap_summary_dialog.isVisible()
    assert fit_action.isChecked() is True

    wf.dap_summary_dialog.close()
    assert wf.dap_summary_dialog is None
    assert fit_action.isChecked() is False


def test_show_scan_history_popup(qtbot, mocked_client):
    """
    Test that show_scan_history_popup displays the scan history browser dialog
    and toggles the toolbar action correctly.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    scan_action = wf.toolbar.components.get_action("scan_history").action
    # Initially unchecked and no dialog
    assert not scan_action.isChecked()
    assert wf.scan_history_dialog is None

    # Show the popup
    wf.show_scan_history_popup()
    # Dialog should exist and be visible, action checked
    assert wf.scan_history_dialog is not None
    assert wf.scan_history_dialog.isVisible()
    assert scan_action.isChecked()
    # The embedded widget should be the correct type
    assert isinstance(wf.scan_history_widget, ScanHistoryBrowser)

    # Close the dialog (triggers _scan_history_closed)
    wf.scan_history_dialog.close()
    # Dialog reference should be cleared and action unchecked
    assert wf.scan_history_dialog is None
    assert not scan_action.isChecked()


#####################################################
# The following tests are for the dataset-size guard
#####################################################


def test_skip_large_dataset_warning_property(qtbot, mocked_client, monkeypatch):
    """
    Verify the getter and setter of skip_large_dataset_warning work correctly.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    # Default should be False
    assert wf.skip_large_dataset_warning is False

    # Set to True
    wf.skip_large_dataset_warning = True
    assert wf.skip_large_dataset_warning is True

    # Toggle back to False
    wf.skip_large_dataset_warning = False
    assert wf.skip_large_dataset_warning is False


def test_skip_large_dataset_check_property(qtbot, mocked_client, monkeypatch):
    """
    Verify the getter and setter of the per-plot skip_large_dataset_check flag.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    assert wf.skip_large_dataset_check is False
    wf.skip_large_dataset_check = True
    assert wf.skip_large_dataset_check is True


def test_max_dataset_size_mb_property(qtbot, mocked_client, monkeypatch):
    """
    Verify getter, setter, and validation of max_dataset_size_mb.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    # Default from WaveformConfig is 10 MB
    assert wf.max_dataset_size_mb == 10

    # Set to a valid new value
    wf.max_dataset_size_mb = 5.5
    assert wf.max_dataset_size_mb == 5.5
    # Ensure the config is updated too
    assert wf.config.max_dataset_size_mb == 5.5

    # The config survives a round-trip through the widget config dict
    assert wf._config_dict["max_dataset_size_mb"] == 5.5


def _oversized(monkeypatch, wf, size_mb=50.0, shape=(100, 1000)):
    """Make every source of the widget look oversized, with a known shape."""
    monkeypatch.setattr(
        Waveform, "_estimate_source_bytes", lambda self, scan, source: int(size_mb * 1024 * 1024)
    )
    monkeypatch.setattr(Waveform, "_stored_shape", lambda self, scan, device, entry: shape)
    return wf


def test_small_dataset_loads_without_prompt(qtbot, mocked_client, monkeypatch):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    monkeypatch.setattr(Waveform, "_estimate_source_bytes", lambda self, scan, source: 1024)
    with mock.patch.object(wf, "_confirm_large_dataset") as dialog:
        kept = wf._filter_oversized_sources([("bpm4i", "bpm4i")], "scan-1")
    dialog.assert_not_called()
    assert kept == [("bpm4i", "bpm4i")]


def test_live_and_skip_check_bypass_the_gate(qtbot, mocked_client, monkeypatch):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    _oversized(monkeypatch, wf)
    sources = [("waveform", "waveform_waveform")]
    with mock.patch.object(wf, "_confirm_large_dataset") as dialog:
        assert wf._filter_oversized_sources(sources, "live") == sources
        assert wf._filter_oversized_sources(sources, None) == sources
        wf.skip_large_dataset_check = True
        assert wf._filter_oversized_sources(sources, "scan-1") == sources
    dialog.assert_not_called()


def test_oversized_dataset_prompts_per_dataset_and_loads_on_accept(
    qtbot, mocked_client, monkeypatch
):
    """The user decides per dataset; an accepted dataset is loaded and is not
    re-prompted when the subscription is rebuilt."""
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    _oversized(monkeypatch, wf, size_mb=50.0, shape=(100, 1000))
    sources = [("waveform", "waveform_waveform"), ("bpm4i", "bpm4i")]

    with mock.patch.object(wf, "_confirm_large_dataset", return_value=True) as dialog:
        kept = wf._filter_oversized_sources(sources, "scan-1")
    assert kept == sources
    # One prompt per dataset, carrying the dataset identity and its shape.
    assert dialog.call_count == 2
    first = dialog.call_args_list[0]
    assert first.kwargs["source"] == ("waveform", "waveform_waveform")
    assert first.kwargs["shape"] == (100, 1000)
    assert first.args[0] == pytest.approx(50.0)

    with mock.patch.object(wf, "_confirm_large_dataset") as dialog2:
        assert wf._filter_oversized_sources(sources, "scan-1") == sources
    dialog2.assert_not_called()


def test_declined_dataset_is_not_loaded_but_others_are(qtbot, mocked_client, monkeypatch):
    """Declining drops only that dataset — the curve stays (empty), it is not
    hidden, and the remaining datasets still load."""
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    def estimate(self, scan, source):
        return 50 * 1024 * 1024 if source[0] == "waveform" else 1024

    monkeypatch.setattr(Waveform, "_estimate_source_bytes", estimate)
    monkeypatch.setattr(Waveform, "_stored_shape", lambda self, scan, device, entry: (100, 1000))
    sources = [("waveform", "waveform_waveform"), ("bpm4i", "bpm4i")]

    with mock.patch.object(wf, "_confirm_large_dataset", return_value=False) as dialog:
        kept = wf._filter_oversized_sources(sources, "scan-1")
    dialog.assert_called_once()
    assert kept == [("bpm4i", "bpm4i")]


def test_skip_large_dataset_warning_suppresses_dialog(qtbot, mocked_client, monkeypatch):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    _oversized(monkeypatch, wf)
    wf.skip_large_dataset_warning = True
    with mock.patch.object(wf, "_confirm_large_dataset") as dialog:
        kept = wf._filter_oversized_sources([("waveform", "waveform_waveform")], "scan-1")
    dialog.assert_not_called()
    assert kept == []


def test_history_subscription_gates_before_reading(qtbot, mocked_client, monkeypatch):
    """No bridge (and therefore no file read) is created for a declined
    dataset."""
    bridges = _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.plot("bpm4i")  # a configured curve, so the widget has sources to bind
    _oversized(monkeypatch, wf)
    bridges.clear()

    with mock.patch.object(wf, "_confirm_large_dataset", return_value=False):
        wf._setup_data_api_subscription(scan="scan-1")
    assert not bridges
    assert wf._data_bridge is None

    with mock.patch.object(wf, "_confirm_large_dataset", return_value=True):
        wf._setup_data_api_subscription(scan="scan-1")
    assert bridges and bridges[-1].scan == "scan-1"
    # The gate is decided up front, so the bridge itself is never size-gated.
    assert getattr(bridges[-1], "size_limit_bytes", None) is None


def test_describe_dataset_reports_point_counts():
    assert "1,000 points" in Waveform._describe_dataset(("det", "sig"), (1000,))
    text = Waveform._describe_dataset(("det", "sig"), (100, 1000))
    assert "100 points x 1,000 samples" in text
    assert "'det-sig'" in text


def _open_dialog_and_click(handler):
    """
    Utility that schedules *handler* to run as soon as a modal
    dialog is shown.  Returns a function suitable for QTimer.singleShot.
    """

    def _cb():
        # Locate the active modal dialog
        dlg = QApplication.activeModalWidget()
        assert isinstance(dlg, QDialog), "No active modal dialog found"
        handler(dlg)

    return _cb


def test_dialog_accept_real_interaction(qtbot, mocked_client, monkeypatch):
    """
    End-to-end: user changes the limit spinner to 5 MiB, ticks
    'don't show again', then presses YES.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.max_dataset_size_mb = 1

    def handler(dlg):
        spin: QDoubleSpinBox = dlg.findChild(QDoubleSpinBox)
        chk: QCheckBox = dlg.findChild(QCheckBox)
        btns: QDialogButtonBox = dlg.findChild(QDialogButtonBox)

        spin.setValue(5)
        chk.setChecked(True)

        yes_btn = btns.button(QDialogButtonBox.Yes)
        yes_btn.click()

    QTimer.singleShot(0, _open_dialog_and_click(handler))

    accepted = wf._confirm_large_dataset(4.6)
    assert accepted is True
    assert wf.max_dataset_size_mb == 5
    assert wf.skip_large_dataset_warning is True


def test_dialog_reject_real_interaction(qtbot, mocked_client, monkeypatch):
    """
    End-to-end: user leaves spinner unchanged, ticks 'don't show again',
    and presses NO.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.max_dataset_size_mb = 1

    def handler(dlg):
        chk: QCheckBox = dlg.findChild(QCheckBox)
        btns: QDialogButtonBox = dlg.findChild(QDialogButtonBox)

        chk.setChecked(True)
        no_btn = btns.button(QDialogButtonBox.No)
        no_btn.click()

    QTimer.singleShot(0, _open_dialog_and_click(handler))

    accepted = wf._confirm_large_dataset(4.6)
    assert accepted is False
    assert wf.skip_large_dataset_warning is True
    # Limit remains unchanged
    assert wf.max_dataset_size_mb == 1


def test_update_with_scan_history_by_index(qtbot, mocked_client, scan_history_factory, monkeypatch):
    """
    Test that update_with_scan_history by index loads the correct historical scan.
    """
    bridges = _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    hist1, hist2 = inject_scan_history(wf, scan_history_factory, ("hist1", 1), ("hist2", 2))

    assert len(wf.client.history._scan_ids) == 2, "Expected two history scans"

    # Do history curve plotting
    wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id="hist1")
    wf.plot(device_y="bpm4i", scan_number=2)

    assert len(wf.plot_item.curves) == 2, "Expected two curves for history scans"
    c1, c2 = wf.plot_item.curves
    # First curve should be for hist1, second for hist2
    assert c1.config.signal.device == "bpm4i"
    assert c1.config.signal.signal == "bpm4i"
    assert c1.config.scan_id == "hist1"
    assert c1.config.scan_number == 1
    assert c1.name() == "bpm4i-bpm4i-scan-1"

    assert c2.config.signal.device == "bpm4i"
    assert c2.config.signal.signal == "bpm4i"
    assert c2.config.scan_id == "hist2"
    assert c2.config.scan_number == 2
    assert c2.name() == "bpm4i-bpm4i-scan-2"

    # One scan-bound subscription per pinned history scan.
    history_scans = {bridge.scan for bridge in bridges if not bridge.closed}
    assert history_scans == {"hist1", "hist2"}


def test_history_curve_receives_data_from_scan_bound_subscription(
    qtbot, mocked_client, scan_history_factory, monkeypatch
):
    """
    History curve data flows through a DataAPI subscription bound to the
    pinned scan id; updates are routed by scan id and rendered against the
    auto-resolved x device.
    """
    bridges = _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    inject_scan_history(wf, scan_history_factory, ("hist1", 1))

    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id="hist1")
    history_bridge = wf._history_bridges["hist1"]
    assert history_bridge in bridges
    assert history_bridge.scan == "hist1"
    assert ("bpm4i", "bpm4i") in history_bridge.sources
    # Auto mode pulls in the scan's first report device as x source.
    assert ("samx", "samx") in history_bridge.sources

    update = _make_update(
        [
            _monitored_source("bpm4i", values=(5, 6, 7)),
            _monitored_source("samx", values=(10, 20, 30)),
        ],
        scan_id="hist1",
        reason="history",
    )
    wf._on_data_update(update)

    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(x_data, [10, 20, 30])
    np.testing.assert_array_equal(y_data, [5, 6, 7])

    # Updates for other scans do not touch the pinned curve.
    other = _make_update([_monitored_source("bpm4i", values=(1, 1, 1))], scan_id="other-scan")
    wf._on_data_update(other)
    _, y_data = c.get_data()
    np.testing.assert_array_equal(y_data, [5, 6, 7])


@pytest.mark.parametrize("mode", ["auto", "timestamp", "index", "samx"])
def test_history_curve_x_modes_pre_plot(
    qtbot, mocked_client, scan_history_factory, mode, monkeypatch
):
    """
    Test that history curves respect x_mode when set before plotting.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    hist1, hist2 = inject_scan_history(wf, scan_history_factory, ("hist1", 1), ("hist2", 2))
    wf.x_mode = mode
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id="hist1")
    assert c.config.current_x_mode == mode


@pytest.mark.parametrize("mode", ["auto", "timestamp", "index", "samx"])
def test_history_curve_x_modes_post_plot(
    qtbot, mocked_client, scan_history_factory, mode, monkeypatch
):
    """
    Test that changing x_mode after plotting history curves updates the curve on refresh.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    hist1, hist2 = inject_scan_history(wf, scan_history_factory, ("hist1", 1), ("hist2", 2))
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id="hist1")
    # Change x_mode after plotting
    wf.x_mode = mode
    # Refresh history curves
    wf._refresh_history_curves()
    assert c.config.current_x_mode == mode


def test_history_curve_incompatible_x_mode_hides_curve(
    qtbot, mocked_client, scan_history_factory, monkeypatch
):
    """
    Test that setting an x_mode not present in stored data hides the history curve.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "nonexistent_device"
    # Inject history scan for this test
    [history_msg] = inject_scan_history(wf, scan_history_factory, ("hist_bad", 1))
    # Plot history curve
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id=history_msg.scan_id)
    # Curve should be hidden due to incompatible x_mode
    assert not c.isVisible()


def test_history_curve_no_stored_data_raises(
    qtbot, mocked_client, monkeypatch, suppress_message_box
):
    """
    Test that plotting a history curve when stored_data_info is missing
    raises ValueError (metadata-level validation kept from the legacy fetch).
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    # Create a dummy scan_item lacking stored_data_info
    dummy_scan = SimpleNamespace(
        _msg=SimpleNamespace(stored_data_info=None),
        devices={},
        metadata={"bec": {"scan_id": "dummy", "scan_number": 1, "scan_report_devices": []}},
    )
    # Force get_history_scan_item to return our dummy
    monkeypatch.setattr(wf, "get_history_scan_item", lambda scan_id, scan_index: dummy_scan)
    # Attempt to plot history curve should be suppressed by SafeSlot and return None
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id="dummy", scan_number=1)
    assert c is None
    assert len(wf.curves) == 0


def test_history_curve_device_missing_returns_none(qtbot, mocked_client, scan_history_factory):
    """
    If the y-device is not in stored_data_info, plot should return None.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "index"
    [history_msg] = inject_scan_history(wf, scan_history_factory, ("hist_dev_missing", 1))
    c = wf.plot(device_y="non-existing", signal_y="non-existing", scan_id=history_msg.scan_id)
    assert c is None


def test_history_curve_custom_shape_mismatch_hides_curve(
    qtbot, mocked_client, scan_history_factory, monkeypatch
):
    """
    For custom x-mode, if x and y shapes mismatch, curve should be hidden.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "async_device"
    [history_msg] = inject_scan_history(wf, scan_history_factory, ("hist_custom_shape", 1))
    # Force shape mismatch for x-data
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id=history_msg.scan_id)
    assert c is not None
    assert not c.isVisible()


def test_history_curve_index_mode_plots_curve(
    qtbot, mocked_client, scan_history_factory, monkeypatch
):
    """
    Test that setting x_mode to 'index' plots and shows the history curve correctly.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "index"
    [history_msg] = inject_scan_history(wf, scan_history_factory, ("hist_index", 1))
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id=history_msg.scan_id)
    assert c is not None
    assert c.isVisible()
    assert c.config.current_x_mode == "index"


def test_history_curve_timestamp_mode_plots_curve(
    qtbot, mocked_client, scan_history_factory, monkeypatch
):
    """
    Test that setting x_mode to 'timestamp' plots and shows the history curve correctly.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "timestamp"
    [history_msg] = inject_scan_history(wf, scan_history_factory, ("hist_time", 1))
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id=history_msg.scan_id)
    assert c is not None
    assert c.isVisible()
    assert c.config.current_x_mode == "timestamp"


def test_history_curve_auto_valid_uses_first_report_device(
    qtbot, mocked_client, scan_history_factory, monkeypatch
):
    """
    Test that 'auto' x_mode uses the first available report device and shows the curve.
    """
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "auto"
    [history_msg] = inject_scan_history(wf, scan_history_factory, ("hist_auto_valid", 1))
    # Plot history curve
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id=history_msg.scan_id)
    assert c is not None
    assert c.isVisible()
    # Should have fallen back to the first scan_report_device
    assert c.config.current_x_mode == "auto"


def test_history_curve_file_not_found_returns_none(qtbot, mocked_client, scan_history_factory):
    """
    If the history file path does not exist, plot should return None.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "index"
    # Inject a valid history message then corrupt its file_path
    [history_msg] = inject_scan_history(wf, scan_history_factory, ("bad_file", 1))
    history_msg.file_path = "/nonexistent/path.h5"
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id=history_msg.scan_id)
    assert c is None


def test_history_curve_scan_not_found_returns_none(qtbot, mocked_client):
    """
    If the requested scan_id is not in history, plot should return None.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "index"
    # No history scans injected for this widget
    c = wf.plot(device_y="bpm4i", signal_y="bpm4i", scan_id="unknown_scan")
    assert c is None


def test_categorise_device_curves_monitored_device_with_async_signal(qtbot, mocked_client):
    """Device listed under 'monitored'
    readout priority may expose an asynchronous signal; the curve must be
    classified by the signal class, not the parent device's readout priority."""
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    dummy_scan = create_dummy_scan_item()
    wf.scan_item = dummy_scan

    # bpm4i is listed under 'monitored' in the dummy scan; give it an
    # additional async signal, as a mixed device would have.
    device = mocked_client.device_manager.devices["bpm4i"]
    device.signals["bpm4i_stream"] = {"value": 0.0}
    device._info["signals"]["bpm4i_stream"] = {
        "kind_str": "hinted",
        "component_name": "bpm4i_stream",
        "obj_name": "bpm4i_stream",
        "signal_class": "AsyncSignal",
    }

    c_sync = wf.plot(arg1="bpm4i", label="sync-curve")
    c_async = wf.plot(device_y="bpm4i", signal_y="bpm4i_stream", label="async-curve")

    mode = wf._categorise_device_curves()

    assert mode == "mixed"
    assert c_sync in wf._sync_curves
    assert c_async in wf._async_curves


def test_categorise_device_curves_falls_back_to_readout_priority(qtbot, mocked_client):
    """When no signal info is available (e.g. history data for a removed
    device), classification falls back to the scan's readout-priority lists."""
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    dummy_scan = create_dummy_scan_item()
    wf.scan_item = dummy_scan

    c_async = wf.plot(arg1="async_device", label="fallback-curve")
    # Simulate the device's signal info being unavailable.
    mocked_client.device_manager.devices["async_device"]._info = {}

    wf._categorise_device_curves()

    assert c_async in wf._async_curves


def test_x_source_resolution_does_not_open_the_data_file(qtbot, mocked_client, monkeypatch):
    """Auto x-mode must resolve the report device from in-memory metadata:
    ScanDataContainer.metadata lazily opens the HDF5 file, which would block
    the GUI thread (and would even precede the large-dataset gate)."""
    wf = create_widget(qtbot, Waveform, client=mocked_client)

    class _ExplodingMetadata:
        def __getitem__(self, key):
            raise AssertionError("data file was opened on the GUI thread")

        def get(self, *args, **kwargs):
            raise AssertionError("data file was opened on the GUI thread")

    # History container: report device comes from the scan history message.
    history_item = SimpleNamespace(
        metadata=_ExplodingMetadata(),
        _msg=SimpleNamespace(request_inputs={"arg_bundle": ["samx", -5, 5, 10], "kwargs": {}}),
        status_message=None,
    )
    assert wf._report_devices_no_file_io(history_item) == ["samx"]
    assert wf._history_x_source_key(history_item) == ("samx", "samx")

    # Live scan item: report devices come from the status message.
    live_item = SimpleNamespace(
        metadata=_ExplodingMetadata(),
        status_message=SimpleNamespace(scan_report_devices=["samy"], info={}),
        _msg=None,
    )
    assert wf._report_devices_no_file_io(live_item) == ["samy"]


def test_x_source_falls_back_to_file_metadata_when_unavailable(qtbot, mocked_client):
    """When neither the status message nor the history message names the
    report devices, the file metadata is still consulted (last resort)."""
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    scan_item = SimpleNamespace(
        metadata={"bec": {"scan_report_devices": ["samx"]}}, status_message=None, _msg=None
    )
    assert wf._report_devices_no_file_io(scan_item) == []
    assert wf._history_x_source_key(scan_item) == ("samx", "samx")


def test_detector_shaped_history_curve_is_not_hidden(qtbot, mocked_client, monkeypatch):
    """A large detector dataset has more rows than the scan has points; it is
    plotted against the sample index, so the x/y row-count difference must not
    hide the curve (regression: large history datasets disappeared)."""
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "samx"  # custom device x-axis: the strictest visibility path

    stored = {
        "samx": {"samx": SimpleNamespace(shape=(100,))},
        # Flat async concatenation: 100 acquisitions x 1000 samples appended
        # along one axis — the shape a large "add" async signal really has.
        "waveform": {"waveform_waveform": SimpleNamespace(shape=(100_000,))},
        # 2-D detector data (one row per acquisition).
        "eiger": {"eiger_data": SimpleNamespace(shape=(100, 1000))},
        "bpm4i": {"bpm4i": SimpleNamespace(shape=(100,))},
    }
    scan_item = SimpleNamespace(
        _msg=SimpleNamespace(
            stored_data_info=stored,
            num_points=100,
            num_monitored_readouts=100,
            request_inputs={"arg_bundle": ["samx", -5, 5, 100], "kwargs": {}},
        ),
        status_message=None,
    )
    monkeypatch.setattr(Waveform, "get_history_scan_item", lambda self, **kwargs: scan_item)

    def curve_for(device, signal):
        return SimpleNamespace(
            config=SimpleNamespace(
                scan_id="scan-1",
                scan_number=None,
                signal=SimpleNamespace(device=device, signal=signal),
            ),
            name=lambda: f"{device}-{signal}",
        )

    # Flat async data (100 000 samples vs a 100-point motor): visible.
    assert wf._history_curve_compatible(curve_for("waveform", "waveform_waveform")) is True
    # 2-D detector data: visible.
    assert wf._history_curve_compatible(curve_for("eiger", "eiger_data")) is True
    # A monitored signal with the same length as x: visible.
    assert wf._history_curve_compatible(curve_for("bpm4i", "bpm4i")) is True
    # A monitored signal whose length disagrees with x is still hidden
    # (unchanged behaviour for point-per-scan-point data).
    stored["bpm4i"]["bpm4i"] = SimpleNamespace(shape=(37,))
    scan_item._msg.num_monitored_readouts = 37
    scan_item._msg.num_points = 37
    assert wf._history_curve_compatible(curve_for("bpm4i", "bpm4i")) is False


def test_history_source_with_numpy_columns_renders(qtbot, mocked_client, monkeypatch):
    """Regression: the history plugin delivers numpy-array columns (bulk
    ingest keeps the file arrays intact). The render must accept them; a
    ``if not source.values`` truth-test raised ValueError on multi-element
    arrays and SafeSlot swallowed it, so the curve showed no data."""
    _fake_bridge_factory(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_axis_mode["name"] = "index"

    # monitored history column, numpy-valued (what bec_lib now emits)
    c = wf.plot(arg1="bpm4i", label="bpm4i-bpm4i")
    wf.scan_id = "dummy"
    src = _monitored_source("bpm4i", values=[5.0, 6.0, 7.0, 8.0], as_numpy=True)
    wf._on_data_update(_make_update([src], reason="history"))
    x_data, y_data = c.get_data()
    np.testing.assert_array_equal(y_data, [5.0, 6.0, 7.0, 8.0])

    # async history waveform, flat numpy value column, no async_update_type
    ca = wf.plot(arg1="async_device", label="async_device-async_device")
    src_a = _async_source(
        "async_device", values=[1.0, 2.0, 3.0, 4.0, 5.0], update_type=None, as_numpy=True
    )
    # history reads carry no async_update_type
    src_a.metadata.pop("async_update_type", None)
    wf._on_data_update(_make_update([src_a], reason="history"))
    x_data, y_data = ca.get_data()
    assert y_data is not None and len(y_data) == 5


def test_async_display_values_accepts_numpy(qtbot, mocked_client):
    """Both display helpers must handle numpy-valued sources (bulk history)."""
    from types import SimpleNamespace

    src = _async_source("async_device", values=[1, 2, 3], update_type="add", as_numpy=True)
    assert list(Waveform._async_display_values(src)) == [1, 2, 3]
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    carrier = SimpleNamespace(_data_api_async_cache=None)
    cached = wf._async_display_values_cached(carrier, _make_update([src]), src)
    assert list(cached) == [1, 2, 3]
