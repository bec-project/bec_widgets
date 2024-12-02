import inspect
from unittest import mock

import pytest
from qtpy.QtWidgets import QLabel

from bec_widgets.widgets.editors.user_script.user_script import UserScriptWidget

from .client_mocks import mocked_client


def dummy_script():
    pass


def dummy_script_with_args(arg1: str, arg2: int = 0):
    pass


@pytest.fixture
def SCRIPTS(tmp_path):
    """Create dummy script files"""
    home_script = f"{tmp_path}/dummy_path_home_scripts/home_testing.py"
    bec_script = f"{tmp_path}/dummy_path_bec_lib_scripts/bec_testing.py"
    rtr = {
        "dummy_script": {"cls": dummy_script, "fname": home_script},
        "dummy_script_with_args": {"cls": dummy_script_with_args, "fname": bec_script},
    }
    return rtr


@pytest.fixture
def user_script_widget(SCRIPTS, qtbot, mocked_client):
    mocked_client._scripts = SCRIPTS
    files = {
        "USER": [SCRIPTS["dummy_script"]["fname"]],
        "BEC": [SCRIPTS["dummy_script_with_args"]["fname"]],
    }
    with mock.patch(
        "bec_widgets.widgets.editors.user_script.user_script.UserScriptWidget.get_script_files",
        return_value=files,
    ):
        with mock.patch("bec_widgets.widgets.editors.user_script.user_script", "BECConsole"):
            with mock.patch("bec_widgets.widgets.editors.user_script.user_script", "VSCodeEditor"):
                widget = UserScriptWidget(client=mocked_client)
                qtbot.addWidget(widget)
                qtbot.waitExposed(widget)
                yield widget


def test_user_script_widget_start_up(SCRIPTS, user_script_widget):
    """Test init the user_script widget with dummy scripts from above"""
    assert user_script_widget.tree_widget.columnCount() == 2
    assert len(user_script_widget.tree_widget.children()[0].children()) == 6
    assert user_script_widget.user_scripts["home_testing"].location == "USER"
    assert user_script_widget.user_scripts["home_testing"].module_name == "home_testing"
    assert user_script_widget.user_scripts["home_testing"].fname == SCRIPTS["dummy_script"]["fname"]
    assert user_script_widget.user_scripts["home_testing"].user_script_name == dummy_script.__name__

    assert user_script_widget.user_scripts["bec_testing"].location == "BEC"
    assert user_script_widget.user_scripts["bec_testing"].module_name == "bec_testing"
    assert (
        user_script_widget.user_scripts["bec_testing"].fname
        == SCRIPTS["dummy_script_with_args"]["fname"]
    )
    assert (
        user_script_widget.user_scripts["bec_testing"].user_script_name
        == dummy_script_with_args.__name__
    )
    for label in user_script_widget.tree_widget.children()[0].findChildren(QLabel):
        assert label.text() in [
            "home_testing",
            "bec_testing",
            "dummy_script",
            "dummy_script_with_args",
        ]


def test_handle_open_script(SCRIPTS, user_script_widget):
    """Test handling open script"""
    with mock.patch.object(user_script_widget, "open_script") as mock_open_script:
        user_script_widget.handle_edit_button_clicked("home_testing")
        fp = SCRIPTS["dummy_script"]["fname"]
        mock_open_script.assert_called_once_with(fp)


def test_open_script(user_script_widget):
    """Test opening script"""
    assert user_script_widget._code_dialog is None
    # Override the _vscode_ed
    with mock.patch.object(user_script_widget._vscode_editor, "show") as mock_show:
        with mock.patch.object(user_script_widget._vscode_editor, "open_file") as mock_open_file:
            with mock.patch.object(user_script_widget._vscode_editor, "zen_mode") as mock_zen_mode:
                user_script_widget.open_script("/dummy_path_home_scripts/home_testing.py")
                mock_show.assert_called_once()
                mock_open_file.assert_called_once_with("/dummy_path_home_scripts/home_testing.py")
                mock_zen_mode.assert_called_once()
                assert user_script_widget._code_dialog is not None


def test_play_button(user_script_widget):
    """Test play button"""
    with mock.patch.object(user_script_widget, "_console") as mock_console:
        with mock.patch.object(user_script_widget, "_handle_call_with_args") as mock_handle_call:
            # Test first with no args
            user_script_widget.handle_play_button_clicked("dummy_script")
            mock_console.execute_command.caller_args == [
                mock.call("bec.load_all_user_scripts()"),
                mock.call("dummy_script()"),
            ]
            assert user_script_widget._script_dialog is None

            # Test with args
            user_script_widget.handle_play_button_clicked("dummy_script_with_args")
            caller_args = inspect.getfullargspec(dummy_script_with_args)
            assert mock_handle_call.call_args == mock.call("dummy_script_with_args", caller_args)
