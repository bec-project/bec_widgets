from unittest import mock

import numpy as np
import pytest
from bec_lib.endpoints import messages

from bec_widgets.utils import Colors
from bec_widgets.widgets.figure import BECFigure

from .client_mocks import mocked_client
from .conftest import create_widget


def test_set_monitor(qtbot, mocked_client):
    """Test that setting the monitor connects the appropriate slot."""
    # Create a BECFigure
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    # Add a multi_waveform plot
    multi_waveform = bec_figure.multi_waveform()
    multi_waveform.set_monitor("waveform1d")

    assert multi_waveform.config.monitor == "waveform1d"
    assert multi_waveform.connected is True

    data_0 = np.random.rand(100)
    msg = messages.DeviceMonitor1DMessage(
        device="waveform1d", data=data_0, metadata={"scan_id": "12345"}
    )
    multi_waveform.on_monitor_1d_update(msg.content, msg.metadata)
    data_waveform = multi_waveform.get_all_data()
    print(data_waveform)

    assert len(data_waveform) == 1
    assert np.array_equal(data_waveform["curve_0"]["y"], data_0)

    data_1 = np.random.rand(100)
    msg = messages.DeviceMonitor1DMessage(
        device="waveform1d", data=data_1, metadata={"scan_id": "12345"}
    )
    multi_waveform.on_monitor_1d_update(msg.content, msg.metadata)

    data_waveform = multi_waveform.get_all_data()
    assert len(data_waveform) == 2
    assert np.array_equal(data_waveform["curve_0"]["y"], data_0)
    assert np.array_equal(data_waveform["curve_1"]["y"], data_1)


def test_on_monitor_1d_update(qtbot, mocked_client):
    """Test that data updates add curves to the plot."""
    # Create a BECFigure
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    # Add a multi_waveform plot
    multi_waveform = bec_figure.multi_waveform()
    multi_waveform.set_monitor("test_monitor")

    # Simulate receiving data updates
    test_data = np.array([1, 2, 3, 4, 5])
    msg = {"data": test_data}
    metadata = {"scan_id": "scan_1"}

    # Call the on_monitor_1d_update method
    multi_waveform.on_monitor_1d_update(msg, metadata)

    # Check that a curve has been added
    assert len(multi_waveform.curves) == 1
    # Check that the data in the curve is correct
    curve = multi_waveform.curves[-1]
    x_data, y_data = curve.getData()
    assert np.array_equal(y_data, test_data)

    # Simulate another data update
    test_data_2 = np.array([6, 7, 8, 9, 10])
    msg2 = {"data": test_data_2}
    metadata2 = {"scan_id": "scan_1"}

    multi_waveform.on_monitor_1d_update(msg2, metadata2)

    # Check that another curve has been added
    assert len(multi_waveform.curves) == 2
    # Check that the data in the curve is correct
    curve2 = multi_waveform.curves[-1]
    x_data2, y_data2 = curve2.getData()
    assert np.array_equal(y_data2, test_data_2)


def test_set_curve_limit_no_flush(qtbot, mocked_client):
    """Test set_curve_limit with flush_buffer=False."""
    # Create a BECFigure
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    # Add a multi_waveform plot
    multi_waveform = bec_figure.multi_waveform()
    multi_waveform.set_monitor("test_monitor")

    # Simulate adding multiple curves
    for i in range(5):
        test_data = np.array([i, i + 1, i + 2])
        msg = {"data": test_data}
        metadata = {"scan_id": "scan_1"}
        multi_waveform.on_monitor_1d_update(msg, metadata)

    # Check that there are 5 curves
    assert len(multi_waveform.curves) == 5
    # Set curve limit to 3 with flush_buffer=False
    multi_waveform.set_curve_limit(3, flush_buffer=False)

    # Check that curves are hidden, but not removed
    assert len(multi_waveform.curves) == 5
    visible_curves = [curve for curve in multi_waveform.curves if curve.isVisible()]
    assert len(visible_curves) == 3
    # The first two curves should be hidden
    assert not multi_waveform.curves[0].isVisible()
    assert not multi_waveform.curves[1].isVisible()
    assert multi_waveform.curves[2].isVisible()
    assert multi_waveform.curves[3].isVisible()
    assert multi_waveform.curves[4].isVisible()


def test_set_curve_limit_flush(qtbot, mocked_client):
    """Test set_curve_limit with flush_buffer=True."""
    # Create a BECFigure
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    # Add a multi_waveform plot
    multi_waveform = bec_figure.multi_waveform()
    multi_waveform.set_monitor("test_monitor")

    # Simulate adding multiple curves
    for i in range(5):
        test_data = np.array([i, i + 1, i + 2])
        msg = {"data": test_data}
        metadata = {"scan_id": "scan_1"}
        multi_waveform.on_monitor_1d_update(msg, metadata)

    # Check that there are 5 curves
    assert len(multi_waveform.curves) == 5
    # Set curve limit to 3 with flush_buffer=True
    multi_waveform.set_curve_limit(3, flush_buffer=True)

    # Check that only 3 curves remain
    assert len(multi_waveform.curves) == 3
    # The curves should be the last 3 added
    x_data, y_data = multi_waveform.curves[0].getData()
    assert np.array_equal(y_data, [2, 3, 4])
    x_data, y_data = multi_waveform.curves[1].getData()
    assert np.array_equal(y_data, [3, 4, 5])
    x_data, y_data = multi_waveform.curves[2].getData()
    assert np.array_equal(y_data, [4, 5, 6])


def test_set_curve_highlight(qtbot, mocked_client):
    """Test that the correct curve is highlighted."""
    # Create a BECFigure
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    # Add a multi_waveform plot
    multi_waveform = bec_figure.multi_waveform()
    multi_waveform.set_monitor("test_monitor")

    # Simulate adding multiple curves
    for i in range(3):
        test_data = np.array([i, i + 1, i + 2])
        msg = {"data": test_data}
        metadata = {"scan_id": "scan_1"}
        multi_waveform.on_monitor_1d_update(msg, metadata)

    # Set highlight_last_curve to False
    multi_waveform.highlight_last_curve = False
    multi_waveform.set_curve_highlight(1)  # Highlight the second curve (index 1)

    # Check that the second curve is highlighted
    visible_curves = [curve for curve in multi_waveform.curves if curve.isVisible()]
    # Reverse the list to match indexing in set_curve_highlight
    visible_curves = list(reversed(visible_curves))
    for i, curve in enumerate(visible_curves):
        pen = curve.opts["pen"]
        width = pen.width()
        if i == 1:
            # Highlighted curve should have width 5
            assert width == 5
        else:
            assert width == 1


def test_set_opacity(qtbot, mocked_client):
    """Test that setting opacity updates the curves."""
    # Create a BECFigure
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    # Add a multi_waveform plot
    multi_waveform = bec_figure.multi_waveform()
    multi_waveform.set_monitor("waveform1d")

    # Simulate adding a curve
    test_data = np.array([1, 2, 3])
    msg = {"data": test_data}
    metadata = {"scan_id": "scan_1"}
    multi_waveform.on_monitor_1d_update(msg, metadata)

    # Set opacity to 30
    multi_waveform.set_opacity(30)
    assert multi_waveform.config.opacity == 30


def test_set_colormap(qtbot, mocked_client):
    """Test that setting the colormap updates the curve colors."""
    # Create a BECFigure
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    # Add a multi_waveform plot
    multi_waveform = bec_figure.multi_waveform()
    multi_waveform.set_monitor("waveform1d")

    # Simulate adding multiple curves
    for i in range(3):
        test_data = np.array([i, i + 1, i + 2])
        msg = {"data": test_data}
        metadata = {"scan_id": "scan_1"}
        multi_waveform.on_monitor_1d_update(msg, metadata)

    # Set a new colormap
    multi_waveform.set_opacity(100)
    multi_waveform.set_colormap("viridis")
    # Check that the colors of the curves have changed accordingly
    visible_curves = [curve for curve in multi_waveform.curves if curve.isVisible()]
    # Get the colors applied
    colors = Colors.evenly_spaced_colors(colormap="viridis", num=len(visible_curves), format="HEX")
    for i, curve in enumerate(visible_curves):
        pen = curve.opts["pen"]
        pen_color = pen.color().name()
        expected_color = colors[i]
        # Compare pen color to expected color
        assert pen_color.lower() == expected_color.lower()


def test_export_to_matplotlib(qtbot, mocked_client):
    """Test that export_to_matplotlib can be called without errors."""
    try:
        import matplotlib
    except ImportError:
        pytest.skip("Matplotlib not installed")

    # Create a BECFigure
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    # Add a multi_waveform plot
    multi_waveform = bec_figure.multi_waveform()
    multi_waveform.set_monitor("test_monitor")

    # Simulate adding a curve
    test_data = np.array([1, 2, 3])
    msg = {"data": test_data}
    metadata = {"scan_id": "scan_1"}
    multi_waveform.on_monitor_1d_update(msg, metadata)

    # Call export_to_matplotlib
    with mock.patch("pyqtgraph.exporters.MatplotlibExporter.export") as mock_export:
        multi_waveform.export_to_matplotlib()
        mock_export.assert_called_once()
