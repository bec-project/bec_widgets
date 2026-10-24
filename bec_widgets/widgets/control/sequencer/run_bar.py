"""Bottom bar shared by all concepts: what will happen, is it valid, preview, save, run."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import rgba
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.backend import (
    Problem,
    SequencerBackend,
    run_failure,
    sequences_dir,
)
from bec_widgets.widgets.control.sequencer.checks import check
from bec_widgets.widgets.control.sequencer.document import SequenceDocument
from bec_widgets.widgets.control.sequencer.style import Chip, kind_color, kind_icon, theme

_MOVE_SCANS = ("mv", "umv")


def _mono() -> QFont:
    font = QFont("Menlo")
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def _clock(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


class PreviewDialog(QDialog):
    """Show a sequence step by step, as the backend describes it, and as Python."""

    def __init__(self, backend: SequencerBackend, doc: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Preview sequence")
        self.resize(760, 540)
        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        layout.addWidget(tabs)

        steps = QListWidget(tabs)
        items = model.timeline(doc["root"], backend.scan_entries(), limit=2000)
        for index, item in enumerate(items, 1):
            row = QListWidgetItem(kind_icon(item.kind, 16), f"{index:>4}.  {item.text}")
            if item.context:
                row.setText(f"{row.text()}      ({item.context})")
            steps.addItem(row)
        if len(items) >= 2000:
            steps.addItem("… and more")
        tabs.addTab(steps, "Step by step")

        for title, producer in (("In words", backend.describe), ("Python", backend.python)):
            text = QPlainTextEdit(tabs)
            text.setReadOnly(True)
            text.setFont(_mono())
            try:
                text.setPlainText(producer(doc))
            except Exception as exc:  # pylint: disable=broad-except
                text.setPlainText(f"Not available until the problems are fixed:\n{exc}")
            tabs.addTab(text, title)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class DetailsDialog(QDialog):
    """The full error report of a failed run."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Why the sequence failed")
        self.resize(760, 460)
        layout = QVBoxLayout(self)
        view = QPlainTextEdit(self)
        view.setReadOnly(True)
        view.setFont(_mono())
        view.setPlainText(text)
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class RunBar(QWidget):
    """Summary, check result and the Run/Stop buttons for one document.

    Args:
        backend (SequencerBackend): Checks and runs the sequence.
        document (SequenceDocument): The sequence.
        dispatcher: BEC dispatcher used to follow the scans while the sequence runs.
        parent (QWidget | None): Parent widget.
    """

    problems_changed = Signal(list)
    new_requested = Signal()
    opened = Signal(dict)

    def __init__(
        self,
        backend: SequencerBackend,
        document: SequenceDocument,
        dispatcher=None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.backend = backend
        self.document = document
        self.dispatcher = dispatcher
        self.problems: list[Problem] = []
        self._status = None
        self._started = 0.0
        self._planned = model.Summary()
        self._scans_done = 0
        self._scan_open = False
        self._following = False
        self._error_text = ""
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
        self.message.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.summary)
        layout.addWidget(self.state)
        layout.addWidget(self.message, 1)

        def button(text, icon, tip):
            btn = QPushButton(text, self)
            btn.setIcon(material_icon(icon, size=(18, 18), convert_to_pixmap=False))
            btn.setToolTip(tip)
            layout.addWidget(btn)
            return btn

        self.details_button = button("Details", "description", "Show the full error report")
        self.details_button.setVisible(False)
        self.new_button = button("New", "note_add", "Start a new, empty sequence")
        self.open_button = button("Open", "folder_open", "Open a saved sequence")
        self.save_button = button("Save", "save", "Save this sequence to a file")
        self.preview_button = button("Preview", "visibility", "See every step that will run")
        self.run_button = button("Run sequence", "play_arrow", "Start the sequence")
        self.run_button.setProperty("variant", "success")
        self.stop_button = button("Stop", "stop", "Stop the running sequence")
        self.stop_button.setProperty("variant", "danger")
        self.stop_button.setVisible(False)

        self.details_button.clicked.connect(self.show_details)
        self.new_button.clicked.connect(self.new)
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

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"#SequencerRunBar {{ background: {theme('CARD_BG', '#ffffff').name()};"
            f" border-top: 1px solid {theme('BORDER', '#d0d0d0').name()}; }}"
            # the theme keeps a disabled Run button green, which reads as "ready"
            '#SequencerRunBar QPushButton[variant="success"]:disabled {'
            f" background: transparent; color: {rgba(theme('FG', '#333333'), 110)};"
            f" border: 1px solid {theme('BORDER', '#d0d0d0').name()}; }}"
        )

    @property
    def running(self) -> bool:
        """Whether a sequence from this bar is queued or running."""
        return self._status is not None

    # --- checking --------------------------------------------------------------------------
    @SafeSlot()
    def check(self) -> None:
        """Count steps, find unfinished steps and validate with the backend."""
        summary = model.summarize(self.document.root)
        self.summary.setText(summary.text())
        if self.running:
            return
        self.details_button.setVisible(False)
        if not summary.scans and not summary.moves and not model.children_of(self.document.root):
            self._set_problems([])
            self._set_state("Empty", theme("FG", "#666666"))
            self._say("Add a step to get started.")
            self.run_button.setEnabled(False)
            return
        problems = check(self.document.root, self.backend)
        if not problems:
            problems = self.backend.validate(self.document.doc)
        self._set_problems(problems)
        if problems:
            count = len(problems)
            self._set_state(
                f"{count} step{'s' if count != 1 else ''} to finish",
                theme("ACCENT_WARNING", "#eda200"),
            )
            self._say(self._where(problems[0]) + problems[0].message)
        elif not self.backend.available:
            self._set_state("Editing only", theme("ACCENT_WARNING", "#eda200"))
            self._say("This BEC version cannot run sequences yet.")
        else:
            self._set_state("Ready to run", theme("ACCENT_SUCCESS", "#59a869"))
            self._say("")
        self.run_button.setEnabled(not problems and self.backend.available)

    def _where(self, problem: Problem) -> str:
        node = self.document.node(problem.node_id) if problem.node_id else None
        if node is None or node is self.document.root:
            return ""
        title = model.KIND_TITLES.get(node["type"], "Step")
        if node["type"] == "set" and node.get("bind_status"):
            title = "Start moving"
        return f"{title}: "

    def _say(self, text: str) -> None:
        self.message.setText(text)
        self.message.setToolTip(text)

    def _set_problems(self, problems: list[Problem]) -> None:
        self.problems = problems
        self.problems_changed.emit(problems)

    def _set_state(self, text: str, color) -> None:
        self.state.setText(text)
        self.state.set_color(color)

    # --- files -----------------------------------------------------------------------------
    def _folder(self) -> str:
        folder = sequences_dir(self.backend.client)
        if folder is None:
            return ""
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            return ""
        return str(folder)

    @SafeSlot()
    def new(self) -> None:
        """Ask to start over with an empty sequence."""
        if model.children_of(self.document.root):
            answer = QMessageBox.question(
                self,
                "New sequence",
                "Start a new, empty sequence? Changes that are not saved are lost.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.new_requested.emit()

    @SafeSlot(popup_error=True)
    def open_file(self) -> None:
        """Load a sequence file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open sequence", self._folder(), "Sequence (*.json)"
        )
        if not path:
            return
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("type") != "sequence" or "root" not in doc:
            raise ValueError(f"{Path(path).name} is not a sequence file.")
        self.opened.emit(doc)

    @SafeSlot(popup_error=True)
    def save_file(self) -> None:
        """Save the sequence as JSON; the file name becomes the sequence name."""
        name = f"{self.document.doc.get('id', 'sequence')}.json"
        start = str(Path(self._folder()) / name) if self._folder() else name
        path, _ = QFileDialog.getSaveFileName(self, "Save sequence", start, "Sequence (*.json)")
        if not path:
            return
        path = Path(path).with_suffix(".json")
        self.document.doc["id"] = re.sub(r"\W+", "_", path.stem).strip("_") or "sequence"
        path.write_text(json.dumps(self.document.doc, indent=2), encoding="utf-8")
        self._say(f"Saved as {path.name}")

    @SafeSlot()
    def preview(self) -> None:
        """Open the preview dialog."""
        PreviewDialog(self.backend, self.document.doc, self).exec()

    @SafeSlot()
    def show_details(self) -> None:
        """Show the full error of the last failed run."""
        DetailsDialog(self._error_text, self).exec()

    # --- running ---------------------------------------------------------------------------
    @SafeSlot(popup_error=True)
    def run(self) -> None:
        """Queue the sequence."""
        self.check()
        if self.problems or not self.backend.available:
            return
        doc = self.document.doc
        doc["revision"] = int(doc.get("revision", 1)) + 1
        self._planned = model.summarize(doc["root"])
        self._scans_done = 0
        self._scan_open = False
        self._status = self.backend.submit(doc)
        self._started = time.monotonic()
        self._follow_scans(True)
        self.run_button.setVisible(False)
        self.stop_button.setVisible(True)
        self.stop_button.setEnabled(True)
        self.new_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self._set_state("Queued", kind_color("set"))
        self._say("Waiting for the sequence to start…")
        self._poll_timer.start()

    @SafeSlot(popup_error=True)
    def stop(self) -> None:
        """Ask BEC to stop the sequence; the scan that is running is aborted."""
        if self._status is not None and not self._status.done:
            self._status.cancel()
            self.stop_button.setEnabled(False)
            self._set_state("Stopping", theme("ACCENT_WARNING", "#eda200"))
            self._say("Stopping… a move that already started may still finish.")

    def _follow_scans(self, follow: bool) -> None:
        if self.dispatcher is None or follow == self._following:
            return
        if follow:
            self.dispatcher.connect_slot(self._on_scan_status, MessageEndpoints.scan_status())
        else:
            self.dispatcher.disconnect_slot(self._on_scan_status, MessageEndpoints.scan_status())
        self._following = follow

    @SafeSlot(dict, dict)
    def _on_scan_status(self, content: dict, _metadata: dict) -> None:
        if self._status is None:
            return
        name = (content.get("info") or {}).get("scan_name", "")
        if name in _MOVE_SCANS:
            return
        status = content.get("status")
        if status == "open":
            self._scan_open = True
        elif status == "closed" and self._scan_open:
            self._scan_open = False
            self._scans_done += 1

    def _progress(self) -> str:
        total = self._planned.scans
        current = self._scans_done + (1 if self._scan_open else 0)
        if not total and not self._planned.open_ended:
            return ""
        if self._planned.open_ended:
            return f"scan {max(current, 1)}"
        return f"scan {min(max(current, 1), total)} of {total}"

    @SafeSlot()
    def _poll(self) -> None:
        status = self._status
        if status is None:
            self._poll_timer.stop()
            return
        state = status.state.value
        elapsed = _clock(time.monotonic() - self._started)
        if state in ("Requested", "Scheduled"):
            self._set_state("Queued", kind_color("set"))
            self._say(f"Waiting for the sequence to start… {elapsed}")
            return
        if state == "Running":
            if self.stop_button.isEnabled():
                self._set_state("Running", kind_color("set"))
            progress = self._progress()
            self._say(f"{progress.capitalize()} · {elapsed}" if progress else elapsed)
            return
        self._finish(status, state, elapsed)

    def _finish(self, status, state: str, elapsed: str) -> None:
        self._poll_timer.stop()
        self._follow_scans(False)
        self._status = None
        self.run_button.setVisible(True)
        self.stop_button.setVisible(False)
        self.new_button.setEnabled(True)
        self.open_button.setEnabled(True)
        scans = f"{self._scans_done} scan{'s' if self._scans_done != 1 else ''}"
        if state == "Success":
            self._set_state("Finished", theme("ACCENT_SUCCESS", "#59a869"))
            self._say(f"Done: {scans} in {elapsed}")
            self.run_button.setEnabled(not self.problems)
            return
        error = str(status.error or "")
        if "Aborted by user" in error:
            self._set_state("Stopped", theme("ACCENT_WARNING", "#eda200"))
            where = f"during {self._progress()}" if self._scan_open else f"after {scans}"
            self._say(f"Stopped {where}, {elapsed}")
            self.run_button.setEnabled(not self.problems)
            return
        failure = run_failure(error) if error else Problem("", f"The sequence was {state.lower()}")
        self._error_text = error or failure.message
        self._set_state("Failed", theme("ACCENT_EMERGENCY", "#e0534b"))
        self._say(self._where(failure) + failure.message)
        self.details_button.setVisible(bool(error))
        self.run_button.setEnabled(True)
        if failure.node_id:
            self._set_problems([Problem(failure.node_id, f"Failed here: {failure.message}")])

    def cleanup(self) -> None:
        """Stop timers and listeners."""
        self._check_timer.stop()
        self._poll_timer.stop()
        self._follow_scans(False)
        self.backend.close()
