"""Tests for the QML and QWidget ports of the beamline state manager."""

# pylint: disable=redefined-outer-name, protected-access, missing-function-docstring
import pytest
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QDialog, QMessageBox

from bec_widgets.widgets.services.beamline_states import beamline_states_ux_common as common
from bec_widgets.widgets.services.beamline_states.beamline_states_qml import BeamlineStatesQML
from bec_widgets.widgets.services.beamline_states.beamline_states_qwidget import (
    BeamlineStatesQWidget,
)
from bec_widgets.widgets.services.beamline_states.beamline_states_ux_common import (
    EditBeamlineStateDialog,
    format_parameter,
    state_device,
)

from .conftest import create_widget
from .test_beamline_state_pill import _FakeScanInterlock, _limits_state


def _message(name: str, status: str, label: str = "") -> dict:
    return {"name": name, "status": status, "label": label or f"{name} is {status}"}


@pytest.fixture(params=[BeamlineStatesQML, BeamlineStatesQWidget])
def manager(request, qtbot, mocked_client):
    widget = create_widget(qtbot, request.param, client=mocked_client)
    widget._scan_interlock = _FakeScanInterlock()
    widget._refresh_scan_interlock()
    return widget


def _load(manager, *names_devices):
    states = [_limits_state(name=name, device=device) for name, device in names_devices]
    manager.update_available_states({"states": states}, {})


def _state_rows(manager) -> list[dict]:
    return [row for row in manager.view_state()["rows"] if row["kind"] == "state"]


def test_helpers():
    assert format_parameter(0.1) == "0.1"
    assert format_parameter(10.0) == "10"
    assert format_parameter(None) == "—"
    assert state_device(_limits_state(device="samy")) == "samy"
    assert state_device(None) is None


def test_empty_state(manager):
    state = manager.view_state()
    assert state["empty"]
    assert state["rows"] == []
    assert state["interlockText"] == "Off"


def test_adds_and_removes_states_and_subscriptions(manager, mocked_client):
    _load(manager, ("limits", "samx"), ("samy_limits", "samy"))
    assert manager._subscribed == {"limits", "samy_limits"}
    assert [row["name"] for row in _state_rows(manager)] == ["limits", "samy_limits"]

    manager.update_state(_message("limits", "valid", "Within limits."))
    summary = manager.state_summary()
    assert summary["limits"] == {"status": "valid", "label": "Within limits."}
    assert summary["samy_limits"]["status"] == "unknown"

    _load(manager, ("limits", "samx"))
    assert manager._subscribed == {"limits"}
    assert list(manager.state_summary()) == ["limits"]


def test_reads_cached_state_on_add(qtbot, mocked_client):
    from bec_lib import messages

    mocked_client.connector.xadd(
        MessageEndpoints.beamline_state("cached_limits"),
        {
            "data": messages.BeamlineStateMessage(
                name="cached_limits", status="invalid", label="Out of range"
            )
        },
    )
    widget = create_widget(qtbot, BeamlineStatesQWidget, client=mocked_client)
    widget._scan_interlock = _FakeScanInterlock()
    _load(widget, ("cached_limits", "samx"))
    assert widget.state_summary()["cached_limits"] == {"status": "invalid", "label": "Out of range"}


def test_ignores_messages_for_unknown_states(manager):
    _load(manager, ("limits", "samx"))
    manager.update_state(_message("other", "invalid"))
    assert "other" not in manager.state_summary()
    assert manager.state_summary()["limits"]["status"] == "unknown"


def test_orders_by_severity_and_groups_by_interlock(manager):
    _load(manager, ("a", "samx"), ("b", "samy"), ("c", "samz"), ("d", "bpm4i"))
    for name, status in (("a", "valid"), ("b", "warning"), ("c", "invalid"), ("d", "valid")):
        manager.update_state(_message(name, status))
    manager._scan_interlock = _FakeScanInterlock(states_watched={"d": "valid", "b": "valid"})
    manager._refresh_scan_interlock()

    rows = manager.view_state()["rows"]
    assert [(row["kind"], row["name"]) for row in rows] == [
        ("header", "interlock"),
        ("state", "b"),
        ("state", "d"),
        ("header", "others"),
        ("state", "c"),
        ("state", "a"),
    ]
    assert rows[0]["count"] == 2 and rows[3]["count"] == 2


def test_status_chips_filter_and_watched_states_bypass(manager):
    _load(manager, ("a", "samx"), ("b", "samy"), ("c", "samz"))
    manager.update_state(_message("a", "valid"))
    manager.update_state(_message("b", "invalid"))
    manager.update_state(_message("c", "valid"))
    manager._scan_interlock = _FakeScanInterlock(states_watched={"c": "valid"})
    manager._refresh_scan_interlock()

    chips = {chip["status"]: chip for chip in manager.view_state()["chips"]}
    assert chips["valid"]["text"] == "2 valid"
    assert chips["invalid"]["text"] == "1 invalid"

    manager.toggle_status_filter("invalid")
    state = manager.view_state()
    assert [row["name"] for row in _state_rows(manager)] == ["c", "b"]
    assert state["hiddenCount"] == 1
    assert state["filtersActive"]
    assert {chip["status"]: chip["active"] for chip in state["chips"]}["invalid"]

    manager.set_show_hidden(True)
    assert {row["name"] for row in _state_rows(manager)} == {"a", "b", "c"}

    manager.toggle_status_filter("invalid")
    assert manager._selected_statuses is None


def test_text_filter_matches_name_and_device(manager):
    _load(manager, ("limits", "samx"), ("temp", "bpm4i"))
    manager.set_filter_text("bpm")
    assert [row["name"] for row in _state_rows(manager)] == ["temp"]
    manager.set_filter_text("lim, temp")
    assert len(_state_rows(manager)) == 2
    manager.set_filter_text("nothing")
    assert manager.view_state()["noMatches"]
    manager.clear_filters()
    assert manager.view_state()["filterText"] == ""
    assert len(_state_rows(manager)) == 2


def test_toggle_interlock_for_state(manager):
    fake = _FakeScanInterlock()
    manager._scan_interlock = fake
    _load(manager, ("limits", "samx"))

    manager.toggle_interlock_for("limits")
    assert fake.added == [("limits", ["valid", "warning"])]
    assert _state_rows(manager)[0]["watched"]

    manager.toggle_interlock_for("limits")
    assert fake.removed == ["limits"]
    assert not _state_rows(manager)[0]["watched"]


def test_trip_on_warning(manager):
    fake = _FakeScanInterlock()
    manager._scan_interlock = fake
    _load(manager, ("limits", "samx"))

    # not watched yet: kept as preference for when it is added
    manager.set_trip_on_warning("limits", True)
    assert fake.added == []
    assert _state_rows(manager)[0]["tripOnWarning"]
    manager.toggle_interlock_for("limits")
    assert fake.added == [("limits", ["valid"])]

    # watched: written to the interlock right away
    manager.set_trip_on_warning("limits", False)
    assert fake.added[-1] == ("limits", ["valid", "warning"])
    assert _state_rows(manager)[0]["acceptedText"] == "VALID or WARNING"


def test_tripped_state_and_banner(manager):
    manager._scan_interlock = _FakeScanInterlock(enabled=True, states_watched={"limits": "valid"})
    _load(manager, ("limits", "samx"))
    manager._refresh_scan_interlock()
    manager.update_state(_message("limits", "valid"))
    state = manager.view_state()
    assert state["interlockText"] == "Armed" and state["banner"] == ""

    manager.update_state(_message("limits", "warning"))
    state = manager.view_state()
    assert state["interlockText"] == "Tripped"
    assert state["interlockTone"] == "danger"
    assert "limits" in state["banner"]
    assert _state_rows(manager)[0]["tripped"]

    manager._on_interlock_enabled_changed(False)
    assert not _state_rows(manager)[0]["tripped"]
    assert manager.view_state()["banner"] == ""


def test_set_interlock_enabled_writes_backend(manager):
    fake = _FakeScanInterlock()
    manager._scan_interlock = fake
    manager.set_interlock_enabled(True)
    assert fake.enabled is True
    assert manager.view_state()["interlockEnabled"]


def test_interlock_failure_is_reported(manager, monkeypatch):
    class Broken(_FakeScanInterlock):
        def add_state_to_interlock(self, state_name, required_value="valid"):
            raise RuntimeError("no actor")

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    manager._scan_interlock = Broken()
    _load(manager, ("limits", "samx"))
    manager.toggle_interlock_for("limits")
    assert warnings == ["no actor"]


def test_expand_and_collapse_all(manager):
    _load(manager, ("a", "samx"), ("b", "samy"))
    manager.toggle_expanded("a")
    manager.set_expanded("b", True)
    assert all(row["expanded"] for row in _state_rows(manager))
    params = {p["key"]: p["value"] for p in _state_rows(manager)[0]["params"]}
    assert params["device"] == "samx" and params["high_limit"] == "10"
    manager.collapse_all()
    assert not any(row["expanded"] for row in _state_rows(manager))


def test_remove_state_confirms(manager, mocked_client, monkeypatch):
    class StateManager:
        deleted = None

        def delete(self, name):
            self.deleted = name

    mocked_client.beamline_states = StateManager()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    manager.remove_state("limits")
    assert mocked_client.beamline_states.deleted is None
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    manager.remove_state("limits")
    assert mocked_client.beamline_states.deleted == "limits"


def test_edit_state_sends_new_parameters(manager, mocked_client, monkeypatch):
    class StateClient:
        parameters = None

        def update_parameters(self, **kwargs):
            self.parameters = kwargs

    class StateManager:
        limits = StateClient()

    mocked_client.beamline_states = StateManager()
    _load(manager, ("limits", "samx"))

    def fake_exec(dialog):
        dialog.form.input_widget("high_limit").setValue(20.0)
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(EditBeamlineStateDialog, "exec", fake_exec)
    manager.edit_state("limits")
    assert mocked_client.beamline_states.limits.parameters["high_limit"] == 20.0
    assert mocked_client.beamline_states.limits.parameters["device"] == "samx"


def test_update_parameters_unknown_state(manager, mocked_client, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    mocked_client.beamline_states = object()
    assert not manager.update_state_parameters("limits", _limits_state())
    assert "not available" in warnings[0]


def test_add_state_dialog_adds_to_interlock(manager, mocked_client, monkeypatch):
    added = []

    class StateManager:
        def add(self, config):
            added.append(config)

    class FakeDialog:
        config_result = _limits_state(name="new_state")

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def add_to_interlock(self):
            return True

        def interlock_statuses(self):
            return ["valid"]

        def cleanup(self):
            pass

        def deleteLater(self):  # pylint: disable=invalid-name
            pass

    fake = _FakeScanInterlock()
    manager._scan_interlock = fake
    mocked_client.beamline_states = StateManager()
    monkeypatch.setattr(common, "AddBeamlineStateDialog", FakeDialog)
    manager.open_add_state_dialog()
    assert added[0].name == "new_state"
    assert fake.added == [("new_state", ["valid"])]


def test_renderer_follows_state(manager, qtbot):
    _load(manager, ("a", "samx"), ("b", "samy"))
    manager.update_state(_message("b", "invalid"))
    manager.set_expanded("a", True)
    if isinstance(manager, BeamlineStatesQML):
        assert isinstance(manager.view, QQuickWidget)
        assert manager.view.status() == QQuickWidget.Status.Ready
        rows = manager.backend._rows.items
        assert [row["name"] for row in rows] == ["b", "a"]
        assert manager.backend.state["total"] == 2
    else:
        rows = manager.state_rows
        assert set(rows) == {"a", "b"}
        assert rows["a"].details.isVisibleTo(manager)
        assert not rows["b"].details.isVisibleTo(manager)
        assert rows["b"].status_pill.text == "Invalid"
        first = rows["a"]
        manager.update_state(_message("a", "warning"))
        assert manager.state_rows["a"] is first


def test_qwidget_tripped_row_animates(qtbot, mocked_client):
    widget = create_widget(qtbot, BeamlineStatesQWidget, client=mocked_client)
    widget._scan_interlock = _FakeScanInterlock(enabled=True, states_watched={"a": "valid"})
    _load(widget, ("a", "samx"))
    widget._refresh_scan_interlock()
    widget.update_state(_message("a", "invalid"))
    row = widget.state_rows["a"]
    assert row._flash_animation.state() == row._flash_animation.State.Running
    assert widget.banner.isVisibleTo(widget)
    widget.update_state(_message("a", "valid"))
    assert row._flash_animation.state() == row._flash_animation.State.Stopped


def test_ports_are_not_rpc_or_designer_plugins():
    for cls in (BeamlineStatesQML, BeamlineStatesQWidget):
        assert cls.PLUGIN is False and cls.RPC is False
        assert cls.rpc_widget_class == "BeamlineStateManager"
