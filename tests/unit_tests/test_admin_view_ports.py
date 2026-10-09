"""Tests for the reworked admin view (QML and QWidget) and its guided experiment switch."""

# pylint: disable=protected-access,redefined-outer-name
import time
from datetime import datetime
from unittest import mock

import pytest
from qtpy.QtCore import QUrl
from qtpy.QtNetwork import QNetworkRequest

from bec_widgets.applications.views.admin_view import admin_view as admin_view_module
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.services.bec_atlas_admin_view.admin_ux import admin_demo
from bec_widgets.widgets.services.bec_atlas_admin_view.admin_ux.admin_ux_common import (
    AdminAtlasService,
    account_notice,
    experiment_summary,
    filter_experiments,
    format_beamtime,
    format_remaining,
    linux_account_for,
    select_next_pgroup,
    switch_plan,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.admin_ux.admin_view_qml import AdminViewQML
from bec_widgets.widgets.services.bec_atlas_admin_view.admin_ux.admin_view_qwidget import (
    AdminViewQWidget,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_admin_view import BECAtlasAdminView

AUTH = {"email": "staff@psi.ch", "groups": [], "deployment_id": "dep-x12sa"}


def _summaries():
    experiments = admin_demo.demo_experiments()
    next_pgroup = select_next_pgroup([e for e in experiments if e["pgroup"] != "p22622"])
    return {
        e["pgroup"]: experiment_summary(e, active_pgroup="p22622", next_pgroup=next_pgroup)
        for e in experiments
    }


########################
## Pure helpers
########################


def test_linux_account_comes_from_eaccount_or_pgroup():
    assert linux_account_for({"eaccount": "e11111", "pgroup": "p22222"}) == "e11111"
    assert linux_account_for({"eaccount": "", "pgroup": "p22222"}) == "e22222"
    assert linux_account_for({"eaccount": "", "pgroup": "staff"}) == ""
    assert linux_account_for(None) == ""


def test_summaries_mark_active_next_past_and_unscheduled():
    rows = _summaries()
    assert rows["p22622"]["status"] == "active"
    assert rows["p22623"]["status"] == "next"
    assert rows["p22631"]["status"] == "upcoming"
    assert rows["p22604"]["status"] == "past"
    assert rows["p22640"]["status"] == "unscheduled"
    assert rows["p22623"]["linuxAccount"] == "e22623"
    assert rows["p22623"]["pi"] == "Marco Rossi"


def test_filter_hides_past_by_default_and_matches_all_words():
    rows = list(_summaries().values())
    upcoming = filter_experiments(rows, "", "upcoming")
    assert "p22604" not in [r["pgroup"] for r in upcoming]
    assert upcoming[0]["pgroup"] == "p22622"  # the active experiment comes first
    assert upcoming[-1]["pgroup"] == "p22640"  # unscheduled last
    assert "p22604" in [r["pgroup"] for r in filter_experiments(rows, "", "all")]
    assert [r["pgroup"] for r in filter_experiments(rows, "rossi battery", "all")] == ["p22623"]
    assert [r["pgroup"] for r in filter_experiments(rows, "e22631", "all")] == ["p22631"]


def test_select_next_prefers_running_then_soonest():
    now = datetime(2026, 1, 10, 12)
    experiments = [
        {
            "pgroup": "pa",
            "schedule": [{"start": "20/01/2026 08:00:00", "end": "21/01/2026 08:00:00"}],
        },
        {
            "pgroup": "pb",
            "schedule": [{"start": "15/01/2026 08:00:00", "end": "16/01/2026 08:00:00"}],
        },
        {
            "pgroup": "pc",
            "schedule": [{"start": "01/01/2026 08:00:00", "end": "02/01/2026 08:00:00"}],
        },
    ]
    assert select_next_pgroup(experiments, now) == "pb"
    experiments.append(
        {
            "pgroup": "pd",
            "schedule": [{"start": "09/01/2026 08:00:00", "end": "11/01/2026 08:00:00"}],
        }
    )
    assert select_next_pgroup(experiments, now) == "pd"
    assert select_next_pgroup([], now) == ""


def test_account_notice_tones():
    active = _summaries()["p22622"]
    assert account_notice("e22622", active)["tone"] == "ok"
    assert account_notice("wyzula_j", active)["tone"] == "info"
    warning = account_notice("e22604", active)
    assert warning["tone"] == "warning"
    assert "e22622" in warning["text"]
    assert account_notice("anyone", {}) == {}


def test_switch_plan_names_the_new_linux_account_and_the_queue():
    rows = _summaries()
    plan = switch_plan(rows["p22622"], rows["p22623"], "wyzula_j", queue_busy=False)
    login = next(c for c in plan["changes"] if c["label"] == "Linux login")
    assert (login["before"], login["after"], login["key"]) == ("e22622", "e22623", True)
    assert plan["linuxAccount"] == "e22623"
    assert "e22623" in plan["ackText"]
    assert any("e22623" in step["title"] for step in plan["loginSteps"])
    assert any("wyzula_j" in step["text"] for step in plan["loginSteps"])
    assert plan["consequences"][-1]["tone"] == "ok"
    busy = switch_plan(rows["p22622"], rows["p22623"], "wyzula_j", queue_busy=True)
    assert busy["consequences"][-1]["title"] == "A scan is running or queued"


def test_small_formatters():
    assert format_remaining(872) == "14:32"
    assert format_remaining(3723) == "1:02:03"
    assert format_remaining(-5) == "0:00"
    assert format_beamtime(None, None) == "No beamtime scheduled"
    start, end = datetime(2026, 10, 12, 8), datetime(2026, 10, 15, 8)
    assert format_beamtime(start, end) == "12 Oct 2026, 08:00 – 15 Oct, 08:00"


########################
## Atlas service
########################


class _Reply:
    def __init__(self, url: str, status: int):
        self._url = url
        self._status = status
        self.deleteLater = mock.MagicMock()

    def attribute(self, attr):
        assert attr == QNetworkRequest.Attribute.HttpStatusCodeAttribute
        return self._status

    def url(self):
        return QUrl(self._url)


@pytest.mark.parametrize(
    "endpoint, status, kind, text",
    [
        ("/user/login", 401, "login", "Wrong username or password."),
        ("/user/login", 0, "login", "not reachable"),
        ("/deployments/experiment", 500, "switch", "was not changed"),
        ("/realms/experiments", 404, "experiments", "Could not load"),
    ],
)
def test_service_reports_failures_inline(qtbot, endpoint, status, kind, text):
    service = AdminAtlasService(base_url="http://atlas")
    qtbot.addWidget(service)
    received = []
    service.request_failed.connect(lambda k, m: received.append((k, m)))
    reply = _Reply(f"http://atlas{endpoint}", status)
    service._handle_response(reply)
    assert received and received[0][0] == kind and text in received[0][1]
    reply.deleteLater.assert_called_once()
    service.cleanup()
    service.cleanup()  # a second cleanup (close event) is harmless


########################
## Both views
########################


@pytest.fixture(params=[AdminViewQWidget, AdminViewQML], ids=["qwidget", "qml"])
def admin(request, qtbot, mocked_client):
    widget = create_widget(qtbot, request.param, client=mocked_client, system_user="wyzula_j")
    service = widget.atlas_http_service
    for name in ("login", "logout", "get_experiments_for_realm", "set_experiment"):
        setattr(service, name, mock.MagicMock())
    widget._on_deployment_info(admin_demo.demo_deployment().model_dump(), {})
    yield widget


def _sign_in(widget):
    widget._on_authenticated({**AUTH, "exp": time.time() + 900})
    widget.atlas_http_service.get_experiments_for_realm.assert_called_with("X12SA")
    widget._on_http_response(
        {
            "request_url": f"{widget._atlas_url}/realms/experiments?realm_id=X12SA",
            "headers": {},
            "status": 200,
            "data": admin_demo.demo_experiments(),
        }
    )


def test_signed_out_shows_active_experiment_and_account_notice(admin):
    state = admin.view_state()
    assert not state["signedIn"]
    assert state["active"]["pgroup"] == "p22622"
    assert state["active"]["linuxAccount"] == "e22622"
    assert state["notice"]["tone"] == "info"
    admin.login("", "")
    assert admin.view_state()["signInError"]
    admin.atlas_http_service.login.assert_not_called()
    admin.login("staff", "secret")
    admin.atlas_http_service.login.assert_called_once_with(username="staff", password="secret")
    assert admin.view_state()["signingIn"]
    admin._on_request_failed("login", "Wrong username or password.")
    state = admin.view_state()
    assert not state["signingIn"] and state["signInError"] == "Wrong username or password."


def test_sign_in_for_another_deployment_is_refused(admin):
    admin._on_authenticated({**AUTH, "deployment_id": "other", "exp": time.time() + 900})
    state = admin.view_state()
    assert not state["signedIn"]
    assert "owner rights" in state["signInError"]


def test_sign_in_lists_experiments_and_preselects_the_next(admin):
    _sign_in(admin)
    state = admin.view_state()
    assert state["signedIn"] and state["remaining"]
    assert state["selected"]["pgroup"] == "p22623"
    assert state["canSwitch"]
    assert [r["pgroup"] for r in state["rows"]][0] == "p22622"
    admin.set_scope("all")
    assert "p22604" in [r["pgroup"] for r in admin.view_state()["rows"]]
    admin.set_query("tanaka")
    assert [r["pgroup"] for r in admin.view_state()["rows"]] == ["p22631"]
    admin.select_experiment("p22622")
    assert not admin.view_state()["canSwitch"]


def test_guided_switch_needs_confirmation_and_ends_with_login_steps(admin):
    _sign_in(admin)
    admin.start_switch("")
    wizard = admin.view_state()["wizard"]
    assert wizard["open"] and wizard["step"] == 0 and wizard["fromPgroup"] == "p22622"
    assert wizard["plan"]["linuxAccount"] == "e22623"
    admin.wizard_next()
    admin.confirm_switch()  # not acknowledged yet: nothing is sent
    admin.atlas_http_service.set_experiment.assert_not_called()
    assert not admin.view_state()["wizard"]["canConfirm"]
    admin.set_acknowledged(True)
    assert admin.view_state()["wizard"]["canConfirm"]
    admin.confirm_switch()
    admin.atlas_http_service.set_experiment.assert_called_once_with("p22623", "dep-x12sa")
    assert admin.view_state()["wizard"]["phase"] == "switching"
    admin.close_wizard()  # cannot leave while the request runs
    assert admin.view_state()["wizard"]["open"]
    switched = []
    admin.experiment_switched.connect(switched.append)
    admin._on_http_response(
        {
            "request_url": f"{admin._atlas_url}/deployments/experiment?experiment_id=p22623",
            "headers": {},
            "status": 200,
            "data": {},
        }
    )
    state = admin.view_state()
    assert switched == ["p22623"]
    assert state["wizard"]["phase"] == "done" and state["wizard"]["step"] == 2
    assert state["active"]["pgroup"] == "p22623"
    # the confirmed change stays visible although the active experiment moved
    login = next(c for c in state["wizard"]["plan"]["changes"] if c["label"] == "Linux login")
    assert (login["before"], login["after"]) == ("e22622", "e22623")
    admin.close_wizard()
    assert not admin.view_state()["wizard"]["open"]


def test_failed_switch_stays_in_confirm_step(admin):
    _sign_in(admin)
    admin.start_switch("p22631")
    admin.wizard_next()
    admin.set_acknowledged(True)
    admin.confirm_switch()
    admin._on_request_failed("switch", "BEC Atlas refused the switch (HTTP 500).")
    wizard = admin.view_state()["wizard"]
    assert wizard["phase"] == "error" and wizard["step"] == 1 and "refused" in wizard["error"]
    admin.confirm_switch()  # retry is possible
    assert admin.atlas_http_service.set_experiment.call_count == 2
    admin._on_request_failed("switch", "again")
    admin.wizard_back()
    assert admin.view_state()["wizard"]["step"] == 0
    admin.wizard_back()
    assert not admin.view_state()["wizard"]["open"]


def test_busy_queue_adds_a_warning(admin):
    _sign_in(admin)
    item = mock.MagicMock(status="RUNNING")
    admin._on_queue_status({"queue": {"primary": mock.MagicMock(info=[item])}}, {})
    admin.start_switch("")
    consequences = admin.view_state()["wizard"]["plan"]["consequences"]
    assert consequences[-1]["tone"] == "warning"


def test_sign_out_clears_the_session(admin):
    _sign_in(admin)
    admin.start_switch("")
    admin._on_authenticated({})
    state = admin.view_state()
    assert not state["signedIn"] and not state["rows"] and not state["wizard"]["open"]


def test_qml_backend_drives_the_same_flow(qtbot, mocked_client):
    widget = create_widget(qtbot, AdminViewQML, client=mocked_client, system_user="e22622")
    for name in ("login", "logout", "get_experiments_for_realm", "set_experiment"):
        setattr(widget.atlas_http_service, name, mock.MagicMock())
    widget._on_deployment_info(admin_demo.demo_deployment().model_dump(), {})
    assert widget.view.rootObject() is not None
    _sign_in(widget)
    backend = widget.backend
    assert backend.rows.rowCount() == len(widget.view_state()["rows"])
    assert backend.state["notice"]["tone"] == "ok"
    backend.selectExperiment("p22631")
    backend.startSwitch("")
    backend.next()
    backend.setAcknowledged(True)
    backend.confirm()
    widget.atlas_http_service.set_experiment.assert_called_once_with("p22631", "dep-x12sa")


def test_qwidget_buttons_drive_the_flow(qtbot, mocked_client):
    widget = create_widget(qtbot, AdminViewQWidget, client=mocked_client, system_user="wyzula_j")
    for name in ("login", "logout", "get_experiments_for_realm", "set_experiment"):
        setattr(widget.atlas_http_service, name, mock.MagicMock())
    widget._on_deployment_info(admin_demo.demo_deployment().model_dump(), {})
    widget._username.setText("staff")
    widget._password.setText("secret")
    widget._sign_in_button.click()
    widget.atlas_http_service.login.assert_called_once_with(username="staff", password="secret")
    assert widget._password.text() == ""
    _sign_in(widget)
    assert widget._pages.currentIndex() == 1
    widget._switch_button.click()
    assert widget._content.currentIndex() == 1
    widget._wiz_primary.click()
    assert not widget._wiz_primary.isEnabled()
    widget._ack.setChecked(True)
    assert widget._wiz_primary.isEnabled()
    widget._wiz_primary.click()
    widget.atlas_http_service.set_experiment.assert_called_once_with("p22623", "dep-x12sa")


@pytest.mark.parametrize(
    "value, cls", [("qml", AdminViewQML), ("qwidget", AdminViewQWidget), ("", BECAtlasAdminView)]
)
def test_admin_view_env_switch(qtbot, mocked_client, monkeypatch, value, cls):
    monkeypatch.setenv(admin_view_module.ADMIN_UI_ENV, value)
    widget = admin_view_module.create_admin_widget()
    qtbot.addWidget(widget)
    assert isinstance(widget, cls)
