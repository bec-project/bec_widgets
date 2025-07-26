import os
from pathlib import Path

from bec_lib.logger import bec_logger
from qtpy.QtCore import QModelIndex, QRect, QRegularExpression, QSortFilterProxyModel, Qt, Signal
from qtpy.QtGui import QAction, QPainter
from qtpy.QtWidgets import QFileSystemModel, QStyledItemDelegate, QTreeView, QVBoxLayout, QWidget

from bec_widgets.utils.colors import get_theme_palette
from bec_widgets.utils.toolbars.actions import MaterialIconAction

logger = bec_logger.logger


class FileItemDelegate(QStyledItemDelegate):
    """Custom delegate to show action buttons on hover"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_index = QModelIndex()
        self.file_actions: list[QAction] = []
        self.dir_actions: list[QAction] = []
        self.button_rects: list[QRect] = []
        self.current_file_path = ""

    def add_file_action(self, action: QAction) -> None:
        """Add an action for files"""
        self.file_actions.append(action)

    def add_dir_action(self, action: QAction) -> None:
        """Add an action for directories"""
        self.dir_actions.append(action)

    def clear_actions(self) -> None:
        """Remove all actions"""
        self.file_actions.clear()
        self.dir_actions.clear()

    def paint(self, painter, option, index):
        """Paint the item with action buttons on hover"""
        # Paint the default item
        super().paint(painter, option, index)

        # Early return if not hovering over this item
        if index != self.hovered_index:
            return

        tree_view = self.parent()
        if not isinstance(tree_view, QTreeView):
            return

        proxy_model = tree_view.model()
        if not isinstance(proxy_model, QSortFilterProxyModel):
            return

        source_index = proxy_model.mapToSource(index)
        source_model = proxy_model.sourceModel()
        if not isinstance(source_model, QFileSystemModel):
            return

        is_dir = source_model.isDir(source_index)
        file_path = source_model.filePath(source_index)
        self.current_file_path = file_path

        # Choose appropriate actions based on item type
        actions = self.dir_actions if is_dir else self.file_actions
        if actions:
            self._draw_action_buttons(painter, option, actions)

    def _draw_action_buttons(self, painter, option, actions: list[QAction]):
        """Draw action buttons on the right side"""
        button_size = 18
        margin = 4
        spacing = 2

        # Calculate total width needed for all buttons
        total_width = len(actions) * button_size + (len(actions) - 1) * spacing

        # Clear previous button rects and create new ones
        self.button_rects.clear()

        # Calculate starting position (right side of the item)
        start_x = option.rect.right() - total_width - margin
        current_x = start_x

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get theme colors for better integration
        palette = get_theme_palette()
        button_bg = palette.button().color()
        button_bg.setAlpha(150)  # Semi-transparent

        for action in actions:
            if not action.isVisible():
                continue

            # Calculate button position
            button_rect = QRect(
                current_x,
                option.rect.top() + (option.rect.height() - button_size) // 2,
                button_size,
                button_size,
            )
            self.button_rects.append(button_rect)

            # Draw button background
            painter.setBrush(button_bg)
            painter.setPen(palette.mid().color())
            painter.drawRoundedRect(button_rect, 3, 3)

            # Draw action icon
            icon = action.icon()
            if not icon.isNull():
                icon_rect = button_rect.adjusted(2, 2, -2, -2)
                icon.paint(painter, icon_rect)

            # Move to next button position
            current_x += button_size + spacing

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Handle mouse events for action buttons"""
        # Early return if not a left click
        if not (
            event.type() == event.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            return super().editorEvent(event, model, option, index)

        # Early return if not a proxy model
        if not isinstance(model, QSortFilterProxyModel):
            return super().editorEvent(event, model, option, index)

        source_index = model.mapToSource(index)
        source_model = model.sourceModel()

        # Early return if not a file system model
        if not isinstance(source_model, QFileSystemModel):
            return super().editorEvent(event, model, option, index)

        is_dir = source_model.isDir(source_index)
        actions = self.dir_actions if is_dir else self.file_actions

        # Check which button was clicked
        visible_actions = [action for action in actions if action.isVisible()]
        for i, button_rect in enumerate(self.button_rects):
            if button_rect.contains(event.pos()) and i < len(visible_actions):
                # Trigger the action
                visible_actions[i].trigger()
                return True

        return super().editorEvent(event, model, option, index)

    def set_hovered_index(self, index):
        """Set the currently hovered index"""
        self.hovered_index = index


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
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)

        # Enable mouse tracking for hover effects
        self.tree.setMouseTracking(True)

        # Create file system model
        self.model = QFileSystemModel()
        self.model.setNameFilters(["*.py"])
        self.model.setNameFilterDisables(False)

        # Create proxy model to filter out underscore directories
        self.proxy_model = QSortFilterProxyModel()
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

        # pylint: disable=f-string-without-interpolation
        tree_style = f""" 
            QTreeView {{ 
                border: none;
                outline: 0;
                show-decoration-selected: 0;
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

    def set_directory(self, directory):
        """Set the scripts directory"""
        self.directory = directory

        # Early return if directory doesn't exist
        if not directory or not os.path.exists(directory):
            return

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

    def add_file_action(self, action: QAction) -> None:
        """Add an action for file items"""
        self.delegate.add_file_action(action)

    def add_dir_action(self, action: QAction) -> None:
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
