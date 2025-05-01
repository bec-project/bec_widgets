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
    assert "gui.bec.panels" in completer.all_completions("gui.bec.pan")
