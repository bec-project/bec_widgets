"""Module for the device configuration form widget for EpicsMotor, EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV"""

from copy import deepcopy
from typing import Any, Type

from bec_lib.atlas_models import Device as DeviceModel
from bec_lib.logger import bec_logger
from ophyd_devices.interfaces.device_config_templates.ophyd_templates import OPHYD_DEVICE_TEMPLATES
from pydantic import BaseModel
from pydantic_core import PydanticUndefinedType
from qtpy import QtWidgets

from bec_widgets.widgets.control.device_manager.components.device_config_template.template_items import (
    DEVICE_CONFIG_FIELDS,
    DEVICE_FIELDS,
    DeviceConfigField,
    DeviceTagsWidget,
    InputLineEdit,
    LimitInputWidget,
    OnFailureComboBox,
    ParameterValueWidget,
    ReadoutPriorityComboBox,
)
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch

logger = bec_logger.logger


class DeviceConfigTemplate(QtWidgets.QWidget):
    """
    Device Configuration Template Widget.
    Current supported templates follow the structure in
    ophyd_devices.interfaces.device_config_templates.ophyd_templates.OPHYD_DEVICE_TEMPLATES.

    Args:
        parent (QtWidgets.QWidget, optional)         : Parent widget. Defaults to None.
        client (BECClient, optional)                 : BECClient instance. Defaults to None.
        template (dict[str, any], optional)          : Device configuration template. If None,
                                                       the "CustomDevice" template will be used. Defaults to None.
    """

    RPC = False

    def __init__(self, parent=None, template: dict[str, any] = None):
        super().__init__(parent=parent)
        if template is None:
            template = OPHYD_DEVICE_TEMPLATES["CustomDevice"]["CustomDevice"]
        self.template = template
        self._device_fields = deepcopy(DEVICE_FIELDS)
        self._device_config_fields = deepcopy(DEVICE_CONFIG_FIELDS)
        self._unknown_device_config_entry: dict[str, any] = {}

        # Dict to store references to input widgets
        self._widgets: dict[str, QtWidgets.QWidget] = {}

        # Two column layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        # Left hand side, settings, connection and advanced settings
        self._left_layout = QtWidgets.QVBoxLayout()
        self._left_layout.setContentsMargins(2, 2, 2, 2)
        self._left_layout.setSpacing(4)
        # Settings box, name | deviceClass | description
        self.settings_box = self._create_settings_box()
        # Device Config settings box | dynamic fields from deviceConfig
        self.connection_settings_box = self._create_connection_settings_box()
        # Advanced Control box | readoutPriority | onFailure | softwareTrigger | enabled | readOnly
        self.advanced_control_box = self._create_advanced_control_box()
        # Add boxes to left layout
        self._left_layout.addWidget(self.settings_box)
        self._left_layout.addWidget(self.connection_settings_box)
        self._left_layout.addWidget(self.advanced_control_box)
        layout.addLayout(self._left_layout)

        # Right hand side, advanced settings
        self._right_layout = QtWidgets.QVBoxLayout()
        self._right_layout.setContentsMargins(2, 2, 2, 2)
        self._right_layout.setSpacing(4)
        layout.addLayout(self._right_layout)
        # Create Additional Settings box
        self.additional_settings_box = self.create_additional_settings()
        self._right_layout.addWidget(self.additional_settings_box)

        # Set default values
        self.reset_to_defaults()

    def _clear_layout(self, layout: QtWidgets.QLayout) -> None:
        """Clear a layout recursively. If the layout contains sub-layouts, they will also be cleared."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().close()
                item.widget().deleteLater()
            if item.layout():
                self._clear_layout(item.layout())

    def reset_to_defaults(self) -> None:
        """Reset all fields to default values."""
        self._widgets.pop("deviceConfig", None)
        self._clear_layout(self.connection_settings_box.layout())

        # Recreate Connection Settings box
        layout: QtWidgets.QGridLayout = self.connection_settings_box.layout()
        self._fill_connection_settings_box(self.connection_settings_box, layout)

        # Reset Settings and Advanced Control boxes
        for field_name, widget in self._widgets.items():
            if field_name in self.template:
                self._set_value_for_widget(widget, self.template[field_name])
            else:
                self._set_default_entry(field_name, widget)

    def change_template(self, template: dict[str, any]) -> None:
        """
        Change the template and update the form fields accordingly.

        Args:
            template (dict[str, any]): New device configuration template.
        """
        self.template = template
        self.reset_to_defaults()

    def get_config_fields(self) -> dict:
        """Retrieve the current configuration from the input fields."""
        config: dict[str, any] = {}
        for device_entry, widget in self._widgets.items():
            config[device_entry] = self._get_entry_for_widget(widget)
        if self._unknown_device_config_entry:
            if "deviceConfig" not in config:
                config["deviceConfig"] = {}
            config["deviceConfig"].update(self._unknown_device_config_entry)
        return config

    def set_config_fields(self, config: dict) -> None:
        """
        Set the configuration fields based on the provided config dictionary.

        Args:
            config (dict): Configuration dictionary to set the fields.
        """
        # Clear storage for unknown entries
        self._unknown_device_config_entry.clear()
        if self.template.get("deviceClass", "") != config.get("deviceClass", ""):
            logger.warning(
                f"Device class {config.get('deviceClass', '')} does not match template device class {self.template.get('deviceClass', '')}. Using custom device template."
            )
            self.change_template(OPHYD_DEVICE_TEMPLATES["CustomDevice"]["CustomDevice"])
        else:
            self.reset_to_defaults()
        self._fill_fields_from_config(config)

    def _fill_fields_from_config(self, model: dict) -> None:
        """
        Fill the form fields base on the provided configuration dictionary.
        Please note, deviceConfig is handled separately through _fill_connection_settings_box
        as this depends on the template used.

        Args:
            model (dict): Configuration dictionary to fill the fields.
        """
        for key, value in model.items():
            if key == "name":
                wid = self._widgets["name"]
                wid.setText(value or "")
            elif key == "deviceClass":
                wid = self._widgets["deviceClass"]
                wid.setText(value or "")
                if "deviceClass" in self.template:
                    wid.setEnabled(False)
                else:
                    wid.setEnabled(True)
            elif key == "deviceConfig" and isinstance(
                self._widgets.get("deviceConfig", None), dict
            ):
                # If _widgets["deviceConfig"] is a dict, we have individual widgets for each field
                for sub_key, sub_value in value.items():
                    widget = self._widgets["deviceConfig"].get(sub_key, None)
                    if widget is None:
                        logger.warning(
                            f"Widget for key {sub_key} not found in deviceConfig widgets."
                        )
                        # Store any unknown entry fields
                        self._unknown_device_config_entry[sub_key] = sub_value
                        continue
                    self._set_value_for_widget(widget, sub_value)
            else:
                widget = self._widgets.get(key, None)
                if widget is not None:
                    self._set_value_for_widget(widget, value)

    def _set_value_for_widget(self, widget: QtWidgets.QWidget, value: Any) -> None:
        """
        Set the value for a widget based on its type.

        Args:
            widget (QtWidgets.QWidget): The widget to set the value for.
            value (any): The value to set.
        """
        if isinstance(widget, (ParameterValueWidget)) and isinstance(value, dict):
            for param, val in value.items():
                widget.add_parameter_line(param, val)
        elif isinstance(widget, DeviceTagsWidget) and isinstance(value, (list, tuple, set)):
            for tag in value:
                widget.add_parameter_line(tag or "")
        elif isinstance(widget, InputLineEdit):
            widget.setText(str(value or ""))
        elif isinstance(widget, ToggleSwitch):
            widget.setChecked(bool(value))
        elif isinstance(widget, LimitInputWidget):
            widget.set_limits(value)
        elif isinstance(widget, QtWidgets.QComboBox):
            index = widget.findText(value)
            if index != -1:
                widget.setCurrentIndex(index)
        elif isinstance(widget, QtWidgets.QTextEdit):
            widget.setPlainText(str(value or ""))
        else:
            logger.warning(f"Unsupported widget type for setting value: {type(widget)}")

    def _get_entry_for_widget(self, widget: QtWidgets.QWidget) -> any:
        """
        Get the value from a widget based on its type.

        Args:
            widget (QtWidgets.QWidget): The widget to get the value from.
        Returns:
            any: The value retrieved from the widget.
        """
        if isinstance(widget, (ParameterValueWidget, DeviceTagsWidget)):
            return widget.parameters()
        elif isinstance(widget, InputLineEdit):
            return widget.text().strip()
        elif isinstance(widget, ToggleSwitch):
            return widget.isChecked()
        elif isinstance(widget, LimitInputWidget):
            return widget.get_limits()
        elif isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText()
        elif isinstance(widget, QtWidgets.QTextEdit):
            return widget.toPlainText()
        elif isinstance(widget, dict):
            result = {}
            for sub_entry, sub_widget in widget.items():
                result[sub_entry] = self._get_entry_for_widget(sub_widget)
            return result
        else:
            logger.warning(f"Unsupported widget type for getting entry: {type(widget)}")
            return None

    def _create_device_field(
        self, field_name: str, field_info: DeviceConfigField | None = None
    ) -> tuple[QtWidgets.QLabel, QtWidgets.QWidget]:
        """
        Create a device field based on the field name. If field_info is not provided,
        a default label and input widget will be created.

        Args:
            field_name (str): Name of the field.
            field_info (DeviceConfigField | None, optional): Information about the field. Defaults to None.
        """
        if field_info is None:
            label = QtWidgets.QLabel(field_name, parent=self)
            input_widget = QtWidgets.QLineEdit(parent=self)
            return label, input_widget

        label_text = field_info.label
        label = QtWidgets.QLabel(label_text, parent=self)
        if field_info.required:
            label_text = label.text()
            label_text += " *"
            label.setText(label_text)
            label.setStyleSheet("font-weight: bold;")
        input_widget = field_info.widget_cls(parent=self)
        if field_info.placeholder_text:
            if hasattr(input_widget, "setPlaceholderText"):
                input_widget.setPlaceholderText(field_info.placeholder_text)
        if field_info.static:
            input_widget.setEnabled(False)
        if field_info.validation_callback:
            # Attach validation callback if provided
            if isinstance(input_widget, InputLineEdit):
                input_widget: InputLineEdit
                for callback in field_info.validation_callback:
                    input_widget.register_validation_callback(callback)
        if field_info.default is not None:
            # Set default value
            if isinstance(input_widget, QtWidgets.QLineEdit):
                input_widget.setText(str(field_info.default))
            elif isinstance(input_widget, QtWidgets.QTextEdit):
                input_widget.setPlainText(str(field_info.default))
            elif isinstance(input_widget, ToggleSwitch):
                input_widget.setChecked(bool(field_info.default))
            elif isinstance(input_widget, (ReadoutPriorityComboBox, OnFailureComboBox)):
                index = input_widget.findText(field_info.default)
                if index != -1:
                    input_widget.setCurrentIndex(index)
        return label, input_widget

    def _create_group_box_with_grid_layout(
        self, title: str
    ) -> tuple[QtWidgets.QGroupBox, QtWidgets.QGridLayout]:
        """Create a group box with a grid layout."""
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QGridLayout(box)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)
        box.setLayout(layout)
        return box, layout

    def _set_default_entry(self, field_name: str, widget: QtWidgets.QWidget) -> None:
        """
        Set the default value for a given field in the form based on the Pydantic model.

        Args:
            field_name (str): Name of the field.
            widget (QtWidgets.QWidget): The widget to set the default value for.
        """
        if field_name == "enabled":
            widget.setChecked(True)
            return
        if field_name == "readOnly":
            widget.setChecked(False)
            return
        default = self._get_default_for_device_config_field(field_name) or ""
        widget.setEnabled(True)
        if isinstance(widget, QtWidgets.QComboBox):
            index = widget.findText(default)
            if index != -1:
                widget.setCurrentIndex(index)
        elif isinstance(widget, (QtWidgets.QTextEdit, QtWidgets.QLineEdit)):
            widget.setText(str(default))
        elif isinstance(widget, ToggleSwitch):
            widget.setChecked(bool(default))
        elif isinstance(widget, (ParameterValueWidget, DeviceTagsWidget)):
            widget.clear_widget()

    def _get_default_for_device_config_field(self, field_name: str) -> any:
        """
        Get the default value for a given deviceConfig field based on the Pydantic model.

        Args:
            field_name (str): Name of the deviceConfig field.
        Returns:
            any: The default value for the field, or None if not found.
        """
        model_properties: dict = DeviceModel.model_json_schema()["properties"]
        if field_name in model_properties:
            field_info = model_properties[field_name]
            default = field_info.get("default", None)
            if default:
                return default
        return None

    ### Box creation methods ###

    def _create_box(self, box_title: str, field_names: list[str]) -> QtWidgets.QGroupBox:
        """
        Create a box layout with specific fields. If field_names are in _device_fields,
        their corresponding widgets will be used.
        """
        # Create box
        box, layout = self._create_group_box_with_grid_layout(box_title)
        box.setLayout(layout)

        for ii, field_name in enumerate(field_names):
            label, input_widget = self._create_device_field(
                field_name, self._device_fields.get(field_name, None)
            )
            layout.addWidget(label, ii, 0)
            layout.addWidget(input_widget, ii, 1)
            self._widgets[field_name] = input_widget
        return box

    def _create_settings_box(self) -> QtWidgets.QGroupBox:
        """Create the settings box widget."""
        box = self._create_box("Settings", ["name", "deviceClass", "description"])
        layout = box.layout()
        # Set column stretch
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        return box

    def _create_advanced_control_box(self) -> QtWidgets.QGroupBox:
        """Create the advanced control box widget."""
        # Set up advanced control box
        box = self._create_box("Advanced Control", ["readoutPriority", "onFailure"])
        layout = box.layout()
        for ii, field_name in enumerate(["enabled", "readOnly", "softwareTrigger"]):
            label, input_widget = self._create_device_field(
                field_name, self._device_fields.get(field_name, None)
            )
            layout.addWidget(label, ii, 2)
            layout.addWidget(input_widget, ii, 3)
            self._widgets[field_name] = input_widget
        return box

    def _create_connection_settings_box(self) -> QtWidgets.QGroupBox:
        """Create the connection settings box widget. These are all entries in the deviceConfig field."""
        box, layout = self._create_group_box_with_grid_layout("Connection Settings")
        box = self._fill_connection_settings_box(box, layout)
        return box

    def _fill_connection_settings_box(
        self, box: QtWidgets.QGroupBox, layout: QtWidgets.QGridLayout
    ) -> QtWidgets.QGroupBox:
        """Fill the connection settings box based on the deviceConfig template."""
        if not self.template.get("deviceConfig", {}):
            widget = ParameterValueWidget(parent=self)
            widget.setToolTip(
                "Add custom deviceConfig entries as key-value pairs in the tree view."
            )
            layout.addWidget(widget, 0, 0)
            self._widgets["deviceConfig"] = widget
            return box
        # If template specifies deviceConfig fields, create them
        self._widgets["deviceConfig"] = {}
        model: Type[BaseModel] = self.template["deviceConfig"]
        for field_name, field in model.model_fields.items():
            field_info = self._device_config_fields.get(field_name, None)
            default = field.get_default()
            if isinstance(default, PydanticUndefinedType):
                default = None
            if field_info:
                if field.is_required():
                    field_info.required = True
                if field.description:
                    field_info.placeholder_text = field.description
                if default is not None:
                    field_info.default = default
            label, input_widget = self._create_device_field(field_name, field_info)
            row = layout.rowCount()
            layout.addWidget(label, row, 0)
            layout.addWidget(input_widget, row, 1)
            self._widgets["deviceConfig"][field_name] = input_widget
        return box

    def create_additional_settings(self) -> QtWidgets.QGroupBox:
        """Create the additional settings box widget."""
        box, layout = self._create_group_box_with_grid_layout("Additional Settings")
        toolbox = QtWidgets.QToolBox(parent=self)
        layout.addWidget(toolbox, 0, 0)
        user_parameters_widget = ParameterValueWidget(parent=self)
        self._widgets["userParameter"] = user_parameters_widget
        toolbox.addItem(user_parameters_widget, "User Parameter")
        device_tags_widget = DeviceTagsWidget(parent=self)
        toolbox.addItem(device_tags_widget, "Device Tags")
        toolbox.setCurrentIndex(1)
        self._widgets["deviceTags"] = device_tags_widget
        return box


if __name__ == """__main__""":  # pragma: no cover
    import sys

    app = QtWidgets.QApplication(sys.argv)
    import yaml
    from bec_qthemes import apply_theme

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    apply_theme("light")

    class TestWidget(QtWidgets.QWidget):
        pass

    w = TestWidget()
    w_layout = QtWidgets.QVBoxLayout(w)
    w_layout.setContentsMargins(0, 0, 0, 0)
    w_layout.setSpacing(20)
    dark_mode_button = DarkModeButton()
    w_layout.addWidget(dark_mode_button)
    test_motor = "EpicsMotor"
    config_form = DeviceConfigTemplate(template=OPHYD_DEVICE_TEMPLATES[test_motor][test_motor])
    w_layout.addWidget(config_form)
    button_layout = QtWidgets.QHBoxLayout()
    button = QtWidgets.QPushButton("Get Config")
    button.clicked.connect(
        lambda: print("Device Config:", yaml.dump(config_form.get_config_fields(), indent=4))
    )
    button_layout.addWidget(button)
    button2 = QtWidgets.QPushButton("Reset")
    button2.clicked.connect(config_form.reset_to_defaults)
    button_layout.addWidget(button2)
    combo = QtWidgets.QComboBox()
    combo_keys = [
        "EpicsMotor",
        "EpicsSignal",
        "EpicsSignalRO",
        "EpicsSignalWithRBV",
        "CustomDevice",
    ]
    combo.addItems(combo_keys)
    combo.setCurrentText(test_motor)

    def text_changed(text: str) -> None:
        if text.startswith("EpicsMotor"):
            if text == "EpicsMotor":
                template = OPHYD_DEVICE_TEMPLATES[text][text]
            else:
                template = OPHYD_DEVICE_TEMPLATES["EpicsMotor"][text]
        elif text.startswith("EpicsSignal"):
            if text == "EpicsSignal":
                template = OPHYD_DEVICE_TEMPLATES[text][text]
            else:
                template = OPHYD_DEVICE_TEMPLATES["EpicsSignal"][text]
        else:
            template = OPHYD_DEVICE_TEMPLATES["CustomDevice"]["CustomDevice"]
        config_form.change_template(template)

    combo.currentTextChanged.connect(text_changed)
    button_layout.addWidget(button)
    button_layout.addWidget(combo)
    w_layout.addLayout(button_layout)
    w.resize(1200, 600)
    w.show()
    sys.exit(app.exec_())
