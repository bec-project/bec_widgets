import pytest
from bec_lib.device import ReadoutPriority

from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import (
    BECDeviceFilter,
    DeviceComboBox,
)

from .client_mocks import mocked_client


@pytest.fixture
def device_input_combobox(qtbot, mocked_client):
    widget = DeviceComboBox(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def device_input_combobox_with_kwargs(qtbot, mocked_client):
    widget = DeviceComboBox(
        client=mocked_client,
        gui_id="test_gui_id",
        device_filter=[BECDeviceFilter.POSITIONER],
        default="samx",
        arg_name="test_arg_name",
    )
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_device_input_combobox_init(device_input_combobox):
    assert device_input_combobox is not None
    assert device_input_combobox.client is not None
    assert isinstance(device_input_combobox, DeviceComboBox)
    assert device_input_combobox.config.widget_class == "DeviceComboBox"
    assert device_input_combobox.isEditable() is True
    assert device_input_combobox.currentText() == ""
    assert device_input_combobox.is_valid_input is False
    assert device_input_combobox.config.device_filter == []
    assert device_input_combobox.config.readout_filter == [
        ReadoutPriority.MONITORED.value,
        ReadoutPriority.BASELINE.value,
        ReadoutPriority.ASYNC.value,
        ReadoutPriority.CONTINUOUS.value,
        ReadoutPriority.ON_REQUEST.value,
    ]
    assert device_input_combobox.config.default is None
    assert device_input_combobox.autocomplete is False
    assert device_input_combobox.completer() is not None
    assert device_input_combobox.completer().model() == device_input_combobox.model()
    assert device_input_combobox.devices == [
        "samx",
        "samy",
        "samz",
        "aptrx",
        "aptry",
        "gauss_bpm",
        "gauss_adc1",
        "gauss_adc2",
        "gauss_adc3",
        "bpm4i",
        "bpm3a",
        "bpm3i",
        "eiger",
        "waveform1d",
        "async_device",
        "test",
        "test_device",
    ]


def test_device_input_combobox_init_with_kwargs(device_input_combobox_with_kwargs):
    assert device_input_combobox_with_kwargs.config.gui_id == "test_gui_id"
    assert device_input_combobox_with_kwargs.config.device_filter == ["Positioner"]
    assert device_input_combobox_with_kwargs.config.default == "samx"
    assert device_input_combobox_with_kwargs.config.arg_name == "test_arg_name"


def test_device_input_combobox_autocomplete(qtbot, mocked_client):
    widget = DeviceComboBox(client=mocked_client, autocomplete=True)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)

    assert widget.autocomplete is True
    assert widget.completer() is not None
    assert widget.completer().model().stringList() == widget.devices
    assert widget.completer().model() != widget.model()

    widget.autocomplete = False

    assert widget.completer() is not None
    assert widget.completer().model() == widget.model()


def test_get_device_from_input_combobox_init(device_input_combobox):
    device_input_combobox.setCurrentIndex(0)
    device_text = device_input_combobox.currentText()
    current_device = device_input_combobox.get_current_device()

    assert current_device.name == device_text
