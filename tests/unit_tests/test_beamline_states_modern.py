import pytest
from bec_lib import bl_states, messages

from bec_widgets.widgets.services.beamline_states.modern import actions
from bec_widgets.widgets.services.beamline_states.modern.beamline_states_qml import (
    BeamlineStatesQML,
)
from bec_widgets.widgets.services.beamline_states.modern.beamline_states_widget import (
    BeamlineStatesWidget,
)

from .conftest import create_widget


class _FakeScanInterlock:
    def __init__(self, enabled=False, states_watched=None):
        self.enabled = enabled
        self._states = {name: list(v) for name, v in (states_watched or {}).items()}
        self.added = []
        self.removed = []

    @property
    def states_watched(self):
        return {name: list(v) for name, v in self._states.items()}

    def add_state_to_interlock(self, state_name, required_value="valid"):
        self.added.append((state_name, list(required_value)))
        self._states[state_name] = list(required_value)

    def remove_state_from_interlock(self, state_name):
        self.removed.append(state_name)
        self._states.pop(state_name, None)


def _limits(name, device="samx"):
    config = bl_states.DeviceWithinLimitsState.CONFIG_CLASS(
        name=name, device=device, signal=device, low_limit=0.0, high_limit=10.0, tolerance=0.1
    )
    return messages.BeamlineStateConfig(
        name=name,
        state_type="DeviceWithinLimitsState",
        parameters=config.model_dump(exclude={"name"}),
    )


@pytest.fixture(params=[BeamlineStatesQML, BeamlineStatesWidget], ids=["qml", "qwidget"])
def view(request, qtbot, mocked_client):
    widget = create_widget(qtbot, request.param, client=mocked_client)
    widget.controller._interlock = _FakeScanInterlock(
        enabled=True, states_watched={"samx_ok": ["valid", "warning"]}
    )
    widget.controller.refresh_interlock()
    widget.controller.update_available_states(
        {"states": [_limits("samx_ok"), _limits("samy_ok", "samy"), _limits("temp_ok", "temp")]}, {}
    )
    return widget


def _names(widget):
    return [row["name"] for row in widget.controller.model.rows()]


def _status(widget, name, status, label="label"):
    widget.controller.update_state({"name": name, "status": status, "label": label}, {})


def test_rows_grouped_watched_first_then_by_severity(view):
    _status(view, "temp_ok", "invalid")
    _status(view, "samy_ok", "valid")
    assert _names(view) == ["samx_ok", "temp_ok", "samy_ok"]
    sections = [row["section"] for row in view.controller.model.rows()]
    assert sections == ["interlock", "others", "others"]


def test_state_summary_includes_all_states(view):
    _status(view, "samy_ok", "warning", "close to limit")
    view.controller.toggleStatusFilter("warning")
    summary = view.state_summary()
    assert set(summary) == {"samx_ok", "samy_ok", "temp_ok"}
    assert summary["samy_ok"] == {"status": "warning", "label": "close to limit"}
    assert summary["temp_ok"]["status"] == "unknown"


def test_status_chip_filter_keeps_watched_states(view):
    _status(view, "samy_ok", "valid")
    _status(view, "temp_ok", "invalid")
    view.controller.toggleStatusFilter("invalid")
    assert _names(view) == ["samx_ok", "temp_ok"]
    assert view.controller.hiddenCount == 1
    view.controller.setShowFiltered(True)
    rows = {row["name"]: row for row in view.controller.model.rows()}
    assert rows["samy_ok"]["filteredOut"] is True
    view.clear_filters()
    assert view.controller.hiddenCount == 0
    assert len(_names(view)) == 3


def test_search_matches_name_or_device(view):
    view.controller.setSearchText("temp")
    assert _names(view) == ["samx_ok", "temp_ok"]
    view.controller.setSearchText("samy, temp")
    assert set(_names(view)) == {"samx_ok", "samy_ok", "temp_ok"}


def test_triggered_state_blocks_banner(view):
    # A watched state without a status yet (unknown) is not accepted, so it blocks scans.
    assert view.controller.blockingStates == ["samx_ok"]
    _status(view, "samx_ok", "valid")
    assert view.controller.blockingStates == []
    _status(view, "samx_ok", "invalid")
    assert view.controller.blockingStates == ["samx_ok"]
    assert view.controller.model.rows()[0]["triggered"] is True
    view.controller.setInterlockArmed(False)
    assert view.controller._interlock.enabled is False
    assert view.controller.blockingStates == []


def test_lock_toggles_interlock_membership(view):
    view.controller.toggleWatched("samy_ok")
    assert view.controller._interlock.added == [("samy_ok", ["valid", "warning"])]
    assert "samy_ok" in [r["name"] for r in view.controller.model.rows() if r["watched"]]
    view.controller.toggleWatched("samx_ok")
    assert view.controller._interlock.removed == ["samx_ok"]


def test_trigger_on_warning_reenrolls_watched_state(view):
    view.controller.setTriggerOnWarning("samx_ok", True)
    assert view.controller._interlock.added == [("samx_ok", ["valid"])]
    view.controller.setTriggerOnWarning("samy_ok", True)
    assert len(view.controller._interlock.added) == 1
    view.controller.toggleWatched("samy_ok")
    assert view.controller._interlock.added[-1] == ("samy_ok", ["valid"])


class _StateClient:
    def __init__(self):
        self.parameters = None

    def update_parameters(self, **kwargs):
        self.parameters = kwargs


class _StateManager:
    def __init__(self):
        self.deleted = None
        self.samx_ok = _StateClient()

    def delete(self, state_name):
        self.deleted = state_name


def test_remove_state_calls_backend(view):
    view.controller.client.beamline_states = _StateManager()
    view.controller.removeState("samy_ok")
    assert view.controller.client.beamline_states.deleted == "samy_ok"


def test_removed_state_disappears(view):
    view.controller.update_available_states({"states": [_limits("samx_ok")]}, {})
    assert _names(view) == ["samx_ok"]
    assert view.controller._subscribed == {"samx_ok"}


def test_edit_pushes_parameters(view, monkeypatch):

    class _Dialog:
        def __init__(self, name, config_class, parameters, parent, client=None):
            data = dict(parameters, high_limit=20.0)
            self.result_config = config_class(name=name, **data)

        def exec(self):
            return actions.QDialog.DialogCode.Accepted

        def cleanup(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr(actions, "EditBeamlineStateDialog", _Dialog)
    view.controller.client.beamline_states = _StateManager()
    view.controller.requestEdit("samx_ok")
    assert view.controller.client.beamline_states.samx_ok.parameters["high_limit"] == 20.0


def test_qwidget_cards_follow_rows(qtbot, mocked_client):
    widget = create_widget(qtbot, BeamlineStatesWidget, client=mocked_client)
    widget.controller._interlock = _FakeScanInterlock()
    widget.controller.update_available_states({"states": [_limits("a"), _limits("b")]}, {})
    card_a = widget._cards["a"]
    widget.controller.update_state({"name": "b", "status": "invalid", "label": "x"}, {})
    assert widget._cards["a"] is card_a
    assert widget._list_layout.indexOf(widget._cards["b"]) < widget._list_layout.indexOf(card_a)
    widget._toggle_expanded("a")
    assert card_a.is_expanded()
    widget.collapse_all()
    assert not card_a.is_expanded()


def test_qml_view_loads_and_collapses(qtbot, mocked_client):
    widget = create_widget(qtbot, BeamlineStatesQML, client=mocked_client)
    root = widget.view.rootObject()
    assert root is not None
    root.setProperty("expanded", {"a": True})

    def expanded():
        value = root.property("expanded")
        return value.toVariant() if hasattr(value, "toVariant") else value

    assert expanded() == {"a": True}
    widget.collapse_all()
    assert expanded() == {}
