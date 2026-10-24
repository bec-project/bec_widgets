"""Concept 4, Guided: pick what you want to do, then fill in the blanks of a sentence.

Starts from the scientist's goal instead of from loops. Each goal is a sentence with inline
fields; the preview underneath lists exactly what will happen. "Fine-tune in Recipe" hands
the result to the Recipe editor for anything the sentence cannot say.
"""

from __future__ import annotations

import copy

from bec_qthemes import material_icon
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import rgba
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.editor_base import SequenceEditorBase
from bec_widgets.widgets.control.sequencer.fields import (
    NumberEdit,
    ValuesEdit,
    device_picker,
    values_text,
)
from bec_widgets.widgets.control.sequencer.inspector import RangeDialog, ScanSettingsDialog
from bec_widgets.widgets.control.sequencer.style import (
    card_qss,
    heading,
    hint,
    kind_icon,
    problem_label,
    theme,
)

GOALS = [
    (
        "positions",
        "location_on",
        "Measure at several positions",
        "Go to each position in a list and run a scan there.",
    ),
    (
        "values",
        "thermostat",
        "Step through a setting",
        "Change energy, temperature or any setting step by step, measuring at each value.",
    ),
    ("grid", "grid_on", "Map a grid", "Measure at every combination of two motor positions."),
    ("repeat", "repeat", "Repeat a measurement", "Run the same scan several times in a row."),
    (
        "during",
        "hourglass_top",
        "Measure while moving",
        "Start a slow move and keep scanning until it arrives.",
    ),
]


class FlowRow(QWidget):
    """One line of a fill-in-the-blanks sentence: words and fields side by side."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(8)

    def words(self, text: str) -> "FlowRow":
        """Add sentence text."""
        label = QLabel(text, self)
        font = label.font()
        font.setPointSize(font.pointSize() + 3)
        label.setFont(font)
        self.row.addWidget(label)
        return self

    def field(self, widget: QWidget, width: int | None = None) -> "FlowRow":
        """Add an input."""
        font = widget.font()
        font.setPointSize(font.pointSize() + 2)
        widget.setFont(font)
        if width:
            widget.setMinimumWidth(width)
        self.row.addWidget(widget)
        return self

    def end(self) -> "FlowRow":
        """Close the line."""
        self.row.addStretch(1)
        return self


class GoalCard(QFrame):
    """A selectable card describing one goal."""

    clicked = Signal(str)

    def __init__(self, key: str, icon: str, title: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("GoalCard")
        self.setFixedWidth(300)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        self.icon = QLabel(self)
        self.icon_name = icon
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        name = QLabel(title, self)
        font = name.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        name.setFont(font)
        texts.addWidget(name)
        texts.addWidget(hint(text, self))
        layout.addLayout(texts, 1)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        """Highlight the card."""
        primary = theme("PRIMARY", "#2f6fdf")
        border = primary.name() if selected else theme("BORDER", "#d0d0d0").name()
        background = rgba(primary, 30) if selected else theme("CARD_BG", "#ffffff").name()
        self.setStyleSheet(
            f"#GoalCard {{ border: {2 if selected else 1}px solid {border}; border-radius: 10px;"
            f" background: {background}; }}"
        )
        color = primary.name() if selected else theme("FG", "#333333").name()
        self.icon.setPixmap(material_icon(self.icon_name, size=(26, 26), color=color))

    def mousePressEvent(self, _event):  # pylint: disable=invalid-name
        self.clicked.emit(self.key)


class GuidedEditor(SequenceEditorBase):
    """Goal picker with fill-in-the-blanks sentences."""

    # pylint: disable=too-many-ancestors, attribute-defined-outside-init

    CONCEPT_ID = "guided"
    CONCEPT_TITLE = "Guided"
    CONCEPT_TAGLINE = "Pick a goal and fill in the blanks of a sentence; no loops to think about."

    def build_editor(self, host: QWidget) -> None:
        self.goal = "positions"
        self.scan = model.scan_node("")
        # What was typed, kept when switching goals: device, values, repeat, …
        self.memory: dict = {}
        self._field_nodes: dict[str, str] = {}
        layout = QHBoxLayout(host)
        layout.setContentsMargins(16, 14, 16, 8)
        layout.setSpacing(16)

        goals = QVBoxLayout()
        goals.setSpacing(8)
        goals.addWidget(heading("What do you want to do?", host))
        self.goal_cards: list[GoalCard] = []
        for key, icon, title, text in GOALS:
            card = GoalCard(key, icon, title, text, host)
            card.clicked.connect(self._on_goal)
            self.goal_cards.append(card)
            goals.addWidget(card)
        goals.addStretch(1)
        layout.addLayout(goals)
        self._style_goals()

        right = QVBoxLayout()
        right.setSpacing(10)
        self.sentence_card = QFrame(host)
        self.sentence_card.setObjectName("GuidedSentence")
        self.sentence_card.setStyleSheet(card_qss("#GuidedSentence", 10))
        self.sentence_layout = QVBoxLayout(self.sentence_card)
        self.sentence_layout.setContentsMargins(20, 16, 20, 16)
        self.sentence_layout.setSpacing(12)
        right.addWidget(self.sentence_card)

        preview_head = QHBoxLayout()
        preview_head.addWidget(heading("What will happen", host, 13))
        preview_head.addStretch(1)
        self.count = QLabel(host)
        preview_head.addWidget(self.count)
        right.addLayout(preview_head)
        self.preview = QListWidget(host)
        self.preview.setStyleSheet(
            f"QListWidget {{ border: 1px solid {theme('BORDER', '#d0d0d0').name()};"
            " border-radius: 8px; padding: 4px; } QListWidget::item { padding: 4px; }"
        )
        right.addWidget(self.preview, 1)
        tune = QPushButton("Fine-tune in Recipe…", host)
        tune.setIcon(material_icon("edit_note", size=(18, 18), convert_to_pixmap=False))
        tune.setToolTip("Open this sequence in the Recipe editor to add or change steps")
        tune.clicked.connect(lambda: self.open_in_recipe.emit(self.document.doc))
        right.addWidget(tune, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(right, 1)

        self.fields: dict[str, QWidget] = {}
        self._build_sentence()

    def _style_goals(self) -> None:
        for card in self.goal_cards:
            card.set_selected(card.key == self.goal)

    # --- sentence fields -------------------------------------------------------------------
    def _device(self, key: str, placeholder: str, settable: bool = False):
        picker = device_picker(self.sentence_card, self.client, placeholder, settable=settable)
        picker.setCurrentText(self.memory.get(key, ""))
        picker.device_selected.connect(self._compile)
        picker.lineEdit().editingFinished.connect(self._compile)
        self.fields[key] = picker
        return picker

    def _count_field(self, key: str, default: int) -> QSpinBox:
        spin = QSpinBox(self.sentence_card, minimum=1, maximum=100000)
        spin.setValue(int(self.memory.get(key, default)))
        spin.setSuffix(" ×")
        spin.valueChanged.connect(self._compile)
        self.fields[key] = spin
        return spin

    def _number(self, key: str) -> NumberEdit:
        edit = NumberEdit(self.sentence_card, "position")
        edit.set_value(self.memory.get(key))
        edit.edited.connect(self._compile)
        self.fields[key] = edit
        return edit

    def _values(self, key: str) -> ValuesEdit:
        edit = ValuesEdit(self.sentence_card)
        edit.set_values(self.memory.get(key, []))
        edit.textEdited.connect(self._compile)
        self.fields[key] = edit
        return edit

    def _fill_button(self, target: ValuesEdit) -> QPushButton:
        button = QPushButton("Evenly spaced…", self.sentence_card)

        def fill():
            dialog = RangeDialog(self)
            if dialog.exec():
                target.setText(values_text(dialog.values()))
                self._compile()

        button.clicked.connect(fill)
        return button

    def _scan_button(self) -> QPushButton:
        button = QPushButton(self.sentence_card)
        button.setIcon(kind_icon("scan_call", 18))
        button.setToolTip("Choose the scan and its settings")
        self.fields["scan"] = button

        def edit():
            dialog = ScanSettingsDialog(self.scan, self.client, self.scan_entries(), self)
            if dialog.exec():
                name, positional, arguments = dialog.values()
                if name:
                    self.scan.update(name=name, positional=positional, arguments=arguments)
                    self._compile()

        button.clicked.connect(edit)
        return button

    def _scan_text(self) -> str:
        if not self.scan.get("name"):
            return "Choose a scan…"
        details = model.scan_details(self.scan, self.scan_entries())
        title = model.scan_title(self.scan["name"]).lower()
        return f"{title}: {details}" if details else title

    def _line(self) -> FlowRow:
        line = FlowRow(self.sentence_card)
        self.sentence_layout.addWidget(line)
        return line

    def _build_sentence(self) -> None:
        while self.sentence_layout.count():
            item = self.sentence_layout.takeAt(0)
            if item.widget():
                item.widget().hide()  # gone at once, deleted when Qt gets to it
                item.widget().deleteLater()
        self.fields = {}
        title = next(g for g in GOALS if g[0] == self.goal)[2]
        self.sentence_layout.addWidget(heading(title, self.sentence_card, 16))
        if self.goal == "positions":
            self._line().words("Move").field(self._device("motor", "Choose a motor"), 170).words(
                "to each of these positions:"
            ).end()
            values = self._values("positions")
            self._line().field(values, 320).field(self._fill_button(values)).end()
            self._line().words("and there run a").field(self._scan_button()).end()
            self._line().words("Do all of this").field(self._count_field("repeat", 1), 90).end()
        elif self.goal == "values":
            self._line().words("Set").field(
                self._device("setting", "Choose a setting", settable=True), 170
            ).words("to each of these values:").end()
            values = self._values("setting_values")
            self._line().field(values, 320).field(self._fill_button(values)).end()
            self._line().words("and at each value run a").field(self._scan_button()).end()
            self._line().words("Do all of this").field(self._count_field("repeat", 1), 90).end()
        elif self.goal == "grid":
            slow_values = self._values("slow_values")
            self._line().words("For each").field(self._device("slow", "Choose a motor"), 150).words(
                "position"
            ).field(slow_values, 200).field(self._fill_button(slow_values)).end()
            fast_values = self._values("fast_values")
            self._line().words("go through every").field(
                self._device("fast", "Choose a motor"), 150
            ).words("position").field(fast_values, 200).field(self._fill_button(fast_values)).end()
            self._line().words("and run a").field(self._scan_button()).words("at each point.").end()
        elif self.goal == "repeat":
            self._line().words("Run a").field(self._scan_button()).end()
            self._line().field(self._count_field("count", 2), 90).words("in a row.").end()
        elif self.goal == "during":
            self._line().words("Start moving").field(
                self._device("motor", "Choose a motor"), 170
            ).words("to").field(self._number("target"), 110).end()
            self._line().words("and keep running a").field(self._scan_button()).end()
            self._line().words("until it has arrived.").end()
        self.problem = problem_label(self.sentence_card)
        self.sentence_layout.addWidget(self.problem)
        self.sentence_layout.addStretch(1)
        self._compile()

    # --- building the sequence -------------------------------------------------------------
    def _remember(self) -> None:
        for key, widget in self.fields.items():
            if isinstance(widget, ValuesEdit):
                self.memory[key] = widget.values()
            elif isinstance(widget, NumberEdit):
                self.memory[key] = widget.value()
            elif isinstance(widget, QSpinBox):
                self.memory[key] = widget.value()
            elif hasattr(widget, "currentText"):
                self.memory[key] = widget.currentText().strip()

    def _move(self, key: str, value) -> dict:
        node = model.move_node(self.memory.get(key, ""), value)
        self._field_nodes[node["id"]] = key
        return node

    def _loop(self, variable: str, key: str, children: list[dict]) -> dict:
        node = model.for_each_node(variable, self.memory.get(key, []), children)
        self._field_nodes[node["id"]] = key
        return node

    def _scan(self) -> dict:
        node = model.clone(self.scan)
        self._field_nodes[node["id"]] = "scan"
        return node

    @SafeSlot()
    def _compile(self, *_args) -> None:
        self._remember()
        self._field_nodes = {}
        memory = self.memory
        doc = model.empty_document(f"guided_{self.goal}")
        steps: list[dict] = []
        if self.goal in ("positions", "values"):
            device_key, values_key = (
                ("motor", "positions")
                if self.goal == "positions"
                else ("setting", "setting_values")
            )
            variable = "position" if self.goal == "positions" else "value"
            loop = self._loop(
                variable, values_key, [self._move(device_key, model.ref(variable)), self._scan()]
            )
            repeat = int(memory.get("repeat", 1))
            steps = [model.repeat_node(repeat, [loop])] if repeat > 1 else [loop]
        elif self.goal == "grid":
            inner = self._loop(
                "fast_position",
                "fast_values",
                [self._move("fast", model.ref("fast_position")), self._scan()],
            )
            steps = [
                self._loop(
                    "slow_position",
                    "slow_values",
                    [self._move("slow", model.ref("slow_position")), inner],
                )
            ]
        elif self.goal == "repeat":
            steps = [model.repeat_node(int(memory.get("count", 2)), [self._scan()])]
        elif self.goal == "during":
            start, loop = model.while_moving_nodes(
                memory.get("motor", ""), memory.get("target"), [self._scan()]
            )
            self._field_nodes[start["id"]] = "motor"
            steps = [start, loop]
        doc["root"]["children"] = steps
        if "scan" in self.fields:
            self.fields["scan"].setText(self._scan_text())
        self.document.set_document(doc)

    @SafeSlot()
    def refresh(self) -> None:
        if not hasattr(self, "preview"):
            return
        self.preview.clear()
        items = model.timeline(self.document.root, self.scan_entries(), limit=500)
        for index, item in enumerate(items, 1):
            text = f"{index}.  {item.text}"
            if item.context:
                text += f"      ({item.context})"
            self.preview.addItem(QListWidgetItem(kind_icon(item.kind, 16), text))
        if not items:
            self.preview.addItem("Fill in the sentence to see every step here.")
        self.count.setText(model.summarize(self.document.root).text())

    @SafeSlot(str)
    def _on_goal(self, key: str) -> None:
        self._remember()
        self.goal = key
        self._style_goals()
        self._build_sentence()

    def reset(self) -> None:
        self.memory = {}
        self.scan = model.scan_node("")
        self._build_sentence()

    def open_document(self, doc: dict) -> None:
        """A sequence from a file can have any shape, so it opens in the Recipe editor."""
        self.open_in_recipe.emit(doc)

    def save_state(self) -> dict:
        self._remember()
        return {"goal": self.goal, "scan": copy.deepcopy(self.scan), "memory": dict(self.memory)}

    def restore_state(self, state: dict) -> None:
        self.goal = state.get("goal", "positions")
        self.scan = state.get("scan") or model.scan_node("")
        self.memory = dict(state.get("memory", {}))
        self._style_goals()
        self._build_sentence()

    def show_problems(self, problems) -> None:
        red = theme("ACCENT_EMERGENCY", "#e0534b").name()
        marked = {self._field_nodes.get(p.node_id) for p in problems}
        for key, widget in self.fields.items():
            if key == "scan" or not hasattr(widget, "setStyleSheet"):
                continue
            if isinstance(widget, (ValuesEdit, QSpinBox)):
                widget.setStyleSheet(
                    f"{type(widget).__name__} {{ border: 1px solid {red}; }}"
                    if key in marked
                    else ""
                )
        scan_button = self.fields.get("scan")
        if scan_button is not None:
            scan_button.setStyleSheet(
                f"QPushButton {{ border: 1px solid {red}; }}" if "scan" in marked else ""
            )
        self.problem.setText(problems[0].message if problems else "")
        self.problem.setVisible(bool(problems))
