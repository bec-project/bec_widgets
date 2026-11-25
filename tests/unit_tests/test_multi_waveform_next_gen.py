from dataclasses import replace
from unittest.mock import MagicMock

import numpy as np
import pyqtgraph as pg
import pytest
from bec_lib import messages
from bec_lib.data_api import CorrelationGroup
from bec_lib.data_api.models import SourceData, SubscriptionUpdate
from bec_lib.endpoints import MessageEndpoints
from bec_lib.scan_items import ScanItem

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.tests.utils import fake_data_subscriptions
from bec_widgets.widgets.plots.multi_waveform.multi_waveform import MultiWaveform

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
            self, client, sources, scan="live", owner=None, update_rate=10.0, max_buffer_size=None
        ):
            self.client = client
            self.sources = list(sources)
            self.scan = scan
            self.max_buffer_size = max_buffer_size
            self.healthy = True
            # What the widgets read of a real bridge about its binding.
            self.groups = {}
            self.routes = {}
            self.unbound_sources = []
            self.closed = False
            self.updated = MagicMock()

        def set_max_buffer_size(self, max_buffer_size):
            self.max_buffer_size = max_buffer_size

        def close(self):
            self.closed = True

    def factory(client, sources, scan="live", owner=None, update_rate=10.0, max_buffer_size=None):
        bridge = _FakeBridge(client, sources, scan=scan, max_buffer_size=max_buffer_size)
        created.append(bridge)
        return bridge

    fake_data_subscriptions(monkeypatch, factory)
    return created


#: 1D PreviewSignal every test device carries (see the autouse fixture below).
TRACE = "trace"


@pytest.fixture(autouse=True)
def preview_traces(mocked_client):
    """Give the plain test devices one 1D preview signal, the scan-less MultiWaveform source."""
    for device in ("waveform1d", "bpm4i"):
        _set_signal_config(mocked_client, device, TRACE, signal_class="PreviewSignal", ndim=1)
    yield
    for device in ("waveform1d", "bpm4i"):
        _clear_signal_config(mocked_client, device, TRACE)


def _monitor_update(
    traces, scan_id="scan_1", monitor="waveform1d", start=0, scan_first_ordinal=None
):
    """
    Build a full-state preview snapshot: one 1-D trace per value, newest last.

    ``scan_first_ordinal`` is what the DataAPI records with the scan id of a stream: the
    ordinal of the first trace of that scan.
    """
    ordinals = tuple(range(start, start + len(traces)))
    metadata = {"stream": "preview", "scan_id": scan_id}
    if scan_first_ordinal is not None:
        metadata["scan_first_ordinal"] = scan_first_ordinal
    source = SourceData(
        device=monitor,
        entry=TRACE,
        kind="unindexed",
        ordinals=ordinals,
        values=tuple(traces),
        timestamps=tuple(float(ordinal) for ordinal in ordinals),
        complete=True,
        metadata=metadata,
    )
    return SubscriptionUpdate(
        scan_id="",
        reason="live",
        sources={(monitor, TRACE): source},
        aligned_ordinals=ordinals,
        complete=True,
        metadata={"group": CorrelationGroup.standalone(monitor, TRACE)},
    )


def _async_update(
    traces,
    scan_id="scan_1",
    device="eiger",
    entry="eiger_data",
    start=0,
    update_type="add",
    ordinals=None,
):
    """Build a full-state scan-scoped async snapshot: one trace per ordinal."""
    ordinals = tuple(range(start, start + len(traces))) if ordinals is None else tuple(ordinals)
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
        metadata={"group": CorrelationGroup.standalone(*source.key)},
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
    assert mw._data_subscription is None
    assert mw.config.connection_status == "disconnected"


def test_multiwaveform_set_monitor(qtbot, mocked_client):
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    assert mw.monitor is None

    # Set a monitor without a signal: its only 1D preview signal is selected.
    mw.plot("waveform1d")
    assert mw.monitor == "waveform1d"
    assert mw.monitor_signal == TRACE
    assert mw.config.monitor == "waveform1d"
    assert mw.config.monitor_signal == TRACE
    assert mw.connected is True
    assert mw.config.connection_status == "connected"
    assert mw._data_subscription is not None
    assert mw._data_subscription.sources == [("waveform1d", TRACE)]
    assert mw._data_subscription.scan_id == ""  # device scope


def test_multiwaveform_preview_buffer_is_not_the_display_limit(qtbot, mocked_client, monkeypatch):
    """
    With ``flush_buffer`` off, traces above the display limit are kept hidden and come back
    when the limit is raised. A burst between two updates must reach the widget whole, so
    the backend may not drop what the display limit hides.
    """
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.config.curve_limit = 2
    mw.config.flush_buffer = False

    mw.plot("waveform1d")
    assert bridges[-1].max_buffer_size is None


def test_multiwaveform_preview_buffer_follows_the_limit_when_flushing(
    qtbot, mocked_client, monkeypatch
):
    """With ``flush_buffer`` on the backend keeps the display limit, also when that changes."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.config.curve_limit = 2
    mw.config.flush_buffer = True

    mw.plot("waveform1d")
    assert bridges[-1].max_buffer_size == 2
    mw.set_curve_limit(5, True)
    assert bridges[-1].max_buffer_size == 5
    mw.set_curve_limit(3, True)
    assert bridges[-1].max_buffer_size == 3
    mw.set_curve_limit(3, False)  # keep everything from now on
    assert bridges[-1].max_buffer_size is None
    # The same subscription all along: a new one would count its traces from zero again.
    assert len(bridges) == 1 and not bridges[-1].closed


def _publish_previews(client, start, count):
    """Publish ``count`` preview traces of ``waveform1d/wave_prev``, numbered from ``start``."""
    for index in range(start, start + count):
        message = messages.DevicePreviewMessage(
            device="waveform1d", signal="wave_prev", data=np.full(4, float(index))
        )
        client.connector.xadd(
            MessageEndpoints.device_preview("waveform1d", "wave_prev"), {"data": message}
        )


def test_multiwaveform_burst_through_the_data_api_keeps_every_trace(qtbot, mocked_client):
    """
    Through the real DataAPI: a burst of more traces than the display limit, all within one
    update, is kept whole while ``flush_buffer`` is off. Switching it on keeps the
    subscription and its numbering, so the newest traces follow the ones already shown.
    """
    _set_signal_config(
        mocked_client,
        "waveform1d",
        "wave_prev",
        signal_class="PreviewSignal",
        ndim=1,
        obj_name="waveform1d_wave_prev",
    )
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.update_rate = 1  # Hz: the whole burst falls into one update
    mw.config.curve_limit = 2
    mw.config.flush_buffer = False
    mw.plot("waveform1d", "wave_prev")

    _publish_previews(mocked_client, 0, 205)
    qtbot.waitUntil(lambda: len(mw.curves) == 205, timeout=10000)
    assert len([curve for curve in mw.curves if curve.isVisible()]) == 2
    mw.set_curve_limit(500, False)
    assert len([curve for curve in mw.curves if curve.isVisible()]) == 205

    subscription = mw._data_subscription
    mw.set_curve_limit(50, True)
    assert mw._data_subscription is subscription and len(mw.curves) == 50
    _publish_previews(mocked_client, 205, 60)
    qtbot.waitUntil(lambda: mw._last_ordinal == 264, timeout=10000)
    assert [curve._data_api_ordinal for curve in mw.curves] == list(range(215, 265))
    _clear_signal_config(mocked_client, "waveform1d", "wave_prev")


def test_multiwaveform_bridge_lifecycle(qtbot, mocked_client, monkeypatch):
    """plot() creates a scan-less bridge; re-plot replaces it."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    mw.plot("waveform1d")
    assert len(bridges) == 1
    assert bridges[-1].sources == [("waveform1d", TRACE)]
    assert bridges[-1].scan is None
    assert bridges[-1].max_buffer_size is None
    assert mw.connected is True

    first = bridges[-1]
    mw.plot("bpm4i")
    assert first.closed is True
    assert bridges[-1].sources == [("bpm4i", TRACE)]

    mw._cleanup_data_api_subscription()
    assert bridges[-1].closed is True
    assert mw.connected is False
    assert mw._data_subscription is None


##################################################
# Signal classification and routing
##################################################


def test_multiwaveform_async_signal_routes_live(qtbot, mocked_client, monkeypatch):
    """Selecting an AsyncSignal creates a scan="live" bridge with the obj_name entry.

    This is the simulated-waveform case: the device publishes via
    device_async_signal (scan-scoped).
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
    assert bridges[-1].max_buffer_size is None
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


def test_multiwaveform_device_only_ambiguous_asks_for_a_signal(qtbot, mocked_client, monkeypatch):
    """A device with several 1D-capable signals is not guessed: the user must pick one."""
    bridges = _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    _set_signal_config(
        mocked_client, "eiger", "img", signal_class="PreviewSignal", ndim=1, obj_name="eiger_img"
    )

    mw.plot("eiger")
    assert mw.monitor == "eiger"
    assert not mw.monitor_signal
    assert not bridges
    assert mw.config.connection_status == "error"
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
    assert bridges[-1].max_buffer_size is None
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


def test_multiwaveform_scan_update_populates_info_label(qtbot, mocked_client, monkeypatch):
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")
    scan_item = ScanItem(queue_id="queue-1", scan_number=1, scan_id="scan_1", status="open")
    scan_item.status_message = messages.ScanStatusMessage(
        scan_id="scan_1", scan_number=1, scan_name="line_scan", status="open", info={}
    )
    monkeypatch.setattr(mw.queue.scan_storage, "find_scan_by_ID", lambda scan_id: scan_item)

    mw._on_data_update(_monitor_update([np.array([1, 2, 3])], scan_id="scan_1"))

    assert [label.text for _, label in mw.info_label.items] == [
        "Scan: 1 (live)",
        "Scan Name: line_scan",
    ]


def test_multiwaveform_clears_info_label_when_scan_id_is_unknown(qtbot, mocked_client, monkeypatch):
    """Regression: monitor data without a known scan_id kept the previous scan's rows."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")
    mw.show_info_label = True
    scan_item = ScanItem(queue_id="queue-1", scan_number=1, scan_id="scan_1", status="open")
    scan_item.status_message = messages.ScanStatusMessage(
        scan_id="scan_1", scan_number=1, scan_name="line_scan", status="open", info={}
    )
    storage = {"scan_1": scan_item}
    monkeypatch.setattr(
        mw.queue.scan_storage, "find_scan_by_ID", lambda scan_id: storage.get(scan_id)
    )

    mw._on_data_update(_monitor_update([np.array([1, 2, 3])], scan_id="scan_1"))
    assert mw.info_label.isVisible()

    # e.g. the device was triggered outside a scan: no scan_id in the metadata
    mw._on_data_update(_monitor_update([np.array([4, 5, 6])], scan_id=None))

    assert mw.scan_id is None
    assert mw.info_label.rows == []
    assert not mw.info_label.isVisible()


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


def test_multiwaveform_scan_change_starts_at_the_first_trace_of_the_scan(
    qtbot, mocked_client, monkeypatch
):
    """
    The last trace of a scan and the first of the next can arrive in one update. The
    stream says where the new scan starts: the trace before it is not drawn as part of it.
    """
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    a0, a1 = np.array([1.0, 1.0]), np.array([1.5, 1.5])
    b0, b1 = np.array([9.0, 9.0]), np.array([9.5, 9.5])
    mw._on_data_update(_monitor_update([a0], scan_id="scan_1", scan_first_ordinal=0))
    mw._on_data_update(_monitor_update([a0, a1, b0], scan_id="scan_2", scan_first_ordinal=2))
    assert mw.scan_id == "scan_2"
    assert [curve.getData()[1].tolist() for curve in mw.curves] == [b0.tolist()]

    # the retained window still holds the old traces in later updates: they stay out
    mw._on_data_update(_monitor_update([a0, a1, b0, b1], scan_id="scan_2", scan_first_ordinal=2))
    assert [curve.getData()[1].tolist() for curve in mw.curves] == [b0.tolist(), b1.tolist()]


def test_multiwaveform_first_update_starts_at_the_first_trace_of_the_scan(
    qtbot, mocked_client, monkeypatch
):
    """The same holds for the first update of a subscription that spans two scans."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    old, new = np.array([1.0, 1.0]), np.array([9.0, 9.0])
    mw._on_data_update(_monitor_update([old, new], scan_id="scan_2", scan_first_ordinal=1))
    assert [curve.getData()[1].tolist() for curve in mw.curves] == [new.tolist()]


def test_multiwaveform_late_trace_is_drawn_at_its_place(qtbot, mocked_client, monkeypatch):
    """
    A trace can arrive after a newer one (a late hole-fill). It is drawn, between its
    neighbours: the newest trace stays the last one.
    """
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    mw.plot("eiger", "data")

    traces = [np.array([0.0, 0.0]), np.array([1.0, 1.0]), np.array([2.0, 2.0])]
    mw._on_data_update(_async_update([traces[0], traces[2]], ordinals=(0, 2)))
    assert [curve._data_api_ordinal for curve in mw.curves] == [0, 2]
    mw._on_data_update(_async_update(traces, ordinals=(0, 1, 2)))
    assert [curve._data_api_ordinal for curve in mw.curves] == [0, 1, 2]
    assert [curve.getData()[1].tolist() for curve in mw.curves] == [t.tolist() for t in traces]
    _clear_signal_config(mocked_client, "eiger", "data")


def test_multiwaveform_late_trace_counts_for_the_display_limit(qtbot, mocked_client, monkeypatch):
    """
    With a flushing display limit the newest traces by ordinal are kept: a late trace
    takes its place among them, and a trace that was flushed is not drawn again.
    """
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    mw.plot("eiger", "data")
    mw.max_trace = 2
    mw.flush_buffer = True

    traces = [np.full(2, float(index)) for index in range(4)]
    mw._on_data_update(_async_update([traces[0], traces[1], traces[3]], ordinals=(0, 1, 3)))
    assert [curve._data_api_ordinal for curve in mw.curves] == [1, 3]
    # trace 2 arrives late; trace 0 is still in the snapshot but was flushed
    mw._on_data_update(_async_update(traces, ordinals=(0, 1, 2, 3)))
    assert [curve._data_api_ordinal for curve in mw.curves] == [2, 3]
    mw._on_data_update(_async_update(traces, ordinals=(0, 1, 2, 3)))
    assert [curve._data_api_ordinal for curve in mw.curves] == [2, 3]
    assert len([item for item in mw.plot_item.items if isinstance(item, pg.PlotDataItem)]) == 2
    _clear_signal_config(mocked_client, "eiger", "data")


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

    # The signal combobox offers the preview signal (no legacy monitor entry)
    signal_items = [
        device_selection.signal_combo_box.itemText(i)
        for i in range(device_selection.signal_combo_box.count())
    ]
    assert "monitor_1d" not in signal_items
    assert "wave" in signal_items

    device_selection.signal_combo_box.setCurrentText("wave")
    assert mw.monitor_signal == "wave"
    assert bridges[-1].scan is None
    assert bridges[-1].sources == [("waveform1d", "wave")]

    cmap_action = mw.toolbar.components.get_action("color_map")
    cmap_action.widget.colormap = "viridis"
    assert mw.color_palette == "viridis"


def test_toolbar_syncs_from_properties(qtbot, mocked_client, monkeypatch):
    """Programmatic plot() calls are mirrored into the selection comboboxes."""
    _fake_bridge_factory(monkeypatch)
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    def fake_get(signal_class_filter):
        # Production-like discovery: the combobox lists the device's preview signal.
        info = mocked_client.device_manager.devices["waveform1d"]._info["signals"][TRACE]
        return [("waveform1d", TRACE, info)]

    monkeypatch.setattr(mocked_client.device_manager, "get_bec_signals", fake_get)
    mw.plot("waveform1d")
    qtbot.wait(100)
    device_selection = mw.toolbar.components.get_action("device_selection").widget
    assert device_selection.device_combo_box.currentText() == "waveform1d"
    assert device_selection.signal_combo_box.currentText() == TRACE


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


def test_multiwaveform_growing_rows_update_existing_traces(qtbot, mocked_client, monkeypatch):
    _fake_bridge_factory(monkeypatch)
    widget = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    widget.plot("eiger", "data")
    first, second = np.array([1, 2]), np.array([3, 4])
    widget._on_data_update(_async_update([first, second], update_type="add_slice"))
    curves = list(widget.curves)
    grown = np.array([1, 2, 5, 6])
    widget._on_data_update(_async_update([grown, second], update_type="add_slice"))
    assert list(widget.curves) == curves
    np.testing.assert_array_equal(widget.curves[0].getData()[1], grown)
    np.testing.assert_array_equal(widget.curves[1].getData()[1], second)
    _clear_signal_config(mocked_client, "eiger", "data")


def test_multiwaveform_keeps_its_traces_when_the_scan_moves_to_its_file(
    qtbot, mocked_client, monkeypatch
):
    """
    The scan file stores a growing 1-D signal as one series of samples, without the
    acquisitions it arrived in. When the subscription moves to the file after the scan,
    that update holds no traces: the ones drawn while the scan ran stay.
    """
    _fake_bridge_factory(monkeypatch)
    widget = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    widget.plot("eiger", "data")
    traces = [np.full(5, float(index)) for index in range(3)]
    live = _async_update(traces)
    widget._on_data_update(live)
    drawn = list(widget.curves)
    assert len(drawn) == 3

    samples = np.concatenate(traces)
    stored = SourceData(
        device="eiger",
        entry="eiger_data",
        kind="async",
        ordinals=np.arange(len(samples)),
        values=samples,
        timestamps=np.full(len(samples), None, dtype=object),
        complete=True,
    )
    from_file = replace(
        live,
        sources={stored.key: stored},
        aligned_ordinals=tuple(range(len(samples))),
        reason="history",
        generation=1,
    )
    widget._on_data_update(from_file)
    assert list(widget.curves) == drawn
    assert [curve.getData()[1].tolist() for curve in drawn] == [t.tolist() for t in traces]
    _clear_signal_config(mocked_client, "eiger", "data")


def test_multiwaveform_late_subscriber_draws_the_stored_series_as_one_trace(
    qtbot, mocked_client, monkeypatch
):
    """
    A widget that has no trace of a scan (it subscribed after the scan) gets the stored
    1-D series from the scan file: it draws it as its one trace, and keeps it when the
    same data arrives again.
    """
    _fake_bridge_factory(monkeypatch)
    widget = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    widget.plot("eiger", "data")
    samples = np.arange(6.0)
    stored = SourceData(
        device="eiger",
        entry="eiger_data",
        kind="async",
        ordinals=np.arange(len(samples)),
        values=samples,
        timestamps=np.full(len(samples), None, dtype=object),
        complete=True,
    )
    from_file = replace(
        _async_update([samples]),
        sources={stored.key: stored},
        aligned_ordinals=tuple(range(len(samples))),
        reason="history",
    )
    # the file is read block by block: the trace grows with it
    partial = replace(stored, ordinals=stored.ordinals[:2], values=samples[:2].copy())
    widget._on_data_update(replace(from_file, sources={stored.key: partial}))
    assert [curve.getData()[1].tolist() for curve in widget.curves] == [[0.0, 1.0]]
    widget._on_data_update(from_file)
    widget._on_data_update(from_file)
    assert [curve.getData()[1].tolist() for curve in widget.curves] == [samples.tolist()]
    _clear_signal_config(mocked_client, "eiger", "data")


def test_multiwaveform_same_scan_rebind_discards_previous_traces(qtbot, mocked_client, monkeypatch):
    _fake_bridge_factory(monkeypatch)
    widget = create_widget(qtbot, MultiWaveform, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "data", signal_class="AsyncSignal", ndim=1, obj_name="eiger_data"
    )
    widget.plot("eiger", "data")
    widget._on_data_update(_async_update([np.array([1, 2]), np.array([3, 4])]))
    widget._on_data_update(
        replace(_async_update([np.array([5, 6])]), generation=1, reason="rebind")
    )
    assert len(widget.curves) == 1
    np.testing.assert_array_equal(widget.curves[0].getData()[1], [5, 6])
    _clear_signal_config(mocked_client, "eiger", "data")
