from __future__ import annotations

from types import NoneType
from typing import NamedTuple

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from pydantic import BaseModel, ValidationError
from qtpy.QtCore import Signal  # type: ignore
from qtpy.QtWidgets import QApplication, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.compact_popup import CompactPopupWidget
from bec_widgets.utils.error_popups import SafeProperty
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
        self._form_grid = QWidget(parent=self._form_grid_container)
        self._form_grid.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self._layout.addWidget(self._form_grid_container)
        self._form_grid_container.setLayout(QVBoxLayout())
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
        label = QLabel(item.name)
        label.setProperty("_model_field_name", item.name)
        label.setToolTip(item.info.description or item.name)
        grid.addWidget(label, row, 0)
        widget = self._widget_from_type(item, self._widget_types)(parent=self, spec=item)
        widget.valueChanged.connect(self.value_changed)
        widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        grid.addWidget(widget, row, 1)

    def enumerate_form_widgets(self):
        """Return a generator over the rows of the form, with the row number, the label widget (to
        which the field name is attached as a property "_model_field_name"), and the entry widget"""
        grid: QGridLayout = self._form_grid.layout()  # type: ignore
        for i in range(grid.rowCount() - 1):  # One extra row for stretch
            yield GridRow(i, grid.itemAtPosition(i, 0).widget(), grid.itemAtPosition(i, 1).widget())

    def _dict_from_grid(self) -> dict[str, DynamicFormItemType]:
        return {
            row.label.property("_model_field_name"): row.widget.getValue()
            for row in self.enumerate_form_widgets()
        }

    def _clear_grid(self):
        if (old_layout := self._form_grid.layout()) is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            old_layout.deleteLater()
            self._form_grid.deleteLater()
        self._form_grid = QWidget()
        self._form_grid.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
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
    metadata_updated = Signal(dict)
    metadata_cleared = Signal(NoneType)

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
        super().__init__(
            parent=parent,
            form_item_specs=self._form_item_specs(),
            enabled=enabled,
            client=client,
            **kwargs,
        )

        self._validity = CompactPopupWidget()
        self._validity.compact_view = True  # type: ignore
        self._validity.label = "Metadata validity"  # type: ignore
        self._validity.compact_show_popup.setIcon(
            material_icon(icon_name="info", size=(10, 10), convert_to_pixmap=False)
        )
        self._validity_message = QLabel("Not yet validated")
        self._validity.addWidget(self._validity_message)
        self._layout.addWidget(self._validity)
        self.value_changed.connect(self.validate_form)

        self._connect_to_theme_change()

    def set_pretty_display_theme(self, theme: str = "dark"):
        if self._pretty_display:
            self.setStyleSheet(styles.pretty_display_theme(theme))

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
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
        super().populate()

    def get_form_data(self):
        """Get the entered metadata as a dict."""
        return self._dict_from_grid()

    def validate_form(self, *_) -> bool:
        """validate the currently entered metadata against the pydantic schema.
        If successful, returns on metadata_emitted and returns true.
        Otherwise, emits on metadata_cleared and returns false."""
        try:
            metadata_dict = self.get_form_data()
            self._md_schema.model_validate(metadata_dict)
            self._validity.set_global_state("success")
            self._validity_message.setText("No errors!")
            self.metadata_updated.emit(metadata_dict)
            return True
        except ValidationError as e:
            self._validity.set_global_state("emergency")
            self._validity_message.setText(str(e))
            self.metadata_cleared.emit(None)
            return False
