"""Tests for the widgets of the HDF5 viewer."""

import os
import re
import sys
import threading
import time
from datetime import datetime
from unittest import mock

import h5py
import numpy as np
import pytest
from bec_lib import messages
from bec_lib.scan_history import ScanHistory
from qtpy.QtCore import QEvent, QLocale, QObject, QPoint, Qt
from qtpy.QtGui import QColor, QFocusEvent, QFontMetrics, QKeyEvent, QPalette
from qtpy.QtWidgets import QApplication, QLabel, QStyleOptionViewItem, QToolButton, QWidget

from bec_widgets.tests.utils import create_history_file, create_widget
from bec_widgets.utils.error_popups import ErrorPopupUtility
from bec_widgets.widgets.containers import qt_ads as QtAds
from bec_widgets.widgets.services.hdf5_viewer import file_box, h5_preview, h5_reader
from bec_widgets.widgets.services.hdf5_viewer.file_box import FileBox
from bec_widgets.widgets.services.hdf5_viewer.h5_preview import (
    SCAN_AXES,
    TIME,
    H5Preview,
    dataset_name,
    error_state,
    grid_image,
    views_for,
)
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import H5Node, H5ReadError
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service
from bec_widgets.widgets.services.hdf5_viewer.h5_tree import (
    CONTEXT_ROLE,
    MATCH_ROLE,
    NODE_ROLE,
    PLACEHOLDER_ROLE,
    ROW_RING_GAP,
    SELECT_DELAY_MS,
    STATE_ROLE,
    TREE_ROW_HEIGHT,
    X_BUTTON_ROOM,
    Y_COLUMN,
    Y_COLUMN_WIDTH,
    Z_BUTTON_ROOM,
    H5Tree,
    ZButton,
    _MutedColumnDelegate,
)
from bec_widgets.widgets.services.hdf5_viewer.hdf5_viewer import (
    COPY_MAX_POINTS,
    MIDDLE_OPEN_WIDTH,
    SCAN_LIST_OPEN_WIDTH,
    SWITCH_HOLD_MS,
    FactsLabel,
    HDF5Viewer,
    PathLabel,
    planned_on_one_line,
    read_sentence,
)
from bec_widgets.widgets.services.hdf5_viewer.scan_list import (
    ENTRY_ROLE,
    NAME_KEEPS_POINTS,
    NAME_KEEPS_TIME,
    ROW_HEIGHT,
    STATE_KEPT_MS,
    ScanEntry,
    ScanList,
    day_label,
    fit_parts,
    format_duration,
    format_when,
    grid_shape,
    scan_motors,
    series_color,
)
from bec_widgets.widgets.services.hdf5_viewer.signal_list import (
    ASYNC_NOTE,
    AUTO_TIP,
    BOX_ROLE,
    INDEX_X,
    SIGNAL_ROLE,
    TIMESTAMP_X,
    DatasetKey,
    SignalList,
    box_of,
    classify,
    signals_of,
)

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
    return make_history(tmp_path, (10, 11, 12))


def make_history(tmp_path, numbers):
    """Three finished scans with files and the given scan numbers, the newest last."""
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
                # A fast signal: many samples per scan point, one timestamp per point.
                "wave": {
                    "wave": {"value": np.arange(points * 50.0), "timestamp": np.arange(points)}
                },
                "camera": {
                    "camera": {"value": np.ones((points, 8, 8)), "timestamp": np.arange(points)}
                },
            },
        }
        info = messages._StoredDataInfo  # pylint: disable=protected-access
        stored = {
            "samx": {"samx": info(shape=(points,), dtype="float64")},
            "bpm4i": {"bpm4i": info(shape=(points,), dtype="float64")},
            "bpm3a": {"bpm3a": info(shape=(points,), dtype="float64")},
            "old_diode": {"old_diode": info(shape=(points,), dtype="float64")},
            "wave": {"wave": info(shape=(points * 50,), dtype="float64")},
            "camera": {"camera": info(shape=(points, 8, 8), dtype="float64")},
            "mono": {"mono": info(shape=(1,), dtype="float64")},
        }
        metadata = {
            "scan_id": f"scan-{index}",
            "scan_name": "line_scan",
            "scan_type": "step",
            "status": "closed",
            "scan_number": numbers[index],
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
    return make_viewer(qtbot, mocked_client, history)


def make_viewer(qtbot, mocked_client, history):
    """The viewer on a history, showing its newest scan."""
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in history:
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    widget = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    widget.resize(1200, 700)
    qtbot.waitUntil(lambda: widget.scan_list.model.rowCount() == 3)
    wait_for_switch(qtbot, widget)  # the newest scan is shown
    return widget


def wait_for_switch(qtbot, viewer):
    """A scan picked in the list is shown once the event loop has run."""
    qtbot.waitUntil(lambda: not viewer._switch_timer.isActive())  # pylint: disable=protected-access


def box_text(signal_list) -> str:
    """
    The box on top of the signal list as one line, read from its chips: each role with the
    names it holds, "auto" for those the scan chose, e.g. "X: samx auto | Y: bpm3a auto".
    """
    rows = []
    for letter, field in signal_list.box.fields.items():
        names = ", ".join(
            f"{chip.info.label} auto" if chip.info.auto else chip.info.label
            for chip in field.flow.chips
        )
        rows.append(f"{letter}: {names}" if names else f"{letter}:")
    return " | ".join(rows)


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


def test_reader_joins_a_file_another_reader_holds_open_with_the_default_lock(data_file):
    # The DataAPI opens scan files with h5py's default locking; while it holds one open,
    # HDF5 refuses an open with locking=False in the same process.
    with h5py.File(data_file, "r"):
        with h5_reader.open_readonly(str(data_file)) as handle:
            assert "plot" in handle["entry"]
        curve = h5_reader.read_curve(str(data_file), "/entry/plot/counts", stop=10)
    assert len(curve.y) == 10


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
        h5_reader.read_curve, "__defaults__", ((), None, None, 2_000, None, None, None, False)
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
    # The plot ranges itself once after a curve is added; zoom after that, as a person would.
    qtbot.wait(300)

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


def test_unpin_all_says_it_in_the_words_of_the_pin(qtbot):
    scans = ScanList()
    qtbot.addWidget(scans)
    assert scans.unpin_button.toolTip() == "Take all pinned scans off the plot"


def test_day_headers_name_the_weekday_this_year_and_let_it_go_first(qtbot):
    # pylint: disable=import-outside-toplevel
    from datetime import date

    from qtpy.QtGui import QFont, QFontMetrics

    from bec_widgets.widgets.services.hdf5_viewer.scan_list import day_title

    today = date(2026, 11, 19)
    assert day_label(today, today) == "Today"
    assert day_label(date(2026, 11, 18), today) == "Yesterday"
    assert day_label(date(2026, 11, 16), today) == "Mon 16 Nov"
    assert day_label(date(2026, 3, 2), today) == "Mon 2 Mar"
    assert day_label(date(2025, 11, 16), today) == "16 Nov 2025"
    metrics = QFontMetrics(QFont())
    assert day_title("Mon 16 Nov", metrics, 1000) == "MON 16 NOV"
    assert day_title("Mon 16 Nov", metrics, metrics.horizontalAdvance("16 NOV")) == "16 NOV"
    # Only a weekday gives way: neither the day of an older year nor a two-word label.
    assert day_title("16 Nov 2025", metrics, 10) == "16 NOV 2025"
    assert day_title("No date", metrics, 10) == "NO DATE"


def test_the_scan_list_says_why_it_is_empty_and_offers_the_way_out(qtbot, history):
    scans = ScanList()
    qtbot.addWidget(scans)
    scans.show()
    qtbot.waitExposed(scans)
    scans.activateWindow()
    qtbot.waitActive(scans)
    reloads, opens = [], []
    scans.reload_requested.connect(lambda: reloads.append(1))
    scans.open_file_requested.connect(lambda: opens.append(1))

    def actions():
        return [button.text() for button in scans.state._actions]

    # Until the scans are read, the list is not empty: it is being read. A read that answers
    # within LOADING_SHOWN_AFTER_MS shows nothing in between, so that it does not flicker.
    assert scans.list_stack.currentWidget() is scans.blank
    assert scans.note.text() == ""
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.state)
    assert scans.state.title.text() == "Reading the scan history…"
    assert actions() == []
    assert scans.note.text() == "Reading scans…"

    # No scans yet: without a file to open, nothing to click.
    scans.set_entries([])
    assert scans.state.title.text() == "No scans yet"
    assert scans.state.text.text() == "A scan shows up here as soon as it has run."
    assert actions() == []
    assert scans.note.text() == "No scans"

    scans.offer_open_file = True
    scans.lists_running_scans = True
    scans.set_entries([])
    assert scans.state.text.text() == (
        "A scan shows up here as soon as it starts. A file can be opened meanwhile."
    )
    assert actions() == ["Open file…"]
    scans.state._actions[0].click()
    assert opens == [1]

    # The history could not be read: say so and offer to try again.
    scans.show_load_failed("Reading it from BEC failed: timeout.")
    assert scans.state.title.text() == "The scan history could not be read"
    assert scans.state.text.text() == "Reading it from BEC failed: timeout."
    assert actions() == ["Try again"]
    scans.state._actions[0].click()
    assert reloads == [1]
    # Trying again reads again: loading, then the result. While the state stays, so does the
    # focus on its button; once the scans are there, it goes to the list.
    scans.reload_requested.connect(lambda: scans.show_loading())
    scans.reload_requested.connect(lambda: scans.show_load_failed("Still no answer."))
    qtbot.wait(10)  # the layout shows the new button
    scans.state._actions[0].setFocus()
    scans.state._actions[0].click()
    assert scans.state.text.text() == "Still no answer."
    assert scans.window().focusWidget() is scans.state._actions[0]
    scans.set_entries([ScanEntry.from_history(msg.model_dump()) for msg in history])
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.view)
    assert scans.window().focusWidget() is scans.view

    # Nothing fits the filter: say what hides the scans and offer to clear the filter.
    scans.ending_buttons["early"].click()
    scans.search_edit.setText("zzz")
    assert scans.state.title.text() == "No scan fits the filter"
    assert scans.state.text.text() == "All 3 are hidden by “zzz” and “Ended early”."
    scans.ending_buttons["all"].click()
    scans.search_edit.setText("grid")
    assert scans.state.text.text() == "All 3 are hidden by “grid”."
    assert actions() == ["Clear the filter"]
    scans.ending_buttons["early"].click()
    qtbot.wait(10)  # the layout shows the new button
    scans.state._actions[0].setFocus()
    scans.state._actions[0].click()
    assert scans.search_edit.text() == ""
    assert scans.ending_buttons["all"].isChecked()
    assert scans.list_stack.currentWidget() is scans.view
    # The button is gone: the focus is on the list, which has a current row.
    assert scans.window().focusWidget() is scans.view
    assert scans.view.currentIndex().isValid()

    # By mouse too: the button takes the focus on a click (also on macOS, where buttons take
    # Tab focus only; the style here is Fusion), so the focus goes on to the list.
    scans.search_edit.setFocus()
    scans.search_edit.setText("zzz")
    qtbot.wait(10)  # the layout shows the new button
    button = scans.state._actions[0]
    assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert scans.list_stack.currentWidget() is scans.view
    assert scans.window().focusWidget() is scans.view


def test_the_filter_counts_show_only_once_there_are_scans_to_count(qtbot, history):
    scans = ScanList()
    qtbot.addWidget(scans)
    scans.resize(900, 600)

    def texts():
        return [button.text() for button in scans.ending_buttons.values()]

    # While the history is read a 0 is not known, and with no scan at all it says nothing.
    assert texts() == ["All", "Finished", "Ended early"]
    assert scans.ending_buttons["all"].toolTip() == "Show every scan"
    scans.set_entries([])
    assert texts() == ["All", "Finished", "Ended early"]
    scans.set_entries([ScanEntry.from_history(msg.model_dump()) for msg in history])
    assert texts() == ["All 3", "Finished 2", "Ended early 1"]
    # A search that leaves nothing keeps its zeros: no status has a match.
    scans.search_edit.setText("zzz")
    assert texts() == ["All 0", "Finished 0", "Ended early 0"]
    assert scans.ending_buttons["all"].toolTip() == "Show every scan  ·  0 scans"


def test_a_state_page_filled_again_shows_only_its_new_buttons(qtbot):
    scans = ScanList()
    qtbot.addWidget(scans)
    scans.show()
    qtbot.waitExposed(scans)
    page = scans.state
    page.show_state("history", "No scans yet", "", (("Open file…", lambda: None),))
    old = list(page._actions)
    # Filled again before the event loop deletes the old button: it must not show meanwhile.
    page.show_state(
        "error", "The scan history could not be read", "", (("Try again", lambda: None),)
    )
    assert all(button.isHidden() for button in old)
    assert [button.text() for button in page._actions if button.isVisibleTo(page)] == ["Try again"]


def test_every_count_of_the_scan_list_reads_the_same_with_the_locale_separator(qtbot):
    previous = QLocale()
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
    try:
        scans = ScanList()
        qtbot.addWidget(scans)
        scans.resize(900, 600)
        scans.set_entries(
            [
                ScanEntry(scan_id=f"id-{n}", scan_number=n, scan_name="line_scan", status="closed")
                for n in range(1, 1001)
            ]
        )
        assert scans.note.text() == "1,000 scans"
        assert scans.ending_buttons["all"].toolTip().endswith("1,000 scans")
        scans.search_edit.setText("zzz")
        assert scans.note.text() == "0 of 1,000 scans"
        assert scans.state.text.text() == "All 1,000 are hidden by “zzz”."
    finally:
        QLocale.setDefault(previous)


def test_the_page_about_reading_the_scans_stays_long_enough_to_be_read(qtbot, history):
    scans = ScanList()
    qtbot.addWidget(scans)
    entries = [ScanEntry.from_history(msg.model_dump()) for msg in history]
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.state)
    # The poll above sees the page a little after it showed: time what is left of its stay.
    left = scans._state_kept.remainingTime()  # pylint: disable=protected-access
    shown = time.perf_counter()
    # The scans come in just after the loading page showed: it stays STATE_KEPT_MS in all.
    scans.set_entries(entries)
    assert scans.list_stack.currentWidget() is scans.state
    assert scans.state.title.text() == "Reading the scan history…"
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.view)
    # A coarse timer may end up to 5 % early; nobody reads a page 15 ms faster.
    assert (time.perf_counter() - shown) * 1000 >= left - STATE_KEPT_MS * 0.05 - 1
    # A page about a filter is the user's own doing: it comes and goes at once.
    scans.search_edit.setText("zzz")
    assert scans.state.title.text() == "No scan fits the filter"
    scans.search_edit.clear()
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.view)
    # So does the error page: once shown, a late answer still waits for its moment.
    scans.set_entries([])
    scans.show_load_failed("No answer.")
    scans.set_entries(entries)
    assert scans.state.title.text() == "The scan history could not be read"
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.view)


def test_the_viewer_waits_for_the_scan_history_and_never_shows_an_empty_list_first(
    qtbot, mocked_client, history, monkeypatch
):
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "HISTORY_POLL_MS", 50)
    monkeypatch.setattr(viewer_module, "HISTORY_WAIT_MS", 1000)
    mocked_client.history = ScanHistory(mocked_client, False)
    mocked_client.history._scan_history_loaded_event.clear()  # still being read
    mocked_client.queue.scan_storage.current_scan = None
    viewer = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    scans = viewer.scan_list

    # Right after construction the list is being read, not empty: blank at first, then it
    # says so.
    assert scans.list_stack.currentWidget() is scans.blank
    qtbot.waitUntil(lambda: scans.state.title.text() == "Reading the scan history…")
    for msg in history:
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.history._scan_history_loaded_event.set()
    qtbot.waitUntil(lambda: scans.model.rowCount() == 3)
    # The page about reading stays STATE_KEPT_MS once shown; then the list.
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.view)

    # No answer in time: the loading ends with the reason and a way to try again.
    scans.set_entries([])
    mocked_client.history._scan_history_loaded_event.clear()
    viewer._load_history()  # pylint: disable=protected-access
    qtbot.waitUntil(lambda: scans.state.title.text() == "The scan history could not be read")
    assert scans.state.text.text() == "BEC did not answer within 1 s."
    mocked_client.history._scan_history_loaded_event.clear()
    scans.state._actions[0].click()  # Try again: loading, then the result
    assert scans.list_stack.currentWidget() is scans.blank
    qtbot.waitUntil(lambda: scans.state.title.text() == "The scan history could not be read")

    # A scan that starts while the page is up brings the list back.
    viewer.on_scan_status(
        {"scan_id": "live-1", "scan_number": 99, "status": "open", "num_points": 10}, {}
    )
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.view)
    scans.model.remove("live-1")
    assert scans.state.title.text() == "The scan history could not be read"

    # A late answer wins: the list appears by itself, the failure does not stay.
    mocked_client.history._scan_history_loaded_event.set()
    qtbot.waitUntil(lambda: scans.model.rowCount() == 3, timeout=3000)
    qtbot.waitUntil(lambda: scans.list_stack.currentWidget() is scans.view)
    assert not viewer._history_timer.isActive()  # pylint: disable=protected-access


def test_the_scan_history_callback_ends_the_wait_at_once(
    qtbot, mocked_client, history, monkeypatch
):
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "HISTORY_POLL_MS", 5000)  # no tick during the test
    mocked_client.history = ScanHistory(mocked_client, False)
    mocked_client.history._scan_history_loaded_event.clear()  # still being read
    mocked_client.queue.scan_storage.current_scan = None
    viewer = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    # BEC's loader runs its callback once it has read scans: the list does not wait for a tick.
    viewer.history_manager._on_scan_history_reloaded(history)  # pylint: disable=protected-access
    qtbot.waitUntil(lambda: viewer.scan_list.model.rowCount() == 3, timeout=1000)
    assert not viewer._history_timer.isActive()  # pylint: disable=protected-access


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
    assert scans.list_stack.currentWidget() is scans.state
    assert scans.state.title.text() == "No scan fits the filter"
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


def _day_entries(now: float) -> list[ScanEntry]:
    """Three scans today, two yesterday, one the day before; scan 5 ended early."""
    day = 86400
    starts = [now - 60, now - 120, now - 180, now - day, now - day - 60, now - 2 * day]
    return [
        ScanEntry(
            scan_id=f"d{number}",
            scan_number=number,
            scan_name="line_scan",
            status="aborted" if number == 5 else "closed",
            start_time=start,
            end_time=start + 30,
            num_points=100,
            motors=("samx",),
            stored_data_info={"samx": {"samx": {"shape": [37 if number == 5 else 100]}}},
        )
        for number, start in zip(range(6, 0, -1), starts)
    ]


def test_scans_are_grouped_by_day_with_the_count_of_what_is_listed(qtbot):
    now = time.time()
    if time.localtime(now).tm_hour == 0 and time.localtime(now).tm_min < 5:
        pytest.skip("too close to midnight for a fixed day split")
    scans = ScanList()
    qtbot.addWidget(scans)
    scans.set_entries(_day_entries(now))
    heads = scans.view.heads
    assert [(row, head.label, head.count, head.first) for row, head in heads.items()] == [
        (0, "Today", 3, True),
        (3, "Yesterday", 2, False),
        (5, day_label(datetime.fromtimestamp(now - 2 * 86400).date()), 1, False),
    ]
    # The first row of a day is taller by its header; the others are rows of the queue's look.
    delegate, model = scans.delegate, scans.filter_model
    assert delegate.sizeHint(None, model.index(1, 0)).height() == ROW_HEIGHT + 1
    assert delegate.sizeHint(None, model.index(3, 0)).height() > ROW_HEIGHT + 1

    # The counts follow the filter, and a day with nothing listed has no header.
    scans.ending_buttons["early"].click()
    assert [(head.label, head.count) for head in scans.view.heads.values()] == [("Today", 1)]
    scans.ending_buttons["all"].click()
    scans.search_edit.setText("6")
    assert [(head.label, head.count) for head in scans.view.heads.values()] == [("Today", 1)]


def test_a_click_on_a_day_header_selects_nothing(qtbot):
    scans = ScanList()
    qtbot.addWidget(scans)
    scans.resize(300, 400)
    scans.show()
    scans.set_entries(_day_entries(time.time()))
    scans.select("d4")  # the second scan of today
    index = scans.filter_model.index(3, 0)  # the first of yesterday, under its header
    rect = scans.view.visualRect(index)
    qtbot.mouseClick(
        scans.view.viewport(), Qt.MouseButton.LeftButton, pos=rect.topLeft() + QPoint(40, 4)
    )
    assert scans.current_entry().scan_id == "d4"
    qtbot.mouseClick(
        scans.view.viewport(), Qt.MouseButton.LeftButton, pos=rect.bottomLeft() + QPoint(40, -6)
    )
    assert scans.current_entry().scan_id == "d3"


def test_keys_walk_the_scans_and_pin_them(qtbot):
    scans = ScanList()
    qtbot.addWidget(scans)
    scans.resize(300, 400)
    scans.show()
    scans.set_entries(_day_entries(time.time()))
    view = scans.view
    view.setFocus()
    assert scans.current_entry().scan_id == "d6"
    # Down crosses a day header to the next scan: headers are not stops.
    for _ in range(3):
        qtbot.keyClick(view, Qt.Key.Key_Down)
    assert scans.current_entry().scan_id == "d3"
    qtbot.keyClick(view, Qt.Key.Key_Up)
    assert scans.current_entry().scan_id == "d4"
    qtbot.keyClick(view, Qt.Key.Key_End)
    assert scans.current_entry().scan_id == "d1"
    qtbot.keyClick(view, Qt.Key.Key_Home)
    assert scans.current_entry().scan_id == "d6"
    qtbot.keyClick(view, Qt.Key.Key_PageDown)
    assert scans.current_entry().scan_id != "d6"
    qtbot.keyClick(view, Qt.Key.Key_P)
    assert scans.current_entry().scan_id in scans.model.pins()
    qtbot.keyClick(view, Qt.Key.Key_P)
    assert scans.model.pins() == {}

    # The marked scan stays marked, and in view, when the list is filled again.
    scans.select("d1")
    scans.set_entries(_day_entries(time.time()))
    assert scans.current_entry().scan_id == "d1"
    assert view.viewport().rect().intersects(view.visualRect(view.currentIndex()))


def test_a_scan_row_says_its_points_status_and_place_in_words(qtbot):
    entries = _day_entries(time.time())
    early = entries[1]  # scan 5: 37 of 100 points
    assert early.points_text() == "37/100"
    assert early.points_words() == "37 of 100 points"
    grid = ScanEntry.from_history(
        {
            "scan_id": "g",
            "scan_number": 21,
            "scan_name": "grid_scan",
            "num_points": 96,
            "request_inputs": {"arg_bundle": ["samx", -4, 6, 12, "samy", -3, 2, 8]},
        }
    )
    assert grid.points_text() == "12 × 8"
    assert grid.points_words() == "96 points (12 × 8)"
    # History messages may carry the bundle as a numpy array.
    bundle = np.array(["samx", -4, 6, np.int64(12), "samy", -3, 2, np.int64(8)], dtype=object)
    assert grid_shape({"arg_bundle": bundle}) == (12, 8)
    assert grid_shape({"arg_bundle": np.array([], dtype=float)}) == ()

    scans = ScanList()
    qtbot.addWidget(scans)
    scans.set_entries(entries)
    model = scans.model
    model.toggle_pin("d5")
    sentence = model.describe(early)
    assert sentence.startswith("Scan 5  line_scan, aborted, 37 of 100 points, started ")
    assert sentence.endswith("pinned for comparison") and "on the plot" not in sentence

    # Rows are filled with their curve colour only while two scans or more are on the plot.
    scans.set_plot({"d6"}, {"d6": "#2a78d6"})
    assert model.plot_color("d6") is None
    scans.set_plot({"d6", "d5"}, {"d6": "#2a78d6", "d5": "#eb6834"})
    assert model.plot_color("d5") == "#eb6834"
    assert model.describe(early).endswith("on the plot, pinned for comparison")
    # A pinned scan without a curve says why.
    scans.set_plot({"d6"}, {}, {"d5": "Not on the plot: this scan did not store bpm3a"})
    assert "Not on the plot: this scan did not store bpm3a" in model.tooltip(early)


def test_a_narrow_row_gives_way_points_first_then_the_time_then_the_name(qtbot):
    from qtpy.QtCore import QRect

    from bec_widgets.widgets.progress.stage_bar import mono_font

    scans = ScanList()
    qtbot.addWidget(scans)
    delegate = scans.delegate
    entry = ScanEntry(
        scan_id="w",
        scan_number=12345,
        scan_name="fermat_scan_with_a_long_name",
        start_time=time.time(),
        num_points=400,
    )
    metrics = QFontMetrics(mono_font(0))

    def parts(width):
        return delegate.row_parts(QRect(0, 0, width, ROW_HEIGHT), entry)

    wide = parts(600)
    assert (wide.points, bool(wide.time), wide.name) == ("400", True, entry.scan_name)
    # Narrower: the points go once the name could not show its first letters.
    widths = range(600, 60, -1)
    first_without_points = next(w for w in widths if not parts(w).points)
    without_points = parts(first_without_points)
    assert without_points.time
    assert (
        metrics.horizontalAdvance(entry.scan_name[:NAME_KEEPS_POINTS])
        > (
            parts(first_without_points).name_rect.width()
            - metrics.horizontalAdvance(without_points.number)
            - 2 * QFontMetrics(mono_font(-1)).horizontalAdvance("400")
        )
        or without_points.name != entry.scan_name
    )
    first_without_time = next(w for w in widths if not parts(w).time)
    assert first_without_time < first_without_points
    narrow = parts(first_without_time)
    assert narrow.number == "#12345 " and narrow.name.endswith("…")
    shown = narrow.name.rstrip("…")
    assert len(shown) >= NAME_KEEPS_TIME - 1


def test_the_filters_show_their_counts_only_when_all_three_fit(qtbot):
    scans = ScanList()
    qtbot.addWidget(scans)
    scans.set_entries(_day_entries(time.time()))
    scans.resize(400, 400)
    scans.show()
    texts = [button.text() for button in scans.ending_buttons.values()]
    assert texts == ["All 6", "Finished 5", "Ended early 1"]
    assert scans.hint.isVisible()
    scans.resize(150, 400)
    texts = [button.text() for button in scans.ending_buttons.values()]
    assert texts == ["All", "Finished", "Ended early"]
    assert scans.ending_buttons["early"].accessibleName() == "Ended early, 1 scan"
    assert scans.ending_buttons["all"].toolTip().endswith("6 scans")
    # The footer keeps the count; the hint goes as a whole.
    assert scans.note.text() == "6 scans" and not scans.hint.isVisible()
    scans.model.toggle_pin("d5")
    assert scans.pin_label.text() == "1 pinned"
    scans.resize(400, 400)
    assert scans.pin_label.text() == "1 pinned for comparison"


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


def test_signals_are_listed_in_the_readout_group_of_their_device(history):
    entry = ScanEntry.from_history(history[0].model_dump())
    entry.stored_data_info["mono"]["mono"] = {"shape": (20,), "dtype": "float64"}
    entry.stored_data_info["tracker"] = {"tracker": {"shape": (20,), "dtype": "float64"}}
    readouts = {
        "samx": "monitored",
        "bpm4i": "monitored",
        "bpm3a": "monitored",
        "old_diode": "monitored",
        "wave": "async",
        "camera": "async",
        "mono": "baseline",
    }

    boxes = {signal.key[0]: signal.box for signal in signals_of(entry, None, readouts)}
    groups = {signal.key[0]: signal.group for signal in signals_of(entry, None, readouts)}

    assert boxes["bpm4i"] == "point" and boxes["wave"] == "fast"
    # An image goes with its readout group and still opens in the file view.
    assert boxes["camera"] == "fast" and groups["camera"] == "array"
    # A baseline device is read once, whatever its shape says.
    assert boxes["mono"] == "single" and groups["mono"] == "single"
    # In no readout group of the scan.
    assert boxes["tracker"] == "other"

    # Not known yet: sorted by shape, an image with the signals keyed like it.
    unknown = {signal.key[0]: signal.box for signal in signals_of(entry)}
    assert unknown["camera"] == "point" and unknown["wave"] == "fast"
    assert unknown["tracker"] == "point"
    assert box_of("array", (5, 8, 8), 20, kind="async") == "fast"


def test_the_readout_groups_are_read_from_the_scan_file(history):
    assert h5_reader.readout_groups(history[0].file_path) == {
        "mono": "baseline",
        "samx": "monitored",
        "bpm4i": "monitored",
        "bpm3a": "monitored",
        "old_diode": "monitored",
        "wave": "async",
        "camera": "async",
    }


def test_reading_the_readout_groups_lets_the_data_api_open_the_file_meanwhile(history):
    file_path = history[0].file_path
    with h5_reader.open_readonly(file_path, like_data_api=True):
        # The DataAPI opens a scan file with the default locking flags.
        with h5py.File(file_path, "r") as handle:
            assert "entry" in handle
    # And the other way round, and beside another read of the viewer of the listed file.
    with h5py.File(file_path, "r"):
        assert h5_reader.readout_groups(file_path)["mono"] == "baseline"
    owner = object()
    h5_reader.set_listed_files(owner, [file_path])
    try:
        with h5_reader.open_readonly(file_path):
            assert h5_reader.readout_groups(file_path)["wave"] == "async"
    finally:
        h5_reader.set_listed_files(owner, [])


def test_a_file_without_readout_groups_says_its_signals_are_grouped_by_shape(
    qtbot, mocked_client, history
):
    for msg in history:
        with h5py.File(msg.file_path, "a") as handle:
            del handle["entry/collection/readout_groups"]
        settle(msg.file_path)
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in history:
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    viewer = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    tree = viewer.signal_list.tree

    qtbot.waitUntil(
        lambda: tree.topLevelItemCount() > 1
        and "grouped by the shape" in tree.topLevelItem(1).toolTip(0)
    )
    assert tree.topLevelItem(1).text(0).startswith("Monitored")
    # Picked again, the file is not read again and the boxes still say so.
    viewer.show_scan(10)
    viewer.show_scan(12)
    assert "does not name its readout groups" in tree.topLevelItem(1).toolTip(0)


def test_a_running_scan_lists_its_signals_in_the_readout_groups_of_its_status(
    qtbot, mocked_client, viewer
):
    viewer.on_scan_status(
        {
            "scan_id": "live-1",
            "scan_number": 99,
            "status": "open",
            "num_points": 10,
            "readout_priority": {"monitored": ["bpm4i"], "baseline": ["mono"], "async": []},
        },
        {},
    )
    entry = viewer.scan_list.model.entry("live-1")
    assert entry.readout_groups == {"bpm4i": "monitored", "mono": "baseline"}

    # The lists may arrive as numpy arrays, also empty ones.
    viewer.on_scan_status(
        {
            "scan_id": "live-2",
            "scan_number": 100,
            "status": "open",
            "num_points": 10,
            "scan_report_devices": np.array(["samx", "samy"]),
            "readout_priority": {
                "monitored": np.array(["bpm4i"]),
                "baseline": np.array([]),
                "async": np.array([]),
            },
        },
        {},
    )
    entry = viewer.scan_list.model.entry("live-2")
    assert entry.readout_groups == {"bpm4i": "monitored"}
    assert entry.motors == ("samx", "samy")


def test_the_next_scan_with_the_same_signals_keeps_the_rows_and_updates_their_shapes(
    qtbot, history
):
    signals = SignalList()
    qtbot.addWidget(signals)
    first = ScanEntry.from_history(history[0].model_dump())
    second = ScanEntry.from_history(history[0].model_dump())
    second.scan_id = "other"
    second.num_points = 77
    for device in second.stored_data_info.values():
        for name in device:
            shape = tuple(device[name]["shape"])
            if shape and shape[0] == first.num_points:  # one value per point
                device[name] = {**device[name], "shape": (77, *shape[1:])}

    signals.set_scan(first)
    rows = dict(signals._rows)  # pylint: disable=protected-access
    signals.set_scan(second)
    # The same rows, with the shapes of the second scan.
    assert signals._rows == rows  # pylint: disable=protected-access
    assert rows[("bpm4i", "bpm4i")].text(1) == "77"
    assert rows[("bpm4i", "bpm4i")].data(0, SIGNAL_ROLE).shape == (77,)

    # Other signals: the list is built anew.
    del second.stored_data_info["bpm3a"]
    signals.set_scan(second)
    assert ("bpm3a", "bpm3a") not in signals._rows  # pylint: disable=protected-access
    assert all(
        row is not rows[key]
        for key, row in signals._rows.items()  # pylint: disable=protected-access
    )


def test_a_finished_scan_is_described_once(qtbot, viewer, monkeypatch):
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer as viewer_module

    calls = []
    monkeypatch.setattr(
        viewer.client.data_api, "describe", lambda *args, **kwargs: calls.append(1) or {}
    )
    viewer.show_scan(11)
    viewer.show_scan(12)
    viewer.show_scan(11)
    assert len(calls) <= 2
    assert set(viewer._described) <= {
        "scan-0",
        "scan-1",
        "scan-2",
    }  # pylint: disable=protected-access

    # A running scan is never kept: its signals are still being written.
    viewer.on_scan_status(
        {
            "scan_id": "live-1",
            "scan_number": 99,
            "status": "open",
            "num_points": 10,
            "readout_priority": {"monitored": ["bpm4i"], "baseline": [], "async": []},
        },
        {},
    )
    viewer.show_scan("live-1")
    assert "live-1" not in viewer._described  # pylint: disable=protected-access

    # The store has a cap, and is emptied when the scan history is read again.
    monkeypatch.setattr(viewer_module, "DESCRIBED_KEPT", 2)
    viewer._described.clear()  # pylint: disable=protected-access
    for scan in (10, 11, 12):
        viewer.show_scan(scan)
    # The oldest answer (scan 10) went.
    assert list(viewer._described) == ["scan-1", "scan-2"]  # pylint: disable=protected-access
    viewer._load_history()  # pylint: disable=protected-access
    assert viewer._described == {}  # pylint: disable=protected-access


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
    assert box_text(signals) == "X: samx | Y: bpm3a, bpm4i"
    assert signals.note.isHidden()

    # A fast signal cannot share the plot with signals per scan point.
    signals.toggle_y(("adc", "adc"))
    assert signals.y_signals() == [("adc", "adc")]
    assert signals.x_signal() is None
    signals.toggle_x(("adc", "adc"))
    assert signals.x_signal() is None

    signals.toggle_y(("camera", "camera"))
    assert signals.y_signals() == [("adc", "adc")]

    signals.filter_edit.setText("zzz")
    assert signals.filter_empty_text.text() == "No signal of this scan fits “zzz”."
    assert len(changes) >= 4


def test_a_box_the_user_opened_or_closed_stays_so_for_every_scan(qtbot, history):
    signals = SignalList()
    qtbot.addWidget(signals)
    first = ScanEntry.from_history(history[0].model_dump())
    for number in range(20):  # a long Baseline box starts closed
        first.stored_data_info[f"extra{number}"] = {
            f"extra{number}": {"shape": (1,), "dtype": "float64"}
        }
    signals.set_scan(first)

    def box(name):
        tree = signals.tree
        return next(
            tree.topLevelItem(row)
            for row in range(tree.topLevelItemCount())
            if tree.topLevelItem(row).data(0, BOX_ROLE) == name
        )

    long_box = "single"
    assert not box(long_box).isExpanded()
    box(long_box).setExpanded(True)  # the user opens it
    point_box = next(
        signals.tree.topLevelItem(row).data(0, BOX_ROLE)
        for row in range(signals.tree.topLevelItemCount())
        if signals.tree.topLevelItem(row).isExpanded()
        and signals.tree.topLevelItem(row).data(0, BOX_ROLE) != long_box
    )
    box(point_box).setExpanded(False)  # and closes another one

    # A scan of another kind: the list is built anew, the boxes keep the user's choice.
    second = ScanEntry.from_history(history[0].model_dump())
    second.stored_data_info = {**first.stored_data_info}
    del second.stored_data_info["bpm3a"]
    signals.set_scan(second)
    assert box(long_box).isExpanded()
    assert not box(point_box).isExpanded()
    # A search opens boxes for itself, which is not the user's choice.
    signals.filter_edit.setText("bpm")
    signals.filter_edit.clear()
    signals.set_scan(first)
    assert not box(point_box).isExpanded()


def test_scan_motors_come_from_the_bundle_or_the_motor_inputs():
    line = {"arg_bundle": ["samx", -1, 1], "kwargs": {"steps": 10}}
    grid = {"arg_bundle": ["samx", -5, 5, 21, "samy", -5, 5, 21], "inputs": {}}
    fermat = {
        "arg_bundle": np.array([]),
        "inputs": {"motor2": "samy", "motor1": "samx", "step": 0.5, "relative": False},
    }
    assert scan_motors(line) == ("samx",)
    assert scan_motors(grid) == ("samx", "samy")
    assert scan_motors(fermat) == ("samx", "samy")
    assert scan_motors({}) == ()
    entry = ScanEntry.from_history(
        {"scan_id": "f", "scan_number": 22, "scan_name": "fermat_scan", "request_inputs": fermat}
    )
    assert entry.motors == ("samx", "samy")


def test_the_default_signal_is_each_scans_own_until_the_user_picks_one(qtbot, history):
    signals = SignalList()
    qtbot.addWidget(signals)
    first = ScanEntry.from_history(history[0].model_dump())
    second = ScanEntry.from_history(history[1].model_dump())
    del second.stored_data_info["bpm3a"]

    signals.set_scan(first)
    assert signals.y_signals() == [("bpm3a", "bpm3a")]
    assert signals.y_is_default()
    assert box_text(signals).endswith(" | Y: bpm3a auto")

    # The next scan gets its own default, the first detector it has.
    signals.set_scan(second)
    assert signals.y_signals() == [("bpm4i", "bpm4i")]
    assert signals.y_is_default()

    # A choice of the user stays when coming back to a scan that has it.
    signals.toggle_y(("old_diode", "old_diode"))
    signals.toggle_y(("bpm4i", "bpm4i"))
    assert signals.y_signals() == [("old_diode", "old_diode")]
    assert not signals.y_is_default()
    signals.set_scan(first)
    assert signals.y_signals() == [("old_diode", "old_diode")]
    assert box_text(signals).endswith(" | Y: old_diode")


def test_the_signal_list_reads_the_theme_once_per_rebuild(qtbot, history, monkeypatch):
    from bec_widgets.widgets.services.hdf5_viewer import signal_list as signal_list_module

    reads = []
    real = signal_list_module.muted_color
    monkeypatch.setattr(signal_list_module, "muted_color", lambda: reads.append(1) or real())
    signals = SignalList()
    qtbot.addWidget(signals)
    entry = ScanEntry.from_history(history[0].model_dump())
    for number in range(200):
        entry.stored_data_info[f"extra{number}"] = {
            f"extra{number}": {"shape": (20,), "dtype": "float64"}
        }
    reads.clear()
    signals.set_scan(entry)
    # Once for the rows, once for the scan devices: not once per row.
    assert len(reads) <= 2


def box_list(qtbot, history, extra: int = 0) -> SignalList:
    """A shown signal list on the first scan, with ``extra`` monitored signals of long names."""
    signals = SignalList()
    qtbot.addWidget(signals)
    entry = ScanEntry.from_history(history[0].model_dump())
    for number in range(extra):
        name = f"detector_channel_{number:02d}_counts"
        entry.stored_data_info[name] = {name: {"shape": (20,), "dtype": "float64"}}
    signals.set_scan(entry)
    signals.resize(440, 700)
    signals.show()
    qtbot.waitExposed(signals)
    return signals


#: Two chips, as in a Y field with two curves.
BOX_CHIPS = ("bpm3a", "bpm4s")


def test_the_box_keeps_its_chips_and_rows_when_a_scan_changes_nothing_in_them(qtbot):
    from bec_widgets.widgets.services.hdf5_viewer.role_fields import ChipInfo, Role, RoleBox

    box = RoleBox()
    qtbot.addWidget(box)

    def role(letter, *labels):
        chips = tuple(ChipInfo(key=(label, label), label=label) for label in labels)
        return Role(
            letter,
            axis=letter != "Y",
            multi=letter == "Y",
            caption="",
            chips=chips,
            name=letter,
            hint="",
        )

    box.set_roles([role("X", "samx"), role("Y", "bpm4i"), role("Z", "samy")], False)
    fields = dict(box.fields)
    chip = fields["Y"].flow.chips[0]
    # The next scan with the same roles: nothing in the box is made anew.
    box.set_roles([role("X", "samx"), role("Y", "bpm4i"), role("Z", "samy")], False)
    assert box.fields["Y"].flow.chips[0] is chip
    # A scan of one motor, then a map again: the rows are kept, not made anew.
    box.set_roles([role("X", "samx"), role("Y", "bpm4i")], False)
    assert list(box.fields) == ["X", "Y"]
    assert box.fields["X"] is fields["X"] and box.fields["Y"] is fields["Y"]
    assert not fields["Z"].isVisibleTo(box)
    box.set_roles([role("X", "samx"), role("Y", "bpm4i"), role("Z", "samy")], False)
    assert box.fields == fields
    assert fields["Z"].isVisibleTo(box)


def test_a_field_shows_its_placeholder_whole_or_not_at_all(qtbot):
    from bec_widgets.widgets.services.hdf5_viewer.role_fields import (
        EDIT_MIN_WIDTH,
        ChipInfo,
        Role,
        RoleBox,
    )

    box = RoleBox()
    qtbot.addWidget(box)
    chips = tuple(ChipInfo(key=(name, name), label=name, removable=True) for name in BOX_CHIPS)
    roles = [
        Role(
            "Y",
            axis=False,
            multi=True,
            caption="",
            chips=chips,
            name="The curves on the plot",
            hint="Type to add a signal",
            placeholder="Add a signal…",
        )
    ]
    box.set_roles(roles, False)
    box.show()
    qtbot.waitExposed(box)
    field = box.fields["Y"]
    edit, flow = field.edit, field.flow
    need = flow.placeholder_need()
    assert need > EDIT_MIN_WIDTH
    cut, whole = None, None
    for width in range(240, 900, 4):
        box.resize(width, 200)
        qtbot.waitUntil(lambda w=width: box.width() == w)
        QApplication.processEvents()
        if flow.lines != 1:
            continue
        if cut is None and EDIT_MIN_WIDTH <= edit.width() < need:
            cut = width
            chips_before = [chip.geometry() for chip in flow.chips]
            # No room for all of it: no placeholder, and the text stays beside the chips.
            assert edit.placeholderText() == ""
            assert edit.y() == flow.chips[0].y()
            assert [chip.geometry() for chip in flow.chips] == chips_before
            assert edit.toolTip() == "Type to add a signal"
            assert edit.accessibleName() == "The curves on the plot. Type to add a signal"
        if edit.width() >= need:
            whole = width
            assert edit.placeholderText() == "Add a signal…"
            break
    assert cut is not None and whole is not None
    # Narrower again: the placeholder goes and the chips stay where they are.
    box.resize(cut, 200)
    qtbot.waitUntil(lambda: edit.placeholderText() == "")
    assert [chip.geometry() for chip in flow.chips] == chips_before


def test_chips_add_line_styles_while_a_second_scan_is_pinned_and_back(qtbot, history):
    signals = box_list(qtbot, history)
    signals.toggle_y(BPM4I)
    colors = {BPM3A: "#d62728", BPM4I: "#1f77b4"}
    y_field = signals.box.fields["Y"]

    def swatches():
        return [(chip.info.swatch.color, chip.info.swatch.style) for chip in y_field.flow.chips]

    signals.set_colors(colors, "#000000")
    assert swatches() == [("#d62728", "solid"), ("#1f77b4", "solid")]
    # A second scan pinned: the colour of each signal's curve for the selected scan, and its
    # line style as the second cue. The rows stay filled in that colour.
    shades = {BPM3A: "#1f77b4", BPM4I: "#5a9bd5"}
    signals.set_colors(shades, "#000000", {BPM3A: "solid", BPM4I: "dash"})
    assert swatches() == [("#1f77b4", "solid"), ("#5a9bd5", "dash")]
    assert [c.name() for c in signals.row_fill(BPM4I)] == ["#5a9bd5"]
    signals.set_colors(colors, "#000000")
    assert swatches() == [("#d62728", "solid"), ("#1f77b4", "solid")]


def test_signals_on_the_plot_fill_their_rows_in_the_colour_of_their_curve(qtbot, history):
    signals = box_list(qtbot, history)
    signals.toggle_y(BPM4I)
    signals.set_colors({BPM3A: "#d62728", BPM4I: "#1f77b4"}, "#000000")
    assert signals.y_signals() == [BPM3A, BPM4I]
    # As the scans on the plot in the scan list: the row in the colour of the curve, its text
    # in black or white.
    assert [c.name() for c in signals.row_fill(BPM4I)] == ["#1f77b4"]
    assert [c.name() for c in signals.row_fill(BPM3A)] == ["#d62728"]
    assert signals.ink_of(BPM4I).name() in ("#000000", "#ffffff")
    # The x axis keeps its filled X and gets no fill; a signal off the plot neither.
    x_key = signals.x_signal() or next(k for k in signals._signals if k[0] == "samx")
    assert signals.row_fill(x_key) == []
    assert signals.ink_of(x_key) == signals.row_colors()[1]
    signals.toggle_y(BPM4I)
    assert signals.row_fill(BPM4I) == []
    # The theme paints no selection or hover of its own: the list paints its rows.
    assert "background: transparent" in signals.tree.styleSheet()


def has_bad_outline(chip) -> bool:
    """Whether the swatch of a chip is drawn as an outline in the colour of a problem."""
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.progress.stage_bar import Tone
    from bec_widgets.widgets.services.hdf5_viewer.role_fields import CHIP_PADDING, SWATCH_WIDTH
    from bec_widgets.widgets.services.hdf5_viewer.style import tone_color

    image = chip.grab().toImage()
    ratio = image.devicePixelRatio()
    bad = tone_color(Tone.BAD)
    for x in range(int(CHIP_PADDING * ratio), int((CHIP_PADDING + SWATCH_WIDTH) * ratio)):
        for y in range(image.height()):
            pixel = image.pixelColor(x, y)
            if (
                max(
                    abs(pixel.red() - bad.red()),
                    abs(pixel.green() - bad.green()),
                    abs(pixel.blue() - bad.blue()),
                )
                < 40
                and pixel.alpha() > 200
            ):
                return True
    return False


def test_a_curve_that_is_not_drawn_has_an_outlined_chip_until_try_again_brings_it(qtbot, history):
    signals = box_list(qtbot, history)
    signal = signals._signals[BPM3A]
    signals.toggle_y(BPM4I)
    field = signals.box.fields["Y"]
    assert not has_bad_outline(field.chip_of(BPM3A))
    signals.set_unread({BPM3A: "it could not be read"})
    assert signals.chip_tip("Y", signal).startswith("Not drawn: it could not be read.")
    chip = field.chip_of(BPM3A)
    # The box says what is on the plot: the swatch is an outline, as on the row's button.
    assert has_bad_outline(chip)
    assert chip.toolTip() == "Not drawn: it could not be read."
    assert chip.accessibleName() == "bpm3a, not drawn. it could not be read"
    assert chip.remove_button is not None
    assert not has_bad_outline(field.chip_of(BPM4I))
    # Try again brings it: the button and the swatch are filled again.
    signals.set_unread({})
    assert signals.chip_tip("Y", signal) == "Show on the plot (Y)"
    chip = field.chip_of(BPM3A)
    assert not has_bad_outline(chip)
    assert chip.accessibleName() == "bpm3a"
    assert chip.toolTip() == ""


@pytest.mark.parametrize("first, second", [(100, 10000), (10000, 100)])
def test_the_length_column_is_measured_again_when_the_lengths_change(qtbot, history, first, second):
    signals = box_list(qtbot, history)

    def scan(points):
        entry = ScanEntry.from_history(history[0].model_dump())
        for entries in entry.stored_data_info.values():
            for sub, info in entries.items():
                shape = tuple(info.get("shape", ()))
                if shape not in ((), (0,), (1,)):
                    entries[sub] = {**info, "shape": (points, *shape[1:])}
        return entry

    metrics = QFontMetrics(signals.tree.font())

    def widest():
        return max(metrics.horizontalAdvance(item.text(1)) for item in signals._rows.values())

    signals.set_scan(scan(first))
    before = widest()
    assert signals._length == signals.length_width() > before
    signals.set_scan(scan(second))
    assert widest() != before
    assert signals._length == signals.length_width() > widest()


def test_the_filter_holds_across_a_change_of_scan_and_clears_cleanly(qtbot, history):
    from bec_widgets.widgets.services.hdf5_viewer.signal_list import MATCH_ROLE as NAME_MATCH

    signals = box_list(qtbot, history)
    signals.filter_edit.setText("bpm4")
    signals.set_scan(ScanEntry.from_history(history[0].model_dump()))
    rows = signals._rows
    assert rows[BPM3A].isHidden() and not rows[BPM4I].isHidden()
    assert rows[BPM4I].data(0, NAME_MATCH) == (0, 1, 2, 3)
    signals.filter_edit.clear()
    signals.set_scan(ScanEntry.from_history(history[0].model_dump()))
    assert all(not item.isHidden() and not item.data(0, NAME_MATCH) for item in rows.values())


def test_the_box_names_its_fields_and_their_chips_for_assistive_tools(qtbot, history):
    signals = box_list(qtbot, history)
    signals.toggle_y(BPM4I)
    x_field, y_field = signals.box.fields["X"], signals.box.fields["Y"]
    assert y_field.edit.accessibleName() == (
        "The curves on the plot, 2 curves. Type to add a signal"
    )
    # Alone, the list does not know the positioner of the scan: the plot chooses.
    assert x_field.edit.accessibleName() == (
        "The x axis: chosen by the plot. Type to choose another signal"
    )
    assert y_field.edit.placeholderText() == "Add a signal…"
    assert y_field.arrow.toolTip() == "Show every signal that can be a curve"
    assert x_field.arrow.toolTip() == "Show every signal that can be the x axis"
    remove = y_field.chip_of(BPM4I).findChild(QWidget, "chip_remove")
    assert remove.accessibleName() == "Take bpm4i off the plot"
    # The arrow and the x of a chip are reached with the pointer, not with Tab.
    assert remove.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert x_field.arrow.focusPolicy() == Qt.FocusPolicy.NoFocus
    # An axis has no x: it is changed, not taken off.
    assert x_field.flow.chips[0].findChild(QWidget, "chip_remove") is None


def test_the_x_of_a_chip_takes_its_curve_off_the_plot(qtbot, history):
    signals = box_list(qtbot, history)
    signals.toggle_y(BPM4I)
    assert box_text(signals) == "X: chosen by the plot auto | Y: bpm3a, bpm4i"
    remove = signals.box.fields["Y"].chip_of(BPM3A).findChild(QWidget, "chip_remove")
    qtbot.mouseClick(remove, Qt.MouseButton.LeftButton)
    assert signals.y_signals() == [BPM4I]
    assert box_text(signals) == "X: chosen by the plot auto | Y: bpm4i"


def test_reset_axes_sits_in_the_box_and_shows_after_a_hand_change(qtbot, history):
    signals = box_list(qtbot, history)
    assert signals.reset_axes_button.parent() is signals.box
    assert not signals.reset_axes_button.isVisibleTo(signals)
    signals.toggle_x(BPM4I)
    assert signals.reset_axes_button.isVisibleTo(signals)
    qtbot.mouseClick(signals.reset_axes_button, Qt.MouseButton.LeftButton)
    assert signals.x_signal() is None
    assert box_text(signals).startswith("X: chosen by the plot auto | ")
    assert not signals.reset_axes_button.isVisibleTo(signals)


def test_reset_brings_back_the_default_curve_and_the_scan_axes(qtbot, history):
    signals = box_list(qtbot, history)
    assert signals.is_default() and signals.y_signals() == [BPM3A]
    # Another curve alone is a change Reset undoes, like another axis.
    signals.toggle_y(BPM4I)
    assert not signals.is_default() and signals.reset_axes_button.isVisibleTo(signals)
    signals.toggle_x(BPM4I)
    signals.reset_axes_button.click()
    assert signals.y_signals() == [BPM3A] and signals.x_signal() is None
    assert signals.is_default() and not signals.reset_axes_button.isVisibleTo(signals)
    assert signals.reset_axes_button.text() == "Reset"


def test_curves_set_from_outside_keep_one_group(qtbot, history):
    signals = box_list(qtbot, history)
    signals.set_curves([BPM3A, BPM4I])
    assert signals.y_signals() == [BPM3A, BPM4I] and signals.lines_signals() == [BPM3A, BPM4I]
    assert not signals.y_is_default()
    async_key = next(s.key for s in signals.signals() if s.group == "fast")
    # Curves of two groups cannot share Lines: the one added last stays.
    signals.set_curves([BPM3A, BPM4I, async_key])
    assert signals.y_signals() == [async_key]


def test_tab_goes_through_the_fields_reset_the_filter_and_the_list(qtbot, history):
    signals = box_list(qtbot, history)
    signals.toggle_x(BPM4I)  # Reset axes shows
    order = [
        signals.box.fields["X"].edit,
        signals.box.fields["Y"].edit,
        signals.reset_axes_button,
        signals.filter_edit,
        signals.tree,
    ]
    signals.activateWindow()
    order[0].setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.waitUntil(order[0].hasFocus)
    reached = [QApplication.focusWidget()]
    for _ in order[1:]:
        qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
        reached.append(QApplication.focusWidget())
    assert reached == order


def test_more_curves_than_three_lines_scroll_in_the_box_and_are_counted(qtbot, history):
    signals = box_list(qtbot, history, extra=6)
    signals.resize(300, 700)
    for number in range(6):
        name = f"detector_channel_{number:02d}_counts"
        signals.toggle_y((name, name))
    field = signals.box.fields["Y"]
    qtbot.waitUntil(lambda: field.lines() > 3)
    badge = signals.box.count_badge
    assert badge.isVisibleTo(signals)
    assert badge.toolTip() == "7 curves on the plot"
    assert field.edit.accessibleName().startswith("The curves on the plot, 7 curves.")
    signals.toggle_y(("detector_channel_05_counts", "detector_channel_05_counts"))
    assert not badge.isVisibleTo(signals) or badge.toolTip() == "6 curves on the plot"


def test_long_names_are_cut_in_the_middle_and_told_in_full(qtbot, history):
    signals = box_list(qtbot, history, extra=1)
    signals.resize(260, 700)
    name = "detector_channel_00_counts"
    signals.toggle_y((name, name))
    chip = signals.box.fields["Y"].chip_of((name, name))
    qtbot.waitUntil(lambda: chip.shown_name() != name)
    shown = chip.shown_name()
    assert shown.startswith("det") and shown.endswith("counts"[-2:]) and "…" in shown
    assert name in chip.toolTip()


def focus_field(qtbot, signals, letter: str):
    """Give a field of the box the focus, as a click would, and return its text field."""
    edit = signals.box.fields[letter].edit
    signals.activateWindow()
    edit.setFocus(Qt.FocusReason.MouseFocusReason)
    qtbot.waitUntil(edit.hasFocus)
    return edit


def listed(signals) -> list[tuple[str, str, str]]:
    """The lines of the list under the fields: kind, text and the text at the right."""
    return [(e.kind, e.text, e.right) for e in signals.typing.list.listing.entries]


def test_typing_in_a_field_lists_what_fits_and_enter_adds_the_best(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "Y")
    typing = signals.typing
    qtbot.keyClicks(edit, "bpm")
    assert typing.is_open("Y") and not typing.by_user
    # The curve on the plot keeps its place with a tick; the mark is on the best fit not on it.
    assert listed(signals) == [
        ("entry", "bpm3a", "on the plot"),
        ("entry", "bpm4i", "Monitored · 20"),
    ]
    assert signals.typing.list.listing.entries[0].positions == (0, 1, 2)
    assert typing.list.marked() == 1
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert signals.y_signals() == [BPM3A, BPM4I]
    # The text goes, the focus stays, and a list that came with the text goes with it.
    assert edit.text() == "" and edit.hasFocus() and not typing.is_open()


def test_signals_that_cannot_take_a_role_are_listed_last_with_a_reason(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "X")
    qtbot.keyClicks(edit, "m")
    entries = signals.typing.list.listing.entries
    states = [(e.text, e.state, e.right) for e in entries]
    off = [(text, right) for text, state, right in states if state == "off"]
    assert ("mono", "Baseline · one value, see File") in off
    assert ("camera", "Monitored · an image, see File") in off
    # Muted and last: after every signal that can be the x axis.
    first_off = next(i for i, (_, state, _) in enumerate(states) if state == "off")
    assert all(state == "off" for _, state, _ in states[first_off:])
    assert not signals.typing.list.model.item(len(entries) - 1).isEnabled()
    # A role of one signal says so; nothing that can take it: Enter does nothing.
    edit.clear()
    qtbot.keyClicks(edit, "mono")
    assert signals.typing.list.marked() is None
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert signals.x_signal() is None and edit.text() == "mono"


def test_a_role_of_one_signal_takes_the_signal(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "X")
    qtbot.keyClicks(edit, "bpm4")
    assert listed(signals) == [("entry", "bpm4i", "Monitored · 20")]
    assert signals.typing.list.marked() == 0
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert signals.x_signal() == BPM4I
    # The holder of the role has a tick and says so.
    qtbot.keyClicks(edit, "bpm4")
    assert listed(signals) == [("entry", "bpm4i", "the x axis now")]


def test_the_x_field_offers_index_and_timestamp_above_the_signals(qtbot, history):
    signals = box_list(qtbot, history)
    entries = signals.role_listing("X", "").entries
    assert [(e.kind, e.text, e.right) for e in entries[:3]] == [
        ("head", "Plot axis", ""),
        ("entry", "Index", "point number"),
        ("entry", "Timestamp", "time of each point"),
    ]
    assert entries[0].count == 2 and entries[3].kind == "head"
    # Typing finds them.
    for typed, name in (("ind", "Index"), ("time", "Timestamp"), ("stamp", "Timestamp")):
        assert signals.role_listing("X", typed).entries[0].text == name, typed
    # Taken, it is the chip of X, chosen by hand: Reset axes brings the scan's device back.
    signals.take_role("X", TIMESTAMP_X)
    assert signals.x_signal() == TIMESTAMP_X
    chip = signals.box.fields["X"].flow.chips[0].info
    assert chip.label == "Timestamp" and not chip.auto
    assert not signals.axes_are_auto() and signals.reset_axes_button.isVisibleTo(signals)
    assert signals.axis_of(("samx", "samx")) == ""
    assert ("entry", "Timestamp", "the x axis now") in [
        (e.kind, e.text, e.right) for e in signals.role_listing("X", "").entries
    ]
    signals.take_role("X", INDEX_X)
    assert signals.x_signal() == INDEX_X
    signals.reset_axes_button.click()
    assert signals.x_signal() is None and signals.axes_are_auto()


def test_index_and_timestamp_set_the_x_mode_of_the_plot(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    signals = viewer.signal_list
    for key, mode in ((INDEX_X, "index"), (TIMESTAMP_X, "timestamp")):
        signals.take_role("X", key)
        qtbot.waitUntil(lambda mode=mode: viewer.waveform.x_mode == mode)
    signals.reset_axes_button.click()
    qtbot.waitUntil(lambda: viewer.waveform.x_mode == "samx")


def active_viewer(qtbot, viewer):
    """The viewer shown in the active window, as the user has it; its plot drawn."""
    viewer.show()
    qtbot.waitExposed(viewer)
    viewer.activateWindow()
    qtbot.waitActive(viewer)
    qtbot.waitUntil(lambda: bool(viewer._curves) and not viewer._lines_loading())
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform)


def click_list_entry(qtbot, typing, text: str) -> None:
    """Click a line of the open list under a field with the mouse, on the list's viewport."""
    row = next(i for i, e in enumerate(typing.list.listing.entries) if e.text == text)
    view = typing.list.view
    centre = view.visualRect(view.model().index(row, 0)).center()
    qtbot.mouseMove(view.viewport(), centre)
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=centre)


def assert_x_holds(qtbot, viewer, label: str, mode: str) -> None:
    """
    The x chip of both tabs (the File tab's once it was built) names the pick with no "auto",
    the plot is drawn against it, and so it stays once every sync that follows has run.
    """
    boxes = [viewer.signal_list.box, viewer.file_box.box]

    def holds() -> bool:
        return (
            all(
                [(c.info.label, c.info.auto) for c in box.fields["X"].flow.chips]
                == [(label, False)]
                for box in boxes
                if "X" in box.fields
            )
            and viewer.waveform.x_mode == mode
        )

    qtbot.waitUntil(holds)
    qtbot.waitUntil(lambda: not viewer._lines_loading())
    qtbot.wait(300)  # the syncs and refreshes that follow a pick
    assert holds()
    # The test history stamps its points 0, 1, 2, …: both modes draw them at 0…19, not at samx.
    assert np.array_equal(curve_x(viewer), np.arange(20))


def curve_x(viewer) -> np.ndarray:
    """The x data of the first curve on the plot."""
    curve, _live = next(iter(viewer._curves.values()))
    return np.asarray(curve.xData, dtype=float)


@pytest.mark.parametrize("tab", ["signals", "file"])
def test_a_click_in_the_x_list_takes_index_and_timestamp(qtbot, dock_focus, viewer, tab):
    """
    In bec-app the dock of the pane takes the focus on a click: the press on a line of the
    list must not close the list before the click takes its line.
    """
    active_viewer(qtbot, viewer)
    if tab == "file":
        viewer.file_dock.setAsCurrentTab()
        box, typing = viewer.file_box.box, viewer.file_box.typing
    else:
        box, typing = viewer.signal_list.box, viewer.signal_list.typing
    field = box.fields["X"]
    qtbot.waitUntil(field.isVisible)
    for label, mode in (("Index", "index"), ("Timestamp", "timestamp")):
        qtbot.mouseClick(field.arrow, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: typing.is_open("X") and field.edit.hasFocus())
        click_list_entry(qtbot, typing, label)
        assert_x_holds(qtbot, viewer, label, mode)
        assert not typing.is_open()
    # Typed in part, then clicked: the same.
    qtbot.keyClicks(field.edit, "ind")
    qtbot.waitUntil(lambda: typing.is_open("X"))
    click_list_entry(qtbot, typing, "Index")
    assert_x_holds(qtbot, viewer, "Index", "index")
    # The pick stays across a switch of tabs; Reset brings the scan's axis back.
    for dock in (viewer.signals_dock, viewer.file_dock, viewer.signals_dock):
        dock.setAsCurrentTab()
        assert_x_holds(qtbot, viewer, "Index", "index")
    assert "X" in viewer.file_box.box.fields
    viewer.signal_list.reset_axes_button.click()
    qtbot.waitUntil(lambda: viewer.waveform.x_mode == "samx")
    chips = viewer.signal_list.box.fields["X"].flow.chips
    assert [(c.info.label, c.info.auto) for c in chips] == [("samx", True)]
    qtbot.waitUntil(lambda: np.allclose(curve_x(viewer), np.linspace(-1, 1, 20)))


def test_a_typed_x_mode_and_enter_take_it(qtbot, dock_focus, viewer):
    active_viewer(qtbot, viewer)
    signals = viewer.signal_list
    edit = focus_field(qtbot, signals, "X")
    for typed, label, mode in (
        ("Timestamp", "Timestamp", "timestamp"),
        ("Index", "Index", "index"),
    ):
        qtbot.keyClicks(edit, typed)
        qtbot.waitUntil(lambda: signals.typing.is_open("X"))
        qtbot.keyClick(edit, Qt.Key.Key_Return)
        assert_x_holds(qtbot, viewer, label, mode)
        assert edit.hasFocus() and edit.text() == ""


def test_clicks_in_the_y_list_add_curves_and_keep_it_open(qtbot, dock_focus, viewer):
    """Each click on a line of the open Y list adds its curve; the list stays for the next."""
    active_viewer(qtbot, viewer)
    signals, typing = viewer.signal_list, viewer.signal_list.typing
    field = signals.box.fields["Y"]
    assert signals.y_signals() == [BPM3A]
    qtbot.mouseClick(field.arrow, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: typing.is_open("Y") and field.edit.hasFocus())
    added = []
    for name in ("bpm4i", "old_diode"):
        click_list_entry(qtbot, typing, name)
        added.append(name)
        names = ["bpm3a", *added]
        qtbot.waitUntil(
            lambda names=names: sorted(device for _scan, device, _signal in viewer._curves)
            == sorted(names)
            and not viewer._lines_loading()
        )
        qtbot.wait(300)  # the syncs and refreshes that follow a take
        assert signals.y_signals() == [(n, n) for n in names]
        assert [c.info.label for c in field.flow.chips] == names
        assert typing.is_open("Y") and field.edit.hasFocus()
        entry = next(e for e in typing.list.listing.entries if e.text == name)
        assert entry.state == "on"


def test_a_map_takes_no_index_or_timestamp_as_its_axis(qtbot, map_viewer):
    viewer = map_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    assert "Plot axis" not in [e.text for e in signals.role_listing("X", "").entries]
    # Typed, they are listed last, muted, with the reason.
    entry = signals.role_listing("X", "time").entries[-1]
    assert (entry.text, entry.state, entry.right) == (
        "Timestamp",
        "off",
        "Plot axis · only in Lines",
    )
    signals.take_role("X", TIMESTAMP_X)
    assert signals.x_signal() is None
    # In Lines they can be the x axis of the same scan; the map keeps its axes.
    viewer.view_switch.buttons["lines"].click()
    signals.take_role("X", INDEX_X)
    assert signals.x_signal() == INDEX_X
    qtbot.waitUntil(lambda: viewer.waveform.x_mode == "index")
    viewer.view_switch.buttons["scatter"].click()
    assert signals.plane_axes() == tuple(signals.scan_axes()[:2])
    assert signals.axes_are_auto()


def test_the_groups_of_signals_have_headers_set_apart_from_the_rows(qtbot, history):
    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.utils.theme_utils import theme_colors
    from bec_widgets.widgets.services.hdf5_viewer.style import (
        HEAD_BAND_HEIGHT,
        HEAD_GAP,
        HEAD_MIN_CONTRAST,
        contrast,
        head_colors,
    )

    signals = box_list(qtbot, history)
    tree = signals.tree
    heads = [tree.topLevelItem(row) for row in range(tree.topLevelItemCount())]
    assert len(heads) >= 2
    # The names stay as they were, for the tests and the screen readers.
    assert heads[0].text(0).split("  (")[0] == "Scan devices"
    rows = [tree.visualItemRect(head).height() for head in heads]
    row = tree.visualItemRect(heads[1].child(0)).height()
    # The first header has no room above it; the others have more than a row has.
    assert rows[0] >= HEAD_BAND_HEIGHT and rows[1] == rows[0] + HEAD_GAP > row
    # A click on a header folds its group and opens it again.
    assert heads[1].isExpanded()
    rect = tree.visualItemRect(heads[1])
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert not heads[1].isExpanded()
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert heads[1].isExpanded()
    # The title and the count read on the band in both themes.
    try:
        for theme in ("light", "dark"):
            apply_theme(theme)
            for base in (theme_colors()["bg"], theme_colors()["card"]):
                colors = head_colors(base)
                assert contrast(colors["title"], colors["band"]) >= HEAD_MIN_CONTRAST, theme
                assert contrast(colors["count"], colors["badge"]) >= HEAD_MIN_CONTRAST, theme
    finally:
        apply_theme("light")


def test_nothing_fits_offers_close_names_and_says_so(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "Y")
    qtbot.keyClicks(edit, "bmp4i")
    assert listed(signals)[:3] == [
        ("message", "No signal of this scan fits “bmp4i”", ""),
        ("message", "The File tab lists everything the file holds.", ""),
        ("head", "Similar names", ""),
    ]
    assert listed(signals)[3][1] == "bpm4i"
    assert signals.typing.list.marked() is None
    qtbot.keyClick(edit, Qt.Key.Key_Return)  # nothing marked yet
    assert signals.y_signals() == [BPM3A]
    qtbot.keyClick(edit, Qt.Key.Key_Down)
    assert signals.typing.list.marked() == 3
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert signals.y_signals() == [BPM3A, BPM4I]
    # No close name either: nothing changes on the plot.
    qtbot.keyClicks(edit, "zzzz")
    assert [kind for kind, _, _ in listed(signals)] == ["message", "message"]


def test_the_arrow_opens_every_signal_that_can_take_the_role_by_group(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "Y")
    field = signals.box.fields["Y"]
    qtbot.mouseClick(field.arrow, Qt.MouseButton.LeftButton)
    typing = signals.typing
    assert typing.is_open("Y") and typing.by_user
    kinds = listed(signals)
    heads = [
        (text, e.count)
        for (kind, text, _), e in zip(kinds, typing.list.listing.entries)
        if kind == "head"
    ]
    assert [text for text, _ in heads] == ["Scan devices", "Monitored", "Async"]
    assert ("entry", "bpm3a", "on the plot") in kinds
    assert all(text != "mono" for _, text, _ in kinds)  # a baseline value is no curve
    assert typing.list.marked() is None
    # No line under the entries: the list is its rows.
    assert typing.list.findChildren(QLabel) == []
    margins = typing.list.layout().contentsMargins()
    assert typing.list.height() == typing.list.view.height() + margins.top() + margins.bottom()
    qtbot.keyClick(edit, Qt.Key.Key_Return)  # nothing marked: nothing happens
    assert signals.y_signals() == [BPM3A]
    # Down marks the first that is not on the plot; taking keeps the list open and moves on.
    qtbot.keyClick(edit, Qt.Key.Key_Down)
    first = typing.list.listing.entries[typing.list.marked()]
    assert first.takeable
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert first.key in signals.y_signals()
    assert typing.is_open("Y")
    marked = typing.list.listing.entries[typing.list.marked()]
    assert marked.takeable and marked.key != first.key
    # The arrow again closes it; Esc too, and only Esc of an open list is taken.
    qtbot.mouseClick(field.arrow, Qt.MouseButton.LeftButton)
    assert not typing.is_open()
    qtbot.keyClick(edit, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    assert typing.is_open("Y") and typing.list.marked() is None


def test_esc_closes_the_list_and_keeps_the_text_tab_leaves_and_drops_it(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "Y")
    qtbot.keyClicks(edit, "bpm")
    escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(edit, escape)
    assert escape.isAccepted()
    assert not signals.typing.is_open() and edit.text() == "bpm"
    # The list is closed: Esc is left to the window.
    assert not signals.typing.eventFilter(edit, escape)
    qtbot.keyClick(edit, Qt.Key.Key_Tab)
    assert not edit.hasFocus() and edit.text() == ""
    assert signals.y_signals() == [BPM3A]


def test_the_filter_finds_names_as_the_fields_do_and_marks_the_letters(qtbot, history):
    from bec_widgets.widgets.services.hdf5_viewer.signal_list import MATCH_ROLE

    signals = box_list(qtbot, history)
    rows = signals._rows  # pylint: disable=protected-access
    signals.filter_edit.setText("bp3")  # pieces that start the words of bpm3a
    shown = [key for key, row in rows.items() if not row.isHidden()]
    assert shown == [BPM3A]
    assert rows[BPM3A].data(0, MATCH_ROLE) == (0, 1, 3)
    # Letters scattered inside a word do not fit.
    signals.filter_edit.setText("smx")
    assert not any(not row.isHidden() for row in rows.values())
    assert signals.filter_empty.isVisibleTo(signals) and not signals.tree.isVisibleTo(signals)
    assert signals.filter_empty_text.text() == "No signal of this scan fits “smx”."
    qtbot.mouseClick(signals.clear_filter_button, Qt.MouseButton.LeftButton)
    assert signals.filter_edit.text() == ""
    assert signals.tree.isVisibleTo(signals) and not signals.filter_empty.isVisibleTo(signals)
    assert rows[BPM3A].data(0, MATCH_ROLE) == ()


def test_the_length_gives_way_once_names_get_short(qtbot, history):
    signals = box_list(qtbot, history)
    assert not signals.tree.isColumnHidden(1)
    # The panel keeps 260 px, where the length still fits; the picker has no such minimum.
    signals.resize(100, 700)
    assert signals.width() == 260 and not signals.tree.isColumnHidden(1)
    signals.setMinimumWidth(0)
    signals.resize(170, 700)
    qtbot.waitUntil(lambda: signals.tree.isColumnHidden(1))
    signals.resize(440, 700)
    qtbot.waitUntil(lambda: not signals.tree.isColumnHidden(1))


def test_leaving_the_window_keeps_the_text_and_the_list(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "Y")
    qtbot.keyClicks(edit, "bpm")
    mark = signals.typing.list.marked()
    for reason in (Qt.FocusReason.ActiveWindowFocusReason, Qt.FocusReason.PopupFocusReason):
        QApplication.sendEvent(edit, QFocusEvent(QEvent.Type.FocusOut, reason))
        assert edit.text() == "bpm"
        assert signals.typing.is_open("Y") and signals.typing.list.marked() == mark


def test_leaving_for_another_widget_closes_the_list_and_drops_the_text(qtbot, history):
    signals = box_list(qtbot, history)
    for reason in (
        Qt.FocusReason.TabFocusReason,
        Qt.FocusReason.BacktabFocusReason,
        Qt.FocusReason.MouseFocusReason,
        Qt.FocusReason.ShortcutFocusReason,
    ):
        edit = focus_field(qtbot, signals, "Y")
        qtbot.keyClicks(edit, "bpm")
        QApplication.sendEvent(edit, QFocusEvent(QEvent.Type.FocusOut, reason))
        assert edit.text() == "" and not signals.typing.is_open(), reason
    assert signals.y_signals() == [BPM3A]


def test_pasted_text_is_typed_text_with_lines_as_spaces(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "Y")
    QApplication.clipboard().setText("bpm\n4i")
    edit.paste()
    assert edit.text() == "bpm 4i"
    assert signals.typing.is_open("Y")
    assert [e.text for e in signals.typing.list.listing.entries] == ["bpm4i"]


def test_a_click_outside_closes_the_list(qtbot, history):
    signals = box_list(qtbot, history)
    edit = focus_field(qtbot, signals, "Y")
    qtbot.keyClicks(edit, "bpm")
    assert signals.typing.is_open()
    qtbot.mouseClick(signals.tree.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(5, 400))
    assert not signals.typing.is_open()


def test_left_walks_the_curves_and_backspace_takes_one_off(qtbot, history):
    signals = box_list(qtbot, history)
    signals.toggle_y(BPM4I)
    signals.toggle_y(("old_diode", "old_diode"))
    edit = focus_field(qtbot, signals, "Y")
    chips = lambda: signals.box.fields["Y"].flow.chips  # noqa: E731
    qtbot.keyClick(edit, Qt.Key.Key_Left)
    assert signals.typing.chip_mark == 2
    qtbot.keyClick(edit, Qt.Key.Key_Left)
    qtbot.keyClick(edit, Qt.Key.Key_Left)
    qtbot.keyClick(edit, Qt.Key.Key_Left)  # stays on the first
    assert signals.typing.chip_mark == 0
    qtbot.keyClick(edit, Qt.Key.Key_Right)
    qtbot.keyClick(edit, Qt.Key.Key_Delete)
    assert signals.y_signals() == [BPM3A, ("old_diode", "old_diode")]
    assert signals.typing.chip_mark == 1 and chips()[1].info.key == ("old_diode", "old_diode")
    # A letter goes back to typing.
    qtbot.keyClicks(edit, "b")
    assert signals.typing.chip_mark is None and edit.text() == "b"
    # Backspace in an empty field takes the last curve off.
    edit.clear()
    qtbot.keyClick(edit, Qt.Key.Key_Backspace)
    assert signals.y_signals() == [BPM3A]


@pytest.fixture(params=[False, True], ids=["alone", "dock_focus"])
def dock_focus(request):
    """
    QtAds focus highlighting off (the viewer alone) or on (as bec-app sets it); restored after.

    It must come before the viewer in a test's arguments: a dock manager reads it when built.
    """
    flag = QtAds.CDockManager.eConfigFlag.FocusHighlighting
    before = QtAds.CDockManager.testConfigFlag(flag)
    QtAds.CDockManager.setConfigFlag(flag, request.param)
    yield request.param
    QtAds.CDockManager.setConfigFlag(flag, before)


def test_a_field_that_does_not_apply_says_so_and_takes_no_typing(qtbot, dock_focus, map_viewer):
    viewer = map_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    y_field, z_field = signals.box.fields["Y"], signals.box.fields["Z"]
    assert y_field.edit.isEnabled() and y_field.role.caption == "y axis"
    assert z_field.edit.isEnabled() and z_field.role.caption == "colour"
    viewer.view_switch.buttons["lines"].click()
    # In Lines Y holds the curves and the colour waits for a map.
    assert y_field.edit.isEnabled() and y_field.edit.placeholderText() == "Add a signal…"
    assert z_field.role.caption == "colour"
    assert not z_field.edit.isEnabled() and not z_field.arrow.isEnabled()
    assert z_field.edit.placeholderText() == "Not used in Lines"
    assert not z_field.flow.chips
    assert [f.role.caption for f in signals.box.fields.values()] == ["x axis", "", "colour"]
    assert signals.box.count_badge.parentWidget() is signals.box._made["Y"][0]
    assert z_field.edit.accessibleName() == "The colour of a map. Not used in Lines"
    # No Tab stop and no click target: nothing can be done there.
    viewer.show()
    qtbot.waitExposed(viewer)
    y_edit = focus_field(qtbot, signals, "Y")
    qtbot.keyClick(y_edit, Qt.Key.Key_Tab)
    after_y = signals.box.reset_button if signals.box.reset_button.isVisible() else None
    qtbot.waitUntil(
        lambda: QApplication.focusWidget() is (after_y or signals.filter_edit), timeout=2000
    )
    # A click there never gives the field the focus. Where the focus goes is the host's: alone
    # it stays put, in bec-app the dock that was clicked takes it.
    before = QApplication.focusWidget()
    for target in (z_field, z_field.edit, z_field.arrow):
        qtbot.mouseClick(target, Qt.MouseButton.LeftButton, pos=target.rect().center())
        focus = QApplication.focusWidget()
        assert focus is None or not (focus is z_field or z_field.isAncestorOf(focus))
        if not dock_focus:
            assert focus is before
    qtbot.keyClicks(z_field.edit, "bpm")
    assert z_field.edit.text() == "" and not z_field.flow.chips
    assert not signals.typing.is_open()
    viewer.view_switch.buttons["heatmap"].click()
    captions = [f.role.caption for f in signals.box.fields.values()]
    assert captions == ["x axis", "y axis", "colour"]


def test_a_key_that_moves_the_current_row_gives_back_the_held_height(qtbot, history):
    signals = box_list(qtbot, history)
    signals.toggle_y(BPM4I)
    signals._hold_top()  # pylint: disable=protected-access
    assert signals.top.minimumHeight()
    signals.tree.setFocus()
    qtbot.keyClick(signals.tree, Qt.Key.Key_Down)
    assert signals.top.minimumHeight() == 0


def test_the_current_row_takes_the_ring_and_tint_of_the_scan_list(qtbot, history):
    from bec_widgets.utils.theme_utils import theme_colors
    from bec_widgets.widgets.services.bec_queue.queue_ui import ROW_SELECTED_ALPHA

    signals = box_list(qtbot, history)
    item = signals._rows[BPM4I]
    signals.tree.setCurrentItem(item)
    tint = QColor(theme_colors()["primary"])
    a = ROW_SELECTED_ALPHA
    # The theme paints no selection of its own; the list paints the row as the scan list.
    assert "background: transparent" in signals.tree.styleSheet()
    rect = signals.tree.visualItemRect(item)
    image = signals.tree.viewport().grab().toImage()
    # Inside the ring, right of the short name: the tint, over the panel's background.
    x = signals.tree.header().sectionSize(0) - 6
    inside = image.pixelColor(x, rect.center().y())
    assert abs(inside.alphaF() - a) < 0.02
    assert (
        max(
            abs(inside.red() - tint.red()),
            abs(inside.green() - tint.green()),
            abs(inside.blue() - tint.blue()),
        )
        <= 3
    )
    # On the ring at the top of the row: the primary colour.
    ring = image.pixelColor(x, rect.top() + 2)
    assert abs(ring.blue() - tint.blue()) <= 40 and abs(ring.red() - tint.red()) <= 40


def test_a_scan_switch_tells_the_rpc_registry_once(qtbot, viewer, monkeypatch):
    from bec_widgets.utils.rpc_register import RPCRegister

    qtbot.waitUntil(lambda: bool(viewer._curves))  # pylint: disable=protected-access
    walks = []
    real = RPCRegister.list_all_connections
    # The registry is walked and sent once per broadcast that is not held back.
    monkeypatch.setattr(
        RPCRegister, "list_all_connections", lambda self: walks.append(1) or real(self)
    )
    register = RPCRegister()
    monkeypatch.setattr(register, "callbacks", [lambda: (lambda _connections: None)])
    before = dict(viewer._curves)  # pylint: disable=protected-access
    viewer.scan_list.select("scan-1")
    wait_for_switch(qtbot, viewer)
    after = dict(viewer._curves)  # pylint: disable=protected-access
    assert set(after) != set(before)  # curves went and came
    assert len(walks) == 1


def test_a_held_arrow_key_loads_only_the_scan_it_stops_on(qtbot, viewer):
    loads = []
    real = viewer._switch_to  # pylint: disable=protected-access
    viewer._switch_to = lambda entry: loads.append(entry) or real(entry)
    view = viewer.scan_list.view
    view.setFocus()
    # Ten row changes before the event loop runs again, as when an arrow key is held.
    down, up = Qt.Key.Key_Down, Qt.Key.Key_Up
    for key in [down, down, up, down, up, up, down, up, down, down]:
        QApplication.sendEvent(
            view, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        )
    assert loads == []
    wait_for_switch(qtbot, viewer)
    assert [entry.scan_number for entry in loads] == [10]
    assert viewer.scan_list.current_entry().scan_number == 10
    # A call asks for its scan at once.
    viewer.show_scan(12)
    assert [entry.scan_number for entry in loads] == [10, 12]


def test_a_held_key_loads_on_its_release_or_once_it_settles(qtbot, viewer, monkeypatch):
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer as viewer_module

    loads = []
    real = viewer._switch_to  # pylint: disable=protected-access
    viewer._switch_to = lambda entry: loads.append(entry) or real(entry)
    view = viewer.scan_list.view
    viewer.scan_list.show()
    view.setFocus()

    def press(key, repeat):
        QApplication.sendEvent(
            view, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, "", repeat)
        )

    def release(key, repeat=False):
        QApplication.sendEvent(
            view, QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier, "", repeat)
        )

    down, up = Qt.Key.Key_Down, Qt.Key.Key_Up
    # (1) A held key: the first press is a real one, the others are repeats. Nothing loads
    # while it is held, the release loads the row it stopped on.
    press(down, False)
    qtbot.waitUntil(lambda: len(loads) == 1)
    for key in [down, up, down, up, down, up, down, up, down]:
        press(key, True)
        release(key, True)
        qtbot.wait(20)  # faster than the settle time
    assert len(loads) == 1
    assert view.key_held
    release(down)
    assert not view.key_held
    qtbot.waitUntil(lambda: len(loads) == 2)
    assert loads[-1].scan_id == viewer.scan_list.current_entry().scan_id
    qtbot.wait(viewer_module.HOLD_SETTLE_MS + 50)
    assert len(loads) == 2

    # (2) A single press and a click load at once, without the settle time.
    press(up, False)
    release(up)
    assert viewer._switch_timer.interval() == 0  # pylint: disable=protected-access
    qtbot.waitUntil(lambda: len(loads) == 3)
    rect = view.visualRect(view.model().index(0, 0))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    if viewer._switch_timer.isActive():  # pylint: disable=protected-access
        assert viewer._switch_timer.interval() == 0  # pylint: disable=protected-access

    # (3) No release at all: the settle time alone loads.
    monkeypatch.setattr(viewer_module, "HOLD_SETTLE_MS", 50)
    qtbot.wait(10)  # the click's load
    before = len(loads)
    press(down, True)
    assert viewer._switch_timer.interval() == 50  # pylint: disable=protected-access
    qtbot.waitUntil(lambda: len(loads) == before + 1, timeout=2000)
    assert loads[-1].scan_id == viewer.scan_list.current_entry().scan_id

    # (4) The list loses the focus while the key is held: the next press is no longer held.
    press(down, True)
    assert view.key_held
    viewer.signal_list.filter_edit.setFocus()
    QApplication.sendEvent(view, QFocusEvent(QEvent.Type.FocusOut))
    assert not view.key_held


def test_a_scan_of_motors_only_has_no_default_signal(qtbot, history):
    signals = SignalList()
    qtbot.addWidget(signals)
    entry = ScanEntry.from_history(history[0].model_dump())
    entry.stored_data_info = {"samx": entry.stored_data_info["samx"]}
    signals.set_scan(entry)
    assert signals.y_signals() == []
    assert not signals.has_default()


################################################################################
# Viewer
################################################################################


def test_viewer_lists_the_history_and_plots_the_newest_scan(qtbot, viewer):
    assert viewer.scan_list.current_entry().scan_number == 12
    qtbot.waitUntil(lambda: ("scan-2", "bpm3a", "bpm3a") in viewer._curves)
    curve = viewer._curves[("scan-2", "bpm3a", "bpm3a")][0]
    assert curve.config.source == "history"
    assert curve.config.scan_id == "scan-2"
    assert viewer.plot_title.text() == "Scan 12  line_scan"
    # The curve gets its data through the Data API; until then the plot says it is loading.
    qtbot.waitUntil(lambda: curve.xData is not None and len(curve.xData) == 20, timeout=10000)
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform)

    viewer.show_scan(10)
    assert viewer.plot_stack.currentWidget() is viewer.plot_state
    assert (viewer.plot_state.title.text(), viewer.plot_state.text.text()) == (
        "Loading the plot",
        "Scan 10",
    )
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform)
    # A signal added to a drawn plot does not hide it while it loads.
    viewer.signal_list.toggle_y(("bpm4i", "bpm4i"))
    assert viewer.plot_stack.currentWidget() is viewer.waveform


def hold_file_during_the_read(monkeypatch, viewer, path):
    """
    Hold a scan's file open without the lock, as the File tab did, from the moment the plot
    starts its Data API read: the read cannot open it with its own flags.
    """
    holders = []
    waveform = viewer.waveform
    real_open = waveform._open_history_subscription

    def open_while_held(scan_id, sources):
        if not holders:
            holders.append(h5py.File(path, "r", locking=False))
        return real_open(scan_id, sources)

    monkeypatch.setattr(waveform, "_open_history_subscription", open_while_held)

    def release():
        while holders:
            holders.pop().close()
        monkeypatch.setattr(waveform, "_open_history_subscription", real_open)

    return release


def test_a_failed_read_ends_the_loading_page_with_the_reason_and_a_way_to_read_again(
    qtbot, viewer, history, monkeypatch
):
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    release = hold_file_during_the_read(monkeypatch, viewer, history[0].file_path)
    try:
        viewer.show_scan(10)
        assert viewer.plot_state.title.text() == "Loading the plot"
        qtbot.waitUntil(
            lambda: viewer.plot_state.title.text() == "The plot could not be read", timeout=10000
        )
        assert viewer.plot_stack.currentWidget() is viewer.plot_state
        # bec_lib's read of the file gives up after its retries; its words stay at hand.
        assert (
            viewer.plot_state.text.text() == "The scan's file could not be opened at that moment."
        )
        assert viewer.plot_state.text.toolTip() == "Error accessing file."
        curve = viewer._curves[("scan-0", "bpm3a", "bpm3a")][0]
        assert viewer.waveform.history_curve_error(curve.name())
        assert not viewer.waveform.history_curve_waiting(curve.name())
        assert [b.text() for b in viewer.plot_state._actions] == ["Try again"]
        # The whole plot failed: the page says it, no note above it.
        assert viewer.read_note.isHidden()
    finally:
        release()

    # Once the file is free, Try again reads the scan and shows the plot in place.
    viewer.plot_state._actions[0].click()
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    assert viewer._curves[("scan-0", "bpm3a", "bpm3a")][0] is curve
    assert viewer.waveform.history_curve_error(curve.name()) is None
    assert len(curve.yData) == 20


def test_a_plot_that_cannot_be_made_while_the_file_is_held_offers_to_try_again(
    qtbot, viewer, history
):
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    # Held before the plot is made: bec_lib's own look into the file fails in plot().
    holder = h5py.File(history[0].file_path, "r", locking=False)
    try:
        viewer.show_scan(10)
        assert viewer.plot_state.title.text() == "The plot could not be read"
        assert (
            viewer.plot_state.text.text() == "The scan's file could not be opened at that moment."
        )
        assert viewer.plot_state.text.toolTip() == "Error accessing file."
    finally:
        holder.close()
    viewer.plot_state._actions[0].click()
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    assert ("scan-0", "bpm3a", "bpm3a") in viewer._curves


def test_a_curve_that_could_not_be_read_beside_drawn_ones_is_named_above_the_plot(
    qtbot, viewer, history, monkeypatch
):
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    assert viewer.read_note.isHidden()
    release = hold_file_during_the_read(monkeypatch, viewer, history[0].file_path)
    try:
        click_scan_row(qtbot, viewer, 2, Qt.KeyboardModifier.ControlModifier)  # pin scan 10
        qtbot.waitUntil(lambda: not viewer.read_note.isHidden(), timeout=10000)
    finally:
        release()
    assert viewer.plot_stack.currentWidget() is viewer.waveform
    assert viewer.read_note_text.full_text() == (
        "bpm3a could not be read. The scan's file could not be opened at that moment."
    )
    assert viewer.read_note_text.toolTip() == "Error accessing file."
    # bpm3a of scan 12 is drawn: its Y button and its chip stay those of a plotted signal.
    assert viewer.signal_list.unread_reason(("bpm3a", "bpm3a")) is None
    chip = viewer.signal_list.box.fields["Y"].chip_of(("bpm3a", "bpm3a"))
    assert not chip.info.problem and not has_bad_outline(chip)
    drawn = viewer._curves[("scan-2", "bpm3a", "bpm3a")][0]
    shown = drawn.yData.copy()

    viewer.read_note_button.click()
    qtbot.waitUntil(lambda: viewer.read_note.isHidden(), timeout=10000)
    # Only scan 10 was read again: the curve of scan 12 kept what it showed.
    assert viewer._curves[("scan-2", "bpm3a", "bpm3a")][0] is drawn
    np.testing.assert_array_equal(drawn.yData, shown)
    failed = viewer._curves[("scan-0", "bpm3a", "bpm3a")][0]
    qtbot.waitUntil(lambda: failed.yData is not None and len(failed.yData) == 20, timeout=10000)


def test_a_signal_none_of_whose_curves_could_be_read_does_not_look_plotted(qtbot, viewer):
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    signals = viewer.signal_list
    signals.toggle_y(("bpm4i", "bpm4i"))
    qtbot.waitUntil(lambda: ("scan-2", "bpm4i", "bpm4i") in viewer._curves)
    lost = viewer._curves[("scan-2", "bpm4i", "bpm4i")][0].name()
    errors = {lost: "Stored signal is missing."}
    viewer.waveform.history_curve_error = errors.get
    viewer._update_read_note()

    assert signals.unread_reason(("bpm4i", "bpm4i")) == "bpm4i is not stored in this scan's file"
    assert signals.unread_reason(("bpm3a", "bpm3a")) is None
    chip = signals.box.fields["Y"].chip_of(("bpm4i", "bpm4i"))
    assert chip.toolTip() == "Not drawn: bpm4i is not stored in this scan's file."
    assert has_bad_outline(chip)
    info = next(signal for signal in signals.signals() if signal.key == ("bpm4i", "bpm4i"))
    assert signals.chip_tip("Y", info) == (
        "Not drawn: bpm4i is not stored in this scan's file. Press Y to take it off the plot."
    )
    assert viewer.read_note_text.full_text() == (
        "bpm4i could not be read. bpm4i is not stored in this scan's file."
    )


def test_a_scan_without_points_is_said_as_such_and_not_as_a_failure(qtbot, viewer):
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    viewer.signal_list.toggle_y(("bpm4i", "bpm4i"))
    qtbot.waitUntil(lambda: ("scan-2", "bpm4i", "bpm4i") in viewer._curves)
    empty = viewer._curves[("scan-2", "bpm4i", "bpm4i")][0].name()
    errors = {empty: "no data in this scan"}
    viewer.waveform.history_curve_error = errors.get

    # Beside a drawn curve: named above the plot, with nothing to try again.
    viewer._update_read_note()
    assert not viewer.read_note.isHidden()
    assert viewer.read_note_text.full_text() == "bpm4i has no points in this scan."
    assert viewer.read_note_button.isHidden()

    # Alone: the page says so, without an alert and without a button.
    for curve, _live in viewer._curves.values():
        errors[curve.name()] = "no data in this scan"
    assert viewer._show_lines_page(viewer._plot_scans())
    assert viewer.plot_state.title.text() == "No points in this scan"
    assert viewer.plot_state.text.text() == "The scan stored no values for bpm3a, bpm4i."
    assert viewer.plot_state._actions == []


def test_a_curve_above_the_size_limit_is_not_loaded_until_asked_and_never_pops_up(
    qtbot, viewer, monkeypatch
):
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    waveform = viewer.waveform

    def no_popup(*_args, **_kwargs):
        raise AssertionError("the size question popped up")

    monkeypatch.setattr(waveform, "_confirm_large_dataset", no_popup)
    waveform.max_dataset_size_mb = 0.0001  # 104 bytes: 20 values of bpm3a are more
    viewer.show_scan(10)
    qtbot.waitUntil(lambda: viewer.plot_state.title.text() == "Not loaded", timeout=10000)
    assert viewer.plot_state.text.text() == ("bpm3a is larger than the size limit of 0.0001 MB.")
    assert [b.text() for b in viewer.plot_state._actions] == ["Load it"]

    viewer.plot_state._actions[0].click()
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    curve = viewer._curves[("scan-0", "bpm3a", "bpm3a")][0]
    qtbot.waitUntil(lambda: curve.yData is not None and len(curve.yData) == 20, timeout=10000)

    # Beside a drawn curve, a curve too large is named above the plot with Load it.
    viewer.signal_list.toggle_y(("bpm4i", "bpm4i"))
    qtbot.waitUntil(lambda: not viewer.read_note.isHidden(), timeout=10000)
    assert viewer.read_note_text.full_text() == (
        "bpm4i is larger than the size limit of 0.0001 MB."
    )
    assert viewer.read_note_button.text() == "Load it"
    viewer.read_note_button.click()
    qtbot.waitUntil(lambda: viewer.read_note.isHidden(), timeout=10000)


@pytest.mark.parametrize(
    "error, sentence",
    [
        (
            "Unable to synchronously open file (unable to open file: name = "
            "'/sls/x01da/data/p12345/raw/S00000-00999/S00053/S00053_master.h5', errno = 2, "
            "error message = 'No such file or directory', flags = 0, o_flags = 0)",
            "The scan's file is not there any more: /sls/x01da/data…00-00999/S00053/S00053_master.h5",
        ),
        (
            "[Errno 13] Permission denied: '/data/S00053_master.h5'",
            "This account may not read the scan's file",
        ),
        (
            "Unable to synchronously open file (file locking flag values don't match)",
            "The scan's file was open for another read at that moment",
        ),
        ("Stored signal is missing.", "bpm4i is not stored in this scan's file"),
        ("no data in this scan", "bpm4i has no points in this scan"),
        ("something else went wrong.", "something else went wrong"),
    ],
)
def test_a_failed_read_is_said_in_the_users_words(error, sentence):
    assert read_sentence(error, "bpm4i") == sentence


def test_a_plot_that_stays_loading_offers_to_read_again(qtbot, viewer, monkeypatch):
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer as viewer_module

    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform, timeout=10000)
    monkeypatch.setattr(viewer_module, "MAP_WAIT_MS", 0)
    # A read that never answers: the curves of scan 10 keep waiting.
    monkeypatch.setattr(viewer.waveform, "_on_history_data_update", lambda _update: None)
    viewer.show_scan(10)
    qtbot.waitUntil(lambda: viewer.plot_state.title.text() == "Still loading the plot")
    assert [b.text() for b in viewer.plot_state._actions] == ["Try again"]
    old = viewer.waveform._history_subscriptions["scan-0"]
    viewer.plot_state._actions[0].click()
    # The waiting scan is read anew.
    assert viewer.waveform._history_subscriptions["scan-0"] is not old
    assert viewer.plot_state.title.text() == "Loading the plot"


def click_scan_row(qtbot, viewer, row, modifier=Qt.KeyboardModifier.NoModifier):
    view = viewer.scan_list.view
    rect = view.visualRect(view.model().index(row, 0))
    # Left of the pin, so that the click lands on the row itself.
    point = rect.topLeft() + QPoint(40, rect.height() // 2)
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, modifier, point)


def scan_row(viewer, scan_id: str) -> int:
    """The row of a scan in the scan list as the list shows it."""
    model = viewer.scan_list.view.model()
    return next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data(ENTRY_ROLE) is not None
        and model.index(row, 0).data(ENTRY_ROLE).scan_id == scan_id
    )


class PanePaints(QObject):
    """What the plot pane paints: its title on each paint, and the state page when painted."""

    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self.titles: list[str] = []
        self.states: list[str] = []
        viewer.plot_title.installEventFilter(self)
        viewer.plot_state.installEventFilter(self)

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        if event.type() == QEvent.Type.Paint:
            if obj is self.viewer.plot_title:
                self.titles.append(obj.text())
            else:
                self.states.append(self.viewer.plot_state.title.text())
        return False

    def remove(self):
        self.viewer.plot_title.removeEventFilter(self)
        self.viewer.plot_state.removeEventFilter(self)


def drop_updates_of(monkeypatch, viewer, scan_id: str) -> None:
    """A read of one scan that never answers: its updates do not reach the plot."""
    real = viewer.waveform._on_history_data_update
    monkeypatch.setattr(
        viewer.waveform,
        "_on_history_data_update",
        lambda update: None if update.scan_id == scan_id else real(update),
    )


def test_a_click_on_another_scan_keeps_the_plot_until_the_new_one_is_drawn(qtbot, viewer):
    # pylint: disable=protected-access
    active_viewer(qtbot, viewer)
    viewer._hold_timer.setInterval(10_000)  # the plot alone ends the hold
    paints = PanePaints(viewer)
    try:
        qtbot.wait(50)
        paints.titles.clear()
        paints.states.clear()
        click_scan_row(qtbot, viewer, scan_row(viewer, "scan-0"))
        # While scan 10 is read, the pane keeps the plot of scan 12 as it is on screen.
        assert not viewer.plot_page.updatesEnabled()
        qtbot.waitUntil(viewer.plot_page.updatesEnabled, timeout=10000)
        curve = viewer._curves[("scan-0", "bpm3a", "bpm3a")][0]
        assert curve.yData is not None and len(curve.yData) == 20
        assert viewer.plot_stack.currentWidget() is viewer.waveform
        assert not viewer._hold_timer.isActive()
        qtbot.waitUntil(lambda: bool(paints.titles))
        # One change of the pane: to the drawn plot of scan 10, no loading page on the way.
        assert set(paints.titles) == {"Scan 10  line_scan"}
        assert paints.states == []
    finally:
        paints.remove()


def test_a_scan_picked_during_the_hold_is_the_one_the_pane_shows(qtbot, viewer, monkeypatch):
    # pylint: disable=protected-access
    active_viewer(qtbot, viewer)
    viewer._hold_timer.setInterval(10_000)
    drop_updates_of(monkeypatch, viewer, "scan-0")
    paints = PanePaints(viewer)
    try:
        qtbot.wait(50)
        paints.titles.clear()
        paints.states.clear()
        click_scan_row(qtbot, viewer, scan_row(viewer, "scan-0"))
        wait_for_switch(qtbot, viewer)
        assert viewer.plot_title.text() == "Scan 10  line_scan"
        # Scan 10 never comes in; the next click does not start the hold again.
        click_scan_row(qtbot, viewer, scan_row(viewer, "scan-1"))
        assert not viewer.plot_page.updatesEnabled()
        qtbot.waitUntil(viewer.plot_page.updatesEnabled, timeout=10000)
        assert viewer.plot_stack.currentWidget() is viewer.waveform
        qtbot.waitUntil(lambda: bool(paints.titles))
        assert set(paints.titles) == {"Scan 11  line_scan"}
        assert paints.states == []
    finally:
        paints.remove()


def test_the_hold_ends_after_its_time_when_the_data_does_not_come(qtbot, viewer, monkeypatch):
    # pylint: disable=protected-access
    active_viewer(qtbot, viewer)
    drop_updates_of(monkeypatch, viewer, "scan-0")
    paints = PanePaints(viewer)
    try:
        start = time.monotonic()
        click_scan_row(qtbot, viewer, scan_row(viewer, "scan-0"))
        assert not viewer.plot_page.updatesEnabled()
        qtbot.waitUntil(viewer.plot_page.updatesEnabled, timeout=5000)
        assert time.monotonic() - start >= SWITCH_HOLD_MS / 1000
        # The data is not in: the pane says so, and the page that says it stays.
        assert viewer.plot_stack.currentWidget() is viewer.plot_state
        assert viewer.plot_state.title.text() == "Loading the plot"
        qtbot.waitUntil(lambda: bool(paints.states))
        assert set(paints.states) == {"Loading the plot"}
    finally:
        paints.remove()


def test_a_failed_read_ends_the_hold_with_its_reason(qtbot, viewer, history, monkeypatch):
    # pylint: disable=protected-access
    active_viewer(qtbot, viewer)
    viewer._hold_timer.setInterval(60_000)  # the failure alone ends the hold
    release = hold_file_during_the_read(monkeypatch, viewer, history[0].file_path)
    try:
        click_scan_row(qtbot, viewer, scan_row(viewer, "scan-0"))
        assert not viewer.plot_page.updatesEnabled()
        qtbot.waitUntil(viewer.plot_page.updatesEnabled, timeout=15000)
        assert viewer.plot_stack.currentWidget() is viewer.plot_state
        assert viewer.plot_state.title.text() == "The plot could not be read"
        assert not viewer._hold_timer.isActive()
    finally:
        release()


def test_the_hold_waits_for_a_dataset_of_the_file_on_the_plot(qtbot, mocked_client, history):
    # pylint: disable=protected-access
    trace = "/entry/extra/trace"
    for msg in history[1:]:
        with h5py.File(msg.file_path, "a") as handle:
            handle[trace] = np.arange(20.0) * 3
        settle(msg.file_path)
    viewer = make_viewer(qtbot, mocked_client, history)
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    click_y(qtbot, viewer, trace)
    qtbot.waitUntil(lambda: file_curve(viewer, trace) is not None)
    viewer.signals_dock.setAsCurrentTab()
    active_viewer(qtbot, viewer)
    viewer._hold_timer.setInterval(10_000)

    click_scan_row(qtbot, viewer, scan_row(viewer, "scan-1"))
    assert not viewer.plot_page.updatesEnabled()
    qtbot.waitUntil(viewer.plot_page.updatesEnabled, timeout=10000)
    # Shown once the dataset of scan 11's file is drawn too.
    assert viewer._entry.scan_id == "scan-1"
    assert file_curve(viewer, trace) is not None
    assert viewer.plot_stack.currentWidget() is viewer.waveform


def test_hiding_or_closing_the_viewer_ends_the_hold(qtbot, viewer, monkeypatch):
    # pylint: disable=protected-access
    active_viewer(qtbot, viewer)
    drop_updates_of(monkeypatch, viewer, "scan-0")
    click_scan_row(qtbot, viewer, scan_row(viewer, "scan-0"))
    assert not viewer.plot_page.updatesEnabled()
    viewer.hide()
    assert viewer.plot_page.updatesEnabled()
    assert not viewer._hold_timer.isActive() and not viewer._hold_poll.isActive()

    active_viewer(qtbot, viewer)
    click_scan_row(qtbot, viewer, scan_row(viewer, "scan-1"))
    assert not viewer.plot_page.updatesEnabled()
    viewer.cleanup()
    viewer._destroyed = True  # cleaned up, as a close marks it
    assert viewer.plot_page.updatesEnabled()
    assert not viewer._hold_timer.isActive() and not viewer._hold_poll.isActive()


def test_ctrl_click_adds_a_scan_to_the_comparison_and_takes_it_off(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    assert "to compare" in viewer.plot_subtitle.full_text()
    selected = viewer.scan_list.current_entry().scan_id

    click_scan_row(qtbot, viewer, 2, Qt.KeyboardModifier.ControlModifier)

    # The selection stays; the clicked scan joins the plot.
    assert viewer.scan_list.current_entry().scan_id == selected
    assert set(viewer.scan_list.model.pins()) == {"scan-0"}
    assert ("scan-0", "bpm3a", "bpm3a") in viewer._curves
    assert "compared with 10" in viewer.plot_subtitle.full_text()

    click_scan_row(qtbot, viewer, 2, Qt.KeyboardModifier.ControlModifier)
    assert viewer.scan_list.model.pins() == {}
    assert "to compare" in viewer.plot_subtitle.full_text()


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


def test_viewer_compares_pinned_scans_in_shades_of_one_colour_each(qtbot, viewer):
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
    # A scan's first curve has its colour, the next a shade of the same hue; the line style
    # stays the second cue.
    first, second = (config[("scan-2", s, s)].color for s in ("bpm3a", "bpm4i"))
    assert first != second
    assert QColor(first).hslHue() == pytest.approx(QColor(second).hslHue(), abs=6)
    assert config[("scan-0", "bpm3a", "bpm3a")].color != first
    assert config[("scan-2", "bpm3a", "bpm3a")].pen_style == "solid"
    assert config[("scan-2", "bpm4i", "bpm4i")].pen_style == "dash"
    assert "compared with 10" in viewer.plot_subtitle.full_text()
    # The signal list shows the curves of the selected scan: row, Y button and chip in the
    # shade of that scan's colour, with the line style.
    signals = viewer.signal_list
    for key in (("bpm3a", "bpm3a"), ("bpm4i", "bpm4i")):
        color = QColor(config[("scan-2", *key)].color).name()
        assert [c.name() for c in signals.row_fill(key)] == [color]
        assert signals.swatch_of(key).color == color
    assert signals.swatch_of(("bpm4i", "bpm4i")).style == "dash"

    viewer.scan_list.model.toggle_pin("scan-0")
    assert len(viewer._curves) == 2

    viewer.signal_list.toggle_y(("bpm3a", "bpm3a"))
    viewer.signal_list.toggle_y(("bpm4i", "bpm4i"))
    assert not viewer._curves
    assert viewer.plot_stack.currentWidget() is viewer.plot_state
    assert viewer.plot_state.title.text() == "Nothing on the plot"


def test_the_shades_of_a_scan_keep_its_hue_and_read_on_the_plot():
    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.utils.theme_utils import theme_colors
    from bec_widgets.widgets.services.hdf5_viewer.scan_list import SERIES_COLORS
    from bec_widgets.widgets.services.hdf5_viewer.style import (
        CURVE_MIN_CONTRAST,
        SHADE_STEPS,
        contrast,
        oklch_of,
        scan_shades,
    )

    try:
        for theme in ("light", "dark"):
            apply_theme(theme)
            backs = (theme_colors()["bg"], theme_colors()["card"])
            for base in SERIES_COLORS[theme]:
                shades = scan_shades(base, backs)
                # The scan's own colour first, then distinct shades of its hue.
                assert len(shades) == SHADE_STEPS and shades[0].name() == base
                assert len({shade.name() for shade in shades}) == SHADE_STEPS
                hue = oklch_of(shades[0])[2]
                lightness = sorted(oklch_of(shade)[0] for shade in shades)
                assert min(b - a for a, b in zip(lightness, lightness[1:])) >= 0.05, base
                for shade in shades[1:]:
                    assert abs(oklch_of(shade)[2] - hue) < 0.05, (theme, base, shade.name())
                    assert min(contrast(shade, back) for back in backs) >= CURVE_MIN_CONTRAST
    finally:
        apply_theme("light")


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


def test_viewer_plots_a_signal_of_a_device_that_left_the_session(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)

    with mock.patch.object(ErrorPopupUtility(), "custom_exception_hook") as popup:
        viewer.signal_list.toggle_y(("old_diode", "old_diode"))

    popup.assert_not_called()
    assert set(viewer._curves) == {
        ("scan-2", "bpm3a", "bpm3a"),
        ("scan-2", "old_diode", "old_diode"),
    }
    assert (
        legend_texts(viewer)[("scan-2", "old_diode", "old_diode")] == "old_diode-old_diode-scan-12"
    )


def test_viewer_explains_a_signal_it_cannot_plot_in_place(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)

    with (
        mock.patch.object(ErrorPopupUtility(), "custom_exception_hook") as popup,
        mock.patch.object(viewer.waveform, "plot", side_effect=ValueError("no data")),
    ):
        viewer.signal_list.toggle_y(("bpm4i", "bpm4i"))

    # No popup and no broken entry: the reason stands under the title of the plot.
    popup.assert_not_called()
    assert set(viewer._curves) == {("scan-2", "bpm3a", "bpm3a")}
    assert "bpm4i could not be plotted: no data" in viewer.plot_subtitle.full_text()


def test_viewer_names_its_buttons_and_lists_for_tests_and_scripts(viewer):
    names = [
        "scan_list",
        "scan_search",
        "scan_filter_all",
        "scan_filter_finished",
        "scan_filter_early",
        "unpin_all_button",
        "scan_view",
        "signal_list",
        "signal_filter",
        "signal_view",
        "file_tree",
        "file_search",
        "file_view",
        "file_details",
        "dataset_preview",
        "open_file_button",
        "add_to_plot_button",
        "file_add_to_plot_button",
        "status_label",
    ]
    for name in names:
        assert len(viewer.findChildren(QWidget, name)) == 1, name


def test_viewer_lays_out_its_panes_as_fixed_docks(qtbot, viewer):
    assert {dock.objectName() for dock in viewer.dock_list()} == {
        "Scans",
        "Signals",
        "File",
        "Plot",
    }
    for dock in viewer.dock_list():
        features = dock.features()
        for feature in ("DockWidgetClosable", "DockWidgetFloatable", "DockWidgetMovable"):
            assert not features & getattr(type(dock).DockWidgetFeature, feature)
    # Signals and File are the two tabs of one dock area; "Open file…" is in the Scans card.
    area = viewer.signals_dock.dockAreaWidget()
    assert viewer.file_dock.dockAreaWidget() is area
    assert not area.titleBar().isAncestorOf(viewer.open_button)
    assert viewer.scan_list.isAncestorOf(viewer.open_button)
    # Every pane has the title tab of a dock in the dock area.
    for dock in viewer.dock_list():
        assert dock.dockAreaWidget().titleBar().isVisibleTo(viewer), dock.objectName()

    # Picking a tab of the dock area switches the middle; the right side keeps the scan's plot.
    assert not viewer.file_tab_current()
    viewer.file_dock.tabWidget().clicked.emit()
    assert viewer.file_tab_current()
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    viewer.signals_dock.tabWidget().clicked.emit()
    assert viewer.right_stack.currentWidget() is viewer.plot_page


def test_viewer_gives_the_room_to_the_plot_when_it_gets_narrower(qtbot, viewer):
    viewer.resize(1400, 700)
    viewer.show()
    splitter = viewer.plot_dock.dockAreaWidget().parentSplitter()
    plot_area = viewer.plot_dock.dockAreaWidget()
    qtbot.waitUntil(lambda: plot_area.sizePolicy().horizontalStretch() == 1)
    assert splitter.widget(0).sizePolicy().horizontalStretch() == 0
    # The panes take their opening widths once the window is laid out.
    qtbot.waitUntil(lambda: viewer.scan_list.width() == SCAN_LIST_OPEN_WIDTH)
    lists = splitter.sizes()[:2]
    viewer.resize(1100, 700)
    qtbot.waitUntil(lambda: splitter.sizes()[2] < 700)
    assert splitter.sizes()[:2] == lists


def opened_widths(qtbot, viewer, width):
    """Show the viewer, built before it has a width as in bec-app, and return its pane widths."""
    viewer.resize(100, 100)
    viewer.resize(width, 700)
    viewer.show()
    splitter = viewer.plot_dock.dockAreaWidget().parentSplitter()
    opened = []
    original = viewer._open_widths

    def record():
        original()
        opened.append(True)

    viewer._open_widths = record
    qtbot.waitUntil(lambda: bool(opened))
    # Let the panes lay out at their new widths.
    qtbot.wait(100)
    return splitter.sizes()


def plot_toolbar_overflows(viewer) -> bool:
    extension = viewer.waveform.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
    return extension is not None and extension.isVisible()


@pytest.mark.parametrize("width", [1500, 1900])
def test_viewer_opens_with_fixed_list_widths_and_gives_the_rest_to_the_plot(qtbot, viewer, width):
    scans, middle, plot = opened_widths(qtbot, viewer, width)
    assert viewer.scan_list.width() == SCAN_LIST_OPEN_WIDTH
    # The lists keep their widths: only the plot grows with the window.
    assert middle == MIDDLE_OPEN_WIDTH
    assert plot > scans + middle - 300
    assert not plot_toolbar_overflows(viewer)
    # The search row has the whole placeholder and the button its text.
    search = viewer.scan_list.search_edit
    assert search.width() >= viewer.scan_list.search_field_need()
    assert viewer.open_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon


@pytest.mark.parametrize("width", [1100, 1250, 900])
def test_a_narrow_viewer_keeps_the_plot_toolbar_whole_while_the_lists_can_give_way(
    qtbot, viewer, width
):
    scans, middle, plot = opened_widths(qtbot, viewer, width)
    areas = [viewer.scans_dock.dockAreaWidget(), viewer.signals_dock.dockAreaWidget()]
    minimums = [area.minimumSizeHint().width() for area in areas]
    need = viewer._plot_toolbar_need(viewer.plot_dock.dockAreaWidget())
    padding = scans - viewer.scan_list.width()
    assert scans <= SCAN_LIST_OPEN_WIDTH + padding and middle <= MIDDLE_OPEN_WIDTH
    if plot >= need:
        assert not plot_toolbar_overflows(viewer)
    else:
        # Only once both lists are at their minimums does the plot get less.
        assert [scans, middle] == minimums
    # The middle pane gives way before the scans pane does.
    if scans < SCAN_LIST_OPEN_WIDTH + padding:
        assert middle == minimums[1]


def test_tree_leaves_the_type_column_out_while_it_is_narrow(qtbot, service):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.resize(500, 400)
    tree.show()
    qtbot.waitUntil(lambda: not tree.view.isColumnHidden(2))
    tree.resize(320, 400)
    qtbot.waitUntil(lambda: tree.view.isColumnHidden(2))
    tree.cleanup()


def test_viewer_says_when_a_scan_has_no_default_plot(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    entry = viewer.scan_list.current_entry()
    entry.stored_data_info = {"samx": entry.stored_data_info["samx"]}
    viewer._on_scan_selected(entry)
    wait_for_switch(qtbot, viewer)
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.plot_state)
    assert viewer.plot_state.title.text() == "No default plot"
    assert not viewer._curves


def test_viewer_sets_the_x_axis_from_the_signal_list(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    viewer.signal_list.toggle_x(("bpm4i", "bpm4i"))
    assert viewer.waveform.x_mode == "bpm4i"
    assert box_text(viewer.signal_list) == "X: bpm4i | Y: bpm3a auto"
    viewer.signal_list.toggle_x(("bpm4i", "bpm4i"))
    assert viewer.waveform.x_mode == "samx"


def test_viewer_plots_signals_against_the_positioner_of_the_scan(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    # The plot is told the motor, and the list names it: what it says is what is drawn.
    assert viewer.waveform.x_mode == "samx"
    assert viewer.waveform.signal_x == "samx"
    assert box_text(viewer.signal_list) == "X: samx auto | Y: bpm3a auto"
    assert viewer.signal_list.box.fields["X"].flow.chips[0].info.tip == AUTO_TIP

    # A scan that moved another motor first, compared with this one: the plot chooses.
    other = viewer.scan_list.model.entries()[0]
    other.motors = ("samy",)
    viewer.scan_list.model.toggle_pin(other.scan_id)
    qtbot.waitUntil(lambda: viewer.waveform.x_mode == "auto")
    assert box_text(viewer.signal_list).startswith("X: chosen by the plot auto | ")

    # Fast signals keep their sample number.
    viewer.scan_list.model.clear_pins()
    viewer.signal_list.toggle_y(("wave", "wave"))
    qtbot.waitUntil(lambda: viewer.waveform.x_mode == "index")
    assert box_text(viewer.signal_list) == "X: sample number auto | Y: wave"
    assert viewer.signal_list.note.text() == ASYNC_NOTE
    # Timestamp and Index pair no values: they can be the x axis of async curves too.
    signals = viewer.signal_list
    assert signals.x_mode_state(TIMESTAMP_X) == ("", "")
    signals.take_role("X", TIMESTAMP_X)
    qtbot.waitUntil(lambda: viewer.waveform.x_mode == "timestamp")
    assert box_text(signals) == "X: Timestamp | Y: wave"
    signals.take_role("X", INDEX_X)
    qtbot.waitUntil(lambda: viewer.waveform.x_mode == "index")


def scan_device_rows(signal_list) -> list[tuple[str, str, str]]:
    """Label, count column and tooltip of each row of the Scan devices group."""
    head = signal_list._scan_head  # pylint: disable=protected-access
    if head is None:
        return []
    return [
        (head.child(row).text(0), head.child(row).text(1), head.child(row).toolTip(0))
        for row in range(head.childCount())
    ]


def test_the_scan_devices_are_listed_first_with_their_axis_chosen(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    signals = viewer.signal_list
    # The motor of the scan has a group of its own, on top, and is not listed twice.
    assert signals.tree.topLevelItem(0) is signals._scan_head  # pylint: disable=protected-access
    rows = scan_device_rows(signals)
    assert [row[0] for row in rows] == ["samx"]
    assert rows[0][1].startswith("auto") and rows[0][2] == AUTO_TIP
    point_head = signals.tree.topLevelItem(1)
    listed = [point_head.child(row).text(0) for row in range(point_head.childCount())]
    assert "samx" not in listed
    # The boxes are BEC's readout groups, read from the file; images and spectra are listed in
    # their readout group after its single numbers.
    qtbot.waitUntil(
        lambda: {s.key: s.box for s in signals.signals()}[("camera", "camera")] == "fast"
    )
    heads = [signals.tree.topLevelItem(i) for i in range(signals.tree.topLevelItemCount())]
    assert [head.text(0).split("  (")[0] for head in heads] == [
        "Scan devices",
        "Monitored",
        "Async",
        "Baseline",
    ]
    async_rows = [heads[2].child(row) for row in range(heads[2].childCount())]
    assert [row.text(0) for row in async_rows] == ["wave", "camera"]
    assert async_rows[1].text(1) == "20 × 8 × 8" and not async_rows[1].icon(0).isNull()
    assert "an image per reading" in async_rows[1].toolTip(0)
    assert signals.axis_of(("samx", "samx")) == "x" and signals.axes_are_auto()
    assert not signals.reset_axes_button.isVisibleTo(signals)

    # Another x: the ticks follow, the mark goes, and Reset axes brings the motor back.
    signals.toggle_x(("bpm4i", "bpm4i"))
    assert signals.axis_of(("bpm4i", "bpm4i")) == "x"
    assert signals.axis_of(("samx", "samx")) == ""
    assert not scan_device_rows(signals)[0][1].startswith("auto")
    assert signals.reset_axes_button.isVisibleTo(signals)
    signals.reset_axes_button.click()
    assert signals.x_signal() is None and viewer.waveform.x_mode == "samx"
    assert scan_device_rows(signals)[0][1].startswith("auto")

    # X on the motor that is the axis already keeps it chosen by the scan.
    signals.toggle_x(("samx", "samx"))
    assert signals.axes_are_auto()


def test_a_scan_that_moved_nothing_has_no_scan_devices(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    entry = viewer.scan_list.current_entry()
    entry.motors = ()
    viewer._on_scan_selected(entry)
    wait_for_switch(qtbot, viewer)
    viewer._refresh_plot()
    signals = viewer.signal_list
    assert scan_device_rows(signals) == []
    assert box_text(signals).startswith("X: point number auto | ")
    assert signals.box.fields["X"].flow.chips[0].info.tip == "The scan moved no device"


def test_the_file_tab_keeps_the_map_and_its_rows_choose_its_axes(qtbot, map_viewer):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    entry = viewer.scan_list.current_entry()
    file_tab_of_scan(qtbot, viewer, entry.file_path)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    assert viewer.plot_stack.currentWidget() is viewer.maps.scatter
    # The fields are the map's, as in Signals.
    assert [r.letter for r in viewer.signal_list.roles()] == list(viewer.file_box.box.fields)
    assert field_chips(viewer.file_box.box, "Z") == field_chips(viewer.signal_list.box, "Z")
    signals = viewer.signal_list
    samy = "/entry/collection/devices/samy/samy/value"
    bpm4i = "/entry/collection/devices/bpm4i/bpm4i/value"
    # The rows of signals show the axes: X on samx, Y on samy.
    samx = "/entry/collection/devices/samx/samx/value"
    assert viewer.tree._x_rows[samx] is True and viewer.tree._x_rows[samy] is False
    assert viewer.tree._kept == {samy: ""}
    # Y on a row does what Y does on its row in Signals: it becomes the map's y axis.
    pick_row(qtbot, viewer, bpm4i, by_hand=False)
    viewer.tree.keep_toggled.emit(viewer.preview.node)
    assert signals.plane_axes()[1] == BPM4I
    assert viewer.tree._kept == {bpm4i: ""}
    assert viewer.right_stack.currentWidget() is viewer.plot_page


def test_the_rows_of_signals_in_the_file_tab_have_the_z_button_of_the_map(qtbot, map_viewer):
    # pylint: disable=protected-access
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    entry = viewer.scan_list.current_entry()
    file_tab_of_scan(qtbot, viewer, entry.file_path)
    tree, signals = viewer.tree, viewer.signal_list
    bpm3a = "/entry/collection/devices/bpm3a/bpm3a/value"
    bpm4i = "/entry/collection/devices/bpm4i/bpm4i/value"
    assert signals.row_letters() == ["X", "Y", "Z"] and signals.y_signals() == [BPM3A]
    # As on their rows in Signals: Z in the colour of the map where it colours it.
    assert tree._z_rows[bpm3a] == ZButton(color=signals.swatch_of(BPM3A).color)
    assert tree._z_rows[bpm4i] == ZButton()
    # X, Y and Z side by side in the column of the buttons, Z on the right as in Signals.
    header = tree.view.header()
    assert header.sectionSize(Y_COLUMN) == Y_COLUMN_WIDTH + X_BUTTON_ROOM + Z_BUTTON_ROOM
    tree.select_path(bpm4i)
    qtbot.waitUntil(lambda: tree_row(tree, bpm4i) is not None)
    click_row(qtbot, viewer, bpm3a)
    qtbot.waitUntil(lambda: tree.current_node().path == bpm3a)
    row = show_row(qtbot, viewer, bpm4i)
    cell = tree.view.visualRect(row.sibling(row.row(), Y_COLUMN))
    z_rect = _MutedColumnDelegate.z_button_rect(cell)
    y_rect = _MutedColumnDelegate.button_rect(cell, z=True)
    x_rect = _MutedColumnDelegate.x_button_rect(cell, z=True)
    assert x_rect.right() < y_rect.left() and y_rect.right() < z_rect.left()
    assert tree.view.viewport().rect().contains(z_rect)
    # A click on the Z of bpm4i colours the map by it, as Z on its row in Signals; the row
    # under the pointer is not selected.
    qtbot.mouseClick(tree.view.viewport(), Qt.MouseButton.LeftButton, pos=z_rect.center())
    assert signals.y_signals() == [BPM4I]
    assert tree.current_node().path == bpm3a
    assert tree._z_rows[bpm4i] == ZButton(color=signals.swatch_of(BPM4I).color)
    assert tree._z_rows[bpm3a] == ZButton()
    # Z on the current row does the same.
    qtbot.keyClick(tree.view, Qt.Key.Key_Z)
    assert signals.y_signals() == [BPM3A]
    assert tree._z_rows[bpm3a].color
    assert viewer.right_stack.currentWidget() is viewer.plot_page


def test_the_two_motors_of_a_map_are_its_x_and_y_axes(qtbot, map_viewer):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    signals = viewer.signal_list
    assert [row[0] for row in scan_device_rows(signals)] == ["samx", "samy"]
    assert all(row[1].startswith("auto") for row in scan_device_rows(signals))
    assert signals.axis_of(("samx", "samx")) == "x"
    assert signals.axis_of(("samy", "samy")) == "y"
    # Y on an axis does not make it the colour.
    signals.toggle_y(("samy", "samy"))
    assert signals.y_signals() == [BPM3A]
    assert "is an axis of the map" in signals.note.text()


def open_hdf5_files() -> set[str]:
    """Paths of the files HDF5 has open in this process."""
    return {
        os.path.normpath(file_id.name.decode())
        for file_id in h5py.h5f.get_obj_ids(types=h5py.h5f.OBJ_FILE)
    }


def read_like_bec(path):
    """bec_lib's own reads of a stored signal: the whole entry, and block by block."""
    from bec_lib.scan_data_container import FileReference, SignalDataReference

    whole = FileReference(path).read("entry/collection/devices/bpm3a/bpm3a/value", cached=False)
    with SignalDataReference(path, "entry/collection/devices/bpm3a/bpm3a").read_slabs() as slabs:
        rows = sum(slab.stop - slab.start for slab in slabs)
    return len(whole), rows


def test_a_listed_scan_file_is_read_by_the_file_tab_and_by_bec_at_the_same_moment(
    viewer, history, monkeypatch
):
    from bec_lib import scan_data_container

    monkeypatch.setattr(scan_data_container.time, "sleep", lambda _s: None)  # its retries
    path = history[0].file_path
    assert h5_reader.is_listed(path)  # the viewer named the files of its history
    with h5_reader.open_readonly(path):
        # While the viewer reads, bec_lib opens the same file as the Data API does.
        assert read_like_bec(path) == (20, 20)

    # The proof that it bites: held without the lock, bec_lib cannot open it.
    with h5py.File(path, "r", locking=False):
        with pytest.raises(RuntimeError, match="Error accessing file"):
            read_like_bec(path)


def test_a_file_that_is_not_listed_is_read_without_the_lock(data_file):
    assert not h5_reader.is_listed(str(data_file))
    with h5_reader.open_readonly(str(data_file)):
        # Opened without the lock: another open with the default flags is refused.
        with pytest.raises(OSError, match="flag values don't match"):
            h5py.File(data_file, "r")


def test_a_listed_file_opened_by_hand_is_read_as_the_data_api_reads_it(qtbot, viewer, history):
    viewer.open_file(history[1].file_path)
    qtbot.waitUntil(lambda: viewer.tree.model.rowCount() == 1)
    # The footer names the whole path of the file and how much of it was read.
    qtbot.waitUntil(lambda: viewer.status_note.text().endswith(" read"))
    assert viewer.status_label.full_text() == history[1].file_path
    assert h5_reader.is_listed(history[1].file_path)


def test_listed_files_are_named_per_owner_and_by_path(tmp_path):
    first, second = object(), object()
    h5_reader.set_listed_files(first, [str(tmp_path / "a" / ".." / "S1.h5")])
    h5_reader.set_listed_files(second, [str(tmp_path / "S2.h5")])
    try:
        assert h5_reader.is_listed(str(tmp_path / "S1.h5"))
        assert h5_reader.is_listed(str(tmp_path / "S2.h5"))
        h5_reader.set_listed_files(first, [])
        assert not h5_reader.is_listed(str(tmp_path / "S1.h5"))
        assert h5_reader.is_listed(str(tmp_path / "S2.h5"))
    finally:
        h5_reader.set_listed_files(first, [])
        h5_reader.set_listed_files(second, [])


def test_the_file_tab_keeps_no_file_of_a_listed_scan_open_after_its_reads(qtbot, viewer, history):
    path = os.path.normpath(history[2].file_path)
    viewer.file_dock.setAsCurrentTab()
    qtbot.waitUntil(lambda: viewer.tree.model.rowCount() == 1)
    qtbot.waitUntil(lambda: viewer.tree.model.item(0).rowCount() == 1)
    qtbot.waitUntil(lambda: path not in open_hdf5_files(), timeout=2000)
    qtbot.wait(300)  # the reads that follow the first ones close their file too
    assert path not in open_hdf5_files()


def test_a_read_that_meets_another_read_with_other_flags_waits_and_is_then_busy(
    history, monkeypatch
):
    monkeypatch.setattr(h5_reader, "OTHER_READER_WAIT_S", 0.2)
    path = history[0].file_path
    owner = object()
    h5_reader.set_listed_files(owner, [path])
    try:
        holder = h5py.File(path, "r", locking=False)
        released = threading.Timer(0.05, holder.close)
        released.start()
        # The other read ends within the wait: this one goes on.
        with h5_reader.open_readonly(path) as handle:
            assert "entry" in handle
        released.join()

        with h5py.File(path, "r", locking=False):
            with pytest.raises(H5ReadError) as raised:
                with h5_reader.open_readonly(path):
                    pass
    finally:
        h5_reader.set_listed_files(owner, [])
    error = raised.value
    assert (error.kind, error.other_reader) == ("busy", True)
    _icon, title, text, actions = error_state(error, lambda: None, waiting=True)
    assert title == "In use at this moment"
    assert text == (
        f"Another part of this program is reading {os.path.basename(path)} right now. "
        "It opens here by itself in a moment."
    )
    assert [label for label, _callback in actions] == ["Check again"]


def test_viewer_shows_the_file_of_the_scan_in_the_file_tab(qtbot, viewer, history):
    viewer.file_dock.setAsCurrentTab()
    # The plot pane keeps the scan's plot; the tab shows its file.
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    qtbot.waitUntil(lambda: viewer.tree.model.rowCount() == 1)
    assert viewer.tree.file_path == history[2].file_path
    qtbot.waitUntil(lambda: viewer.tree.model.item(0).rowCount() == 1)
    # The footer names the whole path of the file and how much of it was read.
    assert viewer.status_label.full_text() == history[2].file_path
    assert viewer.status_label.toolTip() == history[2].file_path
    assert re.fullmatch(r"·  \S+ \S+ of \S+ \S+ read", viewer.status_note.text())
    assert "read-only" not in viewer.status_note.text()
    # On the Signals tab it names the file and its size.
    viewer.signals_dock.setAsCurrentTab()
    assert viewer.status_label.full_text() == history[2].file_path
    assert "read" not in viewer.status_note.text()
    viewer.file_dock.setAsCurrentTab()

    # An image of the scan opens in the file view at the place BEC stored it.
    viewer.signals_dock.setAsCurrentTab()
    camera = next(s for s in viewer.signal_list.signals() if s.device == "camera")
    viewer.signal_list.open_requested.emit(camera)
    assert viewer.file_tab_current()
    qtbot.waitUntil(
        lambda: viewer.preview.node is not None
        and viewer.preview.node.path == "/entry/collection/devices/camera/camera/value"
    )
    qtbot.waitUntil(lambda: viewer.preview.view == "image")


BPM4I_VALUE = "/entry/collection/devices/bpm4i/bpm4i/value"
BPM4I_TIMESTAMP = "/entry/collection/devices/bpm4i/bpm4i/timestamp"
BPM3A_TIMESTAMP = "/entry/collection/devices/bpm3a/bpm3a/timestamp"
#: A dataset of the scan's file that its plot cannot draw: frames of a camera.
CAMERA_VALUE = "/entry/collection/devices/camera/camera/value"


def file_tab_of_scan(qtbot, viewer, file_path):
    """Bring the File tab to the front and wait until its tree lists the scan's file."""
    viewer.file_dock.setAsCurrentTab()
    qtbot.waitUntil(lambda: viewer.tree.file_path == file_path)
    qtbot.waitUntil(lambda: viewer.tree.model.rowCount() == 1)
    qtbot.waitUntil(lambda: viewer.tree.model.item(0).rowCount() == 1)


def tree_row(tree, path):
    """The index of the row of a path in the tree, or None while it is not listed."""
    item = tree.model.item(0)
    for name in [part for part in path.split("/") if part]:
        children = [item.child(row) for row in range(item.rowCount())]
        item = next((child for child in children if child.text() == name), None)
        if item is None:
            return None
    return item.index()


def show_row(qtbot, viewer, path):
    """Show the viewer and list the row of a path in the File tab's tree, in view."""
    tree = viewer.tree
    if not tree.view.isVisible():
        viewer.show()
        qtbot.waitExposed(viewer)
    if tree_row(tree, path) is None:
        tree.select_path(path.rsplit("/", 1)[0])
        qtbot.waitUntil(lambda: tree_row(tree, path) is not None)
    tree.view.scrollTo(tree_row(tree, path))
    return tree_row(tree, path)


def click_y(qtbot, viewer, path):
    """Click the Y button of a row of the File tab's tree, as a person does."""
    tree = viewer.tree
    row = show_row(qtbot, viewer, path)
    cell = tree.view.visualRect(row.sibling(row.row(), Y_COLUMN))
    rect = _MutedColumnDelegate.button_rect(cell, z=tree.has_z_rows())
    qtbot.mouseClick(tree.view.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def click_row(qtbot, viewer, path):
    """Click the name of a row of the File tab's tree, as a person does."""
    tree = viewer.tree
    rect = tree.view.visualRect(show_row(qtbot, viewer, path))
    # On the name, clear of the buttons of the row.
    point = QPoint(rect.left() + 6, rect.center().y())
    qtbot.mouseClick(tree.view.viewport(), Qt.MouseButton.LeftButton, pos=point)


def pick_row(qtbot, viewer, path, by_hand=True):
    """Select a row of the File tab's tree with a click on it, or as the viewer itself does."""
    if by_hand:
        click_row(qtbot, viewer, path)
    else:
        viewer.tree.select_path(path)
    qtbot.waitUntil(lambda: viewer.preview.node is not None and viewer.preview.node.path == path)


def field_chips(box, letter="Y"):
    """(key, label, tag) of each chip of a field of a box."""
    return [(c.info.key, c.info.label, c.info.tag) for c in box.fields[letter].flow.chips]


def test_switching_tabs_keeps_the_plot_of_the_scan_as_it_is(qtbot, viewer, history):
    qtbot.waitUntil(lambda: bool(viewer._curves) and not viewer._lines_loading())
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform)
    qtbot.wait(100)
    curves = dict(viewer._curves)
    view_box = viewer.waveform.plot_item.getViewBox()
    view_box.setXRange(0.2, 1.4, padding=0)
    qtbot.wait(50)
    shown = view_box.viewRange()
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    qtbot.wait(300)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    # Nothing is drawn again: the same curves, at the same zoom.
    assert viewer._curves == curves
    assert view_box.viewRange() == shown
    # The fields of the File tab are those of Signals: no chip for a selected dataset.
    assert field_chips(viewer.file_box.box) == field_chips(viewer.signal_list.box)
    assert all(tag != "selected" for _key, _label, tag in field_chips(viewer.file_box.box))
    viewer.signals_dock.setAsCurrentTab()
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    assert viewer._curves == curves and view_box.viewRange() == shown


def test_a_row_of_the_scans_file_that_is_a_signal_is_only_selected(qtbot, viewer, history):
    qtbot.waitUntil(lambda: bool(viewer._curves))
    curves = dict(viewer._curves)
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    chips = field_chips(viewer.signal_list.box)
    pick_row(qtbot, viewer, BPM4I_VALUE)
    # Its details are shown; the plot and the fields stay as they are.
    qtbot.waitUntil(lambda: viewer.preview._details is not None)
    # Lines: the rows have no Z, as in Signals.
    assert viewer.tree._z_rows == {}
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    assert viewer._curves == curves
    assert field_chips(viewer.file_box.box) == chips


def test_a_dataset_the_plot_cannot_draw_opens_the_preview_only_on_a_click(qtbot, viewer, history):
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    # Selected by the viewer, not by hand: the scan's plot stays.
    pick_row(qtbot, viewer, CAMERA_VALUE, by_hand=False)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    # Picked by hand: the file's preview. The fields stay those of the scan's plot.
    pick_row(qtbot, viewer, BPM4I_VALUE)
    pick_row(qtbot, viewer, CAMERA_VALUE)
    assert viewer.right_stack.currentWidget() is viewer.preview
    qtbot.waitUntil(lambda: viewer.preview.view == "image")
    assert field_chips(viewer.file_box.box) == field_chips(viewer.signal_list.box)
    # A signal picked again brings the scan's plot back.
    pick_row(qtbot, viewer, BPM4I_VALUE)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    # So does the Signals tab; back in the File tab the plot stays until the next click.
    pick_row(qtbot, viewer, CAMERA_VALUE)
    assert viewer.right_stack.currentWidget() is viewer.preview
    viewer.signals_dock.setAsCurrentTab()
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    viewer.file_dock.setAsCurrentTab()
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    assert viewer.preview.node.path == CAMERA_VALUE


def test_back_to_the_plot_shows_the_scans_plot_and_keeps_the_row_selected(
    qtbot, viewer, history, data_file
):
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    back = viewer.back_button
    assert not back.isVisibleTo(viewer)
    pick_row(qtbot, viewer, CAMERA_VALUE)
    assert viewer.right_stack.currentWidget() is viewer.preview
    # In the header of the preview while it covers the scan's plot.
    assert back.isVisibleTo(viewer) and back.text() == "Back to the plot"
    assert viewer.preview.isAncestorOf(back)
    qtbot.mouseClick(back, Qt.MouseButton.LeftButton)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    assert viewer.tree.current_node().path == CAMERA_VALUE
    assert not back.isVisibleTo(viewer)
    # A click on the row opens it again.
    pick_row(qtbot, viewer, CAMERA_VALUE)
    assert viewer.right_stack.currentWidget() is viewer.preview and back.isVisibleTo(viewer)
    # A file that is not the scan's has no plot of the scan to go back to.
    show_dataset(qtbot, viewer, data_file, "/entry/plot/counts")
    assert viewer.right_stack.currentWidget() is viewer.preview
    assert not back.isVisibleTo(viewer)


def test_a_click_or_enter_on_the_selected_row_opens_the_preview(qtbot, viewer, history):
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    pick_row(qtbot, viewer, CAMERA_VALUE)
    assert viewer.right_stack.currentWidget() is viewer.preview
    viewer.signals_dock.setAsCurrentTab()
    viewer.file_dock.setAsCurrentTab()
    qtbot.wait(SELECT_DELAY_MS + 50)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    # The same row again, already selected and shown: the click itself opens the preview.
    pick_row(qtbot, viewer, CAMERA_VALUE)
    assert viewer.right_stack.currentWidget() is viewer.preview
    # Enter on the selected row does too.
    viewer.signals_dock.setAsCurrentTab()
    viewer.file_dock.setAsCurrentTab()
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    qtbot.keyClick(viewer.tree.view, Qt.Key.Key_Return)
    assert viewer.right_stack.currentWidget() is viewer.preview


def test_the_fill_of_a_tree_row_starts_at_its_icon(qtbot, viewer, history):
    # pylint: disable=protected-access
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    tree = viewer.tree
    bpm3a = "/entry/collection/devices/bpm3a/bpm3a/value"
    click_row(qtbot, viewer, bpm3a.rsplit("/", 1)[0] + "/timestamp")
    fill = QColor(viewer.signal_list.signal_color(BPM3A))
    assert fill.isValid()
    index = tree_row(tree, bpm3a)
    cell = tree.view.visualRect(index)
    icon = tree.view._content_left(index, cell)
    assert icon > cell.left()
    image = tree.view.viewport().grab().toImage()
    ratio = image.devicePixelRatio()

    def near_fill(x):
        color = image.pixelColor(int(x * ratio), int(cell.center().y() * ratio))
        return max(abs(color.red() - fill.red()), abs(color.green() - fill.green())) < 24

    # Filled up to a few pixels before the icon, not further out than after the buttons.
    assert near_fill(icon - 2)
    assert not near_fill(icon - ROW_RING_GAP - 3)


def test_a_row_the_viewer_selects_right_after_a_click_keeps_the_plot(qtbot, viewer, history):
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    tree = viewer.tree
    tree.select_path(BPM4I_VALUE.rsplit("/", 1)[0])
    click_row(qtbot, viewer, BPM4I_VALUE)
    assert tree.current_node().path == BPM4I_VALUE
    # Before the clicked row is read, the viewer selects a dataset the plot cannot draw.
    tree.select_path(CAMERA_VALUE)
    qtbot.waitUntil(lambda: viewer.preview.node is not None)
    qtbot.waitUntil(lambda: viewer.preview.node.path == CAMERA_VALUE)
    qtbot.wait(SELECT_DELAY_MS + 50)
    assert viewer.right_stack.currentWidget() is viewer.plot_page


def test_the_file_preview_reads_only_while_it_is_shown(qtbot, viewer, history, monkeypatch):
    # pylint: disable=protected-access
    qtbot.waitUntil(lambda: bool(viewer._curves) and not viewer._lines_loading())
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    preview = viewer.preview
    qtbot.wait(SELECT_DELAY_MS + 100)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    channels = []
    request = viewer.service.request

    def spy(channel, *args, **kwargs):
        channels.append(channel)
        return request(channel, *args, **kwargs)

    monkeypatch.setattr(viewer.service, "request", spy)

    def values_read():
        reads = (f"{preview._channel}-data", f"{preview._channel}-frame")
        return [channel for channel in channels if channel.startswith(reads)]

    # A row the plot draws, picked by hand: the hidden preview reads none of its values.
    pick_row(qtbot, viewer, BPM4I_VALUE)
    qtbot.wait(SELECT_DELAY_MS + 100)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    assert values_read() == []
    # Shown, the preview reads its dataset.
    pick_row(qtbot, viewer, CAMERA_VALUE)
    assert viewer.right_stack.currentWidget() is preview
    qtbot.waitUntil(lambda: values_read() != [])


def file_curve(viewer, path):
    """The curve of a dataset that is no signal for the selected scan, or None."""
    # pylint: disable=protected-access
    state = viewer._file_curves.get((viewer._entry.scan_id, path))
    return state.item if state is not None else None


def chip_of(box, key, letter="Y"):
    """The chip of a field with this key, or None."""
    return next((c for c in box.fields[letter].flow.chips if c.info.key == key), None)


def test_y_on_a_dataset_without_a_signal_draws_it_on_the_scans_plot(qtbot, viewer, history):
    # pylint: disable=protected-access
    signals, box = viewer.signal_list, viewer.file_box
    qtbot.waitUntil(lambda: bool(viewer._curves) and not viewer._lines_loading())
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    # A click on its row only selects it and shows its details, as for a signal.
    pick_row(qtbot, viewer, BPM4I_TIMESTAMP)
    qtbot.wait(SELECT_DELAY_MS + 50)
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    qtbot.waitUntil(lambda: viewer.details.topLevelItemCount() > 0)

    # Y on its row: one more curve of the scan's plot, after the signals in the colours.
    click_y(qtbot, viewer, BPM4I_TIMESTAMP)
    qtbot.waitUntil(lambda: file_curve(viewer, BPM4I_TIMESTAMP) is not None)
    curve = file_curve(viewer, BPM4I_TIMESTAMP)
    assert curve in viewer.waveform.curves and curve.config.source == "custom"
    assert curve.config.color == series_color(len(signals.y_signals()))
    # Read in full, against the x axis of the plot: samx, the scan's positioner.
    assert np.allclose(curve.xData, np.linspace(-1, 1, 20))
    assert np.allclose(curve.yData, np.arange(20))
    assert viewer.plot_stack.currentWidget() is viewer.waveform
    # Its chip sits in the one Y field of both tabs, with the path in its tooltip.
    key = DatasetKey(BPM4I_TIMESTAMP)
    for owner in (signals.box, box.box):
        chip = chip_of(owner, key)
        assert chip is not None and chip.info.label == "timestamp"
        assert chip.info.tip == BPM4I_TIMESTAMP and chip.info.problem == ""
        assert chip.info.swatch.color == curve.config.color
    assert field_chips(box.box) == field_chips(signals.box)
    # Its row is filled with the colour of its curve, as the rows of the signals.
    node = viewer.tree.current_node()
    assert viewer.tree.row_fill(node).name() == curve.config.color.lower()
    assert viewer.right_stack.currentWidget() is viewer.plot_page

    # Typing in Y in the File tab offers the datasets, those on the plot said as such.
    qtbot.waitUntil(lambda: box.role_listing("Y", "timest").entries[0].kind == "entry")
    listed = {e.key: e for e in box.role_listing("Y", "timest").entries if e.kind == "entry"}
    assert listed[("dataset", BPM4I_TIMESTAMP)].state == "on"
    assert listed[("dataset", BPM3A_TIMESTAMP)].state == ""
    box.take_role("Y", ("dataset", BPM3A_TIMESTAMP))
    qtbot.waitUntil(lambda: file_curve(viewer, BPM3A_TIMESTAMP) is not None)
    # Two of the same name: each named with its group, in the chips and the legend.
    labels = [label for _key, label, _tag in field_chips(signals.box)]
    assert labels[-2:] == ["bpm4i/timestamp", "bpm3a/timestamp"]

    # The x of its chip takes it off, in either tab; the other stays.
    viewer.signals_dock.setAsCurrentTab()
    chip = chip_of(signals.box, key)
    qtbot.mouseClick(chip.remove_button, Qt.MouseButton.LeftButton)
    assert chip_of(signals.box, key) is None and chip_of(signals.box, DatasetKey(BPM3A_TIMESTAMP))
    assert curve not in viewer.waveform.curves
    # Reset takes it off like any other.
    assert signals.reset_axes_button.isVisibleTo(signals.box)
    qtbot.mouseClick(signals.reset_axes_button, Qt.MouseButton.LeftButton)
    assert signals.dataset_chips() == () and viewer._file_curves == {}
    assert not any(c.config.source == "custom" for c in viewer.waveform.curves)
    assert signals.is_default() and not signals.reset_axes_button.isVisibleTo(signals.box)


def test_a_dataset_on_the_scans_plot_takes_its_x_axis_and_is_never_cut(
    qtbot, mocked_client, history
):
    # pylint: disable=protected-access
    trace = "/entry/extra/trace"
    with h5py.File(history[2].file_path, "a") as handle:
        handle[trace] = np.arange(50.0)
    settle(history[2].file_path)
    viewer = make_viewer(qtbot, mocked_client, history)
    signals = viewer.signal_list
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    click_y(qtbot, viewer, BPM4I_TIMESTAMP)
    click_y(qtbot, viewer, trace)
    qtbot.waitUntil(lambda: file_curve(viewer, BPM4I_TIMESTAMP) is not None)

    def problem(path):
        chip = chip_of(signals.box, DatasetKey(path))
        return chip.info.problem if chip is not None else None

    # 50 rows do not fit the 20 points of samx: not cut, its chip muted with the reason.
    qtbot.waitUntil(lambda: problem(trace) == "it has 50 rows, samx has 20 values")
    assert file_curve(viewer, trace) is None
    assert viewer.tree._kept[trace] == ""
    # Index fits everything.
    signals.toggle_x(INDEX_X)
    qtbot.waitUntil(lambda: file_curve(viewer, trace) is not None)
    assert problem(trace) == ""
    assert np.array_equal(file_curve(viewer, trace).xData, np.arange(50.0))
    # A signal as the x axis: its values, where the lengths fit.
    signals.toggle_x(BPM3A)
    qtbot.waitUntil(lambda: problem(trace) == "it has 50 rows, bpm3a has 20 values")
    curve = file_curve(viewer, BPM4I_TIMESTAMP)
    assert np.allclose(curve.xData, np.linspace(-1, 1, 20) + 2)
    # The timestamps of a timestamp: there are none next to it.
    signals.toggle_x(TIMESTAMP_X)
    qtbot.waitUntil(lambda: problem(BPM4I_TIMESTAMP) == "it has no timestamps next to it")
    assert file_curve(viewer, BPM4I_TIMESTAMP) is None


def test_a_dataset_on_the_scans_plot_is_read_from_the_file_of_each_scan(
    qtbot, mocked_client, history
):
    # pylint: disable=protected-access
    trace = "/entry/extra/trace"
    with h5py.File(history[2].file_path, "a") as handle:
        handle[trace] = np.arange(20.0) * 3
    settle(history[2].file_path)
    viewer = make_viewer(qtbot, mocked_client, history)
    signals = viewer.signal_list
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    click_y(qtbot, viewer, trace)
    click_y(qtbot, viewer, BPM4I_TIMESTAMP)
    qtbot.waitUntil(lambda: file_curve(viewer, trace) is not None)
    qtbot.waitUntil(lambda: file_curve(viewer, BPM4I_TIMESTAMP) is not None)

    # Another scan: the same paths, read from its file; one it does not have is muted.
    viewer.signals_dock.setAsCurrentTab()
    viewer.scan_list.select("scan-1")
    wait_for_switch(qtbot, viewer)
    qtbot.waitUntil(lambda: file_curve(viewer, BPM4I_TIMESTAMP) is not None)
    chip = chip_of(signals.box, DatasetKey(trace))
    qtbot.waitUntil(lambda: chip_of(signals.box, DatasetKey(trace)).info.problem != "")
    assert chip_of(signals.box, DatasetKey(trace)).info.problem == "not in this file"
    assert ("scan-1", BPM4I_TIMESTAMP) in viewer._file_curves

    # A pinned scan: drawn for each scan whose file has it, in that scan's shade.
    viewer.scan_list.model.toggle_pin("scan-2")
    qtbot.waitUntil(lambda: ("scan-2", trace) in viewer._file_curves)
    qtbot.waitUntil(lambda: viewer._file_curves[("scan-2", trace)].item is not None)
    ours = viewer._file_curves[("scan-1", BPM4I_TIMESTAMP)]
    theirs = viewer._file_curves[("scan-2", BPM4I_TIMESTAMP)]
    qtbot.waitUntil(lambda: ours.item is not None and theirs.item is not None)
    assert ours.color != theirs.color and ours.style == theirs.style != "solid"
    tip = chip_of(signals.box, DatasetKey(trace)).info.tip
    assert tip.splitlines() == [trace, "Drawn for scan 12"]
    assert chip.info.problem == "not in this file"


def test_a_dataset_longer_than_the_plot_reads_says_so_and_loads_on_request(
    qtbot, viewer, history, monkeypatch
):
    # pylint: disable=protected-access,import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer

    monkeypatch.setattr(hdf5_viewer, "COPY_MAX_POINTS", 10)
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: bool(viewer._curves) and not viewer._lines_loading())
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    click_y(qtbot, viewer, BPM4I_TIMESTAMP)
    key = DatasetKey(BPM4I_TIMESTAMP)
    # Not read: said on its chip and over the plot, with the two ways on.
    qtbot.waitUntil(lambda: chip_of(signals.box, key).info.problem != "")
    assert chip_of(signals.box, key).info.problem == (
        "not read: 20 rows, more than the 10 the plot reads by itself"
    )
    assert file_curve(viewer, BPM4I_TIMESTAMP) is None
    assert viewer.read_note.isVisibleTo(viewer)
    assert viewer.read_note_text.full_text() == (
        "timestamp has 20 rows, more than the 10 the plot reads by itself."
    )
    assert viewer.read_note_button.text() == "Load it"
    assert viewer.read_note_open.isVisibleTo(viewer)
    # "Add to plot" sends what is drawn.
    assert viewer.signal_offers()[0] == "Lines of bpm3a · scan 12"
    # The File tab's preview, whose overview is made for long data.
    qtbot.mouseClick(viewer.read_note_open, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: viewer.right_stack.currentWidget() is viewer.preview)
    qtbot.waitUntil(lambda: viewer.preview.view == "line")
    assert viewer.preview.node.path == BPM4I_TIMESTAMP
    # Back on the plot, loaded anyway.
    viewer.signals_dock.setAsCurrentTab()
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    qtbot.mouseClick(viewer.read_note_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: file_curve(viewer, BPM4I_TIMESTAMP) is not None)
    assert len(file_curve(viewer, BPM4I_TIMESTAMP).yData) == 20
    assert not viewer.read_note.isVisibleTo(viewer)
    assert chip_of(signals.box, key).info.problem == ""


def test_rows_without_a_signal_offer_no_y_on_a_map(qtbot, map_viewer):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    entry = viewer.scan_list.current_entry()
    file_tab_of_scan(qtbot, viewer, entry.file_path)
    tree = viewer.tree
    show_row(qtbot, viewer, BPM4I_TIMESTAMP)
    stamp = tree.node_at(tree_row(tree, BPM4I_TIMESTAMP))
    value = tree.node_at(tree_row(tree, BPM4I_VALUE))
    # A curve has no place on a map: only the signals have Y there.
    assert not tree.can_keep_row(stamp) and tree.can_keep_row(value)
    viewer.tree.keep_toggled.emit(stamp)
    assert viewer._file_paths == []  # pylint: disable=protected-access
    # In Lines it is a curve as in a line scan.
    viewer.view_switch.chosen.emit("lines")
    qtbot.waitUntil(lambda: tree.can_keep_row(stamp))
    click_y(qtbot, viewer, BPM4I_TIMESTAMP)
    qtbot.waitUntil(lambda: file_curve(viewer, BPM4I_TIMESTAMP) is not None)
    # Back on the map it waits, without a chip, and comes back with Lines.
    viewer.view_switch.chosen.emit("scatter")
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    assert viewer.signal_list.dataset_chips() == ()
    assert not any(c.config.source == "custom" for c in viewer.waveform.curves)
    viewer.view_switch.chosen.emit("lines")
    qtbot.waitUntil(lambda: file_curve(viewer, BPM4I_TIMESTAMP) is not None)


def test_another_file_than_the_scans_still_opens_in_the_preview(qtbot, viewer, tmp_path):
    path = tmp_path / "other.h5"
    with h5py.File(path, "w") as handle:
        handle["counts"] = np.arange(5.0)
    viewer.file_dock.setAsCurrentTab()
    viewer.open_file(str(path))
    qtbot.waitUntil(lambda: viewer.tree.file_path == str(path))
    assert viewer.right_stack.currentWidget() is viewer.preview


def test_viewer_waits_for_a_file_that_is_still_being_written(qtbot, viewer, history):
    os.utime(history[2].file_path, None)  # the writer just touched it
    viewer.file_dock.setAsCurrentTab()

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

    # Whether BEC wrote the file is read first, off the GUI thread.
    qtbot.waitUntil(viewer.file_tab_current)
    assert viewer.scan_list.current_entry() is None
    qtbot.waitUntil(
        lambda: viewer.preview.node is not None and viewer.preview.node.path == "/entry/name"
    )
    qtbot.waitUntil(lambda: viewer.preview.view == "value")
    assert viewer.status_label.full_text() == str(data_file)
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
    wait_for_switch(qtbot, viewer)
    assert [signal.group for signal in viewer.signal_list.signals()] == ["point", "point"]

    viewer.file_dock.setAsCurrentTab()
    # Its plot stays in the pane; over the empty tree the tab says why the file is not open.
    assert viewer.right_stack.currentWidget() is viewer.plot_page
    assert viewer.file_box.note.text().startswith("Scan 13 is still running")
    assert viewer.file_box.note.isVisibleTo(viewer.file_box)
    assert viewer.tree.model.rowCount() == 0
    # Its status names no file: the bar under the panes stays empty.
    assert viewer.status_label.full_text() == "" and viewer.status_note.text() == ""

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


def test_the_hint_beside_the_plot_title_is_shown_whole_or_not_at_all(qtbot, viewer):
    # pylint: disable=protected-access
    subtitle = viewer.plot_subtitle
    assert isinstance(subtitle, FactsLabel) and "to compare" in subtitle._hint
    label = FactsLabel()
    qtbot.addWidget(label)
    label.set_facts(subtitle._facts, subtitle._hint)
    label.show()
    qtbot.waitExposed(label)
    facts, hint = subtitle._facts, subtitle._hint
    assert label.full_text() == f"{facts}{FactsLabel.SEPARATOR}{hint}"
    metrics = label.fontMetrics()
    whole = metrics.horizontalAdvance(label.full_text())
    label.resize(whole + 2, label.height())
    assert label.shown_text() == label.full_text() and label.toolTip() == ""
    # A pixel short: the hint is left out, not cut; the tooltip has it.
    label.resize(whole - 1, label.height())
    assert label.shown_text() == facts and label.toolTip() == label.full_text()
    # Narrower than the facts: they are cut as before, still without the hint.
    label.resize(metrics.horizontalAdvance(facts) // 2, label.height())
    assert label.shown_text().endswith("…") and hint[:4] not in label.shown_text()
    # A line without a hint is cut as before.
    label.setText("a very long line about the scan " * 10)
    assert label.shown_text().endswith("…")


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


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_signal_list_follows_the_theme_and_its_lists_stay_readable(qtbot, history, theme):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.utils.theme_utils import theme_colors

    signals = box_list(qtbot, history)
    apply_theme(theme)
    try:
        # The list is no BEC widget and is told of the theme all the same.
        assert signals.row_colors()[1] == theme_colors()["fg"]
        edit = focus_field(qtbot, signals, "X")
        qtbot.keyClicks(edit, "m")
        colors = signals.typing.list.delegate.colors
        assert colors["card"].alpha() == 255
        assert contrast(colors["muted"], colors["card"]) >= 4.5
        assert contrast(colors["fg"], colors["mark"]) >= 4.5
        assert contrast(colors["primary"], colors["card"]) >= 3
    finally:
        apply_theme("light")


def test_scan_status_words_and_tones_are_the_ones_of_the_scan_queue():
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.bec_queue.queue_model import HISTORY_STATUS
    from bec_widgets.widgets.services.hdf5_viewer.scan_list import scan_status

    for status in ("closed", "aborted", "halted", "user_completed"):
        assert scan_status(ScanEntry(scan_id="s", status=status)) == HISTORY_STATUS[status]
    assert scan_status(ScanEntry(scan_id="s", status="open", live=True))[2] == "Running"


def test_curves_keep_the_colours_of_the_scan_list_after_a_theme_change(qtbot, viewer):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.utils.colors import apply_theme

    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    curve = next(iter(viewer._curves.values()))[0]
    try:
        apply_theme("dark")
        qtbot.waitUntil(lambda: curve.config.color == series_color(0))
        assert viewer.signal_list.signal_color(("bpm3a", "bpm3a")) == series_color(0)
    finally:
        apply_theme("light")


def test_viewer_does_not_grow_wider_because_of_long_lines(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    viewer.plot_subtitle.setText("a very long line about the scan " * 10)
    viewer.status_label.setText("a very long status line " * 10)
    # The lines are cut to the room they get and say the rest in their tooltip.
    assert viewer.right_stack.parentWidget().minimumSizeHint().width() < 400
    assert viewer.minimumSizeHint().width() < 1000
    viewer.resize(900, 600)
    qtbot.waitUntil(lambda: viewer.plot_subtitle.toolTip() != "")


def test_the_path_in_the_footer_is_cut_in_its_middle_and_copied_whole(qtbot):
    label = PathLabel()
    qtbot.addWidget(label)
    label.show()
    path = "/sls/x01da/data/p12345/raw/2026/scans/S00000-00999/S00007/S00007_master.h5"
    label.setText(path)
    assert label.toolTip() == path and label.full_text() == path
    label.resize(label.fontMetrics().horizontalAdvance(path) // 2, label.height())
    shown = label.text()
    # The start and the file name stay; the middle is cut.
    assert "…" in shown and shown.endswith("_master.h5") and shown.startswith("/sls")
    # A selection over the cut copies what was cut too; one beside it copies what it shows.
    label.setSelection(0, len(shown))
    assert label.selected_path_text() == path
    label.setSelection(len(shown) - 3, 3)
    assert label.selected_path_text() == ".h5"
    label.setFocus()
    qtbot.keyClick(label, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text() == ".h5"
    label.setSelection(0, len(shown))
    qtbot.keyClick(label, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text() == path


def test_tree_leaves_out_the_type_while_a_name_in_view_would_be_cut(qtbot, service, tmp_path):
    path = tmp_path / "deep.h5"
    with h5py.File(path, "w") as handle:
        handle[
            "entry/collection/configuration/samx/samx_acceleration_of_the_motor_in_the_optics_hutch"
        ] = [1.0]
    settle(path)
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.resize(900, 400)
    tree.show()
    tree.set_file(str(path), select_path="/entry/collection/configuration/samx")
    qtbot.waitUntil(lambda: tree.current_node() is not None)
    qtbot.waitUntil(lambda: not tree.view.isColumnHidden(2))

    tree.resize(420, 400)
    qtbot.waitUntil(lambda: tree.view.isColumnHidden(2))
    tree.resize(900, 400)
    qtbot.waitUntil(lambda: not tree.view.isColumnHidden(2))
    tree.cleanup()


def test_tree_leaves_out_the_shape_after_the_type_while_names_get_too_little_room(
    qtbot, service, tmp_path
):
    path = tmp_path / "deep_signal.h5"
    with h5py.File(path, "w") as handle:
        handle["entry/collection/devices/samx/samx/value"] = [1.0, 2.0]
        handle["entry/collection/devices/samx/samx/timestamp"] = [1.0, 2.0]
    settle(path)
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.resize(900, 400)
    tree.show()
    tree.set_file(str(path), select_path="/entry/collection/devices/samx/samx/timestamp")
    qtbot.waitUntil(lambda: tree.current_node() is not None)
    view = tree.view
    qtbot.waitUntil(lambda: not view.isColumnHidden(2) and not view.isColumnHidden(1))

    # Narrow: the type goes first, the shape stays while the names fit beside it.
    tree.resize(300, 400)
    qtbot.waitUntil(lambda: view.isColumnHidden(2))
    assert not view.isColumnHidden(1)
    # Narrower: "timestamp" would keep a few letters, the shape goes too; the buttons stay.
    tree.resize(260, 400)
    qtbot.waitUntil(lambda: view.isColumnHidden(1))
    assert not view.isColumnHidden(Y_COLUMN)
    # Wide again: both come back.
    tree.resize(900, 400)
    qtbot.waitUntil(lambda: not view.isColumnHidden(1) and not view.isColumnHidden(2))
    tree.cleanup()


def test_tree_goes_on_along_the_last_path_while_another_row_opens(qtbot, service, tmp_path):
    path = tmp_path / "two_signals.h5"
    with h5py.File(path, "w") as handle:
        for device in ("samx", "samy"):
            handle[f"entry/collection/devices/{device}/{device}/value"] = [1.0, 2.0]
    settle(path)
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.resize(600, 400)
    tree.show()
    samx = "/entry/collection/devices/samx/samx/value"
    samy = "/entry/collection/devices/samy/samy/value"
    tree.set_file(str(path), select_path=samx)
    qtbot.waitUntil(lambda: tree.current_node() is not None and tree.current_node().path == samx)
    samx_group = tree.view.currentIndex().parent()
    tree.view.collapse(samx_group)

    # On the way to samy, whose group is still to be read, a row that is read already opens,
    # here by hand; it does not end the way to samy.
    tree.select_path(samy)
    tree.view.expand(samx_group)
    qtbot.waitUntil(lambda: tree.current_node() is not None and tree.current_node().path == samy)
    tree.cleanup()


def short_forms(monkeypatch, viewer) -> list[str]:
    """The short forms the viewer gives its buttons along with each message, as said."""
    said = []
    say_on = viewer._say_on

    def record(button, timer, text, width, short=""):
        said.append(short)
        say_on(button, timer, text, width, short)

    monkeypatch.setattr(viewer, "_say_on", record)
    return said


def menu_texts(menu):
    return [action.text() for action in menu.actions() if not action.isSeparator()]


def test_add_to_plot_adds_the_viewer_curves_to_another_plot_as_history_curves(
    qtbot, viewer, mocked_client
):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.plots.waveform.waveform import Waveform
    from bec_widgets.widgets.services.hdf5_viewer.plot_targets import other_plots

    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    target = create_widget(qtbot, Waveform, client=mocked_client)
    target.setObjectName("TargetPlot")

    plots = other_plots(viewer)
    # The plots of the viewer itself are not offered.
    assert [plot for _name, plot in plots] == [target]
    viewer._fill_add_menu()
    # What is sent first, then the open plots with what happens to each.
    assert menu_texts(viewer.add_menu) == [
        "Lines of bpm3a · scan 12",
        "Plots that are open",
        "TargetPlot\tadds 1 curve",
    ]

    result = viewer.add_to_plot(target, "TargetPlot")

    assert result.added == 1
    [curve] = target.curves
    assert curve.config.source == "history" and curve.config.scan_id == "scan-2"
    assert curve.name() == "bpm3a-bpm3a-scan-12"
    assert viewer.add_button.text() == "Added 1 curve to TargetPlot"

    again = viewer.add_to_plot(target, "TargetPlot")
    assert again.added == 0 and len(target.curves) == 1
    assert viewer.add_button.text() == "Already on TargetPlot"
    qtbot.waitUntil(lambda: viewer.add_button.text() == "Add to plot", timeout=5000)


def test_add_to_plot_says_when_there_is_nowhere_to_add(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    viewer._fill_add_menu()
    line = viewer.add_menu.actions()[-1]
    assert not line.isEnabled() and line.text() == "No other plot is open"


def test_overlay_adds_a_scan_with_the_signals_the_other_plot_shows(qtbot, viewer, mocked_client):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.plots.waveform.waveform import Waveform
    from bec_widgets.widgets.services.hdf5_viewer.plot_targets import held_history_curves

    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    target = create_widget(qtbot, Waveform, client=mocked_client)
    target.setObjectName("TargetPlot")
    target.plot(device_y="bpm4i", signal_y="bpm4i")
    oldest = viewer.scan_list.model.entry("scan-0")

    menu = viewer.scan_menu(oldest)
    assert [action.text() for action in menu.actions()] == ["Overlay on"]
    assert menu_texts(menu.overlay_menu) == ["TargetPlot"]
    menu.deleteLater()

    text = viewer.overlay_scan(oldest, target, "TargetPlot")

    assert ("scan-0", "bpm4i", "bpm4i") in held_history_curves(target)
    assert text == "Added 1 curve to TargetPlot"
    assert viewer.scan_list.note.text() == text
    qtbot.waitUntil(lambda: viewer.scan_list.note.text() == "3 scans", timeout=5000)


def test_tree_pause_cuts_off_a_listing_and_resume_reads_it_again(qtbot, service, data_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.set_file(str(data_file), select_path="/entry")
    root = tree.model.item(0)
    qtbot.waitUntil(lambda: child_names(root) == ["entry"])
    entry = root.child(0)
    qtbot.waitUntil(lambda: "plot" in child_names(entry))
    plot = entry.child(child_names(entry).index("plot"))

    with qtbot.waitSignal(service.busy_changed, timeout=1000, raising=False):
        tree.view.expand(plot.index())
        tree.pause()
    assert not service.has_pending()
    assert plot.data(STATE_ROLE) == "unloaded"

    tree.resume()
    qtbot.waitUntil(lambda: child_names(plot) == ["counts", "energy"])
    tree.cleanup()


@pytest.fixture
def twin_viewer(qtbot, mocked_client, tmp_path):
    """The viewer on a history in which the oldest and the newest scan are both numbered 12."""
    history = make_history(tmp_path, (12, 11, 12))
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in history:
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    widget = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    widget.resize(1200, 700)
    qtbot.waitUntil(lambda: widget.scan_list.model.rowCount() == 3)
    wait_for_switch(qtbot, widget)  # the newest scan is shown
    return widget


def test_scans_that_share_a_number_are_listed_and_told_apart(qtbot, twin_viewer):
    model = twin_viewer.scan_list.model
    old, middle, new = (model.entry(f"scan-{index}") for index in range(3))
    assert model.is_repeated(old) and model.is_repeated(new) and not model.is_repeated(middle)
    assert model.scan_label(middle) == "11"
    assert model.scan_label(old).startswith("12 (") and model.scan_label(new).startswith("12 (")
    assert model.scan_label(old) != model.scan_label(new)
    row = next(r for r in range(model.rowCount()) if model.entries()[r].scan_id == "scan-0")
    assert "Scan id scan-0" in model.data(model.index(row), Qt.ItemDataRole.ToolTipRole)

    # A number picks its newest scan; a scan id picks exactly that one.
    twin_viewer.show_scan(12)
    assert twin_viewer.scan_list.current_entry().scan_id == "scan-2"
    twin_viewer.show_scan("scan-0")
    assert twin_viewer.scan_list.current_entry().scan_id == "scan-0"


def test_scans_that_share_a_number_are_compared_on_one_plot(qtbot, twin_viewer):
    qtbot.waitUntil(lambda: len(twin_viewer._curves) == 1)
    twin_viewer.scan_list.model.toggle_pin("scan-0")

    assert set(twin_viewer._curves) == {("scan-2", "bpm3a", "bpm3a"), ("scan-0", "bpm3a", "bpm3a")}
    names = {key[0]: curve.name() for key, (curve, _live) in twin_viewer._curves.items()}
    assert names["scan-2"] == "bpm3a-bpm3a-scan-12"
    assert names["scan-0"].startswith("bpm3a-bpm3a-scan-12-")
    label = twin_viewer.scan_list.model.scan_label(twin_viewer.scan_list.model.entry("scan-0"))
    assert f"compared with {label}" in twin_viewer.plot_subtitle.full_text()
    assert twin_viewer.plot_title.text().startswith("Scan 12 (")


def test_add_to_plot_tells_scans_that_share_a_number_apart(qtbot, twin_viewer, mocked_client):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.plots.waveform.waveform import Waveform
    from bec_widgets.widgets.services.hdf5_viewer.plot_targets import held_history_curves

    qtbot.waitUntil(lambda: len(twin_viewer._curves) == 1)
    target = create_widget(qtbot, Waveform, client=mocked_client)
    target.setObjectName("TargetPlot")
    first = twin_viewer.add_to_plot(target, "TargetPlot")
    assert first.added == 1

    # The other scan 12 is not "already there" just because its number is.
    twin_viewer.scan_list.model.toggle_pin("scan-0")
    second = twin_viewer.add_to_plot(target, "TargetPlot")
    assert (second.added, second.already) == (1, 1)
    assert held_history_curves(target) == {
        ("scan-2", "bpm3a", "bpm3a"),
        ("scan-0", "bpm3a", "bpm3a"),
    }
    assert twin_viewer.add_to_plot(target, "TargetPlot").already == 2


def test_history_picker_follows_the_scan_id_not_the_number(qtbot, twin_viewer, mocked_client):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.plots.waveform.waveform import Waveform
    from bec_widgets.widgets.services.hdf5_viewer.history_picker import HistoryPicker

    target = create_widget(qtbot, Waveform, client=mocked_client)
    target.plot(device_y="bpm3a", signal_y="bpm3a", scan_id="scan-2")
    picker = HistoryPicker(target)
    qtbot.addWidget(picker)
    qtbot.waitUntil(lambda: picker.scan_list.model.rowCount() == 3)

    assert picker.scan_list.select("scan-0")
    assert picker.signal_list.y_signals() == []
    assert picker.scan_list.select("scan-2")
    assert picker.signal_list.y_signals() == [("bpm3a", "bpm3a")]
    picker.cleanup()


@pytest.mark.parametrize("platform, key", [("linux", "Ctrl"), ("darwin", "⌘")])
def test_compare_hint_names_the_key_of_the_platform(qtbot, viewer, monkeypatch, platform, key):
    # Qt reports Ctrl on Linux and Cmd on macOS as the same ControlModifier, so the click works
    # on both; only the hint names the key a person presses there.
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    monkeypatch.setattr("sys.platform", platform)
    viewer._refresh_plot()
    assert f"pin another scan or {key}-click it to compare" in viewer.plot_subtitle.full_text()


@pytest.mark.parametrize("platform, key", [("linux", "Ctrl"), ("darwin", "⌘")])
def test_control_key_is_named_as_on_the_platform(monkeypatch, platform, key):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.style import control_key_name

    monkeypatch.setattr("sys.platform", platform)
    assert control_key_name() == key


@pytest.mark.parametrize(
    "count, english, german",
    [(999, "999", "999"), (1000, "1,000", "1.000"), (5213, "5,213", "5.213")],
)
def test_counts_read_with_the_group_separator_of_the_locale(count, english, german):
    # pylint: disable=import-outside-toplevel
    from qtpy.QtCore import QLocale

    from bec_widgets.widgets.services.hdf5_viewer.style import count_text

    english_locale = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
    german_locale = QLocale(QLocale.Language.German, QLocale.Country.Germany)
    assert count_text(count, english_locale) == english
    assert count_text(count, german_locale) == german


def show_dataset(qtbot, viewer, file_path, dataset):
    viewer.open_file(str(file_path), dataset)
    qtbot.waitUntil(
        lambda: viewer.preview.line_source() is not None
        and viewer.preview.line_source().node.path == dataset,
        timeout=5000,
    )


def no_curves(viewer):
    """Take every signal off the scan's plot; the File tab's own plot keeps nothing either."""
    viewer.signal_list.set_curves([])
    assert viewer.preview.kept_paths() == []


def file_target(qtbot, mocked_client):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.plots.waveform.waveform import Waveform

    target = create_widget(qtbot, Waveform, client=mocked_client)
    target.setObjectName("TargetPlot")
    return target


def test_file_tab_adds_a_signal_dataset_as_the_same_history_curve(qtbot, viewer, mocked_client):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.plot_targets import held_history_curves

    target = file_target(qtbot, mocked_client)
    scan = viewer.scan_list.model.entry("scan-2")
    show_dataset(qtbot, viewer, scan.file_path, "/entry/collection/devices/bpm4i/bpm4i/value")
    no_curves(viewer)

    assert viewer.file_history_source() == ("scan-2", "bpm4i", "bpm4i")
    assert not viewer.file_add_button.isHidden()
    assert viewer.file_add_button.toolTip() == "Adds bpm4i of scan 12 to another plot"
    result = viewer.add_file_to_plot(target, "TargetPlot")
    assert result.added == 1
    assert held_history_curves(target) == {("scan-2", "bpm4i", "bpm4i")}
    # Named exactly as from the Signals tab.
    assert [curve.name() for curve in target.curves] == ["bpm4i-bpm4i-scan-12"]
    assert viewer.add_file_to_plot(target, "TargetPlot").already == 1
    assert viewer.file_add_button.property("feedback") == "Already on TargetPlot"


def test_file_tab_finds_the_signal_through_the_readout_group_link(qtbot, viewer):
    scan = viewer.scan_list.model.entry("scan-1")
    show_dataset(
        qtbot,
        viewer,
        scan.file_path,
        "/entry/collection/readout_groups/monitored/bpm4i/bpm4i/value",
    )
    assert viewer.file_history_source() == ("scan-1", "bpm4i", "bpm4i")


def test_file_tab_copies_the_timestamp_and_says_it_is_a_copy(qtbot, viewer, mocked_client):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.hdf5_viewer import COPY_TOOLTIP

    target = file_target(qtbot, mocked_client)
    scan = viewer.scan_list.model.entry("scan-2")
    dataset = "/entry/collection/devices/bpm4i/bpm4i/timestamp"
    show_dataset(qtbot, viewer, scan.file_path, dataset)
    no_curves(viewer)

    # Only the value dataset is the signal; its timestamp is a copy.
    assert viewer.file_history_source() is None
    assert viewer.file_add_button.toolTip() == COPY_TOOLTIP
    viewer.add_file_to_plot(target, "TargetPlot")
    label = f"S00012_master.h5 {dataset}"
    qtbot.waitUntil(lambda: [curve.name() for curve in target.curves] == [label])
    [curve] = target.curves
    assert curve.config.source == "custom"
    x, y = curve.getData()
    assert len(y) == 20 and list(x) == list(range(20))
    assert (
        viewer.file_add_button.property("feedback")
        == "Copied to TargetPlot, not saved with the workspace"
    )

    viewer.add_file_to_plot(target, "TargetPlot")
    assert viewer.file_add_button.property("feedback") == "Already on TargetPlot"
    assert len(target.curves) == 1


def test_file_tab_copies_a_dataset_of_a_file_outside_the_history_at_full_length(
    qtbot, viewer, mocked_client, data_file
):
    target = file_target(qtbot, mocked_client)
    show_dataset(qtbot, viewer, data_file, "/entry/plot/counts")

    assert viewer.file_history_source() is None
    viewer.add_file_to_plot(target, "TargetPlot")
    qtbot.waitUntil(lambda: len(target.curves) == 1, timeout=10000)
    # All rows, not the reduced overview of the preview.
    assert len(target.curves[0].getData()[1]) == ROWS


def test_file_tab_does_not_copy_more_rows_than_the_cap(qtbot, viewer, data_file, monkeypatch):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer

    monkeypatch.setattr(hdf5_viewer, "COPY_MAX_POINTS", 1000)
    show_dataset(qtbot, viewer, data_file, "/entry/plot/counts")

    header, offers = viewer.file_offers()
    assert offers["Waveform"] == f"too many rows to copy: {ROWS:,}"
    assert header == "Show the dataset as a line, map or image first"


def test_file_tab_does_not_copy_a_file_that_is_being_written(
    qtbot, viewer, mocked_client, data_file
):
    target = file_target(qtbot, mocked_client)
    show_dataset(qtbot, viewer, data_file, "/entry/plot/energy")

    os.utime(data_file, None)  # written just now
    viewer.add_file_to_plot(target, "TargetPlot")

    qtbot.waitUntil(
        lambda: viewer.file_add_button.property("feedback").startswith("Could not copy")
    )
    assert target.curves == []
    assert viewer.file_add_button.isEnabled()


def test_file_tab_shows_no_add_button_for_tables(qtbot, viewer, data_file):
    show_dataset(qtbot, viewer, data_file, "/entry/plot/counts")
    assert not viewer.file_add_button.isHidden()
    viewer.preview.view_buttons["table"].click()
    qtbot.waitUntil(lambda: viewer.file_add_button.isHidden())


WAVE, SAMX, BPM = ("wave", "wave"), ("samx", "samx"), ("bpm3a", "bpm3a")


def plot_state(viewer):
    waveform = viewer.waveform
    return waveform.x_mode, waveform.x_axis_mode["entry"], viewer.signal_list.note.text()


def test_x_axis_stays_in_step_with_the_x_choice_through_fast_and_point_signals(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    signals = viewer.signal_list
    assert signals.group_of(WAVE) == "fast"

    signals.toggle_y(WAVE)  # a fast signal alone: against its sample number
    assert plot_state(viewer)[:2] == ("index", None)
    assert box_text(signals) == "X: sample number auto | Y: wave"

    signals.toggle_x(SAMX)  # samx cannot be its x: refused, said, the plot keeps its curve
    assert signals.x_signal() is None and signals.y_signals() == [WAVE]
    assert "can only be the x axis of monitored signals" in signals.note.text()
    assert plot_state(viewer)[:2] == ("index", None)
    assert set(viewer._curves) == {("scan-2", "wave", "wave")}

    signals.toggle_y(BPM)  # a point signal takes over the plot
    signals.toggle_x(SAMX)
    assert plot_state(viewer)[:2] == ("samx", "samx")
    # X on the scan's own positioner keeps it the scan's choice.
    assert box_text(signals) == "X: samx auto | Y: bpm3a"

    signals.toggle_x(SAMX)  # off again: the scan's positioner, which is samx here
    assert plot_state(viewer)[:2] == ("samx", "samx")
    assert box_text(signals) == "X: samx auto | Y: bpm3a"
    signals.toggle_y(WAVE)
    assert plot_state(viewer)[:2] == ("index", None)
    assert box_text(signals) == "X: sample number auto | Y: wave"


def test_every_curve_has_points_and_the_view_covers_them_after_a_zoom(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    viewer.scan_list.model.toggle_pin("scan-0")
    viewer.signal_list.toggle_y(WAVE)
    curves = [curve for curve, _live in viewer._curves.values()]
    qtbot.waitUntil(lambda: all(c.yData is not None and len(c.yData) == 1000 for c in curves))

    viewer.waveform.plot_item.vb.setXRange(100, 200, padding=0)
    viewer.signal_list.toggle_y(SAMX)  # another curve set ...
    viewer.signal_list.toggle_y(WAVE)  # ... and back: the view shows all of it again

    curves = [curve for curve, _live in viewer._curves.values()]
    qtbot.waitUntil(lambda: all(c.yData is not None and len(c.yData) == 1000 for c in curves))

    def covered():
        (x0, x1), _ = viewer.waveform.plot_item.vb.viewRange()
        return x0 <= 0 and x1 >= 999

    qtbot.waitUntil(covered)
    assert not viewer.plot_subtitle.full_text().startswith("Nothing to draw")


def test_viewer_names_a_curve_that_has_nothing_to_draw(qtbot, viewer):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    [curve] = [curve for curve, _live in viewer._curves.values()]
    qtbot.waitUntil(lambda: curve.yData is not None and len(curve.yData) > 0)
    curve.setVisible(False)  # e.g. the plot hid it: its x does not fit

    viewer._check_empty_curves()

    assert viewer.plot_subtitle.full_text().startswith("Nothing to draw for bpm3a of scan 12")


################################################################################
# Maps of scans that moved two motors
################################################################################


def make_map_history(tmp_path, diagonal: bool = False, plugin: bool = False):
    """
    A line scan, a grid scan and a fermat scan of samx and samy, the fermat newest; with
    diagonal, a line scan that moved samx and samy together comes after them as scan 33.
    With plugin, a raster of samx and samy by a scan of a beamline plugin comes last.
    """
    out = []
    start = time.time() - 7200
    info = messages._StoredDataInfo  # pylint: disable=protected-access
    scans = [
        ("line_scan", {"arg_bundle": ["samx", -1, 1], "kwargs": {"steps": 16}}, ("samx",)),
        (
            "grid_scan",
            {"arg_bundle": ["samx", -1, 1, 4, "samy", -1, 1, 4], "kwargs": {"snaked": False}},
            ("samx", "samy"),
        ),
        (
            "fermat_scan",
            {"arg_bundle": [], "inputs": {"motor1": "samx", "motor2": "samy", "step": 0.5}},
            ("samx", "samy"),
        ),
    ]
    if diagonal:
        scans.append(
            (
                "line_scan",
                {"arg_bundle": ["samx", -1, 1, "samy", -1, 1], "kwargs": {"steps": 16}},
                ("samx", "samy"),
            )
        )
    if plugin:
        scans.append(
            (
                "beamline_raster_scan",
                {"arg_bundle": ["samx", -1, 1, "samy", -1, 1], "kwargs": {"steps": 4}},
                ("samx", "samy"),
            )
        )
    for index, (name, inputs, motors) in enumerate(scans):
        points = 16
        x = np.repeat(np.linspace(-1, 1, 4), 4)
        y = np.tile(np.linspace(-1, 1, 4), 4)
        if name == "line_scan" and len(motors) == 2:
            # Both motors move together, with a little readback noise across the path.
            x = np.linspace(-1, 1, points)
            y = x + np.where(np.arange(points) % 2, 1e-3, -1e-3)
        monitored = {
            motor: {motor: {"value": value, "timestamp": np.arange(points)}}
            for motor, value in zip(motors, (x, y))
        }
        monitored["bpm3a"] = {"bpm3a": {"value": x + y, "timestamp": np.arange(points)}}
        monitored["bpm4i"] = {"bpm4i": {"value": x * y, "timestamp": np.arange(points)}}
        data = {
            "monitored": monitored,
            "async": {
                "wave": {"wave": {"value": np.arange(points * 10.0), "timestamp": np.arange(16)}}
            },
        }
        stored = {device: {device: info(shape=(points,), dtype="float64")} for device in monitored}
        stored["wave"] = {"wave": info(shape=(points * 10,), dtype="float64")}
        metadata = {
            "scan_id": f"map-{index}",
            "scan_name": name,
            "scan_type": "step",
            "status": "closed",
            "scan_number": 30 + index,
            "dataset_number": 1,
            # The file helper writes one level of nested inputs; the message gets them all below.
            "request_inputs": {
                "arg_bundle": inputs["arg_bundle"],
                "kwargs": inputs.get("kwargs") or {"relative": False},
            },
            "num_points": points,
            "stored_data_info": stored,
            "scan_report_devices": [motor.encode() for motor in motors],
        }
        file_path = str(tmp_path / f"S{30 + index:05d}_master.h5")
        msg = create_history_file(file_path, data, metadata)
        dump = msg.model_dump() | {
            "request_inputs": inputs,
            "exit_status": "closed",
            "start_time": start + 600 * index,
            "end_time": start + 600 * index + 30,
        }
        out.append(messages.ScanHistoryMessage.model_validate(dump))
        settle(file_path)
    return out


@pytest.fixture
def map_viewer(qtbot, mocked_client, tmp_path):
    """The viewer on a history of a line scan, a grid scan and a fermat scan (selected)."""
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in make_map_history(tmp_path):
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    widget = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    widget.resize(1200, 700)
    qtbot.waitUntil(lambda: widget.scan_list.model.rowCount() == 3)
    wait_for_switch(qtbot, widget)  # the newest scan is shown
    return widget


BPM3A = ("bpm3a", "bpm3a")
BPM4I = ("bpm4i", "bpm4i")


def test_scans_of_two_stored_motors_are_maps():
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.map_view import (
        default_view,
        is_area_scan,
        is_two_dimensional,
        map_axes,
    )

    stored = {name: {name: {}} for name in ("samx", "samy")}
    grid = ScanEntry(scan_id="g", scan_name="grid_scan", motors=("samx", "samy"))
    grid.stored_data_info = stored
    fermat = ScanEntry(scan_id="f", scan_name="fermat_scan", motors=("samx", "samy"))
    fermat.stored_data_info = stored
    line = ScanEntry(scan_id="l", scan_name="line_scan", motors=("samx",))
    line.stored_data_info = stored
    unstored = ScanEntry(scan_id="u", scan_name="grid_scan", motors=("samx", "samz"))
    unstored.stored_data_info = stored
    # Two motors moved together along one path, and a raster of a beamline plugin: maps too,
    # but they open as lines against their first motor.
    diagonal = ScanEntry(scan_id="d", scan_name="line_scan", motors=("samx", "samy"))
    diagonal.stored_data_info = stored
    plugin = ScanEntry(scan_id="p", scan_name="beamline_raster_scan", motors=("samx", "samy"))
    plugin.stored_data_info = stored

    assert map_axes(grid) == (("samx", "samx"), ("samy", "samy"))
    assert default_view(grid) == "heatmap"
    assert default_view(fermat) == "scatter"
    assert map_axes(line) is None and default_view(line) == "lines"
    assert map_axes(unstored) is None and default_view(unstored) == "lines"
    assert map_axes(None) is None
    assert is_two_dimensional(grid) and is_two_dimensional(fermat)
    assert not is_two_dimensional(line) and not is_area_scan(line)
    for entry in (diagonal, plugin):
        assert is_two_dimensional(entry) and not is_area_scan(entry)
        assert map_axes(entry) == (("samx", "samx"), ("samy", "samy"))
        assert default_view(entry) == "lines"


def test_points_lie_on_one_line_when_the_cloud_is_thin_across_its_length():
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.map_view import points_on_one_line

    path = np.linspace(-1, 1, 50)
    assert points_on_one_line(path, 3 * path + 5)  # two motors together, any scale
    assert points_on_one_line(path, path + np.where(np.arange(50) % 2, 0.01, -0.01))  # 1 %
    assert points_on_one_line(path, np.full(50, 2.0))  # one motor did not move
    assert points_on_one_line([0, 1], [0, 1])  # too few points to fill anything
    assert not points_on_one_line(path, path + np.where(np.arange(50) % 2, 0.05, -0.05))
    assert not points_on_one_line(np.repeat(path[:5], 5), np.tile(path[:5], 5))  # a grid
    # A raster of two lines is an area, however narrow, once each motor has its own scale.
    assert not points_on_one_line(np.tile(path, 2), np.repeat([0.0, 1e-3], 50))


def test_a_scan_of_two_motors_opens_as_a_map_of_its_default_signal(qtbot, map_viewer):
    viewer = map_viewer
    # The newest scan is the fermat: a scatter, coloured by the first signal per point.
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    assert viewer.view_switch.isVisibleTo(viewer) and viewer.current_view() == "scatter"
    assert viewer.view_switch.current() == "scatter"
    assert viewer.signal_list.y_signals() == [BPM3A]
    assert box_text(viewer.signal_list) == "X: samx auto | Y: samy auto | Z: bpm3a auto"
    captions = {k: f.role.caption for k, f in viewer.signal_list.box.fields.items()}
    assert captions == {"X": "x axis", "Y": "y axis", "Z": "colour"}
    assert not viewer._curves
    scatter = viewer.maps.scatter
    assert (scatter.device_x, scatter.device_y, scatter.device_z) == ("samx", "samy", "bpm3a")
    # One curve, named in the signal list: no legend over the points, no path between them.
    assert not scatter.plot_item.legend.isVisible()
    assert scatter.main_curve.opts["pen"].style() == Qt.PenStyle.NoPen

    # The grid opens as a heatmap of the same motors.
    viewer.show_scan(31)
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.heatmap)
    assert viewer.current_view() == "heatmap"
    heatmap = viewer.maps.heatmap
    assert (heatmap.device_x, heatmap.device_y, heatmap.device_z) == ("samx", "samy", "bpm3a")
    assert heatmap._history_scan_id == "map-1"  # pylint: disable=protected-access

    # A line scan has lines and no switch.
    viewer.show_scan(30)
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform)
    assert len(viewer._curves) == 1
    assert not viewer.view_switch.isVisibleTo(viewer)


def test_the_view_switch_keeps_the_choice_per_kind_of_scan(qtbot, map_viewer):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    viewer.view_switch.buttons["heatmap"].click()
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.heatmap)
    assert viewer.view_switch.current() == "heatmap"

    # The grid keeps its own default; the fermat comes back as the user left it.
    viewer.show_scan(31)
    assert viewer.current_view() == "heatmap"
    viewer.view_switch.buttons["lines"].click()
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform)
    assert set(viewer._curves) == {("map-1", "bpm3a", "bpm3a")}
    assert viewer.waveform.x_mode == "samx"
    assert box_text(viewer.signal_list) == "X: samx auto | Y: bpm3a auto | Z:"
    assert viewer.signal_list.box.fields["Z"].edit.placeholderText() == "Not used in Lines"

    viewer.show_scan(32)
    assert viewer.current_view() == "heatmap"


def test_a_map_has_one_colour_and_says_what_it_refuses(qtbot, map_viewer):
    viewer = map_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)

    # A new Z replaces the colour.
    signals.press("Z", BPM4I)
    assert signals.y_signals() == [BPM4I]
    assert box_text(signals) == "X: samx auto | Y: samy auto | Z: bpm4i"
    qtbot.waitUntil(lambda: viewer.maps.scatter.device_z == "bpm4i")

    # A fast signal cannot colour a point, and the colour cannot be an axis too.
    signals.press("Z", ("wave", "wave"))
    assert signals.y_signals() == [BPM4I]
    assert "Switch to Lines to plot it" in signals.note.text()
    signals.press("X", BPM4I)
    assert signals.plane_axes() == (("samx", "samx"), ("samy", "samy"))
    assert "bpm4i is the colour of the map" in signals.note.text()

    # No colour: the map says how to get one.
    signals.toggle_y(BPM4I)
    assert viewer.plot_stack.currentWidget() is viewer.plot_state
    assert viewer.plot_state.title.text() == "Nothing on the map"


def test_lines_with_several_signals_become_a_map_of_the_first(qtbot, map_viewer):
    viewer = map_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    viewer.view_switch.buttons["lines"].click()
    # In Lines the rows offer X and Y: Y adds a curve, X swaps the axes of the map.
    assert signals._delegate.letters(signals._signals[BPM4I]) == ["X", "Y"]
    signals.press("Y", BPM4I)
    signals.press("X", ("samy", "samy"))  # samy takes the place of samx, which goes to y
    signals.press("Z", BPM3A)  # no Z in Lines: nothing changes
    assert signals.y_signals() == [BPM3A, BPM4I]
    assert signals.plane_axes() == (("samy", "samy"), ("samx", "samx"))
    assert box_text(signals) == "X: samy | Y: bpm3a, bpm4i | Z:"
    qtbot.waitUntil(lambda: viewer.waveform.x_mode == "samy")

    viewer.view_switch.buttons["scatter"].click()

    # The axes keep their roles; the map is coloured by the first curve, and takes nothing
    # off: the curves wait for Lines.
    assert signals.y_signals() == [BPM3A]
    assert signals.plane_axes() == (("samy", "samy"), ("samx", "samx"))
    assert box_text(signals) == "X: samy | Y: samx | Z: bpm3a"
    assert signals.note.text() == ""
    assert signals._delegate.letters(signals._signals[BPM4I]) == ["X", "Y", "Z"]
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    scatter = viewer.maps.scatter
    qtbot.waitUntil(lambda: (scatter.device_x, scatter.device_y) == ("samy", "samx"))

    viewer.view_switch.buttons["lines"].click()
    assert signals.y_signals() == [BPM3A, BPM4I]
    assert signals.plane_axes() == (("samy", "samy"), ("samx", "samx"))


def test_the_map_keeps_its_colour_when_it_is_one_of_the_curves(qtbot, map_viewer):
    viewer = map_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    viewer.view_switch.buttons["lines"].click()
    # Typed into Y: it counts at once, as a press on a row does.
    signals.take_role("Y", BPM4I)
    assert signals.y_signals() == [BPM3A, BPM4I]
    viewer.view_switch.buttons["scatter"].click()
    assert signals.y_signals() == [BPM3A]
    signals.press("Z", BPM4I)
    assert box_text(signals) == "X: samx auto | Y: samy auto | Z: bpm4i"

    viewer.view_switch.buttons["lines"].click()
    assert signals.y_signals() == [BPM3A, BPM4I]
    viewer.view_switch.buttons["scatter"].click()
    # The colour the map had is one of the curves: it stays, not the first curve.
    assert signals.y_signals() == [BPM4I]


def test_a_scan_shown_in_between_loses_no_choice_and_the_words_follow_the_view(qtbot, map_viewer):
    viewer = map_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    viewer.view_switch.buttons["lines"].click()
    signals.press("Y", BPM4I)
    y_field = signals.box.fields["Y"]
    assert y_field.edit.accessibleName() == (
        "The curves on the plot, 2 curves. Type to add a signal"
    )
    signals.set_unread({BPM4I: "it could not be read"})
    assert signals.chip_tip("Y", signals._signals[BPM4I]).endswith(
        "Press Y to take it off the plot."
    )
    signals.set_unread({})

    # The grid opens as a heatmap of one colour; the fermat comes back in Lines with both.
    viewer.show_scan(31)
    assert viewer.current_view() == "heatmap"
    assert signals.y_signals() == [BPM3A]
    viewer.show_scan(32)
    assert viewer.current_view() == "lines"
    assert signals.y_signals() == [BPM3A, BPM4I]

    viewer.view_switch.buttons["scatter"].click()
    assert signals.chip_tip("Z", signals._signals[BPM3A]) == "Colour the map by it (Z)"
    assert signals.chip_tip("Y", signals._signals[BPM3A]) == "Use as the y axis (Y)"
    signals.set_unread({BPM3A: "it could not be read"})
    assert signals.chip_tip("Z", signals._signals[BPM3A]).endswith(
        "Press Z to take it off the plot."
    )


def test_lines_get_the_colour_of_the_map_added_to_their_curves(qtbot, map_viewer):
    viewer = map_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    # No curves chosen in Lines yet: Lines show the colour alone.
    signals.press("Z", BPM4I)
    viewer.view_switch.buttons["lines"].click()
    assert signals.y_signals() == [BPM4I]
    assert box_text(signals) == "X: samx auto | Y: bpm4i | Z:"

    signals.press("Y", BPM4I)
    signals.press("Y", BPM3A)
    assert signals.y_signals() == [BPM3A]
    viewer.view_switch.buttons["scatter"].click()
    # The map's last colour is no curve now: the first curve colours it.
    assert signals.y_signals() == [BPM3A]
    signals.press("Z", BPM4I)
    viewer.view_switch.buttons["lines"].click()
    # The colour of the map is not among the curves: it is added after them.
    assert signals.y_signals() == [BPM3A, BPM4I]


def test_an_area_scan_gives_its_signals_x_y_and_z(qtbot, map_viewer):
    viewer = map_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    delegate = signals._delegate  # pylint: disable=protected-access
    assert signals.is_two_dimensional()
    assert delegate.letters(signals._signals[BPM4I]) == ["X", "Y", "Z"]
    assert delegate.letters(signals._signals[("wave", "wave")]) == ["X", "Y", "Z"]
    assert signals.chip_tip("Y", signals._signals[BPM4I]) == "Use as the y axis (Y)"

    # Y on the x axis swaps the two; the auto marks go and the header offers a reset.
    signals.press("Y", ("samx", "samx"))
    assert signals.plane_axes() == (("samy", "samy"), ("samx", "samx"))
    assert not signals.axes_are_auto()
    assert signals.reset_axes_button.isVisibleTo(signals)
    assert not any(row[1].startswith("auto") for row in scan_device_rows(signals))
    assert box_text(signals) == "X: samy | Y: samx | Z: bpm3a auto"
    scatter = viewer.maps.scatter
    qtbot.waitUntil(lambda: (scatter.device_x, scatter.device_y) == ("samy", "samx"))

    # Any signal per point can be an axis; a fast one cannot.
    signals.press("X", BPM4I)
    assert signals.plane_axes() == (BPM4I, ("samx", "samx"))
    signals.press("X", ("wave", "wave"))
    assert signals.plane_axes() == (BPM4I, ("samx", "samx"))

    # The same axes again are the scan's own: auto, whichever way they were reached.
    signals.reset_axes()
    assert signals.axes_are_auto()
    assert not signals.reset_axes_button.isVisibleTo(signals)
    assert box_text(signals) == "X: samx auto | Y: samy auto | Z: bpm3a auto"
    signals.press("X", ("samy", "samy"))
    signals.press("X", ("samx", "samx"))
    assert signals.axes_are_auto()


@pytest.fixture
def diagonal_viewer(qtbot, mocked_client, tmp_path):
    """The viewer on the map history plus a line scan of samx and samy together (selected)."""
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in make_map_history(tmp_path, diagonal=True):
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    widget = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    widget.resize(1200, 700)
    qtbot.waitUntil(lambda: widget.scan_list.model.rowCount() == 4)
    wait_for_switch(qtbot, widget)  # the newest scan is shown
    return widget


def test_a_line_scan_of_two_motors_opens_as_lines_and_has_no_heatmap(qtbot, diagonal_viewer):
    viewer = diagonal_viewer
    signals = viewer.signal_list
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.waveform)
    assert viewer._entry.scan_name == "line_scan"
    assert viewer.current_view() == "lines"
    assert viewer.waveform.x_mode == "samx"

    # Two motors: the switch and X, Y and Z, the motors as x and y as for an area scan.
    assert viewer.view_switch.isVisibleTo(viewer)
    assert signals.is_two_dimensional()
    assert signals.plane_axes() == (("samx", "samx"), ("samy", "samy"))
    # Lines: the rows offer X and Y, the box shows Z without use.
    assert signals._delegate.letters(signals._signals[BPM4I]) == ["X", "Y"]
    assert [row[0] for row in scan_device_rows(signals)] == ["samx", "samy"]
    assert box_text(signals) == "X: samx auto | Y: bpm3a auto | Z:"

    # Its points lie on one line: no heatmap, said where the view is off and in the menu.
    heatmap = viewer.view_switch.buttons["heatmap"]
    qtbot.waitUntil(lambda: not heatmap.isEnabled())
    assert heatmap.toolTip() == "No heatmap: the scan's points lie on one line"
    assert heatmap.accessibleDescription() == heatmap.toolTip()
    assert viewer.view_switch.buttons["scatter"].isEnabled()
    assert viewer.view_switch.buttons["scatter"].accessibleDescription() == ""
    assert viewer.current_view() == "lines"
    _header, offers = viewer.signal_offers()
    assert offers["Heatmap"] == "the scan's points lie on one line"
    assert offers["ScatterWaveform"].describe == (
        "Shows bpm3a over samx, samy of scan 33, saved with the workspace"
    )

    # Scatter shows the points; the choice holds for this kind of scan only.
    viewer.view_switch.buttons["scatter"].click()
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    viewer.show_scan(32)
    assert viewer.current_view() == "scatter"  # the fermat's own default
    viewer.show_scan(31)
    assert viewer.current_view() == "heatmap"
    assert viewer.view_switch.buttons["heatmap"].isEnabled()
    viewer.show_scan(33)
    assert viewer.current_view() == "scatter"


def test_a_scan_of_two_motors_by_a_plugin_opens_as_lines_and_can_be_a_heatmap(
    qtbot, mocked_client, tmp_path
):
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in make_map_history(tmp_path, plugin=True):
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    viewer = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    viewer.resize(1200, 700)
    qtbot.waitUntil(lambda: viewer.scan_list.model.rowCount() == 4)
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    assert viewer._entry.scan_name == "beamline_raster_scan"
    assert viewer.current_view() == "lines" and viewer.view_switch.isVisibleTo(viewer)

    # Its points cover an area: the heatmap stays on once the positions are read.
    viewer.view_switch.buttons["heatmap"].click()
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.heatmap)
    qtbot.waitUntil(lambda: viewer._one_line.get(viewer._entry.scan_id) is False)
    assert viewer.view_switch.buttons["heatmap"].isEnabled()
    assert viewer.current_view() == "heatmap"
    heatmap = viewer.maps.heatmap
    assert (heatmap.device_x, heatmap.device_y) == ("samx", "samy")


def test_a_scan_that_ran_keeps_its_view_when_it_turns_out_to_lie_on_one_line(
    qtbot, diagonal_viewer
):
    viewer = diagonal_viewer
    qtbot.waitUntil(lambda: not viewer.view_switch.buttons["heatmap"].isEnabled())
    scan_id = viewer._entry.scan_id
    # As if the user had looked at it as a heatmap while it ran: it is not taken away.
    viewer._view_choice["path"] = "heatmap"
    viewer._kept_view = (scan_id, "heatmap")
    assert viewer.current_view() == "heatmap"
    # Picked again later, it opens where it can.
    viewer._kept_view = None
    assert viewer.current_view() == "lines"


def test_a_scan_whose_file_was_just_written_is_read_again_soon(
    qtbot, mocked_client, tmp_path, monkeypatch
):
    # Right after a scan its file looks busy for a few seconds: the reads come back until the
    # file is free, and then stop.
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "BUSY_RETRY_MS", 50)
    calls = {"read_map": 0, "readout_groups": 0}
    for name in calls:
        real = getattr(h5_reader, name)

        def busy_twice(*args, _name=name, _real=real, **kwargs):
            calls[_name] += 1
            if calls[_name] <= 2:
                raise H5ReadError("written a moment ago", "busy", args[0])
            return _real(*args, **kwargs)

        monkeypatch.setattr(h5_reader, name, busy_twice)
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in make_map_history(tmp_path, diagonal=True):
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    viewer = create_widget(qtbot, HDF5Viewer, client=mocked_client)

    qtbot.waitUntil(lambda: not viewer.view_switch.buttons["heatmap"].isEnabled())
    qtbot.waitUntil(lambda: calls["readout_groups"] == 3)
    assert calls["read_map"] == 3
    # The third read lands back in the GUI thread a moment after it ran.
    qtbot.waitUntil(lambda: bool(viewer.signal_list._readouts))  # pylint: disable=protected-access
    qtbot.wait(200)
    assert calls == {"read_map": 3, "readout_groups": 3}
    assert not viewer._reread_timer.isActive()  # pylint: disable=protected-access


def test_a_scan_file_that_cannot_be_read_is_grouped_by_shape_at_once(
    qtbot, mocked_client, tmp_path, monkeypatch
):
    # Only a busy file is tried again: one that cannot be read gets its answer at once.
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "BUSY_RETRY_MS", 50)
    calls = {"read_map": 0, "readout_groups": 0}
    for name in calls:

        def unreadable(*args, _name=name, **kwargs):
            calls[_name] += 1
            raise H5ReadError("not an HDF5 file", "unreadable", args[0])

        monkeypatch.setattr(h5_reader, name, unreadable)
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in make_map_history(tmp_path, diagonal=True):
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    viewer = create_widget(qtbot, HDF5Viewer, client=mocked_client)

    qtbot.waitUntil(lambda: calls == {"read_map": 1, "readout_groups": 1})
    qtbot.waitUntil(lambda: viewer.signal_list._by_shape)  # pylint: disable=protected-access
    qtbot.wait(200)
    assert calls == {"read_map": 1, "readout_groups": 1}
    assert not viewer._reread_timer.isActive()  # pylint: disable=protected-access
    # As for a scan that was not checked: the heatmap stays on.
    assert viewer.view_switch.buttons["heatmap"].isEnabled()


def test_a_running_scan_knows_from_its_planned_positions_whether_it_has_a_heatmap(
    qtbot, mocked_client, tmp_path, monkeypatch
):
    # The status of a scan names the positions it will go to: points on one line turn the
    # Heatmap off from its first second, and its file is not read for that after its end.
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer as viewer_module

    reads = []
    real = h5_reader.read_map
    monkeypatch.setattr(
        h5_reader, "read_map", lambda path, *a, **k: (reads.append(path), real(path, *a, **k))[1]
    )
    history = make_map_history(tmp_path, diagonal=True)
    diagonal = history.pop()  # scan 33 is still running
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in history:
        # pylint: disable=protected-access
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
    mocked_client.queue.scan_storage.current_scan = None
    viewer = create_widget(qtbot, HDF5Viewer, client=mocked_client)
    viewer.resize(1200, 700)
    qtbot.waitUntil(lambda: viewer.scan_list.model.rowCount() == 3)
    wait_for_switch(qtbot, viewer)

    def status(scan_id, number, positions, state="open"):
        info = {} if positions is None else {"positions": positions}
        viewer.on_scan_status(
            {
                "scan_id": scan_id,
                "scan_number": number,
                "scan_name": "line_scan",
                "status": state,
                "num_points": 16,
                "scan_report_devices": ["samx", "samy"],
                "readout_priority": {"monitored": ["samx", "samy", "bpm4i"]},
                "info": info,
            },
            {},
        )

    on_line = np.column_stack([np.linspace(-1, 1, 16)] * 2)
    status(diagonal.scan_id, 33, on_line.tolist())
    viewer.show_scan(33)
    assert viewer._entry.live
    assert not viewer.view_switch.buttons["heatmap"].isEnabled()
    assert viewer.view_switch.buttons["heatmap"].toolTip()
    # Later status messages of the scan do not test its positions again.
    monkeypatch.setattr(viewer_module, "points_on_one_line", lambda *a: pytest.fail("tested again"))
    status(diagonal.scan_id, 33, on_line.tolist(), state="paused")

    # It ends and its history entry replaces it: the answer stays, the file is not read for it.
    status(diagonal.scan_id, 33, None, state="closed")
    mocked_client.history._scan_data[diagonal.scan_id] = (
        diagonal  # pylint: disable=protected-access
    )
    mocked_client.history._scan_ids.append(diagonal.scan_id)  # pylint: disable=protected-access
    viewer._load_history()  # pylint: disable=protected-access
    qtbot.waitUntil(lambda: not viewer._entry.live)
    qtbot.wait(200)
    assert not viewer.view_switch.buttons["heatmap"].isEnabled()
    assert diagonal.file_path not in reads


def test_planned_positions_of_a_grid_leave_the_heatmap_on_and_none_fall_back_to_the_file(
    qtbot, map_viewer
):
    viewer = map_viewer
    xx, yy = np.meshgrid(np.linspace(-1, 1, 4), np.linspace(-1, 1, 4))
    for scan_id, info in (
        ("grid-live", {"positions": np.column_stack([xx.ravel(), yy.ravel()]).tolist()}),
        ("fly-live", {}),
        ("odd-live", {"positions": [[1.0], [2.0]]}),  # one motor only: nothing to tell
    ):
        viewer.on_scan_status(
            {
                "scan_id": scan_id,
                "scan_number": 90,
                "scan_name": "grid_scan",
                "status": "open",
                "scan_report_devices": ["samx", "samy"],
                "readout_priority": {"monitored": ["samx", "samy"]},
                "info": info,
            },
            {},
        )
    assert viewer._one_line["grid-live"] is False
    # Without positions the answer is left to the read of the file after the end.
    assert "fly-live" not in viewer._one_line
    assert "odd-live" not in viewer._one_line
    assert planned_on_one_line({"positions": np.zeros((0, 2))}) is None
    assert planned_on_one_line(None) is None


def test_a_map_shows_the_selected_scan_only(qtbot, map_viewer):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    viewer.scan_list.model.toggle_pin("map-1")
    assert viewer.plot_stack.currentWidget() is viewer.maps.scatter
    assert "the map shows this scan only" in viewer.plot_subtitle.full_text()

    # What goes to another plot is the map, of the selected scan only.
    header, _offers = viewer.signal_offers()
    assert header == "Scatter of bpm3a over samx, samy · scan 32"


def test_the_scatter_map_stays_on_its_scan_while_another_runs(qtbot, map_viewer):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    scatter = viewer.maps.scatter
    assert scatter.history_scan_id == "map-2"
    scatter.on_scan_status({"scan_id": "running-scan", "status": "open"}, {})
    assert scatter.history_scan_id == "map-2" and scatter.scan_id == "map-2"


################################################################################
# Default plots of NeXus groups
################################################################################


@pytest.fixture
def nexus_file(tmp_path):
    """A file whose entries name their default plots in the ways files do, and do not."""
    path = tmp_path / "nexus.h5"
    other = tmp_path / "other.h5"
    with h5py.File(other, "w") as handle:
        handle["counts"] = np.arange(10.0)
    with h5py.File(path, "w") as handle:
        handle.attrs["default"] = "scan"
        scan = handle.create_group("scan")
        scan.attrs["NX_class"] = "NXentry"
        scan.attrs["default"] = "data"
        data = scan.create_group("data")
        data.attrs["NX_class"] = "NXdata"
        data.attrs["signal"] = "bpm4i"
        data.attrs["axes"] = ["samx"]
        data["bpm4i"] = np.linspace(0, 1, 50) ** 2
        data["samx"] = np.linspace(-5, 5, 50)
        data["samx"].attrs["units"] = "mm"
        # A map: two axes, one per dimension; "." where a dimension has none.
        image = handle.create_group("map/data")
        handle["map"].attrs["default"] = "data"
        image.attrs["NX_class"] = "NXdata"
        image.attrs["signal"] = "intensity"
        image.attrs["axes"] = ["samy", "."]
        image["intensity"] = np.ones((4, 6))
        image["samy"] = np.arange(4.0)
        # As BEC writes it: the first motor is the signal, no axes, no default.
        bec = handle.create_group("bec/data")
        bec.attrs["NX_class"] = "NXdata"
        bec.attrs["signal"] = "samx"
        bec["samx"] = np.arange(5.0)
        # The old way: axes as one string.
        old = handle.create_group("old")
        old.attrs["signal"] = "y"
        old.attrs["axes"] = "x"
        old["y"] = np.arange(3.0)
        old["x"] = np.arange(3.0) * 2
        # Defaults that lead nowhere useful.
        handle.create_group("plain")["values"] = np.arange(3.0)
        loop = handle.create_group("loop")
        loop.attrs["default"] = "."
        text = handle.create_group("text")
        text.attrs["signal"] = "label"
        text["label"] = "hello"
        away = handle.create_group("away")
        away.attrs["signal"] = "counts"
        away["counts"] = h5py.ExternalLink(other.name, "/counts")
        wrong = handle.create_group("wrong_axis")
        wrong.attrs["signal"] = "y"
        wrong.attrs["axes"] = "x"
        wrong["y"] = np.arange(4.0)
        wrong["x"] = np.arange(3.0)
    settle(path, other)
    return path


def test_default_plot_follows_default_down_to_the_signal_and_its_axes(nexus_file):
    file_path = str(nexus_file)
    for start in ("/", "/scan", "/scan/data"):
        plot = h5_reader.default_plot(file_path, start)
        assert plot.nxdata_path == "/scan/data"
        assert plot.signal.path == "/scan/data/bpm4i" and plot.signal.shape == (50,)
        assert (plot.axes, plot.x_path, plot.x_name, plot.x_units) == (
            ("samx",),
            "/scan/data/samx",
            "samx",
            "mm",
        )
        assert plot.group_path == start

    image = h5_reader.default_plot(file_path, "/map")
    assert image.signal.shape == (4, 6) and image.axes == ("samy", "")
    assert image.x_path == ""  # the last dimension has no axis

    bec = h5_reader.default_plot(file_path, "/bec/data")
    assert bec.signal.path == "/bec/data/samx" and bec.x_path == ""

    old = h5_reader.default_plot(file_path, "/old")
    assert old.x_path == "/old/x"


def test_default_plot_is_none_where_a_group_leads_to_no_numeric_signal(nexus_file):
    file_path = str(nexus_file)
    for group in ("/plain", "/loop", "/text", "/away", "/bec"):
        assert h5_reader.default_plot(file_path, group) is None, group
    # An axis that does not fit the signal is left out, the signal stays.
    plot = h5_reader.default_plot(file_path, "/wrong_axis")
    assert plot.signal.path == "/wrong_axis/y" and plot.x_path == ""


def group(file_path, path, nx_class="", n_children=1):
    name = path.rstrip("/").rsplit("/", 1)[-1] or "nexus.h5"
    kind = "file" if path == "/" else "group"
    return H5Node(
        name=name,
        path=path,
        file_path=str(file_path),
        kind=kind,
        nx_class=nx_class,
        n_children=n_children,
    )


def test_preview_of_a_group_shows_its_default_plot_against_its_axis(
    qtbot, service, mocked_client, nexus_file
):
    preview = H5Preview(service, client=mocked_client)
    qtbot.addWidget(preview)
    preview.resize(800, 500)

    preview.show_node(group(nexus_file, "/scan", "NXentry"))
    qtbot.waitUntil(lambda: preview._overview is not None)

    assert preview.default_plot.nxdata_path == "/scan/data"
    assert preview.node.path == "/scan/data/bpm4i" and preview.view == "line"
    assert preview.x_combo.currentData() == "/scan/data/samx"
    assert preview.x_combo.currentText() == "samx (mm)"
    np.testing.assert_allclose(preview._curve.xData, np.linspace(-5, 5, 50))
    assert preview.summary_label.text().startswith("default plot of scan")
    source = preview.line_source()
    assert (source.x_path, source.x_label) == ("/scan/data/samx", "samx (mm)")

    # A map is shown as an image.
    preview.show_node(group(nexus_file, "/map"))
    qtbot.waitUntil(lambda: preview.stack.currentWidget() is preview.image_page)
    assert preview.node.path == "/map/data/intensity"

    # A NeXus group without a default plot says so; a plain group does not.
    preview.show_node(group(nexus_file, "/plain", "NXentry"))
    qtbot.waitUntil(lambda: "names no default plot" in preview.state_page.text.text())
    assert preview.default_plot is None and preview.node.path == "/plain"
    preview.cleanup()
    for plot in (preview._waveform, preview._image):
        plot.close()
        plot.deleteLater()


def test_a_map_shows_a_loading_state_until_its_data_is_drawn(qtbot, map_viewer):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)

    # Neither the scatter of the scan before nor an empty heatmap: the loading state.
    viewer.show_scan(31)
    assert viewer.plot_stack.currentWidget() is viewer.plot_state
    assert viewer.plot_state.title.text() == "Loading the map"
    assert viewer.plot_state.text.text() == "bpm3a over samx and samy"
    viewer._on_map_slow()  # pylint: disable=protected-access
    assert viewer.plot_state.title.text() == "Still loading the map"
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.heatmap)
    assert viewer.maps.heatmap.main_image.raw_data.shape == (4, 4)

    # A map drawn already is shown at once.
    viewer.show_scan(32)
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    viewer.show_scan(31)
    viewer.show_scan(32)
    assert viewer.plot_stack.currentWidget() is viewer.maps.scatter


def test_a_map_is_not_ready_with_the_image_of_another_scan(qtbot, map_viewer):
    viewer = map_viewer
    viewer.show_scan(31)
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.heatmap)
    maps = viewer.maps
    # Another colour of the same scan: the map stays on its axes while the new one loads.
    viewer.signal_list.toggle_y(BPM4I)
    assert maps.recoloured and not maps.is_ready("heatmap")
    assert viewer.plot_stack.currentWidget() is maps.heatmap
    maps.heatmap.scan_id = "map-2"  # e.g. a late image of the scan before
    maps.heatmap.image_updated.emit()
    assert not maps.is_ready("heatmap")
    maps.heatmap.scan_id = "map-1"
    qtbot.waitUntil(lambda: maps.is_ready("heatmap"))
    assert maps.heatmap.device_z == "bpm4i"

    # Another scan is never shown with the map of this one.
    viewer.show_scan(32)
    viewer.view_switch.buttons["heatmap"].click()
    assert not maps.recoloured
    assert viewer.plot_stack.currentWidget() is viewer.plot_state
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is maps.heatmap)


################################################################################
# Scan axes of a file: what its signals are plotted against
################################################################################


def write_bec_file(path, scan_name="fermat_scan", motors=("samx", "samy"), points=16):
    """A master file laid out as BEC writes it: /entry/data names the motors, the devices
    keep value and timestamp of each signal."""
    with h5py.File(path, "w") as handle:
        entry = handle.create_group("entry")
        entry.attrs["NX_class"] = "NXentry"
        handle["entry/collection/metadata/bec/scan_name"] = scan_name
        devices = handle.create_group("entry/collection/devices")
        positions = {
            "samx": np.repeat(np.linspace(-1, 1, 4), points // 4),
            "samy": np.tile(np.linspace(-1, 1, 4), points // 4),
        }
        values = {**positions, "bpm4i": np.arange(points, dtype=float) ** 2}
        for name, value in values.items():
            signal = devices.create_group(f"{name}/{name}")
            signal.attrs["NX_class"] = "NXdata"
            signal.attrs["signal"] = "value"
            signal["value"] = value
            signal["timestamp"] = 1000.0 + 0.5 * np.arange(points)
        devices["samx/samx"]["value"].attrs["units"] = "mm"
        setpoint = devices.create_group("samx/samx_setpoint")
        setpoint["value"] = positions["samx"]
        setpoint["timestamp"] = 1000.0 + 0.5 * np.arange(points)
        wave = devices.create_group("wave/wave")
        wave["value"] = np.arange(40.0)
        wave["timestamp"] = np.arange(40.0)
        data = handle.create_group("entry/data")
        data.attrs["NX_class"] = "NXdata"
        data.attrs["signal"] = motors[0]
        if len(motors) > 1:
            data.attrs["auxiliary_signals"] = list(motors[1:])
        for motor in motors:
            data[motor] = h5py.SoftLink(f"/entry/collection/devices/{motor}/{motor}/value")
    settle(path)
    return path


@pytest.fixture
def bec_file(tmp_path):
    return write_bec_file(tmp_path / "S00022_master.h5")


BPM4I_VALUE = "/entry/collection/devices/bpm4i/bpm4i/value"


def test_the_scan_axes_are_the_motors_bec_names_in_entry_data(bec_file):
    details = h5_reader.describe(str(bec_file), BPM4I_VALUE)
    axes = details.scan_axes
    assert axes.source == "bec" and axes.scan_name == "fermat_scan"
    assert [axis.path for axis in axes.axes] == ["/entry/data/samx", "/entry/data/samy"]
    assert axes.names == "samx, samy" and axes.length == 16
    assert axes.axes[0].units == "mm"
    assert details.time.path == "/entry/collection/devices/bpm4i/bpm4i/timestamp"
    # The timestamps are not a choice of their own besides "Timestamp".
    assert h5_reader.describe(str(bec_file), details.time.path).time is None


def test_the_axes_of_a_nexus_plot_win_over_the_bec_convention(tmp_path):
    path = write_bec_file(tmp_path / "nexus_axes.h5")
    with h5py.File(path, "a") as handle:
        handle["entry"].attrs["default"] = "plot"
        plot = handle.create_group("entry/plot")
        plot.attrs["NX_class"] = "NXdata"
        plot.attrs["signal"] = "bpm4i"
        plot.attrs["axes"] = ["energy"]
        plot["bpm4i"] = np.arange(16.0)
        plot["energy"] = np.linspace(7000, 7100, 16)
    settle(path)
    axes = h5_reader.describe(str(path), BPM4I_VALUE).scan_axes
    assert axes.source == "nexus" and axes.names == "energy"
    # In the plot's own group the axis is the dataset's own, not a scan axis.
    assert h5_reader.describe(str(path), "/entry/plot/bpm4i").scan_axes is None


def test_a_device_group_plots_its_main_signal(bec_file):
    file_path = str(bec_file)
    plot = h5_reader.default_plot(file_path, "/entry/collection/devices/bpm4i")
    assert plot.signal.path == BPM4I_VALUE and plot.rule == "device"
    # Named like the device first, whatever comes first in the group.
    plot = h5_reader.default_plot(file_path, "/entry/collection/devices/samx")
    assert plot.signal.path == "/entry/collection/devices/samx/samx/value"
    # A signal group without NeXus attributes: its value.
    plot = h5_reader.default_plot(file_path, "/entry/collection/devices/samx/samx_setpoint")
    assert plot.signal.path.endswith("samx_setpoint/value") and plot.rule == "device"
    # The NeXus @signal of a signal group comes first.
    assert h5_reader.default_plot(file_path, "/entry/collection/devices/bpm4i/bpm4i").rule == (
        "nexus"
    )
    for other in ("/entry/collection", "/entry/collection/devices"):
        assert h5_reader.default_plot(file_path, other) is None, other


def test_read_map_and_time_since_the_first_point(bec_file):
    file_path = str(bec_file)
    data = h5_reader.read_map(file_path, BPM4I_VALUE, "/entry/data/samx", "/entry/data/samy")
    np.testing.assert_allclose(data.z, np.arange(16.0) ** 2)
    np.testing.assert_allclose(data.x, np.repeat(np.linspace(-1, 1, 4), 4))
    assert data.stride == 1
    timestamps = "/entry/collection/devices/bpm4i/bpm4i/timestamp"
    curve = h5_reader.read_curve(file_path, BPM4I_VALUE, x_path=timestamps, relative_x=True)
    np.testing.assert_allclose(curve.x, 0.5 * np.arange(16))
    with pytest.raises(H5ReadError):
        h5_reader.read_map(
            file_path,
            "/entry/collection/devices/wave/wave/value",
            "/entry/data/samx",
            "/entry/data/samy",
        )


def make_preview(qtbot, service, mocked_client):
    preview = H5Preview(service, client=mocked_client)
    qtbot.addWidget(preview)
    preview.resize(900, 600)
    preview.show()
    return preview


def close_preview(preview):
    preview.cleanup()
    for plot in (preview._waveform, preview._image):
        if plot is not None:
            plot.close()
            plot.deleteLater()


def entries(preview) -> list[str]:
    combo = preview.x_combo
    return [combo.itemText(index) for index in range(combo.count())]


def test_a_device_group_of_a_map_scan_opens_as_a_map_of_the_scan_axes(
    qtbot, service, mocked_client, bec_file
):
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(group(bec_file, "/entry/collection/devices/bpm4i"))
    qtbot.waitUntil(lambda: preview.stack.currentWidget() is preview.map_page)

    assert preview.node.path == BPM4I_VALUE and preview.view == "map"
    assert preview.summary_label.text().startswith("main signal of bpm4i")
    # What to plot against is chosen in the X field of the File tab, not on the plot pane.
    assert not preview.x_combo.isVisibleTo(preview)
    assert entries(preview) == ["Scan axes (samx, samy)", "Index", "Timestamp"]
    assert preview.x_combo.currentData() == SCAN_AXES
    assert preview.map_kind() == "scatter"
    scatter = preview.map_widget()
    np.testing.assert_allclose(scatter.main_curve.xData, np.repeat(np.linspace(-1, 1, 4), 4))
    np.testing.assert_allclose(scatter.main_curve.data_z, np.arange(16.0) ** 2)
    assert (scatter.x_label, scatter.y_label) == ("samx (mm)", "samy")
    assert preview.info_label.text() == (
        "16 points  ·  x: samx  ·  y: samy  ·  colour: bpm4i  ·  read from the file"
    )
    assert preview.view_buttons["map"].isVisibleTo(preview)
    close_preview(preview)


def test_the_choice_of_what_to_plot_against_is_kept_for_other_datasets(
    qtbot, service, mocked_client, bec_file
):
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(group(bec_file, "/entry/collection/devices/bpm4i"))
    qtbot.waitUntil(lambda: preview.view == "map" and preview._map_data is not None)

    # Time: a line against the seconds since the first point.
    preview._on_x_chosen(preview.x_combo.findData(TIME))
    qtbot.waitUntil(lambda: preview._overview is not None)
    assert preview.view == "line" and preview.x_choice == TIME
    np.testing.assert_allclose(preview._curve.xData, 0.5 * np.arange(16))
    assert preview._waveform.x_label == "Timestamp (s since the first point)"

    # Another signal is shown the same way.
    preview.show_node(group(bec_file, "/entry/collection/devices/samx"))
    qtbot.waitUntil(lambda: preview._overview is not None)
    assert preview.view == "line" and preview.x_combo.currentData() == TIME

    # A dataset without timestamps falls back to the row number and says why; the choice stays.
    preview.show_node(dataset(bec_file, "/entry/data/samx", (16,)))
    qtbot.waitUntil(lambda: preview._overview is not None)
    assert preview.x_combo.currentData() == "" and preview.x_choice == TIME
    assert preview.info_label.text().startswith(
        "This dataset has no timestamps next to it. Shown against Index."
    )

    # The scan axes again: the map comes back.
    preview._on_x_chosen(preview.x_combo.findData(SCAN_AXES))
    qtbot.waitUntil(lambda: preview.view == "map" and preview._map_data is not None)
    assert preview.x_choice == SCAN_AXES
    close_preview(preview)


def test_scan_axes_that_do_not_fit_fall_back_to_the_row_number_in_place(
    qtbot, service, mocked_client, bec_file
):
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(group(bec_file, "/entry/collection/devices/bpm4i"))
    qtbot.waitUntil(lambda: preview.view == "map" and preview._map_data is not None)
    preview._on_x_chosen(preview.x_combo.findData(SCAN_AXES))  # chosen by the user

    preview.show_node(group(bec_file, "/entry/collection/devices/wave"))
    qtbot.waitUntil(lambda: preview._overview is not None)
    assert preview.view == "line" and preview.x_combo.currentData() == ""
    assert not preview.view_buttons["map"].isVisibleTo(preview)
    assert preview.x_choice == SCAN_AXES
    assert preview.info_label.text().startswith(
        "Scan axes do not fit this dataset (40 rows, the scan has 16 points). "
        "Shown against Index."
    )
    axes_item = preview.x_combo.model().item(preview.x_combo.findData(SCAN_AXES))
    assert not axes_item.isEnabled()
    close_preview(preview)


def test_a_grid_scan_file_is_drawn_as_a_heatmap_and_one_motor_as_a_line(
    qtbot, service, mocked_client, tmp_path
):
    grid = write_bec_file(tmp_path / "S00020_master.h5", scan_name="grid_scan")
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(group(grid, "/entry/collection/devices/bpm4i"))
    qtbot.waitUntil(lambda: preview.view == "map" and preview._map_data is not None)
    assert preview.map_kind() == "heatmap"
    heatmap = preview.map_widget()
    # Points on a regular grid: one pixel each, placed where they were taken.
    np.testing.assert_allclose(heatmap.main_image.raw_data.ravel(), np.arange(16.0) ** 2)
    assert heatmap.title == "bpm4i"

    line = write_bec_file(tmp_path / "S00011_master.h5", scan_name="line_scan", motors=("samx",))
    preview.show_node(group(line, "/entry/collection/devices/bpm4i"))
    qtbot.waitUntil(lambda: preview._overview is not None)
    assert preview.view == "line" and preview.x_combo.currentText() == "Scan axes (samx)"
    np.testing.assert_allclose(preview._curve.xData, np.repeat(np.linspace(-1, 1, 4), 4))
    assert not preview.view_buttons["map"].isVisibleTo(preview)
    close_preview(preview)


def test_grid_image_places_each_point_of_a_regular_grid_in_its_pixel():
    x = np.repeat(np.linspace(-5, 5, 3), 4) + np.random.default_rng(1).normal(0, 1e-4, 12)
    y = np.tile(np.linspace(0, 3, 4), 3)
    image, transform = grid_image(x, y, np.arange(12.0))
    np.testing.assert_allclose(image, np.arange(12.0).reshape(3, 4))
    # Pixel centres sit on the positions.
    centre = transform.map(0.5, 0.5)
    np.testing.assert_allclose(centre, (-5.0, 0.0), atol=1e-3)
    # Points that lie on no grid: interpolated by the Heatmap instead.
    rng = np.random.default_rng(2)
    assert grid_image(rng.uniform(0, 1, 50), rng.uniform(0, 1, 50), np.zeros(50)) is None


################################################################################
# Sending to plots of every kind
################################################################################


def open_target(qtbot, mocked_client, kind: str, name: str):
    """An open plot of a kind, outside the viewer."""
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.plots.heatmap.heatmap import Heatmap
    from bec_widgets.widgets.plots.image.image import Image
    from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform
    from bec_widgets.widgets.plots.waveform.waveform import Waveform

    classes = {
        "Waveform": Waveform,
        "Heatmap": Heatmap,
        "ScatterWaveform": ScatterWaveform,
        "Image": Image,
    }
    target = create_widget(qtbot, classes[kind], client=mocked_client)
    target.setObjectName(name)
    return target


class FakeDockArea:
    """Opens plots as a dock area does, for the "New plot in the workspace" entries."""

    def __init__(self, qtbot, client):
        self.qtbot, self.client, self.opened = qtbot, client, []

    def new(self, kind: str):
        plot = open_target(self.qtbot, self.client, kind, f"New{kind}")
        self.opened.append(plot)
        return plot


def test_a_map_goes_to_open_plots_of_every_kind_that_fits(
    qtbot, map_viewer, mocked_client, monkeypatch
):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.plot_targets import MapSource, show_map, shown_map

    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    heatmap = open_target(qtbot, mocked_client, "Heatmap", "TargetHeatmap")
    scatter = open_target(qtbot, mocked_client, "ScatterWaveform", "TargetScatter")
    waveform = open_target(qtbot, mocked_client, "Waveform", "TargetWaveform")
    open_target(qtbot, mocked_client, "Image", "TargetImage")
    # The heatmap shows another signal of another scan before.
    before = MapSource("map-1", ("samx", "samx"), ("samy", "samy"), BPM4I)
    show_map(heatmap, before)

    viewer._fill_add_menu()
    texts = menu_texts(viewer.add_menu)
    assert texts == [
        "Scatter of bpm3a over samx, samy · scan 32",
        "Plots that are open",
        "TargetHeatmap\treplaces what it shows",
        "TargetImage\tneeds a 2D dataset",
        "TargetScatter\treplaces what it shows",
        "TargetWaveform\tadds 1 curve",
    ]
    [image_line] = [a for a in viewer.add_menu.actions() if a.text().startswith("TargetImage")]
    assert not image_line.isEnabled()

    said = short_forms(monkeypatch, viewer)
    assert viewer.add_to_plot(heatmap, "TargetHeatmap")
    assert said[-1] == "TargetHeatmap now shows scan 32 · Undo"
    wanted = MapSource("map-2", ("samx", "samx"), ("samy", "samy"), BPM3A)
    assert shown_map(heatmap) == wanted and heatmap.history_scan_id == "map-2"
    assert viewer.add_button.property("feedback") == (
        "TargetHeatmap now shows bpm3a of scan 32 · Undo"
    )

    # The way back is the first line of the menu, until the next replace.
    viewer._fill_add_menu()
    undo = viewer.add_menu.actions()[0]
    assert undo.text() == "Undo: TargetHeatmap back to bpm4i of scan 31"
    undo.trigger()
    assert shown_map(heatmap) == before
    assert viewer.add_button.property("feedback") == "TargetHeatmap shows bpm4i of scan 31 again"
    assert said[-1] == "TargetHeatmap shows scan 31 again"
    viewer._fill_add_menu()
    assert not viewer.add_menu.actions()[0].text().startswith("Undo")

    # A scatter that showed nothing has nothing to go back to.
    assert viewer.add_to_plot(scatter, "TargetScatter")
    assert shown_map(scatter) == wanted and scatter.history_scan_id == "map-2"
    assert viewer.add_button.property("feedback") == "TargetScatter now shows bpm3a of scan 32"
    viewer._fill_add_menu()
    assert "TargetScatter\tshows it already" in menu_texts(viewer.add_menu)

    result = viewer.add_to_plot(waveform, "TargetWaveform")
    assert result.added == 1
    assert [curve.config.scan_id for curve in waveform.curves] == ["map-2"]


def test_a_map_opens_in_a_new_plot_of_the_workspace(qtbot, map_viewer, mocked_client):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    area = FakeDockArea(qtbot, mocked_client)
    with mock.patch(
        "bec_widgets.widgets.services.hdf5_viewer.hdf5_viewer.dock_area_for", return_value=area
    ):
        viewer._fill_add_menu()
    texts = menu_texts(viewer.add_menu)
    assert texts[:6] == [
        "Scatter of bpm3a over samx, samy · scan 32",
        "New plot in the workspace",
        "Heatmap\tthis map",
        "Scatter Waveform\tthis map",
        "Waveform\tbpm3a as a line",
        "Image\tneeds a 2D dataset",
    ]

    assert viewer.add_to_new_plot(area, "Heatmap")
    [heatmap] = area.opened
    assert heatmap.history_scan_id == "map-2" and heatmap.device_z == "bpm3a"
    assert viewer.add_button.property("feedback") == "NewHeatmap now shows bpm3a of scan 32"

    assert viewer.add_to_new_plot(area, "Image") is None
    assert len(area.opened) == 1

    # A new Waveform draws the line against what the viewer does: the scan's first motor.
    assert viewer.add_to_new_plot(area, "Waveform").added == 1
    waveform = area.opened[-1]
    assert (waveform.x_mode, waveform.signal_x) == ("samx", "samx")


def test_the_button_says_the_longest_text_that_fits_and_keeps_the_way_back(qtbot, viewer):
    button, timer = viewer.add_button, viewer._add_reset_timer
    metrics = button.fontMetrics()
    full = "Heatmap now shows bpm3a of scan 22 · Undo"
    short = "Heatmap now shows scan 22 · Undo"
    tool_tip = button.toolTip()

    # Room for the whole sentence: it is shown as it is, and the tooltip stays the button's.
    viewer._say_on(button, timer, full, metrics.horizontalAdvance(full), short)
    assert button.text() == full and button.toolTip() == tool_tip

    # Room for the short form only: that is shown, the sentence is in the tooltip.
    viewer._say_on(button, timer, full, metrics.horizontalAdvance(short), short)
    assert button.text() == short and button.toolTip() == full
    assert button.property("feedback") == full

    # Not even that: the sentence is cut, the way back stays in sight.
    width = metrics.horizontalAdvance(short) - 20
    viewer._say_on(button, timer, full, width, short)
    shown = button.text()
    assert shown.endswith("… · Undo") and metrics.horizontalAdvance(shown) <= width + 2
    assert button.toolTip() == full

    timer.timeout.emit()
    assert button.text() == "Add to plot" and button.toolTip() == tool_tip


def test_the_add_button_takes_the_room_the_subtitle_leaves(qtbot, viewer):
    viewer.resize(1100, 600)
    viewer.show()
    qtbot.waitExposed(viewer)
    page = viewer.plot_page.width()
    room = viewer._text_room(viewer.add_button, page, [viewer.plot_title, viewer.view_switch])
    assert room > page - viewer.plot_title.width() - 120
    narrow = viewer._text_room(viewer.add_button, 10, [viewer.plot_title])
    assert narrow == viewer.add_button.fontMetrics().horizontalAdvance("Add to plot")


def test_a_scan_of_one_motor_cannot_be_a_map_but_lines_of_an_area_scan_can(qtbot, map_viewer):
    viewer = map_viewer
    qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.maps.scatter)
    viewer.view_switch.buttons["lines"].click()
    qtbot.waitUntil(lambda: viewer.current_view() == "lines" and bool(viewer._curves))
    header, offers = viewer.signal_offers()
    assert header.startswith("Lines of ") and header.endswith(" · scan 32")
    assert offers["Heatmap"].describe == (
        "Shows bpm3a over samx, samy of scan 32, saved with the workspace"
    )

    viewer.scan_list.select("map-0")
    qtbot.waitUntil(lambda: viewer._entry.scan_id == "map-0")
    _header, offers = viewer.signal_offers()
    assert offers["Heatmap"] == offers["ScatterWaveform"] == "needs a scan of two motors"
    assert offers["Image"] == "needs a 2D dataset"


def test_the_scan_axes_of_a_file_know_where_their_values_are_stored(bec_file):
    axes = h5_reader.describe(str(bec_file), BPM4I_VALUE).scan_axes
    assert [axis.target for axis in axes.axes] == [
        "/entry/collection/devices/samx/samx/value",
        "/entry/collection/devices/samy/samy/value",
    ]


def show_map_of_file(qtbot, viewer, file_path, dataset):
    viewer.open_file(str(file_path), dataset)
    qtbot.waitUntil(
        lambda: viewer.preview.node is not None
        and viewer.preview.node.path == dataset
        and viewer.preview.map_fits(),
        timeout=5000,
    )
    viewer.preview.view_buttons["map"].click()
    qtbot.waitUntil(lambda: viewer.preview.view == "map")


def test_the_file_map_of_a_listed_scan_goes_to_a_heatmap_backed_by_its_history(
    qtbot, map_viewer, mocked_client
):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.plot_targets import MapSource, shown_map

    viewer = map_viewer
    scan = viewer.scan_list.model.entry("map-2")
    write_bec_file(scan.file_path)
    heatmap = open_target(qtbot, mocked_client, "Heatmap", "TargetHeatmap")
    show_map_of_file(qtbot, viewer, scan.file_path, BPM4I_VALUE)

    header, offers = viewer.file_offers()
    assert header == "Scatter of bpm4i over samx, samy · scan 32"
    assert offers["Image"] == "needs a 2D dataset"
    assert not viewer.file_add_button.isHidden()

    assert viewer.add_file_to_plot(heatmap, "TargetHeatmap")
    assert shown_map(heatmap) == MapSource("map-2", ("samx", "samx"), ("samy", "samy"), BPM4I)
    assert viewer.file_add_button.property("feedback") == (
        "TargetHeatmap now shows bpm4i of scan 32"
    )


def test_the_file_map_of_another_file_is_no_map_for_other_plots(qtbot, viewer, bec_file):
    show_map_of_file(qtbot, viewer, bec_file, BPM4I_VALUE)
    header, offers = viewer.file_offers()
    reason = "only for scans in the list"
    assert offers["Heatmap"] == offers["ScatterWaveform"] == reason
    assert offers["Waveform"] == "needs a line"
    assert header == f"Nothing to add: {reason}"


def test_a_frame_of_a_file_goes_to_an_image_as_a_copy_and_back(
    qtbot, viewer, data_file, mocked_client, monkeypatch
):
    image = open_target(qtbot, mocked_client, "Image", "TargetImage")
    viewer.open_file(str(data_file), "/entry/frames")
    qtbot.waitUntil(lambda: viewer.preview.shown_frame() is not None, timeout=5000)
    frame, index = viewer.preview.shown_frame()
    assert index == (0,)

    header, offers = viewer.file_offers()
    assert header == "Copy of S00007_frames.h5 /entry/data [0]"
    assert offers["Waveform"] == "needs a line"
    viewer._fill_file_add_menu()
    assert "TargetImage\treplaces what it shows" in menu_texts(viewer.file_add_menu)

    said = short_forms(monkeypatch, viewer)
    assert viewer.add_file_to_plot(image, "TargetImage")
    assert said[-1] == "TargetImage now shows a copy · Undo"
    assert np.array_equal(image.main_image.raw_data, frame.data)
    assert image.title == "S00007_frames.h5 /entry/data [0]"
    assert viewer.file_add_button.property("feedback") == (
        "TargetImage now shows a copy, not saved with the workspace · Undo"
    )
    viewer._fill_file_add_menu()
    undo = viewer.file_add_menu.actions()[0]
    assert undo.text() == "Undo: TargetImage back to what it showed"
    undo.trigger()
    assert image.main_image.raw_data is None and image.title == ""


################################################################################
# Datasets kept on the plot of the File tab
################################################################################

SAMX_VALUE = "/entry/collection/devices/samx/samx/value"
SAMY_VALUE = "/entry/collection/devices/samy/samy/value"
WAVE_VALUE = "/entry/collection/devices/wave/wave/value"


def kept_node(file_path, path, rows=16):
    return dataset(file_path, path, (rows,))


def choose_x(preview, data):
    """Pick what to plot against as a person does: the box shows it, then it is applied."""
    index = preview.x_combo.findData(data)
    preview.x_combo.setCurrentIndex(index)
    preview._on_x_chosen(index)


def test_short_names_of_datasets_follow_the_signal_names_of_bec():
    assert dataset_name(BPM4I_VALUE) == "bpm4i"
    assert dataset_name(BPM4I_VALUE, with_parent=True) == "bpm4i/bpm4i"
    assert dataset_name("/entry/data/samx", with_parent=True) == "data/samx"
    assert dataset_name("/counts", with_parent=True) == "counts"


def test_rows_that_can_be_one_curve_have_a_y_button_that_keeps_them_without_selecting(
    qtbot, service, data_file
):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.resize(466, 400)
    tree.show()
    toggled = []
    tree.keep_toggled.connect(toggled.append)
    tree.set_file(str(data_file), select_path="/entry/plot/counts")
    qtbot.waitUntil(
        lambda: (tree.current_node() or H5Node("", "", "", "group")).path == "/entry/plot/counts"
    )
    counts = tree.view.currentIndex()
    energy = counts.sibling(counts.row() + 1, 0)
    assert tree.node_at(energy).path == "/entry/plot/energy"
    plot_group = counts.parent()
    # Datasets of numbers along one axis can be kept; a group that is no NXdata cannot.
    assert tree.can_keep_row(tree.node_at(counts)) and tree.can_keep_row(tree.node_at(energy))
    assert not tree.can_keep_row(tree.node_at(plot_group))
    # Name, Type, Shape, then the Y button: Shape is right-aligned next to it.
    header = tree.view.header()
    order = [header.logicalIndex(visual) for visual in range(header.count())]
    names = [tree.model.headerData(i, Qt.Orientation.Horizontal) for i in order]
    assert names[:3] == ["Name", "Type", "Shape"] and order[-1] == Y_COLUMN
    assert header.sectionSize(Y_COLUMN) == 34
    # The rows are as high as those of the Signals tab: the button has room above and below.
    row = tree.view.visualRect(energy)
    assert row.height() == TREE_ROW_HEIGHT
    button_cell = tree.view.visualRect(energy.sibling(energy.row(), Y_COLUMN))
    button_rect = _MutedColumnDelegate.button_rect(button_cell)
    assert button_rect.top() - row.top() >= 3 and row.bottom() - button_rect.bottom() >= 3
    # Each header is aligned as its column: Shape on the right, over its numbers.
    shape_align = tree.model.headerData(1, Qt.Orientation.Horizontal, Qt.TextAlignmentRole)
    assert Qt.AlignmentFlag(shape_align) & Qt.AlignmentFlag.AlignRight
    assert header.sectionViewportPosition(Y_COLUMN) + 34 <= tree.view.viewport().width()
    modifier = "⌘" if sys.platform == "darwin" else "Ctrl"
    assert tree.button_tip(tree.node_at(energy)) == f"Show on the plot (Y or {modifier}-click)"

    # A click on the Y button of another row keeps that row's dataset; the selection stays.
    button = tree.view.visualRect(energy.sibling(energy.row(), Y_COLUMN)).center()
    qtbot.mouseClick(tree.view.viewport(), Qt.MouseButton.LeftButton, pos=button)
    assert [node.path for node in toggled] == ["/entry/plot/energy"]
    assert tree.view.currentIndex() == counts

    # Ctrl-click (the command key on macOS) anywhere on the row does the same.
    name = tree.view.visualRect(energy).center()
    qtbot.mouseClick(
        tree.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, name
    )
    assert [node.path for node in toggled][-1] == "/entry/plot/energy" and len(toggled) == 2
    assert tree.view.currentIndex() == counts

    # Y keeps the current row's dataset; P no longer does.
    qtbot.keyClick(tree.view, Qt.Key.Key_Y)
    assert toggled[-1].path == "/entry/plot/counts" and len(toggled) == 3
    qtbot.keyClick(tree.view, Qt.Key.Key_P)
    assert len(toggled) == 3

    # Ctrl-click on a group only does what it did before: nothing is kept.
    group_rect = tree.view.visualRect(plot_group).center()
    qtbot.mouseClick(
        tree.view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        group_rect,
    )
    assert len(toggled) == 3

    # The tree fills the row and the button of a kept dataset.
    tree.set_kept({"/entry/plot/energy": "#2f6fdc"})
    assert tree.is_kept(tree.node_at(energy)) and not tree.is_kept(tree.node_at(counts))
    assert tree.row_fill(tree.node_at(energy)).name() == "#2f6fdc"
    tree.cleanup()


def test_the_y_button_of_an_nxdata_group_keeps_its_default_dataset(qtbot, service, bec_file):
    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.resize(466, 400)
    tree.show()
    toggled = []
    tree.keep_toggled.connect(toggled.append)
    tree.set_file(str(bec_file), select_path=BPM4I_VALUE)
    qtbot.waitUntil(
        lambda: (tree.current_node() or H5Node("", "", "", "group")).path == BPM4I_VALUE
    )
    value = tree.view.currentIndex()
    signal_group = tree.node_at(value.parent())
    assert signal_group.nx_class == "NXdata" and tree.can_keep_row(signal_group)
    modifier = "⌘" if sys.platform == "darwin" else "Ctrl"
    assert tree.button_tip(signal_group) == (
        f"Show its default dataset on the plot (Y or {modifier}-click)"
    )

    tree.toggle_row(signal_group)
    qtbot.waitUntil(lambda: len(toggled) == 1)
    assert toggled[0].path == BPM4I_VALUE
    # Kept, the group row and the row of its default dataset both show as on the plot.
    tree.set_kept({BPM4I_VALUE: "#2f6fdc"})
    assert tree.is_kept(signal_group) and tree.is_kept(tree.node_at(value))
    assert tree.row_fill(signal_group).name() == "#2f6fdc"
    tree.cleanup()


def test_a_group_shows_the_kept_datasets_inside_it_collapsed_or_expanded(qtbot, service, bec_file):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.scan_list import on_color
    from bec_widgets.widgets.services.hdf5_viewer.style import DIM_ON_TINT_ALPHA, muted_color

    tree = H5Tree(service)
    qtbot.addWidget(tree)
    tree.resize(466, 400)
    tree.show()
    tree.set_file(str(bec_file), select_path=BPM4I_VALUE)
    qtbot.waitUntil(
        lambda: (tree.current_node() or H5Node("", "", "", "group")).path == BPM4I_VALUE
    )
    devices = tree.view.currentIndex().parent().parent().parent()
    assert tree.node_at(devices).path == "/entry/collection/devices"
    children = [tree.model.index(r, 0, devices) for r in range(tree.model.rowCount(devices))]
    rows = {tree.node_at(child).name: child for child in children}
    tree.set_kept({SAMX_VALUE: "#e05a2b", SAMY_VALUE: "#1aa874", "/entry/data/x": ""})
    # A device group takes the colour of the kept dataset inside it; one with none inside, none.
    assert [c.name() for c in tree.row_colors(rows["samx"])] == ["#e05a2b"]
    assert tree.row_colors(rows["bpm4i"]) == []
    # Several inside: all of their colours, in the order they were kept, collapsed or expanded,
    # so that the way to a kept dataset stays marked while the groups are open.
    tree.view.collapse(devices)
    assert [c.name() for c in tree.row_colors(devices)] == ["#e05a2b", "#1aa874"]
    tree.view.expand(devices)
    assert tree.view.isExpanded(devices)
    assert [c.name() for c in tree.row_colors(devices)] == ["#e05a2b", "#1aa874"]
    collection = devices.parent()
    assert tree.view.isExpanded(collection)
    assert [c.name() for c in tree.row_colors(collection)] == ["#e05a2b", "#1aa874"]
    # A row that only leads to curves is a tint with the colours of the theme; the row of a
    # curve is solid, its text and icon in black or white.
    assert tree.row_ink(devices) is None and tree.row_ink(rows["samx"]) is None
    tree.set_kept({SAMX_VALUE: "#e05a2b", SAMY_VALUE: "#1aa874", BPM4I_VALUE: "#2f6fdc"})
    value = tree.view.currentIndex()
    assert tree.node_at(value).path == BPM4I_VALUE
    assert tree.row_ink(value) == on_color(QColor("#2f6fdc"))
    delegate = tree.view.itemDelegateForIndex(devices)

    def icon_and_text(index):
        option = QStyleOptionViewItem()
        tree.view.initViewItemOption(option)
        delegate.initStyleOption(option, index)
        image = option.icon.pixmap(option.decorationSize).toImage()
        inks = {
            image.pixelColor(x, y).rgb()
            for x in range(image.width())
            for y in range(image.height())
            if image.pixelColor(x, y).alpha() > 128
        }
        return option.icon.cacheKey(), inks, option.palette.color(QPalette.ColorRole.Text).rgb()

    _key, inks, text = icon_and_text(value)
    assert inks == {text} == {on_color(QColor("#2f6fdc")).rgb()}
    for lead in (devices, rows["bpm4i"]):
        key, _inks, text = icon_and_text(lead)
        assert key == tree.model.itemFromIndex(lead).icon().cacheKey()
    # Secondary text is stronger on a tinted row than on a plain one, to stay readable.
    assert icon_and_text(devices.siblingAtColumn(1))[2] == muted_color(DIM_ON_TINT_ALPHA).rgb()
    plain = next(row for name, row in rows.items() if name not in ("samx", "samy", "bpm4i"))
    plain_shape = plain.siblingAtColumn(1)
    assert tree.row_colors(plain_shape) == []
    assert icon_and_text(plain_shape)[2] == muted_color().rgb()
    tree.cleanup()


def test_kept_datasets_are_drawn_next_to_the_selected_one_and_named_in_chips(
    qtbot, service, mocked_client, bec_file
):
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview.view == "map")  # a signal of a map scan
    preview._on_x_chosen(preview.x_combo.findData(""))  # Index
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")
    # Nothing kept: no chip.
    assert preview.kept_chips() == []

    preview.toggle_kept(kept_node(bec_file, SAMX_VALUE))
    preview.toggle_kept(kept_node(bec_file, "/entry/data/samx"))
    qtbot.waitUntil(
        lambda: preview.kept_curve(SAMX_VALUE) is not None
        and preview.kept_curve("/entry/data/samx") is not None
    )
    # Equal names get the group above them, in the chips and in the legend.
    assert [chip.label for chip in preview.kept_chips()] == ["samx/samx", "data/samx"]
    curves = {curve.name(): curve for curve in preview._waveform.curves}
    assert sorted(curves) == ["bpm4i", "data/samx", "samx/samx"]
    colours = [curves[name].config.color for name in ("bpm4i", "samx/samx", "data/samx")]
    assert len(set(colours)) == 3
    np.testing.assert_allclose(
        preview.kept_curve(SAMX_VALUE).yData, np.repeat(np.linspace(-1, 1, 4), 4)
    )
    # The chips carry the colour of their curve.
    assert [chip.color for chip in preview.kept_chips()] == colours[1:]

    # Taking one off leaves the colours of the others.
    preview.remove_kept(SAMX_VALUE)
    assert preview.kept_paths() == ["/entry/data/samx"]
    assert [curve.name() for curve in preview._waveform.curves] == ["bpm4i", "samx"]
    assert preview.kept_curve("/entry/data/samx").config.color == colours[2]

    # A kept dataset that is selected is drawn once, as the selected one.
    preview.show_node(kept_node(bec_file, "/entry/data/samx"))
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")
    assert [curve.name() for curve in preview._waveform.curves] == ["samx"]
    assert preview.kept_chips()[0].color == preview._curve.config.color

    preview.clear_kept()
    assert preview.kept_chips() == [] and preview.kept_paths() == []
    close_preview(preview)


def test_keeping_a_dataset_shows_the_line_and_other_views_only_the_selected_one(
    qtbot, service, mocked_client, bec_file
):
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(group(bec_file, "/entry/collection/devices/bpm4i"))
    qtbot.waitUntil(lambda: preview.view == "map" and preview._map_data is not None)

    preview.toggle_kept(kept_node(bec_file, SAMY_VALUE))
    assert preview.view == "line"
    qtbot.waitUntil(lambda: preview.kept_curve(SAMY_VALUE) is not None)
    # Against the scan axes, as chosen: samx for both curves.
    np.testing.assert_allclose(
        preview.kept_curve(SAMY_VALUE).xData, np.repeat(np.linspace(-1, 1, 4), 4)
    )

    # The table shows the selected dataset only; the kept datasets stay.
    preview._on_view_clicked("table")
    assert preview.stack.currentWidget() is preview.table
    assert [chip.path for chip in preview.kept_chips()] == [SAMY_VALUE]

    # Another signal of the map scan opens as a line while datasets are kept.
    preview._on_view_clicked("line")
    preview.show_node(group(bec_file, "/entry/collection/devices/samx"))
    qtbot.waitUntil(lambda: preview._overview is not None)
    assert preview.view == "line"
    close_preview(preview)


def legend_names(preview) -> list[str]:
    """The names in the legend of the preview's plot, top to bottom."""
    return [label.text for _sample, label in preview._waveform.plot_item.legend.items]


def test_the_legend_lists_the_kept_datasets_in_the_order_of_their_chips(
    qtbot, service, mocked_client, bec_file, monkeypatch
):
    read_curve = h5_reader.read_curve

    def slow_for_samx(file_path, path, *args, **kwargs):
        if path == SAMX_VALUE:
            time.sleep(0.3)  # the first kept dataset is read last
        return read_curve(file_path, path, *args, **kwargs)

    monkeypatch.setattr(h5_reader, "read_curve", slow_for_samx)
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview.view == "map")
    preview._on_x_chosen(preview.x_combo.findData(""))  # Index
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")
    for path in (SAMX_VALUE, SAMY_VALUE, "/entry/data/samx"):
        preview.toggle_kept(kept_node(bec_file, path))
    qtbot.waitUntil(lambda: len(preview._waveform.curves) == 4)
    assert [chip.label for chip in preview.kept_chips()] == ["samx/samx", "samy", "data/samx"]
    assert legend_names(preview) == ["bpm4i", "samx/samx", "samy", "data/samx"]
    close_preview(preview)


def test_a_kept_dataset_keeps_its_colour_when_it_is_selected(
    qtbot, service, mocked_client, bec_file
):
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview.view == "map")
    preview._on_x_chosen(preview.x_combo.findData(""))  # Index
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")
    first = preview._curve.config.color
    for path in (SAMX_VALUE, SAMY_VALUE):
        preview.toggle_kept(kept_node(bec_file, path))
    qtbot.waitUntil(lambda: preview.kept_curve(SAMY_VALUE) is not None)
    samy = preview.kept_curve(SAMY_VALUE).config.color
    assert first not in (samy, preview.kept_curve(SAMX_VALUE).config.color)

    # Selected, it is drawn in its chip's colour, not in the colour of a selected dataset.
    preview.show_node(kept_node(bec_file, SAMY_VALUE))
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")
    assert preview._curve.config.color == samy
    assert preview.kept_chips()[1].color == samy
    # Another chip taken off: it stays.
    preview.remove_kept(SAMX_VALUE)
    assert preview._curve.config.color == samy
    # The selection moves on: it stays too, and the selected one gets the first colour.
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview.kept_curve(SAMY_VALUE) is not None)
    assert preview.kept_curve(SAMY_VALUE).config.color == samy
    assert preview._curve.config.color == first
    close_preview(preview)


def test_the_y_axis_names_the_curve_only_while_one_is_drawn(
    qtbot, service, mocked_client, bec_file
):
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview.view == "map")
    preview._on_x_chosen(preview.x_combo.findData(""))  # Index
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")
    assert preview._waveform.y_label == "bpm4i"

    preview.toggle_kept(kept_node(bec_file, SAMX_VALUE))
    qtbot.waitUntil(lambda: preview.kept_curve(SAMX_VALUE) is not None)
    # The legend names the curves.
    assert preview._waveform.y_label == ""
    # The selected dataset kept too: one curve again.
    preview.show_node(kept_node(bec_file, SAMX_VALUE))
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")
    assert preview._waveform.y_label == "samx"
    preview.remove_kept(SAMX_VALUE)
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")
    assert preview._waveform.y_label == "bpm4i"
    close_preview(preview)


def test_a_kept_dataset_that_does_not_fit_the_axis_is_left_off_and_says_why(
    qtbot, service, mocked_client, bec_file
):
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(group(bec_file, "/entry/collection/devices/bpm4i"))
    qtbot.waitUntil(lambda: preview.view == "map" and preview._map_data is not None)
    preview.toggle_kept(kept_node(bec_file, WAVE_VALUE, rows=40))
    qtbot.waitUntil(lambda: preview.kept_problems() != {})

    # 40 rows do not fit the 16 points of the scan: not drawn against something else.
    reason = "it has 40 rows, the scan has 16 points"
    assert preview.kept_problems() == {WAVE_VALUE: reason}
    assert preview.kept_curve(WAVE_VALUE) is None
    chip = preview.kept_chips()[0]
    assert chip.problem == reason and chip.color == "" and chip.slot_color

    # Its own timestamps fit it.
    choose_x(preview, TIME)
    qtbot.waitUntil(lambda: preview.kept_curve(WAVE_VALUE) is not None)
    np.testing.assert_allclose(preview.kept_curve(WAVE_VALUE).xData, np.arange(40.0))

    # With Index everything fits.
    choose_x(preview, "")
    qtbot.waitUntil(lambda: preview.kept_curve(WAVE_VALUE) is not None)
    assert preview.kept_problems() == {}
    close_preview(preview)


def test_kept_datasets_are_looked_up_again_in_another_file(
    qtbot, service, mocked_client, bec_file, tmp_path
):
    other = write_bec_file(tmp_path / "S00023_master.h5")
    with h5py.File(other, "a") as handle:
        del handle["entry/collection/devices/wave"]
    settle(other)
    preview = make_preview(qtbot, service, mocked_client)
    preview.set_kept_file(str(bec_file))
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview.view == "map")
    preview._on_x_chosen(preview.x_combo.findData(""))
    qtbot.waitUntil(lambda: preview._overview is not None)
    preview.toggle_kept(kept_node(bec_file, WAVE_VALUE, rows=40))
    preview.toggle_kept(kept_node(bec_file, SAMX_VALUE))
    qtbot.waitUntil(lambda: preview.kept_curve(WAVE_VALUE) is not None)

    # The other scan's file: what exists there is drawn from it, the rest says so.
    preview.set_kept_file(str(other))
    preview.show_node(kept_node(other, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview.kept_curve(SAMX_VALUE) is not None)
    qtbot.waitUntil(lambda: preview.kept_problems() == {WAVE_VALUE: "not in this file"})
    assert preview.kept_curve(WAVE_VALUE) is None
    assert preview.kept_paths() == [WAVE_VALUE, SAMX_VALUE]
    # A dataset that is not there can still be taken off.
    preview.remove_kept(WAVE_VALUE)
    assert preview.kept_paths() == [SAMX_VALUE]
    close_preview(preview)


def test_the_number_of_kept_datasets_is_capped_and_the_cap_is_said_in_place(
    qtbot, service, mocked_client, bec_file, monkeypatch
):
    monkeypatch.setattr(h5_preview, "KEPT_MAX", 2)
    preview = make_preview(qtbot, service, mocked_client)
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    for path in (SAMX_VALUE, SAMY_VALUE, WAVE_VALUE):
        preview.toggle_kept(kept_node(bec_file, path))
    assert preview.kept_paths() == [SAMX_VALUE, SAMY_VALUE]
    assert preview.kept_note() == "2 kept at most: take one off to keep another"
    # Taking one off makes room, and the note goes.
    preview.remove_kept(SAMX_VALUE)
    assert preview.kept_note() == ""
    close_preview(preview)


def test_the_tree_and_the_preview_of_the_viewer_share_the_kept_datasets(qtbot, viewer, data_file):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    show_dataset(qtbot, viewer, data_file, "/entry/plot/counts")
    file_path = str(data_file)
    assert viewer.preview.kept_file() == file_path
    # The box stands above the tree; the plot pane has no x choice or chips of its own.
    holder = viewer.file_box.layout()
    assert holder.itemAt(0).widget() is viewer.file_box.top
    assert holder.itemAt(1).widget() is viewer.file_splitter
    assert not viewer.preview.x_combo.isVisibleTo(viewer.preview)
    assert not hasattr(viewer.preview, "kept_bar")
    node = h5_reader.describe(file_path, "/entry/plot/energy").node
    viewer.tree.keep_toggled.emit(node)
    assert viewer.preview.kept_paths() == [node.path]
    assert viewer.tree.is_kept(node)
    # Its row is filled with the colour of its curve, as a scan on the plot in the scan list.
    qtbot.waitUntil(lambda: bool(viewer.preview.kept_colors()[node.path]))
    color = viewer.preview.kept_colors()[node.path]
    assert viewer.tree.row_fill(node).name() == color.lower()
    assert any(label == "energy" and x for label, _mark, x in chips_of(viewer.file_box, "Y"))
    # Nothing of it on the scan's plot.
    assert viewer.signal_list.dataset_chips() == ()
    viewer.preview.clear_kept()
    assert not viewer.tree.is_kept(node)
    assert viewer.tree.row_fill(node) is None


def test_the_signals_and_the_file_tab_share_their_curves(qtbot, viewer):
    # pylint: disable=protected-access
    signals, preview, tree = viewer.signal_list, viewer.preview, viewer.tree
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    bpm3a = "/entry/collection/devices/bpm3a/bpm3a/value"
    bpm4i = "/entry/collection/devices/bpm4i/bpm4i/value"
    stamp = "/entry/collection/devices/samx/samx/timestamp"
    signals.toggle_y(BPM4I)
    viewer.file_dock.setAsCurrentTab()
    qtbot.waitUntil(lambda: tree.file_path != "")
    file_path = tree.file_path
    # The rows of the curves of Signals are filled in their colours; the File tab's own
    # plot keeps nothing of the scan's.
    for key, path in ((BPM3A, bpm3a), (BPM4I, bpm4i)):
        assert tree._kept[path] == signals.signal_color(key)
    assert preview.kept_paths() == [] and preview.kept_file() == ""

    def node(path):
        return h5_reader.describe(str(file_path), path).node

    # Y on a row changes the scan's plot: a signal as Y on its row in Signals.
    tree.keep_toggled.emit(node(bpm4i))
    assert signals.y_signals() == [BPM3A]
    tree.keep_toggled.emit(node(bpm4i))
    assert signals.y_signals() == [BPM3A, BPM4I]
    # A dataset that is no signal joins after the signals; Signals keeps its own.
    tree.keep_toggled.emit(node(stamp))
    assert viewer._file_paths == [stamp]
    assert [key for key, _label, _tag in field_chips(signals.box)] == [
        BPM3A,
        BPM4I,
        DatasetKey(stamp),
    ]
    signals.toggle_y(BPM3A)
    assert viewer._file_paths == [stamp] and signals.y_signals() == [BPM4I]

    # One Reset, the same in both tabs: the default curve, the scan's axes, nothing else.
    box = viewer.file_box
    assert box.reset_button.text() == signals.reset_axes_button.text() == "Reset"
    assert box.reset_button.toolTip() == signals.reset_axes_button.toolTip()
    assert box.reset_button.isVisibleTo(box)
    qtbot.mouseClick(box.reset_button, Qt.MouseButton.LeftButton)
    assert signals.y_signals() == [BPM3A] and signals.is_default()
    assert viewer._file_paths == [] and preview.x_is_auto()
    assert not box.reset_button.isVisibleTo(box)


def test_the_signals_and_the_file_tab_share_their_x_axis(qtbot, viewer):
    signals, preview, tree, box = viewer.signal_list, viewer.preview, viewer.tree, viewer.file_box
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    viewer.file_dock.setAsCurrentTab()
    qtbot.waitUntil(lambda: tree.file_path != "")
    file_path = tree.file_path
    value = "/entry/collection/devices/bpm4i/bpm4i/value"
    group = "/entry/collection/devices/bpm4i/bpm4i"
    stamp = "/entry/collection/devices/samx/samx/timestamp"

    def node(path):
        return h5_reader.describe(str(file_path), path).node

    # Rows that are signals have an X button, their group too; other rows none.
    assert tree.x_state(node(value)) is False and tree.x_state(node(group)) is False
    assert tree.x_state(node(stamp)) is None

    def x_chips(letter_box):
        role = next(role for role in letter_box.roles() if role.letter == "X")
        return [chip.label for chip in role.chips]

    # X in the tree: the signal is the x axis of both tabs.
    tree.x_toggled.emit(value)
    assert signals.x_signal() == BPM4I
    assert preview.x_choice == value
    assert tree.x_state(node(value)) is True and tree.x_state(node(group)) is True
    qtbot.waitUntil(lambda: x_chips(box) == x_chips(signals) == ["bpm4i"])
    # Its group's X takes it back to the scan's axes.
    tree.x_toggled.emit(group)
    assert signals.x_signal() is None and preview.x_is_auto()

    # Typing in X in the File tab offers what Signals offers, and takes it there.
    texts = [entry.text for entry in box.role_listing("X", "").entries]
    assert texts[:3] == ["Plot axis", "Index", "Timestamp"] and "bpm4i" in texts
    box.take_role("X", INDEX_X)
    assert signals.x_signal() == INDEX_X and preview.x_choice == ""
    signals.toggle_x(TIMESTAMP_X)
    assert preview.x_choice == TIME

    # The X key on the current row, as Y keeps it.
    tree.select_path(value)
    qtbot.waitUntil(lambda: tree.current_node() is not None and tree.current_node().path == value)
    qtbot.keyClick(tree.view, Qt.Key.Key_X)
    assert signals.x_signal() == BPM4I

    # One Reset: the scan's axes in both tabs.
    box.reset_button.click()
    assert signals.x_signal() is None and preview.x_is_auto()


def test_a_file_opened_by_hand_keeps_its_own_curves(qtbot, viewer, data_file):
    qtbot.waitUntil(lambda: len(viewer._curves) == 1)
    show_dataset(qtbot, viewer, data_file, "/entry/plot/counts")
    # Not the file of a scan: nothing of Signals is kept, the x axis and Reset are the File
    # tab's own, and no row has an X button.
    assert viewer.preview.kept_paths() == []
    assert viewer.file_box.is_default()
    role = next(role for role in viewer.file_box.roles() if role.letter == "X")
    assert [chip.key for chip in role.chips] == [("x", viewer.preview.x_data())]
    assert viewer.tree.x_state(viewer.tree.current_node()) is None


################################################################################
# The X and Y box of the File tab
################################################################################

GONE_VALUE = "/entry/collection/devices/gone/gone/value"


def make_box(qtbot, service, mocked_client) -> FileBox:
    """The box of the File tab over an empty content, with its own preview."""
    preview = make_preview(qtbot, service, mocked_client)
    box = FileBox(preview, service, QWidget())
    qtbot.addWidget(box)
    box.resize(466, 500)
    box.show()
    qtbot.waitExposed(box)
    return box


def close_box(box):
    box.cleanup()
    close_preview(box.preview)


def chips_of(box, letter) -> list[tuple[str, str, bool]]:
    """The chips of a field: name, the word after it, and whether it has an x."""
    return [
        (chip.info.label, chip.info.mark, chip.remove_button is not None)
        for chip in box.box.fields[letter].flow.chips
    ]


def show_line(qtbot, preview, file_path, path=BPM4I_VALUE):
    """Show a signal of the map scan as a line against the row number."""
    preview.show_node(kept_node(file_path, path))
    qtbot.waitUntil(lambda: preview.view == "map")
    choose_x(preview, "")  # Index
    qtbot.waitUntil(lambda: preview._overview is not None and preview.view == "line")


def test_the_x_field_of_the_file_tab_follows_the_axes_the_file_names(
    qtbot, service, mocked_client, bec_file
):
    box = make_box(qtbot, service, mocked_client)
    preview = box.preview
    # Nothing selected and nothing kept: no box.
    assert not box.box.isVisibleTo(box)
    preview.show_node(kept_node(bec_file, BPM4I_VALUE))
    qtbot.waitUntil(lambda: preview.view == "map")
    assert box.box.isVisibleTo(box)
    # On auto it reads as the X of the Signals tab: the axes and "auto", no x.
    assert chips_of(box, "X") == [("samx, samy", "auto", False)]
    assert box.box.fields["X"].flow.chips[0].info.tip == file_box.AUTO_TIP
    assert not box.reset_button.isVisibleTo(box)
    # Its list: Index and Timestamp under Plot axis, the scan's axes in a group of their own.
    listing = box.role_listing("X", "")
    assert [(e.kind, e.text, e.state) for e in listing.entries] == [
        ("head", "Plot axis", ""),
        ("entry", "Index", ""),
        ("entry", "Timestamp", ""),
        ("head", "Scan axes", ""),
        ("entry", "samx, samy", "on"),
    ]

    # Typed, Enter makes the best fit the x axis; Reset shows after the change by hand.
    edit = focus_field(qtbot, box, "X")
    qtbot.keyClicks(edit, "ind")
    assert box.typing.list.marked() == 0
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: preview.view == "line")
    assert preview.x_data() == "" and not preview.x_is_auto()
    assert chips_of(box, "X") == [("Index", "", False)]
    assert box.reset_button.isVisibleTo(box) and box.reset_button.text() == "Reset"

    # The choice is kept for another dataset.
    preview.show_node(kept_node(bec_file, SAMY_VALUE))
    qtbot.waitUntil(lambda: preview.node.path == SAMY_VALUE and preview.view == "line")
    assert chips_of(box, "X") == [("Index", "", False)]

    # Reset: the file's axes again.
    box.reset_button.click()
    qtbot.waitUntil(lambda: preview.x_is_auto())
    assert chips_of(box, "X")[0][1:] == ("auto", False)
    assert not box.reset_button.isVisibleTo(box)
    close_box(box)


def test_the_y_field_shows_the_selected_dataset_then_the_kept_ones(
    qtbot, service, mocked_client, bec_file
):
    box = make_box(qtbot, service, mocked_client)
    preview = box.preview
    show_line(qtbot, preview, bec_file)
    # The selected dataset, tagged and without an x: it follows the selection.
    assert chips_of(box, "Y") == [("bpm4i", "selected", False)]
    selected = box.box.fields["Y"].flow.chips[0].info
    assert selected.swatch.color == preview._curve.config.color
    assert box.box.fields["Y"].edit.placeholderText() == "Add a dataset…"

    for path in (SAMX_VALUE, SAMY_VALUE, GONE_VALUE):
        preview.toggle_kept(kept_node(bec_file, path))
    qtbot.waitUntil(lambda: all_drawn(preview, SAMX_VALUE, SAMY_VALUE))
    qtbot.waitUntil(lambda: GONE_VALUE in preview.kept_problems())
    # Then the kept ones, each in the colour of its curve and with its x.
    assert chips_of(box, "Y") == [
        ("bpm4i", "selected", False),
        ("samx", "", True),
        ("samy", "", True),
        ("gone", "", True),
    ]
    chips = box.box.fields["Y"].flow.chips
    assert [chip.info.swatch.color for chip in chips[1:3]] == [
        preview.kept_curve(SAMX_VALUE).config.color,
        preview.kept_curve(SAMY_VALUE).config.color,
    ]
    # One that is not drawn is greyed and says why.
    assert chips[3].info.problem == "not in this file"
    assert chips[3].toolTip() == "Not drawn: not in this file."
    assert box.reset_button.isVisibleTo(box)

    # The x of a chip takes its dataset off.
    chips[1].remove_button.click()
    assert preview.kept_paths() == [SAMY_VALUE, GONE_VALUE]
    # Backspace in the empty field takes the last one off, Left and Delete a marked one.
    edit = focus_field(qtbot, box, "Y")
    qtbot.keyClick(edit, Qt.Key.Key_Backspace)
    assert preview.kept_paths() == [SAMY_VALUE]
    qtbot.keyClick(edit, Qt.Key.Key_Left)
    qtbot.keyClick(edit, Qt.Key.Key_Delete)
    assert preview.kept_paths() == []
    # The chip of the selected dataset is not taken off.
    qtbot.keyClick(edit, Qt.Key.Key_Backspace)
    assert chips_of(box, "Y") == [("bpm4i", "selected", False)]

    # The selected dataset kept too: one chip, tagged, with its x.
    preview.toggle_kept(preview.node)
    assert chips_of(box, "Y") == [("bpm4i", "selected", True)]
    # The chip follows the selection; the kept dataset stays.
    preview.show_node(kept_node(bec_file, SAMY_VALUE))
    qtbot.waitUntil(lambda: preview._overview is not None and preview.node.path == SAMY_VALUE)
    assert chips_of(box, "Y") == [("samy", "selected", False), ("bpm4i", "", True)]
    close_box(box)


def test_the_cap_of_the_kept_datasets_is_said_under_the_box(
    qtbot, service, mocked_client, bec_file, monkeypatch
):
    monkeypatch.setattr(h5_preview, "KEPT_MAX", 2)
    monkeypatch.setattr(file_box, "KEPT_MAX", 2)
    box = make_box(qtbot, service, mocked_client)
    preview = box.preview
    show_line(qtbot, preview, bec_file)
    for path in (SAMX_VALUE, SAMY_VALUE, WAVE_VALUE):
        preview.toggle_kept(kept_node(bec_file, path))
    assert box.note.text() == "2 kept at most: take one off to keep another"
    assert box.note.isVisibleTo(box)
    preview.remove_kept(SAMX_VALUE)
    assert not box.note.isVisibleTo(box)
    close_box(box)


def test_typing_in_the_y_field_lists_the_datasets_of_the_file_that_can_be_a_curve(
    qtbot, service, mocked_client, bec_file
):
    box = make_box(qtbot, service, mocked_client)
    preview = box.preview
    show_line(qtbot, preview, bec_file)
    preview.toggle_kept(kept_node(bec_file, SAMX_VALUE))
    edit = focus_field(qtbot, box, "Y")
    qtbot.keyClicks(edit, "samx")
    # The file is listed once, off the GUI thread; the list fills when it is.
    qtbot.waitUntil(lambda: box.typing.is_open("Y") and listed(box)[0][0] == "entry")
    # The same matcher as in the Signals tab; a kept one keeps its place with a tick. A link
    # (/entry/data/samx) is the dataset it points to, listed once.
    assert listed(box) == [
        ("entry", "samx", "on the plot"),
        ("entry", "samx_setpoint", "devices · 16"),
    ]
    setpoint = "/entry/collection/devices/samx/samx_setpoint/value"
    assert box.typing.list.marked() == 1
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert preview.kept_paths() == [SAMX_VALUE, setpoint]
    assert edit.text() == "" and not box.typing.is_open()

    # The full list holds only datasets that can be a curve.
    listing = box.role_listing("Y", "")
    assert listing.entries[0].kind == "head" and listing.entries[0].text == "Datasets"
    nodes = h5_reader.curve_datasets(str(bec_file))
    assert [e.key[1] for e in listing.entries[1:]] == [node.path for node in nodes]
    assert all(node.ndim == 1 and node.size > 1 and node.is_numeric for node in nodes)
    close_box(box)


def test_datasets_are_listed_under_the_group_that_names_them():
    assert file_box.group_of(BPM4I_VALUE) == "devices"
    assert file_box.group_of("/entry/data/samx") == "data"
    assert file_box.group_of("/counts") == "/"


def test_the_fields_say_they_are_not_used_where_the_plot_draws_no_curves(
    qtbot, service, mocked_client, bec_file
):
    box = make_box(qtbot, service, mocked_client)
    preview = box.preview
    show_line(qtbot, preview, bec_file)
    preview.toggle_kept(kept_node(bec_file, SAMY_VALUE))
    preview._on_view_clicked("table")
    assert preview.view == "table"
    for letter in ("X", "Y"):
        field = box.box.fields[letter]
        assert field.role.inactive == "Not used in Table"
        assert field.edit.placeholderText() == "Not used in Table"
        assert not field.edit.isEnabled()
    # The kept datasets stay in view and can be taken off.
    assert chips_of(box, "Y") == [("samy", "", True)]
    assert box.role_listing("Y", "").entries == ()
    preview._on_view_clicked("line")
    assert box.box.fields["Y"].role.inactive == ""
    assert chips_of(box, "Y")[0] == ("bpm4i", "selected", False)
    close_box(box)


def keep_in_viewer(viewer, file_path, *paths):
    """Keep datasets of the file the viewer shows."""
    for path in paths:
        viewer.preview.toggle_kept(h5_reader.describe(str(file_path), path).node)


def all_drawn(preview, *paths) -> bool:
    """Whether the Line view draws all these kept datasets."""
    return all(preview.kept_curve(path) is not None for path in paths)


def test_add_to_plot_sends_the_datasets_of_the_scans_plot_with_its_signals(
    qtbot, viewer, history, mocked_client
):
    # pylint: disable=import-outside-toplevel,protected-access
    from bec_widgets.widgets.services.hdf5_viewer.plot_targets import held_history_curves

    target = file_target(qtbot, mocked_client)
    qtbot.waitUntil(lambda: bool(viewer._curves) and not viewer._lines_loading())
    file_tab_of_scan(qtbot, viewer, history[2].file_path)
    stamp = "/entry/collection/devices/samx/samx/timestamp"
    click_y(qtbot, viewer, stamp)
    qtbot.waitUntil(lambda: file_curve(viewer, stamp) is not None)
    header, offers = viewer.signal_offers()
    assert header == "Lines of bpm3a, timestamp · scan 12"
    assert offers["Waveform"].hint == "2 curves"

    # The signal as its history curve, the dataset as a copy of what the plot draws.
    viewer.add_to_plot(target, "TargetPlot")
    label = f"S00012_master.h5 {stamp}"
    names = ["bpm3a-bpm3a-scan-12", label]
    qtbot.waitUntil(lambda: [curve.name() for curve in target.curves] == names)
    assert held_history_curves(target) == {("scan-2", "bpm3a", "bpm3a")}
    copy = next(curve for curve in target.curves if curve.name() == label)
    assert np.allclose(copy.yData, np.arange(20))
    assert viewer.add_button.property("feedback") == (
        "Added 2 curves to TargetPlot, copies not saved with the workspace"
    )
    # Sent again: nothing doubled.
    viewer.add_to_plot(target, "TargetPlot")
    assert [curve.name() for curve in target.curves] == names


def test_add_to_plot_of_another_file_sends_the_others_when_one_cannot_go(
    qtbot, viewer, mocked_client, tmp_path, monkeypatch
):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer import hdf5_viewer

    monkeypatch.setattr(hdf5_viewer, "COPY_MAX_POINTS", 10)
    path = tmp_path / "other.h5"
    with h5py.File(path, "w") as handle:
        handle["short"] = np.arange(5.0)
        handle["long"] = np.arange(20.0)
    settle(path)
    target = file_target(qtbot, mocked_client)
    # Not the file of a scan: the File tab keeps datasets on its own plot, as before.
    show_dataset(qtbot, viewer, path, "/short")
    keep_in_viewer(viewer, path, "/long")
    qtbot.waitUntil(lambda: all_drawn(viewer.preview, "/long"))
    assert viewer.right_stack.currentWidget() is viewer.preview
    viewer.add_file_to_plot(target, "TargetPlot")
    qtbot.waitUntil(lambda: [curve.name() for curve in target.curves] == ["other.h5 /short"])
    qtbot.waitUntil(lambda: viewer.file_add_button.isEnabled())
    assert viewer.file_add_button.property("feedback") == (
        "Added 1 curve to TargetPlot, 1 could not be added; "
        "left out long (too many rows to copy: 20), copies not saved with the workspace"
    )


KEEP = object()


def foreign_bec_file(
    tmp_path, source, scan_id="ext-1", status=KEEP, name="S00042_master.h5", number=42
):
    """A copy of a scan file that BEC wrote, naming a scan the history does not know."""
    # pylint: disable=import-outside-toplevel
    import shutil

    target = tmp_path / "elsewhere" / name
    target.parent.mkdir(exist_ok=True)
    shutil.copy(source, target)
    with h5py.File(target, "a") as handle:
        bec = handle["entry/collection/metadata/bec"]
        del bec["scan_id"]
        bec.create_dataset("scan_id", data=scan_id)
        bec["scan_number"][()] = number
        if status is not KEEP:
            del bec["status"]
            if status is not None:
                bec.create_dataset("status", data=status)
        handle["entry"].attrs["start_time"] = "2025-11-19T14:23:00"
        handle["entry"].attrs["end_time"] = "2025-11-19T14:24:15"
    settle(target)
    return str(target)


def import_file(qtbot, viewer, file_path):
    viewer.open_file(file_path)
    qtbot.waitUntil(lambda: viewer.scan_list.model.entry(f"imported:{file_path}") is not None)
    qtbot.waitUntil(lambda: viewer.scan_list.current_entry().file_path == file_path)
    wait_for_switch(qtbot, viewer)
    return viewer.scan_list.model.entry(f"imported:{file_path}")


def test_the_scan_of_a_file_bec_wrote_is_read_without_its_data(history, data_file, tmp_path):
    scan = h5_reader.bec_scan_file(history[1].file_path)
    assert (scan.scan_id, scan.scan_number, scan.dataset_number) == ("scan-1", 11, 1)
    assert (scan.scan_name, scan.status, scan.num_points) == ("line_scan", "closed", 20)
    assert scan.request_inputs["arg_bundle"] == ["samx", -1, 1]
    assert scan.scan_report_devices == ("samx",)
    assert scan.stored_data_info["camera"]["camera"] == {"shape": (20, 8, 8), "dtype": "float64"}
    assert scan.stored_data_info["wave"]["wave"]["shape"] == (1000,)
    assert not scan.truncated
    assert h5_reader.bec_scan_file(history[1].file_path, max_signals=2).truncated

    other = foreign_bec_file(tmp_path, history[1].file_path)
    scan = h5_reader.bec_scan_file(other)
    assert scan.start_time == datetime(2025, 11, 19, 14, 23).timestamp()
    assert scan.end_time - scan.start_time == 75
    # Files without the scan id of BEC are no scan.
    assert h5_reader.bec_scan_file(str(data_file)) is None
    plain = tmp_path / "plain.h5"
    write_bec_file(plain, "line_scan", ["samx"], 5)
    assert h5_reader.bec_scan_file(str(plain)) is None


def test_a_bec_file_outside_the_history_is_listed_under_imported(qtbot, viewer, history, tmp_path):
    # pylint: disable=import-outside-toplevel
    from datetime import date

    from bec_widgets.utils.imported_scans import imported_scan_item
    from bec_widgets.widgets.services.hdf5_viewer.scan_list import row_when

    file_path = foreign_bec_file(tmp_path, history[1].file_path)
    assert not viewer.file_tab_current()
    entry = import_file(qtbot, viewer, file_path)

    assert entry.imported and entry.scan_id == f"imported:{file_path}"
    assert viewer.scan_list.model.rowCount() == 4
    # The tab in front stays; the row is selected and named by its date, under its own head.
    assert not viewer.file_tab_current()
    heads = [(head.label, head.count) for head in viewer.scan_list.view.heads.values()]
    assert heads == [("Imported", 1), ("Today", 3)]
    assert row_when(entry, date(2025, 12, 1)) == "19 Nov"
    assert row_when(entry, date(2026, 1, 2)) == "19 Nov 2025"
    tip = viewer.scan_list.model.tooltip(entry)
    assert "not in the scan history" in tip and "ext-1" not in tip
    assert viewer.status_label.full_text() == file_path

    # Its signals are those the file stored, and its curves come from the file.
    qtbot.waitUntil(lambda: (entry.scan_id, "bpm3a", "bpm3a") in viewer._curves)
    assert imported_scan_item(viewer.client, entry.scan_id).metadata["bec"]["scan_id"] == (
        entry.scan_id
    )
    assert ("camera", "camera") in {signal.key for signal in viewer.signal_list.signals()}

    # A search applies to it as to any row, and the file's name finds it.
    viewer.scan_list.search_edit.setText("S00042")
    assert viewer.scan_list.filter_model.rowCount() == 1
    viewer.scan_list.search_edit.setText("line_scan")
    assert viewer.scan_list.filter_model.rowCount() == 4
    viewer.scan_list.search_edit.clear()

    # A refresh of the history keeps it.
    viewer.history_manager.scan_history_refreshed.emit([msg.model_dump() for msg in history])
    qtbot.waitUntil(lambda: viewer.scan_list.model.entry(entry.scan_id) is not None)
    assert viewer.scan_list.model.rowCount() == 4


def test_a_file_opened_again_or_of_a_history_scan_adds_no_row(qtbot, viewer, history, tmp_path):
    file_path = foreign_bec_file(tmp_path, history[1].file_path)
    import_file(qtbot, viewer, file_path)
    viewer.scan_list.select("scan-0")

    viewer.open_file(file_path)
    qtbot.waitUntil(lambda: viewer.scan_list.current_entry().file_path == file_path)
    assert viewer.scan_list.model.rowCount() == 4

    # A copy of a history scan's file elsewhere selects that scan's row.
    copy = foreign_bec_file(tmp_path, history[0].file_path, scan_id="scan-0", name="copy.h5")
    viewer.open_file(copy)
    qtbot.waitUntil(lambda: viewer.scan_list.current_entry().scan_id == "scan-0")
    assert viewer.scan_list.model.rowCount() == 4


def test_a_file_not_written_by_bec_still_opens_in_the_file_tab(qtbot, viewer, tmp_path):
    plain = tmp_path / "plain.h5"
    write_bec_file(plain, "line_scan", ["samx"], 5)
    settle(plain)
    viewer.open_file(str(plain))
    qtbot.waitUntil(viewer.file_tab_current)
    assert viewer.scan_list.current_entry() is None
    assert viewer.scan_list.model.rowCount() == 3
    assert viewer.status_label.full_text() == str(plain)


def test_an_imported_scan_is_taken_off_the_list_by_the_menu_or_the_delete_key(
    qtbot, viewer, history, tmp_path
):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.utils.imported_scans import imported_scan_item

    first = import_file(qtbot, viewer, foreign_bec_file(tmp_path, history[1].file_path))
    second = import_file(
        qtbot,
        viewer,
        foreign_bec_file(tmp_path, history[0].file_path, scan_id="ext-2", name="S00043.h5"),
    )
    # A scan of the history offers no removal.
    assert not hasattr(viewer.scan_menu(viewer.scan_list.model.entry("scan-2")), "remove_action")

    # The menu takes the selected one off; the newest scan of the history is selected then.
    viewer.scan_menu(second).remove_action.trigger()
    assert viewer.scan_list.model.entry(second.scan_id) is None
    assert viewer.scan_list.current_entry().scan_id == "scan-2"
    assert imported_scan_item(viewer.client, second.scan_id) is None
    assert os.path.exists(second.file_path)

    # Delete takes it off only while the list has the keyboard focus, and only an imported row.
    view = viewer.scan_list.view
    viewer.scan_list.select(first.scan_id)
    viewer.scan_list.search_edit.setFocus()
    qtbot.keyClick(viewer.scan_list.search_edit, Qt.Key.Key_Delete)
    qtbot.keyClick(viewer.scan_list.search_edit, Qt.Key.Key_Backspace)
    assert viewer.scan_list.model.entry(first.scan_id) is not None
    viewer.scan_list.select("scan-1")
    qtbot.keyClick(view, Qt.Key.Key_Delete)
    assert viewer.scan_list.model.rowCount() == 4
    viewer.scan_list.select(first.scan_id)
    qtbot.keyClick(view, Qt.Key.Key_Backspace)
    assert viewer.scan_list.model.rowCount() == 3
    assert viewer.scan_list.current_entry().scan_id == "scan-2"
    assert imported_scan_item(viewer.client, first.scan_id) is None


def test_removing_a_pinned_imported_scan_takes_it_out_of_the_comparison(
    qtbot, viewer, history, tmp_path
):
    entry = import_file(qtbot, viewer, foreign_bec_file(tmp_path, history[1].file_path))
    viewer.scan_list.select("scan-2")
    wait_for_switch(qtbot, viewer)
    viewer.scan_list.model.toggle_pin(entry.scan_id)
    qtbot.waitUntil(lambda: (entry.scan_id, "bpm3a", "bpm3a") in viewer._curves)
    assert "compared with 42" in viewer.plot_subtitle.full_text()

    viewer.remove_imported(entry)

    assert viewer.scan_list.current_entry().scan_id == "scan-2"
    assert not viewer.scan_list.pinned_entries()
    qtbot.waitUntil(lambda: set(viewer._curves) == {("scan-2", "bpm3a", "bpm3a")})
    assert "compared" not in viewer.plot_subtitle.full_text()


@pytest.mark.parametrize("status", [None, "", "unheard_of"])
def test_an_imported_scan_without_a_known_status_has_the_neutral_mark(
    qtbot, viewer, history, tmp_path, status
):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.scan_list import Tone, scan_status

    entry = import_file(
        qtbot, viewer, foreign_bec_file(tmp_path, history[1].file_path, status=status)
    )
    icon, tone, word = scan_status(entry)
    assert (icon, tone) == ("help", Tone.NEUTRAL)
    assert word != "Finished"
    assert entry.status != "closed"


def test_an_imported_file_that_was_once_written_open_is_not_shown_running(
    qtbot, viewer, history, tmp_path
):
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.services.hdf5_viewer.scan_list import Tone, scan_status

    entry = import_file(
        qtbot, viewer, foreign_bec_file(tmp_path, history[1].file_path, status="open")
    )
    assert scan_status(entry)[:2] == ("help", Tone.NEUTRAL)


@pytest.mark.parametrize(
    "lose, title", [("delete", "Not found"), ("move", "Not found"), ("deny", "No permission")]
)
def test_an_imported_scan_whose_file_is_gone_keeps_its_row_and_says_so_in_place(
    qtbot, viewer, history, tmp_path, lose, title
):
    file_path = foreign_bec_file(tmp_path, history[1].file_path)
    entry = import_file(qtbot, viewer, file_path)
    qtbot.waitUntil(lambda: (entry.scan_id, "bpm3a", "bpm3a") in viewer._curves)
    viewer.scan_list.select("scan-2")
    wait_for_switch(qtbot, viewer)
    if lose == "delete":
        os.remove(file_path)
    elif lose == "move":
        os.rename(file_path, f"{file_path}.moved")
    else:
        os.chmod(file_path, 0)

    try:
        with mock.patch.object(ErrorPopupUtility(), "custom_exception_hook") as popup:
            viewer.scan_list.select(entry.scan_id)
            wait_for_switch(qtbot, viewer)
            qtbot.waitUntil(lambda: viewer.plot_stack.currentWidget() is viewer.plot_state)
            viewer.file_dock.setAsCurrentTab()
            qtbot.waitUntil(lambda: viewer.preview.state_page.title.text() == title)
    finally:
        if lose == "deny":
            os.chmod(file_path, 0o644)

    popup.assert_not_called()
    # The row stays; the plot and the File tab say in place what is wrong with the file.
    assert viewer.scan_list.model.entry(entry.scan_id) is not None
    assert viewer.scan_list.current_entry().scan_id == entry.scan_id
    assert viewer.plot_state.title.text() == "The plot could not be read"
    if lose != "deny":
        assert "not there any more" in viewer.plot_state.text.text()
        assert viewer.preview.state_page.text.text() == "S00042_master.h5 was moved or deleted."


def test_an_imported_scan_with_the_number_of_a_session_scan_is_told_apart_by_its_date(
    qtbot, viewer, history, tmp_path
):
    file_path = foreign_bec_file(tmp_path, history[1].file_path, number=12)
    imported = import_file(qtbot, viewer, file_path)
    key = (imported.scan_id, "bpm3a", "bpm3a")
    session = ("scan-2", "bpm3a", "bpm3a")
    scan_list = viewer.scan_list

    for selected, pinned in ((imported.scan_id, "scan-2"), ("scan-2", imported.scan_id)):
        with mock.patch.object(ErrorPopupUtility(), "custom_exception_hook") as popup:
            scan_list.select(selected)
            wait_for_switch(qtbot, viewer)
            scan_list.model.toggle_pin(pinned)
            qtbot.waitUntil(lambda: set(viewer._curves) == {key, session})
        popup.assert_not_called()
        # Both are drawn, each in the colour of its scan.
        colours = {k: curve.config.color for k, (curve, _live) in viewer._curves.items()}
        assert colours[key] != colours[session]
        # The imported curve carries its start time, whichever was there first.
        legend = legend_texts(viewer)
        assert legend[key] == "bpm3a-bpm3a-scan-12-20251119-1423"
        assert legend[session] == "bpm3a-bpm3a-scan-12"
        # The subtitle names the compared scan by its number and start.
        label = scan_list.model.scan_label(scan_list.model.entry(pinned))
        assert re.fullmatch(r"12 \(\d+ \w{3}( \d{4})? \d\d:\d\d\)", label)
        assert f"compared with {label}" in viewer.plot_subtitle.full_text()
        if pinned == imported.scan_id:
            assert label == "12 (19 Nov 2025 14:23)"
        scan_list.model.toggle_pin(pinned)
        qtbot.waitUntil(lambda: len(viewer._curves) == 1)


def test_open_file_sits_beside_the_scan_search_and_gives_way_to_its_icon(qtbot, viewer):
    scan_list, button = viewer.scan_list, viewer.open_button
    viewer.show()
    qtbot.waitExposed(viewer)
    # At the right end of the search row, as tall as the field, after it in the keyboard order.
    search = scan_list.search_edit
    assert button.geometry().left() > search.geometry().right()
    assert button.geometry().top() == search.geometry().top()
    assert button.height() == search.height()

    def next_stop(widget):
        widget = widget.nextInFocusChain()
        while not (widget.focusPolicy() & Qt.FocusPolicy.TabFocus and widget.isVisible()):
            widget = widget.nextInFocusChain()
        return widget

    assert next_stop(search) is button
    assert next_stop(button) is scan_list.ending_buttons["all"]
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert "Imported" in button.toolTip()

    # The field needs its whole placeholder, measured in its font: without that room beside
    # the text, the button shows its icon alone, the text in the tooltip.
    search_need = scan_list.search_field_need()
    metrics = search.fontMetrics()
    assert search_need > metrics.horizontalAdvance("Search scans")
    assert search_need < search.sizeHint().width()
    text_width = button.sizeHint().width()
    scan_list.resize(search_need + text_width - 10, scan_list.height())
    scan_list._fit_texts()  # pylint: disable=protected-access
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert button.toolTip() == "Open file…"
    scan_list.resize(search_need + text_width + 10, scan_list.height())
    scan_list._fit_texts()  # pylint: disable=protected-access
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon

    # A click still asks for a file, which then opens as before.
    with mock.patch(
        "bec_widgets.widgets.services.hdf5_viewer.hdf5_viewer.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ) as dialog:
        button.click()
    dialog.assert_called_once()
