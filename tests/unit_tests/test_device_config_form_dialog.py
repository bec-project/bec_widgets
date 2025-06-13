from unittest.mock import MagicMock, patch

import pytest
from bec_lib.atlas_models import Device as DeviceConfigModel

from bec_widgets.widgets.services.device_browser.device_item.device_config_dialog import (
    DeviceConfigDialog,
)

_BASIC_CONFIG = {
    "name": "test_device",
    "enabled": True,
    "deviceClass": "TestDevice",
    "readoutPriority": "monitored",
}


@pytest.fixture
def dialog(qtbot):
    """Fixture to create a DeviceConfigDialog instance."""
    mock_device = MagicMock(_config=DeviceConfigModel.model_validate(_BASIC_CONFIG).model_dump())
    mock_client = MagicMock()
    mock_client.device_manager.devices = {"test_device": mock_device}
    dialog = DeviceConfigDialog(device="test_device", config_helper=MagicMock(), client=mock_client)
    qtbot.addWidget(dialog)
    return dialog


def test_initialization(dialog):
    assert dialog._device == "test_device"
    assert dialog._container.count() == 2


def test_fill_form(dialog):
    with patch.object(dialog._form, "set_data") as mock_set_data:
        dialog._fill_form()
        mock_set_data.assert_called_once_with(DeviceConfigModel.model_validate(_BASIC_CONFIG))


def test_updated_config(dialog):
    """Test that updated_config returns the correct changes."""
    dialog._initial_config = {"key1": "value1", "key2": "value2"}
    with patch.object(
        dialog._form, "get_form_data", return_value={"key1": "value1", "key2": "new_value"}
    ):
        updated = dialog.updated_config()
        assert updated == {"key2": "new_value"}


def test_apply(dialog):
    with patch.object(dialog, "_process_update_action") as mock_process_update:
        dialog.apply()
        mock_process_update.assert_called_once()


def test_accept(dialog):
    with (
        patch.object(dialog, "_process_update_action") as mock_process_update,
        patch("qtpy.QtWidgets.QDialog.accept") as mock_parent_accept,
    ):
        dialog.accept()
        mock_process_update.assert_called_once()
        mock_parent_accept.assert_called_once()


def test_waiting_display(dialog, qtbot):
    with (
        patch.object(dialog._spinner, "start") as mock_spinner_start,
        patch.object(dialog._spinner, "stop") as mock_spinner_stop,
    ):
        dialog.show()
        dialog._start_waiting_display()
        qtbot.waitUntil(dialog._overlay_widget.isVisible, timeout=100)
        mock_spinner_start.assert_called_once()
        mock_spinner_stop.assert_not_called()
        dialog._stop_waiting_display()
        qtbot.waitUntil(lambda: not dialog._overlay_widget.isVisible(), timeout=100)
        mock_spinner_stop.assert_called_once()


def test_update_cycle(dialog, qtbot):
    update = {"enabled": False, "readoutPriority": "baseline", "deviceTags": ["tag"]}

    def _mock_send(a, c, w):
        dialog.client.device_manager.devices["test_device"]._config = c["test_device"]

    dialog._config_helper.send_config_request = MagicMock(side_effect=_mock_send)
    for item in dialog._form.enumerate_form_widgets():
        if (val := update.get(item.label.property("_model_field_name"))) is not None:
            item.widget.setValue(val)

    assert dialog.updated_config() == update
    dialog.apply()
    qtbot.waitUntil(lambda: dialog._config_helper.send_config_request.call_count == 1, timeout=100)

    dialog._config_helper.send_config_request.assert_called_with(
        action="update", config={"test_device": update}, wait_for_response=False
    )
