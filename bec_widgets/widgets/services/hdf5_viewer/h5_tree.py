"""
The tree of the HDF5 viewer: files, groups and datasets, listed one group at a time.

A group is listed when it is expanded, never before. Links into other files are shown as
links and their file is opened only when the link is expanded or selected.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path

from bec_qthemes import material_icon
from qtpy.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from qtpy.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.theme_utils import theme_colors
from bec_widgets.widgets.progress.stage_bar import Tone
from bec_widgets.widgets.services.bec_queue.queue_ui import ROW_HOVER_ALPHA, tone_color
from bec_widgets.widgets.services.hdf5_viewer import h5_reader
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import FoundBranches, H5Node, H5ReadError
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service
from bec_widgets.widgets.services.hdf5_viewer.scan_list import on_color
from bec_widgets.widgets.services.hdf5_viewer.style import (
    DIM_ON_TINT_ALPHA,
    control_key_name,
    lead_tint,
    mute,
    muted_color,
    paint_list_row,
)

NODE_ROLE = Qt.ItemDataRole.UserRole + 1
STATE_ROLE = Qt.ItemDataRole.UserRole + 2
PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 3
#: In the search results: ``(start, length)`` of the part of the name that matches.
MATCH_ROLE = Qt.ItemDataRole.UserRole + 4
#: In the search results: a group that only leads to a match.
CONTEXT_ROLE = Qt.ItemDataRole.UserRole + 5

#: Pause after the last change of the selection before a preview is asked for.
SELECT_DELAY_MS = 150
#: Pause after the last key stroke before the file is searched.
FIND_DELAY_MS = 300
#: Deepest level the tree opens by itself when a file is shown.
AUTO_EXPAND_DEPTH = 6
#: Below this width the tree shows names and shapes only; the type is in the details.
NARROW_TREE_WIDTH = 380
#: Letters of a name the tree keeps in view before it leaves the shape out too.
NAME_LETTERS = 10
#: The column of the Y button that puts a dataset on the plot, and its width.
Y_COLUMN = 3
Y_COLUMN_WIDTH = 34
#: Room the X button of rows that are signals takes left of the Y button.
X_BUTTON_ROOM = 28
#: Room between the ring of the selected row and its icon, as after its last button.
ROW_RING_GAP = 5
#: Icons of coloured rows kept in their colour, at most; each row has an icon of its own.
TINTED_ICONS_MAX = 512
#: Room the Z button of rows that are signals of a map takes right of the Y button.
Z_BUTTON_ROOM = 28
#: The Y button, as on the rows of the Signals tab.
Y_BUTTON = QSize(24, 20)
#: Height of a row: the Y button with 3 px above and below, as the rows of the Signals tab.
TREE_ROW_HEIGHT = Y_BUTTON.height() + 6


def can_keep(node: H5Node | None) -> bool:
    """
    Whether a node can be kept on the plot of the File tab as one more curve.

    Args:
        node (H5Node | None): The node of a row.

    Returns:
        bool: True for a dataset of numbers along one axis, with more than one value.
    """
    return (
        node is not None
        and node.kind == "dataset"
        and node.is_numeric
        and node.ndim == 1
        and node.size > 1
    )


def node_icon_name(node: H5Node) -> str:
    """
    Name of the icon of a node.

    Args:
        node (H5Node): The node.

    Returns:
        str: A Material icon name.
    """
    if node.kind == "file":
        return "draft"
    if node.kind == "group":
        return "insights" if node.nx_class == "NXdata" else "folder"
    if node.kind == "link":
        return "link"
    if node.kind == "broken":
        return "link_off"
    if node.kind == "dataset":
        if not node.is_numeric:
            return "notes"
        if node.size <= 1:
            return "tag"
        return "show_chart" if node.ndim == 1 else "grid_on"
    return "help"


def node_type_text(node: H5Node) -> str:
    """
    Text of the type column of a node.

    Args:
        node (H5Node): The node.

    Returns:
        str: For example ``float64``, ``NXdata`` or ``link``.
    """
    if node.kind == "dataset":
        return node.dtype
    if node.kind == "group":
        return node.nx_class or "group"
    if node.kind == "link":
        return "link"
    if node.kind == "broken":
        return "broken link"
    return "" if node.kind == "file" else node.kind


@dataclass(frozen=True)
class ZButton:
    """The Z button of a row that is a signal of a map, as on its row in the Signals tab."""

    #: The colour of the map while the signal colours it, else empty.
    color: str = ""
    #: Why the signal colours nothing although it was asked to, else empty.
    problem: str = ""

    @property
    def tip(self) -> str:
        """The tooltip of the button."""
        if self.problem:
            return f"Not drawn: {self.problem}. Press Z to take it off the plot."
        return "Colour the map by it (Z)"


class _MutedColumnDelegate(QStyledItemDelegate):
    """
    Draws the shape and type columns, placeholders and the groups that only lead to a search
    match in the muted text colour of the theme, and the matching part of a name in bold.
    """

    def __init__(self, tree: H5Tree):
        super().__init__(tree.view)
        self._tree = tree
        self._tinted: dict[tuple, QIcon] = {}

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        super().initStyleOption(option, index)
        # The view paints the background of a row as the scan list does; the cells only
        # paint their text, never a selection of their own.
        option.state &= ~QStyle.StateFlag.State_Selected
        ink = self._tree.row_ink(index)
        if ink is not None:
            # On the solid row of a curve everything is black or white, the icon as its text;
            # nothing is muted there. A row tinted for the curves it leads to keeps the
            # colours of the theme.
            option.palette.setColor(QPalette.ColorRole.Text, ink)
            if not option.icon.isNull():
                option.icon = self._tinted_icon(option.icon, ink, option.decorationSize)
        elif index.column() > 0 or index.data(PLACEHOLDER_ROLE) or index.data(CONTEXT_ROLE):
            # Secondary text; stronger on a tinted row, so that it stays readable on the tint.
            tinted = bool(self._tree.row_colors(index))
            dim = muted_color(DIM_ON_TINT_ALPHA) if tinted else muted_color()
            option.palette.setColor(QPalette.ColorRole.Text, dim)

    def _tinted_icon(self, icon: QIcon, ink: QColor, size: QSize) -> QIcon:
        """The icon of a row in one colour, kept for the next paint."""
        ratio = self._tree.view.devicePixelRatioF()
        key = (icon.cacheKey(), ink.rgba(), size.width(), size.height(), ratio)
        tinted = self._tinted.get(key)
        if tinted is None:
            if len(self._tinted) > TINTED_ICONS_MAX:
                self._tinted.clear()
            pixmap = QPixmap(icon.pixmap(size, ratio))
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), ink)
            painter.end()
            tinted = self._tinted[key] = QIcon(pixmap)
        return tinted

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        # The Y button fits the row with room above and below it.
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), TREE_ROW_HEIGHT))

    @staticmethod
    def x_button_rect(cell: QRect, z: bool = False) -> QRect:
        """
        Where the X button of a row that is a signal is drawn and clicked: left of its Y.

        Args:
            cell (QRect): Rectangle of the row's cell in the Y column.
            z (bool): Whether the rows of the tree have a Z button right of the Y.

        Returns:
            QRect: The button.
        """
        y_rect = _MutedColumnDelegate.button_rect(cell, z)
        return y_rect.translated(-X_BUTTON_ROOM, 0)

    @staticmethod
    def button_rect(cell: QRect, z: bool = False) -> QRect:
        """
        Where the Y button of a row is drawn and clicked.

        Args:
            cell (QRect): Rectangle of the row's cell in the Y column.
            z (bool): Whether the rows of the tree have a Z button right of the Y.

        Returns:
            QRect: The button, at the right of the cell, or left of the Z button, and centred
            in its height.
        """
        top = cell.top() + (cell.height() - Y_BUTTON.height()) // 2
        right = cell.right() - 6 - (Z_BUTTON_ROOM if z else 0)
        return QRect(right - Y_BUTTON.width() + 1, top, Y_BUTTON.width(), Y_BUTTON.height())

    @staticmethod
    def z_button_rect(cell: QRect) -> QRect:
        """
        Where the Z button of a row that is a signal of a map is drawn and clicked: right of its
        Y, as on the rows of the Signals tab.

        Args:
            cell (QRect): Rectangle of the row's cell in the Y column.

        Returns:
            QRect: The button, at the right of the cell.
        """
        return _MutedColumnDelegate.button_rect(cell)

    def _paint_button(self, painter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """
        The Y button of a row that can be a curve, as on the rows of the Signals tab: an
        outline, filled while the dataset is on the plot.
        """
        node = self._tree.node_at(index)
        self._paint_x_button(painter, option, index)
        self._paint_z_button(painter, option, index)
        if not self._tree.can_keep_row(node):
            return
        colors = theme_colors()
        rect = self.button_rect(option.rect, self._tree.has_z_rows())
        viewport = self._tree.view.viewport()
        pointer = viewport.mapFromGlobal(QCursor.pos())
        fill = self._tree.row_fill(node)
        kept = self._tree.is_kept(node)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSizeF(option.font.pointSizeF() * 0.9)
        painter.setFont(font)
        body = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        if fill is not None:
            # On the row in the colour of its curve: the button in black or white, its
            # letter in the colour of the curve.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(on_color(fill))
            painter.drawRoundedRect(body, 5, 5)
            ink = QColor(fill)
        else:
            ink = QColor(colors["fg"])
            outline = tone_color(Tone.BAD) if kept else QColor(ink)
            if not kept:
                outline.setAlphaF(0.45)
            painter.setPen(QPen(outline, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(body, 5, 5)
            if kept:
                ink = tone_color(Tone.BAD)
        if viewport.underMouse() and rect.contains(pointer):
            shade = QColor(colors["fg"])
            shade.setAlphaF(ROW_HOVER_ALPHA * 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shade)
            painter.drawRoundedRect(body, 5, 5)
        painter.setPen(ink)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Y")
        painter.restore()

    def _paint_x_button(self, painter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """
        The X button of a row that is a signal, as on the rows of the Signals tab: an
        outline, filled with the text colour while the signal is the x axis.
        """
        state = self._tree.x_state(self._tree.node_at(index))
        if state is None:
            return
        colors = theme_colors()
        rect = self.x_button_rect(option.rect, self._tree.has_z_rows())
        body = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        ink = self._tree.row_ink(index) or QColor(colors["fg"])
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSizeF(option.font.pointSizeF() * 0.9)
        painter.setFont(font)
        if state:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ink)
            painter.drawRoundedRect(body, 5, 5)
            letter = on_color(ink)
        else:
            outline = QColor(ink)
            outline.setAlphaF(0.45)
            painter.setPen(QPen(outline, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(body, 5, 5)
            letter = ink
        viewport = self._tree.view.viewport()
        if viewport.underMouse() and rect.contains(viewport.mapFromGlobal(QCursor.pos())):
            shade = QColor(colors["fg"])
            shade.setAlphaF(ROW_HOVER_ALPHA * 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shade)
            painter.drawRoundedRect(body, 5, 5)
        painter.setPen(letter)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "X")
        painter.restore()

    def _paint_z_button(self, painter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """
        The Z button of a row that is a signal of a map, as on the rows of the Signals tab: an
        outline, filled with the colour of the map while the signal colours it, and outlined in
        the colour of a problem while it was asked for but colours nothing.
        """
        state = self._tree.z_state(self._tree.node_at(index))
        if state is None:
            return
        colors = theme_colors()
        rect = self.z_button_rect(option.rect)
        body = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        ink = self._tree.row_ink(index) or QColor(colors["fg"])
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSizeF(option.font.pointSizeF() * 0.9)
        painter.setFont(font)
        if state.problem:
            letter = tone_color(Tone.BAD)
            painter.setPen(QPen(letter, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        elif state.color:
            fill = QColor(state.color)
            letter = on_color(fill)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
        else:
            outline = QColor(ink)
            outline.setAlphaF(0.45)
            painter.setPen(QPen(outline, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            letter = ink
        painter.drawRoundedRect(body, 5, 5)
        viewport = self._tree.view.viewport()
        if viewport.underMouse() and rect.contains(viewport.mapFromGlobal(QCursor.pos())):
            shade = QColor(colors["fg"])
            shade.setAlphaF(ROW_HOVER_ALPHA * 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shade)
            painter.drawRoundedRect(body, 5, 5)
        painter.setPen(letter)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Z")
        painter.restore()

    def helpEvent(self, event, view, option, index) -> bool:
        if index.isValid() and index.column() == Y_COLUMN:
            node = self._tree.node_at(index)
            z = self._tree.has_z_rows()
            z_state = self._tree.z_state(node)
            if z_state is not None and self.z_button_rect(option.rect).contains(event.pos()):
                QToolTip.showText(event.globalPos(), z_state.tip, view, option.rect)
                return True
            state = self._tree.x_state(node)
            if state is not None and self.x_button_rect(option.rect, z).contains(event.pos()):
                tip = (
                    "The x axis; X again plots against the scan's axes"
                    if state
                    else "Plot against it, as X in the Signals tab"
                )
                QToolTip.showText(event.globalPos(), tip, view, option.rect)
                return True
            if self._tree.can_keep_row(node) and self.button_rect(option.rect, z).contains(
                event.pos()
            ):
                QToolTip.showText(event.globalPos(), self._tree.button_tip(node), view, option.rect)
                return True
        return super().helpEvent(event, view, option, index)

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex):
        if index.column() == Y_COLUMN:
            super().paint(painter, option, index)
            self._paint_button(painter, option, index)
            return
        span = index.data(MATCH_ROLE) if index.column() == 0 else None
        if not span:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)
        text = opt.text
        opt.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, None, widget) + 1
        rect = rect.adjusted(margin, 0, -margin, 0)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        start, length = span
        strong = QFont(opt.font)
        strong.setWeight(QFont.Weight.Bold)
        painter.save()
        painter.setPen(opt.palette.color(role))
        x = rect.left()
        for part, font in (
            (text[:start], opt.font),
            (text[start : start + length], strong),
            (text[start + length :], opt.font),
        ):
            if not part:
                continue
            metrics = QFontMetrics(font)
            room = rect.right() - x
            if room <= 0:
                break
            shown = metrics.elidedText(part, Qt.TextElideMode.ElideRight, room)
            painter.setFont(font)
            painter.drawText(
                x, rect.top(), room, rect.height(), Qt.AlignmentFlag.AlignVCenter, shown
            )
            x += metrics.horizontalAdvance(shown)
            if shown != part:
                break
        painter.restore()


class _FindKeys(QObject):
    """Down and Enter in the search field move into the results, Esc clears the search."""

    def __init__(self, tree: H5Tree):
        super().__init__(tree)
        self._tree = tree

    def eventFilter(self, watched, event) -> bool:  # pylint: disable=invalid-name
        if event.type() != QEvent.Type.KeyPress:
            return False
        key = event.key()
        if key == Qt.Key.Key_Escape and self._tree.find_edit.text():
            self._tree.find_edit.clear()
            return True
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return self._tree.enter_results()
        return False


class _KeepInput(QObject):
    """
    Puts datasets on the plot from the tree, as the Signals tab does: a click on the Y button
    of a row or a click with Ctrl (⌘ on macOS) keeps or releases the dataset of the row
    without selecting it, Y does it for the current row.
    """

    def __init__(self, tree: H5Tree):
        super().__init__(tree)
        self._tree = tree
        self._hovered = QRect()

    def _keep_target(self, event) -> H5Node | None:
        """The dataset a mouse event keeps or releases, or None for a plain click."""
        if event.button() != Qt.MouseButton.LeftButton:
            return None
        view = self._tree.view
        position = event.position().toPoint()
        index = view.indexAt(position)
        if not index.isValid():
            return None
        node = self._tree.node_at(index)
        if not self._tree.can_keep_row(node):
            return None
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return node
        cell = view.visualRect(index.sibling(index.row(), Y_COLUMN))
        y_rect = _MutedColumnDelegate.button_rect(cell, self._tree.has_z_rows())
        if not view.isColumnHidden(Y_COLUMN) and y_rect.contains(position):
            return node
        return None

    #: The events the filter acts on; any other passes untouched, also while the tree goes.
    _EVENTS = (
        QEvent.Type.KeyPress,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseMove,
        QEvent.Type.Leave,
    )

    def _x_target(self, event) -> str:
        """The path of the row whose X button a mouse event is on, or empty."""
        if event.button() != Qt.MouseButton.LeftButton:
            return ""
        view = self._tree.view
        position = event.position().toPoint()
        index = view.indexAt(position)
        node = self._tree.node_at(index)
        if self._tree.x_state(node) is None or view.isColumnHidden(Y_COLUMN):
            return ""
        cell = view.visualRect(index.sibling(index.row(), Y_COLUMN))
        x_rect = _MutedColumnDelegate.x_button_rect(cell, self._tree.has_z_rows())
        return node.path if x_rect.contains(position) else ""

    def _z_target(self, event) -> str:
        """The path of the row whose Z button a mouse event is on, or empty."""
        if event.button() != Qt.MouseButton.LeftButton:
            return ""
        view = self._tree.view
        position = event.position().toPoint()
        index = view.indexAt(position)
        node = self._tree.node_at(index)
        if self._tree.z_state(node) is None or view.isColumnHidden(Y_COLUMN):
            return ""
        cell = view.visualRect(index.sibling(index.row(), Y_COLUMN))
        return node.path if _MutedColumnDelegate.z_button_rect(cell).contains(position) else ""

    def eventFilter(self, watched, event) -> bool:  # pylint: disable=invalid-name
        kind = event.type()
        if kind not in self._EVENTS:
            return False
        view = self._tree.view
        if watched is view and kind == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Y and not event.modifiers():
                node = self._tree.current_node()
                if self._tree.can_keep_row(node):
                    self._tree.toggle_row(node)
                    return True
            if event.key() == Qt.Key.Key_X and not event.modifiers():
                node = self._tree.current_node()
                if self._tree.x_state(node) is not None:
                    self._tree.x_toggled.emit(node.path)
                    return True
            if event.key() == Qt.Key.Key_Z and not event.modifiers():
                node = self._tree.current_node()
                if self._tree.z_state(node) is not None:
                    self._tree.z_toggled.emit(node.path)
                    return True
            return False
        if kind == QEvent.Type.KeyPress or watched is not view.viewport():
            return False
        if kind == QEvent.Type.Leave:
            if not self._hovered.isNull():
                view.viewport().update(self._hovered)
                self._hovered = QRect()
            return False
        if kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            # Taken whole, so that keeping a dataset does not select it.
            return (
                bool(self._x_target(event) or self._z_target(event))
                or self._keep_target(event) is not None
            )
        if kind == QEvent.Type.MouseButtonRelease:
            path = self._x_target(event)
            if path:
                self._tree.x_toggled.emit(path)
                return True
            path = self._z_target(event)
            if path:
                self._tree.z_toggled.emit(path)
                return True
            node = self._keep_target(event)
            if node is not None:
                self._tree.toggle_row(node)
                return True
        if kind == QEvent.Type.MouseMove:
            # The row under the pointer is shaded: repaint the rows it leaves and enters.
            index = view.indexAt(event.position().toPoint())
            rect = QRect()
            if index.isValid():
                cell = view.visualRect(index)
                rect = QRect(0, cell.top(), view.viewport().width(), cell.height())
            if rect != self._hovered:
                for changed in (self._hovered, rect):
                    if not changed.isNull():
                        view.viewport().update(changed)
                self._hovered = rect
        return False


class _FileView(QTreeView):
    """
    The tree of the file. Its rows get the backgrounds of the rows of the scan list: a kept
    dataset is filled with the colour of its curve, the selected row has a ring and a tint, and
    the row under the pointer a shade.
    """

    def __init__(self, tree: H5Tree):
        super().__init__(tree)
        self._tree = tree
        # The theme fills the selected and the hovered cells and the indent of the selected
        # row; this view paints whole rows itself instead.
        self.setStyleSheet(
            "QTreeView::item:selected, QTreeView::item:hover, QTreeView::branch:selected,"
            " QTreeView::branch:hover { background: transparent; }"
            " QTreeView { selection-background-color: transparent; }"
        )

    def drawRow(self, painter, option, index):  # pylint: disable=invalid-name
        self._paint_row(painter, option, index)
        super().drawRow(painter, option, index)

    def _paint_row(self, painter: QPainter, option, index: QModelIndex) -> None:
        cell = self.visualRect(index.siblingAtColumn(0))
        # As much room before the icon of the row as after its last button.
        left = self._content_left(index.siblingAtColumn(0), cell) - ROW_RING_GAP
        row = QRectF(max(0, left), option.rect.top(), 0, option.rect.height())
        row.setRight(self.viewport().width() - 2)
        selected = self.selectionModel().isRowSelected(index.row(), index.parent())
        viewport = self.viewport()
        pointer = viewport.mapFromGlobal(QCursor.pos())
        hovered = viewport.underMouse() and option.rect.contains(pointer)
        # Several kept datasets inside a collapsed group: their colours side by side.
        # Solid in the colour of its curve for a row on the plot, a tint for one that leads to
        # curves inside it.
        strength = 1.0 if self._tree.row_ink(index) is not None else lead_tint()
        paint_list_row(painter, row, self._tree.row_colors(index), selected, hovered, strength)

    def _content_left(self, index: QModelIndex, cell: QRect) -> int:
        """Where the icon of a row starts, or its text for a row without an icon."""
        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        self.itemDelegateForIndex(index).initStyleOption(option, index)
        option.rect = cell
        style = self.style()
        for element in (
            QStyle.SubElement.SE_ItemViewItemDecoration,
            QStyle.SubElement.SE_ItemViewItemText,
        ):
            rect = style.subElementRect(element, option, self)
            if rect.isValid() and rect.width() > 0:
                return rect.left()
        return cell.left()

    def mousePressEvent(self, event) -> None:  # pylint: disable=invalid-name
        """A click on a row picks it by hand, also the row that is selected already."""
        super().mousePressEvent(event)
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.indexAt(event.position().toPoint()).isValid()
        ):
            self._tree.mark_pick()

    def keyPressEvent(self, event) -> None:  # pylint: disable=invalid-name
        """A key that moves to a row picks it by hand, Enter the row that is selected."""
        before = self.currentIndex()
        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) or self.currentIndex() != before:
            self._tree.mark_pick()


class H5Tree(QWidget):
    """Tree of one main file and the files next to it, with a search by name."""

    #: The node to preview: an :class:`H5Node`, with links already followed, or None.
    node_selected = Signal(object)
    #: The node of a row the user picked by hand, with a click or a key: sent after
    #: :attr:`node_selected` for that row, and alone for a row that is shown already.
    node_picked = Signal(object)
    #: The main file could not be listed; carries the :class:`H5ReadError`.
    file_failed = Signal(object)
    #: The top level of the main file was listed.
    file_listed = Signal(str)
    #: The Y button or a Ctrl-click of a row asks to keep its dataset on the plot, or to
    #: release it: carries the :class:`H5Node` of the dataset (for a group, of its default).
    keep_toggled = Signal(object)
    #: The X button of a row that is a signal was pressed: carries the path of the row.
    x_toggled = Signal(str)
    #: The Z button of a row that is a signal of a map was pressed: carries the path of the row.
    z_toggled = Signal(str)

    def __init__(self, service: H5Service, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._generation = 0
        #: Bumped whenever the search results are rebuilt or left, so late reads into the old
        #: result rows are dropped.
        self._found_generation = 0
        #: Rows whose listing :meth:`pause` cut off, read again by :meth:`resume`.
        self._paused_loads: list[QStandardItem] = []
        self._find_interrupted = False
        #: The node announced last, so that finding it again in the tree does not read it again.
        self._shown_node: H5Node | None = None
        #: Whether the next node announced is that of a row picked by hand.
        self._pick_pending = False
        #: The path whose row counts as picked by hand once it is selected by following it.
        self._pick_path: list[str] = []
        #: Rows of the tree that were open when the search results took the view.
        self._expanded: list[QStandardItem] = []
        self._file_path = ""
        self._pending_path: list[str] = []
        #: The names of the path being followed that are open already, from the file down.
        self._path_done: list[str] = []
        self._follow_default = False
        self._channel = f"tree-{id(self)}"
        #: Paths inside the main file of the datasets kept on the plot.
        #: Colour of each kept dataset by path; empty for one that is not drawn.
        self._kept: dict[str, str] = {}
        #: The default dataset of each NXdata group of the main file looked up so far.
        self._group_signals: dict[str, H5Node] = {}
        #: Rows that are signals of the scan and can be its x axis, by path, and whether each
        #: is the x axis now.
        self._x_rows: dict[str, bool] = {}
        #: Rows that are signals of the scan while it is a map, by path: their Z buttons.
        self._z_rows: dict[str, ZButton] = {}
        #: The only rows that have a Y button, by path, e.g. the signals of a map, where a
        #: dataset that is no signal has no place; None for every row that can be one curve.
        self._y_rows: frozenset[str] | None = None

        self.find_edit = QLineEdit(self)
        self.find_edit.setObjectName("file_search")
        self.find_edit.setPlaceholderText("Find by name in this file")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setAccessibleName("Find by name in this file")
        self.find_edit.addAction(
            material_icon("search", size=(16, 16), convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )

        self.model = QStandardItemModel(self)
        self.found_model = QStandardItemModel(self)
        for model in (self.model, self.found_model):
            model.setHorizontalHeaderLabels(["Name", "Shape", "Type", ""])
            # The shapes are right-aligned: their header stands over them.
            model.horizontalHeaderItem(1).setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

        self.view = _FileView(self)
        self.view.setObjectName("file_view")
        self.view.setModel(self.model)
        self.view.setItemDelegate(_MutedColumnDelegate(self))
        self.view.setMouseTracking(True)
        self.view.setUniformRowHeights(True)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setAllColumnsShowFocus(True)
        self.view.setIndentation(14)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.setAccessibleName("Contents of the file")
        self._size_header()

        self.note = QLabel(self)
        self.note.setWordWrap(True)
        mute(self.note)
        self.note.setContentsMargins(6, 2, 6, 2)
        self.note.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.find_edit)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.note)

        self._select_timer = QTimer(self)
        self._select_timer.setSingleShot(True)
        self._select_timer.setInterval(SELECT_DELAY_MS)
        self._select_timer.timeout.connect(self._emit_selection)
        self._find_timer = QTimer(self)
        self._find_timer.setSingleShot(True)
        self._find_timer.setInterval(FIND_DELAY_MS)
        self._find_timer.timeout.connect(self._find)
        # Rows come and go in bursts; look at the columns once things settle.
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(0)
        self._fit_timer.timeout.connect(self._fit_columns)
        self.view.expanded.connect(self._schedule_fit)
        self.view.collapsed.connect(self._schedule_fit)
        self.view.verticalScrollBar().valueChanged.connect(self._schedule_fit)
        for model in (self.model, self.found_model):
            model.rowsInserted.connect(self._schedule_fit)
            model.rowsRemoved.connect(self._schedule_fit)

        self.view.expanded.connect(self._on_expanded)
        self.view.collapsed.connect(self._on_collapsed)
        self.view.customContextMenuRequested.connect(self._show_menu)
        self.find_edit.textChanged.connect(self._on_find_text)
        self.find_edit.installEventFilter(_FindKeys(self))
        keep_input = _KeepInput(self)
        self.view.installEventFilter(keep_input)
        self.view.viewport().installEventFilter(keep_input)
        self._connect_selection()

    ################################################################################
    # Public interface
    ################################################################################

    @property
    def file_path(self) -> str:
        """Path of the main file, empty when no file is shown."""
        return self._file_path

    def set_file(
        self, file_path: str | None, neighbours: tuple[str, ...] = (), select_path: str = ""
    ) -> None:
        """
        Show a file, and the files next to it as closed entries below it.

        Args:
            file_path (str | None): Path of the main file, or None to empty the tree.
            neighbours (tuple[str, ...]): Paths of further files, listed when expanded.
            select_path (str): Path inside the main file to open and select. Without it the
                tree opens along the default plot of the file, where the file names one.
        """
        self._generation += 1
        self._service.cancel_all(self._channel)
        self._select_timer.stop()
        self._pick_pending = False
        self._file_path = file_path or ""
        self._group_signals = {}
        self._pending_path = [part for part in select_path.split("/") if part]
        self._path_done = []
        self._follow_default = not self._pending_path
        self.find_edit.blockSignals(True)
        self.find_edit.clear()
        self.find_edit.blockSignals(False)
        self._show_tree(reveal=False)
        self._expanded = []
        self._shown_node = None
        self.model.removeRows(0, self.model.rowCount())
        self.find_edit.setEnabled(bool(file_path))
        if not file_path:
            return
        for index, path in enumerate((file_path, *neighbours)):
            node = H5Node(name=Path(path).name, path="/", file_path=path, kind="file")
            row = self._row_for(node)
            row[0].setToolTip(path)
            self.model.appendRow(row)
            if index == 0:
                self.view.expand(row[0].index())

    def select_path(self, path: str) -> None:
        """
        Open the main file along ``path`` and select the node at its end.

        Args:
            path (str): Path inside the main file, for example ``/entry/data/counts``.
        """
        if not self._file_path or self.model.rowCount() == 0:
            return
        if self.find_edit.text():
            self.find_edit.blockSignals(True)
            self.find_edit.clear()
            self.find_edit.blockSignals(False)
            self._show_tree(reveal=False)
        self._pending_path = [part for part in path.split("/") if part]
        self._path_done = []
        self._follow_default = False
        self._continue_path(self.model.item(0))

    def current_node(self) -> H5Node | None:
        """
        The node under the cursor.

        Returns:
            H5Node | None: The node, or None when nothing is selected.
        """
        index = self.view.currentIndex()
        if not index.isValid():
            return None
        return index.sibling(index.row(), 0).data(NODE_ROLE)

    @staticmethod
    def node_at(index: QModelIndex) -> H5Node | None:
        """
        The node of the row of an index, whatever its column.

        Args:
            index (QModelIndex): An index of the view's model.

        Returns:
            H5Node | None: The node, or None for a placeholder.
        """
        if not index.isValid():
            return None
        return index.sibling(index.row(), 0).data(NODE_ROLE)

    def can_keep_row(self, node: H5Node | None) -> bool:
        """
        Whether a row shows the Y button: a dataset of the main file that can be one curve, or
        an NXdata group of it, which puts its default dataset on the plot.

        Args:
            node (H5Node | None): The node of the row.

        Returns:
            bool: True when the row can put a curve on the plot.
        """
        if node is None or node.file_path != self._file_path:
            return False
        if self._y_rows is not None and node.path not in self._y_rows:
            return False
        return can_keep(node) or (node.kind == "group" and node.nx_class == "NXdata")

    def set_y_rows(self, paths) -> None:
        """
        Give the Y button only to these rows, e.g. to the signals of a map; or to every row
        that can be one curve again.

        Args:
            paths (Iterable[str] | None): Paths inside the main file, or None for every row.
        """
        rows = frozenset(paths) if paths is not None else None
        if rows != self._y_rows:
            self._y_rows = rows
            self.view.viewport().update()

    def _kept_path(self, node: H5Node | None) -> str:
        """The path a row stands for on the plot: its own, or the default of a group."""
        if node is None:
            return ""
        if node.kind == "group":
            signal = self._group_signals.get(node.path)
            return signal.path if signal is not None else ""
        return node.path

    def is_kept(self, node: H5Node | None) -> bool:
        """
        Whether a row's dataset is kept on the plot; for an NXdata group, its default dataset.

        Args:
            node (H5Node | None): The node of the row.

        Returns:
            bool: True when its path is kept and it is in the main file.
        """
        if node is None or node.file_path != self._file_path:
            return False
        return self._kept_path(node) in self._kept

    def toggle_row(self, node: H5Node) -> None:
        """
        Keep the dataset of a row on the plot, or take it off. A group stands for its default
        dataset, which is looked up in the file first.

        Args:
            node (H5Node): The node of the row.
        """
        if node.kind != "group":
            self.keep_toggled.emit(node)
            return
        signal = self._group_signals.get(node.path)
        if signal is not None:
            self.keep_toggled.emit(signal)
            return
        file_path, group_path = node.file_path, node.path

        def done(plot):
            signal = plot.signal if plot is not None else None
            if signal is None or not can_keep(signal) or signal.file_path != self._file_path:
                self.show_note(f"{node.name} has no default dataset that can be one curve")
                return
            self._group_signals[group_path] = signal
            self.keep_toggled.emit(signal)

        def failed(error: H5ReadError):
            self.show_note(f"Could not look into {node.name}: {error.message}")

        self._service.request(
            f"{self._channel}-default-{group_path}",
            file_path,
            lambda _ctx: h5_reader.default_plot(file_path, group_path),
            done,
            failed,
        )

    def button_tip(self, node: H5Node) -> str:
        """The tooltip of the Y button of a row."""
        click = f"{control_key_name()}-click"
        if node.kind == "group":
            return f"Show its default dataset on the plot (Y or {click})"
        return f"Show on the plot (Y or {click})"

    def set_x_rows(self, rows: dict[str, bool]) -> None:
        """
        Give the rows that are signals of the scan an X button, as in the Signals tab.

        Args:
            rows (dict[str, bool]): Paths inside the main file of the rows that can be the x
                axis (a signal's dataset and its group), and whether each is the x axis now.
        """
        rows = dict(rows)
        if rows == self._x_rows:
            return
        width_changed = bool(rows) != bool(self._x_rows)
        self._x_rows = rows
        if width_changed:
            self._size_y_column()
        self.view.viewport().update()

    def set_z_rows(self, rows: dict[str, ZButton]) -> None:
        """
        Give the rows that are signals of a map a Z button, as in the Signals tab.

        Args:
            rows (dict[str, ZButton]): Paths inside the main file of the rows that can colour
                the map, and the state of the button of each.
        """
        rows = dict(rows)
        if rows == self._z_rows:
            return
        width_changed = bool(rows) != bool(self._z_rows)
        self._z_rows = rows
        if width_changed:
            self._size_y_column()
        self.view.viewport().update()

    def has_z_rows(self) -> bool:
        """Whether rows have a Z button, which then takes the place right of the Y buttons."""
        return bool(self._z_rows)

    def z_state(self, node: H5Node | None) -> ZButton | None:
        """
        The Z button of a row: None for a row without one.

        Args:
            node (H5Node | None): The node of the row.

        Returns:
            ZButton | None: Its state.
        """
        if node is None or node.file_path != self._file_path:
            return None
        return self._z_rows.get(node.path)

    def x_state(self, node: H5Node | None) -> bool | None:
        """
        The X button of a row: None for a row without one, else whether it is the x axis.

        Args:
            node (H5Node | None): The node of the row.

        Returns:
            bool | None: Its state.
        """
        if node is None or node.file_path != self._file_path:
            return None
        return self._x_rows.get(node.path)

    def set_kept(self, colors) -> None:
        """
        Show which datasets are kept on the plot: their Y buttons are filled and their rows take
        the colour of their curve, as the scans on the plot do in the scan list.

        Args:
            colors (Iterable[str] | dict[str, str]): Paths inside the main file, or the colour
                of each by path; an empty colour for one that is not drawn.
        """
        kept = dict(colors) if isinstance(colors, dict) else dict.fromkeys(colors, "")
        if kept != self._kept:
            self._kept = kept
            self.view.viewport().update()

    def row_fill(self, node: H5Node | None) -> QColor | None:
        """
        The fill of a row: the colour of its curve while its dataset is kept and drawn.

        Args:
            node (H5Node | None): The node of the row.

        Returns:
            QColor | None: The fill, or None for a row without one.
        """
        if not self.is_kept(node):
            return None
        color = self._kept.get(self._kept_path(node), "")
        return QColor(color) if color else None

    def row_colors(self, index: QModelIndex) -> list[QColor]:
        """
        The colours a row is painted in: that of its curve while its dataset is kept (solid),
        else, for a group, those of the kept datasets inside it (a tint), so that every row that
        leads to a kept dataset shows it, also while the group is expanded.

        Args:
            index (QModelIndex): An index of the row, whatever its column.

        Returns:
            list[QColor]: The colours, in the order the datasets were kept; empty for none.
        """
        node = self.node_at(index)
        fill = self.row_fill(node)
        if fill is not None:
            return [fill]
        if node is None or node.file_path != self._file_path or not node.is_container:
            return []
        prefix = node.path.rstrip("/") + "/"
        return [
            QColor(color) for path, color in self._kept.items() if color and path.startswith(prefix)
        ]

    def row_ink(self, index: QModelIndex) -> QColor | None:
        """
        The colour of the text and icon of a row painted solid in the colour of its curve:
        black or white, whichever reads better on it.

        Args:
            index (QModelIndex): An index of the row, whatever its column.

        Returns:
            QColor | None: The colour, or None for a row that is not on the plot itself; it
                keeps the colours of the theme, also where it is tinted for the curves inside.
        """
        fill = self.row_fill(self.node_at(index))
        return on_color(fill) if fill is not None else None

    def show_note(self, text: str) -> None:
        """Say something about the tree under it, e.g. why a row cannot go on the plot."""
        self.note.setText(text)
        self.note.show()

    def pause(self) -> None:
        """Stop reading while the tree is not shown; :meth:`resume` reads again what was cut off."""
        self._select_timer.stop()
        self._fit_timer.stop()
        self._find_interrupted = self._find_timer.isActive() or self._service.has_pending(
            f"{self._channel}-find"
        )
        self._find_timer.stop()
        self._service.cancel_all(self._channel)
        self._paused_loads = []
        for model in (self.model, self.found_model):
            self._collect_loading(model.invisibleRootItem(), self._paused_loads)
        for item in self._paused_loads:
            item.setData("unloaded", STATE_ROLE)

    def resume(self) -> None:
        """Read again what :meth:`pause` cut off."""
        loads, self._paused_loads = self._paused_loads, []
        for item in loads:
            try:
                if item.model() is not None and item.data(STATE_ROLE) == "unloaded":
                    self._load(item)
            except RuntimeError:  # the row went away meanwhile
                continue
        if self._find_interrupted:
            self._find_interrupted = False
            self._find_timer.start()

    def _collect_loading(self, parent: QStandardItem, found: list[QStandardItem]) -> None:
        for row in range(parent.rowCount()):
            child = parent.child(row)
            if child is None:
                continue
            if child.data(STATE_ROLE) == "loading":
                found.append(child)
            self._collect_loading(child, found)

    def cleanup(self) -> None:
        """Stop the timers and drop the pending reads."""
        self._generation += 1
        self._select_timer.stop()
        self._find_timer.stop()
        self._fit_timer.stop()
        self._found_generation += 1
        self._service.cancel_all(self._channel)

    ################################################################################
    # Building rows
    ################################################################################

    def _size_header(self) -> None:
        header = self.view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(24)
        header.setSectionResizeMode(Y_COLUMN, QHeaderView.ResizeMode.Fixed)
        self._size_y_column()
        # Name, Type, Shape, as silx shows them: the shape is right-aligned, so it stands
        # right before the Y button at every width.
        header.moveSection(header.visualIndex(2), 1)
        self._fit_columns()

    def _size_y_column(self) -> None:
        """
        The column of the buttons: Y, X left of it while rows are signals, and Z right of it
        while they are signals of a map.
        """
        width = Y_COLUMN_WIDTH + (X_BUTTON_ROOM if self._x_rows else 0)
        width += Z_BUTTON_ROOM if self._z_rows else 0
        self.view.header().resizeSection(Y_COLUMN, width)

    def _fit_columns(self) -> None:
        """
        Leave the type column out while the tree is narrow or while a name in view would be
        cut with it, so that names stay readable; and the shape too while a name in view would
        keep fewer than about ten letters with it. Both are also in the details, the buttons
        always stay.
        """
        view = self.view
        hide_type = self.width() < NARROW_TREE_WIDTH or self._names_need_room((1, 2))
        hide_shape = hide_type and self._names_need_room((1,), NAME_LETTERS)
        for column, hide in ((1, hide_shape), (2, hide_type)):
            if hide != view.isColumnHidden(column):
                view.setColumnHidden(column, hide)

    def _names_need_room(self, columns: tuple[int, ...], letters: int = 0) -> bool:
        """
        Whether a name in view would be cut while these columns are shown.

        Args:
            columns (tuple[int, ...]): The columns shown beside the names and the buttons.
            letters (int): Cut only when fewer letters than this stay in view; 0 for the
                whole name.
        """
        view = self.view
        model = view.model()
        if model is None:
            return False
        header = view.header()
        room = view.viewport().width() - header.sectionSize(Y_COLUMN)
        for column in columns:
            room -= max(view.sizeHintForColumn(column), header.sectionSizeHint(column))
        icon = view.iconSize().width() if view.iconSize().isValid() else 16
        index = view.indexAt(view.viewport().rect().topLeft())
        bottom = view.viewport().height()
        while index.isValid():
            rect = view.visualRect(index)
            if rect.top() > bottom:
                break
            font = index.data(Qt.ItemDataRole.FontRole) or view.font()
            if index.data(MATCH_ROLE):
                font = QFont(font)
                font.setWeight(QFont.Weight.Bold)
            metrics = QFontMetrics(font)
            text = str(index.data() or "")
            width = metrics.horizontalAdvance(text)
            if letters:
                width = min(width, metrics.horizontalAdvance(text[:letters].ljust(letters, "x")))
            if rect.left() + icon + 12 + width > room:
                return True
            index = view.indexBelow(index)
        return False

    def _schedule_fit(self, *_args) -> None:
        self._fit_timer.start()

    def resizeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Fit the columns to the new width."""
        super().resizeEvent(event)
        self._fit_columns()

    def _connect_selection(self) -> None:
        self.view.selectionModel().currentChanged.connect(self._on_current_changed)

    def _use_model(self, model: QStandardItemModel) -> None:
        """Show the tree or the search results in the view, keeping what is open in the tree."""
        if self.view.model() is model:
            return
        if self.view.model() is self.model:
            self._expanded = self._expanded_items(self.model.invisibleRootItem())
        previous = self.view.selectionModel()
        if previous is not None:
            previous.currentChanged.disconnect(self._on_current_changed)
        self.view.setModel(model)
        if previous is not None:
            previous.deleteLater()
        self._size_header()
        self._connect_selection()
        if model is self.model:
            self.view.blockSignals(True)
            for item in self._expanded:
                self.view.expand(item.index())
            self.view.blockSignals(False)
            self._expanded = []

    def _expanded_items(self, parent: QStandardItem) -> list[QStandardItem]:
        """The loaded rows below ``parent`` that are open in the view, parents first."""
        items = []
        for row in range(parent.rowCount()):
            child = parent.child(row)
            if child.data(STATE_ROLE) == "loaded" and self.view.isExpanded(child.index()):
                items.append(child)
                items.extend(self._expanded_items(child))
        return items

    def _token(self, item: QStandardItem) -> tuple[int, int | None]:
        """What must still hold when a read for ``item`` comes back."""
        found = self._found_generation if item.model() is self.found_model else None
        return (self._generation, found)

    def _current(self, token: tuple[int, int | None]) -> bool:
        generation, found = token
        if generation != self._generation:
            return False
        return found is None or found == self._found_generation

    def _row_for(
        self, node: H5Node, name: str | None = None, mark_default: bool = True
    ) -> list[QStandardItem]:
        name_item = QStandardItem(name or node.name)
        name_item.setToolTip(name or node.name)
        name_item.setIcon(material_icon(node_icon_name(node), convert_to_pixmap=False))
        name_item.setData(node, NODE_ROLE)
        name_item.setData("unloaded", STATE_ROLE)
        shape = h5_reader.format_shape(node.shape) if node.kind == "dataset" else ""
        if node.kind == "group" and node.n_children is not None:
            shape = "1 item" if node.n_children == 1 else f"{node.n_children} items"
        shape_item = QStandardItem(shape)
        shape_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        type_item = QStandardItem(node_type_text(node))
        button_item = QStandardItem()
        if node.kind == "link":
            name_item.setToolTip(f"Link to {node.link_path} in {Path(node.link_file).name}")
            type_item.setToolTip(name_item.toolTip())
        if node.is_default and mark_default:
            font = name_item.font()
            font.setBold(True)
            name_item.setFont(font)
            name_item.setToolTip("The file names this as its default plot")
        if node.is_container and node.n_children != 0:
            name_item.appendRow(self._placeholder("Loading…"))
        return [name_item, shape_item, type_item, button_item]

    @staticmethod
    def _placeholder(text: str, icon: str = "") -> list[QStandardItem]:
        item = QStandardItem(text)
        item.setData(True, PLACEHOLDER_ROLE)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        if icon:
            item.setIcon(material_icon(icon, convert_to_pixmap=False))
        font = item.font()
        font.setItalic(True)
        item.setFont(font)
        return [item]

    def _set_node(self, item: QStandardItem, node: H5Node) -> None:
        """Replace the node of a row, after its link was followed."""
        parent = item.parent() or item.model().invisibleRootItem()
        item.setData(node, NODE_ROLE)
        shape = h5_reader.format_shape(node.shape) if node.kind == "dataset" else ""
        parent.child(item.row(), 1).setText(shape)

    ################################################################################
    # Listing groups
    ################################################################################

    def _on_expanded(self, index: QModelIndex) -> None:
        item = self.view.model().itemFromIndex(index)
        if item is None:
            return
        if item.data(STATE_ROLE) == "unloaded":
            self._load(item)
        elif item.data(STATE_ROLE) == "loaded" and item.model() is self.model:
            self._continue_path(item)

    def _on_collapsed(self, index: QModelIndex) -> None:
        item = self.view.model().itemFromIndex(index)
        if item is not None and item.data(STATE_ROLE) == "failed":
            # Opening it again tries again.
            item.removeRows(0, item.rowCount())
            item.appendRow(self._placeholder("Loading…"))
            item.setData("unloaded", STATE_ROLE)

    def _load(self, item: QStandardItem) -> None:
        node: H5Node = item.data(NODE_ROLE)
        item.setData("loading", STATE_ROLE)
        generation = self._token(item)
        found = "-found" if item.model() is self.found_model else ""
        channel = f"{self._channel}-list{found}-{node.file_path}-{node.path}"
        if node.kind == "link":
            self._service.request(
                channel,
                node.link_file,
                lambda _ctx, node=node: h5_reader.resolve_link(node),
                partial(self._on_link_resolved, generation, item),
                partial(self._on_load_failed, generation, item),
            )
            return
        self._service.request(
            channel,
            node.file_path,
            lambda _ctx, node=node: h5_reader.list_children(node.file_path, node.path),
            partial(self._on_children, generation, item),
            partial(self._on_load_failed, generation, item),
        )

    def _on_link_resolved(self, generation, item: QStandardItem, target: H5Node) -> None:
        if not self._current(generation):
            return
        self._set_node(item, target)
        if target.kind == "group":
            self._load(item)
            return
        item.removeRows(0, item.rowCount())
        item.setData("loaded", STATE_ROLE)
        if self.view.currentIndex() == item.index():
            self._select_timer.start()

    def _on_children(self, generation, item: QStandardItem, nodes: list[H5Node]) -> None:
        if not self._current(generation):
            return
        item.removeRows(0, item.rowCount())
        if self.view.model() is item.model():
            self.view.setFirstColumnSpanned(0, item.index(), False)
        # In the search results bold marks the matches, not the default plot.
        mark_default = item.model() is self.model
        parent: H5Node = item.data(NODE_ROLE)
        for node in nodes:
            item.appendRow(self._row_for(node, mark_default=mark_default))
            if parent is not None and parent.nx_class == "NXdata" and node.is_default:
                # The group's row stands for this dataset on the plot.
                if can_keep(node):
                    self._group_signals[parent.path] = node
        if not nodes:
            item.appendRow(self._placeholder("Empty"))
        item.setData("loaded", STATE_ROLE)
        if item.model() is not self.model:
            return
        node: H5Node = item.data(NODE_ROLE)
        if node.kind == "file" and node.file_path == self._file_path:
            self.file_listed.emit(self._file_path)
        self._continue_path(item)

    def _on_load_failed(self, generation, item: QStandardItem, error: H5ReadError) -> None:
        if not self._current(generation):
            return
        item.removeRows(0, item.rowCount())
        item.appendRow(self._placeholder(error.message, "error"))
        if self.view.model() is item.model():
            self.view.setFirstColumnSpanned(0, item.index(), True)
        item.setData("failed", STATE_ROLE)
        if item.model() is not self.model:
            return
        node: H5Node = item.data(NODE_ROLE)
        if node.kind == "file" and node.file_path == self._file_path:
            self.file_failed.emit(error)

    @staticmethod
    def _item_names(item: QStandardItem) -> list[str]:
        """The names from the file down to ``item``, the file itself left out."""
        names = []
        while item.parent() is not None:
            names.insert(0, item.text())
            item = item.parent()
        return names

    def _continue_path(self, item: QStandardItem) -> None:
        """Open the next level of the path that is being followed."""
        node: H5Node = item.data(NODE_ROLE)
        if node.file_path != self._file_path and not self._pending_path:
            return
        if item.data(STATE_ROLE) != "loaded":
            if item.data(STATE_ROLE) == "unloaded":
                self.view.expand(item.index())
            return
        children = [item.child(row) for row in range(item.rowCount())]
        children = [child for child in children if not child.data(PLACEHOLDER_ROLE)]
        target = None
        if self._pending_path:
            if self._item_names(item) != self._path_done:
                # A row of an older path, or one opened by hand, finished loading: the path
                # goes on from its own row only.
                return
            wanted = self._pending_path[0]
            target = next((child for child in children if child.text() == wanted), None)
            if target is None:
                self._pending_path = []
                self._pick_path = []
                return
            self._path_done.append(self._pending_path.pop(0))
            last = not self._pending_path
        elif self._follow_default:
            depth = 0
            walker = item
            while walker.parent() is not None:
                walker = walker.parent()
                depth += 1
            defaults = [child for child in children if child.data(NODE_ROLE).is_default]
            groups = [child for child in children if child.data(NODE_ROLE).kind == "group"]
            if defaults:
                target = defaults[0]
            elif len(groups) == 1 and depth < AUTO_EXPAND_DEPTH:
                target = groups[0]
            if target is None:
                self._follow_default = False
                return
            last = target.data(NODE_ROLE).kind == "dataset"
        else:
            return
        if last:
            self._follow_default = False
            self.view.setCurrentIndex(target.index())
            self.view.scrollTo(target.index())
            if self._pick_path and self._pick_path == self._path_done:
                self._pick_path = []
                self.mark_pick()
            if target.data(NODE_ROLE).is_container and self._pending_path == []:
                self.view.expand(target.index())
            return
        if self.view.isExpanded(target.index()):
            self._continue_path(target)
        else:
            self.view.expand(target.index())

    ################################################################################
    # Selection
    ################################################################################

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        # Another row: a pick of the row before is void, one of this row comes after.
        self._pick_pending = False
        if current.isValid() and current.data(PLACEHOLDER_ROLE):
            return
        self._select_timer.start()

    def _emit_selection(self) -> None:
        index = self.view.currentIndex()
        if not index.isValid():
            if not self._pending_path:
                self._emit_node(None)
            return
        index = index.sibling(index.row(), 0)
        node: H5Node | None = index.data(NODE_ROLE)
        if node is None:
            return
        if node.kind != "link":
            self._emit_node(node)
            return
        generation = self._generation
        model = index.model()
        item = model.itemFromIndex(index)

        def _resolved(target: H5Node):
            if generation != self._generation or self.view.model() is not model:
                return
            if model is self.model:
                self._set_node(item, target)
            else:
                item.setData(target, NODE_ROLE)
            if self.view.currentIndex().sibling(self.view.currentIndex().row(), 0) == index:
                self._emit_node(target)

        def _failed(error: H5ReadError):
            if generation != self._generation:
                return
            broken = H5Node(
                name=node.name,
                path=node.path,
                file_path=node.file_path,
                kind="broken",
                link_file=node.link_file,
                link_path=error.message,
            )
            self._emit_node(broken)

        self._service.request(
            f"{self._channel}-select",
            node.link_file,
            lambda _ctx: h5_reader.resolve_link(node),
            _resolved,
            _failed,
        )

    def mark_pick(self) -> None:
        """
        The user picked the current row by hand: :attr:`node_picked` carries its node, at once
        for the row that is shown already, else with the node once it is read.
        """
        node = self.current_node()
        if node is None:
            return
        if not self._select_timer.isActive() and node == self._shown_node:
            self._pick_pending = False
            self.node_picked.emit(node)
            return
        self._pick_pending = True

    def pick_when_selected(self, path: str) -> None:
        """
        Count the row of ``path`` as picked by hand once :meth:`select_path`, or the path given
        to :meth:`set_file`, selects it: the dataset was asked for by name.

        Args:
            path (str): Path inside the main file.
        """
        self._pick_path = [part for part in path.split("/") if part]

    def _emit_node(self, node: H5Node | None) -> None:
        """Announce the selected node, unless it is the one already shown, and a pick of it."""
        picked, self._pick_pending = self._pick_pending, False
        if node is None or node != self._shown_node:
            self._shown_node = node
            self.node_selected.emit(node)
        if picked and node is not None:
            self.node_picked.emit(node)

    def _show_menu(self, position: QPoint) -> None:
        index = self.view.indexAt(position)
        node: H5Node | None = index.sibling(index.row(), 0).data(NODE_ROLE)
        if node is None:
            return
        menu = QMenu(self)
        copy_path = menu.addAction("Copy path in file")
        copy_file = menu.addAction("Copy file path")
        chosen = menu.exec(self.view.viewport().mapToGlobal(position))
        if chosen is copy_path:
            QGuiApplication.clipboard().setText(node.path)
        elif chosen is copy_file:
            QGuiApplication.clipboard().setText(node.file_path)

    ################################################################################
    # Find by name
    ################################################################################

    def enter_results(self) -> bool:
        """
        Move from the search field into the results and select the first match.

        Returns:
            bool: Whether there were results to move into.
        """
        if self.view.model() is not self.found_model:
            return False
        first = self._first_match(self.found_model.invisibleRootItem())
        if first is None:
            return False
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)
        self.view.setCurrentIndex(first.index())
        self.view.scrollTo(first.index())
        return True

    def _first_match(self, parent: QStandardItem) -> QStandardItem | None:
        for row in range(parent.rowCount()):
            child = parent.child(row)
            if child.data(MATCH_ROLE):
                return child
            found = self._first_match(child)
            if found is not None:
                return found
        return None

    def _show_tree(self, reveal: bool = True) -> None:
        """
        Leave the search and show the whole file again.

        Args:
            reveal (bool): Open the tree along the entry selected in the results.
        """
        self._find_timer.stop()
        self._service.cancel(f"{self._channel}-find")
        self._service.cancel_all(f"{self._channel}-list-found")
        self.note.hide()
        selected = self.current_node() if self.view.model() is self.found_model else None
        self._found_generation += 1
        self._use_model(self.model)
        self.found_model.removeRows(0, self.found_model.rowCount())
        if reveal and selected is not None and selected.file_path == self._file_path:
            self._pending_path = [part for part in selected.path.split("/") if part]
            self._path_done = []
            self._follow_default = False
            if self.model.rowCount():
                self._continue_path(self.model.item(0))

    def _on_find_text(self, text: str) -> None:
        if not text.strip():
            self._show_tree()
            return
        self._find_timer.start()

    def _find(self) -> None:
        text = self.find_edit.text().strip()
        if not self._file_path:
            return
        if len(text) < 2:
            if self.view.model() is self.found_model:
                self._show_tree(reveal=False)
            self.note.setText("Type at least two letters.")
            self.note.show()
            return
        generation = self._generation
        file_path = self._file_path
        self.note.setText("Searching…")
        self.note.show()

        def _found(result: FoundBranches):
            if generation != self._generation or self.find_edit.text().strip() != text:
                return
            self._show_results(file_path, text, result)

        def _failed(error: H5ReadError):
            if generation == self._generation:
                self.note.setText(error.message)

        self._service.request(
            f"{self._channel}-find",
            file_path,
            lambda ctx: h5_reader.find_branches(file_path, text, cancel=ctx.cancelled),
            _found,
            _failed,
        )

    def _show_results(self, file_path: str, text: str, result: FoundBranches) -> None:
        """Fill the results with the branches that lead to a match, opened, and show them."""
        self._found_generation += 1
        self._service.cancel_all(f"{self._channel}-list-found")
        self.found_model.removeRows(0, self.found_model.rowCount())
        needle = text.lower()
        root = H5Node(name=Path(file_path).name, path="/", file_path=file_path, kind="file")
        root_row = self._row_for(root, mark_default=False)
        root_row[0].removeRows(0, root_row[0].rowCount())
        root_row[0].setData("filtered", STATE_ROLE)
        root_row[0].setToolTip(file_path)
        self.found_model.appendRow(root_row)
        items: dict[str, QStandardItem] = {"/": root_row[0]}
        nodes = {node.path: node for node in (*result.ancestors, *result.matches)}
        matched = {node.path for node in result.matches}
        branches = set()
        for path in matched:
            parts = [part for part in path.split("/") if part]
            branches.update("/" + "/".join(parts[:depth]) for depth in range(1, len(parts)))

        def _item(path: str) -> QStandardItem | None:
            if path in items:
                return items[path]
            node = nodes.get(path)
            parent = _item(path.rsplit("/", 1)[0] or "/")
            if node is None or parent is None:
                return None
            row = self._row_for(node, mark_default=False)
            row[0].setToolTip(path)
            if path in matched:
                start = node.name.lower().find(needle)
                row[0].setData((start, len(needle)) if start >= 0 else None, MATCH_ROLE)
            else:
                row[0].setData(True, CONTEXT_ROLE)
            if path in branches:
                # Lists the way to the matches below it, not all of its children.
                row[0].removeRows(0, row[0].rowCount())
                row[0].setData("filtered", STATE_ROLE)
            parent.appendRow(row)
            items[path] = row[0]
            return row[0]

        for node in result.matches:
            _item(node.path)
        self._use_model(self.found_model)
        for path in ("/", *sorted(branches, key=lambda p: p.count("/"))):
            item = items.get(path)
            if item is not None:
                self.view.expand(item.index())
        count = len(result.matches)
        if count == 0:
            self.note.setText(f"No name in this file contains “{text}”.")
        elif result.truncated:
            self.note.setText("Showing the first 200 matches. Type more to narrow it down.")
        else:
            self.note.setText("1 match" if count == 1 else f"{count} matches")
        self.note.show()
