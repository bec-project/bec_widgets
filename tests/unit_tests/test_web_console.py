from unittest import mock

import pytest
from qtpy.QtCore import Qt
from qtpy.QtGui import QHideEvent
from qtpy.QtNetwork import QAuthenticator

from bec_widgets.widgets.editors.web_console.web_console import (
    BECShell,
    ConsoleMode,
    WebConsole,
    _web_console_registry,
)


@pytest.fixture
def mocked_server_startup():
    """Mock the web console server startup process."""
    with mock.patch(
        "bec_widgets.widgets.editors.web_console.web_console.subprocess"
    ) as mock_subprocess:
        with mock.patch.object(_web_console_registry, "_wait_for_server_port"):
            _web_console_registry._server_port = 12345
            yield mock_subprocess


def static_console(qtbot, client, unique_id: str | None = None):
    """Fixture to provide a static unique_id for WebConsole tests."""
    if unique_id is None:
        widget = WebConsole(client=client)
    else:
        widget = WebConsole(client=client, unique_id=unique_id)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def console_widget(qtbot, mocked_client, mocked_server_startup):
    """Create a WebConsole widget with mocked server startup."""
    yield static_console(qtbot, mocked_client)


@pytest.fixture
def bec_shell_widget(qtbot, mocked_client, mocked_server_startup):
    """Create a BECShell widget with mocked server startup."""
    widget = BECShell(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def console_widget_with_static_id(qtbot, mocked_client, mocked_server_startup):
    """Create a WebConsole widget with a static unique ID."""
    yield static_console(qtbot, mocked_client, unique_id="test_console")


@pytest.fixture
def two_console_widgets_same_id(qtbot, mocked_client, mocked_server_startup):
    """Create two WebConsole widgets sharing the same unique ID."""
    widget1 = static_console(qtbot, mocked_client, unique_id="shared_console")
    widget2 = static_console(qtbot, mocked_client, unique_id="shared_console")
    yield widget1, widget2


def test_web_console_widget_initialization(console_widget):
    assert (
        console_widget.page.url().toString()
        == f"http://localhost:{_web_console_registry._server_port}"
    )


def test_web_console_write(console_widget):
    # Test the write method
    with mock.patch.object(console_widget.page, "runJavaScript") as mock_run_js:
        console_widget.write("Hello, World!")

        assert mock.call('window.term.paste("Hello, World!");') in mock_run_js.mock_calls


def test_web_console_write_no_return(console_widget):
    # Test the write method with send_return=False
    with mock.patch.object(console_widget.page, "runJavaScript") as mock_run_js:
        console_widget.write("Hello, World!", send_return=False)

        assert mock.call('window.term.paste("Hello, World!");') in mock_run_js.mock_calls
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


def test_bec_shell_startup_contains_gui_id(bec_shell_widget):
    """Test that the BEC shell startup command includes the GUI ID."""
    bec_shell = bec_shell_widget

    assert bec_shell._is_bec_shell
    assert bec_shell._unique_id == "bec_shell"

    with mock.patch.object(bec_shell.bec_dispatcher, "cli_server", None):
        assert bec_shell.startup_cmd == "bec --nogui"

    with mock.patch.object(bec_shell.bec_dispatcher.cli_server, "gui_id", "test_gui_id"):
        assert bec_shell.startup_cmd == "bec --gui-id test_gui_id"


def test_web_console_set_readonly(console_widget):
    # Test the set_readonly method
    console_widget.set_readonly(True)
    assert not console_widget.isEnabled()

    console_widget.set_readonly(False)
    assert console_widget.isEnabled()


def test_web_console_with_unique_id(console_widget_with_static_id):
    """Test creating a WebConsole with a unique_id."""
    widget = console_widget_with_static_id

    assert widget._unique_id == "test_console"
    assert widget._unique_id in _web_console_registry._page_registry
    page_info = _web_console_registry.get_page_info("test_console")
    assert page_info is not None
    assert page_info.owner_gui_id == widget.gui_id
    assert widget.gui_id in page_info.widget_ids


def test_web_console_page_sharing(two_console_widgets_same_id):
    """Test that two widgets can share the same page using unique_id."""
    widget1, widget2 = two_console_widgets_same_id

    # Both should reference the same page in the registry
    page_info = _web_console_registry.get_page_info("shared_console")
    assert page_info is not None
    assert widget1.gui_id in page_info.widget_ids
    assert widget2.gui_id in page_info.widget_ids
    assert widget1.page == widget2.page


def test_web_console_has_ownership(console_widget_with_static_id):
    """Test the has_ownership method."""
    widget = console_widget_with_static_id

    # Widget should have ownership by default
    assert widget.has_ownership()


def test_web_console_yield_ownership(console_widget_with_static_id):
    """Test yielding ownership of a page."""
    widget = console_widget_with_static_id

    assert widget.has_ownership()

    # Yield ownership
    widget.yield_ownership()

    # Widget should no longer have ownership
    assert not widget.has_ownership()
    page_info = _web_console_registry.get_page_info("test_console")
    assert page_info.owner_gui_id is None
    # Overlay should be shown
    assert widget._mode == ConsoleMode.INACTIVE


def test_web_console_take_page_ownership(two_console_widgets_same_id):
    """Test taking ownership of a page."""
    widget1, widget2 = two_console_widgets_same_id

    # Widget1 should have ownership initially
    assert widget1.has_ownership()
    assert not widget2.has_ownership()

    # Widget2 takes ownership
    widget2.take_page_ownership()

    # Now widget2 should have ownership
    assert not widget1.has_ownership()
    assert widget2.has_ownership()

    assert widget2._mode == ConsoleMode.ACTIVE
    assert widget1._mode == ConsoleMode.INACTIVE


def test_web_console_hide_event_yields_ownership(qtbot, console_widget_with_static_id):
    """Test that hideEvent yields ownership."""
    widget = console_widget_with_static_id

    assert widget.has_ownership()

    # Hide the widget. Note that we cannot call widget.hide() directly
    # because it doesn't trigger the hideEvent in tests as widgets are
    # not visible in the test environment.
    widget.hideEvent(QHideEvent())
    qtbot.wait(100)  # Allow event processing

    # Widget should have yielded ownership
    assert not widget.has_ownership()
    page_info = _web_console_registry.get_page_info("test_console")
    assert page_info.owner_gui_id is None


def test_web_console_show_event_takes_ownership(console_widget_with_static_id):
    """Test that showEvent takes ownership when page has no owner."""
    widget = console_widget_with_static_id

    # Yield ownership
    widget.yield_ownership()
    assert not widget.has_ownership()

    # Show the widget again
    widget.show()

    # Widget should have reclaimed ownership
    assert widget.has_ownership()
    assert widget.browser.isVisible()
    assert not widget.overlay.isVisible()


def test_web_console_mouse_press_takes_ownership(qtbot, two_console_widgets_same_id):
    """Test that clicking on overlay takes ownership."""
    widget1, widget2 = two_console_widgets_same_id
    widget1.show()
    widget2.show()

    # Widget1 has ownership, widget2 doesn't
    assert widget1.has_ownership()
    assert not widget2.has_ownership()
    assert widget1.isVisible()
    assert widget1._mode == ConsoleMode.ACTIVE
    assert widget2._mode == ConsoleMode.INACTIVE

    qtbot.mouseClick(widget2, Qt.MouseButton.LeftButton)

    # Widget2 should now have ownership
    assert widget2.has_ownership()
    assert not widget1.has_ownership()


def test_web_console_registry_cleanup_removes_page(console_widget_with_static_id):
    """Test that the registry cleans up pages when all widgets are removed."""
    widget = console_widget_with_static_id

    assert widget._unique_id in _web_console_registry._page_registry

    # Cleanup the widget
    widget.cleanup()

    # Page should be removed from registry
    assert widget._unique_id not in _web_console_registry._page_registry


def test_web_console_without_unique_id_no_page_sharing(console_widget):
    """Test that widgets without unique_id don't participate in page sharing."""
    widget = console_widget

    # Widget should not be in the page registry
    assert widget._unique_id is None
    assert not widget.has_ownership()  # Should return False for non-unique widgets


def test_web_console_registry_get_page_info_nonexistent(qtbot, mocked_client):
    """Test getting page info for a non-existent page."""
    page_info = _web_console_registry.get_page_info("nonexistent")
    assert page_info is None


def test_web_console_take_ownership_without_unique_id(console_widget):
    """Test that take_page_ownership fails gracefully without unique_id."""
    widget = console_widget
    # Should not crash when taking ownership without unique_id
    widget.take_page_ownership()


def test_web_console_yield_ownership_without_unique_id(console_widget):
    """Test that yield_ownership fails gracefully without unique_id."""
    widget = console_widget
    # Should not crash when yielding ownership without unique_id
    widget.yield_ownership()


def test_registry_yield_ownership_gui_id_not_in_instances():
    """Test registry yield_ownership returns False when gui_id not in instances."""
    result = _web_console_registry.yield_ownership("nonexistent_gui_id")
    assert result is False


def test_registry_yield_ownership_instance_is_none(console_widget_with_static_id):
    """Test registry yield_ownership returns False when instance weakref is dead."""
    widget = console_widget_with_static_id
    gui_id = widget.gui_id

    # Store the gui_id and simulate the weakref being dead
    _web_console_registry._instances[gui_id] = lambda: None

    result = _web_console_registry.yield_ownership(gui_id)
    assert result is False


def test_registry_yield_ownership_unique_id_none(console_widget_with_static_id):
    """Test registry yield_ownership returns False when page info's unique_id is None."""
    widget = console_widget_with_static_id
    gui_id = widget.gui_id
    unique_id = widget._unique_id
    widget._unique_id = None

    result = _web_console_registry.yield_ownership(gui_id)
    assert result is False

    widget._unique_id = unique_id  # Restore for cleanup


def test_registry_yield_ownership_unique_id_not_in_page_registry(console_widget_with_static_id):
    """Test registry yield_ownership returns False when unique_id not in page registry."""
    widget = console_widget_with_static_id
    gui_id = widget.gui_id
    unique_id = widget._unique_id
    widget._unique_id = "nonexistent_unique_id"

    result = _web_console_registry.yield_ownership(gui_id)
    assert result is False

    widget._unique_id = unique_id  # Restore for cleanup


def test_registry_owner_is_visible_page_info_none():
    """Test owner_is_visible returns False when page info doesn't exist."""
    result = _web_console_registry.owner_is_visible("nonexistent_page")
    assert result is False


def test_registry_owner_is_visible_no_owner(console_widget_with_static_id):
    """Test owner_is_visible returns False when page has no owner."""
    widget = console_widget_with_static_id

    # Yield ownership so there's no owner
    widget.yield_ownership()
    page_info = _web_console_registry.get_page_info(widget._unique_id)
    assert page_info.owner_gui_id is None

    result = _web_console_registry.owner_is_visible(widget._unique_id)
    assert result is False


def test_registry_owner_is_visible_owner_ref_none(console_widget_with_static_id):
    """Test owner_is_visible returns False when owner ref doesn't exist in instances."""
    widget = console_widget_with_static_id
    unique_id = widget._unique_id

    # Remove owner from instances dict
    del _web_console_registry._instances[widget.gui_id]

    result = _web_console_registry.owner_is_visible(unique_id)
    assert result is False


def test_registry_owner_is_visible_owner_instance_none(console_widget_with_static_id):
    """Test owner_is_visible returns False when owner instance weakref is dead."""
    widget = console_widget_with_static_id
    unique_id = widget._unique_id
    gui_id = widget.gui_id

    # Simulate dead weakref
    _web_console_registry._instances[gui_id] = lambda: None

    result = _web_console_registry.owner_is_visible(unique_id)
    assert result is False


def test_registry_owner_is_visible_owner_visible(console_widget_with_static_id):
    """Test owner_is_visible returns True when owner is visible."""
    widget = console_widget_with_static_id
    widget.show()

    result = _web_console_registry.owner_is_visible(widget._unique_id)
    assert result is True


def test_registry_owner_is_visible_owner_not_visible(console_widget_with_static_id):
    """Test owner_is_visible returns False when owner is not visible."""
    widget = console_widget_with_static_id
    widget.hide()

    result = _web_console_registry.owner_is_visible(widget._unique_id)
    assert result is False
