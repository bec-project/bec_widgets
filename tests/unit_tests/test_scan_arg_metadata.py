import pytest
from qtpy.QtWidgets import QDoubleSpinBox, QSpinBox

from bec_widgets.utils.scan_arg_metadata import (
    apply_numeric_limits,
    apply_numeric_precision,
    apply_unit_metadata,
    device_units,
    ui_config_from_metadata,
    unit_tooltip,
)

from .conftest import create_widget


def test_unit_tooltip_and_cleanup(qtbot):
    widget = create_widget(qtbot, QDoubleSpinBox)
    item = {"tooltip": "Move start", "reference_units": "device"}

    assert unit_tooltip(item) == "Move start\nUnits from: device"

    apply_unit_metadata(widget, item)
    assert widget.toolTip() == "Move start\nUnits from: device"
    assert widget.suffix() == ""

    apply_unit_metadata(widget, item, "mm")
    assert widget.toolTip() == "Move start\nUnits: mm"
    assert widget.suffix() == " mm"

    apply_unit_metadata(widget, item, "deg")
    assert widget.toolTip() == "Move start\nUnits: deg"
    assert widget.suffix() == " deg"


def test_numeric_precision_and_limits(qtbot):
    float_widget = create_widget(qtbot, QDoubleSpinBox)
    int_widget = create_widget(qtbot, QSpinBox)

    apply_numeric_precision(float_widget, {"name": "position", "precision": 3})
    apply_numeric_limits(float_widget, {"ge": -1.5, "lt": 2.0})
    apply_numeric_limits(int_widget, {"gt": 2, "le": 8})

    assert float_widget.decimals() == 3
    assert float_widget.minimum() == pytest.approx(-1.5)
    assert float_widget.maximum() == pytest.approx(1.999)
    assert int_widget.minimum() == 3
    assert int_widget.maximum() == 8


def test_device_units_uses_egu():
    class Device:
        def egu(self):
            return "mm"

    assert device_units(Device()) == "mm"
    assert device_units(object()) is None


def test_ui_config_from_metadata_matches_scan_control_item_shape():
    item = ui_config_from_metadata(
        name="exp_time",
        input_type="float",
        default=0.1,
        metadata={"tooltip": "Exposure", "units": "s", "precision": 3, "ge": 0},
    )

    assert item == {
        "arg": False,
        "name": "exp_time",
        "type": "float",
        "display_name": "Exp Time",
        "tooltip": "Exposure",
        "default": 0.1,
        "expert": False,
        "hidden": False,
        "precision": 3,
        "units": "s",
        "reference_units": None,
        "reference_limits": None,
        "gt": None,
        "ge": 0,
        "lt": None,
        "le": None,
        "alternative_group": None,
    }
