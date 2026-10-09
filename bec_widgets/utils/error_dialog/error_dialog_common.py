"""Shared model of the error dialog used by its QML and QWidget versions.

The dialog replaces the small ``QMessageBox`` that ``SafeSlot(popup_error=True)``, the global
excepthook and :class:`~bec_widgets.utils.error_popups.ErrorPopupUtility` used to open. Both views
render the same :meth:`ErrorDialogController.view_state` and call the same controller slots, so
they behave identically and can be compared side by side.

What the model adds on top of the plain traceback text:

* the traceback is parsed into exceptions (including ``raise ... from`` and "during handling"
  chains) and frames, shown most recent call first;
* frames from the Python standard library and third party packages are folded into one row, so
  the BEC frames that matter stand out, and the deepest BEC frame is shown as "where it happened"
  with a few lines of source around it;
* errors that arrive while the dialog is open are collected in one list instead of stacking modal
  dialogs, and repeats of the same error are folded into one entry with a counter;
* a plain-text report with the environment (versions, platform) can be copied or turned into a
  pre-filled issue.
"""

from __future__ import annotations

import itertools
import linecache
import platform
import re
import sysconfig
import textwrap
import time
from dataclasses import dataclass, field
from datetime import datetime
from importlib import metadata
from pathlib import Path, PurePath
from urllib.parse import urlencode

from qtpy.QtCore import QObject, Qt, QUrl, Signal
from qtpy.QtGui import QDesktopServices, QGuiApplication
from qtpy.QtWidgets import QApplication

#: Where "Report issue" opens a pre-filled issue. Decided by the maintainers, so kept in one place.
ISSUE_URL = "https://github.com/bec-project/bec_widgets/issues/new"
#: Packages whose frames count as BEC code even when they are installed in site-packages.
BEC_PACKAGE_PREFIXES = ("bec", "ophyd_devices", "pytest_bec")
#: Frames of the error plumbing itself, which never explain an error.
PLUMBING_FRAMES = (("bec_widgets/utils/error_popups.py", "wrapper"),)
MAX_ERRORS = 50
CONTEXT_LINES = 2
#: GitHub rejects very long URLs; the report body is cut to this many characters.
MAX_ISSUE_BODY = 6000

_FILE_RE = re.compile(r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<func>.+))?$')
_CARET_RE = re.compile(r"^\s*[\^~\-]+\s*$")
_CHAIN_MARKERS = {
    "The above exception was the direct cause of the following exception:": "Caused by",
    "During handling of the above exception, another exception occurred:": "While handling",
}
_STDLIB_DIRS = tuple(
    str(PurePath(p))
    for p in dict.fromkeys(
        [sysconfig.get_paths().get("stdlib"), sysconfig.get_paths().get("platstdlib")]
    )
    if p
)


@dataclass
class TraceFrame:
    """One ``File "...", line N, in func`` entry of a traceback."""

    file: str
    line: int
    func: str
    code: str = ""

    @property
    def is_bec(self) -> bool:
        """True for frames in BEC packages or user scripts, False for stdlib and third party."""
        return classify_path(self.file) == "bec"

    @property
    def is_plumbing(self) -> bool:
        """True for the SafeSlot wrapper and similar frames that only forward the error."""
        posix = self.file.replace("\\", "/")
        return any(posix.endswith(path) and self.func == func for path, func in PLUMBING_FRAMES)


@dataclass
class TraceException:
    """One exception of a (possibly chained) traceback with the frames that led to it."""

    type: str
    message: str
    frames: list[TraceFrame] = field(default_factory=list)
    #: How this exception relates to the one after it: "Caused by", "While handling" or "".
    relation: str = ""

    @property
    def short_type(self) -> str:
        """Exception class name without its module, e.g. ``ValueError``."""
        return self.type.rsplit(".", 1)[-1]


def classify_path(path: str) -> str:
    """Return ``"bec"`` for BEC and user code, ``"library"`` for stdlib and third party code."""
    posix = path.replace("\\", "/")
    if posix.startswith("<") and posix.endswith(">"):
        # <frozen runpy>, <string> and friends
        return "library" if posix.startswith("<frozen") else "bec"
    for marker in ("/site-packages/", "/dist-packages/"):
        if marker in posix:
            package = posix.split(marker, 1)[1].split("/", 1)[0]
            return "bec" if package.startswith(BEC_PACKAGE_PREFIXES) else "library"
    if any(posix.startswith(stdlib.replace("\\", "/") + "/") for stdlib in _STDLIB_DIRS):
        return "library"
    if re.search(r"/lib/python3\.\d+/", posix):
        return "library"
    return "bec"


def short_path(path: str) -> str:
    """Shorten ``path`` to the part a developer recognises, e.g. ``bec_widgets/utils/x.py``."""
    posix = path.replace("\\", "/")
    for marker in ("/site-packages/", "/dist-packages/"):
        if marker in posix:
            return posix.split(marker, 1)[1]
    match = re.search(r"/lib/python3\.\d+/(.+)$", posix)
    if match:
        return match.group(1)
    parts = PurePath(posix).parts
    top = _top_package_index(posix)
    if top is not None:
        return "/".join(parts[top:])
    for index, part in enumerate(parts[:-1]):
        if part.startswith(BEC_PACKAGE_PREFIXES):
            # a checkout is often named like its package: repo/bec_widgets/bec_widgets/...
            while index + 2 < len(parts) and parts[index + 1] == part:
                index += 1
            return "/".join(parts[index:])
    return "/".join(parts[-3:]) if len(parts) > 3 else posix


def _top_package_index(posix: str) -> int | None:
    """Index of the outermost directory of ``posix`` that is still a Python package."""
    path = Path(posix)
    if not path.is_absolute() or not path.is_file():
        return None
    directory = path.parent
    top = None
    while (directory / "__init__.py").is_file() and directory != directory.parent:
        top = directory
        directory = directory.parent
    if top is None:
        return None
    return len(top.parts) - 1


def parse_traceback(text: str) -> list[TraceException]:  # pylint: disable=too-many-branches
    """Parse a formatted Python traceback into its chain of exceptions, oldest first.

    Args:
        text(str): Output of :func:`traceback.format_exception` or any similar text.

    Returns:
        list[TraceException]: The exceptions in the order Python prints them. The last one is the
        exception that was actually raised. Text that is not a traceback yields one exception
        holding the text as message.
    """
    exceptions: list[TraceException] = []
    frames: list[TraceFrame] = []
    relation = ""
    message_lines: list[str] | None = None
    exc_type = ""

    def finish():
        nonlocal frames, message_lines, exc_type, relation
        if message_lines is not None:
            message = "\n".join(message_lines).strip()
            exceptions.append(TraceException(exc_type, message, frames, ""))
            if exceptions[:-1]:
                exceptions[-2].relation = relation
            relation = ""
        frames, message_lines, exc_type = [], None, ""

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped in _CHAIN_MARKERS:
            finish()
            relation = _CHAIN_MARKERS[stripped]
            continue
        if stripped.startswith("Traceback (most recent call last)"):
            if message_lines is not None:
                finish()
            continue
        match = _FILE_RE.match(line)
        if match and message_lines is None:
            frames.append(
                TraceFrame(
                    file=match.group("file"),
                    line=int(match.group("line")),
                    func=(match.group("func") or "").strip(),
                )
            )
            continue
        if message_lines is None and frames and line.startswith("    "):
            if _CARET_RE.match(line) or frames[-1].code:
                continue
            frames[-1].code = stripped
            continue
        if message_lines is None:
            if not stripped:
                continue
            head, sep, tail = stripped.partition(":")
            if sep and head and " " not in head:
                exc_type, message_lines = head, [tail.strip()]
            elif re.fullmatch(r"[\w.]+", stripped):
                exc_type, message_lines = stripped, []
            else:
                exc_type, message_lines = "", [stripped]
            continue
        message_lines.append(line)
    finish()
    if not exceptions:
        exceptions.append(TraceException("Error", (text or "").strip()))
    for exc in exceptions:
        if not exc.type:
            exc.type = "Error"
    return exceptions


def source_context(frame: TraceFrame, around: int = CONTEXT_LINES) -> list[dict]:
    """Return the source lines around ``frame`` as ``{"no", "text", "current"}`` rows.

    Falls back to the code line printed in the traceback when the file cannot be read.
    """
    rows = []
    if not frame.file.startswith("<"):
        for number in range(max(1, frame.line - around), frame.line + around + 1):
            text = linecache.getline(frame.file, number)
            if not text and number > frame.line:
                break
            rows.append({"no": number, "text": text.rstrip("\n"), "current": number == frame.line})
    if not any(row["current"] and row["text"].strip() for row in rows):
        rows = [{"no": frame.line, "text": frame.code, "current": True}] if frame.code else []
    return rows


def environment_lines() -> list[str]:
    """Versions and platform for the report."""

    def version(dist: str) -> str:
        try:
            return metadata.version(dist)
        except metadata.PackageNotFoundError:
            return "not installed"

    try:
        from qtpy import QT_VERSION  # pylint: disable=import-outside-toplevel
    except ImportError:  # pragma: no cover
        QT_VERSION = "unknown"  # pylint: disable=invalid-name
    return [
        f"bec_widgets {version('bec_widgets')}, bec_lib {version('bec_lib')}, "
        f"ophyd_devices {version('ophyd_devices')}",
        f"Python {platform.python_version()}, Qt {QT_VERSION}, {platform.platform()}",
    ]


def absolute_time(timestamp: float) -> str:
    """Full local timestamp."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def clock_time(timestamp: float) -> str:
    """``HH:MM:SS`` of ``timestamp``."""
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


@dataclass
class ErrorRecord:  # pylint: disable=too-many-instance-attributes
    """One error shown by the dialog; repeats of the same error raise ``count``."""

    id: str
    title: str
    traceback: str
    source: str = ""
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    count: int = 1
    seen: bool = False
    exceptions: list[TraceException] = field(default_factory=list)

    def __post_init__(self):
        if not self.exceptions:
            self.exceptions = parse_traceback(self.traceback)

    @property
    def final(self) -> TraceException:
        """The exception that was raised last, i.e. the one the user sees first."""
        return self.exceptions[-1]

    @property
    def signature(self) -> tuple:
        """Identity used to fold repeats: type, message and every frame location."""
        return tuple(
            (exc.type, exc.message, tuple((f.file, f.line) for f in exc.frames))
            for exc in self.exceptions
        )

    def focus_frame(self) -> TraceFrame | None:
        """The deepest BEC frame of the raised exception, else its deepest frame."""
        for exc in reversed(self.exceptions):
            candidates = [f for f in exc.frames if not f.is_plumbing]
            for frame in reversed(candidates):
                if frame.is_bec:
                    return frame
        frames = self.final.frames
        return frames[-1] if frames else None

    def report_text(self) -> str:
        """Plain-text report for the clipboard, a logbook or an issue."""
        final = self.final
        lines = [f"{final.type}: {final.message}".rstrip(": ")]
        lines.append(f"Kind: {self.title}")
        if self.source:
            lines.append(f"Raised in: {self.source}")
        focus = self.focus_frame()
        if focus is not None:
            lines.append(f"Location: {short_path(focus.file)}:{focus.line} in {focus.func}")
        lines.append(f"Time: {absolute_time(self.updated)}")
        if self.count > 1:
            lines.append(f"Occurrences: {self.count} (first at {absolute_time(self.created)})")
        lines.extend(environment_lines())
        lines.extend(["", self.traceback.strip()])
        return "\n".join(lines)

    def issue_url(self) -> str:
        """A pre-filled "new issue" URL for this error."""
        final = self.final
        title = f"{final.short_type}: {final.message.splitlines()[0] if final.message else ''}"
        body = self.report_text()
        if len(body) > MAX_ISSUE_BODY:
            body = body[: MAX_ISSUE_BODY - 40] + "\n... (cut, use Copy report for the rest)"
        body = f"**What I was doing:**\n\n\n**Error report:**\n```\n{body}\n```\n"
        return f"{ISSUE_URL}?{urlencode({'title': title[:200], 'body': body})}"


class ErrorDialogController(QObject):  # pylint: disable=too-many-instance-attributes
    """State and actions of the error dialog, shared by the QML and QWidget versions.

    Signals:
        changed: Emitted after any change; views re-read :meth:`view_state`.
        error_added(str): Emitted with the id of a new or repeated error.
    """

    changed = Signal()
    error_added = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._errors: list[ErrorRecord] = []  # newest first
        self._current: str | None = None
        self._ids = itertools.count(1)
        self.show_library = False
        self.mode = "frames"
        self._expanded_frames: set[str] = set()
        self._open_groups: set[str] = set()
        self.last_copied = ""

    # ------------------------------------------------------------------ errors

    @property
    def errors(self) -> list[ErrorRecord]:
        """All errors, newest first."""
        return list(self._errors)

    @property
    def current(self) -> ErrorRecord | None:
        """The error the dialog shows."""
        return next((e for e in self._errors if e.id == self._current), None)

    def add_error(self, title: str, traceback_text: str, source: str = "") -> str:
        """Add an error, folding it into an identical earlier one.

        The dialog switches to the new error unless the user is reading an older one, so a
        burst of errors does not pull the view away from what they are looking at.

        Args:
            title(str): Kind of error, e.g. ``"Method error"`` or ``"Application error"``.
            traceback_text(str): Formatted traceback.
            source(str): Where it was raised, e.g. the slot's qualified name.

        Returns:
            str: Id of the (possibly folded) error.
        """
        record = ErrorRecord(f"e{next(self._ids)}", title, traceback_text, source)
        follow = self._current is None or (self._errors and self._errors[0].id == self._current)
        existing = next((e for e in self._errors if e.signature == record.signature), None)
        if existing is not None:
            existing.count += 1
            existing.updated = record.updated
            existing.seen = existing.id == self._current
            self._errors.remove(existing)
            self._errors.insert(0, existing)
            record = existing
        else:
            self._errors.insert(0, record)
            del self._errors[MAX_ERRORS:]
        if follow:
            self._select(record.id)
        self.changed.emit()
        self.error_added.emit(record.id)
        return record.id

    def select(self, error_id: str) -> None:
        """Show the error with ``error_id``."""
        if any(e.id == error_id for e in self._errors):
            self._select(error_id)
            self.changed.emit()

    def step(self, delta: int) -> None:
        """Move ``delta`` entries in the list (positive = older)."""
        if not self._errors:
            return
        ids = [e.id for e in self._errors]
        index = ids.index(self._current) if self._current in ids else 0
        self.select(ids[max(0, min(len(ids) - 1, index + delta))])

    def dismiss(self, error_id: str | None = None) -> None:
        """Remove one error (the current one by default) and show its neighbour."""
        error_id = error_id or self._current
        ids = [e.id for e in self._errors]
        if error_id not in ids:
            return
        index = ids.index(error_id)
        self._errors.pop(index)
        if error_id == self._current:
            self._current = None
            if self._errors:
                self._select(self._errors[min(index, len(self._errors) - 1)].id)
        self.changed.emit()

    def clear(self) -> None:
        """Remove every error."""
        self._errors.clear()
        self._current = None
        self.changed.emit()

    def _select(self, error_id: str) -> None:
        if error_id != self._current:
            self._expanded_frames.clear()
            self._open_groups.clear()
        self._current = error_id
        record = self.current
        if record is not None:
            record.seen = True

    # ------------------------------------------------------------------ traceback view

    def set_show_library(self, show: bool) -> None:
        """Show or fold the standard library and third party frames."""
        self.show_library = bool(show)
        self.changed.emit()

    def set_mode(self, mode: str) -> None:
        """Switch the traceback between ``"frames"`` and ``"raw"`` text."""
        if mode in ("frames", "raw"):
            self.mode = mode
            self.changed.emit()

    def toggle_frame(self, key: str) -> None:
        """Expand or collapse the source context of one frame."""
        self._expanded_frames.symmetric_difference_update({key})
        self.changed.emit()

    def toggle_group(self, key: str) -> None:
        """Unfold or fold one run of library frames."""
        self._open_groups.symmetric_difference_update({key})
        self.changed.emit()

    # ------------------------------------------------------------------ actions

    def copy_report(self) -> str:
        """Copy the report of the current error to the clipboard and return it."""
        record = self.current
        if record is None:
            return ""
        self.last_copied = record.report_text()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.last_copied)
        return self.last_copied

    def copy_location(self) -> str:
        """Copy ``path:line`` of the "where it happened" frame."""
        record = self.current
        frame = record.focus_frame() if record else None
        if frame is None:
            return ""
        self.last_copied = f"{frame.file}:{frame.line}"
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.last_copied)
        return self.last_copied

    def report_issue(self) -> str:
        """Open a pre-filled issue for the current error in the browser and return the URL."""
        record = self.current
        if record is None:
            return ""
        url = record.issue_url()
        QDesktopServices.openUrl(QUrl(url))
        return url

    # ------------------------------------------------------------------ view state

    def view_state(self, now: float | None = None) -> dict:
        """Everything the views need to render, as plain Python data."""
        now = time.time() if now is None else now
        ids = [e.id for e in self._errors]
        index = ids.index(self._current) if self._current in ids else -1
        state = {
            "count": len(self._errors),
            "index": index,
            "unseen": sum(1 for e in self._errors if not e.seen),
            "show_library": self.show_library,
            "mode": self.mode,
            "errors": [self._list_row(e, now) for e in self._errors],
            "current": None,
        }
        record = self.current
        if record is not None:
            state["current"] = self._detail(record, now)
        return state

    @staticmethod
    def _list_row(record: ErrorRecord, now: float) -> dict:
        final = record.final
        return {
            "id": record.id,
            "type": final.short_type,
            "message": final.message.splitlines()[0] if final.message else "",
            "time": clock_time(record.updated),
            "age": _age(record.updated, now),
            "count": record.count,
            "source": record.source,
            "seen": record.seen,
        }

    def _detail(self, record: ErrorRecord, now: float) -> dict:
        final = record.final
        focus = record.focus_frame()
        location = None
        if focus is not None:
            location = {
                "file": focus.file,
                "file_short": short_path(focus.file),
                "line": focus.line,
                "func": focus.func,
                "context": source_context(focus),
            }
        library_frames = sum(
            1 for exc in record.exceptions for f in exc.frames if not f.is_bec or f.is_plumbing
        )
        headline, _, more = final.message.partition("\n")
        return {
            "id": record.id,
            "title": record.title,
            "type": final.short_type,
            "qualified_type": final.type,
            "message": final.message,
            "headline": headline.strip(),
            "message_more": textwrap.dedent(more).strip("\n"),
            "source": record.source,
            "time": absolute_time(record.updated),
            "age": _age(record.updated, now),
            "count": record.count,
            "first_time": absolute_time(record.created),
            "location": location,
            "rows": self._rows(record, focus),
            "frame_count": sum(len(exc.frames) for exc in record.exceptions),
            "library_frame_count": library_frames,
            "raw": record.traceback.strip(),
        }

    def _rows(self, record: ErrorRecord, focus: TraceFrame | None) -> list[dict]:
        """Flat list of section, frame and folded-group rows, most recent call first."""
        rows: list[dict] = []
        chain = list(enumerate(record.exceptions))
        for position, (exc_index, exc) in enumerate(reversed(chain)):
            if position == 0:
                label = "Raised"
            else:
                label = record.exceptions[exc_index].relation or "Earlier"
            rows.append(
                {
                    "kind": "section",
                    "key": f"x{exc_index}",
                    "label": label,
                    "type": exc.short_type,
                    "message": exc.message,
                    "first": position == 0,
                }
            )
            pending: list[tuple[int, TraceFrame]] = []
            for frame_index in range(len(exc.frames) - 1, -1, -1):
                frame = exc.frames[frame_index]
                if frame.is_bec and not frame.is_plumbing:
                    self._flush_group(rows, exc_index, pending, focus)
                    rows.append(self._frame_row(exc_index, frame_index, frame, focus))
                else:
                    pending.append((frame_index, frame))
            self._flush_group(rows, exc_index, pending, focus)
        return rows

    def _flush_group(
        self,
        rows: list[dict],
        exc_index: int,
        pending: list[tuple[int, TraceFrame]],
        focus: TraceFrame | None,
    ) -> None:
        """Append a run of library frames as one foldable group row."""
        if not pending:
            return
        key = f"g{exc_index}.{pending[0][0]}"
        is_open = self.show_library or key in self._open_groups
        if not self.show_library:
            rows.append(
                {
                    "kind": "group",
                    "key": key,
                    "count": len(pending),
                    "open": is_open,
                    "label": _group_label(pending),
                }
            )
        if is_open:
            rows.extend(self._frame_row(exc_index, i, f, focus) for i, f in pending)
        pending.clear()

    def _frame_row(
        self, exc_index: int, frame_index: int, frame: TraceFrame, focus: TraceFrame | None
    ) -> dict:
        key = f"f{exc_index}.{frame_index}"
        expanded = key in self._expanded_frames
        return {
            "kind": "frame",
            "key": key,
            "func": frame.func or "<module>",
            "file": frame.file,
            "file_short": short_path(frame.file),
            "line": frame.line,
            "code": frame.code,
            "bec": frame.is_bec and not frame.is_plumbing,
            "focus": frame is focus,
            "expanded": expanded,
            "context": source_context(frame) if expanded else [],
        }


def _group_label(pending: list[tuple[int, TraceFrame]]) -> str:
    if all(frame.is_plumbing for _, frame in pending):
        return "SafeSlot error handling"
    packages = []
    for _, frame in pending:
        name = short_path(frame.file).split("/", 1)[0]
        name = name.removesuffix(".py")
        if name not in packages:
            packages.append(name)
    noun = "frame" if len(pending) == 1 else "frames"
    shown = ", ".join(packages[:3]) + (" …" if len(packages) > 3 else "")
    return f"{len(pending)} library {noun} · {shown}"


def _age(timestamp: float, now: float) -> str:
    seconds = max(0, int(now - timestamp))
    if seconds < 10:
        return "just now"
    if seconds < 60:
        return f"{seconds} s ago"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    return clock_time(timestamp)


class ErrorDialogWindowMixin:
    """Window behaviour shared by both dialog versions: size, theme and presenting errors.

    The dialog is not modal: errors that arrive while it is open are added to its list instead
    of stacking further dialogs, and the rest of the application stays usable. Closing it
    clears the list.
    """

    MIN_SIZE = (600, 420)
    DEFAULT_SIZE = (960, 680)

    controller: ErrorDialogController

    def init_window(self) -> None:
        """Set flags, size and theme hooks. Call at the end of ``__init__``."""
        # pylint: disable=no-member
        self.setWindowTitle("Error")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(False)
        self.setSizeGripEnabled(True)
        self.setMinimumSize(*self.MIN_SIZE)
        width, height = self.DEFAULT_SIZE
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, int(available.width() * 0.85))
            height = min(height, int(available.height() * 0.85))
        self.resize(max(width, self.MIN_SIZE[0]), max(height, self.MIN_SIZE[1]))
        app = QApplication.instance()
        theme = getattr(app, "theme", None)
        if theme is not None:
            theme.theme_changed.connect(self._on_theme_changed)
        self.apply_theme()

    def _on_theme_changed(self, *_args) -> None:
        self.apply_theme()

    def apply_theme(self) -> None:  # pragma: no cover - implemented by the views
        """Restyle the view for the current theme."""
        raise NotImplementedError

    def show_error(self, title: str, traceback_text: str, source: str = "") -> str:
        """Add an error and bring the dialog to the front.

        Args:
            title(str): Kind of error, e.g. ``"Method error"``.
            traceback_text(str): Formatted traceback.
            source(str): Where the error was raised, e.g. a slot's qualified name.

        Returns:
            str: Id of the error in the list.
        """
        error_id = self.controller.add_error(title, traceback_text, source)
        self.present()
        return error_id

    def present(self) -> None:
        """Show the dialog, or raise it if it is already open."""
        # pylint: disable=no-member
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """Closing the dialog clears its list of errors."""
        self.controller.clear()
        super().closeEvent(event)  # pylint: disable=no-member
