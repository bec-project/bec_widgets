# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring

import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest
from qtpy.Qsci import QsciScintilla
from qtpy.QtWidgets import QTextEdit

from bec_widgets.widgets.editor.editor import AutoCompleter, BECEditor


@pytest.fixture(scope="function")
def editor(qtbot, docstring_tooltip=False):
    """Helper function to set up the BECEditor widget."""
    widget = BECEditor(toolbar_enabled=True, docstring_tooltip=docstring_tooltip)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def find_action_by_text(toolbar, text):
    """Helper function to find an action in the toolbar by its text."""
    for action in toolbar.actions():
        if action.text() == text:
            return action
    return None


def test_bec_editor_initialization(editor):
    """Test if the BECEditor widget is initialized correctly."""
    assert isinstance(editor.editor, QsciScintilla)
    assert isinstance(editor.terminal, QTextEdit)
    assert isinstance(editor.auto_completer, AutoCompleter)


@patch("bec_widgets.widgets.editor.editor.Script")  # Mock the Script class from jedi
def test_autocompleter_suggestions(mock_script, editor, qtbot):
    """Test if the autocompleter provides correct suggestions based on input."""
    # Set up mock return values for the Script.complete method
    mock_completion = MagicMock()
    mock_completion.name = "mocked_method"
    mock_script.return_value.complete.return_value = [mock_completion]

    # Simulate user input in the editor
    test_code = "print("
    editor.editor.setText(test_code)
    line, index = editor.editor.getCursorPosition()

    # Trigger autocomplete
    editor.auto_completer.get_completions(line, index, test_code)

    # Use qtbot to wait for the completion thread
    qtbot.waitUntil(lambda: editor.auto_completer.completions is not None, timeout=1000)

    # Check if the expected completion is in the autocompleter's suggestions
    suggested_methods = [completion.name for completion in editor.auto_completer.completions]
    assert "mocked_method" in suggested_methods


@patch("bec_widgets.widgets.editor.editor.Script")  # Mock the Script class from jedi
@pytest.mark.parametrize(
    "docstring_enabled, expected_signature",
    [(True, "Mocked signature with docstring"), (False, "Mocked signature")],
)
def test_autocompleter_signature(mock_script, editor, docstring_enabled, expected_signature):
    """Test if the autocompleter provides correct function signature based on docstring setting."""
    # Set docstring mode based on parameter
    editor.docstring_tooltip = docstring_enabled
    editor.auto_completer.enable_docstring = docstring_enabled

    # Set up mock return values for the Script.get_signatures method
    mock_signature = MagicMock()
    if docstring_enabled:
        mock_signature.docstring.return_value = expected_signature
    else:
        mock_signature.to_string.return_value = expected_signature
    mock_script.return_value.get_signatures.return_value = [mock_signature]

    # Simulate user input that would trigger a signature request
    test_code = "print("
    editor.editor.setText(test_code)
    line, index = editor.editor.getCursorPosition()

    # Trigger signature request
    signature = editor.auto_completer.get_function_signature(line, index, test_code)

    # Check if the expected signature is returned
    assert signature == expected_signature


def test_open_file(editor):
    """Test open_file method of BECEditor."""
    # Create a temporary file with some content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as temp_file:
        temp_file.write(b"test file content")

    # Mock user selecting the file in the dialog
    with patch("qtpy.QtWidgets.QFileDialog.getOpenFileName", return_value=(temp_file.name, "")):
        with patch("builtins.open", new_callable=mock_open, read_data="test file content"):
            editor.open_file()

            # Verify if the editor's text is set to the file content
            assert editor.editor.text() == "test file content"

    # Clean up by removing the temporary file
    os.remove(temp_file.name)


def test_save_file(editor):
    """Test save_file method of BECEditor."""
    # Set some text in the editor
    editor.editor.setText("test save content")

    # Mock user selecting the file in the dialog
    with patch(
        "qtpy.QtWidgets.QFileDialog.getSaveFileName", return_value=("/path/to/save/file.py", "")
    ):
        with patch("builtins.open", new_callable=mock_open) as mock_file:
            editor.save_file()

            # Verify if the file was opened correctly for writing
            mock_file.assert_called_with("/path/to/save/file.py", "w")

            # Verify if the editor's text was written to the file
            mock_file().write.assert_called_with("test save content")


def test_open_file_through_toolbar(editor):
    """Test the open_file method through the ModularToolBar."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as temp_file:
        temp_file.write(b"test file content")

    # Find the open file action in the toolbar
    open_action = find_action_by_text(editor.toolbar, "Open File")
    assert open_action is not None, "Open File action should be found"

    # Mock the file dialog and built-in open function
    with patch("qtpy.QtWidgets.QFileDialog.getOpenFileName", return_value=(temp_file.name, "")):
        with patch("builtins.open", new_callable=mock_open, read_data="test file content"):
            open_action.trigger()
            # Verify if the editor's text is set to the file content
            assert editor.editor.text() == "test file content"

    # Clean up
    os.remove(temp_file.name)


def test_save_file_through_toolbar(editor):
    """Test the save_file method through the ModularToolBar."""
    # Set some text in the editor
    editor.editor.setText("test save content")

    # Find the save file action in the toolbar
    save_action = find_action_by_text(editor.toolbar, "Save File")
    assert save_action is not None, "Save File action should be found"

    # Mock the file dialog and built-in open function
    with patch(
        "qtpy.QtWidgets.QFileDialog.getSaveFileName", return_value=("/path/to/save/file.py", "")
    ):
        with patch("builtins.open", new_callable=mock_open) as mock_file:
            save_action.trigger()
            # Verify if the file was opened correctly for writing
            mock_file.assert_called_with("/path/to/save/file.py", "w")

            # Verify if the editor's text was written to the file
            mock_file().write.assert_called_with("test save content")
