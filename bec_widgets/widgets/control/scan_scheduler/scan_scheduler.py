"""Compose JSON sequences, inspect exports and submit through BEC procedures."""

from __future__ import annotations

import json

# Qt signal descriptors are not understood by pylint.
# pylint: disable=no-member
from pathlib import Path

from bec_lib.scan_sequencer import (
    BECAdapter,
    DefinitionLibrary,
    ScanCatalog,
    Schedule,
    Sequencer,
    available_components,
)
from bec_qthemes import material_icon
from qtpy.QtCore import QSignalBlocker, Qt, QTimer
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import BECWidget, SafeSlot

from .document import SequenceDraft
from .inspector import ComponentInspector
from .presentation import LABELS, StepDelegate, step_title


class ScanScheduler(BECWidget, QWidget):
    """Edit nested components and execute validated sequences through procedures.

    Description, Python and JSON representations share the backend's resolver. Execution
    uses the existing run_sequence procedure without keeping submission records.

    Args:
        parent (QWidget | None): Owning widget.
        **kwargs (object): BECWidget connection and configuration arguments.
    """

    PLUGIN = True
    ICON_NAME = "account_tree"
    USER_ACCESS = ["load_json", "document_json", "validate_sequence", "execute_sequence"]

    def __init__(self, parent=None, **kwargs) -> None:
        super().__init__(parent=parent, **kwargs)
        self.draft = SequenceDraft()
        self.schema = available_components()
        self.catalog = ScanCatalog.from_client(self.client)
        self._path = ()
        self._busy = False
        self._closed = False
        self._result = {}
        self.exports = None
        self.description = None
        self.python = None
        self.json = None
        self.definitions = None
        self.title = None
        self.tree = None
        self.apply_json_button = None
        self._build_ui()
        self.edit_timer = QTimer(self)
        self.edit_timer.setSingleShot(True)
        self.edit_timer.setInterval(250)
        self.edit_timer.timeout.connect(self._apply)
        self.inspector.changed.connect(self.edit_timer.start)
        self.title.editingFinished.connect(self.edit_timer.start)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(250)
        self.render_timer.timeout.connect(self.validate_sequence)
        self._rebuild_tree()

    def _button(self, text, slot, layout):
        button = QPushButton(text, self)
        button.clicked.connect(slot)
        layout.addWidget(button)
        return button

    def _build_ui(self) -> None:
        self.setObjectName("scanScheduler")
        self.setStyleSheet("""
            QWidget#scanScheduler { background: palette(base); }
            QWidget#sequenceOutline { background: palette(alternate-base); border-radius: 5px; }
            QLabel#sectionHeading, QLabel#brand { font-weight: 600; }
            QLabel#stepHeading { font-size: 16px; font-weight: 600; margin-top: 12px; }
            QLabel#breadcrumb { color: palette(placeholder-text); font-size: 11px; }
            QLabel#scopeChip { background: palette(alternate-base); padding: 8px; border-radius: 4px; }
            QTreeWidget { background: transparent; border: none; }
            QLineEdit, QComboBox, QSpinBox { min-height: 24px; }
            QLineEdit { padding-left: 7px; }
            QPushButton#primary { background: palette(highlight); color: palette(highlighted-text); padding: 7px 16px; }
            QTabWidget::pane { border: 1px solid palette(midlight); }
            QTabBar { qproperty-expanding: false; }
            QTabBar::tab { min-width: 80px; padding: 8px 12px; margin-right: 5px; }
            QTreeWidget::item:selected, QTreeWidget::branch:selected { background: transparent; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        brand = QLabel("BEC   Scan scheduler", self)
        brand.setObjectName("brand")
        layout.addWidget(brand)
        self.editor = QWidget(self)
        layout.addWidget(self.editor)
        editor_layout = QVBoxLayout(self.editor)
        editor_layout.setContentsMargins(0, 12, 0, 0)
        self._build_toolbar(editor_layout)
        splitter = QSplitter(self)
        splitter.setChildrenCollapsible(False)
        editor_layout.addWidget(splitter, 1)
        self._build_outline(splitter)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self.inspector = ComponentInspector(self, client=self.client)
        scroll.setWidget(self.inspector)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([380, 760])
        self._build_exports(editor_layout)
        self.message = QLabel("Compose steps and execute the validated sequence.", self)
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.PlainText)
        self.message.setObjectName("breadcrumb")
        layout.addWidget(self.message)

    def _build_toolbar(self, editor_layout):
        toolbar = QHBoxLayout()
        self.title = QLineEdit(self.draft.document["id"], self)
        self.title.setPlaceholderText("Sequence name")
        toolbar.addWidget(self.title, 1)
        toolbar.addWidget(QLabel("Draft", self))
        options = QMenu(self)
        for text, slot in (
            ("New sequence", self._new),
            ("Open sequence…", self._open),
            ("Save sequence…", self._save),
            ("Reusable definitions…", self._definitions_dialog),
        ):
            options.addAction(text, slot)
        more = QPushButton("Sequence options  ⋯", self)
        more.setMenu(options)
        toolbar.addWidget(more)
        editor_layout.addLayout(toolbar)

    def _build_outline(self, splitter):
        outline = QWidget(self)
        outline.setObjectName("sequenceOutline")
        outline_layout = QVBoxLayout(outline)
        outline_layout.setContentsMargins(10, 12, 6, 10)
        actions = QHBoxLayout()
        heading = QLabel("Sequence", self)
        heading.setObjectName("sectionHeading")
        actions.addWidget(heading)
        actions.addStretch()
        self.palette = QComboBox(self)
        self.palette.addItems(list(self.schema["discriminator"]["mapping"]))
        self.palette.hide()
        add_menu = QMenu(self)
        for kind in self.schema["discriminator"]["mapping"]:
            add_menu.addAction(
                LABELS[kind], lambda _checked=False, kind=kind: self._choose_add(kind)
            )
        add = QPushButton("+ Add step", self)
        add.setMenu(add_menu)
        actions.addWidget(add)
        outline_layout.addLayout(actions)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setItemDelegate(StepDelegate(self.tree))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._step_menu)
        self.tree.currentItemChanged.connect(self._selected)
        outline_layout.addWidget(self.tree)
        hint = QLabel("Groups run in order. Repeats apply to their children.", self)
        hint.setWordWrap(True)
        hint.setObjectName("breadcrumb")
        outline_layout.addWidget(hint)
        splitter.addWidget(outline)

    def _build_exports(self, editor_layout):
        self.exports = QTabWidget(self)
        self.exports.tabBar().setExpanding(False)
        self.exports.setMaximumHeight(210)
        self.description = self._text_tab(self.exports, "Description", readonly=True)
        self.python = self._text_tab(self.exports, "Python", readonly=True)
        self.json = self._text_tab(self.exports, "JSON", readonly=False)
        self.definitions = QPlainTextEdit(self)
        self.definitions.setPlainText("[]")
        self.definitions.hide()
        editor_layout.addWidget(self.exports)
        footer = QHBoxLayout()
        self.apply_json_button = self._button("Apply JSON edits", self._apply_json, footer)
        self.apply_json_button.hide()
        self.exports.currentChanged.connect(
            lambda index: self.apply_json_button.setVisible(index == 2)
        )
        footer.addStretch()
        execute = self._button("Execute", self.execute_sequence, footer)
        execute.setObjectName("primary")
        editor_layout.addLayout(footer)

    def _choose_add(self, kind):
        self.palette.setCurrentText(kind)
        self._add()

    @SafeSlot(object)
    def _step_menu(self, point):
        item = self.tree.itemAt(point)
        if item is None:
            return
        self.tree.setCurrentItem(item)
        menu = QMenu(self)
        add = menu.addMenu("Add step")
        for kind in self.schema["discriminator"]["mapping"]:
            add.addAction(LABELS[kind], lambda _checked=False, kind=kind: self._choose_add(kind))
        wrap = menu.addMenu("Wrap in")
        for kind in ("sequence", "repeat", "for_each", "while"):

            def wrap_step(_checked=False, kind=kind):
                self.palette.setCurrentText(kind)
                self._wrap()

            wrap.addAction(LABELS[kind], wrap_step)
        menu.addSeparator()
        menu.addAction("Move up", lambda: self._move(-1))
        menu.addAction("Move down", lambda: self._move(1))
        menu.addAction("Remove step", self._remove)
        menu.exec(self.tree.viewport().mapToGlobal(point))

    @SafeSlot()
    def _definitions_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Reusable definitions")
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Versioned component definitions (JSON list)", dialog))
        text = QPlainTextEdit(self.definitions.toPlainText(), dialog)
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            self.definitions.setPlainText(text.toPlainText())
            self._sync_json()
        dialog.deleteLater()

    def _text_tab(self, tabs, title, readonly):
        text = QPlainTextEdit(self)
        text.setReadOnly(readonly)
        tabs.addTab(text, title)
        return text

    def _schema(self, kind):
        ref = self.schema["discriminator"]["mapping"][kind].rsplit("/", 1)[-1]
        return self.schema["$defs"][ref]

    def _show_inspector(self):
        node = self.draft.node(self._path)
        self.inspector.display(
            node,
            self._schema(node["type"]),
            self.draft.variables(self._path),
            self.catalog.entries,
            sorted(self.client.device_manager.devices),
            self._breadcrumb(),
        )

    def _breadcrumb(self):
        titles = [self.title.text().replace("_", " ")]
        for length in range(len(self._path) + 1):
            node = self.draft.node(self._path[:length])
            if isinstance(node, dict) and node.get("type") != "sequence":
                titles.append(step_title(node))
        return " / ".join(titles)

    def _rebuild_tree(self, selected=()):
        if hasattr(self, "edit_timer"):
            self.edit_timer.stop()
        blocker = QSignalBlocker(self.tree)
        self.tree.clear()
        target = None

        def add(node, path, parent):
            nonlocal target
            kind = node["type"]
            detail = {
                "repeat": f"Repeat whole group ×{node.get('count')}",
                "for_each": f"For each ${node.get('variable')} · {len(node.get('values', []))} values",
                "set": f"Set {node.get('device')}"
                + (" and wait" if node.get("wait") else " asynchronously"),
                "scan_call": node.get("name", "").replace("_", " "),
                "while": "Check before each iteration",
                "sequence": "Children execute in order",
                "component_call": str(node.get("definition", "")),
            }[kind]
            item = QTreeWidgetItem(parent, [step_title(node), detail])
            item.setIcon(
                0,
                material_icon(
                    {
                        "sequence": "account_tree",
                        "repeat": "repeat",
                        "for_each": "format_list_bulleted",
                        "while": "sync",
                        "set": "tune",
                        "scan_call": "filter_center_focus",
                        "component_call": "extension",
                    }[kind]
                ),
            )
            item.setData(0, Qt.UserRole + 1, detail)
            item.setData(0, Qt.UserRole, path)
            if path == selected:
                target = item
            for index, child in enumerate(node.get("children", [])):
                add(child, path + ("children", index), item)
            if "body" in node:
                body = node["body"]
                if body["type"] == "sequence":
                    for index, child in enumerate(body["children"]):
                        add(child, path + ("body", "children", index), item)
                else:
                    add(body, path + ("body",), item)

        root = self.draft.document["root"]
        if root["type"] == "sequence" and root["children"]:
            for index, child in enumerate(root["children"]):
                add(child, ("children", index), self.tree)
        else:
            add(root, (), self.tree)
        self.tree.expandAll()
        self.tree.setCurrentItem(target or self.tree.topLevelItem(0))
        self._path = tuple(self.tree.currentItem().data(0, Qt.UserRole))
        del blocker
        self._show_inspector()
        self.tree.setColumnHidden(1, True)
        self.tree.header().setStretchLastSection(True)
        self._sync_json()

    def _sync_json(self):
        self.json.setPlainText(json.dumps(self.draft.document, indent=2, ensure_ascii=False))
        self.description.clear()
        self.python.clear()
        self.message.setText("Sequence changed.")
        if hasattr(self, "render_timer"):
            self.render_timer.start()

    def _commit(self):
        node = self.inspector.values()
        changed = (
            node != self.draft.node(self._path) or self.draft.document["id"] != self.title.text()
        )
        self.draft.replace(self._path, node)
        self.draft.document["id"] = self.title.text()
        return changed

    @SafeSlot(object, object)
    def _selected(self, current, previous):
        if current is None:
            return
        try:
            changed = self._commit()
        except (ValueError, TypeError) as exc:
            blocker = QSignalBlocker(self.tree)
            self.tree.setCurrentItem(previous)
            del blocker
            self.message.setText(f"Step not applied: {exc}")
            return
        self._path = tuple(current.data(0, Qt.UserRole))
        self._show_inspector()
        if changed:
            self._sync_json()

    @SafeSlot()
    def _apply(self):
        if not self._busy and not self._closed:
            self._edit(lambda: self._path)

    def _edit(self, action):
        try:
            self._commit()
            selected = action()
            self._rebuild_tree(selected or ())
        except (ValueError, TypeError, KeyError) as exc:
            self.message.setText(str(exc))

    @SafeSlot()
    def _add(self):
        self._edit(lambda: self.draft.add(self._path, self.palette.currentText()))

    @SafeSlot()
    def _wrap(self):
        def wrap():
            self.draft.wrap(self._path, self.palette.currentText())
            return self._path

        self._edit(wrap)

    @SafeSlot()
    def _remove(self):
        self._edit(lambda: self.draft.remove(self._path))

    def _move(self, offset):
        self._edit(lambda: self.draft.move(self._path, offset))

    @SafeSlot()
    def _new(self):
        self.draft = SequenceDraft()
        self.title.setText(self.draft.document["id"])
        self._rebuild_tree()

    def load_json(self, document: str, definitions: str = "[]") -> None:
        """Load a structurally valid document and reusable definitions into the editor.

        Args:
            document (str): Sequence document JSON.
            definitions (str): JSON list of reusable definitions. Defaults to an empty library.
        """
        if self._busy:
            raise RuntimeError("Wait for the current validation or execution to finish.")
        schedule = Schedule.model_validate_json(document)
        DefinitionLibrary(json.loads(definitions))
        self.draft = SequenceDraft(schedule.model_dump(mode="json"))
        self.title.setText(schedule.id)
        self.definitions.setPlainText(definitions)
        self._rebuild_tree()

    def document_json(self) -> str:
        """Return the current edited document with structural schema validation.

        Returns:
            str: Authoritative sequence JSON for saving or submission.
        """
        self._commit()
        return self.draft.validated().model_dump_json(indent=2)

    @SafeSlot()
    def _apply_json(self):
        try:
            self.load_json(self.json.toPlainText(), self.definitions.toPlainText())
        except (ValueError, TypeError) as exc:
            self.message.setText(str(exc))

    @SafeSlot()
    def _open(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open sequence", filter="JSON (*.json)")
        if filename:
            try:
                self.load_json(
                    Path(filename).read_text(encoding="utf-8"), self.definitions.toPlainText()
                )
            except (OSError, ValueError) as exc:
                self.message.setText(str(exc))

    @SafeSlot()
    def _save(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save sequence", filter="JSON (*.json)")
        if filename:
            try:
                Path(filename).write_text(self.document_json(), encoding="utf-8")
            except (OSError, ValueError) as exc:
                self.message.setText(str(exc))

    @SafeSlot()
    def validate_sequence(self) -> None:
        """Validate the entire draft and refresh all exports on a background task."""
        self._start(False)

    @SafeSlot()
    def execute_sequence(self) -> None:
        """Validate and execute the current sequence through the existing procedure API."""
        self._start(True)

    def _start(self, execute):
        self.edit_timer.stop()
        self.render_timer.stop()
        if self._busy:
            return
        try:
            payload = self.document_json()
            definitions = json.loads(self.definitions.toPlainText())
        except (ValueError, TypeError) as exc:
            self.message.setText(str(exc))
            return
        self.description.clear()
        self.python.clear()
        self.json.setPlainText(payload)
        self._busy = True
        self.editor.setEnabled(False)
        self.message.setText("Validating and executing…" if execute else "Validating…")
        self._result = {}
        client = self.client
        result = self._result

        def prepare():
            catalog = ScanCatalog.from_client(client)
            library = DefinitionLibrary(definitions)
            sequencer = Sequencer(catalog, library)
            sequencer.validate(payload, BECAdapter(client) if execute else None)
            description = sequencer.export(payload, format="description")
            python = sequencer.export(payload, format="python")
            _, closure = library.resolve(Schedule.model_validate_json(payload).root)
            result.update(description=description, python=python, payload=payload)
            if execute:
                client.proc.request_new(
                    "run_sequence",
                    ((payload, [entry.model_dump(mode="json") for entry in closure]), {}),
                )
                result["executed"] = True

        self.submit_task(prepare, on_complete=self._prepared, on_failed=self._failed)

    @SafeSlot()
    def _prepared(self):
        if self._closed:
            return
        self._busy = False
        self.editor.setEnabled(True)
        self.description.setPlainText(self._result["description"])
        self.python.setPlainText(self._result["python"])
        self.json.setPlainText(self._result["payload"])
        self.message.setText(
            "Execution requested through run_sequence."
            if self._result.get("executed")
            else "Sequence valid."
        )

    @SafeSlot(str)
    def _failed(self, error):
        if self._closed:
            return
        self._busy = False
        self.editor.setEnabled(True)
        self.message.setText(error.strip().splitlines()[-1])
        self.message.setToolTip(error)

    def cleanup(self) -> None:
        """Stop pending edits and disconnect widget resources."""
        self._closed = True
        if hasattr(self, "edit_timer"):
            self.edit_timer.stop()
        if hasattr(self, "render_timer"):
            self.render_timer.stop()
        if hasattr(self, "inspector"):
            self.inspector.cleanup()
        super().cleanup()
