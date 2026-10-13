from __future__ import annotations

from types import GenericAlias, NoneType, UnionType
from typing import NamedTuple, Union, get_args, get_origin

from bec_lib.logger import bec_logger
from pydantic import BaseModel, ValidationError
from qtpy.QtCore import Qt, Signal  # type: ignore
from qtpy.QtWidgets import QApplication, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.forms_from_types import styles
from bec_widgets.utils.forms_from_types.items import (
    DynamicFormItem,
    DynamicFormItemType,
    FormItemSpec,
    widget_from_type,
)

logger = bec_logger.logger


class GridRow(NamedTuple):
    i: int
    label: QLabel
    widget: DynamicFormItem


class ValidationIssue(NamedTuple):
    """One invalid field of a form, ready for display."""

    field: str
    title: str
    problem: str
    entered: str


class TypedForm(BECWidget, QWidget):
    PLUGIN = True
    ICON_NAME = "list_alt"

    value_changed = Signal()

    RPC = True
    USER_ACCESS = ["enabled", "enabled.setter"]

    def __init__(
        self,
        parent=None,
        items: list[tuple[str, type]] | None = None,
        form_item_specs: list[FormItemSpec] | None = None,
        enabled: bool = True,
        pretty_display: bool = False,
        client=None,
        **kwargs,
    ):
        """Widget with a list of form items based on a list of types.

        Args:
            items (list[tuple[str, type]]):         list of tuples of a name for the field and its type.
                                                    Should be a type supported by the logic in items.py
            form_item_specs (list[FormItemSpec]):   list of form item specs, equivalent to items.
                                                    only one of items or form_item_specs should be
                                                    supplied.
            enabled (bool, optional):               whether fields are enabled for editing.
            pretty_display (bool, optional): Whether to use a pretty display for the widget. Defaults to False. If True, disables the widget, doesn't add a clear button, and adapts the stylesheet for non-editable display.
        """
        if items is not None and form_item_specs is not None:
            logger.error(
                "Must specify one and only one of items and form_item_specs! Ignoring `items`."
            )
            items = None
        if items is None and form_item_specs is None:
            logger.error("Must specify one and only one of items and form_item_specs!")
            items = []
        super().__init__(parent=parent, client=client, **kwargs)
        self._items = form_item_specs or [
            FormItemSpec(name=name, item_type=item_type, pretty_display=pretty_display)
            for name, item_type in items  # type: ignore
        ]
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        self._enabled: bool = enabled

        self._form_grid_container = QWidget(parent=self)
        self._form_grid_container.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self._form_grid_container.setLayout(QVBoxLayout())
        self._layout.addWidget(self._form_grid_container)

        self._form_grid = QWidget(parent=self._form_grid_container)
        self._form_grid.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self._form_grid.setLayout(self._new_grid_layout())

        self._widget_types: dict | None = None
        self._widget_from_type = widget_from_type
        self._post_init()

    def _post_init(self):
        """Override this if a subclass should do things after super().__init__ and before populate()"""
        self.populate()
        self.enabled = self._enabled  # type: ignore # QProperty

    def populate(self):
        self._clear_grid()
        for r, item in enumerate(self._items):
            self._add_griditem(item, r)
        gl: QGridLayout = self._form_grid.layout()
        gl.setRowStretch(gl.rowCount(), 1)

    def _add_griditem(self, item: FormItemSpec, row: int):
        grid = self._form_grid.layout()
        # Use title from FieldInfo if available, otherwise use the property name
        label_text = item.info.title if item.info.title else item.name
        label = QLabel(parent=self._form_grid, text=label_text)
        label.setProperty("_model_field_name", item.name)
        label.setToolTip(item.info.description or item.name)
        grid.addWidget(label, row, 0)
        widget = self._widget_from_type(item, self._widget_types)(parent=self._form_grid, spec=item)
        widget.valueChanged.connect(self.value_changed)
        widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        grid.addWidget(widget, row, 1)

    def enumerate_form_widgets(self):
        """Return a generator over the rows of the form, with the row number, the label widget (to
        which the field name is attached as a property "_model_field_name"), and the entry widget"""
        grid: QGridLayout = self._form_grid.layout()  # type: ignore
        for i in range(grid.rowCount() - 1):  # One extra row for stretch
            label, widget = grid.itemAtPosition(i, 0), grid.itemAtPosition(i, 1)
            if label is None or widget is None:  # e.g. the error line under a field
                continue
            yield GridRow(i, label.widget(), widget.widget())

    def _dict_from_grid(self) -> dict[str, DynamicFormItemType]:
        return {
            row.label.property("_model_field_name"): row.widget.getValue()
            for row in self.enumerate_form_widgets()
        }

    def _clear_grid(self):
        gl = self._form_grid.layout()
        while w := gl.takeAt(0):
            w = w.widget()
            if hasattr(w, "teardown"):
                w.teardown()
            w.deleteLater()
        self._form_grid_container.layout().removeWidget(self._form_grid)
        self._form_grid.deleteLater()
        self._form_grid = QWidget()
        self._form_grid.setLayout(self._new_grid_layout())
        self._form_grid_container.layout().addWidget(self._form_grid)
        self.update_size()

    def update_size(self):
        self._form_grid.adjustSize()
        self._form_grid_container.adjustSize()
        self.adjustSize()

    def _new_grid_layout(self):
        new_grid = QGridLayout()
        new_grid.setContentsMargins(0, 0, 0, 0)
        return new_grid

    @property
    def widget_dict(self):
        return {
            row.label.property("_model_field_name"): row.widget
            for row in self.enumerate_form_widgets()
        }

    @SafeProperty(bool)
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        self.setEnabled(value)


class PydanticModelForm(TypedForm):
    form_data_updated = Signal(dict)
    form_data_cleared = Signal(NoneType)
    validity_proc = Signal(bool)

    def __init__(
        self,
        parent=None,
        data_model: type[BaseModel] | None = None,
        enabled: bool = True,
        pretty_display: bool = False,
        client=None,
        **kwargs,
    ):
        """
        A form generated from a pydantic model.

        Args:
            data_model (type[BaseModel]): the model class for which to generate a form.
            enabled (bool, optional): whether fields are enabled for editing.
            pretty_display (bool, optional): Whether to use a pretty display for the widget. Defaults to False. If True, disables the widget, doesn't add a clear button, and adapts the stylesheet for non-editable display.

        """
        self._pretty_display = pretty_display
        self._md_schema = data_model
        self._field_errors: dict[str, QLabel] = {}
        super().__init__(
            parent=parent,
            form_item_specs=self._form_item_specs(),
            enabled=enabled,
            client=client,
            **kwargs,
        )

        self._validity_message = QLabel("Not yet validated", self)
        self._validity_message.setWordWrap(True)
        self._validity_message.setTextFormat(Qt.TextFormat.PlainText)
        self._validity = self._validity_message
        self._validity_state: bool | None = None
        self._validity_summary = "Not yet validated"
        self._validity_issues: list[ValidationIssue] = []
        self._layout.addWidget(self._validity)
        self.value_changed.connect(self.validate_form)

        self._connect_pretty_display_theme()

    @SafeSlot()
    def clear(self): ...

    def set_pretty_display_theme(self, theme: str = "dark"):
        if self._pretty_display:
            self.setStyleSheet(styles.pretty_display_theme(theme))

    def _connect_pretty_display_theme(self):
        """Connect the pretty-display styling to the theme-updated signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self.set_pretty_display_theme)  # type: ignore

    def set_schema(self, schema: type[BaseModel]):
        self._md_schema = schema
        self.populate()

    def set_data(self, data: BaseModel):
        """Fill the data for the form.

        Args:
            data (BaseModel):   the data to enter into the form. Must be the same type as the
                                currently set schema, raises TypeError otherwise."""
        if not self._md_schema:
            raise ValueError("Schema not set - can't set data")
        if not isinstance(data, self._md_schema):
            raise TypeError(f"Supplied data {data} not of type {self._md_schema}")
        for form_item in self.enumerate_form_widgets():
            form_item.widget.setValue(getattr(data, form_item.label.property("_model_field_name")))

    def _form_item_specs(self):
        return [
            FormItemSpec(
                name=name, info=info, item_type=info.annotation, pretty_display=self._pretty_display
            )
            for name, info in self._md_schema.model_fields.items()
        ]

    def update_items_from_schema(self):
        self._items = self._form_item_specs()

    def populate(self):
        self.update_items_from_schema()
        self._field_errors = {}
        super().populate()

    def _add_griditem(self, item: FormItemSpec, row: int):
        # every field takes two grid rows: the field itself and its (hidden) error line below
        super()._add_griditem(item, 2 * row)
        error = QLabel(parent=self._form_grid)
        error.setWordWrap(True)
        error.setVisible(False)
        self._form_grid.layout().addWidget(error, 2 * row + 1, 1)
        self._field_errors[item.name] = error

    def get_form_data(self):
        """Get the entered metadata as a dict."""
        return self._dict_from_grid()

    def _set_validity(self, valid: bool, message: str, details: str = ""):
        """Show a short validation result under the form.

        Args:
            valid (bool): whether the form data is valid.
            message (str): the one-line summary.
            details (str): readable list of the problems, used as tooltip.
        """
        self._validity_state = valid
        self._validity_summary = message
        accents = get_accent_colors()
        color = accents.success if valid else accents.emergency
        self._validity_message.setStyleSheet(f"color: {color.name()};")
        self._validity_message.setText(message)
        self._validity_message.setToolTip(details)

    def _show_field_errors(self, issues: list[ValidationIssue]):
        """Show each field's problem directly under its input; hide the lines of valid fields."""
        problems = {issue.field: issue.problem for issue in issues}
        color = get_accent_colors().emergency.name()
        for name, label in self._field_errors.items():
            problem = problems.get(name)
            label.setVisible(problem is not None)
            if problem is not None:
                label.setStyleSheet(f"color: {color};")
                label.setText(problem)

    def _describe_errors(self, error: ValidationError) -> list[ValidationIssue]:
        """One issue per invalid top-level field, without pydantic's error codes and links.

        Errors inside a field (list entries, dict keys, nested models) keep their location, e.g.
        ``[1]: Input should be a valid integer``; every failing entry of a field is listed."""
        problems: dict[str, list[str]] = {}
        entered: dict[str, str] = {}
        for err in error.errors():
            loc = tuple(err["loc"])
            name = str(loc[0]) if loc else "form"
            path = self._error_path(name, loc[1:])
            value = err.get("input")
            if err["type"] == "missing" or value is None:
                message = "Required - please fill in"
            else:
                message = err["msg"]
            line = f"{path}: {message}" if path else message
            lines = problems.setdefault(name, [])
            if line not in lines:
                lines.append(line)
            if name not in entered:
                if value is None:
                    entered[name] = "empty"
                else:
                    entered[name] = repr(value) if isinstance(value, str) else str(value)
        issues = []
        for name, lines in problems.items():
            field = self._md_schema.model_fields.get(name)
            title = field.title if field is not None and field.title else name
            issues.append(ValidationIssue(name, title, "\n".join(lines), entered[name]))
        return issues

    def _error_path(self, name: str, sub_loc: tuple) -> str:
        """Readable location inside a field, e.g. ``[1]``, ``key`` or ``inner[0].name``.

        For fields with several possible types (``int | float``), pydantic reports one error per
        type, tagged with the type name; that tag is not a location and is dropped."""
        field = self._md_schema.model_fields.get(name)
        annotation = field.annotation if field is not None else None
        if get_origin(annotation) in (Union, UnionType):
            members = [arg for arg in get_args(annotation) if arg is not NoneType]
            if len(members) > 1 and sub_loc and isinstance(sub_loc[0], str):
                sub_loc = sub_loc[1:]
        path = ""
        for part in sub_loc:
            path += f"[{part}]" if isinstance(part, int) else f".{part}"
        return path.lstrip(".")

    @staticmethod
    def _summarize_issues(issues: list[ValidationIssue]) -> str:
        if len(issues) == 1:
            return f"Invalid field: {issues[0].title}"
        return f"{len(issues)} invalid fields: {', '.join(issue.title for issue in issues)}"

    def _summarize_errors(self, error: ValidationError) -> str:
        """One short line naming the invalid fields, so the form keeps its size."""
        return self._summarize_issues(self._describe_errors(error))

    def validate_form(self, *_) -> bool:
        """validate the currently entered metadata against the pydantic schema.
        If successful, returns on metadata_emitted and returns true.
        Otherwise, emits on form_data_cleared and returns false."""
        try:
            metadata_dict = self.get_form_data()
            self._md_schema.model_validate(metadata_dict)
            self._validity_issues = []
            self._show_field_errors([])
            self._set_validity(True, "No errors!")
            self.form_data_updated.emit(metadata_dict)
            self.validity_proc.emit(True)
            return True
        except ValidationError as e:
            self._validity_issues = self._describe_errors(e)
            self._show_field_errors(self._validity_issues)
            details = "\n".join(
                f"{issue.title}: {line}"
                for issue in self._validity_issues
                for line in issue.problem.split("\n")
            )
            self._set_validity(False, self._summarize_issues(self._validity_issues), details)
            self.form_data_cleared.emit(None)
            self.validity_proc.emit(False)
            return False


class PydanticModelFormItem(DynamicFormItem):
    def __init__(
        self, parent: QWidget | None = None, *, spec: FormItemSpec, model: type[BaseModel]
    ) -> None:
        self._data_model = model

        super().__init__(parent=parent, spec=spec)
        self._main_widget.form_data_updated.connect(self._value_changed)

    def _add_main_widget(self) -> None:

        self._main_widget = PydanticModelForm(data_model=self._data_model)
        self._layout.addWidget(self._main_widget)

    def getValue(self):
        return self._main_widget.get_form_data()

    def setValue(self, value: dict):
        self._main_widget.set_data(self._data_model.model_validate(value))
