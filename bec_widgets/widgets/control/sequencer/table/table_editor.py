"""Concept 3, Measurement table: a spreadsheet of points to measure.

Each row is one place to measure: the motor positions to go to and a sample name. The same
scan runs at every row; the whole table can be repeated. Rows can be pasted from Excel or
generated as a grid. The table is turned into a sequence (move, move, scan per row).
"""

from __future__ import annotations

import copy
import itertools

import numpy as np
from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtGui import QBrush, QColor, QKeySequence
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import rgba
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.editor_base import SequenceEditorBase
from bec_widgets.widgets.control.sequencer.fields import device_picker, parse_number
from bec_widgets.widgets.control.sequencer.inspector import ScanSettingsDialog
from bec_widgets.widgets.control.sequencer.style import (
    card_qss,
    empty_state,
    heading,
    hint,
    kind_color,
    kind_icon,
    problem_label,
    theme,
)

FIRST_MOTOR_COLUMN = 2


class GridDialog(QDialog):
    """Generate rows for every combination of evenly spaced motor positions."""

    def __init__(self, motors: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Fill the table with a grid")
        self.motors = motors
        layout = QVBoxLayout(self)
        layout.addWidget(hint("One row is created for every combination of positions.", self))
        grid = QGridLayout()
        for column, text in enumerate(("Motor", "From", "To", "Points")):
            grid.addWidget(QLabel(f"<b>{text}</b>", self), 0, column)
        self.inputs = []
        for row, motor in enumerate(motors, 1):
            start = QDoubleSpinBox(self, decimals=4, minimum=-1e6, maximum=1e6)
            stop = QDoubleSpinBox(self, decimals=4, minimum=-1e6, maximum=1e6)
            points = QSpinBox(self, minimum=1, maximum=1000, value=2)
            for column, widget in enumerate((QLabel(motor, self), start, stop, points)):
                grid.addWidget(widget, row, column)
            self.inputs.append((start, stop, points))
        layout.addLayout(grid)
        self.count = hint("", self)
        layout.addWidget(self.count)
        self.replace = QComboBox(self)
        self.replace.addItems(["Replace the rows", "Add below the rows"])
        layout.addWidget(self.replace)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for _start, _stop, points in self.inputs:
            points.valueChanged.connect(self._count)
        self._count()

    def _count(self, *_args) -> None:
        total = int(np.prod([points.value() for _a, _b, points in self.inputs]))
        self.count.setText(f"{total} row{'s' if total != 1 else ''}")

    def rows(self) -> list[list[float]]:
        """All combinations, first motor changing slowest."""
        axes = [
            [round(float(v), 6) for v in np.linspace(a.value(), b.value(), n.value())]
            for a, b, n in self.inputs
        ]
        return [list(combo) for combo in itertools.product(*axes)]


def _scan_settings(node: dict) -> tuple:
    arguments = {k: v for k, v in (node.get("arguments") or {}).items() if k != "metadata"}
    return node.get("name"), node.get("positional") or [], arguments


def table_state(doc: dict) -> dict | None:
    """Read a sequence back as a table, if it has the shape the table creates.

    Args:
        doc (dict): Sequence document.

    Returns:
        dict | None: Table state for ``TableEditor.restore_state``, or None when the sequence
        is not a list of "move, move, …, scan" rows with the same scan.
    """
    steps = model.children_of(doc.get("root", {}))
    repeats = 1
    if len(steps) == 1 and steps[0].get("type") == "repeat":
        repeats = int(steps[0].get("count", 1))
        steps = model.children_of(steps[0])
    motors: list[str] = []
    rows = []
    scan = None
    pending: dict = {}
    for node in steps:
        kind = node.get("type")
        if kind == "set" and node.get("wait", True) and not node.get("bind_status"):
            device = node.get("device") or ""
            if not device or model.is_ref(node.get("value")) or device in pending:
                return None
            pending[device] = node.get("value")
            if device not in motors:
                motors.append(device)
        elif kind == "scan_call":
            if scan is None:
                scan = node
            elif _scan_settings(node) != _scan_settings(scan):
                return None
            name = ((node.get("arguments") or {}).get("metadata") or {}).get("sample_name", "")
            rows.append((str(name), pending))
            pending = {}
        else:
            return None
    if pending or scan is None:
        return None
    name, positional, arguments = _scan_settings(scan)
    return {
        "motors": motors,
        "rows": [[name_, [values.get(m) for m in motors], True] for name_, values in rows],
        "scan": model.scan_node(name, positional, arguments),
        "repeats": repeats,
    }


class TableEditor(SequenceEditorBase):
    """Spreadsheet of measurement points."""

    # pylint: disable=too-many-ancestors, attribute-defined-outside-init

    CONCEPT_ID = "table"
    CONCEPT_TITLE = "Table"
    CONCEPT_TAGLINE = "A spreadsheet of points: one row per place to measure, paste from Excel."

    def build_editor(self, host: QWidget) -> None:
        self.motors: list[str] = []
        self.scan = model.scan_node("")
        self.repeats = 1
        self._cells: dict[str, tuple[int, int]] = {}
        self._scan_ids: set[str] = set()
        self._building = False

        layout = QVBoxLayout(host)
        layout.setContentsMargins(16, 14, 16, 8)
        layout.setSpacing(10)
        layout.addWidget(heading("Measurement points", host))
        layout.addWidget(
            hint(
                "Each row is one place to measure: the motors go to the row's positions, then the"
                " scan below runs. Leave a cell empty to keep that motor where it is. Paste rows"
                " from Excel with Ctrl+V.",
                host,
            )
        )

        # what to do at each point
        card = QWidget(host)
        card.setObjectName("TableScanCard")
        card.setStyleSheet(card_qss("#TableScanCard"))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        row = QHBoxLayout()
        icon = QLabel(card)
        icon.setPixmap(kind_icon("scan_call", 22).pixmap(22, 22))
        row.addWidget(icon)
        row.addWidget(QLabel("<b>At every row run</b>", card))
        self.scan_button = QPushButton(card)
        self.scan_button.setIcon(material_icon("tune", size=(16, 16), convert_to_pixmap=False))
        self.scan_button.setToolTip("Choose the scan and its settings")
        self.scan_button.clicked.connect(self._edit_scan)
        row.addWidget(self.scan_button)
        self.scan_label = QLabel(card)
        row.addWidget(self.scan_label, 1)
        row.addSpacing(16)
        row.addWidget(QLabel("Measure the whole table", card))
        self.repeat_spin = QSpinBox(card, minimum=1, maximum=1000)
        self.repeat_spin.setSuffix(" ×")
        self.repeat_spin.valueChanged.connect(self._on_repeats)
        row.addWidget(self.repeat_spin)
        card_layout.addLayout(row)
        self.scan_problem = problem_label(card)
        card_layout.addWidget(self.scan_problem)
        layout.addWidget(card)

        # motor columns and rows
        tools = QHBoxLayout()
        tools.setSpacing(6)
        tools.addWidget(QLabel("Motor columns:", host))
        self.motor_chips = QHBoxLayout()
        self.motor_chips.setSpacing(4)
        tools.addLayout(self.motor_chips)
        self.motor_picker = device_picker(host, self.client, "Add a motor column…")
        self.motor_picker.setMinimumWidth(190)
        self.motor_picker.activated.connect(self._on_motor_activated)
        self.motor_picker.lineEdit().returnPressed.connect(self._on_motor_entered)
        tools.addWidget(self.motor_picker)
        tools.addStretch(1)
        self.add_row_button = QPushButton("Add row", host)
        self.add_row_button.setIcon(material_icon("add", size=(16, 16), convert_to_pixmap=False))
        self.add_row_button.clicked.connect(self._add_row)
        tools.addWidget(self.add_row_button)
        self.grid_button = QPushButton("Fill grid…", host)
        self.grid_button.setIcon(material_icon("grid_on", size=(16, 16), convert_to_pixmap=False))
        self.grid_button.setToolTip("Create a row for every combination of motor positions")
        self.grid_button.clicked.connect(self._fill_grid)
        tools.addWidget(self.grid_button)
        self.row_tools: list[QToolButton] = []
        for icon_name, tip, slot in (
            ("arrow_upward", "Move the selected rows up", lambda: self._shift_rows(-1)),
            ("arrow_downward", "Move the selected rows down", lambda: self._shift_rows(1)),
            ("delete", "Remove the selected rows", self._remove_rows),
        ):
            btn = QToolButton(host)
            btn.setIcon(material_icon(icon_name, size=(18, 18), convert_to_pixmap=False))
            btn.setToolTip(tip)
            btn.setAutoRaise(True)
            btn.clicked.connect(slot)
            tools.addWidget(btn)
            self.row_tools.append(btn)
        layout.addLayout(tools)

        self.stack = QStackedWidget(host)
        self.empty = empty_state(
            "No measurement points yet",
            "Add a motor column, then add rows, fill a grid or paste rows from Excel. When the"
            " first pasted line holds motor names, they become the columns.",
            self.stack,
            icon="table_rows",
        )
        self.empty.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.stack.addWidget(self.empty)
        self.table = QTableWidget(host)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {theme('BORDER', '#d0d0d0').name()};"
            " border-radius: 8px; gridline-color: transparent; }"
        )
        self.stack.addWidget(self.table)
        self.empty.installEventFilter(self)
        self.table.installEventFilter(self)
        layout.addWidget(self.stack, 1)
        self.footer = hint("", host)
        layout.addWidget(self.footer)

        self._rebuild_table([])

    # --- table <-> data --------------------------------------------------------------------
    def _rebuild_table(self, rows: list[tuple]) -> None:
        """Show rows of ``(name, positions)`` or ``(name, positions, measure)``."""
        self._building = True
        self.table.clear()
        self.table.setColumnCount(FIRST_MOTOR_COLUMN + len(self.motors))
        self.table.setHorizontalHeaderLabels(["", "Sample name", *self.motors])
        self.table.setRowCount(0)
        for row in rows:
            self._append_row(*row)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(FIRST_MOTOR_COLUMN, self.table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, 150)
        self._building = False
        self._refresh_motor_chips()
        self._compile()

    def _append_row(self, name: str, positions: list, measure: bool = True) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        check = QTableWidgetItem()
        check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        check.setCheckState(Qt.CheckState.Checked if measure else Qt.CheckState.Unchecked)
        check.setToolTip("Untick to skip this row")
        self.table.setItem(row, 0, check)
        self.table.setItem(row, 1, QTableWidgetItem(name))
        for column in range(len(self.motors)):
            value = positions[column] if column < len(positions) else None
            self._set_cell(row, FIRST_MOTOR_COLUMN + column, value)

    def _set_cell(self, row: int, column: int, value) -> None:
        text = "" if value is None else model.format_value(value)
        item = QTableWidgetItem(str(value).strip() if isinstance(value, str) else text)
        if column >= FIRST_MOTOR_COLUMN:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, column, item)

    def _rows(self) -> list[tuple[bool, str, list]]:
        rows = []
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            positions = []
            for column in range(FIRST_MOTOR_COLUMN, self.table.columnCount()):
                item = self.table.item(row, column)
                positions.append(parse_number(item.text()) if item else None)
            rows.append(
                (
                    check is None or check.checkState() == Qt.CheckState.Checked,
                    name_item.text().strip() if name_item else "",
                    positions,
                )
            )
        return rows

    def _compile(self) -> None:
        """Turn the table into the sequence document."""
        steps = []
        self._cells = {}
        self._scan_ids = set()
        rows = self._rows()
        for index, (measure, name, positions) in enumerate(rows):
            if not measure:
                continue
            for column, (motor, value) in enumerate(zip(self.motors, positions)):
                if value is None:
                    continue
                node = model.move_node(motor, value)
                self._cells[node["id"]] = (index, FIRST_MOTOR_COLUMN + column)
                steps.append(node)
            scan = model.clone(self.scan)
            arguments = dict(scan.get("arguments") or {})
            if name:
                arguments["metadata"] = {"sample_name": name}
            scan["arguments"] = arguments
            self._cells[scan["id"]] = (index, 1)
            self._scan_ids.add(scan["id"])
            steps.append(scan)
        doc = model.empty_document(self.document.doc.get("id", "measurement_table"))
        if self.repeats > 1 and steps:
            steps = [model.repeat_node(self.repeats, steps)]
        doc["root"]["children"] = steps
        self.document.set_document(doc)
        self._update_labels(rows)

    def _update_labels(self, rows: list) -> None:
        if self.scan.get("name"):
            self.scan_button.setText(model.scan_title(self.scan["name"]))
            self.scan_label.setText(model.scan_details(self.scan, self.scan_entries()))
        else:
            self.scan_button.setText("Choose a scan…")
            self.scan_label.setText("")
        measured = sum(1 for r in rows if r[0])
        self.footer.setText(
            f"{len(rows)} row{'s' if len(rows) != 1 else ''}, {measured} measured"
            + (f", whole table {self.repeats}×" if self.repeats > 1 else "")
            + ". Rows are measured from top to bottom."
        )
        self.stack.setCurrentWidget(self.table if self.motors or rows else self.empty)
        self._update_buttons()

    @SafeSlot()
    def _update_buttons(self) -> None:
        self.grid_button.setEnabled(bool(self.motors))
        selected = bool(self.table.selectedIndexes())
        for button in self.row_tools:
            button.setEnabled(selected)

    def _refresh_motor_chips(self) -> None:
        while self.motor_chips.count():
            item = self.motor_chips.takeAt(0)
            if item.widget():
                item.widget().hide()  # gone at once, deleted when Qt gets to it
                item.widget().deleteLater()
        color = kind_color("set")
        for motor in self.motors:
            chip = QToolButton(self)
            chip.setText(f"{motor}  ✕")
            chip.setToolTip(f"Remove the {motor} column")
            chip.setStyleSheet(
                f"QToolButton {{ background: {rgba(color, 38)}; color: {color.name()};"
                " border: none; border-radius: 10px; padding: 3px 10px; font-weight: 600; }"
            )
            chip.clicked.connect(lambda _=False, m=motor: self._remove_motor(m))
            self.motor_chips.addWidget(chip)

    # --- interaction -----------------------------------------------------------------------
    def refresh(self) -> None:
        """The table owns the data; the document is derived from it."""

    def reset(self) -> None:
        self.motors = []
        self.scan = model.scan_node("")
        self.repeats = 1
        self.repeat_spin.blockSignals(True)
        self.repeat_spin.setValue(1)
        self.repeat_spin.blockSignals(False)
        self._rebuild_table([])

    def open_document(self, doc: dict) -> None:
        """Show an opened sequence as a table, or hand it to the Recipe editor."""
        state = table_state(doc)
        if state is None:
            self.open_in_recipe.emit(doc)
            return
        self.document.doc["id"] = doc.get("id", "measurement_table")
        self.restore_state(state)

    @SafeSlot(QTableWidgetItem)
    def _on_item_changed(self, _item) -> None:
        if not self._building:
            self._compile()

    @SafeSlot(int)
    def _on_repeats(self, value: int) -> None:
        self.repeats = value
        self._compile()

    @SafeSlot(int)
    def _on_motor_activated(self, index: int) -> None:
        self.add_motor(self.motor_picker.itemText(index))
        self.motor_picker.setCurrentText("")

    @SafeSlot()
    def _on_motor_entered(self) -> None:
        if self.motor_picker.is_valid_input:
            self.add_motor(self.motor_picker.currentText())
            self.motor_picker.setCurrentText("")

    def add_motor(self, name: str) -> None:
        """Add a motor column."""
        name = name.strip()
        if not name or name in self.motors:
            return
        rows = [(n, p + [None], m) for m, n, p in self._rows()]
        self.motors.append(name)
        self._rebuild_table(rows)

    def _remove_motor(self, motor: str) -> None:
        index = self.motors.index(motor)
        rows = [(n, p[:index] + p[index + 1 :], m) for m, n, p in self._rows()]
        self.motors.remove(motor)
        self._rebuild_table(rows)

    @SafeSlot()
    def _add_row(self) -> None:
        self._building = True
        self._append_row(f"Point {self.table.rowCount() + 1}", [])
        self._building = False
        self._compile()
        row = self.table.rowCount() - 1
        self.table.setCurrentCell(row, FIRST_MOTOR_COLUMN if self.motors else 1)
        self.table.editItem(self.table.currentItem())

    def _selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectedIndexes()})

    @SafeSlot()
    def _remove_rows(self) -> None:
        self._building = True
        for row in reversed(self._selected_rows()):
            self.table.removeRow(row)
        self._building = False
        self._compile()

    def _shift_rows(self, offset: int) -> None:
        selected = self._selected_rows()
        rows = self._rows()
        if not selected or min(selected) + offset < 0 or max(selected) + offset >= len(rows):
            return
        order = list(range(len(rows)))
        for row in selected if offset < 0 else reversed(selected):
            order[row], order[row + offset] = order[row + offset], order[row]
        self._rebuild_table([(rows[i][1], rows[i][2], rows[i][0]) for i in order])
        for row in selected:
            self.table.selectRow(row + offset)

    @SafeSlot()
    def _fill_grid(self) -> None:
        if not self.motors:
            return
        dialog = GridDialog(self.motors, self)
        if not dialog.exec():
            return
        keep = [] if dialog.replace.currentIndex() == 0 else [(n, p, m) for m, n, p in self._rows()]
        new = [(f"Point {len(keep) + i + 1}", r) for i, r in enumerate(dialog.rows())]
        self._rebuild_table(keep + new)

    @SafeSlot()
    def _edit_scan(self) -> None:
        dialog = ScanSettingsDialog(self.scan, self.client, self.scan_entries(), self)
        if dialog.exec():
            name, positional, arguments = dialog.values()
            if name:
                self.scan.update(name=name, positional=positional, arguments=arguments)
                self._compile()

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        """Paste rows from Excel and clear cells with the Delete key."""
        if obj in (self.table, self.empty) and event.type() == event.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Paste):
                self.paste(QApplication.clipboard().text())
                return True
            editing = self.table.state() == QAbstractItemView.State.EditingState
            if event.matches(QKeySequence.StandardKey.Delete) and not editing:
                self._building = True
                for item in self.table.selectedItems():
                    if item.column() >= 1:
                        item.setText("")
                self._building = False
                self._compile()
                return True
        return super().eventFilter(obj, event)

    def paste(self, text: str) -> None:
        """Paste tab-separated rows, e.g. copied from Excel.

        When the first line holds motor names after the sample name ("name, samx, samy"),
        those motors become columns and every following line becomes a new row.
        """
        lines = [line.split("\t") for line in text.strip("\n").splitlines() if line.strip()]
        if not lines:
            return
        known = set(self.backend.device_names())
        header = [cell.strip() for cell in lines[0][1:]]
        self._building = True
        if header and all(cell in known for cell in header):
            self._building = False
            for name in header:
                self.add_motor(name)
            self._building = True
            columns = [FIRST_MOTOR_COLUMN + self.motors.index(name) for name in header]
            first = self.table.rowCount()
            for offset, cells in enumerate(lines[1:]):
                name = cells[0].strip() if cells else ""
                self._append_row(name or f"Point {first + offset + 1}", [])
                for column, value in zip(columns, cells[1:]):
                    self._set_cell(first + offset, column, value)
        else:
            start_row = max(self.table.currentRow(), 0)
            start_col = max(self.table.currentColumn(), 1)
            for r, cells in enumerate(lines):
                row = start_row + r
                if row >= self.table.rowCount():
                    self._append_row(f"Point {row + 1}", [])
                for c, value in enumerate(cells):
                    if start_col + c < self.table.columnCount():
                        self._set_cell(row, start_col + c, value)
        self._building = False
        self._compile()

    def show_problems(self, problems) -> None:
        red = theme("ACCENT_EMERGENCY", "#e0534b")
        tint = QBrush(QColor(red.red(), red.green(), red.blue(), 50))
        bad: dict[tuple[int, int], str] = {}
        general = ""
        for problem in problems:
            if problem.node_id in self._scan_ids or problem.node_id not in self._cells:
                general = general or problem.message
            else:
                bad.setdefault(self._cells[problem.node_id], problem.message)
        self.scan_problem.setText(general)
        self.scan_problem.setVisible(bool(general))
        self._building = True
        for row in range(self.table.rowCount()):
            for column in range(1, self.table.columnCount()):
                item = self.table.item(row, column)
                if item is None:
                    continue
                message = bad.get((row, column), "")
                item.setBackground(tint if message else QBrush())
                item.setToolTip(message)
        self._building = False

    def save_state(self) -> dict:
        return {
            "motors": list(self.motors),
            "rows": [[name, positions, measure] for measure, name, positions in self._rows()],
            "scan": copy.deepcopy(self.scan),
            "repeats": self.repeats,
        }

    def restore_state(self, state: dict) -> None:
        self.motors = list(state.get("motors", []))
        self.scan = state.get("scan") or model.scan_node("")
        self.repeats = int(state.get("repeats", 1))
        self.repeat_spin.blockSignals(True)
        self.repeat_spin.setValue(self.repeats)
        self.repeat_spin.blockSignals(False)
        self._rebuild_table([tuple(row) for row in state.get("rows", [])])
