"""Per-curve pairing, in-place source changes and the data warning row of the plots."""

from types import SimpleNamespace
from unittest import mock

from bec_lib.data_api import SCAN_GROUP, CorrelationGroup
from bec_lib.data_api.data_bundler import DataBundler

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.plots.plot_base import PlotBase
from bec_widgets.widgets.plots.waveform.waveform import Waveform

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring


def _update(points, metadata=None, group=SCAN_GROUP):
    bundle = DataBundler("scan-1")
    for key, ordinals in points.items():
        series = bundle.get_series(*key, "monitored")
        for ordinal in ordinals:
            series.insert(ordinal, float(ordinal) * 2.0, 100.0 + ordinal)
    for key, values in (metadata or {}).items():
        bundle.get_series(*key, "monitored").update_metadata(**values)
    return bundle.build_update("live", metadata={"group": group})


def _stream_update(key, values, stamps):
    """An update of a scan-less device stream, as the Data API delivers it."""
    bundle = DataBundler("")
    series = bundle.get_series(*key, "unindexed")
    for value, stamp in zip(values, stamps):
        series.insert(None, value, stamp)
    return bundle.build_update(
        "live", metadata={"group": CorrelationGroup.standalone(key[0], key[1])}
    )


def _bridges(monkeypatch) -> list:
    """Replace the Qt bridge of the Waveform; returns the list the bridges are recorded in."""
    created = []

    class Bridge:
        def __init__(self, client, sources, scan="live", **_kwargs):
            self.sources, self.scan, self.closed = list(sources), scan, False
            self.updated, self.progress = mock.MagicMock(), mock.MagicMock()
            self.groups, self.unbound_sources, self.scan_id = {}, [], None
            created.append(self)

        def set_sources(self, sources):
            self.sources = list(sources)

        def set_min_emit_interval(self, _seconds):
            pass

        def close(self):
            self.closed = True

    monkeypatch.setattr("bec_widgets.widgets.plots.waveform.waveform.QtDataSubscription", Bridge)
    return created


def test_a_silent_signal_does_not_blank_the_other_curves(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "index"
    curve = wf.plot("bpm4i")
    silent = wf.plot("bpm3a")
    update = _update({("bpm4i", "bpm4i"): range(5), ("bpm3a", "bpm3a"): []})
    assert len(update.aligned()[("bpm4i", "bpm4i")]) == 0  # group-wide alignment is empty
    assert wf._render_curve_from_update(curve, update, update.aligned(), None)
    x, y = curve.get_data()
    assert list(x) == [0, 1, 2, 3, 4] and list(y) == [0.0, 2.0, 4.0, 6.0, 8.0]
    assert not wf._render_curve_from_update(silent, update, update.aligned(), None)


def test_a_curve_is_paired_with_its_own_x_only(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    curve = wf.plot("bpm4i")
    x_key = ("samx", "samx")
    update = _update({x_key: range(5), ("bpm4i", "bpm4i"): [0, 1, 2, 4], ("bpm3a", "bpm3a"): [0]})
    wf.x_axis_mode["name"] = "samx"
    assert wf._render_curve_from_update(curve, update, update.aligned(), x_key)
    x, y = curve.get_data()
    assert list(x) == [0.0, 2.0, 4.0, 8.0] and list(y) == [0.0, 2.0, 4.0, 8.0]


def test_adding_a_curve_keeps_the_subscription(qtbot, mocked_client, monkeypatch):
    created = _bridges(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.plot("bpm4i")
    first = wf._data_bridge
    wf.plot("bpm3a")
    assert wf._data_bridge is first and not first.closed
    assert ("bpm3a", "bpm3a") in first.sources and len(created) == 1
    wf._setup_data_api_subscription(scan="scan-9")  # another target: a new subscription
    assert wf._data_bridge is not first and first.closed


def test_data_warning_lists_what_the_update_reports():
    a, b = ("samx", "samx"), ("bpm4i", "bpm4i")
    update = _update({a: range(3), b: range(3)}, {b: {"stream_trimmed": True, "error": "boom"}})
    bridge = SimpleNamespace(unbound_sources=[("det", "wave")])
    text = PlotBase.data_warning_of(update, bridge)
    assert "bpm4i.bpm4i: boom" in text
    assert "start of the live stream" in text
    assert "det.wave: not available in this scan" in text
    assert PlotBase.data_warning_of(_update({a: range(3)})) is None


def test_data_warning_names_an_unserved_source_of_a_device_stream():
    update = _stream_update(("samx", "samx"), [1.0], [10.0])
    bridge = SimpleNamespace(unbound_sources=[("gauss", "gauss_data_x")])
    text = PlotBase.data_warning_of(update, bridge)
    assert text == "gauss.gauss_data_x: has no live value to follow"


def test_data_warning_row_shows_and_clears_per_group(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.set_data_warning("first", group=SCAN_GROUP)
    wf.set_data_warning("second", group=CorrelationGroup.standalone("det", "wave"))
    assert wf._data_rows == [("Data", "first; second")]
    wf.set_data_warning(None, group=SCAN_GROUP)
    assert wf._data_rows == [("Data", "second")]
    wf.set_data_warning(None, group=CorrelationGroup.standalone("det", "wave"))
    assert wf._data_rows == []


def test_data_warnings_go_with_their_subscription(qtbot, mocked_client, monkeypatch):
    created = _bridges(monkeypatch)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.plot("samx")
    live = created[-1]
    wf.set_data_warning("samx.samx: boom", group="/scan")
    wf.set_data_warning("det.wave: boom", group="/standalone:det/wave")
    wf.set_data_warning("scan 7: file missing", group="scan-7/scan")  # of a history curve

    # The source of one group is removed: its warning goes, the others stay.
    live.groups = {SCAN_GROUP: [("samx", "samx")]}
    wf._setup_data_api_subscription(scan="live")
    assert wf._data_bridge is live
    assert wf._data_rows == [("Data", "samx.samx: boom; scan 7: file missing")]

    # Another target: the subscription is replaced, and what the old one reported goes.
    wf._setup_data_api_subscription(scan="scan-9")
    assert live.closed
    assert wf._data_rows == [("Data", "scan 7: file missing")]
