from __future__ import annotations

import shiboken6
from bec_lib import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils import BECConnector
from bec_widgets.utils.widget_highlighter import WidgetHighlighter
from bec_widgets.utils.widget_io import WidgetHierarchy

logger = bec_logger.logger


class WidgetHierarchyDialog(QDialog):
    """Popup dialog listing all widgets currently alive in the QApplication."""

    def __init__(self, root_widget: QWidget | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.root_widget = root_widget
        self.setWindowTitle("Widget Hierarchy")
        self.resize(520, 640)

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self._only_bec_checkbox = QCheckBox("Show only BECConnector widgets", self)
        controls.addWidget(self._only_bec_checkbox)
        self._visibility_filter = QComboBox(self)
        self._visibility_filter.addItem("All widgets", "all")
        self._visibility_filter.addItem("Visible only", "visible")
        self._visibility_filter.addItem("Hidden only", "hidden")
        controls.addWidget(self._visibility_filter)
        self._refresh_button = QToolButton(self)
        self._refresh_button.setText("Refresh")
        self._refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_button.setAutoRaise(True)
        self._refresh_button.setToolTip("Reload widget tree")
        self._refresh_button.clicked.connect(self._refresh_tree)
        controls.addWidget(self._refresh_button)
        controls.addStretch()
        layout.addLayout(controls)

        self._tree = QTreeWidget(self)
        self._tree.setAlternatingRowColors(True)
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Widget", "GUI ID", "Visible", "Find"])
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._tree.setColumnWidth(0, 260)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tree.setColumnWidth(1, 160)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._tree.setColumnWidth(2, 80)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._tree.setColumnWidth(3, 40)
        header.setSectionsMovable(True)
        layout.addWidget(self._tree)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._only_bec_checkbox.toggled.connect(self._refresh_tree)
        self._visibility_filter.currentIndexChanged.connect(self._refresh_tree)
        self._highlighter = WidgetHighlighter()
        self._refresh_tree()

    def refresh(self) -> None:
        self._refresh_tree()

    def closeEvent(self, event):
        if self._highlighter is not None:
            self._highlighter.cleanup()
        super().closeEvent(event)

    def _refresh_tree(self) -> None:
        self._tree.clear()
        only_bec = self._only_bec_checkbox.isChecked()
        roots = self._collect_root_widgets()
        widget_items: dict[QWidget, QTreeWidgetItem] = {}
        seen: set[int] = set()
        for root in roots:
            for node in WidgetHierarchy.iter_widget_tree(root):
                widget = node.widget
                widget_id = id(widget)
                if widget_id in seen:
                    continue
                seen.add(widget_id)

                if self._is_dialog_ancestor(widget):
                    continue

                if only_bec and not isinstance(widget, BECConnector):
                    continue

                parent_widget = (
                    WidgetHierarchy.get_becwidget_ancestor(widget) if only_bec else node.parent
                )
                parent_item = widget_items.get(parent_widget)
                item = self._create_tree_item(widget)
                if parent_item is None:
                    self._tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                self._add_highlight_button(item, widget)
                widget_items[widget] = item
        self._tree.expandAll()
        self._tree.resizeColumnToContents(0)
        self._tree.resizeColumnToContents(1)
        self._filter_tree_by_visibility()

    def _collect_root_widgets(self) -> list[QWidget]:
        if self.root_widget and shiboken6.isValid(self.root_widget):
            return [self.root_widget]
        app = QApplication.instance()
        if app is None:
            return []
        roots: list[QWidget] = []
        seen: set[int] = set()
        for widget in app.allWidgets():
            if not shiboken6.isValid(widget):
                continue
            parent = widget.parent()
            if parent is not None and shiboken6.isValid(parent):
                continue
            key = id(widget)
            if key in seen:
                continue
            seen.add(key)
            roots.append(widget)
        return roots

    def _create_tree_item(self, widget: QWidget) -> QTreeWidgetItem:
        labels = [
            self._format_widget_label(widget),
            self._get_gui_id(widget),
            self._visible_label(widget),
            "",
        ]
        item = QTreeWidgetItem(labels)
        item.setData(0, Qt.ItemDataRole.UserRole, widget)
        item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
        return item

    @staticmethod
    def _format_widget_label(widget: QWidget) -> str:
        object_name = widget.objectName() or "<unnamed>"
        return f"{widget.__class__.__name__} ({object_name})"

    @staticmethod
    def _get_gui_id(widget: QWidget) -> str:
        gui_id = getattr(widget, "gui_id", None)
        return str(gui_id) if gui_id else ""

    @staticmethod
    def _visible_label(widget: QWidget) -> str:
        try:
            return "Yes" if widget.isVisible() else "No"
        except Exception as e:
            logger.error(f"Error checking visibility for widget {widget}: {e}")
            return "Unknown"

    def _add_highlight_button(self, item: QTreeWidgetItem, widget: QWidget) -> None:
        button = QToolButton(self._tree)
        icon = material_icon("filter_center_focus", convert_to_pixmap=False)
        button.setIcon(icon)
        button.setEnabled(self._can_highlight(widget))
        button.clicked.connect(lambda _, w=widget: self._highlight_widget(w))
        self._tree.setItemWidget(item, 3, button)

    def _highlight_widget(self, widget: QWidget | None) -> None:
        if not self._can_highlight(widget):
            return
        self._highlighter.highlight(widget)

    @staticmethod
    def _can_highlight(widget: QWidget | None) -> bool:
        if widget is None or not shiboken6.isValid(widget):
            return False
        try:
            return widget.isVisible()
        except Exception:
            return False

    def _filter_tree_by_visibility(self) -> None:
        mode = self._visibility_filter.currentData()
        if mode in (None, "all"):
            return
        for index in reversed(range(self._tree.topLevelItemCount())):
            item = self._tree.topLevelItem(index)
            if not self._filter_item_by_visibility(item, mode):
                self._tree.takeTopLevelItem(index)

    def _filter_item_by_visibility(self, item: QTreeWidgetItem, mode: str) -> bool:
        has_match = self._matches_visibility_filter(item, mode)
        for idx in reversed(range(item.childCount())):
            child_item = item.child(idx)
            if not self._filter_item_by_visibility(child_item, mode):
                item.removeChild(child_item)
            else:
                has_match = True
        return has_match

    @staticmethod
    def _matches_visibility_filter(item: QTreeWidgetItem, mode: str) -> bool:
        if mode == "all":
            return True
        widget = item.data(0, Qt.ItemDataRole.UserRole)
        if widget is None or not shiboken6.isValid(widget):
            return False
        try:
            visible = widget.isVisible()
        except Exception:
            return False
        if mode == "visible":
            return visible
        if mode == "hidden":
            return not visible
        return True

    def _is_dialog_ancestor(self, widget: QWidget | None) -> bool:
        current = widget
        while current is not None and shiboken6.isValid(current):
            if current is self:
                return True
            current = current.parentWidget()
        return False
