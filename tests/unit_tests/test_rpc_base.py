import pytest

from bec_widgets.cli.rpc.rpc_base import DeletedWidgetError, RPCBase, RPCReference


@pytest.fixture
def rpc_base():
    yield RPCBase(gui_id="rpc_base_test", object_name="test")


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
