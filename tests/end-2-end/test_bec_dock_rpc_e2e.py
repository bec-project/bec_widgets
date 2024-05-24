import numpy as np
import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.cli.client import BECDockArea, BECFigure, BECImageShow, BECMotorMap, BECWaveform


def test_rpc_add_dock_with_figure_e2e(rpc_server_dock, qtbot):
    dock = BECDockArea(rpc_server_dock.gui_id)
    dock_server = rpc_server_dock.gui

    # BEC client shortcuts
    client = rpc_server_dock.client
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    # Create 3 docks
    d0 = dock.add_dock("dock_0")
    d1 = dock.add_dock("dock_1")
    d2 = dock.add_dock("dock_2")

    assert len(dock_server.docks) == 3

    # Add 3 figures with some widgets
    fig0 = d0.add_widget_bec("BECFigure")
    fig1 = d1.add_widget_bec("BECFigure")
    fig2 = d2.add_widget_bec("BECFigure")

    assert len(dock_server.docks) == 3
    assert len(dock_server.docks["dock_0"].widgets) == 1
    assert len(dock_server.docks["dock_1"].widgets) == 1
    assert len(dock_server.docks["dock_2"].widgets) == 1

    assert fig1.__class__.__name__ == "BECFigure"
    assert fig1.__class__ == BECFigure
    assert fig2.__class__.__name__ == "BECFigure"
    assert fig2.__class__ == BECFigure

    mm = fig0.motor_map("samx", "samy")
    plt = fig1.plot(x_name="samx", y_name="bpm4i")
    im = fig2.image("eiger")

    assert mm.__class__.__name__ == "BECMotorMap"
    assert mm.__class__ == BECMotorMap
    assert plt.__class__.__name__ == "BECWaveform"
    assert plt.__class__ == BECWaveform
    assert im.__class__.__name__ == "BECImageShow"
    assert im.__class__ == BECImageShow

    assert mm.config_dict["signals"] == {
        "source": "device_readback",
        "x": {
            "name": "samx",
            "entry": "samx",
            "unit": None,
            "modifier": None,
            "limits": [-50.0, 50.0],
        },
        "y": {
            "name": "samy",
            "entry": "samy",
            "unit": None,
            "modifier": None,
            "limits": [-50.0, 50.0],
        },
        "z": None,
    }
    assert plt.config_dict["curves"]["bpm4i-bpm4i"]["signals"] == {
        "source": "scan_segment",
        "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
        "y": {"name": "bpm4i", "entry": "bpm4i", "unit": None, "modifier": None, "limits": None},
        "z": None,
    }
    assert im.config_dict["images"]["eiger"]["monitor"] == "eiger"

    # check initial position of motor map
    initial_pos_x = dev.samx.read()["samx"]["value"]
    initial_pos_y = dev.samy.read()["samy"]["value"]

    # Try to make a scan
    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)

    # wait for scan to finish
    while not status.status == "COMPLETED":
        qtbot.wait(200)

    # plot
    plt_last_scan_data = queue.scan_storage.storage[-1].data
    plt_data = plt.get_all_data()
    assert plt_data["bpm4i-bpm4i"]["x"] == plt_last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4i-bpm4i"]["y"] == plt_last_scan_data["bpm4i"]["bpm4i"].val

    # image
    last_image_device = client.connector.get_last(MessageEndpoints.device_monitor("eiger"))[
        "data"
    ].data
    qtbot.wait(500)
    last_image_plot = im.images[0].get_data()
    np.testing.assert_equal(last_image_device, last_image_plot)

    # motor map
    final_pos_x = dev.samx.read()["samx"]["value"]
    final_pos_y = dev.samy.read()["samy"]["value"]

    # check final coordinates of motor map
    motor_map_data = mm.get_data()

    np.testing.assert_equal(
        [motor_map_data["x"][0], motor_map_data["y"][0]], [initial_pos_x, initial_pos_y]
    )
    np.testing.assert_equal(
        [motor_map_data["x"][-1], motor_map_data["y"][-1]], [final_pos_x, final_pos_y]
    )


def test_dock_manipulations_e2e(rpc_server_dock, qtbot):
    dock = BECDockArea(rpc_server_dock.gui_id)
    dock_server = rpc_server_dock.gui

    d0 = dock.add_dock("dock_0")
    d1 = dock.add_dock("dock_1")
    d2 = dock.add_dock("dock_2")
    assert len(dock_server.docks) == 3

    d0.detach()
    dock.detach_dock("dock_2")
    assert len(dock_server.docks) == 3
    assert len(dock_server.tempAreas) == 2

    d0.attach()
    assert len(dock_server.docks) == 3
    assert len(dock_server.tempAreas) == 1

    d2.remove()
    qtbot.wait(200)

    assert len(dock_server.docks) == 2
    docks_list = list(dict(dock_server.docks).keys())
    assert ["dock_0", "dock_1"] == docks_list

    dock.clear_all()

    assert len(dock_server.docks) == 0
    assert len(dock_server.tempAreas) == 0
