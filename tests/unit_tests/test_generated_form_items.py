import sys
from typing import Any, Literal, get_args

import pytest
from pydantic import ValidationError
from pydantic.fields import FieldInfo

from bec_widgets.utils.forms_from_types.items import FormItemSpec, ListFormItem
from bec_widgets.utils.widget_io import WidgetIO


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Generic types don't support this in 3.10")
@pytest.mark.parametrize(
    ["input", "validity"],
    [
        ({}, False),
        ({"item_type": int, "name": "test", "info": FieldInfo(), "pretty_display": True}, True),
        (
            {
                "item_type": dict[dict, dict],
                "name": "test",
                "info": FieldInfo(),
                "pretty_display": True,
            },
            False,
        ),
        (
            {
                "item_type": dict[str, str],
                "name": "test",
                "info": FieldInfo(),
                "pretty_display": True,
            },
            True,
        ),
        (
            {
                "item_type": Literal["a", "b"],
                "name": "test",
                "info": FieldInfo(),
                "pretty_display": True,
            },
            True,
        ),
        (
            {
                "item_type": Literal["a", 2],
                "name": "test",
                "info": FieldInfo(),
                "pretty_display": True,
            },
            False,
        ),
    ],
)
def test_form_item_spec(input, validity):
    if validity:
        assert FormItemSpec.model_validate(input)
    else:
        with pytest.raises(ValidationError):
            FormItemSpec.model_validate(input)


@pytest.fixture(
    params=[
        {"type": list[int], "value": [1, 2, 3], "extra": 79},
        {"type": list[str], "value": ["a", "b", "c"], "extra": "string"},
        {"type": list[float], "value": [0.1, 0.2, 0.3], "extra": 79.0},
    ]
)
def list_field_and_values(request, qtbot):
    itype, vals, extra = (
        request.param.get("type"),
        request.param.get("value"),
        request.param.get("extra"),
    )
    spec = FormItemSpec(item_type=itype, name="test_list", info=FieldInfo(annotation=itype))
    (widget := ListFormItem(parent=None, spec=spec)).setValue(vals)
    qtbot.addWidget(widget)
    yield widget, vals, extra, get_args(itype)[0]


def test_list_metadata_field(list_field_and_values: tuple[ListFormItem, list, Any, type]):
    list_field, vals, extra, _ = list_field_and_values
    assert list_field.getValue() == vals
    assert list_field._main_widget.count() == 3

    list_field._add_button.click()
    assert len(list_field.getValue()) == 4
    assert list_field._main_widget.count() == 4

    list_field._main_widget.setCurrentRow(-1)
    list_field._remove_button.click()
    assert len(list_field.getValue()) == 4
    assert list_field._main_widget.count() == 4

    list_field._main_widget.setCurrentRow(2)
    list_field._remove_button.click()
    assert list_field.getValue() == vals[:2] + [list_field._types.default]
    assert list_field._main_widget.count() == 3

    list_field._main_widget.setCurrentRow(1)
    WidgetIO.set_value(list_field._main_widget.itemWidget(list_field._main_widget.item(1)), extra)
    assert list_field._main_widget.count() == 3
    assert list_field.getValue() == [vals[0], extra, list_field._types.default]

    list_field._add_item(extra)
    assert list_field._main_widget.count() == 4
    assert list_field.getValue() == [vals[0], extra, list_field._types.default, extra]


def test_list_field_value_acceptance(list_field_and_values: tuple[ListFormItem, list, Any, type]):
    class _WrongType(object): ...

    list_field, _, _, t = list_field_and_values
    list_field.setValue([])
    assert list_field._main_widget.count() == 0
    list_field.setValue([t(), t(), t()])
    assert list_field._main_widget.count() == 3
    with pytest.raises(ValueError) as e:
        list_field.setValue([_WrongType()])
    assert list_field._main_widget.count() == 3
    assert e.match(f"This widget only accepts items of type {t}")
