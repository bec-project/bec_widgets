from typing import Optional

import PySide6QtAds as QtAds
from PySide6.QtWidgets import QTableWidget, QListWidget, QTableWidgetItem, QPushButton
from PySide6QtAds import CDockManager, CDockWidget
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QSplitter, QTreeWidget, QVBoxLayout, QWidget

from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow


class AutoHidePush(QWidget):

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Top-level layout hosting a toolbar and the dock manager
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)
        # CDockManager.setConfigFlag(CDockManager.FocusHighlighting, True)
        CDockManager.setAutoHideConfigFlags(CDockManager.DefaultAutoHideConfig)
        # CDockManager.setAutoHideConfigFlag(CDockManager.AutoHideShowOnMouseOver, True)
        self.dock_manager = CDockManager(self)
        self._root_layout.addWidget(self.dock_manager)

        # Initialize the widgets
        self.left_widget = QWidget(self)
        self.left_widget.layout = QVBoxLayout(self.left_widget)
        self.push_mode_btn = QPushButton(self.left_widget)
        self.push_mode_btn.setCheckable(True)
        self.push_mode_btn.setText("Pin (show and push)")
        self.push_mode_btn.setChecked(False)
        self.tree_widget = QTreeWidget(self)
        self.left_widget.layout.addWidget(self.push_mode_btn)
        self.left_widget.layout.addWidget(self.tree_widget)

        self.plotting_ads = AdvancedDockArea(self, mode="plot", default_add_direction="bottom")
        # table with some data
        self.table = QTableWidget(10, 3, self)
        self.table.setHorizontalHeaderLabels(["Column 1", "Column 2", "Column 3"])
        for row in range(10):
            for col in range(3):
                self.table.setItem(row, col, QTableWidgetItem(f"Item {row+1}, {col+1}"))

        self.list_widget = QListWidget(self)
        for i in range(10):
            self.list_widget.addItem(f"List Item {i+1}")

        # Create the dock widgets
        self.tree_dock = QtAds.CDockWidget("Explorer", self)
        self.tree_dock.setWidget(self.left_widget)

        self.table_dock = QtAds.CDockWidget("Table", self)
        self.table_dock.setWidget(self.table)

        self.plotting_ads_dock = QtAds.CDockWidget("Plotting Area", self)
        self.plotting_ads_dock.setWidget(self.plotting_ads)
        # this one will be autohide one
        self.list_dock = QtAds.CDockWidget("List Widget", self)
        self.list_dock.setWidget(self.list_widget)

        # Monaco will be central widget
        self.dock_manager.setCentralWidget(self.plotting_ads_dock)

        # Add the dock widgets to the dock manager
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.BottomDockWidgetArea, self.table_dock)
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.LeftDockWidgetArea, self.tree_dock)
        self.autohide_container = self.dock_manager.addAutoHideDockWidget(
            QtAds.SideBarRight, self.list_dock
        )
        self.autohide_container.setSize(350)
        self._last_side = QtAds.SideBarRight
        # Ensure auto-hide starts collapsed and button text is correct
        self.autohide_container.collapseView(True)
        self.push_mode_btn.setText("Pin (show and push)")

        # Connect signals
        self.push_mode_btn.toggled.connect(self.toggle_pin_mode)

    def toggle_pin_mode(self, pinned: bool):
        # pinned=True -> convert auto-hide overlay into a normal dock (push layout) and show it
        if pinned:
            if self.autohide_container is not None:
                # Remember the current side (edge) to restore when unpinning
                if hasattr(self.autohide_container, "sideBarLocation"):
                    self._last_side = self.autohide_container.sideBarLocation()
                # Move contents back into the dock container (this deletes the auto-hide container)
                self.autohide_container.moveContentsToParent()
                self.autohide_container = None
            # Ensure the dock is visible when pinned
            self.list_dock.show()
            self.push_mode_btn.setText("Unpin (send to sidebar)")
        else:
            # Convert the pinned dock back into an auto-hide overlay at the last used side and collapse it
            side = getattr(self, "_last_side", QtAds.SideBarRight)
            container = self.dock_manager.addAutoHideDockWidget(side, self.list_dock)
            # Preserve a sensible size from the current dock widget geometry
            if side in (QtAds.SideBarLeft, QtAds.SideBarRight):
                target_size = max(200, min(self.list_dock.width(), 600))
            else:
                target_size = max(200, min(self.list_dock.height(), 600))
            container.setSize(int(target_size))
            self.autohide_container = container
            # Collapse so it disappears to the side tab
            self.autohide_container.collapseView(True)
            self.push_mode_btn.setText("Pin (show and push)")


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    apply_theme("dark")
    auto_hide_overlay = AutoHidePush()
    auto_hide_overlay.show()
    auto_hide_overlay.resize(1200, 800)

    sys.exit(app.exec())
