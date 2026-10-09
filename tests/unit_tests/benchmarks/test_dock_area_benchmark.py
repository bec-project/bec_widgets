from __future__ import annotations

import pytest

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea
from bec_widgets.widgets.plots.waveform.waveform import Waveform


@pytest.fixture
def dock_area(qtbot, mocked_client):
    widget = BECDockArea(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_add_waveform_to_dock_area(benchmark, dock_area, qtbot, mocked_client):
    """Benchmark adding a Waveform widget to an existing dock area."""

    def add_waveform():
        dock_area.new("Waveform")
        return dock_area

    dock = benchmark(add_waveform)

    assert dock is not None


def test_switch_to_profile(benchmark, dock_area, qtbot):
    """Benchmark switching to a saved profile with several plots (blocking load_profile)."""
    for where in ("left", "right", "bottom"):
        dock_area.new("Waveform", where=where)
    dock_area.new("BECQueue", where="bottom")
    dock_area.save_profile("bench_profile", show_dialog=False)
    dock_area.delete_all()
    dock_area.new("BECQueue")
    dock_area.save_profile("bench_other", show_dialog=False)

    def switch():
        dock_area.load_profile("bench_other")
        dock_area.load_profile("bench_profile")

    benchmark(switch)

    assert len(dock_area.widget_list()) == 4
