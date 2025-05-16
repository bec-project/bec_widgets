from __future__ import annotations

from typing import Literal

import numpy as np
import pyqtgraph as pg
import pytest
from qtpy.QtCore import QPointF

from bec_widgets.widgets.plots.image.image import Image
from bec_widgets.widgets.plots.roi.image_roi import CircularROI, RectangularROI, ROIController
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget


@pytest.fixture(params=["rect", "circle"])
def bec_image_widget_with_roi(qtbot, request, mocked_client):
    """Return (widget, roi, shape_label) for each ROI class."""

    roi_type: Literal["rect", "circle"] = request.param

    # Build an Image widget with a trivial 100×100 zeros array
    widget: Image = create_widget(qtbot, Image, client=mocked_client)
    data = np.zeros((100, 100), dtype=float)
    data[20:40, 20:40] = 5  # content assertion for roi to check
    widget.main_image.set_data(data)

    # Add a single ROI via the public API
    roi = widget.add_roi(kind=roi_type)

    yield widget, roi, roi_type


def test_default_properties(bec_image_widget_with_roi):
    """Label, width, type sanity‑check."""

    _widget, roi, roi_type = bec_image_widget_with_roi

    assert roi.label.startswith("ROI")

    assert roi.line_width == 10

    # concrete subclass type
    assert isinstance(roi, RectangularROI) if roi_type == "rect" else isinstance(roi, CircularROI)


def test_coordinate_structures(bec_image_widget_with_roi):
    """Typed vs untyped coordinate structures are consistent."""

    _widget, roi, _ = bec_image_widget_with_roi

    raw = roi.get_coordinates(typed=False)
    typed = roi.get_coordinates(typed=True)

    # untyped is always a tuple
    assert isinstance(raw, tuple)

    # typed is always a dict and has same number of scalars as raw flattens to
    assert isinstance(typed, dict)
    assert sum(isinstance(v, (tuple, list)) and len(v) or 1 for v in typed.values()) == len(
        np.ravel(raw)
    )


def test_data_extraction_matches_coordinates(bec_image_widget_with_roi):
    """Pixels reported by get_data_from_image have non‑zero size and match ROI extents."""

    widget, roi, _ = bec_image_widget_with_roi

    pixels = roi.get_data_from_image()  # auto‑detect ImageItem

    assert pixels.size > 0  # ROI covers at least one pixel

    # For rectangular ROI: pixel bounding box equals coordinate bbox
    if isinstance(roi, RectangularROI):
        (x0, y0), (_, _), (_, _), (x1, y1) = roi.get_coordinates(typed=False)
        # ensure ints inside image shape
        x0, y0, x1, y1 = map(int, (x0, y0, x1, y1))
        expected = widget.main_image.image[y0:y1, x0:x1]
        assert pixels.shape == expected.shape


@pytest.mark.parametrize("index", [0])
def test_controller_remove_by_index(bec_image_widget_with_roi, index):
    """Image.remove_roi(index) removes the graphics item and updates controller."""

    widget, roi, _ = bec_image_widget_with_roi
    controller: ROIController = widget.roi_controller

    assert controller.rois  # non‑empty before

    widget.remove_roi(index)

    # ROI list now empty and item no longer in scene
    assert not controller.rois
    assert roi not in widget.plot_item.items


def test_color_uniqueness_across_multiple_rois(qtbot, mocked_client):
    widget: Image = create_widget(qtbot, Image, client=mocked_client)

    # add two of each ROI type
    for _kind in ("rect", "circle"):
        widget.add_roi(kind=_kind)
        widget.add_roi(kind=_kind)

    colors = [r.line_color for r in widget.roi_controller.rois]
    assert len(colors) == len(set(colors)), "Colors must be unique per ROI"


def test_roi_label_and_signals(bec_image_widget_with_roi):
    widget, roi, _ = bec_image_widget_with_roi
    changed = []
    roi.nameChanged.connect(lambda name: changed.append(name))
    roi.label = "new_label"
    assert roi.label == "new_label"
    assert changed and changed[0] == "new_label"


def test_roi_line_color_and_width(bec_image_widget_with_roi):
    _widget, roi, _ = bec_image_widget_with_roi
    changed = []
    roi.penChanged.connect(lambda: changed.append(True))
    roi.line_color = "#123456"
    assert roi.line_color == "#123456"
    roi.line_width = 5
    assert roi.line_width == 5
    assert changed  # penChanged should have been emitted


def test_roi_controller_add_remove_multiple(qtbot, mocked_client):
    widget = create_widget(qtbot, Image, client=mocked_client)
    controller = widget.roi_controller
    r1 = widget.add_roi(kind="rect", name="r1")
    r2 = widget.add_roi(kind="circle", name="c1")
    assert r1 in controller.rois and r2 in controller.rois
    widget.remove_roi("r1")
    assert r1 not in controller.rois and r2 in controller.rois
    widget.remove_roi("c1")
    assert not controller.rois


def test_roi_controller_colormap_changes(qtbot, mocked_client):
    widget = create_widget(qtbot, Image, client=mocked_client)
    controller = widget.roi_controller
    widget.add_roi(kind="rect")
    widget.add_roi(kind="circle")
    old_colors = [r.line_color for r in controller.rois]
    controller.colormap = "plasma"
    new_colors = [r.line_color for r in controller.rois]
    assert old_colors != new_colors
    assert all(isinstance(c, str) for c in new_colors)


def test_roi_controller_clear(qtbot, mocked_client):
    widget = create_widget(qtbot, Image, client=mocked_client)
    widget.add_roi(kind="rect")
    widget.add_roi(kind="circle")
    controller = widget.roi_controller
    controller.clear()
    assert not controller.rois


def test_roi_get_data_from_image_no_image(qtbot, mocked_client):
    widget = create_widget(qtbot, Image, client=mocked_client)
    roi = widget.add_roi(kind="rect")
    # Remove all images from scene
    for item in list(widget.plot_item.items):
        if hasattr(item, "image"):
            widget.plot_item.removeItem(item)
    import pytest

    with pytest.raises(RuntimeError):
        roi.get_data_from_image()


def test_roi_remove_cleans_up(bec_image_widget_with_roi):
    widget, roi, _ = bec_image_widget_with_roi
    roi.remove()
    assert roi not in widget.roi_controller.rois
    assert roi not in widget.plot_item.items


def test_roi_controller_get_roi_methods(qtbot, mocked_client):
    widget = create_widget(qtbot, Image, client=mocked_client)
    r1 = widget.add_roi(kind="rect", name="findme")
    r2 = widget.add_roi(kind="circle")
    controller = widget.roi_controller
    assert controller.get_roi_by_name("findme") == r1
    assert controller.get_roi(1) == r2
    assert controller.get_roi(99) is None
    assert controller.get_roi_by_name("notfound") is None
