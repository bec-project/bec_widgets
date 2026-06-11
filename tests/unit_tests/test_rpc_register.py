from bec_widgets.utils.rpc_register import RPCRegister


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


class _CallbackOwner:
    """Owner of a bound-method registry callback for lifecycle tests."""

    def __init__(self):
        self.received = []

    def on_update(self, connections):
        self.received.append(dict(connections))


def test_register_callback_receives_broadcast(rpc_register):
    owner = _CallbackOwner()
    rpc_register.add_callback(owner.on_update)

    rpc_register.broadcast()
    assert len(owner.received) == 1


def test_duplicate_callback_registration_is_deduplicated(rpc_register):
    """Regression test for BW-009: registering the same bound method twice
    must deliver each broadcast exactly once."""
    owner = _CallbackOwner()
    callbacks_before = len(rpc_register.callbacks)

    rpc_register.add_callback(owner.on_update)
    rpc_register.add_callback(owner.on_update)
    assert len(rpc_register.callbacks) == callbacks_before + 1

    rpc_register.broadcast()
    assert len(owner.received) == 1


def test_remove_callback_is_idempotent(rpc_register):
    owner = _CallbackOwner()
    callbacks_before = len(rpc_register.callbacks)

    rpc_register.add_callback(owner.on_update)
    rpc_register.remove_callback(owner.on_update)
    assert len(rpc_register.callbacks) == callbacks_before

    # Repeated removal and removing an unknown callback are no-ops.
    rpc_register.remove_callback(owner.on_update)
    rpc_register.remove_callback(_CallbackOwner().on_update)
    assert len(rpc_register.callbacks) == callbacks_before

    rpc_register.broadcast()
    assert owner.received == []


def test_bound_method_identity_across_method_objects(rpc_register):
    """Two bound-method objects for the same method of the same instance must
    be treated as the same callback (remove works with a fresh method object)."""
    owner = _CallbackOwner()
    rpc_register.add_callback(owner.on_update)
    # 'owner.on_update' here creates a *new* bound-method object.
    rpc_register.remove_callback(owner.on_update)

    rpc_register.broadcast()
    assert owner.received == []


def test_callback_does_not_keep_owner_alive(rpc_register):
    """Regression test for BW-009: the register must not keep callback owners
    alive, and dead callbacks must be pruned on the next broadcast."""
    import gc
    import weakref

    owner = _CallbackOwner()
    rpc_register.add_callback(owner.on_update)
    ref = weakref.ref(owner)
    callbacks_with_owner = len(rpc_register.callbacks)

    del owner
    gc.collect()
    assert ref() is None, "register must not hold a strong reference to the owner"

    rpc_register.broadcast()  # must not raise; prunes the dead reference
    assert len(rpc_register.callbacks) == callbacks_with_owner - 1
