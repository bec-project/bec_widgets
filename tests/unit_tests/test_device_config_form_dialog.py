from unittest.mock import MagicMock, patch

import pytest
from bec_lib.atlas_models import Device as DeviceConfigModel
from qtpy.QtWidgets import QDialogButtonBox, QPushButton

from bec_widgets.utils.forms_from_types.items import StrFormItem
from bec_widgets.widgets.services.device_browser.device_item.device_config_dialog import (
    DirectUpdateDeviceConfigDialog,
    _try_literal_eval,
)

_BASIC_CONFIG = {
    "name": "test_device",
    "enabled": True,
    "deviceClass": "TestDevice",
    "readoutPriority": "monitored",
}


@pytest.fixture
def mock_client():
    mock_device = MagicMock(_config=DeviceConfigModel.model_validate(_BASIC_CONFIG).model_dump())
    mock_client = MagicMock()
    mock_client.device_manager.devices = {"test_device": mock_device}
    return mock_client


@pytest.fixture
def update_dialog(mock_client, qtbot):
    """Fixture to create a DeviceConfigDialog instance."""
    update_dialog = DirectUpdateDeviceConfigDialog(
        device="test_device", config_helper=MagicMock(), client=mock_client
    )
    qtbot.addWidget(update_dialog)
    return update_dialog


@pytest.fixture
def add_dialog(mock_client, qtbot):
    """Fixture to create a DeviceConfigDialog instance."""
    add_dialog = DirectUpdateDeviceConfigDialog(
        device=None, config_helper=MagicMock(), client=mock_client, action="add"
    )
    qtbot.addWidget(add_dialog)
    return add_dialog


def test_initialization(update_dialog):
    assert update_dialog._device == "test_device"
    assert update_dialog._container.count() == 2


def test_fill_form(update_dialog):
    with patch.object(update_dialog._form, "set_data") as mock_set_data:
        update_dialog._fill_form()
        mock_set_data.assert_called_once_with(DeviceConfigModel.model_validate(_BASIC_CONFIG))


def test_updated_config(update_dialog):
    """Test that updated_config returns the correct changes."""
    update_dialog._initial_config = {"key1": "value1", "key2": "value2"}
    with patch.object(
        update_dialog._form, "get_form_data", return_value={"key1": "value1", "key2": "new_value"}
    ):
        updated = update_dialog.updated_config()
        assert updated == {"key2": "new_value"}


def test_apply(update_dialog):
    with patch.object(update_dialog, "_process_action") as mock_process_update:
        update_dialog.apply()
        mock_process_update.assert_called_once()


def test_accept(update_dialog):
    with (
        patch.object(update_dialog, "_process_action") as mock_process_update,
        patch("qtpy.QtWidgets.QDialog.accept") as mock_parent_accept,
    ):
        update_dialog.accept()
        mock_process_update.assert_called_once()
        mock_parent_accept.assert_called_once()


def test_waiting_display(update_dialog, qtbot):
    with (
        patch.object(update_dialog._spinner, "start") as mock_spinner_start,
        patch.object(update_dialog._spinner, "stop") as mock_spinner_stop,
    ):
        update_dialog.show()
        update_dialog._start_waiting_display()
        qtbot.waitUntil(update_dialog._overlay_widget.isVisible, timeout=100)
        mock_spinner_start.assert_called_once()
        mock_spinner_stop.assert_not_called()
        update_dialog._stop_waiting_display()
        qtbot.waitUntil(lambda: not update_dialog._overlay_widget.isVisible(), timeout=100)
        mock_spinner_stop.assert_called_once()


def test_update_cycle(update_dialog, qtbot):
    update = {"enabled": False, "readoutPriority": "baseline", "deviceTags": {"tag"}}

    def _mock_send(action="update", config=None, wait_for_response=True, timeout_s=None):
        update_dialog.client.device_manager.devices["test_device"]._config = config["test_device"]  # type: ignore

    update_dialog._config_helper.send_config_request = MagicMock(side_effect=_mock_send)
    for item in update_dialog._form.enumerate_form_widgets():
        if (val := update.get(item.label.property("_model_field_name"))) is not None:
            item.widget.setValue(val)

    assert update_dialog.updated_config() == update
    update_dialog.apply()
    qtbot.waitUntil(
        lambda: update_dialog._config_helper.send_config_request.call_count == 1, timeout=100
    )

    update_dialog._config_helper.send_config_request.assert_called_with(
        action="update", config={"test_device": update}, wait_for_response=False
    )


@pytest.mark.parametrize(
    ["changes", "result"],
    [
        ({}, {}),
        ({"readOnly": True}, {"readOnly": True}),
        ({"readOnly": False}, {}),
        ({"readOnly": True, "description": "test"}, {"readOnly": True, "description": "test"}),
        (
            {"deviceConfig": {"param1": "'val1'"}},
            {
                "enabled": True,
                "deviceClass": "TestDevice",
                "deviceConfig": {"param1": "val1"},
                "readoutPriority": "monitored",
                "description": None,
                "readOnly": False,
                "softwareTrigger": False,
                "onFailure": "retry",
                "deviceTags": set(),
                "userParameter": {},
                "name": "test_device",
            },
        ),
        ({"deviceConfig": {}}, {}),
    ],
)
def test_update_with_modified_deviceconfig(update_dialog, changes, result):
    for k, v in changes.items():
        update_dialog._form.widget_dict[k].setValue(v)
    assert update_dialog.updated_config() == result


def test_add_form_init_without_name(add_dialog, qtbot):
    assert (name_widget := add_dialog._form.widget_dict.get("name")) is not None
    assert isinstance(name_widget, StrFormItem)
    assert name_widget.getValue() is None


def test_add_form_validates_and_disables_on_init(add_dialog, qtbot):
    assert (ok_button := add_dialog.button_box.button(QDialogButtonBox.Ok)) is not None
    assert isinstance(ok_button, QPushButton)
    assert not ok_button.isEnabled()


def test_try_literal_eval():
    assert _try_literal_eval("") == ""
    assert _try_literal_eval("[1, 2, 3]") == [1, 2, 3]
    assert _try_literal_eval('"[,,]"') == "[,,]"
    with pytest.raises(ValueError) as e:
        _try_literal_eval("[,,]")
        assert e.match("Entered config value [,,]")
