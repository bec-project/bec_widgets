from __future__ import annotations

from abc import abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, get_args

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from pydantic import BaseModel, Field
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
    QSpinBox,
    QToolButton,
    QWidget,
)

from bec_widgets.widgets.editors.scan_metadata._util import (
    clearable_required,
    field_default,
    field_limits,
    field_maxlen,
    field_minlen,
    field_precision,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

logger = bec_logger.logger


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


class MetadataWidget(QWidget):

    valueChanged = Signal()

    def __init__(self, info: FieldInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._info = info
        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetMaximumSize)
        self._default = field_default(self._info)
        self._desc = self._info.description
        self.setLayout(self._layout)
        self._add_main_widget()
        if clearable_required(info):
            self._add_clear_button()

    @abstractmethod
    def getValue(self): ...

    @abstractmethod
    def setValue(self, value): ...

    @abstractmethod
    def _add_main_widget(self) -> None:
        """Add the main data entry widget to self._main_widget and appply any
        constraints from the field info"""

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


class StrMetadataField(MetadataWidget):
    def __init__(self, info: FieldInfo, parent: QWidget | None = None) -> None:
        super().__init__(info, parent)
        self._main_widget.textChanged.connect(self._value_changed)

    def _add_main_widget(self) -> None:
        self._main_widget = QLineEdit()
        self._layout.addWidget(self._main_widget)
        min_length, max_length = field_minlen(self._info), field_maxlen(self._info)
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
        self._main_widget.setText(value)


class IntMetadataField(MetadataWidget):
    def __init__(self, info: FieldInfo, parent: QWidget | None = None) -> None:
        super().__init__(info, parent)
        self._main_widget.textChanged.connect(self._value_changed)

    def _add_main_widget(self) -> None:
        self._main_widget = QSpinBox()
        self._layout.addWidget(self._main_widget)
        min_, max_ = field_limits(self._info, int)
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


class FloatDecimalMetadataField(MetadataWidget):
    def __init__(self, info: FieldInfo, parent: QWidget | None = None) -> None:
        super().__init__(info, parent)
        self._main_widget.textChanged.connect(self._value_changed)

    def _add_main_widget(self) -> None:
        self._main_widget = QDoubleSpinBox()
        self._layout.addWidget(self._main_widget)
        min_, max_ = field_limits(self._info, int)
        self._main_widget.setMinimum(min_)
        self._main_widget.setMaximum(max_)
        precision = field_precision(self._info)
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

    def setValue(self, value: float):
        if value is None:
            self._main_widget.clear()
        self._main_widget.setValue(value)


class BoolMetadataField(MetadataWidget):
    def __init__(self, info: FieldInfo, parent: QWidget | None = None) -> None:
        super().__init__(info, parent)
        self._main_widget.stateChanged.connect(self._value_changed)

    def _add_main_widget(self) -> None:
        if clearable_required(self._info):
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


def widget_from_type(annotation: type | None) -> Callable[[FieldInfo], MetadataWidget]:
    if annotation in [str, str | None]:
        return StrMetadataField
    if annotation in [int, int | None]:
        return IntMetadataField
    if annotation in [float, float | None, Decimal, Decimal | None]:
        return FloatDecimalMetadataField
    if annotation in [bool, bool | None]:
        return BoolMetadataField
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
