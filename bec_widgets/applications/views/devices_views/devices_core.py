"""Toolkit-independent state of the two device views.

:class:`ConfigEditor` drives the *Config* view: it keeps the running session config and an edited
copy, computes the field-level difference between them, tests devices and applies only the
differences, device by device. :class:`DeviceBrowser` drives the read-only *Devices* view: device
search by kind and live values. The QML and QWidget views only render what these controllers
expose and call their methods, so both look and behave the same.
"""

from __future__ import annotations

import copy
import importlib
import inspect
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from bec_lib import config_helper
from bec_lib.bec_yaml_loader import yaml_load
from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

logger = bec_logger.logger

READOUT_LABELS = {
    "monitored": "Monitored · every point",
    "baseline": "Baseline · once per scan",
    "async": "Async · detector-paced",
    "continuous": "Continuous",
    "on_request": "On request",
}
READOUT_HINT = (
    "When BEC reads it: at every scan point, once per scan, or when the detector says so."
)
ON_FAILURE_LABELS = {"retry": "Retry once", "buffer": "Use last value", "raise": "Fail immediately"}

# status key -> (label, tone, material icon). Tones: ok, neutral, stale, busy, warn, err.
STATUS = {
    "session": ("Valid · in session", "neutral", "check"),
    "valid": ("Valid", "ok", "check"),
    "unchecked": ("Not checked", "stale", "help"),
    "testing": ("Testing…", "busy", "sync"),
    "unreach": ("Unreachable", "err", "power_off"),
    "invalid": ("Invalid config", "err", "error"),
}
PROBLEM_STATES = ("unreach", "invalid")
CHANGE_LABELS = {"A": "Added", "M": "Modified", "D": "Removed"}
CHANGE_TONES = {"A": "ok", "M": "warn", "D": "err"}

# Keys the server can update in place; changing anything else needs remove + add.
UPDATABLE = set(config_helper._ConfigConstants.UPDATABLE)  # pylint: disable=protected-access
EDITABLE_FIELDS = ("readoutPriority", "enabled", "onFailure", "description", "readOnly")
DEFAULTS = {
    "enabled": True,
    "readOnly": False,
    "softwareTrigger": False,
    "onFailure": "retry",
    "description": "",
    "deviceTags": [],
    "deviceConfig": {},
}
DEVICE_CLASSES = ["ophyd.EpicsMotor", "ophyd.EpicsSignal", "ophyd.EpicsSignalRO"] + [
    f"ophyd_devices.{name}" for name in ("SimPositioner", "SimMonitor", "SimCamera")
]
NEW_NAME_RULE = "Lower case, letters, digits and _ (starting with a letter)"


# --------------------------------------------------------------------------------------- helpers
def normalize_config(name: str, cfg: dict) -> dict:
    """Return a deep copy of ``cfg`` with defaults filled in and tags as a sorted list.

    Unknown keys such as ``needs`` or ``connectionTimeout`` are kept as they are.
    """
    out = copy.deepcopy(dict(cfg))
    out["name"] = name
    for key, value in DEFAULTS.items():
        if out.get(key) is None:
            out[key] = copy.deepcopy(value)
    out["deviceTags"] = sorted(str(t) for t in (out.get("deviceTags") or []))
    out["deviceConfig"] = dict(out.get("deviceConfig") or {})
    return out


def configs_by_name(configs: list[dict] | dict) -> dict[str, dict]:
    """Turn a config list or a ``{name: cfg}`` mapping into normalised ``{name: cfg}``."""
    if isinstance(configs, dict):
        items = list(configs.items())
    else:
        items = [(cfg.get("name"), cfg) for cfg in configs]
    return {name: normalize_config(name, cfg) for name, cfg in items if name}


def short_class(device_class: str) -> str:
    """``ophyd_devices.sim.SimPositioner`` -> ``SimPositioner``."""
    return str(device_class or "").rsplit(".", 1)[-1]


def value_text(value: Any) -> str:
    """Compact, stable text of a config value for tables and diffs."""
    if isinstance(value, str):
        return value
    return (
        yaml.safe_dump(value, default_flow_style=True, sort_keys=False)
        .strip()
        .removesuffix("\n...")
    )


def parse_value(text: str) -> Any:
    """Parse a value typed into a config field the way YAML would (``1,5`` reads as 1.5)."""
    text = text.strip()
    if not text:
        return None
    candidate = text.replace(",", ".") if _looks_like_decimal_comma(text) else text
    try:
        return yaml.safe_load(candidate)
    except yaml.YAMLError:
        return text


def _looks_like_decimal_comma(text: str) -> bool:
    head, sep, tail = text.lstrip("-").partition(",")
    return bool(sep) and head.isdigit() and tail.isdigit()


def diff_device(old: dict, new: dict) -> list[tuple[str, str, str]]:
    """Field-level difference ``[(field, old_text, new_text)]`` of two normalised configs.

    ``deviceConfig`` is compared key by key (``deviceConfig.limits``); every other key, including
    keys the editor does not know, is compared as a whole.
    """
    fields: list[tuple[str, str, str]] = []
    keys = [k for k in dict.fromkeys([*old, *new]) if k != "name"]
    for key in keys:
        if key == "deviceConfig":
            a, b = old.get(key) or {}, new.get(key) or {}
            for sub in dict.fromkeys([*a, *b]):
                if a.get(sub, _MISSING) != b.get(sub, _MISSING):
                    fields.append(
                        (f"deviceConfig.{sub}", _text_or_dash(a, sub), _text_or_dash(b, sub))
                    )
        elif old.get(key, _MISSING) != new.get(key, _MISSING):
            fields.append((key, _text_or_dash(old, key), _text_or_dash(new, key)))
    return fields


_MISSING = object()


def _text_or_dash(data: dict, key: str) -> str:
    return value_text(data[key]) if key in data else "—"


@dataclass
class Change:
    """One device that differs between the running session and the edited copy."""

    kind: str  # "A" added, "M" modified, "D" removed
    name: str
    fields: list[tuple[str, str, str]] = field(default_factory=list)


def diff_configs(session: dict[str, dict], work: dict[str, dict]) -> list[Change]:
    """All differences between ``session`` and ``work``, in the order of the edited copy."""
    changes: list[Change] = []
    for name, cfg in work.items():
        old = session.get(name)
        if old is None:
            changes.append(Change("A", name))
            continue
        fields = diff_device(old, cfg)
        if fields:
            changes.append(Change("M", name, fields))
    changes.extend(Change("D", name) for name in session if name not in work)
    return changes


def plan_requests(change: Change, session: dict[str, dict], work: dict[str, dict]) -> list:
    """Config requests ``[(action, {name: cfg})]`` that apply one change to the session.

    Modifications of updatable keys are sent as one ``update`` with only the changed keys; a
    changed device class, a removed ``deviceConfig`` key or any other key re-creates the device.
    """

    def payload(cfg: dict) -> dict:
        return {k: copy.deepcopy(v) for k, v in cfg.items() if k != "name"}

    name = change.name
    if change.kind == "A":
        return [("add", {name: payload(work[name])})]
    if change.kind == "D":
        return [("remove", {name: {}})]
    old, new = session[name], work[name]
    top_keys = list(dict.fromkeys(f.split(".", 1)[0] for f, _, _ in change.fields))
    removed_sub = set(old.get("deviceConfig", {})) - set(new.get("deviceConfig", {}))
    if removed_sub or any(key not in UPDATABLE for key in top_keys):
        return [("remove", {name: {}}), ("add", {name: payload(new)})]
    return [("update", {name: {key: copy.deepcopy(new.get(key)) for key in top_keys}})]


def device_yaml(cfg: dict) -> str:
    """YAML block of one device, without keys that only repeat defaults."""
    body = {
        k: v
        for k, v in cfg.items()
        if k != "name" and not (k in DEFAULTS and v == DEFAULTS[k] and k != "enabled")
    }
    return yaml.safe_dump({cfg["name"]: body}, sort_keys=False, default_flow_style=False)


def class_docstring(device_class: str) -> str:
    """First paragraphs of the device class docstring, or a short note if it cannot load."""
    module_name, _, cls_name = str(device_class).rpartition(".")
    try:
        cls = getattr(importlib.import_module(module_name), cls_name)
    except Exception:  # pylint: disable=broad-except
        return f"The class {device_class} could not be imported here, so no documentation."
    return inspect.getdoc(cls) or f"{cls_name} has no docstring."


# --------------------------------------------------------------------------------------- workers
class _WorkerSignals(QObject):
    progress = Signal(str, str, str)  # device name, state, message
    finished = Signal(int, int)  # applied, failed
    tested = Signal(str, str, str)  # device name, status key, message
    done = Signal(object)  # generic result


class ApplyWorker(QRunnable):
    """Apply a list of changes to the running session, one device at a time."""

    def __init__(self, helper, requests: list[tuple[str, list]]):
        super().__init__()
        self.helper = helper
        self.requests = requests
        self.signals = _WorkerSignals()

    def run(self):  # pragma: no cover - needs a running BEC
        applied = failed = 0
        for name, steps in self.requests:
            self.signals.progress.emit(name, "running", "")
            try:
                for action, config in steps:
                    self.helper.send_config_request(
                        action=action, config=config, wait_for_response=True
                    )
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                self.signals.progress.emit(name, "failed", str(exc).strip().splitlines()[-1])
            else:
                applied += 1
                self.signals.progress.emit(name, "done", "")
        self.signals.finished.emit(applied, failed)


class TestWorker(QRunnable):
    """Run the ophyd static device test (config + connection) for one device config."""

    def __init__(self, cfg: dict, timeout: float = 5.0):
        super().__init__()
        self.cfg = cfg
        self.timeout = timeout
        self.signals = _WorkerSignals()

    def run(self):  # pragma: no cover - needs ophyd_devices and hardware or simulation
        name = self.cfg["name"]
        try:
            from ophyd_devices.utils.static_device_test import StaticDeviceTest
        except ImportError:
            self.signals.tested.emit(name, "unchecked", "ophyd_devices is not installed here")
            return
        try:
            body = {k: v for k, v in self.cfg.items() if k != "name"}
            tester = StaticDeviceTest(config_dict={name: body})
            results = tester.run_with_list_output(
                connect=True, force_connect=False, timeout_per_device=self.timeout
            )
            result = results[0]
            if not result.config_is_valid:
                self.signals.tested.emit(name, "invalid", result.message or "")
            elif not result.success:
                self.signals.tested.emit(name, "unreach", result.message or "")
            else:
                self.signals.tested.emit(name, "valid", "")
        except Exception as exc:  # pylint: disable=broad-except
            self.signals.tested.emit(name, "invalid", str(exc))


class CallWorker(QRunnable):
    """Run ``fn`` off the GUI thread and deliver its result (or exception) via ``signals.done``."""

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _WorkerSignals()

    def run(self):
        try:
            result = self.fn()
        except Exception as exc:  # pylint: disable=broad-except
            result = exc
        self.signals.done.emit(result)


# ----------------------------------------------------------------------------------- Config view
class ConfigEditor(QObject):
    """State of the *Config* view: an edited copy of the session config, reviewed and applied.

    Args:
        client: The BEC client.
        dispatcher: The BEC dispatcher used for the scan-status subscription.
        parent: Parent QObject.
    """

    changed = Signal()
    toast = Signal(str, str, bool)  # message, tone, offers undo
    apply_progress = Signal(str, str, str)  # device, state (waiting/running/done/failed), message
    apply_finished = Signal(int, int)

    def __init__(self, client, dispatcher=None, parent: QObject | None = None):
        super().__init__(parent)
        self.client = client
        self.dispatcher = dispatcher
        self.session: dict[str, dict] = {}
        self.work: dict[str, dict] = {}
        self.status: dict[str, str] = {}
        self.messages: dict[str, str] = {}
        self.source = "running session"
        self.selected: str | None = None
        self.query = ""
        self.facets: dict[str, set[str]] = {"st": set(), "rp": set(), "tag": set()}
        self.undo_stack: list[tuple[dict, dict]] = []
        self.scan_running = False
        self.scan_number: int | None = None
        self.applying = False
        self.apply_rows: list[dict] = []
        self.apply_summary = ""
        self._changes: list[Change] | None = None
        self._workers: list[QRunnable] = []
        self._helper = None
        if dispatcher is not None:
            dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
            msg = client.connector.get(MessageEndpoints.scan_status())
            if msg is not None:
                self.on_scan_status(msg.content, msg.metadata)

    # ------------------------------------------------------------------ loading and saving
    def load_session(self) -> None:
        """Start a fresh edited copy from the running session."""
        configs = self.client.device_manager._get_redis_device_config() or []
        self.session = configs_by_name(configs)
        self.work = copy.deepcopy(self.session)
        self.status = {name: "session" for name in self.work}
        self.messages = {}
        self.source = "running session"
        self.undo_stack.clear()
        if self.selected not in self.work:
            self.selected = next(iter(self.work), None)
        self._touch()

    def refresh_session(self) -> None:
        """Re-read the running session but keep the edited copy (e.g. after applying)."""
        configs = self.client.device_manager._get_redis_device_config() or []
        self.session = configs_by_name(configs)
        self._restatus()
        self._touch()

    def open_file(self, path: str | Path) -> None:
        """Edit the devices of a YAML config file; the diff stays against the running session."""
        loaded = yaml_load(str(path)) or {}
        self._push_undo()
        self.work = configs_by_name(loaded)
        self.source = Path(path).name
        self._restatus(reset=True)
        if self.selected not in self.work:
            self.selected = next(iter(self.work), None)
        self._touch()
        self.toast.emit(f"Opened {self.source} — {len(self.work)} devices", "neutral", True)

    def save_file(self, path: str | Path) -> None:
        """Write the edited copy to ``path`` as YAML."""
        data = {
            name: {k: v for k, v in cfg.items() if k != "name"} for name, cfg in self.work.items()
        }
        Path(path).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        self.toast.emit(f"Saved {len(data)} devices to {Path(path).name}", "ok", False)

    # ------------------------------------------------------------------ derived state
    def changes(self) -> list[Change]:
        """Cached differences between session and edited copy."""
        if self._changes is None:
            self._changes = diff_configs(self.session, self.work)
        return self._changes

    def change_kinds(self) -> dict[str, str]:
        """``{device: "A" | "M" | "D"}``."""
        return {c.name: c.kind for c in self.changes()}

    def status_of(self, name: str) -> tuple[str, str, str]:
        """``(label, tone, icon)`` of a device's status."""
        return STATUS[self.status.get(name, "unchecked")]

    def matches(self, cfg: dict, kinds: dict[str, str]) -> bool:
        """True if ``cfg`` passes the search text and the facet filters."""
        q = self.query.strip().lower()
        if q:
            hay = " ".join(
                [
                    cfg["name"],
                    str(cfg.get("deviceClass", "")),
                    " ".join(cfg.get("deviceTags", [])),
                    str(cfg.get("deviceConfig", {}).get("prefix", "")),
                    str(cfg.get("description", "")),
                ]
            ).lower()
            if q not in hay:
                return False
        if self.facets["rp"] and cfg.get("readoutPriority") not in self.facets["rp"]:
            return False
        if self.facets["tag"] and not set(cfg.get("deviceTags", [])) & self.facets["tag"]:
            return False
        if self.facets["st"]:
            st = self.status.get(cfg["name"])
            ok = (
                ("changed" in self.facets["st"] and cfg["name"] in kinds)
                or ("problem" in self.facets["st"] and st in PROBLEM_STATES)
                or ("unchecked" in self.facets["st"] and st == "unchecked")
            )
            if not ok:
                return False
        return True

    def rows(self) -> list[dict]:
        """Table rows of the devices that pass the filters."""
        kinds = self.change_kinds()
        out = []
        for name, cfg in self.work.items():
            if not self.matches(cfg, kinds):
                continue
            label, tone, icon = self.status_of(name)
            old = self.session.get(name)
            rp_was = ""
            if old is not None and old.get("readoutPriority") != cfg.get("readoutPriority"):
                rp_was = f"was {old.get('readoutPriority')}"
            out.append(
                {
                    "name": name,
                    "deviceClass": short_class(cfg.get("deviceClass")),
                    "readout": str(cfg.get("readoutPriority", "")),
                    "readoutWas": rp_was,
                    "on": bool(cfg.get("enabled", True)),
                    "tags": ", ".join(cfg.get("deviceTags", [])),
                    "change": kinds.get(name, ""),
                    "changeLabel": CHANGE_LABELS.get(kinds.get(name, ""), ""),
                    "statusText": label,
                    "statusTone": tone,
                    "statusIcon": icon,
                    "selected": name == self.selected,
                }
            )
        return out

    def filters_active(self) -> bool:
        """True while a search text or facet narrows the table."""
        return bool(self.query.strip() or any(self.facets.values()))

    def facet_sections(self) -> list[dict]:
        """Facet groups for the filter column.

        Returns ``[{title, key, items: [{value, label, count, checked}]}]``.
        """
        all_cfg = list(self.work.values())
        problems = sum(1 for n in self.work if self.status.get(n) in PROBLEM_STATES)
        unchecked = sum(1 for n in self.work if self.status.get(n) == "unchecked")
        status_items = [
            ("changed", "Changed vs session", len(self.changes())),
            ("problem", "Problems", problems),
            ("unchecked", "Not checked yet", unchecked),
        ]
        readouts: dict[str, int] = {}
        tags: dict[str, int] = {}
        for cfg in all_cfg:
            rp = str(cfg.get("readoutPriority", ""))
            readouts[rp] = readouts.get(rp, 0) + 1
            for tag in cfg.get("deviceTags", []):
                tags[tag] = tags.get(tag, 0) + 1
        rp_items = [(k, k, readouts[k]) for k in READOUT_LABELS if readouts.get(k)]
        rp_items += [(k, k, n) for k, n in readouts.items() if k not in READOUT_LABELS]
        tag_items = [(t, t, n) for t, n in sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))]

        def section(title, key, items):
            return {
                "title": title,
                "key": key,
                "items": [
                    {"value": v, "label": l, "count": n, "checked": v in self.facets[key]}
                    for v, l, n in items
                ],
            }

        return [
            section("Status", "st", status_items),
            section("Readout priority", "rp", rp_items),
            section("Tags", "tag", tag_items),
        ]

    def problems(self) -> list[dict]:
        """Devices with a problem or not checked yet, for the Problems panel."""
        out = []
        for name in self.work:
            st = self.status.get(name)
            if st in PROBLEM_STATES or st == "unchecked":
                message = self.messages.get(name) or (
                    "Connection not tested yet" if st == "unchecked" else STATUS[st][0]
                )
                out.append({"name": name, "state": st, "message": message})
        return out

    def problem_counts(self) -> tuple[int, int]:
        """``(problems, not checked)``."""
        probs = self.problems()
        return (
            sum(1 for p in probs if p["state"] in PROBLEM_STATES),
            sum(1 for p in probs if p["state"] == "unchecked"),
        )

    def bar_state(self) -> dict:
        """Session bar: what is being edited and how far it is from the session."""
        n = len(self.changes())
        return {
            "sessionCount": len(self.session),
            "source": self.source,
            "changeCount": n,
            "changeText": (
                f"{n} change{'s' if n != 1 else ''} vs session" if n else "Same as session"
            ),
            "reviewText": f"Review changes ({n})" if n else "Review changes",
            "scanRunning": self.scan_running,
            "scanText": (
                f"Scan {self.scan_number} is running" if self.scan_number else "A scan is running"
            ),
            "canUndo": bool(self.undo_stack),
            "hasSelection": self.selected in self.work,
        }

    def detail(self) -> dict:
        """Inspector content for the selected device (``{"name": ""}`` when none)."""
        name = self.selected
        cfg = self.work.get(name) if name else None
        if cfg is None:
            return {"name": ""}
        old = self.session.get(name)
        label, tone, icon = self.status_of(name)

        def was(key: str, labels: dict | None = None) -> str:
            if old is None or old.get(key) == cfg.get(key):
                return ""
            value = old.get(key)
            text = (labels or {}).get(value, value_text(value))
            return f"In session: {text}"

        old_dc = (old or {}).get("deviceConfig", {})
        dev_cfg = [
            {
                "key": key,
                "value": value_text(value),
                "was": (
                    f"In session: {value_text(old_dc[key])}"
                    if old is not None and key in old_dc and old_dc[key] != value
                    else ("New key" if old is not None and key not in old_dc else "")
                ),
            }
            for key, value in cfg.get("deviceConfig", {}).items()
        ]
        known = {"name", "deviceClass", "deviceTags", "deviceConfig", *EDITABLE_FIELDS}
        extra = [
            {"key": k, "value": value_text(v)}
            for k, v in cfg.items()
            if k not in known and k not in ("softwareTrigger",)
        ]
        return {
            "name": name,
            "deviceClass": str(cfg.get("deviceClass", "")),
            "shortClass": short_class(cfg.get("deviceClass")),
            "statusText": label,
            "statusTone": tone,
            "statusIcon": icon,
            "statusMessage": self.messages.get(name, ""),
            "isNew": old is None,
            "isModified": old is not None and old != cfg,
            "readout": str(cfg.get("readoutPriority", "")),
            "readoutWas": was("readoutPriority", READOUT_LABELS),
            "enabled": bool(cfg.get("enabled", True)),
            "enabledWas": was("enabled"),
            "onFailure": str(cfg.get("onFailure", "retry")),
            "onFailureWas": was("onFailure", ON_FAILURE_LABELS),
            "readOnly": bool(cfg.get("readOnly", False)),
            "readOnlyWas": was("readOnly"),
            "description": str(cfg.get("description") or ""),
            "descriptionWas": was("description"),
            "tags": list(cfg.get("deviceTags", [])),
            "tagsWas": was("deviceTags"),
            "deviceConfig": dev_cfg,
            "extra": extra,
            "yaml": device_yaml(cfg),
        }

    def review(self) -> dict:
        """Content of the review sheet."""
        groups = []
        for kind, title in (("A", "Added"), ("M", "Modified"), ("D", "Removed")):
            items = []
            for c in self.changes():
                if c.kind != kind:
                    continue
                cfg = self.work.get(c.name) or self.session.get(c.name) or {}
                label, tone, icon = self.status_of(c.name) if c.name in self.work else ("", "", "")
                items.append(
                    {
                        "name": c.name,
                        "deviceClass": short_class(cfg.get("deviceClass")),
                        "statusText": label,
                        "statusTone": tone,
                        "statusIcon": icon,
                        "fields": [{"field": f, "old": a, "new": b} for f, a, b in c.fields],
                    }
                )
            if items:
                groups.append({"title": f"{title} ({len(items)})", "kind": kind, "items": items})
        n = len(self.changes())
        touched = sum(1 for c in self.changes() if c.kind != "A")
        unchecked = sum(
            1 for c in self.changes() if c.kind != "D" and self.status.get(c.name) == "unchecked"
        )
        return {
            "groups": groups,
            "count": n,
            "unchecked": unchecked,
            "uncheckedText": (
                f"{unchecked} changed device{'s' if unchecked != 1 else ''} not tested yet"
                if unchecked
                else ""
            ),
            "footText": f"{n} change{'s' if n != 1 else ''} · "
            f"{len(self.session) - touched} devices untouched",
            "applyText": f"Apply {n} change{'s' if n != 1 else ''}",
            "scanRunning": self.scan_running,
        }

    # ------------------------------------------------------------------ filters and selection
    def set_query(self, text: str) -> None:
        """Filter the table by name, class, tag, PV prefix or description."""
        if text != self.query:
            self.query = text
            self.changed.emit()

    def toggle_facet(self, key: str, value: str, checked: bool) -> None:
        """Add or remove one facet filter."""
        (self.facets[key].add if checked else self.facets[key].discard)(value)
        self.changed.emit()

    def clear_filters(self) -> None:
        """Remove the search text and all facet filters."""
        self.query = ""
        self.facets = {k: set() for k in self.facets}
        self.changed.emit()

    def select(self, name: str) -> None:
        """Select a device for the inspector."""
        if name in self.work and name != self.selected:
            self.selected = name
            self.changed.emit()

    # ------------------------------------------------------------------ editing
    def set_field(self, name: str, key: str, value: Any) -> None:
        """Change one top-level key of a device in the edited copy."""
        cfg = self.work.get(name)
        if cfg is None or cfg.get(key) == value:
            return
        self._push_undo()
        cfg[key] = value
        self._mark_edited(name)
        self._touch()

    def set_config_value(self, name: str, key: str, text: str) -> None:
        """Change one ``deviceConfig`` entry; ``text`` is parsed like YAML."""
        cfg = self.work.get(name)
        if cfg is None:
            return
        value = parse_value(text)
        if cfg["deviceConfig"].get(key) == value:
            return
        self._push_undo()
        cfg["deviceConfig"][key] = value
        self._mark_edited(name)
        self._touch()

    def add_tag(self, name: str, tag: str) -> None:
        """Add a tag to a device."""
        tag = tag.strip()
        cfg = self.work.get(name)
        if cfg is None or not tag or tag in cfg["deviceTags"]:
            return
        self.set_field(name, "deviceTags", sorted([*cfg["deviceTags"], tag]))

    def remove_tag(self, name: str, tag: str) -> None:
        """Remove a tag from a device."""
        cfg = self.work.get(name)
        if cfg is not None and tag in cfg["deviceTags"]:
            self.set_field(name, "deviceTags", [t for t in cfg["deviceTags"] if t != tag])

    def validate_new_name(self, name: str) -> str:
        """Error message for a new device name, or ``""`` if it can be used."""
        name = name.strip()
        if not name:
            return "Enter a name"
        if not (name[0].isalpha() and name.islower() and name.replace("_", "").isalnum()):
            return f"Use {NEW_NAME_RULE[0].lower()}{NEW_NAME_RULE[1:]}"
        if name in self.work:
            return f"{name} already exists — pick another name"
        return ""

    def add_device(self, name: str, device_class: str, prefix: str = "") -> str:
        """Add a device to the edited copy; returns an error message or ``""``."""
        error = self.validate_new_name(name)
        if error:
            return error
        name = name.strip()
        self._push_undo()
        dev_cfg = {"prefix": prefix.strip()} if prefix.strip() else {}
        self.work[name] = normalize_config(
            name,
            {"deviceClass": device_class, "readoutPriority": "baseline", "deviceConfig": dev_cfg},
        )
        self.status[name] = "unchecked"
        self.selected = name
        self._touch()
        return ""

    def remove(self, name: str | None = None) -> None:
        """Remove a device from the edited copy (Undo restores it)."""
        name = name or self.selected
        if name not in self.work:
            return
        self._push_undo()
        keys = list(self.work)
        index = keys.index(name)
        del self.work[name]
        rest = list(self.work)
        self.selected = rest[min(index, len(rest) - 1)] if rest else None
        self._touch()
        self.toast.emit(
            f"Removed {name} from the edited copy — the session is unchanged until you apply",
            "neutral",
            True,
        )

    def revert(self, name: str | None = None) -> None:
        """Reset a device to its session config."""
        name = name or self.selected
        if name not in self.session or self.work.get(name) == self.session[name]:
            return
        self._push_undo()
        self.work[name] = copy.deepcopy(self.session[name])
        self.status[name] = "session"
        self.messages.pop(name, None)
        self._touch()

    def undo(self) -> None:
        """Undo the last edit."""
        if not self.undo_stack:
            return
        self.work, self.status = self.undo_stack.pop()
        if self.selected not in self.work:
            self.selected = next(iter(self.work), None)
        self._touch()
        self.toast.emit("Undone", "neutral", False)

    # ------------------------------------------------------------------ testing
    def test(self, name: str | None = None) -> None:
        """Test config and connection of one device without blocking the GUI."""
        name = name or self.selected
        cfg = self.work.get(name)
        if cfg is None:
            return
        self.status[name] = "testing"
        self.messages.pop(name, None)
        worker = TestWorker(copy.deepcopy(cfg))
        worker.signals.tested.connect(self._on_tested)
        self._start(worker)
        self.changed.emit()

    def test_all(self) -> None:
        """Test every device of the edited copy."""
        for name in list(self.work):
            self.test(name)

    def _on_tested(self, name: str, status: str, message: str) -> None:
        if name not in self.work:
            return
        unchanged = self.work[name] == self.session.get(name)
        self.status[name] = "session" if status == "valid" and unchanged else status
        if message:
            self.messages[name] = message.strip()
        else:
            self.messages.pop(name, None)
        tone = "err" if status in PROBLEM_STATES else "ok"
        text = f"{name}: connection OK" if status == "valid" else f"{name}: {STATUS[status][0]}"
        self.toast.emit(text, tone, False)
        self._touch()

    # ------------------------------------------------------------------ applying
    def on_scan_status(self, content: dict, _metadata: dict | None = None) -> None:
        """Lock applying while a scan is open or paused."""
        status = content.get("status")
        self.scan_running = status in ("open", "paused")
        self.scan_number = content.get("scan_number") if self.scan_running else None
        self.changed.emit()

    def can_apply(self) -> bool:
        """True if there is something to apply and nothing blocks it."""
        return bool(self.changes()) and not self.scan_running and not self.applying

    def apply(self) -> bool:
        """Apply all changes, device by device, off the GUI thread."""
        if not self.can_apply():
            return False
        requests = [(c.name, plan_requests(c, self.session, self.work)) for c in self.changes()]
        self.applying = True
        self.apply_summary = ""
        kinds = {"A": "add", "M": "update", "D": "remove"}
        self.apply_rows = [
            {"name": c.name, "action": kinds[c.kind], "state": "waiting", "message": ""}
            for c in self.changes()
        ]
        worker = ApplyWorker(self._config_helper(), requests)
        worker.signals.progress.connect(self._on_apply_progress)
        worker.signals.finished.connect(self._on_apply_finished)
        self._start(worker)
        self.changed.emit()
        return True

    def _config_helper(self):
        # A separate helper: the client's own one would block other config traffic.
        if self._helper is None:
            self._helper = config_helper.ConfigHelper(self.client.connector)
        return self._helper

    def _on_apply_progress(self, name: str, state: str, message: str) -> None:
        for row in self.apply_rows:
            if row["name"] == name:
                row["state"], row["message"] = state, message
        if state == "failed":
            if name in self.work:
                self.status[name] = "invalid"
            self.messages[name] = message
        self.apply_progress.emit(name, state, message)
        self.changed.emit()

    def _on_apply_finished(self, applied: int, failed: int) -> None:
        self.applying = False
        total = applied + failed
        self.apply_summary = f"{applied} of {total} changes applied"
        try:
            self.refresh_session()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"Could not re-read the session after applying: {exc}")
        self.apply_finished.emit(applied, failed)
        self.changed.emit()

    def clear_session(self, confirmation: str) -> str:
        """Remove every device from the running session. Returns an error or ``""``."""
        if confirmation.strip() != "CLEAR":
            return "Type CLEAR to confirm"
        if self.scan_running:
            return "Clearing is not possible during a scan"
        worker = CallWorker(self.client.config.reset_config)
        worker.signals.done.connect(self._on_cleared)
        self._start(worker)
        return ""

    def _on_cleared(self, result) -> None:
        if isinstance(result, Exception):
            self.toast.emit(f"Clearing the session failed: {result}", "err", False)
            return
        self.refresh_session()
        self.toast.emit("The running session is now empty", "warn", False)

    # ------------------------------------------------------------------ internals
    def _start(self, worker: QRunnable) -> None:
        worker.setAutoDelete(False)
        self._workers.append(worker)
        worker.signals.finished.connect(lambda *_: self._drop(worker))
        worker.signals.tested.connect(lambda *_: self._drop(worker))
        worker.signals.done.connect(lambda *_: self._drop(worker))
        QThreadPool.globalInstance().start(worker)

    def _drop(self, worker: QRunnable) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    def _push_undo(self) -> None:
        self.undo_stack.append((copy.deepcopy(self.work), dict(self.status)))
        del self.undo_stack[:-100]

    def _mark_edited(self, name: str) -> None:
        if self.work[name] == self.session.get(name):
            self.status[name] = "session"
        elif self.status.get(name) not in PROBLEM_STATES:
            self.status[name] = "unchecked"

    def _restatus(self, reset: bool = False) -> None:
        for name, cfg in self.work.items():
            same = cfg == self.session.get(name)
            if same:
                self.status[name] = "session"
            elif reset or self.status.get(name) in (None, "session"):
                self.status[name] = "unchecked"
        for name in list(self.status):
            if name not in self.work:
                del self.status[name]

    def _touch(self) -> None:
        self._changes = None
        self.changed.emit()

    def cleanup(self) -> None:
        """Disconnect the scan-status subscription."""
        if self.dispatcher is not None:
            self.dispatcher.disconnect_slot(self.on_scan_status, MessageEndpoints.scan_status())


# ---------------------------------------------------------------------------------- Devices view
KINDS = [
    ("positioner", "Motors"),
    ("monitor", "Monitors"),
    ("detector", "Detectors"),
    ("any", "All"),
]
PREFERRED = ["samx", "samy", "samz", "mokev", "idgap", "bpm4i", "bpm3a", "diode", "eiger"]
MAX_ROWS = 150


def device_kind(device) -> str:
    """Classify a session device as ``positioner``, ``detector`` or ``monitor``."""
    if isinstance(device, Positioner):
        return "positioner"
    priority = str(getattr(device, "readout_priority", "") or "").lower()
    tags = {str(t).lower() for t in (getattr(device, "_config", {}) or {}).get("deviceTags", [])}
    if priority.endswith("async") or "detector" in tags:
        return "detector"
    return "monitor"


def readback_value(name: str, content: dict | None) -> Any:
    """The main value of a device readback message (its own signal, else the first one)."""
    signals = (content or {}).get("signals") or {}
    entry = signals.get(name)
    if entry is None and signals:
        entry = next(iter(signals.values()))
    return (entry or {}).get("value")


def format_value(value: Any, precision: int | None, units: str = "") -> str:
    """Readable value with the device precision and unit; arrays show their shape."""
    if value is None:
        return "—"
    if hasattr(value, "shape") and getattr(value, "shape", ()):
        return f"array {tuple(value.shape)}"
    if isinstance(value, (list, tuple)):
        return f"list [{len(value)}]"
    if isinstance(value, bool):
        text = str(value)
    elif isinstance(value, (int, float)):
        text = f"{value:.{precision}f}" if isinstance(precision, int) else f"{value:.6g}"
        text = text.replace("-", "−", 1) if text.startswith("-") else text
    else:
        text = str(value)
    return f"{text} {units}".strip()


class DeviceBrowser(QObject):
    """State of the *Devices* view: find a device by kind and text, see it live.

    Args:
        client: The BEC client.
        dispatcher: The BEC dispatcher for readback subscriptions.
        parent: Parent QObject.
    """

    changed = Signal()
    values_changed = Signal()
    spark_changed = Signal()
    open_in_workspace = Signal(str, str)  # widget class name, device

    def __init__(self, client, dispatcher=None, parent: QObject | None = None):
        super().__init__(parent)
        self.client = client
        self.dispatcher = dispatcher
        self.kind = "positioner"
        self.query = ""
        self.selected: str | None = None
        self.values: dict[str, Any] = {}
        self.spark: deque = deque(maxlen=90)
        self._subscribed: list[str] = []
        self._dirty = False
        self._throttle = QTimer(self)
        self._throttle.setInterval(250)
        self._throttle.timeout.connect(self._flush_values)
        self._throttle.start()
        self._workers: list[QRunnable] = []
        self._visible: list[dict] = []
        self._total = 0

    # ------------------------------------------------------------------ data
    def _devices(self) -> dict:
        try:
            return dict(self.client.device_manager.devices.items())
        except AttributeError:
            return {}

    def _info(self, name: str, device) -> dict:
        info = getattr(device, "_info", {}) or {}
        describe = (info.get("describe") or {}).get(name, {})
        cfg = getattr(device, "_config", {}) or {}
        precision = getattr(device, "precision", None)
        if not isinstance(precision, int):
            precision = (
                describe.get("precision") if isinstance(describe.get("precision"), int) else None
            )
        return {
            "units": str(describe.get("units") or describe.get("egu") or ""),
            "precision": precision,
            "description": str(cfg.get("description") or ""),
            "deviceClass": short_class(cfg.get("deviceClass", type(device).__name__)),
            "tags": sorted(str(t) for t in cfg.get("deviceTags", []) or []),
            "readout": str(cfg.get("readoutPriority", "")),
            "enabled": bool(cfg.get("enabled", True)),
        }

    def kind_counts(self) -> dict[str, int]:
        """Number of devices per kind, for the kind switch."""
        counts = {k: 0 for k, _ in KINDS}
        for device in self._devices().values():
            counts[device_kind(device)] += 1
            counts["any"] += 1
        return counts

    def rows(self) -> list[dict]:
        """Up to :data:`MAX_ROWS` devices matching kind and search, preferred names first."""
        q = self.query.strip().lower()
        out = []
        for name, device in self._devices().items():
            kind = device_kind(device)
            if self.kind not in ("any", kind):
                continue
            info = self._info(name, device)
            if (
                q
                and q
                not in " ".join(
                    [name, info["description"], info["deviceClass"], " ".join(info["tags"])]
                ).lower()
            ):
                continue
            what = info["description"] or " · ".join(
                x for x in (info["deviceClass"], ", ".join(info["tags"]) or info["readout"]) if x
            )
            out.append(
                {
                    "name": name,
                    "what": what,
                    "kind": kind,
                    "valueText": format_value(
                        self.values.get(name), info["precision"], info["units"]
                    ),
                    "selected": name == self.selected,
                }
            )
        pref = {n: i for i, n in enumerate(PREFERRED)}
        out.sort(key=lambda r: (pref.get(r["name"], len(pref)), r["name"]))
        self._total = len(out)
        self._visible = out[:MAX_ROWS]
        self._resubscribe([r["name"] for r in self._visible])
        return self._visible

    def shown_text(self) -> str:
        """``"150 of 212 shown"``."""
        total = self._total
        return f"{len(self._visible)} of {total} shown"

    def detail(self) -> dict:
        """Detail panel of the selected device."""
        name = self.selected
        device = self._devices().get(name) if name else None
        if device is None:
            return {"name": ""}
        info = self._info(name, device)
        kind = device_kind(device)
        facts = [
            ("Class", info["deviceClass"]),
            ("Readout", info["readout"]),
            ("Tags", ", ".join(info["tags"]) or "—"),
        ]
        if not info["enabled"]:
            facts.append(("Enabled", "No — disabled in the session"))
        return {
            "name": name,
            "kind": kind,
            "description": info["description"] or info["deviceClass"],
            "valueText": format_value(self.values.get(name), info["precision"]),
            "units": info["units"],
            "facts": [{"label": k, "value": v} for k, v in facts],
            "actionText": {
                "positioner": f"Add {name} to the workspace",
                "detector": "Open the live image in the workspace",
            }.get(kind, f"Plot {name} in the workspace"),
        }

    def spark_points(self) -> list[float]:
        """Recent numeric values of the selected monitor (oldest first)."""
        return [float(v) for v in self.spark]

    # ------------------------------------------------------------------ interaction
    def set_kind(self, kind: str) -> None:
        """Show only one kind of device."""
        if kind != self.kind:
            self.kind = kind
            self.changed.emit()

    def set_query(self, text: str) -> None:
        """Filter by name, description, class or tag."""
        if text != self.query:
            self.query = text
            self.changed.emit()

    def select(self, name: str) -> None:
        """Show a device in the detail panel."""
        if name == self.selected:
            return
        self.selected = name
        self.spark.clear()
        value = self.values.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            self.spark.append(value)
        self.changed.emit()
        self.spark_changed.emit()

    def request_open(self) -> None:
        """Ask the app to open a widget for the selected device in the workspace."""
        device = self._devices().get(self.selected) if self.selected else None
        if device is None:
            return
        widget = {"positioner": "PositionerBox", "detector": "Image"}.get(
            device_kind(device), "Waveform"
        )
        self.open_in_workspace.emit(widget, self.selected)

    # ------------------------------------------------------------------ live values
    def _resubscribe(self, names: list[str]) -> None:
        if self.dispatcher is None or names == self._subscribed:
            return
        old = [n for n in self._subscribed if n not in names]
        new = [n for n in names if n not in self._subscribed]
        if old:
            self.dispatcher.disconnect_slot(
                self.on_readback, [MessageEndpoints.device_readback(n) for n in old]
            )
        if new:
            self.dispatcher.connect_slot(
                self.on_readback, [MessageEndpoints.device_readback(n) for n in new]
            )
            missing = [n for n in new if n not in self.values]
            if missing:
                self._fetch_initial(missing)
        self._subscribed = list(names)

    def _fetch_initial(self, names: list[str]) -> None:
        connector = self.client.connector

        def read():
            out = {}
            for n in names:
                msg = connector.get(MessageEndpoints.device_readback(n))
                if msg is not None:
                    out[n] = readback_value(n, msg.content)
            return out

        worker = CallWorker(read)
        worker.setAutoDelete(False)
        worker.signals.done.connect(self._on_initial)
        self._workers.append(worker)
        QThreadPool.globalInstance().start(worker)

    def _on_initial(self, result) -> None:
        self._workers = [w for w in self._workers if w.signals is not self.sender()]
        if isinstance(result, dict):
            for name, value in result.items():
                self.values.setdefault(name, value)
            self._dirty = True

    def on_readback(self, content: dict, metadata: dict) -> None:
        """Store a readback; the views refresh at most every 250 ms."""
        name = (metadata or {}).get("device")
        signals = (content or {}).get("signals") or {}
        if name is None:
            name = next((n for n in self._subscribed if n in signals), None)
            if name is None and signals:
                first = next(iter(signals))
                name = next((n for n in self._subscribed if first.startswith(f"{n}_")), first)
        if name is None:
            return
        value = readback_value(name, content)
        self.values[name] = value
        if name == self.selected and isinstance(value, (int, float)):
            self.spark.append(value)
            self.spark_changed.emit()
        self._dirty = True

    def _flush_values(self) -> None:
        if self._dirty:
            self._dirty = False
            self.values_changed.emit()

    def cleanup(self) -> None:
        """Stop the refresh timer and drop all readback subscriptions."""
        self._throttle.stop()
        if self.dispatcher is not None and self._subscribed:
            self.dispatcher.disconnect_slot(
                self.on_readback, [MessageEndpoints.device_readback(n) for n in self._subscribed]
            )
        self._subscribed = []
