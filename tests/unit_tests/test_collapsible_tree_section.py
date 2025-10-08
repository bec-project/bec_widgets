# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

from unittest import mock

import pytest
from qtpy.QtCore import QMimeData, QPoint, Qt
from qtpy.QtWidgets import QLabel

from bec_widgets.widgets.containers.explorer.collapsible_tree_section import CollapsibleSection


@pytest.fixture
def collapsible_section(qtbot):
    """Create a basic CollapsibleSection widget for testing"""
    widget = CollapsibleSection(title="Test Section")
    qtbot.addWidget(widget)
    yield widget


@pytest.fixture
def dummy_content_widget(qtbot):
    """Create a simple widget to be used as content"""
    widget = QLabel("Test Content")
    qtbot.addWidget(widget)
    return widget


def test_basic_initialization(collapsible_section):
    """Test basic initialization"""
    assert collapsible_section.title == "Test Section"
    assert collapsible_section.expanded is True
    assert collapsible_section.content_widget is None


def test_toggle_expanded(collapsible_section):
    """Test toggling expansion state"""
    assert collapsible_section.expanded is True
    collapsible_section.toggle_expanded()
    assert collapsible_section.expanded is False
    collapsible_section.toggle_expanded()
    assert collapsible_section.expanded is True


def test_set_widget(collapsible_section, dummy_content_widget):
    """Test setting content widget"""
    collapsible_section.set_widget(dummy_content_widget)
    assert collapsible_section.content_widget == dummy_content_widget
    assert dummy_content_widget.parent() == collapsible_section


def test_connect_add_button(qtbot):
    """Test connecting add button"""
    widget = CollapsibleSection(title="Test", show_add_button=True)
    qtbot.addWidget(widget)

    mock_slot = mock.MagicMock()
    widget.connect_add_button(mock_slot)

    qtbot.mouseClick(widget.header_add_button, Qt.MouseButton.LeftButton)
    mock_slot.assert_called_once()


def test_section_reorder_signal(collapsible_section):
    """Test section reorder signal emission"""
    signals_received = []
    collapsible_section.section_reorder_requested.connect(
        lambda source, target: signals_received.append((source, target))
    )

    # Create mock drop event
    mime_data = QMimeData()
    mime_data.setText("section:Source Section")

    mock_event = mock.MagicMock()
    mock_event.mimeData.return_value = mime_data

    collapsible_section._header_drop_event(mock_event)

    assert len(signals_received) == 1
    assert signals_received[0] == ("Source Section", "Test Section")


def test_nested_collapsible_sections(qtbot):
    """Test that collapsible sections can be nested"""
    # Create parent section
    parent_section = CollapsibleSection(title="Parent Section")
    qtbot.addWidget(parent_section)

    # Create child section
    child_section = CollapsibleSection(title="Child Section")
    qtbot.addWidget(child_section)

    # Add some content to the child section
    child_content = QLabel("Child Content")
    qtbot.addWidget(child_content)
    child_section.set_widget(child_content)

    # Nest the child section inside the parent
    parent_section.set_widget(child_section)

    # Verify nesting structure
    assert parent_section.content_widget == child_section
    assert child_section.parent() == parent_section
    assert child_section.content_widget == child_content
    assert child_content.parent() == child_section

    # Test that both sections can expand/collapse independently
    assert parent_section.expanded is True
    assert child_section.expanded is True

    # Collapse child section
    child_section.toggle_expanded()
    assert child_section.expanded is False
    assert parent_section.expanded is True  # Parent should remain expanded

    # Collapse parent section
    parent_section.toggle_expanded()
    assert parent_section.expanded is False
    assert child_section.expanded is False  # Child state unchanged
