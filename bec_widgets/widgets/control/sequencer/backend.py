"""Bridge between the sequencer editors and ``bec_lib.scan_sequencer``.

The backend lives in bec (draft PR bec-project/bec#1128). When the installed bec_lib does not
ship it yet, editing still works and ``available`` is False, so the GUI can say why checking
and running are disabled.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger

logger = bec_logger.logger

try:  # the backend is not released yet
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


@dataclass
class Problem:
    """A validation problem, attached to a step when the backend names one."""

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
    if message.startswith("Unknown scan: "):
        return f"This beamline has no scan called “{message.split(': ', 1)[1]}”"
    return message.strip().splitlines()[0] if message.strip() else "Unknown problem"


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

    @property
    def available(self) -> bool:
        """Whether bec_lib ships the scan sequencer."""
        return BACKEND_AVAILABLE

    # --- scans -----------------------------------------------------------------------------
    def scan_entries(self) -> dict[str, dict]:
        """Advertised scans usable as a sequence step, by name."""
        try:
            msg = self.client.connector.get(MessageEndpoints.available_scans())
        except Exception:  # pylint: disable=broad-except
            return {}
        resource = getattr(msg, "resource", None) or {}
        return {
            name: info
            for name, info in resource.items()
            if name not in _HIDDEN_SCANS and not info.get("is_internal")
        }

    def device_names(self) -> list[str]:
        """Names of devices that can be moved or set."""
        try:
            return sorted(self.client.device_manager.devices.keys())
        except Exception:  # pylint: disable=broad-except
            return []

    # --- checks and exports ----------------------------------------------------------------
    def _tree(self, doc: dict):
        schedule = Schedule.model_validate(doc)
        tree, _ = DefinitionLibrary(self.definitions).resolve(schedule.root)
        return tree

    def _device_manager(self):
        return getattr(self.client, "device_manager", None)

    def validate(self, doc: dict) -> list[Problem]:
        """Validate a document; returns an empty list when it can run.

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
