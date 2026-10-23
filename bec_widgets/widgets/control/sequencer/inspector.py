"""Side panel that edits the selected step in plain language.

Used by the Recipe and Flowchart concepts. Scan steps reuse the existing ``ScanControl``
form, so scientists see the same scan settings they know from the scan control widget.
"""

from __future__ import annotations

import numpy as np
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QAbstractSpinBox,
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
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.scan_control.scan_control import ScanControl
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.document import SequenceDocument
from bec_widgets.widgets.control.sequencer.style import heading, hint, kind_icon


def parse_values(text: str) -> list:
    """Parse ``1, -1, 2.5`` (or one value per line) into numbers, keeping words as text."""
    values = []
    for part in text.replace("\n", ",").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            number = float(part)
            values.append(int(number) if number.is_integer() and "." not in part else number)
        except ValueError:
            values.append(part)
    return values


def values_text(values: list) -> str:
    """Inverse of ``parse_values``."""
    return ", ".join(model.format_value(v) for v in values)


class RangeDialog(QDialog):
    """Fill a list of values from start, stop and number of points."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Fill evenly spaced values")
        form = QFormLayout(self)
        self.start = QDoubleSpinBox(self, decimals=4, minimum=-1e6, maximum=1e6, value=0)
        self.stop = QDoubleSpinBox(self, decimals=4, minimum=-1e6, maximum=1e6, value=10)
        self.points = QSpinBox(self, minimum=1, maximum=10000, value=11)
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
    """The scan control form without its Start/Stop buttons and metadata."""
    form = ScanControl(parent, client=client)
    form.hide_scan_control_buttons = True
    form.hide_metadata = True
    group = getattr(form, "_metadata_group", None)
    if group is not None:
        group.setVisible(False)
    return form


def scan_form_values(form: ScanControl) -> tuple[str, list, dict]:
    """Scan name, positional and keyword arguments shown in a scan form."""
    positional, arguments = form.get_scan_parameters(bec_object=False)
    arguments.pop("metadata", None)
    return form.current_scan, list(positional), arguments


def set_scan_form_values(form: ScanControl, node: dict) -> None:
    """Show a scan node in a scan form."""
    form.set_current_scan(node.get("name", ""))
    positional = [v for v in node.get("positional", []) if not isinstance(v, dict)]
    if form.arg_box is not None and positional:
        form.arg_box.set_parameters(positional)
    arguments = node.get("arguments") if isinstance(node.get("arguments"), dict) else {}
    for box in form.kwarg_boxes:
        box.set_parameters(arguments)


class ScanSettingsDialog(QDialog):
    """Edit one scan step in the familiar scan control form."""

    def __init__(self, node: dict, client, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Scan settings")
        self.resize(520, 620)
        layout = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.form = make_scan_form(scroll, client)
        scroll.setWidget(self.form)
        layout.addWidget(scroll, 1)
        set_scan_form_values(self.form, node)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, list, dict]:
        """Scan name, positional and keyword arguments."""
        return scan_form_values(self.form)


class ValueInput(QWidget):
    """Either a fixed number or "the current loop value"."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.source = QComboBox(self)
        self.number = QDoubleSpinBox(self, decimals=4, minimum=-1e9, maximum=1e9)
        self.number.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        layout.addWidget(self.source, 1)
        layout.addWidget(self.number, 1)
        self.source.currentIndexChanged.connect(self._sync)

    def set_choices(self, variables: list[str]) -> None:
        """Offer the loop variables visible at this step."""
        self.source.blockSignals(True)
        self.source.clear()
        self.source.addItem("a fixed value", None)
        for name in variables:
            self.source.addItem(f"each {name} from the loop", name)
        self.source.blockSignals(False)

    def set_value(self, value) -> None:
        """Show a literal or a reference."""
        if model.is_ref(value) and self.source.findData(value["ref"]) >= 0:
            self.source.setCurrentIndex(self.source.findData(value["ref"]))
        else:
            self.source.setCurrentIndex(0)
            self.number.setValue(float(value) if isinstance(value, (int, float)) else 0.0)
        self._sync()

    def value(self):
        """Literal number or reference expression."""
        name = self.source.currentData()
        if name:
            return model.ref(name)
        number = self.number.value()
        return int(number) if number.is_integer() else number

    def _sync(self):
        self.number.setVisible(self.source.currentData() is None)
        self.source.setVisible(self.source.count() > 1)


class StepInspector(QWidget):
    """Edit the step selected in a ``SequenceDocument``."""

    def __init__(self, document: SequenceDocument, parent: QWidget | None = None, client=None):
        super().__init__(parent)
        self.document = document
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

        self.pages = QStackedWidget(self)
        layout.addWidget(self.pages, 1)
        self.pages.addWidget(QWidget(self))  # empty

        # move / set
        self.move_page = QWidget(self)
        form = QFormLayout(self.move_page)
        self.device = DeviceComboBox(
            self.move_page, client=client, device_filter=["Positioner"], autocomplete=True
        )
        self.device.setEditable(True)
        self.move_value = ValueInput(self.move_page)
        self.move_wait = QCheckBox("Wait until it has arrived", self.move_page)
        form.addRow("Motor", self.device)
        form.addRow("Go to", self.move_value)
        form.addRow("", self.move_wait)
        self.pages.addWidget(self.move_page)

        # scan
        self.scan_page = QScrollArea(self)
        self.scan_page.setWidgetResizable(True)
        self.scan_page.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scan_control = make_scan_form(self.scan_page, client)
        self.scan_page.setWidget(self.scan_control)
        self.pages.addWidget(self.scan_page)

        # repeat
        self.repeat_page = QWidget(self)
        form = QFormLayout(self.repeat_page)
        self.repeat_count = QSpinBox(self.repeat_page, minimum=1, maximum=100000)
        form.addRow("How many times", self.repeat_count)
        form.addRow(hint("Everything inside the loop runs this many times.", self.repeat_page))
        self.pages.addWidget(self.repeat_page)

        # for each
        self.each_page = QWidget(self)
        form = QFormLayout(self.each_page)
        self.each_name = QLineEdit(self.each_page)
        self.each_values = QLineEdit(self.each_page)
        self.each_values.setPlaceholderText("e.g. 1, -1, 2.5")
        fill = QPushButton("Fill evenly spaced…", self.each_page)
        fill.clicked.connect(self._fill_range)
        self.each_count = hint("", self.each_page)
        form.addRow("Name of the value", self.each_name)
        form.addRow("Values (in order)", self.each_values)
        form.addRow("", fill)
        form.addRow(self.each_count)
        form.addRow(
            hint(
                "Steps inside the loop can use this value, e.g. “Move samx to each position”.",
                self.each_page,
            )
        )
        self.pages.addWidget(self.each_page)

        # while moving
        self.while_page = QWidget(self)
        form = QFormLayout(self.while_page)
        self.while_device = DeviceComboBox(
            self.while_page, client=client, device_filter=["Positioner"], autocomplete=True
        )
        self.while_device.setEditable(True)
        self.while_target = QDoubleSpinBox(self.while_page, decimals=4, minimum=-1e9, maximum=1e9)
        form.addRow("Motor", self.while_device)
        form.addRow("Moves to", self.while_target)
        form.addRow(
            hint(
                "The motor starts moving, and the steps inside keep repeating until it arrives.",
                self.while_page,
            )
        )
        self.pages.addWidget(self.while_page)

        # group / other
        self.info_page = QWidget(self)
        QVBoxLayout(self.info_page).addWidget(
            hint("A group just keeps steps together. Drag steps in or out.", self.info_page)
        )
        self.pages.addWidget(self.info_page)

        for widget in (self.move_value.number, self.while_target):
            widget.valueChanged.connect(self._schedule)
        self.repeat_count.valueChanged.connect(self._schedule)
        self.move_value.source.currentIndexChanged.connect(self._schedule)
        self.move_wait.toggled.connect(self._schedule)
        self.each_name.textChanged.connect(self._schedule)
        self.each_values.textChanged.connect(self._schedule)
        for combo in (self.device, self.while_device):
            combo.currentTextChanged.connect(self._schedule)
        self.scan_control.scan_selected.connect(self._on_scan_selected)

        document.selection_changed.connect(self.load)
        document.changed.connect(self._on_document_changed)

    # --- loading ---------------------------------------------------------------------------
    @SafeSlot(str)
    def load(self, node_id: str) -> None:
        """Show the editor for a step."""
        self._commit_timer.stop()
        self._node_id = node_id
        node = self.document.node(node_id) if node_id else None
        self._loading = True
        try:
            if node is None or node is self.document.root:
                self.icon.clear()
                self.title.setText("Step details")
                self.subtitle.setText("Select a step to change it.")
                self.pages.setCurrentIndex(0)
                return
            kind = node["type"]
            self.icon.setPixmap(kind_icon(kind, 22).pixmap(22, 22))
            title = model.KIND_TITLES.get(kind, kind)
            if kind == "set" and "." not in node.get("device", ""):
                title = "Start moving" if node.get("bind_status") else "Move"
            self.title.setText(title)
            self.subtitle.setText(model.sentence(node, self.document.root, self._entries()))
            getattr(self, f"_load_{kind}", self._load_other)(node)
        finally:
            self._loading = False

    def _entries(self) -> dict:
        return getattr(self.scan_control, "available_scans", None) or {}

    def _load_set(self, node: dict) -> None:
        self.device.setCurrentText(node.get("device", ""))
        self.move_value.set_choices(model.visible_variables(self.document.root, node["id"]))
        self.move_value.set_value(node.get("value"))
        self.move_wait.setChecked(bool(node.get("wait", True)))
        self.move_wait.setEnabled(not node.get("bind_status"))
        self.pages.setCurrentWidget(self.move_page)

    def _load_scan_call(self, node: dict) -> None:
        self.pages.setCurrentWidget(self.scan_page)
        set_scan_form_values(self.scan_control, node)
        self._hook_scan_inputs()

    def _load_repeat(self, node: dict) -> None:
        self.repeat_count.setValue(int(node.get("count", 1)))
        self.pages.setCurrentWidget(self.repeat_page)

    def _load_for_each(self, node: dict) -> None:
        self.each_name.setText(node.get("variable", ""))
        values = node.get("values") if isinstance(node.get("values"), list) else []
        self.each_values.setText(values_text(values))
        self.each_count.setText(f"{len(values)} value{'s' if len(values) != 1 else ''}")
        self.pages.setCurrentWidget(self.each_page)

    def _load_while(self, node: dict) -> None:
        status = model.while_status(node)
        owner = model.status_owner(self.document.root, status) if status else None
        if owner is not None:
            self.while_device.setCurrentText(owner.get("device", ""))
            value = owner.get("value")
            self.while_target.setValue(float(value) if isinstance(value, (int, float)) else 0)
        self.pages.setCurrentWidget(self.while_page)

    def _load_other(self, _node: dict) -> None:
        self.pages.setCurrentWidget(self.info_page)

    # --- committing ------------------------------------------------------------------------
    def _schedule(self, *_args) -> None:
        if not self._loading and self._node_id:
            self._commit_timer.start()

    @SafeSlot(str)
    def _on_scan_selected(self, _name: str) -> None:
        self._hook_scan_inputs()
        self._schedule()

    def _hook_scan_inputs(self) -> None:
        for widget in self.scan_control.findChildren(QWidget):
            if widget.property("_sequencer_hooked"):
                continue
            widget.setProperty("_sequencer_hooked", True)
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self._schedule)
            elif (
                isinstance(widget, QComboBox)
                and widget is not self.scan_control.comboBox_scan_selection
            ):
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
            self.document.update(
                node["id"],
                device=self.device.currentText().strip() or node.get("device"),
                value=self.move_value.value(),
                wait=True if node.get("bind_status") else self.move_wait.isChecked(),
            )
        elif kind == "scan_call":
            name, positional, arguments = scan_form_values(self.scan_control)
            if not name:
                return
            self.document.update(
                node["id"], name=name, positional=list(positional), arguments=arguments
            )
        elif kind == "repeat":
            self.document.update(node["id"], count=self.repeat_count.value())
        elif kind == "for_each":
            values = parse_values(self.each_values.text())
            self.each_count.setText(f"{len(values)} value{'s' if len(values) != 1 else ''}")
            new_name = self.each_name.text().strip() or node.get("variable")
            self._rename_variable(node, node.get("variable"), new_name)
            self.document.update(node["id"], variable=new_name, values=values)
        elif kind == "while":
            status = model.while_status(node)
            owner = model.status_owner(self.document.root, status) if status else None
            if owner is not None:
                target = self.while_target.value()
                self.document.update(
                    owner["id"],
                    device=self.while_device.currentText().strip() or owner.get("device"),
                    value=int(target) if target.is_integer() else target,
                )
        self.subtitle.setText(model.sentence(node, self.document.root, self._entries()))

    def _rename_variable(self, loop: dict, old: str, new: str) -> None:
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
            for key in ("value", "positional", "arguments", "values"):
                if key in node:
                    node[key] = visit(node[key])

    @SafeSlot()
    def _on_document_changed(self) -> None:
        if self._node_id and self.document.node(self._node_id) is None:
            self.load("")

    @SafeSlot()
    def _fill_range(self) -> None:
        dialog = RangeDialog(self)
        if dialog.exec():
            self.each_values.setText(values_text(dialog.values()))

    def cleanup(self) -> None:
        """Stop the commit timer."""
        self._commit_timer.stop()
