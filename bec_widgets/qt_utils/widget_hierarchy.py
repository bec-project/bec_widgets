from PyQt5.QtWidgets import (
    QTabWidget,
    QLineEdit,
    QComboBox,
    QTableWidget,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidgetItem,
)


def print_widget_hierarchy(widget, indent: int = 0):
    """
    Print the widget hierarchy to the console.
    Args:
        widget: Widget to print the hierarchy of.
        indent(int): Level of indentation.

    """
    print("  " * indent + f"{widget.__class__.__name__} ({widget.objectName()})")
    for child in widget.children():
        print_widget_hierarchy(child, indent + 1)


def export_config_to_dict(
    widget, config: dict = None, indent: int = 0, grab_values=False, print_hierarchy=False
) -> dict:
    """
    Export the widget hierarchy to a dictionary.
    Args:
        widget: widget to export the hierarchy of.
        config(dict,optional): Dictionary to export the hierarchy to.
        indent(int): Level of indentation.
        grab_values(bool): Whether to grab the values of the widgets.
        print_hierarchy(bool): Whether to print the hierarchy to the console.

    Returns:
        config(dict): Dictionary containing the widget hierarchy.
    """
    if config is None:
        config = {}
    widget_info = f"{widget.__class__.__name__} ({widget.objectName()})"
    config[widget_info] = {}
    if isinstance(widget, QTabWidget):
        config[widget_info]["currentIndex"] = widget.currentIndex()
    if grab_values:
        if isinstance(widget, QLineEdit):
            config[widget_info]["text"] = widget.text()
        elif isinstance(widget, QComboBox):
            config[widget_info]["currentIndex"] = widget.currentIndex()
        elif isinstance(widget, QTableWidget):
            config[widget_info]["tableData"] = [
                [
                    widget.item(row, col).text() if widget.item(row, col) else ""
                    for col in range(widget.columnCount())
                ]
                for row in range(widget.rowCount())
            ]
        elif isinstance(widget, QSpinBox):
            config[widget_info]["value"] = widget.value()
        elif isinstance(widget, QDoubleSpinBox):
            config[widget_info]["value"] = widget.value()

    if print_hierarchy:
        extra_info = ""
        if grab_values:
            if isinstance(widget, QLineEdit):
                extra_info = f" [text: {widget.text()}]"
            elif isinstance(widget, QComboBox):
                extra_info = f" [currentIndex: {widget.currentIndex()}]"
            elif isinstance(widget, QTableWidget):
                extra_info = f" [tableData: {config[widget_info]['tableData']}]"
            elif isinstance(widget, QSpinBox):
                extra_info = f" [value: {widget.value()}]"
            elif isinstance(widget, QDoubleSpinBox):
                extra_info = f" [value: {widget.value()}]"
        print("  " * indent + f"{widget_info}{extra_info}")

    for child in widget.children():
        export_config_to_dict(
            child,
            config=config,
            indent=indent + 1,
            grab_values=grab_values,
            print_hierarchy=print_hierarchy,
        )
    return config


def import_config_from_dict(widget, config, grab_values=False):  # TODO decide if useful
    widget_name = f"{widget.__class__.__name__} ({widget.objectName()})"
    widget_config = config.get(widget_name, {})
    for child in widget.children():
        child_name = f"{child.__class__.__name__} ({child.objectName()})"
        child_config = widget_config.get(child_name)
        if child_config is not None:
            if isinstance(child, QTabWidget):
                child.setCurrentIndex(child_config.get("currentIndex", 0))
                for i in range(child.count()):
                    tab = child.widget(i)
                    import_config_from_dict(tab, widget_config, grab_values)
            else:
                import_config_from_dict(child, widget_config, grab_values)

            if grab_values:
                if isinstance(child, QLineEdit):
                    child.setText(child_config.get("text", ""))
                elif isinstance(child, QComboBox):
                    child.setCurrentIndex(child_config.get("currentIndex", 0))
                elif isinstance(child, QTableWidget):
                    table_values = child_config.get("tableValues", [])
                    for row, row_values in enumerate(table_values):
                        for col, value in enumerate(row_values):
                            item = QTableWidgetItem(str(value))
                            child.setItem(row, col, item)
                elif isinstance(child, QSpinBox):
                    child.setValue(child_config.get("value", 0))
                elif isinstance(child, QDoubleSpinBox):
                    child.setValue(child_config.get("value", 0.0))
