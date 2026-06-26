from unittest.mock import MagicMock

import pytest
from bec_lib import messages
from bec_lib.device import DeviceBaseWithConfig, Signal

from bec_widgets.cli.rpc import rpc_base as rpc_base_module
from bec_widgets.cli.rpc.rpc_base import (
    DeletedWidgetError,
    RPCBase,
    RPCReference,
    RPCResponseTimeoutError,
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


def test_run_rpc_logs_response_timeout(monkeypatch):
    rpc = RPCBase(gui_id="progress_widget", object_name="progressbar")
    rpc._rpc_timeout = 0
    rpc._client = MagicMock()
    rpc._client.connector.get.return_value = None

    info_mock = MagicMock()
    error_mock = MagicMock()
    monkeypatch.setattr(rpc_base_module.logger, "info", info_mock)
    monkeypatch.setattr(rpc_base_module.logger, "error", error_mock)

    with pytest.raises(RPCResponseTimeoutError):
        rpc._run_rpc("set_value", 42, precision=2, timeout=0)

    publish_msg = rpc._client.connector.set_and_publish.call_args.args[1]
    assert publish_msg.metadata["method"] == "set_value"
    assert publish_msg.metadata["target_gui_id"] == "progress_widget"
    assert publish_msg.metadata["object_name"] == "progressbar"
    assert publish_msg.metadata["timeout"] == 0
    assert publish_msg.metadata["deadline"] == publish_msg.metadata["sent_at"]
    assert info_mock.call_count == 1
    info_message = info_mock.call_args.args[0]
    error_mock.assert_called_once()
    error_message = error_mock.call_args.args[0]
    assert "GUI RPC response timeout" in error_message
    assert "method=set_value" in error_message
    assert "target_gui_id=progress_widget" in error_message
    assert "object_name=progressbar" in error_message
    assert "timeout=0" in error_message


def test_run_rpc_waits_indefinitely_when_timeout_is_none(monkeypatch):
    rpc = RPCBase(gui_id="progress_widget", object_name="progressbar")
    rpc._client = MagicMock()
    rpc._create_widget_from_msg_result = MagicMock(return_value="done")

    response = messages.RequestResponseMessage(accepted=True, message={"result": "rpc-result"})

    wait_calls = {"count": 0}

    def wait_side_effect(timeout):
        wait_calls["count"] += 1
        if wait_calls["count"] == 1:
            return False
        rpc._rpc_response = response
        rpc._msg_wait_event.set()
        return True

    monkeypatch.setattr(rpc._msg_wait_event, "wait", wait_side_effect)
    fetch_mock = MagicMock()
    monkeypatch.setattr(rpc, "_fetch_rpc_response", fetch_mock)

    result = rpc._run_rpc("set_value", timeout=None)

    assert result == "done"
    assert fetch_mock.call_count == 1
    assert wait_calls["count"] == 2
    assert rpc._create_widget_from_msg_result.call_args.args == ("rpc-result",)


def test_run_rpc_fetches_response_before_timeout(monkeypatch):
    rpc = RPCBase(gui_id="progress_widget", object_name="progressbar")
    rpc._client = MagicMock()
    rpc._create_widget_from_msg_result = MagicMock(return_value="done")

    response = messages.RequestResponseMessage(accepted=True, message={"result": "rpc-result"})

    monkeypatch.setattr(rpc._msg_wait_event, "wait", MagicMock(return_value=False))

    def fetch_side_effect(_request_id):
        rpc._rpc_response = response
        rpc._msg_wait_event.set()

    fetch_mock = MagicMock(side_effect=fetch_side_effect)
    monkeypatch.setattr(rpc, "_fetch_rpc_response", fetch_mock)

    result = rpc._run_rpc("set_value", timeout=0)

    assert result == "done"
    fetch_mock.assert_called_once()
    rpc._create_widget_from_msg_result.assert_called_once_with("rpc-result")
