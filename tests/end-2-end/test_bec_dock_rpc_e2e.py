import pytest

from bec_widgets.cli import Image, MotorMap, Waveform
from bec_widgets.cli.rpc.rpc_base import RPCReference

# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-locals
# pylint: disable=protected-access


def test_gui_rpc_registry(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.new("cool_dock_area")

    def check_dock_area_registered():
        return dock_area._gui_id in gui._server_registry

    qtbot.waitUntil(check_dock_area_registered, timeout=5000)
    assert hasattr(gui, "cool_dock_area")

    dock = dock_area.new("dock_0")

    def check_dock_registered():
        return dock._gui_id in gui._server_registry

    qtbot.waitUntil(check_dock_registered, timeout=5000)
    assert hasattr(gui.cool_dock_area, "dock_0")


def test_rpc_add_dock_with_plots_e2e(qtbot, bec_client_lib, connected_client_gui_obj):

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
        return all(
            [gui_id in gui._server_registry for gui_id in [d0._gui_id, d1._gui_id, d2._gui_id]]
        )

    # Waii until docks are registered
    qtbot.waitUntil(check_docks_registered, timeout=5000)
    qtbot.wait(500)
    assert len(dock.panels) == 3
    assert hasattr(gui.bec, "dock_0")

    # Add 3 figures with some widgets
    wf = d0.new("Waveform")
    im = d1.new("Image")
    mm = d2.new("MotorMap")

    def check_figs_registered():
        return all(
            [gui_id in gui._server_registry for gui_id in [wf._gui_id, im._gui_id, mm._gui_id]]
        )

    qtbot.waitUntil(check_figs_registered, timeout=5000)

    assert len(d0.element_list) == 1
    assert len(d1.element_list) == 1
    assert len(d2.element_list) == 1

    assert wf.__class__.__name__ == "RPCReference"
    assert wf.__class__ == RPCReference
    assert gui._ipython_registry[wf._gui_id].__class__ == Waveform
    assert im.__class__.__name__ == "RPCReference"
    assert im.__class__ == RPCReference
    assert gui._ipython_registry[im._gui_id].__class__ == Image
    assert mm.__class__.__name__ == "RPCReference"
    assert mm.__class__ == RPCReference
    assert gui._ipython_registry[mm._gui_id].__class__ == MotorMap

    mm.map("samx", "samy")
    curve = wf.plot(x_name="samx", y_name="bpm4i")
    im_item = im.image("eiger")

    assert curve.__class__.__name__ == "RPCReference"
    assert curve.__class__ == RPCReference
    assert im_item.__class__.__name__ == "RPCReference"
    assert im_item.__class__ == RPCReference


def test_dock_manipulations_e2e(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec

    d0 = dock_area.new("dock_0")
    d1 = dock_area.new("dock_1")
    d2 = dock_area.new("dock_2")

    assert hasattr(gui.bec, "dock_0")
    assert hasattr(gui.bec, "dock_1")
    assert hasattr(gui.bec, "dock_2")
    assert len(gui.bec.panels) == 3

    d0.detach()
    dock_area.detach_dock("dock_2")
    # How can we properly check that the dock is detached?
    assert len(gui.bec.panels) == 3

    d0.attach()
    assert len(gui.bec.panels) == 3

    gui_id = d2._gui_id

    def wait_for_dock_removed():
        return gui_id not in gui._ipython_registry

    d2.remove()
    qtbot.waitUntil(wait_for_dock_removed, timeout=5000)
    assert len(gui.bec.panels) == 2

    ids = [widget._gui_id for widget in dock_area.panel_list]

    def wait_for_docks_removed():
        return all(widget_id not in gui._ipython_registry for widget_id in ids)

    dock_area.delete_all()
    qtbot.waitUntil(wait_for_docks_removed, timeout=5000)
    assert len(gui.bec.panels) == 0


def test_ring_bar(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec
    d0 = dock_area.new("dock_0")

    bar = d0.new("RingProgressBar")
    assert bar.__class__.__name__ == "RPCReference"
    assert gui._ipython_registry[bar._gui_id].__class__.__name__ == "RingProgressBar"


def test_rpc_gui_obj(connected_client_gui_obj, qtbot):
    gui = connected_client_gui_obj

    qtbot.waitUntil(lambda: len(gui.windows) == 1, timeout=3000)
    assert gui.windows["bec"] is gui.bec
    mw = gui.bec
    assert mw.__class__.__name__ == "RPCReference"
    assert gui._ipython_registry[mw._gui_id].__class__.__name__ == "BECDockArea"

    xw = gui.new("X")
    assert xw.__class__.__name__ == "RPCReference"
    assert gui._ipython_registry[xw._gui_id].__class__.__name__ == "BECDockArea"
    assert len(gui.windows) == 2

    assert gui._gui_is_alive()
    gui.kill_server()
    assert not gui._gui_is_alive()
    gui.start(wait=True)
    assert gui._gui_is_alive()
    # calling start multiple times should not change anything
    gui.start(wait=True)
    gui.start(wait=True)

    def wait_for_gui_started():
        return "bec" in gui.windows

    qtbot.waitUntil(wait_for_gui_started, timeout=3000)
    # gui.windows should have bec with gui_id 'bec'
    assert len(gui.windows) == 1

    # communication should work, main dock area should have same id and be visible

    yw = gui.new("Y")
    assert len(gui.windows) == 2
    yw.remove()
    assert len(gui.windows) == 1  # only bec is left


def test_rpc_call_with_exception_in_safeslot_error_popup(connected_client_gui_obj, qtbot):
    gui = connected_client_gui_obj

    gui.bec.new("test")
    qtbot.waitUntil(lambda: len(gui.bec.panels) == 1)  # test
    qtbot.wait(500)
    with pytest.raises(ValueError):
        gui.bec.new("test")
        # time.sleep(0.1)
