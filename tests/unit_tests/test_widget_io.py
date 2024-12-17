# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.widget_io import WidgetHierarchy, WidgetIO


@pytest.fixture(scope="function")
def example_widget(qtbot):
    # Create a widget with a few child widgets
    main_widget = QWidget()
    layout = QVBoxLayout(main_widget)
    line_edit = QLineEdit(main_widget)
    combo_box = QComboBox(main_widget)
    table_widget = QTableWidget(2, 2, main_widget)
    spin_box = QSpinBox(main_widget)
    layout.addWidget(line_edit)
    layout.addWidget(combo_box)
    layout.addWidget(table_widget)
    layout.addWidget(spin_box)

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
            "QVBoxLayout ()": {},
            "QLineEdit ()": {"value": "New Text", "QObject ()": {}},
            "QComboBox ()": {"value": 1, "QStandardItemModel ()": {}},
            "QTableWidget ()": {
                "value": [["a", "b"], ["c", "d"]],
                "QWidget (qt_scrollarea_viewport)": {},
                "QStyledItemDelegate ()": {},
                "QHeaderView ()": {
                    "QWidget (qt_scrollarea_viewport)": {},
                    "QWidget (qt_scrollarea_hcontainer)": {
                        "QScrollBar ()": {},
                        "QBoxLayout ()": {},
                    },
                    "QWidget (qt_scrollarea_vcontainer)": {
                        "QScrollBar ()": {},
                        "QBoxLayout ()": {},
                    },
                    "QItemSelectionModel ()": {},
                },
                "QAbstractButton ()": {},
                "QAbstractTableModel ()": {},
                "QItemSelectionModel ()": {},
                "QWidget (qt_scrollarea_hcontainer)": {"QScrollBar ()": {}, "QBoxLayout ()": {}},
                "QWidget (qt_scrollarea_vcontainer)": {"QScrollBar ()": {}, "QBoxLayout ()": {}},
            },
            "QSpinBox ()": {
                "value": 10,
                "QLineEdit (qt_spinbox_lineedit)": {"value": "10", "QObject ()": {}},
                "QValidator (qt_spinboxvalidator)": {},
            },
        }
    }
    expected_reduced = {
        "QWidget ()": {
            "QLineEdit ()": {"value": "New Text"},
            "QComboBox ()": {"value": 1},
            "QTableWidget ()": {"value": [["a", "b"], ["c", "d"]]},
            "QSpinBox ()": {"value": 10, "QLineEdit (qt_spinbox_lineedit)": {"value": "10"}},
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

    # Check initial values
    assert WidgetIO.get_value(line_edit) == ""
    assert WidgetIO.get_value(combo_box) == 0  # first index
    assert WidgetIO.get_value(table_widget) == [
        ["Initial A", "Initial B"],
        ["Initial C", "Initial D"],
    ]
    assert WidgetIO.get_value(spin_box) == 0

    # Set new values
    WidgetIO.set_value(line_edit, "Hello")
    WidgetIO.set_value(combo_box, "Option 2")
    WidgetIO.set_value(table_widget, [["X", "Y"], ["Z", "W"]])
    WidgetIO.set_value(spin_box, 5)

    # Check updated values
    assert WidgetIO.get_value(line_edit) == "Hello"
    assert WidgetIO.get_value(combo_box, as_string=True) == "Option 2"
    assert WidgetIO.get_value(table_widget) == [["X", "Y"], ["Z", "W"]]
    assert WidgetIO.get_value(spin_box) == 5


def test_widget_io_signal(qtbot, example_widget):
    # Extract widgets
    line_edit = example_widget.findChild(QLineEdit)
    combo_box = example_widget.findChild(QComboBox)
    spin_box = example_widget.findChild(QSpinBox)
    table_widget = example_widget.findChild(QTableWidget)

    # We'll store changes in a list to verify the slot is called
    changes = []

    def universal_slot(w, val):
        changes.append((w, val))

    # Connect signals
    WidgetIO.connect_widget_change_signal(line_edit, universal_slot)
    WidgetIO.connect_widget_change_signal(combo_box, universal_slot)
    WidgetIO.connect_widget_change_signal(spin_box, universal_slot)
    WidgetIO.connect_widget_change_signal(table_widget, universal_slot)

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
