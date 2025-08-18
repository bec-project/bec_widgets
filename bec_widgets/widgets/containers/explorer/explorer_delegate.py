from __future__ import annotations

from typing import Any

from qtpy.QtCore import QModelIndex, QRect, QSortFilterProxyModel, Qt
from qtpy.QtGui import QPainter
from qtpy.QtWidgets import QAction, QStyledItemDelegate, QTreeView

from bec_widgets.utils.colors import get_theme_palette


class ExplorerDelegate(QStyledItemDelegate):
    """Custom delegate to show action buttons on hover for the explorer"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_index = QModelIndex()
        self.button_rects: list[QRect] = []
        self.current_macro_info = {}
        self.target_model = QSortFilterProxyModel

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
        if not isinstance(proxy_model, self.target_model):
            return

        actions = self.get_actions_for_current_item(proxy_model, index)
        if actions:
            self._draw_action_buttons(painter, option, actions)

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

    def get_actions_for_current_item(self, model, index) -> list[QAction] | None:
        """Get actions for the current item based on its type"""
        return None

    def editorEvent(self, event, model, option, index):
        """Handle mouse events for action buttons"""
        # Early return if not a left click
        if not (
            event.type() == event.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            return super().editorEvent(event, model, option, index)

        actions = self.get_actions_for_current_item(model, index)
        if not actions:
            return super().editorEvent(event, model, option, index)

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
