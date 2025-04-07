from unittest import mock

import pytest
from bec_lib.device import ReadoutPriority
from qtpy.QtWidgets import QWidget

from bec_widgets.widgets.control.device_input.base_classes.device_input_base import (
    BECDeviceFilter,
    DeviceInputBase,
)

from .client_mocks import mocked_client
from .conftest import create_widget


# DeviceInputBase is meant to be mixed in a QWidget
class DeviceInputWidget(DeviceInputBase, QWidget):
    """Thin wrapper around DeviceInputBase to make it a QWidget"""

    def __init__(self, parent=None, client=None, config=None, gui_id=None, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)


@pytest.fixture
def device_input_base(qtbot, mocked_client):
    """Fixture with mocked FilterIO and WidgetIO"""
    with mock.patch("bec_widgets.utils.filter_io.FilterIO.set_selection"):
        with mock.patch("bec_widgets.utils.widget_io.WidgetIO.set_value"):
            with mock.patch("bec_widgets.utils.widget_io.WidgetIO.get_value"):
                widget = create_widget(qtbot=qtbot, widget=DeviceInputWidget, client=mocked_client)
                yield widget


def test_device_input_base_init(device_input_base):
    """Test init"""
    assert device_input_base is not None
    assert device_input_base.client is not None
    assert isinstance(device_input_base, DeviceInputBase)
    assert device_input_base.config.widget_class == "DeviceInputWidget"
    assert device_input_base.config.device_filter == []
    assert device_input_base.config.default is None
    assert device_input_base.devices == []


def test_device_input_base_init_with_config(mocked_client):
    """Test init with Config"""
    config = {
        "widget_class": "DeviceInputWidget",
        "gui_id": "test_gui_id",
        "device_filter": [BECDeviceFilter.POSITIONER],
        "default": "samx",
    }
    widget = DeviceInputWidget(client=mocked_client, config=config)
    assert widget.config.gui_id == "test_gui_id"
    assert widget.config.device_filter == ["Positioner"]
    assert widget.config.default == "samx"


def test_device_input_base_set_device_filter(device_input_base):
    """Test device filter setter."""
    device_input_base.set_device_filter(BECDeviceFilter.POSITIONER)
    assert device_input_base.config.device_filter == ["Positioner"]


def test_device_input_base_set_device_filter_error(device_input_base):
    """Test set_device_filter with Noneexisting class. This should not raise. It writes a log message entry."""
    device_input_base.set_device_filter("NonExistingClass")
    assert device_input_base.device_filter == []


def test_device_input_base_set_default_device(device_input_base):
    """Test setting the default device. Also tests the update_devices method."""
    device_input_base.set_device("samx")
    assert device_input_base.config.default == None
    device_input_base.set_device_filter(BECDeviceFilter.POSITIONER)
    device_input_base.set_readout_priority_filter(ReadoutPriority.MONITORED)
    device_input_base.set_device("samx")
    assert device_input_base.config.default == "samx"


def test_device_input_base_get_filters(device_input_base):
    """Test getting the available filters."""
    filters = device_input_base.get_available_filters()
    selection = [
        BECDeviceFilter.POSITIONER,
        BECDeviceFilter.DEVICE,
        BECDeviceFilter.COMPUTED_SIGNAL,
        BECDeviceFilter.SIGNAL,
    ] + [
        ReadoutPriority.MONITORED,
        ReadoutPriority.BASELINE,
        ReadoutPriority.ASYNC,
        ReadoutPriority.ON_REQUEST,
    ]
    assert [entry for entry in filters if entry in selection]


def test_device_input_base_properties(device_input_base):
    """Test setting the properties of the device input base."""
    assert device_input_base.device_filter == []
    device_input_base.filter_to_device = True
    assert device_input_base.device_filter == [BECDeviceFilter.DEVICE]
    device_input_base.filter_to_positioner = True
    assert device_input_base.device_filter == [BECDeviceFilter.DEVICE, BECDeviceFilter.POSITIONER]
    device_input_base.filter_to_computed_signal = True
    assert device_input_base.device_filter == [
        BECDeviceFilter.DEVICE,
        BECDeviceFilter.POSITIONER,
        BECDeviceFilter.COMPUTED_SIGNAL,
    ]
    device_input_base.filter_to_signal = True
    assert device_input_base.device_filter == [
        BECDeviceFilter.DEVICE,
        BECDeviceFilter.POSITIONER,
        BECDeviceFilter.COMPUTED_SIGNAL,
        BECDeviceFilter.SIGNAL,
    ]
    assert device_input_base.readout_filter == []
    device_input_base.readout_async = True
    assert device_input_base.readout_filter == [ReadoutPriority.ASYNC]
    device_input_base.readout_baseline = True
    assert device_input_base.readout_filter == [ReadoutPriority.ASYNC, ReadoutPriority.BASELINE]
    device_input_base.readout_monitored = True
    assert device_input_base.readout_filter == [
        ReadoutPriority.ASYNC,
        ReadoutPriority.BASELINE,
        ReadoutPriority.MONITORED,
    ]
    device_input_base.readout_on_request = True
    assert device_input_base.readout_filter == [
        ReadoutPriority.ASYNC,
        ReadoutPriority.BASELINE,
        ReadoutPriority.MONITORED,
        ReadoutPriority.ON_REQUEST,
    ]
