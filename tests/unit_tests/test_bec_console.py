from unittest import mock

import pytest
from qtpy.QtCore import Qt
from qtpy.QtGui import QHideEvent, QShowEvent
from qtpy.QtTest import QTest

from bec_widgets.widgets.editors.bec_console.bec_console import (
    BecConsole,
    BECShell,
    ConsoleMode,
    _bec_console_registry,
)

from .client_mocks import mocked_client


@pytest.fixture
def console_widget(qtbot):
    """Create a BecConsole widget."""
    widget = BecConsole(client=mocked_client, gui_id="test_console", terminal_id="test_terminal")
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def two_console_widgets_same_terminal(qtbot):
    widget1 = BecConsole(client=mocked_client, gui_id="console_1", terminal_id="shared_terminal")
    widget2 = BecConsole(client=mocked_client, gui_id="console_2", terminal_id="shared_terminal")
    qtbot.addWidget(widget1)
    qtbot.addWidget(widget2)
    return widget1, widget2


def test_bec_console_initialization(console_widget: BecConsole):
    assert console_widget.console_id == "test_console"
    assert console_widget.terminal_id == "test_terminal"
    assert console_widget._mode == ConsoleMode.ACTIVE
    assert console_widget.term is not None
    assert console_widget._overlay.isHidden()
    console_widget.show()
    assert console_widget.isVisible()
    assert _bec_console_registry.owner_is_visible(console_widget.terminal_id)


def test_bec_console_yield_terminal_ownership(console_widget):
    console_widget.show()
    console_widget.take_terminal_ownership()
    console_widget.yield_ownership()
    assert console_widget.term is None
    assert console_widget._mode == ConsoleMode.INACTIVE


def test_bec_console_hide_event_yields_ownership(console_widget):
    console_widget.take_terminal_ownership()
    console_widget.hideEvent(QHideEvent())
    assert console_widget.term is None
    assert console_widget._mode == ConsoleMode.HIDDEN


def test_bec_console_show_event_takes_ownership(console_widget):
    console_widget.yield_ownership()
    console_widget.showEvent(QShowEvent())
    assert console_widget.term is not None
    assert console_widget._mode == ConsoleMode.ACTIVE


def test_bec_console_overlay_click_takes_ownership(qtbot, console_widget):
    console_widget.yield_ownership()
    assert console_widget._mode == ConsoleMode.HIDDEN

    QTest.mouseClick(console_widget._overlay, Qt.LeftButton)
    assert console_widget.term is not None
    assert console_widget._mode == ConsoleMode.ACTIVE
    assert not console_widget._overlay.isVisible()


def test_two_consoles_shared_terminal(two_console_widgets_same_terminal):
    widget1, widget2 = two_console_widgets_same_terminal

    # Widget1 takes ownership
    widget1.take_terminal_ownership()
    assert widget1.term is not None
    assert widget1._mode == ConsoleMode.ACTIVE
    assert widget2.term is None
    assert widget2._mode == ConsoleMode.HIDDEN

    # Widget2 takes ownership
    widget2.take_terminal_ownership()
    assert widget2.term is not None
    assert widget2._mode == ConsoleMode.ACTIVE
    assert widget1.term is None
    assert widget1._mode == ConsoleMode.HIDDEN


def test_bec_console_registry_cleanup(console_widget: BecConsole):
    console_widget.take_terminal_ownership()
    terminal_id = console_widget.terminal_id

    assert terminal_id in _bec_console_registry._terminal_registry
    _bec_console_registry.unregister(console_widget)
    assert terminal_id not in _bec_console_registry._terminal_registry


def test_bec_shell_initialization(qtbot):
    widget = BECShell(gui_id="bec_shell")
    qtbot.addWidget(widget)

    assert widget.console_id == "bec_shell"
    assert widget.terminal_id == "bec_shell"
    assert widget.startup_cmd is not None


def test_bec_console_write(console_widget):
    console_widget.take_terminal_ownership()
    with mock.patch.object(console_widget.term, "write") as mock_write:
        console_widget.write("test command")
        mock_write.assert_called_once_with("test command", True)


def test_is_owner(console_widget: BecConsole):
    assert _bec_console_registry.is_owner(console_widget)
    mock_console = mock.MagicMock()
    mock_console.console_id = "fake_console"
    _bec_console_registry._consoles["fake_console"] = mock_console
    assert not _bec_console_registry.is_owner(mock_console)
    mock_console.terminal_id = console_widget.terminal_id
    assert not _bec_console_registry.is_owner(mock_console)
