# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from unittest import mock

import numpy as np
import pytest
from bec_lib import messages, RedisConnector
from pytestqt import qtbot
import threading

from bec_widgets.examples.stream_plot.stream_plot import StreamPlot


@pytest.fixture(scope="function")
def stream_app(qtbot):
    """Helper function to set up the StreamPlot widget."""
    client = mock.MagicMock()
    widget = StreamPlot(client=client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_roi_signals_emitted(qtbot, stream_app):
    region = (0.1, 0.9)
    with qtbot.waitSignal(stream_app.roi_signal, timeout=1000) as blocker:
        stream_app.roi_signal.emit(region)
    assert blocker.signal_triggered
    assert blocker.args == [region]


def test_update_signals_emitted(qtbot, stream_app):
    # Mimic data coming from the data stream
    stream_app.plotter_data_x = [list(range(10))]  # Replace with the actual x data
    stream_app.plotter_data_y = [list(range(10))]  # Replace with the actual y data

    # Initialize curves
    stream_app.init_curves()

    with qtbot.waitSignal(stream_app.update_signal, timeout=1000) as blocker:
        stream_app.update_signal.emit()
    assert blocker.signal_triggered


def test_ui_initialization(qtbot, stream_app):
    """Checking the UI creation."""

    # Check if UI elements are initialized correctly
    assert stream_app.label_plot is not None
    assert stream_app.label_plot_moved is not None
    assert stream_app.label_plot_clicked is not None
    assert stream_app.label_image_moved is not None
    assert stream_app.label_image_clicked is not None

    # Check if plots are initialized correctly
    assert stream_app.plot is not None
    assert stream_app.plot_image is not None

    # Check if ROI selector is initialized correctly
    assert stream_app.roi_selector is not None


def test_1d_plotting_data(qtbot, stream_app):
    # Set up some mock data
    x_data = [list(range(10))]
    y_data = [list(range(10))]

    # Manually set the data attributes
    stream_app.plotter_data_x = x_data
    stream_app.plotter_data_y = y_data
    stream_app.y_value_list = ["Curve 1"]

    # Initialize curves and update the plot
    stream_app.init_curves()
    stream_app.update()  # This should update the plot with the new data

    # Check the data on the plot
    for idx, curve in enumerate(stream_app.curves):
        np.testing.assert_array_equal(curve.xData, x_data[0])  # Access the first list of x_data
        np.testing.assert_array_equal(
            curve.yData, y_data[idx]
        )  # Access the list of y_data for each curve without additional indexing


def test_flip_even_rows(qtbot, stream_app):
    # Create a numpy array with some known data
    original_array = np.array(
        [
            [1, 2, 3, 4, 5],
            [6, 7, 8, 9, 10],
            [11, 12, 13, 14, 15],
            [16, 17, 18, 19, 20],
        ]
    )

    # Call flip_even_rows on the original array
    flipped_array = stream_app.flip_even_rows(original_array)

    # Expected array flipped along the rows with even indices
    expected_array = np.array(
        [
            [1, 2, 3, 4, 5],
            [10, 9, 8, 7, 6],
            [11, 12, 13, 14, 15],
            [20, 19, 18, 17, 16],
        ]
    )

    # Check that flip_even_rows returned the expected result
    np.testing.assert_array_equal(flipped_array, expected_array)


def test_on_dap_update(qtbot, stream_app):
    """2D image rendering by dap update"""
    # Create some mock data to be "received" by the slot
    data_dict = {"data": {"z": np.random.rand(10, 10)}}
    metadata_dict = {}

    # Trigger the slot
    stream_app.on_dap_update(data_dict, metadata_dict)

    # Apply the same transformation to the test data
    expected_data = stream_app.flip_even_rows(data_dict["data"]["z"])

    # Now check the state of the StreamPlot object
    # For example, check the data of the image plot:
    np.testing.assert_array_equal(stream_app.img.image, expected_data)


####################
# Until Here
####################

# def test_new_proj(qtbot, stream_app): #TODO this test is not working, does it make sense testing even?
#     # Create some mock content to be "received" by the slot
#     content_dict = {"signals": {"proj_nr": 1}}
#     metadata_dict = {}
#
#     # Manually create some mock data that new_proj would work with
#     # This step may need to be adjusted to fit the actual behavior of new_proj
#     mock_data = {
#         "q": np.array([1, 2, 3, 4, 5]),
#         "norm_sum": np.array([6, 7, 8, 9, 10]),
#         "metadata": "some_metadata",
#     }
#
#     # Assume the RedisConnector client would return this data when new_proj is called
#     mock_message = mock.MagicMock(spec=messages.DeviceMessage)
#     mock_message.__getitem__.side_effect = lambda key: mock_data[key]
#     stream_app.client.producer.get = mock.MagicMock(return_value=mock_message.dumps())
#
#     # Trigger the slot
#     stream_app.new_proj(content_dict, metadata_dict)
#
#     # Now check the state of the StreamPlot object
#     # For example, check that the plotter_data_x attribute was updated correctly:
#     np.testing.assert_array_equal(stream_app.plotter_data_x, [mock_data["q"]])
#     assert stream_app._current_proj == 1
#     assert stream_app._current_q == mock_data["q"]
#     assert stream_app._current_norm == mock_data["norm_sum"]
#     assert stream_app._current_metadata == mock_data["metadata"]


# def test_connection_creation(qtbot, stream_app): #TODO maybe test connections in a different way?
#     assert isinstance(stream_app.producer, RedisConnector)
#     assert isinstance(stream_app.data_retriever, threading.Thread)
#     assert stream_app.data_retriever.is_alive()
