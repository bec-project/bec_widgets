import os
from pathlib import Path
from unittest import mock

import pytest
from qtpy.QtWidgets import QMessageBox

from bec_widgets.widgets.utility.ide_explorer.ide_explorer import IDEExplorer


@pytest.fixture
def ide_explorer(qtbot, tmpdir):
    """Create an IDEExplorer widget for testing"""
    widget = IDEExplorer()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_ide_explorer_initialization(ide_explorer):
    """Test the initialization of the IDEExplorer widget"""
    assert ide_explorer is not None
    assert "scripts" in ide_explorer.sections
    assert ide_explorer.main_explorer.sections[0].title == "SCRIPTS"


def test_ide_explorer_add_local_script(ide_explorer, qtbot, tmpdir):
    local_script_section = ide_explorer.main_explorer.get_section(
        "SCRIPTS"
    ).content_widget.get_section("Local")
    local_script_section.content_widget.set_directory(str(tmpdir))

    with mock.patch(
        "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QInputDialog.getText",
        return_value=("test_file.py", True),
    ):
        ide_explorer._add_local_script()
        assert os.path.exists(os.path.join(tmpdir, "test_file.py"))


def test_shared_scripts_section_with_files(ide_explorer, tmpdir):
    """Test that shared scripts section is created when plugin directory has files"""
    # Create dummy shared script files
    shared_scripts_dir = tmpdir.mkdir("shared_scripts")
    shared_scripts_dir.join("shared_script1.py").write("# Shared script 1")
    shared_scripts_dir.join("shared_script2.py").write("# Shared script 2")

    ide_explorer.clear()

    with mock.patch.object(ide_explorer, "_get_plugin_dir") as mock_get_plugin_dir:
        mock_get_plugin_dir.return_value = str(shared_scripts_dir)

        ide_explorer.add_script_section()

        scripts_section = ide_explorer.main_explorer.get_section("SCRIPTS")
        assert scripts_section is not None

        # Should have both Local and Shared sections
        local_section = scripts_section.content_widget.get_section("Local")
        shared_section = scripts_section.content_widget.get_section("Shared (Read-only)")

        assert local_section is not None
        assert shared_section is not None
        assert "read-only" in shared_section.toolTip().lower()


def test_shared_macros_section_with_files(ide_explorer, tmpdir):
    """Test that shared macros section is created when plugin directory has files"""
    # Create dummy shared macro files
    shared_macros_dir = tmpdir.mkdir("shared_macros")
    shared_macros_dir.join("shared_macro1.py").write("""
def shared_function1():
    return "shared1"

def shared_function2():
    return "shared2"
""")
    shared_macros_dir.join("utilities.py").write("""
def utility_function():
    return "utility"
""")

    with mock.patch.object(ide_explorer, "_get_plugin_dir") as mock_get_plugin_dir:
        mock_get_plugin_dir.return_value = str(shared_macros_dir)

        ide_explorer.clear()
        ide_explorer.sections = ["macros"]

        macros_section = ide_explorer.main_explorer.get_section("MACROS")
        assert macros_section is not None

        # Should have both Local and Shared sections
        local_section = macros_section.content_widget.get_section("Local")
        shared_section = macros_section.content_widget.get_section("Shared (Read-only)")

        assert local_section is not None
        assert shared_section is not None
        assert "read-only" in shared_section.toolTip().lower()


def test_shared_sections_not_added_when_plugin_dir_missing(ide_explorer):
    """Test that shared sections are not added when plugin directories don't exist"""
    ide_explorer.clear()
    with mock.patch.object(ide_explorer, "_get_plugin_dir") as mock_get_plugin_dir:
        mock_get_plugin_dir.return_value = None

        ide_explorer.add_script_section()

        scripts_section = ide_explorer.main_explorer.get_section("SCRIPTS")
        assert scripts_section is not None

        # Should only have Local section
        local_section = scripts_section.content_widget.get_section("Local")
        shared_section = scripts_section.content_widget.get_section("Shared (Read-only)")

        assert local_section is not None
        assert shared_section is None


def test_shared_sections_not_added_when_directory_empty(ide_explorer, tmpdir):
    """Test that shared sections are not added when plugin directory doesn't exist on disk"""
    ide_explorer.clear()
    # Return a path that doesn't exist
    nonexistent_path = str(tmpdir.join("nonexistent"))

    with mock.patch.object(ide_explorer, "_get_plugin_dir") as mock_get_plugin_dir:
        mock_get_plugin_dir.return_value = nonexistent_path

        ide_explorer.add_script_section()

        scripts_section = ide_explorer.main_explorer.get_section("SCRIPTS")
        assert scripts_section is not None

        # Should only have Local section since directory doesn't exist
        local_section = scripts_section.content_widget.get_section("Local")
        shared_section = scripts_section.content_widget.get_section("Shared (Read-only)")

        assert local_section is not None
        assert shared_section is None


@pytest.mark.parametrize(
    "slot, signal, file_name,scope",
    [
        (
            "_emit_file_open_scripts_local",
            "file_open_requested",
            "example_script.py",
            "scripts/local",
        ),
        (
            "_emit_file_preview_scripts_local",
            "file_preview_requested",
            "example_macro.py",
            "scripts/local",
        ),
        (
            "_emit_file_open_scripts_shared",
            "file_open_requested",
            "example_script.py",
            "scripts/shared",
        ),
        (
            "_emit_file_preview_scripts_shared",
            "file_preview_requested",
            "example_macro.py",
            "scripts/shared",
        ),
    ],
)
def test_ide_explorer_file_signals(ide_explorer, qtbot, slot, signal, file_name, scope):
    """Test that the correct signals are emitted when files are opened or previewed"""
    recv = []

    def recv_file_signal(file_name, scope):
        recv.append((file_name, scope))

    sig = getattr(ide_explorer, signal)
    sig.connect(recv_file_signal)
    # Call the appropriate slot
    getattr(ide_explorer, slot)(file_name)
    qtbot.wait(300)
    # Verify the signal was emitted with correct arguments
    assert recv == [(file_name, scope)]


@pytest.mark.parametrize(
    "slot, signal, func_name, file_path,scope",
    [
        (
            "_emit_file_open_macros_local",
            "file_open_requested",
            "example_macro_function",
            "macros/local/example_macro.py",
            "macros/local",
        ),
        (
            "_emit_file_preview_macros_local",
            "file_preview_requested",
            "example_macro_function",
            "macros/local/example_macro.py",
            "macros/local",
        ),
        (
            "_emit_file_open_macros_shared",
            "file_open_requested",
            "example_macro_function",
            "macros/shared/example_macro.py",
            "macros/shared",
        ),
        (
            "_emit_file_preview_macros_shared",
            "file_preview_requested",
            "example_macro_function",
            "macros/shared/example_macro.py",
            "macros/shared",
        ),
    ],
)
def test_ide_explorer_file_signals_macros(
    ide_explorer, qtbot, slot, signal, func_name, file_path, scope
):
    """Test that the correct signals are emitted when macro files are opened or previewed"""
    recv = []

    def recv_file_signal(file_name, scope):
        recv.append((file_name, scope))

    sig = getattr(ide_explorer, signal)
    sig.connect(recv_file_signal)
    # Call the appropriate slot
    getattr(ide_explorer, slot)(func_name, file_path)
    qtbot.wait(300)
    # Verify the signal was emitted with correct arguments
    assert recv == [(file_path, scope)]


def test_ide_explorer_add_local_macro(ide_explorer, qtbot, tmpdir):
    """Test adding a local macro through the UI"""
    # Create macros section first
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    # Set up the local macro directory
    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    with mock.patch(
        "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QInputDialog.getText",
        return_value=("test_macro_function", True),
    ):
        ide_explorer._add_local_macro()

        # Check that the macro file was created
        expected_file = os.path.join(tmpdir, "test_macro_function.py")
        assert os.path.exists(expected_file)

        # Check that the file contains the expected function
        with open(expected_file, "r") as f:
            content = f.read()
            assert "def test_macro_function():" in content
            assert "test_macro_function macro" in content


def test_ide_explorer_add_local_macro_invalid_name(ide_explorer, qtbot, tmpdir):
    """Test adding a local macro with invalid function name"""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    # Test with invalid function name (starts with number)
    with (
        mock.patch(
            "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QInputDialog.getText",
            return_value=("123invalid", True),
        ),
        mock.patch(
            "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QMessageBox.warning"
        ) as mock_warning,
    ):
        ide_explorer._add_local_macro()

        # Should show warning message
        mock_warning.assert_called_once()

        # Should not create any file
        assert len(os.listdir(tmpdir)) == 0


def test_ide_explorer_add_local_macro_file_exists(ide_explorer, qtbot, tmpdir):
    """Test adding a local macro when file already exists"""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    # Create an existing file
    existing_file = Path(tmpdir) / "existing_macro.py"
    existing_file.write_text("# Existing macro")

    with (
        mock.patch(
            "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QInputDialog.getText",
            return_value=("existing_macro", True),
        ),
        mock.patch(
            "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as mock_question,
    ):
        ide_explorer._add_local_macro()

        # Should ask for overwrite confirmation
        mock_question.assert_called_once()

        # File should be overwritten with new content
        with open(existing_file, "r") as f:
            content = f.read()
            assert "def existing_macro():" in content


def test_ide_explorer_add_local_macro_cancelled(ide_explorer, qtbot, tmpdir):
    """Test cancelling the add local macro dialog"""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    # User cancels the dialog
    with mock.patch(
        "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QInputDialog.getText",
        return_value=("", False),  # User cancelled
    ):
        ide_explorer._add_local_macro()

        # Should not create any file
        assert len(os.listdir(tmpdir)) == 0


def test_ide_explorer_reload_macros_success(ide_explorer, qtbot):
    """Test successful macro reloading"""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    # Mock the client and macros
    mock_client = mock.MagicMock()
    mock_macros = mock.MagicMock()
    mock_client.macros = mock_macros
    ide_explorer.client = mock_client

    with mock.patch(
        "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QMessageBox.information"
    ) as mock_info:
        ide_explorer._reload_macros()

        # Should call load_all_user_macros
        mock_macros.load_all_user_macros.assert_called_once()

        # Should show success message
        mock_info.assert_called_once()
        assert "successfully" in mock_info.call_args[0][2]


def test_ide_explorer_reload_macros_error(ide_explorer, qtbot):
    """Test macro reloading when an error occurs"""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    # Mock client with macros that raises an exception
    mock_client = mock.MagicMock()
    mock_macros = mock.MagicMock()
    mock_macros.load_all_user_macros.side_effect = Exception("Test error")
    mock_client.macros = mock_macros
    ide_explorer.client = mock_client

    with mock.patch(
        "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QMessageBox.critical"
    ) as mock_critical:
        ide_explorer._reload_macros()

        # Should show error message
        mock_critical.assert_called_once()
        assert "Failed to reload macros" in mock_critical.call_args[0][2]


def test_ide_explorer_refresh_macro_file_local(ide_explorer, qtbot, tmpdir):
    """Test refreshing a local macro file"""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    # Set up the local macro directory
    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    # Create a test macro file
    macro_file = Path(tmpdir) / "test_macro.py"
    macro_file.write_text("def test_function(): pass")

    # Mock the refresh_file_item method
    with mock.patch.object(
        local_macros_section.content_widget, "refresh_file_item"
    ) as mock_refresh:
        ide_explorer.refresh_macro_file(str(macro_file))

        # Should call refresh_file_item with the file path
        mock_refresh.assert_called_once_with(str(macro_file))


def test_ide_explorer_refresh_macro_file_no_match(ide_explorer, qtbot, tmpdir):
    """Test refreshing a macro file that doesn't match any directory"""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    # Set up the local macro directory
    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    # Try to refresh a file that's not in any macro directory
    unrelated_file = "/some/other/path/unrelated.py"

    # Mock the refresh_file_item method
    with mock.patch.object(
        local_macros_section.content_widget, "refresh_file_item"
    ) as mock_refresh:
        ide_explorer.refresh_macro_file(unrelated_file)

        # Should not call refresh_file_item
        mock_refresh.assert_not_called()


def test_ide_explorer_refresh_macro_file_no_sections(ide_explorer, qtbot):
    """Test refreshing a macro file when no macro sections exist"""
    ide_explorer.clear()
    # Don't add macros section

    # Should handle gracefully without error
    ide_explorer.refresh_macro_file("/some/path/test.py")
    # Test passes if no exception is raised
