"""Tests for the 3D VolumePlot widget, its data model, GL helpers and the beam simulation."""

from unittest import mock

import numpy as np
import pytest
from bec_lib.data_api.models import SourceData, SubscriptionUpdate
from qtpy.QtCore import QPointF
from qtpy.QtGui import QColor, QVector4D

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.plots.volume_plot import gl_volume_view
from bec_widgets.widgets.plots.volume_plot.beam_simulation import (
    focus_positions,
    simulate_astigmatic_beam,
)
from bec_widgets.widgets.plots.volume_plot.gl_volume_view import (
    frame_points,
    opengl_status,
    plane_matrix,
    plane_rgba,
    ray_box,
    volume_rgba,
)
from bec_widgets.widgets.plots.volume_plot.volume_data import (
    VolumeData,
    VolumeMark,
    grid_from_points,
)
from bec_widgets.widgets.plots.volume_plot.volume_plot import VolumePlot


def _ramp_volume(shape=(4, 5, 6)) -> VolumeData:
    values = np.arange(np.prod(shape), dtype=float).reshape(shape)
    return VolumeData.from_array(
        values,
        x=np.linspace(0, 3, shape[0]),
        y=np.linspace(10, 14, shape[1]),
        z=np.linspace(-1, 1, shape[2]),
        labels=("samx", "samy", "samz"),
        units=("mm", "mm", "mm"),
    )


# ---------------------------------------------------------------------- data model
def test_volume_data_rejects_wrong_shapes():
    with pytest.raises(ValueError):
        VolumeData.from_array(np.zeros((3, 3)))
    with pytest.raises(ValueError):
        VolumeData.from_array(np.zeros((3, 3, 3)), x=np.arange(4))


def test_volume_data_defaults_to_index_coordinates():
    volume = VolumeData.from_array(np.zeros((2, 3, 4)))
    assert volume.shape == (2, 3, 4)
    np.testing.assert_array_equal(volume.axes[2], [0, 1, 2, 3])
    assert volume.extent(2) == (-0.5, 3.5)


def test_volume_data_slices_keep_data_order():
    volume = _ramp_volume()
    np.testing.assert_array_equal(volume.slice(2, 3), volume.values[:, :, 3])
    np.testing.assert_array_equal(volume.slice(0, 1), volume.values[1])
    np.testing.assert_array_equal(volume.slice(1, 99), volume.values[:, -1, :])  # clamped
    assert VolumeData.plane_axes(1) == (0, 2)


def test_volume_data_coordinates_and_index_lookup():
    volume = _ramp_volume()
    assert volume.coordinate(2, 0) == pytest.approx(-1)
    assert volume.index_of(2, 0.05) == 3
    assert volume.index_of(0, 100) == 3
    assert volume.spacing(1) == pytest.approx(1.0)


def test_volume_data_projection_ignores_missing_voxels():
    values = np.ones((2, 2, 3))
    values[0, 0, :] = np.nan
    volume = VolumeData.from_array(values)
    np.testing.assert_array_equal(volume.projection(2, "sum"), [[0, 3], [3, 3]])
    assert volume.projection(0, "max").shape == (2, 3)


def test_volume_data_normalized_maps_nan_to_zero():
    values = np.array([[[1.0, 3.0], [np.nan, 2.0]]])
    normalized = VolumeData.from_array(values).normalized()
    np.testing.assert_allclose(normalized, [[[0.0, 1.0], [0.0, 0.5]]])
    assert VolumeData.from_array(np.full((1, 1, 2), np.nan)).value_range() == (0.0, 1.0)


def test_display_box_rules():
    volume = _ramp_volume()
    # same unit and ratios within 10x: physical lengths
    lengths = np.array([volume.extent(a)[1] - volume.extent(a)[0] for a in range(3)])
    np.testing.assert_allclose(volume.display_box(), lengths / lengths.max())
    volume.units = ("mm", "mm", "deg")
    assert volume.display_box() == (1.0, 1.0, 1.0)
    volume.box_aspect = (1, 1, 4)
    assert volume.display_box() == (0.25, 0.25, 1.0)


def test_brightest_along_picks_the_bright_voxel():
    values = np.zeros((5, 5, 5))
    values[2, 2, 4] = 10
    volume = VolumeData.from_array(values)
    samples = np.array([[2.5, 2.5, z + 0.5] for z in range(5)])
    assert volume.brightest_along(samples) == 4
    empty = VolumeData.from_array(np.full((2, 2, 2), np.nan))
    assert empty.brightest_along(np.array([[0.5, 0.5, 0.5]])) is None


# ---------------------------------------------------------------------- gridding
def test_grid_from_points_regular_grid():
    xs, ys, zs = np.meshgrid([0, 1], [0, 1, 2], [5, 6], indexing="ij")
    values = np.arange(xs.size, dtype=float)
    grid, axes = grid_from_points(xs.ravel(), ys.ravel(), zs.ravel(), values)
    assert grid.shape == (2, 3, 2)
    np.testing.assert_array_equal(axes[1], [0, 1, 2])
    np.testing.assert_array_equal(grid.ravel(), values)


def test_grid_from_points_uses_the_planned_grid_for_a_running_scan():
    planned = np.array(np.meshgrid([0, 1], [0, 1], [0, 1, 2], indexing="ij")).reshape(3, -1).T
    measured = planned[:5] + 1e-4  # readback jitter
    grid, axes = grid_from_points(*measured.T, np.ones(5), planned=planned)
    assert grid.shape == (2, 2, 3)
    assert np.count_nonzero(np.isfinite(grid)) == 5
    np.testing.assert_array_equal(axes[2], [0, 1, 2])


def test_grid_from_points_merges_readback_jitter():
    rng = np.random.default_rng(3)
    xs, ys, zs = np.meshgrid([0, 1, 2, 3], [0, 1, 2], [0, 0.5], indexing="ij")
    points = np.column_stack([xs.ravel(), ys.ravel(), zs.ravel()])
    measured = points + rng.uniform(-2e-3, 2e-3, size=points.shape)
    grid, axes = grid_from_points(*measured.T, np.arange(len(points), dtype=float))
    assert grid.shape == (4, 3, 2)
    np.testing.assert_allclose(axes[0], [0, 1, 2, 3], atol=2e-3)
    assert np.isfinite(grid).all()


def test_grid_from_points_keeps_distinct_single_positions():
    # a line of positions, each visited once, is not mistaken for jitter
    x = np.linspace(0, 1, 11)
    grid, axes = grid_from_points(x, np.zeros(11), np.zeros(11), np.ones(11))
    assert grid.shape == (11, 1, 1)
    np.testing.assert_allclose(axes[0], x)


def test_grid_from_points_bins_scattered_points():
    rng = np.random.default_rng(1)
    points = rng.uniform(0, 1, size=(2000, 3))
    grid, axes = grid_from_points(*points.T, np.ones(2000), max_bins=8)
    assert grid.shape == (8, 8, 8)
    assert np.nanmax(grid) == pytest.approx(1.0)
    assert axes[0][0] > 0 and axes[0][-1] < 1


def test_grid_from_points_without_points():
    grid, _axes = grid_from_points([], [], [], [])
    assert grid.shape == (1, 1, 1)
    assert np.isnan(grid).all()


# ---------------------------------------------------------------------- beam simulation
def test_astigmatic_beam_focuses_where_the_marks_say():
    volume = simulate_astigmatic_beam(n_z=41, n_xy=64, pupil_samples=128, pupil_radius=24)
    intensity, x, z = volume.values, volume.axes[0], volume.axes[2]

    def rms_width(axis):
        profile = intensity.sum(axis=1 - axis)  # (n, nz) profile along x or y
        mean = (profile * x[:, None]).sum(0) / profile.sum(0)
        return np.sqrt((profile * (x[:, None] - mean) ** 2).sum(0) / profile.sum(0))

    width_x, width_y = rms_width(0), rms_width(1)
    marks = {m.label: m.coordinate for m in volume.marks}
    sagittal, least, tangential = (c * 1e3 for c in focus_positions(1e-9, 2.5e-3, 1.0))
    assert marks["Sagittal focus"] == pytest.approx(sagittal)
    step = z[1] - z[0]
    assert z[np.argmin(width_y)] == pytest.approx(sagittal, abs=step)  # horizontal line
    assert z[np.argmin(width_x)] == pytest.approx(tangential, abs=step)  # vertical line
    round_at = z[np.argmin(np.abs(width_x - width_y))]
    assert round_at == pytest.approx(least, abs=step)
    assert volume.up_axis == 1 and volume.units == ("µm", "µm", "mm")


# ---------------------------------------------------------------------- GL helpers
def test_ray_box_hit_and_miss():
    size = np.array([2.0, 2.0, 2.0])
    hit = ray_box(np.array([1.0, 1.0, -5.0]), np.array([0.0, 0.0, 1.0]), size)
    assert hit == pytest.approx((5.0, 7.0))
    assert ray_box(np.array([5.0, 5.0, -5.0]), np.array([0.0, 0.0, 1.0]), size) is None
    # starting inside the box enters at t = 0
    assert ray_box(np.array([1.0, 1.0, 1.0]), np.array([1.0, 0.0, 0.0]), size)[0] == 0.0


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_plane_matrix_puts_the_image_on_the_cut(axis):
    matrix = plane_matrix(axis, 3.5)
    p, q = VolumeData.plane_axes(axis)
    mapped = matrix.map(QVector4D(2.0, 5.0, 0.0, 1.0))
    point = np.array([mapped.x(), mapped.y(), mapped.z()])
    assert point[axis] == pytest.approx(3.5)
    assert point[p] == pytest.approx(2.0)
    assert point[q] == pytest.approx(5.0)
    corners = frame_points((4, 5, 6), axis, 3.5)
    assert corners.shape == (5, 3) and np.all(corners[:, axis] == 3.5)


def test_volume_and_plane_colouring():
    lut = np.stack([np.arange(256)] * 3, axis=1).astype(np.ubyte)
    rgba = volume_rgba(np.array([[[0.0, 0.04, 1.0]]]), lut, opacity=1.0, threshold=0.05)
    assert rgba.shape == (1, 1, 3, 4)
    assert rgba[0, 0, 0, 3] == 0 and rgba[0, 0, 1, 3] == 0  # below the threshold
    assert rgba[0, 0, 2, 3] == 255
    plane = plane_rgba(np.array([[np.nan, 0.0, 1.0]]), lut)
    assert plane[0, 0, 3] == 0  # no data: transparent
    assert 0 < plane[0, 1, 3] < plane[0, 2, 3] == 255


def test_opengl_status_can_be_turned_off(monkeypatch):
    monkeypatch.setenv(gl_volume_view.DISABLE_ENV, "1")
    info = opengl_status()
    assert not info.available
    assert gl_volume_view.DISABLE_ENV in info.message


def test_opengl_status_refuses_indirect_glx(monkeypatch):
    monkeypatch.delenv(gl_volume_view.DISABLE_ENV, raising=False)
    monkeypatch.setenv("LIBGL_ALWAYS_INDIRECT", "1")
    info = opengl_status(refresh=True)
    assert not info.available and "LIBGL_ALWAYS_INDIRECT" in info.message


@pytest.mark.parametrize(
    "ssh, display, remote",
    [
        ("1.2.3.4 5 6.7.8.9 22", "localhost:10.0", True),
        ("", "localhost:10.0", False),
        ("1.2.3.4 5 6.7.8.9 22", ":0", False),
    ],
)
def test_remote_x11_display(monkeypatch, ssh, display, remote):
    monkeypatch.setenv("SSH_CONNECTION", ssh)
    monkeypatch.setenv("DISPLAY", display)
    assert gl_volume_view.remote_x11_display() is remote


def test_opengl_status_reports_the_offscreen_platform(monkeypatch):
    monkeypatch.delenv(gl_volume_view.DISABLE_ENV, raising=False)
    info = opengl_status(refresh=True)
    if not info.available:
        assert "OpenGL" in info.message


# ---------------------------------------------------------------------- widget
@pytest.fixture
def volume_plot(qtbot, mocked_client, monkeypatch):
    monkeypatch.setenv(gl_volume_view.DISABLE_ENV, "1")
    widget = create_widget(qtbot, VolumePlot, client=mocked_client)
    yield widget


def test_volume_plot_without_opengl_keeps_the_2d_cut(volume_plot):
    assert not volume_plot.gl_view.available
    assert "turned off" in volume_plot.gl_view.note.text()
    volume_plot.load_demo()
    assert volume_plot.main_image.raw_data is not None
    assert volume_plot.gl_view.pick(QPointF(10, 10), volume_plot.volume, 2) is None


def test_load_demo_pins_the_three_foci(volume_plot):
    volume_plot.load_demo()
    labels = [cut["label"] for cut in volume_plot.pinned_cuts()]
    assert labels == ["Sagittal focus", "Disk of least confusion", "Tangential focus"]
    assert len(volume_plot._thumbs) == 3
    assert volume_plot.pins_scroll.isVisibleTo(volume_plot)
    assert not volume_plot.pins_hint.isVisibleTo(volume_plot)
    assert volume_plot.cut_axis == "z"
    assert volume_plot.x_label == "x" and volume_plot.x_label_units == "µm"


def test_set_volume_and_cut_controls(volume_plot):
    volume = _ramp_volume()
    volume_plot.set_volume(
        volume.values, *volume.axes, labels=volume.labels, units=volume.units, value_label="I"
    )
    assert volume_plot.cut_index == 3  # middle of six
    assert volume_plot.cut_slider.maximum() == 5
    volume_plot.cut_index = 99
    assert volume_plot.cut_index == 5
    assert volume_plot.cut_coordinate() == pytest.approx(1.0)
    np.testing.assert_array_equal(volume_plot.main_image.raw_data, volume.values[:, :, 5])
    assert volume_plot.cut_label.text() == "samz = 1 mm"

    volume_plot.cut_axis = "x"
    assert volume_plot.cut_index == 2 and volume_plot.cut_slider.maximum() == 3
    assert volume_plot.axis_buttons.checkedId() == 0
    # cut through x shows (samy, samz); samy is the longer box side and lies horizontal
    np.testing.assert_array_equal(volume_plot.main_image.raw_data, volume.values[2])
    assert volume_plot.x_label == "samy"

    volume_plot.cut_axis = "w"  # refused (SafeProperty logs it), the axis stays
    assert volume_plot.cut_axis == "x"


def test_slider_moves_the_cut(volume_plot, qtbot):
    volume = _ramp_volume()
    volume_plot.set_volume(volume.values)
    volume_plot.cut_slider.setValue(1)
    qtbot.waitUntil(lambda: volume_plot.cut_index_label.text() == "2 / 6")
    np.testing.assert_array_equal(volume_plot.main_image.raw_data, volume.values[:, :, 1])


def test_pin_go_and_remove(volume_plot):
    volume_plot.set_volume(_ramp_volume().values)
    volume_plot.pin_cut()
    volume_plot.pin_cut()  # the same cut twice is pinned once
    assert len(volume_plot.pinned_cuts()) == 1
    volume_plot.cut_axis = "y"
    volume_plot.pin_cut(label="mine")
    assert [c["axis"] for c in volume_plot.pinned_cuts()] == ["y", "z"]
    volume_plot._go_to_pin((2, 3))
    assert volume_plot.cut_axis == "z" and volume_plot.cut_index == 3
    assert [t.isChecked() for t in volume_plot._thumbs] == [False, True]
    volume_plot._thumbs[0].remove_requested.emit((1, 2, "mine"))
    assert len(volume_plot.pinned_cuts()) == 1
    volume_plot.clear_pinned_cuts()
    assert volume_plot.pinned_cuts() == [] and volume_plot._thumbs == []
    assert volume_plot.pins_hint.isVisibleTo(volume_plot)


def test_display_properties(volume_plot):
    volume_plot.set_volume(_ramp_volume().values)
    volume_plot.mouse_mode = "follow"
    assert volume_plot.toolbar.components.get_action("volume_mode_follow").action.isChecked()
    assert not volume_plot.toolbar.components.get_action("volume_mode_click").action.isChecked()
    volume_plot.mouse_mode = "drag"  # refused, the mode stays
    assert volume_plot.mouse_mode == "follow"
    volume_plot.clip_volume = True
    assert volume_plot.toolbar.components.get_action("volume_clip").action.isChecked()
    volume_plot.show_projections = False
    assert not volume_plot.config.show_projections
    volume_plot.opacity = 3
    assert volume_plot.opacity == 1.0
    lut_before = volume_plot._lut.copy()
    volume_plot.color_map = "viridis"
    assert volume_plot.color_map == "viridis"
    assert not np.array_equal(lut_before, volume_plot._lut)


def test_empty_cut_shows_a_hint(volume_plot):
    values = np.full((3, 3, 3), np.nan)
    values[:, :, 0] = 1.0
    volume_plot.set_volume(values)
    volume_plot.cut_index = 2
    assert volume_plot._empty_hint.isVisible()
    volume_plot.cut_index = 0
    assert not volume_plot._empty_hint.isVisible()


def test_click_and_follow_modes_use_the_pick(volume_plot):
    volume_plot.set_volume(_ramp_volume().values)
    with mock.patch.object(volume_plot.gl_view, "pick", return_value=1):
        volume_plot._on_gl_click(QPointF(5, 5), 0)
        assert volume_plot.cut_index == 1 and volume_plot.pinned_cuts() == []
        volume_plot._on_gl_click(QPointF(5, 5), 0x02000000)  # Shift
        assert len(volume_plot.pinned_cuts()) == 1
    volume_plot.mouse_mode = "follow"
    with mock.patch.object(volume_plot.gl_view, "pick", return_value=4):
        volume_plot._on_gl_hover(QPointF(5, 5))
        volume_plot._apply_cut()
        assert volume_plot.cut_index == 4
        volume_plot._on_gl_click(QPointF(5, 5), 0)  # click pins in follow mode
    assert len(volume_plot.pinned_cuts()) == 2


class _FakeBridge:
    """Stand-in for QtDataSubscription, as in the heatmap tests."""

    def __init__(self, client, sources, scan="live", parent=None, min_emit_interval=0.1):
        self.client = client
        self.sources = list(sources)
        self.scan = scan
        self.groups = {}
        self.routes = {}
        self.unbound_sources = []
        self.updated = mock.MagicMock()

    def close(self):
        pass


def _update(scan_id, points, values):
    n = len(values)

    def source(dev, column):
        return SourceData(
            device=dev,
            entry=dev,
            kind="monitored",
            ordinals=tuple(range(n)),
            values=tuple(float(v) for v in column),
            timestamps=tuple(float(i) for i in range(n)),
            complete=True,
        )

    return SubscriptionUpdate(
        scan_id=scan_id,
        reason="live",
        sources={
            ("samx", "samx"): source("samx", points[:, 0]),
            ("samy", "samy"): source("samy", points[:, 1]),
            ("samz", "samz"): source("samz", points[:, 2]),
            ("bpm4i", "bpm4i"): source("bpm4i", values),
        },
        aligned_ordinals=tuple(range(n)),
        complete=True,
    )


def test_live_grid_scan_fills_the_planned_grid(volume_plot):
    with mock.patch(
        "bec_widgets.widgets.plots.volume_plot.volume_plot.QtDataSubscription", _FakeBridge
    ):
        volume_plot.plot("samx", "samy", "samz", "bpm4i")
    assert volume_plot._config_sources() == [
        ("samx", "samx"),
        ("samy", "samy"),
        ("samz", "samz"),
        ("bpm4i", "bpm4i"),
    ]
    # grid_scan(samz, 3 pts, samx, 2 pts, samy, 2 pts): samz is the slow axis
    slow, mid, fast = np.meshgrid([0, 1, 2], [0, 1], [0, 1], indexing="ij")
    planned_zxy = np.column_stack([slow.ravel(), mid.ravel(), fast.ravel()]).astype(float)
    status = {
        "scan_id": "s1",
        "scan_name": "grid_scan",
        "request_inputs": {"arg_bundle": ["samz", 0, 2, 3, "samx", 0, 1, 2, "samy", 0, 1, 2]},
        "info": {"positions": planned_zxy.tolist()},
    }
    volume_plot.on_scan_status(status, {})
    planned_xyz = planned_zxy[:, [1, 2, 0]]
    np.testing.assert_array_equal(volume_plot._planned_positions, planned_xyz)

    volume_plot._on_data_update(_update("s1", planned_xyz[:6], np.arange(6.0)))
    assert volume_plot.volume.shape == (2, 2, 3)
    assert np.count_nonzero(np.isfinite(volume_plot.volume.values)) == 6
    # the cut follows the layer that receives data, on the slow axis
    assert volume_plot.cut_axis == "z" and volume_plot.cut_index == 1
    volume_plot._on_data_update(_update("s1", planned_xyz[:10], np.arange(10.0)))
    assert volume_plot.cut_index == 2
    # once the user moves the cut it stays put
    volume_plot.cut_slider.setValue(0)
    volume_plot._on_data_update(_update("s1", planned_xyz, np.arange(12.0)))
    assert volume_plot.cut_index == 0
    assert np.isfinite(volume_plot.volume.values).all()


def _grid_status(scan_id):
    slow, mid, fast = np.meshgrid([0, 1, 2], [0, 1], [0, 1], indexing="ij")
    planned_zxy = np.column_stack([slow.ravel(), mid.ravel(), fast.ravel()]).astype(float)
    status = {
        "scan_id": scan_id,
        "scan_name": "grid_scan",
        "request_inputs": {"arg_bundle": ["samz", 0, 2, 3, "samx", 0, 1, 2, "samy", 0, 1, 2]},
        "info": {"positions": planned_zxy.tolist()},
    }
    return status, planned_zxy[:, [1, 2, 0]]


def test_scan_status_after_the_first_data_still_gives_the_full_grid(volume_plot):
    with mock.patch(
        "bec_widgets.widgets.plots.volume_plot.volume_plot.QtDataSubscription", _FakeBridge
    ):
        volume_plot.plot("samx", "samy", "samz", "bpm4i")
    status, planned_xyz = _grid_status("s2")
    volume_plot._on_data_update(_update("s2", planned_xyz[:5], np.arange(5.0)))
    assert volume_plot.volume.shape != (2, 2, 3)
    volume_plot.on_scan_status(status, {})
    assert volume_plot.volume.shape == (2, 2, 3)
    assert np.count_nonzero(np.isfinite(volume_plot.volume.values)) == 5
    # later updates of the same scan keep the plan; repeated status messages change nothing
    volume_plot.on_scan_status(status, {})
    volume_plot._on_data_update(_update("s2", planned_xyz[:7], np.arange(7.0)))
    assert volume_plot.volume.shape == (2, 2, 3)
    assert np.count_nonzero(np.isfinite(volume_plot.volume.values)) == 7


def test_scan_status_is_ignored_while_a_static_volume_is_shown(volume_plot):
    with mock.patch(
        "bec_widgets.widgets.plots.volume_plot.volume_plot.QtDataSubscription", _FakeBridge
    ):
        volume_plot.plot("samx", "samy", "samz", "bpm4i")
    volume_plot.set_volume(_ramp_volume().values)
    volume_plot.on_scan_status(_grid_status("s3")[0], {})
    assert volume_plot.volume is not None
    assert volume_plot.scan_id != "s3"


def test_planned_positions_only_for_grid_scans_over_our_devices(volume_plot):
    volume_plot.config.device_x = None
    assert volume_plot._config_sources() is None
    volume_plot.on_scan_status({"scan_id": "x"}, {})  # nothing plotted: ignored
    assert volume_plot.scan_id is None
    with mock.patch(
        "bec_widgets.widgets.plots.volume_plot.volume_plot.QtDataSubscription", _FakeBridge
    ):
        volume_plot.plot("samx", "samy", "samz", "bpm4i")
    assert volume_plot._planned_from_status({"scan_name": "line_scan"}) is None
    other = {
        "scan_name": "grid_scan",
        "request_inputs": {"arg_bundle": ["samx", 0, 1, 2, "samy", 0, 1, 2]},
        "info": {"positions": [[0, 0], [0, 1]]},
    }
    assert volume_plot._planned_from_status(other) is None


def test_volume_marks_survive_as_named_pins(volume_plot):
    volume = _ramp_volume()
    volume.marks = [VolumeMark(axis=0, coordinate=2.0, label="edge")]
    volume_plot.show_volume(volume)
    assert volume_plot.pinned_cuts() == [
        {"axis": "x", "index": 2, "coordinate": 2.0, "label": "edge"}
    ]
    assert volume_plot.cut_axis == "x"


def test_cleanup_stops_the_feed(volume_plot):
    bridge = mock.MagicMock()
    volume_plot._data_bridge = bridge
    volume_plot.cleanup()
    bridge.close.assert_called_once()
    assert volume_plot._data_bridge is None
