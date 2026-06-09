from __future__ import annotations

from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

from bec_lib.device import DeviceBase, Signal
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
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

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox
from bec_widgets.widgets.utility.spinbox.decimal_spinbox import BECSpinBox


class OptionalValueWidget(QWidget):
    """Generic optional-value wrapper preserving ``None`` for editor widgets."""

    value_changed = QtSignal(object)

    def __init__(self, value_widget: QWidget, parent: QWidget | None = None) -> None:
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
        return self._value_widget

    @property
    def checkbox(self) -> QCheckBox:
        return self._checkbox

    def value(self) -> Any:
        if not self._checkbox.isChecked():
            return None
        return WidgetIO.get_value(self._value_widget)

    def set_value(self, value: Any) -> None:
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
    """Qt form generated from a Pydantic model using type-based widget selection."""

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
        super().__init__(parent=parent)
        self._model = model
        self._client = client
        self._read_only_fields = set(read_only_fields or set())
        self._widgets: dict[str, QWidget] = {}
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
        return self._model

    @property
    def widgets(self) -> dict[str, QWidget]:
        return dict(self._widgets)

    def field_widget(self, name: str) -> QWidget:
        return self._widgets[name]

    def input_widget(self, name: str) -> QWidget:
        widget = self._widgets[name]
        if isinstance(widget, OptionalValueWidget):
            return widget.value_widget
        return widget

    def input_widgets(self) -> dict[str, QWidget]:
        return {name: self.input_widget(name) for name in self._widgets}

    def input_widgets_by_type(self, widget_type: type[QWidget]) -> list[QWidget]:
        return [
            widget for widget in self.input_widgets().values() if isinstance(widget, widget_type)
        ]

    def set_model(self, model: type[BaseModel], data: dict[str, Any] | None = None) -> None:
        old_data = self.raw_data()
        self._clear()
        self._model = model
        self._populate()
        if data is None:
            data = {key: value for key, value in old_data.items() if key in model.model_fields}
        self.set_partial_data(data)
        self.mark_clean()

    def set_data(self, data: BaseModel | dict[str, Any]) -> None:
        values = data.model_dump() if isinstance(data, BaseModel) else dict(data)
        self.set_partial_data(values)

    def set_partial_data(self, data: dict[str, Any]) -> None:
        for name, value in data.items():
            if name not in self._widgets:
                continue
            self._set_widget_value(name, value)
        self.changed.emit()

    def raw_data(self) -> dict[str, Any]:
        return {name: self._read_widget_value(name) for name in self._widgets}

    def get_data(self) -> dict[str, Any]:
        return self.model_instance().model_dump()

    def model_instance(self) -> BaseModel:
        self._validate_domain_widgets()
        return self._model.model_validate(self.raw_data())

    def validate(self) -> bool:
        try:
            self.get_data()
        except (ValidationError, ValueError):
            self.validity_changed.emit(False)
            return False
        self.validity_changed.emit(True)
        return True

    def dirty_fields(self) -> set[str]:
        current = self.raw_data()
        fields = set(current) | set(self._baseline)
        dirty = set()
        for field in fields:
            if self._values_differ(current.get(field), self._baseline.get(field)):
                dirty.add(field)
        return dirty

    def mark_clean(self) -> None:
        self._baseline = self.raw_data()

    def reset_to_baseline(self) -> None:
        self.set_partial_data(self._baseline)

    def editable_data(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.get_data().items()
            if key not in self._read_only_fields
        }

    def raw_editable_data(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.raw_data().items()
            if key not in self._read_only_fields
        }

    def cleanup(self) -> None:
        self._clear(delete_later=False)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.cleanup()
        super().closeEvent(event)

    def _populate(self) -> None:
        for name, info in self._model.model_fields.items():
            widget = self._create_widget(name, info)
            label_text = info.title or self._format_label(name)
            self._layout.addRow(label_text, widget)
            label = self._layout.labelForField(widget)
            if label is not None:
                label.setProperty("_model_field_name", name)
            if info.description:
                widget.setToolTip(info.description)
                if label is not None:
                    label.setToolTip(info.description)
            widget.setEnabled(name not in self._read_only_fields)
            self._widgets[name] = widget
            self._set_widget_value(name, self._field_default(info))
            self._connect_widget(name, widget)

        self._connect_device_signal_widgets()

    def _clear(self, *, delete_later: bool = True) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.close()
                if delete_later:
                    widget.deleteLater()
        self._widgets.clear()

    def _create_widget(self, name: str, info: FieldInfo) -> QWidget:
        annotation = info.annotation
        optional = self._is_optional(annotation)
        value_annotation = self._without_none(annotation)

        widget = self._create_value_widget(name, value_annotation, info)
        if optional and (self._is_numeric_annotation(value_annotation) or value_annotation is bool):
            return OptionalValueWidget(widget, parent=self)
        return widget

    def _create_value_widget(self, name: str, annotation: Any, info: FieldInfo) -> QWidget:
        if self._contains_type(annotation, Signal):
            return SignalComboBox(
                parent=self,
                client=self._client,
                require_device=self._model_has_device_field(),
                arg_name=name,
            )
        if self._contains_type(annotation, DeviceBase):
            return DeviceComboBox(parent=self, client=self._client, arg_name=name)
        if self._is_literal(annotation):
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
            spin_box.setDecimals(int((info.json_schema_extra or {}).get("precision", 6)))
            return spin_box
        return QLineEdit(self)

    def _connect_widget(self, _name: str, widget: QWidget) -> None:
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
            return None if self._is_optional(info.annotation) and value == "" else value
        if isinstance(widget, QComboBox) and self._is_literal(self._without_none(info.annotation)):
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

    @staticmethod
    def _values_differ(current: Any, baseline: Any) -> bool:
        if current is None or baseline is None:
            return current is not None or baseline is not None
        if isinstance(current, float) or isinstance(baseline, float):
            return abs(float(current) - float(baseline)) >= 1e-9
        return current != baseline

    @staticmethod
    def _field_default(info: FieldInfo) -> Any:
        if info.default is not PydanticUndefined:
            return info.default
        if info.default_factory is not None:
            return info.get_default(call_default_factory=True)
        return None

    @staticmethod
    def _format_label(name: str) -> str:
        return name.replace("_", " ").capitalize()

    @staticmethod
    def _is_literal(annotation: Any) -> bool:
        return get_origin(annotation) is Literal

    @classmethod
    def _is_optional(cls, annotation: Any) -> bool:
        return NoneType in cls._annotation_args(annotation)

    @classmethod
    def _without_none(cls, annotation: Any) -> Any:
        args = [arg for arg in cls._annotation_args(annotation) if arg is not NoneType]
        if not args:
            return annotation
        if len(args) == 1:
            return args[0]
        return annotation

    @classmethod
    def _annotation_args(cls, annotation: Any) -> tuple[Any, ...]:
        origin = get_origin(annotation)
        if origin in (Union, UnionType) or isinstance(annotation, UnionType):
            return get_args(annotation)
        return ()

    @classmethod
    def _contains_type(cls, annotation: Any, expected: type) -> bool:
        if isinstance(annotation, type):
            return issubclass(annotation, expected)
        return any(
            isinstance(arg, type) and issubclass(arg, expected)
            for arg in cls._annotation_args(annotation)
        )

    def _model_has_device_field(self) -> bool:
        return any(
            self._is_device_annotation(field.annotation)
            for field in self._model.model_fields.values()
        )

    @classmethod
    def _is_device_annotation(cls, annotation: Any) -> bool:
        return cls._contains_type(annotation, DeviceBase) and not cls._contains_type(
            annotation, Signal
        )

    @classmethod
    def _is_numeric_annotation(cls, annotation: Any) -> bool:
        if annotation in (int, float):
            return True
        return any(arg in (int, float) for arg in cls._annotation_args(annotation))


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    from pydantic import Field
    from qtpy.QtWidgets import QApplication, QLabel, QPushButton, QTabWidget, QTextEdit, QVBoxLayout

    class BasicScanConfig(BaseModel):
        sample_name: str
        enabled: bool = True
        repeats: int = 3

    class LimitConfig(BaseModel):
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
            self.resize(720, 520)

            self._tabs = QTabWidget(self)
            self._output = QTextEdit(self)
            self._output.setReadOnly(True)
            self._output.setPlaceholderText("Validated form data appears here.")
            self._forms: list[PydanticWidgetForm] = []

            self._add_form("Basic", PydanticWidgetForm(BasicScanConfig))
            self._add_form("Limits", PydanticWidgetForm(LimitConfig))
            self._add_form("Display", PydanticWidgetForm(DisplayConfig))
            self._add_form("Device + signal", PydanticWidgetForm(DeviceAndSignalConfig))
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
    window = ExampleWindow()
    window.show()
    sys.exit(app.exec())
