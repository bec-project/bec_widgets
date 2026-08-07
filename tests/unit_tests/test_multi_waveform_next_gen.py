from unittest.mock import MagicMock

import numpy as np
from bec_lib.data_api.models import SourceData, SubscriptionUpdate

from bec_widgets.widgets.plots.multi_waveform.multi_waveform import MultiWaveform
from tests.unit_tests.client_mocks import mocked_client

from .conftest import create_widget

##################################################
# Test helpers (DataAPI fake bridge + updates)
##################################################


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
    assert mw.color_palette == "plasma"
    assert mw.max_trace == 200
    assert mw.flush_buffer is False
    assert mw.highlight_last_curve is True
    assert mw.opacity == 50
    assert mw.scan_id is None
    assert mw.highlighted_index == 0
    assert mw._data_bridge is None


def test_multiwaveform_set_monitor(qtbot, mocked_client):
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    assert mw.monitor is None

    # Set a monitor; data flows through a scan-less DataAPI subscription.
    mw.plot("waveform1d")
    assert mw.monitor == "waveform1d"
    assert mw.config.monitor == "waveform1d"
    assert mw.connected is True
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

    # Default color_palette is "magma"
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


def test_selection_toolbar_updates_widget(qtbot, mocked_client):
    """
    Confirm that selecting a monitor and a colormap from the selection toolbar
    updates the widget properties.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    monitor_selection_action = mw.toolbar.components.get_action("monitor_selection")
    cmap_action = mw.toolbar.components.get_action("color_map")

    monitor_selection_action.combobox.addItem("waveform1d")
    monitor_selection_action.combobox.setCurrentText("waveform1d")
    assert mw.monitor == "waveform1d"

    cmap_action.widget.colormap = "viridis"
    assert mw.color_palette == "viridis"


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
