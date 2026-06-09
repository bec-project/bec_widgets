from __future__ import annotations

from types import NoneType
from typing import Any, Literal, get_args, get_origin

from bec_lib.device import DeviceBase, Signal
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo
from qtpy.QtCore import Qt
from qtpy.QtCore import Signal as QtSignal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from bec_widgets.utils.forms_from_types.pydantic_model_info_adapter import (
    NUMERIC_BOUND_KEYS,
    pydantic_model_input_configs,
)
from bec_widgets.utils.scan_arg_metadata import (
    apply_numeric_limits,
    apply_numeric_precision,
    apply_unit_metadata,
    device_units,
)
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox
from bec_widgets.widgets.utility.spinbox.decimal_spinbox import BECSpinBox


class OptionalValueWidget(QWidget):
    """Wrap a value widget with an enable checkbox for optional Pydantic fields.

    Attributes:
        value_changed: Signal emitted with the current value whenever the checkbox
            state or wrapped widget value changes.
    """

    value_changed = QtSignal(object)

    def __init__(self, value_widget: QWidget, parent: QWidget | None = None) -> None:
        """Create an optional-value wrapper.

        Args:
            value_widget: Input widget used when the optional value is enabled.
            parent: Optional parent widget.
        """
        super().__init__(parent=parent)
        self._value_widget = value_widget
        self._checkbox = QCheckBox(self)
        self._checkbox.setToolTip("Enable value")
        self._value_widget.setParent(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._checkbox)
        layout.addWidget(self._value_widget, 1)

        self._checkbox.toggled.connect(self._on_enabled_changed)
        WidgetIO.connect_widget_change_signal(self._value_widget, self._emit_current_value)
        self._on_enabled_changed(False)

    @property
    def value_widget(self) -> QWidget:
        """Return the wrapped input widget.

        Returns:
            The widget that edits the non-``None`` value.
        """
        return self._value_widget

    @property
    def checkbox(self) -> QCheckBox:
        """Return the checkbox controlling whether the value is enabled.

        Returns:
            The enable checkbox.
        """
        return self._checkbox

    def value(self) -> Any:
        """Return the current optional value.

        Returns:
            ``None`` when the checkbox is unchecked; otherwise the wrapped widget value.
        """
        if not self._checkbox.isChecked():
            return None
        return WidgetIO.get_value(self._value_widget)

    def set_value(self, value: Any) -> None:
        """Set the optional value.

        Args:
            value: Value to set on the wrapped widget. ``None`` disables the value.
        """
        enabled = value is not None
        self._checkbox.setChecked(enabled)
        self._value_widget.setEnabled(enabled)
        if enabled:
            WidgetIO.set_value(self._value_widget, value)

    def _on_enabled_changed(self, enabled: bool) -> None:
        self._value_widget.setEnabled(enabled)
        self.value_changed.emit(self.value())

    def _emit_current_value(self, *_args) -> None:
        self.value_changed.emit(self.value())


class PydanticWidgetForm(QWidget):
    """Generate a Qt form from a Pydantic model.

    The form maps Pydantic field annotations to Qt widgets, applies supported
    field metadata, and exposes typed and raw data accessors for the generated
    fields.

    Attributes:
        changed: Signal emitted whenever a generated input widget changes.
        validity_changed: Signal emitted by :meth:`validate` with the current
            validation result.
    """

    changed = QtSignal()
    validity_changed = QtSignal(bool)

    def __init__(
        self,
        model: type[BaseModel],
        parent: QWidget | None = None,
        *,
        data: BaseModel | dict[str, Any] | None = None,
        read_only_fields: set[str] | None = None,
        client=None,
    ) -> None:
        """Create a generated form for a Pydantic model.

        Args:
            model: Pydantic model class used to generate fields and validate data.
            parent: Optional parent widget.
            data: Optional initial model instance or raw field-value mapping.
            read_only_fields: Field names that should be displayed but not editable.
            client: Optional BEC client passed to domain-specific widgets such as
                device and signal combo boxes.
        """
        super().__init__(parent=parent)
        self._model = model
        self._client = client
        self._read_only_fields = set(read_only_fields or set())
        self._widgets: dict[str, QWidget] = {}
        self._field_configs: dict[str, dict[str, Any]] = {}
        self._baseline: dict[str, Any] = {}

        self._layout = QFormLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(10)
        self._layout.setVerticalSpacing(8)
        self._layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.setLayout(self._layout)

        self._populate()
        if data is not None:
            self.set_data(data)
        self.mark_clean()

    @property
    def model(self) -> type[BaseModel]:
        """Return the active Pydantic model class.

        Returns:
            The model class currently used by this form.
        """
        return self._model

    @property
    def widgets(self) -> dict[str, QWidget]:
        """Return generated field widgets keyed by model field name.

        Returns:
            A shallow copy of the field-widget mapping. Optional fields return
            their outer :class:`OptionalValueWidget`.
        """
        return dict(self._widgets)

    def field_widget(self, name: str) -> QWidget:
        """Return the generated widget for a field.

        Args:
            name: Model field name.

        Returns:
            The generated field widget. Optional fields return their outer
            :class:`OptionalValueWidget`.

        Raises:
            KeyError: If no widget exists for ``name``.
        """
        return self._widgets[name]

    def input_widget(self, name: str) -> QWidget:
        """Return the direct input widget for a field.

        Args:
            name: Model field name.

        Returns:
            The editable input widget. Optional fields return the wrapped value
            widget instead of the outer optional wrapper.

        Raises:
            KeyError: If no widget exists for ``name``.
        """
        widget = self._widgets[name]
        if isinstance(widget, OptionalValueWidget):
            return widget.value_widget
        return widget

    def input_widgets(self) -> dict[str, QWidget]:
        """Return direct input widgets keyed by model field name.

        Returns:
            Mapping of field names to editable input widgets.
        """
        return {name: self.input_widget(name) for name in self._widgets}

    def input_widgets_by_type(self, widget_type: type[QWidget]) -> list[QWidget]:
        """Return direct input widgets matching a widget type.

        Args:
            widget_type: Qt widget class to match with ``isinstance``.

        Returns:
            List of input widgets matching ``widget_type``.
        """
        return [
            widget for widget in self.input_widgets().values() if isinstance(widget, widget_type)
        ]

    def set_model(self, model: type[BaseModel], data: dict[str, Any] | None = None) -> None:
        """Replace the active model and rebuild the form.

        Args:
            model: New Pydantic model class.
            data: Optional initial data for the new model. When omitted, values
                from fields shared with the previous model are preserved.
        """
        old_data = self.raw_data()
        self.cleanup()
        self._model = model
        self._populate()
        if data is None:
            data = {key: value for key, value in old_data.items() if key in model.model_fields}
        self.set_partial_data(data)
        self.mark_clean()

    def set_data(self, data: BaseModel | dict[str, Any]) -> None:
        """Set form values from a model instance or mapping.

        Args:
            data: Pydantic model instance or raw field-value mapping.
        """
        values = data.model_dump() if isinstance(data, BaseModel) else dict(data)
        self.set_partial_data(values)

    def set_partial_data(self, data: dict[str, Any]) -> None:
        """Set values for fields present in the form.

        Unknown keys are ignored, which allows callers to pass larger model
        dumps or backend payloads safely.

        Args:
            data: Field-value mapping to apply.
        """
        for name, value in data.items():
            if name not in self._widgets:
                continue
            self._set_widget_value(name, value)
        self._refresh_reference_units()
        self.changed.emit()

    def raw_data(self) -> dict[str, Any]:
        """Return current widget values without Pydantic validation.

        Returns:
            Mapping of model field names to raw widget values.
        """
        return {name: self._read_widget_value(name) for name in self._widgets}

    def get_data(self) -> dict[str, Any]:
        """Return current data after Pydantic validation.

        Returns:
            Validated model data as a dictionary.

        Raises:
            ValidationError: If Pydantic validation fails.
            ValueError: If domain widget validation fails.
        """
        return self.model_instance().model_dump()

    def model_instance(self) -> BaseModel:
        """Return the current values as a Pydantic model instance.

        Returns:
            Validated instance of the active model class.

        Raises:
            ValidationError: If Pydantic validation fails.
            ValueError: If domain widget validation fails.
        """
        self._validate_domain_widgets()
        return self._model.model_validate(self.raw_data())

    def validate(self) -> bool:
        """Validate the current form values.

        Returns:
            ``True`` when current values validate successfully, otherwise ``False``.
        """
        try:
            self.get_data()
        except (ValidationError, ValueError):
            self.validity_changed.emit(False)
            return False
        self.validity_changed.emit(True)
        return True

    def dirty_fields(self) -> set[str]:
        """Return fields whose raw values differ from the clean baseline.

        Returns:
            Set of dirty field names.
        """
        current = self.raw_data()
        fields = set(current) | set(self._baseline)
        return {field for field in fields if current.get(field) != self._baseline.get(field)}

    def mark_clean(self) -> None:
        """Store the current raw values as the clean baseline."""
        self._baseline = self.raw_data()

    def reset_to_baseline(self) -> None:
        """Restore the form values to the current clean baseline."""
        self.set_partial_data(self._baseline)

    def editable_data(self) -> dict[str, Any]:
        """Return validated data excluding read-only fields.

        Returns:
            Validated editable field values.

        Raises:
            ValidationError: If Pydantic validation fails.
            ValueError: If domain widget validation fails.
        """
        return {
            key: value
            for key, value in self.get_data().items()
            if key not in self._read_only_fields
        }

    def raw_editable_data(self) -> dict[str, Any]:
        """Return raw widget data excluding read-only fields.

        Returns:
            Raw editable field values.
        """
        return {
            key: value
            for key, value in self.raw_data().items()
            if key not in self._read_only_fields
        }

    def cleanup(self) -> None:
        """Close and schedule deletion of all generated field widgets."""
        while self._layout.rowCount():
            row = self._layout.takeRow(0)
            for item in (row.labelItem, row.fieldItem):
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.close()
                    # Detach before deleteLater: a child pending deletion that still has a
                    # signal connection into this form crashes if the form is garbage
                    # collected before the deferred delete is processed.
                    widget.setParent(None)
                    widget.deleteLater()
        self._widgets.clear()
        self._field_configs.clear()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.cleanup()
        super().closeEvent(event)

    def _populate(self) -> None:
        for config in pydantic_model_input_configs(self._model):
            name = config["name"]
            info = self._model.model_fields[name]
            widget = self._create_widget(name, info)
            label_text = config["display_name"]
            self._layout.addRow(label_text, widget)
            label = self._layout.labelForField(widget)
            if label is not None:
                label.setProperty("_model_field_name", name)
            if config.get("tooltip") and label is not None:
                label.setToolTip(config["tooltip"])
            widget.setEnabled(name not in self._read_only_fields)
            self._widgets[name] = widget
            self._field_configs[name] = config
            self._set_widget_value(name, config["default"])
            self._apply_field_metadata(name)
            self._connect_widget(widget)

        self._connect_device_signal_widgets()
        self._connect_reference_unit_widgets()
        self._refresh_reference_units()

    def _create_widget(self, name: str, info: FieldInfo) -> QWidget:
        annotation = info.annotation
        args = get_args(annotation)
        optional = NoneType in args
        non_none_args = tuple(arg for arg in args if arg is not NoneType)
        value_annotation = non_none_args[0] if len(non_none_args) == 1 else annotation

        widget = self._create_value_widget(name, value_annotation)
        numeric = value_annotation in (int, float) or any(
            arg in (int, float) for arg in get_args(value_annotation)
        )
        if optional and (numeric or value_annotation is bool):
            return OptionalValueWidget(widget, parent=self)
        return widget

    def _create_value_widget(self, name: str, annotation: Any) -> QWidget:
        args = get_args(annotation)
        if (
            isinstance(annotation, type)
            and issubclass(annotation, Signal)
            or any(isinstance(arg, type) and issubclass(arg, Signal) for arg in args)
        ):
            return SignalComboBox(
                parent=self,
                client=self._client,
                require_device=self._model_has_device_field(),
                arg_name=name,
            )
        if (
            isinstance(annotation, type)
            and issubclass(annotation, DeviceBase)
            or any(isinstance(arg, type) and issubclass(arg, DeviceBase) for arg in args)
        ):
            return DeviceComboBox(parent=self, client=self._client, arg_name=name)
        if get_origin(annotation) is Literal:
            widget = QComboBox(self)
            widget.addItems([str(value) for value in get_args(annotation)])
            return widget
        if annotation is bool:
            return QCheckBox(self)
        if annotation is int:
            spin_box = QSpinBox(self)
            spin_box.setRange(-2147483647, 2147483647)
            return spin_box
        if annotation is float:
            spin_box = BECSpinBox(self)
            spin_box.setRange(-1_000_000_000, 1_000_000_000)
            return spin_box
        return QLineEdit(self)

    def _apply_field_metadata(self, name: str) -> None:
        config = self._field_configs[name]
        field_widget = self._widgets[name]
        input_widget = self.input_widget(name)

        if config.get("precision") is not None:
            apply_numeric_precision(input_widget, config)
        if any(config.get(key) is not None for key in NUMERIC_BOUND_KEYS):
            apply_numeric_limits(input_widget, config)

        apply_unit_metadata(field_widget, config)
        if input_widget is not field_widget:
            apply_unit_metadata(input_widget, config)

    def _connect_widget(self, widget: QWidget) -> None:
        if isinstance(widget, OptionalValueWidget):
            widget.value_changed.connect(lambda _value: self.changed.emit())
            return
        WidgetIO.connect_widget_change_signal(widget, lambda *_args: self.changed.emit())

    def _connect_device_signal_widgets(self) -> None:
        devices = [
            widget for widget in self._widgets.values() if isinstance(widget, DeviceComboBox)
        ]
        signals = [
            widget for widget in self._widgets.values() if isinstance(widget, SignalComboBox)
        ]
        if not devices or not signals:
            return
        device_widget = devices[0]
        for signal_widget in signals:
            device_widget.device_selected.connect(signal_widget.set_device)
            device_widget.device_reset.connect(lambda w=signal_widget: w.set_device(None))
            if device_widget.currentText().strip():
                signal_widget.set_device(device_widget.currentText().strip())

    def _connect_reference_unit_widgets(self) -> None:
        for name, widget in self.input_widgets().items():
            if not isinstance(widget, DeviceComboBox):
                continue
            widget.device_selected.connect(
                lambda _device_name, field_name=name: self._update_reference_units(field_name)
            )
            widget.device_reset.connect(
                lambda field_name=name: self._apply_reference_units(field_name, None)
            )
            widget.currentTextChanged.connect(
                lambda text, field_name=name: self._handle_reference_device_text(field_name, text)
            )

    def _refresh_reference_units(self) -> None:
        for name, widget in self.input_widgets().items():
            if isinstance(widget, DeviceComboBox):
                self._update_reference_units(name)

    def _update_reference_units(self, source_name: str) -> None:
        widget = self.input_widget(source_name)
        if not isinstance(widget, DeviceComboBox) or not widget.is_valid_input:
            self._apply_reference_units(source_name, None)
            return
        self._apply_reference_units(source_name, device_units(widget.get_current_device()))

    def _apply_reference_units(self, source_name: str, units: str | None) -> None:
        for field_name, config in self._field_configs.items():
            if config.get("reference_units") != source_name:
                continue
            field_widget = self.field_widget(field_name)
            input_widget = self.input_widget(field_name)
            apply_unit_metadata(field_widget, config, units)
            if input_widget is not field_widget:
                apply_unit_metadata(input_widget, config, units)

    def _handle_reference_device_text(self, source_name: str, device_name: str) -> None:
        widget = self.input_widget(source_name)
        if isinstance(widget, DeviceComboBox) and not widget.validate_device(device_name):
            self._apply_reference_units(source_name, None)

    def _validate_domain_widgets(self) -> None:
        for widget in self._widgets.values():
            if isinstance(widget, DeviceComboBox):
                device = widget.currentText().strip()
                if not device:
                    raise ValueError("Device is required.")
                if not widget.is_valid_input:
                    raise ValueError(f"Device '{device}' is not available.")
            if isinstance(widget, SignalComboBox):
                signal = widget.get_signal_name().strip()
                if signal and not widget.is_valid_input:
                    raise ValueError(f"Signal '{signal}' is not available.")

    def _read_widget_value(self, name: str) -> Any:
        widget = self._widgets[name]
        info = self._model.model_fields[name]
        if isinstance(widget, OptionalValueWidget):
            return widget.value()
        if isinstance(widget, QLineEdit):
            value = WidgetIO.get_value(widget)
            return None if NoneType in get_args(info.annotation) and value == "" else value
        if isinstance(widget, QComboBox) and get_origin(info.annotation) is Literal:
            return WidgetIO.get_value(widget, as_string=True)
        return WidgetIO.get_value(widget)

    def _set_widget_value(self, name: str, value: Any) -> None:
        widget = self._widgets[name]
        if isinstance(widget, OptionalValueWidget):
            widget.set_value(value)
            return
        if value is None:
            if isinstance(widget, QLineEdit):
                value = ""
            elif isinstance(widget, QCheckBox):
                value = False
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                value = 0
        WidgetIO.set_value(widget, value)

    def _model_has_device_field(self) -> bool:
        for field in self._model.model_fields.values():
            annotation = field.annotation
            args = get_args(annotation)
            has_device = (
                isinstance(annotation, type)
                and issubclass(annotation, DeviceBase)
                or any(isinstance(arg, type) and issubclass(arg, DeviceBase) for arg in args)
            )
            has_signal = (
                isinstance(annotation, type)
                and issubclass(annotation, Signal)
                or any(isinstance(arg, type) and issubclass(arg, Signal) for arg in args)
            )
            if has_device and not has_signal:
                return True
        return False


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    from bec_lib.scan_args import ScanArgument
    from pydantic import Field
    from qtpy.QtWidgets import QApplication, QLabel, QPushButton, QTabWidget, QTextEdit, QVBoxLayout

    from bec_widgets.utils.colors import apply_theme

    class BasicScanConfig(BaseModel):
        """Plain Pydantic fields without GUI metadata."""

        sample_name: str
        enabled: bool = True
        repeats: int = 3

    class LimitConfig(BaseModel):
        """Normal Pydantic Field metadata."""

        mode: Literal["monitor", "scan", "calibration"] = "scan"
        low_limit: (
            float | None
        )  # example of the field without additional metadata, still works in form
        high_limit: float | None = Field(
            default=10.0,
            title="High limit",
            description="Optional upper allowed value.",
            json_schema_extra={"precision": 4},
        )
        tolerance: float = Field(
            default=0.1,
            title="Tolerance",
            description="Warning tolerance around configured limits.",
            json_schema_extra={"precision": 4},
        )

    class ScanArgumentConfig(BaseModel):
        """ScanArgument metadata applied through Field extras."""

        settling_time: float = Field(
            default=0.0,
            **ScanArgument(
                display_name="Settling time",
                description="Time to wait after moving.",
                units="s",
                precision=3,
                ge=0,
            ).model_dump(),
        )
        frames: int = Field(
            default=1,
            **ScanArgument(
                display_name="Frames", description="Number of frames per trigger.", ge=1
            ).model_dump(),
        )

    class DeviceSignalLimitsConfig(BaseModel):
        """Device, signal, and numeric fields whose units follow the selected device."""

        model_config = {"arbitrary_types_allowed": True}

        device: DeviceBase | str = Field(
            default="",
            **ScanArgument(display_name="Device", description="Positioner device.").model_dump(),
        )
        signal: Signal | str | None = Field(
            default=None,
            **ScanArgument(display_name="Signal", description="Device signal.").model_dump(),
        )
        low_limit: float | None = Field(
            default=None,
            **ScanArgument(
                display_name="Low limit",
                description="Optional lower limit.",
                reference_units="device",
                precision=4,
            ).model_dump(),
        )
        high_limit: float | None = Field(
            default=None,
            **ScanArgument(
                display_name="High limit",
                description="Optional upper limit.",
                reference_units="device",
                precision=4,
            ).model_dump(),
        )

    class DisplayConfig(BaseModel):
        title: str | None = Field(
            default=None, title="Title", description="Optional display title."
        )
        show_grid: bool = Field(default=True, title="Show grid")
        refresh_interval: int = Field(
            default=1000, title="Refresh interval", description="Refresh interval in milliseconds."
        )

    class DeviceAndSignalConfig(BaseModel):
        model_config = {"arbitrary_types_allowed": True}

        title: str | None = Field(
            default=None, title="Title", description="Optional display title."
        )
        device: DeviceBase | str = Field(
            default="", title="Device", description="BEC device selection."
        )
        signal: Signal | str | None = Field(
            default=None,
            title="Signal",
            description="Signal selection scoped to the selected device.",
        )
        refresh_interval: int = Field(
            default=1000, title="Refresh interval", description="Refresh interval in milliseconds."
        )

    class DeviceOnlyConfig(BaseModel):
        model_config = {"arbitrary_types_allowed": True}

        title: str | None = Field(
            default=None, title="Title", description="Optional display title."
        )
        device: DeviceBase | str = Field(
            default="", title="Device", description="BEC device selection."
        )
        refresh_interval: int = Field(
            default=1000, title="Refresh interval", description="Refresh interval in milliseconds."
        )

    class SignalOnlyConfig(BaseModel):
        model_config = {"arbitrary_types_allowed": True}

        title: str | None = Field(
            default=None, title="Title", description="Optional display title."
        )
        signal: Signal | str | None = Field(
            default=None,
            title="Signal",
            description="Global BEC signal selection without a device field.",
        )
        refresh_interval: int = Field(
            default=1000, title="Refresh interval", description="Refresh interval in milliseconds."
        )

    class ExampleWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("PydanticWidgetForm example")

            self._tabs = QTabWidget(self)
            self._output = QTextEdit(self)
            self._output.setReadOnly(True)
            self._output.setPlaceholderText("Validated form data appears here.")
            self._forms: list[PydanticWidgetForm] = []

            self._add_form("Basic", PydanticWidgetForm(BasicScanConfig))
            self._add_form("Limits", PydanticWidgetForm(LimitConfig))
            self._add_form("ScanArgument", PydanticWidgetForm(ScanArgumentConfig))
            self._add_form("Display", PydanticWidgetForm(DisplayConfig))
            self._add_form("Device + signal", PydanticWidgetForm(DeviceAndSignalConfig))
            self._add_form("Device limits", PydanticWidgetForm(DeviceSignalLimitsConfig))
            self._add_form("Device only", PydanticWidgetForm(DeviceOnlyConfig))
            self._add_form("Signal only", PydanticWidgetForm(SignalOnlyConfig))

            show_data = QPushButton("Show current tab data", self)
            show_data.clicked.connect(self._show_current_data)

            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Generated forms from Pydantic models", self))
            layout.addWidget(self._tabs)
            layout.addWidget(show_data)
            layout.addWidget(self._output)

        def _add_form(self, title: str, form: PydanticWidgetForm) -> None:
            form.changed.connect(lambda _form=form: self._on_form_changed(_form))
            self._forms.append(form)
            self._tabs.addTab(form, title)

        def _show_current_data(self, _checked: bool = False, *, validate: bool = True) -> None:
            form = self._forms[self._tabs.currentIndex()]
            if validate:
                try:
                    data = form.get_data()
                except (ValidationError, ValueError) as exc:
                    self._output.setPlainText(str(exc))
                    return
                key = "data"
            else:
                data = form.raw_data()
                key = "raw_data"
            self._output.setPlainText(
                json.dumps(
                    {key: data, "dirty_fields": sorted(form.dirty_fields())}, indent=2, default=str
                )
            )

        def _on_form_changed(self, form: PydanticWidgetForm) -> None:
            if form is self._forms[self._tabs.currentIndex()]:
                self._show_current_data(validate=False)

    app = QApplication(sys.argv)
    apply_theme("dark")
    window = ExampleWindow()
    window.show()
    sys.exit(app.exec())
