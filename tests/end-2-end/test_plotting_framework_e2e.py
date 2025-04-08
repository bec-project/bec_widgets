import time

import numpy as np
import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.cli.client import Image, MotorMap, MultiWaveform, ScatterWaveform, Waveform
from bec_widgets.cli.rpc.rpc_base import RPCReference
from bec_widgets.tests.utils import check_remote_data_size


def test_rpc_waveform1d_custom_curve(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock = gui.bec

    wf = dock.new("wf_dock").new("Waveform")

    c1 = wf.plot(x=[1, 2, 3], y=[1, 2, 3])
    c1.set_color("red")
    assert c1._config_dict["color"] == "red"
    c1.set_color("blue")
    assert c1._config_dict["color"] == "blue"

    assert len(wf.curves) == 1


def test_rpc_plotting_shortcuts_init_configs(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock = gui.bec

    wf = dock.new("wf_dock").new("Waveform")
    im = dock.new("im_dock").new("Image")
    mm = dock.new("mm_dock").new("MotorMap")
    sw = dock.new("sw_dock").new("ScatterWaveform")
    mw = dock.new("mw_dock").new("MultiWaveform")

    c1 = wf.plot(x_name="samx", y_name="bpm4i")
    im_item = im.image(monitor="eiger")
    mm.map(x_name="samx", y_name="samy")
    sw.plot(x_name="samx", y_name="samy", z_name="bpm4i")
    mw.plot(monitor="waveform")

    # Checking if classes are correctly initialised
    assert len(dock.panel_list) == 5
    assert wf.__class__.__name__ == "RPCReference"
    assert wf.__class__ == RPCReference
    assert gui._ipython_registry[wf._gui_id].__class__ == Waveform
    assert im.__class__.__name__ == "RPCReference"
    assert im.__class__ == RPCReference
    assert gui._ipython_registry[im._gui_id].__class__ == Image
    assert mm.__class__.__name__ == "RPCReference"
    assert mm.__class__ == RPCReference
    assert gui._ipython_registry[mm._gui_id].__class__ == MotorMap
    assert sw.__class__.__name__ == "RPCReference"
    assert sw.__class__ == RPCReference
    assert gui._ipython_registry[sw._gui_id].__class__ == ScatterWaveform
    assert mw.__class__.__name__ == "RPCReference"
    assert mw.__class__ == RPCReference
    assert gui._ipython_registry[mw._gui_id].__class__ == MultiWaveform

    # check if the correct devices are set
    # Curve
    assert c1._config["signal"] == {
        "dap": None,
        "name": "bpm4i",
        "entry": "bpm4i",
        "dap_oversample": 1,
    }
    assert c1._config["source"] == "device"
    assert c1._config["label"] == "bpm4i-bpm4i"

    # Image Item
    assert im_item._config["monitor"] == "eiger"
    assert im_item._config["source"] == "auto"


def test_rpc_waveform_scan(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock = gui.bec

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    wf = dock.new("wf_dock").new("Waveform")

    # add 3 different curves to track
    wf.plot(x_name="samx", y_name="bpm4i")
    wf.plot(x_name="samx", y_name="bpm3a")
    wf.plot(x_name="samx", y_name="bpm4d")

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    item = queue.scan_storage.storage[-1]
    last_scan_data = item.live_data if hasattr(item, "live_data") else item.data

    num_elements = 10

    for plot_name in ["bpm4i-bpm4i", "bpm3a-bpm3a", "bpm4d-bpm4d"]:
        qtbot.waitUntil(lambda: check_remote_data_size(wf, plot_name, num_elements))

    # get data from curves
    plt_data = wf.get_all_data()

    # check plotted data
    assert plt_data["bpm4i-bpm4i"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4i-bpm4i"]["y"] == last_scan_data["bpm4i"]["bpm4i"].val
    assert plt_data["bpm3a-bpm3a"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm3a-bpm3a"]["y"] == last_scan_data["bpm3a"]["bpm3a"].val
    assert plt_data["bpm4d-bpm4d"]["x"] == last_scan_data["samx"]["samx"].val
    assert plt_data["bpm4d-bpm4d"]["y"] == last_scan_data["bpm4d"]["bpm4d"].val


def test_async_plotting(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock = gui.bec

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    # Test add
    dev.waveform.sim.select_model("GaussianModel")
    dev.waveform.sim.params = {"amplitude": 1000, "center": 4000, "sigma": 300}
    dev.waveform.async_update.put("add")
    dev.waveform.waveform_shape.put(10000)
    wf = dock.new("wf_dock").new("Waveform")
    curve = wf.plot(y_name="waveform")

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    # Wait for the scan to finish and the data to be available in history
    # Wait until scan_id is in history
    def _wait_for_scan_in_history():
        if len(client.history) == 0:
            return False
        # Once items appear in storage, the last one hast to be the one we just scanned
        return client.history[-1].metadata.bec["scan_id"] == status.scan.scan_id

    qtbot.waitUntil(_wait_for_scan_in_history, timeout=10000)
    last_scan_data = client.history[-1]
    # check plotted data
    x_data, y_data = curve.get_data()
    assert np.array_equal(x_data, np.linspace(0, len(y_data) - 1, len(y_data)))
    assert np.array_equal(
        y_data, last_scan_data.devices.waveform.get("waveform_waveform", {}).read().get("value", [])
    )

    # Check displayed data
    x_data_display, y_data_display = curve._get_displayed_data()
    # Should be not more than 1% difference, actually be closer but this might be flaky
    assert np.isclose(x_data_display[-1], x_data[-1], rtol=0.01)
    # Downsampled data should be smaller than original data
    assert len(y_data_display) < len(y_data)


def test_rpc_image(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock = gui.bec

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    im = dock.new("im_dock").new("Image")
    im.image(monitor="eiger")

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    last_image_device = client.connector.get_last(MessageEndpoints.device_monitor_2d("eiger"))[
        "data"
    ].data
    last_image_plot = im.main_image.get_data()

    # check plotted data
    np.testing.assert_equal(last_image_device, last_image_plot)


def test_rpc_motor_map(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans

    dock = gui.bec
    motor_map = dock.new("mm_dock").new("MotorMap")
    motor_map.map(x_name="samx", y_name="samy")

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


def test_dap_rpc(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans

    dock = gui.bec
    wf = dock.new("wf_dock").new("Waveform")
    wf.plot(x_name="samx", y_name="bpm4i", dap="GaussianModel")

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
        dap_curve = wf.get_curve("bpm4i-bpm4i-GaussianModel")
        fit_params = dap_curve.dap_params
        if fit_params is None:
            return False
        print(fit_params)
        return np.isclose(fit_params["center"], 5, atol=0.5)

    qtbot.waitUntil(wait_for_fit, timeout=10000)

    # Repeat fit after adding a region of interest
    wf.select_roi(region=(3, 7))
    res = scans.line_scan(dev.samx, 0, 8, steps=50, relative=False)
    res.wait()

    qtbot.waitUntil(wait_for_fit, timeout=10000)
