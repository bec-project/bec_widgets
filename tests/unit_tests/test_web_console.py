from unittest import mock

import pytest
from qtpy.QtNetwork import QAuthenticator

from bec_widgets.widgets.editors.web_console.web_console import WebConsole, _web_console_registry

from .client_mocks import mocked_client


@pytest.fixture
def console_widget(qtbot, mocked_client):
    with mock.patch(
        "bec_widgets.widgets.editors.web_console.web_console.subprocess"
    ) as mock_subprocess:
        with mock.patch.object(_web_console_registry, "_wait_for_server_port"):
            _web_console_registry._server_port = 12345
            # Create the WebConsole widget
            widget = WebConsole(client=mocked_client)
            qtbot.addWidget(widget)
            qtbot.waitExposed(widget)
            yield widget


def test_web_console_widget_initialization(console_widget):
    assert (
        console_widget.page.url().toString()
        == f"http://localhost:{_web_console_registry._server_port}"
    )


def test_web_console_write(console_widget):
    # Test the write method
    with mock.patch.object(console_widget.page, "runJavaScript") as mock_run_js:
        console_widget.write("Hello, World!")

        assert mock.call("window.term.paste('Hello, World!');") in mock_run_js.mock_calls


def test_web_console_write_no_return(console_widget):
    # Test the write method with send_return=False
    with mock.patch.object(console_widget.page, "runJavaScript") as mock_run_js:
        console_widget.write("Hello, World!", send_return=False)

        assert mock.call("window.term.paste('Hello, World!');") in mock_run_js.mock_calls
        assert mock_run_js.call_count == 1


def test_web_console_send_return(console_widget):
    # Test the send_return method
    with mock.patch.object(console_widget.page, "runJavaScript") as mock_run_js:
        console_widget.send_return()

        script = mock_run_js.call_args[0][0]
        assert "new KeyboardEvent('keypress', {charCode: 13})" in script
        assert mock_run_js.call_count == 1


def test_web_console_send_ctrl_c(console_widget):
    # Test the send_ctrl_c method
    with mock.patch.object(console_widget.page, "runJavaScript") as mock_run_js:
        console_widget.send_ctrl_c()

        script = mock_run_js.call_args[0][0]
        assert "new KeyboardEvent('keypress', {charCode: 3})" in script
        assert mock_run_js.call_count == 1


def test_web_console_authenticate(console_widget):
    # Test the _authenticate method
    token = _web_console_registry._token
    mock_auth = mock.MagicMock(spec=QAuthenticator)
    console_widget._authenticate(None, mock_auth)
    mock_auth.setUser.assert_called_once_with("user")
    mock_auth.setPassword.assert_called_once_with(token)


def test_web_console_registry_wait_for_server_port():
    # Test the _wait_for_server_port method
    with mock.patch.object(_web_console_registry, "_server_process") as mock_subprocess:
        mock_subprocess.stderr.readline.side_effect = [b"Starting", b"Listening on port: 12345"]
        _web_console_registry._wait_for_server_port()
        assert _web_console_registry._server_port == 12345


def test_web_console_registry_wait_for_server_port_timeout():
    # Test the _wait_for_server_port method with timeout
    with mock.patch.object(_web_console_registry, "_server_process") as mock_subprocess:
        with pytest.raises(TimeoutError):
            _web_console_registry._wait_for_server_port(timeout=0.1)


def test_web_console_startup_command_execution(console_widget, qtbot):
    """Test that the startup command is triggered after successful initialization."""
    # Set a custom startup command
    console_widget.startup_cmd = "test startup command"

    assert console_widget.startup_cmd == "test startup command"

    # Generator to simulate JS initialization sequence
    def js_readiness_sequence():
        yield False  # First call: not ready yet
        while True:
            yield True  # Any subsequent calls: ready

    readiness_gen = js_readiness_sequence()

    def mock_run_js(script, callback=None):
        # Check if this is the initialization check call
        if "window.term !== undefined" in script and callback:
            ready = next(readiness_gen)
            callback(ready)
        else:
            # For other JavaScript calls (like paste), just call the callback
            if callback:
                callback(True)

    with mock.patch.object(
        console_widget.page, "runJavaScript", side_effect=mock_run_js
    ) as mock_run_js_method:
        # Reset initialization state and start the timer
        console_widget._is_initialized = False
        console_widget._startup_timer.start()

        # Wait for the initialization to complete
        qtbot.waitUntil(lambda: console_widget._is_initialized, timeout=3000)

        # Verify that the startup command was executed
        startup_calls = [
            call
            for call in mock_run_js_method.call_args_list
            if "test startup command" in str(call)
        ]
        assert len(startup_calls) > 0, "Startup command should have been executed"

        # Verify the initialized signal was emitted
        assert console_widget._is_initialized is True
        assert not console_widget._startup_timer.isActive()


def test_web_console_set_readonly(console_widget):
    # Test the set_readonly method
    console_widget.set_readonly(True)
    assert not console_widget.isEnabled()

    console_widget.set_readonly(False)
    assert console_widget.isEnabled()
