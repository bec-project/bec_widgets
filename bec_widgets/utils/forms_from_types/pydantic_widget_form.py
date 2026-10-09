from __future__ import annotations

from decimal import Decimal
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

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

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.forms_from_types.entry_list_editor import EntryListEditor, ExtraFieldsSection
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

#: Key of :meth:`PydanticWidgetForm.validation_errors` entries about the extra fields editor.
EXTRA_FIELDS_KEY = "__extra_fields__"


def _value_annotation(annotation: Any) -> Any:
    """Return the annotation without ``None`` for ``X | None``; unchanged otherwise."""
    non_none_args = tuple(arg for arg in get_args(annotation) if arg is not NoneType)
    if NoneType in get_args(annotation) and len(non_none_args) == 1:
        return non_none_args[0]
    return annotation


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


# pylint: disable-next=too-many-instance-attributes,too-many-public-methods
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

    def __init__(  # pylint: disable=too-many-arguments
        self,
        model: type[BaseModel],
        parent: QWidget | None = None,
        *,
        data: BaseModel | dict[str, Any] | None = None,
        read_only_fields: set[str] | None = None,
        client=None,
        allow_extra_fields: bool = False,
        extra_fields_title: str = "Additional fields",
        extra_fields_hint: str = "",
        mark_required: bool = False,
        empty_text_as_missing: bool = False,
    ) -> None:
        """Create a generated form for a Pydantic model.

        Args:
            model: Pydantic model class used to generate fields and validate data.
            parent: Optional parent widget.
            data: Optional initial model instance or raw field-value mapping.
            read_only_fields: Field names that should be displayed but not editable.
            client: Optional BEC client passed to domain-specific widgets such as
                device and signal combo boxes.
            allow_extra_fields: Show a key/value editor below the model fields for
                entries that are not part of the model. Only useful for models with
                ``extra="allow"``.
            extra_fields_title: Heading of the extra fields editor.
            extra_fields_hint: Hint shown in the extra fields editor while it is empty.
            mark_required: Append ``*`` to the labels of fields without a default.
            empty_text_as_missing: Treat an empty text field without a default as a
                missing value, so validation reports it as required instead of
                accepting an empty string.
        """
        super().__init__(parent=parent)
        self._model = model
        self._client = client
        self._read_only_fields = set(read_only_fields or set())
        self._widgets: dict[str, QWidget] = {}
        self._field_configs: dict[str, dict[str, Any]] = {}
        self._baseline: dict[str, Any] = {}
        self._mark_required = mark_required
        self._empty_text_as_missing = empty_text_as_missing
        self._shown_errors: dict[str, str] = {}
        self._extra_section: ExtraFieldsSection | None = None
        if allow_extra_fields:
            self._extra_section = ExtraFieldsSection(
                self, title=extra_fields_title, empty_text=extra_fields_hint
            )
            self._extra_section.editor.changed.connect(self.changed)

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

    @property
    def extra_fields_section(self) -> ExtraFieldsSection | None:
        """Return the extra fields section, or ``None`` if extra fields are disabled."""
        return self._extra_section

    def field_label(self, name: str) -> str:
        """Return the user-facing label of field ``name``, without the required marker."""
        return self._field_configs[name]["display_name"]

    def extra_data(self) -> dict[str, str]:
        """Return the non-blank extra fields as a mapping; empty when they are disabled."""
        if self._extra_section is None:
            return {}
        return self._extra_section.editor.value()

    def set_extra_data(self, data: dict[str, Any] | None) -> None:
        """Replace the entries of the extra fields editor.

        Args:
            data: Mapping of extra keys to values; ``None`` clears the editor.
        """
        if self._extra_section is None:
            return
        self._extra_section.editor.set_value(data)

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
        if self._extra_section is not None:
            self.set_extra_data(
                {key: value for key, value in values.items() if key not in self._widgets}
            )
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
            Mapping of model field names to raw widget values, followed by the
            entries of the extra fields editor that do not shadow a model field.
        """
        data = {name: self._read_widget_value(name) for name in self._widgets}
        for key, value in self.extra_data().items():
            data.setdefault(key, value)
        return data

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
        self._validate_extra_fields()
        return self._model.model_validate(self._validation_payload())

    def validate(self) -> bool:
        """Validate the current form values and highlight the fields that are invalid.

        Returns:
            ``True`` when current values validate successfully, otherwise ``False``.
        """
        errors = self.validation_errors()
        self._show_errors(errors)
        self.validity_changed.emit(not errors)
        return not errors

    def validation_errors(self) -> dict[str, str]:
        """Return the first validation error of each invalid field.

        Returns:
            Mapping of field names to error messages. Problems in the extra fields
            editor are reported under :data:`EXTRA_FIELDS_KEY`; errors Pydantic
            cannot attribute to a field are reported under ``""``. Empty when the
            form is valid.
        """
        errors = dict(self._domain_widget_errors())
        extra_errors = self._extra_field_errors()
        if extra_errors:
            errors[EXTRA_FIELDS_KEY] = next(iter(extra_errors.values()))
        try:
            self._model.model_validate(self._validation_payload())
        except ValidationError as exc:
            for error in exc.errors():
                loc = error.get("loc") or ("",)
                errors.setdefault(str(loc[0]), error["msg"])
        return errors

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
        if self._extra_section is not None and self._layout.indexOf(self._extra_section) >= 0:
            # The extra fields section outlives model changes; take it out before clearing.
            self._layout.takeRow(self._extra_section)
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
        self._shown_errors.clear()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.cleanup()
        super().closeEvent(event)

    def _populate(self) -> None:
        for config in pydantic_model_input_configs(self._model):
            name = config["name"]
            info = self._model.model_fields[name]
            widget = self._create_widget(name, info)
            label_text = config["display_name"]
            if self._mark_required and info.is_required():
                label_text = f"{label_text} *"
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

        if self._extra_section is not None:
            self._layout.addRow(self._extra_section)

        self._connect_device_signal_widgets()
        self._connect_reference_unit_widgets()
        self._refresh_reference_units()

    def _create_widget(self, name: str, info: FieldInfo) -> QWidget:
        annotation = info.annotation
        optional = NoneType in get_args(annotation)
        value_annotation = _value_annotation(annotation)

        widget = self._create_value_widget(name, value_annotation)
        numeric = value_annotation in (int, float, Decimal) or (
            get_origin(value_annotation) in (Union, UnionType)
            and any(arg in (int, float, Decimal) for arg in get_args(value_annotation))
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
            if NoneType in get_args(self._model.model_fields[name].annotation):
                widget.addItem("")  # the empty entry stands for None
            widget.addItems([str(value) for value in get_args(annotation)])
            return widget
        if annotation is Decimal:
            spin_box = QDoubleSpinBox(self)
            spin_box.setRange(-1_000_000_000, 1_000_000_000)
            return spin_box
        container = get_origin(annotation) or annotation
        if container in (dict, list, set, tuple):
            return EntryListEditor(self, key_value=container is dict, add_text="Add entry")
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

        if isinstance(input_widget, QLineEdit):
            if config.get("max_length") is not None:
                input_widget.setMaxLength(int(config["max_length"]))
            placeholder = config.get("placeholder") or config.get("description")
            if placeholder:
                input_widget.setPlaceholderText(str(placeholder))

    def _connect_widget(self, widget: QWidget) -> None:
        if isinstance(widget, OptionalValueWidget):
            widget.value_changed.connect(lambda _value: self.changed.emit())
            return
        if isinstance(widget, EntryListEditor):
            widget.changed.connect(self.changed)
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
        for message in self._domain_widget_errors().values():
            raise ValueError(message)

    def _domain_widget_errors(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        for name, widget in self._widgets.items():
            if isinstance(widget, DeviceComboBox):
                device = widget.currentText().strip()
                if not device:
                    errors[name] = "Device is required."
                elif not widget.is_valid_input:
                    errors[name] = f"Device '{device}' is not available."
            if isinstance(widget, SignalComboBox):
                signal = widget.get_signal_name().strip()
                if signal and not widget.is_valid_input:
                    errors[name] = f"Signal '{signal}' is not available."
        return errors

    def _validate_extra_fields(self) -> None:
        for message in self._extra_field_errors().values():
            raise ValueError(message)

    def _extra_field_errors(self) -> dict[int, str]:
        if self._extra_section is None:
            return {}
        return self._extra_section.row_errors(set(self._widgets))

    def _validation_payload(self) -> dict[str, Any]:
        data = self.raw_data()
        if self._empty_text_as_missing:
            for name, widget in self._widgets.items():
                if (
                    isinstance(widget, QLineEdit)
                    and data.get(name) in ("", None)
                    and self._model.model_fields[name].is_required()
                ):
                    data.pop(name, None)
        return data

    def _show_errors(self, errors: dict[str, str]) -> None:
        """Highlight invalid inputs and their labels; clear fields that became valid."""
        for name in set(self._shown_errors) | set(errors):
            if name not in self._widgets:
                continue
            message = errors.get(name)
            if self._shown_errors.get(name) == message:
                continue
            widget = self.input_widget(name)
            widget.setProperty("state", "error" if message else "")
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            label = self._layout.labelForField(self._widgets[name])
            if label is not None:
                # Themes do not style QLabel[state="error"], so colour the label directly.
                error_color = get_accent_colors().emergency.name()
                label.setStyleSheet(f"color: {error_color};" if message else "")
        if self._extra_section is not None:
            self._extra_section.show_row_errors(set(self._widgets))
        self._shown_errors = {name: msg for name, msg in errors.items() if name in self._widgets}

    def _read_widget_value(self, name: str) -> Any:
        widget = self._widgets[name]
        info = self._model.model_fields[name]
        if isinstance(widget, OptionalValueWidget):
            return widget.value()
        if isinstance(widget, EntryListEditor):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox) and _value_annotation(info.annotation) is Decimal:
            return Decimal(f"{widget.value():.{widget.decimals()}f}")
        if isinstance(widget, QLineEdit):
            value = WidgetIO.get_value(widget)
            return None if NoneType in get_args(info.annotation) and value == "" else value
        if (
            isinstance(widget, QComboBox)
            and get_origin(_value_annotation(info.annotation)) is Literal
        ):
            value = WidgetIO.get_value(widget, as_string=True)
            return None if NoneType in get_args(info.annotation) and value == "" else value
        return WidgetIO.get_value(widget)

    def _set_widget_value(self, name: str, value: Any) -> None:
        widget = self._widgets[name]
        if isinstance(widget, OptionalValueWidget):
            widget.set_value(value)
            return
        if isinstance(widget, EntryListEditor):
            widget.set_value(value)
            return
        if isinstance(value, Decimal):
            value = float(value)
        if value is None:
            if isinstance(widget, QLineEdit):
                value = ""
            elif isinstance(widget, QCheckBox):
                value = False
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                value = 0
            elif isinstance(widget, QComboBox):
                value = ""
        elif isinstance(widget, QLineEdit) and not isinstance(value, str):
            value = str(value)
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
