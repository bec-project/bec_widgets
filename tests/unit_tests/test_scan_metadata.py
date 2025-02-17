from decimal import Decimal
from typing import Annotated

import pytest
from bec_lib.metadata_schema import BasicScanMetadata
from pydantic import Field
from pydantic.types import Json
from qtpy.QtCore import QItemSelectionModel, QPoint, Qt

from bec_widgets.widgets.editors.scan_metadata import ScanMetadata
from bec_widgets.widgets.editors.scan_metadata._metadata_widgets import (
    BoolMetadataField,
    FloatDecimalMetadataField,
    IntMetadataField,
    MetadataWidget,
    StrMetadataField,
)
from bec_widgets.widgets.editors.scan_metadata.additional_metadata_table import (
    AdditionalMetadataTable,
)


class ExampleSchema(BasicScanMetadata):
    str_optional: str | None = Field(
        None, title="Optional string", description="an optional string", max_length=23
    )
    str_required: str
    bool_optional: bool | None = Field(None)
    bool_required_default: bool = Field(True)
    bool_required_nodefault: bool = Field()
    int_default: int = Field(123)
    int_nodefault_optional: int | None = Field(lt=-1, ge=-44)
    float_nodefault: float
    decimal_dp_limits_nodefault: Decimal = Field(Decimal(1.23), decimal_places=2, gt=1, le=34.5)
    unsupported_class: Json = Field(default_factory=dict)


pytest.approx(0.1)

TEST_DICT = {
    "sample_name": "test name",
    "str_optional": None,
    "str_required": "something",
    "bool_optional": None,
    "bool_required_default": True,
    "bool_required_nodefault": False,
    "int_default": 21,
    "int_nodefault_optional": -10,
    "float_nodefault": pytest.approx(0.1),
    "decimal_dp_limits_nodefault": pytest.approx(34),
    "unsupported_class": '{"key": "value"}',
}


@pytest.fixture
def example_md():
    return ExampleSchema.model_validate(TEST_DICT)


@pytest.fixture
def empty_metadata_widget():
    widget = ScanMetadata()
    widget._additional_metadata._table_model._data = [["extra_field", "extra_data"]]
    yield widget
    widget._clear_grid()
    widget.deleteLater()


@pytest.fixture
def metadata_widget(empty_metadata_widget: ScanMetadata):
    widget = empty_metadata_widget
    widget._md_schema = ExampleSchema
    widget.populate()

    sample_name = widget._md_grid_layout.itemAtPosition(0, 1).widget()
    str_optional = widget._md_grid_layout.itemAtPosition(1, 1).widget()
    str_required = widget._md_grid_layout.itemAtPosition(2, 1).widget()
    bool_optional = widget._md_grid_layout.itemAtPosition(3, 1).widget()
    bool_required_default = widget._md_grid_layout.itemAtPosition(4, 1).widget()
    bool_required_nodefault = widget._md_grid_layout.itemAtPosition(5, 1).widget()
    int_default = widget._md_grid_layout.itemAtPosition(6, 1).widget()
    int_nodefault_optional = widget._md_grid_layout.itemAtPosition(7, 1).widget()
    float_nodefault = widget._md_grid_layout.itemAtPosition(8, 1).widget()
    decimal_dp_limits_nodefault = widget._md_grid_layout.itemAtPosition(9, 1).widget()
    unsupported_class = widget._md_grid_layout.itemAtPosition(10, 1).widget()

    yield (
        widget,
        {
            "sample_name": sample_name,
            "str_optional": str_optional,
            "str_required": str_required,
            "bool_optional": bool_optional,
            "bool_required_default": bool_required_default,
            "bool_required_nodefault": bool_required_nodefault,
            "int_default": int_default,
            "int_nodefault_optional": int_nodefault_optional,
            "float_nodefault": float_nodefault,
            "decimal_dp_limits_nodefault": decimal_dp_limits_nodefault,
            "unsupported_class": unsupported_class,
        },
    )


def fill_commponents(components: dict[str, MetadataWidget]):
    components["sample_name"].setValue("test name")
    components["str_optional"].setValue(None)
    components["str_required"].setValue("something")
    components["bool_optional"].setValue(None)
    components["bool_required_nodefault"].setValue(False)
    components["int_default"].setValue(21)
    components["int_nodefault_optional"].setValue(-10)
    components["float_nodefault"].setValue(0.1)
    components["decimal_dp_limits_nodefault"].setValue(456.789)
    components["unsupported_class"].setValue(r'{"key": "value"}')


def test_griditems_are_correct_class(
    metadata_widget: tuple[ScanMetadata, dict[str, MetadataWidget]]
):
    _, components = metadata_widget
    assert isinstance(components["sample_name"], StrMetadataField)
    assert isinstance(components["str_optional"], StrMetadataField)
    assert isinstance(components["str_required"], StrMetadataField)
    assert isinstance(components["bool_optional"], BoolMetadataField)
    assert isinstance(components["bool_required_default"], BoolMetadataField)
    assert isinstance(components["bool_required_nodefault"], BoolMetadataField)
    assert isinstance(components["int_default"], IntMetadataField)
    assert isinstance(components["int_nodefault_optional"], IntMetadataField)
    assert isinstance(components["float_nodefault"], FloatDecimalMetadataField)
    assert isinstance(components["decimal_dp_limits_nodefault"], FloatDecimalMetadataField)
    assert isinstance(components["unsupported_class"], StrMetadataField)


def test_grid_to_dict(metadata_widget: tuple[ScanMetadata, dict[str, MetadataWidget]]):
    widget, components = metadata_widget = metadata_widget
    fill_commponents(components)

    assert widget._dict_from_grid() == TEST_DICT
    assert widget.get_full_model_dict() == TEST_DICT | {"extra_field": "extra_data"}


def test_validation(metadata_widget: tuple[ScanMetadata, dict[str, MetadataWidget]]):
    widget, components = metadata_widget = metadata_widget
    assert widget._validity.compact_status.styleSheet().startswith(
        widget._validity.compact_status.default_led[:114]
    )

    fill_commponents(components)
    widget.validate_form()
    assert widget._validity_message.text() == "No errors!"

    components["bool_required_nodefault"]._main_widget.clear()
    widget.validate_form()
    assert "Input should be a valid boolean" in widget._validity_message.text()
    components["bool_required_nodefault"].setValue(True)

    components["float_nodefault"]._main_widget.clear()
    widget.validate_form()
    assert "Input should be a valid number" in widget._validity_message.text()
    components["float_nodefault"].setValue(True)


def test_numbers_clipped_to_limits(metadata_widget: tuple[ScanMetadata, dict[str, MetadataWidget]]):
    widget, components = metadata_widget = metadata_widget
    fill_commponents(components)

    components["decimal_dp_limits_nodefault"].setValue(-56)
    widget.validate_form()
    assert components["decimal_dp_limits_nodefault"].getValue() == pytest.approx(2)
    assert widget._validity_message.text() == "No errors!"


@pytest.fixture
def table():
    table = AdditionalMetadataTable([["key1", "value1"], ["key2", "value2"], ["key3", "value3"]])
    yield table
    table._table_model.deleteLater()
    table._table_view.deleteLater()
    table.deleteLater()


def test_additional_metadata_table_add_row(table: AdditionalMetadataTable):
    assert table._table_model.rowCount() == 3
    table._add_button.click()
    assert table._table_model.rowCount() == 4


def test_additional_metadata_table_delete_row(table: AdditionalMetadataTable):
    assert table._table_model.rowCount() == 3
    m = table._table_view.selectionModel()
    item = table._table_view.indexAt(QPoint(0, 0)).siblingAtRow(1)
    m.select(item, QItemSelectionModel.SelectionFlag.Select)
    table.delete_selected_rows()
    assert table._table_model.rowCount() == 2
    assert list(table.dump_dict().keys()) == ["key1", "key3"]


def test_additional_metadata_allows_changes(table: AdditionalMetadataTable):
    assert table._table_model.rowCount() == 3
    assert list(table.dump_dict().keys()) == ["key1", "key2", "key3"]
    table._table_model.setData(table._table_model.index(1, 0), "key4", Qt.ItemDataRole.EditRole)
    assert list(table.dump_dict().keys()) == ["key1", "key4", "key3"]


def test_additional_metadata_doesnt_allow_dupes(table: AdditionalMetadataTable):
    assert table._table_model.rowCount() == 3
    assert list(table.dump_dict().keys()) == ["key1", "key2", "key3"]
    table._table_model.setData(table._table_model.index(1, 0), "key1", Qt.ItemDataRole.EditRole)
    assert list(table.dump_dict().keys()) == ["key1", "key2", "key3"]
