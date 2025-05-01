import pytest

from bec_widgets.cli.client import ImageItem
from bec_widgets.cli.rpc.rpc_base import RPCReference

# pylint: disable=unused-argument
# pylint: disable=protected-access


def test_rpc_reference_objects(connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock = gui.window_list[0].new()
    plt = dock.new(name="fig", widget="Waveform")

    plt.plot(x_name="samx", y_name="bpm4i")

    im = dock.new("Image")
    im.image("eiger")
    motor_map = dock.new("MotorMap")
    motor_map.map("samx", "samy")
    plt_z = dock.new("Waveform")
    plt_z.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    assert len(plt_z.curves) == 1
    assert len(plt.curves) == 1
    assert im.monitor == "eiger"

    assert isinstance(im.main_image, RPCReference)
    image_item = gui._ipython_registry.get(im.main_image._gui_id, None)
    assert isinstance(image_item, ImageItem)
