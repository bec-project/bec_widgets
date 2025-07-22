from unittest.mock import MagicMock

import pytest
from bec_lib.device import DeviceBaseWithConfig, Signal

from bec_widgets.cli.rpc.rpc_base import (
    DeletedWidgetError,
    RPCBase,
    RPCReference,
    _transform_args_kwargs,
)


@pytest.fixture
def rpc_base():
    yield RPCBase(gui_id="rpc_base_test", object_name="test")


def test_rpc_base(rpc_base):
    """Test registry and reference creation"""
    registry = {rpc_base._gui_id: rpc_base}
    ref = RPCReference(registry, rpc_base._gui_id)

    assert ref._gui_id == rpc_base._gui_id
    assert ref.object_name == rpc_base.object_name
    assert ref.__str__() == rpc_base.__str__()
    assert ref.__repr__() == rpc_base.__repr__()

    # Remove object from registry
    registry.pop(rpc_base._gui_id)

    assert ref.__str__() == f"<Deleted widget with gui_id {rpc_base._gui_id}>"
    assert ref.__repr__() == f"<Deleted widget with gui_id {rpc_base._gui_id}>"

    with pytest.raises(DeletedWidgetError):
        ref._root  # Object no longer referenced in registry


def test_transform_args_kwargs():
    device_mock = MagicMock(spec=DeviceBaseWithConfig)
    device_mock.full_name = "full name"
    fallthrough_device_mock = MagicMock()
    fallthrough_device_mock.name = "short name"
    string_arg = "string_arg"
    signal_mock = MagicMock(spec=Signal)
    signal_mock.full_name = "full name"

    args, kwargs = _transform_args_kwargs(
        (device_mock, fallthrough_device_mock, string_arg, signal_mock),
        {"a": device_mock, "b": fallthrough_device_mock, "c": string_arg, "d": signal_mock},
    )
    assert args == ("full name", "short name", "string_arg", "full name")
    assert kwargs == {"a": "full name", "b": "short name", "c": "string_arg", "d": "full name"}
