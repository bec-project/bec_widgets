"""Editable sequence trees owned by the scheduler interface."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from bec_lib.scan_sequencer.components import Schedule


def component(kind: str) -> dict:
    """Create an editable component with a unique identity.

    Args:
        kind (str): Backend component discriminator.

    Returns:
        dict: Component template. Scan and device targets require user selection.
    """
    node = {"id": f"{kind}_{uuid4().hex[:12]}", "type": kind}
    if kind == "sequence":
        node["children"] = []
    elif kind in {"repeat", "for_each", "while"}:
        node["body"] = component("sequence")
        node.update(
            {
                "repeat": {"count": 1},
                "for_each": {"variable": "value", "values": []},
                "while": {"condition": False},
            }[kind]
        )
    elif kind == "set":
        node.update(device="", value=0, wait=True, bind_status=None)
    elif kind == "scan_call":
        node.update(name="", positional=[], arguments={})
    elif kind == "component_call":
        node.update(definition={"id": "", "version": 1}, arguments={})
    else:
        raise ValueError(f"Unknown component: {kind}")
    return node


class SequenceDraft:
    """Hold an editable tree independently of submitted procedure payloads.

    Args:
        document (dict | None): Initial sequence document or a new empty sequence.
    """

    def __init__(self, document: dict | None = None) -> None:
        self.document = (
            deepcopy(document)
            if document is not None
            else {
                "schema_version": 1,
                "type": "sequence",
                "id": "new_sequence",
                "revision": 1,
                "root": component("sequence"),
            }
        )

    def node(self, path: tuple) -> dict:
        """Look up a component by its structural path.

        Args:
            path (tuple): Keys and child indices relative to the root.

        Returns:
            dict: Mutable component in this draft.
        """
        value = self.document["root"]
        for key in path:
            value = value[key]
        return value

    def replace(self, path: tuple, node: dict) -> None:
        """Replace one component.

        Args:
            path (tuple): Component path.
            node (dict): Replacement component.
        """
        if not path:
            self.document["root"] = node
        else:
            parent = self.node(path[:-1])
            parent[path[-1]] = node

    def add(self, path: tuple, kind: str) -> tuple:
        """Append inside a sequence or loop; insert after a selected sequence child.

        Args:
            path (tuple): Selected component path.
            kind (str): Component type to insert.

        Returns:
            tuple: Inserted component's path.
        """
        node = self.node(path)
        if "body" in node:
            if node["body"]["type"] != "sequence":
                wrapper = component("sequence")
                wrapper["children"] = [node["body"]]
                node["body"] = wrapper
            path += ("body",)
            node = node["body"]
        if node["type"] == "sequence":
            index = len(node["children"])
            node["children"].append(component(kind))
            return path + ("children", index)
        if len(path) >= 2 and path[-2] == "children":
            index = path[-1] + 1
            self.node(path[:-2])["children"].insert(index, component(kind))
            return path[:-1] + (index,)
        raise ValueError("Select a sequence, or wrap this step in a sequence first.")

    def wrap(self, path: tuple, kind: str) -> None:
        """Wrap the selected component in a sequence or loop.

        Args:
            path (tuple): Selected component path.
            kind (str): Sequence, repeat, for_each or while.
        """
        if kind not in {"sequence", "repeat", "for_each", "while"}:
            raise ValueError("Only a sequence or loop can wrap a step.")
        wrapper = component(kind)
        if kind == "sequence":
            wrapper["children"] = [self.node(path)]
        else:
            wrapper["body"] = self.node(path)
        self.replace(path, wrapper)

    def remove(self, path: tuple) -> None:
        """Remove a child, replacing a required root or body with an empty sequence.

        Args:
            path (tuple): Selected component path.
        """
        if len(path) >= 2 and path[-2] == "children":
            self.node(path[:-2])["children"].pop(path[-1])
        else:
            self.replace(path, component("sequence"))

    def move(self, path: tuple, offset: int) -> tuple:
        """Move a component amongst its sequence siblings.

        Args:
            path (tuple): Selected child path.
            offset (int): Relative sibling position.

        Returns:
            tuple: New component path.
        """
        if len(path) < 2 or path[-2] != "children":
            return path
        children = self.node(path[:-2])["children"]
        target = path[-1] + offset
        if 0 <= target < len(children):
            children.insert(target, children.pop(path[-1]))
            return path[:-1] + (target,)
        return path

    def validated(self) -> Schedule:
        """Validate the document's structural schema.

        Returns:
            Schedule: Typed document; semantic validation is performed by the sequencer.
        """
        return Schedule.model_validate(self.document)

    def variables(self, path: tuple) -> list[str]:
        """Return visible loop variables, with inner bindings shadowing outer ones.

        Args:
            path (tuple): Selected component path.

        Returns:
            list[str]: Names visible inside enclosing for_each bodies.
        """
        names = []
        for length, part in enumerate(path):
            if part == "body":
                ancestor = self.node(path[:length])
                if ancestor["type"] == "for_each":
                    name = ancestor["variable"]
                    if name in names:
                        names.remove(name)
                    names.append(name)
        return names
