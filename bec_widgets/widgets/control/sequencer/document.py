"""Editable sequence document shared by an editor and the run bar."""

from __future__ import annotations

import copy

from qtpy.QtCore import QObject, Signal

from bec_widgets.widgets.control.sequencer import model


class SequenceDocument(QObject):
    """Hold one sequence document and announce every change.

    Editors change the tree through these methods (or change node dictionaries directly and
    call ``touch``), and listen to ``changed`` to redraw. ``selection_changed`` carries the id
    of the selected step, so a list, a canvas and an inspector can follow the same selection.
    """

    changed = Signal()
    selection_changed = Signal(str)

    def __init__(self, doc: dict | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._doc = model.normalize(copy.deepcopy(doc) if doc else model.empty_document())
        self._selected = ""
        self._undo: list[dict] = []

    # --- access ----------------------------------------------------------------------------
    @property
    def doc(self) -> dict:
        """The document as plain JSON-compatible data."""
        return self._doc

    @property
    def root(self) -> dict:
        """The root group."""
        return self._doc["root"]

    @property
    def selected(self) -> str:
        """Id of the selected step, or an empty string."""
        return self._selected

    def node(self, node_id: str) -> dict | None:
        """Return a node by id."""
        return model.find(self.root, node_id)[0]

    # --- changes ---------------------------------------------------------------------------
    def set_document(self, doc: dict) -> None:
        """Replace the whole document."""
        self._remember()
        self._doc = model.normalize(copy.deepcopy(doc))
        self._selected = ""
        self.touch()

    def touch(self) -> None:
        """Announce that the document changed."""
        self.changed.emit()

    def select(self, node_id: str) -> None:
        """Select a step by id (empty string clears)."""
        if node_id == self._selected:
            return
        self._selected = node_id or ""
        self.selection_changed.emit(self._selected)

    def add(self, nodes: list[dict], parent_id: str | None = None, index: int = -1) -> None:
        """Insert new steps and select the first one."""
        self._remember()
        model.insert(self.root, nodes, parent_id, index)
        self.touch()
        if nodes:
            self.select(nodes[0]["id"])

    def add_next_to_selection(self, nodes: list[dict]) -> None:
        """Insert steps inside the selected loop/group, or right after the selected step."""
        node, parent = model.find(self.root, self._selected) if self._selected else (None, None)
        if node is not None and model.is_container(node) and node is not self.root:
            self.add(nodes, node["id"])
        elif node is not None and parent is not None:
            siblings = model.children_of(parent)
            self.add(nodes, parent["id"], siblings.index(node) + 1)
        else:
            self.add(nodes)

    def update(self, node_id: str, **fields) -> None:
        """Change fields of a node."""
        node = self.node(node_id)
        if node is None:
            return
        self._remember()
        for key, value in fields.items():
            if value is None and key in ("bind_status",):
                node.pop(key, None)
            else:
                node[key] = value
        self.touch()

    def delete(self, node_id: str) -> None:
        """Remove a step; a "while moving" loop also removes the move it watches."""
        node = self.node(node_id)
        if node is None or node is self.root:
            return
        self._remember()
        status = model.while_status(node) if node.get("type") == "while" else None
        model.remove(self.root, node_id)
        if status:
            owner = model.status_owner(self.root, status)
            if owner is not None:
                model.remove(self.root, owner["id"])
        self._selected = ""
        self.touch()
        self.selection_changed.emit("")

    def move(self, node_id: str, parent_id: str | None, index: int) -> None:
        """Move a step to another position (index counted after removal)."""
        node = self.node(node_id)
        if node is None or node is self.root:
            return
        if parent_id and any(a.get("id") == node_id for a in model.ancestors(self.root, parent_id)):
            return
        if parent_id == node_id:
            return
        self._remember()
        model.remove(self.root, node_id)
        model.insert(self.root, [node], parent_id, index)
        self.touch()

    def shift(self, node_id: str, offset: int) -> None:
        """Move a step up or down among its siblings."""
        node, parent = model.find(self.root, node_id)
        if node is None or parent is None:
            return
        siblings = model.children_of(parent)
        index = siblings.index(node) + offset
        if 0 <= index < len(siblings):
            self._remember()
            siblings.remove(node)
            siblings.insert(index, node)
            self.touch()

    def duplicate(self, node_id: str) -> None:
        """Insert a copy right after a step."""
        node, parent = model.find(self.root, node_id)
        if node is None or parent is None:
            return
        siblings = model.children_of(parent)
        self.add([model.clone(node)], parent["id"], siblings.index(node) + 1)

    def wrap(self, node_id: str, kind: str) -> None:
        """Put a step inside a new repeat or for-each loop."""
        node, parent = model.find(self.root, node_id)
        if node is None or parent is None:
            return
        self._remember()
        siblings = model.children_of(parent)
        index = siblings.index(node)
        loop = model.new_step(kind)[0]
        siblings[index] = loop
        model.children_of(loop).append(node)
        self.touch()
        self.select(loop["id"])

    def undo(self) -> None:
        """Restore the previous version."""
        if self._undo:
            self._doc = self._undo.pop()
            self._selected = ""
            self.touch()
            self.selection_changed.emit("")

    def can_undo(self) -> bool:
        """Return whether there is something to undo."""
        return bool(self._undo)

    def _remember(self) -> None:
        self._undo.append(copy.deepcopy(self._doc))
        del self._undo[:-50]
