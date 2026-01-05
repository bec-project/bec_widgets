from unittest import mock

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from bec_widgets.widgets.utility.widget_hierarchy_tree.widget_hierarchy_tree import (
    WidgetHierarchyDialog,
)


def _iter_tree_items(tree_widget):
    for i in range(tree_widget.topLevelItemCount()):
        item = tree_widget.topLevelItem(i)
        yield from _walk_item(item)


def _walk_item(item):
    yield item
    for i in range(item.childCount()):
        yield from _walk_item(item.child(i))


def _tree_widgets(dialog: WidgetHierarchyDialog) -> list[QWidget]:
    return [
        item.data(0, Qt.ItemDataRole.UserRole)
        for item in _iter_tree_items(dialog._tree)
        if item.data(0, Qt.ItemDataRole.UserRole) is not None
    ]


def _find_item_by_widget(dialog: WidgetHierarchyDialog, widget: QWidget):
    for item in _iter_tree_items(dialog._tree):
        if item.data(0, Qt.ItemDataRole.UserRole) is widget:
            return item
    return None


@pytest.fixture
def hierarchy_fixture(qtbot):
    root = QWidget()
    root.setObjectName("root_widget")
    root_layout = QVBoxLayout(root)

    visible_btn = QPushButton("Visible", root)
    visible_btn.setObjectName("visible_btn")
    root_layout.addWidget(visible_btn)

    hidden_label = QLabel("Hidden", root)
    hidden_label.setObjectName("hidden_lbl")
    hidden_label.hide()
    root_layout.addWidget(hidden_label)

    container = QWidget(root)
    container.setObjectName("container")
    container_layout = QVBoxLayout(container)
    nested_btn = QPushButton("Nested", container)
    nested_btn.setObjectName("nested_btn")
    container_layout.addWidget(nested_btn)
    root_layout.addWidget(container)

    qtbot.addWidget(root)
    root.show()
    qtbot.waitExposed(root)

    dialog = WidgetHierarchyDialog(root_widget=root)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    yield dialog, root, visible_btn, hidden_label, nested_btn, root_layout

    dialog.close()
    root.close()


def test_tree_populates_widgets_for_explicit_root(hierarchy_fixture):
    dialog, root, visible_btn, hidden_label, nested_btn, _ = hierarchy_fixture
    widgets = _tree_widgets(dialog)

    assert dialog._tree.topLevelItemCount() == 1
    assert root in widgets
    assert visible_btn in widgets
    assert hidden_label in widgets
    assert nested_btn in widgets
    assert dialog not in widgets


def test_visibility_filter_visible_only(hierarchy_fixture, qtbot):
    dialog, root, visible_btn, hidden_label, nested_btn, _ = hierarchy_fixture

    dialog._visibility_filter.setCurrentText("Visible only")
    qtbot.wait(50)
    widgets = _tree_widgets(dialog)

    assert root in widgets
    assert visible_btn in widgets
    assert nested_btn in widgets
    assert hidden_label not in widgets


def test_visibility_filter_hidden_only(hierarchy_fixture, qtbot):
    dialog, root, visible_btn, hidden_label, nested_btn, _ = hierarchy_fixture

    dialog._visibility_filter.setCurrentText("Hidden only")
    qtbot.wait(50)
    widgets = _tree_widgets(dialog)

    assert hidden_label in widgets
    assert root in widgets
    assert visible_btn not in widgets
    assert nested_btn not in widgets


def test_refresh_button_updates_tree_for_new_widget(hierarchy_fixture, qtbot):
    dialog, _, _, _, _, root_layout = hierarchy_fixture

    late_btn = QPushButton("Late")
    late_btn.setObjectName("late_btn")
    root_layout.addWidget(late_btn)

    qtbot.mouseClick(dialog._refresh_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)

    widgets = _tree_widgets(dialog)
    assert late_btn in widgets


def test_find_button_triggers_highlighter(hierarchy_fixture, qtbot):
    dialog, _, visible_btn, _, _, _ = hierarchy_fixture
    item = _find_item_by_widget(dialog, visible_btn)
    assert item is not None

    button = dialog._tree.itemWidget(item, 3)
    assert isinstance(button, QToolButton)
    assert button.isEnabled()

    with mock.patch.object(dialog._highlighter, "highlight") as highlight_mock:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        highlight_mock.assert_called_once_with(visible_btn)
