import os
from pathlib import Path
from unittest import mock

import pytest
from qtpy.QtCore import QItemSelectionModel
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


def test_script_section_has_info_tooltip(ide_explorer):
    """Scripts section exposes click-to-open help on the info icon."""
    scripts_section = ide_explorer.main_explorer.get_section("SCRIPTS")

    assert not scripts_section.header_button.toolTip()
    assert not scripts_section.header_info_button.isHidden()
    assert scripts_section.header_info_button.isEnabled()
    assert scripts_section.header_info_button.toolTip() == "Show help"


def test_macro_section_has_info_tooltip(ide_explorer):
    """Macros section exposes click-to-open help on the info icon."""
    macros_section = ide_explorer.main_explorer.get_section("MACROS")

    assert not macros_section.header_button.toolTip()
    assert not macros_section.header_info_button.isHidden()
    assert macros_section.header_info_button.isEnabled()
    assert macros_section.header_info_button.toolTip() == "Show help"


def test_script_section_info_button_opens_help_popup(ide_explorer, qtbot):
    """Clicking the info button should show the styled help popup."""
    scripts_section = ide_explorer.main_explorer.get_section("SCRIPTS")

    scripts_section.header_info_button.click()
    qtbot.waitUntil(
        lambda: scripts_section._help_tooltip is not None
        and scripts_section._help_tooltip.isVisible(),
        timeout=1000,
    )

    assert scripts_section._help_tooltip.content.text().startswith("Scripts are executable")
    scripts_section._cleanup_help_tooltip()


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


def test_file_selection_highlight_is_global_across_scripts_and_macros(ide_explorer, qtbot, tmpdir):
    """Selecting a script file clears the previous macro file highlight."""
    scripts_dir = tmpdir.mkdir("scripts")
    macros_dir = tmpdir.mkdir("macros")
    script_file = scripts_dir.join("script.py")
    macro_file = macros_dir.join("macro.py")
    script_file.write("print('script')")
    macro_file.write("def macro():\n    pass\n")

    scripts_browser = (
        ide_explorer.main_explorer.get_section("SCRIPTS")
        .content_widget.get_section("Local")
        .content_widget
    )
    macros_browser = (
        ide_explorer.main_explorer.get_section("MACROS")
        .content_widget.get_section("Local")
        .content_widget
    )
    scripts_browser.set_directory(str(scripts_dir))
    macros_browser.set_directory(str(macros_dir))

    def get_index(browser, file_name):
        root_index = browser.tree.rootIndex()
        for i in range(browser.proxy_model.rowCount(root_index)):
            index = browser.proxy_model.index(i, 0, root_index)
            if browser.proxy_model.data(index) == file_name:
                return index
        return None

    qtbot.waitUntil(
        lambda: get_index(scripts_browser, "script.py") is not None
        and get_index(macros_browser, "macro.py") is not None,
        timeout=5000,
    )

    macro_index = get_index(macros_browser, "macro.py")
    assert macro_index is not None
    macros_browser.tree.setCurrentIndex(macro_index)
    macros_browser.tree.selectionModel().select(
        macro_index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    macros_browser.file_selected.emit(str(macro_file))

    assert macros_browser.tree.selectionModel().hasSelection()

    script_index = get_index(scripts_browser, "script.py")
    assert script_index is not None
    scripts_browser.tree.setCurrentIndex(script_index)
    scripts_browser.tree.selectionModel().select(
        script_index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    scripts_browser.file_selected.emit(str(script_file))

    assert scripts_browser.tree.selectionModel().hasSelection()
    assert not macros_browser.tree.selectionModel().hasSelection()


def test_modifier_file_selection_keeps_existing_highlights(ide_explorer, qtbot, tmpdir):
    """Modifier-click selection keeps earlier highlights across scripts and macros."""
    scripts_dir = tmpdir.mkdir("scripts")
    macros_dir = tmpdir.mkdir("macros")
    script_file = scripts_dir.join("script.py")
    macro_file = macros_dir.join("macro.py")
    script_file.write("print('script')")
    macro_file.write("def macro():\n    pass\n")

    scripts_browser = (
        ide_explorer.main_explorer.get_section("SCRIPTS")
        .content_widget.get_section("Local")
        .content_widget
    )
    macros_browser = (
        ide_explorer.main_explorer.get_section("MACROS")
        .content_widget.get_section("Local")
        .content_widget
    )
    scripts_browser.set_directory(str(scripts_dir))
    macros_browser.set_directory(str(macros_dir))

    def get_index(browser, file_name):
        root_index = browser.tree.rootIndex()
        for i in range(browser.proxy_model.rowCount(root_index)):
            index = browser.proxy_model.index(i, 0, root_index)
            if browser.proxy_model.data(index) == file_name:
                return index
        return None

    qtbot.waitUntil(
        lambda: get_index(scripts_browser, "script.py") is not None
        and get_index(macros_browser, "macro.py") is not None,
        timeout=5000,
    )

    macro_index = get_index(macros_browser, "macro.py")
    assert macro_index is not None
    macros_browser.tree.selectionModel().select(
        macro_index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    macros_browser.file_selected.emit(str(macro_file))

    script_index = get_index(scripts_browser, "script.py")
    assert script_index is not None
    scripts_browser.tree.selectionModel().select(
        script_index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    scripts_browser._selection_extending = True
    scripts_browser.file_selected.emit(str(script_file))

    assert scripts_browser.tree.selectionModel().hasSelection()
    assert macros_browser.tree.selectionModel().hasSelection()


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
        with open(expected_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "def test_macro_function():" in content
            assert "test_macro_function macro" in content


def test_ide_explorer_delete_local_script(ide_explorer, tmpdir):
    """Test deleting a local script file."""
    local_script_section = ide_explorer.main_explorer.get_section(
        "SCRIPTS"
    ).content_widget.get_section("Local")
    local_script_section.content_widget.set_directory(str(tmpdir))

    file_path = os.path.join(tmpdir, "delete_me.py")
    Path(file_path).write_text("print('delete me')", encoding="utf-8")

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        ide_explorer._delete_local_script(file_path)

    assert not os.path.exists(file_path)


def test_ide_explorer_delete_local_script_directory(ide_explorer, tmpdir):
    """Test deleting a local script directory."""
    local_script_section = ide_explorer.main_explorer.get_section(
        "SCRIPTS"
    ).content_widget.get_section("Local")
    local_script_section.content_widget.set_directory(str(tmpdir))

    script_dir = Path(tmpdir) / "subdir"
    script_dir.mkdir()
    nested_file = script_dir / "nested.py"
    nested_file.write_text("print('nested')", encoding="utf-8")

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        ide_explorer._delete_local_script(str(script_dir))

    assert not script_dir.exists()


def test_ide_explorer_delete_local_macro_broadcasts_removals(ide_explorer, tmpdir):
    """Test deleting a local macro unloads loaded macros and removes the file."""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    file_path = os.path.join(tmpdir, "delete_macro.py")
    Path(file_path).write_text("def delete_macro():\n    pass\n", encoding="utf-8")

    ide_explorer.client.macros = mock.MagicMock()
    ide_explorer.client.macros._update_handler = mock.MagicMock()
    ide_explorer.client.macros._update_handler.get_existing_macros.return_value = {
        "delete_macro": {"fname": file_path}
    }

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        ide_explorer._delete_local_macro(file_path)

    ide_explorer.client.macros._update_handler.broadcast.assert_called_once_with(
        action="remove", name="delete_macro"
    )
    assert not os.path.exists(file_path)


def test_ide_explorer_delete_local_macro_directory_broadcasts_removals(ide_explorer, tmpdir):
    """Test deleting a local macro directory unloads macros from contained files."""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    macro_dir = Path(tmpdir) / "subdir"
    macro_dir.mkdir()
    file_path = macro_dir / "delete_macro.py"
    file_path.write_text("def delete_macro():\n    pass\n", encoding="utf-8")

    ide_explorer.client.macros = mock.MagicMock()
    ide_explorer.client.macros._update_handler = mock.MagicMock()
    ide_explorer.client.macros._update_handler.get_existing_macros.return_value = {
        "delete_macro": {"fname": str(file_path)}
    }

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        ide_explorer._delete_local_macro(str(macro_dir))

    ide_explorer.client.macros._update_handler.broadcast.assert_called_once_with(
        action="remove", name="delete_macro"
    )
    assert not macro_dir.exists()


def test_ide_explorer_rename_local_macro_path_reloads_macros(ide_explorer, tmpdir):
    """Test local macro renames refresh open-editor and macro state."""
    ide_explorer.clear()
    ide_explorer.sections = ["macros"]

    local_macros_section = ide_explorer.main_explorer.get_section(
        "MACROS"
    ).content_widget.get_section("Local")
    local_macros_section.content_widget.set_directory(str(tmpdir))

    old_path = os.path.join(tmpdir, "old_name.py")
    new_path = os.path.join(tmpdir, "new_name.py")

    ide_explorer.client.macros = mock.MagicMock()
    ide_explorer.client.macros._update_handler = mock.MagicMock()

    with (
        mock.patch.object(ide_explorer, "_rename_open_editor_path") as mock_rename_open_editor,
        mock.patch.object(ide_explorer, "_broadcast_removed_macros") as mock_broadcast_removed,
    ):
        ide_explorer._rename_local_macro_path(old_path, new_path)

    mock_broadcast_removed.assert_called_once_with(old_path)
    mock_rename_open_editor.assert_called_once_with(old_path, new_path)
    ide_explorer.client.macros.load_all_user_macros.assert_called_once()


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

    # Mock the refresh method
    with mock.patch.object(local_macros_section.content_widget, "refresh") as mock_refresh:
        ide_explorer.refresh_macro_file(str(macro_file))

        # Should refresh the file browser
        mock_refresh.assert_called_once_with()


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

    # Mock the refresh method
    with mock.patch.object(local_macros_section.content_widget, "refresh") as mock_refresh:
        ide_explorer.refresh_macro_file(unrelated_file)

        # Should not refresh for unrelated files
        mock_refresh.assert_not_called()


def test_ide_explorer_refresh_macro_file_no_sections(ide_explorer, qtbot):
    """Test refreshing a macro file when no macro sections exist"""
    ide_explorer.clear()
    # Don't add macros section

    # Should handle gracefully without error
    ide_explorer.refresh_macro_file("/some/path/test.py")
    # Test passes if no exception is raised
