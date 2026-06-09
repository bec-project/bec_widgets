from typing import Any, Generator

import pytest
import shiboken6
from bec_lib import bl_states
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtWidgets import QMessageBox, QStyleOptionViewItem

from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.services.beamline_states import beamline_state_pill as pill_module
from bec_widgets.widgets.services.beamline_states.beamline_state_pill import (
    BeamlineStateManager,
    BeamlineStatePill,
)
from bec_widgets.widgets.services.beamline_states.dialogs import AddBeamlineStateDialog

from .client_mocks import mocked_client


@pytest.fixture
def pill(qtbot, mocked_client) -> Generator[BeamlineStatePill, Any, None]:
    widget = BeamlineStatePill(state_name="shutter_open", title="Shutter", client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_beamline_state_pill_updates_from_message(pill):
    pill.update_state({"name": "shutter_open", "status": "valid", "label": "Shutter is open."}, {})

    assert pill._state_name == "shutter_open"
    assert pill._name_label.text() == "Shutter"
    assert pill._status_label.text() == "VALID"
    assert pill._detail_label.text() == "Shutter is open."
    assert not pill._icon_label.pixmap().isNull()
    assert pill.toolTip() == "Shutter is open."


def test_beamline_state_pill_ignores_other_states(pill):
    pill.update_state(
        {"name": "other_state", "status": "invalid", "label": "Should be ignored."}, {}
    )

    assert pill._status_label.text() == "UNKNOWN"
    assert pill.toolTip() == "No state information available."


def test_beamline_state_pill_expands_and_emits_updated_limits(qtbot, mocked_client):
    widget = BeamlineStatePill(state_name="limits", title="Limits", client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    widget.set_state_config(
        {
            "name": "limits",
            "title": "Limits",
            "state_type": "DeviceWithinLimitsState",
            "parameters": {
                "name": "limits",
                "title": "Limits",
                "device": "samx",
                "signal": "samx",
                "low_limit": 0.0,
                "high_limit": 10.0,
                "tolerance": 0.1,
            },
        }
    )

    assert widget._settings.isHidden()
    assert widget._config_form is None
    assert not widget._update_button.isEnabled()
    assert not widget._revert_button.isEnabled()

    qtbot.mouseClick(widget._header, Qt.MouseButton.LeftButton)
    assert widget._config_form is not None
    high_limit = widget._config_form.input_widget("high_limit")
    high_limit.setValue(20.0)

    assert not widget._settings.isHidden()
    assert widget._update_button.isEnabled()
    assert widget._revert_button.isEnabled()
    assert widget._config_form.field_widget("high_limit").property("beamlineStateDirty") is True
    assert widget._config_form.get_data()["device"] == "samx"
    assert widget.edited_config().high_limit == 20.0

    with qtbot.waitSignal(widget.update_requested) as signal:
        widget._update_button.click()

    assert signal.args[0] == "limits"
    assert isinstance(signal.args[1], bl_states.DeviceWithinLimitsState.CONFIG_CLASS)
    assert signal.args[1].device == "samx"
    assert signal.args[1].signal == "samx"
    assert signal.args[1].low_limit == 0.0
    assert signal.args[1].high_limit == 20.0
    assert signal.args[1].tolerance == 0.1
    assert not widget._settings.isHidden()


def test_beamline_state_pill_first_expand_uses_config_class_without_rebuild(
    qtbot, mocked_client, monkeypatch
):
    set_model_calls = []
    original_set_model = pill_module.PydanticWidgetForm.set_model

    def set_model_spy(self, model, data=None):
        set_model_calls.append(model)
        return original_set_model(self, model, data=data)

    monkeypatch.setattr(pill_module.PydanticWidgetForm, "set_model", set_model_spy)
    widget = BeamlineStatePill(state_name="limits", title="Limits", client=mocked_client)
    qtbot.addWidget(widget)
    widget.set_state_config(
        {
            "name": "limits",
            "title": "Limits",
            "state_type": "DeviceWithinLimitsState",
            "parameters": {
                "device": "samx",
                "signal": "samx",
                "low_limit": 0.0,
                "high_limit": 10.0,
                "tolerance": 0.1,
            },
        }
    )

    widget.set_expanded(True)
    assert widget._config_form is not None
    assert set_model_calls == []


def test_beamline_state_pill_reverts_changed_settings(qtbot, mocked_client):
    widget = BeamlineStatePill(state_name="limits", title="Limits", client=mocked_client)
    qtbot.addWidget(widget)
    widget.set_state_config(
        {
            "name": "limits",
            "title": "Limits",
            "state_type": "DeviceWithinLimitsState",
            "parameters": {
                "device": "samx",
                "signal": "samx",
                "low_limit": 0.0,
                "high_limit": 10.0,
                "tolerance": 0.1,
            },
        }
    )

    widget.set_expanded(True)
    assert widget._config_form is not None
    low_limit = widget._config_form.input_widget("low_limit")
    low_limit.setValue(-5.0)

    assert widget._update_button.isEnabled()
    assert widget._config_form.field_widget("low_limit").property("beamlineStateDirty") is True

    widget._revert_button.click()

    assert low_limit.value() == 0.0
    assert not widget._update_button.isEnabled()
    assert not widget._revert_button.isEnabled()
    assert widget._config_form.field_widget("low_limit").property("beamlineStateDirty") is False


def test_beamline_state_pill_does_not_override_themed_input_controls(qtbot, mocked_client):
    widget = BeamlineStatePill(state_name="limits", title="Limits", client=mocked_client)
    qtbot.addWidget(widget)
    widget.set_expanded(True)

    stylesheet = widget.styleSheet()

    assert "QAbstractSpinBox" not in stylesheet
    assert "QComboBox" not in stylesheet
    assert "QCheckBox::indicator" not in stylesheet


def test_beamline_state_manager_adds_and_removes_pills(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)

    widget.update_available_states(
        {
            "states": [
                messages.BeamlineStateConfig(
                    name="shutter_open", title="Shutter", state_type="ShutterState", parameters={}
                ),
                {
                    "name": "limits",
                    "title": "Limits",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {},
                },
            ]
        },
        {},
    )

    assert sorted(widget._state_pills) == ["limits", "shutter_open"]
    assert widget._model.rowCount() == 2
    assert widget._state_pills["shutter_open"]._name_label.text() == "Shutter"
    assert not widget._empty_label.isVisible()

    widget.update_available_states(
        {
            "states": [
                {
                    "name": "limits",
                    "title": "Limits",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {},
                }
            ]
        },
        {},
    )

    assert sorted(widget._state_pills) == ["limits"]
    assert widget._model.rowCount() == 1


def test_beamline_state_manager_ignores_unchanged_available_states(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)
    content = {
        "states": [
            {
                "name": "limits",
                "title": "Limits",
                "state_type": "DeviceWithinLimitsState",
                "parameters": {
                    "device": "samx",
                    "signal": "samx",
                    "low_limit": 0.0,
                    "high_limit": 10.0,
                    "tolerance": 0.1,
                },
            }
        ]
    }

    widget.update_available_states(content, {})
    pill = widget._state_pills["limits"]

    widget.update_available_states(content, {})

    assert widget._state_pills["limits"] is pill
    assert pill._config_form is None


def test_beamline_state_manager_adds_state_without_recreating_existing_pills(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)
    limits_state = {
        "name": "limits",
        "title": "Limits",
        "state_type": "DeviceWithinLimitsState",
        "parameters": {
            "device": "samx",
            "signal": "samx",
            "low_limit": 0.0,
            "high_limit": 10.0,
            "tolerance": 0.1,
        },
    }
    shutter_state = {
        "name": "shutter_open",
        "title": "Shutter",
        "state_type": "ShutterState",
        "parameters": {},
    }

    widget.update_available_states({"states": [limits_state]}, {})
    pill = widget._state_pills["limits"]
    pill.set_expanded(True)
    config_form = pill._config_form

    widget.update_available_states({"states": [limits_state, shutter_state]}, {})

    assert widget._state_pills["limits"] is pill
    assert pill._config_form is config_form
    assert pill.is_expanded()
    assert sorted(widget._state_pills) == ["limits", "shutter_open"]


def test_beamline_state_manager_does_not_force_horizontal_minimum(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)

    widget.update_available_states(
        {
            "states": [
                {
                    "name": "limits",
                    "title": "Limits",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {
                        "device": "samx",
                        "signal": "samx",
                        "low_limit": 0.0,
                        "high_limit": 10.0,
                        "tolerance": 0.1,
                    },
                }
            ]
        },
        {},
    )

    index = widget._model.index_for_name("limits")
    hint = widget._delegate.sizeHint(QStyleOptionViewItem(), index)

    assert widget.minimumWidth() == 0
    assert widget.minimumSizeHint().width() == 0
    assert widget._view.minimumWidth() == 0
    assert widget._view.minimumSizeHint().width() == 0
    assert hint.width() == 0


def test_beamline_state_manager_header_click_expands_pill_once(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)
    widget.update_available_states(
        {
            "states": [
                {
                    "name": "limits",
                    "title": "Limits",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {"device": "samx"},
                }
            ]
        },
        {},
    )

    pill = widget._state_pills["limits"]
    assert pill._settings.isHidden()

    qtbot.mouseClick(pill._header, Qt.MouseButton.LeftButton)

    assert not pill._settings.isHidden()


def test_beamline_state_manager_preserves_expanded_pill_on_refresh(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)
    state = {
        "name": "limits",
        "title": "Limits",
        "state_type": "DeviceWithinLimitsState",
        "parameters": {"device": "samx", "high_limit": 10.0},
    }
    widget.update_available_states({"states": [state]}, {})

    widget._state_pills["limits"].set_expanded(True)
    widget.update_available_states({"states": [state]}, {})

    assert widget._state_pills["limits"].is_expanded()
    assert not widget._state_pills["limits"]._settings.isHidden()


def test_beamline_state_manager_propagates_idle_card_background(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client, idle_card_background=True)
    qtbot.addWidget(widget)

    widget.update_available_states(
        {
            "states": [
                {
                    "name": "limits",
                    "title": "Limits",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {"device": "samx"},
                }
            ]
        },
        {},
    )

    assert widget._state_pills["limits"]._idle_card_background is True

    widget.idle_card_background = False

    assert widget._state_pills["limits"]._idle_card_background is False


def test_beamline_state_manager_filters_status(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)

    widget.update_available_states(
        {
            "states": [
                {
                    "name": "shutter_open",
                    "title": "Shutter",
                    "state_type": "ShutterState",
                    "parameters": {"device": "samy"},
                },
                {
                    "name": "limits",
                    "title": "Limits",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {"device": "samx"},
                },
            ]
        },
        {},
    )

    assert isinstance(widget._toolbar, ModularToolBar)

    widget._state_pills["limits"].update_state(
        {"name": "limits", "status": "valid", "label": "Within limits."}, {}
    )
    widget._state_pills["shutter_open"].update_state(
        {"name": "shutter_open", "status": "invalid", "label": "Closed."}, {}
    )
    widget._selected_statuses = {"valid"}
    widget._apply_filters()

    assert not widget._hidden_summary.isHidden()
    assert "1 state is hidden" in widget._hidden_summary.text()
    assert not widget._view.isRowHidden(widget._model.index_for_name("limits").row())
    assert widget._view.isRowHidden(widget._model.index_for_name("shutter_open").row())

    widget._hidden_summary.click()

    assert not widget._view.isRowHidden(widget._model.index_for_name("shutter_open").row())
    assert shiboken6.isValid(widget._state_pills["shutter_open"])

    widget._hidden_summary.click()

    assert widget._view.isRowHidden(widget._model.index_for_name("shutter_open").row())
    assert shiboken6.isValid(widget._state_pills["shutter_open"])


def test_beamline_state_manager_status_filter_reacts_to_state_changes(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)

    widget.update_available_states(
        {
            "states": [
                {
                    "name": "limits",
                    "title": "Limits",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {"device": "samx"},
                }
            ]
        },
        {},
    )

    widget._selected_statuses = {"valid"}
    widget._state_pills["limits"].update_state(
        {"name": "limits", "status": "valid", "label": "Within limits."}, {}
    )

    assert widget._hidden_summary.isHidden()

    widget._state_pills["limits"].update_state(
        {"name": "limits", "status": "invalid", "label": "Out of limits."}, {}
    )

    assert not widget._hidden_summary.isHidden()
    assert widget._view.isRowHidden(widget._model.index_for_name("limits").row())


def test_beamline_state_manager_filters_devices(qtbot, mocked_client, monkeypatch):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)

    widget.update_available_states(
        {
            "states": [
                {
                    "name": "samx_limits",
                    "title": "samx",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {"device": "samx"},
                },
                {
                    "name": "samy_limits",
                    "title": "samy",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {"device": "samy"},
                },
            ]
        },
        {},
    )

    widget._device_filter_text = "samx"
    widget._apply_filters()

    assert not widget._hidden_summary.isHidden()
    assert "1 state is hidden" in widget._hidden_summary.text()

    captured = {}

    class FakeDeviceFilterDialog:
        def __init__(self, devices, selected_devices, device_filter_text, parent):
            captured["devices"] = devices
            captured["selected_devices"] = selected_devices
            captured["device_filter_text"] = device_filter_text
            captured["parent"] = parent

        def exec(self):
            return 0

    monkeypatch.setattr(pill_module, "DeviceFilterDialog", FakeDeviceFilterDialog)

    widget.open_device_filter_dialog()

    assert captured["devices"] == ["samx", "samy"]
    assert captured["device_filter_text"] == "samx"
    assert captured["parent"] is widget


def test_beamline_state_manager_updates_state_parameters(qtbot, mocked_client):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)
    widget.update_available_states(
        {
            "states": [
                {
                    "name": "limits",
                    "title": "Limits",
                    "state_type": "DeviceWithinLimitsState",
                    "parameters": {
                        "device": "samx",
                        "signal": "samx",
                        "low_limit": 0.0,
                        "high_limit": 10.0,
                        "tolerance": 0.1,
                    },
                }
            ]
        },
        {},
    )

    class StateClient:
        def __init__(self):
            self.parameters = None

        def update_parameters(self, **kwargs):
            self.parameters = kwargs

    class StateManager:
        def __init__(self):
            self.limits = StateClient()

    mocked_client.beamline_states = StateManager()
    pill = widget._state_pills["limits"]
    pill.set_expanded(True)
    high_limit = pill._config_form.input_widget("high_limit")
    high_limit.setValue(20.0)

    assert pill._update_button.isEnabled()

    widget._update_state_parameters("limits", pill.edited_config())

    assert mocked_client.beamline_states.limits.parameters == {
        "title": "Limits",
        "device": "samx",
        "signal": "samx",
        "low_limit": 0.0,
        "high_limit": 20.0,
        "tolerance": 0.1,
    }
    assert not pill._update_button.isEnabled()
    assert pill._config_form.field_widget("high_limit").property("beamlineStateDirty") is False


def test_beamline_state_manager_removes_state(qtbot, mocked_client, monkeypatch):
    widget = BeamlineStateManager(client=mocked_client)
    qtbot.addWidget(widget)

    class StateManager:
        def __init__(self):
            self.deleted = None

        def delete(self, state_name):
            self.deleted = state_name

    mocked_client.beamline_states = StateManager()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )

    widget._remove_state_requested("limits")

    assert mocked_client.beamline_states.deleted == "limits"


def test_add_beamline_state_dialog_uses_generated_widgets_and_normalizes_name(qtbot, mocked_client):
    dialog = AddBeamlineStateDialog(client=mocked_client)
    qtbot.addWidget(dialog)
    limits_index = dialog._type_combo.findText(bl_states.DeviceWithinLimitsState.__name__)
    assert limits_index >= 0
    dialog._type_combo.setCurrentIndex(limits_index)

    assert dialog._config_form.model is bl_states.DeviceWithinLimitsState.CONFIG_CLASS

    name = dialog._config_form.input_widget("name")
    title = dialog._config_form.input_widget("title")
    device = dialog._config_form.input_widget("device")
    signal = dialog._config_form.input_widget("signal")
    low_limit = dialog._config_form.field_widget("low_limit")
    high_limit = dialog._config_form.field_widget("high_limit")

    name.setText("samx-limits")
    title.setText("samx-limits-15")
    WidgetIO.set_value(device, "samx")
    WidgetIO.set_value(signal, "samx")
    low_limit.checkbox.setChecked(True)
    high_limit.checkbox.setChecked(True)
    high_limit.value_widget.setValue(15.0)

    config = dialog.config()

    assert config.name == "samx_limits"
    assert config.title == "samx-limits-15"
    assert config.device == "samx"
    assert config.signal == "samx"
    assert config.low_limit == 0.0
    assert config.high_limit == 15.0


def test_add_beamline_state_dialog_generates_name_only_after_valid_device_selection(
    qtbot, mocked_client
):
    dialog = AddBeamlineStateDialog(client=mocked_client)
    qtbot.addWidget(dialog)
    name = dialog._config_form.input_widget("name")
    device = dialog._config_form.input_widget("device")

    device.setCurrentText("s")

    assert name.text() == ""

    device.set_device("samx")

    assert name.text() == "samx_device_within_limits_state"


def test_add_beamline_state_dialog_switches_state_type_without_collapsing(qtbot, mocked_client):
    dialog = AddBeamlineStateDialog(client=mocked_client)
    qtbot.addWidget(dialog)

    initial_height = dialog.height()
    limits_index = dialog._type_combo.findText("DeviceWithinLimitsState")
    assert limits_index >= 0
    shutter_index = dialog._type_combo.findText("ShutterState")
    assert shutter_index >= 0

    dialog._type_combo.setCurrentIndex(shutter_index)
    qtbot.wait(0)

    assert dialog._config_form.model is bl_states.DeviceStateConfig
    assert dialog._config_form_host.count() == 1
    assert not dialog._config_form.isHidden()
    assert not dialog._buttons.isHidden()
    assert dialog.sizeHint().height() > dialog._buttons.sizeHint().height()
    assert dialog.minimumWidth() == 280
    assert dialog.maximumWidth() > dialog.minimumWidth()
    assert dialog.minimumHeight() == dialog.maximumHeight()

    dialog._type_combo.setCurrentIndex(limits_index)
    qtbot.wait(0)

    assert dialog._config_form.model is bl_states.DeviceWithinLimitsState.CONFIG_CLASS
    assert dialog.height() >= initial_height
    assert dialog.minimumHeight() == dialog.maximumHeight()


def test_add_beamline_state_dialog_cleanup_deletes_device_widgets(qtbot, mocked_client):
    dialog = AddBeamlineStateDialog(client=mocked_client)
    qtbot.addWidget(dialog)
    device = dialog._config_form.input_widget("device")
    signal = dialog._config_form.input_widget("signal")

    dialog.reject()
    assert shiboken6.isValid(device)
    assert shiboken6.isValid(signal)

    dialog.cleanup()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert not shiboken6.isValid(device)
    assert not shiboken6.isValid(signal)
