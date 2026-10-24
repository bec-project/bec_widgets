"""Bridge between the sequencer editors and ``bec_lib.scan_sequencer``.

The backend lives in bec (bec-project/bec#1128). When the installed bec_lib does not ship it
yet, editing still works and ``available`` is False, so the GUI can say why checking and
running are disabled.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger

from bec_widgets.widgets.control.scan_control.scan_info_adapter import ScanInfoAdapter

logger = bec_logger.logger

try:  # the backend is not released yet
    # pylint: disable=ungrouped-imports
    from bec_lib.scan_sequencer import DefinitionLibrary, ScanCatalog, Schedule
    from bec_lib.scan_sequencer.core.description import describe as _describe
    from bec_lib.scan_sequencer.core.python_export import export_python as _export_python
    from bec_lib.scan_sequencer.core.validation import validate as _validate

    BACKEND_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the installed bec_lib
    BACKEND_AVAILABLE = False

# Scans that make no sense as a sequence step (moves have their own step).
_HIDDEN_SCANS = {
    "mv",
    "umv",
    "device_rpc",
    "open_scan_def",
    "close_scan_def",
    "close_scan_group",
    "open_interactive_scan",
    "close_interactive_scan",
    "interactive_scan_trigger",
}

_NODE_PREFIX = re.compile(r"^Node (?P<path>[^:]+): (?P<message>.*)$", re.S)
_EXECUTION_ERROR = re.compile(r"ExecutionError: Node (?P<path>[^:]+): (?P<message>.*)$", re.S)


@dataclass
class Problem:
    """A problem in a sequence, attached to a step when one is known."""

    node_id: str
    message: str


def friendly_message(message: str) -> str:
    """Make a backend validation message readable for scientists."""
    message = message.replace("ScanInputValidationError: ", "")
    message = re.sub(r"^\d+ validation errors? for \w+\s*", "", message)
    if message.startswith("Undefined Reference: "):
        name = message.split(": ", 1)[1]
        return f"“{name}” is only known inside its “For each {name}” loop"
    if message.startswith("Unknown device or signal: "):
        return f"There is no device called “{message.split(': ', 1)[1]}”"
    if message.startswith("Non-settable device or signal: "):
        return f"“{message.split(': ', 1)[1]}” cannot be moved or set"
    if message.startswith("Unknown scan: "):
        return f"This beamline has no scan called “{message.split(': ', 1)[1]}”"
    device = re.match(r"Device '(.*)' specified for scan argument", message)
    if device:
        name = device.group(1)
        return f"There is no device called “{name}”" if name else "Choose a motor for the scan"
    return message.strip().splitlines()[0] if message.strip() else "Unknown problem"


def run_failure(error: str | None) -> Problem:
    """Turn the error of a failed sequence into the step that failed and a short reason.

    Args:
        error (str | None): Error text of the procedure, usually a traceback.

    Returns:
        Problem: The failed step (empty id when unknown) and the last line of the reason.
    """
    text = (error or "").strip()
    match = _EXECUTION_ERROR.search(text)
    node_id = ""
    if match:
        node_id = match.group("path").split("/")[-1]
        text = match.group("message")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return Problem(node_id, lines[-1] if lines else "The sequence failed")


def sequences_dir(client) -> Path | None:
    """Folder where sequences and drafts are kept, next to the widget profiles.

    Args:
        client: BEC client.

    Returns:
        Path | None: The folder, or None when the client has no widget settings folder.
    """
    # the same settings folder the widget profiles use
    # pylint: disable=protected-access
    try:
        settings = client._service_config.config.get("widgets_settings") or {}
        base = settings.get("base_path")
    except Exception:  # pylint: disable=broad-except
        return None
    if not isinstance(base, str) or not base:
        return None
    return Path(base).expanduser() / "sequences"


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


class SequencerBackend:
    """Check, describe, export and run sequence documents for one BEC client.

    Args:
        client: BEC client of the hosting widget.
    """

    QUEUE = "sequences"

    def __init__(self, client):
        self.client = client
        self.definitions: list[dict] = []
        self._helper = None
        self._entries: dict[str, dict] | None = None

    @property
    def available(self) -> bool:
        """Whether bec_lib ships the scan sequencer."""
        return BACKEND_AVAILABLE

    # --- scans -----------------------------------------------------------------------------
    def reload(self) -> None:
        """Forget the cached scan list, e.g. after the beamline configuration changed."""
        self._entries = None

    def scan_entries(self) -> dict[str, dict]:
        """Advertised scans that can be a sequence step, by name (read once, then cached)."""
        if self._entries is None:
            try:
                msg = self.client.connector.get(MessageEndpoints.available_scans())
            except Exception:  # pylint: disable=broad-except
                msg = None
            resource = getattr(msg, "resource", None) or {}
            self._entries = {
                name: info
                for name, info in sorted(resource.items())
                if name not in _HIDDEN_SCANS
                and not name.startswith("_")
                and not info.get("is_internal")
                and ScanInfoAdapter.has_scan_ui_config(info)
            }
        return self._entries

    # --- devices ---------------------------------------------------------------------------
    def _devices(self):
        try:
            return self.client.device_manager.devices
        except Exception:  # pylint: disable=broad-except
            return {}

    def device_names(self) -> list[str]:
        """Names of all configured devices."""
        try:
            return sorted(self._devices().keys())
        except Exception:  # pylint: disable=broad-except
            return []

    def device(self, name: str):
        """The device proxy for a name (``samx`` or ``samx.velocity``), or None."""
        if not name:
            return None
        root, _, rest = name.partition(".")
        try:
            device = self._devices().get(root)
            for part in [p for p in rest.split(".") if p]:
                device = getattr(device, part)
            return device
        except Exception:  # pylint: disable=broad-except
            return None

    def is_motor(self, name: str) -> bool:
        """Whether a name is a motor (a positioner), so its value must be a number."""
        device = self.device(name)
        if isinstance(device, Positioner):
            return True
        return getattr(device, "_info", {}).get("device_base_class") == "positioner"

    def limits(self, name: str) -> tuple[float, float] | None:
        """Soft limits of a motor, or None when it has none."""
        device = self.device(name)
        if device is None or not self.is_motor(name):
            return None
        try:
            low, high = (float(v) for v in device.limits)
        except Exception:  # pylint: disable=broad-except
            return None
        if low == high == 0 or low >= high:
            return None
        return low, high

    def position(self, name: str) -> float | None:
        """Last known position of a motor (from the cache, no hardware access)."""
        device = self.device(name)
        if device is None or not self.is_motor(name):
            return None
        try:
            reading = device.read(cached=True) or {}
        except Exception:  # pylint: disable=broad-except
            return None
        value = (reading.get(device.name) or reading.get(name) or {}).get("value")
        return _number(value)

    # --- checks and exports ----------------------------------------------------------------
    def _tree(self, doc: dict):
        schedule = Schedule.model_validate(doc)
        tree, _ = DefinitionLibrary(self.definitions).resolve(schedule.root)
        return tree

    def _device_manager(self):
        return getattr(self.client, "device_manager", None)

    def validate(self, doc: dict) -> list[Problem]:
        """Validate a document with the backend; returns an empty list when it can run.

        The backend stops at the first problem, so at most one problem is returned.
        """
        if not BACKEND_AVAILABLE:
            return []
        try:
            tree = self._tree(doc)
            catalog = ScanCatalog(self.scan_entries(), self._device_manager())
            _validate(tree, catalog, self._device_manager())
        except Exception as exc:  # pylint: disable=broad-except
            text = str(exc)
            match = _NODE_PREFIX.match(text)
            if match:
                node_id = match.group("path").split("/")[-1]
                return [Problem(node_id, friendly_message(match.group("message")))]
            return [Problem("", friendly_message(text))]
        return []

    def describe(self, doc: dict) -> str:
        """Backend's procedural description."""
        if not BACKEND_AVAILABLE:
            return "The scan sequencer backend is not installed."
        return _describe(self._tree(doc))

    def python(self, doc: dict) -> str:
        """Equivalent BEC IPython code."""
        if not BACKEND_AVAILABLE:
            return "# The scan sequencer backend is not installed."
        return _export_python(self._tree(doc), self._device_manager())

    # --- execution -------------------------------------------------------------------------
    def submit(self, doc: dict):
        """Queue the sequence on the procedure worker.

        Returns:
            ProcedureStatus: Status of the queued procedure.
        """
        # pylint: disable=import-outside-toplevel
        from bec_lib.procedures.helper import FrontendProcedureHelper

        if self._helper is None:
            self._helper = FrontendProcedureHelper(self.client.connector)
        return self._helper.request.procedure(
            "run_sequence", ((doc, list(self.definitions)), {}), self.QUEUE
        )

    def close(self) -> None:
        """Stop listening for procedure updates."""
        helper, self._helper = self._helper, None
        if helper is None:
            return
        connector = self.client.connector
        # pylint: disable=protected-access
        try:
            connector.unregister(
                MessageEndpoints.procedure_request_response(), cb=helper._request_cb
            )
            connector.unregister(MessageEndpoints.procedure_status_update(), cb=helper._update_cb)
        except Exception:  # pylint: disable=broad-except
            logger.debug("Could not unregister the procedure helper callbacks")
