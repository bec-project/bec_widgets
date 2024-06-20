# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import pytest

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.scan_control.scan_group_box import ScanGroupBox


def test_kwarg_box(qtbot):
    group_input = {
        "name": "Kwarg Test",
        "inputs": [
            # Test float
            {
                "arg": False,
                "name": "exp_time",
                "type": "float",
                "display_name": "Exp Time",
                "tooltip": "Exposure time in seconds",
                "default": 0,
                "expert": False,
            },
            # Test int
            {
                "arg": False,
                "name": "num_points",
                "type": "int",
                "display_name": "Num Points",
                "tooltip": "Number of points",
                "default": 1,
                "expert": False,
            },
            # Test bool
            {
                "arg": False,
                "name": "relative",
                "type": "bool",
                "display_name": "Relative",
                "tooltip": "If True, the motors will be moved relative to their current position",
                "default": False,
                "expert": False,
            },
            # Test str
            {
                "arg": False,
                "name": "scan_type",
                "type": "str",
                "display_name": "Scan Type",
                "tooltip": "Type of scan",
                "default": "line",
                "expert": False,
            },
        ],
    }

    kwarg_box = ScanGroupBox(box_type="kwargs", config=group_input)
    assert kwarg_box is not None
    assert kwarg_box.box_type == "kwargs"
    assert kwarg_box.config == group_input
    assert kwarg_box.title() == "Kwarg Test"

    # Labels
    assert kwarg_box.layout.itemAtPosition(0, 0).widget().text() == "Exp Time"
    assert kwarg_box.layout.itemAtPosition(0, 1).widget().text() == "Num Points"
    assert kwarg_box.layout.itemAtPosition(0, 2).widget().text() == "Relative"
    assert kwarg_box.layout.itemAtPosition(0, 3).widget().text() == "Scan Type"

    # Widget 0
    assert kwarg_box.widgets[0].__class__.__name__ == "ScanDoubleSpinBox"
    assert kwarg_box.widgets[0].arg_name == "exp_time"
    assert WidgetIO.get_value(kwarg_box.widgets[0]) == 0
    assert kwarg_box.widgets[0].toolTip() == "Exposure time in seconds"

    # Widget 1
    assert kwarg_box.widgets[1].__class__.__name__ == "ScanSpinBox"
    assert kwarg_box.widgets[1].arg_name == "num_points"
    assert WidgetIO.get_value(kwarg_box.widgets[1]) == 1
    assert kwarg_box.widgets[1].toolTip() == "Number of points"

    # Widget 2
    assert kwarg_box.widgets[2].__class__.__name__ == "ScanCheckBox"
    assert kwarg_box.widgets[2].arg_name == "relative"
    assert WidgetIO.get_value(kwarg_box.widgets[2]) == False
    assert (
        kwarg_box.widgets[2].toolTip()
        == "If True, the motors will be moved relative to their current position"
    )

    # Widget 3
    assert kwarg_box.widgets[3].__class__.__name__ == "ScanLineEdit"
    assert kwarg_box.widgets[3].arg_name == "scan_type"
    assert WidgetIO.get_value(kwarg_box.widgets[3]) == "line"
    assert kwarg_box.widgets[3].toolTip() == "Type of scan"

    parameters = kwarg_box.get_parameters()
    assert parameters == {"exp_time": 0, "num_points": 1, "relative": False, "scan_type": "line"}


def test_arg_box(qtbot):
    group_input = {
        "name": "Arg Test",
        "inputs": [
            # Test device
            {
                "arg": True,
                "name": "device",
                "type": "str",
                "display_name": "Device",
                "tooltip": "Device to scan",
                "default": "samx",
                "expert": False,
            },
            # Test float
            {
                "arg": True,
                "name": "start",
                "type": "float",
                "display_name": "Start",
                "tooltip": "Start position",
                "default": 0,
                "expert": False,
            },
            # Test int
            {
                "arg": True,
                "name": "stop",
                "type": "int",
                "display_name": "Stop",
                "tooltip": "Stop position",
                "default": 1,
                "expert": False,
            },
        ],
    }

    arg_box = ScanGroupBox(box_type="args", config=group_input)
    assert arg_box is not None
    assert arg_box.box_type == "args"
    assert arg_box.config == group_input
    assert arg_box.title() == "Arg Test"

    # Labels
    assert arg_box.layout.itemAtPosition(0, 0).widget().text() == "Device"
    assert arg_box.layout.itemAtPosition(0, 1).widget().text() == "Start"
    assert arg_box.layout.itemAtPosition(0, 2).widget().text() == "Stop"

    # Widget 0
    assert arg_box.widgets[0].__class__.__name__ == "ScanLineEdit"
    assert arg_box.widgets[0].arg_name == "device"
    assert WidgetIO.get_value(arg_box.widgets[0]) == "samx"
    assert arg_box.widgets[0].toolTip() == "Device to scan"

    # Widget 1
    assert arg_box.widgets[1].__class__.__name__ == "ScanDoubleSpinBox"
    assert arg_box.widgets[1].arg_name == "start"
    assert WidgetIO.get_value(arg_box.widgets[1]) == 0
    assert arg_box.widgets[1].toolTip() == "Start position"

    # Widget 2
    assert arg_box.widgets[2].__class__.__name__ == "ScanSpinBox"
    assert arg_box.widgets[2].arg_name
