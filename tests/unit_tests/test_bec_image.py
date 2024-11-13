# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import numpy as np
from bec_lib import messages

from bec_widgets.widgets.containers.figure import BECFigure

from .client_mocks import mocked_client
from .conftest import create_widget


def test_on_image_update(qtbot, mocked_client):
    bec_image_show = create_widget(qtbot, BECFigure, client=mocked_client).image("eiger")
    data = np.random.rand(100, 100)
    msg = messages.DeviceMonitor2DMessage(device="eiger", data=data, metadata={"scan_id": "12345"})
    bec_image_show.on_image_update(msg.content, msg.metadata)
    img = bec_image_show.images[0]
    assert np.array_equal(img.get_data(), data)


def test_autorange_on_image_update(qtbot, mocked_client):
    bec_image_show = create_widget(qtbot, BECFigure, client=mocked_client).image("eiger")
    # Check if autorange mode "mean" works, should be default
    data = np.random.rand(100, 100)
    msg = messages.DeviceMonitor2DMessage(device="eiger", data=data, metadata={"scan_id": "12345"})
    bec_image_show.on_image_update(msg.content, msg.metadata)
    img = bec_image_show.images[0]
    assert np.array_equal(img.get_data(), data)
    vmin = max(np.mean(data) - 2 * np.std(data), 0)
    vmax = np.mean(data) + 2 * np.std(data)
    assert np.isclose(img.color_bar.getLevels(), (vmin, vmax), rtol=(1e-5, 1e-5)).all()
    # Test general update with autorange True, mode "max"
    bec_image_show.set_autorange_mode("max")
    bec_image_show.on_image_update(msg.content, msg.metadata)
    img = bec_image_show.images[0]
    vmin = np.min(data)
    vmax = np.max(data)
    assert np.array_equal(img.get_data(), data)
    assert np.isclose(img.color_bar.getLevels(), (vmin, vmax), rtol=(1e-5, 1e-5)).all()
    # Change the input data, and switch to autorange False, colormap levels should stay untouched
    data *= 100
    msg = messages.DeviceMonitor2DMessage(device="eiger", data=data, metadata={"scan_id": "12345"})
    bec_image_show.set_autorange(False)
    bec_image_show.on_image_update(msg.content, msg.metadata)
    img = bec_image_show.images[0]
    assert np.array_equal(img.get_data(), data)
    assert np.isclose(img.color_bar.getLevels(), (vmin, vmax), rtol=(1e-3, 1e-3)).all()
    # Reactivate autorange, should now scale the new data
    bec_image_show.set_autorange(True)
    bec_image_show.set_autorange_mode("mean")
    bec_image_show.on_image_update(msg.content, msg.metadata)
    img = bec_image_show.images[0]
    vmin = max(np.mean(data) - 2 * np.std(data), 0)
    vmax = np.mean(data) + 2 * np.std(data)
    assert np.isclose(img.color_bar.getLevels(), (vmin, vmax), rtol=(1e-5, 1e-5)).all()


def test_on_image_update_variable_length(qtbot, mocked_client):
    """
    Test the on_image_update slot with data arrays of varying lengths for 'device_monitor_1d' image type.
    """
    # Create the widget and set image_type to 'device_monitor_1d'
    bec_image_show = create_widget(qtbot, BECFigure, client=mocked_client).image("waveform1d", "1d")

    # Generate data arrays of varying lengths
    data_lengths = [10, 15, 12, 20, 5, 8, 1, 21]
    data_arrays = [np.random.rand(length) for length in data_lengths]

    # Simulate sending messages with these data arrays
    device = "waveform1d"
    for data in data_arrays:
        msg = messages.DeviceMonitor1DMessage(
            device=device, data=data, metadata={"scan_id": "12345"}
        )
        bec_image_show.on_image_update(msg.content, msg.metadata)

    # After processing all data, retrieve the image and its data
    img = bec_image_show.images[0]
    image_buffer = img.get_data()

    # The image_buffer should be a 2D array with number of rows equal to number of data arrays
    # and number of columns equal to the maximum data length
    expected_num_rows = len(data_arrays)
    expected_num_cols = max(data_lengths)
    assert image_buffer.shape == (
        expected_num_rows,
        expected_num_cols,
    ), f"Expected image buffer shape {(expected_num_rows, expected_num_cols)}, got {image_buffer.shape}"

    # Check that each row in image_buffer corresponds to the padded data arrays
    for i, data in enumerate(data_arrays):
        padded_data = np.pad(
            data, (0, expected_num_cols - len(data)), mode="constant", constant_values=0
        )
        assert np.array_equal(
            image_buffer[i], padded_data
        ), f"Row {i} in image buffer does not match expected padded data"
