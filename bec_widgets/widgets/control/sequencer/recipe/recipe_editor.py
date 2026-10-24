"""Concept 1, Recipe: a numbered list of plain-language steps with a details panel.

Reads like a lab protocol. Loops are steps that hold indented steps; drag to reorder or to
move steps into a loop. The panel on the right edits the selected step.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtGui import QBrush, QColor, QFontMetrics, QKeySequence, QShortcut
from qtpy.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import rgba
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.editor_base import SequenceEditorBase
from bec_widgets.widgets.control.sequencer.inspector import StepInspector
from bec_widgets.widgets.control.sequencer.style import (
    empty_state,
    heading,
    hint,
    kind_color,
    kind_icon,
    theme,
)

ID_ROLE = Qt.ItemDataRole.UserRole + 1

ADD_BUTTONS = [
    ("set", "Move"),
    ("scan_call", "Scan"),
    ("repeat", "Repeat"),
    ("for_each", "For each value"),
    ("while", "While moving"),
]
PROBLEM_WIDTH = 260


class RecipeTree(QTreeWidget):
    """Tree whose drag and drop moves steps in the document."""

    def __init__(self, editor: "RecipeEditor"):
        super().__init__(editor)
        self.editor = editor
        self.setHeaderHidden(True)
        self.setColumnCount(2)
        self.setIndentation(26)
        self.setUniformRowHeights(False)
        self.setRootIsDecorated(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAnimated(True)
        self.setExpandsOnDoubleClick(False)

    def dropEvent(self, event):  # pylint: disable=invalid-name
        """Translate a drop into a document move."""
        source = self.currentItem()
        if source is None:
            event.ignore()
            return
        node_id = source.data(0, ID_ROLE)
        target = self.itemAt(event.position().toPoint())
        indicator = self.dropIndicatorPosition()
        doc = self.editor.document
        if target is None or indicator == QAbstractItemView.DropIndicatorPosition.OnViewport:
            parent_id, index = None, -1
        else:
            target_id = target.data(0, ID_ROLE)
            target_node, target_parent = model.find(doc.root, target_id)
            if indicator == QAbstractItemView.DropIndicatorPosition.OnItem and model.is_container(
                target_node
            ):
                parent_id, index = target_id, -1
            else:
                siblings = model.children_of(target_parent)
                index = siblings.index(target_node)
                if indicator in (
                    QAbstractItemView.DropIndicatorPosition.BelowItem,
                    QAbstractItemView.DropIndicatorPosition.OnItem,
                ):
                    index += 1
                source_node, source_parent = model.find(doc.root, node_id)
                if source_parent is target_parent and siblings.index(source_node) < index:
                    index -= 1
                parent_id = target_parent["id"]
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        doc.move(node_id, parent_id, index)


class RecipeEditor(SequenceEditorBase):
    """Numbered recipe of plain-language steps, with a details panel."""

    CONCEPT_ID = "recipe"
    CONCEPT_TITLE = "Recipe"
    CONCEPT_TAGLINE = "A numbered list of plain-language steps, like a lab protocol."

    def build_editor(self, host: QWidget) -> None:
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, host)
        layout.addWidget(splitter)

        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 14, 8, 8)
        left_layout.setSpacing(10)
        left_layout.addWidget(heading("Sequence steps", left))
        left_layout.addWidget(
            hint("Steps run from top to bottom. Indented steps belong to the loop above.", left)
        )

        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        for kind, text in ADD_BUTTONS:
            btn = QPushButton(f"{text}", left)
            btn.setIcon(kind_icon(kind, 16))
            btn.setToolTip(f"Add a “{model.KIND_TITLES[kind]}” step after the selected one")
            btn.clicked.connect(lambda _=False, k=kind: self.add_step(k))
            add_row.addWidget(btn)
        add_row.addStretch(1)
        left_layout.addLayout(add_row)

        self.stack = QStackedWidget(left)
        self.empty = empty_state(
            "No steps yet",
            "Add a move, a scan or a loop with the buttons above. Steps run from top to bottom.",
            self.stack,
        )
        self.stack.addWidget(self.empty)
        self.tree = RecipeTree(self)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.stack.addWidget(self.tree)
        left_layout.addWidget(self.stack, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(2)
        self.action_buttons = {}
        for key, icon, tip in (
            ("up", "arrow_upward", "Move up"),
            ("down", "arrow_downward", "Move down"),
            ("duplicate", "content_copy", "Duplicate"),
            ("wrap_repeat", "repeat", "Put inside a Repeat loop"),
            ("wrap_each", "format_list_numbered", "Put inside a For each loop"),
            ("delete", "delete", "Delete step"),
            ("undo", "undo", "Undo"),
        ):
            btn = QToolButton(left)
            btn.setIcon(material_icon(icon, size=(18, 18), convert_to_pixmap=False))
            btn.setToolTip(tip)
            btn.setAutoRaise(True)
            btn.clicked.connect(lambda _=False, k=key: self._action(k))
            action_row.addWidget(btn)
            self.action_buttons[key] = btn
        action_row.addStretch(1)
        left_layout.addLayout(action_row)
        for keys, key in (
            (QKeySequence.StandardKey.Delete, "delete"),
            (QKeySequence.StandardKey.Undo, "undo"),
            (QKeySequence("Ctrl+D"), "duplicate"),
        ):
            shortcut = QShortcut(QKeySequence(keys), self.tree)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(lambda k=key: self._action(k))

        self.inspector = StepInspector(self.document, self.backend, splitter, client=self.client)
        self.inspector.setMinimumWidth(340)
        splitter.addWidget(left)
        splitter.addWidget(self.inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.document.selection_changed.connect(self._select_in_tree)
        self.document.selection_changed.connect(self._update_actions)
        self._style_tree()

    def _style_tree(self) -> None:
        border = theme("BORDER", "#d0d0d0").name()
        primary = theme("PRIMARY", "#2f6fdf")
        self.tree.setStyleSheet(
            f"QTreeWidget {{ border: 1px solid {border}; border-radius: 8px; padding: 4px;"
            f" background: {theme('CARD_BG', '#ffffff').name()}; }}"
            "QTreeWidget { show-decoration-selected: 0; }"
            "QTreeWidget::item { padding: 7px 4px; border-radius: 6px; }"
            f"QTreeWidget::item:selected {{ background: {rgba(primary, 50)};"
            " color: palette(text); }"
        )

    # --- drawing ---------------------------------------------------------------------------
    @SafeSlot()
    def refresh(self) -> None:
        if not hasattr(self, "tree"):
            return
        entries = self.scan_entries()
        self.tree.blockSignals(True)
        self.tree.clear()
        root = self.document.root

        def add(node: dict, parent_item, number: str):
            text = model.sentence(node, root, entries)
            item = QTreeWidgetItem([f"{number}   {text}", self._side_text(node)])
            item.setData(0, ID_ROLE, node["id"])
            item.setIcon(0, kind_icon(node["type"], 18))
            flags = item.flags() | Qt.ItemFlag.ItemIsDragEnabled
            if model.is_container(node):
                flags |= Qt.ItemFlag.ItemIsDropEnabled
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            else:
                flags &= ~Qt.ItemFlag.ItemIsDropEnabled
            item.setFlags(flags)
            item.setForeground(1, QBrush(kind_color(node["type"])))
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if parent_item is None:
                self.tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            for index, child in enumerate(model.children_of(node), 1):
                add(child, item, f"{number}{index}.")
            if model.is_container(node) and not model.children_of(node):
                empty = QTreeWidgetItem(["Drop or add steps here"])
                empty.setFlags(Qt.ItemFlag.ItemIsEnabled)
                empty.setForeground(0, QBrush(theme("DISABLED_FG", "#999999")))
                font = empty.font(0)
                font.setItalic(True)
                empty.setFont(0, font)
                item.addChild(empty)
            item.setExpanded(True)

        for index, child in enumerate(model.children_of(root), 1):
            add(child, None, f"{index}.")
        self.stack.setCurrentWidget(self.tree if model.children_of(root) else self.empty)
        self.tree.setColumnWidth(1, PROBLEM_WIDTH)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        self.tree.blockSignals(False)
        self._select_in_tree(self.document.selected)
        self.show_problems(self.problems)
        self._update_actions()

    @staticmethod
    def _side_text(node: dict) -> str:
        kind = node["type"]
        if kind == "repeat":
            return f"× {node.get('count', 1)}"
        if kind == "for_each":
            values = node.get("values")
            return f"{len(values)} values" if isinstance(values, list) else ""
        if kind == "while":
            return "until it arrives"
        if kind == "set":
            return "waits" if node.get("wait", True) else "keeps going"
        if kind == "scan_call":
            metadata = (node.get("arguments") or {}).get("metadata") or {}
            return str(metadata.get("sample_name", ""))
        return ""

    def show_problems(self, problems) -> None:
        bad = {p.node_id: p.message for p in problems}
        red = theme("ACCENT_EMERGENCY", "#e0534b")
        iterator = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while iterator:
            item = iterator.pop()
            iterator.extend(item.child(i) for i in range(item.childCount()))
            node_id = item.data(0, ID_ROLE)
            if node_id in bad:
                item.setBackground(0, QBrush(QColor(red.red(), red.green(), red.blue(), 45)))
                item.setToolTip(0, bad[node_id])
                item.setToolTip(1, bad[node_id])
                metrics = QFontMetrics(item.font(1))
                item.setText(
                    1,
                    metrics.elidedText(
                        bad[node_id], Qt.TextElideMode.ElideRight, PROBLEM_WIDTH - 16
                    ),
                )
                item.setForeground(1, QBrush(red))
            elif node_id:
                node = self.document.node(node_id)
                item.setBackground(0, QBrush())
                item.setToolTip(0, "")
                item.setToolTip(1, "")
                if node is not None:
                    item.setText(1, self._side_text(node))
                    item.setForeground(1, QBrush(kind_color(node["type"])))

    # --- interaction -----------------------------------------------------------------------
    def add_step(self, kind: str) -> None:
        """Add a new step next to the selection (inside it when a loop is selected)."""
        self.document.add_next_to_selection(self.document.new_nodes(kind))

    @SafeSlot()
    @SafeSlot(str)
    def _update_actions(self, *_args) -> None:
        selected = bool(self.document.selected)
        for key, button in self.action_buttons.items():
            button.setEnabled(self.document.can_undo() if key == "undo" else selected)

    @SafeSlot()
    def _on_tree_selection(self) -> None:
        item = self.tree.currentItem()
        node_id = item.data(0, ID_ROLE) if item is not None else ""
        if node_id:
            self.document.select(node_id)

    @SafeSlot(str)
    def _select_in_tree(self, node_id: str) -> None:
        iterator = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while iterator:
            item = iterator.pop(0)
            if item.data(0, ID_ROLE) == node_id:
                self.tree.blockSignals(True)
                self.tree.setCurrentItem(item)
                self.tree.blockSignals(False)
                return
            iterator.extend(item.child(i) for i in range(item.childCount()))

    def _action(self, key: str) -> None:
        doc = self.document
        if key == "undo":
            doc.undo()
            return
        node_id = doc.selected
        if not node_id:
            return
        if key == "up":
            doc.shift(node_id, -1)
        elif key == "down":
            doc.shift(node_id, 1)
        elif key == "duplicate":
            doc.duplicate(node_id)
        elif key == "wrap_repeat":
            doc.wrap(node_id, "repeat")
        elif key == "wrap_each":
            doc.wrap(node_id, "for_each")
        elif key == "delete":
            doc.delete(node_id)
