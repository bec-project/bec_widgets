"""State and behaviour shared by the QML and QWidget versions of the reworked admin view.

The admin view lets beamline staff sign in to BEC Atlas and switch the active experiment.
Switching the experiment changes the BEC account (the p-group) that new scans are written to,
and the experiment's group works on the beamline computers under its own Linux account (the
e-account). The old view did not say any of this; this module turns it into an explicit
three-step flow (review, confirm, log in as the new account) and a notice that compares the
Linux login of this computer with the account of the active experiment.

:class:`AdminViewBase` owns the Atlas connection and all state and renders it as one plain
dictionary (:meth:`AdminViewBase.view_state`). The QML and QWidget subclasses only draw that
dictionary and call the public slots, so both show exactly the same UX.
"""

from __future__ import annotations

import getpass
import re
import time
from datetime import datetime

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import DeploymentInfoMessage, ExperimentInfoMessage
from qtpy.QtCore import QTimer, Signal
from qtpy.QtNetwork import QNetworkReply, QNetworkRequest
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_http_service import (
    AtlasEndpoints,
    AuthenticatedUserInfo,
    BECAtlasHTTPService,
    HTTPResponse,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.utils import (
    format_name,
    format_schedule,
)

logger = bec_logger.logger

DEFAULT_ATLAS_URL = "https://bec-atlas-prod.psi.ch/api/v1"

SECTIONS = [
    {"id": "experiment", "label": "Experiment", "icon": "science", "enabled": True, "badge": ""},
    {"id": "messaging", "label": "Messaging", "icon": "chat", "enabled": False, "badge": "Soon"},
]
"""Sections of the signed-in admin view. Later staff tools are added here."""

WIZARD_STEPS = ["Review", "Confirm", "Log in"]

HOW_IT_WORKS = [
    "Pick the experiment from the list. Nothing changes yet.",
    "Review what changes and confirm. New data then goes to the new p-group.",
    "Everyone on this computer logs out and logs in as the experiment's Linux account.",
]

_EACCOUNT = re.compile(r"^e\d{5}$")

STATUS_LABELS = {
    "active": "Active",
    "now": "Beamtime now",
    "next": "Next",
    "upcoming": "Upcoming",
    "past": "Past",
    "unscheduled": "No beamtime",
}


########################
## Pure helpers
########################


def linux_account_for(info: ExperimentInfoMessage | dict | None) -> str:
    """Return the Linux account the experiment's group logs in with, e.g. ``e22622``.

    Args:
        info(ExperimentInfoMessage | dict | None): Experiment information.

    Returns:
        str: The e-account, derived from the p-group if Atlas did not send one, else ``""``.
    """
    if info is None:
        return ""
    if isinstance(info, dict):
        eaccount = info.get("eaccount") or ""
        pgroup = info.get("pgroup") or ""
    else:
        eaccount = info.eaccount or ""
        pgroup = info.pgroup or ""
    if eaccount:
        return eaccount
    if re.match(r"^p\d{5}$", pgroup):
        return f"e{pgroup[1:]}"
    return ""


def format_beamtime(start: datetime | None, end: datetime | None) -> str:
    """Format a beamtime as ``12 Oct 2026, 08:00 – 14 Oct, 18:00``."""
    if start is None:
        return "No beamtime scheduled"
    text = f"{start:%d %b %Y, %H:%M}"
    if end is None:
        return text
    if end.date() == start.date():
        return f"{text} – {end:%H:%M}"
    end_format = "%d %b, %H:%M" if end.year == start.year else "%d %b %Y, %H:%M"
    return f"{text} – {end.strftime(end_format)}"


def select_next_pgroup(experiments: list[dict], now: datetime | None = None) -> str:
    """Return the p-group of the experiment whose beamtime starts next (or runs now)."""
    now = now or datetime.now()
    best = None
    for info in experiments:
        start, end = format_schedule(info.get("schedule"), as_datetime=True)
        if start is None:
            continue
        running = end is not None and start <= now <= end
        if start < now and not running:
            continue
        key = (0 if running else 1, abs((start - now).total_seconds()))
        if best is None or key < best[0]:
            best = (key, info.get("pgroup", ""))
    return best[1] if best else ""


def experiment_summary(
    info: ExperimentInfoMessage | dict | None,
    *,
    active_pgroup: str = "",
    next_pgroup: str = "",
    now: datetime | None = None,
) -> dict:
    """Flatten experiment information into the fields both views display.

    Args:
        info(ExperimentInfoMessage | dict | None): Experiment information from Atlas.
        active_pgroup(str): P-group of the active experiment, to mark it.
        next_pgroup(str): P-group of the next scheduled experiment, to mark it.
        now(datetime | None): Reference time, for tests.

    Returns:
        dict: Display fields; empty if ``info`` is None.
    """
    if info is None:
        return {}
    if isinstance(info, ExperimentInfoMessage):
        info = info.model_dump()
    now = now or datetime.now()
    pgroup = info.get("pgroup") or ""
    start, end = format_schedule(info.get("schedule"), as_datetime=True)
    if pgroup and pgroup == active_pgroup:
        status = "active"
    elif start is None:
        status = "unscheduled"
    elif end is not None and start <= now <= end:
        status = "now"
    elif pgroup and pgroup == next_pgroup:
        status = "next"
    elif start > now:
        status = "upcoming"
    else:
        status = "past"
    try:
        name = format_name(info)
    except Exception:  # pylint: disable=broad-except
        name = " ".join(p for p in [info.get("firstname"), info.get("lastname")] if p)
    pi = " ".join(p for p in [info.get("pi_firstname"), info.get("pi_lastname")] if p)
    return {
        "pgroup": pgroup,
        "title": info.get("title") or "Untitled experiment",
        "pi": pi or name or "—",
        "contact": name or "—",
        "email": info.get("pi_email") or info.get("email") or "",
        "proposal": info.get("proposal") or "",
        "hasProposal": bool(info.get("proposal")),
        "linuxAccount": linux_account_for(info),
        "dataAccount": pgroup,
        "beamtime": format_beamtime(start, end),
        "startSort": start.timestamp() if start else float("inf"),
        "status": status,
        "statusLabel": STATUS_LABELS[status],
        "isActive": status == "active",
        "isNext": pgroup != "" and pgroup == next_pgroup,
        "abstract": (info.get("abstract") or "").strip(),
    }


def filter_experiments(rows: list[dict], query: str = "", scope: str = "upcoming") -> list[dict]:
    """Filter and order experiment summaries for the switch list.

    Args:
        rows(list[dict]): Summaries from :func:`experiment_summary`.
        query(str): Case-insensitive text matched against p-group, title, people and accounts.
        scope(str): ``"upcoming"`` hides past beamtimes, ``"all"`` shows everything.

    Returns:
        list[dict]: The active experiment first, then by beamtime start; unscheduled last.
    """
    words = query.lower().split()
    result = []
    for row in rows:
        if scope == "upcoming" and row["status"] == "past":
            continue
        haystack = " ".join(
            str(row.get(key, ""))
            for key in ("pgroup", "title", "pi", "contact", "linuxAccount", "proposal")
        ).lower()
        if all(word in haystack for word in words):
            result.append(row)
    return sorted(result, key=lambda r: (not r["isActive"], r["startSort"], r["pgroup"]))


def account_notice(system_user: str, active: dict) -> dict:
    """Compare the Linux login of this computer with the active experiment's account.

    Args:
        system_user(str): Linux user running this BEC app.
        active(dict): Summary of the active experiment.

    Returns:
        dict: ``tone`` (``ok``, ``info`` or ``warning``), ``title`` and ``text``; empty if there
        is no active experiment.
    """
    account = active.get("linuxAccount", "") if active else ""
    if not account:
        return {}
    if system_user == account:
        return {
            "tone": "ok",
            "title": f"Logged in as {account}",
            "text": f"This computer runs under the account of the active experiment {active['pgroup']}.",
        }
    if _EACCOUNT.match(system_user or ""):
        return {
            "tone": "warning",
            "title": f"Still logged in as {system_user}",
            "text": (
                f"{system_user} belongs to a different experiment. Close BEC, log out and log in "
                f"as {account} before the group of {active['pgroup']} continues."
            ),
        }
    return {
        "tone": "info",
        "title": f"Logged in as {system_user or 'unknown'} (staff)",
        "text": f"The group of {active['pgroup']} works on this computer as {account}.",
    }


def switch_plan(current: dict, target: dict, system_user: str, queue_busy: bool = False) -> dict:
    """Describe what switching from ``current`` to ``target`` changes, for the confirmation flow.

    Args:
        current(dict): Summary of the active experiment (may be empty).
        target(dict): Summary of the experiment to switch to.
        system_user(str): Linux user running this BEC app.
        queue_busy(bool): Whether a scan is running or queued.

    Returns:
        dict: ``changes`` (before/after rows), ``consequences`` (what happens),
        ``loginSteps`` (what to do afterwards), ``ackText`` and ``linuxAccount``.
    """
    old_pgroup = current.get("pgroup") or "none"
    new_pgroup = target["pgroup"]
    new_account = target.get("linuxAccount") or "the experiment account"
    old_account = current.get("linuxAccount") or "—"
    changes = [
        {"label": "Experiment", "before": old_pgroup, "after": new_pgroup, "key": False},
        {
            "label": "Title",
            "before": current.get("title", "—"),
            "after": target["title"],
            "key": False,
        },
        {"label": "PI", "before": current.get("pi", "—"), "after": target["pi"], "key": False},
        {"label": "Linux login", "before": old_account, "after": new_account, "key": True},
        {"label": "Data saved to", "before": old_pgroup, "after": new_pgroup, "key": True},
    ]
    consequences = [
        {
            "icon": "save",
            "tone": "info",
            "title": f"New scans are saved for {new_pgroup}",
            "text": "From the next scan on, file paths and scan numbers follow the new experiment.",
        },
        {
            "icon": "folder_shared",
            "tone": "info",
            "title": f"Data already recorded stays with {old_pgroup}",
            "text": "Nothing is moved or deleted. The previous group keeps access to its data.",
        },
        {
            "icon": "terminal",
            "tone": "warning",
            "title": "Open BEC sessions keep their Linux login",
            "text": (
                f"This app and any bec terminal keep running as {system_user or 'the current user'}"
                f". Close them so nobody keeps working under the previous login."
            ),
        },
    ]
    if queue_busy:
        consequences.append(
            {
                "icon": "pending_actions",
                "tone": "warning",
                "title": "A scan is running or queued",
                "text": (
                    f"The running scan finishes in {old_pgroup}'s folder; scans that start after "
                    f"the switch go to {new_pgroup}. Wait for the queue to be idle if unsure."
                ),
            }
        )
    else:
        consequences.append(
            {
                "icon": "check_circle",
                "tone": "ok",
                "title": "The scan queue is idle",
                "text": "No scan is affected by switching now.",
            }
        )
    login_steps = [
        {"title": "Close BEC", "text": "Quit this app and every bec terminal on this computer."},
        {
            "title": "Log out",
            "text": f"Log out of the desktop session of {system_user or 'the current user'}.",
        },
        {
            "title": f"Log in as {new_account}",
            "text": "Use the password of the experiment account, as given to the user group.",
        },
        {
            "title": "Start BEC again",
            "text": f"The bec prompt then starts with {new_pgroup}, confirming the new experiment.",
        },
    ]
    return {
        "changes": changes,
        "consequences": consequences,
        "loginSteps": login_steps,
        "ackText": f"After switching, everyone on this computer logs in as {new_account}.",
        "linuxAccount": new_account,
    }


def format_remaining(seconds: float) -> str:
    """Format a remaining session time as ``14:32`` or ``1:02:03``."""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


########################
## Atlas service
########################


class AdminAtlasService(BECAtlasHTTPService):
    """Atlas HTTP service that reports failed sign-ins and switches inline instead of in popups."""

    request_failed = Signal(str, str)  # endpoint kind ("login", "switch", "experiments"), message

    _KINDS = {
        AtlasEndpoints.LOGIN.value: "login",
        AtlasEndpoints.SET_EXPERIMENT.value: "switch",
        AtlasEndpoints.REALMS_EXPERIMENTS.value: "experiments",
    }

    @SafeSlot(QNetworkReply, popup_error=True)
    def _handle_response(self, reply: QNetworkReply):
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        url = reply.url().toString()
        kind = next((k for endpoint, k in self._KINDS.items() if endpoint in url), None)
        if kind is None or status == 200:
            super()._handle_response(reply)
            return
        reply.deleteLater()
        self.request_failed.emit(kind, self._failure_text(kind, status))

    def _failure_text(self, kind: str, status: int | None) -> str:
        if not status:
            return f"BEC Atlas is not reachable at {self._base_url}."
        if kind == "login" and status in (401, 403):
            return "Wrong username or password."
        if kind == "switch":
            return f"BEC Atlas refused the switch (HTTP {status}). The experiment was not changed."
        if kind == "experiments":
            return f"Could not load the experiments of this beamline (HTTP {status})."
        return f"Request failed (HTTP {status})."

    def _show_warning(self, text: str):
        self.request_failed.emit("login", text)

    def cleanup(self):
        """Close the Atlas session once; the widget and its close event may both ask."""
        if getattr(self, "_cleaned_up", False):
            return
        self._cleaned_up = True
        super().cleanup()


########################
## Shared view base
########################


class AdminViewBase(BECWidget, QWidget):
    """Admin view logic shared by the QML and QWidget versions.

    Subclasses implement :meth:`_render`, which receives :meth:`view_state` after every change.
    """

    RPC = False

    authenticated = Signal(bool)
    experiment_switched = Signal(str)

    def __init__(
        self,
        parent=None,
        atlas_url: str = DEFAULT_ATLAS_URL,
        client=None,
        system_user: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, **kwargs)
        self._atlas_url = atlas_url
        self._system_user = system_user if system_user is not None else getpass.getuser()
        self._deployment: DeploymentInfoMessage | None = None
        self._active_info: ExperimentInfoMessage | None = None
        self._experiments: list[dict] = []
        self._loading_experiments = False
        self._auth: AuthenticatedUserInfo | None = None
        self._signing_in = False
        self._sign_in_error = ""
        self._section = "experiment"
        self._query = ""
        self._scope = "upcoming"
        self._selected = ""
        self._queue_busy = False
        self._wizard = self._closed_wizard()

        self.atlas_http_service = AdminAtlasService(
            parent=self, base_url=atlas_url, headers={"accept": "application/json"}
        )
        self.atlas_http_service.hide()
        self.atlas_http_service.http_response.connect(self._on_http_response)
        self.atlas_http_service.authenticated.connect(self._on_authenticated)
        self.atlas_http_service.request_failed.connect(self._on_request_failed)

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

        self.bec_dispatcher.connect_slot(
            self._on_deployment_info, MessageEndpoints.deployment_info(), from_start=True
        )
        self.bec_dispatcher.connect_slot(
            self._on_queue_status, MessageEndpoints.scan_queue_status()
        )

    @staticmethod
    def _closed_wizard() -> dict:
        return {
            "open": False,
            "step": 0,
            "target": "",
            "ack": False,
            "phase": "review",
            "error": "",
            "frozen": None,
            "fromPgroup": "",
        }

    ########################
    ## Rendering
    ########################

    def _render(self, state: dict) -> None:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def refresh(self) -> None:
        """Re-render the view from the current state."""
        self._render(self.view_state())

    def _summaries(self) -> tuple[dict, list[dict]]:
        active_pgroup = self._active_info.pgroup if self._active_info else ""
        next_pgroup = select_next_pgroup(
            [e for e in self._experiments if e.get("pgroup") != active_pgroup]
        )
        active = experiment_summary(
            self._active_info, active_pgroup=active_pgroup, next_pgroup=next_pgroup
        )
        rows = [
            experiment_summary(info, active_pgroup=active_pgroup, next_pgroup=next_pgroup)
            for info in self._experiments
        ]
        return active, rows

    def view_state(self) -> dict:
        """Return everything the views display as one plain dictionary."""
        active, all_rows = self._summaries()
        rows = filter_experiments(all_rows, self._query, self._scope)
        by_pgroup = {row["pgroup"]: row for row in all_rows}
        selected = by_pgroup.get(self._selected, {})
        wizard = dict(self._wizard)
        target = by_pgroup.get(wizard["target"], {})
        wizard["targetInfo"] = target
        frozen = wizard.pop("frozen")
        if frozen is not None:
            # Keep showing the change as confirmed, even after the active experiment moved.
            wizard["plan"], wizard["targetInfo"] = frozen
        else:
            wizard["plan"] = (
                switch_plan(active, target, self._system_user, self._queue_busy) if target else {}
            )
        wizard["steps"] = WIZARD_STEPS
        wizard["canConfirm"] = (
            bool(wizard["targetInfo"]) and wizard["ack"] and wizard["phase"] != "switching"
        )
        deployment = self._deployment
        remaining = (self._auth.exp - time.time()) if self._auth else 0
        return {
            "deploymentName": deployment.name if deployment else "No deployment",
            "realm": (self._active_info.realm_id if self._active_info else "") or "",
            "atlasUrl": self._atlas_url,
            "signedIn": self._auth is not None,
            "email": self._auth.email if self._auth else "",
            "remaining": format_remaining(remaining) if self._auth else "",
            "signingIn": self._signing_in,
            "signInError": self._sign_in_error,
            "systemUser": self._system_user,
            "section": self._section,
            "sections": SECTIONS,
            "active": active,
            "hasActive": bool(active),
            "notice": account_notice(self._system_user, active),
            "query": self._query,
            "scope": self._scope,
            "rows": rows,
            "totalCount": len(all_rows),
            "loadingExperiments": self._loading_experiments,
            "selected": selected,
            "canSwitch": bool(selected) and not selected.get("isActive", False),
            "queueBusy": self._queue_busy,
            "wizard": wizard,
        }

    ########################
    ## User actions
    ########################

    @SafeSlot(str, str)
    def login(self, username: str, password: str) -> None:
        """Sign in to BEC Atlas with a PSI account."""
        if not username or not password:
            self._sign_in_error = "Enter your PSI username and password."
            self.refresh()
            return
        if self._auth is not None:
            self.atlas_http_service.logout()
        self._signing_in = True
        self._sign_in_error = ""
        self.refresh()
        self.atlas_http_service.login(username=username, password=password)

    @SafeSlot()
    def logout(self) -> None:
        """Sign out of BEC Atlas."""
        self.atlas_http_service.logout()

    @SafeSlot(str, str, popup_error=True)
    def set_experiment(self, experiment_id: str, deployment_id: str) -> None:
        """Ask BEC Atlas to make ``experiment_id`` the active experiment of the deployment."""
        self.atlas_http_service.set_experiment(experiment_id, deployment_id)

    @SafeSlot(str)
    def open_section(self, section: str) -> None:
        """Show a section of the signed-in view."""
        if any(s["id"] == section and s["enabled"] for s in SECTIONS):
            self._section = section
            self.refresh()

    @SafeSlot(str)
    def set_query(self, query: str) -> None:
        """Filter the experiment list."""
        self._query = query
        self.refresh()

    @SafeSlot(str)
    def set_scope(self, scope: str) -> None:
        """Show only upcoming beamtimes (``upcoming``) or all experiments (``all``)."""
        self._scope = "all" if scope == "all" else "upcoming"
        self.refresh()

    @SafeSlot(str)
    def select_experiment(self, pgroup: str) -> None:
        """Select an experiment in the list to see its details."""
        self._selected = pgroup
        self.refresh()

    @SafeSlot(str)
    def start_switch(self, pgroup: str = "") -> None:
        """Open the switch flow for ``pgroup`` (default: the selected experiment)."""
        pgroup = pgroup or self._selected
        if not pgroup or self._auth is None:
            return
        self._wizard = self._closed_wizard()
        active = self._active_info.pgroup if self._active_info else ""
        self._wizard.update({"open": True, "target": pgroup, "fromPgroup": active or "none"})
        self.refresh()

    @SafeSlot()
    def wizard_next(self) -> None:
        """Go from reviewing the change to confirming it."""
        if self._wizard["open"] and self._wizard["step"] == 0:
            self._wizard["step"] = 1
            self.refresh()

    @SafeSlot()
    def wizard_back(self) -> None:
        """Go back one step, or close the flow from the first step."""
        if self._wizard["phase"] in ("switching", "done"):
            return
        if self._wizard["step"] == 0:
            self.close_wizard()
            return
        self._wizard["step"] -= 1
        self._wizard["error"] = ""
        self.refresh()

    @SafeSlot(bool)
    def set_acknowledged(self, acknowledged: bool) -> None:
        """Tick or untick the confirmation that everyone logs in as the new account."""
        self._wizard["ack"] = bool(acknowledged)
        self.refresh()

    @SafeSlot()
    def confirm_switch(self) -> None:
        """Send the switch to BEC Atlas once the change was confirmed."""
        wizard = self._wizard
        if not (wizard["open"] and wizard["ack"] and wizard["phase"] in ("review", "error")):
            return
        if self._deployment is None:
            wizard.update({"phase": "error", "error": "No deployment information from BEC."})
            self.refresh()
            return
        state = self.view_state()["wizard"]
        wizard.update(
            {"phase": "switching", "error": "", "frozen": (state["plan"], state["targetInfo"])}
        )
        self.refresh()
        self.set_experiment(wizard["target"], self._deployment.deployment_id)

    @SafeSlot()
    def close_wizard(self) -> None:
        """Leave the switch flow."""
        if self._wizard["phase"] == "switching":
            return
        self._wizard = self._closed_wizard()
        self.refresh()

    ########################
    ## Incoming data
    ########################

    @SafeSlot(dict, dict)
    def _on_deployment_info(self, msg: dict, _meta: dict) -> None:
        deployment = DeploymentInfoMessage.model_validate(msg)
        self._deployment = deployment
        session = deployment.active_session
        if session is not None and session.experiment is not None:
            self._active_info = session.experiment
        self.atlas_http_service._set_current_deployment_info(  # pylint: disable=protected-access
            deployment
        )
        self.refresh()

    @SafeSlot(dict, dict)
    def _on_queue_status(self, content: dict, _meta: dict) -> None:
        primary = (content.get("queue") or {}).get("primary")
        info = getattr(primary, "info", None) or []
        busy = any(
            getattr(item, "status", "") not in ("STOPPED", "COMPLETED", "IDLE") for item in info
        )
        if busy != self._queue_busy:
            self._queue_busy = busy
            self.refresh()

    def _on_http_response(self, response: dict) -> None:
        response = HTTPResponse(**response)
        if AtlasEndpoints.REALMS_EXPERIMENTS in response.request_url:
            self._experiments = response.data if isinstance(response.data, list) else []
            self._loading_experiments = False
            if not self._selected:
                _active, rows = self._summaries()
                upcoming = filter_experiments(rows, "", "upcoming")
                choice = next((r for r in rows if r["isNext"]), None) or next(
                    (r for r in upcoming if not r["isActive"]), None
                )
                self._selected = choice["pgroup"] if choice else ""
            self.refresh()
        elif AtlasEndpoints.SET_EXPERIMENT in response.request_url:
            if self._wizard["open"]:
                self._wizard.update({"phase": "done", "step": 2, "error": ""})
            target = self._wizard.get("target", "")
            for info in self._experiments:
                if info.get("pgroup") == target:
                    # Show the new experiment right away; deployment info confirms it shortly.
                    self._active_info = ExperimentInfoMessage.model_validate(info)
                    break
            self.refresh()
            self.experiment_switched.emit(target)

    @SafeSlot(str, str)
    def _on_request_failed(self, kind: str, message: str) -> None:
        if kind == "login":
            self._signing_in = False
            self._sign_in_error = message
        elif kind == "switch" and self._wizard["open"]:
            self._wizard.update({"phase": "error", "error": message})
        elif kind == "experiments":
            self._loading_experiments = False
            self._sign_in_error = message
        self.refresh()

    @SafeSlot(dict)
    def _on_authenticated(self, auth_info: dict) -> None:
        self._signing_in = False
        info = AuthenticatedUserInfo.model_validate(auth_info) if auth_info else None
        if info is not None and (
            self._deployment is None or info.deployment_id != self._deployment.deployment_id
        ):
            self._sign_in_error = "This account has no owner rights on this beamline deployment."
            info = None
        self._auth = info
        if info is not None:
            self._sign_in_error = ""
            self._tick.start()
            self._fetch_experiments()
        else:
            self._tick.stop()
            self._experiments = []
            self._selected = ""
            self._wizard = self._closed_wizard()
        self.refresh()
        self.authenticated.emit(info is not None)

    def _fetch_experiments(self) -> None:
        realm = self._active_info.realm_id if self._active_info else None
        if not realm:
            self._sign_in_error = "The active experiment has no realm; cannot list experiments."
            return
        self._loading_experiments = True
        self.atlas_http_service.get_experiments_for_realm(realm)

    def _on_tick(self) -> None:
        if self._auth is None:
            self._tick.stop()
            return
        self._render_session_time(format_remaining(self._auth.exp - time.time()))

    def _render_session_time(self, remaining: str) -> None:
        """Show the remaining session time; views may override this with a cheaper update."""
        self.refresh()

    ########################
    ## Cleanup
    ########################

    def cleanup(self):
        """Stop the timer and close the Atlas session."""
        self._tick.stop()
        self.bec_dispatcher.disconnect_slot(
            self._on_deployment_info, MessageEndpoints.deployment_info()
        )
        self.bec_dispatcher.disconnect_slot(
            self._on_queue_status, MessageEndpoints.scan_queue_status()
        )
        self.atlas_http_service.cleanup()
        super().cleanup()
