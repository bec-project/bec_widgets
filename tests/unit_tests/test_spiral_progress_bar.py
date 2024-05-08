# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest
from bec_lib.endpoints import MessageEndpoints
from pydantic import ValidationError

from bec_widgets.utils import Colors
from bec_widgets.widgets import SpiralProgressBar
from bec_widgets.widgets.spiral_progress_bar.ring import RingConfig, RingConnections
from bec_widgets.widgets.spiral_progress_bar.spiral_progress_bar import SpiralProgressBarConfig

from .client_mocks import mocked_client


@pytest.fixture
def spiral_progress_bar(qtbot, mocked_client):
    widget = SpiralProgressBar(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_bar_init(spiral_progress_bar):
    assert spiral_progress_bar is not None
    assert spiral_progress_bar.client is not None
    assert isinstance(spiral_progress_bar, SpiralProgressBar)
    assert spiral_progress_bar.config.widget_class == "SpiralProgressBar"
    assert spiral_progress_bar.config.gui_id is not None
    assert spiral_progress_bar.gui_id == spiral_progress_bar.config.gui_id


def test_config_validation_num_of_bars():
    config = SpiralProgressBarConfig(num_bars=100, min_num_bars=1, max_num_bars=10)

    assert config.num_bars == 10


def test_config_validation_num_of_ring_error():
    ring_config_0 = RingConfig(index=0)
    ring_config_1 = RingConfig(index=1)

    with pytest.raises(ValidationError) as excinfo:
        SpiralProgressBarConfig(rings=[ring_config_0, ring_config_1], num_bars=1)
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "different number of configs"
    assert "Length of rings configuration (2) does not match the number of bars (1)." in str(
        excinfo.value
    )


def test_config_validation_ring_indices_wrong_order():
    ring_config_0 = RingConfig(index=2)
    ring_config_1 = RingConfig(index=5)

    with pytest.raises(ValidationError) as excinfo:
        SpiralProgressBarConfig(rings=[ring_config_0, ring_config_1], num_bars=2)
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "wrong indices"
    assert (
        "Indices of ring configurations must be unique and in order from 0 to num_bars 2."
        in str(excinfo.value)
    )


def test_config_validation_ring_same_indices():
    ring_config_0 = RingConfig(index=0)
    ring_config_1 = RingConfig(index=0)

    with pytest.raises(ValidationError) as excinfo:
        SpiralProgressBarConfig(rings=[ring_config_0, ring_config_1], num_bars=2)
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "wrong indices"
    assert (
        "Indices of ring configurations must be unique and in order from 0 to num_bars 2."
        in str(excinfo.value)
    )


def test_config_validation_invalid_colormap():
    with pytest.raises(ValueError) as excinfo:
        SpiralProgressBarConfig(color_map="crazy_colors")
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "unsupported colormap"
    assert "Colormap 'crazy_colors' not found in the current installation of pyqtgraph" in str(
        excinfo.value
    )


def test_ring_connection_endpoint_validation():
    with pytest.raises(ValueError) as excinfo:
        RingConnections(slot="on_scan_progress", endpoint="non_existing")
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "unsupported endpoint"
    assert (
        "For slot 'on_scan_progress', endpoint must be MessageEndpoint.scan_progress or 'scans/scan_progress'."
        in str(excinfo.value)
    )

    with pytest.raises(ValueError) as excinfo:
        RingConnections(slot="on_device_readback", endpoint="non_existing")
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "unsupported endpoint"
    assert (
        "For slot 'on_device_readback', endpoint must be MessageEndpoint.device_readback(device) or 'internal/devices/readback/{device}'."
        in str(excinfo.value)
    )


def test_bar_add_number_of_bars(spiral_progress_bar):
    assert spiral_progress_bar.config.num_bars == 1

    spiral_progress_bar.set_number_of_bars(5)
    assert spiral_progress_bar.config.num_bars == 5

    spiral_progress_bar.set_number_of_bars(2)
    assert spiral_progress_bar.config.num_bars == 2


def test_add_remove_bars_individually(spiral_progress_bar):
    spiral_progress_bar.add_ring()
    spiral_progress_bar.add_ring()

    assert spiral_progress_bar.config.num_bars == 3
    assert len(spiral_progress_bar.config.rings) == 3

    spiral_progress_bar.remove_ring(1)
    assert spiral_progress_bar.config.num_bars == 2
    assert len(spiral_progress_bar.config.rings) == 2
    assert spiral_progress_bar.rings[0].config.index == 0
    assert spiral_progress_bar.rings[1].config.index == 1


def test_bar_set_value(spiral_progress_bar):
    spiral_progress_bar.set_number_of_bars(5)

    assert spiral_progress_bar.config.num_bars == 5
    assert len(spiral_progress_bar.config.rings) == 5
    assert len(spiral_progress_bar.rings) == 5

    spiral_progress_bar.set_value([10, 20, 30, 40, 50])
    ring_values = [ring.value for ring in spiral_progress_bar.rings]
    assert ring_values == [10, 20, 30, 40, 50]

    # update just one bar
    spiral_progress_bar.set_value(90, 1)
    ring_values = [ring.value for ring in spiral_progress_bar.rings]
    assert ring_values == [10, 90, 30, 40, 50]


def test_bar_set_precision(spiral_progress_bar):
    spiral_progress_bar.set_number_of_bars(3)

    assert spiral_progress_bar.config.num_bars == 3
    assert len(spiral_progress_bar.config.rings) == 3
    assert len(spiral_progress_bar.rings) == 3

    spiral_progress_bar.set_precision(2)
    ring_precision = [ring.config.precision for ring in spiral_progress_bar.rings]
    assert ring_precision == [2, 2, 2]

    spiral_progress_bar.set_value([10.1234, 20.1234, 30.1234])
    ring_values = [ring.value for ring in spiral_progress_bar.rings]
    assert ring_values == [10.12, 20.12, 30.12]

    spiral_progress_bar.set_precision(4, 1)
    ring_precision = [ring.config.precision for ring in spiral_progress_bar.rings]
    assert ring_precision == [2, 4, 2]

    spiral_progress_bar.set_value([10.1234, 20.1234, 30.1234])
    ring_values = [ring.value for ring in spiral_progress_bar.rings]
    assert ring_values == [10.12, 20.1234, 30.12]


def test_set_min_max_value(spiral_progress_bar):
    spiral_progress_bar.set_number_of_bars(2)

    spiral_progress_bar.set_min_max_values(0, 10)
    ring_min_values = [ring.config.min_value for ring in spiral_progress_bar.rings]
    ring_max_values = [ring.config.max_value for ring in spiral_progress_bar.rings]

    assert ring_min_values == [0, 0]
    assert ring_max_values == [10, 10]

    spiral_progress_bar.set_value([5, 15])
    ring_values = [ring.value for ring in spiral_progress_bar.rings]
    assert ring_values == [5, 10]


def test_setup_colors_from_colormap(spiral_progress_bar):
    spiral_progress_bar.set_number_of_bars(5)
    spiral_progress_bar.set_colors_from_map("viridis", "RGB")

    expected_colors = Colors.golden_angle_color("viridis", 5, "RGB")
    converted_colors = [ring.color.getRgb() for ring in spiral_progress_bar.rings]
    ring_config_colors = [ring.config.color for ring in spiral_progress_bar.rings]

    assert expected_colors == converted_colors
    assert ring_config_colors == expected_colors


def get_colors_from_rings(rings):
    converted_colors = [ring.color.getRgb() for ring in rings]
    ring_config_colors = [ring.config.color for ring in rings]
    return converted_colors, ring_config_colors


def test_set_colors_from_colormap_and_change_num_of_bars(spiral_progress_bar):
    spiral_progress_bar.set_number_of_bars(2)
    spiral_progress_bar.set_colors_from_map("viridis", "RGB")

    expected_colors = Colors.golden_angle_color("viridis", 2, "RGB")
    converted_colors, ring_config_colors = get_colors_from_rings(spiral_progress_bar.rings)

    assert expected_colors == converted_colors
    assert ring_config_colors == expected_colors

    # increase the number of bars to 6
    spiral_progress_bar.set_number_of_bars(6)
    expected_colors = Colors.golden_angle_color("viridis", 6, "RGB")
    converted_colors, ring_config_colors = get_colors_from_rings(spiral_progress_bar.rings)

    assert expected_colors == converted_colors
    assert ring_config_colors == expected_colors

    # decrease the number of bars to 3
    spiral_progress_bar.set_number_of_bars(3)
    expected_colors = Colors.golden_angle_color("viridis", 3, "RGB")
    converted_colors, ring_config_colors = get_colors_from_rings(spiral_progress_bar.rings)

    assert expected_colors == converted_colors
    assert ring_config_colors == expected_colors


def test_set_colors_directly(spiral_progress_bar):
    spiral_progress_bar.set_number_of_bars(3)

    # setting as a list of rgb tuples
    colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
    spiral_progress_bar.set_colors_directly(colors)
    converted_colors = get_colors_from_rings(spiral_progress_bar.rings)[0]

    assert colors == converted_colors

    spiral_progress_bar.set_colors_directly((255, 0, 0, 255), 1)
    converted_colors = get_colors_from_rings(spiral_progress_bar.rings)[0]

    assert converted_colors == [(255, 0, 0, 255), (255, 0, 0, 255), (0, 0, 255, 255)]


def test_set_line_width(spiral_progress_bar):
    spiral_progress_bar.set_number_of_bars(3)

    spiral_progress_bar.set_line_widths(5)
    line_widths = [ring.config.line_width for ring in spiral_progress_bar.rings]

    assert line_widths == [5, 5, 5]

    spiral_progress_bar.set_line_widths([10, 20, 30])
    line_widths = [ring.config.line_width for ring in spiral_progress_bar.rings]

    assert line_widths == [10, 20, 30]

    spiral_progress_bar.set_line_widths(15, 1)
    line_widths = [ring.config.line_width for ring in spiral_progress_bar.rings]

    assert line_widths == [10, 15, 30]


def test_set_gap(spiral_progress_bar):
    spiral_progress_bar.set_number_of_bars(3)
    spiral_progress_bar.set_gap(20)

    assert spiral_progress_bar.config.gap == 20


def test_auto_update(spiral_progress_bar):
    spiral_progress_bar.enable_auto_updates(True)

    scan_queue_status_scan_progress = {
        "queue": {
            "primary": {
                "info": [{"active_request_block": {"report_instructions": [{"scan_progress": 10}]}}]
            }
        }
    }
    meta = {}

    spiral_progress_bar.on_scan_queue_status(scan_queue_status_scan_progress, meta)

    assert spiral_progress_bar._auto_updates is True
    assert len(spiral_progress_bar._rings) == 1
    assert spiral_progress_bar._rings[0].config.connections == RingConnections(
        slot="on_scan_progress", endpoint=MessageEndpoints.scan_progress()
    )

    scan_queue_status_device_readback = {
        "queue": {
            "primary": {
                "info": [
                    {
                        "active_request_block": {
                            "report_instructions": [
                                {
                                    "readback": {
                                        "devices": ["samx", "samy"],
                                        "start": [1, 2],
                                        "end": [10, 20],
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }
    spiral_progress_bar.on_scan_queue_status(scan_queue_status_device_readback, meta)

    assert spiral_progress_bar._auto_updates is True
    assert len(spiral_progress_bar._rings) == 2
    assert spiral_progress_bar._rings[0].config.connections == RingConnections(
        slot="on_device_readback", endpoint=MessageEndpoints.device_readback("samx")
    )
    assert spiral_progress_bar._rings[1].config.connections == RingConnections(
        slot="on_device_readback", endpoint=MessageEndpoints.device_readback("samy")
    )

    assert spiral_progress_bar._rings[0].config.min_value == 1
    assert spiral_progress_bar._rings[0].config.max_value == 10
    assert spiral_progress_bar._rings[1].config.min_value == 2
    assert spiral_progress_bar._rings[1].config.max_value == 20
