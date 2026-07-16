import shiboken6
from bec_lib import bl_states, messages
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtWidgets import QComboBox, QDialog, QMessageBox, QStyleOptionViewItem, QTreeWidget

from bec_widgets.utils.eliding_label import ElidingLabel
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.services.beamline_states import beamline_state_manager as manager_module
from bec_widgets.widgets.services.beamline_states import beamline_state_pill as pill_module
from bec_widgets.widgets.services.beamline_states.aggregated_state_editor import (
    AggregatedStateConfigEditor,
)
from bec_widgets.widgets.services.beamline_states.beamline_state_manager import BeamlineStateManager
from bec_widgets.widgets.services.beamline_states.beamline_state_pill import BeamlineStatePill
from bec_widgets.widgets.services.beamline_states.dialogs import AddBeamlineStateDialog

from .client_mocks import mocked_client
from .conftest import create_widget


def _state(name: str, state_type: str, parameters: dict | None = None):
    return messages.BeamlineStateConfig(
        name=name, state_type=state_type, parameters=parameters or {}
    )


def _wire_state(
    state_class: type[bl_states.BeamlineState], config: bl_states.BeamlineStateConfig
) -> messages.BeamlineStateConfig:
    return messages.BeamlineStateConfig(
        name=config.name,
        state_type=state_class.__name__,
        parameters=config.model_dump(exclude={"name"}),
    )


def _limits_state(name: str = "limits", **overrides) -> messages.BeamlineStateConfig:
    values = {
        "device": "samx",
        "signal": "samx",
        "low_limit": 0.0,
        "high_limit": 10.0,
        "tolerance": 0.1,
    }
    values.update(overrides)
    config = bl_states.DeviceWithinLimitsState.CONFIG_CLASS(name=name, **values)
    return _wire_state(bl_states.DeviceWithinLimitsState, config)


def _aggregated_state(
    name: str = "machine_mode", evaluation_method: str | None = "any"
) -> messages.BeamlineStateConfig:
    config = bl_states.AggregatedStateConfig(
        name=name,
        evaluation_method=evaluation_method,
        states={
            "alignment": {
                "devices": {
                    "samx": {
                        "value": 0,
                        "abs_tol": 0.1,
                        "signals": {"velocity": {"value": 5, "abs_tol": 0.2}},
                    },
                    "samy": {"at": "in", "abs_tol": 0.1},
                },
                "transition_metadata": {"description": "Prepare alignment"},
            },
            "parked": {
                "devices": {
                    "samx": {
                        "low_limit": {"at": "low", "abs_tol": 0.3},
                        "high_limit": {"value": 10, "abs_tol": 0.4},
                    }
                }
            },
        },
    )
    return _wire_state(bl_states.AggregatedState, config)


def _tree_rows(tree: QTreeWidget) -> list[list[str]]:
    rows: list[list[str]] = []

    def collect(item) -> None:
        rows.append([item.text(column) for column in range(tree.columnCount())])
        for index in range(item.childCount()):
            collect(item.child(index))

    for index in range(tree.topLevelItemCount()):
        collect(tree.topLevelItem(index))
    return rows


def _as_status_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


class _FakeScanInterlock:
    def __init__(
        self, enabled: bool = False, states_watched: dict[str, str | list[str]] | None = None
    ):
        self.enabled = enabled
        self._states = {
            name: _as_status_list(value) for name, value in (states_watched or {}).items()
        }
        self.added: list[tuple[str, str]] = []
        self.removed: list[str] = []

    @property
    def states_watched(self) -> dict[str, list[str]]:
        return {name: list(statuses) for name, statuses in self._states.items()}

    def add_state_to_interlock(self, state_name: str, required_value: str = "valid") -> None:
        self.added.append((state_name, required_value))
        self._states[state_name] = _as_status_list(required_value)

    def remove_state_from_interlock(self, state_name: str) -> None:
        self.removed.append(state_name)
        self._states.pop(state_name, None)


def _install_fake_scan_interlock(
    manager: BeamlineStateManager, fake_interlock: _FakeScanInterlock
) -> None:
    manager._scan_interlock = fake_interlock
    manager._refresh_scan_interlock()


def test_beamline_state_pill_updates_from_message(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    pill.update_state({"name": "limits", "status": "valid", "label": "Within limits."}, {})

    assert pill._state_name == "limits"
    assert pill._name_label.text() == "limits"
    assert pill._status_label.text() == "VALID"
    assert pill._detail_label.text() == "Within limits."
    assert not pill._icon_label.pixmap().isNull()
    assert pill.toolTip() == "Within limits."


def test_beamline_state_pill_ignores_other_states(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
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


def test_aggregated_state_pill_displays_rule_inspector(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="machine_mode", client=mocked_client)
    pill.set_state_config(_aggregated_state())
    pill.update_state({"name": "machine_mode", "status": "valid", "label": "alignment"}, {})

    pill.set_expanded(True)

    editor = pill._config_form
    assert isinstance(editor, AggregatedStateConfigEditor)
    assert editor.input_widget("evaluation_method").currentData() == "any"
    assert editor._summary.text() == "2 labels · 2 devices · 5 requirements"
    assert editor.tree.maximumHeight() == 360
    assert editor.tree.topLevelItemCount() == 2

    rows = _tree_rows(editor.tree)
    assert ["alignment", "", ""] in rows
    assert ["samx", "", ""] in rows
    assert ["readback", "0", "± 0.1"] in rows
    assert ["velocity", "5", "± 0.2"] in rows
    assert ["readback", "at: in", "± 0.1"] in rows
    assert ["low limit", "at: low", "± 0.3"] in rows
    assert ["high limit", "10", "± 0.4"] in rows
    assert any(row[0] == "Transition metadata" and "Prepare alignment" in row[2] for row in rows)

    alignment = editor.tree.topLevelItem(0)
    parked = editor.tree.topLevelItem(1)
    assert alignment.text(0) == "alignment"
    assert alignment.font(0).bold()
    assert alignment.isExpanded()
    assert not parked.font(0).bold()


def test_aggregated_state_pill_updates_evaluation_method(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="machine_mode", client=mocked_client)
    pill.set_state_config(_aggregated_state())
    pill.set_expanded(True)
    editor = pill._config_form
    assert isinstance(editor, AggregatedStateConfigEditor)
    method_combo = editor.input_widget("evaluation_method")
    assert isinstance(method_combo, QComboBox)

    exclusive_index = next(
        index
        for index in range(method_combo.count())
        if method_combo.itemData(index) == "exclusive"
    )
    method_combo.setCurrentIndex(exclusive_index)

    assert pill._update_button.isEnabled()
    assert pill._revert_button.isEnabled()
    assert pill._settings_dirty_fields == {"evaluation_method"}
    edited = pill.edited_config()
    assert isinstance(edited, bl_states.AggregatedStateConfig)
    assert edited.evaluation_method == "exclusive"
    assert set(edited.states) == {"alignment", "parked"}

    with qtbot.waitSignal(pill.update_requested) as signal:
        pill._update_button.click()

    assert signal.args[0] == "machine_mode"
    assert signal.args[1].evaluation_method == "exclusive"
    assert set(signal.args[1].states) == {"alignment", "parked"}


def test_aggregated_state_pill_round_trips_disabled_evaluation_and_reverts(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="machine_mode", client=mocked_client)
    pill.set_state_config(_aggregated_state(evaluation_method=None))
    pill.set_expanded(True)
    editor = pill._config_form
    assert isinstance(editor, AggregatedStateConfigEditor)
    method_combo = editor.input_widget("evaluation_method")
    assert isinstance(method_combo, QComboBox)
    assert method_combo.currentData() is None
    assert pill.edited_config().evaluation_method is None

    any_index = next(
        index for index in range(method_combo.count()) if method_combo.itemData(index) == "any"
    )
    method_combo.setCurrentIndex(any_index)
    assert pill._update_button.isEnabled()

    pill._revert_button.click()

    assert method_combo.currentData() is None
    assert pill.edited_config().evaluation_method is None
    assert not pill._update_button.isEnabled()
    assert not pill._revert_button.isEnabled()


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


def test_beamline_state_pill_releases_form_on_collapse(qtbot, mocked_client):
    limits_pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    limits_pill.set_state_config(_limits_state())

    limits_pill.set_expanded(True)
    device_widget = limits_pill._config_form.input_widget("device")

    limits_pill.set_expanded(False)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert limits_pill._config_form is None
    assert not shiboken6.isValid(device_widget)

    limits_pill.set_expanded(True)

    assert limits_pill._config_form is not None
    assert limits_pill._config_form.input_widget("high_limit").value() == 10.0
    assert not limits_pill._update_button.isEnabled()


def test_beamline_state_pill_collapse_discards_unsaved_edits(qtbot, mocked_client):
    limits_pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    limits_pill.set_state_config(_limits_state())

    limits_pill.set_expanded(True)
    limits_pill._config_form.input_widget("high_limit").setValue(20.0)
    assert limits_pill._update_button.isEnabled()

    limits_pill.set_expanded(False)

    assert limits_pill._config_form is None

    limits_pill.set_expanded(True)

    assert limits_pill._config_form.input_widget("high_limit").value() == 10.0
    assert not limits_pill._update_button.isEnabled()


def test_beamline_state_pill_does_not_override_themed_input_controls(qtbot, mocked_client):
    limits_pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    limits_pill.set_state_config(_limits_state())
    limits_pill.set_expanded(True)

    stylesheet = limits_pill.styleSheet()

    assert "QAbstractSpinBox" not in stylesheet
    assert "QComboBox" not in stylesheet
    assert "QCheckBox::indicator" not in stylesheet


def test_beamline_state_pill_title_and_detail_elide_without_wrapping(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="x", client=mocked_client)

    assert isinstance(pill._name_label, ElidingLabel)
    assert isinstance(pill._detail_label, ElidingLabel)
    # The detail no longer word-wraps, so a long message can't make a collapsed pill taller.
    assert not pill._detail_label.wordWrap()
    assert pill.minimumWidth() == 200

    pill.update_state({"name": "x", "status": "valid", "label": "L" * 200}, {})

    # A long title/detail keeps its full logical text instead of forcing the pill to grow.
    assert pill._detail_label.text() == "L" * 200


def test_beamline_state_manager_adds_and_removes_pills(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {
            "states": [
                _state("limits", "DeviceWithinLimitsState"),
                _limits_state(name="samy_limits", device="samy"),
            ]
        },
        {},
    )

    assert sorted(beamline_state_manager._state_pills) == ["limits", "samy_limits"]
    assert beamline_state_manager._model.rowCount() == 2
    assert beamline_state_manager._state_pills["samy_limits"]._name_label.text() == "samy_limits"
    assert not beamline_state_manager._empty_label.isVisible()

    beamline_state_manager._state_pills["limits"].update_state(
        {"name": "limits", "status": "valid", "label": "Within limits."}, {}
    )
    summary = beamline_state_manager.state_summary()
    assert summary["limits"] == {"status": "valid", "label": "Within limits."}
    assert summary["samy_limits"]["status"] == "unknown"

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
    samy_limits_state = _limits_state(name="samy_limits", device="samy")

    beamline_state_manager.update_available_states({"states": [limits_state]}, {})
    pill = beamline_state_manager._state_pills["limits"]
    pill.set_expanded(True)
    config_form = pill._config_form

    beamline_state_manager.update_available_states(
        {"states": [limits_state, samy_limits_state]}, {}
    )

    assert beamline_state_manager._state_pills["limits"] is pill
    assert pill._config_form is config_form
    assert pill.is_expanded()
    assert sorted(beamline_state_manager._state_pills) == ["limits", "samy_limits"]


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


def test_beamline_state_manager_filters_status(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {"states": [_limits_state(name="samy_limits", device="samy"), _limits_state()]}, {}
    )

    assert isinstance(beamline_state_manager._toolbar, ModularToolBar)
    assert not beamline_state_manager._toolbar.components.exists("refresh")

    beamline_state_manager._state_pills["limits"].update_state(
        {"name": "limits", "status": "valid", "label": "Within limits."}, {}
    )
    beamline_state_manager._state_pills["samy_limits"].update_state(
        {"name": "samy_limits", "status": "invalid", "label": "Out of limits."}, {}
    )
    beamline_state_manager._selected_statuses = {"valid"}
    beamline_state_manager._apply_filters()

    assert not beamline_state_manager._hidden_summary.isHidden()
    assert "1 state is hidden" in beamline_state_manager._hidden_summary.text()
    assert not beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("limits").row()
    )
    assert beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("samy_limits").row()
    )

    beamline_state_manager._hidden_summary.click()

    assert not beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("samy_limits").row()
    )
    assert shiboken6.isValid(beamline_state_manager._state_pills["samy_limits"])

    beamline_state_manager._hidden_summary.click()

    assert beamline_state_manager._view.isRowHidden(
        beamline_state_manager._model.index_for_name("samy_limits").row()
    )
    assert shiboken6.isValid(beamline_state_manager._state_pills["samy_limits"])


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
                _limits_state(name="samx_limits"),
                _limits_state(name="samy_limits", device="samy"),
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


def test_beamline_state_manager_collapse_all(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {"states": [_limits_state(), _limits_state(name="samy_limits", device="samy")]}, {}
    )

    for pill in beamline_state_manager._state_pills.values():
        pill.set_expanded(True)
    assert all(pill.is_expanded() for pill in beamline_state_manager._state_pills.values())

    collapse_action = beamline_state_manager._toolbar.components.get_action("collapse_all")
    collapse_action.action.trigger()

    assert not any(pill.is_expanded() for pill in beamline_state_manager._state_pills.values())


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


def test_beamline_state_pill_emits_interlock_toggle_request(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)

    with qtbot.waitSignal(pill.scan_interlock_toggle_requested) as include_signal:
        pill._interlock_button.click()

    assert include_signal.args == ["limits", True]

    pill.set_scan_interlock(["valid"], False)

    with qtbot.waitSignal(pill.scan_interlock_toggle_requested) as exclude_signal:
        pill._interlock_button.click()

    assert exclude_signal.args == ["limits", False]


def test_beamline_state_pill_included_state_forces_card_background(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)
    colors = BeamlineStatePill._state_colors("unknown")

    assert f"border: 1px solid {colors['card_border']}" not in pill.styleSheet().split(":hover")[0]
    assert not pill._shadow.isEnabled()

    pill.set_scan_interlock(["valid"], False)

    assert f"border: 1px solid {colors['card_border']}" in pill.styleSheet()
    assert pill._shadow.isEnabled()
    assert "Watched by the scan interlock" in pill._interlock_button.toolTip()

    pill.set_scan_interlock(None, False)

    assert not pill._shadow.isEnabled()
    assert "Not watched by the scan interlock" in pill._interlock_button.toolTip()


def test_beamline_state_pill_triggered_interlock_animates(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)

    pill.set_scan_interlock(["valid"], True)

    assert pill._interlock_animation.state() == pill._interlock_animation.State.Running
    pill.interlock_pulse = 0.5

    stylesheet = pill.styleSheet()
    assert "border: 2px solid" in stylesheet
    assert "qlineargradient" in stylesheet

    pill.set_scan_interlock(["valid"], False)

    assert pill._interlock_animation.state() == pill._interlock_animation.State.Stopped
    assert pill._interlock_pulse == 0.0
    assert "border: 2px solid" not in pill.styleSheet()
    assert "border: 1px solid" in pill.styleSheet()


def test_beamline_state_pill_traveling_gradient_keeps_stops_sorted():
    for phase in (0.0, 0.2, 0.5, 0.8, 1.0):
        gradient = BeamlineStatePill._traveling_gradient("#101010", "#ff0000", phase)
        positions = [
            float(stop.split()[0].removeprefix("stop:"))
            for stop in gradient.split(", ")
            if stop.startswith("stop:")
        ]
        assert positions == sorted(positions)
        assert positions[0] == 0.0
        assert positions[-1] == 1.0


def test_beamline_state_manager_toolbar_scan_interlock_on_right(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)

    bundle = beamline_state_manager._toolbar.bundles["beamline_state_manager"]
    assert list(bundle.bundle_actions)[-3:] == [
        "scan_interlock_spacer",
        "separator",
        "scan_interlock",
    ]

    spacer_action = beamline_state_manager._toolbar.components.get_action("scan_interlock_spacer")
    assert spacer_action.container.sizePolicy().horizontalPolicy() == (
        spacer_action.container.sizePolicy().Policy.Expanding
    )

    interlock_action = beamline_state_manager._toolbar.components.get_action("scan_interlock")
    assert interlock_action.action.isCheckable()
    assert not interlock_action.action.isChecked()
    assert "disabled" in interlock_action.action.toolTip()


def test_beamline_state_manager_groups_states_under_headers(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {"states": [_limits_state(), _limits_state(name="samy_limits", device="samy")]}, {}
    )
    model = beamline_state_manager._model

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), model.HeaderRole) is None

    _install_fake_scan_interlock(
        beamline_state_manager, _FakeScanInterlock(states_watched={"samy_limits": "valid"})
    )

    assert model.rowCount() == 4
    assert model.data(model.index(0, 0), model.HeaderRole) == model.INTERLOCK_HEADER
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "Scan interlock states"
    assert model.data(model.index(1, 0), model.NameRole) == "samy_limits"
    assert model.data(model.index(2, 0), model.HeaderRole) == model.OTHERS_HEADER
    assert (
        model.data(model.index(2, 0), Qt.ItemDataRole.DisplayRole)
        == "Not included in scan interlock"
    )
    assert model.data(model.index(3, 0), model.NameRole) == "limits"
    assert sorted(beamline_state_manager._state_pills) == ["limits", "samy_limits"]

    _install_fake_scan_interlock(
        beamline_state_manager,
        _FakeScanInterlock(states_watched={"samy_limits": "valid", "limits": "valid"}),
    )

    assert model.rowCount() == 3
    assert model.data(model.index(0, 0), model.HeaderRole) == model.INTERLOCK_HEADER
    assert model.data(model.index(1, 0), model.NameRole) == "limits"
    assert model.data(model.index(2, 0), model.NameRole) == "samy_limits"

    _install_fake_scan_interlock(beamline_state_manager, _FakeScanInterlock())

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), model.HeaderRole) is None


def test_beamline_state_manager_header_visibility_follows_filters(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {"states": [_limits_state(), _limits_state(name="samy_limits", device="samy")]}, {}
    )
    _install_fake_scan_interlock(
        beamline_state_manager, _FakeScanInterlock(states_watched={"samy_limits": "valid"})
    )

    beamline_state_manager._state_pills["limits"].update_state(
        {"name": "limits", "status": "invalid", "label": "Out of limits."}, {}
    )
    beamline_state_manager._state_pills["samy_limits"].update_state(
        {"name": "samy_limits", "status": "valid", "label": "Within limits."}, {}
    )
    beamline_state_manager._selected_statuses = {"valid"}
    beamline_state_manager._apply_filters()

    model = beamline_state_manager._model
    assert not beamline_state_manager._view.isRowHidden(0)
    assert not beamline_state_manager._view.isRowHidden(model.index_for_name("samy_limits").row())
    assert beamline_state_manager._view.isRowHidden(2)
    assert beamline_state_manager._view.isRowHidden(model.index_for_name("limits").row())

    beamline_state_manager.clear_filters()

    assert not beamline_state_manager._view.isRowHidden(2)


def test_beamline_state_manager_interlock_states_bypass_filters(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {"states": [_limits_state(), _limits_state(name="samy_limits", device="samy")]}, {}
    )
    _install_fake_scan_interlock(
        beamline_state_manager, _FakeScanInterlock(states_watched={"samy_limits": "valid"})
    )

    beamline_state_manager._state_pills["limits"].update_state(
        {"name": "limits", "status": "invalid", "label": "Out of limits."}, {}
    )
    beamline_state_manager._state_pills["samy_limits"].update_state(
        {"name": "samy_limits", "status": "invalid", "label": "Out of limits."}, {}
    )
    beamline_state_manager._selected_statuses = {"valid"}
    beamline_state_manager._apply_filters()

    model = beamline_state_manager._model
    assert not beamline_state_manager._view.isRowHidden(model.index_for_name("samy_limits").row())
    assert beamline_state_manager._view.isRowHidden(model.index_for_name("limits").row())
    assert "1 state is hidden" in beamline_state_manager._hidden_summary.text()

    beamline_state_manager._device_filter_text = "nonexistent_device"
    beamline_state_manager._apply_filters()

    assert not beamline_state_manager._view.isRowHidden(model.index_for_name("samy_limits").row())


def test_beamline_state_manager_section_headers_are_widgets(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {"states": [_limits_state(), _limits_state(name="samy_limits", device="samy")]}, {}
    )
    _install_fake_scan_interlock(
        beamline_state_manager,
        _FakeScanInterlock(enabled=True, states_watched={"samy_limits": "valid"}),
    )

    model = beamline_state_manager._model
    delegate = beamline_state_manager._delegate
    header_index = model.index(0, 0)

    assert delegate.sizeHint(QStyleOptionViewItem(), header_index).height() == (
        delegate.HEADER_HEIGHT
    )
    assert model.flags(header_index) == Qt.ItemFlag.NoItemFlags

    # Both section headers are rendered by persistent header widgets, not by a custom paint().
    headers = beamline_state_manager._section_headers
    assert set(headers) == {model.INTERLOCK_HEADER, model.OTHERS_HEADER}
    assert headers[model.INTERLOCK_HEADER]._label.text() == "Scan interlock states"
    assert headers[model.OTHERS_HEADER]._label.text() == "Not included in scan interlock"
    assert not headers[model.INTERLOCK_HEADER]._icon.pixmap().isNull()


def test_beamline_state_manager_marks_triggered_pills(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states({"states": [_limits_state()]}, {})
    fake_interlock = _FakeScanInterlock(enabled=True, states_watched={"limits": "valid"})
    _install_fake_scan_interlock(beamline_state_manager, fake_interlock)

    pill = beamline_state_manager._state_pills["limits"]
    assert pill._interlock_required_statuses == ["valid"]
    assert pill._interlock_triggered

    pill.update_state({"name": "limits", "status": "valid", "label": "Within limits."}, {})

    assert not pill._interlock_triggered

    pill.update_state({"name": "limits", "status": "invalid", "label": "Out of limits."}, {})

    assert pill._interlock_triggered

    fake_interlock.enabled = False
    beamline_state_manager._refresh_scan_interlock()

    assert not pill._interlock_triggered
    assert pill._interlock_required_statuses == ["valid"]


def test_beamline_state_manager_orders_both_sections_by_status_severity(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states(
        {
            "states": [
                _limits_state(name="watched_valid"),
                _limits_state(name="watched_invalid"),
                _limits_state(name="free_warning"),
                _limits_state(name="free_invalid"),
            ]
        },
        {},
    )
    _install_fake_scan_interlock(
        beamline_state_manager,
        _FakeScanInterlock(
            enabled=True, states_watched={"watched_valid": "valid", "watched_invalid": "valid"}
        ),
    )
    pills = beamline_state_manager._state_pills
    pills["watched_valid"].update_state(
        {"name": "watched_valid", "status": "valid", "label": ""}, {}
    )
    pills["watched_invalid"].update_state(
        {"name": "watched_invalid", "status": "invalid", "label": ""}, {}
    )
    pills["free_warning"].update_state(
        {"name": "free_warning", "status": "warning", "label": ""}, {}
    )
    pills["free_invalid"].update_state(
        {"name": "free_invalid", "status": "invalid", "label": ""}, {}
    )

    model = beamline_state_manager._model
    names = [model.data(model.index(row, 0), model.NameRole) for row in range(model.rowCount())]

    # Interlock section: invalid before valid. Non-interlock section: invalid before warning.
    assert names == [
        None,  # "Scan interlock states" header
        "watched_invalid",
        "watched_valid",
        None,  # "Not included in scan interlock" header
        "free_invalid",
        "free_warning",
    ]
    assert pills["watched_invalid"]._interlock_triggered
    assert not pills["watched_valid"]._interlock_triggered


def test_beamline_state_manager_orders_by_status_severity_on_initial_render(
    qtbot, mocked_client, monkeypatch
):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    # The statuses are visible in the connector cache when the pills are first created, so the
    # severity order must hold from the very first render. ``get_last`` is patched (rather than
    # writing to the session-shared fake connector) so the seeded statuses can't leak into and
    # pollute other tests.
    seeded = {"limits": "valid", "samy_limits": "invalid"}
    real_get_last = mocked_client.connector.get_last

    def fake_get_last(endpoint, *args, **kwargs):
        topic = str(getattr(endpoint, "endpoint", endpoint))
        for name, status in seeded.items():
            if topic.endswith(f"/beamline_state/{name}"):
                return messages.BeamlineStateMessage(name=name, status=status, label="x")
        return real_get_last(endpoint, *args, **kwargs)

    monkeypatch.setattr(mocked_client.connector, "get_last", fake_get_last)

    beamline_state_manager.update_available_states(
        {"states": [_limits_state(), _limits_state(name="samy_limits", device="samy")]}, {}
    )

    model = beamline_state_manager._model
    names = [model.data(model.index(row, 0), model.NameRole) for row in range(model.rowCount())]
    assert names == ["samy_limits", "limits"]
    assert beamline_state_manager._state_pills["samy_limits"]._status == "invalid"


def test_beamline_state_manager_toolbar_toggle_writes_backend(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    fake_interlock = _FakeScanInterlock()
    _install_fake_scan_interlock(beamline_state_manager, fake_interlock)
    interlock_action = beamline_state_manager._toolbar.components.get_action("scan_interlock")

    interlock_action.action.setChecked(True)

    assert fake_interlock.enabled is True
    assert beamline_state_manager._interlock_enabled is True
    assert "armed" in interlock_action.action.toolTip()

    interlock_action.action.setChecked(False)

    assert fake_interlock.enabled is False
    assert "disabled" in interlock_action.action.toolTip()


def test_beamline_state_manager_pill_toggle_calls_backend(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states({"states": [_limits_state()]}, {})
    fake_interlock = _FakeScanInterlock()
    _install_fake_scan_interlock(beamline_state_manager, fake_interlock)

    beamline_state_manager._state_pills["limits"]._interlock_button.click()

    assert fake_interlock.added == [("limits", ["valid", "warning"])]
    # The toggle refreshes immediately, so the state is reflected without a backend notification.
    assert beamline_state_manager._interlock_states == {"limits": ["valid", "warning"]}

    beamline_state_manager._state_pills["limits"]._interlock_button.click()

    assert fake_interlock.removed == ["limits"]
    assert beamline_state_manager._interlock_states == {}


def test_beamline_state_pill_settings_warning_checkbox(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)

    # Default accepts VALID and WARNING, so the checkbox is unchecked.
    assert pill._interlock_warning_checkbox.isChecked() is False
    assert pill.interlock_statuses == ["valid", "warning"]

    with qtbot.waitSignal(pill.scan_interlock_statuses_changed) as signal:
        pill._interlock_warning_checkbox.setChecked(True)

    assert signal.args == ["limits", ["valid"]]
    assert pill.interlock_statuses == ["valid"]

    pill._interlock_warning_checkbox.setChecked(False)
    assert pill.interlock_statuses == ["valid", "warning"]


def test_beamline_state_pill_settings_warning_checkbox_reflects_statuses(qtbot, mocked_client):
    pill = create_widget(qtbot, BeamlineStatePill, state_name="limits", client=mocked_client)

    pill.set_interlock_statuses(["valid"])
    assert pill._interlock_warning_checkbox.isChecked() is True

    pill.set_interlock_statuses(["valid", "warning"])
    assert pill._interlock_warning_checkbox.isChecked() is False


def test_beamline_state_manager_settings_warning_reenrolls_watched_state(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states({"states": [_limits_state()]}, {})
    fake_interlock = _FakeScanInterlock(
        enabled=True, states_watched={"limits": ["valid", "warning"]}
    )
    _install_fake_scan_interlock(beamline_state_manager, fake_interlock)
    pill = beamline_state_manager._state_pills["limits"]
    assert pill.interlock_statuses == ["valid", "warning"]

    pill._interlock_warning_checkbox.setChecked(True)

    assert fake_interlock.added[-1] == ("limits", ["valid"])
    assert beamline_state_manager._interlock_states == {"limits": ["valid"]}


def test_beamline_state_manager_settings_warning_no_backend_when_not_watched(qtbot, mocked_client):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    beamline_state_manager.update_available_states({"states": [_limits_state()]}, {})
    fake_interlock = _FakeScanInterlock()
    _install_fake_scan_interlock(beamline_state_manager, fake_interlock)
    pill = beamline_state_manager._state_pills["limits"]

    pill._interlock_warning_checkbox.setChecked(True)

    # Not watched yet: no backend write, but the preference is kept and used when locked.
    assert fake_interlock.added == []
    assert pill.interlock_statuses == ["valid"]

    pill._interlock_button.click()
    assert fake_interlock.added == [("limits", ["valid"])]


def test_beamline_state_manager_lock_uses_dialog_status_preference(
    qtbot, mocked_client, monkeypatch
):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    fake_interlock = _FakeScanInterlock()
    _install_fake_scan_interlock(beamline_state_manager, fake_interlock)
    _stub_beamline_states_add(mocked_client)
    # Create a state that triggers on WARNING (statuses = ["valid"]) but is NOT enrolled now.
    _install_fake_add_dialog(
        monkeypatch,
        config=_limits_state(name="limits"),
        add_to_interlock=False,
        interlock_statuses=["valid"],
    )
    beamline_state_manager.open_add_state_dialog()
    assert fake_interlock.added == []

    # When the state's pill appears, it is seeded with the configured statuses.
    beamline_state_manager.update_available_states({"states": [_limits_state(name="limits")]}, {})
    pill = beamline_state_manager._state_pills["limits"]
    assert pill.interlock_statuses == ["valid"]

    # Clicking the lock later enrolls with the remembered preference, not the default.
    pill._interlock_button.click()

    assert fake_interlock.added == [("limits", ["valid"])]


def test_add_beamline_state_dialog_uses_generated_widgets_and_normalizes_name(qtbot, mocked_client):
    add_state_dialog = create_widget(qtbot, AddBeamlineStateDialog, client=mocked_client)
    limits_index = add_state_dialog._type_combo.findText(bl_states.DeviceWithinLimitsState.__name__)
    assert limits_index >= 0
    assert add_state_dialog._type_combo.findText("ShutterState") == -1
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


def test_add_beamline_state_dialog_interlock_checkboxes(qtbot, mocked_client):
    add_state_dialog = create_widget(qtbot, AddBeamlineStateDialog, client=mocked_client)

    # Not enrolled by default; VALID and WARNING are both accepted (WARNING does not trip it).
    assert add_state_dialog.add_to_interlock() is False
    assert add_state_dialog.interlock_statuses() == ["valid", "warning"]

    # The warning condition is independent of enrollment (settable without "Add to interlock").
    assert add_state_dialog._trigger_on_warning_checkbox.isEnabled()
    add_state_dialog._trigger_on_warning_checkbox.setChecked(True)
    assert add_state_dialog.interlock_statuses() == ["valid"]
    assert add_state_dialog.add_to_interlock() is False

    add_state_dialog._add_to_interlock_checkbox.setChecked(True)
    assert add_state_dialog.add_to_interlock() is True


def _install_fake_add_dialog(monkeypatch, *, config, add_to_interlock, interlock_statuses):
    class FakeAddDialog:
        def __init__(self, parent, client=None):
            pass

        def exec(self):
            return QDialog.Accepted

        @property
        def config_result(self):
            return config

        def add_to_interlock(self):
            return add_to_interlock

        def interlock_statuses(self):
            return interlock_statuses

        def cleanup(self):
            pass

        def deleteLater(self):  # noqa: N802
            pass

    monkeypatch.setattr(manager_module, "AddBeamlineStateDialog", FakeAddDialog)


def _stub_beamline_states_add(mocked_client):
    added_configs = []

    class StateManager:
        def add(self, config):
            added_configs.append(config)

    mocked_client.beamline_states = StateManager()
    return added_configs


def test_beamline_state_manager_add_dialog_enrolls_new_state_in_interlock(
    qtbot, mocked_client, monkeypatch
):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    fake_interlock = _FakeScanInterlock()
    _install_fake_scan_interlock(beamline_state_manager, fake_interlock)
    added_configs = _stub_beamline_states_add(mocked_client)
    new_config = _limits_state(name="new_state")
    _install_fake_add_dialog(
        monkeypatch,
        config=new_config,
        add_to_interlock=True,
        interlock_statuses=["valid", "warning"],
    )

    beamline_state_manager.open_add_state_dialog()

    assert added_configs == [new_config]
    assert fake_interlock.added == [("new_state", ["valid", "warning"])]


def test_beamline_state_manager_add_dialog_skips_interlock_when_not_requested(
    qtbot, mocked_client, monkeypatch
):
    beamline_state_manager = create_widget(qtbot, BeamlineStateManager, client=mocked_client)
    fake_interlock = _FakeScanInterlock()
    _install_fake_scan_interlock(beamline_state_manager, fake_interlock)
    added_configs = _stub_beamline_states_add(mocked_client)
    new_config = _limits_state(name="new_state")
    _install_fake_add_dialog(
        monkeypatch, config=new_config, add_to_interlock=False, interlock_statuses=["valid"]
    )

    beamline_state_manager.open_add_state_dialog()

    assert added_configs == [new_config]
    assert fake_interlock.added == []


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
