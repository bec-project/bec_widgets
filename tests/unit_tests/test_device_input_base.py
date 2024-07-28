import pytest
from qtpy.QtWidgets import QWidget

from bec_widgets.widgets.base_classes.device_input_base import DeviceInputBase

from .client_mocks import mocked_client


# DeviceInputBase is meant to be mixed in a QWidget
class DeviceInputWidget(DeviceInputBase, QWidget):
    def __init__(self, parent=None, client=None, config=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)


@pytest.fixture
def device_input_base(qtbot, mocked_client):
    widget = DeviceInputWidget(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_device_input_base_init(device_input_base):
    assert device_input_base is not None
    assert device_input_base.client is not None
    assert isinstance(device_input_base, DeviceInputBase)
    assert device_input_base.config.widget_class == "DeviceInputWidget"
    assert device_input_base.config.device_filter is None
    assert device_input_base.config.default is None
    assert device_input_base.devices == []


def test_device_input_base_init_with_config(mocked_client):
    config = {
        "widget_class": "DeviceInputWidget",
        "gui_id": "test_gui_id",
        "device_filter": "FakePositioner",
        "default": "samx",
    }
    widget = DeviceInputWidget(client=mocked_client, config=config)
    assert widget.config.gui_id == "test_gui_id"
    assert widget.config.device_filter == "FakePositioner"
    assert widget.config.default == "samx"


def test_device_input_base_set_device_filter(device_input_base):
    device_input_base.set_device_filter("FakePositioner")
    assert device_input_base.config.device_filter == "FakePositioner"


def test_device_input_base_set_device_filter_error(device_input_base):
    with pytest.raises(ValueError) as excinfo:
        device_input_base.set_device_filter("NonExistingClass")
        assert "Device filter NonExistingClass is not in the device list." in str(excinfo.value)


def test_device_input_base_set_default_device(device_input_base):
    device_input_base.set_default_device("samx")
    assert device_input_base.config.default == "samx"


def test_device_input_base_set_default_device_error(device_input_base):
    with pytest.raises(ValueError) as excinfo:
        device_input_base.set_default_device("NonExistingDevice")
        assert "Default device NonExistingDevice is not in the device list." in str(excinfo.value)


def test_device_input_base_get_device_list(device_input_base):
    devices = device_input_base.get_device_list("FakePositioner")
    assert devices == ["samx", "samy", "samz", "aptrx", "aptry"]


def test_device_input_base_get_filters(device_input_base):
    filters = device_input_base.get_available_filters()
    assert filters == {"FakePositioner", "FakeDevice", "Positioner", "Device"}
