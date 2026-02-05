import os
from pathlib import Path

from bec_lib.logger import bec_logger
from qtpy.QtCore import QModelIndex, QRegularExpression, QSortFilterProxyModel, Signal
from qtpy.QtWidgets import QFileSystemModel, QTreeView, QVBoxLayout, QWidget

from bec_widgets.utils.colors import get_theme_palette
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.widgets.containers.explorer.explorer_delegate import ExplorerDelegate

logger = bec_logger.logger


class FileItemDelegate(ExplorerDelegate):
    """Custom delegate to show action buttons on hover"""

    def __init__(self, tree_widget):
        super().__init__(tree_widget)
        self.file_actions = []
        self.dir_actions = []

    def add_file_action(self, action) -> None:
        """Add an action for files"""
        self.file_actions.append(action)

    def add_dir_action(self, action) -> None:
        """Add an action for directories"""
        self.dir_actions.append(action)

    def clear_actions(self) -> None:
        """Remove all actions"""
        self.file_actions.clear()
        self.dir_actions.clear()

    def get_actions_for_current_item(self, model, index) -> list[MaterialIconAction] | None:
        """Get actions for the current item based on its type"""
        if not isinstance(model, QSortFilterProxyModel):
            return None

        source_index = model.mapToSource(index)
        source_model = model.sourceModel()
        if not isinstance(source_model, QFileSystemModel):
            return None

        is_dir = source_model.isDir(source_index)
        return self.dir_actions if is_dir else self.file_actions


class ScriptTreeWidget(QWidget):
    """A simple tree widget for scripts using QFileSystemModel - designed to be injected into CollapsibleSection"""

    file_selected = Signal(str)  # Script file path selected
    file_open_requested = Signal(str)  # File open button clicked
    file_renamed = Signal(str, str)  # Old path, new path

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create tree view
        self.tree = QTreeView(parent=self)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)

        # Enable mouse tracking for hover effects
        self.tree.setMouseTracking(True)

        # Create file system model
        self.model = QFileSystemModel(parent=self)
        self.model.setNameFilters(["*.py"])
        self.model.setNameFilterDisables(False)

        # Create proxy model to filter out underscore directories
        self.proxy_model = QSortFilterProxyModel(parent=self)
        self.proxy_model.setFilterRegularExpression(QRegularExpression("^[^_].*"))
        self.proxy_model.setSourceModel(self.model)
        self.tree.setModel(self.proxy_model)

        # Create and set custom delegate
        self.delegate = FileItemDelegate(self.tree)
        self.tree.setItemDelegate(self.delegate)

        # Add default open button for files
        action = MaterialIconAction(icon_name="file_open", tooltip="Open file", parent=self)
        action.action.triggered.connect(self._on_file_open_requested)
        self.delegate.add_file_action(action.action)

        # Remove unnecessary columns
        self.tree.setColumnHidden(1, True)  # Hide size column
        self.tree.setColumnHidden(2, True)  # Hide type column
        self.tree.setColumnHidden(3, True)  # Hide date modified column

        # Apply BEC styling
        self._apply_styling()

        # Script specific properties
        self.directory = None

        # Connect signals
        self.tree.clicked.connect(self._on_item_clicked)
        self.tree.doubleClicked.connect(self._on_item_double_clicked)

        # Install event filter for hover tracking
        self.tree.viewport().installEventFilter(self)

        # Add to layout
        layout.addWidget(self.tree)

    def _apply_styling(self):
        """Apply styling to the tree widget"""
        # Get theme colors for subtle tree lines
        palette = get_theme_palette()
        subtle_line_color = palette.mid().color()
        subtle_line_color.setAlpha(80)

        # Standard editable styling
        opacity_modifier = ""
        cursor_style = ""

        # pylint: disable=f-string-without-interpolation
        tree_style = f""" 
            QTreeView {{ 
                border: none;
                outline: 0;
                show-decoration-selected: 0;
                {opacity_modifier}
                {cursor_style}
            }}
            QTreeView::branch {{
                border-image: none;
                background: transparent;
            }}

            QTreeView::item {{
                border: none;
                padding: 0px;
                margin: 0px;
            }}
            QTreeView::item:hover {{
                background: palette(midlight);
                border: none;
                padding: 0px;
                margin: 0px;
                text-decoration: none;
            }}
            QTreeView::item:selected {{
                background: palette(highlight);
                color: palette(highlighted-text);
            }}
            QTreeView::item:selected:hover {{
                background: palette(highlight);
            }}
        """

        self.tree.setStyleSheet(tree_style)

    def eventFilter(self, obj, event):
        """Handle mouse move events for hover tracking"""
        # Early return if not the tree viewport
        if obj != self.tree.viewport():
            return super().eventFilter(obj, event)

        if event.type() == event.Type.MouseMove:
            index = self.tree.indexAt(event.pos())
            if index.isValid():
                self.delegate.set_hovered_index(index)
            else:
                self.delegate.set_hovered_index(QModelIndex())
            self.tree.viewport().update()
            return super().eventFilter(obj, event)

        if event.type() == event.Type.Leave:
            self.delegate.set_hovered_index(QModelIndex())
            self.tree.viewport().update()
            return super().eventFilter(obj, event)

        return super().eventFilter(obj, event)

    def set_directory(self, directory: str) -> None:
        """Set the scripts directory"""
        # Early return if directory doesn't exist
        if not directory or not isinstance(directory, str) or not os.path.exists(directory):
            return

        self.directory = directory

        root_index = self.model.setRootPath(directory)
        # Map the source model index to proxy model index
        proxy_root_index = self.proxy_model.mapFromSource(root_index)
        self.tree.setRootIndex(proxy_root_index)
        self.tree.expandAll()

    def _on_item_clicked(self, index: QModelIndex):
        """Handle item clicks"""
        # Map proxy index back to source index
        source_index = self.proxy_model.mapToSource(index)

        # Early return for directories
        if self.model.isDir(source_index):
            return

        file_path = self.model.filePath(source_index)

        # Early return if not a valid file
        if not file_path or not os.path.isfile(file_path):
            return

        path_obj = Path(file_path)

        # Only emit signal for Python files
        if path_obj.suffix.lower() == ".py":
            logger.info(f"Script selected: {file_path}")
            self.file_selected.emit(file_path)

    def _on_item_double_clicked(self, index: QModelIndex):
        """Handle item double-clicks"""
        # Map proxy index back to source index
        source_index = self.proxy_model.mapToSource(index)

        # Early return for directories
        if self.model.isDir(source_index):
            return

        file_path = self.model.filePath(source_index)

        # Early return if not a valid file
        if not file_path or not os.path.isfile(file_path):
            return

        # Emit signal to open the file
        logger.info(f"File open requested via double-click: {file_path}")
        self.file_open_requested.emit(file_path)

    def _on_file_open_requested(self):
        """Handle file open action triggered"""
        logger.info("File open requested")
        # Early return if no hovered item
        if not self.delegate.hovered_index.isValid():
            return

        source_index = self.proxy_model.mapToSource(self.delegate.hovered_index)
        file_path = self.model.filePath(source_index)

        # Early return if not a valid file
        if not file_path or not os.path.isfile(file_path):
            return

        self.file_open_requested.emit(file_path)

    def add_file_action(self, action) -> None:
        """Add an action for file items"""
        self.delegate.add_file_action(action)

    def add_dir_action(self, action) -> None:
        """Add an action for directory items"""
        self.delegate.add_dir_action(action)

    def clear_actions(self) -> None:
        """Remove all actions from items"""
        self.delegate.clear_actions()

    def refresh(self):
        """Refresh the tree view"""
        if self.directory is None:
            return
        self.model.setRootPath("")  # Reset
        root_index = self.model.setRootPath(self.directory)
        proxy_root_index = self.proxy_model.mapFromSource(root_index)
        self.tree.setRootIndex(proxy_root_index)

    def expand_all(self):
        """Expand all items in the tree"""
        self.tree.expandAll()

    def collapse_all(self):
        """Collapse all items in the tree"""
        self.tree.collapseAll()
