from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLineEdit,
    QComboBox,
    QTableWidget,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
)

from abc import ABC, abstractmethod


class WidgetHandler(ABC):
    """Abstract base class for all widget handlers."""

    @abstractmethod
    def get_value(self, widget: QWidget):
        """Retrieve value from the widget instance."""
        pass

    @abstractmethod
    def set_value(self, widget: QWidget, value):
        """Set a value on the widget instance."""
        pass


class LineEditHandler(WidgetHandler):
    def get_value(self, widget: QLineEdit) -> str:
        return widget.text()

    def set_value(self, widget: QLineEdit, value: str) -> None:
        widget.setText(value)


class ComboBoxHandler(WidgetHandler):
    def get_value(self, widget: QComboBox) -> int:
        return widget.currentIndex()

    def set_value(self, widget: QComboBox, value: int) -> None:
        widget.setCurrentIndex(value)


class TableWidgetHandler(WidgetHandler):
    def get_value(self, widget: QTableWidget) -> list:
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


class SpinBoxHandler(WidgetHandler):
    def get_value(self, widget):
        return widget.value()

    def set_value(self, widget, value):
        widget.setValue(value)


# TODO remove when widgetIO works
# HANDLERS = {
#     QLineEdit: LineEditHandler,
#     QComboBox: ComboBoxHandler,
#     QTableWidget: TableWidgetHandler,
#     QSpinBox: SpinBoxHandler,
#     QDoubleSpinBox: SpinBoxHandler,
# }
#

##################### Public interface for getting and setting values #####################
# def get_value(widget):
#     handler_class = HANDLERS.get(type(widget))
#     if handler_class:
#         return handler_class.get_value(widget)
#     return None
#
#
# def set_value(widget, value):
#     handler_class = HANDLERS.get(type(widget))
#     if handler_class:
#         handler_class.set_value(widget, value)


class WidgetIO:
    """Public interface for getting and setting values using handler mapping"""

    _handlers = {
        QLineEdit: LineEditHandler,
        QComboBox: ComboBoxHandler,
        QTableWidget: TableWidgetHandler,
        QSpinBox: SpinBoxHandler,
        QDoubleSpinBox: SpinBoxHandler,
    }

    @staticmethod
    def get_value(widget, ignore_errors=False):
        """
        Retrieve value from the widget instance.
        Args:
            widget: Widget instance.
            ignore_errors(bool, optional): Whether to ignore if no handler is found.
        """
        handler_class = WidgetIO._handlers.get(type(widget))
        if handler_class:
            return handler_class().get_value(widget)  # Instantiate the handler
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
        handler_class = WidgetIO._handlers.get(type(widget))
        if handler_class:
            handler_class().set_value(widget, value)  # Instantiate the handler
        elif not ignore_errors:
            raise ValueError(f"No handler for widget type: {type(widget)}")


##################### Public interface for exporting and importing widget hierarchies #####################


class WidgetHierarchy:
    @staticmethod
    def print_widget_hierarchy(
        widget, indent: int = 0, grab_values: bool = False, prefix: str = ""
    ) -> None:
        """
        Print the widget hierarchy to the console.
        Args:
            widget: Widget to print the hierarchy of.
            indent(int, optional): Level of indentation.
            grab_values(bool,optional): Whether to grab the values of the widgets.
            prefix(stc,optional): Custom string prefix for indentation.
        """
        widget_info = f"{widget.__class__.__name__} ({widget.objectName()})"
        if grab_values:
            value = WidgetIO.get_value(widget, ignore_errors=True)
            value_str = f" [value: {value}]" if value is not None else ""
            widget_info += value_str

        print(prefix + widget_info)

        children = widget.children()
        for child in children:
            child_prefix = prefix + "  "
            arrow = "├─ " if child != children[-1] else "└─ "
            WidgetHierarchy.print_widget_hierarchy(
                child, indent + 1, grab_values, prefix=child_prefix + arrow
            )

    @staticmethod
    def export_config_to_dict(
        widget,
        config=None,
        indent=0,
        grab_values: bool = False,
        print_hierarchy: bool = False,
        save_all: bool = True,
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


# Example application to demonstrate the usage of the functions
if __name__ == "__main__":
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
