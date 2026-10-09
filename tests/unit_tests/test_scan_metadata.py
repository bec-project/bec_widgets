from decimal import Decimal

import pytest
from bec_lib.metadata_schema import BasicScanMetadata
from pydantic import Field
from pydantic.types import Json
from qtpy.QtCore import QItemSelectionModel, QPoint, Qt
from qtpy.QtWidgets import QCheckBox, QDoubleSpinBox, QLineEdit, QSpinBox

from bec_widgets.tests.utils import create_widget
from bec_widgets.utils.forms_from_types.entry_list_editor import EntryListEditor
from bec_widgets.utils.forms_from_types.pydantic_widget_form import OptionalValueWidget
from bec_widgets.widgets.editors.dict_backed_table import DictBackedTable
from bec_widgets.widgets.editors.scan_metadata.scan_metadata import ScanMetadata
from bec_widgets.widgets.utility.spinbox.decimal_spinbox import BECSpinBox

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


TEST_VALUES = {
    "sample_name": "test name",
    "str_optional": None,
    "str_required": "something",
    "bool_optional": None,
    "bool_required_nodefault": False,
    "int_default": 21,
    "int_nodefault_optional": -10,
    "float_nodefault": 0.1,
    "decimal_dp_limits_nodefault": 456.789,
    "dict_default": {"test_dict": "values"},
    "unsupported_class": '["set", "item"]',
}

TEST_DICT = {
    "scan_name": "example_scan",
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
def schema_registry(monkeypatch):
    monkeypatch.setattr(
        "bec_lib.metadata_schema._get_metadata_schema_registry",
        lambda: {"example_scan": ExampleSchema},
    )


@pytest.fixture
def metadata_widget(qtbot, schema_registry):
    widget = create_widget(
        qtbot,
        ScanMetadata,
        scan_name="example_scan",
        initial_extras=[["extra_field", "extra_data"]],
    )
    yield widget


def test_fields_use_matching_widgets(metadata_widget: ScanMetadata):
    widgets = metadata_widget.form.widgets
    for name in ["scan_name", "comment", "sample_name", "str_required", "unsupported_class"]:
        assert type(widgets[name]) is QLineEdit, name
    assert isinstance(metadata_widget.form.input_widget("str_optional"), QLineEdit)
    assert metadata_widget.form.input_widget("str_optional").maxLength() == 23
    assert isinstance(widgets["bool_optional"], OptionalValueWidget)
    assert isinstance(widgets["bool_required_default"], QCheckBox)
    assert isinstance(widgets["bool_required_nodefault"], QCheckBox)
    assert isinstance(widgets["int_default"], QSpinBox)
    assert isinstance(widgets["int_nodefault_optional"], OptionalValueWidget)
    assert isinstance(widgets["float_nodefault"], BECSpinBox)
    decimal = widgets["decimal_dp_limits_nodefault"]
    assert type(decimal) is QDoubleSpinBox
    assert decimal.decimals() == 2
    assert (decimal.minimum(), decimal.maximum()) == (pytest.approx(1.01), pytest.approx(34.5))
    assert isinstance(widgets["dict_default"], EntryListEditor)


def test_required_fields_are_marked(metadata_widget: ScanMetadata):
    form = metadata_widget.form
    assert form.layout().labelForField(form.field_widget("str_required")).text() == (
        "Str required *"
    )
    assert form.layout().labelForField(form.field_widget("comment")).text() == "Comment"


def test_form_data_includes_extras_and_scan_name(metadata_widget: ScanMetadata, qtbot):
    metadata_widget.set_field_values(TEST_VALUES)
    received = []
    metadata_widget.form_data_updated.connect(received.append)

    assert metadata_widget.validate_form()
    # the emitted metadata is validated, so the Json field arrives parsed
    assert received[-1] == TEST_DICT | {
        "unsupported_class": ["set", "item"],
        "extra_field": "extra_data",
    }
    # Decimals are sent as floats, like the other numbers
    assert isinstance(received[-1]["decimal_dp_limits_nodefault"], float)
    assert metadata_widget.get_form_data()["extra_field"] == "extra_data"


def test_validation_messages(metadata_widget: ScanMetadata):
    metadata_widget.set_field_values(TEST_VALUES | {"str_required": ""})
    cleared = []
    metadata_widget.form_data_cleared.connect(cleared.append)

    assert not metadata_widget.validate_form()
    assert cleared == [None]
    assert metadata_widget.validation_messages() == ["Str required: Field required"]
    assert metadata_widget._summary.isVisibleTo(metadata_widget)
    assert "Str required: Field required" in metadata_widget._summary.text.text()
    assert metadata_widget.form.input_widget("str_required").property("state") == "error"

    metadata_widget.set_field_values({"str_required": "something"})
    assert metadata_widget.validate_form()
    assert not metadata_widget._summary.isVisibleTo(metadata_widget)
    assert metadata_widget.form.input_widget("str_required").property("state") == ""


def test_numbers_clipped_to_limits(metadata_widget: ScanMetadata):
    metadata_widget.set_field_values(TEST_VALUES | {"decimal_dp_limits_nodefault": -56})
    assert metadata_widget.get_form_data()["decimal_dp_limits_nodefault"] == pytest.approx(1.01)
    assert metadata_widget.validate_form()


def test_editing_a_field_revalidates(metadata_widget: ScanMetadata):
    metadata_widget.set_field_values(TEST_VALUES)
    received = []
    metadata_widget.validity_proc.connect(received.append)
    metadata_widget.form.input_widget("str_required").setText("x")
    assert received[-1] is True
    metadata_widget.form.input_widget("str_required").setText("")
    assert received[-1] is False


@pytest.mark.parametrize(
    "key, message",
    [
        ("sample_name", "'sample_name' is already a field of this form."),
        ("extra_field", "Key 'extra_field' is used more than once."),
        ("", "Enter a key for the value."),
    ],
)
def test_invalid_additional_metadata_keys(metadata_widget: ScanMetadata, key, message):
    metadata_widget.set_field_values(TEST_VALUES)
    editor = metadata_widget.form.extra_fields_section.editor
    row = editor.add_entry(key, "value")

    assert not metadata_widget.validate_form()
    assert metadata_widget.validation_messages() == [f"Additional metadata: {message}"]
    assert row.key_edit.property("state") == "error"

    row.key_edit.setText("unique_key")
    assert metadata_widget.validate_form()
    assert row.key_edit.property("state") == ""
    assert metadata_widget.get_form_data()["unique_key"] == "value"


def test_blank_additional_metadata_rows_are_ignored(metadata_widget: ScanMetadata):
    metadata_widget.set_field_values(TEST_VALUES)
    metadata_widget.form.extra_fields_section.editor.add_button.click()

    assert metadata_widget.validate_form()
    assert "" not in metadata_widget.get_form_data()


def test_switching_scans_keeps_shared_values_and_extras(metadata_widget: ScanMetadata):
    metadata_widget.set_field_values(TEST_VALUES | {"comment": "keep me"})
    metadata_widget.update_with_new_scan("other_scan")

    assert metadata_widget._md_schema is BasicScanMetadata
    assert set(metadata_widget.form.widgets) == {"scan_name", "comment", "sample_name"}
    assert metadata_widget.form.input_widget("scan_name").placeholderText() == "other_scan"
    assert metadata_widget.get_form_data() == {
        "scan_name": "other_scan",
        "comment": "keep me",
        "sample_name": "test name",
        "extra_field": "extra_data",
    }


def test_typed_scan_name_is_kept(metadata_widget: ScanMetadata):
    metadata_widget.set_field_values({"scan_name": "my alignment"})
    assert metadata_widget.get_form_data()["scan_name"] == "my alignment"


def test_hide_optional_metadata(metadata_widget: ScanMetadata):
    section = metadata_widget.form.extra_fields_section
    assert section.isVisibleTo(metadata_widget)
    metadata_widget.hide_optional_metadata = True
    assert metadata_widget.hide_optional_metadata
    assert not section.isVisibleTo(metadata_widget)


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
