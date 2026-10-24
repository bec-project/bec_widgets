"""Common base for the five sequencer editor concepts."""

from __future__ import annotations

import copy
import json

from bec_lib.logger import bec_logger
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets import BECWidget
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.backend import Problem, SequencerBackend, sequences_dir
from bec_widgets.widgets.control.sequencer.document import SequenceDocument
from bec_widgets.widgets.control.sequencer.run_bar import RunBar

logger = bec_logger.logger


class SequenceEditorBase(BECWidget, QWidget):
    """An editor for one sequence document, with the shared run bar underneath.

    Subclasses build their editing surface in ``build_editor`` and redraw in ``refresh``.
    ``show_problems`` receives the problems so the editor can mark each step that needs a fix.

    Args:
        parent (QWidget | None): Parent widget.
        client: BEC client.
        doc (dict | None): Initial document; an empty sequence by default.
        draft_name (str | None): Keep the work in a draft file with this name, so it is still
            there after the application was closed. No draft is kept without a name.
    """

    RPC = False
    PLUGIN = False
    CONCEPT_ID = ""
    CONCEPT_TITLE = ""
    CONCEPT_TAGLINE = ""

    # Asks the host to open a sequence in the Recipe editor, which can edit any sequence.
    open_in_recipe = Signal(dict)

    def __init__(
        self,
        parent=None,
        client=None,
        doc: dict | None = None,
        draft_name: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, **kwargs)
        self.get_bec_shortcuts()
        self.backend = SequencerBackend(self.client)
        self.document = SequenceDocument(doc, self)
        self.problems: list[Problem] = []
        self.draft_name = draft_name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.editor = QWidget(self)
        layout.addWidget(self.editor, 1)
        self.build_editor(self.editor)
        self.run_bar = RunBar(self.backend, self.document, self.bec_dispatcher, self)
        layout.addWidget(self.run_bar)
        self.run_bar.problems_changed.connect(self._on_problems)
        self.run_bar.new_requested.connect(self.reset)
        self.run_bar.opened.connect(self.open_document)
        self.document.changed.connect(self.refresh)

        self._draft_timer = QTimer(self, singleShot=True, interval=1000)
        self._draft_timer.timeout.connect(self.save_draft)
        if doc is None:
            self.load_draft()
        self.document.changed.connect(self._draft_timer.start)
        self.refresh()
        self.run_bar.check()

    def build_editor(self, host: QWidget) -> None:
        """Create the editing surface inside ``host``."""
        raise NotImplementedError

    def refresh(self) -> None:
        """Redraw after the document changed."""

    def show_problems(self, problems: list[Problem]) -> None:
        """Mark steps that need a fix."""

    def reset(self) -> None:
        """Start over with an empty sequence."""
        self.document.set_document(model.empty_document())

    def open_document(self, doc: dict) -> None:
        """Show a sequence opened from a file."""
        self.document.set_document(doc)

    # --- state and drafts ------------------------------------------------------------------
    def save_state(self) -> dict:
        """What the editor needs to come back after being rebuilt (e.g. on a theme change)."""
        return {"doc": copy.deepcopy(self.document.doc), "selected": self.document.selected}

    def restore_state(self, state: dict) -> None:
        """Restore ``save_state`` output."""
        self.document.set_document(state["doc"])
        if state.get("selected"):
            self.document.select(state["selected"])

    def _draft_path(self):
        folder = sequences_dir(self.client) if self.draft_name else None
        return folder / "drafts" / f"{self.draft_name}.json" if folder else None

    def save_draft(self) -> None:
        """Write the current work to the draft file."""
        path = self._draft_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.save_state(), indent=1), encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            logger.warning(f"Could not save the sequence draft {path}: {exc}")

    def load_draft(self) -> None:
        """Bring back the work from the draft file, if there is one."""
        path = self._draft_path()
        if path is None or not path.exists():
            return
        try:
            self.restore_state(json.loads(path.read_text(encoding="utf-8")))
            self.document.select("")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"Could not restore the sequence draft {path}: {exc}")

    # --- problems --------------------------------------------------------------------------
    def _on_problems(self, problems: list) -> None:
        self.problems = problems
        inspector = getattr(self, "inspector", None)
        if inspector is not None:
            inspector.set_problems(problems)
        self.show_problems(problems)

    def problem_for(self, node_id: str) -> str:
        """Problem message for a step, or an empty string."""
        return next((p.message for p in self.problems if p.node_id == node_id), "")

    def scan_entries(self) -> dict:
        """Advertised scans by name."""
        return self.backend.scan_entries()

    def cleanup(self):
        """Save the draft and stop timers of the shared parts."""
        inspector = getattr(self, "inspector", None)
        if inspector is not None:
            inspector.cleanup()
        if self._draft_timer.isActive():
            self._draft_timer.stop()
            self.save_draft()
        self.run_bar.cleanup()
        super().cleanup()
