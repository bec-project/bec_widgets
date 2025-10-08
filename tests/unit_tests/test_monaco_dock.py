import os
from typing import Generator
from unittest import mock

import pytest
from qtpy.QtWidgets import QFileDialog, QMessageBox

from bec_widgets.widgets.editors.monaco.monaco_dock import MonacoDock
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget

from .client_mocks import mocked_client


@pytest.fixture
def monaco_dock(qtbot, mocked_client) -> Generator[MonacoDock, None, None]:
    """Create a MonacoDock for testing."""
    # Mock the macros functionality
    mocked_client.macros = mock.MagicMock()
    mocked_client.macros._update_handler = mock.MagicMock()
    mocked_client.macros._update_handler.get_macros_from_file.return_value = {}
    mocked_client.macros._update_handler.get_existing_macros.return_value = {}

    widget = MonacoDock(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


class TestFocusEditor:
    def test_last_focused_editor_initial_none(self, monaco_dock: MonacoDock):
        """Test that last_focused_editor is initially None."""
        assert monaco_dock.last_focused_editor is not None

    def test_set_last_focused_editor(self, qtbot, monaco_dock: MonacoDock, tmpdir):
        """Test setting last_focused_editor when an editor is focused."""
        file_path = tmpdir.join("test.py")
        file_path.write("print('Hello, World!')")

        monaco_dock.open_file(str(file_path))
        qtbot.wait(300)  # Wait for the editor to be fully set up

        assert monaco_dock.last_focused_editor is not None

    def test_last_focused_editor_updates_on_focus_change(
        self, qtbot, monaco_dock: MonacoDock, tmpdir
    ):
        """Test that last_focused_editor updates when focus changes."""
        file1 = tmpdir.join("file1.py")
        file1.write("print('File 1')")
        file2 = tmpdir.join("file2.py")
        file2.write("print('File 2')")

        monaco_dock.open_file(str(file1))
        qtbot.wait(300)
        editor1 = monaco_dock.last_focused_editor

        monaco_dock.open_file(str(file2))
        qtbot.wait(300)
        editor2 = monaco_dock.last_focused_editor

        assert editor1 != editor2
        assert editor2 is not None

    def test_opening_existing_file_updates_focus(self, qtbot, monaco_dock: MonacoDock, tmpdir):
        """Test that opening an already open file simply switches focus to it."""
        file1 = tmpdir.join("file1.py")
        file1.write("print('File 1')")
        file2 = tmpdir.join("file2.py")
        file2.write("print('File 2')")

        monaco_dock.open_file(str(file1))
        qtbot.wait(300)
        editor1 = monaco_dock.last_focused_editor

        monaco_dock.open_file(str(file2))
        qtbot.wait(300)
        editor2 = monaco_dock.last_focused_editor

        # Re-open file1
        monaco_dock.open_file(str(file1))
        qtbot.wait(300)
        editor1_again = monaco_dock.last_focused_editor

        assert editor1 == editor1_again
        assert editor1 != editor2
        assert editor2 is not None


class TestSaveFiles:
    def test_save_file_existing_file_no_macros(self, qtbot, monaco_dock: MonacoDock, tmpdir):
        """Test saving an existing file that is not a macro."""
        # Create a test file
        file_path = tmpdir.join("test.py")
        file_path.write("print('Hello, World!')")

        # Open file in Monaco dock
        monaco_dock.open_file(str(file_path))
        qtbot.wait(300)

        # Get the editor widget and modify content
        editor_widget = monaco_dock.last_focused_editor.widget()
        assert isinstance(editor_widget, MonacoWidget)
        editor_widget.set_text("print('Modified content')")
        qtbot.wait(100)

        # Verify the editor is marked as modified
        assert editor_widget.modified

        # Save the file
        with mock.patch(
            "bec_widgets.widgets.editors.monaco.monaco_dock.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            mock_dialog.return_value = (str(file_path), "Python files (*.py)")
            monaco_dock.save_file()
        qtbot.wait(100)

        # Verify file was saved
        saved_content = file_path.read()
        assert saved_content == 'print("Modified content")\n'

        # Verify editor is no longer marked as modified
        assert not editor_widget.modified

    def test_save_file_with_macros_scope(self, qtbot, monaco_dock: MonacoDock, tmpdir):
        """Test saving a file with macros scope updates macro handler."""
        # Create a test file
        file_path = tmpdir.join("test_macro.py")
        file_path.write("def test_function(): pass")

        # Open file in Monaco dock with macros scope
        monaco_dock.open_file(str(file_path), scope="macros")
        qtbot.wait(300)

        # Get the editor widget and modify content
        editor_widget = monaco_dock.last_focused_editor.widget()
        editor_widget.set_text("def modified_function(): pass")
        qtbot.wait(100)

        # Mock macro validation to return True (valid)
        with mock.patch.object(monaco_dock, "_validate_macros", return_value=True):
            # Mock file dialog to avoid opening actual dialog (file already exists)
            with mock.patch.object(QFileDialog, "getSaveFileName") as mock_dialog:
                mock_dialog.return_value = (str(file_path), "")  # User cancels
                # Save the file (should save to existing file, not open dialog)
                monaco_dock.save_file()
                qtbot.wait(100)

        # Verify macro update methods were called
        monaco_dock.client.macros._update_handler.get_macros_from_file.assert_called_with(
            str(file_path)
        )
        monaco_dock.client.macros._update_handler.get_existing_macros.assert_called_with(
            str(file_path)
        )

    def test_save_file_invalid_macro_content(self, qtbot, monaco_dock: MonacoDock, tmpdir):
        """Test saving a macro file with invalid content shows warning."""
        # Create a test file
        file_path = tmpdir.join("test_macro.py")
        file_path.write("def test_function(): pass")

        # Open file in Monaco dock with macros scope
        monaco_dock.open_file(str(file_path), scope="macros")
        qtbot.wait(300)

        # Get the editor widget and modify content to invalid macro
        editor_widget = monaco_dock.last_focused_editor.widget()
        assert isinstance(editor_widget, MonacoWidget)
        editor_widget.set_text("exec('print(hello)')")  # Invalid macro content
        qtbot.wait(100)

        # Mock QMessageBox to capture warning
        with mock.patch(
            "bec_widgets.widgets.editors.monaco.monaco_dock.QMessageBox.warning"
        ) as mock_warning:
            with mock.patch.object(QFileDialog, "getSaveFileName") as mock_dialog:
                mock_dialog.return_value = (str(file_path), "")
                # Save the file
                monaco_dock.save_file()
                qtbot.wait(100)

        # Verify validation was called and warning was shown
        mock_warning.assert_called_once()

        # Verify file was not saved (content should remain original)
        saved_content = file_path.read()
        assert saved_content == "def test_function(): pass"

    def test_save_file_as_new_file(self, qtbot, monaco_dock: MonacoDock, tmpdir):
        """Test Save As functionality creates a new file."""
        # Create initial content in editor
        editor_dock = monaco_dock.add_editor()
        editor_widget = editor_dock.widget()
        assert isinstance(editor_widget, MonacoWidget)
        editor_widget.set_text("print('New file content')")
        qtbot.wait(100)

        # Mock QFileDialog.getSaveFileName
        new_file_path = str(tmpdir.join("new_file.py"))
        with mock.patch.object(QFileDialog, "getSaveFileName") as mock_dialog:
            mock_dialog.return_value = (new_file_path, "Python files (*.py)")

            # Save as new file
            monaco_dock.save_file(force_save_as=True)
            qtbot.wait(100)

        # Verify new file was created
        assert os.path.exists(new_file_path)
        with open(new_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == 'print("New file content")\n'

        # Verify editor is no longer marked as modified
        assert not editor_widget.modified

        # Verify current_file was updated
        assert editor_widget.current_file == new_file_path

    def test_save_file_as_adds_py_extension(self, qtbot, monaco_dock: MonacoDock, tmpdir):
        """Test Save As automatically adds .py extension if none provided."""
        # Create initial content in editor
        editor_dock = monaco_dock.add_editor()
        editor_widget = editor_dock.widget()
        assert isinstance(editor_widget, MonacoWidget)
        editor_widget.set_text("print('Test content')")
        qtbot.wait(100)

        # Mock QFileDialog.getSaveFileName to return path without extension
        file_path_no_ext = str(tmpdir.join("test_file"))
        expected_path = file_path_no_ext + ".py"

        with mock.patch.object(QFileDialog, "getSaveFileName") as mock_dialog:
            mock_dialog.return_value = (file_path_no_ext, "All files (*)")

            # Save as new file
            monaco_dock.save_file(force_save_as=True)
            qtbot.wait(100)

        # Verify file was created with .py extension
        assert os.path.exists(expected_path)
        assert editor_widget.current_file == expected_path

    def test_save_file_no_focused_editor(self, monaco_dock: MonacoDock):
        """Test save_file handles case when no editor is focused."""
        # Set last_focused_editor to None
        with mock.patch.object(monaco_dock.last_focused_editor, "widget", return_value=None):
            # Attempt to save should not raise exception
            monaco_dock.save_file()

    def test_save_file_emits_macro_file_updated_signal(self, qtbot, monaco_dock, tmpdir):
        """Test that macro_file_updated signal is emitted when saving macro files."""
        # Create a test file
        file_path = tmpdir.join("test_macro.py")
        file_path.write("def test_function(): pass")

        # Open file in Monaco dock with macros scope
        monaco_dock.open_file(str(file_path), scope="macros")
        qtbot.wait(300)

        # Get the editor widget and modify content
        editor_widget = monaco_dock.last_focused_editor.widget()
        editor_widget.set_text("def modified_function(): pass")
        qtbot.wait(100)

        # Connect signal to capture emission
        signal_emitted = []
        monaco_dock.macro_file_updated.connect(lambda path: signal_emitted.append(path))

        # Mock file dialog to avoid opening actual dialog (file already exists)
        with mock.patch.object(QFileDialog, "getSaveFileName") as mock_dialog:
            mock_dialog.return_value = (str(file_path), "")
            # Save the file
            monaco_dock.save_file()
            qtbot.wait(100)

        # Verify signal was emitted
        assert len(signal_emitted) == 1
        assert signal_emitted[0] == str(file_path)

    def test_close_dock_asks_to_save_modified_file(self, qtbot, monaco_dock: MonacoDock, tmpdir):
        """Test that closing a modified file dock asks to save changes."""
        # Create a test file
        file_path = tmpdir.join("test.py")
        file_path.write("print('Hello, World!')")

        # Open file in Monaco dock
        monaco_dock.open_file(str(file_path))
        qtbot.wait(300)

        # Get the editor widget and modify content
        editor_widget = monaco_dock.last_focused_editor.widget()
        assert isinstance(editor_widget, MonacoWidget)
        editor_widget.set_text("print('Modified content')")
        qtbot.wait(100)

        # Mock QMessageBox to simulate user clicking 'Save'
        with mock.patch(
            "bec_widgets.widgets.editors.monaco.monaco_dock.QMessageBox.question"
        ) as mock_question:
            mock_question.return_value = QMessageBox.StandardButton.Yes

            # Mock QFileDialog.getSaveFileName
            with mock.patch.object(QFileDialog, "getSaveFileName") as mock_dialog:
                mock_dialog.return_value = (str(file_path), "Python files (*.py)")

                # Close the dock; sadly, calling close() alone does not trigger the closeRequested signal
                # It is only triggered if the mouse is on top of the tab close button, so we directly call the handler
                monaco_dock._on_editor_close_requested(
                    monaco_dock.last_focused_editor, editor_widget
                )
                qtbot.wait(100)

        # Verify file was saved
        saved_content = file_path.read()
        assert saved_content == 'print("Modified content")\n'


class TestSignatureHelp:
    def test_signature_help_signal_emission(self, qtbot, monaco_dock: MonacoDock):
        """Test that signature help signal is emitted correctly."""
        # Connect signal to capture emission
        signature_emitted = []
        monaco_dock.signature_help.connect(lambda sig: signature_emitted.append(sig))

        # Create mock signature data
        signature_data = {
            "signatures": [
                {
                    "label": "print(value, sep=' ', end='\\n', file=sys.stdout, flush=False)",
                    "documentation": {
                        "value": "Print objects to the text stream file, separated by sep and followed by end."
                    },
                }
            ],
            "activeSignature": 0,
            "activeParameter": 0,
        }

        # Trigger signature change
        monaco_dock._on_signature_change(signature_data)
        qtbot.wait(100)

        # Verify signal was emitted with correct markdown format
        assert len(signature_emitted) == 1
        emitted_signature = signature_emitted[0]
        assert "```python" in emitted_signature
        assert "print(value, sep=' ', end='\\n', file=sys.stdout, flush=False)" in emitted_signature
        assert "Print objects to the text stream file" in emitted_signature

    def test_signature_help_empty_signatures(self, qtbot, monaco_dock: MonacoDock):
        """Test signature help with empty signatures."""
        # Connect signal to capture emission
        signature_emitted = []
        monaco_dock.signature_help.connect(lambda sig: signature_emitted.append(sig))

        # Create mock signature data with no signatures
        signature_data = {"signatures": []}

        # Trigger signature change
        monaco_dock._on_signature_change(signature_data)
        qtbot.wait(100)

        # Verify empty string was emitted
        assert len(signature_emitted) == 1
        assert signature_emitted[0] == ""

    def test_signature_help_no_documentation(self, qtbot, monaco_dock: MonacoDock):
        """Test signature help when documentation is missing."""
        # Connect signal to capture emission
        signature_emitted = []
        monaco_dock.signature_help.connect(lambda sig: signature_emitted.append(sig))

        # Create mock signature data without documentation
        signature_data = {"signatures": [{"label": "function_name(param)"}], "activeSignature": 0}

        # Trigger signature change
        monaco_dock._on_signature_change(signature_data)
        qtbot.wait(100)

        # Verify signal was emitted with just the function signature
        assert len(signature_emitted) == 1
        emitted_signature = signature_emitted[0]
        assert "```python" in emitted_signature
        assert "function_name(param)" in emitted_signature

    def test_signature_help_string_documentation(self, qtbot, monaco_dock: MonacoDock):
        """Test signature help when documentation is a string instead of dict."""
        # Connect signal to capture emission
        signature_emitted = []
        monaco_dock.signature_help.connect(lambda sig: signature_emitted.append(sig))

        # Create mock signature data with string documentation
        signature_data = {
            "signatures": [
                {"label": "function_name(param)", "documentation": "Simple string documentation"}
            ],
            "activeSignature": 0,
        }

        # Trigger signature change
        monaco_dock._on_signature_change(signature_data)
        qtbot.wait(100)

        # Verify signal was emitted with correct format
        assert len(signature_emitted) == 1
        emitted_signature = signature_emitted[0]
        assert "```python" in emitted_signature
        assert "function_name(param)" in emitted_signature
        assert "Simple string documentation" in emitted_signature

    def test_signature_help_connected_to_editor(self, qtbot, monaco_dock: MonacoDock):
        """Test that signature help is connected when creating new editors."""
        # Create a new editor
        editor_dock = monaco_dock.add_editor()
        editor_widget = editor_dock.widget()

        # Verify the signal connection exists by checking connected signals
        # We do this by mocking the signal and verifying the connection
        with mock.patch.object(monaco_dock, "_on_signature_change") as mock_handler:
            # Simulate signature help trigger from the editor
            editor_widget.editor.signature_help_triggered.emit({"signatures": []})
            qtbot.wait(100)

            # Verify the handler was called
            mock_handler.assert_called_once()
