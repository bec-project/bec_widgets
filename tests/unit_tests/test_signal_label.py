from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from qtpy import QtCore
from qtpy.QtWidgets import QDialogButtonBox, QLabel

from bec_widgets.widgets.control.device_input.base_classes.device_signal_input_base import (
    DeviceSignalInputBaseConfig,
)
from bec_widgets.widgets.utility.signal_label.signal_label import ChoiceDialog, SignalLabel

from .client_mocks import mocked_client

SAMX_INFO_DICT = {
    "signals": {
        "readback": {
            "component_name": "readback",
            "obj_name": "samx",
            "kind_int": 5,
            "kind_str": "hinted",
            "doc": "",
            "describe": {"source": "SIM:samx", "dtype": "integer", "shape": [], "precision": 3},
            "metadata": {
                "connected": True,
                "read_access": True,
                "write_access": False,
                "timestamp": 123456.789,
                "status": None,
                "severity": None,
                "precision": None,
            },
        }
    },
    "setpoint": {
        "component_name": "setpoint",
        "obj_name": "samx_setpoint",
        "kind_int": 1,
        "kind_str": "normal",
        "doc": "",
        "describe": {
            "source": "SIM:samx_setpoint",
            "dtype": "integer",
            "shape": [],
            "precision": 3,
        },
        "metadata": {
            "connected": True,
            "read_access": True,
            "write_access": True,
            "timestamp": 1747657955.012516,
            "status": None,
            "severity": None,
            "precision": None,
        },
    },
}


@pytest.fixture
def signal_label(qtbot, mocked_client: MagicMock):
    with patch.object(mocked_client.device_manager.devices.samx, "_info", SAMX_INFO_DICT):
        config = DeviceSignalInputBaseConfig(device="samx", default="samx")
        widget = SignalLabel(
            config=config, custom_label="Test Label", custom_units="m/s", client=mocked_client
        )
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        widget.show()
        yield widget


def test_initialization(signal_label: SignalLabel):
    """Test the initialization of the SignalLabel widget."""
    assert signal_label.device == "Not set!"
    assert signal_label.custom_label == "Test Label"
    assert signal_label.custom_units == "m/s"
    assert signal_label.show_select_button is True
    assert signal_label.show_default_units is False
    assert signal_label.decimal_places == 3
    signal_label.set_display_value()
    assert signal_label._display.text() == ""


def test_initialization_with_device(qtbot, mocked_client: MagicMock):
    with patch.object(mocked_client.device_manager.devices.samx, "_info", SAMX_INFO_DICT):
        widget = SignalLabel(device="samx", signal="readback", client=mocked_client)
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        widget.show()
        assert widget._label.title() == "samx readback:"


def test_set_display_value(signal_label: SignalLabel, qtbot):
    qtbot.addWidget(signal_label)
    signal_label.set_display_value("123.456")
    assert signal_label._display.text() == "123.456 m/s"


def test_show_select_button(signal_label: SignalLabel, qtbot):
    assert signal_label.show_select_button == True
    qtbot.waitUntil(lambda: signal_label._select_button.isVisible(), timeout=1000)
    signal_label.show_select_button = False
    qtbot.waitUntil(lambda: not signal_label._select_button.isVisible(), timeout=1000)
    signal_label.show_select_button = True
    qtbot.waitUntil(lambda: signal_label._select_button.isVisible(), timeout=1000)


def test_show_default_units(signal_label: SignalLabel, qtbot):
    signal_label.show_default_units = True
    assert signal_label.show_default_units is True
    signal_label.show_default_units = False
    assert signal_label.show_default_units is False


def test_custom_label(signal_label: SignalLabel, qtbot):
    signal_label.custom_label = "New Label"
    assert signal_label._label.title() == "New Label"


def test_units_in_display(signal_label: SignalLabel, qtbot):
    signal_label._value = "1.8"
    signal_label._dtype = "float"
    signal_label.custom_units = "Mfurlong μfortnight⁻¹"
    assert signal_label._display.text() == "1.800 Mfurlong μfortnight⁻¹"


def test_decimal_places(signal_label: SignalLabel, qtbot):
    signal_label._dtype = "float"
    signal_label.decimal_places = 2
    signal_label.set_display_value("123.456")
    assert signal_label._display.text() == "123.46 m/s"
    signal_label.decimal_places = 0
    signal_label.set_display_value("123.456")
    assert signal_label._display.text() == "123.456 m/s"


def test_choose_signal_dialog_sends_choices(signal_label: SignalLabel, qtbot):
    signal_label._process_dialog = MagicMock()
    dialog = signal_label.show_choice_dialog()
    qtbot.waitUntil(dialog.button_box.button(QDialogButtonBox.Ok).isVisible, timeout=500)
    dialog._device_field.dev["test device"] = MagicMock()
    dialog._device_field.setText("test device")
    dialog._signal_field._signals = [("test signal", {"component_name": "test signal"})]
    dialog._signal_field.addItem("test signal")
    dialog._signal_field.setCurrentIndex(0)
    qtbot.mouseClick(dialog.button_box.button(QDialogButtonBox.Ok), QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=1000)
    signal_label._process_dialog.assert_called_once_with("test device", "test signal")


def test_dialog_handler_updates_devices(signal_label: SignalLabel, qtbot):
    dialog = signal_label.show_choice_dialog()
    qtbot.waitUntil(dialog.button_box.button(QDialogButtonBox.Ok).isVisible, timeout=500)
    dialog._device_field.dev["flux_capacitor"] = MagicMock()
    dialog._device_field.setText("flux_capacitor")
    dialog._signal_field._signals = [("spin_speed", {"component_name": "spin_speed"})]
    dialog._signal_field.addItem("spin_speed")
    dialog._signal_field.setCurrentIndex(0)
    qtbot.mouseClick(dialog.button_box.button(QDialogButtonBox.Ok), QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=1000)
    assert signal_label._device == "flux_capacitor"
    assert signal_label._signal == "spin_speed"


def test_choose_signal_dialog_invalid_device(signal_label: SignalLabel, qtbot):
    signal_label._process_dialog = MagicMock()
    dialog = signal_label.show_choice_dialog()
    qtbot.waitUntil(dialog.button_box.button(QDialogButtonBox.Ok).isVisible, timeout=500)
    dialog._device_field.setText("invalid device")
    dialog._signal_field.addItem("test signal")
    dialog._signal_field.setCurrentIndex(0)
    qtbot.mouseClick(dialog.button_box.button(QDialogButtonBox.Ok), QtCore.Qt.LeftButton)
    qtbot.wait(100)
    qtbot.mouseClick(dialog.button_box.button(QDialogButtonBox.Cancel), QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=1000)
    signal_label._process_dialog.assert_not_called()


def test_choice_dialog_with_no_client(qtbot):
    dialog = ChoiceDialog()
    qtbot.addWidget(dialog)

    assert dialog.button_box.button(QDialogButtonBox.Ok) is None
    assert dialog.button_box.button(QDialogButtonBox.Cancel) is not None
    assert dialog.layout().itemAt(0).widget().text() == ChoiceDialog.CONNECTION_ERROR_STR


def test_dialog_has_signals(signal_label: SignalLabel, qtbot):
    signal_label._process_dialog = MagicMock()
    dialog = signal_label.show_choice_dialog()
    qtbot.waitUntil(dialog.button_box.button(QDialogButtonBox.Ok).isVisible, timeout=500)
    dialog._device_field.dev["test device"] = MagicMock()
    dialog._device_field.dev["test device"]._info = {
        "signals": {"signal 1": {"kind_str": "hinted"}, "signal 2": {"kind_str": "normal"}}
    }

    dialog._device_field.setText("test device")
    assert dialog._signal_field.count() == 2  # the actual signal and the category label
    assert dialog._signal_field.currentText() == "signal 1"


def test_set_existing_device_and_signal(signal_label: SignalLabel, qtbot):
    signal_label.device = "samx"
    signal_label.signal = "readback"
    assert signal_label._device == "samx"
    assert signal_label._config.device == "samx"
    assert signal_label._signal == "readback"
    assert signal_label._config.default == "readback"


def test_set_nonexisting_device_and_signal(signal_label: SignalLabel, qtbot):
    signal_label.custom_units = ""
    signal_label.device = "samq"
    signal_label.signal = "readfront"
    assert signal_label._device == "samq"
    assert signal_label._config.device == "samq"
    signal_label._manual_read()
    signal_label.set_display_value(signal_label._value)
    assert signal_label._display.text() == "__"
    assert signal_label._signal == "readfront"
    assert signal_label._config.default == "readfront"
    signal_label._manual_read()
    signal_label.set_display_value(signal_label._value)
    assert signal_label._display.text() == "__"


def test_handle_readback(signal_label: SignalLabel, qtbot):
    signal_label.device = "samx"
    signal_label.signal = "readback"
    signal_label.custom_units = "μm"
    signal_label._dtype = "float"
    signal_label.on_device_readback({"random": {"stuff": "in", "corrupted": "reading"}}, {})
    assert signal_label._display.text() == "ERROR!"
    assert "Error processing incoming reading" in signal_label._display.toolTip()
    signal_label.on_device_readback(
        {
            "signals": {
                "samx": {"value": 0.9927490347496489, "timestamp": 1747662246.3741279},
                "samx_setpoint": {"value": 1.0, "timestamp": 1747662246.368704},
                "samx_motor_is_moving": {"value": 0, "timestamp": 1747662246.373092},
            }
        },
        {},
    )
    assert signal_label._display.text() == "0.993 μm"
    assert signal_label._display.toolTip() == ""
