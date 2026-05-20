from unittest import mock

import pytest
from bec_lib.device import Signal

from bec_widgets.utils.ophyd_kind_util import Kind
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import (
    BECDeviceFilter,
    DeviceComboBox,
)
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import (
    SignalComboBox,
    SignalComboBoxConfig,
)

from .client_mocks import mocked_client
from .conftest import create_widget


class FakeSignal(Signal):
    """Fake signal used by SignalComboBox tests."""


def signal_names(signals):
    return [entry[0] if isinstance(entry, tuple) else entry for entry in signals]


@pytest.fixture
def device_signal_combobox(qtbot, mocked_client):
    widget = create_widget(qtbot=qtbot, widget=SignalComboBox, client=mocked_client)
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


def test_signal_combobox_init(device_signal_combobox):
    assert device_signal_combobox._device is None
    assert device_signal_combobox._signal_filter == {Kind.config, Kind.normal, Kind.hinted}
    assert device_signal_combobox._signals == []
    assert device_signal_combobox._hinted_signals == []
    assert device_signal_combobox._normal_signals == []
    assert device_signal_combobox._config_signals == []
    assert device_signal_combobox.autocomplete is False
    assert device_signal_combobox.completer() is not None
    assert device_signal_combobox.completer().model() == device_signal_combobox.model()


def test_signal_combobox_config_defaults_are_independent_lists():
    config_a = SignalComboBoxConfig(widget_class="SignalComboBox")
    config_b = SignalComboBoxConfig(widget_class="SignalComboBox")

    config_a.signal_filter.append("hinted")
    config_a.signal_class_filter.append("AsyncSignal")
    config_a.signals.append("sig")

    assert config_b.signal_filter == []
    assert config_b.signal_class_filter == []
    assert config_b.signals == []


def test_signal_combobox_autocomplete(qtbot, mocked_client):
    widget = create_widget(
        qtbot=qtbot, widget=SignalComboBox, client=mocked_client, autocomplete=True
    )
    line_edit = widget.lineEdit()
    text_changes: list[str] = []
    line_edit.setPlaceholderText("Select Signal")
    line_edit.textChanged.connect(text_changes.append)

    widget.set_device("samx")

    assert widget.autocomplete is True
    assert widget.completer() is not None
    assert widget.completer().model().stringList() == ["samx (readback)", "setpoint", "velocity"]
    assert widget.completer().model() != widget.model()

    widget.autocomplete = False

    assert widget.completer() is not None
    assert widget.completer().model() == widget.model()
    assert widget.lineEdit().placeholderText() == "Select Signal"

    widget.lineEdit().setText("manual_signal")

    assert text_changes[-1] == "manual_signal"


def test_signal_combobox_qproperties(device_signal_combobox):
    device_signal_combobox.include_config_signals = False
    device_signal_combobox.include_normal_signals = False
    device_signal_combobox.include_hinted_signals = False
    assert device_signal_combobox._signal_filter == set()
    device_signal_combobox.include_config_signals = True
    assert device_signal_combobox._signal_filter == {Kind.config}
    device_signal_combobox.include_normal_signals = True
    assert device_signal_combobox._signal_filter == {Kind.config, Kind.normal}
    device_signal_combobox.include_hinted_signals = True
    assert device_signal_combobox._signal_filter == {Kind.config, Kind.normal, Kind.hinted}
    device_signal_combobox.include_hinted_signals = False
    assert device_signal_combobox._signal_filter == {Kind.config, Kind.normal}


def test_signal_combobox_disabled_invalid_has_neutral_border(device_signal_combobox):
    device_signal_combobox.setCurrentText("manual_signal")
    assert "red" in device_signal_combobox.styleSheet()

    device_signal_combobox.setEnabled(False)
    assert "transparent" in device_signal_combobox.styleSheet()

    device_signal_combobox.setEnabled(True)
    assert "red" in device_signal_combobox.styleSheet()


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


def test_linked_device_combobox_updates_signal_combobox_on_each_text_change(
    qtbot, test_device_signal_combo
):
    device, signal = test_device_signal_combo
    device.currentTextChanged.connect(signal.set_device)

    emitted_device_texts: list[str] = []
    device.currentTextChanged.connect(emitted_device_texts.append)

    device.setCurrentText("samx")
    assert signal.device == "samx"
    assert signal.currentText() == "samx (readback)"

    device.setCurrentText("sa")

    assert emitted_device_texts[-1] == "sa"
    assert signal.device == ""
    assert signal.signals == []
    assert signal.currentText() == ""
    assert signal.is_valid_input is False

    device.setCurrentText("samx")

    assert emitted_device_texts[-1] == "samx"
    assert signal.device == "samx"
    assert [entry[0] for entry in signal.signals] == ["samx (readback)", "setpoint", "velocity"]


def test_device_signal_input_base_cleanup(qtbot, mocked_client):
    with mock.patch.object(mocked_client.callbacks, "remove"):
        widget = SignalComboBox(client=mocked_client)
        callback_id = widget._device_update_register
        widget.close()
        widget.deleteLater()

        mocked_client.callbacks.remove.assert_called_once_with(callback_id)
        assert widget._device_update_register is None


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

    assert signal_names(widget.signals) == ["samx_readback_async"]
    assert widget.signal_class_filter == ["AsyncSignal"]

    widget.set_device("samy")
    assert signal_names(widget.signals) == ["samy_readback_async"]


def test_signal_combobox_signal_class_filter_selects_by_metadata(qtbot, mocked_client):
    """Class-based signal lists should support obj_name/component_name lookup."""
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[
            (
                "eiger",
                "image",
                {
                    "obj_name": "eiger_image",
                    "component_name": "det.image",
                    "signal_class": "PreviewSignal",
                    "describe": {"signal_info": {"ndim": 2}},
                },
            )
        ]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=SignalComboBox,
        client=mocked_client,
        signal_class_filter=["PreviewSignal"],
        ndim_filter=[2],
        device="eiger",
    )

    assert widget.validate_signal("eiger_image") is True
    assert widget.validate_signal("det.image") is True
    assert widget.set_to_obj_name("eiger_image") is True
    assert widget.currentText() == "image"

    widget.set_signal("det.image")

    assert widget.currentText() == "image"


def test_signal_combobox_signal_class_update_revalidates_selected_signal(qtbot, mocked_client):
    """Signal-class rebuilds should validate after items and signal metadata are in sync."""
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[
            (
                "eiger",
                "img",
                {
                    "obj_name": "img",
                    "signal_class": "PreviewSignal",
                    "describe": {"signal_info": {"ndim": 2}},
                },
            )
        ]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=SignalComboBox,
        client=mocked_client,
        signal_class_filter=["PreviewSignal"],
        ndim_filter=[2],
        require_device=True,
    )

    widget.set_device("eiger")

    assert widget.currentText() == "img"
    assert widget.is_valid_input is True


def test_signal_combobox_signal_class_refresh_preserves_manual_text(qtbot, mocked_client):
    mocked_client.device_manager.get_bec_signals = mock.MagicMock(
        return_value=[
            (
                "eiger",
                "img",
                {
                    "obj_name": "img",
                    "signal_class": "PreviewSignal",
                    "describe": {"signal_info": {"ndim": 2}},
                },
            )
        ]
    )
    widget = create_widget(
        qtbot=qtbot,
        widget=SignalComboBox,
        client=mocked_client,
        signal_class_filter=["PreviewSignal"],
        ndim_filter=[2],
        require_device=True,
    )

    widget.set_device("eiger")
    widget.setCurrentText("manual_signal")
    widget.update_signals_from_signal_classes()

    assert widget.currentText() == "manual_signal"
    assert widget.is_valid_input is False


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
    assert signal_names(widget.signals) == ["samx_readback_async"]

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
    assert signal_names(widget.signals) == ["samx_readback_async"]

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
    assert signal_names(widget.signals) == ["sig1"]

    # Enable config kinds and widen ndim to include sig2
    widget.include_config_signals = True
    widget.ndim_filter = 2
    assert signal_names(widget.signals) == ["sig2"]


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
    assert signal_names(widget.signals) == ["sig1"]

    resets: list[str] = []
    widget.signal_reset.connect(lambda: resets.append("reset"))
    widget.check_validity("")
    assert resets == ["reset"]
