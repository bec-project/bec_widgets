"""Concept 4, Guided: pick what you want to do, then fill in the blanks of a sentence.

Starts from the scientist's goal instead of from loops. Each goal is a sentence with inline
fields; the preview underneath lists exactly what will happen. "Fine-tune in Recipe" hands
the result to the Recipe editor for anything the sentence cannot say.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from bec_widgets.widgets.control.sequencer.inspector import (
    RangeDialog,
    ScanSettingsDialog,
    parse_values,
    values_text,
)
from bec_widgets.widgets.control.sequencer.style import card_qss, heading, hint, kind_icon, theme

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


class GuidedEditor(SequenceEditorBase):  # pylint: disable=too-many-ancestors
    """Goal picker with fill-in-the-blanks sentences."""

    CONCEPT_ID = "guided"
    CONCEPT_TITLE = "Guided"
    CONCEPT_TAGLINE = "Pick a goal and fill in the blanks of a sentence; no loops to think about."

    open_in_recipe = Signal(dict)

    def build_editor(self, host: QWidget) -> None:
        self.goal = "positions"
        self.scan = model.scan_node(
            "line_scan", ["samy", -2, 2], {"steps": 20, "exp_time": 0.1, "relative": True}
        )
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

    # --- sentences -------------------------------------------------------------------------
    def _device_combo(self, current: str) -> QComboBox:
        combo = QComboBox(self.sentence_card)
        combo.setEditable(True)
        combo.addItems(self.backend.device_names())
        combo.setCurrentText(current)
        combo.currentTextChanged.connect(self._compile)
        return combo

    def _spin(self, value: int, suffix: str = "") -> QSpinBox:
        spin = QSpinBox(self.sentence_card, minimum=1, maximum=100000)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.valueChanged.connect(self._compile)
        return spin

    def _number(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self.sentence_card, decimals=3, minimum=-1e9, maximum=1e9)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setValue(value)
        spin.valueChanged.connect(self._compile)
        return spin

    def _values(self, values: list) -> QLineEdit:
        edit = QLineEdit(values_text(values), self.sentence_card)
        edit.setPlaceholderText("1, 2, 3")
        edit.textChanged.connect(self._compile)
        return edit

    def _fill_button(self, target: QLineEdit) -> QPushButton:
        button = QPushButton("Evenly spaced…", self.sentence_card)

        def fill():
            dialog = RangeDialog(self)
            if dialog.exec():
                target.setText(values_text(dialog.values()))

        button.clicked.connect(fill)
        return button

    def _scan_button(self) -> QPushButton:
        button = QPushButton(self.sentence_card)
        button.setIcon(kind_icon("scan_call", 18))
        button.setText(model.sentence(self.scan, None, self.scan_entries())[4:])
        button.setToolTip("Change the scan and its settings")

        def edit():
            dialog = ScanSettingsDialog(self.scan, self.client, self)
            if dialog.exec():
                name, positional, arguments = dialog.values()
                self.scan.update(name=name, positional=positional, arguments=arguments)
                button.setText(model.sentence(self.scan, None, self.scan_entries())[4:])
                self._compile()

        button.clicked.connect(edit)
        return button

    def _line(self) -> FlowRow:
        line = FlowRow(self.sentence_card)
        self.sentence_layout.addWidget(line)
        return line

    def _build_sentence(self) -> None:
        while self.sentence_layout.count():
            item = self.sentence_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        f = self.fields = {}
        title = next(g for g in GOALS if g[0] == self.goal)[2]
        self.sentence_layout.addWidget(heading(title, self.sentence_card, 16))
        if self.goal in ("positions", "values"):
            device = "samx" if self.goal == "positions" else "samz"
            f["device"] = self._device_combo(device)
            f["values"] = self._values(
                [1, -1] if self.goal == "positions" else [0.5, 1.0, 1.5, 2.0]
            )
            verb = "Move" if self.goal == "positions" else "Set"
            noun = "positions" if self.goal == "positions" else "values"
            self._line().words(verb).field(f["device"], 140).words(
                f"to each of these {noun}:"
            ).end()
            self._line().field(f["values"], 320).field(self._fill_button(f["values"])).end()
            self._line().words("and there run a").field(self._scan_button()).end()
            f["repeat"] = self._spin(2, " times")
            self._line().words("Do all of this").field(f["repeat"], 100).end()
        elif self.goal == "grid":
            f["fast"] = self._device_combo("samx")
            f["fast_values"] = self._values([0, 1, 2])
            f["slow"] = self._device_combo("samy")
            f["slow_values"] = self._values([0, 1])
            self._line().words("For each").field(f["slow"], 120).words("position").field(
                f["slow_values"], 200
            ).field(self._fill_button(f["slow_values"])).end()
            self._line().words("go through every").field(f["fast"], 120).words("position").field(
                f["fast_values"], 200
            ).field(self._fill_button(f["fast_values"])).end()
            self._line().words("and run a").field(self._scan_button()).words("at each point.").end()
        elif self.goal == "repeat":
            f["repeat"] = self._spin(5, " times")
            self._line().words("Run a").field(self._scan_button()).end()
            self._line().field(f["repeat"], 100).words("in a row.").end()
        elif self.goal == "during":
            f["device"] = self._device_combo("samx")
            f["target"] = self._number(10)
            self._line().words("Start moving").field(f["device"], 140).words("to").field(
                f["target"], 100
            ).end()
            self._line().words("and keep running a").field(self._scan_button()).end()
            self._line().words("until it has arrived.").end()
        self.sentence_layout.addStretch(1)
        self._compile()

    @SafeSlot()
    def _compile(self, *_args) -> None:
        f = self.fields
        scan = model.clone(self.scan)
        doc = model.empty_document(f"guided_{self.goal}")
        steps: list[dict] = []
        if self.goal in ("positions", "values"):
            variable = "position" if self.goal == "positions" else "value"
            loop = model.for_each_node(
                variable,
                parse_values(f["values"].text()),
                [model.move_node(f["device"].currentText(), model.ref(variable)), scan],
            )
            repeat = f["repeat"].value()
            steps = [model.repeat_node(repeat, [loop])] if repeat > 1 else [loop]
        elif self.goal == "grid":
            fast, slow = f["fast"].currentText(), f["slow"].currentText()
            inner = model.for_each_node(
                fast,
                parse_values(f["fast_values"].text()),
                [model.move_node(fast, model.ref(fast)), scan],
            )
            steps = [
                model.for_each_node(
                    slow,
                    parse_values(f["slow_values"].text()),
                    [model.move_node(slow, model.ref(slow)), inner],
                )
            ]
        elif self.goal == "repeat":
            steps = [model.repeat_node(f["repeat"].value(), [scan])]
        elif self.goal == "during":
            target = f["target"].value()
            steps = model.while_moving_nodes(
                f["device"].currentText(), int(target) if target.is_integer() else target, [scan]
            )
        doc["root"]["children"] = steps
        self.document.set_document(doc)

    @SafeSlot()
    def refresh(self) -> None:
        if not hasattr(self, "preview"):
            return
        self.preview.clear()
        items = model.timeline(self.document.root, self.scan_entries(), limit=200)
        for index, item in enumerate(items, 1):
            text = f"{index}.  {item.text}"
            if item.context:
                text += f"      — {item.context}"
            self.preview.addItem(QListWidgetItem(kind_icon(item.kind, 16), text))
        summary = model.summarize(self.document.root)
        self.count.setText(summary.text())

    @SafeSlot(str)
    def _on_goal(self, key: str) -> None:
        self.goal = key
        self._style_goals()
        self._build_sentence()

    def save_state(self) -> dict:
        return {"goal": self.goal, "scan": self.scan}

    def restore_state(self, state: dict) -> None:
        self.goal = state["goal"]
        self.scan = state["scan"]
        self._style_goals()
        self._build_sentence()

    def show_problems(self, problems) -> None:
        red = theme("ACCENT_EMERGENCY", "#e0534b")
        self.count.setStyleSheet(f"color: {red.name()};" if problems else "")
        if problems:
            self.count.setText(
                f"{model.summarize(self.document.root).text()} · {problems[0].message}"
            )
