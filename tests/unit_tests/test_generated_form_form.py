from decimal import Decimal
from unittest.mock import patch

import pytest
from bec_lib.device import Device, Signal
from bec_lib.scan_args import ScanArgument
from pydantic import BaseModel, Field
from qtpy.QtWidgets import QCheckBox, QLabel, QLineEdit

from bec_widgets.utils.forms_from_types.forms import PydanticModelForm, TypedForm
from bec_widgets.utils.forms_from_types.items import FloatDecimalFormItem, IntFormItem, StrFormItem
from bec_widgets.utils.forms_from_types.pydantic_widget_form import (
    OptionalValueWidget,
    PydanticWidgetForm,
)
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox
from bec_widgets.widgets.utility.spinbox.decimal_spinbox import BECSpinBox

from .client_mocks import mocked_client

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


class GeneratedBeamlineSchema(BaseModel):
    name: str = Field(title="State name", description="Unique state identifier.")
    title: str | None = Field(default=None, title="Display title", description="Visible title.")
    device: Device | str = Field(title="Device", description="BEC device.")
    signal: Signal | str | None = Field(
        default=None, title="Signal", description="Optional device signal."
    )
    limit: float | None = Field(
        default=None,
        title="Limit",
        description="Optional numeric limit.",
        json_schema_extra={"precision": 6},
    )
    tolerance: float = Field(
        default=0.1,
        title="Tolerance",
        description="Warning tolerance.",
        json_schema_extra={"precision": 6},
    )

    model_config = {"arbitrary_types_allowed": True}


class GeneratedPlainSchema(BaseModel):
    sample_name: str


class GeneratedDeviceOnlySchema(BaseModel):
    device: Device | str = Field(default="", title="Device")

    model_config = {"arbitrary_types_allowed": True}


class GeneratedSignalOnlySchema(BaseModel):
    signal: Signal | str | None = Field(default=None, title="Signal")

    model_config = {"arbitrary_types_allowed": True}


class GeneratedScanArgumentSchema(BaseModel):
    device: Device | str = Field(
        default="", **ScanArgument(display_name="Device", description="Device source.").model_dump()
    )
    signal: Signal | str | None = Field(
        default=None,
        **ScanArgument(display_name="Signal", description="Signal source.").model_dump(),
    )
    low_limit: float | None = Field(
        default=None,
        **ScanArgument(
            display_name="Low limit",
            description="Optional lower bound.",
            reference_units="device",
            precision=4,
            ge=-5,
            le=5,
        ).model_dump(),
    )
    exposure: float = Field(
        default=0.1,
        **ScanArgument(
            display_name="Exposure", tooltip="Camera exposure.", units="s", precision=3, gt=0
        ).model_dump(),
    )

    model_config = {"arbitrary_types_allowed": True}


class GeneratedRequiredNumericAndOptionalBoolSchema(BaseModel):
    enabled: bool | None = None
    retry_count: int
    scale: float


TEST_DICT = {
    "sample_name": "test name",
    "str_optional": "None",
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
def model_widget(qtbot):
    widget = PydanticModelForm(data_model=ExampleSchema)
    widget.populate()
    qtbot.addWidget(widget)
    yield widget


def test_widget_dict(model_widget: PydanticModelForm):
    assert isinstance(model_widget.widget_dict["str_optional"], StrFormItem)
    assert isinstance(model_widget.widget_dict["float_nodefault"], FloatDecimalFormItem)
    assert isinstance(model_widget.widget_dict["int_default"], IntFormItem)


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


def test_pydantic_widget_form_uses_field_metadata_and_type_widgets(qtbot, mocked_client):
    form = PydanticWidgetForm(GeneratedBeamlineSchema, client=mocked_client)
    qtbot.addWidget(form)

    assert isinstance(form.input_widget("name"), QLineEdit)
    assert isinstance(form.input_widget("device"), DeviceComboBox)
    assert isinstance(form.input_widget("signal"), SignalComboBox)
    assert isinstance(form.field_widget("limit"), OptionalValueWidget)
    assert isinstance(form.input_widget("limit"), BECSpinBox)
    assert form.input_widgets_by_type(DeviceComboBox) == [form.input_widget("device")]
    assert form.input_widgets_by_type(SignalComboBox) == [form.input_widget("signal")]

    label = form.layout().labelForField(form.field_widget("device"))
    assert isinstance(label, QLabel)
    assert label.text() == "Device"
    assert label.toolTip() == "BEC device."
    assert form.field_widget("limit").toolTip() == "Optional numeric limit."


def test_pydantic_widget_form_device_signal_variants(qtbot, mocked_client):
    device_signal_form = PydanticWidgetForm(GeneratedBeamlineSchema, client=mocked_client)
    device_only_form = PydanticWidgetForm(GeneratedDeviceOnlySchema, client=mocked_client)
    signal_only_form = PydanticWidgetForm(GeneratedSignalOnlySchema, client=mocked_client)
    qtbot.addWidget(device_signal_form)
    qtbot.addWidget(device_only_form)
    qtbot.addWidget(signal_only_form)

    assert isinstance(device_signal_form.input_widget("device"), DeviceComboBox)
    assert isinstance(device_signal_form.input_widget("signal"), SignalComboBox)
    assert device_signal_form.input_widget("signal").require_device is True

    assert isinstance(device_only_form.input_widget("device"), DeviceComboBox)
    assert device_only_form.input_widgets_by_type(SignalComboBox) == []

    assert isinstance(signal_only_form.input_widget("signal"), SignalComboBox)
    assert signal_only_form.input_widget("signal").require_device is False
    assert signal_only_form.input_widgets_by_type(DeviceComboBox) == []


def test_pydantic_widget_form_plain_field_has_generated_label_and_no_tooltip(qtbot):
    form = PydanticWidgetForm(GeneratedPlainSchema)
    qtbot.addWidget(form)

    label = form.layout().labelForField(form.field_widget("sample_name"))
    assert isinstance(label, QLabel)
    assert label.text() == "Sample name"
    assert label.toolTip() == ""
    assert form.field_widget("sample_name").toolTip() == ""


def test_pydantic_model_input_configs_reads_bl_states_annotated_scan_arguments():
    """Contract test: ScanArgument metadata attached via ``Annotated`` in bec_lib's beamline
    state configs must reach the generated-form configuration."""
    from bec_lib import bl_states

    from bec_widgets.utils.forms_from_types.pydantic_model_info_adapter import (
        pydantic_model_input_configs,
    )

    items = {
        item["name"]: item
        for item in pydantic_model_input_configs(bl_states.DeviceWithinLimitsState.CONFIG_CLASS)
    }

    assert items["name"]["display_name"] == "State name"
    assert items["name"]["tooltip"]
    assert items["device"]["display_name"] == "Device"
    assert items["low_limit"]["reference_units"] == "device"
    assert items["high_limit"]["reference_units"] == "device"
    assert items["tolerance"]["reference_units"] == "device"


def test_pydantic_widget_form_uses_scan_argument_metadata(qtbot, mocked_client):
    form = PydanticWidgetForm(GeneratedScanArgumentSchema, client=mocked_client)
    qtbot.addWidget(form)

    low_limit = form.field_widget("low_limit")
    low_limit_input = form.input_widget("low_limit")
    exposure = form.input_widget("exposure")

    low_limit_label = form.layout().labelForField(low_limit)
    assert isinstance(low_limit_label, QLabel)
    assert low_limit_label.text() == "Low limit"
    assert low_limit.toolTip() == "Optional lower bound.\nUnits from: device"
    assert low_limit_input.toolTip() == "Optional lower bound.\nUnits from: device"
    assert low_limit_input.decimals() == 4
    assert low_limit_input.minimum() == pytest.approx(-5)
    assert low_limit_input.maximum() == pytest.approx(5)

    assert form.field_widget("exposure").toolTip() == "Camera exposure.\nUnits: s"
    assert exposure.toolTip() == "Camera exposure.\nUnits: s"
    assert exposure.suffix() == " s"
    assert exposure.decimals() == 3
    assert exposure.minimum() == pytest.approx(0.001)

    with patch.object(mocked_client.device_manager.devices.samx, "egu", return_value="mm"):
        WidgetIO.set_value(form.input_widget("device"), "samx")

    assert low_limit.toolTip() == "Optional lower bound.\nUnits: mm"
    assert low_limit_input.toolTip() == "Optional lower bound.\nUnits: mm"
    assert low_limit_input.suffix() == " mm"


def test_pydantic_widget_form_cleans_up_on_close(qtbot):
    form = PydanticWidgetForm(GeneratedPlainSchema)
    qtbot.addWidget(form)

    form.close()

    assert form.widgets == {}
    assert form.layout().count() == 0


def test_pydantic_widget_form_round_trips_optional_numeric_and_dirty_state(qtbot, mocked_client):
    form = PydanticWidgetForm(
        GeneratedBeamlineSchema,
        client=mocked_client,
        data={"name": "state_1", "title": "State", "device": "samx", "signal": "samx"},
    )
    qtbot.addWidget(form)

    assert form.get_data()["limit"] is None

    limit = form.field_widget("limit")
    limit.checkbox.setChecked(True)
    form.input_widget("limit").setValue(5.0)

    assert form.get_data()["limit"] == 5.0
    assert form.model_instance().limit == 5.0
    assert "limit" in form.dirty_fields()

    form.reset_to_baseline()

    assert form.get_data()["limit"] is None
    assert form.dirty_fields() == set()


def test_pydantic_widget_form_initializes_required_numeric_fields(qtbot):
    form = PydanticWidgetForm(GeneratedRequiredNumericAndOptionalBoolSchema)
    qtbot.addWidget(form)

    assert form.raw_data()["retry_count"] == 0
    assert form.raw_data()["scale"] == 0.0
    assert form.model_instance().retry_count == 0
    assert form.model_instance().scale == 0.0


def test_pydantic_widget_form_preserves_optional_bool_none(qtbot):
    form = PydanticWidgetForm(GeneratedRequiredNumericAndOptionalBoolSchema)
    qtbot.addWidget(form)

    enabled = form.field_widget("enabled")

    assert isinstance(enabled, OptionalValueWidget)
    assert isinstance(form.input_widget("enabled"), QCheckBox)
    assert form.raw_data()["enabled"] is None
    assert form.model_instance().enabled is None

    enabled.checkbox.setChecked(True)
    form.input_widget("enabled").setChecked(True)

    assert form.raw_data()["enabled"] is True
    assert form.model_instance().enabled is True
