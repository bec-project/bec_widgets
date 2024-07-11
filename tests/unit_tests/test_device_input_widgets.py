import pytest

from bec_widgets.widgets.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit

from .client_mocks import mocked_client


@pytest.fixture
def device_input_combobox(qtbot, mocked_client):
    widget = DeviceComboBox(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


@pytest.fixture
def device_input_combobox_with_config(qtbot, mocked_client):
    config = {
        "widget_class": "DeviceComboBox",
        "gui_id": "test_gui_id",
        "device_filter": "FakePositioner",
        "default": "samx",
        "arg_name": "test_arg_name",
    }
    widget = DeviceComboBox(client=mocked_client, config=config)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


@pytest.fixture
def device_input_combobox_with_kwargs(qtbot, mocked_client):
    widget = DeviceComboBox(
        client=mocked_client,
        gui_id="test_gui_id",
        device_filter="FakePositioner",
        default="samx",
        arg_name="test_arg_name",
    )
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_device_input_combobox_init(device_input_combobox):
    assert device_input_combobox is not None
    assert device_input_combobox.client is not None
    assert isinstance(device_input_combobox, DeviceComboBox)
    assert device_input_combobox.config.widget_class == "DeviceComboBox"
    assert device_input_combobox.config.device_filter is None
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
        "async_device",
        "test",
    ]


def test_device_input_combobox_init_with_config(device_input_combobox_with_config):
    assert device_input_combobox_with_config.config.gui_id == "test_gui_id"
    assert device_input_combobox_with_config.config.device_filter == "FakePositioner"
    assert device_input_combobox_with_config.config.default == "samx"
    assert device_input_combobox_with_config.config.arg_name == "test_arg_name"


def test_device_input_combobox_init_with_kwargs(device_input_combobox_with_kwargs):
    assert device_input_combobox_with_kwargs.config.gui_id == "test_gui_id"
    assert device_input_combobox_with_kwargs.config.device_filter == "FakePositioner"
    assert device_input_combobox_with_kwargs.config.default == "samx"
    assert device_input_combobox_with_kwargs.config.arg_name == "test_arg_name"


def test_get_device_from_input_combobox_init(device_input_combobox):
    device_input_combobox.setCurrentIndex(0)
    device_text = device_input_combobox.currentText()
    current_device = device_input_combobox.get_device()

    assert current_device.name == device_text


@pytest.fixture
def device_input_line_edit(qtbot, mocked_client):
    widget = DeviceLineEdit(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


@pytest.fixture
def device_input_line_edit_with_config(qtbot, mocked_client):
    config = {
        "widget_class": "DeviceLineEdit",
        "gui_id": "test_gui_id",
        "device_filter": "FakePositioner",
        "default": "samx",
        "arg_name": "test_arg_name",
    }
    widget = DeviceLineEdit(client=mocked_client, config=config)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


@pytest.fixture
def device_input_line_edit_with_kwargs(qtbot, mocked_client):
    widget = DeviceLineEdit(
        client=mocked_client,
        gui_id="test_gui_id",
        device_filter="FakePositioner",
        default="samx",
        arg_name="test_arg_name",
    )
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_device_input_line_edit_init(device_input_line_edit):
    assert device_input_line_edit is not None
    assert device_input_line_edit.client is not None
    assert isinstance(device_input_line_edit, DeviceLineEdit)
    assert device_input_line_edit.config.widget_class == "DeviceLineEdit"
    assert device_input_line_edit.config.device_filter is None
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
        "async_device",
        "test",
    ]


def test_device_input_line_edit_init_with_config(device_input_line_edit_with_config):
    assert device_input_line_edit_with_config.config.gui_id == "test_gui_id"
    assert device_input_line_edit_with_config.config.device_filter == "FakePositioner"
    assert device_input_line_edit_with_config.config.default == "samx"
    assert device_input_line_edit_with_config.config.arg_name == "test_arg_name"


def test_device_input_line_edit_init_with_kwargs(device_input_line_edit_with_kwargs):
    assert device_input_line_edit_with_kwargs.config.gui_id == "test_gui_id"
    assert device_input_line_edit_with_kwargs.config.device_filter == "FakePositioner"
    assert device_input_line_edit_with_kwargs.config.default == "samx"
    assert device_input_line_edit_with_kwargs.config.arg_name == "test_arg_name"


def test_get_device_from_input_line_edit_init(device_input_line_edit):
    device_input_line_edit.setText("samx")
    device_text = device_input_line_edit.text()
    current_device = device_input_line_edit.get_device()

    assert current_device.name == device_text
