import time

import numpy as np
import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.cli.client import Image, MotorMap, MultiWaveform, ScatterWaveform, Waveform
from bec_widgets.cli.rpc.rpc_base import RPCReference
from bec_widgets.tests.utils import check_remote_data_size


def test_rpc_waveform1d_custom_curve(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec

    wf = dock_area.new("Waveform")

    c1 = wf.plot(x=[1, 2, 3], y=[1, 2, 3])
    c1.set_color("red")
    assert c1._config_dict["color"] == "red"
    c1.set_color("blue")
    assert c1._config_dict["color"] == "blue"

    assert len(wf.curves) == 1


def test_rpc_plotting_shortcuts_init_configs(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec

    wf = dock_area.new("Waveform")
    im = dock_area.new("Image")
    mm = dock_area.new("MotorMap")
    sw = dock_area.new("ScatterWaveform")
    mw = dock_area.new("MultiWaveform")

    c1 = wf.plot(x_name="samx", y_name="bpm4i")
    # Adding custom curves, removing one and adding it again should not crash
    c2 = wf.plot(y=[1, 2, 3], x=[1, 2, 3])
    assert c2.object_name == "Curve_0"
    c2.remove()
    c3 = wf.plot(y=[1, 2, 3], x=[1, 2, 3])
    assert c3.object_name == "Curve_0"

    im.image(monitor="eiger")
    mm.map(x_name="samx", y_name="samy")
    sw.plot(x_name="samx", y_name="samy", z_name="bpm4i")
    assert sw.main_curve.object_name == "bpm4i_bpm4i"
    # Create a new curve on the scatter waveform should replace the old one
    sw.plot(x_name="samx", y_name="samy", z_name="bpm4a")
    assert sw.main_curve.object_name == "bpm4a_bpm4a"
    mw.plot(monitor="waveform")
    # Adding multiple custom curves sho

    # Checking if classes are correctly initialised
    assert len(dock_area.widget_list()) == 5
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
    assert c1._config_dict["signal"] == {
        "dap": None,
        "name": "bpm4i",
        "entry": "bpm4i",
        "dap_oversample": 1,
    }
    assert c1._config_dict["source"] == "device"
    assert c1._config_dict["label"] == "bpm4i-bpm4i"


def test_rpc_waveform_scan(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    wf = dock_area.new("Waveform")

    # add 3 different curves to track
    wf.plot(x_name="samx", y_name="bpm4i")
    wf.plot(x_name="samx", y_name="bpm3a")
    wf.plot(x_name="samx", y_name="bpm4d")

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    # FIXME if this gets flaky, we wait for status.scan.scan_id to be in client.history[-1] and then fetch data from history
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


@pytest.mark.timeout(100)
def test_async_plotting(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans

    # Test add
    dev.waveform.sim.select_model("GaussianModel")
    dev.waveform.sim.params = {"amplitude": 1000, "center": 4000, "sigma": 300}
    dev.waveform.async_update.set("add").wait()
    dev.waveform.waveform_shape.set(10000).wait()
    wf = dock_area.new("Waveform")
    curve = wf.plot(y_name="waveform")

    status = scans.line_scan(dev.samx, -5, 5, steps=5, exp_time=0.05, relative=False)
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


def test_rpc_image(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec

    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans

    im = dock_area.new("Image")
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

    dock_area = gui.bec

    motor_map = dock_area.new("MotorMap")
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

    dock_area = gui.bec

    wf = dock_area.new("Waveform")
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


def test_waveform_passing_device(qtbot, bec_client_lib, connected_client_gui_obj):
    gui = connected_client_gui_obj
    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans

    dock_area = gui.bec

    wf = dock_area.new("Waveform")
    c1 = wf.plot(
        y_name=dev.samx, y_entry=dev.samx.setpoint
    )  # using setpoint to not use readback signal

    assert c1.object_name == "samx_samx_setpoint"

    status = scans.line_scan(dev.samx, -5, 5, steps=5, exp_time=0.05, relative=False)
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
    x_data, y_data = c1.get_data()
    assert np.array_equal(y_data, last_scan_data.devices.samx.samx_setpoint.read().get("value"))


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "history_selector", ["scan_id", "scan_number"]
)  # ensure unique curves per run
def test_rpc_waveform_history_curve(
    qtbot, bec_client_lib, connected_client_gui_obj, history_selector
):
    """
    E2E test for the new history curve feature:
    - Run 3 scans
    - For each scan, fetch history curve data using either scan_id OR scan_number (parametrized)
    - Compare waveform data with BEC client scan data
    Note: Parameterization prevents adding the same logical curve twice (which would collide on label).
    """
    gui = connected_client_gui_obj
    dock_area = gui.bec
    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    wf = dock_area.new("Waveform")

    # Collect references for validation
    scan_meta = []  # list of dicts with scan_id, scan_number, data

    # Run 3 scans and collect their metadata and data
    for i in range(3):
        status = scans.line_scan(dev.samx, -5 + i, 5 + i, steps=10, exp_time=0.01, relative=False)
        status.wait()

        # Wait until the history entry appears and corresponds to this scan
        def _wait_for_scan_in_history():
            if len(client.history) == 0:
                return False
            return client.history[-1].metadata.bec.get("scan_id", None) == status.scan.scan_id

        qtbot.waitUntil(_wait_for_scan_in_history, timeout=10000)

        hist_item = client.history[-1]
        item = queue.scan_storage.storage[-1]
        data = item.live_data if hasattr(item, "live_data") else item.data
        scan_meta.append(
            {
                "scan_id": hist_item.metadata.bec.get("scan_id"),
                "scan_number": hist_item.metadata.bec.get("scan_number"),
                "data": data,
            }
        )

    # For each scan, fetch history curve by the chosen selector and compare to client data
    for meta in scan_meta:
        sel_value = meta[history_selector]
        scan_data = meta["data"]

        # Add curve from history using the chosen selector; single curve per scan to avoid duplicates
        kwargs = {history_selector: sel_value}
        curve = wf.plot(x_name="samx", y_name="bpm4i", **kwargs)

        num_elements = 10

        # Wait until curve has the expected number of points
        def _curve_ready():
            try:
                x, y = curve.get_data()
            except Exception:
                return False
            return x is not None and len(x) == num_elements and len(y) == num_elements

        qtbot.waitUntil(_curve_ready, timeout=10000)

        # Get plotted data
        x_vals, y_vals = curve.get_data()

        # Compare against BEC client scan data
        np.testing.assert_equal(x_vals, np.array(scan_data["samx"]["samx"].val))
        np.testing.assert_equal(y_vals, np.array(scan_data["bpm4i"]["bpm4i"].val))

        # Clean up
        curve.remove()
