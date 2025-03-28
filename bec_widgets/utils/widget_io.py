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

from bec_widgets.utils.bec_widget import BECWidget
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
        # Decide if this particular widget is to be printed
        is_bec = isinstance(widget, BECWidget)
        print_this = (not only_bec_widgets) or is_bec

        # If it is a BECWidget and we're showing the parent, climb the chain to find the nearest BECWidget ancestor
        if show_parent and is_bec:
            ancestor = WidgetHierarchy._get_becwidget_ancestor(widget)
            if ancestor is not None:
                parent_info = f" parent={ancestor.__class__.__name__}"
            else:
                parent_info = " parent=None"
        else:
            parent_info = ""

        if print_this:
            widget_info = f"{widget.__class__.__name__} ({widget.objectName()}){parent_info}"
            if grab_values:
                value = WidgetIO.get_value(widget, ignore_errors=True)
                value_str = f" [value: {value}]" if value is not None else ""
                widget_info += value_str
            print(prefix + widget_info)

        # Always recurse so we can discover deeper BECWidgets even if the current widget is not a BECWidget
        children = widget.children()
        for i, child in enumerate(children):
            # Possibly skip known internal child widgets of a QComboBox
            if (
                exclude_internal_widgets
                and isinstance(widget, QComboBox)
                and child.__class__.__name__ in ["QFrame", "QBoxLayout", "QListView"]
            ):
                continue

            child_prefix = prefix + "  "
            arrow = "├─ " if child != children[-1] else "└─ "

            # Regardless of whether child is BECWidget or not, keep recursing, or we might miss deeper BECWidgets
            WidgetHierarchy.print_widget_hierarchy(
                child,
                indent + 1,
                grab_values=grab_values,
                prefix=child_prefix + arrow,
                exclude_internal_widgets=exclude_internal_widgets,
                only_bec_widgets=only_bec_widgets,
                show_parent=show_parent,
            )

    @staticmethod
    def _get_becwidget_ancestor(widget):
        """
        Climb the parent chain to find the nearest BECWidget above this widget.
        Returns None if none is found.
        """
        parent = widget.parent()
        while parent is not None:
            if isinstance(parent, BECWidget):
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
