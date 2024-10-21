import pytest
from bec_lib.device import ReadoutPriority

from bec_widgets.widgets.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit

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
    assert device_input_combobox.config.default is None
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
    assert device_input_combobox_with_kwargs.config.device_filter == [BECDeviceFilter.POSITIONER]
    assert device_input_combobox_with_kwargs.config.default == "samx"
    assert device_input_combobox_with_kwargs.config.arg_name == "test_arg_name"


def test_get_device_from_input_combobox_init(device_input_combobox):
    device_input_combobox.setCurrentIndex(0)
    device_text = device_input_combobox.currentText()
    current_device = device_input_combobox.get_current_device()

    assert current_device.name == device_text


@pytest.fixture
def device_input_line_edit(qtbot, mocked_client):
    widget = DeviceLineEdit(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def device_input_line_edit_with_kwargs(qtbot, mocked_client):
    widget = DeviceLineEdit(
        client=mocked_client,
        gui_id="test_gui_id",
        device_filter=[BECDeviceFilter.POSITIONER],
        default="samx",
        arg_name="test_arg_name",
    )
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_device_input_line_edit_init(device_input_line_edit):
    assert device_input_line_edit is not None
    assert device_input_line_edit.client is not None
    assert isinstance(device_input_line_edit, DeviceLineEdit)
    assert device_input_line_edit.config.widget_class == "DeviceLineEdit"
    assert device_input_line_edit.config.device_filter == []
    assert device_input_line_edit.config.readout_filter == [
        ReadoutPriority.MONITORED,
        ReadoutPriority.BASELINE,
        ReadoutPriority.ASYNC,
        ReadoutPriority.CONTINUOUS,
        ReadoutPriority.ON_REQUEST,
    ]
    assert device_input_line_edit.config.default is None
    assert device_input_line_edit.devices == [
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


def test_device_input_line_edit_init_with_kwargs(device_input_line_edit_with_kwargs):
    assert device_input_line_edit_with_kwargs.config.gui_id == "test_gui_id"
    assert device_input_line_edit_with_kwargs.config.device_filter == [BECDeviceFilter.POSITIONER]
    assert device_input_line_edit_with_kwargs.config.default == "samx"
    assert device_input_line_edit_with_kwargs.config.arg_name == "test_arg_name"


def test_get_device_from_input_line_edit_init(device_input_line_edit):
    device_input_line_edit.setText("samx")
    device_text = device_input_line_edit.text()
    current_device = device_input_line_edit.get_current_device()

    assert current_device.name == device_text
