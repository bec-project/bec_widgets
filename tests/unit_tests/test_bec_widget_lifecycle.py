# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import shiboken6
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QEvent, QObject
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.rpc_register import RPCRegister

from .client_mocks import mocked_client


class LifecycleWidget(BECWidget, QWidget):
    def __init__(self, parent=None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.cleanup_calls = 0

    def on_message(self, msg_content, metadata):
        pass

    def cleanup(self):
        self.cleanup_calls += 1
        super().cleanup()


def _flush_deferred_deletes(qtbot):
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def test_close_runs_cleanup_once(qtbot, mocked_client):
    widget = LifecycleWidget(client=mocked_client)
    gui_id = widget.gui_id
    assert RPCRegister().get_rpc_by_id(gui_id) is widget

    widget.close()
    assert widget.cleanup_calls == 1
    assert widget._destroyed is True
    assert RPCRegister().get_rpc_by_id(gui_id) is None

    # a second close must not re-run cleanup
    widget.close()
    assert widget.cleanup_calls == 1

    widget.deleteLater()
    _flush_deferred_deletes(qtbot)


def test_delete_later_without_close_runs_cleanup(qtbot, mocked_client):
    widget = LifecycleWidget(client=mocked_client)
    gui_id = widget.gui_id
    assert RPCRegister().get_rpc_by_id(gui_id) is widget

    # destruction path that never delivers a close event
    widget.deleteLater()
    _flush_deferred_deletes(qtbot)

    assert widget.cleanup_calls == 1
    assert RPCRegister().get_rpc_by_id(gui_id) is None


def test_close_then_delete_later_runs_cleanup_once(qtbot, mocked_client):
    widget = LifecycleWidget(client=mocked_client)

    widget.close()
    widget.deleteLater()
    _flush_deferred_deletes(qtbot)

    assert widget.cleanup_calls == 1


def test_parent_destruction_removes_registry_entry(qtbot, mocked_client):
    # A BECWidget embedded in a plain (non-BECWidget) parent: destroying the parent
    # delivers neither a close event nor a DeferredDelete event to the child, so
    # cleanup() cannot run — the destroyed-signal hook must still remove the child
    # from the RPC registry by gui_id.
    parent = QWidget()
    layout = QVBoxLayout(parent)
    child = LifecycleWidget(parent=parent, client=mocked_client)
    layout.addWidget(child)
    gui_id = child.gui_id
    assert RPCRegister().get_rpc_by_id(gui_id) is child

    cleanup_calls_seen = []
    child.destroyed.connect(lambda *_: cleanup_calls_seen.append(child.cleanup_calls))

    parent.deleteLater()
    _flush_deferred_deletes(qtbot)

    # cleanup itself could not run on this path (documented limitation) ...
    assert cleanup_calls_seen == [0]
    # ... but the registry entry is gone
    assert RPCRegister().get_rpc_by_id(gui_id) is None


def test_delete_later_without_close_releases_dispatcher_subscriptions(
    qtbot, mocked_client, bec_dispatcher
):
    # End-to-end: the DeferredDelete hook runs cleanup(), which releases the widget's
    # dispatcher subscriptions via disconnect_owner — no close(), no manual disconnect,
    # no message traffic needed.
    widget = LifecycleWidget(client=mocked_client)
    bec_dispatcher.connect_slot(widget.on_message, MessageEndpoints.scan_status())
    slots_before = len(bec_dispatcher._registered_slots)

    widget.deleteLater()
    _flush_deferred_deletes(qtbot)

    assert widget.cleanup_calls == 1
    assert len(bec_dispatcher._registered_slots) == slots_before - 1


def test_lambda_without_owner_warns_and_stays(qtbot, mocked_client, bec_dispatcher):
    # A lambda has no trackable owner: connect_slot must warn loudly, and the
    # subscription stays alive (working) until disconnect_slot is called.
    from unittest import mock

    from bec_widgets.utils import bec_dispatcher as bd_module

    received = []
    cb = lambda content, metadata: received.append(content)  # noqa: E731
    with mock.patch.object(bd_module, "logger") as mock_logger:
        bec_dispatcher.connect_slot(cb, MessageEndpoints.scan_status())
    slots_before = len(bec_dispatcher._registered_slots)

    assert any(
        "cannot be released automatically" in str(call.args[0])
        for call in mock_logger.warning.call_args_list
    )

    # not reaped by the sweep: nothing marks it dead
    bec_dispatcher.cleanup_dead_slots()
    assert len(bec_dispatcher._registered_slots) == slots_before

    bec_dispatcher.disconnect_slot(cb, MessageEndpoints.scan_status())
    assert len(bec_dispatcher._registered_slots) == slots_before - 1


def test_lambda_with_owner_released_with_widget(qtbot, mocked_client, bec_dispatcher):
    # owner= binds a lambda's lifetime to a widget: cleanup of the widget releases it.
    widget = LifecycleWidget(client=mocked_client)
    received = []
    bec_dispatcher.connect_slot(
        lambda content, metadata: received.append(content),
        MessageEndpoints.scan_status(),
        owner=widget,
    )
    slots_before = len(bec_dispatcher._registered_slots)

    widget.close()
    assert len(bec_dispatcher._registered_slots) == slots_before - 1

    widget.deleteLater()
    _flush_deferred_deletes(qtbot)


def test_dead_slot_sweep_reaps_garbage_collected_owners(qtbot, mocked_client, bec_dispatcher):
    # An owner that is garbage collected (never closed, never deleted via Qt) leaves a
    # wrapper whose weak callback ref is dead; cleanup_dead_slots must reap it without
    # waiting for the next message on the topic.
    import gc

    class PlainOwner:
        def on_message(self, msg_content, metadata):
            pass

    owner = PlainOwner()
    bec_dispatcher.connect_slot(owner.on_message, MessageEndpoints.scan_status())
    slots_before = len(bec_dispatcher._registered_slots)

    del owner
    gc.collect()

    bec_dispatcher.cleanup_dead_slots()
    assert len(bec_dispatcher._registered_slots) == slots_before - 1


def test_destroyed_hook_survives_registry_failure(qtbot, mocked_client, bec_dispatcher):
    # During late application shutdown the registry broadcast can fail (the client and
    # its connector may already be shut down). The destroyed hook runs in destructor
    # context and must never raise: it logs, still purges the registry entry (popped
    # before the broadcast), and still runs the dispatcher sweep.
    from unittest import mock

    from bec_widgets.utils import bec_widget as bw_module

    parent = QWidget()
    layout = QVBoxLayout(parent)
    child = LifecycleWidget(parent=parent, client=mocked_client)
    layout.addWidget(child)
    gui_id = child.gui_id
    bec_dispatcher.connect_slot(child.on_message, MessageEndpoints.scan_status())
    slots_before = len(bec_dispatcher._registered_slots)

    with (
        mock.patch.object(RPCRegister, "broadcast", side_effect=RuntimeError("client gone")),
        mock.patch.object(bw_module, "logger") as mock_logger,
    ):
        parent.deleteLater()
        _flush_deferred_deletes(qtbot)

    assert any(
        "Registry purge for destroyed widget" in str(call.args[0])
        for call in mock_logger.warning.call_args_list
    )
    assert RPCRegister().get_rpc_by_id(gui_id) is None
    assert len(bec_dispatcher._registered_slots) == slots_before - 1


def test_parent_destruction_purges_dead_dispatcher_slots(qtbot, mocked_client, bec_dispatcher):
    parent = QWidget()
    layout = QVBoxLayout(parent)
    child = LifecycleWidget(parent=parent, client=mocked_client)
    layout.addWidget(child)

    bec_dispatcher.connect_slot(child.on_message, MessageEndpoints.scan_status())
    assert any(
        getattr(slot.cb, "__self__", None) is child
        for slot in bec_dispatcher._registered_slots.values()
    )
    slots_before = len(bec_dispatcher._registered_slots)

    parent.deleteLater()
    _flush_deferred_deletes(qtbot)

    # the destroyed hook purged the redis subscription of the dead receiver ...
    assert len(bec_dispatcher._registered_slots) == slots_before - 1
    # ... and every remaining slot has a live (or non-Qt) owner
    for slot in bec_dispatcher._registered_slots.values():
        owner = getattr(slot.cb, "__self__", None)
        assert not isinstance(owner, QObject) or shiboken6.isValid(owner)
