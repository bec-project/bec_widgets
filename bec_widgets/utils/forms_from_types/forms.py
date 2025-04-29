from __future__ import annotations

from decimal import Decimal
from types import NoneType

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from pydantic import BaseModel, ValidationError
from qtpy.QtCore import Signal  # type: ignore
from qtpy.QtWidgets import QGridLayout, QLabel, QLayout, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.compact_popup import CompactPopupWidget
from bec_widgets.utils.forms_from_types.items import FormItemSpec, widget_from_type

logger = bec_logger.logger


class TypedForm(BECWidget, QWidget):
    PLUGIN = True
    ICON_NAME = "list_alt"

    value_changed = Signal()

    RPC = False

    def __init__(
        self,
        parent=None,
        items: list[tuple[str, type]] | None = None,
        form_item_specs: list[FormItemSpec] | None = None,
        client=None,
        **kwargs,
    ):
        """Widget with a list of form items based on a list of types.

        Args:
            items (list[tuple[str, type]]): list of tuples of a name for the field and its type.
                                            Should be a type supported by the logic in items.py
            form_item_specs (list[FormItemSpec]): list of form item specs, equivalent to items.
                                                  only one of items or form_item_specs should be
                                                  supplied.

        """
        if (items is not None and form_item_specs is not None) or (
            items is None and form_item_specs is None
        ):
            raise ValueError("Must specify one and only one of items and form_item_specs")
        super().__init__(parent=parent, client=client, **kwargs)
        self._items = (
            form_item_specs
            if form_item_specs is not None
            else [
                FormItemSpec(name=name, item_type=item_type)
                for name, item_type in items  # type: ignore
            ]
        )
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        self._form_grid_container = QWidget(parent=self)
        self._form_grid = QWidget(parent=self._form_grid_container)
        self._layout.addWidget(self._form_grid_container)
        self._form_grid_container.setLayout(QVBoxLayout())
        self._form_grid.setLayout(self._new_grid_layout())

        self.populate()

    def populate(self):
        self._clear_grid()
        for r, item in enumerate(self._items):
            self._add_griditem(item, r)

    def _add_griditem(self, item: FormItemSpec, row: int):
        grid = self._form_grid.layout()
        label = QLabel(item.name)
        label.setProperty("_model_field_name", item.name)
        label.setToolTip(item.info.description or item.name)
        grid.addWidget(label, row, 0)
        widget = widget_from_type(item.item_type)(parent=self, spec=item)
        widget.valueChanged.connect(self.value_changed)
        grid.addWidget(widget, row, 1)

    def _dict_from_grid(self) -> dict[str, str | int | float | Decimal | bool]:
        grid: QGridLayout = self._form_grid.layout()  # type: ignore
        return {
            grid.itemAtPosition(i, 0)
            .widget()
            .property("_model_field_name"): grid.itemAtPosition(i, 1)
            .widget()
            .getValue()  # type: ignore # we only add 'DynamicFormItem's here
            for i in range(grid.rowCount())
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

        self._form_grid.setLayout(self._new_grid_layout())
        self._form_grid_container.layout().addWidget(self._form_grid)

        self._form_grid.adjustSize()
        self._form_grid_container.adjustSize()
        self.adjustSize()

    def _new_grid_layout(self):
        new_grid = QGridLayout()
        new_grid.setContentsMargins(0, 0, 0, 0)
        new_grid.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        return new_grid


class PydanticModelForm(TypedForm):
    metadata_updated = Signal(dict)
    metadata_cleared = Signal(NoneType)

    def __init__(self, parent=None, metadata_model: type[BaseModel] = None, client=None, **kwargs):
        """
        A form generated from a pydantic model.

        Args:
            metadata_model (type[BaseModel]): the model class for which to generate a form.
        """
        self._md_schema = metadata_model
        super().__init__(parent=parent, form_item_specs=self._form_item_specs(), client=client)

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

    def set_schema(self, schema: type[BaseModel]):
        self._md_schema = schema
        self.populate()

    def _form_item_specs(self):
        return [
            FormItemSpec(name=name, info=info, item_type=info.annotation)
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
