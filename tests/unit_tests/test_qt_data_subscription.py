"""Tests for the QtDataSubscription bridge."""

import gc
import threading
import weakref
from dataclasses import replace
from unittest import mock

import pytest
import shiboken6
from bec_lib.data_api import SCAN_GROUP, CorrelationGroup, UpdateReason
from bec_lib.data_api.models import SubscriptionUpdate
from qtpy.QtCore import QObject

from bec_widgets.utils.qt_data_subscription import QtDataSubscription

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring


@pytest.fixture
def fake_api():
    subscription = mock.MagicMock()
    subscription.scan_id = "scan_1"
    subscription.generation = 0
    subscription.unbound_sources = []
    subscription.sources = [("samx", "samx")]
    api = mock.MagicMock(closed=False)
    api.subscribe.return_value = subscription
    return api, subscription


def collecting(api, **options):
    """A subscription with the updates and progress values its slots were called with."""
    received, progress = [], []
    bridge = QtDataSubscription(
        mock.MagicMock(data_api=api),
        lambda update: received.append(update),
        progress_slot=lambda fraction: progress.append(fraction),
        **options,
    )
    return bridge, received, progress


def make_update(scan_id="scan_1"):
    return SubscriptionUpdate(
        scan_id=scan_id, reason="live", sources={}, aligned_ordinals=(), complete=True
    )


def test_every_update_reason_has_a_rank():
    """A superseded update keeps the more important reason; none may be unknown."""
    assert set(QtDataSubscription._REASON_RANK) == set(UpdateReason)


def test_updates_are_marshalled_to_qt_thread(qtbot, fake_api):
    api, subscription = fake_api
    bridge, received, _ = collecting(api, sources=[("samx", "samx")])

    callback = api.subscribe.call_args.kwargs["callback"]
    update = make_update()
    callback(update)
    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert received[0] is update
    bridge.close()
    assert subscription.close.called


def test_stale_scan_payload_dropped(qtbot, fake_api):
    api, subscription = fake_api
    bridge, received, _ = collecting(api, sources=[("samx", "samx")])
    callback = api.subscribe.call_args.kwargs["callback"]

    subscription.scan_id = "scan_2"
    callback(make_update("scan_1"))  # stale
    callback(make_update("scan_2"))  # current
    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert [u.scan_id for u in received] == ["scan_2"]
    bridge.close()


def test_payload_queued_before_same_scan_rebind_is_dropped(qtbot, fake_api):
    api, subscription = fake_api
    bridge, received, _ = collecting(api, devices=["samx"])
    callback = api.subscribe.call_args.kwargs["callback"]
    callback(make_update())
    subscription.generation = 1
    current = replace(make_update(), generation=1)
    callback(current)
    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert received == [current]
    bridge.close()


def test_health_and_source_delegation(fake_api):
    api, subscription = fake_api
    bridge, _, _ = collecting(api, sources=[("samx", "samx")])
    assert bridge.healthy
    subscription.unbound_sources = [("samx", "samx")]
    assert not bridge.healthy
    bridge.set_sources([("samy", "samy")])
    subscription.set_sources.assert_called_once_with([("samy", "samy")])
    assert bridge.scan_id == "scan_1"
    bridge.close()
    bridge.close()  # idempotent
    assert subscription.close.call_count == 1


def test_size_limit_is_forwarded_to_the_backend(fake_api):
    api, _ = fake_api
    bridge, _, _ = collecting(api, sources=[("samx", "samx")], scan="scan_1", size_limit_bytes=1024)
    assert api.subscribe.call_args.kwargs["size_limit_bytes"] == 1024
    bridge.close()


def test_routing_options_are_forwarded_to_the_backend(fake_api):
    api, _ = fake_api
    bridge, _, _ = collecting(
        api, devices=["samx", "samy"], scan=None, pair_sources=True, force_source="redis"
    )
    kwargs = api.subscribe.call_args.kwargs
    assert kwargs["sources"] is None and kwargs["devices"] == ["samx", "samy"]
    assert kwargs["pair_sources"] is True and kwargs["force_source"] == "redis"
    bridge.close()
    bridge, _, _ = collecting(api, sources=[("samx", "samx")])
    kwargs = api.subscribe.call_args.kwargs
    assert kwargs["devices"] is None and kwargs["pair_sources"] is False
    assert kwargs["force_source"] is None
    bridge.close()


def test_size_limit_defaults_to_none(fake_api):
    api, _ = fake_api
    bridge, _, _ = collecting(api, sources=[("samx", "samx")])
    assert api.subscribe.call_args.kwargs["size_limit_bytes"] is None
    bridge.close()


def test_size_gate_properties_and_confirm(fake_api):
    api, subscription = fake_api
    subscription.size_gated = True
    subscription.estimated_bytes = 4096
    bridge, _, _ = collecting(api, sources=[("samx", "samx")], scan="scan_1", size_limit_bytes=1024)

    assert bridge.size_gated is True
    assert bridge.estimated_bytes == 4096

    bridge.confirm_size()
    subscription.confirm_size.assert_called_once_with()

    subscription.size_gated = False
    assert bridge.size_gated is False
    bridge.close()


def test_synchronous_initial_delivery_is_queued(qtbot):
    """The backend delivers the initial backfill synchronously inside
    subscribe() on the Qt thread; the bridge must neither crash on its
    not-yet-assigned subscription nor lose that first snapshot."""
    subscription = mock.MagicMock()
    subscription.scan_id = "scan_1"
    subscription.generation = 0

    api = mock.MagicMock(closed=False)

    def synchronous_subscribe(sources, scan, callback, **kwargs):
        callback(make_update("scan_1"))
        return subscription

    api.subscribe.side_effect = synchronous_subscribe

    bridge, received, _ = collecting(api, sources=[("samx", "samx")])
    assert received == []  # not from inside the constructor

    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert received[0].scan_id == "scan_1"
    bridge.close()


def test_client_owns_the_bridge_api(qtbot, bec_dispatcher):
    client = bec_dispatcher.client
    bridge = QtDataSubscription(client, lambda update: None, devices=["samx"], scan=None)
    assert bridge._api is client.data_api
    assert client._data_api is bridge._api
    client.shutdown()
    assert bridge._api.closed
    bridge.close()


def test_queued_updates_and_progress_are_discarded_after_api_shutdown(qtbot, fake_api):
    api, _ = fake_api
    bridge, received, progress = collecting(api, devices=["samx"])
    callbacks = api.subscribe.call_args.kwargs
    callbacks["callback"](make_update())
    callbacks["progress_callback"](0.5)
    api.closed = True
    qtbot.wait(10)
    assert received == []
    assert progress == []
    bridge.close()


def test_progress_reaches_its_slot(qtbot, fake_api):
    api, _ = fake_api
    bridge, _, progress = collecting(api, devices=["samx"])
    api.subscribe.call_args.kwargs["progress_callback"](0.5)
    qtbot.waitUntil(lambda: progress == [0.5], timeout=2000)
    bridge.close()


def test_queued_updates_collapse_to_the_latest_per_group(qtbot, fake_api):
    """A busy Qt thread receives the newest snapshot, not a backlog; a superseded
    transition reason ("rebind") is kept."""
    api, _ = fake_api
    bridge, received, _ = collecting(api, sources=[("samx", "samx")])
    callback = api.subscribe.call_args.kwargs["callback"]

    def update(reason, value, group=SCAN_GROUP):
        return SubscriptionUpdate(
            scan_id="scan_1",
            reason=reason,
            sources={},
            aligned_ordinals=(),
            complete=True,
            metadata={"group": group, "value": value},
        )

    callback(update("rebind", 1))
    callback(update("live", 2))
    callback(update("live", 3))
    callback(update("live", 9, group=CorrelationGroup.multi("det", "frames")))
    qtbot.waitUntil(lambda: len(received) == 2, timeout=2000)
    qtbot.wait(50)
    by_group = {u.metadata["group"]: u for u in received}
    assert len(received) == 2
    assert by_group[SCAN_GROUP].metadata["value"] == 3 and by_group[SCAN_GROUP].reason == "rebind"
    assert by_group[CorrelationGroup.multi("det", "frames")].metadata["value"] == 9
    bridge.close()


def test_closed_subscription_is_inactive_for_data_threads_and_queued_updates(qtbot, fake_api):
    """The safeguard of the Redis slots: after close nothing is queued and nothing delivered."""
    api, _ = fake_api
    bridge, received, progress = collecting(api, sources=[("samx", "samx")])
    callbacks = api.subscribe.call_args.kwargs
    callbacks["callback"](make_update())  # queued for the GUI thread
    bridge.close()
    assert bridge.closed
    callbacks["callback"](make_update())  # a data thread that is late
    callbacks["progress_callback"](0.5)
    qtbot.wait(50)
    assert received == [] and progress == []


# --- owned by the dispatcher ---------------------------------------------------------------


class Owner(QObject):
    """A widget as the dispatcher sees it: a Qt object with slots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.received = []
        self.progress = []

    def on_update(self, update):
        self.received.append(update)

    def on_progress(self, fraction):
        self.progress.append(fraction)


@pytest.fixture
def dispatcher(bec_dispatcher, fake_api):
    """The dispatcher with a DataAPI stand-in; yields it with the API's subscription mock."""
    api, subscription = fake_api
    bec_dispatcher.client._data_api = api
    yield bec_dispatcher, api, subscription
    bec_dispatcher.client._data_api = None


def connect(dispatcher, owner):
    """Connect ``owner`` through the dispatcher; returns the bridge and the data-thread callback."""
    bec_dispatcher, api, _ = dispatcher
    bridge = bec_dispatcher.connect_data_subscription(
        owner.on_update, sources=[("samx", "samx")], progress_slot=owner.on_progress
    )
    return bridge, api.subscribe.call_args.kwargs["callback"]


def test_connect_delivers_to_the_slot_and_disconnect_ends_it(qtbot, dispatcher):
    bec_dispatcher, api, subscription = dispatcher
    owner = Owner()
    bridge, callback = connect(dispatcher, owner)
    assert isinstance(bridge, QtDataSubscription) and bridge.parent() is None
    assert bec_dispatcher.data_subscriptions(owner) == [bridge]
    assert api.subscribe.call_args.kwargs["sources"] == [("samx", "samx")]

    callback(make_update())
    qtbot.waitUntil(lambda: len(owner.received) == 1, timeout=2000)

    bec_dispatcher.disconnect_data_subscription(bridge)
    subscription.close.assert_called_once()
    assert bec_dispatcher.data_subscriptions(owner) == []
    bec_dispatcher.disconnect_data_subscription(bridge)  # idempotent
    bec_dispatcher.disconnect_data_subscription(None)
    subscription.close.assert_called_once()


def test_the_dispatcher_never_keeps_the_owner_alive(dispatcher):
    owner = Owner()
    connect(dispatcher, owner)
    alive = weakref.ref(owner)
    del owner
    gc.collect()
    assert alive() is None


def test_disconnect_owner_closes_the_owners_subscriptions(dispatcher):
    """What BECWidget.cleanup calls; widgets need not disconnect at teardown."""
    bec_dispatcher, _, subscription = dispatcher
    owner, other = Owner(), Owner()
    connect(dispatcher, owner)
    kept, _ = connect(dispatcher, other)
    subscription.close.reset_mock()

    bec_dispatcher.disconnect_owner(owner)
    subscription.close.assert_called_once()
    assert bec_dispatcher._data_subscriptions == [kept]


def test_subscription_survives_the_destruction_of_its_owner_and_is_swept(qtbot, dispatcher):
    """The owner dies with its Qt parent, without any cleanup or close event."""
    bec_dispatcher, _, subscription = dispatcher
    parent = QObject()
    owner = Owner(parent)
    bridge, callback = connect(dispatcher, owner)
    received = owner.received
    shiboken6.delete(parent)

    assert shiboken6.isValid(bridge)  # the object data threads emit on is still there
    with qtbot.captureExceptions() as exceptions:
        callback(make_update())  # a data thread that still delivers
        qtbot.wait(50)
    assert exceptions == [] and received == []

    bec_dispatcher.cleanup_dead_slots()
    subscription.close.assert_called_once()
    assert bec_dispatcher._data_subscriptions == []


@pytest.mark.parametrize("death", ["qt object destroyed", "garbage collected"])
def test_dead_slot_sweep_closes_the_subscriptions_of_dead_owners(dispatcher, death):
    bec_dispatcher, _, subscription = dispatcher
    owner = Owner()
    connect(dispatcher, owner)
    if death == "qt object destroyed":
        shiboken6.delete(owner)
    else:
        del owner
        gc.collect()

    bec_dispatcher.cleanup_dead_slots()
    subscription.close.assert_called_once()
    assert bec_dispatcher._data_subscriptions == []


def test_update_queued_before_the_owner_died_is_not_delivered(qtbot, dispatcher):
    owner = Owner()
    _, callback = connect(dispatcher, owner)
    received = owner.received
    callback(make_update())  # queued for the GUI thread
    shiboken6.delete(owner)
    qtbot.wait(50)
    assert received == []


def test_widget_in_cleanup_gets_no_update(qtbot, dispatcher):
    owner = Owner()
    _, callback = connect(dispatcher, owner)
    owner._destroyed = True  # what BECWidget sets before its cleanup runs
    callback(make_update())
    qtbot.wait(50)
    assert owner.received == []


def test_slot_without_a_method_is_bound_to_its_owner(qtbot, dispatcher):
    """A lambda has no owner of its own; ``owner=`` ties it to a widget, as for connect_slot."""
    bec_dispatcher, api, subscription = dispatcher
    owner = Owner()
    received = []
    bec_dispatcher.connect_data_subscription(
        lambda update: received.append(update), sources=[("samx", "samx")], owner=owner
    )
    callback = api.subscribe.call_args.kwargs["callback"]
    callback(make_update())
    qtbot.waitUntil(lambda: len(received) == 1, timeout=2000)

    shiboken6.delete(owner)
    callback(make_update())
    qtbot.wait(50)
    assert len(received) == 1
    bec_dispatcher.cleanup_dead_slots()
    subscription.close.assert_called_once()


def test_disconnect_all_closes_every_subscription(dispatcher):
    bec_dispatcher, _, subscription = dispatcher
    owner = Owner()
    connect(dispatcher, owner)
    bec_dispatcher.disconnect_all()
    subscription.close.assert_called_once()
    assert bec_dispatcher._data_subscriptions == []


def test_data_thread_delivering_while_the_owner_is_destroyed(qtbot, dispatcher):
    """A data thread keeps delivering while the GUI thread destroys the owner."""
    bec_dispatcher, _, subscription = dispatcher
    owner = Owner()
    bridge, callback = connect(dispatcher, owner)
    stop = threading.Event()
    errors = []

    def deliver():
        while not stop.is_set():
            try:
                callback(make_update())
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(exc)

    thread = threading.Thread(target=deliver)
    thread.start()
    try:
        qtbot.wait(20)
        shiboken6.delete(owner)
        qtbot.wait(20)
        bec_dispatcher.cleanup_dead_slots()
    finally:
        stop.set()
        thread.join(2)
    assert not thread.is_alive() and errors == []
    subscription.close.assert_called_once()
    assert bridge.closed and bec_dispatcher._data_subscriptions == []
