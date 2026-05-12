from unittest import mock

from bec_lib.device import ReadoutPriority

from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import (
    BECDeviceFilter,
    DeviceComboBox,
    DeviceInputConfig,
)

from .client_mocks import mocked_client
from .conftest import create_widget


def test_device_combobox_init_with_config(qtbot, mocked_client):
    config = {
        "widget_class": "DeviceComboBox",
        "gui_id": "test_gui_id",
        "device_filter": [BECDeviceFilter.POSITIONER.value],
        "default": "samx",
    }
    widget = create_widget(
        qtbot=qtbot,
        widget=DeviceComboBox,
        client=mocked_client,
        config=DeviceInputConfig.model_validate(config),
    )

    assert widget.config.gui_id == "test_gui_id"
    assert widget.config.device_filter == ["Positioner"]
    assert widget.config.default == "samx"


def test_device_combobox_set_device_filter(qtbot, mocked_client):
    widget = create_widget(qtbot=qtbot, widget=DeviceComboBox, client=mocked_client)

    widget.set_device_filter(BECDeviceFilter.POSITIONER)

    assert widget.config.device_filter == ["Positioner"]


def test_device_combobox_set_device_filter_error(qtbot, mocked_client):
    widget = create_widget(qtbot=qtbot, widget=DeviceComboBox, client=mocked_client)

    widget.set_device_filter("NonExistingClass")

    assert widget.device_filter == []


def test_device_combobox_set_default_device(qtbot, mocked_client):
    widget = create_widget(qtbot=qtbot, widget=DeviceComboBox, client=mocked_client)

    widget.set_device("samx")

    assert widget.config.default == "samx"


def test_device_combobox_get_filters(qtbot, mocked_client):
    widget = create_widget(qtbot=qtbot, widget=DeviceComboBox, client=mocked_client)

    assert BECDeviceFilter.POSITIONER in widget.get_available_filters()
    assert ReadoutPriority.MONITORED in widget.get_readout_priority_filters()


def test_device_combobox_properties(qtbot, mocked_client):
    widget = create_widget(qtbot=qtbot, widget=DeviceComboBox, client=mocked_client)

    widget.filter_to_device = True
    widget.filter_to_positioner = True
    widget.filter_to_computed_signal = True
    widget.filter_to_signal = True
    assert widget.device_filter == [
        BECDeviceFilter.DEVICE,
        BECDeviceFilter.POSITIONER,
        BECDeviceFilter.COMPUTED_SIGNAL,
        BECDeviceFilter.SIGNAL,
    ]

    widget.readout_async = True
    widget.readout_baseline = True
    widget.readout_monitored = True
    widget.readout_on_request = True
    assert ReadoutPriority.ASYNC in widget.readout_filter
    assert ReadoutPriority.BASELINE in widget.readout_filter
    assert ReadoutPriority.MONITORED in widget.readout_filter
    assert ReadoutPriority.ON_REQUEST in widget.readout_filter


def test_device_combobox_signal_class_filter(qtbot, mocked_client):
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[
            ("samx", "async_signal", {"signal_class": "AsyncSignal"}),
            ("samy", "async_signal", {"signal_class": "AsyncSignal"}),
            ("bpm4i", "async_signal", {"signal_class": "AsyncSignal"}),
        ]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=DeviceComboBox,
        client=mocked_client,
        signal_class_filter=["AsyncSignal"],
    )

    devices = [widget.itemText(i) for i in range(widget.count())]
    assert set(devices) == {"samx", "samy", "bpm4i"}
    assert widget.signal_class_filter == ["AsyncSignal"]
