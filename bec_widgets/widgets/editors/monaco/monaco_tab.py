from __future__ import annotations

import os
import pathlib
from typing import Any, cast

import PySide6QtAds as QtAds
from bec_lib.logger import bec_logger
from PySide6QtAds import CDockWidget
from qtpy.QtCore import QEvent, QTimer, Signal
from qtpy.QtWidgets import QFileDialog, QMessageBox, QToolButton, QVBoxLayout, QWidget

from bec_widgets import BECWidget
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget

logger = bec_logger.logger


class MonacoDock(BECWidget, QWidget):
    """
    MonacoDock is a dock widget that contains Monaco editor instances.
    It is used to manage multiple Monaco editors in a dockable interface.
    """

    focused_editor = Signal(object)  # Emitted when the focused editor changes
    save_enabled = Signal(bool)  # Emitted when the save action is enabled/disabled
    signature_help = Signal(str)  # Emitted when signature help is requested

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        # Top-level layout hosting a toolbar and the dock manager
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self.dock_manager = QtAds.CDockManager(self)
        self.dock_manager.setStyleSheet("")
        self.dock_manager.focusedDockWidgetChanged.connect(self._on_focus_event)
        self._root_layout.addWidget(self.dock_manager)
        self.dock_manager.installEventFilter(self)
        self._last_focused_editor: MonacoWidget | None = None
        self.focused_editor.connect(self._on_last_focused_editor_changed)
        self.add_editor()
        self._open_files = {}

    def _create_editor(self):
        widget = MonacoWidget(self)
        widget.save_enabled.connect(self.save_enabled.emit)
        widget.editor.signature_help_triggered.connect(self._on_signature_change)
        count = len(self.dock_manager.dockWidgets())
        dock = CDockWidget(f"Untitled_{count + 1}")
        dock.setWidget(widget)

        dock.setFeature(CDockWidget.DockWidgetDeleteOnClose, True)
        dock.setFeature(CDockWidget.CustomCloseHandling, True)
        dock.setFeature(CDockWidget.DockWidgetClosable, True)
        dock.setFeature(CDockWidget.DockWidgetFloatable, False)
        dock.setFeature(CDockWidget.DockWidgetMovable, True)

        dock.closeRequested.connect(lambda: self._on_editor_close_requested(dock, widget))

        return dock

    @property
    def last_focused_editor(self) -> CDockWidget | None:
        """
        Get the last focused editor.
        """
        return self._last_focused_editor

    @last_focused_editor.setter
    def last_focused_editor(self, editor: CDockWidget | None):
        self._last_focused_editor = editor
        self.focused_editor.emit(editor)

    def _on_last_focused_editor_changed(self, editor: CDockWidget | None):
        if editor is None:
            self.save_enabled.emit(False)
            return

        widget = cast(MonacoWidget, editor.widget())
        if widget.modified:
            logger.info(f"Editor '{widget.current_file}' has unsaved changes: {widget.get_text()}")
        self.save_enabled.emit(widget.modified)

    def _on_signature_change(self, signature: dict):
        signatures = signature.get("signatures", [])
        if not signatures:
            self.signature_help.emit("")
            return

        active_sig = signatures[signature.get("activeSignature", 0)]
        active_param = signature.get("activeParameter", 0)  # TODO: Add highlight for active_param

        # Get signature label and documentation
        label = active_sig.get("label", "")
        doc_obj = active_sig.get("documentation", {})
        documentation = doc_obj.get("value", "") if isinstance(doc_obj, dict) else str(doc_obj)

        # Format the markdown output
        markdown = f"```python\n{label}\n```\n\n{documentation}"
        self.signature_help.emit(markdown)

    def _on_focus_event(self, old_widget, new_widget) -> None:
        # Track focus events for the dock widget
        widget = new_widget.widget()
        if isinstance(widget, MonacoWidget):
            self.last_focused_editor = new_widget

    def _on_editor_close_requested(self, dock: CDockWidget, widget: QWidget):
        # Check if we have unsaved changes
        if widget.modified:
            # Prompt the user to save changes
            response = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if response == QMessageBox.StandardButton.Yes:
                self.save_file(widget)
            elif response == QMessageBox.StandardButton.Cancel:
                return

        # Count all editor docks managed by this dock manager
        total = len(self.dock_manager.dockWidgets())
        if total <= 1:
            # Do not remove the last dock; just wipe its editor content
            if hasattr(widget, "set_text"):
                widget.set_text("")
            dock.setWindowTitle("Untitled")
            dock.setTabToolTip("Untitled")
            return

        # Otherwise, proceed to close and delete the dock
        widget.close()
        dock.closeDockWidget()
        dock.deleteDockWidget()
        if self.last_focused_editor is dock:
            self.last_focused_editor = None
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
            # pylint: disable=protected-access
            area._monaco_plus_btn = plus_btn

    def _scan_and_fix_areas(self):
        # Find all dock areas under this manager and ensure each single-tab area has a plus button
        areas = self.dock_manager.findChildren(QtAds.CDockAreaWidget)
        for a in areas:
            self._ensure_area_plus(a)

    def eventFilter(self, obj, event):
        # Track dock manager events
        if obj is self.dock_manager and event.type() in (
            QEvent.Type.ChildAdded,
            QEvent.Type.ChildRemoved,
            QEvent.Type.LayoutRequest,
        ):
            QTimer.singleShot(0, self._scan_and_fix_areas)

        return super().eventFilter(obj, event)

    def add_editor(
        self, area: Any | None = None, title: str | None = None, tooltip: str | None = None
    ):  # Any as qt ads does not return a proper type
        """
        Adds a new Monaco editor dock widget to the dock manager.
        """
        new_dock = self._create_editor()
        if title is not None:
            new_dock.setWindowTitle(title)
        if tooltip is not None:
            new_dock.setTabToolTip(tooltip)
        if area is None:
            area_obj = self.dock_manager.addDockWidgetTab(QtAds.TopDockWidgetArea, new_dock)
            self._ensure_area_plus(area_obj)
        else:
            # If an area is provided, add the dock to that area
            self.dock_manager.addDockWidgetTabToArea(new_dock, area)
            self._ensure_area_plus(area)

        QTimer.singleShot(0, self._scan_and_fix_areas)
        return new_dock

    def open_file(self, file_name: str):
        """
        Open a file in the specified area. If the file is already open, activate it.
        """
        open_files = self._get_open_files()
        if file_name in open_files:
            dock = self._get_editor_dock(file_name)
            if dock is not None:
                dock.setAsCurrentTab()
            return

        file = os.path.basename(file_name)
        # If the current editor is empty, we reuse it

        # For now, the dock manager is only for the editor docks. We can therefore safely assume
        # that all docks are editor docks.
        dock_area = self.dock_manager.dockArea(0)

        editor_dock = dock_area.currentDockWidget()
        editor_widget = editor_dock.widget() if editor_dock else None
        if editor_widget:
            editor_widget = cast(MonacoWidget, editor_dock.widget())
            if editor_widget.current_file is None and editor_widget.get_text() == "":
                editor_dock.setWindowTitle(file)
                editor_dock.setTabToolTip(file_name)
                editor_widget.open_file(file_name)
                return

        # File is not open, create a new editor
        editor_dock = self.add_editor(title=file, tooltip=file_name)
        widget = cast(MonacoWidget, editor_dock.widget())
        widget.open_file(file_name)

    def save_file(
        self, widget: MonacoWidget | None = None, force_save_as: bool = False, format_on_save=True
    ) -> None:
        """
        Save the currently focused file.

        Args:
            widget (MonacoWidget | None): The widget to save. If None, the last focused editor will be used.
            force_save_as (bool): If True, the "Save As" dialog will be shown even if the file is already saved.
        """
        if widget is None:
            widget = self.last_focused_editor.widget() if self.last_focused_editor else None
        if not widget:
            return
        if widget.current_file and not force_save_as:
            if format_on_save and pathlib.Path(widget.current_file).suffix == ".py":
                widget.format()
            with open(widget.current_file, "w", encoding="utf-8") as f:
                f.write(widget.get_text())
            # pylint: disable=protected-access
            widget._original_content = widget.get_text()
            widget.save_enabled.emit(False)
            return

        # Save as option
        save_file = QFileDialog.getSaveFileName(self, "Save File As", "", "All files (*)")

        if save_file:
            # check if we have suffix specified
            file = pathlib.Path(save_file[0])
            if file.suffix == "":
                file = file.with_suffix(".py")
            if format_on_save and file.suffix == ".py":
                widget.format()

            text = widget.get_text()
            with open(file, "w", encoding="utf-8") as f:
                f.write(text)
            widget._original_content = text
            widget.save_enabled.emit(False)

        print(f"Save file called, last focused editor: {self.last_focused_editor}")

    def set_vim_mode(self, enabled: bool):
        """
        Set Vim mode for all editor widgets.

        Args:
            enabled (bool): Whether to enable or disable Vim mode.
        """
        for widget in self.dock_manager.dockWidgets():
            editor_widget = cast(MonacoWidget, widget.widget())
            editor_widget.set_vim_mode_enabled(enabled)

    def _get_open_files(self) -> list[str]:
        open_files = []
        for widget in self.dock_manager.dockWidgets():
            editor_widget = cast(MonacoWidget, widget.widget())
            if editor_widget.current_file is not None:
                open_files.append(editor_widget.current_file)
        return open_files

    def _get_editor_dock(self, file_name: str) -> CDockWidget | None:
        for widget in self.dock_manager.dockWidgets():
            editor_widget = cast(MonacoWidget, widget.widget())
            if editor_widget.current_file == file_name:
                return widget
        return None


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    _dock = MonacoDock()
    _dock.show()
    sys.exit(app.exec())
