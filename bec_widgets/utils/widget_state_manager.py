from __future__ import annotations

import shiboken6
from bec_lib import bec_logger
from qtpy.QtCore import QSettings
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.widget_io import WidgetHierarchy

logger = bec_logger.logger


class WidgetStateManager:
    """
    Manage saving and loading widget state to/from an INI file.

    Args:
        widget (QWidget): Root widget whose subtree will be serialized.
        serialize_from_root (bool): When True, build group names relative to
            this root and ignore parents above it. This keeps profiles portable
            between different host window hierarchies.
        root_id (str | None): Optional stable label to use for the root in
            the settings key path. When omitted and `serialize_from_root` is
            True, the class name of `widget` is used, falling back to its
            objectName and finally to "root".
    """

    def __init__(self, widget, *, serialize_from_root: bool = False, root_id: str | None = None):
        self.widget = widget
        self._serialize_from_root = bool(serialize_from_root)
        self._root_id = root_id

    def save_state(self, filename: str | None = None, settings: QSettings | None = None):
        """
        Save the state of the widget to an INI file.

        Args:
            filename(str): The filename to save the state to.
            settings(QSettings): Optional QSettings object to save the state to.
        """
        if not filename and not settings:
            filename, _ = QFileDialog.getSaveFileName(
                self.widget, "Save Settings", "", "INI Files (*.ini)"
            )
        if filename:
            settings = QSettings(filename, QSettings.IniFormat)
            self._save_widget_state_qsettings(self.widget, settings)
        elif settings:
            # If settings are provided, save the state to the provided QSettings object
            self._save_widget_state_qsettings(self.widget, settings)
        else:
            logger.warning("No filename or settings provided for saving state.")

    def load_state(self, filename: str | None = None, settings: QSettings | None = None):
        """
        Load the state of the widget from an INI file.

        Args:
            filename(str): The filename to load the state from.
            settings(QSettings): Optional QSettings object to load the state from.
        """
        if not filename and not settings:
            filename, _ = QFileDialog.getOpenFileName(
                self.widget, "Load Settings", "", "INI Files (*.ini)"
            )
        if filename:
            settings = QSettings(filename, QSettings.IniFormat)
            self._load_widget_state_qsettings(self.widget, settings)
        elif settings:
            # If settings are provided, load the state from the provided QSettings object
            self._load_widget_state_qsettings(self.widget, settings)
        else:
            logger.warning("No filename or settings provided for saving state.")

    def _save_widget_state_qsettings(
        self, widget: QWidget, settings: QSettings, recursive: bool = True
    ):
        """
        Save the state of the widget to QSettings.

        Args:
            widget(QWidget): The widget to save the state for.
            settings(QSettings): The QSettings object to save the state to.
            recursive(bool): Whether to recursively save the state of child widgets.
        """
        if widget is None or not shiboken6.isValid(widget):
            return

        if widget.property("skip_settings") is True:
            return

        meta = widget.metaObject()
        widget_name = self._get_full_widget_name(widget)
        settings.beginGroup(widget_name)
        for i in range(meta.propertyCount()):
            prop = meta.property(i)
            name = prop.name()

            # Always save `visible` as True to avoid restoring hidden widgets from profiles.
            if name == "visible":
                settings.setValue(name, True)
                continue

            if (
                name == "objectName"
                or not prop.isReadable()
                or not prop.isWritable()
                or not prop.isStored()  # can be extended to fine filter
            ):
                continue

            value = widget.property(name)
            settings.setValue(name, value)
        settings.endGroup()

        # Recursively process children (only if they aren't skipped)
        if not recursive:
            return

        direct_children = widget.children()
        bec_connector_children = WidgetHierarchy.get_bec_connectors_from_parent(widget)
        all_children = list(
            set(direct_children) | set(bec_connector_children)
        )  # to avoid duplicates
        for child in all_children:
            if (
                child
                and shiboken6.isValid(child)
                and child.objectName()
                and child.property("skip_settings") is not True
                and not isinstance(child, QLabel)
            ):
                self._save_widget_state_qsettings(child, settings, False)
        logger.info(f"Saved state for widget '{widget_name}'")

    def _load_widget_state_qsettings(
        self, widget: QWidget, settings: QSettings, recursive: bool = True
    ):
        """
        Load the state of the widget from QSettings.

        Args:
            widget(QWidget): The widget to load the state for.
            settings(QSettings): The QSettings object to load the state from.
            recursive(bool): Whether to recursively load the state of child widgets.
        """
        if widget is None or not shiboken6.isValid(widget):
            return

        if widget.property("skip_settings") is True:
            return

        meta = widget.metaObject()
        widget_name = self._get_full_widget_name(widget)
        settings.beginGroup(widget_name)
        for i in range(meta.propertyCount()):
            prop = meta.property(i)
            name = prop.name()
            if settings.contains(name):
                value = settings.value(name)
                widget.setProperty(name, value)
        settings.endGroup()

        if not recursive:
            return
        # Recursively process children (only if they aren't skipped)
        direct_children = widget.children()
        bec_connector_children = WidgetHierarchy.get_bec_connectors_from_parent(widget)
        all_children = list(
            set(direct_children) | set(bec_connector_children)
        )  # to avoid duplicates
        for child in all_children:
            if (
                child
                and shiboken6.isValid(child)
                and child.objectName()
                and child.property("skip_settings") is not True
                and not isinstance(child, QLabel)
            ):
                self._load_widget_state_qsettings(child, settings, False)

    def _get_full_widget_name(self, widget: QWidget) -> str:
        """
        Build a group key for *widget*.

        When `serialize_from_root` is False (default), this preserves the original
        behavior and walks all parents up to the top-level widget.

        When `serialize_from_root` is True, the key is built relative to
        `self.widget` and parents above the managed root are ignored. The first
        path segment is either `root_id` (when provided) or a stable label derived
        from the root widget (class name, then objectName, then "root").

        Args:
            widget (QWidget): The widget to build the key for.
        """
        # Backwards-compatible behavior: include the entire parent chain.
        if not getattr(self, "_serialize_from_root", False):
            name = widget.objectName()
            parent = widget.parent()
            while parent:
                obj_name = parent.objectName() or parent.metaObject().className()
                name = obj_name + "." + name
                parent = parent.parent()
            return name

        parts: list[str] = []
        current: QWidget | None = widget

        while current is not None:
            if current is self.widget:
                # Reached the serialization root.
                root_label = self._root_id
                if not root_label:
                    meta = current.metaObject() if hasattr(current, "metaObject") else None
                    class_name = meta.className() if meta is not None else ""
                    root_label = class_name or current.objectName() or "root"
                parts.append(str(root_label))
                break

            obj_name = current.objectName() or current.metaObject().className()
            parts.append(obj_name)
            current = current.parent()

        parts.reverse()
        return ".".join(parts)


class ExampleApp(QWidget):  # pragma: no cover:
    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle("State Manager Example")

        layout = QVBoxLayout(self)

        # A line edit to store some user text
        self.line_edit = QLineEdit(self)
        self.line_edit.setObjectName("MyLineEdit")
        self.line_edit.setPlaceholderText("Enter some text here...")
        layout.addWidget(self.line_edit)

        # A spin box to hold a numeric value
        self.spin_box = QSpinBox(self)
        self.spin_box.setObjectName("MySpinBox")
        self.spin_box.setRange(0, 100)
        layout.addWidget(self.spin_box)

        # A checkbox to hold a boolean value
        self.check_box = QCheckBox("Enable feature?", self)
        self.check_box.setObjectName("MyCheckBox")
        layout.addWidget(self.check_box)

        # A checkbox that we want to skip
        self.check_box_skip = QCheckBox("Enable feature - skip save?", self)
        self.check_box_skip.setProperty("skip_state", True)
        self.check_box_skip.setObjectName("MyCheckBoxSkip")
        layout.addWidget(self.check_box_skip)

        #  CREATE A "SIDE PANEL" with nested structure and skip all what is inside
        self.side_panel = QWidget(self)
        self.side_panel.setObjectName("SidePanel")
        self.side_panel.setProperty("skip_settings", True)  # skip the ENTIRE panel
        layout.addWidget(self.side_panel)

        # Put some sub-widgets inside side_panel
        panel_layout = QVBoxLayout(self.side_panel)
        self.panel_label = QLabel("Label in side panel", self.side_panel)
        self.panel_label.setObjectName("PanelLabel")
        panel_layout.addWidget(self.panel_label)

        self.panel_edit = QLineEdit(self.side_panel)
        self.panel_edit.setObjectName("PanelLineEdit")
        self.panel_edit.setPlaceholderText("I am inside side panel")
        panel_layout.addWidget(self.panel_edit)

        self.panel_checkbox = QCheckBox("Enable feature in side panel?", self.side_panel)
        self.panel_checkbox.setObjectName("PanelCheckBox")
        panel_layout.addWidget(self.panel_checkbox)

        # Save/Load buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save State", self)
        self.load_button = QPushButton("Load State", self)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        layout.addLayout(button_layout)

        # Create the state manager
        self.state_manager = WidgetStateManager(self)

        # Connect buttons
        self.save_button.clicked.connect(lambda: self.state_manager.save_state())
        self.load_button.clicked.connect(lambda: self.state_manager.load_state())


if __name__ == "__main__":  # pragma: no cover:
    import sys

    app = QApplication(sys.argv)
    w = ExampleApp()
    w.show()
    sys.exit(app.exec_())
