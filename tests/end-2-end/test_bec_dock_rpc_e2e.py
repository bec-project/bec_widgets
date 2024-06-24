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


def test_ring_bar(rpc_server_dock):
    dock = BECDockArea(rpc_server_dock)

    d0 = dock.add_dock(name="dock_0")

    bar = d0.add_widget("RingProgressBar")
    assert bar.__class__.__name__ == "RingProgressBar"

    bar.set_number_of_bars(5)
    bar.set_colors_from_map("viridis")
    bar.set_value([10, 20, 30, 40, 50])

    bar_config = bar.config_dict

    expected_colors = [list(color) for color in Colors.golden_angle_color("viridis", 5, "RGB")]
    bar_colors = [ring.config_dict["color"] for ring in bar.rings]
    bar_values = [ring.config_dict["value"] for ring in bar.rings]
    assert bar_config["num_bars"] == 5
    assert bar_values == [10, 20, 30, 40, 50]
    assert bar_colors == expected_colors


def test_ring_bar_scan_update(bec_client_lib, rpc_server_dock):
    dock = BECDockArea(rpc_server_dock)

    d0 = dock.add_dock("dock_0")

    bar = d0.add_widget("RingProgressBar")

    client = bec_client_lib
    dev = client.device_manager.devices
    dev.samx.tolerance.set(0)
    dev.samy.tolerance.set(0)
    scans = client.scans

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    bar_config = bar.config_dict
    assert bar_config["num_bars"] == 1
    assert bar_config["rings"][0]["value"] == 10
    assert bar_config["rings"][0]["min_value"] == 0
    assert bar_config["rings"][0]["max_value"] == 10

    status = scans.grid_scan(dev.samx, -5, 5, 4, dev.samy, -10, 10, 4, relative=True, exp_time=0.1)
    status.wait()

    bar_config = bar.config_dict
    assert bar_config["num_bars"] == 1
    assert bar_config["rings"][0]["value"] == 16
    assert bar_config["rings"][0]["min_value"] == 0
    assert bar_config["rings"][0]["max_value"] == 16

    init_samx = dev.samx.read()["samx"]["value"]
    init_samy = dev.samy.read()["samy"]["value"]
    final_samx = init_samx + 5
    final_samy = init_samy + 10

    dev.samx.velocity.put(5)
    dev.samy.velocity.put(5)

    status = scans.umv(dev.samx, 5, dev.samy, 10, relative=True)
    status.wait()

    bar_config = bar.config_dict
    assert bar_config["num_bars"] == 2
    assert bar_config["rings"][0]["value"] == final_samx
    assert bar_config["rings"][1]["value"] == final_samy
    assert bar_config["rings"][0]["min_value"] == init_samx
    assert bar_config["rings"][0]["max_value"] == final_samx
    assert bar_config["rings"][1]["min_value"] == init_samy
    assert bar_config["rings"][1]["max_value"] == final_samy


def test_auto_update(bec_client_lib, rpc_server_dock):
    dock = BECDockArea(rpc_server_dock)

    AutoUpdates.enabled = True
    AutoUpdates.create_default_dock = True
    dock.auto_updates = AutoUpdates(gui=dock)
    dock.auto_updates.start_default_dock()
    dock.selected_device = "bpm4i"

    # we need to start the update script manually; normally this is done when the GUI is started
    dock._start_update_script()

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    last_scan_data = queue.scan_storage.storage[-1].data

    # get data from curves
    plt = dock.auto_updates.get_default_figure()
    widgets = plt.widget_list
    plt_data = widgets[0].get_all_data()

    # check plotted data
    assert (
        plt_data[f"Scan {status.scan.scan_number} - bpm4i"]["x"]
        == last_scan_data["samx"]["samx"].val
    )
    assert (
        plt_data[f"Scan {status.scan.scan_number} - bpm4i"]["y"]
        == last_scan_data["bpm4i"]["bpm4i"].val
    )

    status = scans.grid_scan(
        dev.samx, -10, 10, 5, dev.samy, -5, 5, 5, exp_time=0.05, relative=False
    )
    status.wait()

    plt = dock.auto_updates.get_default_figure()
    widgets = plt.widget_list
    plt_data = widgets[0].get_all_data()

    last_scan_data = queue.scan_storage.storage[-1].data

    # check plotted data
    assert (
        plt_data[f"Scan {status.scan.scan_number} - {dock.selected_device}"]["x"]
        == last_scan_data["samx"]["samx"].val
    )
    assert (
        plt_data[f"Scan {status.scan.scan_number} - {dock.selected_device}"]["y"]
        == last_scan_data["samy"]["samy"].val
    )
