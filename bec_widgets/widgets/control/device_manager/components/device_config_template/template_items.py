"""Module for custom input widgets used in device configuration templates."""

from ast import literal_eval
from typing import Any, Callable

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from pydantic import BaseModel, ConfigDict
from qtpy import QtWidgets

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.widgets.control.scan_control.scan_group_box import ScanDoubleSpinBox
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch

logger = bec_logger.logger


def _try_literal_eval(value: str) -> Any:
    """Consolidated function for literal evaluation of a value."""
    if value in ["true", "True"]:
        return True
    if value in ["false", "False"]:
        return False
    if value == "":
        return ""
    try:
        return literal_eval(f"{value}")
    except ValueError:
        return value
    except Exception:
        logger.warning(f"Could not literal_eval value: {value}, returning as string")
        return value


class InputLineEdit(QtWidgets.QLineEdit):
    """
    Custom QLineEdit for input fields with validation.

    Args:
        parent (QtWidgets.QWidget, optional): Parent widget. Defaults to None.
        config_field (str, optional): Configuration field name. Defaults to "no_field_specified"
        required (bool, optional): Whether the field is required. Defaults to True.
        placeholder_text (str, optional): Placeholder text for the input field. Defaults to "".
    """

    def __init__(
        self,
        parent=None,
        config_field: str = "no_field_specified",
        required: bool = True,
        placeholder_text: str = "",
    ):
        super().__init__(parent)
        self._config_field = config_field
        self._colors = get_accent_colors()
        self._required = required
        self.textChanged.connect(self._update_input_field_style)
        self._validation_callbacks: list[Callable[[bool], str]] = []
        self.setPlaceholderText(placeholder_text)
        self._update_input_field_style()

    def register_validation_callback(self, callback: Callable[[str], bool]) -> None:
        """
        Register a custom validation callback.

        Args:
            callback (Callable[[str], bool]): A function that takes the input string
                and returns True if valid, False otherwise.
        """
        self._validation_callbacks.append(callback)

    def apply_theme(self, theme: str) -> None:
        """Apply the theme to the widget."""
        self._colors = get_accent_colors()
        self._update_input_field_style()

    def _update_input_field_style(self) -> None:
        """Update the input field style based on validation."""
        name = self.text()
        if not self.is_valid_input(name) and self._required is True:
            self.setStyleSheet(f"border: 1px solid {self._colors.emergency.name()};")
            return
        self.setStyleSheet("")
        return

    def is_valid_input(self, name: str) -> bool:
        """Validate the input string using plugin helper."""
        name = name.strip()  # Remove leading/trailing whitespace
        # Run registered validation callbacks
        for callback in self._validation_callbacks:
            try:
                valid = callback(name)
            except Exception as exc:
                logger.warning(
                    f"Validation callback raised an exception: {exc}. Defaulting to valid"
                )
                valid = True
            if not valid:
                return False
        if not self._required:
            return True
        if not name:
            return False
        return True


class OnFailureComboBox(QtWidgets.QComboBox):
    """Custom QComboBox for the onFailure input field."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems(["buffer", "retry", "raise"])


class ReadoutPriorityComboBox(QtWidgets.QComboBox):
    """Custom QComboBox for the readoutPriority input field."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems(["monitored", "baseline", "async", "continuous", "on_request"])


class LimitInputWidget(QtWidgets.QWidget):
    """Custom widget for inputting limits as a tuple (min, max)."""

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        # Colors
        self._colors = get_accent_colors()

        self.min_input = ScanDoubleSpinBox(self, arg_name="min_limit", default=0.0)
        self.min_input.setPrefix("Min: ")
        self.min_input.setEnabled(False)
        self.min_input.setRange(-1e12, 1e12)
        self._layout.addWidget(self.min_input)

        self.max_input = ScanDoubleSpinBox(self, arg_name="max_limit", default=0.0)
        self.max_input.setPrefix("Max: ")
        self.max_input.setRange(-1e12, 1e12)
        self.max_input.setEnabled(False)
        self._layout.addWidget(self.max_input)

        # Add validity checks
        self.min_input.valueChanged.connect(self._check_valid_inputs)
        self.max_input.valueChanged.connect(self._check_valid_inputs)

        # Add checkbox to enable/disable limits
        self.enable_toggle = ToggleSwitch(self)
        self.enable_toggle.setToolTip("Enable editing limits")
        self.enable_toggle.setChecked(False)
        self.enable_toggle.enabled.connect(self._toggle_limits_enabled)
        self._layout.addWidget(self.enable_toggle)

    def reset_defaults(self) -> None:
        """Reset limits to default values."""
        self.min_input.setValue(0.0)
        self.max_input.setValue(0.0)
        self.enable_toggle.setChecked(False)

    def _is_valid_limit(self) -> bool:
        """Check if the current limits are valid (min < max)."""
        return self.min_input.value() <= self.max_input.value()

    def _check_valid_inputs(self) -> None:
        """Check if the current inputs are valid and update styles accordingly."""
        if not self._is_valid_limit():
            self.min_input.setStyleSheet(f"border: 1px solid {self._colors.emergency.name()};")
            self.max_input.setStyleSheet(f"border: 1px solid {self._colors.emergency.name()};")
        else:
            self.min_input.setStyleSheet("")
            self.max_input.setStyleSheet("")

    def _toggle_limits_enabled(self, enable: bool) -> None:
        """Enable or disable the limit inputs based on the checkbox state."""
        self.min_input.setEnabled(enable)
        self.max_input.setEnabled(enable)

    def get_limits(self) -> list[float, float]:
        """Return the limits as a list [min, max]."""
        min_val = self.min_input.value()
        max_val = self.max_input.value()
        return [min_val, max_val]

    def set_limits(self, limits: tuple) -> None:
        """Set the limits from a tuple (min, max)."""
        checked_state = self.enable_toggle.isChecked()
        if not checked_state:
            self.enable_toggle.setChecked(True)
        self.min_input.setValue(limits[0])
        self.max_input.setValue(limits[1])
        self.enable_toggle.setChecked(checked_state)


class ParameterValueWidget(QtWidgets.QWidget):
    """Custom QTreeWidget for user parameters input field."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.tree_widget = QtWidgets.QTreeWidget(self)
        self._layout.addWidget(self.tree_widget)
        self.tree_widget.setColumnCount(2)
        self.tree_widget.setHeaderLabels(["Parameter", "Value"])
        self.tree_widget.setIndentation(0)
        self.tree_widget.setRootIsDecorated(False)
        header = self.tree_widget.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self._add_tool_buttons()

    def clear_widget(self) -> None:
        """Clear all tags."""
        for i in reversed(range(self.tree_widget.topLevelItemCount())):
            item = self.tree_widget.topLevelItem(i)
            index = self.tree_widget.indexOfTopLevelItem(item)
            if index != -1:
                self.tree_widget.takeTopLevelItem(index)

    def _add_tool_buttons(self) -> None:
        """Add tool buttons for adding/removing parameter lines."""
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)
        self._layout.addLayout(button_layout)
        self._button_add = QtWidgets.QPushButton(self)
        self._button_add.setIcon(material_icon("add", size=(16, 16), convert_to_pixmap=False))
        self._button_add.setToolTip("Add parameter")
        self._button_add.clicked.connect(self._add_button_clicked)
        button_layout.addWidget(self._button_add)

        self._button_remove = QtWidgets.QPushButton(self)
        self._button_remove.setIcon(material_icon("remove", size=(16, 16), convert_to_pixmap=False))
        self._button_remove.setToolTip("Remove selected parameter")
        self._button_remove.clicked.connect(self.remove_parameter_line)
        button_layout.addWidget(self._button_remove)

    def _add_button_clicked(self, *args, **kwargs) -> None:
        """Handle the add button click event."""
        self.add_parameter_line()

    def add_parameter_line(self, parameter: str | None = None, value: str | None = None) -> None:
        """Add a new row with editable Parameter/Value QLineEdits."""
        item = QtWidgets.QTreeWidgetItem(self.tree_widget)
        self.tree_widget.addTopLevelItem(item)

        # Parameter field
        param_edit = QtWidgets.QLineEdit(self.tree_widget)
        param_edit.setPlaceholderText("Parameter")
        self.tree_widget.setItemWidget(item, 0, param_edit)

        # Value field
        value_edit = QtWidgets.QLineEdit(self.tree_widget)
        value_edit.setPlaceholderText("Value")
        self.tree_widget.setItemWidget(item, 1, value_edit)
        if parameter is not None:
            param_edit.setText(str(parameter))
        if value is not None:
            value_edit.setText(str(value))

    def remove_parameter_line(self) -> None:
        """Remove the selected row."""
        selected_items = self.tree_widget.selectedItems()
        for item in selected_items:
            index = self.tree_widget.indexOfTopLevelItem(item)
            if index != -1:
                self.tree_widget.takeTopLevelItem(index)

    # ---------------------------------------------------------------------

    def parameters(self) -> dict:
        """Return all parameters as a dictionary {parameter: value}."""
        result = {}
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            param_edit = self.tree_widget.itemWidget(item, 0)
            value_edit = self.tree_widget.itemWidget(item, 1)
            if param_edit and value_edit:
                key = param_edit.text().strip()
                val = value_edit.text().strip()
                if key and val:
                    result[key] = _try_literal_eval(val)
        return result


class DeviceTagsWidget(QtWidgets.QWidget):
    """Custom QTreeWidget for deviceTags input field."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.tree_widget = QtWidgets.QTreeWidget(self)
        self._layout.addWidget(self.tree_widget)
        self.tree_widget.setColumnCount(1)
        self.tree_widget.setHeaderLabels(["Tags"])
        self.tree_widget.setIndentation(0)
        self.tree_widget.setRootIsDecorated(False)
        self._add_tool_buttons()

    def clear_widget(self) -> None:
        """Clear all tags."""
        for i in reversed(range(self.tree_widget.topLevelItemCount())):
            item = self.tree_widget.topLevelItem(i)
            index = self.tree_widget.indexOfTopLevelItem(item)
            if index != -1:
                self.tree_widget.takeTopLevelItem(index)

    def _add_tool_buttons(self) -> None:
        """Add tool buttons for adding/removing parameter lines."""
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)
        self._layout.addLayout(button_layout)
        self._button_add = QtWidgets.QPushButton(self)
        self._button_add.setIcon(material_icon("add", size=(16, 16), convert_to_pixmap=False))
        self._button_add.setToolTip("Add parameter")
        self._button_add.clicked.connect(self._add_button_clicked)
        button_layout.addWidget(self._button_add)

        self._button_remove = QtWidgets.QPushButton(self)
        self._button_remove.setIcon(material_icon("remove", size=(16, 16), convert_to_pixmap=False))
        self._button_remove.setToolTip("Remove selected parameter")
        self._button_remove.clicked.connect(self.remove_parameter_line)
        button_layout.addWidget(self._button_remove)

    def _add_button_clicked(self, *args, **kwargs) -> None:
        """Handle the add button click event."""
        self.add_parameter_line()

    def add_parameter_line(self, parameter: str | None = None) -> None:
        """Add a new row with editable Tag QLineEdit."""
        item = QtWidgets.QTreeWidgetItem(self.tree_widget)
        self.tree_widget.addTopLevelItem(item)

        # Tag field
        param_edit = QtWidgets.QLineEdit(self.tree_widget)
        param_edit.setPlaceholderText("Tag")
        self.tree_widget.setItemWidget(item, 0, param_edit)
        if parameter is not None:
            param_edit.setText(str(parameter))

    def remove_parameter_line(self) -> None:
        """Remove the selected row."""
        selected_items = self.tree_widget.selectedItems()
        for item in selected_items:
            index = self.tree_widget.indexOfTopLevelItem(item)
            if index != -1:
                self.tree_widget.takeTopLevelItem(index)

    # ---------------------------------------------------------------------

    def parameters(self) -> list[str]:
        """Return all parameters as a list of tags."""
        result = []
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            param_edit = self.tree_widget.itemWidget(item, 0)
            if param_edit:
                tag = param_edit.text().strip()
                if tag:
                    result.append(tag)
        return result


# Validation callback for name field
def validate_name(name: str) -> bool:
    """Check that the name does not contain spaces."""
    if " " in name:
        return False
    if not name.replace("_", "").isalnum():
        return False
    return True


# Validation callback for deviceClass field
def validate_device_cls(name: str) -> bool:
    """Check that the name does not contain spaces."""
    if " " in name:
        return False
    if not name.replace("_", "").replace(".", "").isalnum():
        return False
    return True


def validate_prefix(value: str) -> bool:
    """Check that the prefix does not contain spaces."""
    if " " in value:
        return False
    if not value.replace("_", "").replace(".", "").replace("-", "").replace(":", "").isalnum():
        return False
    return True


class DeviceConfigField(BaseModel):
    """Pydantic model for device configuration fields."""

    label: str
    widget_cls: type[QtWidgets.QWidget]
    required: bool = False
    static: bool = False
    placeholder_text: str | None = None
    validation_callback: list[Callable[[str], bool]] | None = None
    default: Any = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


DEVICE_FIELDS = {
    "name": DeviceConfigField(
        label="Name",
        widget_cls=InputLineEdit,
        required=True,
        placeholder_text="Device name (no spaces or special characters)",
        validation_callback=[validate_name],
    ),
    "deviceClass": DeviceConfigField(
        label="Device Class",
        widget_cls=InputLineEdit,
        required=True,
        placeholder_text="Device class (no spaces or special characters)",
        validation_callback=[validate_device_cls],
    ),
    "description": DeviceConfigField(
        label="Description",
        widget_cls=QtWidgets.QTextEdit,
        required=False,
        placeholder_text="Short device description",
    ),
    "enabled": DeviceConfigField(
        label="Enabled", widget_cls=ToggleSwitch, required=False, default=True
    ),
    "readOnly": DeviceConfigField(
        label="Read Only", widget_cls=ToggleSwitch, required=False, default=False
    ),
    "softwareTrigger": DeviceConfigField(
        label="Software Trigger", widget_cls=ToggleSwitch, required=False, default=False
    ),
    "readoutPriority": DeviceConfigField(
        label="Readout Priority", widget_cls=ReadoutPriorityComboBox, default="baseline"
    ),
    "onFailure": DeviceConfigField(
        label="On Failure", widget_cls=OnFailureComboBox, default="retry"
    ),
    "userParameter": DeviceConfigField(
        label="User Parameters", widget_cls=ParameterValueWidget, static=False
    ),
    "deviceTags": DeviceConfigField(label="Device Tags", widget_cls=DeviceTagsWidget, static=False),
}

DEVICE_CONFIG_FIELDS = {
    "prefix": DeviceConfigField(
        label="Prefix",
        widget_cls=InputLineEdit,
        static=False,
        placeholder_text="EPICS IOC prefix, e.g. X25DA-ES1-MOT:",
        validation_callback=[validate_prefix],
    ),
    "read_pv": DeviceConfigField(
        label="Read PV",
        widget_cls=InputLineEdit,
        static=False,
        placeholder_text="EPICS read PV: e.g. X25DA-ES1-MOT:GET",
        validation_callback=[validate_prefix],
    ),
    "write_pv": DeviceConfigField(
        label="Write PV",
        widget_cls=InputLineEdit,
        static=False,
        placeholder_text="EPICS write PV (if different from read_pv): e.g. X25DA-ES1-MOT:SET",
        validation_callback=[validate_prefix],
    ),
    "limits": DeviceConfigField(label="Limits", widget_cls=LimitInputWidget, static=False),
    "DEFAULT": DeviceConfigField(label="DEFAULT FIELD", widget_cls=InputLineEdit, static=False),
}
