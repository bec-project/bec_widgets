"""
The tree of the HDF5 viewer: files, groups and datasets, listed one group at a time.

A group is listed when it is expanded, never before. Links into other files are shown as
links and their file is opened only when the link is expanded or selected.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from bec_qthemes import material_icon
from qtpy.QtCore import QModelIndex, QPoint, Qt, QTimer, Signal
from qtpy.QtGui import QGuiApplication, QPalette, QStandardItem, QStandardItemModel
from qtpy.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.services.hdf5_viewer import h5_reader
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import H5Node, H5ReadError
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service

NODE_ROLE = Qt.ItemDataRole.UserRole + 1
STATE_ROLE = Qt.ItemDataRole.UserRole + 2
PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 3

#: Pause after the last change of the selection before a preview is asked for.
SELECT_DELAY_MS = 150
#: Pause after the last key stroke before the file is searched.
FIND_DELAY_MS = 300
#: Deepest level the tree opens by itself when a file is shown.
AUTO_EXPAND_DEPTH = 6


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


class _MutedColumnDelegate(QStyledItemDelegate):
    """Draws the shape and type columns in the muted text colour of the theme."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        super().initStyleOption(option, index)
        if index.column() > 0 or index.data(PLACEHOLDER_ROLE):
            muted = option.palette.color(QPalette.ColorRole.PlaceholderText)
            option.palette.setColor(QPalette.ColorRole.Text, muted)


class H5Tree(QWidget):
    """Tree of one main file and the files next to it, with a search by name."""

    #: The node to preview: an :class:`H5Node`, with links already followed, or None.
    node_selected = Signal(object)
    #: The main file could not be listed; carries the :class:`H5ReadError`.
    file_failed = Signal(object)
    #: The top level of the main file was listed.
    file_listed = Signal(str)

    def __init__(self, service: H5Service, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._generation = 0
        self._file_path = ""
        self._pending_path: list[str] = []
        self._follow_default = False
        self._channel = f"tree-{id(self)}"

        self.find_edit = QLineEdit(self)
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
            model.setHorizontalHeaderLabels(["Name", "Shape", "Type"])

        self.view = QTreeView(self)
        self.view.setModel(self.model)
        self.view.setItemDelegate(_MutedColumnDelegate(self.view))
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
        self.note.setEnabled(False)
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

        self.view.expanded.connect(self._on_expanded)
        self.view.collapsed.connect(self._on_collapsed)
        self.view.customContextMenuRequested.connect(self._show_menu)
        self.find_edit.textChanged.connect(self._on_find_text)
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
        self._file_path = file_path or ""
        self._pending_path = [part for part in select_path.split("/") if part]
        self._follow_default = not self._pending_path
        self.find_edit.blockSignals(True)
        self.find_edit.clear()
        self.find_edit.blockSignals(False)
        self._show_tree()
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
        self.find_edit.clear()
        self._pending_path = [part for part in path.split("/") if part]
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

    def cleanup(self) -> None:
        """Stop the timers and drop the pending reads."""
        self._generation += 1
        self._select_timer.stop()
        self._find_timer.stop()
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
        header.setMinimumSectionSize(48)

    def _connect_selection(self) -> None:
        self.view.selectionModel().currentChanged.connect(self._on_current_changed)

    def _use_model(self, model: QStandardItemModel) -> None:
        """Show the tree or the list of matches in the view."""
        if self.view.model() is model:
            return
        previous = self.view.selectionModel()
        self.view.setModel(model)
        if previous is not None:
            previous.deleteLater()
        self.view.setRootIsDecorated(model is self.model)
        self._size_header()
        self._connect_selection()

    def _row_for(self, node: H5Node, name: str | None = None) -> list[QStandardItem]:
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
        if node.kind == "link":
            name_item.setToolTip(f"Link to {node.link_path} in {Path(node.link_file).name}")
            type_item.setToolTip(name_item.toolTip())
        if node.is_default:
            font = name_item.font()
            font.setBold(True)
            name_item.setFont(font)
            name_item.setToolTip("The file names this as its default plot")
        if node.is_container and node.n_children != 0:
            name_item.appendRow(self._placeholder("Loading…"))
        return [name_item, shape_item, type_item]

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
        parent = item.parent() or self.model.invisibleRootItem()
        item.setData(node, NODE_ROLE)
        shape = h5_reader.format_shape(node.shape) if node.kind == "dataset" else ""
        parent.child(item.row(), 1).setText(shape)

    ################################################################################
    # Listing groups
    ################################################################################

    def _on_expanded(self, index: QModelIndex) -> None:
        if self.view.model() is not self.model:
            return
        item = self.model.itemFromIndex(index)
        if item is not None and item.data(STATE_ROLE) == "unloaded":
            self._load(item)

    def _on_collapsed(self, index: QModelIndex) -> None:
        if self.view.model() is not self.model:
            return
        item = self.model.itemFromIndex(index)
        if item is not None and item.data(STATE_ROLE) == "failed":
            # Opening it again tries again.
            item.removeRows(0, item.rowCount())
            item.appendRow(self._placeholder("Loading…"))
            item.setData("unloaded", STATE_ROLE)

    def _load(self, item: QStandardItem) -> None:
        node: H5Node = item.data(NODE_ROLE)
        item.setData("loading", STATE_ROLE)
        generation = self._generation
        channel = f"{self._channel}-list-{node.file_path}-{node.path}"
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

    def _on_link_resolved(self, generation: int, item: QStandardItem, target: H5Node) -> None:
        if generation != self._generation:
            return
        self._set_node(item, target)
        if target.kind == "group":
            self._load(item)
            return
        item.removeRows(0, item.rowCount())
        item.setData("loaded", STATE_ROLE)
        if self.view.currentIndex() == item.index():
            self._select_timer.start()

    def _on_children(self, generation: int, item: QStandardItem, nodes: list[H5Node]) -> None:
        if generation != self._generation:
            return
        item.removeRows(0, item.rowCount())
        self.view.setFirstColumnSpanned(0, item.index(), False)
        for node in nodes:
            item.appendRow(self._row_for(node))
        if not nodes:
            item.appendRow(self._placeholder("Empty"))
        item.setData("loaded", STATE_ROLE)
        node: H5Node = item.data(NODE_ROLE)
        if node.kind == "file" and node.file_path == self._file_path:
            self.file_listed.emit(self._file_path)
        self._continue_path(item)

    def _on_load_failed(self, generation: int, item: QStandardItem, error: H5ReadError) -> None:
        if generation != self._generation:
            return
        item.removeRows(0, item.rowCount())
        item.appendRow(self._placeholder(error.message, "error"))
        self.view.setFirstColumnSpanned(0, item.index(), True)
        item.setData("failed", STATE_ROLE)
        node: H5Node = item.data(NODE_ROLE)
        if node.kind == "file" and node.file_path == self._file_path:
            self.file_failed.emit(error)

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
            wanted = self._pending_path[0]
            target = next((child for child in children if child.text() == wanted), None)
            if target is None:
                self._pending_path = []
                return
            self._pending_path.pop(0)
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
        if current.isValid() and current.data(PLACEHOLDER_ROLE):
            return
        self._select_timer.start()

    def _emit_selection(self) -> None:
        index = self.view.currentIndex()
        if not index.isValid():
            self.node_selected.emit(None)
            return
        index = index.sibling(index.row(), 0)
        node: H5Node | None = index.data(NODE_ROLE)
        if node is None:
            return
        if node.kind != "link":
            self.node_selected.emit(node)
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
                self.node_selected.emit(target)

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
            self.node_selected.emit(broken)

        self._service.request(
            f"{self._channel}-select",
            node.link_file,
            lambda _ctx: h5_reader.resolve_link(node),
            _resolved,
            _failed,
        )

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

    def _show_tree(self) -> None:
        self._find_timer.stop()
        self._service.cancel(f"{self._channel}-find")
        self.note.hide()
        self._use_model(self.model)

    def _on_find_text(self, text: str) -> None:
        if len(text.strip()) < 2:
            self._show_tree()
            if text.strip():
                self.note.setText("Type at least two letters.")
                self.note.show()
            return
        self._find_timer.start()

    def _find(self) -> None:
        text = self.find_edit.text().strip()
        if len(text) < 2 or not self._file_path:
            return
        generation = self._generation
        file_path = self._file_path
        self.note.setText("Searching…")
        self.note.show()

        def _found(nodes: list[H5Node]):
            if generation != self._generation or self.find_edit.text().strip() != text:
                return
            self.found_model.removeRows(0, self.found_model.rowCount())
            for node in nodes:
                row = self._row_for(node, name=node.path)
                row[0].removeRows(0, row[0].rowCount())
                self.found_model.appendRow(row)
            self._use_model(self.found_model)
            if not nodes:
                self.note.setText(f"No name in this file contains “{text}”.")
            elif len(nodes) >= 200:
                self.note.setText("Showing the first 200 matches. Type more to narrow it down.")
            else:
                count = "1 match" if len(nodes) == 1 else f"{len(nodes)} matches"
                self.note.setText(f"{count}. Clear the search to see the tree again.")

        def _failed(error: H5ReadError):
            if generation == self._generation:
                self.note.setText(error.message)

        self._service.request(
            f"{self._channel}-find",
            file_path,
            lambda ctx: h5_reader.find_nodes(file_path, text, cancel=ctx.cancelled),
            _found,
            _failed,
        )
