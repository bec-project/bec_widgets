"""Tests for the widgets of the HDF5 viewer."""

import os
import threading
import time
from unittest import mock

import h5py
import numpy as np
import pytest
from bec_lib import messages
from bec_lib.scan_history import ScanHistory
from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QFontMetrics
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.tests.utils import create_history_file, create_widget
from bec_widgets.utils.error_popups import ErrorPopupUtility
from bec_widgets.widgets.services.hdf5_viewer import h5_reader
from bec_widgets.widgets.services.hdf5_viewer.h5_preview import H5Preview, views_for
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import H5Node, H5ReadError
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service
from bec_widgets.widgets.services.hdf5_viewer.h5_tree import (
    CONTEXT_ROLE,
    MATCH_ROLE,
    NODE_ROLE,
    PLACEHOLDER_ROLE,
    H5Tree,
)
from bec_widgets.widgets.services.hdf5_viewer.hdf5_viewer import HDF5Viewer
from bec_widgets.widgets.services.hdf5_viewer.pane_tabs import PaneTabs
from bec_widgets.widgets.services.hdf5_viewer.scan_list import (
    ScanEntry,
    ScanList,
    fit_parts,
    format_duration,
    format_when,
)
from bec_widgets.widgets.services.hdf5_viewer.signal_list import SignalList, classify

ROWS = 300_000


def settle(*paths):
    """Make files look like they were written a while ago."""
    past = time.time() - 600
    for path in paths:
        os.utime(path, (past, past))


@pytest.fixture
def data_file(tmp_path):
    """A file with a default plot, a long signal, a stack of frames and a link."""
    path = tmp_path / "S00007_master.h5"
    frames = tmp_path / "S00007_frames.h5"
    with h5py.File(frames, "w") as handle:
        handle["entry/data"] = np.arange(5 * 4 * 6, dtype=np.int32).reshape(5, 4, 6)
    with h5py.File(path, "w") as handle:
        entry = handle.create_group("entry")
        entry.attrs["default"] = "plot"
        plot = entry.create_group("plot")
        plot.attrs["signal"] = "counts"
        plot.attrs["axes"] = "energy"
        plot["counts"] = np.cos(np.arange(ROWS) / 3000.0)
        plot["energy"] = np.linspace(7000.0, 7100.0, ROWS)
        entry["name"] = "sample 7"
        entry["frames"] = h5py.ExternalLink(frames.name, "/entry/data")
        entry["broken"] = h5py.ExternalLink("S00007_missing.h5", "/entry/data")
    settle(path, frames)
    return path


@pytest.fixture
def service(qtbot):
    service = H5Service()
    yield service
    service.cleanup()


@pytest.fixture
def history(tmp_path):
    """Three finished scans with files, the newest last."""
    out = []
    start = time.time() - 7200
    for index, exit_status in enumerate(["closed", "aborted", "closed"]):
        points = 20
        x = np.linspace(-1, 1, points)
        data = {
            "baseline": {"mono": {"mono": {"value": [8.9], "timestamp": [1]}}},
            "monitored": {
                "samx": {"samx": {"value": x, "timestamp": np.arange(points)}},
                "bpm4i": {"bpm4i": {"value": x**2 + index, "timestamp": np.arange(points)}},
                "bpm3a": {"bpm3a": {"value": x + index, "timestamp": np.arange(points)}},
                # A device of the time of the scan that the session of today does not have.
                "old_diode": {"old_diode": {"value": x * 2, "timestamp": np.arange(points)}},
            },
            "async": {
                "camera": {
                    "camera": {"value": np.ones((points, 8, 8)), "timestamp": np.arange(points)}
                }
            },
        }
        info = messages._StoredDataInfo  # pylint: disable=protected-access
        stored = {
            "samx": {"samx": info(shape=(points,), dtype="float64")},
            "bpm4i": {"bpm4i": info(shape=(points,), dtype="float64")},
            "bpm3a": {"bpm3a": info(shape=(points,), dtype="float64")},
            "old_diode": {"old_diode": info(shape=(points,), dtype="float64")},
            "camera": {"camera": info(shape=(points, 8, 8), dtype="float64")},
            "mono": {"mono": info(shape=(1,), dtype="float64")},
        }
        metadata = {
            "scan_id": f"scan-{index}",
            "scan_name": "line_scan",
            "scan_type": "step",
            "status": "closed",
            "scan_number": 10 + index,
            "dataset_number": 1,
            "request_inputs": {"arg_bundle": ["samx", -1, 1], "kwargs": {"steps": points}},
            "num_points": points,
            "stored_data_info": stored,
            "scan_report_devices": [b"samx"],
        }
        file_path = str(tmp_path / f"S{10 + index:05d}_master.h5")
        msg = create_history_file(file_path, data, metadata)
        dump = msg.model_dump() | {
            "exit_status": exit_status,
            "start_time": start + 600 * index,
            "end_time": start + 600 * index + 75,
        }
        out.append(messages.ScanHistoryMessage.model_validate(dump))
        settle(file_path)
    return out


@pytest.fixture
def viewer(qtbot, mocked_client, history):
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in history:
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    widget = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    widget.resize(1200, 700)
    qtbot.waitUntil(lambda: widget.scan_list.model.rowCount() == 3)
    return widget


################################################################################
# Service
################################################################################


def test_service_reads_off_the_gui_thread_and_answers_on_it(qtbot, service, data_file):
    seen = {}

    def read(_ctx):
        seen["read_thread"] = threading.get_ident()
        return h5_reader.list_children(str(data_file), "/entry")

    def done(nodes):
        seen["done_thread"] = threading.get_ident()
        seen["names"] = [node.name for node in nodes]

    service.request("test", str(data_file), read, done)
    qtbot.waitUntil(lambda: "names" in seen)

    assert seen["read_thread"] != threading.get_ident()
    assert seen["done_thread"] == threading.get_ident()
    assert "plot" in seen["names"]


def test_service_delivers_only_the_newest_request_of_a_channel(qtbot, service, data_file):
    release = threading.Event()
    results = []

    def slow(_ctx):
        release.wait(5)
        return "old"

    service.request("same", str(data_file), slow, results.append)
    service.request("same", str(data_file), lambda _ctx: "new", results.append)
    release.set()
    qtbot.waitUntil(lambda: results == ["new"])
    qtbot.wait(100)

    assert results == ["new"]


def test_service_does_not_read_a_file_that_is_being_written(qtbot, service, data_file):
    os.utime(data_file, None)  # changed just now
    calls, errors, results = [], [], []

    def read(_ctx):
        calls.append(1)
        return "data"

    service.request("busy", str(data_file), read, results.append, errors.append)
    qtbot.waitUntil(lambda: len(errors) == 1)
    assert errors[0].kind == "busy"
    assert not calls and not results

    service.allow_busy_file(str(data_file))
    service.request("busy", str(data_file), read, results.append, errors.append)
    qtbot.waitUntil(lambda: results == ["data"])


def test_service_counts_the_bytes_it_read(qtbot, service, data_file):
    changed = []
    service.bytes_read_changed.connect(changed.append)
    service.request(
        "bytes",
        str(data_file),
        lambda _ctx: h5_reader.read_curve(str(data_file), "/entry/plot/counts", stop=10),
        lambda _curve: None,
    )
    qtbot.waitUntil(lambda: changed == [str(data_file)])
    assert service.bytes_read(str(data_file)) == 80


################################################################################
# Tree
################################################################################


def child_names(item):
    return [item.child(row).text() for row in range(item.rowCount())]


def test_tree_lists_groups_only_when_they_are_opened(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    selected = []
    tree.node_selected.connect(selected.append)

    tree.set_file(str(data_file), select_path="/entry")
    root = tree.model.item(0)
    qtbot.waitUntil(lambda: child_names(root) == ["entry"])
    entry = root.child(0)
    qtbot.waitUntil(lambda: "plot" in child_names(entry))

    # The group below is known by name only until it is opened.
    plot = entry.child(child_names(entry).index("plot"))
    assert plot.child(0).data(PLACEHOLDER_ROLE)
    tree.view.expand(plot.index())
    qtbot.waitUntil(lambda: child_names(plot) == ["counts", "energy"])
    tree.cleanup()


def test_tree_opens_along_the_default_plot_of_the_file(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    selected = []
    tree.node_selected.connect(selected.append)

    tree.set_file(str(data_file))

    qtbot.waitUntil(lambda: bool(selected) and selected[-1] is not None)
    assert selected[-1].path == "/entry/plot/counts"
    tree.cleanup()


def test_tree_follows_a_link_into_another_file_when_it_is_selected(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    selected = []
    tree.node_selected.connect(selected.append)
    tree.set_file(str(data_file), select_path="/entry/name")
    qtbot.waitUntil(lambda: bool(selected) and selected[-1].name == "name")

    tree.select_path("/entry/frames")
    qtbot.waitUntil(lambda: selected[-1].name == "frames")
    assert selected[-1].kind == "dataset"
    assert selected[-1].shape == (5, 4, 6)
    assert selected[-1].file_path.endswith("S00007_frames.h5")

    tree.select_path("/entry/broken")
    qtbot.waitUntil(lambda: selected[-1].name == "broken")
    assert selected[-1].kind == "broken"
    tree.cleanup()


def found_root(tree):
    return tree.found_model.item(0)


def test_tree_finds_entries_by_name_and_shows_names_in_their_branch(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.set_file(str(data_file), select_path="/entry")
    qtbot.waitUntil(lambda: tree.model.item(0).rowCount() == 1)

    tree.find_edit.setText("ENER")
    qtbot.waitUntil(lambda: tree.view.model() is tree.found_model)
    # The way to the match is a branch of the tree, opened, with names instead of paths.
    root = found_root(tree)
    assert child_names(root) == ["entry"]
    entry = root.child(0)
    assert entry.data(CONTEXT_ROLE) and child_names(entry) == ["plot"]
    plot = entry.child(0)
    assert child_names(plot) == ["energy"]
    energy = plot.child(0)
    assert energy.data(NODE_ROLE).path == "/entry/plot/energy"
    assert energy.data(MATCH_ROLE) == (0, 4)
    assert tree.view.isExpanded(plot.index())
    assert tree.note.text() == "1 match"
    # Nothing is read only because something was typed.
    assert not tree.view.currentIndex().isValid()

    tree.find_edit.setText("zzz")
    qtbot.waitUntil(lambda: "No name" in tree.note.text())
    tree.find_edit.clear()
    assert tree.view.model() is tree.model
    tree.cleanup()


def test_tree_search_matches_names_not_paths(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.set_file(str(data_file), select_path="/entry")
    qtbot.waitUntil(lambda: tree.model.item(0).rowCount() == 1)

    tree.find_edit.setText("plot")
    qtbot.waitUntil(lambda: tree.view.model() is tree.found_model)
    plot = found_root(tree).child(0).child(0)
    assert plot.data(MATCH_ROLE) == (0, 4)
    # Its children do not match because of their parent; they are listed when it is opened.
    assert plot.child(0).data(PLACEHOLDER_ROLE)
    assert tree.note.text() == "1 match"
    tree.cleanup()


def test_tree_search_result_is_selected_and_its_group_lists_children(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    selected = []
    tree.node_selected.connect(selected.append)
    tree.set_file(str(data_file), select_path="/entry")
    qtbot.waitUntil(lambda: tree.model.item(0).rowCount() == 1)

    tree.find_edit.setText("plot")
    qtbot.waitUntil(lambda: tree.view.model() is tree.found_model)
    plot = found_root(tree).child(0).child(0)
    tree.view.setCurrentIndex(plot.index())
    qtbot.waitUntil(lambda: selected[-1] is not None and selected[-1].path == "/entry/plot")

    tree.view.expand(plot.index())
    qtbot.waitUntil(lambda: child_names(plot) == ["counts", "energy"])
    # Bold marks the matches here, so the default signal of the plot is not bold.
    assert not plot.child(0).font().bold()
    tree.view.setCurrentIndex(plot.child(0).index())
    qtbot.waitUntil(lambda: selected[-1] is not None and selected[-1].path == "/entry/plot/counts")
    tree.cleanup()


def test_tree_enter_in_the_search_selects_the_first_match(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    selected = []
    tree.node_selected.connect(selected.append)
    tree.set_file(str(data_file), select_path="/entry")
    qtbot.waitUntil(lambda: tree.model.item(0).rowCount() == 1)

    tree.find_edit.setText("ener")
    qtbot.waitUntil(lambda: tree.view.model() is tree.found_model)
    qtbot.keyClick(tree.find_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: selected[-1] is not None and selected[-1].path == "/entry/plot/energy")

    qtbot.keyClick(tree.find_edit, Qt.Key.Key_Escape)
    assert tree.find_edit.text() == ""
    tree.cleanup()


def test_clearing_the_search_reveals_the_selected_match_in_the_tree(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.set_file(str(data_file), select_path="/entry")
    qtbot.waitUntil(lambda: tree.model.item(0).rowCount() == 1)

    tree.find_edit.setText("ener")
    qtbot.waitUntil(lambda: tree.view.model() is tree.found_model)
    assert tree.enter_results()
    tree.find_edit.clear()

    assert tree.view.model() is tree.model
    qtbot.waitUntil(lambda: tree.current_node() is not None)
    assert tree.current_node().path == "/entry/plot/energy"
    assert tree.view.isExpanded(tree.view.currentIndex().parent())
    tree.cleanup()


def test_find_branches_lists_the_groups_on_the_way(data_file):
    result = h5_reader.find_branches(str(data_file), "ener")
    assert [node.path for node in result.matches] == ["/entry/plot/energy"]
    assert sorted(node.path for node in result.ancestors) == ["/entry", "/entry/plot"]
    assert not result.truncated


def dataset(file_path, path, shape, dtype_kind="f"):
    name = path.rsplit("/", 1)[-1]
    return H5Node(name, path, str(file_path), "dataset", shape, "float64", dtype_kind)


def test_views_offered_for_a_dataset():
    assert views_for(dataset("f", "/a", (100,))) == ["line", "table"]
    assert views_for(dataset("f", "/a", (5, 4, 6))) == ["image", "line", "table"]
    assert views_for(dataset("f", "/a", ())) == ["value"]
    assert views_for(dataset("f", "/a", (3,), "S")) == ["value"]
    assert views_for(dataset("f", "/a", (300,), "S")) == ["table"]
    assert views_for(H5Node("g", "/g", "f", "group")) == []


def test_preview_draws_a_long_signal_reduced_and_reads_the_rows_in_view(
    qtbot, service, mocked_client, data_file, monkeypatch
):
    monkeypatch.setattr(h5_reader, "OVERVIEW_POINTS", 2_000)
    monkeypatch.setattr(
        h5_reader.read_curve, "__defaults__", ((), None, None, 2_000, None, None, None)
    )
    preview = H5Preview(service, client=mocked_client)
    qtbot.addWidget(preview)
    preview.resize(800, 500)
    preview.show()

    preview.show_node(dataset(data_file, "/entry/plot/counts", (ROWS,)))
    qtbot.waitUntil(lambda: preview._overview is not None)

    assert preview.view == "line"
    assert preview._overview.reduced
    # The x axis the file names is chosen without asking.
    assert preview.x_combo.currentData() == "/entry/plot/energy"
    assert "lowest and highest" in preview.info_label.text()
    points_before = len(preview._curve.xData)

    preview._waveform.plot_item.vb.setXRange(7050.0, 7050.2, padding=0)
    qtbot.waitUntil(lambda: preview._detail_bins is not None)

    assert len(preview._curve.xData) > points_before
    assert "in full" in preview.info_label.text()
    # The curve still spans the whole signal, so zooming out needs no new read.
    assert preview._curve.xData[0] == 7000.0
    preview.cleanup()
    preview._waveform.close()
    preview._waveform.deleteLater()


def test_preview_reads_one_frame_of_a_stack(qtbot, service, mocked_client, data_file):
    frames = data_file.parent / "S00007_frames.h5"
    preview = H5Preview(service, client=mocked_client)
    qtbot.addWidget(preview)

    preview.show_node(dataset(frames, "/entry/data", (5, 4, 6), "i"))
    qtbot.waitUntil(lambda: preview.stack.currentWidget() is preview.image_page)
    assert preview.view == "image"
    np.testing.assert_array_equal(preview._image.main_image.raw_data, np.arange(24).reshape(4, 6))

    preview.index_bar._spins[0].setValue(3)
    qtbot.waitUntil(lambda: preview._image.main_image.raw_data[0, 0] == 72)
    assert "Frame 3 of 5" in preview.info_label.text()
    assert service.bytes_read(str(frames)) == 2 * 4 * 6 * 4

    preview.view_buttons["table"].click()
    qtbot.waitUntil(lambda: preview.table_model.index(1, 2).data() == "80")
    assert preview.table_model.rowCount() == 4
    assert preview.table_model.columnCount() == 6
    preview.cleanup()
    preview._image.close()
    preview._image.deleteLater()


def test_preview_shows_a_text_and_explains_a_missing_file(qtbot, service, data_file):
    preview = H5Preview(service)
    qtbot.addWidget(preview)
    details = []
    preview.details_changed.connect(details.append)

    preview.show_node(dataset(data_file, "/entry/name", (), "S"))
    qtbot.waitUntil(lambda: preview.stack.currentWidget() is preview.value_view)
    assert preview.value_view.toPlainText() == "sample 7"
    assert details[-1].node.path == "/entry/name"

    preview.show_node(dataset(data_file.parent / "gone.h5", "/entry/name", (), "S"))
    qtbot.waitUntil(lambda: preview.state_page.title.text() == "Not found")
    assert "gone.h5" in preview.state_page.text.text()
    assert preview.stack.currentWidget() is preview.state_page

    preview.show_node(None)
    assert preview.state_page.title.text() == "Nothing picked"
    preview.cleanup()


################################################################################
# Scans and signals
################################################################################


def test_times_and_durations_read_naturally():
    assert format_duration(48) == "48 s"
    assert format_duration(192) == "3 min 12 s"
    assert format_duration(7500) == "2 h 05 min"
    now = time.mktime((2026, 11, 16, 20, 0, 0, 0, 0, -1))
    assert format_when(now - 3600, now) == "19:00"
    assert format_when(now - 4 * 86400, now) == "12 Nov 20:00"
    assert format_when(0) == ""


def test_scan_list_filters_and_pins(qtbot, history):
    scans = ScanList()
    qtbot.addWidget(scans)
    selected, pins = [], []
    scans.scan_selected.connect(selected.append)
    scans.pins_changed.connect(lambda: pins.append(scans.model.pins()))

    scans.set_entries([ScanEntry.from_history(msg.model_dump()) for msg in history])

    # Newest first, and the newest is selected.
    assert [entry.scan_number for entry in scans.model.entries()] == [12, 11, 10]
    assert selected[-1].scan_number == 12
    assert scans.note.text() == "3 scans"
    assert selected[-1].summary().startswith("samx  ·  20 points  ·  1 min 15 s")

    scans.ending_buttons["early"].click()
    assert scans.filter_model.rowCount() == 1
    assert scans.note.text() == "1 of 3 scans"
    scans.ending_buttons["all"].click()
    scans.search_edit.setText("nothing like this")
    assert scans.filter_model.rowCount() == 0
    assert "No scan fits" in scans.note.text()
    scans.search_edit.setText("11")
    assert scans.filter_model.rowCount() == 1
    # Searching changes what is listed, not which scan is selected.
    assert scans.current_entry().scan_number == 12
    assert not scans.view.currentIndex().isValid()
    scans.search_edit.clear()
    assert scans.view.currentIndex().data(Qt.ItemDataRole.DisplayRole).startswith("Scan 12")
    assert len(selected) == 1

    scans.model.toggle_pin("scan-0")
    assert pins[-1] == {"scan-0": 1}
    assert not scans.unpin_button.isHidden()
    qtbot.keyClick(scans.view, Qt.Key.Key_P)  # the selected scan
    assert set(pins[-1]) == {"scan-0", selected[-1].scan_id}
    scans.unpin_button.click()
    assert pins[-1] == {}


def test_signals_are_grouped_by_what_can_share_a_plot():
    assert classify((120,), 120) == "point"
    assert classify((6000,), 120) == "fast"
    assert classify((120, 256), 120) == "array"
    assert classify((1,), 120) == "single"
    assert classify((), 120) == "single"
    assert classify((120,), None, "monitored") == "point"
    assert classify((120,), 120, "async") == "fast"
    # A running scan: the shape is not known yet.
    assert classify((0,), 120, "monitored") == "point"


def test_signal_list_keeps_one_group_on_the_plot(qtbot, history):
    signals = SignalList()
    qtbot.addWidget(signals)
    changes, opened = [], []
    signals.selection_changed.connect(lambda: changes.append(1))
    signals.open_requested.connect(opened.append)
    entry = ScanEntry.from_history(history[0].model_dump())
    entry.stored_data_info["adc"] = {"adc": {"shape": (5000,), "dtype": "float64"}}

    signals.set_scan(entry)

    # The first detector is on the plot, not the motor that was scanned.
    assert signals.y_signals() == [("bpm3a", "bpm3a")]
    assert signals.x_signal() is None
    groups = {signal.key: signal.group for signal in signals.signals()}
    assert groups[("camera", "camera")] == "array"
    assert groups[("mono", "mono")] == "single"
    assert groups[("adc", "adc")] == "fast"

    signals.toggle_y(("bpm4i", "bpm4i"))
    signals.toggle_x(("samx", "samx"))
    assert signals.y_signals() == [("bpm3a", "bpm3a"), ("bpm4i", "bpm4i")]
    assert signals.x_signal() == ("samx", "samx")
    assert "2 signals on the plot" in signals.note.text()

    # A fast signal cannot share the plot with signals per scan point.
    signals.toggle_y(("adc", "adc"))
    assert signals.y_signals() == [("adc", "adc")]
    assert signals.x_signal() is None
    signals.toggle_x(("adc", "adc"))
    assert signals.x_signal() is None

    signals.toggle_y(("camera", "camera"))
    assert signals.y_signals() == [("adc", "adc")]

    signals.filter_edit.setText("zzz")
    assert signals.note.text() == "No signal fits the filter."
    assert len(changes) >= 4


################################################################################
# Viewer
################################################################################


def test_viewer_lists_the_history_and_plots_the_newest_scan(qtbot, viewer):
    assert viewer.scan_list.current_entry().scan_number == 12
    qtbot.waitUntil(lambda: ("scan-2", "bpm3a", "bpm3a") in viewer._curves)
    curve = viewer._curves[("scan-2", "bpm3a", "bpm3a")][0]
    assert curve.config.source == "history"
    assert curve.config.scan_id == "scan-2"
    assert viewer.plot_stack.currentWidget() is viewer.waveform
    assert viewer.plot_title.text() == "Scan 12  line_scan"
    # The curve gets its data through the Data API.
    qtbot.waitUntil(lambda: curve.xData is not None and len(curve.xData) == 20, timeout=10000)


def click_scan_row(qtbot, viewer, row, modifier=Qt.KeyboardModifier.NoModifier):
    view = viewer.scan_list.view
    rect = view.visualRect(view.model().index(row, 0))
    # Left of the pin, so that the click lands on the row itself.
    point = rect.topLeft() + QPoint(40, rect.height() // 2)
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, modifier, point)


def test_ctrl_click_adds_a_scan_to_the_comparison_and_takes_it_off(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    assert "to compare" in viewer.plot_subtitle.text()
    selected = viewer.scan_list.current_entry().scan_id

    click_scan_row(qtbot, viewer, 2, Qt.KeyboardModifier.ControlModifier)

    # The selection stays; the clicked scan joins the plot.
    assert viewer.scan_list.current_entry().scan_id == selected
    assert set(viewer.scan_list.model.pins()) == {"scan-0"}
    assert ("scan-0", "bpm3a", "bpm3a") in viewer._curves
    assert "compared with 10" in viewer.plot_subtitle.text()

    click_scan_row(qtbot, viewer, 2, Qt.KeyboardModifier.ControlModifier)
    assert viewer.scan_list.model.pins() == {}
    assert "to compare" in viewer.plot_subtitle.text()


def test_shift_click_adds_every_scan_up_to_the_clicked_one(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    selected = viewer.scan_list.current_entry().scan_id

    click_scan_row(qtbot, viewer, 2, Qt.KeyboardModifier.ShiftModifier)

    assert viewer.scan_list.current_entry().scan_id == selected
    assert set(viewer.scan_list.model.pins()) == {"scan-1", "scan-0"}
    assert {key[0] for key in viewer._curves} == {"scan-2", "scan-1", "scan-0"}

    # A plain click only selects; the pins stay.
    click_scan_row(qtbot, viewer, 1)
    assert viewer.scan_list.current_entry().scan_id == "scan-1"
    assert set(viewer.scan_list.model.pins()) == {"scan-1", "scan-0"}


def test_viewer_compares_pinned_scans_in_one_colour_each(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    viewer.signal_list.toggle_y(("bpm4i", "bpm4i"))
    assert len(viewer._curves) == 2
    colours = {curve.config.color for curve, _live in viewer._curves.values()}
    assert len(colours) == 2  # one scan: a colour per signal

    viewer.scan_list.model.toggle_pin("scan-0")

    assert set(viewer._curves) == {
        ("scan-2", "bpm3a", "bpm3a"),
        ("scan-2", "bpm4i", "bpm4i"),
        ("scan-0", "bpm3a", "bpm3a"),
        ("scan-0", "bpm4i", "bpm4i"),
    }
    config = {key: curve.config for key, (curve, _live) in viewer._curves.items()}
    assert config[("scan-2", "bpm3a", "bpm3a")].color == config[("scan-2", "bpm4i", "bpm4i")].color
    assert config[("scan-0", "bpm3a", "bpm3a")].color != config[("scan-2", "bpm3a", "bpm3a")].color
    assert config[("scan-2", "bpm3a", "bpm3a")].pen_style == "solid"
    assert config[("scan-2", "bpm4i", "bpm4i")].pen_style == "dash"
    assert "compared with 10" in viewer.plot_subtitle.text()

    viewer.scan_list.model.toggle_pin("scan-0")
    assert len(viewer._curves) == 2

    viewer.signal_list.toggle_y(("bpm3a", "bpm3a"))
    viewer.signal_list.toggle_y(("bpm4i", "bpm4i"))
    assert not viewer._curves
    assert viewer.plot_stack.currentWidget() is viewer.plot_state
    assert viewer.plot_state.title.text() == "Nothing on the plot"


def legend_texts(viewer):
    legend = viewer.waveform.plot_item.legend
    return {key: legend.getLabel(curve).text for key, (curve, _live) in viewer._curves.items()}


def test_viewer_keeps_the_waveform_names_of_history_curves(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    key = ("scan-2", "bpm3a", "bpm3a")
    # The curves are history curves of their scans and are named as the Waveform names them.
    curve = viewer._curves[key][0]
    assert curve.name() == "bpm3a-bpm3a-scan-12"
    assert curve.config.source == "history" and curve.config.scan_number == 12
    assert legend_texts(viewer) == {key: "bpm3a-bpm3a-scan-12"}

    viewer.scan_list.model.toggle_pin("scan-0")

    assert legend_texts(viewer) == {
        key: "bpm3a-bpm3a-scan-12",
        ("scan-0", "bpm3a", "bpm3a"): "bpm3a-bpm3a-scan-10",
    }


def test_viewer_explains_a_signal_the_session_cannot_plot(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)

    with mock.patch.object(ErrorPopupUtility(), "custom_exception_hook") as popup:
        viewer.signal_list.toggle_y(("old_diode", "old_diode"))

    # No popup and no broken entry: the reason stands under the title of the plot.
    popup.assert_not_called()
    assert set(viewer._curves) == {("scan-2", "bpm3a", "bpm3a")}
    assert "old_diode is not a device of the current BEC session" in viewer.plot_subtitle.text()
    assert legend_texts(viewer) == {("scan-2", "bpm3a", "bpm3a"): "bpm3a-bpm3a-scan-12"}


def test_tabs_open_a_page_and_say_so(qtbot):
    tabs = PaneTabs()
    qtbot.addWidget(tabs)
    first, second = QWidget(), QWidget()
    opened = []
    tabs.current_changed.connect(opened.append)
    assert tabs.add_tab(first, "Signals") == 0
    assert tabs.add_tab(second, "File", "Everything in the file") == 1
    assert tabs.current_index() == 0

    tabs._buttons[1].click()
    assert tabs.current_index() == 1
    assert tabs._stack.currentWidget() is second
    tabs.set_current_index(1)
    tabs.set_current_index(5)
    assert opened == [1]
    tabs.set_current_index(0)
    assert tabs._buttons[0].isChecked() and not tabs._buttons[1].isChecked()
    assert opened == [1, 0]


def test_tree_leaves_the_type_column_out_while_it_is_narrow(qtbot, service):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.resize(500, 400)
    tree.show()
    qtbot.waitUntil(lambda: not tree.view.isColumnHidden(2))
    tree.resize(320, 400)
    qtbot.waitUntil(lambda: tree.view.isColumnHidden(2))
    tree.cleanup()


def test_viewer_sets_the_x_axis_from_the_signal_list(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    viewer.signal_list.toggle_x(("samx", "samx"))
    assert viewer.waveform.x_mode == "samx"
    viewer.signal_list.toggle_x(("samx", "samx"))
    assert viewer.waveform.x_mode == "auto"


def test_viewer_shows_the_file_of_the_scan_in_the_file_tab(qtbot, viewer, history):
    viewer.tabs.set_current_index(1)
    assert viewer.right_stack.currentWidget() is viewer.preview
    qtbot.waitUntil(lambda: viewer.tree.model.rowCount() == 1)
    assert viewer.tree.file_path == history[2].file_path
    qtbot.waitUntil(lambda: viewer.tree.model.item(0).rowCount() == 1)
    assert "never locked" in viewer.status_label.text()

    # An image of the scan opens in the file view at the place BEC stored it.
    viewer.tabs.set_current_index(0)
    camera = next(s for s in viewer.signal_list.signals() if s.device == "camera")
    viewer.signal_list.open_requested.emit(camera)
    assert viewer.tabs.current_index() == 1
    qtbot.waitUntil(
        lambda: viewer.preview.node is not None
        and viewer.preview.node.path == "/entry/collection/devices/camera/camera/value"
    )
    qtbot.waitUntil(lambda: viewer.preview.view == "image")


def test_viewer_waits_for_a_file_that_is_still_being_written(qtbot, viewer, history):
    os.utime(history[2].file_path, None)  # the writer just touched it
    viewer.tabs.set_current_index(1)

    qtbot.waitUntil(lambda: viewer.preview.state_page.title.text() == "Still being written")
    assert viewer._busy_timer.isActive()
    assert viewer.service.bytes_read(history[2].file_path) == 0

    # Once the writer is done the file opens without a click.
    settle(history[2].file_path)
    viewer._busy_timer.setInterval(50)
    viewer._busy_timer.start()
    qtbot.waitUntil(
        lambda: viewer.tree.model.rowCount() == 1
        and child_names(viewer.tree.model.item(0)) == ["entry"]
    )
    assert not viewer._busy_timer.isActive()
    assert viewer.preview.state_page.title.text() != "Still being written"


def test_viewer_opens_any_file_and_selects_a_dataset(qtbot, viewer, data_file):
    viewer.open_file(str(data_file), "/entry/name")

    assert viewer.tabs.current_index() == 1
    assert viewer.scan_list.current_entry() is None
    qtbot.waitUntil(
        lambda: viewer.preview.node is not None and viewer.preview.node.path == "/entry/name"
    )
    qtbot.waitUntil(lambda: viewer.preview.view == "value")
    # The files of the same scan are offered next to it, closed.
    assert viewer.tree.model.rowCount() == 2
    assert viewer.tree.model.item(1).text() == "S00007_frames.h5"

    viewer.show_scan(11)
    assert viewer.scan_list.current_entry().scan_id == "scan-1"
    with pytest.raises(ValueError):
        viewer.show_scan(999, _override_slot_params={"raise_error": True})


def test_viewer_lists_a_running_scan_and_keeps_its_file_closed(qtbot, viewer):
    status = {
        "scan_id": "live-1",
        "status": "open",
        "scan_number": 13,
        "scan_name": "line_scan",
        "num_points": 50,
        "readout_priority": {"monitored": ["samx", "bpm4i"], "async": []},
        "scan_report_devices": ["samx"],
        "timestamp": time.time(),
    }
    viewer.on_scan_status(status, {})

    entries = viewer.scan_list.model.entries()
    assert entries[0].live and entries[0].scan_number == 13
    viewer.scan_list.select("live-1")
    assert [signal.group for signal in viewer.signal_list.signals()] == ["point", "point"]

    viewer.tabs.set_current_index(1)
    assert viewer.preview.state_page.title.text() == "Scan 13 is still running"
    assert viewer.tree.model.rowCount() == 0
    assert "not opened" in viewer.status_label.text()

    # A scan that ended is replaced by its history entry, never listed twice.
    viewer.on_scan_status(status | {"status": "closed"}, {})
    viewer._on_history_updated(
        {
            "scan_id": "live-1",
            "scan_number": 13,
            "scan_name": "line_scan",
            "exit_status": "closed",
            "start_time": time.time() - 60,
            "end_time": time.time(),
            "num_points": 50,
            "file_path": "/data/S00013_master.h5",
            "stored_data_info": {},
        }
    )
    listed = [entry for entry in viewer.scan_list.model.entries() if entry.scan_id == "live-1"]
    assert len(listed) == 1 and not listed[0].live


def test_scan_row_leaves_out_the_last_parts_instead_of_cutting_them(qtbot):
    metrics = QFontMetrics(QApplication.font())
    parts = ["samx", "100 points", "3 s"]
    full = "  ·  ".join(parts)
    assert fit_parts(parts, metrics, metrics.horizontalAdvance(full)) == full
    two = "  ·  ".join(parts[:2])
    assert fit_parts(parts, metrics, metrics.horizontalAdvance(two) + 2) == two
    # Only the first part is ever cut, and only when nothing else fits.
    assert fit_parts(parts, metrics, metrics.horizontalAdvance("sa")).endswith("…")
    assert fit_parts([], metrics, 100) == ""


def contrast(a, b):
    def lum(c):
        def ch(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())

    high, low = sorted((lum(a), lum(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_muted_text_is_the_queue_colour_and_stays_readable(qtbot, theme):
    # pylint: disable=import-outside-toplevel
    from qtpy.QtGui import QPalette
    from qtpy.QtWidgets import QLabel

    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.utils.theme_utils import theme_colors
    from bec_widgets.widgets.services.hdf5_viewer.style import mute, muted_color, remute

    holder = QWidget()
    qtbot.addWidget(holder)
    label = QLabel("note", holder)
    mute(label)
    apply_theme(theme)
    remute(holder)

    color = label.palette().color(QPalette.ColorRole.WindowText)
    assert color == muted_color()
    assert contrast(color, theme_colors()["bg"]) >= 4.5
    apply_theme("light")
