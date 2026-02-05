# pylint: disable=missing-function-docstring, missing-module-docstring

from unittest.mock import MagicMock

import pytest
from qtpy.QtGui import QColor

from bec_widgets.tests.utils import FakeDevice
from bec_widgets.widgets.progress.ring_progress_bar.ring import ProgressbarConfig, Ring
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import (
    RingProgressContainerWidget,
)


@pytest.fixture
def ring_container(qtbot, mocked_client):
    container = RingProgressContainerWidget()
    qtbot.addWidget(container)
    yield container


@pytest.fixture
def ring_widget(qtbot, ring_container, mocked_client):
    ring = Ring(parent=ring_container, client=mocked_client)
    qtbot.addWidget(ring)
    qtbot.waitExposed(ring)
    yield ring


@pytest.fixture
def ring_widget_with_device(ring_widget):
    mock_device = FakeDevice(name="samx")
    ring_widget.bec_dispatcher.client.device_manager.devices["samx"] = mock_device
    yield ring_widget


def test_ring_initialization(ring_widget):
    assert ring_widget is not None
    assert isinstance(ring_widget.config, ProgressbarConfig)
    assert ring_widget.config.mode == "manual"
    assert ring_widget.config.value == 0
    assert ring_widget.registered_slot is None


def test_ring_has_default_config_values(ring_widget):
    assert ring_widget.config.direction == -1
    assert ring_widget.config.line_width == 20
    assert ring_widget.config.start_position == 90
    assert ring_widget.config.min_value == 0
    assert ring_widget.config.max_value == 100
    assert ring_widget.config.precision == 3


###################################
# set_update method tests
###################################


def test_set_update_to_manual(ring_widget):
    # Start in manual mode
    assert ring_widget.config.mode == "manual"

    # Set to manual again (should return early)
    ring_widget.set_update("manual")
    assert ring_widget.config.mode == "manual"
    assert ring_widget.registered_slot is None


def test_set_update_to_scan(ring_widget):
    # Mock the dispatcher to avoid actual connections
    ring_widget.bec_dispatcher.connect_slot = MagicMock()

    # Set to scan mode
    ring_widget.set_update("scan")

    assert ring_widget.config.mode == "scan"
    # Verify that connect_slot was called
    ring_widget.bec_dispatcher.connect_slot.assert_called_once()
    call_args = ring_widget.bec_dispatcher.connect_slot.call_args
    assert call_args[0][0] == ring_widget.on_scan_progress
    assert "scan_progress" in str(call_args[0][1])


def test_set_update_from_scan_to_manual(ring_widget):
    # Mock the dispatcher
    ring_widget.bec_dispatcher.connect_slot = MagicMock()
    ring_widget.bec_dispatcher.disconnect_slot = MagicMock()

    # Set to scan mode first
    ring_widget.set_update("scan")
    assert ring_widget.config.mode == "scan"

    # Now switch back to manual
    ring_widget.set_update("manual")

    assert ring_widget.config.mode == "manual"
    assert ring_widget.registered_slot is None


def test_set_update_to_device(ring_widget_with_device):
    ring_widget = ring_widget_with_device
    # Mock the dispatcher
    ring_widget.bec_dispatcher.connect_slot = MagicMock()

    # Set to device mode
    test_device = "samx"
    ring_widget.set_update("device", device=test_device)

    assert ring_widget.config.mode == "device"
    assert ring_widget.config.device == test_device
    assert ring_widget.config.signal == "samx"
    ring_widget.bec_dispatcher.connect_slot.assert_called_once()


def test_set_update_from_device_to_manual(ring_widget_with_device):
    ring_widget = ring_widget_with_device
    # Mock the dispatcher
    ring_widget.bec_dispatcher.connect_slot = MagicMock()
    ring_widget.bec_dispatcher.disconnect_slot = MagicMock()

    # Set to device mode first
    ring_widget.set_update("device", device="samx")
    assert ring_widget.config.mode == "device"

    # Switch to manual
    ring_widget.set_update("manual")

    assert ring_widget.config.mode == "manual"
    assert ring_widget.registered_slot is None


def test_set_update_scan_to_device(ring_widget_with_device):
    ring_widget = ring_widget_with_device
    # Mock the dispatcher
    ring_widget.bec_dispatcher.connect_slot = MagicMock()
    ring_widget.bec_dispatcher.disconnect_slot = MagicMock()

    # Set to scan mode first
    ring_widget.set_update("scan")
    assert ring_widget.config.mode == "scan"

    # Switch to device mode
    ring_widget.set_update("device", device="samx")

    assert ring_widget.config.mode == "device"
    assert ring_widget.config.device == "samx"


def test_set_update_device_to_scan(ring_widget_with_device):
    ring_widget = ring_widget_with_device
    # Mock the dispatcher
    ring_widget.bec_dispatcher.connect_slot = MagicMock()
    ring_widget.bec_dispatcher.disconnect_slot = MagicMock()

    # Set to device mode first
    ring_widget.set_update("device", device="samx")
    assert ring_widget.config.mode == "device"

    # Switch to scan mode
    ring_widget.set_update("scan")

    assert ring_widget.config.mode == "scan"


def test_set_update_same_device_resubscribes(ring_widget_with_device):
    ring_widget = ring_widget_with_device
    # Mock the dispatcher
    ring_widget.bec_dispatcher.connect_slot = MagicMock()
    ring_widget.bec_dispatcher.disconnect_slot = MagicMock()

    # Set to device mode
    test_device = "samx"
    ring_widget.set_update("device", device=test_device)

    # Reset mocks
    ring_widget.bec_dispatcher.connect_slot.reset_mock()
    ring_widget.bec_dispatcher.disconnect_slot.reset_mock()

    # Set to same device mode again (should resubscribe)
    ring_widget.set_update("device", device=test_device)

    # Should disconnect and reconnect
    ring_widget.bec_dispatcher.disconnect_slot.assert_called_once()
    ring_widget.bec_dispatcher.connect_slot.assert_called_once()


def test_set_update_invalid_mode(ring_widget):
    with pytest.raises(ValueError) as excinfo:
        ring_widget.set_update("invalid_mode")

    assert "Unsupported mode: invalid_mode" in str(excinfo.value)


###################################
# Value and property tests
###################################


def test_set_value(ring_widget):
    ring_widget.set_value(42.5)
    assert ring_widget.config.value == 42.5


def test_set_value_with_min_max_clamping(ring_widget):
    ring_widget.set_min_max_values(0, 100)

    # Set value above max
    ring_widget.set_value(150)
    assert ring_widget.config.value == 100

    # Set value below min
    ring_widget.set_value(-10)
    assert ring_widget.config.value == 0


def test_set_precision(ring_widget):
    ring_widget.set_precision(2)
    assert ring_widget.config.precision == 2

    ring_widget.set_value(10.12345)
    assert ring_widget.config.value == 10.12


def test_set_min_max_values(ring_widget):
    ring_widget.set_min_max_values(10, 90)

    assert ring_widget.config.min_value == 10
    assert ring_widget.config.max_value == 90


def test_set_line_width(ring_widget):
    ring_widget.set_line_width(25)
    assert ring_widget.config.line_width == 25


def test_set_start_angle(ring_widget):
    ring_widget.set_start_angle(180)
    assert ring_widget.config.start_position == 180


###################################
# Color management tests
###################################


def test_set_color(ring_widget):
    test_color = (255, 128, 64, 255)
    ring_widget.set_color(test_color)

    # Color is stored as hex string internally
    assert ring_widget.color.getRgb() == test_color


def test_set_color_with_link_colors_updates_background(ring_widget):
    # Enable color linking
    ring_widget.config.link_colors = True

    # Store original background
    original_bg = ring_widget.background_color.getRgb()

    test_color = (255, 100, 50, 255)
    ring_widget.set_color(test_color)

    # Background should be derived using subtle_background_color
    bg_color = ring_widget.background_color
    # Background should have changed
    assert bg_color.getRgb() != original_bg
    # Background should be different from the main color
    assert bg_color.getRgb() != test_color


def test_set_background_when_colors_unlinked(ring_widget):
    # Disable color linking
    ring_widget.config.link_colors = False

    test_bg = (100, 100, 100, 128)
    ring_widget.set_background(test_bg)

    assert ring_widget.background_color.getRgb() == test_bg


def test_set_background_when_colors_linked_does_nothing(ring_widget):
    # Enable color linking
    ring_widget.config.link_colors = True

    original_bg = ring_widget.background_color.getRgb()
    test_bg = (100, 100, 100, 128)

    ring_widget.set_background(test_bg)

    # Background should not change when colors are linked
    assert ring_widget.background_color.getRgb() == original_bg


def test_color_link_derives_background(ring_widget):
    ring_widget.config.link_colors = True

    bright_color = QColor(255, 255, 0, 255)  # Bright yellow
    original_bg = ring_widget.background_color.getRgb()

    ring_widget.set_color(bright_color.getRgb())

    # Get the derived background color
    bg_color = ring_widget.background_color

    # Background should have changed
    assert bg_color.getRgb() != original_bg
    # Background should be a subtle blend, not the same as the main color
    assert bg_color.getRgb() != bright_color.getRgb()


def test_convert_color_from_tuple(ring_widget):
    color_tuple = (200, 150, 100, 255)
    qcolor = ring_widget.convert_color(color_tuple)

    assert isinstance(qcolor, QColor)
    assert qcolor.getRgb() == color_tuple


def test_convert_color_from_hex_string(ring_widget):
    hex_color = "#FF8040FF"
    qcolor = ring_widget.convert_color(hex_color)

    assert isinstance(qcolor, QColor)
    assert qcolor.isValid()


###################################
# Gap property tests
###################################


def test_gap_property(ring_widget):
    ring_widget.gap = 15
    assert ring_widget.gap == 15


###################################
# Config validation tests
###################################


def test_config_default_values():
    config = ProgressbarConfig()

    assert config.value == 0
    assert config.direction == -1
    assert config.line_width == 20
    assert config.start_position == 90
    assert config.min_value == 0
    assert config.max_value == 100
    assert config.precision == 3
    assert config.mode == "manual"
    assert config.link_colors is True


def test_config_with_custom_values():
    config = ProgressbarConfig(
        value=50, direction=1, line_width=20, min_value=10, max_value=90, precision=2, mode="scan"
    )

    assert config.value == 50
    assert config.direction == 1
    assert config.line_width == 20
    assert config.min_value == 10
    assert config.max_value == 90
    assert config.precision == 2
    assert config.mode == "scan"


###################################
# set_direction tests
###################################


def test_set_direction_clockwise(ring_widget):
    ring_widget.set_direction(-1)
    assert ring_widget.config.direction == -1


def test_set_direction_counter_clockwise(ring_widget):
    ring_widget.set_direction(1)
    assert ring_widget.config.direction == 1


###################################
# _update_device_connection tests
###################################


def test_update_device_connection_with_progress_signal(ring_widget_with_device):
    ring_widget = ring_widget_with_device
    samx = ring_widget.bec_dispatcher.client.device_manager.devices.samx
    samx._info["signals"]["progress"] = {
        "obj_name": "samx_progress",
        "component_name": "progress",
        "signal_class": "ProgressSignal",
        "kind_str": "hinted",
    }

    ring_widget.bec_dispatcher.connect_slot = MagicMock()

    ring_widget._update_device_connection("samx", "progress")

    # Should connect to device_progress endpoint
    ring_widget.bec_dispatcher.connect_slot.assert_called_once()
    call_args = ring_widget.bec_dispatcher.connect_slot.call_args
    assert call_args[0][0] == ring_widget.on_device_progress


def test_update_device_connection_with_hinted_signal(ring_widget):
    mock_device = FakeDevice(name="samx")
    mock_device._info = {
        "signals": {
            "samx": {"obj_name": "samx", "signal_class": "SomeOtherSignal", "kind_str": "hinted"}
        }
    }

    ring_widget.bec_dispatcher.client.device_manager.devices["samx"] = mock_device

    ring_widget.bec_dispatcher.connect_slot = MagicMock()

    ring_widget._update_device_connection("samx", "samx")

    # Should connect to device_readback endpoint
    ring_widget.bec_dispatcher.connect_slot.assert_called_once()
    call_args = ring_widget.bec_dispatcher.connect_slot.call_args
    assert call_args[0][0] == ring_widget.on_device_readback


def test_update_device_connection_no_device_manager(ring_widget):
    ring_widget.bec_dispatcher.client.device_manager = None

    with pytest.raises(ValueError) as excinfo:
        ring_widget._update_device_connection("samx", "signal")
    assert "Device manager is not available" in str(excinfo.value)


def test_update_device_connection_device_not_found(ring_widget):
    mock_device = FakeDevice(name="samx")
    ring_widget.bec_dispatcher.client.device_manager.devices["samx"] = mock_device

    # Should return without raising an error
    ring_widget._update_device_connection("nonexistent", "signal")


###################################
# on_scan_progress tests
###################################


def test_on_scan_progress_updates_value(ring_widget):
    msg = {"value": 42, "max_value": 100}
    meta = {"RID": "test_rid_123"}

    ring_widget.on_scan_progress(msg, meta)

    assert ring_widget.config.value == 42


def test_on_scan_progress_updates_min_max_on_new_rid(ring_widget):
    msg = {"value": 50, "max_value": 200}
    meta = {"RID": "new_rid"}

    ring_widget.RID = "old_rid"
    ring_widget.on_scan_progress(msg, meta)

    assert ring_widget.config.min_value == 0
    assert ring_widget.config.max_value == 200
    assert ring_widget.config.value == 50


def test_on_scan_progress_same_rid_no_min_max_update(ring_widget):
    msg = {"value": 75, "max_value": 300}
    meta = {"RID": "same_rid"}

    ring_widget.RID = "same_rid"
    ring_widget.set_min_max_values(0, 100)

    ring_widget.on_scan_progress(msg, meta)

    # Max value should not be updated when RID is the same
    assert ring_widget.config.max_value == 100
    assert ring_widget.config.value == 75


###################################
# on_device_readback tests
###################################


def test_on_device_readback_updates_value(ring_widget):
    ring_widget.config.device = "samx"
    ring_widget.config.signal = "readback"

    msg = {"signals": {"readback": {"value": 12.34}}}
    meta = {}

    ring_widget.on_device_readback(msg, meta)

    assert ring_widget.config.value == 12.34


def test_on_device_readback_uses_device_name_when_no_signal(ring_widget):
    ring_widget.config.device = "samy"
    ring_widget.config.signal = None

    msg = {"signals": {"samy": {"value": 56.78}}}
    meta = {}

    ring_widget.on_device_readback(msg, meta)

    assert ring_widget.config.value == 56.78


def test_on_device_readback_no_device_returns_early(ring_widget):
    ring_widget.config.device = None

    msg = {"signals": {"samx": {"value": 99.99}}}
    meta = {}

    initial_value = ring_widget.config.value
    ring_widget.on_device_readback(msg, meta)

    # Value should not change
    assert ring_widget.config.value == initial_value


def test_on_device_readback_missing_signal_data(ring_widget):
    ring_widget.config.device = "samx"
    ring_widget.config.signal = "missing_signal"

    msg = {"signals": {"other_signal": {"value": 11.11}}}
    meta = {}

    initial_value = ring_widget.config.value
    ring_widget.on_device_readback(msg, meta)

    # Value should not change when signal is missing
    assert ring_widget.config.value == initial_value


###################################
# on_device_progress tests
###################################


def test_on_device_progress_updates_value_and_max(ring_widget):
    ring_widget.config.device = "samx"

    msg = {"value": 30, "max_value": 150, "done": False}
    meta = {}

    ring_widget.on_device_progress(msg, meta)

    assert ring_widget.config.value == 30
    assert ring_widget.config.max_value == 150


def test_on_device_progress_done_sets_to_max(ring_widget):
    ring_widget.config.device = "samx"

    msg = {"value": 80, "max_value": 100, "done": True}
    meta = {}

    ring_widget.on_device_progress(msg, meta)

    # When done is True, value should be set to max_value
    assert ring_widget.config.value == 100
    assert ring_widget.config.max_value == 100


def test_on_device_progress_no_device_returns_early(ring_widget):
    ring_widget.config.device = None

    msg = {"value": 50, "max_value": 100, "done": False}
    meta = {}

    initial_value = ring_widget.config.value
    initial_max = ring_widget.config.max_value

    ring_widget.on_device_progress(msg, meta)

    # Nothing should change
    assert ring_widget.config.value == initial_value
    assert ring_widget.config.max_value == initial_max


def test_on_device_progress_default_values(ring_widget):
    ring_widget.config.device = "samx"

    # Message without value and max_value
    msg = {}
    meta = {}

    ring_widget.on_device_progress(msg, meta)

    # Should use defaults: value=0, max_value=100
    assert ring_widget.config.value == 0
    assert ring_widget.config.max_value == 100
