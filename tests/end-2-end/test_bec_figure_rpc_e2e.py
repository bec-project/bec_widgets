import time

import numpy as np
import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.cli.client import BECFigure, BECImageShow, BECMotorMap, BECWaveform


def test_rpc_waveform1d_custom_curve(connected_client_figure):
    fig = BECFigure(connected_client_figure)

    ax = fig.plot()
    curve = ax.plot(x=[1, 2, 3], y=[1, 2, 3])
    curve.set_color("red")
    curve = ax.curves[0]
    curve.set_color("blue")

    assert len(fig.widgets) == 1
    assert len(fig.widgets[ax._rpc_id].curves) == 1


def test_rpc_plotting_shortcuts_init_configs(connected_client_figure, qtbot):
    fig = BECFigure(connected_client_figure)

    plt = fig.plot(x_name="samx", y_name="bpm4i")
    im = fig.image("eiger")
    motor_map = fig.motor_map("samx", "samy")
    plt_z = fig.plot(x_name="samx", y_name="samy", z_name="bpm4i", new=True)

    # Checking if classes are correctly initialised
    assert len(fig.widgets) == 4
    assert plt.__class__.__name__ == "BECWaveform"
    assert plt.__class__ == BECWaveform
    assert im.__class__.__name__ == "BECImageShow"
    assert im.__class__ == BECImageShow
    assert motor_map.__class__.__name__ == "BECMotorMap"
    assert motor_map.__class__ == BECMotorMap

    # check if the correct devices are set
    # plot
    assert plt._config_dict["curves"]["bpm4i-bpm4i"]["signals"] == {
        "dap": None,
        "source": "scan_segment",
        "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
        "y": {"name": "bpm4i", "entry": "bpm4i", "unit": None, "modifier": None, "limits": None},
        "z": None,
    }
    # image
    assert im._config_dict["images"]["eiger"]["monitor"] == "eiger"
    # motor map
    assert motor_map._config_dict["signals"] == {
        "dap": None,
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
    assert plt_z._config_dict["curves"]["bpm4i-bpm4i"]["signals"] == {
        "dap": None,
        "source": "scan_segment",
        "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
        "y": {"name": "samy", "entry": "samy", "unit": None, "modifier": None, "limits": None},
        "z": {"name": "bpm4i", "entry": "bpm4i", "unit": None, "modifier": None, "limits": None},
    }


def test_rpc_waveform_scan(connected_client_figure, bec_client_lib):
    fig = BECFigure(connected_client_figure)

    # add 3 different curves to track
    plt = fig.plot(x_name="samx", y_name="bpm4i")
    fig.plot(x_name="samx", y_name="bpm3a")
    fig.plot(x_name="samx", y_name="bpm4d")

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    item = queue.scan_storage.storage[-1]
    last_scan_data = item.live_data if hasattr(item, "live_data") else item.data

    # get data from curves
    plt_data = plt.get_all_data()

    # check plotted data
    assert plt_data["bpm4i-bpm4i"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4i-bpm4i"]["y"] == last_scan_data["bpm4i"]["bpm4i"].val
    assert plt_data["bpm3a-bpm3a"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm3a-bpm3a"]["y"] == last_scan_data["bpm3a"]["bpm3a"].val
    assert plt_data["bpm4d-bpm4d"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4d-bpm4d"]["y"] == last_scan_data["bpm4d"]["bpm4d"].val


def test_rpc_image(connected_client_figure, bec_client_lib):
    fig = BECFigure(connected_client_figure)

    im = fig.image("eiger")

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    last_image_device = client.connector.get_last(MessageEndpoints.device_monitor_2d("eiger"))[
        "data"
    ].data
    last_image_plot = im.images[0].get_data()

    # check plotted data
    np.testing.assert_equal(last_image_device, last_image_plot)


def test_rpc_motor_map(connected_client_figure, bec_client_lib):
    fig = BECFigure(connected_client_figure)

    motor_map = fig.motor_map("samx", "samy")

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans

    initial_pos_x = dev.samx.read()["samx"]["value"]
    initial_pos_y = dev.samy.read()["samy"]["value"]

    status = scans.mv(dev.samx, 1, dev.samy, 2, relative=True)
    status.wait()

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


def test_dap_rpc(connected_client_figure, bec_client_lib, qtbot):

    fig = BECFigure(connected_client_figure)
    plt = fig.plot(x_name="samx", y_name="bpm4i", dap="GaussianModel")

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans

    dev.bpm4i.sim.select_model("GaussianModel")
    params = dev.bpm4i.sim.params
    params.update(
        {"noise": "uniform", "noise_multiplier": 10, "center": 5, "sigma": 1, "amplitude": 200}
    )
    dev.bpm4i.sim.params = params
    time.sleep(1)

    res = scans.line_scan(dev.samx, 0, 8, steps=50, relative=False)
    res.wait()

    # especially on slow machines, the fit might not be done yet
    # so we wait until the fit reaches the expected value
    def wait_for_fit():
        dap_curve = plt.get_curve("bpm4i-bpm4i-GaussianModel")
        fit_params = dap_curve.dap_params
        if fit_params is None:
            return False
        print(fit_params)
        return np.isclose(fit_params["center"], 5, atol=0.5)

    qtbot.waitUntil(wait_for_fit, timeout=10000)

    # Repeat fit after adding a region of interest
    plt.select_roi(region=(3, 7))
    res = scans.line_scan(dev.samx, 0, 8, steps=50, relative=False)
    res.wait()

    qtbot.waitUntil(wait_for_fit, timeout=10000)


def test_removing_subplots(connected_client_figure, bec_client_lib):
    fig = BECFigure(connected_client_figure)
    plt = fig.plot(x_name="samx", y_name="bpm4i", dap="GaussianModel")
    im = fig.image(monitor="eiger")
    mm = fig.motor_map(motor_x="samx", motor_y="samy")

    assert len(fig.widget_list) == 3

    # removing curves
    assert len(plt.curves) == 2
    plt.curves[0].remove()
    assert len(plt.curves) == 1
    plt.remove_curve("bpm4i-bpm4i")
    assert len(plt.curves) == 0

    # removing all subplots from figure
    plt.remove()
    im.remove()
    mm.remove()

    assert len(fig.widget_list) == 0
