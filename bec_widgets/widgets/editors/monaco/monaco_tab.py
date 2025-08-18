import PySide6QtAds as QtAds
from PySide6QtAds import CDockWidget
from qtpy.QtCore import QEvent, QTimer
from qtpy.QtWidgets import QToolButton, QVBoxLayout, QWidget

from bec_widgets import BECWidget
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget


class MonacoDock(BECWidget, QWidget):
    """
    MonacoDock is a dock widget that contains Monaco editor instances.
    It is used to manage multiple Monaco editors in a dockable interface.
    """

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        # Top-level layout hosting a toolbar and the dock manager
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self.dock_manager = QtAds.CDockManager(self)
        self._root_layout.addWidget(self.dock_manager)
        self.dock_manager.installEventFilter(self)

        self.add_editor()

    def _create_editor(self):
        widget = MonacoWidget(self)
        count = len(self.dock_manager.dockWidgets())
        dock = CDockWidget(f"Editor {count + 1}")
        dock.setWidget(widget)

        dock.setFeature(CDockWidget.DockWidgetDeleteOnClose, True)
        dock.setFeature(CDockWidget.CustomCloseHandling, True)
        dock.setFeature(CDockWidget.DockWidgetClosable, True)
        dock.setFeature(CDockWidget.DockWidgetFloatable, False)
        dock.setFeature(CDockWidget.DockWidgetMovable, True)

        dock.closeRequested.connect(lambda: self._on_editor_close_requested(dock, widget))

        return dock

    def _on_editor_close_requested(self, dock: CDockWidget, widget: QWidget):
        # Count all editor docks managed by this dock manager
        # TODO change this is wrong
        total = len(self.dock_manager.dockWidgets())
        if total <= 1:
            # Do not remove the last dock; just wipe its editor content
            widget.set_text("")
            return
        # Otherwise, proceed to close and delete the dock
        widget.close()
        dock.closeDockWidget()
        dock.deleteDockWidget()
        # After topology changes, make sure single-tab areas get a plus button
        QTimer.singleShot(0, self._scan_and_fix_areas)

    def _ensure_area_plus(self, area):
        if area is None:
            return
        # Only add once per area
        if getattr(area, "_monaco_plus_btn", None) is not None:
            return
        # If the area has exactly one tab, inject a + button next to the tab bar
        try:
            tabbar = area.titleBar().tabBar()
            count = tabbar.count() if hasattr(tabbar, "count") else 1
        except Exception:
            count = 1
        if count >= 1:
            plus_btn = QToolButton(area)
            plus_btn.setText("+")
            plus_btn.setToolTip("New Monaco Editor")
            plus_btn.setAutoRaise(True)
            tb = area.titleBar()
            idx = tb.indexOf(tb.tabBar())
            tb.insertWidget(idx + 1, plus_btn)
            plus_btn.clicked.connect(lambda: self.add_editor(area))
            area._monaco_plus_btn = plus_btn

    def _scan_and_fix_areas(self):
        # Find all dock areas under this manager and ensure each single-tab area has a plus button
        areas = self.dock_manager.findChildren(QtAds.CDockAreaWidget)
        for a in areas:
            self._ensure_area_plus(a)

    def eventFilter(self, obj, event):
        if obj is self.dock_manager and event.type() in (
            QEvent.ChildAdded,
            QEvent.ChildRemoved,
            QEvent.LayoutRequest,
        ):
            QTimer.singleShot(0, self._scan_and_fix_areas)
        return super().eventFilter(obj, event)

    def add_editor(self, area=None):
        """
        Adds a new Monaco editor dock widget to the dock manager.
        """
        new_dock = self._create_editor()
        if area is None:
            area = self.dock_manager.addDockWidgetTab(QtAds.TopDockWidgetArea, new_dock)
            self._ensure_area_plus(area)
        else:
            # If an area is provided, add the dock to that area
            self.dock_manager.addDockWidgetTabToArea(new_dock, area)
            self._ensure_area_plus(area)

        QTimer.singleShot(0, self._scan_and_fix_areas)
        return new_dock


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dock = MonacoDock()
    dock.show()
    sys.exit(app.exec())
