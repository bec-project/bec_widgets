import numpy as np
import pytest
from bec_lib import MessageEndpoints

from bec_widgets.cli.client import BECFigure, BECImageShow, BECMotorMap, BECWaveform


def test_rpc_waveform1d_custom_curve(rpc_server_figure, qtbot):
    fig = BECFigure(rpc_server_figure.gui_id)
    fig_server = rpc_server_figure.gui

    ax = fig.add_plot()
    curve = ax.add_curve_custom([1, 2, 3], [1, 2, 3])
    curve.set_color("red")
    curve = ax.curves[0]
    curve.set_color("blue")

    assert len(fig_server.widgets) == 1
    assert len(fig_server.widgets[ax.rpc_id].curves) == 1


def test_rpc_plotting_shortcuts_init_configs(rpc_server_figure, qtbot):
    fig = BECFigure(rpc_server_figure.gui_id)
    fig_server = rpc_server_figure.gui

    plt = fig.plot("samx", "bpm4i")
    im = fig.image("eiger")
    motor_map = fig.motor_map("samx", "samy")
    plt_z = fig.add_plot("samx", "samy", "bpm4i")

    # Checking if classes are correctly initialised
    assert len(fig_server.widgets) == 4
    assert plt.__class__.__name__ == "BECWaveform"
    assert plt.__class__ == BECWaveform
    assert im.__class__.__name__ == "BECImageShow"
    assert im.__class__ == BECImageShow
    assert motor_map.__class__.__name__ == "BECMotorMap"
    assert motor_map.__class__ == BECMotorMap

    # check if the correct devices are set
    # plot
    assert plt.config_dict["curves"]["bpm4i-bpm4i"]["signals"] == {
        "source": "scan_segment",
        "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
        "y": {"name": "bpm4i", "entry": "bpm4i", "unit": None, "modifier": None, "limits": None},
        "z": None,
    }
    # image
    assert im.config_dict["images"]["eiger"]["monitor"] == "eiger"
    # motor map
    assert motor_map.config_dict["signals"] == {
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
    # plot with z scatter
    assert plt_z.config_dict["curves"]["bpm4i-bpm4i"]["signals"] == {
        "source": "scan_segment",
        "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
        "y": {"name": "samy", "entry": "samy", "unit": None, "modifier": None, "limits": None},
        "z": {"name": "bpm4i", "entry": "bpm4i", "unit": None, "modifier": None, "limits": None},
    }


def test_rpc_waveform_scan(rpc_server_figure, qtbot):
    fig = BECFigure(rpc_server_figure.gui_id)

    # add 3 different curves to track
    plt = fig.plot("samx", "bpm4i")
    fig.plot("samx", "bpm3a")
    fig.plot("samx", "bpm4d")

    client = rpc_server_figure.client
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)

    # wait for scan to finish
    while not status.status == "COMPLETED":
        qtbot.wait(200)

    last_scan_data = queue.scan_storage.storage[-1].data

    # get data from curves
    plt_data = plt.get_all_data()

    # check plotted data
    assert plt_data["bpm4i-bpm4i"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4i-bpm4i"]["y"] == last_scan_data["bpm4i"]["bpm4i"].val
    assert plt_data["bpm3a-bpm3a"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm3a-bpm3a"]["y"] == last_scan_data["bpm3a"]["bpm3a"].val
    assert plt_data["bpm4d-bpm4d"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4d-bpm4d"]["y"] == last_scan_data["bpm4d"]["bpm4d"].val


def test_rpc_image(rpc_server_figure, qtbot):
    fig = BECFigure(rpc_server_figure.gui_id)

    im = fig.image("eiger")

    client = rpc_server_figure.client
    dev = client.device_manager.devices
    scans = client.scans

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)

    # wait for scan to finish
    while not status.status == "COMPLETED":
        qtbot.wait(200)

    last_image_device = client.connector.get_last(MessageEndpoints.device_monitor("eiger"))[
        "data"
    ].data
    qtbot.wait(500)
    last_image_plot = im.images[0].get_data()

    # check plotted data
    np.testing.assert_equal(last_image_device, last_image_plot)


def test_rpc_motor_map(rpc_server_figure, qtbot):
    fig = BECFigure(rpc_server_figure.gui_id)
    fig_server = rpc_server_figure.gui

    motor_map = fig.motor_map("samx", "samy")

    client = rpc_server_figure.client
    dev = client.device_manager.devices
    scans = client.scans

    initial_pos_x = dev.samx.read()["samx"]["value"]
    initial_pos_y = dev.samy.read()["samy"]["value"]

    status = scans.mv(dev.samx, 1, dev.samy, 2, relative=True)

    # wait for scan to finish
    while not status.status == "COMPLETED":
        qtbot.wait(200)
    final_pos_x = dev.samx.read()["samx"]["value"]
    final_pos_y = dev.samy.read()["samy"]["value"]

    # check plotted data
    motor_map_data = motor_map.get_data()

    np.testing.assert_equal(
        [motor_map_data["x"][0], motor_map_data["y"][0]], [initial_pos_x, initial_pos_y]
    )
    np.testing.assert_equal(
        [motor_map_data["x"][-1], motor_map_data["y"][-1]], [final_pos_x, final_pos_y]
    )
