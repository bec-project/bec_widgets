from unittest import mock

import pytest
from bec_lib.device import Signal
from qtpy.QtWidgets import QWidget

from bec_widgets.tests.utils import create_widget
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


class FakeSignal(Signal):
    """Fake signal to test the DeviceSignalInputBase."""


class DeviceInputWidget(DeviceSignalInputBase, QWidget):
    """Thin wrapper around DeviceInputBase to make it a QWidget"""


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
    assert device_signal_base._signal_filter == set()
    assert device_signal_base._signals == []
    assert device_signal_base._hinted_signals == []
    assert device_signal_base._normal_signals == []
    assert device_signal_base._config_signals == []


def test_device_signal_qproperties(device_signal_base):
    """Test if the DeviceSignalInputBase has the correct QProperties"""
    assert device_signal_base._signal_filter == set()
    device_signal_base.include_config_signals = False
    device_signal_base.include_normal_signals = False
    assert device_signal_base._signal_filter == set()
    device_signal_base.include_config_signals = True
    assert device_signal_base._signal_filter == {Kind.config}
    device_signal_base.include_normal_signals = True
    assert device_signal_base._signal_filter == {Kind.config, Kind.normal}
    device_signal_base.include_hinted_signals = True
    assert device_signal_base._signal_filter == {Kind.config, Kind.normal, Kind.hinted}
    device_signal_base.include_hinted_signals = True
    assert device_signal_base._signal_filter == {Kind.config, Kind.normal, Kind.hinted}
    device_signal_base.include_hinted_signals = True
    assert device_signal_base._signal_filter == {Kind.config, Kind.normal, Kind.hinted}
    device_signal_base.include_hinted_signals = False
    assert device_signal_base._signal_filter == {Kind.config, Kind.normal}


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
    samx = device_signal_combobox.dev.samx
    assert device_signal_combobox.signals == [
        ("samx (readback)", samx._info["signals"].get("readback")),
        ("setpoint", samx._info["signals"].get("setpoint")),
        ("velocity", samx._info["signals"].get("velocity")),
    ]
    qtbot.wait(100)
    assert container == ["samx (readback)"]
    # Set the type of class from the FakeDevice to Signal
    fake_signal = FakeSignal(name="fake_signal", info={"device_info": {"signals": {}}})
    device_signal_combobox.client.device_manager.add_devices([fake_signal])
    device_signal_combobox.set_device("fake_signal")
    fake_signal = device_signal_combobox.dev.fake_signal
    assert device_signal_combobox.signals == [
        ("fake_signal", fake_signal._info["signals"].get("fake_signal", {}))
    ]
    assert device_signal_combobox._config_signals == []
    assert device_signal_combobox._normal_signals == []
    assert device_signal_combobox._hinted_signals == [("fake_signal", {})]


def test_signal_lineedit(device_signal_line_edit):
    """Test the signal_combobox"""

    assert device_signal_line_edit._signals == []
    device_signal_line_edit.include_normal_signals = True
    device_signal_line_edit.include_hinted_signals = True
    device_signal_line_edit.include_config_signals = True
    assert device_signal_line_edit.signals == []
    device_signal_line_edit.set_device("samx")
    assert device_signal_line_edit.signals == ["readback", "setpoint", "velocity"]
    device_signal_line_edit.set_signal("readback")
    assert device_signal_line_edit.text() == "readback"
    assert device_signal_line_edit._is_valid_input is True
    device_signal_line_edit.setText("invalid")
    assert device_signal_line_edit._is_valid_input is False


def test_device_signal_input_base_cleanup(qtbot, mocked_client):
    with mock.patch.object(mocked_client.callbacks, "remove"):
        widget = DeviceInputWidget(client=mocked_client)
        widget.close()
        widget.deleteLater()

        mocked_client.callbacks.remove.assert_called_once_with(widget._device_update_register)


def test_signal_combobox_get_signal_name_with_item_data(qtbot, device_signal_combobox):
    """Test get_signal_name returns obj_name from item data when available."""
    device_signal_combobox.include_normal_signals = True
    device_signal_combobox.include_hinted_signals = True
    device_signal_combobox.set_device("samx")

    # Select a signal that has item data with obj_name
    device_signal_combobox.setCurrentText("samx (readback)")

    # get_signal_name should return the obj_name from item data
    signal_name = device_signal_combobox.get_signal_name()
    assert signal_name == "samx"


def test_signal_combobox_get_signal_name_without_item_data(qtbot, device_signal_combobox):
    """Test get_signal_name returns currentText when no item data available."""
    # Add a custom item without item data
    device_signal_combobox.addItem("custom_signal")
    device_signal_combobox.setCurrentText("custom_signal")

    signal_name = device_signal_combobox.get_signal_name()
    assert signal_name == "custom_signal"


def test_signal_combobox_get_signal_name_not_found(qtbot, device_signal_combobox):
    """Test get_signal_name when text is not found in combobox (index == -1)."""
    # Set editable to allow text that's not in items
    device_signal_combobox.setEditable(True)
    device_signal_combobox.setCurrentText("nonexistent_signal")

    signal_name = device_signal_combobox.get_signal_name()
    assert signal_name == "nonexistent_signal"


def test_signal_combobox_get_signal_name_empty(qtbot, device_signal_combobox):
    """Test get_signal_name when combobox is empty."""
    device_signal_combobox.clear()
    device_signal_combobox.setEditable(True)
    device_signal_combobox.setCurrentText("")

    signal_name = device_signal_combobox.get_signal_name()
    assert signal_name == ""


def test_signal_combobox_get_signal_name_with_velocity(qtbot, device_signal_combobox):
    """Test get_signal_name with velocity signal."""
    device_signal_combobox.include_normal_signals = True
    device_signal_combobox.include_hinted_signals = True
    device_signal_combobox.include_config_signals = True
    device_signal_combobox.set_device("samx")

    # Select velocity signal
    device_signal_combobox.setCurrentText("velocity")

    signal_name = device_signal_combobox.get_signal_name()
    assert signal_name == "samx_velocity"


def test_signal_combobox_get_signal_config(device_signal_combobox):
    device_signal_combobox.include_normal_signals = True
    device_signal_combobox.include_hinted_signals = True
    device_signal_combobox.set_device("samx")

    index = device_signal_combobox.currentIndex()
    assert index != -1

    expected_config = device_signal_combobox.itemData(index)
    assert expected_config is not None
    assert device_signal_combobox.get_signal_config() == expected_config


def test_signal_combobox_get_signal_config_disabled(qtbot, mocked_client):
    combobox = create_widget(
        qtbot=qtbot, widget=SignalComboBox, client=mocked_client, store_signal_config=False
    )
    combobox.include_normal_signals = True
    combobox.include_hinted_signals = True
    combobox.set_device("samx")
    assert combobox.get_signal_config() is None


def test_signal_combobox_signal_class_filter_by_device(qtbot, mocked_client):
    """Test signal_class_filter restricts signals to the selected device."""
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[
            ("samx", "samx_readback_async", {"obj_name": "samx_readback_async"}),
            ("samy", "samy_readback_async", {"obj_name": "samy_readback_async"}),
            ("bpm4i", "bpm4i_value_async", {"obj_name": "bpm4i_value_async"}),
        ]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=SignalComboBox,
        client=mocked_client,
        signal_class_filter=["AsyncSignal"],
        device="samx",
    )

    assert widget.signals == ["samx_readback_async"]
    assert widget.signal_class_filter == ["AsyncSignal"]

    widget.set_device("samy")
    assert widget.signals == ["samy_readback_async"]


def test_signal_class_filter_setter_clears_to_kind_filters(qtbot, mocked_client):
    """Clearing signal_class_filter should rebuild list using Kind filters."""
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[("samx", "samx_readback_async", {"obj_name": "samx_readback_async"})]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=SignalComboBox,
        client=mocked_client,
        signal_class_filter=["AsyncSignal"],
        device="samx",
    )
    assert widget.signals == ["samx_readback_async"]

    widget.signal_class_filter = []
    samx = widget.dev.samx
    assert widget.signals == [
        ("samx (readback)", samx._info["signals"].get("readback")),
        ("setpoint", samx._info["signals"].get("setpoint")),
        ("velocity", samx._info["signals"].get("velocity")),
    ]


def test_signal_class_filter_setter_none_reverts_to_kind_filters(qtbot, mocked_client):
    """Setting signal_class_filter to None should revert to Kind-based filtering."""
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[("samx", "samx_readback_async", {"obj_name": "samx_readback_async"})]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=SignalComboBox,
        client=mocked_client,
        signal_class_filter=["AsyncSignal"],
        device="samx",
    )
    assert widget.signals == ["samx_readback_async"]

    widget.signal_class_filter = None
    samx = widget.dev.samx
    assert widget.signals == [
        ("samx (readback)", samx._info["signals"].get("readback")),
        ("setpoint", samx._info["signals"].get("setpoint")),
        ("velocity", samx._info["signals"].get("velocity")),
    ]


def test_signal_combobox_set_first_element_as_empty(qtbot, mocked_client):
    """set_first_element_as_empty should insert/remove the empty option."""
    widget = create_widget(qtbot=qtbot, widget=SignalComboBox, client=mocked_client)
    widget.addItem("item1")
    widget.addItem("item2")

    widget.set_first_element_as_empty = True
    assert widget.itemText(0) == ""

    widget.set_first_element_as_empty = False
    assert widget.itemText(0) == "item1"


def test_signal_combobox_class_kind_ndim_filters(qtbot, mocked_client):
    """Test class + kind + ndim filters are all applied together."""
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[
            (
                "samx",
                "sig1",
                {
                    "obj_name": "samx_sig1",
                    "kind_str": "hinted",
                    "describe": {"signal_info": {"ndim": 1}},
                },
            ),
            (
                "samx",
                "sig2",
                {
                    "obj_name": "samx_sig2",
                    "kind_str": "config",
                    "describe": {"signal_info": {"ndim": 2}},
                },
            ),
            (
                "samy",
                "sig3",
                {
                    "obj_name": "samy_sig3",
                    "kind_str": "normal",
                    "describe": {"signal_info": {"ndim": 1}},
                },
            ),
        ]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=SignalComboBox,
        client=mocked_client,
        signal_class_filter=["AsyncSignal"],
        ndim_filter=1,
        device="samx",
    )

    # Default kinds are hinted + normal, ndim=1, device=samx
    assert widget.signals == ["sig1"]

    # Enable config kinds and widen ndim to include sig2
    widget.include_config_signals = True
    widget.ndim_filter = 2
    assert widget.signals == ["sig2"]


def test_signal_combobox_require_device_validation(qtbot, mocked_client):
    """Require device should block validation and list updates without a device."""
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[
            (
                "samx",
                "sig1",
                {
                    "obj_name": "samx_sig1",
                    "kind_str": "hinted",
                    "describe": {"signal_info": {"ndim": 1}},
                },
            )
        ]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=SignalComboBox,
        client=mocked_client,
        signal_class_filter=["AsyncSignal"],
        require_device=True,
    )

    assert widget.signals == []
    widget.set_device("samx")
    assert widget.signals == ["sig1"]

    resets: list[str] = []
    widget.signal_reset.connect(lambda: resets.append("reset"))
    widget.check_validity("")
    assert resets == ["reset"]
