from unittest import mock

import pytest

from bec_widgets.cli.client import Waveform
from bec_widgets.cli.rpc.rpc_base import DeletedWidgetError, RPCBase, RPCReference


@pytest.fixture
def rpc_base():
    yield RPCBase(gui_id="rpc_base_test", name="test")


@pytest.fixture
def rpc_waveform():
    yield Waveform(gui_id="rpc_waveform_test", name="test")


def test_rpc_base(rpc_base):
    """Test registry and reference creation"""
    registry = {rpc_base._gui_id: rpc_base}
    ref = RPCReference(registry, rpc_base._gui_id)

    assert ref._gui_id == rpc_base._gui_id
    assert ref.widget_name == rpc_base.widget_name
    assert ref.__str__() == rpc_base.__str__()
    assert ref.__repr__() == rpc_base.__repr__()

    # Remove object from registry
    registry.pop(rpc_base._gui_id)

    assert ref.__str__() == f"<Deleted widget with gui_id {rpc_base._gui_id}>"
    assert ref.__repr__() == f"<Deleted widget with gui_id {rpc_base._gui_id}>"

    with pytest.raises(DeletedWidgetError):
        ref.widget_name  # Object no longer referenced in registry


def test_rpc_reference_property(rpc_waveform):
    """Test registry and reference creation"""
    waveform = rpc_waveform
    registry = {rpc_waveform._gui_id: rpc_waveform}
    ref = RPCReference(registry, rpc_waveform._gui_id)

    with mock.patch.object(waveform, "_run_rpc") as mock_run_rpc:
        with mock.patch.object(waveform._root, "_gui_is_alive", return_value=True):
            # Call property
            ref.enable_fps_monitor = True
            assert mock_run_rpc.call_count == 1
            assert mock_run_rpc.call_args == mock.call("enable_fps_monitor", True)
            # Call method
            ref.set(title="test_title")
            assert mock_run_rpc.call_count == 2
            assert mock_run_rpc.call_args == mock.call("set", title="test_title")
