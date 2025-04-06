from __future__ import annotations

from decimal import Decimal
from types import NoneType
from typing import TYPE_CHECKING

from bec_lib.logger import bec_logger
from bec_lib.metadata_schema import get_metadata_schema_for_scan
from bec_qthemes import material_icon
from pydantic import Field, ValidationError
from qtpy.QtCore import Signal  # type: ignore
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.compact_popup import CompactPopupWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.expandable_frame import ExpandableGroupFrame
from bec_widgets.widgets.editors.scan_metadata._metadata_widgets import widget_from_type
from bec_widgets.widgets.editors.scan_metadata.additional_metadata_table import (
    AdditionalMetadataTable,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

logger = bec_logger.logger


class ScanMetadata(BECWidget, QWidget):
    """Dynamically generates a form for inclusion of metadata for a scan. Uses the
    metadata schema registry supplied in the plugin repo to find pydantic models
    associated with the scan type. Sets limits for numerical values if specified."""

    metadata_updated = Signal(dict)
    metadata_cleared = Signal(NoneType)

    def __init__(
        self,
        parent=None,
        client=None,
        scan_name: str | None = None,
        initial_extras: list[list[str]] | None = None,
        **kwargs,
    ):
        QWidget.__init__(self, parent=parent)
        BECWidget.__init__(self, client=client, **kwargs)

        self.set_schema(scan_name)

        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        self._required_md_box = ExpandableGroupFrame("Scan schema metadata")
        self._layout.addWidget(self._required_md_box)
        self._required_md_box_layout = QHBoxLayout()
        self._required_md_box.set_layout(self._required_md_box_layout)

        self._md_grid = QWidget()
        self._required_md_box_layout.addWidget(self._md_grid)
        self._grid_container = QVBoxLayout()
        self._md_grid.setLayout(self._grid_container)
        self._new_grid_layout()
        self._grid_container.addLayout(self._md_grid_layout)

        self._additional_md_box = ExpandableGroupFrame("Additional metadata", expanded=False)
        self._layout.addWidget(self._additional_md_box)
        self._additional_md_box_layout = QHBoxLayout()
        self._additional_md_box.set_layout(self._additional_md_box_layout)

        self._additional_metadata = AdditionalMetadataTable(initial_extras or [])
        self._additional_md_box_layout.addWidget(self._additional_metadata)

        self._validity = CompactPopupWidget()
        self._validity.compact_view = True  # type: ignore
        self._validity.label = "Metadata validity"  # type: ignore
        self._validity.compact_show_popup.setIcon(
            material_icon(icon_name="info", size=(10, 10), convert_to_pixmap=False)
        )
        self._validity_message = QLabel("Not yet validated")
        self._validity.addWidget(self._validity_message)
        self._layout.addWidget(self._validity)

        self.populate()

    @SafeSlot(str)
    def update_with_new_scan(self, scan_name: str):
        self.set_schema(scan_name)
        self.populate()
        self.validate_form()

    def validate_form(self, *_) -> bool:
        """validate the currently entered metadata against the pydantic schema.
        If successful, returns on metadata_emitted and returns true.
        Otherwise, emits on metadata_cleared and returns false."""
        try:
            metadata_dict = self.get_full_model_dict()
            self._md_schema.model_validate(metadata_dict)
            self._validity.set_global_state("success")
            self._validity_message.setText("No errors!")
            self.metadata_updated.emit(metadata_dict)
        except ValidationError as e:
            self._validity.set_global_state("emergency")
            self._validity_message.setText(str(e))
            self.metadata_cleared.emit(None)

    def get_full_model_dict(self):
        """Get the entered metadata as a dict"""
        return self._additional_metadata.dump_dict() | self._dict_from_grid()

    def set_schema(self, scan_name: str | None = None):
        self._scan_name = scan_name or ""
        self._md_schema = get_metadata_schema_for_scan(self._scan_name)

    def populate(self):
        self._clear_grid()
        self._populate()

    def _populate(self):
        self._additional_metadata.update_disallowed_keys(list(self._md_schema.model_fields.keys()))
        for i, (field_name, info) in enumerate(self._md_schema.model_fields.items()):
            self._add_griditem(field_name, info, i)

    def _add_griditem(self, field_name: str, info: FieldInfo, row: int):
        grid = self._md_grid_layout
        label = QLabel(info.title or field_name)
        label.setProperty("_model_field_name", field_name)
        label.setToolTip(info.description or field_name)
        grid.addWidget(label, row, 0)
        widget = widget_from_type(info.annotation)(info)
        widget.valueChanged.connect(self.validate_form)
        grid.addWidget(widget, row, 1)

    def _dict_from_grid(self) -> dict[str, str | int | float | Decimal | bool]:
        grid = self._md_grid_layout
        return {
            grid.itemAtPosition(i, 0).widget().property("_model_field_name"): grid.itemAtPosition(i, 1).widget().getValue()  # type: ignore # we only add 'MetadataWidget's here
            for i in range(grid.rowCount())
        }

    def _clear_grid(self):
        while self._md_grid_layout.count():
            item = self._md_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._md_grid_layout.deleteLater()
        self._new_grid_layout()
        self._grid_container.addLayout(self._md_grid_layout)
        self._md_grid.adjustSize()
        self.adjustSize()

    def _new_grid_layout(self):
        self._md_grid_layout = QGridLayout()
        self._md_grid_layout.setContentsMargins(0, 0, 0, 0)
        self._md_grid_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

    @SafeProperty(bool)
    def hide_optional_metadata(self):  # type: ignore
        """Property to hide the optional metadata table."""
        return not self._additional_md_box.isVisible()

    @hide_optional_metadata.setter
    def hide_optional_metadata(self, hide: bool):
        """Setter for the hide_optional_metadata property.

        Args:
            hide(bool): Hide or show the optional metadata table.
        """
        self._additional_md_box.setVisible(not hide)


if __name__ == "__main__":  # pragma: no cover
    from unittest.mock import patch

    from bec_lib.metadata_schema import BasicScanMetadata

    from bec_widgets.utils.colors import set_theme

    class ExampleSchema1(BasicScanMetadata):
        abc: int = Field(gt=0, lt=2000, description="Heating temperature abc", title="A B C")
        foo: str = Field(max_length=12, description="Sample database code", default="DEF123")
        xyz: Decimal = Field(decimal_places=4)
        baz: bool

    class ExampleSchema2(BasicScanMetadata):
        checkbox_up_top: bool
        checkbox_again: bool = Field(
            title="Checkbox Again", description="this one defaults to True", default=True
        )
        different_items: int | None = Field(
            None, description="This is just one different item...", gt=-100, lt=0
        )
        length_limited_string: str = Field(max_length=32)
        float_with_2dp: Decimal = Field(decimal_places=2)

    class ExampleSchema3(BasicScanMetadata):
        optional_with_regex: str | None = Field(None, pattern=r"^\d+-\d+$")

    with patch(
        "bec_lib.metadata_schema._get_metadata_schema_registry",
        lambda: {"scan1": ExampleSchema1, "scan2": ExampleSchema2, "scan3": ExampleSchema3},
    ):

        app = QApplication([])
        w = QWidget()
        selection = QComboBox()
        selection.addItems(["grid_scan", "scan1", "scan2", "scan3"])

        layout = QVBoxLayout()
        w.setLayout(layout)

        scan_metadata = ScanMetadata(
            scan_name="grid_scan",
            initial_extras=[["key1", "value1"], ["key2", "value2"], ["key3", "value3"]],
        )
        selection.currentTextChanged.connect(scan_metadata.update_with_new_scan)

        layout.addWidget(selection)
        layout.addWidget(scan_metadata)

        set_theme("dark")
        window = w
        window.show()
        app.exec()
