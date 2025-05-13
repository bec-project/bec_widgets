import sys
from typing import Literal

import pytest
from pydantic import ValidationError
from pydantic.fields import FieldInfo

from bec_widgets.utils.forms_from_types.items import FormItemSpec


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
