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


class WidgetHandler:
    @staticmethod
    def get_value(widget):
        raise NotImplementedError

    @staticmethod
    def set_value(widget, value):
        raise NotImplementedError


class LineEditHandler(WidgetHandler):
    @staticmethod
    def get_value(widget):
        return widget.text()

    @staticmethod
    def set_value(widget, value):
        widget.setText(value)


class ComboBoxHandler(WidgetHandler):
    @staticmethod
    def get_value(widget):
        return widget.currentIndex()

    @staticmethod
    def set_value(widget, value):
        widget.setCurrentIndex(value)


class TableWidgetHandler(WidgetHandler):
    @staticmethod
    def get_value(widget):
        return [
            [
                widget.item(row, col).text() if widget.item(row, col) else ""
                for col in range(widget.columnCount())
            ]
            for row in range(widget.rowCount())
        ]

    @staticmethod
    def set_value(widget, value):
        for row, row_values in enumerate(value):
            for col, cell_value in enumerate(row_values):
                item = QTableWidgetItem(str(cell_value))
                widget.setItem(row, col, item)


class SpinBoxHandler(WidgetHandler):
    @staticmethod
    def get_value(widget):
        return widget.value()

    @staticmethod
    def set_value(widget, value):
        widget.setValue(value)


HANDLERS = {
    QLineEdit: LineEditHandler,
    QComboBox: ComboBoxHandler,
    QTableWidget: TableWidgetHandler,
    QSpinBox: SpinBoxHandler,
    QDoubleSpinBox: SpinBoxHandler,
}


def get_value(widget):
    handler_class = HANDLERS.get(type(widget))
    if handler_class:
        return handler_class.get_value(widget)
    return None


def set_value(widget, value):
    handler_class = HANDLERS.get(type(widget))
    if handler_class:
        handler_class.set_value(widget, value)


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
        value = get_value(widget)
        value_str = f" [value: {value}]" if value is not None else ""
        widget_info += value_str

    print(prefix + widget_info)

    children = widget.children()
    for child in children:
        child_prefix = prefix + "  "
        arrow = "├─ " if child != children[-1] else "└─ "
        print_widget_hierarchy(child, indent + 1, grab_values, prefix=child_prefix + arrow)


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

    if grab_values:
        value = get_value(widget)
        if value is not None or save_all:
            if widget_info not in config:
                config[widget_info] = {}
            if value is not None:
                config[widget_info]["value"] = value

    if print_hierarchy:
        print_widget_hierarchy(widget, indent, grab_values)

    for child in widget.children():
        child_config = export_config_to_dict(
            child, None, indent + 1, grab_values, print_hierarchy, save_all
        )
        if child_config or save_all:
            if widget_info not in config:
                config[widget_info] = {}
            config[widget_info].update(child_config)

    return config


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
                set_value(child, value)
            import_config_from_dict(child, widget_config, set_values)


# Example application to demonstrate the usage of the functions
if __name__ == "__main__":
    app = QApplication([])

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
    config_dict = export_config_to_dict(main_widget, grab_values=True, print_hierarchy=True)
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
    import_config_from_dict(main_widget, new_config_dict, set_values=True)
    print(30 * "#")
    config_dict_new = export_config_to_dict(main_widget, grab_values=True, print_hierarchy=True)
    config_dict_new_reduced = export_config_to_dict(
        main_widget, grab_values=True, print_hierarchy=True, save_all=False
    )
    print(30 * "#")
    print(f"Config dict new FULL: {config_dict_new}")
    print(f"Config dict new REDUCED: {config_dict_new_reduced}")

    app.exec()
