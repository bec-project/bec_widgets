from decimal import Decimal

import pytest
from pydantic import BaseModel, Field

from bec_widgets.utils.forms_from_types.forms import PydanticModelForm
from bec_widgets.utils.forms_from_types.items import (
    BoolMetadataField,
    DynamicFormItem,
    FloatDecimalMetadataField,
    IntMetadataField,
    StrMetadataField,
)

# pylint: disable=no-member
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access


class ExampleSchema(BaseModel):
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
    decimal_dp_limits_nodefault: Decimal = Field(decimal_places=2, gt=1, le=34.5)


TEST_DICT = {
    "sample_name": "test name",
    "str_optional": None,
    "str_required": "something",
    "bool_optional": None,
    "bool_required_default": True,
    "bool_required_nodefault": False,
    "int_default": 21,
    "int_nodefault_optional": -10,
    "float_nodefault": 123.456,
    "decimal_dp_limits_nodefault": 34.5,
}


@pytest.fixture
def example_md():
    return ExampleSchema.model_validate(TEST_DICT)


@pytest.fixture
def model_widget():
    widget = PydanticModelForm(data_model=ExampleSchema)
    widget.populate()
    yield widget
    widget._clear_grid()
    widget.deleteLater()


def test_widget_dict(model_widget: PydanticModelForm):
    assert isinstance(model_widget.widget_dict["str_optional"], StrMetadataField)
    assert isinstance(model_widget.widget_dict["float_nodefault"], FloatDecimalMetadataField)
    assert isinstance(model_widget.widget_dict["int_default"], IntMetadataField)


def test_widget_set_data(model_widget: PydanticModelForm):
    data = ExampleSchema.model_validate(TEST_DICT)
    model_widget.set_data(data)
    for key in [
        "str_optional",
        "str_required",
        "bool_optional",
        "bool_required_default",
        "bool_required_nodefault",
        "int_default",
        "int_nodefault_optional",
        "float_nodefault",
        "decimal_dp_limits_nodefault",
    ]:
        assert model_widget.widget_dict[key].getValue() == TEST_DICT[key]
