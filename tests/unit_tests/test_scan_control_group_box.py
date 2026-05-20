# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.control.scan_control.scan_group_box import ScanGroupBox


def _arg_group_input(min_bundles: int = 1) -> dict:
    return {
        "name": "Arg Test",
        "min": min_bundles,
        "inputs": [
            {
                "arg": True,
                "name": "device",
                "type": "str",
                "display_name": "Device",
                "tooltip": "Device to scan",
                "default": "samx",
                "expert": False,
            },
            {
                "arg": True,
                "name": "start",
                "type": "float",
                "display_name": "Start",
                "tooltip": "Start position",
                "default": 0,
                "expert": False,
            },
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
    assert kwarg_box.label_texts() == ["Exp Time", "Num Points", "Relative", "Scan Type"]

    # Widget 0
    assert kwarg_box.widgets[0].__class__.__name__ == "ScanDoubleSpinBox"
    assert kwarg_box.widgets[0].arg_name == "exp_time"
    assert WidgetIO.get_value(kwarg_box.widgets[0]) == 0
    assert "Exposure time in seconds" in kwarg_box.widgets[0].toolTip()

    # Widget 1
    assert kwarg_box.widgets[1].__class__.__name__ == "ScanSpinBox"
    assert kwarg_box.widgets[1].arg_name == "num_points"
    assert WidgetIO.get_value(kwarg_box.widgets[1]) == 1
    assert "Number of points" in kwarg_box.widgets[1].toolTip()

    # Widget 2
    assert kwarg_box.widgets[2].__class__.__name__ == "ScanCheckBox"
    assert kwarg_box.widgets[2].arg_name == "relative"
    assert WidgetIO.get_value(kwarg_box.widgets[2]) == False
    assert (
        "If True, the motors will be moved relative to their current position"
        in kwarg_box.widgets[2].toolTip()
    )

    # Widget 3
    assert kwarg_box.widgets[3].__class__.__name__ == "ScanLineEdit"
    assert kwarg_box.widgets[3].arg_name == "scan_type"
    assert WidgetIO.get_value(kwarg_box.widgets[3]) == "line"
    assert "Type of scan" in kwarg_box.widgets[3].toolTip()

    parameters = kwarg_box.get_parameters()
    assert parameters == {"exp_time": 0, "num_points": 1, "relative": False, "scan_type": "line"}


def test_arg_box(qtbot):
    group_input = _arg_group_input()

    arg_box = ScanGroupBox(box_type="args", config=group_input)
    assert arg_box is not None
    assert arg_box.box_type == "args"
    assert arg_box.config == group_input
    assert arg_box.title() == "Arg Test"

    # Labels
    assert arg_box.label_texts() == ["Device", "Start", "Stop"]

    # Widget 0
    assert arg_box.widgets[0].__class__.__name__ == "ScanLineEdit"
    assert arg_box.widgets[0].arg_name == "device"
    assert WidgetIO.get_value(arg_box.widgets[0]) == "samx"
    assert "Device to scan" in arg_box.widgets[0].toolTip()

    # Widget 1
    assert arg_box.widgets[1].__class__.__name__ == "ScanDoubleSpinBox"
    assert arg_box.widgets[1].arg_name == "start"
    assert WidgetIO.get_value(arg_box.widgets[1]) == 0
    assert "Start position" in arg_box.widgets[1].toolTip()

    # Widget 2
    assert arg_box.widgets[2].__class__.__name__ == "ScanSpinBox"
    assert arg_box.widgets[2].arg_name


def test_arg_bundles_have_separate_flow_layouts(qtbot):
    arg_box = ScanGroupBox(box_type="args", config=_arg_group_input(min_bundles=2))
    qtbot.addWidget(arg_box)
    arg_box.show()
    qtbot.waitExposed(arg_box)

    assert arg_box.count_arg_rows() == 2
    assert arg_box.get_bundle_widgets(0) == arg_box.widgets[:3]
    assert arg_box.get_bundle_widgets(1) == arg_box.widgets[3:6]
    assert arg_box.get_bundle_widgets(0)[0] is not arg_box.get_bundle_widgets(1)[0]
    assert arg_box.label_texts() == ["Device", "Start", "Stop", "Device", "Start", "Stop"]
    bundle_layout = arg_box._bundle_containers[0].flow_layout
    assert bundle_layout.heightForWidth(80) > bundle_layout.heightForWidth(500)


def test_scan_group_box_reports_wrapped_height_for_width(qtbot):
    arg_box = ScanGroupBox(box_type="args", config=_arg_group_input())
    qtbot.addWidget(arg_box)
    arg_box.show()
    qtbot.waitExposed(arg_box)

    assert arg_box.hasHeightForWidth()
    assert arg_box.heightForWidth(180) > arg_box.heightForWidth(800)


def test_scan_group_box_height_tracks_content(qtbot):
    # Mirrors real usage: ScanControl hosts the boxes in a top-aligned QVBoxLayout, and
    # Qt's native height-for-width propagation sizes the group box to its wrapped content.
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setAlignment(Qt.AlignTop)
    arg_box = ScanGroupBox(box_type="args", config=_arg_group_input())
    layout.addWidget(arg_box)
    qtbot.addWidget(container)
    container.resize(800, 400)
    container.show()
    qtbot.waitExposed(container)

    def height_tracks_hint(tolerance: int = 2) -> bool:
        # Allow a small tolerance: style metrics can introduce off-by-1 rounding between
        # the laid-out height and heightForWidth across platforms/styles.
        return abs(arg_box.height() - arg_box.heightForWidth(arg_box.width())) <= tolerance

    heights = {}
    for width in (800, 300):
        container.resize(width, 400)
        qtbot.waitUntil(height_tracks_hint, timeout=1000)
        heights[width] = arg_box.height()

    # Narrower container -> more wrapped rows -> taller box.
    assert heights[300] > heights[800]


def test_spinbox_limits_from_scan_info(qtbot):
    group_input = {
        "name": "Kwarg Test",
        "inputs": [
            {
                "arg": False,
                "name": "exp_time",
                "type": "float",
                "display_name": "Exp Time",
                "tooltip": "Exposure time in seconds",
                "default": 2.0,
                "expert": False,
                "precision": 3,
                "gt": 1.5,
                "ge": None,
                "lt": 5.0,
                "le": None,
            },
            {
                "arg": False,
                "name": "num_points",
                "type": "int",
                "display_name": "Num Points",
                "tooltip": "Number of points",
                "default": 4,
                "expert": False,
                "gt": None,
                "ge": 3,
                "lt": 9,
                "le": None,
            },
            {
                "arg": False,
                "name": "settling_time",
                "type": "float",
                "display_name": "Settling Time",
                "tooltip": "Settling time in seconds",
                "default": 0.5,
                "expert": False,
                "gt": None,
                "ge": 0.2,
                "lt": None,
                "le": 3.5,
            },
            {
                "arg": False,
                "name": "steps",
                "type": "int",
                "display_name": "Steps",
                "tooltip": "Number of steps",
                "default": 4,
                "expert": False,
                "gt": 0,
                "ge": None,
                "lt": None,
                "le": 10,
            },
        ],
    }

    kwarg_box = ScanGroupBox(box_type="kwargs", config=group_input)

    exp_time = kwarg_box.widgets[0]
    num_points = kwarg_box.widgets[1]
    settling_time = kwarg_box.widgets[2]
    steps = kwarg_box.widgets[3]

    assert exp_time.decimals() == 3
    assert exp_time.minimum() == 1.501
    assert exp_time.maximum() == 4.999
    assert num_points.minimum() == 3
    assert num_points.maximum() == 8
    assert settling_time.minimum() == 0.2
    assert settling_time.maximum() == 3.5
    assert steps.minimum() == 1
    assert steps.maximum() == 10
