"""Concept 2, Blocks: Scratch-style colored blocks that are edited where they are.

Drag blocks from the palette into the sequence. Loops are C-shaped blocks that hold other
blocks. Every setting is typed straight into the block, so there is no separate form.
"""

from __future__ import annotations

import json

from bec_qthemes import material_icon
from qtpy.QtCore import QMimeData, QPoint, QRectF, Qt, Signal
from qtpy.QtGui import QColor, QDrag, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import rgba
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.editor_base import SequenceEditorBase
from bec_widgets.widgets.control.sequencer.fields import (
    NumberEdit,
    ScanPicker,
    ValuesEdit,
    device_picker,
    values_text,
)
from bec_widgets.widgets.control.sequencer.inspector import (
    RangeDialog,
    ScanSettingsDialog,
    rename_variable,
    scan_arguments,
)
from bec_widgets.widgets.control.sequencer.style import (
    heading,
    hint,
    kind_color,
    kind_icon,
    problem_label,
    theme,
)

MIME = "application/x-bec-sequence-block"
PALETTE = [
    ("set", "Move a motor", "Go to a position"),
    ("scan_call", "Run a scan", "Any scan of this beamline"),
    ("repeat", "Repeat", "Do the inside N times"),
    ("for_each", "For each value", "Once per value in a list"),
    ("while", "While moving", "Repeat inside until a motor arrives"),
]


def _mime(payload: dict) -> QMimeData:
    data = QMimeData()
    data.setData(MIME, json.dumps(payload).encode())
    return data


def _payload(mime: QMimeData) -> dict | None:
    if not mime.hasFormat(MIME):
        return None
    return json.loads(bytes(mime.data(MIME)).decode())


def _start_drag(source: QWidget, payload: dict) -> None:
    drag = QDrag(source)
    drag.setMimeData(_mime(payload))
    pixmap = source.grab()
    drag.setPixmap(pixmap.scaledToWidth(min(pixmap.width(), 360)))
    drag.setHotSpot(QPoint(12, 12))
    drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)


class PaletteTile(QFrame):
    """A block in the palette: drag it into the sequence or click to append."""

    clicked = Signal(str)

    def __init__(self, kind: str, title: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.kind = kind
        self._press: QPoint | None = None
        color = kind_color(kind)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setObjectName("PaletteTile")
        self.setStyleSheet(
            f"#PaletteTile {{ background: {rgba(color, 40)}; border: 1px solid {rgba(color, 120)};"
            f" border-left: 6px solid {color.name()}; border-radius: 8px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        icon = QLabel(self)
        icon.setPixmap(kind_icon(kind, 22).pixmap(22, 22))
        layout.addWidget(icon)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(title, self)
        font = name.font()
        font.setBold(True)
        name.setFont(font)
        texts.addWidget(name)
        texts.addWidget(hint(text, self))
        layout.addLayout(texts, 1)
        self.setToolTip("Drag into the sequence, or click to add at the end")

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        self._press = event.position().toPoint()

    def mouseMoveEvent(self, event):  # pylint: disable=invalid-name
        if (
            self._press is not None
            and (event.position().toPoint() - self._press).manhattanLength() > 6
        ):
            self._press = None
            _start_drag(self, {"new": self.kind})

    def mouseReleaseEvent(self, _event):  # pylint: disable=invalid-name
        if self._press is not None:
            self.clicked.emit(self.kind)
        self._press = None


class BlockBody(QWidget):
    """Vertical list of blocks that accepts drops between them."""

    def __init__(self, editor: "BlocksEditor", parent_id: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.editor = editor
        self.parent_id = parent_id
        self.setAcceptDrops(True)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 4, 0, 4)
        self.layout_.setSpacing(6)
        self._drop_y: int | None = None
        self.blocks: list[QWidget] = []

    def add_block(self, block: QWidget) -> None:
        """Append a block widget."""
        self.blocks.append(block)
        self.layout_.addWidget(block)

    def add_placeholder(self, text: str) -> None:
        """Show a dashed drop target when there are no blocks."""
        label = QLabel(text, self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(40)
        label.setStyleSheet(
            f"border: 2px dashed {theme('BORDER', '#c0c0c0').name()}; border-radius: 8px;"
            f" color: {rgba(theme('FG', '#333333'), 140)};"
        )
        self.layout_.addWidget(label)

    def _index_at(self, y: int) -> int:
        for index, block in enumerate(self.blocks):
            if y < block.geometry().center().y():
                return index
        return len(self.blocks)

    def _line_y(self, index: int) -> int:
        if not self.blocks:
            return 4
        if index < len(self.blocks):
            return self.blocks[index].geometry().top() - 3
        return self.blocks[-1].geometry().bottom() + 3

    def dragEnterEvent(self, event):  # pylint: disable=invalid-name
        payload = _payload(event.mimeData())
        if payload is None or payload.get("move") == self.parent_id:
            event.ignore()
            return
        event.acceptProposedAction()

    def dragMoveEvent(self, event):  # pylint: disable=invalid-name
        payload = _payload(event.mimeData())
        if payload is None:
            event.ignore()
            return
        moving = payload.get("move")
        if moving and (
            moving == self.parent_id
            or any(
                a.get("id") == moving
                for a in model.ancestors(self.editor.document.root, self.parent_id)
            )
        ):
            event.ignore()
            return
        self._drop_y = self._line_y(self._index_at(int(event.position().y())))
        self.update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, _event):  # pylint: disable=invalid-name
        self._drop_y = None
        self.update()

    def dropEvent(self, event):  # pylint: disable=invalid-name
        payload = _payload(event.mimeData())
        self._drop_y = None
        self.update()
        if payload is None:
            event.ignore()
            return
        index = self._index_at(int(event.position().y()))
        event.acceptProposedAction()
        self.editor.drop(payload, self.parent_id if self.parent_id != "root" else None, index)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        if self._drop_y is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(theme("PRIMARY", "#2f6fdf"), 3, cap=Qt.PenCapStyle.RoundCap))
        painter.drawLine(4, self._drop_y, self.width() - 4, self._drop_y)
        painter.end()


class Block(QFrame):
    """One step drawn as a colored block with its settings inline."""

    def __init__(self, editor: "BlocksEditor", node: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.editor = editor
        self.node = node
        self.kind = node["type"]
        self.color = kind_color(self.kind)
        self.problem = editor.problem_for(node["id"])
        self._press: QPoint | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(self.problem)

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(0)
        self.header = QWidget(self)
        self.row = QHBoxLayout(self.header)
        self.row.setContentsMargins(12, 7, 6, 7)
        self.row.setSpacing(6)
        grip = QLabel(self.header)
        grip.setPixmap(material_icon("drag_indicator", size=(18, 18), color=self.color.name()))
        grip.setCursor(Qt.CursorShape.OpenHandCursor)
        grip.setToolTip("Drag to move")
        self.row.addWidget(grip)
        icon = QLabel(self.header)
        icon.setPixmap(kind_icon(self.kind, 20).pixmap(20, 20))
        self.row.addWidget(icon)
        self.outer.addWidget(self.header)
        self.problem_text = problem_label(self)
        self.problem_text.setContentsMargins(42, 0, 8, 6)
        self.outer.addWidget(self.problem_text)
        getattr(self, f"_build_{self.kind}", self._build_other)()
        self.row.addStretch(1)
        delete = QToolButton(self.header)
        delete.setAutoRaise(True)
        delete.setIcon(material_icon("close", size=(16, 16), convert_to_pixmap=False))
        delete.setToolTip("Remove this block")
        delete.clicked.connect(lambda: editor.document.delete(node["id"]))
        self.row.addWidget(delete)

        self.set_problem(self.problem)
        if model.is_container(node):
            self.body = BlockBody(editor, node["id"], self)
            wrapper = QHBoxLayout()
            wrapper.setContentsMargins(22, 0, 8, 0)
            wrapper.addWidget(self.body)
            self.outer.addLayout(wrapper)
            footer = QWidget(self)
            footer.setFixedHeight(14)
            self.outer.addWidget(footer)

    def set_problem(self, message: str) -> None:
        """Show what this step still needs (or nothing)."""
        self.problem = message
        self.problem_text.setText(message)
        self.problem_text.setVisible(bool(message))
        self.setToolTip(message)
        self.update()

    # --- inline editors --------------------------------------------------------------------
    def _word(self, text: str, bold: bool = False) -> QLabel:
        label = QLabel(text, self.header)
        if bold:
            font = label.font()
            font.setBold(True)
            label.setFont(font)
        self.row.addWidget(label)
        return label

    def _field(self, widget: QWidget, width: int | None = None) -> QWidget:
        if width:
            widget.setFixedWidth(width)
        self.row.addWidget(widget)
        return widget

    def _number(self, value, width: int = 90) -> NumberEdit:
        edit = NumberEdit(self.header, "position")
        edit.set_value(value)
        return self._field(edit, width)

    def _device_combo(self, current: str, settable: bool = True):
        combo = device_picker(self.header, self.editor.client, settable=settable)
        combo.setCurrentText(current)
        return self._field(combo, 150)

    @staticmethod
    def _on_device(combo, commit) -> None:
        combo.device_selected.connect(commit)
        combo.lineEdit().editingFinished.connect(commit)

    def _build_set(self) -> None:
        node = self.node
        bound = bool(node.get("bind_status"))
        self._word("Start moving" if bound else "Move", True)
        device = self._device_combo(node.get("device", ""))
        self._word("to")
        variables = model.visible_variables(self.editor.document.root, node["id"])
        source = QComboBox(self.header)
        source.addItem("a value", None)
        for name in reversed(variables):
            source.addItem(f"each {name}", name)
        if model.is_ref(node.get("value")) and source.findData(node["value"]["ref"]) >= 0:
            source.setCurrentIndex(source.findData(node["value"]["ref"]))
        if variables:
            self._field(source)
        else:
            source.hide()
        number = self._number(node.get("value"))
        number.setVisible(source.currentData() is None)
        wait = QCheckBox("wait until it arrives", self.header)
        wait.setChecked(bool(node.get("wait", True)))
        wait.setVisible(not bound)
        self.row.addWidget(wait)

        def commit(*_):
            number.setVisible(source.currentData() is None)
            value = model.ref(source.currentData()) if source.currentData() else number.value()
            self.editor.inline_update(
                node["id"],
                device=device.currentText().strip(),
                value=value,
                wait=True if bound else wait.isChecked(),
            )

        self._on_device(device, commit)
        source.currentIndexChanged.connect(commit)
        number.edited.connect(commit)
        wait.toggled.connect(commit)

    def _build_scan_call(self) -> None:
        node = self.node
        self._word("Run", True)
        entries = self.editor.scan_entries()
        picker = ScanPicker(entries, self.header)
        picker.set_scan(node.get("name", ""))
        self._field(picker)
        details = QLabel(model.scan_details(node, entries) if node.get("name") else "", self.header)
        details.setStyleSheet(f"color: {rgba(theme('FG', '#333333'), 170)};")
        self.row.addWidget(details)
        settings = QPushButton("Settings…", self.header)
        settings.setIcon(material_icon("tune", size=(16, 16), convert_to_pixmap=False))
        settings.setEnabled(bool(node.get("name")))
        self.row.addWidget(settings)

        def open_settings(name: str | None = None):
            shown = dict(node) if not name else {"name": name}
            dialog = ScanSettingsDialog(shown, self.editor.client, entries, self)
            if dialog.exec():
                chosen, positional, arguments = dialog.values()
                if chosen:
                    self.editor.document.update(
                        node["id"], name=chosen, **scan_arguments(node, positional, arguments)
                    )
                    return
            picker.set_scan(node.get("name", ""))

        def choose(name: str):
            if name != node.get("name"):
                open_settings(name)

        picker.scan_chosen.connect(choose)
        settings.clicked.connect(lambda _checked=False: open_settings())

    def _build_repeat(self) -> None:
        node = self.node
        self._word("Repeat", True)
        spin = QSpinBox(self.header, minimum=1, maximum=100000)
        spin.setValue(int(node.get("count", 1)))
        self._field(spin, 70)
        self._word("times")
        spin.valueChanged.connect(lambda v: self.editor.inline_update(node["id"], count=v))

    def _build_for_each(self) -> None:
        node = self.node
        self._word("For each", True)
        name = QLineEdit(node.get("variable", ""), self.header)
        self._field(name, 90)
        self._word("in")
        values = ValuesEdit(self.header)
        values.set_values(node.get("values") or [])
        self._field(values)
        values.setMinimumWidth(180)
        fill = QToolButton(self.header)
        fill.setIcon(material_icon("linear_scale", size=(16, 16), convert_to_pixmap=False))
        fill.setToolTip("Fill evenly spaced values")
        fill.setAutoRaise(True)
        self.row.addWidget(fill)

        def commit(*_):
            self.editor.inline_update(node["id"], values=values.values())

        def fill_values():
            dialog = RangeDialog(self)
            if dialog.exec():
                values.setText(values_text(dialog.values()))
                commit()

        name.editingFinished.connect(lambda: self.editor.rename_variable(node, name.text()))
        values.textEdited.connect(commit)
        fill.clicked.connect(fill_values)

    def _build_while(self) -> None:
        node = self.node
        status = model.while_status(node)
        owner = model.status_owner(self.editor.document.root, status) if status else None
        self._word("While", True)
        if owner is None:
            self._word("the condition holds")
            return
        self._word(f"{owner.get('device') or 'the motor'} is moving, keep repeating:")

    def _build_other(self) -> None:
        self._word(model.sentence(self.node, self.editor.document.root), True)

    # --- painting and dragging -------------------------------------------------------------
    def paintEvent(self, event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 9, 9)
        fill = QColor(self.color)
        fill.setAlpha(42 if model.is_container(self.node) else 34)
        painter.fillPath(path, theme("CARD_BG", "#ffffff"))
        painter.fillPath(path, fill)
        border = theme("ACCENT_EMERGENCY", "#e0534b") if self.problem else QColor(self.color)
        if not self.problem:
            border.setAlpha(150)
        painter.setPen(QPen(border, 2 if self.problem else 1))
        painter.drawPath(path)
        # solid strip on the left, the "spine" of the block
        strip = QPainterPath()
        strip.addRoundedRect(QRectF(rect.left(), rect.top(), 6, rect.height()), 3, 3)
        painter.fillPath(strip, self.color)
        painter.end()
        super().paintEvent(event)

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if event.position().y() <= self.header.height():
            self._press = event.position().toPoint()

    def mouseMoveEvent(self, event):  # pylint: disable=invalid-name
        if (
            self._press is not None
            and (event.position().toPoint() - self._press).manhattanLength() > 6
        ):
            self._press = None
            _start_drag(self, {"move": self.node["id"]})

    def mouseReleaseEvent(self, _event):  # pylint: disable=invalid-name
        self._press = None


class BlocksEditor(SequenceEditorBase):
    """Scratch-style block editor."""

    # pylint: disable=too-many-ancestors, attribute-defined-outside-init

    CONCEPT_ID = "blocks"
    CONCEPT_TITLE = "Blocks"
    CONCEPT_TAGLINE = "Colored blocks you drag together and edit in place, like Scratch."

    def build_editor(self, host: QWidget) -> None:
        self._inline = False
        layout = QHBoxLayout(host)
        layout.setContentsMargins(16, 14, 16, 8)
        layout.setSpacing(16)

        palette = QWidget(host)
        palette.setFixedWidth(240)
        pal = QVBoxLayout(palette)
        pal.setContentsMargins(0, 0, 0, 0)
        pal.setSpacing(8)
        pal.addWidget(heading("Blocks", palette))
        pal.addWidget(
            hint("Drag a block into the sequence, or click it to add at the end.", palette)
        )
        for kind, title, text in PALETTE:
            tile = PaletteTile(kind, title, text, palette)
            tile.clicked.connect(self.append)
            pal.addWidget(tile)
        pal.addStretch(1)
        undo = QPushButton("Undo", palette)
        undo.setIcon(material_icon("undo", size=(16, 16), convert_to_pixmap=False))
        undo.clicked.connect(self.document.undo)
        pal.addWidget(undo)
        layout.addWidget(palette)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(heading("My sequence", host))
        self.scroll = QScrollArea(host)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {theme('BORDER', '#d0d0d0').name()};"
            " border-radius: 8px; }"
        )
        right.addWidget(self.scroll, 1)
        layout.addLayout(right, 1)

    @SafeSlot()
    def refresh(self) -> None:
        if not hasattr(self, "scroll") or self._inline:
            return
        self._blocks: dict[str, Block] = {}
        position = self.scroll.verticalScrollBar().value()
        canvas = QWidget()
        canvas.setObjectName("BlocksCanvas")
        canvas.setStyleSheet(f"#BlocksCanvas {{ background: {theme('BG', '#f5f5f7').name()}; }}")
        layout = QVBoxLayout(canvas)
        layout.setContentsMargins(14, 14, 14, 14)
        start = QLabel("▶  When I press Run", canvas)
        start.setStyleSheet(
            f"background: {theme('PRIMARY', '#2f6fdf').name()}; color: white; font-weight: 600;"
            " padding: 6px 14px; border-radius: 12px;"
        )
        start.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout.addWidget(start)
        body = BlockBody(self, "root", canvas)
        self._fill(body, self.document.root)
        layout.addWidget(body)
        layout.addStretch(1)
        self.scroll.setWidget(canvas)
        self.scroll.verticalScrollBar().setValue(position)

    def _fill(self, body: BlockBody, node: dict) -> None:
        children = model.children_of(node)
        if not children:
            body.add_placeholder(
                "Drag blocks here" if node is self.document.root else "Drop blocks inside the loop"
            )
        for child in children:
            block = Block(self, child, body)
            self._blocks[child["id"]] = block
            body.add_block(block)
            if model.is_container(child):
                self._fill(block.body, child)

    def show_problems(self, problems) -> None:
        """Update the blocks in place, so typing in a block keeps its focus."""
        messages = {p.node_id: p.message for p in problems}
        for node_id, block in getattr(self, "_blocks", {}).items():
            if block.problem != messages.get(node_id, ""):
                block.set_problem(messages.get(node_id, ""))

    # --- actions ---------------------------------------------------------------------------
    @SafeSlot(str)
    def append(self, kind: str) -> None:
        """Add a block at the end of the sequence."""
        self.document.add(self.document.new_nodes(kind))

    def drop(self, payload: dict, parent_id: str | None, index: int) -> None:
        """Handle a dropped palette tile or block."""
        if "new" in payload:
            self.document.add(self.document.new_nodes(payload["new"]), parent_id, index)
            return
        node_id = payload.get("move")
        node, parent = model.find(self.document.root, node_id)
        if node is None:
            return
        target_parent = parent_id or "root"
        if parent is not None and parent["id"] == target_parent:
            if model.children_of(parent).index(node) < index:
                index -= 1
        self.document.move(node_id, parent_id, index)

    def inline_update(self, node_id: str, **fields) -> None:
        """Store an inline edit without rebuilding the blocks (keeps keyboard focus)."""
        self._inline = True
        try:
            self.document.update(node_id, **fields)
        finally:
            self._inline = False

    def rename_variable(self, loop: dict, new_name: str) -> None:
        """Rename a for-each variable and every use of it, then redraw."""
        new_name = new_name.strip()
        if not new_name or new_name == loop.get("variable"):
            return
        rename_variable(loop, loop.get("variable"), new_name)
        self.document.update(loop["id"], variable=new_name)
