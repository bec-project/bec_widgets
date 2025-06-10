from __future__ import annotations

import typing
from abc import abstractmethod
from decimal import Decimal
from types import GenericAlias, UnionType
from typing import Callable, Final, Iterable, Literal, NamedTuple, OrderedDict, get_args

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from qtpy import QtCore
from qtpy.QtCore import QSize, Qt, Signal  # type: ignore
from qtpy.QtGui import QFontMetrics
from qtpy.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.editors.dict_backed_table import DictBackedTable
from bec_widgets.widgets.editors.scan_metadata._util import (
    clearable_required,
    field_default,
    field_limits,
    field_maxlen,
    field_minlen,
    field_precision,
)
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch

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
            if v.__origin__ in [list, dict, set] and all(
                arg in allowed_primitives for arg in v.__args__
            ):
                return v
            raise ValueError(
                f"Generics of type {v} are not supported - only lists, dicts and sets of primitive types {allowed_primitives}"
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


DynamicFormItemType = str | int | float | Decimal | bool | dict | list | None


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
        assert isinstance(self._main_widget, QWidget), "Please set a widget in _add_main_widget()"  # type: ignore
        self._main_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
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
        if button := getattr(self, "_clear_button", None):
            button.setVisible(False)

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


class StrFormItem(DynamicFormItem):
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
            return self._main_widget.setText("")
        self._main_widget.setText(str(value))


class IntFormItem(DynamicFormItem):
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


class FloatDecimalFormItem(DynamicFormItem):
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


class BoolFormItem(DynamicFormItem):
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


class BoolToggleFormItem(BoolFormItem):
    def __init__(self, *, parent: QWidget | None = None, spec: FormItemSpec) -> None:
        if spec.info.default is PydanticUndefined:
            spec.info.default = False
        super().__init__(parent=parent, spec=spec)

    def _add_main_widget(self) -> None:
        self._main_widget = ToggleSwitch()
        self._layout.addWidget(self._main_widget)
        self._main_widget.setToolTip(self._describe(""))
        if self._default is not None:
            self._main_widget.setChecked(self._default)


class DictFormItem(DynamicFormItem):
    def __init__(self, *, parent: QWidget | None = None, spec: FormItemSpec) -> None:
        super().__init__(parent=parent, spec=spec)
        self._main_widget.data_changed.connect(self._value_changed)
        if spec.info.default is not PydanticUndefined:
            self._main_widget.set_default(spec.info.default)

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


class _ItemAndWidgetType(NamedTuple):
    # TODO: this should be generic but not supported in 3.10
    item: type[int | float | str]
    widget: type[QWidget]
    default: int | float | str


class ListFormItem(DynamicFormItem):
    def __init__(self, *, parent: QWidget | None = None, spec: FormItemSpec) -> None:
        if spec.info.annotation is list:
            self._types = _ItemAndWidgetType(str, QLineEdit, "")
        elif isinstance(spec.info.annotation, GenericAlias):
            args = set(typing.get_args(spec.info.annotation))
            if args == {str}:
                self._types = _ItemAndWidgetType(str, QLineEdit, "")
            if args == {int}:
                self._types = _ItemAndWidgetType(int, QSpinBox, 0)
            if args == {float} or args == {int, float}:
                self._types = _ItemAndWidgetType(float, QDoubleSpinBox, 0.0)
        else:
            self._types = _ItemAndWidgetType(str, QLineEdit, "")
        super().__init__(parent=parent, spec=spec)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self._main_widget: QListWidget
        self._data = []
        self._min_lines = 2 if spec.pretty_display else 4
        self._repop(self._data)

    def sizeHint(self):
        default = super().sizeHint()
        return QSize(default.width(), QFontMetrics(self.font()).height() * 6)

    def _add_main_widget(self) -> None:
        self._main_widget = QListWidget()
        self._layout.addWidget(self._main_widget)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._add_buttons()

    def _add_buttons(self):
        self._button_holder = QWidget()
        self._buttons = QVBoxLayout()
        self._button_holder.setLayout(self._buttons)
        self._layout.addWidget(self._button_holder)
        self._add_button = QPushButton("+")
        self._add_button.setToolTip("add a new row")
        self._remove_button = QPushButton("-")
        self._remove_button.setToolTip("delete the focused row (if any)")
        self._add_button.clicked.connect(self._add_row)
        self._remove_button.clicked.connect(self._delete_row)
        self._buttons.addWidget(self._add_button)
        self._buttons.addWidget(self._remove_button)

    def _set_pretty_display(self):
        super()._set_pretty_display()
        self._button_holder.setHidden(True)

    def _repop(self, data):
        self._main_widget.clear()
        for val in data:
            self._add_list_item(val)
        self.scale_to_data()

    def _add_data_item(self, val=None):
        val = val or self._types.default
        self._data.append(val)
        self._add_list_item(val)
        self._repop(self._data)

    def _add_list_item(self, val):
        item = QListWidgetItem(self._main_widget)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEditable)
        item_widget = self._types.widget(parent=self)
        WidgetIO.set_value(item_widget, val)
        self._main_widget.setItemWidget(item, item_widget)
        self._main_widget.addItem(item)
        WidgetIO.connect_widget_change_signal(item_widget, self._update)
        return item_widget

    def _update(self, _, value, *args):
        self._data[self._main_widget.currentRow()] = value

    @SafeSlot()
    def _add_row(self):
        self._add_data_item(self._types.default)
        self._repop(self._data)

    @SafeSlot()
    def _delete_row(self):
        if selected := self._main_widget.currentItem():
            self._main_widget.removeItemWidget(selected)
            row = self._main_widget.currentRow()
            self._main_widget.takeItem(row)
            self._data.pop(row)
        self._repop(self._data)

    @SafeSlot()
    def clear(self):
        self._repop([])

    def getValue(self):
        return self._data

    def setValue(self, value: Iterable):
        if set(map(type, value)) | {self._types.item} != {self._types.item}:
            raise ValueError(f"This widget only accepts items of type {self._types.item}")
        self._data = list(value)
        self._repop(self._data)

    def _line_height(self):
        return QFontMetrics(self._main_widget.font()).height()

    def set_max_height_in_lines(self, lines: int):
        outer_inc = 1 if self._spec.pretty_display else 3
        self._main_widget.setFixedHeight(self._line_height() * max(lines, self._min_lines))
        self._button_holder.setFixedHeight(self._line_height() * (max(lines, self._min_lines) + 1))
        self.setFixedHeight(self._line_height() * (max(lines, self._min_lines) + outer_inc))

    def scale_to_data(self, *_):
        self.set_max_height_in_lines(self._main_widget.count() + 1)


class SetFormItem(ListFormItem):
    def _add_main_widget(self) -> None:
        super()._add_main_widget()
        self._add_item_field = self._types.widget()
        self._buttons.addWidget(QLabel("Add new:"))
        self._buttons.addWidget(self._add_item_field)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)

    @SafeSlot()
    def _add_row(self):
        self._add_data_item(WidgetIO.get_value(self._add_item_field))
        self._repop(self._data)

    def _update(self, _, value, *args):
        if value in self._data:
            return
        return super()._update(_, value, *args)

    def _add_data_item(self, val=None):
        val = val or self._types.default
        if val == self._types.default or val in self._data:
            return
        self._data.append(val)
        self._add_list_item(val)

    def _add_list_item(self, val):
        item_widget = super()._add_list_item(val)
        if isinstance(item_widget, QLineEdit):
            item_widget.setReadOnly(True)
        return item_widget

    def getValue(self):
        return set(self._data)

    def setValue(self, value: set):
        return super().setValue(set(value))


class StrLiteralFormItem(DynamicFormItem):
    def _add_main_widget(self) -> None:
        self._main_widget = QComboBox()
        self._options = get_args(self._spec.info.annotation)
        for opt in self._options:
            self._main_widget.addItem(opt)
        self._layout.addWidget(self._main_widget)

    def getValue(self):
        return self._main_widget.currentText()

    def setValue(self, value: str | None):
        if value is None:
            self.clear()
        for i in range(self._main_widget.count()):
            if self._main_widget.itemText(i) == value:
                self._main_widget.setCurrentIndex(i)
                return
        raise ValueError(f"Cannot set value: {value}, options are: {self._options}")

    def clear(self):
        self._main_widget.setCurrentIndex(-1)


WidgetTypeRegistry = OrderedDict[str, tuple[Callable[[FormItemSpec], bool], type[DynamicFormItem]]]

DEFAULT_WIDGET_TYPES: Final[WidgetTypeRegistry] = OrderedDict() | {
    # dict literals are ordered already but TypedForm subclasses may modify coppies of this dict
    # and delete/insert keys or change the order
    "literal_str": (
        lambda spec: type(spec.info.annotation) is type(Literal[""])
        and set(type(arg) for arg in get_args(spec.info.annotation)) == {str},
        StrLiteralFormItem,
    ),
    "str": (lambda spec: spec.item_type in [str, str | None, None], StrFormItem),
    "int": (lambda spec: spec.item_type in [int, int | None], IntFormItem),
    "float_decimal": (
        lambda spec: spec.item_type in [float, float | None, Decimal, Decimal | None],
        FloatDecimalFormItem,
    ),
    "bool": (lambda spec: spec.item_type in [bool, bool | None], BoolFormItem),
    "dict": (
        lambda spec: spec.item_type in [dict, dict | None]
        or (isinstance(spec.item_type, GenericAlias) and spec.item_type.__origin__ is dict),
        DictFormItem,
    ),
    "list": (
        lambda spec: spec.item_type in [list, list | None]
        or (isinstance(spec.item_type, GenericAlias) and spec.item_type.__origin__ is list),
        ListFormItem,
    ),
    "set": (
        lambda spec: spec.item_type in [set, set | None]
        or (isinstance(spec.item_type, GenericAlias) and spec.item_type.__origin__ is set),
        SetFormItem,
    ),
}


def widget_from_type(
    spec: FormItemSpec, widget_types: WidgetTypeRegistry | None = None
) -> type[DynamicFormItem]:
    widget_types = widget_types or DEFAULT_WIDGET_TYPES
    for predicate, widget_type in widget_types.values():
        if predicate(spec):
            return widget_type
    logger.warning(
        f"Type {spec.item_type=} / {spec.info.annotation=} is not (yet) supported in dynamic form creation."
    )
    return StrFormItem


if __name__ == "__main__":  # pragma: no cover

    class TestModel(BaseModel):
        value0: set = Field(set(["a", "b"]))
        value1: str | None = Field(None)
        value2: bool | None = Field(None)
        value3: bool = Field(True)
        value4: int = Field(123)
        value5: int | None = Field()
        value6: list[int] = Field()
        value7: list = Field()

    app = QApplication([])
    w = QWidget()
    layout = QGridLayout()
    w.setLayout(layout)
    items = []
    for i, (field_name, info) in enumerate(TestModel.model_fields.items()):
        spec = spec = FormItemSpec(item_type=info.annotation, name=field_name, info=info)
        layout.addWidget(QLabel(field_name), i, 0)
        widg = widget_from_type(spec)(spec=spec)
        items.append(widg)
        layout.addWidget(widg, i, 1)

    items[6].setValue([1, 2, 3, 4])
    items[7].setValue(["1", "2", "asdfg", "qwerty"])

    w.show()
    app.exec()
