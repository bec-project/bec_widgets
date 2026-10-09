"""Tests for the Devices and Config views (device manager split into two views)."""

# pylint: disable=redefined-outer-name, protected-access, missing-function-docstring
import copy
from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.applications.views.devices_views import devices_core
from bec_widgets.applications.views.devices_views.devices_core import (
    Change,
    ConfigEditor,
    DeviceBrowser,
    configs_by_name,
    device_kind,
    diff_configs,
    format_value,
    parse_value,
    plan_requests,
    signal_entries,
)
from bec_widgets.applications.views.devices_views.devices_qml import (
    DeviceConfigViewQML,
    DevicesViewQML,
)
from bec_widgets.applications.views.devices_views.devices_qwidget import (
    DeviceConfigViewQWidget,
    DevicesViewQWidget,
)

from .conftest import create_widget

SESSION = {
    "samx": {
        "deviceClass": "ophyd_devices.SimPositioner",
        "readoutPriority": "baseline",
        "deviceConfig": {"limits": [-50, 50], "tolerance": 0.01},
        "deviceTags": ["user motors"],
        "needs": ["samy"],
        "connectionTimeout": 10,
    },
    "bpm4i": {
        "deviceClass": "ophyd_devices.SimMonitor",
        "readoutPriority": "monitored",
        "deviceConfig": {},
    },
}


class _SyncPool:
    """Runs QRunnables at once on the calling thread."""

    def start(self, worker):
        worker.run()


@pytest.fixture
def sync_pool():
    with mock.patch.object(devices_core.QThreadPool, "globalInstance", return_value=_SyncPool()):
        yield


@pytest.fixture
def editor(mocked_client):
    with mock.patch.object(
        mocked_client.device_manager,
        "_get_redis_device_config",
        return_value=[{"name": k, **copy.deepcopy(v)} for k, v in SESSION.items()],
    ):
        ed = ConfigEditor(mocked_client)
        ed.load_session()
        yield ed


# ------------------------------------------------------------------------------------ pure logic
def test_configs_by_name_keeps_unknown_keys_and_fills_defaults():
    cfgs = configs_by_name(SESSION)
    assert cfgs["samx"]["needs"] == ["samy"]
    assert cfgs["samx"]["connectionTimeout"] == 10
    assert cfgs["bpm4i"]["enabled"] is True
    assert cfgs["bpm4i"]["deviceTags"] == []


def test_diff_is_field_level_and_ordered():
    session = configs_by_name(SESSION)
    work = copy.deepcopy(session)
    work["samx"]["readoutPriority"] = "monitored"
    work["samx"]["deviceConfig"]["limits"] = [-10, 10]
    del work["bpm4i"]
    work["newmot"] = devices_core.normalize_config("newmot", {"deviceClass": "ophyd.EpicsMotor"})
    changes = diff_configs(session, work)
    assert [(c.kind, c.name) for c in changes] == [("M", "samx"), ("A", "newmot"), ("D", "bpm4i")]
    assert changes[0].fields == [
        ("readoutPriority", "baseline", "monitored"),
        ("deviceConfig.limits", "[-50, 50]", "[-10, 10]"),
    ]


def test_plan_requests_update_only_changed_updatable_keys():
    session = configs_by_name(SESSION)
    work = copy.deepcopy(session)
    work["samx"]["readoutPriority"] = "monitored"
    change = diff_configs(session, work)[0]
    assert plan_requests(change, session, work) == [
        ("update", {"samx": {"readoutPriority": "monitored"}})
    ]


def test_plan_requests_recreates_device_for_class_or_removed_key():
    session = configs_by_name(SESSION)
    work = copy.deepcopy(session)
    work["samx"]["deviceClass"] = "ophyd.EpicsMotor"
    change = diff_configs(session, work)[0]
    steps = plan_requests(change, session, work)
    assert [s[0] for s in steps] == ["remove", "add"]
    # the re-added device keeps keys the editor does not show
    assert steps[1][1]["samx"]["needs"] == ["samy"]

    work = copy.deepcopy(session)
    del work["samx"]["deviceConfig"]["tolerance"]
    change = diff_configs(session, work)[0]
    assert [s[0] for s in plan_requests(change, session, work)] == ["remove", "add"]
    assert plan_requests(Change("D", "bpm4i"), session, work) == [("remove", {"bpm4i": {}})]


def test_parse_and_format_values():
    assert parse_value("1,5") == 1.5
    assert parse_value("[1, 2]") == [1, 2]
    assert parse_value("X05LA:ES") == "X05LA:ES"
    assert parse_value("") is None
    assert format_value(-1.23456, 3, "mm") == "−1.235 mm"
    assert format_value(None, 3) == "—"
    assert format_value([1, 2, 3], None) == "list [3]"


# ------------------------------------------------------------------------------------ Config logic
def test_editor_tracks_changes_and_undo(editor):
    assert editor.changes() == []
    assert editor.bar_state()["changeText"] == "Same as session"
    editor.set_field("samx", "readoutPriority", "monitored")
    assert [c.kind for c in editor.changes()] == ["M"]
    assert editor.status["samx"] == "unchecked"
    assert editor.detail()["readoutWas"] == "In session: Baseline · once per scan"
    assert editor.rows()[0]["readoutWas"] == "was baseline"
    editor.undo()
    assert editor.changes() == []
    assert editor.status["samx"] == "session"


def test_editor_add_remove_and_name_rules(editor):
    assert editor.add_device("Bad Name", "ophyd.EpicsMotor") != ""
    assert "already exists" in editor.add_device("samx", "ophyd.EpicsMotor")
    assert editor.add_device("pinz2", "ophyd.EpicsMotor", "X05LA:Z2") == ""
    assert editor.selected == "pinz2"
    assert editor.work["pinz2"]["deviceConfig"] == {"prefix": "X05LA:Z2"}
    editor.remove("bpm4i")
    kinds = {c.name: c.kind for c in editor.changes()}
    assert kinds == {"pinz2": "A", "bpm4i": "D"}
    review = editor.review()
    assert [g["kind"] for g in review["groups"]] == ["A", "D"]
    assert review["applyText"] == "Apply 2 changes"
    editor.undo()
    assert "bpm4i" in editor.work


def test_editor_revert_and_config_value(editor):
    editor.set_config_value("samx", "limits", "[-5, 5]")
    assert editor.work["samx"]["deviceConfig"]["limits"] == [-5, 5]
    assert editor.detail()["deviceConfig"][0]["was"] == "In session: [-50, 50]"
    editor.revert("samx")
    assert editor.changes() == []


def test_editor_filters_and_facets(editor):
    editor.set_field("samx", "enabled", False)
    editor.set_query("bpm")
    assert [r["name"] for r in editor.rows()] == ["bpm4i"]
    editor.clear_filters()
    editor.toggle_facet("st", "changed", True)
    assert [r["name"] for r in editor.rows()] == ["samx"]
    status = editor.facet_sections()[0]
    assert status["items"][0] == {
        "value": "changed",
        "label": "Changed vs session",
        "count": 1,
        "checked": True,
    }
    assert editor.filters_active()


def test_scan_running_blocks_apply(editor):
    editor.set_field("samx", "enabled", False)
    assert editor.can_apply()
    editor.on_scan_status({"status": "open", "scan_number": 1285}, {})
    assert not editor.can_apply()
    assert editor.bar_state()["scanText"] == "Scan 1285 is running"
    assert not editor.apply()
    editor.on_scan_status({"status": "closed"}, {})
    assert editor.can_apply()


def test_apply_sends_one_request_per_device(editor, sync_pool):
    editor.set_field("samx", "readoutPriority", "monitored")
    editor.remove("bpm4i")
    helper = mock.MagicMock()
    editor._helper = helper
    finished = []
    editor.apply_finished.connect(lambda ok, failed: finished.append((ok, failed)))
    assert editor.apply()
    calls = [c.kwargs for c in helper.send_config_request.call_args_list]
    assert calls == [
        {
            "action": "update",
            "config": {"samx": {"readoutPriority": "monitored"}},
            "wait_for_response": True,
        },
        {"action": "remove", "config": {"bpm4i": {}}, "wait_for_response": True},
    ]
    assert finished == [(2, 0)]
    assert [r["state"] for r in editor.apply_rows] == ["done", "done"]
    assert editor.apply_summary == "2 of 2 changes applied"


def test_apply_reports_failed_device(editor, sync_pool):
    editor.set_field("samx", "readoutPriority", "monitored")
    helper = mock.MagicMock()
    helper.send_config_request.side_effect = RuntimeError("PV X05LA-ES:Z not found")
    editor._helper = helper
    editor.apply()
    assert editor.apply_rows[0]["state"] == "failed"
    assert editor.status["samx"] == "invalid"
    assert "not found" in editor.messages["samx"]
    assert editor.problem_counts() == (1, 0)


def test_clear_session_needs_typed_confirmation(editor, sync_pool):
    with mock.patch.object(editor.client.config, "reset_config") as reset:
        assert editor.clear_session("clear") == "Type CLEAR to confirm"
        reset.assert_not_called()
        editor.on_scan_status({"status": "open"}, {})
        assert editor.clear_session("CLEAR") == "Clearing is not possible during a scan"
        editor.on_scan_status({"status": "closed"}, {})
        assert editor.clear_session("CLEAR") == ""
        reset.assert_called_once()


# ------------------------------------------------------------------------------------ Devices logic
def test_device_kind_and_browser_rows(mocked_client):
    devices = mocked_client.device_manager.devices
    assert device_kind(devices["samx"]) == "positioner"
    assert device_kind(devices["eiger"]) == "detector"
    assert device_kind(devices["bpm4i"]) == "monitor"
    browser = DeviceBrowser(mocked_client)
    rows = browser.rows()
    assert rows[0]["name"] == "samx"
    assert all(r["kind"] == "positioner" for r in rows)
    browser.set_kind("detector")
    assert {r["name"] for r in browser.rows()} == {"eiger", "async_device"}
    browser.set_kind("any")
    browser.set_query("bpm4")
    assert [r["name"] for r in browser.rows()] == ["bpm4i"]
    browser.cleanup()


def test_browser_readback_and_open_request(mocked_client):
    browser = DeviceBrowser(mocked_client)
    browser.set_kind("monitor")
    browser.select("bpm4i")
    browser.on_readback({"signals": {"bpm4i": {"value": 12.5}}}, {})
    browser.on_readback({"signals": {"bpm4i": {"value": 13.5}}}, {})
    assert browser.spark_points() == [12.5, 13.5]
    assert browser.detail()["valueText"] == "13.5"
    opened = []
    browser.open_in_workspace.connect(lambda w, d: opened.append((w, d)))
    browser.request_open()
    assert opened == [("Waveform", "bpm4i")]
    browser.cleanup()


def test_signal_entries_split_readings_and_settable_settings(mocked_client, monkeypatch):
    samx = mocked_client.device_manager.devices["samx"]
    entries = {e["key"]: e for e in signal_entries(samx)}
    assert entries["readback"]["section"] == "reading"
    assert entries["velocity"]["section"] == "setting"
    assert entries["velocity"]["settable"]
    info = copy.deepcopy(samx._info)
    info["signals"]["velocity"]["signal_class"] = "EpicsSignalRO"
    monkeypatch.setattr(samx, "_info", info)
    assert not {e["key"]: e for e in signal_entries(samx)}["velocity"]["settable"]
    info = copy.deepcopy(info)
    info["signals"]["velocity"]["signal_class"] = "Signal"
    info["write_access"] = False
    monkeypatch.setattr(samx, "_info", info)
    assert not {e["key"]: e for e in signal_entries(samx)}["velocity"]["settable"]


def test_browser_shows_settings_values_and_sets_them(mocked_client, sync_pool):
    browser = DeviceBrowser(mocked_client)
    browser.select("samx")
    browser.on_config({"signals": {"samx_velocity": {"value": 2.0}}}, {"device": "samx"})
    rows = {r["key"]: r for r in browser.signal_rows()}
    assert "readback" not in rows  # the positioner card shows it
    assert rows["velocity"]["valueText"] == "2"
    with mock.patch.object(browser._devices()["samx"], "velocity", create=True) as velocity:
        browser.set_signal("velocity", "2,5")
        velocity.set.assert_called_once_with(2.5)
        row = {r["key"]: r for r in browser.signal_rows()}["velocity"]
        assert (row["statusTone"], row["statusText"]) == ("ok", "Set to 2.5")
        velocity.set.side_effect = RuntimeError("Velocity above limit 10")
        browser.set_signal("velocity", "20")
        row = {r["key"]: r for r in browser.signal_rows()}["velocity"]
        assert row["statusTone"] == "err"
        assert "Velocity above limit 10" in row["statusText"]
    browser.cleanup()


def test_browser_follows_config_of_selected_device_only(mocked_client):
    dispatcher = mock.MagicMock()
    browser = DeviceBrowser(mocked_client, dispatcher)
    browser.select("samx")
    browser.select("samy")
    endpoints = [c.args[1] for c in dispatcher.connect_slot.call_args_list]
    assert MessageEndpoints.device_read_configuration("samy") in endpoints
    dispatcher.disconnect_slot.assert_any_call(
        browser.on_config, MessageEndpoints.device_read_configuration("samx")
    )
    browser.cleanup()
    dispatcher.disconnect_slot.assert_any_call(
        browser.on_config, MessageEndpoints.device_read_configuration("samy")
    )


# ------------------------------------------------------------------------------------ both views
@pytest.fixture(params=[DeviceConfigViewQWidget, DeviceConfigViewQML])
def config_view(request, qtbot, mocked_client):
    with mock.patch.object(
        mocked_client.device_manager,
        "_get_redis_device_config",
        return_value=[{"name": k, **copy.deepcopy(v)} for k, v in SESSION.items()],
    ):
        widget = create_widget(qtbot, request.param, client=mocked_client)
    yield widget


@pytest.fixture(params=[DevicesViewQWidget, DevicesViewQML])
def devices_view(request, qtbot, mocked_client):
    yield create_widget(qtbot, request.param, client=mocked_client)


def test_config_view_shows_session_and_edits(config_view, qtbot):
    editor = config_view.editor
    assert len(editor.work) == 2
    editor.select("bpm4i")
    editor.set_field("bpm4i", "enabled", False)
    qtbot.wait(20)
    assert editor.bar_state()["reviewText"] == "Review changes (1)"
    if isinstance(config_view, DeviceConfigViewQML):
        assert config_view.backend.rows.rowCount() == 2
        assert config_view.backend.detail["name"] == "bpm4i"
        assert config_view.backend.selectedIndex == 1
    else:
        assert config_view.model.rowCount() == 2
        assert config_view.i_name.text() == "bpm4i"
        assert config_view.review_btn.isEnabled()


def test_config_view_review_sheet_opens_and_closes(config_view, qtbot):
    config_view.editor.set_field("samx", "readoutPriority", "monitored")
    sheet = config_view.open_review()
    qtbot.wait(20)
    if isinstance(config_view, DeviceConfigViewQML):
        root = config_view.view.rootObject()
        qtbot.waitUntil(lambda: root.property("reviewOpen"), timeout=1000)
        config_view.close_sheet()
        qtbot.waitUntil(lambda: not root.property("reviewOpen"), timeout=1000)
    else:
        assert sheet.isVisible()
        sheet.reject()


def test_config_view_toggles_enabled_from_table(config_view, qtbot):
    if isinstance(config_view, DeviceConfigViewQML):
        config_view.backend.setField("samx", "enabled", False)
    else:
        config_view.model.toggled.emit("samx", False)
    qtbot.wait(20)
    assert config_view.editor.work["samx"]["enabled"] is False


def test_devices_view_lists_motors_and_follows_selection(devices_view, qtbot):
    browser = devices_view.browser
    assert browser.selected == "samx"
    browser.set_kind("monitor")
    browser.select("bpm4i")
    qtbot.wait(20)
    if isinstance(devices_view, DevicesViewQML):
        assert devices_view.backend.detail["name"] == "bpm4i"
        assert devices_view.backend.kind == "monitor"
    else:
        assert devices_view.d_name.text() == "bpm4i"
        assert devices_view.model.rows[devices_view.table.currentIndex().row()]["name"] == "bpm4i"


def test_devices_view_subscribes_to_visible_readbacks(devices_view):
    assert "samx" in devices_view.browser._subscribed
    devices_view.browser.set_kind("detector")
    devices_view.browser.rows()
    assert "samx" not in devices_view.browser._subscribed
    assert "eiger" in devices_view.browser._subscribed


def test_main_app_has_no_device_views_by_default(monkeypatch, qtbot, mocked_client):
    from bec_widgets.applications.main_app import BECMainApp

    monkeypatch.delenv("BEC_DEVICE_VIEWS", raising=False)
    app = BECMainApp(client=mocked_client, anim_duration=60, show_examples=False)
    qtbot.addWidget(app)
    assert "Devices" not in app._view_index
    assert "Config" not in app._view_index
    assert "DM" in app._view_index


@pytest.mark.parametrize("flavor", ["qml", "qwidget"])
def test_main_app_adds_device_views_when_opted_in(flavor, monkeypatch, qtbot, mocked_client):
    from bec_widgets.applications.main_app import BECMainApp

    monkeypatch.setenv("BEC_DEVICE_VIEWS", flavor)
    app = BECMainApp(client=mocked_client, anim_duration=60, show_examples=False)
    qtbot.addWidget(app)
    assert {"Devices", "Config", "DM"} <= set(app._view_index)
    with mock.patch.object(app.dock_area.dock_area, "new") as new:
        app.devices_view.browser.open_in_workspace.emit("PositionerBox", "samx")
    new.assert_called_once_with("PositionerBox")
    new.return_value.set_positioner.assert_called_once_with("samx")
    assert app.stack.currentIndex() == app._view_index["Docks"]


def test_devices_view_lets_users_change_a_setting(devices_view, qtbot, sync_pool):
    browser = devices_view.browser
    browser.on_config({"signals": {"samx_velocity": {"value": 2.0}}}, {"device": "samx"})
    with mock.patch.object(browser._devices()["samx"], "velocity", create=True) as velocity:
        if isinstance(devices_view, DevicesViewQML):
            qtbot.waitUntil(lambda: devices_view.backend.settings.count == 1, timeout=1000)
            devices_view.backend.setSignal("velocity", "3")
            qtbot.waitUntil(
                lambda: devices_view.backend.settings.items[0]["statusText"] == "Set to 3",
                timeout=1000,
            )
        else:
            qtbot.waitUntil(lambda: "velocity" in devices_view._signal_widgets, timeout=1000)
            widgets = devices_view._signal_widgets["velocity"]
            widgets["edit"].setText("3")
            widgets["edit"].returnPressed.emit()
            qtbot.waitUntil(lambda: widgets["status"].text() == "Set to 3", timeout=1000)
        velocity.set.assert_called_once_with(3)
