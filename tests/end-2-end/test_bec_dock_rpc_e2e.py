import numpy as np
import pytest
from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.cli.auto_updates import AutoUpdates
from bec_widgets.cli.client import BECDockArea, BECFigure, BECImageShow, BECMotorMap, BECWaveform
from bec_widgets.utils import Colors


@pytest.fixture(name="bec_client")
def cli_bec_client(rpc_server_dock):
    """
    Fixture to create a BECClient instance that is independent of the GUI.
    """
    # pylint: disable=protected-access
    cli_client = BECClient(forced=True, config=rpc_server_dock.client._service_config)
    cli_client.start()
    yield cli_client
    cli_client.shutdown()


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


def test_spiral_bar(rpc_server_dock):
    dock = BECDockArea(rpc_server_dock.gui_id)
    dock_server = rpc_server_dock.gui

    d0 = dock.add_dock(name="dock_0")

    bar = d0.add_widget_bec("SpiralProgressBar")
    assert bar.__class__.__name__ == "SpiralProgressBar"

    bar.set_number_of_bars(5)
    bar.set_colors_from_map("viridis")
    bar.set_value([10, 20, 30, 40, 50])

    bar_server = dock_server.docks["dock_0"].widgets[0]

    expected_colors = Colors.golden_angle_color("viridis", 5, "RGB")
    bar_colors = [ring.color.getRgb() for ring in bar_server.rings]
    bar_values = [ring.config.value for ring in bar_server.rings]
    assert bar_values == [10, 20, 30, 40, 50]
    assert bar_colors == expected_colors


def test_spiral_bar_scan_update(rpc_server_dock, qtbot):
    dock = BECDockArea(rpc_server_dock.gui_id)
    dock_server = rpc_server_dock.gui

    d0 = dock.add_dock("dock_0")

    d0.add_widget_bec("SpiralProgressBar")

    client = rpc_server_dock.client
    dev = client.device_manager.devices
    scans = client.scans

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)

    while not status.status == "COMPLETED":
        qtbot.wait(200)

    qtbot.wait(200)
    bar_server = dock_server.docks["dock_0"].widgets[0]
    assert bar_server.config.num_bars == 1
    np.testing.assert_allclose(bar_server.rings[0].config.value, 10, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[0].config.min_value, 0, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[0].config.max_value, 10, atol=0.1)

    status = scans.grid_scan(dev.samx, -5, 5, 4, dev.samy, -10, 10, 4, relative=True, exp_time=0.1)

    while not status.status == "COMPLETED":
        qtbot.wait(200)

    qtbot.wait(200)
    assert bar_server.config.num_bars == 1
    np.testing.assert_allclose(bar_server.rings[0].config.value, 16, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[0].config.min_value, 0, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[0].config.max_value, 16, atol=0.1)

    init_samx = dev.samx.read()["samx"]["value"]
    init_samy = dev.samy.read()["samy"]["value"]
    final_samx = init_samx + 5
    final_samy = init_samy + 10

    dev.samx.velocity.put(5)
    dev.samy.velocity.put(5)

    status = scans.umv(dev.samx, 5, dev.samy, 10, relative=True)

    while not status.status == "COMPLETED":
        qtbot.wait(200)

    qtbot.wait(200)
    assert bar_server.config.num_bars == 2
    np.testing.assert_allclose(bar_server.rings[0].config.value, final_samx, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[1].config.value, final_samy, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[0].config.min_value, init_samx, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[1].config.min_value, init_samy, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[0].config.max_value, final_samx, atol=0.1)
    np.testing.assert_allclose(bar_server.rings[1].config.max_value, final_samy, atol=0.1)


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
