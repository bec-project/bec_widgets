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
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
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
from bec_widgets.widgets.control.sequencer.inspector import ScanSettingsDialog
from bec_widgets.widgets.control.sequencer.style import (
    Chip,
    card_qss,
    heading,
    hint,
    kind_color,
    kind_icon,
    theme,
)

EXAMPLE_ROWS = [
    ("Sample A", [0.0, 0.0]),
    ("Sample B", [2.5, 0.0]),
    ("Sample C", [5.0, 0.0]),
    ("Reference foil", [0.0, 3.0]),
    ("Empty holder", [2.5, 3.0]),
]


class GridDialog(QDialog):
    """Generate rows for every combination of evenly spaced motor positions."""

    def __init__(self, motors: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Fill table with a grid")
        self.motors = motors
        layout = QVBoxLayout(self)
        layout.addWidget(hint("One row is created for every combination of positions.", self))
        grid = QGridLayout()
        for column, text in enumerate(("Motor", "From", "To", "Points")):
            grid.addWidget(QLabel(f"<b>{text}</b>", self), 0, column)
        self.inputs = []
        for row, motor in enumerate(motors, 1):
            start = QDoubleSpinBox(self, decimals=3, minimum=-1e6, maximum=1e6, value=0)
            stop = QDoubleSpinBox(self, decimals=3, minimum=-1e6, maximum=1e6, value=5)
            points = QSpinBox(self, minimum=1, maximum=1000, value=3)
            for column, widget in enumerate((QLabel(motor, self), start, stop, points)):
                grid.addWidget(widget, row, column)
            self.inputs.append((start, stop, points))
        layout.addLayout(grid)
        self.replace = QComboBox(self)
        self.replace.addItems(["Replace the rows", "Add below the rows"])
        layout.addWidget(self.replace)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def rows(self) -> list[list[float]]:
        """All combinations, first motor changing slowest."""
        axes = [
            [round(float(v), 6) for v in np.linspace(a.value(), b.value(), n.value())]
            for a, b, n in self.inputs
        ]
        return [list(combo) for combo in itertools.product(*axes)]


class TableEditor(SequenceEditorBase):  # pylint: disable=too-many-ancestors
    """Spreadsheet of measurement points."""

    CONCEPT_ID = "table"
    CONCEPT_TITLE = "Table"
    CONCEPT_TAGLINE = "A spreadsheet of points: one row per place to measure, paste from Excel."

    def build_editor(self, host: QWidget) -> None:
        self.motors: list[str] = ["samx", "samy"]
        self.scan = model.scan_node(
            "line_scan", ["samz", -1, 1], {"steps": 10, "exp_time": 0.1, "relative": True}
        )
        self.repeats = 1
        self._row_nodes: dict[str, int] = {}
        self._building = False

        layout = QVBoxLayout(host)
        layout.setContentsMargins(16, 14, 16, 8)
        layout.setSpacing(10)
        layout.addWidget(heading("Measurement points", host))
        layout.addWidget(
            hint(
                "Each row is one place to measure. The motors go to the row's positions, then "
                "the scan below runs. You can paste rows from Excel (Ctrl+V).",
                host,
            )
        )

        # what to do at each point
        card = QWidget(host)
        card.setObjectName("TableScanCard")
        card.setStyleSheet(card_qss("#TableScanCard"))
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        icon = QLabel(card)
        icon.setPixmap(kind_icon("scan_call", 22).pixmap(22, 22))
        row.addWidget(icon)
        row.addWidget(QLabel("<b>At every point run</b>", card))
        self.scan_label = QLabel(card)
        row.addWidget(self.scan_label, 1)
        change = QPushButton("Change scan…", card)
        change.setIcon(material_icon("tune", size=(16, 16), convert_to_pixmap=False))
        change.clicked.connect(self._edit_scan)
        row.addWidget(change)
        row.addSpacing(16)
        row.addWidget(QLabel("Measure the whole table", card))
        self.repeat_spin = QSpinBox(card, minimum=1, maximum=1000)
        self.repeat_spin.setSuffix(" ×")
        self.repeat_spin.valueChanged.connect(self._on_repeats)
        row.addWidget(self.repeat_spin)
        layout.addWidget(card)

        # toolbar
        tools = QHBoxLayout()
        tools.setSpacing(6)
        tools.addWidget(QLabel("Motors:", host))
        self.motor_chips = QHBoxLayout()
        self.motor_chips.setSpacing(4)
        tools.addLayout(self.motor_chips)
        self.add_motor = QComboBox(host)
        self.add_motor.setPlaceholderText("+ add motor column")
        self.add_motor.activated.connect(self._on_add_motor)
        tools.addWidget(self.add_motor)
        tools.addStretch(1)
        for text, icon_name, slot in (
            ("Add row", "add", self._add_row),
            ("Fill grid…", "grid_on", self._fill_grid),
            ("Remove rows", "delete", self._remove_rows),
        ):
            btn = QPushButton(text, host)
            btn.setIcon(material_icon(icon_name, size=(16, 16), convert_to_pixmap=False))
            btn.clicked.connect(slot)
            tools.addWidget(btn)
        layout.addLayout(tools)

        self.table = QTableWidget(host)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.installEventFilter(self)
        self.table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {theme('BORDER', '#d0d0d0').name()};"
            " border-radius: 8px; gridline-color: transparent; }"
        )
        layout.addWidget(self.table, 1)
        self.footer = hint("", host)
        layout.addWidget(self.footer)

        self._rebuild_table(EXAMPLE_ROWS)

    # --- table <-> data --------------------------------------------------------------------
    def _columns(self) -> list[str]:
        return ["Measure", "Sample name", *self.motors]

    def _rebuild_table(self, rows: list[tuple[str, list]]) -> None:
        self._building = True
        self.table.clear()
        self.table.setColumnCount(len(self._columns()))
        self.table.setHorizontalHeaderLabels(
            ["", "Sample name", *[f"{m} position" for m in self.motors]]
        )
        self.table.setRowCount(0)
        for name, positions in rows:
            self._append_row(name, positions)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(2, self.table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, 170)
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
        for column, value in enumerate(positions, 2):
            item = QTableWidgetItem(model.format_value(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, item)

    def _rows(self) -> list[tuple[bool, str, list]]:
        rows = []
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            positions = []
            for column in range(2, self.table.columnCount()):
                item = self.table.item(row, column)
                text = item.text().strip() if item else ""
                try:
                    positions.append(float(text) if text else None)
                except ValueError:
                    positions.append(text)
            rows.append(
                (
                    check is None or check.checkState() == Qt.CheckState.Checked,
                    name_item.text() if name_item else "",
                    positions,
                )
            )
        return rows

    def _compile(self) -> None:
        """Turn the table into the sequence document."""
        steps = []
        self._row_nodes = {}
        for index, (measure, name, positions) in enumerate(self._rows()):
            if not measure:
                continue
            for motor, value in zip(self.motors, positions):
                if value is None:
                    continue
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
                node = model.move_node(motor, value)
                self._row_nodes[node["id"]] = index
                steps.append(node)
            scan = model.clone(self.scan)
            arguments = dict(scan.get("arguments") or {})
            if name:
                arguments["metadata"] = {"sample_name": name}
            scan["arguments"] = arguments
            self._row_nodes[scan["id"]] = index
            steps.append(scan)
        doc = model.empty_document("measurement_table")
        if self.repeats > 1:
            loop = model.repeat_node(self.repeats, steps)
            doc["root"]["children"] = [loop]
        else:
            doc["root"]["children"] = steps
        self.document.set_document(doc)
        entries = self.scan_entries()
        self.scan_label.setText(model.sentence(self.scan, None, entries)[4:].capitalize())
        measured = sum(1 for r in self._rows() if r[0])
        self.footer.setText(
            f"{self.table.rowCount()} rows, {measured} measured"
            + (f", whole table {self.repeats}×" if self.repeats > 1 else "")
            + ". Rows are measured from top to bottom."
        )

    def _refresh_motor_chips(self) -> None:
        while self.motor_chips.count():
            item = self.motor_chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for motor in self.motors:
            chip = QToolButton(self)
            chip.setText(f"{motor}  ✕")
            chip.setToolTip(f"Remove the {motor} column")
            color = kind_color("set")
            chip.setStyleSheet(
                f"QToolButton {{ background: {rgba(color, 38)}; color: {color.name()};"
                " border: none; border-radius: 10px; padding: 3px 10px; font-weight: 600; }"
            )
            chip.clicked.connect(lambda _=False, m=motor: self._remove_motor(m))
            self.motor_chips.addWidget(chip)
        self.add_motor.clear()
        for name in self.backend.device_names():
            if name not in self.motors:
                self.add_motor.addItem(name)
        self.add_motor.setCurrentIndex(-1)

    # --- interaction -----------------------------------------------------------------------
    def refresh(self) -> None:
        """The table owns the data; the document is derived from it."""

    @SafeSlot(QTableWidgetItem)
    def _on_item_changed(self, _item) -> None:
        if not self._building:
            self._compile()

    @SafeSlot(int)
    def _on_repeats(self, value: int) -> None:
        self.repeats = value
        self._compile()

    @SafeSlot(int)
    def _on_add_motor(self, index: int) -> None:
        name = self.add_motor.itemText(index)
        if name and name not in self.motors:
            rows = [(n, p + [None]) for _m, n, p in self._rows()]
            self.motors.append(name)
            self._rebuild_table(rows)

    def _remove_motor(self, motor: str) -> None:
        index = self.motors.index(motor)
        rows = [(n, p[:index] + p[index + 1 :]) for _m, n, p in self._rows()]
        self.motors.remove(motor)
        self._rebuild_table(rows)

    @SafeSlot()
    def _add_row(self) -> None:
        self._building = True
        last = self._rows()[-1][2] if self.table.rowCount() else [0] * len(self.motors)
        self._append_row(f"Point {self.table.rowCount() + 1}", last)
        self._building = False
        self._compile()
        self.table.editItem(self.table.item(self.table.rowCount() - 1, 1))

    @SafeSlot()
    def _remove_rows(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        self._building = True
        for row in rows:
            self.table.removeRow(row)
        self._building = False
        self._compile()

    @SafeSlot()
    def _fill_grid(self) -> None:
        dialog = GridDialog(self.motors, self)
        if not dialog.exec():
            return
        keep = [] if dialog.replace.currentIndex() == 0 else [(n, p) for _m, n, p in self._rows()]
        new = [(f"Point {len(keep) + i + 1}", r) for i, r in enumerate(dialog.rows())]
        self._rebuild_table(keep + new)

    @SafeSlot()
    def _edit_scan(self) -> None:
        dialog = ScanSettingsDialog(self.scan, self.client, self)
        if dialog.exec():
            name, positional, arguments = dialog.values()
            self.scan.update(name=name, positional=positional, arguments=arguments)
            self._compile()

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        """Paste tab-separated rows (from Excel) into the table."""
        if obj is self.table and event.type() == event.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Paste):
                self._paste()
                return True
        return super().eventFilter(obj, event)

    def _paste(self) -> None:
        # pylint: disable=import-outside-toplevel
        from qtpy.QtWidgets import QApplication

        text = QApplication.clipboard().text()
        lines = [line.split("\t") for line in text.strip().splitlines() if line.strip()]
        if not lines:
            return
        start_row = max(self.table.currentRow(), 0)
        start_col = max(self.table.currentColumn(), 1)
        self._building = True
        for r, cells in enumerate(lines):
            row = start_row + r
            if row >= self.table.rowCount():
                self._append_row("", [None] * len(self.motors))
            for c, value in enumerate(cells):
                column = start_col + c
                if column < self.table.columnCount():
                    self.table.setItem(row, column, QTableWidgetItem(value.strip()))
        self._building = False
        self._compile()

    def show_problems(self, problems) -> None:
        bad_rows = {
            self._row_nodes[p.node_id]: p.message for p in problems if p.node_id in self._row_nodes
        }
        red = theme("ACCENT_EMERGENCY", "#e0534b")
        self._building = True
        for row in range(self.table.rowCount()):
            for column in range(1, self.table.columnCount()):
                item = self.table.item(row, column)
                if item is None:
                    continue
                if row in bad_rows:
                    item.setBackground(QBrush(QColor(red.red(), red.green(), red.blue(), 45)))
                    item.setToolTip(bad_rows[row])
                else:
                    item.setBackground(QBrush())
                    item.setToolTip("")
        self._building = False

    def save_state(self) -> dict:
        return {
            "motors": list(self.motors),
            "rows": [(name, positions, measure) for measure, name, positions in self._rows()],
            "scan": copy.deepcopy(self.scan),
            "repeats": self.repeats,
        }

    def restore_state(self, state: dict) -> None:
        self.motors = list(state["motors"])
        self.scan = state["scan"]
        self.repeats = state["repeats"]
        self.repeat_spin.blockSignals(True)
        self.repeat_spin.setValue(self.repeats)
        self.repeat_spin.blockSignals(False)
        self._rebuild_table([(name, positions) for name, positions, _m in state["rows"]])
        self._building = True
        for row, (_name, _positions, measure) in enumerate(state["rows"]):
            self.table.item(row, 0).setCheckState(
                Qt.CheckState.Checked if measure else Qt.CheckState.Unchecked
            )
        self._building = False
        self._compile()

    def screenshot_setup(self) -> None:
        """Select a cell for screenshots."""
        self.table.setCurrentCell(1, 2)
