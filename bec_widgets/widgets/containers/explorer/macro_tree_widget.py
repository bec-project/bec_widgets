import ast
import os
from pathlib import Path
from typing import Any

from bec_lib.logger import bec_logger
from qtpy.QtCore import QModelIndex, QRect, Qt, Signal
from qtpy.QtGui import QPainter, QStandardItem, QStandardItemModel
from qtpy.QtWidgets import QStyledItemDelegate, QTreeView, QVBoxLayout, QWidget

from bec_widgets.utils.colors import get_theme_palette
from bec_widgets.utils.toolbars.actions import MaterialIconAction

logger = bec_logger.logger


class MacroItemDelegate(QStyledItemDelegate):
    """Custom delegate to show action buttons on hover for macro functions"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_index = QModelIndex()
        self.macro_actions: list[Any] = []
        self.button_rects: list[QRect] = []
        self.current_macro_info = {}

    def add_macro_action(self, action: Any) -> None:
        """Add an action for macro functions"""
        self.macro_actions.append(action)

    def clear_actions(self) -> None:
        """Remove all actions"""
        self.macro_actions.clear()

    def paint(self, painter, option, index):
        """Paint the item with action buttons on hover"""
        # Paint the default item
        super().paint(painter, option, index)

        # Early return if not hovering over this item
        if index != self.hovered_index:
            return

        # Only show actions for macro functions (not directories)
        item = index.model().itemFromIndex(index)
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return

        macro_info = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(macro_info, dict) or "function_name" not in macro_info:
            return

        self.current_macro_info = macro_info

        if self.macro_actions:
            self._draw_action_buttons(painter, option, self.macro_actions)

    def _draw_action_buttons(self, painter, option, actions: list[Any]):
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

        # Check which button was clicked
        visible_actions = [action for action in self.macro_actions if action.isVisible()]
        for i, button_rect in enumerate(self.button_rects):
            if button_rect.contains(event.pos()) and i < len(visible_actions):
                # Trigger the action
                visible_actions[i].trigger()
                return True

        return super().editorEvent(event, model, option, index)

    def set_hovered_index(self, index):
        """Set the currently hovered index"""
        self.hovered_index = index


class MacroTreeWidget(QWidget):
    """A tree widget that displays macro functions from Python files"""

    macro_selected = Signal(str, str)  # Function name, file path
    macro_open_requested = Signal(str, str)  # Function name, file path

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

        # Disable editing to prevent renaming on double-click
        self.tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)

        # Enable mouse tracking for hover effects
        self.tree.setMouseTracking(True)

        # Create model for macro functions
        self.model = QStandardItemModel()
        self.tree.setModel(self.model)

        # Create and set custom delegate
        self.delegate = MacroItemDelegate(self.tree)
        self.tree.setItemDelegate(self.delegate)

        # Add default open button for macros
        action = MaterialIconAction(icon_name="file_open", tooltip="Open macro file", parent=self)
        action.action.triggered.connect(self._on_macro_open_requested)
        self.delegate.add_macro_action(action.action)

        # Apply BEC styling
        self._apply_styling()

        # Macro specific properties
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

    def set_directory(self, directory):
        """Set the macros directory and scan for macro functions"""
        self.directory = directory

        # Early return if directory doesn't exist
        if not directory or not os.path.exists(directory):
            return

        self._scan_macro_functions()

    def _create_file_item(self, py_file: Path) -> QStandardItem | None:
        """Create a file item with its functions

        Args:
            py_file: Path to the Python file

        Returns:
            QStandardItem representing the file, or None if no functions found
        """
        # Skip files starting with underscore
        if py_file.name.startswith("_"):
            return None

        try:
            functions = self._extract_functions_from_file(py_file)
            if not functions:
                return None

            # Create a file node
            file_item = QStandardItem(py_file.stem)
            file_item.setData({"file_path": str(py_file), "type": "file"}, Qt.ItemDataRole.UserRole)

            # Add function nodes
            for func_name, func_info in functions.items():
                func_item = QStandardItem(func_name)
                func_data = {
                    "function_name": func_name,
                    "file_path": str(py_file),
                    "line_number": func_info.get("line_number", 1),
                    "type": "function",
                }
                func_item.setData(func_data, Qt.ItemDataRole.UserRole)
                file_item.appendRow(func_item)

            return file_item
        except Exception as e:
            logger.warning(f"Failed to parse {py_file}: {e}")
            return None

    def _scan_macro_functions(self):
        """Scan the directory for Python files and extract macro functions"""
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Macros"])

        if not self.directory or not os.path.exists(self.directory):
            return

        # Get all Python files in the directory
        python_files = list(Path(self.directory).glob("*.py"))

        for py_file in python_files:
            file_item = self._create_file_item(py_file)
            if file_item:
                self.model.appendRow(file_item)

        self.tree.expandAll()

    def _extract_functions_from_file(self, file_path: Path) -> dict:
        """Extract function definitions from a Python file"""
        functions = {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse the AST
            tree = ast.parse(content)

            # Only get top-level function definitions
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    functions[node.name] = {
                        "line_number": node.lineno,
                        "docstring": ast.get_docstring(node) or "",
                    }

        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")

        return functions

    def _on_item_clicked(self, index: QModelIndex):
        """Handle item clicks"""
        item = self.model.itemFromIndex(index)
        if not item:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "function":
            function_name = data.get("function_name")
            file_path = data.get("file_path")
            if function_name and file_path:
                logger.info(f"Macro function selected: {function_name} in {file_path}")
                self.macro_selected.emit(function_name, file_path)

    def _on_item_double_clicked(self, index: QModelIndex):
        """Handle item double-clicks"""
        item = self.model.itemFromIndex(index)
        if not item:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "function":
            function_name = data.get("function_name")
            file_path = data.get("file_path")
            if function_name and file_path:
                logger.info(
                    f"Macro open requested via double-click: {function_name} in {file_path}"
                )
                self.macro_open_requested.emit(function_name, file_path)

    def _on_macro_open_requested(self):
        """Handle macro open action triggered"""
        logger.info("Macro open requested")
        # Early return if no hovered item
        if not self.delegate.hovered_index.isValid():
            return

        macro_info = self.delegate.current_macro_info
        if not macro_info or macro_info.get("type") != "function":
            return

        function_name = macro_info.get("function_name")
        file_path = macro_info.get("file_path")
        if function_name and file_path:
            self.macro_open_requested.emit(function_name, file_path)

    def add_macro_action(self, action: Any) -> None:
        """Add an action for macro items"""
        self.delegate.add_macro_action(action)

    def clear_actions(self) -> None:
        """Remove all actions from items"""
        self.delegate.clear_actions()

    def refresh(self):
        """Refresh the tree view"""
        if self.directory is None:
            return
        self._scan_macro_functions()

    def refresh_file_item(self, file_path: str):
        """Refresh a single file item by re-scanning its functions

        Args:
            file_path: Path to the Python file to refresh
        """
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Cannot refresh file item: {file_path} does not exist")
            return

        py_file = Path(file_path)

        # Find existing file item in the model
        existing_item = None
        existing_row = -1
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if not item or not item.data(Qt.ItemDataRole.UserRole):
                continue
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_data.get("type") == "file" and item_data.get("file_path") == str(py_file):
                existing_item = item
                existing_row = row
                break

        # Store expansion state if item exists
        was_expanded = existing_item and self.tree.isExpanded(existing_item.index())

        # Remove existing item if found
        if existing_item and existing_row >= 0:
            self.model.removeRow(existing_row)

        # Create new item using the helper method
        new_item = self._create_file_item(py_file)
        if new_item:
            # Insert at the same position or append if it was a new file
            insert_row = existing_row if existing_row >= 0 else self.model.rowCount()
            self.model.insertRow(insert_row, new_item)

            # Restore expansion state
            if was_expanded:
                self.tree.expand(new_item.index())
            else:
                self.tree.expand(new_item.index())

    def expand_all(self):
        """Expand all items in the tree"""
        self.tree.expandAll()

    def collapse_all(self):
        """Collapse all items in the tree"""
        self.tree.collapseAll()
