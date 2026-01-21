import argparse
from unittest.mock import patch

import pytest
from bec_lib.service_config import ServiceConfig
from qtpy.QtWidgets import QWidget

from bec_widgets.cli.server import GUIServer
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

    # Patch serialize_object to control when it raises RegistryNotReadyError
    with patch.object(rpc_server, "serialize_object", side_effect=serialize_side_effect):
        with patch.object(rpc_server, "send_response") as mock_send_response:
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
