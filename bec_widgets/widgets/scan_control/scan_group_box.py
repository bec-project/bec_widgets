from typing import Literal

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
)
from qtpy.QtWidgets import QGroupBox

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets import DeviceLineEdit


class ScanArgType:
    DEVICE = "device"
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STR = "str"
    DEVICEBASE = "DeviceBase"
    LITERALS = "dict"


class ScanSpinBox(QSpinBox):
    def __init__(
        self, parent=None, arg_name: str = None, default: int | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        self.setRange(-9999, 9999)
        if default is not None:
            self.setValue(default)


class ScanDoubleSpinBox(QDoubleSpinBox):
    def __init__(
        self, parent=None, arg_name: str = None, default: float | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        self.setRange(-9999, 9999)
        if default is not None:
            self.setValue(default)


class ScanLineEdit(QLineEdit):
    def __init__(
        self, parent=None, arg_name: str = None, default: str | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        if default is not None:
            self.setText(default)


class ScanCheckBox(QCheckBox):
    def __init__(
        self, parent=None, arg_name: str = None, default: bool | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        if default is not None:
            self.setChecked(default)


class ScanGroupBox(QGroupBox):
    WIDGET_HANDLER = {
        ScanArgType.DEVICE: DeviceLineEdit,
        ScanArgType.DEVICEBASE: DeviceLineEdit,
        ScanArgType.FLOAT: ScanDoubleSpinBox,
        ScanArgType.INT: ScanSpinBox,
        ScanArgType.BOOL: ScanCheckBox,
        ScanArgType.STR: ScanLineEdit,
        ScanArgType.LITERALS: QComboBox,  # TODO figure out combobox logic
    }

    def __init__(
        self,
        parent=None,
        box_type=Literal["args", "kwargs"],
        config: dict | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.config = config
        self.box_type = box_type

        self.layout = QGridLayout(self)
        self.labels = []
        self.widgets = []

        self.init_box(self.config)

    def init_box(self, config: dict):
        box_name = config.get("name", "ScanGroupBox")
        self.inputs = config.get("inputs", {})
        self.setTitle(box_name)

        # Labels
        self.add_input_labels(self.inputs, 0)

        # Widgets
        self.add_input_widgets(self.inputs, 1)

    def add_input_labels(self, group_inputs: dict, row: int) -> None:
        """
        Adds the given arg_group from arg_bundle to the scan control layout. The input labels are always added to the first row.

        Args:
            group(dict): Dictionary containing the arg_group information.
        """
        for column_index, item in enumerate(group_inputs):
            arg_name = item.get("name", None)
            display_name = item.get("display_name", arg_name)
            label = QLabel(text=display_name)
            self.layout.addWidget(label, row, column_index)
            self.labels.append(label)

    def add_input_widgets(self, group_inputs: dict, row) -> None:
        """
        Adds the given arg_group from arg_bundle to the scan control layout.

        Args:
            group_inputs(dict): Dictionary containing the arg_group information.
            row(int): The row to add the widgets to.
        """
        for column_index, item in enumerate(group_inputs):
            arg_name = item.get("name", None)
            default = item.get("default", None)
            widget = self.WIDGET_HANDLER.get(item["type"], None)
            if widget is None:
                print(f"Unsupported annotation '{item['type']}' for parameter '{item['name']}'")
                continue
            if default == "_empty":
                default = None
            widget_to_add = widget(arg_name=arg_name, default=default)
            tooltip = item.get("tooltip", None)
            if tooltip is not None:
                widget_to_add.setToolTip(item["tooltip"])
            self.layout.addWidget(widget_to_add, row, column_index)
            self.widgets.append(widget_to_add)

    def add_widget_bundle(self):
        """
        Adds a new row of widgets to the scan control layout. Only usable for arg_groups.
        """
        if self.box_type != "args":
            return
        arg_max = self.config.get("max", None)
        row = self.layout.rowCount()
        if arg_max is not None and row >= arg_max:
            return

        self.add_input_widgets(self.inputs, row)

    def remove_widget_bundle(self):
        """
        Removes the last row of widgets from the scan control layout. Only usable for arg_groups.
        """
        if self.box_type != "args":
            return
        arg_min = self.config.get("min", None)
        row = self.layout.rowCount()
        if arg_min is not None and row <= arg_min + 1:
            return

        for widget in self.widgets[-len(self.inputs) :]:
            widget.deleteLater()
        self.widgets = self.widgets[: -len(self.inputs)]

    def get_parameters(self):
        """
        Returns the parameters from the widgets in the scan control layout formated to run scan from BEC.
        """
        if self.box_type == "args":
            print(self._get_arg_parameterts())
            return self._get_arg_parameterts()
        elif self.box_type == "kwargs":
            print(self._get_kwarg_parameters())
            return self._get_kwarg_parameters()

    def _get_arg_parameterts(self):
        args = []
        for i in range(1, self.layout.rowCount()):
            for j in range(self.layout.columnCount()):
                widget = self.layout.itemAtPosition(i, j).widget()
                if isinstance(widget, DeviceLineEdit):
                    value = widget.get_device()
                else:
                    value = WidgetIO.get_value(widget)
                args.append(value)
        return args

    def _get_kwarg_parameters(self):
        kwargs = {}
        for i in range(self.layout.columnCount()):
            widget = self.layout.itemAtPosition(1, i).widget()
            if isinstance(widget, DeviceLineEdit):
                value = widget.get_device()
            else:
                value = WidgetIO.get_value(widget)
            kwargs[widget.arg_name] = value
        return kwargs
