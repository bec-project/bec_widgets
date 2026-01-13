from __future__ import annotations

from functools import partial

from bec_lib import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import BECWidget, SafeSlot
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.widgets.containers.advanced_dock_area.profile_utils import (
    get_profile_info,
    is_quick_select,
    list_profiles,
    load_profile_screenshot,
    set_quick_select,
)

logger = bec_logger.logger


class WorkSpaceManager(BECWidget, QWidget):
    RPC = False
    PLUGIN = False
    COL_ACTIONS = 0
    COL_NAME = 1
    COL_AUTHOR = 2
    HEADERS = ["Actions", "Profile", "Author"]

    def __init__(
        self, parent=None, target_widget=None, default_profile: str | None = None, **kwargs
    ):
        super().__init__(parent=parent, **kwargs)
        self.target_widget = target_widget
        self.profile_namespace = (
            getattr(target_widget, "profile_namespace", None) if target_widget else None
        )
        self.accent_colors = get_accent_colors()
        self._init_ui()
        if self.target_widget is not None and hasattr(self.target_widget, "profile_changed"):
            self.target_widget.profile_changed.connect(self.on_profile_changed)
        if default_profile is not None:
            self._select_by_name(default_profile)
            self._show_profile_details(default_profile)

    def _init_ui(self):
        self.root_layout = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.root_layout.addWidget(self.splitter)

        # Init components
        self._init_profile_table()
        self._init_profile_details_tree()
        self._init_screenshot_preview()

        # Build two-column layout
        left_col = QVBoxLayout()
        left_col.addWidget(self.profile_table, 1)
        left_col.addWidget(self.profile_details_tree, 0)

        self.save_profile_button = QPushButton("Save current layout as new profile", self)
        self.save_profile_button.clicked.connect(self.save_current_as_profile)
        left_col.addWidget(self.save_profile_button)
        self.save_profile_button.setEnabled(self.target_widget is not None)

        # Wrap left widgets into a panel that participates in splitter sizing
        left_panel = QWidget(self)
        left_panel.setLayout(left_col)
        left_panel.setMinimumWidth(220)

        # Make the screenshot preview expand to fill remaining space
        self.screenshot_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.right_box = QGroupBox("Profile Screenshot Preview", self)
        right_col = QVBoxLayout(self.right_box)
        right_col.addWidget(self.screenshot_label, 1)

        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(self.right_box)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([350, 650])

    def _init_profile_table(self):
        self.profile_table = QTableWidget(self)
        self.profile_table.setColumnCount(len(self.HEADERS))
        self.profile_table.setHorizontalHeaderLabels(self.HEADERS)
        self.profile_table.setAlternatingRowColors(True)
        self.profile_table.verticalHeader().setVisible(False)

        # Enforce row selection, single-select, and disable edits
        self.profile_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.profile_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.profile_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Ensure the table expands to use vertical space in the left panel
        self.profile_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        header = self.profile_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignCenter)

        class _CenterDelegate(QStyledItemDelegate):
            def initStyleOption(self, option, index):
                super().initStyleOption(option, index)
                option.displayAlignment = Qt.AlignCenter

        self.profile_table.setItemDelegate(_CenterDelegate(self.profile_table))

        header.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_AUTHOR, QHeaderView.ResizeToContents)
        self.render_table()
        self.profile_table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.profile_table.cellClicked.connect(self._on_cell_clicked)

    def _init_profile_details_tree(self):
        self.profile_details_tree = QTreeWidget(self)
        self.profile_details_tree.setHeaderLabels(["Field", "Value"])
        # Keep details compact so the table can expand
        self.profile_details_tree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

    def _init_screenshot_preview(self):
        self.screenshot_label = QLabel(self)
        self.screenshot_label.setMinimumHeight(160)
        self.screenshot_label.setAlignment(Qt.AlignCenter)

    def render_table(self):
        self.profile_table.setRowCount(0)
        for profile in list_profiles(namespace=self.profile_namespace):
            self._add_profile_row(profile)

    def _add_profile_row(self, name: str):
        row = self.profile_table.rowCount()
        self.profile_table.insertRow(row)

        actions_items = QWidget(self)
        actions_items.profile_name = name
        actions_items_layout = QHBoxLayout(actions_items)
        actions_items_layout.setContentsMargins(0, 0, 0, 0)

        info = get_profile_info(name, namespace=self.profile_namespace)

        # Flags
        is_active = (
            self.target_widget is not None
            and getattr(self.target_widget, "_current_profile_name", None) == name
        )
        quick = info.is_quick_select
        is_read_only = info.is_read_only

        # Play (green if active)
        self._make_action_button(
            actions_items,
            "play_circle",
            "Switch to this profile",
            self.switch_profile,
            filled=is_active,
            color=(self.accent_colors.success if is_active else None),
        )

        # Quick-select (yellow if enabled)
        self._make_action_button(
            actions_items,
            "star",
            "Include in quick selection",
            self.toggle_quick_select,
            filled=quick,
            color=(self.accent_colors.warning if quick else None),
        )

        # Delete (red, disabled when read-only)
        delete_button = self._make_action_button(
            actions_items,
            "delete",
            "Delete this profile",
            self.delete_profile,
            color=self.accent_colors.emergency,
        )
        if is_read_only:
            delete_button.setEnabled(False)
            delete_button.setToolTip("Bundled profiles are read-only and cannot be deleted.")

        actions_items_layout.addStretch()

        self.profile_table.setCellWidget(row, self.COL_ACTIONS, actions_items)
        self.profile_table.setItem(row, self.COL_NAME, QTableWidgetItem(name))
        self.profile_table.setItem(row, self.COL_AUTHOR, QTableWidgetItem(info.author))

    def _make_action_button(
        self,
        parent: QWidget,
        icon_name: str,
        tooltip: str,
        slot: callable,
        *,
        filled: bool = False,
        color: str | None = None,
    ):
        button = QToolButton(parent=parent)
        button.setIcon(material_icon(icon_name, filled=filled, color=color))
        button.setToolTip(tooltip)
        button.clicked.connect(partial(slot, parent.profile_name))
        parent.layout().addWidget(button)
        return button

    def _select_by_name(self, name: str) -> None:
        for row in range(self.profile_table.rowCount()):
            item = self.profile_table.item(row, self.COL_NAME)
            if item and item.text() == name:
                self.profile_table.selectRow(row)
                break

    def _current_selected_profile(self) -> str | None:
        rows = self.profile_table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = self.profile_table.item(row, self.COL_NAME)
        return item.text() if item else None

    def _show_profile_details(self, name: str) -> None:
        info = get_profile_info(name, namespace=self.profile_namespace)
        self.profile_details_tree.clear()
        entries = [
            ("Name", info.name),
            ("Author", info.author or ""),
            ("Created", info.created or ""),
            ("Modified", info.modified or ""),
            ("Quick select", "Yes" if info.is_quick_select else "No"),
            ("Widgets", str(info.widget_count)),
            ("Size (KB)", str(info.size_kb)),
            ("User path", info.user_path or ""),
            ("Default path", info.default_path or ""),
        ]
        for k, v in entries:
            self.profile_details_tree.addTopLevelItem(QTreeWidgetItem([k, v]))
        self.profile_details_tree.expandAll()

        # Render screenshot preview from profile INI
        pm = load_profile_screenshot(name, namespace=self.profile_namespace)
        if pm is not None and not pm.isNull():
            scaled = pm.scaled(
                self.screenshot_label.width() or 800,
                self.screenshot_label.height() or 450,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.screenshot_label.setPixmap(scaled)
        else:
            self.screenshot_label.setPixmap(QPixmap())

    @SafeSlot()
    def _on_table_selection_changed(self):
        name = self._current_selected_profile()
        if name:
            self._show_profile_details(name)

    @SafeSlot(int, int)
    def _on_cell_clicked(self, row: int, column: int):
        item = self.profile_table.item(row, self.COL_NAME)
        if item:
            self._show_profile_details(item.text())

    ##################################################
    # Public Slots
    ##################################################
    @SafeSlot(str)
    def on_profile_changed(self, name: str):
        """Keep the manager in sync without forcing selection to the active profile."""
        selected = self._current_selected_profile()
        self.render_table()
        if selected:
            self._select_by_name(selected)
            self._show_profile_details(selected)

    @SafeSlot(str)
    def switch_profile(self, profile_name: str):
        self.target_widget.load_profile(profile_name)
        try:
            self.target_widget.toolbar.components.get_action(
                "workspace_combo"
            ).widget.setCurrentText(profile_name)
        except Exception as e:
            logger.warning(f"Warning: Could not update workspace combo box. {e}")

        self.render_table()
        self._select_by_name(profile_name)
        self._show_profile_details(profile_name)

    @SafeSlot(str)
    def toggle_quick_select(self, profile_name: str):
        enabled = is_quick_select(profile_name, namespace=self.profile_namespace)
        set_quick_select(profile_name, not enabled, namespace=self.profile_namespace)
        self.render_table()
        if self.target_widget is not None:
            self.target_widget._refresh_workspace_list()
        name = self._current_selected_profile()
        if name:
            self._show_profile_details(name)

    @SafeSlot()
    def save_current_as_profile(self):
        if self.target_widget is None:
            QMessageBox.information(
                self,
                "Save Profile",
                "No workspace is associated with this manager. Attach a workspace to save profiles.",
            )
            return

        self.target_widget.save_profile_dialog()
        # AdvancedDockArea will emit profile_changed which will trigger table refresh,
        # but ensure the UI stays in sync even if the signal is delayed.
        self.render_table()
        current = getattr(self.target_widget, "_current_profile_name", None)
        if current:
            self._select_by_name(current)
            self._show_profile_details(current)

    @SafeSlot(str)
    def delete_profile(self, profile_name: str):
        """
        Delete a profile by delegating to the target widget's delete_profile method.

        Args:
            profile_name: The name of the profile to delete.
        """
        if self.target_widget is None or not hasattr(self.target_widget, "delete_profile"):
            QMessageBox.warning(
                self, "Delete Profile", "No target widget available for profile deletion."
            )
            return

        try:
            result = self.target_widget.delete_profile(profile_name, show_dialog=True)
        except ValueError:
            # Error was already handled by target widget's dialog
            result = False

        if result:
            # Refresh our table and select next profile
            self.render_table()
            remaining_profiles = list_profiles(namespace=self.profile_namespace)
            if remaining_profiles:
                next_profile = remaining_profiles[0]
                self._select_by_name(next_profile)
                self._show_profile_details(next_profile)
            else:
                self.profile_details_tree.clear()
                self.screenshot_label.setPixmap(QPixmap())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        name = self._current_selected_profile()
        if not name:
            return
        pm = load_profile_screenshot(name, namespace=self.profile_namespace)
        if pm is None or pm.isNull():
            return
        scaled = pm.scaled(
            self.screenshot_label.width() or 800,
            self.screenshot_label.height() or 450,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.screenshot_label.setPixmap(scaled)
