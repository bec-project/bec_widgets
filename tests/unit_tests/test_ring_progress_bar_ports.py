"""Tests for the QML and QWidget ports of the ring progress bar."""

# pylint: disable=redefined-outer-name, protected-access, missing-function-docstring
import json

import pytest
from qtpy.QtCore import QPointF
from qtpy.QtQuickWidgets import QQuickWidget

from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar_qml import RingProgressBarQML
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar_qwidget import (
    RingProgressBarQWidget,
)

from .conftest import create_widget


@pytest.fixture(params=[RingProgressBarQML, RingProgressBarQWidget])
def ring_bar(request, qtbot, mocked_client):
    widget = create_widget(qtbot, request.param, client=mocked_client)
    widget.resize(420, 300)
    yield widget


def test_qml_view_loads(qtbot, mocked_client):
    widget = create_widget(qtbot, RingProgressBarQML, client=mocked_client)
    view = widget.ring_progress_bar.view
    assert view.status() == QQuickWidget.Status.Ready
    assert view.errors() == []


def test_add_ring_and_value_snapshot(ring_bar):
    ring = ring_bar.add_ring()
    ring.set_value(25)
    snapshots = ring_bar.ring_progress_bar.snapshots()
    assert len(snapshots) == 1
    assert snapshots[0]["fraction"] == pytest.approx(0.25)
    assert snapshots[0]["percentText"] == "25%"
    assert snapshots[0]["valueText"] == "25 / 100"
    assert snapshots[0]["label"] == "Ring 1"


def test_center_text_defaults_to_first_ring_percentage(ring_bar):
    container = ring_bar.ring_progress_bar
    assert container.center_texts() == ("", "")
    ring_bar.add_ring().set_value(40)
    assert container.center_texts() == ("40%", "Ring 1")
    ring_bar.set_center_label("Scan 12")
    assert ring_bar.center_label == "Scan 12"
    assert container.center_texts() == ("Scan 12", "")


def test_set_progress_state_updates_rings_and_label(ring_bar):
    for _ in range(3):
        ring_bar.add_ring()
    ring_bar.set_progress_state(values=[10, None, 80], center_label="busy")
    assert [ring.config.value for ring in ring_bar.rings] == [10, 0, 80]
    ring_bar.set_progress_state(values={1: 55})
    assert ring_bar.rings[1].config.value == 55
    assert ring_bar.center_label == "busy"


def test_remove_ring_and_highlight(ring_bar):
    for _ in range(3):
        ring_bar.add_ring()
    container = ring_bar.ring_progress_bar
    container.set_highlighted(2)
    assert container.snapshots()[2]["highlighted"]
    assert container.is_ring_hovered(ring_bar.rings[2])
    ring_bar.remove_ring(2)
    assert len(container.snapshots()) == 2
    assert container.highlighted == -1
    container.set_highlighted(7)
    assert container.highlighted == -1


def test_gap_is_applied_live(ring_bar):
    ring_bar.add_ring()
    ring_bar.add_ring()
    ring_bar.set_gap(30)
    assert [snapshot["gap"] for snapshot in ring_bar.ring_progress_bar.snapshots()] == [0, 30]


def test_ring_json_roundtrip(ring_bar):
    ring_bar.add_ring().set_value(12)
    ring_bar.add_ring().set_value(34)
    data = ring_bar.ring_json
    ring_bar.ring_json = json.dumps([])
    assert ring_bar.rings == []
    ring_bar.ring_json = data
    assert [ring.config.value for ring in ring_bar.rings] == [12, 34]


def test_done_ring_and_scan_label(ring_bar):
    ring = ring_bar.add_ring()
    ring.set_update("scan")
    ring.set_value(100)
    snapshot = ring_bar.ring_progress_bar.snapshots()[0]
    assert snapshot["done"]
    assert snapshot["label"] == "Scan progress"


def test_device_label(ring_bar):
    ring = ring_bar.add_ring()
    ring.config.mode = "device"
    ring.config.device = "samx"
    ring.config.signal = "samx_readback"
    ring.set_value(1)
    assert ring_bar.ring_progress_bar.snapshots()[0]["label"] == "samx:samx_readback"


def test_show_legend_toggle(ring_bar):
    ring_bar.add_ring()
    assert ring_bar.show_legend
    ring_bar.show_legend = False
    assert not ring_bar.show_legend


def test_qml_backend_model_follows_rings(qtbot, mocked_client):
    widget = create_widget(qtbot, RingProgressBarQML, client=mocked_client)
    backend = widget.ring_progress_bar.backend
    widget.add_ring().set_value(50)
    widget.add_ring()
    assert backend.rings.count == 2
    assert backend.rings.items[0]["fraction"] == pytest.approx(0.5)
    assert backend.centerText == "50%"
    backend.setHighlighted(1)
    assert backend.highlighted == 1


def test_qwidget_legend_and_hover_picking(qtbot, mocked_client):
    widget = create_widget(qtbot, RingProgressBarQWidget, client=mocked_client)
    widget.resize(420, 300)
    widget.show()
    qtbot.waitExposed(widget)
    widget.add_ring().set_value(50)
    widget.add_ring()
    container = widget.ring_progress_bar
    assert len(container.legend.rows) == 2
    canvas = container.canvas
    snapshot = container.snapshots()[0]
    radius = canvas._base_radius() - snapshot["gap"]
    pos = QPointF(canvas.width() / 2 + radius, canvas.height() / 2)
    assert canvas.ring_at(pos) == 0
    assert canvas.ring_at(QPointF(canvas.width() / 2, canvas.height() / 2)) == -1
    widget.remove_ring()
    assert len(container.legend.rows) == 1


def test_ports_export_inherited_properties(ring_bar):
    names = set(ring_bar._get_bec_meta_objects())
    assert {"gap", "color_map", "center_label", "ring_json"} <= names
    ring = ring_bar.add_ring()
    assert {"value", "line_width", "link_colors"} <= set(ring._get_bec_meta_objects())
