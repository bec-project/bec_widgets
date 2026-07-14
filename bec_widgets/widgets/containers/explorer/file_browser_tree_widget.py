import os
from fnmatch import fnmatch
from pathlib import Path

from bec_lib.logger import bec_logger
from qtpy.QtCore import QModelIndex, QPoint, QSortFilterProxyModel, Qt, Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QFileSystemModel,
    QInputDialog,
    QMenu,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

logger = bec_logger.logger


class _FileBrowserFilterProxyModel(QSortFilterProxyModel):
    """Filter out cache directories while keeping the filesystem model behavior."""

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source_model = self.sourceModel()
        if source_model is None:
            return False

        index = source_model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False

        file_name = source_model.fileName(index)
        if file_name in {"__pycache__", "__init__.py"}:
            return False
        return super().filterAcceptsRow(source_row, source_parent)


class FileBrowserTreeWidget(QWidget):
    """A plain QFileSystemModel browser pinned to a single directory."""

    file_selected = Signal(str)
    file_open_requested = Signal(str)
    file_delete_requested = Signal(str)
    file_renamed = Signal(str, str)

    def __init__(
        self,
        parent=None,
        directory: str | None = None,
        read_only: bool = False,
        name_filters: list[str] | None = None,
    ):
        """
        A file browser tree widget that displays files and directories in a tree view.

        Args:
            parent: The parent widget.
            directory: The initial directory to display. If None, the browser will be empty.
            read_only: If True, the browser will be in read-only mode (no drag-and-drop, no renaming, no deletion).
            name_filters: A list of name filters (e.g., ["*.py", "*.txt"]) to filter displayed files. If None, all files are displayed.
        """
        super().__init__(parent)
        self.name_filters = name_filters or ["*.py"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tree = QTreeView(parent=self)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setSortingEnabled(True)
        self.tree.setAnimated(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.model = QFileSystemModel(parent=self)
        self.model.setNameFilters(self.name_filters)
        self.model.setNameFilterDisables(False)
        self.proxy_model = _FileBrowserFilterProxyModel(parent=self)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setSourceModel(self.model)
        self.tree.setModel(self.proxy_model)

        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)

        self._apply_styling()

        self.directory: str | None = None
        self._selection_extending = False

        self.tree.clicked.connect(self._on_item_clicked)
        self.tree.doubleClicked.connect(self._on_item_double_clicked)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.model.fileRenamed.connect(self._on_model_file_renamed)

        layout.addWidget(self.tree)

        self.set_readonly(read_only)
        if directory:
            self.set_directory(directory)

    def _apply_styling(self):
        """Apply styling to the tree widget."""
        tree_style = """
            QTreeView {
                border: none;
                outline: 0;
                show-decoration-selected: 0;
            }
            QTreeView::branch {
                border-image: none;
                background: transparent;
            }
            QTreeView::item {
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """

        self.tree.setStyleSheet(tree_style)

    def set_directory(self, directory: str) -> None:
        """Pin the browser to a directory."""
        if not directory or not isinstance(directory, str) or not os.path.exists(directory):
            return

        self.directory = directory
        root_index = self.model.setRootPath(directory)
        self.tree.setRootIndex(self.proxy_model.mapFromSource(root_index))

    def set_readonly(self, read_only: bool) -> None:
        """Toggle read-only mode for the file browser."""
        self.model.setReadOnly(read_only)
        self.tree.setDragEnabled(not read_only)
        self.tree.setAcceptDrops(not read_only)
        self.tree.setDropIndicatorShown(not read_only)
        self.tree.setDragDropMode(
            QAbstractItemView.DragDropMode.NoDragDrop
            if read_only
            else QAbstractItemView.DragDropMode.InternalMove
        )

    def _on_item_clicked(self, index: QModelIndex):
        """Emit a selection signal for Python files."""
        self._selection_extending = self._is_multi_selection_modifier_pressed()
        source_index = self._map_to_source(index)
        if not source_index.isValid() or self.model.isDir(source_index):
            return

        selection_model = self.tree.selectionModel()
        if selection_model is not None and not selection_model.isSelected(index):
            return

        file_path = self.model.filePath(source_index)
        if not file_path or not os.path.isfile(file_path):
            return

        if self._matches_name_filters(file_path):
            logger.info(f"File selected: {file_path}")
            self.file_selected.emit(file_path)

    def is_selection_extending(self) -> bool:
        """Return whether the current click is extending an existing selection."""
        return self._selection_extending

    @staticmethod
    def _is_multi_selection_modifier_pressed() -> bool:
        modifiers = QApplication.keyboardModifiers()
        return bool(
            modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        )

    def _on_item_double_clicked(self, index: QModelIndex):
        """Emit an open signal for Python files."""
        source_index = self._map_to_source(index)
        if not source_index.isValid() or self.model.isDir(source_index):
            return

        file_path = self.model.filePath(source_index)
        if not file_path or not os.path.isfile(file_path):
            return

        logger.info(f"File open requested via double-click: {file_path}")
        self.file_open_requested.emit(file_path)

    def _on_file_open_requested(self):
        """Emit open for the currently selected file."""
        file_path = self._get_selected_file_path()
        if file_path:
            self.file_open_requested.emit(file_path)

    def _on_file_delete_requested(self):
        """Emit delete for the currently selected file."""
        index = self.tree.currentIndex()
        if not index.isValid():
            return

        source_index = self._map_to_source(index)
        file_path = self.model.filePath(source_index)
        if not file_path or self._is_root_path(file_path):
            return

        self.file_delete_requested.emit(file_path)

    def _get_selected_file_path(self) -> str | None:
        """Return the currently selected file path."""
        index = self.tree.currentIndex()
        if not index.isValid():
            return None

        source_index = self._map_to_source(index)
        file_path = self.model.filePath(source_index)
        if not file_path or not os.path.isfile(file_path):
            return None
        return file_path

    def clear_selection(self) -> None:
        """Clear the highlighted selection in the tree view."""
        selection_model = self.tree.selectionModel()
        if selection_model is not None:
            selection_model.clear()
        self.tree.setCurrentIndex(QModelIndex())

    def _show_context_menu(self, position: QPoint) -> None:
        """Show a right-click context menu for editable items."""
        if self.model.isReadOnly():
            return

        index = self.tree.indexAt(position)
        if index.isValid():
            self.tree.setCurrentIndex(index)

        menu = self._build_context_menu(index)
        if menu is None:
            return
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _build_context_menu(self, index: QModelIndex) -> QMenu | None:
        """Build the context menu for a specific model index."""
        if self.model.isReadOnly():
            return None

        menu = QMenu(self)
        target_directory = self._get_target_directory(index)
        if target_directory is not None:
            new_folder_action = QAction("New Folder", self)
            new_folder_action.triggered.connect(lambda: self._create_subdirectory(target_directory))
            menu.addAction(new_folder_action)

        source_index = self._map_to_source(index) if index.isValid() else QModelIndex()

        if source_index.isValid() and not self.model.isDir(source_index):
            open_action = QAction("Open", self)
            open_action.triggered.connect(self._on_file_open_requested)
            menu.addAction(open_action)

        file_path = self.model.filePath(source_index) if source_index.isValid() else None
        if index.isValid() and file_path and not self._is_root_path(file_path):
            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(lambda: self.tree.edit(index))
            menu.addAction(rename_action)

            delete_label = "Delete Folder" if self.model.isDir(source_index) else "Delete File"
            delete_action = QAction(delete_label, self)
            delete_action.triggered.connect(self._on_file_delete_requested)
            menu.addAction(delete_action)

        if not menu.actions():
            return None
        return menu

    def _on_model_file_renamed(self, directory: str, old_name: str, new_name: str) -> None:
        """Emit full rename paths when QFileSystemModel completes a rename."""
        old_path = os.path.join(directory, old_name)
        new_path = os.path.join(directory, new_name)
        self.file_renamed.emit(old_path, new_path)

    def _get_target_directory(self, index: QModelIndex) -> str | None:
        """Return the directory where a new subdirectory should be created."""
        if self.directory is None:
            return None

        if not index.isValid():
            return self.directory

        source_index = self._map_to_source(index)
        file_path = self.model.filePath(source_index)
        if not file_path:
            return self.directory

        if self.model.isDir(source_index):
            return file_path
        return os.path.dirname(file_path)

    def _create_subdirectory(self, parent_directory: str) -> None:
        """Prompt for and create a subdirectory inside parent_directory."""
        folder_name, ok = QInputDialog.getText(
            self, "New Folder", f"Enter folder name ({parent_directory}/<folder>):"
        )
        if not ok or not folder_name:
            return

        folder_name = folder_name.strip()
        if not folder_name or os.path.sep in folder_name:
            return

        os.makedirs(os.path.join(parent_directory, folder_name), exist_ok=True)
        self.refresh()

    def _is_root_path(self, file_path: str) -> bool:
        """Return True when a path is the pinned root directory itself."""
        if self.directory is None:
            return False
        return os.path.abspath(file_path) == os.path.abspath(self.directory)

    def refresh(self):
        """Refresh the tree view."""
        if self.directory is None:
            return
        self.model.setRootPath("")
        root_index = self.model.setRootPath(self.directory)
        self.tree.setRootIndex(self.proxy_model.mapFromSource(root_index))

    def expand_all(self):
        """Expand all items in the tree."""
        self.tree.expandAll()

    def collapse_all(self):
        """Collapse all items in the tree."""
        self.tree.collapseAll()

    def _map_to_source(self, index: QModelIndex) -> QModelIndex:
        """Map a tree index back to the QFileSystemModel index."""
        if not index.isValid():
            return QModelIndex()
        return self.proxy_model.mapToSource(index)

    def _matches_name_filters(self, file_path: str) -> bool:
        """Return whether file_path matches the configured name filters."""
        if not self.name_filters:
            return True

        file_name = Path(file_path).name.lower()
        return any(fnmatch(file_name, name_filter.lower()) for name_filter in self.name_filters)
