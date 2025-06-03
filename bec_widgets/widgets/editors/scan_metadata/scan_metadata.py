from __future__ import annotations

from decimal import Decimal

from bec_lib.logger import bec_logger
from bec_lib.metadata_schema import get_metadata_schema_for_scan
from pydantic import Field
from qtpy.QtWidgets import QApplication, QComboBox, QHBoxLayout, QVBoxLayout, QWidget

from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.expandable_frame import ExpandableGroupFrame
from bec_widgets.utils.forms_from_types.forms import PydanticModelForm
from bec_widgets.widgets.editors.dict_backed_table import DictBackedTable

logger = bec_logger.logger


class ScanMetadata(PydanticModelForm):

    RPC = False

    def __init__(
        self,
        parent=None,
        client=None,
        scan_name: str | None = None,
        initial_extras: list[list[str]] | None = None,
        **kwargs,
    ):
        """Dynamically generates a form for inclusion of metadata for a scan. Uses the
        metadata schema registry supplied in the plugin repo to find pydantic models
        associated with the scan type. Sets limits for numerical values if specified.

        Args:
            scan_name (str): The scan for which to generate a metadata form
            Initial_extras (list[list[str]]): Initial data with which to populate the additional
                                              metadata table - inner lists should be key-value pairs
        """

        # self.populate() gets called in super().__init__
        # so make sure self._additional_metadata exists
        self._additional_md_box = ExpandableGroupFrame(
            parent, "Additional metadata", expanded=False
        )
        self._additional_md_box_layout = QHBoxLayout()
        self._additional_md_box.set_layout(self._additional_md_box_layout)

        self._additional_metadata = DictBackedTable(parent, initial_extras or [])
        self._scan_name = scan_name or ""
        self._md_schema = get_metadata_schema_for_scan(self._scan_name)
        self._additional_metadata.data_changed.connect(self.validate_form)

        super().__init__(parent=parent, data_model=self._md_schema, client=client, **kwargs)

        self._layout.addWidget(self._additional_md_box)
        self._additional_md_box_layout.addWidget(self._additional_metadata)

    @SafeSlot(str)
    def update_with_new_scan(self, scan_name: str):
        self.set_schema_from_scan(scan_name)
        self.validate_form()

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

    def get_form_data(self):
        """Get the entered metadata as a dict"""
        return self._additional_metadata.dump_dict() | self._dict_from_grid()

    def populate(self):
        self._additional_metadata.update_disallowed_keys(list(self._md_schema.model_fields.keys()))
        super().populate()

    def set_schema_from_scan(self, scan_name: str | None):
        self._scan_name = scan_name or ""
        self.set_schema(get_metadata_schema_for_scan(self._scan_name))
        self.populate()


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=redefined-outer-name
    # pylint: disable=protected-access
    # pylint: disable=disallowed-name

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
            parent=w,
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
