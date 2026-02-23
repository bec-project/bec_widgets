# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from unittest import mock

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.widget_io import WidgetHierarchy, WidgetIO, WidgetTreeNode
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch


@pytest.fixture(scope="function")
def example_widget(qtbot):
    # Create a widget with a few child widgets
    main_widget = QWidget()
    layout = QVBoxLayout(main_widget)
    line_edit = QLineEdit(main_widget)
    combo_box = QComboBox(main_widget)
    table_widget = QTableWidget(2, 2, main_widget)
    spin_box = QSpinBox(main_widget)
    toggle = ToggleSwitch(main_widget)

    layout.addWidget(line_edit)
    layout.addWidget(combo_box)
    layout.addWidget(table_widget)
    layout.addWidget(spin_box)
    layout.addWidget(toggle)

    # Add text items to the combo box
    combo_box.addItems(["Option 1", "Option 2", "Option 3"])

    # Populate the table widget
    table_widget.setItem(0, 0, QTableWidgetItem("Initial A"))
    table_widget.setItem(0, 1, QTableWidgetItem("Initial B"))
    table_widget.setItem(1, 0, QTableWidgetItem("Initial C"))
    table_widget.setItem(1, 1, QTableWidgetItem("Initial D"))

    qtbot.addWidget(main_widget)
    qtbot.waitExposed(main_widget)
    yield main_widget


def test_export_import_config(example_widget):
    initial_config = {
        "QWidget ()": {
            "QLineEdit ()": {"value": "New Text"},
            "QComboBox ()": {"value": 1},
            "QTableWidget ()": {"value": [["a", "b"], ["c", "d"]]},
            "QSpinBox ()": {"value": 10},
        }
    }
    WidgetHierarchy.import_config_from_dict(example_widget, initial_config, set_values=True)

    exported_config_full = WidgetHierarchy.export_config_to_dict(example_widget, grab_values=True)
    exported_config_reduced = WidgetHierarchy.export_config_to_dict(
        example_widget, grab_values=True, save_all=False
    )

    expected_full = {
        "QWidget ()": {
            "QComboBox ()": {"QStandardItemModel ()": {}, "value": 1},
            "QLineEdit ()": {"QObject ()": {}, "value": "New Text"},
            "QSpinBox ()": {
                "QLineEdit (qt_spinbox_lineedit)": {"QObject ()": {}, "value": "10"},
                "QValidator (qt_spinboxvalidator)": {},
                "value": 10,
            },
            "QTableWidget ()": {
                "QAbstractButton ()": {},
                "QAbstractTableModel ()": {},
                "QHeaderView ()": {
                    "QItemSelectionModel ()": {},
                    "QWidget (qt_scrollarea_hcontainer)": {
                        "QBoxLayout ()": {},
                        "QScrollBar ()": {},
                    },
                    "QWidget (qt_scrollarea_vcontainer)": {
                        "QBoxLayout ()": {},
                        "QScrollBar ()": {},
                    },
                    "QWidget (qt_scrollarea_viewport)": {},
                },
                "QItemSelectionModel ()": {},
                "QStyledItemDelegate ()": {},
                "QWidget (qt_scrollarea_hcontainer)": {"QBoxLayout ()": {}, "QScrollBar ()": {}},
                "QWidget (qt_scrollarea_vcontainer)": {"QBoxLayout ()": {}, "QScrollBar ()": {}},
                "QWidget (qt_scrollarea_viewport)": {},
                "value": [["a", "b"], ["c", "d"]],
            },
            "QVBoxLayout ()": {},
            "ToggleSwitch ()": {"value": True},
        }
    }
    expected_reduced = {
        "QWidget ()": {
            "QComboBox ()": {"value": 1},
            "QLineEdit ()": {"value": "New Text"},
            "QSpinBox ()": {"QLineEdit (qt_spinbox_lineedit)": {"value": "10"}, "value": 10},
            "QTableWidget ()": {"value": [["a", "b"], ["c", "d"]]},
            "ToggleSwitch ()": {"value": True},
        }
    }

    assert exported_config_full == expected_full
    assert exported_config_reduced == expected_reduced


def test_widget_io_get_set_value(example_widget):
    # Extract widgets
    line_edit = example_widget.findChild(QLineEdit)
    combo_box = example_widget.findChild(QComboBox)
    table_widget = example_widget.findChild(QTableWidget)
    spin_box = example_widget.findChild(QSpinBox)
    toggle = example_widget.findChild(ToggleSwitch)

    # Check initial values
    assert WidgetIO.get_value(line_edit) == ""
    assert WidgetIO.get_value(combo_box) == 0  # first index
    assert WidgetIO.get_value(table_widget) == [
        ["Initial A", "Initial B"],
        ["Initial C", "Initial D"],
    ]
    assert WidgetIO.get_value(spin_box) == 0
    assert WidgetIO.get_value(toggle) == True

    # Set new values
    WidgetIO.set_value(line_edit, "Hello")
    WidgetIO.set_value(combo_box, "Option 2")
    WidgetIO.set_value(table_widget, [["X", "Y"], ["Z", "W"]])
    WidgetIO.set_value(spin_box, 5)
    WidgetIO.set_value(toggle, False)

    # Check updated values
    assert WidgetIO.get_value(line_edit) == "Hello"
    assert WidgetIO.get_value(combo_box, as_string=True) == "Option 2"
    assert WidgetIO.get_value(table_widget) == [["X", "Y"], ["Z", "W"]]
    assert WidgetIO.get_value(spin_box) == 5
    assert WidgetIO.get_value(toggle) == False


def test_widget_io_signal(qtbot, example_widget):
    # Extract widgets
    line_edit = example_widget.findChild(QLineEdit)
    combo_box = example_widget.findChild(QComboBox)
    spin_box = example_widget.findChild(QSpinBox)
    table_widget = example_widget.findChild(QTableWidget)
    toggle = example_widget.findChild(ToggleSwitch)

    # We'll store changes in a list to verify the slot is called
    changes = []

    def universal_slot(w, val):
        changes.append((w, val))

    # Connect signals
    WidgetIO.connect_widget_change_signal(line_edit, universal_slot)
    WidgetIO.connect_widget_change_signal(combo_box, universal_slot)
    WidgetIO.connect_widget_change_signal(spin_box, universal_slot)
    WidgetIO.connect_widget_change_signal(table_widget, universal_slot)
    WidgetIO.connect_widget_change_signal(toggle, universal_slot)

    # Trigger changes
    line_edit.setText("NewText")
    qtbot.waitUntil(lambda: len(changes) > 0)
    assert changes[-1][1] == "NewText"

    combo_box.setCurrentIndex(2)
    qtbot.waitUntil(lambda: len(changes) > 1)
    # combo_box change should give the current index or value
    # We set "Option 3" is index 2
    assert changes[-1][1] == 2 or changes[-1][1] == "Option 3"

    spin_box.setValue(42)
    qtbot.waitUntil(lambda: len(changes) > 2)
    assert changes[-1][1] == 42

    # For the table widget, changing a cell triggers cellChanged
    table_widget.setItem(0, 0, QTableWidgetItem("ChangedCell"))
    qtbot.waitUntil(lambda: len(changes) > 3)
    # The entire table value should be retrieved
    assert changes[-1][1][0][0] == "ChangedCell"

    # Test the toggle switch
    toggle.checked = False
    qtbot.waitUntil(lambda: len(changes) > 4)
    assert changes[-1][1] == False


def test_find_widgets(example_widget):
    # Test find_widgets by class type
    line_edits = WidgetIO.find_widgets(QLineEdit)
    assert len(line_edits) == 2  # one LineEdit and one in the SpinBox
    assert isinstance(line_edits[0], QLineEdit)

    # Test find_widgets by class-name string
    combo_boxes = WidgetIO.find_widgets("QComboBox")
    assert len(combo_boxes) == 1
    assert isinstance(combo_boxes[0], QComboBox)

    # Test non-recursive search returns the same widgets
    combo_boxes_flat = WidgetIO.find_widgets(QComboBox, recursive=False)
    assert combo_boxes_flat == combo_boxes

    # Test search for non-existent widget returns empty list
    non_exist = WidgetIO.find_widgets("NonExistentWidget")
    assert non_exist == []


# ── WidgetHierarchy._build_prefix ─────────────────────────────────────────────


def test_build_prefix_empty():
    assert WidgetHierarchy._build_prefix([]) == ""


def test_build_prefix_single_last():
    assert WidgetHierarchy._build_prefix([True]) == "└─ "


def test_build_prefix_single_not_last():
    assert WidgetHierarchy._build_prefix([False]) == "├─ "


def test_build_prefix_nested_last_last():
    # parent is last (True), child is last (True): "   └─ "
    assert WidgetHierarchy._build_prefix([True, True]) == "   └─ "


def test_build_prefix_nested_not_last_last():
    # parent is not last (False), child is last (True): "│  └─ "
    assert WidgetHierarchy._build_prefix([False, True]) == "│  └─ "


def test_build_prefix_nested_not_last_not_last():
    # parent is not last (False), child is not last (False): "│  ├─ "
    assert WidgetHierarchy._build_prefix([False, False]) == "│  ├─ "


def test_build_prefix_deep_tree():
    # Three levels: not-last → not-last → last
    assert WidgetHierarchy._build_prefix([False, False, True]) == "│  │  └─ "


# ── WidgetHierarchy._filtered_children ────────────────────────────────────────


def test_filtered_children_plain_widget(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    child1 = QLabel(parent)
    child2 = QPushButton(parent)
    result = WidgetHierarchy._filtered_children(parent, exclude_internal_widgets=True)
    assert child1 in result
    assert child2 in result


def test_filtered_children_combobox_excludes_internal(qtbot):
    combo = QComboBox()
    qtbot.addWidget(combo)
    combo.addItems(["a", "b"])
    result_excluded = WidgetHierarchy._filtered_children(combo, exclude_internal_widgets=True)
    result_included = WidgetHierarchy._filtered_children(combo, exclude_internal_widgets=False)
    internal_names = {c.__class__.__name__ for c in result_included}
    excluded_names = {c.__class__.__name__ for c in result_excluded}
    # At least one internal widget type is present when not excluded
    assert internal_names & {"QFrame", "QListView"}
    # The same internal types should be absent when excluded
    assert not (excluded_names & {"QFrame", "QListView"})


def test_filtered_children_skips_invalid_child(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    child = QLabel(parent)
    with mock.patch("shiboken6.isValid", side_effect=lambda w: w is not child):
        result = WidgetHierarchy._filtered_children(parent, exclude_internal_widgets=False)
    assert child not in result


# ── WidgetHierarchy.iter_widget_tree ──────────────────────────────────────────


def test_iter_widget_tree_basic(qtbot):
    root = QWidget()
    qtbot.addWidget(root)
    child = QLabel(root)
    nodes = list(WidgetHierarchy.iter_widget_tree(root))
    widgets = [n.widget for n in nodes]
    assert root in widgets
    assert child in widgets


def test_iter_widget_tree_root_node_attrs(qtbot):
    root = QWidget()
    qtbot.addWidget(root)
    nodes = list(WidgetHierarchy.iter_widget_tree(root))
    root_node = nodes[0]
    assert root_node.widget is root
    assert root_node.parent is None
    assert root_node.depth == 0
    assert root_node.prefix == ""


def test_iter_widget_tree_child_node_attrs(qtbot):
    root = QWidget()
    qtbot.addWidget(root)
    child = QLabel(root)
    nodes = list(WidgetHierarchy.iter_widget_tree(root))
    child_node = next(n for n in nodes if n.widget is child)
    assert child_node.parent is root
    assert child_node.depth == 1
    assert child_node.prefix in ("├─ ", "└─ ")


def test_iter_widget_tree_none_widget():
    nodes = list(WidgetHierarchy.iter_widget_tree(None))
    assert nodes == []


def test_iter_widget_tree_invalid_widget(qtbot):
    root = QWidget()
    qtbot.addWidget(root)
    with mock.patch("shiboken6.isValid", return_value=False):
        nodes = list(WidgetHierarchy.iter_widget_tree(root))
    assert nodes == []


def test_iter_widget_tree_prevents_revisiting(qtbot):
    """Visited-set prevents infinite loops when the same widget is returned
    more than once by _filtered_children (simulates a circular-reference
    scenario that cannot arise naturally in Qt but is handled defensively)."""
    root = QWidget()
    qtbot.addWidget(root)
    child = QLabel(root)

    call_count = 0

    original = WidgetHierarchy._filtered_children

    def patched(widget, exclude):
        nonlocal call_count
        result = original(widget, exclude)
        # After the first call (for root), inject root itself as a child of child
        if widget is child:
            call_count += 1
            result = [root] + result  # root already visited – should be skipped
        return result

    with mock.patch.object(WidgetHierarchy, "_filtered_children", staticmethod(patched)):
        nodes = list(WidgetHierarchy.iter_widget_tree(root))

    widget_ids = [id(n.widget) for n in nodes]
    # root must appear exactly once despite being injected as a child of child
    assert widget_ids.count(id(root)) == 1
    assert call_count >= 1


def test_iter_widget_tree_depth_and_prefix_for_multiple_children(qtbot):
    root = QWidget()
    qtbot.addWidget(root)
    first = QLabel(root)
    second = QPushButton(root)
    nodes = list(WidgetHierarchy.iter_widget_tree(root))
    child_nodes = [n for n in nodes if n.depth == 1]
    prefixes = {n.prefix for n in child_nodes}
    # Non-last child gets "├─ " and last child gets "└─ "
    assert "├─ " in prefixes
    assert "└─ " in prefixes
