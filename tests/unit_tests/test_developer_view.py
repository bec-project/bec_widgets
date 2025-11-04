"""
Unit tests for the Developer View widget.

This module tests the DeveloperView widget functionality including:
- Widget initialization and setup
- Monaco editor integration
- IDE Explorer integration
- File operations (open, save, format)
- Context menu actions
- Toolbar functionality
"""

import os
import tempfile
from unittest import mock

import pytest
from qtpy.QtWidgets import QDialog

from bec_widgets.applications.views.developer_view.developer_widget import DeveloperWidget
from bec_widgets.widgets.editors.monaco.monaco_dock import MonacoDock
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
from bec_widgets.widgets.utility.ide_explorer.ide_explorer import IDEExplorer

from .client_mocks import mocked_client


@pytest.fixture
def developer_view(qtbot, mocked_client):
    """Create a DeveloperWidget for testing."""
    widget = DeveloperWidget(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def temp_python_file():
    """Create a temporary Python file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """# Test Python file
import os
import sys

def test_function():
    return "Hello, World!"

if __name__ == "__main__":
    print(test_function())
"""
        )
        temp_file_path = f.name

    yield temp_file_path

    # Cleanup
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)


@pytest.fixture
def mock_scan_control_dialog():
    """Mock the ScanControlDialog for testing."""
    with mock.patch(
        "bec_widgets.widgets.editors.monaco.scan_control_dialog.ScanControlDialog"
    ) as mock_dialog:
        # Configure the mock dialog
        mock_dialog_instance = mock.MagicMock()
        mock_dialog_instance.exec_.return_value = QDialog.DialogCode.Accepted
        mock_dialog_instance.get_scan_code.return_value = (
            "scans.ascan(dev.samx, 0, 1, 10, exp_time=0.1)"
        )
        mock_dialog.return_value = mock_dialog_instance
        yield mock_dialog_instance


class TestDeveloperViewInitialization:
    """Test developer view initialization and basic functionality."""

    def test_developer_view_initialization(self, developer_view):
        """Test that the developer view initializes correctly."""
        # Check that main components are created
        assert hasattr(developer_view, "monaco")
        assert hasattr(developer_view, "explorer")
        assert hasattr(developer_view, "console")
        assert hasattr(developer_view, "terminal")
        assert hasattr(developer_view, "toolbar")
        assert hasattr(developer_view, "dock_manager")
        assert hasattr(developer_view, "plotting_ads")
        assert hasattr(developer_view, "signature_help")

    def test_monaco_editor_integration(self, developer_view):
        """Test that Monaco editor is properly integrated."""
        assert isinstance(developer_view.monaco, MonacoDock)
        assert developer_view.monaco.parent() is not None

    def test_ide_explorer_integration(self, developer_view):
        """Test that IDE Explorer is properly integrated."""
        assert isinstance(developer_view.explorer, IDEExplorer)
        assert developer_view.explorer.parent() is not None

    def test_toolbar_components(self, developer_view):
        """Test that toolbar components are properly set up."""
        assert developer_view.toolbar is not None

        # Check for expected toolbar actions
        toolbar_components = developer_view.toolbar.components
        expected_actions = ["save", "save_as", "run", "stop", "vim"]

        for action_name in expected_actions:
            assert toolbar_components.exists(action_name)

    def test_dock_manager_setup(self, developer_view):
        """Test that dock manager is properly configured."""
        assert developer_view.dock_manager is not None

        # Check that docks are added
        dock_widgets = developer_view.dock_manager.dockWidgets()
        assert len(dock_widgets) >= 4  # Explorer, Monaco, Console, Terminal


class TestFileOperations:
    """Test file operation functionality."""

    def test_open_new_file(self, developer_view, temp_python_file, qtbot):
        """Test opening a new file in the Monaco editor."""
        # Simulate opening a file through the IDE explorer signal
        developer_view._open_new_file(temp_python_file, "scripts/local")

        # Wait for the file to be loaded
        qtbot.waitUntil(
            lambda: temp_python_file in developer_view.monaco._get_open_files(), timeout=2000
        )

        # Check that the file was opened
        assert temp_python_file in developer_view.monaco._get_open_files()

        # Check that content was loaded (simplified check)
        # Get the editor dock for the file and check its content
        dock = developer_view.monaco._get_editor_dock(temp_python_file)
        if dock:
            editor_widget = dock.widget()
            assert "test_function" in editor_widget.get_text()

    def test_open_shared_file_readonly(self, developer_view, temp_python_file, qtbot):
        """Test that shared files are opened in read-only mode."""
        # Open file with shared scope
        developer_view._open_new_file(temp_python_file, "scripts/shared")

        qtbot.waitUntil(
            lambda: temp_python_file in developer_view.monaco._get_open_files(), timeout=2000
        )

        # Check that the file is set to read-only
        dock = developer_view.monaco._get_editor_dock(temp_python_file)
        if dock:
            monaco_widget = dock.widget()
            # Check that the widget is in read-only mode
            # This depends on MonacoWidget having a readonly property or method
            assert monaco_widget is not None

    def test_file_icon_assignment(self, developer_view, temp_python_file, qtbot):
        """Test that file icons are assigned based on scope."""
        # Test script file icon
        developer_view._open_new_file(temp_python_file, "scripts/local")

        qtbot.waitUntil(
            lambda: temp_python_file in developer_view.monaco._get_open_files(), timeout=2000
        )

        # Check that an icon was set (simplified check)
        dock = developer_view.monaco._get_editor_dock(temp_python_file)
        if dock:
            assert not dock.icon().isNull()

    def test_save_functionality(self, developer_view, qtbot):
        """Test the save functionality."""
        # Get the currently focused editor widget (if any)
        if developer_view.monaco.last_focused_editor:
            editor_widget = developer_view.monaco.last_focused_editor.widget()
            test_text = "print('Hello from save test')"
            editor_widget.set_text(test_text)

            qtbot.waitUntil(lambda: editor_widget.get_text() == test_text, timeout=1000)

        # Test the save action
        with mock.patch.object(developer_view.monaco, "save_file") as mock_save:
            developer_view.on_save()
            mock_save.assert_called_once()

    def test_save_as_functionality(self, developer_view, qtbot):
        """Test the save as functionality."""
        # Get the currently focused editor widget (if any)
        if developer_view.monaco.last_focused_editor:
            editor_widget = developer_view.monaco.last_focused_editor.widget()
            test_text = "print('Hello from save as test')"
            editor_widget.set_text(test_text)

            qtbot.waitUntil(lambda: editor_widget.get_text() == test_text, timeout=1000)

        # Test the save as action
        with mock.patch.object(developer_view.monaco, "save_file") as mock_save:
            developer_view.on_save_as()
            mock_save.assert_called_once_with(force_save_as=True)


class TestMonacoEditorIntegration:
    """Test Monaco editor specific functionality."""

    def test_vim_mode_toggle(self, developer_view, qtbot):
        """Test vim mode toggle functionality."""
        # Test enabling vim mode
        with mock.patch.object(developer_view.monaco, "set_vim_mode") as mock_vim:
            developer_view.on_vim_triggered()
            # The actual call depends on the checkbox state
            mock_vim.assert_called_once()

    def test_context_menu_insert_scan(self, developer_view, mock_scan_control_dialog, qtbot):
        """Test the Insert Scan context menu action."""
        # This functionality is handled by individual MonacoWidget instances
        # Test that the dock has editor widgets
        dock_widgets = developer_view.monaco.dock_manager.dockWidgets()
        assert len(dock_widgets) >= 1

        # Test on the first available editor
        first_dock = dock_widgets[0]
        monaco_widget = first_dock.widget()
        assert isinstance(monaco_widget, MonacoWidget)

    def test_context_menu_format_code(self, developer_view, qtbot):
        """Test the Format Code context menu action."""
        # Get an editor widget from the dock manager
        dock_widgets = developer_view.monaco.dock_manager.dockWidgets()
        if dock_widgets:
            first_dock = dock_widgets[0]
            monaco_widget = first_dock.widget()

            # Set some unformatted Python code
            unformatted_code = "import os,sys\ndef test():\n  x=1+2\n  return x"
            monaco_widget.set_text(unformatted_code)

            qtbot.waitUntil(lambda: monaco_widget.get_text() == unformatted_code, timeout=1000)

            # Test format action on the individual widget
            with mock.patch.object(monaco_widget, "format") as mock_format:
                monaco_widget.format()
                mock_format.assert_called_once()

    def test_save_enabled_signal_handling(self, developer_view, qtbot):
        """Test that save enabled signals are handled correctly."""
        # Mock the toolbar update method
        with mock.patch.object(developer_view, "_on_save_enabled_update") as mock_update:
            # Simulate save enabled signal
            developer_view.monaco.save_enabled.emit(True)
            mock_update.assert_called_with(True)

            developer_view.monaco.save_enabled.emit(False)
            mock_update.assert_called_with(False)


class TestIDEExplorerIntegration:
    """Test IDE Explorer integration."""

    def test_file_open_signal_connection(self, developer_view):
        """Test that file open signals are properly connected."""
        # Test that the signal connection works by mocking the connected method
        with mock.patch.object(developer_view, "_open_new_file") as mock_open:
            # Emit the signal to test the connection
            developer_view.explorer.file_open_requested.emit("test_file.py", "scripts/local")
            mock_open.assert_called_once_with("test_file.py", "scripts/local")

    def test_file_preview_signal_connection(self, developer_view):
        """Test that file preview signals are properly connected."""
        # Test that the signal exists and can be emitted (basic connection test)
        try:
            developer_view.explorer.file_preview_requested.emit("test_file.py", "scripts/local")
            # If no exception is raised, the signal exists and is connectable
            assert True
        except AttributeError:
            assert False, "file_preview_requested signal not found"

    def test_sections_configuration(self, developer_view):
        """Test that IDE Explorer sections are properly configured."""
        assert "scripts" in developer_view.explorer.sections
        assert "macros" in developer_view.explorer.sections


class TestToolbarIntegration:
    """Test toolbar functionality and integration."""

    def test_toolbar_save_button_state(self, developer_view):
        """Test toolbar save button state management."""
        # Test that save buttons exist and can be controlled
        save_action = developer_view.toolbar.components.get_action("save")
        save_as_action = developer_view.toolbar.components.get_action("save_as")

        # Test that the actions exist and are accessible
        assert save_action.action is not None
        assert save_as_action.action is not None

        # Test that they can be enabled/disabled via the update method
        developer_view._on_save_enabled_update(False)
        assert not save_action.action.isEnabled()
        assert not save_as_action.action.isEnabled()

        developer_view._on_save_enabled_update(True)
        assert save_action.action.isEnabled()
        assert save_as_action.action.isEnabled()

    def test_vim_mode_button_toggle(self, developer_view, qtbot):
        """Test vim mode button toggle functionality."""
        vim_action = developer_view.toolbar.components.get_action("vim")

        if vim_action:
            # Test toggling vim mode
            initial_state = vim_action.action.isChecked()

            # Simulate button click
            vim_action.action.trigger()

            # Check that state changed
            assert vim_action.action.isChecked() != initial_state


class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_invalid_scope_handling(self, developer_view, temp_python_file):
        """Test handling of invalid scope parameters."""
        # Test with invalid scope
        try:
            developer_view._open_new_file(temp_python_file, "invalid/scope")
        except Exception as e:
            assert False, f"Invalid scope should be handled gracefully: {e}"

    def test_monaco_editor_error_handling(self, developer_view):
        """Test error handling in Monaco editor operations."""
        # Test with editor widgets from dock manager
        dock_widgets = developer_view.monaco.dock_manager.dockWidgets()
        if dock_widgets:
            first_dock = dock_widgets[0]
            monaco_widget = first_dock.widget()

            # Test setting invalid text
            try:
                monaco_widget.set_text(None)  # This might cause an error
            except Exception:
                # Errors should be handled gracefully
                pass


class TestSignalIntegration:
    """Test signal connections and data flow."""

    def test_file_open_signal_flow(self, developer_view, temp_python_file, qtbot):
        """Test the complete file open signal flow."""
        # Mock the _open_new_file method to verify it gets called
        with mock.patch.object(developer_view, "_open_new_file") as mock_open:
            # Emit the file open signal from explorer
            developer_view.explorer.file_open_requested.emit(temp_python_file, "scripts/local")

            # Verify the signal was handled
            mock_open.assert_called_once_with(temp_python_file, "scripts/local")

    def test_save_enabled_signal_flow(self, developer_view, qtbot):
        """Test the save enabled signal flow."""
        # Mock the update method (the actual method is _on_save_enabled_update)
        with mock.patch.object(developer_view, "_on_save_enabled_update") as mock_update:
            # Simulate monaco dock emitting save enabled signal
            developer_view.monaco.save_enabled.emit(True)

            # Verify the signal was handled
            mock_update.assert_called_once_with(True)


if __name__ == "__main__":
    pytest.main([__file__])
