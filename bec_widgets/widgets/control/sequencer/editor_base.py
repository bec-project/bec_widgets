"""Common base for the five sequencer editor concepts."""

from __future__ import annotations

import copy

from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets import BECWidget
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.backend import Problem, SequencerBackend
from bec_widgets.widgets.control.sequencer.document import SequenceDocument
from bec_widgets.widgets.control.sequencer.run_bar import RunBar


class SequenceEditorBase(BECWidget, QWidget):
    """An editor for one sequence document, with the shared run bar underneath.

    Subclasses build their editing surface in ``build_editor`` and redraw in ``refresh``.
    ``show_problems`` receives the validation problems so the editor can mark the step.

    Args:
        parent (QWidget | None): Parent widget.
        client: BEC client.
        doc (dict | None): Initial document; defaults to the shared example.
    """

    RPC = False
    PLUGIN = False
    CONCEPT_ID = ""
    CONCEPT_TITLE = ""
    CONCEPT_TAGLINE = ""

    def __init__(self, parent=None, client=None, doc: dict | None = None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.get_bec_shortcuts()
        self.backend = SequencerBackend(self.client)
        self.document = SequenceDocument(doc if doc is not None else model.example_document(), self)
        self.problems: list[Problem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.editor = QWidget(self)
        layout.addWidget(self.editor, 1)
        self.build_editor(self.editor)
        self.run_bar = RunBar(self.backend, self.document, self)
        layout.addWidget(self.run_bar)
        self.run_bar.problems_changed.connect(self._on_problems)
        self.document.changed.connect(self.refresh)
        self.refresh()
        self.run_bar.check()

    def build_editor(self, host: QWidget) -> None:
        """Create the editing surface inside ``host``."""
        raise NotImplementedError

    def refresh(self) -> None:
        """Redraw after the document changed."""

    def show_problems(self, problems: list[Problem]) -> None:
        """Mark steps that need a fix."""

    def save_state(self) -> dict:
        """What the editor needs to come back after being rebuilt (e.g. on a theme change)."""
        return {"doc": copy.deepcopy(self.document.doc), "selected": self.document.selected}

    def restore_state(self, state: dict) -> None:
        """Restore ``save_state`` output."""
        self.document.set_document(state["doc"])
        if state.get("selected"):
            self.document.select(state["selected"])

    def _on_problems(self, problems: list) -> None:
        self.problems = problems
        self.show_problems(problems)

    def problem_for(self, node_id: str) -> str:
        """Problem message for a step, or an empty string."""
        return next((p.message for p in self.problems if p.node_id == node_id), "")

    def scan_entries(self) -> dict:
        """Advertised scans by name."""
        return self.backend.scan_entries()

    def cleanup(self):
        """Stop timers of the shared parts."""
        self.run_bar.cleanup()
        inspector = getattr(self, "inspector", None)
        if inspector is not None:
            inspector.cleanup()
        super().cleanup()
