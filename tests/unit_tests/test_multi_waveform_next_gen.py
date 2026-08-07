from unittest.mock import MagicMock

import numpy as np
from bec_lib.data_api.models import SourceData, SubscriptionUpdate

from bec_widgets.widgets.plots.multi_waveform.multi_waveform import MultiWaveform
from tests.unit_tests.client_mocks import mocked_client

from .conftest import create_widget

##################################################
# Test helpers (DataAPI fake bridge + updates)
##################################################


def _set_signal_config(
    client, device: str, signal_name: str, signal_class: str, ndim: int, obj_name: str | None = None
):
    device = client.device_manager.devices[device]
    device._info["signals"][signal_name] = {
        "obj_name": obj_name or signal_name,
        "signal_class": signal_class,
        "component_name": signal_name,
        "describe": {"signal_info": {"ndim": ndim}},
    }


def _clear_signal_config(client, device: str, signal_name: str):
    client.device_manager.devices[device]._info["signals"].pop(signal_name, None)


def _fake_bridge_factory(monkeypatch):
    created = []

    class _FakeBridge:
        def __init__(
            self, client, sources, scan="live", parent=None, min_emit_interval=0.1, max_points=None
        ):
            self.client = client
            self.sources = list(sources)
            self.scan = scan
            self.max_points = max_points
            self.healthy = True
            self.closed = False
            self.updated = MagicMock()

        def close(self):
            self.closed = True

    def factory(client, sources, scan="live", parent=None, min_emit_interval=0.1, max_points=None):
        bridge = _FakeBridge(client, sources, scan=scan, max_points=max_points)
        created.append(bridge)
        return bridge

    monkeypatch.setattr(
        "bec_widgets.widgets.plots.multi_waveform.multi_waveform.QtDataSubscription", factory
    )
    return created


def _monitor_update(traces, scan_id="scan_1", monitor="waveform1d", start=0):
    """Build a full-state monitor_1d snapshot: one 1-D trace per value, newest last."""
    ordinals = tuple(range(start, start + len(traces)))
    source = SourceData(
        device=monitor,
        entry="monitor_1d",
        kind="unindexed",
        ordinals=ordinals,
        values=tuple(traces),
        timestamps=tuple(float(ordinal) for ordinal in ordinals),
        complete=True,
        metadata={"stream": "monitor_1d", "scan_id": scan_id},
    )
    return SubscriptionUpdate(
        scan_id="",
        reason="live",
        sources={(monitor, "monitor_1d"): source},
        aligned_ordinals=ordinals,
        complete=True,
        metadata={"group": f"standalone:{monitor}/monitor_1d"},
    )


def _async_update(
    traces, scan_id="scan_1", device="eiger", entry="eiger_data", start=0, update_type="add"
):
    """Build a full-state scan-scoped async snapshot: one trace per ordinal."""
    ordinals = tuple(range(start, start + len(traces)))
    source = SourceData(
        device=device,
        entry=entry,
        kind="async",
        ordinals=ordinals,
        values=tuple(traces),
        timestamps=tuple(float(ordinal) for ordinal in ordinals),
        complete=True,
        metadata={"async_update_type": update_type},
    )
    return SubscriptionUpdate(
        scan_id=scan_id,
        reason="live",
        sources={(device, entry): source},
        aligned_ordinals=ordinals,
        complete=True,
        metadata={"group": "standalone"},
    )


##################################################
# MultiWaveform widget base functionality tests
##################################################


def test_multiwaveform_initialization(qtbot, mocked_client):
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    assert mw.objectName() == "MultiWaveform"
    # Inherited from PlotBase
    assert mw.title == ""
    assert mw.x_label == ""
    assert mw.y_label == ""
    # No crosshair or FPS monitor by default
    assert mw.crosshair is None
    assert mw.fps_monitor is None
    # No curves initially
    assert len(mw.plot_item.curves) == 0
    # Multiwaveform specific
    assert mw.monitor is None
    assert mw.monitor_signal is None
    assert mw.color_palette == "plasma"
    assert mw.max_trace == 200
    assert mw.flush_buffer is False
    assert mw.highlight_last_curve is True
    assert mw.opacity == 50
    assert mw.scan_id is None
    assert mw.highlighted_index == 0
    assert mw._data_bridge is None
    assert mw.config.connection_status == "disconnected"


def test_multiwaveform_set_monitor(qtbot, mocked_client):
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    assert mw.monitor is None

    # Set a monitor without a signal; the device has no 1D-capable class signals,
    # so the selection falls back to the scan-less monitor_1d stream.
    mw.plot("waveform1d")
    assert mw.monitor == "waveform1d"
    assert mw.monitor_signal == "monitor_1d"
    assert mw.config.monitor == "waveform1d"
    assert mw.config.monitor_signal == "monitor_1d"
    assert mw.connected is True
    assert mw.config.connection_status == "connected"
    assert mw._data_bridge is not None
    assert mw._data_bridge.sources == [("waveform1d", "monitor_1d")]
    assert mw._data_bridge.scan_id == ""  # device scope


def test_multiwaveform_bridge_lifecycle(qtbot, mocked_client, monkeypatch):
    """plot() creates a scan-less bridge bounded by the curve limit; re-plot replaces it."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    mw.plot("waveform1d")
    assert len(bridges) == 1
    assert bridges[-1].sources == [("waveform1d", "monitor_1d")]
    assert bridges[-1].scan is None
    assert bridges[-1].max_points == mw.config.curve_limit
    assert mw.connected is True

    first = bridges[-1]
    mw.plot("bpm4i")
    assert first.closed is True
    assert bridges[-1].sources == [("bpm4i", "monitor_1d")]

    mw._cleanup_data_api_subscription()
    assert bridges[-1].closed is True
    assert mw.connected is False
    assert mw._data_bridge is None


##################################################
# Signal classification and routing
##################################################


def test_multiwaveform_async_signal_routes_live(qtbot, mocked_client, monkeypatch):
    """Selecting an AsyncSignal creates a scan="live" bridge with the obj_name entry.

    This is the simulated-waveform case: the device publishes via
    device_async_signal (scan-scoped), not via the device_monitor_1d stream.
    """
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )

    mw.plot("eiger", "data")
    assert mw.monitor == "eiger"
    assert mw.monitor_signal == "data"
    assert mw.connected is True
    assert bridges[-1].scan == "live"
    assert bridges[-1].sources == [("eiger", "eiger_data")]
    assert bridges[-1].max_points is None
    _clear_signal_config(mocked_client, "eiger", "data")


def test_multiwaveform_device_only_picks_unambiguous_async_signal(
    qtbot, mocked_client, monkeypatch
):
    """A device-only plot() picks the device's only 1D-capable class signal."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )

    mw.plot("eiger")
    assert mw.monitor_signal == "data"
    assert bridges[-1].scan == "live"
    assert bridges[-1].sources == [("eiger", "eiger_data")]
    _clear_signal_config(mocked_client, "eiger", "data")


def test_multiwaveform_device_only_ambiguous_falls_back_to_monitor(
    qtbot, mocked_client, monkeypatch
):
    """A device with several 1D-capable signals falls back to the monitor_1d stream."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    _set_signal_config(
        mocked_client, "eiger", "img", signal_class="PreviewSignal", ndim=1, obj_name="eiger_img"
    )

    mw.plot("eiger")
    assert mw.monitor_signal == "monitor_1d"
    assert bridges[-1].scan is None
    assert bridges[-1].sources == [("eiger", "monitor_1d")]
    _clear_signal_config(mocked_client, "eiger", "data")
    _clear_signal_config(mocked_client, "eiger", "img")


def test_multiwaveform_preview_signal_routes_scanless(qtbot, mocked_client, monkeypatch):
    """Selecting a PreviewSignal creates a scan-less bridge with the signal entry."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client,
        "waveform1d",
        "wave_prev",
        signal_class="PreviewSignal",
        ndim=1,
        obj_name="waveform1d_wave_prev",
    )

    mw.plot("waveform1d", "wave_prev")
    assert mw.monitor_signal == "wave_prev"
    assert bridges[-1].scan is None
    assert bridges[-1].sources == [("waveform1d", "wave_prev")]
    assert bridges[-1].max_points == mw.config.curve_limit
    _clear_signal_config(mocked_client, "waveform1d", "wave_prev")


def test_multiwaveform_rejects_unsupported_signal(qtbot, mocked_client, monkeypatch):
    """A signal with an unsupported class does not create a bridge and flags an error."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "plain", signal_class="Signal", ndim=1)

    mw.plot("eiger", "plain")
    assert bridges == []
    assert mw.connected is False
    assert mw.config.connection_status == "error"
    _clear_signal_config(mocked_client, "eiger", "plain")


def test_multiwaveform_rejects_2d_signal(qtbot, mocked_client, monkeypatch):
    """A 2D async signal is rejected for the 1D multi waveform plot."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img2d", signal_class="AsyncSignal", ndim=2)

    mw.plot("eiger", "img2d")
    assert bridges == []
    assert mw.config.connection_status == "error"
    _clear_signal_config(mocked_client, "eiger", "img2d")


def test_multiwaveform_switching_device_replaces_async_bridge(qtbot, mocked_client, monkeypatch):
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="async_obj"
    )
    _set_signal_config(
        mocked_client,
        "async_device",
        "data",
        signal_class="AsyncSignal",
        ndim=1,
        obj_name="async_obj",
    )

    def fake_get(signal_class_filter):
        # Production-like discovery so the signal combobox lists the async entry
        # for both devices when the toolbar re-populates on device change.
        return [
            (device, "data", mocked_client.device_manager.devices[device]._info["signals"]["data"])
            for device in ("eiger", "async_device")
        ]

    monkeypatch.setattr(mocked_client.device_manager, "get_bec_signals", fake_get)

    mw.plot("eiger", "data")
    first = bridges[-1]
    assert first.sources == [("eiger", "async_obj")]

    mw.device = "async_device"
    assert first.closed is True
    assert bridges[-1].sources == [("async_device", "async_obj")]
    _clear_signal_config(mocked_client, "eiger", "data")
    _clear_signal_config(mocked_client, "async_device", "data")


def test_multiwaveform_disconnect_via_empty_device(qtbot, mocked_client, monkeypatch):
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")
    assert mw.connected is True

    mw.device = ""
    assert bridges[-1].closed is True
    assert mw.connected is False
    assert mw.monitor is None
    assert mw.monitor_signal is None
    assert mw.config.connection_status == "disconnected"


##################################################
# Rendering
##################################################


def test_multiwaveform_set_properties(qtbot, mocked_client):
    """Check that MultiWaveform properties can be set and retrieved correctly."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    # Default checks
    assert mw.color_palette == "plasma"
    assert mw.max_trace == 200
    assert mw.flush_buffer is False
    assert mw.highlight_last_curve is True
    assert mw.opacity == 50

    # Change properties
    mw.color_palette = "viridis"
    mw.max_trace = 10
    mw.flush_buffer = True
    mw.highlight_last_curve = False
    mw.opacity = 75

    # Verify that changes took effect
    assert mw.color_palette == "viridis"
    assert mw.max_trace == 10
    assert mw.flush_buffer is True
    assert mw.highlight_last_curve is False
    assert mw.opacity == 75


def test_multiwaveform_curve_limit_no_flush(qtbot, mocked_client, monkeypatch):
    """Check that limiting the number of curves without flush simply hides older ones."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")
    mw.max_trace = 3
    mw.flush_buffer = False

    # Simulate updates that create multiple curves (snapshots grow, newest last)
    traces = []
    for i in range(5):
        traces.append(np.array([i, i + 0.5, i + 1]))
        mw._on_data_update(_monitor_update(list(traces)))

    # There should be 5 curves in total, but only the last 3 are visible
    assert len(mw.curves) == 5
    visible_curves = [c for c in mw.curves if c.isVisible()]
    assert len(visible_curves) == 3


def test_multiwaveform_curve_limit_flush(qtbot, mocked_client, monkeypatch):
    """Check that limiting the number of curves with flush removes older ones."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")
    mw.max_trace = 3
    mw.flush_buffer = True

    # Simulate adding multiple curves
    traces = []
    for i in range(5):
        traces.append(np.array([i, i + 0.5, i + 1]))
        mw._on_data_update(_monitor_update(list(traces)))

    # Only 3 curves remain after flush
    assert len(mw.curves) == 3
    # They should match the last 3 that were inserted
    x_data, y_data = mw.curves[0].getData()
    assert np.array_equal(y_data, [2, 2.5, 3])
    x_data, y_data = mw.curves[1].getData()
    assert np.array_equal(y_data, [3, 3.5, 4])
    x_data, y_data = mw.curves[2].getData()
    assert np.array_equal(y_data, [4, 4.5, 5])


def test_multiwaveform_snapshot_ordinal_filtering(qtbot, mocked_client, monkeypatch):
    """Full-state snapshots must not duplicate already-rendered traces."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    first = np.array([1, 2, 3])
    second = np.array([4, 5, 6])
    mw._on_data_update(_monitor_update([first]))
    assert len(mw.curves) == 1

    # Same snapshot delivered again (e.g. trailing coalesced emission): no new curves.
    mw._on_data_update(_monitor_update([first]))
    assert len(mw.curves) == 1

    # Snapshot grows by one trace: exactly one curve appended.
    mw._on_data_update(_monitor_update([first, second]))
    assert len(mw.curves) == 2
    _, y_data = mw.curves[-1].getData()
    assert np.array_equal(y_data, second)

    # Retention window slid (oldest dropped): only newer ordinals are added.
    third = np.array([7, 8, 9])
    mw._on_data_update(_monitor_update([second, third], start=1))
    assert len(mw.curves) == 3
    _, y_data = mw.curves[-1].getData()
    assert np.array_equal(y_data, third)


def test_multiwaveform_scan_change_clears_curves(qtbot, mocked_client, monkeypatch):
    """A new scan_id in the source metadata clears the previous scan's curves."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    old_trace = np.array([1, 2, 3])
    new_trace = np.array([4, 5, 6])
    mw._on_data_update(_monitor_update([old_trace], scan_id="scan_1"))
    assert len(mw.curves) == 1
    assert mw.scan_id == "scan_1"

    # New scan: the retained window still contains the old-scan trace, but
    # only the not-yet-consumed ordinal is rendered after the clear.
    mw._on_data_update(_monitor_update([old_trace, new_trace], scan_id="scan_2"))
    assert mw.scan_id == "scan_2"
    assert len(mw.curves) == 1
    _, y_data = mw.curves[-1].getData()
    assert np.array_equal(y_data, new_trace)


def test_multiwaveform_async_scan_rollover_clears_curves(qtbot, mocked_client, monkeypatch):
    """For scan-scoped async sources the update.scan_id drives the rollover and
    resets the ordinal delta-append (async ordinals restart per scan)."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    mw.plot("eiger", "data")

    first = np.array([1, 2, 3])
    second = np.array([4, 5, 6])
    mw._on_data_update(_async_update([first, second], scan_id="scan_1"))
    assert mw.scan_id == "scan_1"
    assert len(mw.curves) == 2
    assert mw._last_ordinal == 1

    # New scan: ordinals restart at 0; curves are cleared and the delta-append reset.
    rollover = np.array([7, 8, 9])
    mw._on_data_update(_async_update([rollover], scan_id="scan_2"))
    assert mw.scan_id == "scan_2"
    assert len(mw.curves) == 1
    assert mw._last_ordinal == 0
    _, y_data = mw.curves[-1].getData()
    assert np.array_equal(y_data, rollover)
    _clear_signal_config(mocked_client, "eiger", "data")


def test_multiwaveform_async_replace_updates_single_trace(qtbot, mocked_client, monkeypatch):
    """A "replace" async source exposes one current state that replaces the trace set."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    mw.plot("eiger", "data")

    first = np.array([1, 2, 3])
    second = np.array([4, 5, 6])
    mw._on_data_update(_async_update([first], scan_id="scan_1", update_type="replace"))
    assert len(mw.curves) == 1
    _, y_data = mw.curves[-1].getData()
    assert np.array_equal(y_data, first)

    # The replace source keeps ordinal 0; the new state still replaces the trace.
    mw._on_data_update(_async_update([second], scan_id="scan_1", update_type="replace"))
    assert len(mw.curves) == 1
    _, y_data = mw.curves[-1].getData()
    assert np.array_equal(y_data, second)
    _clear_signal_config(mocked_client, "eiger", "data")


def test_multiwaveform_highlight_last_curve(qtbot, mocked_client, monkeypatch):
    """Check highlight_last_curve behavior."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")
    mw.max_trace = 5
    mw.flush_buffer = False

    # Simulate adding multiple curves
    traces = []
    for i in range(3):
        traces.append(np.array([i, i + 1, i + 2]))
        mw._on_data_update(_monitor_update(list(traces)))

    # Initially highlight_last_curve is True, so the last visible curve is highlighted
    # The highlight index should be -1 in the code's logic
    assert mw.highlight_last_curve is True

    # Disable highlight_last_curve
    mw.highlight_last_curve = False

    # Force highlight of the 1st visible curve (index 0 among visible)
    mw.set_curve_highlight(0)
    assert mw.highlighted_index == 0


def test_multiwaveform_opacity_changes(qtbot, mocked_client, monkeypatch):
    """Check changing opacity affects existing curves."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    # Add one curve
    mw._on_data_update(_monitor_update([np.array([10, 20, 30])]))
    assert len(mw.curves) == 1

    # Default opacity is 50
    assert mw.opacity == 50

    # Change opacity
    mw.opacity = 80
    assert mw.opacity == 80


def test_multiwaveform_set_colormap(qtbot, mocked_client, monkeypatch):
    """Check that setting a new colormap updates curve colors."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    # Simulate multiple curve updates
    traces = []
    for i in range(3):
        traces.append(np.array([i, i + 1, i + 2]))
        mw._on_data_update(_monitor_update(list(traces)))

    # Default color_palette is "plasma"
    assert mw.color_palette == "plasma"
    # Now change to a new colormap
    mw.color_palette = "viridis"
    assert mw.color_palette == "viridis"


def test_multiwaveform_simulate_updates(qtbot, mocked_client, monkeypatch):
    """Simulate a series of 1D updates to ensure the data is appended and the correct number of curves appear."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    data_series = [np.random.rand(5), np.random.rand(5), np.random.rand(5)]
    traces = []
    for idx, arr in enumerate(data_series):
        traces.append(arr)
        mw._on_data_update(_monitor_update(list(traces), scan_id="scan_99"))
        # Each update should add a new curve
        assert len(mw.curves) == idx + 1
        x_data, y_data = mw.curves[-1].getData()
        assert np.array_equal(y_data, arr)

    # Check that the scan_id was updated
    assert mw.scan_id == "scan_99"


##################################################
# MultiWaveform control panel and toolbar
##################################################


def test_control_panel_updates_widget(qtbot, mocked_client):
    """
    Interact with the control panel’s UI elements and confirm the widget’s properties are updated.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    assert mw.opacity == 50
    assert mw.flush_buffer is False
    assert mw.max_trace == 200
    assert mw.highlight_last_curve is True

    mw.controls.ui.opacity.setValue(80)
    assert mw.opacity == 80

    mw.controls.ui.flush_buffer.setChecked(True)
    assert mw.flush_buffer is True

    mw.controls.ui.max_trace.setValue(12)
    assert mw.max_trace == 12

    mw.controls.ui.highlight_last_curve.setChecked(False)
    assert mw.highlight_last_curve is False


def test_widget_updates_control_panel(qtbot, mocked_client):
    """
    Change properties directly on the MultiWaveform and verify the control panel UI reflects those changes.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    mw.opacity = 25
    qtbot.wait(100)
    assert mw.controls.ui.opacity.value() == 25

    mw.flush_buffer = True
    qtbot.wait(100)
    assert mw.controls.ui.flush_buffer.isChecked() is True

    mw.max_trace = 9
    qtbot.wait(100)
    assert mw.controls.ui.max_trace.value() == 9

    mw.highlight_last_curve = False
    qtbot.wait(100)
    assert mw.controls.ui.highlight_last_curve.isChecked() is False


def test_selection_toolbar_builds_device_and_signal_comboboxes(qtbot, mocked_client):
    """The toolbar carries the shared device+signal selection with the width splitter."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    device_selection = mw.toolbar.components.get_action("device_selection").widget
    assert device_selection.device_combo_box is not None
    assert device_selection.signal_combo_box is not None
    # The section-width splitter of the shared component is registered as well
    assert mw.toolbar.components.exists("device_selection_splitter")
    # The color map widget remains available
    assert mw.toolbar.components.get_action("color_map").widget is not None


def test_selection_toolbar_updates_widget(qtbot, mocked_client, monkeypatch):
    """
    Selecting a device and signal from the toolbar comboboxes connects the widget,
    and selecting a colormap updates the color palette.
    """
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    def fake_get(signal_class_filter):
        signal_classes = (
            signal_class_filter
            if isinstance(signal_class_filter, (list, tuple, set))
            else [signal_class_filter]
        )
        if "PreviewSignal" in signal_classes:
            return [
                (
                    "waveform1d",
                    "wave",
                    {
                        "obj_name": "waveform1d_wave",
                        "component_name": "wave",
                        "signal_class": "PreviewSignal",
                        "describe": {"signal_info": {"ndim": 1}},
                    },
                )
            ]
        return []

    monkeypatch.setattr(mw.client.device_manager, "get_bec_signals", fake_get)
    device_selection = mw.toolbar.components.get_action("device_selection").widget
    device_selection.device_combo_box.update_devices_from_filters()

    device_selection.device_combo_box.setCurrentText("waveform1d")
    assert mw.monitor == "waveform1d"

    # The signal combobox offers the monitor_1d sentinel and the preview signal
    signal_items = [
        device_selection.signal_combo_box.itemText(i)
        for i in range(device_selection.signal_combo_box.count())
    ]
    assert "monitor_1d" in signal_items
    assert "wave" in signal_items

    device_selection.signal_combo_box.setCurrentText("wave")
    assert mw.monitor_signal == "wave"
    assert bridges[-1].scan is None
    assert bridges[-1].sources == [("waveform1d", "wave")]

    cmap_action = mw.toolbar.components.get_action("color_map")
    cmap_action.widget.colormap = "viridis"
    assert mw.color_palette == "viridis"


def test_selection_toolbar_monitor_1d_entry(qtbot, mocked_client, monkeypatch):
    """Selecting the monitor_1d sentinel routes to the scan-less device stream."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    def fake_get(signal_class_filter):
        return []

    monkeypatch.setattr(mw.client.device_manager, "get_bec_signals", fake_get)
    device_selection = mw.toolbar.components.get_action("device_selection").widget
    device_selection.device_combo_box.update_devices_from_filters()

    # Async-readout devices are listed even without matching class signals
    assert "eiger" in device_selection.device_combo_box.devices

    device_selection.device_combo_box.setCurrentText("eiger")
    device_selection.signal_combo_box.setCurrentText("monitor_1d")
    assert mw.monitor == "eiger"
    assert mw.monitor_signal == "monitor_1d"
    assert bridges[-1].scan is None
    assert bridges[-1].sources == [("eiger", "monitor_1d")]


def test_toolbar_syncs_from_properties(qtbot, mocked_client, monkeypatch):
    """Programmatic plot() calls are mirrored into the selection comboboxes."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    mw.plot("waveform1d")
    qtbot.wait(100)
    device_selection = mw.toolbar.components.get_action("device_selection").widget
    assert device_selection.device_combo_box.currentText() == "waveform1d"
    assert device_selection.signal_combo_box.currentText() == "monitor_1d"


def test_control_panel_opacity_slider_spinbox(qtbot, mocked_client):
    """
    Verify that when the user moves the opacity slider or spinbox, the widget's
    opacity property updates, and vice versa. Also confirm they stay in sync.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    slider_opacity = mw.controls.ui.opacity
    spinbox_opacity = mw.controls.ui.spinbox_opacity

    # Default
    assert mw.opacity == 50
    assert slider_opacity.value() == 50
    assert spinbox_opacity.value() == 50

    # Move the slider
    slider_opacity.setValue(75)
    assert mw.opacity == 75
    assert spinbox_opacity.value() == 75

    # Move the spinbox
    spinbox_opacity.setValue(20)
    assert mw.opacity == 20
    assert slider_opacity.value() == 20

    mw.opacity = 95
    qtbot.wait(100)
    assert slider_opacity.value() == 95
    assert spinbox_opacity.value() == 95


def test_control_panel_highlight_slider_spinbox(qtbot, mocked_client, monkeypatch):
    """
    Test that the slider and spinbox for curve highlighting update
    the widget's highlighted_index property, and are disabled if
    highlight_last_curve is True.
    """
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")
    slider_index = mw.controls.ui.highlighted_index
    spinbox_index = mw.controls.ui.spinbox_index
    checkbox_highlight_last = mw.controls.ui.highlight_last_curve

    # By default highlight_last_curve is True, so slider/spinbox are disabled:
    assert checkbox_highlight_last.isChecked() is True
    assert not slider_index.isEnabled()
    assert not spinbox_index.isEnabled()

    # Uncheck highlight_last_curve -> slider/spinbox become enabled
    checkbox_highlight_last.setChecked(False)
    assert checkbox_highlight_last.isChecked() is False
    assert slider_index.isEnabled()
    assert spinbox_index.isEnabled()

    # Simulate a few curves so there's something to highlight
    data_arrays = [np.array([0, 1, 2]), np.array([3, 4, 5]), np.array([6, 7, 8])]
    traces = []
    for arr in data_arrays:
        traces.append(arr)
        mw._on_data_update(_monitor_update(list(traces), scan_id="scan_123"))

    # The number_of_visible_curves == 3 now
    max_index = mw.number_of_visible_curves - 1
    assert max_index == 2

    # Move the slider to index 1
    slider_index.setValue(1)
    assert mw.highlighted_index == 1
    assert spinbox_index.value() == 1

    # Move the spinbox to index 2
    spinbox_index.setValue(2)
    assert mw.highlighted_index == 2
    assert slider_index.value() == 2

    # Directly set mw.highlighted_index
    mw.highlighted_index = 0
    qtbot.wait(100)
    assert slider_index.value() == 0
    assert spinbox_index.value() == 0

    # Re-check highlight_last_curve -> slider/spinbox disabled again
    checkbox_highlight_last.setChecked(True)
    assert not slider_index.isEnabled()
    assert not spinbox_index.isEnabled()
    assert mw.highlighted_index == 2
