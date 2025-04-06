# pylint: disable=no-name-in-module
from __future__ import annotations

from abc import ABC, abstractmethod

from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch


class WidgetHandler(ABC):
    """Abstract base class for all widget handlers."""

    @abstractmethod
    def get_value(self, widget: QWidget, **kwargs):
        """Retrieve value from the widget instance."""

    @abstractmethod
    def set_value(self, widget: QWidget, value):
        """Set a value on the widget instance."""

    def connect_change_signal(self, widget: QWidget, slot):
        """
        Connect a change signal from this widget to the given slot.
        If the widget type doesn't have a known "value changed" signal, do nothing.

        slot: a function accepting two arguments (widget, value)
        """
        pass


class LineEditHandler(WidgetHandler):
    """Handler for QLineEdit widgets."""

    def get_value(self, widget: QLineEdit, **kwargs) -> str:
        return widget.text()

    def set_value(self, widget: QLineEdit, value: str) -> None:
        widget.setText(value)

    def connect_change_signal(self, widget: QLineEdit, slot):
        widget.textChanged.connect(lambda text, w=widget: slot(w, text))


class ComboBoxHandler(WidgetHandler):
    """Handler for QComboBox widgets."""

    def get_value(self, widget: QComboBox, as_string: bool = False, **kwargs) -> int | str:
        if as_string is True:
            return widget.currentText()
        return widget.currentIndex()

    def set_value(self, widget: QComboBox, value: int | str) -> None:
        if isinstance(value, str):
            value = widget.findText(value)
        if isinstance(value, int):
            widget.setCurrentIndex(value)

    def connect_change_signal(self, widget: QComboBox, slot):
        # currentIndexChanged(int) or currentIndexChanged(str) both possible.
        # We use currentIndexChanged(int) for a consistent behavior.
        widget.currentIndexChanged.connect(lambda idx, w=widget: slot(w, self.get_value(w)))


class TableWidgetHandler(WidgetHandler):
    """Handler for QTableWidget widgets."""

    def get_value(self, widget: QTableWidget, **kwargs) -> list:
        return [
            [
                widget.item(row, col).text() if widget.item(row, col) else ""
                for col in range(widget.columnCount())
            ]
            for row in range(widget.rowCount())
        ]

    def set_value(self, widget: QTableWidget, value) -> None:
        for row, row_values in enumerate(value):
            for col, cell_value in enumerate(row_values):
                item = QTableWidgetItem(str(cell_value))
                widget.setItem(row, col, item)

    def connect_change_signal(self, widget: QTableWidget, slot):
        # If desired, we could connect cellChanged(row, col) and then fetch all data.
        # This might be noisy if table is large.
        # For demonstration, connect cellChanged to update entire table value.
        def on_cell_changed(row, col, w=widget):
            val = self.get_value(w)
            slot(w, val)

        widget.cellChanged.connect(on_cell_changed)


class SpinBoxHandler(WidgetHandler):
    """Handler for QSpinBox and QDoubleSpinBox widgets."""

    def get_value(self, widget: QSpinBox | QDoubleSpinBox, **kwargs):
        return widget.value()

    def set_value(self, widget: QSpinBox | QDoubleSpinBox, value):
        widget.setValue(value)

    def connect_change_signal(self, widget: QSpinBox | QDoubleSpinBox, slot):
        widget.valueChanged.connect(lambda val, w=widget: slot(w, val))


class CheckBoxHandler(WidgetHandler):
    """Handler for QCheckBox widgets."""

    def get_value(self, widget: QCheckBox, **kwargs):
        return widget.isChecked()

    def set_value(self, widget: QCheckBox, value):
        widget.setChecked(value)

    def connect_change_signal(self, widget: QCheckBox, slot):
        widget.toggled.connect(lambda val, w=widget: slot(w, val))


class SlideHandler(WidgetHandler):
    """Handler for QCheckBox widgets."""

    def get_value(self, widget: QSlider, **kwargs):
        return widget.value()

    def set_value(self, widget: QSlider, value):
        widget.setValue(value)

    def connect_change_signal(self, widget: QSlider, slot):
        widget.valueChanged.connect(lambda val, w=widget: slot(w, val))


class ToggleSwitchHandler(WidgetHandler):
    """Handler for ToggleSwitch widgets."""

    def get_value(self, widget: ToggleSwitch, **kwargs):
        return widget.checked

    def set_value(self, widget: ToggleSwitch, value):
        widget.checked = value

    def connect_change_signal(self, widget: ToggleSwitch, slot):
        widget.enabled.connect(lambda val, w=widget: slot(w, val))


class LabelHandler(WidgetHandler):
    """Handler for QLabel widgets."""

    def get_value(self, widget: QLabel, **kwargs):
        return widget.text()

    def set_value(self, widget: QLabel, value):
        widget.setText(value)

    # QLabel typically doesn't have user-editable changes. No signal to connect.
    # If needed, this can remain empty.


class WidgetIO:
    """Public interface for getting, setting values and connecting signals using handler mapping"""

    _handlers = {
        QLineEdit: LineEditHandler,
        QComboBox: ComboBoxHandler,
        QTableWidget: TableWidgetHandler,
        QSpinBox: SpinBoxHandler,
        QDoubleSpinBox: SpinBoxHandler,
        QCheckBox: CheckBoxHandler,
        QLabel: LabelHandler,
        ToggleSwitch: ToggleSwitchHandler,
        QSlider: SlideHandler,
    }

    @staticmethod
    def get_value(widget, ignore_errors=False, **kwargs):
        """
        Retrieve value from the widget instance.

        Args:
            widget: Widget instance.
            ignore_errors(bool, optional): Whether to ignore if no handler is found.
        """
        handler_class = WidgetIO._find_handler(widget)
        if handler_class:
            return handler_class().get_value(widget, **kwargs)  # Instantiate the handler
        if not ignore_errors:
            raise ValueError(f"No handler for widget type: {type(widget)}")
        return None

    @staticmethod
    def set_value(widget, value, ignore_errors=False):
        """
        Set a value on the widget instance.

        Args:
            widget: Widget instance.
            value: Value to set.
            ignore_errors(bool, optional): Whether to ignore if no handler is found.
        """
        handler_class = WidgetIO._find_handler(widget)
        if handler_class:
            handler_class().set_value(widget, value)  # Instantiate the handler
        elif not ignore_errors:
            raise ValueError(f"No handler for widget type: {type(widget)}")

    @staticmethod
    def connect_widget_change_signal(widget, slot):
        """
        Connect the widget's value-changed signal to a generic slot function (widget, value).
        This now delegates the logic to the widget's handler.
        """
        handler_class = WidgetIO._find_handler(widget)
        if handler_class:
            handler = handler_class()
            handler.connect_change_signal(widget, slot)

    @staticmethod
    def check_and_adjust_limits(spin_box: QDoubleSpinBox, number: float):
        """
        Check if the new limits are within the current limits, if not adjust the limits.

        Args:
            number(float): The new value to check against the limits.
        """

        min_value = spin_box.minimum()
        max_value = spin_box.maximum()

        # Calculate the new limits
        new_limit = number + 5 * number

        if number < min_value:
            spin_box.setMinimum(new_limit)
        elif number > max_value:
            spin_box.setMaximum(new_limit)

    @staticmethod
    def _find_handler(widget):
        """
        Find the appropriate handler for the widget by checking its base classes.

        Args:
            widget: Widget instance.

        Returns:
            handler_class: The handler class if found, otherwise None.
        """
        for base in type(widget).__mro__:
            if base in WidgetIO._handlers:
                return WidgetIO._handlers[base]
        return None


################## for exporting and importing widget hierarchies ##################


class WidgetHierarchy:
    @staticmethod
    def print_widget_hierarchy(
        widget,
        indent: int = 0,
        grab_values: bool = False,
        prefix: str = "",
        exclude_internal_widgets: bool = True,
        only_bec_widgets: bool = False,
        show_parent: bool = True,
    ) -> None:
        """
        Print the widget hierarchy to the console.

        Args:
            widget: Widget to print the hierarchy of.
            indent(int, optional): Level of indentation.
            grab_values(bool,optional): Whether to grab the values of the widgets.
            prefix(str,optional): Custom string prefix for indentation.
            exclude_internal_widgets(bool,optional): Whether to exclude internal widgets (e.g. QComboBox in PyQt6).
            only_bec_widgets(bool, optional): Whether to print only widgets that are instances of BECWidget.
            show_parent(bool, optional): Whether to display which BECWidget is the parent of each discovered BECWidget.
        """
        from bec_widgets.utils import BECConnector
        from bec_widgets.widgets.plots.waveform.waveform import Waveform

        # 1) Filter out widgets that are not BECConnectors (if 'only_bec_widgets' is True)
        is_bec = isinstance(widget, BECConnector)
        if only_bec_widgets and not is_bec:
            return

        # 2) Determine and print the parent's info (closest BECConnector)
        parent_info = ""
        if show_parent and is_bec:
            ancestor = WidgetHierarchy._get_becwidget_ancestor(widget)
            if ancestor:
                parent_label = ancestor.objectName() or ancestor.__class__.__name__
                parent_info = f" parent={parent_label}"
            else:
                parent_info = " parent=None"

        widget_info = f"{widget.__class__.__name__} ({widget.objectName()}){parent_info}"
        print(prefix + widget_info)

        # 3) If it's a Waveform, explicitly print the curves
        if isinstance(widget, Waveform):
            for curve in widget.curves:
                curve_prefix = prefix + "  └─ "
                print(
                    f"{curve_prefix}{curve.__class__.__name__} ({curve.objectName()}) "
                    f"parent={widget.objectName()}"
                )

        # 4) Recursively handle each child if:
        #    - It's a QWidget
        #    - It is a BECConnector (or we don't care about filtering)
        #    - Its closest BECConnector parent is the current widget
        for child in widget.findChildren(QWidget):
            if only_bec_widgets and not isinstance(child, BECConnector):
                continue

            # if WidgetHierarchy._get_becwidget_ancestor(child) == widget:
            child_prefix = prefix + "  └─ "
            WidgetHierarchy.print_widget_hierarchy(
                child,
                indent=indent + 1,
                grab_values=grab_values,
                prefix=child_prefix,
                exclude_internal_widgets=exclude_internal_widgets,
                only_bec_widgets=only_bec_widgets,
                show_parent=show_parent,
            )

    @staticmethod
    def print_becconnector_hierarchy_from_app():
        """
        Enumerate ALL BECConnector objects in the QApplication.
        Also detect if a widget is a PlotBase, and add any data items
        (PlotDataItem-like) that are also BECConnector objects.

        Build a parent->children graph where each child's 'parent'
        is its closest BECConnector ancestor. Print the entire hierarchy
        from the root(s).

        The result is a single, consolidated tree for your entire
        running GUI, including PlotBase data items that are BECConnector.
        """
        import sys
        from collections import defaultdict

        from qtpy.QtWidgets import QApplication

        from bec_widgets.utils import BECConnector
        from bec_widgets.widgets.plots.plot_base import PlotBase

        # 1) Gather ALL QWidget-based BECConnector objects
        all_qwidgets = QApplication.allWidgets()
        bec_widgets = set(w for w in all_qwidgets if isinstance(w, BECConnector))

        # 2) Also gather any BECConnector-based data items from PlotBase widgets
        for w in all_qwidgets:
            if isinstance(w, PlotBase) and hasattr(w, "plot_item"):
                plot_item = w.plot_item
                if hasattr(plot_item, "listDataItems"):
                    for data_item in plot_item.listDataItems():
                        if isinstance(data_item, BECConnector):
                            bec_widgets.add(data_item)

        # 3) Build a map of (closest BECConnector parent) -> list of children
        parent_map = defaultdict(list)
        for w in bec_widgets:
            parent_bec = WidgetHierarchy._get_becwidget_ancestor(w)
            parent_map[parent_bec].append(w)

        # 4) Define a recursive printer to show each object's children
        def print_tree(parent, prefix=""):
            children = parent_map[parent]
            for i, child in enumerate(children):
                connector_class = child.__class__.__name__
                connector_name = child.objectName() or connector_class

                if parent is None:
                    parent_label = "None"
                else:
                    parent_label = parent.objectName() or parent.__class__.__name__

                line = f"{connector_class} ({connector_name}) parent={parent_label}"
                # Determine tree-branch symbols
                is_last = i == len(children) - 1
                branch_str = "└─ " if is_last else "├─ "
                print(prefix + branch_str + line)

                # Recurse deeper
                next_prefix = prefix + ("   " if is_last else "│  ")
                print_tree(child, prefix=next_prefix)

        # 5) Print top-level items (roots) whose BECConnector parent is None
        roots = parent_map[None]
        for r_i, root in enumerate(roots):
            root_class = root.__class__.__name__
            root_name = root.objectName() or root_class
            line = f"{root_class} ({root_name}) parent=None"
            is_last_root = r_i == len(roots) - 1
            print(line)
            # Recurse into its children
            print_tree(root, prefix="   ")

    @staticmethod
    def _get_becwidget_ancestor(widget):
        """
        Traverse up the parent chain to find the nearest BECConnector.
        Returns None if none is found.
        """
        from bec_widgets.utils import BECConnector

        parent = widget.parent()
        while parent is not None:
            if isinstance(parent, BECConnector):
                return parent
            parent = parent.parent()
        return None

    @staticmethod
    def export_config_to_dict(
        widget: QWidget,
        config: dict = None,
        indent: int = 0,
        grab_values: bool = False,
        print_hierarchy: bool = False,
        save_all: bool = True,
        exclude_internal_widgets: bool = True,
    ) -> dict:
        """
        Export the widget hierarchy to a dictionary.

        Args:
            widget: Widget to print the hierarchy of.
            config(dict,optional): Dictionary to export the hierarchy to.
            indent(int,optional): Level of indentation.
            grab_values(bool,optional): Whether to grab the values of the widgets.
            print_hierarchy(bool,optional): Whether to print the hierarchy to the console.
            save_all(bool,optional): Whether to save all widgets or only those with values.
            exclude_internal_widgets(bool,optional): Whether to exclude internal widgets (e.g. QComboBox in PyQt6).
        Returns:
            config(dict): Dictionary containing the widget hierarchy.
        """
        if config is None:
            config = {}
        widget_info = f"{widget.__class__.__name__} ({widget.objectName()})"

        # if grab_values and type(widget) in WidgetIO._handlers:
        if grab_values:
            value = WidgetIO.get_value(widget, ignore_errors=True)
            if value is not None or save_all:
                if widget_info not in config:
                    config[widget_info] = {}
                if value is not None:
                    config[widget_info]["value"] = value

        if print_hierarchy:
            WidgetHierarchy.print_widget_hierarchy(widget, indent, grab_values)

        for child in widget.children():
            # Skip internal widgets of QComboBox in PyQt6
            if (
                exclude_internal_widgets
                and isinstance(widget, QComboBox)
                and child.__class__.__name__ in ["QFrame", "QBoxLayout", "QListView"]
            ):
                continue
            child_config = WidgetHierarchy.export_config_to_dict(
                child, None, indent + 1, grab_values, print_hierarchy, save_all
            )
            if child_config or save_all:
                if widget_info not in config:
                    config[widget_info] = {}
                config[widget_info].update(child_config)

        return config

    @staticmethod
    def import_config_from_dict(widget, config: dict, set_values: bool = False) -> None:
        """
        Import the widget hierarchy from a dictionary.

        Args:
            widget: Widget to import the hierarchy to.
            config:
            set_values:
        """
        widget_name = f"{widget.__class__.__name__} ({widget.objectName()})"
        widget_config = config.get(widget_name, {})
        for child in widget.children():
            child_name = f"{child.__class__.__name__} ({child.objectName()})"
            child_config = widget_config.get(child_name)
            if child_config is not None:
                value = child_config.get("value")
                if set_values and value is not None:
                    WidgetIO.set_value(child, value)
                WidgetHierarchy.import_config_from_dict(child, widget_config, set_values)


# Example usage
def hierarchy_example():  # pragma: no cover
    app = QApplication([])

    # Create instance of WidgetHierarchy
    widget_hierarchy = WidgetHierarchy()

    # Create a simple widget hierarchy for demonstration purposes
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

    main_widget.show()

    # Hierarchy of original widget
    print(30 * "#")
    print(f"Widget hierarchy for {main_widget.objectName()}:")
    print(30 * "#")
    config_dict = widget_hierarchy.export_config_to_dict(
        main_widget, grab_values=True, print_hierarchy=True
    )
    print(30 * "#")
    print(f"Config dict: {config_dict}")

    # Hierarchy of new widget and set values
    new_config_dict = {
        "QWidget ()": {
            "QLineEdit ()": {"value": "New Text"},
            "QComboBox ()": {"value": 1},
            "QTableWidget ()": {"value": [["a", "b"], ["c", "d"]]},
            "QSpinBox ()": {"value": 10},
        }
    }
    widget_hierarchy.import_config_from_dict(main_widget, new_config_dict, set_values=True)
    print(30 * "#")
    config_dict_new = widget_hierarchy.export_config_to_dict(
        main_widget, grab_values=True, print_hierarchy=True
    )
    config_dict_new_reduced = widget_hierarchy.export_config_to_dict(
        main_widget, grab_values=True, print_hierarchy=True, save_all=False
    )
    print(30 * "#")
    print(f"Config dict new FULL: {config_dict_new}")
    print(f"Config dict new REDUCED: {config_dict_new_reduced}")

    app.exec()


def widget_io_signal_example():  # pragma: no cover
    app = QApplication([])

    main_widget = QWidget()
    layout = QVBoxLayout(main_widget)
    line_edit = QLineEdit(main_widget)
    combo_box = QComboBox(main_widget)
    spin_box = QSpinBox(main_widget)
    combo_box.addItems(["Option 1", "Option 2", "Option 3"])

    layout.addWidget(line_edit)
    layout.addWidget(combo_box)
    layout.addWidget(spin_box)

    main_widget.show()

    def universal_slot(w, val):
        print(f"Widget {w.objectName() or w} changed, new value: {val}")

    # Connect all supported widgets through their handlers
    WidgetIO.connect_widget_change_signal(line_edit, universal_slot)
    WidgetIO.connect_widget_change_signal(combo_box, universal_slot)
    WidgetIO.connect_widget_change_signal(spin_box, universal_slot)

    app.exec_()


if __name__ == "__main__":  # pragma: no cover
    # Change example function to test different scenarios

    # hierarchy_example()
    widget_io_signal_example()
