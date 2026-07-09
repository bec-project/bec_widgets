from unittest import mock

import pytest
import shiboken6
from qtpy.QtCore import QEvent, QEventLoop, Qt
from qtpy.QtGui import QHideEvent, QShowEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

import bec_widgets.widgets.editors.bec_console.bec_console as bec_console_module
from bec_widgets.widgets.editors.bec_console.bec_console import (
    BecConsole,
    BECShell,
    ConsoleMode,
    _bec_console_registry,
)
from bec_widgets.widgets.utility.bec_term.qtermwidget_wrapper import BecQTerm

from .client_mocks import mocked_client


def process_deferred_deletes():
    app = QApplication.instance()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents(QEventLoop.AllEvents)


@pytest.fixture(autouse=True)
def clean_bec_console_registry():
    _bec_console_registry.clear()
    yield
    _bec_console_registry.clear()
    process_deferred_deletes()


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
    assert console_widget.zoom_level == 1
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
    assert widget.zoom_level == 1


def test_bec_console_write(console_widget):
    console_widget.take_terminal_ownership()
    with mock.patch.object(console_widget.term, "write") as mock_write:
        console_widget.write("test command")
        mock_write.assert_called_once_with("test command", True)


def test_bec_console_write_can_target_shared_terminal_without_ownership(qtbot):
    owner = BecConsole(client=mocked_client, gui_id="owner_console", terminal_id="shared_submit")
    submitter = BecConsole(
        client=mocked_client, gui_id="submitter_console", terminal_id="shared_submit"
    )
    qtbot.addWidget(owner)
    qtbot.addWidget(submitter)

    owner.take_terminal_ownership()
    assert owner.term is not None
    assert submitter.term is None

    with mock.patch.object(owner.term, "write") as mock_write:
        submitter.write("test command", regardless_of_ownership=True)
        mock_write.assert_called_once_with("test command", True)


def test_bec_console_zoom_tracks_shared_terminal_without_ownership(qtbot):
    owner = BecConsole(client=mocked_client, gui_id="zoom_owner", terminal_id="shared_zoom")
    follower = BecConsole(client=mocked_client, gui_id="zoom_follower", terminal_id="shared_zoom")
    qtbot.addWidget(owner)
    qtbot.addWidget(follower)

    owner.take_terminal_ownership()
    assert owner.term is not None

    with (
        mock.patch.object(owner.term, "zoom_in") as mock_zoom_in,
        mock.patch.object(owner.term, "zoom_out") as mock_zoom_out,
    ):
        assert follower.zoom_in() == 2
        assert follower.zoom_level == 2
        mock_zoom_in.assert_called_once_with()

        assert follower.zoom_out() == 1
        assert follower.zoom_level == 1
        mock_zoom_out.assert_called_once_with()


def test_bec_console_reapplies_zoom_level_when_terminal_is_recreated(qtbot, monkeypatch):
    class RecordingTerminal(QWidget):
        zoom_in_calls = 0
        zoom_out_calls = 0

        def write(self, text: str, add_newline: bool = True):
            return None

        def zoom_in(self):
            type(self).zoom_in_calls += 1

        def zoom_out(self):
            type(self).zoom_out_calls += 1

        def send_ctrl_c(self):
            return None

    monkeypatch.setattr(bec_console_module, "_BecTermClass", RecordingTerminal)

    widget = BecConsole(client=mocked_client, gui_id="zoom_recreate", terminal_id="zoom_recreate")
    qtbot.addWidget(widget)

    widget.zoom_in()
    widget.zoom_in()
    assert widget.zoom_level == 3
    assert RecordingTerminal.zoom_in_calls == 3

    _bec_console_registry._terminal_registry[widget.terminal_id].instance = None
    widget.take_terminal_ownership()

    assert widget.zoom_level == 3
    assert RecordingTerminal.zoom_in_calls == 6


def test_bec_console_starts_with_default_zoom_level(qtbot, monkeypatch):
    class RecordingTerminal(QWidget):
        zoom_in_calls = 0
        zoom_out_calls = 0

        def write(self, text: str, add_newline: bool = True):
            return None

        def zoom_in(self):
            type(self).zoom_in_calls += 1

        def zoom_out(self):
            type(self).zoom_out_calls += 1

        def send_ctrl_c(self):
            return None

    monkeypatch.setattr(bec_console_module, "_BecTermClass", RecordingTerminal)

    widget = BecConsole(
        client=mocked_client, gui_id="console_zoom_default", terminal_id="zoom_default"
    )
    qtbot.addWidget(widget)

    assert widget.zoom_level == 1
    assert RecordingTerminal.zoom_in_calls == 1
    assert RecordingTerminal.zoom_out_calls == 0


def test_is_owner(console_widget: BecConsole):
    assert _bec_console_registry.is_owner(console_widget)
    mock_console = mock.MagicMock()
    mock_console.console_id = "fake_console"
    _bec_console_registry._consoles["fake_console"] = mock_console
    assert not _bec_console_registry.is_owner(mock_console)
    mock_console.terminal_id = console_widget.terminal_id
    assert not _bec_console_registry.is_owner(mock_console)


def test_closing_active_console_keeps_terminal_valid_for_remaining_console(qtbot):
    widget1 = BecConsole(client=mocked_client, gui_id="close_owner", terminal_id="shared_close")
    widget2 = BecConsole(client=mocked_client, gui_id="remaining", terminal_id="shared_close")
    qtbot.addWidget(widget2)

    widget1.take_terminal_ownership()
    term = widget1.term
    assert term is not None

    widget1.close()
    widget1.deleteLater()
    process_deferred_deletes()

    assert shiboken6.isValid(term)
    widget2.take_terminal_ownership()

    assert widget2.term is term
    assert widget2._mode == ConsoleMode.ACTIVE


def test_active_console_detaches_terminal_before_destruction(qtbot):
    widget1 = BecConsole(client=mocked_client, gui_id="owner", terminal_id="shared_detach")
    widget2 = BecConsole(client=mocked_client, gui_id="survivor", terminal_id="shared_detach")
    qtbot.addWidget(widget1)
    qtbot.addWidget(widget2)

    widget1.take_terminal_ownership()
    term = widget1.term
    assert term is not None
    assert widget1.isAncestorOf(term)

    widget1.close()

    assert shiboken6.isValid(term)
    assert not widget1.isAncestorOf(term)
    assert term.parent() is widget2._term_holder


def test_bec_shell_terminal_persists_after_last_shell_unregisters(qtbot):
    shell = BECShell(gui_id="bec_shell_persistent")
    qtbot.addWidget(shell)
    term = shell.term
    assert term is not None

    _bec_console_registry.unregister(shell)

    info = _bec_console_registry._terminal_registry["bec_shell"]
    assert info.registered_console_ids == set()
    assert info.owner_console_id is None
    assert info.persist_session is True
    assert info.instance is term
    assert shiboken6.isValid(term)


def test_new_bec_shell_claims_preserved_terminal(qtbot):
    shell1 = BECShell(gui_id="bec_shell_first")
    term = shell1.term
    assert term is not None

    shell1.close()
    shell1.deleteLater()
    process_deferred_deletes()

    assert "bec_shell" in _bec_console_registry._terminal_registry
    assert shiboken6.isValid(term)

    shell2 = BECShell(gui_id="bec_shell_second")
    qtbot.addWidget(shell2)
    shell2.showEvent(QShowEvent())

    assert shell2.term is term
    assert shell2._mode == ConsoleMode.ACTIVE


def test_persistent_bec_shell_sends_startup_command_once(qtbot, monkeypatch):
    class RecordingTerminal(QWidget):
        writes = []

        def write(self, text: str, add_newline: bool = True):
            self.writes.append((text, add_newline))

    monkeypatch.setattr(bec_console_module, "_BecTermClass", RecordingTerminal)

    shell1 = BECShell(gui_id="bec_shell_startup_first")
    shell1.close()
    shell1.deleteLater()
    process_deferred_deletes()

    shell2 = BECShell(gui_id="bec_shell_startup_second")
    qtbot.addWidget(shell2)
    shell2.showEvent(QShowEvent())

    assert len(RecordingTerminal.writes) == 1
    assert RecordingTerminal.writes[0][0].startswith("bec ")
    assert RecordingTerminal.writes[0][1] is True


def test_plain_console_terminal_removed_after_last_unregister(qtbot):
    widget = BecConsole(client=mocked_client, gui_id="plain_console", terminal_id="plain_terminal")
    qtbot.addWidget(widget)

    assert "plain_terminal" in _bec_console_registry._terminal_registry
    _bec_console_registry.unregister(widget)

    assert "plain_terminal" not in _bec_console_registry._terminal_registry


def test_bec_qterm_clipboard_shortcuts_call_terminal_clipboard_methods(qtbot):
    term = BecQTerm()
    qtbot.addWidget(term)

    with (
        mock.patch.object(term, "_copyClipboard") as mock_copy,
        mock.patch.object(term, "_pasteClipboard") as mock_paste,
    ):
        term._clipboard_shortcuts["copy"].activated.emit()
        term._clipboard_shortcuts["paste"].activated.emit()

    mock_copy.assert_called_once_with()
    mock_paste.assert_called_once_with()
