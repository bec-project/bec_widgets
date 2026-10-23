"""Bottom bar shared by all concepts: what will happen, is it valid, preview, save, run."""

from __future__ import annotations

import json
import time
from pathlib import Path

from bec_qthemes import material_icon
from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.backend import Problem, SequencerBackend
from bec_widgets.widgets.control.sequencer.document import SequenceDocument
from bec_widgets.widgets.control.sequencer.style import Chip, kind_color, kind_icon, theme


class PreviewDialog(QDialog):
    """Show a sequence step by step, as the backend describes it, and as Python."""

    def __init__(self, backend: SequencerBackend, doc: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Preview sequence")
        self.resize(720, 520)
        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        layout.addWidget(tabs)

        steps = QListWidget(tabs)
        entries = backend.scan_entries()
        for index, item in enumerate(model.timeline(doc["root"], entries), 1):
            row = QListWidgetItem(kind_icon(item.kind, 16), f"{index:>3}.  {item.text}")
            if item.context:
                row.setToolTip(item.context)
                row.setText(f"{row.text()}      ({item.context})")
            steps.addItem(row)
        tabs.addTab(steps, "Step by step")

        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        for title, producer in (("In words", backend.describe), ("Python", backend.python)):
            text = QPlainTextEdit(tabs)
            text.setReadOnly(True)
            text.setFont(mono)
            try:
                text.setPlainText(producer(doc))
            except Exception as exc:  # pylint: disable=broad-except
                text.setPlainText(f"Not available until the problems are fixed:\n{exc}")
            tabs.addTab(text, title)


class RunBar(QWidget):
    """Summary, validation status and the Run/Stop buttons for one document."""

    problems_changed = Signal(list)

    def __init__(
        self, backend: SequencerBackend, document: SequenceDocument, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.backend = backend
        self.document = document
        self._status = None
        self._started = 0.0
        self.problems: list[Problem] = []
        self.setObjectName("SequencerRunBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)
        self.summary = QLabel(self)
        font = self.summary.font()
        font.setBold(True)
        self.summary.setFont(font)
        self.state = Chip("", parent=self)
        self.message = QLabel(self)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.summary)
        layout.addWidget(self.state)
        layout.addWidget(self.message, 1)

        def button(text, icon, tip):
            btn = QPushButton(text, self)
            btn.setIcon(material_icon(icon, size=(18, 18), convert_to_pixmap=False))
            btn.setToolTip(tip)
            layout.addWidget(btn)
            return btn

        self.open_button = button("Open", "folder_open", "Open a saved sequence")
        self.save_button = button("Save", "save", "Save this sequence to a file")
        self.preview_button = button("Preview", "visibility", "See every step that will run")
        self.run_button = button("Run sequence", "play_arrow", "Start the sequence")
        self.run_button.setProperty("variant", "success")
        self.stop_button = button("Stop", "stop", "Stop the running sequence")
        self.stop_button.setProperty("variant", "danger")
        self.stop_button.setVisible(False)

        self.open_button.clicked.connect(self.open_file)
        self.save_button.clicked.connect(self.save_file)
        self.preview_button.clicked.connect(self.preview)
        self.run_button.clicked.connect(self.run)
        self.stop_button.clicked.connect(self.stop)

        self._check_timer = QTimer(self, singleShot=True, interval=300)
        self._check_timer.timeout.connect(self.check)
        self._poll_timer = QTimer(self, interval=500)
        self._poll_timer.timeout.connect(self._poll)
        document.changed.connect(self._check_timer.start)
        self._apply_style()
        self.check()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"#SequencerRunBar {{ background: {theme('CARD_BG', '#ffffff').name()};"
            f" border-top: 1px solid {theme('BORDER', '#d0d0d0').name()}; }}"
        )

    # --- checking --------------------------------------------------------------------------
    @SafeSlot()
    def check(self) -> None:
        """Count steps and validate with the backend."""
        summary = model.summarize(self.document.root)
        self.summary.setText(summary.text())
        if self._status is not None:
            return
        if not self.backend.available:
            self.problems = []
            self._set_state("Editing only", theme("ACCENT_WARNING", "#eda200"))
            self.message.setText("Install bec with the scan sequencer (bec PR #1128) to run.")
            self.run_button.setEnabled(False)
            self.problems_changed.emit([])
            return
        if not summary.scans and not summary.moves:
            self.problems = []
            self._set_state("Empty", theme("BORDER", "#999999"))
            self.message.setText("Add a step to get started.")
            self.run_button.setEnabled(False)
            self.problems_changed.emit([])
            return
        self.problems = self.backend.validate(self.document.doc)
        if summary.empty_loops and not self.problems:
            self.problems = [Problem(summary.empty_loops[0], "This loop has no steps inside")]
        if self.problems:
            problem = self.problems[0]
            self._set_state("Needs a fix", theme("ACCENT_EMERGENCY", "#e0534b"))
            node = self.document.node(problem.node_id) if problem.node_id else None
            where = f"{model.KIND_TITLES.get(node['type'], 'Step')}: " if node else ""
            self.message.setText(where + problem.message)
        else:
            self._set_state("Ready to run", theme("ACCENT_SUCCESS", "#59a869"))
            self.message.setText("")
        self.run_button.setEnabled(not self.problems)
        self.problems_changed.emit(self.problems)

    def _set_state(self, text: str, color) -> None:
        self.state.setText(text)
        self.state.set_color(color)

    # --- files -----------------------------------------------------------------------------
    @SafeSlot()
    def open_file(self) -> None:
        """Load a sequence JSON file."""
        path, _ = QFileDialog.getOpenFileName(self, "Open sequence", "", "Sequence (*.json)")
        if path:
            self.document.set_document(json.loads(Path(path).read_text(encoding="utf-8")))

    @SafeSlot()
    def save_file(self) -> None:
        """Save the sequence as JSON."""
        name = f"{self.document.doc.get('id', 'sequence')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Save sequence", name, "Sequence (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.document.doc, indent=2), encoding="utf-8")

    @SafeSlot()
    def preview(self) -> None:
        """Open the preview dialog."""
        PreviewDialog(self.backend, self.document.doc, self).exec()

    # --- running ---------------------------------------------------------------------------
    @SafeSlot(popup_error=True)
    def run(self) -> None:
        """Queue the sequence."""
        self.check()
        if self.problems:
            return
        doc = self.document.doc
        doc["revision"] = int(doc.get("revision", 1)) + 1
        self._status = self.backend.submit(doc)
        self._started = time.monotonic()
        self.run_button.setVisible(False)
        self.stop_button.setVisible(True)
        self._set_state("Queued", kind_color("set"))
        self.message.setText("Waiting for the procedure worker…")
        self._poll_timer.start()

    @SafeSlot(popup_error=True)
    def stop(self) -> None:
        """Ask the worker to stop the sequence."""
        if self._status is not None and not self._status.done:
            self._status.cancel()
            self.message.setText("Stopping… (a move that already started may finish first)")

    @SafeSlot()
    def _poll(self) -> None:
        status = self._status
        if status is None:
            self._poll_timer.stop()
            return
        state = status.state.value
        elapsed = int(time.monotonic() - self._started)
        if state in ("Running", "Scheduled", "Requested"):
            label = {"Running": "Running", "Scheduled": "Queued", "Requested": "Queued"}[state]
            self._set_state(label, kind_color("set"))
            self.message.setText(f"{elapsed // 60}:{elapsed % 60:02d} elapsed")
            return
        self._poll_timer.stop()
        self._status = None
        self.run_button.setVisible(True)
        self.stop_button.setVisible(False)
        if state == "Success":
            self._set_state("Finished", theme("ACCENT_SUCCESS", "#59a869"))
            self.message.setText(f"Done after {elapsed // 60}:{elapsed % 60:02d}")
        else:
            self._set_state(
                "Stopped" if "Aborted" in str(status.error) else "Failed",
                theme("ACCENT_EMERGENCY", "#e0534b"),
            )
            self.message.setText(str(status.error or state).splitlines()[-1][:200])

    def cleanup(self) -> None:
        """Stop timers."""
        self._check_timer.stop()
        self._poll_timer.stop()
