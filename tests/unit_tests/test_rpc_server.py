import argparse
from unittest.mock import MagicMock, patch

import pytest
from bec_lib.service_config import ServiceConfig
from qtpy.QtWidgets import QWidget

from bec_widgets.applications import companion_app as companion_app_module
from bec_widgets.applications.companion_app import GUIServer
from bec_widgets.utils import rpc_server as rpc_server_module
from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.utils.rpc_server import RegistryNotReadyError, RPCServer, SingleshotRPCRepeat

from .client_mocks import mocked_client


class DummyWidget(BECConnector, QWidget):
    def __init__(self, parent=None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.setObjectName("DummyWidget")


@pytest.fixture
def dummy_widget(qtbot, mocked_client):
    widget = DummyWidget(client=mocked_client)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def gui_server():
    args = argparse.Namespace(
        config=None, id="gui_id", gui_class="LaunchWindow", gui_class_id="bec", hide=False
    )
    return GUIServer(args=args)


@pytest.fixture
def rpc_server(mocked_client):
    rpc_server = RPCServer(gui_id="test_gui", client=mocked_client)
    yield rpc_server
    rpc_server.shutdown()


def test_gui_server_start_server_without_service_config(gui_server):
    """
    Test that the server is started with the correct arguments.
    """
    assert gui_server.config is None
    assert gui_server.gui_id == "gui_id"
    assert gui_server.gui_class == "LaunchWindow"
    assert gui_server.gui_class_id == "bec"
    assert gui_server.hide is False


def test_gui_server_get_service_config(gui_server):
    """
    Test that the server is started with the correct arguments.
    """
    assert gui_server._get_service_config().config == ServiceConfig().config


def test_gui_server_signal_shutdown_closes_widgets_and_quits_app(gui_server):
    widget = MagicMock()
    gui_server.app = MagicMock()
    gui_server.app.topLevelWidgets.return_value = [widget]

    gui_server.request_shutdown()

    widget.close.assert_called_once()
    gui_server.app.quit.assert_called_once()


def test_gui_server_shutdown_is_idempotent(gui_server):
    gui_server.launcher_window = MagicMock()
    gui_server.dispatcher = MagicMock()

    with (
        patch.object(companion_app_module.shiboken6, "isValid", return_value=True),
        patch.object(companion_app_module.pylsp_server, "is_running", return_value=False),
    ):
        gui_server.shutdown()
        gui_server.shutdown()

    gui_server.launcher_window.close.assert_called_once()
    gui_server.launcher_window.deleteLater.assert_called_once()
    gui_server.dispatcher.stop_cli_server.assert_called_once()
    gui_server.dispatcher.disconnect_all.assert_called_once()


def test_rpc_server_system_capabilities_include_shutdown(rpc_server):
    assert rpc_server.run_system_rpc("system.list_capabilities", [], {}) == {
        "system.launch_dock_area": True,
        "system.shutdown": True,
    }


def test_rpc_server_system_shutdown_requests_gui_server_shutdown(rpc_server, qapp):
    gui_server = MagicMock()
    qapp.gui_server = gui_server

    rpc_server.run_system_rpc("system.shutdown", [], {})
    qapp.processEvents()

    gui_server.request_shutdown.assert_called_once()
    del qapp.gui_server


def test_on_rpc_update_system_shutdown_sends_response_before_return(rpc_server):
    order = []
    rpc_server.run_system_rpc = MagicMock(side_effect=lambda *_args: order.append("shutdown"))
    rpc_server.send_response = MagicMock(side_effect=lambda *_args: order.append("response"))
    rpc_server.serialize_result_and_send = MagicMock()

    rpc_server.on_rpc_update(
        {"action": "system.shutdown", "parameter": {"args": [], "kwargs": {}}},
        {"request_id": "shutdown-request", "sent_at": 1.0, "deadline": 10.0, "timeout": 2},
    )

    assert order == ["shutdown", "response"]
    rpc_server.send_response.assert_called_once_with("shutdown-request", True, {"result": None})
    rpc_server.serialize_result_and_send.assert_not_called()


def test_singleshot_rpc_repeat_raises_on_repeated_singleshot(rpc_server):
    """
    Test that a singleshot RPC method raises an error when called multiple times.
    """
    repeat = SingleshotRPCRepeat()
    rpc_server._rpc_singleshot_repeats["test_method"] = repeat

    repeat += 100  # First call should work fine
    with pytest.raises(RegistryNotReadyError):
        repeat += 2000  # Should raise here


def test_serialize_result_and_send_with_singleshot_retry(rpc_server, qtbot, dummy_widget):
    """
    Test that serialize_result_and_send retries when RegistryNotReadyError is raised,
    and eventually succeeds when the object becomes registered.
    """
    request_id = "test_request_123"

    dummy = dummy_widget

    # Track how many times serialize_object is called
    call_count = 0

    def serialize_side_effect(obj):
        nonlocal call_count
        call_count += 1
        # First 2 calls raise RegistryNotReadyError
        if call_count <= 2:
            raise RegistryNotReadyError(f"Not ready yet (call {call_count})")
        # Third call succeeds
        return {"gui_id": dummy.gui_id, "success": True}

    warning_mock = MagicMock()

    # Patch serialize_object to control when it raises RegistryNotReadyError
    with patch.object(rpc_server, "serialize_object", side_effect=serialize_side_effect):
        with patch.object(rpc_server, "send_response") as mock_send_response:
            with patch.object(rpc_server_module.logger, "warning", warning_mock):
                # Start the serialization process
                rpc_server._rpc_singleshot_repeats[request_id] = SingleshotRPCRepeat()
                rpc_server.serialize_result_and_send(request_id, dummy)

                # Verify that serialize_object was called 3 times
                qtbot.waitUntil(lambda: call_count >= 3, timeout=5000)

                # Verify that send_response was called with success
                mock_send_response.assert_called_once()
                args = mock_send_response.call_args[0]
                assert args[0] == request_id
                assert args[1] is True  # accepted=True
                assert "result" in args[2]

    assert warning_mock.call_count == 2
    warning_logs = "\n".join(call.args[0] for call in warning_mock.call_args_list)
    assert "result serialization delayed; retrying" in warning_logs
    assert "request_id=test_request_123" in warning_logs
    assert "retry_delay_ms=100" in warning_logs
    assert "accumulated_delay_ms=100" in warning_logs
    assert "accumulated_delay_ms=200" in warning_logs
    assert "max_delay_ms=2000" in warning_logs


def test_serialize_result_and_send_max_delay_exceeded(rpc_server, qtbot, dummy_widget):
    """
    Test that serialize_result_and_send sends an error response when max delay is exceeded.
    """
    request_id = "test_request_456"

    dummy = dummy_widget

    # Always raise RegistryNotReadyError
    with patch.object(
        rpc_server, "serialize_object", side_effect=RegistryNotReadyError("Always not ready")
    ):
        with patch.object(rpc_server, "send_response") as mock_send_response:
            # Start the serialization process
            rpc_server._rpc_singleshot_repeats[request_id] = SingleshotRPCRepeat()
            rpc_server.serialize_result_and_send(request_id, dummy)

            # Process event loop to allow all singleshot timers to fire
            # Max delay is 2000ms, with 100ms retry intervals = ~20 retries
            # Wait for the max delay plus some buffer
            qtbot.wait(2500)

            # Verify that send_response was called with an error
            mock_send_response.assert_called()
            args = mock_send_response.call_args[0]
            assert args[0] == request_id
            assert args[1] is False  # accepted=False
            assert "error" in args[2]
            assert "Max delay exceeded" in args[2]["error"]


def test_send_response_logs_publish_status(rpc_server, monkeypatch):
    info_mock = MagicMock()
    error_mock = MagicMock()
    monkeypatch.setattr(rpc_server_module.logger, "info", info_mock)
    monkeypatch.setattr(rpc_server_module.logger, "error", error_mock)

    with patch.object(rpc_server.client.connector, "set_and_publish") as publish_mock:
        rpc_server.send_response("request-ok", True, {"result": None})
        rpc_server.send_response("request-failed", False, {"error": "bad"})

    assert publish_mock.call_count == 2
    assert "request_id=request-ok" in info_mock.call_args.args[0]
    assert "accepted=True" in info_mock.call_args.args[0]
    assert "request_id=request-failed" in error_mock.call_args.args[0]
    assert "accepted=False" in error_mock.call_args.args[0]


def test_on_rpc_update_logs_late_client_deadline(rpc_server, monkeypatch):
    info_mock = MagicMock()
    warning_mock = MagicMock()
    monkeypatch.setattr(rpc_server_module.logger, "info", info_mock)
    monkeypatch.setattr(rpc_server_module.logger, "warning", warning_mock)

    rpc_server.rpc_register.get_rpc_by_id = MagicMock()
    rpc_server.run_rpc = MagicMock(return_value=None)
    rpc_server.serialize_result_and_send = MagicMock()

    rpc_server.on_rpc_update(
        {
            "action": "set_value",
            "parameter": {"args": [1], "kwargs": {"source": "test"}, "gui_id": "ring"},
        },
        {"request_id": "late-request", "timeout": 0.1, "sent_at": 1.0, "deadline": 1.1},
    )

    received_log = info_mock.call_args_list[0].args[0]
    executed_log = info_mock.call_args_list[1].args[0]
    warning_logs = "\n".join(call.args[0] for call in warning_mock.call_args_list)

    assert "GUI RPC server received request" in received_log
    assert "request_id=late-request" in received_log
    assert "method=set_value" in received_log
    assert "target_gui_id=ring" in received_log
    assert "timeout=0.1" in received_log
    assert "stale_on_receive=True" in received_log
    assert "response_after_client_deadline=True" in executed_log
    assert "received request after client timeout deadline" in warning_logs
    assert "response is late for client timeout" in warning_logs


def test_run_rpc_delegates_to_rpc_content_class(rpc_server):
    class Content:
        USER_ACCESS = ["foo", "mode", "mode.setter"]

        def __init__(self):
            self._mode = "initial"

        def foo(self):
            return "ok"

        @property
        def mode(self):
            return self._mode

        @mode.setter
        def mode(self, value):
            self._mode = value

    class View:
        RPC_CONTENT_CLASS = Content
        RPC_CONTENT_ATTR = "content"

        def __init__(self):
            self.content = Content()

    view = View()

    assert rpc_server.run_rpc(view, "foo", [], {}) == "ok"
    assert rpc_server.run_rpc(view, "mode", [], {}) == "initial"
    assert rpc_server.run_rpc(view, "mode", ["creator"], {}) is None
    assert view.content.mode == "creator"


def test_rpc_server_shutdown_releases_registrations(mocked_client):
    """Regression test for BW-008/BW-009: shutdown must disconnect the
    gui_instructions dispatcher slot and remove the registry callback so a
    restarted server does not duplicate registrations and the old server can
    be collected."""
    from bec_widgets.utils.rpc_register import RPCRegister

    register = RPCRegister()
    callbacks_before = len(register.callbacks)

    server = RPCServer(gui_id="lifecycle_gui", client=mocked_client)
    assert len(register.callbacks) == callbacks_before + 1

    dispatcher_slots_with_topic = [
        slot
        for slot in server.dispatcher._registered_slots.values()
        if any("lifecycle_gui" in topic for topic in slot.topics)
    ]
    assert len(dispatcher_slots_with_topic) == 1

    server.shutdown()

    assert len(register.callbacks) == callbacks_before
    dispatcher_slots_with_topic = [
        slot
        for slot in server.dispatcher._registered_slots.values()
        if any("lifecycle_gui" in topic for topic in slot.topics)
    ]
    assert dispatcher_slots_with_topic == []

    # Shutdown must be idempotent.
    server.shutdown()
    assert len(register.callbacks) == callbacks_before


def test_rpc_register_remove_callback_is_noop_for_unknown(rpc_register=None):
    from bec_widgets.utils.rpc_register import RPCRegister

    register = RPCRegister()
    register.remove_callback(lambda connections: None)  # must not raise
