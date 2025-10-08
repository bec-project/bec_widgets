from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
from bec_widgets.widgets.editors.monaco.scan_control_dialog import ScanControlDialog

from .client_mocks import mocked_client
from .test_scan_control import available_scans_message


@pytest.fixture
def monaco_widget(qtbot, mocked_client):
    widget = MonacoWidget(client=mocked_client)
    mocked_client.connector.set(MessageEndpoints.available_scans(), available_scans_message)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_monaco_widget_set_text(monaco_widget: MonacoWidget, qtbot):
    """
    Test that the MonacoWidget can set text correctly.
    """
    test_text = "Hello, Monaco!"
    monaco_widget.set_text(test_text)
    qtbot.waitUntil(lambda: monaco_widget.get_text() == test_text, timeout=1000)
    assert monaco_widget.get_text() == test_text


def test_monaco_widget_readonly(monaco_widget: MonacoWidget, qtbot):
    """
    Test that the MonacoWidget can be set to read-only mode.
    """
    monaco_widget.set_text("Initial text")
    qtbot.waitUntil(lambda: monaco_widget.get_text() == "Initial text", timeout=1000)
    monaco_widget.set_readonly(True)

    with pytest.raises(ValueError):
        monaco_widget.set_text("This should not change")

    monaco_widget.set_readonly(False)  # Set back to editable
    qtbot.wait(100)
    monaco_widget.set_text("Attempting to change text")
    qtbot.waitUntil(lambda: monaco_widget.get_text() == "Attempting to change text", timeout=1000)
    assert monaco_widget.get_text() == "Attempting to change text"


def test_monaco_widget_show_scan_control_dialog(monaco_widget: MonacoWidget, qtbot):
    """
    Test that the MonacoWidget can show the scan control dialog.
    """

    with mock.patch.object(monaco_widget, "_run_dialog_and_insert_code") as mock_run_dialog:
        monaco_widget._show_scan_control_dialog()
        mock_run_dialog.assert_called_once()


def test_monaco_widget_get_scan_control_code(monaco_widget: MonacoWidget, qtbot, mocked_client):
    """
    Test that the MonacoWidget can get scan control code from the dialog.
    """
    mocked_client.connector.set(MessageEndpoints.available_scans(), available_scans_message)

    scan_control_dialog = ScanControlDialog(client=mocked_client)
    qtbot.addWidget(scan_control_dialog)
    qtbot.waitExposed(scan_control_dialog)
    qtbot.wait(300)

    scan_control = scan_control_dialog.scan_control
    scan_name = "grid_scan"
    kwargs = {"exp_time": 0.2, "settling_time": 0.1, "relative": False, "burst_at_each_point": 2}
    args_row1 = {"device": "samx", "start": -10, "stop": 10, "steps": 20}
    args_row2 = {"device": "samy", "start": -5, "stop": 5, "steps": 10}
    mock_slot = mock.MagicMock()

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

    scan_control_dialog.accept()
    out = scan_control_dialog.get_scan_code()

    expected_code = "scans.grid_scan(dev.samx, -10.0, 10.0, 20, dev.samy, -5.0, 5.0, 10, exp_time=0.2, settling_time=0.1, burst_at_each_point=2, relative=False, optim_trajectory=None)"
    assert out == expected_code
