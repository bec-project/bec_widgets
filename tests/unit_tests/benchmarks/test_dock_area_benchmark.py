from __future__ import annotations

import pytest

from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from tests.unit_tests.client_mocks import mocked_client


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
