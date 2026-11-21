"""
Test module for the gui object within the BEC IPython client.
"""

from unittest import mock

import IPython
import pytest


@pytest.fixture
def bec_ipython_shell(connected_client_gui_obj, bec_client_lib):
    with mock.patch("IPython.core.history.HistoryManager.enabled", False):
        shell = IPython.terminal.interactiveshell.TerminalInteractiveShell.instance()  # type: ignore
        shell.user_ns["dev"] = bec_client_lib.device_manager.devices
        shell.user_ns["gui"] = connected_client_gui_obj
        completer = IPython.get_ipython().Completer  # type: ignore
        yield shell, completer


def test_ipython_tab_completion(bec_ipython_shell):
    _, completer = bec_ipython_shell
    assert "gui.bec" in completer.all_completions("gui.")
    assert "gui.bec.new" in completer.all_completions("gui.bec.")
    assert "gui.bec.widget_list" in completer.all_completions("gui.bec.widget_")


def test_gui_visibility_and_display_info(connected_client_gui_obj):
    gui = connected_client_gui_obj
    flomni = gui.new("flomni", startup_profile="skip")

    info = gui.get_display_info()
    assert info["pid"] == gui._process.pid
    assert info["qt_platform"]

    def flomni_state():
        return next(
            window
            for window in gui.get_display_info()["windows"]
            if window["title"] == "BEC - flomni"
        )

    flags = flomni_state()["flags"]
    for show_window in (gui.show, gui.raise_window, flomni.raise_window):
        flomni.hide()
        assert not flomni_state()["visible"]
        for _ in range(3):
            show_window()
            state = flomni_state()
            assert state["visible"]
            assert state["flags"] == flags
