from __future__ import annotations

from abc import abstractmethod
from decimal import Decimal
from types import GenericAlias, UnionType
from typing import Literal

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.fields import FieldInfo
from qtpy.QtCore import Signal  # type: ignore
from qtpy.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QWidget,
)

from bec_widgets.widgets.editors.dict_backed_table import DictBackedTable
from bec_widgets.widgets.editors.scan_metadata._util import (
    clearable_required,
    field_default,
    field_limits,
    field_maxlen,
    field_minlen,
    field_precision,
)

logger = bec_logger.logger


class FormItemSpec(BaseModel):
    """
    The specification for an item in a dynamically generated form. Uses a pydantic FieldInfo
    to store most annotation info, since one of the main purposes is to store data for
    forms genrated from pydantic models, but can also be composed from other sources or by hand.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    item_type: type | UnionType | GenericAlias
    name: str
    info: FieldInfo = FieldInfo()
    pretty_display: bool = Field(
        default=False,
        description="Whether to use a pretty display for the widget. Defaults to False. If True, disables the widget, doesn't add a clear button, and adapts the stylesheet for non-editable display.",
    )

    @field_validator("item_type", mode="before")
    @classmethod
    def _validate_type(cls, v):
        allowed_primitives = [str, int, float, bool]
        if isinstance(v, (type, UnionType)):
            return v
        if isinstance(v, GenericAlias):
            if v.__origin__ in [list, dict] and all(
                arg in allowed_primitives for arg in v.__args__
            ):
                return v
            raise ValueError(
                f"Generics of type {v} are not supported - only lists and dicts of primitive types {allowed_primitives}"
            )
        if type(v) is type(Literal[""]):  # _LiteralGenericAlias is not exported from typing
            arg_types = set(type(arg) for arg in v.__args__)
            if len(arg_types) != 1:
                raise ValueError("Mixtures of literal types are not supported!")
            if (t := arg_types.pop()) in allowed_primitives:
                return t
            raise ValueError(f"Literals of type {t} are not supported")


class ClearableBoolEntry(QWidget):
    stateChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self._entry = QButtonGroup()
        self._true = QRadioButton("true", parent=self)
        self._false = QRadioButton("false", parent=self)
        for button in [self._true, self._false]:
            self._layout.addWidget(button)
            self._entry.addButton(button)
            button.toggled.connect(self.stateChanged)

    def clear(self):
        self._entry.setExclusive(False)
        self._true.setChecked(False)
        self._false.setChecked(False)
        self._entry.setExclusive(True)

    def isChecked(self) -> bool | None:
        if not self._true.isChecked() and not self._false.isChecked():
            return None
        return self._true.isChecked()

    def setChecked(self, value: bool | None):
        if value is None:
            self.clear()
        elif value:
            self._true.setChecked(True)
            self._false.setChecked(False)
        else:
            self._true.setChecked(False)
            self._false.setChecked(True)

    def setToolTip(self, tooltip: str):
        self._true.setToolTip(tooltip)
        self._false.setToolTip(tooltip)


DynamicFormItemType = str | int | float | Decimal | bool | dict


class DynamicFormItem(QWidget):
    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None, *, spec: FormItemSpec) -> None:
        """
        Initializes the form item widget.

        Args:
            parent (QWidget | None, optional): The parent widget. Defaults to None.
            spec (FormItemSpec): The specification for the form item.
        """
        super().__init__(parent)
        self._spec = spec
        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetMaximumSize)
        self._default = field_default(self._spec.info)
        self._desc = self._spec.info.description
        self.setLayout(self._layout)
        self._add_main_widget()
        self._main_widget: QWidget
        self._main_widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        if not spec.pretty_display:
            if clearable_required(spec.info):
                self._add_clear_button()
        else:
            self._set_pretty_display()

    @abstractmethod
    def getValue(self) -> DynamicFormItemType: ...

    @abstractmethod
    def setValue(self, value): ...

    @abstractmethod
    def _add_main_widget(self) -> None:
        """Add the main data entry widget to self._main_widget and appply any
        constraints from the field info"""

    def _set_pretty_display(self):
        self.setEnabled(False)

    def _describe(self, pad=" "):
        return pad + (self._desc if self._desc else "")

    def _add_clear_button(self):
        self._clear_button = QToolButton()
        self._clear_button.setIcon(
            material_icon(icon_name="close", size=(10, 10), convert_to_pixmap=False)
        )
        self._layout.addWidget(self._clear_button)
        # the widget added in _add_main_widget must implement .clear() if value is not required
        self._clear_button.setToolTip("Clear value or reset to default.")
        self._clear_button.clicked.connect(self._main_widget.clear)  # type: ignore

    def _value_changed(self, *_, **__):
        self.valueChanged.emit()


class StrMetadataField(DynamicFormItem):
    def __init__(self, parent: QWidget | None = None, *, spec: FormItemSpec) -> None:
        super().__init__(parent=parent, spec=spec)
        self._main_widget.textChanged.connect(self._value_changed)

    def _add_main_widget(self) -> None:
        self._main_widget = QLineEdit()
        self._layout.addWidget(self._main_widget)
        min_length, max_length = (field_minlen(self._spec.info), field_maxlen(self._spec.info))
        if max_length:
            self._main_widget.setMaxLength(max_length)
        self._main_widget.setToolTip(
            f"(length min: {min_length} max: {max_length}){self._describe()}"
        )
        if self._default:
            self._main_widget.setText(self._default)
            self._add_clear_button()

    def getValue(self):
        if self._main_widget.text() == "":
            return self._default
        return self._main_widget.text()

    def setValue(self, value: str):
        if value is None:
            self._main_widget.setText("")
        self._main_widget.setText(str(value))


class IntMetadataField(DynamicFormItem):
    def __init__(self, parent: QWidget | None = None, *, spec: FormItemSpec) -> None:
        super().__init__(parent=parent, spec=spec)
        self._main_widget.textChanged.connect(self._value_changed)

    def _add_main_widget(self) -> None:
        self._main_widget = QSpinBox()
        self._layout.addWidget(self._main_widget)
        min_, max_ = field_limits(self._spec.info, int)
        self._main_widget.setMinimum(min_)
        self._main_widget.setMaximum(max_)
        self._main_widget.setToolTip(f"(range {min_} to {max_}){self._describe()}")
        if self._default is not None:
            self._main_widget.setValue(self._default)
            self._add_clear_button()
        else:
            self._main_widget.clear()

    def getValue(self):
        if self._main_widget.text() == "":
            return self._default
        return self._main_widget.value()

    def setValue(self, value: int):
        if value is None:
            self._main_widget.clear()
        self._main_widget.setValue(value)


class FloatDecimalMetadataField(DynamicFormItem):
    def __init__(self, parent: QWidget | None = None, *, spec: FormItemSpec) -> None:
        super().__init__(parent=parent, spec=spec)
        self._main_widget.textChanged.connect(self._value_changed)

    def _add_main_widget(self) -> None:
        precision = field_precision(self._spec.info)
        self._main_widget = QDoubleSpinBox()
        self._layout.addWidget(self._main_widget)
        min_, max_ = field_limits(self._spec.info, float, precision)
        self._main_widget.setMinimum(min_)
        self._main_widget.setMaximum(max_)
        if precision:
            self._main_widget.setDecimals(precision)
        minstr = f"{float(min_):.3f}" if abs(min_) <= 1000 else f"{float(min_):.3e}"
        maxstr = f"{float(max_):.3f}" if abs(max_) <= 1000 else f"{float(max_):.3e}"
        self._main_widget.setToolTip(f"(range {minstr} to {maxstr}){self._describe()}")
        if self._default is not None:
            self._main_widget.setValue(self._default)
            self._add_clear_button()
        else:
            self._main_widget.clear()

    def getValue(self):
        if self._main_widget.text() == "":
            return self._default
        return self._main_widget.value()

    def setValue(self, value: float | Decimal):
        if value is None:
            self._main_widget.clear()
        self._main_widget.setValue(float(value))


class BoolMetadataField(DynamicFormItem):
    def __init__(self, *, parent: QWidget | None = None, spec: FormItemSpec) -> None:
        super().__init__(parent=parent, spec=spec)
        self._main_widget.stateChanged.connect(self._value_changed)

    def _add_main_widget(self) -> None:
        if clearable_required(self._spec.info):
            self._main_widget = ClearableBoolEntry()
        else:
            self._main_widget = QCheckBox()
        self._layout.addWidget(self._main_widget)
        self._main_widget.setToolTip(self._describe(""))
        self._main_widget.setChecked(self._default)  # type: ignore # if there is no default then it will be ClearableBoolEntry and can be set with None

    def getValue(self):
        return self._main_widget.isChecked()

    def setValue(self, value):
        self._main_widget.setChecked(value)


class DictMetadataField(DynamicFormItem):
    def __init__(self, *, parent: QWidget | None = None, spec: FormItemSpec) -> None:
        super().__init__(parent=parent, spec=spec)
        self._main_widget.data_changed.connect(self._value_changed)

    def _set_pretty_display(self):
        self._main_widget.set_button_visibility(False)
        super()._set_pretty_display()

    def _add_main_widget(self) -> None:
        self._main_widget = DictBackedTable(self, [])
        self._layout.addWidget(self._main_widget)
        self._main_widget.setToolTip(self._describe(""))

    def getValue(self):
        return self._main_widget.dump_dict()

    def setValue(self, value):
        self._main_widget.replace_data(value)


def widget_from_type(annotation: type | UnionType | None) -> type[DynamicFormItem]:
    if annotation in [str, str | None]:
        return StrMetadataField
    if annotation in [int, int | None]:
        return IntMetadataField
    if annotation in [float, float | None, Decimal, Decimal | None]:
        return FloatDecimalMetadataField
    if annotation in [bool, bool | None]:
        return BoolMetadataField
    if annotation in [dict, dict | None] or (
        isinstance(annotation, GenericAlias) and annotation.__origin__ is dict
    ):
        return DictMetadataField
    if annotation in [list, list | None] or (
        isinstance(annotation, GenericAlias) and annotation.__origin__ is list
    ):
        return StrMetadataField
    else:
        logger.warning(f"Type {annotation} is not (yet) supported in metadata form creation.")
        return StrMetadataField


if __name__ == "__main__":  # pragma: no cover

    class TestModel(BaseModel):
        value1: str | None = Field(None)
        value2: bool | None = Field(None)
        value3: bool = Field(True)
        value4: int = Field(123)
        value5: int | None = Field()

    app = QApplication([])
    w = QWidget()
    layout = QGridLayout()
    w.setLayout(layout)
    for i, (field_name, info) in enumerate(TestModel.model_fields.items()):
        layout.addWidget(QLabel(field_name), i, 0)
        layout.addWidget(widget_from_type(info.annotation)(info), i, 1)

    w.show()
    app.exec()
