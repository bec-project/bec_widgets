import time

import numpy as np
import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.cli.client import BECFigure, BECImageShow, BECMotorMap, BECWaveform
from bec_widgets.cli.rpc.rpc_base import RPCReference
from bec_widgets.tests.utils import check_remote_data_size
from bec_widgets.utils import Colors

# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-locals
# pylint: disable=protected-access


def test_gui_rpc_registry(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.new("cool_dock_area")

    def check_dock_area_registered():
        return dock_area._gui_id in gui._registry_state

    qtbot.waitUntil(check_dock_area_registered, timeout=5000)
    assert hasattr(gui, "cool_dock_area")

    dock = dock_area.new("dock_0")

    def check_dock_registered():
        dock_dict = (
            gui._registry_state.get(dock_area._gui_id, {}).get("config", {}).get("docks", {})
        )
        return len(dock_dict) == 1

    qtbot.waitUntil(check_dock_registered, timeout=5000)
    assert hasattr(gui.cool_dock_area, "dock_0")

    # assert hasattr(dock_area, "dock_0")


def test_rpc_add_dock_with_figure_e2e(qtbot, bec_client_lib, connected_client_gui_obj):

    gui = connected_client_gui_obj
    # BEC client shortcuts
    dock = gui.bec
    client = bec_client_lib
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    # Create 3 docks
    d0 = dock.new("dock_0")
    d1 = dock.new("dock_1")
    d2 = dock.new("dock_2")

    # Check that callback for dock_registry is done
    def check_docks_registered():
        dock_register = dock._parent._registry_state.get(dock._gui_id, None)
        if dock_register is not None:
            n_docks = dock_register.get("config", {}).get("docks", {})
            return len(n_docks) == 3
        return False
        # raise AssertionError("Docks not registered yet")

    # Waii until docks are registered
    qtbot.waitUntil(check_docks_registered, timeout=5000)
    qtbot.wait(500)
    assert len(dock.panels) == 3
    assert hasattr(gui.bec, "dock_0")

    # Add 3 figures with some widgets
    fig0 = d0.new("BECFigure")
    fig1 = d1.new("BECFigure")
    fig2 = d2.new("BECFigure")

    def check_fig2_registered():
        # return hasattr(d2, "BECFigure_2")
        dock_config = dock._parent._registry_state[dock._gui_id]["config"]["docks"].get(
            d2.widget_name, {}
        )
        if dock_config:
            n_widgets = dock_config.get("widgets", {})
            if any(widget_name.startswith("BECFigure") for widget_name in n_widgets.keys()):
                return True
        raise AssertionError("Figure not registered yet")

    qtbot.waitUntil(check_fig2_registered, timeout=5000)

    assert len(d0.element_list) == 1
    assert len(d1.element_list) == 1
    assert len(d2.element_list) == 1

    assert fig1.__class__.__name__ == "RPCReference"
    assert fig1.__class__ == RPCReference
    assert gui._ipython_registry[fig1._gui_id].__class__ == BECFigure
    assert fig2.__class__.__name__ == "RPCReference"
    assert fig2.__class__ == RPCReference
    assert gui._ipython_registry[fig2._gui_id].__class__ == BECFigure

    mm = fig0.motor_map("samx", "samy")
    plt = fig1.plot(x_name="samx", y_name="bpm4i")
    im = fig2.image("eiger")

    assert mm.__class__.__name__ == "RPCReference"
    assert mm.__class__ == RPCReference
    assert plt.__class__.__name__ == "RPCReference"
    assert plt.__class__ == RPCReference
    assert im.__class__.__name__ == "RPCReference"
    assert im.__class__ == RPCReference


def test_dock_manipulations_e2e(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock = gui.bec

    d0 = dock.new("dock_0")
    d1 = dock.new("dock_1")
    d2 = dock.new("dock_2")

    assert hasattr(gui.bec, "dock_0")
    assert hasattr(gui.bec, "dock_1")
    assert hasattr(gui.bec, "dock_2")
    assert len(gui.bec.panels) == 3

    d0.detach()
    dock.detach_dock("dock_2")
    # How can we properly check that the dock is detached?
    assert len(gui.bec.panels) == 3

    d0.attach()
    assert len(gui.bec.panels) == 3

    def wait_for_dock_removed():
        dock_config = gui._registry_state[gui.bec._gui_id]["config"]["docks"]
        return len(dock_config.keys()) == 2

    d2.remove()
    qtbot.waitUntil(wait_for_dock_removed, timeout=5000)
    assert len(gui.bec.panels) == 2

    def wait_for_docks_removed():
        dock_config = gui._registry_state[gui.bec._gui_id]["config"]["docks"]
        return len(dock_config.keys()) == 0

    dock.clear_all()
    qtbot.waitUntil(wait_for_docks_removed, timeout=5000)
    assert len(gui.bec.panels) == 0


def test_ring_bar(connected_client_dock):
    dock = connected_client_dock

    d0 = dock.add_dock(name="dock_0")

    bar = d0.add_widget("RingProgressBar")
    assert bar.__class__.__name__ == "RingProgressBar"

    plt = get_default_figure()

    gui.selected_device = "bpm4i"

    status = scans.line_scan(dev.samx, -5, 5, steps=10, exp_time=0.05, relative=False)
    status.wait()

    # get data from curves
    widgets = plt.widget_list
    qtbot.waitUntil(lambda: len(plt.widget_list) > 0, timeout=5000)

    item = queue.scan_storage.storage[-1]
    last_scan_data = item.live_data if hasattr(item, "live_data") else item.data

    num_elements = 10

    plot_name = f"Scan {status.scan.scan_number} - {dock.selected_device}"

    qtbot.waitUntil(lambda: check_remote_data_size(widgets[0], plot_name, num_elements))
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

    plt = auto_updates.get_default_figure()
    widgets = plt.widget_list

    qtbot.waitUntil(lambda: len(plt.widget_list) > 0, timeout=5000)

    item = queue.scan_storage.storage[-1]
    last_scan_data = item.live_data if hasattr(item, "live_data") else item.data

    plot_name = f"Scan {status.scan.scan_number} - bpm4i"

    num_elements_bec = 25
    qtbot.waitUntil(lambda: check_remote_data_size(widgets[0], plot_name, num_elements_bec))
    plt_data = widgets[0].get_all_data()

    # check plotted data
    assert (
        plt_data[f"Scan {status.scan.scan_number} - {dock.selected_device}"]["x"]
        == last_scan_data["samx"]["samx"].val
    )
    assert (
        plt_data[f"Scan {status.scan.scan_number} - {dock.selected_device}"]["y"]
        == last_scan_data["samy"]["samy"].val
    )


def test_rpc_gui_obj(connected_client_gui_obj, qtbot):
    gui = connected_client_gui_obj

    assert gui.selected_device is None
    assert len(gui.windows) == 1
    assert gui.windows["bec"] is gui.bec
    mw = gui.bec
    assert mw.__class__.__name__ == "BECDockArea"

    xw = gui.new("X")
    assert xw.__class__.__name__ == "BECDockArea"
    assert len(gui.windows) == 2

    gui_info = gui._dump()
    mw_info = gui_info[mw._gui_id]
    assert mw_info["title"] == "BEC"
    assert mw_info["visible"]
    xw_info = gui_info[xw._gui_id]
    assert xw_info["title"] == "BEC - X"
    assert xw_info["visible"]

    gui.hide()
    gui_info = gui._dump()
    assert not any(windows["visible"] for windows in gui_info.values())

    gui.show()
    gui_info = gui._dump()
    assert all(windows["visible"] for windows in gui_info.values())

    assert gui._gui_is_alive()
    gui._close()
    assert not gui._gui_is_alive()
    gui._start_server(wait=True)
    assert gui._gui_is_alive()
    # calling start multiple times should not change anything
    gui._start_server(wait=True)
    gui._start()
    # gui.windows should have bec with gui_id 'bec'
    assert len(gui.windows) == 1
    assert gui.windows["bec"]._gui_id == mw._gui_id
    # communication should work, main dock area should have same id and be visible
    gui_info = gui._dump()
    assert gui_info[mw._gui_id]["visible"]

    with pytest.raises(RuntimeError):
        gui.bec.delete()

    yw = gui.new("Y")
    assert len(gui.windows) == 2
    yw.delete()
    assert len(gui.windows) == 1
    # check it is really deleted on server
    gui_info = gui._dump()
    assert yw._gui_id not in gui_info


def test_rpc_call_with_exception_in_safeslot_error_popup(connected_client_gui_obj, qtbot):
    gui = connected_client_gui_obj

    gui.main.add_dock("test")
    qtbot.waitUntil(lambda: len(gui.main.panels) == 2)  # default_figure + test
    qtbot.wait(500)
    with pytest.raises(ValueError):
        gui.bec.add_dock("test")
        # time.sleep(0.1)
