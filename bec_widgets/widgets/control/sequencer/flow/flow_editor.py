"""Concept 5, Flowchart: the sequence as a diagram, plus a timeline of every action.

Steps are boxes connected by arrows; loops are framed with an arrow going back up. The "+"
on each arrow inserts a step exactly there. Underneath, the timeline unrolls all loops into
the concrete list of moves and scans, so you can check exactly what will run.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QPointF, QRectF, QSize, Qt
from qtpy.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from qtpy.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.editor_base import SequenceEditorBase
from bec_widgets.widgets.control.sequencer.inspector import StepInspector
from bec_widgets.widgets.control.sequencer.style import heading, hint, kind_color, kind_icon, theme

ID_ROLE = Qt.ItemDataRole.UserRole + 1
ROOT_WIDTH = 560
BOX_H = 46
GAP = 38
PAD = 16
HEADER_H = 38
LOOP_MARGIN = 34


def _font(size: int = 10, bold: bool = False) -> QFont:
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)
    return font


class StepBox(QGraphicsPathItem):
    """A step box; clicking it selects the step."""

    def __init__(self, editor: "FlowEditor", node: dict, rect: QRectF, text: str):
        super().__init__()
        self.editor = editor
        self.node_id = node["id"]
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        self.setPath(path)
        color = kind_color(node["type"])
        problem = editor.problem_for(node["id"])
        selected = editor.document.selected == node["id"]
        fill = QColor(theme("CARD_BG", "#ffffff"))
        self.setBrush(QBrush(fill))
        if problem:
            pen = QPen(theme("ACCENT_EMERGENCY", "#e0534b"), 2.5)
        elif selected:
            pen = QPen(theme("PRIMARY", "#2f6fdf"), 2.5)
        else:
            pen = QPen(theme("BORDER", "#c8c8c8"), 1.2)
        self.setPen(pen)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(problem or "Click to edit")
        strip = QGraphicsPathItem(self)
        strip_path = QPainterPath()
        strip_path.addRoundedRect(QRectF(rect.left(), rect.top(), 7, rect.height()), 3, 3)
        strip.setPath(strip_path)
        strip.setBrush(QBrush(color))
        strip.setPen(QPen(Qt.PenStyle.NoPen))
        icon = kind_icon(node["type"], 20).pixmap(20, 20)
        pix = QGraphicsPixmapItem(icon, self)
        pix.setPos(rect.left() + 18, rect.center().y() - 10)
        label = QGraphicsSimpleTextItem(self._elide(text, rect.width() - 70), self)
        label.setFont(_font(10))
        label.setBrush(QBrush(theme("FG", "#222222")))
        label.setPos(rect.left() + 48, rect.center().y() - label.boundingRect().height() / 2)
        if problem:
            badge = QGraphicsSimpleTextItem(self._elide(problem, rect.width() * 0.6), self)
            badge.setFont(_font(8, True))
            badge.setBrush(QBrush(theme("ACCENT_EMERGENCY", "#e0534b")))
            badge.setPos(rect.right() - badge.boundingRect().width() - 10, rect.top() + 2)

    @staticmethod
    def _elide(text: str, width: float) -> str:
        max_chars = int(width / 7.2)
        return text if len(text) <= max_chars else text[: max_chars - 1] + "…"

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        self.editor.document.select(self.node_id)
        event.accept()

    def contextMenuEvent(self, event):  # pylint: disable=invalid-name
        self.editor.step_menu(self.node_id, event.screenPos())


class AddButton(QGraphicsEllipseItem):
    """Round "+" on an arrow: inserts a step at this point."""

    def __init__(self, editor: "FlowEditor", center: QPointF, parent_id: str | None, index: int):
        super().__init__(center.x() - 10, center.y() - 10, 20, 20)
        self.editor = editor
        self.parent_id = parent_id
        self.index = index
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Add a step here")
        self._set_hover(False)
        plus = QGraphicsSimpleTextItem("+", self)
        plus.setFont(_font(12, True))
        plus.setBrush(QBrush(theme("PRIMARY", "#2f6fdf")))
        box = plus.boundingRect()
        plus.setPos(center.x() - box.width() / 2, center.y() - box.height() / 2 - 1)
        self.setZValue(5)

    def _set_hover(self, hover: bool) -> None:
        primary = theme("PRIMARY", "#2f6fdf")
        fill = QColor(primary)
        fill.setAlpha(60)
        self.setBrush(QBrush(fill if hover else theme("CARD_BG", "#ffffff")))
        self.setPen(QPen(primary, 1.4))

    def hoverEnterEvent(self, _event):  # pylint: disable=invalid-name
        self._set_hover(True)

    def hoverLeaveEvent(self, _event):  # pylint: disable=invalid-name
        self._set_hover(False)

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        self.editor.insert_menu(self.parent_id, self.index, event.screenPos())
        event.accept()


class FlowEditor(SequenceEditorBase):  # pylint: disable=too-many-ancestors
    """Flowchart editor with a timeline."""

    CONCEPT_ID = "flow"
    CONCEPT_TITLE = "Flowchart"
    CONCEPT_TAGLINE = "A diagram with arrows and loop-backs, plus a timeline of every action."

    def build_editor(self, host: QWidget) -> None:
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, host)
        layout.addWidget(splitter)

        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 14, 8, 8)
        left_layout.setSpacing(8)
        left_layout.addWidget(heading("Flowchart", left))
        left_layout.addWidget(
            hint("Click a box to edit it. Click + on an arrow to add a step there.", left)
        )
        self.scene = QGraphicsScene(left)
        self.view = QGraphicsView(self.scene, left)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.view.setStyleSheet(
            f"QGraphicsView {{ border: 1px solid {theme('BORDER', '#d0d0d0').name()};"
            f" border-radius: 8px; background: {theme('BG', '#f5f5f7').name()}; }}"
        )
        left_layout.addWidget(self.view, 1)

        timeline_head = QHBoxLayout()
        timeline_head.addWidget(heading("Timeline: everything that will run, in order", left, 12))
        timeline_head.addStretch(1)
        self.timeline_count = QLabel(left)
        timeline_head.addWidget(self.timeline_count)
        left_layout.addLayout(timeline_head)
        self.timeline = QListWidget(left)
        self.timeline.setFlow(QListView.Flow.LeftToRight)
        self.timeline.setWrapping(False)
        self.timeline.setFixedHeight(92)
        self.timeline.setIconSize(QSize(18, 18))
        self.timeline.setSpacing(4)
        self.timeline.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.timeline.itemClicked.connect(
            lambda item: self.document.select(item.data(ID_ROLE) or "")
        )
        left_layout.addWidget(self.timeline)

        self.inspector = StepInspector(self.document, self.backend, splitter, client=self.client)
        self.inspector.setMinimumWidth(340)
        splitter.addWidget(left)
        splitter.addWidget(self.inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.document.selection_changed.connect(lambda _id: self.refresh())

    # --- drawing ---------------------------------------------------------------------------
    @SafeSlot()
    def refresh(self) -> None:
        if not hasattr(self, "scene"):
            return
        self.scene.clear()
        self._entries = self.scan_entries()
        root = self.document.root
        y = self._terminal("Start", 0, theme("PRIMARY", "#2f6fdf"))
        y = self._column(root, 0, y, ROOT_WIDTH)
        self._terminal("Finish", y, theme("ACCENT_SUCCESS", "#59a869"))
        if not model.children_of(root):
            note = QGraphicsSimpleTextItem("Click + to add the first step")
            note.setFont(_font(10))
            note.setBrush(QBrush(theme("FG", "#333333")))
            note.setPos(ROOT_WIDTH / 2 + 20, 32 + GAP / 2 - note.boundingRect().height() / 2)
            self.scene.addItem(note)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        self._fill_timeline()

    def _terminal(self, text: str, y: float, color: QColor) -> float:
        rect = QRectF(ROOT_WIDTH / 2 - 60, y, 120, 32)
        path = QPainterPath()
        path.addRoundedRect(rect, 16, 16)
        item = self.scene.addPath(path, QPen(Qt.PenStyle.NoPen), QBrush(color))
        label = QGraphicsSimpleTextItem(text, item)
        label.setFont(_font(10, True))
        label.setBrush(QBrush(QColor("white")))
        box = label.boundingRect()
        label.setPos(rect.center().x() - box.width() / 2, rect.center().y() - box.height() / 2)
        return y + rect.height()

    def _arrow(self, x: float, y1: float, y2: float) -> None:
        pen = QPen(theme("BORDER", "#b0b0b0").darker(115), 1.6)
        self.scene.addLine(x, y1, x, y2 - 6, pen)
        head = QPolygonF([QPointF(x - 5, y2 - 8), QPointF(x + 5, y2 - 8), QPointF(x, y2)])
        self.scene.addPolygon(head, pen, QBrush(pen.color()))

    def _column(self, container: dict, x: float, y: float, width: float) -> float:
        """Lay out a container's children top to bottom; return the bottom y."""
        center = x + width / 2
        parent_id = None if container is self.document.root else container["id"]
        children = model.children_of(container)
        for index, child in enumerate(children):
            self._arrow(center, y, y + GAP)
            self.scene.addItem(AddButton(self, QPointF(center, y + GAP / 2), parent_id, index))
            y += GAP
            y = self._step(child, x, y, width)
        self._arrow(center, y, y + GAP)
        self.scene.addItem(AddButton(self, QPointF(center, y + GAP / 2), parent_id, len(children)))
        return y + GAP

    def _step(self, node: dict, x: float, y: float, width: float) -> float:
        text = model.sentence(node, self.document.root, self._entries)
        if not model.is_container(node):
            self.scene.addItem(StepBox(self, node, QRectF(x, y, width, BOX_H), text))
            return y + BOX_H
        color = kind_color(node["type"])
        top = y
        header = StepBox(self, node, QRectF(x, y, width, HEADER_H), text)
        self.scene.addItem(header)
        inner_x = x + PAD
        inner_w = width - PAD - LOOP_MARGIN
        bottom = self._column(node, inner_x, y + HEADER_H, inner_w) + 4
        frame = QPainterPath()
        frame.addRoundedRect(QRectF(x, top, width, bottom - top), 12, 12)
        pen = QPen(color, 1.4, Qt.PenStyle.DashLine)
        fill = QColor(color)
        fill.setAlpha(22)
        item = self.scene.addPath(frame, pen, QBrush(fill))
        item.setZValue(-10)
        # loop-back arrow on the right
        loop_x = x + width - LOOP_MARGIN / 2
        back = QPainterPath(QPointF(x + inner_w + PAD, bottom - 18))
        back.lineTo(loop_x - 6, bottom - 18)
        back.quadTo(loop_x, bottom - 18, loop_x, bottom - 24)
        back.lineTo(loop_x, top + HEADER_H + 10)
        self.scene.addPath(back, QPen(color, 1.8))
        head = QPolygonF(
            [
                QPointF(loop_x - 5, top + HEADER_H + 16),
                QPointF(loop_x + 5, top + HEADER_H + 16),
                QPointF(loop_x, top + HEADER_H + 7),
            ]
        )
        self.scene.addPolygon(head, QPen(color), QBrush(color))
        label = QGraphicsSimpleTextItem(self._loop_label(node))
        label.setFont(_font(8, True))
        label.setBrush(QBrush(color))
        label.setRotation(-90)
        label.setPos(loop_x - 16, (top + HEADER_H + bottom) / 2 + label.boundingRect().width() / 2)
        self.scene.addItem(label)
        return bottom

    @staticmethod
    def _loop_label(node: dict) -> str:
        if node["type"] == "repeat":
            return f"again, {node.get('count', 1)}× in total"
        if node["type"] == "for_each":
            return f"next {node.get('variable')}"
        if node["type"] == "while":
            return "again until it arrives"
        return ""

    def _fill_timeline(self) -> None:
        self.timeline.clear()
        items = model.timeline(self.document.root, self._entries)
        for index, item in enumerate(items, 1):
            short = item.text
            if item.kind == "set" and short.startswith("Move "):
                short = short[len("Move ") :].replace(" to ", " → ")
            elif item.kind == "scan_call":
                short = short.split(":")[0].replace("Run ", "")
            entry = QListWidgetItem(kind_icon(item.kind, 18), f"{index}. {short}\n{item.context}")
            entry.setData(ID_ROLE, item.node_id)
            entry.setToolTip(f"{item.text}\n{item.context}")
            color = kind_color(item.kind)
            entry.setBackground(QBrush(QColor(color.red(), color.green(), color.blue(), 34)))
            entry.setSizeHint(QSize(200, 60))
            self.timeline.addItem(entry)
        self.timeline_count.setText(model.summarize(self.document.root).text())

    def show_problems(self, problems) -> None:
        self.refresh()

    # --- menus -----------------------------------------------------------------------------
    def insert_menu(self, parent_id: str | None, index: int, screen_pos) -> None:
        """Ask which step to insert at a "+"."""
        menu = QMenu(self)
        for kind in ("set", "scan_call", "repeat", "for_each", "while"):
            action = menu.addAction(kind_icon(kind, 16), model.KIND_TITLES[kind])
            action.setData(kind)
        chosen = menu.exec(screen_pos)
        if chosen is not None:
            self.document.add(self.document.new_nodes(chosen.data()), parent_id, index)

    def step_menu(self, node_id: str, screen_pos) -> None:
        """Right-click menu of a step."""
        doc = self.document
        menu = QMenu(self)
        actions = {
            menu.addAction(
                material_icon("arrow_upward", size=(16, 16), convert_to_pixmap=False), "Move up"
            ): lambda: doc.shift(node_id, -1),
            menu.addAction(
                material_icon("arrow_downward", size=(16, 16), convert_to_pixmap=False), "Move down"
            ): lambda: doc.shift(node_id, 1),
            menu.addAction(
                material_icon("content_copy", size=(16, 16), convert_to_pixmap=False), "Duplicate"
            ): lambda: doc.duplicate(node_id),
            menu.addAction(kind_icon("repeat", 16), "Put inside Repeat"): lambda: doc.wrap(
                node_id, "repeat"
            ),
            menu.addAction(kind_icon("for_each", 16), "Put inside For each"): lambda: doc.wrap(
                node_id, "for_each"
            ),
            menu.addAction(
                material_icon("delete", size=(16, 16), convert_to_pixmap=False), "Delete"
            ): lambda: doc.delete(node_id),
        }
        chosen = menu.exec(screen_pos)
        if chosen in actions:
            actions[chosen]()
