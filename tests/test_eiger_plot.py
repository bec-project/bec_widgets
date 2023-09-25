import pytest
from unittest.mock import MagicMock
import numpy as np
from bec_widgets.examples.eiger_plot.eiger_plot import EigerPlot


# Common fixture for all tests
@pytest.fixture
def eiger_plot_instance(qtbot):
    widget = EigerPlot()
    qtbot.addWidget(widget)
    return widget


# Tests for on_image_update method
class TestOnImageUpdate:
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
        self,
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
