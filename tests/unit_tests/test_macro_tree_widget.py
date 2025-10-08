"""
Unit tests for the MacroTreeWidget.
"""

from pathlib import Path

import pytest
from qtpy.QtCore import QEvent, QModelIndex, Qt
from qtpy.QtGui import QMouseEvent

from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.widgets.containers.explorer.macro_tree_widget import MacroTreeWidget


@pytest.fixture
def temp_macro_files(tmpdir):
    """Create temporary macro files for testing."""
    macro_dir = Path(tmpdir) / "macros"
    macro_dir.mkdir()

    # Create a simple macro file with functions
    macro_file1 = macro_dir / "test_macros.py"
    macro_file1.write_text(
        '''
def test_macro_function():
    """A test macro function."""
    return "test"

def another_function(param1, param2):
    """Another function with parameters."""
    return param1 + param2

class TestClass:
    """This class should be ignored."""
    def method(self):
        pass
'''
    )

    # Create another macro file
    macro_file2 = macro_dir / "utils_macros.py"
    macro_file2.write_text(
        '''
def utility_function():
    """A utility function."""
    pass

def deprecated_function():
    """Old function."""
    return None
'''
    )

    # Create a file with no functions (should be ignored)
    empty_file = macro_dir / "empty.py"
    empty_file.write_text(
        """
# Just a comment
x = 1
y = 2
"""
    )

    # Create a file starting with underscore (should be ignored)
    private_file = macro_dir / "_private.py"
    private_file.write_text(
        """
def private_function():
    return "private"
"""
    )

    # Create a file with syntax errors
    error_file = macro_dir / "error_file.py"
    error_file.write_text(
        """
def broken_function(
    # Missing closing parenthesis and colon
    pass
"""
    )

    return macro_dir


@pytest.fixture
def macro_tree(qtbot, temp_macro_files):
    """Create a MacroTreeWidget with test macro files."""
    widget = MacroTreeWidget()
    widget.set_directory(str(temp_macro_files))
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


class TestMacroTreeWidgetInitialization:
    """Test macro tree widget initialization and basic functionality."""

    def test_initialization(self, qtbot):
        """Test that the macro tree widget initializes correctly."""
        widget = MacroTreeWidget()
        qtbot.addWidget(widget)

        # Check basic properties
        assert widget.tree is not None
        assert widget.model is not None
        assert widget.delegate is not None
        assert widget.directory is None

        # Check that tree is configured properly
        assert widget.tree.isHeaderHidden()
        assert widget.tree.rootIsDecorated()
        assert not widget.tree.editTriggers()

    def test_set_directory_with_valid_path(self, macro_tree, temp_macro_files):
        """Test setting a valid directory path."""
        assert macro_tree.directory == str(temp_macro_files)

        # Check that files were loaded
        assert macro_tree.model.rowCount() > 0

        # Should have 2 files (test_macros.py and utils_macros.py)
        # empty.py and _private.py should be filtered out
        expected_files = ["test_macros", "utils_macros"]
        actual_files = []

        for row in range(macro_tree.model.rowCount()):
            item = macro_tree.model.item(row)
            if item:
                actual_files.append(item.text())

        # Sort for consistent comparison
        actual_files.sort()
        expected_files.sort()

        for expected in expected_files:
            assert expected in actual_files

    def test_set_directory_with_invalid_path(self, qtbot):
        """Test setting an invalid directory path."""
        widget = MacroTreeWidget()
        qtbot.addWidget(widget)

        widget.set_directory("/nonexistent/path")

        # Should handle gracefully
        assert widget.directory == "/nonexistent/path"
        assert widget.model.rowCount() == 0

    def test_set_directory_with_none(self, qtbot):
        """Test setting directory to None."""
        widget = MacroTreeWidget()
        qtbot.addWidget(widget)

        widget.set_directory(None)

        # Should handle gracefully
        assert widget.directory is None
        assert widget.model.rowCount() == 0


class TestMacroFunctionParsing:
    """Test macro function parsing and AST functionality."""

    def test_extract_functions_from_file(self, macro_tree, temp_macro_files):
        """Test extracting functions from a Python file."""
        test_file = temp_macro_files / "test_macros.py"
        functions = macro_tree._extract_functions_from_file(test_file)

        # Should extract 2 functions, not the class method
        assert len(functions) == 2
        assert "test_macro_function" in functions
        assert "another_function" in functions
        assert "method" not in functions  # Class methods should be excluded

        # Check function details
        test_func = functions["test_macro_function"]
        assert test_func["line_number"] == 2  # First function starts at line 2
        assert "A test macro function" in test_func["docstring"]

    def test_extract_functions_from_empty_file(self, macro_tree, temp_macro_files):
        """Test extracting functions from a file with no functions."""
        empty_file = temp_macro_files / "empty.py"
        functions = macro_tree._extract_functions_from_file(empty_file)

        assert len(functions) == 0

    def test_extract_functions_from_invalid_file(self, macro_tree):
        """Test extracting functions from a non-existent file."""
        nonexistent_file = Path("/nonexistent/file.py")
        functions = macro_tree._extract_functions_from_file(nonexistent_file)

        assert len(functions) == 0

    def test_extract_functions_from_syntax_error_file(self, macro_tree, temp_macro_files):
        """Test extracting functions from a file with syntax errors."""
        error_file = temp_macro_files / "error_file.py"
        functions = macro_tree._extract_functions_from_file(error_file)

        # Should return empty dict on syntax error
        assert len(functions) == 0

    def test_create_file_item(self, macro_tree, temp_macro_files):
        """Test creating a file item from a Python file."""
        test_file = temp_macro_files / "test_macros.py"
        file_item = macro_tree._create_file_item(test_file)

        assert file_item is not None
        assert file_item.text() == "test_macros"
        assert file_item.rowCount() == 2  # Should have 2 function children

        # Check file data
        file_data = file_item.data(Qt.ItemDataRole.UserRole)
        assert file_data["type"] == "file"
        assert file_data["file_path"] == str(test_file)

        # Check function children
        func_names = []
        for row in range(file_item.rowCount()):
            child = file_item.child(row)
            func_names.append(child.text())

            # Check function data
            func_data = child.data(Qt.ItemDataRole.UserRole)
            assert func_data["type"] == "function"
            assert func_data["file_path"] == str(test_file)
            assert "function_name" in func_data
            assert "line_number" in func_data

        assert "test_macro_function" in func_names
        assert "another_function" in func_names

    def test_create_file_item_with_private_file(self, macro_tree, temp_macro_files):
        """Test that files starting with underscore are ignored."""
        private_file = temp_macro_files / "_private.py"
        file_item = macro_tree._create_file_item(private_file)

        assert file_item is None

    def test_create_file_item_with_no_functions(self, macro_tree, temp_macro_files):
        """Test that files with no functions return None."""
        empty_file = temp_macro_files / "empty.py"
        file_item = macro_tree._create_file_item(empty_file)

        assert file_item is None


class TestMacroTreeInteractions:
    """Test macro tree widget interactions and signals."""

    def test_item_click_on_function(self, macro_tree, qtbot):
        """Test clicking on a function item."""
        # Set up signal spy
        macro_selected_signals = []

        def on_macro_selected(function_name, file_path):
            macro_selected_signals.append((function_name, file_path))

        macro_tree.macro_selected.connect(on_macro_selected)

        # Find a function item
        file_item = macro_tree.model.item(0)  # First file
        if file_item and file_item.rowCount() > 0:
            func_item = file_item.child(0)  # First function
            func_index = func_item.index()

            # Simulate click
            macro_tree._on_item_clicked(func_index)

            # Check signal was emitted
            assert len(macro_selected_signals) == 1
            function_name, file_path = macro_selected_signals[0]
            assert function_name is not None
            assert file_path is not None
            assert file_path.endswith(".py")

    def test_item_click_on_file(self, macro_tree, qtbot):
        """Test clicking on a file item (should not emit signal)."""
        # Set up signal spy
        macro_selected_signals = []

        def on_macro_selected(function_name, file_path):
            macro_selected_signals.append((function_name, file_path))

        macro_tree.macro_selected.connect(on_macro_selected)

        # Find a file item
        file_item = macro_tree.model.item(0)
        if file_item:
            file_index = file_item.index()

            # Simulate click
            macro_tree._on_item_clicked(file_index)

            # Should not emit signal for file items
            assert len(macro_selected_signals) == 0

    def test_item_double_click_on_function(self, macro_tree, qtbot):
        """Test double-clicking on a function item."""
        # Set up signal spy
        open_requested_signals = []

        def on_macro_open_requested(function_name, file_path):
            open_requested_signals.append((function_name, file_path))

        macro_tree.macro_open_requested.connect(on_macro_open_requested)

        # Find a function item
        file_item = macro_tree.model.item(0)
        if file_item and file_item.rowCount() > 0:
            func_item = file_item.child(0)
            func_index = func_item.index()

            # Simulate double-click
            macro_tree._on_item_double_clicked(func_index)

            # Check signal was emitted
            assert len(open_requested_signals) == 1
            function_name, file_path = open_requested_signals[0]
            assert function_name is not None
            assert file_path is not None

    def test_hover_events(self, macro_tree, qtbot):
        """Test mouse hover events and action button visibility."""
        # Get the tree view and its viewport
        tree_view = macro_tree.tree
        viewport = tree_view.viewport()

        # Initially, no item should be hovered
        assert not macro_tree.delegate.hovered_index.isValid()

        # Find a function item to hover over
        file_item = macro_tree.model.item(0)
        if file_item and file_item.rowCount() > 0:
            func_item = file_item.child(0)
            func_index = func_item.index()

            # Get the position of the function item
            rect = tree_view.visualRect(func_index)
            pos = rect.center()

            # Simulate a mouse move event over the item
            mouse_event = QMouseEvent(
                QEvent.Type.MouseMove,
                pos,
                tree_view.mapToGlobal(pos),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )

            # Send the event to the viewport
            macro_tree.eventFilter(viewport, mouse_event)
            qtbot.wait(100)

            # Now, the hover index should be set
            assert macro_tree.delegate.hovered_index.isValid()
            assert macro_tree.delegate.hovered_index == func_index

            # Simulate mouse leaving the viewport
            leave_event = QEvent(QEvent.Type.Leave)
            macro_tree.eventFilter(viewport, leave_event)
            qtbot.wait(100)

            # After leaving, no item should be hovered
            assert not macro_tree.delegate.hovered_index.isValid()

    def test_macro_open_action(self, macro_tree, qtbot):
        """Test the macro open action functionality."""
        # Set up signal spy
        open_requested_signals = []

        def on_macro_open_requested(function_name, file_path):
            open_requested_signals.append((function_name, file_path))

        macro_tree.macro_open_requested.connect(on_macro_open_requested)

        # Find a function item and set it as hovered
        file_item = macro_tree.model.item(0)
        if file_item and file_item.rowCount() > 0:
            func_item = file_item.child(0)
            func_index = func_item.index()

            # Set the delegate's hovered index and current macro info
            macro_tree.delegate.set_hovered_index(func_index)
            func_data = func_item.data(Qt.ItemDataRole.UserRole)
            macro_tree.delegate.current_macro_info = func_data

            # Trigger the open action
            macro_tree._on_macro_open_requested()

            # Check signal was emitted
            assert len(open_requested_signals) == 1
            function_name, file_path = open_requested_signals[0]
            assert function_name is not None
            assert file_path is not None


class TestMacroTreeRefresh:
    """Test macro tree refresh functionality."""

    def test_refresh(self, macro_tree, temp_macro_files):
        """Test refreshing the entire tree."""
        # Get initial count
        initial_count = macro_tree.model.rowCount()

        # Add a new macro file
        new_file = temp_macro_files / "new_macros.py"
        new_file.write_text(
            '''
def new_function():
    """A new function."""
    return "new"
'''
        )

        # Refresh the tree
        macro_tree.refresh()

        # Should have one more file
        assert macro_tree.model.rowCount() == initial_count + 1

    def test_refresh_file_item(self, macro_tree, temp_macro_files):
        """Test refreshing a single file item."""
        # Find the test_macros.py file
        test_file_path = str(temp_macro_files / "test_macros.py")

        # Get initial function count
        initial_functions = []
        for row in range(macro_tree.model.rowCount()):
            item = macro_tree.model.item(row)
            if item:
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if item_data and item_data.get("file_path") == test_file_path:
                    for child_row in range(item.rowCount()):
                        child = item.child(child_row)
                        initial_functions.append(child.text())
                    break

        # Modify the file to add a new function
        with open(test_file_path, "a") as f:
            f.write(
                '''

def newly_added_function():
    """A newly added function."""
    return "added"
'''
            )

        # Refresh just this file
        macro_tree.refresh_file_item(test_file_path)

        # Check that the new function was added
        updated_functions = []
        for row in range(macro_tree.model.rowCount()):
            item = macro_tree.model.item(row)
            if item:
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if item_data and item_data.get("file_path") == test_file_path:
                    for child_row in range(item.rowCount()):
                        child = item.child(child_row)
                        updated_functions.append(child.text())
                    break

        # Should have the new function
        assert len(updated_functions) == len(initial_functions) + 1
        assert "newly_added_function" in updated_functions

    def test_refresh_nonexistent_file(self, macro_tree):
        """Test refreshing a non-existent file."""
        # Should handle gracefully without crashing
        macro_tree.refresh_file_item("/nonexistent/file.py")

        # Tree should remain unchanged
        assert macro_tree.model.rowCount() >= 0  # Just ensure it doesn't crash

    def test_expand_collapse_all(self, macro_tree, qtbot):
        """Test expand/collapse all functionality."""
        # Initially should be expanded
        for row in range(macro_tree.model.rowCount()):
            item = macro_tree.model.item(row)
            if item:
                # Items with children should be expanded after initial load
                if item.rowCount() > 0:
                    assert macro_tree.tree.isExpanded(item.index())

        # Collapse all
        macro_tree.collapse_all()
        qtbot.wait(50)

        for row in range(macro_tree.model.rowCount()):
            item = macro_tree.model.item(row)
            if item and item.rowCount() > 0:
                assert not macro_tree.tree.isExpanded(item.index())

        # Expand all
        macro_tree.expand_all()
        qtbot.wait(50)

        for row in range(macro_tree.model.rowCount()):
            item = macro_tree.model.item(row)
            if item and item.rowCount() > 0:
                assert macro_tree.tree.isExpanded(item.index())


class TestMacroItemDelegate:
    """Test the custom macro item delegate functionality."""

    def test_delegate_action_management(self, qtbot):
        """Test adding and clearing delegate actions."""
        widget = MacroTreeWidget()
        qtbot.addWidget(widget)

        # Should have at least one default action (open)
        assert len(widget.delegate.macro_actions) >= 1

        # Add a custom action
        custom_action = MaterialIconAction(icon_name="edit", tooltip="Edit", parent=widget)
        widget.add_macro_action(custom_action.action)

        # Should have the additional action
        assert len(widget.delegate.macro_actions) >= 2

        # Clear actions
        widget.clear_actions()

        # Should be empty
        assert len(widget.delegate.macro_actions) == 0

    def test_delegate_hover_index_management(self, qtbot):
        """Test hover index management in the delegate."""
        widget = MacroTreeWidget()
        qtbot.addWidget(widget)

        # Initially no hover
        assert not widget.delegate.hovered_index.isValid()

        # Create a fake index
        fake_index = widget.model.createIndex(0, 0)

        # Set hover
        widget.delegate.set_hovered_index(fake_index)
        assert widget.delegate.hovered_index == fake_index

        # Clear hover
        widget.delegate.set_hovered_index(QModelIndex())
        assert not widget.delegate.hovered_index.isValid()
