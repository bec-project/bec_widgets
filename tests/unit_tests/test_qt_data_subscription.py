"""Tests for the QtDataSubscription bridge."""

from unittest import mock

import pytest
from bec_lib.data_api import SCAN_GROUP, CorrelationGroup, UpdateReason
from bec_lib.data_api.models import SubscriptionUpdate

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


def make_update(scan_id="scan_1"):
    return SubscriptionUpdate(
        scan_id=scan_id, reason="live", sources={}, aligned_ordinals=(), complete=True
    )


def test_every_update_reason_has_a_rank():
    """A superseded update keeps the more important reason; none may be unknown."""
    assert set(QtDataSubscription._REASON_RANK) == set(UpdateReason)


def test_updates_are_marshalled_to_qt_thread(qtbot, fake_api):
    api, subscription = fake_api
    bridge = QtDataSubscription(mock.MagicMock(data_api=fake_api[0]), sources=[("samx", "samx")])
    received = []
    bridge.updated.connect(received.append)

    callback = api.subscribe.call_args.kwargs["callback"]
    update = make_update()
    callback(update)
    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert received[0] is update
    bridge.close()
    assert subscription.close.called


def test_stale_scan_payload_dropped(qtbot, fake_api):
    api, subscription = fake_api
    bridge = QtDataSubscription(mock.MagicMock(data_api=fake_api[0]), sources=[("samx", "samx")])
    received = []
    bridge.updated.connect(received.append)
    callback = api.subscribe.call_args.kwargs["callback"]

    subscription.scan_id = "scan_2"
    callback(make_update("scan_1"))  # stale
    callback(make_update("scan_2"))  # current
    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert [u.scan_id for u in received] == ["scan_2"]
    bridge.close()


def test_payload_queued_before_same_scan_rebind_is_dropped(qtbot, fake_api):
    from dataclasses import replace

    api, subscription = fake_api
    bridge = QtDataSubscription(mock.MagicMock(data_api=fake_api[0]), devices=["samx"])
    received = []
    bridge.updated.connect(received.append)
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
    bridge = QtDataSubscription(mock.MagicMock(data_api=fake_api[0]), sources=[("samx", "samx")])
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
    api, subscription = fake_api
    bridge = QtDataSubscription(
        mock.MagicMock(data_api=fake_api[0]),
        sources=[("samx", "samx")],
        scan="scan_1",
        size_limit_bytes=1024,
    )
    assert api.subscribe.call_args.kwargs["size_limit_bytes"] == 1024
    bridge.close()


def test_routing_options_are_forwarded_to_the_backend(fake_api):
    api, _ = fake_api
    bridge = QtDataSubscription(
        mock.MagicMock(data_api=fake_api[0]),
        devices=["samx", "samy"],
        scan=None,
        correlation="continuous",
        force_source="redis",
    )
    kwargs = api.subscribe.call_args.kwargs
    assert kwargs["sources"] is None and kwargs["devices"] == ["samx", "samy"]
    assert kwargs["correlation"] == "continuous" and kwargs["force_source"] == "redis"
    bridge.close()
    bridge = QtDataSubscription(mock.MagicMock(data_api=fake_api[0]), sources=[("samx", "samx")])
    kwargs = api.subscribe.call_args.kwargs
    assert kwargs["devices"] is None and kwargs["correlation"] == "ordinal"
    assert kwargs["force_source"] is None
    bridge.close()


def test_size_limit_defaults_to_none(fake_api):
    api, _ = fake_api
    bridge = QtDataSubscription(mock.MagicMock(data_api=fake_api[0]), sources=[("samx", "samx")])
    assert api.subscribe.call_args.kwargs["size_limit_bytes"] is None
    bridge.close()


def test_size_gate_properties_and_confirm(fake_api):
    _, subscription = fake_api
    subscription.size_gated = True
    subscription.estimated_bytes = 4096
    bridge = QtDataSubscription(
        mock.MagicMock(data_api=fake_api[0]),
        sources=[("samx", "samx")],
        scan="scan_1",
        size_limit_bytes=1024,
    )

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

    bridge = QtDataSubscription(mock.MagicMock(data_api=api), sources=[("samx", "samx")])
    received = []
    # Widgets connect AFTER the constructor returns — the queued initial
    # emission must still reach them.
    bridge.updated.connect(received.append)

    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert received[0].scan_id == "scan_1"
    bridge.close()


def test_client_owns_the_bridge_api(qtbot, bec_dispatcher):
    client = bec_dispatcher.client
    bridge = QtDataSubscription(client, devices=["samx"], scan=None, max_points=1)
    assert bridge._api is client.data_api
    assert client._data_api is bridge._api
    client.shutdown()
    assert bridge._api.closed
    bridge.close()


def test_queued_updates_and_progress_are_discarded_after_api_shutdown(qtbot, fake_api):
    api, _ = fake_api
    bridge = QtDataSubscription(mock.MagicMock(data_api=api), devices=["samx"])
    received, progress = [], []
    bridge.updated.connect(received.append)
    bridge.progress.connect(progress.append)
    callbacks = api.subscribe.call_args.kwargs
    callbacks["callback"](make_update())
    callbacks["progress_callback"](0.5)
    api.closed = True
    qtbot.wait(10)
    assert received == []
    assert progress == []
    bridge.close()


def test_queued_updates_collapse_to_the_latest_per_group(qtbot, fake_api):
    """A busy Qt thread receives the newest snapshot, not a backlog; a superseded
    transition reason ("rebind") is kept."""
    api, _ = fake_api
    bridge = QtDataSubscription(mock.MagicMock(data_api=api), sources=[("samx", "samx")])
    received = []
    bridge.updated.connect(received.append)
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
