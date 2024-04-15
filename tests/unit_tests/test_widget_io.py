# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import pytest
from qtpy.QtWidgets import QComboBox, QLineEdit, QSpinBox, QTableWidget, QVBoxLayout, QWidget

from bec_widgets.utils.widget_io import WidgetHierarchy


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
