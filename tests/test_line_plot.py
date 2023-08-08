from unittest import mock

import numpy as np
from pytestqt import qtbot

from bec_widgets import line_plot


def test_line_plot_emits_no_signal(qtbot):
    """Test LinePlot emits no signal when only one data entry is present."""

    y_value_list = ["y1", "y2"]
    plot = line_plot.BasicPlot(y_value_list=y_value_list)
    data = {
        "data": {
            "x": {"x": {"value": 1}},
            "y1": {"y1": {"value": 1}},
            "y2": {"y2": {"value": 3}},
        }
    }
    metadata = {"scanID": "test", "scan_number": 1, "scan_report_devices": ["x"]}
    with mock.patch("bec_widgets.line_plot.BECClient") as mock_client:
        with mock.patch.object(plot, "update_signal") as mock_update_signal:
            plot(data=data, metadata=metadata)
            mock_update_signal.emit.assert_not_called()


def test_line_plot_emits_signal(qtbot):
    """Test LinePlot emits signal."""

    y_value_list = ["y1", "y2"]
    plot = line_plot.BasicPlot(y_value_list=y_value_list)
    data = {
        "data": {
            "x": {"x": {"value": 1}},
            "y1": {"y1": {"value": 1}},
            "y2": {"y2": {"value": 3}},
        }
    }
    plotter_data_y = [[1, 1], [3, 3]]
    metadata = {"scanID": "test", "scan_number": 1, "scan_report_devices": ["x"]}
    with mock.patch("bec_widgets.line_plot.BECClient") as mock_client:
        # mock_client.device_manager.devices.keys.return_value = ["y1"]
        with mock.patch.object(plot, "update_signal") as mock_update_signal:
            mock_update_signal.emit()
            plot(data=data, metadata=metadata)
            plot(data=data, metadata=metadata)
            mock_update_signal.emit.assert_called()
            # TODO allow mock_client to create return values for device_manager_devices
            # assert plot.plotter_data_y == plotter_data_y


def test_line_plot_raise_warning_wrong_signal_request(qtbot):
    """Test LinePlot raises warning and skips signal when entry not present in data."""

    y_value_list = ["y1", "y22"]
    plot = line_plot.BasicPlot(y_value_list=y_value_list)
    data = {
        "data": {
            "x": {"x": {"value": [1, 2, 3, 4, 5]}},
            "y1": {"y1": {"value": [1, 2, 3, 4, 5]}},
            "y2": {"y2": {"value": [1, 2, 3, 4, 5]}},
        }
    }
    metadata = {"scanID": "test", "scan_number": 1, "scan_report_devices": ["x"]}
    with mock.patch("bec_widgets.line_plot.BECClient") as mock_client:
        # TODO fix mock_client
        mock_dict = {"y1": [1, 2]}
        mock_client().device_manager.devices.__contains__.side_effect = mock_dict.__contains__

        # = {"y1": [1, 2]}
        with mock.patch.object(plot, "update_signal") as mock_update_signal:
            mock_update_signal.emit()
            plot(data=data, metadata=metadata)
            assert plot.y_value_list == ["y1"]


def test_line_plot_update(qtbot):
    """Test LinePlot update."""

    y_value_list = ["y1", "y2"]
    plot = line_plot.BasicPlot(y_value_list=y_value_list)
    plot.label_bottom = "x"
    plot.label_left = f"{', '.join(y_value_list)}"
    plot.plotter_data_x = [1, 2, 3, 4, 5]
    plot.plotter_data_y = [[1, 2, 3, 4, 5], [3, 4, 5, 6, 7]]
    plot.update()

    assert all(plot.curves[0].getData()[0] == np.array([1, 2, 3, 4, 5]))
    assert all(plot.curves[0].getData()[1] == np.array([1, 2, 3, 4, 5]))
    assert all(plot.curves[1].getData()[1] == np.array([3, 4, 5, 6, 7]))


# TODO Outputting the wrong data, e.g. motor is not in list of devices
def test_line_plot_update(qtbot):
    """Test LinePlot update."""

    y_value_list = ["y1", "y2"]
    plot = line_plot.BasicPlot(y_value_list=y_value_list)
    plot.label_bottom = "x"
    plot.label_left = f"{', '.join(y_value_list)}"
    plot.plotter_data_x = [1, 2, 3, 4, 5]
    plot.plotter_data_y = [[1, 2, 3, 4, 5], [3, 4, 5, 6, 7]]
    plot.update()

    assert all(plot.curves[0].getData()[0] == np.array([1, 2, 3, 4, 5]))
    assert all(plot.curves[0].getData()[1] == np.array([1, 2, 3, 4, 5]))
    assert all(plot.curves[1].getData()[1] == np.array([3, 4, 5, 6, 7]))


def test_line_plot_mouse_moved(qtbot):
    """Test LinePlot mouse_moved."""

    y_value_list = ["y1", "y2"]
    plot = line_plot.BasicPlot(y_value_list=y_value_list)
    plot.plotter_data_x = [1, 2, 3, 4, 5]
    plot.plotter_data_y = [[1, 2, 3, 4, 5], [3, 4, 5, 6, 7]]
    plot.precision = 3
    string_cap = 10
    x_data = f"{3:.{plot.precision}f}"
    y_data = f"{3:.{plot.precision}f}"
    output_string = "".join(
        [
            "Mouse cursor",
            "\n",
            f"{y_value_list[0]}",
            "\n",
            f"X_data:   {x_data:>{string_cap}}",
            "\n",
            f"Y_data: {y_data:>{string_cap}}",
        ]
    )
    x_data = f"{3:.{plot.precision}f}"
    y_data = f"{5:.{plot.precision}f}"
    output_string = "".join(
        [
            output_string,
            "\n",
            f"{y_value_list[1]}",
            "\n",
            f"X_data:   {x_data:>{string_cap}}",
            "\n",
            f"Y_data: {y_data:>{string_cap}}",
        ]
    )
    with mock.patch.object(
        plot, "plot"
    ) as mock_plot:  # TODO change test to simulate QTable instead of QLabel
        mock_plot.sceneBoundingRect.contains.return_value = True
        mock_plot.vb.mapSceneToView((20, 10)).x.return_value = 2.8
        plot.mouse_moved((20, 10))
        assert plot.mouse_box_data.text() == output_string
