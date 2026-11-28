"""Tests for the reader of the HDF5 viewer: what it reads, and that it never holds a file."""

import os
import subprocess
import sys

import h5py
import numpy as np
import pytest

from bec_widgets.widgets.services.hdf5_viewer import h5_reader
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import H5ReadError

ROWS = 50_000


@pytest.fixture
def scan_files(tmp_path):
    """A master file with a default plot, a link into a detector file and a broken link."""
    master = tmp_path / "S00001_master.h5"
    detector = tmp_path / "S00001_detector.h5"
    with h5py.File(detector, "w") as handle:
        frames = np.arange(4 * 6 * 8, dtype=np.uint16).reshape(4, 6, 8)
        handle.create_dataset("entry/data/data", data=frames, chunks=(1, 6, 8), compression="gzip")
    with h5py.File(master, "w") as handle:
        handle.attrs["default"] = "entry"
        entry = handle.create_group("entry")
        entry.attrs["NX_class"] = "NXentry"
        entry.attrs["default"] = "plot"
        plot = entry.create_group("plot")
        plot.attrs["NX_class"] = "NXdata"
        plot.attrs["signal"] = "counts"
        plot.attrs["axes"] = "energy"
        counts = np.sin(np.arange(ROWS) / 500.0)
        counts[31_415] = 99.0
        dataset = plot.create_dataset("counts", data=counts)
        dataset.attrs["units"] = "counts"
        energy = plot.create_dataset("energy", data=np.linspace(8000.0, 9000.0, ROWS))
        energy.attrs["units"] = "eV"
        plot.create_dataset("other_length", data=np.arange(7))
        entry.create_dataset("name", data="Cu foil")
        entry.create_dataset("grid", data=np.arange(12.0).reshape(3, 4))
        entry["detector"] = h5py.ExternalLink(detector.name, "/entry/data")
        entry["gone_file"] = h5py.ExternalLink("S00001_missing.h5", "/entry/data")
        entry["gone"] = h5py.SoftLink("/entry/not_there")
    return master, detector


def open_file_count() -> int:
    """Number of HDF5 files this process holds open."""
    return h5py.h5f.get_obj_count(h5py.h5f.OBJ_ALL, h5py.h5f.OBJ_FILE)


def test_list_children_describes_one_group_and_follows_no_link(scan_files):
    master, _detector = scan_files
    nodes = {node.name: node for node in h5_reader.list_children(str(master), "/entry")}

    assert nodes["plot"].kind == "group"
    assert nodes["plot"].nx_class == "NXdata"
    assert nodes["plot"].is_default
    assert nodes["plot"].n_children == 3
    assert nodes["name"].kind == "dataset" and not nodes["name"].is_numeric
    assert nodes["grid"].shape == (3, 4)
    # Links into other files are named, not opened: the missing file does no harm.
    assert nodes["detector"].kind == "link"
    assert nodes["detector"].link_path == "/entry/data"
    assert nodes["gone_file"].kind == "link"
    assert nodes["gone"].kind == "broken"
    assert open_file_count() == 0


def test_resolve_link_opens_the_linked_file_only_when_asked(scan_files):
    master, detector = scan_files
    link = next(n for n in h5_reader.list_children(str(master), "/entry") if n.name == "detector")

    target = h5_reader.resolve_link(link)

    assert target.kind == "group"
    assert target.file_path == str(detector)
    assert target.name == "detector"
    children = h5_reader.list_children(target.file_path, target.path)
    assert [(child.name, child.shape) for child in children] == [("data", (4, 6, 8))]

    missing = next(
        n for n in h5_reader.list_children(str(master), "/entry") if n.name == "gone_file"
    )
    with pytest.raises(H5ReadError) as error:
        h5_reader.resolve_link(missing)
    assert error.value.kind == "missing"


def test_describe_reports_storage_attributes_and_x_axes(scan_files):
    master, detector = scan_files
    details = h5_reader.describe(str(master), "/entry/plot/counts")

    assert details.attributes == {"units": "counts"}
    assert details.logical_bytes == ROWS * 8
    assert details.node.units == "counts"
    # Only datasets with one value per row are offered, the axis the file names first.
    assert [(axis.name, axis.preferred) for axis in details.x_candidates] == [("energy", True)]
    assert details.x_candidates[0].units == "eV"

    stack = h5_reader.describe(str(detector), "/entry/data/data")
    assert stack.chunks == (1, 6, 8)
    assert stack.compression.startswith("gzip")
    assert 0 < stack.stored_bytes

    group = h5_reader.describe(str(master), "/entry/plot")
    assert group.node.kind == "group"
    assert group.attributes["signal"] == "counts"


def test_read_curve_returns_all_rows_of_a_short_range(scan_files):
    master, _detector = scan_files
    curve = h5_reader.read_curve(str(master), "/entry/plot/counts", start=100, stop=110)

    assert not curve.reduced
    assert curve.total == ROWS
    np.testing.assert_array_equal(curve.x, np.arange(100, 110))
    np.testing.assert_allclose(curve.y, np.sin(np.arange(100, 110) / 500.0))
    assert curve.bytes_read == 80


def test_read_curve_reduces_a_long_signal_and_keeps_its_peak(scan_files):
    master, _detector = scan_files
    curve = h5_reader.read_curve(str(master), "/entry/plot/counts", max_points=1000)

    assert curve.reduced
    assert len(curve.x) == len(curve.y) <= 1000
    # The single outlier survives, which plain striding would lose.
    assert curve.y.max() == 99.0
    assert curve.x[0] == 0
    assert np.all(np.diff(curve.x) >= 0)
    assert curve.bytes_read == ROWS * 8


def test_read_curve_is_read_block_by_block(scan_files, monkeypatch):
    master, _detector = scan_files
    monkeypatch.setattr(h5_reader, "SLAB_ELEMENTS", 5_000)
    fractions = []
    reference = h5_reader.read_curve(str(master), "/entry/plot/counts", max_points=1000)

    curve = h5_reader.read_curve(
        str(master), "/entry/plot/counts", max_points=1000, progress=fractions.append
    )

    assert len(fractions) > 5
    assert fractions[-1] == 1.0
    np.testing.assert_array_equal(curve.y, reference.y)


def test_read_curve_takes_the_x_values_from_another_dataset(scan_files):
    master, _detector = scan_files
    reduced = h5_reader.read_curve(
        str(master), "/entry/plot/counts", max_points=1000, x_path="/entry/plot/energy"
    )
    assert reduced.x[0] == 8000.0
    assert 8990.0 < reduced.x[-1] <= 9000.0

    exact = h5_reader.read_curve(
        str(master), "/entry/plot/counts", start=0, stop=5, x_path="/entry/plot/energy"
    )
    np.testing.assert_allclose(exact.x, np.linspace(8000.0, 9000.0, ROWS)[:5])

    with pytest.raises(H5ReadError):
        h5_reader.read_curve(str(master), "/entry/plot/counts", x_path="/entry/plot/other_length")


def test_read_curve_can_be_cancelled(scan_files, monkeypatch):
    master, _detector = scan_files
    monkeypatch.setattr(h5_reader, "SLAB_ELEMENTS", 5_000)
    with pytest.raises(H5ReadError) as error:
        h5_reader.read_curve(
            str(master), "/entry/plot/counts", max_points=1000, cancel=lambda: True
        )
    assert error.value.kind == "cancelled"
    assert open_file_count() == 0


def test_read_curve_reads_one_row_of_a_stack(scan_files):
    master, _detector = scan_files
    curve = h5_reader.read_curve(str(master), "/entry/grid", index=(2,))
    np.testing.assert_array_equal(curve.y, [8.0, 9.0, 10.0, 11.0])
    with pytest.raises(H5ReadError):
        h5_reader.read_curve(str(master), "/entry/grid", index=(3,))


def test_read_frame_reads_one_frame_and_strides_a_huge_one(scan_files):
    _master, detector = scan_files
    frame = h5_reader.read_frame(str(detector), "/entry/data/data", index=(2,))
    assert frame.stride == 1
    np.testing.assert_array_equal(frame.data, np.arange(96, 144).reshape(6, 8))
    assert frame.bytes_read == 6 * 8 * 2

    coarse = h5_reader.read_frame(str(detector), "/entry/data/data", index=(2,), max_pixels=12)
    assert coarse.stride == 2
    assert coarse.data.shape == (3, 4)


def test_read_table_reads_a_window_as_text(scan_files):
    master, _detector = scan_files
    table = h5_reader.read_table(str(master), "/entry/grid", row_start=1, row_stop=3, col_stop=2)
    assert table.cells == [["4", "5"], ["8", "9"]]
    column = h5_reader.read_table(str(master), "/entry/plot/energy", row_start=0, row_stop=2)
    assert column.cells[0] == ["8000"]
    assert len(column.cells) == 2


def test_read_value_and_find_nodes(scan_files):
    master, _detector = scan_files
    assert h5_reader.read_value(str(master), "/entry/name") == "Cu foil"
    with pytest.raises(H5ReadError):
        h5_reader.read_value(str(master), "/entry/plot/counts")

    found = h5_reader.find_nodes(str(master), "ENER")
    assert [node.path for node in found] == ["/entry/plot/energy"]
    assert h5_reader.find_nodes(str(master), "  ") == []
    assert len(h5_reader.find_nodes(str(master), "e", limit=2)) == 2


def test_errors_say_what_went_wrong(scan_files, tmp_path):
    master, _detector = scan_files
    with pytest.raises(H5ReadError) as missing_file:
        h5_reader.list_children(str(tmp_path / "nothing.h5"))
    assert missing_file.value.kind == "missing"
    assert "nothing.h5" in missing_file.value.message

    not_hdf5 = tmp_path / "text.h5"
    not_hdf5.write_text("this is not an HDF5 file")
    with pytest.raises(H5ReadError) as unreadable:
        h5_reader.list_children(str(not_hdf5))
    assert unreadable.value.kind == "unreadable"

    with pytest.raises(H5ReadError) as missing_dataset:
        h5_reader.read_curve(str(master), "/entry/nope")
    assert missing_dataset.value.kind == "missing"
    assert open_file_count() == 0


def test_no_file_stays_open_after_any_read(scan_files):
    master, detector = scan_files
    h5_reader.list_children(str(master))
    h5_reader.describe(str(master), "/entry/plot/counts")
    h5_reader.read_curve(str(master), "/entry/plot/counts", max_points=100)
    h5_reader.read_frame(str(detector), "/entry/data/data")
    h5_reader.read_table(str(master), "/entry/grid")
    h5_reader.read_value(str(master), "/entry/name")
    h5_reader.find_nodes(str(master), "counts")
    assert open_file_count() == 0


def test_a_writer_can_open_the_file_while_it_is_read(scan_files):
    """The reader takes no file lock: another program can open the file for writing."""
    master, _detector = scan_files
    writer = (
        "import h5py, sys\n"
        "with h5py.File(sys.argv[1], 'a') as handle:\n"
        "    handle.attrs['written_while_read'] = 1\n"
    )
    with h5_reader.open_readonly(str(master)) as handle:
        assert "entry" in handle
        result = subprocess.run(
            [sys.executable, "-c", writer, str(master)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    with h5py.File(master, "r") as handle:
        assert handle.attrs["written_while_read"] == 1


def test_file_summary_flags_a_file_that_just_changed(scan_files):
    master, _detector = scan_files
    changed = os.stat(master).st_mtime

    fresh = h5_reader.file_summary(str(master), now=changed + 1)
    settled = h5_reader.file_summary(str(master), now=changed + 60)

    assert fresh.recently_modified and fresh.busy
    assert not settled.recently_modified and not settled.busy
    assert settled.size_bytes == os.stat(master).st_size
    with pytest.raises(H5ReadError) as error:
        h5_reader.file_summary(str(master.parent / "nothing.h5"))
    assert error.value.kind == "missing"


def test_held_by_writer_reads_the_lock_table_without_locking(scan_files, tmp_path):
    master, _detector = scan_files
    stat = os.stat(master)
    key = f"{os.major(stat.st_dev):02x}:{os.minor(stat.st_dev):02x}:{stat.st_ino}"
    table = tmp_path / "locks"

    table.write_text(f"1: FLOCK  ADVISORY  WRITE 4242 {key} 0 EOF\n")
    assert h5_reader.held_by_writer(str(master), str(table))

    table.write_text(f"1: FLOCK  ADVISORY  READ 4242 {key} 0 EOF\n")
    assert not h5_reader.held_by_writer(str(master), str(table))

    table.write_text("1: FLOCK  ADVISORY  WRITE 4242 00:00:1 0 EOF\n")
    assert not h5_reader.held_by_writer(str(master), str(table))
    assert not h5_reader.held_by_writer(str(master), str(tmp_path / "no_table"))


def test_scan_folder_files_lists_the_files_of_the_same_scan(scan_files):
    master, detector = scan_files
    other_scan = master.parent / "S00002_master.h5"
    with h5py.File(other_scan, "w"):
        pass
    (master.parent / "S00001_notes.txt").write_text("not HDF5")

    files = h5_reader.scan_folder_files(str(master))

    assert [summary.file_path for summary in files] == [str(master), str(detector)]


def test_formatting():
    assert h5_reader.format_shape(()) == "scalar"
    assert h5_reader.format_shape((600, 1679, 1475)) == "600 × 1\u2009679 × 1\u2009475"
    assert h5_reader.format_count(1200000) == "1\u2009200\u2009000"
    assert h5_reader.format_bytes(512) == "512 bytes"
    assert h5_reader.format_bytes(5.9e9) == "5.9 GB"
