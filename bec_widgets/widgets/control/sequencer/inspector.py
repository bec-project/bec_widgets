"""Side panel that edits the selected step in plain language.

Used by the Recipe and Flowchart concepts. Scan steps reuse the existing ``ScanControl``
form, so scientists see the same scan settings they know from the scan control widget.
"""

from __future__ import annotations

import numpy as np
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.scan_control.scan_control import ScanControl
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.backend import Problem, SequencerBackend
from bec_widgets.widgets.control.sequencer.document import SequenceDocument
from bec_widgets.widgets.control.sequencer.fields import (
    NumberEdit,
    ScanPicker,
    ValuesEdit,
    device_picker,
    values_text,
)
from bec_widgets.widgets.control.sequencer.style import heading, hint, kind_icon, problem_label


class RangeDialog(QDialog):
    """Fill a list of values from start, stop and number of points."""

    def __init__(self, parent: QWidget | None = None, title: str = "Fill evenly spaced values"):
        super().__init__(parent)
        self.setWindowTitle(title)
        form = QFormLayout(self)
        self.start = QDoubleSpinBox(self, decimals=4, minimum=-1e6, maximum=1e6)
        self.stop = QDoubleSpinBox(self, decimals=4, minimum=-1e6, maximum=1e6)
        self.points = QSpinBox(self, minimum=1, maximum=10000, value=2)
        form.addRow("From", self.start)
        form.addRow("To", self.stop)
        form.addRow("Number of values", self.points)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> list[float]:
        """The generated values."""
        return [
            round(float(v), 6)
            for v in np.linspace(self.start.value(), self.stop.value(), self.points.value())
        ]


def make_scan_form(parent: QWidget | None, client) -> ScanControl:
    """The scan control form without its scan selector, Start/Stop buttons and metadata."""
    form = ScanControl(parent, client=client)
    form.hide_scan_control_buttons = True
    form.hide_scan_selection_combobox = True
    form.hide_metadata = True
    group = getattr(form, "_metadata_group", None)
    if group is not None:
        group.setVisible(False)
    return form


def scan_form_values(form: ScanControl) -> tuple[list, dict]:
    """Positional and keyword arguments shown in a scan form."""
    positional, arguments = form.get_scan_parameters(bec_object=False)
    arguments.pop("metadata", None)
    return list(positional), arguments


def show_scan_in_form(form: ScanControl, node: dict) -> None:
    """Show a scan node in a scan form; a fresh node gets the scan's own defaults."""
    name = node.get("name", "")
    # The form remembers values per scan; a step must only ever show its own values.
    form.config.scans.clear()
    form.previous_scan = None
    if form.current_scan == name:
        form.scan_select(name)
    else:
        form.set_current_scan(name)
    positional = node.get("positional") or []
    if form.arg_box is not None and positional and not any(isinstance(v, dict) for v in positional):
        form.arg_box.set_parameters(positional)
    arguments = node.get("arguments") if isinstance(node.get("arguments"), dict) else {}
    for box in form.kwarg_boxes:
        box.set_parameters({k: v for k, v in arguments.items() if not isinstance(v, dict)})


def scan_arguments(node: dict, positional: list, arguments: dict) -> dict:
    """New scan fields for a node, keeping metadata the form does not show (e.g. sample name)."""
    old = node.get("arguments") if isinstance(node.get("arguments"), dict) else {}
    if "metadata" in old:
        arguments = {**arguments, "metadata": old["metadata"]}
    return {"positional": list(positional), "arguments": arguments}


class ScanSettingsDialog(QDialog):
    """Choose a scan and edit its settings in the familiar scan control form."""

    def __init__(self, node: dict, client, entries: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.node = node
        self.setWindowTitle("Scan settings")
        self.resize(540, 640)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Scan", self))
        self.picker = ScanPicker(entries, self)
        self.picker.set_scan(node.get("name", ""))
        row.addWidget(self.picker, 1)
        layout.addLayout(row)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.form = make_scan_form(self.scroll, client)
        self.scroll.setWidget(self.form)
        layout.addWidget(self.scroll, 1)
        self.empty = hint("Choose the scan to run at this step.", self)
        layout.addWidget(self.empty)
        self.picker.scan_chosen.connect(self._on_scan)
        self._on_scan(node.get("name", ""), keep_values=True)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _on_scan(self, name: str, keep_values: bool = False) -> None:
        shown = dict(self.node) if keep_values else {"name": name}
        self.scroll.setVisible(bool(name))
        self.empty.setVisible(not name)
        if name:
            show_scan_in_form(self.form, shown)

    def values(self) -> tuple[str, list, dict]:
        """Scan name, positional and keyword arguments."""
        name = self.picker.scan()
        if not name:
            return "", [], {}
        positional, arguments = scan_form_values(self.form)
        return name, positional, arguments


class ValueInput(QWidget):
    """Either a typed number or "each value from the loop"."""

    edited = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.source = QComboBox(self)
        self.number = NumberEdit(self, "position")
        layout.addWidget(self.source, 1)
        layout.addWidget(self.number, 1)
        self.source.activated.connect(self._on_source)
        self.number.edited.connect(self.edited)

    def set_choices(self, variables: list[str]) -> None:
        """Offer the loop variables visible at this step."""
        self.source.clear()
        self.source.addItem("a fixed value", None)
        for name in reversed(variables):
            self.source.addItem(f"each {name} from the loop", name)

    def set_value(self, value) -> None:
        """Show a literal or a reference."""
        index = self.source.findData(value["ref"]) if model.is_ref(value) else 0
        self.source.setCurrentIndex(max(index, 0))
        self.number.set_value(None if model.is_ref(value) else value)
        self._sync()

    def value(self):
        """Typed value (None when empty) or reference expression."""
        name = self.source.currentData()
        return model.ref(name) if name else self.number.value()

    def _on_source(self, _index: int) -> None:
        self._sync()
        self.edited.emit()

    def _sync(self) -> None:
        self.number.setVisible(self.source.currentData() is None)
        self.source.setVisible(self.source.count() > 1)


class StepInspector(QWidget):
    """Edit the step selected in a ``SequenceDocument``."""

    def __init__(
        self,
        document: SequenceDocument,
        backend: SequencerBackend,
        parent: QWidget | None = None,
        client=None,
    ):
        super().__init__(parent)
        self.document = document
        self.backend = backend
        self.problems: list[Problem] = []
        self._node_id = ""
        self._loading = False
        self._commit_timer = QTimer(self, singleShot=True, interval=250)
        self._commit_timer.timeout.connect(self._commit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        self.icon = QLabel(self)
        self.title = heading("Step details", self)
        title_row.addWidget(self.icon)
        title_row.addWidget(self.title, 1)
        layout.addLayout(title_row)
        self.subtitle = hint("Select a step to change it.", self)
        layout.addWidget(self.subtitle)
        self.problem = problem_label(self)
        layout.addWidget(self.problem)

        self.pages = QStackedWidget(self)
        layout.addWidget(self.pages, 1)
        self.pages.addWidget(QWidget(self))  # nothing selected

        # move / set
        self.move_page = QWidget(self)
        form = QFormLayout(self.move_page)
        self.device = device_picker(self.move_page, client, settable=True)
        self.move_value = ValueInput(self.move_page)
        self.move_info = hint("", self.move_page)
        self.move_wait = QCheckBox("Wait until it has arrived", self.move_page)
        form.addRow("Motor", self.device)
        form.addRow("Go to", self.move_value)
        form.addRow("", self.move_info)
        form.addRow("", self.move_wait)
        self.pages.addWidget(self.move_page)

        # scan
        self.scan_page = QWidget(self)
        scan_layout = QVBoxLayout(self.scan_page)
        scan_layout.setContentsMargins(0, 0, 0, 0)
        picker_row = QFormLayout()
        self.scan_picker = ScanPicker(backend.scan_entries(), self.scan_page)
        picker_row.addRow("Scan", self.scan_picker)
        scan_layout.addLayout(picker_row)
        self.scan_scroll = QScrollArea(self.scan_page)
        self.scan_scroll.setWidgetResizable(True)
        self.scan_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scan_control = make_scan_form(self.scan_scroll, client)
        self.scan_scroll.setWidget(self.scan_control)
        scan_layout.addWidget(self.scan_scroll, 1)
        self.scan_empty = hint("Choose the scan to run at this step.", self.scan_page)
        scan_layout.addWidget(self.scan_empty)
        scan_layout.addStretch(0)
        self.pages.addWidget(self.scan_page)

        # repeat
        self.repeat_page = QWidget(self)
        form = QFormLayout(self.repeat_page)
        self.repeat_count = QSpinBox(self.repeat_page, minimum=1, maximum=100000)
        self.repeat_count.setSuffix(" times")
        form.addRow("Repeat", self.repeat_count)
        form.addRow(hint("Everything inside the loop runs this many times.", self.repeat_page))
        self.pages.addWidget(self.repeat_page)

        # for each
        self.each_page = QWidget(self)
        form = QFormLayout(self.each_page)
        self.each_name = QLineEdit(self.each_page)
        self.each_values = ValuesEdit(self.each_page)
        fill = QPushButton("Fill evenly spaced…", self.each_page)
        fill.clicked.connect(self._fill_range)
        self.each_count = hint("", self.each_page)
        form.addRow("Name of the value", self.each_name)
        form.addRow("Values, in order", self.each_values)
        form.addRow("", fill)
        form.addRow("", self.each_count)
        form.addRow(
            hint(
                "Steps inside the loop run once for every value. A move inside the loop can go"
                " to “each value from the loop”.",
                self.each_page,
            )
        )
        self.pages.addWidget(self.each_page)

        # while moving
        self.while_page = QWidget(self)
        form = QFormLayout(self.while_page)
        self.while_device = device_picker(self.while_page, client)
        self.while_target = NumberEdit(self.while_page, "position")
        self.while_info = hint("", self.while_page)
        form.addRow("Motor", self.while_device)
        form.addRow("Moves to", self.while_target)
        form.addRow("", self.while_info)
        form.addRow(
            hint(
                "The motor starts moving, and the steps inside keep repeating until it arrives.",
                self.while_page,
            )
        )
        self.pages.addWidget(self.while_page)

        # group / other
        self.info_page = QWidget(self)
        self.info_text = hint("", self.info_page)
        QVBoxLayout(self.info_page).addWidget(self.info_text)
        self.pages.addWidget(self.info_page)

        self.move_value.edited.connect(self._schedule)
        self.while_target.edited.connect(self._schedule)
        self.repeat_count.valueChanged.connect(self._schedule)
        self.move_wait.toggled.connect(self._schedule)
        self.each_name.textEdited.connect(self._schedule)
        self.each_values.textEdited.connect(self._schedule)
        for combo in (self.device, self.while_device):
            combo.device_selected.connect(self._schedule)
            combo.lineEdit().editingFinished.connect(self._schedule)
        self.scan_picker.scan_chosen.connect(self._on_scan_chosen)

        document.selection_changed.connect(self.load)
        document.changed.connect(self._on_document_changed)

    # --- loading ---------------------------------------------------------------------------
    @SafeSlot(str)
    def load(self, node_id: str) -> None:
        """Show the editor for a step."""
        if self._commit_timer.isActive():
            self._commit_timer.stop()
            self._commit()
        self._node_id = node_id
        node = self.document.node(node_id) if node_id else None
        self._loading = True
        try:
            if node is None or node is self.document.root:
                self.icon.clear()
                self.title.setText("Step details")
                self.subtitle.setText("Select a step to change it.")
                self.pages.setCurrentIndex(0)
                self._show_problem()
                return
            kind = node["type"]
            self.icon.setPixmap(kind_icon(kind, 22).pixmap(22, 22))
            title = model.KIND_TITLES.get(kind, kind)
            if kind == "set" and node.get("bind_status"):
                title = "Start moving"
            self.title.setText(title)
            self._update_subtitle(node)
            getattr(self, f"_load_{kind}", self._load_other)(node)
            self._show_problem()
        finally:
            self._loading = False

    def _update_subtitle(self, node: dict) -> None:
        self.subtitle.setText(model.sentence(node, self.document.root, self.backend.scan_entries()))

    def _motor_info(self, device: str) -> str:
        if not device or self.backend.device(device) is None:
            return ""
        parts = []
        position = self.backend.position(device)
        if position is not None:
            parts.append(f"Now at {position:.4g}")
        limits = self.backend.limits(device)
        if limits is not None:
            parts.append(f"limits {limits[0]:g} to {limits[1]:g}")
        return " · ".join(parts)

    def _load_set(self, node: dict) -> None:
        self.device.setCurrentText(node.get("device", ""))
        self.move_value.set_choices(model.visible_variables(self.document.root, node["id"]))
        self.move_value.set_value(node.get("value"))
        self.move_info.setText(self._motor_info(node.get("device", "")))
        self.move_wait.setChecked(bool(node.get("wait", True)))
        self.move_wait.setVisible(not node.get("bind_status"))
        self.pages.setCurrentWidget(self.move_page)

    def _load_scan_call(self, node: dict) -> None:
        self.pages.setCurrentWidget(self.scan_page)
        name = node.get("name", "")
        self.scan_picker.set_scan(name)
        self.scan_scroll.setVisible(bool(name))
        self.scan_empty.setVisible(not name)
        if name:
            show_scan_in_form(self.scan_control, node)
            self._hook_scan_inputs()

    def _load_repeat(self, node: dict) -> None:
        self.repeat_count.setValue(int(node.get("count", 1)))
        self.pages.setCurrentWidget(self.repeat_page)

    def _load_for_each(self, node: dict) -> None:
        self.each_name.setText(node.get("variable", ""))
        values = node.get("values") if isinstance(node.get("values"), list) else []
        self.each_values.setText(values_text(values))
        self._count_values(values)
        self.pages.setCurrentWidget(self.each_page)

    def _count_values(self, values: list) -> None:
        self.each_count.setText(f"{len(values)} value{'s' if len(values) != 1 else ''}")

    def _load_while(self, node: dict) -> None:
        owner = self._while_owner(node)
        device = owner.get("device", "") if owner else ""
        self.while_device.setCurrentText(device)
        self.while_target.set_value(owner.get("value") if owner else None)
        self.while_info.setText(self._motor_info(device))
        self.pages.setCurrentWidget(self.while_page)

    def _while_owner(self, node: dict) -> dict | None:
        status = model.while_status(node)
        return model.status_owner(self.document.root, status) if status else None

    def _load_other(self, node: dict) -> None:
        if node.get("type") == "component_call":
            text = "A saved block from another tool. It can be moved or deleted here."
        else:
            text = "A group keeps steps together. Drag steps in or out of it."
        self.info_text.setText(text)
        self.pages.setCurrentWidget(self.info_page)

    # --- problems --------------------------------------------------------------------------
    def set_problems(self, problems: list[Problem]) -> None:
        """Show the problem of the selected step, if any."""
        self.problems = problems
        self._show_problem()

    def _show_problem(self) -> None:
        message = next((p.message for p in self.problems if p.node_id == self._node_id), "")
        self.problem.setText(message)
        self.problem.setVisible(bool(message and self._node_id))

    # --- committing ------------------------------------------------------------------------
    def _schedule(self, *_args) -> None:
        if not self._loading and self._node_id:
            self._commit_timer.start()

    @SafeSlot(str)
    def _on_scan_chosen(self, name: str) -> None:
        node = self.document.node(self._node_id)
        if node is None or node.get("type") != "scan_call" or name == node.get("name"):
            return
        self._loading = True
        try:
            self.scan_picker.set_scan(name)
            self.scan_scroll.setVisible(True)
            self.scan_empty.setVisible(False)
            show_scan_in_form(self.scan_control, {"name": name})
            self._hook_scan_inputs()
        finally:
            self._loading = False
        positional, arguments = scan_form_values(self.scan_control)
        self.document.update(node["id"], name=name, **scan_arguments(node, positional, arguments))
        self._update_subtitle(node)

    def _hook_scan_inputs(self) -> None:
        for widget in self.scan_control.findChildren(QWidget):
            if widget.property("_sequencer_hooked"):
                continue
            widget.setProperty("_sequencer_hooked", True)
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self._schedule)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._schedule)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._schedule)
            elif isinstance(widget, QLineEdit) and not isinstance(widget.parent(), QComboBox):
                widget.textChanged.connect(self._schedule)

    @SafeSlot()
    def _commit(self) -> None:
        node = self.document.node(self._node_id)
        if node is None:
            return
        kind = node["type"]
        if kind == "set":
            device = self.device.currentText().strip()
            self.document.update(
                node["id"],
                device=device,
                value=self.move_value.value(),
                wait=True if node.get("bind_status") else self.move_wait.isChecked(),
            )
            self.move_info.setText(self._motor_info(device))
        elif kind == "scan_call":
            if not node.get("name"):
                return
            positional, arguments = scan_form_values(self.scan_control)
            self.document.update(node["id"], **scan_arguments(node, positional, arguments))
        elif kind == "repeat":
            self.document.update(node["id"], count=self.repeat_count.value())
        elif kind == "for_each":
            values = self.each_values.values()
            self._count_values(values)
            new_name = self.each_name.text().strip()
            if new_name:
                rename_variable(node, node.get("variable"), new_name)
            self.document.update(node["id"], variable=new_name, values=values)
        elif kind == "while":
            owner = self._while_owner(node)
            if owner is not None:
                device = self.while_device.currentText().strip()
                self.document.update(owner["id"], device=device, value=self.while_target.value())
                self.while_info.setText(self._motor_info(device))
        self._update_subtitle(node)

    @SafeSlot()
    def _on_document_changed(self) -> None:
        if self._node_id and self.document.node(self._node_id) is None:
            self.load("")

    @SafeSlot()
    def _fill_range(self) -> None:
        dialog = RangeDialog(self)
        if dialog.exec():
            self.each_values.setText(values_text(dialog.values()))
            self._schedule()

    def cleanup(self) -> None:
        """Save a pending edit and stop the commit timer."""
        if self._commit_timer.isActive():
            self._commit_timer.stop()
            self._commit()


def rename_variable(loop: dict, old: str | None, new: str) -> None:
    """Rename a loop variable in every step inside the loop that uses it.

    Args:
        loop (dict): The for-each node; its own ``variable`` is not changed.
        old (str | None): Current name.
        new (str): New name.
    """
    if not old or old == new:
        return

    def visit(value):
        if model.is_ref(value) and value["ref"] == old:
            return model.ref(new)
        if isinstance(value, list):
            return [visit(v) for v in value]
        if isinstance(value, dict):
            return {k: visit(v) for k, v in value.items()}
        return value

    for node, _depth, _parent in model.walk(loop):
        for key in ("value", "values", "positional", "arguments"):
            if key in node:
                node[key] = visit(node[key])
