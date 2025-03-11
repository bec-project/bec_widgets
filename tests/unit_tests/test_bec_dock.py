# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.widgets.containers.dock import BECDockArea

from .client_mocks import mocked_client
from .test_bec_queue import bec_queue_msg_full


@pytest.fixture
def bec_dock_area(qtbot, mocked_client):
    widget = BECDockArea(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_bec_dock_area_init(bec_dock_area):
    assert bec_dock_area is not None
    assert bec_dock_area.client is not None
    assert isinstance(bec_dock_area, BECDockArea)
    assert bec_dock_area.config.widget_class == "BECDockArea"


def test_bec_dock_area_add_remove_dock(bec_dock_area, qtbot):
    initial_count = len(bec_dock_area.dock_area.docks)

    # Adding 3 docks
    d0 = bec_dock_area.new()
    d1 = bec_dock_area.new()
    d2 = bec_dock_area.new()

    # Check if the docks were added
    assert len(bec_dock_area.dock_area.docks) == initial_count + 3
    assert d0.name() in dict(bec_dock_area.dock_area.docks)
    assert d1.name() in dict(bec_dock_area.dock_area.docks)
    assert d2.name() in dict(bec_dock_area.dock_area.docks)
    assert bec_dock_area.dock_area.docks[d0.name()].config.widget_class == "BECDock"
    assert bec_dock_area.dock_area.docks[d1.name()].config.widget_class == "BECDock"
    assert bec_dock_area.dock_area.docks[d2.name()].config.widget_class == "BECDock"

    # Check panels API for getting docks to CLI
    assert bec_dock_area.panels == dict(bec_dock_area.dock_area.docks)

    # Remove docks
    d0_name = d0.name()
    bec_dock_area.delete(d0_name)
    qtbot.wait(200)
    d1.remove()
    qtbot.wait(200)

    assert len(bec_dock_area.dock_area.docks) == initial_count + 1
    assert d0.name() not in dict(bec_dock_area.dock_area.docks)
    assert d1.name() not in dict(bec_dock_area.dock_area.docks)
    assert d2.name() in dict(bec_dock_area.dock_area.docks)


def test_add_remove_bec_figure_to_dock(bec_dock_area):
    d0 = bec_dock_area.new()
    fig = d0.new("BECFigure")
    plt = fig.plot(x_name="samx", y_name="bpm4i")
    im = fig.image("eiger")
    mm = fig.motor_map("samx", "samy")
    mw = fig.multi_waveform("waveform1d")

    assert len(bec_dock_area.dock_area.docks) == 1
    assert len(d0.elements) == 1
    assert len(d0.element_list) == 1
    assert len(fig.widgets) == 4

    assert fig.config.widget_class == "BECFigure"
    assert plt.config.widget_class == "BECWaveform"
    assert im.config.widget_class == "BECImageShow"
    assert mm.config.widget_class == "BECMotorMap"
    assert mw.config.widget_class == "BECMultiWaveform"


def test_close_docks(bec_dock_area, qtbot):
    d0 = bec_dock_area.new(name="dock_0")
    d1 = bec_dock_area.new(name="dock_1")
    d2 = bec_dock_area.new(name="dock_2")

    bec_dock_area.delete_all()
    qtbot.wait(200)
    assert len(bec_dock_area.dock_area.docks) == 0


def test_undock_and_dock_docks(bec_dock_area, qtbot):
    d0 = bec_dock_area.new(name="dock_0")
    d1 = bec_dock_area.new(name="dock_1")
    d2 = bec_dock_area.new(name="dock_4")
    d3 = bec_dock_area.new(name="dock_3")

    d0.detach()
    bec_dock_area.detach_dock("dock_1")
    d2.detach()

    assert len(bec_dock_area.dock_area.docks) == 4
    assert len(bec_dock_area.dock_area.tempAreas) == 3

    d0.attach()
    assert len(bec_dock_area.dock_area.docks) == 4
    assert len(bec_dock_area.dock_area.tempAreas) == 2

    bec_dock_area.attach_all()
    assert len(bec_dock_area.dock_area.docks) == 4
    assert len(bec_dock_area.dock_area.tempAreas) == 0


###################################
# Toolbar Actions
###################################
def test_toolbar_add_plot_waveform(bec_dock_area):
    bec_dock_area.toolbar.widgets["menu_plots"].widgets["waveform"].trigger()
    assert "Waveform_0" in bec_dock_area.panels
    assert bec_dock_area.panels["Waveform_0"].widgets[0].config.widget_class == "Waveform"


def test_toolbar_add_plot_image(bec_dock_area):
    bec_dock_area.toolbar.widgets["menu_plots"].widgets["image"].trigger()
    assert "Image_0" in bec_dock_area.panels
    assert bec_dock_area.panels["Image_0"].widgets[0].config.widget_class == "Image"


def test_toolbar_add_plot_motor_map(bec_dock_area):
    bec_dock_area.toolbar.widgets["menu_plots"].widgets["motor_map"].trigger()
    assert "BECMotorMapWidget_0" in bec_dock_area.panels
    assert (
        bec_dock_area.panels["BECMotorMapWidget_0"].widgets[0].config.widget_class
        == "BECMotorMapWidget"
    )


def test_toolbar_add_device_positioner_box(bec_dock_area):
    bec_dock_area.toolbar.widgets["menu_devices"].widgets["positioner_box"].trigger()
    assert "PositionerBox_0" in bec_dock_area.panels
    assert bec_dock_area.panels["PositionerBox_0"].widgets[0].config.widget_class == "PositionerBox"


def test_toolbar_add_utils_queue(bec_dock_area, bec_queue_msg_full):
    bec_dock_area.client.connector.set_and_publish(
        MessageEndpoints.scan_queue_status(), bec_queue_msg_full
    )
    bec_dock_area.toolbar.widgets["menu_utils"].widgets["queue"].trigger()
    assert "BECQueue_0" in bec_dock_area.panels
    assert bec_dock_area.panels["BECQueue_0"].widgets[0].config.widget_class == "BECQueue"


def test_toolbar_add_utils_status(bec_dock_area):
    bec_dock_area.toolbar.widgets["menu_utils"].widgets["status"].trigger()
    assert "BECStatusBox_0" in bec_dock_area.panels
    assert bec_dock_area.panels["BECStatusBox_0"].widgets[0].config.widget_class == "BECStatusBox"


def test_toolbar_add_utils_progress_bar(bec_dock_area):
    bec_dock_area.toolbar.widgets["menu_utils"].widgets["progress_bar"].trigger()
    assert "RingProgressBar_0" in bec_dock_area.panels
    assert (
        bec_dock_area.panels["RingProgressBar_0"].widgets[0].config.widget_class
        == "RingProgressBar"
    )
