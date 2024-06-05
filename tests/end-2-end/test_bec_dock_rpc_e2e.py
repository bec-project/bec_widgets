import time

import numpy as np
import pytest
from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.cli.auto_updates import AutoUpdates
from bec_widgets.cli.client import BECDockArea, BECFigure, BECImageShow, BECMotorMap, BECWaveform
from bec_widgets.utils import Colors


def test_rpc_add_dock_with_figure_e2e(bec_client_lib, rpc_server_dock):
    # BEC client shortcuts
    dock = BECDockArea(rpc_server_dock)
    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    # Create 3 docks
    d0 = dock.add_dock("dock_0")
    d1 = dock.add_dock("dock_1")
    d2 = dock.add_dock("dock_2")

    dock_config = dock.config_dict
    assert len(dock_config["docks"]) == 3
    # Add 3 figures with some widgets
    fig0 = d0.add_widget("BECFigure")
    fig1 = d1.add_widget("BECFigure")
    fig2 = d2.add_widget("BECFigure")

    dock_config = dock.config_dict
    assert len(dock_config["docks"]) == 3
    assert len(dock_config["docks"]["dock_0"]["widgets"]) == 1
    assert len(dock_config["docks"]["dock_1"]["widgets"]) == 1
    assert len(dock_config["docks"]["dock_2"]["widgets"]) == 1

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
        time.sleep(0.2)

    # plot
    plt_last_scan_data = queue.scan_storage.storage[-1].data
    plt_data = plt.get_all_data()
    assert plt_data["bpm4i-bpm4i"]["x"] == plt_last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4i-bpm4i"]["y"] == plt_last_scan_data["bpm4i"]["bpm4i"].val

    # image
    last_image_device = client.connector.get_last(MessageEndpoints.device_monitor("eiger"))[
        "data"
    ].data
    time.sleep(0.5)
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


def test_dock_manipulations_e2e(rpc_server_dock):
    dock = BECDockArea(rpc_server_dock)

    d0 = dock.add_dock("dock_0")
    d1 = dock.add_dock("dock_1")
    d2 = dock.add_dock("dock_2")
    dock_config = dock.config_dict
    assert len(dock_config["docks"]) == 3

    d0.detach()
    dock.detach_dock("dock_2")
    dock_config = dock.config_dict
    assert len(dock_config["docks"]) == 3
    assert len(dock.temp_areas) == 2

    d0.attach()
    dock_config = dock.config_dict
    assert len(dock_config["docks"]) == 3
    assert len(dock.temp_areas) == 1

    d2.remove()
    dock_config = dock.config_dict
    assert len(dock_config["docks"]) == 2

    assert ["dock_0", "dock_1"] == list(dock_config["docks"])

    dock.clear_all()

    dock_config = dock.config_dict
    assert len(dock_config["docks"]) == 0
    assert len(dock.temp_areas) == 0


def test_spiral_bar(rpc_server_dock):
    dock = BECDockArea(rpc_server_dock)

    d0 = dock.add_dock(name="dock_0")

    bar = d0.add_widget("SpiralProgressBar")
    assert bar.__class__.__name__ == "SpiralProgressBar"

    bar.set_number_of_bars(5)
    bar.set_colors_from_map("viridis")
    bar.set_value([10, 20, 30, 40, 50])

    docks_repr = dock.get_docks_repr()
    bar_repr = docks_repr["docks"]["dock_0"]["widgets"][0]

    expected_colors = Colors.golden_angle_color("viridis", 5, "RGB")
    assert f"Bar colors: {expected_colors}" in bar_repr
    assert f"Bar values: [10.000, 20.000, 30.000, 40.000, 50.000]" in bar_repr


def test_spiral_bar_scan_update(bec_client_lib, rpc_server_dock):
    dock = BECDockArea(rpc_server_dock)

    d0 = dock.add_dock("dock_0")

    d0.add_widget("SpiralProgressBar")

    client = bec_client_lib
    dev = client.device_manager.devices
    dev.samx.tolerance.set(0)
    dev.samy.tolerance.set(0)
    scans = client.scans

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    bar_repr = dock.get_docks_repr()["docks"]["dock_0"]["widgets"][0]
    assert "Num bars: 1" in bar_repr
    assert "Bar values: [10.000]" in bar_repr
    assert "0: config min=0.000, max=10.000" in bar_repr

    status = scans.grid_scan(dev.samx, -5, 5, 4, dev.samy, -10, 10, 4, relative=True, exp_time=0.1)
    status.wait()

    bar_repr = dock.get_docks_repr()["docks"]["dock_0"]["widgets"][0]
    assert "Num bars: 1" in bar_repr
    assert "Bar values: [16.000]" in bar_repr
    assert "0: config min=0.000, max=16.000" in bar_repr

    init_samx = dev.samx.read()["samx"]["value"]
    init_samy = dev.samy.read()["samy"]["value"]
    final_samx = init_samx + 5
    final_samy = init_samy + 10

    dev.samx.velocity.put(5)
    dev.samy.velocity.put(5)

    status = scans.umv(dev.samx, 5, dev.samy, 10, relative=True)
    status.wait()

    bar_repr = dock.get_docks_repr()["docks"]["dock_0"]["widgets"][0]
    assert "Num bars: 2" in bar_repr
    assert f"Bar values: [{'%.3f' % final_samx}, {'%.3f' % final_samy}]" in bar_repr
    assert (
        f"0: config min={'%.3f' % init_samx}, max={'%.3f' % final_samx} | 1: config min={'%.3f' % init_samy}, max={'%.3f' % final_samy}"
        in bar_repr
    )


def test_auto_update(rpc_server_dock, bec_client, qtbot):
    dock = BECDockArea(rpc_server_dock.gui_id)
    dock._client = bec_client

    AutoUpdates.enabled = True
    AutoUpdates.create_default_dock = True
    dock.auto_updates = AutoUpdates(gui=dock)
    dock.auto_updates.start_default_dock()
    dock.selected_device = "bpm4i"

    # we need to start the update script manually; normally this is done when the GUI is started
    dock._start_update_script()

    client = bec_client
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)

    # wait for scan to finish
    while not status.status == "COMPLETED":
        qtbot.wait(200)

    last_scan_data = queue.scan_storage.storage[-1].data

    # get data from curves
    plt = dock.auto_updates.get_default_figure()
    widgets = plt.widget_list
    plt_data = widgets[0].get_all_data()

    # check plotted data
    assert plt_data["bpm4i-bpm4i"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4i-bpm4i"]["y"] == last_scan_data["bpm4i"]["bpm4i"].val

    status = scans.grid_scan(
        dev.samx, -10, 10, 5, dev.samy, -5, 5, 5, exp_time=0.05, relative=False
    )

    # wait for scan to finish
    while not status.status == "COMPLETED":
        qtbot.wait(200)

    plt = dock.auto_updates.get_default_figure()
    widgets = plt.widget_list
    plt_data = widgets[0].get_all_data()

    last_scan_data = queue.scan_storage.storage[-1].data

    # check plotted data
    assert plt_data[f"Scan {status.scan.scan_number}"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data[f"Scan {status.scan.scan_number}"]["y"] == last_scan_data["samy"]["samy"].val
