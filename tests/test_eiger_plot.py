import json
from unittest.mock import MagicMock, patch
import numpy as np
import pyqtgraph as pg
import pytest
import zmq
from bec_widgets.examples.eiger_plot.eiger_plot import EigerPlot


# Common fixture for all tests
@pytest.fixture
def eiger_plot_instance(qtbot):
    widget = EigerPlot()
    qtbot.addWidget(widget)
    return widget


@pytest.mark.parametrize(
    "fft_checked, rotation_index, transpose_checked, log_checked, expected_image",
    [
        (False, 0, False, False, np.array([[2, 1], [1, 5]], dtype=float)),  # just mask
        (False, 1, False, False, np.array([[1, 5], [2, 1]], dtype=float)),  # 90 deg rotation
        (False, 2, False, False, np.array([[5, 1], [1, 2]], dtype=float)),  # 180 deg rotation
        (False, 0, True, False, np.array([[2, 1], [1, 5]], dtype=float)),  # transposed
        (False, 0, False, True, np.array([[0.30103, 0.0], [0.0, 0.69897]], dtype=float)),  # log
        (True, 0, False, False, np.array([[5.0, 3.0], [3.0, 9.0]], dtype=float)),  # FFT
    ],
)
def test_on_image_update(
    qtbot,
    eiger_plot_instance,
    fft_checked,
    rotation_index,
    transpose_checked,
    log_checked,
    expected_image,
):
    # Initialize image and mask
    eiger_plot_instance.image = np.array([[1, 2], [3, 4]], dtype=float)
    eiger_plot_instance.mask = np.array([[0, 1], [1, 0]], dtype=float)

    # Mock UI elements
    eiger_plot_instance.checkBox_FFT = MagicMock()
    eiger_plot_instance.checkBox_FFT.isChecked.return_value = fft_checked
    eiger_plot_instance.comboBox_rotation = MagicMock()
    eiger_plot_instance.comboBox_rotation.currentIndex.return_value = rotation_index
    eiger_plot_instance.checkBox_transpose = MagicMock()
    eiger_plot_instance.checkBox_transpose.isChecked.return_value = transpose_checked
    eiger_plot_instance.checkBox_log = MagicMock()
    eiger_plot_instance.checkBox_log.isChecked.return_value = log_checked
    eiger_plot_instance.imageItem = MagicMock()

    # Call the method
    eiger_plot_instance.on_image_update()

    # Validate the transformations
    np.testing.assert_array_almost_equal(eiger_plot_instance.image, expected_image, decimal=5)

    # Validate that setImage was called
    eiger_plot_instance.imageItem.setImage.assert_called_with(
        eiger_plot_instance.image, autoLevels=False
    )


def test_init_ui(eiger_plot_instance):
    assert isinstance(eiger_plot_instance.plot_item, pg.PlotItem)
    assert isinstance(eiger_plot_instance.imageItem, pg.ImageItem)
    assert isinstance(eiger_plot_instance.hist, pg.HistogramLUTItem)


def test_start_zmq_consumer(eiger_plot_instance):
    with patch("threading.Thread") as MockThread:
        eiger_plot_instance.start_zmq_consumer()
        MockThread.assert_called_once()
        MockThread.return_value.start.assert_called_once()


def test_zmq_consumer(eiger_plot_instance, qtbot):
    fake_meta = json.dumps({"type": "int32", "shape": (2, 2)}).encode("utf-8")
    fake_data = np.array([[1, 2], [3, 4]], dtype="int32").tobytes()

    with patch("zmq.Context") as MockContext:
        MockContext.reset_mock()  # Reset the mock here

        # Mocking zmq socket and its methods
        mock_socket = MagicMock()
        MockContext().socket.return_value = mock_socket
        mock_socket.recv_multipart.side_effect = [[fake_meta, fake_data], Exception("Break loop")]

        # Mocking the update_signal to check if it gets emitted
        eiger_plot_instance.update_signal = MagicMock()

        try:
            # Run the method under test
            eiger_plot_instance.zmq_consumer()
        except Exception as e:
            # Ensure the loop was broken by our mocked exception
            assert str(e) == "Break loop"

        # Check if zmq methods are called
        # MockContext.assert_called_once()
        assert MockContext.call_count == 2  # TODO why 2?
        mock_socket.connect.assert_called_with("tcp://129.129.95.38:20000")
        mock_socket.setsockopt_string.assert_called_with(zmq.SUBSCRIBE, "")
        mock_socket.recv_multipart.assert_called()

        # Check if update_signal was emitted
        eiger_plot_instance.update_signal.emit.assert_called_once()

        # Validate the image data
        np.testing.assert_array_equal(
            eiger_plot_instance.image, np.array([[1, 2], [3, 4]], dtype="int32")
        )
