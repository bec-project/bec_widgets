import pytest

from bec_widgets.cli.client import Image, MotorMap, Waveform
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

    widget = dock_area.new("Waveform", object_name="cool_waveform")

    def check_widget_registered():
        return widget._gui_id in gui._server_registry

    qtbot.waitUntil(check_widget_registered, timeout=5000)
    assert hasattr(gui.cool_dock_area, widget.object_name)


def test_rpc_add_dock_with_plots_e2e(qtbot, bec_client_lib, connected_client_gui_obj):

    gui = connected_client_gui_obj
    # BEC client shortcuts
    dock_area = gui.bec

    # Add 3 figures with some widgets
    wf = dock_area.new("Waveform")
    im = dock_area.new("Image")
    mm = dock_area.new("MotorMap")

    def check_widgets_registered():
        return all(
            gui_id in gui._server_registry for gui_id in [wf._gui_id, im._gui_id, mm._gui_id]
        )

    qtbot.waitUntil(check_widgets_registered, timeout=5000)
    assert len(dock_area.widget_list()) == 3

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
    curve = wf.plot(device_x="samx", device_y="bpm4i")
    im_item = im.image(device="eiger", signal="preview")

    assert curve.__class__.__name__ == "RPCReference"
    assert curve.__class__ == RPCReference
    assert im_item.__class__.__name__ == "RPCReference"
    assert im_item.__class__ == RPCReference


def test_dock_manipulations_e2e(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec

    w0 = dock_area.new("Waveform")
    w1 = dock_area.new("Waveform")
    w2 = dock_area.new("Waveform")

    qtbot.waitUntil(
        lambda: all(
            gui_id in gui._server_registry for gui_id in [w0._gui_id, w1._gui_id, w2._gui_id]
        ),
        timeout=5000,
    )

    assert hasattr(gui.bec, "Waveform")
    assert hasattr(gui.bec, "Waveform_0")
    assert hasattr(gui.bec, "Waveform_1")
    assert len(gui.bec.widget_list()) == 3

    w0.detach()
    w2.detach()
    assert len(gui.bec.widget_list()) == 3

    w0.attach()
    w2.attach()
    assert len(gui.bec.widget_list()) == 3

    gui_id = w2._gui_id

    def wait_for_dock_removed():
        return gui_id not in gui._ipython_registry

    w2.remove()
    qtbot.waitUntil(wait_for_dock_removed, timeout=5000)
    assert len(gui.bec.widget_list()) == 2

    dock_area.delete_all()

    def wait_for_all_docks_deleted():
        return len(gui.bec.widget_list()) == 0

    qtbot.waitUntil(wait_for_all_docks_deleted, timeout=5000)
    assert len(gui.bec.widget_list()) == 0


def test_ring_bar(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.bec

    bar = dock_area.new("RingProgressBar")
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
    xw.delete_all()
    qtbot.waitUntil(lambda: len(gui.windows) == 2, timeout=3000)
    assert xw.__class__.__name__ == "RPCReference"
    assert gui._ipython_registry[xw._gui_id].__class__.__name__ == "BECDockArea"
    assert len(gui.windows) == 2

    assert gui._gui_is_alive()
    qtbot.wait(500)
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
    qtbot.waitUntil(lambda: len(gui.windows) == 1, timeout=3000)
    assert len(gui.windows) == 1

    # communication should work, main dock area should have same id and be visible

    yw = gui.new("Y")
    yw.delete_all()
    qtbot.waitUntil(lambda: len(gui.windows) == 2, timeout=3000)
    assert len(gui.windows) == 2
    yw.remove()
    qtbot.waitUntil(lambda: len(gui.windows) == 1, timeout=3000)
    assert len(gui.windows) == 1  # only bec is left
