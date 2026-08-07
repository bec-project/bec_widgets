"""Tests for the QtDataSubscription bridge."""

from unittest import mock

import pytest
from bec_lib.data_api.models import SubscriptionUpdate

from bec_widgets.utils.qt_data_subscription import QtDataSubscription

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring


@pytest.fixture
def fake_api(monkeypatch):
    subscription = mock.MagicMock()
    subscription.scan_id = "scan_1"
    subscription.unbound_sources = []
    subscription.sources = [("samx", "samx")]
    api = mock.MagicMock()
    api.subscribe.return_value = subscription
    monkeypatch.setattr("bec_widgets.utils.qt_data_subscription.DataAPI", lambda client: api)
    return api, subscription


def make_update(scan_id="scan_1"):
    return SubscriptionUpdate(
        scan_id=scan_id, reason="live", sources={}, aligned_ordinals=(), complete=True
    )


def test_updates_are_marshalled_to_qt_thread(qtbot, fake_api):
    api, subscription = fake_api
    bridge = QtDataSubscription(mock.MagicMock(), sources=[("samx", "samx")])
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
    bridge = QtDataSubscription(mock.MagicMock(), sources=[("samx", "samx")])
    received = []
    bridge.updated.connect(received.append)
    callback = api.subscribe.call_args.kwargs["callback"]

    subscription.scan_id = "scan_2"
    callback(make_update("scan_1"))  # stale
    callback(make_update("scan_2"))  # current
    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert [u.scan_id for u in received] == ["scan_2"]
    bridge.close()


def test_health_and_source_delegation(fake_api):
    api, subscription = fake_api
    bridge = QtDataSubscription(mock.MagicMock(), sources=[("samx", "samx")])
    assert bridge.healthy
    subscription.unbound_sources = [("samx", "samx")]
    assert not bridge.healthy
    bridge.set_sources([("samy", "samy")])
    subscription.set_sources.assert_called_once_with([("samy", "samy")])
    assert bridge.scan_id == "scan_1"
    bridge.close()
    bridge.close()  # idempotent
    assert subscription.close.call_count == 1


def test_synchronous_initial_delivery_is_queued(qtbot, monkeypatch):
    """The backend delivers the initial backfill synchronously inside
    subscribe() on the Qt thread; the bridge must neither crash on its
    not-yet-assigned subscription nor lose that first snapshot."""
    subscription = mock.MagicMock()
    subscription.scan_id = "scan_1"

    api = mock.MagicMock()

    def synchronous_subscribe(sources, scan, callback, **kwargs):
        callback(make_update("scan_1"))
        return subscription

    api.subscribe.side_effect = synchronous_subscribe
    monkeypatch.setattr("bec_widgets.utils.qt_data_subscription.DataAPI", lambda client: api)

    bridge = QtDataSubscription(mock.MagicMock(), sources=[("samx", "samx")])
    received = []
    # Widgets connect AFTER the constructor returns — the queued initial
    # emission must still reach them.
    bridge.updated.connect(received.append)

    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert received[0].scan_id == "scan_1"
    bridge.close()
