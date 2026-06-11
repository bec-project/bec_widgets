import shiboken6
from bec_lib import bl_states, messages
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtWidgets import QMessageBox

from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.services.beamline_states import beamline_state_manager as manager_module
from bec_widgets.widgets.services.beamline_states import beamline_state_pill as pill_module
from bec_widgets.widgets.services.beamline_states.beamline_state_manager import BeamlineStateManager
from bec_widgets.widgets.services.beamline_states.beamline_state_pill import BeamlineStatePill
from bec_widgets.widgets.services.beamline_states.dialogs import AddBeamlineStateDialog

from .client_mocks import mocked_client
from .conftest import create_widget


def _state(name: str, state_type: str, parameters: dict | None = None):
    return messages.BeamlineStateConfig(
        name=name, state_type=state_type, parameters=parameters or {}
    )


def _limits_state(name: str = "limits", **overrides):
    parameters = {
        "device": "samx",
        "signal": "samx",
        "low_limit": 0.0,
        "high_limit": 10.0,
        "tolerance": 0.1,
    }
    parameters.update(overrides)
    return _state(name, "DeviceWithinLimitsState", parameters)


def test_beamline_state_pill_updates_from_message(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="shutter_open", client=mocked_client)
    pill.update_state({"name": "shutter_open", "status": "valid", "label": "Shutter is open."}, {})

    assert pill._state_name == "shutter_open"
    assert pill._name_label.text() == "shutter_open"
    assert pill._status_label.text() == "VALID"
    assert pill._detail_label.text() == "Shutter is open."
    assert not pill._icon_label.pixmap().isNull()
    assert pill.toolTip() == "Shutter is open."


def test_beamline_state_pill_ignores_other_states(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="shutter_open", client=mocked_client)
    pill.update_state(
        {"name": "other_state", "status": "invalid", "label": "Should be ignored."}, {}
    )

    assert pill._status_label.text() == "UNKNOWN"
    assert pill.toolTip() == "No state information available."


def test_beamline_state_pill_expands_and_emits_updated_limits(qtbot, mocked_client):
    limits_pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    limits_pill.set_state_config(_limits_state())

    assert limits_pill._settings.isHidden()
    assert limits_pill._config_form is None
    assert not limits_pill._update_button.isEnabled()
    assert not limits_pill._revert_button.isEnabled()

    qtbot.mouseClick(limits_pill._header, Qt.MouseButton.LeftButton)
    assert limits_pill._config_form is not None
    high_limit = limits_pill._config_form.input_widget("high_limit")
    high_limit.setValue(20.0)

    assert not limits_pill._settings.isHidden()
    assert limits_pill._update_button.isEnabled()
    assert limits_pill._revert_button.isEnabled()
    assert (
        limits_pill._config_form.field_widget("high_limit").property("beamlineStateDirty") is True
    )
    assert limits_pill._config_form.get_data()["device"] == "samx"
    assert limits_pill.edited_config().high_limit == 20.0

    with qtbot.waitSignal(limits_pill.update_requested) as signal:
        limits_pill._update_button.click()

    assert signal.args[0] == "limits"
    assert isinstance(signal.args[1], bl_states.DeviceWithinLimitsState.CONFIG_CLASS)
    assert signal.args[1].device == "samx"
    assert signal.args[1].signal == "samx"
    assert signal.args[1].low_limit == 0.0
    assert signal.args[1].high_limit == 20.0
    assert signal.args[1].tolerance == 0.1
    assert not limits_pill._settings.isHidden()


def test_beamline_state_pill_first_expand_uses_config_class_without_rebuild(
    qtbot, mocked_client, monkeypatch
):
    limits_pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    set_model_calls = []
    original_set_model = pill_module.PydanticWidgetForm.set_model

    def set_model_spy(self, model, data=None):
        set_model_calls.append(model)
        return original_set_model(self, model, data=data)

    monkeypatch.setattr(pill_module.PydanticWidgetForm, "set_model", set_model_spy)
    limits_pill.set_state_config(_limits_state())

    limits_pill.set_expanded(True)
    assert limits_pill._config_form is not None
    assert set_model_calls == []


def test_beamline_state_pill_reverts_changed_settings(qtbot, mocked_client):
    limits_pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    limits_pill.set_state_config(_limits_state())

    limits_pill.set_expanded(True)
    assert limits_pill._config_form is not None
    low_limit = limits_pill._config_form.input_widget("low_limit")
    low_limit.setValue(-5.0)

    assert limits_pill._update_button.isEnabled()
    assert limits_pill._config_form.field_widget("low_limit").property("beamlineStateDirty") is True

    limits_pill._revert_button.click()

    assert low_limit.value() == 0.0
    assert not limits_pill._update_button.isEnabled()
    assert not limits_pill._revert_button.isEnabled()
    assert (
        limits_pill._config_form.field_widget("low_limit").property("beamlineStateDirty") is False
    )


def test_beamline_state_pill_does_not_override_themed_input_controls(qtbot, mocked_client):
    limits_pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    limits_pill.set_state_config(_limits_state())
    limits_pill.set_expanded(True)

    stylesheet = limits_pill.styleSheet()

    assert "QAbstractSpinBox" not in stylesheet
    assert "QComboBox" not in stylesheet
    assert "QCheckBox::indicator" not in stylesheet


def test_beamline_state_manager_adds_and_removes_pills(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {
            "states": [
                _state("shutter_open", "ShutterState"),
                _state("limits", "DeviceWithinLimitsState"),
            ]
        },
        {},
    )

    assert sorted(beamline_state_manager._state_pills) == ["limits", "shutter_open"]
    assert beamline_state_manager._model.rowCount() == 2
    assert beamline_state_manager._state_pills["shutter_open"]._name_label.text() == "shutter_open"
    assert not beamline_state_manager._empty_label.isVisible()

    beamline_state_manager._state_pills["limits"].update_state(
        {"name": "limits", "status": "valid", "label": "Within limits."}, {}
    )
    summary = beamline_state_manager.state_summary()
    assert summary["limits"] == {"status": "valid", "label": "Within limits."}
    assert summary["shutter_open"]["status"] == "unknown"

    beamline_state_manager.update_available_states(
        {"states": [_state("limits", "DeviceWithinLimitsState")]}, {}
    )

    assert sorted(beamline_state_manager._state_pills) == ["limits"]
    assert beamline_state_manager._model.rowCount() == 1


def test_beamline_state_manager_ignores_unchanged_available_states(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    content = {"states": [_limits_state()]}

    beamline_state_manager.update_available_states(content, {})
    pill = beamline_state_manager._state_pills["limits"]

    beamline_state_manager.update_available_states(content, {})

    assert beamline_state_manager._state_pills["limits"] is pill
    assert pill._config_form is None


def test_beamline_state_manager_adds_state_without_recreating_existing_pills(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    limits_state = _limits_state()
    shutter_state = _state("shutter_open", "ShutterState")

    beamline_state_manager.update_available_states({"states": [limits_state]}, {})
    pill = beamline_state_manager._state_pills["limits"]
    pill.set_expanded(True)
    config_form = pill._config_form

    beamline_state_manager.update_available_states({"states": [limits_state, shutter_state]}, {})

    assert beamline_state_manager._state_pills["limits"] is pill
    assert pill._config_form is config_form
    assert pill.is_expanded()
    assert sorted(beamline_state_manager._state_pills) == ["limits", "shutter_open"]


def test_beamline_state_manager_header_click_expands_pill_once(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {"states": [_state("limits", "DeviceWithinLimitsState", {"device": "samx"})]}, {}
    )

    pill = beamline_state_manager._state_pills["limits"]
    assert pill._settings.isHidden()

    qtbot.mouseClick(pill._header, Qt.MouseButton.LeftButton)

    assert not pill._settings.isHidden()


def test_beamline_state_manager_preserves_expanded_pill_on_refresh(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    state = _state("limits", "DeviceWithinLimitsState", {"device": "samx", "high_limit": 10.0})
    beamline_state_manager.update_available_states({"states": [state]}, {})

    beamline_state_manager._state_pills["limits"].set_expanded(True)
    beamline_state_manager.update_available_states({"states": [state]}, {})

    assert beamline_state_manager._state_pills["limits"].is_expanded()
    assert not beamline_state_manager._state_pills["limits"]._settings.isHidden()


def test_beamline_state_manager_propagates_idle_card_background(qtbot, mocked_client):
    idle_card_manager = create_widget(
        qtbot, BeamlineStateManager, client=mocked_client, idle_card_background=True
    )
    idle_card_manager.update_available_states(
        {"states": [_state("limits", "DeviceWithinLimitsState", {"device": "samx"})]}, {}
    )

    assert idle_card_manager._state_pills["limits"]._idle_card_background is True

    idle_card_manager.idle_card_background = False

    assert idle_card_manager._state_pills["limits"]._idle_card_background is False


def test_beamline_state_manager_filters_status(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {
            "states": [
                _state("shutter_open", "ShutterState", {"device": "samy"}),
                _state("limits", "DeviceWithinLimitsState", {"device": "samx"}),
            ]
        },
        {},
    )

    assert isinstance(beamline_state_manager._toolbar, ModularToolBar)
    assert not beamline_state_manager._toolbar.components.exists("refresh")

    beamline_state_manager._state_pills["limits"].update_state(
        {"name": "limits", "status": "valid", "label": "Within limits."}, {}
    )
    beamline_state_manager._state_pills["shutter_open"].update_state(
        {"name": "shutter_open", "status": "invalid", "label": "Closed."}, {}
    )
    beamline_state_manager._selected_statuses = {"valid"}
    beamline_state_manager._apply_filters()

    assert not beamline_state_manager._hidden_summary.isHidden()
    assert "1 state is hidden" in beamline_state_manager._hidden_summary.text()
    assert not beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("limits").row()
    )
    assert beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("shutter_open").row()
    )

    beamline_state_manager._hidden_summary.click()

    assert not beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("shutter_open").row()
    )
    assert shiboken6.isValid(beamline_state_manager._state_pills["shutter_open"])

    beamline_state_manager._hidden_summary.click()

    assert beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("shutter_open").row()
    )
    assert shiboken6.isValid(beamline_state_manager._state_pills["shutter_open"])


def test_beamline_state_manager_status_filter_reacts_to_state_changes(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {"states": [_state("limits", "DeviceWithinLimitsState", {"device": "samx"})]}, {}
    )

    beamline_state_manager._selected_statuses = {"valid"}
    beamline_state_manager._state_pills["limits"].update_state(
        {"name": "limits", "status": "valid", "label": "Within limits."}, {}
    )

    assert beamline_state_manager._hidden_summary.isHidden()

    beamline_state_manager._state_pills["limits"].update_state(
        {"name": "limits", "status": "invalid", "label": "Out of limits."}, {}
    )

    assert not beamline_state_manager._hidden_summary.isHidden()
    assert beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("limits").row()
    )


def test_beamline_state_manager_filters_devices(qtbot, mocked_client, monkeypatch):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {
            "states": [
                _state("samx_limits", "DeviceWithinLimitsState", {"device": "samx"}),
                _state("samy_limits", "DeviceWithinLimitsState", {"device": "samy"}),
            ]
        },
        {},
    )

    beamline_state_manager._device_filter_text = "samx"
    beamline_state_manager._apply_filters()

    assert not beamline_state_manager._hidden_summary.isHidden()
    assert "1 state is hidden" in beamline_state_manager._hidden_summary.text()

    captured = {}

    class FakeDeviceFilterDialog:
        def __init__(self, devices, selected_devices, device_filter_text, parent):
            captured["devices"] = devices
            captured["selected_devices"] = selected_devices
            captured["device_filter_text"] = device_filter_text
            captured["parent"] = parent

        def exec(self):
            return 0

    monkeypatch.setattr(manager_module, "DeviceFilterDialog", FakeDeviceFilterDialog)

    beamline_state_manager.open_device_filter_dialog()

    assert captured["devices"] == ["samx", "samy"]
    assert captured["device_filter_text"] == "samx"
    assert captured["parent"] is beamline_state_manager


def test_beamline_state_manager_backend_echo_repopulates_expanded_pill(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states({"states": [_limits_state()]}, {})

    pill = beamline_state_manager._state_pills["limits"]
    pill.set_expanded(True)
    high_limit = pill._config_form.input_widget("high_limit")
    high_limit.setValue(20.0)

    assert pill._update_button.isEnabled()

    beamline_state_manager.update_available_states({"states": [_limits_state(high_limit=20.0)]}, {})

    assert pill.is_expanded()
    assert high_limit.value() == 20.0
    assert not pill._update_button.isEnabled()
    assert pill._config_form.dirty_fields() == set()


def test_beamline_state_manager_updates_state_parameters(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states({"states": [_limits_state()]}, {})

    class StateClient:
        def __init__(self):
            self.parameters = None

        def update_parameters(self, **kwargs):
            self.parameters = kwargs

    class StateManager:
        def __init__(self):
            self.limits = StateClient()

    mocked_client.beamline_states = StateManager()
    pill = beamline_state_manager._state_pills["limits"]
    pill.set_expanded(True)
    high_limit = pill._config_form.input_widget("high_limit")
    high_limit.setValue(20.0)

    assert pill._update_button.isEnabled()

    beamline_state_manager._update_state_parameters("limits", pill.edited_config())

    assert mocked_client.beamline_states.limits.parameters == {
        "device": "samx",
        "signal": "samx",
        "low_limit": 0.0,
        "high_limit": 20.0,
        "tolerance": 0.1,
    }
    assert not pill._update_button.isEnabled()
    assert pill._config_form.field_widget("high_limit").property("beamlineStateDirty") is False


def test_beamline_state_manager_removes_state(qtbot, mocked_client, monkeypatch):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)

    class StateManager:
        def __init__(self):
            self.deleted = None

        def delete(self, state_name):
            self.deleted = state_name

    mocked_client.beamline_states = StateManager()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )

    beamline_state_manager._remove_state_requested("limits")

    assert mocked_client.beamline_states.deleted == "limits"


def test_add_beamline_state_dialog_uses_generated_widgets_and_normalizes_name(qtbot, mocked_client):
    add_state_dialog = create_widget(qtbot, AddBeamlineStateDialog, client=mocked_client)
    limits_index = add_state_dialog._type_combo.findText(bl_states.DeviceWithinLimitsState.__name__)
    assert limits_index >= 0
    add_state_dialog._type_combo.setCurrentIndex(limits_index)

    assert add_state_dialog._config_form.model is bl_states.DeviceWithinLimitsState.CONFIG_CLASS

    name = add_state_dialog._config_form.input_widget("name")
    device = add_state_dialog._config_form.input_widget("device")
    signal = add_state_dialog._config_form.input_widget("signal")
    low_limit = add_state_dialog._config_form.field_widget("low_limit")
    high_limit = add_state_dialog._config_form.field_widget("high_limit")

    name.setText("samx-limits")
    WidgetIO.set_value(device, "samx")
    WidgetIO.set_value(signal, "samx")
    low_limit.checkbox.setChecked(True)
    high_limit.checkbox.setChecked(True)
    high_limit.value_widget.setValue(15.0)

    config = add_state_dialog.config()

    assert config.name == "samx_limits"
    assert config.device == "samx"
    assert config.signal == "samx"
    assert config.low_limit == 0.0
    assert config.high_limit == 15.0


def test_add_beamline_state_dialog_generates_name_only_after_valid_device_selection(
    qtbot, mocked_client
):
    add_state_dialog = create_widget(qtbot, AddBeamlineStateDialog, client=mocked_client)
    name = add_state_dialog._config_form.input_widget("name")
    device = add_state_dialog._config_form.input_widget("device")

    device.setCurrentText("s")

    assert name.text() == ""

    device.set_device("samx")

    assert name.text() == "samx_device_within_limits_state"


def test_add_beamline_state_dialog_switches_state_type_without_collapsing(qtbot, mocked_client):
    add_state_dialog = create_widget(qtbot, AddBeamlineStateDialog, client=mocked_client)
    initial_height = add_state_dialog.height()
    limits_index = add_state_dialog._type_combo.findText("DeviceWithinLimitsState")
    assert limits_index >= 0
    shutter_index = add_state_dialog._type_combo.findText("ShutterState")
    assert shutter_index >= 0

    add_state_dialog._type_combo.setCurrentIndex(shutter_index)
    qtbot.wait(0)

    assert add_state_dialog._config_form.model is bl_states.DeviceStateConfig
    assert add_state_dialog._config_form_host.count() == 1
    assert not add_state_dialog._config_form.isHidden()
    assert not add_state_dialog._buttons.isHidden()
    assert add_state_dialog.sizeHint().height() > add_state_dialog._buttons.sizeHint().height()
    assert add_state_dialog.minimumHeight() == add_state_dialog.maximumHeight()

    add_state_dialog._type_combo.setCurrentIndex(limits_index)
    qtbot.wait(0)

    assert add_state_dialog._config_form.model is bl_states.DeviceWithinLimitsState.CONFIG_CLASS
    assert add_state_dialog.height() >= initial_height
    assert add_state_dialog.minimumHeight() == add_state_dialog.maximumHeight()


def test_add_beamline_state_dialog_cleanup_deletes_device_widgets(qtbot, mocked_client):
    add_state_dialog = create_widget(qtbot, AddBeamlineStateDialog, client=mocked_client)
    device = add_state_dialog._config_form.input_widget("device")
    signal = add_state_dialog._config_form.input_widget("signal")

    add_state_dialog.reject()
    assert shiboken6.isValid(device)
    assert shiboken6.isValid(signal)

    add_state_dialog.cleanup()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert not shiboken6.isValid(device)
    assert not shiboken6.isValid(signal)
