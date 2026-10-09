"""The *Devices* and *Config* views in plain QWidgets.

QWidget twin of :mod:`devices_qml`: both render the controllers of :mod:`devices_core` with the
same layout, words and colours, so they can be compared side by side.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.applications.views.devices_views.devices_core import (
    DEVICE_CLASSES,
    KINDS,
    NEW_NAME_RULE,
    ON_FAILURE_LABELS,
    READOUT_HINT,
    READOUT_LABELS,
    ConfigEditor,
    DeviceBrowser,
    class_docstring,
)
from bec_widgets.applications.views.devices_views.staff_access import StaffAccess
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import TextButton, ToggleSwitch, field_qss, rgba

MONO = "JetBrains Mono, Menlo, DejaVu Sans Mono, monospace"


# ------------------------------------------------------------------------------- shared pieces
def tone_color(tokens: ThemeTokens, tone: str) -> QColor:
    """Colour of a state tone; only problems and work in progress are coloured."""
    return {
        "ok": tokens.success,
        "busy": tokens.primary,
        "warn": tokens.warning,
        "err": tokens.danger,
        "stale": tokens.fg_subtle,
    }.get(tone, tokens.fg_muted)


def paint_chip(painter: QPainter, rect: QRectF, text: str, tone: str, icon: str, tokens) -> float:
    """Paint a state chip (icon + word on a soft tint) at the left of ``rect``; returns its width."""
    color = tone_color(tokens, tone)
    font = QFont(painter.font())
    font.setPixelSize(11)
    font.setWeight(QFont.Weight.DemiBold)
    width = QFontMetrics(font).horizontalAdvance(text) + (30 if icon else 16)
    height = 20.0
    chip = QRectF(rect.left(), rect.center().y() - height / 2, width, height)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    soft = tokens.soft(color, 0.18 if tone != "neutral" else 0.1)
    painter.setBrush(soft)
    painter.drawRoundedRect(chip, height / 2, height / 2)
    x = chip.left() + 8
    if icon:
        pix = material_icon(icon, size=(28, 28), color=color, convert_to_pixmap=True)
        painter.drawPixmap(QRectF(x, chip.top() + 3, 14, 14).toRect(), pix)
        x += 17
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(QRectF(x, chip.top(), width, height), Qt.AlignmentFlag.AlignVCenter, text)
    painter.restore()
    return width


class Chip(QWidget):
    """State chip: icon and word on a soft tint, matching ``BecUi`` chips in the QML views."""

    def __init__(self, text: str = "", tone: str = "neutral", icon: str = "", parent=None):
        super().__init__(parent)
        self._text, self._tone, self._icon = text, tone, icon
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_chip(self, text: str, tone: str = "neutral", icon: str = "") -> None:
        """Change text, tone and icon."""
        if (text, tone, icon) != (self._text, self._tone, self._icon):
            self._text, self._tone, self._icon = text, tone, icon
            self.updateGeometry()
            self.update()

    def text(self) -> str:
        """Chip text."""
        return self._text

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        font = QFont(self.font())
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        return QSize(
            QFontMetrics(font).horizontalAdvance(self._text) + (30 if self._icon else 16), 22
        )

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        paint_chip(painter, QRectF(self.rect()), self._text, self._tone, self._icon, ThemeTokens())


def label(text: str = "", role: str = "", parent=None) -> QLabel:
    """QLabel with a style role (muted, faint, upper, title, mono, big)."""
    widget = QLabel(text, parent)
    if role:
        widget.setProperty("role", role)
    return widget


def clear_layout(layout) -> None:
    """Remove and delete every item of ``layout``, hiding widgets at once."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def vline() -> QFrame:
    """One-pixel vertical rule."""
    line = QFrame()
    line.setProperty("role", "rule")
    line.setFixedWidth(1)
    return line


def hline() -> QFrame:
    """Thin separator line."""
    line = QFrame()
    line.setProperty("role", "rule")
    line.setFixedHeight(1)
    return line


def view_qss(t: ThemeTokens) -> str:
    """Stylesheet shared by both views."""
    return field_qss(t) + f"""
        QWidget#DevicesRoot, QWidget#ConfigRoot {{ background: {t.bg.name()}; }}
        QWidget[pane="card"] {{ background: {t.card.name()}; }}
        QWidget[pane="bg"] {{ background: {t.bg.name()}; }}
        QWidget[pane="bar"] {{ background: {t.card.name()};
            border-bottom: 1px solid {t.border.name()}; }}
        QFrame[role="rule"] {{ background: {t.border.name()}; border: none; }}
        QLabel {{ color: {t.fg.name()}; font-size: 13px; background: transparent; }}
        QLabel[role="muted"] {{ color: {t.fg_muted.name()}; font-size: 12px; }}
        QLabel[role="faint"] {{ color: {t.fg_subtle.name()}; font-size: 11px; }}
        QLabel[role="upper"] {{ color: {t.fg_subtle.name()}; font-size: 11px; font-weight: 700;
            letter-spacing: 0.5px; }}
        QLabel[role="title"] {{ font-size: 14px; font-weight: 700; font-family: {MONO}; }}
        QLabel[role="mono"] {{ font-family: {MONO}; font-size: 12px; }}
        QLabel[role="big"] {{ font-size: 28px; font-weight: 600; font-family: {MONO}; }}
        QLabel[role="was"] {{ color: {t.warning.name()}; font-size: 11px; }}
        QLabel[role="err"] {{ color: {t.danger.name()}; font-size: 12px; }}
        QLabel[role="ok"] {{ color: {t.success.name()}; font-size: 12px; }}
        QLabel[role="link"] {{ color: {t.primary.name()}; font-size: 12px; }}
        QToolButton[tb="ghost"] {{ color: {t.fg.name()}; background: transparent; border: none;
            border-radius: 6px; padding: 4px 8px; font-size: 12px; }}
        QToolButton[tb="ghost"]:hover {{ background: {t.hover.name()}; }}
        QToolButton[tb="ghost"]:pressed {{ background: {t.pressed.name()}; }}
        QToolButton[tb="ghost"]:disabled {{ color: {t.fg_subtle.name()}; }}
        QToolButton::menu-indicator {{ image: none; width: 0; }}
        QPushButton[seg="true"] {{ background: transparent; color: {t.fg_muted.name()};
            border: none; border-radius: 5px; padding: 3px 10px; font-size: 12px; }}
        QPushButton[seg="true"]:checked {{ background: {t.card.name()}; color: {t.fg.name()};
            font-weight: 600; }}
        QFrame[role="segbox"] {{ background: {t.track.name()}; border-radius: 7px; }}
        QPushButton[role="linkbtn"] {{ color: {t.primary.name()}; background: transparent;
            border: none; font-size: 12px; padding: 0; }}
        QPushButton[role="problem"] {{ text-align: left; background: transparent; border: none;
            border-radius: 4px; padding: 3px 4px; color: {t.fg.name()}; font-size: 12px; }}
        QPushButton[role="problem"]:hover {{ background: {t.hover.name()}; }}
        QCheckBox {{ color: {t.fg.name()}; font-size: 12px; spacing: 6px; }}
        QTableView {{ background: {t.card.name()}; color: {t.fg.name()}; border: none;
            gridline-color: transparent; font-size: 12px;
            selection-background-color: {t.soft(t.primary, 0.18).name()};
            selection-color: {t.fg.name()}; }}
        QTableView::item {{ border-bottom: 1px solid {t.soft(t.border, 0.6).name()};
            padding: 0 6px; }}
        QTableView::item:selected {{ background: {t.soft(t.primary, 0.18).name()};
            color: {t.fg.name()}; }}
        QHeaderView::section {{ background: {t.card.name()}; color: {t.fg_muted.name()};
            border: none; border-bottom: 1px solid {t.border.name()}; padding: 4px 6px;
            font-size: 11px; font-weight: 700; }}
        QTabBar::tab {{ background: transparent; color: {t.fg_muted.name()}; padding: 6px 12px;
            border: none; border-bottom: 2px solid transparent; font-size: 12px; }}
        QTabBar::tab:selected {{ color: {t.fg.name()}; border-bottom: 2px solid
            {t.primary.name()}; font-weight: 600; }}
        QPlainTextEdit {{ background: {t.field.name()}; color: {t.fg.name()};
            border: 1px solid {t.border.name()}; border-radius: 6px;
            font-family: {MONO}; font-size: 12px; }}
        QScrollArea {{ border: none; background: transparent; }}
        QFrame[role="banner-warn"] {{ background: {t.soft(t.warning, 0.16).name()};
            border: 1px solid {rgba(t.warning, 0.5)}; border-radius: 8px; }}
        QFrame[role="banner-err"] {{ background: {t.soft(t.danger, 0.14).name()};
            border: 1px solid {rgba(t.danger, 0.5)}; border-radius: 8px; }}
        QFrame[role="banner-ok"] {{ background: {t.soft(t.success, 0.14).name()};
            border: 1px solid {rgba(t.success, 0.5)}; border-radius: 8px; }}
        QFrame[role="diffcard"] {{ background: {t.card.name()}; border: 1px solid
            {t.border.name()}; border-radius: 7px; }}
        QFrame[role="toast"] {{ background: {t.fg.name()}; border-radius: 8px; }}
        QFrame[role="toast"] QLabel {{ color: {t.bg.name()}; font-size: 12px; }}
        QFrame[role="toast"] QPushButton {{ color: {t.primary.darker(130).name() if t.dark
            else t.primary.lighter(160).name()}; background: transparent; border: none;
            font-weight: 700; font-size: 12px; }}
        QMenu {{ background: {t.card.name()}; color: {t.fg.name()}; border: 1px solid
            {t.border.name()}; border-radius: 8px; padding: 4px; }}
        QMenu::item {{ padding: 6px 18px 6px 10px; border-radius: 5px; }}
        QMenu::item:selected {{ background: {t.hover.name()}; }}
        QMenu::section {{ color: {t.fg_subtle.name()}; font-size: 11px; font-weight: 700;
            padding: 6px 10px 2px; }}
    """


def tool(text: str, icon: str, tip: str = "") -> QToolButton:
    """Ghost toolbar button with icon and text."""
    btn = QToolButton()
    btn.setProperty("tb", "ghost")
    btn.setText(text)
    btn.setProperty("icon_name", icon)
    btn.setToolButtonStyle(
        Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        if text
        else Qt.ToolButtonStyle.ToolButtonIconOnly
    )
    btn.setIconSize(QSize(16, 16))
    btn.setToolTip(tip or text)
    btn.setAccessibleName(text or tip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def retheme_icons(root: QWidget, tokens: ThemeTokens) -> None:
    """Re-tint every ghost tool button icon below ``root``."""
    for btn in root.findChildren(QToolButton):
        name = btn.property("icon_name")
        if name:
            btn.setIcon(
                material_icon(name, size=(32, 32), color=tokens.fg_muted, convert_to_pixmap=False)
            )
    for child in root.findChildren(QWidget):
        refresh = getattr(child, "refresh_theme", None)
        if callable(refresh):
            refresh(tokens)


class Banner(QFrame):
    """Inline banner (warn, err, ok) with icon, title and text."""

    def __init__(self, tone: str = "warn", parent=None):
        super().__init__(parent)
        self.setProperty("role", f"banner-{tone}")
        self._tone = tone
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)
        self.icon = QLabel()
        self.icon.setFixedSize(18, 18)
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = label("")
        self.title.setStyleSheet("font-weight: 700;")
        self.text = label("", "muted")
        self.text.setWordWrap(True)
        col.addWidget(self.title)
        col.addWidget(self.text)
        lay.addLayout(col, 1)
        self._icon_name = "lock"

    def set_content(self, icon: str, title: str, text: str) -> None:
        """Set icon, bold title and body text."""
        self._icon_name = icon
        self.title.setText(title)
        self.text.setText(text)
        self.text.setVisible(bool(text))
        self.refresh_theme(ThemeTokens())

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Re-tint the icon."""
        color = tone_color(tokens, self._tone)
        self.icon.setPixmap(material_icon(self._icon_name, size=(18, 18), color=color))


class Toasts(QWidget):
    """Bottom-right stack of short messages; one may offer Undo."""

    undo_requested = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(6)
        self.hide()

    def show_toast(self, message: str, tone: str = "neutral", undo: bool = False) -> None:
        """Show a message for five seconds."""
        frame = QFrame(self)
        frame.setProperty("role", "toast")
        row = QHBoxLayout(frame)
        row.setContentsMargins(12, 8, 8, 8)
        text = label(message)
        text.setWordWrap(True)
        text.setMinimumWidth(280)
        text.setMaximumWidth(380)
        row.addWidget(text, 1)
        if undo:
            btn = QPushButton("Undo")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(self.undo_requested.emit)
            btn.clicked.connect(frame.deleteLater)
            row.addWidget(btn)
        self._lay.addWidget(frame)
        while self._lay.count() > 3:
            old = self._lay.takeAt(0).widget()
            if old is not None:
                old.deleteLater()
        QTimer.singleShot(5000, frame, frame.deleteLater)
        QTimer.singleShot(5050, self, self._reposition)
        self.show()
        self.raise_()
        self._reposition()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if self._lay.count() == 0 or parent is None:
            self.hide()
            return
        self.adjustSize()
        self.move(parent.width() - self.width() - 16, parent.height() - self.height() - 16)


class Sheet(QDialog):
    """Window-modal sheet with a title, a sub line, a scrolling body and a footer."""

    def __init__(self, parent: QWidget, title: str, sub: str = "", wide: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(640 if wide else 420)
        tokens = ThemeTokens()
        self.setStyleSheet(view_qss(tokens) + f"QDialog {{ background: {tokens.card.name()}; }}")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)
        head = label(title)
        head.setStyleSheet("font-size: 16px; font-weight: 700;")
        outer.addWidget(head)
        if sub:
            sub_label = label(sub, "muted")
            sub_label.setWordWrap(True)
            sub_label.setTextFormat(Qt.TextFormat.RichText)
            outer.addWidget(sub_label)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        body_widget = QWidget()
        body_widget.setLayout(self.body)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body_widget)
        scroll.setSizeAdjustPolicy(QScrollArea.SizeAdjustPolicy.AdjustToContents)
        scroll.setMaximumHeight(460)
        outer.addWidget(scroll, 1)
        self.foot = QHBoxLayout()
        self.foot.setSpacing(8)
        outer.addLayout(self.foot)

    def clear_body(self) -> None:
        """Remove all body widgets."""
        clear_layout(self.body)

    def clear_foot(self) -> None:
        """Remove all footer widgets."""
        clear_layout(self.foot)


class RowsModel(QAbstractTableModel):
    """Table model over a list of row dictionaries.

    Args:
        columns: ``[(key, header)]``.
        check_key: Column key shown as a checkbox (toggling emits :attr:`toggled`).
    """

    toggled = Signal(str, bool)

    def __init__(self, columns: list[tuple[str, str]], check_key: str = "", parent=None):
        super().__init__(parent)
        self.columns = columns
        self.check_key = check_key
        self.rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        """Replace the rows; same-length updates only repaint."""
        if len(rows) == len(self.rows) and [r["name"] for r in rows] == [
            r["name"] for r in self.rows
        ]:
            self.rows = rows
            if rows:
                self.dataChanged.emit(
                    self.index(0, 0), self.index(len(rows) - 1, len(self.columns) - 1)
                )
            return
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    # pylint: disable=invalid-name, missing-function-docstring
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section][1]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        key = self.columns[index.column()][0]
        if key == self.check_key:
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if row.get(key) else Qt.CheckState.Unchecked
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return str(row.get(key, ""))
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role == Qt.ItemDataRole.ToolTipRole and key == "change":
            return row.get("changeLabel") or None
        return None

    def flags(self, index):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self.columns[index.column()][0] == self.check_key:
            base |= Qt.ItemFlag.ItemIsUserCheckable
        return base

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        key = self.columns[index.column()][0]
        if key == self.check_key and role == Qt.ItemDataRole.CheckStateRole:
            checked = value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value, 2, True)
            self.toggled.emit(self.rows[index.row()]["name"], checked)
            return True
        return False


class RowDelegate(QStyledItemDelegate):
    """Paints change marks, status chips, bold mono names and right-aligned values."""

    def paint(self, painter, option, index):
        row = index.data(Qt.ItemDataRole.UserRole)
        key = index.model().columns[index.column()][0]
        tokens = ThemeTokens()
        if row is None or key not in (
            "change",
            "status",
            "name",
            "readout",
            "valueText",
            "what",
            "on",
        ):
            super().paint(painter, option, index)
            return
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, tokens.soft(tokens.primary, 0.18))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, tokens.hover)
        rect = QRectF(option.rect.adjusted(8, 0, -8, 0))
        if key == "change" and row.get("change"):
            font = QFont(MONO.split(",")[0])
            font.setPixelSize(12)
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(tone_color(tokens, {"A": "ok", "M": "warn", "D": "err"}[row["change"]]))
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, row["change"])
        elif key == "status":
            paint_chip(
                painter, rect, row["statusText"], row["statusTone"], row["statusIcon"], tokens
            )
        elif key == "name":
            font = QFont(MONO.split(",")[0])
            font.setPixelSize(12)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(tokens.fg)
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, row["name"])
        elif key == "readout":
            painter.setPen(tokens.fg)
            text = row["readout"]
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, text)
            if row.get("readoutWas"):
                dx = painter.fontMetrics().horizontalAdvance(text + " ")
                small = QFont(painter.font())
                small.setPixelSize(11)
                painter.setFont(small)
                painter.setPen(tokens.fg_subtle)
                painter.drawText(
                    rect.adjusted(dx, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, row["readoutWas"]
                )
        elif key == "what":
            painter.setPen(tokens.fg_muted)
            text = painter.fontMetrics().elidedText(
                row["what"], Qt.TextElideMode.ElideRight, int(rect.width())
            )
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, text)
        elif key == "on":
            box = QRectF(rect.left(), rect.center().y() - 7.5, 15, 15)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(tokens.primary if row["on"] else tokens.border)
            painter.setBrush(tokens.primary if row["on"] else tokens.field)
            painter.drawRoundedRect(box, 4, 4)
            if row["on"]:
                pix = material_icon("check", size=(24, 24), color=tokens.on_primary)
                painter.drawPixmap(box.adjusted(1.5, 1.5, -1.5, -1.5).toRect(), pix)
        elif key == "valueText":
            font = QFont(MONO.split(",")[0])
            font.setPixelSize(12)
            painter.setFont(font)
            painter.setPen(tokens.fg)
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, row["valueText"]
            )
        painter.restore()

    def editorEvent(self, event, model, option, index):  # pylint: disable=invalid-name
        """Toggle the checkbox column with one click."""
        if (
            model.columns[index.column()][0] == model.check_key
            and event.type() == event.Type.MouseButtonRelease
        ):
            row = model.rows[index.row()]
            model.toggled.emit(row["name"], not row[model.check_key])
            return True
        return False


def make_table(model: RowsModel, widths: dict[str, int]) -> QTableView:
    """Read-only table with row selection, the row delegate and fixed column widths."""
    table = QTableView()
    table.setModel(model)
    table.setItemDelegate(RowDelegate(table))
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(32)
    table.setShowGrid(False)
    table.setMouseTracking(True)
    table.setWordWrap(False)
    header = table.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setHighlightSections(False)
    for col, (key, _) in enumerate(model.columns):
        if key in widths:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col, widths[key])
        else:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
    # Keep the selected row in view when the viewport changes height (first show, panels
    # appearing below the table).
    table.verticalScrollBar().rangeChanged.connect(
        lambda *_: table.currentIndex().isValid() and table.scrollTo(table.currentIndex())
    )
    return table


def select_row(table: QTableView, model: RowsModel, name: str | None) -> None:
    """Select the row of ``name`` without emitting a new selection round-trip."""
    for i, row in enumerate(model.rows):
        if row["name"] == name:
            if table.currentIndex().row() != i:
                table.blockSignals(True)
                table.selectionModel().blockSignals(True)
                table.selectRow(i)
                table.selectionModel().blockSignals(False)
                table.blockSignals(False)
            table.scrollTo(model.index(i, 0))
            return
    table.clearSelection()


class Segmented(QFrame):
    """Segmented control of checkable buttons."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], value: str, parent=None):
        super().__init__(parent)
        self.setProperty("role", "segbox")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.group = QButtonGroup(self)
        self.buttons: dict[str, QPushButton] = {}
        for key, text in options:
            btn = QPushButton(text)
            btn.setProperty("seg", "true")
            btn.setCheckable(True)
            btn.setChecked(key == value)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            self.group.addButton(btn)
            self.buttons[key] = btn
            lay.addWidget(btn)


class Sparkline(QWidget):
    """Tiny live line of recent values."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points: list[float] = []
        self.setMinimumHeight(70)
        self.setMaximumWidth(380)

    def set_points(self, points: list[float]) -> None:
        """Replace the values and repaint."""
        self.points = points
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        if len(self.points) < 2:
            return
        tokens = ThemeTokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        lo, hi = min(self.points), max(self.points)
        span = (hi - lo) or 1.0
        w, h = self.width(), self.height()
        painter.setPen(QPen(tokens.soft(tokens.border, 0.7), 1, Qt.PenStyle.DashLine))
        for frac in (0.0, 0.5, 1.0):
            y = 5 + frac * (h - 10)
            painter.drawLine(0, int(y), w, int(y))
        path = QPainterPath()
        for i, v in enumerate(self.points):
            x = i / 89 * w
            y = h - 5 - (v - lo) / span * (h - 10)
            if i:
                path.lineTo(x, y)
            else:
                path.moveTo(x, y)
        area = QPainterPath(path)
        area.lineTo((len(self.points) - 1) / 89 * w, h)
        area.lineTo(0, h)
        area.closeSubpath()
        fill = QColor(tokens.primary)
        fill.setAlphaF(0.12)
        painter.fillPath(area, fill)
        painter.setPen(QPen(tokens.primary, 1.8))
        painter.drawPath(path)
        end = path.currentPosition()
        painter.setBrush(tokens.primary)
        painter.drawEllipse(end, 3, 3)
        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(tokens.fg_subtle)
        painter.drawText(QRectF(0, 0, w - 4, 14), Qt.AlignmentFlag.AlignRight, f"{hi:.6g}")
        painter.drawText(QRectF(0, h - 14, w - 4, 14), Qt.AlignmentFlag.AlignRight, f"{lo:.6g}")


# ----------------------------------------------------------------------------------- Devices view
class DeviceRowDelegate(QStyledItemDelegate):
    """Two-line device row: bold name over what it is, live value on the right."""

    def paint(self, painter, option, index):
        row = index.data(Qt.ItemDataRole.UserRole)
        if row is None:
            return
        tokens = ThemeTokens()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, tokens.soft(tokens.primary, 0.18))
            painter.fillRect(rect.x(), rect.y(), 3, rect.height(), tokens.primary)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, tokens.hover)
        painter.setPen(tokens.soft(tokens.border, 0.6))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        inner = QRectF(rect.adjusted(14, 6, -14, -6))
        value_font = QFont(MONO.split(",", maxsplit=1)[0])
        value_font.setPixelSize(12)
        painter.setFont(value_font)
        value_w = min(QFontMetrics(value_font).horizontalAdvance(row["valueText"]) + 4, 150)
        painter.setPen(tokens.fg)
        painter.drawText(
            QRectF(inner.right() - value_w, inner.top(), value_w, inner.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            row["valueText"],
        )
        text_w = inner.width() - value_w - 12
        name_font = QFont(MONO.split(",", maxsplit=1)[0])
        name_font.setPixelSize(13)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        half = inner.height() / 2
        painter.drawText(
            QRectF(inner.left(), inner.top(), text_w, half),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(name_font).elidedText(row["name"], Qt.TextElideMode.ElideRight, text_w),
        )
        what_font = QFont()
        what_font.setPixelSize(11)
        painter.setFont(what_font)
        painter.setPen(tokens.fg_muted)
        painter.drawText(
            QRectF(inner.left(), inner.top() + half, text_w, half),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(what_font).elidedText(row["what"], Qt.TextElideMode.ElideRight, text_w),
        )
        painter.restore()

    def sizeHint(self, option, index):  # pylint: disable=invalid-name
        return QSize(300, 48)


class Panel(QFrame):
    """Bordered card with an upper-case title and an optional hint on the right."""

    def __init__(self, title: str, hint: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("role", "panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = label(title.upper(), "upper")
        head.addWidget(self.title)
        head.addStretch(1)
        self.hint = label(hint, "faint")
        head.addWidget(self.hint)
        lay.addLayout(head)
        self.body = lay


class DevicesViewQWidget(BECWidget, QWidget):
    """Devices for users: find any device, watch it live, move it and change its settings.

    QWidget version. The list on the left is compact; the device fills the rest of the view with
    a live panel (motor card, value and trend) next to its settings and readings.
    """

    RPC = False
    PLUGIN = False
    NARROW = 860

    def __init__(self, parent=None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.get_bec_shortcuts()
        self.setObjectName("DevicesRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.browser = DeviceBrowser(self.client, self.bec_dispatcher, self)
        self.open_in_workspace = self.browser.open_in_workspace
        self._motor = None
        self._signal_widgets: dict[str, dict] = {}
        self._signal_device: str | None = None
        self._build()
        self.browser.changed.connect(self._sync)
        self.browser.values_changed.connect(self._sync_values)
        self.browser.spark_changed.connect(self._sync_spark)
        self.apply_theme("")
        self._sync()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_bar())
        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_list())
        body.addWidget(vline())
        body.addWidget(self._build_detail(), 1)
        root.addLayout(body, 1)

    def _build_bar(self) -> QWidget:
        bar = QWidget()
        bar.setProperty("pane", "bar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(10)
        self.title_icon = QLabel()
        row.addWidget(self.title_icon)
        title = label("Devices")
        title.setStyleSheet("font-weight: 700;")
        row.addWidget(title)
        row.addSpacing(8)
        counts = self.browser.kind_counts()
        self.kinds = Segmented(
            [(k, f"{t}  {counts.get(k, 0)}") for k, t in KINDS], self.browser.kind
        )
        self.kinds.changed.connect(self.browser.set_kind)
        row.addWidget(self.kinds)
        row.addStretch(1)
        lock = Chip("Device setup: staff only", "neutral", "lock")
        lock.setToolTip("Adding devices and changing the session is in Device Config")
        row.addWidget(lock)
        return bar

    def _build_list(self) -> QWidget:
        left = QWidget()
        left.setProperty("pane", "card")
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left.setFixedWidth(360)
        lay = QVBoxLayout(left)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name, tag or description")
        self.search.setAccessibleName("Search devices")
        self.search.setClearButtonEnabled(True)
        self._debounce = QTimer(self, singleShot=True, interval=120)
        self._debounce.timeout.connect(lambda: self.browser.set_query(self.search.text()))
        self.search.textChanged.connect(lambda _: self._debounce.start())
        search_row = QHBoxLayout()
        search_row.setContentsMargins(12, 0, 12, 0)
        search_row.addWidget(self.search)
        lay.addLayout(search_row)
        self.shown = label("", "faint")
        self.shown.setContentsMargins(14, 2, 14, 2)
        lay.addWidget(self.shown)
        self.model = RowsModel([("name", "Device")])
        self.table = make_table(self.model, {})
        self.table.setItemDelegate(DeviceRowDelegate(self.table))
        self.table.horizontalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.selectionModel().currentRowChanged.connect(self._on_row)
        lay.addWidget(self.table, 1)
        return left

    def _build_detail(self) -> QWidget:
        self.detail = QWidget()
        self.detail.setProperty("pane", "bg")
        self.detail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.detail)
        d = QVBoxLayout(self.detail)
        d.setContentsMargins(24, 18, 24, 18)
        d.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(12)
        names = QVBoxLayout()
        names.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self.d_name = label("", "title")
        self.d_name.setStyleSheet("font-size: 20px;")
        title_row.addWidget(self.d_name)
        self.d_kind = Chip("", "neutral")
        title_row.addWidget(self.d_kind)
        self.d_disabled = Chip("Disabled in this session", "warn", "block")
        title_row.addWidget(self.d_disabled)
        title_row.addStretch(1)
        names.addLayout(title_row)
        self.d_desc = label("", "muted")
        self.d_desc.setWordWrap(True)
        names.addWidget(self.d_desc)
        head.addLayout(names, 1)
        self.action = TextButton("", "primary", "add")
        self.action.clicked.connect(self.browser.request_open)
        head.addWidget(self.action, 0, Qt.AlignmentFlag.AlignTop)
        d.addLayout(head)

        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(16)
        left_col = QVBoxLayout()
        left_col.setSpacing(16)
        right_col = QVBoxLayout()
        right_col.setSpacing(16)
        self.columns.addLayout(left_col, 1)
        self.columns.addLayout(right_col, 1)
        d.addLayout(self.columns)

        self.motor_holder = QVBoxLayout()
        left_col.addLayout(self.motor_holder)
        self.live = Panel("Live value", "last ~20 s")
        self.d_value = label("", "big")
        self.live.body.addWidget(self.d_value)
        self.spark = Sparkline()
        self.spark.setMinimumHeight(120)
        self.spark.setMaximumWidth(16777215)
        self.live.body.addWidget(self.spark)
        left_col.addWidget(self.live)
        self.about = Panel("About")
        self.facts = QGridLayout()
        self.facts.setHorizontalSpacing(16)
        self.facts.setVerticalSpacing(4)
        self.facts.setColumnStretch(1, 1)
        self.about.body.addLayout(self.facts)
        left_col.addWidget(self.about)
        left_col.addStretch(1)

        self.settings = Panel("Settings", "Applied to the device at once")
        self.settings_grid = self._signal_grid()
        self.settings.body.addLayout(self.settings_grid)
        right_col.addWidget(self.settings)
        self.readings = Panel("Readings", "live")
        self.readings_grid = self._signal_grid()
        self.readings.body.addLayout(self.readings_grid)
        right_col.addWidget(self.readings)
        right_col.addStretch(1)

        self.empty = label("Select a device to see it here.", "muted")
        d.addWidget(self.empty)
        d.addStretch(1)
        return scroll

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        # Width left for the two columns: view minus list, rule and the detail margins.
        narrow = self.width() - 361 - 48 < self.NARROW
        self.columns.setDirection(
            QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        )

    @staticmethod
    def _signal_grid() -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        return grid

    # ------------------------------------------------------------------ syncing
    def _on_row(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if current.isValid():
            self.browser.select(self.model.rows[current.row()]["name"])

    @SafeSlot()
    def _sync(self) -> None:
        rows = self.browser.rows()
        self.model.set_rows(rows)
        select_row(self.table, self.model, self.browser.selected)
        self.shown.setText(self.browser.shown_text())
        for key, btn in self.kinds.buttons.items():
            btn.setChecked(key == self.browser.kind)
        self._sync_detail()

    @SafeSlot()
    def _sync_values(self) -> None:
        self.model.set_rows(self.browser.rows())
        detail = self.browser.detail()
        if detail.get("name") and detail["kind"] != "positioner":
            self.d_value.setText(self._value_html(detail))
            self.spark.setVisible(detail["numeric"])
            self.live.hint.setVisible(detail["numeric"])
        self._update_signals()

    @staticmethod
    def _value_html(detail: dict) -> str:
        unit = detail.get("units", "")
        return f"{detail['valueText']}<span style='font-size:15px'> {unit}</span>"

    @SafeSlot()
    def _sync_spark(self) -> None:
        self.spark.set_points(self.browser.spark_points())

    def _sync_detail(self) -> None:
        detail = self.browser.detail()
        has = bool(detail.get("name"))
        self.empty.setVisible(not has)
        for w in (self.d_name, self.d_kind, self.d_desc, self.action, self.about):
            w.setVisible(has)
        clear_layout(self.facts)
        if not has:
            self.d_disabled.hide()
            self.live.hide()
            self.settings.hide()
            self.readings.hide()
            self._show_motor(None)
            return
        kind = detail["kind"]
        self._show_motor(detail["name"] if kind == "positioner" else None)
        self.d_name.setText(detail["name"])
        self.d_kind.set_chip(detail["kindLabel"], "neutral")
        self.d_disabled.setVisible(not detail["enabled"])
        self.d_desc.setText(detail["description"])
        self.live.setVisible(kind != "positioner")
        self.d_value.setText(self._value_html(detail))
        self.spark.setVisible(detail["numeric"])
        self.live.hint.setVisible(detail["numeric"])
        self.spark.set_points(self.browser.spark_points())
        for i, fact in enumerate(detail["facts"]):
            self.facts.addWidget(label(fact["label"], "muted"), i, 0)
            self.facts.addWidget(label(fact["value"]), i, 1)
        self.action.setText(detail["actionText"])
        self.action._icon_name = {"detector": "image", "monitor": "show_chart"}.get(kind, "add")
        self.action.refresh_theme(ThemeTokens())
        self._build_signals()

    def _build_signals(self) -> None:
        """Lay out the settings and readings of the selected device (on selection change)."""
        clear_layout(self.settings_grid)
        clear_layout(self.readings_grid)
        self._signal_widgets = {}
        self._signal_device = self.browser.selected
        counts = {"setting": 0, "reading": 0}
        next_row = {"setting": 0, "reading": 0}
        for row in self.browser.signal_rows():
            grid = self.settings_grid if row["section"] == "setting" else self.readings_grid
            r = next_row[row["section"]]
            next_row[row["section"]] += 2 if row["settable"] else 1
            counts[row["section"]] += 1
            name = label(row["key"], "mono")
            name.setToolTip(row["doc"] or row["key"])
            value = label(row["valueText"], "mono")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(name, r, 0)
            grid.addWidget(value, r, 1)
            widgets = {"value": value}
            if row["settable"]:
                edit = QLineEdit()
                edit.setPlaceholderText("New value")
                edit.setAccessibleName(f"New value for {row['key']}")
                edit.setFixedWidth(120)
                button = TextButton("Set", "neutral")
                key = row["key"]
                submit = lambda _=False, k=key, e=edit: self.browser.set_signal(k, e.text())
                edit.returnPressed.connect(submit)
                button.clicked.connect(submit)
                grid.addWidget(edit, r, 2)
                grid.addWidget(button, r, 3)
                status = label("", "faint")
                status.setWordWrap(True)
                status.hide()
                grid.addWidget(status, r + 1, 0, 1, 4)
                widgets.update(edit=edit, status=status)
            self._signal_widgets[row["key"]] = widgets
        self.settings.setVisible(counts["setting"] > 0)
        self.readings.setVisible(counts["reading"] > 0)

    def _update_signals(self) -> None:
        """Refresh values and set results in place, keeping typed text and focus."""
        if self._signal_device != self.browser.selected:
            self._build_signals()
            return
        for row in self.browser.signal_rows():
            widgets = self._signal_widgets.get(row["key"])
            if widgets is None:
                continue
            widgets["value"].setText(row["valueText"])
            status = widgets.get("status")
            if status is None:
                continue
            role = {"ok": "ok", "err": "err"}.get(row["statusTone"], "faint")
            if status.property("role") != role:
                status.setProperty("role", role)
                status.style().unpolish(status)
                status.style().polish(status)
            status.setText(row["statusText"])
            status.setVisible(bool(row["statusText"]))
            if row["statusTone"] == "ok" and widgets["edit"].text():
                widgets["edit"].clear()

    def _show_motor(self, name: str | None) -> None:
        if name is None:
            if self._motor is not None:
                self._motor.hide()
            return
        if self._motor is None:
            from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_qwidget import (  # pylint: disable=import-outside-toplevel
                PositionerBoxQWidget,
            )

            self._motor = PositionerBoxQWidget(parent=self.detail, device=name, client=self.client)
            self._motor.hide_device_selection = True
            self._motor.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            self.motor_holder.addWidget(self._motor)
        elif self._motor.device != name:
            self._motor.set_positioner(name)
        self._motor.show()

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        tokens = ThemeTokens()
        self.setStyleSheet(view_qss(tokens) + f"""
            QFrame[role="panel"] {{ background: {tokens.card.name()};
                border: 1px solid {tokens.border.name()}; border-radius: 8px; }}
            QFrame[role="panel"] QLabel {{ border: none; }}
            """)
        self.title_icon.setPixmap(material_icon("memory", size=(18, 18), color=tokens.fg_muted))
        retheme_icons(self, tokens)
        self.update()

    def cleanup(self):
        self.browser.cleanup()
        if self._motor is not None:
            self._motor.close()
            self._motor.deleteLater()
        super().cleanup()


# ------------------------------------------------------------------------------------ Config view
class DeviceConfigViewQWidget(BECWidget, QWidget):
    """Config for staff: edit a copy of the session config, review, then apply (QWidget version)."""

    RPC = False
    PLUGIN = False
    sign_out_requested = Signal()

    def __init__(self, parent=None, client=None, load_session: bool = True, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.get_bec_shortcuts()
        self.setObjectName("ConfigRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.editor = ConfigEditor(self.client, self.bec_dispatcher, self)
        self._tab = "form"
        self._last_detail: dict | None = None
        self._sheet: Sheet | None = None
        self._build()
        self.toasts = Toasts(self)
        self.toasts.undo_requested.connect(self.editor.undo)
        self.editor.changed.connect(self._schedule_sync)
        self.editor.toast.connect(self.toasts.show_toast)
        self.editor.apply_progress.connect(lambda *_: self._sync_apply_sheet())
        self.editor.apply_finished.connect(lambda *_: self._sync_apply_sheet(final=True))
        self._sync_timer = QTimer(self, singleShot=True, interval=0)
        self._sync_timer.timeout.connect(self._sync)
        self.apply_theme("")
        if load_session:
            self.editor.load_session()
        self._sync()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_bar())
        root.addWidget(self._build_toolbar())
        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_filters())
        body.addWidget(vline())
        center = QVBoxLayout()
        center.setSpacing(0)
        center.addWidget(self._build_table(), 1)
        center.addWidget(hline())
        center.addWidget(self._build_problems())
        center_w = QWidget()
        center_w.setLayout(center)
        body.addWidget(center_w, 1)
        body.addWidget(vline())
        body.addWidget(self._build_inspector())
        root.addLayout(body, 1)

    def _build_bar(self) -> QWidget:
        bar = QWidget()
        bar.setProperty("pane", "bar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        col = QVBoxLayout(bar)
        col.setContentsMargins(12, 8, 12, 8)
        col.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.dot = QLabel()
        self.dot.setFixedSize(9, 9)
        row.addWidget(self.dot)
        title = label("Running session")
        title.setStyleSheet("font-weight: 700;")
        row.addWidget(title)
        self.session_count = label("", "muted")
        row.addWidget(self.session_count)
        row.addSpacing(10)
        row.addWidget(self._vline_short())
        row.addSpacing(10)
        self.file_icon = QLabel()
        row.addWidget(self.file_icon)
        row.addWidget(label("Editing a copy from", "muted"))
        self.source = label("", "mono")
        self.source.setStyleSheet("font-weight: 700;")
        row.addWidget(self.source)
        self.change_chip = Chip()
        row.addWidget(self.change_chip)
        row.addStretch(1)
        self.staff_label = label("", "muted")
        self.staff_label.hide()
        row.addWidget(self.staff_label)
        self.sign_out_btn = tool("Sign out", "logout", "Lock Device Config again")
        self.sign_out_btn.clicked.connect(self.sign_out_requested)
        self.sign_out_btn.hide()
        row.addWidget(self.sign_out_btn)
        row.addSpacing(6)
        self.review_btn = TextButton("Review changes", "primary", "difference")
        self.review_btn.clicked.connect(self.open_review)
        row.addWidget(self.review_btn)
        col.addLayout(row)
        self.scan_banner = Banner("warn")
        col.addWidget(self.scan_banner)
        return bar

    @staticmethod
    def _vline_short() -> QFrame:
        line = QFrame()
        line.setProperty("role", "rule")
        line.setFixedSize(1, 18)
        return line

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setProperty("pane", "bar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(2)
        self.open_btn = tool("Open…", "folder_open")
        menu = QMenu(self.open_btn)
        menu.addAction("Open YAML file…", self.open_file_dialog)
        menu.addSeparator()
        menu.addAction("Start from the running session", self.editor.load_session)
        self.open_btn.setMenu(menu)
        self.open_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.save_btn = tool("Save", "save", "Save the edited copy as YAML (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_file_dialog)
        self.add_btn = tool("Add device", "add")
        self.add_btn.clicked.connect(self.open_add_device)
        self.remove_btn = tool("Remove", "delete")
        self.remove_btn.clicked.connect(lambda: self.editor.remove())
        self.test_btn = tool(
            "Test connection", "power", "Tests the selected device; to test everything use ⋯"
        )
        self.test_btn.clicked.connect(lambda: self.editor.test())
        self.undo_btn = tool("", "undo", "Undo (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.editor.undo)
        self.more_btn = tool("", "more_horiz", "More")
        self.more_menu = QMenu(self.more_btn)
        self.more_btn.setMenu(self.more_menu)
        self.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu.aboutToShow.connect(self._fill_more_menu)
        for w in (self.open_btn, self.save_btn):
            row.addWidget(w)
        row.addSpacing(6)
        row.addWidget(self._vline_short())
        row.addSpacing(6)
        for w in (self.add_btn, self.remove_btn, self.test_btn):
            row.addWidget(w)
        row.addSpacing(6)
        row.addWidget(self._vline_short())
        row.addSpacing(6)
        row.addWidget(self.undo_btn)
        row.addStretch(1)
        row.addWidget(self.more_btn)
        return bar

    def _fill_more_menu(self) -> None:
        self.more_menu.clear()
        self.more_menu.addAction(f"Test all {len(self.editor.work)} devices", self.editor.test_all)
        self.more_menu.addAction("Reload from running session", self.editor.load_session)
        self.more_menu.addSection("Danger zone")
        clear = self.more_menu.addAction("Clear the running session…", self.open_clear_session)
        clear.setIcon(material_icon("warning", size=(16, 16), color=ThemeTokens().danger))

    def _build_filters(self) -> QWidget:
        pane = QWidget()
        pane.setProperty("pane", "bg")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pane.setFixedWidth(220)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(220)
        scroll.setWidget(pane)
        self.filters = QVBoxLayout(pane)
        self.filters.setContentsMargins(10, 10, 10, 10)
        self.filters.setSpacing(4)
        self.filters.addWidget(label("SEARCH", "upper"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Name, class, tag or PV prefix")
        self.search.setAccessibleName("Search devices")
        self._debounce = QTimer(self, singleShot=True, interval=120)
        self._debounce.timeout.connect(lambda: self.editor.set_query(self.search.text()))
        self.search.textChanged.connect(lambda _: self._debounce.start())
        self.filters.addWidget(self.search)
        self.facet_box = QVBoxLayout()
        self.facet_box.setSpacing(3)
        self.filters.addLayout(self.facet_box)
        self.filters.addStretch(1)
        self._facet_key = None
        return scroll

    def _build_table(self) -> QWidget:
        pane = QWidget()
        pane.setProperty("pane", "card")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(10, 6, 10, 6)
        self.showing = label("", "muted")
        head.addWidget(self.showing)
        head.addStretch(1)
        self.clear_filters_btn = QPushButton("Clear filters")
        self.clear_filters_btn.setProperty("role", "linkbtn")
        self.clear_filters_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        head.addWidget(self.clear_filters_btn)
        lay.addLayout(head)
        self.model = RowsModel(
            [
                ("change", "Δ"),
                ("status", "Status"),
                ("name", "Name"),
                ("deviceClass", "Class"),
                ("readout", "Readout"),
                ("on", "On"),
                ("tags", "Tags"),
            ],
            check_key="on",
        )
        self.model.toggled.connect(lambda name, on: self.editor.set_field(name, "enabled", on))
        self.table = make_table(
            self.model,
            {
                "change": 30,
                "status": 150,
                "name": 130,
                "deviceClass": 130,
                "readout": 150,
                "on": 40,
            },
        )
        self.table.model().headerData  # noqa: B018 - keep a reference for tooltips
        self.table.selectionModel().currentRowChanged.connect(self._on_row)
        self.table.installEventFilter(self)
        lay.addWidget(self.table, 1)
        return pane

    def _build_problems(self) -> QWidget:
        pane = QWidget()
        pane.setProperty("pane", "bg")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(6)
        title = label("Problems")
        title.setStyleSheet("font-weight: 700; font-size: 12px;")
        head.addWidget(title)
        self.problem_chip = Chip("0", "err")
        head.addWidget(self.problem_chip)
        self.unchecked_label = label("", "muted")
        head.addWidget(self.unchecked_label)
        head.addStretch(1)
        lay.addLayout(head)
        self.problem_list = QVBoxLayout()
        self.problem_list.setSpacing(1)
        lay.addLayout(self.problem_list)
        pane.setMaximumHeight(150)
        return pane

    def _build_inspector(self) -> QWidget:
        pane = QWidget()
        pane.setProperty("pane", "bg")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pane.setFixedWidth(340)
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QWidget()
        h = QVBoxLayout(head)
        h.setContentsMargins(12, 10, 12, 8)
        h.setSpacing(5)
        top = QHBoxLayout()
        self.i_name = label("", "title")
        self.i_class = label("", "muted")
        self.revert_btn = TextButton("Revert", "neutral", "undo")
        self.revert_btn.setMinimumHeight(26)
        self.revert_btn.clicked.connect(lambda: self.editor.revert())
        top.addWidget(self.i_name)
        top.addWidget(self.i_class)
        top.addStretch(1)
        top.addWidget(self.revert_btn)
        h.addLayout(top)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.i_status = Chip()
        self.i_new = Chip("New — not in session", "ok", "add")
        chips.addWidget(self.i_status)
        chips.addWidget(self.i_new)
        chips.addStretch(1)
        h.addLayout(chips)
        self.i_status_msg = label("", "err")
        self.i_status_msg.setWordWrap(True)
        h.addWidget(self.i_status_msg)
        lay.addWidget(head)
        tabs = QHBoxLayout()
        tabs.setContentsMargins(12, 0, 12, 0)
        self.tab_buttons = {}
        for key, text in (("form", "Form"), ("yaml", "YAML"), ("docs", "Docs")):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setProperty("seg", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._set_tab(k))
            self.tab_buttons[key] = btn
            tabs.addWidget(btn)
        tabs.addStretch(1)
        tab_box = QFrame()
        tab_box.setLayout(tabs)
        lay.addWidget(tab_box)
        lay.addWidget(hline())
        self.stack = QStackedWidget()
        self.form = QWidget()
        self.form_lay = QVBoxLayout(self.form)
        self.form_lay.setContentsMargins(12, 12, 12, 12)
        self.form_lay.setSpacing(10)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_scroll.setWidget(self.form)
        self.yaml_view = QPlainTextEdit()
        self.yaml_view.setReadOnly(True)
        yaml_page = QWidget()
        y = QVBoxLayout(yaml_page)
        y.setContentsMargins(12, 12, 12, 12)
        y.addWidget(self.yaml_view, 1)
        note = label(
            "Saved as plain YAML; only keys that differ from defaults are listed.", "faint"
        )
        note.setWordWrap(True)
        y.addWidget(note)
        self.docs_view = label("", "muted")
        self.docs_view.setWordWrap(True)
        self.docs_view.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.docs_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        docs_scroll = QScrollArea()
        docs_scroll.setWidgetResizable(True)
        docs_page = QWidget()
        dp = QVBoxLayout(docs_page)
        dp.setContentsMargins(12, 12, 12, 12)
        self.docs_title = label("")
        self.docs_title.setStyleSheet("font-weight: 700;")
        dp.addWidget(self.docs_title)
        dp.addWidget(self.docs_view, 1)
        docs_scroll.setWidget(docs_page)
        self.empty_inspector = label("Select a device to see and edit its configuration.", "muted")
        self.empty_inspector.setContentsMargins(20, 20, 20, 20)
        self.empty_inspector.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.empty_inspector.setWordWrap(True)
        for page in (form_scroll, yaml_page, docs_scroll, self.empty_inspector):
            self.stack.addWidget(page)
        lay.addWidget(self.stack, 1)
        self.inspector_head = head
        self.inspector_tabs = tab_box
        return pane

    # ------------------------------------------------------------------ syncing
    def _schedule_sync(self) -> None:
        self._sync_timer.start()

    @SafeSlot()
    def _sync(self) -> None:
        bar = self.editor.bar_state()
        tokens = ThemeTokens()
        self.session_count.setText(f"{bar['sessionCount']} devices · connected")
        self.source.setText(bar["source"])
        if bar["changeCount"]:
            self.change_chip.set_chip(bar["changeText"], "warn")
        else:
            self.change_chip.set_chip(bar["changeText"], "ok", "check")
        self.review_btn.setText(bar["reviewText"])
        self.review_btn.setEnabled(bool(bar["changeCount"]))
        self.review_btn.setToolTip(
            "You can review now; applying waits until the scan finishes"
            if bar["scanRunning"]
            else "See exactly what will change in the running session, then apply"
        )
        self.scan_banner.setVisible(bar["scanRunning"])
        if bar["scanRunning"]:
            self.scan_banner.set_content(
                "lock",
                bar["scanText"],
                "You can keep editing and reviewing. Applying to the session is locked until the "
                "scan ends.",
            )
        self.dot.setStyleSheet(f"background: {tokens.success.name()}; border-radius: 4px;")
        self.undo_btn.setEnabled(bar["canUndo"])
        self.remove_btn.setEnabled(bar["hasSelection"])
        self.test_btn.setEnabled(bar["hasSelection"])
        rows = self.editor.rows()
        self.model.set_rows(rows)
        select_row(self.table, self.model, self.editor.selected)
        self.showing.setText(f"Showing {len(rows)} of {len(self.editor.work)} devices")
        self.clear_filters_btn.setVisible(self.editor.filters_active())
        self._sync_facets()
        self._sync_problems()
        self._sync_inspector()
        if self._sheet is not None and self._sheet.property("kind") == "review":
            self._fill_review(self._sheet)

    def _sync_facets(self) -> None:
        sections = self.editor.facet_sections()
        key = repr(sections)
        if key == self._facet_key:
            return
        self._facet_key = key
        clear_layout(self.facet_box)
        for section in sections:
            if not section["items"]:
                continue
            spacer = label(section["title"].upper(), "upper")
            spacer.setContentsMargins(0, 10, 0, 2)
            self.facet_box.addWidget(spacer)
            for item in section["items"]:
                row = QWidget()
                r = QHBoxLayout(row)
                r.setContentsMargins(0, 0, 0, 0)
                box = QCheckBox(item["label"])
                box.setChecked(item["checked"])
                box.toggled.connect(
                    lambda on, k=section["key"], v=item["value"]: self.editor.toggle_facet(k, v, on)
                )
                r.addWidget(box, 1)
                count = label(str(item["count"]), "faint")
                count.setStyleSheet(f"font-family: {MONO};")
                r.addWidget(count)
                self.facet_box.addWidget(row)

    def _sync_problems(self) -> None:
        problems = self.editor.problems()
        n_err, n_unchecked = self.editor.problem_counts()
        self.problem_chip.set_chip(str(n_err), "err" if n_err else "neutral")
        self.unchecked_label.setText(f"· {n_unchecked} not checked")
        clear_layout(self.problem_list)
        tokens = ThemeTokens()
        for p in problems[:4]:
            btn = QPushButton()
            btn.setProperty("role", "problem")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            r = QHBoxLayout(btn)
            r.setContentsMargins(4, 2, 4, 2)
            r.setSpacing(8)
            icon = QLabel()
            unchecked = p["state"] == "unchecked"
            icon.setPixmap(
                material_icon(
                    "help" if unchecked else "warning",
                    size=(14, 14),
                    color=tokens.fg_subtle if unchecked else tokens.danger,
                )
            )
            r.addWidget(icon)
            name = label(p["name"], "mono")
            name.setStyleSheet("font-weight: 700;")
            r.addWidget(name)
            msg = label(p["message"], "muted")
            r.addWidget(msg, 1)
            r.addWidget(label("Select", "link"))
            btn.setMinimumHeight(24)
            btn.clicked.connect(lambda _=False, n=p["name"]: self.editor.select(n))
            self.problem_list.addWidget(btn)
        if len(problems) > 4:
            self.problem_list.addWidget(label(f"and {len(problems) - 4} more", "faint"))

    def _sync_inspector(self) -> None:
        detail = self.editor.detail()
        if detail == self._last_detail:
            return
        self._last_detail = detail
        has = bool(detail.get("name"))
        self.inspector_head.setVisible(has)
        self.inspector_tabs.setVisible(has)
        if not has:
            self.stack.setCurrentWidget(self.empty_inspector)
            return
        self.i_name.setText(detail["name"])
        self.i_class.setText(detail["shortClass"])
        self.revert_btn.setVisible(detail["isModified"])
        self.i_status.set_chip(detail["statusText"], detail["statusTone"], detail["statusIcon"])
        self.i_new.setVisible(detail["isNew"])
        self.i_status_msg.setText(detail["statusMessage"])
        self.i_status_msg.setVisible(bool(detail["statusMessage"]))
        for key, btn in self.tab_buttons.items():
            btn.setChecked(key == self._tab)
        self.yaml_view.setPlainText(detail["yaml"])
        if self._tab == "docs":
            self.docs_title.setText(detail["shortClass"])
            self.docs_view.setText(class_docstring(detail["deviceClass"]))
        self._fill_form(detail)
        self.stack.setCurrentIndex({"form": 0, "yaml": 1, "docs": 2}[self._tab])

    def _set_tab(self, key: str) -> None:
        self._tab = key
        self._last_detail = None
        self._sync_inspector()

    def _fill_form(self, d: dict) -> None:
        lay = self.form_lay
        clear_layout(lay)
        name = d["name"]

        def was(text: str) -> None:
            if text:
                note = label(f"↳ {text}", "was")
                note.setWordWrap(True)
                lay.addWidget(note)

        def field_label(text: str) -> QLabel:
            lbl = label(text)
            lbl.setStyleSheet("font-weight: 600; font-size: 12px;")
            return lbl

        lay.addWidget(field_label("Readout priority"))
        rp = QComboBox()
        rp.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        rp.setMinimumContentsLength(10)
        for key, text in READOUT_LABELS.items():
            rp.addItem(text, key)
        if rp.findData(d["readout"]) < 0:
            rp.addItem(d["readout"], d["readout"])
        rp.setCurrentIndex(rp.findData(d["readout"]))
        rp.activated.connect(
            lambda i: self.editor.set_field(name, "readoutPriority", rp.itemData(i))
        )
        lay.addWidget(rp)
        hint = label(READOUT_HINT, "faint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        was(d["readoutWas"])

        row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(field_label("Enabled"))
        note = label("Disabled devices stay in the file but are not loaded", "faint")
        note.setWordWrap(True)
        col.addWidget(note)
        row.addLayout(col, 1)
        switch = ToggleSwitch()
        switch.setFixedWidth(42)
        switch.setAccessibleName("Enabled")
        switch.setChecked(d["enabled"])
        switch.toggled.connect(lambda on: self.editor.set_field(name, "enabled", on))
        row.addWidget(switch)
        holder = QWidget()
        holder.setLayout(row)
        lay.addWidget(holder)
        was(d["enabledWas"])

        lay.addWidget(field_label("If reading fails"))
        of = QComboBox()
        of.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        of.setMinimumContentsLength(10)
        for key, text in ON_FAILURE_LABELS.items():
            of.addItem(f"{text} ({key})", key)
        of.setCurrentIndex(max(0, of.findData(d["onFailure"])))
        of.activated.connect(lambda i: self.editor.set_field(name, "onFailure", of.itemData(i)))
        lay.addWidget(of)
        was(d["onFailureWas"])

        lay.addWidget(field_label("Description"))
        desc = QLineEdit(d["description"])
        desc.setPlaceholderText("What this device is, for colleagues")
        desc.editingFinished.connect(
            lambda: self.editor.set_field(name, "description", desc.text())
        )
        lay.addWidget(desc)
        was(d["descriptionWas"])

        lay.addWidget(label("TAGS", "upper"))
        tags = QHBoxLayout()
        tags.setSpacing(4)
        for tag in d["tags"]:
            chip = QToolButton()
            chip.setProperty("tb", "ghost")
            chip.setText(f"{tag}  ✕")
            chip.setToolTip(f"Remove the tag {tag}")
            chip.clicked.connect(lambda _=False, t=tag: self.editor.remove_tag(name, t))
            tags.addWidget(chip)
        add_tag = QLineEdit()
        add_tag.setPlaceholderText("Add tag")
        add_tag.setFixedWidth(90)
        add_tag.returnPressed.connect(lambda: self.editor.add_tag(name, add_tag.text()))
        tags.addWidget(add_tag)
        tags.addStretch(1)
        tags_w = QWidget()
        tags_w.setLayout(tags)
        lay.addWidget(tags_w)
        was(d["tagsWas"])

        lay.addWidget(label("DEVICE CONFIG", "upper"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        for i, item in enumerate(d["deviceConfig"]):
            key_label = label(item["key"], "mono")
            key_label.setProperty("role", "muted")
            grid.addWidget(key_label, 2 * i, 0)
            edit = QLineEdit(item["value"])
            edit.setStyleSheet(f"font-family: {MONO}; font-size: 12px; min-height: 26px;")
            edit.editingFinished.connect(
                lambda e=edit, k=item["key"]: self.editor.set_config_value(name, k, e.text())
            )
            grid.addWidget(edit, 2 * i, 1)
            if item["was"]:
                grid.addWidget(label(f"↳ {item['was']}", "was"), 2 * i + 1, 1)
        if not d["deviceConfig"]:
            grid.addWidget(label("No deviceConfig keys", "faint"), 0, 0, 1, 2)
        grid_w = QWidget()
        grid_w.setLayout(grid)
        lay.addWidget(grid_w)
        if d["extra"]:
            lay.addWidget(label("OTHER KEYS · KEPT AS THEY ARE", "upper"))
            for item in d["extra"]:
                lay.addWidget(label(f"{item['key']}: {item['value']}", "mono"))

        test_row = QHBoxLayout()
        test = TextButton("Test connection", "neutral", "power")
        test.clicked.connect(lambda: self.editor.test(name))
        test_row.addWidget(test)
        note = label("Result appears here, no dialog", "faint")
        note.setWordWrap(True)
        test_row.addWidget(note, 1)
        test_w = QWidget()
        test_w.setLayout(test_row)
        lay.addWidget(test_w)
        lay.addStretch(1)
        retheme_icons(self.form, ThemeTokens())

    # ------------------------------------------------------------------ interaction
    def _on_row(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if current.isValid():
            self.editor.select(self.model.rows[current.row()]["name"])

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        if obj is self.table and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                self.editor.remove()
                return True
            if event.key() == Qt.Key.Key_Space and self.editor.selected:
                cfg = self.editor.work[self.editor.selected]
                self.editor.set_field(cfg["name"], "enabled", not cfg["enabled"])
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self.editor.undo()
                return
            if event.key() == Qt.Key.Key_S:
                self.save_file_dialog()
                return
        super().keyPressEvent(event)

    def _clear_filters(self) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.editor.clear_filters()

    @SafeSlot()
    def open_file_dialog(self) -> None:
        """Pick a YAML config file to edit."""
        path, _ = QFileDialog.getOpenFileName(self, "Open device config", "", "YAML (*.yaml *.yml)")
        if path:
            self.editor.open_file(path)

    @SafeSlot()
    def save_file_dialog(self) -> None:
        """Save the edited copy as YAML."""
        path, _ = QFileDialog.getSaveFileName(self, "Save device config", "", "YAML (*.yaml)")
        if path:
            self.editor.save_file(path)

    @SafeSlot()
    def open_add_device(self) -> Sheet:
        """Sheet to add a device to the edited copy."""
        sheet = Sheet(
            self, "Add device", "Added to the edited copy. Test it, then review and apply."
        )
        name = QLineEdit()
        name.setPlaceholderText("e.g. pinz2")
        error = label(NEW_NAME_RULE, "faint")
        cls = QComboBox()
        cls.setEditable(True)
        cls.addItems(DEVICE_CLASSES)
        prefix = QLineEdit()
        prefix.setPlaceholderText("X05LA-ES-PH:Z2")
        for text, widget in (("Name", name), (None, error), ("Class", cls), ("PV prefix", prefix)):
            if text:
                sheet.body.addWidget(label(text))
            sheet.body.addWidget(widget)
        sheet.foot.addStretch(1)
        cancel = TextButton("Cancel")
        cancel.clicked.connect(sheet.reject)
        ok = TextButton("Add device", "primary")

        def add():
            message = self.editor.add_device(name.text(), cls.currentText(), prefix.text())
            if message:
                error.setText(message)
                error.setProperty("role", "err")
                error.style().unpolish(error)
                error.style().polish(error)
                return
            sheet.accept()

        ok.clicked.connect(add)
        name.returnPressed.connect(add)
        sheet.foot.addWidget(cancel)
        sheet.foot.addWidget(ok)
        sheet.setProperty("kind", "add")
        self._show_sheet(sheet)
        name.setFocus()
        return sheet

    @SafeSlot()
    def set_staff(self, user: str) -> None:
        """Show who is signed in (BEC Atlas) next to Review changes."""
        self.staff_label.setText(f"Signed in as {user}" if user else "")
        self.staff_label.setVisible(bool(user))
        self.sign_out_btn.setVisible(bool(user))

    def open_review(self) -> Sheet:
        """Sheet listing every difference to the running session, with Apply."""
        sheet = Sheet(
            self,
            "Apply changes to the running session",
            "These are the only differences between your edited copy and what BEC runs now. "
            "Other devices are left exactly as they are.",
            wide=True,
        )
        sheet.setProperty("kind", "review")
        self._fill_review(sheet)
        self._show_sheet(sheet)
        return sheet

    def _fill_review(self, sheet: Sheet) -> None:
        review = self.editor.review()
        sheet.clear_body()
        sheet.clear_foot()
        tokens = ThemeTokens()
        for group in review["groups"]:
            sheet.body.addWidget(label(group["title"].upper(), "upper"))
            for item in group["items"]:
                card = QFrame()
                card.setProperty("role", "diffcard")
                c = QVBoxLayout(card)
                c.setContentsMargins(9, 7, 9, 7)
                c.setSpacing(3)
                head = QHBoxLayout()
                name = label(item["name"], "mono")
                name.setStyleSheet("font-weight: 700;")
                head.addWidget(name)
                head.addWidget(label(item["deviceClass"], "muted"))
                head.addStretch(1)
                if item["statusText"]:
                    head.addWidget(Chip(item["statusText"], item["statusTone"], item["statusIcon"]))
                c.addLayout(head)
                for f in item["fields"]:
                    line = label(
                        f"<span style='color:{tokens.fg_muted.name()}'>{f['field']}: </span>"
                        f"<span style='color:{tokens.danger.name()}; text-decoration:"
                        f" line-through'>{f['old']}</span> → "
                        f"<span style='color:{tokens.success.name()}'>{f['new']}</span>",
                        "mono",
                    )
                    line.setTextFormat(Qt.TextFormat.RichText)
                    line.setWordWrap(True)
                    c.addWidget(line)
                sheet.body.addWidget(card)
        if review["uncheckedText"]:
            banner = Banner("warn")
            banner.set_content(
                "warning",
                review["uncheckedText"],
                "Each is loaded on its own; if one cannot connect it is reported and the others "
                "are not affected.",
            )
            sheet.body.addWidget(banner)
        if review["scanRunning"]:
            banner = Banner("err")
            banner.set_content(
                "lock", self.editor.bar_state()["scanText"], "Applying waits until it finishes."
            )
            sheet.body.addWidget(banner)
        sheet.body.addStretch(1)
        sheet.foot.addWidget(label(review["footText"], "muted"), 1)
        cancel = TextButton("Cancel")
        cancel.clicked.connect(sheet.reject)
        apply = TextButton(review["applyText"], "primary")
        apply.setEnabled(self.editor.can_apply())
        apply.clicked.connect(lambda: self._start_apply(sheet))
        sheet.foot.addWidget(cancel)
        sheet.foot.addWidget(apply)

    def _start_apply(self, sheet: Sheet) -> None:
        if self.editor.apply():
            sheet.setProperty("kind", "apply")
            self._sync_apply_sheet()

    def _sync_apply_sheet(self, final: bool = False) -> None:
        sheet = self._sheet
        if sheet is None or sheet.property("kind") != "apply":
            return
        sheet.clear_body()
        sheet.clear_foot()
        rows = self.editor.apply_rows
        if final or not self.editor.applying:
            failed = sum(1 for r in rows if r["state"] == "failed")
            banner = Banner("warn" if failed else "ok")
            banner.set_content(
                "warning" if failed else "check_circle",
                self.editor.apply_summary,
                (
                    "The devices marked Failed were not changed; see the Problems panel. "
                    "Everything else is live."
                    if failed
                    else "The running session now matches your copy."
                ),
            )
            sheet.body.addWidget(banner)
        states = {
            "waiting": ("Waiting", "neutral", "schedule"),
            "running": ("Initialising…", "busy", "sync"),
            "done": ("Done", "ok", "check"),
            "failed": ("Failed", "err", "warning"),
        }
        for r in rows:
            line = QHBoxLayout()
            name = label(r["name"], "mono")
            name.setStyleSheet("font-weight: 700;")
            name.setFixedWidth(140)
            line.addWidget(name)
            line.addWidget(label(r["action"], "muted"), 1)
            if r["message"]:
                msg = label(r["message"], "err")
                msg.setWordWrap(True)
                line.addWidget(msg, 2)
            line.addWidget(Chip(*states[r["state"]]))
            holder = QWidget()
            holder.setLayout(line)
            sheet.body.addWidget(holder)
        sheet.body.addStretch(1)
        sheet.foot.addStretch(1)
        done = TextButton("Done", "primary")
        done.setEnabled(not self.editor.applying)
        done.clicked.connect(sheet.accept)
        sheet.foot.addWidget(done)

    @SafeSlot()
    def open_clear_session(self) -> Sheet:
        """Danger-zone sheet: type CLEAR to remove every device from the session."""
        n = len(self.editor.session)
        sheet = Sheet(
            self,
            "Clear the running session?",
            f"Removes <b>all {n} devices</b> from BEC for everybody using this beamline. Plots, "
            "scans and motors stop working until a config is loaded again.",
        )
        if self.editor.scan_running:
            banner = Banner("err")
            banner.set_content(
                "lock", "A scan is running", "Clearing is not possible during a scan."
            )
            sheet.body.addWidget(banner)
        sheet.body.addWidget(label("Type CLEAR to confirm"))
        confirm = QLineEdit()
        confirm.setPlaceholderText("Type CLEAR")
        sheet.body.addWidget(confirm)
        sheet.foot.addStretch(1)
        cancel = TextButton("Cancel")
        cancel.clicked.connect(sheet.reject)
        go = TextButton(f"Remove all {n} devices", "danger")
        go.setEnabled(False)
        confirm.textChanged.connect(
            lambda t: go.setEnabled(t.strip() == "CLEAR" and not self.editor.scan_running)
        )
        go.clicked.connect(
            lambda: (not self.editor.clear_session(confirm.text())) and sheet.accept()
        )
        sheet.foot.addWidget(cancel)
        sheet.foot.addWidget(go)
        sheet.setProperty("kind", "clear")
        self._show_sheet(sheet)
        return sheet

    def _show_sheet(self, sheet: Sheet) -> None:
        if self._sheet is not None:
            self._sheet.close()
        self._sheet = sheet
        sheet.finished.connect(lambda _: self._forget_sheet(sheet))
        retheme_icons(sheet, ThemeTokens())
        sheet.open()

    def _forget_sheet(self, sheet: Sheet) -> None:
        if self._sheet is sheet:
            self._sheet = None
        sheet.deleteLater()

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self.toasts._reposition()  # pylint: disable=protected-access

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        tokens = ThemeTokens()
        self.setStyleSheet(view_qss(tokens))
        self.file_icon.setPixmap(material_icon("description", size=(16, 16), color=tokens.fg_muted))
        self._facet_key = None
        self._last_detail = None
        retheme_icons(self, tokens)
        if hasattr(self, "editor"):
            self._sync()

    def cleanup(self):
        self.editor.cleanup()
        if self._sheet is not None:
            self._sheet.close()
        super().cleanup()


# ------------------------------------------------------------------------------------ staff gate
class DeviceConfigGateQWidget(BECWidget, QWidget):
    """Device Config behind the BEC Atlas staff sign-in (QWidget version).

    The Config view is built on the first sign-in and locks again when the view is left.
    """

    RPC = False
    PLUGIN = False

    def __init__(self, parent=None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.get_bec_shortcuts()
        self.setObjectName("ConfigRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.access = StaffAccess(self.bec_dispatcher, self)
        self.config: DeviceConfigViewQWidget | None = None
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self._build_lock())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self.access.changed.connect(self._sync)
        self.apply_theme("")
        self._sync()

    def _build_lock(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        card = QFrame()
        card.setProperty("role", "panel")
        card.setFixedWidth(420)
        form = QVBoxLayout(card)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(12)
        self.lock_icon = QLabel()
        self.lock_icon.setFixedSize(44, 44)
        self.lock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addWidget(self.lock_icon)
        title = label("Device Config is for beamline staff")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        form.addWidget(title)
        text = label(
            "Sign in with your BEC Atlas account to add, remove and configure devices. "
            "Everyone can watch and operate devices in Devices.",
            "muted",
        )
        text.setWordWrap(True)
        form.addWidget(text)
        form.addSpacing(4)
        form.addWidget(label("User name", "fieldlabel"))
        self.user = QLineEdit()
        self.user.setPlaceholderText("e.g. e12345")
        self.user.setAccessibleName("User name")
        form.addWidget(self.user)
        form.addWidget(label("Password", "fieldlabel"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("Password")
        form.addWidget(self.password)
        self.error = label("", "err")
        self.error.setWordWrap(True)
        form.addWidget(self.error)
        foot = QHBoxLayout()
        self.deployment = label("", "faint")
        foot.addWidget(self.deployment, 1)
        self.sign_in = TextButton("Sign in", "primary", "login")
        foot.addWidget(self.sign_in)
        form.addLayout(foot)
        self.user.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self._submit)
        self.sign_in.clicked.connect(self._submit)
        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        self.lock_page = page
        return page

    def _submit(self) -> None:
        self.access.sign_in(self.user.text(), self.password.text())

    @SafeSlot()
    def _sync(self) -> None:
        busy = self.access.busy
        self.user.setEnabled(not busy)
        self.password.setEnabled(not busy)
        self.sign_in.setEnabled(not busy)
        self.sign_in.setText("Signing in…" if busy else "Sign in")
        self.error.setText(self.access.error)
        self.error.setVisible(bool(self.access.error))
        self.deployment.setText(
            f"Deployment {self.access.deployment}" if self.access.deployment else ""
        )
        if self.access.unlocked and self.config is None:
            self.config = DeviceConfigViewQWidget(parent=self, client=self.client)
            self.config.sign_out_requested.connect(self.access.sign_out)
            self.stack.addWidget(self.config)
        if self.config is not None:
            self.config.set_staff(self.access.user)
        if self.access.unlocked and self.config is not None:
            self.password.clear()
            self.stack.setCurrentWidget(self.config)
        else:
            self.stack.setCurrentWidget(self.lock_page)

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        if not event.spontaneous():
            self.access.sign_out()

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        tokens = ThemeTokens()
        self.setStyleSheet(view_qss(tokens) + f"""
            QFrame[role="panel"] {{ background: {tokens.card.name()};
                border: 1px solid {tokens.border.name()}; border-radius: 10px; }}
            QFrame[role="panel"] QLabel {{ border: none; }}
            QLabel[role="fieldlabel"] {{ font-size: 12px; font-weight: 600; }}
            """)
        self.lock_icon.setStyleSheet(
            f"background: {rgba(tokens.primary, 0.14)}; border-radius: 22px; border: none;"
        )
        self.lock_icon.setPixmap(material_icon("lock", size=(22, 22), color=tokens.primary))
        retheme_icons(self, tokens)

    def cleanup(self):
        self.access.cleanup()
        if self.config is not None:
            self.config.close()
            self.config.deleteLater()
        super().cleanup()
