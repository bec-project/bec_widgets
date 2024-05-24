# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest

from bec_widgets.widgets import BECDock, BECDockArea

from .client_mocks import mocked_client


@pytest.fixture
def bec_dock_area(qtbot, mocked_client):
    widget = BECDockArea(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_bec_dock_area_init(bec_dock_area):
    assert bec_dock_area is not None
    assert bec_dock_area.client is not None
    assert isinstance(bec_dock_area, BECDockArea)
    assert bec_dock_area.config.widget_class == "BECDockArea"


def test_bec_dock_area_add_remove_dock(bec_dock_area, qtbot):
    initial_count = len(bec_dock_area.docks)

    # Adding 3 docks
    d0 = bec_dock_area.add_dock()
    d1 = bec_dock_area.add_dock()
    d2 = bec_dock_area.add_dock()

    # Check if the docks were added
    assert len(bec_dock_area.docks) == initial_count + 3
    assert d0.name() in dict(bec_dock_area.docks)
    assert d1.name() in dict(bec_dock_area.docks)
    assert d2.name() in dict(bec_dock_area.docks)
    assert bec_dock_area.docks[d0.name()].config.widget_class == "BECDock"
    assert bec_dock_area.docks[d1.name()].config.widget_class == "BECDock"
    assert bec_dock_area.docks[d2.name()].config.widget_class == "BECDock"

    # Check panels API for getting docks to CLI
    assert bec_dock_area.panels == dict(bec_dock_area.docks)

    # Remove docks
    d0_name = d0.name()
    bec_dock_area.remove_dock(d0_name)  # TODO fix this, works in jupyter console
    qtbot.wait(200)
    d1.remove()
    qtbot.wait(200)

    assert len(bec_dock_area.docks) == initial_count + 1
    assert d0.name() not in dict(bec_dock_area.docks)
    assert d1.name() not in dict(bec_dock_area.docks)
    assert d2.name() in dict(bec_dock_area.docks)


def test_add_remove_bec_figure_to_dock(bec_dock_area):
    d0 = bec_dock_area.add_dock()
    fig = d0.add_widget_bec("BECFigure")
    plt = fig.plot(x_name="samx", y_name="bpm4i")
    im = fig.image("eiger")
    mm = fig.motor_map("samx", "samy")

    assert len(bec_dock_area.docks) == 1
    assert len(d0.widgets) == 1
    assert len(d0.widget_list) == 1
    assert len(fig.widgets) == 3

    assert fig.config.widget_class == "BECFigure"
    assert plt.config.widget_class == "BECWaveform"
    assert im.config.widget_class == "BECImageShow"
    assert mm.config.widget_class == "BECMotorMap"


def test_dock_area_errors(bec_dock_area):
    d0 = bec_dock_area.add_dock(name="dock_0")

    with pytest.raises(ValueError) as excinfo:
        bec_dock_area.add_dock(name="dock_0")
        assert "Dock with name  dock_0 already exists." in str(excinfo.value)


def test_close_docks(bec_dock_area, qtbot):
    d0 = bec_dock_area.add_dock(name="dock_0")
    d1 = bec_dock_area.add_dock(name="dock_1")
    d2 = bec_dock_area.add_dock(name="dock_2")

    bec_dock_area.clear_all()
    qtbot.wait(200)
    assert len(bec_dock_area.docks) == 0


def test_undock_and_dock_docks(bec_dock_area, qtbot):
    d0 = bec_dock_area.add_dock(name="dock_0")
    d1 = bec_dock_area.add_dock(name="dock_1")
    d2 = bec_dock_area.add_dock(name="dock_4")
    d3 = bec_dock_area.add_dock(name="dock_3")

    d0.detach()
    bec_dock_area.detach_dock("dock_1")
    d2.detach()

    assert len(bec_dock_area.docks) == 4
    assert len(bec_dock_area.tempAreas) == 3

    d0.attach()
    assert len(bec_dock_area.docks) == 4
    assert len(bec_dock_area.tempAreas) == 2

    bec_dock_area.attach_all()
    assert len(bec_dock_area.docks) == 4
    assert len(bec_dock_area.tempAreas) == 0
