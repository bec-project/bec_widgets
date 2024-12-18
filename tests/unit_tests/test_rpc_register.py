from bec_widgets.cli.rpc.rpc_register import RPCRegister


class FakeObject:
    def __init__(self, gui_id):
        self.gui_id = gui_id


def test_add_connection(rpc_register):
    obj1 = FakeObject("id1")
    obj2 = FakeObject("id2")

    rpc_register.add_rpc(obj1)
    rpc_register.add_rpc(obj2)

    all_connections = rpc_register.list_all_connections()

    assert len(all_connections) == 2
    assert all_connections["id1"] == obj1
    assert all_connections["id2"] == obj2


def test_remove_connection(rpc_register):

    obj1 = FakeObject("id1")
    obj2 = FakeObject("id2")

    rpc_register.add_rpc(obj1)
    rpc_register.add_rpc(obj2)

    rpc_register.remove_rpc(obj1)

    all_connections = rpc_register.list_all_connections()

    assert len(all_connections) == 1
    assert all_connections["id2"] == obj2


def test_reset_singleton(rpc_register):
    obj1 = FakeObject("id1")
    obj2 = FakeObject("id2")

    rpc_register.add_rpc(obj1)
    rpc_register.add_rpc(obj2)

    rpc_register.reset_singleton()
    rpc_register = RPCRegister()

    all_connections = rpc_register.list_all_connections()

    assert len(all_connections) == 0
    assert all_connections == {}
