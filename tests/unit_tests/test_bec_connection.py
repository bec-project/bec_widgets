# pylint: skip-file
"""Running without Redis: kept subscriptions, the connection state, reconnect and its display."""

from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtWidgets import QWidget

from bec_widgets.tests.utils import create_widget
from bec_widgets.utils.bec_connection import ConnectionState, redis_reachable
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.containers.main_window.addons.server_status_item import server_indicator
from bec_widgets.widgets.containers.main_window.addons.status_pill import (
    ToolSeverity,
    indicator_icon,
)
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.services.bec_status_box.status_model import ServiceStatusModel


class Receiver:
    def on_message(self, content, metadata): ...


class ShortcutWidget(BECWidget, QWidget):
    pass


def _slot_of(dispatcher, callback):
    return next(slot for slot in dispatcher._registered_slots.values() if slot.cb == callback)


@pytest.fixture
def offline(bec_dispatcher):
    """The dispatcher as after a start without Redis."""
    bec_dispatcher.connection._set_state(ConnectionState.OFFLINE)
    yield bec_dispatcher


def test_subscriptions_are_kept_while_offline_and_made_on_reconnect(offline):
    receiver = Receiver()
    connector = offline.client.connector
    with mock.patch.object(connector, "register") as register:
        offline.connect_slot(
            receiver.on_message, [MessageEndpoints.scan_status(), MessageEndpoints.alarm()]
        )
        register.assert_not_called()
    qt_slot = _slot_of(offline, receiver.on_message)
    assert len(qt_slot.pending) == 2

    offline.connection._set_state(ConnectionState.CONNECTED)
    with (
        mock.patch.object(connector, "register") as register,
        mock.patch.object(offline, "start_cli_server"),
    ):
        offline.on_client_connected()
    calls = [call for call in register.call_args_list if call.kwargs["cb"] is qt_slot]
    assert {call.args[0] for call in calls} == {
        MessageEndpoints.scan_status(),
        MessageEndpoints.alarm(),
    }
    assert qt_slot.pending == []


def test_subscription_released_offline_is_not_made_on_reconnect(offline):
    receiver = Receiver()
    connector = offline.client.connector
    offline.connect_slot(
        receiver.on_message, [MessageEndpoints.scan_status(), MessageEndpoints.alarm()]
    )
    with mock.patch.object(connector, "unregister") as unregister:
        offline.disconnect_slot(receiver.on_message, MessageEndpoints.alarm())
        unregister.assert_not_called()  # nothing to undo without Redis

    qt_slot = _slot_of(offline, receiver.on_message)
    offline.connection._set_state(ConnectionState.CONNECTED)
    with (
        mock.patch.object(connector, "register") as register,
        mock.patch.object(offline, "start_cli_server"),
    ):
        offline.on_client_connected()
    calls = [call for call in register.call_args_list if call.kwargs["cb"] is qt_slot]
    assert [call.args[0] for call in calls] == [MessageEndpoints.scan_status()]


def test_reconnect_starts_the_client_and_subscribes(offline, qtbot):
    client = offline.client
    client.started = False

    def start():
        client.started = True

    with (
        mock.patch.object(client, "start", side_effect=start),
        mock.patch.object(offline, "on_client_connected") as connected,
    ):
        with qtbot.waitSignal(offline.connection.reconnected, timeout=5000):
            offline.connection.reconnect()
        connected.assert_called_once()
    assert offline.connection.state == ConnectionState.CONNECTED
    assert offline.connected


def test_failed_reconnect_stays_offline_with_a_reason(offline, qtbot):
    client = offline.client
    client.started = False
    with mock.patch.object(client, "start"):
        with qtbot.waitSignal(offline.connection.state_changed, timeout=5000) as blocker:
            offline.connection.reconnect()
        qtbot.waitUntil(lambda: offline.connection.state == ConnectionState.OFFLINE)
    assert "Still no answer" in offline.connection.error
    client.started = True


@pytest.mark.parametrize(
    "state, reachable, expected",
    [
        (ConnectionState.CONNECTED, False, ConnectionState.LOST),
        (ConnectionState.LOST, True, ConnectionState.CONNECTED),
        (ConnectionState.OFFLINE, True, ConnectionState.AVAILABLE),
        (ConnectionState.AVAILABLE, False, ConnectionState.OFFLINE),
        (ConnectionState.CONNECTED, True, ConnectionState.CONNECTED),
        (ConnectionState.OFFLINE, False, ConnectionState.OFFLINE),
        (ConnectionState.CONNECTING, True, ConnectionState.CONNECTING),
    ],
)
def test_reachability_moves_the_state(bec_dispatcher, state, reachable, expected):
    connection = bec_dispatcher.connection
    connection._set_state(state)
    connection.set_reachable(reachable)
    assert connection.state == expected


def test_redis_reachable(bec_dispatcher):
    # the test client runs on fakeredis, which always answers
    assert redis_reachable(bec_dispatcher.client)
    assert not redis_reachable(mock.MagicMock(connector=None))


def test_shortcuts_are_empty_offline_and_filled_on_reconnect(qtbot, offline):
    widget = create_widget(qtbot, ShortcutWidget)
    client = offline.client
    with (
        mock.patch.object(client, "device_manager", None),
        mock.patch.object(client, "queue", None),
    ):
        widget.get_bec_shortcuts()
        assert len(widget.dev) == 0
        assert widget.scan_storage is None
    offline.connection._set_state(ConnectionState.CONNECTED)
    with mock.patch.object(offline, "start_cli_server"):
        offline.on_client_connected()
    assert widget.dev is client.device_manager.devices


@pytest.mark.parametrize(
    "state, headline, severity",
    [
        (ConnectionState.OFFLINE, "Not connected to BEC", ToolSeverity.WARNING),
        (ConnectionState.AVAILABLE, "BEC is reachable again", ToolSeverity.INFO),
        (ConnectionState.CONNECTING, "Connecting to BEC", ToolSeverity.INFO),
        (ConnectionState.LOST, "Connection to BEC lost", ToolSeverity.CRITICAL),
    ],
)
def test_model_and_pill_show_the_connection(state, headline, severity):
    model = ServiceStatusModel()
    model.set_connection(state, "localhost:6379")
    assert model.headline == headline
    assert model.severity == severity
    assert model.rows == []
    assert not model.can_restart
    assert model.can_reconnect == (state in (ConnectionState.OFFLINE, ConnectionState.AVAILABLE))
    indicator = server_indicator(model)
    assert indicator.summary == headline
    if state == ConnectionState.CONNECTING:
        assert indicator.active
    else:
        assert indicator.badge == "offline"
        assert indicator_icon(indicator)[0] in ("cloud_off", "cloud_sync")


def test_status_box_reconnect_button(qtbot, offline):
    box = create_widget(qtbot, BECStatusBox, bec_service_status_mixin=mock.MagicMock())
    header = box.view.header
    assert box.model.connection == ConnectionState.OFFLINE
    assert not header.reconnect_button.isHidden()
    assert header.restart_button.isHidden()
    assert not box.view.offline_label.isHidden()
    assert box.get_server_state() == "NOTCONNECTED"
    with mock.patch.object(offline.connection, "reconnect") as reconnect:
        # the box connected the bound method before the patch; call through the model
        box.model.reconnect_requested.disconnect()
        box.model.reconnect_requested.connect(reconnect)
        header.reconnect_button.click()
        reconnect.assert_called_once()

    offline.connection._set_state(ConnectionState.CONNECTED)
    assert header.reconnect_button.isHidden()
    assert not header.restart_button.isHidden()
    assert box.view.offline_label.isHidden()


def test_lost_connection_says_it_comes_back_by_itself(qtbot, bec_dispatcher):
    box = create_widget(qtbot, BECStatusBox, bec_service_status_mixin=mock.MagicMock())
    bec_dispatcher.connection._set_state(ConnectionState.LOST)
    assert box.view.header.reconnect_button.isHidden()
    assert "by itself" in box.view.offline_label.text()
