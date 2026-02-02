import pytest

from bec_widgets.cli.client import ImageItem
from bec_widgets.cli.rpc.rpc_base import RPCReference

# pylint: disable=unused-argument
# pylint: disable=protected-access


def test_rpc_reference_objects(connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_area = gui.window_list[0]
    plt = dock_area.new("Waveform", object_name="fig")

    plt.plot(device_x="samx", device_y="bpm4i")

    im = dock_area.new("Image")
    im.image(device="eiger", signal="preview")
    motor_map = dock_area.new("MotorMap")
    motor_map.map("samx", "samy")
    plt_z = dock_area.new("Waveform")
    plt_z.plot(device_x="samx", device_y="samy", device_z="bpm4i")

    assert len(plt_z.curves) == 1
    assert len(plt.curves) == 1
    assert im.device == "eiger"
    assert im.signal == "preview"

    assert isinstance(im.main_image, RPCReference)
    image_item = gui._ipython_registry.get(im.main_image._gui_id, None)
    assert isinstance(image_item, ImageItem)
