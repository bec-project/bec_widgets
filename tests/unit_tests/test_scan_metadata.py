from decimal import Decimal
from typing import Set

import pytest
from bec_lib.metadata_schema import BasicScanMetadata
from pydantic import BaseModel, Field, ValidationError
from pydantic.types import Json
from qtpy.QtCore import QItemSelectionModel, QPoint, Qt

from bec_widgets.utils.forms_from_types.items import (
    BoolFormItem,
    DictFormItem,
    DynamicFormItem,
    FloatDecimalFormItem,
    IntFormItem,
    StrFormItem,
)
from bec_widgets.widgets.editors.dict_backed_table import DictBackedTable
from bec_widgets.widgets.editors.scan_metadata.scan_metadata import ScanMetadata

# pylint: disable=no-member
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access


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
    dict_default: dict = Field(default_factory=dict)
    unsupported_class: Json = Field(default=set())


TEST_DICT = {
    "scan_name": "",
    "comment": "",
    "sample_name": "test name",
    "str_optional": None,
    "str_required": "something",
    "bool_optional": None,
    "bool_required_default": True,
    "bool_required_nodefault": False,
    "int_default": 21,
    "int_nodefault_optional": -10,
    "float_nodefault": pytest.approx(0.1),
    "decimal_dp_limits_nodefault": pytest.approx(34.5),
    "dict_default": {"test_dict": "values"},
    "unsupported_class": '["set", "item"]',
}


@pytest.fixture
def example_md():
    return ExampleSchema.model_validate(TEST_DICT)


@pytest.fixture
def empty_metadata_widget(qtbot):
    widget = ScanMetadata()
    widget._additional_metadata._table_model._data = [["extra_field", "extra_data"]]
    qtbot.addWidget(widget)
    yield widget


@pytest.fixture
def metadata_widget(empty_metadata_widget: ScanMetadata):
    widget = empty_metadata_widget
    widget._md_schema = ExampleSchema
    widget.populate()

    yield widget, widget.widget_dict


def fill_components(components: dict[str, DynamicFormItem]):
    components["sample_name"].setValue("test name")
    components["str_optional"].setValue(None)
    components["str_required"].setValue("something")
    components["bool_optional"].setValue(None)
    components["bool_required_nodefault"].setValue(False)
    components["int_default"].setValue(21)
    components["int_nodefault_optional"].setValue(-10)
    components["float_nodefault"].setValue(0.1)
    components["decimal_dp_limits_nodefault"].setValue(456.789)
    components["dict_default"].setValue({"test_dict": "values"})
    components["unsupported_class"].setValue(r'["set", "item"]')


def test_griditems_are_correct_class(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    _, components = metadata_widget
    assert isinstance(components["sample_name"], StrFormItem)
    assert isinstance(components["str_optional"], StrFormItem)
    assert isinstance(components["str_required"], StrFormItem)
    assert isinstance(components["bool_optional"], BoolFormItem)
    assert isinstance(components["bool_required_default"], BoolFormItem)
    assert isinstance(components["bool_required_nodefault"], BoolFormItem)
    assert isinstance(components["int_default"], IntFormItem)
    assert isinstance(components["int_nodefault_optional"], IntFormItem)
    assert isinstance(components["float_nodefault"], FloatDecimalFormItem)
    assert isinstance(components["decimal_dp_limits_nodefault"], FloatDecimalFormItem)
    assert isinstance(components["dict_default"], DictFormItem)
    assert isinstance(components["unsupported_class"], StrFormItem)


def test_grid_to_dict(metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]]):
    widget, components = metadata_widget = metadata_widget
    fill_components(components)

    assert widget._dict_from_grid() == TEST_DICT
    assert widget.get_form_data() == TEST_DICT | {"extra_field": "extra_data"}


def test_validation(metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]]):
    widget, components = metadata_widget = metadata_widget
    assert widget._validity_state is None
    assert widget._validity_message.text() == "Not yet validated"

    fill_components(components)
    widget.validate_form()
    assert widget._validity_state is True
    assert widget._validity_message.text() == "No errors!"

    components["bool_required_nodefault"]._main_widget.clear()
    widget.validate_form()
    assert widget._validity_state is False
    assert widget._validity_message.text() == "Invalid field: bool_required_nodefault"
    assert (
        widget._validity_message.toolTip() == "bool_required_nodefault: Required - please fill in"
    )
    components["bool_required_nodefault"].setValue(True)

    components["float_nodefault"]._main_widget.clear()
    widget.validate_form()
    assert widget._validity_message.text() == "Invalid field: float_nodefault"
    assert widget._validity_message.toolTip() == "float_nodefault: Required - please fill in"
    components["float_nodefault"].setValue(True)


def test_validation_summary_stays_short(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    widget, components = metadata_widget
    fill_components(components)
    components["bool_required_nodefault"]._main_widget.clear()
    components["float_nodefault"]._main_widget.clear()
    widget.validate_form()
    summary = widget._validity_summary
    assert summary == "2 invalid fields: bool_required_nodefault, float_nodefault"
    assert "\n" not in summary
    assert "errors.pydantic.dev" not in widget._validity_message.toolTip()


def test_validation_summary_uses_field_titles(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    widget, _ = metadata_widget
    with pytest.raises(ValidationError) as excinfo:
        ExampleSchema.model_validate(TEST_DICT | {"str_optional": "x" * 30})
    assert "Optional string" in widget._summarize_errors(excinfo.value)


def test_validation_summary_groups_union_and_list_errors(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    class UnionListSchema(BasicScanMetadata):
        u: int | float = Field(title="Union")
        lst: list[int] = Field(default_factory=list, title="List")

    widget, _ = metadata_widget
    with pytest.raises(ValidationError) as excinfo:
        UnionListSchema.model_validate({"u": "x", "lst": [1, "a", "b"]})
    widget._md_schema = UnionListSchema
    assert widget._summarize_errors(excinfo.value) == "2 invalid fields: Union, List"


def test_validation_issues_are_readable(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    class ReadableSchema(BasicScanMetadata):
        name: str = Field(max_length=3, title="Name")
        count: int = Field(title="Count")
        value: Decimal = Field(decimal_places=1, title="Value")

    widget, _ = metadata_widget
    widget._md_schema = ReadableSchema
    with pytest.raises(ValidationError) as excinfo:
        ReadableSchema.model_validate({"name": "toolong", "count": None, "value": Decimal("1.25")})
    issues = widget._describe_errors(excinfo.value)
    assert [(i.field, i.title, i.entered) for i in issues] == [
        ("name", "Name", "'toolong'"),
        ("count", "Count", "empty"),
        ("value", "Value", "1.25"),
    ]
    assert issues[0].problem == "String should have at most 3 characters"
    assert issues[1].problem == "Required - please fill in"


def test_validation_issues_keep_nested_locations(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    class Detector(BaseModel):
        prefix: str
        gain: int

    class NestedSchema(BasicScanMetadata):
        positions: list[int] = Field(default_factory=list, title="Positions")
        offsets: dict[str, int] = Field(default_factory=dict, title="Offsets")
        detector: Detector | None = Field(None, title="Detector")
        value: int | float = Field(0, title="Value")

    widget, _ = metadata_widget
    widget._md_schema = NestedSchema
    with pytest.raises(ValidationError) as excinfo:
        NestedSchema.model_validate(
            {
                "positions": [1, "a", 3, "b"],
                "offsets": {"x": 1, "y": "bad"},
                "detector": {"gain": "hi"},
                "value": "x",
            }
        )
    issues = {issue.field: issue for issue in widget._describe_errors(excinfo.value)}
    positions = issues["positions"].problem.split("\n")
    assert [line.split(":")[0] for line in positions] == ["[1]", "[3]"]
    assert issues["offsets"].problem.startswith("y: Input should be a valid integer")
    assert issues["detector"].problem.split("\n") == [
        "prefix: Required - please fill in",
        "gain: Input should be a valid integer, unable to parse string as an integer",
    ]
    # union members are tagged with their type name, which is not a location
    assert not any(
        line.startswith(("int:", "float:")) for line in issues["value"].problem.split("\n")
    )
    assert len(issues["value"].problem.split("\n")) == 2


def test_validation_errors_under_each_field(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    widget, components = metadata_widget
    errors = widget._field_errors
    assert set(errors) == set(components)
    assert not any(label.isVisibleTo(widget) for label in errors.values())

    fill_components(components)
    components["bool_required_nodefault"]._main_widget.clear()
    components["float_nodefault"]._main_widget.clear()
    widget.validate_form()
    shown = {name for name, label in errors.items() if label.isVisibleTo(widget)}
    assert shown == {"bool_required_nodefault", "float_nodefault"}
    assert errors["float_nodefault"].text() == "Required - please fill in"
    assert "errors.pydantic.dev" not in errors["float_nodefault"].text()

    components["bool_required_nodefault"].setValue(True)
    widget.validate_form()
    shown = {name for name, label in errors.items() if label.isVisibleTo(widget)}
    assert shown == {"float_nodefault"}

    components["float_nodefault"].setValue(1.5)
    widget.validate_form()
    assert not any(label.isVisibleTo(widget) for label in errors.values())


def test_validation_error_line_sits_under_its_field(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    widget, components = metadata_widget
    grid = widget._form_grid.layout()
    rows = list(widget.enumerate_form_widgets())
    assert len(rows) == len(components)  # error lines are not form rows
    for row in rows:
        name = row.label.property("_model_field_name")
        index = grid.indexOf(widget._field_errors[name])
        assert grid.getItemPosition(index)[:2] == (row.i + 1, 1)


def test_validation_error_lines_follow_schema_change(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    class OtherSchema(BasicScanMetadata):
        count: int = Field(title="Count")

    widget, _ = metadata_widget
    widget.set_schema(OtherSchema)
    assert set(widget._field_errors) == {"scan_name", "comment", "sample_name", "count"}
    widget.validate_form()
    assert widget._field_errors["count"].isVisibleTo(widget)
    assert widget._validity_message.text() == "Invalid field: Count"


def test_numbers_clipped_to_limits(
    metadata_widget: tuple[ScanMetadata, dict[str, DynamicFormItem]],
):
    widget, components = metadata_widget = metadata_widget
    fill_components(components)

    components["decimal_dp_limits_nodefault"].setValue(-56)
    assert components["decimal_dp_limits_nodefault"].getValue() == pytest.approx(1.01)
    widget.validate_form()
    assert widget._validity_message.text() == "No errors!"


@pytest.fixture
def table():
    table = DictBackedTable(
        initial_data=[["key1", "value1"], ["key2", "value2"], ["key3", "value3"]]
    )
    yield table
    table._table_model.deleteLater()
    table._table_view.deleteLater()
    table.deleteLater()


def test_additional_metadata_table_add_row(table: DictBackedTable):
    assert table._table_model.rowCount() == 3
    table._add_button.click()
    assert table._table_model.rowCount() == 4


def test_additional_metadata_table_delete_row(table: DictBackedTable):
    assert table._table_model.rowCount() == 3
    m = table._table_view.selectionModel()
    item = table._table_view.indexAt(QPoint(0, 0)).siblingAtRow(1)
    m.select(item, QItemSelectionModel.SelectionFlag.Select)
    table.delete_selected_rows()
    assert table._table_model.rowCount() == 2
    assert list(table.dump_dict().keys()) == ["key1", "key3"]


def test_additional_metadata_allows_changes(table: DictBackedTable):
    assert table._table_model.rowCount() == 3
    assert list(table.dump_dict().keys()) == ["key1", "key2", "key3"]
    table._table_model.setData(table._table_model.index(1, 0), "key4", Qt.ItemDataRole.EditRole)
    assert list(table.dump_dict().keys()) == ["key1", "key4", "key3"]


def test_additional_metadata_doesnt_allow_dupes(table: DictBackedTable):
    assert table._table_model.rowCount() == 3
    assert list(table.dump_dict().keys()) == ["key1", "key2", "key3"]
    table._table_model.setData(table._table_model.index(1, 0), "key1", Qt.ItemDataRole.EditRole)
    assert list(table.dump_dict().keys()) == ["key1", "key2", "key3"]
