# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import AvailableResourceMessage, ScanHistoryMessage
from qtpy.QtCore import QModelIndex, QPoint, Qt
from qtpy.QtWidgets import QCheckBox, QDialog, QStyle

from bec_widgets.utils.forms_from_types.items import StrFormItem
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.scan_control import ScanControl
from bec_widgets.widgets.control.scan_control.scan_control import ScanControlConfig
from bec_widgets.widgets.control.scan_control.scan_info_adapter import ScanInfoAdapter
from bec_widgets.widgets.control.scan_control.scan_selection_dialog import ScanSelectionDialog

from .client_mocks import mocked_client

# pylint: disable=no-member
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

available_scans_message = AvailableResourceMessage(
    resource={
        "line_scan": {
            "class": "LineScan",
            "base_class": "ScanBase",
            "doc": (
                "Run a line scan.\n\n"
                "Args:\n"
                "    device (DeviceBase | str): Device to move.\n\n"
                "Examples:\n"
                "    >>> scans.line_scan(samx, 0, 1)"
            ),
            "arg_input": {"device": "device", "start": "float", "stop": "float"},
            "gui_config": {
                "scan_class_name": "LineScan",
                "arg_group": {
                    "name": "Scan Arguments",
                    "bundle": 3,
                    "arg_inputs": {"device": "device", "start": "float", "stop": "float"},
                    "inputs": [
                        {
                            "arg": True,
                            "name": "device",
                            "type": "device",
                            "display_name": "Device",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "start",
                            "type": "float",
                            "display_name": "Start",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "stop",
                            "type": "float",
                            "display_name": "Stop",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                    ],
                    "min": 1,
                    "max": None,
                },
                "kwarg_groups": [
                    {
                        "name": "Movement Parameters",
                        "inputs": [
                            {
                                "arg": False,
                                "name": "steps",
                                "type": "int",
                                "display_name": "Steps",
                                "tooltip": "Number of steps",
                                "default": None,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "relative",
                                "type": "bool",
                                "display_name": "Relative",
                                "tooltip": "If True, the start and end positions are relative to the current position",
                                "default": False,
                                "expert": False,
                            },
                        ],
                    },
                    {
                        "name": "Acquisition Parameters",
                        "inputs": [
                            {
                                "arg": False,
                                "name": "exp_time",
                                "type": "float",
                                "display_name": "Exp Time",
                                "tooltip": "Exposure time in s",
                                "default": 0,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "burst_at_each_point",
                                "type": "int",
                                "display_name": "Burst At Each Point",
                                "tooltip": "Number of acquisition per point",
                                "default": 1,
                                "expert": False,
                            },
                        ],
                    },
                ],
            },
            "required_kwargs": ["steps", "relative"],
            "arg_bundle_size": {"bundle": 3, "min": 1, "max": None},
        },
        "grid_scan": {
            "class": "Scan",
            "base_class": "ScanBase",
            "doc": "Run a grid scan over one or more devices.",
            "arg_input": {"device": "device", "start": "float", "stop": "float", "steps": "int"},
            "gui_config": {
                "scan_class_name": "Scan",
                "arg_group": {
                    "name": "Scan Arguments",
                    "bundle": 4,
                    "arg_inputs": {
                        "device": "device",
                        "start": "float",
                        "stop": "float",
                        "steps": "int",
                    },
                    "inputs": [
                        {
                            "arg": True,
                            "name": "device",
                            "type": "device",
                            "display_name": "Device",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "start",
                            "type": "float",
                            "display_name": "Start",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "stop",
                            "type": "float",
                            "display_name": "Stop",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "steps",
                            "type": "int",
                            "display_name": "Steps",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                    ],
                    "min": 2,
                    "max": None,
                },
                "kwarg_groups": [
                    {
                        "name": "Scan Parameters",
                        "inputs": [
                            {
                                "arg": False,
                                "name": "exp_time",
                                "type": "float",
                                "display_name": "Exp Time",
                                "tooltip": "Exposure time in seconds",
                                "default": 0,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "settling_time",
                                "type": "float",
                                "display_name": "Settling Time",
                                "tooltip": "Settling time in seconds",
                                "default": 0,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "burst_at_each_point",
                                "type": "int",
                                "display_name": "Burst At Each Point",
                                "tooltip": "Number of exposures at each point",
                                "default": 1,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "relative",
                                "type": "bool",
                                "display_name": "Relative",
                                "tooltip": "If True, the motors will be moved relative to their current position",
                                "default": False,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "optim_trajectory",
                                "type": {"Literal": ("option1", "option2", "option3", None)},
                                "display_name": "Optim Trajectory",
                                "tooltip": None,
                                "default": None,
                                "expert": False,
                            },
                        ],
                    }
                ],
            },
            "required_kwargs": ["relative"],
            "arg_bundle_size": {"bundle": 4, "min": 2, "max": None},
        },
        "not_supported_scan_class": {"base_class": "NotSupportedScanClass"},
    }
)

scan_history = ScanHistoryMessage(
    metadata={},
    scan_id="79cbef20-9ebe-45bb-a44c-f518be27a25c",
    scan_number=1,
    dataset_number=1,
    file_path="/somepath/scan_1.h5",
    exit_status="closed",
    start_time=1750618470.936856,
    end_time=1750618473.668227,
    scan_name="line_scan",
    num_points=100,
    request_inputs={
        "arg_bundle": ["samx", 0.0, 2.0],
        "inputs": {},
        "kwargs": {
            "steps": 10,
            "exp_time": 2,
            "relative": False,
            "system_config": {"file_suffix": None, "file_directory": None},
        },
    },
)


@pytest.fixture(scope="function")
def scan_control(qtbot, mocked_client):  # , mock_dev):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )
    mocked_client.connector.xadd(
        topic=MessageEndpoints.scan_history(), msg_dict={"data": scan_history}
    )
    widget = ScanControl(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_populate_scans(scan_control, mocked_client):
    expected_scans = ["line_scan", "grid_scan"]
    items = [
        scan_control.comboBox_scan_selection.itemText(i)
        for i in range(scan_control.comboBox_scan_selection.count())
    ]

    assert scan_control.comboBox_scan_selection.count() == 2
    assert sorted(items) == sorted(expected_scans)


def test_scan_selector_items_and_combo_show_doc_tooltips(scan_control):
    line_index = scan_control.comboBox_scan_selection.findText("line_scan")
    line_tooltip = scan_control.comboBox_scan_selection.itemData(
        line_index, Qt.ItemDataRole.ToolTipRole
    )

    assert "line_scan" in line_tooltip
    assert "Run a line scan." in line_tooltip
    assert "Parameters:" in line_tooltip
    assert "device: DeviceBase | str" in line_tooltip
    assert scan_control.comboBox_scan_selection.toolTip() == line_tooltip

    scan_control.comboBox_scan_selection.setCurrentText("grid_scan")

    assert "grid_scan" in scan_control.comboBox_scan_selection.toolTip()
    assert "Run a grid scan" in scan_control.comboBox_scan_selection.toolTip()


def test_scan_info_button_shows_styled_selected_scan_docstring(scan_control, qtbot):
    assert not scan_control.scan_info_button.icon().isNull()
    assert scan_control.scan_info_button.accessibleName() == "Scan information"

    with patch.object(scan_control.client.connector, "get") as connector_get:
        qtbot.mouseClick(scan_control.scan_info_button, Qt.MouseButton.LeftButton)
    connector_get.assert_not_called()

    assert scan_control._scan_info_dialog.isVisible()
    assert not scan_control._scan_info_dialog.isModal()
    assert scan_control._scan_info_dialog.windowTitle() == "Scan information: line_scan"
    plain_text = scan_control._scan_info_dialog.text_browser.toPlainText()
    assert "line_scan" in plain_text
    assert "Arguments" in plain_text
    assert "device" in plain_text
    assert "Examples" in plain_text
    assert ">>> scans.line_scan" in plain_text
    style = scan_control._scan_info_dialog.text_browser.document().defaultStyleSheet()
    assert "h1" in style
    assert "pre" in style


def test_scan_info_button_handles_missing_docstring(scan_control, qtbot):
    scan_control.available_scans["line_scan"].pop("doc")

    qtbot.mouseClick(scan_control.scan_info_button, Qt.MouseButton.LeftButton)

    assert "No documentation is available for this scan." in (
        scan_control._scan_info_dialog.text_browser.toPlainText()
    )


def test_allowed_scans_property_filters_selector(scan_control):
    scan_control.comboBox_scan_selection.setCurrentText("grid_scan")

    scan_control.allowed_scans = ["line_scan", "unknown_scan", "line_scan"]

    # The configured filter is kept verbatim (deduplicated) so that scans that are not
    # available right now reappear once the scan server publishes them.
    assert scan_control.allowed_scans == ["line_scan", "unknown_scan"]
    assert scan_control.config.allowed_scans == ["line_scan", "unknown_scan"]
    assert scan_control.comboBox_scan_selection.count() == 1
    assert scan_control.current_scan == "line_scan"


def test_allowed_scans_none_clears_filter(scan_control):
    scan_control.allowed_scans = ["line_scan"]
    assert scan_control.comboBox_scan_selection.count() == 1

    scan_control.allowed_scans = None

    assert scan_control.allowed_scans is None
    assert scan_control.config.allowed_scans is None
    assert scan_control.comboBox_scan_selection.count() == 2


def test_allowed_scans_override_support_filter(scan_control):
    scan_control.allowed_scans = ["not_supported_scan_class", "line_scan"]

    items = [
        scan_control.comboBox_scan_selection.itemText(i)
        for i in range(scan_control.comboBox_scan_selection.count())
    ]

    assert items == ["not_supported_scan_class", "line_scan"]


def test_filter_change_saves_current_scan_parameters(scan_control):
    assert scan_control.current_scan == "line_scan"

    scan_control.allowed_scans = ["grid_scan"]

    assert scan_control.current_scan == "grid_scan"
    assert "line_scan" in scan_control.config.scans


def test_empty_allowed_scans_disable_scan_info_and_run(scan_control):
    scan_control.allowed_scans = []

    assert scan_control.comboBox_scan_selection.count() == 0
    assert scan_control.comboBox_scan_selection.toolTip() == ""
    assert not scan_control.scan_info_button.isEnabled()
    assert not scan_control.button_run_scan.isEnabled()
    # run_scan must not raise even if triggered without a selected scan
    scan_control.run_scan()


def test_configured_allowed_scans_are_preserved(qtbot, mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )
    config = ScanControlConfig(widget_class="ScanControl", allowed_scans=["grid_scan"])

    widget = ScanControl(client=mocked_client, config=config)
    qtbot.addWidget(widget)

    assert widget.allowed_scans == ["grid_scan"]
    assert widget.comboBox_scan_selection.count() == 1
    assert widget.comboBox_scan_selection.currentText() == "grid_scan"


def test_configured_default_scan_is_preserved_and_applied(qtbot, mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )

    widget = ScanControl(client=mocked_client, default_scan="grid_scan")
    qtbot.addWidget(widget)
    assert widget.comboBox_scan_selection.currentText() == "grid_scan"

    # A default_scan from a passed-in config must not be wiped by the ctor default None
    config = ScanControlConfig(widget_class="ScanControl", default_scan="grid_scan")
    widget_from_config = ScanControl(client=mocked_client, config=config)
    qtbot.addWidget(widget_from_config)
    assert widget_from_config.config.default_scan == "grid_scan"
    assert widget_from_config.comboBox_scan_selection.currentText() == "grid_scan"


def test_scan_selector_settings_dialog_applies_checked_scans(scan_control, monkeypatch, qtbot):
    def select_line_scan(dialog):
        labels = [dialog.checkbox_for_scan(name).text() for name in ("line_scan", "grid_scan")]
        assert labels == ["line_scan", "grid_scan"]
        checkbox = dialog.checkbox_for_scan("grid_scan")
        assert isinstance(checkbox, QCheckBox)
        checkbox.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ScanSelectionDialog, "exec", select_line_scan)

    qtbot.mouseClick(scan_control.scan_selector_settings_button, Qt.MouseButton.LeftButton)

    assert scan_control.allowed_scans == ["line_scan"]
    assert scan_control.comboBox_scan_selection.count() == 1
    assert scan_control.comboBox_scan_selection.currentText() == "line_scan"


def test_scan_selector_settings_dialog_all_checked_clears_filter(scan_control, monkeypatch, qtbot):
    scan_control.allowed_scans = ["line_scan"]

    def check_everything(dialog):
        dialog.checkbox_for_scan("grid_scan").setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ScanSelectionDialog, "exec", check_everything)

    qtbot.mouseClick(scan_control.scan_selector_settings_button, Qt.MouseButton.LeftButton)

    assert scan_control.allowed_scans is None
    assert scan_control.comboBox_scan_selection.count() == 2


def test_scan_selector_settings_dialog_is_released_after_use(scan_control, monkeypatch, qtbot):
    monkeypatch.setattr(ScanSelectionDialog, "exec", lambda dialog: QDialog.DialogCode.Rejected)
    with patch.object(ScanSelectionDialog, "deleteLater") as delete_later:
        qtbot.mouseClick(scan_control.scan_selector_settings_button, Qt.MouseButton.LeftButton)
    delete_later.assert_called_once()


def test_scan_selector_dialog_whole_row_click_toggles_checkbox(qtbot):
    dialog = ScanSelectionDialog(
        scan_names=["line_scan", "grid_scan"], selected_scans=["line_scan"]
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    checkbox = dialog.checkbox_for_scan("line_scan")
    assert isinstance(checkbox, QCheckBox)
    assert checkbox.isChecked()

    indicator_width = checkbox.style().pixelMetric(
        QStyle.PixelMetric.PM_IndicatorWidth, widget=checkbox
    )
    label_right = indicator_width + 8 + checkbox.fontMetrics().horizontalAdvance(checkbox.text())
    empty_row_x = checkbox.rect().right() - 8
    assert empty_row_x > label_right
    qtbot.mouseClick(
        checkbox, Qt.MouseButton.LeftButton, pos=QPoint(empty_row_x, checkbox.rect().center().y())
    )

    assert not checkbox.isChecked()
    assert dialog.selected_scans() == []


def test_scan_selector_dialog_info_button_opens_docs_without_toggling(qtbot):
    dialog = ScanSelectionDialog(
        scan_names=["line_scan"],
        selected_scans=["line_scan"],
        scan_docs={"line_scan": available_scans_message.resource["line_scan"]["doc"]},
    )
    qtbot.addWidget(dialog)
    dialog.setModal(True)
    dialog.show()
    qtbot.waitExposed(dialog)

    checkbox = dialog.checkbox_for_scan("line_scan")
    info_button = dialog.info_button_for_scan("line_scan")
    qtbot.mouseClick(info_button, Qt.MouseButton.LeftButton)

    assert checkbox.isChecked()
    assert dialog._scan_info_dialog.parent() is dialog
    assert dialog._scan_info_dialog.isVisible()
    assert dialog._scan_info_dialog.windowTitle() == "Scan information: line_scan"
    assert "Arguments" in dialog._scan_info_dialog.text_browser.toPlainText()


def test_scan_selector_settings_properties_are_profile_safe(scan_control):
    exported = scan_control.export_settings()

    # "No filter" survives the round trip as None so that future scans keep appearing.
    assert exported["allowed_scans"] is None
    assert exported["hide_scan_selector_settings_button"] is False

    scan_control.load_settings(
        {"allowed_scans": ["grid_scan"], "hide_scan_selector_settings_button": True}
    )

    assert scan_control.allowed_scans == ["grid_scan"]
    assert scan_control.comboBox_scan_selection.currentText() == "grid_scan"
    assert scan_control.hide_scan_selector_settings_button is True
    assert scan_control.scan_selector_settings_button.isHidden()

    scan_control.load_settings({"allowed_scans": None})

    assert scan_control.allowed_scans is None
    assert scan_control.comboBox_scan_selection.count() == 2


def test_scan_control_uses_gui_visibility_and_signature(qtbot, mocked_client):
    scan_info = {
        "class": "AnnotatedScan",
        "base_class": "ScanBase",
        "arg_input": {
            "device": "DeviceBase",
            "start": {
                "Annotated": {
                    "type": "float",
                    "metadata": {
                        "ScanArgument": {
                            "display_name": "Start Position",
                            "description": "Start position",
                            "tooltip": "Custom start tooltip",
                            "expert": False,
                            "alternative_group": None,
                            "units": None,
                            "reference_units": "device",
                        }
                    },
                }
            },
            "stop": {
                "Annotated": {
                    "type": "float",
                    "metadata": {
                        "ScanArgument": {
                            "display_name": None,
                            "description": "Stop position",
                            "tooltip": None,
                            "expert": False,
                            "alternative_group": None,
                            "units": None,
                            "reference_units": "device",
                        }
                    },
                }
            },
        },
        "arg_bundle_size": {"bundle": 3, "min": 1, "max": None},
        "gui_visibility": {
            "Movement Parameters": ["steps", "step_size"],
            "Acquisition Parameters": ["exp_time", "relative"],
        },
        "required_kwargs": [],
        "signature": [
            {"name": "args", "kind": "VAR_POSITIONAL", "default": "_empty", "annotation": "_empty"},
            {"name": "steps", "kind": "KEYWORD_ONLY", "default": 10, "annotation": "int"},
            {
                "name": "step_size",
                "kind": "KEYWORD_ONLY",
                "default": None,
                "annotation": {
                    "Annotated": {
                        "type": "float",
                        "metadata": {
                            "ScanArgument": {
                                "display_name": "Step Size Custom",
                                "description": "Step size",
                                "tooltip": "Custom step tooltip",
                                "expert": False,
                                "alternative_group": "scan_resolution",
                                "units": "mm",
                                "reference_units": None,
                            }
                        },
                    }
                },
            },
            {
                "name": "exp_time",
                "kind": "KEYWORD_ONLY",
                "default": 0,
                "annotation": {
                    "Annotated": {
                        "type": "float",
                        "metadata": {
                            "ScanArgument": {
                                "display_name": None,
                                "description": None,
                                "tooltip": "Exposure time",
                                "expert": False,
                                "alternative_group": None,
                                "units": "s",
                                "reference_units": None,
                            }
                        },
                    }
                },
            },
            {"name": "relative", "kind": "KEYWORD_ONLY", "default": False, "annotation": "bool"},
            {"name": "kwargs", "kind": "VAR_KEYWORD", "default": "_empty", "annotation": "_empty"},
        ],
    }
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(),
        AvailableResourceMessage(resource={"annotated_scan": scan_info}),
    )

    widget = ScanControl(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    widget.comboBox_scan_selection.setCurrentText("annotated_scan")

    assert widget.comboBox_scan_selection.count() == 1
    assert widget.arg_box.label_for_widget(widget.arg_box.widgets[1]).text() == "Start Position"
    assert "Custom start tooltip\nUnits from: device" in widget.arg_box.widgets[1].toolTip()
    with patch.object(mocked_client.device_manager.devices.samx, "egu", return_value="mm"):
        WidgetIO.set_value(widget.arg_box.widgets[0], "samx")
    assert widget.arg_box.label_for_widget(widget.arg_box.widgets[1]).text() == "Start Position"
    assert widget.arg_box.widgets[1].suffix() == " mm"
    assert "Custom start tooltip\nUnits: mm" in widget.arg_box.widgets[1].toolTip()
    widget.arg_box.widgets[0].setCurrentText("not_a_device")
    assert widget.arg_box.label_for_widget(widget.arg_box.widgets[1]).text() == "Start Position"
    assert widget.arg_box.widgets[1].suffix() == ""
    assert "Custom start tooltip\nUnits from: device" in widget.arg_box.widgets[1].toolTip()
    assert [box.title() for box in widget.kwarg_boxes] == [
        "Movement Parameters",
        "Acquisition Parameters",
    ]
    assert widget.kwarg_boxes[0].label_for_widget(widget.kwarg_boxes[0].widgets[1]).text() == (
        "Step Size Custom"
    )
    assert widget.kwarg_boxes[0].widgets[1].suffix() == " mm"
    assert "Custom step tooltip\nUnits: mm" in widget.kwarg_boxes[0].widgets[1].toolTip()
    assert widget.kwarg_boxes[1].label_for_widget(widget.kwarg_boxes[1].widgets[0]).text() == (
        "Exp Time"
    )
    assert "Exposure time\nUnits: s" in widget.kwarg_boxes[1].widgets[0].toolTip()


def test_scan_info_adapter_skips_duplicate_visible_kwargs():
    scan_info = {
        "class": "DuplicateScan",
        "base_class": "ScanBaseV4",
        "arg_input": {},
        "arg_bundle_size": {"bundle": 0, "min": None, "max": None},
        "gui_visibility": {
            "Scan Parameters": ["relative", "burst_at_each_point"],
            "Acquisition Parameters": ["exp_time", "burst_at_each_point"],
        },
        "signature": [
            {"name": "relative", "kind": "KEYWORD_ONLY", "default": False, "annotation": "bool"},
            {
                "name": "burst_at_each_point",
                "kind": "KEYWORD_ONLY",
                "default": 1,
                "annotation": "int",
            },
            {"name": "exp_time", "kind": "KEYWORD_ONLY", "default": 0, "annotation": "float"},
        ],
    }

    gui_config = ScanInfoAdapter().build_scan_ui_config(scan_info)
    groups = {
        group["name"]: [input_spec["name"] for input_spec in group["inputs"]]
        for group in gui_config["kwarg_groups"]
    }

    assert groups == {
        "Scan Parameters": ["relative", "burst_at_each_point"],
        "Acquisition Parameters": ["exp_time"],
    }


def test_scan_info_adapter_rejects_unsupported_visible_inputs():
    scan_info = {
        "class": "UnsupportedScan",
        "base_class": "ScanBaseV4",
        "arg_input": {},
        "arg_bundle_size": {"bundle": 0, "min": None, "max": None},
        "gui_visibility": {"Regions": ["regions"]},
        "signature": [
            {
                "name": "regions",
                "kind": "KEYWORD_ONLY",
                "default": "_empty",
                "annotation": {
                    "Generic": {
                        "origin": "list",
                        "args": [
                            {"Generic": {"origin": "tuple", "args": ["float", "float", "int"]}}
                        ],
                    }
                },
            }
        ],
    }

    gui_config = ScanInfoAdapter().build_scan_ui_config(scan_info)
    unsupported_inputs = ScanInfoAdapter.unsupported_inputs(gui_config)

    assert [input_spec["name"] for input_spec in unsupported_inputs] == ["regions"]
    assert ScanInfoAdapter.has_scan_ui_config(scan_info) is False


def test_scan_info_adapter_skips_hidden_visible_kwargs():
    scan_info = {
        "class": "HiddenScan",
        "base_class": "ScanBaseV4",
        "arg_input": {},
        "arg_bundle_size": {"bundle": 0, "min": None, "max": None},
        "gui_visibility": {"Acquisition": ["exp_time", "internal_token"]},
        "signature": [
            {"name": "exp_time", "kind": "KEYWORD_ONLY", "default": 0, "annotation": "float"},
            {
                "name": "internal_token",
                "kind": "KEYWORD_ONLY",
                "default": None,
                "annotation": {
                    "Annotated": {
                        "type": "str",
                        "metadata": {
                            "ScanArgument": {"display_name": "Internal Token", "hidden": True}
                        },
                    }
                },
            },
        ],
    }

    gui_config = ScanInfoAdapter().build_scan_ui_config(scan_info)

    assert [input_spec["name"] for input_spec in gui_config["kwarg_groups"][0]["inputs"]] == [
        "exp_time"
    ]


def test_scan_control_propagates_reference_units_across_kwarg_groups(qtbot, mocked_client):
    scan_info = {
        "class": "RoundScan",
        "base_class": "ScanBaseV4",
        "arg_input": {},
        "arg_bundle_size": {"bundle": 0, "min": None, "max": None},
        "gui_visibility": {
            "Motors": ["motor_1", "motor_2"],
            "Ring Parameters": ["inner_radius", "outer_radius", "center_1", "center_2"],
        },
        "required_kwargs": [],
        "signature": [
            {
                "name": "motor_1",
                "kind": "POSITIONAL_OR_KEYWORD",
                "default": "_empty",
                "annotation": "DeviceBase",
            },
            {
                "name": "motor_2",
                "kind": "POSITIONAL_OR_KEYWORD",
                "default": "_empty",
                "annotation": "DeviceBase",
            },
            {
                "name": "inner_radius",
                "kind": "POSITIONAL_OR_KEYWORD",
                "default": "_empty",
                "annotation": {
                    "Annotated": {
                        "type": "float",
                        "metadata": {
                            "ScanArgument": {
                                "display_name": "Inner Radius",
                                "units": None,
                                "reference_units": "motor_1",
                                "ge": 0,
                            }
                        },
                    }
                },
            },
            {
                "name": "outer_radius",
                "kind": "POSITIONAL_OR_KEYWORD",
                "default": "_empty",
                "annotation": {
                    "Annotated": {
                        "type": "float",
                        "metadata": {
                            "ScanArgument": {
                                "display_name": "Outer Radius",
                                "units": None,
                                "reference_units": "motor_1",
                                "ge": 0,
                            }
                        },
                    }
                },
            },
            {
                "name": "center_1",
                "kind": "KEYWORD_ONLY",
                "default": 0,
                "annotation": {
                    "Annotated": {
                        "type": "float",
                        "metadata": {
                            "ScanArgument": {
                                "display_name": "Center Motor 1",
                                "units": None,
                                "reference_units": "motor_1",
                            }
                        },
                    }
                },
            },
            {
                "name": "center_2",
                "kind": "KEYWORD_ONLY",
                "default": 0,
                "annotation": {
                    "Annotated": {
                        "type": "float",
                        "metadata": {
                            "ScanArgument": {
                                "display_name": "Center Motor 2",
                                "units": None,
                                "reference_units": "motor_2",
                            }
                        },
                    }
                },
            },
        ],
    }
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(),
        AvailableResourceMessage(resource={"round_scan": scan_info}),
    )

    widget = ScanControl(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    widget.comboBox_scan_selection.setCurrentText("round_scan")

    motor_box = widget.kwarg_boxes[0]
    ring_box = widget.kwarg_boxes[1]

    assert "Units from: motor_1" in ring_box.widgets[0].toolTip()
    assert ring_box.widgets[0].suffix() == ""

    with patch.object(mocked_client.device_manager.devices.samx, "egu", return_value="mm"):
        WidgetIO.set_value(motor_box.widgets[0], "samx")

    assert ring_box.widgets[0].suffix() == " mm"
    assert ring_box.widgets[1].suffix() == " mm"
    assert ring_box.widgets[2].suffix() == " mm"
    assert ring_box.widgets[3].suffix() == ""
    assert "Units: mm" in ring_box.widgets[0].toolTip()

    motor_box.widgets[0].setCurrentText("not_a_device")

    assert ring_box.widgets[0].suffix() == ""
    assert ring_box.widgets[1].suffix() == ""
    assert ring_box.widgets[2].suffix() == ""
    assert "Units from: motor_1" in ring_box.widgets[0].toolTip()


def test_current_scan(scan_control, mocked_client):
    current_scan = scan_control.current_scan
    wrong_scan = "error_scan"
    scan_control.current_scan = wrong_scan
    assert scan_control.current_scan == current_scan
    new_scan = "grid_scan" if current_scan == "line_scan" else "line_scan"
    scan_control.current_scan = new_scan
    assert scan_control.current_scan == new_scan


def test_scan_switch_runs_cleanup_on_previous_inputs(scan_control):
    """Switching scans tears down the old group boxes; the BECWidget inputs inside
    (device comboboxes) must go through close() so their cleanup runs, instead of
    being destroyed by deleteLater() without cleanup."""
    scan_control.comboBox_scan_selection.setCurrentText("line_scan")
    old_inputs = [w for w in scan_control.arg_box.widgets if hasattr(w, "_destroyed")]
    assert old_inputs, "line_scan arg box should contain at least one BECWidget input"
    assert all(not w._destroyed for w in old_inputs)

    scan_control.comboBox_scan_selection.setCurrentText("grid_scan")

    # closeEvent ran cleanup and flagged each old input as destroyed
    assert all(w._destroyed for w in old_inputs)
    register = scan_control.rpc_register
    assert all(not register.object_is_registered(w) for w in old_inputs)


@pytest.mark.parametrize("scan_name", ["line_scan", "grid_scan"])
def test_on_scan_selected(scan_control, scan_name):
    expected_scan_info = available_scans_message.resource[scan_name]
    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Check arg_box labels and widgets
    inputs_per_bundle = len(expected_scan_info["arg_input"])
    for index, (arg_key, arg_value) in enumerate(expected_scan_info["arg_input"].items()):
        assert scan_control.arg_box.label_texts()[index].lower() == arg_key

        for row in range(expected_scan_info["arg_bundle_size"]["min"]):
            widget = scan_control.arg_box.get_bundle_widgets(row)[index]
            expected_widget_type = scan_control.arg_box.WIDGET_HANDLER.get(arg_value, None)
            assert isinstance(widget, expected_widget_type)  # Confirm the widget type matches
            if isinstance(widget, DeviceComboBox):
                assert widget.currentText() == ""
                assert widget.autocomplete is True
                assert widget.include_signals_with_write_access is True
                assert "samx" in widget.devices
                assert (
                    "async_device" in widget.devices
                )  # async device should also be present in the device list
    assert len(scan_control.arg_box.widgets) == (
        inputs_per_bundle * expected_scan_info["arg_bundle_size"]["min"]
    )

    # Check kwargs boxes
    kwargs_group = [param for param in expected_scan_info["gui_config"]["kwarg_groups"]]
    print(kwargs_group)

    for kwarg_box, kwarg_group in zip(scan_control.kwarg_boxes, kwargs_group):
        assert kwarg_box.title() == kwarg_group["name"]
        for index, kwarg_info in enumerate(kwarg_group["inputs"]):
            widget = kwarg_box.widgets[index]
            assert kwarg_box.label_for_widget(widget).text() == kwarg_info["display_name"]
            if isinstance(kwarg_info["type"], dict) and "Literal" in kwarg_info["type"]:
                expected_widget_type = kwarg_box.WIDGET_HANDLER.get("dict", None)
            else:
                expected_widget_type = kwarg_box.WIDGET_HANDLER.get(kwarg_info["type"], None)
            assert isinstance(widget, expected_widget_type)


@pytest.mark.parametrize("scan_name", ["line_scan", "grid_scan"])
def test_add_remove_bundle(scan_control, scan_name, qtbot):
    expected_scan_info = available_scans_message.resource[scan_name]
    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Initial number of args row
    initial_num_of_rows = scan_control.arg_box.count_arg_rows()

    assert initial_num_of_rows == expected_scan_info["arg_bundle_size"]["min"]

    scan_control.arg_box.button_add_bundle.click()
    scan_control.arg_box.button_add_bundle.click()

    if expected_scan_info["arg_bundle_size"]["max"] is None:
        assert scan_control.arg_box.count_arg_rows() == initial_num_of_rows + 2

    # Remove one bundle
    scan_control.arg_box.button_remove_bundle.click()
    qtbot.wait(200)

    assert scan_control.arg_box.count_arg_rows() == initial_num_of_rows + 1


def test_run_line_scan_with_parameters(scan_control, mocked_client):
    scan_name = "line_scan"
    kwargs = {"exp_time": 0.1, "steps": 10, "relative": True, "burst_at_each_point": 1}
    args = {"device": "samx", "start": -5, "stop": 5}
    mock_slot = MagicMock()
    scan_control.scan_args.connect(mock_slot)

    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Set kwargs in the UI
    for kwarg_box in scan_control.kwarg_boxes:
        for widget in kwarg_box.widgets:
            if widget.arg_name in kwargs:
                WidgetIO.set_value(widget, kwargs[widget.arg_name])

    # Set args in the UI
    for widget in scan_control.arg_box.widgets:
        if widget.arg_name in args:
            WidgetIO.set_value(widget, args[widget.arg_name])

    # Mock the scan function
    mocked_scan_function = MagicMock()
    setattr(mocked_client.scans, scan_name, mocked_scan_function)

    # Run the scan
    scan_control.button_run_scan.click()

    # Retrieve the actual arguments passed to the mock
    called_args, called_kwargs = mocked_scan_function.call_args

    # Check if the scan function was called correctly
    expected_device = mocked_client.device_manager.devices.samx
    expected_args_list = [expected_device, args["start"], args["stop"]]
    assert called_args == tuple(expected_args_list)
    assert called_kwargs == kwargs | {
        "metadata": {"sample_name": "", "comment": "", "scan_name": "line_scan"}
    }

    # Check the emitted signal
    mock_slot.assert_called_once()
    emitted_args_list = mock_slot.call_args[0][0]
    assert len(emitted_args_list) == 3  # Expected 3 arguments for line_scan
    assert emitted_args_list == [expected_device, -5.0, 5.0]


def test_run_grid_scan_with_parameters(scan_control, mocked_client):
    scan_name = "grid_scan"
    kwargs = {"exp_time": 0.2, "settling_time": 0.1, "relative": False, "burst_at_each_point": 2}
    args_row1 = {"device": "samx", "start": -10, "stop": 10, "steps": 20}
    args_row2 = {"device": "samy", "start": -5, "stop": 5, "steps": 10}
    mock_slot = MagicMock()
    scan_control.scan_args.connect(mock_slot)

    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Ensure there are two rows in the arg_box
    current_rows = scan_control.arg_box.count_arg_rows()
    required_rows = 2
    while current_rows < required_rows:
        scan_control.arg_box.add_widget_bundle()
        current_rows += 1

    # Set kwargs in the UI
    for kwarg_box in scan_control.kwarg_boxes:
        for widget in kwarg_box.widgets:
            if widget.arg_name in kwargs:
                WidgetIO.set_value(widget, kwargs[widget.arg_name])

    # Set args in the UI for both rows
    arg_widgets = scan_control.arg_box.widgets  # This is a flat list of widgets
    num_columns = len(scan_control.arg_box.inputs)
    num_rows = int(len(arg_widgets) / num_columns)
    assert num_rows == required_rows  # We expect 2 rows for grid_scan

    # Set values for first row
    for i in range(num_columns):
        widget = arg_widgets[i]
        arg_name = widget.arg_name
        if arg_name in args_row1:
            WidgetIO.set_value(widget, args_row1[arg_name])

    # Set values for second row
    for i in range(num_columns):
        widget = arg_widgets[num_columns + i]  # Next row
        arg_name = widget.arg_name
        if arg_name in args_row2:
            WidgetIO.set_value(widget, args_row2[arg_name])

    # Mock the scan function
    mocked_scan_function = MagicMock()
    setattr(mocked_client.scans, scan_name, mocked_scan_function)

    # Run the scan
    scan_control.button_run_scan.click()

    # Retrieve the actual arguments passed to the mock
    called_args, called_kwargs = mocked_scan_function.call_args

    # Check if the scan function was called correctly
    expected_device1 = mocked_client.device_manager.devices.samx
    expected_device2 = mocked_client.device_manager.devices.samy
    expected_args_list = [
        expected_device1,
        args_row1["start"],
        args_row1["stop"],
        args_row1["steps"],
        expected_device2,
        args_row2["start"],
        args_row2["stop"],
        args_row2["steps"],
    ]
    assert called_args == tuple(expected_args_list)
    assert called_kwargs == kwargs | {
        "metadata": {"sample_name": "", "comment": "", "scan_name": "grid_scan"},
        "optim_trajectory": None,
    }

    # Check the emitted signal
    mock_slot.assert_called_once()
    emitted_args_list = mock_slot.call_args[0][0]
    assert len(emitted_args_list) == 8  # Expected 8 arguments for grid_scan
    assert emitted_args_list == expected_args_list


def test_changing_scans_remember_parameters(scan_control, mocked_client):
    scan_name = "line_scan"
    kwargs = {"exp_time": 0.1, "steps": 10, "relative": True, "burst_at_each_point": 1}
    args = {"device": "samx", "start": -5, "stop": 5}

    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Set kwargs in the UI
    for kwarg_box in scan_control.kwarg_boxes:
        for widget in kwarg_box.widgets:
            for key, value in kwargs.items():
                if widget.arg_name == key:
                    WidgetIO.set_value(widget, value)
                    break
    # Set args in the UI
    for widget in scan_control.arg_box.widgets:
        for key, value in args.items():
            if widget.arg_name == key:
                WidgetIO.set_value(widget, value)
                break

    scan_control.save_current_scan_parameters()

    # Change the scan
    new_scan_name = "grid_scan"
    scan_control.comboBox_scan_selection.setCurrentText(new_scan_name)

    # Check if kwargs are same as in the line_scan
    grid_args, grid_kwargs = scan_control.get_scan_parameters(bec_object=False)
    assert grid_kwargs["exp_time"] == kwargs["exp_time"]
    assert grid_kwargs["relative"] == kwargs["relative"]
    assert grid_kwargs["burst_at_each_point"] == kwargs["burst_at_each_point"]


def test_scan_selection_does_not_fetch_last_scan_parameters(
    scan_control, mocked_client, monkeypatch
):
    xread = MagicMock(wraps=mocked_client.connector.xread)
    monkeypatch.setattr(mocked_client.connector, "xread", xread)

    scan_control.comboBox_scan_selection.setCurrentText("line_scan")
    assert scan_control.comboBox_scan_selection.currentText() == "line_scan"

    scan_control.comboBox_scan_selection.setCurrentText("grid_scan")

    xread.assert_not_called()


def test_restore_last_scan_parameters_button_fetches_on_demand(
    scan_control, mocked_client, monkeypatch
):
    xread = MagicMock(wraps=mocked_client.connector.xread)
    monkeypatch.setattr(mocked_client.connector, "xread", xread)

    scan_control.comboBox_scan_selection.setCurrentText("grid_scan")
    scan_control.comboBox_scan_selection.setCurrentText("line_scan")
    xread.assert_not_called()

    scan_control.last_scan_button.click()

    xread.assert_called_once_with(
        MessageEndpoints.scan_history(), from_start=True, user_id=scan_control.object_name
    )
    args, kwargs = scan_control.get_scan_parameters(bec_object=False)
    assert args == ["samx", 0.0, 2.0]
    assert kwargs["steps"] == 10
    assert kwargs["relative"] is False
    assert kwargs["exp_time"] == 2


def test_get_scan_parameters_from_redis(scan_control):
    scan_name = "line_scan"
    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    scan_control.last_scan_button.click()

    args, kwargs = scan_control.get_scan_parameters(bec_object=False)

    assert args == ["samx", 0.0, 2.0]
    assert kwargs == {
        "steps": 10,
        "relative": False,
        "exp_time": 2.0,
        "burst_at_each_point": 1,
        "metadata": {"comment": "", "sample_name": "", "scan_name": "line_scan"},
    }


TEST_MD = {
    "comment": "",
    "sample_name": "Test Sample",
    "scan_name": "grid_scan",
    "test key 1": "test value 1",
    "test key 2": "test value 2",
}
TEST_TABLE_ENTRY = [["test key 1", "test value 1"], ["test key 2", "test value 2"]]


def test_scan_metadata_is_updated_even_without_default_form_changes(
    scan_control: ScanControl, qtbot
):
    assert scan_control._metadata_form._scan_name == "line_scan"
    scan_control.comboBox_scan_selection.setCurrentText("grid_scan")
    assert scan_control._metadata_form._scan_name == "grid_scan"
    scan_control._metadata_form._additional_metadata._add_button.click()
    qtbot.wait(100)
    table_model = scan_control._metadata_form._additional_metadata._table_model
    model_key = table_model.index(0, 0, QModelIndex())
    table_model.setData(model_key, "test key 1", Qt.EditRole)
    model_value = model_key.siblingAtColumn(1)
    table_model.setData(model_value, "test value 1", Qt.EditRole)
    assert scan_control._metadata_form._additional_metadata.dump_dict() == {
        "test key 1": "test value 1"
    }
    assert scan_control._scan_metadata == {
        "comment": "",
        "sample_name": "",
        "scan_name": "grid_scan",
        "test key 1": "test value 1",
    }


def test_scan_metadata_is_connected(scan_control):
    assert scan_control._metadata_form._scan_name == "line_scan"
    scan_control.comboBox_scan_selection.setCurrentText("grid_scan")
    assert scan_control._metadata_form._scan_name == "grid_scan"
    sample_name = scan_control._metadata_form._form_grid.layout().itemAtPosition(2, 1).widget()
    assert isinstance(sample_name, StrFormItem)
    sample_name._main_widget.setText("Test Sample")

    scan_control._metadata_form._additional_metadata._table_model._data = TEST_TABLE_ENTRY
    scan_control._metadata_form.validate_form()
    assert scan_control._scan_metadata == TEST_MD


def test_scan_metadata_is_passed_to_scan_function(scan_control: ScanControl):
    scan_control.comboBox_scan_selection.setCurrentText("grid_scan")

    sample_name = scan_control._metadata_form._form_grid.layout().itemAtPosition(2, 1).widget()
    sample_name._main_widget.setText("Test Sample")
    scan_control._metadata_form._additional_metadata._table_model._data = TEST_TABLE_ENTRY
    scan_control._metadata_form.validate_form()

    assert scan_control._scan_metadata == TEST_MD

    scans = SimpleNamespace(grid_scan=MagicMock())
    with (
        patch.object(scan_control, "scans", scans),
        patch.object(scan_control, "get_scan_parameters", lambda: ((), {"metadata": TEST_MD})),
    ):
        scan_control.run_scan()
    scans.grid_scan.assert_called_once_with(metadata=TEST_MD)


def test_restore_parameters_with_fewer_arg_bundles(scan_control):
    """
    Ensure that when more argument bundles are present than exist in the
    stored history, restoring parameters regenerates the arg box to the
    correct (smaller) size and sets the values properly.
    This is a check for the previous infinite loop bug.
    """
    # Select the scan type that has history with only one arg bundle
    scan_control.comboBox_scan_selection.setCurrentText("line_scan")

    # Manually add bundles so we end up with three rows
    while scan_control.arg_box.count_arg_rows() < 3:
        scan_control.arg_box.add_widget_bundle()
    assert scan_control.arg_box.count_arg_rows() == 3

    # Trigger restore of parameters from history
    scan_control.last_scan_button.click()

    # After restore, arg_box should have only one bundle (the history size)
    assert scan_control.arg_box.count_arg_rows() == 1

    # Verify that the restored parameter values match the history
    args, kwargs = scan_control.get_scan_parameters(bec_object=False)
    assert args == ["samx", 0.0, 2.0]
    assert kwargs["steps"] == 10
