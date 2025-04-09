from unittest.mock import MagicMock, patch

import pytest
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.settings_dialog import SettingsDialog, SettingWidget

###################################
# SettingWidget base class tests
###################################


@pytest.fixture
def setting_widget(qtbot):
    widget = SettingWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_setting_widget_initialization(setting_widget):
    assert setting_widget.target_widget is None


def test_setting_widget_set_target_widget(setting_widget):
    mock_target = MagicMock(spec=QWidget)
    setting_widget.set_target_widget(mock_target)
    assert setting_widget.target_widget == mock_target


def test_setting_widget_accept_changes(setting_widget):
    with patch.object(setting_widget, "accept_changes") as mock_accept_changes:
        setting_widget.accept_changes()
        mock_accept_changes.assert_called_once()


def test_setting_widget_display_current_settings(setting_widget):
    config_dict = {"setting1": "value1", "setting2": "value2"}
    with patch.object(setting_widget, "display_current_settings") as mock_display_current_settings:
        setting_widget.display_current_settings(config_dict)
        mock_display_current_settings.assert_called_once_with(config_dict)


###################################
# SettingsDialog tests
###################################
@pytest.fixture
def settings_dialog(qtbot, setting_widget):
    parent_widget = QWidget()
    setting_widget.set_target_widget = MagicMock()
    setting_widget.display_current_settings = MagicMock()
    setting_widget.accept_changes = MagicMock()

    dialog = SettingsDialog(
        parent=parent_widget,
        settings_widget=setting_widget,
        window_title="Test Settings",
        config={"setting1": "value1", "setting2": "value2"},
    )
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)
    yield dialog, parent_widget, setting_widget
    parent_widget.close()
    parent_widget.deleteLater()


def test_settings_dialog_initialization(settings_dialog):
    dialog, parent_widget, settings_widget = settings_dialog

    assert dialog.windowTitle() == "Test Settings"
    settings_widget.set_target_widget.assert_called_once_with(parent_widget)
    settings_widget.display_current_settings.assert_called_once_with(
        {"setting1": "value1", "setting2": "value2"}
    )


def test_settings_dialog_accept(settings_dialog, qtbot):
    dialog, _, settings_widget = settings_dialog

    dialog.button_box.buttons()[0].click()  # OK Button
    settings_widget.accept_changes.assert_called_once()


def test_settings_dialog_reject_calls_cleanup(settings_dialog, qtbot):
    dialog, _, _ = settings_dialog

    with patch.object(dialog, "cleanup") as mock_cleanup:
        dialog.button_box.buttons()[1].click()  # Cancel Button
        mock_cleanup.assert_called_once()


def test_settings_dialog_apply_changes(settings_dialog, qtbot):
    dialog, _, settings_widget = settings_dialog

    dialog.apply_button.click()
    settings_widget.accept_changes.assert_called_once()
