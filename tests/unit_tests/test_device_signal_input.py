from unittest import mock

import pytest
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.ophyd_kind_util import Kind
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.base_classes.device_signal_input_base import (
    DeviceSignalInputBase,
)
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox
from bec_widgets.widgets.control.device_input.signal_line_edit.signal_line_edit import (
    SignalLineEdit,
)

from .client_mocks import mocked_client
from .conftest import create_widget


class DeviceInputWidget(DeviceSignalInputBase, QWidget):
    """Thin wrapper around DeviceInputBase to make it a QWidget"""

    def __init__(self, parent=None, client=None, config=None, gui_id=None):
        QWidget.__init__(self, parent=parent)
        DeviceSignalInputBase.__init__(self, client=client, config=config, gui_id=gui_id)


@pytest.fixture
def device_signal_base(qtbot, mocked_client):
    """Fixture with mocked FilterIO and WidgetIO"""
    with mock.patch("bec_widgets.utils.filter_io.FilterIO.set_selection"):
        with mock.patch("bec_widgets.utils.widget_io.WidgetIO.set_value"):
            widget = create_widget(qtbot=qtbot, widget=DeviceInputWidget, client=mocked_client)
            yield widget


@pytest.fixture
def device_signal_combobox(qtbot, mocked_client):
    """Fixture with mocked FilterIO and WidgetIO"""
    widget = create_widget(qtbot=qtbot, widget=SignalComboBox, client=mocked_client)
    yield widget


@pytest.fixture
def device_signal_line_edit(qtbot, mocked_client):
    """Fixture with mocked FilterIO and WidgetIO"""
    widget = create_widget(qtbot=qtbot, widget=SignalLineEdit, client=mocked_client)
    yield widget


@pytest.fixture
def test_device_signal_combo(qtbot, mocked_client):
    """Fixture to create a SignalComboBox widget and a DeviceInputWidget widget"""
    input = create_widget(
        qtbot=qtbot,
        widget=DeviceComboBox,
        client=mocked_client,
        device_filter=[BECDeviceFilter.POSITIONER],
    )
    signal = create_widget(qtbot=qtbot, widget=SignalComboBox, client=mocked_client)
    yield input, signal


def test_device_signal_base_init(device_signal_base):
    """Test if the DeviceSignalInputBase is initialized correctly"""
    assert device_signal_base._device is None
    assert device_signal_base._signal_filter == []
    assert device_signal_base._signals == []
    assert device_signal_base._hinted_signals == []
    assert device_signal_base._normal_signals == []
    assert device_signal_base._config_signals == []


def test_device_signal_qproperties(device_signal_base):
    """Test if the DeviceSignalInputBase has the correct QProperties"""
    device_signal_base.include_config_signals = True
    assert device_signal_base._signal_filter == [Kind.config]
    device_signal_base.include_normal_signals = True
    assert device_signal_base._signal_filter == [Kind.config, Kind.normal]
    device_signal_base.include_hinted_signals = True
    assert device_signal_base._signal_filter == [Kind.config, Kind.normal, Kind.hinted]


def test_device_signal_set_device(device_signal_base):
    """Test if the set_device method works correctly"""
    device_signal_base.include_hinted_signals = True
    device_signal_base.set_device("samx")
    assert device_signal_base.device == "samx"
    assert device_signal_base.signals == ["readback"]
    device_signal_base.include_normal_signals = True
    assert device_signal_base.signals == ["readback", "setpoint"]
    device_signal_base.include_config_signals = True
    assert device_signal_base.signals == ["readback", "setpoint", "velocity"]


def test_signal_combobox(qtbot, device_signal_combobox):
    """Test the signal_combobox"""
    container = []

    def test_cb(input):
        container.append(input)

    device_signal_combobox.device_signal_changed.connect(test_cb)
    assert device_signal_combobox._signals == []
    device_signal_combobox.include_normal_signals = True
    device_signal_combobox.include_hinted_signals = True
    device_signal_combobox.include_config_signals = True
    assert device_signal_combobox.signals == []
    device_signal_combobox.set_device("samx")
    assert device_signal_combobox.signals == ["readback", "setpoint", "velocity"]
    qtbot.wait(100)
    assert container == ["samx"]


def test_signal_lineeidt(device_signal_line_edit):
    """Test the signal_combobox"""

    assert device_signal_line_edit._signals == []
    device_signal_line_edit.include_normal_signals = True
    device_signal_line_edit.include_hinted_signals = True
    device_signal_line_edit.include_config_signals = True
    assert device_signal_line_edit.signals == []
    device_signal_line_edit.set_device("samx")
    assert device_signal_line_edit.signals == ["readback", "setpoint", "velocity"]
