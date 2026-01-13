from pathlib import Path

import pytest
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QMouseEvent

from bec_widgets.widgets.containers.explorer.script_tree_widget import ScriptTreeWidget


@pytest.fixture
def script_tree(qtbot, tmpdir):
    """Create a ScriptTreeWidget with the tmpdir directory"""
    # Create test files and directories
    (Path(tmpdir) / "test_file.py").touch()
    (Path(tmpdir) / "test_dir").mkdir()
    (Path(tmpdir) / "test_dir" / "nested_file.py").touch()

    widget = ScriptTreeWidget()
    widget.set_directory(str(tmpdir))
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_script_tree_set_directory(script_tree, tmpdir):
    """Test setting the directory"""
    assert script_tree.directory == str(tmpdir)


def test_script_tree_hover_events(script_tree, qtbot):
    """Test mouse hover events and actions button visibility"""

    # Get the tree view and its viewport
    tree_view = script_tree.tree
    viewport = tree_view.viewport()

    # Find the position of the first item (test_file.py)
    index = script_tree.proxy_model.index(0, 0)  # first item
    rect = tree_view.visualRect(index)
    pos = rect.center()

    # Initially, no item should be hovered
    assert script_tree.delegate.hovered_index.isValid() == False

    # Simulate a mouse move event over the item
    mouse_event = QMouseEvent(
        QEvent.Type.MouseMove,
        pos,
        tree_view.mapToGlobal(pos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    # Send the event to the viewport (the event filter is installed on the viewport)
    script_tree.eventFilter(viewport, mouse_event)

    # Now, the hover index should be set to the first item
    qtbot.waitUntil(lambda: script_tree.delegate.hovered_index.isValid(), timeout=5000)
    assert script_tree.delegate.hovered_index.row() == index.row()

    # Simulate mouse leaving the viewport
    leave_event = QEvent(QEvent.Type.Leave)
    script_tree.eventFilter(viewport, leave_event)

    # After leaving, no item should be hovered
    qtbot.waitUntil(lambda: not script_tree.delegate.hovered_index.isValid(), timeout=5000)


@pytest.mark.timeout(10)
def test_script_tree_on_item_clicked(script_tree, qtbot, tmpdir):
    """Test that _on_item_clicked emits file_selected signal only for Python files"""

    file_selected_signals = []
    file_open_requested_signals = []

    def on_file_selected(file_path):
        file_selected_signals.append(file_path)

    def on_file_open_requested(file_path):
        file_open_requested_signals.append(file_path)

    # Connect to the signal
    script_tree.file_selected.connect(on_file_selected)
    script_tree.file_open_requested.connect(on_file_open_requested)

    # Wait until the model sees test_file.py
    def has_py_file():
        nonlocal py_file_index
        root_index = script_tree.tree.rootIndex()
        for i in range(script_tree.proxy_model.rowCount(root_index)):
            index = script_tree.proxy_model.index(i, 0, root_index)
            source_index = script_tree.proxy_model.mapToSource(index)
            if script_tree.model.fileName(source_index) == "test_file.py":
                py_file_index = index
                return True
        return False

    py_file_index = None
    qtbot.waitUntil(has_py_file)

    # Simulate clicking on the center of the item
    script_tree._on_item_clicked(py_file_index)
    qtbot.wait(100)  # Allow time for the click to be processed

    py_file_index = None
    qtbot.waitUntil(has_py_file)

    script_tree._on_item_double_clicked(py_file_index)
    qtbot.wait(100)

    # Verify the signal was emitted with the correct path
    assert len(file_selected_signals) == 1
    assert Path(file_selected_signals[0]).name == "test_file.py"
